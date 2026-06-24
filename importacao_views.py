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

from flask import (Blueprint, current_app, flash, jsonify, redirect,
                   render_template, request, send_file, url_for)
from flask_login import login_required

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


# ─── API: Entidades para autocomplete ────────────────────────────────────────

@importacao_bp.route('/api/entidades')
@login_required
def api_entidades():
    """Retorna lista JSON de fornecedores + funcionários para Tom Select."""
    from models import Fornecedor, Funcionario
    admin_id = get_admin_id_robusta()
    q = request.args.get('q', '').strip()

    results = []

    func_q = Funcionario.query.filter_by(admin_id=admin_id, ativo=True)
    if q:
        func_q = func_q.filter(Funcionario.nome.ilike(f'%{q}%'))
    for f in func_q.order_by(Funcionario.nome).limit(20).all():
        results.append({'id': f'funcionario:{f.id}', 'nome': f.nome, 'tipo': 'funcionario'})

    forn_q = Fornecedor.query.filter_by(admin_id=admin_id, ativo=True)
    if q:
        forn_q = forn_q.filter(
            db.or_(
                Fornecedor.nome.ilike(f'%{q}%'),
                Fornecedor.razao_social.ilike(f'%{q}%'),
                Fornecedor.nome_fantasia.ilike(f'%{q}%'),
            )
        )
    for f in forn_q.order_by(Fornecedor.nome).limit(20).all():
        display = f.nome or f.razao_social or f.nome_fantasia or '?'
        results.append({'id': f'fornecedor:{f.id}', 'nome': display, 'tipo': 'fornecedor'})

    return jsonify(results)


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

    # Ler período selecionado pelo usuário
    data_inicio = None
    data_fim = None
    try:
        di_str = request.form.get('data_inicio', '').strip()
        df_str = request.form.get('data_fim', '').strip()
        if di_str:
            data_inicio = datetime.strptime(di_str, '%Y-%m-%d').date()
        if df_str:
            data_fim = datetime.strptime(df_str, '%Y-%m-%d').date()
    except ValueError:
        pass

    try:
        import io
        from services.importacao_excel import ImportacaoFluxoCaixa
        conteudo = arquivo.read()
        arquivo_like = io.BytesIO(conteudo)
        svc = ImportacaoFluxoCaixa()
        resultado = svc.processar(arquivo_like, admin_id,
                                  data_inicio=data_inicio, data_fim=data_fim)
    except Exception as e:
        logger.error(f'[FLUXO_CAIXA] Erro no upload: {e}', exc_info=True)
        flash(f'Erro ao processar arquivo: {e}', 'danger')
        return redirect(url_for('importacao.index'))

    entradas = resultado['entradas']
    saidas_auto = resultado['saidas_auto']
    saidas_manual = resultado['saidas_manual']
    ignorados = resultado['ignorados']
    transferencias = resultado.get('transferencias', [])
    primeiro_dia = resultado.get('primeiro_dia')
    periodo_str = resultado.get('periodo_str', '—')
    sugestoes = resultado.get('sugestoes', [])

    # Persiste a fila por Termo do tenant (substitui as anteriores). Guardado:
    # uma falha aqui não pode derrubar o preview.
    try:
        from services.seed_palavras_chave import persistir_sugestoes
        persistir_sugestoes(admin_id, sugestoes, commit=True)
    except Exception as _exc_sug:
        from models import db as _db
        _db.session.rollback()
        logger.warning(f'[FLUXO_CAIXA] Falha ao persistir sugestões: {_exc_sug}')

    # Assinar payload com HMAC (envelope contendo os 3 tipos + transferências)
    payload = {
        'entradas': entradas,
        'saidas_auto': saidas_auto,
        'saidas_manual': saidas_manual,
        'transferencias': transferencias,
    }
    dados_assinados = _assinar_payload([payload], admin_id, 'fluxo_caixa')

    from models import BancoEmpresa, CategoriaFluxoCaixa, Obra
    bancos = BancoEmpresa.query.filter_by(admin_id=admin_id, ativo=True).order_by(BancoEmpresa.nome_banco).all()
    categorias_tenant = CategoriaFluxoCaixa.query.filter_by(admin_id=admin_id, ativo=True).order_by(
        CategoriaFluxoCaixa.tipo,
        CategoriaFluxoCaixa.grupo_financeiro.nullslast(),
        CategoriaFluxoCaixa.nome
    ).all()
    categorias_saida = [c for c in categorias_tenant if c.tipo == 'SAIDA']
    categorias_entrada = [c for c in categorias_tenant if c.tipo == 'ENTRADA']
    obras = Obra.query.filter_by(admin_id=admin_id, ativo=True).order_by(Obra.nome).all()

    # Pré-selecionar categoria para entradas com tipo_categoria classificado
    # Mapeia tipo_categoria → cfc_id buscando por keywords no nome da categoria
    _CAT_ENT_KEYWORDS = {
        'RECEITA_SERVICO': ['serviç', 'obra', 'honorar', 'faturamento', 'medicao', 'medição'],
        'MAO_OBRA_DIRETA': ['servic', 'tercei', 'subempreit'],
        'TRIBUTOS': ['imposto', 'tributo', 'tax'],
        'OUTROS': ['outro'],
    }
    _cat_ent_map = {}
    for cfc in categorias_entrada:
        cfc_nome_lower = cfc.nome.lower()
        for tipo_cat, kws in _CAT_ENT_KEYWORDS.items():
            if tipo_cat not in _cat_ent_map:
                if any(kw in cfc_nome_lower for kw in kws):
                    _cat_ent_map[tipo_cat] = cfc.id
                    break
    for row in entradas:
        tc = row.get('tipo_categoria')
        if tc and not row.get('categoria_fluxo_caixa_id') and tc in _cat_ent_map:
            row['categoria_fluxo_caixa_id'] = _cat_ent_map[tc]

    return render_template(
        'importacao/preview_fluxo.html',
        entradas=entradas,
        saidas_auto=saidas_auto,
        saidas_manual=saidas_manual,
        ignorados=ignorados,
        transferencias=transferencias,
        categorias_tenant=categorias_tenant,
        categorias_saida=categorias_saida,
        categorias_entrada=categorias_entrada,
        dados_json=dados_assinados,
        bancos=bancos,
        obras=obras,
        total_saidas=len(saidas_auto) + len(saidas_manual),
        total_valor_saidas=sum(r.get('valor', 0) for r in saidas_auto + saidas_manual),
        total_valor_entradas=sum(r.get('valor', 0) for r in entradas),
        primeiro_dia=primeiro_dia,
        periodo_str=periodo_str,
        sugestoes=sugestoes,
    )


