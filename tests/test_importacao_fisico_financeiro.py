import os
import sys
sys.path.insert(0, os.path.abspath(os.path.dirname(__file__) + '/..'))

import pytest
from decimal import Decimal
from app import app, db
from models import MedicaoContrato


@pytest.fixture(autouse=True)
def _fotos_base_isolada(tmp_path):
    """Isola FOTOS_RDO_BASE numa pasta VAZIA por padrão, para os testes deste
    arquivo NÃO processarem as fotos reais do repo (fotos_rdos/) — mantém a suíte
    rápida e determinística. Os testes de foto sobrescrevem `ff.FOTOS_RDO_BASE`
    no corpo com o próprio tmp_path."""
    from services import importacao_fisico_financeiro as ff
    orig = ff.FOTOS_RDO_BASE
    vazio = tmp_path / '_fotos_vazio'
    vazio.mkdir(exist_ok=True)
    ff.FOTOS_RDO_BASE = str(vazio)
    yield
    ff.FOTOS_RDO_BASE = orig


@pytest.mark.integration
def test_medicao_contrato_schema_existe():
    with app.app_context():
        cols = {c.name for c in MedicaoContrato.__table__.columns}
        assert {'obra_id', 'admin_id', 'nome', 'data', 'pct',
                'recebido_no_mes', 'obs', 'ordem'} <= cols


@pytest.mark.integration
def test_obra_tem_coluna_fluxo_caixa_planilha():
    from models import Obra
    assert 'fluxo_caixa_planilha' in {c.name for c in Obra.__table__.columns}


@pytest.mark.integration
def test_obra_tem_regime_medicao_default_fixa():
    """F1 — regime de medição por obra: 'fixa' (marcos) | 'percentual' (% via RDO).
    Default 'fixa' para não alterar obras existentes."""
    from models import Obra
    cols = {c.name for c in Obra.__table__.columns}
    assert 'regime_medicao' in cols
    col = Obra.__table__.columns['regime_medicao']
    assert col.default.arg == 'fixa'
    assert col.nullable is False


import json
from datetime import date, datetime
from werkzeug.security import generate_password_hash


def _carregar_json():
    caminho = os.path.join(os.path.dirname(__file__), 'fixtures',
                           'cronograma_fisico_financeiro_baias.json')
    with open(caminho, encoding='utf-8') as f:
        return json.load(f)


def _novo_admin():
    from models import Usuario, TipoUsuario
    tag = datetime.utcnow().strftime('%H%M%S%f')
    u = Usuario(username=f'ff_{tag}', email=f'ff_{tag}@test.local',
                nome=f'Admin FF {tag}',
                password_hash=generate_password_hash('senha123'),
                tipo_usuario=TipoUsuario.ADMIN)
    db.session.add(u)
    db.session.commit()
    return u.id


@pytest.mark.integration
def test_importa_cria_obra_com_contrato():
    from services.importacao_fisico_financeiro import importar_fisico_financeiro
    from models import Obra
    with app.app_context():
        admin_id = _novo_admin()
        res = importar_fisico_financeiro(_carregar_json(), admin_id)
        obra = Obra.query.get(res['obra_id'])
        assert obra.admin_id == admin_id
        assert abs(float(obra.valor_contrato) - 1505613.76) < 0.01
        assert obra.data_inicio == date(2026, 6, 8)
        assert obra.data_previsao_fim == date(2026, 10, 8)
        assert obra.endereco == 'Fazenda Santa Mônica'  # exibido no portal


@pytest.mark.integration
def test_importa_cria_etapas_tarefas_e_custos():
    from services.importacao_fisico_financeiro import importar_fisico_financeiro
    from models import (TarefaCronograma, ItemMedicaoComercial,
                        ItemMedicaoCronogramaTarefa, ObraServicoCusto)
    with app.app_context():
        admin_id = _novo_admin()
        res = importar_fisico_financeiro(_carregar_json(), admin_id)
        oid = res['obra_id']
        # Cronograma físico = espelho fiel das 101 tarefas do .mpp (06.07, split A/B), no outline.
        tarefas = TarefaCronograma.query.filter_by(obra_id=oid, admin_id=admin_id).all()
        assert len(tarefas) == 101
        raizes = [t for t in tarefas if t.tarefa_pai_id is None]
        assert len(raizes) == 1 and 'OBRA' in (raizes[0].nome_tarefa or '').upper()
        nomes = {(t.nome_tarefa or '').upper() for t in tarefas}
        # tarefa físico-pura (sem custo) presente, fiel ao .mpp
        assert any('FAZENDA' in n for n in nomes)
        # INDIRETOS é custo de período — NÃO vira tarefa do cronograma
        assert not any('INDIRETO' in n for n in nomes)
        assert ItemMedicaoComercial.query.filter_by(obra_id=oid).count() == 12
        # vínculo opcional custo↔tarefa: ao menos uma tarefa por etapa entregável
        assert ItemMedicaoCronogramaTarefa.query.filter_by(admin_id=admin_id).count() >= 11
        oscs = ObraServicoCusto.query.filter_by(obra_id=oid, admin_id=admin_id).all()
        soma_veks = sum(float(o.mao_obra_a_realizar or 0) for o in oscs)
        soma_fat = sum(float(o.material_a_realizar or 0) for o in oscs)
        # Veks total reconciliado pela Planilha1 (REV01 nova), indiretos 5 meses
        # = 800.960; fat_direto reconciliado = 550.775 (ESTMET 332.892 + FUND 87.882,64 + demais).
        assert abs(soma_veks - 800960) < 50
        assert abs(soma_fat - 550775) < 50


@pytest.mark.integration
def test_indiretos_e_periodo_na_baia():
    """F5 — na Baia, INDIRETOS é custo de período: aparece no painel como
    tipo='periodo' (sem % físico), veks 457.000, e NÃO vira tarefa do cronograma."""
    from services.importacao_fisico_financeiro import importar_fisico_financeiro
    from services.cronograma_fisico_financeiro import montar_fisico_financeiro
    from models import TarefaCronograma
    with app.app_context():
        admin_id = _novo_admin()
        oid = importar_fisico_financeiro(_carregar_json(), admin_id)['obra_id']
        dados = montar_fisico_financeiro(oid, admin_id)
        ind = [e for e in dados['etapas'] if 'INDIRET' in (e['nome'] or '').upper()]
        assert len(ind) == 1
        assert ind[0]['tipo'] == 'periodo'
        assert ind[0]['pct_fisico'] is None
        assert abs(float(ind[0]['veks']) - 457000) < 50
        # não materializou tarefa de indiretos no cronograma
        nomes = {(t.nome_tarefa or '').upper()
                 for t in TarefaCronograma.query.filter_by(obra_id=oid).all()}
        assert not any('INDIRETO' in n for n in nomes)


@pytest.mark.integration
def test_periodo_fora_do_cronograma_rdo_portal():
    """F7 — custo de período não vira TarefaCronograma. Como cronograma, RDO e portal
    do cliente listam SOMENTE TarefaCronograma, a ausência aqui garante a ausência nos
    três (invariante estrutural, não filtro)."""
    from services.importacao_fisico_financeiro import importar_fisico_financeiro
    from services.cronograma_fisico_financeiro import montar_fisico_financeiro
    from models import TarefaCronograma
    with app.app_context():
        admin_id = _novo_admin()
        oid = importar_fisico_financeiro(_carregar_json(), admin_id)['obra_id']
        dados = montar_fisico_financeiro(oid, admin_id)
        nomes_periodo = {(e['nome'] or '').upper()
                         for e in dados['etapas'] if e.get('tipo') == 'periodo'}
        assert nomes_periodo, "deveria haver ao menos um custo de período"
        nomes_tarefas = {(t.nome_tarefa or '').upper()
                         for t in TarefaCronograma.query.filter_by(obra_id=oid).all()}
        assert nomes_periodo.isdisjoint(nomes_tarefas)


@pytest.mark.integration
def test_painel_deriva_apos_import():
    from services.importacao_fisico_financeiro import importar_fisico_financeiro
    from services.cronograma_fisico_financeiro import montar_fisico_financeiro
    with app.app_context():
        admin_id = _novo_admin()
        oid = importar_fisico_financeiro(_carregar_json(), admin_id)['obra_id']
        dados = montar_fisico_financeiro(oid, admin_id)
        assert len(dados['etapas']) == 12
        assert dados['totais']['total'] > 0
        assert dados['meses_veks']


@pytest.mark.integration
def test_importa_medicoes_e_snapshot():
    from services.importacao_fisico_financeiro import importar_fisico_financeiro
    from models import Obra, MedicaoContrato, MedicaoObra
    with app.app_context():
        admin_id = _novo_admin()
        oid = importar_fisico_financeiro(_carregar_json(), admin_id)['obra_id']
        meds = MedicaoContrato.query.filter_by(obra_id=oid, admin_id=admin_id).all()
        assert len(meds) == 6
        assert abs(sum(float(m.pct) for m in meds) - 1.0) < 1e-6
        total = sum(float(m.valor) for m in meds)
        assert abs(total - 1505613.76) < 1.0
        assert MedicaoObra.query.filter_by(obra_id=oid).count() == 0
        snap = Obra.query.get(oid).fluxo_caixa_planilha
        # Modelo corrigido: junho/mobilização tributado → lucro em caixa = 24.976.
        assert snap and snap['lucro_caixa_final'] == 24976


@pytest.mark.integration
def test_reimport_nao_duplica():
    from services.importacao_fisico_financeiro import importar_fisico_financeiro
    from models import TarefaCronograma, MedicaoContrato, Obra
    with app.app_context():
        admin_id = _novo_admin()
        oid1 = importar_fisico_financeiro(_carregar_json(), admin_id)['obra_id']
        oid2 = importar_fisico_financeiro(_carregar_json(), admin_id)['obra_id']
        assert oid1 == oid2
        assert Obra.query.filter_by(admin_id=admin_id).count() == 1
        # cronograma não duplica: continua com as 101 tarefas do .mpp, 1 raiz (OBRA)
        assert TarefaCronograma.query.filter_by(obra_id=oid1).count() == 101
        assert TarefaCronograma.query.filter_by(obra_id=oid1, tarefa_pai_id=None).count() == 1
        assert MedicaoContrato.query.filter_by(obra_id=oid1).count() == 6


