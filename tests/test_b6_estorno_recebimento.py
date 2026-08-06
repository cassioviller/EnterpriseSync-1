"""B6.1 — o estorno de recebimento nasce inteiro: debita o banco, apaga FC e LC.

Task B6.1 de `docs/superpowers/plans/2026-08-06-rodada-b6-varredura.md`, sob a
decisão **D-B6.1**: `ContaReceber.banco_id` persistido na baixa (migração 281),
estorno debita E limpa pelo campo — e **exclui `origem_tipo='OBRA_MEDICAO'`**.

**A catraca que este arquivo mede.** Antes da B6.1 não existia estorno de
recebimento nenhum (🔬 grep `estorn` fora de archive/tests: só `estornar_conta`,
`estornar_gcp` e `contabilidade.estornar_lancamento`). `baixar_recebimento`
credita `banco.saldo_atual += valor` e **descartava** qual banco foi — o espelho
exato da B5.6, direção invertida. E o receber tem o que o pagar não tinha: o
**FC ENTRADA é vivo** (escritor no checkbox do modal, leitor `rr_query` no fluxo
realizado), então estorno sem delete de FC deixaria **entrada fantasma**.

⚠️ **O escopo OBR-MED é a correção mais séria da rodada.** A CR de medição é um
acumulador com UPSERT que o recalc reescreve; um cinto de banco único aplicado a
ela travaria a **baixa de medição** — fluxo vivo, 104 liquidadas no parque — com
ValueError engolido em flash genérico. Cinto e gravação NÃO se aplicam a
`origem_tipo='OBRA_MEDICAO'`, e o **caso 7 é o cão de guarda** disso.

**Matriz de mutação (Step 7), MEDIDA — e ela desviou do recorte em dois pontos.**
Delete de LC removido → só o 4; cinto removido → só o 5; **escopo do cinto
removido → só o 7** (cirúrgicas, como previsto). Mas: débito desligado derruba
1 **e 8**; delete de FC removido derruba 3 **e 8**. O recorte previu as cinco
cirúrgicas porque escreveu a matriz antes de o caso 8 existir com as asserções
que tem — o 8 é o ciclo integrativo, e afirmar "nada dobra" **é** afirmar que o
banco voltou e que o FC saiu. O overlap é poder de oráculo real, não teste
frouxo: enfraquecer o 8 para limpar a matriz trocaria cobertura por estética.
Cada mutação continua sendo apanhada pelo seu caso dedicado.
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
from financeiro_service import FinanceiroService
from models import (BancoEmpresa, ContaReceber, FluxoCaixa, LancamentoContabil,
                    PlanoContas)

from helpers_tenant import cliente_de, um_tenant

# ⚠️ Cão de guarda do verde-e-oco (risco 3): o oráculo do caso 3 é `rr_query`
# (`financeiro_service.py:774-796`), que filtra por `data_movimento` DENTRO da
# janela e por `obra_id`. Data da baixa e janela consultada são fixadas juntas
# aqui — um FC fora da janela sumiria do oráculo por filtro, não por delete, e
# o caso ficaria verde sobre nada.
DATA = '2026-08-06'
DATA_D = date(2026, 8, 6)
JANELA = (date(2026, 8, 1), date(2026, 8, 31))

CONTA_RECEITA = '3.1.01.001'
# A partida de DÉBITO da baixa é fixa em Caixa/Bancos
# (`financeiro_service.py:416`), e `partida_contabil` tem FK composta para
# `plano_contas` — sem semear as DUAS contas o LC do caso 4 nem nasce.
CONTA_CAIXA = '1.1.01.001'


@pytest.fixture(scope='module')
def tenant():
    app.config['TESTING'] = True
    app.config['WTF_CSRF_ENABLED'] = False
    with app.app_context():
        t = um_tenant('b6est', com_fatos=False)
        # O FK composto (admin_id, conta_contabil_codigo) → plano_contas exige
        # a conta existir antes de a CR do caso 4 citá-la.
        db.session.add(PlanoContas(
            admin_id=t.admin_id, codigo=CONTA_RECEITA,
            nome='Receita de Obras B6.1', tipo_conta='RECEITA',
            natureza='CREDORA', nivel=4, aceita_lancamento=True, ativo=True))
        db.session.add(PlanoContas(
            admin_id=t.admin_id, codigo=CONTA_CAIXA,
            nome='Caixa e Equivalentes', tipo_conta='ATIVO',
            natureza='DEVEDORA', nivel=4, aceita_lancamento=True, ativo=True))
        db.session.commit()
        return t


def _banco(admin_id, saldo=5000):
    with app.app_context():
        b = BancoEmpresa(
            nome_banco=f'Banco B61 {uuid.uuid4().hex[:4]}', agencia='0001',
            conta=f'{uuid.uuid4().int % 10**6}-0',
            saldo_inicial=Decimal(saldo), saldo_atual=Decimal(saldo),
            ativo=True, admin_id=admin_id)
        db.session.add(b)
        db.session.commit()
        return b.id


def _conta(admin_id, valor=1000, origem_tipo=None, obra_id=None, **kw):
    campos = dict(
        cliente_nome='Cliente B6.1', descricao='B6.1 conta',
        valor_original=Decimal(valor), valor_recebido=Decimal('0'),
        saldo=Decimal(valor), data_emissao=date(2026, 8, 1),
        data_vencimento=date(2026, 8, 20), status='PENDENTE',
        origem_tipo=origem_tipo, obra_id=obra_id, admin_id=admin_id)
    campos.update(kw)  # casos 9 e 5 sobrescrevem status/valor_recebido/saldo
    with app.app_context():
        c = ContaReceber(**campos)
        db.session.add(c)
        db.session.commit()
        return c.id


def _receber(cli, conta_id, valor, banco_id=None, fluxo=False):
    data = {'valor_recebido': str(valor), 'data_recebimento': DATA,
            'forma_recebimento': 'PIX'}
    if banco_id is not None:
        data['banco_id'] = str(banco_id)
    if fluxo:
        data['criar_fluxo_caixa'] = '1'
    return cli.post(f'/financeiro/contas-receber/{conta_id}/receber',
                    data=data, follow_redirects=False)


def _estornar(cli, conta_id):
    return cli.post(f'/financeiro/contas-receber/{conta_id}/estornar',
                    follow_redirects=False)


def _saldo_banco(banco_id):
    with app.app_context():
        return float(db.session.get(BancoEmpresa, banco_id).saldo_atual)


def _cr(conta_id):
    with app.app_context():
        return db.session.get(ContaReceber, conta_id)


def _flashes(cli):
    with cli.session_transaction() as s:
        return s.get('_flashes', [])


def test_caso1_estorno_debita_o_banco_e_limpa_o_campo(tenant):
    """Baixa de R$ 1.000 com banco → estorno: `saldo_atual` volta ao inicial,
    `conta.banco_id` limpo, status PENDENTE, saldo = valor_original. É o único
    DÉBITO novo do sistema — o par invertido de `financeiro_service.py:127`."""
    cli = cliente_de(tenant.admin_id)
    banco_id = _banco(tenant.admin_id, 5000)
    conta_id = _conta(tenant.admin_id)

    _receber(cli, conta_id, 1000, banco_id=banco_id)
    assert _saldo_banco(banco_id) == 6000.0, 'sanidade: a baixa credita o banco'

    _estornar(cli, conta_id)

    assert _saldo_banco(banco_id) == 5000.0, (
        f'saldo_atual={_saldo_banco(banco_id)}: o estorno NÃO debitou de volta '
        f'— a catraca invertida da B5.6')
    conta = _cr(conta_id)
    assert conta.status == 'PENDENTE'
    assert float(conta.valor_recebido) == 0.0
    assert float(conta.saldo) == 1000.0
    assert conta.data_recebimento is None
    assert conta.banco_id is None, 'banco_id tem de ser limpo no estorno'


def test_caso2_estorno_de_baixa_sem_banco_nao_inventa_debito(tenant):
    """Baixa sem banco → estorno debita ZERO e avisa. Simétrico do "nunca
    inventar crédito" da B5.6: aqui é nunca inventar DÉBITO."""
    cli = cliente_de(tenant.admin_id)
    banco_id = _banco(tenant.admin_id, 5000)
    conta_id = _conta(tenant.admin_id)

    _receber(cli, conta_id, 1000)          # sem banco
    _estornar(cli, conta_id)

    assert _saldo_banco(banco_id) == 5000.0, 'débito inventado sem crédito'
    assert _cr(conta_id).status == 'PENDENTE'
    msgs = ' | '.join(m for _, m in _flashes(cli))
    assert 'sem banco' in msgs.lower(), (
        f'faltou o aviso explícito do débito zero: {msgs}')


