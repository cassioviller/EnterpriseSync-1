from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify
from flask_login import login_required, current_user
from app import db
from models import *
from forms import *
from utils import calcular_horas_trabalhadas, calcular_custo_real_obra, calcular_custos_mes, calcular_kpis_funcionarios_geral
from datetime import datetime, date
from sqlalchemy import func

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
        db.session.add(funcionario)
        db.session.commit()
        flash('Funcionário cadastrado com sucesso!', 'success')
        return redirect(url_for('main.funcionarios'))
    
    return render_template('funcionarios.html', form=form, funcionarios=Funcionario.query.all())

@main_bp.route('/funcionarios/<int:id>/editar', methods=['GET', 'POST'])
@login_required
def editar_funcionario(id):
    funcionario = Funcionario.query.get_or_404(id)
    form = FuncionarioForm(obj=funcionario)
    form.departamento_id.choices = [(0, 'Selecione...')] + [(d.id, d.nome) for d in Departamento.query.all()]
    form.funcao_id.choices = [(0, 'Selecione...')] + [(f.id, f.nome) for f in Funcao.query.all()]
    
    if form.validate_on_submit():
        funcionario.nome = form.nome.data
        funcionario.cpf = form.cpf.data
        funcionario.rg = form.rg.data
        funcionario.data_nascimento = form.data_nascimento.data
        funcionario.endereco = form.endereco.data
        funcionario.telefone = form.telefone.data
        funcionario.email = form.email.data
        funcionario.data_admissao = form.data_admissao.data
        funcionario.salario = form.salario.data or 0.0
        funcionario.departamento_id = form.departamento_id.data if form.departamento_id.data > 0 else None
        funcionario.funcao_id = form.funcao_id.data if form.funcao_id.data > 0 else None
        funcionario.ativo = form.ativo.data
        
        db.session.commit()
        flash('Funcionário atualizado com sucesso!', 'success')
        return redirect(url_for('main.funcionarios'))
    
    return render_template('funcionarios.html', form=form, funcionario=funcionario, funcionarios=Funcionario.query.all())

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
    
    # Calcular KPIs individuais
    kpis = calcular_kpis_funcionario(id)
    
    # Buscar registros de ponto
    registros_ponto = RegistroPonto.query.filter_by(funcionario_id=id).order_by(RegistroPonto.data.desc()).limit(50).all()
    
    # Buscar ocorrências
    ocorrencias = Ocorrencia.query.filter_by(funcionario_id=id).order_by(Ocorrencia.data_inicio.desc()).all()
    
    # Buscar registros de alimentação
    registros_alimentacao = RegistroAlimentacao.query.filter_by(funcionario_id=id).order_by(RegistroAlimentacao.data.desc()).limit(50).all()
    
    # Buscar obras para os dropdowns
    obras = Obra.query.filter_by(status='Em andamento').all()
    
    # Obter dados para gráficos
    graficos = obter_dados_graficos_funcionario(id)
    
    # Criar objeto para KPIs (simular uma estrutura)
    class KPIData:
        def __init__(self, data):
            for key, value in data.items():
                setattr(self, key, value)
    
    kpis_obj = KPIData(kpis)
    
    return render_template('funcionario_perfil.html',
                         funcionario=funcionario,
                         kpis=kpis_obj,
                         registros_ponto=registros_ponto,
                         ocorrencias=ocorrencias,
                         registros_alimentacao=registros_alimentacao,
                         obras=obras,
                         graficos=graficos)

@main_bp.route('/funcionarios/<int:id>/excluir', methods=['POST'])
@login_required
def excluir_funcionario(id):
    funcionario = Funcionario.query.get_or_404(id)
    db.session.delete(funcionario)
    db.session.commit()
    flash('Funcionário excluído com sucesso!', 'success')
    return redirect(url_for('main.funcionarios'))

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
    
    obras = Obra.query.all()
    
    # Adicionar KPIs básicos para cada obra (últimos 30 dias)
    data_fim = date.today()
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
        obra.kpis = type('KPIs', (), {
            'total_rdos': total_rdos,
            'dias_trabalhados': dias_trabalhados,
            'custo_total': custo_alimentacao  # Simplificado para exibição nos cards
        })()
    
    return render_template('obras.html', obras=obras)

