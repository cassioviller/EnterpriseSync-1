#!/usr/bin/env python3
"""Relatório de conformidade do destino do custo — SIGE Fase 4.

Este script é o GATE da migration 253/254. Enquanto ele reportar
`sem_destino > 0`, a constraint não deve ser validada: validar com linha
pendente derruba o boot da aplicação.

READ-ONLY. Não grava nada, em nenhuma circunstância.

Uso:
    python scripts/relatorio_destino_custo.py
    python scripts/relatorio_destino_custo.py --tenant 832
    python scripts/relatorio_destino_custo.py --amostra 50
"""
from __future__ import annotations

import argparse
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def conformidade(admin_id=None, limite_amostra=20):
    """Quantas linhas de custo continuam sem destino, e quais."""
    from sqlalchemy import text

    from app import db

    filtro = 'AND f.admin_id = :aid' if admin_id else ''
    params = {'aid': admin_id} if admin_id else {}

    total = db.session.execute(text(f"""
        SELECT count(*) FROM gestao_custo_filho f
        WHERE f.obra_id IS NULL AND f.centro_custo_id IS NULL {filtro}
    """), params).scalar() or 0

    valor = db.session.execute(text(f"""
        SELECT COALESCE(sum(f.valor), 0) FROM gestao_custo_filho f
        WHERE f.obra_id IS NULL AND f.centro_custo_id IS NULL {filtro}
    """), params).scalar() or 0

    por_origem = db.session.execute(text(f"""
        SELECT COALESCE(f.origem_tabela, '(sem origem)') AS origem, count(*) AS n
        FROM gestao_custo_filho f
        WHERE f.obra_id IS NULL AND f.centro_custo_id IS NULL {filtro}
        GROUP BY 1 ORDER BY n DESC
    """), params).fetchall()

    por_tenant = db.session.execute(text(f"""
        SELECT f.admin_id, count(*) AS n
        FROM gestao_custo_filho f
        WHERE f.obra_id IS NULL AND f.centro_custo_id IS NULL {filtro}
        GROUP BY 1 ORDER BY n DESC LIMIT 20
    """), params).fetchall()

    amostra = db.session.execute(text(f"""
        SELECT f.id, f.pai_id, f.admin_id, f.data_referencia, f.valor,
               COALESCE(f.origem_tabela, ''), LEFT(COALESCE(f.descricao, ''), 60)
        FROM gestao_custo_filho f
        WHERE f.obra_id IS NULL AND f.centro_custo_id IS NULL {filtro}
        ORDER BY f.valor DESC
        LIMIT :lim
    """), {**params, 'lim': limite_amostra}).fetchall()

    pais_sem_obra = db.session.execute(text("""
        SELECT count(*) FROM gestao_custo_pai p
        WHERE p.obra_id IS NULL
    """) if not admin_id else text("""
        SELECT count(*) FROM gestao_custo_pai p
        WHERE p.obra_id IS NULL AND p.admin_id = :aid
    """), params).scalar() or 0

    tenants_sem_centro = db.session.execute(text("""
        SELECT count(*) FROM usuario u
        WHERE u.tipo_usuario IN ('ADMIN', 'SUPER_ADMIN')
          AND NOT EXISTS (
              SELECT 1 FROM centro_custo c
              WHERE c.admin_id = u.id AND c.tipo = 'administrativo')
    """)).scalar() or 0

    return {
        'sem_destino': int(total),
        'valor_sem_destino': valor,
        'por_origem': [{'origem': o, 'n': n} for o, n in por_origem],
        'por_tenant': [{'admin_id': a, 'n': n} for a, n in por_tenant],
        'amostra': [{
            'filho_id': r[0], 'pai_id': r[1], 'admin_id': r[2],
            'data': str(r[3]), 'valor': str(r[4]), 'origem': r[5],
            'descricao': r[6],
        } for r in amostra],
        'pais_sem_obra_derivada': int(pais_sem_obra),
        'tenants_sem_centro_administrativo': int(tenants_sem_centro),
        'pronto_para_constraint': int(total) == 0,
    }


def imprimir(rel):
    print('=' * 72)
    print('FASE 4 — CONFORMIDADE DO DESTINO DO CUSTO')
    print('=' * 72)
    print(f"gestao_custo_filho SEM destino ....... {rel['sem_destino']}")
    print(f"  valor envolvido .................... R$ {rel['valor_sem_destino']}")
    print(f"gestao_custo_pai com obra_id NULL .... {rel['pais_sem_obra_derivada']}"
          "   <- inclui multi-obra e administrativo, é esperado")
    print(f"tenants sem centro administrativo .... "
          f"{rel['tenants_sem_centro_administrativo']}")
    if rel['por_origem']:
        print('-' * 72)
        print('Pendentes por origem:')
        for linha in rel['por_origem']:
            print(f"  {linha['origem']:<30} {linha['n']:>7}")
    if rel['amostra']:
        print('-' * 72)
        print('Maiores pendentes:')
        for a in rel['amostra']:
            print(f"  filho={a['filho_id']:<8} pai={a['pai_id']:<8} "
                  f"tenant={a['admin_id']:<6} R$ {a['valor']:>12} "
                  f"{a['origem']:<24} {a['descricao']}")
    print('=' * 72)
    if rel['pronto_para_constraint']:
        print('✅ PRONTO — a migration 254 (VALIDATE) pode rodar.')
    else:
        print('❌ NÃO VALIDE A CONSTRAINT. Rode antes:')
        print('   python scripts/backfill_destino_custo.py --aplicar')
    print('=' * 72)


def main():
    ap = argparse.ArgumentParser(description='Conformidade do destino do custo')
    ap.add_argument('--tenant', type=int, default=None)
    ap.add_argument('--amostra', type=int, default=20)
    args = ap.parse_args()

    from app import app

    with app.app_context():
        imprimir(conformidade(admin_id=args.tenant,
                              limite_amostra=args.amostra))


if __name__ == '__main__':
    main()
