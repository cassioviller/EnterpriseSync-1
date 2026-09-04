"""Fase 8 / Task 3 — um semeador só: os dois concorrentes ficam EM APOSENTADORIA.

Hoje existem QUATRO lugares que instanciam `PlanoContas`: o semeador canônico
`contabilidade_utils.seed_plano_contas_if_needed` (SQL puro — não aparece no
guarda por `ast` abaixo porque não chama o construtor do modelo) e mais três
concorrentes:

- `contabilidade_views.py:93` chamava `contabilidade_utils.criar_plano_contas_padrao`
- `financeiro_views.py:1320` chamava `financeiro_seeds.criar_plano_contas_padrao`
- `scripts/seed_demo_alfa.py` — seed da Construtora Alfa (demo), que roda no
  boot (📖 app.py:618) e não é andaime, é código vivo.

Para o mesmo código `5.1.01`, o primeiro semeador a rodar decidia o
significado da conta naquele tenant, e os outros eram descartados em
silêncio. Esta task faz `seed_plano_contas_if_needed` o único chamador vivo
nos dois pontos de entrada HTTP, e marca as duas `criar_plano_contas_padrao`
como `EM APOSENTADORIA` — sem apagar (conta nunca é apagada; função
aposentada nunca é apagada).
"""
import ast
import os
import pathlib
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pytest

import main  # noqa: F401 — registra os blueprints
from app import app, db
from helpers_tenant import cliente_de, um_tenant

pytestmark = pytest.mark.integration


@pytest.fixture(autouse=True)
def _config():
    app.config['TESTING'] = True
    app.config['WTF_CSRF_ENABLED'] = False
    if not app.secret_key:
        app.secret_key = 'test-fase8-semeador-unico'
    yield


# Os QUATRO lugares que instanciam PlanoContas hoje: o semeador canônico usa
# SQL puro, então sobram a dupla em aposentadoria e o seed de DEMONSTRAÇÃO.
#
# 🔴 CORREÇÃO DE 04/09 (pré-voo da Task 12): a versão de 24/08 listava só os
# dois primeiros, e 🔬 o scan devolve QUATRO. O teste reprovava acusando de
# "criador NOVO" código que já estava na árvore desde antes do plano — falso
# positivo no RED, o defeito que esta casa persegue. `scripts/` NÃO está na
# lista de diretórios ignorados abaixo, e não deve estar: seed de demo que
# roda no boot (📖 app.py:618) é código vivo, não andaime.
_CRIADORES_CONHECIDOS = {
    ('financeiro_seeds.py', 'criar_plano_contas_padrao'),
    ('contabilidade_utils.py', 'criar_plano_contas_padrao'),
    # scripts/seed_demo_alfa.py — seed da Construtora Alfa (demo), 12 contas
    # com as raízes INVERTIDAS (3 = receita, 4 = despesa). É o 4º plano
    # concorrente. Ele não é alvo desta fase (não cria 5.x, logo o de-para é
    # no-op nele), mas está aqui para o guarda não mentir.
    ('seed_demo_alfa.py', '_seed'),
    ('seed_demo_alfa.py', '_upsert_conta'),
}


