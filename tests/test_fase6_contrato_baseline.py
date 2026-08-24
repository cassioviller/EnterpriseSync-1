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
    """com_created_at=False simula uma obra pré-existente sem created_at.

    `Obra.created_at` tem `default=datetime.utcnow` (models.py) — um Python-side
    default do SQLAlchemy, que dispara sempre que o atributo está None NO FLUSH,
    inclusive quando é atribuído None explicitamente (não só quando nunca foi
    tocado). Por isso simplesmente deixar de setar `obra.created_at` não basta
    para simular NULL: o INSERT já sai com o timestamp do default. O NULL real
    só existe fazendo um UPDATE bruto depois do insert, direto na coluna (que é
    nullable no banco — `information_schema.columns.is_nullable = 'YES'` para
    `obra.created_at`).
    """
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
    if not com_created_at:
        from sqlalchemy import text as _text
        db.session.execute(_text('UPDATE obra SET created_at = NULL WHERE id = :id'),
                           {'id': obra.id})
        db.session.flush()
        db.session.expire(obra, ['created_at'])
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
def test_backfill_cai_para_data_inicio_quando_created_at_e_nulo():
    """2º elo do COALESCE: created_at NULL, data_inicio presente → vigente_de
    vira data_inicio (00:00:00, por causa do cast ::timestamp na migração)."""
    from migrations import _migration_271_obra_contrato_versao
    with app.app_context():
        admin = _novo_admin('f6cb_sem_ca')
        obra = _nova_obra(admin, com_created_at=False)
        db.session.commit()
        assert obra.created_at is None, (
            'fixture deveria ter deixado created_at NULL — sem isso o teste '
            'não exercita o 2º elo do COALESCE')

        _migration_271_obra_contrato_versao()

        v = ObraContratoVersao.query.filter_by(obra_id=obra.id).one()
        assert v.vigente_de == datetime.combine(obra.data_inicio, datetime.min.time())


@pytest.mark.integration
def test_backfill_coalesce_cai_para_now_quando_ambos_sao_nulos():
    """3º elo do COALESCE: created_at E data_inicio NULL → now().

    Não dá pra montar este cenário com uma obra REAL: `obra.data_inicio` é
    NOT NULL no banco (`information_schema.columns.is_nullable = 'NO'`,
    verificado — é uma constraint de verdade, não só `nullable=False` no
    modelo), então nenhuma obra chega a ter os dois campos NULL ao mesmo
    tempo. Alterar essa constraint só pra este teste mexeria numa tabela
    com ~129 mil linhas compartilhada com o resto da suíte — fora de escopo
    e arriscado.

    Em vez disso, o teste roda a MESMA expressão SQL da migração
    (migrations.py, `_migration_271_obra_contrato_versao`:
    `COALESCE(o.created_at, o.data_inicio::timestamp, now())`) com os dois
    primeiros operandos NULL, e prova que o resultado é um `now()` recente.
    Se a expressão da migração mudar, este teste precisa ser atualizado
    junto — é o acoplamento certo para travar o 3º elo do fallback.
    """
    from sqlalchemy import text as _text
    with app.app_context():
        antes = datetime.utcnow()
        # CAST externo pro tipo da coluna de destino real (`vigente_de
        # TIMESTAMP`, sem timezone) — é o mesmo cast implícito que o INSERT
        # da migração faz ao gravar o valor de COALESCE(...) na coluna.
        resultado = db.session.execute(_text(
            "SELECT CAST(COALESCE(CAST(NULL AS timestamp), CAST(NULL AS timestamp), now()) AS timestamp)"
        )).scalar()
        depois = datetime.utcnow()
        # now() do Postgres roda no servidor; folga de 5s absorve qualquer
        # deriva de relógio entre o processo de teste e o Postgres.
        margem = timedelta(seconds=5)
        assert antes - margem <= resultado <= depois + margem, (
            f'esperava um timestamp recente (entre {antes} e {depois}), '
            f'veio {resultado}')


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


# ---------------------------------------------------------------------------
# Task 2 — services/contrato_obra.py: leitura por vigência e o escritor
# único (`definir_valor_contrato`) abrindo/fechando `ObraContratoVersao`.
# ---------------------------------------------------------------------------

