"""Read-model do Resultado por Atividade (Fatia 1 — só Mão de Obra).

Calcula, a partir das fontes que já existem (sem migration):
  - valor_agregado_atividade   : a receber pela produção feita
  - custo_mo_atividade         : custo onerado real de MO rateado por horas (D1)
  - resultado_realizado_atividade = agregado − custo MO
  - custo_orcado_unitario      : custo orçado por unidade de serviço (genérico por tipo, DC5)
  - custo_mo_orcado_atividade  : MO orçada (composicao_snapshot × quantidade × peso)
  - alarme_mo                  : real vs orçado-para-o-avanço, em R$ (D5 primário)
  - indice_horas               : refino, só onde a MO foi orçada em hora
  - resultado_obra             : rollup por atividade / serviço / obra

O peso Serviço→Atividade é o da medição (ItemMedicaoCronogramaTarefa.peso) — D6,
fonte única de verdade. Nada é gravado: tudo é computado sob demanda (DC1).

Cadeia atividade→orçamento (confirmada no código):
  TarefaCronograma → ItemMedicaoCronogramaTarefa (cronograma_tarefa_id)
  → ItemMedicaoComercial (item_medicao_id; valor_comercial, quantidade, proposta_item_id)
  → Proposta? NÃO: → PropostaItem (proposta_item_id) → composicao_snapshot.
"""
from collections import defaultdict
from decimal import Decimal, ROUND_HALF_UP

from app import db
from models import (
    TarefaCronograma, ItemMedicaoComercial, ItemMedicaoCronogramaTarefa,
    PropostaItem, RDOMaoObra, RDOCustoDiario, RDO,
    GestaoCustoFilho, GestaoCustoPai,
)

# Categorias do ledger que JÁ são MO (lidas do RDOCustoDiario, D1) — o read-model
# NÃO as soma de novo a partir do GestaoCustoFilho, senão a folha contaria 2x (DC3).
_CATEGORIAS_MO = {'SALARIO', 'MAO_OBRA_DIRETA', 'VALE_ALIMENTACAO', 'VALE_TRANSPORTE'}

CEM = Decimal('100')
CENTAVO = Decimal('0.01')
MILESIMO = Decimal('0.001')


def _D(x):
    """Converte qualquer numérico/None para Decimal de forma segura."""
    return Decimal(str(x)) if x is not None else Decimal('0')


def _q(d):
    return d.quantize(CENTAVO, rounding=ROUND_HALF_UP)


# ── helpers reutilizáveis (DC6/DC8 — usados também pelas fatias seguintes) ─────

def _soma_peso_item(item_id):
    """Soma dos pesos de todas as tarefas vinculadas ao item de medição (D6).
    É o denominador da normalização do peso."""
    total = (
        db.session.query(
            db.func.coalesce(db.func.sum(ItemMedicaoCronogramaTarefa.peso), 0)
        )
        .filter(ItemMedicaoCronogramaTarefa.item_medicao_id == item_id)
        .scalar()
    )
    return _D(total)


def _links_da_tarefa(tarefa):
    """Vínculos (item_medicao, peso) desta atividade."""
    return (
        ItemMedicaoCronogramaTarefa.query
        .filter_by(cronograma_tarefa_id=tarefa.id)
        .all()
    )


def _horas_func_no_rdo(rdo_id, func_id):
    """Total de horas que um funcionário lançou num RDO (todas as atividades).
    Denominador do rateio do custo onerado (DC6 — a Fatia 2 reusa este helper)."""
    return _D(
        db.session.query(
            db.func.coalesce(db.func.sum(RDOMaoObra.horas_trabalhadas), 0)
        )
        .filter(RDOMaoObra.rdo_id == rdo_id, RDOMaoObra.funcionario_id == func_id)
        .scalar()
    )


# ── venda / valor agregado ────────────────────────────────────────────────────

