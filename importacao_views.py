"""
Blueprint de Importação Excel — SIGE v9.0
5 módulos: Funcionários, Diárias, Alimentação, Transporte, Custos
Fluxo por módulo: download template → upload → preview → confirmar
"""
import hashlib
import hmac
import json
import logging
import os

from flask import (Blueprint, current_app, flash, redirect, render_template,
                   request, send_file, url_for)
from flask_login import current_user, login_required

from models import db
from views.helpers import get_admin_id_robusta

logger = logging.getLogger(__name__)

importacao_bp = Blueprint('importacao', __name__, url_prefix='/importacao')


def _assinar_payload(dados: list) -> str:
    """Serializa e assina a lista de dados com HMAC-SHA256 para evitar adulteração."""
    body = json.dumps(dados, sort_keys=True, default=str).encode()
    chave = (current_app.secret_key or 'sige-secret').encode()
    sig = hmac.new(chave, body, digestmod=hashlib.sha256).hexdigest()
    return f"{sig}:{body.decode()}"


def _verificar_payload(token: str):
    """Verifica a assinatura e retorna a lista de dados, ou None se inválido."""
    try:
        sig_rec, body = token.split(':', 1)
    except ValueError:
        return None
    chave = (current_app.secret_key or 'sige-secret').encode()
    sig_esp = hmac.new(chave, body.encode(), digestmod=hashlib.sha256).hexdigest()
    if not hmac.compare_digest(sig_rec, sig_esp):
        return None
    try:
        return json.loads(body)
    except (json.JSONDecodeError, ValueError):
        return None

TEMPLATES_DIR = os.path.join(os.path.dirname(__file__), 'static', 'templates_importacao')

MODULO_CONFIG = {
    'funcionarios': {
        'label': 'Funcionários',
        'icone': 'users',
        'cor': '#1e3a5f',
        'cor_bg': '#e8f0f8',
        'template_file': '1_funcionarios.xlsx',
        'descricao': 'Cadastra ou atualiza funcionários em massa. Suporta o formato SIGE e planilha Registro de Colaboradores.',
        'colunas': [
            ('operacao', 'Ação'),
            ('nome', 'Nome'),
            ('cpf', 'CPF'),
            ('tipo_remuneracao', 'Remuneração'),
            ('valor', 'Valor (R$)'),
            ('data_admissao', 'Admissão'),
        ],
        'tem_defaults': True,
    },
    'diarias': {
        'label': 'Diárias',
        'icone': 'calendar',
        'cor': '#155724',
        'cor_bg': '#d4edda',
        'template_file': '2_diarias.xlsx',
        'descricao': 'Registra diárias de mão de obra por funcionário e data. Integra automaticamente com Contas a Pagar.',
        'colunas': [
            ('nome', 'Funcionário'),
            ('data', 'Data'),
            ('valor', 'Valor (R$)'),
            ('obra_nome', 'Obra'),
            ('status', 'Status'),
            ('descricao', 'Descrição'),
        ],
        'tem_defaults': False,
    },
    'alimentacao': {
        'label': 'Alimentação',
        'icone': 'coffee',
        'cor': '#856404',
        'cor_bg': '#fff3cd',
        'template_file': '3_alimentacao.xlsx',
        'descricao': 'Lançamentos de alimentação com múltiplos funcionários separados por ponto e vírgula.',
        'colunas': [
            ('data', 'Data'),
            ('obra_nome', 'Obra'),
            ('valor_total', 'Valor Total (R$)'),
            ('funcionarios_nomes', 'Funcionários'),
            ('descricao', 'Descrição'),
            ('restaurante', 'Restaurante'),
        ],
        'tem_defaults': False,
    },
    'transporte': {
        'label': 'Transporte',
        'icone': 'truck',
        'cor': '#6f42c1',
        'cor_bg': '#ede7f6',
        'template_file': '4_transporte.xlsx',
        'descricao': 'Registra despesas de transporte: VT, combustível, aplicativo, passagens. Integra com Contas a Pagar.',
        'colunas': [
            ('nome', 'Funcionário'),
            ('data', 'Data'),
            ('categoria', 'Categoria'),
            ('valor', 'Valor (R$)'),
            ('obra_nome', 'Obra'),
            ('descricao', 'Descrição'),
        ],
        'tem_defaults': False,
    },
    'custos': {
        'label': 'Custos (Contas a Pagar)',
        'icone': 'file-text',
        'cor': '#721c24',
        'cor_bg': '#f8d7da',
        'template_file': '5_custos.xlsx',
        'descricao': 'Importa lançamentos financeiros diretamente para Contas a Pagar. Ideal para migrar dados de planilhas de pagamentos.',
        'colunas': [
            ('fornecedor', 'Fornecedor'),
            ('descricao', 'Descrição'),
            ('valor', 'Valor (R$)'),
            ('data', 'Data'),
            ('categoria', 'Categoria'),
            ('obra_nome', 'Obra'),
            ('status', 'Status'),
        ],
        'tem_defaults': False,
    },
}

MODULOS_VALIDOS = set(MODULO_CONFIG.keys())


def _parse_xlsx(arquivo):
    import openpyxl
    wb = openpyxl.load_workbook(arquivo, data_only=True)
    return wb.active


# ─── Rotas ────────────────────────────────────────────────────────────────────

@importacao_bp.route('/', methods=['GET'])
@login_required
def index():
    return render_template('importacao/index.html', modulos=MODULO_CONFIG)


