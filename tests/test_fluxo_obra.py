"""Filtro de Obra em FinanceiroService.calcular_fluxo_caixa (Passo 1 do redesenho
do Fluxo de Caixa — spec 2026-06-11, decisões Q5/Q6/Q8).

Testes de integração read-only sobre o tenant onde o batch real foi importado
(admin_id=1). Asserções RELACIONAIS: o que o service devolve filtrado por obra deve
bater com uma query direta pela mesma obra. Nada é gravado (só leitura) — robusto a
mudanças de dado porque o esperado é recalculado do banco.
"""
from datetime import date

import pytest

ADMIN = 1
OBRA = 25                       # obra com mais lançamentos no batch importado
DI = date(2026, 1, 1)
DF = date(2026, 6, 5)


@pytest.fixture(scope="module")
def app_ctx():
    from main import app
    with app.app_context():
        yield


@pytest.mark.integration
def test_filtro_obra_restringe_entradas_previstas(app_ctx):
    """Com obra_id, entradas_previstas == soma das ContaReceber pendentes da obra."""
    from financeiro_service import FinanceiroService
    from models import ContaReceber

    contas = ContaReceber.query.filter(
        ContaReceber.admin_id == ADMIN,
        ContaReceber.data_vencimento >= DI,
        ContaReceber.data_vencimento <= DF,
        ContaReceber.status.in_(["PENDENTE", "PARCIAL"]),
        ContaReceber.obra_id == OBRA,
    ).all()
    esperado = float(sum(
        (c.saldo if c.saldo is not None else (c.valor_original or 0)) for c in contas
    ))
    if esperado <= 0:
        pytest.skip(f"sem ContaReceber pendente da obra {OBRA} no período — precondição")

    res = FinanceiroService.calcular_fluxo_caixa(ADMIN, DI, DF, obra_id=OBRA)
    assert res["entradas_previstas"] == pytest.approx(esperado, abs=0.01)


@pytest.mark.integration
def test_filtro_obra_restringe_saidas_realizadas(app_ctx):
    """Com obra_id, as saídas realizadas (FluxoCaixa) batem com a query direta da obra
    e ficam menores que o total sem filtro."""
    from financeiro_service import FinanceiroService
    from models import FluxoCaixa

    # Esperado: FluxoCaixa SAIDA da obra no período, nas origens que o service consome
    # (pagamento de gestão de custo + lançamento direto).
    fc = FluxoCaixa.query.filter(
        FluxoCaixa.admin_id == ADMIN,
        FluxoCaixa.tipo_movimento == "SAIDA",
        FluxoCaixa.data_movimento >= DI,
        FluxoCaixa.data_movimento <= DF,
        FluxoCaixa.obra_id == OBRA,
        FluxoCaixa.referencia_tabela.in_(["gestao_custo_pai", None]),
    ).all()
    esperado = float(sum(float(f.valor) for f in fc))
    if esperado <= 0:
        pytest.skip(f"sem FluxoCaixa SAIDA da obra {OBRA} no período — precondição")

    res_obra = FinanceiroService.calcular_fluxo_caixa(ADMIN, DI, DF, obra_id=OBRA)
    res_geral = FinanceiroService.calcular_fluxo_caixa(ADMIN, DI, DF)

    def saidas_realizadas(res):
        return float(sum(
            d["valor"] for d in res["detalhes"]
            if d["tipo"] == "SAIDA" and d.get("realizado")
        ))

    assert saidas_realizadas(res_obra) == pytest.approx(esperado, abs=0.01)
    assert saidas_realizadas(res_obra) < saidas_realizadas(res_geral)


@pytest.mark.integration
def test_filtro_obra_inexistente_zera_saidas_previstas(app_ctx):
    """Filtrar por uma obra sem nada zera as saídas previstas (GestaoCustoPai via
    filhos — Q8). Usa janela que cobre as previstas; prova que um 'pai' sem filho na
    obra não vaza."""
    from financeiro_service import FinanceiroService

    # Janela que cobre as saídas previstas em aberto (criadas em jun/2026).
    di_prev, df_prev = date(2026, 6, 1), date(2026, 6, 30)
    OBRA_VAZIA = 999_999_999

    geral = FinanceiroService.calcular_fluxo_caixa(ADMIN, di_prev, df_prev)
    if geral["saidas_previstas"] <= 0:
        pytest.skip("sem saídas previstas em aberto no período — precondição")

    res = FinanceiroService.calcular_fluxo_caixa(ADMIN, di_prev, df_prev, obra_id=OBRA_VAZIA)
    assert res["saidas_previstas"] == pytest.approx(0.0, abs=0.01)
    assert res["detalhes"] == []
