"""Triagem de 23/07 (docs/anexos/B-triagem-rotas-expoe-dado.md) — as 3 rotas
de veredito FECHAR ganharam @login_required:

- /funcionario_perfil/<id>/pdf servia o dossiê de ponto de QUALQUER
  funcionário de QUALQUER tenant a anônimo (get_or_404 sem tenant e, sem
  login, admin_id=None removia o filtro de RegistroPonto);
- /api/funcionarios tinha bypass explícito que entregava a lista de
  funcionários do MAIOR tenant do banco a qualquer anônimo;
- /rdo/<id> só não vazava porque anônimo quebrava em AttributeError
  engolido pelo except — agora é 302 intencional.
"""
import os
import sys
import uuid

import pytest
from werkzeug.security import generate_password_hash

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import main  # noqa: F401 — registra os blueprints
from app import app, db
from models import TipoUsuario, Usuario

pytestmark = pytest.mark.integration

SENHA = 'Senha@2026'


@pytest.fixture(autouse=True)
def _config():
    app.config['TESTING'] = True
    app.config['WTF_CSRF_ENABLED'] = False
    if not app.secret_key:
        app.secret_key = 'test-triagem-rotas'
    yield


@pytest.mark.parametrize('rota', [
    '/funcionario_perfil/1/pdf',
    '/api/funcionarios',
    '/rdo/1',
])
def test_anonimo_nao_recebe_dado(rota):
    """Anônimo é redirecionado ao login (ou recebe 401) — nunca 200 com dado."""
    c = app.test_client()
    r = c.get(rota, follow_redirects=False)
    assert r.status_code in (301, 302, 401), (
        f'{rota}: esperava redirect/401 para anônimo, veio {r.status_code}')
    if r.status_code in (301, 302):
        assert '/login' in (r.headers.get('Location') or ''), (
            f'{rota}: redirect anônimo deveria ir para /login')


@pytest.mark.parametrize('rota', [
    # As 4 APIs de RDO com vazamento cross-tenant latente (mortas por
    # referência, vivas por URL até 23/07):
    '/rdo/api/ultimo-rdo/1',
    '/api/test/rdo/servicos-obra/1',
    '/api/ultimo-rdo-dados/1',
    '/api/servicos-obra-primeira-rdo/1',
    # Páginas de debug/teste sem referência viva:
    '/ponto-diagnostico',
    '/ponto/debug',
    '/test',
])
def test_rota_morta_removida(rota):
    """Rotas de veredito MORTA do Anexo B foram removidas — 404 para todos."""
    c = app.test_client()
    r = c.get(rota, follow_redirects=False)
    assert r.status_code == 404, (
        f'{rota}: esperava 404 (rota removida), veio {r.status_code}')


def test_persistent_uploads_removida():
    """/persistent-uploads/<path> servia o volume de uploads inteiro a
    anônimo — removida; comprovantes saem por rota escopada."""
    c = app.test_client()
    r = c.get('/persistent-uploads/comprovantes/qualquer.pdf')
    assert r.status_code == 404


@pytest.fixture
def cenario_comprovante(tmp_path, monkeypatch):
    """Obra com portal ativo + pedido com comprovante físico em tmp."""
    import portal_obras_views as pov
    from datetime import date
    from decimal import Decimal
    from models import Cliente, Fornecedor, Obra, PedidoCompra

    pasta = tmp_path / 'comprovantes'
    pasta.mkdir()
    conteudo = b'%PDF-comprovante-de-teste'
    (pasta / 'comp_teste.pdf').write_bytes(conteudo)
    monkeypatch.setattr(pov, 'UPLOAD_FOLDER', str(pasta))

    suf = uuid.uuid4().hex[:8]
    with app.app_context():
        admin = Usuario(
            username=f'cpv_{suf}', email=f'cpv_{suf}@test.local',
            nome=f'Admin Comprovante {suf}',
            password_hash=generate_password_hash(SENHA),
            tipo_usuario=TipoUsuario.ADMIN, ativo=True, versao_sistema='v2',
        )
        db.session.add(admin)
        db.session.commit()
        cliente = Cliente(nome=f'Cliente {suf}', admin_id=admin.id)
        db.session.add(cliente)
        db.session.commit()
        obra = Obra(nome=f'Obra Comp {suf}', codigo=f'C{suf[:6].upper()}',
                    data_inicio=date(2026, 1, 1), admin_id=admin.id,
                    cliente_id=cliente.id, ativo=True, portal_ativo=True)
        obra.token_cliente = f'tok-teste-{uuid.uuid4().hex}'
        db.session.add(obra)
        db.session.commit()
        fornecedor = Fornecedor(nome=f'Fornecedor {suf}',
                                cnpj=f'{suf[:8]}0001-{suf[:2]}',
                                admin_id=admin.id)
        db.session.add(fornecedor)
        db.session.commit()
        pedido = PedidoCompra(
            fornecedor_id=fornecedor.id, obra_id=obra.id,
            data_compra=date(2026, 7, 1), valor_total=Decimal('100.00'),
            admin_id=admin.id,
            comprovante_pagamento_url='/persistent-uploads/comprovantes/comp_teste.pdf',
        )
        db.session.add(pedido)
        db.session.commit()
        return {'token': obra.token_cliente, 'pedido_id': pedido.id,
                'conteudo': conteudo}


def test_portal_serve_comprovante_com_token_valido(cenario_comprovante):
    c = app.test_client()
    r = c.get(f"/portal/obra/{cenario_comprovante['token']}/compra/"
              f"{cenario_comprovante['pedido_id']}/comprovante")
    assert r.status_code == 200, f'esperava 200, veio {r.status_code}'
    assert r.data == cenario_comprovante['conteudo']


def test_portal_nao_serve_comprovante_com_token_errado(cenario_comprovante):
    c = app.test_client()
    r = c.get(f"/portal/obra/token-invalido-{uuid.uuid4().hex}/compra/"
              f"{cenario_comprovante['pedido_id']}/comprovante")
    assert r.status_code == 404


def test_comprovante_interno_exige_login(cenario_comprovante):
    c = app.test_client()
    r = c.get(f"/compras/{cenario_comprovante['pedido_id']}/comprovante",
              follow_redirects=False)
    assert r.status_code in (301, 302, 401)
    if r.status_code in (301, 302):
        assert '/login' in (r.headers.get('Location') or '')


def test_api_funcionarios_segue_servindo_autenticado():
    """O fechamento não pode quebrar o consumidor legítimo (obras.html, logado)."""
    suf = uuid.uuid4().hex[:8]
    with app.app_context():
        admin = Usuario(
            username=f'tri_{suf}', email=f'tri_{suf}@test.local',
            nome=f'Admin Triagem {suf}',
            password_hash=generate_password_hash(SENHA),
            tipo_usuario=TipoUsuario.ADMIN, ativo=True, versao_sistema='v2',
        )
        db.session.add(admin)
        db.session.commit()
        email = admin.email
    c = app.test_client()
    r = c.post('/login', data={'email': email, 'password': SENHA},
               follow_redirects=False)
    assert r.status_code in (302, 303), f'login falhou (status={r.status_code})'
    r = c.get('/api/funcionarios')
    assert r.status_code == 200
    payload = r.get_json()
    assert payload is not None and payload.get('success') is True, payload
