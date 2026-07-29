#!/usr/bin/env python3
"""Ciência do cliente sobre o RDO — SIGE Fase 9a.

CIÊNCIA NÃO É TRANSIÇÃO DE ESTADO, e essa é a distinção que justifica este
módulo existir em vez de um parâmetro a mais em `services/rdo_assinatura.py`.

O ciclo de vida do RDO (`rascunho → preenchido → assinado → aprovado`) é
INTERNO: quem executou, quem responde pela obra. `rdo_assinatura.assinar()`
reflete isso em duas exigências que o cliente nunca satisfaz — estado
`PREENCHIDO` e um `Funcionario` vinculado ao usuário (levanta
`SemIdentidade` sem ele). Um responsável do cliente não é funcionário da
construtora, e o RDO que ele enxerga no portal já está assinado.

A ciência é ORTOGONAL: registra que uma pessoa nomeada pelo cliente viu
aquele documento, sem mexer em `RDO.estado`. Por isso ela só é aceita sobre
RDO em estado IMUTÁVEL — não se dá ciência a documento que ainda pode
mudar debaixo da assinatura.

O que ela compartilha com a assinatura interna é o que importa para valer
como prova: mesma tabela (`RDOAssinatura`, papel `cliente`), mesmo hash
canônico (`services/rdo_hash.py`), mesmo carimbo de servidor, IP e
user-agent. O escopo jurídico continua o da Fase 5 — autoria e integridade
(MP 2.200-2/2001, art. 10, §2º), não ICP-Brasil.
"""
from __future__ import annotations

import logging

from models import ObraSignatarioCliente, RDOAssinatura, db
from services.rdo_ciclo_vida import ESTADOS_IMUTAVEIS, RETIFICADO, estado_de
from services.rdo_hash import calcular_hash

logger = logging.getLogger('rdo.ciencia')


class CienciaInvalida(Exception):
    """Recusa de ciência, com mensagem apta à UI do portal."""


def _contexto_request():
    """(ip, user_agent) do request atual, ou (None, None) fora de request.

    `request.remote_addr` e NUNCA `X-Forwarded-For` lido à mão. A primeira
    versão parseava o header e pegava o primeiro salto — que é justamente a
    parte que o CLIENTE escreve. Bastava mandar `X-Forwarded-For: 8.8.8.8`
    ao assinar para gravar esse IP num registro que este módulo apresenta
    como evidência de autoria sob a MP 2.200-2/2001. Um campo probatório
    preenchido pelo próprio interessado não prova nada.

    `ProxyFix(x_for=1)` está ativo em app.py:94 e já resolveu o IP real —
    `models.py:1567` diz isso explicitamente. Mesma implementação da irmã
    `services/rdo_assinatura._contexto_request`, e não uma cópia divergente.
    """
    try:
        from flask import request
        ip = (request.remote_addr or '') or None
        ua = (request.headers.get('User-Agent') or '')[:400] or None
        return (ip[:45] if ip else None), ua
    except Exception:
        return None, None


def motivo_inelegivel(rdo) -> str | None:
    """Por que este RDO não aceita ciência — ou None se aceita.

    Devolve o motivo em vez de um booleano porque a mensagem vai para a tela
    do cliente, e "aguardando a construtora finalizar" é muito diferente de
    "este RDO foi substituído".
    """
    estado = estado_de(rdo)
    if estado == RETIFICADO:
        return ('Este RDO foi substituído por um retificador. Dê ciência no '
                'RDO que o substituiu.')
    if estado not in ESTADOS_IMUTAVEIS:
        return ('Este RDO ainda está sendo finalizado pela construtora. '
                'A ciência fica disponível quando ele for assinado.')
    return None


def placar(rdo) -> dict:
    """Estado da ciência do RDO: quem assinou, quem falta, e se fechou.

    A lista exigida são os signatários ATIVOS da obra no momento da leitura.
    Consequência assumida (decisão de produto): incluir um 4º responsável faz
    um RDO "3 de 3" voltar a "3 de 4". Congelar a lista por RDO pediria outra
    tabela para resolver um caso raro — a lista muda pouco, e quando muda o
    efeito é justamente o desejado.

    Assinatura de quem foi DESATIVADO depois continua contando e aparecendo:
    o ato aconteceu, e `nome_signatario` é snapshot. Ela entra em `extras`,
    fora do denominador.
    """
    ativos = (ObraSignatarioCliente.query
              .filter_by(obra_id=rdo.obra_id)
              .filter(ObraSignatarioCliente.ativo.is_(True))
              .order_by(ObraSignatarioCliente.nome).all())

    assinaturas = (RDOAssinatura.query
                   .filter_by(rdo_id=rdo.id, papel=RDOAssinatura.PAPEL_CLIENTE)
                   .all())
    por_signatario = {a.signatario_cliente_id: a for a in assinaturas
                      if a.signatario_cliente_id is not None}

    # Integridade — o hash gravado só vale se alguém o conferir. UM cálculo
    # para o RDO inteiro (o payload canônico é o mesmo para todas as
    # assinaturas dele), comparado com o que cada uma guardou. Divergência
    # significa que o documento mudou DEPOIS de assinado: é exatamente o que
    # a Fase 5 quis poder provar, e precisa aparecer na tela do cliente.
    try:
        hash_atual = calcular_hash(rdo)
    except Exception:
        logger.exception('[ciencia] falha ao recalcular hash do rdo %s', rdo.id)
        hash_atual = None   # falha FECHADA: sem hash, nada é dado por íntegro

    def _integra(a):
        return bool(a is not None and hash_atual
                    and (a.algoritmo or 'sha256') == 'sha256'
                    and a.hash_conteudo == hash_atual)

    itens = [{'signatario': s,
              'assinatura': por_signatario.get(s.id),
              'integra': _integra(por_signatario.get(s.id))}
             for s in ativos]
    ids_ativos = {s.id for s in ativos}
    extras = [a for a in assinaturas
              if a.signatario_cliente_id not in ids_ativos]
    alteradas = [i for i in itens if i['assinatura'] is not None
                 and not i['integra']]

    assinados = sum(1 for i in itens if i['assinatura'] is not None)
    total = len(itens)
    return {
        'itens': itens,
        'extras': extras,
        'assinados': assinados,
        'total': total,
        # Sem responsável cadastrado não há ciência a dar — `completo` fica
        # False para a tela não anunciar conclusão de algo que ninguém podia
        # fazer.
        'completo': bool(total) and assinados == total,
        'pendentes': [i['signatario'] for i in itens if i['assinatura'] is None],
        # Assinaturas cujo hash não bate mais com o RDO de hoje.
        'alteradas': alteradas,
    }


