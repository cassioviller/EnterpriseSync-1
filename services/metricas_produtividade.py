"""
services/metricas_produtividade.py — Task #3

Métricas de Produtividade e Lucratividade por RDO.

Funções puras que recebem período/filtros e retornam agregados.
Fonte de dados:
  - Custo do funcionário: RDOCustoDiario (Task #2)
  - Receita/orçamento operacional: obter_operacional_vigente (Task #1)
  - Produção: RDOServicoSubatividade.quantidade_produzida
  - Vínculo papel↔composicao: RDOMaoObra.composicao_servico_id + vinculo_status

Fórmulas canônicas (conforme especificação Task #3):
  custo_dia = componente_folha + componente_extra + componente_va + componente_vt
  custo_hora_real = custo_dia / horas_lancadas_no_dia
  custo_dele_na_sub = custo_dia × (horas_dele_na_sub / horas_dele_no_rdo)
  producao_esperada = MIN(horas_papel / coef_papel) para cada papel
  indice_equipe = quantidade_produzida / producao_esperada × 100
  papel_gargalo = papel com min(capacidade_papel)
  folga(papel) = capacidade − producao_esperada
  alerta_subutilizado: folga / capacidade >= 0.30
  esforco_esperado_papel = coef_papel × quantidade_produzida
  receita_dele = receita_liq_total × (esforco_papel / total_esforco)
                              × (horas_dele / horas_totais_papel)
  lucro_real_dele = receita_dele − custo_dele_na_sub
"""
from __future__ import annotations

import logging
from collections import defaultdict
from datetime import date, datetime, timedelta
from decimal import Decimal
from typing import Optional

logger = logging.getLogger(__name__)

_VINCULOS_CONFIRMADOS = ('auto', 'manual')


# ─────────────────────────────────────────────────────────────────────────────
# Helpers internos
# ─────────────────────────────────────────────────────────────────────────────

def _d(v, default=0.0) -> float:
    if v is None:
        return default
    try:
        return float(v)
    except (TypeError, ValueError):
        return default


def _dias_uteis_periodo(data_inicio: date, data_fim: date) -> int:
    """Conta dias úteis (seg–sex) no intervalo fechado [data_inicio, data_fim]."""
    total = 0
    cur = data_inicio
    while cur <= data_fim:
        if cur.weekday() < 5:
            total += 1
        cur += timedelta(days=1)
    return total


def _receita_liquida_unit(composicao_snap: list, margem_pct, imposto_pct) -> Optional[float]:
    """Receita líquida por unidade produzida, a partir do snapshot operacional.

    Fórmula:
      custo_unit = Σ(coef × preco_unitario)
      divisor    = 1 − margem/100 − imposto/100
      preco_venda = custo_unit / divisor
      receita_liq_unit = preco_venda × (1 − imposto/100)

    Retorna None se divisor ≤ 0 ou composição vazia.
    """
    snap = composicao_snap or []
    custo_unit = sum(
        _d(l.get('coeficiente')) * _d(l.get('preco_unitario'))
        for l in snap
    )
    if custo_unit == 0:
        return None
    margem = _d(margem_pct)
    imposto = _d(imposto_pct)
    divisor = 1.0 - margem / 100.0 - imposto / 100.0
    if divisor <= 0:
        return None
    preco_venda = custo_unit / divisor
    return preco_venda * (1.0 - imposto / 100.0)


def _coef_papel_do_snapshot(composicao_snap: list, composicao_servico_id: int) -> Optional[float]:
    """Retorna coeficiente do papel (pelo insumo_id) dentro do snapshot.

    O snapshot armazena insumo_id e coeficiente. Como composicao_servico_id
    mapeia para um (servico_id, insumo_id) via ComposicaoServico, precisamos
    fazer lookup no DB apenas quando necessário.
    """
    return None  # ver _get_coef_papel que faz lookup no DB


def _get_operacional_cache(cache: dict, obra_id: int, servico_id: int, data_ref: date):
    """Busca e cacheia o item operacional vigente para (obra_id, servico_id, data)."""
    key = (obra_id, servico_id, data_ref)
    if key in cache:
        return cache[key]

    try:
        from models import ObraOrcamentoOperacional, ObraOrcamentoOperacionalItem
        from services.orcamento_operacional import obter_operacional_vigente
        from app import db

        item = (
            ObraOrcamentoOperacionalItem.query
            .join(ObraOrcamentoOperacional,
                  ObraOrcamentoOperacionalItem.operacional_id == ObraOrcamentoOperacional.id)
            .filter(
                ObraOrcamentoOperacional.obra_id == obra_id,
                ObraOrcamentoOperacionalItem.servico_id == servico_id,
            )
            .first()
        )
        if not item:
            cache[key] = None
            return None

        dt = datetime.combine(data_ref, datetime.min.time())
        result = obter_operacional_vigente(obra_id, item.id, dt)
        cache[key] = result
    except Exception:
        logger.exception("_get_operacional_cache falhou obra=%s servico=%s", obra_id, servico_id)
        cache[key] = None

    return cache[key]


