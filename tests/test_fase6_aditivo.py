"""Fase 6 / Task 3 — `AditivoContrato` + transições de estado.

O aditivo formaliza o que a Fase 6 quer eliminar: reprecificação IN-PLACE de
`Obra.valor_contrato` sem motivo, sem valor anterior e sem data. Aqui cada
aditivo nasce em `rascunho`, congela `valor_anterior` na abertura, e só na
APROVAÇÃO toca o baseline — abrindo uma `ObraContratoVersao` nova (via
`abrir_versao`, o escritor único da Task 2) com `origem_tipo='aditivo'` e
`aditivo_id` preenchido. Cancelar um rascunho não toca no baseline.

D2 do plano: o divisor do que é aditivo é a EXISTÊNCIA de contrato vigente,
não o valor — aditivo de delta zero (prazo puro) é aditivo, e a aprovação
dele abre versão nova mesmo com o mesmo valor.

Migration 272 (não 271 — a 271 foi consumida pela Task 1): cria
`aditivo_contrato` e adiciona a FK pendente `obra_contrato_versao.aditivo_id
-> aditivo_contrato.id ON DELETE SET NULL` que a Task 1 deixou como Integer
plano de propósito.
"""
import os
import sys
import uuid
from datetime import date, datetime
from decimal import Decimal

import pytest
from werkzeug.security import generate_password_hash

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import main  # noqa: F401 — registra blueprints e handlers de evento
from app import app, db
from models import AditivoContrato, Cliente, Obra, ObraContratoVersao, TipoUsuario, Usuario

pytestmark = pytest.mark.integration


@pytest.fixture(autouse=True)
def _config():
    app.config['TESTING'] = True
    app.config['WTF_CSRF_ENABLED'] = False
    if not app.secret_key:
        app.secret_key = 'test-fase6-aditivo'
    yield


@pytest.fixture(autouse=True, scope='module')
def _schema():
    """Garante `aditivo_contrato` + a FK da 272 no banco de teste.

    O boot da suíte roda com SIGE_BOOT_DDL=0 (conftest) — nem create_all nem
    migrações. A 272 é idempotente, então rodá-la aqui é seguro mesmo que a
    tabela já exista de uma execução anterior."""
    from migrations import (_migration_271_obra_contrato_versao,
                            _migration_272_aditivo_contrato)
    with app.app_context():
        _migration_271_obra_contrato_versao()
        _migration_272_aditivo_contrato()
    yield


def _novo_admin(prefixo='f6ad'):
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


def _nova_obra(admin, valor_contrato=0.0):
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
    db.session.add(obra)
    db.session.flush()
    return obra


@pytest.fixture
def ambiente():
    """Admin + obra com contrato vigente de R$ 100.000 (versão nº1 aberta
    pelo escritor único da Task 2 — não por INSERT manual)."""
    from services.contrato_obra import ORIGEM_CADASTRO, definir_valor_contrato
    with app.app_context():
        admin = _novo_admin()
        obra = _nova_obra(admin, valor_contrato=0.0)
        definir_valor_contrato(obra, 100000.0, origem=ORIGEM_CADASTRO,
                               motivo='contrato original')
        db.session.commit()
        yield {'admin_id': admin.id, 'obra_id': obra.id}


# ---------------------------------------------------------------------------
# abrir_aditivo
# ---------------------------------------------------------------------------

@pytest.mark.integration
def test_abrir_aditivo_sem_contrato_vigente_levanta_erro():
    """D2: aditivo pressupõe contrato vigente. Obra sem nenhuma versão
    (valor_contrato zero, estado pré-baseline) não pode abrir aditivo."""
    from services.contrato_obra import abrir_aditivo
    with app.app_context():
        admin = _novo_admin('f6ad_semctr')
        obra = _nova_obra(admin, valor_contrato=0.0)
        db.session.commit()
        assert ObraContratoVersao.query.filter_by(obra_id=obra.id).count() == 0

        with pytest.raises(ValueError, match='contrato vigente'):
            abrir_aditivo(obra, tipo='acrescimo', motivo='sem base',
                          valor_novo=50000.0)


