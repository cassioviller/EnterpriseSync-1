"""B6.2 — a família 2 de gêmeos sai da tela e do fluxo; o migrar para de clonar.

Task B6.2 de `docs/superpowers/plans/2026-08-06-rodada-b6-varredura.md`, sob a
decisão **D-B6.2** (o `apenas_pagamento` segue editável; só o texto muda).

⚠️ **Prevenção da FORMA, não incidente medível.** A família 2 tem **ZERO
exemplares** em dev (⚠️ 06/08, reproduzido pela refutação): o caminho de
gravação do import de fluxo com checkbox de reembolso nunca rodou lá. **Este
arquivo É o exemplar** — a forma é montada por ORM exatamente como
`services/importacao_excel.py:2400-2431` a grava.

**A forma.** GCP + GCF **sem `origem_tabela`** (invisível a toda exclusão por
GCF, que é como a B5.7 excluiu a família 1) + CP gêmea com
`origem_tipo='gestao_custo_pai'` **minúsculo** e `origem_id=gcp.id` — chave
DIRETA, mais forte que a da família 1. Por isso a exclusão desta família é uma
subquery sobre `conta_pagar`, não sobre `gestao_custo_filho`.

**A dupla contagem, na mesma tela.** `listar_contas_pagar` só exclui GCP com
filho `'pedido_compra'`; o GCF do import tem origem NULL, então a GCP entra em
`custos_v2` ao lado da CP e o KPI soma as duas. No fluxo, a GCP entra em
`saidas_previstas` enquanto a CP é invisível — pagar a CP debita banco e deixa
a prevista **eterna**, o defeito que a B5.7 fechou para a família 1.

**O buraco do migrar.** `migrar_contas_pagar` pula só `upper()=='COMPRA'`; a CP
`'gestao_custo_pai'` PENDENTE é clonada **no 1º clique** (o guard de
idempotência só vê clones da própria rota, do 2º clique em diante) e o clone
escapa de todas as exclusões → tripla contagem. E o botão promete "ação segura
e pode ser repetida".

**Matriz de mutação (Step 5).** Restaurar o guard antigo do migrar derruba só o
1; tirar o `admin_id` da subquery derruba só o 5; restaurar uma ponta da
exclusão derruba só o caso daquela ponta (2 = tela, 3 = fluxo).
"""
import os
import sys
import uuid
from datetime import date, timedelta
from decimal import Decimal

import pytest
from flask import template_rendered

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import main  # noqa: F401 — registra os blueprints antes de qualquer request
from app import app, db
from models import (ContaPagar, FluxoCaixa, GestaoCustoFilho, GestaoCustoPai)

from financeiro_service import FinanceiroService
from helpers_tenant import cliente_de, um_tenant

HOJE = date(2026, 8, 6)
JANELA_FIM = HOJE + timedelta(days=30)


@pytest.fixture()
def tenant():
    app.config['TESTING'] = True
    app.config['WTF_CSRF_ENABLED'] = False
    # function-scoped, pela lição da B5.2: os casos 2 e 3 medem KPI e
    # `saidas_previstas` do tenant INTEIRO — resíduo de outro caso viraria
    # falso verde (ou falso vermelho) por soma.
    with app.app_context():
        return um_tenant('b6fam2', com_fatos=False)


def _familia2(admin_id, obra_id, valor=1000, batch_id=None, com_cp=True,
              cp_admin_id=None, cp_origem_id='pai'):
    """A forma EXATA do import de fluxo em modo reembolso.

    `com_cp=False` monta o GCP manual (sem gêmea) do caso 4. `cp_admin_id`
    planta a CP gêmea em OUTRO tenant — o caso 5, cão de guarda do `admin_id`
    na subquery.
    """
    with app.app_context():
        g = GestaoCustoPai(
            tipo_categoria='MATERIAL',
            entidade_nome=f'REEMB-{uuid.uuid4().hex[:6]}',
            valor_total=Decimal(valor), saldo=Decimal(valor),
            status='PENDENTE', data_vencimento=HOJE + timedelta(days=5),
            admin_id=admin_id, obra_id=obra_id, import_batch_id=batch_id)
        db.session.add(g)
        db.session.flush()

        # ⚠️ O filho nasce SEM `origem_tabela` (`importacao_excel.py:2368-2376`)
        # — é por isso que a exclusão da B5.7, que olha o filho, não o vê. O
        # `obra_id` é obrigatório pelo check da Fase 4.
        db.session.add(GestaoCustoFilho(
            pai_id=g.id, admin_id=admin_id, obra_id=obra_id,
            descricao='reembolso', valor=Decimal(valor),
            data_referencia=HOJE, origem_tabela=None, origem_id=None))

        cp_id = None
        if com_cp:
            cp = ContaPagar(
                descricao=f'CP gemea {g.entidade_nome}',
                valor_original=Decimal(valor), valor_pago=Decimal('0'),
                saldo=Decimal(valor), data_emissao=HOJE,
                data_vencimento=HOJE + timedelta(days=10), status='PENDENTE',
                # minúsculo, como o import grava (`:2427`)
                origem_tipo='gestao_custo_pai',
                origem_id=(g.id if cp_origem_id == 'pai' else cp_origem_id),
                obra_id=obra_id, admin_id=(cp_admin_id or admin_id),
                import_batch_id=batch_id)
            db.session.add(cp)
            db.session.flush()
            cp_id = cp.id

        db.session.commit()
        return g.id, g.entidade_nome, cp_id


