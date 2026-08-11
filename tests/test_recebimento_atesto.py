"""Recebimento e atesto — fase 1 do ciclo de compras.

Spec: docs/superpowers/specs/2026-08-11-recebimento-atesto-design.md
Plano: docs/superpowers/plans/2026-08-11-plano-execucao-recebimento-atesto.md

O material que chega na obra passa a ser um fato registrado: quem recebeu,
quando, quanto, com que divergência — e é ESSE registro que dá entrada no
estoque, não mais a emissão do pedido.

Molde de tests/test_fase3_portal_seguranca.py: fixtures locais, tenant por
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
from models import (Cliente, Fornecedor, Obra, PedidoCompra, PedidoCompraItem,
                    TipoUsuario, Usuario)

pytestmark = pytest.mark.integration


@pytest.fixture(autouse=True)
def _config():
    app.config['TESTING'] = True
    app.config['WTF_CSRF_ENABLED'] = False
    if not app.secret_key:
        app.secret_key = 'test-recebimento-atesto'
    yield


def _admin():
    suf = uuid.uuid4().hex[:8]
    u = Usuario(
        username=f'rec_{suf}', email=f'rec_{suf}@test.local', nome=f'Adm {suf}',
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


def _pedido(admin_id, obra_id, fornecedor_id, itens=(('Cimento CP-II', 50, 32.50),)):
    p = PedidoCompra(
        numero=f'PC-{uuid.uuid4().hex[:6].upper()}',
        fornecedor_id=fornecedor_id, data_compra=date(2026, 8, 1),
        obra_id=obra_id, condicao_pagamento='a_vista', parcelas=1,
        valor_total=Decimal('1625.00'), tipo_compra='normal',
        processada_apos_aprovacao=False, admin_id=admin_id)
    db.session.add(p)
    db.session.commit()
    for desc, qtd, preco in itens:
        db.session.add(PedidoCompraItem(
            pedido_id=p.id, descricao=desc, quantidade=Decimal(str(qtd)),
            preco_unitario=Decimal(str(preco)),
            subtotal=Decimal(str(qtd)) * Decimal(str(preco)), admin_id=admin_id))
    db.session.commit()
    return p


# ---------------------------------------------------------------------------
# R1 — o esqueleto: modelos, constraints e os defaults do regime
# ---------------------------------------------------------------------------

def test_modelos_de_recebimento_existem():
    """As duas tabelas do spec são importáveis de `models`."""
    from models import RecebimentoPedido, RecebimentoPedidoItem
    assert RecebimentoPedido.__tablename__ == 'recebimento_pedido'
    assert RecebimentoPedidoItem.__tablename__ == 'recebimento_pedido_item'


def test_pedido_novo_nasce_no_regime_antigo():
    """`exige_atesto` e `situacao_recebimento` têm default de linha.

    Um pedido criado sem passar pelas rotas (como este) tem que nascer no
    regime ANTIGO. O default no banco é o que garante que a migration não
    deixe NULL em pedido histórico — é o backfill que não precisou existir.
    """
    with app.app_context():
        admin = _admin()
        obra = _obra(admin.id)
        forn = _fornecedor(admin.id)
        pedido = _pedido(admin.id, obra.id, forn.id)

        db.session.refresh(pedido)
        assert pedido.exige_atesto is False
        assert pedido.situacao_recebimento == 'nao_recebido'


def test_sequencia_nao_repete_no_mesmo_pedido():
    """UNIQUE (pedido_id, sequencia) — "PC-1234/2" tem que ser um só."""
    from sqlalchemy.exc import IntegrityError

    from models import RecebimentoPedido

    with app.app_context():
        admin = _admin()
        obra = _obra(admin.id)
        forn = _fornecedor(admin.id)
        pedido = _pedido(admin.id, obra.id, forn.id)

        db.session.add(RecebimentoPedido(
            pedido_id=pedido.id, admin_id=admin.id, sequencia=1,
            recebido_por_id=admin.id, data_recebimento=date(2026, 8, 5)))
        db.session.commit()

        db.session.add(RecebimentoPedido(
            pedido_id=pedido.id, admin_id=admin.id, sequencia=1,
            recebido_por_id=admin.id, data_recebimento=date(2026, 8, 6)))
        with pytest.raises(IntegrityError):
            db.session.commit()
        db.session.rollback()


def test_mesmo_item_nao_entra_duas_vezes_no_mesmo_recebimento():
    """UNIQUE (recebimento_id, pedido_item_id).

    Duas linhas do mesmo item no mesmo atesto seriam duas quantidades para o
    mesmo fato — e a soma por item, que decide a situação do pedido, passaria
    a depender de qual linha alguém editou por último.
    """
    from sqlalchemy.exc import IntegrityError

    from models import RecebimentoPedido, RecebimentoPedidoItem

    with app.app_context():
        admin = _admin()
        obra = _obra(admin.id)
        forn = _fornecedor(admin.id)
        pedido = _pedido(admin.id, obra.id, forn.id)
        item = PedidoCompraItem.query.filter_by(pedido_id=pedido.id).first()

        rec = RecebimentoPedido(
            pedido_id=pedido.id, admin_id=admin.id, sequencia=1,
            recebido_por_id=admin.id, data_recebimento=date(2026, 8, 5))
        db.session.add(rec)
        db.session.commit()

        db.session.add(RecebimentoPedidoItem(
            recebimento_id=rec.id, admin_id=admin.id, pedido_item_id=item.id,
            quantidade_recebida=Decimal('30')))
        db.session.commit()

        db.session.add(RecebimentoPedidoItem(
            recebimento_id=rec.id, admin_id=admin.id, pedido_item_id=item.id,
            quantidade_recebida=Decimal('20')))
        with pytest.raises(IntegrityError):
            db.session.commit()
        db.session.rollback()


# ---------------------------------------------------------------------------
# R2 — a flag por tenant e o carimbo do regime
# ---------------------------------------------------------------------------

def _ligar_flag(admin_id, valor=True):
    from scripts.flag_recebimento_atesto import definir_flag
    return definir_flag(admin_id, valor)


def test_flag_desligada_por_padrao():
    """Ninguém vira sozinho: tenant novo nasce no regime antigo."""
    from scripts.flag_recebimento_atesto import recebimento_atesto_ativo
    with app.app_context():
        admin = _admin()
        assert recebimento_atesto_ativo(admin.id) is False


def test_flag_falha_fechada():
    """Qualquer erro devolve False — o regime NOVO nunca liga por acidente.

    Mesma postura de `governanca_ativa` (scripts/flag_compras_governanca.py):
    numa flag que muda de onde o estoque recebe entrada, o modo de falha
    seguro é o comportamento ANTIGO.
    """
    from scripts.flag_recebimento_atesto import recebimento_atesto_ativo
    with app.app_context():
        assert recebimento_atesto_ativo(None) is False
        assert recebimento_atesto_ativo(999_999_999) is False


def test_carimbo_do_regime_segue_a_flag():
    """O pedido nasce com o regime que o tenant tinha NAQUELE momento."""
    from services.recebimento_pedido import regime_do_tenant
    with app.app_context():
        admin = _admin()
        assert regime_do_tenant(admin.id) is False

        _ligar_flag(admin.id, True)
        assert regime_do_tenant(admin.id) is True


def test_desligar_a_flag_nao_muda_pedido_ja_criado():
    """O teste que trava a razão de carimbar na LINHA em vez de comparar datas.

    A flag é um booleano que alguém liga e desliga. Se o regime fosse
    `created_at > data_de_corte`, cada toggle reinterpretaria retroativamente
    pedidos já fechados — um pedido recebido sob o regime antigo passaria a
    ser cobrado pelo novo. Carimbado na linha, o passado não se move.
    """
    with app.app_context():
        admin = _admin()
        obra = _obra(admin.id)
        forn = _fornecedor(admin.id)

        _ligar_flag(admin.id, True)
        from services.recebimento_pedido import regime_do_tenant
        pedido = _pedido(admin.id, obra.id, forn.id)
        pedido.exige_atesto = regime_do_tenant(admin.id)
        db.session.commit()
        assert pedido.exige_atesto is True

        _ligar_flag(admin.id, False)
        db.session.refresh(pedido)
        assert pedido.exige_atesto is True, (
            'desligar a flag reescreveu o regime de um pedido já criado')


def test_todo_ponto_que_cria_pedido_carimba_o_regime():
    """Guarda de fonte: nenhum `PedidoCompra(...)` sem `exige_atesto`.

    Os testes de cima exercitam `regime_do_tenant`, não a LIGAÇÃO dele nas
    rotas — os dois carimbos poderiam sumir num refactor e nada ficaria
    vermelho. Um pedido criado sem carimbo nasce no regime antigo por default
    da coluna: silenciosamente, o estoque volta a entrar na emissão para
    aquele caminho, e ninguém descobre até o estoque não bater.

    Mesmo formato do teste de fonte em tests/test_p4_formula_unica_progresso.py.
    Se um terceiro ponto de criação nascer, este teste exige que ele decida
    sobre o regime em vez de herdar o default por descuido.
    """
    import re

    caminho = os.path.join(
        os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
        'compras_views.py')
    with open(caminho, encoding='utf-8') as f:
        fonte = f.read()

    # Cada construção de PedidoCompra e o que vem até o fecha-parênteses.
    construcoes = re.findall(r'PedidoCompra\((.*?)\n\s*\)', fonte, re.DOTALL)
    assert construcoes, 'nenhuma construção de PedidoCompra encontrada'
    sem_carimbo = [c for c in construcoes if 'exige_atesto' not in c]
    assert not sem_carimbo, (
        f'{len(sem_carimbo)} de {len(construcoes)} construções de PedidoCompra '
        f'não carimbam `exige_atesto`. Um pedido sem carimbo cai no regime '
        f'antigo por default e o estoque volta a entrar na emissão sem aviso.')


def test_guard_recusa_ligar_sem_almoxarifado():
    """Ligar em tenant sem catálogo cria pedido que ninguém consegue receber.

    Com o regime novo o estoque só entra pelo atesto, e o atesto só gera
    movimento para item de catálogo. Tenant sem `AlmoxarifadoItem` nenhum
    ligaria a chave e ficaria sem entrada de estoque em lugar nenhum.
    """
    from scripts.flag_recebimento_atesto import pode_ligar
    with app.app_context():
        admin = _admin()
        ok, motivo = pode_ligar(admin.id)
        assert ok is False
        assert 'almoxarifado' in motivo.lower()