@pytest.mark.integration
def test_definir_valor_contrato_abre_primeira_versao_vigente(ambiente):
    """Obra sem nenhuma versão (estado pré-271): a 1ª chamada com valor
    diferente do atual abre a versão nº1, e obra.valor_contrato reflete a
    versão vigente — não um valor solto."""
    from services.contrato_obra import ORIGEM_CADASTRO, definir_valor_contrato
    with app.app_context():
        obra_id = ambiente['obra_id']
        obra = db.session.get(Obra, obra_id)
        assert ObraContratoVersao.query.filter_by(obra_id=obra_id).count() == 0

        definir_valor_contrato(obra, 150000.0, origem=ORIGEM_CADASTRO,
                               motivo='teste task2')
        db.session.commit()

        vigente = ObraContratoVersao.query.filter_by(
            obra_id=obra_id, vigente_ate=None).one()
        assert vigente.versao == 1
        assert vigente.valor == Decimal('150000.00')
        obra = db.session.get(Obra, obra_id)
        assert float(obra.valor_contrato) == 150000.0


@pytest.mark.integration
def test_definir_valor_contrato_com_valor_diferente_fecha_a_anterior_e_abre_nova(ambiente):
    """Uma 2ª chamada com valor diferente fecha a versão vigente (vigente_ate
    passa a existir) e abre a versão seguinte — a versão fechada nunca muda
    mais de valor."""
    from services.contrato_obra import ORIGEM_ADITIVO, definir_valor_contrato
    with app.app_context():
        obra_id = ambiente['obra_id']
        obra = db.session.get(Obra, obra_id)

        # `ambiente` já cria a obra com valor_contrato=100000.0 (sem
        # nenhuma versão por trás — estado pré-271/pré-Task 2). 80000.0
        # aqui é DIFERENTE desse valor de partida, para garantir que esta
        # 1ª chamada é uma mudança real e abre a versão nº1.
        definir_valor_contrato(obra, 80000.0, origem=ORIGEM_ADITIVO)
        db.session.commit()
        v1 = ObraContratoVersao.query.filter_by(obra_id=obra_id, versao=1).one()
        assert v1.vigente_ate is None
        valor_v1_antes = v1.valor

        obra = db.session.get(Obra, obra_id)
        definir_valor_contrato(obra, 120000.0, origem=ORIGEM_ADITIVO,
                               motivo='aditivo de teste')
        db.session.commit()

        db.session.expire_all()
        v1 = ObraContratoVersao.query.filter_by(obra_id=obra_id, versao=1).one()
        assert v1.vigente_ate is not None, 'a versão 1 deveria ter sido fechada'
        assert v1.valor == valor_v1_antes, (
            'versão fechada não pode mudar de valor')

        v2 = ObraContratoVersao.query.filter_by(
            obra_id=obra_id, vigente_ate=None).one()
        assert v2.versao == 2
        assert v2.valor == Decimal('120000.00')

        obra = db.session.get(Obra, obra_id)
        assert float(obra.valor_contrato) == 120000.0


@pytest.mark.integration
def test_definir_valor_contrato_com_mesmo_valor_nao_abre_nova_versao(ambiente):
    """Idempotência: gravar o MESMO valor da versão vigente não deve abrir
    uma versão por save — só uma mudança real de valor abre versão nova."""
    from services.contrato_obra import ORIGEM_EDICAO, definir_valor_contrato
    with app.app_context():
        obra_id = ambiente['obra_id']
        obra = db.session.get(Obra, obra_id)

        # 150000.0 difere do valor de partida da fixture (100000.0, sem
        # versão) — a 1ª chamada é uma mudança real e abre a versão nº1.
        definir_valor_contrato(obra, 150000.0, origem=ORIGEM_EDICAO)
        db.session.commit()
        total_apos_primeira = ObraContratoVersao.query.filter_by(obra_id=obra_id).count()
        assert total_apos_primeira == 1

        obra = db.session.get(Obra, obra_id)
        # mesmo valor de novo (edição que não mexeu no campo, por exemplo)
        definir_valor_contrato(obra, 150000.0, origem=ORIGEM_EDICAO,
                               motivo='reedição sem mudança de valor')
        db.session.commit()

        total_depois = ObraContratoVersao.query.filter_by(obra_id=obra_id).count()
        assert total_depois == 1, (
            f'valor igual ao vigente não deveria abrir versão nova — achei '
            f'{total_depois}')
        vigente = ObraContratoVersao.query.filter_by(
            obra_id=obra_id, vigente_ate=None).one()
        assert vigente.versao == 1


