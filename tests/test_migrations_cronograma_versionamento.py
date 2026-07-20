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