def _get_coef_papel(composicao_servico_id: int, coef_cache: dict) -> float:
    """Retorna coeficiente da linha ComposicaoServico."""
    if composicao_servico_id in coef_cache:
        return coef_cache[composicao_servico_id]
    try:
        from models import ComposicaoServico
        cs = ComposicaoServico.query.get(composicao_servico_id)
        v = float(cs.coeficiente) if cs else 0.0
    except Exception:
        v = 0.0
    coef_cache[composicao_servico_id] = v
    return v


def _get_insumo_nome(composicao_servico_id: int, nome_cache: dict) -> str:
    """Retorna nome do insumo (papel) da linha ComposicaoServico."""
    if composicao_servico_id in nome_cache:
        return nome_cache[composicao_servico_id]
    try:
        from models import ComposicaoServico
        cs = ComposicaoServico.query.get(composicao_servico_id)
        nome = cs.insumo.nome if cs and cs.insumo else f'Papel #{composicao_servico_id}'
    except Exception:
        nome = f'Papel #{composicao_servico_id}'
    nome_cache[composicao_servico_id] = nome
    return nome


# ─────────────────────────────────────────────────────────────────────────────
# Carga principal de dados
# ─────────────────────────────────────────────────────────────────────────────

def _carregar_dados_periodo(admin_id: int, data_inicio: date, data_fim: date,
                            obra_ids=None, funcao_ids=None) -> list:
    """Carrega e estrutura todos os dados de RDO/MO/custo para o período.

    Retorna lista de registros-por-linha de mão-de-obra, cada um com:
    {
        'rdo_id', 'rdo_data', 'rdo_obra_id', 'rdo_numero',
        'sub_id', 'sub_servico_id', 'sub_servico_nome', 'sub_unidade',
        'sub_quantidade_produzida',
        'mo_id', 'mo_func_id', 'mo_func_nome', 'mo_funcao_exercida',
        'mo_horas', 'mo_extras', 'mo_composicao_id', 'mo_vinculo_status',
        'custo_total_dia', 'custo_horas_neste_rdo',  # totais para rateio
    }
    Caches de operacional, coeficiente e nome são devolvidos separadamente.
    """
    from models import (
        RDO, RDOMaoObra, RDOServicoSubatividade, RDOCustoDiario,
        Funcionario, Servico,
    )
    from app import db

    # 1) Buscar todos os RDOs do tenant no período (apenas Finalizado)
    q = (
        db.session.query(RDO)
        .filter(
            RDO.admin_id == admin_id,
            RDO.data_relatorio >= data_inicio,
            RDO.data_relatorio <= data_fim,
            RDO.status == 'Finalizado',
        )
    )
    if obra_ids:
        q = q.filter(RDO.obra_id.in_(obra_ids))
    rdos = q.all()

    if not rdos:
        return []

    rdo_ids = [r.id for r in rdos]
    rdo_map = {r.id: r for r in rdos}

    # 2) RDOMaoObra
    mos = RDOMaoObra.query.filter(
        RDOMaoObra.rdo_id.in_(rdo_ids),
        RDOMaoObra.admin_id == admin_id,
    ).all()
    if funcao_ids:
        mos = [mo for mo in mos if mo.funcionario and
               getattr(mo.funcionario, 'funcao_id', None) in funcao_ids]

    # 3) RDOServicoSubatividade
    subs = RDOServicoSubatividade.query.filter(
        RDOServicoSubatividade.rdo_id.in_(rdo_ids),
        RDOServicoSubatividade.ativo.is_(True),
    ).all()
    sub_map = {s.id: s for s in subs}

    # 4) RDOCustoDiario
    custos = RDOCustoDiario.query.filter(
        RDOCustoDiario.rdo_id.in_(rdo_ids),
        RDOCustoDiario.admin_id == admin_id,
    ).all()
    custo_map = {(c.rdo_id, c.funcionario_id): c for c in custos}

    # 5) Servicos
    servico_ids = {s.servico_id for s in subs if s.servico_id}
    servicos = {s.id: s for s in Servico.query.filter(Servico.id.in_(servico_ids)).all()} if servico_ids else {}

    # 6) Funcionarios
    func_ids_set = {mo.funcionario_id for mo in mos}
    funcs = {f.id: f for f in Funcionario.query.filter(Funcionario.id.in_(func_ids_set)).all()} if func_ids_set else {}

    # 7) Horas por funcionario por RDO (para rateio dentro do RDO)
    horas_func_rdo = defaultdict(float)  # (rdo_id, func_id) -> total horas neste rdo
    for mo in mos:
        horas_func_rdo[(mo.rdo_id, mo.funcionario_id)] += _d(mo.horas_trabalhadas)

    # 8) Montar registros
    registros = []
    for mo in mos:
        rdo = rdo_map.get(mo.rdo_id)
        if not rdo:
            continue

        sub = sub_map.get(mo.subatividade_id) if mo.subatividade_id else None
        custo_dia = custo_map.get((mo.rdo_id, mo.funcionario_id))
        func = funcs.get(mo.funcionario_id)
        servico = servicos.get(sub.servico_id) if sub and sub.servico_id else None

        horas_neste_rdo = horas_func_rdo.get((mo.rdo_id, mo.funcionario_id), 0.0)

        registros.append({
            'rdo_id': rdo.id,
            'rdo_data': rdo.data_relatorio,
            'rdo_obra_id': rdo.obra_id,
            'rdo_numero': rdo.numero_rdo,
            'sub_id': sub.id if sub else None,
            'sub_servico_id': sub.servico_id if sub else None,
            'sub_servico_nome': servico.nome if servico else (sub.nome_subatividade if sub else ''),
            'sub_unidade': servico.unidade_medida if servico else '',
            'sub_quantidade_produzida': _d(sub.quantidade_produzida) if sub else None,
            'mo_id': mo.id,
            'mo_func_id': mo.funcionario_id,
            'mo_func_nome': func.nome if func else f'Func#{mo.funcionario_id}',
            'mo_funcao_id': getattr(func, 'funcao_id', None) if func else None,
            'mo_funcao_exercida': mo.funcao_exercida,
            'mo_horas': _d(mo.horas_trabalhadas),
            'mo_extras': _d(mo.horas_extras),
            'mo_composicao_id': mo.composicao_servico_id,
            'mo_vinculo_status': mo.vinculo_status,
            'custo_total_dia': _d(custo_dia.custo_total_dia) if custo_dia else None,
            'horas_func_neste_rdo': horas_neste_rdo,
        })
    return registros


