#!/usr/bin/env python3
"""
ENGINE DE CÁLCULO DE KPIs CORRIGIDO - SIGE v8.1
Sistema Integrado de Gestão Empresarial - Estruturas do Vale

CORREÇÕES IMPLEMENTADAS:
1. Tipos de registro padronizados e claros
2. Lógica de custo corrigida (faltas não justificadas = custo ZERO)
3. Diferenciação entre sábados/domingos trabalhados vs folga
4. KPIs consistentes entre cards e detalhes
5. Validações cruzadas para garantir precisão

Data: 01 de Agosto de 2025
"""

from datetime import date, datetime, time, timedelta
from app import db
from models import (
    Funcionario, RegistroPonto, RegistroAlimentacao, 
    Ocorrencia, TipoOcorrencia, CalendarioUtil, HorarioTrabalho
)
from sqlalchemy import func, extract, and_, or_
import logging

class TimeRecordType:
    """Tipos padronizados de lançamento de ponto"""
    # DIAS TRABALHADOS (COM CUSTO)
    TRABALHO_NORMAL = 'trabalho_normal'          # Segunda a Sexta normal
    TRABALHADO = 'trabalhado'                    # Alias para compatibilidade
    SABADO_TRABALHADO = 'sabado_trabalhado'      # Sábado com trabalho (50% extra)
    SABADO_HORAS_EXTRAS = 'sabado_horas_extras'  # Alias para compatibilidade
    DOMINGO_TRABALHADO = 'domingo_trabalhado'    # Domingo com trabalho (100% extra)
    DOMINGO_HORAS_EXTRAS = 'domingo_horas_extras' # Alias para compatibilidade
    FERIADO_TRABALHADO = 'feriado_trabalhado'    # Feriado com trabalho (100% extra)
    MEIO_PERIODO = 'meio_periodo'                # Meio período - CUSTO PROPORCIONAL
    
    # DIAS NÃO TRABALHADOS (SEM CUSTO)
    SABADO_FOLGA = 'sabado_folga'                # Sábado de folga - SEM CUSTO
    DOMINGO_FOLGA = 'domingo_folga'              # Domingo de folga - SEM CUSTO
    FERIADO_FOLGA = 'feriado_folga'              # Feriado de folga - SEM CUSTO
    
    # AUSÊNCIAS
    FALTA = 'falta'                              # Falta sem justificativa - SEM CUSTO
    FALTA_INJUSTIFICADA = 'falta_injustificada'  # Alias para compatibilidade
    FALTA_JUSTIFICADA = 'falta_justificada'      # Falta justificada - COM CUSTO
    ATESTADO_MEDICO = 'atestado_medico'          # Atestado médico - COM CUSTO
    
    # BENEFÍCIOS
    FERIAS = 'ferias'                            # Férias - COM CUSTO (1/3 adicional)
    LICENCA = 'licenca'                          # Licença - COM CUSTO
    
    # GRUPOS DE CLASSIFICAÇÃO
    TIPOS_COM_CUSTO = [
        TRABALHO_NORMAL, TRABALHADO, SABADO_TRABALHADO, SABADO_HORAS_EXTRAS,
        DOMINGO_TRABALHADO, DOMINGO_HORAS_EXTRAS, FERIADO_TRABALHADO,
        MEIO_PERIODO, FALTA_JUSTIFICADA, ATESTADO_MEDICO, FERIAS, LICENCA
    ]
    
    TIPOS_SEM_CUSTO = [
        SABADO_FOLGA, DOMINGO_FOLGA, FERIADO_FOLGA, FALTA, FALTA_INJUSTIFICADA
    ]
    
    TIPOS_TRABALHADOS = [
        TRABALHO_NORMAL, TRABALHADO, SABADO_TRABALHADO, SABADO_HORAS_EXTRAS,
        DOMINGO_TRABALHADO, DOMINGO_HORAS_EXTRAS, FERIADO_TRABALHADO, MEIO_PERIODO
    ]
    
    TIPOS_AUSENCIAS = [
        FALTA, FALTA_INJUSTIFICADA, FALTA_JUSTIFICADA, ATESTADO_MEDICO
    ]

