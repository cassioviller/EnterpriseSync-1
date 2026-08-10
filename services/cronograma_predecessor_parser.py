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

# O MS Project em inglês (e muito hábito de usuário) grafa FS/SS/FF/SF —
# aceitos como apelidos e normalizados para o vocabulário pt-BR.
_APELIDOS_TIPO = {'FS': 'TI', 'SS': 'II', 'FF': 'TT', 'SF': 'IT'}

# Gramática de uma entrada (normalizada com strip()/upper() e SEM espaços
# internos — o Project escreve "12TI+3 dias" e aceita espaços à vontade).
# O lag pode vir com a unidade que o Project exibe: "+3 dias", "+3d",
# "+3dia". Só dia útil — "dd" (dias decorridos) e "%" são recusados adiante
# com mensagem própria.
_ENTRADA_RE = re.compile(
    r'^(\d+)(TI|II|TT|IT|FS|SS|FF|SF)?([+-]\d+)(?:D|DIA|DIAS)?$'
    r'|^(\d+)(TI|II|TT|IT|FS|SS|FF|SF)?$')

# Formas "quase válidas", para o erro dizer O QUE está errado:
_ENTRADA_TIPO_QUALQUER_RE = re.compile(r'^(\d+)([A-Z]{2})([+-]\d+)?[A-Z]*$')
_LAG_PERCENTUAL_RE = re.compile(r'^\d+[A-Z]{0,2}[+-]\d+%$')
_LAG_DECORRIDO_RE = re.compile(r'^\d+[A-Z]{0,2}[+-]\d+DD$')


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
        # Espaços somem ANTES do match: o Project escreve "12TI+3 dias" e
        # tolera "12 TI + 3" — quem digita igual ao Project não pode errar.
        # EXCETO dígito-espaço-dígito ("12 15"): colapsar viraria a linha
        # 1215 e criaria um vínculo errado em silêncio — é ';' esquecido.
        bruto = entrada.strip().upper()
        if re.search(r'\d\s+\d', bruto):
            raise ErroParsePredecessora(
                f"Formato inválido: '{bruto}' — separe as predecessoras "
                f"com ';' (ex.: 12; 15TI+3)"
            )
        entrada = re.sub(r'\s+', '', bruto)
        if not entrada:
            continue

        m = _ENTRADA_RE.match(entrada)
        if not m:
            if _LAG_PERCENTUAL_RE.match(entrada):
                raise ErroParsePredecessora(
                    f"Lag percentual não é suportado: '{entrada}' — "
                    "use lag em dias úteis (ex.: 12TI+3)"
                )
            if _LAG_DECORRIDO_RE.match(entrada):
                raise ErroParsePredecessora(
                    f"Dias decorridos ('dd') não são suportados: '{entrada}' "
                    "— o lag é sempre em dias ÚTEIS (ex.: 12TI+3)"
                )
            m_tipo = _ENTRADA_TIPO_QUALQUER_RE.match(entrada)
            if m_tipo and m_tipo.group(2) not in TIPOS_VALIDOS \
                    and m_tipo.group(2) not in _APELIDOS_TIPO:
                raise ErroParsePredecessora(
                    f"Tipo de vínculo inválido: '{m_tipo.group(2)}' "
                    "(use TI, II, TT ou IT — ou FS, SS, FF, SF)"
                )
            raise ErroParsePredecessora(
                f"Formato inválido: '{entrada}'. Exemplos: 12, 12TI+3, "
                f"12II-2, 12FS+3 dias"
            )

        # O regex tem duas alternativas (com e sem lag) — grupos 1-3 ou 4-5.
        linha = int(m.group(1) or m.group(4))
        tipo = (m.group(2) or m.group(5)) or 'TI'
        tipo = _APELIDOS_TIPO.get(tipo, tipo)
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