# ─────────────────────────────────────────────────────────────────────────────
# Cálculo por subatividade (unidade de análise base)
# ─────────────────────────────────────────────────────────────────────────────

def _calcular_metricas_subatividade(regs_sub: list, op_cache: dict,
                                     coef_cache: dict, nome_cache: dict) -> dict:
    """Calcula métricas para um conjunto de registros de uma mesma subatividade+RDO.

    regs_sub: lista de registros do mesmo (rdo_id, sub_id).
    Retorna dict com métricas calculadas.
    """
    if not regs_sub:
        return {}

    r0 = regs_sub[0]
    obra_id = r0['rdo_obra_id']
    servico_id = r0['sub_servico_id']
    data_ref = r0['rdo_data']
    qtd = r0['sub_quantidade_produzida']

    # ── Papéis (grupos por composicao_servico_id) ──────────────────────────
    papeis: dict[int, dict] = {}
    for r in regs_sub:
        cid = r['mo_composicao_id']
        if cid not in papeis:
            papeis[cid] = {
                'composicao_id': cid,
                'nome': _get_insumo_nome(cid, nome_cache) if cid else r['mo_funcao_exercida'],
                'horas': 0.0,
                'funcs': set(),
                'vinculo_confirmado_horas': 0.0,
            }
        papeis[cid]['horas'] += r['mo_horas']
        papeis[cid]['funcs'].add(r['mo_func_id'])
        if r['mo_vinculo_status'] in _VINCULOS_CONFIRMADOS:
            papeis[cid]['vinculo_confirmado_horas'] += r['mo_horas']

    total_hh = sum(p['horas'] for p in papeis.values())
    total_hh_confirmado = sum(p['vinculo_confirmado_horas'] for p in papeis.values())
    cobertura_pct = (total_hh_confirmado / total_hh * 100) if total_hh > 0 else 0.0

    # ── Modo: single_role vs equipe_mista ──────────────────────────────────
    papeis_validos = {k: v for k, v in papeis.items() if k is not None}
    modo = 'single_role' if len(papeis_validos) <= 1 else 'equipe_mista'

    # ── Produção esperada (gargalo) ─────────────────────────────────────────
    producao_esperada = None
    papel_gargalo_id = None
    papel_gargalo_nome = None
    papel_subutilizado_nome = None
    papeis_capacidade = {}

    for cid, p in papeis_validos.items():
        coef = _get_coef_papel(cid, coef_cache) if cid else 0.0
        if coef > 0:
            capacidade = p['horas'] / coef
            papeis_capacidade[cid] = capacidade

    if papeis_capacidade:
        min_cap = min(papeis_capacidade.values())
        producao_esperada = min_cap
        papel_gargalo_id = min(papeis_capacidade, key=papeis_capacidade.get)
        papel_gargalo_nome = nome_cache.get(papel_gargalo_id, f'Papel#{papel_gargalo_id}')

        # Papel subutilizado: folga/capacidade >= 0.30
        for cid, cap in papeis_capacidade.items():
            folga = cap - min_cap
            if cap > 0 and folga / cap >= 0.30:
                papel_subutilizado_nome = nome_cache.get(cid, f'Papel#{cid}')
                break

    # ── Índice equipe ───────────────────────────────────────────────────────
    indice_equipe = None
    if qtd is not None and producao_esperada and producao_esperada > 0:
        indice_equipe = qtd / producao_esperada * 100

    # ── Receita líquida total ───────────────────────────────────────────────
    receita_liq_total = None
    op = None
    if servico_id:
        op = _get_operacional_cache(op_cache, obra_id, servico_id, data_ref)
    if op and qtd and qtd > 0:
        rl_unit = _receita_liquida_unit(op['composicao'], op.get('margem_pct'), op.get('imposto_pct'))
        if rl_unit is not None:
            receita_liq_total = rl_unit * qtd

    # ── Esforço por papel (para rateio de receita) ──────────────────────────
    esforco_por_papel: dict[int, float] = {}
    total_esforco = 0.0
    if qtd and qtd > 0:
        for cid, p in papeis_validos.items():
            coef = _get_coef_papel(cid, coef_cache) if cid else 0.0
            esf = coef * qtd
            esforco_por_papel[cid] = esf
            total_esforco += esf

    # ── Custo e receita por funcionário ────────────────────────────────────
    func_metricas: dict[int, dict] = {}
    for r in regs_sub:
        fid = r['mo_func_id']
        cid = r['mo_composicao_id']
        if fid not in func_metricas:
            func_metricas[fid] = {
                'func_id': fid,
                'func_nome': r['mo_func_nome'],
                'funcao_id': r['mo_funcao_id'],
                'composicao_id': cid,
                'horas_na_sub': 0.0,
                'horas_no_rdo': r['horas_func_neste_rdo'],
                'custo_total_dia': r['custo_total_dia'],
                'custo_na_sub': None,
                'receita_dele': None,
                'lucro_dele': None,
                'modo': modo,
            }
        func_metricas[fid]['horas_na_sub'] += r['mo_horas']

    for fid, fm in func_metricas.items():
        horas_rdo = fm['horas_no_rdo']
        horas_sub = fm['horas_na_sub']
        custo_dia = fm['custo_total_dia']

        if custo_dia is not None and horas_rdo > 0:
            fm['custo_na_sub'] = custo_dia * (horas_sub / horas_rdo)

        # Receita rateada para este funcionário
        if receita_liq_total is not None and total_esforco > 0:
            cid = fm['composicao_id']
            esf_papel = esforco_por_papel.get(cid, 0.0)
            horas_totais_papel = papeis.get(cid, {}).get('horas', 0.0) if cid in papeis else 0.0
            if esf_papel > 0 and horas_totais_papel > 0:
                fm['receita_dele'] = (receita_liq_total
                                      * (esf_papel / total_esforco)
                                      * (horas_sub / horas_totais_papel))

        if fm['custo_na_sub'] is not None and fm['receita_dele'] is not None:
            fm['lucro_dele'] = fm['receita_dele'] - fm['custo_na_sub']

    return {
        'rdo_id': r0['rdo_id'],
        'rdo_data': data_ref,
        'rdo_numero': r0['rdo_numero'],
        'obra_id': obra_id,
        'sub_id': r0['sub_id'],
        'servico_id': servico_id,
        'servico_nome': r0['sub_servico_nome'],
        'unidade': r0['sub_unidade'],
        'quantidade_produzida': qtd,
        'total_hh': total_hh,
        'cobertura_pct': cobertura_pct,
        'modo': modo,
        'papeis': list(papeis.values()),
        'papeis_capacidade': papeis_capacidade,
        'producao_esperada': producao_esperada,
        'indice_equipe': indice_equipe,
        'papel_gargalo_id': papel_gargalo_id,
        'papel_gargalo_nome': papel_gargalo_nome,
        'papel_subutilizado_nome': papel_subutilizado_nome,
        'receita_liq_total': receita_liq_total,
        'tem_operacional': op is not None,
        'func_metricas': func_metricas,
        'total_custo': sum(
            fm['custo_na_sub'] for fm in func_metricas.values()
            if fm['custo_na_sub'] is not None
        ),
    }


