"""Task #43 — Despachante de webhooks para n8n.

Esta é a "fundação reutilizável" de notificações externas: qualquer evento
emitido via :class:`event_manager.EventManager` que esteja na ALLOWLIST
declarada aqui pode, opcionalmente, ser entregue ao n8n via HTTP POST
assinado com HMAC-SHA256 (header ``X-Signature``).

Pontos importantes:

* **Opt-in por configuração** — se ``N8N_WEBHOOK_URL`` não estiver no
  ambiente, o módulo não envia nada (no-op). Nada quebra.
* **Allowlist explícita** — ``WEBHOOK_EVENT_ALLOWLIST`` começa **vazia**
  para que nenhum evento vaze por engano. Tarefas seguintes (como a
  notificação de proposta enviada) adicionam o que precisarem.
* **Idempotência da fila** — toda tentativa, sucesso ou falha, vai parar
  na tabela :class:`models.WebhookEntrega` para auditoria e retry.
* **Retry com backoff** — falhas de rede/HTTP 5xx ficam em ``status='pendente'``
  e são reprocessadas pelo job de retry com janelas 1 min → 5 min → 15 min.
  Após 3 tentativas, ``status='falha'`` (falha permanente).

A rotina é segura por design: nunca propaga exceção para o handler chamador
(``dispatch_webhook`` engole tudo internamente), porque webhooks são um
canal **best-effort** — não devem derrubar a transação de negócio que os
disparou.
"""
from __future__ import annotations

import hashlib
import hmac
import json
import logging
import os
import threading
import time
from datetime import datetime, timedelta
from typing import Any

logger = logging.getLogger(__name__)


# Nome do "source" embutido em todo payload — útil para o n8n filtrar
# eventos vindos de instâncias diferentes (homologação x produção, etc.).
WEBHOOK_SOURCE = "obra"

# Allowlist de eventos que PODEM sair para o n8n.
# Convenção de nomenclatura: "dominio.acao" (ex.: "proposta.enviada").
#
# Task #45 — catálogo inicial de eventos do sistema. Cada nome aqui é
# emitido EM PARALELO ao evento legado correspondente (proposta_aprovada,
# rdo_finalizado etc.) — os legados continuam orquestrando handlers
# internos de negócio; estes nomes em formato `dominio.acao` saem pelo
# canal externo do n8n. Veja `docs/notificacoes/README.md` para a
# tabela completa (campos do payload, ponto de emissão, exemplo n8n).
WEBHOOK_EVENT_ALLOWLIST: set[str] = {
    # — Propostas comerciais —
    # `proposta.enviada` é dono da Task #44 (em paralelo); reservado aqui
    # para coexistência: como o tipo é ``set``, o merge é idempotente —
    # se a outra task já registra esta chave, não há conflito; se ela não
    # emitir, esta entrada é benigna (nenhum código aqui dispara o evento).
    "proposta.enviada",
    "proposta.aprovada",
    "proposta.rejeitada",
    "proposta.expirando",
    # — Obras —
    "obra.rdo_publicado",
    "obra.medicao_publicada",
    "obra.cronograma_atualizado",
    "obra.concluida",
}

# Backoff em segundos por número da tentativa que acabou de falhar.
# Tabela completa do ciclo de vida com `MAX_TENTATIVAS = 4`:
#   tentativa 1 falha → agenda nova em +60s   (RETRY_BACKOFF_SECONDS[0])
#   tentativa 2 falha → agenda nova em +5m    (RETRY_BACKOFF_SECONDS[1])
#   tentativa 3 falha → agenda nova em +15m   (RETRY_BACKOFF_SECONDS[2])
#   tentativa 4 falha → status='falha' (permanente).
# Em outras palavras, a 1ª tentativa é o disparo original e há até 3 *retries*
# subsequentes — o 1m/5m/15m do contrato é cumprido por inteiro.
RETRY_BACKOFF_SECONDS = [60, 5 * 60, 15 * 60]
MAX_TENTATIVAS = len(RETRY_BACKOFF_SECONDS) + 1  # = 4 (1 inicial + 3 retries)
HTTP_TIMEOUT_SECONDS = 5

