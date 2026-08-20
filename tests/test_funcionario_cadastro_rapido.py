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


# ---------------------------------------------------------------------------
# Rodada 1 de fix — os dois testes acima só provam o modelo/ORM. A tela real
# passa pelo POST /funcionarios (criação) e POST /funcionarios/<id>/editar
# (edição), com um guard de JS na frente (`validateForm()` em
# templates/funcionarios.html) e uma checagem de duplicidade no servidor.
# Nenhum dos dois testes acima bate nessa rota — daí o `_client_como` já
# importado e nunca usado ter sido a pista perdida na rodada anterior.
# ---------------------------------------------------------------------------

def test_post_criar_dois_funcionarios_sem_cpf_convivem_via_rota():
    """POST real em /funcionarios com cpf='' precisa gravar NULL (não '')
    e dois cadastros assim seguidos não podem colidir no UNIQUE."""
    with app.app_context():
        admin, _obra = _ambiente()
        admin_id = admin.id
        c = _client_como(admin_id)

        resp1 = c.post('/funcionarios', data={
            'nome': 'Luiz Rota', 'cpf': '', 'codigo': f'C1{admin_id}',
            'data_admissao': '2026-08-20',
        })
        assert resp1.status_code in (200, 302)

        resp2 = c.post('/funcionarios', data={
            'nome': 'Fabrício Rota', 'cpf': '', 'codigo': f'C2{admin_id}',
            'data_admissao': '2026-08-20',
        })
        assert resp2.status_code in (200, 302)

        f1 = Funcionario.query.filter_by(admin_id=admin_id, codigo=f'C1{admin_id}').first()
        f2 = Funcionario.query.filter_by(admin_id=admin_id, codigo=f'C2{admin_id}').first()
        assert f1 is not None and f2 is not None
        assert f1.cpf is None, f"esperado NULL, veio {f1.cpf!r}"
        assert f2.cpf is None, f"esperado NULL, veio {f2.cpf!r}"


def test_post_editar_limpando_cpf_grava_null_e_preserva_outros_campos():
    """POST real em /funcionarios/<id>/editar limpando o CPF precisa gravar
    NULL (não ''), dois funcionários editados assim não podem colidir no
    UNIQUE, e um campo irmão trocado na mesma submissão precisa persistir —
    é a regressão de perda de dados do Critical 2 (rollback do except
    genérico quando a UniqueViolation de '' == '' estourava)."""
    with app.app_context():
        admin, _obra = _ambiente()
        admin_id = admin.id
        c = _client_como(admin_id)

        f1 = Funcionario(codigo=f'E1{admin_id}', nome='Original Um',
                          cpf=f'11111111{admin_id % 100:03d}',
                          data_admissao=date(2026, 8, 20),
                          admin_id=admin_id, ativo=True)
        f2 = Funcionario(codigo=f'E2{admin_id}', nome='Original Dois',
                          cpf=f'22222222{admin_id % 100:03d}',
                          data_admissao=date(2026, 8, 20),
                          admin_id=admin_id, ativo=True)
        db.session.add_all([f1, f2])
        db.session.commit()
        f1_id, f2_id = f1.id, f2.id

        resp1 = c.post(f'/funcionarios/{f1_id}/editar', data={
            'nome': 'Editado Um', 'cpf': '',
        })
        assert resp1.status_code in (200, 302)

        resp2 = c.post(f'/funcionarios/{f2_id}/editar', data={
            'nome': 'Editado Dois', 'cpf': '',
        })
        assert resp2.status_code in (200, 302)

        db.session.expire_all()
        f1_depois = Funcionario.query.get(f1_id)
        f2_depois = Funcionario.query.get(f2_id)

        assert f1_depois.cpf is None, f"esperado NULL, veio {f1_depois.cpf!r}"
        assert f2_depois.cpf is None, f"esperado NULL, veio {f2_depois.cpf!r}"
        # Prova de que a UniqueViolation não estourou e não fez rollback: o
        # nome trocado na mesma submissão precisa ter sobrevivido.
        assert f1_depois.nome == 'Editado Um'
        assert f2_depois.nome == 'Editado Dois'
