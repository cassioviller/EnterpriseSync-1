"""tests/test_webhook_dispatcher.py — Task #43

Cobertura unitária do despachante de webhooks para n8n
(`utils.webhook_dispatcher`):

* `sign_payload` / `verify_signature` — HMAC-SHA256 com `compare_digest`.
* `build_payload` — schema esperado pelo n8n.
* Allowlist — eventos fora dela são ignorados (no-op).
* `dispatch_webhook` em sucesso (2xx) → `WebhookEntrega.status == 'enviado'`.
* `dispatch_webhook` com 4xx → `status='falha'` (sem retry).
* `dispatch_webhook` com 5xx → `status='pendente'` + backoff agendado.
* Erro de rede → idem 5xx (pendente).
* Backoff respeita o array `RETRY_BACKOFF_SECONDS` por número de tentativa.
* Após `MAX_TENTATIVAS` falhas, status final é `falha` permanente.
* `reentregar_uma` reseta tentativas e tenta de novo.

Cada teste usa transação isolada (rollback no fim) e mocka `_post_to_n8n`
para nunca tocar a rede.
"""
import json
import os
import sys
from datetime import datetime, timedelta
from unittest.mock import patch

import pytest

sys.path.insert(0, os.path.abspath(os.path.dirname(__file__) + '/..'))

from app import app, db  # noqa: E402
from models import WebhookEntrega  # noqa: E402
from utils import webhook_dispatcher as wd  # noqa: E402


# ────────────────────────────────────────────────────────────────────────
# Fixtures
# ────────────────────────────────────────────────────────────────────────
@pytest.fixture
def app_ctx():
    with app.app_context():
        yield


@pytest.fixture
def webhook_ligado(monkeypatch):
    """Liga o webhook (URL + segredo) e adiciona um evento de teste na allowlist."""
    monkeypatch.setenv('N8N_WEBHOOK_URL', 'https://n8n.fake/webhook/teste')
    monkeypatch.setenv('N8N_WEBHOOK_SECRET', 'segredo-de-teste-123')
    # mexer na allowlist exige limpar depois
    original = set(wd.WEBHOOK_EVENT_ALLOWLIST)
    wd.WEBHOOK_EVENT_ALLOWLIST.add('teste.evento')
    try:
        yield
    finally:
        wd.WEBHOOK_EVENT_ALLOWLIST.clear()
        wd.WEBHOOK_EVENT_ALLOWLIST.update(original)


@pytest.fixture
def limpar_entregas(app_ctx):
    """Apaga linhas criadas no teste para isolar o banco."""
    criadas: list[int] = []
    yield criadas
    if criadas:
        WebhookEntrega.query.filter(WebhookEntrega.id.in_(criadas)).delete(
            synchronize_session=False
        )
        db.session.commit()


def _coletar_novos(limpar_entregas):
    """Após o teste, registra todos os ids criados pra cleanup."""
    novos = [
        e.id for e in
        WebhookEntrega.query.filter(WebhookEntrega.event == 'teste.evento').all()
    ]
    limpar_entregas.extend(novos)
    return novos


# ────────────────────────────────────────────────────────────────────────
# HMAC
# ────────────────────────────────────────────────────────────────────────
class TestHmac:
    def test_sign_payload_devolve_hex_64chars(self):
        sig = wd.sign_payload(b'{"x":1}', 'segredo')
        assert isinstance(sig, str)
        assert len(sig) == 64
        # hex puro
        int(sig, 16)

    def test_sign_payload_sem_segredo_e_none(self):
        assert wd.sign_payload(b'{"x":1}', None) is None
        assert wd.sign_payload(b'{"x":1}', '') is None

    def test_sign_payload_e_deterministico(self):
        a = wd.sign_payload(b'{"a":1}', 'seg')
        b = wd.sign_payload(b'{"a":1}', 'seg')
        assert a == b

    def test_sign_payload_muda_com_segredo_diferente(self):
        a = wd.sign_payload(b'{"a":1}', 'segA')
        b = wd.sign_payload(b'{"a":1}', 'segB')
        assert a != b

    def test_verify_signature_ok(self):
        body = b'{"event":"x"}'
        sig = wd.sign_payload(body, 'seg')
        assert wd.verify_signature(body, sig, 'seg') is True

    def test_verify_signature_falsa_e_recusada(self):
        body = b'{"event":"x"}'
        sig = wd.sign_payload(body, 'seg')
        assert wd.verify_signature(b'outro_corpo', sig, 'seg') is False
        assert wd.verify_signature(body, 'a' * 64, 'seg') is False

    def test_verify_signature_sem_segredo(self):
        body = b'{"event":"x"}'
        assert wd.verify_signature(body, 'qualquer', '') is False


