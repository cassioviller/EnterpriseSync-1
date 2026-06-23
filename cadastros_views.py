import logging
from flask import Blueprint, render_template, redirect, url_for, flash, request, jsonify
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


@cadastros_hub_bp.route('/dropdowns/<slug>/<int:opcao_id>/verificar-uso')
@login_required
def dropdown_verificar_uso(slug, opcao_id):
    """Retorna JSON com { em_uso, total, opcoes_disponiveis } para popular o modal de exclusão."""
    from services.dropdown_service import contar_uso_opcao, get_dropdown_options
    admin_id = _get_admin_id()
    try:
        total = contar_uso_opcao(slug, opcao_id, admin_id)
        opcoes_raw = get_dropdown_options(slug, admin_id, incluir_inativos=False)
        opcoes_disp = [
            {'id': o.id, 'valor': o.valor}
            for o in opcoes_raw
            if o.id != opcao_id
        ]
        return jsonify({
            'em_uso': total > 0,
            'total': total,
            'opcoes_disponiveis': opcoes_disp,
        })
    except Exception:
        logger.exception('Erro ao verificar uso slug=%s id=%s', slug, opcao_id)
        return jsonify({'error': 'Erro interno'}), 500


@cadastros_hub_bp.route('/dropdowns/<slug>/<int:opcao_id>/excluir', methods=['POST'])
@login_required
def dropdown_excluir_opcao(slug, opcao_id):
    """Exclui fisicamente a opção, migrando registros se necessário."""
    from services.dropdown_service import contar_uso_opcao, migrar_e_excluir_opcao
    admin_id = _get_admin_id()
    opcao_destino_id = request.form.get('opcao_destino_id', type=int)
    try:
        total = contar_uso_opcao(slug, opcao_id, admin_id)
        if total > 0:
            if not opcao_destino_id:
                flash(
                    f'Esta opção está em uso por {total} registro(s). '
                    'Selecione uma opção de destino para migrar antes de excluir.',
                    'warning',
                )
                return redirect(url_for('cadastros_hub.dropdown_opcoes', slug=slug))
            migrar_e_excluir_opcao(slug, opcao_id, opcao_destino_id, admin_id)
            db.session.commit()
            flash(f'Opção excluída. {total} registro(s) migrado(s) com sucesso.', 'success')
        else:
            from models import DropdownOpcao
            crm = None
            try:
                from services.dropdown_service import _crm_model
                crm = _crm_model(slug)
            except Exception:
                pass
            opcao = DropdownOpcao.query.filter_by(id=opcao_id, admin_id=admin_id).first()
            if opcao:
                if crm and opcao.ext_id:
                    leg = crm.query.filter_by(id=opcao.ext_id, admin_id=admin_id).first()
                    if leg:
                        db.session.delete(leg)
                db.session.delete(opcao)
            db.session.commit()
            flash('Opção excluída com sucesso.', 'success')
    except ValueError as exc:
        db.session.rollback()
        flash(str(exc), 'warning')
    except Exception:
        db.session.rollback()
        logger.exception('Erro ao excluir opção slug=%s id=%s', slug, opcao_id)
        flash('Erro inesperado ao excluir. Tente novamente.', 'danger')
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
