"""Task #76 — Alertas de estouro de orçamento por serviço.

Helpers para detectar quando um ObraServicoCusto ultrapassa o valor orçado
(realizado + a_realizar > valor_orcado) e materializar isso como uma
NotificacaoOrcamento persistida (1 por serviço, com upsert/idempotência).

Exporta:
    - servico_estourou(svc) -> dict | None
    - verificar_estouros_obra(obra_id, admin_id=None) -> list[dict]
    - listar_notificacoes_ativas(admin_id, obra_id=None) -> list[NotificacaoOrcamento]
    - marcar_resolvida(notif_id, admin_id) -> bool
"""
from __future__ import annotations

import logging
from datetime import datetime
from decimal import Decimal

logger = logging.getLogger(__name__)


def _f(v) -> float:
    if v is None:
        return 0.0
    if isinstance(v, Decimal):
        return float(v)
    try:
        return float(v)
    except (TypeError, ValueError):
        return 0.0


def servico_estourou(svc) -> dict | None:
    """Retorna dict com info do estouro ou None se está dentro do orçamento.

    Considera estouro quando (realizado_total + a_realizar_total) > valor_orcado
    e valor_orcado > 0. Serviços sem orçamento (valor_orcado = 0) não disparam
    alerta — não há referência para comparar.
    """
    valor_orcado = _f(getattr(svc, 'valor_orcado', 0))
    if valor_orcado <= 0:
        return None
    realizado = _f(getattr(svc, 'realizado_total', 0))
    a_realizar = _f(getattr(svc, 'a_realizar_total', 0))
    projetado = realizado + a_realizar
    if projetado <= valor_orcado:
        return None
    excesso = projetado - valor_orcado
    percentual = (projetado / valor_orcado) * 100.0
    return {
        'obra_servico_custo_id': svc.id,
        'nome': getattr(svc, 'nome', '') or '',
        'valor_orcado': round(valor_orcado, 2),
        'valor_projetado': round(projetado, 2),
        'realizado': round(realizado, 2),
        'a_realizar': round(a_realizar, 2),
        'excesso': round(excesso, 2),
        'percentual': round(percentual, 2),
    }


def _upsert_notificacao(admin_id, obra_id, info):
    from models import db, NotificacaoOrcamento
    notif = (
        NotificacaoOrcamento.query
        .filter_by(
            admin_id=admin_id,
            obra_id=obra_id,
            obra_servico_custo_id=info['obra_servico_custo_id'],
        )
        .first()
    )
    mensagem = (
        f"Serviço '{info['nome']}' estourou o orçamento: "
        f"projetado R$ {info['valor_projetado']:.2f} vs orçado R$ {info['valor_orcado']:.2f} "
        f"({info['percentual']:.1f}% — excesso R$ {info['excesso']:.2f})."
    )
    if notif is None:
        notif = NotificacaoOrcamento(
            admin_id=admin_id,
            obra_id=obra_id,
            obra_servico_custo_id=info['obra_servico_custo_id'],
            percentual=info['percentual'],
            valor_excesso=info['excesso'],
            valor_orcado=info['valor_orcado'],
            valor_projetado=info['valor_projetado'],
            mensagem=mensagem,
            ativa=True,
            resolvida_em=None,
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow(),
        )
        db.session.add(notif)
    else:
        notif.percentual = info['percentual']
        notif.valor_excesso = info['excesso']
        notif.valor_orcado = info['valor_orcado']
        notif.valor_projetado = info['valor_projetado']
        notif.mensagem = mensagem
        notif.ativa = True
        notif.resolvida_em = None
        notif.updated_at = datetime.utcnow()
    return notif


def _resolver_notificacao(admin_id, obra_id, obra_servico_custo_id):
    from models import NotificacaoOrcamento
    notif = (
        NotificacaoOrcamento.query
        .filter_by(
            admin_id=admin_id,
            obra_id=obra_id,
            obra_servico_custo_id=obra_servico_custo_id,
            ativa=True,
        )
        .first()
    )
    if notif is None:
        return False
    notif.ativa = False
    notif.resolvida_em = datetime.utcnow()
    notif.updated_at = datetime.utcnow()
    return True


def verificar_estouros_obra(obra_id, admin_id=None) -> list[dict]:
    """Sincroniza notificações de estouro para todos os serviços de uma obra.

    - Cria/atualiza NotificacaoOrcamento ativa para serviços que estouraram.
    - Marca como resolvida quem deixou de estourar.
    - Faz commit ao final (uma única transação).

    Retorna lista (possivelmente vazia) de dicts com info do estouro de cada
    serviço atualmente acima do orçado.
    """
    estouros: list[dict] = []
    try:
        from models import db, Obra, ObraServicoCusto

        obra = db.session.get(Obra, obra_id)
        if obra is None:
            return estouros
        tenant_admin_id = admin_id if admin_id is not None else obra.admin_id

        q = ObraServicoCusto.query.filter_by(obra_id=obra_id)
        if tenant_admin_id is not None:
            q = q.filter_by(admin_id=tenant_admin_id)
        servicos = q.all()

        for svc in servicos:
            info = servico_estourou(svc)
            if info is None:
                _resolver_notificacao(tenant_admin_id, obra_id, svc.id)
            else:
                _upsert_notificacao(tenant_admin_id, obra_id, info)
                estouros.append(info)

        db.session.commit()
    except Exception:
        logger.exception("verificar_estouros_obra(%s) falhou", obra_id)
        try:
            from models import db
            db.session.rollback()
        except Exception:
            pass
    return estouros


def listar_notificacoes_ativas(admin_id, obra_id=None):
    """Lista NotificacaoOrcamento ativas (por tenant; opcionalmente por obra)."""
    try:
        from models import NotificacaoOrcamento
        q = NotificacaoOrcamento.query.filter_by(admin_id=admin_id, ativa=True)
        if obra_id is not None:
            q = q.filter_by(obra_id=obra_id)
        return q.order_by(NotificacaoOrcamento.created_at.desc()).all()
    except Exception:
        logger.exception("listar_notificacoes_ativas falhou")
        return []


def marcar_resolvida(notif_id, admin_id) -> bool:
    """Marca manualmente uma notificação como resolvida."""
    try:
        from models import db, NotificacaoOrcamento
        notif = NotificacaoOrcamento.query.filter_by(
            id=notif_id, admin_id=admin_id
        ).first()
        if notif is None:
            return False
        notif.ativa = False
        notif.resolvida_em = datetime.utcnow()
        notif.updated_at = datetime.utcnow()
        db.session.commit()
        return True
    except Exception:
        logger.exception("marcar_resolvida(%s) falhou", notif_id)
        from models import db
        db.session.rollback()
        return False
