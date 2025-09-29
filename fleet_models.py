# ================================
# NOVO SISTEMA FLEET - SCHEMA COMPLETO
# ================================
# Reconstrução total do sistema de veículos com nomes únicos
# Evita todos os conflitos com sistema legacy

from datetime import datetime
from app import db


class FleetVehicle(db.Model):
    """Modelo principal da frota - substitui completamente 'veiculo'"""
    __tablename__ = 'fleet_vehicle'
    
    # PK com nome único
    vehicle_id = db.Column(db.Integer, primary_key=True)
    
    # Dados básicos - nomes únicos
    reg_plate = db.Column(db.String(10), nullable=False)  # substitui 'placa'
    make_name = db.Column(db.String(50), nullable=False)  # substitui 'marca'
    model_name = db.Column(db.String(100), nullable=False, default='Não informado')  # substitui 'modelo'
    vehicle_year = db.Column(db.Integer, nullable=False)  # substitui 'ano'
    vehicle_kind = db.Column(db.String(30), nullable=False, default='Veículo')  # substitui 'tipo'
    
    # Controle de quilometragem
    current_km = db.Column(db.Integer, default=0)  # substitui 'km_atual'
    
    # Dados opcionais
    vehicle_color = db.Column(db.String(30))  # substitui 'cor'
    chassis_number = db.Column(db.String(50))  # substitui 'chassi'
    renavam_code = db.Column(db.String(20))  # substitui 'renavam'
    fuel_type = db.Column(db.String(20), default='Gasolina')  # substitui 'combustivel'
    
    # Controle de status
    status_code = db.Column(db.String(20), default='ativo')  # substitui 'ativo' boolean
    
    # Manutenção
    last_maintenance_date = db.Column(db.Date)  # substitui 'data_ultima_manutencao'
    next_maintenance_date = db.Column(db.Date)  # substitui 'data_proxima_manutencao'
    next_maintenance_km = db.Column(db.Integer)  # substitui 'km_proxima_manutencao'
    
    # Multi-tenant - nome único
    admin_owner_id = db.Column(db.Integer, db.ForeignKey('usuario.id'), nullable=False)  # substitui 'admin_id'
    
    # Controle de tempo
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relacionamentos
    admin_owner = db.relationship('Usuario', backref='fleet_vehicles')
    usage_records = db.relationship('FleetVehicleUsage', backref='fleet_vehicle', cascade='all, delete-orphan', lazy='dynamic')
    cost_records = db.relationship('FleetVehicleCost', backref='fleet_vehicle', cascade='all, delete-orphan', lazy='dynamic')
    
    # Índices únicos para performance
    __table_args__ = (
        db.UniqueConstraint('admin_owner_id', 'reg_plate', name='uk_fleet_vehicle_admin_plate'),
        db.Index('idx_fleet_vehicle_admin_kind', 'admin_owner_id', 'vehicle_kind'),
        db.Index('idx_fleet_vehicle_plate_admin', 'reg_plate', 'admin_owner_id'),
        db.Index('idx_fleet_vehicle_status', 'admin_owner_id', 'status_code'),
    )
    
    def __repr__(self):
        return f'<FleetVehicle {self.reg_plate} - {self.make_name} {self.model_name}>'
    
    def to_dict(self):
        """Converter para dicionário compatível com frontend"""
        return {
            'id': self.vehicle_id,  # Mapeamento para frontend
            'placa': self.reg_plate,  # Mapeamento para frontend  
            'marca': self.make_name,  # Mapeamento para frontend
            'modelo': self.model_name,  # Mapeamento para frontend
            'ano': self.vehicle_year,  # Mapeamento para frontend
            'tipo': self.vehicle_kind,  # Mapeamento para frontend
            'km_atual': self.current_km,  # Mapeamento para frontend
            'cor': self.vehicle_color,  # Mapeamento para frontend
            'combustivel': self.fuel_type,  # Mapeamento para frontend
            'ativo': self.status_code == 'ativo',  # Conversão boolean para frontend
            'data_ultima_manutencao': self.last_maintenance_date.isoformat() if self.last_maintenance_date else None,
            'data_proxima_manutencao': self.next_maintenance_date.isoformat() if self.next_maintenance_date else None,
            'km_proxima_manutencao': self.next_maintenance_km,
            'admin_id': self.admin_owner_id,  # Mapeamento para frontend
            'created_at': self.created_at.isoformat() if self.created_at else None
        }
    
    @classmethod
    def from_legacy_dict(cls, legacy_data):
        """Converter dados do formato legacy para novo schema"""
        return cls(
            reg_plate=legacy_data.get('placa', ''),
            make_name=legacy_data.get('marca', ''),
            model_name=legacy_data.get('modelo', 'Não informado'),
            vehicle_year=legacy_data.get('ano', datetime.now().year),
            vehicle_kind=legacy_data.get('tipo', 'Veículo'),
            current_km=legacy_data.get('km_atual', 0),
            vehicle_color=legacy_data.get('cor'),
            chassis_number=legacy_data.get('chassi'),
            renavam_code=legacy_data.get('renavam'),
            fuel_type=legacy_data.get('combustivel', 'Gasolina'),
            status_code='ativo' if legacy_data.get('ativo', True) else 'inativo',
            last_maintenance_date=legacy_data.get('data_ultima_manutencao'),
            next_maintenance_date=legacy_data.get('data_proxima_manutencao'),
            next_maintenance_km=legacy_data.get('km_proxima_manutencao'),
            admin_owner_id=legacy_data.get('admin_id')
        )
    
    @property
    def display_name(self):
        """Nome para exibição - compatível com frontend"""
        return f"{self.make_name} {self.model_name}"
    
    @property
    def full_description(self):
        """Descrição completa - compatível com frontend"""
        return f"{self.reg_plate} - {self.make_name} {self.model_name} ({self.vehicle_year})"