def _reclassificar_payload(admin_id, payload):
    """Reclassifica o payload do preview em memória com as Regras + Memória Exata
    atuais do tenant. Devolve (cls, novo_token) onde cls = {entradas, saidas_auto,
    saidas_manual, sugestoes} e novo_token é o payload re-assinado (HMAC)."""
    from models import CategoriaFluxoCaixa
    from services.classificador_cadastro import _norm as _norm_cat, Contexto
    from services.seed_palavras_chave import regras_do_tenant, carregar_memoria_exata
    from services.importacao_excel import classificar_preview

    entradas = payload.get('entradas', [])
    saidas = payload.get('saidas_auto', []) + payload.get('saidas_manual', [])
    cat_id_por_nome = {_norm_cat(c.nome): c.id for c in
                       CategoriaFluxoCaixa.query.filter_by(admin_id=admin_id, ativo=True).all()}
    ctx = Contexto(regras=regras_do_tenant(admin_id),
                   memoria_exata=carregar_memoria_exata(admin_id))
    cls = classificar_preview(entradas, saidas, ctx, cat_id_por_nome)
    novo_payload = {
        'entradas': cls['entradas'], 'saidas_auto': cls['saidas_auto'],
        'saidas_manual': cls['saidas_manual'],
        'transferencias': payload.get('transferencias', []),
    }
    return cls, _assinar_payload([novo_payload], admin_id, 'fluxo_caixa')