class CorrectedKPIService:
    """Serviço corrigido para cálculo de KPIs"""
    
    def __init__(self):
        self.hoje = date.today()
        self.logger = logging.getLogger(__name__)
    
    def calcular_kpis_funcionario(self, funcionario_id, data_inicio=None, data_fim=None):
        """
        Calcula todos os KPIs de um funcionário no período especificado
        COM LÓGICA CORRIGIDA para consistência total
        """
        if not data_inicio:
            data_inicio = self.hoje.replace(day=1)
        if not data_fim:
            data_fim = self.hoje
            
        funcionario = Funcionario.query.get(funcionario_id)
        if not funcionario:
            return None
        
        # Buscar todos os registros do período
        registros = RegistroPonto.query.filter(
            RegistroPonto.funcionario_id == funcionario_id,
            RegistroPonto.data >= data_inicio,
            RegistroPonto.data <= data_fim
        ).all()
        
        # Calcular KPIs com validação cruzada
        kpis = self._calcular_kpis_base(funcionario, registros, data_inicio, data_fim)
        
        # Validar consistência
        self._validar_consistencia_kpis(kpis, registros)
        
        return kpis
    
    def _calcular_kpis_base(self, funcionario, registros, data_inicio, data_fim):
        """Cálculo base dos KPIs com lógica corrigida"""
        
        # Inicializar contadores
        horas_trabalhadas = 0.0
        horas_extras = 0.0
        custo_total = 0.0
        faltas_injustificadas = 0
        faltas_justificadas = 0
        dias_trabalhados = 0
        total_atrasos_horas = 0.0
        
        # Valor base por hora
        salario_mensal = float(funcionario.salario or 0)
        valor_hora_base = salario_mensal / 22 / 8  # 22 dias úteis, 8h por dia
        
        # Processar cada registro
        for registro in registros:
            tipo = registro.tipo_registro or 'trabalhado'
            
            # Normalizar tipos para compatibilidade
            if tipo in ['trabalhado', 'trabalho_normal']:
                tipo = TimeRecordType.TRABALHO_NORMAL
            elif tipo in ['sabado_horas_extras', 'sabado_trabalhado']:
                tipo = TimeRecordType.SABADO_TRABALHADO
            elif tipo in ['domingo_horas_extras', 'domingo_trabalhado']:
                tipo = TimeRecordType.DOMINGO_TRABALHADO
            
            # CONTABILIZAR HORAS TRABALHADAS
            if tipo in TimeRecordType.TIPOS_TRABALHADOS:
                horas_reg = float(registro.horas_trabalhadas or 0)
                extras_reg = float(registro.horas_extras or 0)
                
                horas_trabalhadas += horas_reg
                horas_extras += extras_reg
                dias_trabalhados += 1
                
                # CALCULAR CUSTO POR TIPO
                if tipo == TimeRecordType.TRABALHO_NORMAL:
                    # Dia normal: até 8h normal, resto com 50% extra
                    horas_normais = min(horas_reg, 8.0)
                    horas_extras_calculadas = max(horas_reg - 8.0, 0)
                    
                    custo_reg = (horas_normais * valor_hora_base) + \
                               (horas_extras_calculadas * valor_hora_base * 1.5)
                    custo_total += custo_reg
                    
                elif tipo == TimeRecordType.SABADO_TRABALHADO:
                    # Sábado: 50% adicional
                    custo_total += horas_reg * valor_hora_base * 1.5
                    
                elif tipo in [TimeRecordType.DOMINGO_TRABALHADO, TimeRecordType.FERIADO_TRABALHADO]:
                    # Domingo/Feriado: 100% adicional
                    custo_total += horas_reg * valor_hora_base * 2.0
                    
                elif tipo == TimeRecordType.MEIO_PERIODO:
                    # Meio período: proporcional
                    custo_total += horas_reg * valor_hora_base
            
            # CONTABILIZAR AUSÊNCIAS
            elif tipo in TimeRecordType.TIPOS_AUSENCIAS:
                if tipo in ['falta', 'falta_injustificada']:
                    faltas_injustificadas += 1
                    # FALTAS INJUSTIFICADAS NÃO TÊM CUSTO
                elif tipo in ['falta_justificada', 'atestado_medico']:
                    faltas_justificadas += 1
                    # FALTAS JUSTIFICADAS TÊM CUSTO (8h normais)
                    custo_total += 8.0 * valor_hora_base
            
            # CONTABILIZAR ATRASOS (apenas em dias trabalhados)
            if tipo in TimeRecordType.TIPOS_TRABALHADOS and tipo not in [
                TimeRecordType.SABADO_TRABALHADO, TimeRecordType.DOMINGO_TRABALHADO
            ]:
                total_atrasos_horas += float(registro.total_atraso_horas or 0)
        
        # Calcular custos adicionais
        custo_alimentacao = self._calcular_custo_alimentacao(funcionario.id, data_inicio, data_fim)
        custo_transporte = self._calcular_custo_transporte(funcionario.id, data_inicio, data_fim)
        outros_custos = self._calcular_outros_custos(funcionario.id, data_inicio, data_fim)
        
        # Calcular métricas derivadas
        total_registros = len(registros)
        dias_presenca = dias_trabalhados + faltas_justificadas
        
        # Produtividade: baseada em dias efetivamente trabalhados
        horas_esperadas = dias_trabalhados * 8.0
        produtividade = (horas_trabalhadas / horas_esperadas * 100) if horas_esperadas > 0 else 0
        
        # Absenteísmo: apenas faltas injustificadas
        absenteismo = (faltas_injustificadas / total_registros * 100) if total_registros > 0 else 0
        
        # Média diária
        media_diaria = (horas_trabalhadas / dias_trabalhados) if dias_trabalhados > 0 else 0
        
        # Horas perdidas
        horas_perdidas = (faltas_injustificadas * 8.0) + total_atrasos_horas
        
        # Eficiência
        eficiencia = max(0, 100 - (horas_perdidas / (horas_trabalhadas + horas_perdidas) * 100)) if (horas_trabalhadas + horas_perdidas) > 0 else 0
        
        # Valor das faltas justificadas
        valor_falta_justificada = faltas_justificadas * 8.0 * valor_hora_base
        
        return {
            # Primeira linha (4 indicadores)
            'horas_trabalhadas': round(horas_trabalhadas, 1),
            'horas_extras': round(horas_extras, 1),
            'faltas': faltas_injustificadas,
            'atrasos_horas': round(total_atrasos_horas, 1),
            
            # Segunda linha (4 indicadores)
            'produtividade': round(produtividade, 1),
            'absenteismo': round(absenteismo, 1),
            'media_diaria': round(media_diaria, 1),
            'faltas_justificadas': faltas_justificadas,
            
            # Terceira linha (4 indicadores)
            'custo_mao_obra': round(custo_total, 2),
            'custo_alimentacao': round(custo_alimentacao, 2),
            'custo_transporte': round(custo_transporte, 2),
            'outros_custos': round(outros_custos, 2),
            
            # Quarta linha (3 indicadores)
            'horas_perdidas': round(horas_perdidas, 1),
            'eficiencia': round(eficiencia, 1),
            'valor_falta_justificada': round(valor_falta_justificada, 2),
            
            # Informações auxiliares
            'periodo': {
                'inicio': data_inicio,
                'fim': data_fim,
                'dias_uteis': total_registros,
                'dias_com_lancamento': total_registros
            },
            'funcionario': {
                'id': funcionario.id,
                'codigo': funcionario.codigo,
                'nome': funcionario.nome,
                'salario': float(funcionario.salario or 0)
            }
        }
    
    def _calcular_custo_alimentacao(self, funcionario_id, data_inicio, data_fim):
        """Calcula custo total com alimentação no período"""
        resultado = db.session.query(func.coalesce(func.sum(RegistroAlimentacao.valor), 0)).filter(
            RegistroAlimentacao.funcionario_id == funcionario_id,
            RegistroAlimentacao.data >= data_inicio,
            RegistroAlimentacao.data <= data_fim
        ).scalar()
        return float(resultado or 0)
    
    def _calcular_custo_transporte(self, funcionario_id, data_inicio, data_fim):
        """Calcula custos de transporte (implementar conforme necessário)"""
        # TODO: Implementar quando houver tabela de custos de transporte
        return 0.0
    
    def _calcular_outros_custos(self, funcionario_id, data_inicio, data_fim):
        """Calcula outros custos do funcionário"""
        try:
            from models import OutroCusto
            resultado = db.session.query(func.coalesce(func.sum(OutroCusto.valor), 0)).filter(
                OutroCusto.funcionario_id == funcionario_id,
                OutroCusto.data >= data_inicio,
                OutroCusto.data <= data_fim
            ).scalar()
            return float(resultado or 0)
        except:
            return 0.0
    
    def _validar_consistencia_kpis(self, kpis, registros):
        """Valida consistência dos KPIs calculados"""
        total_horas_registros = sum(float(r.horas_trabalhadas or 0) for r in registros)
        
        if abs(kpis['horas_trabalhadas'] - total_horas_registros) > 0.1:
            self.logger.warning(f"Inconsistência detectada em horas trabalhadas: "
                              f"KPI={kpis['horas_trabalhadas']}, "
                              f"Registros={total_horas_registros}")
        
        return True

