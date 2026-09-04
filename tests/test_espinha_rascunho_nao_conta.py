"""O porte do PR #6 atravessa a Fase 5: em 15/06 não existia RDO.estado, e
os módulos filtravam por RDO.status == 'Finalizado' — que não filtra nada,
porque todo RDO nasce 'Finalizado' (models.py, classe RDO).

Portado como estava, o aprendizado leria RASCUNHO. É o mesmo defeito que o
main fechou em 24/08 do outro lado (95eb585f, "RDO em rascunho para de mover
o percentual"): fechá-lo por cima e reabri-lo por baixo deixaria o
ESTADO-ATUAL.md com duas afirmações contraditórias verdadeiras ao mesmo tempo.

⚠️ Fixture que cria RDO SEM `estado` explícito nasce rascunho e produz falso
vermelho — é a "dívida de fixture" que fez o trabalho de 24/08 parecer que
quebrava dezenas de testes. Aqui todo RDO declara o seu estado.

Desvio declarado em relação ao esboço do plano: `_catalogo_de_teste()` devolve
o `Tenant` inteiro, não só o `admin_id`. O esboço passava `admin_id`, mas criar
o RDO e a linha de mão de obra exige também `obra_id` e `funcionario_id` — e
buscá-los por `admin_id` dentro da fixture seria adivinhação onde o molde já
oferece o objeto.
"""
import os
import sys
from datetime import date
from uuid import uuid4

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app import app, db  # noqa: E402
from helpers_tenant import um_tenant  # noqa: E402
from models import (RDO, RDOCustoDiario, RDOMaoObra,  # noqa: E402
                    RDOServicoSubatividade, SubatividadeMestre,
                    TarefaCronograma)

pytestmark = pytest.mark.integration

DIA = date(2026, 6, 15)


@pytest.fixture(autouse=True)
def _config():
    app.config['TESTING'] = True
    app.config['WTF_CSRF_ENABLED'] = False
    if not app.secret_key:
        app.secret_key = 'test-espinha-rascunho'
    yield


def _catalogo_de_teste():
    """Tenant limpo + uma SubatividadeMestre no catálogo. -> (tenant, sub_mestre_id)"""
    tenant = um_tenant('espinha-prod', data_ref=DIA, com_fatos=False)
    sm = SubatividadeMestre(
        nome=f'Alvenaria de teste {tenant.marca}',
        admin_id=tenant.admin_id,
        tipo='subatividade',
        ativo=True,
        unidade_medida='m²',
        meta_produtividade=10.0,
        duracao_estimada_horas=8.0,
    )
    db.session.add(sm)
    db.session.commit()
    return tenant, sm.id


def _rdo_com_produtividade(tenant, sub_mestre_id, estado, produtividade, horas):
    """Um RDO no `estado` pedido, com uma linha de mão de obra cuja
    produtividade real já está calculada. O `estado` é SEMPRE explícito."""
    rdo = RDO(
        # `numero_rdo` e' varchar(20) e UNIQUE na tabela inteira: o nome tem de
        # ser curto E unico. Montar a marca do tenant mais o estado estoura a
        # coluna (foi o primeiro vermelho deste teste, e era da fixture).
        numero_rdo=f'ESP{uuid4().hex[:12]}',
        data_relatorio=DIA,
        obra_id=tenant.obra_id,
        admin_id=tenant.admin_id,
        estado=estado,
    )
    db.session.add(rdo)
    db.session.flush()

    linha = RDOServicoSubatividade(
        rdo_id=rdo.id,
        nome_subatividade='Alvenaria de teste',
        admin_id=tenant.admin_id,
        subatividade_mestre_id=sub_mestre_id,
        ativo=True,
    )
    db.session.add(linha)
    db.session.flush()

    db.session.add(RDOMaoObra(
        admin_id=tenant.admin_id,
        rdo_id=rdo.id,
        funcionario_id=tenant.funcionario_id,
        funcao_exercida='Pedreiro',
        horas_trabalhadas=horas,
        subatividade_id=linha.id,
        produtividade_real=produtividade,
    ))
    db.session.commit()
    return rdo


