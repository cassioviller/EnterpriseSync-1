from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify
from flask_login import login_required, current_user
from app import db
from models import *
from models import OutroCusto
from forms import *
from utils import calcular_horas_trabalhadas, calcular_custo_real_obra, calcular_custos_mes, calcular_kpis_funcionarios_geral, calcular_kpis_funcionario_periodo, calcular_kpis_funcionario_completo, calcular_ocorrencias_funcionario, processar_meio_periodo_exemplo
from kpis_engine import kpis_engine
from datetime import datetime, date
from sqlalchemy import func

import os
import json
from werkzeug.utils import secure_filename
from sqlalchemy import or_

main_bp = Blueprint('main', __name__)

# Rotas adicionais de veículos serão adicionadas diretamente aqui

@main_bp.route('/')
@login_required
def dashboard():
    # Filtros de data dos parâmetros
    data_inicio = request.args.get('data_inicio')
    data_fim = request.args.get('data_fim')
    
    # Definir período padrão (mês atual)
    if not data_inicio:
        data_inicio = date.today().replace(day=1)
    else:
        data_inicio = datetime.strptime(data_inicio, '%Y-%m-%d').date()
    
    if not data_fim:
        data_fim = date.today()
    else:
        data_fim = datetime.strptime(data_fim, '%Y-%m-%d').date()
    
    # KPIs para o dashboard
    total_funcionarios = Funcionario.query.filter_by(ativo=True).count()
    total_obras = Obra.query.filter(Obra.status.in_(['Em andamento', 'Pausada'])).count()
    total_veiculos = Veiculo.query.count()
    
    # Custos do período usando função corrigida
    custos_detalhados = calcular_custos_mes(data_inicio, data_fim)
    custos_mes = custos_detalhados['total']
    
    # Obras em andamento
    obras_andamento = Obra.query.filter_by(status='Em andamento').limit(5).all()
    
    # Funcionários por departamento
    funcionarios_dept = db.session.query(
        Departamento.nome,
        func.count(Funcionario.id).label('total')
    ).join(Funcionario).filter(Funcionario.ativo == True).group_by(Departamento.nome).all()
    
    # Custos por obra no período
    custos_recentes = []
    for obra in Obra.query.limit(10).all():
        custo_obra = calcular_custo_real_obra(obra.id, data_inicio, data_fim)
        if custo_obra['custo_total'] > 0:
            custos_recentes.append({
                'nome': obra.nome,
                'total_custo': custo_obra['custo_total']
            })
    
    return render_template('dashboard.html',
                         total_funcionarios=total_funcionarios,
                         total_obras=total_obras,
                         total_veiculos=total_veiculos,
                         custos_mes=custos_mes,
                         custos_detalhados=custos_detalhados,
                         data_inicio=data_inicio,
                         data_fim=data_fim,
                         obras_andamento=obras_andamento,
                         funcionarios_dept=funcionarios_dept,
                         custos_recentes=custos_recentes)

# Funcionários
@main_bp.route('/funcionarios')
@login_required
def funcionarios():
    # Filtros de data dos parâmetros
    data_inicio = request.args.get('data_inicio')
    data_fim = request.args.get('data_fim')
    
    # Definir período padrão (mês atual)
    if not data_inicio:
        data_inicio = date.today().replace(day=1)
    else:
        data_inicio = datetime.strptime(data_inicio, '%Y-%m-%d').date()
    
    if not data_fim:
        data_fim = date.today()
    else:
        data_fim = datetime.strptime(data_fim, '%Y-%m-%d').date()
    
    # Calcular KPIs gerais dos funcionários para o período
    kpis_geral = calcular_kpis_funcionarios_geral(data_inicio, data_fim)
    
    return render_template('funcionarios.html', 
                         funcionarios_kpis=kpis_geral['funcionarios_kpis'],
                         kpis_geral=kpis_geral,
                         departamentos=Departamento.query.all(),
                         funcoes=Funcao.query.all(),
                         horarios=HorarioTrabalho.query.all(),
                         data_inicio=data_inicio,
                         data_fim=data_fim)

@main_bp.route('/funcionarios/novo', methods=['GET', 'POST'])
@login_required
def novo_funcionario():
    form = FuncionarioForm()
    form.departamento_id.choices = [(0, 'Selecione...')] + [(d.id, d.nome) for d in Departamento.query.all()]
    form.funcao_id.choices = [(0, 'Selecione...')] + [(f.id, f.nome) for f in Funcao.query.all()]
    form.horario_trabalho_id.choices = [(0, 'Selecione...')] + [(h.id, h.nome) for h in HorarioTrabalho.query.all()]
    
    if form.validate_on_submit():
        try:
            # Validar CPF
            from utils import validar_cpf, gerar_codigo_funcionario, salvar_foto_funcionario
            if not validar_cpf(form.cpf.data):
                flash('CPF inválido. Verifique o número informado.', 'error')
                return render_template('funcionario_form.html', form=form, titulo='Novo Funcionário',
                                     departamentos=Departamento.query.all(),
                                     funcoes=Funcao.query.all(),
                                     horarios=HorarioTrabalho.query.all())
            
            # Verificar se CPF já existe
            cpf_existe = Funcionario.query.filter_by(cpf=form.cpf.data).first()
            if cpf_existe:
                flash('CPF já cadastrado para outro funcionário.', 'error')
                return render_template('funcionario_form.html', form=form, titulo='Novo Funcionário',
                                     departamentos=Departamento.query.all(),
                                     funcoes=Funcao.query.all(),
                                     horarios=HorarioTrabalho.query.all())
            
            funcionario = Funcionario(
                nome=form.nome.data,
                cpf=form.cpf.data,
                rg=form.rg.data,
                data_nascimento=form.data_nascimento.data,
                endereco=form.endereco.data,
                telefone=form.telefone.data,
                email=form.email.data,
                data_admissao=form.data_admissao.data,
                salario=form.salario.data or 0.0,
                departamento_id=form.departamento_id.data if form.departamento_id.data > 0 else None,
                funcao_id=form.funcao_id.data if form.funcao_id.data > 0 else None,
                horario_trabalho_id=form.horario_trabalho_id.data if form.horario_trabalho_id.data > 0 else None,
                ativo=form.ativo.data
            )
            
            # Gerar código único
            funcionario.codigo = gerar_codigo_funcionario()
            
            db.session.add(funcionario)
            db.session.flush()  # Para obter o ID antes do commit
            
            # Processar upload de foto
            if form.foto.data:
                foto_path = salvar_foto_funcionario(form.foto.data, funcionario.codigo)
                if foto_path:
                    funcionario.foto = foto_path
            
            db.session.commit()
            flash('Funcionário cadastrado com sucesso!', 'success')
            return redirect(url_for('main.funcionarios'))
            
        except Exception as e:
            db.session.rollback()
            flash(f'Erro ao cadastrar funcionário: {str(e)}', 'error')
            return render_template('funcionario_form.html', form=form, titulo='Novo Funcionário',
                                 departamentos=Departamento.query.all(),
                                 funcoes=Funcao.query.all(),
                                 horarios=HorarioTrabalho.query.all())
    
    return render_template('funcionario_form.html', form=form, titulo='Novo Funcionário',
                         departamentos=Departamento.query.all(),
                         funcoes=Funcao.query.all(),
                         horarios=HorarioTrabalho.query.all())

@main_bp.route('/funcionarios/<int:id>/editar', methods=['GET', 'POST'])
@login_required
def editar_funcionario(id):
    funcionario = Funcionario.query.get_or_404(id)
    
    if request.method == 'POST':
        try:
            # Atualizar dados do funcionário
            funcionario.nome = request.form.get('nome')
            funcionario.cpf = request.form.get('cpf')
            funcionario.rg = request.form.get('rg')
            funcionario.endereco = request.form.get('endereco')
            funcionario.telefone = request.form.get('telefone')
            funcionario.email = request.form.get('email')
            funcionario.salario = float(request.form.get('salario', 0) or 0)
            
            # Data de nascimento
            data_nascimento = request.form.get('data_nascimento')
            if data_nascimento:
                funcionario.data_nascimento = datetime.strptime(data_nascimento, '%Y-%m-%d').date()
            
            # Data de admissão
            data_admissao = request.form.get('data_admissao')
            if data_admissao:
                funcionario.data_admissao = datetime.strptime(data_admissao, '%Y-%m-%d').date()
            
            # IDs opcionais
            departamento_id = request.form.get('departamento_id')
            funcionario.departamento_id = int(departamento_id) if departamento_id and departamento_id != '0' else None
            
            funcao_id = request.form.get('funcao_id')
            funcionario.funcao_id = int(funcao_id) if funcao_id and funcao_id != '0' else None
            
            horario_id = request.form.get('horario_trabalho_id')
            funcionario.horario_trabalho_id = int(horario_id) if horario_id and horario_id != '0' else None
            
            funcionario.ativo = bool(request.form.get('ativo'))
            
            # Processar upload de foto
            if 'foto' in request.files:
                foto = request.files['foto']
                if foto and foto.filename:
                    from utils import salvar_foto_funcionario
                    foto_path = salvar_foto_funcionario(foto, funcionario.codigo)
                    if foto_path:
                        funcionario.foto = foto_path
            
            db.session.commit()
            flash('Funcionário atualizado com sucesso!', 'success')
            return redirect(url_for('main.funcionario_perfil', id=funcionario.id))
            
        except Exception as e:
            flash(f'Erro ao atualizar funcionário: {str(e)}', 'error')
            return redirect(url_for('main.funcionario_perfil', id=id))
    
    # Para GET, redirecionar para a página de perfil com modo de edição
    return redirect(url_for('main.funcionario_perfil', id=id, edit=1))

@main_bp.route('/funcionarios/ponto/novo', methods=['POST'])
@login_required
def novo_ponto():
    """Criar novo registro de ponto com suporte a tipos de lançamento"""
    try:
        funcionario_id = request.form.get('funcionario_id')
        data = datetime.strptime(request.form.get('data'), '%Y-%m-%d').date()
        tipo_lancamento = request.form.get('tipo_lancamento')
        obra_id = request.form.get('obra_id') if request.form.get('obra_id') else None
        percentual_extras = float(request.form.get('percentual_extras', 0)) if request.form.get('percentual_extras') else 0.0
        observacoes = request.form.get('observacoes', '')
        
        # Verificar se já existe registro para esta data
        registro_existente = RegistroPonto.query.filter_by(
            funcionario_id=funcionario_id,
            data=data
        ).first()
        
        if registro_existente:
            flash('Já existe um registro de ponto para esta data.', 'error')
            return redirect(request.referrer or url_for('main.funcionario_perfil', id=funcionario_id))
        
        # Criar registro baseado no tipo de lançamento
        registro = RegistroPonto(
            funcionario_id=funcionario_id,
            obra_id=obra_id,
            data=data,
            observacoes=observacoes,
            tipo_registro=tipo_lancamento,
            percentual_extras=percentual_extras
        )
        
        if tipo_lancamento == 'trabalhado':
            # Registro normal de trabalho
            registro.hora_entrada = datetime.strptime(request.form.get('hora_entrada'), '%H:%M').time() if request.form.get('hora_entrada') else None
            registro.hora_saida = datetime.strptime(request.form.get('hora_saida'), '%H:%M').time() if request.form.get('hora_saida') else None
            registro.hora_almoco_saida = datetime.strptime(request.form.get('hora_almoco_saida'), '%H:%M').time() if request.form.get('hora_almoco_saida') else None
            registro.hora_almoco_retorno = datetime.strptime(request.form.get('hora_almoco_retorno'), '%H:%M').time() if request.form.get('hora_almoco_retorno') else None
            
        elif tipo_lancamento == 'feriado_trabalhado':
            # Trabalho em feriado = 100% extra
            registro.hora_entrada = datetime.strptime(request.form.get('hora_entrada'), '%H:%M').time() if request.form.get('hora_entrada') else None
            registro.hora_saida = datetime.strptime(request.form.get('hora_saida'), '%H:%M').time() if request.form.get('hora_saida') else None
            registro.hora_almoco_saida = datetime.strptime(request.form.get('hora_almoco_saida'), '%H:%M').time() if request.form.get('hora_almoco_saida') else None
            registro.hora_almoco_retorno = datetime.strptime(request.form.get('hora_almoco_retorno'), '%H:%M').time() if request.form.get('hora_almoco_retorno') else None
            # Marcar como feriado trabalhado para cálculo especial
            registro.observacoes = f"FERIADO_TRABALHADO: {observacoes}"
            
        elif tipo_lancamento in ['sabado_horas_extras', 'domingo_horas_extras']:
            # Trabalho em fim de semana com horas extras
            registro.hora_entrada = datetime.strptime(request.form.get('hora_entrada'), '%H:%M').time() if request.form.get('hora_entrada') else None
            registro.hora_saida = datetime.strptime(request.form.get('hora_saida'), '%H:%M').time() if request.form.get('hora_saida') else None
            registro.hora_almoco_saida = datetime.strptime(request.form.get('hora_almoco_saida'), '%H:%M').time() if request.form.get('hora_almoco_saida') else None
            registro.hora_almoco_retorno = datetime.strptime(request.form.get('hora_almoco_retorno'), '%H:%M').time() if request.form.get('hora_almoco_retorno') else None
            
            # Marcar tipo específico para cálculo com percentual configurado
            percentual_info = f" (Extra: {percentual_extras}%)" if percentual_extras > 0 else ""
            registro.observacoes = f"{tipo_lancamento.upper()}{percentual_info}: {observacoes}"
            
        elif tipo_lancamento in ['falta', 'falta_justificada', 'feriado']:
            # Tipos sem horários - apenas marcação
            registro.observacoes = f"{tipo_lancamento.upper()}: {observacoes}"
            
            # Para falta justificada, apenas registrar o ponto (sem criar ocorrência)
            # Ocorrências serão gerenciadas separadamente se necessário
        
        db.session.add(registro)
        db.session.commit()
        
        # Recalcular KPIs após inserção
        try:
            from kpis_engine import atualizar_calculos_ponto
            atualizar_calculos_ponto(registro.id)
        except ImportError:
            # KPIs engine não disponível, continuar sem erro
            pass
        
        flash(f'Registro de ponto ({tipo_lancamento}) criado com sucesso!', 'success')
        return redirect(request.referrer or url_for('main.funcionario_perfil', id=funcionario_id))
        
    except Exception as e:
        db.session.rollback()
        flash(f'Erro ao criar registro de ponto: {str(e)}', 'error')
        return redirect(request.referrer or url_for('main.funcionarios'))

@main_bp.route('/funcionarios/<int:funcionario_id>/horario-padrao')
@login_required 
def horario_padrao_funcionario(funcionario_id):
    """Retorna o horário padrão do funcionário em JSON"""
    funcionario = Funcionario.query.get_or_404(funcionario_id)
    
    # Buscar horário de trabalho do funcionário
    if funcionario.horario_trabalho_id:
        horario = HorarioTrabalho.query.get(funcionario.horario_trabalho_id)
        if horario:
            return jsonify({
                'success': True,
                'hora_entrada': horario.entrada.strftime('%H:%M') if horario.entrada else '08:00',
                'hora_saida': horario.saida.strftime('%H:%M') if horario.saida else '17:00',
                'hora_almoco_saida': horario.saida_almoco.strftime('%H:%M') if horario.saida_almoco else '12:00',
                'hora_almoco_retorno': horario.retorno_almoco.strftime('%H:%M') if horario.retorno_almoco else '13:00'
            })
    else:
        return jsonify({
            'success': False,
            'message': 'Funcionário não possui horário de trabalho configurado'
        })

@main_bp.route('/funcionarios/modal', methods=['POST'])
@login_required
def funcionario_modal():
    """Rota específica para processamento do modal de funcionários"""
    try:
        # Validar CPF
        from utils import validar_cpf, gerar_codigo_funcionario, salvar_foto_funcionario
        
        cpf = request.form.get('cpf')
        if not validar_cpf(cpf):
            flash('CPF inválido. Verifique o número informado.', 'error')
            return redirect(url_for('main.funcionarios'))
        
        # Verificar se CPF já existe
        cpf_existe = Funcionario.query.filter_by(cpf=cpf).first()
        if cpf_existe:
            flash('CPF já cadastrado para outro funcionário.', 'error')
            return redirect(url_for('main.funcionarios'))
        
        funcionario = Funcionario(
            nome=request.form.get('nome'),
            cpf=cpf,
            rg=request.form.get('rg'),
            endereco=request.form.get('endereco'),
            telefone=request.form.get('telefone'),
            email=request.form.get('email'),
            salario=float(request.form.get('salario', 0) or 0),
            ativo=bool(request.form.get('ativo'))
        )
        
        # Datas opcionais
        data_nascimento = request.form.get('data_nascimento')
        if data_nascimento:
            funcionario.data_nascimento = datetime.strptime(data_nascimento, '%Y-%m-%d').date()
        
        data_admissao = request.form.get('data_admissao')
        if data_admissao:
            funcionario.data_admissao = datetime.strptime(data_admissao, '%Y-%m-%d').date()
        else:
            funcionario.data_admissao = date.today()  # Padrão para hoje
        
        # IDs opcionais
        departamento_id = request.form.get('departamento_id')
        funcionario.departamento_id = int(departamento_id) if departamento_id and departamento_id != '0' else None
        
        funcao_id = request.form.get('funcao_id')
        funcionario.funcao_id = int(funcao_id) if funcao_id and funcao_id != '0' else None
        
        horario_id = request.form.get('horario_trabalho_id')
        funcionario.horario_trabalho_id = int(horario_id) if horario_id and horario_id != '0' else None
        
        # Gerar código único
        funcionario.codigo = gerar_codigo_funcionario()
        
        db.session.add(funcionario)
        db.session.flush()  # Para obter o ID antes do commit
        
        # Processar upload de foto
        if 'foto' in request.files:
            foto = request.files['foto']
            if foto and foto.filename:
                foto_path = salvar_foto_funcionario(foto, funcionario.codigo)
                if foto_path:
                    funcionario.foto = foto_path
        
        db.session.commit()
        flash('Funcionário cadastrado com sucesso!', 'success')
        return redirect(url_for('main.funcionarios'))
        
    except Exception as e:
        db.session.rollback()
        flash(f'Erro ao cadastrar funcionário: {str(e)}', 'error')
        return redirect(url_for('main.funcionarios'))

def calcular_kpis_funcionario(funcionario_id):
    """Calcula KPIs individuais do funcionário para o mês atual"""
    hoje = date.today()
    primeiro_dia_mes = hoje.replace(day=1)
    
    # Buscar registros de ponto do mês atual
    registros_ponto = RegistroPonto.query.filter(
        RegistroPonto.funcionario_id == funcionario_id,
        RegistroPonto.data >= primeiro_dia_mes,
        RegistroPonto.data <= hoje
    ).all()
    
    # Calcular KPIs
    horas_trabalhadas = sum(r.horas_trabalhadas or 0 for r in registros_ponto)
    horas_extras = sum(r.horas_extras or 0 for r in registros_ponto)
    
    # Contar dias úteis no mês (aproximação: 22 dias úteis)
    dias_uteis_mes = 22
    dias_com_registro = len([r for r in registros_ponto if r.hora_entrada])
    
    # Calcular faltas e atrasos
    faltas = max(0, dias_uteis_mes - dias_com_registro)
    atrasos = len([r for r in registros_ponto if r.hora_entrada and r.hora_entrada.hour > 8])
    
    # Calcular absenteísmo
    absenteismo = (faltas / dias_uteis_mes) * 100 if dias_uteis_mes > 0 else 0
    
    # Calcular média de horas diárias
    media_horas_diarias = horas_trabalhadas / dias_com_registro if dias_com_registro > 0 else 0
    
    return {
        'horas_trabalhadas': horas_trabalhadas,
        'horas_extras': horas_extras,
        'faltas': faltas,
        'atrasos': atrasos,
        'absenteismo': absenteismo,
        'media_horas_diarias': media_horas_diarias
    }