# ─────────────────────────────────────────────────────────────────────────────
# API Pública
# ─────────────────────────────────────────────────────────────────────────────

def produtividade_por_servico(admin_id: int, data_inicio: date, data_fim: date,
                               obra_id: int = None) -> list:
    """Agrega métricas de produtividade por serviço no período.

    Retorna lista de dicts (um por serviço com ocorrências no período).
    """
    obra_ids = [obra_id] if obra_id else None
    regs = _carregar_dados_periodo(admin_id, data_inicio, data_fim, obra_ids=obra_ids)
    if not regs:
        return []

    op_cache: dict = {}
    coef_cache: dict = {}
    nome_cache: dict = {}

    # Agrupar por (rdo_id, sub_id)
    por_sub: dict = defaultdict(list)
    for r in regs:
        chave = (r['rdo_id'], r['sub_id'])
        por_sub[chave].append(r)

    # Calcular métricas por subatividade
    metricas_sub = []
    for chave, sub_regs in por_sub.items():
        m = _calcular_metricas_subatividade(sub_regs, op_cache, coef_cache, nome_cache)
        if m:
            metricas_sub.append(m)

    # Agregar por serviço
    por_servico: dict = defaultdict(lambda: {
        'servico_id': None,
        'servico_nome': '',
        'unidade': '',
        'total_hh': 0.0,
        'total_produzido': 0.0,
        'total_custo': 0.0,
        'total_receita': 0.0,
        'n_subs_com_qty': 0,
        'n_subs_sem_qty': 0,
        'cobertura_hh_confirmado': 0.0,
        'cobertura_hh_total': 0.0,
        'papeis_hh': defaultdict(float),  # composicao_id -> horas
        'papeis_coef': {},
        'papeis_nomes': {},
        'sub_indices': [],
        'gargalo_ocorrencias': defaultdict(int),
        'subutilizado_ocorrencias': defaultdict(int),
        'n_rdos': 0,
        'rdos_vistos': set(),
    })

    for m in metricas_sub:
        sid = m['servico_id']
        agg = por_servico[sid]
        agg['servico_id'] = sid
        agg['servico_nome'] = m['servico_nome']
        agg['unidade'] = m['unidade']
        agg['total_hh'] += m['total_hh']
        agg['cobertura_hh_total'] += m['total_hh']
        agg['cobertura_hh_confirmado'] += m['total_hh'] * m['cobertura_pct'] / 100.0

        if m['quantidade_produzida'] is not None:
            agg['total_produzido'] += m['quantidade_produzida']
            agg['n_subs_com_qty'] += 1
        else:
            agg['n_subs_sem_qty'] += 1

        agg['total_custo'] += m['total_custo'] or 0.0
        if m['receita_liq_total'] is not None:
            agg['total_receita'] += m['receita_liq_total']

        if m['rdo_id'] not in agg['rdos_vistos']:
            agg['rdos_vistos'].add(m['rdo_id'])
            agg['n_rdos'] += 1

        if m['indice_equipe'] is not None:
            agg['sub_indices'].append(m['indice_equipe'])

        if m['papel_gargalo_nome']:
            agg['gargalo_ocorrencias'][m['papel_gargalo_nome']] += 1

        if m['papel_subutilizado_nome']:
            agg['subutilizado_ocorrencias'][m['papel_subutilizado_nome']] += 1

        for p in m['papeis']:
            cid = p['composicao_id']
            agg['papeis_hh'][cid] = agg['papeis_hh'].get(cid, 0.0) + p['horas']
            if cid is not None:
                coef = _get_coef_papel(cid, coef_cache)
                nome = _get_insumo_nome(cid, nome_cache)
                agg['papeis_coef'][cid] = coef
                agg['papeis_nomes'][cid] = nome

    resultado = []
    for sid, agg in por_servico.items():
        total_hh = agg['total_hh']
        total_prod = agg['total_produzido']
        total_custo = agg['total_custo']
        total_receita = agg['total_receita']

        prod_real = total_prod / total_hh if (total_hh > 0 and agg['n_subs_com_qty'] > 0) else None

        # Produtividade orçada do gargalo: min(1/coef) sobre papéis com coef > 0
        prod_orcada_gargalo = None
        papel_gargalo_nome = None
        max_coef = 0.0
        for cid, coef in agg['papeis_coef'].items():
            if coef > max_coef:
                max_coef = coef
                papel_gargalo_nome = agg['papeis_nomes'].get(cid, '')
        if max_coef > 0:
            prod_orcada_gargalo = 1.0 / max_coef

        # Papel gargalo mais frequente
        if agg['gargalo_ocorrencias']:
            papel_gargalo_nome = max(agg['gargalo_ocorrencias'], key=agg['gargalo_ocorrencias'].get)

        # Papel subutilizado mais frequente
        papel_subutilizado = None
        if agg['subutilizado_ocorrencias']:
            papel_subutilizado = max(agg['subutilizado_ocorrencias'], key=agg['subutilizado_ocorrencias'].get)

        indice_pct = None
        if prod_real is not None and prod_orcada_gargalo and prod_orcada_gargalo > 0:
            indice_pct = prod_real / prod_orcada_gargalo * 100

        cobertura_pct = (agg['cobertura_hh_confirmado'] / agg['cobertura_hh_total'] * 100
                         if agg['cobertura_hh_total'] > 0 else 0.0)

        custo_medio_un = total_custo / total_prod if total_prod > 0 and total_custo > 0 else None
        receita_media_un = total_receita / total_prod if total_prod > 0 and total_receita > 0 else None
        lucro_medio_un = (receita_media_un - custo_medio_un
                          if receita_media_un is not None and custo_medio_un is not None else None)

        papeis_lista = [
            {
                'composicao_id': cid,
                'nome': agg['papeis_nomes'].get(cid, f'Papel#{cid}'),
                'coef': agg['papeis_coef'].get(cid, 0.0),
                'hh': hh,
            }
            for cid, hh in sorted(agg['papeis_hh'].items(), key=lambda x: -x[1])
        ]

        resultado.append({
            'servico_id': sid,
            'servico_nome': agg['servico_nome'],
            'unidade': agg['unidade'],
            'total_hh': total_hh,
            'total_produzido': total_prod if agg['n_subs_com_qty'] > 0 else None,
            'prod_orcada_gargalo': prod_orcada_gargalo,
            'prod_real_media': prod_real,
            'indice_pct': indice_pct,
            'custo_real_medio_un': custo_medio_un,
            'receita_liq_media_un': receita_media_un,
            'lucro_real_medio_un': lucro_medio_un,
            'cobertura_pct': cobertura_pct,
            'papel_gargalo_nome': papel_gargalo_nome,
            'papel_subutilizado_nome': papel_subutilizado,
            'papeis': papeis_lista,
            'n_rdos': agg['n_rdos'],
            'n_subs_com_qty': agg['n_subs_com_qty'],
            'n_subs_sem_qty': agg['n_subs_sem_qty'],
            'pode_aplicar_referencia': (
                agg['n_subs_com_qty'] > 0 and total_hh > 0 and sid is not None
            ),
        })

    return sorted(resultado, key=lambda x: x['servico_nome'])


