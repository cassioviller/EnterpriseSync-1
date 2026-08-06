"""B5.7 — a exclusão de gêmeos chega ao fluxo de caixa; os mortos saem.

Task B5.7 do apenso (§10) de
`docs/superpowers/plans/2026-08-06-rodada-b5-varredura.md`, sob a decisão
**D-B5.1 = (a)** (GestaoCustoPai é a única fonte da SAÍDA) e **D-B5.7 = (2)**
(compras ficam fora do realizado do fluxo, por decisão documentada).

**O defeito.** A exclusão de gêmeos `~GestaoCustoPai.id.in_(_compra_gcp_ids)`
existia SÓ em `listar_contas_pagar`; `calcular_fluxo_caixa` não tinha
equivalente: os GCPs de pedido de compra (que têm gêmea `ContaPagar` da mesma
obrigação) entravam inteiros em `saidas_previstas` e nos buckets de
`agregar_fluxo_mensal` — ⚠️ dev 06/08: 580 gêmeos, R$ 490.950, 24% do valor
aberto do parque. E pagar a gêmea CP com banco debitava o `saldo_inicial`
(via `banco.saldo_atual`) MANTENDO a prevista do GCP para sempre — a mesma
despesa subtraída duas vezes do `saldo_final_projetado`.

**As armadilhas que os casos 2 e 5 vigiam** (achados do adversário do WF-2):
subquery sem `admin_id` = misjoin (41 falsos gêmeos na primeira medição); e o
guard de idempotência de `migrar_contas_pagar` não via a gêmea
`'pedido_compra'` — um clique no botão vivo ("Esta ação é segura e pode ser
repetida") criava a SEGUNDA GCP por parcela, fora de toda exclusão.

**Matriz de mutação (Step 6).** Restaurar a inclusão dos gêmeos derruba só
1/4; tirar o `admin_id` da subquery derruba só o 2; restaurar o guard antigo
do migrar derruba só o 5.
"""
import os
import sys
import uuid
from datetime import date, timedelta
from decimal import Decimal

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import main  # noqa: F401 — registra os blueprints antes de qualquer request
from app import app, db
from models import (ContaPagar, GestaoCustoFilho, GestaoCustoPai,
                    RegistroPonto)

from financeiro_service import FinanceiroService
from helpers_tenant import cliente_de, um_tenant

HOJE = date(2026, 8, 6)


@pytest.fixture()
def tenant():
    app.config['TESTING'] = True
    app.config['WTF_CSRF_ENABLED'] = False
    # function-scoped: cada teste mede saidas_previstas do SEU tenant limpo —
    # a lição da B5.2 (nada aqui depende de ordem nem de resíduo).
    with app.app_context():
        return um_tenant('b5flx', com_fatos=False)


def _gcp(admin_id, obra_id, valor=1000, saldo='igual', compra_origem_id=None,
         entidade=None, filho_admin_id=None, filho_obra_id=None):
    """GCP PENDENTE com vencimento na janela. `compra_origem_id` cria o filho
    `'pedido_compra'` que o torna gêmeo; `filho_admin_id`/`filho_obra_id`
    permitem plantar o filho em OUTRO tenant (caso 2 — a forma das 168 órfãs
    de dev). O filho carrega `obra_id` por causa do check da Fase 4
    (`ck_gestao_custo_filho_destino`: todo custo tem destino)."""
    with app.app_context():
        g = GestaoCustoPai(
            tipo_categoria='MATERIAL',
            entidade_nome=entidade or f'GCP-{uuid.uuid4().hex[:6]}',
            valor_total=Decimal(valor),
            saldo=(Decimal(valor) if saldo == 'igual' else saldo),
            status='PENDENTE', data_vencimento=HOJE + timedelta(days=5),
            admin_id=admin_id, obra_id=obra_id)
        db.session.add(g)
        db.session.flush()
        if compra_origem_id is not None:
            db.session.add(GestaoCustoFilho(
                pai_id=g.id, admin_id=(filho_admin_id or admin_id),
                obra_id=(filho_obra_id or obra_id),
                descricao='parcela', valor=Decimal(valor),
                data_referencia=HOJE, origem_tabela='pedido_compra',
                origem_id=compra_origem_id))
        db.session.commit()
        return g.id, g.entidade_nome


def _fluxo(admin_id):
    with app.app_context():
        return FinanceiroService.calcular_fluxo_caixa(
            admin_id, HOJE, HOJE + timedelta(days=30))


def _nas_previstas(fluxo, entidade):
    return any(entidade in d['descricao'] for d in fluxo['detalhes']
               if d['tipo'] == 'SAIDA' and not d.get('realizado'))


def test_caso1_gcp_de_compra_com_gemea_sai_das_previstas_e_dos_buckets(tenant):
    _, entidade = _gcp(tenant.admin_id, tenant.obra_id, valor=700, compra_origem_id=91001)

    fluxo = _fluxo(tenant.admin_id)

    assert fluxo['saidas_previstas'] == 0.0, (
        f"saidas_previstas={fluxo['saidas_previstas']}: o GCP-compra com "
        f"gêmea CP continua sendo previsto — a dupla subtração do item nº5")
    assert not _nas_previstas(fluxo, entidade), (
        'o gêmeo continua nos detalhes → nos buckets de agregar_fluxo_mensal')
    # WF-3: a primeira forma desta asserção usava m.get('saidas') — chave que
    # os buckets NÃO têm (são saidas_real/previsto_liquido) — e era vácua.
    mensal = FinanceiroService.agregar_fluxo_mensal(
        fluxo['detalhes'], fluxo['saldo_inicial'])
    for m in (mensal.get('meses') or []):
        assert m.get('previsto_liquido', 0) == 0 and m.get('saidas_real', 0) == 0, (
            f'bucket {m.get("mes")} carrega valor do gêmeo: {m}')


