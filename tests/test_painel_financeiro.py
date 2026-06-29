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
def test_osc_item_sem_valor_realizado():
    from models import ObraServicoCustoItem
    cols = {c.name for c in ObraServicoCustoItem.__table__.columns}
    assert 'valor_realizado' not in cols


@pytest.mark.integration
def test_painel_itens_tem_campos_para_agrupar():
    """Cada item do painel expõe (descricao, fonte, valor) — base do
    agrupamento (descricao, fonte) feito na UI. Itens de período repetem descricao+fonte."""
    from services.importacao_fisico_financeiro import importar_fisico_financeiro
    from services.cronograma_fisico_financeiro import painel_financeiro
    from models import Obra
    from collections import Counter
    import json, os
    with app.app_context():
        aid = _novo_admin()
        caminho = os.path.join(os.path.dirname(__file__), 'fixtures',
                               'cronograma_fisico_financeiro_baias.json')
        oid = importar_fisico_financeiro(json.load(open(caminho, encoding='utf-8')), aid)['obra_id']
        p = painel_financeiro(Obra.query.get(oid))
        for e in p['etapas']:
            for it in e['itens']:
                assert {'descricao', 'fonte', 'valor'} <= set(it.keys())
        # ao menos uma etapa de período tem grupo com >1 item (mesma descricao+fonte)
        algum_grupo_multi = False
        for e in p['etapas']:
            chaves = Counter((it['descricao'], it['fonte']) for it in e['itens'])
            if any(c > 1 for c in chaves.values()):
                algum_grupo_multi = True
        assert algum_grupo_multi


@pytest.mark.integration
def test_lancamentos_da_etapa_lista_gestao_custo_filho():
    from services.importacao_fisico_financeiro import importar_fisico_financeiro
    from services.cronograma_fisico_financeiro import lancamentos_da_etapa
    from models import Obra, ObraServicoCusto, GestaoCustoPai, GestaoCustoFilho
    from decimal import Decimal
    from datetime import date
    import json, os
    with app.app_context():
        aid = _novo_admin()
        caminho = os.path.join(os.path.dirname(__file__), 'fixtures',
                               'cronograma_fisico_financeiro_baias.json')
        oid = importar_fisico_financeiro(json.load(open(caminho, encoding='utf-8')), aid)['obra_id']
        obra = Obra.query.get(oid)
        osc = ObraServicoCusto.query.filter_by(obra_id=oid, admin_id=aid).first()
        pai = GestaoCustoPai(admin_id=aid, tipo_categoria='OUTROS',
                             entidade_nome='Fornecedor X', valor_total=Decimal('300'),
                             status='PENDENTE')
        db.session.add(pai); db.session.flush()
        db.session.add(GestaoCustoFilho(
            pai_id=pai.id, admin_id=aid, obra_id=oid, obra_servico_custo_id=osc.id,
            data_referencia=date(2026, 6, 10), descricao='Aluguel sala',
            valor=Decimal('300'), origem_tabela='lancamento_periodo_manual'))
        db.session.commit()
        out = lancamentos_da_etapa(obra, osc.id)
        assert len(out) == 1
        l = out[0]
        assert l['descricao'] == 'Aluguel sala'
        assert Decimal(str(l['valor'])) == Decimal('300')
        assert l['data'] == date(2026, 6, 10)
        assert l['editavel'] is True
        assert l['origem'] == 'lancamento_periodo_manual'


@pytest.mark.integration
def test_get_lancamentos_endpoint():
    from services.importacao_fisico_financeiro import importar_fisico_financeiro
    from models import Usuario, ObraServicoCusto, GestaoCustoPai, GestaoCustoFilho
    from decimal import Decimal
    from datetime import date
    import json, os
    app.config['WTF_CSRF_ENABLED'] = False
    with app.app_context():
        aid = _novo_admin()
        u = Usuario.query.get(aid); u.versao_sistema = 'v2'; db.session.commit()
        caminho = os.path.join(os.path.dirname(__file__), 'fixtures',
                               'cronograma_fisico_financeiro_baias.json')
        oid = importar_fisico_financeiro(json.load(open(caminho, encoding='utf-8')), aid)['obra_id']
        osc = ObraServicoCusto.query.filter_by(obra_id=oid, admin_id=aid).first()
        pai = GestaoCustoPai(admin_id=aid, tipo_categoria='OUTROS', entidade_nome='F',
                             valor_total=Decimal('150'), status='PENDENTE')
        db.session.add(pai); db.session.flush()
        db.session.add(GestaoCustoFilho(
            pai_id=pai.id, admin_id=aid, obra_id=oid, obra_servico_custo_id=osc.id,
            data_referencia=date(2026, 7, 5), descricao='Conta luz', valor=Decimal('150'),
            origem_tabela='lancamento_periodo_manual'))
        db.session.commit()
        osc_id = osc.id
    with app.test_client() as c:
        with c.session_transaction() as s:
            s['_user_id'] = str(aid); s['_fresh'] = True
        r = c.get(f'/obras/{oid}/financeiro/etapa/{osc_id}/lancamentos')
        assert r.status_code == 200
        body = r.get_json()
        assert len(body['lancamentos']) == 1
        assert body['lancamentos'][0]['descricao'] == 'Conta luz'