@pytest.mark.integration
def test_isolamento_multitenant():
    from services.importacao_fisico_financeiro import importar_fisico_financeiro
    from models import TarefaCronograma
    with app.app_context():
        a1 = _novo_admin()
        a2 = _novo_admin()
        o1 = importar_fisico_financeiro(_carregar_json(), a1)['obra_id']
        o2 = importar_fisico_financeiro(_carregar_json(), a2)['obra_id']
        assert o1 != o2
        assert TarefaCronograma.query.filter_by(obra_id=o1, admin_id=a2).count() == 0


@pytest.mark.integration
def test_wrappers_de_servico():
    from services.importacao_fisico_financeiro import importar_fisico_financeiro
    from services.cronograma_fisico_financeiro import (
        medicoes_contrato, fluxo_caixa, fluxo_caixa_divergencia, kpis)
    from models import Obra
    with app.app_context():
        admin_id = _novo_admin()
        oid = importar_fisico_financeiro(_carregar_json(), admin_id)['obra_id']
        obra = Obra.query.get(oid)

        meds = medicoes_contrato(obra)
        assert len(meds) == 6
        assert abs(sum(float(m['valor']) for m in meds) - 1505613.76) < 1.0

        fc = fluxo_caixa(obra)
        assert fc['linhas'] and 'lucro_em_caixa' in fc

        div = fluxo_caixa_divergencia(obra)
        # Modelo reconciliado (Indiretos 5 meses): Veks das etapas (800.960) bate
        # com o GASTO VEKS do snapshot → divergência ~0.
        assert abs(float(div['resumo']['delta_veks'])) < 2000

        k = kpis(obra)
        assert abs(float(k['venda']) - 1505613.76) < 1.0
        assert k['desembolso_veks'] > 0 and k['fat_direto'] > 0


@pytest.mark.integration
def test_rota_import_json_get_existe():
    with app.test_client() as c:
        resp = c.get('/importacao/fisico-financeiro')
        assert resp.status_code in (200, 302)


@pytest.mark.integration
def test_rota_import_json_post_importa_e_redireciona():
    import io
    from models import Obra
    app.config['TESTING'] = True
    app.config['WTF_CSRF_ENABLED'] = False
    if not app.secret_key:
        app.secret_key = 'test-secret-ff-post'

    with app.app_context():
        admin_id = _novo_admin()
        antes = Obra.query.filter_by(admin_id=admin_id).count()

    caminho = os.path.join(os.path.dirname(__file__), 'fixtures',
                           'cronograma_fisico_financeiro_baias.json')
    with open(caminho, 'rb') as f:
        json_bytes = f.read()

    c = app.test_client()
    with c.session_transaction() as sess:
        sess['_user_id'] = str(admin_id)
        sess['_fresh'] = True

    resp = c.post(
        '/importacao/fisico-financeiro',
        data={'arquivo': (io.BytesIO(json_bytes), 'baias.json')},
        content_type='multipart/form-data',
        follow_redirects=False,
    )
    assert resp.status_code == 302
    assert '/fisico-financeiro' in resp.headers['Location']

    with app.app_context():
        depois = Obra.query.filter_by(admin_id=admin_id).count()
        assert depois == antes + 1


@pytest.mark.integration
def test_importa_sem_cliente_falha_claramente():
    from services.importacao_fisico_financeiro import importar_fisico_financeiro
    with app.app_context():
        admin_id = _novo_admin()
        payload = _carregar_json()
        payload['obra'] = dict(payload['obra'])
        payload['obra'].pop('cliente', None)
        with pytest.raises(ValueError):
            importar_fisico_financeiro(payload, admin_id)


@pytest.mark.integration
def test_importa_retorna_avisos_como_lista():
    # No fixture Baias, TODAS as etapas (inclusive Indiretos/transversal) têm
    # tarefas_mpp não vazias, então nenhum aviso 'sem tarefas' é gerado.
    # Garantimos apenas que 'avisos' é uma lista no retorno.
    from services.importacao_fisico_financeiro import importar_fisico_financeiro
    with app.app_context():
        admin_id = _novo_admin()
        res = importar_fisico_financeiro(_carregar_json(), admin_id)
        assert isinstance(res['avisos'], list)


@pytest.mark.integration
def test_etapa_sem_tarefas_vira_periodo():
    # Etapa sem tarefas_mpp = custo de PERÍODO: não vira tarefa no cronograma,
    # não gera aviso 'sem tarefas', e aparece no painel com tipo='periodo'.
    from services.importacao_fisico_financeiro import importar_fisico_financeiro
    from services.cronograma_fisico_financeiro import montar_fisico_financeiro
    with app.app_context():
        admin_id = _novo_admin()
        payload = _carregar_json()
        payload['eap'] = [dict(e) for e in payload['eap']]
        alvo = payload['eap'][-1]
        alvo['cronograma'] = dict(alvo.get('cronograma', {}))
        alvo['cronograma']['tarefas_mpp'] = []
        res = importar_fisico_financeiro(payload, admin_id)
        assert not any('sem tarefas' in a.lower() for a in res['avisos'])
        dados = montar_fisico_financeiro(res['obra_id'], admin_id)
        periodo = [e for e in dados['etapas'] if e.get('tipo') == 'periodo']
        assert periodo, "etapa sem tarefas_mpp deveria virar tipo='periodo'"
        assert all(e.get('pct_fisico') is None for e in periodo)


@pytest.mark.integration
def test_painel_renderiza_apos_import():
    import io  # noqa
    from services.importacao_fisico_financeiro import importar_fisico_financeiro
    from models import Usuario
    with app.app_context():
        admin_id = _novo_admin()
        # O painel é guardado por _check_v2() → is_v2_active(), que exige
        # versao_sistema == 'v2' no admin do tenant. Sem isso a rota redireciona.
        admin = Usuario.query.get(admin_id)
        admin.versao_sistema = 'v2'
        db.session.commit()
        oid = importar_fisico_financeiro(_carregar_json(), admin_id)['obra_id']
    prev = app.config.get('WTF_CSRF_ENABLED', True)
    app.config['WTF_CSRF_ENABLED'] = False
    try:
        with app.test_client() as c:
            with c.session_transaction() as sess:
                sess['_user_id'] = str(admin_id)
                sess['_fresh'] = True
            # A rota standalone agora redireciona para a aba Financeiro da
            # página da obra (main.detalhes_obra → /obras/detalhes/<id>).
            resp = c.get(f'/cronograma/obra/{oid}/fisico-financeiro')
            assert resp.status_code in (301, 302)
            loc = resp.headers.get('Location', '')
            assert f'/obras/detalhes/{oid}' in loc and loc.endswith('#financeiro')
    finally:
        app.config['WTF_CSRF_ENABLED'] = prev


# ──────────────────────────────────────────────────────────────────────
# Fluxo comercial completo (Orçamento → Proposta → IMC/OSC), sem contábil
# ──────────────────────────────────────────────────────────────────────
@pytest.mark.integration
def test_importa_cria_orcamento_e_proposta():
    from services.importacao_fisico_financeiro import importar_fisico_financeiro
    from models import Orcamento, OrcamentoItem, Proposta, PropostaItem
    with app.app_context():
        admin_id = _novo_admin()
        res = importar_fisico_financeiro(_carregar_json(), admin_id)
        assert res['orcamento_id'] and res['proposta_id']

        orcs = Orcamento.query.filter_by(admin_id=admin_id).all()
        assert len(orcs) == 1
        assert OrcamentoItem.query.filter_by(orcamento_id=orcs[0].id).count() == 12

        prop = Proposta.query.filter_by(id=res['proposta_id'], admin_id=admin_id).first()
        assert prop is not None and prop.obra_id == res['obra_id']
        assert prop.orcamento_id == orcs[0].id
        assert PropostaItem.query.filter_by(proposta_id=prop.id).count() == 12
        # venda da proposta ≈ contrato (Σ peso_pct ≈ 1; pesos têm 4 casas no JSON)
        assert abs(float(orcs[0].venda_total) - 1505613.76) < 2000


@pytest.mark.integration
def test_importa_casa_insumos_no_catalogo():
    from services.importacao_fisico_financeiro import importar_fisico_financeiro
    from models import Insumo, ComposicaoServico, OrcamentoItem
    with app.app_context():
        admin_id = _novo_admin()
        res = importar_fisico_financeiro(_carregar_json(), admin_id)
        # itens de custo do JSON viraram Insumos do catálogo + composição
        assert Insumo.query.filter_by(admin_id=admin_id).count() > 0
        assert ComposicaoServico.query.filter_by(admin_id=admin_id).count() > 0
        # cada OrcamentoItem carrega um composicao_snapshot não vazio
        itens = OrcamentoItem.query.filter_by(admin_id=admin_id).all()
        assert all(isinstance(i.composicao_snapshot, list) for i in itens)
        assert any((i.composicao_snapshot or []) for i in itens)


@pytest.mark.integration
def test_importa_nao_gera_lancamento_contabil():
    from services.importacao_fisico_financeiro import importar_fisico_financeiro
    from models import LancamentoContabil
    with app.app_context():
        admin_id = _novo_admin()
        res = importar_fisico_financeiro(_carregar_json(), admin_id)
        # skip_contabil=True → nenhum lançamento contábil desta proposta
        lcs = LancamentoContabil.query.filter_by(
            admin_id=admin_id, origem='PROPOSTAS',
            origem_id=res['proposta_id']).count()
        assert lcs == 0


