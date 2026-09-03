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
from models import (RDO, RDOMaoObra, RDOServicoSubatividade,  # noqa: E402
                    SubatividadeMestre)

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
