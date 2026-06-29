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


def calcular_fluxo_caixa(meses, medicao, fat_direto, gasto_veks, imposto_pct,
                         fat_competencia="seguinte"):
    """Modelo de caixa derivado. Dicts mes->Decimal. `fat_competencia` controla
    em qual período o faturamento direto abate a base de imposto/entrada:
      - "seguinte" (padrão, regra da Planilha1): cada mês usa o fat_direto do mês
        ANTERIOR — o desconto escorrega para o período seguinte.
      - "mesma": o fat_direto abate na PRÓPRIA medição (mesma competência),
        reduzindo o imposto no período a que pertence (inclusive o último).
    Em ambos os casos o imposto incide sobre (medição − fat abatido).
    Retorna {linhas:[...], lucro_em_caixa}."""
    imposto_pct = Decimal(imposto_pct)
    mesma = (fat_competencia == "mesma")
    fat_anterior = Decimal("0")
    caixa_final_anterior = None
    linhas = []
    for m in meses:
        med = Decimal(medicao.get(m, 0) or 0)
        fat_mes = Decimal(fat_direto.get(m, 0) or 0)
        # valor de fat_direto que abate NESTE período
        fat_abatido = fat_mes if mesma else fat_anterior
        imp = ((med - fat_abatido) * imposto_pct).quantize(CENTAVO, ROUND_HALF_UP)
        entrada = (med - fat_abatido - imp).quantize(CENTAVO, ROUND_HALF_UP)
        if caixa_final_anterior is None:
            caixa_ini = entrada
        else:
            caixa_ini = caixa_final_anterior + entrada
        veks = Decimal(gasto_veks.get(m, 0) or 0)
        caixa_fim = (caixa_ini - veks).quantize(CENTAVO, ROUND_HALF_UP)
        linhas.append({
            "mes": m, "medicao": med, "fat_anterior": fat_abatido,
            "imposto": imp, "entrada": entrada,
            "caixa_inicial": caixa_ini, "gasto_veks": veks, "caixa_final": caixa_fim,
        })
        fat_anterior = fat_mes
        caixa_final_anterior = caixa_fim
    # Alerta de caixa negativo: derivado ao vivo dos próprios `linhas`, nunca
    # persistido — recalcula a cada chamada, então se autocorrige quando os
    # valores mudam (mês que deixa de ser negativo some; outro que vira aparece).
    meses_negativos = [
        {"mes": l["mes"], "caixa_final": l["caixa_final"]}
        for l in linhas if l["caixa_final"] < 0
    ]
    pior_caixa = min(meses_negativos, key=lambda x: x["caixa_final"]) \
        if meses_negativos else None
    return {
        "linhas": linhas,
        "lucro_em_caixa": linhas[-1]["caixa_final"] if linhas else Decimal("0"),
        "meses_negativos": meses_negativos,
        "pior_caixa": pior_caixa,
    }