def test_rdo_em_rascunho_nao_entra_na_produtividade_observada():
    from services.aprendizado_produtividade import produtividade_observada
    with app.app_context():
        tenant, sub_id = _catalogo_de_teste()
        _rdo_com_produtividade(tenant, sub_id, estado='rascunho',
                               produtividade=99.0, horas=8)
        media, n = produtividade_observada(sub_id, tenant.admin_id)
        assert n == 0 and media is None, (
            'RDO em rascunho é documento que o autor ainda não submeteu — '
            f'entrou assim mesmo no catálogo (n={n}, media={media})')


def test_rdo_preenchido_entra_normalmente():
    from services.aprendizado_produtividade import produtividade_observada
    with app.app_context():
        tenant, sub_id = _catalogo_de_teste()
        _rdo_com_produtividade(tenant, sub_id, estado='preenchido',
                               produtividade=12.0, horas=8)
        media, n = produtividade_observada(sub_id, tenant.admin_id)
        assert n == 1 and float(media) == 12.0


# ── Task 5 — o mesmo defeito, agora no read-model do custo ────────────────────
# O read-model da branch não filtra RDO de forma nenhuma: 🔬 zero ocorrências de
# `status`, `estado` ou `'Finalizado'` nas 537 linhas. `custo_mo_atividade` soma
# `RDOCustoDiario` de todo RDO que encontrar, e esse número alimenta o alarme
# (D5), o CPI e o EAC. Rascunho ali é pior que no catálogo: move dinheiro.


def _tarefa_com_apontamento(tenant, estado, custo_dia, horas=8.0):
    """Uma atividade do cronograma com `horas` apontadas por um funcionário num
    RDO no `estado` pedido, e o custo onerado daquele dia no RDOCustoDiario.

    O `estado` é SEMPRE explícito — RDO sem `estado` nasce 'rascunho'
    (models.py, `default='rascunho'`), e é essa a dívida de fixture que faz
    teste honesto ficar vermelho pelo motivo errado.
    """
    tarefa = TarefaCronograma(
        obra_id=tenant.obra_id, admin_id=tenant.admin_id,
        nome_tarefa=f'Atividade {tenant.marca}', ordem=1, duracao_dias=5,
        quantidade_total=100.0, percentual_concluido=50.0,
    )
    db.session.add(tarefa)
    db.session.flush()

    rdo = RDO(
        numero_rdo=f'ESP{uuid4().hex[:12]}',
        data_relatorio=DIA, obra_id=tenant.obra_id,
        admin_id=tenant.admin_id, estado=estado,
    )
    db.session.add(rdo)
    db.session.flush()

    db.session.add(RDOMaoObra(
        admin_id=tenant.admin_id, rdo_id=rdo.id,
        funcionario_id=tenant.funcionario_id, funcao_exercida='Pedreiro',
        horas_trabalhadas=horas, tarefa_cronograma_id=tarefa.id,
    ))
    db.session.add(RDOCustoDiario(
        rdo_id=rdo.id, funcionario_id=tenant.funcionario_id,
        admin_id=tenant.admin_id, data=DIA,
        tipo_remuneracao_snapshot='salario', custo_total_dia=custo_dia,
        horas_normais=horas,
    ))
    db.session.commit()
    return tarefa


def test_rdo_em_rascunho_nao_entra_no_custo_de_mao_de_obra():
    from services.resultado_atividade_service import custo_mo_atividade
    with app.app_context():
        tenant = um_tenant('espinha-custo', data_ref=DIA, com_fatos=False)
        tarefa = _tarefa_com_apontamento(tenant, estado='rascunho',
                                         custo_dia=1000.0)
        assert float(custo_mo_atividade(tarefa)) == 0.0, (
            'rascunho entrou no custo incorrido — alarme e EAC passam a '
            'reagir a documento não submetido')


def test_rdo_preenchido_entra_no_custo_de_mao_de_obra():
    """A contraprova: sem ela, `return 0` passaria no teste de cima."""
    from services.resultado_atividade_service import custo_mo_atividade
    with app.app_context():
        tenant = um_tenant('espinha-custo-ok', data_ref=DIA, com_fatos=False)
        tarefa = _tarefa_com_apontamento(tenant, estado='preenchido',
                                         custo_dia=1000.0)
        assert float(custo_mo_atividade(tarefa)) == 1000.0
