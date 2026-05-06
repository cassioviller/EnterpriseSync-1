"""Ferramentas de desenvolvimento (apenas para uso interno).

Atualmente expõe:
- /dev/mobile-preview : iframe redimensionável para testar telas em tamanhos
  de celular dentro do próprio preview do Replit, sem depender de DevTools.

Acesso restrito a SUPER_ADMIN, ADMIN ou GESTOR_EQUIPES (usuário final
e funcionário operacional não devem ver ferramentas de dev).
"""
import os
from flask import Blueprint, abort, render_template, request
from flask_login import current_user, login_required

from models import TipoUsuario

dev_bp = Blueprint("dev", __name__, url_prefix="/dev")

_ALLOWED_ROLES = {TipoUsuario.SUPER_ADMIN}


def _is_dev_environment() -> bool:
    """True quando rodando em DEV/Replit (libera mais cedo)."""
    if os.environ.get("FLASK_ENV") == "development":
        return True
    if os.environ.get("REPL_ID") or os.environ.get("REPLIT_DEV_DOMAIN"):
        return True
    return False


@dev_bp.route("/mobile-preview")
@login_required
def mobile_preview():
    """Página com iframe + seletor de tamanho para testar telas em mobile.

    Acesso permitido a:
    - qualquer usuário autenticado em ambiente de dev (Replit/local);
    - apenas SUPER_ADMIN em produção.
    """
    if not _is_dev_environment():
        try:
            tipo = current_user.tipo_usuario
        except Exception:
            abort(403)
        if tipo not in _ALLOWED_ROLES:
            abort(403)

    target = request.args.get("target", "/dashboard")
    width = request.args.get("w", "390")
    height = request.args.get("h", "780")
    orientation = request.args.get("orientation", "portrait")
    return render_template(
        "dev/mobile_preview.html",
        target=target,
        width=width,
        height=height,
        orientation=orientation,
    )
