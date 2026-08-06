"""B5.6 — o estorno devolve o débito bancário, e apaga o que a baixa criou.

Task B5.6 do apenso (§10) de
`docs/superpowers/plans/2026-08-06-rodada-b5-varredura.md`, sob a decisão
**D-B5.6 = (A)**: `ContaPagar.banco_id` persistido na baixa (migração 280),
estorno credita E limpa pelo campo.

**A catraca que este arquivo mede.** `baixar_pagamento` debita
`banco.saldo_atual` e NADA creditava de volta: `estornar_conta` devolvia
valor/saldo/status e deixava o débito — e `sum(banco.saldo_atual)` é
literalmente o `saldo_inicial` do fluxo de caixa. Pior: o LC que a baixa de
uma conta COMPRA de fato gera (o V2 de `gerar_lancamento_contabil_automatico`)
nascia com `origem='V2_AUTO'/origem_id=None`, e o delete do estorno buscava
`origem='FINANCEIRO_PAGAR'` — estornar+re-pagar DOBRAVA a contabilidade. O
mesmo no GCP: o delete buscava `origem='GESTAO_CUSTO_PAI'` e o escritor real
gravava `V2_AUTO` (defeito registrado em `analises-2026-07-30.json:1529`,
correção proposta em `:1556` desde 30/07 — este arquivo é o cobrador).

**Matriz de mutação (Step 7).** Desfazer o crédito+limpeza do estorno derruba
só os casos 1 e 4; desfazer a rastreabilidade dos LCs + limpeza do GCP derruba
só os casos 5 e 6.

⚠️ Zero testes citavam `estornar` antes deste arquivo (medido na varredura).
"""
import os
import sys
import uuid
from datetime import date
from decimal import Decimal

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import main  # noqa: F401 — registra os blueprints antes de qualquer request
from app import app, db
from models import (BancoEmpresa, ContaPagar, FluxoCaixa, GestaoCustoPai,
                    LancamentoContabil)

from helpers_tenant import cliente_de, um_tenant

DATA = '2026-08-06'


@pytest.fixture(scope='module')
def tenant():
    # helpers_tenant cria o admin com versao_sistema='v2' — o que liga o
    # gerador de LC V2 na baixa (caso 5) e o _check_v2 do GCP (caso 6).
    # CSRF off: o blueprint gestao_custos não é exempt (o financeiro é), e o
    # caso 6 posta nele — mesmo padrão de test_e2e_orcamento_operacional.
    app.config['TESTING'] = True
    app.config['WTF_CSRF_ENABLED'] = False
    with app.app_context():
        return um_tenant('b5est', com_fatos=False)


def _banco(admin_id, saldo=5000):
    with app.app_context():
        b = BancoEmpresa(
            nome_banco=f'Banco B56 {uuid.uuid4().hex[:4]}', agencia='0001',
            conta=f'{uuid.uuid4().int % 10**6}-0',
            saldo_inicial=Decimal(saldo), saldo_atual=Decimal(saldo),
            ativo=True, admin_id=admin_id)
        db.session.add(b)
        db.session.commit()
        return b.id


def _conta(admin_id, valor=1000, origem_tipo=None, **kw):
    campos = dict(
        descricao='B5.6 conta', valor_original=Decimal(valor),
        valor_pago=Decimal('0'), saldo=Decimal(valor),
        data_emissao=date(2026, 8, 1), data_vencimento=date(2026, 8, 20),
        status='PENDENTE', origem_tipo=origem_tipo, admin_id=admin_id)
    campos.update(kw)  # caso 3 sobrescreve status/valor_pago/saldo (legado)
    with app.app_context():
        c = ContaPagar(**campos)
        db.session.add(c)
        db.session.commit()
        return c.id


def _gcp(admin_id, obra_id, valor=1000):
    with app.app_context():
        g = GestaoCustoPai(
            tipo_categoria='MATERIAL', entidade_nome='Fornecedor B56',
            valor_total=Decimal(valor), status='AUTORIZADO',
            admin_id=admin_id, obra_id=obra_id)
        db.session.add(g)
        db.session.commit()
        return g.id


def _pagar(cli, conta_id, valor, banco_id=None):
    data = {'valor_pago': str(valor), 'data_pagamento': DATA,
            'forma_pagamento': 'PIX'}
    if banco_id is not None:
        data['banco_id'] = str(banco_id)
    return cli.post(f'/financeiro/contas-pagar/{conta_id}/pagar', data=data,
                    follow_redirects=False)


def _estornar(cli, conta_id):
    return cli.post(f'/financeiro/contas-pagar/{conta_id}/estornar',
                    follow_redirects=False)


def _saldo_banco(banco_id):
    with app.app_context():
        return float(db.session.get(BancoEmpresa, banco_id).saldo_atual)


def _cp(conta_id):
    with app.app_context():
        return db.session.get(ContaPagar, conta_id)


def _flashes(cli):
    with cli.session_transaction() as s:
        return s.get('_flashes', [])