def test_caso3_estorno_apaga_o_fluxo_caixa_entrada(tenant):
    """Baixa com o checkbox de FC ENTRADA → estorno: o FC some do `rr_query`.
    Sem o delete, a entrada vira FANTASMA no fluxo realizado (o simétrico do
    vazamento nº3 da B5.6) e a re-baixa dobraria a entrada nos buckets.

    ⚠️ Data e obra fixadas DENTRO da janela consultada — senão o caso ficaria
    verde por filtro, não por delete (achado do adversário)."""
    cli = cliente_de(tenant.admin_id)
    banco_id = _banco(tenant.admin_id, 5000)
    conta_id = _conta(tenant.admin_id, obra_id=tenant.obra_id)

    def _entradas_realizadas():
        with app.app_context():
            fluxo = FinanceiroService.calcular_fluxo_caixa(
                tenant.admin_id, JANELA[0], JANELA[1], obra_id=tenant.obra_id)
            return [d for d in fluxo['detalhes']
                    if d.get('origem') == 'Conta a Receber'
                    and d.get('realizado')]

    _receber(cli, conta_id, 1000, banco_id=banco_id, fluxo=True)
    assert len(_entradas_realizadas()) == 1, (
        'sanidade: a baixa com checkbox gera o FC ENTRADA e ele aparece no '
        'rr_query — se falhar AQUI, a janela/obra do arreio está errada e o '
        'resto do caso seria verde-e-oco')

    _estornar(cli, conta_id)

    assert _entradas_realizadas() == [], (
        'FluxoCaixa ENTRADA sobrou após o estorno — entrada fantasma no fluxo '
        'realizado')
    with app.app_context():
        assert FluxoCaixa.query.filter_by(
            admin_id=tenant.admin_id, referencia_tabela='conta_receber',
            referencia_id=conta_id).count() == 0


