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


# ---------------------------------------------------------------------------
# R3 — o serviço: documento, validações e situação derivada
# ---------------------------------------------------------------------------

def _cenario_pedido(qtd=50):
    """Tenant + obra + pedido de UM item com `qtd` unidades, regime novo."""
    admin = _admin()
    obra = _obra(admin.id)
    forn = _fornecedor(admin.id)
    pedido = _pedido(admin.id, obra.id, forn.id,
                     itens=(('Cimento CP-II', qtd, 32.50),))
    pedido.exige_atesto = True
    db.session.commit()
    item = PedidoCompraItem.query.filter_by(pedido_id=pedido.id).first()
    return admin, obra, pedido, item


def _receber(pedido, usuario, item, qtd, **kw):
    from services.recebimento_pedido import registrar_recebimento
    return registrar_recebimento(
        pedido, usuario, [(item.id, Decimal(str(qtd)))],
        data=kw.pop('data', date(2026, 8, 5)), **kw)


def test_recebimento_parcial_deixa_o_pedido_parcial():
    with app.app_context():
        admin, _obr, pedido, item = _cenario_pedido(50)
        _receber(pedido, admin, item, 30)
        db.session.refresh(pedido)
        assert pedido.situacao_recebimento == 'parcial'


def test_segundo_recebimento_completa_o_pedido():
    """As quantidades ACUMULAM entre entregas — 30 + 20 fecha os 50."""
    with app.app_context():
        admin, _obr, pedido, item = _cenario_pedido(50)
        _receber(pedido, admin, item, 30)
        _receber(pedido, admin, item, 20, data=date(2026, 8, 7))
        db.session.refresh(pedido)
        assert pedido.situacao_recebimento == 'recebido'


def test_encerrar_saldo_faltando_quantidade():
    """"Chegaram 48 dos 50 e o resto não vem" — fecha, mas fica marcado."""
    with app.app_context():
        admin, _obr, pedido, item = _cenario_pedido(50)
        _receber(pedido, admin, item, 48, encerra_saldo=True,
                 motivo='fornecedor não entrega o saldo')
        db.session.refresh(pedido)
        assert pedido.situacao_recebimento == 'encerrado_com_saldo'


def test_encerrar_saldo_com_tudo_entregue_e_so_recebido():
    """A ordem de avaliação importa: encerrar o que já veio inteiro não é
    "encerrado com saldo" — não há saldo. Sem esta regra o relatório de
    saldo em aberto contaria pedido completo."""
    with app.app_context():
        admin, _obr, pedido, item = _cenario_pedido(50)
        _receber(pedido, admin, item, 50, encerra_saldo=True,
                 motivo='entrega única')
        db.session.refresh(pedido)
        assert pedido.situacao_recebimento == 'recebido'


@pytest.mark.parametrize('qtd', [0, -5])
def test_quantidade_nao_positiva_recusa(qtd):
    """Devolução não é recebimento negativo, e não entra nesta fase."""
    from services.recebimento_pedido import RecebimentoInvalido
    with app.app_context():
        admin, _obr, pedido, item = _cenario_pedido(50)
        with pytest.raises(RecebimentoInvalido):
            _receber(pedido, admin, item, qtd)


def test_sobre_entrega_recusa_por_padrao():
    from services.recebimento_pedido import RecebimentoInvalido
    with app.app_context():
        admin, _obr, pedido, item = _cenario_pedido(50)
        with pytest.raises(RecebimentoInvalido) as e:
            _receber(pedido, admin, item, 60)
        assert '50' in str(e.value)


def test_sobre_entrega_passa_quando_liberada():
    """Mesmo par bloqueio-com-liberação-explícita do `permitir_sobreexecucao`
    do RDO: chegar mais é legítimo, passar despercebido não é."""
    with app.app_context():
        admin, _obr, pedido, item = _cenario_pedido(50)
        _receber(pedido, admin, item, 60, permitir_sobre_entrega=True)
        db.session.refresh(pedido)
        assert pedido.situacao_recebimento == 'recebido'