class FleetVehicleUsage(db.Model):
    """Registros de uso da frota - substitui completamente 'uso_veiculo'"""
    __tablename__ = 'fleet_vehicle_usage'
    
    # PK com nome único
    usage_id = db.Column(db.Integer, primary_key=True)
    
    # Relacionamentos principais - nomes únicos
    vehicle_id = db.Column(db.Integer, db.ForeignKey('fleet_vehicle.vehicle_id'), nullable=False)
    driver_id = db.Column(db.Integer, db.ForeignKey('funcionario.id'), nullable=True)  # substitui 'motorista_id'
    worksite_id = db.Column(db.Integer, db.ForeignKey('obra.id'), nullable=True)  # substitui 'obra_id'
    
    # Dados do uso
    usage_date = db.Column(db.Date, nullable=False)  # substitui 'data_uso'
    departure_time = db.Column(db.Time, nullable=True)  # substitui 'hora_saida'
    return_time = db.Column(db.Time, nullable=True)  # substitui 'hora_retorno'
    
    # Quilometragem
    start_km = db.Column(db.Integer, nullable=True)  # substitui 'km_inicial'
    end_km = db.Column(db.Integer)  # substitui 'km_final'
    distance_km = db.Column(db.Integer)  # substitui 'km_percorrido'
    
    # Passageiros
    front_passengers = db.Column(db.Text)  # substitui 'passageiros_frente'
    rear_passengers = db.Column(db.Text)  # substitui 'passageiros_tras'
    
    # Controle
    vehicle_responsible = db.Column(db.String(100))  # substitui 'responsavel_veiculo'
    
    # Observações
    usage_notes = db.Column(db.Text)  # substitui 'observacoes'
    
    # Multi-tenant
    admin_owner_id = db.Column(db.Integer, db.ForeignKey('usuario.id'), nullable=False)
    
    # Controle de tempo
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relacionamentos
    driver = db.relationship('Funcionario', foreign_keys=[driver_id], backref='fleet_usage_records')
    worksite = db.relationship('Obra', backref='fleet_usage_records')
    admin_owner = db.relationship('Usuario', backref='fleet_usage_records')
    
    # Índices para performance
    __table_args__ = (
        db.Index('idx_fleet_usage_date_admin', 'usage_date', 'admin_owner_id'),
        db.Index('idx_fleet_usage_driver', 'driver_id'),
        db.Index('idx_fleet_usage_worksite', 'worksite_id'),
        db.Index('idx_fleet_usage_vehicle', 'vehicle_id'),
    )
    
    def __repr__(self):
        driver_name = self.driver.nome if self.driver else f"ID:{self.driver_id}"
        vehicle_plate = self.fleet_vehicle.reg_plate if self.fleet_vehicle else f"ID:{self.vehicle_id}"
        return f'<FleetVehicleUsage {vehicle_plate} - {driver_name} ({self.usage_date})>'
    
    def to_dict(self):
        """Converter para dicionário compatível com frontend"""
        return {
            'id': self.usage_id,  # Mapeamento para frontend
            'veiculo_id': self.vehicle_id,  # Mapeamento para frontend
            'veiculo_placa': self.fleet_vehicle.reg_plate if self.fleet_vehicle else None,
            'motorista_id': self.driver_id,  # Mapeamento para frontend
            'motorista_nome': self.driver.nome if self.driver else None,
            'obra_id': self.worksite_id,  # Mapeamento para frontend
            'obra_nome': self.worksite.nome if self.worksite else None,
            'data_uso': self.usage_date.isoformat(),  # Mapeamento para frontend
            'hora_saida': self.departure_time.isoformat() if self.departure_time else None,
            'hora_retorno': self.return_time.isoformat() if self.return_time else None,
            'km_inicial': self.start_km,  # Mapeamento para frontend
            'km_final': self.end_km,  # Mapeamento para frontend
            'km_percorrido': self.distance_km,  # Mapeamento para frontend
            'observacoes': self.usage_notes,  # Mapeamento para frontend
            'admin_id': self.admin_owner_id,  # Mapeamento para frontend
            'created_at': self.created_at.isoformat() if self.created_at else None
        }
    
    @classmethod
    def from_legacy_dict(cls, legacy_data):
        """Converter dados do formato legacy para novo schema"""
        return cls(
            vehicle_id=legacy_data.get('veiculo_id'),
            driver_id=legacy_data.get('motorista_id'),
            worksite_id=legacy_data.get('obra_id'),
            usage_date=legacy_data.get('data_uso'),
            departure_time=legacy_data.get('hora_saida'),
            return_time=legacy_data.get('hora_retorno'),
            start_km=legacy_data.get('km_inicial'),
            end_km=legacy_data.get('km_final'),
            distance_km=legacy_data.get('km_percorrido'),
            front_passengers=legacy_data.get('passageiros_frente'),
            rear_passengers=legacy_data.get('passageiros_tras'),
            vehicle_responsible=legacy_data.get('responsavel_veiculo'),
            usage_notes=legacy_data.get('observacoes'),
            admin_owner_id=legacy_data.get('admin_id')
        )
    
    def calculate_distance(self):
        """Calcula automaticamente distância percorrida"""
        if self.start_km and self.end_km and self.end_km > self.start_km:
            self.distance_km = self.end_km - self.start_km
            return self.distance_km
        return 0


