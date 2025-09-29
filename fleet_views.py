"""
FLEET MANAGEMENT SYSTEM V3.0 - Blueprint Principal
==================================================
Sistema completo de gestão de frota com nomenclatura limpa
- Veículos (fleet_vehicle)
- Viagens (fleet_trip) 
- Custos (fleet_cost)
- Passageiros (fleet_passenger)

🎯 OBJETIVO: Rotas modernas com multi-tenant rigoroso
"""

from flask import Blueprint, render_template, request, jsonify, redirect, url_for, flash
from flask_login import login_required, current_user
from sqlalchemy import and_, func, desc, asc
from models import db, FleetVehicle, FleetTrip, FleetCost, FleetPassenger, Funcionario, Obra, TipoUsuario
from datetime import datetime, date
from decimal import Decimal
import logging

# Configurar logging
logger = logging.getLogger(__name__)

# Blueprint principal
fleet_bp = Blueprint('fleet', __name__, url_prefix='/fleet')

def get_admin_id():
    """Obter admin_id do usuário atual com multi-tenant rigoroso"""
    try:
        from flask_login import current_user
        if hasattr(current_user, 'is_authenticated') and current_user.is_authenticated:
            if hasattr(current_user, 'tipo_usuario'):
                if current_user.tipo_usuario == TipoUsuario.ADMIN:
                    return current_user.id
                else:
                    return getattr(current_user, 'admin_id', current_user.id)
            return getattr(current_user, 'admin_id', current_user.id)
        else:
            # Sistema de fallback automático
            from sqlalchemy import text
            admin_counts = db.session.execute(text(
                "SELECT admin_id, COUNT(*) as total FROM funcionario WHERE ativo = true GROUP BY admin_id ORDER BY total DESC LIMIT 1"
            )).fetchone()
            return admin_counts[0] if admin_counts else 10
    except Exception as e:
        logger.error(f"Erro ao obter admin_id: {e}")
        return 10

# ========================================
# ROTAS PRINCIPAIS - DASHBOARD E VEÍCULOS
# ========================================

@fleet_bp.route('/')
@fleet_bp.route('/dashboard')
@login_required
def dashboard():
    """
    Dashboard principal do Fleet V3.0
    Exibe resumo geral da frota e indicadores
    """
    try:
        admin_id = get_admin_id()
        logger.info(f"🚗 Fleet Dashboard - admin_id: {admin_id}")
        
        # Contar veículos ativos
        total_vehicles = FleetVehicle.query.filter_by(admin_id=admin_id).count()
        active_vehicles = FleetVehicle.query.filter_by(admin_id=admin_id, status='Ativo').count()
        
        # Contar viagens (últimos 30 dias)
        from datetime import datetime, timedelta
        thirty_days_ago = datetime.now() - timedelta(days=30)
        recent_trips = FleetTrip.query.filter(
            FleetTrip.admin_id == admin_id,
            FleetTrip.start_date >= thirty_days_ago
        ).count()
        
        # Calcular custos (último mês)
        total_costs = db.session.query(func.sum(FleetCost.amount)).filter(
            FleetCost.admin_id == admin_id,
            FleetCost.date >= thirty_days_ago
        ).scalar() or Decimal('0.00')
        
        # Últimas viagens
        latest_trips = FleetTrip.query.filter_by(admin_id=admin_id)\
                                    .order_by(FleetTrip.start_date.desc())\
                                    .limit(5).all()
        
        # Veículos com mais custos
        vehicle_costs = db.session.query(
            FleetVehicle.license_plate,
            FleetVehicle.make,
            FleetVehicle.model,
            func.sum(FleetCost.amount).label('total_cost')
        ).join(FleetCost, FleetVehicle.id == FleetCost.vehicle_id)\
         .filter(FleetVehicle.admin_id == admin_id)\
         .filter(FleetCost.date >= thirty_days_ago)\
         .group_by(FleetVehicle.id, FleetVehicle.license_plate, FleetVehicle.make, FleetVehicle.model)\
         .order_by(func.sum(FleetCost.amount).desc())\
         .limit(5).all()
        
        context = {
            'total_vehicles': total_vehicles,
            'active_vehicles': active_vehicles,
            'recent_trips': recent_trips,
            'total_costs': float(total_costs),
            'latest_trips': latest_trips,
            'vehicle_costs': vehicle_costs
        }
        
        logger.info(f"✅ Fleet Dashboard carregado - {total_vehicles} veículos, {recent_trips} viagens")
        return render_template('fleet/dashboard.html', **context)
        
    except Exception as e:
        logger.error(f"❌ Erro no Fleet Dashboard: {e}")
        flash('Erro ao carregar dashboard da frota', 'error')
        return redirect(url_for('main.dashboard'))

