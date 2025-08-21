"""
Blueprint para configurações da empresa
"""
from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify
from flask_login import login_required, current_user
from app import db
from models import ConfiguracaoEmpresa
from decorators import admin_required
from datetime import datetime

configuracoes_bp = Blueprint('configuracoes', __name__, url_prefix='/configuracoes')

@configuracoes_bp.route('/')
@login_required
@admin_required
def configuracoes():
    """Página principal de configurações da empresa"""
    admin_id = getattr(current_user, 'admin_id', None) or current_user.id
    config = ConfiguracaoEmpresa.query.filter_by(admin_id=admin_id).first()
    return render_template('configuracoes/index.html', config=config)

@configuracoes_bp.route('/empresa')
@login_required
@admin_required
def empresa():
    """Configurações da empresa"""
    admin_id = getattr(current_user, 'admin_id', None) or current_user.id
    config = ConfiguracaoEmpresa.query.filter_by(admin_id=admin_id).first()
    return render_template('configuracoes/empresa.html', config=config)

@configuracoes_bp.route('/empresa/salvar', methods=['POST'])
@login_required
@admin_required
def salvar_empresa():
    """Salva configurações da empresa"""
    try:
        # Obter admin_id corretamente (para ADMIN usa o próprio ID, para SUPER_ADMIN pode ser diferente)
        admin_id = getattr(current_user, 'admin_id', None) or current_user.id
        print(f"DEBUG SALVAR: admin_id = {admin_id}, user.id = {current_user.id}")
        
        config = ConfiguracaoEmpresa.query.filter_by(admin_id=admin_id).first()
        print(f"DEBUG SALVAR: config existente = {config is not None}")
        
        # Usar merge() ao invés de add() para evitar conflitos
        if not config:
            config = ConfiguracaoEmpresa()
            config.admin_id = admin_id
        
        # Importante: não usar session.add() se o objeto já existe
        
        # Dados básicos da empresa
        config.nome_empresa = request.form.get('nome_empresa')
        config.cnpj = request.form.get('cnpj')
        config.endereco = request.form.get('endereco')
        config.telefone = request.form.get('telefone')
        config.email = request.form.get('email')
        config.website = request.form.get('website')
        
        # Upload de logo em base64
        logo_base64 = request.form.get('logo_base64')
        if logo_base64 and logo_base64.strip():
            config.logo_base64 = logo_base64
            print("DEBUG LOGO: Logo base64 salva")
        elif request.form.get('clear_logo') == 'true':
            config.logo_base64 = None
            print("DEBUG LOGO: Logo base64 removida")
            
        # Upload de logo PDF em base64
        logo_pdf_base64 = request.form.get('logo_pdf_base64')
        if logo_pdf_base64 and logo_pdf_base64.strip():
            config.logo_pdf_base64 = logo_pdf_base64
            print("DEBUG LOGO PDF: Logo PDF base64 salva")
        elif request.form.get('clear_logo_pdf') == 'true':
            config.logo_pdf_base64 = None
            print("DEBUG LOGO PDF: Logo PDF base64 removida")
            
        # Upload de header PDF em base64 - VERSÃO CORRIGIDA
        header_pdf_base64 = request.form.get('header_pdf_base64', '').strip()
        clear_header = request.form.get('clear_header_pdf', '').strip()
        
        print(f"DEBUG HEADER: Campo header_pdf_base64 = {len(header_pdf_base64) if header_pdf_base64 else 0} chars")
        print(f"DEBUG HEADER: Campo clear_header_pdf = '{clear_header}'")
        print(f"DEBUG HEADER: Todos os campos do form: {list(request.form.keys())}")
        
        # Se há comando para limpar
        if clear_header == 'true':
            config.header_pdf_base64 = None
            print("DEBUG HEADER: ✅ Header PDF removido com sucesso")
        # Se há dados para salvar
        elif header_pdf_base64 and len(header_pdf_base64) > 100:  # Base64 válido deve ter mais de 100 chars
            config.header_pdf_base64 = header_pdf_base64
            print(f"DEBUG HEADER: ✅ Header PDF salvo com sucesso ({len(header_pdf_base64)} chars)")
        else:
            print(f"DEBUG HEADER: ⚠️ Nenhuma ação realizada (header vazio ou inválido)")
        
        # Personalização visual
        cor_primaria = request.form.get('cor_primaria', '#007bff')
        cor_secundaria = request.form.get('cor_secundaria', '#6c757d') 
        cor_fundo = request.form.get('cor_fundo_proposta', '#f8f9fa')
        
        config.cor_primaria = cor_primaria
        config.cor_secundaria = cor_secundaria
        config.cor_fundo_proposta = cor_fundo
        
        print(f"DEBUG CORES: primaria={cor_primaria}, secundaria={cor_secundaria}, fundo={cor_fundo}")
        
        # Dados para propostas
        config.itens_inclusos_padrao = request.form.get('itens_inclusos_padrao')
        config.itens_exclusos_padrao = request.form.get('itens_exclusos_padrao')
        config.condicoes_padrao = request.form.get('condicoes_padrao')
        config.condicoes_pagamento_padrao = request.form.get('condicoes_pagamento_padrao')
        config.garantias_padrao = request.form.get('garantias_padrao')
        config.observacoes_gerais_padrao = request.form.get('observacoes_gerais_padrao')
        
        # Configurações padrão
        config.prazo_entrega_padrao = int(request.form.get('prazo_entrega_padrao', 90))
        config.validade_padrao = int(request.form.get('validade_padrao', 7))
        config.percentual_nota_fiscal_padrao = float(request.form.get('percentual_nota_fiscal_padrao', 13.5))
        
        config.atualizado_em = datetime.utcnow()
        
        print(f"DEBUG: Salvando config para admin_id {admin_id}")
        # Usar merge para evitar conflitos de foreign key
        config = db.session.merge(config)
        db.session.commit()
        print("DEBUG: Commit realizado com sucesso")
        flash('Configurações da empresa salvas com sucesso!', 'success')
        
    except Exception as e:
        db.session.rollback()
        flash(f'Erro ao salvar configurações: {str(e)}', 'error')
    
    return redirect(url_for('configuracoes.empresa'))

@configuracoes_bp.route('/api/empresa')
@login_required
def api_empresa():
    """API para obter configurações da empresa"""
    config = ConfiguracaoEmpresa.query.filter_by(admin_id=current_user.admin_id).first()
    
    if not config:
        return jsonify({
            'success': False,
            'message': 'Configurações não encontradas'
        })
    
    return jsonify({
        'success': True,
        'config': config.to_dict()
    })