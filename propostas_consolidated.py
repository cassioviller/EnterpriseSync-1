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
import base64
from werkzeug.utils import secure_filename
from sqlalchemy import func, desc, or_, and_, text
from PIL import Image

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
    Proposta, PropostaItem, PropostaTemplate, PropostaHistorico, PropostaArquivo,
    ConfiguracaoEmpresa, Usuario, TipoUsuario, Obra, Servico, Cliente
)

# Blueprint unificado
propostas_bp = Blueprint('propostas', __name__, url_prefix='/propostas')

# Configurações
UPLOAD_FOLDER = 'static/uploads/propostas'
ALLOWED_EXTENSIONS = {'pdf', 'dwg', 'dxf', 'png', 'jpg', 'jpeg', 'gif', 'doc', 'docx', 'xlsx', 'xls'}

# ===== HELPER FUNCTIONS =====

def organizar_itens_por_template(itens):
    """
    Organiza itens por template e categoria com subtotais
    
    Returns:
        List[Dict]: Lista de templates organizados com categorias e subtotais
        [
            {
                'template_nome': 'Nome do Template',
                'categorias': [('Categoria 1', [item1, item2]), ('Categoria 2', [item3])],
                'subtotal': Decimal('5000.00')
            },
            ...
        ]
    """
    if not itens:
        return []
    
    # Agrupar por template primeiro
    templates = {}
    for item in itens:
        template_nome = getattr(item, 'template_origem_nome', None) or 'Serviços Gerais'
        if template_nome not in templates:
            templates[template_nome] = []
        templates[template_nome].append(item)
    
    # Para cada template, organizar por categoria
    templates_organizados = []
    for template_nome, itens_template in templates.items():
        categorias = {}
        subtotal_template = Decimal('0.00')
        
        for item in itens_template:
            categoria = getattr(item, 'categoria_titulo', 'Serviços')
            if categoria not in categorias:
                categorias[categoria] = []
            categorias[categoria].append(item)
            
            # Calcular subtotal do item
            item_total = Decimal(str(item.quantidade)) * Decimal(str(item.preco_unitario))
            subtotal_template += item_total
        
        # Converter para lista de tuplas (categoria, itens)
        categorias_lista = [(cat, itens_cat) for cat, itens_cat in categorias.items()]
        
        templates_organizados.append({
            'template_nome': template_nome,
            'categorias': categorias_lista,
            'subtotal': subtotal_template
        })
    
    return templates_organizados

def parse_currency(value_str):
    """
    Converte string de moeda brasileira para float
    Aceita formatos: "2.500,50", "2500,50", "2500.50", "2500", "R$ 1.234,56"
    
    Examples:
        parse_currency("2.500,00") → 2500.00
        parse_currency("2500,50") → 2500.50
        parse_currency("2500.50") → 2500.50
        parse_currency("R$ 1.234,56") → 1234.56
    """
    if not value_str:
        return 0.0
    
    # Limpar string
    value_str = str(value_str).strip().replace(' ', '').replace('R$', '')
    
    if not value_str:
        return 0.0
    
    # Detectar formato: se tem vírgula E ponto, é formato BR (1.234,56)
    if ',' in value_str and '.' in value_str:
        # Formato BR: remover pontos (separador de milhares), trocar vírgula por ponto
        value_str = value_str.replace('.', '').replace(',', '.')
    elif ',' in value_str:
        # Só tem vírgula: trocar por ponto (2500,50 → 2500.50)
        value_str = value_str.replace(',', '.')
    # Se só tem ponto, já está no formato correto (2500.50)
    
    try:
        return float(value_str)
    except ValueError:
        print(f"ERRO parse_currency: não consegui converter '{value_str}'")
        return 0.0

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

