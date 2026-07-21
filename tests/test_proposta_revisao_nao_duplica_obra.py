"""Fase 0 / R1 — revisar proposta aprovada NÃO pode criar uma segunda obra.

Cenário real: o cliente pede uma mudança, a Veks revisa a proposta (o
sistema obriga criar nova versão — `propostas_consolidated.py:1224`) e
aprova. Antes desta correção, `criar_nova_versao` não copiava `obra_id`,
então `propagar_proposta_para_obra` não achava a obra (procura por
`proposta.obra_id` e por `proposta_origem_id == id_da_v2`, mas a obra
aponta para a v1), caía no ramo de criação e nascia uma SEGUNDA obra com
novo código OBR####, replicando itens de medição e custos.

Dois caminhos cobertos:
  A. v2 criada DEPOIS da correção — herda `obra_id`.
  B. v2 já existente no banco SEM `obra_id` (gravada antes da correção) —
     a guarda de cadeia de versões em `event_manager` a reconcilia.
"""
import os
import sys
import uuid
from datetime import date, datetime
from decimal import Decimal

import pytest
from werkzeug.security import generate_password_hash

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import main  # noqa: F401 — registra blueprints e handlers de evento
from app import app, db
from event_manager import EventManager
from models import (
    Cliente,
    ItemMedicaoComercial,
    Obra,
    Proposta,
    PropostaItem,
    TipoUsuario,
    Usuario,
)

pytestmark = pytest.mark.integration


@pytest.fixture(autouse=True)
def _config():
    app.config['TESTING'] = True
    app.config['WTF_CSRF_ENABLED'] = False
    if not app.secret_key:
        app.secret_key = 'test-revisao-obra'
    yield


def _ambiente():
    """Admin + cliente + proposta v1 APROVADA (com obra já criada)."""
    suf = uuid.uuid4().hex[:8]
    admin = Usuario(
        username=f'r1_{suf}', email=f'r1_{suf}@test.local',
        nome=f'Admin R1 {suf}',
        password_hash=generate_password_hash('Senha@2026'),
        tipo_usuario=TipoUsuario.ADMIN, ativo=True, versao_sistema='v2',
    )
    db.session.add(admin)
    db.session.flush()
    cliente = Cliente(admin_id=admin.id, nome=f'Cliente {suf}',
                      email=f'cli_{suf}@test.local', telefone='11988887777')
    db.session.add(cliente)
    db.session.flush()

    v1 = Proposta(
        admin_id=admin.id,
        numero=f'R1-{suf}',
        titulo=f'Galpão {suf}',
        cliente_id=cliente.id,
        cliente_nome=cliente.nome,
        valor_total=Decimal('100000.00'),
        status='enviada',
        versao=1,
    )
    db.session.add(v1)
    db.session.flush()
    db.session.add(PropostaItem(
        proposta_id=v1.id, admin_id=admin.id, item_numero=1,
        descricao='Estrutura metálica', quantidade=Decimal('1'), unidade='vb',
        preco_unitario=Decimal('100000.00'), subtotal=Decimal('100000.00')))
    db.session.commit()
    return admin, cliente, v1


def _aprovar(proposta, admin_id):
    """Dispara o fluxo real de aprovação (mesmo evento das rotas)."""
    proposta.status = 'aprovada'
    db.session.commit()
    EventManager.emit('proposta_aprovada', {
        'proposta_id': proposta.id,
        'admin_id': admin_id,
        'cliente_nome': proposta.cliente_nome,
        'valor_total': float(proposta.valor_total or 0),
        'data_aprovacao': date.today().isoformat(),
    }, admin_id)
    db.session.commit()


def _clonar_como_revisao(origem, admin_id, herdar_obra: bool):
    """Reproduz o essencial de `criar_nova_versao`.

    `herdar_obra=False` simula uma revisão gravada ANTES da correção — é o
    estoque que já existe no banco.
    """
    nova = Proposta(
        admin_id=admin_id,
        numero=f'{origem.numero}-v2',
        titulo=origem.titulo,
        cliente_id=origem.cliente_id,
        cliente_nome=origem.cliente_nome,
        valor_total=Decimal('120000.00'),   # aditivo: valor sobe
        status='rascunho',
        versao=(origem.versao or 1) + 1,
        proposta_origem_id=origem.id,
        obra_id=origem.obra_id if herdar_obra else None,
    )
    db.session.add(nova)
    db.session.flush()
    db.session.add(PropostaItem(
        proposta_id=nova.id, admin_id=admin_id, item_numero=1,
        descricao='Estrutura metálica (revisada)', quantidade=Decimal('1'),
        unidade='vb',
        preco_unitario=Decimal('120000.00'), subtotal=Decimal('120000.00')))
    db.session.commit()
    return nova


def _obras_do_tenant(admin_id):
    return Obra.query.filter_by(admin_id=admin_id).all()


# ---------------------------------------------------------------------------

def test_aprovar_revisao_nao_cria_segunda_obra():
    """Caminho A — revisão criada depois da correção (herda obra_id)."""
    with app.app_context():
        admin, _cliente, v1 = _ambiente()
        admin_id = admin.id

        _aprovar(v1, admin_id)
        obras = _obras_do_tenant(admin_id)
        assert len(obras) == 1, 'v1 aprovada deve criar exatamente 1 obra'
        obra_id, codigo = obras[0].id, obras[0].codigo

        v2 = _clonar_como_revisao(v1, admin_id, herdar_obra=True)
        _aprovar(v2, admin_id)

        obras_depois = _obras_do_tenant(admin_id)
        assert len(obras_depois) == 1, (
            f'aprovar a revisão duplicou a obra: '
            f'{[o.codigo for o in obras_depois]}')
        assert obras_depois[0].id == obra_id
        assert obras_depois[0].codigo == codigo
        db.session.refresh(v2)
        assert v2.obra_id == obra_id


