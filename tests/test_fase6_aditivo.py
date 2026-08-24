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
from datetime import date
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
                            _migration_272_aditivo_contrato,
                            _migration_273_medicao_contrato_versionada)
    with app.app_context():
        _migration_271_obra_contrato_versao()
        _migration_272_aditivo_contrato()
        _migration_273_medicao_contrato_versionada()
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


# ---------------------------------------------------------------------------
# Fix round 1 — prazo_dias da versão: propagação do aditivo de prazo
# (ruling do controlador: ObraContratoVersao.prazo_dias não tinha dono; a
# Task 3 assume porque aprovar_aditivo é o único ponto que conhece o delta
# e a versão sendo aberta ao mesmo tempo).
# ---------------------------------------------------------------------------

@pytest.mark.integration
def test_aditivo_de_prazo_deriva_base_das_datas_da_obra_quando_versao_sem_prazo(ambiente):
    """Versão vigente com prazo_dias NULL (caso de todo o parque: backfill da
    271) e obra COM data_previsao_fim: a base vem de
    (data_previsao_fim - data_inicio).days, e a versão nova carrega
    base + delta."""
    from services.contrato_obra import abrir_aditivo, aprovar_aditivo
    with app.app_context():
        obra = db.session.get(Obra, ambiente['obra_id'])
        obra.data_previsao_fim = date(2026, 7, 10)  # data_inicio: 2026-01-10
        db.session.commit()
        base = (obra.data_previsao_fim - obra.data_inicio).days
        assert base == 181

        vigente = ObraContratoVersao.query.filter_by(
            obra_id=obra.id, vigente_ate=None).one()
        assert vigente.prazo_dias is None, 'o cenário exige base NULL na versão'

        aditivo = abrir_aditivo(obra, tipo='prazo', motivo='chuvas',
                                prazo_delta_dias=45)
        db.session.commit()
        aprovar_aditivo(aditivo)
        db.session.commit()

        v2 = ObraContratoVersao.query.filter_by(
            obra_id=obra.id, vigente_ate=None).one()
        assert v2.versao == 2
        assert v2.prazo_dias == base + 45, (
            f'esperava prazo derivado {base}+45={base + 45}, veio {v2.prazo_dias}')


@pytest.mark.integration
def test_aditivo_de_prazo_sem_base_conhecida_mantem_prazo_none(ambiente):
    """Versão sem prazo_dias E obra sem data_previsao_fim: base desconhecida
    + delta é desconhecida — a versão nova fica NULL (nunca inventar zero);
    o delta continua auditável no próprio AditivoContrato."""
    from services.contrato_obra import abrir_aditivo, aprovar_aditivo
    with app.app_context():
        obra = db.session.get(Obra, ambiente['obra_id'])
        assert obra.data_previsao_fim is None

        aditivo = abrir_aditivo(obra, tipo='prazo', motivo='chuvas',
                                prazo_delta_dias=45)
        db.session.commit()
        aprovar_aditivo(aditivo)
        db.session.commit()

        v2 = ObraContratoVersao.query.filter_by(
            obra_id=obra.id, vigente_ate=None).one()
        assert v2.versao == 2
        assert v2.prazo_dias is None
        assert aditivo.prazo_delta_dias == 45, 'o delta fica auditável no aditivo'


@pytest.mark.integration
def test_versao_aberta_por_outro_caminho_herda_prazo_dias(ambiente):
    """Sem herança, o prazo evaporaria na primeira versão aberta por outro
    caminho (reprecificação, proposta): definir_valor_contrato depois do
    aditivo de prazo mantém o prazo_dias da versão que está fechando."""
    from services.contrato_obra import (ORIGEM_EDICAO, abrir_aditivo,
                                        aprovar_aditivo,
                                        definir_valor_contrato)
    with app.app_context():
        obra = db.session.get(Obra, ambiente['obra_id'])
        obra.data_previsao_fim = date(2026, 7, 10)
        db.session.commit()

        aditivo = abrir_aditivo(obra, tipo='prazo', motivo='chuvas',
                                prazo_delta_dias=45)
        db.session.commit()
        aprovar_aditivo(aditivo)
        db.session.commit()
        v2 = ObraContratoVersao.query.filter_by(
            obra_id=obra.id, vigente_ate=None).one()
        assert v2.prazo_dias == 181 + 45

        obra = db.session.get(Obra, obra.id)
        definir_valor_contrato(obra, 175000.0, origem=ORIGEM_EDICAO,
                               motivo='reprecificação pós-aditivo')
        db.session.commit()

        v3 = ObraContratoVersao.query.filter_by(
            obra_id=obra.id, vigente_ate=None).one()
        assert v3.versao == 3
        assert v3.prazo_dias == 181 + 45, (
            'a versão aberta por outro caminho tem de HERDAR o prazo, '
            f'não zerá-lo — veio {v3.prazo_dias}')


@pytest.mark.integration
def test_supressao_de_prazo_que_deixa_prazo_negativo_levanta_erro(ambiente):
    """Delta negativo funciona pela mesma conta, mas um prazo RESULTANTE
    negativo é contrato impossível — a aprovação recusa e o aditivo continua
    em rascunho (nada foi mutado antes do erro)."""
    from services.contrato_obra import abrir_aditivo, aprovar_aditivo
    with app.app_context():
        obra = db.session.get(Obra, ambiente['obra_id'])
        obra.data_previsao_fim = date(2026, 7, 10)  # base 181
        db.session.commit()

        aditivo = abrir_aditivo(obra, tipo='prazo', motivo='corte impossível',
                                prazo_delta_dias=-200)
        db.session.commit()

        with pytest.raises(ValueError, match='negativo'):
            aprovar_aditivo(aditivo)

        assert aditivo.status == 'rascunho', (
            'a recusa não pode deixar o aditivo meio-aprovado')
        assert ObraContratoVersao.query.filter_by(obra_id=obra.id).count() == 1


# ---------------------------------------------------------------------------
# Fase 6 / Task 4 — MedicaoContrato presa à versão do baseline.
#
# A coluna `contrato_versao_id` é RASTREABILIDADE (nullable, fora da
# property `valor` — quem congela valor de marco recebido continua sendo
# `valor_base`, Fase 0.6/D1c). O entregável de negócio: `aprovar_aditivo`
# passa a fazer o MESMO congelamento que o caminho da proposta
# (event_manager) já fazia — sem ele, a porta nova reprecificava
# retroativamente até o que o cliente já pagou — e reponta os marcos ainda
# não recebidos para a versão nova.
# ---------------------------------------------------------------------------

def _novo_marco(obra, nome, pct, recebido_no_mes=None, contrato_versao_id=None):
    from models import MedicaoContrato
    marco = MedicaoContrato(
        obra_id=obra.id, admin_id=obra.admin_id, nome=nome,
        pct=Decimal(str(pct)), recebido_no_mes=recebido_no_mes,
        contrato_versao_id=contrato_versao_id)
    db.session.add(marco)
    db.session.flush()
    return marco


@pytest.mark.integration
def test_aprovar_aditivo_congela_recebido_e_reponta_nao_recebido(ambiente):
    """Cenário do Step 1 do brief: obra de 100k com 2 marcos de 50%; aditivo
    para 120k. O marco JÁ RECEBIDO continua valendo 50.000 (valor_base
    congelado na base anterior; contrato_versao_id parado na versão em que
    nasceu). O marco NÃO recebido passa a valer 60.000 e é repontado para a
    versão nova."""
    from models import MedicaoContrato
    from services.contrato_obra import abrir_aditivo, aprovar_aditivo
    with app.app_context():
        obra = db.session.get(Obra, ambiente['obra_id'])
        v1 = ObraContratoVersao.query.filter_by(
            obra_id=obra.id, vigente_ate=None).one()
        recebido = _novo_marco(obra, 'Marco 1 (pago)', '0.5',
                               recebido_no_mes='2026-02',
                               contrato_versao_id=v1.id)
        futuro = _novo_marco(obra, 'Marco 2 (futuro)', '0.5',
                             contrato_versao_id=v1.id)
        db.session.commit()
        v1_id, recebido_id, futuro_id = v1.id, recebido.id, futuro.id
        assert float(recebido.valor) == 50000.0
        assert float(futuro.valor) == 50000.0

        aditivo = abrir_aditivo(obra, tipo='acrescimo',
                                motivo='acréscimo de escopo',
                                valor_novo=120000.0)
        db.session.commit()
        v2 = aprovar_aditivo(aditivo, aprovado_por_id=ambiente['admin_id'])
        db.session.commit()
        v2_id = v2.id

        db.session.expire_all()
        recebido = db.session.get(MedicaoContrato, recebido_id)
        futuro = db.session.get(MedicaoContrato, futuro_id)

        assert float(recebido.valor) == 50000.0, (
            'aditivo reprecificou marco JÁ RECEBIDO — o defeito que a Fase '
            f'0.6 fechou na porta da proposta: veio {recebido.valor}')
        assert recebido.valor_base == Decimal('100000.00'), (
            'aprovar_aditivo tem de congelar valor_base do marco recebido '
            f'com o valor da versão anterior — veio {recebido.valor_base}')
        assert recebido.contrato_versao_id == v1_id, (
            'marco recebido mantém a versão em que nasceu — não se move')

        assert float(futuro.valor) == 60000.0, (
            'marco não recebido tem de seguir o contrato novo '
            f'(50% × 120k) — veio {futuro.valor}')
        assert futuro.valor_base is None, (
            'marco não recebido NÃO congela — seguir o contrato novo é o '
            'que um aditivo significa')
        assert futuro.contrato_versao_id == v2_id, (
            'marco não recebido tem de ser repontado para a versão nova — '
            f'ficou em {futuro.contrato_versao_id}')


