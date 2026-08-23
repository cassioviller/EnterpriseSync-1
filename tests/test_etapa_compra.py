"""A régua de status unificado — Fase 4 do ciclo de compras.

Spec: docs/superpowers/specs/2026-08-19-status-unificado-design.md
Plano: docs/superpowers/plans/2026-08-23-plano-execucao-status-unificado.md

Molde de tests/test_nota_e_liberacao.py: fixtures locais, tenant por uuid4,
sem depender de seed.
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
from models import (Cliente, EstadoRequisicao, Fornecedor, Obra, PedidoCompra,
                    RequisicaoCompra, TipoUsuario, Usuario)
from services.etapa_compra import CHAVES, etapa_do_pedido

pytestmark = pytest.mark.integration


@pytest.fixture(autouse=True)
def _config():
    app.config['TESTING'] = True
    app.config['WTF_CSRF_ENABLED'] = False
    if not app.secret_key:
        app.secret_key = 'test-etapa-compra'
    yield


def _cenario(estado_requisicao=None, exige_atesto=True, fluxo='faturado'):
    """Admin + obra + fornecedor + pedido. Requisição só se o estado for dado."""
    suf = uuid.uuid4().hex[:8]
    with app.app_context():
        adm = Usuario(
            username=f'ec_{suf}', email=f'ec_{suf}@test.local', nome=f'Adm {suf}',
            password_hash=generate_password_hash('Senha@2026'),
            tipo_usuario=TipoUsuario.ADMIN, ativo=True, versao_sistema='v2')
        db.session.add(adm)
        db.session.commit()

        cliente = Cliente(nome=f'Cli {suf}', admin_id=adm.id)
        db.session.add(cliente)
        db.session.commit()
        obra = Obra(nome=f'Obra {suf}', codigo=f'O{suf[:6].upper()}',
                    data_inicio=date(2026, 1, 1), admin_id=adm.id,
                    cliente_id=cliente.id)
        forn = Fornecedor(nome=f'Forn {suf}', cnpj=suf, admin_id=adm.id)
        db.session.add_all([obra, forn])
        db.session.commit()

        requisicao = None
        if estado_requisicao is not None:
            requisicao = RequisicaoCompra(
                admin_id=adm.id, obra_id=obra.id, estado=estado_requisicao,
                numero=f'REQ-{suf.upper()}', solicitante_id=adm.id)
            db.session.add(requisicao)
            db.session.commit()

        pedido = PedidoCompra(
            admin_id=adm.id, obra_id=obra.id, fornecedor_id=forn.id,
            numero=f'PC-{suf.upper()}', valor_total=Decimal('1000.00'),
            data_compra=date(2026, 1, 10), exige_atesto=exige_atesto,
            fluxo_pagamento=fluxo,
            requisicao_id=requisicao.id if requisicao else None)
        db.session.add(pedido)
        db.session.commit()
        return adm.id, pedido.id


def _casas(pedido_id):
    with app.app_context():
        pedido = db.session.get(PedidoCompra, pedido_id)
        regua = etapa_do_pedido(pedido)
        return regua, {c.chave: c for c in regua['casas']}


def test_regua_tem_as_nove_casas_na_ordem():
    _, pedido_id = _cenario(estado_requisicao=EstadoRequisicao.RASCUNHO)
    regua, _ = _casas(pedido_id)
    assert [c.chave for c in regua['casas']] == list(CHAVES)


def test_requisicao_em_rascunho_acende_so_a_casa_1():
    _, pedido_id = _cenario(estado_requisicao=EstadoRequisicao.RASCUNHO)
    _, casas = _casas(pedido_id)
    assert casas['requisitada'].acesa is True
    assert casas['aprovada'].acesa is False


def test_requisicao_aprovada_acende_1_e_2():
    _, pedido_id = _cenario(estado_requisicao=EstadoRequisicao.APROVADA)
    _, casas = _casas(pedido_id)
    assert casas['requisitada'].acesa is True
    assert casas['aprovada'].acesa is True


def test_pedido_existente_acende_a_casa_3():
    _, pedido_id = _cenario(estado_requisicao=EstadoRequisicao.CONVERTIDA)
    _, casas = _casas(pedido_id)
    assert casas['pedido_emitido'].acesa is True


def test_compra_direta_sem_requisicao_deixa_1_e_2_apagadas_nao_ausentes():
    """Sem requisição as duas primeiras casas não se aplicam — mas continuam
    na régua, apagadas. Casa ausente quebraria a comparação entre compras."""
    _, pedido_id = _cenario(estado_requisicao=None)
    regua, casas = _casas(pedido_id)
    assert [c.chave for c in regua['casas']] == list(CHAVES)
    assert casas['requisitada'].aplicavel is False
    assert casas['aprovada'].aplicavel is False
    assert casas['pedido_emitido'].acesa is True


def test_ponteiro_e_a_primeira_casa_aplicavel_nao_satisfeita():
    _, pedido_id = _cenario(estado_requisicao=EstadoRequisicao.RASCUNHO)
    regua, _ = _casas(pedido_id)
    assert regua['ponteiro'] == 'aprovada'


def test_recebimento_parcial_acende_material_recebido():
    _, pedido_id = _cenario(estado_requisicao=EstadoRequisicao.CONVERTIDA)
    with app.app_context():
        pedido = db.session.get(PedidoCompra, pedido_id)
        pedido.situacao_recebimento = 'parcial'
        db.session.commit()
    _, casas = _casas(pedido_id)
    assert casas['material_recebido'].acesa is True


def test_encerrado_com_saldo_acende_com_selo_nas_casas_4_e_9():
    """Encerrar com saldo satisfaz a casa — mas a régua não pode esconder que
    encerramos com falta."""
    _, pedido_id = _cenario(estado_requisicao=EstadoRequisicao.CONVERTIDA)
    with app.app_context():
        pedido = db.session.get(PedidoCompra, pedido_id)
        pedido.situacao_recebimento = 'encerrado_com_saldo'
        db.session.commit()
    _, casas = _casas(pedido_id)
    assert casas['material_recebido'].acesa is True
    assert 'com saldo' in casas['material_recebido'].selos
    assert 'com saldo' in casas['encerrada'].selos


def test_nao_recebido_deixa_a_casa_4_apagada():
    _, pedido_id = _cenario(estado_requisicao=EstadoRequisicao.CONVERTIDA)
    _, casas = _casas(pedido_id)
    assert casas['material_recebido'].acesa is False


def test_pedido_legado_sem_atesto_nao_tem_triade_de_material_e_nota():
    """📖 templates/compras/index.html:126 — em pedido legado inventar 'Não
    recebido' seria mentir sobre estoque que entrou na emissão."""
    _, pedido_id = _cenario(estado_requisicao=EstadoRequisicao.CONVERTIDA,
                            exige_atesto=False)
    _, casas = _casas(pedido_id)
    assert casas['material_recebido'].aplicavel is False
    assert casas['nota_lancada'].aplicavel is False


