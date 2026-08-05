"""A03 — a CR de medição nasce ligada à contabilidade, e o recebimento LIQUIDA o
cliente em vez de inventar receita.

## Por que este arquivo passa pelo EVENTO

`tests/test_ciclo_proposta_obra_medido_cr.py` chama `recalcular_medicao_obra`
**direto**. Isso prova o cálculo e não prova o trajeto: o caminho de produção é
`EventManager.emit('rdo_finalizado', ...)` → `recalcular_medicao_apos_rdo`
(`event_manager.py:1748`) → commit. E é exatamente no trajeto que mora o risco da
Task, porque o `except` daquele handler **loga e não faz rollback**, e o `emit`
engole a exceção (`event_manager.py:44-52`). Um `IntegrityError` da FK composta ali
não apareceria como erro: apareceria como os handlers SEGUINTES de `rdo_finalizado`
quebrando com `PendingRollbackError`, num ponto que não tem nada a ver com a causa.

## A escolha contábil que este arquivo decide

Na aprovação, `handlers/propostas_handlers.py:454-486` debita **`1.1.02.001`
(Clientes)** e credita **`4.1.01.001`** — a receita **já foi reconhecida ali**.
Quando a medição é recebida, o dinheiro entra e o direito contra o cliente é que se
extingue: DÉBITO em caixa, CRÉDITO em `1.1.02.001`.

Se a CR de medição nascesse com `4.1.01.001`, o recebimento creditaria receita **de
novo** — a mesma venda reconhecida duas vezes, e o DRE do mês inflado. É por isso
que a asserção do DRE existe: ela é o cão de guarda contra o `4.1.01.001` que o
documento original do A03 sugeria.
"""
import os
import sys
from datetime import date
from decimal import Decimal

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import main  # noqa: F401 — registra handlers e blueprints
from app import app, db
from contabilidade_utils import calcular_dre_mensal
from event_manager import EventManager
from models import (ContaReceber, ItemMedicaoComercial,
                    ItemMedicaoCronogramaTarefa, LancamentoContabil, Obra,
                    PartidaContabil, PlanoContas, Proposta, PropostaItem,
                    TarefaCronograma)

from helpers_tenant import cliente_de, um_tenant

pytestmark = pytest.mark.integration

DIA = date(2026, 1, 15)
CONTRATO = Decimal('1000.00')
MEDIDO = Decimal('500.00')  # 50% da tarefa única


@pytest.fixture(autouse=True)
def _config():
    app.config['TESTING'] = True
    app.config['WTF_CSRF_ENABLED'] = False
    if not app.secret_key:
        app.secret_key = 'test-a03'
    yield


def _proposta_aprovada(t):
    """Proposta de R$ 1.000 aprovada pelo EVENTO — que é quem cria a obra, o IMC
    e o lançamento contábil do reconhecimento da receita."""
    p = Proposta(numero=f'P-{t.marca}', data_proposta=DIA,
                 cliente_nome=f'Cliente {t.marca}', titulo='Obra A03',
                 prazo_entrega_dias=30, valor_total=CONTRATO,
                 status='rascunho', admin_id=t.admin_id)
    db.session.add(p)
    db.session.flush()
    db.session.add(PropostaItem(
        proposta_id=p.id, item_numero=1, descricao='Serviço', quantidade=Decimal('10'),
        unidade='un', preco_unitario=Decimal('100.00'), ordem=1,
        subtotal=CONTRATO, admin_id=t.admin_id))
    db.session.commit()

    EventManager.emit('proposta_aprovada', {
        'proposta_id': p.id,
        'cliente_nome': p.cliente_nome,
        'valor_total': float(CONTRATO),
        'data_aprovacao': DIA.isoformat(),
    }, t.admin_id)
    # O handler não commita: a rota é dona da transação (Task #102).
    db.session.commit()

    db.session.refresh(p)
    obra = db.session.get(Obra, p.obra_id)
    assert obra is not None, 'a aprovação não criou a obra'
    assert obra.proposta_origem_id == p.id, (
        'obra.proposta_origem_id não foi preenchido — é ele que decide a conta '
        'contábil da CR de medição')
    return p, obra


def _mede_metade(obra, admin_id, imcs=None):
    """Tarefa de cronograma a 50%, vinculada aos IMC da obra."""
    imcs = imcs if imcs is not None else ItemMedicaoComercial.query.filter_by(
        obra_id=obra.id, admin_id=admin_id).all()
    assert imcs, 'nenhum ItemMedicaoComercial na obra — nada a medir'

    tarefa = TarefaCronograma(obra_id=obra.id, ordem=1, nome_tarefa='Tarefa A03',
                              duracao_dias=30, percentual_concluido=50.0,
                              admin_id=admin_id)
    db.session.add(tarefa)
    db.session.flush()
    for imc in imcs:
        db.session.add(ItemMedicaoCronogramaTarefa(
            item_medicao_id=imc.id, cronograma_tarefa_id=tarefa.id,
            peso=Decimal('100'), admin_id=admin_id))
    db.session.commit()