@pytest.mark.integration
def test_contrato_vigente_devolve_a_versao_sem_vigente_ate(ambiente):
    from services.contrato_obra import ORIGEM_CADASTRO, contrato_vigente, definir_valor_contrato
    with app.app_context():
        obra_id, admin_id = ambiente['obra_id'], ambiente['admin_id']
        obra = db.session.get(Obra, obra_id)

        assert contrato_vigente(obra_id, admin_id) is None, (
            'sem nenhuma versão ainda, contrato_vigente deve devolver None')

        # 150000.0 difere do valor de partida da fixture (100000.0, sem
        # versão) — garante que esta é uma mudança real.
        definir_valor_contrato(obra, 150000.0, origem=ORIGEM_CADASTRO)
        db.session.commit()

        v = contrato_vigente(obra_id, admin_id)
        assert v is not None
        assert v.vigente_ate is None
        assert v.valor == Decimal('150000.00')


@pytest.mark.integration
def test_valor_vigente_em_data_anterior_devolve_valor_antigo(ambiente):
    """`valor_vigente_em` com uma data ANTERIOR à troca devolve o valor da
    versão que estava em vigor naquele momento — não o valor atual."""
    from services.contrato_obra import (ORIGEM_ADITIVO,
                                        definir_valor_contrato,
                                        valor_vigente_em)
    with app.app_context():
        obra_id, admin_id = ambiente['obra_id'], ambiente['admin_id']
        obra = db.session.get(Obra, obra_id)

        t0 = datetime(2026, 1, 1, 12, 0, 0)
        # 150000.0 difere do valor de partida da fixture (100000.0, sem
        # versão) — garante que esta 1ª chamada é uma mudança real e abre
        # a versão nº1.
        definir_valor_contrato(obra, 150000.0, origem=ORIGEM_ADITIVO)
        v1 = ObraContratoVersao.query.filter_by(obra_id=obra_id, versao=1).one()
        v1.vigente_de = t0
        db.session.commit()

        t1 = datetime(2026, 3, 1, 12, 0, 0)
        obra = db.session.get(Obra, obra_id)
        definir_valor_contrato(obra, 120000.0, origem=ORIGEM_ADITIVO)
        v2 = ObraContratoVersao.query.filter_by(obra_id=obra_id, versao=2).one()
        v2.vigente_de = t1
        db.session.commit()

        antes_da_troca = datetime(2026, 2, 1)
        depois_da_troca = datetime(2026, 4, 1)

        assert valor_vigente_em(obra_id, admin_id, antes_da_troca) == Decimal('150000.00')
        assert valor_vigente_em(obra_id, admin_id, depois_da_troca) == Decimal('120000.00')


@pytest.mark.integration
def test_valor_contrato_da_obra_sempre_igual_a_versao_vigente_apos_varias_trocas(ambiente):
    """Invariante geral: depois de qualquer sequência de chamadas,
    obra.valor_contrato == valor da versão vigente (vigente_ate IS NULL)."""
    from services.contrato_obra import ORIGEM_EDICAO, definir_valor_contrato
    with app.app_context():
        obra_id = ambiente['obra_id']

        # 150000.0 é a 1ª mudança real vs. o valor de partida da fixture
        # (100000.0, sem versão); as demais repetições testam a
        # idempotência no meio da sequência.
        for valor in (150000.0, 150000.0, 130000.0, 130000.0, 90000.0):
            obra = db.session.get(Obra, obra_id)
            definir_valor_contrato(obra, valor, origem=ORIGEM_EDICAO)
            db.session.commit()

        obra = db.session.get(Obra, obra_id)
        vigente = ObraContratoVersao.query.filter_by(
            obra_id=obra_id, vigente_ate=None).one()
        assert Decimal(str(obra.valor_contrato)) == vigente.valor
        assert vigente.valor == Decimal('90000.00')
        # só houve 2 mudanças reais de valor (100k→130k, 130k→90k) além da
        # abertura inicial — 3 versões no total, não 5.
        assert ObraContratoVersao.query.filter_by(obra_id=obra_id).count() == 3


