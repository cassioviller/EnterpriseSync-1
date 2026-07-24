"""Parser do texto de predecessoras em formato MS Project (Fase 1, editor v2).

Gramática (por entrada, após ``strip()``/``upper()``):

    ^(\\d+)(TI|II|TT|IT)?([+-]\\d+)?$

- entradas separadas por ``;`` (``,`` tolerada);
- número = LINHA VISUAL da grade (1-based), conforme
  `utils.cronograma_engine.ordenar_arvore_visual` — nunca o id da tarefa;
- sem tipo = ``TI`` (Término→Início); sem lag = 0;
- string vazia = remover todos os vínculos (lista vazia).

Este módulo é PURO (sem DB, sem import do scheduler): devolve
`VinculoParseado` leve; a camada de API adapta para `VinculoSpec` /
`TarefaVinculo`. Os erros (`ErroParsePredecessora`) carregam mensagem em
português pronta para resposta HTTP 400.

Validações de auto-referência e de tarefa-resumo dependem de contexto que só
o chamador tem — ele as habilita passando `sucessora_id` (id da tarefa que
está recebendo as predecessoras) e `ids_resumo` (ids das tarefas que têm
filhas na grade). Se omitidos, essas duas checagens NÃO são feitas aqui e
passam a ser responsabilidade do chamador.
"""
from __future__ import annotations

import re
from dataclasses import dataclass

TIPOS_VALIDOS = ('TI', 'II', 'TT', 'IT')

# Gramática oficial de uma entrada (já normalizada com strip()/upper()).
_ENTRADA_RE = re.compile(r'^(\d+)(TI|II|TT|IT)?([+-]\d+)?$')

# Forma "quase válida" com tipo de 2 letras desconhecido (ex.: 12XX+3) —
# usada apenas para diferenciar "tipo inválido" de "formato inválido".
_ENTRADA_TIPO_QUALQUER_RE = re.compile(r'^(\d+)([A-Z]{2})([+-]\d+)?$')


class ErroParsePredecessora(ValueError):
    """Erro de parse/validação de predecessoras (mensagem pt-BR, 400-friendly)."""


@dataclass(frozen=True)
class VinculoParseado:
    """Vínculo resolvido para ids de tarefa (sem dependência do scheduler)."""
    predecessora_id: int
    tipo: str        # 'TI' | 'II' | 'TT' | 'IT'
    lag_dias: int


def parsear_predecessoras(
    texto: str | None,
    linha_para_tarefa: dict[int, int],
    *,
    sucessora_id: int | None = None,
    ids_resumo: set[int] | None = None,
) -> list[VinculoParseado]:
    """Converte o texto digitado na célula de predecessoras em vínculos.

    - `linha_para_tarefa`: linha visual (1-based) → id da tarefa, construído
      pelo chamador via `ordenar_arvore_visual`;
    - `sucessora_id`: se informado, rejeita auto-referência;
    - `ids_resumo`: se informado, rejeita vínculo com tarefa-resumo (pai).

    String vazia/None → lista vazia (= remover todos os vínculos).
    Linha repetida na mesma string → erro.
    Levanta `ErroParsePredecessora` com mensagem em português.
    """
    if texto is None:
        return []
    ids_resumo = ids_resumo or set()

    vinculos: list[VinculoParseado] = []
    linhas_vistas: set[int] = set()

    for entrada in re.split(r'[;,]', texto):
        entrada = entrada.strip().upper()
        if not entrada:
            continue

        m = _ENTRADA_RE.match(entrada)
        if not m:
            m_tipo = _ENTRADA_TIPO_QUALQUER_RE.match(entrada)
            if m_tipo:
                raise ErroParsePredecessora(
                    f"Tipo de vínculo inválido: '{m_tipo.group(2)}' "
                    "(use TI, II, TT ou IT)"
                )
            raise ErroParsePredecessora(
                f"Formato inválido: '{entrada}'. Exemplos: 12, 12TI+3, 12II-2"
            )

        linha = int(m.group(1))
        tipo = m.group(2) or 'TI'
        lag = int(m.group(3)) if m.group(3) else 0

        if linha in linhas_vistas:
            raise ErroParsePredecessora(
                f"Linha {linha} informada mais de uma vez"
            )
        linhas_vistas.add(linha)

        if linha not in linha_para_tarefa:
            raise ErroParsePredecessora(f"Linha {linha} não existe na grade")
        tarefa_id = linha_para_tarefa[linha]

        if sucessora_id is not None and tarefa_id == sucessora_id:
            raise ErroParsePredecessora(
                "Uma tarefa não pode ser predecessora dela mesma"
            )
        if tarefa_id in ids_resumo:
            raise ErroParsePredecessora(
                f"Linha {linha} é uma tarefa-resumo — vincule apenas tarefas-folha"
            )

        vinculos.append(VinculoParseado(tarefa_id, tipo, lag))

    return vinculos


def _campo(vinculo, nome: str, default):
    """Lê `nome` de um vínculo que pode ser objeto (atributos) ou dict."""
    if isinstance(vinculo, dict):
        valor = vinculo.get(nome, default)
    else:
        valor = getattr(vinculo, nome, default)
    return default if valor is None else valor


def formatar_predecessoras(vinculos, tarefa_para_linha: dict[int, int]) -> str:
    """Inverso de `parsear_predecessoras`: vínculos → texto canônico.

    - TI com lag 0 → só o número da linha (``12``);
    - lag 0 com outro tipo → ``12II``;
    - lag ≠ 0 → sinal explícito: ``12TI+3`` / ``12II-2``;
    - junção com ``;`` sem espaços; lista vazia → ``''``.

    Aceita qualquer sequência de itens com `predecessora_id`/`tipo`/`lag_dias`
    (atributos ou chaves de dict) — `VinculoParseado`, `TarefaVinculo`, etc.
    `tarefa_para_linha`: id da tarefa → linha visual (1-based).
    """
    partes: list[str] = []
    for v in vinculos:
        pred_id = _campo(v, 'predecessora_id', None)
        tipo = str(_campo(v, 'tipo', 'TI')).upper()
        lag = int(_campo(v, 'lag_dias', 0))

        linha = tarefa_para_linha.get(pred_id)
        if linha is None:
            raise ErroParsePredecessora(
                f"Tarefa {pred_id} não está na grade"
            )

        if tipo == 'TI' and lag == 0:
            partes.append(str(linha))
        elif lag == 0:
            partes.append(f"{linha}{tipo}")
        else:
            partes.append(f"{linha}{tipo}{lag:+d}")
    return ';'.join(partes)
