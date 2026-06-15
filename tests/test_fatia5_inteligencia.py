"""Fatia 5 — learning loop de produtividade + roll-up de portfólio."""
import os
import sys
from datetime import date, datetime
from decimal import Decimal

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app import app, db
import main  # noqa: F401 — registra blueprints (rota /resultado/portfolio)
from models import (
    Usuario, TipoUsuario, Funcionario, Obra, Cliente,
    RDO, RDOMaoObra, RDOCustoDiario, RDOServicoSubatividade, SubatividadeMestre,
    TarefaCronograma, ItemMedicaoComercial, ItemMedicaoCronogramaTarefa,
)
from werkzeug.security import generate_password_hash


_SEQ = [0]


def _sfx():
    _SEQ[0] += 1
    return datetime.utcnow().strftime('%H%M%S%f') + str(_SEQ[0])


def _novo_admin():
    s = _sfx()
    a = Usuario(username=f'f5_{s}', email=f'f5_{s}@sige.test', nome='F5',
                tipo_usuario=TipoUsuario.ADMIN,
                password_hash=generate_password_hash('Test@1234'),
                versao_sistema='v2', ativo=True)
    db.session.add(a); db.session.flush()
    return a


def _obra(admin):
    s = _sfx()
    cli = Cliente(nome=f'CLI-{s}', admin_id=admin.id); db.session.add(cli); db.session.flush()
    o = Obra(nome=f'Obra {s}', codigo=f'O5{s[-9:]}', data_inicio=date(2026, 1, 1),
             admin_id=admin.id, cliente_id=cli.id, valor_contrato=1)
    db.session.add(o); db.session.flush()
    return o


def _func(admin):
    f = Funcionario(nome=f'F {_sfx()}', cpf=f'3{_sfx()}'.ljust(14, '0')[:14],
                    codigo=f'F{_sfx()[-9:]}', data_admissao=date(2025, 1, 1),
                    admin_id=admin.id, tipo_remuneracao='salario', salario=0.0, ativo=True)
    db.session.add(f); db.session.flush()
    return f


def _rdo(admin, obra, data):
    r = RDO(numero_rdo=f'RDO-{_sfx()}', obra_id=obra.id, data_relatorio=data,
            admin_id=admin.id, status='Finalizado', criado_por_id=admin.id)
    db.session.add(r); db.session.flush()
    return r


# ── PARTE A — learning loop ───────────────────────────────────────────────────

def test_produtividade_observada_e_atualiza_catalogo():
    from services.aprendizado_produtividade import (
        produtividade_observada, atualizar_catalogo_produtividade,
    )
    with app.app_context():
        admin = _novo_admin(); obra = _obra(admin)
        sm = SubatividadeMestre(nome=f'Alvenaria {_sfx()}', tipo='subatividade',
                                admin_id=admin.id, ativo=True,
                                meta_produtividade=5.0, duracao_estimada_horas=10.0,
                                unidade_medida='m2')
        db.session.add(sm); db.session.flush()

        # 3 RDOs finalizados com produtividade real observada = 8 m²/h
        for i in range(3):
            r = _rdo(admin, obra, date(2026, 5, i + 1))
            f = _func(admin)
            rss = RDOServicoSubatividade(rdo_id=r.id, nome_subatividade='Alvenaria',
                                         admin_id=admin.id, subatividade_mestre_id=sm.id,
                                         percentual_conclusao=100.0)
            db.session.add(rss); db.session.flush()
            db.session.add(RDOMaoObra(rdo_id=r.id, funcionario_id=f.id, funcao_exercida='Op',
                                      horas_trabalhadas=8.0, admin_id=admin.id,
                                      subatividade_id=rss.id, produtividade_real=8.0))
        db.session.commit()

        media, n = produtividade_observada(sm.id, admin.id)
        assert n == 3
        assert media == Decimal('8')

        # EMA: 5×0,7 + 8×0,3 = 5,9 ; duração coerente 10×(5/5,9)
        n_upd = atualizar_catalogo_produtividade(admin.id)
        assert n_upd == 1
        db.session.refresh(sm)
        assert abs(sm.meta_produtividade - 5.9) < 0.001
        assert abs(sm.duracao_estimada_horas - (10.0 * 5.0 / 5.9)) < 0.01


