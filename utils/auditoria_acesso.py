"""Trilha de acesso mínima — Fase 0.5 / 1.3.

Antes desta rodada o sistema era cego: gunicorn sem access log, nenhum
`before_request`, nenhuma tabela de auditoria, e o IP do cliente sequer
chegava à aplicação (`ProxyFix` sem `x_for`). Um acesso anônimo
bem-sucedido a uma rota desprotegida não deixava rastro em lugar nenhum.

Este módulo registra, no logger `sige.acesso`, uma linha por requisição de
ESCRITA (POST/PUT/PATCH/DELETE) com: método, path, status, usuário, tenant,
IP e duração. Leitura não é logada aqui — para isso existe o access log do
gunicorn, que passou a sair em stdout.

Deliberadamente NÃO grava em banco: uma tabela de auditoria acoplaria a
trilha à disponibilidade do Postgres e ao ciclo de transação do request (um
rollback apagaria a evidência). Log estruturado em stdout é coletado pelo
EasyPanel e sobrevive ao rollback. A tabela vem quando houver requisito de
retenção/consulta, não antes.
"""
from __future__ import annotations

import logging
import time

logger = logging.getLogger('sige.acesso')

METODOS_DE_ESCRITA = {'POST', 'PUT', 'PATCH', 'DELETE'}

# Rotas cujo path pode carregar informação sensível — marcadas no log.
_PATHS_SENSIVEIS = ('/login', '/alterar-senha', '/usuarios')


def _identidade():
    """(user_id, tenant) do request corrente. Nunca levanta."""
    try:
        from flask_login import current_user
        if not current_user.is_authenticated:
            return 'anonimo', None
        uid = getattr(current_user, 'id', '?')
    except Exception:
        return 'indeterminado', None

    try:
        from utils.tenant import get_tenant_admin_id
        return uid, get_tenant_admin_id()
    except Exception:
        return uid, None


def registrar(app) -> None:
    """Instala os hooks de auditoria no app Flask."""

    @app.before_request
    def _marcar_inicio():
        from flask import g
        g._auditoria_t0 = time.monotonic()

    @app.after_request
    def _registrar_escrita(response):
        try:
            from flask import g, request

            if request.method not in METODOS_DE_ESCRITA:
                return response

            usuario, tenant = _identidade()
            t0 = getattr(g, '_auditoria_t0', None)
            ms = int((time.monotonic() - t0) * 1000) if t0 else -1
            path = request.path
            if any(path.startswith(p) for p in _PATHS_SENSIVEIS):
                path = f'{path} [sensível]'

            linha = (f'metodo={request.method} path={path} '
                     f'status={response.status_code} usuario={usuario} '
                     f'tenant={tenant} ip={request.remote_addr} ms={ms}')

            # Escrita por usuário não autenticado é o sinal que mais importa:
            # sobe para WARNING para destacar no agregador de logs.
            if usuario == 'anonimo':
                logger.warning(f'[ESCRITA-ANONIMA] {linha}')
            else:
                logger.info(linha)
        except Exception:
            logger.debug('falha ao registrar auditoria de acesso', exc_info=True)
        return response