def producao_por_funcionario(admin_id: int, data_inicio: date, data_fim: date,
                              obra_ids=None, funcao_ids=None) -> list:
    """Agrega métricas de produção e lucratividade por funcionário.

    Retorna lista de dicts ordenada por nome do funcionário.
    """
    regs = _carregar_dados_periodo(admin_id, data_inicio, data_fim,
                                   obra_ids=obra_ids, funcao_ids=funcao_ids)

    op_cache: dict = {}
    coef_cache: dict = {}
    nome_cache: dict = {}

    por_sub: dict = defaultdict(list)
    for r in regs:
        chave = (r['rdo_id'], r['sub_id'])
        por_sub[chave].append(r)

    metricas_sub = {}
    for chave, sub_regs in por_sub.items():
        m = _calcular_metricas_subatividade(sub_regs, op_cache, coef_cache, nome_cache)
        if m:
            metricas_sub[chave] = m

    dias_uteis = _dias_uteis_periodo(data_inicio, data_fim)

    func_agg: dict = defaultdict(lambda: {
        'func_id': None,
        'func_nome': '',
        'funcao_id': None,
        'funcao_nome': '',
        'horas_normais': 0.0,
        'horas_extras': 0.0,
        'custo_total': 0.0,
        'receita_total': 0.0,
        'custo_valido': False,
        'receita_valida': False,
        'dias_rdos': set(),
        'prod_hh_list': [],
        'modos': [],
        'servicos_vistos': set(),
    })

    # Processar registros de mão-de-obra individualmente
    for r in regs:
        fid = r['mo_func_id']
        fa = func_agg[fid]
        fa['func_id'] = fid
        fa['func_nome'] = r['mo_func_nome']
        fa['funcao_id'] = r['mo_funcao_id']
        fa['horas_normais'] += r['mo_horas']
        fa['horas_extras'] += r['mo_extras']
        fa['dias_rdos'].add(r['rdo_data'])
        if r['sub_servico_id']:
            fa['servicos_vistos'].add(r['sub_servico_id'])

    # Acumular métricas de subatividade por funcionário
    for chave, m in metricas_sub.items():
        for fid, fm in m['func_metricas'].items():
            fa = func_agg[fid]
            if fm['custo_na_sub'] is not None:
                fa['custo_total'] += fm['custo_na_sub']
                fa['custo_valido'] = True
            if fm['receita_dele'] is not None:
                fa['receita_total'] += fm['receita_dele']
                fa['receita_valida'] = True
            fa['modos'].append(fm['modo'])

        # Produtividade real por HH (quando single_role + tem qty)
        if m['quantidade_produzida'] and m['total_hh'] > 0 and m['modo'] == 'single_role':
            prod_hh = m['quantidade_produzida'] / m['total_hh']
            for fid in m['func_metricas']:
                func_agg[fid]['prod_hh_list'].append(prod_hh)

    # Buscar nome da função
    try:
        from models import Funcao
        funcao_ids_set = {fa['funcao_id'] for fa in func_agg.values() if fa['funcao_id']}
        funcao_map = {f.id: f.nome for f in Funcao.query.filter(Funcao.id.in_(funcao_ids_set)).all()} if funcao_ids_set else {}
    except Exception:
        funcao_map = {}

    resultado = []
    for fid, fa in func_agg.items():
        prod_real = (sum(fa['prod_hh_list']) / len(fa['prod_hh_list'])
                     if fa['prod_hh_list'] else None)
        modo_pred = 'equipe_mista' if fa['modos'].count('equipe_mista') > fa['modos'].count('single_role') else 'single_role'
        lucro_total = (fa['receita_total'] - fa['custo_total']
                       if fa['receita_valida'] and fa['custo_valido'] else None)
        assiduidade = len(fa['dias_rdos']) / dias_uteis * 100 if dias_uteis > 0 else 0.0

        resultado.append({
            'funcionario_id': fid,
            'funcionario_nome': fa['func_nome'],
            'funcao_id': fa['funcao_id'],
            'funcao_nome': funcao_map.get(fa['funcao_id'], fa['func_nome']),
            'horas_normais': fa['horas_normais'],
            'horas_extras': fa['horas_extras'],
            'dias_com_rdo': len(fa['dias_rdos']),
            'dias_uteis_periodo': dias_uteis,
            'assiduidade_pct': min(assiduidade, 100.0),
            'custo_total': fa['custo_total'] if fa['custo_valido'] else None,
            'receita_total': fa['receita_total'] if fa['receita_valida'] else None,
            'lucro_total': lucro_total,
            'modo_predominante': modo_pred,
            'prod_real_hh': prod_real,
            'tem_custo': fa['custo_valido'],
            'tem_receita': fa['receita_valida'],
            'n_servicos': len(fa['servicos_vistos']),
        })

    return sorted(resultado, key=lambda x: x['funcionario_nome'])