def propostas_key_generator(*args, **kwargs):
    """Gerador de chave idempotente para operações de propostas"""
    from flask import request as flask_request
    admin_id = get_admin_id()
    cliente_id = flask_request.form.get('cliente_id', 'sem_cliente')
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
        query = Proposta.query.filter_by(admin_id=admin_id)
        
        # Aplicar filtros
        if status_filter:
            query = query.filter(Proposta.status == status_filter)
        if cliente_filter:
            query = query.filter(Proposta.cliente_nome.ilike(f'%{cliente_filter}%'))
        
        # Paginação
        propostas = query.order_by(Proposta.criado_em.desc()).paginate(
            page=page, per_page=20, error_out=False
        )
        
        # Estatísticas para dashboard
        stats = safe_db_operation(lambda: {
            'total': Proposta.query.filter_by(admin_id=admin_id).count(),
            'pendentes': Proposta.query.filter_by(admin_id=admin_id, status='pendente').count(),
            'aprovadas': Proposta.query.filter_by(admin_id=admin_id, status='aprovada').count(),
            'valor_total': db.session.query(func.sum(Proposta.valor_total)).filter_by(admin_id=admin_id).scalar() or 0
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
def criar():
    """Criar nova proposta COM processamento de itens"""
    try:
        admin_id = get_admin_id()
        
        # Dados básicos do formulário
        cliente_nome = request.form.get('cliente_nome', '').strip()
        cliente_email = request.form.get('cliente_email', '').strip()
        cliente_telefone = request.form.get('cliente_telefone', '').strip()
        cliente_documento = request.form.get('cliente_cpf_cnpj', request.form.get('cliente_documento', '')).strip()
        cliente_endereco = request.form.get('cliente_endereco', '').strip()
        
        # Aceitar 'assunto' ou 'titulo' (compatibilidade)
        titulo = request.form.get('assunto', request.form.get('titulo', '')).strip()
        descricao = request.form.get('objeto', request.form.get('descricao', '')).strip()
        
        # Validações básicas
        if not cliente_nome:
            flash('Nome do cliente é obrigatório', 'error')
            return redirect(url_for('propostas.nova'))
        
        if not titulo:
            flash('Assunto/Título da proposta é obrigatório', 'error')
            return redirect(url_for('propostas.nova'))
        
        # Gerar número da proposta
        numero_proposta_input = request.form.get('numero_proposta', '').strip()
        if numero_proposta_input:
            numero_proposta = numero_proposta_input
        else:
            ano_atual = datetime.now().year
            last_numero = safe_db_operation(
                lambda: Proposta.query.filter_by(admin_id=admin_id).count(),
                0
            )
            numero_proposta = f"PROP-{ano_atual}-{(last_numero + 1):04d}"
        
        # ===== PROCESSAR ITENS DA PROPOSTA (mesma lógica do /editar) =====
        item_descricoes = request.form.getlist('item_descricao')
        item_quantidades = request.form.getlist('item_quantidade')
        item_unidades = request.form.getlist('item_unidade')
        item_precos = request.form.getlist('item_preco')
        
        # Calcular valor total baseado nos itens
        valor_total_calculado = 0
        itens_validos = []
        
        for i in range(len(item_descricoes)):
            descricao_item = item_descricoes[i].strip()
            if not descricao_item:
                continue
            
            try:
                # Usar parser robusto de moeda BR
                quantidade = parse_currency(item_quantidades[i])
                preco_unitario = parse_currency(item_precos[i])
                unidade = item_unidades[i]
                
                itens_validos.append({
                    'descricao': descricao_item,
                    'quantidade': quantidade,
                    'unidade': unidade,
                    'preco_unitario': preco_unitario
                })
                
                valor_total_calculado += quantidade * preco_unitario
            except (ValueError, IndexError) as e:
                print(f"ERRO ao processar item {i}: {e}")
                continue
        
        print(f"DEBUG CRIAR: {len(itens_validos)} itens válidos, total: R$ {valor_total_calculado:,.2f}")
        
        # Criar proposta (usando apenas campos que existem no modelo)
        proposta = Proposta()
        proposta.numero = numero_proposta
        proposta.titulo = titulo
        proposta.descricao = descricao
        proposta.cliente_nome = cliente_nome
        proposta.cliente_email = cliente_email
        proposta.cliente_telefone = cliente_telefone
        proposta.cliente_endereco = cliente_endereco
        proposta.valor_total = valor_total_calculado
        proposta.status = 'rascunho'
        proposta.admin_id = admin_id
        proposta.prazo_entrega_dias = int(request.form.get('prazo_entrega_dias', 90))
        proposta.percentual_nota_fiscal = float(request.form.get('percentual_nota_fiscal', 13.5))
        
        # Condições e observações
        if request.form.get('condicoes_pagamento'):
            proposta.condicoes_pagamento = request.form.get('condicoes_pagamento')
        if request.form.get('garantias'):
            proposta.garantias = request.form.get('garantias')
        if request.form.get('consideracoes_gerais'):
            proposta.consideracoes_gerais = request.form.get('consideracoes_gerais')
        
        # Processar itens inclusos/exclusos
        itens_inclusos_raw = request.form.get('itens_inclusos', '')
        if itens_inclusos_raw:
            proposta.itens_inclusos = itens_inclusos_raw.replace(';', '\n').strip()
        
        itens_exclusos_raw = request.form.get('itens_exclusos', '')
        if itens_exclusos_raw:
            proposta.itens_exclusos = itens_exclusos_raw.replace(';', '\n').strip()
        
        db.session.add(proposta)
        db.session.flush()  # Obter ID da proposta antes de criar itens
        
        # Ler dados adicionais dos templates
        templates_nomes = request.form.getlist('item_template_nome')
        templates_ids = request.form.getlist('item_template_id')
        categorias = request.form.getlist('item_categoria')
        
        # Criar itens da proposta
        for idx, item_data in enumerate(itens_validos):
            # Pegar dados do template se disponíveis
            template_nome = templates_nomes[idx] if idx < len(templates_nomes) and templates_nomes[idx] else None
            template_id = templates_ids[idx] if idx < len(templates_ids) and templates_ids[idx] else None
            categoria = categorias[idx] if idx < len(categorias) and categorias[idx] else None
            
            # Converter template_id para int se não vazio
            template_id_int = None
            if template_id and template_id.strip():
                try:
                    template_id_int = int(template_id)
                except ValueError:
                    pass
            
            item = PropostaItem(
                admin_id=admin_id,
                proposta_id=proposta.id,
                item_numero=idx + 1,
                descricao=item_data['descricao'],
                quantidade=item_data['quantidade'],
                unidade=item_data['unidade'],
                preco_unitario=item_data['preco_unitario'],
                ordem=idx + 1,
                template_origem_nome=template_nome,
                template_origem_id=template_id_int,
                categoria_titulo=categoria
            )
            db.session.add(item)
            print(f"  ✓ Item {idx+1} criado: {item_data['descricao'][:30]}...")
        
        # Registrar no histórico
        historico = PropostaHistorico(
            proposta_id=proposta.id,
            usuario_id=current_user.id,
            acao='criada',
            observacao=f'Proposta criada por {current_user.username} com {len(itens_validos)} itens',
            admin_id=admin_id
        )
        db.session.add(historico)
        
        # Commit transacional único
        db.session.commit()
        
        print(f"DEBUG PROPOSTA CRIADA: {numero_proposta} com {len(itens_validos)} itens - R$ {valor_total_calculado:,.2f}")
        flash(f'Proposta {numero_proposta} criada com sucesso! {len(itens_validos)} itens salvos.', 'success')
        
        return redirect(url_for('propostas.visualizar', id=proposta.id))
        
    except Exception as e:
        db.session.rollback()
        print(f"ERRO CRIAR PROPOSTA: {str(e)}")
        import traceback
        traceback.print_exc()
        flash(f'Erro ao criar proposta: {str(e)}', 'error')
        return redirect(url_for('propostas.nova'))

@propostas_bp.route('/<int:id>')
@login_required
@admin_required
def visualizar(id):
    """Visualizar proposta específica"""
    try:
        admin_id = get_admin_id()
        
        proposta = Proposta.query.filter_by(
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
        
        # Organizar itens por template e categoria (igual ao portal do cliente)
        if hasattr(proposta, 'itens') and proposta.itens:
            templates_organizados = organizar_itens_por_template(proposta.itens)
            proposta.templates_organizados = templates_organizados
        else:
            proposta.templates_organizados = []
        
        # Calcular total geral: priorizar valor_total da proposta (manual), senão calcular dos itens
        if proposta.valor_total:
            total_geral = proposta.valor_total
        elif proposta.itens:
            total_geral = sum(item.quantidade * item.preco_unitario for item in proposta.itens)
        else:
            total_geral = 0
        
        print(f"DEBUG VISUALIZAR: Proposta {proposta.numero} - {len(itens)} itens")
        
        return render_template('propostas/detalhes_proposta.html',
                             proposta=proposta,
                             itens=itens,
                             arquivos=arquivos,
                             total_geral=total_geral,
                             date=date)
        
    except Exception as e:
        print(f"ERRO VISUALIZAR PROPOSTA: {str(e)}")
        flash(f'Erro ao carregar proposta: {str(e)}', 'error')
        return redirect(url_for('propostas.index'))

@propostas_bp.route('/<int:id>/status', methods=['POST'])
@login_required
@admin_required
def alterar_status(id):
    """Altera o status da proposta"""
    try:
        admin_id = get_admin_id()
        proposta = Proposta.query.filter_by(id=id, admin_id=admin_id).first_or_404()
        
        data = request.get_json()
        novo_status = data.get('status', '').upper()
        motivo = data.get('motivo', '')
        
        status_validos = ['RASCUNHO', 'ENVIADA', 'EM_ANALISE', 'APROVADA', 'REJEITADA', 'EXPIRADA']
        if novo_status not in status_validos:
            return jsonify({
                'success': False,
                'message': f'Status inválido. Use: {", ".join(status_validos)}'
            }), 400
        
        status_anterior = proposta.status
        proposta.status = novo_status
        
        if novo_status == 'ENVIADA':
            proposta.data_envio = datetime.utcnow()
        elif novo_status == 'APROVADA':
            proposta.data_aprovacao = datetime.utcnow()
        elif novo_status == 'REJEITADA':
            proposta.data_resposta_cliente = datetime.utcnow()
        
        historico = PropostaHistorico(
            proposta_id=proposta.id,
            usuario_id=current_user.id,
            acao=f'status_alterado_{status_anterior.lower()}_para_{novo_status.lower()}',
            observacao=motivo if motivo else f'Status alterado de {status_anterior} para {novo_status}',
            data_hora=datetime.utcnow()
        )
        
        db.session.add(historico)
        db.session.commit()
        
        mensagens_status = {
            'ENVIADA': 'Proposta enviada com sucesso! O cliente pode visualizar e responder.',
            'APROVADA': 'Proposta aprovada!',
            'REJEITADA': 'Proposta rejeitada.',
            'EM_ANALISE': 'Proposta marcada como "Em Análise".',
            'RASCUNHO': 'Proposta voltou para rascunho.',
            'EXPIRADA': 'Proposta marcada como expirada.'
        }
        
        return jsonify({
            'success': True,
            'message': mensagens_status.get(novo_status, 'Status alterado com sucesso!'),
            'novo_status': novo_status
        })
        
    except Exception as e:
        db.session.rollback()
        print(f"ERRO ALTERAR STATUS: {str(e)}")
        return jsonify({
            'success': False,
            'message': f'Erro ao alterar status: {str(e)}'
        }), 500

@propostas_bp.route('/<int:id>/pdf')
@login_required
@admin_required
def gerar_pdf(id):
    """Gera PDF completo da proposta com template HTML paginado"""
    try:
        admin_id = get_admin_id()
        
        proposta = Proposta.query.filter_by(
            id=id, admin_id=admin_id
        ).first_or_404()
        
        print(f"DEBUG PDF: Proposta {proposta.numero}")
        print(f"DEBUG PDF: Cliente: {proposta.cliente_nome}")
        print(f"DEBUG PDF: Valor total: {proposta.valor_total}")
        print(f"DEBUG PDF: Número de itens: {len(proposta.itens) if proposta.itens else 0}")
        
        config_empresa = safe_db_operation(
            lambda: ConfiguracaoEmpresa.query.filter_by(admin_id=admin_id).first(),
            None
        )
        
        if hasattr(proposta, 'itens_inclusos') and proposta.itens_inclusos:
            if isinstance(proposta.itens_inclusos, str):
                try:
                    itens_list = json.loads(proposta.itens_inclusos)
                    if isinstance(itens_list, list):
                        proposta.itens_inclusos = '\n'.join(itens_list)
                except json.JSONDecodeError:
                    pass
            elif isinstance(proposta.itens_inclusos, list):
                proposta.itens_inclusos = '\n'.join(proposta.itens_inclusos)
        
        if hasattr(proposta, 'itens_exclusos') and proposta.itens_exclusos:
            if isinstance(proposta.itens_exclusos, str):
                try:
                    itens_list = json.loads(proposta.itens_exclusos)
                    if isinstance(itens_list, list):
                        proposta.itens_exclusos = '\n'.join(itens_list)
                except json.JSONDecodeError:
                    pass
            elif isinstance(proposta.itens_exclusos, list):
                proposta.itens_exclusos = '\n'.join(proposta.itens_exclusos)
        
        if config_empresa:
            print(f"DEBUG PDF: Config empresa: {config_empresa.nome_empresa}")
            print(f"DEBUG PDF: Header PDF presente: {'SIM' if config_empresa.header_pdf_base64 else 'NÃO'}")
            if config_empresa.header_pdf_base64:
                print(f"DEBUG PDF: Tamanho header: {len(config_empresa.header_pdf_base64)} chars")
        else:
            print("DEBUG PDF: Nenhuma configuração encontrada")
        
        formato = request.args.get('formato', 'estruturas_vale')
        
        if formato == 'estruturas_vale':
            template_name = 'propostas/pdf_estruturas_vale_paginado.html'
        else:
            template_name = 'propostas/pdf.html'
        
        print(f"DEBUG PDF: Usando template: {template_name}")
        
        template_proposta = None
        if hasattr(proposta, 'template_id') and proposta.template_id:
            template_proposta = PropostaTemplate.query.get(proposta.template_id)
        
        # Organizar itens por template e categoria
        if hasattr(proposta, 'itens') and proposta.itens:
            templates_organizados = organizar_itens_por_template(proposta.itens)
            proposta.templates_organizados = templates_organizados
            print(f"DEBUG PDF: {len(proposta.itens)} itens organizados em {len(templates_organizados)} templates")
            for template_info in templates_organizados:
                print(f"  - Template: {template_info['template_nome']}, Subtotal: R$ {template_info['subtotal']}")
        else:
            proposta.templates_organizados = []
            print("DEBUG PDF: Nenhum item encontrado na proposta")
        
        # Calcular total geral: priorizar valor_total da proposta (manual), senão calcular dos itens
        if proposta.valor_total:
            total_geral = proposta.valor_total
        elif proposta.itens:
            total_geral = sum(item.quantidade * item.preco_unitario for item in proposta.itens)
        else:
            total_geral = 0
        
        print(f"DEBUG PDF: Total calculado dos itens: {total_geral}")
        print(f"DEBUG PDF: Valor total da proposta: {proposta.valor_total}")
        print(f"DEBUG PDF: Total geral final: {total_geral}")
        
        html_content = render_template(template_name, 
                                     proposta=proposta, 
                                     template=template_proposta,
                                     config=config_empresa,
                                     config_empresa=config_empresa,
                                     total_geral=total_geral)
        
        print("DEBUG PDF: Template renderizado com sucesso")
        return html_content
        
    except Exception as e:
        print(f"ERRO PDF: {str(e)}")
        import traceback
        traceback.print_exc()
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
                'descricao': template.descricao,
                'itens_padrao': template.itens_padrao or [],
                'prazo_entrega_dias': template.prazo_entrega_dias,
                'validade_dias': template.validade_dias,
                'percentual_nota_fiscal': float(template.percentual_nota_fiscal) if template.percentual_nota_fiscal else 13.5
            }
        })
        
    except Exception as e:
        print(f"ERRO API TEMPLATE: {str(e)}")
        return jsonify({'success': False, 'error': str(e)}), 400