def comparar_fluxo_caixa(recalc, verbatim):
    """Compara dois dicts mes->Decimal (ex.: gasto_veks recalculado × verbatim).
    delta = verbatim - recalc por mês e no total."""
    meses = sorted(set(recalc) | set(verbatim))
    por_mes = {}
    total_r = Decimal("0")
    total_v = Decimal("0")
    for m in meses:
        r = Decimal(recalc.get(m, 0) or 0)
        v = Decimal(verbatim.get(m, 0) or 0)
        por_mes[m] = {"recalc": r, "verbatim": v, "delta": v - r}
        total_r += r
        total_v += v
    return {
        "por_mes": por_mes,
        "total_recalc": total_r,
        "total_verbatim": total_v,
        "delta_total": total_v - total_r,
    }


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
    meses_veks: dict = {}
    meses_fat: dict = {}
    nao_faseado = Decimal("0")
    avisos: list = []

    def _etapa(osc):
        """Bucket de etapa por CUSTO (OSC), não pela raiz da árvore do cronograma.
        A árvore do cronograma vira o outline do .mpp (raiz única OBRA), então
        agrupar por raiz colapsaria tudo numa etapa só. Cada OSC é uma etapa."""
        if osc.id not in etapas:
            etapas[osc.id] = {
                "etapa_id": osc.id,
                "osc_id": osc.id,
                "nome": osc.nome,
                "categoria": getattr(getattr(osc, "servico", None), "categoria", None),
                "tipo": "entregavel",   # vira 'periodo' se não houver tarefa vinculada
                "pct_fisico": None,     # período não tem avanço físico
                "previsto": {"material": Decimal("0"), "mao_obra": Decimal("0"),
                             "outros": Decimal("0"), "total": Decimal("0")},
                "veks": Decimal("0"), "fat_direto": Decimal("0"),
                "orcado": Decimal("0"), "realizado": Decimal("0"),
                "meses": {},
            }
        return etapas[osc.id]

    # Desembolso (caixa) faseado pelas DATAS DAS LINHAS de custo (fonte da verdade).
    # `meses_veks/meses_fat` arrancam com as parcelas já faseadas por datas; o loop
    # abaixo soma, POR CRONOGRAMA, apenas o que cada OSC ainda não faseou por linha
    # (fallback complementar para linhas sem datas).
    linhas_veks, linhas_fat, faseado_por_osc = fasear_custo_por_linhas(
        obra_id, admin_id, sab, dom)
    meses_veks.update(linhas_veks)
    meses_fat.update(linhas_fat)

    for osc in custos:
        material, mao_obra, outros = _previsto_por_categoria(osc)
        previsto_total = material + mao_obra + outros
        veks, fat = classificar_veks_fat(
            material, mao_obra, outros,
            osc.fonte_material, osc.fonte_mao_obra, osc.fonte_outros,
        )
        et = _etapa(osc)
        et["previsto"]["material"] += material
        et["previsto"]["mao_obra"] += mao_obra
        et["previsto"]["outros"] += outros
        et["previsto"]["total"] += previsto_total
        et["veks"] += veks
        et["fat_direto"] += fat
        et["orcado"] += Decimal(osc.valor_orcado or 0)
        et["realizado"] += Decimal(osc.realizado_total or 0)

        # remanescente a fasear pelo cronograma = total do OSC menos o já faseado
        # por datas de linha. Clamp em 0 (linhas nunca excedem o agregado).
        _ja = faseado_por_osc.get(osc.id, {})
        veks_cron = max(veks - _ja.get('veks', Decimal("0")), Decimal("0"))
        fat_cron = max(fat - _ja.get('fat', Decimal("0")), Decimal("0"))

        vinculos = []
        if osc.item_medicao_comercial_id:
            vinculos = ItemMedicaoCronogramaTarefa.query.filter_by(
                item_medicao_id=osc.item_medicao_comercial_id, admin_id=admin_id,
            ).all()
        pesos = [(v.cronograma_tarefa_id, Decimal(v.peso or 0))
                 for v in vinculos if v.cronograma_tarefa_id in por_id]

        if not pesos:
            # Custo de PERÍODO / avulso (indiretos, escritório, estadia…): não passa
            # por medição física — não tem tarefa no .mpp. O caixa já foi faseado
            # pelas datas das linhas (fasear_custo_por_linhas, acima); não há curva
            # de previsto físico. NÃO é erro: não entra em `nao_faseado`.
            et["tipo"] = "periodo"
            continue

        # Etapa entregável: faseia o previsto físico pelas datas das tarefas
        # vinculadas; o financeiro usa só o remanescente não faseado por linha.
        razao_veks = (veks_cron / previsto_total) if previsto_total else Decimal("0")
        razao_fat = (fat_cron / previsto_total) if previsto_total else Decimal("0")
        aloc = alocar_por_peso(previsto_total, pesos)
        for tarefa_id, valor_tarefa in aloc.items():
            folha = por_id[tarefa_id]
            fases = fasear_por_dias_uteis(valor_tarefa, folha.data_inicio, folha.data_fim, sab, dom)
            for mes, parcela in fases.items():
                if mes == NAO_FASEADO:
                    nao_faseado += parcela
                    continue
                et["meses"][mes] = et["meses"].get(mes, Decimal("0")) + parcela
                meses_globais[mes] = meses_globais.get(mes, Decimal("0")) + parcela
                # precisão cheia de propósito; quantizado só ao entrar em calcular_fluxo_caixa
                meses_veks[mes] = meses_veks.get(mes, Decimal("0")) + (parcela * razao_veks)
                meses_fat[mes] = meses_fat.get(mes, Decimal("0")) + (parcela * razao_fat)

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
        "meses_veks": meses_veks,
        "meses_fat": meses_fat,
    }


