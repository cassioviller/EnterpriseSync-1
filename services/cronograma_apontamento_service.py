"""
Serviço único de apontamento de produção do cronograma (Módulo 1 — plano
cronograma-mpp, passo 2/8).

Extrai a fórmula de apontamento que estava DUPLICADA em:
  - views/rdo.py (bloco "V2: Processar apontamentos" de salvar_rdo_flexivel)
  - cronograma_views.py:apontar_producao

A semântica é EXATAMENTE a atual (cópia literal — mesmos round(..., 2),
min(100.0, ...), mesma query de acumulado anterior). Qualquer mudança de
comportamento é pega pelos testes de caracterização
(tests/test_caracterizacao_apontamento_cronograma.py).

Responsabilidades que FICAM NO CALLER (sem mudança de comportamento):
  - validação de tenant / is_v2_active / is_cliente / parse do request;
  - filtro qty <= 0 (salvar_rdo_flexivel ignora; apontar_producao aceita 0);
  - flush/commit da sessão;
  - atualizar_percentual_tarefa (rollup do percentual_concluido da tarefa).
"""
from __future__ import annotations

import logging

from models import db, RDO, RDOApontamentoCronograma
from utils.cronograma_engine import calcular_progresso_rdo

logger = logging.getLogger(__name__)


def registrar_apontamento(rdo, tarefa, *, quantidade_dia=None,
                          percentual_acumulado=None,
                          admin_id) -> RDOApontamentoCronograma:
    """Exatamente a semântica atual de views/rdo.py:4556-4609.
    quantidade_dia XOR percentual_acumulado. Sem commit (caller comita).

    Modo quantitativo (`quantidade_dia`):
      acumulada = SUM(quantidade_executada_dia) de RDOs ANTERIORES
                  (data_relatorio < rdo.data_relatorio) + quantidade_dia
      percentual_realizado = min(100.0, round(acumulada / quantidade_total
                             * 100, 2)) quando quantidade_total > 0;
                             senão 0.0 (fallback sem quantidade física).

    Modo percentual (`percentual_acumulado`) — semântica do import
    físico-financeiro (services/importacao_fisico_financeiro.py) para
    tarefas sem quantidade física: o valor é o % ACUMULADO da tarefa no
    dia; o incremento diário (gravado em quantidade_executada_dia) é a
    diferença para o último % acumulado anterior; quantidade_acumulada
    fica 0.0.

    UPSERT por (rdo_id, tarefa_cronograma_id): atualiza o apontamento
    existente do mesmo RDO (semântica de apontar_producao); quando não
    existe, cria — em salvar_rdo_flexivel o RDO é sempre recém-criado,
    portanto ali o resultado é sempre criação (mesmo comportamento de
    antes da extração).

    Retorna o RDOApontamentoCronograma (novo ou atualizado), já na sessão.
    """
    if (quantidade_dia is None) == (percentual_acumulado is None):
        raise ValueError(
            'registrar_apontamento: informe exatamente um entre '
            'quantidade_dia e percentual_acumulado'
        )

    from sqlalchemy import func as sqlfunc

    # Acumulado ANTES deste RDO (cópia literal da query de views/rdo.py /
    # cronograma_views.py — soma dos dias em RDOs com data anterior).
    acum_ant = (
        db.session.query(sqlfunc.coalesce(sqlfunc.sum(RDOApontamentoCronograma.quantidade_executada_dia), 0.0))
        .join(RDO, RDO.id == RDOApontamentoCronograma.rdo_id)
        .filter(
            RDOApontamentoCronograma.tarefa_cronograma_id == tarefa.id,
            RDOApontamentoCronograma.admin_id == admin_id,
            RDO.data_relatorio < rdo.data_relatorio,
        )
        .scalar()
    ) or 0.0

    # Planejado na data do RDO (None = tarefa sem plano calculável).
    progresso = calcular_progresso_rdo(tarefa.id, rdo.data_relatorio, admin_id)
    perc_planejado = progresso['percentual_planejado']

    if quantidade_dia is not None:
        tipo = 'quantidade'
        qty = float(quantidade_dia)
        nova_acum = acum_ant + qty
        perc_real = 0.0
        if tarefa.quantidade_total and tarefa.quantidade_total > 0:
            perc_real = min(100.0, round(nova_acum / tarefa.quantidade_total * 100, 2))
    else:
        # Modo percentual direto: o incremento diário é a diferença para o
        # último % acumulado registrado em RDOs anteriores (mesma fórmula do
        # import físico-financeiro: max(0.0, round(pct - anterior, 2))).
        tipo = 'percentual'
        pct = float(percentual_acumulado or 0)
        pct_ant_row = (
            db.session.query(RDOApontamentoCronograma.percentual_realizado)
            .join(RDO, RDO.id == RDOApontamentoCronograma.rdo_id)
            .filter(
                RDOApontamentoCronograma.tarefa_cronograma_id == tarefa.id,
                RDOApontamentoCronograma.admin_id == admin_id,
                RDO.data_relatorio < rdo.data_relatorio,
            )
            .order_by(RDO.data_relatorio.desc())
            .first()
        )
        pct_ant = float(pct_ant_row[0]) if pct_ant_row and pct_ant_row[0] is not None else 0.0
        qty = max(0.0, round(pct - pct_ant, 2))
        nova_acum = 0.0
        perc_real = pct

    # UPSERT por (rdo_id, tarefa_cronograma_id) — cópia literal da busca de
    # apontar_producao (sem filtro extra de admin_id, como no original).
    ap = RDOApontamentoCronograma.query.filter_by(
        rdo_id=rdo.id, tarefa_cronograma_id=tarefa.id
    ).first()
    criado = ap is None
    antes = None if criado else {
        'quantidade_executada_dia': ap.quantidade_executada_dia,
        'quantidade_acumulada': ap.quantidade_acumulada,
        'percentual_realizado': ap.percentual_realizado,
        'percentual_planejado': ap.percentual_planejado,
    }
    if criado:
        ap = RDOApontamentoCronograma(
            rdo_id=rdo.id,
            tarefa_cronograma_id=tarefa.id,
            admin_id=admin_id,
        )
        db.session.add(ap)

    ap.quantidade_executada_dia = qty
    ap.quantidade_acumulada = nova_acum
    ap.percentual_realizado = perc_real
    ap.percentual_planejado = perc_planejado

    # Log estruturado (substitui prints/logs dispersos dos callers).
    logger.info(
        '[apontamento] rdo=%s tarefa=%s tipo=%s %s '
        'antes=%s depois={qty_dia: %s, acum: %s, perc_real: %s, perc_plan: %s} '
        'acum_ant=%s admin=%s',
        rdo.id, tarefa.id, tipo, 'criado' if criado else 'atualizado',
        antes, qty, nova_acum, perc_real, perc_planejado, acum_ant, admin_id,
    )
    return ap
