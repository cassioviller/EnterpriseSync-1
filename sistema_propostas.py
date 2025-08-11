"""
MÓDULO 1 - SISTEMA DE PROPOSTAS COMPLETO
Sistema avançado de gestão comercial com IA e automação total
"""

from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify
from flask_login import login_required, current_user
from models import db, Proposta, Cliente, Usuario, Obra
from datetime import datetime, timedelta
import json
import uuid
from werkzeug.utils import secure_filename
import os

# Blueprint para sistema de propostas
propostas_bp = Blueprint('propostas', __name__, url_prefix='/propostas')

@propostas_bp.route('/dashboard')
@login_required
def dashboard():
    """Dashboard avançado de propostas com métricas e funil de vendas"""
    
    # Métricas de propostas
    total_propostas = Proposta.query.filter_by(admin_id=current_user.id).count()
    propostas_pendentes = Proposta.query.filter_by(admin_id=current_user.id, status='pendente').count()
    propostas_aprovadas = Proposta.query.filter_by(admin_id=current_user.id, status='aprovada').count()
    propostas_rejeitadas = Proposta.query.filter_by(admin_id=current_user.id, status='rejeitada').count()
    
    # Valor total em propostas
    valor_total = db.session.query(db.func.sum(Proposta.valor_total)).filter_by(admin_id=current_user.id).scalar() or 0
    valor_aprovado = db.session.query(db.func.sum(Proposta.valor_total)).filter_by(admin_id=current_user.id, status='aprovada').scalar() or 0
    
    # Taxa de conversão
    taxa_conversao = (propostas_aprovadas / total_propostas * 100) if total_propostas > 0 else 0
    
    # Propostas recentes
    propostas_recentes = Proposta.query.filter_by(admin_id=current_user.id).order_by(Proposta.created_at.desc()).limit(10).all()
    
    # Propostas próximas ao vencimento (7 dias)
    data_limite = datetime.now() + timedelta(days=7)
    propostas_vencendo = Proposta.query.filter(
        Proposta.admin_id == current_user.id,
        Proposta.data_vencimento <= data_limite,
        Proposta.status == 'pendente'
    ).all()
    
    return render_template('propostas/dashboard.html',
                         total_propostas=total_propostas,
                         propostas_pendentes=propostas_pendentes,
                         propostas_aprovadas=propostas_aprovadas,
                         propostas_rejeitadas=propostas_rejeitadas,
                         valor_total=valor_total,
                         valor_aprovado=valor_aprovado,
                         taxa_conversao=taxa_conversao,
                         propostas_recentes=propostas_recentes,
                         propostas_vencendo=propostas_vencendo)

@propostas_bp.route('/nova')
@login_required
def nova_proposta():
    """Formulário para criar nova proposta"""
    clientes = Cliente.query.filter_by(admin_id=current_user.id).all()
    return render_template('propostas/nova.html', clientes=clientes)

@propostas_bp.route('/criar', methods=['POST'])
@login_required
def criar_proposta():
    """Criar nova proposta com dados do formulário"""
    try:
        # Dados do formulário
        cliente_id = request.form.get('cliente_id')
        titulo = request.form.get('titulo')
        descricao = request.form.get('descricao')
        valor_total = float(request.form.get('valor_total', 0))
        data_vencimento = datetime.strptime(request.form.get('data_vencimento'), '%Y-%m-%d')
        
        # Criar proposta
        proposta = Proposta(
            numero=gerar_numero_proposta(),
            cliente_id=cliente_id,
            titulo=titulo,
            descricao=descricao,
            valor_total=valor_total,
            data_vencimento=data_vencimento,
            status='rascunho',
            admin_id=current_user.id
        )
        
        db.session.add(proposta)
        db.session.commit()
        
        flash('Proposta criada com sucesso!', 'success')
        return redirect(url_for('propostas.visualizar', id=proposta.id))
        
    except Exception as e:
        db.session.rollback()
        flash(f'Erro ao criar proposta: {str(e)}', 'error')
        return redirect(url_for('propostas.nova_proposta'))

@propostas_bp.route('/listar')
@login_required
def listar_propostas():
    """Listar todas as propostas com filtros avançados"""
    
    # Filtros
    status_filter = request.args.get('status', '')
    cliente_filter = request.args.get('cliente', '')
    data_inicio = request.args.get('data_inicio', '')
    data_fim = request.args.get('data_fim', '')
    
    # Query base
    query = Proposta.query.filter_by(admin_id=current_user.id)
    
    # Aplicar filtros
    if status_filter:
        query = query.filter(Proposta.status == status_filter)
    
    if cliente_filter:
        query = query.filter(Proposta.cliente_id == cliente_filter)
    
    if data_inicio:
        query = query.filter(Proposta.created_at >= datetime.strptime(data_inicio, '%Y-%m-%d'))
    
    if data_fim:
        query = query.filter(Proposta.created_at <= datetime.strptime(data_fim, '%Y-%m-%d'))
    
    # Paginação
    page = request.args.get('page', 1, type=int)
    propostas = query.paginate(page=page, per_page=20, error_out=False)
    
    # Dados para filtros
    clientes = Cliente.query.filter_by(admin_id=current_user.id).all()
    
    return render_template('propostas/listar.html',
                         propostas=propostas,
                         clientes=clientes,
                         filtros={
                             'status': status_filter,
                             'cliente': cliente_filter,
                             'data_inicio': data_inicio,
                             'data_fim': data_fim
                         })

