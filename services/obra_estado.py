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

from models import EstadoObra
# A normalização de acento/caixa vem de `utils.status_obra`, não é
# reimplementada aqui. Aquele módulo se declara "a única fonte da verdade do
# vocabulário" de `Obra.status` (Fase 0.6 / D5) e já intercepta toda escrita
# pelo `@validates('status')` de models.py:415 — inclusive o write-through
# desta fase. Uma cópia local seria a TERCEIRA implementação da mesma regra
# (a primeira foi o `_norm` de views/obras.py, que aquele módulo substituiu)
# e poderia divergir em silêncio do vocabulário que ela deveria espelhar.
from utils.status_obra import chave_status as _sem_acento

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


# Mapa do texto legado → estado. Chaves já normalizadas por `_sem_acento`.
# Cobre as grafias que existem no banco e no código (o dropdown editável do
# tenant, `forms.py:44`, o default do modelo) e as variantes plausíveis de
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


def estado_atual(obra) -> EstadoObra:
    """Estado corrente da obra, tolerante a linha legada.

    Se `obra.estado` vier vazio (obra inserida por SQL cru, ou a janela em
    que a migration 231 falhou e ainda não foi retentada), cai no texto de
    `obra.status` e, em último caso, no eixo `obra.ativo`. Nunca levanta —
    quem lê o estado de uma obra não pode ser derrubado por dado sujo.

    A ordem abaixo é a MESMA de `migrations._CASE_DERIVA_ESTADO_OBRA`, e tem
    que continuar sendo: a regra de derivação vive em dois lugares, um em SQL
    (o backfill) e outro aqui em Python (o fallback de runtime), e duas
    implementações da mesma regra divergem. Divergiam, aliás, exatamente em
    `status='Em andamento'` + `ativo=False` — o SQL diz 'concluida' porque
    `ativo` vence, e a primeira versão desta função consultava `status`
    primeiro. `test_derivacao_sql_e_python_concordam` compara as duas.

    Ordem canônica:
      a) status mapeia para 'cancelada'  → cancelada
      b) ativo = false                   → concluida
      c) status mapeia para algo         → esse algo
      d) resto                           → em_execucao
    """
    try:
        return coagir(getattr(obra, 'estado', None))
    except EstadoDesconhecido:
        pass
    do_legado = estado_do_status_legado(getattr(obra, 'status', None))
    if do_legado is EstadoObra.CANCELADA:          # (a)
        return EstadoObra.CANCELADA
    if getattr(obra, 'ativo', True) is False:      # (b) — ativo vence status
        return EstadoObra.CONCLUIDA
    if do_legado is not None:                      # (c)
        return do_legado
    return EstadoObra.EM_EXECUCAO                  # (d)


def aplicar_estado(obra, estado: EstadoObra) -> None:
    """Escreve o estado e sincroniza os dois campos derivados.

    `status` e `ativo` continuam existindo porque dezenas de templates e
    queries os leem. Eles deixam de ser fonte de verdade e passam a ser
    espelho — `estado` é quem manda.

    O rótulo gravado em `status` passa ainda pelo `@validates('status')` de
    `models.py`, que o normaliza contra `utils.status_obra`. Os cinco rótulos
    são canônicos lá justamente para atravessarem esse validador intactos;
    `test_write_through_passa_pelo_validates_sem_ser_reescrito` trava isso.
    """
    obra.estado = estado.value
    obra.status = ROTULOS[estado]
    obra.ativo = estado not in ESTADOS_INATIVOS


