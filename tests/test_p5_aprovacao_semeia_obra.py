"""p5 — a aprovação semeia a obra inteira, e o CRM sabe do desfecho.

Duas lacunas que o levantamento de 31/07 confirmou:

1. **A obra nascia sem serviço para apontar.** A aprovação já criava Obra,
   `ItemMedicaoComercial`, `ObraServicoCusto` e cronograma — mas não
   `ServicoObraReal`, que é sobre o que o RDO trabalha. Quem fosse lançar o
   primeiro RDO re-selecionava na mão os mesmos serviços que a proposta
   listava.

2. **O lead ficava aberto para sempre.** `Lead.proposta_id` e `Lead.obra_id`
   existem no modelo e **nada os escrevia**.
"""
import os
import sys
from datetime import date
from decimal import Decimal
from uuid import uuid4

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app import app, db
from models import (Lead, LeadStatus, Proposta, PropostaItem, Servico,
                    ServicoObraReal)
from helpers_tenant import dois_tenants
from handlers.propostas_handlers import (_fechar_lead_da_proposta,
                                         _semear_servicos_reais)

pytestmark = pytest.mark.integration


@pytest.fixture(autouse=True)
def _config():
    app.config['TESTING'] = True
    if not app.secret_key:
        app.secret_key = 'test-p5'
    with app.app_context():
        yield


def _tenant():
    a, _b = dois_tenants('p5')
    return a


def _servico(t, nome):
    s = Servico(nome=f'{nome} {t.marca}', admin_id=t.admin_id, ativo=True,
                unidade_medida='m2', categoria='estrutural')
    db.session.add(s)
    db.session.flush()
    return s


def _proposta_com_itens(t, servicos, com_avulso=False):
    p = Proposta(numero=f'P-{uuid4().hex[:8]}', admin_id=t.admin_id,
                 cliente_id=t.cliente_id, obra_id=t.obra_id,
                 cliente_nome=f'Cliente {t.marca}', data_proposta=date.today(),
                 versao=1, titulo='Proposta p5', status='Aprovada')
    db.session.add(p)
    db.session.flush()
    for i, s in enumerate(servicos, start=1):
        db.session.add(PropostaItem(
            proposta_id=p.id, admin_id=t.admin_id, item_numero=i,
            descricao=f'Item {i}', quantidade=Decimal('10'), unidade='m2',
            preco_unitario=Decimal('100'), servico_id=s.id, ordem=i,
            subtotal=Decimal('1000')))
    if com_avulso:
        db.session.add(PropostaItem(
            proposta_id=p.id, admin_id=t.admin_id, item_numero=99,
            descricao='Item avulso sem catálogo', quantidade=Decimal('1'),
            unidade='vb', preco_unitario=Decimal('500'), servico_id=None,
            ordem=99, subtotal=Decimal('500')))
    db.session.commit()
    return p


def _reais(t):
    return ServicoObraReal.query.filter_by(obra_id=t.obra_id,
                                           admin_id=t.admin_id).all()


# ---------------------------------------------------------------------------
# A obra nasce pronta para o RDO
# ---------------------------------------------------------------------------

def test_aprovacao_semeia_servico_real_de_cada_item():
    t = _tenant()
    s1, s2 = _servico(t, 'Alvenaria'), _servico(t, 'Pintura')
    p = _proposta_com_itens(t, [s1, s2])

    assert _semear_servicos_reais(p.id, t.admin_id) == 2
    db.session.commit()

    semeados = {r.servico_id: r for r in _reais(t)}
    assert set(semeados) == {s1.id, s2.id}
    assert float(semeados[s1.id].quantidade_planejada) == 10.0
    assert float(semeados[s1.id].valor_total_planejado) == 1000.0


def test_item_avulso_sem_catalogo_nao_vira_servico_real():
    """`ServicoObraReal.servico_id` é NOT NULL — inventar um serviço aqui
    seria criar catálogo pelo caminho errado."""
    t = _tenant()
    s1 = _servico(t, 'Alvenaria')
    p = _proposta_com_itens(t, [s1], com_avulso=True)

    assert _semear_servicos_reais(p.id, t.admin_id) == 1
    db.session.commit()
    assert len(_reais(t)) == 1


def test_reaprovar_nao_duplica():
    """Revisão de proposta reaprovada passa pelo mesmo handler."""
    t = _tenant()
    s1 = _servico(t, 'Alvenaria')
    p = _proposta_com_itens(t, [s1])

    _semear_servicos_reais(p.id, t.admin_id)
    db.session.commit()
    assert _semear_servicos_reais(p.id, t.admin_id) == 0
    db.session.commit()

    assert len(_reais(t)) == 1