def valor_agregado_atividade(tarefa):
    """Valor a receber pela produção já feita nesta atividade.
    = (percentual_concluido/100) × peso_norm × valor_comercial, somado sobre os
    itens de medição a que a atividade está vinculada (D6)."""
    perc = _D(tarefa.percentual_concluido) / CEM
    total = Decimal('0')
    for link in _links_da_tarefa(tarefa):
        item = db.session.get(ItemMedicaoComercial, link.item_medicao_id)
        if not item:
            continue
        soma_peso = _soma_peso_item(item.id)
        if soma_peso <= 0:
            continue
        peso_norm = _D(link.peso) / soma_peso
        total += perc * peso_norm * _D(item.valor_comercial)
    return _q(total)


# ── custo de MO incorrido (D1) ────────────────────────────────────────────────

def custo_mo_atividade(tarefa):
    """Custo de MO incorrido nesta atividade (D1): para cada (RDO, funcionário)
    que apontou horas na atividade, rateia o custo onerado real daquele RDO
    (RDOCustoDiario.custo_total_dia) pela fração de horas do funcionário gastas
    na atividade naquele RDO. Soma sobre todos os RDOs."""
    horas_ativ = defaultdict(Decimal)        # (rdo_id, func_id) -> horas na atividade
    for mo in RDOMaoObra.query.filter_by(tarefa_cronograma_id=tarefa.id).all():
        horas_ativ[(mo.rdo_id, mo.funcionario_id)] += _D(mo.horas_trabalhadas)

    total = Decimal('0')
    for (rdo_id, func_id), h_ativ in horas_ativ.items():
        h_total = _horas_func_no_rdo(rdo_id, func_id)
        if h_total <= 0:
            continue
        custo = (
            RDOCustoDiario.query
            .filter_by(rdo_id=rdo_id, funcionario_id=func_id)
            .first()
        )
        if not custo:
            continue
        total += _D(custo.custo_total_dia) * (h_ativ / h_total)
    return _q(total)


# ── custo NÃO-MO incorrido (Fatia 2: material/alimentação/transporte/subempreitada) ──

def _horas_obra_no_dia(obra_id, data):
    """Hora-homem total apontada na obra num dia (denominador do rateio, DC6)."""
    return _D(
        db.session.query(db.func.coalesce(db.func.sum(RDOMaoObra.horas_trabalhadas), 0))
        .join(RDO, RDO.id == RDOMaoObra.rdo_id)
        .filter(RDO.obra_id == obra_id, RDO.data_relatorio == data)
        .scalar()
    )


def _horas_atividade_no_dia(tarefa_id, data):
    """Hora-homem apontada nesta atividade num dia (numerador do rateio)."""
    return _D(
        db.session.query(db.func.coalesce(db.func.sum(RDOMaoObra.horas_trabalhadas), 0))
        .join(RDO, RDO.id == RDOMaoObra.rdo_id)
        .filter(RDOMaoObra.tarefa_cronograma_id == tarefa_id, RDO.data_relatorio == data)
        .scalar()
    )


def custo_nao_mo_atividade(tarefa):
    """Custo não-MO da atividade (Fatia 2):
      (a) DIRETO: lançamentos do ledger com `tarefa_cronograma_id == tarefa.id`;
      (b) COMPARTILHADO: lançamentos do dia sem atividade, rateados pela fração de
          hora-homem da atividade naquele dia (DC6).
    Exclui as categorias de MO (DC3) — elas já vêm do RDOCustoDiario (custo_mo)."""
    total = Decimal('0')
    rows = (
        db.session.query(GestaoCustoFilho, GestaoCustoPai.tipo_categoria)
        .join(GestaoCustoPai, GestaoCustoFilho.pai_id == GestaoCustoPai.id)
        .filter(GestaoCustoFilho.obra_id == tarefa.obra_id)
        .filter(~GestaoCustoPai.tipo_categoria.in_(_CATEGORIAS_MO))
        .all()
    )
    for filho, _cat in rows:
        if filho.tarefa_cronograma_id == tarefa.id:
            total += _D(filho.valor)                         # (a) direto
        elif filho.tarefa_cronograma_id is None:
            dia = filho.data_referencia
            h_obra = _horas_obra_no_dia(tarefa.obra_id, dia)
            if h_obra > 0:
                frac = _horas_atividade_no_dia(tarefa.id, dia) / h_obra
                total += _D(filho.valor) * frac              # (b) rateio
        # lançamento de OUTRA atividade → ignora
    return _q(total)


