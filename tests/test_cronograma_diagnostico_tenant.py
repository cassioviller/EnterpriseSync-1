"""Diagnóstico das flags que escondem cronograma de um tenant.

Motivação: `cronograma_views.py:39` faz TODO o módulo passar por
`_check_v2()`, que redireciona para o dashboard quando
`utils.tenant.is_v2_active()` é falso — e isso depende de
`Usuario.versao_sistema == 'v2'` do ADMIN do tenant (`utils/tenant.py:63`).
Além disso `configuracao_empresa.cronograma_mpp_ativo` nasce FALSE
(`models.py:3620`) e esconde a aba de importação. Antes deste script não
havia como responder "por que o cronograma sumiu para este cliente?" sem
abrir o banco na mão.
"""
import os
import sys
import uuid
from datetime import date

import pytest
from werkzeug.security import generate_password_hash

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import main  # noqa: F401 — registra os blueprints
from app import app, db
from models import Cliente, ConfiguracaoEmpresa, Obra, TipoUsuario, Usuario

pytestmark = pytest.mark.integration


@pytest.fixture(autouse=True)
def _config():
    app.config['TESTING'] = True
    app.config['WTF_CSRF_ENABLED'] = False
    if not app.secret_key:
        app.secret_key = 'test-diagnostico-cronograma'
    yield


def _admin(versao='v1'):
    suf = uuid.uuid4().hex[:8]
    u = Usuario(
        username=f'diag_{suf}', email=f'diag_{suf}@test.local',
        nome=f'Diag {suf}',
        password_hash=generate_password_hash('Senha@2026'),
        tipo_usuario=TipoUsuario.ADMIN, ativo=True, versao_sistema=versao,
    )
    db.session.add(u)
    db.session.commit()
    return u


def _obra(admin_id):
    suf = uuid.uuid4().hex[:8]
    cliente = Cliente(nome=f'Cliente Diag {suf}', admin_id=admin_id)
    db.session.add(cliente)
    db.session.commit()
    o = Obra(
        nome=f'Obra Diag {suf}', codigo=f'DG-{suf[:8].upper()}',
        data_inicio=date(2026, 1, 1), admin_id=admin_id,
        cliente_id=cliente.id,
    )
    db.session.add(o)
    db.session.commit()
    return o


def test_admin_inexistente_e_reportado_sem_explodir():
    from scripts.diagnostico_cronograma_tenant import diagnosticar

    with app.app_context():
        rel = diagnosticar(999_999_999)
        assert rel['admin_existe'] is False
        assert rel['bloqueios'], 'admin inexistente tem que gerar bloqueio'


def test_tenant_v1_e_apontado_como_bloqueio_total():
    from scripts.diagnostico_cronograma_tenant import diagnosticar

    with app.app_context():
        admin = _admin(versao='v1')
        rel = diagnosticar(admin.id)
        assert rel['versao_sistema'] == 'v1'
        assert rel['v2_ativo'] is False
        codigos = [b['codigo'] for b in rel['bloqueios']]
        assert 'versao_sistema_nao_v2' in codigos
        # É o bloqueio mais grave: esconde o módulo inteiro.
        assert rel['bloqueios'][0]['codigo'] == 'versao_sistema_nao_v2'


def test_tenant_v2_sem_flag_mpp_reporta_apenas_a_aba_de_importacao():
    from scripts.diagnostico_cronograma_tenant import diagnosticar

    with app.app_context():
        admin = _admin(versao='v2')
        rel = diagnosticar(admin.id)
        assert rel['v2_ativo'] is True
        codigos = [b['codigo'] for b in rel['bloqueios']]
        assert 'versao_sistema_nao_v2' not in codigos
        assert 'cronograma_mpp_desligado' in codigos


def test_tenant_v2_com_flag_ligada_nao_tem_bloqueio_de_flag():
    from scripts.diagnostico_cronograma_tenant import diagnosticar

    with app.app_context():
        admin = _admin(versao='v2')
        cfg = ConfiguracaoEmpresa(admin_id=admin.id,
                                  nome_empresa='Diag Ltda')
        cfg.cronograma_mpp_ativo = True
        db.session.add(cfg)
        db.session.commit()

        rel = diagnosticar(admin.id)
        codigos = [b['codigo'] for b in rel['bloqueios']]
        assert 'cronograma_mpp_desligado' not in codigos
        assert rel['cronograma_mpp_ativo'] is True


def test_obra_sem_tarefa_aparece_no_relatorio():
    from scripts.diagnostico_cronograma_tenant import diagnosticar

    with app.app_context():
        admin = _admin(versao='v2')
        obra = _obra(admin.id)
        rel = diagnosticar(admin.id)
        assert rel['obras_total'] >= 1
        assert rel['obras_sem_tarefa'] >= 1
        nomes = [o['nome'] for o in rel['amostra_obras_sem_tarefa']]
        assert obra.nome in nomes


def test_relatorio_conta_servicos_sem_template():
    """Sem template não há caminho automático proposta→obra."""
    from scripts.diagnostico_cronograma_tenant import diagnosticar

    with app.app_context():
        admin = _admin(versao='v2')
        rel = diagnosticar(admin.id)
        assert 'servicos_total' in rel
        assert 'servicos_com_template' in rel
        assert rel['servicos_com_template'] <= rel['servicos_total']
