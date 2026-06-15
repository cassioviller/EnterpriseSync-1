"""Fatia 2 — custo não-MO por atividade (direto + rateio) e a regra anti-dupla
contagem de MO (DC3)."""
import os
import sys
from datetime import date, datetime
from decimal import Decimal

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app import app, db
from models import (
    Usuario, TipoUsuario, Funcionario, Obra, Cliente,
    RDO, RDOMaoObra, RDOCustoDiario, TarefaCronograma,
    GestaoCustoPai, GestaoCustoFilho,
    ItemMedicaoComercial, ItemMedicaoCronogramaTarefa, PropostaItem, Proposta,
)
from werkzeug.security import generate_password_hash


def _sfx():
    return datetime.utcnow().strftime('%H%M%S%f')


class FX:
    admin = None
    obra = None


_fx = FX()


@pytest.fixture(scope='module', autouse=True)
def ambiente():
    app.config['TESTING'] = True
    with app.app_context():
        s = _sfx()
        admin = Usuario(
            username=f'f2_{s}', email=f'f2_{s}@sige.test', nome='F2',
            tipo_usuario=TipoUsuario.ADMIN,
            password_hash=generate_password_hash('Test@1234'),
            versao_sistema='v2', ativo=True,
        )
        db.session.add(admin); db.session.flush()
        cli = Cliente(nome=f'CLI-F2-{s}', admin_id=admin.id)
        db.session.add(cli); db.session.flush()
        obra = Obra(nome=f'Obra F2 {s}', codigo=f'OF2{s[:6]}', data_inicio=date(2026, 1, 1),
                    admin_id=admin.id, cliente_id=cli.id, valor_contrato=1)
        db.session.add(obra); db.session.commit()
        _fx.admin = admin; _fx.obra = obra
        yield


def _tarefa(nome, percentual=0.0):
    t = TarefaCronograma(obra_id=_fx.obra.id, nome_tarefa=nome, ordem=1, duracao_dias=1,
                         quantidade_total=100.0, percentual_concluido=percentual,
                         admin_id=_fx.admin.id)
    db.session.add(t); db.session.flush()
    return t


def _func():
    f = Funcionario(nome=f'F {_sfx()}', cpf=f'5{_sfx()}'.ljust(14, '0')[:14],
                    codigo=f'F{_sfx()[:8]}', data_admissao=date(2025, 1, 1),
                    admin_id=_fx.admin.id, tipo_remuneracao='salario', salario=0.0,
                    valor_va=0.0, valor_vt=0.0, ativo=True)
    db.session.add(f); db.session.flush()
    return f


def _rdo(data):
    r = RDO(numero_rdo=f'RDO-F2-{_sfx()}', obra_id=_fx.obra.id, data_relatorio=data,
            admin_id=_fx.admin.id, status='Finalizado', criado_por_id=_fx.admin.id)
    db.session.add(r); db.session.flush()
    return r


def _mo(rdo, func, tarefa, horas):
    db.session.add(RDOMaoObra(rdo_id=rdo.id, funcionario_id=func.id, funcao_exercida='Op',
                              horas_trabalhadas=horas, admin_id=_fx.admin.id,
                              subatividade_id=None, tarefa_cronograma_id=tarefa.id))
    db.session.flush()


def _custo_diario(rdo, func, custo_total):
    db.session.add(RDOCustoDiario(rdo_id=rdo.id, funcionario_id=func.id, admin_id=_fx.admin.id,
                                  data=rdo.data_relatorio, tipo_remuneracao_snapshot='salario',
                                  custo_total_dia=Decimal(str(custo_total)), tipo_lancamento='rdo'))
    db.session.flush()


def _ledger(categoria, valor, data, tarefa_id=None):
    pai = GestaoCustoPai(admin_id=_fx.admin.id, tipo_categoria=categoria,
                         entidade_nome=f'{categoria}', valor_total=Decimal(str(valor)),
                         status='PENDENTE')
    db.session.add(pai); db.session.flush()
    filho = GestaoCustoFilho(pai_id=pai.id, data_referencia=data, descricao=categoria,
                             valor=Decimal(str(valor)), obra_id=_fx.obra.id,
                             admin_id=_fx.admin.id, tarefa_cronograma_id=tarefa_id)
    db.session.add(filho); db.session.flush()
    return filho


def _proposta_item(snapshot, quantidade):
    prop = Proposta(admin_id=_fx.admin.id, numero=f'PROP-{_sfx()}', cliente_nome='C',
                    data_proposta=date(2026, 1, 1))
    db.session.add(prop); db.session.flush()
    pi = PropostaItem(admin_id=_fx.admin.id, proposta_id=prop.id, item_numero=1,
                      descricao='S', quantidade=Decimal(str(quantidade)), unidade='m2',
                      preco_unitario=Decimal('1'), ordem=1, composicao_snapshot=snapshot)
    db.session.add(pi); db.session.flush()
    return pi