def transitar(obra, para, usuario_id=None, motivo: str = '',
              detalhes: dict | None = None):
    """Executa uma transição validada e devolve o registro de histórico.

    Valida, nesta ordem: vocabulário → grafo → motivo obrigatório.
    NÃO valida autorização — isso é `pode_transitar_como`, chamado pela rota,
    porque este serviço também é usado por migração e por seed, onde não
    existe `current_user`.

    Não commita: a rota (ou o handler) é dona da transação, mesmo contrato de
    `propagar_proposta_para_obra`. Faz `flush` para que o id do registro
    exista para o chamador.
    """
    from models import ObraTransicaoEstado, db

    de = estado_atual(obra)
    destino = coagir(para)

    if destino not in TRANSICOES.get(de, ()):
        permitidos = ', '.join(e.value for e in TRANSICOES.get(de, ())) or '(nenhum)'
        raise TransicaoInvalida(
            f'Obra {getattr(obra, "id", "?")}: transição '
            f'{de.value} → {destino.value} não é permitida. '
            f'A partir de {de.value} só é possível ir para: {permitidos}.')

    motivo_limpo = (motivo or '').strip()
    if (de, destino) in TRANSICOES_QUE_EXIGEM_MOTIVO and not motivo_limpo:
        raise TransicaoInvalida(
            f'A transição {de.value} → {destino.value} exige motivo escrito.')

    aplicar_estado(obra, destino)

    registro = ObraTransicaoEstado(
        obra_id=obra.id,
        admin_id=obra.admin_id,
        estado_de=de.value,
        estado_para=destino.value,
        motivo=motivo_limpo or None,
        detalhes=detalhes or None,
        usuario_id=usuario_id,
    )
    db.session.add(registro)
    db.session.flush()

    # Log estruturado, no molde de services/cronograma_observabilidade.
    # Nunca derruba o fluxo.
    try:
        logger.info(
            'evento=transicao obra_id=%s admin_id=%s de=%s para=%s '
            'usuario_id=%s motivo=%r',
            obra.id, obra.admin_id, de.value, destino.value,
            usuario_id, motivo_limpo[:120])
    except Exception:
        logger.debug('falha ao logar transição de obra', exc_info=True)

    return registro


def pode_transitar_como(obra, para, usuario=None) -> bool:
    """`usuario` pode disparar esta transição nesta obra?

    Dois eixos, ambos obrigatórios (Fase 1):
      • tenant  — a obra tem de pertencer ao tenant do usuário;
      • obra    — 'admin' exige TipoUsuario.ADMIN/SUPER_ADMIN;
                  'gestor' aceita também quem tem UsuarioObra(GESTOR).

    Falha FECHADA: anônimo, tenant divergente, transição fora do grafo ou
    estado ilegível devolvem False, nunca exceção. A rota converte isso em
    403/404; o serviço não decide resposta HTTP.

    `usuario=None` significa "use o current_user".
    """
    from models import PapelObra, TipoUsuario, UsuarioObra
    from utils.identidade import tenant_do_usuario

    if obra is None:
        return False

    if usuario is None:
        try:
            from flask_login import current_user
            if not current_user.is_authenticated:
                return False
            usuario = current_user
        except Exception:
            return False

    tenant = tenant_do_usuario(usuario)
    if tenant is None or obra.admin_id != tenant:
        return False

    try:
        de = estado_atual(obra)
        destino = coagir(para)
    except EstadoDesconhecido:
        return False

    if destino not in TRANSICOES.get(de, ()):
        return False

    e_admin = usuario.tipo_usuario in (TipoUsuario.ADMIN, TipoUsuario.SUPER_ADMIN)
    if e_admin:
        return True

    if autoridade_necessaria(de, destino) == 'admin':
        return False

    # 'gestor': exige vínculo explícito com papel GESTOR nesta obra.
    #
    # Consultamos `UsuarioObra` direto em vez de usar
    # `utils.autorizacao.papel_na_obra` porque aquela função devolve GESTOR
    # para TODO usuário do tenant enquanto `escopo_obra_ativo` está desligada
    # — deliberado, para o deploy da Fase 1 não tirar acesso de ninguém, e
    # correto para LEITURA. Para ESCRITA DE ESTADO seria um furo: hoje 586
    # dos 607 tenants estão com a flag desligada, então qualquer usuário
    # autenticado poderia pausar ou concluir obra.
    # `test_autorizacao_nao_afrouxa_com_a_flag_de_escopo_desligada` trava isso.
    vinculo = UsuarioObra.query.filter_by(
        usuario_id=usuario.id, obra_id=obra.id, ativo=True).first()
    return vinculo is not None and vinculo.papel == PapelObra.GESTOR
