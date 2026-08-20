"""Efetivo do RDO: pessoal operacional próprio + equipes de terceiros.

Reunião de 2026-08-20: o Alan anota "Abraão, 11 pessoas" no papel porque o
RDO não tem onde registrar terceiro fora das tarefas marcadas como
`responsavel='subempreitada'`; e o seletor de efetivo lista o pessoal
administrativo junto com o de campo.
"""
import os
import sys
from datetime import date

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import main  # noqa: F401 — registra os blueprints
from app import app, db
from models import Funcao, Funcionario
from test_cronograma_versao_service import _ambiente

pytestmark = pytest.mark.integration


@pytest.fixture(autouse=True)
def _config():
    app.config['TESTING'] = True
    app.config['WTF_CSRF_ENABLED'] = False
    if not app.secret_key:
        app.secret_key = 'test-rdo-efetivo'
    yield


def test_funcao_nasce_operacional():
    """Default TRUE — nenhuma função existente some do RDO no deploy."""
    with app.app_context():
        admin, _obra = _ambiente()
        f = Funcao(nome='Montador', admin_id=admin.id, salario_base=0.0)
        db.session.add(f)
        db.session.commit()
        assert f.operacional is True


def test_funcao_pode_ser_marcada_como_administrativa():
    with app.app_context():
        admin, _obra = _ambiente()
        f = Funcao(nome='Auxiliar Administrativo', admin_id=admin.id,
                   salario_base=0.0, operacional=False)
        db.session.add(f)
        db.session.commit()
        assert f.operacional is False
