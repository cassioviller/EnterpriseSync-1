"""
Views para o Módulo 6 - Sistema de Folha de Pagamento Automática
"""

from flask import Blueprint, render_template, request, jsonify, redirect, url_for, flash
from flask_login import login_required, current_user
from datetime import datetime, date, timedelta
from auth import admin_required
from models import *
from folha_pagamento_utils import *
from app import db
import calendar

folha_bp = Blueprint('folha', __name__, url_prefix='/folha-pagamento')

# ================================
# DASHBOARD PRINCIPAL
# ================================

@folha_bp.route('/')
@admin_required
def dashboard():
    """Dashboard principal da folha de pagamento"""
    
    # Mês atual
    hoje = date.today()
    mes_atual = hoje.replace(day=1)
    
    # Obter folhas do mês atual
    folhas_mes = FolhaPagamento.query.filter_by(
        admin_id=current_user.id,
        mes_referencia=mes_atual
    ).all()
    
    # Calcular métricas
    total_folha = sum(f.total_proventos for f in folhas_mes)
    total_liquido = sum(f.salario_liquido for f in folhas_mes)
    total_encargos = sum(f.inss + f.fgts for f in folhas_mes)
    
    # Mês anterior para comparação
    mes_anterior = (mes_atual - timedelta(days=1)).replace(day=1)
    folhas_anterior = FolhaPagamento.query.filter_by(
        admin_id=current_user.id,
        mes_referencia=mes_anterior
    ).all()
    
    total_anterior = sum(f.total_proventos for f in folhas_anterior)
    variacao = ((total_folha - total_anterior) / total_anterior * 100) if total_anterior > 0 else 0
    
    # Status do processamento
    funcionarios_ativos = Funcionario.query.filter_by(
        admin_id=current_user.id,
        ativo=True
    ).count()
    
    folhas_processadas = len(folhas_mes)
    percentual_processado = (folhas_processadas / funcionarios_ativos * 100) if funcionarios_ativos > 0 else 0
    
    # Top 5 maiores salários
    top_salarios = sorted(folhas_mes, key=lambda x: x.total_proventos, reverse=True)[:5]
    
    # Funcionários com mais horas extras
    top_extras = sorted(folhas_mes, key=lambda x: x.horas_extras, reverse=True)[:5]
    
    # Verificar se parâmetros legais estão configurados
    parametros = ParametrosLegais.query.filter_by(
        admin_id=current_user.id,
        ano_vigencia=hoje.year,
        ativo=True
    ).first()
    
    if not parametros:
        flash('Parâmetros legais não configurados para este ano. Configure antes de processar a folha.', 'warning')
    
    return render_template('folha_pagamento/dashboard.html',
                         total_folha=total_folha,
                         total_liquido=total_liquido,
                         total_encargos=total_encargos,
                         variacao=variacao,
                         funcionarios_ativos=funcionarios_ativos,
                         folhas_processadas=folhas_processadas,
                         percentual_processado=percentual_processado,
                         top_salarios=top_salarios,
                         top_extras=top_extras,
                         mes_referencia=mes_atual,
                         parametros_configurados=parametros is not None)

# ================================
# PROCESSAMENTO DA FOLHA
# ================================

@folha_bp.route('/processar/<int:ano>/<int:mes>', methods=['POST'])
@admin_required
def processar_folha_mes(ano, mes):
    """Processar folha de pagamento do mês"""
    
    try:
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
        
        # Processar folha
        resultados = processar_folha_mensal(current_user.id, mes_referencia)
        
        sucessos = [r for r in resultados if r['sucesso']]
        erros = [r for r in resultados if not r['sucesso']]
        
        if erros:
            flash(f'Folha processada com {len(sucessos)} sucessos e {len(erros)} erros.', 'warning')
            for erro in erros[:5]:  # Mostrar apenas os primeiros 5 erros
                flash(f"Erro em {erro['funcionario'].nome}: {erro['erro']}", 'danger')
        else:
            flash(f'Folha processada com sucesso! {len(sucessos)} funcionários processados.', 'success')
        
        return redirect(url_for('folha.listar_folhas', ano=ano, mes=mes))
        
    except Exception as e:
        flash(f'Erro ao processar folha: {str(e)}', 'danger')
        return redirect(url_for('folha.dashboard'))