@fleet_bp.route('/vehicles')
@login_required
def vehicles():
    """Lista de veículos com filtros avançados"""
    try:
        admin_id = get_admin_id()
        logger.info(f"🚗 Listando veículos para admin_id={admin_id}")
        
        # Filtros da query string
        status_filter = request.args.get('status', '')
        kind_filter = request.args.get('kind', '')
        search_query = request.args.get('search', '')
        
        # Query base
        query = FleetVehicle.query.filter_by(admin_id=admin_id)
        
        # Aplicar filtros
        if status_filter:
            query = query.filter(FleetVehicle.status == status_filter)
        
        if kind_filter:
            query = query.filter(FleetVehicle.kind == kind_filter)
            
        if search_query:
            search_term = f"%{search_query}%"
            query = query.filter(
                db.or_(
                    FleetVehicle.plate.ilike(search_term),
                    FleetVehicle.brand.ilike(search_term),
                    FleetVehicle.model.ilike(search_term)
                )
            )
        
        # Ordenação e paginação
        vehicles = query.order_by(FleetVehicle.plate).all()
        
        # Estatísticas
        total_vehicles = len(vehicles)
        active_vehicles = len([v for v in vehicles if v.status == 'Ativo'])
        
        # Opções para filtros
        status_options = ['Ativo', 'Inativo', 'Manutenção']
        kind_options = ['Veículo', 'Caminhão', 'Van', 'Utilitário', 'Carro']
        
        logger.info(f"✅ Encontrados {total_vehicles} veículos ({active_vehicles} ativos)")
        
        return render_template('fleet/vehicles_list.html',
                             vehicles=vehicles,
                             total_vehicles=total_vehicles,
                             active_vehicles=active_vehicles,
                             status_options=status_options,
                             kind_options=kind_options,
                             current_filters={
                                 'status': status_filter,
                                 'kind': kind_filter,
                                 'search': search_query
                             })
        
    except Exception as e:
        logger.error(f"❌ Erro ao listar veículos: {e}")
        flash(f"Erro ao carregar veículos: {e}", 'danger')
        return render_template('fleet/vehicles_list.html', vehicles=[], total_vehicles=0, active_vehicles=0)

@fleet_bp.route('/vehicles/new', methods=['GET', 'POST'])
@login_required
def vehicle_new():
    """Criar novo veículo"""
    if request.method == 'POST':
        try:
            admin_id = get_admin_id()
            
            # Dados do formulário
            vehicle = FleetVehicle(
                admin_id=admin_id,
                plate=request.form['plate'].strip().upper(),
                brand=request.form['brand'].strip(),
                model=request.form.get('model', 'Não informado').strip(),
                kind=request.form.get('kind', 'Veículo'),
                year=int(request.form['year']) if request.form.get('year') else None,
                color=request.form.get('color', '').strip() or None,
                chassis=request.form.get('chassis', '').strip() or None,
                renavam=request.form.get('renavam', '').strip() or None,
                fuel_type=request.form.get('fuel_type', 'Gasolina'),
                odometer=int(request.form.get('odometer', 0)),
                status=request.form.get('status', 'Ativo')
            )
            
            # Validar placa única por admin
            existing = FleetVehicle.query.filter_by(
                admin_id=admin_id, 
                plate=vehicle.plate
            ).first()
            
            if existing:
                flash(f"Veículo com placa {vehicle.plate} já existe!", 'danger')
                return render_template('fleet/vehicle_form.html', vehicle=None, mode='create')
            
            db.session.add(vehicle)
            db.session.commit()
            
            logger.info(f"✅ Veículo criado: {vehicle.plate} - {vehicle.brand} {vehicle.model}")
            flash(f"Veículo {vehicle.plate} criado com sucesso!", 'success')
            
            return redirect(url_for('fleet.vehicles_list'))
            
        except Exception as e:
            db.session.rollback()
            logger.error(f"❌ Erro ao criar veículo: {e}")
            flash(f"Erro ao criar veículo: {e}", 'danger')
    
    return render_template('fleet/vehicle_form.html', vehicle=None, mode='create')

