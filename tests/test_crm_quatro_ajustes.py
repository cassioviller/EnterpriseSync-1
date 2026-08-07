"""CRM — os quatro ajustes do spec de 07/08.

Spec: ``docs/superpowers/specs/2026-08-07-crm-quatro-ajustes-design.md``.
Plano: ``docs/superpowers/plans/2026-08-07-plano-execucao-crm-quatro-ajustes.md``.

**C1 — dropdowns.** O defeito provado no dev: ``dropdown_grupo`` e
``dropdown_opcao`` com zero linhas enquanto as tabelas legadas ``crm_*`` têm
dado — ``get_dropdown_options`` devolve ``[]`` sem log e os sete selects do
CRM renderizam vazios. O conserto é D-CRM.1 (backfill 282 + fallback), e a
fronteira fina está no teste 1c: o fallback dispara em grupo com **zero
linhas** (nunca semeado), não em grupo com zero **ativas** (estado deliberado
do admin) — a lição da WF-4 sobre guarda vazia, aplicada antes de errar.

**C2 — a tag Validado.** ``mudar_status`` nunca zera ``validacao_aprovada`` e
os templates só olham o booleano: a tag segue o lead até Aprovado. A regra
nova é lista positiva (Em fila, Em andamento, Validação) — e o teste 5 impede
o conserto preguiçoso que esconderia o badge em todo status.

**C3 — prazo.** Lead novo sem prazo ganha ``data_chegada + 3 dias úteis``.
O caso que prova a regra é chegada na QUINTA → prazo na TERÇA: uma soma de
dias corridos passaria em qualquer teste que começasse na segunda.

**C4 — exportação.** ``GET /crm/exportar``: todos os leads do tenant, todos
os campos, aba ``Leads`` (deliberadamente ≠ ``Lead.2026`` — a exportação não
volta pelo importador, D-CRM.6), ignorando os filtros da query string.

Regra de tenant: um único tenant é autor dos requests em cada teste; o outro
existe só como precondição semeada e é pela ``marca`` dele que se procura o
vazamento (padrão de ``helpers_tenant``).
"""
import io
import os
import sys
from datetime import date, datetime

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import main  # noqa: F401 — registra os blueprints antes de qualquer request
from app import app, db
from models import (CrmOrigem, DropdownGrupo, DropdownOpcao, Lead, LeadStatus)

from helpers_tenant import cliente_de, dois_tenants, um_tenant

pytestmark = pytest.mark.integration


@pytest.fixture(autouse=True)
def _config():
    app.config['TESTING'] = True
    app.config['WTF_CSRF_ENABLED'] = False
    if not app.secret_key:
        app.secret_key = 'test-crm-quatro-ajustes'
    yield


# ---------------------------------------------------------------------------
# Sementes
# ---------------------------------------------------------------------------

ORIGENS = ['Loja', 'Indicação', 'Google']


def _origens_legadas(tenant, nomes=None, ativo=True):
    """Semeia CrmOrigem (tabela legada, fonte de verdade da FK) SEM tocar o
    motor de dropdowns — reproduz o tenant torto do diagnóstico."""
    out = []
    for nome in (nomes or ORIGENS):
        o = CrmOrigem(admin_id=tenant.admin_id, nome=nome, ativo=ativo)
        db.session.add(o)
        out.append(o)
    db.session.commit()
    return out


def _lead(tenant, status=LeadStatus.VALIDACAO, **kw):
    lead = Lead(nome=f'Lead {tenant.marca}', admin_id=tenant.admin_id,
                data_chegada=kw.pop('data_chegada', date(2026, 6, 1)),
                status=status.value, cliente_id=tenant.cliente_id, **kw)
    db.session.add(lead)
    db.session.commit()
    return lead


def _form_minimo(**extra):
    """POST mínimo aceito por `_salvar_lead` (só `nome` é obrigatório)."""
    base = {'nome': 'Lead Prazo', 'status': LeadStatus.EM_FILA.value}
    base.update(extra)
    return base


# ===========================================================================
# C1 — dropdowns: fallback ao legado + migração 282
# ===========================================================================

def test_c1_tenant_sem_grupo_cai_no_legado():
    """Teste 1 do spec: sem DropdownGrupo nenhum, `_listas_para_form` devolve
    as origens legadas (hoje devolve lista vazia)."""
    with app.app_context():
        t = um_tenant('c1a', com_fatos=False)
        legadas = _origens_legadas(t)
        from crm_views import _listas_para_form
        listas = _listas_para_form(t.admin_id)
        nomes = [o.nome for o in listas['origem']]
        assert nomes == ORIGENS
        # O id do wrapper é o id LEGADO — é ele que a FK de Lead espera.
        assert [o.id for o in listas['origem']] == [l.id for l in legadas]


def test_c1b_grupo_criado_vazio_tambem_cai_no_legado():
    """Teste 1b: `ensure_grupo` (chamado pela tela de cadastros) cria o grupo
    SEM nenhuma opção — o fallback tem que disparar do mesmo jeito."""
    with app.app_context():
        t = um_tenant('c1b', com_fatos=False)
        _origens_legadas(t)
        from services.dropdown_service import ensure_grupo, get_dropdown_options
        ensure_grupo('crm_origem', t.admin_id)
        db.session.commit()
        opcoes = get_dropdown_options('crm_origem', t.admin_id, for_form=True)
        assert [o.nome for o in opcoes] == ORIGENS


