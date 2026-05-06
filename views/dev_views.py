"""Ferramentas de desenvolvimento (apenas para uso interno).

Atualmente expõe:
- /dev/mobile-preview : iframe redimensionável para testar telas em tamanhos
  de celular dentro do próprio preview do Replit, sem depender de DevTools.

Apenas usuários autenticados podem acessar (não exige permissão
adicional para que o time inteiro consiga validar visualmente).
"""
from flask import Blueprint, render_template, request
from flask_login import login_required

dev_bp = Blueprint("dev", __name__, url_prefix="/dev")


@dev_bp.route("/mobile-preview")
@login_required
def mobile_preview():
    """Página com iframe + seletor de tamanho para testar telas em mobile."""
    target = request.args.get("target", "/dashboard")
    width = request.args.get("w", "390")
    height = request.args.get("h", "780")
    return render_template(
        "dev/mobile_preview.html",
        target=target,
        width=width,
        height=height,
    )
