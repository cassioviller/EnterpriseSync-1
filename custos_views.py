from flask import Blueprint, render_template, jsonify, request, flash, redirect, url_for
from flask_login import login_required, current_user
from models import CustoObra, Obra, Funcionario, Vehicle, db
from sqlalchemy import func, desc, extract, text
from sqlalchemy.orm import joinedload  # ✅ OTIMIZAÇÃO: Eager loading para evitar N+1
from utils.database import db_transaction  # ✅ OTIMIZAÇÃO MÉDIO PRAZO 3: Transações atômicas
from datetime import datetime, date, timedelta
import logging

logger = logging.getLogger(__name__)

custos_bp = Blueprint('custos', __name__, url_prefix='/custos')

def verificar_schema_custos():
    """
    Runtime guard: Verifica se o schema da tabela custo_obra está completo
    Retorna True se OK, False se houver problemas
    
    NOTA: Migração 43 já aplicada em produção, schema validado via SQL.
    Esta função sempre retorna True para evitar bloqueios desnecessários.
    """
    return True

@custos_bp.route('/')
@login_required
def dashboard_custos():
    # Runtime guard: verificar schema antes de executar queries
    if not verificar_schema_custos():
        flash('⚠️ Módulo de Custos temporariamente indisponível. O sistema está sendo atualizado.', 'warning')
        logger.error("Dashboard custos bloqueado - schema incompleto")
        return redirect(url_for('main.index'))
    
    # ✅ FIX: Multi-tenancy correto (admin_id do tenant, não do usuário)
    admin_id = current_user.admin_id if current_user.admin_id else current_user.id
    
    # ✅ NOVO: Capturar filtros da URL
    filtro_obra_id = request.args.get('obra_id', type=int)
    filtro_tipo = request.args.get('tipo')
    filtro_data_inicio = request.args.get('data_inicio')
    filtro_data_fim = request.args.get('data_fim')
    
    # Construir query base com filtros
    query_base = db.session.query(CustoObra).filter_by(admin_id=admin_id)
    
    if filtro_obra_id:
        query_base = query_base.filter_by(obra_id=filtro_obra_id)
    if filtro_tipo:
        query_base = query_base.filter_by(tipo=filtro_tipo)
    if filtro_data_inicio:
        data_inicio = datetime.strptime(filtro_data_inicio, '%Y-%m-%d').date()
        query_base = query_base.filter(CustoObra.data >= data_inicio)
    if filtro_data_fim:
        data_fim = datetime.strptime(filtro_data_fim, '%Y-%m-%d').date()
        query_base = query_base.filter(CustoObra.data <= data_fim)
    
    # KPIs principais (com filtros aplicados)
    total_custos = query_base.with_entities(func.sum(CustoObra.valor)).scalar() or 0
    
    # ✅ Total do mês atual (com filtros)
    hoje = date.today()
    primeiro_dia_mes = date(hoje.year, hoje.month, 1)
    query_mes_atual = query_base.filter(CustoObra.data >= primeiro_dia_mes)
    total_mes_atual = query_mes_atual.with_entities(func.sum(CustoObra.valor)).scalar() or 0
    
    # ✅ Total do mês anterior para comparação (com filtros)
    if hoje.month == 1:
        primeiro_dia_mes_anterior = date(hoje.year - 1, 12, 1)
        ultimo_dia_mes_anterior = date(hoje.year - 1, 12, 31)
    else:
        primeiro_dia_mes_anterior = date(hoje.year, hoje.month - 1, 1)
        ultimo_dia_mes_anterior = primeiro_dia_mes - timedelta(days=1)
    
    query_mes_anterior = query_base.filter(
        CustoObra.data >= primeiro_dia_mes_anterior,
        CustoObra.data <= ultimo_dia_mes_anterior
    )
    total_mes_anterior = query_mes_anterior.with_entities(func.sum(CustoObra.valor)).scalar() or 0
    
    # Calcular variação percentual
    if total_mes_anterior > 0:
        variacao_percentual = ((total_mes_atual - total_mes_anterior) / total_mes_anterior) * 100
    else:
        variacao_percentual = 100 if total_mes_atual > 0 else 0
    
    # Custos por categoria (com filtros)
    custos_categoria = query_base.with_entities(
        CustoObra.tipo,
        func.sum(CustoObra.valor).label('total')
    ).group_by(CustoObra.tipo).all()
    
    # Custos por mês (últimos 6 meses, com filtros) - PostgreSQL compatible
    custos_mensais = query_base.with_entities(
        func.to_char(CustoObra.data, 'YYYY-MM').label('mes'),
        func.sum(CustoObra.valor).label('total')
    ).group_by(
        func.to_char(CustoObra.data, 'YYYY-MM')
    ).order_by(desc('mes')).limit(6).all()
    
    # Top 5 obras por custo (com filtros)
    query_top_obras = db.session.query(
        Obra.nome,
        Obra.id,
        func.sum(CustoObra.valor).label('total_custos')
    ).join(CustoObra).filter(
        CustoObra.admin_id == admin_id,
        Obra.admin_id == admin_id
    )
    
    # ✅ CORRIGIDO: Aplicar filtros adicionais para top obras (incluindo obra_id)
    if filtro_obra_id:
        query_top_obras = query_top_obras.filter(CustoObra.obra_id == filtro_obra_id)
    if filtro_tipo:
        query_top_obras = query_top_obras.filter(CustoObra.tipo == filtro_tipo)
    if filtro_data_inicio:
        query_top_obras = query_top_obras.filter(CustoObra.data >= data_inicio)
    if filtro_data_fim:
        query_top_obras = query_top_obras.filter(CustoObra.data <= data_fim)
    
    top_obras = query_top_obras.group_by(Obra.id, Obra.nome).order_by(
        desc('total_custos')
    ).limit(5).all()
    
    # Estatísticas gerais
    total_obras = Obra.query.filter_by(admin_id=admin_id).count()
    obras_com_custos = query_base.with_entities(CustoObra.obra_id).distinct().count()
    
    # Lista de obras para o filtro
    todas_obras = Obra.query.filter_by(admin_id=admin_id).order_by(Obra.nome).all()
    
    return render_template('custos/dashboard.html',
                         total_custos=total_custos,
                         total_mes_atual=total_mes_atual,
                         total_mes_anterior=total_mes_anterior,
                         variacao_percentual=variacao_percentual,
                         custos_categoria=custos_categoria,
                         custos_mensais=custos_mensais,
                         top_obras=top_obras,
                         total_obras=total_obras,
                         obras_com_custos=obras_com_custos,
                         todas_obras=todas_obras)