@pytest.mark.integration
def test_post_lancamento_manual_cria_conta_pagar():
    from services.importacao_fisico_financeiro import importar_fisico_financeiro
    from models import Usuario, ObraServicoCusto, GestaoCustoFilho
    from decimal import Decimal
    import json, os
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
        r = c.post(f'/obras/{oid}/financeiro/etapa/{osc_id}/lancamentos',
                   json={'data': '2026-06-10', 'descricao': 'Aluguel sala', 'valor': '900'})
        assert r.status_code == 200
        body = r.get_json()
        assert 'painel' in body and body.get('lancamento_id')
        # valor negativo → 400
        r2 = c.post(f'/obras/{oid}/financeiro/etapa/{osc_id}/lancamentos',
                    json={'data': '2026-06-10', 'descricao': 'x', 'valor': '-5'})
        assert r2.status_code == 400
    with app.app_context():
        f = GestaoCustoFilho.query.filter_by(
            obra_id=oid, obra_servico_custo_id=osc_id,
            origem_tabela='lancamento_periodo_manual').one()
        assert Decimal(str(f.valor)) == Decimal('900')
        assert f.descricao == 'Aluguel sala'


@pytest.mark.integration
def test_patch_e_delete_lancamento_manual():
    from services.importacao_fisico_financeiro import importar_fisico_financeiro
    from models import Usuario, ObraServicoCusto, GestaoCustoFilho, GestaoCustoPai
    from decimal import Decimal
    import json, os
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
        r = c.post(f'/obras/{oid}/financeiro/etapa/{osc_id}/lancamentos',
                   json={'data': '2026-06-10', 'descricao': 'X', 'valor': '900'})
        fid = r.get_json()['lancamento_id']
        # editar valor
        rp = c.patch(f'/obras/{oid}/financeiro/etapa/{osc_id}/lancamentos/{fid}',
                     json={'valor': '1200', 'descricao': 'Y'})
        assert rp.status_code == 200
        # excluir
        rd = c.delete(f'/obras/{oid}/financeiro/etapa/{osc_id}/lancamentos/{fid}')
        assert rd.status_code == 200
    with app.app_context():
        assert GestaoCustoFilho.query.get(fid) is None


@pytest.mark.integration
def test_custo_nao_previsto_conta_no_realizado_da_etapa():
    from services.importacao_fisico_financeiro import importar_fisico_financeiro
    from services.cronograma_fisico_financeiro import painel_financeiro
    from models import Usuario, Obra, ObraServicoCusto
    from decimal import Decimal
    import json, os
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
        c.post(f'/obras/{oid}/financeiro/etapa/{osc_id}/lancamentos',
               json={'data': '2026-06-10', 'descricao': 'Multa imprevista', 'valor': '1000'})
    with app.app_context():
        p = painel_financeiro(Obra.query.get(oid))
        et = next(e for e in p['etapas'] if e['osc_id'] == osc_id)
        assert float(et['realizado']) >= 1000 - 1   # conta mesmo sem previsão correspondente


@pytest.mark.integration
def test_gestao_custo_pai_tem_categoria_fluxo_caixa():
    from models import GestaoCustoPai
    cols = {c.name for c in GestaoCustoPai.__table__.columns}
    assert 'categoria_fluxo_caixa_id' in cols


@pytest.mark.integration
def test_registrar_custo_separa_pai_por_categoria_fc():
    from utils.financeiro_integration import registrar_custo_automatico
    from models import CategoriaFluxoCaixa, GestaoCustoFilho
    from decimal import Decimal
    from datetime import date
    with app.app_context():
        aid = _novo_admin()
        CategoriaFluxoCaixa.seed_defaults(aid)
        db.session.commit()
        mat = CategoriaFluxoCaixa.query.filter_by(
            admin_id=aid, nome='Materiais de Obra', tipo='SAIDA').first()
        mo = CategoriaFluxoCaixa.query.filter_by(
            admin_id=aid, nome='Mão de Obra Direta', tipo='SAIDA').first()
        f1 = registrar_custo_automatico(
            admin_id=aid, tipo_categoria='OUTROS', entidade_nome='Lançamento manual',
            entidade_id=None, data=date(2026, 6, 10), descricao='Cimento',
            valor=Decimal('100'), obra_id=None,
            origem_tabela='lancamento_periodo_manual', origem_id=None,
            categoria_fluxo_caixa_id=mat.id, force_v2=True)
        f2 = registrar_custo_automatico(
            admin_id=aid, tipo_categoria='OUTROS', entidade_nome='Lançamento manual',
            entidade_id=None, data=date(2026, 6, 11), descricao='Diária',
            valor=Decimal('200'), obra_id=None,
            origem_tabela='lancamento_periodo_manual', origem_id=None,
            categoria_fluxo_caixa_id=mo.id, force_v2=True)
        db.session.commit()
        assert f1 is not None and f2 is not None
        # categorias diferentes → pais diferentes
        assert f1.pai_id != f2.pai_id
        assert f1.pai.categoria_fluxo_caixa_id == mat.id
        assert f2.pai.categoria_fluxo_caixa_id == mo.id


