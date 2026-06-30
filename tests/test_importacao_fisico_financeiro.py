import os
import sys
sys.path.insert(0, os.path.abspath(os.path.dirname(__file__) + '/..'))

import pytest
from decimal import Decimal
from app import app, db
from models import MedicaoContrato


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
        assert obra.data_inicio == date(2026, 6, 4)
        assert obra.data_previsao_fim == date(2026, 10, 8)


@pytest.mark.integration
def test_importa_cria_etapas_tarefas_e_custos():
    from services.importacao_fisico_financeiro import importar_fisico_financeiro
    from models import (TarefaCronograma, ItemMedicaoComercial,
                        ItemMedicaoCronogramaTarefa, ObraServicoCusto)
    with app.app_context():
        admin_id = _novo_admin()
        res = importar_fisico_financeiro(_carregar_json(), admin_id)
        oid = res['obra_id']
        # Cronograma físico = espelho fiel das 56 tarefas do .mpp, no outline.
        tarefas = TarefaCronograma.query.filter_by(obra_id=oid, admin_id=admin_id).all()
        assert len(tarefas) == 56
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
        # cronograma não duplica: continua com as 56 tarefas do .mpp, 1 raiz (OBRA)
        assert TarefaCronograma.query.filter_by(obra_id=oid1).count() == 56
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
             "apontamentos": [{"tarefa_mpp": 3, "pct": 100}, {"tarefa_mpp": 4, "pct": 50}]},
            {"data": "2026-06-27", "clima": "Ensolarado", "precipitacao": "Sem chuva",
             "comentario": "Nivelamento galpão B.", "mao_de_obra": 0,
             "apontamentos": [{"tarefa_mpp": 3, "pct": 100}, {"tarefa_mpp": 4, "pct": 65},
                              {"tarefa_mpp": 6, "pct": 20}]},
        ]
        oid = importar_fisico_financeiro(payload, aid)['obra_id']
        assert RDO.query.filter_by(obra_id=oid, admin_id=aid).count() == 2
        por_nome = {t.nome_tarefa: t for t in
                    TarefaCronograma.query.filter_by(obra_id=oid, admin_id=aid).all()}
        assert float(por_nome['ESTUDO DE SOLO SPT'].percentual_concluido) == 100.0
        assert float(por_nome['EXECUÇÃO DE PROJETOS. LSF, TELHADO, PISO, BALDRAME, FUNDAÇÃO PARA PILARES DE MADEIRA'].percentual_concluido) == 65.0
        assert float(por_nome['FAZENDA: NIVELAMENTO DO PLATÔ'].percentual_concluido) == 20.0
        assert float(por_nome['MOBILIZAÇÃO EQUIPE'].percentual_concluido) == 0.0


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
    """A fixture canônica da Baia já contém os 6 RDOs do relatório 22–27/06 e o
    import reproduz o físico: solo 100%, projetos 65%, nivelamento 20%."""
    import json, os
    from services.importacao_fisico_financeiro import importar_fisico_financeiro
    from models import RDO, TarefaCronograma
    with app.app_context():
        aid = _novo_admin()
        caminho = os.path.join(os.path.dirname(__file__), 'fixtures',
                               'cronograma_fisico_financeiro_baias.json')
        payload = json.load(open(caminho, encoding='utf-8'))
        assert len(payload.get('rdos', [])) == 6
        oid = importar_fisico_financeiro(payload, aid)['obra_id']
        assert RDO.query.filter_by(obra_id=oid, admin_id=aid).count() == 6
        por_nome = {t.nome_tarefa: float(t.percentual_concluido or 0) for t in
                    TarefaCronograma.query.filter_by(obra_id=oid, admin_id=aid).all()}
        assert por_nome['ESTUDO DE SOLO SPT'] == 100.0
        assert por_nome['EXECUÇÃO DE PROJETOS. LSF, TELHADO, PISO, BALDRAME, FUNDAÇÃO PARA PILARES DE MADEIRA'] == 65.0
        assert por_nome['FAZENDA: NIVELAMENTO DO PLATÔ'] == 20.0
        assert por_nome['MOBILIZAÇÃO EQUIPE'] == 0.0
        assert por_nome['MARCAÇÃO DE OBRA'] == 0.0


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
                    .filter(TarefaCronograma.nome_tarefa.like('EXECUÇÃO DE PROJETOS%'))
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
        esperado = round(calcular_progresso_geral_obra_v2(oid, date.today(), aid)['progresso_geral_pct'])
        raiz = (TarefaCronograma.query
                .filter_by(obra_id=oid, admin_id=aid, tarefa_pai_id=None).first())
        # o rollup persistido da raiz é diferente da métrica v2 (senão o teste é vácuo)
        assert round(float(raiz.percentual_concluido or 0)) != esperado
    with app.test_client() as c:
        with c.session_transaction() as s:
            s['_user_id'] = str(aid); s['_fresh'] = True
        r = c.get(f'/cronograma/obra/{oid}')
        assert r.status_code == 200
        html = r.get_data(as_text=True)
        # a <tr> da raiz tem data-pai="" e data-perc = métrica v2
        m = re.search(r'data-id="%d"[^>]*data-perc="(\d+)"' % raiz.id, html)
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
