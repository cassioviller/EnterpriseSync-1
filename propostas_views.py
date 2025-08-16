from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify, send_file
from flask_login import login_required, current_user
from functools import wraps
import os
from werkzeug.utils import secure_filename
from datetime import datetime, timedelta
import uuid
import mimetypes

from app import db
from models import PropostaComercialSIGE, PropostaItem, PropostaArquivo, PropostaTemplate

# Criar blueprint
propostas_bp = Blueprint('propostas', __name__, url_prefix='/propostas')

def admin_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not current_user.is_authenticated or current_user.tipo_usuario.name not in ['ADMIN', 'SUPER_ADMIN']:
            flash('Acesso negado. Apenas administradores podem acessar esta área.', 'error')
            return redirect(url_for('main.dashboard'))
        return f(*args, **kwargs)
    return decorated_function

# Configurações de upload
UPLOAD_FOLDER = 'static/uploads/propostas'
ALLOWED_EXTENSIONS = {'pdf', 'dwg', 'dxf', 'png', 'jpg', 'jpeg', 'gif', 'doc', 'docx', 'xlsx', 'xls'}

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

def get_file_category(filename):
    """Determina a categoria do arquivo baseado na extensão"""
    ext = filename.rsplit('.', 1)[1].lower() if '.' in filename else ''
    
    if ext in ['dwg', 'dxf']:
        return 'dwg'
    elif ext == 'pdf':
        return 'pdf'
    elif ext in ['png', 'jpg', 'jpeg', 'gif']:
        return 'foto'
    elif ext in ['doc', 'docx', 'xlsx', 'xls']:
        return 'documento'
    else:
        return 'outros'

@propostas_bp.route('/')
@login_required
@admin_required
def listar_propostas():
    """Lista todas as propostas"""
    page = request.args.get('page', 1, type=int)
    status_filter = request.args.get('status', '')
    cliente_filter = request.args.get('cliente', '')
    
    query = PropostaComercialSIGE.query
    
    # Filtros
    if status_filter:
        query = query.filter(PropostaComercialSIGE.status == status_filter)
    if cliente_filter:
        query = query.filter(PropostaComercialSIGE.cliente_nome.ilike(f'%{cliente_filter}%'))
    
    propostas = query.order_by(PropostaComercialSIGE.criado_em.desc()).paginate(
        page=page, per_page=20, error_out=False
    )
    
    return render_template('propostas/listar.html', propostas=propostas, 
                         status_filter=status_filter, cliente_filter=cliente_filter)

@propostas_bp.route('/nova')
@login_required
def nova_proposta():
    """Formulário para criar nova proposta"""
    print(f"DEBUG: ACESSANDO NOVA PROPOSTA - Usuario atual: {current_user.id} - {current_user.nome} - {current_user.tipo_usuario.name}")
    print(f"DEBUG: Usuario autenticado? {current_user.is_authenticated}")
    print(f"DEBUG: Tipo de usuario: {current_user.tipo_usuario.name if current_user.is_authenticated else 'N/A'}")
    
    # Buscar templates disponíveis baseado no tipo de usuário
    if current_user.tipo_usuario.name == 'SUPER_ADMIN':
        # Super Admin vê todos os templates
        templates = PropostaTemplate.query.filter_by(ativo=True).all()
        print(f"DEBUG: Super Admin - encontrou {len(templates)} templates")
    else:
        # Admin vê apenas seus templates
        templates = PropostaTemplate.query.filter_by(
            admin_id=current_user.id, 
            ativo=True
        ).all()
        print(f"DEBUG: Admin - encontrou {len(templates)} templates para admin_id={current_user.id}")
    
    for t in templates:
        print(f"DEBUG: Template {t.id}: {t.nome} (admin_id={t.admin_id})")
    
    return render_template('propostas/nova_proposta.html', templates=templates)