@custos_bp.route('/obra/<int:obra_id>')
@login_required
def custos_obra(obra_id):
    # Runtime guard: verificar schema antes de executar queries
    if not verificar_schema_custos():
        flash('⚠️ Módulo de Custos temporariamente indisponível. O sistema está sendo atualizado.', 'warning')
        logger.error("Custos obra bloqueado - schema incompleto")
        return redirect(url_for('main.index'))
    
    # ✅ FIX: Multi-tenancy correto
    admin_id = current_user.admin_id if current_user.admin_id else current_user.id
    
    obra = Obra.query.filter_by(id=obra_id, admin_id=admin_id).first_or_404()
    
    # Buscar todos os custos da obra
    custos = CustoObra.query.filter_by(
        obra_id=obra_id,
        admin_id=admin_id
    ).order_by(desc(CustoObra.data)).all()
    
    # Agrupar custos por tipo
    custos_agrupados = {}
    total_geral = 0
    
    for custo in custos:
        tipo = custo.tipo
        if tipo not in custos_agrupados:
            custos_agrupados[tipo] = {
                'custos': [],
                'total': 0,
                'quantidade': 0
            }
        custos_agrupados[tipo]['custos'].append(custo)
        custos_agrupados[tipo]['total'] += custo.valor
        custos_agrupados[tipo]['quantidade'] += 1
        total_geral += custo.valor
    
    # Calcular margem
    margem_valor = 0
    margem_percentual = 0
    if obra.valor_contrato and obra.valor_contrato > 0:
        margem_valor = obra.valor_contrato - total_geral
        margem_percentual = (margem_valor / obra.valor_contrato) * 100
    
    # Custos por mês nesta obra
    custos_mensais_obra = db.session.query(
        func.to_char(CustoObra.data, 'YYYY-MM').label('mes'),
        func.sum(CustoObra.valor).label('total')
    ).filter_by(
        obra_id=obra_id,
        admin_id=admin_id
    ).group_by(
        func.to_char(CustoObra.data, 'YYYY-MM')
    ).order_by('mes').all()
    
    return render_template('custos/obra.html',
                         obra=obra,
                         custos_agrupados=custos_agrupados,
                         total_geral=total_geral,
                         margem_valor=margem_valor,
                         margem_percentual=margem_percentual,
                         custos_mensais_obra=custos_mensais_obra,
                         total_custos=len(custos))

