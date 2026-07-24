"""Fase 5 — ciclo de vida do RDO.

Até esta fase o RDO nascia 'Finalizado' por decreto (`models.py:1112`,
comentário "Task #12: RDO sempre Finalizado") e era reescrito por oito
caminhos diferentes sem nenhuma guarda:

  views/rdo.py:698, 1540, 1630, 1755, 2614, 3967
  rdo_editar_sistema.py:221
  crud_rdo_completo.py:338, 572

A coluna `status` NÃO muda de significado — ≥9 consumidores filtram
`status == 'Finalizado'` (cronograma_views.py:2458,2488;
portal_obras_views.py:239; services/medicao_service.py:243;
services/rdo_custos.py:330; services/metricas_produtividade.py:186,972,
1302,1320,1397,1416). O ciclo de vida entra numa coluna NOVA, `estado`.
"""
import os
import sys
import uuid
from datetime import date

import pytest
from werkzeug.security import generate_password_hash

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import main  # noqa: F401 — registra os 54 blueprints antes de qualquer request
from app import app, db
from models import Cliente, Funcionario, Obra, RDO, TipoUsuario, Usuario

pytestmark = pytest.mark.integration


@pytest.fixture(autouse=True)
def _config():
    app.config['TESTING'] = True
    app.config['WTF_CSRF_ENABLED'] = False
    if not app.secret_key:
        app.secret_key = 'test-fase5-rdo'
    yield


def _sfx():
    return uuid.uuid4().hex[:8]


def _admin(nome='Admin F5'):
    suf = _sfx()
    u = Usuario(
        username=f'f5a_{suf}', email=f'f5a_{suf}@test.local',
        nome=f'{nome} {suf}',
        password_hash=generate_password_hash('Senha@2026'),
        tipo_usuario=TipoUsuario.ADMIN, ativo=True, versao_sistema='v2',
    )
    db.session.add(u)
    db.session.commit()
    return u


def _obra(admin_id, nome='Obra F5'):
    """Obra.cliente_id é NOT NULL — o Cliente vem junto, sempre."""
    suf = _sfx()
    cli = Cliente(nome=f'CLI-F5-{suf}', admin_id=admin_id)
    db.session.add(cli)
    db.session.flush()
    o = Obra(
        nome=f'{nome} {suf}', codigo=f'OF5{suf[:6].upper()}',
        data_inicio=date(2026, 1, 1), admin_id=admin_id,
        cliente_id=cli.id, valor_contrato=100000,
    )
    db.session.add(o)
    db.session.commit()
    return o


def _rdo(obra, admin_id, criado_por_id=None, data=None):
    suf = _sfx()
    r = RDO(
        numero_rdo=f'RDO-F5-{suf}',
        data_relatorio=data or date(2026, 6, 22),
        obra_id=obra.id, admin_id=admin_id,
        criado_por_id=criado_por_id,
        comentario_geral='Concretagem do radier.',
        clima_geral='Nublado',
    )
    db.session.add(r)
    db.session.commit()
    return r


def test_rdo_tem_coluna_estado():
    with app.app_context():
        assert hasattr(RDO, 'estado'), (
            'RDO.estado não existe — o RDO continua sem ciclo de vida')


def test_estado_default_e_rascunho():
    from services.rdo_ciclo_vida import RASCUNHO

    with app.app_context():
        admin = _admin()
        obra = _obra(admin.id)
        rdo = _rdo(obra, admin.id)
        assert rdo.estado == RASCUNHO, (
            f'RDO novo nasceu em {rdo.estado!r}, deveria nascer em rascunho')


def test_status_legado_continua_finalizado():
    """≥9 consumidores filtram status=='Finalizado'. Não pode mudar."""
    with app.app_context():
        admin = _admin()
        obra = _obra(admin.id)
        rdo = _rdo(obra, admin.id)
        assert rdo.status == 'Finalizado', (
            'o default de RDO.status mudou — isso some com o RDO do portal '
            '(portal_obras_views.py:239) e das métricas')


def test_backfill_marcou_os_rdos_historicos_como_preenchido():
    """Migration 260: histórico vira 'preenchido', NUNCA 'assinado'."""
    from sqlalchemy import text
    from services.rdo_ciclo_vida import ASSINADO

    with app.app_context():
        forjados = db.session.execute(text(
            "SELECT count(*) FROM rdo WHERE estado = :e"), {'e': ASSINADO}
        ).scalar()
        assert forjados == 0, (
            f'{forjados} RDO(s) históricos foram marcados como assinados pelo '
            f'backfill — isso é forjar autoria')
        orfaos = db.session.execute(text(
            "SELECT count(*) FROM rdo WHERE estado IS NULL")).scalar()
        assert orfaos == 0, f'{orfaos} RDO(s) ficaram sem estado após o backfill'
