#!/usr/bin/env python3
"""Captura as telas do manual de compras, já com as caixas numeradas.

Uso:
    python scripts/seed_manual_compras.py        # 1. o cenário
    python scripts/capturar_manual_compras.py    # 2. as fotos
    python scripts/gerar_manual_compras.py       # 3. o PDF

Pré-requisito: o app de pé em http://localhost:5000.

A REGRA DESTE ARQUIVO: falhou, para. Nada de `except Exception: continue`.
📖 `scripts/capturar_manual_ciclo.py:76-79` engole o erro e segue, e como o
gerador do PDF lê a pasta por nome de arquivo, o manual sai montado com a foto
velha — sem aviso nenhum. Aqui, seletor que não casa, tela que não abre ou
login que falha derrubam o processo com exit ≠ 0 e dizem qual passo quebrou.
"""
import os
import shutil
import sys
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from playwright.sync_api import sync_playwright

from anotar_captura import MarcacaoQuebrada, executar, marcar

# ---------------------------------------------------------------------------
# O Chromium do Playwright não sobe neste ambiente sem ajuda.
#
# 🔬 18/08: `chrome-headless-shell` reclama de `libnspr4.so`, `libnss3.so`,
# `libasound.so.2`, `libgbm.so.1` e `libxkbcommon.so.0`. As cinco EXISTEM no
# nix store — o que falta é o caminho. Em CI o problema não aparece porque
# 📖 `.github/workflows/browser-noturno.yml:44` roda
# `playwright install --with-deps`, que aqui não é possível (precisa de root).
#
# As bibliotecas são procuradas por PADRÃO, não por hash fixo: hash de nix
# store é o mesmo tipo de número sem procedência que aposentou a captura de
# 22/07. Se a busca falhar, o script diz qual biblioteca faltou.
# ---------------------------------------------------------------------------
_LIBS = {
    'libnspr4.so': '/nix/store/*nspr-4.3*/lib',
    'libnss3.so': '/nix/store/*nss-3.*/lib',
    'libasound.so.2': '/nix/store/*alsa-lib-1.2*/lib',
    'libgbm.so.1': '/nix/store/*mesa-libgbm*/lib',
    'libxkbcommon.so.0': '/nix/store/*libxkbcommon-1*/lib',
}


def _e_64bits(caminho):
    """ELFCLASS64 no 5º byte. O store tem builds de 32 bits do mesmo nome."""
    try:
        with open(caminho, 'rb') as fh:
            return fh.read(5)[4:5] == b'\x02'
    except OSError:
        return False


# O caminho resolvido é gravado aqui. /nix/store tem dezenas de milhares de
# entradas: varrê-lo cinco vezes (uma por biblioteca) leva minutos e foi como
# a primeira versão deste script "travou" sem imprimir nada. Uma passada só,
# e o resultado fica em cache para as próximas rodadas.
_CACHE_LD = Path('.cache/sige_ld_library_path')


def preparar_bibliotecas():
    import fnmatch

    if os.environ.get('SIGE_PULAR_LIBS'):
        return
    if _CACHE_LD.exists():
        caminho = _CACHE_LD.read_text().strip()
        if caminho and all(os.path.isdir(d) for d in caminho.split(':') if d):
            _aplicar_ld(caminho)
            return

    try:
        entradas = os.listdir('/nix/store')
    except OSError:
        raise SystemExit('/nix/store não existe — rode com SIGE_PULAR_LIBS=1')

    achados, faltando = [], []
    for lib, padrao in _LIBS.items():
        alvo = padrao.split('/')[3]          # o pedaço com o glob
        for nome in sorted(entradas):
            if not fnmatch.fnmatch(nome, alvo):
                continue
            d = os.path.join('/nix/store', nome, 'lib')
            if _e_64bits(os.path.join(d, lib)):
                achados.append(d)
                break
        else:
            faltando.append(lib)

    if faltando:
        raise SystemExit(
            'não achei no nix store, em 64 bits: ' + ', '.join(faltando)
            + '\nSe o seu ambiente já resolve isso, rode com SIGE_PULAR_LIBS=1.')

    caminho = ':'.join(achados)
    _CACHE_LD.parent.mkdir(parents=True, exist_ok=True)
    _CACHE_LD.write_text(caminho)
    _aplicar_ld(caminho)


def _aplicar_ld(caminho):
    anterior = os.environ.get('LD_LIBRARY_PATH', '')
    os.environ['LD_LIBRARY_PATH'] = caminho + (':' + anterior if anterior else '')


