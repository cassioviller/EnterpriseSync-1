from flask import Blueprint
from flask_login import current_user

almoxarifado_bp = Blueprint('almoxarifado', __name__, url_prefix='/almoxarifado')


def get_admin_id():
    """Retorna admin_id do usuário atual (padrão consolidado do sistema)."""
    if current_user.is_authenticated:
        if hasattr(current_user, 'admin_id') and current_user.admin_id:
            return current_user.admin_id
        return current_user.id
    return None


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
