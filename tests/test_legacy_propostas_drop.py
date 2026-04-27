"""Task #201 — aposentar modelo legado de propostas.

Smoke test: confirma que a Migration 141 dropou todas as tabelas
legadas, que `propostas_comerciais` segue intacta, e que o backup CSV
das 10 linhas de `proposta` foi gerado em `backups/`.
"""
import logging
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

logging.basicConfig(
    level=logging.INFO,
    format='%(levelname)s:%(name)s:%(message)s',
)
logger = logging.getLogger(__name__)

from app import app  # noqa: E402
from models import db  # noqa: E402
from sqlalchemy import text  # noqa: E402


LEGACY_TABLES = [
    'proposta',
    'proposta_servico',
    'item_servico_proposta',
    'item_servico_proposta_dinamica',
    'tabela_composicao_proposta',
    'historico_status_proposta',
    'item_proposta',
    'proposta_log',
]


def _table_exists(name: str) -> bool:
    sql = text(
        "SELECT EXISTS (SELECT 1 FROM information_schema.tables "
        "WHERE table_schema='public' AND table_name=:n)"
    )
    return bool(db.session.execute(sql, {'n': name}).scalar())


def _row_count(name: str) -> int:
    return int(db.session.execute(text(f"SELECT COUNT(*) FROM {name}")).scalar() or 0)


def main() -> int:
    passed = 0
    failed = 0

    def check(label: str, ok: bool, detail: str = ''):
        nonlocal passed, failed
        if ok:
            passed += 1
            logger.info("PASS: %s%s", label, f" ({detail})" if detail else '')
        else:
            failed += 1
            logger.error("FAIL: %s%s", label, f" ({detail})" if detail else '')

    with app.app_context():
        # 1. Nenhuma das 8 tabelas legadas deve existir mais
        for tbl in LEGACY_TABLES:
            existe = _table_exists(tbl)
            check(
                f"L.{tbl} dropada",
                not existe,
                f"existe={existe}",
            )

        # 2. propostas_comerciais (a tabela viva) deve continuar presente e populada
        check(
            "L.propostas_comerciais existe",
            _table_exists('propostas_comerciais'),
        )
        cnt = _row_count('propostas_comerciais')
        check(
            "L.propostas_comerciais populada",
            cnt > 0,
            f"linhas={cnt}",
        )

        # 3. Demais tabelas vivas do domínio de propostas devem seguir intactas
        for tbl in [
            'proposta_historico',
            'proposta_itens',
            'proposta_clausula',
            'proposta_template_clausula',
            'proposta_arquivos',
            'proposta_templates',
        ]:
            check(
                f"L.{tbl} viva e presente",
                _table_exists(tbl),
            )

        # 4. Migration 141 marcada como sucesso em migration_history
        result = db.session.execute(
            text(
                "SELECT status FROM migration_history "
                "WHERE migration_number = 141"
            )
        ).first()
        check(
            "L.migration_history #141 = success",
            result is not None and result[0] == 'success',
            f"row={result}",
        )

        # 5. Backup CSV de `proposta` existe e tem ao menos uma linha de dados
        backup_path = os.path.join(
            os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
            'backups',
            'legacy_proposta_2026-04-27.csv',
        )
        existe_backup = os.path.exists(backup_path)
        check("L.backup CSV de proposta presente", existe_backup, backup_path)
        if existe_backup:
            with open(backup_path, encoding='utf-8') as fh:
                linhas = fh.readlines()
            # cabeçalho + 10 linhas de dados = 11
            check(
                "L.backup CSV tem cabeçalho + dados",
                len(linhas) >= 2,
                f"linhas={len(linhas)}",
            )

    print("=" * 70)
    print(f"E2E Task #201 (E2E201-DROPLG) — {passed} PASS / {failed} FAIL")
    print("=" * 70)
    if failed:
        print(f"FALHA: {failed} assert(s) falharam.")
        return 1
    print("OK — modelo legado de propostas aposentado.")
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