@propostas_bp.route('/criar', methods=['POST'])
@login_required
@admin_required
def criar_proposta():
    """Cria uma nova proposta"""
    try:
        # Dados básicos da proposta
        proposta = PropostaComercialSIGE()
        proposta.cliente_nome = request.form.get('cliente_nome')
        proposta.cliente_telefone = request.form.get('cliente_telefone')
        proposta.cliente_email = request.form.get('cliente_email')
        proposta.cliente_endereco = request.form.get('cliente_endereco')
        proposta.assunto = request.form.get('assunto')
        proposta.objeto = request.form.get('objeto')
        proposta.documentos_referencia = request.form.get('documentos_referencia')
        proposta.prazo_entrega_dias = int(request.form.get('prazo_entrega_dias', 90))
        proposta.observacoes_entrega = request.form.get('observacoes_entrega')
        proposta.validade_dias = int(request.form.get('validade_dias', 7))
        proposta.percentual_nota_fiscal = float(request.form.get('percentual_nota_fiscal', 13.5))
        proposta.condicoes_pagamento = request.form.get('condicoes_pagamento')
        proposta.garantias = request.form.get('garantias')
        proposta.consideracoes_gerais = request.form.get('consideracoes_gerais')
        proposta.criado_por = current_user.id
        
        # Itens inclusos/exclusos
        itens_inclusos = request.form.getlist('itens_inclusos')
        itens_exclusos = request.form.getlist('itens_exclusos')
        
        if itens_inclusos:
            proposta.itens_inclusos = itens_inclusos
        if itens_exclusos:
            proposta.itens_exclusos = itens_exclusos
        
        db.session.add(proposta)
        db.session.flush()  # Para obter o ID da proposta
        
        # Itens da tabela de serviços
        descricoes = request.form.getlist('item_descricao')
        quantidades = request.form.getlist('item_quantidade')
        unidades = request.form.getlist('item_unidade')
        precos = request.form.getlist('item_preco')
        
        for i, descricao in enumerate(descricoes):
            if descricao.strip():
                item = PropostaItem()
                item.proposta_id = proposta.id
                item.item_numero = i + 1
                item.descricao = descricao
                item.quantidade = float(quantidades[i]) if quantidades[i] else 0
                item.unidade = unidades[i] if i < len(unidades) else 'un'
                item.preco_unitario = float(precos[i]) if precos[i] else 0
                item.ordem = i + 1
                db.session.add(item)
        
        # Calcular valor total
        proposta.calcular_valor_total()
        
        db.session.commit()
        flash('Proposta criada com sucesso!', 'success')
        return redirect(url_for('propostas.visualizar_proposta', id=proposta.id))
        
    except Exception as e:
        db.session.rollback()
        flash(f'Erro ao criar proposta: {str(e)}', 'error')
        return redirect(url_for('propostas.nova_proposta'))

@propostas_bp.route('/<int:id>')
@login_required
@admin_required
def visualizar_proposta(id):
    """Visualiza uma proposta específica"""
    proposta = PropostaComercialSIGE.query.get_or_404(id)
    return render_template('propostas/visualizar.html', proposta=proposta)

@propostas_bp.route('/<int:id>/editar')
@login_required
@admin_required
def editar_proposta(id):
    """Formulário para editar proposta"""
    proposta = PropostaComercialSIGE.query.get_or_404(id)
    templates = PropostaTemplate.query.filter_by(ativo=True).all()
    return render_template('propostas/editar.html', proposta=proposta, templates=templates)

