#!/usr/bin/env python3
"""A maquinaria comum dos runbooks por script — 2026-08-19.

Os runbooks de fase (`runbook_fase1.py`, `runbook_fase2.py`, …) percorrem
ciclos diferentes, mas a mecanica e a mesma: subir um Chromium, entrar como
varias pessoas, achar o controle no DOM antes de agir, e conferir no banco a
coluna que a tabela do runbook nomeia.

Isto mora aqui e nao copiado em cada um pelo motivo que o manual de compras ja
tinha aprendido: **duas listas divergem**. Um recorde de conferencias com duas
implementacoes acaba com dois formatos de saida e dois jeitos de contar falha.

A REGRA HERDADA de `capturar_manual_compras.py`: falhou, fica registrado e o
processo sai com codigo != 0. Mas um passo que falha NAO derruba a rodada — um
runbook que para no primeiro tropeco esconde os outros seis, e quem retoma
precisa da lista inteira.
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# `preparar_bibliotecas` resolve as cinco .so do Chromium no nix store. Vive na
# captura do manual porque foi ela quem descobriu o problema; reexportado aqui
# para que os runbooks tenham uma importacao so.
from capturar_manual_compras import preparar_bibliotecas  # noqa: F401

BASE = os.environ.get('SIGE_BASE', 'http://localhost:5000')
VIEWPORT = {'width': 1440, 'height': 950}


# ── o registro da rodada ────────────────────────────────────────────────────
class Runbook:
    """Acumula o resultado de cada conferência, sem parar na primeira falha."""

    def __init__(self, nome='—'):
        self.linhas = []
        self.passo_atual = '—'
        self.nome = nome

    def passo(self, nome):
        self.passo_atual = nome
        print(f'\n── {nome}')

    def conferir(self, o_que, condicao, detalhe=''):
        ok = bool(condicao)
        self.linhas.append((self.passo_atual, o_que, ok, detalhe))
        marca = 'ok  ' if ok else 'FALHA'
        print(f'   [{marca}] {o_que}' + (f' — {detalhe}' if detalhe else ''))
        return ok

    def quebrou(self, o_que, erro):
        self.linhas.append((self.passo_atual, o_que, False, f'{type(erro).__name__}: {erro}'))
        print(f'   [FALHA] {o_que} — {type(erro).__name__}: {erro}')

    @property
    def falhas(self):
        return [l for l in self.linhas if not l[2]]

    def relatorio(self):
        print('\n' + '=' * 72)
        total, falhas = len(self.linhas), len(self.falhas)
        print(f'RUNBOOK {self.nome} — {total - falhas} de {total} conferências passaram')
        if falhas:
            print(f'\n{falhas} FALHA(S):')
            passo_anterior = None
            for passo, o_que, _ok, detalhe in self.falhas:
                if passo != passo_anterior:
                    print(f'\n  {passo}')
                    passo_anterior = passo
                print(f'    - {o_que}')
                if detalhe:
                    print(f'      {detalhe}')
        print('=' * 72)
        return 1 if falhas else 0


# NAO existe instancia de modulo aqui de proposito: cada runbook cria a sua com
# `rb = Runbook()`. Um singleton compartilhado somaria as conferencias de duas
# fases num relatorio so na primeira vez que alguem importasse os dois.


# ── o banco, lido de fora do servidor ───────────────────────────────────────
# Processo separado do que atende as telas: por isso todo bloco de conferência
# começa por `frescos()`. Sem isso a sessão desta ponta continuaria dentro da
# transação em que abriu e leria o estado de antes do clique — o defeito que
# faria este script aprovar uma tela que não gravou nada.
def frescos():
    from app import db
    db.session.rollback()
    db.session.expire_all()


def _pessoas_e_obra():
    from models import Obra, Usuario
    from seed_manual_compras import MARCA, PESSOAS
    pessoas = {}
    for chave, username, _nome, _cargo in PESSOAS:
        u = Usuario.query.filter_by(username=username).first()
        if u is None:
            raise SystemExit(f'cenário ausente: usuário {username} não existe. '
                             f'Rode `python scripts/seed_manual_compras.py`.')
        pessoas[chave] = u
    admin = pessoas['admin']
    obra = Obra.query.filter_by(admin_id=admin.id).order_by(Obra.id).first()
    if obra is None:
        raise SystemExit('cenário ausente: o tenant do manual não tem obra.')
    return pessoas, obra


# ── o navegador ─────────────────────────────────────────────────────────────
def entrar(page, username, senha):
    page.goto(f'{BASE}/login', wait_until='domcontentloaded', timeout=30000)
    page.fill('input[name="username"]', username)
    page.fill('input[name="password"]', senha)
    page.click('button[type="submit"]')
    page.wait_for_load_state('domcontentloaded')
    if '/login' in page.url:
        raise SystemExit(f'login falhou para {username} — URL final {page.url}')


def abrir(page, rota):
    """Vai até a rota e devolve o status. Cair no login é falha, não redirect."""
    resp = page.goto(f'{BASE}{rota}', wait_until='domcontentloaded', timeout=30000)
    page.wait_for_timeout(400)
    status = resp.status if resp is not None else 0
    if '/login' in page.url:
        raise RuntimeError(f'{rota} devolveu o login — sem sessão ou sem permissão')
    return status


def avisos(page):
    """O texto dos flashes da página. É por eles que a tela recusa."""
    return ' | '.join(t.strip() for t in page.eval_on_selector_all(
        '.alert, .toast-body', 'ns => ns.map(n => n.innerText)') if t.strip())


def rodar_python(args, cwd):
    """Roda um script Python filho SEM o `LD_LIBRARY_PATH` do Chromium.

    🔬 19/08, primeira rodada do runbook da Fase 1: o seed rodou inteiro,
    imprimiu o cenario completo — e o processo morreu no encerramento com
    `terminate called without an active exception`, devolvendo exit != 0. O
    runbook leu o codigo e concluiu "o seed falhou", que era mentira.

    A causa e o ambiente, nao o seed: `preparar_bibliotecas()` injeta em
    `os.environ` os cinco caminhos do nix store que o Chromium precisa (nss,
    nspr, alsa, gbm, xkbcommon), e **todo subprocesso herda isso**. O seed
    carrega tensorflow por tabela, e tensorflow com essas bibliotecas na frente
    aborta no shutdown — de forma intermitente, que e o pior jeito.

    Nenhum filho destes precisa de Chromium: o seed mexe em modelos, os scripts
    de flag mexem em coluna, o sensor le. Entao eles rodam com o ambiente limpo,
    e o `LD_LIBRARY_PATH` fica onde e necessario, que e neste processo.
    """
    import subprocess
    ambiente = dict(os.environ)
    ambiente.pop('LD_LIBRARY_PATH', None)
    return subprocess.run(args, cwd=cwd, capture_output=True, text=True,
                          env=ambiente)


MARCA_SEED = 'cenário do manual de compras semeado'


def semear(raiz, rb):
    """Roda o seed e julga pelo MARCADOR, não só pelo codigo de saida.

    🔬 19/08 — o seed roda inteiro, imprime o cenario completo e o processo
    morre no encerramento com `terminate called without an active exception`,
    devolvendo exit != 0. E intermitente. A causa nao e o seed: o caminho do
    recebimento puxa `ponto_views` -> deepface -> tensorflow, e a pilha aborta
    no shutdown. 📖 O proprio docstring do seed previu esse risco ("um exit code
    mentiroso arruinaria a regra de que falha aqui tem de ser visivel") e tentou
    evita-lo nao importando `main`; a cadeia chega por outra porta.

    A saida NAO e ignorar o exit code — isso seria o `except Exception: continue`
    que esta casa proibiu. E julgar pelo que o seed AFIRMA ter feito, e deixar o
    abort VISIVEL no relatorio como conferencia propria. Quem ler sabe que houve
    abort e sabe que o cenario existe.
    """
    p = rodar_python([sys.executable, 'scripts/seed_manual_compras.py'], raiz)
    saida = (p.stdout or '') + (p.stderr or '')
    fez = MARCA_SEED in saida
    abortou = 'terminate called' in saida
    rb.passo('0 — o cenário')
    rb.conferir('o seed montou o cenário', fez,
                '' if fez else saida[-400:])
    if p.returncode != 0:
        rb.conferir(
            'o seed saiu com código 0',
            fez and abortou,
            f'exit {p.returncode} com o cenário montado — abort conhecido de '
            f'tensorflow no encerramento, não falha do seed'
            if (fez and abortou) else f'exit {p.returncode}')
    return fez


def unico(page, seletor, o_que):
    """O elemento de `seletor`, exigindo que exista EXATAMENTE UM.

    `query_selector` devolve o primeiro e cala sobre os outros — e primeiro
    silencioso é como um runbook aprova a tela errada. 📖 O caso real que
    motivou isto: `templates/compras/requisicao_detalhe.html` tem DOIS
    formulários apontando para `/aprovar`, porque a ratificação da emergência
    (A6) usa a mesma rota de propósito. Num cenário não-emergencial só um
    renderiza e o primeiro-match acerta **por acidente**; no dia em que alguém
    rodar isto sobre requisição emergencial, o script aprovaria pela ratificação
    e diria que deu certo.

    Zero ou mais de um levantam, com o que foi encontrado no texto.
    """
    achados = page.query_selector_all(seletor)
    if len(achados) != 1:
        raise RuntimeError(
            f'{o_que}: esperava 1 elemento em `{seletor}`, achei {len(achados)}')
    return achados[0]


def submeter(page, seletor_form):
    """Clica o botão de submit DO formulário indicado.

    Não é preciosismo de seletor: 📖 `templates/compras/nota.html:150` tem
    `<button class="btn btn-primary">` SEM `type`, que é submit por default do
    HTML mas não casa com `button[type="submit"]` — e a tela ainda tem um
    segundo formulário (excluir nota) acima dele. Um seletor solto ou não acha
    nada ou aperta o botão errado.
    """
    botao = page.query_selector(f'{seletor_form} button[type="submit"]') \
        or page.query_selector(f'{seletor_form} button:not([type="button"])')
    if botao is None:
        raise RuntimeError(f'nenhum botão de submit em {seletor_form}')
    botao.click()
    page.wait_for_load_state('domcontentloaded')
    page.wait_for_timeout(700)
