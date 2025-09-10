"""
PROPOSTAS CONSOLIDATED - SIGE v8.0
Sistema unificado de propostas comerciais consolidando:
- sistema_propostas.py
- propostas_views.py
- propostas_engine.py

Implementa padrões de resiliência: Idempotência, Circuit Breaker, Saga
"""

from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify, send_file, make_response
from flask_login import login_required, current_user
from auth import admin_required, funcionario_required
from datetime import datetime, date, timedelta
from decimal import Decimal
from io import BytesIO
import os
import json
import uuid
import mimetypes
from werkzeug.utils import secure_filename
from sqlalchemy import func, desc, or_, and_, text

# Importar utilitários de resiliência
try:
    from utils.idempotency import idempotent, funcionario_key_generator
    from utils.circuit_breaker import circuit_breaker, pdf_generation_fallback, database_query_fallback
    try:
        from utils.saga import PropostasSaga
    except ImportError:
        PropostasSaga = None
    print("✅ Propostas - Utilitários de resiliência importados")
except ImportError as e:
    print(f"⚠️ Propostas - Erro ao importar utilitários de resiliência: {e}")
    # Fallbacks para manter compatibilidade
    def idempotent(*args, **kwargs):
        def decorator(func):
            return func
        return decorator
    def circuit_breaker(*args, **kwargs):
        def decorator(func):
            return func
        return decorator
    def pdf_generation_fallback(*args, **kwargs):
        flash('Geração de PDF temporariamente indisponível', 'warning')
        return redirect(url_for('propostas.index'))
    
    def database_query_fallback(*args, **kwargs):
        flash('Consulta temporariamente indisponível', 'warning') 
        return redirect(url_for('main.dashboard'))

# Importar modelos necessários
from app import db
from models import (
    PropostaComercialSIGE, PropostaItem, PropostaTemplate, 
    ConfiguracaoEmpresa, Usuario, TipoUsuario, Obra, Servico
)

# Blueprint unificado
propostas_bp = Blueprint('propostas', __name__, url_prefix='/propostas')

# Configurações
UPLOAD_FOLDER = 'static/uploads/propostas'
ALLOWED_EXTENSIONS = {'pdf', 'dwg', 'dxf', 'png', 'jpg', 'jpeg', 'gif', 'doc', 'docx', 'xlsx', 'xls'}

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

def get_admin_id():
    """Detecção unificada de admin_id para dev/produção (padrão consolidado)"""
    if hasattr(current_user, 'tipo_usuario') and current_user.is_authenticated:
        if current_user.tipo_usuario == TipoUsuario.ADMIN:
            return current_user.id
        elif hasattr(current_user, 'admin_id') and current_user.admin_id:
            return current_user.admin_id
    
    # Fallback para desenvolvimento
    return 10

def safe_db_operation(operation, default_value=None):
    """Executa operação no banco com tratamento seguro de transação"""
    try:
        return operation()
    except Exception as e:
        print(f"ERRO PROPOSTAS DB: {str(e)}")
        try:
            db.session.rollback()
        except:
            pass
        return default_value

