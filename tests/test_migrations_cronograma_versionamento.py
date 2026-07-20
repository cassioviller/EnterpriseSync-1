"""Módulo 02 — schema do versionamento de cronograma (migrations 207-210).

Cobre: existência de tabelas/colunas/índices, idempotência de reexecução
e backfill (versão nº1 + tipo_apontamento). Padrão de asserts de schema:
test_medicao_contrato_schema_existe (tests/test_importacao_fisico_financeiro.py).
"""
import pytest
from sqlalchemy import text

from app import app, db

TABELAS_NOVAS = [
    'cronograma_importacao',
    'cronograma_versao',
    'cronograma_tarefa_snapshot',
    'cronograma_tarefa_mapeamento',
    'cronograma_importacao_evento',
]

COLUNAS_TAREFA = ['mpp_uid', 'wbs_codigo', 'fingerprint', 'is_marco',
                  'ativa', 'arquivada_em', 'versao_criacao_id']

COLUNAS_APONTAMENTO = ['tipo_apontamento', 'percentual_acumulado',
                       'percentual_incremento_dia',
                       'quantidade_total_snapshot', 'unidade_snapshot']


def _tem_tabela(nome):
    with db.engine.connect() as conn:
        return conn.execute(text(
            "SELECT EXISTS (SELECT FROM information_schema.tables "
            "WHERE table_name = :t)"), {'t': nome}).scalar()


def _colunas(tabela):
    with db.engine.connect() as conn:
        rows = conn.execute(text(
            "SELECT column_name FROM information_schema.columns "
            "WHERE table_name = :t"), {'t': tabela}).fetchall()
    return {r[0] for r in rows}


def test_tabelas_novas_existem():
    with app.app_context():
        faltando = [t for t in TABELAS_NOVAS if not _tem_tabela(t)]
        assert not faltando, f'tabelas ausentes: {faltando}'


def test_colunas_novas_tarefa_cronograma():
    with app.app_context():
        cols = _colunas('tarefa_cronograma')
        faltando = [c for c in COLUNAS_TAREFA if c not in cols]
        assert not faltando, f'colunas ausentes em tarefa_cronograma: {faltando}'


def test_colunas_novas_rdo_apontamento():
    with app.app_context():
        cols = _colunas('rdo_apontamento_cronograma')
        faltando = [c for c in COLUNAS_APONTAMENTO if c not in cols]
        assert not faltando, f'colunas ausentes em rdo_apontamento_cronograma: {faltando}'


def test_unique_uma_versao_ativa_por_obra():
    """Índice parcial: no máximo 1 cronograma_versao ativa por obra."""
    with app.app_context():
        with db.engine.connect() as conn:
            idx = conn.execute(text(
                "SELECT indexdef FROM pg_indexes "
                "WHERE tablename = 'cronograma_versao' "
                "AND indexdef ILIKE '%%status%%ativa%%'")).fetchall()
        assert idx, 'índice parcial WHERE status=ativa não existe'


def test_reexecucao_das_migracoes_e_noop():
    """run_migration_safe pula por migration_history; e o DDL em si é
    idempotente (IF NOT EXISTS) — as funções podem rodar de novo sem erro."""
    from migrations import (_migration_207_cronograma_versionamento,
                            _migration_208_tarefa_cronograma_identidade,
                            _migration_209_rdo_apontamento_semantico)
    with app.app_context():
        _migration_207_cronograma_versionamento()
        _migration_208_tarefa_cronograma_identidade()
        _migration_209_rdo_apontamento_semantico()


# ─────────────────────────────────────────────────────────────────────────────
# Migration 210 — backfill (versão nº1 + snapshots + tipo_apontamento).
# Fixture no padrão dos testes de importação (tests/test_importacao_fisico_
# financeiro.py): admin novo + importar_fisico_financeiro(baias) e, depois,
# limpeza do estado pós-migração para simular o banco PRÉ-210 — tudo filtrado
# por admin_id/obra_id próprios (nunca toca dados de outros admins).
# ─────────────────────────────────────────────────────────────────────────────
import json
import os
from datetime import datetime