@pytest.mark.integration
def test_duas_chamadas_na_mesma_transacao_nao_duplicam_versao_vigente(ambiente):
    """Bug achado em revisão de código (24/08): 2 chamadas de
    definir_valor_contrato para a MESMA obra, na MESMA transação, SEM
    commit/flush entre elas. Antes da correção, o `no_autoflush` das
    consultas de `abrir_versao` escondia da 2ª chamada a versão que a 1ª
    tinha acabado de criar em memória — resultado: 2 linhas `versao=1`,
    ambas `vigente_ate=None`. A correção varre `db.session.new` por
    `ObraContratoVersao` pendentes desta obra e reconcilia contra elas."""
    from services.contrato_obra import ORIGEM_EDICAO, definir_valor_contrato
    with app.app_context():
        obra_id = ambiente['obra_id']
        obra = db.session.get(Obra, obra_id)

        # 150000.0 difere do valor de partida da fixture (100000.0, sem
        # versão) — a 1ª chamada abre a versão nº1. A 2ª, com um valor
        # diferente da 1ª, deveria fechar a nº1 e abrir a nº2 — tudo isso
        # SEM nenhum flush/commit no meio, o cenário exato do bug.
        definir_valor_contrato(obra, 150000.0, origem=ORIGEM_EDICAO)
        definir_valor_contrato(obra, 180000.0, origem=ORIGEM_EDICAO)
        db.session.commit()

        vigentes = ObraContratoVersao.query.filter_by(
            obra_id=obra_id, vigente_ate=None).all()
        assert len(vigentes) == 1, (
            f'esperava exatamente 1 versão vigente, achei {len(vigentes)} — '
            f'{[ (v.versao, v.valor) for v in vigentes ]}')
        assert vigentes[0].versao == 2
        assert vigentes[0].valor == Decimal('180000.00')

        todas = ObraContratoVersao.query.filter_by(obra_id=obra_id).order_by(
            ObraContratoVersao.versao).all()
        assert [v.versao for v in todas] == [1, 2], (
            f'esperava versões 1 e 2 (sem duplicata), achei '
            f'{[v.versao for v in todas]}')
        assert todas[0].vigente_ate is not None, (
            'a versão 1 deveria ter sido fechada pela 2ª chamada')
        assert todas[0].valor == Decimal('150000.00')

        obra = db.session.get(Obra, obra_id)
        assert float(obra.valor_contrato) == 180000.0


# ---------------------------------------------------------------------------
# Task 5 — fechar a edição livre de `valor_contrato`.
#
# O formulário de edição da obra era a última porta de reprecificação
# in-place: com versão vigente, o POST passa a IGNORAR o campo (mudança de
# valor é aditivo — Task 13); sem versão (obra manual, pré-baseline), a
# gravação abre a versão nº1 com origem_tipo='contrato_original' — sempre
# pelo escritor único. E o congelamento de `valor_base` das medições já
# recebidas sobe para DENTRO de `definir_valor_contrato` (mesmo movimento
# do repontamento na Task 4), alcançando as 5 portas — inclusive esta, que
# nunca congelou nada.
#
# Primeiros testes HTTP autenticados da fase: login por injeção de sessão
# (padrão de tests/test_fase0_autorizacao.py), nunca POST em /login.
# ---------------------------------------------------------------------------

@pytest.fixture(scope='module')
def _schema_fase6():
    """Schema das Tasks 1–4 no banco de teste (SIGE_BOOT_DDL=0 no boot).

    As três migrações são idempotentes — mesmo padrão do `_schema` de
    tests/test_fase6_aditivo.py."""
    from migrations import (_migration_271_obra_contrato_versao,
                            _migration_272_aditivo_contrato,
                            _migration_273_medicao_contrato_versionada)
    with app.app_context():
        _migration_271_obra_contrato_versao()
        _migration_272_aditivo_contrato()
        _migration_273_medicao_contrato_versionada()
    yield


