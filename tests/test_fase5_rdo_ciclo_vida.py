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


# ---------------------------------------------------------------------------
# Trilha de transições
# ---------------------------------------------------------------------------

def test_modelo_de_transicao_existe_e_persiste():
    from models import RDOTransicaoEstado

    with app.app_context():
        admin = _admin()
        obra = _obra(admin.id)
        rdo = _rdo(obra, admin.id)
        t = RDOTransicaoEstado(
            rdo_id=rdo.id, admin_id=admin.id,
            estado_anterior='rascunho', estado_novo='preenchido',
            usuario_id=admin.id, motivo='submissão do dia',
            ip='203.0.113.7', detalhes={'origem': 'teste'},
        )
        db.session.add(t)
        db.session.commit()
        tid = t.id

    with app.app_context():
        recarregado = db.session.get(RDOTransicaoEstado, tid)
        assert recarregado.estado_anterior == 'rascunho'
        assert recarregado.estado_novo == 'preenchido'
        assert recarregado.detalhes == {'origem': 'teste'}
        assert recarregado.criado_em is not None


def test_transicao_e_apagada_junto_com_o_rdo():
    """ON DELETE CASCADE: excluir RDO não pode deixar trilha órfã."""
    from models import RDOTransicaoEstado

    with app.app_context():
        admin = _admin()
        obra = _obra(admin.id)
        rdo = _rdo(obra, admin.id)
        db.session.add(RDOTransicaoEstado(
            rdo_id=rdo.id, admin_id=admin.id,
            estado_anterior='rascunho', estado_novo='preenchido',
            usuario_id=admin.id,
        ))
        db.session.commit()
        rid = rdo.id
        db.session.delete(rdo)
        db.session.commit()
        assert RDOTransicaoEstado.query.filter_by(rdo_id=rid).count() == 0


# ---------------------------------------------------------------------------
# Máquina de estados
# ---------------------------------------------------------------------------

def test_conjunto_de_estados_e_fechado():
    from services.rdo_ciclo_vida import ESTADOS

    assert ESTADOS == {'rascunho', 'preenchido', 'assinado',
                       'aprovado', 'retificado'}


def test_transicoes_validas_sao_as_esperadas():
    from services.rdo_ciclo_vida import TRANSICOES_VALIDAS

    assert TRANSICOES_VALIDAS['rascunho'] == {'preenchido'}
    assert TRANSICOES_VALIDAS['preenchido'] == {'rascunho', 'assinado'}
    assert TRANSICOES_VALIDAS['assinado'] == {'aprovado', 'retificado'}
    assert TRANSICOES_VALIDAS['aprovado'] == {'retificado'}
    assert TRANSICOES_VALIDAS['retificado'] == set()


def test_transicionar_grava_estado_e_trilha():
    from models import RDOTransicaoEstado
    from services.rdo_ciclo_vida import PREENCHIDO, transicionar

    with app.app_context():
        admin = _admin()
        obra = _obra(admin.id)
        rdo = _rdo(obra, admin.id)

        transicionar(rdo, PREENCHIDO, usuario=admin, motivo='fim do dia',
                     ip='203.0.113.7')
        db.session.commit()
        rid = rdo.id

    with app.app_context():
        recarregado = db.session.get(RDO, rid)
        assert recarregado.estado == PREENCHIDO
        trilha = RDOTransicaoEstado.query.filter_by(rdo_id=rid).all()
        assert len(trilha) == 1
        assert trilha[0].estado_anterior == 'rascunho'
        assert trilha[0].estado_novo == PREENCHIDO
        assert trilha[0].motivo == 'fim do dia'
        assert trilha[0].ip == '203.0.113.7'


def test_transicao_invalida_e_recusada():
    from services.rdo_ciclo_vida import APROVADO, TransicaoInvalida, transicionar

    with app.app_context():
        admin = _admin()
        obra = _obra(admin.id)
        rdo = _rdo(obra, admin.id)  # rascunho

        with pytest.raises(TransicaoInvalida):
            transicionar(rdo, APROVADO, usuario=admin)
        db.session.rollback()
        assert db.session.get(RDO, rdo.id).estado == 'rascunho'


def test_estado_desconhecido_e_recusado():
    from services.rdo_ciclo_vida import TransicaoInvalida, transicionar

    with app.app_context():
        admin = _admin()
        obra = _obra(admin.id)
        rdo = _rdo(obra, admin.id)
        with pytest.raises(TransicaoInvalida):
            transicionar(rdo, 'homologado', usuario=admin)
        db.session.rollback()


def test_transicao_para_o_mesmo_estado_e_no_op_sem_trilha():
    """Reenviar o mesmo estado não pode poluir a trilha."""
    from models import RDOTransicaoEstado
    from services.rdo_ciclo_vida import RASCUNHO, transicionar

    with app.app_context():
        admin = _admin()
        obra = _obra(admin.id)
        rdo = _rdo(obra, admin.id)
        transicionar(rdo, RASCUNHO, usuario=admin)
        db.session.commit()
        assert RDOTransicaoEstado.query.filter_by(rdo_id=rdo.id).count() == 0


def test_estados_imutaveis_sao_os_tres_finais():
    from services.rdo_ciclo_vida import ESTADOS_IMUTAVEIS

    assert ESTADOS_IMUTAVEIS == {'assinado', 'aprovado', 'retificado'}


def test_garantir_editavel_passa_em_rascunho_e_preenchido():
    from services.rdo_ciclo_vida import (PREENCHIDO, garantir_editavel,
                                         transicionar)

    with app.app_context():
        admin = _admin()
        obra = _obra(admin.id)
        rdo = _rdo(obra, admin.id)
        garantir_editavel(rdo)          # rascunho: passa
        transicionar(rdo, PREENCHIDO, usuario=admin)
        db.session.commit()
        garantir_editavel(rdo)          # preenchido: passa


def test_garantir_editavel_recusa_assinado():
    from services.rdo_ciclo_vida import (ASSINADO, PREENCHIDO, RDOImutavel,
                                         garantir_editavel, transicionar)

    with app.app_context():
        admin = _admin()
        obra = _obra(admin.id)
        rdo = _rdo(obra, admin.id)
        transicionar(rdo, PREENCHIDO, usuario=admin)
        transicionar(rdo, ASSINADO, usuario=admin)
        db.session.commit()
        with pytest.raises(RDOImutavel):
            garantir_editavel(rdo)