@pytest.mark.integration
def test_reimport_nao_duplica_orcamento_proposta():
    from services.importacao_fisico_financeiro import importar_fisico_financeiro
    from models import Orcamento, Proposta, OrcamentoItem, PropostaItem
    with app.app_context():
        admin_id = _novo_admin()
        importar_fisico_financeiro(_carregar_json(), admin_id)
        res2 = importar_fisico_financeiro(_carregar_json(), admin_id)
        assert Orcamento.query.filter_by(admin_id=admin_id).count() == 1
        assert Proposta.query.filter_by(admin_id=admin_id).count() == 1
        assert OrcamentoItem.query.filter_by(
            orcamento_id=res2['orcamento_id']).count() == 12
        assert PropostaItem.query.filter_by(
            proposta_id=res2['proposta_id']).count() == 12


@pytest.mark.integration
def test_importa_popula_linhas_de_custo():
    from services.importacao_fisico_financeiro import importar_fisico_financeiro
    from models import ObraServicoCusto, ObraServicoCustoItem
    from decimal import Decimal
    with app.app_context():
        admin_id = _novo_admin()
        oid = importar_fisico_financeiro(_carregar_json(), admin_id)['obra_id']
        oscs = ObraServicoCusto.query.filter_by(obra_id=oid, admin_id=admin_id).all()
        osc_ids = [o.id for o in oscs]
        linhas = ObraServicoCustoItem.query.filter(
            ObraServicoCustoItem.obra_servico_custo_id.in_(osc_ids)).all()
        assert len(linhas) >= 12  # ao menos uma linha por etapa
        soma_veks = sum(float(l.valor) for l in linhas if l.fonte == 'veks')
        soma_fat = sum(float(l.valor) for l in linhas if l.fonte == 'fat_direto')
        # Veks total reconciliado pela Planilha1 (REV01 nova), indiretos 5 meses
        # = 800.960; fat_direto reconciliado = 550.775 (ESTMET 332.892 + FUND 87.882,64 + demais).
        assert abs(soma_veks - 800960) < 50
        assert abs(soma_fat - 550775) < 50
        # agregado da OSC == soma das linhas (derivação)
        for o in oscs:
            v = sum(float(l.valor) for l in linhas
                    if l.obra_servico_custo_id == o.id and l.fonte == 'veks')
            assert abs(float(o.mao_obra_a_realizar or 0) - v) < 0.01


@pytest.mark.integration
def test_reimport_nao_duplica_linhas_de_custo():
    from services.importacao_fisico_financeiro import importar_fisico_financeiro
    from models import ObraServicoCusto, ObraServicoCustoItem
    with app.app_context():
        admin_id = _novo_admin()
        importar_fisico_financeiro(_carregar_json(), admin_id)
        oid = importar_fisico_financeiro(_carregar_json(), admin_id)['obra_id']
        osc_ids = [o.id for o in ObraServicoCusto.query.filter_by(
            obra_id=oid, admin_id=admin_id).all()]
        linhas = ObraServicoCustoItem.query.filter(
            ObraServicoCustoItem.obra_servico_custo_id.in_(osc_ids)).count()
        # mesma quantia das linhas de eap.itens (sem acumular do 1º import)
        assert linhas >= 12
        orfas = ObraServicoCustoItem.query.filter(
            ~ObraServicoCustoItem.obra_servico_custo_id.in_(osc_ids),
            ObraServicoCustoItem.admin_id == admin_id).count()
        assert orfas == 0


@pytest.mark.integration
def test_indiretos_transversais_viram_linhas_mensais():
    """Etapa transversal (custo de período) é explodida em linhas mensais
    (nome-base, datadas no mês; o rótulo 'mês/aa' é derivado das datas na UI)
    ponderadas pelo perfil da planilha, com o total conservado; etapas normais
    mantêm a janela única da etapa."""
    from services.importacao_fisico_financeiro import importar_fisico_financeiro
    from models import ObraServicoCusto, ObraServicoCustoItem
    with app.app_context():
        admin_id = _novo_admin()
        oid = importar_fisico_financeiro(_carregar_json(), admin_id)['obra_id']

        # OSC da etapa transversal "Indiretos / gestão (período)"
        ind = ObraServicoCusto.query.filter(
            ObraServicoCusto.obra_id == oid,
            ObraServicoCusto.admin_id == admin_id,
            ObraServicoCusto.nome.like('Indiretos%')).first()
        assert ind is not None
        linhas = ObraServicoCustoItem.query.filter_by(
            obra_servico_custo_id=ind.id).all()

        # 10 itens explodidos por mês (jun–out); itens só de um mês geram 1 linha.
        # Total de linhas = soma das entradas mensais dos itens (Indiretos REV01,
        # versão cara/5 meses): Escritório 5 + Empréstimo 4 + Miscelânea 5 +
        # Estadia 5 + Refeição 5 + Equipe Plaq. 1 + LSF 1 + Encarregado 4 +
        # Carro 5 + Ref. Encarregado 4 = 39.
        assert len(linhas) == 39
        # descrição é o nome-base (sem sufixo '(mês/aa)'); o mês vem das datas
        import re as _re
        _suf = _re.compile(
            r' \((jan|fev|mar|abr|mai|jun|jul|ago|set|out|nov|dez)/\d{2}\)$', _re.I)
        assert not any(_suf.search(l.descricao or '') for l in linhas)
        # vários períodos do mesmo nome-base+fonte (ex.: Escritório em 5 meses)
        from collections import Counter as _Counter
        _grp = _Counter((l.descricao, l.fonte) for l in linhas)
        assert any(c > 1 for c in _grp.values())
        # cada linha mensal cai dentro do seu mês (data_inicio.month == data_fim.month)
        assert all(l.data_inicio and l.data_fim
                   and l.data_inicio.month == l.data_fim.month for l in linhas)
        # total conservado (457.000, versão cara) e perfil mensal (jul é o pico)
        por_mes = {}
        for l in linhas:
            k = f"{l.data_inicio.year:04d}-{l.data_inicio.month:02d}"
            por_mes[k] = por_mes.get(k, 0.0) + float(l.valor)
        assert abs(sum(por_mes.values()) - 457000) < 1
        assert sorted(por_mes) == ['2026-06', '2026-07', '2026-08', '2026-09', '2026-10']
        assert por_mes['2026-07'] > por_mes['2026-06']   # jul é o pico do perfil

        # etapa normal (Fundação) NÃO é explodida por mês — janela única
        fund = ObraServicoCusto.query.filter(
            ObraServicoCusto.obra_id == oid,
            ObraServicoCusto.admin_id == admin_id,
            ObraServicoCusto.nome.like('Fundação%')).first()
        assert fund is not None
        linhas_f = ObraServicoCustoItem.query.filter_by(
            obra_servico_custo_id=fund.id).all()
        assert all('/' not in (l.descricao or '') for l in linhas_f)


@pytest.mark.integration
def test_importacao_descricao_periodo_sem_sufixo_mes():
    """Linhas de custo de período (INDIRETOS) gravam a descrição-base, sem '(mês/aa)'."""
    import re, json, os
    from services.importacao_fisico_financeiro import importar_fisico_financeiro
    from models import ObraServicoCusto, ObraServicoCustoItem
    with app.app_context():
        aid = _novo_admin()
        caminho = os.path.join(os.path.dirname(__file__), 'fixtures',
                               'cronograma_fisico_financeiro_baias.json')
        oid = importar_fisico_financeiro(json.load(open(caminho, encoding='utf-8')), aid)['obra_id']
        osc_ids = [o.id for o in ObraServicoCusto.query.filter_by(obra_id=oid, admin_id=aid).all()]
        itens = ObraServicoCustoItem.query.filter(
            ObraServicoCustoItem.obra_servico_custo_id.in_(osc_ids)).all()
        sufixo = re.compile(r' \((jan|fev|mar|abr|mai|jun|jul|ago|set|out|nov|dez)/\d{2}\)$', re.I)
        assert itens, "esperado ao menos um item importado"
        assert not any(sufixo.search(it.descricao) for it in itens), \
            "nenhuma descrição deve terminar com '(mês/aa)'"
        # ainda existem múltiplos períodos do mesmo grupo (mesma descricao+fonte)
        from collections import Counter
        chaves = Counter((it.descricao, it.fonte) for it in itens)
        assert any(c > 1 for c in chaves.values()), \
            "esperado ao menos um grupo com vários períodos (ex.: Escritório veks)"


def test_import_cria_rdos_da_secao_rdos():
    """Import com seção `rdos` cria 1 RDO por item e sincroniza o % das tarefas."""
    import json, os
    from services.importacao_fisico_financeiro import importar_fisico_financeiro
    from models import RDO, TarefaCronograma
    with app.app_context():
        aid = _novo_admin()
        caminho = os.path.join(os.path.dirname(__file__), 'fixtures',
                               'cronograma_fisico_financeiro_baias.json')
        payload = json.load(open(caminho, encoding='utf-8'))
        # injeta uma seção rdos mínima (independente do conteúdo final da fixture)
        payload['rdos'] = [
            {"data": "2026-06-22", "clima": "Nublado", "precipitacao": "Sem chuva",
             "comentario": "Topografia.", "mao_de_obra": 0,
             "apontamentos": [{"tarefa_mpp": 2, "pct": 100}, {"tarefa_mpp": 3, "pct": 50}]},
            {"data": "2026-06-27", "clima": "Ensolarado", "precipitacao": "Sem chuva",
             "comentario": "Nivelamento galpão B.", "mao_de_obra": 0,
             "apontamentos": [{"tarefa_mpp": 2, "pct": 100}, {"tarefa_mpp": 3, "pct": 65},
                              {"tarefa_mpp": 5, "pct": 20}]},
        ]
        oid = importar_fisico_financeiro(payload, aid)['obra_id']
        assert RDO.query.filter_by(obra_id=oid, admin_id=aid).count() == 2
        por_nome = {t.nome_tarefa: t for t in
                    TarefaCronograma.query.filter_by(obra_id=oid, admin_id=aid).all()}
        assert float(por_nome['Estudo de Solo SPT'].percentual_concluido) == 100.0
        assert float(por_nome['Execução de projetos LSF, Telhado, Piso, Baldrame, Fundação para Pilares de Madeira'].percentual_concluido) == 65.0
        assert float(por_nome['Fazenda: Nivelamento dos Platôs'].percentual_concluido) == 20.0
        assert float(por_nome['Mobilização Equipe'].percentual_concluido) == 0.0