def _cliente_http(user_id):
    """Test client autenticado por injeção de sessão (flask-login)."""
    c = app.test_client()
    with c.session_transaction() as sess:
        sess['_user_id'] = str(user_id)
        sess['_fresh'] = True
    return c


def _form_edicao(obra, **extra):
    """Campos mínimos para o POST de /obras/editar/<id> chegar ao commit.

    `cliente_id` do próprio tenant (obrigatório — sem ele a rota redireciona
    com flash de erro antes de salvar); `ativo` marcado para a obra não ser
    desativada de tabela; `codigo` presente para não ser regenerado."""
    dados = {
        'nome': obra.nome,
        'endereco': obra.endereco or '',
        'data_inicio': obra.data_inicio.strftime('%Y-%m-%d'),
        'codigo': obra.codigo,
        'cliente_id': str(obra.cliente_id),
        'ativo': '1',
    }
    dados.update(extra)
    return dados


@pytest.mark.integration
def test_post_edicao_com_baseline_nao_muda_valor_nem_cria_versao(
        ambiente, _schema_fase6):
    """Step 1 do brief: POST de edição com `valor_contrato` alterado numa
    obra COM versão vigente não muda o valor e não cria versão nova — a
    mudança de valor se faz por aditivo."""
    from services.contrato_obra import ORIGEM_PROPOSTA, definir_valor_contrato
    with app.app_context():
        obra_id, admin_id = ambiente['obra_id'], ambiente['admin_id']
        obra = db.session.get(Obra, obra_id)
        # abre o baseline (150000.0 difere dos 100000.0 da fixture — é
        # mudança real e abre a versão nº1)
        definir_valor_contrato(obra, 150000.0, origem=ORIGEM_PROPOSTA)
        db.session.commit()
        form = _form_edicao(obra, valor_contrato='999999')

    c = _cliente_http(admin_id)
    r = c.post(f'/obras/editar/{obra_id}', data=form, follow_redirects=False)
    assert r.status_code == 302, (
        f'o POST de edição deveria ter salvo e redirecionado — veio '
        f'{r.status_code}')

    with app.app_context():
        obra = db.session.get(Obra, obra_id)
        assert float(obra.valor_contrato) == 150000.0, (
            'obra com baseline: o formulário de edição NÃO pode mudar '
            f'valor_contrato — veio {obra.valor_contrato}')
        total = ObraContratoVersao.query.filter_by(obra_id=obra_id).count()
        assert total == 1, (
            f'o POST ignorado não pode ter aberto versão nova — achei {total}')
        vigente = ObraContratoVersao.query.filter_by(
            obra_id=obra_id, vigente_ate=None).one()
        assert vigente.valor == Decimal('150000.00')


@pytest.mark.integration
def test_post_edicao_sem_baseline_abre_versao_contrato_original(
        ambiente, _schema_fase6):
    """Obra sem nenhuma versão (criada à mão, pré-baseline): o campo segue
    editável, e a gravação abre a versão nº1 com
    origem_tipo='contrato_original' — assim toda obra acaba com baseline."""
    with app.app_context():
        obra_id, admin_id = ambiente['obra_id'], ambiente['admin_id']
        obra = db.session.get(Obra, obra_id)
        assert ObraContratoVersao.query.filter_by(obra_id=obra_id).count() == 0
        form = _form_edicao(obra, valor_contrato='250000')

    c = _cliente_http(admin_id)
    r = c.post(f'/obras/editar/{obra_id}', data=form, follow_redirects=False)
    assert r.status_code == 302, (
        f'o POST de edição deveria ter salvo e redirecionado — veio '
        f'{r.status_code}')

    with app.app_context():
        obra = db.session.get(Obra, obra_id)
        assert float(obra.valor_contrato) == 250000.0
        v = ObraContratoVersao.query.filter_by(obra_id=obra_id).one()
        assert v.versao == 1
        assert v.vigente_ate is None
        assert v.origem_tipo == 'contrato_original', (
            f"a versão aberta pela edição de obra sem baseline deve nascer "
            f"como 'contrato_original' — veio {v.origem_tipo!r}")
        assert v.valor == Decimal('250000.00')