# ────────────────────────────────────────────────────────────────────────
# Payload
# ────────────────────────────────────────────────────────────────────────
class TestPayload:
    def test_build_payload_tem_campos_padrao(self):
        p = wd.build_payload('proposta.enviada', {'x': 1}, admin_id=42)
        assert p['event'] == 'proposta.enviada'
        assert p['admin_id'] == 42
        assert p['data'] == {'x': 1}
        assert p['source'] == 'obra'
        # ISO-8601 UTC com Z
        assert p['occurred_at'].endswith('Z')
        # parse de validação
        datetime.strptime(p['occurred_at'], '%Y-%m-%dT%H:%M:%SZ')

    def test_build_payload_aceita_admin_none(self):
        p = wd.build_payload('e.v', {}, admin_id=None)
        assert p['admin_id'] is None

    def test_dump_payload_preserva_acentos(self):
        body = wd._dump_payload({'msg': 'descrição'})
        assert 'descrição' in body.decode('utf-8')

    def test_dump_payload_serializa_datetime(self):
        body = wd._dump_payload({'when': datetime(2026, 4, 30, 12, 0, 0)})
        # vira string ISO via _serialize_default
        assert b'2026-04-30T12:00:00' in body


# ────────────────────────────────────────────────────────────────────────
# Allowlist
# ────────────────────────────────────────────────────────────────────────
class TestAllowlist:
    def test_evento_fora_da_allowlist_e_ignorado(self, app_ctx, webhook_ligado):
        # 'evento.nao.permitido' NÃO foi adicionado à allowlist no fixture.
        with patch.object(wd, '_post_to_n8n') as post_mock:
            ok = wd.dispatch_webhook('evento.nao.permitido', {'x': 1}, admin_id=1)
        assert ok is False
        post_mock.assert_not_called()
        # nenhuma linha persistida
        existe = (
            WebhookEntrega.query
            .filter(WebhookEntrega.event == 'evento.nao.permitido')
            .first()
        )
        assert existe is None

    def test_canal_desligado_nao_persiste(self, app_ctx, monkeypatch):
        monkeypatch.delenv('N8N_WEBHOOK_URL', raising=False)
        wd.WEBHOOK_EVENT_ALLOWLIST.add('teste.evento')
        try:
            with patch.object(wd, '_post_to_n8n') as post_mock:
                ok = wd.dispatch_webhook('teste.evento', {'x': 1}, admin_id=1)
            assert ok is False
            post_mock.assert_not_called()
            existe = (
                WebhookEntrega.query
                .filter(WebhookEntrega.event == 'teste.evento')
                .first()
            )
            assert existe is None
        finally:
            wd.WEBHOOK_EVENT_ALLOWLIST.discard('teste.evento')