def test_apontamento_quantitativo_deriva_percentual_e_acumula():
    """Tarefa com `quantidade_total` + apontamentos por `quantidade` derivam o % da
    tarefa (acumulada/total) e acumulam entre RDOs; a quantidade fica gravada no
    apontamento (executada_dia por dia, acumulada corrente)."""
    import json, os
    from datetime import date
    from services.importacao_fisico_financeiro import importar_fisico_financeiro
    from models import TarefaCronograma, RDOApontamentoCronograma, RDO
    with app.app_context():
        aid = _novo_admin()
        caminho = os.path.join(os.path.dirname(__file__), 'fixtures',
                               'cronograma_fisico_financeiro_baias.json')
        payload = json.load(open(caminho, encoding='utf-8'))
        # t15 já tem quantidade_total=48 na fixture; aponta 10 e depois +15
        payload['rdos'] = [
            {"data": "2026-06-30", "apontamentos": [{"tarefa_mpp": 14, "quantidade": 10}]},
            {"data": "2026-07-01", "apontamentos": [{"tarefa_mpp": 14, "quantidade": 15}]},
        ]
        oid = importar_fisico_financeiro(payload, aid)['obra_id']
        # 2 tarefas homônimas (Galpão A/B); a com quantidade_total é a do apontamento
        t15 = (TarefaCronograma.query
               .filter_by(obra_id=oid, admin_id=aid)
               .filter(TarefaCronograma.quantidade_total.isnot(None)).first())
        assert float(t15.quantidade_total) == 48.0
        # acumulado 25/48 = 52,08%
        assert float(t15.percentual_concluido) == 52.08
        aps = (RDOApontamentoCronograma.query
               .join(RDO, RDO.id == RDOApontamentoCronograma.rdo_id)
               .filter(RDOApontamentoCronograma.tarefa_cronograma_id == t15.id)
               .order_by(RDO.data_relatorio).all())
        assert [a.quantidade_executada_dia for a in aps] == [10.0, 15.0]
        assert [a.quantidade_acumulada for a in aps] == [10.0, 25.0]


def test_apontamento_percentual_grava_incremento_diario():
    """Modo percentual direto (JSON traz o % acumulado): o incremento diário é a
    diferença para o acumulado anterior da mesma tarefa — não fica sempre 0."""
    import json, os
    from services.importacao_fisico_financeiro import importar_fisico_financeiro
    from models import TarefaCronograma, RDOApontamentoCronograma, RDO
    with app.app_context():
        aid = _novo_admin()
        caminho = os.path.join(os.path.dirname(__file__), 'fixtures',
                               'cronograma_fisico_financeiro_baias.json')
        payload = json.load(open(caminho, encoding='utf-8'))
        payload['rdos'] = [
            {"data": "2026-06-22", "apontamentos": [{"tarefa_mpp": 3, "pct": 50}]},
            {"data": "2026-06-23", "apontamentos": [{"tarefa_mpp": 3, "pct": 55}]},
            {"data": "2026-06-24", "apontamentos": [{"tarefa_mpp": 3, "pct": 65}]},
        ]
        oid = importar_fisico_financeiro(payload, aid)['obra_id']
        t4 = (TarefaCronograma.query
              .filter_by(obra_id=oid, admin_id=aid)
              .filter(TarefaCronograma.nome_tarefa.like('Execução de projetos%')).first())
        aps = (RDOApontamentoCronograma.query
               .join(RDO, RDO.id == RDOApontamentoCronograma.rdo_id)
               .filter(RDOApontamentoCronograma.tarefa_cronograma_id == t4.id)
               .order_by(RDO.data_relatorio).all())
        # primeiro dia = 50 (partindo de 0); depois +5 e +10
        assert [a.quantidade_executada_dia for a in aps] == [50.0, 5.0, 10.0]
        assert [a.percentual_realizado for a in aps] == [50.0, 55.0, 65.0]


def test_import_rdos_idempotente_e_opcional():
    """Reimportar não duplica RDOs; payload sem `rdos` não cria nada e não quebra."""
    import json, os
    from services.importacao_fisico_financeiro import importar_fisico_financeiro
    from models import RDO
    with app.app_context():
        aid = _novo_admin()
        caminho = os.path.join(os.path.dirname(__file__), 'fixtures',
                               'cronograma_fisico_financeiro_baias.json')
        payload = json.load(open(caminho, encoding='utf-8'))
        payload['rdos'] = [
            {"data": "2026-06-22", "apontamentos": [{"tarefa_mpp": 3, "pct": 100}]},
        ]
        oid = importar_fisico_financeiro(payload, aid)['obra_id']
        importar_fisico_financeiro(payload, aid)  # reimport
        assert RDO.query.filter_by(obra_id=oid, admin_id=aid).count() == 1

        sem = json.load(open(caminho, encoding='utf-8'))
        sem.pop('rdos', None)
        aid2 = _novo_admin()
        oid2 = importar_fisico_financeiro(sem, aid2)['obra_id']
        assert RDO.query.filter_by(obra_id=oid2, admin_id=aid2).count() == 0


def test_fixture_baia_traz_rdos_do_relatorio():
    """A fixture canônica da Baia contém os RDOs diários do relatório (22/06–13/07) e o
    import reproduz o físico acumulado: solo 100%, projetos 65%,
    nivelamento do platô 100%, gabarito 100% (Galpões A e B), ferragens 100%
    (48 de 48 brocas — modo quantitativo), escavação de baldrames e brocas 100%
    (fundações profundas dos dois galpões concluídas)."""
    import json, os
    from services.importacao_fisico_financeiro import importar_fisico_financeiro
    from models import RDO, TarefaCronograma
    with app.app_context():
        aid = _novo_admin()
        caminho = os.path.join(os.path.dirname(__file__), 'fixtures',
                               'cronograma_fisico_financeiro_baias.json')
        payload = json.load(open(caminho, encoding='utf-8'))
        assert len(payload.get('rdos', [])) == 26
        oid = importar_fisico_financeiro(payload, aid)['obra_id']
        assert RDO.query.filter_by(obra_id=oid, admin_id=aid).count() == 26
        por_nome = {t.nome_tarefa: float(t.percentual_concluido or 0) for t in
                    TarefaCronograma.query.filter_by(obra_id=oid, admin_id=aid).all()}
        assert por_nome['Estudo de Solo SPT'] == 100.0
        assert por_nome['Execução de projetos LSF, Telhado, Piso, Baldrame, Fundação para Pilares de Madeira'] == 65.0
        assert por_nome['Fazenda: Nivelamento dos Platôs'] == 100.0
        assert por_nome['Execução de Gabarito'] == 100.0
        # ferragens das brocas (id14, quantitativo 48/48) concluída até 06/07
        ferr = (TarefaCronograma.query.filter_by(obra_id=oid, admin_id=aid)
                .filter(TarefaCronograma.quantidade_total.isnot(None)).first())
        assert round(float(ferr.percentual_concluido), 2) == 100.0  # 48/48
        # escavações (baldrames e brocas) concluídas nos dois galpões
        escav = [float(t.percentual_concluido or 0) for t in
                 TarefaCronograma.query.filter_by(obra_id=oid, admin_id=aid).all()
                 if t.nome_tarefa in ('Escavação De Fundação Para Baldrames', 'Escavação Das Brocas')]
        assert escav and all(v == 100.0 for v in escav)
        assert por_nome['Mobilização Equipe'] == 0.0


def test_calcular_progresso_rdo_fallback_sem_quantidade_total():
    """Tarefa sem quantidade_total: realizado = percentual_realizado do último
    apontamento até a data (antes era sempre 0)."""
    import json, os
    from datetime import date
    from services.importacao_fisico_financeiro import importar_fisico_financeiro
    from utils.cronograma_engine import calcular_progresso_rdo
    from models import TarefaCronograma
    with app.app_context():
        aid = _novo_admin()
        caminho = os.path.join(os.path.dirname(__file__), 'fixtures',
                               'cronograma_fisico_financeiro_baias.json')
        oid = importar_fisico_financeiro(json.load(open(caminho, encoding='utf-8')), aid)['obra_id']
        projetos = (TarefaCronograma.query
                    .filter_by(obra_id=oid, admin_id=aid)
                    .filter(TarefaCronograma.nome_tarefa.like('Execução de projetos%'))
                    .first())
        assert projetos is not None and not projetos.quantidade_total
        # antes do 1º apontamento (22/06) → 0
        r21 = calcular_progresso_rdo(projetos.id, date(2026, 6, 21), aid)
        assert r21['percentual_realizado'] == 0.0
        # 22/06 → 50 (primeiro apontamento); 27/06 → 65 (acumulado)
        assert calcular_progresso_rdo(projetos.id, date(2026, 6, 22), aid)['percentual_realizado'] == 50.0
        assert calcular_progresso_rdo(projetos.id, date(2026, 6, 27), aid)['percentual_realizado'] == 65.0


def test_progresso_geral_obra_cresce_por_data():
    """O progresso acumulado da obra (usado nos cards de RDO) é > 0 e cresce de
    22/06 para 27/06."""
    import json, os
    from datetime import date
    from services.importacao_fisico_financeiro import importar_fisico_financeiro
    from utils.cronograma_engine import calcular_progresso_geral_obra_v2
    with app.app_context():
        aid = _novo_admin()
        caminho = os.path.join(os.path.dirname(__file__), 'fixtures',
                               'cronograma_fisico_financeiro_baias.json')
        oid = importar_fisico_financeiro(json.load(open(caminho, encoding='utf-8')), aid)['obra_id']
        p22 = calcular_progresso_geral_obra_v2(oid, date(2026, 6, 22), aid)['progresso_geral_pct']
        p27 = calcular_progresso_geral_obra_v2(oid, date(2026, 6, 27), aid)['progresso_geral_pct']
        assert 0 < p22 < p27 < 100


