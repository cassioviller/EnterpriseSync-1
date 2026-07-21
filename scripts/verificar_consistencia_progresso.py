#!/usr/bin/env python3
"""Consistência do progresso de uma obra (M10 §4.3 — ferramenta de suporte).

Compara, folha a folha, o `percentual_concluido` PERSISTIDO com o que o
engine unificado do M06 recalcula a partir dos RDOs. Drift aqui significa
que alguma escrita passou por fora do engine — é o sensor do critério
global 11 ("cronograma, RDO, detalhes e portal exibem o mesmo percentual")
e o gate do rollout fase 1 ("zero drift de progresso").

Não altera nada. Exit code 0 = consistente, 1 = drift, 2 = erro de uso.

Uso:
    python scripts/verificar_consistencia_progresso.py <obra_id> <admin_id>
        [--json]        # saída legível por máquina
"""
from __future__ import annotations

import argparse
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def verificar(obra_id: int, admin_id: int) -> dict:
    """Relatório de consistência da obra. Requer app_context."""
    from models import Obra
    from utils.cronograma_engine import verificar_consistencia_progresso

    obra = Obra.query.filter_by(id=obra_id, admin_id=admin_id).first()
    if obra is None:
        return {'erro': f'obra {obra_id} não encontrada para o admin {admin_id}',
                'consistente': False}

    relatorio = verificar_consistencia_progresso(obra_id, admin_id)
    return {
        'obra_id': obra_id,
        'obra_nome': obra.nome,
        'admin_id': admin_id,
        'tarefas_verificadas': relatorio['tarefas_verificadas'],
        'divergencias': relatorio['divergencias'],
        'consistente': not relatorio['divergencias'],
    }


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(
        description='Consistência do progresso persistido × engine (M10)')
    parser.add_argument('obra_id', type=int)
    parser.add_argument('admin_id', type=int)
    parser.add_argument('--json', action='store_true',
                        help='saída JSON em vez do relatório legível')
    args = parser.parse_args(argv)

    from app import app

    with app.app_context():
        rel = verificar(args.obra_id, args.admin_id)

    if args.json:
        print(json.dumps(rel, ensure_ascii=False, indent=2, default=str))
    elif 'erro' in rel:
        print(rel['erro'])
    else:
        print(f"Obra {rel['obra_id']} — {rel['obra_nome']}")
        print(f"  folhas verificadas: {rel['tarefas_verificadas']}")
        if rel['consistente']:
            print('  OK — nenhum drift de progresso.')
        else:
            print(f"  DRIFT em {len(rel['divergencias'])} tarefa(s):")
            for d in rel['divergencias']:
                print(f"    tarefa {d['tarefa_id']}: persistido "
                      f"{d['persistido']:.2f} × recalculado "
                      f"{d['recalculado']:.2f}")

    if 'erro' in rel:
        return 2
    return 0 if rel['consistente'] else 1


if __name__ == '__main__':
    raise SystemExit(main())