def medicoes_contrato(obra) -> list:
    from models import MedicaoContrato
    meds = (MedicaoContrato.query
            .filter_by(obra_id=obra.id, admin_id=obra.admin_id)
            .order_by(MedicaoContrato.ordem).all())
    venda = Decimal(str(obra.valor_contrato or 0))
    out = []
    for m in meds:
        pct = Decimal(str(m.pct or 0))
        out.append({
            "nome": m.nome, "data": m.data, "pct": pct,
            "valor": (venda * pct).quantize(CENTAVO, ROUND_HALF_UP),
            "mes": m.recebido_no_mes, "obs": m.obs,
        })
    return out


def _medicao_por_mes(obra):
    """Soma valor das medições por mês 'YYYY-MM' (pela data)."""
    out = {}
    for m in medicoes_contrato(obra):
        if m["data"]:
            chave = f"{m['data'].year:04d}-{m['data'].month:02d}"
            out[chave] = out.get(chave, Decimal("0")) + m["valor"]
    return out


def _imposto_pct(obra):
    """Alíquota de imposto: do snapshot da planilha, senão 0.135 (ISS 4% + DAS 9,5%)."""
    snap = obra.fluxo_caixa_planilha or {}
    val = snap.get("imposto_pct") if isinstance(snap, dict) else None
    return Decimal(str(val or "0.135"))


def _fat_competencia(obra):
    """Competência do abatimento do faturamento direto: 'seguinte' (padrão, abate
    no período seguinte) ou 'mesma' (abate na própria medição)."""
    snap = obra.fluxo_caixa_planilha or {}
    val = snap.get("fat_competencia") if isinstance(snap, dict) else None
    return "mesma" if val == "mesma" else "seguinte"


def fluxo_caixa(obra, dados=None):
    """Fluxo de caixa recalculado: medições (por mês) + Veks/Fat faseados pelo
    cronograma. imposto_pct vem do snapshot/contrato (default 0.135)."""
    dados = dados if dados is not None else montar_fisico_financeiro(obra.id, obra.admin_id)
    medicao = _medicao_por_mes(obra)
    veks = {k: Decimal(v) for k, v in dados["meses_veks"].items()}
    fat = {k: Decimal(v) for k, v in dados["meses_fat"].items()}
    meses = sorted(set(medicao) | set(veks) | set(fat))
    imposto_pct = _imposto_pct(obra)
    res = calcular_fluxo_caixa(meses, medicao, fat, veks, imposto_pct,
                               fat_competencia=_fat_competencia(obra))
    res["meses"] = meses
    return res


_MESES_PT = {"jan": 1, "fev": 2, "mar": 3, "abr": 4, "mai": 5, "jun": 6,
             "jul": 7, "ago": 8, "set": 9, "out": 10, "nov": 11, "dez": 12}


def _veks_verbatim_por_mes(rotulos, valores, obra):
    """Converte rótulos 'jun','jul'... + lista de valores em {'YYYY-MM': Decimal},
    inferindo o ano pela data_inicio da obra (rola para o ano seguinte se o mês
    for menor que o mês inicial)."""
    ano_base = obra.data_inicio.year if obra.data_inicio else date.today().year
    mes_ini = obra.data_inicio.month if obra.data_inicio else 1
    out = {}
    for rotulo, val in zip(rotulos, valores):
        m = _MESES_PT.get(str(rotulo).strip().lower()[:3])
        if not m:
            continue
        ano = ano_base if m >= mes_ini else ano_base + 1
        chave = f"{ano:04d}-{m:02d}"
        out[chave] = out.get(chave, Decimal("0")) + Decimal(str(val or 0))
    return out