def test_cronograma_header_usa_progresso_v2():
    """O header 'Progresso Geral' do cronograma usa calcular_progresso_geral_obra_v2
    (média das folhas ponderada por duração), não a média simples de todas as tarefas."""
    import json, os
    from datetime import date
    from services.importacao_fisico_financeiro import importar_fisico_financeiro
    from utils.cronograma_engine import calcular_progresso_geral_obra_v2
    from models import Usuario
    with app.app_context():
        aid = _novo_admin()
        u = Usuario.query.get(aid); u.versao_sistema = 'v2'; db.session.commit()
        caminho = os.path.join(os.path.dirname(__file__), 'fixtures',
                               'cronograma_fisico_financeiro_baias.json')
        oid = importar_fisico_financeiro(json.load(open(caminho, encoding='utf-8')), aid)['obra_id']
        # header exibido com 1 casa decimal (idêntico ao portal)
        esperado = "%.1f" % calcular_progresso_geral_obra_v2(oid, date.today(), aid)['progresso_geral_pct']
    with app.test_client() as c:
        with c.session_transaction() as s:
            s['_user_id'] = str(aid); s['_fresh'] = True
        r = c.get(f'/cronograma/obra/{oid}')
        assert r.status_code == 200
        html = r.get_data(as_text=True)
        assert f'id="statPercGeral">{esperado}%' in html


def test_cronograma_linha_raiz_alinha_progresso_v2():
    """A linha raiz (OBRA) do cronograma exibe o mesmo progresso do header/card
    (calcular_progresso_geral_obra_v2), não o rollup hierárquico persistido."""
    import json, os, re
    from datetime import date
    from services.importacao_fisico_financeiro import importar_fisico_financeiro
    from utils.cronograma_engine import calcular_progresso_geral_obra_v2
    from models import Usuario, TarefaCronograma
    with app.app_context():
        aid = _novo_admin()
        u = Usuario.query.get(aid); u.versao_sistema = 'v2'; db.session.commit()
        caminho = os.path.join(os.path.dirname(__file__), 'fixtures',
                               'cronograma_fisico_financeiro_baias.json')
        oid = importar_fisico_financeiro(json.load(open(caminho, encoding='utf-8')), aid)['obra_id']
        # data-perc da raiz = `progresso_geral_header|int` no template (trunca), com a
        # métrica v2 calculada em `hoje` no route — espelhamos o mesmo int() aqui.
        esperado = int(calcular_progresso_geral_obra_v2(oid, date.today(), aid)['progresso_geral_pct'])
        raiz = (TarefaCronograma.query
                .filter_by(obra_id=oid, admin_id=aid, tarefa_pai_id=None).first())
        raiz_id = raiz.id  # captura antes do commit (evita DetachedInstanceError)
        # força o rollup persistido a um valor distinto da métrica v2, para provar que
        # o display usa a v2 (override no route/template), não o rollup gravado — robusto
        # à evolução do físico (o rollup natural podia coincidir com a v2 e esvaziar o teste).
        forcado = 5.0 if esperado != 5 else 95.0
        raiz.percentual_concluido = forcado
        db.session.commit()
        assert int(forcado) != esperado
    with app.test_client() as c:
        with c.session_transaction() as s:
            s['_user_id'] = str(aid); s['_fresh'] = True
        r = c.get(f'/cronograma/obra/{oid}')
        assert r.status_code == 200
        html = r.get_data(as_text=True)
        # a <tr> da raiz tem data-pai="" e data-perc = métrica v2
        m = re.search(r'data-id="%d"[^>]*data-perc="(\d+)"' % raiz_id, html)
        assert m is not None and int(m.group(1)) == esperado


def test_portal_cliente_usa_progresso_v2():
    """O anel de progresso do portal do cliente usa calcular_progresso_geral_obra_v2
    (mesma métrica do cronograma/RDO), não a média simples de todas as tarefas."""
    import json, os
    from datetime import date
    from services.importacao_fisico_financeiro import importar_fisico_financeiro
    from utils.cronograma_engine import calcular_progresso_geral_obra_v2
    from models import Obra
    with app.app_context():
        aid = _novo_admin()
        caminho = os.path.join(os.path.dirname(__file__), 'fixtures',
                               'cronograma_fisico_financeiro_baias.json')
        oid = importar_fisico_financeiro(json.load(open(caminho, encoding='utf-8')), aid)['obra_id']
        o = Obra.query.get(oid)
        o.token_cliente = f'tok-test-{oid}'
        o.portal_ativo = True
        db.session.commit()
        token = o.token_cliente
        esperado = round(calcular_progresso_geral_obra_v2(oid, date.today(), aid)['progresso_geral_pct'], 1)
    with app.test_client() as c:
        r = c.get(f'/portal/obra/{token}')
        assert r.status_code == 200
        html = r.get_data(as_text=True)
        assert f'>{esperado}%<' in html


def test_portal_cronograma_raiz_alinha_progresso_v2():
    """A linha raiz do cronograma do portal mostra o mesmo número do anel
    (calcular_progresso_geral_obra_v2), não o rollup hierárquico persistido."""
    import json, os
    from datetime import date
    from services.importacao_fisico_financeiro import importar_fisico_financeiro
    from utils.cronograma_engine import calcular_progresso_geral_obra_v2
    from models import Obra, TarefaCronograma
    with app.app_context():
        aid = _novo_admin()
        caminho = os.path.join(os.path.dirname(__file__), 'fixtures',
                               'cronograma_fisico_financeiro_baias.json')
        oid = importar_fisico_financeiro(json.load(open(caminho, encoding='utf-8')), aid)['obra_id']
        o = Obra.query.get(oid)
        o.token_cliente = f'tok-cli-{oid}'
        o.portal_ativo = True
        # cronograma do cliente: raiz com rollup alto (99) + 1 filho (50)
        raiz = TarefaCronograma(obra_id=oid, admin_id=aid, nome_tarefa='OBRA (cliente)',
                                is_cliente=True, percentual_concluido=99.0, ordem=0)
        db.session.add(raiz); db.session.flush()
        db.session.add(TarefaCronograma(obra_id=oid, admin_id=aid, nome_tarefa='Etapa cliente',
                                        is_cliente=True, tarefa_pai_id=raiz.id,
                                        percentual_concluido=50.0, ordem=1))
        db.session.commit()
        token = o.token_cliente
        esperado = round(calcular_progresso_geral_obra_v2(oid, date.today(), aid)['progresso_geral_pct'], 1)
    with app.test_client() as c:
        r = c.get(f'/portal/obra/{token}')
        assert r.status_code == 200
        html = r.get_data(as_text=True)
        # a raiz mostra perc_geral; o rollup antigo (99) não aparece
        assert f'{esperado}%' in html
        assert '99.0%' not in html


def test_fixture_rdos_sem_mao_de_obra():
    """Os RDOs da Baia não trazem mão de obra no import (o usuário adiciona ao editar)."""
    import json, os
    from services.importacao_fisico_financeiro import importar_fisico_financeiro
    from models import RDO, RDOMaoObra
    caminho = os.path.join(os.path.dirname(__file__), 'fixtures',
                           'cronograma_fisico_financeiro_baias.json')
    d = json.load(open(caminho, encoding='utf-8'))
    assert all((r.get('mao_de_obra') or 0) == 0 for r in d['rdos'])
    with app.app_context():
        aid = _novo_admin()
        oid = importar_fisico_financeiro(d, aid)['obra_id']
        rdo_ids = [r.id for r in RDO.query.filter_by(obra_id=oid, admin_id=aid).all()]
        assert len(rdo_ids) == 26
        assert RDOMaoObra.query.filter(RDOMaoObra.rdo_id.in_(rdo_ids)).count() == 0


@pytest.mark.integration
def test_import_cria_rdos_em_estado_preenchido():
    """Fase 5 — o RDO importado é histórico consolidado (dirige a medição
    pelos apontamentos), não um rascunho a submeter. Tem de nascer
    'preenchido', coerente com o status='Finalizado' que o importador já
    grava e com o backfill da migration 260.

    Se cair no default do modelo ('rascunho'), a tela mostra "Submeter" e
    submeter dispararia rdo_finalizado → lancar_custos_rdo sobre uma
    medição que a importação já dirigiu — custo em duplicidade.
    """
    from services.importacao_fisico_financeiro import importar_fisico_financeiro
    from services.rdo_ciclo_vida import PREENCHIDO
    from models import RDO

    with app.app_context():
        admin_id = _novo_admin()
        oid = importar_fisico_financeiro(_carregar_json(), admin_id)['obra_id']
        rdos = RDO.query.filter_by(obra_id=oid).all()
        assert rdos, 'a fixture tem seção rdos — deveria ter criado RDOs'
        assert all(r.estado == PREENCHIDO for r in rdos), (
            'RDO importado nasceu em %r, deveria ser preenchido' %
            {r.estado for r in rdos})
        # o campo legado continua 'Finalizado' (≥9 consumidores filtram por ele)
        assert all(r.status == 'Finalizado' for r in rdos)


