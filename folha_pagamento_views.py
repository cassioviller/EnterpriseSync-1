"""
Views para o Módulo 6 - Sistema de Folha de Pagamento Automática
Versão limpa e funcional
"""

from flask import Blueprint, render_template, request, jsonify, redirect, url_for, flash
from flask_login import login_required, current_user
from datetime import datetime, date, timedelta
import calendar

folha_bp = Blueprint('folha', __name__)

def admin_required(f):
    """Decorator simples para admin - implementação temporária"""
    from functools import wraps
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not current_user.is_authenticated:
            return redirect(url_for('main.login'))
        # Verificação simplificada para Admin
        if hasattr(current_user, 'tipo_usuario') and current_user.tipo_usuario and current_user.tipo_usuario.name in ['ADMIN', 'SUPER_ADMIN']:
            return f(*args, **kwargs)
        flash('Acesso negado. Apenas administradores podem acessar esta página.', 'error')
        return redirect(url_for('main.dashboard'))
    return decorated_function

# ================================
# DASHBOARD PRINCIPAL
# ================================

@folha_bp.route('/dashboard')
@admin_required
def dashboard():
    """Dashboard principal da folha de pagamento"""
    
    # Importar modelos e db dentro da função para evitar importação circular
    from models import FolhaPagamento, Funcionario, ParametrosLegais
    from app import db
    
    # Mês atual
    hoje = date.today()
    mes_atual = hoje.replace(day=1)
    
    # Obter folhas do mês atual
    folhas_mes = FolhaPagamento.query.filter_by(
        admin_id=current_user.id,
        mes_referencia=mes_atual
    ).all()
    
    # Calcular métricas
    total_folha = sum(f.total_proventos or 0 for f in folhas_mes)
    total_liquido = sum(f.salario_liquido or 0 for f in folhas_mes)
    total_encargos = sum((f.inss or 0) + (f.fgts or 0) for f in folhas_mes)
    
    # Mês anterior para comparação
    mes_anterior = (mes_atual - timedelta(days=1)).replace(day=1)
    folhas_anterior = FolhaPagamento.query.filter_by(
        admin_id=current_user.id,
        mes_referencia=mes_anterior
    ).all()
    
    total_anterior = sum(f.total_proventos or 0 for f in folhas_anterior)
    variacao = ((total_folha - total_anterior) / total_anterior * 100) if total_anterior > 0 else 0
    
    # Status do processamento
    funcionarios_ativos = Funcionario.query.filter_by(
        admin_id=current_user.id,
        ativo=True
    ).count()
    
    folhas_processadas = len(folhas_mes)
    percentual_processado = (folhas_processadas / funcionarios_ativos * 100) if funcionarios_ativos > 0 else 0
    
    # Top 5 maiores salários
    top_salarios = sorted(folhas_mes, key=lambda x: x.total_proventos or 0, reverse=True)[:5]
    
    # Funcionários com mais horas extras
    top_extras = sorted(folhas_mes, key=lambda x: x.horas_extras or 0, reverse=True)[:5]
    
    # Verificar se parâmetros legais estão configurados
    parametros = ParametrosLegais.query.filter_by(
        admin_id=current_user.id,
        ano_vigencia=hoje.year,
        ativo=True
    ).first()
    
    parametros_configurados = parametros is not None
    if not parametros_configurados:
        flash('Parâmetros legais não configurados para este ano. Configure antes de processar a folha.', 'warning')
    
    return render_template('folha_pagamento/dashboard.html',
                         mes_referencia=mes_atual,
                         total_folha=total_folha,
                         total_liquido=total_liquido,
                         total_encargos=total_encargos,
                         variacao=variacao,
                         funcionarios_ativos=funcionarios_ativos,
                         folhas_processadas=folhas_processadas,
                         percentual_processado=percentual_processado,
                         top_salarios=top_salarios,
                         top_extras=top_extras,
                         parametros_configurados=parametros_configurados)

# ================================
# PROCESSAMENTO DA FOLHA
# ================================

@folha_bp.route('/processar/<int:ano>/<int:mes>', methods=['POST'])
@admin_required
def processar_folha_mes(ano, mes):
    """Processar folha de pagamento do mês"""
    
    try:
        from models import FolhaPagamento
        from app import db
        
        mes_referencia = date(ano, mes, 1)
        
        # Verificar se já foi processada
        folhas_existentes = FolhaPagamento.query.filter_by(
            admin_id=current_user.id,
            mes_referencia=mes_referencia
        ).count()
        
        if folhas_existentes > 0:
            reprocessar = request.form.get('reprocessar') == 'true'
            if not reprocessar:
                flash('Folha já processada para este mês. Use a opção "Reprocessar" se necessário.', 'warning')
                return redirect(url_for('folha.dashboard'))
        
        flash('Folha de pagamento será processada em breve. Funcionalidade em desenvolvimento.', 'info')
        return redirect(url_for('folha.dashboard'))
        
    except Exception as e:
        flash(f'Erro ao processar folha: {str(e)}', 'danger')
        return redirect(url_for('folha.dashboard'))

# ================================
# ROTAS SIMPLIFICADAS
# ================================

@folha_bp.route('/configuracoes')
@admin_required
def listar_configuracoes():
    """Listar configurações salariais"""
    flash('Funcionalidade em desenvolvimento.', 'info')
    return redirect(url_for('folha.dashboard'))

@folha_bp.route('/beneficios')
@admin_required
def listar_beneficios():
    """Listar benefícios dos funcionários"""
    flash('Funcionalidade em desenvolvimento.', 'info')
    return redirect(url_for('folha.dashboard'))

@folha_bp.route('/adiantamentos')
@admin_required
def listar_adiantamentos():
    """Listar adiantamentos"""
    flash('Funcionalidade em desenvolvimento.', 'info')
    return redirect(url_for('folha.dashboard'))

@folha_bp.route('/relatorios')
@admin_required
def relatorios():
    """Relatórios da folha de pagamento"""
    flash('Funcionalidade em desenvolvimento.', 'info')
    return redirect(url_for('folha.dashboard'))

@folha_bp.route('/parametros-legais')
@admin_required
def parametros_legais():
    """Configurar parâmetros legais"""
    flash('Funcionalidade em desenvolvimento.', 'info')
    return redirect(url_for('folha.dashboard'))