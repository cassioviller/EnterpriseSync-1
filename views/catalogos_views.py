"""
Catálogos — Central de dados auxiliares gerenciados pelo administrador.
Blueprint: catalogos_bp  prefix: /catalogos
"""
import io
import logging
from flask import Blueprint, render_template, request, redirect, url_for, flash, send_file
from flask_login import login_required, current_user
from app import db
from models import (
    CategoriaFluxoCaixa, CategoriaFornecedor, CategoriaReembolso,
    FluxoCaixa, Fornecedor, TipoUsuario
)

logger = logging.getLogger(__name__)

catalogos_bp = Blueprint('catalogos', __name__, url_prefix='/catalogos')


def _get_admin_id():
    if not current_user.is_authenticated:
        return None
    if current_user.tipo_usuario not in (TipoUsuario.SUPER_ADMIN, TipoUsuario.ADMIN):
        return None
    if hasattr(current_user, 'admin_id') and current_user.admin_id:
        return current_user.admin_id
    return current_user.id


def _require_admin():
    admin_id = _get_admin_id()
    if not admin_id:
        flash('Acesso restrito a administradores.', 'danger')
        return None, redirect(url_for('main.index'))
    return admin_id, None


# ============================================================
# HUB
# ============================================================

@catalogos_bp.route('/')
@login_required
def hub():
    admin_id, err = _require_admin()
    if err:
        return err
    from services.dropdown_service import get_grupos_por_modulo, MODULOS_LABELS
    grupos_por_modulo = get_grupos_por_modulo(admin_id)
    return render_template('catalogos/hub.html',
                           grupos_por_modulo=grupos_por_modulo,
                           modulos_labels=MODULOS_LABELS)


# ============================================================
# CategoriaFluxoCaixa
# ============================================================

@catalogos_bp.route('/categorias-fluxo-caixa')
@login_required
def categorias_fluxo_caixa():
    admin_id, err = _require_admin()
    if err:
        return err
    cats = CategoriaFluxoCaixa.query.filter_by(admin_id=admin_id).order_by(CategoriaFluxoCaixa.nome).all()
    return render_template('catalogos/categorias_fluxo_caixa.html', categorias=cats)


@catalogos_bp.route('/categorias-fluxo-caixa/criar', methods=['GET', 'POST'])
@login_required
def categorias_fluxo_caixa_criar():
    admin_id, err = _require_admin()
    if err:
        return err
    if request.method == 'POST':
        nome = request.form.get('nome', '').strip()
        tipo = request.form.get('tipo', 'SAIDA').strip()
        grupo = request.form.get('grupo_financeiro', '').strip()
        descricao = request.form.get('descricao', '').strip()
        if not nome:
            flash('Nome é obrigatório.', 'danger')
            return redirect(url_for('catalogos.categorias_fluxo_caixa_criar'))
        if tipo not in ('ENTRADA', 'SAIDA'):
            tipo = 'SAIDA'
        cat = CategoriaFluxoCaixa(
            nome=nome, tipo=tipo,
            grupo_financeiro=grupo or None,
            descricao=descricao or None,
            ativo=True, admin_id=admin_id
        )
        db.session.add(cat)
        db.session.commit()
        flash(f'Categoria "{nome}" criada com sucesso!', 'success')
        return redirect(url_for('catalogos.categorias_fluxo_caixa'))
    return render_template('catalogos/categorias_fluxo_caixa_form.html', categoria=None)