def test_caso4_estornar_e_rebaixar_nao_dobra_a_contabilidade(tenant):
    """CR com conta contábil: a baixa gera o LC `FINANCEIRO_RECEBER` (já nasce
    carimbado, `financeiro_service.py:405-406` — sem Step de carimbo, ao
    contrário da B5.6). O estorno tem de apagá-lo (partidas por cascade), e a
    re-baixa não pode dobrar."""
    cli = cliente_de(tenant.admin_id)
    banco_id = _banco(tenant.admin_id, 5000)
    conta_id = _conta(tenant.admin_id, conta_contabil_codigo=CONTA_RECEITA)

    def _n_lcs():
        with app.app_context():
            return LancamentoContabil.query.filter_by(
                admin_id=tenant.admin_id, origem='FINANCEIRO_RECEBER',
                origem_id=conta_id).count()

    _receber(cli, conta_id, 1000, banco_id=banco_id)
    n_apos_baixa = _n_lcs()
    assert n_apos_baixa >= 1, 'sanidade: a baixa com conta contábil gera LC'

    _estornar(cli, conta_id)
    assert _n_lcs() == 0, (
        f'{_n_lcs()} LC(s) sobraram após o estorno — o delete por origem não '
        f'casa com o que a baixa criou')

    _receber(cli, conta_id, 1000, banco_id=banco_id)
    assert _n_lcs() == n_apos_baixa, (
        f'{_n_lcs()} LCs após re-baixar (era {n_apos_baixa}): estornar+'
        f're-baixar dobrou a contabilidade')