def custo_incorrido_atividade(tarefa):
    """Custo incorrido total da atividade = MO (D1) + não-MO (Fatia 2)."""
    return _q(custo_mo_atividade(tarefa) + custo_nao_mo_atividade(tarefa))


def resultado_realizado_atividade(tarefa):
    """Resultado (competência) da atividade = Valor agregado − Custo incorrido total
    (MO + material/alimentação/transporte/subempreitada). Assinatura estável."""
    return _q(valor_agregado_atividade(tarefa) - custo_incorrido_atividade(tarefa))


# ── custo orçado a partir do snapshot da composição (DC5) ─────────────────────

def custo_orcado_unitario(composicao_snapshot, tipos=None):
    """Custo orçado por UMA unidade de serviço, somando subtotal_unitario das
    linhas cujo tipo está em `tipos` (None = todos). Função pura."""
    total = Decimal('0')
    for linha in (composicao_snapshot or []):
        tp = (linha.get('tipo') or '').upper()
        if tipos is None or tp in tipos:
            total += _D(linha.get('subtotal_unitario'))
    return total


def custo_mo_orcado_unitario(composicao_snapshot):
    """Caso particular de custo_orcado_unitario para MAO_OBRA."""
    return custo_orcado_unitario(composicao_snapshot, {'MAO_OBRA'})


def custo_mo_orcado_atividade(tarefa):
    """MO orçada alocada à atividade = Σ_itens (MO/un × quantidade × peso_norm).
    quantidade vem do ItemMedicaoComercial (fallback PropostaItem)."""
    total = Decimal('0')
    for link in _links_da_tarefa(tarefa):
        item = db.session.get(ItemMedicaoComercial, link.item_medicao_id)
        if not item or not item.proposta_item_id:
            continue
        pi = db.session.get(PropostaItem, item.proposta_item_id)
        if not pi:
            continue
        soma_peso = _soma_peso_item(item.id)
        if soma_peso <= 0:
            continue
        mo_unit = custo_mo_orcado_unitario(pi.composicao_snapshot)
        qtd = _D(item.quantidade) if item.quantidade is not None else _D(pi.quantidade)
        peso_norm = _D(link.peso) / soma_peso
        total += mo_unit * qtd * peso_norm
    return _q(total)


# ── alarme primário em R$ (D5) ────────────────────────────────────────────────

def alarme_mo(tarefa):
    """Alarme primário em R$ (D5): compara o custo MO real incorrido com o custo
    MO orçado para o avanço atual. Vale para qualquer modelo de precificação."""
    perc = _D(tarefa.percentual_concluido) / CEM
    orcado_total = custo_mo_orcado_atividade(tarefa)
    orcado_para_avanco = _q(orcado_total * perc)
    real = custo_mo_atividade(tarefa)
    indice = None
    if real > 0:
        indice = (orcado_para_avanco / real).quantize(MILESIMO, rounding=ROUND_HALF_UP)
    return {
        'orcado_total': orcado_total,
        'orcado_para_avanco': orcado_para_avanco,
        'real': real,
        'estouro': real > orcado_para_avanco,
        'indice_rs': indice,   # <1 = no vermelho; None se sem custo real ainda
    }