def test_learning_loop_respeita_min_amostras():
    from services.aprendizado_produtividade import atualizar_catalogo_produtividade
    with app.app_context():
        admin = _novo_admin(); obra = _obra(admin)
        sm = SubatividadeMestre(nome=f'Pintura {_sfx()}', tipo='subatividade',
                                admin_id=admin.id, ativo=True, meta_produtividade=5.0)
        db.session.add(sm); db.session.flush()
        # apenas 1 amostra (< min_amostras=3) → não atualiza
        r = _rdo(admin, obra, date(2026, 5, 10)); f = _func(admin)
        rss = RDOServicoSubatividade(rdo_id=r.id, nome_subatividade='Pintura',
                                     admin_id=admin.id, subatividade_mestre_id=sm.id)
        db.session.add(rss); db.session.flush()
        db.session.add(RDOMaoObra(rdo_id=r.id, funcionario_id=f.id, funcao_exercida='Op',
                                  horas_trabalhadas=8.0, admin_id=admin.id,
                                  subatividade_id=rss.id, produtividade_real=9.0))
        db.session.commit()
        assert atualizar_catalogo_produtividade(admin.id) == 0
        db.session.refresh(sm)
        assert sm.meta_produtividade == 5.0   # inalterado


# ── PARTE B — portfólio ───────────────────────────────────────────────────────

def test_resultado_portfolio_consolida_obras():
    from services.resultado_atividade_service import resultado_portfolio
    with app.app_context():
        admin = _novo_admin()
        # 2 obras, cada uma com 1 atividade 100% concluída
        for venda, custo in ((1000, 300), (500, 100)):
            obra = _obra(admin)
            t = TarefaCronograma(obra_id=obra.id, nome_tarefa='A', ordem=1, duracao_dias=1,
                                 quantidade_total=100.0, percentual_concluido=100.0,
                                 admin_id=admin.id)
            db.session.add(t); db.session.flush()
            imc = ItemMedicaoComercial(admin_id=admin.id, obra_id=obra.id, nome='IMC',
                                       valor_comercial=Decimal(str(venda)), status='PENDENTE')
            db.session.add(imc); db.session.flush()
            db.session.add(ItemMedicaoCronogramaTarefa(item_medicao_id=imc.id,
                                                       cronograma_tarefa_id=t.id,
                                                       peso=Decimal('100'), admin_id=admin.id))
            f = _func(admin); r = _rdo(admin, obra, date(2026, 5, 20))
            db.session.add(RDOMaoObra(rdo_id=r.id, funcionario_id=f.id, funcao_exercida='Op',
                                      horas_trabalhadas=8.0, admin_id=admin.id,
                                      subatividade_id=None, tarefa_cronograma_id=t.id))
            db.session.add(RDOCustoDiario(rdo_id=r.id, funcionario_id=f.id, admin_id=admin.id,
                                          data=r.data_relatorio, tipo_remuneracao_snapshot='salario',
                                          custo_total_dia=Decimal(str(custo)), tipo_lancamento='rdo'))
        db.session.commit()

        p = resultado_portfolio(admin.id)
        assert len(p['obras']) == 2
        assert p['valor_agregado'] == Decimal('1500.00')      # 1000 + 500
        assert p['custo_incorrido'] == Decimal('400.00')      # 300 + 100
        assert p['resultado'] == Decimal('1100.00')


def test_rota_portfolio_responde():
    with app.app_context():
        admin = _novo_admin()
        with app.test_client() as c:
            with c.session_transaction() as sess:
                sess['_user_id'] = str(admin.id)
                sess['_fresh'] = True
            resp = c.get('/resultado/portfolio')
        assert resp.status_code == 200, resp.status_code
        assert b'Portf' in resp.data
