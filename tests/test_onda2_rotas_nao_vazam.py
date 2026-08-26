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
from models import (Cliente, Funcionario, Obra, RDO, TipoUsuario, Usuario)

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


# ---------------------------------------------------------------------------
# Task 3, Fix Round 1 — teste de comportamento do guard
# ---------------------------------------------------------------------------

def test_usuario_orfao_sem_tenant_nao_consegue_salvar_rdo_e_recebe_403():
    """Usuário órfão (sem admin_id) não consegue salvar RDO — recebe 403.

    Valida o guard `if admin_id_correto is None: abort(403)` em
    `views/rdo.py:2847-2848`. Sem esse guard, `admin_id_correto=None`
    fluiria para as queries (Obra.admin_id == None), que devolveriam zero
    linhas em silêncio, permitindo gravação indevida. O teste verifica que:

    1. Usuário órfão recebe 403 na tentativa
    2. Nenhum RDO foi gravado (prova que a operação foi bloqueada)
    """
    # Importar cliente_de — atalho de sessão para autenticar
    def cliente_de(user_id):
        """Test client autenticado como `user_id`."""
        c = app.test_client()
        with c.session_transaction() as s:
            s['_user_id'] = str(user_id)
            s['_fresh'] = True
        return c

    # Preparar dados dentro de app context
    with app.app_context():
        # Criar um usuário órfão: Usuario do tipo FUNCIONARIO, mas sem Funcionario
        # associado, ou com Funcionario.admin_id=None (vínculo corrompido)
        marca_unica = f"orfao_{uuid.uuid4().hex[:8]}"
        usuario_orfao = Usuario(
            username=marca_unica,
            email=f'{marca_unica}@test.local',
            nome='Usuario Orfao',
            password_hash=generate_password_hash('Senha@2026'),
            tipo_usuario=TipoUsuario.FUNCIONARIO,
            ativo=True,
            versao_sistema='v2'
        )
        db.session.add(usuario_orfao)
        db.session.commit()

        # Criar uma obra real para tentar usar
        marca_admin = f"admin_{uuid.uuid4().hex[:8]}"
        admin_de_verdade = Usuario(
            username=marca_admin,
            email=f'{marca_admin}@real.local',
            nome='Admin Real',
            password_hash=generate_password_hash('Senha@2026'),
            tipo_usuario=TipoUsuario.ADMIN,
            ativo=True,
            versao_sistema='v2'
        )
        db.session.add(admin_de_verdade)
        db.session.commit()

        cliente_real = Cliente(nome='Cliente Real', admin_id=admin_de_verdade.id)
        db.session.add(cliente_real)
        db.session.flush()

        obra_real = Obra(
            nome='Obra Real',
            codigo='OBRA01',
            data_inicio=date(2026, 1, 1),
            admin_id=admin_de_verdade.id,
            cliente_id=cliente_real.id,
            valor_contrato=100000,
            orcamento=100000,
            status='Em andamento'
        )
        db.session.add(obra_real)
        db.session.commit()

        # Contar RDOs antes
        rdos_antes = RDO.query.count()
        obra_id = obra_real.id
        usuario_id = usuario_orfao.id

    # Autenticar como usuário órfão (fora do context)
    cliente = cliente_de(usuario_id)

    # Tentar salvar RDO como órfão
    resposta = cliente.post(
        '/rdo/salvar',
        data={
            'obra_id': obra_id,
            'data_relatorio': '2026-08-26'
        },
        follow_redirects=False
    )

    # Verificar que recebeu 403 (o guard `if admin_id_correto is None: abort(403)` agora sai)
    assert resposta.status_code == 403, (
        f'Usuário órfão deveria receber 403, recebeu {resposta.status_code}')

    # Verificar que nenhum RDO foi gravado (dentro de um novo context)
    with app.app_context():
        rdos_depois = RDO.query.count()
        assert rdos_depois == rdos_antes, (
            f'RDO foi gravado mesmo com 403: antes={rdos_antes}, depois={rdos_depois}')