def test_nota_lancada_acende_a_casa_5():
    from models import NotaFiscalPedido
    admin_id, pedido_id = _cenario(estado_requisicao=EstadoRequisicao.CONVERTIDA)
    with app.app_context():
        pedido = db.session.get(PedidoCompra, pedido_id)
        db.session.add(NotaFiscalPedido(
            admin_id=admin_id, pedido_id=pedido_id, numero='123',
            fornecedor_id=pedido.fornecedor_id, lancada_por_id=admin_id,
            valor_total=Decimal('1000.00'), data_emissao=date(2026, 1, 11)))
        db.session.commit()
    _, casas = _casas(pedido_id)
    assert casas['nota_lancada'].acesa is True


def _conta(admin_id, pedido_id, **kw):
    from models import ContaPagar
    with app.app_context():
        c = ContaPagar(
            admin_id=admin_id, pedido_compra_id=pedido_id,
            descricao='Conta do pedido', valor_original=Decimal('1000.00'),
            data_emissao=date(2026, 1, 10), data_vencimento=date(2026, 2, 10),
            status=kw.pop('status', 'PENDENTE'),
            situacao_liberacao=kw.pop('situacao_liberacao', 'bloqueada'), **kw)
        db.session.add(c)
        db.session.commit()
        return c.id


