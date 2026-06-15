"""Testes do read-model services/resultado_atividade_service.py (Fatia 1)."""
import os
import sys
from datetime import date, datetime
from decimal import Decimal

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app import app, db
import main  # noqa: F401 — registra os blueprints (rota /obras/<id>/resultado)
from models import (
    Usuario, TipoUsuario, Funcionario, Obra, Cliente,
    RDO, RDOMaoObra, RDOCustoDiario, TarefaCronograma,
    ItemMedicaoComercial, ItemMedicaoCronogramaTarefa, PropostaItem, Proposta,
)
from werkzeug.security import generate_password_hash


def _sfx():
    return datetime.utcnow().strftime('%H%M%S%f')


class FX:
    admin = None
    obra = None
    s = ''


_fx = FX()


@pytest.fixture(scope='module', autouse=True)
def ambiente():
    app.config['TESTING'] = True
    app.config['WTF_CSRF_ENABLED'] = False
    with app.app_context():
        s = _sfx()
        admin = Usuario(
            username=f'res_ativ_{s}', email=f'res_ativ_{s}@sige.test',
            nome='Res Ativ', tipo_usuario=TipoUsuario.ADMIN,
            password_hash=generate_password_hash('Test@1234'),
            versao_sistema='v2', ativo=True,
        )
        db.session.add(admin); db.session.flush()
        cli = Cliente(nome=f'CLI-RA-{s}', admin_id=admin.id)
        db.session.add(cli); db.session.flush()
        obra = Obra(
            nome=f'Obra RA {s}', codigo=f'ORA{s[:6]}',
            data_inicio=date(2026, 1, 1), admin_id=admin.id,
            cliente_id=cli.id, valor_contrato=100000,
        )
        db.session.add(obra); db.session.commit()
        _fx.admin = admin; _fx.obra = obra; _fx.s = s
        yield


# ── builders ────────────────────────────────────────────────────────────────

def _tarefa(nome, quantidade_total=100.0, percentual=0.0, servico_id=None, pai=None):
    t = TarefaCronograma(
        obra_id=_fx.obra.id, nome_tarefa=nome, ordem=1, duracao_dias=5,
        quantidade_total=quantidade_total, percentual_concluido=percentual,
        servico_id=servico_id, admin_id=_fx.admin.id,
        tarefa_pai_id=(pai.id if pai else None),
    )
    db.session.add(t); db.session.flush()
    return t


def _proposta_item(composicao_snapshot, quantidade):
    prop = Proposta(
        admin_id=_fx.admin.id, numero=f'PROP-{_sfx()}',
        cliente_nome='Cliente RA', data_proposta=date(2026, 1, 1),
    )
    db.session.add(prop); db.session.flush()
    pi = PropostaItem(
        admin_id=_fx.admin.id, proposta_id=prop.id, item_numero=1,
        descricao='Serviço', quantidade=Decimal(str(quantidade)), unidade='m2',
        preco_unitario=Decimal('1'), ordem=1,
        composicao_snapshot=composicao_snapshot,
    )
    db.session.add(pi); db.session.flush()
    return pi


def _item_medicao(valor_comercial, tarefa, peso, quantidade=None, proposta_item=None):
    imc = ItemMedicaoComercial(
        admin_id=_fx.admin.id, obra_id=_fx.obra.id, nome='IMC',
        valor_comercial=Decimal(str(valor_comercial)),
        quantidade=(Decimal(str(quantidade)) if quantidade is not None else None),
        proposta_item_id=(proposta_item.id if proposta_item else None),
        status='PENDENTE',
    )
    db.session.add(imc); db.session.flush()
    link = ItemMedicaoCronogramaTarefa(
        item_medicao_id=imc.id, cronograma_tarefa_id=tarefa.id,
        peso=Decimal(str(peso)), admin_id=_fx.admin.id,
    )
    db.session.add(link); db.session.flush()
    return imc