from werkzeug.security import generate_password_hash


def _suffix() -> str:
    # Padrão de tests/test_caracterizacao_apontamento_cronograma.py:60
    return datetime.utcnow().strftime('%Y%m%d%H%M%S%f')


def _carregar_json():
    caminho = os.path.join(os.path.dirname(__file__), 'fixtures',
                           'cronograma_fisico_financeiro_baias.json')
    with open(caminho, encoding='utf-8') as f:
        return json.load(f)


def _novo_admin(prefixo: str) -> int:
    from models import Usuario, TipoUsuario
    suf = _suffix()
    u = Usuario(username=f'{prefixo}_{suf}',
                email=f'{prefixo}_{suf}@test.local',
                nome=f'Admin {prefixo} {suf}',
                password_hash=generate_password_hash('Senha@2026'),
                tipo_usuario=TipoUsuario.ADMIN)
    db.session.add(u)
    db.session.commit()
    return u.id


@pytest.fixture
def ambiente_baias(tmp_path):
    """Admin próprio + importação das baias + estado PRÉ-210 simulado:
    apaga versão/snapshots da obra criada e zera as colunas novas (209) dos
    apontamentos DESTE admin — os campos antigos ficam intactos."""
    from services import importacao_fisico_financeiro as ff
    app.config['TESTING'] = True
    # Isola FOTOS_RDO_BASE (padrão do _fotos_base_isolada dos testes de
    # importação) para não processar as fotos reais do repo.
    orig_fotos = ff.FOTOS_RDO_BASE
    vazio = tmp_path / '_fotos_vazio'
    vazio.mkdir(exist_ok=True)
    ff.FOTOS_RDO_BASE = str(vazio)
    try:
        with app.app_context():
            admin_id = _novo_admin('bkf210')
            res = ff.importar_fisico_financeiro(_carregar_json(), admin_id)
            obra_id = res['obra_id']
            with db.engine.begin() as conn:
                conn.execute(text(
                    "DELETE FROM cronograma_tarefa_snapshot WHERE versao_id IN "
                    "(SELECT id FROM cronograma_versao WHERE obra_id = :o)"),
                    {'o': obra_id})
                conn.execute(text(
                    "DELETE FROM cronograma_versao WHERE obra_id = :o"),
                    {'o': obra_id})
                conn.execute(text(
                    "UPDATE rdo_apontamento_cronograma SET "
                    "tipo_apontamento = NULL, percentual_acumulado = NULL, "
                    "percentual_incremento_dia = NULL, "
                    "quantidade_total_snapshot = NULL, unidade_snapshot = NULL "
                    "WHERE admin_id = :a"), {'a': admin_id})
            db.session.expire_all()
        yield {'admin_id': admin_id, 'obra_id': obra_id}
    finally:
        ff.FOTOS_RDO_BASE = orig_fotos


@pytest.mark.integration
def test_backfill_cria_versao_1_e_snapshots(ambiente_baias):
    """Obra com tarefas ganha versão nº1 ativa e 1 snapshot por tarefa."""
    from migrations import _migration_210_backfill_versao_inicial
    from models import CronogramaVersao, CronogramaTarefaSnapshot, TarefaCronograma
    with app.app_context():
        _migration_210_backfill_versao_inicial()
        obra_id = ambiente_baias['obra_id']
        admin_id = ambiente_baias['admin_id']
        v = CronogramaVersao.query.filter_by(obra_id=obra_id, status='ativa').one()
        assert v.numero == 1
        assert v.observacao == 'backfill inicial'
        n_tarefas = TarefaCronograma.query.filter_by(obra_id=obra_id, admin_id=admin_id).count()
        n_snaps = CronogramaTarefaSnapshot.query.filter_by(versao_id=v.id).count()
        assert n_snaps == n_tarefas