@main_bp.route('/obras/novo', methods=['GET', 'POST'])
@login_required
def nova_obra():
    form = ObraForm()
    form.responsavel_id.choices = [(0, 'Selecione...')] + [(f.id, f.nome) for f in Funcionario.query.filter_by(ativo=True).all()]
    
    if form.validate_on_submit():
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
        db.session.commit()
        flash('Obra cadastrada com sucesso!', 'success')
        return redirect(url_for('main.obras'))
    
    return render_template('obras.html', form=form, obras=Obra.query.all())

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
    
    obra = Obra.query.get_or_404(id)
    
    # Obter filtros de data da query string
    data_inicio_filtro = request.args.get('data_inicio')
    data_fim_filtro = request.args.get('data_fim')
    
    # Definir período padrão (últimos 30 dias)
    if not data_inicio_filtro or not data_fim_filtro:
        data_fim = date.today()
        data_inicio = data_fim - timedelta(days=30)
    else:
        data_inicio = datetime.strptime(data_inicio_filtro, '%Y-%m-%d').date()
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
            if registro.funcionario.salario:
                valor_hora = registro.funcionario.salario / 220  # 220 horas/mês aprox
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
                         kpis=kpis,
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
    return render_template('veiculos.html', veiculos=veiculos)

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
    
    # Buscar registros de uso (quando implementado)
    usos = []
    
    # Buscar registros de custos (quando implementado)
    custos = []
    
    # KPIs do veículo
    kpis = {
        'custo_total': 0,
        'total_usos': 0,
        'media_km': 0
    }
    
    return render_template('veiculos/detalhes_veiculo.html', 
                         veiculo=veiculo, 
                         usos=usos, 
                         custos=custos,
                         kpis=kpis)

@main_bp.route('/veiculos/<int:id>/editar', methods=['GET', 'POST'])
@login_required
def editar_veiculo_route(id):
    veiculo = Veiculo.query.get_or_404(id)
    form = VeiculoForm(obj=veiculo)
    
    if form.validate_on_submit():
        veiculo.placa = form.placa.data
        veiculo.marca = form.marca.data
        veiculo.modelo = form.modelo.data
        veiculo.ano = form.ano.data
        veiculo.tipo = form.tipo.data
        veiculo.status = form.status.data
        veiculo.km_atual = form.km_atual.data
        veiculo.data_ultima_manutencao = form.data_ultima_manutencao.data
        veiculo.data_proxima_manutencao = form.data_proxima_manutencao.data
        
        db.session.commit()
        flash('Veículo atualizado com sucesso!', 'success')
        return redirect(url_for('main.detalhes_veiculo', id=id))
    
    return render_template('veiculos/editar_veiculo.html', form=form, veiculo=veiculo)

@main_bp.route('/veiculos/<int:id>/novo_uso', methods=['GET', 'POST'])
@login_required
def novo_uso_veiculo(id):
    veiculo = Veiculo.query.get_or_404(id)
    form = UsoVeiculoForm()
    
    # Populando choices
    form.veiculo_id.choices = [(veiculo.id, f"{veiculo.placa} - {veiculo.marca} {veiculo.modelo}")]
    form.veiculo_id.data = veiculo.id
    form.funcionario_id.choices = [(0, 'Selecione...')] + [(f.id, f.nome) for f in Funcionario.query.filter_by(ativo=True).all()]
    form.obra_id.choices = [(0, 'Selecione...')] + [(o.id, o.nome) for o in Obra.query.all()]
    
    if form.validate_on_submit():
        uso = UsoVeiculo(
            veiculo_id=form.veiculo_id.data,
            funcionario_id=form.funcionario_id.data,
            obra_id=form.obra_id.data if form.obra_id.data != 0 else None,
            data_uso=form.data_uso.data,
            km_inicial=form.km_inicial.data,
            km_final=form.km_final.data,
            finalidade=form.finalidade.data,
            observacoes=form.observacoes.data
        )
        db.session.add(uso)
        
        # Atualizar KM atual do veículo se fornecido
        if form.km_final.data:
            veiculo.km_atual = form.km_final.data
        
        db.session.commit()
        flash('Uso do veículo registrado com sucesso!', 'success')
        return redirect(url_for('main.detalhes_veiculo', id=id))
    
    return render_template('veiculos/novo_uso.html', form=form, veiculo=veiculo)

@main_bp.route('/veiculos/<int:id>/novo_custo', methods=['GET', 'POST'])
@login_required
def novo_custo_veiculo(id):
    veiculo = Veiculo.query.get_or_404(id)
    form = CustoVeiculoForm()
    
    # Populando choices
    form.veiculo_id.choices = [(veiculo.id, f"{veiculo.placa} - {veiculo.marca} {veiculo.modelo}")]
    form.veiculo_id.data = veiculo.id
    
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
        
        # Atualizar KM atual do veículo se fornecido
        if form.km_atual.data:
            veiculo.km_atual = form.km_atual.data
        
        db.session.commit()
        flash('Custo do veículo registrado com sucesso!', 'success')
        return redirect(url_for('main.detalhes_veiculo', id=id))
    
    return render_template('veiculos/novo_custo.html', form=form, veiculo=veiculo)

