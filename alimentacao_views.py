from flask import Blueprint, render_template, request, redirect, url_for, flash
from flask_login import login_required, current_user
from models import db, Restaurante, AlimentacaoLancamento, Funcionario, Obra
from datetime import datetime
from sqlalchemy import func
from decimal import Decimal
import logging

logger = logging.getLogger(__name__)

alimentacao_bp = Blueprint('alimentacao', __name__, url_prefix='/alimentacao')

# ===== HELPER FUNCTION =====
def get_admin_id():
    """Retorna admin_id do usuário atual"""
    if current_user.is_authenticated:
        return current_user.admin_id if current_user.admin_id else current_user.id
    return None

# ===== RESTAURANTES - CRUD COMPLETO =====

@alimentacao_bp.route('/restaurantes')
@login_required
def restaurantes_lista():
    """Lista todos os restaurantes"""
    admin_id = get_admin_id()
    restaurantes = Restaurante.query.filter_by(admin_id=admin_id).order_by(Restaurante.nome).all()
    return render_template('alimentacao/restaurantes_lista.html', restaurantes=restaurantes)

@alimentacao_bp.route('/restaurantes/novo', methods=['GET', 'POST'])
@login_required
def restaurante_novo():
    """Criar novo restaurante"""
    if request.method == 'POST':
        try:
            admin_id = get_admin_id()
            restaurante = Restaurante(
                nome=request.form['nome'],
                endereco=request.form.get('endereco', ''),
                telefone=request.form.get('telefone', ''),
                razao_social=request.form.get('razao_social', ''),
                cnpj=request.form.get('cnpj', ''),
                pix=request.form.get('pix', ''),
                nome_conta=request.form.get('nome_conta', ''),
                admin_id=admin_id
            )
            db.session.add(restaurante)
            db.session.commit()
            flash('Restaurante cadastrado com sucesso!', 'success')
            return redirect(url_for('alimentacao.restaurantes_lista'))
        except Exception as e:
            db.session.rollback()
            logger.error(f"Erro ao criar restaurante: {e}")
            flash('Erro ao cadastrar restaurante', 'error')
    
    return render_template('alimentacao/restaurante_novo.html')

@alimentacao_bp.route('/restaurantes/<int:restaurante_id>/editar', methods=['GET', 'POST'])
@login_required
def restaurante_editar(restaurante_id):
    """Editar restaurante"""
    admin_id = get_admin_id()
    restaurante = Restaurante.query.filter_by(id=restaurante_id, admin_id=admin_id).first_or_404()
    
    if request.method == 'POST':
        try:
            restaurante.nome = request.form['nome']
            restaurante.endereco = request.form.get('endereco', '')
            restaurante.telefone = request.form.get('telefone', '')
            restaurante.razao_social = request.form.get('razao_social', '')
            restaurante.cnpj = request.form.get('cnpj', '')
            restaurante.pix = request.form.get('pix', '')
            restaurante.nome_conta = request.form.get('nome_conta', '')
            db.session.commit()
            flash('Restaurante atualizado com sucesso!', 'success')
            return redirect(url_for('alimentacao.restaurantes_lista'))
        except Exception as e:
            db.session.rollback()
            logger.error(f"Erro ao editar restaurante: {e}")
            flash('Erro ao atualizar restaurante', 'error')
    
    return render_template('alimentacao/restaurante_editar.html', restaurante=restaurante)

@alimentacao_bp.route('/restaurante/<int:restaurante_id>')
@login_required
def restaurante_detalhes(restaurante_id):
    """Exibir detalhes do restaurante e seus lançamentos"""
    admin_id = get_admin_id()
    
    # Buscar restaurante com validação multi-tenant
    restaurante = Restaurante.query.filter_by(id=restaurante_id, admin_id=admin_id).first_or_404()
    
    # Buscar lançamentos desse restaurante (funcionários carregados via lazy='selectin')
    lancamentos = AlimentacaoLancamento.query.filter_by(
        restaurante_id=restaurante_id, 
        admin_id=admin_id
    ).order_by(AlimentacaoLancamento.data.desc()).all()
    
    # Calcular estatísticas
    total_gasto = sum(l.valor_total for l in lancamentos) if lancamentos else 0
    total_lancamentos = len(lancamentos)
    
    return render_template('alimentacao/restaurante_detalhes.html', 
                         restaurante=restaurante,
                         lancamentos=lancamentos,
                         total_gasto=total_gasto,
                         total_lancamentos=total_lancamentos)

