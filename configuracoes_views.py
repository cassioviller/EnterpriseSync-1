"""
Blueprint para configurações da empresa
"""
from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify
from flask_login import login_required, current_user
from app import db
from models import ConfiguracaoEmpresa, Departamento, Funcao, HorarioTrabalho, Funcionario
from decorators import admin_required
from datetime import datetime, time

configuracoes_bp = Blueprint('configuracoes', __name__, url_prefix='/configuracoes')

@configuracoes_bp.route('/')
@login_required
@admin_required
def configuracoes():
    """Página principal de configurações da empresa"""
    from multitenant_helper import get_admin_id
    admin_id = get_admin_id()
    config = ConfiguracaoEmpresa.query.filter_by(admin_id=admin_id).first()
    return render_template('configuracoes/index.html', config=config)

@configuracoes_bp.route('/empresa')
@login_required
@admin_required
def empresa():
    """Configurações da empresa"""
    from multitenant_helper import get_admin_id
    admin_id = get_admin_id()
    
    print(f"DEBUG EMPRESA: user.id={current_user.id}, admin_id={admin_id}")
    config = ConfiguracaoEmpresa.query.filter_by(admin_id=admin_id).first()
    print(f"DEBUG EMPRESA: config encontrada={config is not None}")
    if config:
        print(f"DEBUG EMPRESA: nome_empresa={config.nome_empresa}")
    
    return render_template('configuracoes/empresa.html', config=config)

@configuracoes_bp.route('/empresa/salvar', methods=['POST'])
@login_required
@admin_required
def salvar_empresa():
    """Salva configurações da empresa"""
    try:
        from multitenant_helper import get_admin_id
        admin_id = get_admin_id()
            
        print(f"DEBUG SALVAR: user.id={current_user.id}, admin_id={admin_id}, tipo={getattr(current_user, 'tipo_usuario', 'N/A')}")
        
        config = ConfiguracaoEmpresa.query.filter_by(admin_id=admin_id).first()
        print(f"DEBUG SALVAR: config existente = {config is not None}")
        
        if not config:
            config = ConfiguracaoEmpresa()
            config.admin_id = admin_id
        
        config.nome_empresa = request.form.get('nome_empresa')
        config.cnpj = request.form.get('cnpj')
        config.endereco = request.form.get('endereco')
        config.telefone = request.form.get('telefone')
        config.email = request.form.get('email')
        config.website = request.form.get('website')
        
        logo_base64 = request.form.get('logo_base64')
        if logo_base64 and logo_base64.strip():
            config.logo_base64 = logo_base64
            print("DEBUG LOGO: Logo base64 salva")
        elif request.form.get('clear_logo') == 'true':
            config.logo_base64 = None
            print("DEBUG LOGO: Logo base64 removida")
            
        logo_pdf_base64 = request.form.get('logo_pdf_base64')
        if logo_pdf_base64 and logo_pdf_base64.strip():
            config.logo_pdf_base64 = logo_pdf_base64
            print("DEBUG LOGO PDF: Logo PDF base64 salva")
        elif request.form.get('clear_logo_pdf') == 'true':
            config.logo_pdf_base64 = None
            print("DEBUG LOGO PDF: Logo PDF base64 removida")
            
        header_pdf_base64 = request.form.get('header_pdf_base64', '').strip()
        clear_header = request.form.get('clear_header_pdf', '').strip()
        
        print(f"DEBUG HEADER: Campo header_pdf_base64 = {len(header_pdf_base64) if header_pdf_base64 else 0} chars")
        print(f"DEBUG HEADER: Campo clear_header_pdf = '{clear_header}'")
        print(f"DEBUG HEADER: Todos os campos do form: {list(request.form.keys())}")
        
        if clear_header == 'true':
            config.header_pdf_base64 = None
            print("DEBUG HEADER: ✅ Header PDF removido com sucesso")
        elif header_pdf_base64 and len(header_pdf_base64) > 100:
            config.header_pdf_base64 = header_pdf_base64
            print(f"DEBUG HEADER: ✅ Header PDF salvo com sucesso ({len(header_pdf_base64)} chars)")
        else:
            print(f"DEBUG HEADER: ⚠️ Nenhuma ação realizada (header vazio ou inválido)")
        
        cor_primaria = request.form.get('cor_primaria', '#007bff')
        cor_secundaria = request.form.get('cor_secundaria', '#6c757d') 
        cor_fundo = request.form.get('cor_fundo_proposta', '#f8f9fa')
        
        config.cor_primaria = cor_primaria
        config.cor_secundaria = cor_secundaria
        config.cor_fundo_proposta = cor_fundo
        
        print(f"DEBUG CORES: primaria={cor_primaria}, secundaria={cor_secundaria}, fundo={cor_fundo}")
        
        config.itens_inclusos_padrao = request.form.get('itens_inclusos_padrao')
        config.itens_exclusos_padrao = request.form.get('itens_exclusos_padrao')
        config.condicoes_padrao = request.form.get('condicoes_padrao')
        config.condicoes_pagamento_padrao = request.form.get('condicoes_pagamento_padrao')
        config.garantias_padrao = request.form.get('garantias_padrao')
        config.observacoes_gerais_padrao = request.form.get('observacoes_gerais_padrao')
        
        config.prazo_entrega_padrao = int(request.form.get('prazo_entrega_padrao', 90))
        config.validade_padrao = int(request.form.get('validade_padrao', 7))
        config.percentual_nota_fiscal_padrao = float(request.form.get('percentual_nota_fiscal_padrao', 13.5))
        
        config.atualizado_em = datetime.utcnow()
        
        print(f"DEBUG: Salvando config para admin_id {admin_id}")
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