def test_conta_liberada_acende_a_casa_6():
    admin_id, pedido_id = _cenario(estado_requisicao=EstadoRequisicao.CONVERTIDA)
    _conta(admin_id, pedido_id, situacao_liberacao='liberada')
    _, casas = _casas(pedido_id)
    assert casas['liberada'].acesa is True


def test_liberacao_com_ressalva_carrega_selo_na_casa_6():
    """📖 ContaPagar.liberacao_justificativa (services/financeiro_compra.py:450).
    Esconder a ressalva é esconder que alguém assumiu um risco."""
    admin_id, pedido_id = _cenario(estado_requisicao=EstadoRequisicao.CONVERTIDA)
    _conta(admin_id, pedido_id, situacao_liberacao='liberada',
           liberacao_justificativa='nota chega semana que vem')
    _, casas = _casas(pedido_id)
    assert 'com ressalva' in casas['liberada'].selos


def test_conta_em_lote_acende_a_casa_7():
    from models import FechamentoPagamento
    admin_id, pedido_id = _cenario(estado_requisicao=EstadoRequisicao.CONVERTIDA)
    conta_id = _conta(admin_id, pedido_id, situacao_liberacao='liberada')
    with app.app_context():
        lote = FechamentoPagamento(admin_id=admin_id, status='FECHADO',
                                   descricao='Lote 1',
                                   data_fechamento=date(2026, 2, 1))
        db.session.add(lote)
        db.session.commit()
        from models import ContaPagar
        conta = db.session.get(ContaPagar, conta_id)
        conta.fechamento_id = lote.id
        db.session.commit()
    _, casas = _casas(pedido_id)
    assert casas['em_lote'].acesa is True


def test_lote_fechado_por_quem_montou_carrega_selo_na_casa_7():
    from models import ContaPagar, FechamentoPagamento
    admin_id, pedido_id = _cenario(estado_requisicao=EstadoRequisicao.CONVERTIDA)
    conta_id = _conta(admin_id, pedido_id, situacao_liberacao='liberada')
    with app.app_context():
        lote = FechamentoPagamento(
            admin_id=admin_id, status='FECHADO', descricao='Lote 2',
            data_fechamento=date(2026, 2, 1),
            segregacao_justificativa='sou o único do financeiro hoje')
        db.session.add(lote)
        db.session.commit()
        conta = db.session.get(ContaPagar, conta_id)
        conta.fechamento_id = lote.id
        db.session.commit()
    _, casas = _casas(pedido_id)
    assert 'fechado por quem montou' in casas['em_lote'].selos


def test_conta_paga_acende_a_casa_8():
    admin_id, pedido_id = _cenario(estado_requisicao=EstadoRequisicao.CONVERTIDA)
    _conta(admin_id, pedido_id, situacao_liberacao='liberada', status='PAGO')
    _, casas = _casas(pedido_id)
    assert casas['paga'].acesa is True


def test_fluxo_b_paga_antes_de_receber_sem_a_regua_mentir():
    """O caso que derrubou a barra de progresso: no adiantamento o dinheiro sai
    antes do material. A casa 8 acende, a 4 não, e o ponteiro continua honesto."""
    from models import AdiantamentoFornecedor
    admin_id, pedido_id = _cenario(estado_requisicao=EstadoRequisicao.CONVERTIDA,
                                   fluxo='adiantamento')
    with app.app_context():
        from datetime import datetime
        db.session.add(AdiantamentoFornecedor(
            admin_id=admin_id, pedido_id=pedido_id, valor=Decimal('500.00'),
            baixado_em=datetime(2026, 1, 12, 10, 0)))
        db.session.commit()
    regua, casas = _casas(pedido_id)
    assert casas['paga'].acesa is True
    assert 'adiantamento' in casas['paga'].selos
    assert casas['material_recebido'].acesa is False
    assert regua['ponteiro'] == 'material_recebido'