@pytest.mark.integration
def test_congelamento_nao_recongela_valor_base_ja_congelado(ambiente):
    """Dois aditivos em sequência: o valor_base congelado pelo primeiro não
    é sobrescrito pelo segundo — o marco vale o contrato da época em que foi
    recebido, para sempre (mesmo filtro `valor_base IS NULL` do bloco
    original do event_manager)."""
    from models import MedicaoContrato
    from services.contrato_obra import abrir_aditivo, aprovar_aditivo
    with app.app_context():
        obra = db.session.get(Obra, ambiente['obra_id'])
        recebido = _novo_marco(obra, 'Marco pago', '0.1',
                               recebido_no_mes='2026-01')
        db.session.commit()
        recebido_id = recebido.id

        a1 = abrir_aditivo(obra, tipo='acrescimo', motivo='primeiro',
                           valor_novo=120000.0)
        db.session.commit()
        aprovar_aditivo(a1)
        db.session.commit()

        a2 = abrir_aditivo(obra, tipo='acrescimo', motivo='segundo',
                           valor_novo=150000.0)
        db.session.commit()
        aprovar_aditivo(a2)
        db.session.commit()

        db.session.expire_all()
        recebido = db.session.get(MedicaoContrato, recebido_id)
        assert recebido.valor_base == Decimal('100000.00'), (
            'o segundo aditivo recongelou um valor_base já congelado — '
            f'veio {recebido.valor_base}')
        assert float(recebido.valor) == 10000.0


@pytest.mark.integration
def test_caminho_da_proposta_continua_congelando_via_servico(ambiente):
    """A extração do bloco do event_manager para o serviço não pode mudar o
    comportamento: a função extraída congela marcos recebidos e ignora os
    não recebidos e os de outra obra/tenant."""
    from models import MedicaoContrato
    from services.contrato_obra import congelar_base_medicoes_recebidas
    with app.app_context():
        obra = db.session.get(Obra, ambiente['obra_id'])
        recebido = _novo_marco(obra, 'Pago', '0.2', recebido_no_mes='2026-03')
        vazio = _novo_marco(obra, 'Recebido vazio', '0.2', recebido_no_mes='')
        futuro = _novo_marco(obra, 'Futuro', '0.6')

        outro_admin = _novo_admin('f6ad_outro')
        outra_obra = _nova_obra(outro_admin)
        alheio = _novo_marco(outra_obra, 'Alheio pago', '0.5',
                             recebido_no_mes='2026-03')
        db.session.commit()

        congeladas = congelar_base_medicoes_recebidas(obra, 100000.0)
        db.session.commit()

        assert congeladas == 1
        db.session.expire_all()
        assert db.session.get(MedicaoContrato, recebido.id).valor_base == \
            Decimal('100000.00')
        assert db.session.get(MedicaoContrato, vazio.id).valor_base is None, (
            "recebido_no_mes == '' não é recebido — mesmo filtro do bloco "
            'original')
        assert db.session.get(MedicaoContrato, futuro.id).valor_base is None
        assert db.session.get(MedicaoContrato, alheio.id).valor_base is None, (
            'a função congelou marco de OUTRA obra/tenant')


@pytest.mark.integration
def test_importador_preenche_contrato_versao_id():
    """`_importar_medicoes` cria os marcos já apontando para a versão
    vigente do baseline (o orquestrador flusha a obra — e a versão aberta
    por definir_valor_contrato — antes deste passo)."""
    from models import MedicaoContrato
    from services.contrato_obra import ORIGEM_IMPORTACAO, definir_valor_contrato
    from services.importacao_fisico_financeiro import _importar_medicoes
    with app.app_context():
        admin = _novo_admin('f6ad_imp')
        obra = _nova_obra(admin)
        definir_valor_contrato(obra, 100000.0, origem=ORIGEM_IMPORTACAO,
                               motivo='import de teste')
        db.session.flush()  # espelha o flush do orquestrador antes do passo 5

        _importar_medicoes(obra, admin.id, {'medicoes': [
            {'nome': 'M1', 'pct': 0.5, 'recebido_no_mes': '2026-01'},
            {'nome': 'M2', 'pct': 0.5},
        ]})
        db.session.commit()

        v1 = ObraContratoVersao.query.filter_by(
            obra_id=obra.id, vigente_ate=None).one()
        meds = MedicaoContrato.query.filter_by(
            obra_id=obra.id, admin_id=admin.id).all()
        assert len(meds) == 2
        assert {m.contrato_versao_id for m in meds} == {v1.id}, (
            'o importador tem de preencher a FK ao criar marcos — veio '
            f'{[m.contrato_versao_id for m in meds]}')


@pytest.mark.integration
def test_migration_273_backfill_aponta_para_vigente_e_e_reexecutavel(ambiente):
    """Backfill: marco sem FK passa a apontar para a versão VIGENTE da obra;
    marco já apontado não é tocado; re-executar não falha nem duplica a FK."""
    from migrations import _migration_273_medicao_contrato_versionada
    from models import MedicaoContrato
    from sqlalchemy import text as _text
    with app.app_context():
        obra = db.session.get(Obra, ambiente['obra_id'])
        v1 = ObraContratoVersao.query.filter_by(
            obra_id=obra.id, vigente_ate=None).one()
        orfao = _novo_marco(obra, 'Sem FK', '0.5')
        assert orfao.contrato_versao_id is None
        # Ids capturados ANTES do commit: qualquer acesso a atributo DEPOIS
        # dele reabre transação ORM segurando AccessShareLock em
        # medicao_contrato — e o ALTER TABLE da migration (conexão própria)
        # ficaria esperando o lock para sempre.
        orfao_id, v1_id = orfao.id, v1.id
        db.session.commit()

        _migration_273_medicao_contrato_versionada()
        _migration_273_medicao_contrato_versionada()  # re-executável

        db.session.expire_all()
        assert db.session.get(MedicaoContrato, orfao_id).contrato_versao_id \
            == v1_id, 'o backfill tem de apontar o marco para a vigente'

        fks = db.session.execute(_text("""
            SELECT count(*)
            FROM pg_constraint c
            WHERE c.conrelid = 'medicao_contrato'::regclass
              AND c.contype = 'f'
              AND c.conkey = ARRAY[(
                  SELECT attnum FROM pg_attribute
                  WHERE attrelid = 'medicao_contrato'::regclass
                    AND attname = 'contrato_versao_id')]::smallint[]
        """)).scalar()
        assert fks == 1, (
            f'esperava exatamente 1 FK em medicao_contrato.contrato_versao_id, '
            f'achei {fks} — reexecução não pode duplicar a constraint')


# ---------------------------------------------------------------------------
# Task 7 — revisão de proposta: item suprimido vira estado, redução abaixo
# do medido é recusada
# ---------------------------------------------------------------------------
# Os helpers de `test_proposta_revisao_nao_duplica_obra` disparam o
# `EventManager.emit` REAL — o mesmo caminho das rotas de aprovação.
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from test_proposta_revisao_nao_duplica_obra import (  # noqa: E402
    _ambiente,
    _aprovar,
    _clonar_como_revisao,
    _obras_do_tenant,
)


def _segundo_item(proposta, admin_id, descricao='Cobertura',
                  valor=Decimal('30000.00')):
    """Acrescenta um 2º item à proposta e ajusta o total."""
    from models import PropostaItem
    db.session.add(PropostaItem(
        proposta_id=proposta.id, admin_id=admin_id, item_numero=2,
        descricao=descricao, quantidade=Decimal('1'), unidade='vb',
        preco_unitario=valor, subtotal=valor))
    proposta.valor_total = (proposta.valor_total or 0) + valor
    db.session.commit()


def _imcs_da_obra(obra_id, admin_id):
    from models import ItemMedicaoComercial
    return ItemMedicaoComercial.query.filter_by(
        obra_id=obra_id, admin_id=admin_id).order_by(
        ItemMedicaoComercial.id).all()


@pytest.mark.integration
def test_revisao_reconcilia_item_sem_duplicar_nem_estourar_saldo():
    """Comportamento pós-Fase 0.6/D1, asserido pelo caminho real do emit:
    aprovar a v2 (100k → 120k) ATUALIZA o item de medição existente.

    1 IMC somando 120.000, 1 OSC, saldo (contrato − itens) == 0. Os números
    do defeito extinto de §1.1 (2 IMC, 220k, saldo -100k) não voltam."""
    from models import ObraServicoCusto
    with app.app_context():
        admin, _cliente, v1 = _ambiente()
        admin_id = admin.id
        _aprovar(v1, admin_id)
        obra = _obras_do_tenant(admin_id)[0]
        obra_id = obra.id

        v2 = _clonar_como_revisao(v1, admin_id, herdar_obra=True)
        _aprovar(v2, admin_id)

        db.session.expire_all()
        imcs = _imcs_da_obra(obra_id, admin_id)
        assert len(imcs) == 1, (
            f'{len(imcs)} itens de medição — a revisão duplicou')
        assert float(imcs[0].valor_comercial) == 120000.0
        oscs = ObraServicoCusto.query.filter_by(
            obra_id=obra_id, admin_id=admin_id).all()
        assert len(oscs) == 1, f'{len(oscs)} OSC para 1 item'
        obra = db.session.get(Obra, obra_id)
        saldo = float(obra.valor_contrato or 0) - sum(
            float(i.valor_comercial or 0) for i in imcs)
        assert saldo == pytest.approx(0.0), (
            f'saldo {saldo:,.2f} — contrato {obra.valor_contrato}')