@importacao_bp.route('/template/<modulo>', methods=['GET'])
@login_required
def baixar_template(modulo):
    if modulo not in MODULOS_VALIDOS:
        flash('Módulo inválido.', 'danger')
        return redirect(url_for('importacao.index'))
    cfg = MODULO_CONFIG[modulo]
    path = os.path.join(TEMPLATES_DIR, cfg['template_file'])
    if not os.path.exists(path):
        flash('Template não encontrado no servidor.', 'warning')
        return redirect(url_for('importacao.index'))
    return send_file(path, as_attachment=True, download_name=cfg['template_file'])


def _handle_preview(modulo):
    """Lógica central de preview reutilizada pelas rotas genérica e por módulo."""
    if modulo not in MODULOS_VALIDOS:
        flash('Módulo inválido.', 'danger')
        return redirect(url_for('importacao.index'))

    arquivo = request.files.get('arquivo')
    if not arquivo or arquivo.filename == '':
        flash('Nenhum arquivo selecionado.', 'warning')
        return redirect(url_for('importacao.index'))

    ext = arquivo.filename.rsplit('.', 1)[-1].lower() if '.' in arquivo.filename else ''
    if ext != 'xlsx':
        flash('Formato inválido. Use arquivo .xlsx (Excel 2007 ou superior).', 'danger')
        return redirect(url_for('importacao.index'))

    admin_id = get_admin_id_robusta()

    try:
        ws = _parse_xlsx(arquivo)
    except Exception as e:
        flash(f'Erro ao abrir planilha: {e}', 'danger')
        return redirect(url_for('importacao.index'))

    try:
        from services.importacao_excel import MODULO_MAP
        servico = MODULO_MAP[modulo]()

        if modulo == 'funcionarios':
            defaults = {
                'data_admissao': request.form.get('default_data_admissao') or None,
                'tipo_remuneracao': request.form.get('default_tipo_remuneracao') or 'salario',
                'valor': request.form.get('default_valor') or '0',
            }
            validos, erros = servico.processar(ws, admin_id, defaults=defaults)
        else:
            validos, erros = servico.processar(ws, admin_id)

    except Exception as e:
        logger.error(f'[IMPORTACAO][{modulo}] Erro no preview: {e}', exc_info=True)
        flash(f'Erro inesperado ao processar planilha: {e}', 'danger')
        return redirect(url_for('importacao.index'))

    cfg = MODULO_CONFIG[modulo]
    # Assina o payload para impedir adulteração entre preview e confirmar
    dados_assinados = _assinar_payload(validos)

    return render_template(
        'importacao/preview.html',
        modulo=modulo,
        cfg=cfg,
        validos=validos,
        erros=erros,
        colunas=cfg['colunas'],
        dados_json=dados_assinados,
    )


def _handle_confirmar(modulo):
    """Lógica central de confirmação reutilizada pelas rotas genérica e por módulo."""
    if modulo not in MODULOS_VALIDOS:
        flash('Módulo inválido.', 'danger')
        return redirect(url_for('importacao.index'))

    admin_id = get_admin_id_robusta()
    token = request.form.get('dados_json', '')

    # Verifica assinatura — rejeita payload adulterado
    rows = _verificar_payload(token)
    if rows is None:
        flash('Dados de preview inválidos ou adulterados — faça o upload novamente.', 'danger')
        return redirect(url_for('importacao.index'))

    if not rows:
        flash('Nenhum registro válido para importar.', 'warning')
        return redirect(url_for('importacao.index'))

    try:
        from services.importacao_excel import MODULO_MAP
        servico = MODULO_MAP[modulo]()
        resultado = servico.importar(rows, admin_id)
    except Exception as e:
        logger.error(f'[IMPORTACAO][{modulo}] Erro no confirmar: {e}', exc_info=True)
        flash(f'Erro inesperado ao importar: {e}', 'danger')
        return redirect(url_for('importacao.index'))

    cfg = MODULO_CONFIG[modulo]
    return render_template(
        'importacao/resultado.html',
        modulo=modulo,
        cfg=cfg,
        resultado=resultado,
    )


# ── Rotas genéricas (/preview/<modulo>) e específicas (/funcionarios/preview) ──

@importacao_bp.route('/preview/<modulo>', methods=['POST'])
@login_required
def preview(modulo):
    return _handle_preview(modulo)


@importacao_bp.route('/confirmar/<modulo>', methods=['POST'])
@login_required
def confirmar(modulo):
    return _handle_confirmar(modulo)


# Rotas explícitas por módulo (contrato especificado no task)
@importacao_bp.route('/funcionarios/preview', methods=['POST'])
@login_required
def funcionarios_preview():
    return _handle_preview('funcionarios')


@importacao_bp.route('/funcionarios/confirmar', methods=['POST'])
@login_required
def funcionarios_confirmar():
    return _handle_confirmar('funcionarios')


@importacao_bp.route('/diarias/preview', methods=['POST'])
@login_required
def diarias_preview():
    return _handle_preview('diarias')


@importacao_bp.route('/diarias/confirmar', methods=['POST'])
@login_required
def diarias_confirmar():
    return _handle_confirmar('diarias')


@importacao_bp.route('/alimentacao/preview', methods=['POST'])
@login_required
def alimentacao_preview():
    return _handle_preview('alimentacao')


@importacao_bp.route('/alimentacao/confirmar', methods=['POST'])
@login_required
def alimentacao_confirmar():
    return _handle_confirmar('alimentacao')


@importacao_bp.route('/transporte/preview', methods=['POST'])
@login_required
def transporte_preview():
    return _handle_preview('transporte')


@importacao_bp.route('/transporte/confirmar', methods=['POST'])
@login_required
def transporte_confirmar():
    return _handle_confirmar('transporte')


@importacao_bp.route('/custos/preview', methods=['POST'])
@login_required
def custos_preview():
    return _handle_preview('custos')


@importacao_bp.route('/custos/confirmar', methods=['POST'])
@login_required
def custos_confirmar():
    return _handle_confirmar('custos')
