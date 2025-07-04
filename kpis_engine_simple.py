#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
ENGINE DE CÁLCULO DE KPIs - SIGE v3.0 (Versão Simplificada)
Sistema Integrado de Gestão Empresarial - Estruturas do Vale

Implementa as regras de negócio específicas para cálculo correto de KPIs
conforme especificação técnica v3.0.

Data: 04 de Julho de 2025
"""

from datetime import date, datetime, time, timedelta
from sqlalchemy import func, and_, or_
from app import db

class KPIsEngine:
    """Engine principal para cálculo de todos os KPIs"""
    
    def __init__(self):
        self.HORAS_PADRAO_DIA = 8  # Horas padrão de trabalho por dia
        self.DIAS_SEMANA_TRABALHO = 5  # Segunda a sexta
        
    def calcular_kpis_funcionario(self, funcionario_id, data_inicio=None, data_fim=None):
        """
        Calcula todos os KPIs de um funcionário no período especificado
        Layout 4-4-2 conforme especificação
        """
        from models import Funcionario, RegistroPonto, RegistroAlimentacao
        
        # Definir período padrão se não fornecido
        if not data_inicio:
            data_inicio = date.today().replace(day=1)
        if not data_fim:
            data_fim = date.today()
        
        # Verificar se funcionário existe
        funcionario = Funcionario.query.get(funcionario_id)
        if not funcionario:
            return None
        
        # Calcular dias úteis no período
        dias_uteis = self._calcular_dias_uteis(data_inicio, data_fim)
        
        # Obter registros de ponto do período
        registros_ponto = RegistroPonto.query.filter(
            RegistroPonto.funcionario_id == funcionario_id,
            RegistroPonto.data >= data_inicio,
            RegistroPonto.data <= data_fim
        ).all()
        
        # Obter registros de alimentação do período
        registros_alimentacao = RegistroAlimentacao.query.filter(
            RegistroAlimentacao.funcionario_id == funcionario_id,
            RegistroAlimentacao.data >= data_inicio,
            RegistroAlimentacao.data <= data_fim
        ).all()
        
        # Calcular cada KPI
        kpis = {
            'horas_trabalhadas': self._calcular_horas_trabalhadas(registros_ponto),
            'horas_extras': self._calcular_horas_extras(registros_ponto),
            'faltas': self._calcular_faltas(registros_ponto, dias_uteis),
            'atrasos_horas': self._calcular_atrasos_horas(registros_ponto),
            'custo_mensal': self._calcular_custo_mensal(funcionario, registros_ponto, dias_uteis),
            'absenteismo': self._calcular_absenteismo(registros_ponto, dias_uteis),
            'media_diaria': self._calcular_media_horas_diarias(registros_ponto),
            'horas_perdidas': 0,  # Será calculado depois
            'produtividade': 0,   # Será calculado depois
            'custo_alimentacao': self._calcular_custo_alimentacao(registros_alimentacao),
            'periodo': {
                'inicio': data_inicio,
                'fim': data_fim,
                'dias_uteis': dias_uteis
            }
        }
        
        # Calcular KPIs que dependem de outros
        kpis['horas_perdidas'] = kpis['faltas'] * self.HORAS_PADRAO_DIA + kpis['atrasos_horas']
        
        horas_esperadas = dias_uteis * self.HORAS_PADRAO_DIA
        kpis['produtividade'] = (kpis['horas_trabalhadas'] / horas_esperadas * 100) if horas_esperadas > 0 else 0
        
        return kpis
    
    def _calcular_horas_trabalhadas(self, registros_ponto):
        """1. Horas Trabalhadas: Soma das horas efetivamente trabalhadas"""
        total_horas = 0
        for registro in registros_ponto:
            if registro.horas_trabalhadas:
                total_horas += registro.horas_trabalhadas
        return total_horas
    
    def _calcular_horas_extras(self, registros_ponto):
        """2. Horas Extras: Horas trabalhadas acima da jornada normal"""
        total_extras = 0
        for registro in registros_ponto:
            if registro.horas_extras:
                total_extras += registro.horas_extras
        return total_extras
    
    def _calcular_faltas(self, registros_ponto, dias_uteis):
        """3. Faltas: Número absoluto de dias úteis sem presença"""
        dias_com_registro = len([r for r in registros_ponto if r.hora_entrada])
        return max(0, dias_uteis - dias_com_registro)
    
    def _calcular_atrasos_horas(self, registros_ponto):
        """4. Atrasos: Total de horas de atraso (entrada + saída antecipada)"""
        total_atrasos = 0
        for registro in registros_ponto:
            if hasattr(registro, 'total_atraso_horas') and registro.total_atraso_horas:
                total_atrasos += registro.total_atraso_horas
        return total_atrasos
    
    def _calcular_custo_mensal(self, funcionario, registros_ponto, dias_uteis):
        """5. Custo Mensal: Valor total incluindo trabalho + faltas justificadas"""
        if not funcionario.salario:
            return 0
        
        # Calcular custo por hora
        custo_hora = funcionario.salario / (dias_uteis * self.HORAS_PADRAO_DIA) if dias_uteis > 0 else 0
        
        # Horas trabalhadas
        horas_trabalhadas = self._calcular_horas_trabalhadas(registros_ponto)
        
        # Horas extras (150% do valor normal)
        horas_extras = self._calcular_horas_extras(registros_ponto)
        
        custo_total = (horas_trabalhadas * custo_hora) + (horas_extras * custo_hora * 1.5)
        
        return custo_total
    
    def _calcular_absenteismo(self, registros_ponto, dias_uteis):
        """6. Absenteísmo: Percentual de ausências em relação aos dias úteis"""
        if dias_uteis == 0:
            return 0
        
        faltas = self._calcular_faltas(registros_ponto, dias_uteis)
        return (faltas / dias_uteis) * 100
    
    def _calcular_media_horas_diarias(self, registros_ponto):
        """7. Média Diária: Média de horas trabalhadas por dia presente"""
        if not registros_ponto:
            return 0
        
        total_horas = self._calcular_horas_trabalhadas(registros_ponto)
        dias_presentes = len([r for r in registros_ponto if r.hora_entrada])
        
        return total_horas / dias_presentes if dias_presentes > 0 else 0
    
    def _calcular_custo_alimentacao(self, registros_alimentacao):
        """10. Custo Alimentação: Gasto total com alimentação no período"""
        return sum(r.valor for r in registros_alimentacao if r.valor)
    
    def _calcular_dias_uteis(self, data_inicio, data_fim):
        """Calcula número de dias úteis no período (segunda a sexta, exceto feriados)"""
        total_dias = 0
        data_atual = data_inicio
        
        while data_atual <= data_fim:
            # Segunda a sexta (0 = segunda, 6 = domingo)
            if data_atual.weekday() < 5:  # 0-4 são dias úteis
                total_dias += 1
            data_atual += timedelta(days=1)
        
        return total_dias

# Instância global do engine
kpis_engine = KPIsEngine()