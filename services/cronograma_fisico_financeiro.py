"""Cronograma físico-financeiro (derivado).

Funções puras (sem banco) para alocação de custo às tarefas, faseamento por dias
úteis e Curva S; mais um orquestrador que monta a visão por etapa a partir de
ObraServicoCusto + pesos do IMC + datas das tarefas.
"""
from __future__ import annotations

from datetime import date, timedelta
from decimal import Decimal, ROUND_HALF_UP

CENTAVO = Decimal("0.01")
NAO_FASEADO = "__nao_faseado__"


def _is_dia_util(d: date, considerar_sabado: bool, considerar_domingo: bool) -> bool:
    wd = d.weekday()  # 0=seg ... 5=sab 6=dom
    if wd == 5 and not considerar_sabado:
        return False
    if wd == 6 and not considerar_domingo:
        return False
    return True


def fasear_por_dias_uteis(valor: Decimal, data_inicio, data_fim,
                          considerar_sabado: bool, considerar_domingo: bool) -> dict:
    """Distribui `valor` pelos dias úteis entre data_inicio e data_fim (inclusive),
    agregando por mês 'YYYY-MM'. Sem datas → bucket NAO_FASEADO. valor 0 → {}.
    Conserva o total (o último mês absorve o resto do arredondamento)."""
    if valor is None or valor == 0:
        return {}
    valor = Decimal(valor)
    if not data_inicio or not data_fim:
        return {NAO_FASEADO: valor}

    dias_por_mes: dict[str, int] = {}
    d = data_inicio
    total_dias = 0
    while d <= data_fim:
        if _is_dia_util(d, considerar_sabado, considerar_domingo):
            chave = f"{d.year:04d}-{d.month:02d}"
            dias_por_mes[chave] = dias_por_mes.get(chave, 0) + 1
            total_dias += 1
        d += timedelta(days=1)

    if total_dias == 0:
        return {NAO_FASEADO: valor}

    meses = sorted(dias_por_mes)
    out: dict[str, Decimal] = {}
    acumulado = Decimal("0")
    for i, mes in enumerate(meses):
        if i < len(meses) - 1:
            parcela = (valor * dias_por_mes[mes] / total_dias).quantize(CENTAVO, ROUND_HALF_UP)
            out[mes] = parcela
            acumulado += parcela
        else:
            out[mes] = (valor - acumulado).quantize(CENTAVO, ROUND_HALF_UP)
    return out


def alocar_por_peso(valor: Decimal, pesos: list) -> dict:
    """Distribui `valor` entre chaves proporcional ao peso. `pesos` é lista de
    (chave, peso). Se Σpeso == 0, distribui igualmente. Conserva o total
    (última chave absorve o resto)."""
    if not pesos:
        return {}
    valor = Decimal(valor)
    soma = sum((Decimal(p) for _, p in pesos), Decimal("0"))
    n = len(pesos)
    out: dict = {}
    acumulado = Decimal("0")
    for i, (chave, peso) in enumerate(pesos):
        if i < n - 1:
            if soma > 0:
                parcela = (valor * Decimal(peso) / soma).quantize(CENTAVO, ROUND_HALF_UP)
            else:
                parcela = (valor / n).quantize(CENTAVO, ROUND_HALF_UP)
            out[chave] = parcela
            acumulado += parcela
        else:
            out[chave] = (valor - acumulado).quantize(CENTAVO, ROUND_HALF_UP)
    return out


def montar_curva_s(meses_valores: dict) -> list:
    """Recebe {'YYYY-MM': Decimal}; retorna lista ordenada por mês com
    custo do mês, acumulado e pct_acumulado (sobre o total). Ignora o bucket
    NAO_FASEADO."""
    meses = {k: Decimal(v) for k, v in meses_valores.items() if k != NAO_FASEADO}
    if not meses:
        return []
    total = sum(meses.values(), Decimal("0"))
    curva = []
    acumulado = Decimal("0")
    for mes in sorted(meses):
        acumulado += meses[mes]
        pct = (acumulado / total) if total > 0 else Decimal("0")
        curva.append({
            "mes": mes,
            "custo_mes": meses[mes],
            "acumulado": acumulado,
            "pct_acumulado": pct,
        })
    return curva


def classificar_veks_fat(material, mao_obra, outros,
                         fonte_material, fonte_mao_obra, fonte_outros):
    """Soma as categorias em (veks, fat_direto) conforme cada fonte. Qualquer
    valor de fonte != 'fat_direto' é tratado como 'veks'."""
    veks = Decimal("0")
    fat = Decimal("0")
    for valor, fonte in (
        (material, fonte_material),
        (mao_obra, fonte_mao_obra),
        (outros, fonte_outros),
    ):
        v = Decimal(valor or 0)
        if fonte == "fat_direto":
            fat += v
        else:
            veks += v
    return veks, fat


