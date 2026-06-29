# tests/test_painel_financeiro.py
import os
import sys
sys.path.insert(0, os.path.abspath(os.path.dirname(__file__) + '/..'))

from datetime import date, datetime
from decimal import Decimal
import pytest
from werkzeug.security import generate_password_hash
from app import app, db

D = Decimal


def _novo_admin():
    from models import Usuario, TipoUsuario
    tag = datetime.utcnow().strftime('%H%M%S%f')
    u = Usuario(username=f'pf_{tag}', email=f'pf_{tag}@t.local', nome='PF',
                password_hash=generate_password_hash('x'), tipo_usuario=TipoUsuario.ADMIN)
    db.session.add(u); db.session.commit()
    return u.id


def _novo_cliente(admin_id):
    from models import Cliente
    c = Cliente(nome='Cliente PF', admin_id=admin_id)
    db.session.add(c); db.session.flush()
    return c.id


def _obra_com_realizado(admin_id):
    from models import Obra, GestaoCustoPai, GestaoCustoFilho
    obra = Obra(nome='Obra PF', codigo=f'PF{admin_id}', admin_id=admin_id,
                cliente_id=_novo_cliente(admin_id),
                data_inicio=date(2026, 6, 1), valor_contrato=1000000.0)
    db.session.add(obra); db.session.flush()
    pai = GestaoCustoPai(tipo_categoria='MAO_OBRA', admin_id=admin_id,
                         entidade_nome='Equipe', valor_total=0)
    db.session.add(pai); db.session.flush()
    pai_fat = GestaoCustoPai(tipo_categoria='FATURAMENTO_DIRETO', admin_id=admin_id,
                             entidade_nome='Cliente', valor_total=0)
    db.session.add(pai_fat); db.session.flush()
    db.session.add_all([
        GestaoCustoFilho(pai_id=pai.id, data_referencia=date(2026, 6, 10),
                         descricao='Diária', valor=D('10000'), obra_id=obra.id, admin_id=admin_id),
        GestaoCustoFilho(pai_id=pai.id, data_referencia=date(2026, 7, 5),
                         descricao='Empreitada', valor=D('25000'), obra_id=obra.id, admin_id=admin_id),
        GestaoCustoFilho(pai_id=pai_fat.id, data_referencia=date(2026, 6, 20),
                         descricao='Material cliente', valor=D('99999'), obra_id=obra.id, admin_id=admin_id),
    ])
    db.session.commit()
    return obra


@pytest.mark.integration
def test_curva_realizado_por_mes_exclui_fat_direto():
    from services.cronograma_fisico_financeiro import curva_realizado
    with app.app_context():
        aid = _novo_admin()
        obra = _obra_com_realizado(aid)
        out = curva_realizado(obra)
        assert out == {'2026-06': D('10000'), '2026-07': D('25000')}


@pytest.mark.integration
def test_realizado_por_etapa_agrupa_por_osc():
    from services.cronograma_fisico_financeiro import realizado_por_etapa
    from models import Obra, GestaoCustoPai, GestaoCustoFilho, ObraServicoCusto, ItemMedicaoComercial
    with app.app_context():
        aid = _novo_admin()
        obra = Obra(nome='O2', codigo=f'O2{aid}', admin_id=aid, cliente_id=_novo_cliente(aid),
                    data_inicio=date(2026,6,1), valor_contrato=0)
        db.session.add(obra); db.session.flush()
        imc = ItemMedicaoComercial(obra_id=obra.id, admin_id=aid, nome='E1', valor_comercial=D('0'))
        db.session.add(imc); db.session.flush()
        osc = ObraServicoCusto.query.filter_by(item_medicao_comercial_id=imc.id).first()
        if osc is None:
            osc = ObraServicoCusto(obra_id=obra.id, admin_id=aid, nome='E1', valor_orcado=D('0'))
            db.session.add(osc); db.session.flush()
        pai = GestaoCustoPai(tipo_categoria='MAO_OBRA', admin_id=aid, entidade_nome='x', valor_total=0)
        db.session.add(pai); db.session.flush()
        db.session.add(GestaoCustoFilho(pai_id=pai.id, data_referencia=date(2026,6,1),
                       descricao='d', valor=D('500'), obra_id=obra.id, admin_id=aid,
                       obra_servico_custo_id=osc.id))
        db.session.commit()
        out = realizado_por_etapa(obra)
        assert out.get(osc.id) == D('500')


