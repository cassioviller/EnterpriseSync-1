"""Fase 3 — os cinco POSTs anônimos do portal do cliente.

O portal é um sistema de identidade paralelo: `Obra.token_cliente`
(models.py:261) é `String(255) unique`, SEM coluna de expiração, SEM
escopo de ação e SEM revogação individual. Cinco rotas POST mutam estado
só com a URL:

  portal_obras_views.py:343  /compra/<id>/aprovar     → cria custo!
  portal_obras_views.py:377  /compra/<id>/recusar
  portal_obras_views.py:388  /compra/<id>/comprovante → upload
  portal_obras_views.py:432  /mapa/<id>/aprovar
  portal_obras_views.py:546  /mapa-v2/<id>/selecionar

Estes testes travam as correções incondicionais da Task 10.
"""
import os
import sys
import uuid
from datetime import date, datetime, timedelta
from decimal import Decimal

import pytest
from werkzeug.security import generate_password_hash

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import main  # noqa: F401 — registra os blueprints
from app import app, db
from models import (Cliente, Fornecedor, Obra, PedidoCompra, TipoUsuario,
                    Usuario)

pytestmark = pytest.mark.integration


@pytest.fixture(autouse=True)
def _config():
    app.config['TESTING'] = True
    app.config['WTF_CSRF_ENABLED'] = False
    if not app.secret_key:
        app.secret_key = 'test-fase3-portal'
    yield


def _admin():
    suf = uuid.uuid4().hex[:8]
    u = Usuario(
        username=f'f3s_{suf}', email=f'f3s_{suf}@test.local', nome=f'Adm {suf}',
        password_hash=generate_password_hash('Senha@2026'),
        tipo_usuario=TipoUsuario.ADMIN, ativo=True, versao_sistema='v2')
    db.session.add(u)
    db.session.commit()
    return u


def _obra_com_token(admin_id, expira_em='padrao'):
    import secrets
    suf = uuid.uuid4().hex[:8]
    cliente = Cliente(nome=f'Cliente {suf}', admin_id=admin_id)
    db.session.add(cliente)
    db.session.commit()
    o = Obra(nome=f'Obra {suf}', codigo=f'O{suf[:6].upper()}',
             data_inicio=date(2026, 1, 1), admin_id=admin_id,
             cliente_id=cliente.id, ativo=True, portal_ativo=True,
             token_cliente=secrets.token_urlsafe(32))
    if expira_em != 'padrao':
        o.token_cliente_expira_em = expira_em
    db.session.add(o)
    db.session.commit()
    return o


def _compra(admin_id, obra_id, tipo='aprovacao_cliente'):
    suf = uuid.uuid4().hex[:14]
    forn = Fornecedor(nome='Forn', cnpj=suf, admin_id=admin_id, ativo=True)
    db.session.add(forn)
    db.session.commit()
    p = PedidoCompra(
        fornecedor_id=forn.id, data_compra=date(2026, 8, 1), obra_id=obra_id,
        condicao_pagamento='a_vista', parcelas=1,
        valor_total=Decimal('1000.00'), tipo_compra=tipo,
        processada_apos_aprovacao=False, admin_id=admin_id,
        status_aprovacao_cliente=('AGUARDANDO_APROVACAO_CLIENTE'
                                  if tipo == 'aprovacao_cliente' else None))
    db.session.add(p)
    db.session.commit()
    return p


# ---------------------------------------------------------------------------
# 1 — a rota de aprovar não pode tocar em compra que não é do cliente
# ---------------------------------------------------------------------------

def test_portal_nao_aprova_compra_do_tipo_normal():
    """portal_obras_views.py:354 gravava APROVADO em QUALQUER PedidoCompra
    da obra — o único filtro era obra_id (:346). Compra 'normal' nunca
    passou pelo cliente e não pode ser marcada como aprovada por ele."""
    with app.app_context():
        admin = _admin()
        obra = _obra_com_token(admin.id)
        compra = _compra(admin.id, obra.id, tipo='normal')
        token, cid = obra.token_cliente, compra.id

    anon = app.test_client()
    r = anon.post(f'/portal/obra/{token}/compra/{cid}/aprovar',
                  follow_redirects=False)
    assert r.status_code in (302, 403, 404)
    with app.app_context():
        assert db.session.get(PedidoCompra, cid).status_aprovacao_cliente is None


# ---------------------------------------------------------------------------
# 2 — expiração do token
# ---------------------------------------------------------------------------

def test_token_expirado_nao_abre_o_portal():
    with app.app_context():
        admin = _admin()
        obra = _obra_com_token(
            admin.id, expira_em=datetime.utcnow() - timedelta(days=1))
        token = obra.token_cliente

    anon = app.test_client()
    assert anon.get(f'/portal/obra/{token}').status_code == 404


def test_token_expirado_nao_muta_estado():
    with app.app_context():
        admin = _admin()
        obra = _obra_com_token(
            admin.id, expira_em=datetime.utcnow() - timedelta(days=1))
        compra = _compra(admin.id, obra.id)
        token, cid = obra.token_cliente, compra.id

    anon = app.test_client()
    r = anon.post(f'/portal/obra/{token}/compra/{cid}/aprovar',
                  follow_redirects=False)
    assert r.status_code == 404
    with app.app_context():
        assert db.session.get(PedidoCompra, cid).status_aprovacao_cliente == \
            'AGUARDANDO_APROVACAO_CLIENTE'


