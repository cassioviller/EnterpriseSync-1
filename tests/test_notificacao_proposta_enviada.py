"""tests/test_notificacao_proposta_enviada.py — Task #44

Cobertura unitária de:

* `_telefone_so_digitos` — normalização BR (com/sem DDI, formato livre).
* `_whatsapp_url_proposta` — wa.me + DDI + texto pré-preenchido + None
  quando falta telefone.
* `proposta.enviada` está na ``WEBHOOK_EVENT_ALLOWLIST``.
* `_notificar_envio_proposta` —
    - emite evento com payload no schema esperado pelo n8n;
    - registra ``PropostaHistorico('notificacao_disparada')``;
    - faz ``flash('warning')`` quando faltam e-mail/telefone.
* Rota ``POST /propostas/<id>/whatsapp/registrar`` cria
  ``PropostaHistorico('whatsapp_aberto')``.
* O template `detalhes_proposta.html` renderiza o botão verde
  (habilitado vs. desabilitado conforme telefone do cliente).

Roda em transação revertida (cleanup explícito no fim de cada teste).
"""
import os
import sys
from datetime import datetime, date
from decimal import Decimal
from unittest.mock import patch

import pytest
from flask import get_flashed_messages

sys.path.insert(0, os.path.abspath(os.path.dirname(__file__) + '/..'))

from app import app, db  # noqa: E402
from models import Usuario, Proposta, PropostaHistorico  # noqa: E402
import propostas_consolidated as pc  # noqa: E402
from utils import webhook_dispatcher as wd  # noqa: E402


# ──────────────────────────────────────────────────────────────────────
# Fixtures
# ──────────────────────────────────────────────────────────────────────
@pytest.fixture
def app_ctx():
    with app.app_context():
        yield


@pytest.fixture
def admin_user(app_ctx):
    from models import TipoUsuario
    # Preferimos um ADMIN real (sem ``admin_id`` indireto). Se não houver,
    # caímos no primeiro usuário disponível e marcamos os testes que
    # dependem de admin_required como skip.
    u = (Usuario.query
         .filter(Usuario.tipo_usuario == TipoUsuario.ADMIN)
         .first()) or Usuario.query.first()
    if u is None:
        pytest.skip('Sem usuário no banco — teste pula.')
    return u


@pytest.fixture
def proposta_factory(admin_user):
    """Cria propostas isoladas e limpa no fim do teste."""
    criadas: list[int] = []

    def _make(**overrides):
        defaults = dict(
            admin_id=admin_user.id,
            numero=f'__T44-{datetime.utcnow().strftime("%H%M%S%f")}',
            cliente_nome='Cliente Teste 44',
            cliente_email='cliente44@example.com',
            cliente_telefone='(31) 99999-1234',
            valor_total=Decimal('1500.00'),
            versao=1,
            validade_dias=10,
            data_envio=datetime(2026, 4, 30, 12, 0, 0),
            token_cliente='tok-44-' + datetime.utcnow().strftime('%H%M%S%f'),
            status='rascunho',
        )
        defaults.update(overrides)
        p = Proposta(**defaults)
        db.session.add(p)
        db.session.flush()
        criadas.append(p.id)
        return p

    yield _make

    if criadas:
        PropostaHistorico.query.filter(
            PropostaHistorico.proposta_id.in_(criadas)
        ).delete(synchronize_session=False)
        Proposta.query.filter(Proposta.id.in_(criadas)).delete(
            synchronize_session=False
        )
        db.session.commit()


# ──────────────────────────────────────────────────────────────────────
# 1) _telefone_so_digitos
# ──────────────────────────────────────────────────────────────────────
class TestTelefoneSoDigitos:
    def test_celular_br_sem_ddi_recebe_55(self):
        assert pc._telefone_so_digitos('(31) 99999-1234') == '5531999991234'

    def test_fixo_br_sem_ddi_recebe_55(self):
        assert pc._telefone_so_digitos('31 3333-4444') == '553133334444'

    def test_com_ddi_55_mantem(self):
        assert pc._telefone_so_digitos('+55 31 99999-1234') == '5531999991234'

    def test_apenas_digitos(self):
        assert pc._telefone_so_digitos('5531999991234') == '5531999991234'

    def test_vazio_e_none(self):
        assert pc._telefone_so_digitos('') == ''
        assert pc._telefone_so_digitos(None) == ''

    def test_so_separadores(self):
        assert pc._telefone_so_digitos('()- /') == ''