@importacao_bp.route('/fluxo-caixa/classificar-termo', methods=['POST'])
@login_required
def fluxo_caixa_classificar_termo():
    """Loop ao vivo (§7.4): cria uma Regra (origem='usuario') para o Termo e
    RECLASSIFICA o payload em memória, devolvendo as seções + a fila atualizadas —
    sem re-upload. Payload-como-estado: recebe e devolve o payload assinado (HMAC)."""
    admin_id = get_admin_id_robusta()
    data = request.get_json(silent=True) or request.form
    token = data.get('dados_json', '')
    termo = (data.get('termo') or '').strip()
    tipo = (data.get('tipo') or 'SAIDA').upper()
    try:
        categoria_id = int(data.get('categoria_id'))
    except (TypeError, ValueError):
        return jsonify({'ok': False, 'erro': 'categoria_id inválido'}), 400

    rows = _verificar_payload(token, admin_id, 'fluxo_caixa')
    if rows is None or not rows:
        return jsonify({'ok': False, 'erro': 'Preview inválido ou expirado.'}), 400
    if not termo:
        return jsonify({'ok': False, 'erro': 'Termo vazio.'}), 400
    if tipo not in ('ENTRADA', 'SAIDA'):
        return jsonify({'ok': False, 'erro': 'Tipo inválido.'}), 400

    from models import CategoriaFluxoCaixa, PalavraChaveCategoria
    from services.classificador_cadastro import _norm as _norm_cat

    # A categoria-alvo precisa ser do próprio tenant (ownership).
    cat = CategoriaFluxoCaixa.query.filter_by(id=categoria_id, admin_id=admin_id).first()
    if not cat:
        return jsonify({'ok': False, 'erro': 'Categoria não encontrada.'}), 404

    termo_norm = _norm_cat(termo)
    # Cria a Regra do usuário (campo_alvo='fornecedor', prioridade=40). Idempotente:
    # não duplica se a mesma regra já existir.
    ja_existe = PalavraChaveCategoria.query.filter_by(
        admin_id=admin_id, palavras=termo_norm, campo_alvo='fornecedor',
        tipo=tipo, origem='usuario').first()
    if not ja_existe:
        db.session.add(PalavraChaveCategoria(
            admin_id=admin_id, categoria_fluxo_caixa_id=categoria_id,
            palavras=termo_norm, campo_alvo='fornecedor', prioridade=40,
            tipo=tipo, origem='usuario', ativo=True))
        db.session.commit()

    cls, novo_token = _reclassificar_payload(admin_id, rows[0])
    return jsonify({
        'ok': True,
        'dados_json': novo_token,
        'entradas': cls['entradas'],
        'saidas_auto': cls['saidas_auto'],
        'saidas_manual': cls['saidas_manual'],
        'sugestoes': cls['sugestoes'],
    })


