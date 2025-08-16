# TEMPLATES DE PROPOSTAS - CRUD COMPLETO
# Sistema de Templates com Serviços/Atividades Pré-selecionados

from flask import Blueprint, render_template, request, redirect, url_for, jsonify, flash
from flask_login import login_required, current_user
from functools import wraps
from models import db, PropostaTemplate, ServicoTemplate, Servico, TipoUsuario
from datetime import datetime
import logging

# Configurar logging
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

# Blueprint para templates de propostas
templates_bp = Blueprint('templates', __name__, url_prefix='/templates')

def admin_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not current_user.is_authenticated or current_user.tipo_usuario.name not in ['ADMIN', 'SUPER_ADMIN']:
            flash('Acesso negado. Apenas administradores podem acessar esta área.', 'error')
            return redirect(url_for('main.dashboard'))
        return f(*args, **kwargs)
    return decorated_function

# ==========================================
# DASHBOARD DE TEMPLATES
# ==========================================

@templates_bp.route('/')
@login_required 
@admin_required
def dashboard():
    """Dashboard principal de templates"""
    
    # Determinar admin_id
    admin_id = current_user.id if current_user.tipo_usuario == TipoUsuario.ADMIN else 2
    
    # Estatísticas gerais
    total_templates = PropostaTemplate.query.filter_by(admin_id=admin_id).count()
    templates_ativos = PropostaTemplate.query.filter_by(admin_id=admin_id, ativo=True).count()
    
    # Templates por categoria
    categorias_stats = db.session.query(
        PropostaTemplate.categoria,
        db.func.count(PropostaTemplate.id).label('total')
    ).filter(
        PropostaTemplate.admin_id == admin_id,
        PropostaTemplate.ativo == True
    ).group_by(PropostaTemplate.categoria).all()
    
    # Templates mais utilizados
    templates_populares = PropostaTemplate.query.filter_by(
        admin_id=admin_id,
        ativo=True
    ).order_by(PropostaTemplate.uso_contador.desc()).limit(5).all()
    
    # Templates recentes
    templates_recentes = PropostaTemplate.query.filter_by(
        admin_id=admin_id
    ).order_by(PropostaTemplate.criado_em.desc()).limit(5).all()
    
    # Total de serviços disponíveis para templates
    total_servicos = Servico.query.filter_by(ativo=True).count()
    
    return render_template('templates/dashboard.html',
                         total_templates=total_templates,
                         templates_ativos=templates_ativos,
                         categorias_stats=categorias_stats,
                         templates_populares=templates_populares,
                         templates_recentes=templates_recentes,
                         total_servicos=total_servicos)

# ==========================================
# LISTAGEM E VISUALIZAÇÃO DE TEMPLATES
# ==========================================

@templates_bp.route('/listar')
@login_required
@admin_required 
def listar_templates():
    """Lista todos os templates com filtros"""
    
    admin_id = current_user.id if current_user.tipo_usuario == TipoUsuario.ADMIN else 2
    
    # Parâmetros de filtro
    page = request.args.get('page', 1, type=int)
    categoria = request.args.get('categoria', '')
    busca = request.args.get('busca', '')
    status = request.args.get('status', '')
    
    # Query base
    query = PropostaTemplate.query.filter_by(admin_id=admin_id)
    
    # Aplicar filtros
    if categoria:
        query = query.filter(PropostaTemplate.categoria == categoria)
    if busca:
        query = query.filter(
            db.or_(
                PropostaTemplate.nome.ilike(f'%{busca}%'),
                PropostaTemplate.descricao.ilike(f'%{busca}%')
            )
        )
    if status == 'ativo':
        query = query.filter(PropostaTemplate.ativo == True)
    elif status == 'inativo':
        query = query.filter(PropostaTemplate.ativo == False)
    
    # Paginação
    templates = query.order_by(
        PropostaTemplate.uso_contador.desc(),
        PropostaTemplate.criado_em.desc()
    ).paginate(page=page, per_page=12, error_out=False)
    
    # Categorias disponíveis para filtro
    categorias = db.session.query(PropostaTemplate.categoria).filter_by(
        admin_id=admin_id
    ).distinct().all()
    categorias = [cat[0] for cat in categorias]
    
    return render_template('templates/listar.html',
                         templates=templates,
                         categorias=categorias,
                         categoria_filtro=categoria,
                         busca=busca,
                         status=status)

@templates_bp.route('/<int:id>')
@login_required
@admin_required
def ver_template(id):
    """Visualiza detalhes de um template"""
    
    admin_id = current_user.id if current_user.tipo_usuario == TipoUsuario.ADMIN else 2
    
    template = PropostaTemplate.query.filter_by(
        id=id, admin_id=admin_id
    ).first_or_404()
    
    return render_template('templates/ver.html', template=template)