def _finaliza_rdo(obra_id, admin_id):
    """O caminho de produção — e nada mais."""
    EventManager.emit('rdo_finalizado', {'obra_id': obra_id}, admin_id)


def _cr_medicao(obra_id, admin_id):
    db.session.expire_all()
    return ContaReceber.query.filter_by(
        admin_id=admin_id, origem_tipo='OBRA_MEDICAO', origem_id=obra_id).first()


def _recebe(t, cr, valor):
    return cliente_de(t.admin_id).post(
        f'/financeiro/contas-receber/{cr.id}/receber',
        data={'valor_recebido': str(valor),
              'data_recebimento': DIA.isoformat(),
              'forma_recebimento': 'PIX'})


def _obra_medida(prefixo):
    """Cenário completo: proposta aprovada, obra a 50%, RDO finalizado."""
    t = um_tenant(prefixo, data_ref=DIA, com_fatos=False)
    _p, obra = _proposta_aprovada(t)
    _mede_metade(obra, t.admin_id)
    _finaliza_rdo(obra.id, t.admin_id)
    cr = _cr_medicao(obra.id, t.admin_id)
    assert cr is not None, (
        'o emit de rdo_finalizado não produziu a ContaReceber OBRA_MEDICAO — '
        'sem ela o resto deste arquivo não tem o que afirmar')
    return t, obra, cr


# ---------------------------------------------------------------------------
# Asserção 1 — a CR nasce apontando para a conta certa, e a conta existe
# ---------------------------------------------------------------------------

def test_cr_de_medicao_nasce_com_a_conta_do_cliente():
    """Obra vinda de proposta ⇒ `1.1.02.001` (Clientes).

    🔬 A segunda asserção não é redundante: a FK de `ContaReceber` é COMPOSTA
    (`admin_id`, `conta_contabil_codigo`) → `plano_contas`. Um código gravado sem
    a linha correspondente **no mesmo tenant** não sobreviveria ao commit — e o
    ponto da Task é que o código só é atribuído depois de confirmado.
    """
    with app.app_context():
        t, _obra, cr = _obra_medida('a03cc')

        assert cr.conta_contabil_codigo == '1.1.02.001', (
            f'a CR de medição nasceu com {cr.conta_contabil_codigo!r}; a receita '
            f'já foi reconhecida na aprovação, então a medição só pode debitar o '
            f'cliente em 1.1.02.001')
        assert PlanoContas.query.filter_by(
            admin_id=t.admin_id, codigo='1.1.02.001').first() is not None, (
            'o código foi gravado sem a conta existir no plano do tenant — a FK '
            'composta não teria deixado, então algo está semeando outro tenant')


# ---------------------------------------------------------------------------
# Asserção 2 — o recebimento gera a partida dobrada, caixa contra cliente
# ---------------------------------------------------------------------------

def test_recebimento_gera_partida_dobrada_de_caixa_contra_cliente():
    """DÉBITO em caixa, CRÉDITO no cliente — e uma só vez."""
    with app.app_context():
        t, _obra, cr = _obra_medida('a03pd')
        assert Decimal(cr.saldo) == MEDIDO, (
            f'saldo da CR veio {cr.saldo}, esperado {MEDIDO} (50% de {CONTRATO})')

        r = _recebe(t, cr, MEDIDO)
        assert r.status_code in (200, 302), f'a rota respondeu {r.status_code}'

        db.session.expire_all()
        lancs = LancamentoContabil.query.filter_by(
            admin_id=t.admin_id, origem='FINANCEIRO_RECEBER', origem_id=cr.id).all()
        assert len(lancs) == 1, (
            f'{len(lancs)} lançamentos FINANCEIRO_RECEBER para um recebimento')

        partidas = PartidaContabil.query.filter_by(
            admin_id=t.admin_id, lancamento_id=lancs[0].id).all()
        assert len(partidas) == 2, f'{len(partidas)} partidas — a dobrada tem duas'

        por_tipo = {p.tipo_partida: p for p in partidas}
        assert por_tipo['DEBITO'].conta_codigo == '1.1.01.001', (
            f"débito foi para {por_tipo['DEBITO'].conta_codigo}, esperado caixa")
        assert por_tipo['CREDITO'].conta_codigo == '1.1.02.001', (
            f"crédito foi para {por_tipo['CREDITO'].conta_codigo}; creditar 4.1.x "
            f"aqui reconheceria a receita uma SEGUNDA vez")
        assert Decimal(por_tipo['DEBITO'].valor) == Decimal(por_tipo['CREDITO'].valor) == MEDIDO, (
            'as duas pernas da partida dobrada não batem entre si')