@folha_bp.route('/listar/<int:ano>/<int:mes>')
@admin_required
def listar_folhas(ano, mes):
    """Listar folhas de pagamento do mês"""
    
    mes_referencia = date(ano, mes, 1)
    
    folhas = FolhaPagamento.query.filter_by(
        admin_id=current_user.id,
        mes_referencia=mes_referencia
    ).join(Funcionario).order_by(Funcionario.nome).all()
    
    # Calcular totais
    total_bruto = sum(f.total_proventos for f in folhas)
    total_descontos = sum(f.total_descontos for f in folhas)
    total_liquido = sum(f.salario_liquido for f in folhas)
    total_inss = sum(f.inss for f in folhas)
    total_fgts = sum(f.fgts for f in folhas)
    total_irrf = sum(f.irrf for f in folhas)
    
    mes_nome = calendar.month_name[mes]
    
    return render_template('folha_pagamento/listar.html',
                         folhas=folhas,
                         mes_referencia=mes_referencia,
                         mes_nome=mes_nome,
                         ano=ano,
                         mes=mes,
                         total_bruto=total_bruto,
                         total_descontos=total_descontos,
                         total_liquido=total_liquido,
                         total_inss=total_inss,
                         total_fgts=total_fgts,
                         total_irrf=total_irrf)

@folha_bp.route('/holerite/<int:funcionario_id>/<int:ano>/<int:mes>')
@admin_required
def visualizar_holerite(funcionario_id, ano, mes):
    """Visualizar holerite individual"""
    
    mes_referencia = date(ano, mes, 1)
    
    folha = FolhaPagamento.query.filter_by(
        funcionario_id=funcionario_id,
        mes_referencia=mes_referencia,
        admin_id=current_user.id
    ).first()
    
    if not folha:
        flash('Holerite não encontrado.', 'error')
        return redirect(url_for('folha.dashboard'))
    
    # Obter dados complementares
    calculo_horas = CalculoHorasMensal.query.filter_by(
        funcionario_id=funcionario_id,
        mes_referencia=mes_referencia
    ).first()
    
    config_salarial = obter_configuracao_salarial_vigente(funcionario_id, mes_referencia)
    
    mes_nome = calendar.month_name[mes]
    
    return render_template('folha_pagamento/holerite.html',
                         folha=folha,
                         calculo_horas=calculo_horas,
                         config_salarial=config_salarial,
                         mes_nome=mes_nome,
                         ano=ano,
                         mes=mes)

# ================================
# CONFIGURAÇÕES SALARIAIS
# ================================

@folha_bp.route('/configuracao-salarial')
@admin_required
def listar_configuracoes():
    """Listar configurações salariais"""
    
    configuracoes = ConfiguracaoSalarial.query.filter_by(
        admin_id=current_user.id,
        ativo=True
    ).join(Funcionario).order_by(Funcionario.nome).all()
    
    funcionarios_sem_config = Funcionario.query.filter_by(
        admin_id=current_user.id,
        ativo=True
    ).filter(
        ~Funcionario.id.in_(
            db.session.query(ConfiguracaoSalarial.funcionario_id).filter_by(
                admin_id=current_user.id,
                ativo=True
            )
        )
    ).all()
    
    return render_template('folha_pagamento/configuracoes.html',
                         configuracoes=configuracoes,
                         funcionarios_sem_config=funcionarios_sem_config)

@folha_bp.route('/configuracao-salarial/nova', methods=['GET', 'POST'])
@admin_required
def nova_configuracao():
    """Criar nova configuração salarial"""
    
    if request.method == 'POST':
        try:
            # Desativar configuração anterior se existir
            config_anterior = ConfiguracaoSalarial.query.filter_by(
                funcionario_id=request.form['funcionario_id'],
                admin_id=current_user.id,
                ativo=True
            ).first()
            
            if config_anterior:
                config_anterior.ativo = False
                config_anterior.data_fim = date.today()
            
            # Criar nova configuração
            config = ConfiguracaoSalarial()
            config.funcionario_id = request.form['funcionario_id']
            config.salario_base = request.form['salario_base']
            config.tipo_salario = request.form['tipo_salario']
            config.valor_hora = request.form.get('valor_hora') or None
            config.percentual_comissao = request.form.get('percentual_comissao') or None
            config.carga_horaria_mensal = request.form.get('carga_horaria_mensal', 220)
            config.dependentes = request.form.get('dependentes', 0)
            config.data_inicio = datetime.strptime(request.form['data_inicio'], '%Y-%m-%d').date()
            config.admin_id = current_user.id
            
            db.session.add(config)
            db.session.commit()
            
            flash('Configuração salarial criada com sucesso!', 'success')
            return redirect(url_for('folha.listar_configuracoes'))
            
        except Exception as e:
            db.session.rollback()
            flash(f'Erro ao criar configuração: {str(e)}', 'danger')
    
    funcionarios = Funcionario.query.filter_by(
        admin_id=current_user.id,
        ativo=True
    ).all()
    
    return render_template('folha_pagamento/nova_configuracao.html',
                         funcionarios=funcionarios)