def _previsto_por_categoria(osc):
    """Previsto = realizado + a_realizar, por categoria (Decimal)."""
    material = Decimal(osc.realizado_material or 0) + Decimal(osc.material_a_realizar or 0)
    mao_obra = Decimal(osc.realizado_mao_obra or 0) + Decimal(osc.mao_obra_a_realizar or 0)
    outros = Decimal(osc.realizado_outros or 0) + Decimal(osc.outros_a_realizar or 0)
    return material, mao_obra, outros


def _raiz_da_tarefa(tarefa, por_id):
    """Sobe a hierarquia até o nó raiz (etapa). `por_id` mapeia id->tarefa."""
    atual = tarefa
    visitados = set()
    while atual.tarefa_pai_id and atual.tarefa_pai_id in por_id and atual.id not in visitados:
        visitados.add(atual.id)
        atual = por_id[atual.tarefa_pai_id]
    return atual


def montar_fisico_financeiro(obra_id: int, admin_id: int) -> dict:
    """Monta a visão físico-financeira por etapa (nó raiz do cronograma) a partir
    de ObraServicoCusto (custo) + pesos do IMC (alocação por tarefa) + datas das
    tarefas (faseamento). Tudo derivado; ver design 2026-06-23."""
    from models import (
        ObraServicoCusto, TarefaCronograma, ItemMedicaoCronogramaTarefa,
    )
    from models import CalendarioEmpresa

    cal = CalendarioEmpresa.query.filter_by(admin_id=admin_id).first()
    sab = cal.considerar_sabado if cal else False
    dom = cal.considerar_domingo if cal else False

    tarefas = TarefaCronograma.query.filter_by(obra_id=obra_id, admin_id=admin_id).all()
    por_id = {t.id: t for t in tarefas}

    custos = ObraServicoCusto.query.filter_by(obra_id=obra_id, admin_id=admin_id).all()

    etapas: dict = {}
    meses_globais: dict = {}
    nao_faseado = Decimal("0")
    avisos: list = []

    def _etapa(raiz):
        if raiz.id not in etapas:
            etapas[raiz.id] = {
                "etapa_id": raiz.id,
                "nome": raiz.nome_tarefa,
                "categoria": getattr(getattr(raiz, "servico", None), "categoria", None),
                "previsto": {"material": Decimal("0"), "mao_obra": Decimal("0"),
                             "outros": Decimal("0"), "total": Decimal("0")},
                "veks": Decimal("0"), "fat_direto": Decimal("0"),
                "orcado": Decimal("0"), "realizado": Decimal("0"),
                "meses": {},
            }
        return etapas[raiz.id]

    for osc in custos:
        material, mao_obra, outros = _previsto_por_categoria(osc)
        previsto_total = material + mao_obra + outros
        veks, fat = classificar_veks_fat(
            material, mao_obra, outros,
            osc.fonte_material, osc.fonte_mao_obra, osc.fonte_outros,
        )

        vinculos = []
        if osc.item_medicao_comercial_id:
            vinculos = ItemMedicaoCronogramaTarefa.query.filter_by(
                item_medicao_id=osc.item_medicao_comercial_id, admin_id=admin_id,
            ).all()
        pesos = [(v.cronograma_tarefa_id, Decimal(v.peso or 0))
                 for v in vinculos if v.cronograma_tarefa_id in por_id]

        if not pesos:
            avisos.append(f"Serviço '{osc.nome}' sem tarefas vinculadas — custo não faseado.")
            nao_faseado += previsto_total
            raiz_sintetica = type("R", (), {"id": f"osc-{osc.id}", "nome_tarefa": osc.nome,
                                            "servico": None, "tarefa_pai_id": None})
            resumo_por_raiz = [(_etapa(raiz_sintetica), Decimal("1"))]
        else:
            # peso total por raiz (etapa) das folhas vinculadas a este OSC
            peso_por_raiz = {}   # raiz_id -> [etapa_dict, peso_acumulado]
            for tarefa_id, peso in pesos:
                folha = por_id[tarefa_id]
                raiz = _raiz_da_tarefa(folha, por_id)
                et = _etapa(raiz)
                slot = peso_por_raiz.setdefault(raiz.id, [et, Decimal("0")])
                slot[1] += Decimal(peso)
            # faseia o previsto alocado a cada folha (inalterado)
            aloc = alocar_por_peso(previsto_total, pesos)
            for tarefa_id, valor_tarefa in aloc.items():
                folha = por_id[tarefa_id]
                et = _etapa(_raiz_da_tarefa(folha, por_id))
                fases = fasear_por_dias_uteis(valor_tarefa, folha.data_inicio, folha.data_fim, sab, dom)
                for mes, parcela in fases.items():
                    if mes == NAO_FASEADO:
                        nao_faseado += parcela
                        continue
                    et["meses"][mes] = et["meses"].get(mes, Decimal("0")) + parcela
                    meses_globais[mes] = meses_globais.get(mes, Decimal("0")) + parcela
            # fração de resumo por raiz = peso da raiz / Σpeso (fallback igual)
            soma_peso = sum((p for _, p in peso_por_raiz.values()), Decimal("0"))
            n_raizes = len(peso_por_raiz)
            resumo_por_raiz = []
            for et, peso_raiz in peso_por_raiz.values():
                frac = (peso_raiz / soma_peso) if soma_peso > 0 else (Decimal("1") / n_raizes)
                resumo_por_raiz.append((et, frac))

        # distribui os agregados de resumo entre as raízes pela fração
        for et, frac in resumo_por_raiz:
            et["previsto"]["material"] += material * frac
            et["previsto"]["mao_obra"] += mao_obra * frac
            et["previsto"]["outros"] += outros * frac
            et["previsto"]["total"] += previsto_total * frac
            et["veks"] += veks * frac
            et["fat_direto"] += fat * frac
            et["orcado"] += Decimal(osc.valor_orcado or 0) * frac
            et["realizado"] += Decimal(osc.realizado_total or 0) * frac

    for et in etapas.values():
        et["desvio"] = et["realizado"] - et["previsto"]["total"]

    meses_ordenados = sorted(meses_globais)
    totais = {
        "veks": sum((e["veks"] for e in etapas.values()), Decimal("0")),
        "fat_direto": sum((e["fat_direto"] for e in etapas.values()), Decimal("0")),
        "previsto": sum((e["previsto"]["total"] for e in etapas.values()), Decimal("0")),
        "orcado": sum((e["orcado"] for e in etapas.values()), Decimal("0")),
        "realizado": sum((e["realizado"] for e in etapas.values()), Decimal("0")),
    }
    totais["total"] = totais["veks"] + totais["fat_direto"]

    return {
        "etapas": sorted(etapas.values(), key=lambda e: str(e["nome"] or "")),
        "meses_ordenados": meses_ordenados,
        "totais": totais,
        "curva_s": montar_curva_s(meses_globais),
        "nao_faseado": nao_faseado,
        "avisos": avisos,
    }


