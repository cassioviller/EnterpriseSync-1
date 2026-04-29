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


_TIPO_LABELS = {
    'MAO_OBRA': 'Mão de obra',
    'MATERIAL': 'Material',
    'EQUIPAMENTO': 'Equipamento',
    'OUTROS': 'Outros',
}
# Ordem fixa para garantir as 3 colunas principais na ordem padrão; "OUTROS"
# vai para o fim se houver insumos sem categoria reconhecida.
_TIPO_ORDEM = ['MAO_OBRA', 'MATERIAL', 'EQUIPAMENTO', 'OUTROS']


def composicao_venda_agrupada(snapshot, custo_unit, preco_venda_unit, quantidade):
    """Task #18 — converte composicao_snapshot (CUSTO) em VENDA agrupada por tipo.

    O snapshot persiste o custo dos insumos. Para mostrar valores de venda na
    proposta sem reabrir o cálculo cascata, aplicamos um markup proporcional:
    cada insumo recebe a mesma razão (preco_venda_unit / custo_unit) que o
    item inteiro — assim a soma das vendas dos insumos == venda total do item.

    Quando o custo unitário é 0 (composição vazia), distribuímos o preço de
    venda igualmente entre os insumos (ou devolvemos lista vazia).

    Args:
        snapshot: lista de dicts {tipo, nome, unidade, coeficiente,
            preco_unitario, subtotal_unitario, ...}
        custo_unit: custo total para 1 unidade do serviço.
        preco_venda_unit: preço de venda para 1 unidade do serviço.
        quantidade: quantidade do serviço no orçamento.

    Returns:
        Lista ordenada de tuplas (tipo, label, subtotal_venda_total, [insumos]).
        Cada insumo tem: nome, unidade, qtd_total, valor_unitario_venda,
        valor_total_venda. Tipos com subtotal == 0 são omitidos.
    """
    snap = snapshot or []
    qtd_serv = _d(quantidade)
    custo_u = _d(custo_unit)
    venda_u = _d(preco_venda_unit)

    # Estratégia de markup:
    #  - custo > 0  → razão proporcional venda/custo (preserva mix de custo).
    #  - custo == 0 mas venda > 0 → distribui venda igualmente entre as linhas
    #    com coeficiente > 0 (mantém o tipo de cada insumo). Garante que o
    #    cliente continua vendo a composição mesmo quando os custos no snapshot
    #    estão zerados (insumos sem preço cadastrado, p.ex.).
    snap_validos = [l for l in snap if _d(l.get('coeficiente')) > 0]
    use_equal_dist = False
    venda_unit_equal = Decimal('0')
    ratio = Decimal('0')
    if custo_u > 0:
        ratio = venda_u / custo_u
    elif venda_u > 0 and snap_validos:
        use_equal_dist = True
        venda_unit_equal = (venda_u / Decimal(len(snap_validos))).quantize(
            Decimal('0.0001')
        )

    grupos = {t: {'subtotal': Decimal('0'), 'insumos': []} for t in _TIPO_ORDEM}

    for linha in snap:
        tipo = (linha.get('tipo') or 'OUTROS').upper()
        if tipo not in grupos:
            tipo = 'OUTROS'
        coef = _d(linha.get('coeficiente'))
        custo_unit_insumo = _d(linha.get('subtotal_unitario'))  # coef × preço (custo)
        if use_equal_dist and coef > 0:
            venda_unit_insumo = venda_unit_equal
        elif ratio > 0:
            venda_unit_insumo = custo_unit_insumo * ratio
        else:
            venda_unit_insumo = Decimal('0')
        venda_total_insumo = (venda_unit_insumo * qtd_serv).quantize(
            Decimal('0.01'), rounding=ROUND_HALF_UP
        )
        qtd_total_insumo = (coef * qtd_serv).quantize(Decimal('0.0001'))
        grupos[tipo]['subtotal'] += venda_total_insumo
        grupos[tipo]['insumos'].append({
            'nome': linha.get('nome') or '',
            'unidade': linha.get('unidade') or 'un',
            'coeficiente': float(coef),
            'qtd_total': float(qtd_total_insumo),
            'valor_unitario_venda': float(
                venda_unit_insumo.quantize(Decimal('0.0001'))
            ),
            'valor_total_venda': float(venda_total_insumo),
        })

    resultado = []
    for tipo in _TIPO_ORDEM:
        sub = grupos[tipo]['subtotal']
        # Esconde categoria zerada (regra explícita da task)
        if sub <= 0 and not grupos[tipo]['insumos']:
            continue
        if sub <= 0:
            continue
        resultado.append((
            tipo,
            _TIPO_LABELS[tipo],
            float(sub.quantize(Decimal('0.01'))),
            grupos[tipo]['insumos'],
        ))
    return resultado


def split_lines(texto):
    """Task #18 — quebra texto livre em lista de bullets, ignorando vazios."""
    if not texto:
        return []
    return [l.strip() for l in str(texto).splitlines() if l and l.strip()]


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