@pytest.mark.integration
def test_item_suprimido_na_revisao_vira_estado_e_nao_some():
    """v1 tem 2 itens; a v2 mantém só o 1º. O IMC do item que saiu NÃO é
    apagado (pode haver MedicaoObraItem apontando) — ele vira
    status='SUPRIMIDO', com o valor_comercial preservado para histórico."""
    with app.app_context():
        admin, _cliente, v1 = _ambiente()
        admin_id = admin.id
        _segundo_item(v1, admin_id)          # v1: 100k + 30k
        _aprovar(v1, admin_id)
        obra_id = _obras_do_tenant(admin_id)[0].id
        assert len(_imcs_da_obra(obra_id, admin_id)) == 2

        v2 = _clonar_como_revisao(v1, admin_id, herdar_obra=True)  # só item 1
        _aprovar(v2, admin_id)

        db.session.expire_all()
        imcs = _imcs_da_obra(obra_id, admin_id)
        assert len(imcs) == 2, (
            'o item suprimido sumiu do banco — nunca DELETE, só estado')
        por_nome = {i.nome: i for i in imcs}
        suprimido = por_nome['Cobertura']
        assert suprimido.status == 'SUPRIMIDO', (
            f"item removido da v2 ficou '{suprimido.status}' — o WARNING "
            'tinha de virar estado')
        assert float(suprimido.valor_comercial) == 30000.0, (
            'o valor histórico do item suprimido foi perdido')
        mantido = por_nome['Estrutura metálica (revisada)']
        assert mantido.status == 'PENDENTE'
        assert float(mantido.valor_comercial) == 120000.0


@pytest.mark.integration
def test_item_suprimido_que_volta_em_versao_posterior_e_reativado():
    """Decisão de negócio da Task 7: SUPRIMIDO descreve o escopo APROVADO
    vigente, não é lápide. Se a v3 re-inclui o item, ele volta a PENDENTE —
    deixá-lo SUPRIMIDO faria o escopo ativo da obra divergir do contrato."""
    from models import Proposta, PropostaItem
    with app.app_context():
        admin, _cliente, v1 = _ambiente()
        admin_id = admin.id
        _segundo_item(v1, admin_id)
        _aprovar(v1, admin_id)
        obra_id = _obras_do_tenant(admin_id)[0].id

        v2 = _clonar_como_revisao(v1, admin_id, herdar_obra=True)  # sem item 2
        _aprovar(v2, admin_id)

        # v3 re-inclui o item 2 (mesmo item_numero — o elo de linhagem).
        v3 = Proposta(
            admin_id=admin_id, numero=f'{v2.numero}-v3', titulo=v2.titulo,
            cliente_id=v2.cliente_id, cliente_nome=v2.cliente_nome,
            valor_total=Decimal('150000.00'), status='rascunho',
            versao=(v2.versao or 2) + 1, proposta_origem_id=v2.id,
            obra_id=v2.obra_id,
        )
        db.session.add(v3)
        db.session.flush()
        db.session.add(PropostaItem(
            proposta_id=v3.id, admin_id=admin_id, item_numero=1,
            descricao='Estrutura metálica (revisada)', quantidade=Decimal('1'),
            unidade='vb', preco_unitario=Decimal('120000.00'),
            subtotal=Decimal('120000.00')))
        db.session.add(PropostaItem(
            proposta_id=v3.id, admin_id=admin_id, item_numero=2,
            descricao='Cobertura', quantidade=Decimal('1'), unidade='vb',
            preco_unitario=Decimal('30000.00'), subtotal=Decimal('30000.00')))
        db.session.commit()
        _aprovar(v3, admin_id)

        db.session.expire_all()
        imcs = _imcs_da_obra(obra_id, admin_id)
        assert len(imcs) == 2, 'a volta do item não pode inserir um 3º IMC'
        por_nome = {i.nome: i for i in imcs}
        reativado = por_nome['Cobertura']
        assert reativado.status == 'PENDENTE', (
            f"item re-incluído na v3 ficou '{reativado.status}' — "
            'SUPRIMIDO não é lápide')
        assert float(reativado.valor_comercial) == 30000.0


@pytest.mark.integration
def test_reducao_de_item_abaixo_do_ja_medido_e_recusada():
    """A guarda aritmética: item com R$ 60.000 já medidos não pode cair para
    R$ 50.000. O aditivo é recusado com item, medido e tentado na mensagem,
    e o rollback da rota (emit raise_on_error=True) desfaz tudo."""
    from decimal import Decimal as D
    from event_manager import EventManager
    from models import Proposta, PropostaItem
    with app.app_context():
        admin, _cliente, v1 = _ambiente()
        admin_id = admin.id
        _aprovar(v1, admin_id)
        obra_id = _obras_do_tenant(admin_id)[0].id
        imc = _imcs_da_obra(obra_id, admin_id)[0]
        imc.percentual_executado_acumulado = D('60')
        imc.valor_executado_acumulado = D('60000.00')
        db.session.commit()

        # v2 tenta reduzir o item de 100k para 50k (< 60k já medidos).
        v2 = Proposta(
            admin_id=admin_id, numero=f'{v1.numero}-v2', titulo=v1.titulo,
            cliente_id=v1.cliente_id, cliente_nome=v1.cliente_nome,
            valor_total=D('50000.00'), status='aprovada',
            versao=(v1.versao or 1) + 1, proposta_origem_id=v1.id,
            obra_id=v1.obra_id,
        )
        db.session.add(v2)
        db.session.flush()
        db.session.add(PropostaItem(
            proposta_id=v2.id, admin_id=admin_id, item_numero=1,
            descricao='Estrutura metálica', quantidade=D('1'), unidade='vb',
            preco_unitario=D('50000.00'), subtotal=D('50000.00')))
        db.session.flush()

        with pytest.raises(ValueError) as exc:
            EventManager.emit('proposta_aprovada', {
                'proposta_id': v2.id,
                'admin_id': admin_id,
                'cliente_nome': v2.cliente_nome,
                'valor_total': float(v2.valor_total),
                'data_aprovacao': date.today().isoformat(),
            }, admin_id, raise_on_error=True)
        db.session.rollback()

        msg = str(exc.value)
        assert 'Estrutura metálica' in msg, f'mensagem sem o item: {msg}'
        assert 'R$ 60000.00' in msg, f'mensagem sem o valor já medido: {msg}'
        assert 'R$ 50000.00' in msg, f'mensagem sem o valor tentado: {msg}'

        # Nada mudou: o rollback da rota desfaz o aditivo inteiro.
        db.session.expire_all()
        imc = _imcs_da_obra(obra_id, admin_id)[0]
        assert float(imc.valor_comercial) == 100000.0, (
            'a recusa não pode deixar o valor reduzido para trás')
        assert float(imc.percentual_executado_acumulado) == 60.0


# ---------------------------------------------------------------------------
# Task 7 — fix round 1: SUPRIMIDO tem de ser durável, e os caminhos comuns
# da guarda ganham guardião
# ---------------------------------------------------------------------------

def _cenario_com_supressao():
    """v1 (100k + 30k) aprovada, v2 (120k, só item 1) aprovada.

    Devolve (admin_id, obra_id, id do IMC suprimido 'Cobertura')."""
    admin, _cliente, v1 = _ambiente()
    admin_id = admin.id
    _segundo_item(v1, admin_id)
    _aprovar(v1, admin_id)
    obra_id = _obras_do_tenant(admin_id)[0].id
    v2 = _clonar_como_revisao(v1, admin_id, herdar_obra=True)
    _aprovar(v2, admin_id)
    db.session.expire_all()
    por_nome = {i.nome: i for i in _imcs_da_obra(obra_id, admin_id)}
    suprimido = por_nome['Cobertura']
    assert suprimido.status == 'SUPRIMIDO'
    return admin_id, obra_id, suprimido.id, v2


