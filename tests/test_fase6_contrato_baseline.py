"""Fase 6 / Task 1 — baseline versionado do contrato da obra.

Antes desta feature `Obra.valor_contrato` era um único Float mutável: um
aditivo reprecificava o contrato IN-PLACE, sem deixar rastro do valor
anterior nem da data em que a mudança passou a valer. A migration 271 cria
`obra_contrato_versao` (janela [vigente_de, vigente_ate), `vigente_ate
IS NULL` = versão vigente) e faz o backfill: toda obra pré-existente com
`valor_contrato > 0` ganha a versão nº1, `origem_tipo='backfill'`, sem
tocar em `obra.valor_contrato`.

`contrato_vigente()` (o serviço de leitura) é Task 2 — aqui a versão
vigente é lida diretamente do modelo (`vigente_ate IS NULL`).
"""
import os
import sys
import uuid
from datetime import date, datetime, timedelta
from decimal import Decimal

import pytest
from werkzeug.security import generate_password_hash

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import main  # noqa: F401 — registra blueprints e handlers de evento
from app import app, db
from models import Cliente, Obra, ObraContratoVersao, TipoUsuario, Usuario

pytestmark = pytest.mark.integration


@pytest.fixture(autouse=True)
def _config():
    app.config['TESTING'] = True
    app.config['WTF_CSRF_ENABLED'] = False
    if not app.secret_key:
        app.secret_key = 'test-fase6-contrato-baseline'
    yield


def _novo_admin(prefixo='f6cb'):
    suf = uuid.uuid4().hex[:8]
    admin = Usuario(
        username=f'{prefixo}_{suf}', email=f'{prefixo}_{suf}@test.local',
        nome=f'Admin {prefixo} {suf}',
        password_hash=generate_password_hash('Senha@2026'),
        tipo_usuario=TipoUsuario.ADMIN, ativo=True, versao_sistema='v2',
    )
    db.session.add(admin)
    db.session.flush()
    return admin


def _nova_obra(admin, valor_contrato=100000.0, com_created_at=True):
    suf = uuid.uuid4().hex[:8]
    cliente = Cliente(admin_id=admin.id, nome=f'Cliente {suf}',
                      email=f'cli_{suf}@test.local', telefone='11988887777')
    db.session.add(cliente)
    db.session.flush()
    obra = Obra(
        nome=f'Obra {suf}',
        codigo=f'OBR{suf}',
        data_inicio=date(2026, 1, 10),
        admin_id=admin.id,
        cliente_id=cliente.id,
        valor_contrato=valor_contrato,
    )
    if com_created_at:
        obra.created_at = datetime(2026, 1, 5, 12, 0, 0)
    db.session.add(obra)
    db.session.flush()
    return obra


@pytest.fixture
def ambiente():
    """Admin próprio + obra com contrato > 0, estado PRÉ-271 (sem versão)."""
    with app.app_context():
        admin = _novo_admin()
        obra = _nova_obra(admin)
        db.session.commit()
        yield {'admin_id': admin.id, 'obra_id': obra.id}


@pytest.mark.integration
def test_backfill_cria_exatamente_uma_versao_vigente(ambiente):
    from migrations import _migration_271_obra_contrato_versao
    with app.app_context():
        obra_id = ambiente['obra_id']
        assert ObraContratoVersao.query.filter_by(obra_id=obra_id).count() == 0, (
            'a fixture deveria ter deixado a obra sem versão (estado pré-271)')

        _migration_271_obra_contrato_versao()

        vigentes = ObraContratoVersao.query.filter_by(
            obra_id=obra_id, vigente_ate=None).all()
        assert len(vigentes) == 1, (
            f'esperava 1 versão vigente para a obra {obra_id}, achei '
            f'{len(vigentes)}')
        v = vigentes[0]
        assert v.versao == 1
        assert v.origem_tipo == 'backfill'


