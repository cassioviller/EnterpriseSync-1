"""Função pura FinanceiroService.agregar_fluxo_mensal (Passo 2 do redesenho do
Fluxo de Caixa — spec 2026-06-11). Agrega a lista plana de `detalhes` em série
mensal + KPIs, separando Realizado de Previsto e acumulando a variação de caixa a
partir de ZERO (ver ADR 0003). Testes unitários puros: sem banco, sem app_context.
"""
from datetime import date

from financeiro_service import FinanceiroService

agregar = FinanceiroService.agregar_fluxo_mensal


def _mov(data, tipo, valor, realizado):
    return {"data": data, "tipo": tipo, "valor": valor, "realizado": realizado,
            "descricao": "x", "origem": "y", "status": "z"}


def test_um_mes_realizado_soma_entradas_saidas_e_variacao():
    """Um mês com 1 entrada + 1 saída realizadas: totais do mês e variação
    acumulada (que parte de 0) corretos."""
    detalhes = [
        _mov(date(2026, 1, 10), "ENTRADA", 100.0, True),
        _mov(date(2026, 1, 20), "SAIDA", 30.0, True),
    ]
    out = agregar(detalhes, saldo_inicial=0.0)

    assert len(out["meses"]) == 1
    m = out["meses"][0]
    assert m["mes"] == "2026-01"
    assert m["label"] == "Jan/26"
    assert m["entradas_real"] == 100.0
    assert m["saidas_real"] == 30.0
    assert m["saldo_mes_real"] == 70.0
    assert m["variacao_acumulada"] == 70.0   # parte de 0


def test_dois_meses_variacao_acumula_de_zero():
    """Meses ordenados; variação acumulada do 2º = soma dos saldos mensais."""
    detalhes = [
        _mov(date(2026, 2, 5), "SAIDA", 50.0, True),     # fora de ordem de propósito
        _mov(date(2026, 1, 10), "ENTRADA", 100.0, True),
        _mov(date(2026, 1, 20), "SAIDA", 30.0, True),
    ]
    out = agregar(detalhes, saldo_inicial=0.0)

    assert [m["mes"] for m in out["meses"]] == ["2026-01", "2026-02"]
    assert out["meses"][0]["variacao_acumulada"] == 70.0    # jan: +70
    assert out["meses"][1]["saldo_mes_real"] == -50.0
    assert out["meses"][1]["variacao_acumulada"] == 20.0    # 70 + (-50)


def test_separa_realizado_de_previsto_e_kpis():
    """Itens realizado=False entram em previsto_liquido (não em *_real); KPIs somam
    realizado e previsto separadamente; saldo_banco = saldo_inicial."""
    detalhes = [
        _mov(date(2026, 1, 10), "ENTRADA", 100.0, True),    # realizado
        _mov(date(2026, 1, 15), "ENTRADA", 40.0, False),    # previsto a receber
        _mov(date(2026, 1, 20), "SAIDA", 30.0, True),       # realizado
        _mov(date(2026, 1, 25), "SAIDA", 10.0, False),      # previsto a pagar
    ]
    out = agregar(detalhes, saldo_inicial=500.0)

    m = out["meses"][0]
    assert m["entradas_real"] == 100.0
    assert m["saidas_real"] == 30.0
    assert m["previsto_liquido"] == 30.0     # 40 a receber - 10 a pagar

    k = out["kpis"]
    assert k["saldo_banco"] == 500.0
    assert k["realizado_liquido"] == 70.0    # 100 - 30
    assert k["previsto_liquido"] == 30.0


def test_serie_chart_barras_e_duas_linhas():
    """serie_chart traz barras realizadas + linha de variação realizada (de 0) e
    projetada (realizada + previsto acumulado)."""
    detalhes = [
        _mov(date(2026, 1, 10), "ENTRADA", 100.0, True),
        _mov(date(2026, 1, 20), "SAIDA", 30.0, True),
        _mov(date(2026, 1, 25), "SAIDA", 10.0, False),    # previsto jan: -10
        _mov(date(2026, 2, 5), "ENTRADA", 50.0, True),
    ]
    s = agregar(detalhes, saldo_inicial=0.0)["serie_chart"]

    assert s["labels"] == ["Jan/26", "Fev/26"]
    assert s["entradas_real"] == [100.0, 50.0]
    assert s["saidas_real"] == [30.0, 0.0]
    assert s["var_acum_real"] == [70.0, 120.0]      # 70 ; 70+50
    assert s["var_acum_proj"] == [60.0, 110.0]      # +previsto acum (-10): 60 ; 110


def test_lista_vazia():
    out = agregar([], saldo_inicial=0.0)
    assert out["meses"] == []
    assert out["kpis"]["realizado_liquido"] == 0.0
    assert out["kpis"]["previsto_liquido"] == 0.0
    assert out["serie_chart"]["labels"] == []


def test_bucket_sem_data():
    """Movimento sem data vai a um bucket 'Sem data' ao fim, sem variação acumulada
    e fora do gráfico, mas conta nos KPIs."""
    detalhes = [
        _mov(date(2026, 1, 10), "ENTRADA", 100.0, True),
        _mov(None, "SAIDA", 25.0, True),    # sem data
    ]
    out = agregar(detalhes, saldo_inicial=0.0)

    assert out["meses"][0]["mes"] == "2026-01"
    sem = out["meses"][-1]
    assert sem["mes"] == "sem-data"
    assert sem["label"] == "Sem data"
    assert sem["variacao_acumulada"] is None
    assert sem["saidas_real"] == 25.0

    # fora do gráfico (só Jan/26 nas labels)
    assert out["serie_chart"]["labels"] == ["Jan/26"]
    # mas entra nos KPIs: 100 - 25
    assert out["kpis"]["realizado_liquido"] == 75.0