@pytest.mark.integration
def test_categorias_fluxo_caixa_saida_agrupa():
    from services.cronograma_fisico_financeiro import categorias_fluxo_caixa_saida
    from models import CategoriaFluxoCaixa
    with app.app_context():
        aid = _novo_admin()
        CategoriaFluxoCaixa.seed_defaults(aid)
        db.session.commit()
        grupos = categorias_fluxo_caixa_saida(aid)
        # estrutura agrupada
        assert all(set(g.keys()) == {'grupo', 'opcoes'} for g in grupos)
        nomes = {o['nome'] for g in grupos for o in g['opcoes']}
        assert 'Materiais de Obra' in nomes
        # só SAÍDA — nenhuma categoria de ENTRADA aparece
        assert 'Receita de Obras' not in nomes


@pytest.mark.integration
def test_resolver_categoria_fluxo_caixa_fallback():
    from services.cronograma_fisico_financeiro import resolver_categoria_fluxo_caixa
    from models import CategoriaFluxoCaixa
    with app.app_context():
        aid = _novo_admin()
        CategoriaFluxoCaixa.seed_defaults(aid)
        db.session.commit()
        outras = CategoriaFluxoCaixa.query.filter_by(
            admin_id=aid, nome='Outras Saídas', tipo='SAIDA').first()
        receita = CategoriaFluxoCaixa.query.filter_by(
            admin_id=aid, tipo='ENTRADA').first()
        mat = CategoriaFluxoCaixa.query.filter_by(
            admin_id=aid, nome='Materiais de Obra', tipo='SAIDA').first()
        # válida → ela mesma
        assert resolver_categoria_fluxo_caixa(aid, mat.id) == mat.id
        # None → Outras Saídas
        assert resolver_categoria_fluxo_caixa(aid, None) == outras.id
        # ENTRADA (não SAÍDA) → fallback Outras Saídas
        assert resolver_categoria_fluxo_caixa(aid, receita.id) == outras.id


@pytest.mark.integration
def test_lancamentos_da_etapa_expoe_categoria():
    from services.importacao_fisico_financeiro import importar_fisico_financeiro
    from services.cronograma_fisico_financeiro import lancamentos_da_etapa
    from utils.financeiro_integration import registrar_custo_automatico
    from models import Obra, ObraServicoCusto, CategoriaFluxoCaixa
    from decimal import Decimal
    from datetime import date
    import json, os
    with app.app_context():
        aid = _novo_admin()
        CategoriaFluxoCaixa.seed_defaults(aid)
        caminho = os.path.join(os.path.dirname(__file__), 'fixtures',
                               'cronograma_fisico_financeiro_baias.json')
        oid = importar_fisico_financeiro(json.load(open(caminho, encoding='utf-8')), aid)['obra_id']
        obra = Obra.query.get(oid)
        osc = ObraServicoCusto.query.filter_by(obra_id=oid, admin_id=aid).first()
        mat = CategoriaFluxoCaixa.query.filter_by(
            admin_id=aid, nome='Materiais de Obra', tipo='SAIDA').first()
        registrar_custo_automatico(
            admin_id=aid, tipo_categoria='OUTROS', entidade_nome='Lançamento manual',
            entidade_id=None, data=date(2026, 6, 10), descricao='Cimento',
            valor=Decimal('100'), obra_id=oid, obra_servico_custo_id=osc.id,
            origem_tabela='lancamento_periodo_manual', origem_id=None,
            categoria_fluxo_caixa_id=mat.id, force_v2=True)
        db.session.commit()
        out = lancamentos_da_etapa(obra, osc.id)
        assert len(out) == 1
        assert out[0]['categoria_id'] == mat.id
        assert out[0]['categoria_label'] == 'Materiais de Obra'