# Loop interno de retry — uma única thread daemon, intervalo curto.
_RETRY_LOOP_INTERVAL_SECONDS = 30
_retry_thread_started = False
_retry_thread_lock = threading.Lock()


# ────────────────────────────────────────────────────────────────────────
# Configuração
# ────────────────────────────────────────────────────────────────────────
def get_webhook_url() -> str | None:
    """URL do webhook do n8n. ``None`` desliga todo o despachante."""
    url = os.environ.get("N8N_WEBHOOK_URL", "").strip()
    return url or None


def get_webhook_secret() -> str | None:
    """Segredo HMAC. ``None`` deixa as requisições sem assinatura
    (modo "ambiente de teste sem segredo")."""
    secret = os.environ.get("N8N_WEBHOOK_SECRET", "").strip()
    return secret or None


def is_enabled() -> bool:
    """True quando há URL configurada (segredo é opcional)."""
    return get_webhook_url() is not None


# ────────────────────────────────────────────────────────────────────────
# Assinatura HMAC
# ────────────────────────────────────────────────────────────────────────
def sign_payload(body: bytes, secret: str | None) -> str | None:
    """Assina um corpo JSON serializado com HMAC-SHA256.

    Devolve a assinatura em hex; ``None`` quando não há segredo configurado
    (o n8n pode optar por aceitar mesmo sem assinatura em ambientes de teste).
    """
    if not secret:
        return None
    if isinstance(body, str):
        body = body.encode("utf-8")
    return hmac.new(secret.encode("utf-8"), body, hashlib.sha256).hexdigest()


def verify_signature(body: bytes, signature: str, secret: str) -> bool:
    """Valida ``X-Signature`` (útil para testes e para o n8n implementar igual)."""
    expected = sign_payload(body, secret)
    if expected is None or not signature:
        return False
    return hmac.compare_digest(expected, signature)


# ────────────────────────────────────────────────────────────────────────
# Payload
# ────────────────────────────────────────────────────────────────────────
def build_payload(event: str, data: dict, admin_id: int | None) -> dict:
    """Monta o payload padrão entregue ao n8n.

    Convenção:

    * ``event`` — nome do evento (ex.: ``proposta.enviada``).
    * ``occurred_at`` — ISO-8601 UTC (com sufixo ``Z``) do disparo.
    * ``admin_id`` — tenant que originou o evento (ou ``None``).
    * ``data`` — dict original passado ao :meth:`EventManager.emit`.
    * ``source`` — sempre ``"obra"`` (este sistema).
    """
    return {
        "event": event,
        "occurred_at": datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ"),
        "admin_id": admin_id,
        "data": data,
        "source": WEBHOOK_SOURCE,
    }


def _serialize_default(o: Any) -> str:
    """Serializa objetos não-JSON-nativos (datetime, Decimal, etc.) como string."""
    try:
        from datetime import date, time as dtime
        from decimal import Decimal
        if isinstance(o, (datetime, date, dtime)):
            return o.isoformat()
        if isinstance(o, Decimal):
            return str(o)
    except Exception:
        pass
    return str(o)


def _dump_payload(payload: dict) -> bytes:
    """Serializa o payload de forma estável (separadores fixos)."""
    return json.dumps(
        payload, default=_serialize_default, ensure_ascii=False,
        separators=(",", ":"),
    ).encode("utf-8")


# ────────────────────────────────────────────────────────────────────────
# HTTP — wrapper testável
# ────────────────────────────────────────────────────────────────────────
def _post_to_n8n(url: str, body: bytes, signature: str | None) -> tuple[int, str]:
    """POST cru para o n8n. Retorna (status_code, mensagem_curta).

    Levanta exceção para erros de rede/timeout (capturado pelo chamador).
    """
    import requests
    headers = {"Content-Type": "application/json; charset=utf-8"}
    if signature:
        headers["X-Signature"] = signature
    resp = requests.post(url, data=body, headers=headers, timeout=HTTP_TIMEOUT_SECONDS)
    return resp.status_code, (resp.text or "")[:500]


