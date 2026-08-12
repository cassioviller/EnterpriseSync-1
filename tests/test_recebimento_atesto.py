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
        assert float(lote.quantidade_inicial) == 30.0
        # O disponível é zero porque o pedido tem obra, e material que chega
        # na obra é reconhecido como consumido no ato — a saída pareada da C2.
        # Quem cuida disso é
        # `test_atesto_com_obra_gera_a_saida_de_consumo_pareada`.
        assert float(lote.quantidade_disponivel) == 0.0

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


# ---------------------------------------------------------------------------
# R5 — exclusão do último recebimento, com estorno
# ---------------------------------------------------------------------------
#
# Errar a quantidade digitada é o erro mais comum de quem recebe caminhão no
# portão. Sem exclusão, o conserto seria um segundo recebimento com número
# negativo — e quantidade negativa é justamente o que esta fase recusa.
#
# Só o ÚLTIMO sai, e só enquanto o material ainda estiver na prateleira: uma
# vez consumido, desfazer a entrada deixaria o estoque negativo e a saída
# apontando para um lote que nunca existiu.


def _lote_de(movimento_id):
    from models import AlmoxarifadoEstoque
    return AlmoxarifadoEstoque.query.filter_by(
        entrada_movimento_id=movimento_id).first()


def _excluir(recebimento, usuario):
    from services.recebimento_pedido import excluir_recebimento
    return excluir_recebimento(recebimento, usuario)


def test_excluir_o_ultimo_recebimento_estorna_o_estoque_e_recalcula():
    """30 + 20 fecha o pedido; excluir o segundo devolve o pedido a `parcial`
    e some com a ENTRADA de 20 — a de 30 fica, porque aquele atesto vale."""
    from models import RecebimentoPedido
    with app.app_context():
        admin, _obr, pedido, item, _almox = _cenario_com_catalogo(50)
        _receber(pedido, admin, item, 30)
        segundo = _receber(pedido, admin, item, 20, data=date(2026, 8, 7))
        db.session.refresh(pedido)
        assert pedido.situacao_recebimento == 'recebido', 'sanidade'
        mov_id = segundo.itens[0].almoxarifado_movimento_id

        _excluir(segundo, admin)

        db.session.refresh(pedido)
        assert pedido.situacao_recebimento == 'parcial', (
            'a situação não voltou ao que a soma dos recebimentos restantes diz')
        entradas = _entradas(pedido.id)
        assert len(entradas) == 1, 'o estorno não removeu a ENTRADA do atesto'
        assert float(entradas[0].quantidade) == 30.0, (
            'sobrou a ENTRADA errada — o estorno pegou o recebimento que fica')
        assert _lote_de(mov_id) is None, 'o lote do movimento estornado ficou'
        assert RecebimentoPedido.query.filter_by(pedido_id=pedido.id).count() == 1


def test_excluir_o_unico_recebimento_devolve_o_pedido_a_nao_recebido():
    with app.app_context():
        admin, _obr, pedido, item, _almox = _cenario_com_catalogo(50)
        rec = _receber(pedido, admin, item, 30)

        _excluir(rec, admin)

        db.session.refresh(pedido)
        assert pedido.situacao_recebimento == 'nao_recebido'
        assert _entradas(pedido.id) == []


def test_excluir_recebimento_que_nao_e_o_ultimo_recusa():
    """A sequência é 1, 2, 3 e não tem buraco.

    Furar o meio quebraria o rótulo que a tela mostra (`PC-1234/2` passaria a
    apontar para outro fato) e deixaria o acumulado do item dependendo de qual
    documento alguém apagou.
    """
    from services.recebimento_pedido import RecebimentoInvalido
    with app.app_context():
        admin, _obr, pedido, item, _almox = _cenario_com_catalogo(50)
        primeiro = _receber(pedido, admin, item, 30)
        _receber(pedido, admin, item, 20, data=date(2026, 8, 7))

        with pytest.raises(RecebimentoInvalido) as e:
            _excluir(primeiro, admin)
        assert '/2' in str(e.value), (
            'a recusa tem que dizer QUAL é o último — sem isso quem errou não '
            'sabe o que excluir primeiro')
        assert len(_entradas(pedido.id)) == 2, 'a recusa estornou alguma coisa'


def test_excluir_recusa_quando_o_lote_ja_teve_saida():
    """Material consumido não volta pelo desfazer.

    Estornar aqui deixaria o estoque negativo e a saída apontando para um lote
    que deixou de existir. A recusa nomeia o item porque quem recebeu precisa
    saber o que já foi usado antes de decidir o que fazer.
    """
    from services.recebimento_pedido import RecebimentoInvalido
    with app.app_context():
        admin, _obr, pedido, item, almox = _cenario_com_catalogo(50)
        rec = _receber(pedido, admin, item, 30)

        # O que a saída do almoxarifado faz com o lote (views/almoxarifado/
        # movimentos.py): baixa o disponível e marca CONSUMIDO no zero.
        lote = _lote_de(rec.itens[0].almoxarifado_movimento_id)
        lote.quantidade_disponivel = Decimal('10')
        lote.quantidade = Decimal('10')
        db.session.commit()

        with pytest.raises(RecebimentoInvalido) as e:
            _excluir(rec, admin)
        assert almox.nome in str(e.value), (
            'a recusa tem que nomear o item que já foi consumido')
        assert len(_entradas(pedido.id)) == 1, 'a recusa estornou mesmo assim'


def test_leitor_nao_exclui_recebimento():
    """Excluir é escrita sobre o mesmo fato que atestar — mesma porta."""
    from services.recebimento_pedido import RecebimentoInvalido
    with app.app_context():
        admin, obra, pedido, item, _almox = _cenario_com_catalogo(50)
        rec = _receber(pedido, admin, item, 30)
        leitor = _pessoa_com_papel(admin.id, obra.id, 'LEITOR')

        with pytest.raises(RecebimentoInvalido):
            _excluir(rec, leitor)
        assert len(_entradas(pedido.id)) == 1


# ---------------------------------------------------------------------------
# R6 — a tela de recebimento na obra
# ---------------------------------------------------------------------------
#
# O defeito que esta rodada conserta na interface: hoje o botão "Registrar
# Recebimento no Estoque" do detalhe aceita o clique em pedido 'normal' e não
# faz nada — o estoque já entrou na emissão, então a rota antiga calcula
# pendente=0 e sai. Um no-op silencioso é pior que uma recusa: quem clicou
# acha que registrou.
#
# A tela nova é para o celular de quem está no portão da obra: uma quantidade
# por item já preenchida com o que falta, observação, e o par
# encerrar-saldo + motivo.


def _flashes(cli):
    with cli.session_transaction() as s:
        return ' | '.join(m for _cat, m in s.get('_flashes', []))


def _cenario_de_rota(exige_atesto=True, qtd=50):
    """Devolve os ids (não os objetos): a rota roda em outro app_context."""
    with app.app_context():
        admin, obra, pedido, item, almox = _cenario_com_catalogo(
            qtd, exige_atesto=exige_atesto)
        return admin.id, obra.id, pedido.id, item.id


def _recebimentos_de(pedido_id):
    from models import RecebimentoPedido
    return RecebimentoPedido.query.filter_by(pedido_id=pedido_id).all()


def test_tela_de_recebimento_abre_para_quem_tem_papel():
    from helpers_tenant import cliente_de
    admin_id, _obra_id, pedido_id, item_id = _cenario_de_rota()

    resposta = cliente_de(admin_id).get(f'/compras/{pedido_id}/recebimento')

    assert resposta.status_code == 200
    corpo = resposta.get_data(as_text=True)
    assert 'Cimento CP-II' in corpo, 'a tela não lista os itens do pedido'
    assert f'qtd_{item_id}' in corpo, (
        'sem um campo de quantidade por item não dá para receber parcial')