class FleetVehicleCost(db.Model):
    """Custos da frota - substitui completamente 'custo_veiculo'"""
    __tablename__ = 'fleet_vehicle_cost'
    
    # PK com nome único
    cost_id = db.Column(db.Integer, primary_key=True)
    
    # Relacionamento principal
    vehicle_id = db.Column(db.Integer, db.ForeignKey('fleet_vehicle.vehicle_id'), nullable=False)
    
    # Dados do custo
    cost_date = db.Column(db.Date, nullable=False)  # substitui 'data_custo'
    cost_type = db.Column(db.String(30), nullable=False)  # substitui 'tipo_custo'
    
    # Valores
    cost_amount = db.Column(db.Numeric(10, 2), nullable=False)  # substitui 'valor'
    
    # Detalhes
    cost_description = db.Column(db.String(200), nullable=False)  # substitui 'descricao'
    supplier_name = db.Column(db.String(100))  # substitui 'fornecedor'
    invoice_number = db.Column(db.String(20))  # substitui 'numero_nota_fiscal'
    due_date = db.Column(db.Date)  # substitui 'data_vencimento'
    
    # Status
    payment_status = db.Column(db.String(20), default='Pendente')  # substitui 'status_pagamento'
    payment_method = db.Column(db.String(30))  # substitui 'forma_pagamento'
    
    # Controle de quilometragem
    vehicle_km = db.Column(db.Integer)  # substitui 'km_veiculo'
    
    # Observações
    cost_notes = db.Column(db.Text)  # substitui 'observacoes'
    
    # Multi-tenant
    admin_owner_id = db.Column(db.Integer, db.ForeignKey('usuario.id'), nullable=False)
    
    # Controle de tempo
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relacionamentos
    admin_owner = db.relationship('Usuario', backref='fleet_cost_records')
    
    # Índices para performance
    __table_args__ = (
        db.Index('idx_fleet_cost_date_admin', 'cost_date', 'admin_owner_id'),
        db.Index('idx_fleet_cost_type', 'cost_type', 'admin_owner_id'),
        db.Index('idx_fleet_cost_status', 'payment_status', 'admin_owner_id'),
        db.Index('idx_fleet_cost_vehicle', 'vehicle_id'),
    )
    
    def __repr__(self):
        vehicle_plate = self.fleet_vehicle.reg_plate if self.fleet_vehicle else f"ID:{self.vehicle_id}"
        return f'<FleetVehicleCost {vehicle_plate} - {self.cost_type} R${self.cost_amount}>'
    
    def to_dict(self):
        """Converter para dicionário compatível com frontend"""
        return {
            'id': self.cost_id,  # Mapeamento para frontend
            'veiculo_id': self.vehicle_id,  # Mapeamento para frontend
            'veiculo_placa': self.fleet_vehicle.reg_plate if self.fleet_vehicle else None,
            'data_custo': self.cost_date.isoformat(),  # Mapeamento para frontend
            'tipo_custo': self.cost_type,  # Mapeamento para frontend
            'valor': float(self.cost_amount),  # Mapeamento para frontend
            'descricao': self.cost_description,  # Mapeamento para frontend
            'fornecedor': self.supplier_name,  # Mapeamento para frontend
            'numero_nota_fiscal': self.invoice_number,  # Mapeamento para frontend
            'data_vencimento': self.due_date.isoformat() if self.due_date else None,
            'status_pagamento': self.payment_status,  # Mapeamento para frontend
            'forma_pagamento': self.payment_method,  # Mapeamento para frontend
            'km_veiculo': self.vehicle_km,  # Mapeamento para frontend
            'observacoes': self.cost_notes,  # Mapeamento para frontend
            'admin_id': self.admin_owner_id,  # Mapeamento para frontend
            'created_at': self.created_at.isoformat() if self.created_at else None
        }
    
    @classmethod
    def from_legacy_dict(cls, legacy_data):
        """Converter dados do formato legacy para novo schema"""
        return cls(
            vehicle_id=legacy_data.get('veiculo_id'),
            cost_date=legacy_data.get('data_custo'),
            cost_type=legacy_data.get('tipo_custo'),
            cost_amount=legacy_data.get('valor'),
            cost_description=legacy_data.get('descricao'),
            supplier_name=legacy_data.get('fornecedor'),
            invoice_number=legacy_data.get('numero_nota_fiscal'),
            due_date=legacy_data.get('data_vencimento'),
            payment_status=legacy_data.get('status_pagamento', 'Pendente'),
            payment_method=legacy_data.get('forma_pagamento'),
            vehicle_km=legacy_data.get('km_veiculo'),
            cost_notes=legacy_data.get('observacoes'),
            admin_owner_id=legacy_data.get('admin_id')
        )