def _func(tipo='salario', salario=0.0, valor_diaria=0.0):
    f = Funcionario(
        nome=f'F {_sfx()}', cpf=f'9{_sfx()}'.ljust(14, '0')[:14],
        codigo=f'F{_sfx()[:8]}', data_admissao=date(2025, 1, 1),
        admin_id=_fx.admin.id, tipo_remuneracao=tipo, salario=salario,
        valor_diaria=valor_diaria, valor_va=0.0, valor_vt=0.0, ativo=True,
    )
    db.session.add(f); db.session.flush()
    return f


def _rdo(data):
    r = RDO(
        numero_rdo=f'RDO-RA-{_sfx()}', obra_id=_fx.obra.id, data_relatorio=data,
        admin_id=_fx.admin.id, status='Finalizado', criado_por_id=_fx.admin.id,
    )
    db.session.add(r); db.session.flush()
    return r


def _mo(rdo, func, tarefa, horas):
    mo = RDOMaoObra(
        rdo_id=rdo.id, funcionario_id=func.id, funcao_exercida='Op',
        horas_trabalhadas=horas, admin_id=_fx.admin.id,
        subatividade_id=None, tarefa_cronograma_id=tarefa.id,
    )
    db.session.add(mo); db.session.flush()
    return mo


def _custo_diario(rdo, func, custo_total):
    """Grava direto o RDOCustoDiario (o read-model só LÊ este valor)."""
    c = RDOCustoDiario(
        rdo_id=rdo.id, funcionario_id=func.id, admin_id=_fx.admin.id,
        data=rdo.data_relatorio, tipo_remuneracao_snapshot='salario',
        custo_total_dia=Decimal(str(custo_total)), tipo_lancamento='rdo',
    )
    db.session.add(c); db.session.flush()
    return c


# ── B2: valor agregado ────────────────────────────────────────────────────────

def test_valor_agregado_atividade():
    from services.resultado_atividade_service import valor_agregado_atividade
    with app.app_context():
        t = _tarefa('Alvenaria', percentual=50.0)
        _item_medicao(valor_comercial=1000, tarefa=t, peso=100)
        db.session.commit()
        assert valor_agregado_atividade(t) == Decimal('500.00')


def test_valor_agregado_com_peso_parcial():
    from services.resultado_atividade_service import valor_agregado_atividade
    with app.app_context():
        t1 = _tarefa('Parte A', percentual=100.0)
        t2 = _tarefa('Parte B', percentual=0.0)
        imc = _item_medicao(valor_comercial=1000, tarefa=t1, peso=40)
        link2 = ItemMedicaoCronogramaTarefa(
            item_medicao_id=imc.id, cronograma_tarefa_id=t2.id,
            peso=Decimal('60'), admin_id=_fx.admin.id,
        )
        db.session.add(link2); db.session.commit()
        assert valor_agregado_atividade(t1) == Decimal('400.00')
        assert valor_agregado_atividade(t2) == Decimal('0.00')


# ── B3: custo MO (rateio onerado, D1) ─────────────────────────────────────────

def test_custo_mo_atividade_rateio_por_horas():
    from services.resultado_atividade_service import custo_mo_atividade
    with app.app_context():
        t_a = _tarefa('Atividade A')
        t_b = _tarefa('Atividade B')
        f = _func()
        r = _rdo(date(2026, 2, 10))
        _mo(r, f, t_a, horas=6.0)
        _mo(r, f, t_b, horas=2.0)
        _custo_diario(r, f, custo_total=200)
        db.session.commit()
        assert custo_mo_atividade(t_a) == Decimal('150.00')
        assert custo_mo_atividade(t_b) == Decimal('50.00')


def test_custo_mo_atividade_soma_multiplos_dias():
    from services.resultado_atividade_service import custo_mo_atividade
    with app.app_context():
        t = _tarefa('Atividade C')
        f = _func()
        r1 = _rdo(date(2026, 2, 11)); _mo(r1, f, t, 8.0); _custo_diario(r1, f, 100)
        r2 = _rdo(date(2026, 2, 12)); _mo(r2, f, t, 8.0); _custo_diario(r2, f, 120)
        db.session.commit()
        assert custo_mo_atividade(t) == Decimal('220.00')


