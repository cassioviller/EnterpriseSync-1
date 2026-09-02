"""B6.6 — lote c: `frota_views.py`, as rotas onde o 404 NÃO está escrito.

**Estado medido em 31/08: a Task B6.6 nunca foi executada.** O plano
`docs/superpowers/plans/2026-08-06-rodada-b6-varredura.md:668-678` manda trocar
os 10 ramos `if not` por `abort(404)` e acrescentar `except HTTPException:
raise` nos excepts largos do arquivo. 🔬 `grep -c 'except HTTPException'
frota_views.py` = **0**, e o comportamento confirma: recurso de outro tenant e
recurso inexistente respondem o MESMO 302 para `/frota/`.

**Por que isto não é um vazamento, e ainda assim é dívida.** As duas respostas
são idênticas, então não há oráculo de enumeração — o que o plano já previa
("o corpo idêntico já está garantido de fábrica"). O que se perde é a semântica:
um GET a recurso que não existe responde "sucesso, vá para a lista", e quem
consome a rota por fetch/JS não tem como distinguir. É a família A da B6.

**A forma destes testes.** Cada rota tem DOIS testes:

1. um **verde de precondição** — o DONO recebe 200. Sem ele, um `xfail` que
   falhasse por erro de andaime (id errado, sessão não montada, modelo com
   NOT NULL esquecido) contaria como "defeito confirmado" sem nunca ter
   chegado à guarda. `xfail(strict=True)` não distingue os dois motivos: essa
   é a versão espelhada do teste que nasce verde, e o par de testes é o que a
   desarma.
2. um **`xfail(strict=True)`** — o estranho deveria receber 404. Quando a B6.6
   for executada, ele falha por passar, e a marca sai junto com o fix.
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
        app.secret_key = 'test-b6-404-frota'
    yield


def _veiculo(admin_id):
    """O veículo que a rota enxerga.

    ⚠️ `models.FrotaVeiculo` é um ALIAS de `Vehicle` (tabela `frota_veiculo`), e
    **não é o modelo desta view**: `frota_views.py:3` faz
    `from models import Veiculo as FrotaVeiculo` — tabela `veiculo`, outra
    classe, mesmo apelido. Semear pelo alias de `models` cria a linha na tabela
    errada e a rota responde 302 "não encontrado" para o próprio dono.
    🔬 Foi o teste de precondição deste arquivo que pegou isso.
    """
    from models import Veiculo

    v = Veiculo(admin_id=admin_id, placa=f'B6{uuid.uuid4().hex[:5].upper()}',
                marca='Ford', modelo='Ranger', ano=2020, tipo='CAMINHONETE',
                ativo=True)
    db.session.add(v)
    db.session.commit()
    return v


def test_o_dono_ve_o_veiculo_precondicao():
    """Precondição de todos os `xfail` deste arquivo: a rota FUNCIONA.

    Sem esta afirmação, um `xfail` que estourasse no andaime — placa duplicada,
    sessão não montada, blueprint não registrado — seria contabilizado como
    "o defeito continua lá", que é uma mentira confortável.
    """
    with app.app_context():
        a, _b = dois_tenants('b6frota_pre', com_fatos=False)
        veiculo = _veiculo(a.admin_id)

        resposta = cliente_de(a.admin_id).get(f'/frota/{veiculo.id}')

        assert resposta.status_code == 200, (
            f'o dono do veículo recebeu {resposta.status_code} na própria '
            f'frota — o andaime deste arquivo está quebrado, e os xfail abaixo '
            f'não provam nada')


@pytest.mark.xfail(strict=True, reason='B6.6 nunca executada (medido em 31/08) '
                   '— frota_views.py:214 responde flash + 302 onde o plano '
                   'manda abort(404)')
def test_veiculo_de_outro_tenant_da_404_e_nao_302():
    """`GET /frota/<id>` — `frota_views.py:214`.

    🔬 Medido em 31/08: 302 para `/frota/`, o mesmo que a rota devolve para um
    id inexistente.
    """
    with app.app_context():
        a, b = dois_tenants('b6frota_ver', com_fatos=False)
        veiculo = _veiculo(a.admin_id)

        resposta = cliente_de(b.admin_id).get(f'/frota/{veiculo.id}')

        assert resposta.status_code == 404, (
            f'veículo de outro tenant respondeu {resposta.status_code} '
            f'(Location: {resposta.headers.get("Location")})')


@pytest.mark.xfail(strict=True, reason='B6.6 nunca executada (medido em 31/08) '
                   '— frota_views.py:214, id inexistente também vira 302')
def test_veiculo_inexistente_da_404_e_nao_302():
    """O outro lado da mesma rota: id que não existe em tenant nenhum.

    Vale por si: um GET a recurso inexistente responder 302 "vá para a lista"
    é o que impede qualquer consumidor de distinguir ausência de sucesso.
    """
    with app.app_context():
        a, _b = dois_tenants('b6frota_inex', com_fatos=False)

        resposta = cliente_de(a.admin_id).get(f'/frota/{INEXISTENTE}')

        assert resposta.status_code == 404, (
            f'id inexistente respondeu {resposta.status_code}')


@pytest.mark.xfail(strict=True, reason='B6.6 nunca executada (medido em 31/08) '
                   '— frota_views.py:314 (editar) responde flash + 302')
def test_editar_veiculo_de_outro_tenant_da_404():
    """`GET /frota/<id>/editar` — `frota_views.py:314`."""
    with app.app_context():
        a, b = dois_tenants('b6frota_edit', com_fatos=False)
        veiculo = _veiculo(a.admin_id)

        resposta = cliente_de(b.admin_id).get(f'/frota/{veiculo.id}/editar')

        assert resposta.status_code == 404, (
            f'edição de veículo alheio respondeu {resposta.status_code}')


@pytest.mark.xfail(strict=True, reason='B6.6 nunca executada (medido em 31/08) '
                   '— frota_views.py:395 (reativar, POST) responde flash + 302')
def test_reativar_veiculo_de_outro_tenant_da_404():
    """`POST /frota/<id>/reativar` — `frota_views.py:395`.

    O caso que mais importa do lote: é POST, muda estado, e hoje um tenant que
    aponte para o id de outro recebe a mesma resposta de sucesso aparente.
    """
    with app.app_context():
        a, b = dois_tenants('b6frota_reat', com_fatos=False)
        veiculo = _veiculo(a.admin_id)

        resposta = cliente_de(b.admin_id).post(f'/frota/{veiculo.id}/reativar')

        assert resposta.status_code == 404, (
            f'reativação de veículo alheio respondeu {resposta.status_code}')