@pytest.mark.integration
def test_get_lancamentos_inclui_categorias():
    from services.importacao_fisico_financeiro import importar_fisico_financeiro
    from models import Usuario, ObraServicoCusto, CategoriaFluxoCaixa
    import json, os
    app.config['WTF_CSRF_ENABLED'] = False
    with app.app_context():
        aid = _novo_admin()
        u = Usuario.query.get(aid); u.versao_sistema = 'v2'
        CategoriaFluxoCaixa.seed_defaults(aid); db.session.commit()
        caminho = os.path.join(os.path.dirname(__file__), 'fixtures',
                               'cronograma_fisico_financeiro_baias.json')
        oid = importar_fisico_financeiro(json.load(open(caminho, encoding='utf-8')), aid)['obra_id']
        osc_id = ObraServicoCusto.query.filter_by(obra_id=oid, admin_id=aid).first().id
    with app.test_client() as c:
        with c.session_transaction() as s:
            s['_user_id'] = str(aid); s['_fresh'] = True
        r = c.get(f'/obras/{oid}/financeiro/etapa/{osc_id}/lancamentos')
        assert r.status_code == 200
        body = r.get_json()
        assert 'categorias' in body and isinstance(body['categorias'], list)
        nomes = {o['nome'] for g in body['categorias'] for o in g['opcoes']}
        assert 'Materiais de Obra' in nomes


@pytest.mark.integration
def test_post_lancamento_grava_categoria_fc_e_fallback():
    from services.importacao_fisico_financeiro import importar_fisico_financeiro
    from models import Usuario, ObraServicoCusto, GestaoCustoFilho, CategoriaFluxoCaixa
    import json, os
    app.config['WTF_CSRF_ENABLED'] = False
    with app.app_context():
        aid = _novo_admin()
        u = Usuario.query.get(aid); u.versao_sistema = 'v2'
        CategoriaFluxoCaixa.seed_defaults(aid); db.session.commit()
        caminho = os.path.join(os.path.dirname(__file__), 'fixtures',
                               'cronograma_fisico_financeiro_baias.json')
        oid = importar_fisico_financeiro(json.load(open(caminho, encoding='utf-8')), aid)['obra_id']
        osc_id = ObraServicoCusto.query.filter_by(obra_id=oid, admin_id=aid).first().id
        mat_id = CategoriaFluxoCaixa.query.filter_by(
            admin_id=aid, nome='Materiais de Obra', tipo='SAIDA').first().id
        outras_id = CategoriaFluxoCaixa.query.filter_by(
            admin_id=aid, nome='Outras Saídas', tipo='SAIDA').first().id
    with app.test_client() as c:
        with c.session_transaction() as s:
            s['_user_id'] = str(aid); s['_fresh'] = True
        # com categoria válida
        r = c.post(f'/obras/{oid}/financeiro/etapa/{osc_id}/lancamentos',
                   json={'data': '2026-06-10', 'descricao': 'Cimento', 'valor': '900',
                         'categoria_fluxo_caixa_id': mat_id})
        assert r.status_code == 200
        # sem categoria → fallback Outras Saídas
        r2 = c.post(f'/obras/{oid}/financeiro/etapa/{osc_id}/lancamentos',
                    json={'data': '2026-06-11', 'descricao': 'Sem categoria', 'valor': '50'})
        assert r2.status_code == 200
    with app.app_context():
        fmat = GestaoCustoFilho.query.filter_by(
            obra_id=oid, obra_servico_custo_id=osc_id, descricao='Cimento').one()
        ffall = GestaoCustoFilho.query.filter_by(
            obra_id=oid, obra_servico_custo_id=osc_id, descricao='Sem categoria').one()
        assert fmat.pai.categoria_fluxo_caixa_id == mat_id
        assert ffall.pai.categoria_fluxo_caixa_id == outras_id


@pytest.mark.integration
def test_fluxo_caixa_usa_nome_categoria_fc():
    from financeiro_service import FinanceiroService
    from utils.financeiro_integration import registrar_custo_automatico
    from models import CategoriaFluxoCaixa
    from decimal import Decimal
    from datetime import date
    with app.app_context():
        aid = _novo_admin()
        CategoriaFluxoCaixa.seed_defaults(aid)
        db.session.commit()
        mat = CategoriaFluxoCaixa.query.filter_by(
            admin_id=aid, nome='Materiais de Obra', tipo='SAIDA').first()
        registrar_custo_automatico(
            admin_id=aid, tipo_categoria='OUTROS', entidade_nome='Fornecedor X',
            entidade_id=None, data=date(2026, 6, 10), descricao='Cimento',
            valor=Decimal('100'), obra_id=None,
            origem_tabela='lancamento_periodo_manual', origem_id=None,
            categoria_fluxo_caixa_id=mat.id, force_v2=True)
        db.session.commit()
        out = FinanceiroService.calcular_fluxo_caixa(
            aid, date(2026, 1, 1), date(2030, 1, 1))
        saidas = [d for d in out['detalhes'] if d.get('tipo') == 'SAIDA']
        assert any('Materiais de Obra' in (d.get('descricao') or '') for d in saidas)
        assert not any('[OUTROS]' in (d.get('descricao') or '') for d in saidas)


