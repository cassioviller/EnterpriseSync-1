from flask import Blueprint
from flask_login import current_user

almoxarifado_bp = Blueprint('almoxarifado', __name__, url_prefix='/almoxarifado')


def get_admin_id():
    """Tenant do usuário autenticado. DELEGA para o resolvedor canônico.

    Convergido em 01/09 (Task 11): a cópia local devolvia current_user.id
    como fallback — um TENANT FANTASMA para usuário sem admin_id, onde o
    canônico falha fechado. Medido pelo censo de
    tests/test_isolamento_tenant_bloco1.py.
    """
    from utils.tenant import get_tenant_admin_id
    return get_tenant_admin_id()


from views.almoxarifado import dashboard   # noqa: E402,F401
from views.almoxarifado import categorias  # noqa: E402,F401
from views.almoxarifado import itens       # noqa: E402,F401
from views.almoxarifado import movimentos  # noqa: E402,F401
from views.almoxarifado import api         # noqa: E402,F401
from views.almoxarifado import relatorios  # noqa: E402,F401
from views.almoxarifado import fornecedores  # noqa: E402,F401

__all__ = ['almoxarifado_bp']