@catalogos_bp.route('/categorias-fluxo-caixa/editar/<int:id>', methods=['GET', 'POST'])
@login_required
def categorias_fluxo_caixa_editar(id):
    admin_id, err = _require_admin()
    if err:
        return err
    cat = CategoriaFluxoCaixa.query.filter_by(id=id, admin_id=admin_id).first_or_404()
    if request.method == 'POST':
        nome = request.form.get('nome', '').strip()
        tipo = request.form.get('tipo', 'SAIDA').strip()
        grupo = request.form.get('grupo_financeiro', '').strip()
        descricao = request.form.get('descricao', '').strip()
        if not nome:
            flash('Nome é obrigatório.', 'danger')
            return redirect(url_for('catalogos.categorias_fluxo_caixa_editar', id=id))
        if tipo not in ('ENTRADA', 'SAIDA'):
            tipo = cat.tipo
        cat.nome = nome
        cat.tipo = tipo
        cat.grupo_financeiro = grupo or None
        cat.descricao = descricao or None
        db.session.commit()
        flash(f'Categoria "{nome}" atualizada com sucesso!', 'success')
        return redirect(url_for('catalogos.categorias_fluxo_caixa'))
    return render_template('catalogos/categorias_fluxo_caixa_form.html', categoria=cat)


@catalogos_bp.route('/categorias-fluxo-caixa/toggle/<int:id>', methods=['POST'])
@login_required
def categorias_fluxo_caixa_toggle(id):
    admin_id, err = _require_admin()
    if err:
        return err
    cat = CategoriaFluxoCaixa.query.filter_by(id=id, admin_id=admin_id).first_or_404()
    cat.ativo = not cat.ativo
    db.session.commit()
    estado = 'ativada' if cat.ativo else 'desativada'
    flash(f'Categoria "{cat.nome}" {estado}.', 'success')
    return redirect(url_for('catalogos.categorias_fluxo_caixa'))


@catalogos_bp.route('/categorias-fluxo-caixa/exportar-modelo', methods=['GET'])
@login_required
def categorias_fluxo_caixa_exportar_modelo():
    admin_id, err = _require_admin()
    if err:
        return err
    import openpyxl
    from openpyxl.styles import Font, PatternFill, Alignment
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = 'Categorias'
    headers = ['Nome', 'Tipo', 'Grupo Financeiro', 'Descrição']
    header_fill = PatternFill(start_color='1e3a5f', end_color='1e3a5f', fill_type='solid')
    header_font = Font(bold=True, color='FFFFFF')
    for col, h in enumerate(headers, 1):
        cell = ws.cell(row=1, column=col, value=h)
        cell.font = header_font
        cell.fill = header_fill
        cell.alignment = Alignment(horizontal='center')
    ws.append(['Receita de Serviços', 'ENTRADA', 'Receitas Operacionais', 'Faturamento por prestação de serviços'])
    ws.append(['Custo de Material', 'SAIDA', 'Custos Diretos', 'Materiais consumidos em obras'])
    note_cell = ws.cell(row=4, column=1, value='NOTA: O campo Tipo deve ser exatamente ENTRADA ou SAIDA (sem acento).')
    note_cell.font = Font(italic=True, color='888888')
    ws.column_dimensions['A'].width = 30
    ws.column_dimensions['B'].width = 12
    ws.column_dimensions['C'].width = 28
    ws.column_dimensions['D'].width = 45
    buf = io.BytesIO()
    wb.save(buf)
    buf.seek(0)
    return send_file(
        buf,
        as_attachment=True,
        download_name='modelo_categorias_fluxo_caixa.xlsx',
        mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
    )