def detalhe_funcionario(admin_id: int, funcionario_id: int,
                        data_inicio: date, data_fim: date) -> dict:
    """Retorna as três seções de detalhe do funcionário:
      (A) por serviço, (B) por dia, (C) diagnóstico de equipe.
    """
    regs = _carregar_dados_periodo(admin_id, data_inicio, data_fim)
    regs_func = [r for r in regs if r['mo_func_id'] == funcionario_id]

    if not regs_func:
        return {'funcionario': None, 'por_servico': [], 'por_dia': [], 'diagnostico': []}

    op_cache: dict = {}
    coef_cache: dict = {}
    nome_cache: dict = {}

    # Agrupar por (rdo_id, sub_id) com TODOS os registros (para cálculo de equipe)
    por_sub_all: dict = defaultdict(list)
    for r in regs:
        chave = (r['rdo_id'], r['sub_id'])
        por_sub_all[chave].append(r)

    metricas_sub: dict = {}
    chaves_func = {(r['rdo_id'], r['sub_id']) for r in regs_func}
    for chave in chaves_func:
        sub_regs = por_sub_all.get(chave, [])
        m = _calcular_metricas_subatividade(sub_regs, op_cache, coef_cache, nome_cache)
        if m:
            metricas_sub[chave] = m

    # ── Seção A: por serviço ────────────────────────────────────────────────
    por_servico_agg: dict = defaultdict(lambda: {
        'servico_id': None, 'servico_nome': '', 'unidade': '',
        'horas': 0.0, 'custo': 0.0, 'receita': 0.0,
        'prod_list': [], 'indice_list': [], 'modo_list': [],
        'custo_valido': False, 'receita_valida': False,
    })
    for chave, m in metricas_sub.items():
        fm = m['func_metricas'].get(funcionario_id, {})
        sid = m['servico_id']
        agg = por_servico_agg[sid]
        agg['servico_id'] = sid
        agg['servico_nome'] = m['servico_nome']
        agg['unidade'] = m['unidade']
        agg['horas'] += fm.get('horas_na_sub', 0.0)
        if fm.get('custo_na_sub') is not None:
            agg['custo'] += fm['custo_na_sub']
            agg['custo_valido'] = True
        if fm.get('receita_dele') is not None:
            agg['receita'] += fm['receita_dele']
            agg['receita_valida'] = True
        if m['quantidade_produzida'] and m['total_hh'] > 0:
            agg['prod_list'].append(m['quantidade_produzida'] / m['total_hh'])
        if m['indice_equipe'] is not None:
            agg['indice_list'].append(m['indice_equipe'])
        agg['modo_list'].append(m['modo'])

    secao_a = []
    for sid, agg in por_servico_agg.items():
        lucro = (agg['receita'] - agg['custo']
                 if agg['receita_valida'] and agg['custo_valido'] else None)
        secao_a.append({
            'servico_id': sid,
            'servico_nome': agg['servico_nome'],
            'unidade': agg['unidade'],
            'horas': agg['horas'],
            'modo': 'equipe_mista' if agg['modo_list'].count('equipe_mista') > len(agg['modo_list'])/2 else 'single_role',
            'prod_media_hh': (sum(agg['prod_list'])/len(agg['prod_list']) if agg['prod_list'] else None),
            'indice_medio_pct': (sum(agg['indice_list'])/len(agg['indice_list']) if agg['indice_list'] else None),
            'custo': agg['custo'] if agg['custo_valido'] else None,
            'receita': agg['receita'] if agg['receita_valida'] else None,
            'lucro': lucro,
        })
    secao_a.sort(key=lambda x: x['servico_nome'])

    # ── Seção B: por dia ────────────────────────────────────────────────────
    por_dia_agg: dict = defaultdict(lambda: {
        'data': None, 'obra_id': None, 'rdo_id': None, 'rdo_numero': '',
        'horas': 0.0, 'custo': None, 'producao': None, 'receita': None,
        'lucro': None, 'modo': 'single_role',
    })
    for chave, m in metricas_sub.items():
        fm = m['func_metricas'].get(funcionario_id, {})
        dia_key = (m['rdo_data'], m['rdo_id'])
        d = por_dia_agg[dia_key]
        d['data'] = m['rdo_data']
        d['obra_id'] = m['obra_id']
        d['rdo_id'] = m['rdo_id']
        d['rdo_numero'] = m['rdo_numero']
        d['horas'] += fm.get('horas_na_sub', 0.0)
        if fm.get('custo_na_sub') is not None:
            d['custo'] = (d['custo'] or 0.0) + fm['custo_na_sub']
        if m['quantidade_produzida'] is not None:
            d['producao'] = (d['producao'] or 0.0) + m['quantidade_produzida']
        if fm.get('receita_dele') is not None:
            d['receita'] = (d['receita'] or 0.0) + fm['receita_dele']

    secao_b = []
    for (dt, rid), d in sorted(por_dia_agg.items(), key=lambda x: x[0][0]):
        if d['receita'] is not None and d['custo'] is not None:
            d['lucro'] = d['receita'] - d['custo']
        secao_b.append(d)

    # ── Seção C: diagnóstico de equipe ──────────────────────────────────────
    dias_gargalo = []
    dias_subutilizado = []
    for chave, m in metricas_sub.items():
        fm = m['func_metricas'].get(funcionario_id)
        if not fm:
            continue
        fid_composicao = fm.get('composicao_id')
        if m['papel_gargalo_id'] and fid_composicao == m['papel_gargalo_id']:
            dias_gargalo.append({'data': m['rdo_data'], 'rdo_numero': m['rdo_numero'],
                                  'servico': m['servico_nome']})
        if m['papel_subutilizado_nome']:
            nome_func_papel = nome_cache.get(fid_composicao, '')
            if nome_func_papel == m['papel_subutilizado_nome']:
                dias_subutilizado.append({'data': m['rdo_data'], 'rdo_numero': m['rdo_numero'],
                                           'servico': m['servico_nome']})

    secao_c = {
        'dias_gargalo': sorted(dias_gargalo, key=lambda x: x['data']),
        'dias_subutilizado': sorted(dias_subutilizado, key=lambda x: x['data']),
    }

    try:
        from models import Funcionario as FuncModel
        func_obj = FuncModel.query.get(funcionario_id)
    except Exception:
        func_obj = None

    return {
        'funcionario': func_obj,
        'por_servico': secao_a,
        'por_dia': secao_b,
        'diagnostico': secao_c,
    }


