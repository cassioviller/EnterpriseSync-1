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

# Fase 3 — quem PEDE e quem COMPRA, por papel na obra.
#
# A assimetria entre as duas listas é a separação de funções no nível do
# papel, e é de propósito:
#   * GESTOR requisita e APROVA (services/alcada_compras.pode_aprovar),
#     mas NÃO emite pedido — quem aprova não emite.
#   * COMPRADOR requisita e EMITE, mas não aprova e não edita a obra.
#   * APONTADOR e LEITOR não fazem nem uma coisa nem outra.
# ADMIN/SUPER_ADMIN passam por cima das duas listas (papel_na_obra
# devolve GESTOR implícito para eles), e é por isso que a checagem de
# "não aprove a própria requisição" existe também para ADMIN.
PAPEIS_QUE_REQUISITAM = (PapelObra.GESTOR, PapelObra.COMPRADOR)
PAPEIS_QUE_COMPRAM = (PapelObra.COMPRADOR,)


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


def pode_requisitar_na_obra(obra_id):
    """Criar/editar requisição de compra nesta obra. Fase 3."""
    papel = papel_na_obra(obra_id)
    if papel is None:
        return False
    if _e_admin_do_tenant():
        return True
    return papel in PAPEIS_QUE_REQUISITAM


def pode_comprar_na_obra(obra_id):
    """Emitir PedidoCompra a partir de requisição aprovada. Fase 3.

    ADMIN pode — não há como impedir o dono da empresa de comprar. Mas
    quando ele emite, `compras_views.requisicao_emitir_pedido` recusa se
    ele foi um dos aprovadores e a faixa exigia mais de uma aprovação
    (Task 8): a separação de funções sobrevive ao acúmulo de chapéus.
    """
    papel = papel_na_obra(obra_id)
    if papel is None:
        return False
    if _e_admin_do_tenant():
        return True
    return papel in PAPEIS_QUE_COMPRAM


def obra_required(papel_minimo=None):
    """Exige login + acesso à obra do `obra_id` da URL.

    Devolve **404** (não 403) quando a obra existe mas está fora do
    alcance, para não vazar a existência de obra de outro tenant. Mesma
    escolha já travada por
    `tests/test_cronograma_permissoes.py::test_admin_de_outro_tenant_recebe_404_sem_vazar_existencia`.

    Args:
        papel_minimo: None → basta ver. `PapelObra.GESTOR` → exige edição.

    Uso:
        @app.route('/obras/<int:obra_id>')
        @obra_required()
        def detalhe(obra_id): ...
    """
    from functools import wraps

    def decorador(f):
        @wraps(f)
        def wrapper(*args, **kwargs):
            from flask import abort, jsonify, redirect, request, url_for

            quer_json = request.path.startswith('/api/') or \
                request.accept_mimetypes.best == 'application/json'

            try:
                autenticado = current_user.is_authenticated
            except Exception:
                autenticado = False
            if not autenticado:
                if quer_json:
                    return jsonify({'error': 'Autenticação necessária'}), 401
                return redirect(url_for('main.login'))

            obra_id = kwargs.get('obra_id') or kwargs.get('id')
            if obra_id is None:
                logger.error('obra_required em rota sem obra_id: %s',
                             request.endpoint)
                abort(500)

            if papel_minimo in PAPEIS_QUE_EDITAM_OBRA:
                permitido = pode_editar_obra(obra_id)
            else:
                permitido = pode_ver_obra(obra_id)

            if not permitido:
                if quer_json:
                    return jsonify({'error': 'Obra não encontrada'}), 404
                abort(404)

            return f(*args, **kwargs)
        return wrapper
    return decorador
