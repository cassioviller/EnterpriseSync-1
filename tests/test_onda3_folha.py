"""Onda 3 — a folha para de dobrar quando é reprocessada.

O arreio de tenant é `tests/helpers_tenant.py`. Task 8 fecha a automação A12:
`reprocessar` apagava só `FolhaPagamento` — o `GestaoCustoPai`/`Filho` e o
`LancamentoContabil` da rodada anterior sobreviviam e eram recriados, e a
folha dobrava no contas a pagar e no razão.
"""
import calendar
import os
import sys
from datetime import date

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import main  # noqa: F401 — registra blueprints e handlers de evento
from app import app, db
from helpers_tenant import cliente_de, um_tenant  # noqa: F401

pytestmark = pytest.mark.integration

ANO_REF = 2026
MES_REF = 6  # bate com o data_ref default de `um_tenant` (2026-06-15) — é o
             # mês em que o RegistroPonto semeado por `com_fatos=True` existe.


@pytest.fixture(autouse=True)
def _config():
    app.config['TESTING'] = True
    app.config['WTF_CSRF_ENABLED'] = False
    if not app.secret_key:
        app.secret_key = 'test-onda3-folha'
    yield


def _seed_ponto_mes_completo(admin_id, funcionario_id, obra_id):
    """`um_tenant(com_fatos=True)` só semeia UM RegistroPonto (2026-06-15).

    A lógica legada de `calcular_horas_mes` (sem `HorarioTrabalho`) conta
    falta em todo dia útil sem ponto — com um único dia batido, os ~21 dias
    úteis restantes viram falta e o líquido fica NEGATIVO
    (`salario_liq > 0` nunca é satisfeito em `folha_pagamento_views.py`, e
    nem GestaoCustoPai/Filho nem o lançamento contábil chegam a nascer).
    Bater o ponto em todo dia útil do mês é o que dá líquido positivo, para
    o teste exercitar de fato o caminho que A12 quebra."""
    from models import RegistroPonto
    ultimo_dia = calendar.monthrange(ANO_REF, MES_REF)[1]
    for dia in range(1, ultimo_dia + 1):
        data = date(ANO_REF, MES_REF, dia)
        if data.weekday() >= 5:  # sábado/domingo
            continue
        db.session.add(RegistroPonto(
            funcionario_id=funcionario_id, obra_id=obra_id, admin_id=admin_id,
            data=data, horas_trabalhadas=8.0, horas_extras=0.0))
    db.session.commit()


def _seed_parametros_legais(admin_id):
    """A folha só processa com ParametrosLegais do ano cadastrado
    (`services/folha_service.py:_obter_parametros_legais`); sem isso
    `processar_folha_funcionario` levanta e o funcionário vira erro, e nem
    FolhaPagamento nem GestaoCusto nascem — o teste ficaria verde por vazio,
    não por a duplicação estar corrigida."""
    from models import ParametrosLegais
    params = ParametrosLegais(admin_id=admin_id, ano_vigencia=ANO_REF, ativo=True)
    db.session.add(params)
    db.session.commit()


# ---------------------------------------------------------------------------
# Task 8 — reprocessar a folha para de dobrá-la (automação A12)
# ---------------------------------------------------------------------------

def test_reprocessar_folha_nao_dobra_contas_a_pagar_nem_o_razao():
    """🔴 A12 — `folha_pagamento_views.py:148` apagava só `FolhaPagamento`.

    O GestaoCustoPai/Filho e o lançamento contábil da rodada anterior
    sobreviviam e eram recriados: a folha dobrava no contas a pagar
    (GestaoCustoFilho) e no razão (LancamentoContabil).
    """
    from models import FolhaPagamento, GestaoCustoFilho, LancamentoContabil

    with app.app_context():
        t = um_tenant('onda3_folha')
        admin_id = t.admin_id
        _seed_parametros_legais(admin_id)
        _seed_ponto_mes_completo(admin_id, t.funcionario_id, t.obra_id)

    cliente = cliente_de(admin_id)

    resp1 = cliente.post(f'/folha/processar/{ANO_REF}/{MES_REF}',
                          data={'reprocessar': 'false'}, follow_redirects=True)
    assert resp1.status_code == 200

    with app.app_context():
        folhas_1 = FolhaPagamento.query.filter_by(admin_id=admin_id).count()
        filhos_1 = GestaoCustoFilho.query.filter_by(admin_id=admin_id).count()
        lcs_1 = LancamentoContabil.query.filter_by(admin_id=admin_id).count()
        assert folhas_1 > 0, 'pré-condição: a primeira rodada precisa ter processado algo'
        assert filhos_1 > 0, 'pré-condição: a primeira rodada precisa ter gerado GestaoCusto'
        assert lcs_1 > 0, 'pré-condição: a primeira rodada precisa ter gerado LancamentoContabil'

    resp2 = cliente.post(f'/folha/processar/{ANO_REF}/{MES_REF}',
                          data={'reprocessar': 'true'}, follow_redirects=True)
    assert resp2.status_code == 200

    with app.app_context():
        folhas_2 = FolhaPagamento.query.filter_by(admin_id=admin_id).count()
        filhos_2 = GestaoCustoFilho.query.filter_by(admin_id=admin_id).count()
        lcs_2 = LancamentoContabil.query.filter_by(admin_id=admin_id).count()

    assert folhas_2 == folhas_1, (
        f'FolhaPagamento dobrou ao reprocessar: {folhas_1} → {folhas_2}')
    assert filhos_2 == filhos_1, (
        f'GestaoCustoFilho (contas a pagar) dobrou ao reprocessar: {filhos_1} → {filhos_2}')
    assert lcs_2 == lcs_1, (
        f'LancamentoContabil (razão) dobrou ao reprocessar: {lcs_1} → {lcs_2}')