# ===== ROTAS DE EDIÇÃO E GESTÃO =====

@propostas_bp.route('/editar/<int:id>')
@login_required
@admin_required
def editar(id):
    """Exibe formulário para editar proposta"""
    try:
        admin_id = get_admin_id()
        proposta = Proposta.query.filter_by(id=id, admin_id=admin_id).first_or_404()
        
        print(f"DEBUG EDITAR: Proposta {proposta.numero} carregada para edição")
        
        return render_template('propostas/editar.html', proposta=proposta)
        
    except Exception as e:
        print(f"ERRO EDITAR PROPOSTA: {str(e)}")
        flash(f'Erro ao carregar proposta para edição: {str(e)}', 'error')
        return redirect(url_for('propostas.index'))

@propostas_bp.route('/editar/<int:id>', methods=['POST'])
@login_required
@admin_required
def atualizar(id):
    """Atualiza proposta existente COM processamento de itens"""
    try:
        admin_id = get_admin_id()
        proposta = Proposta.query.filter_by(id=id, admin_id=admin_id).first_or_404()
        
        # Atualizar campos básicos da proposta
        proposta.numero = request.form.get('numero')
        proposta.titulo = request.form.get('titulo')
        proposta.descricao = request.form.get('descricao')
        proposta.cliente_nome = request.form.get('cliente_nome')
        proposta.cliente_email = request.form.get('cliente_email')
        proposta.cliente_telefone = request.form.get('cliente_telefone')
        proposta.cliente_endereco = request.form.get('cliente_endereco')
        proposta.prazo_entrega_dias = int(request.form.get('prazo_entrega_dias', 90))
        proposta.percentual_nota_fiscal = float(request.form.get('percentual_nota_fiscal', 13.5))
        proposta.condicoes_pagamento = request.form.get('condicoes_pagamento')
        proposta.garantias = request.form.get('garantias')
        
        # Processar itens inclusos/exclusos
        itens_inclusos_raw = request.form.get('itens_inclusos', '')
        if itens_inclusos_raw:
            proposta.itens_inclusos = itens_inclusos_raw.replace(';', '\n').strip()
        
        itens_exclusos_raw = request.form.get('itens_exclusos', '')
        if itens_exclusos_raw:
            proposta.itens_exclusos = itens_exclusos_raw.replace(';', '\n').strip()
        
        proposta.consideracoes_gerais = request.form.get('consideracoes_gerais', proposta.consideracoes_gerais)
        
        # ===== PROCESSAR ITENS DA PROPOSTA =====
        # Coletar dados dos itens do formulário
        item_ids = request.form.getlist('item_id')
        item_descricoes = request.form.getlist('item_descricao')
        item_quantidades = request.form.getlist('item_quantidade')
        item_unidades = request.form.getlist('item_unidade')
        item_precos = request.form.getlist('item_preco')
        
        print(f"DEBUG ATUALIZAR: Proposta {proposta.numero}")
        print(f"DEBUG ITENS: {len(item_descricoes)} itens no formulário")
        
        # Deletar itens antigos que foram removidos
        ids_formulario = [int(item_id) for item_id in item_ids if item_id]
        PropostaItem.query.filter(
            PropostaItem.proposta_id == proposta.id,
            ~PropostaItem.id.in_(ids_formulario) if ids_formulario else True
        ).delete(synchronize_session=False)
        
        # Atualizar/criar itens
        valor_total_calculado = 0
        for i in range(len(item_descricoes)):
            descricao = item_descricoes[i].strip()
            if not descricao:
                continue
            
            # Usar parser robusto de moeda BR
            quantidade = parse_currency(item_quantidades[i])
            unidade = item_unidades[i]
            preco_unitario = parse_currency(item_precos[i])
            
            # Pegar dados do template
            templates_nomes = request.form.getlist('item_template_nome')
            templates_ids = request.form.getlist('item_template_id')
            categorias = request.form.getlist('item_categoria')
            
            template_nome = templates_nomes[i] if i < len(templates_nomes) and templates_nomes[i] else None
            template_id = templates_ids[i] if i < len(templates_ids) and templates_ids[i] else None
            categoria = categorias[i] if i < len(categorias) and categorias[i] else None
            
            # Converter template_id para int se não vazio
            template_id_int = None
            if template_id and template_id.strip():
                try:
                    template_id_int = int(template_id)
                except ValueError:
                    pass
            
            # Verificar se é item existente ou novo
            if i < len(item_ids) and item_ids[i]:
                # Atualizar item existente
                item = PropostaItem.query.get(int(item_ids[i]))
                if item and item.proposta_id == proposta.id:
                    item.descricao = descricao
                    item.quantidade = quantidade
                    item.unidade = unidade
                    item.preco_unitario = preco_unitario
                    item.item_numero = i + 1
                    item.template_origem_nome = template_nome
                    item.template_origem_id = template_id_int
                    item.categoria_titulo = categoria
                    print(f"  ✓ Item {i+1} atualizado: {descricao[:30]}...")
            else:
                # Criar novo item
                novo_item = PropostaItem(
                    admin_id=admin_id,
                    proposta_id=proposta.id,
                    item_numero=i + 1,
                    descricao=descricao,
                    quantidade=quantidade,
                    unidade=unidade,
                    preco_unitario=preco_unitario,
                    ordem=i + 1,
                    template_origem_nome=template_nome,
                    template_origem_id=template_id_int,
                    categoria_titulo=categoria
                )
                db.session.add(novo_item)
                print(f"  ✓ Item {i+1} criado: {descricao[:30]}...")
            
            valor_total_calculado += quantidade * preco_unitario
        
        # Atualizar valor_total da proposta
        proposta.valor_total = valor_total_calculado
        print(f"DEBUG: Valor total calculado: R$ {valor_total_calculado:,.2f}")
        
        # Registrar no histórico
        historico = PropostaHistorico(
            proposta_id=proposta.id,
            usuario_id=current_user.id,
            acao='editada',
            observacao=f'Proposta editada por {current_user.username} - {len(item_descricoes)} itens processados',
            admin_id=admin_id
        )
        db.session.add(historico)
        
        # Commit transacional único (tudo ou nada)
        db.session.commit()
        
        print(f"DEBUG ATUALIZAR: Proposta {proposta.numero} atualizada com {len(item_descricoes)} itens")
        flash(f'Proposta atualizada com sucesso! {len(item_descricoes)} itens salvos.', 'success')
        
        return redirect(url_for('propostas.visualizar', id=proposta.id))
        
    except Exception as e:
        db.session.rollback()
        print(f"ERRO ATUALIZAR PROPOSTA: {str(e)}")
        import traceback
        traceback.print_exc()
        flash(f'Erro ao atualizar proposta: {str(e)}', 'error')
        return redirect(url_for('propostas.editar', id=id))