@pytest.mark.integration
def test_lancamento_categoria_ponta_a_ponta():
    from services.importacao_fisico_financeiro import importar_fisico_financeiro
    from services.cronograma_fisico_financeiro import lancamentos_da_etapa, painel_financeiro
    from models import Usuario, Obra, ObraServicoCusto, CategoriaFluxoCaixa
    import json, os
    app.config['WTF_CSRF_ENABLED'] = False
    with app.app_context():
        aid = _novo_admin()
        u = Usuario.query.get(aid); u.versao_sistema = 'v2'
        CategoriaFluxoCaixa.seed_defaults(aid); db.session.commit()
        caminho = os.path.join(os.path.dirname(__file__), 'fixtures',
                               'cronograma_fisico_financeiro_baias.json')
        oid = importar_fisico_financeiro(json.load(open(caminho, encoding='utf-8')), aid)['obra_id']
        osc_id = ObraServicoCusto.query.filter_by(obra_id=oid, admin_id=aid).first().id
        mat_id = CategoriaFluxoCaixa.query.filter_by(
            admin_id=aid, nome='Materiais de Obra', tipo='SAIDA').first().id
    with app.test_client() as c:
        with c.session_transaction() as s:
            s['_user_id'] = str(aid); s['_fresh'] = True
        c.post(f'/obras/{oid}/financeiro/etapa/{osc_id}/lancamentos',
               json={'data': '2026-06-10', 'descricao': 'Cimento', 'valor': '1000',
                     'categoria_fluxo_caixa_id': mat_id})
    with app.app_context():
        obra = Obra.query.get(oid)
        out = lancamentos_da_etapa(obra, osc_id)
        assert any(l['categoria_label'] == 'Materiais de Obra' for l in out)
        # conta no realizado da etapa
        p = painel_financeiro(obra)
        et = next(e for e in p['etapas'] if e['osc_id'] == osc_id)
        assert float(et['realizado']) >= 1000 - 1


@pytest.mark.integration
def test_fluxo_caixa_lancamento_manual_usa_data_digitada():
    """Lançamento manual aparece no fluxo de caixa na data digitada (data_referencia
    do filho), não na data de criação do Pai — o Pai é explodido em linha por filho."""
    from financeiro_service import FinanceiroService
    from utils.financeiro_integration import registrar_custo_automatico
    from models import CategoriaFluxoCaixa
    from decimal import Decimal
    from datetime import date
    with app.app_context():
        aid = _novo_admin()
        CategoriaFluxoCaixa.seed_defaults(aid); db.session.commit()
        mat = CategoriaFluxoCaixa.query.filter_by(
            admin_id=aid, nome='Materiais de Obra', tipo='SAIDA').first()
        # dois lançamentos manuais, mesma categoria → mesmo Pai, datas distintas
        registrar_custo_automatico(
            admin_id=aid, tipo_categoria='OUTROS', entidade_nome='Lançamento manual',
            entidade_id=None, data=date(2026, 6, 20), descricao='Cimento',
            valor=Decimal('4242.42'), obra_id=None,
            origem_tabela='lancamento_periodo_manual', origem_id=None,
            categoria_fluxo_caixa_id=mat.id, force_v2=True)
        registrar_custo_automatico(
            admin_id=aid, tipo_categoria='OUTROS', entidade_nome='Lançamento manual',
            entidade_id=None, data=date(2026, 7, 15), descricao='Areia',
            valor=Decimal('555.00'), obra_id=None,
            origem_tabela='lancamento_periodo_manual', origem_id=None,
            categoria_fluxo_caixa_id=mat.id, force_v2=True)
        db.session.commit()
        out = FinanceiroService.calcular_fluxo_caixa(aid, date(2026, 1, 1), date(2030, 1, 1))
        c1 = [d for d in out['detalhes']
              if d.get('tipo') == 'SAIDA' and abs(float(d.get('valor', 0)) - 4242.42) < 0.01]
        c2 = [d for d in out['detalhes']
              if d.get('tipo') == 'SAIDA' and abs(float(d.get('valor', 0)) - 555.00) < 0.01]
        # cada lançamento vira sua própria linha, na data digitada
        assert len(c1) == 1 and c1[0]['data'] == date(2026, 6, 20)
        assert len(c2) == 1 and c2[0]['data'] == date(2026, 7, 15)


@pytest.mark.integration
def test_pedido_compra_tem_obra_servico_custo_id():
    from models import PedidoCompra
    cols = {c.name for c in PedidoCompra.__table__.columns}
    assert 'obra_servico_custo_id' in cols


