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


def _login(admin_id):
    """Client autenticado, fora de app_context aberto.

    `_client_como` recebe o ID do usuário, não o objeto — e depois que o
    app_context fecha o objeto está detached, então o ID tem de ser capturado
    ainda dentro do contexto.
    """
    from test_cronograma_endpoints_m05 import _client_como
    return _client_como(admin_id)


def _cenario_efetivo():
    """Um funcionário operacional (Montador) e um administrativo."""
    with app.app_context():
        admin, obra = _ambiente()
        op = Funcao(nome='Montador', admin_id=admin.id, salario_base=0.0,
                    operacional=True)
        adm = Funcao(nome='Auxiliar Administrativo', admin_id=admin.id,
                     salario_base=0.0, operacional=False)
        db.session.add_all([op, adm])
        db.session.flush()
        # CPF é único GLOBAL: derivar os dois do mesmo admin_id com sufixos
        # distintos, senão o "admin.id + 1" de um teste colide com o
        # "admin.id" do teste seguinte (os ids são sequenciais).
        db.session.add(Funcionario(
            codigo=f'OP{admin.id}', nome='Davi Montador',
            cpf=f'{admin.id:09d}01',
            data_admissao=date(2026, 1, 5), admin_id=admin.id,
            funcao_id=op.id, ativo=True))
        db.session.add(Funcionario(
            codigo=f'AD{admin.id}', nome='Ana Escritorio',
            cpf=f'{admin.id:09d}02',
            data_admissao=date(2026, 1, 5), admin_id=admin.id,
            funcao_id=adm.id, ativo=True))
        db.session.commit()
        return admin.id, obra.id


def test_api_efetivo_filtra_administrativo():
    admin_id, obra_id = _cenario_efetivo()
    client = _login(admin_id)

    resp = client.get(f'/api/obras/{obra_id}/funcionarios?operacional=1')

    assert resp.status_code == 200
    nomes = [f['nome'] for f in resp.get_json()['funcionarios']]
    assert 'Davi Montador' in nomes
    assert 'Ana Escritorio' not in nomes


def test_api_sem_parametro_continua_devolvendo_todos():
    """Outras telas consomem esta rota — sem o parâmetro nada muda."""
    admin_id, obra_id = _cenario_efetivo()
    client = _login(admin_id)

    resp = client.get(f'/api/obras/{obra_id}/funcionarios')

    nomes = [f['nome'] for f in resp.get_json()['funcionarios']]
    assert 'Davi Montador' in nomes
    assert 'Ana Escritorio' in nomes
