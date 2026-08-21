#!/usr/bin/env python3
"""Captura as telas do manual do RDO, já com as caixas numeradas.

Uso:
    .pythonlibs/bin/python scripts/seed_manual_rdo.py        # 1. o cenário
    .pythonlibs/bin/python scripts/capturar_manual_rdo.py    # 2. as fotos
    .pythonlibs/bin/python scripts/gerar_manual_rdo.py       # 3. o PDF

Pré-requisito: o app de pé em SIGE_BASE (default http://localhost:5000).

A REGRA (herdada de capturar_manual_compras.py): falhou, para. Seletor que não
casa, tela que não abre, login que falha → exit ≠ 0 com o nome da tela.

O que é diferente de compras: o formulário de RDO é preenchido em etapas na
MESMA página (`Tela.permanece`), o id do RDO nasce no meio da captura
(`Tela.guarda_id` lê da URL), reabrir/retificar pedem motivo num `prompt`
(tratado pelo handler de dialog) e as fotos são PNGs gerados aqui.

Plano: docs/superpowers/plans/2026-08-21-manual-visual-rdo.md
"""
import os
import re
import shutil
import sys
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
os.environ.setdefault('SIGE_BOOT_DDL', '0')
os.environ.setdefault('SIGE_ENABLE_DEMO_SEED', 'false')

from playwright.sync_api import sync_playwright

from anotar_captura import Acao, MarcacaoQuebrada, executar, limpar, marcar
from capturar_manual_compras import entrar, preparar_bibliotecas

BASE = os.environ.get('SIGE_BASE', 'http://localhost:5000')
SAIDA = Path('docs/manual_rdo/screenshots')
FOTOS_DIR = Path('.cache/manual_rdo_fotos')
VIEWPORT = {'width': 1440, 'height': 950}


def _fotos():
    """Três PNGs distintos, com legenda, para o input de fotos."""
    from PIL import Image, ImageDraw
    FOTOS_DIR.mkdir(parents=True, exist_ok=True)
    caminhos = []
    for n, (texto, cor) in enumerate([('Frente de servico - 7h', (120, 140, 160)),
                                      ('Blocos B1 e B2 concretados', (150, 130, 110)),
                                      ('Chuva - 10h', (100, 110, 130))], start=1):
        img = Image.new('RGB', (960, 640), cor)
        ImageDraw.Draw(img).text((30, 30), texto, fill=(255, 255, 255))
        p = FOTOS_DIR / f'foto{n}.png'
        img.save(p)
        caminhos.append(str(p.resolve()))
    return caminhos


def _ultimo_rdo_id(admin_id):
    """O id do RDO mais novo do tenant. 📖 views/rdo.py: depois de salvar, só
    ADMIN cai em /rdo/<id>; FUNCIONARIO (o encarregado) vai para o consolidado —
    então o id nem sempre está na URL."""
    from app import app
    from models import RDO, Obra
    with app.app_context():
        obra_ids = [o.id for o in Obra.query.filter_by(admin_id=admin_id).all()]
        r = (RDO.query.filter(RDO.obra_id.in_(obra_ids))
             .order_by(RDO.id.desc()).first())
        return r.id if r else None


