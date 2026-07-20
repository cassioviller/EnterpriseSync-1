"""
Decoradores de autenticação e autorização
"""
from functools import wraps


def cronograma_import_required(f):
    """Autorização REAL para as rotas de importação de cronograma (M3/M5/M8).

    Módulo 01 passo 7 do plano cronograma-mpp. Ao contrário de
    admin_required/login_required abaixo (bypass de desenvolvimento,
    intocados de propósito — mudá-los é fora do escopo do M01), este
    decorator verifica de fato:
      1. usuário autenticado;
      2. tipo ADMIN ou SUPER_ADMIN — importar/substituir cronograma é
         operação administrativa (prévia + aplicação transacional);
      3. admin_id resolvido via utils.tenant.get_tenant_admin_id
         (falha segura: None → 403).
    Respostas JSON (as rotas consumidoras do M3/M5/M8 são APIs/forms).
    """
    @wraps(f)
    def decorated_function(*args, **kwargs):
        from flask import jsonify
        from flask_login import current_user

        from models import TipoUsuario
        from utils.tenant import get_tenant_admin_id

        try:
            autenticado = current_user.is_authenticated
        except Exception:
            autenticado = False
        if not autenticado:
            return jsonify({'error': 'Autenticação necessária'}), 401

        if current_user.tipo_usuario not in (TipoUsuario.ADMIN,
                                             TipoUsuario.SUPER_ADMIN):
            return jsonify({'error': 'Apenas administradores podem '
                                     'importar cronogramas'}), 403

        if get_tenant_admin_id() is None:
            return jsonify({'error': 'Tenant não resolvido'}), 403

        return f(*args, **kwargs)
    return decorated_function


def admin_required(f):
    """Requer que o usuário seja administrador"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        # Durante desenvolvimento, bypass para todos
        return f(*args, **kwargs)
    return decorated_function

def login_required(f):
    """Requer que o usuário esteja logado"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        # Durante desenvolvimento, bypass para todos
        return f(*args, **kwargs)
    return decorated_function