# ==================== DEPARTAMENTOS ====================

@configuracoes_bp.route('/departamentos')
@login_required
@admin_required
def departamentos():
    """Listar departamentos"""
    departamentos = Departamento.query.all()
    return render_template('configuracoes/departamentos.html', departamentos=departamentos)

@configuracoes_bp.route('/departamentos/criar', methods=['GET', 'POST'])
@login_required
@admin_required
def criar_departamento():
    """Criar departamento"""
    if request.method == 'POST':
        try:
            dept = Departamento(
                nome=request.form['nome'],
                descricao=request.form.get('descricao')
            )
            db.session.add(dept)
            db.session.commit()
            flash('Departamento criado com sucesso!', 'success')
            return redirect(url_for('configuracoes.departamentos'))
        except Exception as e:
            db.session.rollback()
            flash(f'Erro ao criar departamento: {str(e)}', 'danger')
    
    return render_template('configuracoes/departamento_form.html', departamento=None)

@configuracoes_bp.route('/departamentos/editar/<int:id>', methods=['GET', 'POST'])
@login_required
@admin_required
def editar_departamento(id):
    """Editar departamento"""
    dept = Departamento.query.get_or_404(id)
    
    if request.method == 'POST':
        try:
            dept.nome = request.form['nome']
            dept.descricao = request.form.get('descricao')
            db.session.commit()
            flash('Departamento atualizado com sucesso!', 'success')
            return redirect(url_for('configuracoes.departamentos'))
        except Exception as e:
            db.session.rollback()
            flash(f'Erro ao atualizar departamento: {str(e)}', 'danger')
    
    return render_template('configuracoes/departamento_form.html', departamento=dept)

@configuracoes_bp.route('/departamentos/deletar/<int:id>', methods=['POST'])
@login_required
@admin_required
def deletar_departamento(id):
    """Deletar departamento"""
    try:
        dept = Departamento.query.get_or_404(id)
        db.session.delete(dept)
        db.session.commit()
        flash('Departamento deletado com sucesso!', 'success')
    except Exception as e:
        db.session.rollback()
        flash(f'Erro ao deletar departamento: {str(e)}', 'danger')
    
    return redirect(url_for('configuracoes.departamentos'))


# ==================== FUNÇÕES ====================

@configuracoes_bp.route('/funcoes')
@login_required
@admin_required
def funcoes():
    """Listar funções"""
    funcoes = Funcao.query.all()
    return render_template('configuracoes/funcoes.html', funcoes=funcoes)

@configuracoes_bp.route('/funcoes/criar', methods=['GET', 'POST'])
@login_required
@admin_required
def criar_funcao():
    """Criar função"""
    if request.method == 'POST':
        try:
            funcao = Funcao(
                nome=request.form['nome'],
                descricao=request.form.get('descricao'),
                salario_base=float(request.form.get('salario_base', 0))
            )
            db.session.add(funcao)
            db.session.commit()
            flash('Função criada com sucesso!', 'success')
            return redirect(url_for('configuracoes.funcoes'))
        except Exception as e:
            db.session.rollback()
            flash(f'Erro ao criar função: {str(e)}', 'danger')
    
    return render_template('configuracoes/funcao_form.html', funcao=None)