def custo_orcado_atividade_por_tipos(tarefa, tipos=None):
    """Orçado (baseline) da atividade somando os tipos do snapshot pedidos
    (None = todos), via composicao_snapshot × quantidade × Peso da medição.
    Fonte = PropostaItem congelado (DC5/ADR 0005). `custo_mo_orcado_atividade`
    é o caso particular tipos={'MAO_OBRA'}."""
    total = Decimal('0')
    for link in _links_da_tarefa(tarefa):
        item = db.session.get(ItemMedicaoComercial, link.item_medicao_id)
        if not item or not item.proposta_item_id:
            continue
        pi = db.session.get(PropostaItem, item.proposta_item_id)
        if not pi:
            continue
        soma_peso = _soma_peso_item(item.id)
        if soma_peso <= 0:
            continue
        unit = custo_orcado_unitario(pi.composicao_snapshot, tipos)
        qtd = _D(item.quantidade) if item.quantidade is not None else _D(pi.quantidade)
        total += unit * qtd * (_D(link.peso) / soma_peso)
    return _q(total)


def alarme_custo(tarefa):
    """Alarme em R$ sobre o custo TOTAL (CPI da Fatia 3): orçado-para-o-avanço
    (baseline congelado, todos os tipos) vs custo incorrido total."""
    perc = _D(tarefa.percentual_concluido) / CEM
    orcado_total = custo_orcado_atividade_por_tipos(tarefa, None)
    orcado_para_avanco = _q(orcado_total * perc)
    real = custo_incorrido_atividade(tarefa)
    indice = None
    if real > 0:
        indice = (orcado_para_avanco / real).quantize(MILESIMO, rounding=ROUND_HALF_UP)
    return {
        'orcado_total': orcado_total,
        'orcado_para_avanco': orcado_para_avanco,
        'real': real,
        'estouro': real > orcado_para_avanco,
        'indice_rs': indice,
    }


# ── refino em horas (só onde a MO foi orçada em hora) ─────────────────────────

def horas_orcadas_unitarias(composicao_snapshot):
    """Horas orçadas por UMA unidade de serviço = Σ coeficiente das linhas
    MAO_OBRA com unidade 'h'. Retorna None se nenhuma linha de MO é horária."""
    total = Decimal('0')
    achou = False
    for linha in (composicao_snapshot or []):
        if (linha.get('tipo') or '').upper() == 'MAO_OBRA' and \
           (linha.get('unidade') or '').lower() == 'h':
            total += _D(linha.get('coeficiente'))
            achou = True
    return total if achou else None


def indice_horas(tarefa):
    """Refino do alarme (D5), só onde a MO foi orçada em hora. Índice =
    horas ganhas (avanço × horas orçadas) / horas reais apontadas.
    Retorna None quando a MO do item não tem insumo horário."""
    horas_orcadas = Decimal('0')
    tem_hora = False
    for link in _links_da_tarefa(tarefa):
        item = db.session.get(ItemMedicaoComercial, link.item_medicao_id)
        if not item or not item.proposta_item_id:
            continue
        pi = db.session.get(PropostaItem, item.proposta_item_id)
        if not pi:
            continue
        unit = horas_orcadas_unitarias(pi.composicao_snapshot)
        if unit is None:
            continue
        tem_hora = True
        soma_peso = _soma_peso_item(item.id)
        if soma_peso <= 0:
            continue
        qtd = _D(item.quantidade) if item.quantidade is not None else _D(pi.quantidade)
        peso_norm = _D(link.peso) / soma_peso
        horas_orcadas += unit * qtd * peso_norm

    if not tem_hora:
        return None

    perc = _D(tarefa.percentual_concluido) / CEM
    horas_ganhas = horas_orcadas * perc
    horas_reais = _D(
        db.session.query(
            db.func.coalesce(db.func.sum(RDOMaoObra.horas_trabalhadas), 0)
        )
        .filter(RDOMaoObra.tarefa_cronograma_id == tarefa.id)
        .scalar()
    )
    indice = None
    if horas_reais > 0:
        indice = (horas_ganhas / horas_reais).quantize(MILESIMO, rounding=ROUND_HALF_UP)
    return {
        'horas_orcadas': _q(horas_orcadas),
        'horas_ganhas': _q(horas_ganhas),
        'horas_reais': _q(horas_reais),
        'indice': indice,
    }