@propostas_bp.route('/deletar/<int:id>', methods=['POST'])
@login_required
@admin_required
def deletar(id):
    """Deletar proposta"""
    try:
        admin_id = get_admin_id()
        proposta = Proposta.query.filter_by(id=id, admin_id=admin_id).first_or_404()
        
        numero_proposta = proposta.numero
        
        # Registrar no histórico ANTES de deletar
        historico = PropostaHistorico(
            proposta_id=proposta.id,
            usuario_id=current_user.id,
            acao='excluida',
            observacao=f'Proposta excluída por {current_user.username}',
            admin_id=admin_id
        )
        db.session.add(historico)
        
        # Deletar proposta
        db.session.delete(proposta)
        
        # Commit transacional único (tudo ou nada)
        db.session.commit()
        
        print(f"DEBUG DELETAR: Proposta {numero_proposta} excluída com sucesso")
        flash('Proposta excluída com sucesso!', 'success')
        
        return redirect(url_for('propostas.index'))
        
    except Exception as e:
        db.session.rollback()
        print(f"ERRO DELETAR PROPOSTA: {str(e)}")
        flash(f'Erro ao excluir proposta: {str(e)}', 'error')
        return redirect(url_for('propostas.visualizar', id=id))

@propostas_bp.route('/aprovar/<int:id>', methods=['POST'])
@login_required
@admin_required
def aprovar(id):
    """Aprovar proposta"""
    try:
        admin_id = get_admin_id()
        proposta = Proposta.query.filter_by(id=id, admin_id=admin_id).first_or_404()
        
        proposta.status = 'aprovada'
        
        # Registrar no histórico
        historico = PropostaHistorico(
            proposta_id=proposta.id,
            usuario_id=current_user.id,
            acao='aprovada',
            observacao=request.form.get('observacao', ''),
            admin_id=admin_id
        )
        db.session.add(historico)
        
        # Commit transacional único (tudo ou nada)
        db.session.commit()
        
        print(f"DEBUG APROVAR: Proposta {proposta.numero} aprovada")
        flash('Proposta aprovada com sucesso!', 'success')
        
        return redirect(url_for('propostas.visualizar', id=proposta.id))
        
    except Exception as e:
        db.session.rollback()
        print(f"ERRO APROVAR PROPOSTA: {str(e)}")
        flash(f'Erro ao aprovar proposta: {str(e)}', 'error')
        return redirect(url_for('propostas.visualizar', id=id))

