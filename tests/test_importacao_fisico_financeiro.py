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
        assert obra.data_previsao_fim == date(2026, 9, 11)


@pytest.mark.integration
def test_importa_cria_etapas_tarefas_e_custos():
    from services.importacao_fisico_financeiro import importar_fisico_financeiro
    from models import (TarefaCronograma, ItemMedicaoComercial,
                        ItemMedicaoCronogramaTarefa, ObraServicoCusto)
    with app.app_context():
        admin_id = _novo_admin()
        res = importar_fisico_financeiro(_carregar_json(), admin_id)
        oid = res['obra_id']
        raizes = TarefaCronograma.query.filter_by(obra_id=oid, admin_id=admin_id,
                                                  tarefa_pai_id=None).count()
        assert raizes == 12
        folhas = TarefaCronograma.query.filter(
            TarefaCronograma.obra_id == oid,
            TarefaCronograma.admin_id == admin_id,
            TarefaCronograma.tarefa_pai_id.isnot(None)).count()
        assert folhas >= 12
        assert ItemMedicaoComercial.query.filter_by(obra_id=oid).count() == 12
        assert ItemMedicaoCronogramaTarefa.query.filter_by(admin_id=admin_id).count() == folhas
        oscs = ObraServicoCusto.query.filter_by(obra_id=oid, admin_id=admin_id).all()
        soma_veks = sum(float(o.mao_obra_a_realizar or 0) for o in oscs)
        soma_fat = sum(float(o.material_a_realizar or 0) for o in oscs)
        assert abs(soma_veks - 734460) < 50
        assert abs(soma_fat - 423700) < 50


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
        assert snap and snap['lucro_caixa_final'] == 152047


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
        assert TarefaCronograma.query.filter_by(obra_id=oid1, tarefa_pai_id=None).count() == 12
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
        assert abs(float(div['resumo']['delta_veks']) - 90000) < 2000

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
def test_importa_gera_aviso_para_etapa_sem_tarefas():
    # Quando uma etapa não tem tarefas_mpp, o importador cria uma folha de
    # fallback e registra um aviso 'sem tarefas'.
    from services.importacao_fisico_financeiro import importar_fisico_financeiro
    with app.app_context():
        admin_id = _novo_admin()
        payload = _carregar_json()
        payload['eap'] = [dict(e) for e in payload['eap']]
        alvo = payload['eap'][-1]
        alvo['cronograma'] = dict(alvo.get('cronograma', {}))
        alvo['cronograma']['tarefas_mpp'] = []
        res = importar_fisico_financeiro(payload, admin_id)
        assert any('sem tarefas' in a.lower() for a in res['avisos'])


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