@pytest.mark.integration
def test_verba_disponivel_eh_caixa():
    from services.resumo_custos_obra import calcular_resumo_obra
    from models import Obra, GestaoCustoPai, GestaoCustoFilho
    with app.app_context():
        aid = _novo_admin()
        obra = Obra(nome='OV', codigo=f'OV{aid}', admin_id=aid, cliente_id=_novo_cliente(aid),
                    data_inicio=date(2026,6,1), valor_contrato=100000.0)
        db.session.add(obra); db.session.flush()
        pai = GestaoCustoPai(tipo_categoria='MAO_OBRA', admin_id=aid, entidade_nome='x', valor_total=0)
        db.session.add(pai); db.session.flush()
        db.session.add(GestaoCustoFilho(pai_id=pai.id, data_referencia=date(2026,6,5),
                       descricao='real', valor=D('30000'), obra_id=obra.id, admin_id=aid))
        db.session.commit()
        r = calcular_resumo_obra(obra.id, aid)
        i = r['indicadores']
        assert i['verba_disponivel'] == round(i['valor_recebido'] - i['total_realizado'], 2)
        assert 'saldo_orcamentario' in i
        assert i['saldo_orcamentario'] == round(i['total_proposta_orcada'] - i['custo_real_da_obra'], 2)


@pytest.mark.integration
def test_painel_financeiro_estrutura():
    from services.importacao_fisico_financeiro import importar_fisico_financeiro
    from services.cronograma_fisico_financeiro import painel_financeiro
    from models import Obra
    import json
    with app.app_context():
        aid = _novo_admin()
        caminho = os.path.join(os.path.dirname(__file__), 'fixtures',
                               'cronograma_fisico_financeiro_baias.json')
        payload = json.load(open(caminho, encoding='utf-8'))
        oid = importar_fisico_financeiro(payload, aid)['obra_id']
        obra = Obra.query.get(oid)
        p = painel_financeiro(obra)
        for k in ('kpis', 'etapas', 'curva_s', 'caixa', 'medicoes', 'doughnut', 'divergencia'):
            assert k in p, k
        cs = p['curva_s']
        assert set(['meses', 'recebido_liquido', 'gasto_veks', 'lucro', 'realizado']) <= set(cs)
        n = len(cs['meses'])
        assert all(len(cs[s]) == n for s in ('recebido_liquido', 'gasto_veks', 'lucro', 'realizado'))
        assert p['etapas'] and all('realizado' in e and 'previsto' in e for e in p['etapas'])
        assert set(['veks', 'fat']) <= set(p['doughnut'])
        assert 'verba_disponivel' in p['kpis']


@pytest.mark.integration
def test_painel_verba_disponivel_eh_recebido_menos_realizado():
    # No painel, Verba disponível (caixa) = recebido até hoje − custo realizado,
    # usando os próprios KPIs do painel (consistente, não a fonte do resumo).
    from services.importacao_fisico_financeiro import importar_fisico_financeiro
    from services.cronograma_fisico_financeiro import painel_financeiro
    from models import Obra
    from decimal import Decimal
    import json
    with app.app_context():
        aid = _novo_admin()
        caminho = os.path.join(os.path.dirname(__file__), 'fixtures',
                               'cronograma_fisico_financeiro_baias.json')
        oid = importar_fisico_financeiro(json.load(open(caminho, encoding='utf-8')), aid)['obra_id']
        k = painel_financeiro(Obra.query.get(oid))['kpis']
        esperado = Decimal(str(k['recebido_ate_hoje'])) - Decimal(str(k['custo_realizado']))
        assert Decimal(str(k['verba_disponivel'])) == esperado
        # sem custo realizado lançado, a verba é exatamente o recebido até hoje
        assert Decimal(str(k['verba_disponivel'])) == Decimal(str(k['recebido_ate_hoje']))


