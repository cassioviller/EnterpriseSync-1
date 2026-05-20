import logging
from flask import Blueprint, render_template, redirect, url_for, flash, request
from flask_login import login_required, current_user

from app import db

logger = logging.getLogger(__name__)

cadastros_hub_bp = Blueprint('cadastros_hub', __name__, url_prefix='/cadastros')


def _get_admin_id():
    if hasattr(current_user, 'admin_id') and current_user.admin_id:
        return current_user.admin_id
    return current_user.id


# ---------------------------------------------------------------------------
# Hub index
# ---------------------------------------------------------------------------

@cadastros_hub_bp.route('/')
@login_required
def index():
    return render_template('cadastros/index.html')


# ---------------------------------------------------------------------------
# Motor de dropdowns — rotas genéricas por slug
# ---------------------------------------------------------------------------

@cadastros_hub_bp.route('/dropdowns/<slug>')
@login_required
def dropdown_opcoes(slug):
    """Lista e gerencia as opções de um grupo de dropdown."""
    from services.dropdown_service import ensure_grupo, get_dropdown_options
    admin_id = _get_admin_id()
    grupo = ensure_grupo(slug, admin_id)
    try:
        db.session.commit()
    except Exception:
        db.session.rollback()
        logger.exception('Erro ao garantir DropdownGrupo slug=%s', slug)

    opcoes = get_dropdown_options(slug, admin_id, incluir_inativos=True)
    return render_template(
        'cadastros/dropdown_opcoes.html',
        grupo=grupo,
        opcoes=opcoes,
    )


@cadastros_hub_bp.route('/dropdowns/<slug>/criar', methods=['POST'])
@login_required
def dropdown_criar_opcao(slug):
    from services.dropdown_service import criar_opcao, ensure_grupo
    admin_id = _get_admin_id()
    valor = (request.form.get('valor') or '').strip()
    if not valor:
        flash('Informe um nome para a opção.', 'warning')
        return redirect(url_for('cadastros_hub.dropdown_opcoes', slug=slug))
    try:
        ensure_grupo(slug, admin_id)
        criar_opcao(slug, admin_id, valor)
        db.session.commit()
        flash(f'Opção "{valor}" adicionada com sucesso.', 'success')
    except ValueError as exc:
        db.session.rollback()
        flash(str(exc), 'warning')
    except Exception:
        db.session.rollback()
        logger.exception('Erro ao criar opção slug=%s valor=%s', slug, valor)
        flash('Erro inesperado ao criar opção. Tente novamente.', 'danger')
    return redirect(url_for('cadastros_hub.dropdown_opcoes', slug=slug))


@cadastros_hub_bp.route('/dropdowns/<slug>/<int:opcao_id>/editar', methods=['POST'])
@login_required
def dropdown_editar_opcao(slug, opcao_id):
    from services.dropdown_service import atualizar_opcao
    admin_id = _get_admin_id()
    valor = (request.form.get('valor') or '').strip()
    if not valor:
        flash('O nome não pode ficar em branco.', 'warning')
        return redirect(url_for('cadastros_hub.dropdown_opcoes', slug=slug))
    try:
        atualizar_opcao(slug, opcao_id, admin_id, valor)
        db.session.commit()
        flash('Opção atualizada.', 'success')
    except ValueError as exc:
        db.session.rollback()
        flash(str(exc), 'warning')
    except Exception:
        db.session.rollback()
        logger.exception('Erro ao editar opção slug=%s id=%s', slug, opcao_id)
        flash('Erro inesperado ao editar. Tente novamente.', 'danger')
    return redirect(url_for('cadastros_hub.dropdown_opcoes', slug=slug))


@cadastros_hub_bp.route('/dropdowns/<slug>/<int:opcao_id>/toggle', methods=['POST'])
@login_required
def dropdown_toggle_ativo(slug, opcao_id):
    from services.dropdown_service import toggle_ativo_opcao
    admin_id = _get_admin_id()
    try:
        novo = toggle_ativo_opcao(slug, opcao_id, admin_id)
        db.session.commit()
        flash('Opção %s.' % ('ativada' if novo else 'desativada'), 'success')
    except ValueError as exc:
        db.session.rollback()
        flash(str(exc), 'warning')
    except Exception:
        db.session.rollback()
        logger.exception('Erro ao toggle opção slug=%s id=%s', slug, opcao_id)
        flash('Erro inesperado. Tente novamente.', 'danger')
    return redirect(url_for('cadastros_hub.dropdown_opcoes', slug=slug))


@cadastros_hub_bp.route('/dropdowns/<slug>/<int:opcao_id>/excluir', methods=['POST'])
@login_required
def dropdown_excluir_opcao(slug, opcao_id):
    """Política: sem exclusão física — desativa a opção."""
    from services.dropdown_service import desativar_opcao
    admin_id = _get_admin_id()
    try:
        desativar_opcao(slug, opcao_id, admin_id)
        db.session.commit()
        flash('Opção desativada.', 'success')
    except ValueError as exc:
        db.session.rollback()
        flash(str(exc), 'warning')
    except Exception:
        db.session.rollback()
        logger.exception('Erro ao desativar opção slug=%s id=%s', slug, opcao_id)
        flash('Erro inesperado. Tente novamente.', 'danger')
    return redirect(url_for('cadastros_hub.dropdown_opcoes', slug=slug))


@cadastros_hub_bp.route('/dropdowns/<slug>/<int:opcao_id>/mover/<direcao>', methods=['POST'])
@login_required
def dropdown_mover_opcao(slug, opcao_id, direcao):
    """Move uma opção para cima ou para baixo na lista (ordem)."""
    from services.dropdown_service import mover_opcao
    admin_id = _get_admin_id()
    if direcao not in ('cima', 'baixo'):
        flash('Direção inválida.', 'warning')
        return redirect(url_for('cadastros_hub.dropdown_opcoes', slug=slug))
    try:
        mover_opcao(slug, opcao_id, admin_id, direcao)
        db.session.commit()
    except ValueError as exc:
        db.session.rollback()
        flash(str(exc), 'warning')
    except Exception:
        db.session.rollback()
        logger.exception('Erro ao mover opção slug=%s id=%s', slug, opcao_id)
        flash('Erro inesperado. Tente novamente.', 'danger')
    return redirect(url_for('cadastros_hub.dropdown_opcoes', slug=slug))
