"""
MÓDULO 2 - PORTAL DO CLIENTE AVANÇADO
Sistema premium de transparência e comunicação com clientes
"""

from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify
from flask_login import login_required, current_user
from models import db, Cliente, Proposta, Obra, RDO, Usuario
from datetime import datetime, timedelta
import json
import base64
from werkzeug.utils import secure_filename
import os

# Blueprint para portal do cliente
cliente_portal_bp = Blueprint('cliente_portal', __name__, url_prefix='/cliente-portal')

@cliente_portal_bp.route('/dashboard/<string:codigo_acesso>')
def dashboard_cliente(codigo_acesso):
    """Dashboard executivo do cliente com acesso via código único"""
    
    # Verificar código de acesso (implementar lógica de segurança)
    cliente = verificar_codigo_acesso(codigo_acesso)
    if not cliente:
        flash('Código de acesso inválido', 'error')
        return redirect(url_for('main.index'))
    
    # Obras ativas do cliente
    obras_ativas = Obra.query.filter_by(cliente_id=cliente.id, status='em_andamento').all()
    
    # Propostas do cliente
    propostas = Proposta.query.filter_by(cliente_id=cliente.id).order_by(Proposta.created_at.desc()).limit(5).all()
    
    # Últimos RDOs das obras
    rdos_recentes = []
    for obra in obras_ativas:
        rdo = RDO.query.filter_by(obra_id=obra.id).order_by(RDO.data.desc()).first()
        if rdo:
            rdos_recentes.append(rdo)
    
    # Métricas de progresso
    progresso_total = 0
    valor_total_obras = 0
    for obra in obras_ativas:
        progresso_total += obra.percentual_concluido or 0
        valor_total_obras += obra.valor_total or 0
    
    progresso_medio = progresso_total / len(obras_ativas) if obras_ativas else 0
    
    return render_template('cliente_portal/dashboard.html',
                         cliente=cliente,
                         obras_ativas=obras_ativas,
                         propostas=propostas,
                         rdos_recentes=rdos_recentes,
                         progresso_medio=progresso_medio,
                         valor_total_obras=valor_total_obras)

@cliente_portal_bp.route('/obra/<int:obra_id>/detalhes/<string:codigo_acesso>')
def detalhes_obra(obra_id, codigo_acesso):
    """Detalhes completos de uma obra específica"""
    
    cliente = verificar_codigo_acesso(codigo_acesso)
    if not cliente:
        return redirect(url_for('main.index'))
    
    obra = Obra.query.filter_by(id=obra_id, cliente_id=cliente.id).first_or_404()
    
    # RDOs da obra com fotos
    rdos = RDO.query.filter_by(obra_id=obra_id).order_by(RDO.data.desc()).all()
    
    # Cronograma e marcos importantes
    marcos = obter_marcos_obra(obra)
    
    # Fotos organizadas por data
    fotos_por_data = organizar_fotos_por_data(obra)
    
    # Equipe alocada
    equipe = obter_equipe_obra(obra)
    
    return render_template('cliente_portal/detalhes_obra.html',
                         obra=obra,
                         rdos=rdos,
                         marcos=marcos,
                         fotos_por_data=fotos_por_data,
                         equipe=equipe,
                         codigo_acesso=codigo_acesso)

@cliente_portal_bp.route('/obra/<int:obra_id>/cronograma/<string:codigo_acesso>')
def cronograma_obra(obra_id, codigo_acesso):
    """Cronograma interativo da obra"""
    
    cliente = verificar_codigo_acesso(codigo_acesso)
    if not cliente:
        return redirect(url_for('main.index'))
    
    obra = Obra.query.filter_by(id=obra_id, cliente_id=cliente.id).first_or_404()
    
    # Gerar cronograma com marcos e previsões
    cronograma = gerar_cronograma_interativo(obra)
    
    return render_template('cliente_portal/cronograma.html',
                         obra=obra,
                         cronograma=cronograma,
                         codigo_acesso=codigo_acesso)

@cliente_portal_bp.route('/obra/<int:obra_id>/fotos/<string:codigo_acesso>')
def galeria_fotos(obra_id, codigo_acesso):
    """Galeria de fotos organizada e profissional"""
    
    cliente = verificar_codigo_acesso(codigo_acesso)
    if not cliente:
        return redirect(url_for('main.index'))
    
    obra = Obra.query.filter_by(id=obra_id, cliente_id=cliente.id).first_or_404()
    
    # Organizar fotos por categorias e datas
    fotos_organizadas = {
        'antes': obter_fotos_categoria(obra, 'antes'),
        'durante': obter_fotos_categoria(obra, 'durante'),
        'depois': obter_fotos_categoria(obra, 'depois'),
        'detalhes': obter_fotos_categoria(obra, 'detalhes')
    }
    
    return render_template('cliente_portal/galeria.html',
                         obra=obra,
                         fotos_organizadas=fotos_organizadas,
                         codigo_acesso=codigo_acesso)

@cliente_portal_bp.route('/obra/<int:obra_id>/relatorios/<string:codigo_acesso>')
def relatorios_obra(obra_id, codigo_acesso):
    """Relatórios de progresso em PDF"""
    
    cliente = verificar_codigo_acesso(codigo_acesso)
    if not cliente:
        return redirect(url_for('main.index'))
    
    obra = Obra.query.filter_by(id=obra_id, cliente_id=cliente.id).first_or_404()
    
    # Tipos de relatórios disponíveis
    tipos_relatorio = [
        {'nome': 'Progresso Semanal', 'tipo': 'semanal'},
        {'nome': 'Relatório Mensal', 'tipo': 'mensal'},
        {'nome': 'Relatório Financeiro', 'tipo': 'financeiro'},
        {'nome': 'Relatório de Qualidade', 'tipo': 'qualidade'}
    ]
    
    return render_template('cliente_portal/relatorios.html',
                         obra=obra,
                         tipos_relatorio=tipos_relatorio,
                         codigo_acesso=codigo_acesso)

