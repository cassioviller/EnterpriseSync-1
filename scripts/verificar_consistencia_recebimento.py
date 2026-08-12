#!/usr/bin/env python3
"""Consistência da situação de recebimento de um tenant — Fase 4.

Compara, pedido a pedido, o `situacao_recebimento` PERSISTIDO com o que
`services.recebimento_pedido.situacao_para` deriva dos recebimentos. Drift
aqui significa que alguma escrita passou por fora do serviço — um UPDATE na
marra, um script de correção, uma rota nova que esqueceu do chokepoint.

O sensor reusa a MESMA função que grava. É por isso que `situacao_para` é
pura e vive separada de `registrar_recebimento`: um sensor que reimplementa
a regra que vigia não vigia nada — ele passa a ter os próprios defeitos, e
os dois erram juntos exatamente onde erram igual.

**Só pedido do regime novo entra na varredura.** Pedido legado nasce
`nao_recebido` por default da coluna e nunca é atualizado: varrer esses
produziria drift de mentira em todo tenant que ainda não virou, e um sensor
que grita sempre não é lido nunca.

Não altera nada. Exit code 0 = consistente, 1 = drift, 2 = erro de uso.

Uso:
    python scripts/verificar_consistencia_recebimento.py <admin_id>
        [--json]        # saída legível por máquina
"""
from __future__ import annotations

import argparse
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def verificar(admin_id: int) -> dict:
    """Relatório de consistência do tenant. Requer app_context."""
    from models import PedidoCompra, Usuario
    from services.recebimento_pedido import situacao_para, valor_atestado

    admin = Usuario.query.filter_by(id=admin_id).first()
    if admin is None:
        return {'erro': f'admin {admin_id} não encontrado', 'consistente': False}

    pedidos = (PedidoCompra.query
               .filter_by(admin_id=admin_id, exige_atesto=True)
               .order_by(PedidoCompra.id)
               .all())

    divergencias = []
    for pedido in pedidos:
        derivado = situacao_para(pedido)
        if derivado != pedido.situacao_recebimento:
            divergencias.append({
                'pedido_id': pedido.id,
                'numero': pedido.numero,
                'persistido': pedido.situacao_recebimento,
                'derivado': derivado,
                'valor_atestado': float(valor_atestado(pedido)),
            })

    return {
        'admin_id': admin_id,
        'pedidos_verificados': len(pedidos),
        'divergencias': divergencias,
        'consistente': not divergencias,
    }


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(
        description='Consistência da situação de recebimento persistida × '
                    'derivada (Fase 4)')
    parser.add_argument('admin_id', type=int)
    parser.add_argument('--json', action='store_true',
                        help='saída JSON em vez do relatório legível')
    args = parser.parse_args(argv)

    from app import app

    with app.app_context():
        rel = verificar(args.admin_id)

    if args.json:
        print(json.dumps(rel, ensure_ascii=False, indent=2, default=str))
    elif 'erro' in rel:
        print(rel['erro'])
    else:
        print(f"Tenant {rel['admin_id']}")
        print(f"  pedidos no regime de atesto: {rel['pedidos_verificados']}")
        if rel['consistente']:
            print('  OK — nenhum drift de situação de recebimento.')
        else:
            print(f"  DRIFT em {len(rel['divergencias'])} pedido(s):")
            for d in rel['divergencias']:
                print(f"    {d['numero'] or d['pedido_id']}: persistido "
                      f"{d['persistido']} × derivado {d['derivado']} "
                      f"(atestado R$ {d['valor_atestado']:.2f})")

    if 'erro' in rel:
        return 2
    return 0 if rel['consistente'] else 1


if __name__ == '__main__':
    raise SystemExit(main())