# ────────────────────────────────────────────────────────────────────────
# Dispatch — caminho feliz e falhas
# ────────────────────────────────────────────────────────────────────────
class TestDispatch:
    def test_sucesso_2xx_marca_enviado(self, app_ctx, webhook_ligado, limpar_entregas):
        with patch.object(wd, '_post_to_n8n', return_value=(200, 'OK')):
            ok = wd.dispatch_webhook('teste.evento', {'k': 'v'}, admin_id=None)
        assert ok is True
        criados = _coletar_novos(limpar_entregas)
        assert len(criados) == 1
        e = db.session.get(WebhookEntrega, criados[0])
        assert e.status == 'enviado'
        assert e.tentativas == 1
        assert e.sent_at is not None
        assert e.proxima_tentativa_em is None

    def test_4xx_e_falha_permanente_sem_retry(
        self, app_ctx, webhook_ligado, limpar_entregas
    ):
        with patch.object(wd, '_post_to_n8n', return_value=(400, 'Bad Request')):
            ok = wd.dispatch_webhook('teste.evento', {}, admin_id=None)
        assert ok is False
        criados = _coletar_novos(limpar_entregas)
        e = db.session.get(WebhookEntrega, criados[0])
        assert e.status == 'falha'
        assert e.tentativas == 1
        assert e.proxima_tentativa_em is None
        assert 'HTTP 400' in (e.ultimo_erro or '')

    def test_5xx_agenda_retry_com_backoff_de_60s(
        self, app_ctx, webhook_ligado, limpar_entregas
    ):
        antes = datetime.utcnow()
        with patch.object(wd, '_post_to_n8n', return_value=(500, 'boom')):
            ok = wd.dispatch_webhook('teste.evento', {}, admin_id=None)
        assert ok is False
        criados = _coletar_novos(limpar_entregas)
        e = db.session.get(WebhookEntrega, criados[0])
        assert e.status == 'pendente'
        assert e.tentativas == 1
        # 1ª retry → +60s; tolerância de 5s
        delta = (e.proxima_tentativa_em - antes).total_seconds()
        assert 55 <= delta <= 75
        assert 'HTTP 500' in (e.ultimo_erro or '')

    def test_erro_de_rede_agenda_retry(
        self, app_ctx, webhook_ligado, limpar_entregas
    ):
        with patch.object(
            wd, '_post_to_n8n', side_effect=Exception('connection refused')
        ):
            ok = wd.dispatch_webhook('teste.evento', {}, admin_id=None)
        assert ok is False
        criados = _coletar_novos(limpar_entregas)
        e = db.session.get(WebhookEntrega, criados[0])
        assert e.status == 'pendente'
        assert e.tentativas == 1
        assert 'network' in (e.ultimo_erro or '').lower()

    def test_post_recebe_corpo_e_assinatura(
        self, app_ctx, webhook_ligado, limpar_entregas
    ):
        captura = {}

        def _fake(url, body, signature):
            captura['url'] = url
            captura['body'] = body
            captura['signature'] = signature
            return (204, '')

        with patch.object(wd, '_post_to_n8n', side_effect=_fake):
            wd.dispatch_webhook('teste.evento', {'a': 1}, admin_id=7)

        _coletar_novos(limpar_entregas)
        assert captura['url'] == 'https://n8n.fake/webhook/teste'
        # corpo é JSON válido com schema esperado
        decodificado = json.loads(captura['body'].decode('utf-8'))
        assert decodificado['event'] == 'teste.evento'
        assert decodificado['admin_id'] == 7
        assert decodificado['data'] == {'a': 1}
        # assinatura confere com o segredo do fixture
        assert wd.verify_signature(
            captura['body'], captura['signature'], 'segredo-de-teste-123'
        )


