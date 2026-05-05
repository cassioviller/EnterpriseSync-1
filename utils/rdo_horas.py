"""utils/rdo_horas.py

Normalização de horas trabalhadas no RDO quando o mesmo funcionário
aparece em múltiplas atividades (subatividades + tarefas do cronograma)
no mesmo relatório.

Regra de negócio
----------------
A jornada-base do funcionário no dia é o MAIOR valor que ele entrou
em qualquer linha do RDO (cobre o caso comum em que o usuário digita
8h em todas as atividades). Por padrão esse total é dividido
igualmente pelas ``N`` atividades distintas em que ele participa,
evitando que 8h em 3 atividades vire 24h fictícias.

Task #38 — distribuição com pesos
---------------------------------
O apontador pode marcar uma das tarefas do funcionário como
**principal** com um peso livre de 0 a 100 (porcento da jornada-base).
Quando o helper recebe o argumento ``pesos`` (dict
``{(func_id, atividade_key): int_ou_None}``), ele aplica a
distribuição abaixo, por funcionário:

* Se nenhuma das linhas do funcionário tem peso → divisão igual
  (comportamento histórico, sem regressão).
* Se TODAS as linhas têm peso → distribuição proporcional aos pesos
  (a jornada-base é repartida em ``peso_i / sum(pesos)``).
* Caso misto (alguma linha com peso, outras com ``None``) → as linhas
  com peso recebem ``peso_i / 100`` da jornada-base; o restante
  ``max(0, 100 - sum_pesos)`` é dividido igualmente entre as linhas
  ``None`` daquele funcionário.

Funcionários que aparecem em apenas 1 atividade não são alterados,
independente de existir peso (a UI não oferece o painel nesse caso).

A função preserva qualquer campo extra a partir do índice 3 da tupla
(útil para metadados como nome de função etc.).

Task #5 — remoção de hora extra do RDO
--------------------------------------
A dimensão ``horas_extras`` foi removida do pipeline do RDO. As tuplas
de entrada passaram a ter o formato ``(func_id, atividade_key, horas,
*meta)`` e o helper não trata mais horas extras. Hora extra continua
existindo no Ponto Eletrônico/Folha de Pagamento — fora do escopo do RDO.
"""

from typing import Iterable, List, Mapping, Optional, Tuple


def normalizar_horas_funcionario(
    entries: Iterable[Tuple],
    *,
    pesos: Optional[Mapping[Tuple, Optional[int]]] = None,
) -> List[Tuple]:
    """Divide horas-base do funcionário pelas atividades distintas.

    Args:
        entries: iterável de tuplas no formato
            ``(func_id, atividade_key, horas, *meta)``
            onde ``atividade_key`` é qualquer valor hashable que
            identifica unicamente a atividade no RDO. Campos extras
            a partir do índice 3 são preservados como metadados.
        pesos: dicionário opcional ``{(func_id, atividade_key): peso}``
            com pesos em pontos percentuais (``0..100``) ou ``None``.
            Quando ausente para uma chave, vale ``None``. Veja a regra
            de distribuição no docstring do módulo.

    Returns:
        Lista com a mesma estrutura, com ``horas`` substituído pelo
        valor distribuído. Campos extras a partir do índice 3 são
        preservados.
    """
    entries_list = list(entries)
    if not entries_list:
        return entries_list

    pesos = dict(pesos) if pesos else {}

    grupos: dict = {}
    for entry in entries_list:
        func_id = entry[0]
        grupos.setdefault(func_id, []).append(entry)

    resultado: List[Tuple] = []
    for func_id, items in grupos.items():
        chaves_distintas = {item[1] for item in items}
        n = len(chaves_distintas)
        if n <= 1:
            # Funcionário em 1 só atividade: passa direto (UI também
            # não oferece o painel de pesos nesse caso).
            for item in items:
                resultado.append(item)
            continue

        max_horas = max((float(item[2] or 0) for item in items), default=0.0)

        # Lê pesos para esse funcionário (mesma chave que o caller
        # usou em entries). Pesos ausentes/None viram None.
        pesos_por_chave = {}
        for item in items:
            key = item[1]
            peso = pesos.get((func_id, key))
            if peso is None:
                pesos_por_chave[key] = None
            else:
                try:
                    pesos_por_chave[key] = max(0, min(100, int(peso)))
                except (TypeError, ValueError):
                    pesos_por_chave[key] = None

        com_peso = {k: v for k, v in pesos_por_chave.items() if v is not None}
        sem_peso = [k for k, v in pesos_por_chave.items() if v is None]

        if not com_peso:
            # Caminho histórico: divisão igual entre N atividades.
            horas_norm = max_horas / n if n > 0 else 0.0
            for item in items:
                meta = tuple(item[3:]) if len(item) > 3 else ()
                resultado.append(
                    (item[0], item[1], horas_norm) + meta
                )
            continue

        # Há pelo menos um peso definido — calcular fração por chave.
        soma_pesos = sum(com_peso.values())
        fracoes: dict = {}
        if not sem_peso:
            # Todas com peso: distribuição proporcional a soma_pesos.
            # Se soma_pesos==0 → todas as horas viram 0 (caso extremo).
            if soma_pesos > 0:
                for k, v in com_peso.items():
                    fracoes[k] = v / soma_pesos
            else:
                for k in com_peso:
                    fracoes[k] = 0.0
        else:
            # Misto: peso conhecido = v/100; restante /n_sem_peso entre
            # as None. Se sum_known >= 100, sobra 0 para as None.
            restante = max(0.0, 100.0 - soma_pesos)
            cota_sem = (restante / len(sem_peso)) / 100.0 if sem_peso else 0.0
            for k, v in com_peso.items():
                fracoes[k] = v / 100.0
            for k in sem_peso:
                fracoes[k] = cota_sem

        for item in items:
            key = item[1]
            frac = fracoes.get(key, 0.0)
            horas_norm = max_horas * frac
            meta = tuple(item[3:]) if len(item) > 3 else ()
            resultado.append(
                (item[0], item[1], horas_norm) + meta
            )
    return resultado
