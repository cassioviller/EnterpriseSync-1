# ================================
# FLEET SERVICE - CAMADA DE SERVIÇO UNIFICADA
# ================================
# Adapter pattern para manter compatibilidade 100% com frontend
# Usa internamente as novas tabelas FLEET mas expõe interface legacy

import os
from datetime import datetime, date
from sqlalchemy import and_, or_, desc, func
from sqlalchemy.exc import IntegrityError
from app import db
from fleet_models import FleetVehicle, FleetVehicleUsage, FleetVehicleCost


class FleetService:
    """
    Serviço unificado da frota com adapter pattern.
    Internamente usa tabelas FLEET, mas expõe interface compatível com frontend legacy.
    """
    
    @staticmethod
    def _get_feature_flag():
        """Verificar se deve usar sistema FLEET ou legacy"""
        return os.environ.get('FLEET_CUTOVER', 'false').lower() == 'true'
    
    # ================================
    # VEÍCULOS - Interface compatível com VeiculoService
    # ================================
    
    @staticmethod
    def listar_veiculos(admin_id, filtros=None, page=1, per_page=20):
        """
        Lista veículos mantendo interface idêntica ao VeiculoService.
        Retorna dados no formato esperado pelo frontend.
        """
        try:
            query = FleetVehicle.query.filter_by(admin_owner_id=admin_id)
            
            # Aplicar filtros se fornecidos
            if filtros:
                if filtros.get('status'):
                    status_code = 'ativo' if filtros['status'] == 'ativo' else 'inativo'
                    query = query.filter_by(status_code=status_code)
                
                if filtros.get('tipo'):
                    query = query.filter_by(vehicle_kind=filtros['tipo'])
                
                if filtros.get('busca'):
                    busca = f"%{filtros['busca']}%"
                    query = query.filter(
                        or_(
                            FleetVehicle.reg_plate.ilike(busca),
                            FleetVehicle.make_name.ilike(busca),
                            FleetVehicle.model_name.ilike(busca)
                        )
                    )
            
            # Ordenação
            query = query.order_by(desc(FleetVehicle.created_at))
            
            # Paginação
            pagination = query.paginate(
                page=page, 
                per_page=per_page, 
                error_out=False
            )
            
            # Converter para formato legacy
            veiculos = [veiculo.to_dict() for veiculo in pagination.items]
            
            return {
                'success': True,
                'veiculos': veiculos,
                'pagination': {
                    'page': pagination.page,
                    'pages': pagination.pages,
                    'per_page': pagination.per_page,
                    'total': pagination.total,
                    'has_next': pagination.has_next,
                    'has_prev': pagination.has_prev
                }
            }
            
        except Exception as e:
            return {
                'success': False,
                'error': f'Erro ao listar veículos: {str(e)}',
                'veiculos': [],
                'pagination': None
            }
    
    @staticmethod
    def criar_veiculo(dados, admin_id):
        """
        Cria veículo mantendo interface idêntica ao VeiculoService.
        Aceita dados no formato legacy, converte para FLEET internamente.
        """
        try:
            # Criar novo veículo usando dados legacy
            novo_veiculo = FleetVehicle.from_legacy_dict({
                **dados,
                'admin_id': admin_id
            })
            
            db.session.add(novo_veiculo)
            db.session.commit()
            
            return {
                'success': True,
                'message': 'Veículo criado com sucesso!',
                'veiculo': novo_veiculo.to_dict()
            }
            
        except IntegrityError as e:
            db.session.rollback()
            if 'uk_fleet_vehicle_admin_plate' in str(e):
                return {
                    'success': False,
                    'error': 'Já existe um veículo com esta placa para sua empresa.',
                    'veiculo': None
                }
            else:
                return {
                    'success': False,
                    'error': f'Erro de integridade: {str(e)}',
                    'veiculo': None
                }
        except Exception as e:
            db.session.rollback()
            return {
                'success': False,
                'error': f'Erro ao criar veículo: {str(e)}',
                'veiculo': None
            }
    
    @staticmethod
    def atualizar_veiculo(veiculo_id, dados, admin_id):
        """
        Atualiza veículo mantendo interface idêntica ao VeiculoService.
        """
        try:
            veiculo = FleetVehicle.query.filter_by(
                vehicle_id=veiculo_id,
                admin_owner_id=admin_id
            ).first()
            
            if not veiculo:
                return {
                    'success': False,
                    'error': 'Veículo não encontrado.',
                    'veiculo': None
                }
            
            # Atualizar campos mapeando nomes legacy para novos
            if 'placa' in dados:
                veiculo.reg_plate = dados['placa']
            if 'marca' in dados:
                veiculo.make_name = dados['marca']
            if 'modelo' in dados:
                veiculo.model_name = dados['modelo']
            if 'ano' in dados:
                veiculo.vehicle_year = dados['ano']
            if 'tipo' in dados:
                veiculo.vehicle_kind = dados['tipo']
            if 'km_atual' in dados:
                veiculo.current_km = dados['km_atual']
            if 'cor' in dados:
                veiculo.vehicle_color = dados['cor']
            if 'combustivel' in dados:
                veiculo.fuel_type = dados['combustivel']
            if 'ativo' in dados:
                veiculo.status_code = 'ativo' if dados['ativo'] else 'inativo'
            
            veiculo.updated_at = datetime.utcnow()
            
            db.session.commit()
            
            return {
                'success': True,
                'message': 'Veículo atualizado com sucesso!',
                'veiculo': veiculo.to_dict()
            }
            
        except Exception as e:
            db.session.rollback()
            return {
                'success': False,
                'error': f'Erro ao atualizar veículo: {str(e)}',
                'veiculo': None
            }
    
    @staticmethod
    def obter_veiculo(veiculo_id, admin_id):
        """
        Obtém veículo específico mantendo interface legacy.
        """
        try:
            veiculo = FleetVehicle.query.filter_by(
                vehicle_id=veiculo_id,
                admin_owner_id=admin_id
            ).first()
            
            if not veiculo:
                return {
                    'success': False,
                    'error': 'Veículo não encontrado.',
                    'veiculo': None
                }
            
            return {
                'success': True,
                'veiculo': veiculo.to_dict()
            }
            
        except Exception as e:
            return {
                'success': False,
                'error': f'Erro ao obter veículo: {str(e)}',
                'veiculo': None
            }
    
    # ================================
    # USOS DE VEÍCULOS - Interface compatível com UsoVeiculoService
    # ================================
    
    @staticmethod
    def criar_uso_veiculo(dados, admin_id):
        """
        Cria uso de veículo mantendo interface idêntica ao UsoVeiculoService.
        """
        try:
            # Mapear vehicle_id se vier como veiculo_id
            if 'veiculo_id' in dados and 'vehicle_id' not in dados:
                dados['vehicle_id'] = dados['veiculo_id']
            
            novo_uso = FleetVehicleUsage.from_legacy_dict({
                **dados,
                'admin_id': admin_id
            })
            
            # Calcular distância automaticamente
            novo_uso.calculate_distance()
            
            db.session.add(novo_uso)
            db.session.commit()
            
            return {
                'success': True,
                'message': 'Uso de veículo registrado com sucesso!',
                'uso': novo_uso.to_dict()
            }
            
        except Exception as e:
            db.session.rollback()
            return {
                'success': False,
                'error': f'Erro ao registrar uso: {str(e)}',
                'uso': None
            }
    
    @staticmethod
    def listar_usos_veiculo(veiculo_id, admin_id, filtros=None, page=1, per_page=20):
        """
        Lista usos de veículo mantendo interface legacy.
        """
        try:
            query = FleetVehicleUsage.query.filter_by(
                vehicle_id=veiculo_id,
                admin_owner_id=admin_id
            )
            
            # Aplicar filtros
            if filtros:
                if filtros.get('data_inicio'):
                    query = query.filter(FleetVehicleUsage.usage_date >= filtros['data_inicio'])
                if filtros.get('data_fim'):
                    query = query.filter(FleetVehicleUsage.usage_date <= filtros['data_fim'])
                if filtros.get('motorista_id'):
                    query = query.filter_by(driver_id=filtros['motorista_id'])
            
            # Ordenação
            query = query.order_by(desc(FleetVehicleUsage.usage_date))
            
            # Paginação
            pagination = query.paginate(
                page=page,
                per_page=per_page,
                error_out=False
            )
            
            # Converter para formato legacy
            usos = [uso.to_dict() for uso in pagination.items]
            
            return {
                'success': True,
                'usos': usos,
                'pagination': {
                    'page': pagination.page,
                    'pages': pagination.pages,
                    'per_page': pagination.per_page,
                    'total': pagination.total,
                    'has_next': pagination.has_next,
                    'has_prev': pagination.has_prev
                }
            }
            
        except Exception as e:
            return {
                'success': False,
                'error': f'Erro ao listar usos: {str(e)}',
                'usos': [],
                'pagination': None
            }
    
    # ================================
    # CUSTOS DE VEÍCULOS - Interface compatível com CustoVeiculoService
    # ================================
    
    @staticmethod
    def criar_custo_veiculo(dados, admin_id):
        """
        Cria custo de veículo mantendo interface idêntica ao CustoVeiculoService.
        """
        try:
            # Mapear vehicle_id se vier como veiculo_id
            if 'veiculo_id' in dados and 'vehicle_id' not in dados:
                dados['vehicle_id'] = dados['veiculo_id']
            
            novo_custo = FleetVehicleCost.from_legacy_dict({
                **dados,
                'admin_id': admin_id
            })
            
            db.session.add(novo_custo)
            db.session.commit()
            
            return {
                'success': True,
                'message': 'Custo registrado com sucesso!',
                'custo': novo_custo.to_dict()
            }
            
        except Exception as e:
            db.session.rollback()
            return {
                'success': False,
                'error': f'Erro ao registrar custo: {str(e)}',
                'custo': None
            }
    
    @staticmethod
    def listar_custos_veiculo(veiculo_id, admin_id, filtros=None, page=1, per_page=20):
        """
        Lista custos de veículo mantendo interface legacy.
        """
        try:
            query = FleetVehicleCost.query.filter_by(
                vehicle_id=veiculo_id,
                admin_owner_id=admin_id
            )
            
            # Aplicar filtros
            if filtros:
                if filtros.get('data_inicio'):
                    query = query.filter(FleetVehicleCost.cost_date >= filtros['data_inicio'])
                if filtros.get('data_fim'):
                    query = query.filter(FleetVehicleCost.cost_date <= filtros['data_fim'])
                if filtros.get('tipo_custo'):
                    query = query.filter_by(cost_type=filtros['tipo_custo'])
                if filtros.get('status_pagamento'):
                    query = query.filter_by(payment_status=filtros['status_pagamento'])
            
            # Ordenação
            query = query.order_by(desc(FleetVehicleCost.cost_date))
            
            # Paginação
            pagination = query.paginate(
                page=page,
                per_page=per_page,
                error_out=False
            )
            
            # Converter para formato legacy
            custos = [custo.to_dict() for custo in pagination.items]
            
            return {
                'success': True,
                'custos': custos,
                'pagination': {
                    'page': pagination.page,
                    'pages': pagination.pages,
                    'per_page': pagination.per_page,
                    'total': pagination.total,
                    'has_next': pagination.has_next,
                    'has_prev': pagination.has_prev
                }
            }
            
        except Exception as e:
            return {
                'success': False,
                'error': f'Erro ao listar custos: {str(e)}',
                'custos': [],
                'pagination': None
            }
    
    # ================================
    # ESTATÍSTICAS E RELATÓRIOS
    # ================================
    
    @staticmethod
    def obter_estatisticas_veiculo(veiculo_id, admin_id, periodo_dias=30):
        """
        Obtém estatísticas do veículo para dashboards.
        """
        try:
            # Data limite
            data_limite = date.today().replace(day=1)
            if periodo_dias:
                from datetime import timedelta
                data_limite = date.today() - timedelta(days=periodo_dias)
            
            # Estatísticas de uso
            usos = db.session.query(
                func.count(FleetVehicleUsage.usage_id).label('total_usos'),
                func.sum(FleetVehicleUsage.distance_km).label('total_km'),
                func.avg(FleetVehicleUsage.distance_km).label('media_km')
            ).filter(
                FleetVehicleUsage.vehicle_id == veiculo_id,
                FleetVehicleUsage.admin_owner_id == admin_id,
                FleetVehicleUsage.usage_date >= data_limite
            ).first()
            
            # Estatísticas de custos
            custos = db.session.query(
                func.count(FleetVehicleCost.cost_id).label('total_custos'),
                func.sum(FleetVehicleCost.cost_amount).label('total_valor')
            ).filter(
                FleetVehicleCost.vehicle_id == veiculo_id,
                FleetVehicleCost.admin_owner_id == admin_id,
                FleetVehicleCost.cost_date >= data_limite
            ).first()
            
            return {
                'success': True,
                'estatisticas': {
                    'periodo_dias': periodo_dias,
                    'usos': {
                        'total': usos.total_usos or 0,
                        'total_km': float(usos.total_km or 0),
                        'media_km': float(usos.media_km or 0)
                    },
                    'custos': {
                        'total': custos.total_custos or 0,
                        'total_valor': float(custos.total_valor or 0)
                    }
                }
            }
            
        except Exception as e:
            return {
                'success': False,
                'error': f'Erro ao calcular estatísticas: {str(e)}',
                'estatisticas': None
            }
    
    # ================================
    # UTILITÁRIOS
    # ================================
    
    @staticmethod
    def verificar_sistema_ativo():
        """
        Verifica se o sistema FLEET está ativo via feature flag.
        """
        return FleetService._get_feature_flag()
    
    @staticmethod
    def obter_contadores_admin(admin_id):
        """
        Obtém contadores gerais para dashboards.
        """
        try:
            total_veiculos = FleetVehicle.query.filter_by(admin_owner_id=admin_id).count()
            veiculos_ativos = FleetVehicle.query.filter_by(
                admin_owner_id=admin_id, 
                status_code='ativo'
            ).count()
            
            # Usos do mês atual
            hoje = date.today()
            primeiro_dia = hoje.replace(day=1)
            usos_mes = FleetVehicleUsage.query.filter(
                FleetVehicleUsage.admin_owner_id == admin_id,
                FleetVehicleUsage.usage_date >= primeiro_dia
            ).count()
            
            # Custos do mês atual
            custos_mes = db.session.query(
                func.sum(FleetVehicleCost.cost_amount)
            ).filter(
                FleetVehicleCost.admin_owner_id == admin_id,
                FleetVehicleCost.cost_date >= primeiro_dia
            ).scalar() or 0
            
            return {
                'success': True,
                'contadores': {
                    'total_veiculos': total_veiculos,
                    'veiculos_ativos': veiculos_ativos,
                    'usos_mes_atual': usos_mes,
                    'custos_mes_atual': float(custos_mes)
                }
            }
            
        except Exception as e:
            return {
                'success': False,
                'error': f'Erro ao calcular contadores: {str(e)}',
                'contadores': None
            }