# ── B4: resultado ─────────────────────────────────────────────────────────────

def test_resultado_realizado_atividade():
    from services.resultado_atividade_service import resultado_realizado_atividade
    with app.app_context():
        t = _tarefa('Resultado', percentual=100.0)
        _item_medicao(valor_comercial=1000, tarefa=t, peso=100)
        f = _func()
        r = _rdo(date(2026, 2, 13)); _mo(r, f, t, 8.0); _custo_diario(r, f, 300)
        db.session.commit()
        assert resultado_realizado_atividade(t) == Decimal('700.00')


# ── B5: custo orçado ──────────────────────────────────────────────────────────

def test_custo_mo_orcado_unitario_filtra_mao_obra():
    from services.resultado_atividade_service import custo_mo_orcado_unitario
    snap = [
        {'tipo': 'MATERIAL', 'unidade': 'kg', 'coeficiente': 5.0, 'subtotal_unitario': 7.5},
        {'tipo': 'MAO_OBRA', 'unidade': 'h', 'coeficiente': 0.5, 'subtotal_unitario': 15.0},
        {'tipo': 'MAO_OBRA', 'unidade': 'h', 'coeficiente': 0.2, 'subtotal_unitario': 5.0},
    ]
    assert custo_mo_orcado_unitario(snap) == Decimal('20.0')


def test_custo_mo_orcado_atividade():
    from services.resultado_atividade_service import custo_mo_orcado_atividade
    with app.app_context():
        snap = [
            {'tipo': 'MAO_OBRA', 'unidade': 'm2', 'coeficiente': 1.0, 'subtotal_unitario': 10.0},
            {'tipo': 'MATERIAL', 'unidade': 'm2', 'coeficiente': 1.0, 'subtotal_unitario': 40.0},
        ]
        pi = _proposta_item(composicao_snapshot=snap, quantidade=100)
        t = _tarefa('Orcado')
        _item_medicao(valor_comercial=5000, tarefa=t, peso=100,
                      quantidade=100, proposta_item=pi)
        db.session.commit()
        assert custo_mo_orcado_atividade(t) == Decimal('1000.00')


# ── B6: alarme em R$ (D5) ─────────────────────────────────────────────────────

def test_alarme_mo_no_vermelho():
    from services.resultado_atividade_service import alarme_mo
    with app.app_context():
        snap = [{'tipo': 'MAO_OBRA', 'unidade': 'm2', 'coeficiente': 1.0, 'subtotal_unitario': 10.0}]
        pi = _proposta_item(composicao_snapshot=snap, quantidade=100)
        t = _tarefa('Alarme', percentual=50.0)
        _item_medicao(valor_comercial=5000, tarefa=t, peso=100,
                      quantidade=100, proposta_item=pi)
        f = _func()
        r = _rdo(date(2026, 2, 14)); _mo(r, f, t, 8.0); _custo_diario(r, f, 700)
        db.session.commit()
        a = alarme_mo(t)
        assert a['orcado_para_avanco'] == Decimal('500.00')
        assert a['real'] == Decimal('700.00')
        assert a['estouro'] is True
        assert a['indice_rs'] == Decimal('0.714')


def test_alarme_mo_no_verde():
    from services.resultado_atividade_service import alarme_mo
    with app.app_context():
        snap = [{'tipo': 'MAO_OBRA', 'unidade': 'm2', 'coeficiente': 1.0, 'subtotal_unitario': 10.0}]
        pi = _proposta_item(composicao_snapshot=snap, quantidade=100)
        t = _tarefa('AlarmeOk', percentual=50.0)
        _item_medicao(valor_comercial=5000, tarefa=t, peso=100, quantidade=100, proposta_item=pi)
        f = _func()
        r = _rdo(date(2026, 2, 15)); _mo(r, f, t, 8.0); _custo_diario(r, f, 400)
        db.session.commit()
        a = alarme_mo(t)
        assert a['estouro'] is False


