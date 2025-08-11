from models import db
"""
Views para o Módulo 7 - Sistema Contábil Completo
"""

from flask import Blueprint, render_template, request, jsonify, redirect, url_for, flash
    from models import SpedContabil
from flask_login import login_required, current_user
from datetime import datetime, date, timedelta
import calendar

contabilidade_bp = Blueprint('contabilidade', __name__)

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

@contabilidade_bp.route('/dashboard')
@admin_required
def dashboard_contabil():
    """Dashboard principal da contabilidade"""
    from contabilidade_utils import calcular_saldo_conta
    
    hoje = date.today()
    mes_atual = hoje.replace(day=1)
    
    # Buscar DRE do mês atual
    dre_atual = DREMensal.query.filter_by(
        admin_id=current_user.id,
        mes_referencia=mes_atual
    ).first()
    
    # Buscar último balanço
    balanco_atual = BalancoPatrimonial.query.filter_by(
        admin_id=current_user.id
    ).order_by(BalancoPatrimonial.data_referencia.desc()).first()
    
    # Estatísticas rápidas
    total_lancamentos = LancamentoContabil.query.filter_by(admin_id=current_user.id).count()
    
    # Saldos principais
    saldo_caixa = calcular_saldo_conta('1.1.01.001', current_user.id)
    saldo_bancos = calcular_saldo_conta('1.1.01.002', current_user.id)
    saldo_clientes = calcular_saldo_conta('1.1.02.001', current_user.id)
    
    return render_template('contabilidade/dashboard.html',
                         dre_atual=dre_atual,
                         balanco_atual=balanco_atual,
                         total_lancamentos=total_lancamentos,
                         saldo_caixa=saldo_caixa,
                         saldo_bancos=saldo_bancos,
                         saldo_clientes=saldo_clientes,
                         mes_atual=mes_atual)

@contabilidade_bp.route('/plano-contas')
@admin_required
def plano_de_contas():
    """Exibir plano de contas"""
    from contabilidade_utils import criar_plano_contas_padrao
    
    # Criar plano de contas se não existir
    if not PlanoContas.query.filter_by(admin_id=current_user.id).first():
        criar_plano_contas_padrao(current_user.id)
        flash('Plano de contas padrão criado automaticamente.', 'success')
    
    contas = PlanoContas.query.filter_by(admin_id=current_user.id).order_by(PlanoContas.codigo).all()
    
    return render_template('contabilidade/plano_contas.html',
                         contas=contas)

@contabilidade_bp.route('/lancamentos')
@admin_required
def lancamentos_contabeis():
    """Listar lançamentos contábeis"""
    
    page = request.args.get('page', 1, type=int)
    per_page = 20
    
    lancamentos = LancamentoContabil.query.filter_by(admin_id=current_user.id)\
                                       .order_by(LancamentoContabil.data_lancamento.desc(), 
                                               LancamentoContabil.numero.desc())\
                                       .paginate(page=page, per_page=per_page, error_out=False)
    
    return render_template('contabilidade/lancamentos.html',
                         lancamentos=lancamentos)

@contabilidade_bp.route('/balancete')
@admin_required
def balancete():
    """Visualizar balancete mensal"""
    from contabilidade_utils import gerar_balancete_mensal
    
    # Obter mês/ano dos parâmetros ou usar atual
    mes = request.args.get('mes', date.today().month, type=int)
    ano = request.args.get('ano', date.today().year, type=int)
    
    mes_referencia = date(ano, mes, 1)
    
    # Gerar balancete se não existir
    balancetes_existentes = BalanceteMensal.query.filter_by(
        admin_id=current_user.id,
        mes_referencia=mes_referencia
    ).count()
    
    if balancetes_existentes == 0:
        try:
            gerar_balancete_mensal(current_user.id, mes_referencia)
            flash('Balancete gerado automaticamente.', 'success')
        except Exception as e:
            flash(f'Erro ao gerar balancete: {str(e)}', 'error')
    
    balancetes = BalanceteMensal.query.filter_by(
        admin_id=current_user.id,
        mes_referencia=mes_referencia
    ).join('conta').order_by('PlanoContas.codigo').all()
    
    return render_template('contabilidade/balancete.html',
                         balancetes=balancetes,
                         mes_referencia=mes_referencia)

