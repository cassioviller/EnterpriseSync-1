#!/usr/bin/env python3
"""Assinatura e aprovação de RDO — SIGE Fase 5.

Concentra as operações que mudam o estado terminal do RDO:
`assinar` e `aprovar` (o retificador entra na Task 9). A AUTORIZAÇÃO
fica na rota (utils/autorizacao.py, Fase 1); aqui mora a regra de
negócio e a gravação da evidência.

Identidade: SEMPRE por `utils.identidade.funcionario_do_usuario()`. Antes
da Fase 1 este módulo teria que adivinhar quem é a pessoa — por e-mail
sem `admin_id`, por substring de nome, e no último fallback CRIANDO um
`Funcionario` chamado "Administrador Sistema" (heurística removida na
Fase 1; só o comentário histórico sobrevive em views/rdo.py:2560-2575).
Assinatura em cima de palpite não é assinatura; por isso, sem vínculo,
este módulo se recusa a assinar.
"""
from __future__ import annotations

import logging

from models import RDOAssinatura, db
from services.rdo_ciclo_vida import (APROVADO, ASSINADO, CicloVidaInvalido,
                                     PREENCHIDO, estado_de, transicionar)
from services.rdo_hash import calcular_hash

logger = logging.getLogger('rdo.assinatura')


class AssinaturaInvalida(CicloVidaInvalido):
    """Mensagem apta à UI para recusa de assinatura."""


class SemIdentidade(AssinaturaInvalida):
    """Usuário sem `Usuario.funcionario_id` — não há autoria a registrar."""


def _contexto_request():
    """(ip, user_agent) do request atual, ou (None, None) fora de request."""
    try:
        from flask import request
        return (request.remote_addr,
                (request.headers.get('User-Agent') or '')[:400] or None)
    except Exception:
        return None, None


def assinar(rdo, usuario, *, papel=RDOAssinatura.PAPEL_EXECUTOR,
            observacao=None):
    """Registra a assinatura e leva o RDO de `preenchido` a `assinado`.

    Não faz commit — quem chama decide a transação. Levanta
    `AssinaturaInvalida` (ou subclasse) em qualquer recusa.
    """
    from utils.identidade import funcionario_do_usuario

    if papel not in RDOAssinatura.PAPEIS:
        raise AssinaturaInvalida(f'Papel de assinatura inválido: {papel!r}')

    atual = estado_de(rdo)
    if atual != PREENCHIDO:
        raise AssinaturaInvalida(
            f'Só um RDO preenchido pode ser assinado — este está em '
            f'"{atual}". Submeta o RDO antes de assinar.')

    funcionario = funcionario_do_usuario(usuario)
    if funcionario is None:
        raise SemIdentidade(
            'Seu login não está vinculado a um cadastro de funcionário. '
            'Sem esse vínculo não é possível registrar a autoria da '
            'assinatura. Peça ao administrador para vincular seu usuário '
            '(Fase 1 — utils/identidade.py).')

    if RDOAssinatura.query.filter_by(rdo_id=rdo.id, papel=papel).first():
        raise AssinaturaInvalida(
            f'Este RDO já tem assinatura de {papel}. Para corrigir, emita '
            f'um RDO retificador.')

    ip, user_agent = _contexto_request()
    cargo = None
    funcao_ref = getattr(funcionario, 'funcao_ref', None)
    if funcao_ref is not None:
        cargo = getattr(funcao_ref, 'nome', None)
    cargo = cargo or getattr(funcionario, 'cargo', None)

    assinatura = RDOAssinatura(
        rdo_id=rdo.id,
        admin_id=rdo.admin_id or rdo.obra.admin_id,
        usuario_id=usuario.id,
        funcionario_id=funcionario.id,
        papel=papel,
        nome_signatario=(funcionario.nome or usuario.nome or
                         usuario.username)[:200],
        cargo_signatario=(cargo or '')[:120] or None,
        hash_conteudo=calcular_hash(rdo),
        algoritmo='sha256',
        provedor='interno',
        ip=ip,
        user_agent=user_agent,
        observacao=observacao,
    )
    db.session.add(assinatura)
    db.session.flush()

    transicionar(rdo, ASSINADO, usuario=usuario, funcionario=funcionario,
                 motivo=observacao, ip=ip,
                 detalhes={'assinatura_id': assinatura.id, 'papel': papel})

    logger.info('[assinatura] rdo=%s papel=%s usuario=%s funcionario=%s '
                'hash=%s ip=%s', rdo.id, papel, usuario.id, funcionario.id,
                assinatura.hash_conteudo[:12], ip)
    return assinatura


def aprovar(rdo, usuario, *, observacao=None):
    """Aceite do gestor: `assinado` → `aprovado` + assinatura de gestor.

    Não faz commit.
    """
    from utils.identidade import funcionario_do_usuario

    atual = estado_de(rdo)
    if atual != ASSINADO:
        raise AssinaturaInvalida(
            f'Só um RDO assinado pode ser aprovado — este está em '
            f'"{atual}".')

    funcionario = funcionario_do_usuario(usuario)
    ip, user_agent = _contexto_request()

    ja_existe = RDOAssinatura.query.filter_by(
        rdo_id=rdo.id, papel=RDOAssinatura.PAPEL_GESTOR).first()
    assinatura = ja_existe
    if ja_existe is None:
        assinatura = RDOAssinatura(
            rdo_id=rdo.id,
            admin_id=rdo.admin_id or rdo.obra.admin_id,
            usuario_id=usuario.id,
            funcionario_id=getattr(funcionario, 'id', None),
            papel=RDOAssinatura.PAPEL_GESTOR,
            nome_signatario=(getattr(funcionario, 'nome', None) or
                             usuario.nome or usuario.username)[:200],
            cargo_signatario='Gestor da obra',
            hash_conteudo=calcular_hash(rdo),
            algoritmo='sha256',
            provedor='interno',
            ip=ip,
            user_agent=user_agent,
            observacao=observacao,
        )
        db.session.add(assinatura)
        db.session.flush()

    transicionar(rdo, APROVADO, usuario=usuario, funcionario=funcionario,
                 motivo=observacao, ip=ip,
                 detalhes={'assinatura_id': assinatura.id,
                           'papel': RDOAssinatura.PAPEL_GESTOR})

    logger.info('[assinatura] rdo=%s APROVADO por usuario=%s ip=%s',
                rdo.id, usuario.id, ip)
    return assinatura
