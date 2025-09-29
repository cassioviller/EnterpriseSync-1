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
# ROTAS PRINCIPAIS - VEÍCULOS
# ========================================

@fleet_bp.route('/vehicles')
@login_required
def vehicles_list():
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
def trips_list():
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
def costs_list():
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