@pytest.mark.integration
def test_abrir_aditivo_congela_valor_anterior_e_numera_ad_001(ambiente):
    from services.contrato_obra import abrir_aditivo
    with app.app_context():
        obra = db.session.get(Obra, ambiente['obra_id'])

        aditivo = abrir_aditivo(obra, tipo='acrescimo',
                                motivo='serviços extras de fundação',
                                valor_novo=130000.0, criado_por_id=ambiente['admin_id'])
        db.session.commit()

        assert aditivo.numero == 'AD-001'
        assert aditivo.status == 'rascunho'
        assert aditivo.tipo == 'acrescimo'
        assert aditivo.admin_id == obra.admin_id
        assert aditivo.valor_anterior == Decimal('100000.00'), (
            'valor_anterior congela o vigente na abertura')
        assert aditivo.valor_novo == Decimal('130000.00')
        assert aditivo.valor_delta == Decimal('30000.00')
        assert aditivo.criado_em is not None
        assert aditivo.aprovado_em is None

        # abrir_aditivo NÃO toca no baseline — só a aprovação toca.
        assert ObraContratoVersao.query.filter_by(obra_id=obra.id).count() == 1
        obra = db.session.get(Obra, obra.id)
        assert float(obra.valor_contrato) == 100000.0


@pytest.mark.integration
def test_abrir_aditivo_sem_motivo_levanta_erro(ambiente):
    """Aditivo sem motivo é exatamente o que a Fase 6 quer eliminar."""
    from services.contrato_obra import abrir_aditivo
    with app.app_context():
        obra = db.session.get(Obra, ambiente['obra_id'])
        with pytest.raises(ValueError, match='motivo'):
            abrir_aditivo(obra, tipo='acrescimo', motivo='   ',
                          valor_novo=130000.0)


@pytest.mark.integration
def test_so_um_aditivo_em_rascunho_por_obra(ambiente):
    from services.contrato_obra import abrir_aditivo
    with app.app_context():
        obra = db.session.get(Obra, ambiente['obra_id'])
        abrir_aditivo(obra, tipo='acrescimo', motivo='primeiro',
                      valor_novo=110000.0)
        db.session.commit()

        obra = db.session.get(Obra, obra.id)
        with pytest.raises(ValueError, match='rascunho'):
            abrir_aditivo(obra, tipo='supressao', motivo='segundo em paralelo',
                          valor_novo=90000.0)


@pytest.mark.integration
def test_numeracao_sequencial_por_obra_e_por_tenant(ambiente):
    """AD-002 vem depois do AD-001 (mesmo cancelado — número não recicla);
    outra obra começa do AD-001 de novo."""
    from services.contrato_obra import abrir_aditivo, cancelar_aditivo
    with app.app_context():
        obra = db.session.get(Obra, ambiente['obra_id'])
        a1 = abrir_aditivo(obra, tipo='acrescimo', motivo='primeiro',
                           valor_novo=110000.0)
        db.session.commit()
        cancelar_aditivo(a1)
        db.session.commit()

        obra = db.session.get(Obra, obra.id)
        a2 = abrir_aditivo(obra, tipo='acrescimo', motivo='segundo',
                           valor_novo=120000.0)
        db.session.commit()
        assert a2.numero == 'AD-002'

        # Obra irmã (mesmo tenant) numera do zero.
        from services.contrato_obra import ORIGEM_CADASTRO, definir_valor_contrato
        admin_id = ambiente['admin_id']
        admin = db.session.get(Usuario, admin_id)
        obra2 = _nova_obra(admin, valor_contrato=0.0)
        definir_valor_contrato(obra2, 50000.0, origem=ORIGEM_CADASTRO)
        db.session.commit()
        b1 = abrir_aditivo(obra2, tipo='prazo', motivo='chuvas',
                           prazo_delta_dias=30)
        db.session.commit()
        assert b1.numero == 'AD-001'


# ---------------------------------------------------------------------------
# aprovar_aditivo
# ---------------------------------------------------------------------------

@pytest.mark.integration
def test_aprovar_aditivo_cria_versao_2_e_fecha_a_1(ambiente):
    from services.contrato_obra import abrir_aditivo, aprovar_aditivo
    with app.app_context():
        obra = db.session.get(Obra, ambiente['obra_id'])
        aditivo = abrir_aditivo(obra, tipo='acrescimo', motivo='mais escopo',
                                valor_novo=130000.0)
        db.session.commit()

        versao = aprovar_aditivo(aditivo, aprovado_por_id=ambiente['admin_id'])
        db.session.commit()

        db.session.expire_all()
        aditivo = db.session.get(AditivoContrato, aditivo.id)
        assert aditivo.status == 'aprovado'
        assert aditivo.aprovado_em is not None
        assert aditivo.aprovado_por_id == ambiente['admin_id']

        v1 = ObraContratoVersao.query.filter_by(obra_id=obra.id, versao=1).one()
        assert v1.vigente_ate is not None, 'a versão 1 deveria ter sido fechada'

        v2 = ObraContratoVersao.query.filter_by(
            obra_id=obra.id, vigente_ate=None).one()
        assert v2.versao == 2
        assert v2.id == versao.id
        assert v2.valor == Decimal('130000.00')
        assert v2.origem_tipo == 'aditivo'
        assert v2.aditivo_id == aditivo.id
        assert v2.motivo == 'mais escopo'

        obra = db.session.get(Obra, obra.id)
        assert float(obra.valor_contrato) == 130000.0