@propostas_bp.route('/rejeitar/<int:id>', methods=['POST'])
@login_required
@admin_required
def rejeitar(id):
    """Rejeitar proposta"""
    try:
        admin_id = get_admin_id()
        proposta = Proposta.query.filter_by(id=id, admin_id=admin_id).first_or_404()
        
        proposta.status = 'rejeitada'
        
        # Registrar no histórico
        historico = PropostaHistorico(
            proposta_id=proposta.id,
            usuario_id=current_user.id,
            acao='rejeitada',
            observacao=request.form.get('motivo', 'Sem motivo especificado'),
            admin_id=admin_id
        )
        db.session.add(historico)
        
        # Commit transacional único (tudo ou nada)
        db.session.commit()
        
        print(f"DEBUG REJEITAR: Proposta {proposta.numero} rejeitada")
        flash('Proposta rejeitada.', 'warning')
        
        return redirect(url_for('propostas.visualizar', id=proposta.id))
        
    except Exception as e:
        db.session.rollback()
        print(f"ERRO REJEITAR PROPOSTA: {str(e)}")
        flash(f'Erro ao rejeitar proposta: {str(e)}', 'error')
        return redirect(url_for('propostas.visualizar', id=id))

# ===== PORTAL DO CLIENTE (ACESSO PÚBLICO VIA TOKEN) =====

@propostas_bp.route('/cliente/<token>')
def portal_cliente(token):
    """Portal para o cliente visualizar e aprovar proposta"""
    proposta = Proposta.query.filter_by(token_cliente=token).first_or_404()
    
    admin_id = None
    if proposta.criado_por:
        from models import Usuario
        usuario = Usuario.query.get(proposta.criado_por)
        if usuario:
            admin_id = usuario.admin_id or usuario.id
    
    if not admin_id and proposta.admin_id:
        admin_id = proposta.admin_id
    
    if not admin_id:
        admin_id = 10
    
    config_empresa = safe_db_operation(
        lambda: ConfiguracaoEmpresa.query.filter_by(admin_id=admin_id).first(),
        None
    )
    
    # Organizar itens por template e categoria
    if hasattr(proposta, 'itens') and proposta.itens:
        templates_organizados = organizar_itens_por_template(proposta.itens)
        proposta.templates_organizados = templates_organizados
    else:
        proposta.templates_organizados = []
    
    # Calcular total geral: priorizar valor_total da proposta (manual), senão calcular dos itens
    if proposta.valor_total:
        total_geral = proposta.valor_total
    elif proposta.itens:
        total_geral = sum(item.quantidade * item.preco_unitario for item in proposta.itens)
    else:
        total_geral = 0
    
    cores_empresa = {
        'primaria': config_empresa.cor_primaria if config_empresa and config_empresa.cor_primaria else '#007bff',
        'secundaria': config_empresa.cor_secundaria if config_empresa and config_empresa.cor_secundaria else '#6c757d',
        'fundo_proposta': config_empresa.cor_fundo_proposta if config_empresa and config_empresa.cor_fundo_proposta else '#f8f9fa'
    }
    
    return render_template('propostas/portal_cliente.html', 
                         proposta=proposta, 
                         config_empresa=config_empresa,
                         empresa_cores=cores_empresa,
                         total_geral=total_geral)

