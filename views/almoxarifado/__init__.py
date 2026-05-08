from flask import Blueprint
from flask_login import current_user

almoxarifado_bp = Blueprint('almoxarifado', __name__, url_prefix='/almoxarifado')


def get_admin_id():
<<<<<<< HEAD
    """Retorna admin_id do usuário atual (padrão consolidado do sistema)."""
=======
    """Retorna admin_id do usuário atual (padrão consolidado do sistema)"""
>>>>>>> 7d4bef6c2972b820519cd3cab2f33d3f0078ddd1
    if current_user.is_authenticated:
        if hasattr(current_user, 'admin_id') and current_user.admin_id:
            return current_user.admin_id
        return current_user.id
    return None


<<<<<<< HEAD
from . import (  # noqa: E402,F401
    dashboard,
    categorias,
    itens,
    movimentos,
    api,
    relatorios,
    fornecedores,
)

__all__ = ['almoxarifado_bp', 'get_admin_id']
=======
from views.almoxarifado import dashboard   # noqa: E402,F401
from views.almoxarifado import categorias  # noqa: E402,F401
from views.almoxarifado import itens       # noqa: E402,F401
from views.almoxarifado import movimentos  # noqa: E402,F401
from views.almoxarifado import api         # noqa: E402,F401
from views.almoxarifado import relatorios  # noqa: E402,F401
from views.almoxarifado import fornecedores  # noqa: E402,F401

__all__ = ['almoxarifado_bp']
>>>>>>> 7d4bef6c2972b820519cd3cab2f33d3f0078ddd1
