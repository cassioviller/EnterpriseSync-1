"""M10 Task 1 — flag de rollout da importação de cronograma por tenant.

A área do M08 exige V2 **e** `configuracao_empresa.cronograma_mpp_ativo`
(migração 211, default FALSE). O helper `utils.tenant.cronograma_mpp_ativo`
é lido em context processor: falha segura (False), nunca levanta.

NOTA de harness: os asserts do helper rodam em `test_request_context`
próprios com `login_user` — o helper depende de `current_user`.
"""
import os
import sys
import uuid
from datetime import date

import pytest
from flask_login import login_user
from werkzeug.security import generate_password_hash

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app import app, db
from models import Cliente, ConfiguracaoEmpresa, Obra, TipoUsuario, Usuario
from scripts.flag_cronograma_mpp import definir_flag, status_flag
from utils.tenant import cronograma_mpp_ativo

pytestmark = pytest.mark.integration

SENHA = 'Senha@2026'


@pytest.fixture(autouse=True)
def _config():
    app.config['TESTING'] = True
    app.config['WTF_CSRF_ENABLED'] = False
    if not app.secret_key:
        app.secret_key = 'test-flag-mpp'
    yield


def _admin(versao='v2'):
    """Admin novo SEM configuracao_empresa (estado de tenant recém-criado)."""
    suf = uuid.uuid4().hex[:8]
    admin = Usuario(
        username=f'flag_{suf}', email=f'flag_{suf}@test.local',
        nome=f'Admin Flag {suf}',
        password_hash=generate_password_hash(SENHA),
        tipo_usuario=TipoUsuario.ADMIN, ativo=True, versao_sistema=versao,
    )
    db.session.add(admin)
    db.session.commit()
    return admin


def _flag_como(usuario_id):
    """Valor do helper com o usuário autenticado."""
    with app.test_request_context('/'):
        usuario = db.session.get(Usuario, usuario_id)
        login_user(usuario)
        return cronograma_mpp_ativo()


# ---------------------------------------------------------------------------
# Helper — as quatro combinações que importam
# ---------------------------------------------------------------------------

def test_sem_configuracao_a_flag_e_falsa():
    """Tenant V2 recém-criado não vê a área até a fase do rollout ligar."""
    with app.app_context():
        admin_id = _admin().id
        assert ConfiguracaoEmpresa.query.filter_by(
            admin_id=admin_id).first() is None
        assert _flag_como(admin_id) is False


def test_configuracao_com_flag_desligada_e_falsa():
    with app.app_context():
        admin_id = _admin().id
        definir_flag(admin_id, False)
        assert _flag_como(admin_id) is False


def test_v2_com_flag_ligada_e_verdadeira():
    with app.app_context():
        admin_id = _admin().id
        definir_flag(admin_id, True)
        assert _flag_como(admin_id) is True


def test_flag_ligada_sem_v2_continua_falsa():
    """V2 segue sendo pré-requisito: a área vive dentro da V2."""
    with app.app_context():
        admin_id = _admin(versao='v1').id
        definir_flag(admin_id, True)
        assert _flag_como(admin_id) is False


def test_anonimo_nao_levanta_e_devolve_falso():
    with app.test_request_context('/'):
        assert cronograma_mpp_ativo() is False


# ---------------------------------------------------------------------------
# CLI / instrumento de rollout
# ---------------------------------------------------------------------------

def test_definir_flag_cria_configuracao_quando_nao_existe():
    with app.app_context():
        admin_id = _admin().id
        assert definir_flag(admin_id, True) is True
        config = ConfiguracaoEmpresa.query.filter_by(admin_id=admin_id).first()
        assert config is not None
        assert config.cronograma_mpp_ativo is True
        # nome_empresa é NOT NULL — a criação mínima precisa preenchê-lo.
        assert config.nome_empresa


