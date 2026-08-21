"""Rascunho não lança custo; Submeter lança. (Fase 5 × arreio B0.3 — 21/08)

🔬 21/08, captura do manual visual do RDO: um RDO salvo pelo formulário e NUNCA
submetido ficou com 2 `custo_obra` de mão de obra (R$ 277,12). O salvar emitia
`rdo_finalizado` — o mesmo evento do Submeter — e, como `RDO.status` vale
'Finalizado' para todo RDO, os consumidores que filtram por `status` contavam o
rascunho. Isso contradizia o contrato do ciclo de vida
(`services/rdo_ciclo_vida.py`: "PREENCHIDO = submetido; custos lançados") e o
capítulo 23a do manual ("rascunho não lança custo").

O arreio `tests/test_arreio_custo_rdo_rotas.py` (04/08) tinha o salvar como
REFERÊNCIA de custo porque, naquela data, o ciclo de vida ainda não existia.
Ele foi repontado no mesmo commit: a referência passou a ser o fluxo real —
salvar E submeter.
"""
import os
import sys
from datetime import date

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import main  # noqa: F401
from app import app, db
from helpers_dinheiro import (custo_diario, filhos_mao_de_obra, form_rdo,
                              rdo_da_obra, soma, tarefa_da_obra)
from helpers_tenant import cliente_de, um_tenant
from models import RDO

pytestmark = pytest.mark.integration

DIA = date(2026, 6, 15)


@pytest.fixture(autouse=True)
def _config():
    app.config['TESTING'] = True
    app.config['WTF_CSRF_ENABLED'] = False
    if not app.secret_key:
        app.secret_key = 'test-rascunho-sem-custo'
    yield


def _ok(resp):
    assert resp.status_code in (200, 302), resp.status_code


def _rdo_salvo(tenant, dia):
    """O RDO que a ROTA criou. (`helpers_dinheiro.rdo_da_obra` cria um se não
    achar pelo seu próprio critério — aqui não pode haver criação por fora.)"""
    db.session.expire_all()
    rdo = (RDO.query.filter_by(obra_id=tenant.obra_id, data_relatorio=dia)
           .order_by(RDO.id.desc()).first())
    assert rdo is not None, 'a rota não criou o RDO'
    return rdo


def test_salvar_rascunho_nao_lanca_custo_e_submeter_lanca():
    with app.app_context():
        tenant = um_tenant('rasc', data_ref=DIA, com_fatos=False,
                           tipo_remuneracao='salario', valor_diaria=0.0, salario=3000.0)
        tarefa = tarefa_da_obra(tenant)
        cli = cliente_de(tenant.admin_id)

        form = form_rdo(tenant, DIA, tarefa_id=tarefa.id, horas=8.0)
        form['funcionario_id'] = str(tenant.funcionario_id)
        _ok(cli.post('/salvar-rdo-flexivel', data=form))

        rdo = _rdo_salvo(tenant, DIA)
        assert rdo.estado == 'rascunho'
        assert filhos_mao_de_obra(tenant, DIA) == [], \
            'rascunho lançou custo na gestão de custos'
        assert custo_diario(rdo.id) == [], 'rascunho gravou custo diário por funcionário'

        _ok(cli.post(f'/rdo/{rdo.id}/finalizar'))
        assert _rdo_salvo(tenant, DIA).estado == 'preenchido'
        linhas = filhos_mao_de_obra(tenant, DIA)
        assert len(linhas) == 1 and soma(linhas) > 0, \
            'submeter não lançou o custo que o rascunho segurava'


def test_finalizar_legado_tambem_submete_o_rascunho():
    """`POST /rdo/finalizar/<id>` (crud_rdo_completo) marcava `status` e emitia
    custo sem mexer em `estado`. Agora é um Submeter: transiciona antes de emitir."""
    from helpers_dinheiro import mao_de_obra
    with app.app_context():
        tenant = um_tenant('rascleg', data_ref=DIA, com_fatos=False,
                           tipo_remuneracao='salario', valor_diaria=0.0, salario=3000.0)
        tarefa = tarefa_da_obra(tenant)
        rdo = rdo_da_obra(tenant, DIA)
        mao_de_obra(rdo, tenant, horas=8.0, tarefa=tarefa)
        cli = cliente_de(tenant.admin_id)
        _ok(cli.post(f'/rdo/finalizar/{rdo.id}',
                     data=form_rdo(tenant, DIA, tarefa_id=tarefa.id, horas=8.0)))
        assert _rdo_salvo(tenant, DIA).estado == 'preenchido'
        assert len(filhos_mao_de_obra(tenant, DIA)) == 1