@catalogos_bp.route('/categorias-fluxo-caixa/importar', methods=['POST'])
@login_required
def categorias_fluxo_caixa_importar():
    admin_id, err = _require_admin()
    if err:
        return err
    arquivo = request.files.get('arquivo')
    if not arquivo or arquivo.filename == '':
        flash('Nenhum arquivo selecionado.', 'warning')
        return redirect(url_for('catalogos.categorias_fluxo_caixa'))
    ext = arquivo.filename.rsplit('.', 1)[-1].lower() if '.' in arquivo.filename else ''
    if ext != 'xlsx':
        flash('Formato inválido. Use arquivo .xlsx.', 'danger')
        return redirect(url_for('catalogos.categorias_fluxo_caixa'))
    try:
        import openpyxl
        wb = openpyxl.load_workbook(arquivo, data_only=True)
        ws = wb.active
        header_row = None
        col_nome = col_tipo = col_grupo = col_desc = None
        for rn in range(1, min(5, ws.max_row + 1)):
            vals = [str(ws.cell(row=rn, column=c).value or '').strip().lower() for c in range(1, ws.max_column + 1)]
            if 'nome' in vals:
                header_row = rn
                col_nome = next((i + 1 for i, v in enumerate(vals) if v == 'nome'), None)
                col_tipo = next((i + 1 for i, v in enumerate(vals) if v == 'tipo'), None)
                col_grupo = next((i + 1 for i, v in enumerate(vals) if 'grupo' in v), None)
                col_desc = next((i + 1 for i, v in enumerate(vals) if 'descri' in v), None)
                break
        if not header_row or not col_nome or not col_tipo:
            flash('Cabeçalho não encontrado. Use o modelo disponível para download.', 'danger')
            return redirect(url_for('catalogos.categorias_fluxo_caixa'))
        criadas = 0
        ignoradas = 0
        for rn in range(header_row + 1, ws.max_row + 1):
            nome = str(ws.cell(row=rn, column=col_nome).value or '').strip()
            tipo = str(ws.cell(row=rn, column=col_tipo).value or '').strip().upper()
            if not nome or nome.lower().startswith('nota:'):
                continue
            if tipo not in ('ENTRADA', 'SAIDA'):
                ignoradas += 1
                continue
            grupo = str(ws.cell(row=rn, column=col_grupo).value or '').strip() if col_grupo else ''
            desc = str(ws.cell(row=rn, column=col_desc).value or '').strip() if col_desc else ''
            existe = CategoriaFluxoCaixa.query.filter(
                CategoriaFluxoCaixa.admin_id == admin_id,
                db.func.lower(CategoriaFluxoCaixa.nome) == nome.lower(),
                CategoriaFluxoCaixa.tipo == tipo,
            ).first()
            if existe:
                ignoradas += 1
                continue
            cat = CategoriaFluxoCaixa(
                nome=nome, tipo=tipo,
                grupo_financeiro=grupo or None,
                descricao=desc or None,
                ativo=True, admin_id=admin_id,
            )
            db.session.add(cat)
            criadas += 1
        db.session.commit()
        partes = []
        if criadas:
            partes.append(f'{criadas} categoria(s) criada(s)')
        if ignoradas:
            partes.append(f'{ignoradas} ignorada(s) (duplicada ou tipo inválido)')
        flash(', '.join(partes) + '.' if partes else 'Nenhuma linha processada.', 'success' if criadas else 'warning')
    except Exception as e:
        logger.error(f'[IMPORTAR_CATEGORIAS] {e}', exc_info=True)
        flash(f'Erro ao processar arquivo: {e}', 'danger')
    return redirect(url_for('catalogos.categorias_fluxo_caixa'))


@catalogos_bp.route('/categorias-fluxo-caixa/deletar/<int:id>', methods=['POST'])
@login_required
def categorias_fluxo_caixa_deletar(id):
    admin_id, err = _require_admin()
    if err:
        return err
    cat = CategoriaFluxoCaixa.query.filter_by(id=id, admin_id=admin_id).first_or_404()
    em_uso = FluxoCaixa.query.filter_by(admin_id=admin_id, categoria_fluxo_caixa_id=cat.id).first()
    if em_uso:
        flash(f'Não é possível excluir: a categoria "{cat.nome}" está em uso por lançamentos de Fluxo de Caixa.', 'danger')
        return redirect(url_for('catalogos.categorias_fluxo_caixa'))
    db.session.delete(cat)
    db.session.commit()
    flash(f'Categoria "{cat.nome}" excluída.', 'success')
    return redirect(url_for('catalogos.categorias_fluxo_caixa'))


# ============================================================
# CategoriaFornecedor
# ============================================================