def test_post_da_tela_grava_o_recebimento_e_redireciona():
    from helpers_tenant import cliente_de
    admin_id, _obra_id, pedido_id, item_id = _cenario_de_rota()
    cli = cliente_de(admin_id)

    resposta = cli.post(
        f'/compras/{pedido_id}/recebimento',
        data={f'qtd_{item_id}': '30', 'data_recebimento': '2026-08-05',
              'observacao': 'dois sacos rasgados'})

    # A tela reaberta mostra a entrega já registrada e pede só o que falta —
    # é o bloco que quem recebe a segunda parcela vê primeiro.
    corpo = cli.get(f'/compras/{pedido_id}/recebimento').get_data(as_text=True)
    assert 'dois sacos rasgados' in corpo, (
        'a tela não mostra as entregas já registradas')
    assert 'value="20"' in corpo, (
        'o campo não vem preenchido com o que FALTA — quem recebe o resto '
        'teria de calcular de cabeça')

    assert resposta.status_code == 302, 'POST tem que redirecionar'
    with app.app_context():
        recebimentos = _recebimentos_de(pedido_id)
        assert len(recebimentos) == 1
        assert float(recebimentos[0].itens[0].quantidade_recebida) == 30.0
        assert recebimentos[0].observacao == 'dois sacos rasgados'
        assert len(_entradas(pedido_id)) == 1, 'o atesto pela tela não lançou'
        from models import PedidoCompra
        assert db.session.get(
            PedidoCompra, pedido_id).situacao_recebimento == 'parcial'


def test_post_em_pedido_legado_recusa_dizendo_por_que():
    """O conserto do no-op silencioso.

    Pedido legado teve o estoque lançado na emissão. A tela nova não pode
    aceitar o clique e ficar quieta — nem lançar de novo. Recusa, e diz por
    quê e para onde ir.
    """
    from helpers_tenant import cliente_de
    admin_id, _obra_id, pedido_id, item_id = _cenario_de_rota(
        exige_atesto=False)
    cli = cliente_de(admin_id)

    resposta = cli.post(f'/compras/{pedido_id}/recebimento',
                        data={f'qtd_{item_id}': '30',
                              'data_recebimento': '2026-08-05'})

    assert resposta.status_code == 302
    aviso = _flashes(cli)
    assert 'emissão' in aviso or 'emissao' in aviso, (
        f'a recusa tem que explicar que o estoque deste pedido já entrou na '
        f'emissão. Veio: {aviso!r}')
    with app.app_context():
        assert _recebimentos_de(pedido_id) == [], (
            'a tela gravou recebimento num pedido do regime antigo')


def test_leitor_nao_abre_nem_posta_na_tela_de_recebimento():
    from helpers_tenant import cliente_de
    admin_id, obra_id, pedido_id, item_id = _cenario_de_rota()
    with app.app_context():
        leitor_id = _pessoa_com_papel(admin_id, obra_id, 'LEITOR').id

    cli = cliente_de(leitor_id)
    assert cli.get(f'/compras/{pedido_id}/recebimento').status_code == 403
    assert cli.post(f'/compras/{pedido_id}/recebimento',
                    data={f'qtd_{item_id}': '30',
                          'data_recebimento': '2026-08-05'}).status_code == 403
    with app.app_context():
        assert _recebimentos_de(pedido_id) == []


def test_recebimento_vazio_recusa_sem_gravar_documento():
    """Submeter tudo zerado é engano de dedo, não atesto de nada."""
    from helpers_tenant import cliente_de
    admin_id, _obra_id, pedido_id, item_id = _cenario_de_rota()
    cli = cliente_de(admin_id)

    cli.post(f'/compras/{pedido_id}/recebimento',
             data={f'qtd_{item_id}': '0', 'data_recebimento': '2026-08-05'})

    assert _flashes(cli), 'a recusa não disse nada ao usuário'
    with app.app_context():
        assert _recebimentos_de(pedido_id) == []


def test_detalhe_manda_o_pedido_novo_para_a_tela_e_o_legado_para_a_rota_antiga():
    """O botão tem que saber em que regime o pedido nasceu.

    Um botão só, apontando sempre para a rota antiga, é o defeito atual: em
    pedido do regime novo ele lançaria estoque que já vai entrar pelo atesto.
    """
    from helpers_tenant import cliente_de

    # Os dois pedidos no MESMO tenant: `_cenario_de_rota` abre um tenant novo
    # a cada chamada, e o detalhe é escopado por `admin_id`.
    with app.app_context():
        admin, obra, novo, _item, _almox = _cenario_com_catalogo(
            50, exige_atesto=True)
        forn = _fornecedor(admin.id)
        legado = _pedido(admin.id, obra.id, forn.id)
        legado.itens[0].almoxarifado_item_id = _item_de_catalogo(admin.id).id
        db.session.commit()
        admin_id, novo_id, legado_id = admin.id, novo.id, legado.id
    cli = cliente_de(admin_id)

    corpo_novo = cli.get(f'/compras/{novo_id}').get_data(as_text=True)
    assert f'/compras/{novo_id}/recebimento' in corpo_novo, (
        'o detalhe do pedido do regime novo não oferece a tela de recebimento')
    assert 'Não recebido' in corpo_novo, (
        'a situação de recebimento não aparece no detalhe')

    corpo_legado = cli.get(f'/compras/{legado_id}').get_data(as_text=True)
    assert f'/compras/receber/{legado_id}' in corpo_legado, (
        'o pedido legado perdeu a rota antiga, que é a única que ele tem')
    assert f'/compras/{legado_id}/recebimento' not in corpo_legado


def test_listagem_mostra_a_situacao_de_recebimento():
    from helpers_tenant import cliente_de
    admin_id, _obra_id, pedido_id, item_id = _cenario_de_rota()
    cli = cliente_de(admin_id)
    cli.post(f'/compras/{pedido_id}/recebimento',
             data={f'qtd_{item_id}': '30', 'data_recebimento': '2026-08-05'})

    corpo = cli.get('/compras/').get_data(as_text=True)

    assert 'Recebido parcialmente' in corpo, (
        'a listagem não mostra a situação de recebimento')


def test_rota_antiga_recusa_pedido_do_regime_novo():
    """A porta dos fundos da dupla escrita.

    O botão do detalhe já não aponta para cá em pedido do regime novo, mas
    quem tiver a URL ainda pode postar. Se a rota antiga aceitasse, lançaria a
    quantidade INTEIRA — a mesma que o atesto vai lançar quando o caminhão
    chegar.
    """
    from helpers_tenant import cliente_de
    admin_id, _obra_id, pedido_id, _item = _cenario_de_rota(exige_atesto=True)
    cli = cliente_de(admin_id)

    cli.post(f'/compras/receber/{pedido_id}')

    with app.app_context():
        assert _entradas(pedido_id) == [], (
            'a rota antiga lançou estoque de um pedido que exige atesto')
    assert 'atesto' in _flashes(cli).lower() or 'recebimento' in _flashes(cli).lower()


# ---------------------------------------------------------------------------
# R7 — consistência e o gancho da fase financeira
# ---------------------------------------------------------------------------
#
# `valor_atestado` é o número que o Fluxo A da fase financeira vai usar para
# pagar o que CHEGOU em vez do que foi pedido. Barato expor agora, caro
# descobrir depois que não dá para calcular.
#
# O sensor de drift é o par: `situacao_recebimento` é derivada, e derivada
# persistida sai de sincronia na primeira escrita que passa por fora do
# serviço. O script compara o persistido com `situacao_para` — a MESMA função
# que grava —, e é por isso que ela é pura e vive separada de quem grava.


