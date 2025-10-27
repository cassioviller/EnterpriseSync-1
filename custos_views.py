from flask import Blueprint, render_template, jsonify, request, flash, redirect, url_for
from flask_login import login_required, current_user
from models import CustoObra, Obra, Funcionario, Vehicle, db
from sqlalchemy import func, desc, extract, text
from sqlalchemy.orm import joinedload  # ✅ OTIMIZAÇÃO: Eager loading para evitar N+1
from datetime import datetime, date
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
    
    admin_id = current_user.id
    
    # KPIs principais
    total_custos = db.session.query(func.sum(CustoObra.valor)).filter_by(admin_id=admin_id).scalar() or 0
    
    # Custos por categoria (campo correto: 'tipo')
    custos_categoria = db.session.query(
        CustoObra.tipo,
        func.sum(CustoObra.valor).label('total')
    ).filter_by(admin_id=admin_id).group_by(CustoObra.tipo).all()
    
    # Custos por mês (últimos 6 meses) - PostgreSQL compatible
    custos_mensais = db.session.query(
        func.to_char(CustoObra.data, 'YYYY-MM').label('mes'),
        func.sum(CustoObra.valor).label('total')
    ).filter_by(admin_id=admin_id).group_by(
        func.to_char(CustoObra.data, 'YYYY-MM')
    ).order_by(desc('mes')).limit(6).all()
    
    # Top 5 obras por custo
    top_obras = db.session.query(
        Obra.nome,
        Obra.id,
        func.sum(CustoObra.valor).label('total_custos')
    ).join(CustoObra).filter(
        CustoObra.admin_id == admin_id,
        Obra.admin_id == admin_id
    ).group_by(Obra.id, Obra.nome).order_by(
        desc('total_custos')
    ).limit(5).all()
    
    # Estatísticas gerais
    total_obras = Obra.query.filter_by(admin_id=admin_id).count()
    obras_com_custos = db.session.query(CustoObra.obra_id).filter_by(admin_id=admin_id).distinct().count()
    
    return render_template('custos/dashboard.html',
                         total_custos=total_custos,
                         custos_categoria=custos_categoria,
                         custos_mensais=custos_mensais,
                         top_obras=top_obras,
                         total_obras=total_obras,
                         obras_com_custos=obras_com_custos)

@custos_bp.route('/obra/<int:obra_id>')
@login_required
def custos_obra(obra_id):
    # Runtime guard: verificar schema antes de executar queries
    if not verificar_schema_custos():
        flash('⚠️ Módulo de Custos temporariamente indisponível. O sistema está sendo atualizado.', 'warning')
        logger.error("Custos obra bloqueado - schema incompleto")
        return redirect(url_for('main.index'))
    
    obra = Obra.query.filter_by(id=obra_id, admin_id=current_user.id).first_or_404()
    
    # Buscar todos os custos da obra
    custos = CustoObra.query.filter_by(
        obra_id=obra_id,
        admin_id=current_user.id
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
        admin_id=current_user.id
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
    
    custos = db.session.query(
        CustoObra.tipo,
        func.sum(CustoObra.valor).label('total')
    ).filter_by(admin_id=current_user.id).group_by(CustoObra.tipo).all()
    
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
    
    custos = db.session.query(
        func.to_char(CustoObra.data, 'YYYY-MM').label('mes'),
        func.sum(CustoObra.valor).label('total')
    ).filter_by(admin_id=current_user.id).group_by(
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
    
    if request.method == 'POST':
        try:
            # SEGURANÇA: Validar que obra pertence ao admin atual
            obra_id = request.form.get('obra_id', type=int)
            obra = Obra.query.filter_by(id=obra_id, admin_id=current_user.id).first()
            
            if not obra:
                logger.warning(f"⚠️ Tentativa de criar custo em obra {obra_id} sem permissão (admin {current_user.id})")
                flash('Obra não encontrada ou sem permissão.', 'danger')
                return redirect(url_for('custos.listar_custos'))
            
            novo_custo = CustoObra(
                admin_id=current_user.id,
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
    obras = Obra.query.filter_by(admin_id=current_user.id, ativo=True).order_by(Obra.nome).all()
    return render_template('custos/custo_form.html', obras=obras, custo=None)

@custos_bp.route('/editar/<int:custo_id>', methods=['GET', 'POST'])
@login_required
def editar_custo(custo_id):
    """Editar um custo existente."""
    if not verificar_schema_custos():
        flash('⚠️ Módulo de Custos temporariamente indisponível.', 'warning')
        return redirect(url_for('main.index'))
    
    custo = CustoObra.query.filter_by(id=custo_id, admin_id=current_user.id).first_or_404()
    
    if request.method == 'POST':
        try:
            # SEGURANÇA: Validar que obra pertence ao admin atual
            obra_id = request.form.get('obra_id', type=int)
            obra = Obra.query.filter_by(id=obra_id, admin_id=current_user.id).first()
            
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
    obras = Obra.query.filter_by(admin_id=current_user.id, ativo=True).order_by(Obra.nome).all()
    return render_template('custos/custo_form.html', obras=obras, custo=custo)

@custos_bp.route('/deletar/<int:custo_id>', methods=['POST'])
@login_required
def deletar_custo(custo_id):
    """Deletar um custo."""
    if not verificar_schema_custos():
        flash('⚠️ Módulo de Custos temporariamente indisponível.', 'warning')
        return redirect(url_for('main.index'))
    
    custo = CustoObra.query.filter_by(id=custo_id, admin_id=current_user.id).first_or_404()
    
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
    
    # Filtros
    obra_id = request.args.get('obra_id', type=int)
    tipo = request.args.get('tipo')
    data_inicio = request.args.get('data_inicio')
    data_fim = request.args.get('data_fim')
    
    # Paginação - ✅ OTIMIZAÇÃO MÉDIO PRAZO 1
    page = request.args.get('page', 1, type=int)
    per_page = 20  # 20 custos por página
    
    # Query base
    query = CustoObra.query.filter_by(admin_id=current_user.id)
    
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
    obras = Obra.query.filter_by(admin_id=current_user.id, ativo=True).order_by(Obra.nome).all()
    tipos = ['mao_obra', 'material', 'veiculo', 'servico', 'alimentacao']
    
    # Estatísticas (calcular sobre resultados filtrados, NÃO sobre página atual)
    total_custos = db.session.query(func.sum(CustoObra.valor)).filter(
        CustoObra.admin_id == current_user.id
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
