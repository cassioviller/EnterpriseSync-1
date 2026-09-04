"""Fatia 4 — lente de caixa por obra (Realizado/Previsto), reúso do FinanceiroService."""
import os
import sys
from datetime import date, datetime
from decimal import Decimal

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app import app, db
import main  # noqa: F401 — registra blueprints (rota /obras/<id>/caixa)
from models import Usuario, TipoUsuario, Obra, Cliente, ContaReceber
from werkzeug.security import generate_password_hash


def _sfx():
    return datetime.utcnow().strftime('%H%M%S%f')


class FX:
    admin = None
    obra_a = None
    obra_b = None


_fx = FX()


@pytest.fixture(scope='module', autouse=True)
def ambiente():
    app.config['TESTING'] = True
    with app.app_context():
        s = _sfx()
        admin = Usuario(username=f'cx_{s}', email=f'cx_{s}@sige.test', nome='CX',
                        tipo_usuario=TipoUsuario.ADMIN,
                        password_hash=generate_password_hash('Test@1234'),
                        versao_sistema='v2', ativo=True)
        db.session.add(admin); db.session.flush()
        cli = Cliente(nome=f'CLI-CX-{s}', admin_id=admin.id); db.session.add(cli); db.session.flush()
        oa = Obra(nome=f'Obra CXA {s}', codigo=f'CXA{s[:6]}', data_inicio=date(2026, 1, 1),
                  admin_id=admin.id, cliente_id=cli.id, valor_contrato=1)
        ob = Obra(nome=f'Obra CXB {s}', codigo=f'CXB{s[:6]}', data_inicio=date(2026, 1, 1),
                  admin_id=admin.id, cliente_id=cli.id, valor_contrato=1)
        db.session.add_all([oa, ob]); db.session.commit()
        _fx.admin = admin; _fx.obra_a = oa; _fx.obra_b = ob
        yield


def _conta_receber(obra_id, valor, venc=date(2026, 6, 1)):
    cr = ContaReceber(
        admin_id=_fx.admin.id, obra_id=obra_id, cliente_nome='Cliente',
        descricao='Medição', valor_original=Decimal(str(valor)),
        saldo=Decimal(str(valor)), data_emissao=date(2026, 1, 1),
        data_vencimento=venc, status='PENDENTE',
    )
    db.session.add(cr); db.session.flush()
    return cr


def test_fluxo_caixa_obra_escopo_por_obra():
    from services.caixa_obra_service import fluxo_caixa_obra
    with app.app_context():
        _conta_receber(_fx.obra_a.id, 1000)
        _conta_receber(_fx.obra_b.id, 500)
        db.session.commit()
        r = fluxo_caixa_obra(_fx.admin.id, _fx.obra_a.id, date(2026, 1, 1), date(2026, 12, 31))
        # só a obra A entra (500 da obra B fica de fora)
        assert float(r['fluxo']['entradas_previstas']) == 1000.0


def test_fluxo_caixa_obra_estrutura_e_variacao_de_zero():
    from services.caixa_obra_service import fluxo_caixa_obra
    with app.app_context():
        r = fluxo_caixa_obra(_fx.admin.id, _fx.obra_b.id, date(2026, 1, 1), date(2026, 12, 31))
        assert set(r.keys()) >= {'fluxo', 'meses', 'kpis', 'serie_chart'}
        # Realizado e Previsto existem separados (ADR 0003 — nunca somados num número só)
        assert 'realizado_liquido' in r['kpis']
        assert 'previsto_liquido' in r['kpis']
        # sem movimentos Realizados → realizado começa em 0
        assert r['kpis']['realizado_liquido'] == 0.0


def test_rota_caixa_responde():
    with app.app_context():
        with app.test_client() as c:
            with c.session_transaction() as sess:
                sess['_user_id'] = str(_fx.admin.id)
                sess['_fresh'] = True
            resp = c.get(f'/obras/{_fx.obra_a.id}/caixa')
        assert resp.status_code == 200, resp.status_code
        assert b'Caixa da obra' in resp.data