def test_valor_atestado_soma_so_o_que_chegou():
    """30 dos 50 sacos a R$ 32,50 → R$ 975, não os R$ 1.625 do pedido.

    O saldo não entregue não entra: pagar por ele é exatamente o que a fase
    financeira vai evitar com este número.
    """
    from services.recebimento_pedido import valor_atestado
    with app.app_context():
        admin, _obr, pedido, item, _almox = _cenario_com_catalogo(50)
        assert valor_atestado(pedido) == Decimal('0'), (
            'pedido sem recebimento tem valor atestado zero')

        _receber(pedido, admin, item, 30)
        assert valor_atestado(pedido) == Decimal('975.00')

        _receber(pedido, admin, item, 20, data=date(2026, 8, 7))
        assert valor_atestado(pedido) == Decimal('1625.00'), (
            'com tudo entregue, o atestado tem que bater com o pedido')


def test_valor_atestado_conta_item_de_texto_livre():
    """Frete não está no catálogo e não movimenta estoque — mas foi entregue,
    e é para pagar."""
    from services.recebimento_pedido import valor_atestado
    with app.app_context():
        admin = _admin()
        obra = _obra(admin.id)
        forn = _fornecedor(admin.id)
        pedido = _pedido(admin.id, obra.id, forn.id,
                         itens=(('Frete do caminhão', 2, 350.00),))
        pedido.exige_atesto = True
        db.session.commit()
        item = PedidoCompraItem.query.filter_by(pedido_id=pedido.id).first()

        _receber(pedido, admin, item, 1)

        assert valor_atestado(pedido) == Decimal('350.00'), (
            'item fora do catálogo ficou de fora do valor atestado')


def test_sensor_acha_drift_quando_alguem_escreve_a_situacao_na_marra():
    """A escrita por fora do serviço é o que o sensor existe para pegar."""
    from scripts.verificar_consistencia_recebimento import verificar
    with app.app_context():
        admin, _obr, pedido, item, _almox = _cenario_com_catalogo(50)
        _receber(pedido, admin, item, 30)

        rel = verificar(admin.id)
        assert rel['consistente'] is True, (
            f'o serviço deixou drift no próprio caminho feliz: {rel}')

        # O UPDATE na marra que o sensor tem de denunciar.
        pedido.situacao_recebimento = 'recebido'
        db.session.commit()

        rel = verificar(admin.id)
        assert rel['consistente'] is False
        assert len(rel['divergencias']) == 1
        divergencia = rel['divergencias'][0]
        assert divergencia['pedido_id'] == pedido.id
        assert divergencia['persistido'] == 'recebido'
        assert divergencia['derivado'] == 'parcial'


def test_sensor_ignora_pedido_do_regime_antigo():
    """Pedido legado não tem situação de recebimento para conferir.

    Ele nasce `nao_recebido` por default da coluna e nunca é atualizado —
    varrer esses seria produzir drift de mentira em todo tenant que ainda não
    virou, e um sensor que grita sempre não é lido nunca.
    """
    from scripts.verificar_consistencia_recebimento import verificar
    with app.app_context():
        admin, _obr, pedido, _item, _almox = _cenario_com_catalogo(
            50, exige_atesto=False)
        pedido.situacao_recebimento = 'recebido'
        db.session.commit()

        rel = verificar(admin.id)
        assert rel['consistente'] is True, (
            'o sensor apontou drift em pedido do regime antigo')
        assert rel['pedidos_verificados'] == 0


def test_sensor_devolve_exit_1_no_drift_e_2_no_erro_de_uso():
    """Os códigos de saída são o contrato com quem chama de cron."""
    from scripts.verificar_consistencia_recebimento import main
    with app.app_context():
        admin, _obr, pedido, item, _almox = _cenario_com_catalogo(50)
        _receber(pedido, admin, item, 30)
        admin_id = admin.id

    assert main([str(admin_id), '--json']) == 0
    with app.app_context():
        db.session.get(PedidoCompra, pedido.id).situacao_recebimento = 'recebido'
        db.session.commit()
    assert main([str(admin_id)]) == 1
    assert main(['999999999']) == 2


# ---------------------------------------------------------------------------
# C1 — o que o conferente digita é o que fica gravado
# ---------------------------------------------------------------------------
#
# Revisão de 12/08, achados 2, 3 e 4. Três sintomas de uma função só:
# `_quantidade_do_form` transformava erro de digitação em silêncio. Texto
# ilegível virava `Decimal('0')`, a rota filtrava zero como "item que não veio"
# e o recebimento era gravado sem aquele item — com flash verde. Quem digitou
# ia embora achando que tinha atestado.
#
# O ponto de milhar brasileiro ("1.500") era lido como decimal e dividia a
# quantidade por mil, silenciosamente, até o `valor_atestado` da fase
# financeira. E `Decimal('nan')` passava o filtro para estourar
# `InvalidOperation` dentro do serviço, virando 500 sem rollback.


def _cenario_dois_itens(qtd_a=50, qtd_b=20):
    """Pedido de DOIS itens de catálogo — é preciso mais de um para provar que
    o item ilegível some enquanto o outro é gravado."""
    admin = _admin()
    obra = _obra(admin.id)
    forn = _fornecedor(admin.id)
    pedido = _pedido(admin.id, obra.id, forn.id,
                     itens=(('Cimento CP-II', qtd_a, 32.50),
                            ('Areia média', qtd_b, 90.00)))
    pedido.exige_atesto = True
    itens = PedidoCompraItem.query.filter_by(pedido_id=pedido.id).order_by(
        PedidoCompraItem.id).all()
    for item in itens:
        item.almoxarifado_item_id = _item_de_catalogo(admin.id,
                                                      item.descricao).id
    db.session.commit()
    return admin.id, pedido.id, itens[0].id, itens[1].id


@pytest.mark.parametrize('digitado', ['3O', '30 sacos', '30.5.0', 'trinta'])
def test_quantidade_ilegivel_recusa_em_vez_de_sumir(digitado):
    """O item ilegível não pode desaparecer da entrega em silêncio.

    Este é o defeito com a pior forma de todos: some sem erro, e o flash é
    verde. Quem recebeu no portão acredita que atestou o cimento.
    """
    from helpers_tenant import cliente_de
    with app.app_context():
        admin_id, pedido_id, item_a, item_b = _cenario_dois_itens()
    cli = cliente_de(admin_id)

    resposta = cli.post(f'/compras/{pedido_id}/recebimento',
                        data={f'qtd_{item_a}': digitado, f'qtd_{item_b}': '10',
                              'data_recebimento': '2026-08-05'})

    assert resposta.status_code == 302
    aviso = _flashes(cli)
    assert 'Cimento CP-II' in aviso, (
        f'a recusa tem que nomear o item que não deu para ler. Veio: {aviso!r}')
    with app.app_context():
        assert _recebimentos_de(pedido_id) == [], (
            f'{digitado!r} virou zero e o recebimento foi gravado sem o '
            f'cimento — com o outro item dentro, e sem aviso nenhum')