@propostas_bp.route('/<int:id>/atualizar', methods=['POST'])
@login_required
@admin_required
def atualizar_proposta(id):
    """Atualiza uma proposta existente"""
    proposta = PropostaComercialSIGE.query.get_or_404(id)
    
    try:
        # Atualizar dados básicos
        proposta.cliente_nome = request.form.get('cliente_nome')
        proposta.cliente_telefone = request.form.get('cliente_telefone')
        proposta.cliente_email = request.form.get('cliente_email')
        proposta.cliente_endereco = request.form.get('cliente_endereco')
        proposta.assunto = request.form.get('assunto')
        proposta.objeto = request.form.get('objeto')
        proposta.documentos_referencia = request.form.get('documentos_referencia')
        proposta.prazo_entrega_dias = int(request.form.get('prazo_entrega_dias', 90))
        proposta.observacoes_entrega = request.form.get('observacoes_entrega')
        proposta.validade_dias = int(request.form.get('validade_dias', 7))
        proposta.percentual_nota_fiscal = float(request.form.get('percentual_nota_fiscal', 13.5))
        proposta.condicoes_pagamento = request.form.get('condicoes_pagamento')
        proposta.garantias = request.form.get('garantias')
        proposta.consideracoes_gerais = request.form.get('consideracoes_gerais')
        proposta.atualizado_em = datetime.utcnow()
        
        # Atualizar itens inclusos/exclusos
        itens_inclusos = request.form.getlist('itens_inclusos')
        itens_exclusos = request.form.getlist('itens_exclusos')
        
        if itens_inclusos:
            proposta.itens_inclusos = itens_inclusos
        if itens_exclusos:
            proposta.itens_exclusos = itens_exclusos
        
        # Remover itens existentes
        PropostaItem.query.filter_by(proposta_id=proposta.id).delete()
        
        # Adicionar novos itens
        descricoes = request.form.getlist('item_descricao')
        quantidades = request.form.getlist('item_quantidade')
        unidades = request.form.getlist('item_unidade')
        precos = request.form.getlist('item_preco')
        
        for i, descricao in enumerate(descricoes):
            if descricao.strip():
                item = PropostaItem()
                item.proposta_id = proposta.id
                item.item_numero = i + 1
                item.descricao = descricao
                item.quantidade = float(quantidades[i]) if quantidades[i] else 0
                item.unidade = unidades[i] if i < len(unidades) else 'un'
                item.preco_unitario = float(precos[i]) if precos[i] else 0
                item.ordem = i + 1
                db.session.add(item)
        
        # Recalcular valor total
        db.session.flush()
        proposta.calcular_valor_total()
        
        db.session.commit()
        flash('Proposta atualizada com sucesso!', 'success')
        return redirect(url_for('propostas.visualizar_proposta', id=proposta.id))
        
    except Exception as e:
        db.session.rollback()
        flash(f'Erro ao atualizar proposta: {str(e)}', 'error')
        return redirect(url_for('propostas.editar_proposta', id=id))

@propostas_bp.route('/<int:id>/arquivos/upload', methods=['POST'])
@login_required
@admin_required
def upload_arquivo(id):
    """Upload de arquivo para uma proposta"""
    proposta = PropostaComercialSIGE.query.get_or_404(id)
    
    if 'arquivo' not in request.files:
        return jsonify({'error': 'Nenhum arquivo selecionado'}), 400
    
    arquivo = request.files['arquivo']
    if arquivo.filename == '':
        return jsonify({'error': 'Nenhum arquivo selecionado'}), 400
    
    if not allowed_file(arquivo.filename):
        return jsonify({'error': 'Tipo de arquivo não permitido'}), 400
    
    try:
        # Criar diretório se não existir
        upload_path = os.path.join(UPLOAD_FOLDER, str(proposta.id))
        os.makedirs(upload_path, exist_ok=True)
        
        # Gerar nome único para o arquivo
        filename = arquivo.filename or 'arquivo'
        nome_original = secure_filename(filename)
        extensao = nome_original.rsplit('.', 1)[1].lower() if '.' in nome_original else ''
        nome_arquivo = f"{uuid.uuid4().hex}.{extensao}"
        caminho_completo = os.path.join(upload_path, nome_arquivo)
        
        # Salvar arquivo
        arquivo.save(caminho_completo)
        
        # Salvar informações no banco
        proposta_arquivo = PropostaArquivo()
        proposta_arquivo.proposta_id = proposta.id
        proposta_arquivo.nome_arquivo = nome_arquivo
        proposta_arquivo.nome_original = nome_original
        proposta_arquivo.tipo_arquivo = mimetypes.guess_type(nome_original)[0]
        proposta_arquivo.tamanho_bytes = os.path.getsize(caminho_completo)
        proposta_arquivo.caminho_arquivo = caminho_completo
        proposta_arquivo.categoria = get_file_category(nome_original)
        proposta_arquivo.enviado_por = current_user.id
        
        db.session.add(proposta_arquivo)
        db.session.commit()
        
        return jsonify({
            'success': True,
            'arquivo': proposta_arquivo.to_dict()
        })
        
    except Exception as e:
        return jsonify({'error': f'Erro ao fazer upload: {str(e)}'}), 500

