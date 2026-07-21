#!/usr/bin/env python3
"""Backfill do vínculo Usuario ↔ Funcionario — SIGE Fase 1.

Casa login com linha de RH por e-mail EXATO (case-insensitive) DENTRO do
mesmo tenant. Deliberadamente conservador:

  * não casa por nome, nem por substring, nem por CPF;
  * não cria Funcionario nenhum;
  * não casa se houver mais de um candidato (ambiguidade → humano decide);
  * não toca em quem já tem vínculo;
  * dry-run é o PADRÃO.

Uso:
    python scripts/backfill_identidade_funcionario.py            # dry-run
    python scripts/backfill_identidade_funcionario.py --aplicar
    python scripts/backfill_identidade_funcionario.py --admin-id 10 --aplicar
"""
import argparse
import logging
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy import func as sa_func

from models import Funcionario, TipoUsuario, Usuario, db
from utils.identidade import VinculoInvalido, tenant_do_usuario, vincular_funcionario

logger = logging.getLogger('backfill_identidade')


def executar_backfill(dry_run=True, admin_id=None):
    """Casa Usuario↔Funcionario. Devolve relatório; não imprime nada.

    Args:
        dry_run: se True (padrão), conta o que casaria mas não escreve.
        admin_id: restringe a um tenant. None = todos.

    Returns:
        dict com 'casados' (int), 'ja_vinculados' (int) e
        'pendentes' (lista de {usuario_id, email, motivo}).
    """
    query = Usuario.query.filter(Usuario.funcionario_id.is_(None))
    if admin_id is not None:
        query = query.filter(
            db.or_(Usuario.admin_id == admin_id, Usuario.id == admin_id))

    casados = 0
    pendentes = []

    for usuario in query.all():
        tenant = tenant_do_usuario(usuario)
        if tenant is None:
            pendentes.append({'usuario_id': usuario.id,
                              'email': usuario.email,
                              'motivo': 'sem_tenant'})
            continue

        # ADMIN/SUPER_ADMIN normalmente não são funcionários; ainda assim
        # tentamos casar — uma construtora pequena pode ter o dono
        # cadastrado no RH. Se não casar, não é pendência de verdade.
        if not usuario.email:
            pendentes.append({'usuario_id': usuario.id,
                              'email': None,
                              'motivo': 'sem_email'})
            continue

        candidatos = Funcionario.query.filter(
            sa_func.lower(Funcionario.email) == usuario.email.strip().lower(),
            Funcionario.admin_id == tenant,
        ).all()

        if len(candidatos) == 0:
            pendentes.append({'usuario_id': usuario.id,
                              'email': usuario.email,
                              'motivo': 'sem_correspondencia'})
            continue

        if len(candidatos) > 1:
            pendentes.append({'usuario_id': usuario.id,
                              'email': usuario.email,
                              'motivo': 'ambiguo'})
            continue

        candidato = candidatos[0]

        # Já tomado por outro login? UNIQUE recusaria; reporta em vez de estourar.
        ja_tomado = Usuario.query.filter(
            Usuario.funcionario_id == candidato.id,
            Usuario.id != usuario.id,
        ).first()
        if ja_tomado:
            pendentes.append({'usuario_id': usuario.id,
                              'email': usuario.email,
                              'motivo': 'funcionario_ja_vinculado'})
            continue

        casados += 1
        if not dry_run:
            try:
                vincular_funcionario(usuario, candidato)
            except VinculoInvalido:
                casados -= 1
                pendentes.append({'usuario_id': usuario.id,
                                  'email': usuario.email,
                                  'motivo': 'cross_tenant'})

    if not dry_run:
        db.session.commit()
    else:
        db.session.rollback()

    ja_vinculados = Usuario.query.filter(
        Usuario.funcionario_id.isnot(None)).count()

    return {'casados': casados,
            'ja_vinculados': ja_vinculados,
            'pendentes': pendentes}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--aplicar', action='store_true',
                        help='escreve de fato (padrão é dry-run)')
    parser.add_argument('--admin-id', type=int, default=None,
                        help='restringe a um tenant')
    args = parser.parse_args()

    from app import app
    with app.app_context():
        relatorio = executar_backfill(dry_run=not args.aplicar,
                                      admin_id=args.admin_id)

    modo = 'APLICADO' if args.aplicar else 'DRY-RUN (nada foi escrito)'
    print(f'=== Backfill de identidade — {modo} ===')
    print(f'Vínculos criados .....: {relatorio["casados"]}')
    print(f'Já vinculados no banco: {relatorio["ja_vinculados"]}')
    print(f'Pendentes ............: {len(relatorio["pendentes"])}')

    por_motivo = {}
    for p in relatorio['pendentes']:
        por_motivo.setdefault(p['motivo'], []).append(p)
    for motivo, itens in sorted(por_motivo.items()):
        print(f'  {motivo:.<28} {len(itens)}')

    ambiguos = por_motivo.get('ambiguo', [])
    if ambiguos:
        print('\nAMBÍGUOS (exigem decisão humana):')
        for p in ambiguos[:50]:
            print(f'  usuario_id={p["usuario_id"]} email={p["email"]}')

    return 0


if __name__ == '__main__':
    sys.exit(main())
