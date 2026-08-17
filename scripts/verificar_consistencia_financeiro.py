#!/usr/bin/env python3
"""Consistência do financeiro em dois fluxos de um tenant — Fase 2 do ciclo de compras.

Procura três coisas, todas do mesmo tipo: estado que só poderia ter chegado ali
por fora do serviço.

1. **Conta `liberada` sem a tríade fechada.** `services.financeiro_compra.liberar`
   é o único caminho que libera, e ele recusa enquanto faltar nota ou atesto. Uma
   conta liberada com perna faltando significa UPDATE na marra, script de
   correção, ou rota nova que esqueceu do chokepoint.
2. **Adiantamento baixado sem atesto.** Só `registrar_recebimento` baixa. Baixa
   sem material é o buraco que a lista "pago, aguardando entrega" existe para
   tapar — se ele existir, a lista deixou de significar o que promete.
3. **Lote `FECHADO` sem `fechado_por_id`.** Fechar é o ato que autoriza
   pagamento; sem autor não há segregação, só a aparência dela.

E lista uma quarta coisa que **não é defeito**: a **liberação com ressalva**
(D6, construída no fecho de 17/08). Ela é conta liberada com perna aberta —
indistinguível do achado 1 pela consulta, e distinguível pela
`liberacao_justificativa`. Aparece para ser lida uma vez por mês e **não conta
para o exit code**: exceção que ninguém lê é exceção que vira rotina, e sensor
que sai 1 pelo que o próprio desenho autoriza ensina o time a ignorar o exit
code.

O sensor reusa as MESMAS funções que gravam (`pernas_faltantes`,
`valor_atestado`). Um sensor que reimplementa a regra que vigia não vigia nada:
ele passa a ter os próprios defeitos, e os dois erram juntos exatamente onde
erram igual.

**Só o regime novo entra na varredura.** Toda conta de pedido legado é
`liberada` e não tem nota nenhuma — varrer essas produziria drift de mentira em
cada tenant que ainda não virou, e um sensor que grita sempre não é lido nunca.

Não altera nada. Exit code 0 = consistente, 1 = drift, 2 = erro de uso.

Uso:
    python scripts/verificar_consistencia_financeiro.py <admin_id>
        [--json]        # saída legível por máquina
"""
from __future__ import annotations

import argparse
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def inconsistencias(admin_id):
    """Lista de dicionários descrevendo cada drift. Vazia = consistente.

    Não levanta e não escreve: dá para chamar de dentro de um teste, de um
    cron ou de uma tela sem efeito colateral nenhum.
    """
    from models import (AdiantamentoFornecedor, ContaPagar,
                        FechamentoPagamento, PedidoCompra)
    from services.financeiro_compra import pernas_faltantes
    from services.recebimento_pedido import valor_atestado

    achados = []

    # 1. conta liberada sem a tríade
    contas = (ContaPagar.query
              .filter(ContaPagar.admin_id == admin_id,
                      ContaPagar.pedido_compra_id.isnot(None),
                      ContaPagar.situacao_liberacao == 'liberada')
              .all())
    for cp in contas:
        pedido = PedidoCompra.query.filter_by(
            id=cp.pedido_compra_id, admin_id=admin_id).first()
        if pedido is None:
            continue
        # `pernas_faltantes` devolve [] para quem não está no Fluxo A do regime
        # novo — é ele quem faz o recorte, e é por isso que o sensor não
        # precisa reimplementar a regra do regime.
        if getattr(pedido, 'fluxo_pagamento', 'faturado') != 'faturado':
            continue
        faltam = pernas_faltantes(pedido)
        if not faltam and cp.liberada_em is None and cp.situacao_liberacao == 'liberada':
            # Conta do regime antigo: nasce liberada, sem tríade nenhuma, e o
            # recorte acima já a deixou passar. Nada a dizer.
            continue
        if faltam:
            # ⚠️ Fecho da Fase 2 (17/08) — a ressalva do D6 passa por AQUI.
            #
            # Conta liberada com perna aberta é EXATAMENTE o que este achado
            # procura, e é também exatamente o que uma liberação por ressalva
            # é. Sem esta separação, toda exceção legítima viraria
            # inconsistência no dia em que a ressalva entrasse — e sensor que
            # grita pelo esperado deixa de ser lido, que é o mesmo argumento
            # do "só o regime novo entra na varredura" do docstring.
            #
            # A ressalva não é defeito e por isso NÃO conta para o exit 1. Ela
            # aparece assim mesmo, porque exceção que ninguém lê é exceção que
            # vira rotina — e a leitura mensal é metade do controle que o D6
            # comprou ao abrir a porta.
            if cp.liberacao_justificativa:
                achados.append({
                    'tipo': 'liberada_com_ressalva',
                    'defeito': False,
                    'conta_pagar_id': cp.id,
                    'pedido_id': pedido.id,
                    'pedido_numero': pedido.numero,
                    'faltam': faltam,
                    'justificativa': cp.liberacao_justificativa,
                    'liberada_por_id': cp.liberada_por_id,
                })
                continue
            achados.append({
                'tipo': 'conta_liberada_sem_triade',
                'conta_pagar_id': cp.id,
                'pedido_id': pedido.id,
                'pedido_numero': pedido.numero,
                'faltam': faltam,
            })

    # 2. adiantamento baixado sem atesto
    baixados = (AdiantamentoFornecedor.query
                .filter(AdiantamentoFornecedor.admin_id == admin_id,
                        AdiantamentoFornecedor.baixado_em.isnot(None))
                .all())
    for a in baixados:
        pedido = PedidoCompra.query.filter_by(
            id=a.pedido_id, admin_id=admin_id).first()
        if pedido is None:
            continue
        if valor_atestado(pedido) <= 0:
            achados.append({
                'tipo': 'adiantamento_baixado_sem_atesto',
                'adiantamento_id': a.id,
                'pedido_id': pedido.id,
                'pedido_numero': pedido.numero,
            })

    # 3. lote fechado sem autor
    lotes = (FechamentoPagamento.query
             .filter(FechamentoPagamento.admin_id == admin_id,
                     FechamentoPagamento.status == 'FECHADO',
                     FechamentoPagamento.fechado_por_id.is_(None))
             .all())
    for f in lotes:
        achados.append({
            'tipo': 'lote_fechado_sem_autor',
            'fechamento_id': f.id,
            'data_fechamento': str(f.data_fechamento),
        })

    return achados


