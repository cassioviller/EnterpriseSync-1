#!/usr/bin/env python3
"""Quantos registros foram carimbados no tenant fantasma?

`multitenant_helper.get_admin_id()` devolve `current_user.id` para
GESTOR_EQUIPES e ALMOXARIFE, quando o certo é `current_user.admin_id`. Todo
registro escrito por esses papéis pelos 8 módulos que importam o helper foi
para um `admin_id` que não é de nenhum ADMIN.

Este script SÓ LÊ. Rode antes da Task 2 da Onda 2.

    python scripts/medir_tenant_fantasma.py
"""
import sys

from app import app, db
from models import TipoUsuario, Usuario

# As tabelas escritas pelos 8 módulos que importam `multitenant_helper`.
# Nome da tabela → o módulo que a escreve, para o relatório dizer onde olhar.
TABELAS = {
    'conta_pagar': 'financeiro_views',
    'conta_receber': 'financeiro_views',
    'fluxo_caixa': 'financeiro_views',
    'registro_ponto': 'ponto_views / ponto_service',
    'reembolso': 'reembolso_views',
    'custo_escritorio': 'custos_escritorio_views',
    'configuracao_empresa': 'configuracoes_views',
    'usuario': 'views/users.py',
}


def main():
    with app.app_context():
        suspeitos = Usuario.query.filter(
            Usuario.tipo_usuario.in_([TipoUsuario.GESTOR_EQUIPES,
                                      TipoUsuario.ALMOXARIFE])).all()
        if not suspeitos:
            print('Nenhum GESTOR_EQUIPES nem ALMOXARIFE no banco.')
            print('VEREDITO: a Task 2 entra SEM migration de saneamento.')
            return 0

        print(f'{len(suspeitos)} usuário(s) com papel afetado:\n')
        total_geral = 0
        pares_medidos = set()
        pares_falhados = {}
        pares_esperados = set()
        for u in suspeitos:
            print(f'  id={u.id} {u.tipo_usuario.value} admin_id={u.admin_id} '
                  f'({u.email})')
            if u.admin_id == u.id:
                print('    ↳ admin_id == id: este não distingue os dois '
                      'resolvedores, nada a corrigir')
                continue
            for tabela in TABELAS.keys():
                pares_esperados.add((u.id, tabela))
            for tabela, modulo in sorted(TABELAS.items()):
                try:
                    n = db.session.execute(
                        db.text(f'SELECT count(*) FROM {tabela} '
                                f'WHERE admin_id = :aid'),
                        {'aid': u.id}).scalar()
                    pares_medidos.add((u.id, tabela))
                except Exception as erro:
                    print(f'    {tabela}: não consultável ({erro})')
                    chave = (u.id, tabela)
                    pares_falhados[chave] = str(erro)
                    db.session.rollback()
                    continue
                if n:
                    total_geral += n
                    print(f'    🔴 {tabela}: {n} linha(s) com admin_id={u.id} '
                          f'(deveria ser {u.admin_id}) — escrito por {modulo}')

        print()
        pares_nao_medidos = pares_esperados - pares_medidos
        if pares_esperados and pares_nao_medidos == pares_esperados:
            print('FALHA: medição incompleta')
            print(f'{len(pares_nao_medidos)} par(es) usuário-tabela não puderam ser consultados:')
            for uid, tabela in sorted(pares_nao_medidos):
                chave = (uid, tabela)
                err = pares_falhados.get(chave, 'erro desconhecido')
                print(f'  - usuário {uid}, {tabela}: {err}')
            return 1
        elif not pares_esperados:
            print('Nenhum usuário de papel afetado distingue os dois resolvedores.')
            print('VEREDITO: a Task 2 entra SEM migration de saneamento.')
            return 0
        elif pares_nao_medidos:
            usuarios_falhados = sorted(set(uid for uid, _ in pares_nao_medidos))
            tabelas_falhadas = sorted(set(tab for _, tab in pares_nao_medidos))
            print(f'AVISO: medição parcial ({len(pares_medidos)}/{len(pares_esperados)} pares usuário-tabela)')
            print(f'Usuários afetados: {usuarios_falhados}')
            print(f'Tabelas afetadas: {tabelas_falhadas}')
            print()
            if total_geral:
                print(f'VEREDITO (PARCIAL): {total_geral} linha(s) no tenant fantasma.')
                print('A Task 2 PRECISA de migration de saneamento, e ela é '
                      'DECISÃO HUMANA: mover o dado para o admin_id certo pode '
                      'colidir com registro que já existe lá.')
            else:
                print('VEREDITO (PARCIAL): nenhuma linha encontrada nas tabelas consultáveis.')
                print('A Task 2 entra SEM migration de saneamento.')
            return 1
        else:
            if total_geral:
                print(f'VEREDITO: {total_geral} linha(s) no tenant fantasma.')
                print('A Task 2 PRECISA de migration de saneamento, e ela é '
                      'DECISÃO HUMANA: mover o dado para o admin_id certo pode '
                      'colidir com registro que já existe lá.')
            else:
                print('VEREDITO: nenhuma linha no tenant fantasma.')
                print('A Task 2 entra SEM migration de saneamento.')
            return 0


if __name__ == '__main__':
    sys.exit(main())
