#!/usr/bin/env python3
"""Ciclo de vida do RDO — SIGE Fase 5.

ANTES desta fase o RDO não tinha ciclo de vida nenhum. A coluna
`RDO.status` nascia `'Finalizado'` (models.py:1128, comentário literal
"Task #12: RDO sempre Finalizado") e oito caminhos de escrita gravavam
esse valor na mão:

    views/rdo.py:698, 1540, 1630, 1755, 2614, 3967
    rdo_editar_sistema.py:221
    crud_rdo_completo.py:338, 572

Consequência prática: um RDO de três meses atrás podia ser reescrito por
qualquer usuário do tenant, sem registro de quem, quando ou por quê — e o
custo de mão de obra já lançado a partir dele ficava pendurado num
documento que mudou embaixo.

Este módulo é o dono único do estado. A coluna `RDO.status` NÃO é tocada:
≥9 consumidores filtram por `status == 'Finalizado'`
(cronograma_views.py:2458,2488; portal_obras_views.py:239;
services/medicao_service.py:243; services/rdo_custos.py:330;
services/metricas_produtividade.py:186,972,1302,1320,1397,1416) e mudar
aquele valor sumiria com o RDO do portal do cliente e das métricas.

O padrão de máquina de estados aqui é o mesmo de `CronogramaImportacao`
(models.py:5639) e de `services/obra_estado.py` (Fase 2) — dicionário de
transições válidas + tabela de trilha auditada. Se a Fase 6 extrair um
helper genérico de versionamento encadeado, este módulo passa a
consumi-lo sem mudar a API pública.
"""
from __future__ import annotations

import contextlib
import contextvars
import logging

from models import RDO, RDOTransicaoEstado, db

logger = logging.getLogger('rdo.ciclo_vida')

# ── Estados ──────────────────────────────────────────────────────────
RASCUNHO = 'rascunho'      # em preenchimento; edição livre
PREENCHIDO = 'preenchido'  # submetido; custos lançados; ainda corrigível
ASSINADO = 'assinado'      # autoria registrada; IMUTÁVEL
APROVADO = 'aprovado'      # aceite do gestor da obra; IMUTÁVEL, terminal
RETIFICADO = 'retificado'  # substituído por um RDO retificador; terminal

ESTADOS = {RASCUNHO, PREENCHIDO, ASSINADO, APROVADO, RETIFICADO}

# Estado em que os RDOs históricos caíram no backfill da migration 260
# (22.907 em dev, 24/07). É o equivalente semântico do 'Finalizado' de
# hoje.
ESTADO_LEGADO = PREENCHIDO

TRANSICOES_VALIDAS = {
    # Submeter o dia. Depois disso os custos de mão de obra existem.
    RASCUNHO: {PREENCHIDO},
    # Reabrir (só GESTOR — a autorização mora na rota) ou assinar.
    PREENCHIDO: {RASCUNHO, ASSINADO},
    # Assinado não volta. Ou é aprovado, ou é retificado por outro RDO.
    ASSINADO: {APROVADO, RETIFICADO},
    APROVADO: {RETIFICADO},
    RETIFICADO: set(),
}

# A partir daqui o documento não aceita mais escrita — nem nele, nem nos
# filhos (mão de obra, subatividades, fotos, equipamentos, ocorrências,
# apontamentos de cronograma). Corrigir é criar um RDO retificador.
ESTADOS_IMUTAVEIS = {ASSINADO, APROVADO, RETIFICADO}

# Rótulos para a UI (pt-BR).
ROTULOS = {
    RASCUNHO: 'Rascunho',
    PREENCHIDO: 'Preenchido',
    ASSINADO: 'Assinado',
    APROVADO: 'Aprovado',
    RETIFICADO: 'Retificado',
}

# Classe de cor Bootstrap por estado (usado no selo do template).
CORES = {
    RASCUNHO: 'secondary',
    PREENCHIDO: 'primary',
    ASSINADO: 'success',
    APROVADO: 'success',
    RETIFICADO: 'warning',
}


class CicloVidaInvalido(ValueError):
    """Base das violações de ciclo de vida (mensagem apta à UI)."""


class TransicaoInvalida(CicloVidaInvalido):
    """Transição fora de TRANSICOES_VALIDAS, ou estado desconhecido."""