# ================================
# BENEFÍCIOS
# ================================

@folha_bp.route('/beneficios')
@admin_required
def listar_beneficios():
    """Listar benefícios dos funcionários"""
    
    beneficios = BeneficioFuncionario.query.filter_by(
        admin_id=current_user.id,
        ativo=True
    ).join(Funcionario).order_by(Funcionario.nome, BeneficioFuncionario.tipo_beneficio).all()
    
    return render_template('folha_pagamento/beneficios.html',
                         beneficios=beneficios)

@folha_bp.route('/beneficios/novo', methods=['GET', 'POST'])
@admin_required
def novo_beneficio():
    """Criar novo benefício"""
    
    if request.method == 'POST':
        try:
            beneficio = BeneficioFuncionario()
            beneficio.funcionario_id = request.form['funcionario_id']
            beneficio.tipo_beneficio = request.form['tipo_beneficio']
            beneficio.valor = request.form['valor']
            beneficio.percentual_desconto = request.form.get('percentual_desconto', 0)
            beneficio.dias_por_mes = request.form.get('dias_por_mes', 22)
            beneficio.data_inicio = datetime.strptime(request.form['data_inicio'], '%Y-%m-%d').date()
            beneficio.observacoes = request.form.get('observacoes')
            beneficio.admin_id = current_user.id
            
            db.session.add(beneficio)
            db.session.commit()
            
            flash('Benefício criado com sucesso!', 'success')
            return redirect(url_for('folha.listar_beneficios'))
            
        except Exception as e:
            db.session.rollback()
            flash(f'Erro ao criar benefício: {str(e)}', 'danger')
    
    funcionarios = Funcionario.query.filter_by(
        admin_id=current_user.id,
        ativo=True
    ).all()
    
    tipos_beneficio = ['VR', 'VT', 'PLANO_SAUDE', 'SEGURO_VIDA', 'OUTROS']
    
    return render_template('folha_pagamento/novo_beneficio.html',
                         funcionarios=funcionarios,
                         tipos_beneficio=tipos_beneficio)

# ================================
# PARÂMETROS LEGAIS
# ================================

@folha_bp.route('/parametros-legais')
@admin_required
def parametros_legais():
    """Configurar parâmetros legais"""
    
    ano_atual = date.today().year
    
    parametros = ParametrosLegais.query.filter_by(
        admin_id=current_user.id,
        ano_vigencia=ano_atual,
        ativo=True
    ).first()
    
    return render_template('folha_pagamento/parametros_legais.html',
                         parametros=parametros,
                         ano_atual=ano_atual)

@folha_bp.route('/parametros-legais/salvar', methods=['POST'])
@admin_required
def salvar_parametros_legais():
    """Salvar parâmetros legais"""
    
    try:
        ano = int(request.form['ano_vigencia'])
        
        parametros = ParametrosLegais.query.filter_by(
            admin_id=current_user.id,
            ano_vigencia=ano,
            ativo=True
        ).first()
        
        if not parametros:
            parametros = ParametrosLegais()
            parametros.admin_id = current_user.id
            parametros.ano_vigencia = ano
            db.session.add(parametros)
        
        # Atualizar todos os campos
        campos = [
            'inss_faixa1_limite', 'inss_faixa1_percentual',
            'inss_faixa2_limite', 'inss_faixa2_percentual',
            'inss_faixa3_limite', 'inss_faixa3_percentual',
            'inss_faixa4_limite', 'inss_faixa4_percentual',
            'inss_teto', 'irrf_isencao',
            'irrf_faixa1_limite', 'irrf_faixa1_percentual', 'irrf_faixa1_deducao',
            'irrf_faixa2_limite', 'irrf_faixa2_percentual', 'irrf_faixa2_deducao',
            'irrf_faixa3_limite', 'irrf_faixa3_percentual', 'irrf_faixa3_deducao',
            'irrf_faixa4_percentual', 'irrf_faixa4_deducao',
            'irrf_dependente_valor', 'fgts_percentual',
            'salario_minimo', 'vale_transporte_percentual',
            'adicional_noturno_percentual', 'hora_extra_50_percentual',
            'hora_extra_100_percentual'
        ]
        
        for campo in campos:
            if campo in request.form:
                setattr(parametros, campo, request.form[campo])
        
        db.session.commit()
        
        flash('Parâmetros legais salvos com sucesso!', 'success')
        
    except Exception as e:
        db.session.rollback()
        flash(f'Erro ao salvar parâmetros: {str(e)}', 'danger')
    
    return redirect(url_for('folha.parametros_legais'))