def main():
    parser = argparse.ArgumentParser(
        description='Consistência do financeiro em dois fluxos (Fase 2)')
    parser.add_argument('admin_id', type=int)
    parser.add_argument('--json', action='store_true')
    args = parser.parse_args()

    from app import app
    with app.app_context():
        achados = inconsistencias(args.admin_id)

    # A ressalva do D6 é exceção declarada, não drift: ela é IMPRESSA para ser
    # lida, e não conta para o exit code. Um sensor que sai 1 por causa do que
    # o próprio desenho autoriza ensina o time a ignorar o exit code.
    defeitos = [a for a in achados if a.get('defeito', True)]
    ressalvas = [a for a in achados if a['tipo'] == 'liberada_com_ressalva']

    if args.json:
        print(json.dumps(achados, ensure_ascii=False, indent=2))
        return 1 if defeitos else 0

    if ressalvas:
        print(f'tenant {args.admin_id}: {len(ressalvas)} liberação(ões) COM '
              f'RESSALVA — não são defeito, são para ler:\n')
        for a in ressalvas:
            print(f"  ContaPagar {a['conta_pagar_id']} (pedido "
                  f"{a['pedido_numero'] or a['pedido_id']}) liberada faltando "
                  f"{'; '.join(a['faltam'])}\n"
                  f"    motivo: {a['justificativa']}")
        print()

    if not defeitos:
        print(f'tenant {args.admin_id}: sem drift no financeiro de compras.')
    else:
        print(f'tenant {args.admin_id}: {len(defeitos)} inconsistência(s).\n')
        for a in defeitos:
            if a['tipo'] == 'conta_liberada_sem_triade':
                print(f"  ContaPagar {a['conta_pagar_id']} (pedido "
                      f"{a['pedido_numero'] or a['pedido_id']}) está LIBERADA "
                      f"mas falta: {'; '.join(a['faltam'])}")
            elif a['tipo'] == 'adiantamento_baixado_sem_atesto':
                print(f"  Adiantamento {a['adiantamento_id']} (pedido "
                      f"{a['pedido_numero'] or a['pedido_id']}) foi baixado sem "
                      f"nenhum atesto — a entrega não foi conferida")
            else:
                print(f"  Fechamento {a['fechamento_id']} "
                      f"({a['data_fechamento']}) está FECHADO sem registro de "
                      f"quem fechou — sem autor não há segregação")
        print('\nNenhum destes estados sai do serviço. Cada um significa uma '
              'escrita por fora dele.')

    return 1 if defeitos else 0


if __name__ == '__main__':
    sys.exit(main())
