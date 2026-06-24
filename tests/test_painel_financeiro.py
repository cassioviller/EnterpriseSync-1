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