# ────────────────────────────────────────────────────────────────────────
# Despachante principal
# ────────────────────────────────────────────────────────────────────────
def dispatch_webhook(event: str, data: dict, admin_id: int | None) -> bool:
    """Tenta entregar um evento ao n8n.

    Pipeline:

    1. Se a allowlist NÃO contém o evento → ignora (silencioso).
    2. Se webhook está desligado (sem URL) → grava ``WebhookEntrega`` com
       status 'enviado'? Não — apenas faz log e não persiste nada (canal
       desligado = "como se o evento não existisse para o mundo externo").
    3. Cria ``WebhookEntrega(status='pendente')`` ANTES do POST, para ter
       linha de auditoria mesmo se o processo morrer no meio.
    4. POST com timeout curto.
       * Sucesso (2xx) → atualiza para ``status='enviado'``.
       * Erro de rede / 5xx → mantém ``status='pendente'`` com
         ``proxima_tentativa_em`` calculada pelo backoff.
       * 4xx → ``status='falha'`` (não vale retry — payload é o problema).

    Retorna ``True`` se o POST foi aceito (2xx), ``False`` caso contrário
    ou quando o evento não está na allowlist / webhook está desligado.
    Nunca propaga exceção.
    """
    if event not in WEBHOOK_EVENT_ALLOWLIST:
        logger.debug("[webhook] evento %r não está na allowlist — ignorado", event)
        return False

    url = get_webhook_url()
    if not url:
        logger.debug("[webhook] N8N_WEBHOOK_URL não configurado — evento %r ignorado", event)
        return False

    secret = get_webhook_secret()
    payload = build_payload(event, data, admin_id)
    body = _dump_payload(payload)
    signature = sign_payload(body, secret)

    # 3) Persiste a tentativa antes do POST.
    entrega_id = _persist_pending(event, payload, admin_id)

    # 4) POST.
    try:
        status_code, msg = _post_to_n8n(url, body, signature)
    except Exception as e:
        logger.warning("[webhook] falha de rede em %r: %s", event, e)
        _mark_attempt_failed(entrega_id, erro=f"network: {e}")
        return False

    if 200 <= status_code < 300:
        _mark_sent(entrega_id)
        logger.info("[webhook] %r entregue (HTTP %s)", event, status_code)
        return True

    # 4xx — falha permanente (request ruim, n8n recusou).
    if 400 <= status_code < 500:
        _mark_permanent_failure(
            entrega_id, erro=f"HTTP {status_code}: {msg}",
        )
        logger.warning("[webhook] %r recusado (HTTP %s) — falha permanente", event, status_code)
        return False

    # 5xx — falha transitória, agendar retry.
    _mark_attempt_failed(entrega_id, erro=f"HTTP {status_code}: {msg}")
    logger.warning("[webhook] %r erro transitório (HTTP %s) — agendado retry", event, status_code)
    return False


# ────────────────────────────────────────────────────────────────────────
# Persistência (cada operação em commit isolado p/ não derrubar a transação
# de negócio chamadora)
# ────────────────────────────────────────────────────────────────────────
def _persist_pending(event: str, payload: dict, admin_id: int | None) -> int | None:
    """Cria ``WebhookEntrega(status='pendente')`` e devolve o id (ou None em erro)."""
    try:
        from models import db, WebhookEntrega
        entrega = WebhookEntrega(
            event=event,
            payload=payload,
            status='pendente',
            tentativas=0,
            admin_id=admin_id,
            created_at=datetime.utcnow(),
        )
        db.session.add(entrega)
        db.session.commit()
        return entrega.id
    except Exception:
        logger.exception("[webhook] erro ao persistir WebhookEntrega pendente")
        try:
            from models import db
            db.session.rollback()
        except Exception:
            pass
        return None


def _mark_sent(entrega_id: int | None) -> None:
    if entrega_id is None:
        return
    try:
        from models import db, WebhookEntrega
        entrega = db.session.get(WebhookEntrega, entrega_id)
        if entrega is None:
            return
        entrega.status = 'enviado'
        entrega.tentativas = (entrega.tentativas or 0) + 1
        entrega.sent_at = datetime.utcnow()
        entrega.proxima_tentativa_em = None
        db.session.commit()
    except Exception:
        logger.exception("[webhook] erro ao marcar entrega %s como enviada", entrega_id)
        try:
            from models import db
            db.session.rollback()
        except Exception:
            pass