def obter_dados_graficos_funcionario(funcionario_id):
    """Obtém dados para gráficos de desempenho do funcionário"""
    # Últimos 6 meses
    meses = []
    horas_trabalhadas = []
    absenteismo = []
    
    hoje = date.today()
    
    for i in range(6):
        # Calcular mês
        mes = hoje.month - i
        ano = hoje.year
        if mes <= 0:
            mes += 12
            ano -= 1
        
        primeiro_dia = date(ano, mes, 1)
        if mes == 12:
            ultimo_dia = date(ano + 1, 1, 1)
        else:
            ultimo_dia = date(ano, mes + 1, 1)
        
        # Buscar registros do mês
        registros = RegistroPonto.query.filter(
            RegistroPonto.funcionario_id == funcionario_id,
            RegistroPonto.data >= primeiro_dia,
            RegistroPonto.data < ultimo_dia
        ).all()
        
        # Calcular totais
        horas_mes = sum(r.horas_trabalhadas or 0 for r in registros)
        dias_com_registro = len([r for r in registros if r.hora_entrada])
        
        # Nome do mês
        nomes_meses = [
            'Janeiro', 'Fevereiro', 'Março', 'Abril', 'Maio', 'Junho',
            'Julho', 'Agosto', 'Setembro', 'Outubro', 'Novembro', 'Dezembro'
        ]
        nome_mes = nomes_meses[mes - 1]
        
        meses.insert(0, nome_mes)
        horas_trabalhadas.insert(0, horas_mes)
        
        # Calcular absenteísmo (aproximação: 22 dias úteis)
        absenteismo_mes = ((22 - dias_com_registro) / 22) * 100 if dias_com_registro < 22 else 0
        absenteismo.insert(0, absenteismo_mes)
    
    return {
        'meses': meses,
        'horas_trabalhadas': horas_trabalhadas,
        'absenteismo': absenteismo
    }

@main_bp.route('/funcionarios/<int:id>/perfil')
@login_required
def funcionario_perfil(id):
    funcionario = Funcionario.query.get_or_404(id)
    
    # Filtros de data dos parâmetros
    data_inicio = request.args.get('data_inicio')
    data_fim = request.args.get('data_fim')
    obra_filtro = request.args.get('obra')
    
    # Definir período padrão (mês atual)
    if not data_inicio:
        data_inicio = date.today().replace(day=1)
    else:
        data_inicio = datetime.strptime(data_inicio, '%Y-%m-%d').date()
    
    if not data_fim:
        data_fim = date.today()
    else:
        data_fim = datetime.strptime(data_fim, '%Y-%m-%d').date()
    
    # Calcular KPIs individuais para o período (usando engine v3.1)
    kpis = kpis_engine.calcular_kpis_funcionario(id, data_inicio, data_fim)
    
    # Buscar registros de ponto com filtros e identificação de faltas
    
    if obra_filtro:
        # Se há filtro de obra, usar query tradicional
        query_ponto = RegistroPonto.query.filter_by(funcionario_id=id).filter(
            RegistroPonto.data >= data_inicio,
            RegistroPonto.data <= data_fim,
            RegistroPonto.obra_id == obra_filtro
        )
        registros_ponto = query_ponto.order_by(RegistroPonto.data.desc()).all()
        
        # Usar novo engine de KPIs
        faltas = []  # Lista vazia por enquanto - será implementada se necessário
        
        # Lista de feriados 2025
        feriados_2025 = {
            date(2025, 1, 1),   # Ano Novo
            date(2025, 2, 17),  # Carnaval (Segunda-feira)
            date(2025, 2, 18),  # Carnaval (Terça-feira)
            date(2025, 4, 18),  # Paixão de Cristo (Sexta-feira Santa)
            date(2025, 4, 21),  # Tiradentes
            date(2025, 5, 1),   # Dia do Trabalhador
            date(2025, 6, 19),  # Corpus Christi
            date(2025, 9, 7),   # Independência
            date(2025, 10, 12), # Nossa Senhora Aparecida
            date(2025, 11, 2),  # Finados
            date(2025, 11, 15), # Proclamação da República
            date(2025, 12, 25)  # Natal
        }
        
        for registro in registros_ponto:
            # Adicionar informações sobre faltas e feriados baseado no tipo_registro
            registro.is_falta = (registro.tipo_registro in ['falta', 'falta_justificada'])
            registro.is_feriado = (registro.tipo_registro in ['feriado', 'feriado_trabalhado'])
    else:
        # Usar registros de ponto simples
        registros_ponto = RegistroPonto.query.filter_by(funcionario_id=id).filter(
            RegistroPonto.data >= data_inicio,
            RegistroPonto.data <= data_fim
        ).order_by(RegistroPonto.data.desc()).all()
        faltas = []  # Lista vazia por enquanto - será implementada se necessário
        
        # Adicionar informação de feriado e faltas para todos os registros
        for registro in registros_ponto:
            registro.is_falta = (registro.tipo_registro in ['falta', 'falta_justificada'])
            registro.is_feriado = (registro.tipo_registro in ['feriado', 'feriado_trabalhado'])
    
    # Lista de feriados 2025 
    feriados_2025 = {
        date(2025, 1, 1),   # Ano Novo
        date(2025, 2, 17),  # Carnaval (Segunda-feira)
        date(2025, 2, 18),  # Carnaval (Terça-feira)
        date(2025, 4, 18),  # Paixão de Cristo (Sexta-feira Santa)
        date(2025, 4, 21),  # Tiradentes
        date(2025, 5, 1),   # Dia do Trabalhador
        date(2025, 6, 19),  # Corpus Christi
        date(2025, 9, 7),   # Independência
        date(2025, 10, 12), # Nossa Senhora Aparecida
        date(2025, 11, 2),  # Finados
        date(2025, 11, 15), # Proclamação da República
        date(2025, 12, 25)  # Natal
    }
    
    # Buscar ocorrências (sem filtro de data por enquanto)
    ocorrencias = Ocorrencia.query.filter_by(funcionario_id=id).order_by(Ocorrencia.data_inicio.desc()).all()
    
    # Buscar registros de alimentação com filtros
    query_alimentacao = RegistroAlimentacao.query.filter_by(funcionario_id=id).filter(
        RegistroAlimentacao.data >= data_inicio,
        RegistroAlimentacao.data <= data_fim
    )
    
    if obra_filtro:
        query_alimentacao = query_alimentacao.filter_by(obra_id=obra_filtro)
    
    registros_alimentacao = query_alimentacao.order_by(RegistroAlimentacao.data.desc()).all()
    
    # Buscar outros custos com filtros
    query_outros_custos = OutroCusto.query.filter_by(funcionario_id=id).filter(
        OutroCusto.data >= data_inicio,
        OutroCusto.data <= data_fim
    )
    
    if obra_filtro:
        query_outros_custos = query_outros_custos.filter_by(obra_id=obra_filtro)
    
    outros_custos = query_outros_custos.order_by(OutroCusto.data.desc()).all()
    
    # Buscar obras para os dropdowns
    obras = Obra.query.filter_by(status='Em andamento').all()
    
    # Obter dados para gráficos
    graficos = obter_dados_graficos_funcionario(id)
    
    # Criar objeto para KPIs (simular uma estrutura)
    class KPIData:
        def __init__(self, data):
            for key, value in data.items():
                setattr(self, key, value)
    
    # Adicionar cálculo de outros custos
    total_outros_custos = sum(c.valor if c.categoria == 'adicional' else -c.valor for c in outros_custos)
    
    if kpis:
        # Corrigir horas perdidas: (faltas * 8) + atrasos
        kpis['horas_perdidas_total'] = (kpis.get('faltas', 0) * 8) + kpis.get('atrasos', 0)
        kpis['outros_custos'] = total_outros_custos
        kpis_obj = KPIData(kpis)
    else:
        kpis_obj = KPIData({
            'horas_trabalhadas': 0,
            'horas_extras': 0,
            'faltas': 0,
            'atrasos': 0,
            'absenteismo': 0,
            'horas_extras_valor': 0,
            'media_horas_diarias': 0,
            'total_atrasos': 0,
            'pontualidade': 100,
            'custo_total': 0,
            'custo_mao_obra': 0,
            'custo_alimentacao': 0,
            'custo_transporte': 0,
            'dias_trabalhados': 0,
            'dias_uteis': 0,
            'horas_perdidas_total': 0,
            'outros_custos': total_outros_custos
        })
    
    # Buscar dados adicionais para o modal de edição
    departamentos = Departamento.query.all()
    funcoes = Funcao.query.all()
    horarios = HorarioTrabalho.query.all()
    
    return render_template('funcionario_perfil.html',
                         funcionario=funcionario,
                         kpis=kpis_obj,
                         registros_ponto=registros_ponto,
                         ocorrencias=ocorrencias,
                         registros_alimentacao=registros_alimentacao,
                         outros_custos=outros_custos,
                         obras=obras,
                         graficos=graficos,
                         data_inicio=data_inicio,
                         data_fim=data_fim,
                         obra_filtro=obra_filtro,
                         departamentos=departamentos,
                         funcoes=funcoes,
                         horarios=horarios)

@main_bp.route('/funcionarios/<int:id>/excluir', methods=['POST'])
@login_required
def excluir_funcionario(id):
    funcionario = Funcionario.query.get_or_404(id)
    db.session.delete(funcionario)
    db.session.commit()
    flash('Funcionário excluído com sucesso!', 'success')
    return redirect(url_for('main.funcionarios'))

@main_bp.route('/funcionarios/<int:funcionario_id>/outros-custos', methods=['POST'])
@login_required
def criar_outro_custo(funcionario_id):
    funcionario = Funcionario.query.get_or_404(funcionario_id)
    
    try:
        data = datetime.strptime(request.form['data'], '%Y-%m-%d').date()
        
        outro_custo = OutroCusto(
            funcionario_id=funcionario_id,
            data=data,
            tipo=request.form['tipo'],
            categoria=request.form['categoria'],
            valor=float(request.form['valor']),
            descricao=request.form.get('descricao')
        )
        
        db.session.add(outro_custo)
        db.session.commit()
        
        flash('Outro custo registrado com sucesso!', 'success')
    except Exception as e:
        db.session.rollback()
        flash(f'Erro ao registrar outro custo: {str(e)}', 'error')
    
    return redirect(url_for('main.funcionario_perfil', id=funcionario_id))

@main_bp.route('/funcionarios/<int:funcionario_id>/outros-custos/<int:custo_id>', methods=['DELETE'])
@login_required
def excluir_outro_custo(funcionario_id, custo_id):
    custo = OutroCusto.query.get_or_404(custo_id)
    
    # Verificar se o custo pertence ao funcionário
    if custo.funcionario_id != funcionario_id:
        return jsonify({'success': False, 'message': 'Registro não encontrado'}), 404
    
    try:
        db.session.delete(custo)
        db.session.commit()
        return jsonify({'success': True, 'message': 'Registro excluído com sucesso'})
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'message': str(e)}), 500

# Departamentos
@main_bp.route('/departamentos')
@login_required
def departamentos():
    departamentos = Departamento.query.all()
    return render_template('departamentos.html', departamentos=departamentos)

@main_bp.route('/departamentos/novo', methods=['GET', 'POST'])
@login_required
def novo_departamento():
    form = DepartamentoForm()
    if form.validate_on_submit():
        departamento = Departamento(
            nome=form.nome.data,
            descricao=form.descricao.data
        )
        db.session.add(departamento)
        db.session.commit()
        flash('Departamento cadastrado com sucesso!', 'success')
        return redirect(url_for('main.departamentos'))
    
    return render_template('departamentos.html', form=form, departamentos=Departamento.query.all())

@main_bp.route('/departamentos/<int:id>/editar', methods=['GET', 'POST'])
@login_required
def editar_departamento(id):
    departamento = Departamento.query.get_or_404(id)
    form = DepartamentoForm(obj=departamento)
    
    if form.validate_on_submit():
        departamento.nome = form.nome.data
        departamento.descricao = form.descricao.data
        db.session.commit()
        flash('Departamento atualizado com sucesso!', 'success')
        return redirect(url_for('main.departamentos'))
    
    return render_template('departamentos.html', form=form, departamento=departamento, departamentos=Departamento.query.all())

@main_bp.route('/departamentos/<int:id>/excluir', methods=['POST'])
@login_required
def excluir_departamento(id):
    departamento = Departamento.query.get_or_404(id)
    db.session.delete(departamento)
    db.session.commit()
    flash('Departamento excluído com sucesso!', 'success')
    return redirect(url_for('main.departamentos'))

# Funções
@main_bp.route('/funcoes')
@login_required
def funcoes():
    funcoes = Funcao.query.all()
    return render_template('funcoes.html', funcoes=funcoes)

@main_bp.route('/funcoes/novo', methods=['GET', 'POST'])
@login_required
def nova_funcao():
    form = FuncaoForm()
    if form.validate_on_submit():
        funcao = Funcao(
            nome=form.nome.data,
            descricao=form.descricao.data,
            salario_base=form.salario_base.data or 0.0
        )
        db.session.add(funcao)
        db.session.commit()
        flash('Função cadastrada com sucesso!', 'success')
        return redirect(url_for('main.funcoes'))
    
    return render_template('funcoes.html', form=form, funcoes=Funcao.query.all())

@main_bp.route('/funcoes/<int:id>/editar', methods=['GET', 'POST'])
@login_required
def editar_funcao(id):
    funcao = Funcao.query.get_or_404(id)
    form = FuncaoForm(obj=funcao)
    
    if form.validate_on_submit():
        funcao.nome = form.nome.data
        funcao.descricao = form.descricao.data
        funcao.salario_base = form.salario_base.data or 0.0
        db.session.commit()
        flash('Função atualizada com sucesso!', 'success')
        return redirect(url_for('main.funcoes'))
    
    return render_template('funcoes.html', form=form, funcao=funcao, funcoes=Funcao.query.all())

@main_bp.route('/funcoes/<int:id>/excluir', methods=['POST'])
@login_required
def excluir_funcao(id):
    funcao = Funcao.query.get_or_404(id)
    db.session.delete(funcao)
    db.session.commit()
    flash('Função excluída com sucesso!', 'success')
    return redirect(url_for('main.funcoes'))

# Obras
@main_bp.route('/obras')
@login_required
def obras():
    from datetime import date, timedelta
    from sqlalchemy import func
    
    # Filtros
    nome_filtro = request.args.get('nome', '').strip()
    status_filtro = request.args.get('status', '')
    data_inicio_filtro = request.args.get('data_inicio')
    data_fim_filtro = request.args.get('data_fim')
    
    # Query base
    query = Obra.query
    
    # Aplicar filtros
    if nome_filtro:
        query = query.filter(Obra.nome.ilike(f'%{nome_filtro}%'))
    if status_filtro:
        query = query.filter(Obra.status == status_filtro)
    
    obras = query.all()
    
    # Período para KPIs (padrão: último mês)
    if data_fim_filtro:
        data_fim = datetime.strptime(data_fim_filtro, '%Y-%m-%d').date()
    else:
        data_fim = date.today()
        
    if data_inicio_filtro:
        data_inicio = datetime.strptime(data_inicio_filtro, '%Y-%m-%d').date()
    else:
        # Último mês por padrão (30 dias atrás)
        data_inicio = data_fim - timedelta(days=30)
    
    for obra in obras:
        # Calcular RDOs
        total_rdos = RDO.query.filter_by(obra_id=obra.id).count()
        
        # Calcular dias trabalhados (registros de ponto únicos)
        dias_trabalhados = db.session.query(RegistroPonto.data).filter(
            RegistroPonto.obra_id == obra.id,
            RegistroPonto.data.between(data_inicio, data_fim),
            RegistroPonto.hora_entrada.isnot(None)
        ).distinct().count()
        
        # Calcular custo total básico (últimos 30 dias)
        custo_alimentacao = db.session.query(func.sum(RegistroAlimentacao.valor)).filter(
            RegistroAlimentacao.obra_id == obra.id,
            RegistroAlimentacao.data.between(data_inicio, data_fim)
        ).scalar() or 0.0
        
        # Criar objeto KPI simples
        # Calcular custos reais da obra
        custo_obra_total = 0
        
        # Custos diretos de obra
        try:
            from models import CustoObra
            custos_obra = db.session.query(CustoObra).filter(
                CustoObra.obra_id == obra.id,
                CustoObra.data >= data_inicio,
                CustoObra.data <= data_fim
            ).all()
            custo_obra_total += sum(custo.valor for custo in custos_obra)
        except:
            pass
        
        # Adicionar custos de alimentação
        custo_obra_total += custo_alimentacao
        
        # Custos de veículos da obra
        try:
            custos_veiculos = db.session.query(CustoVeiculo).filter(
                CustoVeiculo.obra_id == obra.id,
                CustoVeiculo.data_custo >= data_inicio,
                CustoVeiculo.data_custo <= data_fim
            ).all()
            custo_obra_total += sum(custo.valor for custo in custos_veiculos)
        except:
            pass
        
        obra.kpis = type('KPIs', (), {
            'total_rdos': total_rdos,
            'dias_trabalhados': dias_trabalhados,
            'custo_total': custo_obra_total
        })()
    
    # Status disponíveis para filtro
    status_options = ['Em andamento', 'Concluída', 'Pausada', 'Cancelada']
    
    return render_template('obras.html', 
                         obras=obras,
                         filtros={
                             'nome': nome_filtro,
                             'status': status_filtro,
                             'data_inicio': data_inicio_filtro or data_inicio.strftime('%Y-%m-%d'),
                             'data_fim': data_fim_filtro or data_fim.strftime('%Y-%m-%d')
                         },
                         status_options=status_options)

@main_bp.route('/obras/novo', methods=['GET', 'POST'])
@login_required
def nova_obra():
    from models import Servico, ServicoObra
    import json
    
    form = ObraForm()
    form.responsavel_id.choices = [(0, 'Selecione...')] + [(f.id, f.nome) for f in Funcionario.query.filter_by(ativo=True).all()]
    
    if request.method == 'POST':
        if form.validate_on_submit():
            # Criar obra
            obra = Obra(
                nome=form.nome.data,
                endereco=form.endereco.data,
                data_inicio=form.data_inicio.data,
                data_previsao_fim=form.data_previsao_fim.data,
                orcamento=form.orcamento.data or 0.0,
                status=form.status.data,
                responsavel_id=form.responsavel_id.data if form.responsavel_id.data > 0 else None
            )
            db.session.add(obra)
            db.session.flush()  # Para obter o ID
            
            # Processar serviços da obra
            servicos_data = request.form.get('servicos_data')
            if servicos_data:
                try:
                    servicos_list = json.loads(servicos_data)
                    for servico_item in servicos_list:
                        if servico_item.get('servico_id') and servico_item.get('quantidade'):
                            servico_obra = ServicoObra(
                                obra_id=obra.id,
                                servico_id=int(servico_item['servico_id']),
                                quantidade_planejada=float(servico_item['quantidade']),
                                observacoes=servico_item.get('observacoes', '')
                            )
                            db.session.add(servico_obra)
                except (json.JSONDecodeError, ValueError) as e:
                    flash(f'Erro ao processar serviços: {str(e)}', 'warning')
            
            db.session.commit()
            flash('Obra cadastrada com sucesso!', 'success')
            return redirect(url_for('main.obras'))
    
    # Buscar dados para o formulário
    servicos = Servico.query.filter_by(ativo=True).order_by(Servico.categoria, Servico.nome).all()
    obras = Obra.query.all()
    
    return render_template('obras.html', 
                         form=form, 
                         obras=obras,
                         servicos=servicos)

# API para buscar serviços (para JavaScript)
@main_bp.route('/api/servicos')
@login_required
def api_servicos():
    from models import Servico
    servicos = Servico.query.filter_by(ativo=True).order_by(Servico.categoria, Servico.nome).all()
    
    return jsonify([{
        'id': s.id,
        'nome': s.nome,
        'categoria': s.categoria,
        'unidade_medida': s.unidade_medida,
        'unidade_simbolo': s.unidade_simbolo or s.unidade_medida,
        'custo_unitario': float(s.custo_unitario or 0)
    } for s in servicos])