def test_encerrar_saldo_sem_motivo_recusa():
    """O motivo é o que torna o encerramento auditável seis meses depois."""
    from services.recebimento_pedido import RecebimentoInvalido
    with app.app_context():
        admin, _obr, pedido, item = _cenario_pedido(50)
        with pytest.raises(RecebimentoInvalido) as e:
            _receber(pedido, admin, item, 48, encerra_saldo=True)
        assert 'motivo' in str(e.value).lower()


def test_recebimento_depois_de_encerrado_recusa_dizendo_quem_e_quando():
    with app.app_context():
        from services.recebimento_pedido import RecebimentoInvalido
        admin, _obr, pedido, item = _cenario_pedido(50)
        _receber(pedido, admin, item, 48, encerra_saldo=True,
                 motivo='fornecedor não entrega o saldo')

        with pytest.raises(RecebimentoInvalido) as e:
            _receber(pedido, admin, item, 2, data=date(2026, 8, 9))
        msg = str(e.value)
        assert admin.nome in msg, 'a recusa tem que dizer QUEM encerrou'
        assert '05/08/2026' in msg, 'a recusa tem que dizer QUANDO'


def test_sequencia_incrementa_por_pedido():
    from models import RecebimentoPedido
    with app.app_context():
        admin, _obr, pedido, item = _cenario_pedido(90)
        for i, qtd in enumerate([10, 20, 30], start=1):
            rec = _receber(pedido, admin, item, qtd,
                           data=date(2026, 8, 5 + i))
            assert rec.sequencia == i
            assert rec.rotulo.endswith(f'/{i}')
        assert RecebimentoPedido.query.filter_by(pedido_id=pedido.id).count() == 3


def test_situacao_para_e_pura_e_bate_com_o_persistido():
    """A função que o sensor de drift da R7 vai reusar."""
    from services.recebimento_pedido import situacao_para
    with app.app_context():
        admin, _obr, pedido, item = _cenario_pedido(50)
        assert situacao_para(pedido) == 'nao_recebido'
        _receber(pedido, admin, item, 30)
        db.session.refresh(pedido)
        assert situacao_para(pedido) == pedido.situacao_recebimento == 'parcial'


# --- quem pode atestar -----------------------------------------------------

def _pessoa_com_papel(admin_id, obra_id, papel):
    """Usuário do tenant com vínculo de obra, e o escopo LIGADO.

    Sem `escopo_obra_ativo`, `papel_na_obra` devolve GESTOR para todo
    autenticado do tenant (comportamento pré-Fase 1) e a distinção de papéis
    — que é o que este bloco testa — não vale.
    """
    from models import PapelObra, UsuarioObra
    from scripts.flag_escopo_obra import definir_flag as _escopo

    _escopo(admin_id, True)
    suf = uuid.uuid4().hex[:8]
    u = Usuario(
        username=f'rp_{suf}', email=f'rp_{suf}@test.local', nome=f'P {suf}',
        password_hash=generate_password_hash('Senha@2026'),
        tipo_usuario=TipoUsuario.FUNCIONARIO, ativo=True,
        versao_sistema='v2', admin_id=admin_id)
    db.session.add(u)
    db.session.commit()
    db.session.add(UsuarioObra(usuario_id=u.id, obra_id=obra_id,
                               papel=PapelObra[papel], ativo=True,
                               admin_id=admin_id))
    db.session.commit()
    return u


