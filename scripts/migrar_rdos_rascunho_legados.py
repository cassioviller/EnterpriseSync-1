"""
scripts/migrar_rdos_rascunho_legados.py

Script avulso — substitui a antiga MIGRACAO 154 que rodava a cada boot.

Para cada RDO ainda em status='Rascunho', tenta aplicar o pipeline padrão
de finalização (status='Finalizado' + RDOCustoDiario + GestaoCustoFilho +
recálculo de produtividade).

Diferenças em relação à migração de boot:
  - NÃO levanta exceção em caso de falha — imprime relatório claro com a
    lista de RDOs que não puderam ser finalizados e o motivo (sem admin_id,
    funcionário sem cobertura, etc.) para revisão humana.
  - NÃO marca nada no migration_history — é trabalho de limpeza pontual.
  - Sem efeito no boot da aplicação.

Uso:
    python scripts/migrar_rdos_rascunho_legados.py
    python scripts/migrar_rdos_rascunho_legados.py --dry-run
    python scripts/migrar_rdos_rascunho_legados.py --only 66,204
"""
from __future__ import annotations

import argparse
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.chdir(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        '--dry-run', action='store_true',
        help='Apenas lista os RDOs Rascunho — não altera nada.',
    )
    parser.add_argument(
        '--only', default='',
        help='Lista CSV de IDs de RDO a processar (ex.: 66,204). '
             'Default: todos os Rascunho.',
    )
    args = parser.parse_args()

    only_ids: set[int] = set()
    if args.only.strip():
        try:
            only_ids = {int(x) for x in args.only.split(',') if x.strip()}
        except ValueError:
            print(f"ERRO: --only inválido: {args.only!r}", file=sys.stderr)
            return 2

    from app import app, db
    from models import RDO

    with app.app_context():
        q = RDO.query.filter(RDO.status == 'Rascunho')
        if only_ids:
            q = q.filter(RDO.id.in_(only_ids))
        rascunhos = q.order_by(RDO.id).all()

        total = len(rascunhos)
        if total == 0:
            print("Nenhum RDO em Rascunho — nada a fazer.")
            return 0

        print(f"\n{'='*70}")
        print(f"RDOs em Rascunho encontrados: {total}")
        if only_ids:
            print(f"Filtro --only: {sorted(only_ids)}")
        print('='*70)
        for r in rascunhos:
            print(f"  RDO id={r.id:>5} numero={getattr(r, 'numero_rdo', '?'):<20} "
                  f"obra_id={r.obra_id} data={r.data_relatorio} admin_id={r.admin_id}")

        if args.dry_run:
            print("\n[--dry-run] Nada foi alterado.")
            return 0

        from services.custo_funcionario_dia import gravar_custo_funcionario_rdo
        from services.rdo_custos import (
            gerar_custos_mao_obra_rdo,
            recalcular_produtividade_rdo,
            existe_ponto_no_dia,
        )
        from models import (
            RDOMaoObra, RDOCustoDiario, GestaoCustoFilho,
        )

        sucessos: list[int] = []
        falhas: list[tuple[int, str]] = []

        for rdo in rascunhos:
            rdo_id = rdo.id
            admin_id = rdo.admin_id or (rdo.obra.admin_id if rdo.obra else None)
            if not admin_id:
                falhas.append((rdo_id, "sem admin_id (RDO e obra sem tenant)"))
                continue

            # FASE 1: status + custo diário + produtividade
            rdo.status = 'Finalizado'
            db.session.add(rdo)
            try:
                recalcular_produtividade_rdo(rdo)
                gravar_custo_funcionario_rdo(rdo, admin_id)
            except Exception as e:
                db.session.rollback()
                falhas.append((rdo_id, f"fase 1 (custo diário) exceção: {e}"))
                continue

            db.session.expire_all()
            rdo_check = db.session.get(RDO, rdo_id)
            if rdo_check is None or rdo_check.status != 'Finalizado':
                falhas.append((rdo_id, "fase 1 fez rollback interno (status permaneceu Rascunho)"))
                continue

            # FASE 2: GestaoCustoFilho
            fase2_ok = True
            try:
                gerar_custos_mao_obra_rdo(rdo_check, admin_id)
            except Exception as e:
                fase2_ok = False
                falhas_motivo = f"fase 2 (gestao_custo_filho) exceção: {e}"

            if fase2_ok:
                # Verifica funcionários sem cobertura (mesma checagem da migração antiga)
                try:
                    mao_obras = RDOMaoObra.query.filter_by(rdo_id=rdo_id).all()
                    func_ids_com_horas = {
                        r.funcionario_id for r in mao_obras
                        if r.funcionario_id and float(r.horas_trabalhadas or 0) > 0
                    }
                    sem_cobertura: list[int] = []
                    for fid in func_ids_com_horas:
                        if existe_ponto_no_dia(fid, rdo_check.data_relatorio, admin_id):
                            continue
                        cd_ids = [
                            cd.id for cd in RDOCustoDiario.query.filter_by(
                                rdo_id=rdo_id, funcionario_id=fid
                            ).all()
                        ]
                        mo_ids = [m.id for m in mao_obras if m.funcionario_id == fid]
                        tem_filho = False
                        if cd_ids:
                            tem_filho = GestaoCustoFilho.query.filter(
                                GestaoCustoFilho.origem_tabela.in_([
                                    'rdo_custo_diario',
                                    'rdo_custo_diario_va',
                                    'rdo_custo_diario_vt',
                                ]),
                                GestaoCustoFilho.origem_id.in_(cd_ids),
                            ).first() is not None
                        if not tem_filho and mo_ids:
                            tem_filho = GestaoCustoFilho.query.filter(
                                GestaoCustoFilho.origem_tabela == 'rdo_mao_obra',
                                GestaoCustoFilho.origem_id.in_(mo_ids),
                            ).first() is not None
                        if not tem_filho:
                            sem_cobertura.append(fid)
                    if sem_cobertura:
                        fase2_ok = False
                        falhas_motivo = (
                            f"fase 2 silenciosa — funcionários sem GestaoCustoFilho "
                            f"nem ponto: {sem_cobertura}"
                        )
                except Exception as e:
                    print(f"  [WARN] RDO {rdo_id}: verificação pós-fase-2 falhou (não-bloqueante): {e}")

            if not fase2_ok:
                # Compensação: reverter status
                try:
                    db.session.rollback()
                    rdo_revert = db.session.get(RDO, rdo_id)
                    if rdo_revert and rdo_revert.status == 'Finalizado':
                        rdo_revert.status = 'Rascunho'
                        db.session.add(rdo_revert)
                        db.session.commit()
                except Exception as e:
                    db.session.rollback()
                    falhas.append((rdo_id, f"{falhas_motivo} + falha ao reverter: {e}"))
                    continue
                falhas.append((rdo_id, falhas_motivo))
                continue

            sucessos.append(rdo_id)

        # Relatório final
        print(f"\n{'='*70}")
        print("RELATÓRIO FINAL")
        print('='*70)
        print(f"Total processados : {total}")
        print(f"Sucessos          : {len(sucessos)}")
        print(f"Falhas            : {len(falhas)}")
        if sucessos:
            print(f"\nIDs finalizados com sucesso: {sucessos}")
        if falhas:
            print("\nRDOs que precisam de revisão humana:")
            for rid, motivo in falhas:
                print(f"  - RDO id={rid}: {motivo}")
            print("\nDica: corrija os dados (ex.: criar ponto eletrônico do funcionário")
            print("no dia, conferir admin_id da obra) e re-execute o script.")
        print('='*70)

        return 0 if not falhas else 1


if __name__ == '__main__':
    sys.exit(main())