# API removida - função duplicada

@main_bp.route('/obras/<int:id>/editar', methods=['GET', 'POST'])
@login_required
def editar_obra(id):
    obra = Obra.query.get_or_404(id)
    form = ObraForm(obj=obra)
    form.responsavel_id.choices = [(0, 'Selecione...')] + [(f.id, f.nome) for f in Funcionario.query.filter_by(ativo=True).all()]
    
    if form.validate_on_submit():
        obra.nome = form.nome.data
        obra.endereco = form.endereco.data
        obra.data_inicio = form.data_inicio.data
        obra.data_previsao_fim = form.data_previsao_fim.data
        obra.orcamento = form.orcamento.data or 0.0
        obra.status = form.status.data
        obra.responsavel_id = form.responsavel_id.data if form.responsavel_id.data > 0 else None
        
        db.session.commit()
        flash('Obra atualizada com sucesso!', 'success')
        return redirect(url_for('main.obras'))
    
    return render_template('obras.html', form=form, obra=obra, obras=Obra.query.all())

@main_bp.route('/obra/<int:id>')
@login_required
def detalhes_obra(id):
    from datetime import datetime, date, timedelta
    from sqlalchemy import func
    from models import ServicoObra, Servico
    
    obra = Obra.query.get_or_404(id)
    
    # Buscar serviços da obra
    servicos_obra = db.session.query(ServicoObra, Servico).join(
        Servico, ServicoObra.servico_id == Servico.id
    ).filter(
        ServicoObra.obra_id == id,
        ServicoObra.ativo == True
    ).order_by(Servico.categoria, Servico.nome).all()
    
    # Obter filtros de data da query string
    data_inicio_filtro = request.args.get('data_inicio')
    data_fim_filtro = request.args.get('data_fim')
    
    # Definir período padrão (mês atual)
    if not data_inicio_filtro:
        data_inicio = date.today().replace(day=1)
    else:
        data_inicio = datetime.strptime(data_inicio_filtro, '%Y-%m-%d').date()
    
    if not data_fim_filtro:
        data_fim = date.today()
    else:
        data_fim = datetime.strptime(data_fim_filtro, '%Y-%m-%d').date()
    
    # ===== CÁLCULO DOS KPIS =====
    
    # 1. Custos de Transporte (Veículos)
    # Por enquanto, vamos usar apenas custos de veículos sem vinculação específica à obra
    custo_transporte = db.session.query(func.sum(CustoVeiculo.valor)).filter(
        CustoVeiculo.data_custo.between(data_inicio, data_fim)
    ).scalar() or 0.0
    
    # 2. Custos de Alimentação
    custo_alimentacao = db.session.query(func.sum(RegistroAlimentacao.valor)).filter(
        RegistroAlimentacao.obra_id == id,
        RegistroAlimentacao.data.between(data_inicio, data_fim)
    ).scalar() or 0.0
    
    # 3. Custos de Mão de Obra
    # Buscar registros de ponto da obra no período
    registros_ponto = db.session.query(RegistroPonto).join(Funcionario).filter(
        RegistroPonto.obra_id == id,
        RegistroPonto.data.between(data_inicio, data_fim),
        RegistroPonto.hora_entrada.isnot(None)  # Só dias trabalhados
    ).all()
    
    custo_mao_obra = 0.0
    total_horas = 0.0
    dias_trabalhados = len(set(rp.data for rp in registros_ponto))
    
    for registro in registros_ponto:
        if registro.hora_entrada and registro.hora_saida:
            # Calcular horas trabalhadas
            entrada = datetime.combine(registro.data, registro.hora_entrada)
            saida = datetime.combine(registro.data, registro.hora_saida)
            
            # Subtrair tempo de almoço (1 hora padrão)
            horas_dia = (saida - entrada).total_seconds() / 3600 - 1
            horas_dia = max(0, horas_dia)  # Não pode ser negativo
            total_horas += horas_dia
            
            # Calcular custo baseado no salário do funcionário
            if registro.funcionario_ref.salario:
                valor_hora = registro.funcionario_ref.salario / 220  # 220 horas/mês aprox
                custo_mao_obra += horas_dia * valor_hora
    
    # 4. Custo Total da Obra
    custo_total = custo_transporte + custo_alimentacao + custo_mao_obra
    
    # ===== RDOs =====
    rdos_periodo = RDO.query.filter(
        RDO.obra_id == id,
        RDO.data_relatorio.between(data_inicio, data_fim)
    ).order_by(RDO.data_relatorio.desc()).all()
    
    rdos_recentes = RDO.query.filter_by(obra_id=id).order_by(RDO.data_relatorio.desc()).limit(5).all()
    total_rdos = RDO.query.filter_by(obra_id=id).count()
    rdos_finalizados = RDO.query.filter_by(obra_id=id, status='Finalizado').count()
    
    # ===== MÉTRICAS ADICIONAIS =====
    
    # Progresso da obra
    progresso_obra = 0
    if total_rdos > 0:
        progresso_obra = min(100, (rdos_finalizados / total_rdos) * 100)
    
    # Calcular dias da obra
    hoje = date.today()
    dias_decorridos = (hoje - obra.data_inicio).days if obra.data_inicio else 0
    dias_restantes = 0
    if obra.data_previsao_fim:
        dias_restantes = max(0, (obra.data_previsao_fim - hoje).days)
    
    # Funcionários únicos que trabalharam na obra no período
    funcionarios_periodo = db.session.query(Funcionario).join(RegistroPonto).filter(
        RegistroPonto.obra_id == id,
        RegistroPonto.data.between(data_inicio, data_fim),
        RegistroPonto.hora_entrada.isnot(None)
    ).distinct().all()
    
    # Custos da obra no período
    custos_obra = CustoObra.query.filter(
        CustoObra.obra_id == id,
        CustoObra.data.between(data_inicio, data_fim)
    ).order_by(CustoObra.data.desc()).all()
    
    # ===== CUSTOS DE TRANSPORTE DETALHADOS =====
    custos_transporte = db.session.query(CustoVeiculo).filter(
        CustoVeiculo.data_custo.between(data_inicio, data_fim)
    ).order_by(CustoVeiculo.data_custo.desc()).all()
    
    custos_transporte_total = sum(c.valor for c in custos_transporte)
    
    # ===== CUSTOS DE MÃO DE OBRA DETALHADOS =====
    custos_mao_obra = []
    for registro in registros_ponto:
        if registro.hora_entrada and registro.hora_saida:
            # Calcular horas trabalhadas
            entrada = datetime.combine(registro.data, registro.hora_entrada)
            saida = datetime.combine(registro.data, registro.hora_saida)
            
            # Subtrair tempo de almoço (1 hora padrão)
            horas_dia = (saida - entrada).total_seconds() / 3600 - 1
            horas_dia = max(0, horas_dia)  # Não pode ser negativo
            
            # Calcular custo baseado no salário do funcionário
            if registro.funcionario_ref.salario:
                valor_hora = registro.funcionario_ref.salario / 220  # 220 horas/mês aprox
                total_dia = horas_dia * valor_hora
                
                custos_mao_obra.append({
                    'data': registro.data,
                    'funcionario_nome': registro.funcionario_ref.nome,
                    'horas_trabalhadas': horas_dia,
                    'salario_hora': valor_hora,
                    'total_dia': total_dia
                })
    
    # KPIs organizados
    kpis = {
        'custo_transporte': custo_transporte,
        'custo_alimentacao': custo_alimentacao,
        'custo_mao_obra': custo_mao_obra,
        'custo_total': custo_total,
        'dias_trabalhados': dias_trabalhados,
        'total_horas': round(total_horas, 1),
        'funcionarios_periodo': len(funcionarios_periodo),
        'rdos_periodo': len(rdos_periodo)
    }
    
    return render_template('obras/detalhes_obra.html', 
                         obra=obra,
                         servicos_obra=servicos_obra,
                         kpis=kpis,
                         custos_obra=custos_obra,
                         custos_transporte=custos_transporte,
                         custos_transporte_total=custos_transporte_total,
                         custos_mao_obra=custos_mao_obra,
                         rdos_periodo=rdos_periodo,
                         rdos_recentes=rdos_recentes,
                         total_rdos=total_rdos,
                         rdos_finalizados=rdos_finalizados,
                         progresso_obra=int(progresso_obra),
                         dias_decorridos=dias_decorridos,
                         dias_restantes=dias_restantes,
                         funcionarios_periodo=funcionarios_periodo,
                         data_inicio=data_inicio,
                         data_fim=data_fim)

@main_bp.route('/obras/<int:id>/excluir', methods=['POST'])
@login_required
def excluir_obra(id):
    obra = Obra.query.get_or_404(id)
    db.session.delete(obra)
    db.session.commit()
    flash('Obra excluída com sucesso!', 'success')
    return redirect(url_for('main.obras'))

# Veículos
@main_bp.route('/veiculos')
@login_required
def veiculos():
    veiculos = Veiculo.query.all()
    funcionarios = Funcionario.query.filter_by(ativo=True).all()
    obras = Obra.query.filter_by(status='Em andamento').all()
    return render_template('veiculos.html', 
                         veiculos=veiculos, 
                         funcionarios=funcionarios, 
                         obras=obras)

@main_bp.route('/veiculos/novo', methods=['GET', 'POST'])
@login_required
def novo_veiculo():
    form = VeiculoForm()
    if form.validate_on_submit():
        veiculo = Veiculo(
            placa=form.placa.data,
            marca=form.marca.data,
            modelo=form.modelo.data,
            ano=form.ano.data,
            tipo=form.tipo.data,
            status=form.status.data,
            km_atual=form.km_atual.data or 0,
            data_ultima_manutencao=form.data_ultima_manutencao.data,
            data_proxima_manutencao=form.data_proxima_manutencao.data
        )
        db.session.add(veiculo)
        db.session.commit()
        flash('Veículo cadastrado com sucesso!', 'success')
        return redirect(url_for('main.veiculos'))
    
    return render_template('veiculos.html', form=form, veiculos=Veiculo.query.all())

@main_bp.route('/veiculos/<int:id>/editar', methods=['GET', 'POST'])
@login_required
def editar_veiculo(id):
    veiculo = Veiculo.query.get_or_404(id)
    form = VeiculoForm(obj=veiculo)
    
    if form.validate_on_submit():
        veiculo.placa = form.placa.data
        veiculo.marca = form.marca.data
        veiculo.modelo = form.modelo.data
        veiculo.ano = form.ano.data
        veiculo.tipo = form.tipo.data
        veiculo.status = form.status.data
        veiculo.km_atual = form.km_atual.data or 0
        veiculo.data_ultima_manutencao = form.data_ultima_manutencao.data
        veiculo.data_proxima_manutencao = form.data_proxima_manutencao.data
        
        db.session.commit()
        flash('Veículo atualizado com sucesso!', 'success')
        return redirect(url_for('main.veiculos'))
    
    return render_template('veiculos.html', form=form, veiculo=veiculo, veiculos=Veiculo.query.all())

@main_bp.route('/veiculos/<int:id>/excluir', methods=['POST'])
@login_required
def excluir_veiculo(id):
    veiculo = Veiculo.query.get_or_404(id)
    db.session.delete(veiculo)
    db.session.commit()
    flash('Veículo excluído com sucesso!', 'success')
    return redirect(url_for('main.veiculos'))

@main_bp.route('/veiculos/<int:id>/detalhes')
@login_required
def detalhes_veiculo(id):
    veiculo = Veiculo.query.get_or_404(id)
    
    # Buscar registros de uso
    usos = UsoVeiculo.query.filter_by(veiculo_id=id).order_by(UsoVeiculo.data_uso.desc()).all()
    
    # Buscar registros de custo
    custos = CustoVeiculo.query.filter_by(veiculo_id=id).order_by(CustoVeiculo.data_custo.desc()).all()
    
    # Dados para os formulários
    funcionarios = Funcionario.query.filter_by(ativo=True).order_by(Funcionario.nome).all()
    obras = Obra.query.filter(Obra.status.in_(['Em andamento', 'Pausada'])).order_by(Obra.nome).all()
    
    # KPIs do veículo
    custo_total = sum(custo.valor for custo in custos)
    kpis = {
        'custo_total': custo_total,
        'total_usos': len(usos),
        'total_custos': len(custos)
    }
    
    # Dados para gráfico de uso por obra
    from sqlalchemy import func
    uso_por_obra = db.session.query(
        Obra.nome,
        func.count(UsoVeiculo.id).label('total_usos')
    ).join(UsoVeiculo, Obra.id == UsoVeiculo.obra_id).filter(
        UsoVeiculo.veiculo_id == id
    ).group_by(Obra.id, Obra.nome).all()
    
    # Preparar dados para o gráfico de pizza
    grafico_uso_obras = {
        'labels': [uso[0] for uso in uso_por_obra],
        'data': [uso[1] for uso in uso_por_obra],
        'total': sum([uso[1] for uso in uso_por_obra])
    }
    
    return render_template('detalhes_veiculo.html', 
                         veiculo=veiculo, 
                         usos=usos, 
                         custos=custos,
                         kpis=kpis,
                         funcionarios=funcionarios,
                         obras=obras,
                         grafico_uso_obras=grafico_uso_obras)

@main_bp.route('/veiculos/novo-uso-direto', methods=['POST'])
@login_required
def novo_uso_veiculo_direto():
    """Registra novo uso de veículo na página de detalhes"""
    try:
        veiculo_id = request.form.get('veiculo_id')
        funcionario_id = request.form.get('funcionario_id')
        obra_id = request.form.get('obra_id')
        data_uso = datetime.strptime(request.form.get('data_uso'), '%Y-%m-%d').date()
        km_inicial = int(request.form.get('km_inicial')) if request.form.get('km_inicial') else None
        km_final = int(request.form.get('km_final')) if request.form.get('km_final') else None
        horario_saida = datetime.strptime(request.form.get('horario_saida'), '%H:%M').time() if request.form.get('horario_saida') else None
        horario_chegada = datetime.strptime(request.form.get('horario_chegada'), '%H:%M').time() if request.form.get('horario_chegada') else None
        finalidade = request.form.get('finalidade')
        observacoes = request.form.get('observacoes')
        
        if not obra_id:
            flash('Obra é obrigatória para registrar uso do veículo!', 'error')
            return redirect(url_for('main.detalhes_veiculo', id=veiculo_id))
        
        novo_uso = UsoVeiculo(
            veiculo_id=veiculo_id,
            funcionario_id=funcionario_id,
            obra_id=obra_id,
            data_uso=data_uso,
            km_inicial=km_inicial,
            km_final=km_final,
            horario_saida=horario_saida,
            horario_chegada=horario_chegada,
            finalidade=finalidade,
            observacoes=observacoes
        )
        
        db.session.add(novo_uso)
        
        # Atualizar KM do veículo se fornecido
        if km_final:
            veiculo = Veiculo.query.get(veiculo_id)
            if veiculo:
                veiculo.km_atual = km_final
        
        db.session.commit()
        
        flash('Uso do veículo registrado com sucesso!', 'success')
    except Exception as e:
        flash(f'Erro ao registrar uso: {str(e)}', 'error')
    
    return redirect(url_for('main.detalhes_veiculo', id=veiculo_id))

@main_bp.route('/veiculos/novo-custo', methods=['POST'])
@login_required
def novo_custo_veiculo():
    """Registra novo custo de veículo"""
    try:
        veiculo_id = request.form.get('veiculo_id')
        data_custo = datetime.strptime(request.form.get('data_custo'), '%Y-%m-%d').date()
        valor = float(request.form.get('valor'))
        tipo_custo = request.form.get('tipo_custo')
        obra_id = request.form.get('obra_id')
        fornecedor = request.form.get('fornecedor')
        descricao = request.form.get('descricao')
        
        if not obra_id:
            flash('Obra é obrigatória para registrar custo do veículo!', 'error')
            return redirect(url_for('main.detalhes_veiculo', id=veiculo_id))
        
        novo_custo = CustoVeiculo(
            veiculo_id=veiculo_id,
            data_custo=data_custo,
            valor=valor,
            tipo_custo=tipo_custo,
            obra_id=obra_id,
            fornecedor=fornecedor,
            descricao=descricao
        )
        
        db.session.add(novo_custo)
        db.session.commit()
        
        flash('Custo do veículo registrado com sucesso!', 'success')
    except Exception as e:
        flash(f'Erro ao registrar custo: {str(e)}', 'error')
    
    return redirect(url_for('main.detalhes_veiculo', id=veiculo_id))

@main_bp.route('/veiculos/<int:id>/dados')
@login_required
def dados_veiculo(id):
    """Retorna dados do veículo em JSON para edição via AJAX"""
    veiculo = Veiculo.query.get_or_404(id)
    return jsonify({
        'id': veiculo.id,
        'placa': veiculo.placa,
        'marca': veiculo.marca,
        'modelo': veiculo.modelo,
        'ano': veiculo.ano,
        'tipo': veiculo.tipo,
        'km_atual': veiculo.km_atual,
        'status': veiculo.status,
        'data_ultima_manutencao': veiculo.data_ultima_manutencao.strftime('%Y-%m-%d') if veiculo.data_ultima_manutencao else '',
        'data_proxima_manutencao': veiculo.data_proxima_manutencao.strftime('%Y-%m-%d') if veiculo.data_proxima_manutencao else ''
    })

@main_bp.route('/veiculos/uso', methods=['POST'])
@login_required
def novo_uso_veiculo():
    """Registra novo uso de veículo"""
    form = UsoVeiculoForm()
    
    # Preencher choices dinamicamente
    form.veiculo_id.choices = [(0, 'Selecione...')] + [(v.id, f"{v.placa} - {v.marca} {v.modelo}") for v in Veiculo.query.filter_by(status='Disponível').all()]
    form.funcionario_id.choices = [(0, 'Selecione...')] + [(f.id, f.nome) for f in Funcionario.query.filter_by(ativo=True).all()]
    form.obra_id.choices = [(0, 'Selecione...')] + [(o.id, o.nome) for o in Obra.query.all()]
    
    if form.validate_on_submit():
        uso = UsoVeiculo(
            veiculo_id=form.veiculo_id.data,
            funcionario_id=form.funcionario_id.data,
            obra_id=form.obra_id.data if form.obra_id.data else None,
            data_uso=form.data_uso.data,
            km_inicial=form.km_inicial.data,
            km_final=form.km_final.data,
            finalidade=form.finalidade.data,
            observacoes=form.observacoes.data
        )
        db.session.add(uso)
        
        # Atualizar status do veículo para "Em uso"
        veiculo = Veiculo.query.get(form.veiculo_id.data)
        if veiculo:
            veiculo.status = 'Em uso'
            # Atualizar KM se fornecido
            if form.km_final.data:
                veiculo.km_atual = form.km_final.data
        
        db.session.commit()
        flash('Uso de veículo registrado com sucesso!', 'success')
    else:
        flash('Erro ao registrar uso do veículo. Verifique os dados.', 'error')
    
    return redirect(url_for('main.veiculos'))

@main_bp.route('/veiculos/custo', methods=['POST'])
@login_required
def novo_custo_veiculo_lista():
    """Registra novo custo de veículo a partir da lista principal"""
    form = CustoVeiculoForm()
    
    # Preencher choices dinamicamente
    form.veiculo_id.choices = [(0, 'Selecione...')] + [(v.id, f"{v.placa} - {v.marca} {v.modelo}") for v in Veiculo.query.all()]
    
    if form.validate_on_submit():
        custo = CustoVeiculo(
            veiculo_id=form.veiculo_id.data,
            data_custo=form.data_custo.data,
            valor=form.valor.data,
            tipo_custo=form.tipo_custo.data,
            descricao=form.descricao.data,
            km_atual=form.km_atual.data,
            fornecedor=form.fornecedor.data
        )
        db.session.add(custo)
        
        # Atualizar KM do veículo se fornecido
        if form.km_atual.data:
            veiculo = Veiculo.query.get(form.veiculo_id.data)
            if veiculo:
                veiculo.km_atual = form.km_atual.data
        
        db.session.commit()
        flash('Custo de veículo registrado com sucesso!', 'success')
    else:
        flash('Erro ao registrar custo do veículo. Verifique os dados.', 'error')
    
    return redirect(url_for('main.veiculos'))