@pytest.mark.integration
def test_painel_etapas_osc_id_e_none_ou_osc_real():
    from services.importacao_fisico_financeiro import importar_fisico_financeiro
    from services.cronograma_fisico_financeiro import painel_financeiro
    from models import Obra, ObraServicoCusto
    import json
    with app.app_context():
        aid = _novo_admin()
        caminho = os.path.join(os.path.dirname(__file__), 'fixtures',
                               'cronograma_fisico_financeiro_baias.json')
        oid = importar_fisico_financeiro(json.load(open(caminho, encoding='utf-8')), aid)['obra_id']
        obra = Obra.query.get(oid)
        osc_ids = {o.id for o in ObraServicoCusto.query.filter_by(obra_id=oid, admin_id=aid).all()}
        p = painel_financeiro(obra)
        for e in p['etapas']:
            assert e['osc_id'] is None or e['osc_id'] in osc_ids


@pytest.mark.integration
def test_endpoint_financeiro_dados():
    from services.importacao_fisico_financeiro import importar_fisico_financeiro
    import json
    with app.app_context():
        aid = _novo_admin()
        caminho = os.path.join(os.path.dirname(__file__), 'fixtures',
                               'cronograma_fisico_financeiro_baias.json')
        oid = importar_fisico_financeiro(json.load(open(caminho, encoding='utf-8')), aid)['obra_id']
    app.config['WTF_CSRF_ENABLED'] = False
    with app.test_client() as c:
        with c.session_transaction() as s:
            s['_user_id'] = str(aid); s['_fresh'] = True
        r = c.get(f'/obras/{oid}/financeiro/dados')
        assert r.status_code == 200
        data = r.get_json()
        for k in ('kpis', 'etapas', 'curva_s', 'caixa', 'medicoes', 'doughnut'):
            assert k in data
        assert len(data['curva_s']['meses']) == len(data['curva_s']['realizado'])


@pytest.mark.integration
def test_endpoint_financeiro_dados_multitenant():
    from services.importacao_fisico_financeiro import importar_fisico_financeiro
    import json
    with app.app_context():
        a1 = _novo_admin(); a2 = _novo_admin()
        caminho = os.path.join(os.path.dirname(__file__), 'fixtures',
                               'cronograma_fisico_financeiro_baias.json')
        oid = importar_fisico_financeiro(json.load(open(caminho, encoding='utf-8')), a1)['obra_id']
    app.config['WTF_CSRF_ENABLED'] = False
    with app.test_client() as c:
        with c.session_transaction() as s:
            s['_user_id'] = str(a2); s['_fresh'] = True
        r = c.get(f'/obras/{oid}/financeiro/dados')
        assert r.status_code == 404


@pytest.mark.integration
def test_rota_ff_antiga_redireciona():
    from services.importacao_fisico_financeiro import importar_fisico_financeiro
    from models import Usuario
    import json
    with app.app_context():
        aid = _novo_admin()
        u = Usuario.query.get(aid); u.versao_sistema = 'v2'; db.session.commit()
        caminho = os.path.join(os.path.dirname(__file__), 'fixtures',
                               'cronograma_fisico_financeiro_baias.json')
        oid = importar_fisico_financeiro(json.load(open(caminho, encoding='utf-8')), aid)['obra_id']
    app.config['WTF_CSRF_ENABLED'] = False
    with app.test_client() as c:
        with c.session_transaction() as s:
            s['_user_id'] = str(aid); s['_fresh'] = True
        # Rota real é /cronograma/obra/<id>/fisico-financeiro (singular "obra").
        r = c.get(f'/cronograma/obra/{oid}/fisico-financeiro')
        assert r.status_code in (301, 302)
        loc = r.headers.get('Location', '')
        # main.detalhes_obra → /obras/detalhes/<id>#financeiro (data-hash da aba)
        assert f'/obras/detalhes/{oid}' in loc and loc.endswith('#financeiro')