def test_nenhum_criador_novo_de_plano_contas():
    raiz = pathlib.Path(__file__).resolve().parent.parent
    achados = set()
    for py in raiz.rglob('*.py'):
        partes = set(py.relative_to(raiz).parts)
        # 🔬 04/09 (RED desta task): `.cache` é o cache de pacotes do `uv`
        # (gitignorado, 3,6 GB, 12 763 arquivos .py de bibliotecas de
        # terceiros — nenhum deles é código do projeto) e não estava na
        # lista do brief. Sem excluí-lo o `.read_text(encoding='utf-8')`
        # explode com `UnicodeDecodeError` num fixture de teste do `joblib`
        # (`.cache/uv/archive-v0/.../test_func_inspect_special_encoding.py`,
        # que testa deliberadamente um arquivo big5) antes mesmo do scan
        # terminar — não é o "criador novo" que o guarda procura, é uma
        # pasta de cache que não deveria ter sido varrida.
        if partes & {'archive', 'tests', '__pycache__', '.pythonlibs',
                     'backups', '.cache'}:
            continue
        try:
            arvore = ast.parse(py.read_text(encoding='utf-8'))
        except SyntaxError:
            continue
        for no in ast.walk(arvore):
            if isinstance(no, ast.FunctionDef):
                for interno in ast.walk(no):
                    if (isinstance(interno, ast.Call)
                            and isinstance(interno.func, ast.Name)
                            and interno.func.id == 'PlanoContas'):
                        achados.add((py.name, no.name))
    assert achados <= _CRIADORES_CONHECIDOS, (
        'criador NOVO de PlanoContas: '
        f'{sorted(achados - _CRIADORES_CONHECIDOS)}. Para cada código, o '
        'primeiro semeador a rodar decide o significado e os outros são '
        'descartados em silêncio — é o defeito que a Fase 8 fecha.')


def test_dois_caminhos_de_semeadura_dao_o_mesmo_plano():
    from models import PlanoContas

    with app.app_context():
        a = um_tenant('f8sa')
        b = um_tenant('f8sb')
        admin_a, admin_b = a.admin_id, b.admin_id

    # caminho 1: a tela de contabilidade (GET, semeia se não existir)
    cliente_de(admin_a).get('/contabilidade/plano-contas')
    # caminho 2: o botão do financeiro (POST, sempre tenta semear)
    cliente_de(admin_b).post('/financeiro/plano-contas/inicializar')

    with app.app_context():
        plano_a = {x.codigo: x.nome for x in
                   PlanoContas.query.filter_by(admin_id=admin_a).all()}
        plano_b = {x.codigo: x.nome for x in
                   PlanoContas.query.filter_by(admin_id=admin_b).all()}
        assert plano_a and plano_a == plano_b, (
            'dois tenants receberam planos diferentes por terem clicado em '
            f'telas diferentes — só em A: {sorted(set(plano_a) - set(plano_b))}, '
            f'só em B: {sorted(set(plano_b) - set(plano_a))}')


def test_rota_financeiro_inicializar_nao_quebra_com_o_semeador_canonico():
    """A troca ingênua (Step 3-b do brief): o chamador antigo comparava
    `contas_criadas > 0` contra o retorno de `criar_plano_contas_padrao`
    (int). `seed_plano_contas_if_needed` é `-> None` — se o chamador não for
    corrigido para contar ele mesmo, a comparação `None > 0` levanta
    `TypeError`, e o `except Exception` da rota o engole como flash genérico
    'Erro ao inicializar plano de contas'. Este teste teria de exercitar a
    ROTA para ver isso: chamar `seed_plano_contas_if_needed` direto não
    revelaria nada, porque o erro nasce na comparação do chamador, não na
    função.
    """
    from models import PlanoContas

    with app.app_context():
        t = um_tenant('f8sc')
        admin_id = t.admin_id

    resp = cliente_de(admin_id).post('/financeiro/plano-contas/inicializar',
                                      follow_redirects=True)
    corpo = resp.get_data(as_text=True)

    assert resp.status_code == 200, (
        f'rota devolveu {resp.status_code} — a troca ingênua do chamador '
        'produz 500 (TypeError engolido pelo except genérico)')
    assert 'Erro ao inicializar plano de contas' not in corpo, (
        'flash de erro genérico apareceu — sinal do TypeError engolido pelo '
        'except da rota (ver Step 3-b do brief da Task 3)')

    with app.app_context():
        contas = PlanoContas.query.filter_by(admin_id=admin_id).count()
        assert contas > 0, (
            'a rota respondeu sem erro mas não gravou nenhuma conta — '
            'falta o commit depois do seed (que só faz flush)')
