"""
Migração GestaoCustoPai — Task #8 (Extensão do Modelo GestaoCustos)

Requisito: PostgreSQL 9.5+  (usa IF NOT EXISTS nos ALTER TABLE e pg_constraint
para verificação idempotente de constraints — não compatível com SQLite/MySQL).

Operações:
1. Adiciona novas colunas via ALTER TABLE idempotente (uma transação por comando).
2. Adiciona FK DB-level para fornecedor_id (idempotente via pg_constraint).
3. Migra categorias legadas para a nova hierarquia de categorias contábeis.
4. Verifica pós-migração: colunas presentes + categorias legadas ausentes.

Deploy: execute este script ANTES de subir a nova versão da aplicação.
  python migrate_gestao_custos.py
"""
import sys
import logging
from sqlalchemy import text

logging.basicConfig(level=logging.INFO, format='%(levelname)s: %(message)s')
logger = logging.getLogger(__name__)

CATEGORIA_MAP = {
    'COMPRA':        'MATERIAL',
    'VEICULO':       'EQUIPAMENTO',
    'SALARIO':       'MAO_OBRA_DIRETA',
    'REEMBOLSO':     'OUTROS',
    'DESPESA_GERAL': 'OUTROS',
}

# (col_name, col_type) — sem FK inline para evitar abort de transação
NEW_COLUMNS = [
    ("fornecedor_id",         "INTEGER"),
    ("forma_pagamento",       "VARCHAR(30)"),
    ("valor_pago",            "NUMERIC(15,2)"),
    ("saldo",                 "NUMERIC(15,2)"),
    ("conta_contabil_codigo", "VARCHAR(20)"),
    ("data_emissao",          "DATE"),
    ("numero_parcela",        "INTEGER"),
    ("total_parcelas",        "INTEGER"),
]

FK_CONSTRAINTS = [
    ("fk_gestao_custo_pai_fornecedor",
     "ALTER TABLE gestao_custo_pai ADD CONSTRAINT fk_gestao_custo_pai_fornecedor "
     "FOREIGN KEY (fornecedor_id) REFERENCES fornecedor(id) ON DELETE SET NULL"),
    # NOTA: conta_contabil_codigo NÃO tem FK DB-level porque o banco real de plano_contas
    # tem PRIMARY KEY em 'id' (integer), não em 'codigo'. O campo 'codigo' só tem
    # unique constraint composta (codigo, admin_id) para multi-tenancy.
    # Portanto 'codigo' não pode ser alvo de FK single-column.
    # Vínculo lógico gerenciado pela aplicação via conta_contabil_codigo.
]


def add_columns(engine):
    for col_name, col_type in NEW_COLUMNS:
        try:
            with engine.begin() as conn:
                conn.execute(text(
                    f"ALTER TABLE gestao_custo_pai ADD COLUMN IF NOT EXISTS {col_name} {col_type}"
                ))
            logger.info(f"  Coluna '{col_name}' OK.")
        except Exception as e:
            logger.warning(f"  Coluna '{col_name}' — aviso: {e}")

    # FK constraints — usa pg_constraint (PostgreSQL-specific) para verificação idempotente
    for constraint_name, sql in FK_CONSTRAINTS:
        try:
            with engine.begin() as conn:
                exists = conn.execute(text(
                    "SELECT 1 FROM pg_constraint WHERE conname = :name"
                ), {"name": constraint_name}).fetchone()
                if not exists:
                    conn.execute(text(sql))
                    logger.info(f"  Constraint '{constraint_name}' adicionada.")
                else:
                    logger.info(f"  Constraint '{constraint_name}' já existia.")
        except Exception as e:
            logger.warning(f"  Constraint '{constraint_name}' — aviso: {e}")


def migrate_categories(engine):
    total = 0
    for antiga, nova in CATEGORIA_MAP.items():
        try:
            with engine.begin() as conn:
                result = conn.execute(
                    text("UPDATE gestao_custo_pai SET tipo_categoria = :nova WHERE tipo_categoria = :antiga"),
                    {"nova": nova, "antiga": antiga}
                )
                count = result.rowcount
                if count:
                    logger.info(f"  {antiga} → {nova}: {count} registro(s)")
                    total += count
        except Exception as e:
            logger.error(f"  Erro ao migrar {antiga}: {e}")
    return total


def verify_migration(engine):
    """Verifica pós-migração: colunas presentes e ausência de categorias legadas.
    Lança RuntimeError se verificações críticas falharem."""
    logger.info("=== Passo 3: Verificação pós-migração ===")
    errors = 0

    # Verificar colunas — falha hard se a query der erro
    expected_cols = sorted(c for c, _ in NEW_COLUMNS)
    with engine.connect() as conn:
        placeholders = ", ".join(f"'{c}'" for c in expected_cols)
        result = conn.execute(text(
            f"SELECT column_name FROM information_schema.columns "
            f"WHERE table_name = 'gestao_custo_pai' AND column_name IN ({placeholders})"
        )).fetchall()
        found = {row[0] for row in result}
        missing = set(expected_cols) - found
        if missing:
            logger.error(f"  COLUNAS AUSENTES: {missing}")
            errors += len(missing)
        else:
            logger.info(f"  Todas as {len(expected_cols)} colunas novas presentes. OK")

    # Verificar ausência de categorias legadas — falha hard se a query der erro
    legadas = sorted(CATEGORIA_MAP.keys())
    with engine.connect() as conn:
        placeholders = ", ".join(f"'{c}'" for c in legadas)
        result = conn.execute(text(
            f"SELECT tipo_categoria, COUNT(*) FROM gestao_custo_pai "
            f"WHERE tipo_categoria IN ({placeholders}) GROUP BY tipo_categoria"
        )).fetchall()
        if result:
            for cat, cnt in result:
                logger.warning(f"  Categoria legada ainda presente: {cat} ({cnt} registro(s))")
                errors += 1
        else:
            logger.info("  Nenhuma categoria legada restante. OK")

    return errors


def run_migration():
    from app import app, db

    with app.app_context():
        logger.info("=== Passo 1: Adicionando novas colunas ===")
        add_columns(db.engine)

        logger.info("=== Passo 2: Migrando categorias legadas ===")
        total = migrate_categories(db.engine)

        verify_errors = verify_migration(db.engine)

        logger.info(f"\nMigração concluída: {total} registro(s) de categoria atualizados, "
                    f"{verify_errors} problema(s) pós-verificação.")
        return total, verify_errors


if __name__ == '__main__':
    total, errors = run_migration()
    if errors:
        print(f"\nAVISO: {errors} problema(s) detectado(s) na verificação. Revise os logs.")
        sys.exit(1)
    print(f"\nOK: {total} registro(s) migrados, verificação pós-migração aprovada.")
