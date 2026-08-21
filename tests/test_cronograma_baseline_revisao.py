"""Revisões da linha de base — reunião de 2026-08-20.

O primeiro cronograma aprovado é a V1 e não se mexe. Durante a obra o
Alan move o PLANEJADO. Quando entra um aditivo, sobe uma V2 — e as duas
ficam guardadas para responder "era pra entregar tal dia; com o aditivo
virou tal dia".
"""
import os
import sys
from datetime import date

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import main  # noqa: F401 — registra os blueprints
from app import app, db
from models import ConfiguracaoEmpresa, CronogramaBaseline
from test_cronograma_endpoints_m05 import _client_como
from test_cronograma_versao_service import _ambiente, _tarefa

pytestmark = pytest.mark.integration


@pytest.fixture(autouse=True)
def _config():
    app.config['TESTING'] = True
    app.config['WTF_CSRF_ENABLED'] = False
    if not app.secret_key:
        app.secret_key = 'test-baseline-revisao'
    yield


def _flag_editor_v2(admin_id: int, ativo: bool = True) -> None:
    config = ConfiguracaoEmpresa.query.filter_by(admin_id=admin_id).first()
    if config is None:
        config = ConfiguracaoEmpresa(admin_id=admin_id,
                                     nome_empresa=f'Empresa {admin_id}')
        db.session.add(config)
    config.cronograma_editor_v2 = bool(ativo)
    db.session.commit()


def _cenario():
    """Obra com duas folhas datadas, editor v2 ligado."""
    with app.app_context():
        admin, obra = _ambiente()
        _flag_editor_v2(admin.id, True)
        _tarefa(obra, admin, 'Fundação', ordem=0, duracao_dias=5,
                data_inicio=date(2026, 7, 1), data_fim=date(2026, 7, 7))
        _tarefa(obra, admin, 'Painelização', ordem=1, duracao_dias=3,
                data_inicio=date(2026, 7, 8), data_fim=date(2026, 7, 10))
        # `_client_como` recebe o ID; e o objeto ORM devolvido de dentro do
        # contexto já está destacado quando ele fecha.
        return admin.id, obra.id


def test_primeira_baseline_nasce_revisao_1():
    admin_id, obra_id = _cenario()
    client = _client_como(admin_id)

    resp = client.post(f'/cronograma/obra/{obra_id}/baseline',
                       json={'nome': 'Cronograma aprovado'})

    assert resp.status_code == 201, resp.get_data(as_text=True)
    assert resp.get_json()['baseline']['revisao'] == 1


def test_segunda_baseline_incrementa_a_revisao_e_grava_motivo():
    admin_id, obra_id = _cenario()
    client = _client_como(admin_id)
    client.post(f'/cronograma/obra/{obra_id}/baseline',
                json={'nome': 'Cronograma aprovado'})

    resp = client.post(f'/cronograma/obra/{obra_id}/baseline',
                       json={'nome': 'Pós-aditivo', 'motivo': 'Aditivo 01'})

    bl = resp.get_json()['baseline']
    assert bl['revisao'] == 2
    assert bl['motivo'] == 'Aditivo 01'


def test_revisao_e_sequencial_por_obra():
    """A sequência conta por obra: duas obras do mesmo tenant não se misturam."""
    admin_a_id, obra_a = _cenario()
    _admin_b_id, obra_b = _cenario()

    client_a = _client_como(admin_a_id)
    client_a.post(f'/cronograma/obra/{obra_a}/baseline', json={})
    client_a.post(f'/cronograma/obra/{obra_a}/baseline', json={})

    with app.app_context():
        rev_a = sorted(b.revisao for b in CronogramaBaseline.query
                       .filter_by(obra_id=obra_a).all())
        rev_b = [b.revisao for b in CronogramaBaseline.query
                 .filter_by(obra_id=obra_b).all()]
    assert rev_a == [1, 2]
    assert rev_b == []  # a obra B não recebeu baseline nenhuma