# ============================================================================
# MÓDULO DE SERVIÇOS - SIGE v6.3
# Sistema de cadastro de serviços para coleta de dados reais via RDO
# ============================================================================

@main_bp.route('/servicos')
@login_required
def servicos():
    """Página de listagem de serviços com filtros"""
    # Filtros
    categoria = request.args.get('categoria')
    ativo = request.args.get('ativo')
    
    # Query base
    query = Servico.query
    
    # Aplicar filtros
    if categoria:
        query = query.filter(Servico.categoria == categoria)
    if ativo:
        query = query.filter(Servico.ativo == (ativo == 'true'))
    
    # Ordenar e buscar
    servicos = query.order_by(Servico.nome).all()
    
    # Dados para filtros
    categorias = db.session.query(Servico.categoria).distinct().all()
    categorias = [cat[0] for cat in categorias if cat[0]]
    
    return render_template('servicos.html', 
                         servicos=servicos, 
                         categorias=categorias,
                         filtros={'categoria': categoria, 'ativo': ativo})

@main_bp.route('/api/servicos', methods=['POST'])
@login_required
def api_criar_servico():
    """API para criar serviço com subatividades"""
    try:
        dados = request.get_json()
        
        # Validar dados obrigatórios
        if not dados.get('nome') or not dados.get('categoria') or not dados.get('unidade_medida'):
            return jsonify({'success': False, 'message': 'Campos obrigatórios não preenchidos'})
        
        # Verificar se já existe serviço com mesmo nome
        servico_existente = Servico.query.filter_by(nome=dados['nome']).first()
        if servico_existente:
            return jsonify({'success': False, 'message': 'Já existe um serviço com este nome'})
        
        # Criar serviço
        servico = Servico(
            nome=dados['nome'],
            descricao=dados.get('descricao', ''),
            categoria=dados['categoria'],
            unidade_medida=dados['unidade_medida'],
            complexidade=int(dados.get('complexidade', 3)),
            requer_especializacao=dados.get('requer_especializacao', False),
            ativo=True
        )
        
        db.session.add(servico)
        db.session.flush()  # Para obter o ID do serviço
        
        # Criar subatividades
        for i, sub_dados in enumerate(dados.get('subatividades', [])):
            if sub_dados.get('nome'):
                subatividade = SubAtividade(
                    servico_id=servico.id,
                    nome=sub_dados['nome'],
                    descricao=sub_dados.get('descricao', ''),
                    ordem_execucao=i + 1,
                    ferramentas_necessarias=sub_dados.get('ferramentas_necessarias', ''),
                    materiais_principais=sub_dados.get('materiais_principais', ''),
                    requer_aprovacao=sub_dados.get('requer_aprovacao', False),
                    pode_executar_paralelo=sub_dados.get('pode_executar_paralelo', True),
                    qualificacao_minima=sub_dados.get('qualificacao_minima', ''),
                    ativo=True
                )
                db.session.add(subatividade)
        
        db.session.commit()
        
        return jsonify({
            'success': True, 
            'message': 'Serviço criado com sucesso!',
            'servico_id': servico.id
        })
        
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'message': f'Erro ao criar serviço: {str(e)}'})

@main_bp.route('/api/servicos/<int:id>', methods=['GET'])
@login_required
def api_obter_servico(id):
    """API para obter dados de um serviço com subatividades"""
    try:
        servico = Servico.query.get_or_404(id)
        
        # Buscar subatividades
        subatividades = SubAtividade.query.filter_by(servico_id=id).order_by(SubAtividade.ordem_execucao).all()
        
        dados = {
            'id': servico.id,
            'nome': servico.nome,
            'descricao': servico.descricao,
            'categoria': servico.categoria,
            'unidade_medida': servico.unidade_medida,
            'complexidade': servico.complexidade,
            'requer_especializacao': servico.requer_especializacao,
            'ativo': servico.ativo,
            'subatividades': []
        }
        
        for sub in subatividades:
            dados['subatividades'].append({
                'id': sub.id,
                'nome': sub.nome,
                'descricao': sub.descricao,
                'ordem_execucao': sub.ordem_execucao,
                'ferramentas_necessarias': sub.ferramentas_necessarias,
                'materiais_principais': sub.materiais_principais,
                'requer_aprovacao': sub.requer_aprovacao,
                'pode_executar_paralelo': sub.pode_executar_paralelo,
                'qualificacao_minima': sub.qualificacao_minima
            })
        
        return jsonify({'success': True, 'dados': dados})
        
    except Exception as e:
        return jsonify({'success': False, 'message': f'Erro ao obter serviço: {str(e)}'})

@main_bp.route('/api/servicos/<int:id>', methods=['PUT'])
@login_required
def api_atualizar_servico(id):
    """API para atualizar serviço com subatividades"""
    try:
        servico = Servico.query.get_or_404(id)
        dados = request.get_json()
        
        # Validar dados obrigatórios
        if not dados.get('nome') or not dados.get('categoria') or not dados.get('unidade_medida'):
            return jsonify({'success': False, 'message': 'Campos obrigatórios não preenchidos'})
        
        # Verificar se já existe outro serviço com mesmo nome
        servico_existente = Servico.query.filter(
            Servico.nome == dados['nome'],
            Servico.id != id
        ).first()
        if servico_existente:
            return jsonify({'success': False, 'message': 'Já existe um serviço com este nome'})
        
        # Atualizar serviço
        servico.nome = dados['nome']
        servico.descricao = dados.get('descricao', '')
        servico.categoria = dados['categoria']
        servico.unidade_medida = dados['unidade_medida']
        servico.complexidade = int(dados.get('complexidade', 3))
        servico.requer_especializacao = dados.get('requer_especializacao', False)
        servico.updated_at = datetime.utcnow()
        
        # Remover subatividades antigas
        SubAtividade.query.filter_by(servico_id=id).delete()
        
        # Criar novas subatividades
        for i, sub_dados in enumerate(dados.get('subatividades', [])):
            if sub_dados.get('nome'):
                subatividade = SubAtividade(
                    servico_id=servico.id,
                    nome=sub_dados['nome'],
                    descricao=sub_dados.get('descricao', ''),
                    ordem_execucao=i + 1,
                    ferramentas_necessarias=sub_dados.get('ferramentas_necessarias', ''),
                    materiais_principais=sub_dados.get('materiais_principais', ''),
                    requer_aprovacao=sub_dados.get('requer_aprovacao', False),
                    pode_executar_paralelo=sub_dados.get('pode_executar_paralelo', True),
                    qualificacao_minima=sub_dados.get('qualificacao_minima', ''),
                    ativo=True
                )
                db.session.add(subatividade)
        
        db.session.commit()
        
        return jsonify({
            'success': True, 
            'message': 'Serviço atualizado com sucesso!'
        })
        
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'message': f'Erro ao atualizar serviço: {str(e)}'})

@main_bp.route('/api/servicos/<int:id>', methods=['DELETE'])
@login_required
def api_excluir_servico(id):
    """API para excluir serviço"""
    try:
        servico = Servico.query.get_or_404(id)
        
        # Verificar se há histórico de produtividade
        historico_count = HistoricoProdutividadeServico.query.filter_by(servico_id=id).count()
        if historico_count > 0:
            return jsonify({
                'success': False, 
                'message': f'Não é possível excluir. Existem {historico_count} registros de produtividade vinculados a este serviço.'
            })
        
        db.session.delete(servico)
        db.session.commit()
        
        return jsonify({
            'success': True, 
            'message': 'Serviço excluído com sucesso!'
        })
        
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'message': f'Erro ao excluir serviço: {str(e)}'})

@main_bp.route('/api/servicos/<int:id>/toggle-ativo', methods=['POST'])
@login_required
def api_toggle_ativo_servico(id):
    """API para ativar/desativar serviço"""
    try:
        servico = Servico.query.get_or_404(id)
        servico.ativo = not servico.ativo
        servico.updated_at = datetime.utcnow()
        
        db.session.commit()
        
        status = 'ativado' if servico.ativo else 'desativado'
        return jsonify({
            'success': True, 
            'message': f'Serviço {status} com sucesso!',
            'ativo': servico.ativo
        })
        
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'message': f'Erro ao alterar status: {str(e)}'})

@main_bp.route('/api/servicos/<int:id>/produtividade', methods=['GET'])
@login_required
def api_produtividade_servico(id):
    """API para obter dados de produtividade do serviço"""
    try:
        servico = Servico.query.get_or_404(id)
        
        # Buscar histórico de produtividade
        historicos = HistoricoProdutividadeServico.query.filter_by(servico_id=id).all()
        
        if not historicos:
            return jsonify({
                'success': True,
                'dados': {
                    'servico': servico.nome,
                    'unidade_medida': servico.unidade_medida,
                    'total_execucoes': 0,
                    'estimativas': None,
                    'historico': []
                }
            })
        
        # Calcular estimativas
        tempo_medio = sum(float(h.tempo_execucao_horas) for h in historicos) / len(historicos)
        custo_medio = sum(float(h.custo_mao_obra_real) for h in historicos) / len(historicos)
        produtividade_media = sum(float(h.produtividade_hora) for h in historicos) / len(historicos)
        
        dados = {
            'servico': servico.nome,
            'unidade_medida': servico.unidade_medida,
            'total_execucoes': len(historicos),
            'estimativas': {
                'tempo_medio_por_unidade': round(tempo_medio, 2),
                'custo_medio_por_unidade': round(custo_medio, 2),
                'produtividade_media': round(produtividade_media, 4)
            },
            'historico': []
        }
        
        # Histórico detalhado
        for h in historicos[-10:]:  # Últimos 10 registros
            dados['historico'].append({
                'data': h.data_execucao.strftime('%d/%m/%Y'),
                'obra': h.obra.nome,
                'funcionario': h.funcionario.nome,
                'quantidade': float(h.quantidade_executada),
                'tempo_horas': float(h.tempo_execucao_horas),
                'custo_real': float(h.custo_mao_obra_real),
                'produtividade': float(h.produtividade_hora)
            })
        
        return jsonify({'success': True, 'dados': dados})
        
    except Exception as e:
        return jsonify({'success': False, 'message': f'Erro ao obter produtividade: {str(e)}'})

# ============================================================================
# API ENDPOINTS PARA DROPDOWNS INTELIGENTES - RDO OPERACIONAL
# ============================================================================

@main_bp.route('/api/obras/autocomplete')
@login_required
def obras_autocomplete():
    """API para autocomplete de obras"""
    q = request.args.get('q', '')
    obras = Obra.query.filter(
        or_(
            Obra.nome.ilike(f'%{q}%'),
            Obra.codigo.ilike(f'%{q}%'),
            Obra.endereco.ilike(f'%{q}%')
        )
    ).filter(Obra.ativo == True).limit(10).all()
    
    return jsonify([{
        'id': obra.id,
        'nome': obra.nome,
        'codigo': obra.codigo,
        'endereco': obra.endereco,
        'area_total_m2': float(obra.area_total_m2) if obra.area_total_m2 else 0
    } for obra in obras])

@main_bp.route('/api/servicos/autocomplete')
@login_required
def servicos_autocomplete():
    """API para autocomplete de serviços"""
    q = request.args.get('q', '')
    servicos = Servico.query.filter(
        or_(
            Servico.nome.ilike(f'%{q}%'),
            Servico.categoria.ilike(f'%{q}%')
        )
    ).filter(Servico.ativo == True).limit(10).all()
    
    return jsonify([{
        'id': servico.id,
        'nome': servico.nome,
        'categoria': servico.categoria,
        'unidade_medida': servico.unidade_medida,
        'unidade_simbolo': get_simbolo_unidade(servico.unidade_medida),
        'complexidade': servico.complexidade
    } for servico in servicos])

@main_bp.route('/api/servicos/<int:servico_id>/subatividades')
@login_required
def api_subatividades_servico(servico_id):
    """API para buscar subatividades de um serviço"""
    subatividades = SubAtividade.query.filter_by(servico_id=servico_id, ativo=True).order_by(SubAtividade.ordem_execucao).all()
    
    return jsonify({
        'success': True,
        'subatividades': [{
            'id': sub.id,
            'nome': sub.nome,
            'descricao': sub.descricao,
            'ordem_execucao': sub.ordem_execucao,
            'ferramentas_necessarias': sub.ferramentas_necessarias,
            'materiais_principais': sub.materiais_principais,
            'requer_aprovacao': sub.requer_aprovacao,
            'pode_executar_paralelo': sub.pode_executar_paralelo,
            'qualificacao_minima': sub.qualificacao_minima
        } for sub in subatividades]
    })

@main_bp.route('/api/funcionarios/autocomplete')
@login_required
def funcionarios_autocomplete():
    """API para autocomplete de funcionários"""
    q = request.args.get('q', '')
    funcionarios = Funcionario.query.filter(
        or_(
            Funcionario.nome.ilike(f'%{q}%'),
            Funcionario.codigo.ilike(f'%{q}%')
        )
    ).filter(Funcionario.ativo == True).limit(10).all()
    
    return jsonify([{
        'id': funcionario.id,
        'nome': funcionario.nome,
        'codigo': funcionario.codigo,
        'funcao': funcionario.funcao_ref.nome if funcionario.funcao_ref else 'Sem função',
        'entrada': funcionario.horario_trabalho.entrada.strftime('%H:%M') if funcionario.horario_trabalho else '07:00',
        'saida': funcionario.horario_trabalho.saida.strftime('%H:%M') if funcionario.horario_trabalho else '17:00'
    } for funcionario in funcionarios])

@main_bp.route('/api/equipamentos/autocomplete')
@login_required
def equipamentos_autocomplete():
    """API para autocomplete de equipamentos/veículos"""
    q = request.args.get('q', '')
    veiculos = Veiculo.query.filter(
        or_(
            Veiculo.nome.ilike(f'%{q}%'),
            Veiculo.placa.ilike(f'%{q}%'),
            Veiculo.tipo.ilike(f'%{q}%')
        )
    ).filter(Veiculo.ativo == True).limit(10).all()
    
    return jsonify([{
        'id': veiculo.id,
        'nome': veiculo.nome,
        'placa': veiculo.placa,
        'tipo': veiculo.tipo,
        'status': veiculo.status
    } for veiculo in veiculos])

@main_bp.route('/api/servicos/<int:servico_id>')
@login_required
def servico_detalhes(servico_id):
    """API para obter detalhes de um serviço com subatividades"""
    servico = Servico.query.get_or_404(servico_id)
    subatividades = SubAtividade.query.filter_by(
        servico_id=servico_id, 
        ativo=True
    ).order_by(SubAtividade.ordem_execucao).all()
    
    return jsonify({
        'id': servico.id,
        'nome': servico.nome,
        'unidade_medida': servico.unidade_medida,
        'unidade_simbolo': get_simbolo_unidade(servico.unidade_medida),
        'subatividades': [{
            'id': sub.id,
            'nome': sub.nome,
            'descricao': sub.descricao,
            'ordem_execucao': sub.ordem_execucao
        } for sub in subatividades]
    })

@main_bp.route('/api/rdo/salvar', methods=['POST'])
@login_required
def salvar_rdo():
    """API para salvar RDO como rascunho"""
    try:
        dados = request.get_json()
        
        # Validações básicas
        if not dados.get('data_relatorio') or not dados.get('obra_id'):
            return jsonify({'success': False, 'message': 'Data e obra são obrigatórias'})
        
        # Verificar se já existe RDO para esta data/obra
        rdo_existente = RDO.query.filter_by(
            data_relatorio=datetime.strptime(dados['data_relatorio'], '%Y-%m-%d').date(),
            obra_id=dados['obra_id'],
            funcionario_id=current_user.id
        ).first()
        
        if rdo_existente:
            # Atualizar RDO existente
            rdo = rdo_existente
        else:
            # Criar novo RDO
            rdo = RDO(
                data_relatorio=datetime.strptime(dados['data_relatorio'], '%Y-%m-%d').date(),
                obra_id=dados['obra_id'],
                funcionario_id=current_user.id
            )
        
        # Atualizar dados do RDO
        rdo.tempo_manha = dados.get('tempo_manha', '')
        rdo.tempo_tarde = dados.get('tempo_tarde', '')
        rdo.tempo_noite = dados.get('tempo_noite', '')
        rdo.observacoes_meteorologicas = dados.get('observacoes_meteorologicas', '')
        rdo.comentario_geral = dados.get('comentario_geral', '')
        rdo.status = dados.get('status', 'Rascunho')
        
        db.session.add(rdo)
        db.session.flush()
        
        # Salvar dados das seções (JSON por simplicidade)
        rdo.dados_funcionarios = json.dumps(dados.get('funcionarios', []))
        rdo.dados_atividades = json.dumps(dados.get('atividades', []))
        rdo.dados_equipamentos = json.dumps(dados.get('equipamentos', []))
        rdo.dados_ocorrencias = json.dumps(dados.get('ocorrencias', []))
        
        db.session.commit()
        
        return jsonify({
            'success': True,
            'message': 'RDO salvo com sucesso!',
            'rdo_id': rdo.id
        })
        
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'message': f'Erro ao salvar RDO: {str(e)}'})

@main_bp.route('/api/rdo/finalizar', methods=['POST'])
@login_required
def finalizar_rdo():
    """API para finalizar RDO"""
    try:
        dados = request.get_json()
        
        # Primeiro salvar como rascunho
        resultado_salvar = salvar_rdo()
        if not resultado_salvar.get_json()['success']:
            return resultado_salvar
        
        # Buscar RDO salvo
        rdo = RDO.query.filter_by(
            data_relatorio=datetime.strptime(dados['data_relatorio'], '%Y-%m-%d').date(),
            obra_id=dados['obra_id'],
            funcionario_id=current_user.id
        ).first()
        
        if not rdo:
            return jsonify({'success': False, 'message': 'RDO não encontrado'})
        
        # Atualizar status
        rdo.status = 'Finalizado'
        
        # Processar dados de produtividade
        processar_dados_produtividade(rdo.id)
        
        db.session.commit()
        
        return jsonify({
            'success': True,
            'message': 'RDO finalizado com sucesso!',
            'rdo_id': rdo.id
        })
        
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'message': f'Erro ao finalizar RDO: {str(e)}'})

# Função auxiliar para processar dados de produtividade (chamada pelos RDOs)
def processar_dados_produtividade(rdo_id):
    """Processa dados do RDO e gera histórico de produtividade"""
    try:
        rdo = RDO.query.get(rdo_id)
        if not rdo:
            return
        
        # Processar dados de atividades
        if rdo.dados_atividades:
            atividades = json.loads(rdo.dados_atividades)
            
            for atividade in atividades:
                if atividade.get('servico_id') and atividade.get('quantidade'):
                    # Calcular custo baseado nos funcionários que trabalharam
                    custo_total = 0
                    if rdo.dados_funcionarios:
                        funcionarios = json.loads(rdo.dados_funcionarios)
                        for func in funcionarios:
                            if func.get('funcionario_id') and func.get('horas'):
                                funcionario = Funcionario.query.get(func['funcionario_id'])
                                if funcionario:
                                    custo_hora = float(funcionario.salario) / 220  # 220 horas/mês
                                    custo_total += custo_hora * float(func['horas'])
                    
                    # Criar registro de produtividade
                    historico = HistoricoProdutividadeServico(
                        servico_id=atividade['servico_id'],
                        obra_id=rdo.obra_id,
                        funcionario_id=rdo.funcionario_id,
                        data_execucao=rdo.data_relatorio,
                        quantidade_executada=float(atividade['quantidade']),
                        tempo_execucao_horas=float(atividade.get('tempo', 0)),
                        custo_mao_obra_real=custo_total,
                        produtividade_hora=float(atividade['quantidade']) / max(float(atividade.get('tempo', 1)), 1)
                    )
                    
                    db.session.add(historico)
        
        db.session.commit()
        
    except Exception as e:
        print(f"Erro ao processar dados de produtividade: {str(e)}")