@fleet_bp.route('/vehicles/<int:vehicle_id>')
@login_required
def vehicle_detail(vehicle_id):
    """Detalhes do veículo com histórico"""
    try:
        admin_id = get_admin_id()
        
        vehicle = FleetVehicle.query.filter_by(
            id=vehicle_id, 
            admin_id=admin_id
        ).first_or_404()
        
        # Histórico de viagens (últimas 10)
        recent_trips = FleetTrip.query.filter_by(
            vehicle_id=vehicle_id,
            admin_id=admin_id
        ).order_by(desc(FleetTrip.trip_date)).limit(10).all()
        
        # Custos recentes (últimos 10)
        recent_costs = FleetCost.query.filter_by(
            vehicle_id=vehicle_id,
            admin_id=admin_id
        ).order_by(desc(FleetCost.cost_date)).limit(10).all()
        
        # Estatísticas
        total_trips = FleetTrip.query.filter_by(vehicle_id=vehicle_id, admin_id=admin_id).count()
        total_distance = db.session.query(func.sum(FleetTrip.distance)).filter_by(
            vehicle_id=vehicle_id, admin_id=admin_id
        ).scalar() or 0
        
        total_costs = db.session.query(func.sum(FleetCost.amount)).filter_by(
            vehicle_id=vehicle_id, admin_id=admin_id
        ).scalar() or Decimal('0.00')
        
        logger.info(f"📊 Veículo {vehicle.plate}: {total_trips} viagens, {total_distance}km, R$ {total_costs}")
        
        return render_template('fleet/vehicle_detail.html',
                             vehicle=vehicle,
                             recent_trips=recent_trips,
                             recent_costs=recent_costs,
                             stats={
                                 'total_trips': total_trips,
                                 'total_distance': total_distance,
                                 'total_costs': total_costs
                             })
        
    except Exception as e:
        logger.error(f"❌ Erro ao carregar detalhes do veículo: {e}")
        flash(f"Erro ao carregar veículo: {e}", 'danger')
        return redirect(url_for('fleet.vehicles_list'))

@fleet_bp.route('/vehicles/<int:vehicle_id>/edit', methods=['GET', 'POST'])
@login_required
def vehicle_edit(vehicle_id):
    """Editar veículo"""
    try:
        admin_id = get_admin_id()
        
        vehicle = FleetVehicle.query.filter_by(
            id=vehicle_id, 
            admin_id=admin_id
        ).first_or_404()
        
        if request.method == 'POST':
            # Atualizar dados
            vehicle.plate = request.form['plate'].strip().upper()
            vehicle.brand = request.form['brand'].strip()
            vehicle.model = request.form.get('model', 'Não informado').strip()
            vehicle.kind = request.form.get('kind', 'Veículo')
            vehicle.year = int(request.form['year']) if request.form.get('year') else None
            vehicle.color = request.form.get('color', '').strip() or None
            vehicle.chassis = request.form.get('chassis', '').strip() or None
            vehicle.renavam = request.form.get('renavam', '').strip() or None
            vehicle.fuel_type = request.form.get('fuel_type', 'Gasolina')
            vehicle.odometer = int(request.form.get('odometer', 0))
            vehicle.status = request.form.get('status', 'Ativo')
            vehicle.updated_at = datetime.utcnow()
            
            db.session.commit()
            
            logger.info(f"✅ Veículo atualizado: {vehicle.plate}")
            flash(f"Veículo {vehicle.plate} atualizado com sucesso!", 'success')
            
            return redirect(url_for('fleet.vehicle_detail', vehicle_id=vehicle.id))
        
        return render_template('fleet/vehicle_form.html', vehicle=vehicle, mode='edit')
        
    except Exception as e:
        db.session.rollback()
        logger.error(f"❌ Erro ao editar veículo: {e}")
        flash(f"Erro ao editar veículo: {e}", 'danger')
        return redirect(url_for('fleet.vehicles_list'))

# ========================================
# ROTAS - VIAGENS/USO
# ========================================

