"""A requisição rejeitada volta a ser corrigível — os dois becos de 17/08.

Achados na conferência do fluxo de compras ponta a ponta e registrados no
"Fora de escopo" do spec `2026-08-17-nota-e-liberacao-design.md`:

1. **`REJEITADA` não tinha volta pela tela.** Três camadas discordavam:
   `services/requisicao_compra.py` PERMITE `REJEITADA → RASCUNHO` com o
   desenho explicado por escrito (*"rejeitar não é matar. O gestor rejeita
   '3 chapas é pouco, peça 5'; o solicitante corrige e reenvia"*);
   `models.py` dizia que REJEITADA era **terminal**; e o template só oferecia
   "Cancelar". Quem mandava era o template.

2. **Não havia como editar item de requisição.** `RequisicaoCompraItem` só
   nascia dentro do `nova_post` — nem em RASCUNHO dava para acrescentar,
   corrigir ou remover.

Os dois são uma coisa só: ligar a volta sem a edição devolveria a requisição a
um estado que ninguém consegue mudar. O caminho já era esperado pelo resto do
sistema — 📖 `_inicio_da_rodada_atual` (services/alcada_compras.py) cita
`REJEITADA→RASCUNHO→AGUARDANDO` e escopa os votos à rodada nova justamente
para que a reenviada não feche a alçada com votos velhos.

Molde de tests/test_fase3_requisicao.py.
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
from models import (Cliente, EstadoRequisicao, Obra, RequisicaoCompra,
                    RequisicaoCompraItem, TipoUsuario, Usuario)

pytestmark = pytest.mark.integration


@pytest.fixture(autouse=True)
def _config():
    app.config['TESTING'] = True
    app.config['WTF_CSRF_ENABLED'] = False
    if not app.secret_key:
        app.secret_key = 'test-requisicao-correcao'
    yield


def _admin():
    suf = uuid.uuid4().hex[:8]
    u = Usuario(
        username=f'rc_{suf}', email=f'rc_{suf}@test.local', nome=f'Adm {suf}',
        password_hash=generate_password_hash('Senha@2026'),
        tipo_usuario=TipoUsuario.ADMIN, ativo=True, versao_sistema='v2')
    db.session.add(u)
    db.session.commit()
    return u


def _obra(admin_id):
    suf = uuid.uuid4().hex[:8]
    cliente = Cliente(nome=f'Cliente {suf}', admin_id=admin_id)
    db.session.add(cliente)
    db.session.commit()
    o = Obra(nome=f'Obra {suf}', codigo=f'O{suf[:6].upper()}',
             data_inicio=date(2026, 1, 1), admin_id=admin_id,
             cliente_id=cliente.id, ativo=True)
    db.session.add(o)
    db.session.commit()
    return o


def _requisicao(admin_id, obra_id, usuario_id, estado=EstadoRequisicao.RASCUNHO):
    from services.requisicao_compra import recalcular_valor
    req = RequisicaoCompra(
        numero=f'RC-2026-{uuid.uuid4().hex[:4].upper()}', admin_id=admin_id,
        obra_id=obra_id, solicitante_id=usuario_id, estado=estado,
        valor_estimado=Decimal('0'), justificativa='Reposição de estoque')
    db.session.add(req)
    db.session.commit()
    db.session.add(RequisicaoCompraItem(
        requisicao_id=req.id, admin_id=admin_id, descricao='Chapa 3mm',
        unidade='un', quantidade=3, preco_estimado=100))
    db.session.commit()
    recalcular_valor(req)
    db.session.commit()
    return req


def _flashes(cli):
    with cli.session_transaction() as s:
        return ' | '.join(m for _cat, m in s.get('_flashes', []))


# ---------------------------------------------------------------------------
# R1 — a volta de REJEITADA para RASCUNHO
# ---------------------------------------------------------------------------

def test_o_modelo_nao_pode_dizer_que_rejeitada_e_terminal():
    """As três camadas passam a dizer a mesma coisa.

    O docstring do enum afirmava "Terminais: REJEITADA, CONVERTIDA e
    CANCELADA" enquanto a máquina de estados permitia REJEITADA → RASCUNHO.
    Documentação que contradiz o código é pior que documentação ausente: quem
    lê o modelo para decidir se precisa de uma rota conclui que não precisa.
    """
    from services.requisicao_compra import TRANSICOES_VALIDAS
    doc = EstadoRequisicao.__doc__ or ''

    assert TRANSICOES_VALIDAS[EstadoRequisicao.REJEITADA], (
        'a máquina deixou de permitir a volta — se foi de propósito, o teste '
        'é o lugar de registrar a decisão')
    assert 'Terminais: REJEITADA' not in doc, (
        'o docstring do enum voltou a chamar REJEITADA de terminal, e ela '
        'não é: de REJEITADA se volta para RASCUNHO')


def test_rejeitada_volta_para_rascunho_pela_tela():
    from helpers_tenant import cliente_de
    from services.requisicao_compra import transicionar
    with app.app_context():
        adm = _admin()
        obra = _obra(adm.id)
        req = _requisicao(adm.id, obra.id, adm.id,
                          estado=EstadoRequisicao.AGUARDANDO_APROVACAO)
        transicionar(req, EstadoRequisicao.REJEITADA, adm,
                     motivo='3 chapas é pouco, peça 5')
        db.session.commit()
        adm_id, req_id = adm.id, req.id

    resposta = cliente_de(adm_id).post(f'/compras/requisicoes/{req_id}/corrigir')

    assert resposta.status_code == 302
    with app.app_context():
        assert db.session.get(
            RequisicaoCompra, req_id).estado == EstadoRequisicao.RASCUNHO


def test_a_volta_fica_na_trilha_com_autor():
    """Rejeitar e corrigir são dois momentos, e o histórico guarda os dois."""
    from helpers_tenant import cliente_de
    from models import RequisicaoTransicao
    from services.requisicao_compra import transicionar
    with app.app_context():
        adm = _admin()
        obra = _obra(adm.id)
        req = _requisicao(adm.id, obra.id, adm.id,
                          estado=EstadoRequisicao.AGUARDANDO_APROVACAO)
        transicionar(req, EstadoRequisicao.REJEITADA, adm, motivo='pouco')
        db.session.commit()
        adm_id, req_id = adm.id, req.id

    cliente_de(adm_id).post(f'/compras/requisicoes/{req_id}/corrigir')

    with app.app_context():
        volta = (RequisicaoTransicao.query
                 .filter_by(requisicao_id=req_id,
                            de_estado=EstadoRequisicao.REJEITADA,
                            para_estado=EstadoRequisicao.RASCUNHO)
                 .first())
        assert volta is not None, 'a volta não deixou rastro'
        assert volta.usuario_id == adm_id


def test_nao_se_corrige_requisicao_que_nao_foi_rejeitada():
    """A máquina já recusaria; a rota recusa ANTES, com a razão dita.

    Deixar `TransicaoInvalida` subir daria 500 numa ação que o usuário pode
    disparar clicando duas vezes.
    """
    from helpers_tenant import cliente_de
    with app.app_context():
        adm = _admin()
        obra = _obra(adm.id)
        req = _requisicao(adm.id, obra.id, adm.id)   # RASCUNHO
        adm_id, req_id = adm.id, req.id

    cli = cliente_de(adm_id)
    resposta = cli.post(f'/compras/requisicoes/{req_id}/corrigir')

    assert resposta.status_code == 302, 'não pode virar 500'
    with app.app_context():
        assert db.session.get(
            RequisicaoCompra, req_id).estado == EstadoRequisicao.RASCUNHO


# ---------------------------------------------------------------------------
# R2 — editar os itens em RASCUNHO
# ---------------------------------------------------------------------------

def test_editar_itens_substitui_e_recalcula_o_valor():
    """O valor é a base da alçada — item mexido sem recálculo cai na faixa
    errada, e é o que a docstring de `recalcular_valor` já avisava."""
    from helpers_tenant import cliente_de
    with app.app_context():
        adm = _admin()
        obra = _obra(adm.id)
        req = _requisicao(adm.id, obra.id, adm.id)
        assert Decimal(str(req.valor_estimado)) == Decimal('300.00')
        adm_id, req_id = adm.id, req.id

    resposta = cliente_de(adm_id).post(
        f'/compras/requisicoes/{req_id}/itens',
        data={'item_descricao[]': ['Chapa 3mm', 'Eletrodo'],
              'item_unidade[]': ['un', 'kg'],
              'item_quantidade[]': ['5', '2'],
              'item_preco[]': ['100', '50']})

    assert resposta.status_code == 302
    with app.app_context():
        req = db.session.get(RequisicaoCompra, req_id)
        itens = RequisicaoCompraItem.query.filter_by(
            requisicao_id=req_id).order_by(RequisicaoCompraItem.id).all()
        assert len(itens) == 2
        assert Decimal(str(req.valor_estimado)) == Decimal('600.00'), (
            '5×100 + 2×50 = 600 — o valor não acompanhou os itens')


def test_editar_itens_so_vale_em_rascunho():
    """Mexer em item de requisição já enviada mudaria o valor debaixo de quem
    está aprovando — e a alçada foi calculada sobre o valor de então."""
    from helpers_tenant import cliente_de
    with app.app_context():
        adm = _admin()
        obra = _obra(adm.id)
        req = _requisicao(adm.id, obra.id, adm.id,
                          estado=EstadoRequisicao.AGUARDANDO_APROVACAO)
        adm_id, req_id = adm.id, req.id

    cli = cliente_de(adm_id)
    resposta = cli.post(f'/compras/requisicoes/{req_id}/itens',
                        data={'item_descricao[]': ['Outro'],
                              'item_unidade[]': ['un'],
                              'item_quantidade[]': ['99'],
                              'item_preco[]': ['999']})

    assert resposta.status_code == 302
    with app.app_context():
        req = db.session.get(RequisicaoCompra, req_id)
        assert Decimal(str(req.valor_estimado)) == Decimal('300.00'), (
            'o valor mudou numa requisição que já estava em aprovação')


def test_requisicao_sem_item_nenhum_e_recusada():
    """Requisição vazia não pode existir: a guarda do envio já a recusaria, e
    deixar a edição zerar os itens criaria uma requisição impossível de
    enviar e sem como voltar atrás."""
    from helpers_tenant import cliente_de
    with app.app_context():
        adm = _admin()
        obra = _obra(adm.id)
        req = _requisicao(adm.id, obra.id, adm.id)
        adm_id, req_id = adm.id, req.id

    cli = cliente_de(adm_id)
    resposta = cli.post(f'/compras/requisicoes/{req_id}/itens',
                        data={'item_descricao[]': [''],
                              'item_unidade[]': ['un'],
                              'item_quantidade[]': ['1'],
                              'item_preco[]': ['0']})

    assert resposta.status_code == 302
    with app.app_context():
        assert RequisicaoCompraItem.query.filter_by(
            requisicao_id=req_id).count() == 1, 'os itens foram apagados'


def test_itens_de_outro_tenant_dao_404():
    from helpers_tenant import cliente_de
    with app.app_context():
        adm_a = _admin()
        obra = _obra(adm_a.id)
        req = _requisicao(adm_a.id, obra.id, adm_a.id)
        req_id = req.id
        adm_b_id = _admin().id

    assert cliente_de(adm_b_id).post(
        f'/compras/requisicoes/{req_id}/itens',
        data={'item_descricao[]': ['x'], 'item_unidade[]': ['un'],
              'item_quantidade[]': ['1'], 'item_preco[]': ['1']}
    ).status_code == 404


# ---------------------------------------------------------------------------
# O ciclo que os dois juntos destravam
# ---------------------------------------------------------------------------

def test_rejeitar_corrigir_e_reenviar_abre_rodada_nova():
    """O ciclo inteiro que o desenho previa e que ninguém conseguia executar.

    E o detalhe que torna isto seguro: 📖 `_inicio_da_rodada_atual` escopa os
    votos à entrada REAL em AGUARDANDO, então a requisição reenviada **não**
    herda as aprovações da rodada anterior. Era o achado nº 2 da revisão de
    23/07, e ele já estava consertado antes de existir caminho para chegar
    aqui.
    """
    from helpers_tenant import cliente_de
    from services.alcada_compras import votos_de_aprovacao
    from services.requisicao_compra import transicionar
    with app.app_context():
        adm = _admin()
        obra = _obra(adm.id)
        req = _requisicao(adm.id, obra.id, adm.id,
                          estado=EstadoRequisicao.AGUARDANDO_APROVACAO)
        transicionar(req, EstadoRequisicao.REJEITADA, adm,
                     motivo='3 chapas é pouco, peça 5')
        db.session.commit()
        adm_id, req_id = adm.id, req.id

    cli = cliente_de(adm_id)
    cli.post(f'/compras/requisicoes/{req_id}/corrigir')
    cli.post(f'/compras/requisicoes/{req_id}/itens',
             data={'item_descricao[]': ['Chapa 3mm'],
                   'item_unidade[]': ['un'],
                   'item_quantidade[]': ['5'],
                   'item_preco[]': ['100']})
    cli.post(f'/compras/requisicoes/{req_id}/enviar')

    with app.app_context():
        req = db.session.get(RequisicaoCompra, req_id)
        assert req.estado == EstadoRequisicao.AGUARDANDO_APROVACAO
        assert Decimal(str(req.valor_estimado)) == Decimal('500.00')
        assert votos_de_aprovacao(req) == [], (
            'a rodada nova herdou votos da anterior')


# ---------------------------------------------------------------------------
# As telas OFERECEM as duas ações
# ---------------------------------------------------------------------------
#
# Rota sem botão é exatamente o defeito que esta rodada conserta: a aresta
# REJEITADA→RASCUNHO existia na máquina, tinha teste de serviço, e não tinha
# tela. Testar só a rota repetiria o erro num nível acima.

def test_a_tela_da_rejeitada_oferece_a_volta():
    from helpers_tenant import cliente_de
    from services.requisicao_compra import transicionar
    with app.app_context():
        adm = _admin()
        obra = _obra(adm.id)
        req = _requisicao(adm.id, obra.id, adm.id,
                          estado=EstadoRequisicao.AGUARDANDO_APROVACAO)
        transicionar(req, EstadoRequisicao.REJEITADA, adm, motivo='pouco')
        db.session.commit()
        adm_id, req_id = adm.id, req.id

    resposta = cliente_de(adm_id).get(f'/compras/requisicoes/{req_id}')

    assert resposta.status_code == 200
    corpo = resposta.get_data(as_text=True)
    assert 'Voltar para correção' in corpo, (
        'a rejeitada continua com "Cancelar" como única saída')
    assert f'/requisicoes/{req_id}/corrigir' in corpo


def test_a_tela_do_rascunho_oferece_a_correcao_dos_itens():
    from helpers_tenant import cliente_de
    with app.app_context():
        adm = _admin()
        obra = _obra(adm.id)
        req = _requisicao(adm.id, obra.id, adm.id)
        adm_id, req_id = adm.id, req.id

    resposta = cliente_de(adm_id).get(f'/compras/requisicoes/{req_id}')

    assert resposta.status_code == 200
    corpo = resposta.get_data(as_text=True)
    assert 'Corrigir itens' in corpo
    assert 'Chapa 3mm' in corpo, 'o item existente não veio preenchido no form'


def test_a_tela_da_enviada_nao_oferece_a_correcao_dos_itens():
    """O valor não pode mudar debaixo de quem está aprovando."""
    from helpers_tenant import cliente_de
    with app.app_context():
        adm = _admin()
        obra = _obra(adm.id)
        req = _requisicao(adm.id, obra.id, adm.id,
                          estado=EstadoRequisicao.AGUARDANDO_APROVACAO)
        adm_id, req_id = adm.id, req.id

    corpo = cliente_de(adm_id).get(
        f'/compras/requisicoes/{req_id}').get_data(as_text=True)

    assert 'Corrigir itens' not in corpo