@pytest.mark.integration
def test_recalculo_de_avanco_nao_apaga_suprimido():
    """`_recalcular_imc_avanco` roda a cada RDO finalizado e escrevia
    status='CONCLUIDO' em qualquer item 100% medido — inclusive num
    SUPRIMIDO, apagando em silêncio o estado que a supressão acabou de
    gravar. O item suprimido 100% executado é exatamente o caso que a regra
    'nunca DELETE, marque estado' existe para proteger."""
    from models import ItemMedicaoComercial, ItemMedicaoCronogramaTarefa, TarefaCronograma
    from services.medicao_service import _recalcular_imc_avanco
    with app.app_context():
        admin_id, obra_id, imc_id, _v2 = _cenario_com_supressao()

        # O item suprimido estava 100% executado: tarefa concluída vinculada.
        tarefa = TarefaCronograma(
            obra_id=obra_id, admin_id=admin_id, ordem=1,
            nome_tarefa='Cobertura', percentual_concluido=100)
        db.session.add(tarefa)
        db.session.flush()
        db.session.add(ItemMedicaoCronogramaTarefa(
            item_medicao_id=imc_id, cronograma_tarefa_id=tarefa.id,
            peso=Decimal('100'), admin_id=admin_id))
        db.session.commit()

        _recalcular_imc_avanco(obra_id, admin_id)
        db.session.commit()

        db.session.expire_all()
        imc = db.session.get(ItemMedicaoComercial, imc_id)
        assert float(imc.percentual_executado_acumulado) == 100.0
        assert float(imc.valor_executado_acumulado) == 30000.0, (
            'o executado do item suprimido é devido — o valor tem de contar')
        assert imc.status == 'SUPRIMIDO', (
            f"o recálculo apagou a supressão: status virou '{imc.status}' — "
            'SUPRIMIDO tem de sobreviver ao RDO/medição seguinte')


@pytest.mark.integration
def test_reaprovar_v2_nao_re_suprime_nem_re_loga(caplog):
    """Idempotência da supressão: reaprovar a MESMA v2 não re-suprime nem
    re-emite o warning #82/T7 — órfão já SUPRIMIDO é caso encerrado."""
    import logging as _logging
    with app.app_context():
        admin_id, obra_id, imc_id, v2 = _cenario_com_supressao()

        with caplog.at_level(_logging.WARNING,
                             logger='handlers.propostas_handlers'):
            caplog.clear()
            _aprovar(v2, admin_id)   # segunda aprovação da mesma v2

        db.session.expire_all()
        imcs = _imcs_da_obra(obra_id, admin_id)
        assert len(imcs) == 2
        por_nome = {i.nome: i for i in imcs}
        assert por_nome['Cobertura'].status == 'SUPRIMIDO'
        relogs = [r for r in caplog.records if '#82/T7' in r.getMessage()]
        assert not relogs, (
            f'reaprovar a mesma v2 re-logou a supressão: '
            f'{[r.getMessage() for r in relogs]}')


@pytest.mark.integration
def test_aumento_de_item_ja_medido_e_aceito():
    """O happy path do aditivo em produção: item com 60% medidos cujo valor
    SOBE (100k → 150k). A guarda não pode barrar aumento — só redução
    abaixo do medido."""
    from decimal import Decimal as D
    from event_manager import EventManager
    from models import Proposta, PropostaItem
    with app.app_context():
        admin, _cliente, v1 = _ambiente()
        admin_id = admin.id
        _aprovar(v1, admin_id)
        obra_id = _obras_do_tenant(admin_id)[0].id
        imc = _imcs_da_obra(obra_id, admin_id)[0]
        imc.percentual_executado_acumulado = D('60')
        imc.valor_executado_acumulado = D('60000.00')
        db.session.commit()

        v2 = Proposta(
            admin_id=admin_id, numero=f'{v1.numero}-v2', titulo=v1.titulo,
            cliente_id=v1.cliente_id, cliente_nome=v1.cliente_nome,
            valor_total=D('150000.00'), status='aprovada',
            versao=(v1.versao or 1) + 1, proposta_origem_id=v1.id,
            obra_id=v1.obra_id,
        )
        db.session.add(v2)
        db.session.flush()
        db.session.add(PropostaItem(
            proposta_id=v2.id, admin_id=admin_id, item_numero=1,
            descricao='Estrutura metálica', quantidade=D('1'), unidade='vb',
            preco_unitario=D('150000.00'), subtotal=D('150000.00')))
        db.session.flush()

        EventManager.emit('proposta_aprovada', {
            'proposta_id': v2.id,
            'admin_id': admin_id,
            'cliente_nome': v2.cliente_nome,
            'valor_total': float(v2.valor_total),
            'data_aprovacao': date.today().isoformat(),
        }, admin_id, raise_on_error=True)
        db.session.commit()

        db.session.expire_all()
        imc = _imcs_da_obra(obra_id, admin_id)[0]
        assert float(imc.valor_comercial) == 150000.0, (
            'a guarda barrou o aumento — só redução abaixo do medido é ilegal')
        assert float(imc.percentual_executado_acumulado) == 60.0
        assert imc.status == 'PENDENTE'


# ---------------------------------------------------------------------------
# Task 8 — contabilidade do aditivo: a porta nova lança o delta
# ---------------------------------------------------------------------------
# `handle_proposta_aprovada` (porta velha) lança o DELTA da linhagem desde a
# Fase 0.6/D1b. `aprovar_aditivo` (porta nova, Task 3) mudava o contrato sem
# lançar nada: a soma dos `LancamentoContabil` da linhagem parava no valor
# pré-aditivo. O invariante desta seção: soma(linhagem) == contrato vigente.
#
# O rótulo do lançamento do aditivo fica `origem='PROPOSTAS'` DE PROPÓSITO:
# `ja_lancado` (handlers/propostas_handlers.py) soma
# `origem == 'PROPOSTAS' AND origem_id IN ids_linhagem` — um rótulo
# 'ADITIVO' esconderia o lançamento da PRÓXIMA revisão de proposta, que
# voltaria a lançar o valor cheio (o defeito D1b de volta).

def _lancamentos_da_linhagem(admin_id, ids):
    from models import LancamentoContabil
    return LancamentoContabil.query.filter(
        LancamentoContabil.admin_id == admin_id,
        LancamentoContabil.origem == 'PROPOSTAS',
        LancamentoContabil.origem_id.in_(ids),
    ).order_by(LancamentoContabil.id).all()


def _soma_da_linhagem(admin_id, ids):
    return float(sum((Decimal(str(l.valor_total))
                      for l in _lancamentos_da_linhagem(admin_id, ids)),
                     Decimal('0')))


@pytest.mark.integration
def test_aprovar_aditivo_lanca_delta_e_soma_da_linhagem_acompanha_contrato():
    """O invariante do Step 1 pela porta NOVA: aprovado o aditivo, a soma dos
    LancamentoContabil da linhagem tem de bater com o contrato vigente.
    Antes da Task 8, o contrato ia a 130k e a soma parava em 100k."""
    from services.contrato_obra import abrir_aditivo, aprovar_aditivo
    with app.app_context():
        admin, _cliente, v1 = _ambiente()
        _aprovar(v1, admin.id)
        obra = _obras_do_tenant(admin.id)[0]
        assert _soma_da_linhagem(admin.id, [v1.id]) == pytest.approx(100000.0)

        aditivo = abrir_aditivo(obra, tipo='acrescimo',
                                motivo='fundação extra', valor_novo=130000.0,
                                proposta_id=v1.id,
                                criado_por_id=admin.id)
        db.session.commit()
        aprovar_aditivo(aditivo, aprovado_por_id=admin.id)
        db.session.commit()
        db.session.expire_all()

        obra = db.session.get(Obra, obra.id)
        assert float(obra.valor_contrato) == pytest.approx(130000.0)
        lancs = _lancamentos_da_linhagem(admin.id, [v1.id])
        assert len(lancs) == 2, (
            'a aprovação do aditivo tem de criar o lançamento do delta '
            f'(existem {len(lancs)} lançamento(s) na linhagem)')
        assert float(lancs[-1].valor_total) == pytest.approx(30000.0), (
            'o aditivo lança o DELTA (130k − 100k), nunca o valor cheio')
        assert lancs[-1].origem == 'PROPOSTAS'
        assert _soma_da_linhagem(admin.id, [v1.id]) == pytest.approx(
            float(obra.valor_contrato)), (
            'soma(lançamentos da linhagem) tem de bater com o contrato vigente')

        # Reaprovar é no-op idempotente — não lança em dobro.
        aditivo = db.session.get(AditivoContrato, aditivo.id)
        aprovar_aditivo(aditivo, aprovado_por_id=admin.id)
        db.session.commit()
        assert _soma_da_linhagem(admin.id, [v1.id]) == pytest.approx(130000.0)


@pytest.mark.integration
def test_aditivo_negativo_inverte_partidas_e_usa_conta_de_deducao():
    """Supressão (100k → 80k): mesmo tratamento da revisão para baixo da
    porta velha — partidas invertidas (CREDITO em 1.1.02.001) e contrapartida
    em `4.2.01.001` (dedução), porque um débito na conta de receita ficaria
    invisível no DRE (que soma só partidas CREDITO em 4.1.x)."""
    from models import PartidaContabil
    from services.contrato_obra import abrir_aditivo, aprovar_aditivo
    with app.app_context():
        admin, _cliente, v1 = _ambiente()
        _aprovar(v1, admin.id)
        obra = _obras_do_tenant(admin.id)[0]

        aditivo = abrir_aditivo(obra, tipo='supressao',
                                motivo='corte de escopo', valor_novo=80000.0,
                                proposta_id=v1.id)
        db.session.commit()
        aprovar_aditivo(aditivo, aprovado_por_id=admin.id)
        db.session.commit()
        db.session.expire_all()

        lancs = _lancamentos_da_linhagem(admin.id, [v1.id])
        assert len(lancs) == 2, 'a supressão tem de lançar o estorno do delta'
        estorno = lancs[-1]
        assert float(estorno.valor_total) == pytest.approx(-20000.0)

        partidas = PartidaContabil.query.filter_by(
            lancamento_id=estorno.id).order_by(
            PartidaContabil.sequencia).all()
        assert [(p.conta_codigo, p.tipo_partida, float(p.valor))
                for p in partidas] == [
            ('1.1.02.001', 'CREDITO', pytest.approx(20000.0)),
            ('4.2.01.001', 'DEBITO', pytest.approx(20000.0)),
        ], ('estorno inverte as partidas e usa a conta de dedução '
            '4.2.01.001 — nunca débito na conta de receita')

        obra = db.session.get(Obra, obra.id)
        assert float(obra.valor_contrato) == pytest.approx(80000.0)
        assert _soma_da_linhagem(admin.id, [v1.id]) == pytest.approx(80000.0)


