"""A nota e a liberação — o fecho da Fase 2 do ciclo de compras.

Spec: docs/superpowers/specs/2026-08-17-nota-e-liberacao-design.md
Plano: docs/superpowers/plans/2026-08-17-plano-execucao-nota-e-liberacao.md

A Fase 2 entregou `lancar_nota()` e `liberar()` sem rota, sem template e sem
botão: toda `ContaPagar` do Fluxo A nascia `bloqueada` e não havia caminho no
app para destravá-la. Esta suíte cobre o caminho que faltava — e, no gate de
merge, o ciclo inteiro pela tela: emitir → atestar → lançar nota → liberar →
pagar.

Molde de tests/test_financeiro_dois_fluxos.py: fixtures locais, tenant por
uuid4, sem depender de seed.
"""
import os
import sys
import uuid
from datetime import date
from decimal import Decimal

import pytest
from werkzeug.security import generate_password_hash

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import main  # noqa: F401 — registra os blueprints
from app import app, db
from models import (Cliente, ContaPagar, Fornecedor, Obra, PedidoCompra,
                    PedidoCompraItem, TipoUsuario, Usuario)

pytestmark = pytest.mark.integration


@pytest.fixture(autouse=True)
def _config():
    app.config['TESTING'] = True
    app.config['WTF_CSRF_ENABLED'] = False
    if not app.secret_key:
        app.secret_key = 'test-nota-e-liberacao'
    yield


def _admin():
    suf = uuid.uuid4().hex[:8]
    u = Usuario(
        username=f'nl_{suf}', email=f'nl_{suf}@test.local', nome=f'Adm {suf}',
        password_hash=generate_password_hash('Senha@2026'),
        tipo_usuario=TipoUsuario.ADMIN, ativo=True, versao_sistema='v2')
    db.session.add(u)
    db.session.commit()
    return u


def _obra(admin_id):
    suf = uuid.uuid4().hex[:8]
    cliente = Cliente(nome=f'Cliente {suf}', admin_id=admin_id)
    db.session.add(cliente)
    db.session.commit()
    o = Obra(nome=f'Obra {suf}', codigo=f'O{suf[:6].upper()}',
             data_inicio=date(2026, 1, 1), admin_id=admin_id,
             cliente_id=cliente.id, ativo=True)
    db.session.add(o)
    db.session.commit()
    return o


def _fornecedor(admin_id):
    f = Fornecedor(nome='Forn Teste', cnpj=uuid.uuid4().hex[:14],
                   admin_id=admin_id, ativo=True)
    db.session.add(f)
    db.session.commit()
    return f


def _pedido(admin_id, obra_id, fornecedor_id):
    p = PedidoCompra(
        numero=f'PC-{uuid.uuid4().hex[:6].upper()}',
        fornecedor_id=fornecedor_id, data_compra=date(2026, 8, 1),
        obra_id=obra_id, condicao_pagamento='a_vista', parcelas=1,
        valor_total=Decimal('1625.00'), tipo_compra='normal',
        processada_apos_aprovacao=False, admin_id=admin_id)
    db.session.add(p)
    db.session.commit()
    db.session.add(PedidoCompraItem(
        pedido_id=p.id, descricao='Cimento CP-II', quantidade=Decimal('50'),
        preco_unitario=Decimal('32.50'), subtotal=Decimal('1625.00'),
        admin_id=admin_id))
    db.session.commit()
    return p


# ---------------------------------------------------------------------------
# N1 — a coluna da liberação excepcional
# ---------------------------------------------------------------------------

def test_conta_nova_nasce_sem_justificativa_de_liberacao():
    """`liberacao_justificativa` não-nulo SIGNIFICA liberação excepcional.

    Por isso o default é NULL e não string vazia: `''` seria uma exceção em
    branco, e a pergunta "quais contas foram liberadas por exceção" passaria a
    depender de quem lembrou de não escrever nada.
    """
    with app.app_context():
        adm = _admin()
        obra = _obra(adm.id)
        forn = _fornecedor(adm.id)

        cp = ContaPagar(
            fornecedor_id=forn.id, obra_id=obra.id, descricao='Conta de teste',
            valor_original=Decimal('1625.00'), saldo=Decimal('1625.00'),
            data_emissao=date(2026, 8, 1), data_vencimento=date(2026, 9, 1),
            admin_id=adm.id)
        db.session.add(cp)
        db.session.commit()

        assert cp.liberacao_justificativa is None


def test_coluna_existe_no_banco_e_e_nullable():
    """A migration 308 roda no banco de dev — e a coluna aceita NULL.

    Conta histórica não tem exceção a declarar, e é por isso que a 308 não tem
    backfill. Um NOT NULL aqui obrigaria a inventar um texto para 235 mil linhas
    que nunca passaram por exceção nenhuma.
    """
    from sqlalchemy import inspect
    with app.app_context():
        colunas = {c['name']: c
                   for c in inspect(db.engine).get_columns('conta_pagar')}
        assert 'liberacao_justificativa' in colunas, (
            'migration 308 não aplicada — rode o boot do app antes desta suíte')
        assert colunas['liberacao_justificativa']['nullable'] is True