@pytest.mark.integration
def test_obras_id_serve_pagina_nao_json():
    from services.importacao_fisico_financeiro import importar_fisico_financeiro
    from models import Usuario
    import json
    with app.app_context():
        aid = _novo_admin()
        u = Usuario.query.get(aid); u.versao_sistema = 'v2'; db.session.commit()
        caminho = os.path.join(os.path.dirname(__file__), 'fixtures',
                               'cronograma_fisico_financeiro_baias.json')
        oid = importar_fisico_financeiro(json.load(open(caminho, encoding='utf-8')), aid)['obra_id']
    app.config['WTF_CSRF_ENABLED'] = False
    with app.test_client() as c:
        with c.session_transaction() as s:
            s['_user_id'] = str(aid); s['_fresh'] = True
        r = c.get(f'/obras/{oid}')
        # deve servir HTML (página), não o JSON do financeiro
        assert r.status_code == 200
        ct = r.headers.get('Content-Type', '')
        assert 'text/html' in ct
        assert 'tab-financeiro' in r.get_data(as_text=True)


@pytest.mark.integration
def test_pagina_obra_tem_aba_financeiro_e_endpoint():
    from services.importacao_fisico_financeiro import importar_fisico_financeiro
    from models import Usuario
    import json
    with app.app_context():
        aid = _novo_admin()
        u = Usuario.query.get(aid); u.versao_sistema = 'v2'; db.session.commit()
        caminho = os.path.join(os.path.dirname(__file__), 'fixtures',
                               'cronograma_fisico_financeiro_baias.json')
        oid = importar_fisico_financeiro(json.load(open(caminho, encoding='utf-8')), aid)['obra_id']
    app.config['WTF_CSRF_ENABLED'] = False
    with app.test_client() as c:
        with c.session_transaction() as s:
            s['_user_id'] = str(aid); s['_fresh'] = True
        page = c.get(f'/obras/{oid}', follow_redirects=True)
        assert page.status_code == 200
        html = page.get_data(as_text=True)
        assert 'tab-financeiro' in html
        assert 'financeiro_obra.js' in html
        data = c.get(f'/obras/{oid}/financeiro/dados').get_json()
        assert len(data['curva_s']['meses']) == len(data['curva_s']['realizado'])
        assert len(data['etapas']) == 12
        # INDIRETOS aparece junto das etapas, marcado como custo de período.
        periodo = [e for e in data['etapas'] if e.get('tipo') == 'periodo']
        assert len(periodo) == 1
        assert 'INDIRET' in (periodo[0]['nome'] or '').upper()
        assert all(e.get('tipo') in ('entregavel', 'periodo') for e in data['etapas'])


@pytest.mark.integration
def test_painel_tem_grupos_kpi_e_wrappers_chart():
    # Redesign: 3 grupos de KPI (Resultado/Caixa/Custo) com corpo preenchido por
    # JS (ids fin-kpi-*) + cada canvas dentro de um wrapper .fin-chart de altura fixa.
    from services.importacao_fisico_financeiro import importar_fisico_financeiro
    from models import Usuario
    import json
    with app.app_context():
        aid = _novo_admin()
        u = Usuario.query.get(aid); u.versao_sistema = 'v2'; db.session.commit()
        caminho = os.path.join(os.path.dirname(__file__), 'fixtures',
                               'cronograma_fisico_financeiro_baias.json')
        oid = importar_fisico_financeiro(json.load(open(caminho, encoding='utf-8')), aid)['obra_id']
    app.config['WTF_CSRF_ENABLED'] = False
    with app.test_client() as c:
        with c.session_transaction() as s:
            s['_user_id'] = str(aid); s['_fresh'] = True
        body = c.get(f'/obras/{oid}').get_data(as_text=True)
    for rotulo in ('Resultado', 'Caixa', 'Custo'):
        assert rotulo in body, rotulo
    for gid in ('fin-kpi-resultado', 'fin-kpi-caixa', 'fin-kpi-custo'):
        assert gid in body, gid
    assert body.count('class="fin-chart"') >= 4
    for cid in ('finEtapas', 'finCurva', 'finSplit', 'finCaixa'):
        assert f'<canvas id="{cid}"></canvas>' in body, cid