def fluxo_caixa_divergencia(obra, dados=None):
    """Compara Veks faseado (recalc) × GASTO VEKS do snapshot verbatim, mês a mês,
    e resume a inconsistência dos Indiretos (Δ Veks e os dois lucros)."""
    dados = dados if dados is not None else montar_fisico_financeiro(obra.id, obra.admin_id)
    recalc = {k: Decimal(v) for k, v in dados["meses_veks"].items()}
    snap = obra.fluxo_caixa_planilha or {}
    verbatim = {}
    if isinstance(snap, dict) and snap.get("meses") and snap.get("gasto_veks"):
        verbatim = _veks_verbatim_por_mes(snap["meses"], snap["gasto_veks"], obra)
    cmp = comparar_fluxo_caixa(recalc, verbatim)
    veks_etapas = dados["totais"]["veks"]
    veks_verbatim = cmp["total_verbatim"]
    lucro_caixa = Decimal(str((snap.get("lucro_caixa_final") if isinstance(snap, dict) else 0) or 0))
    venda = Decimal(str(obra.valor_contrato or 0))
    # Imposto incide só sobre o que a Veks fatura/recebe = venda − fat_direto
    # (o fat direto é pago pelo cliente direto ao fornecedor → fora da base).
    base_imposto = venda - dados["totais"]["fat_direto"]
    imposto = (base_imposto * _imposto_pct(obra)).quantize(CENTAVO, ROUND_HALF_UP)
    cmp["resumo"] = {
        "veks_etapas": veks_etapas,
        "veks_verbatim": veks_verbatim,
        "delta_veks": (veks_verbatim - veks_etapas) if veks_verbatim else Decimal("0"),
        "lucro_em_caixa": lucro_caixa,
        "lucro_por_etapas": venda - dados["totais"]["total"] - imposto,
    }
    return cmp


def kpis(obra, dados=None):
    venda = Decimal(str(obra.valor_contrato or 0))
    dados = dados if dados is not None else montar_fisico_financeiro(obra.id, obra.admin_id)
    custo = dados["totais"]["total"]
    # Imposto sobre a base recebida pela Veks = venda − fat_direto (ver fluxo_caixa).
    base_imposto = venda - dados["totais"]["fat_direto"]
    imposto = (base_imposto * _imposto_pct(obra)).quantize(CENTAVO, ROUND_HALF_UP)
    lucro = venda - custo - imposto
    recebido = Decimal("0")
    for m in medicoes_contrato(obra):
        if m["data"] and m["data"] <= date.today():
            recebido += m["valor"]
    return {
        "venda": venda, "custo_total": custo,
        "imposto": imposto, "lucro_projetado": lucro,
        "lucro_pct": (lucro / venda) if venda else Decimal("0"),
        "desembolso_veks": dados["totais"]["veks"],
        "fat_direto": dados["totais"]["fat_direto"],
        "recebido_ate_hoje": recebido,
    }


