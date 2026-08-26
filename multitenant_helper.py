"""Casca de compatibilidade sobre o resolvedor único de tenant.

Este módulo tinha a PRÓPRIA lógica de resolução, e ela discordava de
`utils.tenant.get_tenant_admin_id` em exatamente dois papéis: GESTOR_EQUIPES e
ALMOXARIFE caíam num `return current_user.id` que os mandava para um tenant
inexistente. Como oito módulos o importam — e dois deles o importam com o nome
do resolvedor certo (`get_admin_id as get_tenant_admin_id`, em
`ponto_service.py:9` e `ponto_views.py:28`) — o defeito era invisível na
leitura do chamador.

A lógica agora mora num lugar só. O que fica aqui é a casca defensiva, que o
resolvedor de `utils.tenant` não tem: ele acessa `current_user` direto e
levanta fora de request, e este helper é chamado de job, seed e CLI.
"""
import logging

from flask_login import current_user

logger = logging.getLogger(__name__)


def get_admin_id():
    """O admin_id do tenant do usuário autenticado, ou None.

    Delega para `utils.tenant.get_tenant_admin_id` — o resolvedor único.
    Nunca levanta: fora de request, sem usuário ou com erro, devolve None.
    """
    try:
        from utils.tenant import get_tenant_admin_id
        return get_tenant_admin_id()
    except Exception as erro:
        logger.debug('get_admin_id sem tenant resolvível: %s', erro)
        return None


def get_current_user_safe():
    """Retorna o current_user de forma segura."""
    return current_user