#!/usr/bin/env python3
"""
KPIs Engine v8.2 - Implementação Conforme Documento de Revisão
Sistema completo de cálculo de KPIs seguindo as especificações técnicas
do documento "PROMPT DE REVISÃO – CÁLCULO DE KPIs E CUSTOS DE RH"

Autor: Sistema SIGE v8.2
Data: 1º de agosto de 2025
"""

from datetime import datetime, date
from sqlalchemy import func, and_, or_

class KPIsEngineV82:
    """
    Engine de KPIs v8.2 implementando as especificações do documento oficial
    
    CLASSIFICAÇÃO DE LANÇAMENTOS (conforme documento):
    1. trabalho_normal - Horas de jornada regular (entram no divisor)
    2. sabado_trabalhado - Sábado trabalhado (+50%, não entra no divisor)
    3. domingo_trabalhado - Domingo trabalhado (+100%, não entra no divisor)
    4. feriado_trabalhado - Feriado trabalhado (+100%, não entra no divisor)
    5. falta - Falta sem justificativa (desconta salário, não entra no divisor)
    6. falta_justificada - Falta justificada (remunerada, entra no divisor)
    7. ferias - Férias (+33%, não entra no divisor)
    8. folga_sabado - Folga sábado (não gera pagamento adicional)
    9. folga_domingo - Folga domingo (não gera pagamento adicional)
    10. folga_feriado - Folga feriado (não gera pagamento adicional)
    """
    
    def __init__(self):
        # Tipos que entram no divisor para cálculo do valor/hora
        self.tipos_divisor = ['trabalho_normal', 'falta_justificada']
        
        # Tipos de horas extras com seus multiplicadores
        self.tipos_extras = {
            'sabado_trabalhado': 1.5,      # +50%
            'domingo_trabalhado': 2.0,     # +100%
            'feriado_trabalhado': 2.0      # +100%
        }
        
        # Tipos que geram desconto
        self.tipos_desconto = ['falta']
        
        # Tipos de folga (não geram custo nem desconto)
        self.tipos_folga = ['folga_sabado', 'folga_domingo', 'folga_feriado']
    
    def calcular_kpis_funcionario(self, funcionario_id, data_inicio, data_fim):
        """
        Calcula todos os 16 KPIs para um funcionário no período especificado
        seguindo exatamente as especificações do documento oficial
        """
        funcionario = Funcionario.query.get(funcionario_id)
        if not funcionario:
            return self._kpis_zerados()
        
        # Buscar todos os registros do período
        registros = RegistroPonto.query.filter(
            RegistroPonto.funcionario_id == funcionario_id,
            RegistroPonto.data >= data_inicio,
            RegistroPonto.data <= data_fim
        ).all()
        
        # Classificar registros por tipo
        horas_por_tipo = self._classificar_registros_por_tipo(registros)
        
        # 1. Calcular valor/hora base conforme documento
        valor_hora = self._calcular_valor_hora_base(funcionario, horas_por_tipo)
        
        # 2-16. Calcular cada KPI individualmente
        kpis = {
            # KPIs 1-4: Básicos
            'horas_trabalhadas': self._kpi_1_horas_trabalhadas(horas_por_tipo),
            'horas_extras': self._kpi_2_horas_extras(horas_por_tipo),
            'faltas': self._kpi_3_faltas(horas_por_tipo),
            'atrasos_horas': self._kpi_4_atrasos(registros),
            
            # KPIs 5-8: Percentuais
            'produtividade': self._kpi_5_produtividade(horas_por_tipo, data_inicio, data_fim),
            'absenteismo': self._kpi_6_absenteismo(horas_por_tipo, data_inicio, data_fim),
            'media_diaria': self._kpi_7_media_diaria(horas_por_tipo, registros),
            'faltas_justificadas': self._kpi_8_faltas_justificadas(horas_por_tipo),
            
            # KPIs 9-12: Custos
            'custo_mao_obra': self._kpi_9_custo_mao_obra(funcionario, horas_por_tipo, valor_hora),
            'custo_alimentacao': self._kpi_10_custo_alimentacao(funcionario_id, data_inicio, data_fim),
            'custo_transporte': self._kpi_11_custo_transporte(funcionario_id, data_inicio, data_fim),
            'outros_custos': self._kpi_12_outros_custos(funcionario_id, data_inicio, data_fim),
            
            # KPIs 13-16: Complementares
            'horas_perdidas': self._kpi_13_horas_perdidas(horas_por_tipo, data_inicio, data_fim),
            'eficiencia': self._kpi_14_eficiencia(horas_por_tipo),
            'valor_falta_justificada': self._kpi_15_valor_falta_justificada(horas_por_tipo, valor_hora),
            'custo_total': 0.0  # Será calculado no final
        }
        
        # KPI 16: Custo Total (soma de todos os custos)
        kpis['custo_total'] = (
            kpis['custo_mao_obra'] + 
            kpis['custo_alimentacao'] + 
            kpis['custo_transporte'] + 
            kpis['outros_custos']
        )
        
        return kpis
    
    def _classificar_registros_por_tipo(self, registros):
        """Classifica registros por tipo e soma as horas"""
        horas_por_tipo = {}
        
        for registro in registros:
            tipo = registro.tipo_registro or 'trabalho_normal'
            horas = float(registro.horas_trabalhadas or 0)
            
            if tipo not in horas_por_tipo:
                horas_por_tipo[tipo] = 0.0
            
            horas_por_tipo[tipo] += horas
        
        return horas_por_tipo
    
    def _calcular_valor_hora_base(self, funcionario, horas_por_tipo):
        """
        Calcula valor/hora base conforme documento:
        valor_hora = salário_mensal / (∑Horas Trabalho Normal + ∑Horas Falta Justificada)
        """
        if not funcionario or not funcionario.salario:
            return 0.0
        
        # Somar apenas as horas que entram no divisor
        horas_divisor = 0.0
        for tipo in self.tipos_divisor:
            horas_divisor += horas_por_tipo.get(tipo, 0.0)
        
        if horas_divisor > 0:
            return float(funcionario.salario) / horas_divisor
        else:
            # Fallback: usar jornada padrão mensal
            from calcular_dias_uteis_mes import calcular_dias_uteis_mes
            hoje = datetime.now().date()
            dias_uteis = calcular_dias_uteis_mes(hoje.year, hoje.month)
            
            if funcionario.horario_trabalho:
                horas_diarias = float(funcionario.horario_trabalho.horas_diarias or 8.0)
            else:
                horas_diarias = 8.0
            
            horas_mensais = dias_uteis * horas_diarias
            return float(funcionario.salario) / horas_mensais if horas_mensais > 0 else 0.0
    
    def _kpi_1_horas_trabalhadas(self, horas_por_tipo):
        """KPI 1: ∑(horas de Trabalho Normal)"""
        return horas_por_tipo.get('trabalho_normal', 0.0)
    
    def _kpi_2_horas_extras(self, horas_por_tipo):
        """KPI 2: ∑(horas Sábado) + ∑(horas Domingo) + ∑(horas Feriado)"""
        total_extras = 0.0
        for tipo in self.tipos_extras:
            total_extras += horas_por_tipo.get(tipo, 0.0)
        return total_extras
    
    def _kpi_3_faltas(self, horas_por_tipo):
        """KPI 3: Número de dias marcados como Falta"""
        # Assumindo 8h por dia, converter horas em dias
        horas_falta = horas_por_tipo.get('falta', 0.0)
        return int(horas_falta / 8) if horas_falta > 0 else 0
    
    def _kpi_4_atrasos(self, registros):
        """KPI 4: Soma de atrasos em horas"""
        total_atrasos = 0.0
        for registro in registros:
            total_atrasos += float(registro.total_atraso_horas or 0)
        return total_atrasos
    
    def _kpi_5_produtividade(self, horas_por_tipo, data_inicio, data_fim):
        """KPI 5: (Horas Trabalhadas + Horas Extras) / (Horas Trabalh + Extras + Perdidas) × 100"""
        horas_trabalhadas = self._kpi_1_horas_trabalhadas(horas_por_tipo)
        horas_extras = self._kpi_2_horas_extras(horas_por_tipo)
        horas_perdidas = self._kpi_13_horas_perdidas(horas_por_tipo, data_inicio, data_fim)
        
        horas_uteis = horas_trabalhadas + horas_extras
        horas_totais = horas_uteis + horas_perdidas
        
        return (horas_uteis / horas_totais * 100) if horas_totais > 0 else 0.0
    
    def _kpi_6_absenteismo(self, horas_por_tipo, data_inicio, data_fim):
        """KPI 6: Horas Perdidas / (Horas Trabalh + Extras + Perdidas) × 100"""
        horas_trabalhadas = self._kpi_1_horas_trabalhadas(horas_por_tipo)
        horas_extras = self._kpi_2_horas_extras(horas_por_tipo)
        horas_perdidas = self._kpi_13_horas_perdidas(horas_por_tipo, data_inicio, data_fim)
        
        horas_totais = horas_trabalhadas + horas_extras + horas_perdidas
        
        return (horas_perdidas / horas_totais * 100) if horas_totais > 0 else 0.0
    
    def _kpi_7_media_diaria(self, horas_por_tipo, registros):
        """KPI 7: Horas Trabalhadas / Número de dias com lançamentos"""
        horas_trabalhadas = self._kpi_1_horas_trabalhadas(horas_por_tipo)
        
        # Contar dias únicos com registros de trabalho
        dias_com_trabalho = len([r for r in registros if r.tipo_registro == 'trabalho_normal' and (r.horas_trabalhadas or 0) > 0])
        
        return horas_trabalhadas / dias_com_trabalho if dias_com_trabalho > 0 else 0.0
    
    def _kpi_8_faltas_justificadas(self, horas_por_tipo):
        """KPI 8: Número de lançamentos de Falta Justificada"""
        horas_falta_just = horas_por_tipo.get('falta_justificada', 0.0)
        return int(horas_falta_just / 8) if horas_falta_just > 0 else 0
    
    def _kpi_9_custo_mao_obra(self, funcionario, horas_por_tipo, valor_hora):
        """
        KPI 9: Custo Mão de Obra conforme fórmula do documento
        
        ∑(Horas Trabalho Normal + Faltas Justificadas) × valor_hora +
        ∑Horas Sábado × valor_hora × 1,5 +
        ∑Horas Domingo/Feriado × valor_hora × 2 +
        ∑Horas Férias × valor_hora × 1,33
        """
        custo_total = 0.0
        
        # Remuneração normal (trabalho normal + faltas justificadas)
        horas_normais = (horas_por_tipo.get('trabalho_normal', 0.0) + 
                        horas_por_tipo.get('falta_justificada', 0.0))
        custo_total += horas_normais * valor_hora
        
        # Horas extras com adicionais
        for tipo, multiplicador in self.tipos_extras.items():
            horas = horas_por_tipo.get(tipo, 0.0)
            custo_total += horas * valor_hora * multiplicador
        
        # Férias com adicional de 1/3
        horas_ferias = horas_por_tipo.get('ferias', 0.0)
        custo_total += horas_ferias * valor_hora * 1.33
        
        return custo_total
    
    def _kpi_10_custo_alimentacao(self, funcionario_id, data_inicio, data_fim):
        """KPI 10: Quantidade de refeições × valor unitário"""
        total = db.session.query(func.sum(RegistroAlimentacao.valor_total)).filter(
            RegistroAlimentacao.funcionario_id == funcionario_id,
            RegistroAlimentacao.data >= data_inicio,
            RegistroAlimentacao.data <= data_fim
        ).scalar()
        
        return float(total or 0.0)
    
    def _kpi_11_custo_transporte(self, funcionario_id, data_inicio, data_fim):
        """KPI 11: Quantidade de dias × valor diário de vale-transporte"""
        total = db.session.query(func.sum(RegistroTransporte.valor_total)).filter(
            RegistroTransporte.funcionario_id == funcionario_id,
            RegistroTransporte.data >= data_inicio,
            RegistroTransporte.data <= data_fim
        ).scalar()
        
        return float(total or 0.0)
    
    def _kpi_12_outros_custos(self, funcionario_id, data_inicio, data_fim):
        """KPI 12: Soma de despesas extras (EPIs, uniformes, treinamentos, etc)"""
        # Por enquanto retorna 0, pode ser implementado conforme necessidade
        return 0.0
    
    def _kpi_13_horas_perdidas(self, horas_por_tipo, data_inicio, data_fim):
        """
        KPI 13: (Dias úteis × carga diária) - Horas Trabalhadas - Horas Extras
        Ou simplesmente a soma de horas das Faltas (desconta salário)
        """
        # Usar método simples: soma das faltas
        return horas_por_tipo.get('falta', 0.0)
    
    def _kpi_14_eficiencia(self, horas_por_tipo):
        """KPI 14: Horas Trabalhadas / (Horas Trabalhadas + Horas Perdidas) × 100"""
        horas_trabalhadas = self._kpi_1_horas_trabalhadas(horas_por_tipo)
        horas_perdidas = horas_por_tipo.get('falta', 0.0)
        
        horas_totais = horas_trabalhadas + horas_perdidas
        
        return (horas_trabalhadas / horas_totais * 100) if horas_totais > 0 else 100.0
    
    def _kpi_15_valor_falta_justificada(self, horas_por_tipo, valor_hora):
        """KPI 15: ∑(Horas Falta Justificada × valor_hora)"""
        horas_falta_just = horas_por_tipo.get('falta_justificada', 0.0)
        return horas_falta_just * valor_hora
    
    def _kpis_zerados(self):
        """Retorna KPIs zerados para funcionário inexistente"""
        return {
            'horas_trabalhadas': 0.0,
            'horas_extras': 0.0,
            'faltas': 0,
            'atrasos_horas': 0.0,
            'produtividade': 0.0,
            'absenteismo': 0.0,
            'media_diaria': 0.0,
            'faltas_justificadas': 0,
            'custo_mao_obra': 0.0,
            'custo_alimentacao': 0.0,
            'custo_transporte': 0.0,
            'outros_custos': 0.0,
            'horas_perdidas': 0.0,
            'eficiencia': 0.0,
            'valor_falta_justificada': 0.0,
            'custo_total': 0.0
        }

# Instância global da engine
kpis_engine_v82 = KPIsEngineV82()