@pytest.mark.integration
def test_nunca_duas_versoes_vigentes_simultaneas(ambiente):
    """Rodar a migração duas vezes (idempotência) não cria uma 2ª vigente."""
    from migrations import _migration_271_obra_contrato_versao
    with app.app_context():
        obra_id = ambiente['obra_id']
        _migration_271_obra_contrato_versao()
        _migration_271_obra_contrato_versao()

        vigentes = ObraContratoVersao.query.filter_by(
            obra_id=obra_id, vigente_ate=None).count()
        assert vigentes == 1, (
            f'reexecução da migração duplicou versão vigente: {vigentes}')

        total = ObraContratoVersao.query.filter_by(obra_id=obra_id).count()
        assert total == 1, (
            f'reexecução da migração duplicou linhas: {total} no total')


@pytest.mark.integration
def test_versao_vigente_bate_com_valor_contrato_da_obra(ambiente):
    """contrato_vigente() é Task 2 — aqui a leitura é direta no modelo
    (vigente_ate IS NULL), que é a mesma consulta que o serviço vai fazer."""
    from migrations import _migration_271_obra_contrato_versao
    with app.app_context():
        obra_id = ambiente['obra_id']
        _migration_271_obra_contrato_versao()

        obra = db.session.get(Obra, obra_id)
        vigente = ObraContratoVersao.query.filter_by(
            obra_id=obra_id, vigente_ate=None).one()
        assert vigente.valor == Decimal(str(obra.valor_contrato))


@pytest.mark.integration
def test_invariante_de_tenant_admin_id_bate_com_a_obra(ambiente):
    """100% das linhas de obra_contrato_versao têm admin_id == Obra.admin_id."""
    from migrations import _migration_271_obra_contrato_versao
    with app.app_context():
        admin_id = ambiente['admin_id']
        obra_id = ambiente['obra_id']

        # Segundo admin/obra no mesmo backfill global, pra provar que a
        # invariante vale por linha e não só "por coincidência" quando há
        # um único tenant no banco.
        admin2 = _novo_admin('f6cb_outro')
        obra2 = _nova_obra(admin2, valor_contrato=50000.0)
        db.session.commit()

        _migration_271_obra_contrato_versao()

        for v in ObraContratoVersao.query.filter(
                ObraContratoVersao.obra_id.in_([obra_id, obra2.id])).all():
            obra = db.session.get(Obra, v.obra_id)
            assert v.admin_id == obra.admin_id, (
                f'versão {v.id} da obra {v.obra_id} tem admin_id={v.admin_id}, '
                f'mas a obra é do admin {obra.admin_id}')

        v1 = ObraContratoVersao.query.filter_by(obra_id=obra_id).one()
        assert v1.admin_id == admin_id
        v2 = ObraContratoVersao.query.filter_by(obra_id=obra2.id).one()
        assert v2.admin_id == admin2.id


@pytest.mark.integration
def test_backfill_usa_created_at_como_vigente_de(ambiente):
    """vigente_de = obra.created_at (fallback data_inicio, fallback now())."""
    from migrations import _migration_271_obra_contrato_versao
    with app.app_context():
        obra_id = ambiente['obra_id']
        obra = db.session.get(Obra, obra_id)
        esperado = obra.created_at

        _migration_271_obra_contrato_versao()

        v = ObraContratoVersao.query.filter_by(obra_id=obra_id).one()
        assert v.vigente_de == esperado
        assert v.vigente_ate is None


@pytest.mark.integration
def test_backfill_nao_altera_valor_contrato_da_obra(ambiente):
    """O backfill lê obra.valor_contrato mas não escreve nele."""
    from migrations import _migration_271_obra_contrato_versao
    with app.app_context():
        obra_id = ambiente['obra_id']
        antes = db.session.get(Obra, obra_id).valor_contrato

        _migration_271_obra_contrato_versao()
        db.session.expire_all()

        depois = db.session.get(Obra, obra_id).valor_contrato
        assert antes == depois == 100000.0


@pytest.mark.integration
def test_obra_sem_valor_contrato_nao_ganha_versao(ambiente):
    """valor_contrato <= 0 (ou NULL) não entra no backfill."""
    from migrations import _migration_271_obra_contrato_versao
    with app.app_context():
        admin = _novo_admin('f6cb_zero')
        obra_zero = _nova_obra(admin, valor_contrato=0.0)
        db.session.commit()

        _migration_271_obra_contrato_versao()

        assert ObraContratoVersao.query.filter_by(obra_id=obra_zero.id).count() == 0