@pytest.mark.integration
def test_aditivo_de_prazo_puro_delta_zero_nao_lanca_nada():
    """Aditivo de prazo puro é aditivo (abre versão nova — Task 3), mas não é
    fato contábil: nenhum lançamento novo."""
    from services.contrato_obra import abrir_aditivo, aprovar_aditivo
    with app.app_context():
        admin, _cliente, v1 = _ambiente()
        _aprovar(v1, admin.id)
        obra = _obras_do_tenant(admin.id)[0]

        aditivo = abrir_aditivo(obra, tipo='prazo', motivo='chuvas',
                                prazo_delta_dias=45, proposta_id=v1.id)
        db.session.commit()
        aprovar_aditivo(aditivo, aprovado_por_id=admin.id)
        db.session.commit()
        db.session.expire_all()

        lancs = _lancamentos_da_linhagem(admin.id, [v1.id])
        assert len(lancs) == 1, (
            'delta zero não lança nada — só o lançamento original da proposta')
        assert _soma_da_linhagem(admin.id, [v1.id]) == pytest.approx(100000.0)
        obra = db.session.get(Obra, obra.id)
        assert float(obra.valor_contrato) == pytest.approx(100000.0)


@pytest.mark.integration
def test_aditivo_sem_proposta_id_lanca_na_raiz_e_revisao_seguinte_nao_duplica():
    """Aditivo aberto SEM `proposta_id` numa obra nascida de proposta: o
    `origem_id` cai na RAIZ da linhagem da obra — e a revisão de proposta
    seguinte ENXERGA o lançamento no `ja_lancado`, lançando só o delta
    restante. É a coerência que impede o defeito D1b de voltar por esta
    porta."""
    from services.contrato_obra import abrir_aditivo, aprovar_aditivo
    with app.app_context():
        admin, _cliente, v1 = _ambiente()
        _aprovar(v1, admin.id)
        obra = _obras_do_tenant(admin.id)[0]

        aditivo = abrir_aditivo(obra, tipo='acrescimo',
                                motivo='escopo extra sem revisão formal',
                                valor_novo=130000.0)  # proposta_id=None
        db.session.commit()
        aprovar_aditivo(aditivo, aprovado_por_id=admin.id)
        db.session.commit()
        db.session.expire_all()

        lancs = _lancamentos_da_linhagem(admin.id, [v1.id])
        assert len(lancs) == 2, (
            'sem proposta_id o lançamento tem de cair na linhagem da obra '
            '(raiz) — fora dela, a próxima revisão lançaria em dobro')
        assert lancs[-1].origem_id == v1.id
        assert float(lancs[-1].valor_total) == pytest.approx(30000.0)

        # A revisão seguinte (120k) enxerga os 130k já lançados e ESTORNA 10k
        # — jamais lança os 120k cheios (que dariam 250k de receita).
        v2 = _clonar_como_revisao(v1, admin.id, herdar_obra=True)
        _aprovar(v2, admin.id)
        db.session.expire_all()

        ids = [v1.id, v2.id]
        lancs = _lancamentos_da_linhagem(admin.id, ids)
        assert len(lancs) == 3
        assert float(lancs[-1].valor_total) == pytest.approx(-10000.0), (
            'a revisão pós-aditivo lança o delta sobre TUDO que a linhagem '
            'já lançou (100k + 30k) — não o valor cheio')
        obra = db.session.get(Obra, obra.id)
        assert float(obra.valor_contrato) == pytest.approx(120000.0)
        assert _soma_da_linhagem(admin.id, ids) == pytest.approx(120000.0)


@pytest.mark.integration
def test_aditivo_em_obra_sem_linhagem_de_proposta_nao_lanca_nada(ambiente):
    """Obra de cadastro manual (fixture `ambiente`): o contrato original
    nunca entrou na contabilidade (as portas manuais não lançam receita),
    então o aditivo também não lança — lançar só o delta criaria uma receita
    parcial sem base, e inventar um origem_id fora de linhagem poderia
    colidir com a linhagem de uma proposta real. Decisão registrada no
    report da Task 8."""
    from models import LancamentoContabil
    from services.contrato_obra import abrir_aditivo, aprovar_aditivo
    with app.app_context():
        obra = db.session.get(Obra, ambiente['obra_id'])
        aditivo = abrir_aditivo(obra, tipo='acrescimo', motivo='mais escopo',
                                valor_novo=130000.0)
        db.session.commit()
        aprovar_aditivo(aditivo, aprovado_por_id=ambiente['admin_id'])
        db.session.commit()
        db.session.expire_all()

        assert LancamentoContabil.query.filter_by(
            admin_id=ambiente['admin_id']).count() == 0
        obra = db.session.get(Obra, obra.id)
        assert float(obra.valor_contrato) == pytest.approx(130000.0)


@pytest.mark.integration
def test_porta_velha_revisao_de_proposta_continua_lancando_so_o_delta():
    """Regressão da extração: o corpo do lançamento saiu de
    `handle_proposta_aprovada` para a função reutilizável — a porta velha
    tem de continuar idêntica (v1 lança 100k, a revisão v2 lança +20k)."""
    with app.app_context():
        admin, _cliente, v1 = _ambiente()
        _aprovar(v1, admin.id)
        v2 = _clonar_como_revisao(v1, admin.id, herdar_obra=True)
        _aprovar(v2, admin.id)
        db.session.expire_all()

        ids = [v1.id, v2.id]
        lancs = _lancamentos_da_linhagem(admin.id, ids)
        assert [float(l.valor_total) for l in lancs] == [
            pytest.approx(100000.0), pytest.approx(20000.0)]
        # fix round 1: historico e data_lancamento são exatamente os campos
        # que a extração parametrizou — travá-los fixa o contrato de
        # `lancar_delta_contrato` na porta velha.
        assert lancs[0].historico == (
            f'Proposta aprovada #{v1.id} - {v1.cliente_nome}')
        assert lancs[1].historico == (
            f'Revisão de proposta #{v2.id} - {v2.cliente_nome} - '
            f'aditivo sobre R$ 100000.00')
        assert [l.data_lancamento for l in lancs] == [date.today()] * 2
        assert _soma_da_linhagem(admin.id, ids) == pytest.approx(120000.0)
        obra = _obras_do_tenant(admin.id)[0]
        assert float(obra.valor_contrato) == pytest.approx(120000.0)


@pytest.mark.integration
def test_proposta_id_de_outra_obra_do_tenant_nao_desvia_o_lancamento():
    """fix round 1: `abrir_aditivo` aceita `proposta_id` livre (a Task 13
    vai ligar um <select> a ele). Um id de proposta de OUTRA obra do MESMO
    tenant não pode lançar o delta na linhagem alheia — quebraria o
    invariante das duas obras e envenenaria o `ja_lancado` da próxima
    revisão de lá. O filtro amarra a proposta à obra e o fallback degrada
    para a linhagem da própria obra do aditivo."""
    from models import Proposta, PropostaItem
    from services.contrato_obra import abrir_aditivo, aprovar_aditivo
    with app.app_context():
        admin, _cliente, pa = _ambiente()
        _aprovar(pa, admin.id)
        obra_a = _obras_do_tenant(admin.id)[0]

        # Obra B do MESMO tenant, nascida de outra proposta (pb).
        pb = Proposta(
            admin_id=admin.id, numero=f'{pa.numero}-B', titulo='Outra obra',
            cliente_id=pa.cliente_id, cliente_nome=pa.cliente_nome,
            valor_total=Decimal('50000.00'), status='enviada', versao=1)
        db.session.add(pb)
        db.session.flush()
        db.session.add(PropostaItem(
            proposta_id=pb.id, admin_id=admin.id, item_numero=1,
            descricao='Serviço B', quantidade=Decimal('1'), unidade='vb',
            preco_unitario=Decimal('50000.00'), subtotal=Decimal('50000.00')))
        db.session.commit()
        _aprovar(pb, admin.id)

        aditivo = abrir_aditivo(obra_a, tipo='acrescimo',
                                motivo='vínculo documental errado',
                                valor_novo=130000.0, proposta_id=pb.id)
        db.session.commit()
        aprovar_aditivo(aditivo, aprovado_por_id=admin.id)
        db.session.commit()
        db.session.expire_all()

        # O delta caiu na linhagem da obra A (raiz pa)…
        lancs_a = _lancamentos_da_linhagem(admin.id, [pa.id])
        assert [float(l.valor_total) for l in lancs_a] == [
            pytest.approx(100000.0), pytest.approx(30000.0)]
        obra_a = db.session.get(Obra, obra_a.id)
        assert float(obra_a.valor_contrato) == pytest.approx(130000.0)
        assert _soma_da_linhagem(admin.id, [pa.id]) == pytest.approx(130000.0)

        # …e a linhagem da obra B ficou intocada (só o lançamento da própria
        # proposta pb) — soma == contrato de B.
        lancs_b = _lancamentos_da_linhagem(admin.id, [pb.id])
        assert [float(l.valor_total) for l in lancs_b] == [
            pytest.approx(50000.0)], (
            'a linhagem da obra alheia não pode ganhar o delta do aditivo')
        obra_b = db.session.get(Obra, pb.obra_id)
        assert float(obra_b.valor_contrato) == pytest.approx(50000.0)