@importacao_bp.route('/fluxo-caixa/corrigir-linha', methods=['POST'])
@login_required
def fluxo_caixa_corrigir_linha():
    """Loop ao vivo (§7.3): Correção de UMA linha. Grava Memória Exata (texto
    idêntico futuro já vem classificado), reclassifica o payload e — se o contexto
    contraria a regra do Termo — devolve a proposta de regra refinada (a confirmar)."""
    admin_id = get_admin_id_robusta()
    data = request.get_json(silent=True) or request.form
    token = data.get('dados_json', '')
    descricao = (data.get('descricao') or '').strip()
    fornecedor = (data.get('fornecedor') or '').strip()
    plano = (data.get('plano_contas') or '').strip()
    tipo = (data.get('tipo') or 'SAIDA').upper()
    obra_id = data.get('obra_id')
    try:
        categoria_id = int(data.get('categoria_id'))
    except (TypeError, ValueError):
        return jsonify({'ok': False, 'erro': 'categoria_id inválido'}), 400

    rows = _verificar_payload(token, admin_id, 'fluxo_caixa')
    if rows is None or not rows:
        return jsonify({'ok': False, 'erro': 'Preview inválido ou expirado.'}), 400
    if tipo not in ('ENTRADA', 'SAIDA'):
        return jsonify({'ok': False, 'erro': 'Tipo inválido.'}), 400

    from models import CategoriaFluxoCaixa
    from services.classificador_cadastro import (
        Contexto, Lancamento, regra_vencedora, sugerir_regra_refinada,
    )
    from services.seed_palavras_chave import regras_do_tenant, registrar_correcao

    cat = CategoriaFluxoCaixa.query.filter_by(id=categoria_id, admin_id=admin_id).first()
    if not cat:
        return jsonify({'ok': False, 'erro': 'Categoria não encontrada.'}), 404

    lanc = Lancamento(descricao=descricao, fornecedor=fornecedor, plano=plano,
                      tem_obra=bool(obra_id), tipo=tipo)

    # Detecta a regra conflitante ANTES de gravar a Correção (sem Memória Exata):
    # se uma Regra classificaria isto para OUTRA categoria, ofereça refinar.
    sugestao_refinada = None
    conflitante = regra_vencedora(
        lanc, Contexto(regras=regras_do_tenant(admin_id), memoria_exata={}))
    if conflitante and conflitante.categoria_id != categoria_id:
        refinada = sugerir_regra_refinada(lanc, categoria_id, cat.nome, conflitante)
        if refinada.gatilho_extra:   # só oferece com contexto distintivo (senão reclassifica tudo)
            sugestao_refinada = {
                'palavras': refinada.palavras, 'gatilho_extra': refinada.gatilho_extra,
                'campo_alvo': refinada.campo_alvo, 'campo_extra': refinada.campo_extra,
                'categoria_id': categoria_id, 'categoria_nome': cat.nome,
                'prioridade': refinada.prioridade, 'tipo': refinada.tipo,
            }

    # Grava a Correção (Memória Exata: vale para importações futuras e para
    # Pendentes de texto idêntico) e reclassifica o payload.
    registrar_correcao(admin_id, lanc, categoria_id)
    db.session.commit()
    cls, _ = _reclassificar_payload(admin_id, rows[0])

    # PIN da linha corrigida: a decisão do usuário é autoritária NESTA importação,
    # mesmo quando uma Regra classificaria diferente (ordem Regra→Memória não
    # bastaria — a regra venceria). Força a categoria nas linhas de texto idêntico
    # e garante que saiam da fila (vão para auto). A regra refinada (a confirmar)
    # é o que faz a correção valer dali em diante.
    from services.classificador_cadastro import _norm as _norm_cat, derivar_macro
    alvo = _norm_cat(f"{descricao} {fornecedor}")
    macro = derivar_macro(cat.nome)

    def _reparticiona(lista, ent_key):
        auto, manual = [], []
        for r in lista:
            chave = _norm_cat(f"{r.get('descricao', '')} {r.get(ent_key, '')}")
            if chave == alvo:
                r['categoria_nome'] = cat.nome
                r['categoria_fluxo_caixa_id'] = categoria_id
                r['tipo_categoria'] = macro
                auto.append(r)
            elif r.get('categoria_nome') in ('Outras Saídas', 'Outros Recebimentos'):
                manual.append(r)
            else:
                auto.append(r)
        return auto, manual

    entradas_auto, _ent_manual = _reparticiona(cls['entradas'], 'cliente')
    saidas_auto, saidas_manual = _reparticiona(
        cls['saidas_auto'] + cls['saidas_manual'], 'fornecedor')
    entradas = entradas_auto + _ent_manual

    novo_payload = {'entradas': entradas, 'saidas_auto': saidas_auto,
                    'saidas_manual': saidas_manual,
                    'transferencias': rows[0].get('transferencias', [])}
    return jsonify({
        'ok': True,
        'dados_json': _assinar_payload([novo_payload], admin_id, 'fluxo_caixa'),
        'entradas': entradas,
        'saidas_auto': saidas_auto,
        'saidas_manual': saidas_manual,
        'sugestoes': cls['sugestoes'],
        'sugestao_refinada': sugestao_refinada,
    })


