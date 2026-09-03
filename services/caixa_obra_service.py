"""Lente de CAIXA da obra (Fatia 4) — Realizado/Previsto no tempo.

Distinta da lente de COMPETÊNCIA (Resultado por Atividade): aqui interessa
**quando o dinheiro entra/sai**, não quando o fato econômico ocorre (DC4). Reúsa
integralmente o motor de fluxo de caixa existente (`FinanceiroService`), apenas
filtrado por obra. A variação acumulada parte de ZERO e Realizado/Previsto nunca
são somados num único número (ADR 0003).
"""


def fluxo_caixa_obra(admin_id, obra_id, data_inicio, data_fim):
    """Fluxo de caixa de UMA obra no período. Delegação pura ao FinanceiroService.

    Retorna: {fluxo, meses, kpis, serie_chart}. `saldo_inicial=0.0` porque a
    variação de caixa da obra parte de 0 (ADR 0003; o saldo bancário absoluto
    não é por obra)."""
    from financeiro_service import FinanceiroService
    fluxo = FinanceiroService.calcular_fluxo_caixa(
        admin_id, data_inicio, data_fim, obra_id=obra_id
    )
    agg = FinanceiroService.agregar_fluxo_mensal(fluxo['detalhes'], saldo_inicial=0.0)
    return {
        'fluxo': fluxo,
        'meses': agg['meses'],
        'kpis': agg['kpis'],
        'serie_chart': agg['serie_chart'],
    }
