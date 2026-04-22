"""
Task #144 — Script de manutenção: deduplica TarefaCronograma em todas as obras.

Uso:
    python scripts/dedupe_tarefa_cronograma.py

Reaponta apontamentos (RDOApontamentoCronograma, RDOSubempreitadaApontamento,
ItemMedicaoCronogramaTarefa) e relações pai/predecessora para a tarefa
"canônica" (a que tem `gerada_por_proposta_item_id`, ou a de menor id em
empate). Apaga as tarefas duplicadas. Imprime relatório por obra.
"""
import os
import sys
import logging

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app import app
from services.cronograma_dedup import deduplicar_todas_obras

logging.basicConfig(level=logging.INFO, format='%(asctime)s [%(levelname)s] %(message)s')


def main() -> int:
    with app.app_context():
        relatorio = deduplicar_todas_obras()
    if not relatorio:
        print('OK: nenhuma duplicata encontrada.')
        return 0
    total_int = sum(v['interno'] for v in relatorio.values())
    total_cli = sum(v['cliente'] for v in relatorio.values())
    print(f'Removidas {total_int} duplicatas (interno) + {total_cli} (cliente) '
          f'em {len(relatorio)} obra(s).')
    for obra_id, info in sorted(relatorio.items()):
        print(f'  obra={obra_id}: interno={info["interno"]} cliente={info["cliente"]}')
    return 0


if __name__ == '__main__':
    sys.exit(main())