def propostas_key_generator(request, *args, **kwargs):
    """Gerador de chave idempotente para operações de propostas"""
    admin_id = get_admin_id()
    cliente_id = request.form.get('cliente_id', 'sem_cliente')
    timestamp = int(datetime.now().timestamp() // 3600)  # Janela de 1 hora
    return f"proposta_{admin_id}_{cliente_id}_{timestamp}"

# ===== ROTAS PRINCIPAIS CONSOLIDADAS =====

@propostas_bp.route('/')
@login_required
@admin_required
@circuit_breaker(
    name="propostas_list_query",
    failure_threshold=3,
    recovery_timeout=60,
    expected_exception=(Exception,),
    fallback=lambda *args, **kwargs: redirect(url_for('main.dashboard'))
)
def index():
    """Lista unificada de propostas - Dashboard principal"""
    try:
        admin_id = get_admin_id()
        page = request.args.get('page', 1, type=int)
        status_filter = request.args.get('status', '')
        cliente_filter = request.args.get('cliente', '')
        
        print(f"DEBUG PROPOSTAS: admin_id={admin_id}, filters=status:{status_filter}, cliente:{cliente_filter}")
        
        # Query base com filtro por admin
        query = PropostaComercialSIGE.query.filter_by(admin_id=admin_id)
        
        # Aplicar filtros
        if status_filter:
            query = query.filter(PropostaComercialSIGE.status == status_filter)
        if cliente_filter:
            query = query.filter(PropostaComercialSIGE.cliente_nome.ilike(f'%{cliente_filter}%'))
        
        # Paginação
        propostas = query.order_by(PropostaComercialSIGE.criado_em.desc()).paginate(
            page=page, per_page=20, error_out=False
        )
        
        # Estatísticas para dashboard
        stats = safe_db_operation(lambda: {
            'total': PropostaComercialSIGE.query.filter_by(admin_id=admin_id).count(),
            'pendentes': PropostaComercialSIGE.query.filter_by(admin_id=admin_id, status='pendente').count(),
            'aprovadas': PropostaComercialSIGE.query.filter_by(admin_id=admin_id, status='aprovada').count(),
            'valor_total': db.session.query(func.sum(PropostaComercialSIGE.valor_total)).filter_by(admin_id=admin_id).scalar() or 0
        }, {})
        
        print(f"DEBUG PROPOSTAS: {stats.get('total', 0)} propostas encontradas")
        
        return render_template('propostas/lista_propostas.html', 
                             propostas=propostas, 
                             stats=stats,
                             status_filter=status_filter, 
                             cliente_filter=cliente_filter)
        
    except Exception as e:
        print(f"ERRO PROPOSTAS INDEX: {str(e)}")
        flash(f'Erro ao carregar propostas: {str(e)}', 'error')
        return redirect(url_for('main.dashboard'))

@propostas_bp.route('/dashboard')
@login_required
@admin_required
def dashboard():
    """Dashboard avançado de propostas - Alias para compatibilidade"""
    return redirect(url_for('propostas.index'))

@propostas_bp.route('/nova')
@login_required
@admin_required
def nova():
    """Formulário para criar nova proposta"""
    try:
        admin_id = get_admin_id()
        
        # Buscar templates disponíveis
        templates = safe_db_operation(
            lambda: PropostaTemplate.query.filter_by(admin_id=admin_id, ativo=True).all(),
            []
        )
        
        # Buscar configuração da empresa
        config = safe_db_operation(
            lambda: ConfiguracaoEmpresa.query.filter_by(admin_id=admin_id).first(),
            None
        )
        
        print(f"DEBUG NOVA PROPOSTA: {len(templates)} templates disponíveis")
        
        return render_template('propostas/nova_proposta.html', 
                             templates=templates,
                             config=config)
        
    except Exception as e:
        print(f"ERRO NOVA PROPOSTA: {str(e)}")
        flash(f'Erro ao carregar formulário: {str(e)}', 'error')
        return redirect(url_for('propostas.index'))

@propostas_bp.route('/criar', methods=['POST'])
@login_required
@admin_required
@idempotent(
    operation_type='proposta_create',
    ttl_seconds=3600,  # 1 hora
    key_generator=propostas_key_generator
)
def criar():
    """Criar nova proposta com proteção idempotente"""
    try:
        admin_id = get_admin_id()
        
        # Dados do formulário
        cliente_nome = request.form.get('cliente_nome', '').strip()
        cliente_email = request.form.get('cliente_email', '').strip()
        titulo = request.form.get('titulo', '').strip()
        descricao = request.form.get('descricao', '').strip()
        valor_total = request.form.get('valor_total', '0').replace(',', '.')
        
        # Validações básicas
        if not cliente_nome:
            flash('Nome do cliente é obrigatório', 'error')
            return redirect(url_for('propostas.nova'))
        
        if not titulo:
            flash('Título da proposta é obrigatório', 'error')
            return redirect(url_for('propostas.nova'))
        
        try:
            valor_total = float(valor_total)
        except ValueError:
            flash('Valor total deve ser um número válido', 'error')
            return redirect(url_for('propostas.nova'))
        
        # Gerar número da proposta
        ano_atual = datetime.now().year
        last_numero = safe_db_operation(
            lambda: PropostaComercialSIGE.query.filter_by(admin_id=admin_id).count(),
            0
        )
        numero_proposta = f"PROP-{ano_atual}-{(last_numero + 1):04d}"
        
        # Criar proposta
        proposta = PropostaComercialSIGE(
            numero_proposta=numero_proposta,
            assunto=titulo,
            objeto=descricao,
            cliente_nome=cliente_nome,
            cliente_email=cliente_email,
            valor_total=valor_total,
            status='rascunho',
            admin_id=admin_id,
            criado_por=current_user.id,
            criado_em=datetime.now()
        )
        
        db.session.add(proposta)
        db.session.commit()
        
        print(f"DEBUG PROPOSTA CRIADA: {numero_proposta} - R$ {valor_total}")
        flash(f'Proposta {numero_proposta} criada com sucesso!', 'success')
        
        return redirect(url_for('propostas.visualizar', id=proposta.id))
        
    except Exception as e:
        db.session.rollback()
        print(f"ERRO CRIAR PROPOSTA: {str(e)}")
        flash(f'Erro ao criar proposta: {str(e)}', 'error')
        return redirect(url_for('propostas.nova'))

@propostas_bp.route('/<int:id>')
@login_required
@admin_required
def visualizar(id):
    """Visualizar proposta específica"""
    try:
        admin_id = get_admin_id()
        
        proposta = PropostaComercialSIGE.query.filter_by(
            id=id, admin_id=admin_id
        ).first_or_404()
        
        # Buscar itens da proposta
        itens = safe_db_operation(
            lambda: PropostaItem.query.filter_by(proposta_id=id).all(),
            []
        )
        
        # Buscar arquivos anexos
        arquivos = safe_db_operation(
            lambda: PropostaArquivo.query.filter_by(proposta_id=id).all(),
            []
        )
        
        print(f"DEBUG VISUALIZAR: Proposta {proposta.numero_proposta} - {len(itens)} itens")
        
        return render_template('propostas/visualizar_proposta.html',
                             proposta=proposta,
                             itens=itens,
                             arquivos=arquivos)
        
    except Exception as e:
        print(f"ERRO VISUALIZAR PROPOSTA: {str(e)}")
        flash(f'Erro ao carregar proposta: {str(e)}', 'error')
        return redirect(url_for('propostas.index'))

@propostas_bp.route('/<int:id>/pdf')
@login_required
@admin_required
@circuit_breaker(
    name="proposta_pdf_generation",
    failure_threshold=3,
    recovery_timeout=120,
    expected_exception=(Exception,),
    fallback=lambda *args, **kwargs: redirect(url_for('propostas.visualizar', id=args[0] if args else 1))
)
def gerar_pdf(id):
    """Gerar PDF da proposta com circuit breaker"""
    try:
        admin_id = get_admin_id()
        
        proposta = PropostaComercialSIGE.query.filter_by(
            id=id, admin_id=admin_id
        ).first_or_404()
        
        # Buscar configuração da empresa
        config = safe_db_operation(
            lambda: ConfiguracaoEmpresa.query.filter_by(admin_id=admin_id).first(),
            None
        )
        
        # Gerar PDF (implementação simplificada por ora)
        from reportlab.lib.pagesizes import A4
        from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer
        from reportlab.lib.styles import getSampleStyleSheet
        
        buffer = BytesIO()
        doc = SimpleDocTemplate(buffer, pagesize=A4)
        styles = getSampleStyleSheet()
        story = []
        
        # Cabeçalho
        if config and config.nome_empresa:
            story.append(Paragraph(config.nome_empresa, styles['Title']))
            story.append(Spacer(1, 12))
        
        # Dados da proposta
        story.append(Paragraph(f"Proposta: {proposta.numero_proposta}", styles['Heading1']))
        story.append(Paragraph(f"Cliente: {proposta.cliente_nome}", styles['Normal']))
        story.append(Paragraph(f"Título: {proposta.titulo}", styles['Normal']))
        story.append(Spacer(1, 12))
        
        if proposta.descricao:
            story.append(Paragraph("Descrição:", styles['Heading2']))
            story.append(Paragraph(proposta.descricao, styles['Normal']))
            story.append(Spacer(1, 12))
        
        story.append(Paragraph(f"Valor Total: R$ {proposta.valor_total:,.2f}", styles['Heading2']))
        
        doc.build(story)
        buffer.seek(0)
        
        print(f"DEBUG PDF: Proposta {proposta.numero_proposta} gerada com sucesso")
        
        response = make_response(buffer.getvalue())
        response.headers['Content-Type'] = 'application/pdf'
        response.headers['Content-Disposition'] = f'attachment; filename=proposta_{proposta.numero_proposta}.pdf'
        
        return response
        
    except Exception as e:
        print(f"ERRO GERAR PDF: {str(e)}")
        flash(f'Erro ao gerar PDF: {str(e)}', 'error')
        return redirect(url_for('propostas.visualizar', id=id))

# ===== ALIASES DE COMPATIBILIDADE =====

@propostas_bp.route('/listar')
@login_required
@admin_required
def listar():
    """Alias para compatibilidade com sistema antigo"""
    return redirect(url_for('propostas.index'))

@propostas_bp.route('/nova-proposta')
@login_required
@admin_required
def nova_proposta():
    """Alias para compatibilidade com sistema antigo"""
    return redirect(url_for('propostas.nova'))

@propostas_bp.route('/criar-proposta', methods=['GET', 'POST'])
@login_required
@admin_required
def criar_proposta():
    """Endpoint criar_proposta para compatibilidade"""
    if request.method == 'GET':
        return redirect(url_for('propostas.nova'))
    else:
        return redirect(url_for('propostas.criar'), code=307)  # Preservar método POST

# ===== ROTAS API =====

@propostas_bp.route('/api/template/<int:template_id>')
@login_required
@admin_required
def get_template_data(template_id):
    """API para obter dados de template"""
    try:
        admin_id = get_admin_id()
        
        template = PropostaTemplate.query.filter_by(
            id=template_id, admin_id=admin_id
        ).first_or_404()
        
        return jsonify({
            'success': True,
            'template': {
                'id': template.id,
                'nome': template.nome,
                'categoria': template.categoria,
                'itens_padrao': template.itens_padrao,
                'valor_base': template.valor_base
            }
        })
        
    except Exception as e:
        print(f"ERRO API TEMPLATE: {str(e)}")
        return jsonify({'success': False, 'error': str(e)}), 400

print("✅ Propostas Consolidated Blueprint carregado com padrões de resiliência")