@pytest.mark.integration
def test_aprovar_aditivo_ja_aprovado_e_noop_idempotente(ambiente):
    from services.contrato_obra import abrir_aditivo, aprovar_aditivo
    with app.app_context():
        obra = db.session.get(Obra, ambiente['obra_id'])
        aditivo = abrir_aditivo(obra, tipo='acrescimo', motivo='mais escopo',
                                valor_novo=130000.0)
        db.session.commit()

        v_primeira = aprovar_aditivo(aditivo, aprovado_por_id=ambiente['admin_id'])
        db.session.commit()
        aprovado_em_original = aditivo.aprovado_em

        v_segunda = aprovar_aditivo(aditivo, aprovado_por_id=ambiente['admin_id'])
        db.session.commit()

        assert v_segunda is not None and v_segunda.id == v_primeira.id, (
            're-aprovação devolve a MESMA versão, não abre outra')
        assert aditivo.aprovado_em == aprovado_em_original, (
            're-aprovação não recarimba aprovado_em')
        assert ObraContratoVersao.query.filter_by(obra_id=obra.id).count() == 2, (
            're-aprovação não pode abrir uma 3ª versão')
        vigente = ObraContratoVersao.query.filter_by(
            obra_id=obra.id, vigente_ate=None).one()
        assert vigente.versao == 2


@pytest.mark.integration
def test_reaprovar_na_mesma_transacao_sem_flush_nao_casa_com_versao_alheia(ambiente):
    """Regressão do auto-review: re-aprovar um aditivo ainda NÃO flushado
    (id None) fazia a busca idempotente virar `aditivo_id IS NULL` — e casar
    com qualquer versão sem aditivo (a nº1, por exemplo). A re-aprovação tem
    de devolver a versão DESTE aditivo, mesmo tudo na mesma transação."""
    from services.contrato_obra import abrir_aditivo, aprovar_aditivo
    with app.app_context():
        obra = db.session.get(Obra, ambiente['obra_id'])
        aditivo = abrir_aditivo(obra, tipo='acrescimo', motivo='mesma transação',
                                valor_novo=130000.0)
        v_primeira = aprovar_aditivo(aditivo)
        assert aditivo.id is None, (
            'o cenário exige o aditivo ainda sem id (nada flushado)')
        v_segunda = aprovar_aditivo(aditivo)
        db.session.commit()

        assert v_segunda is v_primeira, (
            're-aprovação na mesma transação devolveu outra versão — '
            f'{v_segunda!r} em vez de {v_primeira!r}')
        assert v_segunda.versao == 2
        assert v_segunda.aditivo_id == aditivo.id
        assert ObraContratoVersao.query.filter_by(obra_id=obra.id).count() == 2


@pytest.mark.integration
def test_aprovar_aditivo_cancelado_levanta_erro(ambiente):
    from services.contrato_obra import abrir_aditivo, aprovar_aditivo, cancelar_aditivo
    with app.app_context():
        obra = db.session.get(Obra, ambiente['obra_id'])
        aditivo = abrir_aditivo(obra, tipo='acrescimo', motivo='desistido',
                                valor_novo=130000.0)
        db.session.commit()
        cancelar_aditivo(aditivo)
        db.session.commit()

        with pytest.raises(ValueError, match='cancelado'):
            aprovar_aditivo(aditivo)


@pytest.mark.integration
def test_aditivo_de_prazo_puro_delta_zero_ainda_abre_versao_nova(ambiente):
    """D2/ruling: delta zero NÃO é no-op. Um aditivo de prazo puro mantém o
    valor mas a aprovação abre versão nova mesmo assim — a régua registra que
    houve um aditivo ali (e a Task 4 vai pendurar o repontamento nele)."""
    from services.contrato_obra import abrir_aditivo, aprovar_aditivo
    with app.app_context():
        obra = db.session.get(Obra, ambiente['obra_id'])
        aditivo = abrir_aditivo(obra, tipo='prazo', motivo='chuvas de janeiro',
                                prazo_delta_dias=45)
        db.session.commit()

        assert aditivo.valor_novo == aditivo.valor_anterior == Decimal('100000.00')
        assert aditivo.valor_delta == Decimal('0.00')
        assert aditivo.prazo_delta_dias == 45

        aprovar_aditivo(aditivo)
        db.session.commit()

        vigente = ObraContratoVersao.query.filter_by(
            obra_id=obra.id, vigente_ate=None).one()
        assert vigente.versao == 2, (
            'delta zero é aditivo: a aprovação abre a versão nº2 mesmo com '
            'o mesmo valor')
        assert vigente.valor == Decimal('100000.00')
        assert vigente.aditivo_id == aditivo.id