def exportar_fisico_financeiro_xlsx(dados: dict):
    """Gera um openpyxl.Workbook no layout da planilha de referência:
    aba 'Cronograma FF (por etapa)' + aba 'Curva S'."""
    from openpyxl import Workbook

    wb = Workbook()
    ws = wb.active
    ws.title = "Cronograma FF (por etapa)"

    meses = dados.get("meses_ordenados", [])
    header = ["Etapa", "Veks (R$)", "Fat Direto (R$)", "Total (R$)", "%"] + list(meses)
    ws.append(header)

    total_geral = dados["totais"]["total"] or Decimal("1")
    for et in dados["etapas"]:
        total_et = et["previsto"]["total"]
        pct = (total_et / total_geral) if total_geral else Decimal("0")
        linha = [
            et["nome"],
            float(et["veks"]), float(et["fat_direto"]), float(total_et), float(pct),
        ]
        for mes in meses:
            linha.append(float(et["meses"].get(mes, 0)))
        ws.append(linha)

    t = dados["totais"]
    rodape = ["TOTAL GERAL", float(t["veks"]), float(t["fat_direto"]), float(t["total"]), 1.0]
    # soma por mês
    soma_mes = {m: Decimal("0") for m in meses}
    for et in dados["etapas"]:
        for m in meses:
            soma_mes[m] += et["meses"].get(m, Decimal("0"))
    rodape += [float(soma_mes[m]) for m in meses]
    ws.append(rodape)

    # aba Curva S
    ws2 = wb.create_sheet("Curva S")
    ws2.append(["Mês", "Custo do mês", "Custo acumulado", "% acumulado"])
    for ponto in dados.get("curva_s", []):
        ws2.append([
            ponto["mes"], float(ponto["custo_mes"]),
            float(ponto["acumulado"]), float(ponto["pct_acumulado"]),
        ])
    return wb
