"""A tela do fechamento de pagamentos RENDERIZA — passo (e) do runbook da Fase 2.

Achado de 18/08, rodando o runbook pela tela pela primeira vez:
`/financeiro/fechamento-pagamentos` devolvia **500** para qualquer tenant com
uma conta pendente na janela do ciclo. A causa é precedência de filtro no
Jinja: em `'%.2f' % valor | replace('.', ',')` o filtro liga mais forte que o
`%`, então `replace` roda ANTES e devolve texto — e `'%.2f' % '1625.00'`
estoura `TypeError: must be real number, not str`.

Os dois lugares são de 22/07 e nunca tiveram teste: a suíte inteira não toca
esta tela (🔬 `grep fechamento-pagamentos tests/` = zero). É a tela onde o lote
é montado e onde a segregação de função é exercida (`fechado_por_id`), ou seja
o controle que o runbook existe para conferir.

Molde de tests/test_nota_e_liberacao.py: fixtures locais, tenant por uuid4.
"""
import os
import sys
import uuid
from datetime import date, timedelta
from decimal import Decimal

import pytest
from werkzeug.security import generate_password_hash

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import main  # noqa: F401 — registra os blueprints
from app import app, db
from models import (ContaPagar, FechamentoPagamento, TipoUsuario, Usuario)

pytestmark = pytest.mark.integration


@pytest.fixture(autouse=True)
def _config():
    app.config['TESTING'] = True
    app.config['WTF_CSRF_ENABLED'] = False
    if not app.secret_key:
        app.secret_key = 'test-fechamento-render'
    yield


def _admin():
    suf = uuid.uuid4().hex[:8]
    u = Usuario(
        username=f'fp_{suf}', email=f'fp_{suf}@test.local', nome=f'Adm {suf}',
        password_hash=generate_password_hash('Senha@2026'),
        tipo_usuario=TipoUsuario.ADMIN, ativo=True, versao_sistema='v2')
    db.session.add(u)
    db.session.commit()
    return u


def _conta(admin_id, valor=Decimal('1625.00')):
    """Conta PENDENTE vencendo hoje — cai na janela do ciclo em qualquer dia."""
    c = ContaPagar(
        descricao='Compra - Fornecedor de Teste',
        valor_original=valor,
        data_emissao=date.today() - timedelta(days=5),
        data_vencimento=date.today(),
        status='PENDENTE',
        admin_id=admin_id)
    db.session.add(c)
    db.session.commit()
    return c


def test_a_tela_do_fechamento_renderiza_com_conta_na_janela():
    """A linha 222: o valor da conta do ciclo.

    Sem conta a tela abre — o laço não roda. Basta UMA conta pendente para o
    500 aparecer, e é por isso que o gate verde nunca viu: nenhum teste chega
    a esta tela, com ou sem dado.
    """
    from helpers_tenant import cliente_de
    with app.app_context():
        adm = _admin()
        _conta(adm.id)
        adm_id = adm.id

    resposta = cliente_de(adm_id).get('/financeiro/fechamento-pagamentos')

    assert resposta.status_code == 200, 'a tela do lote estourou com uma conta na janela'
    corpo = resposta.get_data(as_text=True)
    assert 'Compra - Fornecedor de Teste' in corpo
    assert '1625,00' in corpo, 'o valor não saiu no formato brasileiro'


def test_o_historico_de_fechamentos_renderiza():
    """A linha 295: o total do lote já fechado, no card do histórico.

    Mesma raiz da anterior e caminho independente — um fechamento existente
    aparece mesmo quando não há nenhuma conta na janela.
    """
    from helpers_tenant import cliente_de
    with app.app_context():
        adm = _admin()
        db.session.add(FechamentoPagamento(
            data_fechamento=date.today(),
            descricao='Lote de teste',
            status='ABERTO',
            total_selecionado=Decimal('4900.00'),
            admin_id=adm.id))
        db.session.commit()
        adm_id = adm.id

    resposta = cliente_de(adm_id).get('/financeiro/fechamento-pagamentos')

    assert resposta.status_code == 200, 'o histórico de lotes estourou'
    corpo = resposta.get_data(as_text=True)
    assert 'Lote de teste' in corpo
    assert '4900,00' in corpo, 'o total do lote não saiu no formato brasileiro'