BASE = os.environ.get('SIGE_BASE', 'http://localhost:5000')
SAIDA = Path('docs/manual_compras/screenshots')
VIEWPORT = {'width': 1440, 'height': 950}


def entrar(page, username):
    page.goto(f'{BASE}/login', wait_until='domcontentloaded', timeout=30000)
    page.fill('input[name="username"]', username)
    page.fill('input[name="password"]', SENHA)
    page.click('button[type="submit"]')
    page.wait_for_load_state('domcontentloaded')
    if '/login' in page.url:
        raise SystemExit(f'login falhou para {username} — URL final {page.url}')


def main():
    preparar_bibliotecas()
    from roteiro_manual_compras import telas
    from seed_manual_compras import MARCA, PESSOAS, SENHA
    globals()['SENHA'] = SENHA
    roteiro = telas()
    if SAIDA.exists():
        shutil.rmtree(SAIDA)          # foto velha não sobrevive a esta rodada
    SAIDA.mkdir(parents=True, exist_ok=True)

    usuarios = {chave: f'{MARCA}_{chave}' if chave != 'admin' else f'{MARCA}_admin'
                for chave, _u, _n, _c in PESSOAS}

    falhas = []
    with sync_playwright() as p:
        browser = p.chromium.launch(
            headless=True, args=['--no-sandbox', '--disable-dev-shm-usage'])
        contextos, paginas = {}, {}

        def pagina_de(papel):
            if papel not in paginas:
                ctx = browser.new_context(viewport=VIEWPORT)
                contextos[papel] = ctx
                pg = ctx.new_page()
                if papel != 'anon':
                    if papel not in usuarios:
                        raise SystemExit(f'papel desconhecido no roteiro: {papel}')
                    entrar(pg, usuarios[papel])
                paginas[papel] = pg
            return paginas[papel]

        for tela in roteiro:
            destino = SAIDA / f'{tela.slug}.png'
            print(f'  {tela.slug:24s} {tela.papel:12s} {tela.rota}')
            pg = pagina_de(tela.papel)
            try:
                # `networkidle` NÃO serve aqui: a interface do SIGE mantém
                # requisição de fundo e o evento não dispara — a primeira versão
                # deste script esperou 30 s por tela e não capturou nenhuma.
                resp = pg.goto(f'{BASE}{tela.rota}', wait_until='domcontentloaded',
                               timeout=30000)
                if resp is not None and resp.status >= 400:
                    raise RuntimeError(f'HTTP {resp.status}')
                if tela.papel != 'anon' and '/login' in pg.url:
                    raise RuntimeError('caiu no login — sessão perdida ou sem permissão')
                pg.wait_for_timeout(1600)  # Select2, gráficos e o que carrega por JS
                pg.evaluate("""() => document.querySelectorAll(
                    '.modal.show, .modal-backdrop, .toast').forEach(e => e.remove())""")
                # As ações vêm ANTES da marcação: metade destas telas só existe
                # depois de um POST (a recusa do formulário, o aviso da alçada,
                # o selo da emergência), e o que se fotografa é a resposta.
                if tela.acoes:
                    print(f'      {executar(pg, tela.acoes)} ação(ões) antes da foto')
                    pg.wait_for_timeout(400)
                marcar(pg, tela.campos)
                if tela.recorte:
                    alvo = pg.query_selector(tela.recorte)
                    if alvo is None:
                        raise MarcacaoQuebrada(
                            f'recorte não existe na página: {tela.recorte}')
                    caixa = alvo.bounding_box()
                    folga = 28   # espaço para o badge, que fica fora do campo
                    pg.screenshot(path=str(destino), clip={
                        'x': max(caixa['x'] - folga, 0),
                        'y': max(caixa['y'] - folga, 0),
                        'width': caixa['width'] + folga * 2,
                        'height': caixa['height'] + folga * 2})
                else:
                    pg.screenshot(path=str(destino), full_page=True)
                print(f'      -> {destino.name} ({destino.stat().st_size // 1024} KB)')
            except MarcacaoQuebrada as e:
                falhas.append((tela.slug, f'marcação: {e}'))
                print(f'      !! MARCAÇÃO QUEBRADA: {e}')
            except Exception as e:
                falhas.append((tela.slug, f'{type(e).__name__}: {e}'))
                print(f'      !! FALHOU: {type(e).__name__}: {e}')

        browser.close()

    if falhas:
        print(f'\n{len(falhas)} de {len(roteiro)} telas falharam:')
        for slug, motivo in falhas:
            print(f'  - {slug}: {motivo}')
        sys.exit(1)

    print(f'\n[OK] {len(roteiro)} telas capturadas em {SAIDA}')


if __name__ == '__main__':
    main()