def test_estorno_preserva_pai_compartilhado_com_outra_origem():
    """🔴 `GestaoCustoPai` é rotineiramente compartilhado entre origens —
    `utils/financeiro_integration.py:118-140` reaproveita o pai em aberto
    pela chave (admin_id, categoria, entidade_id), sem olhar
    `origem_tabela`. Se `estornar_folha_do_mes` apagar o pai só porque ele
    tinha UM filho de folha, filhos de outras origens penduradas no MESMO
    pai (`GestaoCustoPai.itens` é `cascade='all, delete-orphan'`) somem
    junto — a mesma classe de bug que a Task 4 já matou em
    `reembolso_views.py`.
    """
    from decimal import Decimal
    from models import GestaoCustoFilho, GestaoCustoPai
    from services.folha_service import estornar_folha_do_mes

    with app.app_context():
        t = um_tenant('onda3_folha_pai')
        admin_id = t.admin_id
        _seed_parametros_legais(admin_id)
        _seed_ponto_mes_completo(admin_id, t.funcionario_id, t.obra_id)

    cliente = cliente_de(admin_id)
    resp = cliente.post(f'/folha/processar/{ANO_REF}/{MES_REF}',
                         data={'reprocessar': 'false'}, follow_redirects=True)
    assert resp.status_code == 200

    with app.app_context():
        filho_folha = GestaoCustoFilho.query.filter_by(
            admin_id=admin_id, origem_tabela='folha_pagamento').first()
        assert filho_folha is not None, (
            'pré-condição: a folha precisa ter gerado o filho de origem folha')
        pai_id = filho_folha.pai_id

        # Um filho de OUTRA origem, no MESMO pai — é exatamente o que
        # `financeiro_integration.reaproveita_pai_em_aberto` produz.
        valor_outra_origem = Decimal('123.45')
        filho_rdo = GestaoCustoFilho(
            pai_id=pai_id, admin_id=admin_id,
            data_referencia=date(ANO_REF, MES_REF, 1),
            descricao='Diária RDO — não é folha',
            valor=valor_outra_origem,
            obra_id=t.obra_id,
            origem_tabela='rdo_mao_obra',
            origem_id=999999,
        )
        db.session.add(filho_rdo)
        db.session.commit()
        filho_rdo_id = filho_rdo.id

        estornar_folha_do_mes(admin_id=admin_id,
                               mes_referencia=date(ANO_REF, MES_REF, 1))
        db.session.commit()

    with app.app_context():
        # O filho de folha foi embora.
        assert GestaoCustoFilho.query.filter_by(
            admin_id=admin_id, origem_tabela='folha_pagamento').count() == 0

        # O filho de outra origem, e o pai que os agrupava, sobrevivem.
        filho_rdo_depois = GestaoCustoFilho.query.get(filho_rdo_id)
        assert filho_rdo_depois is not None, (
            'estorno da folha apagou filho de OUTRA origem no mesmo pai')

        pai_depois = GestaoCustoPai.query.get(pai_id)
        assert pai_depois is not None, (
            'estorno da folha apagou o pai compartilhado com outra origem')

        # E o total do pai foi recalculado — sobrou só o filho do RDO.
        assert pai_depois.valor_total == valor_outra_origem, (
            f'GestaoCustoPai.valor_total não foi recalculado: '
            f'{pai_depois.valor_total} != {valor_outra_origem}')
