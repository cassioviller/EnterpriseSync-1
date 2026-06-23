from datetime import date
from decimal import Decimal

from services.cronograma_fisico_financeiro import fasear_por_dias_uteis

D = Decimal


def test_sem_datas_vai_para_nao_faseado():
    out = fasear_por_dias_uteis(D("1000"), None, None, False, False)
    assert out == {"__nao_faseado__": D("1000")}


def test_tarefa_dentro_de_um_mes():
    out = fasear_por_dias_uteis(D("1000"), date(2026, 6, 1), date(2026, 6, 5), False, False)
    assert set(out) == {"2026-06"}
    assert out["2026-06"] == D("1000")


def test_tarefa_cruza_dois_meses_divide_por_dias_uteis():
    # 29/06 (seg) a 03/07 (sex): 2 dias úteis em junho (29,30) + 3 em julho (1,2,3)
    out = fasear_por_dias_uteis(D("1000"), date(2026, 6, 29), date(2026, 7, 3), False, False)
    assert set(out) == {"2026-06", "2026-07"}
    assert out["2026-06"] + out["2026-07"] == D("1000")
    assert out["2026-06"] == D("400.00")
    assert out["2026-07"] == D("600.00")


def test_valor_zero_retorna_vazio():
    assert fasear_por_dias_uteis(D("0"), date(2026, 6, 1), date(2026, 6, 5), False, False) == {}
