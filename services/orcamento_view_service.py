"""
services/orcamento_view_service.py — Task #115

Cálculo dos totais de um Orçamento aplicando o cascade:
override per-item > global do orçamento > defaults do serviço/empresa.

Snapshot da composição é editável (linhas com tipo MATERIAL/MAO_OBRA/OUTROS,
coeficiente e preço unitário). Recalcula custo_unitario, preço de venda
e totais a partir do snapshot persistido.
"""
from __future__ import annotations

from decimal import Decimal, ROUND_HALF_UP
from typing import Optional


def _d(v) -> Decimal:
    if v is None or v == '':
        return Decimal('0')
    try:
        return Decimal(str(v))
    except Exception:
        return Decimal('0')


def _q2(v) -> Decimal:
    return _d(v).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)


def snapshot_from_servico(servico) -> list:
    """Cria o snapshot inicial da composição a partir do catálogo do serviço."""
    snap = []
    for c in (servico.composicoes or []):
        ins = c.insumo
        preco = float(ins.preco_vigente()) if hasattr(ins, 'preco_vigente') else 0.0
        coef = float(c.coeficiente or 0)
        snap.append({
            'tipo': (ins.tipo or 'MATERIAL').upper(),
            'insumo_id': ins.id,
            'nome': ins.nome,
            'unidade': c.unidade or ins.unidade or 'un',
            'coeficiente': coef,
            'preco_unitario': preco,
            'subtotal_unitario': round(coef * preco, 4),
        })
    return snap


def aliquotas_efetivas(item, orcamento, servico=None) -> tuple[Decimal, Decimal]:
    """Cascade: per-item > global do orçamento > do serviço > 0."""
    imp = item.imposto_pct
    if imp is None:
        imp = orcamento.imposto_pct_global
    if imp is None and servico is not None:
        imp = servico.imposto_pct
    mar = item.margem_pct
    if mar is None:
        mar = orcamento.margem_pct_global
    if mar is None and servico is not None:
        mar = servico.margem_lucro_pct
    return _d(imp), _d(mar)


def recalcular_item(item, orcamento) -> dict:
    """Recalcula o item a partir do snapshot. Atualiza campos in-place.

    Retorna dict com {custo_unit, preco_unit, custo_total, venda_total, lucro_total, erro}.
    """
    snap = item.composicao_snapshot or []
    custo_unit = Decimal('0')
    snap_norm = []
    for linha in snap:
        coef = _d(linha.get('coeficiente'))
        preco = _d(linha.get('preco_unitario'))
        sub = (coef * preco).quantize(Decimal('0.0001'))
        snap_norm.append({
            'tipo': (linha.get('tipo') or 'MATERIAL').upper(),
            'insumo_id': linha.get('insumo_id'),
            'nome': linha.get('nome') or '',
            'unidade': linha.get('unidade') or 'un',
            'coeficiente': float(coef),
            'preco_unitario': float(preco),
            'subtotal_unitario': float(sub),
        })
        custo_unit += sub
    item.composicao_snapshot = snap_norm

    imp, mar = aliquotas_efetivas(item, orcamento, item.servico)
    divisor = Decimal('1') - (imp / Decimal('100')) - (mar / Decimal('100'))
    erro = None
    if divisor <= 0:
        preco_unit = Decimal('0')
        erro = 'imposto + margem >= 100%'
    else:
        preco_unit = (custo_unit / divisor).quantize(Decimal('0.0001'))

    qtd = _d(item.quantidade)
    custo_total = (qtd * custo_unit).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
    venda_total = (qtd * preco_unit).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
    lucro_total = venda_total - custo_total

    item.custo_unitario = custo_unit.quantize(Decimal('0.0001'))
    item.preco_venda_unitario = preco_unit
    item.custo_total = custo_total
    item.venda_total = venda_total
    item.lucro_total = lucro_total

    return {
        'custo_unit': float(custo_unit),
        'preco_unit': float(preco_unit),
        'custo_total': float(custo_total),
        'venda_total': float(venda_total),
        'lucro_total': float(lucro_total),
        'imposto_pct': float(imp),
        'margem_pct': float(mar),
        'erro': erro,
    }


def recalcular_orcamento(orcamento) -> dict:
    """Recalcula todos os itens e os totais do orçamento."""
    custo = Decimal('0')
    venda = Decimal('0')
    for it in orcamento.itens:
        recalcular_item(it, orcamento)
        custo += _d(it.custo_total)
        venda += _d(it.venda_total)
    orcamento.custo_total = custo.quantize(Decimal('0.01'))
    orcamento.venda_total = venda.quantize(Decimal('0.01'))
    orcamento.lucro_total = (venda - custo).quantize(Decimal('0.01'))
    return {
        'custo': float(orcamento.custo_total),
        'venda': float(orcamento.venda_total),
        'lucro': float(orcamento.lucro_total),
        'margem_efetiva_pct': float((orcamento.lucro_total / venda * 100)) if venda > 0 else 0,
    }
