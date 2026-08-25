"""Onda 1 — os cinco lugares em que o dinheiro entrava errado.

Cada teste entra pela porta do operador (rota HTTP ou serviço), não pelo
parser: o parser já tem `tests/test_decimal_br.py`. O que se prova aqui é que
a correção chegou ao caminho vivo.
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
from models import Cliente, Obra, TipoUsuario, Usuario

pytestmark = pytest.mark.integration


@pytest.fixture(autouse=True)
def _config():
    app.config['TESTING'] = True
    app.config['WTF_CSRF_ENABLED'] = False
    if not app.secret_key:
        app.secret_key = 'test-onda1-dinheiro'
    yield


@pytest.fixture(autouse=True, scope='module')
def _schema():
    """As 271-273 são idempotentes; rodá-las aqui é seguro.

    O boot da suíte roda com SIGE_BOOT_DDL=0 (conftest) — nem create_all nem
    migrações.
    """
    from migrations import (_migration_271_obra_contrato_versao,
                            _migration_272_aditivo_contrato,
                            _migration_273_medicao_contrato_versionada)
    with app.app_context():
        _migration_271_obra_contrato_versao()
        _migration_272_aditivo_contrato()
        _migration_273_medicao_contrato_versionada()
    yield


def _novo_admin(prefixo='onda1'):
    suf = uuid.uuid4().hex[:8]
    admin = Usuario(
        username=f'{prefixo}_{suf}', email=f'{prefixo}_{suf}@test.local',
        nome=f'Admin {prefixo} {suf}',
        password_hash=generate_password_hash('Senha@2026'),
        tipo_usuario=TipoUsuario.ADMIN, ativo=True, versao_sistema='v2',
    )
    db.session.add(admin)
    db.session.flush()
    return admin


def _nova_obra(admin, valor_contrato=0.0):
    suf = uuid.uuid4().hex[:8]
    cliente = Cliente(admin_id=admin.id, nome=f'Cliente {suf}',
                      email=f'cli_{suf}@test.local', telefone='11988887777')
    db.session.add(cliente)
    db.session.flush()
    obra = Obra(nome=f'Obra {suf}', codigo=f'OBR{suf}',
                data_inicio=date(2026, 1, 10), admin_id=admin.id,
                cliente_id=cliente.id, valor_contrato=valor_contrato)
    db.session.add(obra)
    db.session.flush()
    return obra


# ---------------------------------------------------------------------------
# Task 2 — o aditivo
# ---------------------------------------------------------------------------

def test_aditivo_nao_le_150000_ponto_00_como_quinze_milhoes():
    """🔴 `views/aditivos_views.py:102` fazia `.replace('.', '')` sem condição.

    Um teclado numérico produz ponto. `150000.00` virava `15000000`, e a
    aprovação gravava R$ 15.000.000,00 em `obra.valor_contrato` e lançava
    ~R$ 14,85M de receita no razão.
    """
    from services.contrato_obra import ORIGEM_CADASTRO, definir_valor_contrato
    with app.app_context():
        admin = _novo_admin('onda1_adit')
        obra = _nova_obra(admin, valor_contrato=0.0)
        definir_valor_contrato(obra, 100000.0, origem=ORIGEM_CADASTRO,
                               motivo='contrato original')
        db.session.commit()
        obra_id, admin_id = obra.id, admin.id

    cliente = app.test_client()
    with cliente.session_transaction() as sessao:
        sessao['_user_id'] = str(admin_id)
        sessao['_fresh'] = True

    resposta = cliente.post(
        f'/obras/{obra_id}/aditivos/novo',
        data={'tipo': 'acrescimo', 'motivo': 'acréscimo de escopo',
              'valor_novo': '150000.00'},
        follow_redirects=True)
    assert resposta.status_code in (200, 400)

    with app.app_context():
        from models import AditivoContrato
        aditivo = AditivoContrato.query.filter_by(obra_id=obra_id).first()
        assert aditivo is not None, 'o aditivo precisa ter sido aberto'
        assert Decimal(str(aditivo.valor_novo)) == Decimal('150000.00'), (
            f'150000.00 virou {aditivo.valor_novo} — o parser inflou o '
            f'contrato')


def test_aditivo_recusa_valor_ambiguo_em_vez_de_adivinhar():
    """`1.500` não é lido: é devolvido ao operador para desambiguar."""
    from services.contrato_obra import ORIGEM_CADASTRO, definir_valor_contrato
    with app.app_context():
        admin = _novo_admin('onda1_ambig')
        obra = _nova_obra(admin, valor_contrato=0.0)
        definir_valor_contrato(obra, 100000.0, origem=ORIGEM_CADASTRO,
                               motivo='contrato original')
        db.session.commit()
        obra_id, admin_id = obra.id, admin.id

    cliente = app.test_client()
    with cliente.session_transaction() as sessao:
        sessao['_user_id'] = str(admin_id)
        sessao['_fresh'] = True

    resposta = cliente.post(
        f'/obras/{obra_id}/aditivos/novo',
        data={'tipo': 'acrescimo', 'motivo': 'teste', 'valor_novo': '1.500'})
    assert resposta.status_code == 400
    assert 'ambíguo' in resposta.get_data(as_text=True)

    with app.app_context():
        from models import AditivoContrato
        assert AditivoContrato.query.filter_by(obra_id=obra_id).count() == 0, (
            'entrada ambígua não pode abrir aditivo nenhum')


# ---------------------------------------------------------------------------
# Task 3 — a emissão do pedido
# ---------------------------------------------------------------------------

def test_preco_real_ambiguo_nao_vira_um_milesimo():
    """🔴 `compras_views.py:2853`: `'1.500'` virava `1.5`.

    E como 1,5 é MENOR que o estimado, a guarda 3 (`valor_total > aprovado`)
    deixava passar em silêncio.

    Testado no nível do parser porque a emissão exige requisição aprovada,
    fornecedor e alçada — cenário que `tests/test_fase3_alcada.py` já monta.
    O que esta task muda é a leitura, e é ela que se prova aqui.
    """
    from utils.decimal_br import ValorAmbiguo, parse_decimal_br
    with pytest.raises(ValorAmbiguo):
        parse_decimal_br('1.500', campo='preço real')
    # e o que NÃO é ambíguo continua entrando
    assert parse_decimal_br('1500,00', campo='preço real') == Decimal('1500.00')
    assert parse_decimal_br('1500.00', campo='preço real') == Decimal('1500.00')


def _cliente_admin(admin_id):
    cliente = app.test_client()
    with cliente.session_transaction() as sessao:
        sessao['_user_id'] = str(admin_id)
        sessao['_fresh'] = True
    return cliente


def test_item_preco_ambiguo_na_requisicao_nova_e_recusado():
    """🔴 `compras_views.py:1891`: o `_num()` do laço de itens tinha o mesmo
    parser artesanal do achado #6 — e ele lê tanto PREÇO quanto QUANTIDADE.

    `1.500` no preço do item não pode virar `1.5` silenciosamente: a
    requisição não pode nem chegar a existir com um valor adivinhado.
    """
    from models import RequisicaoCompra
    with app.app_context():
        admin = _novo_admin('onda1_itpreco')
        obra = _nova_obra(admin)
        db.session.commit()
        admin_id, obra_id = admin.id, obra.id

    resposta = _cliente_admin(admin_id).post(
        '/compras/requisicoes/nova',
        data={'obra_id': str(obra_id), 'justificativa': 'teste',
              'item_descricao[]': ['Item'], 'item_unidade[]': ['un'],
              'item_quantidade[]': ['10'], 'item_preco[]': ['1.500'],
              'item_almoxarifado_id[]': ['']},
        follow_redirects=True)
    assert resposta.status_code == 200
    assert 'ambíguo' in resposta.get_data(as_text=True)

    with app.app_context():
        assert RequisicaoCompra.query.filter_by(admin_id=admin_id).count() == 0, (
            'entrada ambígua não pode abrir requisição nenhuma')


def test_item_quantidade_ambigua_na_requisicao_nova_e_recusada():
    """A mesma ambiguidade na QUANTIDADE é igualmente perigosa: `1.500`
    unidades lidas como `1.5` erra por 1000× do outro lado da conta."""
    from models import RequisicaoCompra
    with app.app_context():
        admin = _novo_admin('onda1_itqtd')
        obra = _nova_obra(admin)
        db.session.commit()
        admin_id, obra_id = admin.id, obra.id

    resposta = _cliente_admin(admin_id).post(
        '/compras/requisicoes/nova',
        data={'obra_id': str(obra_id), 'justificativa': 'teste',
              'item_descricao[]': ['Item'], 'item_unidade[]': ['un'],
              'item_quantidade[]': ['1.500'], 'item_preco[]': ['10,00'],
              'item_almoxarifado_id[]': ['']},
        follow_redirects=True)
    assert resposta.status_code == 200
    assert 'ambíguo' in resposta.get_data(as_text=True)

    with app.app_context():
        assert RequisicaoCompra.query.filter_by(admin_id=admin_id).count() == 0, (
            'entrada ambígua não pode abrir requisição nenhuma')


def test_item_nao_numerico_na_requisicao_nova_continua_virando_padrao():
    """Achado #5 (já corrigido antes desta task) não pode regressar: entrada
    não-numérica ('abc') não é ambígua — vale ZERO (não o `padrao`) e a
    linha entra assim mesmo, para o usuário ver e corrigir na tela, em vez
    de perder o formulário inteiro.

    Zero, e não `padrao`, de propósito: uma quantidade 1 "chutada" parece um
    pedido plausível e pode ser comprada sem que ninguém repare; zero é o
    valor que grita na tela.
    """
    from decimal import Decimal as _D

    from models import RequisicaoCompra, RequisicaoCompraItem
    with app.app_context():
        admin = _novo_admin('onda1_itabc')
        obra = _nova_obra(admin)
        db.session.commit()
        admin_id, obra_id = admin.id, obra.id

    resposta = _cliente_admin(admin_id).post(
        '/compras/requisicoes/nova',
        data={'obra_id': str(obra_id), 'justificativa': 'teste',
              'item_descricao[]': ['Item'], 'item_unidade[]': ['un'],
              'item_quantidade[]': ['abc'], 'item_preco[]': ['xyz'],
              'item_almoxarifado_id[]': ['']},
        follow_redirects=False)
    assert resposta.status_code == 302

    with app.app_context():
        req = RequisicaoCompra.query.filter_by(admin_id=admin_id).first()
        assert req is not None, (
            'entrada não-numérica não pode impedir a requisição de existir')
        item = RequisicaoCompraItem.query.filter_by(requisicao_id=req.id).one()
        assert _D(str(item.quantidade)) == _D('0'), (
            f'lixo em quantidade devia virar 0 (grita na tela), veio '
            f'{item.quantidade}')
        assert _D(str(item.preco_estimado)) == _D('0'), (
            f'lixo em preço devia virar 0, veio {item.preco_estimado}')


def test_num_distingue_campo_vazio_de_campo_com_lixo():
    """Os dois casos são diferentes de propósito, e nenhum teste os fixava
    antes desta correção.

    Campo VAZIO vira o `padrao` (quantidade 1, preço 0) — resolvido antes do
    parser, na linha do `or`. Campo com LIXO ('abc') cai no `except
    ValorInvalido` e vira ZERO nos dois campos — porque zero grita na tela e
    uma quantidade 1 parece um pedido plausível, que pode ser comprada.
    """
    from decimal import Decimal as _D

    from models import RequisicaoCompra, RequisicaoCompraItem
    with app.app_context():
        admin = _novo_admin('onda1_itvazio')
        obra = _nova_obra(admin)
        db.session.commit()
        admin_id, obra_id = admin.id, obra.id

    # Campo vazio: quantidade some do form, preço vem em branco.
    resposta = _cliente_admin(admin_id).post(
        '/compras/requisicoes/nova',
        data={'obra_id': str(obra_id), 'justificativa': 'teste',
              'item_descricao[]': ['Item vazio'], 'item_unidade[]': ['un'],
              'item_quantidade[]': [''], 'item_preco[]': [''],
              'item_almoxarifado_id[]': ['']},
        follow_redirects=False)
    assert resposta.status_code == 302

    with app.app_context():
        req = RequisicaoCompra.query.filter_by(admin_id=admin_id).first()
        assert req is not None
        item = RequisicaoCompraItem.query.filter_by(requisicao_id=req.id).one()
        assert _D(str(item.quantidade)) == _D('1'), (
            f'campo vazio de quantidade devia virar o padrão (1), veio '
            f'{item.quantidade}')
        assert _D(str(item.preco_estimado)) == _D('0'), (
            f'campo vazio de preço devia virar o padrão (0), veio '
            f'{item.preco_estimado}')

    # Campo com lixo: 'abc' não é vazio e não é ambíguo — vira zero, não o
    # padrão (senão uma quantidade 1 "chutada" passaria por pedido real).
    resposta = _cliente_admin(admin_id).post(
        '/compras/requisicoes/nova',
        data={'obra_id': str(obra_id), 'justificativa': 'teste',
              'item_descricao[]': ['Item lixo'], 'item_unidade[]': ['un'],
              'item_quantidade[]': ['abc'], 'item_preco[]': ['xyz'],
              'item_almoxarifado_id[]': ['']},
        follow_redirects=False)
    assert resposta.status_code == 302

    with app.app_context():
        req2 = (RequisicaoCompra.query.filter_by(admin_id=admin_id)
                .order_by(RequisicaoCompra.id.desc()).first())
        assert req2 is not None
        item2 = RequisicaoCompraItem.query.filter_by(requisicao_id=req2.id).one()
        assert _D(str(item2.quantidade)) == _D('0'), (
            f'lixo em quantidade devia virar 0, não o padrão (1); veio '
            f'{item2.quantidade}')
        assert _D(str(item2.preco_estimado)) == _D('0'), (
            f'lixo em preço devia virar 0, veio {item2.preco_estimado}')


@pytest.mark.parametrize('bruto,rotulo', [
    ('   ', 'so-espacos'),
    ('R$', 'so-simbolo'),
    ('\xa0', 'so-nbsp'),
    ('\u202f', 'so-narrow-nbsp'),
])
def test_quantidade_que_se_esvazia_na_limpeza_vale_zero(bruto, rotulo):
    """"Vazio malformado" é LIXO, não "vazio" — e lixo vale zero.

    Campo genuinamente vazio já virou `padrao` na linha do `or`, antes do
    parser. O que chega aqui é texto que `_limpar()` esvazia ('   ', 'R$',
    um NBSP sozinho) — e isso não pode satisfazer nenhum `default`: se
    satisfizesse, viraria `padrao` (quantidade 1), que parece um pedido
    plausível e pode ser comprada sem que ninguém repare. Regrediu quando
    `_num` passou `default=Decimal(str(padrao))` para `parse_decimal_br` —
    correção deste round.
    """
    from decimal import Decimal as _D

    from models import RequisicaoCompra, RequisicaoCompraItem
    with app.app_context():
        admin = _novo_admin(f'onda1_{rotulo}')
        obra = _nova_obra(admin)
        db.session.commit()
        admin_id, obra_id = admin.id, obra.id

    resposta = _cliente_admin(admin_id).post(
        '/compras/requisicoes/nova',
        data={'obra_id': str(obra_id), 'justificativa': 'teste',
              'item_descricao[]': ['Item'], 'item_unidade[]': ['un'],
              'item_quantidade[]': [bruto], 'item_preco[]': ['10,00'],
              'item_almoxarifado_id[]': ['']},
        follow_redirects=False)
    assert resposta.status_code == 302

    with app.app_context():
        req = RequisicaoCompra.query.filter_by(admin_id=admin_id).first()
        assert req is not None
        item = RequisicaoCompraItem.query.filter_by(requisicao_id=req.id).one()
        assert _D(str(item.quantidade)) == _D('0'), (
            f'{rotulo!r} ({bruto!r}) devia esvaziar na limpeza e virar 0, '
            f'não o padrão (1); veio {item.quantidade}')


# ---------------------------------------------------------------------------
# Task 4 — o teto da faixa de alçada
# ---------------------------------------------------------------------------

def test_teto_com_ponto_de_milhar_nao_vira_trinta_reais():
    """🔴 `services/faixa_alcada_admin.py:206`: `'30.000'` virava R$ 30,00.

    A escada seguia monotônica, `_violacoes` não levantava nada, e a primeira
    faixa do tenant passava a cobrir só compras abaixo de R$ 30.
    """
    from services.faixa_alcada_admin import _para_teto

    erros = []
    assert _para_teto('30.000', erros) is None
    assert erros, 'ambíguo precisa virar erro visível, não R$ 30,00'
    assert any('ambíguo' in e for e in erros), erros


def test_teto_continua_aceitando_os_dois_formatos_inequivocos():
    """O que a tela produz de fato continua entrando."""
    from services.faixa_alcada_admin import _para_teto

    for entrada in ('30000.00', '30.000,00', '30000'):
        erros = []
        assert _para_teto(entrada, erros) == Decimal('30000.00'), entrada
        assert erros == [], (entrada, erros)


def test_teto_vazio_continua_sendo_teto_aberto():
    """`valor_ate` NULL é o teto aberto — invariante da faixa. Não regrediu."""
    from services.faixa_alcada_admin import _para_teto

    for vazio in ('', '   ', None):
        erros = []
        assert _para_teto(vazio, erros) is None
        assert erros == []


def test_teto_zero_e_negativo_continuam_recusados():
    from services.faixa_alcada_admin import _para_teto

    for ruim in ('0', '-5'):
        erros = []
        assert _para_teto(ruim, erros) is None
        assert erros, ruim


@pytest.mark.parametrize('entrada', [Decimal('NaN'), float('nan')])
def test_para_teto_nunca_levanta_nem_com_nao_finito(entrada):
    """O contrato de `_para_teto` é acumular em `erros`, jamais levantar."""
    from services.faixa_alcada_admin import _para_teto
    erros = []
    assert _para_teto(entrada, erros) is None
    assert erros