@pytest.mark.integration
def test_definir_valor_contrato_congela_base_de_medicao_recebida(
        ambiente, _schema_fase6):
    """O congelamento de `valor_base` (Fase 0.6/D1c) sobe para DENTRO do
    escritor único: qualquer porta que mude o valor congela a medição JÁ
    RECEBIDA no valor ANTIGO do contrato, antes da escrita — sem isso a
    edição manual reprecificava retroativamente o que o cliente já pagou."""
    from models import MedicaoContrato
    from services.contrato_obra import ORIGEM_EDICAO, definir_valor_contrato
    with app.app_context():
        obra_id = ambiente['obra_id']
        obra = db.session.get(Obra, obra_id)  # valor_contrato=100000.0
        recebido = MedicaoContrato(
            obra_id=obra.id, admin_id=obra.admin_id, nome='Entrada',
            pct=Decimal('0.10'), recebido_no_mes='2026-02')
        futuro = MedicaoContrato(
            obra_id=obra.id, admin_id=obra.admin_id, nome='Entrega',
            pct=Decimal('0.90'))
        db.session.add_all([recebido, futuro])
        db.session.flush()
        recebido_id, futuro_id = recebido.id, futuro.id

        definir_valor_contrato(obra, 120000.0, origem=ORIGEM_EDICAO,
                               motivo='teste task5')
        db.session.commit()

        recebido = db.session.get(MedicaoContrato, recebido_id)
        futuro = db.session.get(MedicaoContrato, futuro_id)
        assert recebido.valor_base == Decimal('100000.00'), (
            'definir_valor_contrato tem de congelar valor_base da medição '
            'recebida com o valor ANTIGO do contrato antes de escrever o '
            f'novo — veio {recebido.valor_base}')
        assert futuro.valor_base is None, (
            'medição não recebida segue o contrato vigente — valor_base '
            f'deveria continuar NULL, veio {futuro.valor_base}')


@pytest.mark.integration
def test_form_edicao_trava_campo_e_linka_aditivos_quando_ha_vigente(
        ambiente, _schema_fase6):
    """GET do formulário de edição com contrato vigente: input travado
    (readonly + disabled), badge com a versão vigente e link para
    /obras/<id>/aditivos (href literal até a Task 13 criar a rota)."""
    import re as _re
    from services.contrato_obra import ORIGEM_PROPOSTA, definir_valor_contrato
    with app.app_context():
        obra_id, admin_id = ambiente['obra_id'], ambiente['admin_id']
        obra = db.session.get(Obra, obra_id)
        definir_valor_contrato(obra, 150000.0, origem=ORIGEM_PROPOSTA)
        db.session.commit()

    c = _cliente_http(admin_id)
    r = c.get(f'/obras/editar/{obra_id}')
    assert r.status_code == 200
    html = r.get_data(as_text=True)

    campo = _re.search(r'<input[^>]*name="valor_contrato"[^>]*>', html)
    assert campo is not None, 'o campo valor_contrato não pode ser removido'
    assert 'readonly' in campo.group(0) and 'disabled' in campo.group(0), (
        'com contrato vigente o input de valor_contrato deve estar '
        f'readonly + disabled — veio: {campo.group(0)}')
    assert f'/obras/{obra_id}/aditivos' in html, (
        'faltou o link para a tela de aditivos da obra')
    assert 'Contrato v1 vigente' in html, (
        'faltou o badge com a versão vigente do contrato')


@pytest.mark.integration
def test_form_edicao_mantem_campo_editavel_sem_vigente(ambiente, _schema_fase6):
    """Sem versão vigente o campo continua editável — é por ele que a obra
    manual ganha o baseline."""
    import re as _re
    with app.app_context():
        obra_id, admin_id = ambiente['obra_id'], ambiente['admin_id']

    c = _cliente_http(admin_id)
    r = c.get(f'/obras/editar/{obra_id}')
    assert r.status_code == 200
    html = r.get_data(as_text=True)

    campo = _re.search(r'<input[^>]*name="valor_contrato"[^>]*>', html)
    assert campo is not None
    assert 'readonly' not in campo.group(0) and 'disabled' not in campo.group(0), (
        f'sem contrato vigente o campo deve seguir editável — veio: '
        f'{campo.group(0)}')