@catalogos_bp.route('/categorias-fornecedor')
@login_required
def categorias_fornecedor():
    admin_id, err = _require_admin()
    if err:
        return err
    cats = CategoriaFornecedor.query.filter_by(admin_id=admin_id).order_by(CategoriaFornecedor.nome).all()
    return render_template('catalogos/categorias_fornecedor.html', categorias=cats)


@catalogos_bp.route('/categorias-fornecedor/criar', methods=['GET', 'POST'])
@login_required
def categorias_fornecedor_criar():
    admin_id, err = _require_admin()
    if err:
        return err
    if request.method == 'POST':
        nome = request.form.get('nome', '').strip()
        descricao = request.form.get('descricao', '').strip()
        if not nome:
            flash('Nome é obrigatório.', 'danger')
            return redirect(url_for('catalogos.categorias_fornecedor_criar'))
        cat = CategoriaFornecedor(nome=nome, descricao=descricao or None, ativo=True, admin_id=admin_id)
        db.session.add(cat)
        db.session.commit()
        flash(f'Categoria "{nome}" criada com sucesso!', 'success')
        return redirect(url_for('catalogos.categorias_fornecedor'))
    return render_template('catalogos/categorias_fornecedor_form.html', categoria=None)


@catalogos_bp.route('/categorias-fornecedor/editar/<int:id>', methods=['GET', 'POST'])
@login_required
def categorias_fornecedor_editar(id):
    admin_id, err = _require_admin()
    if err:
        return err
    cat = CategoriaFornecedor.query.filter_by(id=id, admin_id=admin_id).first_or_404()
    if request.method == 'POST':
        nome = request.form.get('nome', '').strip()
        descricao = request.form.get('descricao', '').strip()
        if not nome:
            flash('Nome é obrigatório.', 'danger')
            return redirect(url_for('catalogos.categorias_fornecedor_editar', id=id))
        cat.nome = nome
        cat.descricao = descricao or None
        db.session.commit()
        flash(f'Categoria "{nome}" atualizada com sucesso!', 'success')
        return redirect(url_for('catalogos.categorias_fornecedor'))
    return render_template('catalogos/categorias_fornecedor_form.html', categoria=cat)


@catalogos_bp.route('/categorias-fornecedor/toggle/<int:id>', methods=['POST'])
@login_required
def categorias_fornecedor_toggle(id):
    admin_id, err = _require_admin()
    if err:
        return err
    cat = CategoriaFornecedor.query.filter_by(id=id, admin_id=admin_id).first_or_404()
    cat.ativo = not cat.ativo
    db.session.commit()
    estado = 'ativada' if cat.ativo else 'desativada'
    flash(f'Categoria "{cat.nome}" {estado}.', 'success')
    return redirect(url_for('catalogos.categorias_fornecedor'))


@catalogos_bp.route('/categorias-fornecedor/deletar/<int:id>', methods=['POST'])
@login_required
def categorias_fornecedor_deletar(id):
    admin_id, err = _require_admin()
    if err:
        return err
    cat = CategoriaFornecedor.query.filter_by(id=id, admin_id=admin_id).first_or_404()
    from sqlalchemy import text as _text
    em_uso = db.session.execute(
        _text("SELECT 1 FROM fornecedor_categorias WHERE categoria_fornecedor_id = :cid LIMIT 1"),
        {'cid': cat.id}
    ).first()
    if em_uso:
        flash(f'Não é possível excluir: a categoria "{cat.nome}" está vinculada a fornecedores.', 'danger')
        return redirect(url_for('catalogos.categorias_fornecedor'))
    db.session.delete(cat)
    db.session.commit()
    flash(f'Categoria "{cat.nome}" excluída.', 'success')
    return redirect(url_for('catalogos.categorias_fornecedor'))


# ============================================================
# CategoriaReembolso
# ============================================================

