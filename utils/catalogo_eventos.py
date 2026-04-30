"""Task #45 — Catálogo inicial de eventos `dominio.acao` para notificação
externa via n8n.

Este módulo centraliza a construção dos payloads dos 7 eventos de catálogo
e oferece *helpers* `emit_*` que:

  1. Montam o payload completo (com lookups defensivos: a falta de uma
     URL de portal ou de um cliente_email NÃO impede o disparo).
  2. Disparam o evento via :class:`event_manager.EventManager` SEM nunca
     propagar exceção para o caller — webhook é best-effort, jamais
     deve quebrar a transação de negócio que o originou.
  3. Sempre emitem com `raise_on_error=False` (default), mantendo o
     contrato de "fundação não-invasiva" da Task #43.

Os eventos legados (`proposta_aprovada`, `rdo_finalizado`, etc.) seguem
sendo emitidos pelo código existente — esses helpers SÃO ADICIONAIS,
chamados em paralelo nos mesmos pontos. Se o webhook estiver desligado
ou o evento não estiver na allowlist, o dispatcher é no-op silencioso.
"""
from __future__ import annotations

import logging
import os
from datetime import date, datetime
from typing import Any

logger = logging.getLogger(__name__)


def _fallback_external_base() -> str | None:
    """Base URL absoluta para gerar links em contexto fora-de-request
    (ex.: CLI ``flask emitir-propostas-expirando`` rodando em cron).

    Ordem: ``PORTAL_BASE_URL`` → ``REPLIT_DEV_DOMAIN`` (com https) → None.
    """
    base = os.environ.get('PORTAL_BASE_URL')
    if base:
        return base.rstrip('/')
    dev = os.environ.get('REPLIT_DEV_DOMAIN')
    if dev:
        return f'https://{dev}'.rstrip('/')
    return None


# ────────────────────────────────────────────────────────────────────────
# Helpers internos
# ────────────────────────────────────────────────────────────────────────
def _safe_float(v: Any) -> float:
    try:
        return float(v or 0)
    except (TypeError, ValueError):
        return 0.0


def _iso_date(d: Any) -> str | None:
    if d is None:
        return None
    if isinstance(d, datetime):
        return d.date().isoformat()
    if isinstance(d, date):
        return d.isoformat()
    return str(d)


def _portal_proposta_url(token: str | None) -> str | None:
    """URL pública do portal do CLIENTE para acompanhar a proposta.

    Tenta `url_for(..., _external=True)`. Em contexto sem request
    (CLI/cron) cai em fallback baseado em env (``PORTAL_BASE_URL``
    ou ``REPLIT_DEV_DOMAIN``) para que o lembrete continue acionável.
    """
    if not token:
        return None
    try:
        from flask import url_for, has_request_context
        if has_request_context():
            return url_for('propostas.portal_cliente', token=token, _external=True)
    except Exception:
        pass
    base = _fallback_external_base()
    if base:
        return f"{base}/propostas/cliente/{token}"
    return None


def _portal_obra_url(obra) -> str | None:
    """URL pública do portal do CLIENTE para acompanhar a obra (se ativo).

    Mesma estratégia de fallback de :func:`_portal_proposta_url`.
    """
    if obra is None:
        return None
    if not getattr(obra, 'portal_ativo', False):
        return None
    token = getattr(obra, 'token_cliente', None)
    if not token:
        return None
    try:
        from flask import url_for, has_request_context
        if has_request_context():
            return url_for('portal_obras.portal_obra', token=token, _external=True)
    except Exception:
        pass
    base = _fallback_external_base()
    if base:
        return f"{base}/portal/obra/{token}"
    return None


def _safe_emit(event_name: str, payload: dict, admin_id: int | None) -> None:
    """Emite via EventManager engolindo qualquer exceção (best-effort)."""
    try:
        from event_manager import EventManager
        EventManager.emit(event_name, payload, admin_id)
    except Exception:
        logger.exception("[catalogo_eventos] falha ao emitir %r (best-effort)", event_name)