def test_caso1_estorno_devolve_o_debito_e_limpa_o_campo(tenant):
    """Baixa de R$ 1.000 com banco → estorno: `saldo_atual` volta ao inicial,
    `conta.banco_id` limpo, status PENDENTE. Antes da B5.6: o débito ficava
    para sempre — a catraca."""
    cli = cliente_de(tenant.admin_id)
    banco_id = _banco(tenant.admin_id, 5000)
    conta_id = _conta(tenant.admin_id)

    _pagar(cli, conta_id, 1000, banco_id=banco_id)
    assert _saldo_banco(banco_id) == 4000.0  # débito da baixa, sanidade

    _estornar(cli, conta_id)

    assert _saldo_banco(banco_id) == 5000.0, (
        f'saldo_atual={_saldo_banco(banco_id)}: o estorno NÃO devolveu o '
        f'débito — a catraca do item nº1 da §4')
    conta = _cp(conta_id)
    assert conta.status == 'PENDENTE'
    assert conta.banco_id is None, 'banco_id tem de ser limpo no estorno'


def test_caso2_estorno_de_baixa_sem_banco_nao_inventa_credito(tenant):
    cli = cliente_de(tenant.admin_id)
    banco_id = _banco(tenant.admin_id, 5000)
    conta_id = _conta(tenant.admin_id)

    _pagar(cli, conta_id, 1000)          # sem banco — caminho padrão do modal
    _estornar(cli, conta_id)

    assert _saldo_banco(banco_id) == 5000.0, 'crédito inventado sem débito'
    assert _cp(conta_id).status == 'PENDENTE'


def test_caso3_conta_legada_paga_sem_banco_estorna_com_aviso_e_credito_zero(tenant):
    """A forma do import (`importacao_excel.py:2414-2430`): conta nasce PAGO
    com banco_id NULL. Estorno reverte a conta, credita ZERO e avisa — o caso
    que um teste só-caminho-feliz deixaria verde e oco (risco 2)."""
    cli = cliente_de(tenant.admin_id)
    banco_id = _banco(tenant.admin_id, 5000)
    conta_id = _conta(tenant.admin_id, valor=800, status='PAGO',
                      valor_pago=Decimal('800'), saldo=Decimal('0'),
                      data_pagamento=date(2026, 8, 2))

    _estornar(cli, conta_id)

    assert _saldo_banco(banco_id) == 5000.0
    conta = _cp(conta_id)
    assert conta.status == 'PENDENTE'
    msgs = ' | '.join(m for _, m in _flashes(cli))
    assert 'sem banco' in msgs.lower() or 'não havia banco' in msgs.lower(), (
        f'faltou o aviso explícito do crédito zero: {msgs}')


def test_caso4_segundo_ciclo_credita_o_banco_da_segunda_rodada(tenant):
    """estorno → re-baixa com OUTRO banco → 2º estorno credita o banco da 2ª
    rodada. É a prova da LIMPEZA do campo: sem ela, o 2º estorno creditaria o
    banco errado (catraca invertida — risco 1)."""
    cli = cliente_de(tenant.admin_id)
    banco_a = _banco(tenant.admin_id, 5000)
    banco_b = _banco(tenant.admin_id, 3000)
    conta_id = _conta(tenant.admin_id)

    _pagar(cli, conta_id, 1000, banco_id=banco_a)
    _estornar(cli, conta_id)
    _pagar(cli, conta_id, 1000, banco_id=banco_b)
    _estornar(cli, conta_id)

    assert _saldo_banco(banco_a) == 5000.0, 'banco A deveria ter voltado ao inicial'
    assert _saldo_banco(banco_b) == 3000.0, (
        f'banco B={_saldo_banco(banco_b)}: o 2º estorno não creditou o banco '
        f'da 2ª rodada — o campo não foi regravado/limpo direito')
    assert _cp(conta_id).banco_id is None


def test_caso5_estornar_e_repagar_nao_dobra_a_contabilidade(tenant):
    """Conta COMPRA num admin V2: a baixa gera o LC de pagamento_fornecedor
    (o V2 — no parque real, o ÚNICO LC que a baixa gera). O estorno tem de
    apagá-lo; antes da B5.6 ele buscava origem='FINANCEIRO_PAGAR' e o LC
    nascia 'V2_AUTO'/origem_id=None — estornar+re-pagar dobrava."""
    cli = cliente_de(tenant.admin_id)
    conta_id = _conta(tenant.admin_id, origem_tipo='COMPRA')

    def _n_lcs():
        with app.app_context():
            return LancamentoContabil.query.filter(
                LancamentoContabil.admin_id == tenant.admin_id,
                LancamentoContabil.historico.like('%B5.6 conta%')).count()

    _pagar(cli, conta_id, 1000)
    n_apos_baixa = _n_lcs()
    assert n_apos_baixa >= 1, 'sanidade: a baixa V2 de COMPRA gera LC'

    _estornar(cli, conta_id)
    assert _n_lcs() == 0, (
        f'{_n_lcs()} LC(s) sobraram após o estorno — o delete não casa com o '
        f'que a baixa criou (o no-op de origem)')

    _pagar(cli, conta_id, 1000)
    assert _n_lcs() == n_apos_baixa, (
        f'{_n_lcs()} LCs após re-pagar (era {n_apos_baixa} na 1ª baixa): '
        f'estornar+re-pagar dobrou a contabilidade')


