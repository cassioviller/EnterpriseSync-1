#!/usr/bin/env python3
"""Chokepoint de autorização — SIGE Fase 1.

Duas perguntas, uma implementação de cada:

  1. "Que obras este usuário enxerga?"  → obras_visiveis()
  2. "Ele pode X nesta obra?"           → pode_ver_obra / pode_editar_obra

Dois eixos, aplicados em ordem:

  * TENANT (`admin_id`) — o eixo que já existia. Vale SEMPRE, para todo
    mundo, com flag ligada ou desligada. Obra de outro tenant nunca é
    alcançável.
  * OBRA (`usuario_obra`) — o eixo novo. Só entra em vigor quando o
    tenant tem `escopo_obra_ativo = TRUE`, e só restringe quem NÃO é
    ADMIN/SUPER_ADMIN.

A ordem importa: o eixo de tenant é aplicado primeiro e não é
negociável. O escopo por obra só pode ESTREITAR o que o tenant já
permitia — nunca alargar.

Falha fechada: anônimo enxerga zero obras; tenant não resolvido idem.
"""
import logging

from flask_login import current_user

from models import Obra, PapelObra, TipoUsuario, UsuarioObra, db
from utils.tenant import get_tenant_admin_id

logger = logging.getLogger('autorizacao')

# Quem pode editar a obra, por papel na obra. LEITOR e APONTADOR não
# editam: o apontador lança RDO (Fase 5), que é outra permissão.
PAPEIS_QUE_EDITAM_OBRA = (PapelObra.GESTOR,)
PAPEIS_QUE_APONTAM = (PapelObra.GESTOR, PapelObra.APONTADOR)


def _e_admin_do_tenant():
    try:
        if not current_user.is_authenticated:
            return False
    except Exception:
        return False
    return current_user.tipo_usuario in (TipoUsuario.ADMIN,
                                         TipoUsuario.SUPER_ADMIN)


def _escopo_ativo(admin_id):
    """Flag do tenant. Import tardio: scripts/ não é importável no boot."""
    try:
        from scripts.flag_escopo_obra import escopo_ativo
        return escopo_ativo(admin_id)
    except Exception:
        logger.warning('flag escopo_obra_ativo ilegível — assumindo desligada')
        return False


def obras_visiveis(admin_id=None):
    """Query de `Obra` já filtrada pelos dois eixos.

    Devolve uma QUERY, não uma lista — quem chama acrescenta filtros,
    ordenação e paginação. Anônimo recebe uma query que não casa nada
    (e não uma exceção), para que as telas degradem em vazio.
    """
    tenant = admin_id if admin_id is not None else get_tenant_admin_id()

    if tenant is None:
        return Obra.query.filter(db.false())

    query = Obra.query.filter(Obra.admin_id == tenant)

    if _e_admin_do_tenant():
        return query

    if not _escopo_ativo(tenant):
        # Comportamento pré-Fase 1, preservado de propósito.
        return query

    return query.join(
        UsuarioObra, UsuarioObra.obra_id == Obra.id,
    ).filter(
        UsuarioObra.usuario_id == current_user.id,
        UsuarioObra.ativo.is_(True),
    )


def papel_na_obra(obra_id):
    """`PapelObra` do usuário logado nesta obra, ou None.

    ADMIN/SUPER_ADMIN devolvem GESTOR implicitamente — sem precisar de
    linha em usuario_obra.
    """
    try:
        if not current_user.is_authenticated:
            return None
    except Exception:
        return None

    obra = db.session.get(Obra, obra_id)
    tenant = get_tenant_admin_id()
    if obra is None or tenant is None or obra.admin_id != tenant:
        return None

    if _e_admin_do_tenant():
        return PapelObra.GESTOR

    if not _escopo_ativo(tenant):
        # Flag desligada: o eixo de obra não está em vigor, nem para
        # alargar nem para estreitar. O papel devolvido tem que reproduzir
        # o comportamento anterior à Fase 1, e ele é permissivo — hoje
        # `editar_obra` (views/obras.py:848) tem só `@login_required`, sem
        # `@admin_required`: qualquer usuário autenticado do tenant edita
        # qualquer obra dele.
        #
        # Devolver LEITOR aqui (como o plano da Fase 1 sugeria) tiraria a
        # edição de todo não-admin no dia do deploy — exatamente o que a
        # flag existe para impedir. E o vínculo é ignorado de propósito:
        # com o eixo desligado, um vínculo LEITOR gravado durante o
        # backfill também não pode restringir ninguém.
        return PapelObra.GESTOR

    vinculo = UsuarioObra.query.filter_by(
        usuario_id=current_user.id, obra_id=obra_id, ativo=True).first()
    if vinculo:
        return vinculo.papel

    return None


def pode_ver_obra(obra_id):
    return papel_na_obra(obra_id) is not None


def pode_editar_obra(obra_id):
    return papel_na_obra(obra_id) in PAPEIS_QUE_EDITAM_OBRA


def pode_apontar_na_obra(obra_id):
    """Lançar RDO/apontamento. Consumido de verdade na Fase 5."""
    return papel_na_obra(obra_id) in PAPEIS_QUE_APONTAM