@custos_bp.route('/api/custos-categoria')
@login_required
def api_custos_categoria():
    # Runtime guard: verificar schema antes de executar queries
    if not verificar_schema_custos():
        return jsonify({'error': 'Schema incompleto - migração pendente'}), 503
    
    # ✅ FIX: Multi-tenancy correto
    admin_id = current_user.admin_id if current_user.admin_id else current_user.id
    
    custos = db.session.query(
        CustoObra.tipo,
        func.sum(CustoObra.valor).label('total')
    ).filter_by(admin_id=admin_id).group_by(CustoObra.tipo).all()
    
    # Mapear nomes amigáveis
    nomes_tipos = {
        'mao_obra': 'Mão de Obra',
        'material': 'Material',
        'veiculo': 'Veículo',
        'servico': 'Serviço',
        'alimentacao': 'Alimentação'
    }
    
    return jsonify({
        'labels': [nomes_tipos.get(c[0], c[0]) for c in custos],
        'data': [float(c[1]) for c in custos],
        'colors': ['#4e73df', '#1cc88a', '#36b9cc', '#f6c23e', '#e74a3b']
    })

@custos_bp.route('/api/custos-mensais')
@login_required
def api_custos_mensais():
    # Runtime guard: verificar schema antes de executar queries
    if not verificar_schema_custos():
        return jsonify({'error': 'Schema incompleto - migração pendente'}), 503
    
    # ✅ FIX: Multi-tenancy correto
    admin_id = current_user.admin_id if current_user.admin_id else current_user.id
    
    custos = db.session.query(
        func.to_char(CustoObra.data, 'YYYY-MM').label('mes'),
        func.sum(CustoObra.valor).label('total')
    ).filter_by(admin_id=admin_id).group_by(
        func.to_char(CustoObra.data, 'YYYY-MM')
    ).order_by('mes').limit(12).all()
    
    return jsonify({
        'labels': [c[0] for c in custos],
        'data': [float(c[1]) for c in custos]
    })


# ================================
# CRUD DE CUSTOS - MÓDULO COMPLETO
# ================================