# Serviços
@main_bp.route('/servicos')
@login_required
def servicos():
    servicos = Servico.query.all()
    return render_template('servicos.html', servicos=servicos)

@main_bp.route('/servicos/novo', methods=['GET', 'POST'])
@login_required
def novo_servico():
    form = ServicoForm()
    if form.validate_on_submit():
        servico = Servico(
            nome=form.nome.data,
            descricao=form.descricao.data,
            preco_unitario=form.preco_unitario.data or 0.0
        )
        db.session.add(servico)
        db.session.commit()
        flash('Serviço cadastrado com sucesso!', 'success')
        return redirect(url_for('main.servicos'))
    
    return render_template('servicos.html', form=form, servicos=Servico.query.all())

@main_bp.route('/servicos/<int:id>/editar', methods=['GET', 'POST'])
@login_required
def editar_servico(id):
    servico = Servico.query.get_or_404(id)
    form = ServicoForm(obj=servico)
    
    if form.validate_on_submit():
        servico.nome = form.nome.data
        servico.descricao = form.descricao.data
        servico.preco_unitario = form.preco_unitario.data or 0.0
        
        db.session.commit()
        flash('Serviço atualizado com sucesso!', 'success')
        return redirect(url_for('main.servicos'))
    
    return render_template('servicos.html', form=form, servico=servico, servicos=Servico.query.all())

@main_bp.route('/servicos/<int:id>/excluir', methods=['POST'])
@login_required
def excluir_servico(id):
    servico = Servico.query.get_or_404(id)
    db.session.delete(servico)
    db.session.commit()
    flash('Serviço excluído com sucesso!', 'success')
    return redirect(url_for('main.servicos'))

# Ponto
@main_bp.route('/ponto')
@login_required
def ponto():
    registros = RegistroPonto.query.order_by(RegistroPonto.data.desc()).limit(50).all()
    return render_template('ponto.html', registros=registros)

@main_bp.route('/ponto/novo', methods=['GET', 'POST'])
@login_required
def novo_ponto():
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

