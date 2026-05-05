"""
scripts/migrar_custos_historicos.py

Script standalone de migração retroativa: percorre todos os RDOMaoObra
históricos e cria RDOCustoDiario com valores atuais do funcionário,
marcando `retroativo=True`.

Idempotente: pula RDOs cujas linhas já existem em RDOCustoDiario.

Uso:
    python scripts/migrar_custos_historicos.py

    # Apenas um tenant
    python scripts/migrar_custos_historicos.py 1

    # Tenant + limitar a N RDOs (para testes)
    python scripts/migrar_custos_historicos.py 1 50
"""

import os
import sys
import logging
from datetime import date

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

logging.basicConfig(level=logging.INFO, format='%(levelname)s %(name)s: %(message)s')
logger = logging.getLogger('migrar_custos')


def migrar(admin_id: int | None = None, limite_rdos: int | None = None) -> dict:
    """
    Migra RDOs históricos gerando RDOCustoDiario retroativos.

    Returns:
        {
          'rdos_processados': int,
          'linhas_criadas': int,
          'rdos_pulados': int,
          'erros': int,
        }
    """
    from app import app, db
    from models import RDO, RDOMaoObra, RDOCustoDiario, Funcionario, Obra
    from services.custo_funcionario_dia import calcular_custo_funcionario_no_rdo
    from sqlalchemy import func as sql_func

    stats = dict(rdos_processados=0, linhas_criadas=0, rdos_pulados=0, erros=0)

    with app.app_context():
        q = RDO.query.join(Obra, Obra.id == RDO.obra_id)
        if admin_id:
            q = q.filter(Obra.admin_id == admin_id)
        if limite_rdos:
            q = q.limit(limite_rdos)
        rdos = q.order_by(RDO.data_relatorio).all()

        logger.info("Iniciando migração: %d RDO(s) encontrado(s)", len(rdos))

        for rdo in rdos:
            try:
                linhas = RDOMaoObra.query.filter_by(rdo_id=rdo.id).all()
                if not linhas:
                    stats['rdos_pulados'] += 1
                    continue

                aid = rdo.admin_id or (rdo.obra.admin_id if rdo.obra else None)
                if not aid:
                    stats['rdos_pulados'] += 1
                    continue

                horas_rdo: dict[int, float] = {}
                extras_rdo: dict[int, float] = {}
                for linha in linhas:
                    fid = linha.funcionario_id
                    horas_rdo[fid] = horas_rdo.get(fid, 0.0) + float(linha.horas_trabalhadas or 0)
                    extras_rdo[fid] = extras_rdo.get(fid, 0.0) + float(linha.horas_extras or 0)

                data_ref = rdo.data_relatorio
                qualquer_criado = False

                for func_id, horas_no_rdo in horas_rdo.items():
                    existente = RDOCustoDiario.query.filter_by(
                        rdo_id=rdo.id,
                        funcionario_id=func_id,
                    ).first()
                    if existente:
                        continue

                    funcionario = Funcionario.query.filter_by(
                        id=func_id, admin_id=aid
                    ).first()
                    if not funcionario:
                        continue

                    total_horas_dia = db.session.query(
                        sql_func.coalesce(sql_func.sum(RDOMaoObra.horas_trabalhadas), 0)
                    ).join(RDO, RDO.id == RDOMaoObra.rdo_id).filter(
                        RDOMaoObra.funcionario_id == func_id,
                        RDO.data_relatorio == data_ref,
                        RDO.admin_id == aid,
                    ).scalar() or 0.0

                    horas_extras_no_rdo = extras_rdo.get(func_id, 0.0)

                    comp = calcular_custo_funcionario_no_rdo(
                        funcionario,
                        horas_no_rdo,
                        float(total_horas_dia),
                        horas_extras_no_rdo,
                        data_ref,
                    )

                    reg = RDOCustoDiario(
                        rdo_id=rdo.id,
                        funcionario_id=func_id,
                        admin_id=aid,
                        data=data_ref,
                        tipo_lancamento='rdo',
                        retroativo=True,
                        tipo_remuneracao_snapshot=comp['tipo_remuneracao_snapshot'],
                        componente_folha=comp['componente_folha'],
                        componente_va=comp['componente_va'],
                        componente_vt=comp['componente_vt'],
                        componente_extra=comp['componente_extra'],
                        custo_total_dia=comp['custo_total_dia'],
                        horas_normais=comp['horas_normais'],
                        horas_extras=comp['horas_extras'],
                        custo_hora_normal=comp['custo_hora_normal'],
                        dias_uteis_mes_referencia=comp.get('dias_uteis_mes_referencia'),
                    )
                    db.session.add(reg)
                    stats['linhas_criadas'] += 1
                    qualquer_criado = True

                db.session.flush()
                stats['rdos_processados'] += 1

                if stats['rdos_processados'] % 50 == 0:
                    db.session.commit()
                    logger.info(
                        "  ... %d RDOs | %d linhas criadas | %d erros",
                        stats['rdos_processados'],
                        stats['linhas_criadas'],
                        stats['erros'],
                    )

            except Exception:
                logger.exception("Erro no RDO %s", getattr(rdo, 'numero_rdo', rdo.id))
                db.session.rollback()
                stats['erros'] += 1

        try:
            db.session.commit()
        except Exception:
            logger.exception("Commit final falhou")
            db.session.rollback()

    logger.info(
        "Migração concluída: processados=%d criados=%d pulados=%d erros=%d",
        stats['rdos_processados'],
        stats['linhas_criadas'],
        stats['rdos_pulados'],
        stats['erros'],
    )
    return stats


if __name__ == '__main__':
    args = sys.argv[1:]
    aid = int(args[0]) if args else None
    lim = int(args[1]) if len(args) >= 2 else None
    migrar(aid, lim)