def placar_por_rdo(obra_id: int, rdos: list) -> dict:
    """Placar de VÁRIOS RDOs de uma obra em DUAS queries — para a listagem.

    `placar()` por RDO numa lista de 20 daria 40 queries. Aqui a lista de
    signatários ativos é uma só (a obra é a mesma) e as assinaturas saem num
    único `IN`.

    Devolve `{rdo_id: {'assinados', 'total', 'completo'}}`, e SÓ para os RDOs
    que aceitam ciência — mostrar "0/3" num RDO que a construtora ainda nem
    finalizou cobraria do cliente algo que ele não pode fazer.
    """
    if not rdos:
        return {}

    total = (ObraSignatarioCliente.query
             .filter_by(obra_id=obra_id)
             .filter(ObraSignatarioCliente.ativo.is_(True)).count())
    if not total:
        return {}

    ids_elegiveis = [r.id for r in rdos if motivo_inelegivel(r) is None]
    if not ids_elegiveis:
        return {}

    ativos = {s.id for s in ObraSignatarioCliente.query
              .filter_by(obra_id=obra_id)
              .filter(ObraSignatarioCliente.ativo.is_(True)).all()}

    contagem: dict[int, int] = {}
    for a in (RDOAssinatura.query
              .filter(RDOAssinatura.rdo_id.in_(ids_elegiveis),
                      RDOAssinatura.papel == RDOAssinatura.PAPEL_CLIENTE)
              .all()):
        # Mesma regra do placar detalhado: quem foi desativado não conta no
        # numerador, senão a lista mostraria "3/2".
        if a.signatario_cliente_id in ativos:
            contagem[a.rdo_id] = contagem.get(a.rdo_id, 0) + 1

    return {rid: {'assinados': contagem.get(rid, 0), 'total': total,
                  'completo': contagem.get(rid, 0) == total}
            for rid in ids_elegiveis}


def ja_assinou(rdo, signatario) -> bool:
    return RDOAssinatura.query.filter_by(
        rdo_id=rdo.id, papel=RDOAssinatura.PAPEL_CLIENTE,
        signatario_cliente_id=signatario.id).first() is not None


def registrar_ciencia(rdo, signatario, *, observacao=None):
    """Grava a ciência de UM responsável. Não faz commit.

    Levanta `CienciaInvalida` em qualquer recusa. A dupla checagem com
    `ja_assinou` é conveniência de mensagem: o índice parcial
    `uq_rdo_assin_cliente` (migração 268) é quem garante de verdade que
    ninguém assina duas vezes o mesmo RDO.
    """
    if signatario.obra_id != rdo.obra_id:
        # Não deveria acontecer (a sessão é presa à obra), mas é a última
        # barreira antes de gravar autoria em obra alheia.
        raise CienciaInvalida('Este responsável não pertence a esta obra.')

    if not signatario.ativo:
        raise CienciaInvalida('Este acesso foi desativado pela construtora.')

    if signatario.senha_temporaria:
        raise CienciaInvalida(
            'Defina uma senha própria antes de assinar — a senha temporária '
            'foi criada pela construtora e não identifica você.')

    motivo = motivo_inelegivel(rdo)
    if motivo:
        raise CienciaInvalida(motivo)

    if ja_assinou(rdo, signatario):
        raise CienciaInvalida('Você já deu ciência neste RDO.')

    ip, user_agent = _contexto_request()
    assinatura = RDOAssinatura(
        rdo_id=rdo.id,
        admin_id=rdo.admin_id or rdo.obra.admin_id,
        usuario_id=None,               # não é usuário do sistema, de propósito
        funcionario_id=None,
        signatario_cliente_id=signatario.id,
        papel=RDOAssinatura.PAPEL_CLIENTE,
        nome_signatario=(signatario.nome or '')[:200],
        cargo_signatario=(signatario.cargo or '')[:120] or None,
        hash_conteudo=calcular_hash(rdo),
        algoritmo='sha256',
        provedor='interno',
        ip=ip,
        user_agent=user_agent,
        observacao=observacao,
    )
    db.session.add(assinatura)
    db.session.flush()

    logger.info('[ciencia] rdo=%s signatario=%s obra=%s hash=%s ip=%s',
                rdo.id, signatario.id, rdo.obra_id,
                assinatura.hash_conteudo[:12], ip)
    return assinatura