# ── rollup atividade → serviço → obra ─────────────────────────────────────────

def _folhas_da_obra(obra_id):
    """Atividades-folha (sem filhas) da obra — os centros de custo reais.
    Grupos (que têm filhas) são agregação, não recebem apontamento direto."""
    tarefas = TarefaCronograma.query.filter_by(obra_id=obra_id).all()
    pais = {t.tarefa_pai_id for t in tarefas if t.tarefa_pai_id is not None}
    return [t for t in tarefas if t.id not in pais]


def resultado_obra(obra_id):
    """Rollup do Resultado da obra a partir das atividades-folha. Retorna o
    detalhe por atividade + totais por serviço + totais da obra."""
    atividades = []
    por_servico = defaultdict(lambda: {
        'valor_agregado': Decimal('0'), 'custo_mo': Decimal('0'),
        'custo_nao_mo': Decimal('0'), 'custo_incorrido': Decimal('0'),
        'resultado': Decimal('0'),
    })
    tot_agregado = Decimal('0')
    tot_mo = Decimal('0')
    tot_nao_mo = Decimal('0')

    for t in _folhas_da_obra(obra_id):
        agregado = valor_agregado_atividade(t)
        custo_mo = custo_mo_atividade(t)
        custo_nao_mo = custo_nao_mo_atividade(t)
        incorrido = _q(custo_mo + custo_nao_mo)
        resultado = _q(agregado - incorrido)
        atividades.append({
            'tarefa_id': t.id,
            'nome': t.nome_tarefa,
            'servico_id': t.servico_id,
            'percentual_concluido': float(t.percentual_concluido or 0),
            'quantidade_total': float(t.quantidade_total or 0),
            'valor_agregado': agregado,
            'custo_mo': custo_mo,
            'custo_nao_mo': custo_nao_mo,
            'custo_incorrido': incorrido,
            'resultado': resultado,
            'alarme': alarme_mo(t),
            'alarme_custo': alarme_custo(t),
            'indice_horas': indice_horas(t),
        })
        chave = t.servico_id or 0
        por_servico[chave]['valor_agregado'] += agregado
        por_servico[chave]['custo_mo'] += custo_mo
        por_servico[chave]['custo_nao_mo'] += custo_nao_mo
        por_servico[chave]['custo_incorrido'] += incorrido
        por_servico[chave]['resultado'] += resultado
        tot_agregado += agregado
        tot_mo += custo_mo
        tot_nao_mo += custo_nao_mo

    tot_incorrido = tot_mo + tot_nao_mo
    return {
        'obra_id': obra_id,
        'atividades': atividades,
        'por_servico': {k: {kk: _q(vv) for kk, vv in v.items()}
                        for k, v in por_servico.items()},
        'valor_agregado': _q(tot_agregado),
        'custo_mo': _q(tot_mo),
        'custo_nao_mo': _q(tot_nao_mo),
        'custo_incorrido': _q(tot_incorrido),
        'resultado': _q(tot_agregado - tot_incorrido),
    }


# ── Fatia 3 — EVM (previsão): CPI / SPI / EAC / resultado projetado ───────────
# Reúso (DC7): CPI = alarme_custo (EV/AC); SPI = cronograma_engine; BAC custo =
# orçado baseline; venda = venda_total_atividade. Puro cálculo, sem migration.