@pytest.mark.integration
def test_aditivo_nao_alcanca_proposta_de_outro_tenant():
    """fix round 1: aditivo do tenant A com `proposta_id` apontando para
    proposta do tenant B não pode alcançá-la — nem para usar o id dela como
    raiz, nem para tocar a contabilidade de B. O delta cai na linhagem da
    própria obra A (fallback filtrado por admin_id + obra_id)."""
    from models import LancamentoContabil
    from services.contrato_obra import abrir_aditivo, aprovar_aditivo
    with app.app_context():
        admin_a, _ca, pa = _ambiente()
        _aprovar(pa, admin_a.id)
        obra_a = _obras_do_tenant(admin_a.id)[0]

        admin_b, _cb, pb = _ambiente()
        _aprovar(pb, admin_b.id)

        aditivo = abrir_aditivo(obra_a, tipo='acrescimo',
                                motivo='id de outro tenant',
                                valor_novo=130000.0, proposta_id=pb.id)
        db.session.commit()
        aprovar_aditivo(aditivo, aprovado_por_id=admin_a.id)
        db.session.commit()
        db.session.expire_all()

        # Tenant A: delta na PRÓPRIA linhagem (raiz pa), invariante fechado.
        lancs_a = _lancamentos_da_linhagem(admin_a.id, [pa.id])
        assert [float(l.valor_total) for l in lancs_a] == [
            pytest.approx(100000.0), pytest.approx(30000.0)]
        assert _soma_da_linhagem(admin_a.id, [pa.id]) == pytest.approx(130000.0)

        # Nenhum lançamento do tenant A referencia a proposta do tenant B…
        assert LancamentoContabil.query.filter_by(
            admin_id=admin_a.id, origem='PROPOSTAS',
            origem_id=pb.id).count() == 0
        # …e a contabilidade do tenant B ficou intocada.
        lancs_b = _lancamentos_da_linhagem(admin_b.id, [pb.id])
        assert [float(l.valor_total) for l in lancs_b] == [
            pytest.approx(100000.0)]


# ---------------------------------------------------------------------------
# Task 9 — aditivo ajusta o cronograma sem destruir histórico (D3)
# ---------------------------------------------------------------------------
# Item suprimido na revisão ARQUIVA (ativa=False) as tarefas geradas por ele,
# em cascata nos filhos — nunca DELETE: apagar TarefaCronograma destrói
# RDOApontamentoCronograma (FK ondelete=CASCADE); o flag `ativa` foi criado
# na M05 exatamente para este caso. Item alterado é no-op no cronograma
# (decisão D3: cronograma é planejamento, não derivado do preço). Item novo
# já era coberto pela idempotência da materialização.

def _no_snapshot(pi_id, servico_nome, filhos_nomes):
    """Nó nível-0 do `cronograma_default_json` como a rota de preview salva:
    raiz-serviço marcada + folhas marcadas (sem template/subatividade)."""
    return {
        'proposta_item_id': pi_id,
        'marcado': True,
        'servico_nome': servico_nome,
        'servico_id': None,
        'sem_template': False,
        'filhos': [
            {'marcado': True, 'nome': nome, 'duracao_dias': 2,
             'horas_estimadas': 8, 'filhos': []}
            for nome in filhos_nomes
        ],
    }


def _tarefas_da_obra(obra_id, admin_id):
    from models import TarefaCronograma
    return (TarefaCronograma.query
            .filter_by(obra_id=obra_id, admin_id=admin_id, is_cliente=False)
            .order_by(TarefaCronograma.id).all())


@pytest.mark.integration
def test_aditivo_suprime_item_arquiva_tarefas_em_cascata_sem_apagar_rdo():
    """Cenário do Step 1: v1 materializa 2 serviços; a v2 suprime o 2º e
    acrescenta um 3º. Esperado: tarefas do 1º intactas; as do 2º com
    ativa=False EM CASCATA (inclusive filho criado à mão, sem
    gerada_por_proposta_item_id); as do 3º criadas; NENHUMA tarefa apagada;
    e o apontamento de RDO existente na tarefa suprimida sobrevive — a razão
    de ser do flag `ativa` (D3)."""
    from models import (CronogramaVersao, Proposta, PropostaItem, RDO,
                        RDOApontamentoCronograma, TarefaCronograma)
    with app.app_context():
        admin, _cliente, v1 = _ambiente()
        admin_id = admin.id
        _segundo_item(v1, admin_id)          # v1: Estrutura 100k + Cobertura 30k
        itens_v1 = {i.item_numero: i for i in PropostaItem.query.filter_by(
            proposta_id=v1.id).all()}
        v1.cronograma_default_json = [
            _no_snapshot(itens_v1[1].id, 'Estrutura metálica',
                         ['Montagem estrutura']),
            _no_snapshot(itens_v1[2].id, 'Cobertura', ['Instalação telhas']),
        ]
        db.session.commit()
        _aprovar(v1, admin_id)

        obra_id = _obras_do_tenant(admin_id)[0].id
        tarefas = _tarefas_da_obra(obra_id, admin_id)
        por_nome = {t.nome_tarefa: t for t in tarefas}
        assert set(por_nome) == {'Estrutura metálica', 'Montagem estrutura',
                                 'Cobertura', 'Instalação telhas'}, (
            f'materialização da v1 gerou {sorted(por_nome)}')
        raiz_cob = por_nome['Cobertura']
        folha_cob = por_nome['Instalação telhas']
        assert folha_cob.tarefa_pai_id == raiz_cob.id

        # Filho criado À MÃO sob a raiz suprimida (sem vínculo com proposta):
        # só a cascata por tarefa_pai_id o alcança.
        manual = TarefaCronograma(
            obra_id=obra_id, admin_id=admin_id, is_cliente=False,
            nome_tarefa='Reforço manual da cobertura', duracao_dias=1,
            data_inicio=date(2026, 2, 1), tarefa_pai_id=raiz_cob.id,
            ordem=9990, responsavel='empresa')
        # Apontamento de RDO REAL na tarefa que será suprimida — o ponto do
        # D3 inteiro: ele tem de sobreviver ao aditivo.
        rdo = RDO(numero_rdo=f'RDO-T9-{uuid.uuid4().hex[:8]}',
                  data_relatorio=date(2026, 2, 2), obra_id=obra_id,
                  admin_id=admin_id)
        db.session.add_all([manual, rdo])
        db.session.flush()
        apontamento = RDOApontamentoCronograma(
            rdo_id=rdo.id, tarefa_cronograma_id=folha_cob.id,
            quantidade_executada_dia=1.0, quantidade_acumulada=1.0,
            percentual_realizado=25.0, admin_id=admin_id)
        db.session.add(apontamento)
        db.session.commit()
        ids_v1 = {t.id for t in tarefas} | {manual.id}
        apontamento_id, manual_id = apontamento.id, manual.id
        raiz_cob_id, folha_cob_id = raiz_cob.id, folha_cob.id

        # v2 = clone real (linhagem via proposta_item_origem_id): mantém a
        # Estrutura (valor ALTERADO — no-op no cronograma), suprime a
        # Cobertura e acrescenta a Pintura.
        v2 = Proposta(
            admin_id=admin_id, numero=f'{v1.numero}-v2', titulo=v1.titulo,
            cliente_id=v1.cliente_id, cliente_nome=v1.cliente_nome,
            valor_total=Decimal('160000.00'), status='rascunho',
            versao=2, proposta_origem_id=v1.id, obra_id=v1.obra_id)
        db.session.add(v2)
        db.session.flush()
        it_estrutura_v2 = PropostaItem(
            proposta_id=v2.id, admin_id=admin_id, item_numero=1,
            proposta_item_origem_id=itens_v1[1].id,
            descricao='Estrutura metálica', quantidade=Decimal('1'),
            unidade='vb', preco_unitario=Decimal('120000.00'),
            subtotal=Decimal('120000.00'))
        it_pintura_v2 = PropostaItem(
            proposta_id=v2.id, admin_id=admin_id, item_numero=3,
            descricao='Pintura', quantidade=Decimal('1'), unidade='vb',
            preco_unitario=Decimal('40000.00'), subtotal=Decimal('40000.00'))
        db.session.add_all([it_estrutura_v2, it_pintura_v2])
        db.session.flush()
        v2.cronograma_default_json = [
            _no_snapshot(it_estrutura_v2.id, 'Estrutura metálica',
                         ['Montagem estrutura']),
            _no_snapshot(it_pintura_v2.id, 'Pintura', ['Pintura final']),
        ]
        db.session.commit()
        _aprovar(v2, admin_id)

        db.session.expire_all()
        tarefas_v2 = _tarefas_da_obra(obra_id, admin_id)
        ids_v2 = {t.id for t in tarefas_v2}
        assert ids_v1 <= ids_v2, (
            f'tarefas apagadas pelo aditivo: {sorted(ids_v1 - ids_v2)} — '
            'nunca DELETE, só ativa=False')

        por_id = {t.id: t for t in tarefas_v2}
        # 2º serviço (suprimido): raiz + folha + filho manual arquivados.
        for tid, rotulo in [(raiz_cob_id, 'raiz Cobertura'),
                            (folha_cob_id, 'folha Instalação telhas'),
                            (manual_id, 'filho manual (cascata)')]:
            t = por_id[tid]
            assert t.ativa is False, (
                f'{rotulo} (id={tid}) continua ativa=True — item suprimido '
                'no aditivo tem de arquivar a tarefa')
            assert t.arquivada_em is not None, (
                f'{rotulo} arquivada sem carimbo arquivada_em')

        # 1º serviço (alterado de valor): no-op — intacto e ativo, sem
        # duplicata por nome.
        vivas = [t for t in tarefas_v2 if t.ativa]
        nomes_vivos = sorted(t.nome_tarefa for t in vivas)
        assert nomes_vivos == ['Estrutura metálica', 'Montagem estrutura',
                               'Pintura', 'Pintura final'], (
            f'cronograma vivo esperado com 4 tarefas, achou {nomes_vivos}')

        # 3º serviço (novo): criado pela idempotência existente.
        assert 'Pintura final' in {t.nome_tarefa for t in vivas}

        # Apontamento de RDO sobrevive apontando para a MESMA tarefa.
        ap = db.session.get(RDOApontamentoCronograma, apontamento_id)
        assert ap is not None, (
            'apontamento de RDO apagado — o aditivo destruiu histórico')
        assert ap.tarefa_cronograma_id == folha_cob_id

        # Ruling 5: aditivo não é versão inicial de cronograma — a única
        # CronogramaVersao segue sendo a nº1 da materialização da v1.
        versoes = CronogramaVersao.query.filter_by(obra_id=obra_id).all()
        assert [v.numero for v in versoes] == [1], (
            f'aditivo criou CronogramaVersao extra: {[v.numero for v in versoes]}')