def ranking_funcionarios(admin_id: int, data_inicio: date, data_fim: date,
                          obra_ids=None, funcao_ids=None, servico_id=None,
                          ordenar_por: str = 'produtividade') -> list:
    """Lista de funcionários ordenada por produtividade, assiduidade ou lucratividade."""
    todos = producao_por_funcionario(admin_id, data_inicio, data_fim,
                                     obra_ids=obra_ids, funcao_ids=funcao_ids)
    if servico_id:
        # Filtro por serviço: mantém funcionários com registro em servico_id
        regs = _carregar_dados_periodo(admin_id, data_inicio, data_fim,
                                       obra_ids=obra_ids, funcao_ids=funcao_ids)
        funcs_com_servico = {r['mo_func_id'] for r in regs if r['sub_servico_id'] == servico_id}
        todos = [f for f in todos if f['funcionario_id'] in funcs_com_servico]

    if ordenar_por == 'produtividade':
        def _key(x):
            return (-(x['prod_real_hh'] or -1e9), x['funcionario_nome'])
    elif ordenar_por == 'assiduidade':
        def _key(x):
            return (-x['assiduidade_pct'], x['funcionario_nome'])
    elif ordenar_por == 'lucratividade':
        def _key(x):
            return (-(x['lucro_total'] or -1e9), x['funcionario_nome'])
    else:
        def _key(x):
            return x['funcionario_nome']

    return sorted(todos, key=_key)