@pytest.mark.parametrize('papel', ['GESTOR', 'APONTADOR', 'COMPRADOR'])
def test_papeis_de_obra_podem_atestar(papel):
    """Quem está na obra recebe o caminhão. Decisão explícita do spec: não há
    checagem de "foi você que pediu" — em equipe pequena é sempre a mesma
    pessoa, e travar isso deixaria material parado no portão."""
    with app.app_context():
        admin, obra, pedido, item = _cenario_pedido(50)
        pessoa = _pessoa_com_papel(admin.id, obra.id, papel)
        _receber(pedido, pessoa, item, 10)
        db.session.refresh(pedido)
        assert pedido.situacao_recebimento == 'parcial'


def test_leitor_nao_atesta():
    """LEITOR é só leitura em toda a Fase 1, e atestar é escrita que libera
    dinheiro na fase seguinte."""
    from services.recebimento_pedido import RecebimentoInvalido
    with app.app_context():
        admin, obra, pedido, item = _cenario_pedido(50)
        leitor = _pessoa_com_papel(admin.id, obra.id, 'LEITOR')
        with pytest.raises(RecebimentoInvalido):
            _receber(pedido, leitor, item, 10)


def test_sem_vinculo_com_a_obra_nao_atesta():
    from services.recebimento_pedido import RecebimentoInvalido
    with app.app_context():
        admin, obra, pedido, item = _cenario_pedido(50)
        from scripts.flag_escopo_obra import definir_flag as _escopo
        _escopo(admin.id, True)
        suf = uuid.uuid4().hex[:8]
        estranho = Usuario(
            username=f'rx_{suf}', email=f'rx_{suf}@test.local', nome='Sem Vinculo',
            password_hash=generate_password_hash('Senha@2026'),
            tipo_usuario=TipoUsuario.FUNCIONARIO, ativo=True,
            versao_sistema='v2', admin_id=admin.id)
        db.session.add(estranho)
        db.session.commit()
        with pytest.raises(RecebimentoInvalido):
            _receber(pedido, estranho, item, 10)


# ---------------------------------------------------------------------------
# R4 — o estoque passa a nascer do atesto
# ---------------------------------------------------------------------------
#
# O conserto da dupla escrita. Até aqui o estoque entrava DUAS vezes na
# cabeça de quem lê o código e UMA no banco, no momento errado: a emissão do
# pedido lançava tudo (compras_views._gerar_entrada_almoxarifado) e a rota
# /receber lançava "o que falta" — que já era zero. Deste bloco em diante,
# pedido com `exige_atesto=True` não lança nada na emissão, e cada atesto
# lança exatamente a quantidade que chegou.
#
# O quarto teste é o que protege produção: com a flag desligada, tudo tem de
# continuar movimento a movimento como está hoje.


def _item_de_catalogo(admin_id, nome='Cimento CP-II'):
    """Um item do catálogo do almoxarifado — o que separa atesto COM movimento
    de atesto sem movimento."""
    from models import AlmoxarifadoCategoria, AlmoxarifadoItem

    suf = uuid.uuid4().hex[:8]
    cat = AlmoxarifadoCategoria(
        nome=f'Cat {suf}', tipo_controle_padrao='CONSUMIVEL', admin_id=admin_id)
    db.session.add(cat)
    db.session.commit()
    it = AlmoxarifadoItem(
        codigo=f'C{suf[:6].upper()}', nome=nome, categoria_id=cat.id,
        tipo_controle='CONSUMIVEL', unidade='sc', admin_id=admin_id)
    db.session.add(it)
    db.session.commit()
    return it


def _cenario_com_catalogo(qtd=50, exige_atesto=True):
    """Pedido de UM item vinculado ao catálogo, no regime pedido."""
    admin = _admin()
    obra = _obra(admin.id)
    forn = _fornecedor(admin.id)
    pedido = _pedido(admin.id, obra.id, forn.id,
                     itens=(('Cimento CP-II', qtd, 32.50),))
    almox = _item_de_catalogo(admin.id)
    pedido.exige_atesto = exige_atesto
    item = PedidoCompraItem.query.filter_by(pedido_id=pedido.id).first()
    item.almoxarifado_item_id = almox.id
    db.session.commit()
    return admin, obra, pedido, item, almox