def _mark_attempt_failed(entrega_id: int | None, erro: str) -> None:
    """Incrementa tentativas; agenda retry ou marca falha permanente."""
    if entrega_id is None:
        return
    try:
        from models import db, WebhookEntrega
        entrega = db.session.get(WebhookEntrega, entrega_id)
        if entrega is None:
            return
        entrega.tentativas = (entrega.tentativas or 0) + 1
        entrega.ultimo_erro = erro[:2000] if erro else None
        if entrega.tentativas >= MAX_TENTATIVAS:
            entrega.status = 'falha'
            entrega.proxima_tentativa_em = None
        else:
            backoff_idx = min(entrega.tentativas - 1, len(RETRY_BACKOFF_SECONDS) - 1)
            entrega.status = 'pendente'
            entrega.proxima_tentativa_em = (
                datetime.utcnow() + timedelta(seconds=RETRY_BACKOFF_SECONDS[backoff_idx])
            )
        db.session.commit()
    except Exception:
        logger.exception("[webhook] erro ao marcar entrega %s com falha", entrega_id)
        try:
            from models import db
            db.session.rollback()
        except Exception:
            pass


def _mark_permanent_failure(entrega_id: int | None, erro: str) -> None:
    if entrega_id is None:
        return
    try:
        from models import db, WebhookEntrega
        entrega = db.session.get(WebhookEntrega, entrega_id)
        if entrega is None:
            return
        entrega.status = 'falha'
        entrega.tentativas = (entrega.tentativas or 0) + 1
        entrega.ultimo_erro = erro[:2000] if erro else None
        entrega.proxima_tentativa_em = None
        db.session.commit()
    except Exception:
        logger.exception("[webhook] erro ao marcar entrega %s falha permanente", entrega_id)
        try:
            from models import db
            db.session.rollback()
        except Exception:
            pass


# ────────────────────────────────────────────────────────────────────────
# Job de retry
# ────────────────────────────────────────────────────────────────────────
def reentregar_pendentes(now: datetime | None = None, limit: int = 50) -> int:
    """Reprocessa entregas pendentes elegíveis (proxima_tentativa_em <= agora).

    Retorna a quantidade processada (com sucesso ou nova falha — total tentado).
    Usado tanto pelo loop interno quanto, se quiser, por um endpoint admin.
    """
    if not is_enabled():
        return 0
    try:
        from models import db, WebhookEntrega
        now = now or datetime.utcnow()
        pendentes = (
            WebhookEntrega.query
            .filter(WebhookEntrega.status == 'pendente')
            .filter(
                (WebhookEntrega.proxima_tentativa_em == None)  # noqa: E711
                | (WebhookEntrega.proxima_tentativa_em <= now)
            )
            .order_by(WebhookEntrega.created_at.asc())
            .limit(limit)
            .all()
        )
    except Exception:
        logger.exception("[webhook] erro ao buscar pendentes")
        return 0

    if not pendentes:
        return 0

    processados = 0
    url = get_webhook_url()
    secret = get_webhook_secret()

    for entrega in pendentes:
        processados += 1
        try:
            body = _dump_payload(entrega.payload or {})
            signature = sign_payload(body, secret)
            try:
                status_code, msg = _post_to_n8n(url, body, signature)
            except Exception as e:
                _mark_attempt_failed(entrega.id, erro=f"network: {e}")
                continue
            if 200 <= status_code < 300:
                _mark_sent(entrega.id)
            elif 400 <= status_code < 500:
                _mark_permanent_failure(entrega.id, erro=f"HTTP {status_code}: {msg}")
            else:
                _mark_attempt_failed(entrega.id, erro=f"HTTP {status_code}: {msg}")
        except Exception:
            logger.exception("[webhook] erro inesperado reentregando id=%s", entrega.id)
    return processados


