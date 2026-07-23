"""Fase 3 — matriz ator × ação, num arquivo só.

Os arquivos test_fase3_requisicao.py e test_fase3_alcada.py testam as
peças. Este testa a TABELA: sete atores contra as quatro ações que a fase
introduz, para que uma permissão nova nunca entre sem aparecer aqui.

A fixture liga `escopo_obra_ativo`: sem ela, papel_na_obra devolve GESTOR
a todo autenticado do tenant (comportamento pré-Fase 1), e o eixo de obra
— que é o que distingue comprador de apontador de leitor de sem-vínculo —
não vale. É o escopo ligado que faz a matriz ter sentido.
"""
import os
import sys
import uuid
from datetime import date
from decimal import Decimal

import pytest
from werkzeug.security import generate_password_hash

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import main  # noqa: F401
from app import app, db
from models import (Cliente, EstadoRequisicao, Fornecedor, Obra, PapelObra,
                    RequisicaoCompra, RequisicaoCompraItem, TipoUsuario,
                    Usuario, UsuarioObra)

pytestmark = pytest.mark.integration


@pytest.fixture(autouse=True)
def _config():
    app.config['TESTING'] = True
    app.config['WTF_CSRF_ENABLED'] = False
    if not app.secret_key:
        app.secret_key = 'test-fase3-matriz'
    yield


def _usuario(tipo, admin_id=None, nome='U'):
    suf = uuid.uuid4().hex[:8]
    u = Usuario(
        username=f'f3m_{suf}', email=f'f3m_{suf}@test.local',
        nome=f'{nome} {suf}',
        password_hash=generate_password_hash('Senha@2026'),
        tipo_usuario=tipo, ativo=True, versao_sistema='v2',
        admin_id=admin_id)
    db.session.add(u)
    db.session.commit()
    return u


def _cliente_de(user_id):
    c = app.test_client()
    with c.session_transaction() as sess:
        sess['_user_id'] = str(user_id)
        sess['_fresh'] = True
    return c


@pytest.fixture
def cenario():
    """Um tenant, uma obra, sete atores, uma requisição aguardando alçada
    de faixa única (1 aprovação, sem exigência de admin)."""
    from models import FaixaAlcada
    from scripts.flag_escopo_obra import definir_flag
    from services.requisicao_compra import proximo_numero, recalcular_valor

    with app.app_context():
        admin = _usuario(TipoUsuario.ADMIN, nome='Admin')
        outro_admin = _usuario(TipoUsuario.ADMIN, nome='Outro')

        suf = uuid.uuid4().hex[:8]
        cli = Cliente(nome=f'C {suf}', admin_id=admin.id)
        db.session.add(cli)
        db.session.commit()
        obra = Obra(nome=f'Obra {suf}', codigo=f'O{suf[:6].upper()}',
                    data_inicio=date(2026, 1, 1), admin_id=admin.id,
                    cliente_id=cli.id, ativo=True)
        db.session.add(obra)
        db.session.commit()

        FaixaAlcada.query.filter_by(admin_id=admin.id).delete()
        db.session.add(FaixaAlcada(
            admin_id=admin.id, ordem=1, valor_ate=None,
            aprovacoes_necessarias=1, exige_admin=False,
            exige_mapa_concorrencia=False, ativo=True))

        atores = {'admin': admin, 'outro_tenant': outro_admin}
        for chave, papel in (('gestor', PapelObra.GESTOR),
                             ('comprador', PapelObra.COMPRADOR),
                             ('apontador', PapelObra.APONTADOR),
                             ('leitor', PapelObra.LEITOR)):
            u = _usuario(TipoUsuario.FUNCIONARIO, admin_id=admin.id, nome=chave)
            db.session.add(UsuarioObra(usuario_id=u.id, obra_id=obra.id,
                                       papel=papel, admin_id=admin.id,
                                       ativo=True))
            atores[chave] = u
        atores['sem_vinculo'] = _usuario(TipoUsuario.FUNCIONARIO,
                                        admin_id=admin.id, nome='sem')

        solicitante = _usuario(TipoUsuario.FUNCIONARIO, admin_id=admin.id,
                               nome='Solicitante')
        db.session.add(UsuarioObra(usuario_id=solicitante.id, obra_id=obra.id,
                                   papel=PapelObra.COMPRADOR,
                                   admin_id=admin.id, ativo=True))
        atores['solicitante'] = solicitante

        forn = Fornecedor(nome='F', cnpj=uuid.uuid4().hex[:14],
                          admin_id=admin.id, ativo=True)
        db.session.add(forn)
        db.session.commit()

        # O eixo de obra só distingue os papéis com a flag ligada.
        definir_flag(admin.id, True)

        req = RequisicaoCompra(
            numero=proximo_numero(admin.id), obra_id=obra.id,
            solicitante_id=solicitante.id, admin_id=admin.id,
            estado=EstadoRequisicao.AGUARDANDO_APROVACAO)
        db.session.add(req)
        db.session.flush()
        db.session.add(RequisicaoCompraItem(
            requisicao_id=req.id, admin_id=admin.id, descricao='Perfil',
            unidade='m', quantidade=Decimal('1.000'),
            preco_estimado=Decimal('100.00')))
        db.session.flush()
        recalcular_valor(req)
        db.session.commit()

        return {
            'ids': {k: v.id for k, v in atores.items()},
            'obra': obra.id, 'req': req.id, 'admin': admin.id,
            'fornecedor': forn.id,
        }