def test_ponto_de_milhar_ambiguo_recusa_em_vez_de_dividir_por_mil():
    """"1.500" tanto vale mil e quinhentos quanto um e meio — e errar custa 1000×.

    O `.replace(',', '.')` original convertia o separador decimal brasileiro e
    deixava o ponto de milhar intacto, que o `Decimal` então lia como decimal:
    o saldo do pedido ficava fantasma e o `valor_atestado` saía mil vezes
    menor, sem nenhum erro na tela.

    Adivinhar de novo, para o outro lado, seria o mesmo defeito com o sinal
    trocado. Entre duas leituras que diferem por mil, a resposta certa é
    perguntar — e a mensagem tem que mostrar as duas.
    """
    from helpers_tenant import cliente_de
    with app.app_context():
        admin_id, pedido_id, item_a, _item_b = _cenario_dois_itens(qtd_a=2000)
    cli = cliente_de(admin_id)

    cli.post(f'/compras/{pedido_id}/recebimento',
             data={f'qtd_{item_a}': '1.500', 'data_recebimento': '2026-08-05'})

    aviso = _flashes(cli)
    assert '1500' in aviso and '1,5' in aviso, (
        f'a recusa tem que mostrar as duas leituras possíveis. Veio: {aviso!r}')
    with app.app_context():
        assert _recebimentos_de(pedido_id) == [], (
            '"1.500" foi gravado sem perguntar qual das duas leituras era')


@pytest.mark.parametrize('digitado,esperado', [
    ('30,5', 30.5),        # o teclado brasileiro — o caminho comum
    ('30.5', 30.5),        # o que `type="number"` entrega
    ('30', 30.0),
    ('1.500,25', 1500.25),  # com a vírgula presente, o ponto é milhar sem dúvida
    ('1.500.000', 1500000.0),
    ('30.25', 30.25),      # dois decimais não formam grupo de milhar
])
def test_formatos_que_ja_funcionavam_continuam_valendo(digitado, esperado):
    """A vírgula do teclado brasileiro é o caminho comum — não pode regredir.

    O pedido é grande de propósito: o que está sob teste é a leitura do
    número, e um teto de quantidade estourando aqui esconderia isso.
    """
    from helpers_tenant import cliente_de
    with app.app_context():
        admin_id, pedido_id, item_a, _item_b = _cenario_dois_itens(
            qtd_a=2_000_000)
    cli = cliente_de(admin_id)

    cli.post(f'/compras/{pedido_id}/recebimento',
             data={f'qtd_{item_a}': digitado, 'data_recebimento': '2026-08-05'})

    with app.app_context():
        recebimentos = _recebimentos_de(pedido_id)
        assert len(recebimentos) == 1, f'não gravou {digitado!r}: {_flashes(cli)!r}'
        assert float(recebimentos[0].itens[0].quantidade_recebida) == esperado


@pytest.mark.parametrize('digitado', ['nan', 'NaN', 'infinity', '-inf', '1e999'])
def test_quantidade_nao_finita_recusa_sem_estourar(digitado):
    """`Decimal('nan')` não levanta no construtor — e passava o filtro do zero.

    Chegava em `_validar_linhas`, onde `qtd <= 0` levanta `InvalidOperation`,
    que a rota não captura: 500 com a sessão sem rollback, em vez da mensagem
    de regra.
    """
    from helpers_tenant import cliente_de
    with app.app_context():
        admin_id, pedido_id, item_a, _item_b = _cenario_dois_itens()
    cli = cliente_de(admin_id)

    resposta = cli.post(f'/compras/{pedido_id}/recebimento',
                        data={f'qtd_{item_a}': digitado,
                              'data_recebimento': '2026-08-05'})

    assert resposta.status_code == 302, (
        f'{digitado!r} devolveu {resposta.status_code} em vez de recusar com '
        f'mensagem de regra')
    assert _flashes(cli), 'recusou calado'
    with app.app_context():
        assert _recebimentos_de(pedido_id) == []


def test_campo_vazio_continua_sendo_item_que_nao_veio():
    """Vazio é ausência, não erro: o item simplesmente não veio nesta entrega."""
    from helpers_tenant import cliente_de
    with app.app_context():
        admin_id, pedido_id, item_a, item_b = _cenario_dois_itens()
    cli = cliente_de(admin_id)

    cli.post(f'/compras/{pedido_id}/recebimento',
             data={f'qtd_{item_a}': '30', f'qtd_{item_b}': '',
                   'data_recebimento': '2026-08-05'})

    with app.app_context():
        recebimentos = _recebimentos_de(pedido_id)
        assert len(recebimentos) == 1, f'não gravou: {_flashes(cli)!r}'
        assert recebimentos[0].itens.count() == 1, (
            'o campo vazio virou uma linha de recebimento')
        assert recebimentos[0].itens[0].pedido_item_id == item_a


def test_servico_recusa_quantidade_nao_finita_por_conta_propria():
    """O serviço é o chokepoint: não pode depender de a rota ter limpado o dado.

    Quem chamar `registrar_recebimento` de um CLI, de um job ou de um teste
    passa por esta validação e não por `_quantidade_do_form`.
    """
    from services.recebimento_pedido import (RecebimentoInvalido,
                                             registrar_recebimento)
    with app.app_context():
        admin, _obr, pedido, item, _almox = _cenario_com_catalogo(50)
        with pytest.raises(RecebimentoInvalido):
            registrar_recebimento(pedido, admin, [(item.id, Decimal('NaN'))],
                                  date(2026, 8, 5))
        with pytest.raises(RecebimentoInvalido):
            registrar_recebimento(pedido, admin, [(item.id, Decimal('Infinity'))],
                                  date(2026, 8, 5))
        assert _recebimentos_de(pedido.id) == []


def test_campo_de_quantidade_e_numerico_na_tela():
    """`type="number"` é o que tira a ambiguidade do ponto na origem.

    O navegador entrega valor canônico e o teclado do celular continua
    numérico. Com `type="text"` o servidor tinha de adivinhar o que "1.500"
    queria dizer — e adivinhava errado.
    """
    from helpers_tenant import cliente_de
    with app.app_context():
        admin_id, pedido_id, item_a, _item_b = _cenario_dois_itens()

    corpo = cliente_de(admin_id).get(
        f'/compras/{pedido_id}/recebimento').get_data(as_text=True)

    import re
    campo = re.search(rf'<input[^>]*name="qtd_{item_a}"[^>]*>', corpo)
    if campo is None:
        campo = re.search(rf'<input[^>]*id="qtd_{item_a}"[^>]*>', corpo)
    assert campo, 'campo de quantidade não encontrado na tela'
    assert 'type="number"' in campo.group(0), (
        f'o campo ainda é texto livre: {campo.group(0)!r}')


def test_quantidade_absurda_recusa_em_vez_de_estourar_no_banco():
    """`1e999` é finito, passa o parser — e não cabe em `Numeric(12,3)`.

    Com a sobre-entrega marcada não há teto de pedido para barrar antes, e o
    valor chega ao banco como DataError: 500 em vez de mensagem de regra. O
    limite da coluna é uma regra como outra qualquer, e quem a conhece é o
    serviço.
    """
    from helpers_tenant import cliente_de
    with app.app_context():
        admin_id, pedido_id, item_a, _item_b = _cenario_dois_itens()
    cli = cliente_de(admin_id)

    resposta = cli.post(f'/compras/{pedido_id}/recebimento',
                        data={f'qtd_{item_a}': '1e999',
                              'permitir_sobre_entrega': 'on',
                              'observacao': 'veio muito mais',
                              'data_recebimento': '2026-08-05'})

    assert resposta.status_code == 302, (
        f'quantidade absurda devolveu {resposta.status_code} em vez de recusar')
    assert _flashes(cli), 'recusou calado'
    with app.app_context():
        assert _recebimentos_de(pedido_id) == []


