"""A02/A03 — o recebimento de conta e o que ele deixa de registrar.

## Três defeitos que se sustentam mutuamente

1. **O gate contábil é MUDO** (B3.6). `financeiro_service.py` só cria a partida
   dobrada `if conta.conta_contabil_codigo:` — sem `else`. Toda CR sem conta
   contábil sai da contabilidade **em silêncio**, e não há como saber quantas
   são.
2. **Uma CR já liquidada aceita nova baixa** (B3.7). O caminho mais plausível não
   é distração: o import de extrato (`services/importacao_excel.py:2478`) **cria
   a conta já `RECEBIDO`**, e baixar essa conta à mão soma de novo.
3. **O recebimento não vira `FluxoCaixa`** (B3.8). O dinheiro entra na conta a
   receber e não aparece no fluxo de caixa.

**A ordem entre eles é a mitigação principal:** a guarda de re-baixa (2) tem de
existir ANTES de o `FluxoCaixa` passar a ser escrito (3). Sem ela, a escrita nova
transforma um defeito de status em **dinheiro contado duas vezes**.

## Por que este arquivo faz POST na rota, e não chama o serviço

Nenhum teste do repositório POSTa em `/financeiro/contas-receber/<id>/receber`
nem chama `baixar_recebimento` — grep confirmado. E o defeito da B3.8 é
exatamente de acoplamento: o formulário vivo é um **modal na listagem**
(`templates/financeiro/contas_receber.html`), não a página `receber_conta.html`,
que nenhum link do app alcança. Um teste que chamasse o serviço direto passaria
com o checkbox nunca chegando ao servidor.
"""
import os
import sys
from datetime import date
from decimal import Decimal

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import main  # noqa: F401 — registra os blueprints antes de qualquer request
from app import app, db
from models import ContaReceber, FluxoCaixa

from helpers_tenant import cliente_de, um_tenant

pytestmark = pytest.mark.integration

DIA = date(2026, 1, 15)


@pytest.fixture(autouse=True)
def _config():
    app.config['TESTING'] = True
    app.config['WTF_CSRF_ENABLED'] = False
    if not app.secret_key:
        app.secret_key = 'test-a02'
    yield


def _conta(t, *, valor=1000.00, status='PENDENTE', recebido=0.00,
           conta_contabil=None):
    """Uma `ContaReceber` do tenant, no estado pedido."""
    cr = ContaReceber(
        admin_id=t.admin_id, obra_id=t.obra_id,
        cliente_nome=f'Cliente {t.marca}',
        numero_documento=f'DOC-{t.marca}',
        descricao='Medição',
        valor_original=Decimal(str(valor)),
        valor_recebido=Decimal(str(recebido)),
        saldo=Decimal(str(valor)) - Decimal(str(recebido)),
        data_emissao=DIA, data_vencimento=DIA,
        status=status,
        conta_contabil_codigo=conta_contabil,
    )
    db.session.add(cr)
    db.session.commit()
    return cr


def _fluxos(t):
    db.session.expire_all()
    return FluxoCaixa.query.filter_by(admin_id=t.admin_id).all()


def _post_baixa(t, cr, **extra):
    dados = {
        'valor_recebido': '1000.00',
        'data_recebimento': DIA.isoformat(),
        'forma_recebimento': 'PIX',
    }
    dados.update(extra)
    return cliente_de(t.admin_id).post(
        f'/financeiro/contas-receber/{cr.id}/receber', data=dados)


# ---------------------------------------------------------------------------
# B3.6 — o gate contábil deixa de ser mudo
# ---------------------------------------------------------------------------

def test_cr_sem_conta_contabil_deixa_rastro_no_log(caplog):
    """O silêncio acaba, e é a única parte do A03 que não depende de escolha
    contábil nenhuma.

    🔬 A asserção é sobre o **log**, e não sobre o lançamento, de propósito: o
    comportamento (não lançar) está certo enquanto a CR não tiver conta
    contábil. O defeito é ninguém ficar sabendo — não há como responder "quantas
    CRs estão fora da contabilidade" sem esse rastro, e essa resposta é o
    diagnóstico de que as etapas seguintes do A03 dependem.
    """
    with app.app_context():
        t = um_tenant('a02log', data_ref=DIA, com_fatos=False)
        cr = _conta(t, conta_contabil=None)

        with caplog.at_level('WARNING'):
            r = _post_baixa(t, cr)
        assert r.status_code in (200, 302), f'a rota respondeu {r.status_code}'

        assert any('partida dobrada' in m.lower() for m in caplog.messages), (
            f'a baixa de uma CR sem conta_contabil_codigo passou calada; '
            f'mensagens: {caplog.messages}')


# ---------------------------------------------------------------------------
# B3.7 — guarda de re-baixa
# ---------------------------------------------------------------------------

@pytest.mark.parametrize('status', ['RECEBIDO', 'QUITADA'])
def test_conta_ja_liquidada_nao_aceita_nova_baixa(status):
    """Os DOIS status importam, e é por isso que o teste é parametrizado.

    `baixar_recebimento` grava **`RECEBIDO`**; quem quita a CR de medição é
    `services/medicao_service.py`, que grava **`QUITADA`**. Uma guarda que só
    olhasse um dos dois deixaria metade do parque desprotegido.

    O caminho mais plausível não é distração do operador: o import de extrato
    **cria a conta já `RECEBIDO`** (`services/importacao_excel.py:2478`), e
    baixá-la à mão soma de novo.
    """
    with app.app_context():
        t = um_tenant(f'a02rb{status[:3].lower()}', data_ref=DIA, com_fatos=False)
        cr = _conta(t, status=status, recebido=1000.00)

        _post_baixa(t, cr)

        db.session.expire_all()
        cr_db = db.session.get(ContaReceber, cr.id)
        assert Decimal(cr_db.valor_recebido) == Decimal('1000.00'), (
            f'a conta {status} aceitou nova baixa e o recebido foi para '
            f'{cr_db.valor_recebido} — é dinheiro contado duas vezes')
        assert len(_fluxos(t)) == 0, (
            'a re-baixa recusada ainda assim gravou FluxoCaixa')