# Matriz: ator → (pode criar requisição, pode aprovar, pode emitir pedido)
MATRIZ = {
    'admin':        (True,  True,  True),
    'gestor':       (True,  True,  False),
    'comprador':    (True,  False, True),
    'apontador':    (False, False, False),
    'leitor':       (False, False, False),
    'sem_vinculo':  (False, False, False),
    'outro_tenant': (False, False, False),
}


@pytest.mark.parametrize('ator', sorted(MATRIZ))
def test_criar_requisicao(ator, cenario):
    esperado = MATRIZ[ator][0]
    antes = None
    with app.app_context():
        antes = RequisicaoCompra.query.filter_by(
            admin_id=cenario['admin']).count()

    _cliente_de(cenario['ids'][ator]).post('/compras/requisicoes/nova', data={
        'obra_id': str(cenario['obra']),
        'justificativa': f'matriz {ator}',
        'item_descricao[]': ['X'], 'item_unidade[]': ['un'],
        'item_quantidade[]': ['1'], 'item_preco[]': ['10'],
        'item_almoxarifado_id[]': [''],
    }, follow_redirects=False)

    with app.app_context():
        depois = RequisicaoCompra.query.filter_by(
            admin_id=cenario['admin']).count()
    criou = depois > antes
    assert criou is esperado, (
        f'{ator}: esperava criar={esperado}, obteve {criou}')


@pytest.mark.parametrize('ator', sorted(MATRIZ))
def test_aprovar_requisicao(ator, cenario):
    esperado = MATRIZ[ator][1]
    _cliente_de(cenario['ids'][ator]).post(
        f"/compras/requisicoes/{cenario['req']}/aprovar",
        follow_redirects=False)
    with app.app_context():
        estado = db.session.get(RequisicaoCompra, cenario['req']).estado
    aprovou = estado == EstadoRequisicao.APROVADA
    assert aprovou is esperado, (
        f'{ator}: esperava aprovar={esperado}, estado ficou {estado}')


@pytest.mark.parametrize('ator', sorted(MATRIZ))
def test_emitir_pedido(ator, cenario):
    """A requisição é levada a APROVADA pelo GESTOR antes de cada tentativa.

    Faixa de 1 aprovação: a guarda de 'quem aprovou não emite' NÃO se
    aplica (ver compras_views.requisicao_emitir_pedido, guarda 2), então
    o gestor falha aqui por não ter papel de COMPRADOR, e não por ter
    aprovado.
    """
    from models import PedidoCompra
    from services.alcada_compras import registrar_aprovacao
    from services.requisicao_compra import transicionar

    esperado = MATRIZ[ator][2]
    with app.app_context():
        req = db.session.get(RequisicaoCompra, cenario['req'])
        gestor = db.session.get(Usuario, cenario['ids']['gestor'])
        registrar_aprovacao(req, gestor, papel='GESTOR')
        transicionar(req, EstadoRequisicao.APROVADA, gestor, motivo='matriz')
        db.session.commit()

    _cliente_de(cenario['ids'][ator]).post(
        f"/compras/requisicoes/{cenario['req']}/emitir-pedido",
        data={'fornecedor_id': str(cenario['fornecedor']),
              'data_compra': '2026-08-01', 'condicao_pagamento': 'a_vista'},
        follow_redirects=False)

    with app.app_context():
        emitiu = PedidoCompra.query.filter_by(
            requisicao_id=cenario['req']).count() > 0
    assert emitiu is esperado, (
        f'{ator}: esperava emitir={esperado}, obteve {emitiu}')


def test_anonimo_nao_alcanca_nenhuma_rota_de_requisicao(cenario):
    anon = app.test_client()
    rotas = [
        ('GET', '/compras/requisicoes'),
        ('GET', '/compras/requisicoes/nova'),
        ('POST', '/compras/requisicoes/nova'),
        ('GET', f"/compras/requisicoes/{cenario['req']}"),
        ('POST', f"/compras/requisicoes/{cenario['req']}/enviar"),
        ('POST', f"/compras/requisicoes/{cenario['req']}/aprovar"),
        ('POST', f"/compras/requisicoes/{cenario['req']}/rejeitar"),
        ('POST', f"/compras/requisicoes/{cenario['req']}/emitir-pedido"),
        ('POST', f"/compras/requisicoes/{cenario['req']}/cancelar"),
    ]
    for metodo, rota in rotas:
        r = anon.open(rota, method=metodo, follow_redirects=False)
        assert r.status_code in (302, 401), (
            f'{metodo} {rota} devolveu {r.status_code} para anônimo')