def painel_financeiro(obra) -> dict:
    """Dicionário consolidado do Painel Financeiro (pronto para JSON):
    KPIs, etapas (previsto+realizado), Curva S de 4 séries (recebido líquido,
    gasto Veks previsto, lucro, custo realizado), caixa, medições, doughnut, divergência."""
    from services.resumo_custos_obra import calcular_resumo_obra

    dados = montar_fisico_financeiro(obra.id, obra.admin_id)
    k = kpis(obra, dados)
    caixa = fluxo_caixa(obra, dados)
    meds = medicoes_contrato(obra)
    div = fluxo_caixa_divergencia(obra, dados)
    resumo = calcular_resumo_obra(obra.id, obra.admin_id).get('indicadores', {})

    realizado_mes = curva_realizado(obra)
    realizado_etapa = realizado_por_etapa(obra)

    meses = sorted(set([l["mes"] for l in caixa["linhas"]]) | set(realizado_mes))
    caixa_por_mes = {l["mes"]: l for l in caixa["linhas"]}
    receb_ac, gasto_ac, real_ac = [], [], []
    r = g = real_ = Decimal("0")
    for m in meses:
        linha = caixa_por_mes.get(m)
        r += (linha["entrada"] if linha else Decimal("0"))
        g += (linha["gasto_veks"] if linha else Decimal("0"))
        real_ += realizado_mes.get(m, Decimal("0"))
        receb_ac.append(r); gasto_ac.append(g); real_ac.append(real_)
    lucro_ac = [receb_ac[i] - gasto_ac[i] for i in range(len(meses))]

    from models import ObraServicoCusto, ObraServicoCustoItem
    osc_ids = [o.id for o in ObraServicoCusto.query.filter_by(
        obra_id=obra.id, admin_id=obra.admin_id).all()]
    itens_por_osc = {}
    if osc_ids:
        linhas = (ObraServicoCustoItem.query
                  .filter(ObraServicoCustoItem.obra_servico_custo_id.in_(osc_ids))
                  .order_by(ObraServicoCustoItem.obra_servico_custo_id,
                            ObraServicoCustoItem.ordem).all())
        for it in linhas:
            itens_por_osc.setdefault(it.obra_servico_custo_id, []).append(
                {"id": it.id, "descricao": it.descricao, "valor": it.valor, "fonte": it.fonte,
                 "data_inicio": it.data_inicio, "data_fim": it.data_fim})

    etapas = []
    for e in dados["etapas"]:
        osc_id = e.get("osc_id")  # id verdadeiro do ObraServicoCusto, ou None (etapa multi-OSC)
        etapas.append({
            "nome": e["nome"],
            "veks": e["veks"],
            "fat": e["fat_direto"],
            "previsto": e["previsto"]["total"],
            "realizado": realizado_etapa.get(osc_id, Decimal("0")),
            "osc_id": osc_id,
            "itens": itens_por_osc.get(osc_id, []),
            # 'entregavel' (medida por execução/RDO) | 'periodo' (custo de período,
            # sem avanço físico). Período aparece junto, sem % físico.
            "tipo": e.get("tipo", "entregavel"),
            "pct_fisico": e.get("pct_fisico"),
        })

    # Verba disponível (caixa) = o que já entrou (recebido até hoje, pelas
    # medições de contrato) menos o que já foi gasto (custo realizado). Usa os
    # próprios números do painel para ficar internamente consistente — o
    # `verba_disponivel` do resumo usa outra fonte de "recebido" (MedicaoObra),
    # que fica zerada em obras importadas/sem medição de execução.
    custo_realizado = Decimal(str(resumo.get("total_realizado", 0) or 0))
    verba_disponivel = k["recebido_ate_hoje"] - custo_realizado

    return {
        "kpis": {**k, "verba_disponivel": verba_disponivel,
                 "custo_realizado": custo_realizado},
        "etapas": etapas,
        "curva_s": {"meses": meses, "recebido_liquido": receb_ac,
                    "gasto_veks": gasto_ac, "lucro": lucro_ac, "realizado": real_ac},
        "caixa": caixa,
        "medicoes": meds,
        "doughnut": {"veks": dados["totais"]["veks"], "fat": dados["totais"]["fat_direto"]},
        "divergencia": div,
        "config": {"fat_competencia": _fat_competencia(obra)},
    }