@pytest.mark.integration
def test_processar_compra_normal_amarra_etapa():
    from services.importacao_fisico_financeiro import importar_fisico_financeiro
    from services.cronograma_fisico_financeiro import realizado_por_etapa
    from compras_views import processar_compra_normal
    from models import (Obra, ObraServicoCusto, Fornecedor, PedidoCompra,
                        PedidoCompraItem, GestaoCustoFilho)
    from decimal import Decimal
    from datetime import date
    import json, os
    with app.app_context():
        aid = _novo_admin()
        caminho = os.path.join(os.path.dirname(__file__), 'fixtures',
                               'cronograma_fisico_financeiro_baias.json')
        oid = importar_fisico_financeiro(json.load(open(caminho, encoding='utf-8')), aid)['obra_id']
        obra = Obra.query.get(oid)
        osc = ObraServicoCusto.query.filter_by(obra_id=oid, admin_id=aid).first()
        forn = Fornecedor(nome='Forn Teste', cnpj=f'CT{aid:012d}'[:18], admin_id=aid, ativo=True)
        db.session.add(forn); db.session.flush()
        ped = PedidoCompra(
            numero='PC-TST', fornecedor_id=forn.id, data_compra=date(2026, 6, 10),
            obra_id=oid, obra_servico_custo_id=osc.id, condicao_pagamento='parcelado',
            parcelas=2, valor_total=Decimal('1000.00'), tipo_compra='normal',
            processada_apos_aprovacao=False, admin_id=aid)
        db.session.add(ped); db.session.flush()
        item = PedidoCompraItem(
            pedido_id=ped.id, almoxarifado_item_id=None, descricao='Cimento',
            quantidade=Decimal('1'), preco_unitario=Decimal('1000'),
            subtotal=Decimal('1000'), admin_id=aid)
        db.session.add(item); db.session.flush()
        itens = [('Cimento', 1.0, 1000.0, None, 1000.0)]
        processar_compra_normal(ped, itens, aid, aid)
        db.session.commit()
        filhos = GestaoCustoFilho.query.filter_by(
            origem_tabela='pedido_compra', origem_id=ped.id).all()
        assert len(filhos) == 2  # parcelado → 2 parcelas
        assert all(f.obra_servico_custo_id == osc.id for f in filhos)
        # realizado da etapa soma a compra inteira
        assert float(realizado_por_etapa(obra).get(osc.id, 0)) >= 1000 - 1


@pytest.mark.integration
def test_lancamentos_da_etapa_rotula_compra():
    from services.importacao_fisico_financeiro import importar_fisico_financeiro
    from services.cronograma_fisico_financeiro import lancamentos_da_etapa
    from models import Obra, ObraServicoCusto, GestaoCustoPai, GestaoCustoFilho
    from decimal import Decimal
    from datetime import date
    import json, os
    with app.app_context():
        aid = _novo_admin()
        caminho = os.path.join(os.path.dirname(__file__), 'fixtures',
                               'cronograma_fisico_financeiro_baias.json')
        oid = importar_fisico_financeiro(json.load(open(caminho, encoding='utf-8')), aid)['obra_id']
        obra = Obra.query.get(oid)
        osc = ObraServicoCusto.query.filter_by(obra_id=oid, admin_id=aid).first()
        pai = GestaoCustoPai(admin_id=aid, tipo_categoria='MATERIAL',
                             entidade_nome='Fornecedor X', valor_total=Decimal('300'),
                             status='PENDENTE')
        db.session.add(pai); db.session.flush()
        db.session.add(GestaoCustoFilho(
            pai_id=pai.id, admin_id=aid, obra_id=oid, obra_servico_custo_id=osc.id,
            data_referencia=date(2026, 6, 10), descricao='Compra cimento',
            valor=Decimal('300'), origem_tabela='pedido_compra', origem_id=1))
        db.session.commit()
        out = lancamentos_da_etapa(obra, osc.id)
        l = next(x for x in out if x['descricao'] == 'Compra cimento')
        assert l['origem_label'] == 'Compra'
        assert l['editavel'] is False


@pytest.mark.integration
def test_endpoint_etapas_custo():
    from services.importacao_fisico_financeiro import importar_fisico_financeiro
    from models import Usuario, ObraServicoCusto
    import json, os
    app.config['WTF_CSRF_ENABLED'] = False
    with app.app_context():
        aid = _novo_admin()
        u = Usuario.query.get(aid); u.versao_sistema = 'v2'; db.session.commit()
        caminho = os.path.join(os.path.dirname(__file__), 'fixtures',
                               'cronograma_fisico_financeiro_baias.json')
        oid = importar_fisico_financeiro(json.load(open(caminho, encoding='utf-8')), aid)['obra_id']
        n = ObraServicoCusto.query.filter_by(obra_id=oid, admin_id=aid).count()
        outro = _novo_admin()
    with app.test_client() as c:
        with c.session_transaction() as s:
            s['_user_id'] = str(aid); s['_fresh'] = True
        r = c.get(f'/obras/{oid}/etapas-custo')
        assert r.status_code == 200
        body = r.get_json()
        assert len(body['etapas']) == n and n > 0
        assert {'id', 'nome'} <= set(body['etapas'][0].keys())
    # obra de outro admin → 404
    with app.test_client() as c:
        with c.session_transaction() as s:
            s['_user_id'] = str(outro); s['_fresh'] = True
        assert c.get(f'/obras/{oid}/etapas-custo').status_code == 404


