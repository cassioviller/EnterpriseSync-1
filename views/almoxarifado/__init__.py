from flask import Blueprint
from flask_login import current_user

almoxarifado_bp = Blueprint('almoxarifado', __name__, url_prefix='/almoxarifado')


def get_admin_id():
    """Retorna admin_id do usuário atual (padrão consolidado do sistema)"""
    if current_user.is_authenticated:
        if hasattr(current_user, 'admin_id') and current_user.admin_id:
            return current_user.admin_id
        return current_user.id
    return None


from views.almoxarifado import dashboard   # noqa: E402,F401
from views.almoxarifado import categorias  # noqa: E402,F401
from views.almoxarifado import itens       # noqa: E402,F401
from views.almoxarifado import movimentos  # noqa: E402,F401
from views.almoxarifado import api         # noqa: E402,F401
from views.almoxarifado import relatorios  # noqa: E402,F401
from views.almoxarifado import fornecedores  # noqa: E402,F401

__all__ = ['almoxarifado_bp']