def curva_realizado(obra) -> dict:
    """Custo realizado por mês 'YYYY-MM' a partir de GestaoCustoFilho.data_referencia,
    tenant-scoped, excluindo FATURAMENTO_DIRETO. Fonte: RDO/diárias, empreitadas,
    compras, aluguel — cresce ao longo do tempo."""
    from models import db, GestaoCustoFilho, GestaoCustoPai
    rows = (db.session.query(GestaoCustoFilho.data_referencia, GestaoCustoFilho.valor)
            .join(GestaoCustoPai, GestaoCustoFilho.pai_id == GestaoCustoPai.id)
            .filter(GestaoCustoFilho.obra_id == obra.id)
            .filter(GestaoCustoPai.admin_id == obra.admin_id)
            .filter(GestaoCustoPai.tipo_categoria != 'FATURAMENTO_DIRETO')
            .all())
    out: dict = {}
    for dt, valor in rows:
        if not dt:
            continue
        chave = f"{dt.year:04d}-{dt.month:02d}"
        out[chave] = out.get(chave, Decimal("0")) + Decimal(valor or 0)
    return out


def realizado_por_etapa(obra) -> dict:
    """Realizado por etapa: {obra_servico_custo_id: Decimal} (exclui FATURAMENTO_DIRETO)."""
    from models import db, GestaoCustoFilho, GestaoCustoPai
    rows = (db.session.query(GestaoCustoFilho.obra_servico_custo_id, GestaoCustoFilho.valor)
            .join(GestaoCustoPai, GestaoCustoFilho.pai_id == GestaoCustoPai.id)
            .filter(GestaoCustoFilho.obra_id == obra.id)
            .filter(GestaoCustoPai.admin_id == obra.admin_id)
            .filter(GestaoCustoPai.tipo_categoria != 'FATURAMENTO_DIRETO')
            .all())
    out: dict = {}
    for osc_id, valor in rows:
        if osc_id is None:
            continue
        out[osc_id] = out.get(osc_id, Decimal("0")) + Decimal(valor or 0)
    return out


def lancamentos_da_etapa(obra, osc_id) -> list:
    """Lança­mentos de custo realizado (GestaoCustoFilho) ligados a uma etapa (OSC),
    ordenados por data. `editavel` = lançamento manual criado no painel."""
    from models import db, GestaoCustoFilho, GestaoCustoPai
    rows = (db.session.query(GestaoCustoFilho)
            .join(GestaoCustoPai, GestaoCustoFilho.pai_id == GestaoCustoPai.id)
            .filter(GestaoCustoFilho.obra_id == obra.id)
            .filter(GestaoCustoFilho.obra_servico_custo_id == osc_id)
            .filter(GestaoCustoPai.admin_id == obra.admin_id)
            .filter(GestaoCustoPai.tipo_categoria != 'FATURAMENTO_DIRETO')
            .all())
    out = []
    for f in rows:
        origem = f.origem_tabela or ''
        editavel = origem == 'lancamento_periodo_manual'
        pai = f.pai
        cat_id = getattr(pai, 'categoria_fluxo_caixa_id', None)
        cat_label = (pai.categoria_fluxo_caixa.nome
                     if cat_id and pai.categoria_fluxo_caixa else None)
        out.append({
            "id": f.id, "data": f.data_referencia, "descricao": f.descricao,
            "valor": f.valor, "origem": origem,
            "origem_label": ("Manual" if editavel else (origem or "Sistema")),
            "categoria_id": cat_id, "categoria_label": cat_label,
            "editavel": editavel,
        })
    out.sort(key=lambda x: (x["data"] is None, x["data"] or 0))
    return out


def categorias_fluxo_caixa_saida(admin_id) -> list:
    """Categorias de SAÍDA ativas do tenant, agrupadas por grupo_financeiro, para o
    dropdown do lançamento: [{"grupo": str, "opcoes": [{"id", "nome"}]}]."""
    from models import db, CategoriaFluxoCaixa
    rows = (db.session.query(CategoriaFluxoCaixa)
            .filter(CategoriaFluxoCaixa.admin_id == admin_id)
            .filter(CategoriaFluxoCaixa.tipo == 'SAIDA')
            .filter(CategoriaFluxoCaixa.ativo.is_(True))
            .order_by(CategoriaFluxoCaixa.grupo_financeiro, CategoriaFluxoCaixa.nome)
            .all())
    grupos: list = []
    idx: dict = {}
    for c in rows:
        g = c.grupo_financeiro or 'Outros'
        if g not in idx:
            idx[g] = len(grupos)
            grupos.append({"grupo": g, "opcoes": []})
        grupos[idx[g]]["opcoes"].append({"id": c.id, "nome": c.nome})
    return grupos