# ────────────────────────────────────────────────────────────────────────
# Propostas
# ────────────────────────────────────────────────────────────────────────
def _payload_proposta(proposta) -> dict:
    """Campos básicos comuns aos eventos de proposta."""
    portal_url = _portal_proposta_url(getattr(proposta, 'token_cliente', None))
    return {
        'proposta_id': proposta.id,
        'proposta_numero': proposta.numero,
        'proposta_versao': getattr(proposta, 'versao', 1) or 1,
        'cliente_nome': proposta.cliente_nome,
        'cliente_email': proposta.cliente_email or '',
        'cliente_telefone': proposta.cliente_telefone or '',
        'valor_total': _safe_float(getattr(proposta, 'valor_total', 0)),
        'portal_url': portal_url,
    }


def emit_proposta_aprovada(proposta, admin_id: int | None,
                           aprovada_por: str = 'admin') -> None:
    """Emite `proposta.aprovada`. `aprovada_por` ∈ {'admin','cliente'}."""
    payload = _payload_proposta(proposta)
    payload.update({
        'data_aprovacao': date.today().isoformat(),
        'aprovada_por': aprovada_por,
        'obra_id': getattr(proposta, 'obra_id', None),
    })
    _safe_emit('proposta.aprovada', payload, admin_id)


def emit_proposta_rejeitada(proposta, admin_id: int | None,
                            rejeitada_por: str = 'admin',
                            motivo: str = '') -> None:
    """Emite `proposta.rejeitada`. `rejeitada_por` ∈ {'admin','cliente'}."""
    payload = _payload_proposta(proposta)
    payload.update({
        'data_rejeicao': date.today().isoformat(),
        'rejeitada_por': rejeitada_por,
        'motivo': (motivo or '')[:500],
    })
    _safe_emit('proposta.rejeitada', payload, admin_id)


def emit_proposta_expirando(proposta, admin_id: int | None,
                            data_validade: date,
                            dias_restantes: int) -> None:
    """Emite `proposta.expirando` (lembrete pré-expiração da janela)."""
    payload = _payload_proposta(proposta)
    payload.update({
        'data_validade': _iso_date(data_validade),
        'dias_restantes': int(dias_restantes),
        'validade_dias': getattr(proposta, 'validade_dias', None),
    })
    _safe_emit('proposta.expirando', payload, admin_id)


# ────────────────────────────────────────────────────────────────────────
# Obras
# ────────────────────────────────────────────────────────────────────────
def _obra_lookup(obra_id: int | None, admin_id: int | None):
    """Carrega Obra defensivamente (None se falhar)."""
    if not obra_id:
        return None
    try:
        from models import Obra
        if admin_id is not None:
            return Obra.query.filter_by(id=obra_id, admin_id=admin_id).first()
        return Obra.query.get(obra_id)
    except Exception:
        logger.exception("[catalogo_eventos] obra_lookup falhou (obra_id=%s)", obra_id)
        return None


def _payload_obra_basico(obra) -> dict:
    """Campos básicos sobre a obra reusados em todos os eventos `obra.*`."""
    if obra is None:
        return {
            'obra_id': None,
            'obra_nome': None,
            'obra_codigo': None,
            'cliente_nome': None,
            'cliente_email': None,
            'cliente_telefone': None,
            'portal_obra_url': None,
        }
    cliente = getattr(obra, 'cliente', None)
    return {
        'obra_id': obra.id,
        'obra_nome': obra.nome,
        'obra_codigo': getattr(obra, 'codigo', None),
        'cliente_nome': getattr(cliente, 'nome', None) if cliente else None,
        'cliente_email': getattr(cliente, 'email', None) if cliente else None,
        'cliente_telefone': getattr(cliente, 'telefone', None) if cliente else None,
        'portal_obra_url': _portal_obra_url(obra),
    }


