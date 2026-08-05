"""Arreio: aprovação de proposta por ROTA — congelar o que hoje funciona.

Task B0.5 do `docs/superpowers/plans/2026-08-04-plano-consolidado.md`.

**Por que vale.** É a única superfície do arreio onde o dinheiro hoje **chega**
no caminho principal. Cobrir serve para congelar o que funciona antes de B3
mexer no branch de valor zero — e o caminho de valor zero é o mesmo que
``services/importacao_fisico_financeiro.py:572-578`` usa com
``skip_contabil=True``, então cobri-lo pela rota cobre a importação de graça,
sem montar planilha.

**A diferença deste arquivo para `tests/test_p5_aprovacao_semeia_obra.py`.**
Aquele chama ``_semear_servicos_reais(p.id, admin_id)`` **direto**
(`tests/test_p5_aprovacao_semeia_obra.py:88`). Chamar a função prova que a
função funciona; não prova que a rota a alcança. E o terceiro caminho do
handler (`handlers/propostas_handlers.py:378-385`) dá ``return`` **antes** de
chamar qualquer uma das duas — defeito invisível para quem testa por dentro.

**Cuidado de transação.** As duas rotas são donas da transação e emitem com
``raise_on_error=True`` (`propostas_consolidated.py:2360-2371` e `:2540-2551`):
exceção em handler faz rollback TOTAL e a rota devolve 302 com flash de erro.
``assert status_code == 302`` não prova nada — só o banco prova.
"""
import os
import sys
from datetime import date
from decimal import Decimal
from uuid import uuid4

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import main  # noqa: F401 — registra os blueprints antes de qualquer request
from app import app, db
from models import (ItemMedicaoComercial, LancamentoContabil, Obra, Proposta,
                    PropostaItem, Servico, ServicoObraReal)

from helpers_tenant import cliente_de, um_tenant

pytestmark = pytest.mark.integration


@pytest.fixture(autouse=True)
def _config():
    app.config['TESTING'] = True
    app.config['WTF_CSRF_ENABLED'] = False
    if not app.secret_key:
        app.secret_key = 'test-arreio-proposta'
    yield


def _servico(tenant, nome):
    s = Servico(nome=f'{nome} {tenant.marca}', admin_id=tenant.admin_id,
                ativo=True, unidade_medida='m2', categoria='estrutural')
    db.session.add(s)
    db.session.flush()
    return s


def _proposta(tenant, valor_item=Decimal('1000'), n_itens=2):
    """Proposta SEM ``obra_id`` — para que a aprovação materialize a obra.

    ``valor_item=0`` é o cenário do branch de valor zero, o mesmo que a
    importação físico-financeira percorre.
    """
    servicos = [_servico(tenant, f'Servico{i}') for i in range(n_itens)]
    total = valor_item * n_itens
    p = Proposta(numero=f'ARR-{uuid4().hex[:8]}', admin_id=tenant.admin_id,
                 cliente_id=tenant.cliente_id,
                 cliente_nome=f'Cliente {tenant.marca}',
                 data_proposta=date(2026, 6, 1), versao=1,
                 titulo='Proposta do arreio', status='Enviada',
                 valor_total=total,
                 token_cliente=f'tok{uuid4().hex[:20]}')
    db.session.add(p)
    db.session.flush()
    for i, s in enumerate(servicos, start=1):
        db.session.add(PropostaItem(
            proposta_id=p.id, admin_id=tenant.admin_id, item_numero=i,
            descricao=f'Item {i}', quantidade=Decimal('10'), unidade='m2',
            preco_unitario=valor_item / 10 if valor_item else Decimal('0'),
            servico_id=s.id, ordem=i, subtotal=valor_item))
    db.session.commit()
    return p


def _aprovar(tenant, proposta):
    cli = cliente_de(tenant.admin_id)
    resposta = cli.post(f'/propostas/aprovar/{proposta.id}', data={})
    assert resposta.status_code in (200, 302), (
        f'rota de aprovação respondeu {resposta.status_code}')
    return resposta


def _obra_da_proposta(tenant, proposta):
    db.session.expire_all()
    p = Proposta.query.get(proposta.id)
    if not p or not p.obra_id:
        return None
    return Obra.query.filter_by(id=p.obra_id, admin_id=tenant.admin_id).first()


def _reais(obra, tenant):
    db.session.expire_all()
    return ServicoObraReal.query.filter_by(
        obra_id=obra.id, admin_id=tenant.admin_id).all()


def _lancamentos(tenant, valor):
    db.session.expire_all()
    return LancamentoContabil.query.filter_by(
        admin_id=tenant.admin_id, valor_total=valor).all()


# ---------------------------------------------------------------------------
# (a) — o caminho principal, congelado
# ---------------------------------------------------------------------------