def test_import_anexa_fotos_do_rdo(tmp_path):
    """Um RDO com `fotos` (legendas em ordem) anexa RDOFoto lendo os arquivos
    numerados de fotos_rdos/<data>/; a legenda e os arquivos em disco são
    persistidos, e uma foto ausente é pulada sem quebrar o import.

    Fase 5 (opção B): sem UPLOADS_PATH no ambiente de teste (disco efêmero),
    a foto nasce 'banco' com base64 — a rede de segurança do deploy."""
    import json, os
    from PIL import Image
    from services import importacao_fisico_financeiro as ff
    from services.importacao_fisico_financeiro import importar_fisico_financeiro
    from models import RDO, RDOFoto

    # pasta de fotos do dia 2026-06-22 com 1.png e 2.png (a 3ª legenda fica órfã)
    dia_dir = tmp_path / '2026-06-22'
    dia_dir.mkdir()
    for n in (1, 2):
        Image.new('RGB', (8, 8), (10 * n, 20, 30)).save(dia_dir / f'{n}.png')

    caminho = os.path.join(os.path.dirname(__file__), 'fixtures',
                           'cronograma_fisico_financeiro_baias.json')
    payload = json.load(open(caminho, encoding='utf-8'))
    payload['rdos'] = [{
        "data": "2026-06-22", "clima": "Nublado", "mao_de_obra": 0,
        "comentario": "Topografia.",
        "apontamentos": [{"tarefa_mpp": 3, "pct": 100}],
        "fotos": ["Nível do platô", "Gabarito da Baia 01", "Foto que falta"],
    }]

    with app.app_context():
        aid = _novo_admin()
        old_base = ff.FOTOS_RDO_BASE
        ff.FOTOS_RDO_BASE = str(tmp_path)
        try:
            oid = importar_fisico_financeiro(payload, aid)['obra_id']
        finally:
            ff.FOTOS_RDO_BASE = old_base

        rdo = RDO.query.filter_by(obra_id=oid, admin_id=aid).first()
        fotos = RDOFoto.query.filter_by(rdo_id=rdo.id).order_by(RDOFoto.ordem).all()
        # 2 fotos anexadas (a 3ª foi pulada por não ter arquivo)
        assert len(fotos) == 2
        assert [f.legenda for f in fotos] == ["Nível do platô", "Gabarito da Baia 01"]
        assert all(f.arquivo_otimizado and f.thumbnail for f in fotos)
        assert all(f.nome_arquivo and f.caminho_arquivo for f in fotos)  # legados NOT NULL
        # Sem volume (default do teste): 'banco' + base64 preservada.
        assert all(f.armazenamento == 'banco' for f in fotos)
        assert all(f.imagem_otimizada_base64 for f in fotos)


def test_import_auto_anexa_fotos_da_pasta_sem_legenda(tmp_path):
    """RDO SEM `fotos` no JSON, mas com imagens na pasta do dia, anexa todas as
    fotos (ordem numérica) com legenda vazia."""
    import json, os
    from PIL import Image
    from services import importacao_fisico_financeiro as ff
    from services.importacao_fisico_financeiro import importar_fisico_financeiro
    from models import RDO, RDOFoto

    dia_dir = tmp_path / '2026-06-29'
    dia_dir.mkdir()
    for n in (1, 2, 3):
        Image.new('RGB', (8, 8), (n * 20, 0, 0)).save(dia_dir / f'{n}.jpeg')

    caminho = os.path.join(os.path.dirname(__file__), 'fixtures',
                           'cronograma_fisico_financeiro_baias.json')
    payload = json.load(open(caminho, encoding='utf-8'))
    # RDO sem chave 'fotos' — as imagens da pasta devem ser anexadas mesmo assim
    payload['rdos'] = [{"data": "2026-06-29", "comentario": "sem legenda",
                        "apontamentos": [{"tarefa_mpp": 6, "pct": 60}]}]

    with app.app_context():
        aid = _novo_admin()
        old = ff.FOTOS_RDO_BASE
        ff.FOTOS_RDO_BASE = str(tmp_path)
        try:
            oid = importar_fisico_financeiro(payload, aid)['obra_id']
        finally:
            ff.FOTOS_RDO_BASE = old
        rdo = RDO.query.filter_by(obra_id=oid, admin_id=aid).first()
        fotos = RDOFoto.query.filter_by(rdo_id=rdo.id).order_by(RDOFoto.ordem).all()
        assert len(fotos) == 3
        assert all((f.legenda or '') == '' for f in fotos)
        assert all(f.arquivo_otimizado for f in fotos)
        # Sem volume (default do teste): 'banco' + base64 preservada.
        assert all(f.armazenamento == 'banco' for f in fotos)


def test_portal_rdo_foto_sem_prefixo_base64_duplicado(tmp_path):
    """A foto importada aparece no portal com UM único prefixo
    `data:image/...;base64,` — regressão do bug que duplicava o prefixo.

    Fase 5 (opção B): sem UPLOADS_PATH (disco efêmero, default do teste) a
    foto guarda base64, então o portal a renderiza como data URI — e o
    invariante é que o prefixo nunca aparece duplicado."""
    import json, os
    from PIL import Image
    from services import importacao_fisico_financeiro as ff
    from services.importacao_fisico_financeiro import importar_fisico_financeiro
    from models import Obra, RDO

    dia_dir = tmp_path / '2026-06-30'
    dia_dir.mkdir()
    Image.new('RGB', (8, 8), (10, 20, 30)).save(dia_dir / '1.png')

    caminho = os.path.join(os.path.dirname(__file__), 'fixtures',
                           'cronograma_fisico_financeiro_baias.json')
    payload = json.load(open(caminho, encoding='utf-8'))
    payload['rdos'] = [{"data": "2026-06-30", "comentario": "x",
                        "apontamentos": [{"tarefa_mpp": 6, "pct": 60}],
                        "fotos": ["Foto teste"]}]

    with app.app_context():
        aid = _novo_admin()
        old = ff.FOTOS_RDO_BASE
        ff.FOTOS_RDO_BASE = str(tmp_path)
        try:
            oid = importar_fisico_financeiro(payload, aid)['obra_id']
        finally:
            ff.FOTOS_RDO_BASE = old
        token = f'tok-foto-rdo-{aid}'  # único por run (o DB Postgres não faz rollback)
        obra = Obra.query.get(oid)
        obra.token_cliente = token
        obra.portal_ativo = True
        db.session.commit()
        rdo_id = RDO.query.filter_by(obra_id=oid, admin_id=aid).first().id

    with app.test_client() as c:
        r = c.get(f'/portal/obra/{token}/rdo/{rdo_id}')
        assert r.status_code == 200
        html = r.get_data(as_text=True)
        # Sem volume: base64 preservada → portal renderiza data URI.
        assert 'data:image/webp;base64,' in html            # a foto renderiza
        assert 'data:image/webp;base64,data:' not in html   # sem prefixo duplicado


def test_import_apontamento_grava_percentual_planejado():
    """O import grava o percentual_planejado (curva do cronograma) nos apontamentos.
    A tela do RDO lê o valor ARMAZENADO — sem isto ficava tudo 'Sem plano'."""
    import json, os
    from services.importacao_fisico_financeiro import importar_fisico_financeiro
    from models import RDOApontamentoCronograma, TarefaCronograma
    with app.app_context():
        aid = _novo_admin()
        caminho = os.path.join(os.path.dirname(__file__), 'fixtures',
                               'cronograma_fisico_financeiro_baias.json')
        oid = importar_fisico_financeiro(
            json.load(open(caminho, encoding='utf-8')), aid)['obra_id']
        t = (TarefaCronograma.query
             .filter_by(obra_id=oid, admin_id=aid, is_cliente=False,
                        nome_tarefa='Estudo de Solo SPT').first())
        assert t.data_inicio is not None
        aps = RDOApontamentoCronograma.query.filter_by(
            tarefa_cronograma_id=t.id, admin_id=aid).all()
        assert aps  # há apontamentos para a tarefa
        # tarefa com datas -> planejado calculado e gravado (não None/'Sem plano')
        assert all(a.percentual_planejado is not None for a in aps)


def test_portal_cronograma_cliente_reflete_progresso_real():
    """A árvore do cronograma do cliente (is_cliente=True, que não recebe sync de
    RDO) reflete no portal o % REAL da tarefa interna de mesmo nome — não fica
    congelada em 0%."""
    import json, os
    from services.importacao_fisico_financeiro import importar_fisico_financeiro
    from models import Obra, TarefaCronograma
    with app.app_context():
        aid = _novo_admin()
        caminho = os.path.join(os.path.dirname(__file__), 'fixtures',
                               'cronograma_fisico_financeiro_baias.json')
        oid = importar_fisico_financeiro(
            json.load(open(caminho, encoding='utf-8')), aid)['obra_id']
        interna = (TarefaCronograma.query
                   .filter_by(obra_id=oid, admin_id=aid, is_cliente=False,
                              nome_tarefa='Execução de Gabarito').first())
        assert float(interna.percentual_concluido) == 100.0  # sincronizado do RDO (gabarito concluído 01/07)

        obra = Obra.query.get(oid)
        token = f'tok-cli-{aid}'
        obra.token_cliente = token
        obra.portal_ativo = True
        # cronograma-cliente CONGELADO em 0%: raiz OBRA + folha GABARITO (mesmo nome)
        raiz = TarefaCronograma(obra_id=oid, admin_id=aid, nome_tarefa='OBRA',
                                is_cliente=True, percentual_concluido=0.0,
                                ordem=1, duracao_dias=1)
        db.session.add(raiz); db.session.flush()
        db.session.add(TarefaCronograma(
            obra_id=oid, admin_id=aid, nome_tarefa='Execução de Gabarito',
            is_cliente=True, percentual_concluido=0.0, ordem=2,
            duracao_dias=1, tarefa_pai_id=raiz.id))
        db.session.commit()

    with app.test_client() as c:
        r = c.get(f'/portal/obra/{token}')
        assert r.status_code == 200
        html = r.get_data(as_text=True)
        assert 'Execução de Gabarito' in html
        assert '100.0%' in html   # % real (sincronizado), não 0.0% congelado