# ────────────────────────────────────────────────────────────────────────
# Backoff & MAX_TENTATIVAS via _mark_attempt_failed
# ────────────────────────────────────────────────────────────────────────
class TestBackoff:
    """Cobre o ciclo completo: 1ª falha → +60s, 2ª → +5m, 3ª → +15m,
    4ª → falha permanente. (3 retries reais, todas as janelas exercitadas.)"""

    def test_segunda_falha_usa_5min(self, app_ctx, webhook_ligado, limpar_entregas):
        # 1ª tentativa: 5xx → tentativas=1, agenda +60s
        with patch.object(wd, '_post_to_n8n', return_value=(500, 'x')):
            wd.dispatch_webhook('teste.evento', {}, admin_id=None)
        criados = _coletar_novos(limpar_entregas)
        eid = criados[0]

        antes = datetime.utcnow()
        wd._mark_attempt_failed(eid, erro='HTTP 500')
        e = db.session.get(WebhookEntrega, eid)
        assert e.tentativas == 2
        assert e.status == 'pendente'
        delta = (e.proxima_tentativa_em - antes).total_seconds()
        # 2ª retry → 5 minutos
        assert 290 <= delta <= 310

    def test_terceira_falha_usa_15min(
        self, app_ctx, webhook_ligado, limpar_entregas
    ):
        # 1ª tentativa: 5xx → tentativas=1, agenda +60s
        with patch.object(wd, '_post_to_n8n', return_value=(500, 'x')):
            wd.dispatch_webhook('teste.evento', {}, admin_id=None)
        criados = _coletar_novos(limpar_entregas)
        eid = criados[0]

        wd._mark_attempt_failed(eid, erro='HTTP 500')  # 2ª (pendente, +5m)
        antes = datetime.utcnow()
        wd._mark_attempt_failed(eid, erro='HTTP 500')  # 3ª (pendente, +15m)

        e = db.session.get(WebhookEntrega, eid)
        assert e.tentativas == 3
        assert e.status == 'pendente'
        delta = (e.proxima_tentativa_em - antes).total_seconds()
        # 3ª retry → 15 minutos (com tolerância de ±10s)
        assert 890 <= delta <= 910

    def test_quarta_falha_marca_permanente(
        self, app_ctx, webhook_ligado, limpar_entregas
    ):
        # Cenário: a 1ª tentativa (do dispatch original) e 3 retries
        # subsequentes falham — a 4ª falha vira `falha` permanente.
        with patch.object(wd, '_post_to_n8n', return_value=(500, 'x')):
            wd.dispatch_webhook('teste.evento', {}, admin_id=None)
        criados = _coletar_novos(limpar_entregas)
        eid = criados[0]

        wd._mark_attempt_failed(eid, erro='HTTP 500')  # 2ª (pendente, +5m)
        wd._mark_attempt_failed(eid, erro='HTTP 500')  # 3ª (pendente, +15m)
        wd._mark_attempt_failed(eid, erro='HTTP 500')  # 4ª → falha permanente

        e = db.session.get(WebhookEntrega, eid)
        assert e.tentativas == 4
        assert e.status == 'falha'
        assert e.proxima_tentativa_em is None

    def test_max_tentativas_iguala_backoff_mais_um(self):
        """A constante MAX_TENTATIVAS deve refletir 1 inicial + N retries
        (onde N é o tamanho da tabela de backoff). Garante que ninguém
        vai mexer numa coisa sem mexer na outra."""
        assert wd.MAX_TENTATIVAS == len(wd.RETRY_BACKOFF_SECONDS) + 1


# ────────────────────────────────────────────────────────────────────────
# reentregar_uma (botão admin)
# ────────────────────────────────────────────────────────────────────────
class TestReentregar:
    def test_reentregar_uma_reseta_e_envia(
        self, app_ctx, webhook_ligado, limpar_entregas
    ):
        # Cria uma falha permanente.
        with patch.object(wd, '_post_to_n8n', return_value=(400, 'Bad')):
            wd.dispatch_webhook('teste.evento', {'a': 1}, admin_id=None)
        criados = _coletar_novos(limpar_entregas)
        eid = criados[0]
        e0 = db.session.get(WebhookEntrega, eid)
        assert e0.status == 'falha'
        assert e0.tentativas == 1

        # Admin clica "reenviar" e dessa vez o n8n responde 200.
        with patch.object(wd, '_post_to_n8n', return_value=(200, 'OK')):
            ok = wd.reentregar_uma(eid)
        assert ok is True
        e1 = db.session.get(WebhookEntrega, eid)
        assert e1.status == 'enviado'
        # tentativas reseta para 0 e o sucesso conta 1.
        assert e1.tentativas == 1
        assert e1.sent_at is not None