def test_pedido_legado_encerra_so_com_o_pagamento():
    """Sem tríade não há recebimento a fechar — exigi-lo prenderia o pedido
    legado para sempre numa casa que nunca acende."""
    admin_id, pedido_id = _cenario(estado_requisicao=EstadoRequisicao.CONVERTIDA,
                                   exige_atesto=False)
    _conta(admin_id, pedido_id, situacao_liberacao='liberada', status='PAGO')
    regua, casas = _casas(pedido_id)
    assert casas['encerrada'].acesa is True
    assert regua['ponteiro'] is None


def test_encerrada_exige_pago_e_recebimento_fechado():
    admin_id, pedido_id = _cenario(estado_requisicao=EstadoRequisicao.CONVERTIDA)
    _conta(admin_id, pedido_id, situacao_liberacao='liberada', status='PAGO')
    with app.app_context():
        pedido = db.session.get(PedidoCompra, pedido_id)
        pedido.situacao_recebimento = 'recebido'
        db.session.commit()
    regua, casas = _casas(pedido_id)
    assert casas['encerrada'].acesa is True
    assert regua['ponteiro'] is None


def test_requisicao_cancelada_encerra_a_regua_e_diz_onde_parou():
    _, pedido_id = _cenario(estado_requisicao=EstadoRequisicao.CANCELADA)
    regua, _ = _casas(pedido_id)
    assert regua['encerrada_por'] == 'cancelada'
    assert regua['parou_em'] == 'aprovada'
    assert regua['ponteiro'] is None


def test_rejeitada_NAO_e_saida_lateral_e_sim_selo_na_casa_1():
    """📖 models.py:80-99 — REJEITADA não é terminal: dela se volta para
    RASCUNHO. 'Rejeitar não é matar.' Tratá-la como fim repetiria o erro que a
    Fase 3 já corrigiu."""
    _, pedido_id = _cenario(estado_requisicao=EstadoRequisicao.REJEITADA)
    regua, casas = _casas(pedido_id)
    assert regua['encerrada_por'] is None
    assert casas['requisitada'].acesa is True
    assert 'rejeitada' in casas['requisitada'].selos
    assert regua['ponteiro'] == 'aprovada'


def _login(client, admin_id):
    with client.session_transaction() as sess:
        sess['_user_id'] = str(admin_id)
        sess['_fresh'] = True


def test_a_regua_aparece_no_DOM_do_detalhe_do_pedido():
    """O critério que a spec fixou: função pura que ninguém chama passa em todo
    teste — foi assim que fechar_lote() ficou semanas testado e inalcançável."""
    admin_id, pedido_id = _cenario(estado_requisicao=EstadoRequisicao.CONVERTIDA)
    with app.test_client() as client:
        _login(client, admin_id)
        resp = client.get(f'/compras/{pedido_id}')
        html = resp.get_data(as_text=True)
    assert resp.status_code == 200
    assert 'id="regua-status"' in html
    for chave in CHAVES:
        assert f'data-casa="{chave}"' in html
    assert 'data-ponteiro="material_recebido"' in html


def _segundo_pedido(admin_id, primeiro_pedido_id, estado_requisicao):
    """Um segundo pedido DISTINTO, no mesmo tenant do primeiro — reaproveita
    obra e fornecedor para isolar o que a contagem de consultas precisa medir:
    se o número de pedidos, e não o número de tenants, é o que importa."""
    suf = uuid.uuid4().hex[:8]
    with app.app_context():
        primeiro = db.session.get(PedidoCompra, primeiro_pedido_id)
        obra_id, fornecedor_id = primeiro.obra_id, primeiro.fornecedor_id
        requisicao = RequisicaoCompra(
            admin_id=admin_id, obra_id=obra_id, estado=estado_requisicao,
            numero=f'REQ-{suf.upper()}', solicitante_id=admin_id)
        db.session.add(requisicao)
        db.session.commit()
        pedido = PedidoCompra(
            admin_id=admin_id, obra_id=obra_id, fornecedor_id=fornecedor_id,
            numero=f'PC-{suf.upper()}', valor_total=Decimal('2000.00'),
            data_compra=date(2026, 1, 11), exige_atesto=True,
            fluxo_pagamento='faturado', requisicao_id=requisicao.id)
        db.session.add(pedido)
        db.session.commit()
        return pedido.id


