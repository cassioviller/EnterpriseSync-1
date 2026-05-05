"""
jobs/cobertura_ociosa_mensalistas.py

Job de cobertura ociosa para mensalistas.

Executa idealmente no dia 1 de cada mês (referente ao mês anterior).
Para cada mensalista ativo do tenant, cria entradas `ocioso_mensal`
em RDOCustoDiario para dias úteis sem RDO no período.

Idempotente: não duplica se já houver lançamento no dia.

Uso:
    # Mês anterior (padrão)
    python jobs/cobertura_ociosa_mensalistas.py

    # Mês específico
    python jobs/cobertura_ociosa_mensalistas.py 2026 2

    # Tenant específico
    python jobs/cobertura_ociosa_mensalistas.py 2026 2 1
"""

import os
import sys
import logging
from datetime import date

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

logging.basicConfig(level=logging.INFO, format='%(levelname)s %(name)s: %(message)s')
logger = logging.getLogger('cobertura_ociosa')


def executar(ano: int, mes: int, admin_id: int | None = None) -> dict:
    """
    Cria dias ociosos para todos os mensalistas ativos do(s) tenant(s).

    Args:
        ano, mes   : período de referência (mês já encerrado)
        admin_id   : se None, processa todos os tenants ativos

    Returns dict {funcionario_id: dias_criados}
    """
    from app import app, db
    from models import Funcionario, Usuario, TipoUsuario
    from services.custo_funcionario_dia import gerar_dias_ociosos_mensalista

    resultado: dict[int, int] = {}

    with app.app_context():
        if admin_id:
            admins = [admin_id]
        else:
            admins = [
                u.id for u in Usuario.query.filter_by(
                    tipo_usuario=TipoUsuario.ADMIN, ativo=True
                ).all()
            ]

        for aid in admins:
            mensalistas = Funcionario.query.filter_by(
                admin_id=aid,
                ativo=True,
                tipo_remuneracao='salario',
            ).all()

            logger.info(
                "[cobertura] admin=%d %d/%d: %d mensalista(s)",
                aid, ano, mes, len(mensalistas),
            )

            for func in mensalistas:
                criados = gerar_dias_ociosos_mensalista(func.id, ano, mes, aid)
                resultado[func.id] = criados
                if criados:
                    logger.info(
                        "  func=%d (%s): %d dia(s) ocioso(s) criado(s)",
                        func.id, func.nome, criados,
                    )

            try:
                db.session.commit()
            except Exception:
                logger.exception("[cobertura] commit falhou para admin=%d", aid)
                db.session.rollback()

    return resultado


def _mes_anterior() -> tuple[int, int]:
    hoje = date.today()
    if hoje.month == 1:
        return hoje.year - 1, 12
    return hoje.year, hoje.month - 1


if __name__ == '__main__':
    args = sys.argv[1:]
    if len(args) >= 2:
        ano_ref = int(args[0])
        mes_ref = int(args[1])
    else:
        ano_ref, mes_ref = _mes_anterior()

    aid_ref = int(args[2]) if len(args) >= 3 else None

    logger.info("Iniciando cobertura ociosa %d/%d admin=%s", ano_ref, mes_ref, aid_ref or 'todos')
    res = executar(ano_ref, mes_ref, aid_ref)
    total = sum(res.values())
    logger.info("Concluído: %d funcionário(s) processado(s), %d dia(s) criado(s)", len(res), total)