def _item_medicao(valor_comercial, tarefa, peso, quantidade=None, proposta_item=None):
    imc = ItemMedicaoComercial(admin_id=_fx.admin.id, obra_id=_fx.obra.id, nome='IMC',
                               valor_comercial=Decimal(str(valor_comercial)),
                               quantidade=(Decimal(str(quantidade)) if quantidade is not None else None),
                               proposta_item_id=(proposta_item.id if proposta_item else None),
                               status='PENDENTE')
    db.session.add(imc); db.session.flush()
    db.session.add(ItemMedicaoCronogramaTarefa(item_medicao_id=imc.id, cronograma_tarefa_id=tarefa.id,
                                               peso=Decimal(str(peso)), admin_id=_fx.admin.id))
    db.session.flush()
    return imc


# ── testes ────────────────────────────────────────────────────────────────────

def test_custo_nao_mo_direto():
    from services.resultado_atividade_service import custo_nao_mo_atividade
    with app.app_context():
        t = _tarefa('Direto')
        _ledger('MATERIAL', 100, date(2026, 4, 1), tarefa_id=t.id)
        db.session.commit()
        assert custo_nao_mo_atividade(t) == Decimal('100.00')


def test_custo_nao_mo_rateio_total():
    from services.resultado_atividade_service import custo_nao_mo_atividade
    with app.app_context():
        t = _tarefa('Rateio100')
        f = _func(); r = _rdo(date(2026, 4, 2)); _mo(r, f, t, 8.0)
        _ledger('ALIMENTACAO', 60, date(2026, 4, 2), tarefa_id=None)  # obra-level, sem tarefa
        db.session.commit()
        # T detém 100% da hora-homem do dia → recebe os 60
        assert custo_nao_mo_atividade(t) == Decimal('60.00')


def test_custo_nao_mo_rateio_parcial():
    from services.resultado_atividade_service import custo_nao_mo_atividade
    with app.app_context():
        t1 = _tarefa('R-A'); t2 = _tarefa('R-B')
        f = _func(); r = _rdo(date(2026, 4, 4)); _mo(r, f, t1, 6.0); _mo(r, f, t2, 2.0)
        _ledger('TRANSPORTE', 80, date(2026, 4, 4), tarefa_id=None)
        db.session.commit()
        assert custo_nao_mo_atividade(t1) == Decimal('60.00')   # 80 × 6/8
        assert custo_nao_mo_atividade(t2) == Decimal('20.00')   # 80 × 2/8


def test_dc3_mo_nao_conta_duas_vezes():
    """A folha (SALARIO/VALE_*) no ledger NÃO entra no custo não-MO; o custo de MO
    vem só do RDOCustoDiario. Senão a MO contaria duas vezes."""
    from services.resultado_atividade_service import (
        custo_nao_mo_atividade, custo_incorrido_atividade,
    )
    with app.app_context():
        t = _tarefa('DC3')
        f = _func(); r = _rdo(date(2026, 4, 3)); _mo(r, f, t, 8.0); _custo_diario(r, f, 500)
        _ledger('SALARIO', 999, date(2026, 4, 3), tarefa_id=t.id)        # folha no ledger
        _ledger('VALE_ALIMENTACAO', 50, date(2026, 4, 3), tarefa_id=t.id)  # auxílio no ledger
        _ledger('MATERIAL', 120, date(2026, 4, 3), tarefa_id=t.id)        # não-MO real
        db.session.commit()
        # não-MO conta só o MATERIAL (120); SALARIO e VALE_* são excluídos (DC3)
        assert custo_nao_mo_atividade(t) == Decimal('120.00')
        # incorrido = MO do RDOCustoDiario (500) + não-MO (120) = 620 (não 500+999+50+120)
        assert custo_incorrido_atividade(t) == Decimal('620.00')


def test_alarme_custo_total():
    from services.resultado_atividade_service import alarme_custo
    with app.app_context():
        snap = [
            {'tipo': 'MAO_OBRA', 'unidade': 'm2', 'coeficiente': 1.0, 'subtotal_unitario': 10.0},
            {'tipo': 'MATERIAL', 'unidade': 'm2', 'coeficiente': 1.0, 'subtotal_unitario': 40.0},
        ]
        pi = _proposta_item(snap, 100)            # orçado total = (10+40) × 100 = 5000
        t = _tarefa('AlarmeTotal', percentual=50.0)
        _item_medicao(valor_comercial=8000, tarefa=t, peso=100, quantidade=100, proposta_item=pi)
        f = _func(); r = _rdo(date(2026, 4, 5)); _mo(r, f, t, 8.0); _custo_diario(r, f, 700)
        _ledger('MATERIAL', 300, date(2026, 4, 5), tarefa_id=t.id)
        db.session.commit()
        a = alarme_custo(t)
        assert a['orcado_total'] == Decimal('5000.00')
        assert a['orcado_para_avanco'] == Decimal('2500.00')   # 50% × 5000
        assert a['real'] == Decimal('1000.00')                 # MO 700 + material 300
        assert a['estouro'] is False