def _resumo_rdo(rdo) -> dict:
    """Conta defensiva de equipe / atividades para o payload do RDO."""
    resumo: dict[str, Any] = {
        'total_funcionarios': 0,
        'total_horas_trabalhadas': 0.0,
        'total_subatividades': 0,
        'percentual_medio': 0.0,
    }
    try:
        from models import RDOMaoObra, RDOServicoSubatividade
        mao = RDOMaoObra.query.filter_by(rdo_id=rdo.id).all()
        resumo['total_funcionarios'] = len(mao)
        resumo['total_horas_trabalhadas'] = round(
            sum(_safe_float(getattr(m, 'horas_trabalhadas', 0)) for m in mao), 2
        )
        subs = RDOServicoSubatividade.query.filter_by(rdo_id=rdo.id).all()
        resumo['total_subatividades'] = len(subs)
        if subs:
            resumo['percentual_medio'] = round(
                sum(_safe_float(getattr(s, 'percentual_conclusao', 0)) for s in subs) / len(subs), 2
            )
    except Exception:
        logger.exception("[catalogo_eventos] _resumo_rdo falhou (rdo_id=%s)", getattr(rdo, 'id', None))
    return resumo


def emit_obra_rdo_publicado(rdo, admin_id: int | None) -> None:
    """Emite `obra.rdo_publicado` em paralelo ao legado `rdo_finalizado`.

    Inclui resumo de equipe e atividades para que o consumidor n8n possa
    montar mensagens ricas (Slack/WhatsApp) sem segundo round-trip.
    """
    obra = _obra_lookup(getattr(rdo, 'obra_id', None), admin_id)
    payload = _payload_obra_basico(obra)
    payload.update({
        'rdo_id': rdo.id,
        'numero_rdo': getattr(rdo, 'numero_rdo', None),
        'data_relatorio': _iso_date(getattr(rdo, 'data_relatorio', None)),
        'status': getattr(rdo, 'status', None),
        'comentario_geral': (getattr(rdo, 'comentario_geral', '') or '')[:500],
    })
    payload.update(_resumo_rdo(rdo))
    _safe_emit('obra.rdo_publicado', payload, admin_id)


def emit_obra_medicao_publicada(medicao, admin_id: int | None) -> None:
    """Emite `obra.medicao_publicada` quando MedicaoObra é fechada (status='APROVADO')."""
    obra = _obra_lookup(getattr(medicao, 'obra_id', None), admin_id)
    payload = _payload_obra_basico(obra)
    payload.update({
        'medicao_id': medicao.id,
        'numero_medicao': getattr(medicao, 'numero', None),
        'valor_medido_periodo': _safe_float(getattr(medicao, 'valor_total_medido_periodo', 0)),
        'valor_a_faturar_periodo': _safe_float(getattr(medicao, 'valor_a_faturar_periodo', 0)),
        'percentual_executado': _safe_float(getattr(medicao, 'percentual_executado', 0)),
        'data_aprovacao': date.today().isoformat(),
    })
    _safe_emit('obra.medicao_publicada', payload, admin_id)


def emit_obra_cronograma_atualizado(obra, admin_id: int | None,
                                    tarefas_geradas: int = 0,
                                    motivo: str = 'revisao_inicial') -> None:
    """Emite `obra.cronograma_atualizado` (revisão inicial OU replanejamento)."""
    payload = _payload_obra_basico(obra)
    payload.update({
        'tarefas_geradas': int(tarefas_geradas or 0),
        'data_atualizacao': datetime.utcnow().strftime('%Y-%m-%dT%H:%M:%SZ'),
        'motivo': motivo,
    })
    _safe_emit('obra.cronograma_atualizado', payload, admin_id)


def emit_obra_concluida(obra, admin_id: int | None) -> None:
    """Emite `obra.concluida` quando Obra.status transita para 'Concluída'."""
    payload = _payload_obra_basico(obra)
    payload.update({
        'data_conclusao': date.today().isoformat(),
        'data_inicio': _iso_date(getattr(obra, 'data_inicio', None)),
        'data_previsao_fim': _iso_date(getattr(obra, 'data_previsao_fim', None)),
        'valor_contrato': _safe_float(getattr(obra, 'valor_contrato', 0)),
    })
    _safe_emit('obra.concluida', payload, admin_id)