# ── B7: índice em horas ───────────────────────────────────────────────────────

def test_indice_horas_quando_mo_em_hora():
    from services.resultado_atividade_service import indice_horas
    with app.app_context():
        snap = [{'tipo': 'MAO_OBRA', 'unidade': 'h', 'coeficiente': 0.1, 'subtotal_unitario': 3.0}]
        pi = _proposta_item(composicao_snapshot=snap, quantidade=100)
        t = _tarefa('HoraItem', percentual=50.0)
        _item_medicao(valor_comercial=5000, tarefa=t, peso=100, quantidade=100, proposta_item=pi)
        f = _func()
        r = _rdo(date(2026, 2, 16)); _mo(r, f, t, 8.0); db.session.commit()
        res = indice_horas(t)
        assert res['horas_orcadas'] == Decimal('10.00')
        assert res['horas_ganhas'] == Decimal('5.00')
        assert res['horas_reais'] == Decimal('8.00')
        assert res['indice'] == Decimal('0.625')


def test_indice_horas_none_quando_mo_em_m2():
    from services.resultado_atividade_service import indice_horas
    with app.app_context():
        snap = [{'tipo': 'MAO_OBRA', 'unidade': 'm2', 'coeficiente': 1.0, 'subtotal_unitario': 10.0}]
        pi = _proposta_item(composicao_snapshot=snap, quantidade=100)
        t = _tarefa('M2Item', percentual=50.0)
        _item_medicao(valor_comercial=5000, tarefa=t, peso=100, quantidade=100, proposta_item=pi)
        db.session.commit()
        assert indice_horas(t) is None


# ── B8: rollup ────────────────────────────────────────────────────────────────

def test_resultado_obra_rollup():
    from services.resultado_atividade_service import resultado_obra
    with app.app_context():
        # obra isolada para este teste (rollup varre todas as folhas da obra)
        s = _sfx()
        cli = Cliente(nome=f'CLI-RB-{s}', admin_id=_fx.admin.id); db.session.add(cli); db.session.flush()
        obra2 = Obra(nome=f'Obra RB {s}', codigo=f'ORB{s[:6]}', data_inicio=date(2026, 1, 1),
                     admin_id=_fx.admin.id, cliente_id=cli.id, valor_contrato=1)
        db.session.add(obra2); db.session.flush()
        _orig = _fx.obra
        _fx.obra = obra2
        try:
            t1 = _tarefa('Folha 1', percentual=100.0)
            _item_medicao(valor_comercial=1000, tarefa=t1, peso=100)
            f1 = _func(); r1 = _rdo(date(2026, 2, 17)); _mo(r1, f1, t1, 8.0); _custo_diario(r1, f1, 300)
            t2 = _tarefa('Folha 2', percentual=100.0)
            _item_medicao(valor_comercial=500, tarefa=t2, peso=100)
            f2 = _func(); r2 = _rdo(date(2026, 2, 18)); _mo(r2, f2, t2, 8.0); _custo_diario(r2, f2, 100)
            db.session.commit()
            res = resultado_obra(obra2.id)
            assert res['valor_agregado'] == Decimal('1500.00')
            assert res['custo_mo'] == Decimal('400.00')
            assert res['resultado'] == Decimal('1100.00')
            nomes = {a['nome'] for a in res['atividades']}
            assert {'Folha 1', 'Folha 2'} <= nomes
        finally:
            _fx.obra = _orig


# ── C1: smoke da rota ─────────────────────────────────────────────────────────

def test_rota_resultado_responde():
    with app.app_context():
        t = _tarefa('Atividade Smoke', percentual=10.0)
        _item_medicao(valor_comercial=1000, tarefa=t, peso=100)
        db.session.commit()
        with app.test_client() as c:
            with c.session_transaction() as sess:
                sess['_user_id'] = str(_fx.admin.id)
                sess['_fresh'] = True
            resp = c.get(f'/obras/{_fx.obra.id}/resultado')
        assert resp.status_code == 200, resp.status_code
        assert b'Resultado por Atividade' in resp.data