def test_token_sem_data_de_expiracao_continua_valendo():
    """Deploy não pode derrubar portal de obra em andamento: token antigo
    sem data segue valendo até ser rotacionado."""
    with app.app_context():
        admin = _admin()
        obra = _obra_com_token(admin.id, expira_em=None)
        token = obra.token_cliente

    anon = app.test_client()
    assert anon.get(f'/portal/obra/{token}').status_code == 200


def test_toggle_do_portal_carimba_a_expiracao():
    from portal_obras_views import PRAZO_TOKEN_DIAS

    with app.app_context():
        admin = _admin()
        obra = _obra_com_token(admin.id, expira_em=None)
        obra.portal_ativo = False
        obra.token_cliente = None
        db.session.commit()
        aid, oid = admin.id, obra.id

    c = app.test_client()
    with c.session_transaction() as sess:
        sess['_user_id'] = str(aid)
        sess['_fresh'] = True
    c.post(f'/portal/obra/{oid}/portal-toggle', follow_redirects=False)

    with app.app_context():
        obra = db.session.get(Obra, oid)
        assert obra.token_cliente
        assert obra.token_cliente_expira_em is not None
        delta = obra.token_cliente_expira_em - datetime.utcnow()
        assert timedelta(days=PRAZO_TOKEN_DIAS - 1) < delta <= \
            timedelta(days=PRAZO_TOKEN_DIAS)


# ---------------------------------------------------------------------------
# 3 — trilha de acesso
# ---------------------------------------------------------------------------

def test_post_no_portal_grava_trilha_com_ip():
    from models import PortalAcessoEvento

    with app.app_context():
        admin = _admin()
        obra = _obra_com_token(admin.id)
        compra = _compra(admin.id, obra.id)
        token, oid, cid = obra.token_cliente, obra.id, compra.id

    anon = app.test_client()
    anon.post(f'/portal/obra/{token}/compra/{cid}/aprovar',
              environ_base={'REMOTE_ADDR': '203.0.113.7'},
              headers={'User-Agent': 'pytest-portal'})

    with app.app_context():
        eventos = PortalAcessoEvento.query.filter_by(obra_id=oid).all()
        assert eventos, 'POST anônimo no portal não deixou trilha'
        assert any(e.ip == '203.0.113.7' for e in eventos)
        assert any('pytest-portal' in (e.user_agent or '') for e in eventos)
        assert any(e.acao == 'compra_aprovar' for e in eventos)


# ---------------------------------------------------------------------------
# Governança ligada: o cliente dá ciência, não cria custo
# ---------------------------------------------------------------------------

def test_sem_governanca_o_portal_continua_criando_custo():
    """Comportamento de hoje, preservado enquanto a flag estiver desligada."""
    from models import GestaoCustoPai

    with app.app_context():
        admin = _admin()
        obra = _obra_com_token(admin.id)
        compra = _compra(admin.id, obra.id)
        token, cid, aid = obra.token_cliente, compra.id, admin.id

    anon = app.test_client()
    anon.post(f'/portal/obra/{token}/compra/{cid}/aprovar',
              follow_redirects=False)

    with app.app_context():
        compra = db.session.get(PedidoCompra, cid)
        assert compra.status_aprovacao_cliente == 'APROVADO'
        assert compra.processada_apos_aprovacao is True
        assert GestaoCustoPai.query.filter_by(
            admin_id=aid, tipo_categoria='FATURAMENTO_DIRETO').count() == 1


def test_com_governanca_o_portal_registra_ciencia_sem_criar_custo():
    from models import GestaoCustoPai
    from scripts.flag_compras_governanca import definir_flag

    with app.app_context():
        admin = _admin()
        obra = _obra_com_token(admin.id)
        compra = _compra(admin.id, obra.id)
        definir_flag(admin.id, True)
        token, cid, aid = obra.token_cliente, compra.id, admin.id

    anon = app.test_client()
    anon.post(f'/portal/obra/{token}/compra/{cid}/aprovar',
              follow_redirects=False)

    with app.app_context():
        compra = db.session.get(PedidoCompra, cid)
        # a ciência do cliente FICA registrada…
        assert compra.status_aprovacao_cliente == 'APROVADO'
        # …mas o custo NÃO nasceu de um POST anônimo
        assert compra.processada_apos_aprovacao is False
        assert GestaoCustoPai.query.filter_by(
            admin_id=aid, tipo_categoria='FATURAMENTO_DIRETO').count() == 0


def test_com_governanca_a_trilha_marca_ciencia():
    from models import PortalAcessoEvento
    from scripts.flag_compras_governanca import definir_flag

    with app.app_context():
        admin = _admin()
        obra = _obra_com_token(admin.id)
        compra = _compra(admin.id, obra.id)
        definir_flag(admin.id, True)
        token, cid, oid = obra.token_cliente, compra.id, obra.id

    anon = app.test_client()
    anon.post(f'/portal/obra/{token}/compra/{cid}/aprovar',
              follow_redirects=False)

    with app.app_context():
        eventos = PortalAcessoEvento.query.filter_by(
            obra_id=oid, acao='compra_aprovar').all()
        assert eventos
        assert any((e.detalhes or {}).get('modo') == 'ciencia' for e in eventos)
