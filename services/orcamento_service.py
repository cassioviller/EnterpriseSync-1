"""
services/orcamento_service.py — Task #82

Cálculo paramétrico de preço de venda de Serviços a partir de sua Composição
(Insumos × coeficientes), aplicando imposto e margem de lucro.

Fórmula:
    custo_unitario = Σ (coeficiente_i × preco_vigente_i)
    preco_venda    = custo_unitario / (1 − imposto_pct/100 − margem_lucro_pct/100)

Quando o serviço não tem composição, o resultado é 0 (não tenta inferir).
Quando a soma de imposto+margem ≥ 100, o cálculo retorna 0 e sinaliza erro
no dict de resposta para evitar divisão por zero/negativos.
"""
from __future__ import annotations

from datetime import date as _date
from decimal import Decimal, ROUND_HALF_UP
from typing import Optional

from app import db


def _q2(v: float) -> Decimal:
    """Arredonda para 2 casas decimais (HALF_UP)."""
    return Decimal(str(v)).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)


def calcular_precos_servico(servico, data_ref: Optional[_date] = None) -> dict:
    """Calcula preço de venda do serviço a partir da composição.

    Returns dict:
        {
          'custo_unitario': Decimal,
          'preco_venda':    Decimal,
          'imposto_pct':    Decimal,
          'margem_lucro_pct': Decimal,
          'detalhamento': [
              {'insumo_id', 'nome', 'unidade', 'coeficiente',
               'preco_unitario', 'subtotal'}, ...
          ],
          'erro': Optional[str],
        }
    """
    data_ref = data_ref or _date.today()

    # Defaults da empresa
    imposto_pct = servico.imposto_pct
    margem_pct = servico.margem_lucro_pct

    if imposto_pct is None or margem_pct is None:
        from models import ConfiguracaoEmpresa
        cfg = ConfiguracaoEmpresa.query.filter_by(admin_id=servico.admin_id).first()
        if cfg:
            if imposto_pct is None:
                imposto_pct = cfg.imposto_pct_padrao
            if margem_pct is None:
                margem_pct = cfg.lucro_pct_padrao

    imposto_pct = Decimal(str(imposto_pct or 0))
    margem_pct = Decimal(str(margem_pct or 0))

    custo_total = Decimal('0')
    custo_material = Decimal('0')
    custo_mao_obra = Decimal('0')
    custo_outros = Decimal('0')
    detalhamento = []
    for comp in servico.composicoes:
        preco_vig = Decimal(str(comp.insumo.preco_vigente(data_ref)))
        coef = Decimal(str(comp.coeficiente or 0))
        sub = (coef * preco_vig).quantize(Decimal('0.0001'))
        custo_total += sub
        tipo = (comp.insumo.tipo or '').upper()
        if tipo == 'MATERIAL':
            custo_material += sub
        elif tipo == 'MAO_OBRA':
            custo_mao_obra += sub
        else:
            custo_outros += sub
        detalhamento.append({
            'insumo_id': comp.insumo_id,
            'nome': comp.insumo.nome,
            'unidade': comp.unidade or comp.insumo.unidade,
            'tipo': comp.insumo.tipo,
            'coeficiente': float(coef),
            'preco_unitario': float(preco_vig),
            'subtotal': float(sub),
        })

    custo_unit_q = _q2(float(custo_total))
    custo_material_q = _q2(float(custo_material))
    custo_mao_obra_q = _q2(float(custo_mao_obra))
    custo_outros_q = _q2(float(custo_outros))

    divisor = Decimal('1') - (imposto_pct / Decimal('100')) - (margem_pct / Decimal('100'))
    erro = None
    if divisor <= Decimal('0'):
        preco_venda = Decimal('0.00')
        erro = 'imposto + margem >= 100% — ajuste os percentuais'
    else:
        preco_venda = (custo_total / divisor).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)

    return {
        # chaves originais (back-compat)
        'custo_unitario': custo_unit_q,
        'preco_venda': preco_venda,
        'imposto_pct': imposto_pct,
        'margem_lucro_pct': margem_pct,
        'detalhamento': detalhamento,
        'erro': erro,
        # contrato Task #82 (split de categorias + alias)
        'custo_material': custo_material_q,
        'custo_mao_obra': custo_mao_obra_q,
        'custo_outros': custo_outros_q,
        'custo_total': custo_unit_q,
        'preco_venda_unitario': preco_venda,
        'detalhes': detalhamento,
    }


def recalcular_servico_preco(servico, data_ref: Optional[_date] = None,
                             persistir: bool = True) -> dict:
    """Recalcula e (opcionalmente) persiste preco_venda_unitario + custo_unitario."""
    resultado = calcular_precos_servico(servico, data_ref)
    if persistir and not resultado.get('erro'):
        servico.custo_unitario = float(resultado['custo_unitario'])
        servico.preco_venda_unitario = resultado['preco_venda']
        db.session.flush()
    return resultado