@pytest.mark.integration
def test_reaprovar_v2_nao_rearquiva_nem_toca_tarefas_ja_arquivadas():
    """Idempotência: reaprovar a mesma v2 (mesmo emit) não re-arquiva nada —
    o carimbo `arquivada_em` das tarefas suprimidas não muda e o cronograma
    vivo fica igual."""
    from models import PropostaItem
    with app.app_context():
        admin, _cliente, v1 = _ambiente()
        admin_id = admin.id
        _segundo_item(v1, admin_id)
        itens_v1 = {i.item_numero: i for i in PropostaItem.query.filter_by(
            proposta_id=v1.id).all()}
        v1.cronograma_default_json = [
            _no_snapshot(itens_v1[1].id, 'Estrutura metálica',
                         ['Montagem estrutura']),
            _no_snapshot(itens_v1[2].id, 'Cobertura', ['Instalação telhas']),
        ]
        db.session.commit()
        _aprovar(v1, admin_id)
        obra_id = _obras_do_tenant(admin_id)[0].id

        v2 = _clonar_como_revisao(v1, admin_id, herdar_obra=True)  # só item 1
        _aprovar(v2, admin_id)

        db.session.expire_all()
        arquivadas = [t for t in _tarefas_da_obra(obra_id, admin_id)
                      if not t.ativa]
        assert sorted(t.nome_tarefa for t in arquivadas) == [
            'Cobertura', 'Instalação telhas']
        carimbos = {t.id: t.arquivada_em for t in arquivadas}

        _aprovar(v2, admin_id)  # reaprovação (mesmo caminho do emit)
        db.session.expire_all()
        depois = {t.id: t.arquivada_em
                  for t in _tarefas_da_obra(obra_id, admin_id) if not t.ativa}
        assert depois == carimbos, (
            'reaprovar a v2 re-arquivou tarefas (carimbo mudou) — a '
            'supressão tem de ser idempotente')


@pytest.mark.integration
def test_v3_reinclui_item_suprimido_e_reativa_as_tarefas_arquivadas():
    """A assimetria que a Task 9 criou, e que a Task 7 já resolvia do seu lado.

    A Task 7 decidiu que SUPRIMIDO descreve o escopo VIGENTE e não é lápide:
    re-incluir o item numa versão posterior devolve o IMC a PENDENTE. Depois
    da Task 9, o cronograma passou a ser arquivado junto na supressão — mas
    nada o desarquivava na volta. O contrato dizia "o serviço está de volta" e
    o cronograma vivo continuava sem ele, em silêncio.

    Antes da Task 9 esse buraco não existia (a supressão não mexia em tarefa),
    então ele é defeito DELA, não pedido novo.
    """
    from models import Proposta, PropostaItem, TarefaCronograma
    from models import ItemMedicaoComercial
    with app.app_context():
        admin, _cliente, v1 = _ambiente()
        admin_id = admin.id
        _segundo_item(v1, admin_id)
        itens_v1 = {i.item_numero: i for i in PropostaItem.query.filter_by(
            proposta_id=v1.id).all()}
        v1.cronograma_default_json = [
            _no_snapshot(itens_v1[1].id, 'Estrutura metálica',
                         ['Montagem estrutura']),
            _no_snapshot(itens_v1[2].id, 'Cobertura', ['Instalação telhas']),
        ]
        db.session.commit()
        _aprovar(v1, admin_id)

        obra_id = _obras_do_tenant(admin_id)[0].id
        por_nome = {t.nome_tarefa: t
                    for t in _tarefas_da_obra(obra_id, admin_id)}
        raiz_cob_id = por_nome['Cobertura'].id
        folha_cob_id = por_nome['Instalação telhas'].id

        # Filho à mão: a cascata da supressão o arquiva, e a volta tem de
        # trazê-lo junto — senão o serviço reaparece sem as subtarefas.
        manual = TarefaCronograma(
            obra_id=obra_id, admin_id=admin_id, is_cliente=False,
            nome_tarefa='Reforço manual da cobertura', duracao_dias=1,
            data_inicio=date(2026, 2, 1), tarefa_pai_id=raiz_cob_id,
            ordem=9990, responsavel='empresa')
        db.session.add(manual)
        db.session.commit()
        manual_id = manual.id

        # v2 SUPRIME a Cobertura (ela some da lista de itens).
        v2 = Proposta(
            admin_id=admin_id, numero=f'{v1.numero}-v2', titulo=v1.titulo,
            cliente_id=v1.cliente_id, cliente_nome=v1.cliente_nome,
            valor_total=Decimal('100000.00'), status='rascunho',
            versao=2, proposta_origem_id=v1.id, obra_id=v1.obra_id)
        db.session.add(v2)
        db.session.flush()
        it_estrutura_v2 = PropostaItem(
            proposta_id=v2.id, admin_id=admin_id, item_numero=1,
            proposta_item_origem_id=itens_v1[1].id,
            descricao='Estrutura metálica', quantidade=Decimal('1'),
            unidade='vb', preco_unitario=Decimal('100000.00'),
            subtotal=Decimal('100000.00'))
        db.session.add(it_estrutura_v2)
        db.session.commit()
        _aprovar(v2, admin_id)

        db.session.expire_all()
        por_id = {t.id: t for t in _tarefas_da_obra(obra_id, admin_id)}
        assert por_id[raiz_cob_id].ativa is False, 'pré-condição: v2 arquivou'
        assert por_id[manual_id].ativa is False, 'pré-condição: cascata'

        # v3 RE-INCLUI a Cobertura, com linhagem apontando para a v1.
        v3 = Proposta(
            admin_id=admin_id, numero=f'{v1.numero}-v3', titulo=v1.titulo,
            cliente_id=v1.cliente_id, cliente_nome=v1.cliente_nome,
            valor_total=Decimal('135000.00'), status='rascunho',
            versao=3, proposta_origem_id=v2.id, obra_id=v1.obra_id)
        db.session.add(v3)
        db.session.flush()
        db.session.add_all([
            PropostaItem(
                proposta_id=v3.id, admin_id=admin_id, item_numero=1,
                proposta_item_origem_id=it_estrutura_v2.id,
                descricao='Estrutura metálica', quantidade=Decimal('1'),
                unidade='vb', preco_unitario=Decimal('100000.00'),
                subtotal=Decimal('100000.00')),
            PropostaItem(
                proposta_id=v3.id, admin_id=admin_id, item_numero=2,
                proposta_item_origem_id=itens_v1[2].id,   # volta a Cobertura
                descricao='Cobertura', quantidade=Decimal('1'),
                unidade='vb', preco_unitario=Decimal('35000.00'),
                subtotal=Decimal('35000.00')),
        ])
        db.session.commit()
        _aprovar(v3, admin_id)

        db.session.expire_all()
        # A Task 7 já devolve o IMC — é a pré-condição do que se cobra abaixo.
        imc = ItemMedicaoComercial.query.filter_by(
            obra_id=obra_id, admin_id=admin_id, nome='Cobertura').first()
        assert imc is not None and imc.status != 'SUPRIMIDO', (
            'pré-condição: a Task 7 devolve o IMC a PENDENTE na re-inclusão')

        por_id = {t.id: t for t in _tarefas_da_obra(obra_id, admin_id)}
        for tid, rotulo in [(raiz_cob_id, 'raiz Cobertura'),
                            (folha_cob_id, 'folha Instalação telhas'),
                            (manual_id, 'filho manual (cascata)')]:
            t = por_id[tid]
            assert t.ativa is True, (
                f'{rotulo} (id={tid}) continua arquivada — o item voltou ao '
                'escopo e o cronograma vivo não acompanhou')
            assert t.arquivada_em is None, (
                f'{rotulo} reativada mas com carimbo arquivada_em pendurado')

        # E sem duplicar: a re-inclusão reusa a tarefa, não cria outra.
        vivas = [t for t in por_id.values() if t.ativa]
        nomes = sorted(t.nome_tarefa for t in vivas)
        assert nomes.count('Cobertura') == 1, (
            f're-inclusão duplicou a raiz: {nomes}')


