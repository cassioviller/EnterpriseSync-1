"""EVM por composição — p10 do `PLANO-NUCLEO.md` (a Fase 7 reescrita).

## Por que não é a Fase 7 do plano de 21/07

Aquele plano mandava construir `TarefaPredecessora`, `utils/cpm.py`,
`cronograma_cpm_service` e uma baseline própria. Três dias depois, o editor
de cronograma v2 entregou o núcleo estrutural disso: `TarefaVinculo` com N
predecessoras tipadas, motor com passe direto e inverso, folga total,
caminho crítico e `CronogramaBaseline`. Implementar a fase como escrita
criaria **uma segunda rede de predecessoras e uma segunda baseline**.

O que sobrou dela é o EVM — e as três séries dele já existem vivas no
sistema. Este módulo **compõe**, não constrói:

| Grandeza | De onde vem |
|---|---|
| **BAC** (orçamento na conclusão) | `services/custo_orcado.custo_orcado_da_obra` — custo, não venda (p3) |
| **PV** (valor planejado) | curva de desembolso previsto de `montar_fisico_financeiro` |
| **AC** (custo real) | `curva_realizado` — o que de fato saiu |
| **EV** (valor agregado) | progresso físico × BAC (p4: uma fórmula, ponderada por duração) |

## As duas armadilhas que este módulo evita

**BAC não é `valor_contrato`.** Contrato é venda; EVM compara custo com
custo. Usar venda como BAC daria CPI sempre favorável — o erro que o p3
existiu para fechar.

**EV usa progresso físico, não financeiro.** Medir avanço pelo dinheiro já
gasto é medir esforço, não entrega — e faz o índice de desempenho de prazo
(SPI) mentir exatamente quando a obra atrasa gastando.
"""
from __future__ import annotations

import logging
from decimal import Decimal

logger = logging.getLogger(__name__)


def _d(v) -> Decimal:
    try:
        return Decimal(str(v or 0))
    except Exception:
        return Decimal('0')


def calcular_evm(obra_id: int, admin_id: int) -> dict:
    """As quatro grandezas do EVM e os índices derivados.

    Devolve dict pronto para JSON:

      bac, pv, ev, ac, cv, sv, cpi, spi, eac, etc, vac, pct_fisico

    Todos os valores em reais (float) e percentuais em 0..100. Nunca levanta:
    obra sem custo cadastrado devolve zeros com `tem_dados=False` — o painel
    precisa distinguir "sem dado" de "índice 0", que significaria desempenho
    nulo.
    """
    from services.cronograma_fisico_financeiro import (curva_realizado,
                                                       montar_fisico_financeiro)
    from services.custo_orcado import custo_orcado_da_obra
    from utils.cronograma_engine import progresso_ponderado_armazenado
    from models import Obra

    vazio = {
        'bac': 0.0, 'pv': 0.0, 'ev': 0.0, 'ac': 0.0,
        'cv': 0.0, 'sv': 0.0, 'cpi': None, 'spi': None,
        'eac': 0.0, 'etc': 0.0, 'vac': 0.0,
        'pct_fisico': 0.0, 'tem_dados': False,
    }

    try:
        obra = Obra.query.filter_by(id=obra_id, admin_id=admin_id).first()
        if obra is None:
            return vazio

        bac = _d(custo_orcado_da_obra(obra_id, admin_id))
        if bac <= 0:
            # Sem custo orçado não há EVM: todos os índices dividiriam por
            # zero, e um painel cheio de "0%" seria lido como obra parada.
            logger.info('[p10] obra %s sem custo orçado — EVM indisponível',
                        obra_id)
            return vazio

        pct_fisico = _d(progresso_ponderado_armazenado(obra_id, admin_id))
        ev = (bac * pct_fisico / Decimal('100'))

        dados = montar_fisico_financeiro(obra_id, admin_id)
        pv = _pv_ate_hoje(dados)

        ac = sum(curva_realizado(obra).values(), Decimal('0'))

        cv = ev - ac
        sv = ev - pv
        cpi = float(ev / ac) if ac > 0 else None
        spi = float(ev / pv) if pv > 0 else None

        # EAC pelo índice de desempenho de custo — a projeção que assume que
        # o desperdício observado continua. Sem CPI (nada gasto ainda), a
        # melhor projeção é o próprio orçamento.
        eac = (bac / _d(cpi)) if cpi else bac
        etc = eac - ac
        vac = bac - eac

        return {
            'bac': float(bac), 'pv': float(pv), 'ev': float(ev),
            'ac': float(ac), 'cv': float(cv), 'sv': float(sv),
            'cpi': round(cpi, 4) if cpi is not None else None,
            'spi': round(spi, 4) if spi is not None else None,
            'eac': float(eac), 'etc': float(etc), 'vac': float(vac),
            'pct_fisico': float(pct_fisico), 'tem_dados': True,
        }
    except Exception:
        logger.exception('[p10] calcular_evm falhou (obra=%s)', obra_id)
        return vazio


def _pv_ate_hoje(dados: dict) -> Decimal:
    """Valor planejado acumulado até o mês corrente.

    O painel já faseia o desembolso previsto por mês
    (`montar_fisico_financeiro`); PV é a soma até hoje — não o total da obra,
    que seria o BAC. Confundir os dois faz o SV parecer catastrófico no
    começo de qualquer obra.
    """
    from datetime import date

    hoje = date.today().strftime('%Y-%m')
    total = Decimal('0')
    for etapa in dados.get('etapas', []):
        for mes, valor in (etapa.get('meses') or {}).items():
            if str(mes) <= hoje:
                total += _d(valor)
    return total