# ──────────────────────────────────────────────────────────────────────
# 2) _whatsapp_url_proposta
# ──────────────────────────────────────────────────────────────────────
class TestWhatsappUrlProposta:
    def test_url_montada_com_msg_e_link(self, proposta_factory):
        p = proposta_factory(cliente_nome='Maria Silva',
                             cliente_telefone='(31) 99999-1234',
                             valor_total=Decimal('1500.00'),
                             numero='PROP-001', versao=2)
        url = pc._whatsapp_url_proposta(p, 'https://app.example/portal/abc')
        assert url is not None
        assert url.startswith('https://wa.me/5531999991234?text=')
        # Texto contém nome, número, versão, valor e link
        from urllib.parse import unquote
        texto = unquote(url.split('?text=', 1)[1])
        assert 'Maria' in texto
        assert 'PROP-001' in texto
        assert 'versão 2' in texto
        assert 'R$ 1.500,00' in texto
        assert 'https://app.example/portal/abc' in texto

    def test_sem_telefone_retorna_none(self, proposta_factory):
        p = proposta_factory(cliente_telefone='')
        assert pc._whatsapp_url_proposta(p, 'https://x') is None

    def test_telefone_lixo_retorna_none(self, proposta_factory):
        p = proposta_factory(cliente_telefone='??')
        assert pc._whatsapp_url_proposta(p, 'https://x') is None


# ──────────────────────────────────────────────────────────────────────
# 3) Allowlist do dispatcher
# ──────────────────────────────────────────────────────────────────────
class TestAllowlist:
    def test_proposta_enviada_no_allowlist(self):
        assert 'proposta.enviada' in wd.WEBHOOK_EVENT_ALLOWLIST


# ──────────────────────────────────────────────────────────────────────
# 4) _notificar_envio_proposta
# ──────────────────────────────────────────────────────────────────────
class TestNotificarEnvioProposta:
    def test_emite_evento_com_payload_correto(self, proposta_factory, admin_user):
        p = proposta_factory(
            cliente_nome='João',
            cliente_email='joao@x.com',
            cliente_telefone='(31) 99999-0000',
            valor_total=Decimal('2500.50'),
            versao=3, validade_dias=15,
            data_envio=datetime(2026, 4, 30, 0, 0, 0),
        )
        with app.test_request_context('/propostas/x/enviar', method='POST',
                                      data={'observacoes_envio': 'urgente'}):
            # Mock current_user (flask_login): patch onde é usado.
            with patch.object(pc, 'current_user', new=admin_user):
                with patch('event_manager.EventManager.emit') as mock_emit:
                    pc._notificar_envio_proposta(p, admin_user.id)
                    assert mock_emit.called
                    args, kwargs = mock_emit.call_args
                    event_name, payload, admin_id = args[0], args[1], args[2]
                    assert event_name == 'proposta.enviada'
                    assert admin_id == admin_user.id
                    # Schema contratual com o n8n
                    assert payload['proposta_id'] == p.id
                    assert payload['numero'] == p.numero
                    assert payload['versao'] == 3
                    assert payload['cliente_nome'] == 'João'
                    assert payload['cliente_email'] == 'joao@x.com'
                    assert payload['cliente_telefone'] == '(31) 99999-0000'
                    assert payload['valor_total'] == 2500.50
                    assert payload['data_validade'] == '2026-05-15'
                    assert 'portal_url' in payload
                    assert payload['portal_url'].startswith('http')
                    assert p.token_cliente in payload['portal_url']
                    assert payload['observacoes_envio'] == 'urgente'

    def test_grava_historico_notificacao_disparada(self, proposta_factory, admin_user):
        p = proposta_factory(cliente_email='c@x.com',
                             cliente_telefone='(31) 99999-1234')
        with app.test_request_context('/p/x/enviar', method='POST'):
            with patch.object(pc, 'current_user', new=admin_user):
                with patch('event_manager.EventManager.emit', return_value=True):
                    pc._notificar_envio_proposta(p, admin_user.id)

        h = (PropostaHistorico.query
             .filter_by(proposta_id=p.id, acao='notificacao_disparada')
             .order_by(PropostaHistorico.id.desc())
             .first())
        assert h is not None
        assert 'e-mail' in (h.observacao or '')
        assert 'whatsapp' in (h.observacao or '')

    def test_sem_email_dispara_flash_warning(self, proposta_factory, admin_user):
        p = proposta_factory(cliente_email='', cliente_telefone='(31) 99999-1234')
        with app.test_request_context('/p/x/enviar', method='POST'):
            with patch.object(pc, 'current_user', new=admin_user):
                with patch('event_manager.EventManager.emit', return_value=True):
                    pc._notificar_envio_proposta(p, admin_user.id)
                    msgs = get_flashed_messages(with_categories=True)
                    assert any(cat == 'warning' and 'e-mail' in m
                               for cat, m in msgs)

    def test_sem_email_e_telefone_flash_e_canais_nenhum(
        self, proposta_factory, admin_user
    ):
        p = proposta_factory(cliente_email='', cliente_telefone='')
        with app.test_request_context('/p/x/enviar', method='POST'):
            with patch.object(pc, 'current_user', new=admin_user):
                with patch('event_manager.EventManager.emit', return_value=True):
                    pc._notificar_envio_proposta(p, admin_user.id)
                    msgs = get_flashed_messages(with_categories=True)
                    assert any(cat == 'warning' for cat, _ in msgs)

        h = (PropostaHistorico.query
             .filter_by(proposta_id=p.id, acao='notificacao_disparada')
             .first())
        assert h is not None
        assert 'nenhum' in (h.observacao or '').lower()