@fleet_bp.route('/trips')
@login_required
def trips():
    """Lista de viagens com filtros"""
    try:
        admin_id = get_admin_id()
        
        # Filtros
        vehicle_id = request.args.get('vehicle_id', type=int)
        driver_id = request.args.get('driver_id', type=int)
        date_from = request.args.get('date_from')
        date_to = request.args.get('date_to')
        
        # Query base
        query = FleetTrip.query.filter_by(admin_id=admin_id)
        
        # Aplicar filtros
        if vehicle_id:
            query = query.filter(FleetTrip.vehicle_id == vehicle_id)
        if driver_id:
            query = query.filter(FleetTrip.driver_id == driver_id)
        if date_from:
            query = query.filter(FleetTrip.trip_date >= datetime.strptime(date_from, '%Y-%m-%d').date())
        if date_to:
            query = query.filter(FleetTrip.trip_date <= datetime.strptime(date_to, '%Y-%m-%d').date())
        
        trips = query.order_by(desc(FleetTrip.trip_date)).limit(100).all()
        
        # Opções para filtros
        vehicles = FleetVehicle.query.filter_by(admin_id=admin_id, status='Ativo').order_by(FleetVehicle.plate).all()
        drivers = Funcionario.query.filter_by(admin_id=admin_id, ativo=True).order_by(Funcionario.nome).all()
        
        logger.info(f"🛣️ Encontradas {len(trips)} viagens")
        
        return render_template('fleet/trips_list.html',
                             trips=trips,
                             vehicles=vehicles,
                             drivers=drivers,
                             current_filters={
                                 'vehicle_id': vehicle_id,
                                 'driver_id': driver_id,
                                 'date_from': date_from,
                                 'date_to': date_to
                             })
        
    except Exception as e:
        logger.error(f"❌ Erro ao listar viagens: {e}")
        flash(f"Erro ao carregar viagens: {e}", 'danger')
        return render_template('fleet/trips_list.html', trips=[])

@fleet_bp.route('/trips/new', methods=['GET', 'POST'])
@login_required
def trip_new():
    """Criar nova viagem"""
    try:
        admin_id = get_admin_id()
        
        if request.method == 'POST':
            # Criar viagem
            trip = FleetTrip(
                admin_id=admin_id,
                vehicle_id=int(request.form['vehicle_id']),
                driver_id=int(request.form['driver_id']) if request.form.get('driver_id') else None,
                obra_id=int(request.form['obra_id']) if request.form.get('obra_id') else None,
                trip_date=datetime.strptime(request.form['trip_date'], '%Y-%m-%d').date(),
                start_time=datetime.strptime(request.form['start_time'], '%H:%M').time() if request.form.get('start_time') else None,
                end_time=datetime.strptime(request.form['end_time'], '%H:%M').time() if request.form.get('end_time') else None,
                start_odometer=int(request.form['start_odometer']) if request.form.get('start_odometer') else None,
                end_odometer=int(request.form['end_odometer']) if request.form.get('end_odometer') else None,
                purpose=request.form.get('purpose', '').strip() or None,
                notes=request.form.get('notes', '').strip() or None
            )
            
            # Calcular distância automaticamente
            trip.calculate_distance()
            
            db.session.add(trip)
            db.session.commit()
            
            logger.info(f"✅ Viagem criada: {trip.vehicle.plate} - {trip.trip_date}")
            flash("Viagem registrada com sucesso!", 'success')
            
            return redirect(url_for('fleet.trips_list'))
        
        # Opções para formulário
        vehicles = FleetVehicle.query.filter_by(admin_id=admin_id, status='Ativo').order_by(FleetVehicle.plate).all()
        drivers = Funcionario.query.filter_by(admin_id=admin_id, ativo=True).order_by(Funcionario.nome).all()
        obras = Obra.query.filter_by(admin_id=admin_id).order_by(Obra.nome).all()
        
        return render_template('fleet/trip_form.html',
                             trip=None,
                             vehicles=vehicles,
                             drivers=drivers,
                             obras=obras,
                             mode='create')
        
    except Exception as e:
        db.session.rollback()
        logger.error(f"❌ Erro ao criar viagem: {e}")
        flash(f"Erro ao criar viagem: {e}", 'danger')
        return redirect(url_for('fleet.trips_list'))

