"""
Blueprint de Importação Excel — SIGE v9.0
Módulos: Funcionários, Diárias, Alimentação, Transporte, Custos, Fluxo de Caixa
Fluxo por módulo: download template → upload → preview → confirmar
"""
import hashlib
import hmac
import json
import logging
import os
import uuid
from datetime import datetime

from flask import (Blueprint, current_app, flash, redirect, render_template,
                   request, send_file, url_for, jsonify)
from flask_login import current_user, login_required

from models import db
from views.helpers import get_admin_id_robusta

logger = logging.getLogger(__name__)

importacao_bp = Blueprint('importacao', __name__, url_prefix='/importacao')


def _get_chave_hmac() -> bytes:
    """Retorna a chave HMAC derivada do secret_key configurado."""
    chave = current_app.secret_key
    if not chave:
        raise RuntimeError(
            'SECRET_KEY não configurada. Defina a variável de ambiente SESSION_SECRET.'
        )
    return chave.encode() if isinstance(chave, str) else chave


def _assinar_payload(dados: list, admin_id: int, modulo: str) -> str:
    """
    Serializa e assina a lista de dados com HMAC-SHA256.
    O admin_id e modulo são incluídos no envelope para evitar replay cross-context.
    """
    envelope = {'admin_id': admin_id, 'modulo': modulo, 'rows': dados}
    body = json.dumps(envelope, sort_keys=True, default=str).encode()
    sig = hmac.new(_get_chave_hmac(), body, digestmod=hashlib.sha256).hexdigest()
    return f"{sig}:{body.decode()}"