def test_caso6_estornar_gcp_remove_fc_limpa_ponteiros_e_apaga_lc(tenant):
    """Pagar GCP cria FluxoCaixa SAIDA + LC V2 e grava ponteiros no pai. O
    estorno tem de desfazer os três — antes, o FC ficava (saída dobrada nos
    buckets no re-pagamento), os ponteiros ficavam e o delete de LC era no-op
    por construção (`analises-2026-07-30.json:1529`). E `saldo_atual` fica
    INTOCADO: pagar GCP nunca debitou banco (item nº2 da §4)."""
    cli = cliente_de(tenant.admin_id)
    banco_id = _banco(tenant.admin_id, 7000)
    gcp_id = _gcp(tenant.admin_id, tenant.obra_id)

    r = cli.post(f'/gestao-custos/{gcp_id}/pagar',
                 data={'data_pagamento': DATA, 'banco_id': str(banco_id),
                       'valor_pago': '1000'},
                 follow_redirects=False)
    assert r.status_code == 302

    def _estado():
        with app.app_context():
            g = db.session.get(GestaoCustoPai, gcp_id)
            fcs = FluxoCaixa.query.filter_by(
                admin_id=tenant.admin_id, referencia_tabela='gestao_custo_pai',
                referencia_id=gcp_id).count()
            lcs = LancamentoContabil.query.filter(
                LancamentoContabil.admin_id == tenant.admin_id,
                LancamentoContabil.historico.like('%Fornecedor B56%')).count()
            return g.status, g.fluxo_caixa_id, g.conta_bancaria, fcs, lcs

    status, fc_id, conta_banc, n_fc, n_lc = _estado()
    assert status == 'PAGO' and n_fc == 1, 'sanidade: pagamento criou o FC'
    # 🔬 Achado da própria B5.6, medido ao escrever este teste: o pagamento de
    # GCP NUNCA gerou LC — os dois caminhos passam tipo_operacao
    # 'DESPESA_GERAL', que NÃO existe no MAPEAMENTO_CONTABIL
    # (contabilidade_utils.py:1536-1543; o gerador loga "não mapeada" e
    # devolve False). Mapear é escolher conta contábil = decisão de contador
    # (lição do A03). O carimbo de origem da B5.6 deixa o caminho pronto: no
    # dia em que o mapeamento existir, o LC nasce estornável e a asserção
    # de zero-sobras abaixo passa a carregar peso real.
    assert n_lc == 0, 'premissa do achado mudou: DESPESA_GERAL foi mapeada? '\
                      'Reavaliar o caso 6 (o LC agora nasce e deve ser estornado)'

    cli.post(f'/financeiro/gestao-custo/{gcp_id}/estornar',
             follow_redirects=False)

    status, fc_id, conta_banc, n_fc, n_lc = _estado()
    assert status == 'PENDENTE'
    assert n_fc == 0, f'{n_fc} FluxoCaixa SAIDA sobrou após o estorno — re-pagar dobraria a saída nos buckets'
    assert fc_id is None, 'pai.fluxo_caixa_id não foi limpo'
    assert conta_banc is None, 'pai.conta_bancaria não foi limpa'
    assert n_lc == 0, f'{n_lc} LC(s) sobraram — o delete do estorno de GCP continua no-op'
    assert _saldo_banco(banco_id) == 7000.0, (
        'saldo_atual mudou num fluxo de GCP — GCP nunca debita banco (nº2)')


def test_caso7_parcial_recusa_troca_de_banco_e_completa_no_mesmo(tenant):
    """Parcial de 400 no banco A → parcial de 600 no banco B é RECUSADA
    (coluna única + estorno tudo-ou-nada: trocar de banco em parcial
    creditaria o total no banco errado — risco 3). Completar no banco A
    fecha PAGO normalmente."""
    cli = cliente_de(tenant.admin_id)
    banco_a = _banco(tenant.admin_id, 5000)
    banco_b = _banco(tenant.admin_id, 3000)
    conta_id = _conta(tenant.admin_id)

    _pagar(cli, conta_id, 400, banco_id=banco_a)
    conta = _cp(conta_id)
    assert conta.status == 'PARCIAL' and float(conta.valor_pago) == 400.0

    _pagar(cli, conta_id, 600, banco_id=banco_b)
    conta = _cp(conta_id)
    assert float(conta.valor_pago) == 400.0, (
        f'valor_pago={conta.valor_pago}: a troca de banco em PARCIAL deveria '
        f'ser recusada')
    assert _saldo_banco(banco_b) == 3000.0, 'banco B não podia ser debitado'

    _pagar(cli, conta_id, 600, banco_id=banco_a)
    conta = _cp(conta_id)
    assert conta.status == 'PAGO' and float(conta.valor_pago) == 1000.0
    assert _saldo_banco(banco_a) == 4000.0