class KPIValidationService:
    """Serviço para validação cruzada de KPIs"""
    
    def validate_employee_kpis(self, employee_id, start_date, end_date):
        """Valida KPIs de um funcionário comparando diferentes métodos"""
        
        # Método 1: Engine atual
        from kpis_engine import KPIsEngine
        engine_atual = KPIsEngine()
        kpis_atual = engine_atual.calcular_kpis_funcionario(employee_id, start_date, end_date)
        
        # Método 2: Engine corrigido
        engine_corrigido = CorrectedKPIService()
        kpis_corrigido = engine_corrigido.calcular_kpis_funcionario(employee_id, start_date, end_date)
        
        # Comparar resultados
        diferencas = {}
        for key in kpis_atual.keys():
            if key in kpis_corrigido and isinstance(kpis_atual[key], (int, float)):
                diff = abs(float(kpis_atual[key]) - float(kpis_corrigido[key]))
                if diff > 0.01:
                    diferencas[key] = {
                        'atual': kpis_atual[key],
                        'corrigido': kpis_corrigido[key],
                        'diferenca': diff
                    }
        
        return {
            'is_consistent': len(diferencas) == 0,
            'diferencas': diferencas,
            'kpis_atual': kpis_atual,
            'kpis_corrigido': kpis_corrigido
        }

# Manter compatibilidade com engine atual
class KPIsEngineCorrigido(CorrectedKPIService):
    """Alias para manter compatibilidade"""
    pass