def venda_total_atividade(tarefa):
    """Venda (valor_comercial) alocada à atividade pelo Peso da medição,
    independente do avanço — o BAC de receita da atividade."""
    total = Decimal('0')
    for link in _links_da_tarefa(tarefa):
        item = db.session.get(ItemMedicaoComercial, link.item_medicao_id)
        if not item:
            continue
        soma_peso = _soma_peso_item(item.id)
        if soma_peso <= 0:
            continue
        total += (_D(link.peso) / soma_peso) * _D(item.valor_comercial)
    return _q(total)


def evm_atividade(tarefa, admin_id, data_ref=None):
    """Earned Value por atividade.
      CPI = EV/AC (reusa alarme_custo); SPI = realizado/planejado (cronograma_engine);
      EAC = BAC_custo / CPI; resultado projetado = venda − EAC.
    SPI fica None quando a atividade não tem baseline de prazo (sem data_inicio —
    vem do export do Projeto1.mpp)."""
    from datetime import date as _date
    from utils.cronograma_engine import calcular_progresso_rdo
    data_ref = data_ref or _date.today()

    a = alarme_custo(tarefa)
    bac = a['orcado_total']          # BAC de custo (baseline congelado)
    ev = a['orcado_para_avanco']     # Earned Value
    ac = a['real']                   # Actual Cost (incorrido)
    cpi = a['indice_rs']             # EV/AC (None se AC=0)

    prog = calcular_progresso_rdo(tarefa.id, data_ref, admin_id)
    plan_raw = prog.get('percentual_planejado')
    plan = _D(plan_raw)
    real = _D(prog.get('percentual_realizado'))
    spi = (real / plan).quantize(MILESIMO, rounding=ROUND_HALF_UP) if plan > 0 else None

    eac = (bac / cpi).quantize(CENTAVO, rounding=ROUND_HALF_UP) if (cpi and cpi > 0) else None
    venda = venda_total_atividade(tarefa)
    resultado_proj = _q(venda - eac) if eac is not None else None

    return {
        'bac_custo': bac, 'ev': ev, 'ac': ac, 'cpi': cpi, 'spi': spi, 'eac': eac,
        'venda_total': venda, 'resultado_projetado': resultado_proj,
        'percentual_planejado': plan_raw,
        'percentual_realizado': float(real),
    }


def evm_obra(obra_id, admin_id, data_ref=None):
    """Rollup EVM da obra: soma BAC/EV/AC/venda das folhas; CPI da obra = ΣEV/ΣAC;
    SPI da obra do cronograma_engine; EAC e resultado projetado da obra."""
    from datetime import date as _date
    from utils.cronograma_engine import calcular_progresso_geral_obra_v2
    data_ref = data_ref or _date.today()

    bac = ev = ac = venda = Decimal('0')
    itens = []
    for t in _folhas_da_obra(obra_id):
        e = evm_atividade(t, admin_id, data_ref)
        bac += e['bac_custo']; ev += e['ev']; ac += e['ac']; venda += e['venda_total']
        itens.append({'tarefa_id': t.id, 'nome': t.nome_tarefa, **e})

    cpi = (ev / ac).quantize(MILESIMO, rounding=ROUND_HALF_UP) if ac > 0 else None
    agg = calcular_progresso_geral_obra_v2(obra_id, data_ref, admin_id)
    plan = _D(agg.get('progresso_planejado_pct'))
    realz = _D(agg.get('progresso_geral_pct'))
    spi = (realz / plan).quantize(MILESIMO, rounding=ROUND_HALF_UP) if plan > 0 else None
    eac = (bac / cpi).quantize(CENTAVO, rounding=ROUND_HALF_UP) if (cpi and cpi > 0) else None

    return {
        'obra_id': obra_id, 'itens': itens,
        'bac_custo': _q(bac), 'ev': _q(ev), 'ac': _q(ac), 'venda_total': _q(venda),
        'cpi': cpi, 'spi': spi, 'eac': eac,
        'resultado_projetado': _q(venda - eac) if eac is not None else None,
    }