# ==========================================
# CRIAÇÃO DE TEMPLATES
# ==========================================

@templates_bp.route('/novo', methods=['GET', 'POST'])
@login_required
@admin_required
def novo_template():
    """Formulário para criar novo template"""
    
    if request.method == 'POST':
        try:
            admin_id = current_user.id if current_user.tipo_usuario == TipoUsuario.ADMIN else 2
            
            # Dados básicos do template
            template = PropostaTemplate()
            template.nome = request.form.get('nome')
            template.descricao = request.form.get('descricao')
            template.categoria = request.form.get('categoria')
            template.prazo_entrega_dias = int(request.form.get('prazo_entrega_dias', 90))
            template.validade_dias = int(request.form.get('validade_dias', 7))
            template.percentual_nota_fiscal = float(request.form.get('percentual_nota_fiscal', 13.5))
            template.condicoes_pagamento = request.form.get('condicoes_pagamento')
            template.garantias = request.form.get('garantias')
            template.publico = 'publico' in request.form
            template.admin_id = admin_id
            template.criado_por = current_user.id
            
            # Processar itens do template (JSON)
            itens_json = request.form.get('itens_json')
            if itens_json:
                import json
                try:
                    template.itens_padrao = json.loads(itens_json)
                except json.JSONDecodeError:
                    template.itens_padrao = []
            else:
                template.itens_padrao = []
            
            db.session.add(template)
            db.session.commit()
            
            flash(f'Template "{template.nome}" criado com sucesso!', 'success')
            return redirect(url_for('templates.ver_template', id=template.id))
            
        except Exception as e:
            db.session.rollback()
            logger.error(f"Erro ao criar template: {str(e)}")
            flash(f'Erro ao criar template: {str(e)}', 'error')
    
    # Buscar serviços disponíveis para selecionar
    servicos = Servico.query.filter_by(ativo=True).order_by(
        Servico.categoria, Servico.nome
    ).all()
    
    # Agrupar serviços por categoria
    servicos_por_categoria = {}
    for servico in servicos:
        cat = servico.categoria
        if cat not in servicos_por_categoria:
            servicos_por_categoria[cat] = []
        servicos_por_categoria[cat].append(servico)
    
    return render_template('templates/novo.html', 
                         servicos_por_categoria=servicos_por_categoria)

# ==========================================
# EDIÇÃO DE TEMPLATES
# ==========================================

@templates_bp.route('/<int:id>/editar', methods=['GET', 'POST'])
@login_required
@admin_required
def editar_template(id):
    """Edita um template existente"""
    
    admin_id = current_user.id if current_user.tipo_usuario == TipoUsuario.ADMIN else 2
    
    template = PropostaTemplate.query.filter_by(
        id=id, admin_id=admin_id
    ).first_or_404()
    
    if request.method == 'POST':
        try:
            # Atualizar dados básicos
            template.nome = request.form.get('nome')
            template.descricao = request.form.get('descricao')
            template.categoria = request.form.get('categoria')
            template.prazo_entrega_dias = int(request.form.get('prazo_entrega_dias', 90))
            template.validade_dias = int(request.form.get('validade_dias', 7))
            template.percentual_nota_fiscal = float(request.form.get('percentual_nota_fiscal', 13.5))
            template.condicoes_pagamento = request.form.get('condicoes_pagamento')
            template.garantias = request.form.get('garantias')
            template.publico = 'publico' in request.form
            template.atualizado_em = datetime.utcnow()
            
            # Atualizar itens do template
            itens_json = request.form.get('itens_json')
            if itens_json:
                import json
                try:
                    template.itens_padrao = json.loads(itens_json)
                except json.JSONDecodeError:
                    pass  # Manter itens existentes se JSON inválido
            
            db.session.commit()
            
            flash(f'Template "{template.nome}" atualizado com sucesso!', 'success')
            return redirect(url_for('templates.ver_template', id=template.id))
            
        except Exception as e:
            db.session.rollback()
            logger.error(f"Erro ao editar template: {str(e)}")
            flash(f'Erro ao editar template: {str(e)}', 'error')
    
    # Buscar serviços disponíveis
    servicos = Servico.query.filter_by(ativo=True).order_by(
        Servico.categoria, Servico.nome
    ).all()
    
    servicos_por_categoria = {}
    for servico in servicos:
        cat = servico.categoria
        if cat not in servicos_por_categoria:
            servicos_por_categoria[cat] = []
        servicos_por_categoria[cat].append(servico)
    
    return render_template('templates/editar.html', 
                         template=template,
                         servicos_por_categoria=servicos_por_categoria)

# ==========================================
# AÇÕES ESPECIAIS
# ==========================================

