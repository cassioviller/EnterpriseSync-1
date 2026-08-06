"""B5.1 — a baixa de conta a pagar volta a funcionar, e recusa re-baixa.

Task B5.1 de `docs/superpowers/plans/2026-08-06-rodada-b5-varredura.md`.

**O defeito que este arquivo existe para nunca mais deixar passar.** A B3.6
(`01883756`) copiou o bloco de log do gate contábil do lado receber para
`baixar_pagamento` e não trocou a variável: `financeiro_service.py:133` cita
`valor_recebido` numa função cujo parâmetro é `valor_pago`. Como o bloco está
sob `if not conta.conta_contabil_codigo:` e (⚠️ dev) 0 de 627 `ContaPagar` têm
o campo, o `NameError` dispara em TODA baixa — depois do `commit()` de `:118`.
O operador vê "Erro ao registrar pagamento" (HTTP 200) sobre um pagamento que
já foi persistido. E não havia guarda de re-baixa do lado pagar: repetir o POST
soma (`conta.valor_pago += valor_pago`, `:97`).

**Por que o gate de 1937 não pegou:** nenhum teste da suíte fazia POST em
`/financeiro/contas-pagar/<id>/pagar` — só GET na listagem
(`tests/test_browser_all_modules.py:541/544/1793`).

**Matriz de mutação (Step 4 da Task).** Desfazer a correção do log derruba SÓ
os casos 1 e 2; desfazer a guarda derruba SÓ o caso 3. Por isso os casos 4 e 5
afirmam apenas ESTADO (que persiste mesmo com o NameError, porque o commit vem
antes do log) — eles medem semântica de baixa parcial e débito bancário, não o
contrato HTTP.

Cada teste cria a própria `ContaPagar` — nada aqui depende de ordem (lição da
Task B5.2, no mesmo documento).
"""
import logging
import os
import sys
from datetime import date
from decimal import Decimal

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import main  # noqa: F401 — registra os blueprints antes de qualquer request
from app import app, db
from models import BancoEmpresa, ContaPagar

from helpers_tenant import cliente_de, um_tenant

DATA_PAGTO = '2026-08-06'


@pytest.fixture(scope='module')
def tenant():
    with app.app_context():
        return um_tenant('b5cp', com_fatos=False)


def _nova_conta(admin_id, valor=1000):
    """ContaPagar PENDENTE sem `conta_contabil_codigo` — o caso de 627/627 em
    ⚠️ dev, e o único ramo que roda em produção."""
    with app.app_context():
        conta = ContaPagar(
            descricao='B5.1 conta de teste',
            valor_original=Decimal(valor),
            valor_pago=Decimal('0'),
            saldo=Decimal(valor),
            data_emissao=date(2026, 8, 1),
            data_vencimento=date(2026, 8, 20),
            status='PENDENTE',
            admin_id=admin_id,
        )
        db.session.add(conta)
        db.session.commit()
        return conta.id


def _post_baixa(cli, conta_id, valor, banco_id=None):
    data = {
        'valor_pago': str(valor),
        'data_pagamento': DATA_PAGTO,
        'forma_pagamento': 'PIX',
    }
    if banco_id is not None:
        data['banco_id'] = str(banco_id)
    return cli.post(f'/financeiro/contas-pagar/{conta_id}/pagar', data=data,
                    follow_redirects=False)


def _conta(conta_id):
    with app.app_context():
        return db.session.get(ContaPagar, conta_id)


def _flashes(cli):
    with cli.session_transaction() as s:
        return s.get('_flashes', [])


def test_caso1_baixa_sem_banco_caminho_padrao_do_modal(tenant):
    """POST de 1.000 sem banco_id → 302 para a listagem com flash de sucesso.

    Antes da correção: 200 renderizando `pagar_conta.html` com flash "Erro ao
    registrar pagamento" — e a conta JÁ PAGO no banco, porque o commit de
    `financeiro_service.py:118` vem antes do `NameError` de `:133`.
    """
    cli = cliente_de(tenant.admin_id)
    conta_id = _nova_conta(tenant.admin_id)

    r = _post_baixa(cli, conta_id, 1000)

    assert r.status_code == 302, (
        f'esperava 302 para a listagem, veio {r.status_code} — o sintoma da '
        f'B5.1 é exatamente um 200 com flash de erro sobre pagamento persistido')
    assert '/financeiro/contas-pagar' in r.headers['Location']
    categorias = [cat for cat, _ in _flashes(cli)]
    assert 'success' in categorias, f'flash de sucesso ausente: {_flashes(cli)}'

    conta = _conta(conta_id)
    assert conta.status == 'PAGO'
    assert float(conta.valor_pago) == 1000.0
    assert float(conta.saldo) == 0.0