@propostas_bp.route('/cliente/<token>/aprovar', methods=['POST'])
def aprovar_proposta_cliente(token):
    """Cliente aprova a proposta"""
    proposta = Proposta.query.filter_by(token_cliente=token).first_or_404()
    
    try:
        proposta.status = 'aprovada'
        proposta.data_resposta_cliente = datetime.utcnow()
        proposta.observacoes_cliente = request.form.get('observacoes', '')
        
        db.session.commit()
        
        flash('Proposta aprovada com sucesso!', 'success')
        return render_template('propostas/aprovada.html', proposta=proposta)
        
    except Exception as e:
        db.session.rollback()
        flash(f'Erro ao aprovar proposta: {str(e)}', 'error')
        return redirect(url_for('propostas.portal_cliente', token=token))

@propostas_bp.route('/cliente/<token>/rejeitar', methods=['POST'])
def rejeitar_proposta_cliente(token):
    """Cliente rejeita a proposta"""
    proposta = Proposta.query.filter_by(token_cliente=token).first_or_404()
    
    try:
        proposta.status = 'rejeitada'
        proposta.data_resposta_cliente = datetime.utcnow()
        proposta.observacoes_cliente = request.form.get('observacoes', '')
        
        db.session.commit()
        
        flash('Sua resposta foi registrada.', 'info')
        return render_template('propostas/rejeitada.html', proposta=proposta)
        
    except Exception as e:
        db.session.rollback()
        flash(f'Erro ao processar resposta: {str(e)}', 'error')
        return redirect(url_for('propostas.portal_cliente', token=token))

# ===== API DE CLIENTES =====

@propostas_bp.route('/api/clientes')
@login_required
def api_clientes():
    """API para buscar clientes - usado no formulário de propostas"""
    try:
        admin_id = get_admin_id()
        termo = request.args.get('q', '').strip()
        
        # Query base com filtro por admin
        query = Cliente.query.filter_by(admin_id=admin_id)
        
        # Se houver termo de busca, filtrar por nome ou email
        if termo:
            query = query.filter(
                or_(
                    Cliente.nome.ilike(f'%{termo}%'),
                    Cliente.email.ilike(f'%{termo}%')
                )
            )
        
        # Limitar a 20 resultados
        clientes = query.limit(20).all()
        
        print(f"DEBUG API CLIENTES: {len(clientes)} clientes encontrados para termo '{termo}'")
        
        # Retornar JSON
        return jsonify([{
            'id': c.id,
            'nome': c.nome,
            'email': c.email if c.email else '',
            'telefone': c.telefone if c.telefone else '',
            'endereco': c.endereco if c.endereco else ''
        } for c in clientes])
        
    except Exception as e:
        print(f"ERRO API CLIENTES: {str(e)}")
        return jsonify({'error': str(e)}), 400

# ===== ROTAS DE ARQUIVOS =====

def otimizar_imagem_base64(arquivo_bytes_ou_path):
    """Otimiza imagens e retorna 3 versões em Base64 (PERSISTÊNCIA COMPLETA)
    
    Args:
        arquivo_bytes_ou_path: Bytes do arquivo ou caminho (str/Path)
    
    Returns:
        Dict com:
            - original_base64: Imagem original completa em Base64 WebP
            - otimizada_base64: Imagem otimizada 1200px em Base64 WebP
            - thumbnail_base64: Thumbnail 300px em Base64 WebP
            - tamanho_original: Tamanho em bytes da versão original
            - tamanho_otimizada: Tamanho em bytes da versão otimizada
            - tamanho_thumbnail: Tamanho em bytes do thumbnail
    """
    try:
        # Abrir imagem (aceita bytes ou caminho)
        if isinstance(arquivo_bytes_ou_path, (str, os.PathLike)):
            img = Image.open(arquivo_bytes_ou_path)
        else:
            img = Image.open(BytesIO(arquivo_bytes_ou_path))
        
        # Converter RGBA para RGB se necessário (WebP não aceita RGBA)
        if img.mode in ('RGBA', 'LA', 'P'):
            background = Image.new('RGB', img.size, (255, 255, 255))
            if img.mode == 'P':
                img = img.convert('RGBA')
            background.paste(img, mask=img.split()[-1] if img.mode == 'RGBA' else None)
            img = background
        
        # 1️⃣ VERSÃO ORIGINAL COMPLETA (WebP otimizado)
        buffer_original = BytesIO()
        img.save(buffer_original, format='WEBP', quality=90, optimize=True)
        buffer_original.seek(0)
        base64_original = base64.b64encode(buffer_original.read()).decode('utf-8')
        original_base64 = f"data:image/webp;base64,{base64_original}"
        tamanho_original = len(base64_original)
        
        # 2️⃣ VERSÃO OTIMIZADA 1200px
        img_otimizada = img.copy()
        if img_otimizada.width > 1200:
            ratio = 1200 / img_otimizada.width
            new_height = int(img_otimizada.height * ratio)
            img_otimizada = img_otimizada.resize((1200, new_height), Image.Resampling.LANCZOS)
        
        buffer_otimizada = BytesIO()
        img_otimizada.save(buffer_otimizada, format='WEBP', quality=85, optimize=True)
        buffer_otimizada.seek(0)
        base64_otimizada = base64.b64encode(buffer_otimizada.read()).decode('utf-8')
        otimizada_base64 = f"data:image/webp;base64,{base64_otimizada}"
        tamanho_otimizada = len(base64_otimizada)
        
        # 3️⃣ THUMBNAIL 300px (crop centralizado)
        img_thumb = img.copy()
        # Calcular crop centralizado (quadrado)
        width, height = img_thumb.size
        if width > height:
            left = (width - height) // 2
            top = 0
            right = left + height
            bottom = height
        else:
            left = 0
            top = (height - width) // 2
            right = width
            bottom = top + width
        
        img_thumb_cropped = img_thumb.crop((left, top, right, bottom))
        img_thumb_cropped.thumbnail((300, 300), Image.Resampling.LANCZOS)
        
        buffer_thumb = BytesIO()
        img_thumb_cropped.save(buffer_thumb, format='WEBP', quality=65, optimize=True)
        buffer_thumb.seek(0)
        base64_thumb = base64.b64encode(buffer_thumb.read()).decode('utf-8')
        thumbnail_base64 = f"data:image/webp;base64,{base64_thumb}"
        tamanho_thumbnail = len(base64_thumb)
        
        print(f"✅ Imagem processada em Base64:")
        print(f"   📊 Original: {tamanho_original:,} bytes")
        print(f"   📊 Otimizada (1200px): {tamanho_otimizada:,} bytes")
        print(f"   📊 Thumbnail (300px): {tamanho_thumbnail:,} bytes")
        print(f"   📊 Total: {(tamanho_original + tamanho_otimizada + tamanho_thumbnail):,} bytes")
        
        return {
            'original_base64': original_base64,
            'otimizada_base64': otimizada_base64,
            'thumbnail_base64': thumbnail_base64,
            'tamanho_original': tamanho_original,
            'tamanho_otimizada': tamanho_otimizada,
            'tamanho_thumbnail': tamanho_thumbnail
        }
        
    except Exception as e:
        print(f"ERRO otimizar_imagem_base64: {str(e)}")
        import traceback
        traceback.print_exc()
        return None