# ---------------------------------------------------------------------------
# cancelar_aditivo
# ---------------------------------------------------------------------------

@pytest.mark.integration
def test_cancelar_aditivo_em_rascunho_nao_toca_no_baseline(ambiente):
    from services.contrato_obra import abrir_aditivo, cancelar_aditivo
    with app.app_context():
        obra = db.session.get(Obra, ambiente['obra_id'])
        aditivo = abrir_aditivo(obra, tipo='supressao', motivo='corte de escopo',
                                valor_novo=80000.0)
        db.session.commit()

        cancelar_aditivo(aditivo)
        db.session.commit()

        db.session.expire_all()
        aditivo = db.session.get(AditivoContrato, aditivo.id)
        assert aditivo.status == 'cancelado'

        # Baseline intocado: 1 versão só, ainda vigente, valor original.
        versoes = ObraContratoVersao.query.filter_by(obra_id=obra.id).all()
        assert len(versoes) == 1
        assert versoes[0].versao == 1
        assert versoes[0].vigente_ate is None
        obra = db.session.get(Obra, obra.id)
        assert float(obra.valor_contrato) == 100000.0


@pytest.mark.integration
def test_cancelar_aditivo_aprovado_levanta_erro(ambiente):
    """Aprovado é terminal: desfazer exige um aditivo novo em sentido
    contrário, nunca cancelar o que já mexeu no baseline."""
    from services.contrato_obra import abrir_aditivo, aprovar_aditivo, cancelar_aditivo
    with app.app_context():
        obra = db.session.get(Obra, ambiente['obra_id'])
        aditivo = abrir_aditivo(obra, tipo='acrescimo', motivo='mais escopo',
                                valor_novo=130000.0)
        db.session.commit()
        aprovar_aditivo(aditivo)
        db.session.commit()

        with pytest.raises(ValueError, match='aprovado'):
            cancelar_aditivo(aditivo)


# ---------------------------------------------------------------------------
# Migration 272
# ---------------------------------------------------------------------------

@pytest.mark.integration
def test_migration_272_e_idempotente_e_reexecutavel():
    from migrations import _migration_272_aditivo_contrato
    with app.app_context():
        _migration_272_aditivo_contrato()
        _migration_272_aditivo_contrato()  # não pode falhar nem duplicar nada

        from sqlalchemy import text as _text
        fks = db.session.execute(_text("""
            SELECT count(*)
            FROM pg_constraint c
            WHERE c.conrelid = 'obra_contrato_versao'::regclass
              AND c.contype = 'f'
              AND c.conkey = ARRAY[(
                  SELECT attnum FROM pg_attribute
                  WHERE attrelid = 'obra_contrato_versao'::regclass
                    AND attname = 'aditivo_id')]::smallint[]
        """)).scalar()
        assert fks == 1, (
            f'esperava exatamente 1 FK em obra_contrato_versao.aditivo_id, '
            f'achei {fks} — reexecução não pode duplicar a constraint')


@pytest.mark.integration
def test_fk_aditivo_id_e_on_delete_set_null(ambiente):
    """Apagar o aditivo não apaga a versão do baseline — a régua sobrevive
    (aditivo_id vira NULL, o resto da versão fica)."""
    from services.contrato_obra import abrir_aditivo, aprovar_aditivo
    with app.app_context():
        obra = db.session.get(Obra, ambiente['obra_id'])
        aditivo = abrir_aditivo(obra, tipo='acrescimo', motivo='mais escopo',
                                valor_novo=130000.0)
        db.session.commit()
        versao = aprovar_aditivo(aditivo)
        db.session.commit()
        versao_id = versao.id

        db.session.delete(aditivo)
        db.session.commit()

        db.session.expire_all()
        v = db.session.get(ObraContratoVersao, versao_id)
        assert v is not None, 'a versão do baseline não pode sumir com o aditivo'
        assert v.aditivo_id is None
        assert v.valor == Decimal('130000.00')