@pytest.mark.integration
def test_backfill_tipo_apontamento(ambiente_baias):
    """quantidade_total>0 → 'quantitativo'; senão 'percentual' com
    percentual_acumulado=percentual_realizado e incremento=quantidade_executada_dia
    (que no modo percentual guarda o incremento % — importacao_fisico_financeiro:521-532).
    Os campos ANTIGOS ficam byte a byte intactos (spec §13.2)."""
    from migrations import _migration_210_backfill_versao_inicial
    from models import RDOApontamentoCronograma, TarefaCronograma
    with app.app_context():
        admin_id = ambiente_baias['admin_id']
        sql_antigos = text(
            "SELECT id, quantidade_executada_dia, quantidade_acumulada, "
            "percentual_realizado FROM rdo_apontamento_cronograma "
            "WHERE admin_id = :a ORDER BY id LIMIT 3")
        with db.engine.connect() as conn:
            antes = [tuple(r) for r in
                     conn.execute(sql_antigos, {'a': admin_id}).fetchall()]
        assert len(antes) == 3, 'fixture deveria ter >= 3 apontamentos'

        _migration_210_backfill_versao_inicial()
        db.session.expire_all()

        with db.engine.connect() as conn:
            depois = [tuple(r) for r in
                      conn.execute(sql_antigos, {'a': admin_id}).fetchall()]
        assert antes == depois, 'backfill NÃO pode alterar os campos antigos'

        aps = (RDOApontamentoCronograma.query
               .join(TarefaCronograma,
                     TarefaCronograma.id == RDOApontamentoCronograma.tarefa_cronograma_id)
               .filter(RDOApontamentoCronograma.admin_id == admin_id)
               .all())
        assert aps, 'fixture sem apontamentos'
        vistos = set()
        for ap in aps:
            t = ap.tarefa
            if t.quantidade_total and t.quantidade_total > 0:
                assert ap.tipo_apontamento == 'quantitativo'
                assert ap.quantidade_total_snapshot == t.quantidade_total
                vistos.add('quantitativo')
            else:
                assert ap.tipo_apontamento == 'percentual'
                assert ap.percentual_acumulado == ap.percentual_realizado
                assert ap.percentual_incremento_dia == ap.quantidade_executada_dia
                vistos.add('percentual')
        # A fixture das baias exercita os DOIS modos (tarefa 14 = quantitativa)
        assert vistos == {'quantitativo', 'percentual'}


@pytest.mark.integration
def test_backfill_reexecucao_noop(ambiente_baias):
    """Rodar de novo não duplica versão nem snapshots."""
    from migrations import _migration_210_backfill_versao_inicial
    from models import CronogramaVersao
    with app.app_context():
        _migration_210_backfill_versao_inicial()
        _migration_210_backfill_versao_inicial()
        n = CronogramaVersao.query.filter_by(obra_id=ambiente_baias['obra_id']).count()
        assert n == 1


@pytest.mark.integration
def test_backfill_multitenant_admin_sem_tarefas(ambiente_baias):
    """Segundo admin sem tarefas: o backfill não cria versão nem snapshot
    para ele; a versão da obra das baias pertence ao admin da fixture."""
    from migrations import _migration_210_backfill_versao_inicial
    from models import CronogramaVersao, CronogramaTarefaSnapshot
    with app.app_context():
        admin2 = _novo_admin('bkf210_vazio')
        _migration_210_backfill_versao_inicial()
        assert CronogramaVersao.query.filter_by(admin_id=admin2).count() == 0
        assert CronogramaTarefaSnapshot.query.filter_by(admin_id=admin2).count() == 0
        v = CronogramaVersao.query.filter_by(obra_id=ambiente_baias['obra_id']).one()
        assert v.admin_id == ambiente_baias['admin_id']