def get_file_category(filename):
    """Determina a categoria do arquivo baseado na extensão"""
    ext = filename.rsplit('.', 1)[1].lower() if '.' in filename else ''
    
    if ext in ['dwg', 'dxf']:
        return 'dwg'
    elif ext in ['pdf']:
        return 'pdf'
    elif ext in ['jpg', 'jpeg', 'png', 'gif', 'webp']:
        return 'imagem'
    elif ext in ['doc', 'docx', 'xlsx', 'xls', 'txt']:
        return 'documento'
    else:
        return 'outros'

@propostas_bp.route('/<int:id>/upload-arquivo', methods=['POST'])
@login_required
@admin_required
def upload_arquivo(id):
    """Upload de múltiplos arquivos para uma proposta - SISTEMA BASE64 PERSISTENTE"""
    try:
        admin_id = get_admin_id()
        proposta = Proposta.query.filter_by(id=id, admin_id=admin_id).first_or_404()
        
        if 'arquivos' not in request.files:
            return jsonify({'success': False, 'message': 'Nenhum arquivo selecionado'}), 400
        
        arquivos = request.files.getlist('arquivos')
        arquivos_salvos = []
        
        for arquivo in arquivos:
            if arquivo.filename == '':
                continue
            
            # Validar extensão
            filename = arquivo.filename
            ext = filename.rsplit('.', 1)[1].lower() if '.' in filename else ''
            if ext not in ALLOWED_EXTENSIONS:
                continue
            
            # Ler bytes do arquivo UMA VEZ
            arquivo_bytes = arquivo.read()
            nome_original = secure_filename(filename)
            categoria = get_file_category(nome_original)
            
            # ===== PROCESSAMENTO CONFORME TIPO =====
            proposta_arquivo = PropostaArquivo()
            proposta_arquivo.admin_id = admin_id
            proposta_arquivo.proposta_id = proposta.id
            proposta_arquivo.nome_original = nome_original
            proposta_arquivo.tipo_arquivo = mimetypes.guess_type(nome_original)[0]
            proposta_arquivo.categoria = categoria
            proposta_arquivo.enviado_por = current_user.id
            
            # 🖼️ IMAGENS: Processar 3 versões Base64
            if ext in ['jpg', 'jpeg', 'png', 'gif']:
                print(f"📸 Processando IMAGEM: {nome_original}...")
                
                resultado = otimizar_imagem_base64(arquivo_bytes)
                if not resultado:
                    print(f"⚠️ Erro ao processar imagem {nome_original}, pulando...")
                    continue
                
                # Salvar 3 versões Base64 no banco
                proposta_arquivo.imagem_original_base64 = resultado['original_base64']
                proposta_arquivo.imagem_otimizada_base64 = resultado['otimizada_base64']
                proposta_arquivo.thumbnail_base64 = resultado['thumbnail_base64']
                
                # Tamanho total (soma das 3 versões)
                tamanho_total = resultado['tamanho_original'] + resultado['tamanho_otimizada'] + resultado['tamanho_thumbnail']
                proposta_arquivo.tamanho_bytes = tamanho_total
                
                # Caminho vazio (não salva no disco)
                proposta_arquivo.caminho_arquivo = f"base64://{nome_original}"
                proposta_arquivo.nome_arquivo = f"{uuid.uuid4().hex}.webp"
                
                print(f"   ✅ Imagem salva em Base64:")
                print(f"      Original: {resultado['tamanho_original']:,} bytes")
                print(f"      Otimizada: {resultado['tamanho_otimizada']:,} bytes")
                print(f"      Thumbnail: {resultado['tamanho_thumbnail']:,} bytes")
                print(f"      TOTAL: {tamanho_total:,} bytes")
            
            # 📄 OUTROS ARQUIVOS (PDF, DWG, DOC): Base64 direto
            else:
                print(f"📄 Processando ARQUIVO: {nome_original}...")
                
                # Converter para Base64
                arquivo_base64_str = base64.b64encode(arquivo_bytes).decode('utf-8')
                proposta_arquivo.arquivo_base64 = f"data:{proposta_arquivo.tipo_arquivo or 'application/octet-stream'};base64,{arquivo_base64_str}"
                
                proposta_arquivo.tamanho_bytes = len(arquivo_base64_str)
                proposta_arquivo.caminho_arquivo = f"base64://{nome_original}"
                proposta_arquivo.nome_arquivo = f"{uuid.uuid4().hex}.{ext}"
                
                print(f"   ✅ Arquivo salvo em Base64: {len(arquivo_base64_str):,} bytes")
            
            db.session.add(proposta_arquivo)
            arquivos_salvos.append({
                'id': proposta_arquivo.id,
                'nome': nome_original,
                'tamanho': proposta_arquivo.tamanho_bytes,
                'categoria': categoria
            })
        
        db.session.commit()
        
        print(f"✅ {len(arquivos_salvos)} arquivo(s) salvos em Base64 para proposta {proposta.numero}")
        
        return jsonify({
            'success': True,
            'message': f'{len(arquivos_salvos)} arquivo(s) enviado(s) com sucesso! (Base64 persistente)',
            'arquivos': arquivos_salvos
        })
        
    except Exception as e:
        db.session.rollback()
        print(f"ERRO UPLOAD ARQUIVO: {str(e)}")
        import traceback
        traceback.print_exc()
        return jsonify({'success': False, 'message': f'Erro ao fazer upload: {str(e)}'}), 500

