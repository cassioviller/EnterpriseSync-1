"""
scripts/migrar_operacional.py — Task #63

Script de migração retroativa: cria ObraOrcamentoOperacional para todas
as obras que já têm RDOs lançados mas ainda não possuem operacional.

Para obras sem orçamento original vinculado, cria operacional vazio com
aviso nos logs (pode ser preenchido manualmente pela tela de operacional).

Uso:
    python scripts/migrar_operacional.py [--dry-run]

Flags:
    --dry-run   Apenas mostra o que seria feito, sem gravar no banco.
"""
from __future__ import annotations

import logging
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s %(levelname)s %(message)s',
)
log = logging.getLogger('migrar_operacional')

DRY_RUN = '--dry-run' in sys.argv


def main() -> int:
    from app import app, db
    from models import Obra, RDO, ObraOrcamentoOperacional
    from services.orcamento_operacional import garantir_operacional

    with app.app_context():
        obras_com_rdo = (
            db.session.query(Obra)
            .join(RDO, RDO.obra_id == Obra.id)
            .distinct()
            .all()
        )
        log.info("Obras com RDO encontradas: %d", len(obras_com_rdo))

        criadas = 0
        ja_existiam = 0
        erros = 0

        for obra in obras_com_rdo:
            op = ObraOrcamentoOperacional.query.filter_by(obra_id=obra.id).first()
            if op:
                ja_existiam += 1
                log.debug("obra=%s já tem operacional id=%s — ignorado", obra.id, op.id)
                continue

            if DRY_RUN:
                log.info("[DRY-RUN] criaria operacional para obra=%s (%s)", obra.id, obra.nome)
                criadas += 1
                continue

            try:
                garantir_operacional(obra.id, criado_por_id=None)
                criadas += 1
                log.info("[OK] operacional criado para obra=%s (%s)", obra.id, obra.nome)
            except Exception as exc:
                erros += 1
                log.error("[ERRO] obra=%s (%s): %s", obra.id, obra.nome, exc)

        log.info("=" * 60)
        log.info(
            "Resultado: criados=%d  já_existiam=%d  erros=%d  dry_run=%s",
            criadas, ja_existiam, erros, DRY_RUN,
        )
        if DRY_RUN:
            log.info("Nada foi gravado (modo dry-run).")
        return erros


if __name__ == '__main__':
    sys.exit(main())