@templates_bp.route('/<int:id>/duplicar', methods=['POST'])
@login_required
@admin_required
def duplicar_template(id):
    """Cria uma cópia do template"""
    
    admin_id = current_user.id if current_user.tipo_usuario == TipoUsuario.ADMIN else 2
    
    template_original = PropostaTemplate.query.filter_by(
        id=id, admin_id=admin_id
    ).first_or_404()
    
    try:
        nome_novo = request.form.get('nome_novo') or f"Cópia de {template_original.nome}"
        
        novo_template = template_original.duplicar(
            nome_novo=nome_novo,
            admin_id=admin_id,
            criado_por=current_user.id
        )
        
        db.session.commit()
        
        flash(f'Template duplicado como "{novo_template.nome}"!', 'success')
        return redirect(url_for('templates.ver_template', id=novo_template.id))
        
    except Exception as e:
        db.session.rollback()
        logger.error(f"Erro ao duplicar template: {str(e)}")
        flash(f'Erro ao duplicar template: {str(e)}', 'error')
        return redirect(url_for('templates.ver_template', id=id))

@templates_bp.route('/<int:id>/toggle-status', methods=['POST'])
@login_required
@admin_required
def toggle_status(id):
    """Ativa/desativa um template"""
    
    admin_id = current_user.id if current_user.tipo_usuario == TipoUsuario.ADMIN else 2
    
    template = PropostaTemplate.query.filter_by(
        id=id, admin_id=admin_id
    ).first_or_404()
    
    try:
        template.ativo = not template.ativo
        db.session.commit()
        
        status = "ativado" if template.ativo else "desativado"
        flash(f'Template "{template.nome}" {status}!', 'success')
        
    except Exception as e:
        db.session.rollback()
        flash(f'Erro ao alterar status: {str(e)}', 'error')
    
    return redirect(url_for('templates.ver_template', id=id))

@templates_bp.route('/<int:id>/deletar', methods=['POST'])
@login_required
@admin_required
def deletar_template(id):
    """Deleta um template (apenas se não tiver uso)"""
    
    admin_id = current_user.id if current_user.tipo_usuario == TipoUsuario.ADMIN else 2
    
    template = PropostaTemplate.query.filter_by(
        id=id, admin_id=admin_id
    ).first_or_404()
    
    try:
        # Verificar se template já foi usado
        if template.uso_contador > 0:
            flash('Não é possível deletar um template que já foi utilizado. Você pode desativá-lo.', 'warning')
            return redirect(url_for('templates.ver_template', id=id))
        
        nome_template = template.nome
        db.session.delete(template)
        db.session.commit()
        
        flash(f'Template "{nome_template}" deletado com sucesso!', 'success')
        return redirect(url_for('templates.listar_templates'))
        
    except Exception as e:
        db.session.rollback()
        logger.error(f"Erro ao deletar template: {str(e)}")
        flash(f'Erro ao deletar template: {str(e)}', 'error')
        return redirect(url_for('templates.ver_template', id=id))

# ==========================================
# APIs PARA INTERFACE DINÂMICA
# ==========================================

@templates_bp.route('/api/servicos')
@login_required
@admin_required
def api_servicos():
    """API para buscar serviços disponíveis"""
    
    busca = request.args.get('q', '')
    categoria = request.args.get('categoria', '')
    
    query = Servico.query.filter_by(ativo=True)
    
    if categoria:
        query = query.filter(Servico.categoria == categoria)
    
    if busca:
        query = query.filter(
            db.or_(
                Servico.nome.ilike(f'%{busca}%'),
                Servico.descricao.ilike(f'%{busca}%')
            )
        )
    
    servicos = query.limit(20).all()
    
    return jsonify([{
        'id': s.id,
        'nome': s.nome,
        'categoria': s.categoria,
        'unidade_medida': s.unidade_medida,
        'custo_unitario': float(s.custo_unitario) if s.custo_unitario else 0,
        'descricao': s.descricao
    } for s in servicos])

@templates_bp.route('/api/template/<int:id>')
@login_required
@admin_required
def api_template(id):
    """API para obter dados de um template em JSON"""
    
    admin_id = current_user.id if current_user.tipo_usuario == TipoUsuario.ADMIN else 2
    
    template = PropostaTemplate.query.filter_by(
        id=id, admin_id=admin_id
    ).first_or_404()
    
    return jsonify(template.to_dict())

@templates_bp.route('/api/categorias')
@login_required
@admin_required  
def api_categorias():
    """API para obter categorias disponíveis"""
    
    admin_id = current_user.id if current_user.tipo_usuario == TipoUsuario.ADMIN else 2
    
    categorias = db.session.query(PropostaTemplate.categoria).filter_by(
        admin_id=admin_id,
        ativo=True
    ).distinct().all()
    
    return jsonify([cat[0] for cat in categorias if cat[0]])