def test_proposta_sem_obra_nao_semeia_nada():
    t = _tenant()
    s1 = _servico(t, 'Alvenaria')
    p = _proposta_com_itens(t, [s1])
    p.obra_id = None
    db.session.commit()

    assert _semear_servicos_reais(p.id, t.admin_id) == 0


def test_nao_semeia_para_obra_de_outro_tenant():
    a, b = dois_tenants('p5b')
    s = Servico(nome=f'Servico {a.marca}', admin_id=a.admin_id, ativo=True,
                unidade_medida='m2', categoria='estrutural')
    db.session.add(s)
    db.session.flush()
    p = Proposta(numero=f'P-{uuid4().hex[:8]}', admin_id=a.admin_id,
                 cliente_id=a.cliente_id, obra_id=a.obra_id,
                 cliente_nome=f'Cliente {a.marca}', data_proposta=date.today(),
                 versao=1, titulo='Proposta', status='Aprovada')
    db.session.add(p)
    db.session.flush()
    db.session.add(PropostaItem(
        proposta_id=p.id, admin_id=a.admin_id, item_numero=1,
        descricao='Item', quantidade=Decimal('1'), unidade='m2',
        preco_unitario=Decimal('10'), servico_id=s.id, ordem=1,
        subtotal=Decimal('10')))
    db.session.commit()

    # o tenant B pede a semeadura da proposta de A: não acha, não semeia
    assert _semear_servicos_reais(p.id, b.admin_id) == 0
    db.session.commit()
    assert ServicoObraReal.query.filter_by(obra_id=b.obra_id).count() == 0


# ---------------------------------------------------------------------------
# O CRM fica sabendo
# ---------------------------------------------------------------------------

def _lead(t, proposta, status=LeadStatus.ENVIADO.value):
    lead = Lead(admin_id=t.admin_id, nome=f'Lead {t.marca}', status=status,
                proposta_id=proposta.id)
    db.session.add(lead)
    db.session.commit()
    return lead


def test_aprovacao_fecha_o_lead_e_amarra_a_obra():
    t = _tenant()
    p = _proposta_com_itens(t, [_servico(t, 'Alvenaria')])
    lead = _lead(t, p)

    assert _fechar_lead_da_proposta(p.id, t.admin_id) == 1
    db.session.commit()
    db.session.refresh(lead)

    assert lead.status == LeadStatus.APROVADO.value
    assert lead.obra_id == t.obra_id


def test_lead_perdido_nao_e_reaberto():
    """Desfecho registrado à mão vale mais que a inferência do handler."""
    t = _tenant()
    p = _proposta_com_itens(t, [_servico(t, 'Alvenaria')])
    lead = _lead(t, p, status=LeadStatus.PERDIDO.value)

    assert _fechar_lead_da_proposta(p.id, t.admin_id) == 0
    db.session.commit()
    db.session.refresh(lead)
    assert lead.status == LeadStatus.PERDIDO.value


def test_fechar_lead_e_idempotente():
    t = _tenant()
    p = _proposta_com_itens(t, [_servico(t, 'Alvenaria')])
    _lead(t, p)

    _fechar_lead_da_proposta(p.id, t.admin_id)
    db.session.commit()
    assert _fechar_lead_da_proposta(p.id, t.admin_id) == 0


def test_forma_o_handler_chama_os_dois_nos_dois_caminhos_conhecidos():
    """**GUARDA DE FORMA — não prova comportamento.**

    Conta ocorrências no texto do handler para pegar quem remover uma das
    chamadas. Serve para isso e só para isso.

    ⚠️ **A docstring anterior estava errada** e vale registrar por quê: ela
    dizia que este teste cobria "o caminho de importação (`skip_contabil`)".
    Não cobre — contar ``== 2`` ocorrências não diz por onde a execução passa.
    🔬 04/08: o handler tem um **terceiro** caminho de saída
    (`handlers/propostas_handlers.py:378-385`) que dá ``return`` **antes** das
    duas chamadas, e é justamente por ele que a importação físico-financeira
    (`services/importacao_fisico_financeiro.py:572-578`) e toda proposta de
    valor zero passam. O contador de strings ficou verde o tempo todo.

    **A prova de comportamento mora em**
    ``tests/test_arreio_aprovacao_proposta_rotas.py``, que aprova pela rota e
    afirma sobre ``ServicoObraReal``.
    """
    caminho = os.path.join(os.path.dirname(os.path.dirname(
        os.path.abspath(__file__))), 'handlers', 'propostas_handlers.py')
    with open(caminho, encoding='utf-8') as fh:
        texto = fh.read()
    assert texto.count('_semear_servicos_reais(proposta_id, admin_id)') == 2
    assert texto.count('_fechar_lead_da_proposta(proposta_id, admin_id)') == 2
