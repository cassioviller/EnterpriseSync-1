"""Fase 6 / Task 6 — revisão de proposta não pode apagar a medição dimensional.

`propostas_consolidated.py:1431` (rota `POST /propostas/<id>/nova-versao`)
clona os `PropostaItem` da origem ao criar uma nova versão. O clone copia
quantidade, preço, snapshot de composição etc., mas NÃO copiava os 6 campos
de medição dimensional (`models.py:4012-4017`, Task #36):
`tipo_medicao_override`, `dim_largura`, `dim_comprimento`, `dim_perimetro`,
`dim_pe_direito`, `dim_area_manual`. Revisar uma proposta com item medido
por dimensão (ex.: pintura por m² calculado de largura × comprimento)
zerava essas 6 colunas na v2 — e o PDF da proposta perdia as dimensões.

Este teste cobre duas coisas na mesma chamada de rota:

1. A CORREÇÃO — os 6 campos dimensionais da v2 têm que bater com os da v1.
2. REGRESSÃO — `proposta_item_origem_id` do item da v2 aponta para o item
   da v1 (a RAIZ, não o pai — ver comentário em `models.py:3979-3987` e
   `propostas_consolidated.py:1434-1437`). Isso já funciona hoje; não pode
   quebrar.
"""
import os
import sys
import uuid
from datetime import date
from decimal import Decimal

import pytest
from werkzeug.security import generate_password_hash

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import main  # noqa: F401 — registra blueprints e handlers de evento
from app import app, db
from models import Cliente, Proposta, PropostaItem, TipoUsuario, Usuario

pytestmark = pytest.mark.integration


@pytest.fixture(autouse=True)
def _config():
    app.config['TESTING'] = True
    app.config['WTF_CSRF_ENABLED'] = False
    if not app.secret_key:
        app.secret_key = 'test-fase6-rastreabilidade-itens'
    yield


def _cliente_http(user_id):
    """Test client autenticado por injeção de sessão (flask-login)."""
    c = app.test_client()
    with c.session_transaction() as sess:
        sess['_user_id'] = str(user_id)
        sess['_fresh'] = True
    return c


@pytest.fixture
def cenario():
    """Admin + cliente + proposta v1 com um item medido por dimensão."""
    with app.app_context():
        s = uuid.uuid4().hex[:8]
        admin = Usuario(
            username=f'f6ri_{s}', email=f'f6ri_{s}@test.local',
            nome=f'Admin {s}',
            password_hash=generate_password_hash('Senha@2026'),
            tipo_usuario=TipoUsuario.ADMIN, ativo=True, versao_sistema='v2',
        )
        db.session.add(admin)
        db.session.flush()

        cliente = Cliente(admin_id=admin.id, nome=f'Cliente {s}',
                          email=f'cli_{s}@test.local', telefone='11988887777')
        db.session.add(cliente)
        db.session.flush()

        proposta = Proposta(
            admin_id=admin.id, numero=f'P{s}',
            cliente_nome=cliente.nome, cliente_id=cliente.id,
            versao=1, valor_total=Decimal('5000.00'),
            status='rascunho', data_proposta=date(2026, 8, 1),
        )
        db.session.add(proposta)
        db.session.flush()

        item = PropostaItem(
            admin_id=admin.id, proposta_id=proposta.id, item_numero=1,
            ordem=1, descricao='Pintura de fachada', quantidade=Decimal('50'),
            unidade='m2', preco_unitario=Decimal('100.00'),
            subtotal=Decimal('5000.00'),
            # Task #36 — medição dimensional (área calculada de largura x
            # comprimento). É exatamente o que a revisão apagava.
            tipo_medicao_override='area_retangular',
            dim_largura=Decimal('5.0'),
            dim_comprimento=Decimal('10.0'),
            dim_perimetro=Decimal('30.0'),
            dim_pe_direito=Decimal('3.0'),
            dim_area_manual=Decimal('50.0'),
        )
        db.session.add(item)
        db.session.commit()

        yield {
            'admin_id': admin.id, 'proposta_id': proposta.id,
            'item_v1_id': item.id,
        }


def test_nova_versao_preserva_medicao_dimensional_e_linhagem(cenario):
    admin_id = cenario['admin_id']
    proposta_id = cenario['proposta_id']
    item_v1_id = cenario['item_v1_id']

    c = _cliente_http(admin_id)
    r = c.post(f'/propostas/{proposta_id}/nova-versao', follow_redirects=False)
    assert r.status_code in (302, 303), (
        f'esperava redirect após criar a nova versão — veio {r.status_code}: '
        f'{r.get_data(as_text=True)[:500]}')

    with app.app_context():
        origem = db.session.get(Proposta, proposta_id)
        assert origem.substituida_por_id, (
            'a proposta original deveria ter sido marcada como substituída')
        v2 = db.session.get(Proposta, origem.substituida_por_id)
        assert v2 is not None and v2.versao == 2

        itens_v2 = PropostaItem.query.filter_by(proposta_id=v2.id).all()
        assert len(itens_v2) == 1, (
            f'esperava exatamente 1 item clonado na v2 — achei {len(itens_v2)}')
        item_v2 = itens_v2[0]

        # 1) A correção: os 6 campos dimensionais sobrevivem à revisão.
        assert item_v2.tipo_medicao_override == 'area_retangular'
        assert item_v2.dim_largura == Decimal('5.0000')
        assert item_v2.dim_comprimento == Decimal('10.0000')
        assert item_v2.dim_perimetro == Decimal('30.0000')
        assert item_v2.dim_pe_direito == Decimal('3.0000')
        assert item_v2.dim_area_manual == Decimal('50.0000')

        # 2) Regressão: a linhagem aponta para a RAIZ (item da v1), não para
        # um item intermediário — já funcionava antes desta task.
        assert item_v2.proposta_item_origem_id == item_v1_id