def _conta_em_lote(admin_id, pedido_id):
    """Uma ContaPagar do pedido, já em lote — sem isto o teste de contagem
    de consultas não exercita `ContaPagar.fechamento` (lazy) e passaria
    mesmo que o `joinedload` em `ponteiros_de` fosse removido: `dados['contas']`
    ficaria vazio e o lazy-load nunca seria disparado."""
    from models import ContaPagar, FechamentoPagamento
    with app.app_context():
        lote = FechamentoPagamento(
            admin_id=admin_id, status='FECHADO', descricao='Lote de teste',
            data_fechamento=date(2026, 2, 1))
        db.session.add(lote)
        db.session.commit()
        c = ContaPagar(
            admin_id=admin_id, pedido_compra_id=pedido_id,
            descricao='Conta do pedido', valor_original=Decimal('1000.00'),
            data_emissao=date(2026, 1, 10), data_vencimento=date(2026, 2, 10),
            status='PENDENTE', situacao_liberacao='liberada',
            fechamento_id=lote.id)
        db.session.add(c)
        db.session.commit()


def test_listagem_nao_consulta_por_linha():
    """O sensor do vício de 21/08: o número de consultas não pode crescer com o
    número de pedidos na página. Dois pedidos DISTINTOS — não o mesmo objeto
    repetido, que o identity map do SQLAlchemy esconderia como se o
    pré-carregamento em lote estivesse funcionando quando não está. Cada um
    carrega uma ContaPagar já em lote, para que o lazy-load de
    `ContaPagar.fechamento` também seja exercitado, não só o de
    `pedido.requisicao`."""
    from sqlalchemy import event
    from services.etapa_compra import ponteiros_de

    admin_id, primeiro = _cenario(estado_requisicao=EstadoRequisicao.CONVERTIDA)
    segundo = _segundo_pedido(admin_id, primeiro, EstadoRequisicao.CONVERTIDA)
    _conta_em_lote(admin_id, primeiro)
    _conta_em_lote(admin_id, segundo)
    with app.app_context():
        um = [db.session.get(PedidoCompra, primeiro)]
        dois = [db.session.get(PedidoCompra, primeiro),
                db.session.get(PedidoCompra, segundo)]
        contadas = []
        motor = db.engine

        def _registrar(conn, cursor, statement, *args):
            contadas.append(statement)

        event.listen(motor, 'before_cursor_execute', _registrar)
        try:
            ponteiros_de(um)
            com_um = len(contadas)
            contadas.clear()
            ponteiros_de(dois)
            com_dois = len(contadas)
        finally:
            event.remove(motor, 'before_cursor_execute', _registrar)

    assert com_dois == com_um, (
        'consultas cresceram com o número de pedidos: %d contra %d'
        % (com_dois, com_um))


def test_listagem_mostra_o_ponteiro_de_cada_pedido():
    """A comparação entre compras é o motivo de haver régua — e ela mora na
    listagem, não no detalhe."""
    admin_id, pedido_id = _cenario(estado_requisicao=EstadoRequisicao.CONVERTIDA)
    with app.test_client() as client:
        _login(client, admin_id)
        resp = client.get('/compras/')
        html = resp.get_data(as_text=True)
    assert resp.status_code == 200
    assert f'data-ponteiro-pedido="{pedido_id}"' in html
    assert 'Material recebido' in html


def test_a_regua_cancelada_ainda_expoe_data_ponteiro_no_DOM():
    """O contrato de DOM é universal: o runbook da Task 7 escolhe um pedido
    qualquer e procura `[data-ponteiro]` — um pedido cancelado que só
    carregasse `data-encerrada` quebraria essa varredura."""
    admin_id, pedido_id = _cenario(estado_requisicao=EstadoRequisicao.CANCELADA)
    with app.test_client() as client:
        _login(client, admin_id)
        resp = client.get(f'/compras/{pedido_id}')
        html = resp.get_data(as_text=True)
    assert resp.status_code == 200
    assert 'data-encerrada="cancelada"' in html
    assert 'data-ponteiro=""' in html