def test_reimport_sem_arquivos_preserva_fotos_do_rdo(tmp_path):
    """Importar com fotos, apagar os arquivos da pasta e reimportar NÃO perde as
    fotos já anexadas (ficam em base64 no banco); reimportar com arquivos novos
    substitui."""
    import json, os
    from PIL import Image
    from services import importacao_fisico_financeiro as ff
    from services.importacao_fisico_financeiro import importar_fisico_financeiro
    from models import RDO, RDOFoto

    dia_dir = tmp_path / '2026-06-22'
    dia_dir.mkdir()
    for n in (1, 2):
        Image.new('RGB', (8, 8), (10 * n, 20, 30)).save(dia_dir / f'{n}.png')

    caminho = os.path.join(os.path.dirname(__file__), 'fixtures',
                           'cronograma_fisico_financeiro_baias.json')
    payload = json.load(open(caminho, encoding='utf-8'))
    payload['rdos'] = [{
        "data": "2026-06-22", "clima": "Nublado", "mao_de_obra": 0,
        "comentario": "Topografia.",
        "apontamentos": [{"tarefa_mpp": 3, "pct": 100}],
        "fotos": ["Nível do platô", "Gabarito da Baia 01"],
    }]

    def _fotos(oid, aid):
        rdo = RDO.query.filter_by(obra_id=oid, admin_id=aid).first()
        return RDOFoto.query.filter_by(rdo_id=rdo.id).order_by(RDOFoto.ordem).all()

    with app.app_context():
        aid = _novo_admin()
        old_base = ff.FOTOS_RDO_BASE
        ff.FOTOS_RDO_BASE = str(tmp_path)
        try:
            # 1) 1º import: 2 fotos vêm da pasta
            oid = importar_fisico_financeiro(payload, aid)['obra_id']
            assert [f.legenda for f in _fotos(oid, aid)] == ["Nível do platô", "Gabarito da Baia 01"]
            b64_antes = [f.imagem_otimizada_base64 for f in _fotos(oid, aid)]

            # 2) usuário apaga os arquivos da raiz p/ aliviar espaço; reimporta
            for n in (1, 2):
                os.remove(dia_dir / f'{n}.png')
            importar_fisico_financeiro(payload, aid)
            fotos = _fotos(oid, aid)
            assert [f.legenda for f in fotos] == ["Nível do platô", "Gabarito da Baia 01"]
            assert [f.imagem_otimizada_base64 for f in fotos] == b64_antes  # mesmo conteúdo

            # 3) coloca um arquivo novo na pasta -> a pasta volta a mandar (substitui)
            Image.new('RGB', (8, 8), (200, 10, 10)).save(dia_dir / '1.png')
            payload['rdos'][0]['fotos'] = ["Só a nova"]
            importar_fisico_financeiro(payload, aid)
            fotos = _fotos(oid, aid)
            assert [f.legenda for f in fotos] == ["Só a nova"]
        finally:
            ff.FOTOS_RDO_BASE = old_base


def test_reimport_limpa_custo_obra_referenciando_rdo():
    """Reimport não viola FK quando há custo_obra (ex.: mão de obra) referenciando
    os RDOs antigos; o custo derivado some junto e os RDOs são recriados."""
    import json, os
    from datetime import date
    from services.importacao_fisico_financeiro import importar_fisico_financeiro
    from models import RDO, CustoObra
    caminho = os.path.join(os.path.dirname(__file__), 'fixtures',
                           'cronograma_fisico_financeiro_baias.json')
    payload = json.load(open(caminho, encoding='utf-8'))
    with app.app_context():
        aid = _novo_admin()
        oid = importar_fisico_financeiro(payload, aid)['obra_id']
        rdo = RDO.query.filter_by(obra_id=oid, admin_id=aid).first()
        db.session.add(CustoObra(obra_id=oid, admin_id=aid, rdo_id=rdo.id,
                                 tipo='mao_obra', descricao='RDO mão de obra',
                                 valor=180.0, data=date(2026, 6, 22)))
        db.session.commit()
        assert CustoObra.query.filter_by(obra_id=oid, rdo_id=rdo.id).count() == 1
        # reimporta — não deve levantar IntegrityError de FK
        oid2 = importar_fisico_financeiro(payload, aid)['obra_id']
        assert oid2 == oid
        assert RDO.query.filter_by(obra_id=oid, admin_id=aid).count() == 26
        assert CustoObra.query.filter_by(obra_id=oid, tipo='mao_obra').count() == 0


def test_import_sem_rdos_lanca_pct_fisico_sem_mao_de_obra():
    """Arquivo SEM seção `rdos` (físico vem do `pct_fisico` do cronograma) gera o
    progresso da obra direto do cronograma — sem adicionar pessoas. Reproduz o
    Baia_fisico_financeiro_IMPORTAR.json (real). Ver 2026-06-30-pct-fisico-no-import-baia."""
    import json, os
    from datetime import date
    from services.importacao_fisico_financeiro import importar_fisico_financeiro
    from models import RDO, RDOMaoObra
    from utils.cronograma_engine import calcular_progresso_geral_obra_v2
    payload = _carregar_json()
    # Simula o arquivo real: sem `rdos`, físico só no `pct_fisico` das folhas.
    payload.pop('rdos', None)
    folhas = [t for t in payload['cronograma_tarefas'] if not t.get('resumo')]
    folhas[0]['pct_fisico'] = 100.0
    folhas[1]['pct_fisico'] = 50.0
    com_fisico = sum(1 for t in folhas if float(t.get('pct_fisico') or 0) > 0)
    with app.app_context():
        aid = _novo_admin()
        oid = importar_fisico_financeiro(payload, aid)['obra_id']
        rdo_ids = [r.id for r in RDO.query.filter_by(obra_id=oid, admin_id=aid).all()]
        # 1 RDO sintético de físico, SEM mão de obra
        assert len(rdo_ids) == 1
        assert RDOMaoObra.query.filter(RDOMaoObra.rdo_id.in_(rdo_ids)).count() == 0
        # progresso da obra > 0 (lançado a partir do pct_fisico)
        prog = calcular_progresso_geral_obra_v2(oid, date.today(), aid)
        assert prog['progresso_geral_pct'] > 0
        assert prog['n_tarefas_apontadas'] == com_fisico


@pytest.mark.integration
def test_apontamentos_do_mesmo_nome_em_galpoes_distintos_sao_distinguiveis():
    """Duas tarefas com o MESMO nome em galpões diferentes precisam aparecer
    distinguíveis no RDO — senão a tela mostra dois cards idênticos e o
    usuário lê como lançamento em duplicidade (relato de 28/07/2026 no RDO de
    22/07 da Baia).

    O caso real: "AJR - Maquinário: …" (Galpão B, 60→80%) e
    "Ajr - Maquinário: …" (Galpão A, 0→60%) no mesmo dia. Só se distinguiam
    por um acaso de grafia herdado do .mpp — a atividade seguinte que
    repetisse a grafia ficaria indistinguível.
    """
    from services.importacao_fisico_financeiro import importar_fisico_financeiro
    from models import TarefaCronograma
    from utils.cronograma_engine import caminho_ancestrais_tarefa
    with app.app_context():
        aid = _novo_admin()
        oid = importar_fisico_financeiro(_carregar_json(), aid)['obra_id']

        alvo = 'nivelamento das calçadas'
        tarefas = [t for t in TarefaCronograma.query.filter_by(
            obra_id=oid, admin_id=aid).all()
            if alvo in (t.nome_tarefa or '').lower()]
        assert len(tarefas) == 2, (
            f'esperava a atividade nos dois galpões, achei {len(tarefas)}')

        caminhos = {caminho_ancestrais_tarefa(t) for t in tarefas}
        assert len(caminhos) == 2, (
            f'os dois cards teriam o mesmo rótulo: {caminhos}')
        assert any('Galpão A' in c for c in caminhos), caminhos
        assert any('Galpão B' in c for c in caminhos), caminhos
        # a raiz (nome da obra) não entra no rótulo — ocuparia espaço à toa
        assert not any('Fazenda Santa Mônica' in c for c in caminhos), caminhos


@pytest.mark.integration
def test_caminho_ancestrais_nao_gira_em_ciclo_de_pai():
    """`tarefa_pai_id` é auto-referente e nada no banco impede um ciclo. Sem a
    guarda de visitados, a tela do RDO travaria o worker em laço infinito."""
    from services.importacao_fisico_financeiro import importar_fisico_financeiro
    from models import TarefaCronograma
    from utils.cronograma_engine import caminho_ancestrais_tarefa
    with app.app_context():
        aid = _novo_admin()
        oid = importar_fisico_financeiro(_carregar_json(), aid)['obra_id']
        a, b = TarefaCronograma.query.filter_by(
            obra_id=oid, admin_id=aid).limit(2).all()
        a.tarefa_pai_id, b.tarefa_pai_id = b.id, a.id
        db.session.commit()
        assert isinstance(caminho_ancestrais_tarefa(a), str)  # termina


@pytest.mark.integration
def test_portal_rdo_mostra_galpao_de_cada_atividade():
    """No PORTAL (a tela que o cliente abre), duas atividades de mesmo nome em
    galpões diferentes precisam sair identificadas — senão viram duas linhas
    idênticas e leem-se como lançamento em duplicidade.

    Reproduz o RDO real de 22/07/2026 da Baia: "AJR - Maquinário: …" no
    Galpão B (60→80%) e "Ajr - Maquinário: …" no Galpão A (0→60%), no mesmo
    dia. Só se distinguiam por um acaso de grafia herdado do .mpp.
    """
    from services.importacao_fisico_financeiro import importar_fisico_financeiro
    from models import Obra, RDO
    from datetime import date
    with app.app_context():
        aid = _novo_admin()
        oid = importar_fisico_financeiro(_carregar_json(), aid)['obra_id']
        token = f'tok-galpao-{aid}'
        obra = Obra.query.get(oid)
        obra.token_cliente = token
        obra.portal_ativo = True
        db.session.commit()
        rdo_id = RDO.query.filter_by(
            obra_id=oid, admin_id=aid,
            data_relatorio=date(2026, 7, 22)).first().id

    with app.test_client() as c:
        r = c.get(f'/portal/obra/{token}/rdo/{rdo_id}')
        assert r.status_code == 200
        html = r.get_data(as_text=True)
        # Procura o RÓTULO inteiro, não a palavra solta: o comentário deste RDO
        # cita "Galpão A"/"Galpão B" em texto livre, e um `'Galpão A' in html`
        # passa mesmo sem o fix (verificado).
        assert 'Baias › Galpão B › Fundação' in html, 'linha do Galpão B sem rótulo'
        assert 'Baias › Galpão A › Fundação' in html, 'linha do Galpão A sem rótulo'


