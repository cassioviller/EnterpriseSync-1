"""
Blueprint de Importação de Funcionários via Excel — SIGE v9.0
Rota: /importacao/*
"""
import logging
import os
from flask import Blueprint, render_template, request, redirect, url_for, flash, send_file
from flask_login import login_required, current_user

from models import db
from views.helpers import get_admin_id_robusta

logger = logging.getLogger(__name__)

importacao_bp = Blueprint('importacao', __name__, url_prefix='/importacao')

TEMPLATE_PATH = os.path.join(os.path.dirname(__file__), 'static', 'templates_importacao', '1_funcionarios.xlsx')


@importacao_bp.route('/', methods=['GET'])
@login_required
def index():
    return render_template('importacao/index.html')


@importacao_bp.route('/template/funcionarios', methods=['GET'])
@login_required
def baixar_template():
    if not os.path.exists(TEMPLATE_PATH):
        flash('Template não encontrado.', 'warning')
        return redirect(url_for('importacao.index'))
    return send_file(TEMPLATE_PATH, as_attachment=True, download_name='1_funcionarios.xlsx')


@importacao_bp.route('/upload/funcionarios', methods=['POST'])
@login_required
def upload_funcionarios():
    arquivo = request.files.get('arquivo')

    if not arquivo or arquivo.filename == '':
        flash('Nenhum arquivo selecionado.', 'warning')
        return redirect(url_for('importacao.index'))

    ext = arquivo.filename.rsplit('.', 1)[-1].lower() if '.' in arquivo.filename else ''
    if ext != 'xlsx':
        flash('Formato inválido. Use o arquivo .xlsx (Excel 2007 ou superior).', 'danger')
        return redirect(url_for('importacao.index'))

    admin_id = get_admin_id_robusta()

    try:
        import openpyxl
        wb = openpyxl.load_workbook(arquivo, data_only=True)
        ws = wb.active
    except Exception as e:
        flash(f'Erro ao abrir planilha: {e}', 'danger')
        return redirect(url_for('importacao.index'))

    try:
        from services.importacao_excel import importar_funcionarios
        resultado = importar_funcionarios(ws, admin_id)
    except Exception as e:
        logger.error(f"[IMPORTACAO] Erro fatal: {e}", exc_info=True)
        flash(f'Erro inesperado durante a importação: {e}', 'danger')
        return redirect(url_for('importacao.index'))

    return render_template('importacao/resultado.html', resultado=resultado)