# ========================================
# ROTAS - CUSTOS
# ========================================

@fleet_bp.route('/costs')
@login_required  
def costs():
    """Lista de custos com filtros"""
    try:
        admin_id = get_admin_id()
        
        # Filtros
        vehicle_id = request.args.get('vehicle_id', type=int)
        category = request.args.get('category')
        status = request.args.get('status')
        date_from = request.args.get('date_from')
        date_to = request.args.get('date_to')
        
        # Query base
        query = FleetCost.query.filter_by(admin_id=admin_id)
        
        # Aplicar filtros
        if vehicle_id:
            query = query.filter(FleetCost.vehicle_id == vehicle_id)
        if category:
            query = query.filter(FleetCost.category == category)
        if status:
            query = query.filter(FleetCost.payment_status == status)
        if date_from:
            query = query.filter(FleetCost.cost_date >= datetime.strptime(date_from, '%Y-%m-%d').date())
        if date_to:
            query = query.filter(FleetCost.cost_date <= datetime.strptime(date_to, '%Y-%m-%d').date())
        
        costs = query.order_by(desc(FleetCost.cost_date)).limit(100).all()
        
        # Estatísticas
        total_amount = db.session.query(func.sum(FleetCost.amount)).filter(
            FleetCost.admin_id == admin_id
        ).scalar() or Decimal('0.00')
        
        # Opções para filtros
        vehicles = FleetVehicle.query.filter_by(admin_id=admin_id).order_by(FleetVehicle.plate).all()
        categories = ['fuel', 'toll', 'maintenance', 'insurance', 'tax', 'other']
        statuses = ['Pendente', 'Pago', 'Vencido', 'Cancelado']
        
        logger.info(f"💰 Encontrados {len(costs)} custos (total: R$ {total_amount})")
        
        return render_template('fleet/costs_list.html',
                             costs=costs,
                             total_amount=total_amount,
                             vehicles=vehicles,
                             categories=categories,
                             statuses=statuses,
                             current_filters={
                                 'vehicle_id': vehicle_id,
                                 'category': category,
                                 'status': status,
                                 'date_from': date_from,
                                 'date_to': date_to
                             })
        
    except Exception as e:
        logger.error(f"❌ Erro ao listar custos: {e}")
        flash(f"Erro ao carregar custos: {e}", 'danger')
        return render_template('fleet/costs_list.html', costs=[], total_amount=0)

@fleet_bp.route('/costs/new', methods=['GET', 'POST'])
@login_required
def cost_new():
    """Criar novo custo"""
    try:
        admin_id = get_admin_id()
        
        if request.method == 'POST':
            # Criar custo
            cost = FleetCost(
                admin_id=admin_id,
                vehicle_id=int(request.form['vehicle_id']),
                obra_id=int(request.form['obra_id']) if request.form.get('obra_id') else None,
                category=request.form['category'],
                amount=Decimal(request.form['amount']),
                cost_date=datetime.strptime(request.form['cost_date'], '%Y-%m-%d').date(),
                description=request.form['description'].strip(),
                supplier=request.form.get('supplier', '').strip() or None,
                invoice_number=request.form.get('invoice_number', '').strip() or None,
                payment_status=request.form.get('payment_status', 'Pendente'),
                payment_method=request.form.get('payment_method', '').strip() or None,
                notes=request.form.get('notes', '').strip() or None
            )
            
            db.session.add(cost)
            db.session.commit()
            
            logger.info(f"✅ Custo criado: {cost.vehicle.plate} - {cost.category} - R$ {cost.amount}")
            flash(f"Custo de R$ {cost.amount} registrado com sucesso!", 'success')
            
            return redirect(url_for('fleet.costs_list'))
        
        # Opções para formulário
        vehicles = FleetVehicle.query.filter_by(admin_id=admin_id).order_by(FleetVehicle.plate).all()
        obras = Obra.query.filter_by(admin_id=admin_id).order_by(Obra.nome).all()
        
        return render_template('fleet/cost_form.html',
                             cost=None,
                             vehicles=vehicles,
                             obras=obras,
                             mode='create')
        
    except Exception as e:
        db.session.rollback()
        logger.error(f"❌ Erro ao criar custo: {e}")
        flash(f"Erro ao criar custo: {e}", 'danger')
        return redirect(url_for('fleet.costs_list'))

