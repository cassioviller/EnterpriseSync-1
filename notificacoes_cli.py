"""Task #45 — CLI: `flask emitir-propostas-expirando`.

Job idempotente que percorre Propostas com `status='enviada'` cuja
janela de validade está prestes a fechar (D-3, D-2, D-1 ou D=hoje) e
dispara o evento `proposta.expirando` para o n8n.

A janela é calculada a partir de `data_envio.date() + validade_dias`
(o modelo Proposta NÃO tem `data_validade` materializada).

Idempotência:
  Para cada (proposta_id, data de hoje) só sai UM `proposta.expirando`,
  consultando ``WebhookEntrega`` (entregue OU pendente OU falha — não
  reemitir nada que já foi enviado/registrado neste dia). Em ambientes
  sem N8N_WEBHOOK_URL o dispatcher é no-op silencioso, e nenhuma
  WebhookEntrega é criada — mas como nenhum evento sai mesmo, dedup é
  irrelevante nesse caso.

Uso típico (cron):
  0 8 * * *   cd /app && flask emitir-propostas-expirando
"""
from __future__ import annotations

import logging
from datetime import date, datetime, timedelta

import click
from flask.cli import with_appcontext
from sqlalchemy import func

logger = logging.getLogger(__name__)

# Janela em dias (≤ N dias para expirar) — D-3 a D (mesmo dia).
# 0 inclui o último dia da validade.
JANELA_DIAS_PADRAO = 3


def _ja_emitido_hoje(proposta_id: int) -> bool:
    """True se já existe uma WebhookEntrega `proposta.expirando` deste
    proposta_id criada hoje (qualquer status)."""
    try:
        from app import db
        from models import WebhookEntrega
        hoje = date.today()
        existe = (
            db.session.query(WebhookEntrega.id)
            .filter(WebhookEntrega.event == 'proposta.expirando')
            .filter(func.date(WebhookEntrega.created_at) == hoje)
            .filter(WebhookEntrega.payload['data']['proposta_id'].astext
                    == str(proposta_id))
            .first()
        )
        return existe is not None
    except Exception:
        # JSON path / dialeto não suportado: cai pra fallback Python.
        try:
            from app import db
            from models import WebhookEntrega
            hoje = date.today()
            candidatos = (
                WebhookEntrega.query
                .filter(WebhookEntrega.event == 'proposta.expirando')
                .filter(WebhookEntrega.created_at >= datetime.combine(hoje, datetime.min.time()))
                .all()
            )
            for c in candidatos:
                pid = (((c.payload or {}).get('data') or {}).get('proposta_id'))
                if pid == proposta_id:
                    return True
            return False
        except Exception:
            logger.exception('[#45] _ja_emitido_hoje fallback falhou')
            return False


def emitir_propostas_expirando(janela_dias: int = JANELA_DIAS_PADRAO,
                               dry_run: bool = False,
                               hoje: date | None = None) -> dict:
    """Função pura (testável) que percorre propostas elegíveis e emite.

    Retorna estatísticas: ``{ 'analisadas', 'emitidas', 'puladas_dedup',
    'puladas_sem_envio', 'puladas_fora_janela' }``.
    """
    from models import Proposta
    from utils.catalogo_eventos import emit_proposta_expirando

    hoje = hoje or date.today()
    stats = {
        'analisadas': 0, 'emitidas': 0, 'puladas_dedup': 0,
        'puladas_sem_envio': 0, 'puladas_fora_janela': 0,
    }

    # Status candidatos: propostas que ainda podem ser aprovadas/
    # rejeitadas pelo cliente. Aprovadas/rejeitadas/expiradas saíram
    # do funil. (Bate com docs/notificacoes/README.md §10.2.)
    STATUS_ELEGIVEIS = ('enviada', 'visualizada', 'em_negociacao')
    propostas = Proposta.query.filter(
        Proposta.status.in_(STATUS_ELEGIVEIS)
    ).all()
    for p in propostas:
        stats['analisadas'] += 1

        if not p.data_envio:
            stats['puladas_sem_envio'] += 1
            continue
        validade_dias = int(p.validade_dias or 0)
        if validade_dias <= 0:
            stats['puladas_sem_envio'] += 1
            continue

        data_validade = p.data_envio.date() + timedelta(days=validade_dias)
        dias_restantes = (data_validade - hoje).days
        if dias_restantes < 0 or dias_restantes > janela_dias:
            stats['puladas_fora_janela'] += 1
            continue

        if _ja_emitido_hoje(p.id):
            stats['puladas_dedup'] += 1
            continue

        if dry_run:
            stats['emitidas'] += 1
            continue

        emit_proposta_expirando(p, p.admin_id, data_validade, dias_restantes)
        stats['emitidas'] += 1

    return stats


@click.command('emitir-propostas-expirando')
@click.option('--janela', 'janela_dias', type=int, default=JANELA_DIAS_PADRAO,
              show_default=True,
              help='Quantos dias antes da expiração começar a notificar (D-N até D).')
@click.option('--dry-run', is_flag=True, default=False,
              help='Apenas simula: lista o que seria emitido.')
@with_appcontext
def emitir_propostas_expirando_cmd(janela_dias: int, dry_run: bool):
    """Dispara `proposta.expirando` para propostas dentro da janela final."""
    stats = emitir_propostas_expirando(janela_dias=janela_dias, dry_run=dry_run)
    click.echo(
        f"[#45] propostas.expirando: analisadas={stats['analisadas']} "
        f"emitidas={stats['emitidas']} dedup={stats['puladas_dedup']} "
        f"sem_envio={stats['puladas_sem_envio']} "
        f"fora_janela={stats['puladas_fora_janela']}"
        + (' (dry-run)' if dry_run else '')
    )
