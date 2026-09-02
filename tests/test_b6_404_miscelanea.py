"""B6.5 — lote b: a miscelânea homogênea (ponto, configurações, alimentação).

**Estado medido em 31/08: a Task B6.5 nunca foi executada.** O plano
`docs/superpowers/plans/2026-08-06-rodada-b6-varredura.md:630-645` manda pôr
`except HTTPException: raise` antes dos excepts largos de `ponto_views.py` (5
handlers), `configuracoes_views.py` (5), `alimentacao_views.py` (1),
`views/obras.py` (1) e `views/dashboard.py` (2 trys). 🔬 `grep -c 'except
HTTPException'` nesses arquivos = **0** em todos.

A forma dos testes é a mesma do lote c (`test_b6_404_frota.py`): cada rota tem
um **verde de precondição** — o dono recebe 200 — e um `xfail(strict=True)` com
o RED medido. Sem o par, um `xfail` que estourasse no andaime contaria como
defeito confirmado.
"""
import os
import sys
import uuid

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import main  # noqa: F401 — registra blueprints e handlers de evento
from app import app, db
from helpers_tenant import cliente_de, dois_tenants

pytestmark = pytest.mark.integration

INEXISTENTE = 999_999_999


@pytest.fixture(autouse=True)
def _config():
    app.config['TESTING'] = True
    app.config['WTF_CSRF_ENABLED'] = False
    if not app.secret_key:
        app.secret_key = 'test-b6-404-misc'
    yield


def _funcao(admin_id):
    from models import Funcao

    f = Funcao(admin_id=admin_id, nome=f'Pedreiro {uuid.uuid4().hex[:6]}',
               operacional=True)
    db.session.add(f)
    db.session.commit()
    return f


def _restaurante(admin_id):
    from models import Restaurante

    r = Restaurante(admin_id=admin_id, nome=f'Cantina {uuid.uuid4().hex[:6]}')
    db.session.add(r)
    db.session.commit()
    return r


# ---------------------------------------------------------------------------
# ponto_views.py — `:731` (obra) e `:637` (funcionário)
# ---------------------------------------------------------------------------

def test_o_dono_ve_o_painel_de_ponto_da_obra_precondicao():
    """Precondição dos xfail de `/ponto/obra/<id>`."""
    with app.app_context():
        a, _b = dois_tenants('b6misc_pre_obra', com_fatos=False)

        resposta = cliente_de(a.admin_id).get(f'/ponto/obra/{a.obra_id}')

        assert resposta.status_code == 200, (
            f'o dono da obra recebeu {resposta.status_code} no painel de ponto '
            f'da própria obra — andaime quebrado')


@pytest.mark.xfail(strict=True, reason='B6.5 nunca executada (medido em 31/08) '
                   '— ponto_views.py:731 responde flash + 302 onde deveria 404')
def test_painel_de_ponto_de_obra_de_outro_tenant_da_404():
    """`GET /ponto/obra/<obra_id>` — `ponto_views.py:731`, except `:755`."""
    with app.app_context():
        a, b = dois_tenants('b6misc_ponto_obra', com_fatos=False)

        resposta = cliente_de(b.admin_id).get(f'/ponto/obra/{a.obra_id}')

        assert resposta.status_code == 404, (
            f'obra de outro tenant respondeu {resposta.status_code} '
            f'(Location: {resposta.headers.get("Location")})')


@pytest.mark.xfail(strict=True, reason='B6.5 nunca executada (medido em 31/08) '
                   '— ponto_views.py:637 responde flash + 302 onde deveria 404')
def test_ponto_de_funcionario_de_outro_tenant_da_404():
    """`GET /ponto/funcionario/<funcionario_id>` — `ponto_views.py:637`.

    🔬 Não confundir com
    `tests/test_arreio_presenca_rotas.py:213`, que prova que **lançar** ponto
    para funcionário alheio é RECUSADO (e é). O que falta aqui é o código de
    status da recusa na tela de leitura: hoje é 302, não 404.
    """
    with app.app_context():
        a, b = dois_tenants('b6misc_ponto_func', com_fatos=False)

        resposta = cliente_de(b.admin_id).get(
            f'/ponto/funcionario/{a.funcionario_id}')

        assert resposta.status_code == 404, (
            f'funcionário de outro tenant respondeu {resposta.status_code}')


# ---------------------------------------------------------------------------
# configuracoes_views.py — `:498`
# ---------------------------------------------------------------------------

def test_o_dono_edita_a_propria_funcao_precondicao():
    """Precondição do xfail de `/configuracoes/funcoes/editar/<id>`."""
    with app.app_context():
        a, _b = dois_tenants('b6misc_pre_func', com_fatos=False)
        funcao = _funcao(a.admin_id)

        resposta = cliente_de(a.admin_id).get(
            f'/configuracoes/funcoes/editar/{funcao.id}')

        assert resposta.status_code == 200, (
            f'o dono da função recebeu {resposta.status_code} ao editá-la — '
            f'andaime quebrado')


def test_editar_funcao_de_outro_tenant_da_404():
    """`GET /configuracoes/funcoes/editar/<id>` — `configuracoes_views.py:498`.

    ✅ **Este sítio JÁ está correto, e o censo do b6 o contou errado.** O teste
    nasceu `xfail(strict=True)` como os vizinhos e deu **XPASS** — foi o
    `strict` que denunciou. Olhando a fonte: `:495` faz
    `Funcao.query.filter_by(id=id, admin_id=admin_id).first_or_404()` **antes**
    do `try` (`:497`), então o 404 escapa por construção. O plano
    (`rodada-b6:632`) lista `configuracoes_views.py:498` entre os cinco
    handlers do lote b, mas a unidade que ele mediu foi o handler, não o
    lookup — e neste o lookup está fora do try, que é exatamente a forma que o
    plano manda adotar.

    O teste fica verde, sem marca: é a guarda que já existe, agora congelada.
    """
    with app.app_context():
        a, b = dois_tenants('b6misc_conf', com_fatos=False)
        funcao = _funcao(a.admin_id)

        resposta = cliente_de(b.admin_id).get(
            f'/configuracoes/funcoes/editar/{funcao.id}')

        assert resposta.status_code == 404, (
            f'função de outro tenant respondeu {resposta.status_code}')


# ---------------------------------------------------------------------------
# alimentacao_views.py — `:151`
# ---------------------------------------------------------------------------

@pytest.mark.xfail(strict=True, reason='B6.5 nunca executada (medido em 31/08) '
                   '— alimentacao_views.py:151 responde flash + 302')
def test_deletar_restaurante_de_outro_tenant_da_404():
    """`POST /alimentacao/restaurantes/<id>/deletar` — `alimentacao_views.py:151`.

    POST destrutivo: o que se afirma além do status é que o restaurante do
    tenant A **continua existindo** depois da tentativa de B. Essa segunda
    afirmação vale mesmo enquanto o status for 302 — e por isso ela vem
    primeiro, fora da parte que o `xfail` cobre.
    """
    from models import Restaurante

    with app.app_context():
        a, b = dois_tenants('b6misc_rest', com_fatos=False)
        restaurante = _restaurante(a.admin_id)
        rid = restaurante.id

        resposta = cliente_de(b.admin_id).post(
            f'/alimentacao/restaurantes/{rid}/deletar')

        assert db.session.get(Restaurante, rid) is not None, (
            '🔴 o restaurante do tenant A foi apagado por B — isto é bem pior '
            'que o 404 que falta, e não é o que este arquivo veio medir')
        assert resposta.status_code == 404, (
            f'exclusão de restaurante alheio respondeu {resposta.status_code}')