class RDOImutavel(CicloVidaInvalido):
    """Tentativa de escrever num RDO assinado/aprovado/retificado."""


# ── Bypass controlado da guarda de imutabilidade ─────────────────────
# A guarda (services/rdo_ciclo_vida._guarda_imutabilidade, Task 4) barra
# QUALQUER escrita em RDO imutável. Mas as próprias transições de estado
# — assinado → aprovado, assinado → retificado — precisam escrever no
# RDO. Este ContextVar é a única porta: quem entra aqui declara que sabe
# o que está fazendo, e o teste
# test_bypass_nao_vaza_entre_transacoes prova que ele volta ao normal.
_BYPASS = contextvars.ContextVar('rdo_ciclo_vida_bypass', default=False)


@contextlib.contextmanager
def escrita_de_ciclo_de_vida():
    """Libera a guarda de imutabilidade dentro do bloco.

    Uso EXCLUSIVO deste módulo e de services/rdo_assinatura.py. Não use
    em rota, view ou script: se você precisa disso, o que você quer é um
    RDO retificador.
    """
    token = _BYPASS.set(True)
    try:
        yield
    finally:
        _BYPASS.reset(token)


def bypass_ativo() -> bool:
    return _BYPASS.get()


# ── API pública ──────────────────────────────────────────────────────
def estado_de(rdo) -> str:
    """Estado do RDO, com fallback para o legado.

    RDOs criados por caminhos que ainda não conhecem a coluna (ou linhas
    em memória antes do flush) devolvem RASCUNHO, nunca None.
    """
    return getattr(rdo, 'estado', None) or RASCUNHO


def e_imutavel(rdo) -> bool:
    return estado_de(rdo) in ESTADOS_IMUTAVEIS


def garantir_editavel(rdo) -> None:
    """Levanta RDOImutavel se o RDO não aceita mais escrita.

    É o contrato oferecido ao plano irmão (apontamento percentual): chame
    antes de gravar apontamento. Mesmo sem a chamada, a guarda
    `before_flush` barra — isto aqui só dá uma mensagem melhor e mais
    cedo.
    """
    if e_imutavel(rdo):
        raise RDOImutavel(
            f'RDO {getattr(rdo, "numero_rdo", rdo.id)} está '
            f'{ROTULOS[estado_de(rdo)].lower()} e não aceita mais edição. '
            f'Para corrigir, emita um RDO retificador.')


def pode_transicionar(rdo, novo_estado: str) -> bool:
    if novo_estado not in ESTADOS:
        return False
    atual = estado_de(rdo)
    return novo_estado in TRANSICOES_VALIDAS.get(atual, set())


def transicionar(rdo, novo_estado: str, *, usuario=None, funcionario=None,
                 motivo=None, ip=None, detalhes=None) -> RDOTransicaoEstado | None:
    """Muda o estado do RDO e grava a trilha. NÃO faz commit.

    Devolve a `RDOTransicaoEstado` criada, ou `None` quando o RDO já
    estava no estado pedido (no-op deliberado: reenvio de formulário não
    pode poluir a trilha).

    Levanta `TransicaoInvalida` para estado desconhecido ou transição
    fora de `TRANSICOES_VALIDAS`. A AUTORIZAÇÃO (quem pode fazer o quê)
    NÃO mora aqui — mora na rota, com `utils.autorizacao`. Este módulo
    responde "essa transição existe?", não "você pode?".
    """
    if novo_estado not in ESTADOS:
        raise TransicaoInvalida(
            f'Estado desconhecido: {novo_estado!r}. '
            f'Válidos: {sorted(ESTADOS)}')

    atual = estado_de(rdo)
    if atual == novo_estado:
        logger.debug('[ciclo-vida] rdo=%s já está em %s — no-op',
                     rdo.id, novo_estado)
        return None

    if novo_estado not in TRANSICOES_VALIDAS.get(atual, set()):
        raise TransicaoInvalida(
            f'RDO {getattr(rdo, "numero_rdo", rdo.id)}: transição '
            f'{atual} → {novo_estado} não é permitida. '
            f'A partir de {atual} só cabe: '
            f'{sorted(TRANSICOES_VALIDAS.get(atual, set())) or "nada"}.')

    funcionario_id = getattr(funcionario, 'id', None)
    if funcionario_id is None and usuario is not None:
        funcionario_id = getattr(usuario, 'funcionario_id', None)

    admin_id = rdo.admin_id or getattr(rdo.obra, 'admin_id', None)

    with escrita_de_ciclo_de_vida():
        rdo.estado = novo_estado
        trilha = RDOTransicaoEstado(
            rdo_id=rdo.id,
            admin_id=admin_id,
            estado_anterior=atual,
            estado_novo=novo_estado,
            usuario_id=getattr(usuario, 'id', None),
            funcionario_id=funcionario_id,
            motivo=motivo,
            ip=ip,
            detalhes=detalhes,
        )
        db.session.add(trilha)
        db.session.flush()

    logger.info('[ciclo-vida] rdo=%s %s→%s usuario=%s funcionario=%s ip=%s '
                'motivo=%r', rdo.id, atual, novo_estado,
                getattr(usuario, 'id', None), funcionario_id, ip, motivo)
    return trilha


