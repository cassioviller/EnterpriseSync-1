"""utils/rdo_horas.py

Normalização de horas trabalhadas no RDO quando o mesmo funcionário
aparece em múltiplas atividades (subatividades + tarefas do cronograma)
no mesmo relatório.

Regra de negócio
----------------
A jornada-base do funcionário no dia é o MAIOR valor que ele entrou
em qualquer linha do RDO (cobre o caso comum em que o usuário digita
8h em todas as atividades). Esse total é dividido igualmente pelas
``N`` atividades distintas em que ele participa, evitando que 8h em
3 atividades vire 24h fictícias.

Exemplo:
    >>> entries = [(10, ('sub', 'A'), 8.0),
    ...            (10, ('sub', 'B'), 8.0),
    ...            (10, ('sub', 'C'), 8.0)]
    >>> normalizar_horas_funcionario(entries)
    [(10, ('sub', 'A'), 2.6666...),
     (10, ('sub', 'B'), 2.6666...),
     (10, ('sub', 'C'), 2.6666...)]

Funcionários que aparecem em apenas 1 atividade não são alterados.
A função preserva qualquer campo extra a partir do índice 3 da tupla
(útil para metadados como objetos de subatividade).
"""

from typing import Iterable, List, Tuple


def normalizar_horas_funcionario(entries: Iterable[Tuple]) -> List[Tuple]:
    """Divide horas-base do funcionário pelas atividades distintas.

    Args:
        entries: iterável de tuplas no formato
            ``(func_id, atividade_key, horas, *extras)`` onde
            ``atividade_key`` é qualquer valor hashable que identifica
            unicamente a atividade no RDO (use uma tupla
            ``('sub', sub_mestre_id)`` ou ``('cron', tarefa_id)`` para
            distinguir subatividades de tarefas do cronograma).

    Returns:
        Lista com a mesma estrutura, com ``horas`` substituídas por
        ``max(horas) / N`` para funcionários que aparecem em N>1
        atividades distintas. Campos extras são preservados.
    """
    entries_list = list(entries)
    if not entries_list:
        return entries_list

    grupos: dict = {}
    for entry in entries_list:
        func_id = entry[0]
        grupos.setdefault(func_id, []).append(entry)

    resultado: List[Tuple] = []
    for func_id, items in grupos.items():
        chaves_distintas = {item[1] for item in items}
        n = len(chaves_distintas)
        if n <= 1:
            resultado.extend(items)
            continue

        max_horas = max((float(item[2] or 0) for item in items), default=0.0)
        horas_norm = max_horas / n if n > 0 else 0.0
        for item in items:
            novo = (item[0], item[1], horas_norm) + tuple(item[3:])
            resultado.append(novo)
    return resultado