# ---------------------------------------------------------------------------
# Asserção 3 — o cão de guarda: o recebimento não inventa receita
# ---------------------------------------------------------------------------

def test_o_recebimento_nao_inventa_receita_no_dre():
    """🔴 **A asserção que decide se a conta certa foi escolhida.**

    As duas anteriores continuariam verdes se a CR nascesse com `4.1.01.001`:
    haveria um lançamento, com duas pernas que batem. O que denuncia a conta
    errada é o DRE — creditar receita no recebimento reconheceria a MESMA venda
    duas vezes, e a receita bruta do mês saltaria de 1.000 para 1.500.

    A comparação é antes/depois no mesmo mês de propósito: os dois lançamentos
    (aprovação e recebimento) caem em janeiro/2026, então uma receita inventada
    não teria como se esconder numa competência diferente.
    """
    with app.app_context():
        t, _obra, cr = _obra_medida('a03dre')

        dre_antes = calcular_dre_mensal(t.admin_id, DIA.year, DIA.month)
        receita_antes = Decimal(str(dre_antes['receita_bruta']))
        assert receita_antes == CONTRATO, (
            f'receita bruta antes do recebimento = {receita_antes}, esperado '
            f'{CONTRATO} — o reconhecimento da aprovação é a premissa desta Task')

        r = _recebe(t, cr, MEDIDO)
        assert r.status_code in (200, 302), f'a rota respondeu {r.status_code}'

        dre_depois = calcular_dre_mensal(t.admin_id, DIA.year, DIA.month)
        receita_depois = Decimal(str(dre_depois['receita_bruta']))
        assert receita_depois == CONTRATO, (
            f'a receita bruta foi de {receita_antes} para {receita_depois} com um '
            f'RECEBIMENTO — o dinheiro que entra liquida o cliente, não é venda '
            f'nova. A CR de medição está apontando para uma conta de resultado')


# ---------------------------------------------------------------------------
# Asserção 4 — tenant sem plano: NULL, e a sessão continua utilizável
# ---------------------------------------------------------------------------

def test_tenant_sem_plano_de_contas_fica_null_sem_sujar_a_sessao(monkeypatch, caplog):
    """O modo de falha que a Task existe para evitar.

    Atribuir o código às cegas num tenant sem plano dá `IntegrityError` no commit
    de `recalcular_medicao_obra`. Como o `except` do handler loga sem rollback e o
    `emit` engole, o estrago não apareceria aqui — apareceria depois, nos handlers
    seguintes, com `PendingRollbackError`. Por isso a asserção do meio: uma query
    trivial DEPOIS do emit tem de funcionar.

    O seed é neutralizado para simular o tenant sem plano; a obra é criada sem
    proposta justamente porque a aprovação semearia o plano por outro caminho.
    """
    import contabilidade_utils

    with app.app_context():
        t = um_tenant('a03np', data_ref=DIA, com_fatos=False)
        assert PlanoContas.query.filter_by(admin_id=t.admin_id).count() == 0, (
            'o tenant já nasceu com plano de contas — o cenário desta asserção '
            'deixou de existir e ela passaria por engano')

        monkeypatch.setattr(contabilidade_utils, 'seed_plano_contas_if_needed',
                            lambda admin_id: None)

        obra = db.session.get(Obra, t.obra_id)
        imc = ItemMedicaoComercial(obra_id=obra.id, admin_id=t.admin_id,
                                   nome='Serviço', valor_comercial=CONTRATO)
        db.session.add(imc)
        db.session.flush()
        _mede_metade(obra, t.admin_id, imcs=[imc])

        with caplog.at_level('WARNING'):
            _finaliza_rdo(obra.id, t.admin_id)

        # 1) a sessão sobreviveu ao emit
        assert ContaReceber.query.filter_by(admin_id=t.admin_id).count() >= 0, (
            'a sessão ficou suja depois do emit — é o PendingRollbackError em '
            'cascata que a confirmação em plano_contas existe para evitar')

        # 2) a CR existe e ficou sem conta contábil, em vez de derrubar o commit
        cr = _cr_medicao(obra.id, t.admin_id)
        assert cr is not None, 'a CR de medição não sobreviveu ao tenant sem plano'
        assert cr.conta_contabil_codigo is None, (
            f'a CR levou {cr.conta_contabil_codigo!r} num tenant sem plano de '
            f'contas — a FK composta derrubaria o commit')

        # 3) o silêncio acabou (B3.6): a baixa denuncia a CR fora da contabilidade
        caplog.clear()
        with caplog.at_level('WARNING'):
            _recebe(t, cr, MEDIDO)
        assert any('partida dobrada' in m.lower() for m in caplog.messages), (
            f'a baixa de uma CR sem conta contábil passou calada; '
            f'mensagens: {caplog.messages}')