@alimentacao_bp.route('/restaurantes/<int:restaurante_id>/deletar', methods=['POST'])
@login_required
def restaurante_deletar(restaurante_id):
    """Deletar restaurante"""
    try:
        admin_id = get_admin_id()
        restaurante = Restaurante.query.filter_by(id=restaurante_id, admin_id=admin_id).first_or_404()
        db.session.delete(restaurante)
        db.session.commit()
        flash('Restaurante excluído com sucesso!', 'success')
    except Exception as e:
        db.session.rollback()
        logger.error(f"Erro ao deletar restaurante: {e}")
        flash('Erro ao excluir restaurante', 'error')
    
    return redirect(url_for('alimentacao.restaurantes_lista'))

# ===== LANÇAMENTOS - CRUD =====

@alimentacao_bp.route('/')
@login_required
def index():
    """Página principal com cards dos restaurantes"""
    admin_id = get_admin_id()
    restaurantes = Restaurante.query.filter_by(admin_id=admin_id).order_by(Restaurante.nome).all()
    return render_template('alimentacao/index.html', restaurantes=restaurantes)

@alimentacao_bp.route('/lancamentos/novo', methods=['GET', 'POST'])
@login_required
def lancamento_novo():
    """Criar novo lançamento com rateio"""
    admin_id = get_admin_id()
    
    if request.method == 'POST':
        try:
            admin_id = get_admin_id()
            
            # VALIDAÇÃO TENANT: Verificar restaurante
            restaurante_id = int(request.form['restaurante_id'])
            restaurante = Restaurante.query.filter_by(id=restaurante_id, admin_id=admin_id).first()
            if not restaurante:
                logger.warning(f"Tentativa de acesso cross-tenant: admin_id={admin_id} tentou acessar restaurante_id={restaurante_id}")
                flash('Restaurante inválido ou sem permissão', 'error')
                return redirect(url_for('alimentacao.lancamento_novo'))
            
            # VALIDAÇÃO TENANT: Verificar obra
            obra_id = int(request.form['obra_id'])
            obra = Obra.query.filter_by(id=obra_id, admin_id=admin_id).first()
            if not obra:
                logger.warning(f"Tentativa de acesso cross-tenant: admin_id={admin_id} tentou acessar obra_id={obra_id}")
                flash('Obra inválida ou sem permissão', 'error')
                return redirect(url_for('alimentacao.lancamento_novo'))
            
            # VALIDAÇÃO TENANT: Verificar funcionários
            funcionarios_ids = request.form.getlist('funcionarios')
            if not funcionarios_ids:
                flash('Selecione pelo menos um funcionário', 'error')
                return redirect(url_for('alimentacao.lancamento_novo'))
            
            # Validar cada funcionário contra admin_id
            funcionarios_validos = []
            for func_id in funcionarios_ids:
                funcionario = Funcionario.query.filter_by(id=int(func_id), admin_id=admin_id).first()
                if funcionario:
                    funcionarios_validos.append(funcionario)
                else:
                    logger.warning(f"Tentativa de acesso cross-tenant: admin_id={admin_id} tentou acessar funcionario_id={func_id}")
            
            if not funcionarios_validos:
                flash('Nenhum funcionário válido selecionado', 'error')
                return redirect(url_for('alimentacao.lancamento_novo'))
            
            # Criar lançamento (agora seguro)
            lancamento = AlimentacaoLancamento(
                data=datetime.strptime(request.form['data'], '%Y-%m-%d').date(),
                valor_total=Decimal(request.form['valor_total']),
                descricao=request.form.get('descricao', ''),
                restaurante_id=restaurante.id,  # Usar objeto validado
                obra_id=obra.id,  # Usar objeto validado
                admin_id=admin_id
            )
            db.session.add(lancamento)
            db.session.flush()
            
            # Associar apenas funcionários validados
            for funcionario in funcionarios_validos:
                lancamento.funcionarios.append(funcionario)
            
            db.session.commit()
            
            # ✅ NOVO: Emitir evento para integração com Financeiro (Tarefa 9)
            try:
                from event_manager import EventManager
                EventManager.emit('alimentacao_lancamento_criado', {
                    'lancamento_id': lancamento.id,
                    'restaurante_id': lancamento.restaurante_id,
                    'obra_id': lancamento.obra_id,
                    'valor_total': float(lancamento.valor_total)
                }, admin_id)
                logger.info(f"✅ Evento 'alimentacao_lancamento_criado' emitido para lançamento {lancamento.id}")
            except Exception as e:
                logger.error(f"❌ Erro ao emitir evento alimentacao_lancamento_criado: {e}")
            
            flash(f'Lançamento criado! Valor por funcionário: R$ {lancamento.valor_por_funcionario:.2f}', 'success')
            return redirect(url_for('alimentacao.index'))
            
        except Exception as e:
            db.session.rollback()
            logger.error(f"Erro ao criar lançamento: {e}")
            flash('Erro ao criar lançamento', 'error')
    
    # GET - carregar dados para o formulário
    restaurantes = Restaurante.query.filter_by(admin_id=admin_id).order_by(Restaurante.nome).all()
    obras = Obra.query.filter_by(admin_id=admin_id).order_by(Obra.nome).all()
    funcionarios = Funcionario.query.filter_by(admin_id=admin_id).order_by(Funcionario.nome).all()
    
    return render_template('alimentacao/lancamento_novo.html', 
                         restaurantes=restaurantes, 
                         obras=obras, 
                         funcionarios=funcionarios)