# ---------------------------------------------------------------------------
# C5 — ninguém fica sem caminho: pedido sem obra, e botão que não engana
# ---------------------------------------------------------------------------
#
# Revisão de 12/08, achados 6 e 15. Dois lados da mesma pergunta: quem pode
# receber?
#
# Pedido SEM obra é caso legítimo — `compras_views.nova_post` aceita `obra_id`
# vazio de propósito, e material de escritório é a razão. Mas
# `papel_de_usuario_na_obra(u, None)` faz `db.session.get(Obra, None)`, que
# devolve None, e o papel sai None: 403 para todo mundo, inclusive para o
# ADMIN dono do tenant. Com o regime novo esse pedido também não recebe
# estoque na emissão — ou seja, o material não entrava em lugar nenhum, e a
# única explicação que o usuário via era um 403 cru.
#
# Do outro lado, o botão do detalhe só olhava `pedido.exige_atesto`: aparecia
# verde para quem a rota ia recusar.


def _pedido_sem_obra():
    """Pedido de material de escritório: sem obra, no regime novo."""
    admin = _admin()
    forn = _fornecedor(admin.id)
    pedido = _pedido(admin.id, None, forn.id,
                     itens=(('Papel A4', 10, 25.00),))
    almox = _item_de_catalogo(admin.id, 'Papel A4')
    pedido.exige_atesto = True
    item = PedidoCompraItem.query.filter_by(pedido_id=pedido.id).first()
    item.almoxarifado_item_id = almox.id
    db.session.commit()
    return admin, pedido, item


def test_admin_atesta_pedido_sem_obra():
    """Sem obra não há eixo de obra para aplicar — quem decide é o tenant."""
    with app.app_context():
        admin, pedido, item = _pedido_sem_obra()

        rec = _receber(pedido, admin, item, 10)

        assert rec is not None
        db.session.refresh(pedido)
        assert pedido.situacao_recebimento == 'recebido'
        assert len(_entradas(pedido.id)) == 1, (
            'o material do pedido sem obra não entrou em lugar nenhum: não na '
            'emissão (regime novo) e não no atesto (403)')


def test_funcionario_sem_vinculo_nao_atesta_pedido_sem_obra_com_escopo_ligado():
    """Com o eixo de obra em vigor, não há vínculo que autorize um pedido sem obra.

    A permissividade de "sem obra" não pode ser maior que a de "com obra":
    seria uma porta lateral para quem o escopo existe para estreitar.
    """
    from scripts.flag_escopo_obra import definir_flag as _escopo
    from services.recebimento_pedido import (RecebimentoInvalido,
                                             registrar_recebimento)
    with app.app_context():
        admin, pedido, item = _pedido_sem_obra()
        _escopo(admin.id, True)
        suf = uuid.uuid4().hex[:8]
        funcionario = Usuario(
            username=f'sf_{suf}', email=f'sf_{suf}@test.local', nome=f'F {suf}',
            password_hash=generate_password_hash('Senha@2026'),
            tipo_usuario=TipoUsuario.FUNCIONARIO, ativo=True,
            versao_sistema='v2', admin_id=admin.id)
        db.session.add(funcionario)
        db.session.commit()

        with pytest.raises(RecebimentoInvalido):
            registrar_recebimento(pedido, funcionario, [(item.id, Decimal('10'))],
                                  date(2026, 8, 5))


def test_botao_de_recebimento_nao_aparece_para_quem_a_rota_recusaria():
    """Botão verde que dá 403 é pior que botão ausente.

    Os outros botões de compras já consultam a permissão antes de renderizar;
    este só olhava o regime do pedido.
    """
    from helpers_tenant import cliente_de
    admin_id, obra_id, pedido_id, _item_id = _cenario_de_rota()
    with app.app_context():
        leitor_id = _pessoa_com_papel(admin_id, obra_id, 'LEITOR').id

    corpo = cliente_de(leitor_id).get(
        f'/compras/{pedido_id}').get_data(as_text=True)

    # A âncora é o link, não a frase: "Registrar Recebimento" também aparece
    # num parágrafo explicativo da mesma tela.
    assert f'/compras/{pedido_id}/recebimento' not in corpo, (
        'o detalhe ofereceu ao LEITOR um botão que a rota responde com 403')


def test_quem_tem_papel_continua_vendo_o_botao():
    """O contrapeso do teste acima: esconder de todo mundo também é defeito."""
    from helpers_tenant import cliente_de
    admin_id, obra_id, pedido_id, _item_id = _cenario_de_rota()
    with app.app_context():
        gestor_id = _pessoa_com_papel(admin_id, obra_id, 'GESTOR').id

    corpo = cliente_de(gestor_id).get(
        f'/compras/{pedido_id}').get_data(as_text=True)

    assert f'/compras/{pedido_id}/recebimento' in corpo


# ---------------------------------------------------------------------------
# C2 — a SAÍDA de consumo volta, no momento certo
# ---------------------------------------------------------------------------
#
# Revisão de 12/08, achados 1 e 11. O achado mais grave da revisão, e o mais
# silencioso: o guard de emissão devolve `[]`, e os dois chamadores derivam a
# SAÍDA pareada de `movs_entrada` — que passou a vir vazia. O regime novo só
# gerava ENTRADA.
#
# Efeito num tenant com a flag ligada: material comprado para a obra, que
# antes era reconhecido como consumido no ato (lote CONSUMIDO, disponível 0),
# passa a ficar DISPONIVEL para sempre. O almoxarifado exibe saldo de material
# que fisicamente já foi para a obra, e alguém pode dar saída do mesmo cimento
# uma segunda vez — consumo em dobro.
#
# O gate original não pegou porque o teste da emissão afirmava `entradas == []`
# e nunca olhou a saída. O teste de paridade abaixo é o que faltava: com e sem
# a flag, o conjunto final de movimentos tem de ser o mesmo. Só o instante muda.

def _saidas(pedido_id):
    from models import AlmoxarifadoMovimento
    return (AlmoxarifadoMovimento.query
            .filter_by(pedido_compra_id=pedido_id, tipo_movimento='SAIDA')
            .all())


def _retrato_dos_movimentos(pedido_id):
    """O que existe no almoxarifado por causa deste pedido, sem o instante.

    É o retrato que tem de ser igual nos dois regimes: tipo, quantidade,
    status e disponível do lote. Data e observação ficam de fora de propósito
    — é exatamente o que a fase mudou.
    """
    from models import AlmoxarifadoEstoque, AlmoxarifadoMovimento
    retrato = []
    movimentos = (AlmoxarifadoMovimento.query
                  .filter_by(pedido_compra_id=pedido_id)
                  .order_by(AlmoxarifadoMovimento.tipo_movimento,
                            AlmoxarifadoMovimento.quantidade)
                  .all())
    for mov in movimentos:
        lote = AlmoxarifadoEstoque.query.filter_by(
            entrada_movimento_id=mov.id).first()
        retrato.append((
            mov.tipo_movimento,
            float(mov.quantidade),
            lote.status if lote else None,
            float(lote.quantidade_disponivel) if lote else None,
        ))
    return sorted(retrato, key=lambda t: (t[0], t[1]))