def reentregar_uma(entrega_id: int) -> bool:
    """Forçar nova tentativa de uma entrega específica (botão admin).

    Reset ``tentativas`` para 0 antes de tentar (admin assumiu o controle).
    Retorna True se entregue com sucesso.
    """
    if not is_enabled():
        return False
    try:
        from models import db, WebhookEntrega
        entrega = db.session.get(WebhookEntrega, entrega_id)
        if entrega is None:
            return False
        entrega.tentativas = 0
        entrega.status = 'pendente'
        entrega.proxima_tentativa_em = None
        db.session.commit()
    except Exception:
        logger.exception("[webhook] erro ao resetar entrega %s", entrega_id)
        try:
            from models import db
            db.session.rollback()
        except Exception:
            pass
        return False

    body = _dump_payload(entrega.payload or {})
    secret = get_webhook_secret()
    signature = sign_payload(body, secret)
    try:
        status_code, msg = _post_to_n8n(get_webhook_url(), body, signature)
    except Exception as e:
        _mark_attempt_failed(entrega_id, erro=f"network: {e}")
        return False
    if 200 <= status_code < 300:
        _mark_sent(entrega_id)
        return True
    if 400 <= status_code < 500:
        _mark_permanent_failure(entrega_id, erro=f"HTTP {status_code}: {msg}")
        return False
    _mark_attempt_failed(entrega_id, erro=f"HTTP {status_code}: {msg}")
    return False


# ────────────────────────────────────────────────────────────────────────
# Listener universal + bootstrap
# ────────────────────────────────────────────────────────────────────────
def _universal_listener_factory(event_name: str):
    """Cria um handler que dispara o webhook para o evento dado."""
    def _handler(data: dict, admin_id: int):
        try:
            dispatch_webhook(event_name, data or {}, admin_id)
        except Exception:
            # Webhook é best-effort — não quebra o pipeline de negócio.
            logger.exception("[webhook] handler universal falhou em %r", event_name)
    _handler.__name__ = f"webhook_emit_{event_name.replace('.', '_')}"
    return _handler


def register_universal_listener() -> int:
    """Registra um handler para CADA evento da allowlist no EventManager.

    Idempotente: se o handler já existe, não duplica. Retorna a quantidade
    de novos handlers registrados.
    """
    from event_manager import EventManager
    novos = 0
    for event_name in sorted(WEBHOOK_EVENT_ALLOWLIST):
        handlers = EventManager._handlers.get(event_name, [])
        ja_registrado = any(
            getattr(h, "__name__", "") == f"webhook_emit_{event_name.replace('.', '_')}"
            for h in handlers
        )
        if ja_registrado:
            continue
        EventManager.register(event_name, _universal_listener_factory(event_name))
        novos += 1
    if novos:
        logger.info("[webhook] %d listener(s) universal(is) registrados na allowlist", novos)
    return novos


def _retry_loop(app):
    """Loop interno: a cada N segundos, reprocessa pendentes elegíveis."""
    logger.info(
        "[webhook] retry loop iniciado (intervalo=%ds, max_tentativas=%d, backoff=%s)",
        _RETRY_LOOP_INTERVAL_SECONDS, MAX_TENTATIVAS, RETRY_BACKOFF_SECONDS,
    )
    while True:
        try:
            time.sleep(_RETRY_LOOP_INTERVAL_SECONDS)
            with app.app_context():
                reentregar_pendentes()
        except Exception:
            logger.exception("[webhook] erro no retry loop — continuando")


def start_retry_loop(app) -> bool:
    """Inicia uma única thread daemon de retry (idempotente).

    Devolve True se uma nova thread foi iniciada; False se já estava rodando
    ou se o webhook está desligado.
    """
    global _retry_thread_started
    with _retry_thread_lock:
        if _retry_thread_started:
            return False
        if not is_enabled():
            logger.debug("[webhook] retry loop não iniciado (webhook desligado)")
            return False
        t = threading.Thread(
            target=_retry_loop, args=(app,), name="webhook-retry", daemon=True,
        )
        t.start()
        _retry_thread_started = True
        return True


def init_app(app) -> None:
    """Bootstrap: registra listener universal + dispara o loop de retry.

    Seguro de chamar no boot da aplicação. No-op se a allowlist está vazia
    ou se o webhook está desligado por configuração.
    """
    try:
        register_universal_listener()
    except Exception:
        logger.exception("[webhook] falha ao registrar listener universal")
    try:
        start_retry_loop(app)
    except Exception:
        logger.exception("[webhook] falha ao iniciar retry loop")
