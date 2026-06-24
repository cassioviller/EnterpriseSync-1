from datetime import date
from decimal import Decimal

import pytest

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


from services.cronograma_fisico_financeiro import classificar_veks_fat


def test_material_fat_mao_obra_veks():
    veks, fat = classificar_veks_fat(
        material=D("100"), mao_obra=D("50"), outros=D("10"),
        fonte_material="fat_direto", fonte_mao_obra="veks", fonte_outros="veks",
    )
    assert fat == D("100")
    assert veks == D("60")
    assert veks + fat == D("160")


def test_tudo_veks_por_default():
    veks, fat = classificar_veks_fat(
        material=D("100"), mao_obra=D("50"), outros=D("10"),
        fonte_material="veks", fonte_mao_obra="veks", fonte_outros="veks",
    )
    assert veks == D("160") and fat == D("0")


from services.cronograma_fisico_financeiro import exportar_fisico_financeiro_xlsx


def test_xlsx_tem_abas_e_cabecalho():
    dados = {
        "etapas": [{
            "etapa_id": 1, "nome": "Fundação", "categoria": "Fundação",
            "previsto": {"material": D("20000"), "mao_obra": D("49000"),
                         "outros": D("9300"), "total": D("78300")},
            "veks": D("58300"), "fat_direto": D("20000"),
            "orcado": D("78300"), "realizado": D("0"), "desvio": D("-78300"),
            "meses": {"2026-06": D("70000"), "2026-07": D("8300")},
        }],
        "meses_ordenados": ["2026-06", "2026-07"],
        "totais": {"veks": D("58300"), "fat_direto": D("20000"), "total": D("78300"),
                   "previsto": D("78300"), "orcado": D("78300"), "realizado": D("0")},
        "curva_s": [
            {"mes": "2026-06", "custo_mes": D("70000"), "acumulado": D("70000"), "pct_acumulado": D("0.894")},
            {"mes": "2026-07", "custo_mes": D("8300"), "acumulado": D("78300"), "pct_acumulado": D("1")},
        ],
        "nao_faseado": D("0"), "avisos": [],
    }
    wb = exportar_fisico_financeiro_xlsx(dados)
    assert {ws.title for ws in wb.worksheets} == {"Cronograma FF (por etapa)", "Curva S"}
    ws = wb["Cronograma FF (por etapa)"]
    # cabeçalho: Etapa | Veks | Fat Direto | Total | % | 2026-06 | 2026-07
    header = [c.value for c in ws[1]]
    assert header[:5] == ["Etapa", "Veks (R$)", "Fat Direto (R$)", "Total (R$)", "%"]
    assert "2026-06" in header and "2026-07" in header
    # primeira etapa
    assert ws.cell(row=2, column=1).value == "Fundação"


from services.cronograma_fisico_financeiro import calcular_fluxo_caixa


def test_caixa_rolante_2_meses_sem_fat():
    meses = ["2026-06", "2026-07"]
    res = calcular_fluxo_caixa(
        meses,
        medicao={"2026-06": D("100000"), "2026-07": D("50000")},
        fat_direto={"2026-06": D("0"), "2026-07": D("0")},
        gasto_veks={"2026-06": D("30000"), "2026-07": D("20000")},
        imposto_pct=D("0.135"),
    )
    jun, jul = res["linhas"]
    assert jun["imposto"] == D("13500.00")
    assert jun["entrada"] == D("86500.00")
    assert jun["caixa_final"] == D("56500.00")
    assert jul["caixa_inicial"] == D("99750.00")
    assert jul["caixa_final"] == D("79750.00")
    assert res["lucro_em_caixa"] == D("79750.00")


def test_caixa_fat_do_periodo_anterior():
    meses = ["2026-06", "2026-07"]
    res = calcular_fluxo_caixa(
        meses,
        medicao={"2026-06": D("100000"), "2026-07": D("100000")},
        fat_direto={"2026-06": D("40000"), "2026-07": D("0")},
        gasto_veks={"2026-06": D("0"), "2026-07": D("0")},
        imposto_pct=D("0.135"),
    )
    jun, jul = res["linhas"]
    assert jun["entrada"] == D("86500.00")
    assert jul["imposto"] == D("8100.00")
    assert jul["entrada"] == D("51900.00")


from services.cronograma_fisico_financeiro import comparar_fluxo_caixa


def test_divergencia_por_mes_e_resumo_veks():
    recalc = {"2026-06": D("100000"), "2026-07": D("100000")}
    verbatim = {"2026-06": D("130000"), "2026-07": D("100000")}
    res = comparar_fluxo_caixa(recalc, verbatim)
    assert res["por_mes"]["2026-06"]["delta"] == D("30000")
    assert res["por_mes"]["2026-07"]["delta"] == D("0")
    assert res["total_recalc"] == D("200000")
    assert res["total_verbatim"] == D("230000")
    assert res["delta_total"] == D("30000")