def resolver_categoria_fluxo_caixa(admin_id, categoria_id):
    """Resolve a categoria do lançamento: devolve `categoria_id` se for uma
    CategoriaFluxoCaixa de SAÍDA ativa do tenant; senão a 'Outras Saídas' do tenant;
    senão None. Nunca levanta — categoria não derruba o POST."""
    from models import CategoriaFluxoCaixa
    if categoria_id is not None:
        c = (CategoriaFluxoCaixa.query
             .filter_by(id=categoria_id, admin_id=admin_id, tipo='SAIDA', ativo=True)
             .first())
        if c:
            return c.id
    fallback = (CategoriaFluxoCaixa.query
                .filter_by(admin_id=admin_id, nome='Outras Saídas', tipo='SAIDA')
                .first())
    return fallback.id if fallback else None


def fasear_custo_por_linhas(obra_id, admin_id, sab, dom):
    """Faseia por dias úteis o valor de cada linha de custo QUE TEM datas válidas,
    agregando por mês 'YYYY-MM' e por fonte. Retorna (meses_veks, meses_fat,
    faseado_por_osc), onde faseado_por_osc[osc_id] = {'veks': Σ, 'fat': Σ} é a
    parcela já faseada por datas (linhas sem datas NÃO entram — o caller faseia o
    restante pelo cronograma, fallback complementar)."""
    from models import ObraServicoCusto, ObraServicoCustoItem
    osc_ids = [o.id for o in ObraServicoCusto.query.filter_by(
        obra_id=obra_id, admin_id=admin_id).all()]
    meses_veks: dict = {}
    meses_fat: dict = {}
    faseado_por_osc: dict = {}
    if not osc_ids:
        return meses_veks, meses_fat, faseado_por_osc
    linhas = ObraServicoCustoItem.query.filter(
        ObraServicoCustoItem.obra_servico_custo_id.in_(osc_ids)).all()
    for l in linhas:
        valor = Decimal(str(l.valor or 0))
        if valor == 0:
            continue
        fases = fasear_por_dias_uteis(valor, l.data_inicio, l.data_fim, sab, dom)
        # linha sem datas (ou intervalo inválido) → NAO_FASEADO → não faseia aqui
        if NAO_FASEADO in fases:
            continue
        alvo = meses_fat if l.fonte == 'fat_direto' else meses_veks
        for mes, parcela in fases.items():
            alvo[mes] = alvo.get(mes, Decimal("0")) + parcela
        slot = faseado_por_osc.setdefault(
            l.obra_servico_custo_id, {'veks': Decimal('0'), 'fat': Decimal('0')})
        slot['fat' if l.fonte == 'fat_direto' else 'veks'] += valor
    return meses_veks, meses_fat, faseado_por_osc


def recalcular_osc_dos_itens(osc):
    """Deriva os agregados da OSC da soma das linhas de custo (fonte da verdade):
    Veks (mao_obra_a_realizar) = Σ valor (fonte != 'fat_direto');
    Fat (material_a_realizar)  = Σ valor (fonte == 'fat_direto'). Retorna (veks, fat)."""
    from models import ObraServicoCustoItem
    itens = ObraServicoCustoItem.query.filter_by(obra_servico_custo_id=osc.id).all()
    veks = sum((Decimal(str(i.valor or 0)) for i in itens if i.fonte != 'fat_direto'), Decimal("0"))
    fat = sum((Decimal(str(i.valor or 0)) for i in itens if i.fonte == 'fat_direto'), Decimal("0"))
    osc.mao_obra_a_realizar = veks
    osc.material_a_realizar = fat
    osc.outros_a_realizar = Decimal("0")
    osc.fonte_mao_obra = 'veks'
    osc.fonte_material = 'fat_direto'
    return veks, fat


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