@pytest.mark.integration
def test_post_nova_compra_grava_etapa():
    from services.importacao_fisico_financeiro import importar_fisico_financeiro
    from models import Usuario, ObraServicoCusto, Fornecedor, PedidoCompra, GestaoCustoFilho
    import json, os
    app.config['WTF_CSRF_ENABLED'] = False
    with app.app_context():
        aid = _novo_admin()
        u = Usuario.query.get(aid); u.versao_sistema = 'v2'
        caminho = os.path.join(os.path.dirname(__file__), 'fixtures',
                               'cronograma_fisico_financeiro_baias.json')
        oid = importar_fisico_financeiro(json.load(open(caminho, encoding='utf-8')), aid)['obra_id']
        osc_id = ObraServicoCusto.query.filter_by(obra_id=oid, admin_id=aid).first().id
        forn = Fornecedor(nome='Forn POST', cnpj=f'CT{aid:012d}'[:18], admin_id=aid, ativo=True)
        db.session.add(forn); db.session.commit()
        forn_id = forn.id
    with app.test_client() as c:
        with c.session_transaction() as s:
            s['_user_id'] = str(aid); s['_fresh'] = True
        data = {
            'fornecedor_id': str(forn_id), 'data_compra': '2026-06-10',
            'condicao_pagamento': 'a_vista', 'parcelas': '1',
            'obra_id': str(oid), 'obra_servico_custo_id': str(osc_id),
            'tipo_compra': 'normal',
            'item_descricao[]': 'Cimento', 'item_quantidade[]': '1',
            'item_preco[]': '100', 'item_almoxarifado_id[]': '',
        }
        r = c.post('/compras/nova', data=data)
        assert r.status_code in (200, 302)
        # etapa inválida (não pertence à obra) → gravada como None
        data2 = dict(data); data2['obra_servico_custo_id'] = '999999'
        data2['item_descricao[]'] = 'Areia'
        r2 = c.post('/compras/nova', data=data2)
        assert r2.status_code in (200, 302)
    with app.app_context():
        ped = PedidoCompra.query.filter_by(admin_id=aid, numero=None,
                                           obra_id=oid).order_by(PedidoCompra.id).all()
        # primeiro pedido: etapa válida; segundo: None
        p_ok = next(p for p in ped if p.obra_servico_custo_id == osc_id)
        assert p_ok is not None
        f = GestaoCustoFilho.query.filter_by(
            origem_tabela='pedido_compra', origem_id=p_ok.id).first()
        assert f.obra_servico_custo_id == osc_id
        p_invalida = next(p for p in ped if p.id != p_ok.id)
        assert p_invalida.obra_servico_custo_id is None


@pytest.mark.integration
def test_compra_com_etapa_entra_no_painel_realizado():
    from services.importacao_fisico_financeiro import importar_fisico_financeiro
    from services.cronograma_fisico_financeiro import painel_financeiro
    from models import Usuario, Obra, ObraServicoCusto, Fornecedor
    import json, os
    app.config['WTF_CSRF_ENABLED'] = False
    with app.app_context():
        aid = _novo_admin()
        u = Usuario.query.get(aid); u.versao_sistema = 'v2'
        caminho = os.path.join(os.path.dirname(__file__), 'fixtures',
                               'cronograma_fisico_financeiro_baias.json')
        oid = importar_fisico_financeiro(json.load(open(caminho, encoding='utf-8')), aid)['obra_id']
        osc_id = ObraServicoCusto.query.filter_by(obra_id=oid, admin_id=aid).first().id
        forn = Fornecedor(nome='Forn E2E', cnpj=f'CT{aid:012d}'[:18], admin_id=aid, ativo=True)
        db.session.add(forn); db.session.commit()
        forn_id = forn.id
    with app.test_client() as c:
        with c.session_transaction() as s:
            s['_user_id'] = str(aid); s['_fresh'] = True
        c.post('/compras/nova', data={
            'fornecedor_id': str(forn_id), 'data_compra': '2026-06-10',
            'condicao_pagamento': 'a_vista', 'parcelas': '1',
            'obra_id': str(oid), 'obra_servico_custo_id': str(osc_id),
            'tipo_compra': 'normal',
            'item_descricao[]': 'Cimento', 'item_quantidade[]': '1',
            'item_preco[]': '750', 'item_almoxarifado_id[]': '',
        })
    with app.app_context():
        p = painel_financeiro(Obra.query.get(oid))
        et = next(e for e in p['etapas'] if e['osc_id'] == osc_id)
        assert float(et['realizado']) >= 750 - 1