def get_simbolo_unidade(unidade_medida):
    """Retorna o símbolo da unidade de medida"""
    simbolos = {
        'm2': 'm²',
        'm3': 'm³',
        'kg': 'kg',
        'ton': 'ton',
        'un': 'un',
        'm': 'm',
        'h': 'h'
    }
    return simbolos.get(unidade_medida, unidade_medida)

# Ponto
@main_bp.route('/ponto')
@login_required
def ponto():
    registros = RegistroPonto.query.order_by(RegistroPonto.data.desc()).limit(50).all()
    return render_template('ponto.html', registros=registros)

@main_bp.route('/ponto/novo', methods=['GET', 'POST'])
@login_required
def novo_ponto_lista():
    form = RegistroPontoForm()
    form.funcionario_id.choices = [(f.id, f.nome) for f in Funcionario.query.filter_by(ativo=True).all()]
    form.obra_id.choices = [(0, 'Selecione...')] + [(o.id, o.nome) for o in Obra.query.filter_by(status='Em andamento').all()]
    
    if form.validate_on_submit():
        registro = RegistroPonto(
            funcionario_id=form.funcionario_id.data,
            obra_id=form.obra_id.data if form.obra_id.data > 0 else None,
            data=form.data.data,
            hora_entrada=form.hora_entrada.data,
            hora_saida=form.hora_saida.data,
            hora_almoco_saida=form.hora_almoco_saida.data,
            hora_almoco_retorno=form.hora_almoco_retorno.data,
            observacoes=form.observacoes.data
        )
        
        # Calcular horas trabalhadas
        if registro.hora_entrada and registro.hora_saida:
            horas_trabalhadas = calcular_horas_trabalhadas(
                registro.hora_entrada, registro.hora_saida,
                registro.hora_almoco_saida, registro.hora_almoco_retorno
            )
            registro.horas_trabalhadas = horas_trabalhadas['total']
            registro.horas_extras = horas_trabalhadas['extras']
        
        db.session.add(registro)
        db.session.commit()
        
        # Atualizar cálculos automáticos do registro
        from kpis_engine import atualizar_calculos_ponto
        atualizar_calculos_ponto(registro.id)
        
        flash('Registro de ponto adicionado com sucesso!', 'success')
        return redirect(url_for('main.ponto'))
    
    return render_template('ponto.html', form=form, registros=RegistroPonto.query.order_by(RegistroPonto.data.desc()).limit(50).all())

# Alimentação
@main_bp.route('/alimentacao')
@login_required
def alimentacao():
    from datetime import date
    registros = RegistroAlimentacao.query.order_by(RegistroAlimentacao.data.desc()).limit(50).all()
    return render_template('alimentacao.html', registros=registros, date=date)

@main_bp.route('/alimentacao/novo', methods=['GET', 'POST'])
@login_required
def nova_alimentacao():
    form = AlimentacaoForm()
    form.funcionario_id.choices = [(f.id, f.nome) for f in Funcionario.query.filter_by(ativo=True).all()]
    form.obra_id.choices = [(0, 'Selecione...')] + [(o.id, o.nome) for o in Obra.query.filter_by(status='Em andamento').all()]
    form.restaurante_id.choices = [(0, 'Selecione...')] + [(r.id, r.nome) for r in Restaurante.query.filter_by(ativo=True).all()]
    
    if form.validate_on_submit():
        registro = RegistroAlimentacao(
            funcionario_id=form.funcionario_id.data,
            obra_id=form.obra_id.data if form.obra_id.data > 0 else None,
            restaurante_id=form.restaurante_id.data if form.restaurante_id.data > 0 else None,
            data=form.data.data,
            tipo=form.tipo.data,
            valor=form.valor.data,
            observacoes=form.observacoes.data
        )
        
        db.session.add(registro)
        
        # Adicionar custo à obra se especificada
        if registro.obra_id:
            custo = CustoObra(
                obra_id=registro.obra_id,
                tipo='alimentacao',
                descricao=f'Alimentação - {registro.tipo} - {registro.funcionario_ref.nome}',
                valor=registro.valor,
                data=registro.data
            )
            db.session.add(custo)
        
        db.session.commit()
        flash('Registro de alimentação adicionado com sucesso!', 'success')
        return redirect(url_for('main.alimentacao'))
    
    return render_template('alimentacao.html', form=form, registros=RegistroAlimentacao.query.order_by(RegistroAlimentacao.data.desc()).limit(50).all())

# Relatórios
@main_bp.route('/relatorios')
@login_required
def relatorios():
    # Buscar dados para filtros
    obras = Obra.query.all()
    departamentos = Departamento.query.all()
    
    return render_template('relatorios.html', obras=obras, departamentos=departamentos)

@main_bp.route('/relatorios/dados-graficos', methods=['POST'])
@login_required
def dados_graficos():
    from datetime import datetime, timedelta
    import json
    from sqlalchemy import func, extract
    
    filtros = request.get_json()
    
    # Processar filtros de data
    data_inicio = datetime.strptime(filtros.get('dataInicio', ''), '%Y-%m-%d').date() if filtros.get('dataInicio') else None
    data_fim = datetime.strptime(filtros.get('dataFim', ''), '%Y-%m-%d').date() if filtros.get('dataFim') else None
    obra_id = filtros.get('obra') if filtros.get('obra') else None
    departamento_id = filtros.get('departamento') if filtros.get('departamento') else None
    
    # Data padrão (últimos 6 meses)
    if not data_inicio or not data_fim:
        hoje = date.today()
        data_fim = hoje
        data_inicio = date(hoje.year, hoje.month - 5 if hoje.month > 5 else hoje.month + 7, 1)
        if hoje.month <= 5:
            data_inicio = data_inicio.replace(year=hoje.year - 1)
    
    # 1. Evolução de Custos
    custos_query = db.session.query(
        extract('month', CustoObra.data).label('mes'),
        extract('year', CustoObra.data).label('ano'),
        CustoObra.tipo,
        func.sum(CustoObra.valor).label('total')
    ).filter(
        CustoObra.data >= data_inicio,
        CustoObra.data <= data_fim
    )
    
    if obra_id:
        custos_query = custos_query.filter(CustoObra.obra_id == obra_id)
    
    custos_dados = custos_query.group_by(
        extract('year', CustoObra.data),
        extract('month', CustoObra.data),
        CustoObra.tipo
    ).all()
    
    # Processar dados de custos
    meses_labels = []
    mao_obra_dados = []
    alimentacao_dados = []
    veiculos_dados = []
    
    # Gerar lista de meses
    current_date = data_inicio.replace(day=1)
    while current_date <= data_fim:
        mes_nome = ['Jan', 'Fev', 'Mar', 'Abr', 'Mai', 'Jun',
                   'Jul', 'Ago', 'Set', 'Out', 'Nov', 'Dez'][current_date.month - 1]
        meses_labels.append(f"{mes_nome}/{current_date.year}")
        
        # Buscar dados do mês
        mao_obra_mes = sum(d.total for d in custos_dados if d.mes == current_date.month and d.ano == current_date.year and d.tipo == 'mao_obra')
        alimentacao_mes = sum(d.total for d in custos_dados if d.mes == current_date.month and d.ano == current_date.year and d.tipo == 'alimentacao')
        veiculos_mes = sum(d.total for d in custos_dados if d.mes == current_date.month and d.ano == current_date.year and d.tipo == 'veiculo')
        
        mao_obra_dados.append(float(mao_obra_mes))
        alimentacao_dados.append(float(alimentacao_mes))
        veiculos_dados.append(float(veiculos_mes))
        
        # Próximo mês
        if current_date.month == 12:
            current_date = current_date.replace(year=current_date.year + 1, month=1)
        else:
            current_date = current_date.replace(month=current_date.month + 1)
    
    # 2. Produtividade por Departamento
    produtividade_query = db.session.query(
        Departamento.nome,
        func.avg(RegistroPonto.horas_trabalhadas).label('media_horas')
    ).join(
        Funcionario, Departamento.id == Funcionario.departamento_id
    ).join(
        RegistroPonto, Funcionario.id == RegistroPonto.funcionario_id
    ).filter(
        RegistroPonto.data >= data_inicio,
        RegistroPonto.data <= data_fim
    )
    
    if departamento_id:
        produtividade_query = produtividade_query.filter(Departamento.id == departamento_id)
    
    produtividade_dados = produtividade_query.group_by(Departamento.nome).all()
    
    # 3. Distribuição de Custos
    distribuicao_dados = db.session.query(
        CustoObra.tipo,
        func.sum(CustoObra.valor).label('total')
    ).filter(
        CustoObra.data >= data_inicio,
        CustoObra.data <= data_fim
    )
    
    if obra_id:
        distribuicao_dados = distribuicao_dados.filter(CustoObra.obra_id == obra_id)
    
    distribuicao_dados = distribuicao_dados.group_by(CustoObra.tipo).all()
    
    # 4. Horas Trabalhadas vs Extras
    horas_query = db.session.query(
        extract('month', RegistroPonto.data).label('mes'),
        extract('year', RegistroPonto.data).label('ano'),
        func.sum(RegistroPonto.horas_trabalhadas).label('horas_normais'),
        func.sum(RegistroPonto.horas_extras).label('horas_extras')
    ).filter(
        RegistroPonto.data >= data_inicio,
        RegistroPonto.data <= data_fim
    )
    
    if departamento_id:
        horas_query = horas_query.join(Funcionario).filter(Funcionario.departamento_id == departamento_id)
    
    horas_dados = horas_query.group_by(
        extract('year', RegistroPonto.data),
        extract('month', RegistroPonto.data)
    ).all()
    
    # Processar dados de horas
    horas_normais_dados = []
    horas_extras_dados = []
    
    current_date = data_inicio.replace(day=1)
    while current_date <= data_fim:
        horas_mes = next((h for h in horas_dados if h.mes == current_date.month and h.ano == current_date.year), None)
        
        horas_normais_dados.append(float(horas_mes.horas_normais or 0) if horas_mes else 0)
        horas_extras_dados.append(float(horas_mes.horas_extras or 0) if horas_mes else 0)
        
        # Próximo mês
        if current_date.month == 12:
            current_date = current_date.replace(year=current_date.year + 1, month=1)
        else:
            current_date = current_date.replace(month=current_date.month + 1)
    
    return jsonify({
        'evolucao': {
            'labels': meses_labels,
            'mao_obra': mao_obra_dados,
            'alimentacao': alimentacao_dados,
            'veiculos': veiculos_dados
        },
        'produtividade': {
            'labels': [p.nome for p in produtividade_dados],
            'valores': [float(p.media_horas or 0) for p in produtividade_dados]
        },
        'distribuicao': {
            'valores': [float(d.total) for d in distribuicao_dados]
        },
        'horas': {
            'labels': meses_labels,
            'normais': horas_normais_dados,
            'extras': horas_extras_dados
        }
    })

@main_bp.route('/relatorios/gerar/<tipo>', methods=['GET', 'POST'])
@login_required
def gerar_relatorio(tipo):
    # Processar filtros de GET ou POST
    if request.method == 'POST':
        filtros = request.get_json() or {}
    else:
        filtros = request.args.to_dict()
    
    # Processar filtros
    data_inicio = datetime.strptime(filtros.get('dataInicio', ''), '%Y-%m-%d').date() if filtros.get('dataInicio') else None
    data_fim = datetime.strptime(filtros.get('dataFim', ''), '%Y-%m-%d').date() if filtros.get('dataFim') else None
    obra_id = int(filtros.get('obra')) if filtros.get('obra') else None
    departamento_id = int(filtros.get('departamento')) if filtros.get('departamento') else None
    
    if tipo == 'funcionarios':
        query = Funcionario.query
        if departamento_id:
            query = query.filter_by(departamento_id=departamento_id)
        funcionarios = query.all()
        
        html = '<div class="table-responsive"><table class="table table-striped">'
        html += '<thead><tr><th>Código</th><th>Nome</th><th>CPF</th><th>Departamento</th><th>Função</th><th>Data Admissão</th><th>Salário</th><th>Status</th></tr></thead><tbody>'
        
        for f in funcionarios:
            status_badge = '<span class="badge bg-success">Ativo</span>' if f.ativo else '<span class="badge bg-danger">Inativo</span>'
            html += f'<tr><td>{f.codigo or "-"}</td><td>{f.nome}</td><td>{f.cpf}</td><td>{f.departamento_ref.nome if f.departamento_ref else "-"}</td>'
            html += f'<td>{f.funcao_ref.nome if f.funcao_ref else "-"}</td><td>{f.data_admissao.strftime("%d/%m/%Y") if f.data_admissao else "-"}</td>'
            html += f'<td>R$ {f.salario:,.2f}</td><td>{status_badge}</td></tr>'
        
        html += '</tbody></table></div>'
        
        return jsonify({
            'titulo': f'Lista de Funcionários ({len(funcionarios)} registros)',
            'html': html
        })
    
    elif tipo == 'ponto':
        query = RegistroPonto.query
        if data_inicio:
            query = query.filter(RegistroPonto.data >= data_inicio)
        if data_fim:
            query = query.filter(RegistroPonto.data <= data_fim)
        if obra_id:
            query = query.filter_by(obra_id=obra_id)
        if departamento_id:
            query = query.join(Funcionario).filter(Funcionario.departamento_id == departamento_id)
        
        registros = query.join(Funcionario).order_by(RegistroPonto.data.desc()).all()
        
        html = '<div class="table-responsive"><table class="table table-striped">'
        html += '<thead><tr><th>Data</th><th>Funcionário</th><th>Obra</th><th>Entrada</th><th>Saída</th><th>Horas Trabalhadas</th><th>Horas Extras</th><th>Atrasos</th></tr></thead><tbody>'
        
        for r in registros:
            html += f'<tr><td>{r.data.strftime("%d/%m/%Y")}</td>'
            html += f'<td>{r.funcionario.nome}</td>'
            html += f'<td>{r.obra.nome if r.obra else "-"}</td>'
            html += f'<td>{r.hora_entrada.strftime("%H:%M") if r.hora_entrada else "-"}</td>'
            html += f'<td>{r.hora_saida.strftime("%H:%M") if r.hora_saida else "-"}</td>'
            html += f'<td>{r.horas_trabalhadas:.2f}h</td>'
            html += f'<td>{r.horas_extras:.2f}h</td>'
            html += f'<td>{r.total_atraso_minutos or 0} min</td></tr>'
        
        html += '</tbody></table></div>'
        
        return jsonify({
            'titulo': f'Relatório de Ponto ({len(registros)} registros)',
            'html': html
        })
    
    elif tipo == 'horas-extras':
        query = RegistroPonto.query.filter(RegistroPonto.horas_extras > 0)
        if data_inicio:
            query = query.filter(RegistroPonto.data >= data_inicio)
        if data_fim:
            query = query.filter(RegistroPonto.data <= data_fim)
        if obra_id:
            query = query.filter_by(obra_id=obra_id)
        if departamento_id:
            query = query.join(Funcionario).filter(Funcionario.departamento_id == departamento_id)
        
        registros = query.join(Funcionario).order_by(RegistroPonto.data.desc()).all()
        
        html = '<div class="table-responsive"><table class="table table-striped">'
        html += '<thead><tr><th>Data</th><th>Funcionário</th><th>Obra</th><th>Horas Extras</th><th>Valor Estimado</th></tr></thead><tbody>'
        
        total_horas = 0
        total_valor = 0
        
        for r in registros:
            valor_hora = (r.funcionario.salario / 220) * 1.5 if r.funcionario.salario else 0
            valor_extras = r.horas_extras * valor_hora
            total_horas += r.horas_extras
            total_valor += valor_extras
            
            html += f'<tr><td>{r.data.strftime("%d/%m/%Y")}</td>'
            html += f'<td>{r.funcionario.nome}</td>'
            html += f'<td>{r.obra.nome if r.obra else "-"}</td>'
            html += f'<td>{r.horas_extras:.2f}h</td>'
            html += f'<td>R$ {valor_extras:.2f}</td></tr>'
        
        html += f'<tr class="table-info"><td colspan="3"><strong>TOTAL</strong></td><td><strong>{total_horas:.2f}h</strong></td><td><strong>R$ {total_valor:.2f}</strong></td></tr>'
        html += '</tbody></table></div>'
        
        return jsonify({
            'titulo': f'Relatório de Horas Extras ({len(registros)} registros)',
            'html': html
        })
    
    elif tipo == 'alimentacao':
        query = RegistroAlimentacao.query
        if data_inicio:
            query = query.filter(RegistroAlimentacao.data >= data_inicio)
        if data_fim:
            query = query.filter(RegistroAlimentacao.data <= data_fim)
        if obra_id:
            query = query.filter_by(obra_id=obra_id)
        if departamento_id:
            query = query.join(Funcionario).filter(Funcionario.departamento_id == departamento_id)
        
        registros = query.join(Funcionario).order_by(RegistroAlimentacao.data.desc()).all()
        
        html = '<div class="table-responsive"><table class="table table-striped">'
        html += '<thead><tr><th>Data</th><th>Funcionário</th><th>Tipo</th><th>Restaurante</th><th>Obra</th><th>Valor</th></tr></thead><tbody>'
        
        total_valor = 0
        
        for r in registros:
            total_valor += r.valor
            html += f'<tr><td>{r.data.strftime("%d/%m/%Y")}</td>'
            html += f'<td>{r.funcionario.nome}</td>'
            html += f'<td>{r.tipo.title()}</td>'
            html += f'<td>{r.restaurante.nome if r.restaurante else "-"}</td>'
            html += f'<td>{r.obra.nome if r.obra else "-"}</td>'
            html += f'<td>R$ {r.valor:.2f}</td></tr>'
        
        html += f'<tr class="table-info"><td colspan="5"><strong>TOTAL</strong></td><td><strong>R$ {total_valor:.2f}</strong></td></tr>'
        html += '</tbody></table></div>'
        
        return jsonify({
            'titulo': f'Relatório de Alimentação ({len(registros)} registros)',
            'html': html
        })
    
    elif tipo == 'obras':
        query = Obra.query
        if obra_id:
            query = query.filter_by(id=obra_id)
        
        obras = query.all()
        
        html = '<div class="table-responsive"><table class="table table-striped">'
        html += '<thead><tr><th>Nome</th><th>Responsável</th><th>Data Início</th><th>Previsão Fim</th><th>Orçamento</th><th>Status</th><th>Funcionários</th></tr></thead><tbody>'
        
        for obra in obras:
            funcionarios_obra = db.session.query(func.count(FuncionarioObra.id)).filter_by(obra_id=obra.id).scalar()
            
            html += f'<tr><td>{obra.nome}</td>'
            html += f'<td>{obra.responsavel.nome if obra.responsavel else "-"}</td>'
            html += f'<td>{obra.data_inicio.strftime("%d/%m/%Y") if obra.data_inicio else "-"}</td>'
            html += f'<td>{obra.data_previsao_fim.strftime("%d/%m/%Y") if obra.data_previsao_fim else "-"}</td>'
            html += f'<td>R$ {obra.orcamento:,.2f}</td>'
            html += f'<td><span class="badge bg-primary">{obra.status}</span></td>'
            html += f'<td>{funcionarios_obra}</td></tr>'
        
        html += '</tbody></table></div>'
        
        return jsonify({
            'titulo': f'Lista de Obras ({len(obras)} registros)',
            'html': html
        })
    
    elif tipo == 'custos-obra':
        query = CustoObra.query
        if data_inicio:
            query = query.filter(CustoObra.data >= data_inicio)
        if data_fim:
            query = query.filter(CustoObra.data <= data_fim)
        if obra_id:
            query = query.filter_by(obra_id=obra_id)
        
        custos = query.join(Obra).order_by(CustoObra.data.desc()).all()
        
        html = '<div class="table-responsive"><table class="table table-striped">'
        html += '<thead><tr><th>Data</th><th>Obra</th><th>Tipo</th><th>Descrição</th><th>Valor</th></tr></thead><tbody>'
        
        total_custos = 0
        
        for custo in custos:
            total_custos += custo.valor
            html += f'<tr><td>{custo.data.strftime("%d/%m/%Y")}</td>'
            html += f'<td>{custo.obra.nome}</td>'
            html += f'<td>{custo.tipo.title()}</td>'
            html += f'<td>{custo.descricao or "-"}</td>'
            html += f'<td>R$ {custo.valor:.2f}</td></tr>'
        
        html += f'<tr class="table-info"><td colspan="4"><strong>TOTAL</strong></td><td><strong>R$ {total_custos:.2f}</strong></td></tr>'
        html += '</tbody></table></div>'
        
        return jsonify({
            'titulo': f'Custos por Obra ({len(custos)} registros)',
            'html': html
        })
    
    elif tipo == 'veiculos':
        query = Veiculo.query
        veiculos = query.all()
        
        html = '<div class="table-responsive"><table class="table table-striped">'
        html += '<thead><tr><th>Placa</th><th>Marca/Modelo</th><th>Ano</th><th>Tipo</th><th>KM Atual</th><th>Status</th><th>Próxima Manutenção</th></tr></thead><tbody>'
        
        for veiculo in veiculos:
            html += f'<tr><td>{veiculo.placa}</td>'
            html += f'<td>{veiculo.marca} {veiculo.modelo}</td>'
            html += f'<td>{veiculo.ano or "-"}</td>'
            html += f'<td>{veiculo.tipo}</td>'
            html += f'<td>{veiculo.km_atual or 0:,} km</td>'
            html += f'<td><span class="badge bg-info">{veiculo.status}</span></td>'
            html += f'<td>{veiculo.data_proxima_manutencao.strftime("%d/%m/%Y") if veiculo.data_proxima_manutencao else "-"}</td></tr>'
        
        html += '</tbody></table></div>'
        
        return jsonify({
            'titulo': f'Relatório de Veículos ({len(veiculos)} registros)',
            'html': html
        })
    
    elif tipo == 'dashboard-executivo':
        # Dados consolidados para dashboard executivo
        total_funcionarios = Funcionario.query.filter_by(ativo=True).count()
        total_obras = Obra.query.filter_by(status='Em andamento').count()
        total_veiculos = Veiculo.query.count()
        
        # Custos do mês atual
        hoje = date.today()
        primeiro_dia_mes = hoje.replace(day=1)
        
        custos_mes = db.session.query(func.sum(CustoObra.valor)).filter(
            CustoObra.data >= primeiro_dia_mes,
            CustoObra.data <= hoje
        ).scalar() or 0
        
        # Horas trabalhadas do mês
        horas_mes = db.session.query(func.sum(RegistroPonto.horas_trabalhadas)).filter(
            RegistroPonto.data >= primeiro_dia_mes,
            RegistroPonto.data <= hoje
        ).scalar() or 0
        
        # Alimentação do mês
        alimentacao_mes = db.session.query(func.sum(RegistroAlimentacao.valor)).filter(
            RegistroAlimentacao.data >= primeiro_dia_mes,
            RegistroAlimentacao.data <= hoje
        ).scalar() or 0
        
        html = '<div class="row">'
        html += f'<div class="col-md-3"><div class="card text-center"><div class="card-body"><h2 class="text-primary">{total_funcionarios}</h2><p>Funcionários Ativos</p></div></div></div>'
        html += f'<div class="col-md-3"><div class="card text-center"><div class="card-body"><h2 class="text-success">{total_obras}</h2><p>Obras em Andamento</p></div></div></div>'
        html += f'<div class="col-md-3"><div class="card text-center"><div class="card-body"><h2 class="text-warning">{total_veiculos}</h2><p>Veículos</p></div></div></div>'
        html += f'<div class="col-md-3"><div class="card text-center"><div class="card-body"><h2 class="text-info">R$ {custos_mes:,.0f}</h2><p>Custos do Mês</p></div></div></div>'
        html += '</div>'
        
        html += '<div class="row mt-4">'
        html += f'<div class="col-md-6"><div class="card"><div class="card-body"><h5>Resumo Mensal</h5><p><strong>Horas Trabalhadas:</strong> {horas_mes:.0f}h</p><p><strong>Custo por Hora:</strong> R$ {(custos_mes/horas_mes if horas_mes > 0 else 0):.2f}</p></div></div></div>'
        html += f'<div class="col-md-6"><div class="card"><div class="card-body"><h5>Alimentação</h5><p><strong>Gasto Mensal:</strong> R$ {alimentacao_mes:,.2f}</p><p><strong>Média por Funcionário:</strong> R$ {(alimentacao_mes/total_funcionarios if total_funcionarios > 0 else 0):.2f}</p></div></div></div>'
        html += '</div>'
        
        return jsonify({
            'titulo': 'Dashboard Executivo',
            'html': html
        })
    
    elif tipo == 'progresso-obras':
        obras = Obra.query.all()
        
        html = '<div class="table-responsive"><table class="table table-striped">'
        html += '<thead><tr><th>Obra</th><th>Progresso</th><th>Orçamento</th><th>Gasto Atual</th><th>Saldo</th><th>% Utilizado</th></tr></thead><tbody>'
        
        for obra in obras:
            gasto_atual = db.session.query(func.sum(CustoObra.valor)).filter_by(obra_id=obra.id).scalar() or 0
            saldo = obra.orcamento - gasto_atual
            percentual = (gasto_atual / obra.orcamento * 100) if obra.orcamento > 0 else 0
            
            cor_saldo = 'text-success' if saldo > 0 else 'text-danger'
            
            html += f'<tr><td>{obra.nome}</td>'
            html += f'<td><span class="badge bg-info">{obra.status}</span></td>'
            html += f'<td>R$ {obra.orcamento:,.2f}</td>'
            html += f'<td>R$ {gasto_atual:,.2f}</td>'
            html += f'<td class="{cor_saldo}">R$ {saldo:,.2f}</td>'
            html += f'<td>{percentual:.1f}%</td></tr>'
        
        html += '</tbody></table></div>'
        
        return jsonify({
            'titulo': f'Progresso das Obras ({len(obras)} registros)',
            'html': html
        })
    
    elif tipo == 'rentabilidade':
        # Análise de rentabilidade por obra
        obras = Obra.query.all()
        
        html = '<div class="table-responsive"><table class="table table-striped">'
        html += '<thead><tr><th>Obra</th><th>Receita Prevista</th><th>Custos</th><th>Margem</th><th>% Margem</th><th>Status</th></tr></thead><tbody>'
        
        for obra in obras:
            custos_obra = db.session.query(func.sum(CustoObra.valor)).filter_by(obra_id=obra.id).scalar() or 0
            receita_prevista = obra.orcamento * 1.3  # Assumindo 30% de margem padrão
            margem = receita_prevista - custos_obra
            percentual_margem = (margem / receita_prevista * 100) if receita_prevista > 0 else 0
            
            cor_margem = 'text-success' if margem > 0 else 'text-danger'
            
            html += f'<tr><td>{obra.nome}</td>'
            html += f'<td>R$ {receita_prevista:,.2f}</td>'
            html += f'<td>R$ {custos_obra:,.2f}</td>'
            html += f'<td class="{cor_margem}">R$ {margem:,.2f}</td>'
            html += f'<td class="{cor_margem}">{percentual_margem:.1f}%</td>'
            html += f'<td><span class="badge bg-primary">{obra.status}</span></td></tr>'
        
        html += '</tbody></table></div>'
        
        return jsonify({
            'titulo': f'Análise de Rentabilidade ({len(obras)} obras)',
            'html': html
        })
    
    else:
        return jsonify({
            'titulo': 'Relatório não implementado',
            'html': '<div class="alert alert-info">Este tipo de relatório ainda não foi implementado.</div>'
        })

