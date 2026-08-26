"""Onda 2 — 14 vazamentos de tenant fechados.

Testes sobre as rotas que vazam tenant resolver mal.
"""
import os
import sys
import uuid
from datetime import date, timedelta
from decimal import Decimal

import pytest
from werkzeug.security import generate_password_hash

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import main  # noqa: F401 — registra blueprints e handlers de evento
from app import app, db
from models import Cliente, Obra, TipoUsuario, Usuario

pytestmark = pytest.mark.integration


@pytest.fixture(autouse=True)
def _config():
    app.config['TESTING'] = True
    app.config['WTF_CSRF_ENABLED'] = False
    if not app.secret_key:
        app.secret_key = 'test-onda2-rotas'
    yield


# ---------------------------------------------------------------------------
# Task 3 — o `return 10`
# ---------------------------------------------------------------------------

def test_rdo_nao_tem_mais_admin_id_fixo_no_codigo():
    """🔴 `views/rdo.py:2848`: o `except` devolvia `10` — um tenant de alguém."""
    import inspect

    import views.rdo as rdo_mod
    fonte = inspect.getsource(rdo_mod)
    assert 'return 10' not in fonte, (
        'views/rdo.py ainda tem admin_id fixo no fallback')


def test_rdo_nao_resolve_tenant_por_email_sem_escopo():
    """A estratégia 3 buscava Funcionario por e-mail, sem admin_id.

    E-mail repetido entre empresas devolvia o funcionário da outra.
    """
    import inspect

    import views.rdo as rdo_mod
    fonte = inspect.getsource(rdo_mod)
    assert 'Funcionario.query.filter_by(email=current_user.email)' not in fonte
