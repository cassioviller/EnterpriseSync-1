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


from services.cronograma_fisico_financeiro import alocar_por_peso


def test_aloca_proporcional_ao_peso_e_conserva_total():
    out = alocar_por_peso(D("1000"), [("a", D("30")), ("b", D("70"))])
    assert out == {"a": D("300.00"), "b": D("700.00")}
    assert sum(out.values()) == D("1000")


def test_peso_zero_distribui_igualmente():
    out = alocar_por_peso(D("900"), [("a", D("0")), ("b", D("0")), ("c", D("0"))])
    assert sum(out.values()) == D("900")
    assert out["a"] == D("300.00") and out["c"] == D("300.00")


def test_sem_tarefas_retorna_vazio():
    assert alocar_por_peso(D("100"), []) == {}


from services.cronograma_fisico_financeiro import montar_curva_s


def test_curva_s_acumula_e_fecha_em_um():
    curva = montar_curva_s({"2026-07": D("600"), "2026-06": D("400")})
    assert [c["mes"] for c in curva] == ["2026-06", "2026-07"]  # ordenado
    assert curva[0]["acumulado"] == D("400")
    assert curva[1]["acumulado"] == D("1000")
    assert curva[1]["pct_acumulado"] == D("1")
    assert curva[0]["pct_acumulado"] == D("0.4")


def test_curva_s_vazia():
    assert montar_curva_s({}) == []