@pytest.mark.integration
def test_obra_servico_custo_item_schema():
    from models import ObraServicoCustoItem
    cols = {c.name for c in ObraServicoCustoItem.__table__.columns}
    assert {'id', 'obra_servico_custo_id', 'admin_id', 'descricao',
            'valor', 'fonte', 'ordem'} <= cols


@pytest.mark.integration
def test_recalcular_osc_dos_itens():
    from services.cronograma_fisico_financeiro import recalcular_osc_dos_itens
    from models import Obra, ObraServicoCusto, ObraServicoCustoItem
    with app.app_context():
        aid = _novo_admin()
        obra = Obra(nome='OI', codigo=f'OI{aid}', admin_id=aid, cliente_id=_novo_cliente(aid),
                    data_inicio=date(2026, 6, 1), valor_contrato=0)
        db.session.add(obra); db.session.flush()
        osc = ObraServicoCusto(obra_id=obra.id, admin_id=aid, nome='E1', valor_orcado=D('0'))
        db.session.add(osc); db.session.flush()
        db.session.add_all([
            ObraServicoCustoItem(obra_servico_custo_id=osc.id, admin_id=aid,
                                 descricao='a', valor=D('100'), fonte='veks', ordem=0),
            ObraServicoCustoItem(obra_servico_custo_id=osc.id, admin_id=aid,
                                 descricao='b', valor=D('50'), fonte='veks', ordem=1),
            ObraServicoCustoItem(obra_servico_custo_id=osc.id, admin_id=aid,
                                 descricao='c', valor=D('200'), fonte='fat_direto', ordem=2),
        ])
        db.session.flush()
        veks, fat = recalcular_osc_dos_itens(osc)
        assert veks == D('150') and fat == D('200')
        assert D(str(osc.mao_obra_a_realizar)) == D('150')
        assert D(str(osc.material_a_realizar)) == D('200')


@pytest.mark.integration
def test_painel_etapas_incluem_itens():
    from services.importacao_fisico_financeiro import importar_fisico_financeiro
    from services.cronograma_fisico_financeiro import painel_financeiro
    from models import Obra
    import json
    with app.app_context():
        aid = _novo_admin()
        caminho = os.path.join(os.path.dirname(__file__), 'fixtures',
                               'cronograma_fisico_financeiro_baias.json')
        oid = importar_fisico_financeiro(json.load(open(caminho, encoding='utf-8')), aid)['obra_id']
        p = painel_financeiro(Obra.query.get(oid))
        assert all('itens' in e for e in p['etapas'])
        # ao menos uma etapa com itens preenchidos
        assert any(e['itens'] for e in p['etapas'])
        for e in p['etapas']:
            for it in e['itens']:
                assert set(it) >= {'id', 'descricao', 'valor', 'fonte'}