# ================================
# ADIANTAMENTOS
# ================================

@folha_bp.route('/adiantamentos')
@admin_required
def listar_adiantamentos():
    """Listar adiantamentos"""
    
    adiantamentos = Adiantamento.query.filter_by(
        admin_id=current_user.id
    ).join(Funcionario).order_by(Adiantamento.data_solicitacao.desc()).all()
    
    return render_template('folha_pagamento/adiantamentos.html',
                         adiantamentos=adiantamentos)

@folha_bp.route('/adiantamentos/novo', methods=['GET', 'POST'])
@admin_required
def novo_adiantamento():
    """Criar novo adiantamento"""
    
    if request.method == 'POST':
        try:
            valor_total = float(request.form['valor_total'])
            parcelas = int(request.form['parcelas'])
            
            adiantamento = Adiantamento()
            adiantamento.funcionario_id = request.form['funcionario_id']
            adiantamento.valor_total = valor_total
            adiantamento.data_solicitacao = datetime.strptime(request.form['data_solicitacao'], '%Y-%m-%d').date()
            adiantamento.parcelas = parcelas
            adiantamento.valor_parcela = valor_total / parcelas
            adiantamento.motivo = request.form.get('motivo')
            adiantamento.observacoes = request.form.get('observacoes')
            adiantamento.admin_id = current_user.id
            
            db.session.add(adiantamento)
            db.session.commit()
            
            flash('Adiantamento criado com sucesso!', 'success')
            return redirect(url_for('folha.listar_adiantamentos'))
            
        except Exception as e:
            db.session.rollback()
            flash(f'Erro ao criar adiantamento: {str(e)}', 'danger')
    
    funcionarios = Funcionario.query.filter_by(
        admin_id=current_user.id,
        ativo=True
    ).all()
    
    return render_template('folha_pagamento/novo_adiantamento.html',
                         funcionarios=funcionarios)

@folha_bp.route('/adiantamentos/<int:id>/aprovar', methods=['POST'])
@admin_required
def aprovar_adiantamento(id):
    """Aprovar adiantamento"""
    
    adiantamento = Adiantamento.query.filter_by(
        id=id,
        admin_id=current_user.id
    ).first()
    
    if not adiantamento:
        flash('Adiantamento não encontrado.', 'error')
        return redirect(url_for('folha.listar_adiantamentos'))
    
    adiantamento.status = 'APROVADO'
    adiantamento.data_aprovacao = date.today()
    adiantamento.aprovado_por = current_user.id
    
    db.session.commit()
    
    flash('Adiantamento aprovado com sucesso!', 'success')
    return redirect(url_for('folha.listar_adiantamentos'))

# ================================
# RELATÓRIOS
# ================================

@folha_bp.route('/relatorios')
@admin_required
def relatorios():
    """Página de relatórios"""
    return render_template('folha_pagamento/relatorios.html')

@folha_bp.route('/api/folhas/<int:ano>/<int:mes>')
@admin_required
def api_folhas_mes(ano, mes):
    """API para obter folhas do mês (para relatórios)"""
    
    mes_referencia = date(ano, mes, 1)
    
    folhas = FolhaPagamento.query.filter_by(
        admin_id=current_user.id,
        mes_referencia=mes_referencia
    ).join(Funcionario).all()
    
    dados = []
    for folha in folhas:
        dados.append({
            'funcionario': folha.funcionario.nome,
            'salario_base': float(folha.salario_base),
            'horas_extras': float(folha.horas_extras),
            'total_proventos': float(folha.total_proventos),
            'inss': float(folha.inss),
            'irrf': float(folha.irrf),
            'total_descontos': float(folha.total_descontos),
            'salario_liquido': float(folha.salario_liquido)
        })
    
    return jsonify(dados)