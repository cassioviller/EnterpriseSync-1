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


def calcular_fluxo_caixa(meses, medicao, fat_direto, gasto_veks, imposto_pct):
    """Modelo de caixa derivado. Dicts mes->Decimal. O fat_direto abate no
    PERÍODO SEGUINTE (regra da Planilha1): cada mês usa o fat_direto do mês
    anterior, e o imposto incide sobre (medição − fat anterior).
    Retorna {linhas:[...], lucro_em_caixa}."""
    imposto_pct = Decimal(imposto_pct)
    fat_anterior = Decimal("0")
    caixa_final_anterior = None
    linhas = []
    for m in meses:
        med = Decimal(medicao.get(m, 0) or 0)
        imp = ((med - fat_anterior) * imposto_pct).quantize(CENTAVO, ROUND_HALF_UP)
        entrada = (med - fat_anterior - imp).quantize(CENTAVO, ROUND_HALF_UP)
        if caixa_final_anterior is None:
            caixa_ini = entrada
        else:
            caixa_ini = caixa_final_anterior + entrada
        veks = Decimal(gasto_veks.get(m, 0) or 0)
        caixa_fim = (caixa_ini - veks).quantize(CENTAVO, ROUND_HALF_UP)
        linhas.append({
            "mes": m, "medicao": med, "fat_anterior": fat_anterior,
            "imposto": imp, "entrada": entrada,
            "caixa_inicial": caixa_ini, "gasto_veks": veks, "caixa_final": caixa_fim,
        })
        fat_anterior = Decimal(fat_direto.get(m, 0) or 0)
        caixa_final_anterior = caixa_fim
    return {
        "linhas": linhas,
        "lucro_em_caixa": linhas[-1]["caixa_final"] if linhas else Decimal("0"),
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
            razao_veks = (veks / previsto_total) if previsto_total else Decimal("0")
            razao_fat = (fat / previsto_total) if previsto_total else Decimal("0")
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
                    # precisão cheia de propósito; quantizado só ao entrar em calcular_fluxo_caixa
                    meses_veks[mes] = meses_veks.get(mes, Decimal("0")) + (parcela * razao_veks)
                    meses_fat[mes] = meses_fat.get(mes, Decimal("0")) + (parcela * razao_fat)
            # fração de resumo por raiz = peso da raiz / Σpeso (fallback igual)
            soma_peso = sum((p for _, p in peso_por_raiz.values()), Decimal("0"))
            n_raizes = len(peso_por_raiz)
            resumo_por_raiz = []
            for et, peso_raiz in peso_por_raiz.values():
                frac = (peso_raiz / soma_peso) if soma_peso > 0 else (Decimal("1") / n_raizes)
                resumo_por_raiz.append((et, frac))

        # distribui os agregados de resumo entre as raízes pela fração
        for et, frac in resumo_por_raiz:
            # Rastreia o OSC de origem da etapa: se uma única OSC alimenta a
            # etapa, guarda seu id (para casar com realizado_por_etapa); se
            # múltiplas OSCs convergem na mesma etapa, marca como None.
            if "osc_id" not in et:
                et["osc_id"] = osc.id
            elif et["osc_id"] != osc.id:
                et["osc_id"] = None
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


def fluxo_caixa(obra, dados=None):
    """Fluxo de caixa recalculado: medições (por mês) + Veks/Fat faseados pelo
    cronograma. imposto_pct vem do snapshot/contrato (default 0.135)."""
    dados = dados if dados is not None else montar_fisico_financeiro(obra.id, obra.admin_id)
    medicao = _medicao_por_mes(obra)
    veks = {k: Decimal(v) for k, v in dados["meses_veks"].items()}
    fat = {k: Decimal(v) for k, v in dados["meses_fat"].items()}
    meses = sorted(set(medicao) | set(veks) | set(fat))
    imposto_pct = _imposto_pct(obra)
    res = calcular_fluxo_caixa(meses, medicao, fat, veks, imposto_pct)
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
    imposto = (venda * _imposto_pct(obra)).quantize(CENTAVO, ROUND_HALF_UP)
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
    imposto = (venda * _imposto_pct(obra)).quantize(CENTAVO, ROUND_HALF_UP)
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
        })

    return {
        "kpis": {**k, "verba_disponivel": resumo.get("verba_disponivel", 0),
                 "custo_realizado": resumo.get("total_realizado", 0)},
        "etapas": etapas,
        "curva_s": {"meses": meses, "recebido_liquido": receb_ac,
                    "gasto_veks": gasto_ac, "lucro": lucro_ac, "realizado": real_ac},
        "caixa": caixa,
        "medicoes": meds,
        "doughnut": {"veks": dados["totais"]["veks"], "fat": dados["totais"]["fat_direto"]},
        "divergencia": div,
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