# ── Guarda de imutabilidade ──────────────────────────────────────────
# Por que um listener de sessão em vez de editar as oito rotas de
# escrita: porque não dá para PROVAR que nenhuma foi esquecida. São oito
# lugares hoje (views/rdo.py:698,1540,1630,1755,2614,3967;
# rdo_editar_sistema.py:221; crud_rdo_completo.py:338,572), mais o
# import físico-financeiro, mais os scripts de seed. Um ponto só é
# auditável; oito não são.
#
# O molde de listener em modelo de RDO já existe no repo:
# models.py:1614 (RDOServicoSubatividade before_insert/update) e
# models.py:7649 (RDO after_insert). Aqui é `before_flush` de SESSÃO
# porque precisamos ver inserts, updates E deletes de uma vez.

# Filhos do RDO cuja escrita também é bloqueada. RDOTransicaoEstado e
# RDOAssinatura ficam DE FORA de propósito: são o registro da própria
# transição, e bloqueá-los tornaria impossível assinar.
_MODELOS_FILHOS = (
    'RDOMaoObra', 'RDOServicoSubatividade', 'RDOEquipamento',
    'RDOOcorrencia', 'RDOFoto', 'RDOApontamentoCronograma',
    'RDOSubempreitadaApontamento',
)


def _rdo_id_do_objeto(obj):
    """Devolve o rdo_id que o objeto afeta, ou None se não for do RDO."""
    nome = type(obj).__name__
    if nome == 'RDO':
        return obj.id
    if nome in _MODELOS_FILHOS:
        return getattr(obj, 'rdo_id', None)
    return None


def _registrar_guarda():
    from sqlalchemy import event as sa_event

    @sa_event.listens_for(db.session, 'before_flush')
    def _guarda_imutabilidade(session, flush_context, instances):
        if _BYPASS.get():
            return

        candidatos = {}
        for coleccao in (session.new, session.dirty, session.deleted):
            for obj in coleccao:
                rdo_id = _rdo_id_do_objeto(obj)
                if rdo_id is not None:
                    candidatos.setdefault(rdo_id, []).append(obj)

        if not candidatos:
            return

        with session.no_autoflush:
            for rdo_id, objetos in candidatos.items():
                alvo = session.get(RDO, rdo_id)
                if alvo is None:
                    continue
                # `estado` recém-atribuído nesta sessão não vale: o que
                # importa é o estado PERSISTIDO. Sem bypass, mudar estado
                # é justamente o que não pode acontecer por fora.
                from sqlalchemy import inspect as sa_inspect
                historico = sa_inspect(alvo).attrs.estado.history
                persistido = (historico.deleted[0] if historico.deleted
                              else alvo.estado)
                if persistido not in ESTADOS_IMUTAVEIS:
                    continue
                nomes = sorted({type(o).__name__ for o in objetos})
                logger.warning(
                    '[ciclo-vida] escrita BARRADA em rdo=%s (estado=%s): %s',
                    rdo_id, persistido, nomes)
                raise RDOImutavel(
                    f'RDO {alvo.numero_rdo or alvo.id} está '
                    f'{ROTULOS.get(persistido, persistido).lower()} e não '
                    f'aceita mais alteração ({", ".join(nomes)}). Para '
                    f'corrigir, emita um RDO retificador.')

    logger.info('[ciclo-vida] guarda de imutabilidade registrada')


_registrar_guarda()