@main_bp.route('/relatorios/gerar/<tipo>', methods=['POST'])
@login_required
def gerar_relatorio(tipo):
    filtros = request.get_json()
    
    # Processar filtros
    data_inicio = datetime.strptime(filtros.get('dataInicio', ''), '%Y-%m-%d').date() if filtros.get('dataInicio') else None
    data_fim = datetime.strptime(filtros.get('dataFim', ''), '%Y-%m-%d').date() if filtros.get('dataFim') else None
    obra_id = filtros.get('obra') if filtros.get('obra') else None
    departamento_id = filtros.get('departamento') if filtros.get('departamento') else None
    
    if tipo == 'funcionarios':
        query = Funcionario.query
        if departamento_id:
            query = query.filter_by(departamento_id=departamento_id)
        funcionarios = query.all()
        
        html = '<div class="table-responsive"><table class="table table-striped">'
        html += '<thead><tr><th>Nome</th><th>CPF</th><th>Departamento</th><th>Função</th><th>Data Admissão</th><th>Salário</th><th>Status</th></tr></thead><tbody>'
        
        for f in funcionarios:
            status_badge = '<span class="badge bg-success">Ativo</span>' if f.ativo else '<span class="badge bg-danger">Inativo</span>'
            html += f'<tr><td>{f.nome}</td><td>{f.cpf}</td><td>{f.departamento_ref.nome if f.departamento_ref else "-"}</td>'
            html += f'<td>{f.funcao_ref.nome if f.funcao_ref else "-"}</td><td>{f.data_admissao.strftime("%d/%m/%Y") if f.data_admissao else "-"}</td>'
            html += f'<td>R$ {f.salario:,.2f}</td><td>{status_badge}</td></tr>'
        
        html += '</tbody></table></div>'
        
        return jsonify({
            'titulo': 'Lista de Funcionários',
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
        
        registros = query.order_by(RegistroPonto.data.desc()).limit(100).all()
        
        html = '<div class="table-responsive"><table class="table table-striped">'
        html += '<thead><tr><th>Funcionário</th><th>Data</th><th>Entrada</th><th>Saída Almoço</th><th>Retorno Almoço</th><th>Saída</th><th>Horas Trabalhadas</th><th>Horas Extras</th><th>Obra</th></tr></thead><tbody>'
        
        for r in registros:
            html += f'<tr><td>{r.funcionario_ref.nome}</td><td>{r.data.strftime("%d/%m/%Y")}</td>'
            html += f'<td>{r.hora_entrada.strftime("%H:%M") if r.hora_entrada else "-"}</td>'
            html += f'<td>{r.hora_almoco_saida.strftime("%H:%M") if r.hora_almoco_saida else "-"}</td>'
            html += f'<td>{r.hora_almoco_retorno.strftime("%H:%M") if r.hora_almoco_retorno else "-"}</td>'
            html += f'<td>{r.hora_saida.strftime("%H:%M") if r.hora_saida else "-"}</td>'
            horas_trab = f"{r.horas_trabalhadas:.2f}h" if r.horas_trabalhadas else "0.00h"
            horas_ext = f"{r.horas_extras:.2f}h" if r.horas_extras else "0.00h"
            html += f'<td>{horas_trab}</td><td>{horas_ext}</td>'
            html += f'<td>{r.obra_ref.nome if r.obra_ref else "-"}</td></tr>'
        
        html += '</tbody></table></div>'
        
        return jsonify({
            'titulo': 'Relatório de Ponto',
            'html': html
        })
    
    elif tipo == 'obras':
        query = Obra.query
        if obra_id:
            query = query.filter_by(id=obra_id)
        obras = query.all()
        
        html = '<div class="table-responsive"><table class="table table-striped">'
        html += '<thead><tr><th>Nome</th><th>Endereço</th><th>Data Início</th><th>Previsão Fim</th><th>Orçamento</th><th>Status</th><th>Responsável</th></tr></thead><tbody>'
        
        for o in obras:
            status_badges = {
                'Em andamento': 'bg-primary',
                'Concluída': 'bg-success',
                'Pausada': 'bg-warning',
                'Cancelada': 'bg-danger'
            }
            status_badge = f'<span class="badge {status_badges.get(o.status, "bg-secondary")}">{o.status}</span>'
            
            html += f'<tr><td>{o.nome}</td><td>{o.endereco or "-"}</td>'
            html += f'<td>{o.data_inicio.strftime("%d/%m/%Y") if o.data_inicio else "-"}</td>'
            html += f'<td>{o.data_previsao_fim.strftime("%d/%m/%Y") if o.data_previsao_fim else "-"}</td>'
            html += f'<td>R$ {o.orcamento:,.2f}</td><td>{status_badge}</td>'
            
            responsavel = Funcionario.query.get(o.responsavel_id) if o.responsavel_id else None
            html += f'<td>{responsavel.nome if responsavel else "-"}</td></tr>'
        
        html += '</tbody></table></div>'
        
        return jsonify({
            'titulo': 'Lista de Obras',
            'html': html
        })
    
    else:
        return jsonify({
            'titulo': 'Relatório não implementado',
            'html': '<p>Este relatório ainda não foi implementado.</p>'
        })

@main_bp.route('/api/dashboard-data')
@login_required
def dashboard_data():
    # Dados para gráficos do dashboard
    funcionarios_dept = db.session.query(
        Departamento.nome,
        func.count(Funcionario.id).label('total')
    ).join(Funcionario).filter(Funcionario.ativo == True).group_by(Departamento.nome).all()
    
    custos_obra = db.session.query(
        Obra.nome,
        func.sum(CustoObra.valor).label('total_custo')
    ).join(CustoObra).group_by(Obra.nome).limit(10).all()
    
    return jsonify({
        'funcionarios_departamento': {
            'labels': [item[0] for item in funcionarios_dept],
            'data': [item[1] for item in funcionarios_dept]
        },
        'custos_obra': {
            'labels': [item[0] for item in custos_obra],
            'data': [float(item[1]) for item in custos_obra]
        }
    })

# Routes para Ocorrências
@main_bp.route('/funcionarios/<int:funcionario_id>/ocorrencia/nova', methods=['POST'])
@login_required
def nova_ocorrencia(funcionario_id):
    from models import Ocorrencia
    
    funcionario = Funcionario.query.get_or_404(funcionario_id)
    
    # Criar nova ocorrência
    ocorrencia = Ocorrencia()
    ocorrencia.funcionario_id = funcionario_id
    ocorrencia.tipo = request.form.get('tipo')
    ocorrencia.data_inicio = datetime.strptime(request.form.get('data_inicio'), '%Y-%m-%d').date()
    if request.form.get('data_fim'):
        ocorrencia.data_fim = datetime.strptime(request.form.get('data_fim'), '%Y-%m-%d').date()
    ocorrencia.descricao = request.form.get('descricao')
    ocorrencia.status = request.form.get('status', 'Pendente')
    
    db.session.add(ocorrencia)
    db.session.commit()
    
    flash('Ocorrência registrada com sucesso!', 'success')
    return redirect(url_for('main.funcionario_perfil', id=funcionario_id))

# Horários de Trabalho
@main_bp.route('/horarios')
@login_required
def horarios():
    horarios = HorarioTrabalho.query.all()
    return render_template('horarios.html', horarios=horarios)

@main_bp.route('/horarios/novo', methods=['GET', 'POST'])
@login_required
def novo_horario():
    form = HorarioTrabalhoForm()
    
    if form.validate_on_submit():
        horario = HorarioTrabalho(
            nome=form.nome.data,
            entrada=form.entrada.data,
            saida_almoco=form.saida_almoco.data,
            retorno_almoco=form.retorno_almoco.data,
            saida=form.saida.data,
            dias_semana=form.dias_semana.data
        )
        db.session.add(horario)
        db.session.commit()
        flash('Horário de trabalho cadastrado com sucesso!', 'success')
        return redirect(url_for('main.horarios'))
    
    return render_template('horarios.html', form=form, horarios=HorarioTrabalho.query.all())

@main_bp.route('/horarios/editar/<int:id>', methods=['GET', 'POST'])
@login_required
def editar_horario(id):
    horario = HorarioTrabalho.query.get_or_404(id)
    form = HorarioTrabalhoForm(obj=horario)
    
    if form.validate_on_submit():
        horario.nome = form.nome.data
        horario.entrada = form.entrada.data
        horario.saida_almoco = form.saida_almoco.data
        horario.retorno_almoco = form.retorno_almoco.data
        horario.saida = form.saida.data
        horario.dias_semana = form.dias_semana.data
        
        db.session.commit()
        flash('Horário de trabalho atualizado com sucesso!', 'success')
        return redirect(url_for('main.horarios'))
    
    return render_template('horarios.html', form=form, horarios=HorarioTrabalho.query.all(), edit_id=id)

@main_bp.route('/horarios/excluir/<int:id>', methods=['POST'])
@login_required
def excluir_horario(id):
    horario = HorarioTrabalho.query.get_or_404(id)
    
    # Verificar se há funcionários usando este horário
    funcionarios_usando = Funcionario.query.filter_by(horario_trabalho_id=id).count()
    if funcionarios_usando > 0:
        flash(f'Não é possível excluir este horário. {funcionarios_usando} funcionário(s) estão usando este horário.', 'error')
        return redirect(url_for('main.horarios'))
    
    db.session.delete(horario)
    db.session.commit()
    flash('Horário de trabalho excluído com sucesso!', 'success')
    return redirect(url_for('main.horarios'))


# ============ ROTAS RDO ============

@main_bp.route('/rdo')
@login_required
def lista_rdos():
    """Lista todos os RDOs com filtros"""
    from forms import RDOFiltroForm
    from models import RDO, Obra
    
    form = RDOFiltroForm()
    
    # Populando choices das obras
    form.obra_id.choices = [(0, 'Todas as Obras')] + [(obra.id, obra.nome) for obra in Obra.query.all()]
    
    # Query base
    query = RDO.query.join(Obra).join(Funcionario, RDO.criado_por_id == Funcionario.id)
    
    # Aplicar filtros se fornecidos
    if request.method == 'POST' and form.validate():
        if form.data_inicio.data:
            query = query.filter(RDO.data_relatorio >= form.data_inicio.data)
        if form.data_fim.data:
            query = query.filter(RDO.data_relatorio <= form.data_fim.data)
        if form.obra_id.data and form.obra_id.data != 0:
            query = query.filter(RDO.obra_id == form.obra_id.data)
        if form.status.data:
            query = query.filter(RDO.status == form.status.data)
    
    # Ordenar por data mais recente
    rdos = query.order_by(RDO.data_relatorio.desc()).all()
    
    return render_template('rdo/lista_rdos.html', rdos=rdos, form=form)


@main_bp.route('/rdo/novo')
@main_bp.route('/rdo/novo/<int:obra_id>')
@login_required
def novo_rdo(obra_id=None):
    """Criar novo RDO"""
    from forms import RDOForm
    from models import Obra, Funcionario
    import json
    
    form = RDOForm()
    
    # Populando choices das obras
    form.obra_id.choices = [(obra.id, obra.nome) for obra in Obra.query.all()]
    
    # Se obra_id foi fornecida, pré-selecionar
    if obra_id:
        form.obra_id.data = obra_id
    
    # Preparar dados para JavaScript
    funcionarios = [
        {'id': f.id, 'nome': f.nome, 'funcao': f.funcao_ref.nome if f.funcao_ref else 'Sem função'}
        for f in Funcionario.query.filter_by(ativo=True).all()
    ]
    
    obras = [
        {'id': o.id, 'nome': o.nome}
        for o in Obra.query.all()
    ]
    
    funcionarios_json = json.dumps(funcionarios)
    obras_json = json.dumps(obras)
    
    return render_template('rdo/formulario_rdo.html', 
                         form=form, 
                         modo='criar',
                         funcionarios_json=funcionarios_json,
                         obras_json=obras_json)


@main_bp.route('/rdo/criar', methods=['POST'])
@login_required
def criar_rdo():
    """Processar criação de RDO"""
    from forms import RDOForm
    from models import RDO, Obra
    import uuid
    from datetime import datetime
    
    form = RDOForm()
    form.obra_id.choices = [(obra.id, obra.nome) for obra in Obra.query.all()]
    
    if form.validate_on_submit():
        # Gerar número único do RDO
        numero_rdo = f"RDO-{datetime.now().year}-{str(uuid.uuid4())[:8].upper()}"
        
        rdo = RDO(
            numero_rdo=numero_rdo,
            data_relatorio=form.data_relatorio.data,
            obra_id=form.obra_id.data,
            criado_por_id=current_user.id,  # Assumindo que current_user é um funcionário
            tempo_manha=form.tempo_manha.data,
            tempo_tarde=form.tempo_tarde.data,
            tempo_noite=form.tempo_noite.data,
            observacoes_meteorologicas=form.observacoes_meteorologicas.data,
            comentario_geral=form.comentario_geral.data,
            status=form.status.data
        )
        
        db.session.add(rdo)
        db.session.commit()
        
        flash('RDO criado com sucesso!', 'success')
        return redirect(url_for('main.visualizar_rdo', id=rdo.id))
    
    return render_template('rdo/formulario_rdo.html', form=form, modo='criar')


@main_bp.route('/rdo/<int:id>')
@login_required
def visualizar_rdo(id):
    """Visualizar detalhes de um RDO"""
    from models import RDO
    
    rdo = RDO.query.get_or_404(id)
    return render_template('rdo/visualizar_rdo.html', rdo=rdo)


@main_bp.route('/rdo/<int:id>/editar')
@login_required
def editar_rdo(id):
    """Editar RDO existente"""
    from forms import RDOForm
    from models import RDO, Obra
    
    rdo = RDO.query.get_or_404(id)
    form = RDOForm(obj=rdo)
    
    # Populando choices das obras
    form.obra_id.choices = [(obra.id, obra.nome) for obra in Obra.query.all()]
    
    return render_template('rdo/formulario_rdo.html', form=form, rdo=rdo, modo='editar')


@main_bp.route('/rdo/<int:id>/atualizar', methods=['POST'])
@login_required
def atualizar_rdo(id):
    """Processar atualização de RDO"""
    from forms import RDOForm
    from models import RDO, Obra
    
    rdo = RDO.query.get_or_404(id)
    form = RDOForm()
    form.obra_id.choices = [(obra.id, obra.nome) for obra in Obra.query.all()]
    
    if form.validate_on_submit():
        rdo.data_relatorio = form.data_relatorio.data
        rdo.obra_id = form.obra_id.data
        rdo.tempo_manha = form.tempo_manha.data
        rdo.tempo_tarde = form.tempo_tarde.data
        rdo.tempo_noite = form.tempo_noite.data
        rdo.observacoes_meteorologicas = form.observacoes_meteorologicas.data
        rdo.comentario_geral = form.comentario_geral.data
        rdo.status = form.status.data
        
        db.session.commit()
        
        flash('RDO atualizado com sucesso!', 'success')
        return redirect(url_for('main.visualizar_rdo', id=rdo.id))
    
    return render_template('rdo/formulario_rdo.html', form=form, rdo=rdo, modo='editar')


@main_bp.route('/rdo/<int:id>/excluir', methods=['POST'])
@login_required
def excluir_rdo(id):
    """Excluir RDO"""
    from models import RDO
    
    rdo = RDO.query.get_or_404(id)
    
    db.session.delete(rdo)
    db.session.commit()
    
    flash('RDO excluído com sucesso!', 'success')
    return redirect(url_for('main.lista_rdos'))


# Rotas para seções dinâmicas do RDO
@main_bp.route('/rdo/<int:rdo_id>/mao-obra')
@login_required
def gerenciar_mao_obra(rdo_id):
    """Gerenciar mão de obra do RDO"""
    from models import RDO, RDOMaoObra, Funcionario
    
    rdo = RDO.query.get_or_404(rdo_id)
    funcionarios = Funcionario.query.filter_by(ativo=True).all()
    
    return render_template('rdo/secoes/mao_obra.html', 
                         rdo=rdo, 
                         funcionarios=funcionarios)


@main_bp.route('/obras/<int:id>/rdos')
@login_required
def rdos_por_obra(id):
    """Lista RDOs de uma obra específica"""
    from models import Obra, RDO
    
    obra = Obra.query.get_or_404(id)
    rdos = RDO.query.filter_by(obra_id=id).order_by(RDO.data_relatorio.desc()).all()
    
    return render_template('rdo/rdos_obra.html', obra=obra, rdos=rdos)


# ========== NOVAS FUNCIONALIDADES: ALIMENTAÇÃO APRIMORADA ==========

@main_bp.route('/alimentacao/restaurantes')
@main_bp.route('/alimentacao/restaurantes', methods=['POST'])
@login_required
def alimentacao_restaurantes():
    """Página principal de alimentação com cards de restaurantes e KPIs"""
    from forms import FiltroDataForm, AlimentacaoMultiplaForm, RestauranteForm
    from models import Restaurante, RegistroAlimentacao, Funcionario, Obra
    from datetime import date, datetime, timedelta
    from sqlalchemy import func
    import json
    
    # Formulários
    filtro_form = FiltroDataForm()
    alimentacao_form = AlimentacaoMultiplaForm()
    restaurante_form = RestauranteForm()
    
    # Definir período padrão (mês atual)
    data_inicio = date.today().replace(day=1)
    data_fim = date.today()
    
    # Aplicar filtros se fornecidos
    if request.method == 'POST' and filtro_form.validate_on_submit():
        if filtro_form.data_inicio.data:
            data_inicio = filtro_form.data_inicio.data
        if filtro_form.data_fim.data:
            data_fim = filtro_form.data_fim.data
    
    # Popular formulários
    alimentacao_form.obra_id.choices = [(0, 'Selecione...')] + [(obra.id, obra.nome) for obra in Obra.query.all()]
    alimentacao_form.restaurante_id.choices = [(0, 'Selecione...')] + [(r.id, r.nome) for r in Restaurante.query.filter_by(ativo=True).all()]
    
    # Calcular KPIs gerais
    query_kpis = RegistroAlimentacao.query.filter(
        RegistroAlimentacao.data >= data_inicio,
        RegistroAlimentacao.data <= data_fim
    )
    
    custo_total = db.session.query(func.sum(RegistroAlimentacao.valor)).filter(
        RegistroAlimentacao.data >= data_inicio,
        RegistroAlimentacao.data <= data_fim
    ).scalar() or 0
    
    registros_hoje = RegistroAlimentacao.query.filter_by(data=date.today()).count()
    
    funcionarios_alimentados = db.session.query(func.count(func.distinct(RegistroAlimentacao.funcionario_id))).filter(
        RegistroAlimentacao.data >= data_inicio,
        RegistroAlimentacao.data <= data_fim
    ).scalar() or 0
    
    dias_periodo = (data_fim - data_inicio).days + 1
    media_diaria = custo_total / dias_periodo if dias_periodo > 0 else 0
    
    kpis = {
        'custo_total': custo_total,
        'media_diaria': media_diaria,
        'registros_hoje': registros_hoje,
        'funcionarios_alimentados': funcionarios_alimentados
    }
    
    # Buscar restaurantes com KPIs
    restaurantes = []
    for restaurante in Restaurante.query.all():
        custo_restaurante = db.session.query(func.sum(RegistroAlimentacao.valor)).filter(
            RegistroAlimentacao.restaurante_id == restaurante.id,
            RegistroAlimentacao.data >= data_inicio,
            RegistroAlimentacao.data <= data_fim
        ).scalar() or 0
        
        total_registros = RegistroAlimentacao.query.filter(
            RegistroAlimentacao.restaurante_id == restaurante.id,
            RegistroAlimentacao.data >= data_inicio,
            RegistroAlimentacao.data <= data_fim
        ).count()
        
        restaurante.kpis = {
            'custo_total': custo_restaurante,
            'total_registros': total_registros
        }
        restaurantes.append(restaurante)
    
    # Dados para JavaScript
    funcionarios = [
        {'id': f.id, 'nome': f.nome, 'funcao': f.funcao_ref.nome if f.funcao_ref else 'Sem função'}
        for f in Funcionario.query.filter_by(ativo=True).all()
    ]
    funcionarios_json = json.dumps(funcionarios)
    
    return render_template('alimentacao/restaurantes.html',
                         restaurantes=restaurantes,
                         kpis=kpis,
                         filtro_form=filtro_form,
                         alimentacao_form=alimentacao_form,
                         restaurante_form=restaurante_form,
                         funcionarios_json=funcionarios_json)


@main_bp.route('/alimentacao/restaurante/criar', methods=['POST'])
@login_required
def criar_restaurante():
    """Criar novo restaurante"""
    from forms import RestauranteForm
    from models import Restaurante
    
    form = RestauranteForm()
    
    if form.validate_on_submit():
        restaurante = Restaurante(
            nome=form.nome.data,
            endereco=form.endereco.data,
            telefone=form.telefone.data,
            email=form.email.data,
            contato_responsavel=form.contato_responsavel.data,
            ativo=form.ativo.data
        )
        
        db.session.add(restaurante)
        db.session.commit()
        
        flash('Restaurante cadastrado com sucesso!', 'success')
    else:
        flash('Erro ao cadastrar restaurante. Verifique os dados.', 'error')
    
    return redirect(url_for('main.alimentacao_restaurantes'))


@main_bp.route('/alimentacao/multipla/criar', methods=['POST'])
@login_required
def criar_alimentacao_multipla():
    """Criar lançamento de alimentação para múltiplos funcionários"""
    from forms import AlimentacaoMultiplaForm
    from models import RegistroAlimentacao
    import json
    
    form = AlimentacaoMultiplaForm()
    
    # Popular choices para validação
    from models import Obra, Restaurante
    form.obra_id.choices = [(0, 'Selecione...')] + [(obra.id, obra.nome) for obra in Obra.query.all()]
    form.restaurante_id.choices = [(0, 'Selecione...')] + [(r.id, r.nome) for r in Restaurante.query.filter_by(ativo=True).all()]
    
    if form.validate_on_submit():
        try:
            funcionarios_ids = json.loads(form.funcionarios_selecionados.data)
            
            if not funcionarios_ids:
                flash('Selecione pelo menos um funcionário.', 'error')
                return redirect(url_for('main.alimentacao_restaurantes'))
            
            # Criar registro para cada funcionário selecionado
            registros_criados = 0
            for funcionario_id in funcionarios_ids:
                registro = RegistroAlimentacao(
                    funcionario_id=funcionario_id,
                    obra_id=form.obra_id.data if form.obra_id.data != 0 else None,
                    restaurante_id=form.restaurante_id.data if form.restaurante_id.data != 0 else None,
                    data=form.data.data,
                    tipo=form.tipo.data,
                    valor=form.valor.data,
                    observacoes=form.observacoes.data
                )
                db.session.add(registro)
                registros_criados += 1
            
            db.session.commit()
            
            flash(f'Lançamento criado com sucesso para {registros_criados} funcionário(s)!', 'success')
            
        except Exception as e:
            db.session.rollback()
            flash('Erro ao criar lançamento. Tente novamente.', 'error')
    else:
        flash('Erro na validação dos dados. Verifique as informações.', 'error')
    
    return redirect(url_for('main.alimentacao_restaurantes'))


@main_bp.route('/alimentacao/restaurante/<int:restaurante_id>')
@login_required
def detalhes_restaurante(restaurante_id):
    """Página de detalhes de um restaurante específico"""
    from models import Restaurante, RegistroAlimentacao, Funcionario
    from datetime import date, timedelta
    from sqlalchemy import func
    
    restaurante = Restaurante.query.get_or_404(restaurante_id)
    
    # Período padrão (mês atual)
    data_inicio = date.today().replace(day=1)
    data_fim = date.today()
    
    # KPIs do restaurante
    custo_total = db.session.query(func.sum(RegistroAlimentacao.valor)).filter(
        RegistroAlimentacao.restaurante_id == restaurante.id,
        RegistroAlimentacao.data >= data_inicio,
        RegistroAlimentacao.data <= data_fim
    ).scalar() or 0
    
    total_registros = RegistroAlimentacao.query.filter(
        RegistroAlimentacao.restaurante_id == restaurante.id,
        RegistroAlimentacao.data >= data_inicio,
        RegistroAlimentacao.data <= data_fim
    ).count()
    
    funcionarios_unicos = db.session.query(func.count(func.distinct(RegistroAlimentacao.funcionario_id))).filter(
        RegistroAlimentacao.restaurante_id == restaurante.id,
        RegistroAlimentacao.data >= data_inicio,
        RegistroAlimentacao.data <= data_fim
    ).scalar() or 0
    
    media_por_funcionario = custo_total / funcionarios_unicos if funcionarios_unicos > 0 else 0
    
    kpis = {
        'custo_total': custo_total,
        'total_registros': total_registros,
        'funcionarios_unicos': funcionarios_unicos,
        'media_por_funcionario': media_por_funcionario
    }
    
    # Histórico de lançamentos
    registros = RegistroAlimentacao.query.filter(
        RegistroAlimentacao.restaurante_id == restaurante.id
    ).join(Funcionario).order_by(RegistroAlimentacao.data.desc()).limit(50).all()
    
    return render_template('alimentacao/detalhes_restaurante.html',
                         restaurante=restaurante,
                         kpis=kpis,
                         registros=registros)