@contabilidade_bp.route('/dre')
@admin_required
def dre():
    """Demonstração do Resultado do Exercício"""
    
    mes = request.args.get('mes', date.today().month, type=int)
    ano = request.args.get('ano', date.today().year, type=int)
    
    mes_referencia = date(ano, mes, 1)
    
    dre = DREMensal.query.filter_by(
        admin_id=current_user.id,
        mes_referencia=mes_referencia
    ).first()
    
    if not dre:
        # Criar DRE básica se não existir
        dre = DREMensal(
            mes_referencia=mes_referencia,
            admin_id=current_user.id
        )
        db.session.add(dre)
        db.session.commit()
        flash('DRE criada automaticamente. Configure os valores conforme necessário.', 'info')
    
    return render_template('contabilidade/dre.html',
                         dre=dre,
                         mes_referencia=mes_referencia)

@contabilidade_bp.route('/balanco-patrimonial')
@admin_required
def balanco_patrimonial():
    """Balanço Patrimonial"""
    
    data_ref = request.args.get('data', date.today().isoformat())
    data_referencia = datetime.strptime(data_ref, '%Y-%m-%d').date()
    
    balanco = BalancoPatrimonial.query.filter_by(
        admin_id=current_user.id,
        data_referencia=data_referencia
    ).first()
    
    if not balanco:
        # Criar balanço básico se não existir
        balanco = BalancoPatrimonial(
            data_referencia=data_referencia,
            admin_id=current_user.id
        )
        db.session.add(balanco)
        db.session.commit()
        flash('Balanço Patrimonial criado automaticamente.', 'info')
    
    return render_template('contabilidade/balanco.html',
                         balanco=balanco,
                         data_referencia=data_referencia)

@contabilidade_bp.route('/auditoria')
@admin_required
def auditoria_contabil():
    """Sistema de auditoria contábil"""
    from contabilidade_utils import executar_auditoria_automatica
    
    # Executar auditoria se solicitado
    if request.args.get('executar') == '1':
        try:
            alertas = executar_auditoria_automatica(current_user.id)
            flash(f'Auditoria executada. {len(alertas)} alertas encontrados.', 'info')
        except Exception as e:
            flash(f'Erro na auditoria: {str(e)}', 'error')
    
    # Buscar alertas não corrigidos
    alertas = AuditoriaContabil.query.filter_by(
        admin_id=current_user.id,
        corrigido=False
    ).order_by(AuditoriaContabil.data_auditoria.desc()).all()
    
    return render_template('contabilidade/auditoria.html',
                         alertas=alertas)

@contabilidade_bp.route('/relatorios')
@admin_required
def relatorios():
    """Central de relatórios contábeis"""
    flash('Central de relatórios em desenvolvimento.', 'info')
    return render_template('contabilidade/relatorios.html')

@contabilidade_bp.route('/sped')
@admin_required
def sped():
    """Geração de SPED Contábil"""
    
    speds = SpedContabil.query.filter_by(admin_id=current_user.id)\
                             .order_by(SpedContabil.data_geracao.desc()).all()
    
    return render_template('contabilidade/sped.html',
                         speds=speds)

# APIs para integração

@contabilidade_bp.route('/api/processar-integracao', methods=['POST'])
@admin_required
def processar_integracao():
    """API para processar integrações automáticas"""
    from contabilidade_utils import (contabilizar_proposta_aprovada, 
                                   contabilizar_entrada_material, 
                                   contabilizar_folha_pagamento)
    
    try:
        tipo = request.json.get('tipo')
        origem_id = request.json.get('origem_id')
        
        if tipo == 'proposta_aprovada':
            contabilizar_proposta_aprovada(origem_id)
        elif tipo == 'entrada_material':
            contabilizar_entrada_material(origem_id)
        elif tipo == 'folha_pagamento':
            mes_ref = datetime.strptime(request.json.get('mes_referencia'), '%Y-%m-%d').date()
            contabilizar_folha_pagamento(current_user.id, mes_ref)
        
        return jsonify({'success': True, 'message': 'Integração processada com sucesso'})
    
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)}), 400