def _itens_validos(pedido):
    """As tuplas que a emissão passa para `_gerar_entrada_almoxarifado`."""
    return [(i.descricao, float(i.quantidade), float(i.preco_unitario),
             i.almoxarifado_item_id, float(i.subtotal))
            for i in PedidoCompraItem.query.filter_by(pedido_id=pedido.id).all()]


def _entradas(pedido_id):
    from models import AlmoxarifadoMovimento
    return (AlmoxarifadoMovimento.query
            .filter_by(pedido_compra_id=pedido_id, tipo_movimento='ENTRADA')
            .all())


def test_emissao_nao_lanca_estoque_quando_o_pedido_exige_atesto():
    """A regressão que impede a dupla escrita de voltar.

    Hoje a emissão lança TUDO — e é por isso que a rota /receber virou no-op.
    Com o regime novo, emitir não é receber: o caminhão ainda nem saiu.
    """
    from compras_views import processar_compra_normal
    with app.app_context():
        admin, _obr, pedido, _item, _almox = _cenario_com_catalogo(50)
        processar_compra_normal(pedido, _itens_validos(pedido), admin.id, admin.id)
        db.session.commit()

        assert _entradas(pedido.id) == [], (
            'a emissão lançou estoque de um pedido que exige atesto — o '
            'material entrou no almoxarifado antes de chegar na obra')


def test_emissao_continua_lancando_estoque_no_regime_antigo():
    """O teste que guarda quem está em produção.

    Tenant sem a flag não pode perceber nada: emitir continua lançando a
    quantidade inteira, e a saída de consumo direto na obra continua saindo.
    Se este ficar vermelho, a virada vazou para fora da flag.
    """
    from compras_views import processar_compra_normal
    from models import AlmoxarifadoMovimento
    with app.app_context():
        admin, _obr, pedido, _item, _almox = _cenario_com_catalogo(
            50, exige_atesto=False)
        processar_compra_normal(pedido, _itens_validos(pedido), admin.id, admin.id)
        db.session.commit()

        entradas = _entradas(pedido.id)
        assert len(entradas) == 1, 'a emissão deixou de lançar no regime antigo'
        assert float(entradas[0].quantidade) == 50.0
        saidas = (AlmoxarifadoMovimento.query
                  .filter_by(pedido_compra_id=pedido.id, tipo_movimento='SAIDA')
                  .count())
        assert saidas == 1, 'o consumo direto na obra sumiu do regime antigo'


def test_atesto_gera_entrada_com_a_quantidade_recebida():
    """30 dos 50 chegaram → ENTRADA de 30, com lote, e o vínculo de volta.

    O `almoxarifado_movimento_id` na linha do recebimento é o que permite
    auditar "esta entrada veio deste atesto" — e o que torna o estorno da R5
    possível sem adivinhação.
    """
    from models import AlmoxarifadoEstoque, RecebimentoPedidoItem
    with app.app_context():
        admin, _obr, pedido, item, almox = _cenario_com_catalogo(50)
        rec = _receber(pedido, admin, item, 30)

        entradas = _entradas(pedido.id)
        assert len(entradas) == 1, 'o atesto não gerou movimento de estoque'
        mov = entradas[0]
        assert mov.item_id == almox.id
        assert float(mov.quantidade) == 30.0, (
            'o movimento tem de ter a quantidade RECEBIDA, não a pedida')
        assert mov.lote or True  # o lote vive no AlmoxarifadoEstoque
        assert mov.pedido_compra_id == pedido.id, (
            'sem `pedido_compra_id` a dedup do handler material_entrada do '
            'EventManager conta o custo duas vezes')

        lote = AlmoxarifadoEstoque.query.filter_by(
            entrada_movimento_id=mov.id).first()
        assert lote is not None, 'entrada sem lote FIFO não sai do estoque'
        assert float(lote.quantidade_disponivel) == 30.0

        linha = RecebimentoPedidoItem.query.filter_by(
            recebimento_id=rec.id, pedido_item_id=item.id).first()
        assert linha.almoxarifado_movimento_id == mov.id, (
            'a linha do recebimento não guardou o movimento que gerou')