@pytest.mark.integration
def test_endpoint_etapa_itens_substitui_e_recalcula():
    from services.importacao_fisico_financeiro import importar_fisico_financeiro
    from models import Usuario, ObraServicoCusto, ObraServicoCustoItem
    import json
    app.config['WTF_CSRF_ENABLED'] = False
    with app.app_context():
        aid = _novo_admin()
        u = Usuario.query.get(aid); u.versao_sistema = 'v2'; db.session.commit()
        caminho = os.path.join(os.path.dirname(__file__), 'fixtures',
                               'cronograma_fisico_financeiro_baias.json')
        oid = importar_fisico_financeiro(json.load(open(caminho, encoding='utf-8')), aid)['obra_id']
        osc = ObraServicoCusto.query.filter_by(obra_id=oid, admin_id=aid).first()
        osc_id = osc.id
    with app.test_client() as c:
        with c.session_transaction() as s:
            s['_user_id'] = str(aid); s['_fresh'] = True
        # substitui por 2 linhas (1 veks 1000, 1 fat 500)
        r = c.post(f'/obras/{oid}/financeiro/etapa/{osc_id}/itens',
                   json={'itens': [
                       {'descricao': 'X', 'valor': '1000', 'fonte': 'veks'},
                       {'descricao': 'Y', 'valor': '500', 'fonte': 'fat_direto'}],
                       'valor_orcado': '2000'})
        assert r.status_code == 200
        p = r.get_json()
        assert 'kpis' in p and 'etapas' in p
        # payload inválido → 400
        r2 = c.post(f'/obras/{oid}/financeiro/etapa/{osc_id}/itens',
                    json={'itens': [{'descricao': 'Z', 'valor': 'abc', 'fonte': 'veks'}]})
        assert r2.status_code == 400
    with app.app_context():
        linhas = ObraServicoCustoItem.query.filter_by(obra_servico_custo_id=osc_id).all()
        assert len(linhas) == 2
        osc = ObraServicoCusto.query.get(osc_id)
        assert abs(float(osc.mao_obra_a_realizar) - 1000) < 0.01
        assert abs(float(osc.material_a_realizar) - 500) < 0.01


@pytest.mark.integration
def test_endpoint_etapa_itens_multitenant():
    from services.importacao_fisico_financeiro import importar_fisico_financeiro
    from models import Usuario, ObraServicoCusto
    import json
    app.config['WTF_CSRF_ENABLED'] = False
    with app.app_context():
        a1 = _novo_admin(); a2 = _novo_admin()
        u = Usuario.query.get(a2); u.versao_sistema = 'v2'; db.session.commit()
        caminho = os.path.join(os.path.dirname(__file__), 'fixtures',
                               'cronograma_fisico_financeiro_baias.json')
        o1 = importar_fisico_financeiro(json.load(open(caminho, encoding='utf-8')), a1)['obra_id']
        osc1 = ObraServicoCusto.query.filter_by(obra_id=o1, admin_id=a1).first().id
    with app.test_client() as c:
        with c.session_transaction() as s:
            s['_user_id'] = str(a2); s['_fresh'] = True
        r = c.post(f'/obras/{o1}/financeiro/etapa/{osc1}/itens',
                   json={'itens': []})
        assert r.status_code == 404


@pytest.mark.integration
def test_osc_item_tem_datas():
    from models import ObraServicoCustoItem
    cols = {c.name for c in ObraServicoCustoItem.__table__.columns}
    assert {'data_inicio', 'data_fim'} <= cols


@pytest.mark.integration
def test_painel_itens_incluem_datas():
    from services.importacao_fisico_financeiro import importar_fisico_financeiro
    from services.cronograma_fisico_financeiro import painel_financeiro
    from models import Obra
    import json
    with app.app_context():
        aid = _novo_admin()
        caminho = os.path.join(os.path.dirname(__file__), 'fixtures',
                               'cronograma_fisico_financeiro_baias.json')
        oid = importar_fisico_financeiro(json.load(open(caminho, encoding='utf-8')), aid)['obra_id']
        p = painel_financeiro(Obra.query.get(oid))
        # toda linha expõe as chaves de data
        for e in p['etapas']:
            for it in e['itens']:
                assert 'data_inicio' in it and 'data_fim' in it
        # ao menos uma linha veio com datas preenchidas da etapa (cronograma)
        assert any(it['data_inicio'] for e in p['etapas'] for it in e['itens'])