@configuracoes_bp.route('/funcoes/editar/<int:id>', methods=['GET', 'POST'])
@login_required
@admin_required
def editar_funcao(id):
    """Editar função"""
    funcao = Funcao.query.get_or_404(id)
    
    if request.method == 'POST':
        try:
            # Capturar salário base antigo para comparação
            salario_base_antigo = funcao.salario_base
            
            # Atualizar dados da função
            funcao.nome = request.form['nome']
            funcao.descricao = request.form.get('descricao')
            novo_salario_base = float(request.form.get('salario_base', 0))
            funcao.salario_base = novo_salario_base
            
            # ATUALIZAÇÃO EM MASSA: Se salário base mudou, atualizar todos funcionários
            funcionarios_atualizados = 0
            if salario_base_antigo != novo_salario_base:
                # Buscar todos os funcionários com essa função (FILTRADO POR TENANT)
                from multitenant_helper import get_admin_id
                admin_id = get_admin_id()
                funcionarios = Funcionario.query.filter_by(
                    funcao_id=id, 
                    admin_id=admin_id
                ).all()
                
                # Atualizar salário de cada funcionário
                for funcionario in funcionarios:
                    funcionario.salario = novo_salario_base
                    funcionarios_atualizados += 1
                
                # Log da operação
                print(f"ATUALIZAÇÃO MASSA SALARIAL: Função '{funcao.nome}' (ID {id})")
                print(f"  Salário base: R$ {salario_base_antigo:.2f} → R$ {novo_salario_base:.2f}")
                print(f"  Funcionários atualizados: {funcionarios_atualizados}")
            
            # Commit da transação (atômica - tudo ou nada)
            db.session.commit()
            
            # Mensagem de sucesso informativa
            if funcionarios_atualizados > 0:
                flash(f'Função atualizada com sucesso! {funcionarios_atualizados} funcionário(s) tiveram seus salários atualizados automaticamente.', 'success')
            else:
                flash('Função atualizada com sucesso!', 'success')
                
            return redirect(url_for('configuracoes.funcoes'))
        except Exception as e:
            db.session.rollback()
            flash(f'Erro ao atualizar função: {str(e)}', 'danger')
    
    return render_template('configuracoes/funcao_form.html', funcao=funcao)

@configuracoes_bp.route('/funcoes/deletar/<int:id>', methods=['POST'])
@login_required
@admin_required
def deletar_funcao(id):
    """Deletar função"""
    try:
        funcao = Funcao.query.get_or_404(id)
        db.session.delete(funcao)
        db.session.commit()
        flash('Função deletada com sucesso!', 'success')
    except Exception as e:
        db.session.rollback()
        flash(f'Erro ao deletar função: {str(e)}', 'danger')
    
    return redirect(url_for('configuracoes.funcoes'))


# ==================== HORÁRIOS ====================

@configuracoes_bp.route('/horarios')
@login_required
@admin_required
def horarios():
    """Listar horários de trabalho"""
    horarios = HorarioTrabalho.query.all()
    return render_template('configuracoes/horarios.html', horarios=horarios)

@configuracoes_bp.route('/horarios/criar', methods=['GET', 'POST'])
@login_required
@admin_required
def criar_horario():
    """Criar horário de trabalho"""
    if request.method == 'POST':
        try:
            horario = HorarioTrabalho(
                nome=request.form['nome'],
                entrada=datetime.strptime(request.form['entrada'], '%H:%M').time(),
                saida_almoco=datetime.strptime(request.form['saida_almoco'], '%H:%M').time(),
                retorno_almoco=datetime.strptime(request.form['retorno_almoco'], '%H:%M').time(),
                saida=datetime.strptime(request.form['saida'], '%H:%M').time(),
                dias_semana=request.form['dias_semana'],
                horas_diarias=float(request.form.get('horas_diarias', 8.0)),
                valor_hora=float(request.form.get('valor_hora', 12.0))
            )
            db.session.add(horario)
            db.session.commit()
            flash('Horário criado com sucesso!', 'success')
            return redirect(url_for('configuracoes.horarios'))
        except Exception as e:
            db.session.rollback()
            flash(f'Erro ao criar horário: {str(e)}', 'danger')
    
    return render_template('configuracoes/horario_form.html', horario=None)

@configuracoes_bp.route('/horarios/editar/<int:id>', methods=['GET', 'POST'])
@login_required
@admin_required
def editar_horario(id):
    """Editar horário de trabalho"""
    horario = HorarioTrabalho.query.get_or_404(id)
    
    if request.method == 'POST':
        try:
            horario.nome = request.form['nome']
            horario.entrada = datetime.strptime(request.form['entrada'], '%H:%M').time()
            horario.saida_almoco = datetime.strptime(request.form['saida_almoco'], '%H:%M').time()
            horario.retorno_almoco = datetime.strptime(request.form['retorno_almoco'], '%H:%M').time()
            horario.saida = datetime.strptime(request.form['saida'], '%H:%M').time()
            horario.dias_semana = request.form['dias_semana']
            horario.horas_diarias = float(request.form.get('horas_diarias', 8.0))
            horario.valor_hora = float(request.form.get('valor_hora', 12.0))
            db.session.commit()
            flash('Horário atualizado com sucesso!', 'success')
            return redirect(url_for('configuracoes.horarios'))
        except Exception as e:
            db.session.rollback()
            flash(f'Erro ao atualizar horário: {str(e)}', 'danger')
    
    return render_template('configuracoes/horario_form.html', horario=horario)

@configuracoes_bp.route('/horarios/deletar/<int:id>', methods=['POST'])
@login_required
@admin_required
def deletar_horario(id):
    """Deletar horário de trabalho"""
    try:
        horario = HorarioTrabalho.query.get_or_404(id)
        db.session.delete(horario)
        db.session.commit()
        flash('Horário deletado com sucesso!', 'success')
    except Exception as e:
        db.session.rollback()
        flash(f'Erro ao deletar horário: {str(e)}', 'danger')
    
    return redirect(url_for('configuracoes.horarios'))