@propostas_bp.route('/api/template/<int:template_id>')
@login_required
@admin_required
def obter_template(template_id):
    """API para obter dados de um template"""
    template = PropostaTemplate.query.get_or_404(template_id)
    return jsonify(template.to_dict())

@propostas_bp.route('/<int:id>/pdf')
@login_required
@admin_required
def gerar_pdf(id):
    """Gera PDF da proposta"""
    proposta = PropostaComercialSIGE.query.get_or_404(id)
    
    # Renderizar HTML da proposta
    html_content = render_template('propostas/pdf.html', proposta=proposta)
    
    # Aqui seria implementada a geração de PDF
    # Por enquanto, retorna o HTML para visualização
    return html_content

@propostas_bp.route('/<int:id>/enviar', methods=['POST'])
@login_required
@admin_required
def enviar_proposta(id):
    """Envia proposta para o cliente"""
    proposta = PropostaComercialSIGE.query.get_or_404(id)
    
    try:
        # Atualizar status e data de envio
        proposta.status = 'enviada'
        proposta.data_envio = datetime.utcnow()
        
        db.session.commit()
        
        # Aqui seria implementado o envio por email
        # Por enquanto apenas atualiza o status
        
        flash('Proposta enviada com sucesso!', 'success')
        return redirect(url_for('propostas.visualizar_proposta', id=proposta.id))
        
    except Exception as e:
        db.session.rollback()
        flash(f'Erro ao enviar proposta: {str(e)}', 'error')
        return redirect(url_for('propostas.visualizar_proposta', id=proposta.id))

@propostas_bp.route('/<int:id>/excluir', methods=['POST'])
@login_required
@admin_required
def excluir_proposta(id):
    """Exclui uma proposta"""
    proposta = PropostaComercialSIGE.query.get_or_404(id)
    
    try:
        # Remover arquivos físicos
        upload_path = os.path.join(UPLOAD_FOLDER, str(proposta.id))
        if os.path.exists(upload_path):
            import shutil
            shutil.rmtree(upload_path)
        
        # Remover do banco (cascade remove itens e arquivos)
        db.session.delete(proposta)
        db.session.commit()
        
        flash('Proposta excluída com sucesso!', 'success')
        return redirect(url_for('propostas.listar_propostas'))
        
    except Exception as e:
        db.session.rollback()
        flash(f'Erro ao excluir proposta: {str(e)}', 'error')
        return redirect(url_for('propostas.visualizar_proposta', id=proposta.id))

# Portal do Cliente
@propostas_bp.route('/cliente/<token>')
def portal_cliente(token):
    """Portal para o cliente visualizar e aprovar proposta"""
    proposta = PropostaComercialSIGE.query.filter_by(token_cliente=token).first_or_404()
    return render_template('propostas/portal_cliente.html', proposta=proposta)

@propostas_bp.route('/cliente/<token>/aprovar', methods=['POST'])
def aprovar_proposta(token):
    """Cliente aprova a proposta"""
    proposta = PropostaComercialSIGE.query.filter_by(token_cliente=token).first_or_404()
    
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
def rejeitar_proposta(token):
    """Cliente rejeita a proposta"""
    proposta = PropostaComercialSIGE.query.filter_by(token_cliente=token).first_or_404()
    
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