def test_caso5_parcial_recusa_troca_de_banco_e_completa_no_mesmo(tenant):
    """CR COMUM: parcial de 400 no banco A → parcial de 600 no banco B é
    RECUSADA (coluna única + estorno tudo-ou-nada: trocar de banco em parcial
    debitaria o total do banco errado). Completar no banco A fecha RECEBIDO.

    O gatilho é `valor_recebido > 0`, não `status == 'PARCIAL'` — lição (ii) da
    WF-3: a CR legada meio-recebida fica em PENDENTE e escaparia da guarda por
    status."""
    cli = cliente_de(tenant.admin_id)
    banco_a = _banco(tenant.admin_id, 5000)
    banco_b = _banco(tenant.admin_id, 3000)
    conta_id = _conta(tenant.admin_id)

    _receber(cli, conta_id, 400, banco_id=banco_a)
    conta = _cr(conta_id)
    assert conta.status == 'PARCIAL' and float(conta.valor_recebido) == 400.0

    _receber(cli, conta_id, 600, banco_id=banco_b)
    conta = _cr(conta_id)
    assert float(conta.valor_recebido) == 400.0, (
        f'valor_recebido={conta.valor_recebido}: a troca de banco em PARCIAL '
        f'deveria ser recusada')
    assert _saldo_banco(banco_b) == 3000.0, 'banco B não podia ser creditado'
    msgs = ' | '.join(m for _, m in _flashes(cli))
    assert 'mesmo banco' in msgs.lower(), (
        f'a recusa da view tem de DIZER o caminho (mesmo banco ou estornar), '
        f'não cair no "Erro ao registrar recebimento" genérico: {msgs}')

    # O cinto é de DUAS camadas, como no lado pagar: a de cima dá o flash, a de
    # baixo (o raise no service) defende qualquer chamador que contorne a view
    # — API, lote, import. Sem este trecho, apagar só o cinto do service não
    # derrubaria teste nenhum.
    with app.app_context():
        with pytest.raises(ValueError, match='caminho bancário'):
            FinanceiroService.baixar_recebimento(
                conta_id=conta_id, admin_id=tenant.admin_id,
                valor_recebido=Decimal('600'), data_recebimento=DATA_D,
                forma_recebimento='PIX', banco_id=banco_b)

    _receber(cli, conta_id, 600, banco_id=banco_a)
    conta = _cr(conta_id)
    assert conta.status == 'RECEBIDO' and float(conta.valor_recebido) == 1000.0
    assert _saldo_banco(banco_a) == 6000.0


def test_caso6_cr_de_medicao_nao_e_estornavel(tenant):
    """D-B6.1: a CR de medição é um acumulador com UPSERT que o recalc
    reescreve e o portal do cliente exibe. Estorná-la por esta rota deixaria o
    recalc e o portal fora de sincronia — a rota recusa POR ORIGEM, mesmo em
    RECEBIDO."""
    cli = cliente_de(tenant.admin_id)
    banco_id = _banco(tenant.admin_id, 5000)
    conta_id = _conta(tenant.admin_id, origem_tipo='OBRA_MEDICAO',
                      obra_id=tenant.obra_id)

    _receber(cli, conta_id, 1000, banco_id=banco_id)
    assert _cr(conta_id).status == 'RECEBIDO'
    saldo_apos_baixa = _saldo_banco(banco_id)

    _estornar(cli, conta_id)

    conta = _cr(conta_id)
    assert conta.status == 'RECEBIDO', (
        'a CR de medição foi estornada — a D-B6.1 recusa por origem')
    assert float(conta.valor_recebido) == 1000.0
    assert _saldo_banco(banco_id) == saldo_apos_baixa, 'banco não podia mudar'
    msgs = ' | '.join(m for _, m in _flashes(cli))
    assert 'medi' in msgs.lower(), (
        f'a recusa tem de dizer POR QUE (origem medição): {msgs}')