@pytest.mark.integration
def test_alimentacao_transporte_tem_obra_servico_custo_id():
    from models import AlimentacaoLancamento, LancamentoTransporte
    assert 'obra_servico_custo_id' in {c.name for c in AlimentacaoLancamento.__table__.columns}
    assert 'obra_servico_custo_id' in {c.name for c in LancamentoTransporte.__table__.columns}


@pytest.mark.integration
def test_post_transporte_grava_etapa():
    from services.importacao_fisico_financeiro import importar_fisico_financeiro
    from services.cronograma_fisico_financeiro import realizado_por_etapa
    from models import (Usuario, Obra, ObraServicoCusto, GestaoCustoFilho,
                        CategoriaTransporte, CentroCusto)
    import json, os
    app.config['WTF_CSRF_ENABLED'] = False
    with app.app_context():
        aid = _novo_admin()
        u = Usuario.query.get(aid); u.versao_sistema = 'v2'
        caminho = os.path.join(os.path.dirname(__file__), 'fixtures',
                               'cronograma_fisico_financeiro_baias.json')
        oid = importar_fisico_financeiro(json.load(open(caminho, encoding='utf-8')), aid)['obra_id']
        osc_id = ObraServicoCusto.query.filter_by(obra_id=oid, admin_id=aid).first().id
        cat = CategoriaTransporte(nome='VT', admin_id=aid)
        cc = CentroCusto(admin_id=aid, codigo=f'CC{aid}', nome='CC', tipo='obra', obra_id=oid)
        db.session.add_all([cat, cc]); db.session.commit()
        cat_id, cc_id = cat.id, cc.id
    with app.test_client() as c:
        with c.session_transaction() as s:
            s['_user_id'] = str(aid); s['_fresh'] = True
        r = c.post('/transporte/novo', data={
            'categoria_id': str(cat_id), 'centro_custo_id': str(cc_id),
            'data_lancamento': '2026-06-10', 'valor': '300', 'descricao': 'Van obra',
            'obra_id': str(oid), 'obra_servico_custo_id': str(osc_id),
        })
        assert r.status_code in (200, 302)
    with app.app_context():
        f = GestaoCustoFilho.query.filter_by(
            origem_tabela='lancamento_transporte', obra_id=oid).first()
        assert f is not None and f.obra_servico_custo_id == osc_id
        assert float(realizado_por_etapa(Obra.query.get(oid)).get(osc_id, 0)) >= 300 - 1


@pytest.mark.integration
def test_post_alimentacao_grava_etapa():
    from services.importacao_fisico_financeiro import importar_fisico_financeiro
    from services.cronograma_fisico_financeiro import realizado_por_etapa
    from models import Usuario, Obra, ObraServicoCusto, AlimentacaoLancamento, GestaoCustoFilho
    import json, os
    app.config['WTF_CSRF_ENABLED'] = False
    with app.app_context():
        aid = _novo_admin()
        u = Usuario.query.get(aid); u.versao_sistema = 'v2'
        caminho = os.path.join(os.path.dirname(__file__), 'fixtures',
                               'cronograma_fisico_financeiro_baias.json')
        oid = importar_fisico_financeiro(json.load(open(caminho, encoding='utf-8')), aid)['obra_id']
        osc_id = ObraServicoCusto.query.filter_by(obra_id=oid, admin_id=aid).first().id
        db.session.commit()
    with app.test_client() as c:
        with c.session_transaction() as s:
            s['_user_id'] = str(aid); s['_fresh'] = True
        r = c.post('/alimentacao/lancamentos/novo-v2', data={
            'obra_id': str(oid), 'data': '2026-06-10', 'descricao': 'Refeições',
            'obra_servico_custo_id': str(osc_id),
            'itens[0][preco]': '120', 'itens[0][quantidade]': '1',
            'itens[0][nome]': 'Marmita',
        })
        assert r.status_code in (200, 302)
    with app.app_context():
        al = AlimentacaoLancamento.query.filter_by(obra_id=oid).first()
        assert al is not None and al.obra_servico_custo_id == osc_id
        f = GestaoCustoFilho.query.filter_by(origem_tabela='alimentacao_lancamento', obra_id=oid).first()
        assert f is not None and f.obra_servico_custo_id == osc_id
        assert float(realizado_por_etapa(Obra.query.get(oid)).get(osc_id, 0)) >= 120 - 1