def test_atesto_com_obra_gera_a_saida_de_consumo_pareada():
    """O material chegou na obra: entra e é consumido, como na emissão era.

    Sem a saída, o lote fica DISPONIVEL para sempre e o mesmo cimento pode
    sair uma segunda vez pela tela do almoxarifado.
    """
    from models import AlmoxarifadoEstoque
    with app.app_context():
        admin, _obr, pedido, item, _almox = _cenario_com_catalogo(50)

        _receber(pedido, admin, item, 30)

        entradas = _entradas(pedido.id)
        saidas = _saidas(pedido.id)
        assert len(entradas) == 1 and float(entradas[0].quantidade) == 30.0
        assert len(saidas) == 1, (
            'o atesto lançou a ENTRADA e não lançou a SAÍDA de consumo que a '
            'emissão lançava — o lote fica disponível para sempre')
        assert float(saidas[0].quantidade) == 30.0
        lote = AlmoxarifadoEstoque.query.filter_by(
            entrada_movimento_id=entradas[0].id).first()
        assert lote.status == 'CONSUMIDO'
        assert float(lote.quantidade_disponivel) == 0.0


def test_atesto_sem_obra_deixa_o_material_em_estoque():
    """Sem obra não há consumo a reconhecer — o material fica na prateleira.

    É o comportamento do regime antigo (`processar_compra_normal` só gera
    saída quando há obra), e é o caso que prova que a correção não saiu
    lançando saída para tudo.
    """
    from models import AlmoxarifadoEstoque
    with app.app_context():
        admin, pedido, item = _pedido_sem_obra()

        _receber(pedido, admin, item, 10)

        assert len(_entradas(pedido.id)) == 1
        assert _saidas(pedido.id) == [], (
            'o atesto consumiu material de um pedido sem obra — não há centro '
            'de custo para consumir contra')
        lote = AlmoxarifadoEstoque.query.filter_by(
            entrada_movimento_id=_entradas(pedido.id)[0].id).first()
        assert lote.status == 'DISPONIVEL'


def test_atesto_de_faturamento_direto_gera_a_saida_do_cliente():
    """`aprovacao_cliente`: o material é do cliente, e sai como faturamento direto."""
    with app.app_context():
        admin, _obr, pedido, item, _almox = _cenario_com_catalogo(50)
        pedido.tipo_compra = 'aprovacao_cliente'
        pedido.status_aprovacao_cliente = 'APROVADO'
        db.session.commit()

        _receber(pedido, admin, item, 50)

        saidas = _saidas(pedido.id)
        assert len(saidas) == 1, 'a saída de faturamento direto sumiu'
        assert 'faturamento' in (saidas[0].observacao or '').lower(), (
            f'a saída não diz que é faturamento direto: '
            f'{saidas[0].observacao!r}')


def test_a_saida_do_atesto_carrega_pedido_obra_e_tenant():
    """`pedido_compra_id` é o que a dedup do EventManager usa; os outros dois
    são o isolamento multi-tenant e o centro de custo."""
    with app.app_context():
        admin, obra, pedido, item, _almox = _cenario_com_catalogo(50)

        _receber(pedido, admin, item, 30)

        saida = _saidas(pedido.id)[0]
        assert saida.pedido_compra_id == pedido.id
        assert saida.obra_id == obra.id
        assert saida.admin_id == admin.id


def test_paridade_de_movimentos_entre_os_dois_regimes():
    """O teste que faltava ao gate original.

    Mesmo pedido, mesma obra, mesmos itens. Num tenant a emissão lança; no
    outro o atesto lança. Ao fim do ciclo, o que existe no almoxarifado tem
    de ser o MESMO — só o instante muda. É esta a promessa da fase inteira, e
    ela não estava sob teste: o teste da emissão afirmava `entradas == []` e
    parava aí.
    """
    with app.app_context():
        legado_admin, _o1, legado, _i1, _a1 = _cenario_com_catalogo(
            50, exige_atesto=False)
        from compras_views import processar_compra_normal
        processar_compra_normal(legado, _itens_validos(legado),
                                legado_admin.id, legado_admin.id)
        db.session.commit()
        retrato_legado = _retrato_dos_movimentos(legado.id)

        novo_admin, _o2, novo, item, _a2 = _cenario_com_catalogo(50)
        processar_compra_normal(novo, _itens_validos(novo),
                                novo_admin.id, novo_admin.id)
        db.session.commit()
        _receber(novo, novo_admin, item, 50)
        retrato_novo = _retrato_dos_movimentos(novo.id)

    assert retrato_novo == retrato_legado, (
        f'os dois regimes divergem no que deixam no almoxarifado.\n'
        f'  legado: {retrato_legado}\n'
        f'  novo:   {retrato_novo}')


def test_movimentos_do_atesto_usam_a_data_do_recebimento():
    """O caminhão chegou sábado e foi lançado na segunda — o fato é sábado.

    É o cenário que o docstring de `RecebimentoPedido.data_recebimento` diz
    que a coluna existe para cobrir. Sem propagar, `data_movimento` cai no
    default `utcnow` e o relatório de entradas por período do almoxarifado
    conta o material no mês errado.
    """
    from models import AlmoxarifadoMovimento
    with app.app_context():
        admin, _obr, pedido, item, _almox = _cenario_com_catalogo(50)

        _receber(pedido, admin, item, 30, data=date(2026, 7, 31))

        movimentos = AlmoxarifadoMovimento.query.filter_by(
            pedido_compra_id=pedido.id).all()
        assert movimentos, 'nenhum movimento gerado'
        for mov in movimentos:
            assert mov.data_movimento.date() == date(2026, 7, 31), (
                f'{mov.tipo_movimento} ficou com a data do registro '
                f'({mov.data_movimento}) em vez da data da entrega')


def test_linha_do_recebimento_guarda_a_saida_que_gerou():
    """Sem guardar o id da saída, o estorno da exclusão não sabe o que desfazer.

    É a mesma razão de `almoxarifado_movimento_id` existir para a entrada: o
    estorno não pode adivinhar qual movimento era dele.
    """
    from models import RecebimentoPedidoItem
    with app.app_context():
        admin, _obr, pedido, item, _almox = _cenario_com_catalogo(50)

        rec = _receber(pedido, admin, item, 30)

        linha = RecebimentoPedidoItem.query.filter_by(
            recebimento_id=rec.id).first()
        assert linha.almoxarifado_saida_movimento_id is not None
        assert (linha.almoxarifado_saida_movimento_id
                == _saidas(pedido.id)[0].id)



# ---------------------------------------------------------------------------
# C3 — a exclusão chega ao usuário, e a do pedido para de mentir
# ---------------------------------------------------------------------------
#
# Revisão de 12/08, achados 7 e 12.
#
# `excluir_recebimento` existe desde a R5, é testado, e o docstring dele diz —
# corretamente — que errar a quantidade é o erro mais comum de quem recebe
# caminhão no portão. Só que nenhuma rota e nenhum botão o chamavam: o caminho
# de correção não chegava a quem precisa dele. Quem digitasse 500 em vez de 50
# só conseguia consertar por acesso direto ao banco.
#
# Do outro lado, `compras.excluir` apagava o pedido sem olhar a situação de
# recebimento. O cascade levava a trilha de atesto junto (quem recebeu, quando,
# com que observação), enquanto ENTRADA, SAÍDA e lote sobreviviam com
# `pedido_compra_id` NULL — estoque sem documento que explique de onde veio, e
# todos os guards de `excluir_recebimento` contornados por aquela porta.


def test_excluir_recebimento_desfaz_o_par_inteiro():
    """A saída pareada da C2 vai junto: desfazer meia coisa é pior que não desfazer."""
    with app.app_context():
        admin, _obr, pedido, item, _almox = _cenario_com_catalogo(50)
        rec = _receber(pedido, admin, item, 30)
        assert len(_saidas(pedido.id)) == 1, 'sanidade'

        _excluir(rec, admin)

        assert _entradas(pedido.id) == []
        assert _saidas(pedido.id) == [], (
            'a ENTRADA foi estornada e a SAÍDA ficou — apontando para um lote '
            'que deixou de existir')


