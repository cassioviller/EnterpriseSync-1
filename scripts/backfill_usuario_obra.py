#!/usr/bin/env python3
"""Backfill de `usuario_obra` — SIGE Fase 1.

Popula o escopo por obra a partir do que o sistema JÁ sabe, sem inventar
permissão. Duas fontes, nesta ordem de precedência:

  1. `Obra.responsavel_id` → GESTOR. É a declaração mais forte que
     existe hoje sobre quem responde pela obra. Exige que o Funcionario
     apontado tenha login (`Usuario.funcionario_id`), senão não há a
     quem dar permissão.
  2. `FuncionarioObrasPonto` → APONTADOR. É configuração de dropdown de
     ponto (models.py:605), mas é a única evidência registrada de que
     "esta pessoa trabalha nesta obra". Idem: só vale com login.

O que NÃO faz: não inventa LEITOR para todo mundo, não usa
`AlocacaoEquipe` (planejamento diário, muda toda semana), não cria
usuário nem funcionário.

Uso:
    python scripts/backfill_usuario_obra.py                      # dry-run
    python scripts/backfill_usuario_obra.py --aplicar
    python scripts/backfill_usuario_obra.py --admin-id 10 --aplicar
"""
import argparse
import logging
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from models import (FuncionarioObrasPonto, Obra, PapelObra, Usuario,
                    UsuarioObra, db)
from utils.identidade import tenant_do_usuario

logger = logging.getLogger('backfill_usuario_obra')


def _vincular(usuario_id, obra_id, papel, admin_id, existentes):
    """Cria o vínculo se ainda não houver. Não faz commit."""
    if (usuario_id, obra_id) in existentes:
        return False
    db.session.add(UsuarioObra(usuario_id=usuario_id, obra_id=obra_id,
                               papel=papel, admin_id=admin_id, ativo=True))
    existentes.add((usuario_id, obra_id))
    return True


def executar_backfill_obras(dry_run=True, admin_id=None):
    """Popula usuario_obra. Devolve relatório; não imprime nada.

    Returns:
        dict com 'criados' (int), 'gestores' (int), 'apontadores' (int) e
        'obras_sem_gestor' (lista de obra_id).
    """
    obras_q = Obra.query
    if admin_id is not None:
        obras_q = obras_q.filter(Obra.admin_id == admin_id)
    obras = obras_q.all()

    existentes = {
        (v.usuario_id, v.obra_id)
        for v in UsuarioObra.query.all()
    }

    criados = gestores = apontadores = 0
    obras_sem_gestor = []

    for obra in obras:
        tem_gestor = False

        # Fonte 1 — o responsável declarado da obra vira GESTOR.
        if obra.responsavel_id:
            usuario = Usuario.query.filter_by(
                funcionario_id=obra.responsavel_id).first()
            # O login tem que ser do MESMO tenant da obra. `tenant_do_usuario`
            # resolve as duas formas (ADMIN é o próprio id; os demais usam
            # admin_id), evitando a comparação torta que isso viraria aqui.
            if usuario is not None and tenant_do_usuario(usuario) == obra.admin_id:
                if _vincular(usuario.id, obra.id, PapelObra.GESTOR,
                             obra.admin_id, existentes):
                    criados += 1
                    gestores += 1
                tem_gestor = True

        # Fonte 2 — quem bate ponto na obra vira APONTADOR.
        configs = FuncionarioObrasPonto.query.filter_by(
            obra_id=obra.id, ativo=True).all()
        for config in configs:
            usuario = Usuario.query.filter_by(
                funcionario_id=config.funcionario_id).first()
            if usuario is None:
                continue
            if _vincular(usuario.id, obra.id, PapelObra.APONTADOR,
                         obra.admin_id, existentes):
                criados += 1
                apontadores += 1

        if not tem_gestor:
            obras_sem_gestor.append(obra.id)

    if dry_run:
        db.session.rollback()
    else:
        db.session.commit()

    return {'criados': criados, 'gestores': gestores,
            'apontadores': apontadores,
            'obras_sem_gestor': obras_sem_gestor}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--aplicar', action='store_true')
    parser.add_argument('--admin-id', type=int, default=None)
    args = parser.parse_args()

    from app import app
    with app.app_context():
        relatorio = executar_backfill_obras(dry_run=not args.aplicar,
                                            admin_id=args.admin_id)

    modo = 'APLICADO' if args.aplicar else 'DRY-RUN (nada foi escrito)'
    print(f'=== Backfill de usuario_obra — {modo} ===')
    print(f'Vínculos criados ...: {relatorio["criados"]}')
    print(f'  como GESTOR ......: {relatorio["gestores"]}')
    print(f'  como APONTADOR ...: {relatorio["apontadores"]}')
    print(f'Obras sem gestor ...: {len(relatorio["obras_sem_gestor"])}')
    if relatorio['obras_sem_gestor']:
        print('\nATENÇÃO: estas obras ficarão sem GESTOR. Ligar a flag do '
              'tenant sem resolvê-las deixa a obra sem ninguém que a edite '
              '(além do ADMIN):')
        print('  obra_id: ' + ', '.join(
            str(i) for i in relatorio['obras_sem_gestor'][:50]))
    return 0


if __name__ == '__main__':
    sys.exit(main())