# ===== DASHBOARD DE ALIMENTAÇÃO (TAREFA 8) =====
@alimentacao_bp.route('/dashboard')
@login_required
def dashboard():
    """Dashboard de Alimentação com KPIs e gráficos"""
    try:
        from datetime import date
        from dateutil.relativedelta import relativedelta
        
        logger.info("📊 [ALIMENTACAO_DASHBOARD] Iniciando dashboard...")
        admin_id = get_admin_id()
        
        if not admin_id:
            flash('Acesso negado. Faça login novamente.', 'error')
            return redirect(url_for('auth.login'))
        
        # Capturar filtros da URL
        filtro_data_inicio = request.args.get('data_inicio')
        filtro_data_fim = request.args.get('data_fim')
        filtro_restaurante_id = request.args.get('restaurante_id', type=int)
        filtro_obra_id = request.args.get('obra_id', type=int)
        
        # Converter datas se fornecidas
        data_inicio = datetime.strptime(filtro_data_inicio, '%Y-%m-%d').date() if filtro_data_inicio else None
        data_fim = datetime.strptime(filtro_data_fim, '%Y-%m-%d').date() if filtro_data_fim else None
        
        # Query base para lançamentos
        query_base = AlimentacaoLancamento.query.filter_by(admin_id=admin_id)
        
        # Aplicar filtros
        if data_inicio:
            query_base = query_base.filter(AlimentacaoLancamento.data >= data_inicio)
        if data_fim:
            query_base = query_base.filter(AlimentacaoLancamento.data <= data_fim)
        if filtro_restaurante_id:
            query_base = query_base.filter(AlimentacaoLancamento.restaurante_id == filtro_restaurante_id)
        if filtro_obra_id:
            query_base = query_base.filter(AlimentacaoLancamento.obra_id == filtro_obra_id)
        
        # KPI 1: Total de Refeições (contagem de lançamentos)
        total_refeicoes = query_base.count()
        
        # KPI 2: Custo Total
        custo_total = db.session.query(
            func.coalesce(func.sum(AlimentacaoLancamento.valor_total), Decimal('0'))
        ).filter(AlimentacaoLancamento.admin_id == admin_id)
        
        if data_inicio:
            custo_total = custo_total.filter(AlimentacaoLancamento.data >= data_inicio)
        if data_fim:
            custo_total = custo_total.filter(AlimentacaoLancamento.data <= data_fim)
        if filtro_restaurante_id:
            custo_total = custo_total.filter(AlimentacaoLancamento.restaurante_id == filtro_restaurante_id)
        if filtro_obra_id:
            custo_total = custo_total.filter(AlimentacaoLancamento.obra_id == filtro_obra_id)
        
        custo_total = float(custo_total.scalar() or 0)
        
        # KPI 3: Custo Médio por Refeição
        custo_medio_refeicao = round(custo_total / total_refeicoes, 2) if total_refeicoes > 0 else 0
        
        # KPI 4: Custos do Mês Atual (com comparação)
        hoje = date.today()
        inicio_mes_atual = date(hoje.year, hoje.month, 1)
        inicio_mes_anterior = (inicio_mes_atual - relativedelta(months=1))
        fim_mes_anterior = inicio_mes_atual - relativedelta(days=1)
        
        # Custos do mês atual
        custos_mes_atual = db.session.query(
            func.coalesce(func.sum(AlimentacaoLancamento.valor_total), Decimal('0'))
        ).filter(
            AlimentacaoLancamento.admin_id == admin_id,
            AlimentacaoLancamento.data >= inicio_mes_atual
        )
        if filtro_restaurante_id:
            custos_mes_atual = custos_mes_atual.filter(AlimentacaoLancamento.restaurante_id == filtro_restaurante_id)
        if filtro_obra_id:
            custos_mes_atual = custos_mes_atual.filter(AlimentacaoLancamento.obra_id == filtro_obra_id)
        
        custos_mes_atual = float(custos_mes_atual.scalar() or 0)
        
        # Custos do mês anterior
        custos_mes_anterior = db.session.query(
            func.coalesce(func.sum(AlimentacaoLancamento.valor_total), Decimal('0'))
        ).filter(
            AlimentacaoLancamento.admin_id == admin_id,
            AlimentacaoLancamento.data >= inicio_mes_anterior,
            AlimentacaoLancamento.data <= fim_mes_anterior
        )
        if filtro_restaurante_id:
            custos_mes_anterior = custos_mes_anterior.filter(AlimentacaoLancamento.restaurante_id == filtro_restaurante_id)
        if filtro_obra_id:
            custos_mes_anterior = custos_mes_anterior.filter(AlimentacaoLancamento.obra_id == filtro_obra_id)
        
        custos_mes_anterior = float(custos_mes_anterior.scalar() or 0)
        
        # Calcular variação percentual
        if custos_mes_anterior > 0:
            variacao_percentual = round(((custos_mes_atual - custos_mes_anterior) / custos_mes_anterior) * 100, 1)
        else:
            variacao_percentual = 100.0 if custos_mes_atual > 0 else 0.0
        
        # Gráfico 1: Top 5 Funcionários (mais refeições)
        # Usar a tabela de associação para contar
        from models import alimentacao_funcionarios_assoc
        
        top_funcionarios = db.session.query(
            Funcionario.nome,
            Funcionario.id,
            func.count(alimentacao_funcionarios_assoc.c.lancamento_id).label('total_refeicoes')
        ).join(
            alimentacao_funcionarios_assoc,
            Funcionario.id == alimentacao_funcionarios_assoc.c.funcionario_id
        ).join(
            AlimentacaoLancamento,
            AlimentacaoLancamento.id == alimentacao_funcionarios_assoc.c.lancamento_id
        ).filter(
            AlimentacaoLancamento.admin_id == admin_id,
            Funcionario.admin_id == admin_id
        )
        
        if data_inicio:
            top_funcionarios = top_funcionarios.filter(AlimentacaoLancamento.data >= data_inicio)
        if data_fim:
            top_funcionarios = top_funcionarios.filter(AlimentacaoLancamento.data <= data_fim)
        if filtro_restaurante_id:
            top_funcionarios = top_funcionarios.filter(AlimentacaoLancamento.restaurante_id == filtro_restaurante_id)
        if filtro_obra_id:
            top_funcionarios = top_funcionarios.filter(AlimentacaoLancamento.obra_id == filtro_obra_id)
        
        top_funcionarios = top_funcionarios.group_by(
            Funcionario.id, Funcionario.nome
        ).order_by(func.count(alimentacao_funcionarios_assoc.c.lancamento_id).desc()).limit(5).all()
        
        # Gráfico 2: Top 5 Obras (mais gastos)
        top_obras = db.session.query(
            Obra.nome,
            Obra.id,
            func.sum(AlimentacaoLancamento.valor_total).label('total_gastos')
        ).join(AlimentacaoLancamento).filter(
            AlimentacaoLancamento.admin_id == admin_id,
            Obra.admin_id == admin_id
        )
        
        if data_inicio:
            top_obras = top_obras.filter(AlimentacaoLancamento.data >= data_inicio)
        if data_fim:
            top_obras = top_obras.filter(AlimentacaoLancamento.data <= data_fim)
        if filtro_restaurante_id:
            top_obras = top_obras.filter(AlimentacaoLancamento.restaurante_id == filtro_restaurante_id)
        if filtro_obra_id:
            top_obras = top_obras.filter(AlimentacaoLancamento.obra_id == filtro_obra_id)
        
        top_obras = top_obras.group_by(Obra.id, Obra.nome).order_by(
            func.sum(AlimentacaoLancamento.valor_total).desc()
        ).limit(5).all()
        
        # Gráfico 3: Evolução Mensal
        evolucao_mensal = db.session.query(
            func.to_char(AlimentacaoLancamento.data, 'YYYY-MM').label('mes'),
            func.sum(AlimentacaoLancamento.valor_total).label('total')
        ).filter(
            AlimentacaoLancamento.admin_id == admin_id
        )
        
        if data_inicio:
            evolucao_mensal = evolucao_mensal.filter(AlimentacaoLancamento.data >= data_inicio)
        if data_fim:
            evolucao_mensal = evolucao_mensal.filter(AlimentacaoLancamento.data <= data_fim)
        if filtro_restaurante_id:
            evolucao_mensal = evolucao_mensal.filter(AlimentacaoLancamento.restaurante_id == filtro_restaurante_id)
        if filtro_obra_id:
            evolucao_mensal = evolucao_mensal.filter(AlimentacaoLancamento.obra_id == filtro_obra_id)
        
        evolucao_mensal = evolucao_mensal.group_by(
            func.to_char(AlimentacaoLancamento.data, 'YYYY-MM')
        ).order_by(func.to_char(AlimentacaoLancamento.data, 'YYYY-MM').desc()).limit(6).all()
        
        # Buscar restaurantes e obras para os filtros
        restaurantes_disponiveis = Restaurante.query.filter_by(admin_id=admin_id).order_by(Restaurante.nome).all()
        obras_disponiveis = Obra.query.filter_by(admin_id=admin_id).order_by(Obra.nome).all()
        
        logger.info(f"✅ [ALIMENTACAO_DASHBOARD] KPIs calculados: Refeições={total_refeicoes}, Custo Total={custo_total}")
        
        return render_template('alimentacao/dashboard.html',
                             total_refeicoes=total_refeicoes,
                             custo_total=custo_total,
                             custo_medio_refeicao=custo_medio_refeicao,
                             custos_mes_atual=custos_mes_atual,
                             variacao_percentual=variacao_percentual,
                             top_funcionarios=top_funcionarios,
                             top_obras=top_obras,
                             evolucao_mensal=evolucao_mensal,
                             restaurantes_disponiveis=restaurantes_disponiveis,
                             obras_disponiveis=obras_disponiveis,
                             filtros={
                                 'restaurante_id': filtro_restaurante_id,
                                 'obra_id': filtro_obra_id,
                                 'data_inicio': filtro_data_inicio,
                                 'data_fim': filtro_data_fim
                             })
        
    except Exception as e:
        logger.error(f"❌ [ALIMENTACAO_DASHBOARD] Erro: {str(e)}")
        import traceback
        traceback.print_exc()
        flash('Erro ao carregar dashboard de alimentação. Tente novamente.', 'error')
        return redirect(url_for('alimentacao.index'))