@main_bp.route('/relatorios/exportar/<tipo>', methods=['GET', 'POST'])
@login_required
def exportar_relatorio(tipo):
    """Exporta relatório em formato específico"""
    from relatorios_funcionais import gerar_relatorio_funcional
    
    # Processar filtros e formato
    if request.method == 'POST':
        filtros = request.get_json() or {}
        formato = filtros.get('formato', 'csv')
    else:
        filtros = request.args.to_dict()
        formato = filtros.get('formato', 'csv')
    
    try:
        return gerar_relatorio_funcional(tipo, formato, filtros)
    except Exception as e:
        return jsonify({'erro': str(e)}), 500

@main_bp.route('/funcionarios/<int:funcionario_id>/ocorrencias/nova', methods=['POST'])
@login_required
def nova_ocorrencia(funcionario_id):
    """Cria nova ocorrência para funcionário"""
    funcionario = Funcionario.query.get_or_404(funcionario_id)
    
    try:
        # Criar ocorrência baseada no modelo existente
        ocorrencia = Ocorrencia(
            funcionario_id=funcionario_id,
            tipo=request.form.get('tipo'),
            data_inicio=datetime.strptime(request.form.get('data_inicio'), '%Y-%m-%d').date(),
            data_fim=datetime.strptime(request.form.get('data_fim'), '%Y-%m-%d').date() if request.form.get('data_fim') else None,
            status=request.form.get('status', 'Pendente'),
            descricao=request.form.get('descricao', '')
        )
        
        db.session.add(ocorrencia)
        db.session.commit()
        
        flash('Ocorrência registrada com sucesso!', 'success')
        
    except Exception as e:
        db.session.rollback()
        flash(f'Erro ao registrar ocorrência: {str(e)}', 'error')
        
    return redirect(url_for('main.funcionario_perfil', id=funcionario_id))

@main_bp.route('/funcionarios/ocorrencias/<int:ocorrencia_id>/editar', methods=['POST'])
@login_required
def editar_ocorrencia(ocorrencia_id):
    """Edita ocorrência existente"""
    ocorrencia = Ocorrencia.query.get_or_404(ocorrencia_id)
    
    try:
        ocorrencia.tipo = request.form.get('tipo')
        ocorrencia.data_inicio = datetime.strptime(request.form.get('data_inicio'), '%Y-%m-%d').date()
        ocorrencia.data_fim = datetime.strptime(request.form.get('data_fim'), '%Y-%m-%d').date() if request.form.get('data_fim') else None
        ocorrencia.status = request.form.get('status')
        ocorrencia.descricao = request.form.get('descricao', '')
        
        db.session.commit()
        flash('Ocorrência atualizada com sucesso!', 'success')
        
    except Exception as e:
        db.session.rollback()
        flash(f'Erro ao atualizar ocorrência: {str(e)}', 'error')
        
    return redirect(url_for('main.funcionario_perfil', id=ocorrencia.funcionario_id))

@main_bp.route('/funcionarios/ocorrencias/<int:ocorrencia_id>/excluir', methods=['POST'])
@login_required
def excluir_ocorrencia(ocorrencia_id):
    """Exclui ocorrência"""
    ocorrencia = Ocorrencia.query.get_or_404(ocorrencia_id)
    funcionario_id = ocorrencia.funcionario_id
    
    try:
        db.session.delete(ocorrencia)
        db.session.commit()
        flash('Ocorrência excluída com sucesso!', 'success')
        
    except Exception as e:
        db.session.rollback()
        flash(f'Erro ao excluir ocorrência: {str(e)}', 'error')
        
    return redirect(url_for('main.funcionario_perfil', id=funcionario_id))

# === ROTAS FINANCEIRAS ===

@main_bp.route('/financeiro')
@login_required
def financeiro_dashboard():
    """Dashboard principal do módulo financeiro"""
    # Filtros de data
    data_inicio = request.args.get('data_inicio')
    data_fim = request.args.get('data_fim')
    
    if not data_inicio:
        data_inicio = date.today().replace(day=1)
    else:
        data_inicio = datetime.strptime(data_inicio, '%Y-%m-%d').date()
    
    if not data_fim:
        data_fim = date.today()
    else:
        data_fim = datetime.strptime(data_fim, '%Y-%m-%d').date()
    
    # Importar módulo financeiro
    from financeiro import obter_kpis_financeiros, calcular_fluxo_caixa_periodo
    
    # KPIs financeiros
    kpis = obter_kpis_financeiros(data_inicio, data_fim)
    
    # Fluxo de caixa detalhado
    fluxo = calcular_fluxo_caixa_periodo(data_inicio, data_fim)
    
    # Receitas recentes
    receitas_recentes = Receita.query.filter(
        Receita.data_receita >= data_inicio,
        Receita.data_receita <= data_fim
    ).order_by(Receita.data_receita.desc()).limit(10).all()
    
    # Centros de custo ativos
    centros_custo = CentroCusto.query.filter_by(ativo=True).all()
    
    return render_template('financeiro/dashboard.html',
                         kpis=kpis,
                         fluxo=fluxo,
                         receitas_recentes=receitas_recentes,
                         centros_custo=centros_custo,
                         data_inicio=data_inicio,
                         data_fim=data_fim)

@main_bp.route('/financeiro/receitas')
@login_required
def receitas():
    """Página de gestão de receitas"""
    # Filtros
    data_inicio = request.args.get('data_inicio')
    data_fim = request.args.get('data_fim')
    status_filtro = request.args.get('status', '')
    obra_filtro = request.args.get('obra_id', '')
    
    query = Receita.query
    
    if data_inicio:
        query = query.filter(Receita.data_receita >= datetime.strptime(data_inicio, '%Y-%m-%d').date())
    if data_fim:
        query = query.filter(Receita.data_receita <= datetime.strptime(data_fim, '%Y-%m-%d').date())
    if status_filtro:
        query = query.filter(Receita.status == status_filtro)
    if obra_filtro:
        query = query.filter(Receita.obra_id == int(obra_filtro))
    
    receitas = query.order_by(Receita.data_receita.desc()).all()
    
    # Dados para formulários
    obras = Obra.query.filter_by(status='Em andamento').all()
    centros_custo = CentroCusto.query.filter_by(ativo=True).all()
    
    return render_template('financeiro/receitas.html',
                         receitas=receitas,
                         obras=obras,
                         centros_custo=centros_custo,
                         data_inicio=data_inicio,
                         data_fim=data_fim,
                         status_filtro=status_filtro,
                         obra_filtro=obra_filtro)

@main_bp.route('/financeiro/fluxo-caixa')
@login_required
def fluxo_caixa():
    """Página de fluxo de caixa"""
    from financeiro import calcular_fluxo_caixa_periodo
    
    # Filtros padrão
    data_inicio = request.args.get('data_inicio', date.today().replace(day=1).strftime('%Y-%m-%d'))
    data_fim = request.args.get('data_fim', date.today().strftime('%Y-%m-%d'))
    obra_id = request.args.get('obra_id', 0, type=int)
    centro_custo_id = request.args.get('centro_custo_id', 0, type=int)
    tipo_movimento = request.args.get('tipo_movimento', '')
    categoria = request.args.get('categoria', '')
    
    # Converter datas
    data_inicio_dt = datetime.strptime(data_inicio, '%Y-%m-%d').date()
    data_fim_dt = datetime.strptime(data_fim, '%Y-%m-%d').date()
    
    # Calcular fluxo
    fluxo = calcular_fluxo_caixa_periodo(
        data_inicio_dt, 
        data_fim_dt,
        obra_id if obra_id != 0 else None,
        centro_custo_id if centro_custo_id != 0 else None
    )
    
    # Filtrar movimentos adicionalmente
    movimentos_filtrados = fluxo['movimentos']
    if tipo_movimento:
        movimentos_filtrados = [m for m in movimentos_filtrados if m.tipo_movimento == tipo_movimento]
    if categoria:
        movimentos_filtrados = [m for m in movimentos_filtrados if m.categoria == categoria]
    
    # Dados para formulários
    obras = Obra.query.all()
    centros_custo = CentroCusto.query.filter_by(ativo=True).all()
    
    return render_template('financeiro/fluxo_caixa.html',
                         fluxo=fluxo,
                         movimentos=movimentos_filtrados,
                         obras=obras,
                         centros_custo=centros_custo,
                         filtros={
                             'data_inicio': data_inicio,
                             'data_fim': data_fim,
                             'obra_id': obra_id,
                             'centro_custo_id': centro_custo_id,
                             'tipo_movimento': tipo_movimento,
                             'categoria': categoria
                         })

@main_bp.route('/financeiro/centros-custo')
@login_required
def centros_custo():
    """Página de gestão de centros de custo"""
    centros = CentroCusto.query.all()
    return render_template('financeiro/centros_custo.html', centros=centros)

# ============================================================================
# ROTAS RDO (RELATÓRIO DIÁRIO DE OBRA)
# ============================================================================

@main_bp.route('/rdo')
@login_required
def lista_rdos():
    """Lista todos os RDOs com filtros"""
    page = request.args.get('page', 1, type=int)
    
    # Filtros
    obra_id = request.args.get('obra_id')
    data_inicio = request.args.get('data_inicio')
    data_fim = request.args.get('data_fim')
    status = request.args.get('status')
    
    # Query base
    query = RDO.query
    
    # Aplicar filtros
    if obra_id:
        query = query.filter(RDO.obra_id == obra_id)
    if data_inicio:
        query = query.filter(RDO.data_relatorio >= datetime.strptime(data_inicio, '%Y-%m-%d').date())
    if data_fim:
        query = query.filter(RDO.data_relatorio <= datetime.strptime(data_fim, '%Y-%m-%d').date())
    if status:
        query = query.filter(RDO.status == status)
    
    # Ordenação e paginação
    rdos = query.order_by(RDO.data_relatorio.desc()).paginate(
        page=page, per_page=20, error_out=False
    )
    
    # Dados para filtros
    obras = Obra.query.all()
    
    return render_template('rdo/lista_rdos.html', 
                         rdos=rdos, 
                         obras=obras,
                         filtros={
                             'obra_id': obra_id,
                             'data_inicio': data_inicio,
                             'data_fim': data_fim,
                             'status': status
                         })

@main_bp.route('/rdo/novo')
@login_required
def novo_rdo():
    """Formulário para criar novo RDO"""
    from models import ServicoObra
    
    # Dados para template
    obras = Obra.query.filter_by(ativo=True).all()
    funcionarios = Funcionario.query.filter_by(ativo=True).all()
    servicos = Servico.query.filter_by(ativo=True).all()
    
    # Obter obra pré-selecionada se houver
    obra_id = request.args.get('obra_id')
    servicos_obra = []
    if obra_id:
        servicos_obra = db.session.query(ServicoObra, Servico).join(
            Servico, ServicoObra.servico_id == Servico.id
        ).filter(
            ServicoObra.obra_id == obra_id,
            ServicoObra.ativo == True
        ).all()
    
    return render_template('rdo_novo.html', 
                         obras=obras,
                         funcionarios=funcionarios,
                         servicos=servicos,
                         servicos_obra=servicos_obra,
                         obra_id=obra_id,
                         data_hoje=datetime.now().strftime('%Y-%m-%d'))

@main_bp.route('/rdo/criar', methods=['POST'])
@login_required
def criar_rdo():
    """Processar criação de novo RDO"""
    try:
        # Gerar número único do RDO
        import uuid
        numero_rdo = f"RDO-{datetime.now().year}-{str(uuid.uuid4())[:8].upper()}"
        
        rdo = RDO(
            numero_rdo=numero_rdo,
            data_relatorio=datetime.strptime(request.form.get('data_relatorio'), '%Y-%m-%d').date(),
            obra_id=request.form.get('obra_id'),
            criado_por_id=current_user.id,
            tempo_manha=request.form.get('tempo_manha', ''),
            tempo_tarde=request.form.get('tempo_tarde', ''),
            tempo_noite=request.form.get('tempo_noite', ''),
            observacoes_meteorologicas=request.form.get('observacoes_meteorologicas', ''),
            comentario_geral=request.form.get('comentario_geral', ''),
            status=request.form.get('status', 'Rascunho')
        )
        
        db.session.add(rdo)
        db.session.commit()
        
        flash('RDO criado com sucesso!', 'success')
        return redirect(url_for('main.visualizar_rdo', id=rdo.id))
        
    except Exception as e:
        db.session.rollback()
        flash(f'Erro ao criar RDO: {str(e)}', 'error')
        return redirect(url_for('main.novo_rdo'))