def test_definir_flag_preserva_configuracao_existente():
    with app.app_context():
        admin_id = _admin().id
        db.session.add(ConfiguracaoEmpresa(
            admin_id=admin_id, nome_empresa='Empresa Original',
            cnpj='00.000.000/0001-00'))
        db.session.commit()

        definir_flag(admin_id, True)
        config = ConfiguracaoEmpresa.query.filter_by(admin_id=admin_id).first()
        assert config.nome_empresa == 'Empresa Original'
        assert config.cnpj == '00.000.000/0001-00'
        assert config.cronograma_mpp_ativo is True


def test_liga_e_desliga_e_idempotente():
    with app.app_context():
        admin_id = _admin().id
        assert definir_flag(admin_id, True) is True
        assert definir_flag(admin_id, True) is True
        assert _flag_como(admin_id) is True
        assert definir_flag(admin_id, False) is False
        assert definir_flag(admin_id, False) is False
        assert _flag_como(admin_id) is False
        assert ConfiguracaoEmpresa.query.filter_by(admin_id=admin_id).count() == 1


def test_status_flag_reporta_o_estado_do_tenant():
    with app.app_context():
        admin_id = _admin().id
        antes = status_flag(admin_id)
        assert antes == {'admin_id': admin_id, 'admin_existe': True,
                         'versao_sistema': 'v2', 'tem_configuracao': False,
                         'cronograma_mpp_ativo': False}
        definir_flag(admin_id, True)
        depois = status_flag(admin_id)
        assert depois['tem_configuracao'] is True
        assert depois['cronograma_mpp_ativo'] is True


def test_status_flag_de_admin_inexistente():
    with app.app_context():
        estado = status_flag(99_999_999)
        assert estado['admin_existe'] is False
        assert estado['cronograma_mpp_ativo'] is False


# ---------------------------------------------------------------------------
# Migração 211 — schema
# ---------------------------------------------------------------------------

def test_migration_211_coluna_existe_com_default_falso():
    from sqlalchemy import text as sa_text
    with app.app_context():
        with db.engine.connect() as conn:
            linha = conn.execute(sa_text("""
                SELECT is_nullable, column_default FROM information_schema.columns
                WHERE table_name = 'configuracao_empresa'
                  AND column_name = 'cronograma_mpp_ativo'
            """)).fetchone()
        assert linha is not None, 'migração 211 não aplicada'
        is_nullable, default = linha
        assert is_nullable == 'NO'
        assert 'false' in str(default).lower()


def test_migration_211_e_idempotente():
    from migrations import _migration_211_configuracao_empresa_cronograma_mpp
    with app.app_context():
        _migration_211_configuracao_empresa_cronograma_mpp()
        _migration_211_configuracao_empresa_cronograma_mpp()


# ---------------------------------------------------------------------------
# Efeito na borda — a seção do M08 aparece/desaparece com a flag
# ---------------------------------------------------------------------------

def test_secao_do_m08_segue_a_flag_na_pagina_da_obra():
    with app.app_context():
        admin = _admin()
        suf = uuid.uuid4().hex[:8]
        cli = Cliente(admin_id=admin.id, nome=f'Cli {suf}',
                      email=f'cli_{suf}@test.local', telefone='119')
        db.session.add(cli)
        db.session.flush()
        obra = Obra(nome=f'Obra Flag {suf}', codigo=f'FL-{suf}',
                    admin_id=admin.id, cliente_id=cli.id,
                    status='Em andamento', data_inicio=date(2026, 7, 1))
        db.session.add(obra)
        db.session.commit()
        admin_id, obra_id = admin.id, obra.id

    def _html():
        c = app.test_client()
        with c.session_transaction() as sess:
            sess['_user_id'] = str(admin_id)
            sess['_fresh'] = True
        r = c.get(f'/obras/{obra_id}')
        assert r.status_code == 200
        return r.get_data(as_text=True)

    # Flag desligada (default da 211): página renderiza sem a seção.
    assert 'secaoCronogramaMpp' not in _html()

    with app.app_context():
        definir_flag(admin_id, True)
    assert 'secaoCronogramaMpp' in _html()
