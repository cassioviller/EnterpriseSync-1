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
    """Cria o snapshot inicial da composição a partir do catálogo do serviço.

    Task #74 — separação semântica de conceitos de preço:
      preco_unitario        = preco_embalagem (preço que se paga ao fornecedor)
      preco_tecnico_unitario = preco_embalagem / fator_comercial (custo proporcional por unidade)
      subtotal_unitario     = coef × preco_tecnico_unitario (custo técnico por 1 unidade do serviço)
    """
    snap = []
    for c in (servico.composicoes or []):
        ins = c.insumo
        preco_emb = float(ins.preco_vigente()) if hasattr(ins, 'preco_vigente') else 0.0
        fator = float(ins.fator_comercial or 1) or 1.0
        preco_tec = preco_emb / fator
        coef = float(c.coeficiente or 0)
        snap.append({
            'tipo': (ins.tipo or 'MATERIAL').upper(),
            'insumo_id': ins.id,
            'nome': ins.nome,
            'unidade': c.unidade or ins.unidade or 'un',
            'coeficiente': coef,
            'preco_unitario': preco_emb,                    # preço da embalagem (base de compra)
            'preco_embalagem': preco_emb,                   # Task #74 — campo explícito para rastreabilidade
            'preco_tecnico_unitario': round(preco_tec, 4),  # Task #74 — preço por unidade técnica
            'subtotal_unitario': round(coef * preco_tec, 4),  # Task #74 — custo técnico correto (coef × preço_tec)
            # Task #19 — campos de quantidade comercial (snapshot do catálogo)
            'fator_comercial': fator,
            'unidade_comercial': ins.unidade_comercial or None,
            # Task #75 — fracionavel: False → ceil mesmo quando fator=1 (peça, barra, un…)
            'fracionavel': bool(ins.fracionavel) if ins.fracionavel is not None else True,
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

    Task #47 — custo_total e venda_total usam o custo real de compra por pacote
    (não o custo técnico proporcional).

    custo_unitario_tecnico = Σ(coef × preço_unit) — custo proporcional por unidade
    custo_compra           = Σ(nº_pacotes × preço_embalagem) — custo real total
    custo_medio_unitario   = custo_compra / qtd_item — custo médio por unidade
    preco_unit             = custo_medio_unitario / divisor — preço de venda por unidade
    custo_total            = custo_compra (custo real de aquisição)
    venda_total            = custo_compra / divisor (preço total de venda)
    lucro_total            = venda_total − custo_total

    Cada linha do snapshot é enriquecida com:
      quantidade_tecnica  = coef × item.quantidade  (uso exato do projeto)
      quantidade_compra   = múltiplo do fator ≥ qtd_tecnica (o que se compra)
      subtotal_compra     = nº_pacotes × preço_pacote (custo real de aquisição)

    Retorna dict com {custo_unit, preco_unit, custo_total, venda_total, lucro_total, erro}.
    """
    snap = item.composicao_snapshot or []
    qtd_item = _d(item.quantidade)
    custo_unit_tec = Decimal('0')   # técnico proporcional: Σ(coef × preço_tec)
    custo_compra = Decimal('0')     # real de compra: Σ(nº_pacotes × preço_emb)
    snap_norm = []
    for linha in snap:
        coef = _d(linha.get('coeficiente'))
        preco = _d(linha.get('preco_unitario'))   # preço da embalagem (backward compat)
        fator = _d(linha.get('fator_comercial') or 1) or Decimal('1')
        # Task #74 — preço técnico por unidade = preço embalagem / fator_comercial
        # Retrocompatível: snapshots legados têm preco_unitario = embalagem (fator divido aqui)
        #                  novos snapshots também têm preco_unitario = embalagem (mesmo resultado)
        preco_tec = (preco / fator).quantize(Decimal('0.00001')) if fator > Decimal('0') else Decimal('0')
        sub_unit = (coef * preco_tec).quantize(Decimal('0.0001'))
        unidade_comercial = linha.get('unidade_comercial') or None
        # Task #75 — fracionavel: False força ceil mesmo quando fator=1 (peça, barra, un…)
        # Snapshots novos: campo está presente. Snapshots antigos: busca no banco pelo insumo_id.
        if 'fracionavel' in linha:
            fracionavel = bool(linha['fracionavel'])
        else:
            _insumo_id = linha.get('insumo_id')
            fracionavel = True  # default retrocompatível
            if _insumo_id:
                try:
                    from models import Insumo as _Insumo
                    from app import db as _db
                    _ins = _db.session.get(_Insumo, int(_insumo_id))
                    if _ins is not None:
                        fracionavel = bool(_ins.fracionavel)
                except Exception:
                    pass
        # quantidades por item (dependem da qtd total do item)
        qtd_tec = (coef * qtd_item).quantize(Decimal('0.0001'))
        deve_arredondar = (not fracionavel) or (fator > Decimal('1'))
        if deve_arredondar and qtd_tec > Decimal('0'):
            # Divisão inteira com arredondamento para cima em puro Decimal
            # (evita imprecisão de float ao converter Decimal → float → ceil)
            from decimal import ROUND_CEILING
            multiplos = (qtd_tec / fator).to_integral_value(rounding=ROUND_CEILING)
            qtd_com = (multiplos * fator).quantize(Decimal('0.0001'))
            # subtotal_compra = nº de pacotes × preço da embalagem (custo real de aquisição)
            sub_compra = (multiplos * preco).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
        else:
            qtd_com = qtd_tec
            sub_compra = (qtd_com * preco).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
        snap_norm.append({
            'tipo': (linha.get('tipo') or 'MATERIAL').upper(),
            'insumo_id': linha.get('insumo_id'),
            'nome': linha.get('nome') or '',
            'unidade': linha.get('unidade') or 'un',
            'coeficiente': float(coef),
            'preco_unitario': float(preco),               # preço da embalagem (backward compat)
            'preco_embalagem': float(preco),              # Task #74 — campo explícito
            'preco_tecnico_unitario': float(preco_tec),   # Task #74 — preço por unidade técnica
            'subtotal_unitario': float(sub_unit),         # Task #74 — custo técnico correto
            'fator_comercial': float(fator),
            'unidade_comercial': unidade_comercial,
            'fracionavel': fracionavel,                   # Task #75 — propaga flag
            'quantidade_tecnica': float(qtd_tec),
            'quantidade_compra': float(qtd_com),
            'subtotal_compra': float(sub_compra),
        })
        custo_unit_tec += sub_unit
        custo_compra += sub_compra
    item.composicao_snapshot = snap_norm

    imp, mar = aliquotas_efetivas(item, orcamento, item.servico)
    divisor = Decimal('1') - (imp / Decimal('100')) - (mar / Decimal('100'))
    erro = None
    if divisor <= 0:
        preco_unit = Decimal('0')
        venda_total = Decimal('0')
        erro = 'imposto + margem >= 100%'
    else:
        # Task #47: preço unitário baseado no custo médio real (custo_compra / qtd)
        custo_medio = (custo_compra / qtd_item) if qtd_item > 0 else custo_compra
        preco_unit = (custo_medio / divisor).quantize(Decimal('0.0001'))
        venda_total = (custo_compra / divisor).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)

    # Task #47: custo_total = custo real de compra (não custo técnico × qtd)
    custo_total = custo_compra.quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
    lucro_total = venda_total - custo_total

    # custo_unitario armazena o custo médio real por unidade do serviço
    custo_medio_unit = (custo_compra / qtd_item).quantize(
        Decimal('0.0001'), rounding=ROUND_HALF_UP
    ) if qtd_item > 0 else custo_compra.quantize(Decimal('0.0001'))

    item.custo_unitario = custo_medio_unit
    item.preco_venda_unitario = preco_unit
    item.custo_total = custo_total
    item.venda_total = venda_total
    item.lucro_total = lucro_total

    return {
        'custo_unit': float(custo_medio_unit),
        'custo_unit_tecnico': float(custo_unit_tec),
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
        # Task #19 — propaga quantidades comerciais do snapshot (se persistidas)
        qtd_compra = _d(linha.get('quantidade_compra') or 0) or qtd_total_insumo
        unidade_comercial = linha.get('unidade_comercial') or None
        fator_com = _d(linha.get('fator_comercial') or 1) or Decimal('1')
        grupos[tipo]['subtotal'] += venda_total_insumo
        grupos[tipo]['insumos'].append({
            'nome': linha.get('nome') or '',
            'unidade': linha.get('unidade') or 'un',
            'coeficiente': float(coef),
            'qtd_total': float(qtd_total_insumo),
            'quantidade_compra': float(qtd_compra),
            'unidade_comercial': unidade_comercial,
            'fator_comercial': float(fator_com),
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