@main_bp.route('/rdo/<int:id>')
@login_required
def visualizar_rdo(id):
    """Visualizar detalhes de um RDO"""
    rdo = RDO.query.get_or_404(id)
    return render_template('rdo/visualizar_rdo.html', rdo=rdo)

@main_bp.route('/rdo/<int:id>/editar')
@login_required
def editar_rdo(id):
    """Formulário para editar RDO"""
    rdo = RDO.query.get_or_404(id)
    obras = Obra.query.all()
    funcionarios = Funcionario.query.filter_by(ativo=True).all()
    
    return render_template('rdo/formulario_rdo.html', 
                         rdo=rdo,
                         obras=obras,
                         funcionarios=funcionarios,
                         modo='editar')

@main_bp.route('/rdo/<int:id>/excluir', methods=['POST'])
@login_required
def excluir_rdo(id):
    """Excluir RDO"""
    try:
        rdo = RDO.query.get_or_404(id)
        db.session.delete(rdo)
        db.session.commit()
        
        flash('RDO excluído com sucesso!', 'success')
        return redirect(url_for('main.lista_rdos'))
        
    except Exception as e:
        db.session.rollback()
        flash(f'Erro ao excluir RDO: {str(e)}', 'error')
        return redirect(url_for('main.lista_rdos'))

@main_bp.route('/financeiro/centros-custo/novo', methods=['GET', 'POST'])
@login_required
def novo_centro_custo():
    """Criar novo centro de custo"""
    from financeiro import gerar_codigo_centro_custo
    
    if request.method == 'POST':
        try:
            centro = CentroCusto(
                codigo=request.form.get('codigo'),
                nome=request.form.get('nome'),
                descricao=request.form.get('descricao'),
                tipo=request.form.get('tipo'),
                obra_id=int(request.form.get('obra_id')) if request.form.get('obra_id') != '0' else None,
                departamento_id=int(request.form.get('departamento_id')) if request.form.get('departamento_id') != '0' else None,
                ativo=bool(request.form.get('ativo'))
            )
            
            db.session.add(centro)
            db.session.commit()
            flash('Centro de custo cadastrado com sucesso!', 'success')
            return redirect(url_for('main.centros_custo'))
        except Exception as e:
            db.session.rollback()
            flash(f'Erro ao cadastrar centro de custo: {str(e)}', 'error')
    
    # Dados para formulário
    obras = Obra.query.all()
    departamentos = Departamento.query.all()
    codigo_padrao = gerar_codigo_centro_custo()
    
    return render_template('financeiro/centro_custo_form.html', 
                         titulo='Novo Centro de Custo',
                         codigo_padrao=codigo_padrao,
                         obras=obras,
                         departamentos=departamentos)

@main_bp.route('/financeiro/sincronizar-fluxo', methods=['POST'])
@login_required
def sincronizar_fluxo():
    """Sincronizar dados do fluxo de caixa"""
    try:
        from financeiro import sincronizar_fluxo_caixa
        sincronizar_fluxo_caixa()
        
        if request.is_json:
            return jsonify({'success': True, 'message': 'Fluxo de caixa sincronizado com sucesso!'})
        else:
            flash('Fluxo de caixa sincronizado com sucesso!', 'success')
            return redirect(url_for('main.fluxo_caixa'))
    except Exception as e:
        if request.is_json:
            return jsonify({'success': False, 'message': str(e)})
        else:
            flash(f'Erro ao sincronizar fluxo de caixa: {str(e)}', 'error')
            return redirect(url_for('main.fluxo_caixa'))

@main_bp.route('/horarios')
@login_required
def horarios():
    """Página de gestão de horários de trabalho"""
    horarios = HorarioTrabalho.query.all()
    return render_template('horarios.html', horarios=horarios)

@main_bp.route('/horarios/novo', methods=['POST'])
@login_required
def novo_horario():
    """Criar novo horário de trabalho"""
    try:
        nome = request.form.get('nome')
        entrada = request.form.get('entrada')
        saida_almoco = request.form.get('saida_almoco')
        retorno_almoco = request.form.get('retorno_almoco')
        saida = request.form.get('saida')
        dias_semana = request.form.get('dias_semana')
        
        # Verificar se já existe horário com o mesmo nome
        horario_existente = HorarioTrabalho.query.filter_by(nome=nome).first()
        if horario_existente:
            flash('Já existe um horário com este nome!', 'error')
            return redirect(url_for('main.horarios'))
        
        # Calcular horas diárias
        entrada_time = datetime.strptime(entrada, '%H:%M').time()
        saida_almoco_time = datetime.strptime(saida_almoco, '%H:%M').time()
        retorno_almoco_time = datetime.strptime(retorno_almoco, '%H:%M').time()
        saida_time = datetime.strptime(saida, '%H:%M').time()
        
        # Calcular horas trabalhadas (manhã + tarde)
        manha_inicio = datetime.combine(date.today(), entrada_time)
        manha_fim = datetime.combine(date.today(), saida_almoco_time)
        tarde_inicio = datetime.combine(date.today(), retorno_almoco_time)
        tarde_fim = datetime.combine(date.today(), saida_time)
        
        horas_manha = (manha_fim - manha_inicio).total_seconds() / 3600
        horas_tarde = (tarde_fim - tarde_inicio).total_seconds() / 3600
        horas_diarias = horas_manha + horas_tarde
        
        # Calcular valor da hora (baseado no salário mínimo padrão)
        valor_hora = 12.00  # Valor padrão, pode ser ajustado
        
        # Criar horário
        horario = HorarioTrabalho(
            nome=nome,
            entrada=entrada_time,
            saida_almoco=saida_almoco_time,
            retorno_almoco=retorno_almoco_time,
            saida=saida_time,
            dias_semana=dias_semana,
            horas_diarias=horas_diarias,
            valor_hora=valor_hora
        )
        
        db.session.add(horario)
        db.session.commit()
        
        flash('Horário de trabalho criado com sucesso!', 'success')
        return redirect(url_for('main.horarios'))
        
    except Exception as e:
        db.session.rollback()
        flash(f'Erro ao criar horário: {str(e)}', 'error')
        return redirect(url_for('main.horarios'))

@main_bp.route('/horarios/editar/<int:id>', methods=['POST'])
@login_required
def editar_horario(id):
    """Editar horário de trabalho"""
    try:
        horario = HorarioTrabalho.query.get_or_404(id)
        
        nome = request.form.get('nome')
        entrada = request.form.get('entrada')
        saida_almoco = request.form.get('saida_almoco')
        retorno_almoco = request.form.get('retorno_almoco')
        saida = request.form.get('saida')
        dias_semana = request.form.get('dias_semana')
        
        # Verificar se já existe outro horário com o mesmo nome
        horario_existente = HorarioTrabalho.query.filter(
            HorarioTrabalho.nome == nome,
            HorarioTrabalho.id != id
        ).first()
        if horario_existente:
            flash('Já existe um horário com este nome!', 'error')
            return redirect(url_for('main.horarios'))
        
        # Calcular horas diárias
        entrada_time = datetime.strptime(entrada, '%H:%M').time()
        saida_almoco_time = datetime.strptime(saida_almoco, '%H:%M').time()
        retorno_almoco_time = datetime.strptime(retorno_almoco, '%H:%M').time()
        saida_time = datetime.strptime(saida, '%H:%M').time()
        
        # Calcular horas trabalhadas (manhã + tarde)
        manha_inicio = datetime.combine(date.today(), entrada_time)
        manha_fim = datetime.combine(date.today(), saida_almoco_time)
        tarde_inicio = datetime.combine(date.today(), retorno_almoco_time)
        tarde_fim = datetime.combine(date.today(), saida_time)
        
        horas_manha = (manha_fim - manha_inicio).total_seconds() / 3600
        horas_tarde = (tarde_fim - tarde_inicio).total_seconds() / 3600
        horas_diarias = horas_manha + horas_tarde
        
        # Atualizar horário
        horario.nome = nome
        horario.entrada = entrada_time
        horario.saida_almoco = saida_almoco_time
        horario.retorno_almoco = retorno_almoco_time
        horario.saida = saida_time
        horario.dias_semana = dias_semana
        horario.horas_diarias = horas_diarias
        
        db.session.commit()
        
        flash('Horário de trabalho atualizado com sucesso!', 'success')
        return redirect(url_for('main.horarios'))
        
    except Exception as e:
        db.session.rollback()
        flash(f'Erro ao atualizar horário: {str(e)}', 'error')
        return redirect(url_for('main.horarios'))

@main_bp.route('/horarios/excluir/<int:id>', methods=['POST'])
@login_required
def excluir_horario(id):
    """Excluir horário de trabalho"""
    try:
        horario = HorarioTrabalho.query.get_or_404(id)
        
        # Verificar se há funcionários usando este horário
        funcionarios_usando = Funcionario.query.filter_by(horario_trabalho_id=id).count()
        if funcionarios_usando > 0:
            flash(f'Não é possível excluir. Existem {funcionarios_usando} funcionários usando este horário.', 'error')
            return redirect(url_for('main.horarios'))
        
        db.session.delete(horario)
        db.session.commit()
        
        flash('Horário de trabalho excluído com sucesso!', 'success')
        return redirect(url_for('main.horarios'))
        
    except Exception as e:
        db.session.rollback()
        flash(f'Erro ao excluir horário: {str(e)}', 'error')
        return redirect(url_for('main.horarios'))

# ==========================================
# MÓDULOS CRUD - CONTROLE DE PONTO, OUTROS CUSTOS E ALIMENTAÇÃO
# ==========================================

@main_bp.route('/controle-ponto')
@login_required
def controle_ponto():
    """Página principal do controle de ponto"""
    # Filtros
    funcionario_id = request.args.get('funcionario_id')
    data_inicio = request.args.get('data_inicio')
    data_fim = request.args.get('data_fim')
    tipo_registro = request.args.get('tipo_registro')
    
    # Query base
    query = RegistroPonto.query
    
    # Aplicar filtros
    if funcionario_id:
        query = query.filter(RegistroPonto.funcionario_id == funcionario_id)
    
    if data_inicio:
        query = query.filter(RegistroPonto.data >= datetime.strptime(data_inicio, '%Y-%m-%d').date())
    
    if data_fim:
        query = query.filter(RegistroPonto.data <= datetime.strptime(data_fim, '%Y-%m-%d').date())
    
    if tipo_registro:
        query = query.filter(RegistroPonto.tipo_registro == tipo_registro)
    
    # Buscar registros com joins
    registros = query.options(
        joinedload(RegistroPonto.funcionario),
        joinedload(RegistroPonto.obra)
    ).order_by(RegistroPonto.data.desc()).all()
    
    # Dados para formulário
    funcionarios = Funcionario.query.filter_by(ativo=True).order_by(Funcionario.nome).all()
    obras = Obra.query.filter_by(status='Em andamento').order_by(Obra.nome).all()
    
    return render_template('controle_ponto.html',
                         registros=registros,
                         funcionarios=funcionarios,
                         obras=obras)

@main_bp.route('/ponto/registro', methods=['POST'])
@login_required
def criar_registro_ponto():
    """Criar novo registro de ponto"""
    try:
        funcionario_id = request.form.get('funcionario_id')
        data = datetime.strptime(request.form.get('data'), '%Y-%m-%d').date()
        tipo_registro = request.form.get('tipo_registro', 'trabalho_normal')
        obra_id = request.form.get('obra_id') or None
        
        # Criar registro
        registro = RegistroPonto(
            funcionario_id=funcionario_id,
            data=data,
            tipo_registro=tipo_registro,
            obra_id=obra_id
        )
        
        # Adicionar horários se não for falta
        if tipo_registro not in ['falta', 'falta_justificada']:
            entrada = request.form.get('entrada')
            saida_almoco = request.form.get('saida_almoco')
            retorno_almoco = request.form.get('retorno_almoco')
            saida = request.form.get('saida')
            
            if entrada:
                registro.entrada = datetime.strptime(entrada, '%H:%M').time()
            if saida_almoco:
                registro.saida_almoco = datetime.strptime(saida_almoco, '%H:%M').time()
            if retorno_almoco:
                registro.retorno_almoco = datetime.strptime(retorno_almoco, '%H:%M').time()
            if saida:
                registro.saida = datetime.strptime(saida, '%H:%M').time()
        
        # Percentual de extras
        percentual_extras = request.form.get('percentual_extras')
        if percentual_extras:
            registro.percentual_extras = float(percentual_extras)
        
        # Observações
        registro.observacoes = request.form.get('observacoes')
        
        db.session.add(registro)
        db.session.commit()
        
        return jsonify({'success': True})
        
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': str(e)}), 500

@main_bp.route('/ponto/registro/<int:registro_id>', methods=['GET'])
@login_required
def obter_registro_ponto(registro_id):
    """Obter dados de um registro de ponto"""
    registro = RegistroPonto.query.get_or_404(registro_id)
    
    return jsonify({
        'id': registro.id,
        'funcionario_id': registro.funcionario_id,
        'data': registro.data.isoformat(),
        'tipo_registro': registro.tipo_registro,
        'obra_id': registro.obra_id,
        'entrada': registro.entrada.strftime('%H:%M') if registro.entrada else None,
        'saida_almoco': registro.saida_almoco.strftime('%H:%M') if registro.saida_almoco else None,
        'retorno_almoco': registro.retorno_almoco.strftime('%H:%M') if registro.retorno_almoco else None,
        'saida': registro.saida.strftime('%H:%M') if registro.saida else None,
        'percentual_extras': registro.percentual_extras,
        'observacoes': registro.observacoes
    })

@main_bp.route('/ponto/registro/<int:registro_id>', methods=['PUT'])
@login_required
def atualizar_registro_ponto(registro_id):
    """Atualizar registro de ponto"""
    try:
        registro = RegistroPonto.query.get_or_404(registro_id)
        
        # Atualizar campos básicos
        registro.funcionario_id = request.form.get('funcionario_id')
        registro.data = datetime.strptime(request.form.get('data'), '%Y-%m-%d').date()
        registro.tipo_registro = request.form.get('tipo_registro', 'trabalho_normal')
        registro.obra_id = request.form.get('obra_id') or None
        
        # Atualizar horários
        if registro.tipo_registro not in ['falta', 'falta_justificada']:
            entrada = request.form.get('entrada')
            saida_almoco = request.form.get('saida_almoco')
            retorno_almoco = request.form.get('retorno_almoco')
            saida = request.form.get('saida')
            
            registro.entrada = datetime.strptime(entrada, '%H:%M').time() if entrada else None
            registro.saida_almoco = datetime.strptime(saida_almoco, '%H:%M').time() if saida_almoco else None
            registro.retorno_almoco = datetime.strptime(retorno_almoco, '%H:%M').time() if retorno_almoco else None
            registro.saida = datetime.strptime(saida, '%H:%M').time() if saida else None
        else:
            # Limpar horários para faltas
            registro.entrada = None
            registro.saida_almoco = None
            registro.retorno_almoco = None
            registro.saida = None
        
        # Percentual de extras
        percentual_extras = request.form.get('percentual_extras')
        registro.percentual_extras = float(percentual_extras) if percentual_extras else None
        
        # Observações
        registro.observacoes = request.form.get('observacoes')
        
        db.session.commit()
        
        return jsonify({'success': True})
        
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': str(e)}), 500

@main_bp.route('/ponto/registro/<int:registro_id>', methods=['DELETE'])
@login_required
def excluir_registro_ponto(registro_id):
    """Excluir registro de ponto"""
    try:
        registro = RegistroPonto.query.get_or_404(registro_id)
        db.session.delete(registro)
        db.session.commit()
        
        return jsonify({'success': True})
        
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': str(e)}), 500

@main_bp.route('/outros-custos')
@login_required
def controle_outros_custos():
    """Página principal do controle de outros custos"""
    # Filtros
    funcionario_id = request.args.get('funcionario_id')
    data_inicio = request.args.get('data_inicio')
    data_fim = request.args.get('data_fim')
    tipo = request.args.get('tipo')
    
    # Query base
    query = OutroCusto.query
    
    # Aplicar filtros
    if funcionario_id:
        query = query.filter(OutroCusto.funcionario_id == funcionario_id)
    
    if data_inicio:
        query = query.filter(OutroCusto.data >= datetime.strptime(data_inicio, '%Y-%m-%d').date())
    
    if data_fim:
        query = query.filter(OutroCusto.data <= datetime.strptime(data_fim, '%Y-%m-%d').date())
    
    if tipo:
        query = query.filter(OutroCusto.tipo == tipo)
    
    # Buscar registros com joins
    custos = query.options(
        joinedload(OutroCusto.funcionario)
    ).order_by(OutroCusto.data.desc()).all()
    
    # Dados para formulário
    funcionarios = Funcionario.query.filter_by(ativo=True).order_by(Funcionario.nome).all()
    
    return render_template('controle_outros_custos.html',
                         custos=custos,
                         funcionarios=funcionarios)

@main_bp.route('/outros-custos/custo', methods=['POST'])
@login_required
def criar_outro_custo_crud():
    """Criar novo custo"""
    try:
        funcionario_id = request.form.get('funcionario_id')
        data = datetime.strptime(request.form.get('data'), '%Y-%m-%d').date()
        tipo = request.form.get('tipo')
        valor = float(request.form.get('valor'))
        descricao = request.form.get('descricao')
        
        # Criar custo
        custo = OutroCusto(
            funcionario_id=funcionario_id,
            data=data,
            tipo=tipo,
            valor=valor,
            descricao=descricao
        )
        
        db.session.add(custo)
        db.session.commit()
        
        return jsonify({'success': True})
        
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': str(e)}), 500

@main_bp.route('/outros-custos/custo/<int:custo_id>', methods=['GET'])
@login_required
def obter_outro_custo_crud(custo_id):
    """Obter dados de um custo"""
    custo = OutroCusto.query.get_or_404(custo_id)
    
    return jsonify({
        'id': custo.id,
        'funcionario_id': custo.funcionario_id,
        'data': custo.data.isoformat(),
        'tipo': custo.tipo,
        'valor': custo.valor,
        'descricao': custo.descricao
    })

@main_bp.route('/outros-custos/custo/<int:custo_id>', methods=['PUT'])
@login_required
def atualizar_outro_custo_crud(custo_id):
    """Atualizar custo"""
    try:
        custo = OutroCusto.query.get_or_404(custo_id)
        
        custo.funcionario_id = request.form.get('funcionario_id')
        custo.data = datetime.strptime(request.form.get('data'), '%Y-%m-%d').date()
        custo.tipo = request.form.get('tipo')
        custo.valor = float(request.form.get('valor'))
        custo.descricao = request.form.get('descricao')
        
        db.session.commit()
        
        return jsonify({'success': True})
        
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': str(e)}), 500

@main_bp.route('/outros-custos/custo/<int:custo_id>', methods=['DELETE'])
@login_required
def excluir_outro_custo_crud(custo_id):
    """Excluir custo"""
    try:
        custo = OutroCusto.query.get_or_404(custo_id)
        db.session.delete(custo)
        db.session.commit()
        
        return jsonify({'success': True})
        
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': str(e)}), 500