def test_caso7_cr_de_medicao_aceita_segunda_baixa_em_outro_banco(tenant):
    """⚠️ O CÃO DE GUARDA DO ESCOPO — o caso que quebraria produção.

    A CR de medição acumula baixas ao longo das medições da obra. Se o cinto de
    banco único valesse para ela, a primeira obra que trocasse de banco entre
    medições veria a baixa falhar com ValueError engolido em flash genérico
    (`financeiro_views.py:837-839`). Cinto e gravação NÃO se aplicam a
    OBRA_MEDICAO: a 2ª baixa em OUTRO banco PASSA, e credita o banco novo."""
    cli = cliente_de(tenant.admin_id)
    banco_a = _banco(tenant.admin_id, 5000)
    banco_b = _banco(tenant.admin_id, 3000)
    conta_id = _conta(tenant.admin_id, valor=1000, origem_tipo='OBRA_MEDICAO',
                      obra_id=tenant.obra_id)

    _receber(cli, conta_id, 400, banco_id=banco_a)
    _receber(cli, conta_id, 600, banco_id=banco_b)

    conta = _cr(conta_id)
    assert float(conta.valor_recebido) == 1000.0, (
        f'valor_recebido={conta.valor_recebido}: a 2ª baixa da medição em '
        f'outro banco foi BARRADA — o cinto vazou para OBRA_MEDICAO e trava a '
        f'baixa de medição em produção')
    assert conta.status == 'RECEBIDO'
    assert _saldo_banco(banco_a) == 5400.0
    assert _saldo_banco(banco_b) == 3600.0
    assert conta.banco_id is None, (
        'CR de medição não grava banco_id — não se prende a caminho bancário')


def test_caso8_ciclo_estornar_rebaixar_nao_dobra_nada(tenant):
    """estornar → re-baixar passa a guarda B3.7 (a conta volta PENDENTE com
    saldo cheio) e nada dobra: banco, FC e LC ficam como na 1ª baixa."""
    cli = cliente_de(tenant.admin_id)
    banco_a = _banco(tenant.admin_id, 5000)
    banco_b = _banco(tenant.admin_id, 3000)
    conta_id = _conta(tenant.admin_id, obra_id=tenant.obra_id)

    def _n_fcs():
        with app.app_context():
            return FluxoCaixa.query.filter_by(
                admin_id=tenant.admin_id, referencia_tabela='conta_receber',
                referencia_id=conta_id).count()

    _receber(cli, conta_id, 1000, banco_id=banco_a, fluxo=True)
    _estornar(cli, conta_id)
    conta = _cr(conta_id)
    assert conta.status == 'PENDENTE' and float(conta.saldo) == 1000.0, (
        'sem voltar a PENDENTE com saldo cheio, a guarda B3.7 barraria a '
        're-baixa e o ciclo seria impossível')

    # Re-baixa em OUTRO banco: prova a LIMPEZA do campo — sem ela o 2º estorno
    # debitaria o banco errado (catraca invertida).
    _receber(cli, conta_id, 1000, banco_id=banco_b, fluxo=True)
    assert _n_fcs() == 1, f'{_n_fcs()} FCs: o estorno não apagou o da 1ª baixa'

    _estornar(cli, conta_id)

    assert _saldo_banco(banco_a) == 5000.0, 'banco A deveria ter voltado'
    assert _saldo_banco(banco_b) == 3000.0, (
        f'banco B={_saldo_banco(banco_b)}: o 2º estorno não debitou o banco da '
        f'2ª rodada — o campo não foi regravado/limpo direito')
    assert _n_fcs() == 0
    assert _cr(conta_id).banco_id is None


def test_caso9_cr_legada_recebida_sem_banco_estorna_com_aviso_e_debito_zero(tenant):
    """A forma do import (`importacao_excel.py:2469-2503`): a CR nasce já
    RECEBIDO com `banco_id` NULL — o import nunca creditou `saldo_atual`.
    O estorno reverte a conta, debita ZERO e avisa. É o caso que um teste
    só-caminho-feliz deixaria verde e oco (risco 2)."""
    cli = cliente_de(tenant.admin_id)
    banco_id = _banco(tenant.admin_id, 5000)
    conta_id = _conta(tenant.admin_id, valor=800, status='RECEBIDO',
                      valor_recebido=Decimal('800'), saldo=Decimal('0'),
                      data_recebimento=date(2026, 8, 2))

    _estornar(cli, conta_id)

    assert _saldo_banco(banco_id) == 5000.0, 'débito inventado numa CR legada'
    conta = _cr(conta_id)
    assert conta.status == 'PENDENTE'
    assert float(conta.saldo) == 800.0
    msgs = ' | '.join(m for _, m in _flashes(cli))
    assert 'sem banco' in msgs.lower(), (
        f'faltou o aviso explícito do débito zero: {msgs}')