def test_item_de_texto_livre_tem_atesto_e_nao_tem_movimento():
    """O "outro" da requisição: tem recebimento, não tem estoque.

    Item fora do catálogo não pode gerar movimento — não há o que movimentar
    —, mas o fato de ter chegado continua registrado. `situacao_recebimento`
    conta com ele.
    """
    from models import RecebimentoPedidoItem
    with app.app_context():
        admin = _admin()
        obra = _obra(admin.id)
        forn = _fornecedor(admin.id)
        pedido = _pedido(admin.id, obra.id, forn.id,
                         itens=(('Frete do caminhão', 1, 350.00),))
        pedido.exige_atesto = True
        db.session.commit()
        item = PedidoCompraItem.query.filter_by(pedido_id=pedido.id).first()
        assert item.almoxarifado_item_id is None, 'sanidade: é texto livre'

        rec = _receber(pedido, admin, item, 1)

        assert _entradas(pedido.id) == [], (
            'item fora do catálogo gerou movimento de estoque')
        linha = RecebimentoPedidoItem.query.filter_by(
            recebimento_id=rec.id).first()
        assert linha is not None, 'o atesto do item de texto livre sumiu'
        assert linha.almoxarifado_movimento_id is None
        db.session.refresh(pedido)
        assert pedido.situacao_recebimento == 'recebido'


def test_recebimento_de_pedido_legado_nao_lanca_estoque_de_novo():
    """A dupla escrita com o sinal trocado — o defeito que a virada poderia
    criar em vez de consertar.

    O estoque de pedido legado já entrou na EMISSÃO. Se o serviço novo
    lançasse de novo ao atestar, o almoxarifado passaria a contar 80 onde
    chegaram 50. O documento de recebimento é gravado (o fato aconteceu);
    o movimento, não.
    """
    from compras_views import processar_compra_normal
    from models import RecebimentoPedidoItem
    with app.app_context():
        admin, _obr, pedido, item, _almox = _cenario_com_catalogo(
            50, exige_atesto=False)
        processar_compra_normal(pedido, _itens_validos(pedido), admin.id, admin.id)
        db.session.commit()
        assert len(_entradas(pedido.id)) == 1, 'sanidade: a emissão lançou'

        rec = _receber(pedido, admin, item, 30)

        assert len(_entradas(pedido.id)) == 1, (
            'o atesto lançou estoque de um pedido cujo estoque já entrou na '
            'emissão — a dupla escrita de volta, com o sinal trocado')
        linha = RecebimentoPedidoItem.query.filter_by(
            recebimento_id=rec.id).first()
        assert linha is not None, 'o documento de recebimento tem de existir'
        assert linha.almoxarifado_movimento_id is None


def test_rota_receber_antiga_continua_valendo_para_pedido_legado():
    """A rota /receber não some: pedido legado continua recebendo por ela.

    O estoque desses pedidos já entrou na emissão; mudar isso reescreveria
    estoque histórico. Aqui a emissão não rodou, então a rota lança os 50
    pendentes — exatamente o que ela faz hoje.
    """
    from helpers_tenant import cliente_de

    with app.app_context():
        admin, _obr, pedido, _item, _almox = _cenario_com_catalogo(
            50, exige_atesto=False)
        admin_id, pedido_id = admin.id, pedido.id

    cliente_de(admin_id).post(f'/compras/receber/{pedido_id}')

    with app.app_context():
        entradas = _entradas(pedido_id)
        assert len(entradas) == 1, 'a rota antiga parou de receber pedido legado'
        assert float(entradas[0].quantidade) == 50.0