def assiduidade_funcionario(admin_id: int, funcionario_id: int,
                             data_inicio: date, data_fim: date) -> dict:
    """Retorna dados de assiduidade bruta de um funcionário no período."""
    from models import RDO, RDOMaoObra
    from app import db

    dias_rdos = (
        db.session.query(RDO.data_relatorio)
        .join(RDOMaoObra, RDOMaoObra.rdo_id == RDO.id)
        .filter(
            RDO.admin_id == admin_id,
            RDOMaoObra.funcionario_id == funcionario_id,
            RDO.data_relatorio >= data_inicio,
            RDO.data_relatorio <= data_fim,
            RDO.status == 'Finalizado',
        )
        .distinct()
        .all()
    )
    dias = {r[0] for r in dias_rdos}
    dias_uteis = _dias_uteis_periodo(data_inicio, data_fim)
    return {
        'funcionario_id': funcionario_id,
        'dias_com_rdo': len(dias),
        'dias_uteis_periodo': dias_uteis,
        'assiduidade_pct': len(dias) / dias_uteis * 100 if dias_uteis > 0 else 0.0,
    }


def aplicar_como_referencia(admin_id: int, servico_id: int, usuario_id: int,
                              data_inicio: date, data_fim: date) -> dict:
    """Atualiza os coeficientes das linhas MAO_OBRA de ComposicaoServico com a
    produtividade real média apurada no período. Grava ComposicaoServicoHistorico.

    Retorna {'atualizados': n, 'historicos': n}.
    """
    from models import (
        ComposicaoServico, Insumo, ComposicaoServicoHistorico, Servico,
    )
    from app import db

    metricas = produtividade_por_servico(admin_id, data_inicio, data_fim)
    met_serv = next((m for m in metricas if m['servico_id'] == servico_id), None)
    if not met_serv or not met_serv['pode_aplicar_referencia']:
        return {'atualizados': 0, 'historicos': 0}

    if not met_serv['total_produzido'] or met_serv['total_produzido'] <= 0:
        return {'atualizados': 0, 'historicos': 0}

    atualizados = 0
    historicos = 0
    hoje = datetime.utcnow()

    for papel in met_serv['papeis']:
        cid = papel.get('composicao_id')
        if not cid:
            continue
        hh = papel.get('hh', 0.0)
        if hh <= 0 or met_serv['total_produzido'] <= 0:
            continue

        novo_coef = hh / met_serv['total_produzido']  # h / un → coef real

        cs = ComposicaoServico.query.get(cid)
        if not cs or cs.admin_id != admin_id:
            continue

        coef_anterior = float(cs.coeficiente)
        if abs(coef_anterior - novo_coef) < 1e-6:
            continue

        hist = ComposicaoServicoHistorico(
            admin_id=admin_id,
            composicao_servico_id=cid,
            servico_id=cs.servico_id,
            insumo_id=cs.insumo_id,
            coeficiente_anterior=coef_anterior,
            coeficiente_novo=novo_coef,
            autor_id=usuario_id,
            motivo=f'Referência real: {data_inicio}–{data_fim} ({met_serv["n_rdos"]} RDOs)',
            data_referencia_inicio=data_inicio,
            data_referencia_fim=data_fim,
        )
        db.session.add(hist)
        historicos += 1

        cs.coeficiente = round(novo_coef, 6)
        atualizados += 1

    if atualizados:
        db.session.commit()

    return {'atualizados': atualizados, 'historicos': historicos}