def test_caso2_colisao_de_id_com_filho_de_outro_tenant_nao_exclui(tenant):
    """O filho `'pedido_compra'` mora em OUTRO tenant apontando (dado sujo,
    como as 168 órfãs de dev) para o GCP deste. Sem `admin_id` na subquery, o
    GCP manual deste tenant seria excluído por misjoin — o erro que a medição
    do WF-2 cometeu duas vezes."""
    with app.app_context():
        outro = um_tenant('b5flxB', com_fatos=False)
    gcp_id, entidade = _gcp(tenant.admin_id, tenant.obra_id, valor=500)  # manual, sem gêmea
    with app.app_context():
        db.session.add(GestaoCustoFilho(
            pai_id=gcp_id, admin_id=outro.admin_id, obra_id=outro.obra_id,
            descricao='orfa', valor=Decimal('500'), data_referencia=HOJE,
            origem_tabela='pedido_compra', origem_id=91002))
        db.session.commit()

    fluxo = _fluxo(tenant.admin_id)
    assert _nas_previstas(fluxo, entidade), (
        'GCP manual excluído por filho de OUTRO tenant — a subquery está sem '
        'o guard de admin_id')
    assert fluxo['saidas_previstas'] == 500.0


def test_caso3_gcp_manual_sem_gemea_continua_previsto(tenant):
    _, entidade = _gcp(tenant.admin_id, tenant.obra_id, valor=300)
    fluxo = _fluxo(tenant.admin_id)
    assert _nas_previstas(fluxo, entidade)
    assert fluxo['saidas_previstas'] == 300.0


def test_caso4_gemeo_com_saldo_null_tambem_sai(tenant):
    """4.202 de 5.081 abertos em dev têm saldo NULL — o fallback para
    valor_total é parte obrigatória de qualquer exclusão."""
    _, entidade = _gcp(tenant.admin_id, tenant.obra_id, valor=900, saldo=None,
                       compra_origem_id=91003)
    fluxo = _fluxo(tenant.admin_id)
    assert fluxo['saidas_previstas'] == 0.0, (
        f"saidas_previstas={fluxo['saidas_previstas']}: gêmeo com saldo NULL "
        f'escapou da exclusão')
    assert not _nas_previstas(fluxo, entidade)


def test_caso5_migrar_contas_pagar_nao_clona_a_gemea_de_compra(tenant):
    """O botão vivo promete "ação segura e repetível"; o guard antigo só via
    filhos `'conta_pagar'` e clonava a CP de compra — cuja obrigação JÁ vive
    num GCP com filho `'pedido_compra'`. Duas chamadas: zero GCP novo."""
    with app.app_context():
        # obra_id preenchida como nas CPs de compra reais — sem ela o filho
        # clonado violaria o check da Fase 4 e o teste ficaria VERDE E OCO
        # (o commit inteiro falharia por outro motivo que não o guard).
        cp = ContaPagar(
            descricao='CP compra B5.7', valor_original=Decimal('1000'),
            valor_pago=Decimal('0'), saldo=Decimal('1000'),
            data_emissao=HOJE, data_vencimento=HOJE + timedelta(days=10),
            status='PENDENTE', origem_tipo='COMPRA', origem_id=91004,
            obra_id=tenant.obra_id, admin_id=tenant.admin_id)
        db.session.add(cp)
        db.session.commit()
    _gcp(tenant.admin_id, tenant.obra_id, valor=1000, compra_origem_id=91004)  # a gêmea real

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
        f'{apos_1 - antes} GCP(s) clonado(s) na 1ª chamada — o guard não '
        f'reconhece a gêmea pedido_compra (o amplificador de um clique)')
    assert apos_2 == antes, f'{apos_2 - antes} clonados na 2ª chamada'


def test_caso6_rota_de_custo_de_veiculo_saiu_do_url_map():
    """`main.novo_custo_veiculo` era morta TRIPLA: FluxoCaixa sem admin_id
    (NOT NULL → IntegrityError garantido no commit), template inexistente
    (GET morria em TemplateNotFound) e zero referências. O corte é a rota
    inteira — cortar só o bloco FC ressuscitaria um escritor de CustoVeiculo
    que nunca persistiu (risco 3)."""
    from werkzeug.exceptions import NotFound
    adapter = app.url_map.bind('localhost')
    with pytest.raises(NotFound):
        adapter.match('/veiculos/1/custo', method='POST')
    assert not [r for r in app.url_map.iter_rules()
                if r.endpoint == 'main.novo_custo_veiculo']


def test_caso7_preview_de_exclusao_de_ponto_mantem_a_chave_fluxo_caixa(tenant):
    """Os leitores de FC `'registro_ponto'` não tinham escritor (⚠️ dev 0
    linhas; homonímia com GestaoCustoFilho checada na varredura). Removê-los
    não muda comportamento observável: o JSON mantém `fluxo_caixa: []` — os
    consumidores JS toleram lista vazia, não chave ausente."""
    with app.app_context():
        rp = RegistroPonto(
            funcionario_id=tenant.funcionario_id, obra_id=tenant.obra_id,
            admin_id=tenant.admin_id, data=HOJE, horas_trabalhadas=8.0)
        db.session.add(rp)
        db.session.commit()
        rp_id = rp.id

    cli = cliente_de(tenant.admin_id)
    r = cli.get(f'/ponto/excluir-preview/{rp_id}')
    assert r.status_code == 200
    payload = r.get_json()
    assert payload['success'] is True
    assert payload['fluxo_caixa'] == [], (
        'a chave fluxo_caixa tem de existir e ser lista vazia — contrato dos '
        'consumidores JS (controle_ponto.html:543-545)')