@propostas_bp.route('/visualizar/<int:id>')
@login_required
def visualizar(id):
    """Visualizar proposta específica com detalhes completos"""
    proposta = Proposta.query.filter_by(id=id, admin_id=current_user.id).first_or_404()
    
    # Histórico de ações na proposta
    historico = PropostaHistorico.query.filter_by(proposta_id=id).order_by(PropostaHistorico.created_at.desc()).all()
    
    return render_template('propostas/visualizar.html', 
                         proposta=proposta,
                         historico=historico)

@propostas_bp.route('/editar/<int:id>')
@login_required
def editar_proposta(id):
    """Formulário para editar proposta"""
    proposta = Proposta.query.filter_by(id=id, admin_id=current_user.id).first_or_404()
    clientes = Cliente.query.filter_by(admin_id=current_user.id).all()
    
    return render_template('propostas/editar.html', 
                         proposta=proposta,
                         clientes=clientes)

@propostas_bp.route('/atualizar/<int:id>', methods=['POST'])
@login_required
def atualizar_proposta(id):
    """Atualizar dados da proposta"""
    proposta = Proposta.query.filter_by(id=id, admin_id=current_user.id).first_or_404()
    
    try:
        # Salvar estado anterior para histórico
        estado_anterior = {
            'titulo': proposta.titulo,
            'descricao': proposta.descricao,
            'valor_total': proposta.valor_total
        }
        
        # Atualizar dados
        proposta.titulo = request.form.get('titulo')
        proposta.descricao = request.form.get('descricao')
        proposta.valor_total = float(request.form.get('valor_total', 0))
        proposta.data_vencimento = datetime.strptime(request.form.get('data_vencimento'), '%Y-%m-%d')
        
        db.session.commit()
        
        # Registrar no histórico
        registrar_historico(proposta.id, 'atualizada', f'Proposta atualizada por {current_user.nome}')
        
        flash('Proposta atualizada com sucesso!', 'success')
        return redirect(url_for('propostas.visualizar', id=id))
        
    except Exception as e:
        db.session.rollback()
        flash(f'Erro ao atualizar proposta: {str(e)}', 'error')
        return redirect(url_for('propostas.editar_proposta', id=id))

@propostas_bp.route('/enviar/<int:id>', methods=['POST'])
@login_required
def enviar_proposta(id):
    """Enviar proposta para cliente com múltiplos canais"""
    proposta = Proposta.query.filter_by(id=id, admin_id=current_user.id).first_or_404()
    
    try:
        # Atualizar status
        proposta.status = 'enviada'
        proposta.data_envio = datetime.now()
        
        # Gerar link único para visualização
        proposta.link_visualizacao = gerar_link_visualizacao()
        
        db.session.commit()
        
        # Enviar por email (implementar integração)
        enviar_email_proposta(proposta)
        
        # Enviar por WhatsApp se configurado
        if request.form.get('enviar_whatsapp'):
            enviar_whatsapp_proposta(proposta)
        
        # Registrar no histórico
        registrar_historico(proposta.id, 'enviada', f'Proposta enviada para {proposta.cliente.nome}')
        
        flash('Proposta enviada com sucesso!', 'success')
        return redirect(url_for('propostas.visualizar', id=id))
        
    except Exception as e:
        db.session.rollback()
        flash(f'Erro ao enviar proposta: {str(e)}', 'error')
        return redirect(url_for('propostas.visualizar', id=id))

@propostas_bp.route('/gerar-pdf/<int:id>')
@login_required
def gerar_pdf(id):
    """Gerar PDF profissional da proposta"""
    proposta = Proposta.query.filter_by(id=id, admin_id=current_user.id).first_or_404()
    
    # Implementar geração de PDF com ReportLab
    pdf_path = gerar_pdf_proposta(proposta)
    
    return send_file(pdf_path, as_attachment=True, 
                    download_name=f'Proposta_{proposta.numero}.pdf')

# Funções auxiliares
def gerar_numero_proposta():
    """Gerar número único para proposta"""
    from datetime import datetime
    timestamp = datetime.now().strftime('%Y%m%d%H%M%S')
    return f'PROP-{timestamp}'

def gerar_link_visualizacao():
    """Gerar link único para visualização da proposta"""
    return str(uuid.uuid4())

def registrar_historico(proposta_id, acao, descricao):
    """Registrar ação no histórico da proposta"""
    historico = PropostaHistorico(
        proposta_id=proposta_id,
        acao=acao,
        descricao=descricao,
        usuario_id=current_user.id
    )
    db.session.add(historico)
    db.session.commit()

def enviar_email_proposta(proposta):
    """Enviar proposta por email (integração externa)"""
    # Implementar integração com serviço de email
    pass

def enviar_whatsapp_proposta(proposta):
    """Enviar proposta por WhatsApp Business API"""
    # Implementar integração com WhatsApp Business
    pass

def gerar_pdf_proposta(proposta):
    """Gerar PDF profissional da proposta"""
    # Implementar geração de PDF com ReportLab
    pass