@pytest.mark.integration
def test_pdf_do_rdo_gera_com_caminho_de_ancestrais():
    """O nome da tarefa e o rótulo de ancestrais vão para um `Paragraph` do
    ReportLab, que faz parse de mini-XML. Um `&` no nome de uma tarefa-pai
    derruba a geração do PDF inteiro se o texto não for escapado."""
    from services import importacao_fisico_financeiro as ff
    from services.rdo_pdf_service import gerar_pdf_rdo
    from models import RDO
    os.makedirs('/tmp/vazio_pdf', exist_ok=True)
    ff.FOTOS_RDO_BASE = '/tmp/vazio_pdf'
    caminho = os.path.join(os.path.dirname(__file__), 'fixtures',
                           'cronograma_fisico_financeiro_baias.json')
    payload = json.load(open(caminho, encoding='utf-8'))
    with app.app_context():
        aid = _novo_admin()
        oid = ff.importar_fisico_financeiro(payload, aid)['obra_id']
        # Nome hostil ao parser XML num ANCESTRAL (vai para o rótulo).
        from models import TarefaCronograma, RDOApontamentoCronograma
        rdo = RDO.query.filter_by(obra_id=oid, admin_id=aid,
                                  data_relatorio=date(2026, 7, 22)).first()
        ap = RDOApontamentoCronograma.query.filter_by(rdo_id=rdo.id).first()
        folha = TarefaCronograma.query.get(ap.tarefa_cronograma_id)
        pai = TarefaCronograma.query.get(folha.tarefa_pai_id)
        pai.nome_tarefa = 'Fundação & Estrutura <B>'
        db.session.commit()
        pdf = gerar_pdf_rdo(rdo)
    assert pdf and pdf[:4] == b'%PDF', 'PDF não foi gerado'
    assert len(pdf) > 1000


@pytest.mark.integration
def test_agrupamento_por_caminho_preserva_ordem_e_nao_inventa_grupo():
    """O agrupamento não pode reordenar as atividades (a sequência é do
    cronograma) nem criar cabeçalho onde não há o que separar."""
    from types import SimpleNamespace as NS
    from utils.cronograma_engine import agrupar_atividades_por_caminho

    a = NS(nome='a', caminho_tarefa='Baias › Galpão B › Fundação')
    b = NS(nome='b', caminho_tarefa='Baias › Galpão A › Fundação')
    c = NS(nome='c', caminho_tarefa='Baias › Galpão B › Fundação')

    grupos = agrupar_atividades_por_caminho([a, b, c])
    assert [t for t, _ in grupos] == ['Baias › Galpão B › Fundação',
                                      'Baias › Galpão A › Fundação'], \
        'ordem de primeira aparição dos grupos não preservada'
    assert [i.nome for i in grupos[0][1]] == ['a', 'c']
    assert [i.nome for i in grupos[1][1]] == ['b']

    # Sem hierarquia (ou tudo no mesmo lugar): um grupo, sem título
    iguais = [NS(nome='x', caminho_tarefa='Mesmo'), NS(nome='y', caminho_tarefa='Mesmo')]
    assert agrupar_atividades_por_caminho(iguais) == [(None, iguais)]
    sem = [NS(nome='x', caminho_tarefa=''), NS(nome='y', caminho_tarefa='')]
    assert agrupar_atividades_por_caminho(sem) == [(None, sem)]
    assert agrupar_atividades_por_caminho([]) == [(None, [])]


@pytest.mark.integration
def test_portal_rdo_agrupa_atividades_por_galpao():
    """No portal, o RDO de 22/07 (que tocou os dois galpões) sai com um
    cabeçalho de grupo por galpão, não com linhas alternadas."""
    from services.importacao_fisico_financeiro import importar_fisico_financeiro
    from models import Obra, RDO
    from datetime import date
    with app.app_context():
        aid = _novo_admin()
        oid = importar_fisico_financeiro(_carregar_json(), aid)['obra_id']
        token = f'tok-grupo-{aid}'
        obra = Obra.query.get(oid)
        obra.token_cliente = token
        obra.portal_ativo = True
        db.session.commit()
        rdo_id = RDO.query.filter_by(
            obra_id=oid, admin_id=aid,
            data_relatorio=date(2026, 7, 22)).first().id

    with app.test_client() as c:
        r = c.get(f'/portal/obra/{token}/rdo/{rdo_id}')
        assert r.status_code == 200
        html = r.get_data(as_text=True)
        # cabeçalho de grupo ocupa a linha inteira da tabela
        assert html.count('colspan="5"') >= 2, 'faltou cabeçalho de grupo'
        assert 'Baias › Galpão A › Fundação' in html
        assert 'Baias › Galpão B › Fundação' in html


@pytest.mark.integration
def test_pdf_do_rdo_agrupa_por_galpao():
    """O PDF sai com uma faixa de cabeçalho por lugar do cronograma, como o
    portal e a tela. Lê o TEXTO do PDF — gerar sem levantar não prova que o
    agrupamento chegou na página.

    Pula sem `pypdf` (não é dependência do projeto; use `pip install pypdf`
    para rodar esta verificação localmente).
    """
    pypdf = pytest.importorskip('pypdf')
    from io import BytesIO
    from services.importacao_fisico_financeiro import importar_fisico_financeiro
    from services.rdo_pdf_service import gerar_pdf_rdo
    from models import RDO
    from datetime import date
    with app.app_context():
        aid = _novo_admin()
        oid = importar_fisico_financeiro(_carregar_json(), aid)['obra_id']
        rdo = RDO.query.filter_by(obra_id=oid, admin_id=aid,
                                  data_relatorio=date(2026, 7, 22)).first()
        pdf = gerar_pdf_rdo(rdo)
    texto = '\n'.join(pg.extract_text() or ''
                      for pg in pypdf.PdfReader(BytesIO(pdf)).pages)
    assert 'Baias › Galpão A › Fundação' in texto
    assert 'Baias › Galpão B › Fundação' in texto


@pytest.mark.integration
def test_bloqueia_quantitativo_em_tarefa_ja_apontada_por_percentual():
    """Cadastrar `quantidade_total` numa tarefa já lançada por percentual
    reescreveria o avanço dela: o campo `quantidade_executada_dia` guarda
    PONTOS PERCENTUAIS nesse modo, e passa a ser lido como produção física.

    Medido na Baia: a tarefa "AJR - Maquinário…" está em 80% (60 pp + 20 pp);
    cadastrar 200 un a jogaria para 40%, e 48 un para 100%.
    """
    from services.importacao_fisico_financeiro import importar_fisico_financeiro
    from models import TarefaCronograma
    from utils.cronograma_engine import (
        impedimento_para_cadastrar_quantitativo, calcular_progresso_rdo)
    from datetime import date
    with app.app_context():
        aid = _novo_admin()
        oid = importar_fisico_financeiro(_carregar_json(), aid)['obra_id']
        apontada = TarefaCronograma.query.filter(
            TarefaCronograma.obra_id == oid, TarefaCronograma.admin_id == aid,
            TarefaCronograma.nome_tarefa.ilike('AJR%')).first()

        # o estrago que a regra evita, medido
        assert calcular_progresso_rdo(
            apontada.id, date(2026, 8, 1), aid)['percentual_realizado'] == 80.0

        msg = impedimento_para_cadastrar_quantitativo(apontada, 200, aid)
        assert msg and 'apontamento' in msg, msg

        # limpar o campo continua livre
        assert impedimento_para_cadastrar_quantitativo(apontada, 0, aid) is None
        assert impedimento_para_cadastrar_quantitativo(apontada, None, aid) is None

        # tarefa SEM apontamento: cadastro livre
        virgem = TarefaCronograma.query.filter(
            TarefaCronograma.obra_id == oid, TarefaCronograma.admin_id == aid,
            TarefaCronograma.nome_tarefa.ilike('%Pedra Moledo%')).first()
        assert not virgem.apontamentos
        assert impedimento_para_cadastrar_quantitativo(virgem, 48, aid) is None

        # tarefa que JÁ é quantitativa: ajustar o total é legítimo
        # (lá o acumulado é físico e recalcular é o comportamento correto)
        apontada.quantidade_total = 50.0
        db.session.commit()
        assert impedimento_para_cadastrar_quantitativo(apontada, 80, aid) is None


@pytest.mark.integration
def test_rota_de_editar_tarefa_recusa_quantitativo_em_tarefa_percentual():
    """O bloqueio vale pela ROTA que a tela usa, não só na função: 400 com a
    explicação, e o campo NÃO é gravado."""
    import main  # noqa: F401 — registra os blueprints
    from services.importacao_fisico_financeiro import importar_fisico_financeiro
    from models import TarefaCronograma, Usuario
    app.config['TESTING'] = True
    app.config['WTF_CSRF_ENABLED'] = False
    if not app.secret_key:
        app.secret_key = 'test-bloqueio-quantitativo'
    with app.app_context():
        aid = _novo_admin()
        u = Usuario.query.get(aid)
        u.versao_sistema = 'v2'
        db.session.commit()
        oid = importar_fisico_financeiro(_carregar_json(), aid)['obra_id']
        tid = TarefaCronograma.query.filter(
            TarefaCronograma.obra_id == oid, TarefaCronograma.admin_id == aid,
            TarefaCronograma.nome_tarefa.ilike('AJR%')).first().id

    c = app.test_client()
    with c.session_transaction() as sess:
        sess['_user_id'] = str(aid)
        sess['_fresh'] = True
    r = c.put(f'/cronograma/obra/{oid}/tarefa/{tid}',
              json={'quantidade_total': 200})
    assert r.status_code == 400, r.get_data(as_text=True)[:400]
    assert 'percentual' in r.get_json()['msg'].lower()

    with app.app_context():
        assert TarefaCronograma.query.get(tid).quantidade_total in (None, 0)
