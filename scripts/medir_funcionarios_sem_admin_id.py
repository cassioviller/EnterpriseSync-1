#!/usr/bin/env python3
"""Mede (read-only) quantos usuários ativos não-admin estão sem admin_id.

É o tamanho do reparo de dado que a falha-fechada de 01/09 expõe: com o
ramo de FK removido de crud_rdo_completo.get_admin_id (Task 10 do plano
as-decisoes-viram-codigo), cada usuário nesse estado passa a receber 403
onde antes funcionava por adivinhação. Rodar contra produção ANTES de
ligar o deploy que contém a Task 10:

    DATABASE_URL=<prod> python scripts/medir_funcionarios_sem_admin_id.py

O número de dev não vale nada (resíduo de suíte); o que importa é o de
produção. Reparo: preencher usuario.admin_id — para quem tem
funcionario_id, o valor correto é o admin_id do Funcionario apontado.
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def main():
    from sqlalchemy import text

    from app import app, db
    with app.app_context():
        linhas = db.session.execute(text("""
            SELECT tipo_usuario, COUNT(*)
            FROM usuario
            WHERE admin_id IS NULL
              AND ativo = true
              AND tipo_usuario NOT IN ('ADMIN', 'SUPER_ADMIN')
            GROUP BY tipo_usuario ORDER BY 2 DESC
        """)).fetchall()
        total = sum(n for _, n in linhas)
        print(f'usuários ativos não-admin sem admin_id: {total}')
        for papel, n in linhas:
            print(f'  {papel}: {n}')

        # quantos deles o ramo removido conseguia "salvar" pela FK — são os
        # que mudam de comportamento de verdade (os demais já falhavam)
        reparaveis = db.session.execute(text("""
            SELECT COUNT(*)
            FROM usuario u
            JOIN funcionario f ON f.id = u.funcionario_id
            WHERE u.admin_id IS NULL
              AND u.ativo = true
              AND u.tipo_usuario = 'FUNCIONARIO'
        """)).scalar()
        print(f'destes, com FK funcionario_id viva (reparo óbvio: copiar o '
              f'admin_id do Funcionario): {reparaveis}')
        print('cada um destes passa a receber 403 com a falha-fechada ativa.')


if __name__ == '__main__':
    main()