def _contexto_contas_pagar(admin_id):
    """`custos_v2` e `resumo` como a tela os recebe.

    O oráculo é o CONTEXTO do template, não o HTML: o KPI passa por filtro de
    formatação e casar número em markup é como o caso 3 da B5.6 ficou oco."""
    capturado = {}

    def _registrar(sender, template, context, **extra):
        if template.name and 'contas_pagar' in template.name:
            capturado.update(context)

    cli = cliente_de(admin_id)
    template_rendered.connect(_registrar, app)
    try:
        r = cli.get('/financeiro/contas-pagar')
        assert r.status_code == 200, f'a tela não abriu: {r.status_code}'
    finally:
        template_rendered.disconnect(_registrar, app)
    return capturado


def _fluxo(admin_id):
    with app.app_context():
        return FinanceiroService.calcular_fluxo_caixa(
            admin_id, HOJE, JANELA_FIM)


def _nas_previstas(fluxo, entidade):
    return any(entidade in (d['descricao'] or '') for d in fluxo['detalhes']
               if d['tipo'] == 'SAIDA' and not d.get('realizado'))


def test_caso1_migrar_nao_clona_a_gemea_de_reembolso_no_primeiro_clique(tenant):
    """O guard de idempotência só vê clones DESTA rota (pega do 2º clique em
    diante) e o guard de origem só pula `'COMPRA'`. A CP `'gestao_custo_pai'`
    PENDENTE é clonada no **1º clique**, e o clone escapa de toda exclusão —
    tripla contagem, num botão que promete ser repetível."""
    _familia2(tenant.admin_id, tenant.obra_id, valor=1000)

    def _n_gcps():
        with app.app_context():
            return GestaoCustoPai.query.filter_by(
                admin_id=tenant.admin_id).count()

    antes = _n_gcps()
    cli = cliente_de(tenant.admin_id)
    r1 = cli.post('/gestao-custos/migrar-contas-pagar', follow_redirects=False)
    apos_1 = _n_gcps()
    cli.post('/gestao-custos/migrar-contas-pagar', follow_redirects=False)
    apos_2 = _n_gcps()

    assert r1.status_code == 302
    assert apos_1 == antes, (
        f'{apos_1 - antes} GCP(s) clonado(s) no 1º clique — o guard não '
        f'reconhece a gêmea gestao_custo_pai (o amplificador de um clique)')
    assert apos_2 == antes, f'{apos_2 - antes} clonados na 2ª chamada'


def test_caso2_gcp_de_reembolso_sai_da_tela_e_o_kpi_conta_uma_vez(tenant):
    """A GCP e a CP gêmea são a MESMA obrigação. Hoje as duas aparecem juntas
    na tabela e o KPI `pendentes` soma as duas — R$ 1.000 viram R$ 2.000."""
    _, entidade, _ = _familia2(tenant.admin_id, tenant.obra_id, valor=1000)

    ctx = _contexto_contas_pagar(tenant.admin_id)

    nomes_v2 = [c.entidade_nome for c in (ctx.get('custos_v2') or [])]
    assert entidade not in nomes_v2, (
        f'a GCP de reembolso continua em custos_v2 ({nomes_v2}) ao lado da CP '
        f'gêmea — a mesma obrigação exibida duas vezes na mesma tela')
    assert ctx['resumo']['pendentes'] == 1000.0, (
        f"resumo['pendentes']={ctx['resumo']['pendentes']}: a obrigação de "
        f'R$ 1.000 foi contada duas vezes no KPI (CP + GCP)')


def test_caso3_gcp_de_reembolso_sai_das_previstas_e_dos_buckets(tenant):
    """No fluxo a assimetria morde ao contrário: a GCP entra nas previstas e a
    CP gêmea é invisível. Pagar a CP debita `banco.saldo_atual` (= o
    `saldo_inicial` deste fluxo) e deixa a prevista ETERNA — a dupla subtração
    que a B5.7 fechou para a família 1."""
    _, entidade, _ = _familia2(tenant.admin_id, tenant.obra_id, valor=700)

    fluxo = _fluxo(tenant.admin_id)

    assert fluxo['saidas_previstas'] == 0.0, (
        f"saidas_previstas={fluxo['saidas_previstas']}: o GCP de reembolso "
        f'com gêmea CP continua sendo previsto')
    assert not _nas_previstas(fluxo, entidade), (
        'o gêmeo continua nos detalhes → nos buckets de agregar_fluxo_mensal')
    mensal = FinanceiroService.agregar_fluxo_mensal(
        fluxo['detalhes'], fluxo['saldo_inicial'])
    for m in (mensal.get('meses') or []):
        assert m.get('previsto_liquido', 0) == 0 and m.get('saidas_real', 0) == 0, (
            f'bucket {m.get("mes")} carrega valor do gêmeo: {m}')