def _verificar_payload(token: str, admin_id: int, modulo: str):
    """
    Verifica a assinatura e retorna a lista de dados.
    Retorna None se inválido, adulterado, ou se admin_id/modulo não correspondem.
    """
    try:
        sig_rec, body = token.split(':', 1)
    except ValueError:
        return None
    try:
        sig_esp = hmac.new(_get_chave_hmac(), body.encode(), digestmod=hashlib.sha256).hexdigest()
    except RuntimeError:
        return None
    if not hmac.compare_digest(sig_rec, sig_esp):
        return None
    try:
        envelope = json.loads(body)
    except (json.JSONDecodeError, ValueError):
        return None
    # Verificação de contexto — previne replay cross-tenant e cross-modulo
    if envelope.get('admin_id') != admin_id or envelope.get('modulo') != modulo:
        return None
    return envelope.get('rows', [])

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
            ('email', 'E-mail'),
            ('tipo_remuneracao', 'Remuneração'),
            ('valor', 'Valor (R$)'),
            ('data_admissao', 'Admissão'),
            ('funcao_nome', 'Função'),
        ],
        'tem_defaults': True,
    },
    'diarias': {
        'label': 'Diárias',
        'icone': 'calendar',
        'cor': '#155724',
        'cor_bg': '#d4edda',
        'template_file': '2_diarias.xlsx',
        'descricao': 'Registra diárias por funcionário e data. Suporta formato SIGE (uma linha/dia) e Colaboradores (múltiplos funcionários). Tipos especiais no campo Obra: FERIADO, FALTOU, FOLGA, DESCANSO, FALTA → sem lançamento · ATESTADO → só diária.',
        'colunas': [
            ('nome', 'Funcionário'),
            ('data', 'Data'),
            ('obra_nome', 'Obra / Tipo'),
            ('tipo_label', 'Lançamento'),
            ('valor_diaria', 'Diária (R$)'),
            ('valor_va', 'VA (R$)'),
            ('valor_vt', 'VT (R$)'),
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
    fmt = request.args.get('formato', 'sige')
    if modulo == 'diarias' and fmt == 'colaboradores':
        fname = '2_diarias_colaboradores.xlsx'
    else:
        fname = cfg['template_file']
    path = os.path.join(TEMPLATES_DIR, fname)
    if not os.path.exists(path):
        flash('Template não encontrado no servidor.', 'warning')
        return redirect(url_for('importacao.index'))
    return send_file(path, as_attachment=True, download_name=fname)


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
    # Assina com admin_id + modulo para impedir adulteração e replay cross-context
    dados_assinados = _assinar_payload(validos, admin_id, modulo)

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

    # Verifica assinatura e contexto (admin_id + modulo) — rejeita payload adulterado/replay
    rows = _verificar_payload(token, admin_id, modulo)
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


# ─── Fluxo de Caixa ─────────────────────────────────────────────────────────

@importacao_bp.route('/fluxo-caixa/upload', methods=['POST'])
@login_required
def fluxo_caixa_upload():
    """Recebe o arquivo, processa e exibe preview de 4 seções."""
    arquivo = request.files.get('arquivo')
    if not arquivo or arquivo.filename == '':
        flash('Nenhum arquivo selecionado.', 'warning')
        return redirect(url_for('importacao.index'))

    ext = arquivo.filename.rsplit('.', 1)[-1].lower() if '.' in arquivo.filename else ''
    if ext != 'xlsx':
        flash('Formato inválido. Use arquivo .xlsx.', 'danger')
        return redirect(url_for('importacao.index'))

    admin_id = get_admin_id_robusta()

    try:
        import io
        from services.importacao_excel import ImportacaoFluxoCaixa
        conteudo = arquivo.read()
        arquivo_like = io.BytesIO(conteudo)
        svc = ImportacaoFluxoCaixa()
        resultado = svc.processar(arquivo_like, admin_id)
    except Exception as e:
        logger.error(f'[FLUXO_CAIXA] Erro no upload: {e}', exc_info=True)
        flash(f'Erro ao processar arquivo: {e}', 'danger')
        return redirect(url_for('importacao.index'))

    entradas = resultado['entradas']
    saidas_auto = resultado['saidas_auto']
    saidas_manual = resultado['saidas_manual']
    ignorados = resultado['ignorados']

    # Assinar payload com HMAC (envelope contendo os 3 tipos)
    payload = {
        'entradas': entradas,
        'saidas_auto': saidas_auto,
        'saidas_manual': saidas_manual,
    }
    dados_assinados = _assinar_payload([payload], admin_id, 'fluxo_caixa')

    CATEGORIAS_OPCOES = [
        ('SALARIO', 'Salário'),
        ('MAO_OBRA_DIRETA', 'Mão de Obra Direta'),
        ('MATERIAL', 'Material'),
        ('ALIMENTACAO', 'Alimentação'),
        ('TRANSPORTE', 'Transporte'),
        ('ALUGUEL_UTILITIES', 'Aluguel / Utilitários'),
        ('TRIBUTOS', 'Tributos'),
        ('EQUIPAMENTO', 'Equipamento'),
        ('OUTROS', 'Outros'),
    ]

    return render_template(
        'importacao/preview_fluxo.html',
        entradas=entradas,
        saidas_auto=saidas_auto,
        saidas_manual=saidas_manual,
        ignorados=ignorados,
        categorias_opcoes=CATEGORIAS_OPCOES,
        dados_json=dados_assinados,
        total_saidas=len(saidas_auto) + len(saidas_manual),
        total_valor_saidas=sum(r.get('valor', 0) for r in saidas_auto + saidas_manual),
        total_valor_entradas=sum(r.get('valor', 0) for r in entradas),
    )


@importacao_bp.route('/fluxo-caixa/confirmar', methods=['POST'])
@login_required
def fluxo_caixa_confirmar():
    """Persiste os dados confirmados após o preview."""
    admin_id = get_admin_id_robusta()
    token = request.form.get('dados_json', '')

    rows = _verificar_payload(token, admin_id, 'fluxo_caixa')
    if rows is None or not rows:
        flash('Dados de preview inválidos ou expirados — faça o upload novamente.', 'danger')
        return redirect(url_for('importacao.index'))

    payload = rows[0]

    # Coletar edições manuais do form
    saidas_auto = payload.get('saidas_auto', [])
    saidas_manual = payload.get('saidas_manual', [])
    entradas = payload.get('entradas', [])

    # Aplicar categorias editadas pelo usuário nas saídas auto
    for i, row in enumerate(saidas_auto):
        cat_editada = request.form.get(f'cat_auto_{i}')
        if cat_editada:
            row['tipo_categoria'] = cat_editada

    # Aplicar categorias das saídas manuais (obrigatório)
    for i, row in enumerate(saidas_manual):
        cat_manual = request.form.get(f'cat_manual_{i}')
        if cat_manual:
            row['tipo_categoria'] = cat_manual
        elif not row.get('tipo_categoria'):
            flash('Há saídas sem categoria definida. Preencha todos os campos obrigatórios.', 'warning')
            return redirect(url_for('importacao.index'))

    todas_saidas = saidas_auto + saidas_manual

    batch_id = f"import_{datetime.now().strftime('%Y%m%d_%H%M')}_{uuid.uuid4().hex[:6]}"

    try:
        from services.importacao_excel import ImportacaoFluxoCaixa
        svc = ImportacaoFluxoCaixa()
        resultado = svc.importar({
            'entradas': entradas,
            'saidas': todas_saidas,
            'batch_id': batch_id,
        }, admin_id)
    except Exception as e:
        logger.error(f'[FLUXO_CAIXA] Erro no confirmar: {e}', exc_info=True)
        flash(f'Erro ao importar: {e}', 'danger')
        return redirect(url_for('importacao.index'))

    return render_template(
        'importacao/resultado_fluxo.html',
        resultado=resultado,
        batch_id=batch_id,
    )


@importacao_bp.route('/fluxo-caixa/rollback/<batch_id>', methods=['POST'])
@login_required
def fluxo_caixa_rollback(batch_id):
    """Desfaz uma importação inteira pelo batch_id."""
    admin_id = get_admin_id_robusta()
    if not batch_id or not batch_id.startswith('import_'):
        flash('Batch ID inválido.', 'danger')
        return redirect(url_for('importacao.historico'))

    try:
        from sqlalchemy import text as sa_text
        with db.engine.begin() as conn:
            # Ordem: FluxoCaixa e ContaReceber primeiro, depois ContaPagar e GestaoCustoPai
            r1 = conn.execute(sa_text(
                "DELETE FROM fluxo_caixa WHERE import_batch_id=:bid AND admin_id=:aid"
            ), {'bid': batch_id, 'aid': admin_id})
            r2 = conn.execute(sa_text(
                "DELETE FROM conta_receber WHERE import_batch_id=:bid AND admin_id=:aid"
            ), {'bid': batch_id, 'aid': admin_id})
            r3 = conn.execute(sa_text(
                "DELETE FROM conta_pagar WHERE import_batch_id=:bid AND admin_id=:aid"
            ), {'bid': batch_id, 'aid': admin_id})
            # Filhos antes do pai (coluna = pai_id)
            conn.execute(sa_text("""
                DELETE FROM gestao_custo_filho
                WHERE pai_id IN (
                    SELECT id FROM gestao_custo_pai
                    WHERE import_batch_id=:bid AND admin_id=:aid
                )
            """), {'bid': batch_id, 'aid': admin_id})
            r4 = conn.execute(sa_text(
                "DELETE FROM gestao_custo_pai WHERE import_batch_id=:bid AND admin_id=:aid"
            ), {'bid': batch_id, 'aid': admin_id})

        total = r1.rowcount + r2.rowcount + r3.rowcount + r4.rowcount
        flash(f'Importação {batch_id} desfeita com sucesso. {total} registros removidos.', 'success')
    except Exception as e:
        logger.error(f'[ROLLBACK] Erro: {e}', exc_info=True)
        flash(f'Erro ao desfazer importação: {e}', 'danger')

    return redirect(url_for('importacao.historico'))


@importacao_bp.route('/historico', methods=['GET'])
@login_required
def historico():
    """Lista todas as importações de fluxo de caixa com batch_id.
    UNION de gestao_custo_pai e conta_receber para cobrir lotes com só entradas.
    """
    admin_id = get_admin_id_robusta()
    try:
        from sqlalchemy import text as sa_text
        with db.engine.connect() as conn:
            # Custos (saídas)
            custo_rows = conn.execute(sa_text("""
                SELECT import_batch_id,
                       MIN(data_criacao) as data_import,
                       COUNT(*) as n_custos,
                       SUM(valor_total) as total_valor
                FROM gestao_custo_pai
                WHERE import_batch_id IS NOT NULL
                  AND import_batch_id LIKE 'import\_%' ESCAPE '\\'
                  AND admin_id = :aid
                GROUP BY import_batch_id
            """), {'aid': admin_id}).fetchall()

            # Entradas (conta_receber)
            entrada_rows = conn.execute(sa_text("""
                SELECT import_batch_id,
                       MIN(created_at) as data_import,
                       COUNT(*) as n_entradas,
                       SUM(valor_original) as total
                FROM conta_receber
                WHERE import_batch_id IS NOT NULL
                  AND import_batch_id LIKE 'import\_%' ESCAPE '\\'
                  AND admin_id = :aid
                GROUP BY import_batch_id
            """), {'aid': admin_id}).fetchall()

        custo_map = {r[0]: {'data_import': r[1], 'n': r[2], 'total': float(r[3] or 0)}
                     for r in custo_rows}
        entrada_map = {r[0]: {'data_import': r[1], 'n': r[2], 'total': float(r[3] or 0)}
                       for r in entrada_rows}

        # UNION de todos os batch_ids conhecidos
        all_bids = sorted(
            set(custo_map.keys()) | set(entrada_map.keys()),
            key=lambda b: (custo_map.get(b, {}).get('data_import')
                           or entrada_map.get(b, {}).get('data_import')),
            reverse=True,
        )

        batches = []
        for bid in all_bids:
            c = custo_map.get(bid, {})
            e = entrada_map.get(bid, {})
            data_import = c.get('data_import') or e.get('data_import')
            batches.append({
                'batch_id': bid,
                'data_import': data_import,
                'n_custos': c.get('n', 0),
                'total_custos': c.get('total', 0.0),
                'n_entradas': e.get('n', 0),
                'total_entradas': e.get('total', 0.0),
            })

    except Exception as e:
        logger.error(f'[HISTORICO] {e}', exc_info=True)
        batches = []
        flash(f'Erro ao carregar histórico: {e}', 'warning')

    return render_template('importacao/historico.html', batches=batches)