def main():
    preparar_bibliotecas()
    import capturar_manual_compras
    from roteiro_manual_rdo import MOTIVO_REABERTURA, MOTIVO_RETIFICACAO, telas
    from seed_manual_rdo import MARCA, SENHA, limpar_rdos
    capturar_manual_compras.SENHA = SENHA        # `entrar` lê o módulo dele

    # RDO do dia anterior atrapalha: a captura sempre começa do zero.
    import main as _main  # noqa: F401
    from app import app
    from models import Usuario
    with app.app_context():
        admin = Usuario.query.filter_by(username=f'{MARCA}_admin').one()
        admin_id = admin.id               # fora do contexto o objeto fica detached
        print(f'  {limpar_rdos(admin_id)} RDO(s) anteriores apagados')

    roteiro = telas()
    if SAIDA.exists():
        shutil.rmtree(SAIDA)          # foto velha não sobrevive a esta rodada
    SAIDA.mkdir(parents=True, exist_ok=True)
    f1, f2, f3 = _fotos()
    ctx = {'foto1': f1, 'foto2': f2, 'foto3': f3}
    usuarios = {'encarregado': f'{MARCA}_encarregado', 'gestor': f'{MARCA}_gestor',
                'admin': f'{MARCA}_admin'}

    def resolver(texto):
        if not texto or '{' not in texto:
            return texto
        try:
            return texto.format(**ctx)
        except KeyError as e:
            raise SystemExit(f'rota/valor usa {e} antes de ele existir — ordem do roteiro')

    def _aceitar(d):
        # reabrir/retificar pedem o motivo num prompt(): aceitar com o motivo do
        # roteiro, para o documento sair com texto de verdade.
        msg = (d.message or '').lower()
        if 'reabert' in msg:
            d.accept(MOTIVO_REABERTURA)
        elif 'retific' in msg:
            d.accept(MOTIVO_RETIFICACAO)
        else:
            d.accept()

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True,
                                    args=['--no-sandbox', '--disable-dev-shm-usage'])
        paginas = {}

        def pagina_de(papel):
            if papel not in paginas:
                pg = browser.new_context(viewport=VIEWPORT).new_page()
                pg.on('dialog', _aceitar)
                if papel != 'anon':
                    if papel not in usuarios:
                        raise SystemExit(f'papel desconhecido no roteiro: {papel}')
                    entrar(pg, usuarios[papel])
                paginas[papel] = pg
            return paginas[papel]

        atual = None
        for tela in roteiro:
            destino = SAIDA / f'{tela.slug}.png'
            rota = resolver(tela.rota)
            print(f'  {tela.slug:22s} {tela.papel:12s} '
                  f'{"(mesma página)" if tela.permanece else rota}')
            pg = atual if tela.permanece else pagina_de(tela.papel)
            if pg is None:
                raise SystemExit(f'{tela.slug}: permanece=True sem tela anterior')
            try:
                if not tela.permanece:
                    resp = pg.goto(f'{BASE}{rota}', wait_until='domcontentloaded',
                                   timeout=30000)
                    if resp is not None and resp.status >= 400:
                        raise RuntimeError(f'HTTP {resp.status}')
                    if tela.papel != 'anon' and '/login' in pg.url:
                        raise RuntimeError('caiu no login — sessão perdida ou sem permissão')
                    pg.wait_for_timeout(1600)  # Select2, gráficos e o que carrega por JS
                    pg.evaluate("""() => document.querySelectorAll(
                        '.modal-backdrop, .toast').forEach(e => e.remove())""")
                else:
                    limpar(pg)                 # as caixas da foto anterior
                acoes = [Acao(a.tipo, resolver(a.seletor), resolver(a.valor))
                         for a in tela.acoes]
                if acoes:
                    print(f'      {executar(pg, acoes)} ação(ões) antes da foto')
                    pg.wait_for_timeout(600)
                if tela.guarda_id:
                    m = re.search(r'/rdo/(\d+)', pg.url)
                    rid = m.group(1) if m else _ultimo_rdo_id(admin_id)
                    if not rid:
                        raise RuntimeError(
                            f'guarda_id={tela.guarda_id}: nenhum RDO na URL nem no banco ({pg.url})')
                    ctx[tela.guarda_id] = str(rid)
                    print(f'      {tela.guarda_id} = {rid}')
                    if not m:
                        # a foto desta tela é o RDO recém-salvo, não a página do redirect
                        pg.goto(f'{BASE}/rdo/{rid}', wait_until='domcontentloaded', timeout=30000)
                        pg.wait_for_timeout(1200)
                marcar(pg, tela.campos)
                if tela.recorte:
                    alvo = pg.query_selector(tela.recorte)
                    if alvo is None:
                        raise MarcacaoQuebrada(f'recorte não existe na página: {tela.recorte}')
                    alvo.screenshot(path=str(destino))
                else:
                    pg.screenshot(path=str(destino), full_page=True)
            except (MarcacaoQuebrada, RuntimeError) as e:
                raise SystemExit(f'\nFALHOU em {tela.slug}: {e}\nURL: {pg.url}')
            atual = pg
        browser.close()
    print(f'\n{len(roteiro)} capturas em {SAIDA}')
    return 0


if __name__ == '__main__':
    sys.exit(main())