def test_aprovar_proposta_com_valor_materializa_a_obra_inteira():
    """O piso: a aprovação pela ROTA cria obra, itens de medição e serviços reais.

    Se este quebrar, B3 não deve encostar em `handlers/propostas_handlers.py`
    até se entender o porquê.
    """
    with app.app_context():
        tenant = um_tenant('aprova', com_fatos=False)
        proposta = _proposta(tenant, valor_item=Decimal('1000'), n_itens=2)

        _aprovar(tenant, proposta)

        obra = _obra_da_proposta(tenant, proposta)
        assert obra is not None, 'a aprovação não materializou a obra'

        imc = ItemMedicaoComercial.query.filter_by(
            obra_id=obra.id, admin_id=tenant.admin_id).all()
        assert len(imc) == 2, f'esperava 2 itens de medição, achou {len(imc)}'

        reais = _reais(obra, tenant)
        assert len(reais) == 2, (
            f'a obra nasceu sem serviço para o RDO apontar: {len(reais)} '
            f'ServicoObraReal')


def test_aprovar_proposta_com_valor_gera_o_lancamento_contabil():
    with app.app_context():
        tenant = um_tenant('contab', com_fatos=False)
        proposta = _proposta(tenant, valor_item=Decimal('1000'), n_itens=2)

        _aprovar(tenant, proposta)

        lancamentos = _lancamentos(tenant, Decimal('2000.00'))
        assert len(lancamentos) == 1, (
            f'esperava um lançamento de R$ 2000,00, achou {len(lancamentos)}')
        partidas = lancamentos[0].partidas
        assert len(partidas) == 2, (
            f'partida dobrada exige duas pernas, achou {len(partidas)}')
        assert (sum(float(p.valor) for p in partidas)
                == pytest.approx(4000.0)), 'débito + crédito devem somar 2×'


# ---------------------------------------------------------------------------
# (b) — o branch de valor zero
# ---------------------------------------------------------------------------

def test_aprovar_proposta_de_valor_zero_semeia_servicos_reais():
    """O terceiro caminho do handler.

    Por ele passam toda proposta de valor zero **e** a importação
    físico-financeira (`services/importacao_fisico_financeiro.py:572-578`, com
    ``skip_contabil=True``). O ``return`` do ramo
    `if valor_total <= 0 or skip_contabil:` acontecia antes das chamadas que
    os outros dois ramos já faziam, então nem serviço era semeado nem lead
    fechado — e nenhum teste que chame a função direto enxerga isso.

    **Era `xfail(strict=True)`**, plantado pelo B0 como checklist do A14.
    A Task B3.5 pôs `_semear_servicos_reais` e `_fechar_lead_da_proposta`
    dentro do ramo; a marca saiu no MESMO trabalho porque `strict` transforma
    XPASS em FAILED.
    """
    with app.app_context():
        tenant = um_tenant('zero', com_fatos=False)
        proposta = _proposta(tenant, valor_item=Decimal('0'), n_itens=2)

        _aprovar(tenant, proposta)

        obra = _obra_da_proposta(tenant, proposta)
        assert obra is not None, 'nem a obra saiu no caminho de valor zero'
        reais = _reais(obra, tenant)
        assert len(reais) == 2, (
            f'proposta de valor zero não semeou ServicoObraReal: {len(reais)}')


# ---------------------------------------------------------------------------
# (c) — reaprovar não duplica
# ---------------------------------------------------------------------------

def test_reaprovar_nao_duplica_o_lancamento_contabil():
    with app.app_context():
        tenant = um_tenant('reaprova', com_fatos=False)
        proposta = _proposta(tenant, valor_item=Decimal('1000'), n_itens=2)

        _aprovar(tenant, proposta)
        depois_de_uma = len(_lancamentos(tenant, Decimal('2000.00')))

        _aprovar(tenant, proposta)
        depois_de_duas = len(_lancamentos(tenant, Decimal('2000.00')))

        assert depois_de_uma == 1
        assert depois_de_duas == 1, (
            f'a reaprovação duplicou o lançamento: {depois_de_duas}')


# ---------------------------------------------------------------------------
# (d) — a rota do cliente
# ---------------------------------------------------------------------------

def test_token_desconhecido_responde_404_e_nao_grava_nada():
    """O plano pedia "token de outro tenant → 404". Ao abrir a rota, a premissa
    não se sustenta: `propostas_consolidated.py:2510` busca por
    ``token_cliente`` **sem** ``admin_id``, e isso está certo — no portal o
    token **é** a credencial, e escopá-lo por tenant não acrescentaria
    segurança (quem tem o token já tem o direito).

    O que dá para afirmar, e é o que importa, é que token inexistente não
    materializa nada.
    """
    with app.app_context():
        tenant = um_tenant('token', com_fatos=False)
        antes = Obra.query.filter_by(admin_id=tenant.admin_id).count()

        resposta = app.test_client().post(
            f'/propostas/cliente/tok-que-nao-existe-{uuid4().hex}/aprovar',
            data={'observacoes': ''})

        assert resposta.status_code == 404
        db.session.expire_all()
        assert Obra.query.filter_by(admin_id=tenant.admin_id).count() == antes