@pytest.mark.integration
def test_endpoint_etapa_itens_persiste_datas():
    from services.importacao_fisico_financeiro import importar_fisico_financeiro
    from models import Usuario, ObraServicoCusto, ObraServicoCustoItem
    import json
    app.config['WTF_CSRF_ENABLED'] = False
    with app.app_context():
        aid = _novo_admin()
        u = Usuario.query.get(aid); u.versao_sistema = 'v2'; db.session.commit()
        caminho = os.path.join(os.path.dirname(__file__), 'fixtures',
                               'cronograma_fisico_financeiro_baias.json')
        oid = importar_fisico_financeiro(json.load(open(caminho, encoding='utf-8')), aid)['obra_id']
        osc_id = ObraServicoCusto.query.filter_by(obra_id=oid, admin_id=aid).first().id
    with app.test_client() as c:
        with c.session_transaction() as s:
            s['_user_id'] = str(aid); s['_fresh'] = True
        r = c.post(f'/obras/{oid}/financeiro/etapa/{osc_id}/itens',
                   json={'itens': [
                       {'descricao': 'X', 'valor': '1000', 'fonte': 'veks',
                        'data_inicio': '2026-07-01', 'data_fim': '2026-07-31'}]})
        assert r.status_code == 200
        # data inválida → 400
        r2 = c.post(f'/obras/{oid}/financeiro/etapa/{osc_id}/itens',
                    json={'itens': [{'descricao': 'Y', 'valor': '1', 'fonte': 'veks',
                                     'data_inicio': 'xx/yy'}]})
        assert r2.status_code == 400
    with app.app_context():
        from datetime import date
        it = ObraServicoCustoItem.query.filter_by(obra_servico_custo_id=osc_id).one()
        assert it.data_inicio == date(2026, 7, 1)
        assert it.data_fim == date(2026, 7, 31)


@pytest.mark.integration
def test_caixa_faseado_pelas_datas_das_linhas():
    """O desembolso Veks/Fat por mês deve seguir as datas das linhas de custo,
    não o cronograma. Mover uma linha para um mês isolado move o caixa."""
    from services.importacao_fisico_financeiro import importar_fisico_financeiro
    from services.cronograma_fisico_financeiro import fluxo_caixa, recalcular_osc_dos_itens
    from models import Obra, ObraServicoCusto, ObraServicoCustoItem
    from datetime import date
    import json
    with app.app_context():
        aid = _novo_admin()
        caminho = os.path.join(os.path.dirname(__file__), 'fixtures',
                               'cronograma_fisico_financeiro_baias.json')
        obra = Obra.query.get(importar_fisico_financeiro(
            json.load(open(caminho, encoding='utf-8')), aid)['obra_id'])
        # zera as linhas de todas as etapas (agregados → 0) e cria UMA linha veks
        # isolada em 2027-03 na primeira etapa
        oscs = ObraServicoCusto.query.filter_by(obra_id=obra.id, admin_id=aid).all()
        osc_ids = [o.id for o in oscs]
        ObraServicoCustoItem.query.filter(
            ObraServicoCustoItem.obra_servico_custo_id.in_(osc_ids)).delete(synchronize_session=False)
        db.session.add(ObraServicoCustoItem(
            obra_servico_custo_id=oscs[0].id, admin_id=aid, descricao='Solo',
            valor=D('30000'), fonte='veks', ordem=0,
            data_inicio=date(2027, 3, 2), data_fim=date(2027, 3, 31)))
        db.session.flush()
        for o in oscs:  # agregados derivam das linhas (todos zeram, exceto oscs[0])
            recalcular_osc_dos_itens(o)
        db.session.flush()
        caixa = fluxo_caixa(obra)
        por_mes = {l['mes']: l for l in caixa['linhas']}
        assert '2027-03' in por_mes
        # todo o gasto_veks cai em 2027-03 (a única linha dada)
        total_veks = sum(float(l['gasto_veks']) for l in caixa['linhas'])
        assert abs(total_veks - 30000) < 1
        assert abs(float(por_mes['2027-03']['gasto_veks']) - 30000) < 1