# ═══════════════════════════════════════════════════════════════════════════
# Task 13 — a porta HTTP: extrato de contrato e ciclo do aditivo
# ═══════════════════════════════════════════════════════════════════════════

def _cliente_de(user_id):
    c = app.test_client()
    with c.session_transaction() as sess:
        sess['_user_id'] = str(user_id)
        sess['_fresh'] = True
    return c


def _obra_com_contrato():
    """Admin + obra com contrato vigente (v1). Devolve ids, fora do contexto."""
    from services.contrato_obra import ORIGEM_CADASTRO, definir_valor_contrato
    with app.app_context():
        suf = uuid.uuid4().hex[:10]
        admin = Usuario(
            username=f'adt_{suf}', email=f'adt_{suf}@test.local',
            nome='Aditivo Fase 6',
            password_hash=generate_password_hash('Senha@2026'),
            tipo_usuario=TipoUsuario.ADMIN, ativo=True, versao_sistema='v2')
        db.session.add(admin)
        db.session.flush()
        cli = Cliente(admin_id=admin.id, nome=f'Cli {suf}',
                      email=f'cli_{suf}@test.local', telefone='11999998888')
        db.session.add(cli)
        db.session.flush()
        obra = Obra(nome=f'Obra Aditivo {suf}', codigo=f'ADT-{suf}',
                    admin_id=admin.id, cliente_id=cli.id,
                    status='Em andamento', data_inicio=date(2026, 1, 10))
        db.session.add(obra)
        db.session.flush()
        definir_valor_contrato(obra, 100000.0, ORIGEM_CADASTRO,
                               motivo='contrato original')
        db.session.commit()
        return {'admin_id': admin.id, 'obra_id': obra.id}


def test_extrato_de_contrato_mostra_versao_vigente():
    ctx = _obra_com_contrato()
    r = _cliente_de(ctx['admin_id']).get(f"/obras/{ctx['obra_id']}/aditivos")
    assert r.status_code == 200, f'extrato não renderizou ({r.status_code})'
    html = r.get_data(as_text=True)
    assert 'Contrato e aditivos' in html
    assert '100.000,00' in html or '100000,00' in html, (
        'o extrato não mostra o valor vigente do contrato')


def test_ciclo_completo_do_aditivo_pela_porta_http():
    """Abrir em rascunho, ver no extrato, aprovar e o contrato mudar.

    É o caminho que a fase inteira existe para oferecer — até a Task 12 tudo
    isso só era alcançável por serviço, ou seja, por ninguém.
    """
    ctx = _obra_com_contrato()
    c = _cliente_de(ctx['admin_id'])

    r = c.post(f"/obras/{ctx['obra_id']}/aditivos/novo", data={
        'tipo': 'acrescimo', 'valor_novo': '130000,00',
        'motivo': 'ampliação da cobertura pedida pelo cliente',
    }, follow_redirects=False)
    assert r.status_code in (302, 303), f'abrir aditivo falhou ({r.status_code})'

    with app.app_context():
        adt = AditivoContrato.query.filter_by(obra_id=ctx['obra_id']).one()
        assert adt.status == 'rascunho', (
            'aditivo tem de nascer em rascunho — aprovar é outro clique')
        assert float(adt.valor_anterior) == 100000.0
        assert float(adt.valor_novo) == 130000.0
        aid = adt.id

    r = c.post(f"/obras/{ctx['obra_id']}/aditivos/{aid}/aprovar",
               follow_redirects=False)
    assert r.status_code in (302, 303)

    with app.app_context():
        adt = db.session.get(AditivoContrato, aid)
        assert adt.status == 'aprovado'
        vigente = (ObraContratoVersao.query
                   .filter_by(obra_id=ctx['obra_id'], vigente_ate=None).one())
        assert float(vigente.valor) == 130000.0, (
            'aprovar tem de abrir a versão seguinte do contrato')
        assert vigente.versao == 2
        assert vigente.aditivo_id == aid, (
            'a versão nova tem de apontar para o aditivo que a abriu')


def test_quem_nao_e_gestor_da_obra_nao_aprova_aditivo():
    """Aprovar mexe no baseline: exige GESTOR.

    O plano pedia 403; a resposta é **404**, e de propósito — é a escolha já
    travada em `tests/test_cronograma_permissoes.py`, para não vazar a
    existência de obra que o usuário não alcança. O decorator `obra_required`
    da Fase 1 é quem aplica isso.
    """
    from models import PapelObra, UsuarioObra
    from scripts.flag_escopo_obra import definir_flag
    ctx = _obra_com_contrato()
    # A flag `escopo_obra_ativo` do tenant PRECISA estar ligada, senão
    # `papel_de_usuario_na_obra` devolve GESTOR para todo mundo do tenant
    # (utils/autorizacao.py, o `if not _escopo_ativo(tenant)`) e a guarda
    # colapsa. O colapso é conhecido, é igual ao do resto do app e foi aceito
    # no ruling de 23/07 — mas ele significa que ESTE teste só prova alguma
    # coisa com a flag ligada. Sem isto, ele passaria hoje por acidente e
    # deixaria de avisar no dia em que a autorização quebrasse.
    with app.app_context():
        definir_flag(ctx['admin_id'], True)
        db.session.commit()
    c = _cliente_de(ctx['admin_id'])
    c.post(f"/obras/{ctx['obra_id']}/aditivos/novo", data={
        'tipo': 'acrescimo', 'valor_novo': '130000,00', 'motivo': 'x'})

    with app.app_context():
        aid = AditivoContrato.query.filter_by(obra_id=ctx['obra_id']).one().id
        suf = uuid.uuid4().hex[:8]
        apontador = Usuario(
            username=f'apt_{suf}', email=f'apt_{suf}@test.local',
            nome='Apontador', password_hash=generate_password_hash('x'),
            tipo_usuario=TipoUsuario.FUNCIONARIO, ativo=True,
            versao_sistema='v2', admin_id=ctx['admin_id'])
        db.session.add(apontador)
        db.session.flush()
        db.session.add(UsuarioObra(
            usuario_id=apontador.id, obra_id=ctx['obra_id'],
            papel=PapelObra.APONTADOR, admin_id=ctx['admin_id'], ativo=True))
        db.session.commit()
        apontador_id = apontador.id

    ca = _cliente_de(apontador_id)
    r = ca.post(f"/obras/{ctx['obra_id']}/aditivos/{aid}/aprovar",
                follow_redirects=False)
    assert r.status_code == 404, (
        f'apontador conseguiu chegar em aprovar ({r.status_code}) — aprovar '
        'aditivo exige papel de gestor da obra')

    with app.app_context():
        assert db.session.get(AditivoContrato, aid).status == 'rascunho', (
            'o aditivo foi aprovado por quem não é gestor')


def test_cancelar_aditivo_aprovado_e_recusado_com_mensagem():
    """Aprovado já mexeu no baseline: desfazer exige aditivo em sentido
    contrário, nunca apagar história. A view traduz o erro do serviço em
    mensagem, em vez de estourar 500."""
    ctx = _obra_com_contrato()
    c = _cliente_de(ctx['admin_id'])
    c.post(f"/obras/{ctx['obra_id']}/aditivos/novo", data={
        'tipo': 'acrescimo', 'valor_novo': '130000,00', 'motivo': 'y'})
    with app.app_context():
        aid = AditivoContrato.query.filter_by(obra_id=ctx['obra_id']).one().id
    c.post(f"/obras/{ctx['obra_id']}/aditivos/{aid}/aprovar")

    r = c.post(f"/obras/{ctx['obra_id']}/aditivos/{aid}/cancelar",
               follow_redirects=True)
    assert r.status_code == 200, 'cancelar aprovado devolveu erro cru'
    with app.app_context():
        assert db.session.get(AditivoContrato, aid).status == 'aprovado', (
            'cancelar desfez um aditivo que já produziu efeito')


def test_obra_de_outro_tenant_devolve_404_no_extrato():
    ctx = _obra_com_contrato()
    with app.app_context():
        suf = uuid.uuid4().hex[:8]
        outro = Usuario(
            username=f'out_{suf}', email=f'out_{suf}@test.local',
            nome='Outro', password_hash=generate_password_hash('x'),
            tipo_usuario=TipoUsuario.ADMIN, ativo=True, versao_sistema='v2')
        db.session.add(outro)
        db.session.commit()
        outro_id = outro.id
    r = _cliente_de(outro_id).get(f"/obras/{ctx['obra_id']}/aditivos")
    assert r.status_code == 404, (
        f'tenant alheio alcançou o extrato de contrato ({r.status_code})')