def test_revisao_legada_sem_obra_id_e_reconciliada_pela_cadeia():
    """Caminho B — v2 já gravada sem obra_id (antes da correção).

    A guarda de cadeia em `propagar_proposta_para_obra` sobe por
    `proposta_origem_id` até achar a obra do ancestral.
    """
    with app.app_context():
        admin, _cliente, v1 = _ambiente()
        admin_id = admin.id

        _aprovar(v1, admin_id)
        obra_id = _obras_do_tenant(admin_id)[0].id

        v2 = _clonar_como_revisao(v1, admin_id, herdar_obra=False)
        assert v2.obra_id is None, 'o cenário exige a v2 órfã'
        _aprovar(v2, admin_id)

        obras_depois = _obras_do_tenant(admin_id)
        assert len(obras_depois) == 1, (
            f'revisão legada duplicou a obra: '
            f'{[o.codigo for o in obras_depois]}')
        db.session.refresh(v2)
        assert v2.obra_id == obra_id, 'a v2 deve ficar ligada à obra existente'


def test_cadeia_de_tres_versoes_converge_na_mesma_obra():
    with app.app_context():
        admin, _cliente, v1 = _ambiente()
        admin_id = admin.id

        _aprovar(v1, admin_id)
        obra_id = _obras_do_tenant(admin_id)[0].id

        v2 = _clonar_como_revisao(v1, admin_id, herdar_obra=False)
        _aprovar(v2, admin_id)
        v3 = _clonar_como_revisao(v2, admin_id, herdar_obra=False)
        _aprovar(v3, admin_id)

        assert len(_obras_do_tenant(admin_id)) == 1
        db.session.refresh(v3)
        assert v3.obra_id == obra_id


def test_itens_de_medicao_nao_sao_replicados_em_obra_nova():
    """O dano colateral da duplicação: IMC/OSC replicados numa obra fantasma."""
    with app.app_context():
        admin, _cliente, v1 = _ambiente()
        admin_id = admin.id

        _aprovar(v1, admin_id)
        obra_id = _obras_do_tenant(admin_id)[0].id

        v2 = _clonar_como_revisao(v1, admin_id, herdar_obra=True)
        _aprovar(v2, admin_id)

        # Todos os itens de medição do tenant pertencem à ÚNICA obra.
        imcs = ItemMedicaoComercial.query.filter_by(admin_id=admin_id).all()
        assert imcs, 'a propagação deve ter criado itens de medição'
        assert {i.obra_id for i in imcs} == {obra_id}


def test_aprovar_revisao_atualiza_valor_de_contrato():
    """O critério do R1 que faltava: a obra existente reflete a revisão.

    Não basta parar de duplicar — se o aditivo sobe o valor e a obra fica no
    valor da v1, todo o faturamento sai errado
    (`MedicaoContrato.valor = pct × obra.valor_contrato`).
    """
    with app.app_context():
        admin, _cliente, v1 = _ambiente()
        admin_id = admin.id

        _aprovar(v1, admin_id)
        obra = _obras_do_tenant(admin_id)[0]
        assert float(obra.valor_contrato) == 100000.0, (
            f'v1 deveria fixar o contrato em 100k, veio {obra.valor_contrato}')
        obra_id = obra.id

        # v2 é o aditivo: 100k → 120k
        v2 = _clonar_como_revisao(v1, admin_id, herdar_obra=True)
        _aprovar(v2, admin_id)

        db.session.expire_all()
        obra = db.session.get(Obra, obra_id)
        assert float(obra.valor_contrato) == 120000.0, (
            f'aprovar o aditivo não atualizou o valor de contrato: '
            f'ficou em {obra.valor_contrato}')


def test_rota_real_de_nova_versao_herda_obra_id():
    """Exercita `criar_nova_versao` DE VERDADE (POST /propostas/<id>/nova-versao).

    Os testes acima montam a revisão à mão e cobrem a guarda do
    `event_manager`; este cobre a outra metade da correção — a rota que
    clona a proposta precisa copiar `obra_id`, senão toda revisão criada
    pela UI nasce órfã.
    """
    with app.app_context():
        admin, _cliente, v1 = _ambiente()
        admin_id = admin.id
        _aprovar(v1, admin_id)
        obra_id = _obras_do_tenant(admin_id)[0].id
        v1_id = v1.id
        db.session.refresh(v1)
        assert v1.obra_id == obra_id

    c = app.test_client()
    with c.session_transaction() as sess:
        sess['_user_id'] = str(admin_id)
        sess['_fresh'] = True
    r = c.post(f'/propostas/{v1_id}/nova-versao', follow_redirects=False)
    assert r.status_code in (200, 302), r.get_data(as_text=True)[:400]

    with app.app_context():
        v2 = (Proposta.query
              .filter_by(admin_id=admin_id, proposta_origem_id=v1_id)
              .first())
        assert v2 is not None, 'a rota deveria ter criado a revisão'
        assert v2.versao == 2
        assert v2.obra_id == obra_id, (
            'revisão criada pela rota nasceu órfã — é o bug R1')


def test_proposta_sem_ancestral_segue_criando_a_obra():
    """Guarda de não-regressão: proposta nova (sem cadeia) cria obra normalmente."""
    with app.app_context():
        admin, _cliente, v1 = _ambiente()
        admin_id = admin.id
        assert _obras_do_tenant(admin_id) == []

        _aprovar(v1, admin_id)
        obras = _obras_do_tenant(admin_id)
        assert len(obras) == 1
        assert obras[0].proposta_origem_id == v1.id