@pytest.mark.integration
def test_caixa_fallback_complementar_linha_sem_data():
    """Fallback complementar: linha COM datas é faseada por elas; linha SEM datas
    cai no faseamento por cronograma — nada se perde."""
    from services.importacao_fisico_financeiro import importar_fisico_financeiro
    from services.cronograma_fisico_financeiro import fluxo_caixa, recalcular_osc_dos_itens
    from models import Obra, ObraServicoCusto, ObraServicoCustoItem
    from datetime import date
    import json
    with app.app_context():
        aid = _novo_admin()
        caminho = os.path.join(os.path.dirname(__file__), 'fixtures',
                               'cronograma_fisico_financeiro_baias.json')
        obra = Obra.query.get(importar_fisico_financeiro(
            json.load(open(caminho, encoding='utf-8')), aid)['obra_id'])
        oscs = ObraServicoCusto.query.filter_by(obra_id=obra.id, admin_id=aid).all()
        baseline = fluxo_caixa(obra)
        total_base = sum(float(l['gasto_veks']) for l in baseline['linhas'])
        veks0_orig = float(oscs[0].mao_obra_a_realizar or 0)
        # substitui as linhas da etapa 0 por: uma DATADA (2027-03) + uma SEM data
        ObraServicoCustoItem.query.filter_by(
            obra_servico_custo_id=oscs[0].id).delete(synchronize_session=False)
        db.session.add_all([
            ObraServicoCustoItem(obra_servico_custo_id=oscs[0].id, admin_id=aid,
                                 descricao='Datada', valor=D('10000'), fonte='veks', ordem=0,
                                 data_inicio=date(2027, 3, 2), data_fim=date(2027, 3, 31)),
            ObraServicoCustoItem(obra_servico_custo_id=oscs[0].id, admin_id=aid,
                                 descricao='SemData', valor=D('7000'), fonte='veks', ordem=1),
        ])
        db.session.flush()
        recalcular_osc_dos_itens(oscs[0])  # agregado etapa0 = 17000
        db.session.flush()
        caixa = fluxo_caixa(obra)
        por_mes = {l['mes']: l for l in caixa['linhas']}
        # a linha datada cai exatamente em 2027-03 (e SÓ ela: 10000, não 17000)
        assert abs(float(por_mes['2027-03']['gasto_veks']) - 10000) < 1
        # nada se perde: total = baseline - etapa0 original + 17000 (10k datada + 7k cronograma)
        total = sum(float(l['gasto_veks']) for l in caixa['linhas'])
        assert abs(total - (total_base - veks0_orig + 17000)) < 2


@pytest.mark.integration
def test_osc_item_tem_valor_realizado():
    from models import ObraServicoCustoItem
    cols = {c.name for c in ObraServicoCustoItem.__table__.columns}
    assert 'valor_realizado' in cols


@pytest.mark.integration
def test_osc_item_valor_realizado_default_zero():
    from models import ObraServicoCusto, ObraServicoCustoItem, Obra, Usuario
    from decimal import Decimal
    with app.app_context():
        aid = _novo_admin()
        obra = Obra(nome='T-vr', admin_id=aid, data_inicio=date(2026, 6, 1),
                    cliente_id=_novo_cliente(aid))
        db.session.add(obra); db.session.flush()
        osc = ObraServicoCusto(obra_id=obra.id, admin_id=aid, nome='E1')
        db.session.add(osc); db.session.flush()
        it = ObraServicoCustoItem(
            obra_servico_custo_id=osc.id, admin_id=aid,
            descricao='Escritório', valor=Decimal('100'), fonte='veks', ordem=0)
        db.session.add(it); db.session.commit()
        assert Decimal(str(it.valor_realizado or 0)) == Decimal('0')