@cliente_portal_bp.route('/obra/<int:obra_id>/chat/<string:codigo_acesso>')
def chat_obra(obra_id, codigo_acesso):
    """Chat em tempo real com a equipe"""
    
    cliente = verificar_codigo_acesso(codigo_acesso)
    if not cliente:
        return redirect(url_for('main.index'))
    
    obra = Obra.query.filter_by(id=obra_id, cliente_id=cliente.id).first_or_404()
    
    # Mensagens do chat
    mensagens = obter_mensagens_chat(obra)
    
    return render_template('cliente_portal/chat.html',
                         obra=obra,
                         mensagens=mensagens,
                         codigo_acesso=codigo_acesso)

@cliente_portal_bp.route('/api/enviar-mensagem', methods=['POST'])
def enviar_mensagem():
    """API para enviar mensagem no chat"""
    
    data = request.get_json()
    obra_id = data.get('obra_id')
    codigo_acesso = data.get('codigo_acesso')
    mensagem = data.get('mensagem')
    
    cliente = verificar_codigo_acesso(codigo_acesso)
    if not cliente:
        return jsonify({'success': False, 'message': 'Acesso negado'})
    
    # Salvar mensagem no banco
    salvar_mensagem_chat(obra_id, cliente.id, mensagem, 'cliente')
    
    # Notificar equipe (WebSocket/email)
    notificar_equipe_nova_mensagem(obra_id, mensagem)
    
    return jsonify({'success': True})

@cliente_portal_bp.route('/obra/<int:obra_id>/avaliacao/<string:codigo_acesso>')
def avaliacao_servico(obra_id, codigo_acesso):
    """Sistema de avaliação do serviço"""
    
    cliente = verificar_codigo_acesso(codigo_acesso)
    if not cliente:
        return redirect(url_for('main.index'))
    
    obra = Obra.query.filter_by(id=obra_id, cliente_id=cliente.id).first_or_404()
    
    return render_template('cliente_portal/avaliacao.html',
                         obra=obra,
                         codigo_acesso=codigo_acesso)

@cliente_portal_bp.route('/obra/<int:obra_id>/solicitar-servico/<string:codigo_acesso>')
def solicitar_servico_adicional(obra_id, codigo_acesso):
    """Solicitação de serviços adicionais"""
    
    cliente = verificar_codigo_acesso(codigo_acesso)
    if not cliente:
        return redirect(url_for('main.index'))
    
    obra = Obra.query.filter_by(id=obra_id, cliente_id=cliente.id).first_or_404()
    
    return render_template('cliente_portal/solicitar_servico.html',
                         obra=obra,
                         codigo_acesso=codigo_acesso)

# Funções auxiliares
def verificar_codigo_acesso(codigo):
    """Verificar se o código de acesso é válido"""
    # Implementar lógica de verificação segura
    try:
        # Decodificar e validar o código
        cliente_id = base64.b64decode(codigo.encode()).decode()
        return Cliente.query.get(int(cliente_id))
    except:
        return None

def gerar_codigo_acesso(cliente_id):
    """Gerar código de acesso único para o cliente"""
    codigo = base64.b64encode(str(cliente_id).encode()).decode()
    return codigo

def obter_marcos_obra(obra):
    """Obter marcos importantes da obra"""
    marcos = [
        {'nome': 'Início da Obra', 'data': obra.data_inicio, 'status': 'concluido'},
        {'nome': 'Fundação', 'data': obra.data_inicio + timedelta(days=15), 'status': 'concluido'},
        {'nome': 'Estrutura', 'data': obra.data_inicio + timedelta(days=45), 'status': 'em_andamento'},
        {'nome': 'Cobertura', 'data': obra.data_inicio + timedelta(days=75), 'status': 'pendente'},
        {'nome': 'Acabamento', 'data': obra.data_inicio + timedelta(days=105), 'status': 'pendente'},
        {'nome': 'Entrega', 'data': obra.data_fim_prevista, 'status': 'pendente'}
    ]
    return marcos

def organizar_fotos_por_data(obra):
    """Organizar fotos da obra por data"""
    # Implementar lógica para organizar fotos
    return {}

def obter_equipe_obra(obra):
    """Obter equipe alocada na obra"""
    # Implementar consulta de alocação de equipe
    return []

def gerar_cronograma_interativo(obra):
    """Gerar dados para cronograma interativo"""
    # Implementar geração de cronograma
    return {}

def obter_fotos_categoria(obra, categoria):
    """Obter fotos por categoria"""
    # Implementar busca de fotos por categoria
    return []

def obter_mensagens_chat(obra):
    """Obter mensagens do chat da obra"""
    # Implementar busca de mensagens
    return []

def salvar_mensagem_chat(obra_id, remetente_id, mensagem, tipo):
    """Salvar mensagem no chat"""
    # Implementar salvamento de mensagem
    pass

def notificar_equipe_nova_mensagem(obra_id, mensagem):
    """Notificar equipe sobre nova mensagem"""
    # Implementar notificação (WebSocket/email)
    pass