def test_c1c_opcoes_todas_desativadas_NAO_ressuscitam():
    """Teste 1c (a guarda da mutação): grupo com opções todas `ativo=False` é
    estado DELIBERADO do admin — cair no legado ali ressuscitaria o que ele
    desativou. Zero linhas ≠ zero ativas."""
    with app.app_context():
        t = um_tenant('c1c', com_fatos=False)
        legadas = _origens_legadas(t)
        from services.dropdown_service import ensure_grupo, get_dropdown_options
        grupo = ensure_grupo('crm_origem', t.admin_id)
        for i, leg in enumerate(legadas):
            db.session.add(DropdownOpcao(
                admin_id=t.admin_id, grupo_id=grupo.id, valor=leg.nome,
                ordem=(i + 1) * 10, ativo=False, ext_id=leg.id))
        db.session.commit()
        opcoes = get_dropdown_options('crm_origem', t.admin_id, for_form=True)
        assert opcoes == []


def test_c1_migracao_282_cria_grupo_e_opcoes_com_ext_id():
    """Teste 3: num tenant torto (legado populado, motor vazio) a 282 cria o
    grupo e copia as opções com `ext_id` = id legado."""
    with app.app_context():
        t = um_tenant('c1m', com_fatos=False)
        legadas = _origens_legadas(t)
        from migrations import _migration_282_backfill_dropdown_crm
        _migration_282_backfill_dropdown_crm()

        grupo = DropdownGrupo.query.filter_by(
            slug='crm_origem', admin_id=t.admin_id).first()
        assert grupo is not None, 'a 282 não criou o grupo que a 173 pulou'
        opcoes = (DropdownOpcao.query
                  .filter_by(grupo_id=grupo.id, admin_id=t.admin_id)
                  .order_by(DropdownOpcao.ordem).all())
        assert [(o.valor, o.ext_id) for o in opcoes] == \
            [(l.nome, l.id) for l in legadas]


def test_c1_migracao_282_e_idempotente():
    """Teste 2: rodar duas vezes não duplica grupo nem opção."""
    with app.app_context():
        t = um_tenant('c1i', com_fatos=False)
        _origens_legadas(t)
        from migrations import _migration_282_backfill_dropdown_crm
        _migration_282_backfill_dropdown_crm()

        def _contagens():
            grupos = DropdownGrupo.query.filter_by(admin_id=t.admin_id).count()
            opcoes = DropdownOpcao.query.filter_by(admin_id=t.admin_id).count()
            return grupos, opcoes

        antes = _contagens()
        _migration_282_backfill_dropdown_crm()
        assert _contagens() == antes


# ===========================================================================
# C2 — a tag "Validado" some de Enviado em diante
# ===========================================================================

def _kanban_do_card(tenant, lead):
    resp = cliente_de(tenant.admin_id).get('/crm/')
    corpo = resp.get_data(as_text=True)
    # Isola o card deste lead: do seu data-lead-id até o do próximo card.
    ini = corpo.find(f'data-lead-id="{lead.id}"')
    assert ini != -1, 'o card do lead não está no kanban'
    fim = corpo.find('data-lead-id="', ini + 1)
    return corpo[ini:fim if fim != -1 else None]


def test_c2_tag_validado_some_no_enviado():
    """Teste 4: lead validado que já foi para Enviado não exibe mais a tag."""
    with app.app_context():
        t = um_tenant('c2a', com_fatos=False)
        lead = _lead(t, status=LeadStatus.ENVIADO, validacao_aprovada=True,
                     valor_proposta=1000)
        card = _kanban_do_card(t, lead)
        assert 'Validado' not in card
        assert 'crm-card--validado' not in card


def test_c2_tag_validado_continua_na_validacao():
    """Teste 5 (a guarda contra esconder demais): em Validação a tag TEM que
    continuar — sem este teste, um conserto que escondesse o badge em todos
    os status passaria no teste 4."""
    with app.app_context():
        t = um_tenant('c2b', com_fatos=False)
        lead = _lead(t, status=LeadStatus.VALIDACAO, validacao_aprovada=True)
        card = _kanban_do_card(t, lead)
        assert 'Validado — pronto para envio' in card


def test_c2_lista_segue_a_mesma_regra():
    """A lista tem o mesmo badge com a mesma falha — mesma regra nas duas."""
    with app.app_context():
        t = um_tenant('c2c', com_fatos=False)
        _lead(t, status=LeadStatus.ENVIADO, validacao_aprovada=True,
              valor_proposta=1000)
        corpo = cliente_de(t.admin_id).get('/crm/lista').get_data(as_text=True)
        assert 'Validado' not in corpo


def test_c2_botao_validar_some_do_lead_enviado():
    """O botão "Marcar como Validado" não faz sentido em lead já enviado."""
    with app.app_context():
        t = um_tenant('c2d', com_fatos=False)
        lead = _lead(t, status=LeadStatus.ENVIADO, validacao_aprovada=False,
                     valor_proposta=1000)
        card = _kanban_do_card(t, lead)
        assert 'btn-validar-lead' not in card


