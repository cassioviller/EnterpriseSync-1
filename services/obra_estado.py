"""Máquina de estados da Obra — Fase 2.

Este módulo é o **único** lugar autorizado a conhecer o grafo de estados da
obra. Antes dele, quatro pontos escreviam `Obra.status` livremente:
`models.py:297` (default), `event_manager.py:1018` (cascata da proposta),
`views/obras.py:279`/`:393` (criação) e `views/obras.py:863` (edição) —
nenhum validava nada. A única "transição" existente era uma comparação de
string normalizada, feita DEPOIS do commit, só para disparar webhook
(`views/obras.py:963-979`).

O molde é `CronogramaImportacao`, o único state machine real do sistema,
com sua trilha em `CronogramaImportacaoEvento` e o log estruturado de
`services/cronograma_observabilidade.log_transicao`. Repetimos a forma:
grafo explícito, transição que grava evento, log que nunca derruba o fluxo.

Esta task entrega só a lógica pura — nada aqui toca o banco. `transitar()`
e a persistência chegam nas Tasks 2-4.

Nada aqui commita. Quem chama é dono da transação — mesmo contrato dos
handlers de evento (`event_manager.py:882-887`).
"""
from __future__ import annotations

import logging
import unicodedata

from models import EstadoObra

logger = logging.getLogger('obra.estado')


class EstadoDesconhecido(ValueError):
    """Texto que não corresponde a nenhum `EstadoObra`."""


class TransicaoInvalida(ValueError):
    """Transição recusada pelo grafo, pela autorização ou por falta de motivo."""


# ── O grafo ──────────────────────────────────────────────────────────
# Ler como "de → destinos permitidos". CANCELADA é terminal de
# propósito: reviver obra cancelada é obra nova, com proposta nova.
TRANSICOES: dict[EstadoObra, tuple[EstadoObra, ...]] = {
    EstadoObra.PLANEJAMENTO: (EstadoObra.EM_EXECUCAO, EstadoObra.CANCELADA),
    EstadoObra.EM_EXECUCAO: (EstadoObra.PAUSADA, EstadoObra.CONCLUIDA,
                             EstadoObra.CANCELADA),
    EstadoObra.PAUSADA: (EstadoObra.EM_EXECUCAO, EstadoObra.CANCELADA),
    EstadoObra.CONCLUIDA: (EstadoObra.EM_EXECUCAO,),
    EstadoObra.CANCELADA: (),
}

# Rótulo humano — é TAMBÉM o valor gravado no campo legado `Obra.status`
# por write-through. Mudar um destes textos muda o que ~40 templates e
# queries leem. Todos cabem em String(20), o tipo da coluna legada;
# `test_rotulo_cabe_na_coluna_legada` trava isso.
ROTULOS: dict[EstadoObra, str] = {
    EstadoObra.PLANEJAMENTO: 'Planejamento',
    EstadoObra.EM_EXECUCAO: 'Em andamento',
    EstadoObra.PAUSADA: 'Pausada',
    EstadoObra.CONCLUIDA: 'Concluída',
    EstadoObra.CANCELADA: 'Cancelada',
}

# `Obra.ativo` deixa de ser eixo independente e passa a derivar daqui.
# A UI já trata ativo=False como "Concluída / Inativa"
# (templates/obras_moderno.html:803,819) — isto só torna explícito.
ESTADOS_INATIVOS: frozenset[EstadoObra] = frozenset(
    {EstadoObra.CONCLUIDA, EstadoObra.CANCELADA})

# Transições que exigem motivo escrito. Critério: toda transição que
# CONTRARIA a expectativa (paralisar, cancelar, reabrir) precisa de
# rastro; as que a confirmam (entregar, retomar) não.
TRANSICOES_QUE_EXIGEM_MOTIVO: frozenset[tuple[EstadoObra, EstadoObra]] = frozenset({
    (EstadoObra.PLANEJAMENTO, EstadoObra.CANCELADA),
    (EstadoObra.EM_EXECUCAO, EstadoObra.PAUSADA),
    (EstadoObra.EM_EXECUCAO, EstadoObra.CANCELADA),
    (EstadoObra.PAUSADA, EstadoObra.CANCELADA),
    (EstadoObra.CONCLUIDA, EstadoObra.EM_EXECUCAO),
})

