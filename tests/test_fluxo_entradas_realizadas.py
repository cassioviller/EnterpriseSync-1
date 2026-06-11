"""calcular_fluxo_caixa deve incluir entradas REALIZADAS vindas de contas a receber
baixadas (FluxoCaixa ENTRADA, referencia_tabela='conta_receber') — simétrico às
saídas realizadas de gestão de custo. Passo 2.5 do redesenho (achado na verificação
com dados reais: R$ 1,17M recebidos ficavam invisíveis). Integração read-only.
"""
from datetime import date

import pytest

ADMIN = 1
DI = date(2026, 1, 1)
DF = date(2026, 6, 5)


@pytest.fixture(scope="module")
def app_ctx():
    from main import app
    with app.app_context():
        yield


@pytest.mark.integration
def test_entradas_recebidas_aparecem_como_realizadas(app_ctx):
    from financeiro_service import FinanceiroService
    from models import FluxoCaixa

    fc = FluxoCaixa.query.filter(
        FluxoCaixa.admin_id == ADMIN,
        FluxoCaixa.tipo_movimento == "ENTRADA",
        FluxoCaixa.data_movimento >= DI,
        FluxoCaixa.data_movimento <= DF,
        FluxoCaixa.referencia_tabela == "conta_receber",
    ).all()
    esperado = float(sum(float(f.valor) for f in fc))
    if esperado <= 0:
        pytest.skip("sem entradas recebidas no período — precondição")

    res = FinanceiroService.calcular_fluxo_caixa(ADMIN, DI, DF)
    entradas_real = float(sum(
        d["valor"] for d in res["detalhes"]
        if d["tipo"] == "ENTRADA" and d.get("realizado")
    ))
    assert entradas_real == pytest.approx(esperado, abs=0.01)