@main_bp.route('/alimentacao')
@login_required
def controle_alimentacao():
    """Página principal do controle de alimentação"""
    # Filtros
    funcionario_id = request.args.get('funcionario_id')
    restaurante_id = request.args.get('restaurante_id')
    data_inicio = request.args.get('data_inicio')
    data_fim = request.args.get('data_fim')
    tipo_refeicao = request.args.get('tipo_refeicao')
    
    # Query base
    query = RegistroAlimentacao.query
    
    # Aplicar filtros
    if funcionario_id:
        query = query.filter(RegistroAlimentacao.funcionario_id == funcionario_id)
    
    if restaurante_id:
        query = query.filter(RegistroAlimentacao.restaurante_id == restaurante_id)
    
    if data_inicio:
        query = query.filter(RegistroAlimentacao.data >= datetime.strptime(data_inicio, '%Y-%m-%d').date())
    
    if data_fim:
        query = query.filter(RegistroAlimentacao.data <= datetime.strptime(data_fim, '%Y-%m-%d').date())
    
    if tipo_refeicao:
        query = query.filter(RegistroAlimentacao.tipo_refeicao == tipo_refeicao)
    
    # Buscar registros com joins
    registros = query.options(
        joinedload(RegistroAlimentacao.funcionario),
        joinedload(RegistroAlimentacao.restaurante)
    ).order_by(RegistroAlimentacao.data.desc()).all()
    
    # Dados para formulário
    funcionarios = Funcionario.query.filter_by(ativo=True).order_by(Funcionario.nome).all()
    restaurantes = Restaurante.query.filter_by(ativo=True).order_by(Restaurante.nome).all()
    
    return render_template('controle_alimentacao.html',
                         registros=registros,
                         funcionarios=funcionarios,
                         restaurantes=restaurantes)

@main_bp.route('/alimentacao/registro', methods=['POST'])
@login_required
def criar_registro_alimentacao():
    """Criar novo registro de alimentação"""
    try:
        funcionario_id = request.form.get('funcionario_id')
        restaurante_id = request.form.get('restaurante_id')
        data = datetime.strptime(request.form.get('data'), '%Y-%m-%d').date()
        tipo_refeicao = request.form.get('tipo_refeicao')
        valor = float(request.form.get('valor'))
        quantidade = int(request.form.get('quantidade', 1))
        observacoes = request.form.get('observacoes')
        
        # Criar registro
        registro = RegistroAlimentacao(
            funcionario_id=funcionario_id,
            restaurante_id=restaurante_id,
            data=data,
            tipo_refeicao=tipo_refeicao,
            valor=valor,
            quantidade=quantidade,
            observacoes=observacoes
        )
        
        db.session.add(registro)
        db.session.commit()
        
        return jsonify({'success': True})
        
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': str(e)}), 500

@main_bp.route('/alimentacao/registro/<int:registro_id>', methods=['GET'])
@login_required
def obter_registro_alimentacao(registro_id):
    """Obter dados de um registro de alimentação"""
    registro = RegistroAlimentacao.query.get_or_404(registro_id)
    
    return jsonify({
        'id': registro.id,
        'funcionario_id': registro.funcionario_id,
        'restaurante_id': registro.restaurante_id,
        'data': registro.data.isoformat(),
        'tipo_refeicao': registro.tipo_refeicao,
        'valor': registro.valor,
        'quantidade': registro.quantidade,
        'observacoes': registro.observacoes
    })

@main_bp.route('/alimentacao/registro/<int:registro_id>', methods=['PUT'])
@login_required
def atualizar_registro_alimentacao(registro_id):
    """Atualizar registro de alimentação"""
    try:
        registro = RegistroAlimentacao.query.get_or_404(registro_id)
        
        registro.funcionario_id = request.form.get('funcionario_id')
        registro.restaurante_id = request.form.get('restaurante_id')
        registro.data = datetime.strptime(request.form.get('data'), '%Y-%m-%d').date()
        registro.tipo_refeicao = request.form.get('tipo_refeicao')
        registro.valor = float(request.form.get('valor'))
        registro.quantidade = int(request.form.get('quantidade', 1))
        registro.observacoes = request.form.get('observacoes')
        
        db.session.commit()
        
        return jsonify({'success': True})
        
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': str(e)}), 500

@main_bp.route('/alimentacao/registro/<int:registro_id>', methods=['DELETE'])
@login_required
def excluir_registro_alimentacao(registro_id):
    """Excluir registro de alimentação"""
    try:
        registro = RegistroAlimentacao.query.get_or_404(registro_id)
        db.session.delete(registro)
        db.session.commit()
        
        return jsonify({'success': True})
        
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': str(e)}), 500



# API Endpoints para RDO
@main_bp.route("/api/obras/autocomplete")
@login_required
def api_obras_autocomplete():
    """API para autocomplete de obras"""
    try:
        q = request.args.get("q", "").strip()
        
        # Query base - obras ativas
        query = Obra.query.filter(Obra.ativo == True)
        
        # Se tem termo de busca, filtrar
        if q:
            query = query.filter(
                or_(
                    Obra.nome.ilike(f"%{q}%"),
                    Obra.codigo.ilike(f"%{q}%"),
                    Obra.endereco.ilike(f"%{q}%")
                )
            )
        
        # Limitar resultados e ordenar
        obras = query.order_by(Obra.nome).limit(20).all()
        
        # Debug - log para verificar
        print(f"Buscando obras com termo: '{q}' - Encontradas: {len(obras)}")
        
        resultado = []
        for obra in obras:
            resultado.append({
                "id": obra.id,
                "nome": obra.nome,
                "codigo": obra.codigo or "S/C",
                "endereco": obra.endereco or "Endereço não informado",
                "area_total_m2": float(obra.area_total_m2) if obra.area_total_m2 else 0,
                "status": obra.status or "Em andamento"
            })
        
        return jsonify(resultado)
        
    except Exception as e:
        print(f"Erro no endpoint obras_autocomplete: {str(e)}")
        return jsonify([]), 500

@main_bp.route("/api/obras/todas")
@login_required
def api_obras_todas():
    """API para carregar todas as obras (fallback)"""
    try:
        obras = Obra.query.filter(Obra.ativo == True).order_by(Obra.nome).all()
        
        return jsonify([{
            "id": obra.id,
            "nome": obra.nome,
            "codigo": obra.codigo or "S/C",
            "endereco": obra.endereco or "Endereço não informado"
        } for obra in obras])
        
    except Exception as e:
        print(f"Erro ao carregar todas as obras: {str(e)}")
        return jsonify([]), 500

@main_bp.route("/api/funcionarios/rdo-autocomplete")
@login_required
def api_funcionarios_rdo_autocomplete():
    """API para autocomplete de funcionários com dados de ponto"""
    try:
        q = request.args.get("q", "").strip()
        data_rdo = request.args.get("data_rdo")
        
        # Query base - funcionários ativos
        query = Funcionario.query.filter(Funcionario.ativo == True)
        
        # Se tem termo de busca
        if q:
            query = query.filter(
                or_(
                    Funcionario.nome.ilike(f"%{q}%"),
                    Funcionario.codigo.ilike(f"%{q}%"),
                    Funcionario.cpf.ilike(f"%{q}%")
                )
            )
        
        funcionarios = query.order_by(Funcionario.nome).limit(20).all()
        
        print(f"Buscando funcionários: '{q}' - Encontrados: {len(funcionarios)}")
        
        resultado = []
        for func in funcionarios:
            # Buscar dados do ponto para a data
            presente_hoje = False
            horas_trabalhadas = 0
            
            if data_rdo:
                try:
                    data_consulta = datetime.strptime(data_rdo, "%Y-%m-%d").date()
                    registro_ponto = RegistroPonto.query.filter_by(
                        funcionario_id=func.id,
                        data=data_consulta
                    ).first()
                    
                    if registro_ponto:
                        presente_hoje = bool(registro_ponto.hora_entrada)
                        horas_trabalhadas = registro_ponto.horas_trabalhadas or 0
                except:
                    pass
            
            resultado.append({
                "id": func.id,
                "nome": func.nome,
                "codigo": func.codigo or f"F{func.id:03d}",
                "funcao": func.funcao.nome if func.funcao else "Não definida",
                "salario": float(func.salario) if func.salario else 0,
                "presente_hoje": presente_hoje,
                "horas_trabalhadas": horas_trabalhadas
            })
        
        return jsonify(resultado)
        
    except Exception as e:
        print(f"Erro no endpoint funcionarios_rdo_autocomplete: {str(e)}")
        return jsonify([]), 500

@main_bp.route("/api/funcionarios/todos")
@login_required
def api_funcionarios_todos():
    """API para carregar todos os funcionários (fallback)"""
    try:
        funcionarios = Funcionario.query.filter(Funcionario.ativo == True).order_by(Funcionario.nome).all()
        
        return jsonify([{
            "id": func.id,
            "nome": func.nome,
            "codigo": func.codigo or f"F{func.id:03d}",
            "funcao": func.funcao.nome if func.funcao else "Não definida"
        } for func in funcionarios])
        
    except Exception as e:
        print(f"Erro ao carregar funcionários: {str(e)}")
        return jsonify([]), 500

@main_bp.route("/api/servicos/autocomplete")
@login_required
def api_servicos_autocomplete():
    """API para autocomplete de serviços"""
    q = request.args.get("q", "")
    ativo = request.args.get("ativo", "true").lower() == "true"
    
    query = Servico.query.filter(Servico.ativo == ativo)
    
    if q:
        query = query.filter(
            or_(
                Servico.nome.ilike(f"%{q}%"),
                Servico.categoria.ilike(f"%{q}%")
            )
        )
    
    servicos = query.limit(10).all()
    
    return jsonify([{
        "id": servico.id,
        "nome": servico.nome,
        "categoria": servico.categoria,
        "unidade_medida": servico.unidade_medida,
        "unidade_simbolo": servico.unidade_simbolo,
        "custo_unitario": float(servico.custo_unitario) if servico.custo_unitario else 0
    } for servico in servicos])

@main_bp.route("/api/servicos/<int:servico_id>")
@login_required
def api_servico_detalhes(servico_id):
    """API para detalhes de um serviço específico com subatividades"""
    servico = Servico.query.get_or_404(servico_id)
    
    subatividades = SubAtividade.query.filter_by(servico_id=servico_id).all()
    
    return jsonify({
        "id": servico.id,
        "nome": servico.nome,
        "categoria": servico.categoria,
        "unidade_medida": servico.unidade_medida,
        "unidade_simbolo": servico.unidade_simbolo,
        "custo_unitario": float(servico.custo_unitario) if servico.custo_unitario else 0,
        "subatividades": [{
            "id": sub.id,
            "nome": sub.nome,
            "descricao": sub.descricao
        } for sub in subatividades]
    })

@main_bp.route("/api/equipamentos/autocomplete")
@login_required
def api_equipamentos_autocomplete():
    """API para autocomplete de equipamentos/veículos"""
    q = request.args.get("q", "")
    ativo = request.args.get("ativo", "true").lower() == "true"
    
    query = Veiculo.query.filter(Veiculo.ativo == ativo)
    
    if q:
        query = query.filter(
            or_(
                Veiculo.marca.ilike(f"%{q}%"),
                Veiculo.modelo.ilike(f"%{q}%"),
                Veiculo.placa.ilike(f"%{q}%"),
                Veiculo.tipo.ilike(f"%{q}%")
            )
        )
    
    veiculos = query.limit(10).all()
    
    return jsonify([{
        "id": veiculo.id,
        "nome": f"{veiculo.marca} {veiculo.modelo}",
        "placa": veiculo.placa,
        "tipo": veiculo.tipo,
        "status": veiculo.status
    } for veiculo in veiculos])

@main_bp.route("/api/ponto/funcionario/<int:funcionario_id>/data/<string:data>")
@login_required
def api_ponto_funcionario_data(funcionario_id, data):
    """API para buscar dados de ponto de um funcionário em uma data específica"""
    try:
        funcionario = Funcionario.query.get_or_404(funcionario_id)
        data_consulta = datetime.strptime(data, "%Y-%m-%d").date()
        
        registro_ponto = RegistroPonto.query.filter_by(
            funcionario_id=funcionario_id,
            data=data_consulta
        ).first()
        
        if registro_ponto:
            return jsonify({
                "success": True,
                "funcionario": {
                    "id": funcionario.id,
                    "nome": funcionario.nome,
                    "codigo": funcionario.codigo,
                    "funcao": funcionario.funcao.nome if funcionario.funcao else "Sem função"
                },
                "registro_ponto": {
                    "hora_entrada": registro_ponto.hora_entrada.strftime("%H:%M") if registro_ponto.hora_entrada else None,
                    "hora_saida": registro_ponto.hora_saida.strftime("%H:%M") if registro_ponto.hora_saida else None,
                    "horas_trabalhadas": registro_ponto.horas_trabalhadas or 0,
                    "tipo_registro": registro_ponto.tipo_registro
                }
            })
        else:
            return jsonify({
                "success": False,
                "message": "Nenhum registro de ponto encontrado para esta data"
            })
    
    except Exception as e:
        return jsonify({
            "success": False,
            "message": f"Erro ao buscar dados: {str(e)}"
        }), 500

@main_bp.route("/api/rdo/salvar", methods=["POST"])
@login_required
def api_rdo_salvar():
    """API para salvar RDO como rascunho"""
    try:
        dados = request.get_json()
        
        # Validações básicas
        if not dados.get("data_relatorio") or not dados.get("obra_id"):
            return jsonify({
                "success": False,
                "message": "Data do relatório e obra são obrigatórios"
            }), 400
        
        # Gerar número único do RDO
        import uuid
        numero_rdo = f"RDO-{datetime.now().year}-{str(uuid.uuid4())[:8].upper()}"
        
        rdo = RDO(
            numero_rdo=numero_rdo,
            data_relatorio=datetime.strptime(dados["data_relatorio"], "%Y-%m-%d").date(),
            obra_id=dados["obra_id"],
            criado_por_id=current_user.id,
            tempo_manha=dados.get("tempo_manha", ""),
            tempo_tarde=dados.get("tempo_tarde", ""),
            tempo_noite=dados.get("tempo_noite", ""),
            observacoes_meteorologicas=dados.get("observacoes_meteorologicas", ""),
            comentario_geral=dados.get("comentario_geral", ""),
            status="Rascunho"
        )
        
        db.session.add(rdo)
        db.session.commit()
        
        return jsonify({
            "success": True,
            "message": "RDO salvo como rascunho com sucesso",
            "rdo_id": rdo.id
        })
    
    except Exception as e:
        db.session.rollback()
        return jsonify({
            "success": False,
            "message": f"Erro ao salvar RDO: {str(e)}"
        }), 500

@main_bp.route("/api/rdo/finalizar", methods=["POST"])
@login_required
def api_rdo_finalizar():
    """API para finalizar RDO"""
    try:
        dados = request.get_json()
        
        # Validações obrigatórias
        if not dados.get("data_relatorio") or not dados.get("obra_id"):
            return jsonify({
                "success": False,
                "message": "Data do relatório e obra são obrigatórios"
            }), 400
        
        # Gerar número único do RDO
        import uuid
        numero_rdo = f"RDO-{datetime.now().year}-{str(uuid.uuid4())[:8].upper()}"
        
        rdo = RDO(
            numero_rdo=numero_rdo,
            data_relatorio=datetime.strptime(dados["data_relatorio"], "%Y-%m-%d").date(),
            obra_id=dados["obra_id"],
            criado_por_id=current_user.id,
            tempo_manha=dados.get("tempo_manha", ""),
            tempo_tarde=dados.get("tempo_tarde", ""),
            tempo_noite=dados.get("tempo_noite", ""),
            observacoes_meteorologicas=dados.get("observacoes_meteorologicas", ""),
            comentario_geral=dados.get("comentario_geral", ""),
            status="Finalizado"
        )
        
        db.session.add(rdo)
        db.session.flush()  # Para obter o ID do RDO
        
        # Salvar dados de mão de obra
        for func_data in dados.get("funcionarios", []):
            if func_data.get("funcionario_id"):
                rdo_mao_obra = RDOMaoObra(
                    rdo_id=rdo.id,
                    funcionario_id=func_data["funcionario_id"],
                    horas_trabalhadas=float(func_data.get("horas", 0)),
                    funcao_exercida=func_data.get("funcao_exercida", ""),
                    presente=func_data.get("presente", True)
                )
                db.session.add(rdo_mao_obra)
        
        # Salvar atividades
        for ativ_data in dados.get("atividades", []):
            if ativ_data.get("servico_id"):
                rdo_atividade = RDOAtividade(
                    rdo_id=rdo.id,
                    servico_id=ativ_data["servico_id"],
                    quantidade=float(ativ_data.get("quantidade", 0)),
                    tempo_execucao=float(ativ_data.get("tempo", 0)),
                    observacoes=ativ_data.get("observacoes", "")
                )
                db.session.add(rdo_atividade)
        
        # Salvar equipamentos
        for equip_data in dados.get("equipamentos", []):
            if equip_data.get("equipamento_id"):
                rdo_equipamento = RDOEquipamento(
                    rdo_id=rdo.id,
                    veiculo_id=equip_data["equipamento_id"],
                    horas_uso=float(equip_data.get("horas_uso", 0)),
                    status=equip_data.get("status", "operando"),
                    observacoes=equip_data.get("observacoes", "")
                )
                db.session.add(rdo_equipamento)
        
        # Salvar ocorrências
        for ocorr_data in dados.get("ocorrencias", []):
            if ocorr_data.get("tipo") and ocorr_data.get("descricao"):
                rdo_ocorrencia = RDOOcorrencia(
                    rdo_id=rdo.id,
                    tipo=ocorr_data["tipo"],
                    gravidade=ocorr_data.get("gravidade", "media"),
                    descricao=ocorr_data["descricao"]
                )
                db.session.add(rdo_ocorrencia)
        
        db.session.commit()
        
        return jsonify({
            "success": True,
            "message": "RDO finalizado com sucesso",
            "rdo_id": rdo.id
        })
    
    except Exception as e:
        db.session.rollback()
        return jsonify({
            "success": False,
            "message": f"Erro ao finalizar RDO: {str(e)}"
        }), 500

# API para carregar serviços de uma obra específica
@main_bp.route('/api/obras/<int:obra_id>/servicos')
@login_required
def api_servicos_obra(obra_id):
    """API para carregar serviços associados a uma obra"""
    try:
        servicos_obra = db.session.query(
            Servico.id,
            Servico.nome,
            Servico.categoria,
            Servico.unidade_medida,
            ServicoObra.quantidade_planejada,
            ServicoObra.observacoes
        ).join(
            ServicoObra, Servico.id == ServicoObra.servico_id
        ).filter(
            ServicoObra.obra_id == obra_id,
            Servico.ativo == True
        ).order_by(Servico.nome).all()
        
        servicos_data = []
        for servico in servicos_obra:
            servicos_data.append({
                'id': servico.id,
                'nome': servico.nome,
                'categoria': servico.categoria,
                'unidade_medida': servico.unidade_medida,
                'unidade_simbolo': get_simbolo_unidade(servico.unidade_medida),
                'quantidade_planejada': float(servico.quantidade_planejada) if servico.quantidade_planejada else 0,
                'observacoes': servico.observacoes
            })
        
        return jsonify({
            'success': True,
            'servicos': servicos_data
        })
        
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

# API para buscar último RDO de uma obra
@main_bp.route('/api/obras/<int:obra_id>/ultimo-rdo')
@login_required
def api_ultimo_rdo_obra(obra_id):
    """API para buscar o último RDO de uma obra para pré-popular valores"""
    try:
        # Buscar o RDO mais recente desta obra
        ultimo_rdo = RegistroRDO.query.filter_by(
            obra_id=obra_id
        ).order_by(RegistroRDO.data_relatorio.desc()).first()
        
        if not ultimo_rdo:
            return jsonify({
                'success': False,
                'message': 'Nenhum RDO anterior encontrado'
            })
        
        # Extrair atividades do JSON armazenado
        atividades = {}
        if ultimo_rdo.dados_atividades:
            try:
                atividades_json = json.loads(ultimo_rdo.dados_atividades)
                for atividade in atividades_json:
                    if atividade.get('servico_id'):
                        atividades[str(atividade['servico_id'])] = {
                            'quantidade': atividade.get('quantidade', 0),
                            'percentual': atividade.get('percentual', 0),
                            'observacoes': atividade.get('observacoes', ''),
                            'tempo': atividade.get('tempo', 0)
                        }
            except json.JSONDecodeError:
                pass
        
        return jsonify({
            'success': True,
            'rdo_id': ultimo_rdo.id,
            'data_relatorio': ultimo_rdo.data_relatorio.isoformat(),
            'atividades': atividades
        })
        
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

