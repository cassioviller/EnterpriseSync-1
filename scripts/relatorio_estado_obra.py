#!/usr/bin/env python3
"""Censo de estado das obras — Fase 2.

Rode ANTES da migração 231 para saber o que existe em produção, e DEPOIS
para conferir. Somente leitura: nunca escreve nada.

O que ele responde:
  - distribuição por `estado` e pelo `status` legado;
  - grafias de `status` que o mapa legado não conhece (candidatas a revisão
    humana — a 231 as derivou por `ativo`);
  - divergências `ativo` × `estado` (a 231 não toca `ativo` de propósito:
    corrigir mudaria a visibilidade de obras sem ninguém pedir);
  - obras EM EXECUÇÃO sem gestor vinculado — a fila de handoff que o
    backfill criou, o número que a Task 14 manda levar ao Cássio.

Uso:
    python scripts/relatorio_estado_obra.py            # todos os tenants
    python scripts/relatorio_estado_obra.py --admin-id 10
"""
from __future__ import annotations

import argparse
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def levantar(admin_id: int | None = None) -> dict:
    """Devolve o censo como dict. Requer app_context ativo."""
    from models import Obra, PapelObra, UsuarioObra, db
    from services.obra_estado import estado_do_status_legado

    q = Obra.query
    if admin_id is not None:
        q = q.filter(Obra.admin_id == admin_id)
    obras = q.all()

    por_estado: dict[str, int] = {}
    por_status: dict[str, int] = {}
    grafias_desconhecidas: dict[str, int] = {}
    divergencias_ativo = 0
    sem_estado = 0

    for o in obras:
        estado = getattr(o, 'estado', None)
        if not estado:
            sem_estado += 1
        else:
            por_estado[estado] = por_estado.get(estado, 0) + 1
        rotulo = o.status or '<NULL>'
        por_status[rotulo] = por_status.get(rotulo, 0) + 1
        if o.status and estado_do_status_legado(o.status) is None:
            grafias_desconhecidas[o.status] = \
                grafias_desconhecidas.get(o.status, 0) + 1
        # `ativo` deve ser False exatamente em concluida/cancelada.
        esperado_ativo = estado not in ('concluida', 'cancelada')
        if estado and bool(o.ativo) != esperado_ativo:
            divergencias_ativo += 1

    ids_em_execucao = [o.id for o in obras
                       if getattr(o, 'estado', None) == 'em_execucao']
    com_gestor = set()
    if ids_em_execucao:
        com_gestor = {
            row[0] for row in db.session.query(UsuarioObra.obra_id).filter(
                UsuarioObra.obra_id.in_(ids_em_execucao),
                UsuarioObra.papel == PapelObra.GESTOR,
                UsuarioObra.ativo.is_(True),
            ).all()
        }

    return {
        'admin_id': admin_id,
        'total': len(obras),
        'sem_estado': sem_estado,
        'por_estado': por_estado,
        'por_status_legado': por_status,
        'grafias_desconhecidas': grafias_desconhecidas,
        'divergencias_ativo': divergencias_ativo,
        'em_execucao_sem_gestor': len(
            [i for i in ids_em_execucao if i not in com_gestor]),
    }


def imprimir(rel: dict) -> None:
    alvo = (f"tenant {rel['admin_id']}" if rel['admin_id'] is not None
            else 'todos os tenants')
    print(f"── Censo de estado das obras ({alvo}) " + '─' * 20)
    print(f"total de obras:          {rel['total']}")
    print(f"sem estado (NULL):       {rel['sem_estado']}")
    print("por estado:")
    for estado, n in sorted(rel['por_estado'].items(), key=lambda kv: -kv[1]):
        print(f"  {estado:14} {n}")
    print("por status legado:")
    for status, n in sorted(rel['por_status_legado'].items(),
                            key=lambda kv: -kv[1]):
        print(f"  {status!r:20} {n}")
    if rel['grafias_desconhecidas']:
        print("grafias fora do mapa legado (revisar):")
        for g, n in rel['grafias_desconhecidas'].items():
            print(f"  {g!r:20} {n}")
    print(f"divergências ativo×estado: {rel['divergencias_ativo']}")
    print(f"EM EXECUÇÃO sem gestor:    {rel['em_execucao_sem_gestor']}"
          "   ← fila de handoff")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--admin-id', type=int, default=None)
    args = parser.parse_args()

    from app import app
    with app.app_context():
        imprimir(levantar(args.admin_id))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