def test_caso4_gcp_manual_sem_gemea_continua_na_tela_e_nas_previstas(tenant):
    """A guarda: só sai quem TEM gêmea. GCP manual (o caso comum do parque)
    segue exibido e previsto — uma exclusão larga demais apagaria o custo do
    fluxo de quem nunca importou nada."""
    _, entidade, _ = _familia2(tenant.admin_id, tenant.obra_id, valor=300,
                               com_cp=False)

    ctx = _contexto_contas_pagar(tenant.admin_id)
    assert entidade in [c.entidade_nome for c in (ctx.get('custos_v2') or [])], (
        'GCP manual sumiu da tela — a exclusão está larga demais')
    assert ctx['resumo']['pendentes'] == 300.0

    fluxo = _fluxo(tenant.admin_id)
    assert _nas_previstas(fluxo, entidade)
    assert fluxo['saidas_previstas'] == 300.0


def test_caso5_cp_gemea_de_outro_tenant_nao_exclui(tenant):
    """Cão de guarda do `admin_id` na subquery — a regra da casa desde a
    contradição 9 da B5. Uma CP de OUTRO tenant com `origem_id` colidindo com
    o id do GCP deste não pode excluí-lo: é o misjoin que a medição do WF-2
    cometeu duas vezes (41 falsos gêmeos)."""
    with app.app_context():
        outro = um_tenant('b6fam2B', com_fatos=False)

    gcp_id, entidade, _ = _familia2(tenant.admin_id, tenant.obra_id, valor=500,
                                    com_cp=False)
    with app.app_context():
        # a CP gêmea existe, mas no tenant ERRADO, apontando para o GCP daqui
        db.session.add(ContaPagar(
            descricao='CP gemea alheia', valor_original=Decimal('500'),
            valor_pago=Decimal('0'), saldo=Decimal('500'), data_emissao=HOJE,
            data_vencimento=HOJE + timedelta(days=10), status='PENDENTE',
            origem_tipo='gestao_custo_pai', origem_id=gcp_id,
            obra_id=outro.obra_id, admin_id=outro.admin_id))
        db.session.commit()

    ctx = _contexto_contas_pagar(tenant.admin_id)
    assert entidade in [c.entidade_nome for c in (ctx.get('custos_v2') or [])], (
        'GCP excluído da tela por CP de OUTRO tenant — a subquery está sem o '
        'guard de admin_id')
    assert ctx['resumo']['pendentes'] == 500.0

    fluxo = _fluxo(tenant.admin_id)
    assert _nas_previstas(fluxo, entidade), (
        'GCP excluído do fluxo por CP de OUTRO tenant — misjoin')
    assert fluxo['saidas_previstas'] == 500.0


def test_caso6_rollback_do_batch_apaga_as_quatro_tabelas_juntas(tenant):
    """Guarda do mecanismo: a família 2 nasce de um batch, e o rollback tem de
    levar CP, GCP, GCF e FC no mesmo movimento. Se ele deixasse a CP para trás,
    a exclusão da tela apagaria o GCP e a obrigação sumiria inteira."""
    batch = f'import_{uuid.uuid4().hex[:10]}'
    gcp_id, _, cp_id = _familia2(tenant.admin_id, tenant.obra_id, valor=1000,
                                 batch_id=batch)
    with app.app_context():
        db.session.add(FluxoCaixa(
            admin_id=tenant.admin_id, obra_id=tenant.obra_id,
            tipo_movimento='SAIDA', categoria='despesa',
            descricao='reembolso pago', valor=Decimal('1000'),
            data_movimento=HOJE, referencia_tabela='gestao_custo_pai',
            referencia_id=gcp_id, import_batch_id=batch))
        db.session.commit()

    def _contagens():
        with app.app_context():
            return (
                ContaPagar.query.filter_by(import_batch_id=batch).count(),
                GestaoCustoPai.query.filter_by(import_batch_id=batch).count(),
                GestaoCustoFilho.query.filter_by(pai_id=gcp_id).count(),
                FluxoCaixa.query.filter_by(import_batch_id=batch).count(),
            )

    assert _contagens() == (1, 1, 1, 1), 'sanidade: o batch foi montado inteiro'

    cli = cliente_de(tenant.admin_id)
    r = cli.post(f'/importacao/fluxo-caixa/rollback/{batch}',
                 follow_redirects=False)
    assert r.status_code == 302

    assert _contagens() == (0, 0, 0, 0), (
        f'o rollback deixou registros para trás: {_contagens()} '
        f'(CP, GCP, GCF, FC)')