def test_rota_de_exclusao_apaga_o_ultimo_recebimento():
    from helpers_tenant import cliente_de
    admin_id, _obra_id, pedido_id, item_id = _cenario_de_rota()
    cli = cliente_de(admin_id)
    cli.post(f'/compras/{pedido_id}/recebimento',
             data={f'qtd_{item_id}': '30', 'data_recebimento': '2026-08-05'})
    with app.app_context():
        rec_id = _recebimentos_de(pedido_id)[0].id

    resposta = cli.post(
        f'/compras/{pedido_id}/recebimento/{rec_id}/excluir')

    assert resposta.status_code == 302
    with app.app_context():
        assert _recebimentos_de(pedido_id) == []
        assert _entradas(pedido_id) == []
        from models import PedidoCompra
        assert db.session.get(
            PedidoCompra, pedido_id).situacao_recebimento == 'nao_recebido'


def test_leitor_nao_exclui_recebimento_pela_rota():
    from helpers_tenant import cliente_de
    admin_id, obra_id, pedido_id, item_id = _cenario_de_rota()
    cli = cliente_de(admin_id)
    cli.post(f'/compras/{pedido_id}/recebimento',
             data={f'qtd_{item_id}': '30', 'data_recebimento': '2026-08-05'})
    with app.app_context():
        rec_id = _recebimentos_de(pedido_id)[0].id
        leitor_id = _pessoa_com_papel(admin_id, obra_id, 'LEITOR').id

    resposta = cliente_de(leitor_id).post(
        f'/compras/{pedido_id}/recebimento/{rec_id}/excluir')

    assert resposta.status_code == 403
    with app.app_context():
        assert len(_recebimentos_de(pedido_id)) == 1


def test_rota_de_exclusao_repassa_a_recusa_do_servico():
    """A regra vive no serviço; a rota mostra a mensagem dele, sem reescrever."""
    from helpers_tenant import cliente_de
    admin_id, _obra_id, pedido_id, item_id = _cenario_de_rota()
    cli = cliente_de(admin_id)
    cli.post(f'/compras/{pedido_id}/recebimento',
             data={f'qtd_{item_id}': '20', 'data_recebimento': '2026-08-05'})
    cli.post(f'/compras/{pedido_id}/recebimento',
             data={f'qtd_{item_id}': '10', 'data_recebimento': '2026-08-06'})
    with app.app_context():
        primeiro = _recebimentos_de(pedido_id)[0]
        primeiro_id, rotulo = primeiro.id, primeiro.rotulo

    cli.post(f'/compras/{pedido_id}/recebimento/{primeiro_id}/excluir')

    aviso = _flashes(cli)
    assert 'último' in aviso, (
        f'a recusa do serviço não chegou ao usuário. Veio: {aviso!r}')
    with app.app_context():
        assert len(_recebimentos_de(pedido_id)) == 2, (
            f'{rotulo} foi apagado do meio da sequência')


def test_a_tela_de_recebimento_abre_com_o_pedido_ja_recebido():
    """Senão o caminho de correção fica inalcançável.

    O botão do detalhe some quando a situação é `recebido`, e a tela é o único
    lugar onde a exclusão existe: quem errou a quantidade e fechou o pedido
    ficaria sem por onde voltar.
    """
    from helpers_tenant import cliente_de
    admin_id, _obra_id, pedido_id, item_id = _cenario_de_rota()
    cli = cliente_de(admin_id)
    cli.post(f'/compras/{pedido_id}/recebimento',
             data={f'qtd_{item_id}': '50', 'data_recebimento': '2026-08-05'})

    resposta = cli.get(f'/compras/{pedido_id}/recebimento')

    assert resposta.status_code == 200
    corpo = resposta.get_data(as_text=True)
    assert 'excluir' in corpo.lower(), (
        'a tela do pedido já recebido não oferece o desfazer')


def test_detalhe_leva_aos_recebimentos_mesmo_com_o_pedido_fechado():
    from helpers_tenant import cliente_de
    admin_id, _obra_id, pedido_id, item_id = _cenario_de_rota()
    cli = cliente_de(admin_id)
    cli.post(f'/compras/{pedido_id}/recebimento',
             data={f'qtd_{item_id}': '50', 'data_recebimento': '2026-08-05'})

    corpo = cli.get(f'/compras/{pedido_id}').get_data(as_text=True)

    assert f'/compras/{pedido_id}/recebimento' in corpo, (
        'com o pedido fechado, o detalhe não leva mais à tela de recebimentos '
        '— e é lá que mora o desfazer')


def test_excluir_pedido_com_recebimento_recusa():
    """O cascade levaria a trilha de atesto e deixaria o estoque órfão.

    `almoxarifado_movimento.pedido_compra_id` é ON DELETE SET NULL: os
    movimentos sobrevivem sem nada que explique de onde vieram, enquanto
    `recebimento_pedido` some por CASCADE. Todos os guards de
    `excluir_recebimento` ficariam contornados por esta porta.
    """
    from helpers_tenant import cliente_de
    admin_id, _obra_id, pedido_id, item_id = _cenario_de_rota()
    cli = cliente_de(admin_id)
    cli.post(f'/compras/{pedido_id}/recebimento',
             data={f'qtd_{item_id}': '30', 'data_recebimento': '2026-08-05'})

    cli.post(f'/compras/excluir/{pedido_id}')

    aviso = _flashes(cli)
    assert 'recebimento' in aviso.lower(), (
        f'a recusa não explicou que existe recebimento gravado. Veio: {aviso!r}')
    with app.app_context():
        from models import PedidoCompra
        assert db.session.get(PedidoCompra, pedido_id) is not None, (
            'o pedido foi excluído com recebimento gravado')
        assert len(_recebimentos_de(pedido_id)) == 1
        assert len(_entradas(pedido_id)) == 1


def test_excluir_pedido_sem_recebimento_continua_funcionando():
    """O contrapeso: o guard não pode transformar exclusão em impossível."""
    from helpers_tenant import cliente_de
    admin_id, _obra_id, pedido_id, _item_id = _cenario_de_rota()

    cliente_de(admin_id).post(f'/compras/excluir/{pedido_id}')

    with app.app_context():
        from models import PedidoCompra
        assert db.session.get(PedidoCompra, pedido_id) is None


# ---------------------------------------------------------------------------
# C4 — não se atesta o que o cliente ainda não aprovou
# ---------------------------------------------------------------------------
#
# Revisão de 12/08, achado 5.
#
# No regime antigo, o estoque de `tipo_compra='aprovacao_cliente'` só existia
# depois do aceite no portal: era `processar_compra_aprovada_cliente` quem
# criava a ENTRADA, e ela só roda na aprovação. Com `exige_atesto=True` essa
# ordem se perdeu — qualquer papel de obra abria a tela, atestava, e o
# almoxarifado ganhava lote de uma compra que o cliente ainda podia recusar.
# E se recusasse (`status_aprovacao_cliente='RECUSADO'`), nada revertia.
#
# O spec já dizia, na tabela de casos de borda: "Pedido cancelado/excluído →
# recusa recebimento". A regra existia no papel e não no código.


def _cenario_aprovacao_cliente(status='AGUARDANDO_APROVACAO_CLIENTE'):
    admin, obra, pedido, item, almox = _cenario_com_catalogo(50)
    pedido.tipo_compra = 'aprovacao_cliente'
    pedido.status_aprovacao_cliente = status
    db.session.commit()
    return admin, obra, pedido, item


@pytest.mark.parametrize('status', ['AGUARDANDO_APROVACAO_CLIENTE',
                                    'PENDENTE', 'RECUSADO'])