# Autoridade mínima por transição.
#   'admin'  → apenas TipoUsuario.ADMIN / SUPER_ADMIN do tenant
#   'gestor' → o acima, OU quem tem UsuarioObra(papel=GESTOR) nesta obra
# Tem que cobrir exatamente os pares de `TRANSICOES`: um par ausente cairia
# no default 'admin' de `autoridade_necessaria` sem ninguém perceber, e um
# par sobrando descreveria autoridade para uma transição que o grafo recusa.
AUTORIDADE: dict[tuple[EstadoObra, EstadoObra], str] = {
    (EstadoObra.PLANEJAMENTO, EstadoObra.EM_EXECUCAO): 'admin',
    (EstadoObra.PLANEJAMENTO, EstadoObra.CANCELADA): 'admin',
    (EstadoObra.EM_EXECUCAO, EstadoObra.PAUSADA): 'gestor',
    (EstadoObra.EM_EXECUCAO, EstadoObra.CONCLUIDA): 'gestor',
    (EstadoObra.EM_EXECUCAO, EstadoObra.CANCELADA): 'admin',
    (EstadoObra.PAUSADA, EstadoObra.EM_EXECUCAO): 'gestor',
    (EstadoObra.PAUSADA, EstadoObra.CANCELADA): 'admin',
    (EstadoObra.CONCLUIDA, EstadoObra.EM_EXECUCAO): 'admin',
}


def _sem_acento(texto: str) -> str:
    """'Concluída' → 'concluida'. Mesma técnica de views/obras.py:969-973."""
    texto = (texto or '').strip().lower()
    return ''.join(c for c in unicodedata.normalize('NFKD', texto)
                   if not unicodedata.combining(c))


# Mapa do texto legado → estado. Chaves já normalizadas por `_sem_acento`.
# Cobre as grafias que existem no banco e no código (o dropdown editável do
# tenant, `forms.py:42`, o default do modelo) e as variantes plausíveis de
# um tenant que editou o dropdown `obra_status`.
_MAPA_LEGADO: dict[str, EstadoObra] = {
    'planejamento': EstadoObra.PLANEJAMENTO,
    'planejada': EstadoObra.PLANEJAMENTO,
    'planejado': EstadoObra.PLANEJAMENTO,
    'em andamento': EstadoObra.EM_EXECUCAO,
    'andamento': EstadoObra.EM_EXECUCAO,
    'em execucao': EstadoObra.EM_EXECUCAO,
    'em_execucao': EstadoObra.EM_EXECUCAO,
    'execucao': EstadoObra.EM_EXECUCAO,
    'ativo': EstadoObra.EM_EXECUCAO,
    'ativa': EstadoObra.EM_EXECUCAO,
    'pausada': EstadoObra.PAUSADA,
    'pausado': EstadoObra.PAUSADA,
    'paralisada': EstadoObra.PAUSADA,
    'paralisado': EstadoObra.PAUSADA,
    'concluida': EstadoObra.CONCLUIDA,
    'concluido': EstadoObra.CONCLUIDA,
    'finalizada': EstadoObra.CONCLUIDA,
    'finalizado': EstadoObra.CONCLUIDA,
    'entregue': EstadoObra.CONCLUIDA,
    'cancelada': EstadoObra.CANCELADA,
    'cancelado': EstadoObra.CANCELADA,
    'distratada': EstadoObra.CANCELADA,
}


def coagir(valor) -> EstadoObra:
    """Aceita `EstadoObra`, o `.value` ('em_execucao') ou o nome
    ('EM_EXECUCAO'). Levanta `EstadoDesconhecido` para o resto.

    Deliberadamente estrito: NÃO aceita rótulo humano ('Em andamento').
    Rótulo é saída, não entrada — aceitá-lo abriria uma segunda porta de
    escrita com o vocabulário que esta fase está fechando. Quem tem texto
    legado usa `estado_do_status_legado`, que devolve None em vez de
    levantar.
    """
    if isinstance(valor, EstadoObra):
        return valor
    if isinstance(valor, str):
        bruto = valor.strip()
        for membro in EstadoObra:
            if bruto == membro.value or bruto.upper() == membro.name:
                return membro
    raise EstadoDesconhecido(f'estado desconhecido: {valor!r}')


def estado_do_status_legado(status: str | None) -> EstadoObra | None:
    """Traduz o texto livre de `Obra.status` em estado, ou None.

    None significa "valor customizado que o mapa não conhece" — quem chama
    decide (a migration 231 cai numa regra de derivação por `Obra.ativo`;
    o relatório de censo lista para revisão humana).
    """
    if not status:
        return None
    return _MAPA_LEGADO.get(_sem_acento(status))


def transicoes_possiveis(estado) -> tuple[EstadoObra, ...]:
    """Destinos permitidos a partir de `estado` (aceita str ou enum)."""
    return TRANSICOES.get(coagir(estado), ())


def pode_transitar(de, para) -> bool:
    """Só o grafo. Autorização e motivo são checados em `transitar`."""
    try:
        return coagir(para) in transicoes_possiveis(de)
    except EstadoDesconhecido:
        return False


def exige_motivo(de, para) -> bool:
    return (coagir(de), coagir(para)) in TRANSICOES_QUE_EXIGEM_MOTIVO


def autoridade_necessaria(de, para) -> str:
    """'admin' ou 'gestor'. Transição fora do grafo é tratada como 'admin'."""
    return AUTORIDADE.get((coagir(de), coagir(para)), 'admin')