@catalogos_bp.route('/categorias-reembolso')
@login_required
def categorias_reembolso():
    admin_id, err = _require_admin()
    if err:
        return err
    cats = CategoriaReembolso.query.filter_by(admin_id=admin_id).order_by(CategoriaReembolso.nome).all()
    return render_template('catalogos/categorias_reembolso.html', categorias=cats)


@catalogos_bp.route('/categorias-reembolso/criar', methods=['GET', 'POST'])
@login_required
def categorias_reembolso_criar():
    admin_id, err = _require_admin()
    if err:
        return err
    if request.method == 'POST':
        nome = request.form.get('nome', '').strip()
        descricao = request.form.get('descricao', '').strip()
        if not nome:
            flash('Nome é obrigatório.', 'danger')
            return redirect(url_for('catalogos.categorias_reembolso_criar'))
        cat = CategoriaReembolso(nome=nome, descricao=descricao or None, ativo=True, admin_id=admin_id)
        db.session.add(cat)
        db.session.commit()
        flash(f'Categoria "{nome}" criada com sucesso!', 'success')
        return redirect(url_for('catalogos.categorias_reembolso'))
    return render_template('catalogos/categorias_reembolso_form.html', categoria=None)


@catalogos_bp.route('/categorias-reembolso/editar/<int:id>', methods=['GET', 'POST'])
@login_required
def categorias_reembolso_editar(id):
    admin_id, err = _require_admin()
    if err:
        return err
    cat = CategoriaReembolso.query.filter_by(id=id, admin_id=admin_id).first_or_404()
    if request.method == 'POST':
        nome = request.form.get('nome', '').strip()
        descricao = request.form.get('descricao', '').strip()
        if not nome:
            flash('Nome é obrigatório.', 'danger')
            return redirect(url_for('catalogos.categorias_reembolso_editar', id=id))
        cat.nome = nome
        cat.descricao = descricao or None
        db.session.commit()
        flash(f'Categoria "{nome}" atualizada com sucesso!', 'success')
        return redirect(url_for('catalogos.categorias_reembolso'))
    return render_template('catalogos/categorias_reembolso_form.html', categoria=cat)


@catalogos_bp.route('/categorias-reembolso/toggle/<int:id>', methods=['POST'])
@login_required
def categorias_reembolso_toggle(id):
    admin_id, err = _require_admin()
    if err:
        return err
    cat = CategoriaReembolso.query.filter_by(id=id, admin_id=admin_id).first_or_404()
    cat.ativo = not cat.ativo
    db.session.commit()
    estado = 'ativada' if cat.ativo else 'desativada'
    flash(f'Categoria "{cat.nome}" {estado}.', 'success')
    return redirect(url_for('catalogos.categorias_reembolso'))


@catalogos_bp.route('/categorias-reembolso/deletar/<int:id>', methods=['POST'])
@login_required
def categorias_reembolso_deletar(id):
    admin_id, err = _require_admin()
    if err:
        return err
    cat = CategoriaReembolso.query.filter_by(id=id, admin_id=admin_id).first_or_404()
    from sqlalchemy import text as _text
    col_exists = db.session.execute(_text("""
        SELECT 1 FROM information_schema.columns
        WHERE table_name = 'reembolso_funcionario'
          AND column_name = 'categoria_reembolso_id'
        LIMIT 1
    """)).first()
    if col_exists:
        em_uso = db.session.execute(
            _text("SELECT 1 FROM reembolso_funcionario WHERE categoria_reembolso_id = :cid LIMIT 1"),
            {'cid': cat.id}
        ).first()
        if em_uso:
            flash(f'Não é possível excluir: a categoria "{cat.nome}" está vinculada a reembolsos existentes.', 'danger')
            return redirect(url_for('catalogos.categorias_reembolso'))
    db.session.delete(cat)
    db.session.commit()
    flash(f'Categoria "{cat.nome}" excluída.', 'success')
    return redirect(url_for('catalogos.categorias_reembolso'))