@propostas_bp.route('/arquivo/<int:arquivo_id>')
@login_required
@admin_required
def download_arquivo(arquivo_id):
    """Download/visualização de arquivo anexado - SISTEMA BASE64 PERSISTENTE"""
    try:
        admin_id = get_admin_id()
        arquivo = PropostaArquivo.query.filter_by(id=arquivo_id, admin_id=admin_id).first_or_404()
        
        # ===== PRIORIDADE 1: Servir a partir do Base64 (PERSISTENTE) =====
        
        # 🖼️ IMAGENS: usar versão otimizada Base64
        if arquivo.imagem_otimizada_base64:
            print(f"📸 Servindo IMAGEM do Base64: {arquivo.nome_original}")
            
            # Extrair Base64 puro (remover prefixo data:image/webp;base64,)
            if ',' in arquivo.imagem_otimizada_base64:
                base64_data = arquivo.imagem_otimizada_base64.split(',', 1)[1]
            else:
                base64_data = arquivo.imagem_otimizada_base64
            
            # Decodificar Base64 para bytes
            arquivo_bytes = base64.b64decode(base64_data)
            
            # Criar BytesIO e servir
            buffer = BytesIO(arquivo_bytes)
            buffer.seek(0)
            
            # 🔧 FIX: Renomear extensão para .webp (imagem foi convertida no upload)
            nome_download = os.path.splitext(arquivo.nome_original)[0] + '.webp'
            
            return send_file(
                buffer,
                mimetype='image/webp',
                as_attachment=False,
                download_name=nome_download
            )
        
        # 📄 OUTROS ARQUIVOS: usar arquivo_base64
        elif arquivo.arquivo_base64:
            print(f"📄 Servindo ARQUIVO do Base64: {arquivo.nome_original}")
            
            # Extrair Base64 puro
            if ',' in arquivo.arquivo_base64:
                base64_data = arquivo.arquivo_base64.split(',', 1)[1]
            else:
                base64_data = arquivo.arquivo_base64
            
            # Decodificar Base64 para bytes
            arquivo_bytes = base64.b64decode(base64_data)
            
            # Criar BytesIO e servir
            buffer = BytesIO(arquivo_bytes)
            buffer.seek(0)
            
            # Detectar mimetype correto
            mimetype = arquivo.tipo_arquivo or mimetypes.guess_type(arquivo.nome_original)[0] or 'application/octet-stream'
            
            return send_file(
                buffer,
                mimetype=mimetype,
                as_attachment=False,
                download_name=arquivo.nome_original
            )
        
        # ===== FALLBACK: Arquivo físico antigo (BACKWARD COMPATIBILITY) =====
        elif arquivo.caminho_arquivo and not arquivo.caminho_arquivo.startswith('base64://'):
            print(f"⚠️ FALLBACK: Servindo arquivo físico (legado): {arquivo.caminho_arquivo}")
            
            if not os.path.exists(arquivo.caminho_arquivo):
                flash('Arquivo não encontrado no servidor', 'error')
                return redirect(url_for('propostas.index'))
            
            # Determinar mimetype correto baseado na extensão real do arquivo
            extensao = os.path.splitext(arquivo.caminho_arquivo)[1].lower()
            if extensao == '.webp':
                mimetype = 'image/webp'
            else:
                mimetype = arquivo.tipo_arquivo or mimetypes.guess_type(arquivo.caminho_arquivo)[0]
            
            return send_file(
                arquivo.caminho_arquivo,
                as_attachment=False,
                download_name=arquivo.nome_original,
                mimetype=mimetype
            )
        
        # ===== ERRO: Nenhuma fonte de dados disponível =====
        else:
            print(f"❌ ERRO: Arquivo {arquivo.nome_original} sem dados Base64 nem arquivo físico")
            flash('Arquivo não disponível', 'error')
            return redirect(url_for('propostas.index'))
        
    except Exception as e:
        print(f"ERRO DOWNLOAD ARQUIVO: {str(e)}")
        import traceback
        traceback.print_exc()
        flash(f'Erro ao baixar arquivo: {str(e)}', 'error')
        return redirect(url_for('propostas.index'))

@propostas_bp.route('/arquivo/<int:arquivo_id>/delete', methods=['POST'])
@login_required
@admin_required
def deletar_arquivo(arquivo_id):
    """Deletar arquivo anexado - SISTEMA BASE64 (sem arquivos físicos)"""
    try:
        admin_id = get_admin_id()
        arquivo = PropostaArquivo.query.filter_by(id=arquivo_id, admin_id=admin_id).first_or_404()
        
        proposta_id = arquivo.proposta_id
        nome_original = arquivo.nome_original
        
        # ===== APENAS DELETAR DO BANCO =====
        # Arquivos Base64 são salvos no banco de dados, não há arquivos físicos para deletar
        # NOTA: Backward compatibility - arquivos antigos físicos permanecem no disco (não causam problema)
        
        db.session.delete(arquivo)
        db.session.commit()
        
        print(f"✅ Arquivo {nome_original} removido do banco (Base64)")
        
        return jsonify({
            'success': True,
            'message': 'Arquivo excluído com sucesso!'
        })
        
    except Exception as e:
        db.session.rollback()
        print(f"ERRO DELETAR ARQUIVO: {str(e)}")
        import traceback
        traceback.print_exc()
        return jsonify({'success': False, 'message': f'Erro ao excluir arquivo: {str(e)}'}), 500

print("✅ Propostas Consolidated Blueprint carregado com padrões de resiliência")