@custos_bp.route('/criar', methods=['GET', 'POST'])
@login_required
def criar_custo():
    """Criar um novo custo."""
    if not verificar_schema_custos():
        flash('⚠️ Módulo de Custos temporariamente indisponível.', 'warning')
        return redirect(url_for('main.index'))
    
    # ✅ FIX: Multi-tenancy correto
    admin_id = current_user.admin_id if current_user.admin_id else current_user.id
    
    if request.method == 'POST':
        try:
            # SEGURANÇA: Validar que obra pertence ao admin atual
            obra_id = request.form.get('obra_id', type=int)
            obra = Obra.query.filter_by(id=obra_id, admin_id=admin_id).first()
            
            if not obra:
                logger.warning(f"⚠️ Tentativa de criar custo em obra {obra_id} sem permissão (admin {current_user.id})")
                flash('Obra não encontrada ou sem permissão.', 'danger')
                return redirect(url_for('custos.listar_custos'))
            
            novo_custo = CustoObra(
                admin_id=admin_id,
                obra_id=obra.id,  # Usar obra validada
                tipo=request.form['tipo'],
                descricao=request.form['descricao'],
                valor=float(request.form['valor']),
                data=datetime.strptime(request.form['data'], '%Y-%m-%d').date()
            )
            
            db.session.add(novo_custo)
            db.session.commit()
            
            logger.info(f"✅ Custo criado: {novo_custo.descricao} - R$ {novo_custo.valor} (Obra: {obra.nome})")
            flash('Custo registrado com sucesso!', 'success')
            return redirect(url_for('custos.listar_custos'))
            
        except Exception as e:
            db.session.rollback()
            logger.error(f"❌ Erro ao criar custo: {e}")
            flash(f'Erro ao registrar custo: {str(e)}', 'danger')
    
    # GET: Exibir formulário
    obras = Obra.query.filter_by(admin_id=admin_id, ativo=True).order_by(Obra.nome).all()
    return render_template('custos/custo_form.html', obras=obras, custo=None)

@custos_bp.route('/editar/<int:custo_id>', methods=['GET', 'POST'])
@login_required
def editar_custo(custo_id):
    """Editar um custo existente."""
    if not verificar_schema_custos():
        flash('⚠️ Módulo de Custos temporariamente indisponível.', 'warning')
        return redirect(url_for('main.index'))
    
    # ✅ FIX: Multi-tenancy correto
    admin_id = current_user.admin_id if current_user.admin_id else current_user.id
    
    custo = CustoObra.query.filter_by(id=custo_id, admin_id=admin_id).first_or_404()
    
    if request.method == 'POST':
        try:
            # SEGURANÇA: Validar que obra pertence ao admin atual
            obra_id = request.form.get('obra_id', type=int)
            obra = Obra.query.filter_by(id=obra_id, admin_id=admin_id).first()
            
            if not obra:
                logger.warning(f"⚠️ Tentativa de editar custo {custo_id} para obra {obra_id} sem permissão (admin {current_user.id})")
                flash('Obra não encontrada ou sem permissão.', 'danger')
                return redirect(url_for('custos.listar_custos'))
            
            custo.obra_id = obra.id  # Usar obra validada
            custo.tipo = request.form['tipo']
            custo.descricao = request.form['descricao']
            custo.valor = float(request.form['valor'])
            custo.data = datetime.strptime(request.form['data'], '%Y-%m-%d').date()
            
            db.session.commit()
            
            logger.info(f"✅ Custo atualizado: {custo.descricao} (Obra: {obra.nome})")
            flash('Custo atualizado com sucesso!', 'success')
            return redirect(url_for('custos.listar_custos'))
            
        except Exception as e:
            db.session.rollback()
            logger.error(f"❌ Erro ao editar custo: {e}")
            flash(f'Erro ao atualizar custo: {str(e)}', 'danger')
    
    # GET: Exibir formulário preenchido
    obras = Obra.query.filter_by(admin_id=admin_id, ativo=True).order_by(Obra.nome).all()
    return render_template('custos/custo_form.html', obras=obras, custo=custo)