def test_caso2_nameerror_nao_aparece_no_log(tenant, caplog):
    """A baixa não pode logar `NameError` nem citar `valor_recebido` — o bloco
    de log do gate contábil (`financeiro_service.py:127-133`) fala de
    `ContaPagar` e usa `valor_pago`."""
    cli = cliente_de(tenant.admin_id)
    conta_id = _nova_conta(tenant.admin_id)

    with caplog.at_level(logging.WARNING):
        _post_baixa(cli, conta_id, 1000)

    assert 'NameError' not in caplog.text
    assert 'valor_recebido' not in caplog.text
    assert 'Erro ao registrar pagamento' not in caplog.text


def test_caso3_rebaixa_recusada(tenant):
    """Segundo POST sobre conta já paga é RECUSADO pela guarda — sem ela,
    `baixar_pagamento` SOMA (`financeiro_service.py:97`) e a conta de R$ 1.000
    vai a R$ 2.000. O vetor não exige distração: `services/importacao_excel.py`
    (`:2414-2430`) cria `ContaPagar` já com `status='PAGO'`.

    Só a guarda é afirmada aqui (não o contrato do primeiro POST): é o que
    permite à mutação do Step 4 derrubar este caso isoladamente.
    """
    cli = cliente_de(tenant.admin_id)
    conta_id = _nova_conta(tenant.admin_id)

    _post_baixa(cli, conta_id, 1000)          # baixa legítima (setup)
    r2 = _post_baixa(cli, conta_id, 1000)     # re-baixa: deve ser recusada

    conta = _conta(conta_id)
    assert float(conta.valor_pago) == 1000.0, (
        f'valor_pago={conta.valor_pago}: a re-baixa SOMOU — a guarda de '
        f'`pagar_conta` (espelho da B3.7) não recusou o segundo POST')
    assert conta.status == 'PAGO'
    assert r2.status_code == 302
    assert '/financeiro/contas-pagar' in r2.headers['Location']
    categorias = [cat for cat, _ in _flashes(cli)]
    assert 'warning' in categorias, (
        f'esperava o flash de recusa da guarda: {_flashes(cli)}')


def test_caso4_baixa_parcial_nao_e_barrada(tenant):
    """400 + 600 = PARCIAL → PAGO com soma 1.000. A guarda não pode barrar
    baixa parcial: `PARCIAL` fica fora da lista de liquidados e `saldo` só
    zera na segunda baixa. Afirma SÓ estado — ver a matriz de mutação no topo.
    """
    cli = cliente_de(tenant.admin_id)
    conta_id = _nova_conta(tenant.admin_id)

    _post_baixa(cli, conta_id, 400)
    conta = _conta(conta_id)
    assert conta.status == 'PARCIAL'
    assert float(conta.valor_pago) == 400.0
    assert float(conta.saldo) == 600.0

    _post_baixa(cli, conta_id, 600)
    conta = _conta(conta_id)
    assert conta.status == 'PAGO'
    assert float(conta.valor_pago) == 1000.0
    assert float(conta.saldo) == 0.0


def test_caso5_banco_debitado_uma_unica_vez(tenant):
    """POST com `banco_id` do tenant debita `saldo_atual` exatamente uma vez
    (`financeiro_service.py:110-114`). Afirma SÓ estado."""
    with app.app_context():
        banco = BancoEmpresa(
            nome_banco='Banco B5', agencia='0001', conta='12345-6',
            saldo_inicial=Decimal('5000'), saldo_atual=Decimal('5000'),
            ativo=True, admin_id=tenant.admin_id)
        db.session.add(banco)
        db.session.commit()
        banco_id = banco.id

    cli = cliente_de(tenant.admin_id)
    conta_id = _nova_conta(tenant.admin_id)
    _post_baixa(cli, conta_id, 1000, banco_id=banco_id)

    with app.app_context():
        banco = db.session.get(BancoEmpresa, banco_id)
        assert float(banco.saldo_atual) == 4000.0, (
            f'saldo_atual={banco.saldo_atual}: o débito deveria ser único '
            f'(nota: o ESTORNO não devolver este débito é o item nº1 da §4 '
            f'da rodada B5 — Task própria, fora do escopo daqui)')
    conta = _conta(conta_id)
    assert conta.status == 'PAGO'
