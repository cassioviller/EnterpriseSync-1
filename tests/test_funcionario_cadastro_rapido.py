"""Cadastro rápido de funcionário — reunião de 2026-08-20.

A Ana cadastra e remove gente toda semana ("Fabrício entrou, ficou dois
dias e já saiu"). Exigir CPF na hora do cadastro trava o fluxo: ela não
sabe o CPF de quem acabou de chegar na obra.
"""
import os
import sys
from datetime import date

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import main  # noqa: F401 — registra os blueprints
from app import app, db
from models import Funcionario
from test_cronograma_endpoints_m05 import _client_como
from test_cronograma_versao_service import _ambiente

pytestmark = pytest.mark.integration


@pytest.fixture(autouse=True)
def _config():
    app.config['TESTING'] = True
    app.config['WTF_CSRF_ENABLED'] = False
    if not app.secret_key:
        app.secret_key = 'test-cadastro-rapido'
    yield


def test_funcionario_pode_nascer_sem_cpf():
    with app.app_context():
        admin, _obra = _ambiente()
        f = Funcionario(codigo=f'RA{admin.id}', nome='Luiz Ajudante',
                        cpf=None, data_admissao=date(2026, 8, 20),
                        admin_id=admin.id, ativo=True)
        db.session.add(f)
        db.session.commit()
        assert f.id is not None
        assert f.cpf is None


def test_dois_funcionarios_sem_cpf_convivem():
    """O UNIQUE da coluna aceita múltiplos NULL no Postgres — se este
    teste quebrar, o índice precisa virar parcial (WHERE cpf IS NOT NULL)."""
    with app.app_context():
        admin, _obra = _ambiente()
        db.session.add(Funcionario(
            codigo=f'R1{admin.id}', nome='Luiz', cpf=None,
            data_admissao=date(2026, 8, 20), admin_id=admin.id, ativo=True))
        db.session.add(Funcionario(
            codigo=f'R2{admin.id}', nome='Fabrício', cpf=None,
            data_admissao=date(2026, 8, 20), admin_id=admin.id, ativo=True))
        db.session.commit()
        assert Funcionario.query.filter_by(
            admin_id=admin.id, cpf=None).count() == 2