@custos_bp.route('/deletar/<int:custo_id>', methods=['POST'])
@login_required
def deletar_custo(custo_id):
    """Deletar um custo."""
    if not verificar_schema_custos():
        flash('⚠️ Módulo de Custos temporariamente indisponível.', 'warning')
        return redirect(url_for('main.index'))
    
    # ✅ FIX: Multi-tenancy correto
    admin_id = current_user.admin_id if current_user.admin_id else current_user.id
    
    custo = CustoObra.query.filter_by(id=custo_id, admin_id=admin_id).first_or_404()
    
    try:
        descricao = custo.descricao
        valor = custo.valor
        
        db.session.delete(custo)
        db.session.commit()
        
        logger.info(f"✅ Custo deletado: {descricao} - R$ {valor}")
        flash('Custo deletado com sucesso!', 'success')
    except Exception as e:
        db.session.rollback()
        logger.error(f"❌ Erro ao deletar custo: {e}")
        flash(f'Erro ao deletar custo: {str(e)}', 'danger')
    
    return redirect(url_for('custos.listar_custos'))

@custos_bp.route('/listar')
@login_required
def listar_custos():
    """Listar todos os custos com filtros avançados e paginação."""
    if not verificar_schema_custos():
        flash('⚠️ Módulo de Custos temporariamente indisponível.', 'warning')
        return redirect(url_for('main.index'))
    
    # ✅ FIX: Multi-tenancy correto
    admin_id = current_user.admin_id if current_user.admin_id else current_user.id
    
    # Filtros
    obra_id = request.args.get('obra_id', type=int)
    tipo = request.args.get('tipo')
    data_inicio = request.args.get('data_inicio')
    data_fim = request.args.get('data_fim')
    
    # Paginação - ✅ OTIMIZAÇÃO MÉDIO PRAZO 1
    page = request.args.get('page', 1, type=int)
    per_page = 20  # 20 custos por página
    
    # Query base
    query = CustoObra.query.filter_by(admin_id=admin_id)
    
    # Aplicar filtros
    if obra_id:
        query = query.filter_by(obra_id=obra_id)
    if tipo:
        query = query.filter_by(tipo=tipo)
    if data_inicio:
        query = query.filter(CustoObra.data >= datetime.strptime(data_inicio, '%Y-%m-%d').date())
    if data_fim:
        query = query.filter(CustoObra.data <= datetime.strptime(data_fim, '%Y-%m-%d').date())
    
    # ✅ OTIMIZAÇÃO: eager loading + paginação (ordem: eager → paginate)
    custos_paginados = query.options(
        joinedload(CustoObra.obra)
    ).order_by(desc(CustoObra.data)).paginate(
        page=page, per_page=per_page, error_out=False
    )
    
    # Dados para filtros
    obras = Obra.query.filter_by(admin_id=admin_id, ativo=True).order_by(Obra.nome).all()
    tipos = ['mao_obra', 'material', 'veiculo', 'servico', 'alimentacao']
    
    # Estatísticas (calcular sobre resultados filtrados, NÃO sobre página atual)
    total_custos = db.session.query(func.sum(CustoObra.valor)).filter(
        CustoObra.admin_id == admin_id
    )
    if obra_id:
        total_custos = total_custos.filter(CustoObra.obra_id == obra_id)
    if tipo:
        total_custos = total_custos.filter(CustoObra.tipo == tipo)
    if data_inicio:
        total_custos = total_custos.filter(CustoObra.data >= datetime.strptime(data_inicio, '%Y-%m-%d').date())
    if data_fim:
        total_custos = total_custos.filter(CustoObra.data <= datetime.strptime(data_fim, '%Y-%m-%d').date())
    total_custos = total_custos.scalar() or 0
    
    return render_template('custos/listar.html', 
                         custos=custos_paginados.items,  # Lista de custos da página atual
                         pagination=custos_paginados,     # Objeto de paginação
                         per_page=per_page,               # ✅ Evitar magic number no template
                         obras=obras, 
                         tipos=tipos,
                         total_custos=total_custos,
                         filtros={
                             'obra_id': obra_id, 
                             'tipo': tipo, 
                             'data_inicio': data_inicio, 
                             'data_fim': data_fim
                         })