# ──────────────────────────────────────────────────────────────────────
# 5) Rota /whatsapp/registrar
# ──────────────────────────────────────────────────────────────────────
class TestRotaWhatsappRegistrar:
    def test_post_grava_historico_whatsapp_aberto(
        self, proposta_factory, admin_user
    ):
        p = proposta_factory(cliente_telefone='(31) 99999-1234')
        client = app.test_client()
        # Bypass do login: empurra o user na sessão do flask-login.
        with client.session_transaction() as sess:
            sess['_user_id'] = str(admin_user.id)
            sess['_fresh'] = True
        resp = client.post(f'/propostas/{p.id}/whatsapp/registrar')
        # Pode falhar por @admin_required dependendo do tipo do user;
        # cobrimos os dois cenários.
        if resp.status_code in (302, 401, 403):
            pytest.skip(f'Usuário disponível não é admin (status {resp.status_code}).')
        assert resp.status_code == 200, resp.data
        assert resp.is_json
        assert resp.get_json().get('ok') is True

        h = (PropostaHistorico.query
             .filter_by(proposta_id=p.id, acao='whatsapp_aberto')
             .first())
        assert h is not None


# ──────────────────────────────────────────────────────────────────────
# 6) Render do template
# ──────────────────────────────────────────────────────────────────────
class TestTemplateRender:
    def _render(self, proposta, wa_url):
        from flask import render_template
        with app.test_request_context('/'):
            return render_template(
                'propostas/detalhes_proposta.html',
                proposta=proposta,
                itens=[],
                arquivos=[],
                total_geral=0,
                whatsapp_url_proposta=wa_url,
                date=date,
            )

    def test_botao_whatsapp_habilitado_quando_tem_telefone(
        self, proposta_factory
    ):
        p = proposta_factory(cliente_telefone='(31) 99999-1234')
        wa = pc._whatsapp_url_proposta(p, 'https://app.example/portal/x')
        html = self._render(p, wa)
        assert 'btnAbrirWhatsapp' in html
        assert 'wa.me/5531999991234' in html
        assert 'Abrir no WhatsApp' in html
        # Botão habilitado: a tag <a> com href existe (não <button disabled>)
        assert 'href="https://wa.me/' in html

    def test_botao_whatsapp_desabilitado_sem_telefone(self, proposta_factory):
        p = proposta_factory(cliente_telefone='')
        html = self._render(p, None)
        assert 'Abrir no WhatsApp' in html
        # Sem telefone, vira <button disabled>
        assert 'disabled' in html
        assert 'Cadastre o telefone do cliente' in html


if __name__ == '__main__':
    sys.exit(pytest.main([__file__, '-v']))
