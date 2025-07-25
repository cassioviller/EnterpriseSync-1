#!/usr/bin/env python3
"""
Sistema Unificado de Cálculo de KPIs - SIGE v8.0
Centraliza todos os cálculos para garantir consistência entre dashboard, cards e perfis
"""

from datetime import datetime, date, timedelta
from sqlalchemy import func, and_, or_
from app import db
from models import (
    Obra, CustoObra, RegistroPonto, RegistroAlimentacao, 
    CustoVeiculo, OutroCusto, Funcionario, Usuario
)

class KPIUnificado:
    """Classe centralizada para cálculos consistentes de KPIs"""
    
    def __init__(self, admin_id=None, data_inicio=None, data_fim=None):
        self.admin_id = admin_id
        self.data_inicio = data_inicio or date.today().replace(day=1)
        self.data_fim = data_fim or date.today()
        
    def calcular_custos_periodo(self, obra_id=None):
        """
        Calcula custos do período de forma unificada
        Se obra_id for None, calcula para todas as obras do admin
        """
        custos = {
            'alimentacao': 0,
            'transporte': 0,
            'mao_obra': 0,
            'outros': 0,
            'total': 0
        }
        
        # 1. ALIMENTAÇÃO
        query_alimentacao = db.session.query(func.sum(RegistroAlimentacao.valor))
        query_alimentacao = query_alimentacao.filter(
            RegistroAlimentacao.data >= self.data_inicio,
            RegistroAlimentacao.data <= self.data_fim
        )
        
        if obra_id:
            query_alimentacao = query_alimentacao.filter(RegistroAlimentacao.obra_id == obra_id)
        elif self.admin_id:
            # Filtrar por obras do admin
            obras_admin = db.session.query(Obra.id).filter(Obra.admin_id == self.admin_id).subquery()
            query_alimentacao = query_alimentacao.filter(RegistroAlimentacao.obra_id.in_(obras_admin))
        
        custos['alimentacao'] = query_alimentacao.scalar() or 0
        
        # 2. TRANSPORTE (Veículos)
        query_transporte = db.session.query(func.sum(CustoVeiculo.valor))
        query_transporte = query_transporte.filter(
            CustoVeiculo.data_custo >= self.data_inicio,
            CustoVeiculo.data_custo <= self.data_fim
        )
        
        if obra_id:
            query_transporte = query_transporte.filter(CustoVeiculo.obra_id == obra_id)
        elif self.admin_id:
            # Buscar veículos do admin (assumindo campo admin_id em Veiculo)
            # Por enquanto, inclui todos os custos de veículos
            pass
        
        custos['transporte'] = query_transporte.scalar() or 0
        
        # 3. MÃO DE OBRA (baseado em registros de ponto)
        funcionarios_filter = []
        if self.admin_id:
            funcionarios_admin = db.session.query(Funcionario.id).filter(
                Funcionario.admin_id == self.admin_id
            ).all()
            funcionarios_filter = [f[0] for f in funcionarios_admin]
        
        if funcionarios_filter or obra_id:
            registros_ponto = db.session.query(RegistroPonto).filter(
                RegistroPonto.data >= self.data_inicio,
                RegistroPonto.data <= self.data_fim
            )
            
            if obra_id:
                # Filtrar por registros da obra
                registros_ponto = registros_ponto.filter(
                    RegistroPonto.funcionario_id.in_(funcionarios_filter) if funcionarios_filter else True
                )
            elif funcionarios_filter:
                registros_ponto = registros_ponto.filter(
                    RegistroPonto.funcionario_id.in_(funcionarios_filter)
                )
            
            mao_obra_total = 0
            for registro in registros_ponto.all():
                funcionario = Funcionario.query.get(registro.funcionario_id)
                if funcionario and funcionario.salario:
                    # Calcular horas totais trabalhadas
                    horas_normais = registro.horas_trabalhadas or 0
                    horas_extras = registro.horas_extras or 0
                    total_horas = horas_normais + horas_extras
                    
                    # Valor hora baseado no salário (220h/mês)
                    valor_hora = funcionario.salario / 220
                    
                    # Custo das horas normais
                    custo_normal = horas_normais * valor_hora
                    
                    # Custo das horas extras (percentual do registro ou 50% padrão)
                    percentual_extra = (registro.percentual_extras or 50) / 100
                    custo_extra = horas_extras * valor_hora * (1 + percentual_extra)
                    
                    mao_obra_total += custo_normal + custo_extra
            
            custos['mao_obra'] = mao_obra_total
        
        # 4. OUTROS CUSTOS
        if funcionarios_filter:
            query_outros = db.session.query(func.sum(OutroCusto.valor))
            query_outros = query_outros.filter(
                OutroCusto.funcionario_id.in_(funcionarios_filter),
                OutroCusto.data >= self.data_inicio,
                OutroCusto.data <= self.data_fim
            )
            custos['outros'] = query_outros.scalar() or 0
        
        # TOTAL
        custos['total'] = sum(custos.values()) - custos['total']  # Evitar double counting
        
        return custos
    
    def calcular_kpis_dashboard(self):
        """KPIs para o dashboard principal"""
        if not self.admin_id:
            return {}
            
        # Funcionários ativos
        funcionarios_ativos = Funcionario.query.filter(
            Funcionario.admin_id == self.admin_id,
            Funcionario.ativo == True
        ).count()
        
        # Obras ativas
        obras_ativas = Obra.query.filter(
            Obra.admin_id == self.admin_id,
            Obra.status == 'Em andamento'
        ).count()
        
        # Veículos (assumindo que todos são acessíveis por admin)
        from models import Veiculo
        veiculos_ativos = Veiculo.query.filter(Veiculo.ativo == True).count()
        
        # Custos do período
        custos = self.calcular_custos_periodo()
        
        return {
            'funcionarios_ativos': funcionarios_ativos,
            'obras_ativas': obras_ativas,
            'veiculos_ativos': veiculos_ativos,
            'custos_periodo': custos['total'],
            'custos_detalhados': custos
        }
    
    def calcular_kpis_obra(self, obra_id):
        """KPIs específicos para uma obra"""
        obra = Obra.query.get(obra_id)
        if not obra:
            return {}
        
        # Custos específicos da obra
        custos = self.calcular_custos_periodo(obra_id=obra_id)
        
        # Adicionar custos diretos da obra (tabela custo_obra)
        custos_diretos = db.session.query(func.sum(CustoObra.valor)).filter(
            CustoObra.obra_id == obra_id,
            CustoObra.data >= self.data_inicio,
            CustoObra.data <= self.data_fim
        ).scalar() or 0
        
        custos['custos_diretos'] = custos_diretos
        custos['total'] += custos_diretos
        
        # Dias trabalhados (registros únicos de ponto)
        dias_trabalhados = db.session.query(RegistroPonto.data).filter(
            RegistroPonto.data >= self.data_inicio,
            RegistroPonto.data <= self.data_fim,
            RegistroPonto.hora_entrada.isnot(None)
        ).distinct().count()
        
        # Total de horas trabalhadas
        total_horas = db.session.query(
            func.sum(RegistroPonto.horas_trabalhadas + RegistroPonto.horas_extras)
        ).filter(
            RegistroPonto.data >= self.data_inicio,
            RegistroPonto.data <= self.data_fim
        ).scalar() or 0
        
        # Funcionários que trabalharam na obra
        funcionarios_obra = db.session.query(RegistroPonto.funcionario_id).filter(
            RegistroPonto.data >= self.data_inicio,
            RegistroPonto.data <= self.data_fim
        ).distinct().count()
        
        return {
            'custo_total': custos['total'],
            'custos_detalhados': custos,
            'dias_trabalhados': dias_trabalhados,
            'total_horas': total_horas,
            'funcionarios_periodo': funcionarios_obra,
            'obra_nome': obra.nome,
            'obra_status': obra.status
        }

def obter_kpi_dashboard(admin_id, data_inicio=None, data_fim=None):
    """Função de conveniência para dashboard"""
    kpi = KPIUnificado(admin_id=admin_id, data_inicio=data_inicio, data_fim=data_fim)
    return kpi.calcular_kpis_dashboard()

def obter_kpi_obra(obra_id, data_inicio=None, data_fim=None):
    """Função de conveniência para obra específica"""
    obra = Obra.query.get(obra_id)
    admin_id = obra.admin_id if obra else None
    kpi = KPIUnificado(admin_id=admin_id, data_inicio=data_inicio, data_fim=data_fim)
    return kpi.calcular_kpis_obra(obra_id)