@importacao_bp.route('/fluxo-caixa/confirmar-regra-refinada', methods=['POST'])
@login_required
def fluxo_caixa_confirmar_regra_refinada():
    """Loop ao vivo (§7.3): efetiva a regra refinada proposta (1 clique). Cria a
    Regra do usuário com a condição extra (AND) e prioridade vencedora, e
    reclassifica o payload."""
    admin_id = get_admin_id_robusta()
    data = request.get_json(silent=True) or request.form
    token = data.get('dados_json', '')
    tipo = (data.get('tipo') or 'SAIDA').upper()
    campo_alvo = data.get('campo_alvo') or 'fornecedor'
    campo_extra = data.get('campo_extra') or 'descricao'
    try:
        categoria_id = int(data.get('categoria_id'))
        prioridade = int(data.get('prioridade', 39))
    except (TypeError, ValueError):
        return jsonify({'ok': False, 'erro': 'categoria_id/prioridade inválidos'}), 400

    def _csv(v):
        if isinstance(v, (list, tuple)):
            return ','.join(str(x) for x in v if x)
        return (v or '').strip()

    palavras = _csv(data.get('palavras'))
    gatilho_extra = _csv(data.get('gatilho_extra'))

    rows = _verificar_payload(token, admin_id, 'fluxo_caixa')
    if rows is None or not rows:
        return jsonify({'ok': False, 'erro': 'Preview inválido ou expirado.'}), 400
    if not palavras or not gatilho_extra:
        return jsonify({'ok': False, 'erro': 'Regra refinada incompleta.'}), 400
    if tipo not in ('ENTRADA', 'SAIDA'):
        return jsonify({'ok': False, 'erro': 'Tipo inválido.'}), 400

    from models import CategoriaFluxoCaixa, PalavraChaveCategoria

    cat = CategoriaFluxoCaixa.query.filter_by(id=categoria_id, admin_id=admin_id).first()
    if not cat:
        return jsonify({'ok': False, 'erro': 'Categoria não encontrada.'}), 404

    db.session.add(PalavraChaveCategoria(
        admin_id=admin_id, categoria_fluxo_caixa_id=categoria_id,
        palavras=palavras, campo_alvo=campo_alvo,
        gatilho_extra=gatilho_extra, campo_extra=campo_extra,
        prioridade=prioridade, tipo=tipo, origem='usuario', ativo=True))
    db.session.commit()

    cls, novo_token = _reclassificar_payload(admin_id, rows[0])
    return jsonify({
        'ok': True,
        'dados_json': novo_token,
        'entradas': cls['entradas'],
        'saidas_auto': cls['saidas_auto'],
        'saidas_manual': cls['saidas_manual'],
        'sugestoes': cls['sugestoes'],
    })


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

    # Pré-computar IDs de obras permitidas para este tenant (validação de ownership)
    from models import Obra as ObraModel
    _obras_tenant = ObraModel.query.filter_by(admin_id=admin_id, ativo=True).with_entities(ObraModel.id).all()
    _allowed_obra_ids = {r[0] for r in _obras_tenant}

    def _obra_segura(obra_val):
        """Converte valor do form em obra_id validado contra o tenant. Retorna None se inválido."""
        if not obra_val:
            return None
        try:
            oid = int(obra_val)
        except (ValueError, TypeError):
            return None
        return oid if oid in _allowed_obra_ids else None

    def _aplicar_categoria(row, cat_val, tipo_esperado=None):
        """Detecta prefixo cfc_<id> para categoria personalizada; senão usa tipo_categoria.
        Se tipo_esperado for fornecido ('ENTRADA' ou 'SAIDA'), valida tenant + tipo antes de aplicar.
        IDs inválidos ou cross-tenant são silenciosamente ignorados.
        """
        if not cat_val:
            return
        if cat_val.startswith('cfc_'):
            try:
                cfc_id = int(cat_val[4:])
            except ValueError:
                return
            from models import CategoriaFluxoCaixa
            q = CategoriaFluxoCaixa.query.filter_by(id=cfc_id, admin_id=admin_id, ativo=True)
            if tipo_esperado:
                q = q.filter_by(tipo=tipo_esperado)
            cfc = q.first()
            if cfc:
                row['categoria_fluxo_caixa_id'] = cfc.id
                row['tipo_categoria'] = row.get('tipo_categoria') or 'OUTROS'
        else:
            row['tipo_categoria'] = cat_val
            row['categoria_fluxo_caixa_id'] = None

    # Pré-carregar IDs válidos do tenant para validação de ownership
    from models import Fornecedor as _Forn, Funcionario as _Func
    _allowed_forn_ids = {
        r[0] for r in _Forn.query.filter_by(admin_id=admin_id, ativo=True)
                                  .with_entities(_Forn.id).all()
    }
    _allowed_func_ids = {
        r[0] for r in _Func.query.filter_by(admin_id=admin_id, ativo=True)
                                  .with_entities(_Func.id).all()
    }

    def _aplicar_destinatario(row, dest_val):
        """Override de entidade_tipo/entidade_id a partir do valor 'tipo:id' do Tom Select.
        Valor vazio limpa o vínculo. IDs fora do tenant são silenciosamente ignorados.
        """
        # Campo explicitamente limpo: apaga o vínculo fuzzy
        if not dest_val:
            row['entidade_tipo'] = None
            row['entidade_id'] = None
            return
        if ':' not in dest_val:
            return
        partes = dest_val.split(':', 1)
        if len(partes) != 2:
            return
        tipo, id_str = partes
        if tipo not in ('funcionario', 'fornecedor') or not id_str.isdigit():
            return
        eid = int(id_str)
        # Validação de ownership: ID deve pertencer ao tenant atual
        if tipo == 'funcionario' and eid not in _allowed_func_ids:
            logger.warning(f'[DEST] funcionario_id={eid} não pertence ao tenant {admin_id} — ignorado')
            return
        if tipo == 'fornecedor' and eid not in _allowed_forn_ids:
            logger.warning(f'[DEST] fornecedor_id={eid} não pertence ao tenant {admin_id} — ignorado')
            return
        row['entidade_tipo'] = tipo
        row['entidade_id'] = eid

    # Aplicar edições manuais nas saídas auto
    for i, row in enumerate(saidas_auto):
        row['obra_id'] = _obra_segura(request.form.get(f'obra_auto_{i}', '').strip())
        cat_editada = request.form.get(f'cat_auto_{i}')
        if cat_editada:
            _aplicar_categoria(row, cat_editada, tipo_esperado='SAIDA')
        # Checkbox "apenas pagamento"
        row['apenas_pagamento'] = request.form.get(f'apenas_pag_auto_{i}') is not None
        # Checkbox "reembolso"
        row['eh_reembolso'] = request.form.get(f'reembolso_auto_{i}') is not None
        # Banco vinculado
        banco_id_val = request.form.get(f'banco_auto_{i}', '').strip()
        row['banco_id'] = int(banco_id_val) if banco_id_val else None
        # Inline edits
        data_edit = request.form.get(f'data_auto_{i}', '').strip()
        if data_edit:
            row['data'] = data_edit
        desc_edit = request.form.get(f'desc_auto_{i}', '').strip()
        if desc_edit:
            row['descricao'] = desc_edit
        valor_edit = request.form.get(f'valor_auto_{i}', '').strip()
        if valor_edit:
            try:
                row['valor'] = float(valor_edit.replace(',', '.'))
            except ValueError:
                pass
        # Override de destinatário (Tom Select)
        _aplicar_destinatario(row, request.form.get(f'destinatario_auto_{i}', '').strip())

    # Aplicar edições manuais das saídas manuais
    for i, row in enumerate(saidas_manual):
        row['obra_id'] = _obra_segura(request.form.get(f'obra_manual_{i}', '').strip())
        cat_manual = request.form.get(f'cat_manual_{i}')
        if cat_manual:
            _aplicar_categoria(row, cat_manual, tipo_esperado='SAIDA')
        elif not row.get('tipo_categoria'):
            row['tipo_categoria'] = 'OUTROS'
        # Checkbox "apenas pagamento"
        row['apenas_pagamento'] = request.form.get(f'apenas_pag_manual_{i}') is not None
        # Checkbox "reembolso"
        row['eh_reembolso'] = request.form.get(f'reembolso_manual_{i}') is not None
        # Banco vinculado
        banco_id_val = request.form.get(f'banco_manual_{i}', '').strip()
        row['banco_id'] = int(banco_id_val) if banco_id_val else None
        # Inline edits
        data_edit = request.form.get(f'data_manual_{i}', '').strip()
        if data_edit:
            row['data'] = data_edit
        desc_edit = request.form.get(f'desc_manual_{i}', '').strip()
        if desc_edit:
            row['descricao'] = desc_edit
        valor_edit = request.form.get(f'valor_manual_{i}', '').strip()
        if valor_edit:
            try:
                row['valor'] = float(valor_edit.replace(',', '.'))
            except ValueError:
                pass
        # Override de destinatário (Tom Select)
        _aplicar_destinatario(row, request.form.get(f'destinatario_manual_{i}', '').strip())

    # Aplicar obra e categorias personalizadas nas entradas
    for i, row in enumerate(entradas):
        row['obra_id'] = _obra_segura(request.form.get(f'obra_entrada_{i}', '').strip())
        cat_entrada = request.form.get(f'cat_entrada_{i}')
        if cat_entrada:
            _aplicar_categoria(row, cat_entrada, tipo_esperado='ENTRADA')

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

    # Intervalo de datas do batch para o botão "Ver no Fluxo de Caixa" —
    # garante que a tela abra cobrindo exatamente o que foi importado.
    fc_data_min = fc_data_max = None
    try:
        from models import FluxoCaixa
        from sqlalchemy import func as sa_func
        rng = db.session.query(
            sa_func.min(FluxoCaixa.data_movimento),
            sa_func.max(FluxoCaixa.data_movimento),
        ).filter(
            FluxoCaixa.admin_id == admin_id,
            FluxoCaixa.import_batch_id == batch_id,
        ).one()
        if rng[0] and rng[1]:
            fc_data_min = rng[0].strftime('%Y-%m-%d')
            fc_data_max = rng[1].strftime('%Y-%m-%d')
    except Exception as e:
        logger.warning(f'[FLUXO_CAIXA] Não foi possível calcular intervalo do batch: {e}')

    return render_template(
        'importacao/resultado_fluxo.html',
        resultado=resultado,
        batch_id=batch_id,
        fc_data_min=fc_data_min,
        fc_data_max=fc_data_max,
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
            # Filhos antes do pai (coluna = pai_id) — conta para auditoria
            r_filhos = conn.execute(sa_text("""
                DELETE FROM gestao_custo_filho
                WHERE pai_id IN (
                    SELECT id FROM gestao_custo_pai
                    WHERE import_batch_id=:bid AND admin_id=:aid
                )
            """), {'bid': batch_id, 'aid': admin_id})
            r4 = conn.execute(sa_text(
                "DELETE FROM gestao_custo_pai WHERE import_batch_id=:bid AND admin_id=:aid"
            ), {'bid': batch_id, 'aid': admin_id})

        total = r1.rowcount + r2.rowcount + r3.rowcount + r_filhos.rowcount + r4.rowcount
        flash(f'Importação {batch_id} desfeita com sucesso. {total} registros removidos.', 'success')
    except Exception as e:
        logger.error(f'[ROLLBACK] Erro: {e}', exc_info=True)
        flash(f'Erro ao desfazer importação: {e}', 'danger')

    return redirect(url_for('importacao.historico'))


@importacao_bp.route('/fisico-financeiro', methods=['GET', 'POST'])
@login_required
def importar_fisico_financeiro_view():
    """Importa cronograma físico-financeiro completo a partir de um arquivo JSON
    (cronograma, custos, vínculos, medições de contrato e fluxo de caixa). Ao
    concluir, redireciona para o painel físico-financeiro da obra criada."""
    import json as _json
    from services.importacao_fisico_financeiro import importar_fisico_financeiro

    admin_id = get_admin_id_robusta()

    if request.method == 'POST':
        arquivo = request.files.get('arquivo')
        if not arquivo or arquivo.filename == '':
            flash('Selecione um arquivo JSON.', 'warning')
            return redirect(url_for('importacao.importar_fisico_financeiro_view'))
        try:
            payload = _json.load(arquivo.stream)
            res = importar_fisico_financeiro(payload, admin_id)
        except Exception as e:
            logger.error(f'[FF_IMPORT] Erro ao importar JSON: {e}', exc_info=True)
            flash(f'Falha ao importar: {e}', 'danger')
            return redirect(url_for('importacao.importar_fisico_financeiro_view'))
        flash('Obra importada — painel físico-financeiro pronto.', 'success')
        return redirect(url_for('cronograma.fisico_financeiro', obra_id=res['obra_id']))

    return render_template('importacao/fisico_financeiro_upload.html')


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

            # ContaPagar (reembolsos importados)
            cp_rows = conn.execute(sa_text("""
                SELECT import_batch_id, COUNT(*) as n_cp, SUM(valor_original) as total
                FROM conta_pagar
                WHERE import_batch_id IS NOT NULL
                  AND import_batch_id LIKE 'import\_%' ESCAPE '\\'
                  AND admin_id = :aid
                GROUP BY import_batch_id
            """), {'aid': admin_id}).fetchall()

        custo_map = {r[0]: {'data_import': r[1], 'n': r[2], 'total': float(r[3] or 0)}
                     for r in custo_rows}
        entrada_map = {r[0]: {'data_import': r[1], 'n': r[2], 'total': float(r[3] or 0)}
                       for r in entrada_rows}
        cp_map = {r[0]: {'n': r[1], 'total': float(r[2] or 0)} for r in cp_rows}

        # UNION de todos os batch_ids conhecidos
        all_bids = sorted(
            set(custo_map.keys()) | set(entrada_map.keys()) | set(cp_map.keys()),
            key=lambda b: (custo_map.get(b, {}).get('data_import')
                           or entrada_map.get(b, {}).get('data_import')),
            reverse=True,
        )

        batches = []
        for bid in all_bids:
            c = custo_map.get(bid, {})
            e = entrada_map.get(bid, {})
            cp = cp_map.get(bid, {})
            data_import = c.get('data_import') or e.get('data_import')
            batches.append({
                'batch_id': bid,
                'data_import': data_import,
                'n_custos': c.get('n', 0),
                'total_custos': c.get('total', 0.0),
                'n_entradas': e.get('n', 0),
                'total_entradas': e.get('total', 0.0),
                'n_reembolsos': cp.get('n', 0),
            })

    except Exception as e:
        logger.error(f'[HISTORICO] {e}', exc_info=True)
        batches = []
        flash(f'Erro ao carregar histórico: {e}', 'warning')

    return render_template('importacao/historico.html', batches=batches)
