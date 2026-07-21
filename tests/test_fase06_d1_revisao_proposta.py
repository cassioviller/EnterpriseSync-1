"""Fase 0.6 / D1 — aprovar revisão de proposta faturava errado.

Reproduzido por execução em 2026-07-21 (v1 R$ 100.000 → v2 R$ 120.000):

    obra.valor_contrato         = 120.000,00   ✔ correto
    ItemMedicaoComercial        = 2 itens, soma 220.000,00
    ObraServicoCusto            = 2 linhas, orçado 220.000,00
    saldo (medicao_views.py:72) = -100.000,00
    receita contábil (4.x CRED) = 220.000,00

Três defeitos independentes empilhados no mesmo fluxo:

**D1a — duplicação.** Criar uma revisão CLONA os `PropostaItem` com ids
novos (`propostas_consolidated.py:1327`). A idempotência de
`_propagar_proposta_para_obra` (`handlers/propostas_handlers.py:36-40`) é
por `proposta_item_id`, então nunca casa com os itens da v1: o handler cria
um segundo conjunto completo de `ItemMedicaoComercial`, e o listener
`after_insert` cria o `ObraServicoCusto` pareado de cada um. Um aditivo de
+20% vira +100% de itens.

**D1b — lançamento pelo valor cheio.** `handle_proposta_aprovada` lança o
`valor_total` da proposta aprovada. Na v2 lança 120.000 outra vez, sobre os
100.000 da v1: receita de 220.000 para um contrato de 120.000. O correto é
lançar o **delta** da linhagem.

**D1c — reprecificação retroativa.** `MedicaoContrato.valor` é property
calculada, `pct × obra.valor_contrato` (`models.py:5652-5655`). Quando
`event_manager.py:1041` atualiza `obra.valor_contrato` pela revisão, toda
medição **já emitida** é reprecificada — inclusive as que o cliente já
pagou. Uma medição de 10% emitida sobre contrato de 100k valia 10.000 e
passa a valer 12.000 retroativamente, sem nenhum registro.

Escopo: as medições ainda NÃO emitidas devem seguir o contrato novo — é o
que um aditivo significa. Só as emitidas (`recebido_no_mes` preenchido)
congelam. O versionamento completo de orçamento e aditivo é a Fase 6.
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
from models import (Cliente, ItemMedicaoComercial, MedicaoContrato, Obra,
                    ObraServicoCusto, PartidaContabil, Proposta, PropostaItem,
                    TipoUsuario, Usuario)

pytestmark = pytest.mark.integration


@pytest.fixture(autouse=True)
def _config():
    app.config['TESTING'] = True
    app.config['WTF_CSRF_ENABLED'] = False
    if not app.secret_key:
        app.secret_key = 'test-fase06-d1'
    yield


@pytest.fixture
def cenario():
    """Admin + cliente + obra sem contrato — o ponto de partida do fluxo."""
    with app.app_context():
        s = uuid.uuid4().hex[:8]
        admin = Usuario(
            username=f'd1_{s}', email=f'd1_{s}@test.local', nome=f'Admin {s}',
            password_hash=generate_password_hash('Senha@2026'),
            tipo_usuario=TipoUsuario.ADMIN, ativo=True, versao_sistema='v2',
        )
        db.session.add(admin)
        db.session.commit()
        cliente = Cliente(nome=f'Cliente {s}', admin_id=admin.id)
        db.session.add(cliente)
        db.session.commit()
        obra = Obra(
            nome=f'Obra {s}', admin_id=admin.id, cliente_id=cliente.id,
            data_inicio=date(2026, 7, 1), valor_contrato=0,
        )
        db.session.add(obra)
        db.session.commit()
        yield {'admin_id': admin.id, 'cliente_id': cliente.id,
               'obra_id': obra.id, 'sufixo': s}


def _proposta(cenario, valor, versao, origem_id=None, itens=None,
              itens_origem=None):
    """Cria proposta com itens. `itens` = [(descricao, valor)].

    `itens_origem` = lista de `PropostaItem.id` da versão anterior, na mesma
    ordem de `itens`. Preenchê-la reproduz o clone REAL
    (`propostas_consolidated.py:1331`, que grava `proposta_item_origem_id`);
    deixá-la vazia reproduz as revisões criadas ANTES da Fase 0.6, que só
    tinham o `item_numero` para casar. Os dois caminhos precisam funcionar.
    """
    pr = Proposta(
        admin_id=cenario['admin_id'], numero=f"P{cenario['sufixo']}-v{versao}",
        cliente_nome=f"Cliente {cenario['sufixo']}",
        cliente_id=cenario['cliente_id'], obra_id=cenario['obra_id'],
        versao=versao, proposta_origem_id=origem_id, valor_total=valor,
        status='RASCUNHO', data_proposta=date(2026, 7, 1),
    )
    db.session.add(pr)
    db.session.flush()
    criados = []
    for n, (descricao, v) in enumerate(itens or [('Serviço X', valor)], start=1):
        item = PropostaItem(
            admin_id=cenario['admin_id'], proposta_id=pr.id, item_numero=n,
            ordem=n, descricao=descricao, quantidade=Decimal('1'), unidade='vb',
            preco_unitario=Decimal(str(v)), subtotal=Decimal(str(v)),
            proposta_item_origem_id=(
                (itens_origem or [None] * n)[n - 1]
                if itens_origem and n <= len(itens_origem) else None
            ),
        )
        db.session.add(item)
        criados.append(item)
    db.session.commit()
    pr._itens_criados = [i.id for i in criados]
    return pr


def _aprovar(cenario, proposta, valor, dia=1):
    from event_manager import EventManager
    EventManager.emit('proposta_aprovada', {
        'proposta_id': proposta.id,
        'cliente_nome': f"Cliente {cenario['sufixo']}",
        'valor_total': valor,
        'data_aprovacao': f'2026-07-{dia:02d}',
    }, admin_id=cenario['admin_id'])
    db.session.commit()
    db.session.expire_all()


def _itens(cenario):
    return ItemMedicaoComercial.query.filter_by(
        obra_id=cenario['obra_id']).all()


def _receita_contabil(cenario):
    """Receita LÍQUIDA — bruta (4.1.x CREDITO) menos deduções (4.2.x DEBITO).

    É a mesma conta que `calcular_dre_mensal` faz (`receita_bruta -
    deducoes`). Medir só o CREDITO em 4.1.x deixaria o estorno invisível, que
    é exatamente por que ele vai para a conta de dedução e não como débito na
    conta de receita.
    """
    def _soma(prefixo, tipo):
        v = db.session.query(db.func.sum(PartidaContabil.valor)).filter(
            PartidaContabil.admin_id == cenario['admin_id'],
            PartidaContabil.tipo_partida == tipo,
            PartidaContabil.conta_codigo.like(f'{prefixo}%'),
        ).scalar()
        return float(v or 0)

    return _soma('4.1', 'CREDITO') - _soma('4.2', 'DEBITO')


# ---------------------------------------------------------------------------
# D1a — a revisão substitui, não acumula
# ---------------------------------------------------------------------------

@pytest.mark.parametrize('com_linhagem', [True, False], ids=[
    'clone-real-com-proposta_item_origem_id', 'revisao-legada-sem-a-coluna'])
def test_revisao_nao_duplica_itens_de_medicao(cenario, com_linhagem):
    """O item da v2 substitui o da v1 — não é somado a ele.

    Roda nos dois modos de propósito: a primeira versão desta correção
    passava sem a linhagem e FALHAVA com ela, porque o item raiz (v1, com
    `proposta_item_origem_id` NULL) e o clone (v2, com a coluna preenchida)
    geravam chaves de tipos diferentes e nunca casavam.
    """
    with app.app_context():
        v1 = _proposta(cenario, 100000, 1)
        _aprovar(cenario, v1, 100000, dia=1)
        assert len(_itens(cenario)) == 1

        v2 = _proposta(cenario, 120000, 2, origem_id=v1.id,
                       itens_origem=v1._itens_criados if com_linhagem else None)
        _aprovar(cenario, v2, 120000, dia=15)

        itens = _itens(cenario)
        assert len(itens) == 1, (
            f'{len(itens)} itens de medição para uma obra de 1 item — '
            f'a revisão duplicou'
        )
        assert float(itens[0].valor_comercial) == 120000.0, (
            'o item ficou com o valor da v1'
        )


def test_saldo_da_obra_nao_fica_negativo_apos_revisao(cenario):
    """A consequência visível: `medicao_views.py:72` mostrava -100.000."""
    with app.app_context():
        v1 = _proposta(cenario, 100000, 1)
        _aprovar(cenario, v1, 100000, dia=1)
        v2 = _proposta(cenario, 120000, 2, origem_id=v1.id)
        _aprovar(cenario, v2, 120000, dia=15)

        obra = db.session.get(Obra, cenario['obra_id'])
        soma_itens = sum(float(i.valor_comercial or 0) for i in _itens(cenario))
        saldo = float(obra.valor_contrato or 0) - soma_itens
        assert saldo == pytest.approx(0.0), (
            f'saldo {saldo:,.2f} — contrato {obra.valor_contrato} × '
            f'itens {soma_itens}'
        )


def test_revisao_nao_duplica_obra_servico_custo(cenario):
    """O `after_insert` de ItemMedicaoComercial cria um OSC pareado.

    Duplicar o item duplicava o custo orçado da obra junto.
    """
    with app.app_context():
        v1 = _proposta(cenario, 100000, 1)
        _aprovar(cenario, v1, 100000, dia=1)
        v2 = _proposta(cenario, 120000, 2, origem_id=v1.id)
        _aprovar(cenario, v2, 120000, dia=15)

        oscs = ObraServicoCusto.query.filter_by(
            obra_id=cenario['obra_id']).all()
        assert len(oscs) <= 1, f'{len(oscs)} linhas de custo para 1 item'


def test_revisao_que_acrescenta_item_cria_so_o_novo(cenario):
    """Aditivo de escopo: v2 mantém o item 1 e acrescenta o item 2."""
    with app.app_context():
        v1 = _proposta(cenario, 100000, 1, itens=[('Fundação', 100000)])
        _aprovar(cenario, v1, 100000, dia=1)

        v2 = _proposta(cenario, 150000, 2, origem_id=v1.id,
                       itens=[('Fundação', 100000), ('Estrutura', 50000)])
        _aprovar(cenario, v2, 150000, dia=15)

        itens = _itens(cenario)
        assert len(itens) == 2, f'{len(itens)} itens — esperado 2'
        assert sum(float(i.valor_comercial) for i in itens) == 150000.0


def test_aprovar_a_mesma_proposta_duas_vezes_continua_idempotente(cenario):
    """A idempotência que já existia não pode ter sido perdida."""
    with app.app_context():
        v1 = _proposta(cenario, 100000, 1)
        _aprovar(cenario, v1, 100000, dia=1)
        _aprovar(cenario, v1, 100000, dia=1)

        assert len(_itens(cenario)) == 1


# ---------------------------------------------------------------------------
# D1b — o lançamento contábil é do delta, não do valor cheio
# ---------------------------------------------------------------------------

def test_receita_contabil_da_revisao_e_o_delta(cenario):
    """v1 100k + v2 120k tem que dar 120k de receita, não 220k."""
    with app.app_context():
        v1 = _proposta(cenario, 100000, 1)
        _aprovar(cenario, v1, 100000, dia=1)
        assert _receita_contabil(cenario) == pytest.approx(100000.0)

        v2 = _proposta(cenario, 120000, 2, origem_id=v1.id)
        _aprovar(cenario, v2, 120000, dia=15)

        assert _receita_contabil(cenario) == pytest.approx(120000.0), (
            'a receita saiu pelo valor cheio da revisão em vez do delta'
        )


def test_revisao_para_baixo_estorna(cenario):
    """Aditivo negativo: v2 de 80k sobre v1 de 100k → receita final 80k."""
    with app.app_context():
        v1 = _proposta(cenario, 100000, 1)
        _aprovar(cenario, v1, 100000, dia=1)

        v2 = _proposta(cenario, 80000, 2, origem_id=v1.id)
        _aprovar(cenario, v2, 80000, dia=15)

        assert _receita_contabil(cenario) == pytest.approx(80000.0)


def test_revisao_sem_mudanca_de_valor_nao_lanca_nada(cenario):
    """Revisar cláusulas sem mexer no preço não movimenta a contabilidade."""
    with app.app_context():
        v1 = _proposta(cenario, 100000, 1)
        _aprovar(cenario, v1, 100000, dia=1)
        lanc_antes = PartidaContabil.query.filter_by(
            admin_id=cenario['admin_id']).count()

        v2 = _proposta(cenario, 100000, 2, origem_id=v1.id)
        _aprovar(cenario, v2, 100000, dia=15)

        assert PartidaContabil.query.filter_by(
            admin_id=cenario['admin_id']).count() == lanc_antes
        assert _receita_contabil(cenario) == pytest.approx(100000.0)


# ---------------------------------------------------------------------------
# D1c — medição já emitida não é reprecificada
# ---------------------------------------------------------------------------

def test_medicao_ja_emitida_nao_e_reprecificada_pela_revisao(cenario):
    """A medição que o cliente já recebeu vale o que valia quando foi emitida."""
    with app.app_context():
        v1 = _proposta(cenario, 100000, 1)
        _aprovar(cenario, v1, 100000, dia=1)

        emitida = MedicaoContrato(
            obra_id=cenario['obra_id'], admin_id=cenario['admin_id'],
            nome='1ª medição', data=date(2026, 7, 5), pct=Decimal('0.10'),
            recebido_no_mes='07/2026',
        )
        pendente = MedicaoContrato(
            obra_id=cenario['obra_id'], admin_id=cenario['admin_id'],
            nome='2ª medição', data=date(2026, 8, 5), pct=Decimal('0.10'),
        )
        db.session.add_all([emitida, pendente])
        db.session.commit()
        assert float(emitida.valor) == pytest.approx(10000.0)

        v2 = _proposta(cenario, 120000, 2, origem_id=v1.id)
        _aprovar(cenario, v2, 120000, dia=15)

        db.session.expire_all()
        emitida = db.session.get(MedicaoContrato, emitida.id)
        pendente = db.session.get(MedicaoContrato, pendente.id)

        assert float(emitida.valor) == pytest.approx(10000.0), (
            'medição já recebida foi reprecificada pelo aditivo'
        )
        assert float(pendente.valor) == pytest.approx(12000.0), (
            'medição ainda não emitida deveria seguir o contrato novo — '
            'é o que um aditivo significa'
        )