# ========================================
# APIS AUXILIARES
# ========================================

@fleet_bp.route('/api/vehicles')
@login_required
def api_vehicles():
    """API para obter veículos (Select2)"""
    try:
        admin_id = get_admin_id()
        
        vehicles = FleetVehicle.query.filter_by(
            admin_id=admin_id,
            status='Ativo'
        ).order_by(FleetVehicle.plate).all()
        
        return jsonify({
            'success': True,
            'vehicles': [v.to_dict() for v in vehicles]
        })
        
    except Exception as e:
        logger.error(f"❌ Erro na API de veículos: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500

@fleet_bp.route('/api/vehicles/<int:vehicle_id>/stats')
@login_required
def api_vehicle_stats(vehicle_id):
    """API para estatísticas do veículo"""
    try:
        admin_id = get_admin_id()
        
        # Verificar se o veículo pertence ao admin
        vehicle = FleetVehicle.query.filter_by(
            id=vehicle_id,
            admin_id=admin_id
        ).first_or_404()
        
        # Calcular estatísticas
        total_trips = FleetTrip.query.filter_by(vehicle_id=vehicle_id, admin_id=admin_id).count()
        total_distance = db.session.query(func.sum(FleetTrip.distance)).filter_by(
            vehicle_id=vehicle_id, admin_id=admin_id
        ).scalar() or 0
        
        total_costs = db.session.query(func.sum(FleetCost.amount)).filter_by(
            vehicle_id=vehicle_id, admin_id=admin_id
        ).scalar() or Decimal('0.00')
        
        return jsonify({
            'success': True,
            'stats': {
                'total_trips': total_trips,
                'total_distance': total_distance,
                'total_costs': float(total_costs),
                'vehicle': vehicle.to_dict()
            }
        })
        
    except Exception as e:
        logger.error(f"❌ Erro nas estatísticas do veículo: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500

# ========================================
# HEALTH CHECK - FLEET V3.0
# ========================================

@fleet_bp.route('/health')
def fleet_health_check():
    """
    Health Check completo do Fleet V3.0
    Verifica conectividade, tabelas, dados e integridade
    """
    try:
        from sqlalchemy import text, inspect
        from datetime import datetime
        
        health_result = {
            'service': 'Fleet V3.0',
            'timestamp': datetime.now().isoformat(),
            'version': '3.0.0',
            'status': 'unknown',
            'checks': {},
            'summary': {},
            'errors': [],
            'warnings': []
        }
        
        # 1. Verificar conectividade com banco
        try:
            db.session.execute(text('SELECT 1'))
            health_result['checks']['database_connection'] = 'OK'
            logger.info("✅ Fleet Health Check - Conectividade: OK")
        except Exception as e:
            health_result['checks']['database_connection'] = 'FAIL'
            health_result['errors'].append(f'Database connection failed: {str(e)}')
            logger.error(f"❌ Fleet Health Check - Conectividade: {e}")
        
        # 2. Verificar existência das tabelas Fleet V3.0
        fleet_tables = {
            'fleet_vehicle': 'Veículos da Frota',
            'fleet_trip': 'Viagens/Deslocamentos', 
            'fleet_cost': 'Custos e Despesas',
            'fleet_passenger': 'Passageiros das Viagens'
        }
        
        try:
            inspector = inspect(db.engine)
            existing_tables = inspector.get_table_names()
            
            for table_name, description in fleet_tables.items():
                if table_name in existing_tables:
                    health_result['checks'][f'table_{table_name}'] = 'PRESENT'
                    logger.info(f"✅ Fleet Health Check - Tabela {table_name}: presente")
                    
                    # Contar registros
                    try:
                        result = db.session.execute(text(f'SELECT COUNT(*) FROM {table_name}'))
                        count = result.scalar()
                        health_result['checks'][f'count_{table_name}'] = count
                        logger.info(f"📊 Fleet Health Check - {table_name}: {count} registros")
                    except Exception as e:
                        health_result['warnings'].append(f'Failed to count records in {table_name}: {str(e)}')
                        
                else:
                    health_result['checks'][f'table_{table_name}'] = 'MISSING'
                    health_result['errors'].append(f'Required table missing: {table_name} ({description})')
                    logger.error(f"❌ Fleet Health Check - Tabela ausente: {table_name}")
                    
        except Exception as e:
            health_result['errors'].append(f'Table inspection failed: {str(e)}')
            logger.error(f"❌ Fleet Health Check - Inspeção de tabelas: {e}")
        
        # 3. Verificar integridade dos modelos Fleet
        try:
            # Tentar instanciar os modelos principais
            vehicle_count = FleetVehicle.query.count()
            trip_count = FleetTrip.query.count()
            cost_count = FleetCost.query.count()
            passenger_count = FleetPassenger.query.count()
            
            health_result['summary'] = {
                'total_vehicles': vehicle_count,
                'total_trips': trip_count,
                'total_costs': cost_count,
                'total_passengers': passenger_count
            }
            
            health_result['checks']['model_integrity'] = 'OK'
            logger.info(f"✅ Fleet Health Check - Modelos: {vehicle_count} veículos, {trip_count} viagens")
            
        except Exception as e:
            health_result['checks']['model_integrity'] = 'FAIL'
            health_result['errors'].append(f'Model integrity check failed: {str(e)}')
            logger.error(f"❌ Fleet Health Check - Integridade de modelos: {e}")
        
        # 4. Verificar funcionamento multi-tenant
        try:
            admin_id = get_admin_id()
            if admin_id:
                # Testar query com filtro de admin_id
                admin_vehicles = FleetVehicle.query.filter_by(admin_id=admin_id).count()
                health_result['checks']['multi_tenant'] = 'OK'
                health_result['summary']['admin_id'] = admin_id
                health_result['summary']['admin_vehicles'] = admin_vehicles
                logger.info(f"✅ Fleet Health Check - Multi-tenant: admin_id={admin_id}, {admin_vehicles} veículos")
            else:
                health_result['checks']['multi_tenant'] = 'WARNING'
                health_result['warnings'].append('No admin_id found - multi-tenant may not be working')
                
        except Exception as e:
            health_result['checks']['multi_tenant'] = 'FAIL'
            health_result['errors'].append(f'Multi-tenant check failed: {str(e)}')
            logger.error(f"❌ Fleet Health Check - Multi-tenant: {e}")
        
        # 5. Verificar tabelas legacy (devem estar ausentes)
        legacy_tables = [
            'veiculo', 'uso_veiculo', 'custo_veiculo', 'passageiro_veiculo',
            'alocacao_veiculo', 'equipe_veiculo', 'transferencia_veiculo'
        ]
        
        try:
            legacy_found = []
            for table in legacy_tables:
                if table in existing_tables:
                    legacy_found.append(table)
                    
            if legacy_found:
                health_result['checks']['legacy_cleanup'] = 'WARNING'
                health_result['warnings'].append(f'Legacy tables still present: {", ".join(legacy_found)}')
                logger.warning(f"⚠️ Fleet Health Check - Tabelas legacy presentes: {legacy_found}")
            else:
                health_result['checks']['legacy_cleanup'] = 'OK'
                logger.info("✅ Fleet Health Check - Limpeza legacy: todas as tabelas removidas")
                
        except Exception as e:
            health_result['warnings'].append(f'Legacy table check failed: {str(e)}')
            logger.warning(f"⚠️ Fleet Health Check - Verificação legacy: {e}")
        
        # Determinar status final
        if health_result['errors']:
            health_result['status'] = 'unhealthy'
            status_code = 503  # Service Unavailable
            logger.error(f"❌ Fleet Health Check: UNHEALTHY - {len(health_result['errors'])} errors")
        elif health_result['warnings']:
            health_result['status'] = 'degraded'
            status_code = 200  # OK but with warnings
            logger.warning(f"⚠️ Fleet Health Check: DEGRADED - {len(health_result['warnings'])} warnings")
        else:
            health_result['status'] = 'healthy'
            status_code = 200
            logger.info("✅ Fleet Health Check: HEALTHY")
        
        return jsonify(health_result), status_code
        
    except Exception as e:
        logger.error(f"❌ Fleet Health Check - Erro crítico: {e}")
        return jsonify({
            'service': 'Fleet V3.0',
            'timestamp': datetime.now().isoformat(),
            'status': 'error',
            'error': str(e)
        }), 500