def test_servico_recusa_atesto_sem_aprovacao_do_cliente(status):
    """A regra vive no serviço: bloquear só na rota deixa CLI e job passando."""
    from services.recebimento_pedido import RecebimentoInvalido
    with app.app_context():
        admin, _obra, pedido, item = _cenario_aprovacao_cliente(status)

        with pytest.raises(RecebimentoInvalido) as e:
            _receber(pedido, admin, item, 30)

        assert 'cliente' in str(e.value).lower(), (
            f'a recusa não explica que falta o aceite do cliente: {e.value}')
        assert _entradas(pedido.id) == []
        assert _saidas(pedido.id) == []


def test_atesto_passa_depois_do_aceite_do_cliente():
    """O contrapeso: aprovado, o fluxo é o de sempre."""
    with app.app_context():
        admin, _obra, pedido, item = _cenario_aprovacao_cliente('APROVADO')

        _receber(pedido, admin, item, 30)

        db.session.refresh(pedido)
        assert pedido.situacao_recebimento == 'parcial'
        assert len(_entradas(pedido.id)) == 1


def test_tela_recusa_pedido_esperando_o_cliente_dizendo_por_que():
    from helpers_tenant import cliente_de
    with app.app_context():
        admin, _obra, pedido, item = _cenario_aprovacao_cliente()
        admin_id, pedido_id, item_id = admin.id, pedido.id, item.id
    cli = cliente_de(admin_id)

    resposta = cli.post(f'/compras/{pedido_id}/recebimento',
                        data={f'qtd_{item_id}': '30',
                              'data_recebimento': '2026-08-05'})

    assert resposta.status_code == 302
    assert 'cliente' in _flashes(cli).lower()
    with app.app_context():
        assert _recebimentos_de(pedido_id) == []


def test_pedido_normal_nao_e_afetado_pela_checagem_de_aprovacao():
    """`status_aprovacao_cliente` fica NULL em pedido normal, e isso não pode
    virar recusa — seria bloquear o caminho comum por causa da borda."""
    with app.app_context():
        admin, _obr, pedido, item, _almox = _cenario_com_catalogo(50)
        assert pedido.tipo_compra == 'normal', 'sanidade'

        _receber(pedido, admin, item, 30)

        db.session.refresh(pedido)
        assert pedido.situacao_recebimento == 'parcial'


# ---------------------------------------------------------------------------
# C6 — "o resto não vem" sem inventar quantidade
# ---------------------------------------------------------------------------
#
# Revisão de 12/08, achado 8.
#
# Encerrar o saldo exigia informar ao menos um item recebido. Quem tinha
# recebido 30 de 50 e ouvia do fornecedor que os 20 não vinham só tinha duas
# saídas: zerar os campos e ser recusado ("recebimento vazio não é atesto de
# nada"), deixando o pedido `parcial` para sempre; ou aceitar o valor
# pré-preenchido e registrar 20 sacos que nunca chegaram, gerando ENTRADA
# fantasma no almoxarifado e marcando o pedido como `recebido`.
#
# Encerramento com motivo É um atesto — do que NÃO vai chegar. E a ordem das
# perguntas de `situacao_para` muda junto: um pedido cancelado antes da
# primeira entrega estava caindo em `nao_recebido`, que descreve um pedido
# ainda esperando o caminhão.


def test_encerrar_saldo_sem_item_recebido():
    """Marcar "o resto não vem" com os campos zerados grava, e não lança estoque."""
    from services.recebimento_pedido import registrar_recebimento
    with app.app_context():
        admin, _obr, pedido, item, _almox = _cenario_com_catalogo(50)
        _receber(pedido, admin, item, 30)

        rec = registrar_recebimento(
            pedido, admin, [], date(2026, 8, 9), encerra_saldo=True,
            motivo='fornecedor não entrega o resto')

        assert rec is not None
        db.session.refresh(pedido)
        assert pedido.situacao_recebimento == 'encerrado_com_saldo'
        assert len(_entradas(pedido.id)) == 1, (
            'o encerramento sem item lançou estoque de material que não chegou')


def test_recebimento_vazio_sem_encerramento_continua_recusado():
    """O contrapeso: submeter tudo zerado por engano continua sendo engano."""
    from services.recebimento_pedido import (RecebimentoInvalido,
                                             registrar_recebimento)
    with app.app_context():
        admin, _obr, pedido, _item, _almox = _cenario_com_catalogo(50)

        with pytest.raises(RecebimentoInvalido):
            registrar_recebimento(pedido, admin, [], date(2026, 8, 9))


def test_pedido_cancelado_antes_da_primeira_entrega_fica_encerrado():
    """Nada chegou e o fornecedor cancelou: `encerrado_com_saldo`, não `nao_recebido`.

    `nao_recebido` descreve pedido que ainda espera o caminhão. Dizer isso de
    um pedido que já foi encerrado é a situação persistida mentindo sobre um
    fato registrado — e é o que a ordem antiga das perguntas fazia, porque
    "nada recebido" vinha antes de "alguém encerrou".
    """
    from services.recebimento_pedido import registrar_recebimento
    with app.app_context():
        admin, _obr, pedido, _item, _almox = _cenario_com_catalogo(50)

        registrar_recebimento(pedido, admin, [], date(2026, 8, 9),
                              encerra_saldo=True,
                              motivo='fornecedor cancelou a entrega')

        db.session.refresh(pedido)
        assert pedido.situacao_recebimento == 'encerrado_com_saldo'


def test_encerramento_completo_continua_sendo_recebido():
    """Recebeu tudo E marcou encerrar: `recebido` vence — não há saldo a encerrar.

    A ordem entre "completo" e "encerrado" não muda nesta rodada, e este teste
    é quem trava isso.
    """
    with app.app_context():
        admin, _obr, pedido, item, _almox = _cenario_com_catalogo(50)

        _receber(pedido, admin, item, 50, encerra_saldo=True,
                 motivo='veio tudo de uma vez')

        db.session.refresh(pedido)
        assert pedido.situacao_recebimento == 'recebido'


def test_valor_atestado_de_pedido_encerrado_sem_entrega_e_zero():
    """A fase financeira não pode pagar nada por um pedido que não chegou."""
    from services.recebimento_pedido import registrar_recebimento, valor_atestado
    with app.app_context():
        admin, _obr, pedido, _item, _almox = _cenario_com_catalogo(50)

        registrar_recebimento(pedido, admin, [], date(2026, 8, 9),
                              encerra_saldo=True, motivo='cancelado')

        assert valor_atestado(pedido) == Decimal('0')


def test_tela_encerra_saldo_com_os_campos_zerados():
    """O caminho que o usuário percorre de verdade: marca a caixa, zera tudo."""
    from helpers_tenant import cliente_de
    admin_id, _obra_id, pedido_id, item_id = _cenario_de_rota()
    cli = cliente_de(admin_id)
    cli.post(f'/compras/{pedido_id}/recebimento',
             data={f'qtd_{item_id}': '30', 'data_recebimento': '2026-08-05'})

    cli.post(f'/compras/{pedido_id}/recebimento',
             data={f'qtd_{item_id}': '', 'data_recebimento': '2026-08-09',
                   'encerra_saldo': 'on',
                   'motivo_encerramento': 'fornecedor não entrega o resto'})

    with app.app_context():
        from models import PedidoCompra
        assert db.session.get(
            PedidoCompra, pedido_id).situacao_recebimento == \
            'encerrado_com_saldo', f'flashes: {_flashes(cli)!r}'
        assert len(_entradas(pedido_id)) == 1
