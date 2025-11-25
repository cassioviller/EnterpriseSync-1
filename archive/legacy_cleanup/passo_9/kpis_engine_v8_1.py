#!/usr/bin/env python3
"""
SIGE v8.1 - ENGINE DE KPIs COMPLETA E CORRIGIDA
Implementa nova lógica de tipos de lançamento e cálculos de custo
"""

from app import app, db
from models import *
from datetime import date, datetime, timedelta
from sqlalchemy import func, and_, or_
import logging

# Configurar logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class TiposLancamento:
    """Definição completa dos tipos de lançamento com suas regras"""
    
    TIPOS = {
        # TIPOS DE TRABALHO
        'trabalho_normal': {
            'nome': 'Trabalho Normal',
            'cor': 'primary',
            'conta_produtividade': True,
            'conta_presenca': True,
            'gera_custo': True,
            'permite_horas_extras': True,
            'adicional_percentual': 0.0,
            'descricao': 'Trabalho em dia útil normal'
        },
        'sabado_trabalhado': {
            'nome': 'Sábado Trabalhado',
            'cor': 'warning',
            'conta_produtividade': False,
            'conta_presenca': True,
            'gera_custo': True,
            'permite_horas_extras': False,  # Todas as horas já são extras
            'adicional_percentual': 50.0,
            'descricao': 'Trabalho em sábado (todas as horas são extras)'
        },
        'domingo_trabalhado': {
            'nome': 'Domingo Trabalhado',
            'cor': 'danger',
            'conta_produtividade': False,
            'conta_presenca': True,
            'gera_custo': True,
            'permite_horas_extras': False,
            'adicional_percentual': 100.0,
            'descricao': 'Trabalho em domingo (todas as horas são extras)'
        },
        'feriado_trabalhado': {
            'nome': 'Feriado Trabalhado',
            'cor': 'info',
            'conta_produtividade': False,
            'conta_presenca': True,
            'gera_custo': True,
            'permite_horas_extras': False,
            'adicional_percentual': 100.0,
            'descricao': 'Trabalho em feriado (todas as horas são extras)'
        },
        
        # TIPOS DE AUSÊNCIA
        'falta': {
            'nome': 'Falta',
            'cor': 'danger',
            'conta_produtividade': True,  # Conta negativamente
            'conta_presenca': False,
            'gera_custo': False,
            'desconta_salario': True,
            'descricao': 'Falta não justificada (desconta do salário)'
        },
        'falta_justificada': {
            'nome': 'Falta Justificada',
            'cor': 'secondary',
            'conta_produtividade': True,  # Conta como dia programado
            'conta_presenca': False,
            'gera_custo': True,  # Tem custo mas não desconta
            'desconta_salario': False,
            'descricao': 'Falta justificada (atestado, etc.)'
        },
        'ferias': {
            'nome': 'Férias',
            'cor': 'success',
            'conta_produtividade': False,
            'conta_presenca': False,
            'gera_custo': True,
            'desconta_salario': False,
            'adicional_percentual': 33.33,  # 1/3 adicional
            'descricao': 'Período de férias'
        },
        
        # TIPOS DE FOLGA
        'sabado_folga': {
            'nome': 'Sábado - Folga',
            'cor': 'light',
            'conta_produtividade': False,
            'conta_presenca': False,
            'gera_custo': False,
            'descricao': 'Sábado de folga (não trabalhado)'
        },
        'domingo_folga': {
            'nome': 'Domingo - Folga',
            'cor': 'light',
            'conta_produtividade': False,
            'conta_presenca': False,
            'gera_custo': False,
            'descricao': 'Domingo de folga (não trabalhado)'
        },
        'feriado_folga': {
            'nome': 'Feriado - Folga',
            'cor': 'info',
            'conta_produtividade': False,
            'conta_presenca': False,
            'gera_custo': False,
            'descricao': 'Feriado não trabalhado'
        }
    }
    
    @classmethod
    def get_tipos_trabalho(cls):
        """Tipos que representam trabalho efetivo"""
        return [k for k, v in cls.TIPOS.items() if v.get('conta_presenca', False)]
    
    @classmethod
    def get_tipos_com_custo(cls):
        """Tipos que geram custo para empresa"""
        return [k for k, v in cls.TIPOS.items() if v.get('gera_custo', False)]
    
    @classmethod
    def get_tipos_produtividade(cls):
        """Tipos que contam para cálculo de produtividade"""
        return [k for k, v in cls.TIPOS.items() if v.get('conta_produtividade', False)]

class CalculadoraCusto:
    """Calculadora de custos baseada em horários específicos e obras"""
    
    def __init__(self):
        self.tipos = TiposLancamento()
    
    def calcular_valor_hora_funcionario(self, funcionario, data_inicio=None, data_fim=None):
        """Calcula valor/hora baseado no horário específico do funcionário e período real"""
        from utils import calcular_valor_hora_periodo
        from datetime import datetime
        
        if funcionario.salario <= 0:
            # Funcionário horista - usar valor do horário
            horario = funcionario.horario_trabalho
            return float(horario.valor_hora) if horario and horario.valor_hora else 15.0
        
        # Funcionário CLT - usar cálculo correto baseado em dias úteis reais
        if not data_inicio:
            hoje = datetime.now().date()
            data_inicio = hoje.replace(day=1)
        if not data_fim:
            data_fim = datetime.now().date()
        
        return calcular_valor_hora_periodo(funcionario, data_inicio, data_fim)
    
    def calcular_custo_registro(self, funcionario, registro):
        """Calcula custo de um registro específico"""
        
        valor_hora = self.calcular_valor_hora_funcionario(funcionario)
        tipo_config = self.tipos.TIPOS.get(registro.tipo_registro, {})
        
        # Tipos sem custo
        if not tipo_config.get('gera_custo', False):
            return 0.0
        
        horas = float(registro.horas_trabalhadas or 0)
        
        if registro.tipo_registro == 'trabalho_normal':
            # Trabalho normal: até horário = normal, acima = 50% extra
            horas_diarias = float(funcionario.horario_trabalho.horas_diarias) if funcionario.horario_trabalho else 8.0
            horas_normais = min(horas, horas_diarias)
            horas_extras = max(horas - horas_diarias, 0)
            
            custo_normal = horas_normais * valor_hora
            custo_extra = horas_extras * valor_hora * 1.5
            
            return custo_normal + custo_extra
        
        elif registro.tipo_registro == 'falta_justificada':
            # Falta justificada: custo normal sem desconto
            horas_diarias = float(funcionario.horario_trabalho.horas_diarias) if funcionario.horario_trabalho else 8.0
            return horas_diarias * valor_hora
        
        elif registro.tipo_registro == 'ferias':
            # Férias: 1/3 adicional
            horas_diarias = float(funcionario.horario_trabalho.horas_diarias) if funcionario.horario_trabalho else 8.0
            return horas_diarias * valor_hora * 1.33
        
        elif registro.tipo_registro in ['sabado_trabalhado']:
            # Sábado: 50% adicional sobre todas as horas
            return horas * valor_hora * 1.5
        
        elif registro.tipo_registro in ['domingo_trabalhado', 'feriado_trabalhado']:
            # Domingo/Feriado: 100% adicional sobre todas as horas
            return horas * valor_hora * 2.0
        
        else:
            # Outros casos: custo normal
            return horas * valor_hora
    
    def calcular_custo_por_obra(self, funcionario_id, obra_id, data_inicio, data_fim):
        """Calcula custo de mão de obra por obra específica"""
        
        funcionario = Funcionario.query.get(funcionario_id)
        if not funcionario:
            return 0.0
        
        # Buscar registros alocados na obra específica
        registros = RegistroPonto.query.filter(
            RegistroPonto.funcionario_id == funcionario_id,
            RegistroPonto.admin_id == funcionario.admin_id,
            RegistroPonto.obra_id == obra_id,
            RegistroPonto.data >= data_inicio,
            RegistroPonto.data <= data_fim
        ).all()
        
        custo_total = 0.0
        for registro in registros:
            custo_total += self.calcular_custo_registro(funcionario, registro)
        
        return custo_total

class KPIsEngineV8_1:
    """Engine de KPIs corrigida para SIGE v8.1"""
    
    def __init__(self):
        self.tipos = TiposLancamento()
        self.calculadora = CalculadoraCusto()
    
    def calcular_kpis_funcionario(self, funcionario_id, data_inicio, data_fim):
        """Calcula todos os KPIs do funcionário com nova lógica"""
        
        funcionario = Funcionario.query.get(funcionario_id)
        if not funcionario:
            return self._kpis_vazios()
        
        # Buscar todos os registros do período
        registros = RegistroPonto.query.filter(
            RegistroPonto.funcionario_id == funcionario_id,
            RegistroPonto.admin_id == funcionario.admin_id,
            RegistroPonto.data >= data_inicio,
            RegistroPonto.data <= data_fim
        ).all()
        
        # Calcular KPIs básicos
        kpis_basicos = self._calcular_kpis_basicos(funcionario, registros)
        
        # Calcular KPIs analíticos
        kpis_analiticos = self._calcular_kpis_analiticos(funcionario, registros, data_inicio, data_fim)
        
        # Calcular KPIs financeiros
        kpis_financeiros = self._calcular_kpis_financeiros(funcionario, registros)
        
        # Combinar todos os KPIs
        kpis_completos = {**kpis_basicos, **kpis_analiticos, **kpis_financeiros}
        
        return kpis_completos
    
    def _calcular_kpis_basicos(self, funcionario, registros):
        """KPIs básicos: horas, faltas, atrasos"""
        
        # 1. HORAS TRABALHADAS (apenas tipos que representam trabalho)
        tipos_trabalho = self.tipos.get_tipos_trabalho()
        horas_trabalhadas = sum([
            float(r.horas_trabalhadas or 0) for r in registros 
            if r.tipo_registro in tipos_trabalho
        ])
        
        # 2. HORAS EXTRAS (lógica específica por tipo)
        horas_extras = 0.0
        for r in registros:
            if r.tipo_registro == 'trabalho_normal':
                # Trabalho normal: extras apenas acima do horário
                horas_diarias = float(funcionario.horario_trabalho.horas_diarias) if funcionario.horario_trabalho else 8.0
                horas_reg = float(r.horas_trabalhadas or 0)
                if horas_reg > horas_diarias:
                    horas_extras += (horas_reg - horas_diarias)
            elif r.tipo_registro in ['sabado_trabalhado', 'domingo_trabalhado', 'feriado_trabalhado']:
                # Tipos especiais: TODAS as horas são extras
                horas_extras += float(r.horas_trabalhadas or 0)
        
        # 3. FALTAS (apenas não justificadas)
        faltas = len([r for r in registros if r.tipo_registro == 'falta'])
        
        # 4. ATRASOS (apenas em trabalho normal)
        total_atrasos_minutos = sum([
            float(r.total_atraso_minutos or 0) for r in registros 
            if r.tipo_registro == 'trabalho_normal'
        ])
        atrasos_horas = total_atrasos_minutos / 60.0
        
        return {
            'horas_trabalhadas': round(horas_trabalhadas, 2),
            'horas_extras': round(horas_extras, 2),
            'faltas': faltas,
            'atrasos': round(atrasos_horas, 2)
        }
    
    def _calcular_kpis_analiticos(self, funcionario, registros, data_inicio, data_fim):
        """KPIs analíticos: produtividade, assiduidade, etc."""
        
        # 5. PRODUTIVIDADE (baseada em dias programados para trabalhar)
        tipos_programados = ['trabalho_normal', 'falta', 'falta_justificada']
        dias_programados = len([r for r in registros if r.tipo_registro in tipos_programados])
        
        produtividade = 0.0
        if dias_programados > 0:
            horas_diarias = float(funcionario.horario_trabalho.horas_diarias) if funcionario.horario_trabalho else 8.0
            horas_esperadas = dias_programados * horas_diarias
            
            # Horas efetivamente trabalhadas (excluindo faltas)
            horas_efetivas = sum([
                float(r.horas_trabalhadas or 0) for r in registros 
                if r.tipo_registro == 'trabalho_normal'
            ])
            
            produtividade = (horas_efetivas / horas_esperadas) * 100 if horas_esperadas > 0 else 0
        
        # 6. ASSIDUIDADE (dias presentes / dias programados)
        tipos_presenca = self.tipos.get_tipos_trabalho()
        dias_presentes = len([r for r in registros if r.tipo_registro in tipos_presenca])
        assiduidade = (dias_presentes / dias_programados * 100) if dias_programados > 0 else 0
        
        # 7. ABSENTEÍSMO (faltas / dias programados)
        faltas = len([r for r in registros if r.tipo_registro == 'falta'])
        absenteismo = (faltas / dias_programados * 100) if dias_programados > 0 else 0
        
        # 8. MÉDIA DIÁRIA (horas trabalhadas / dias presentes)
        media_diaria = 0.0
        if dias_presentes > 0:
            horas_totais = sum([
                float(r.horas_trabalhadas or 0) for r in registros 
                if r.tipo_registro in tipos_presenca
            ])
            media_diaria = horas_totais / dias_presentes
        
        return {
            'produtividade': round(produtividade, 2),
            'assiduidade': round(assiduidade, 2),
            'absenteismo': round(absenteismo, 2),
            'media_diaria': round(media_diaria, 2)
        }
    
    def _calcular_kpis_financeiros(self, funcionario, registros):
        """KPIs financeiros: custo total, por hora, etc."""
        
        # 9. CUSTO TOTAL DE MÃO DE OBRA
        custo_total = 0.0
        for registro in registros:
            custo_total += self.calculadora.calcular_custo_registro(funcionario, registro)
        
        # 10. CUSTO POR HORA TRABALHADA
        horas_totais = sum([
            float(r.horas_trabalhadas or 0) for r in registros 
            if r.tipo_registro in self.tipos.get_tipos_trabalho()
        ])
        custo_por_hora = custo_total / horas_totais if horas_totais > 0 else 0
        
        # 11. VALOR HORA BASE
        valor_hora_base = self.calculadora.calcular_valor_hora_funcionario(funcionario)
        
        return {
            'custo_mao_obra': round(custo_total, 2),
            'custo_por_hora': round(custo_por_hora, 2),
            'valor_hora_base': round(valor_hora_base, 2),
            'custo_horas_extras': round(self._calcular_custo_horas_extras(funcionario, registros), 2)
        }
    
    def _calcular_custo_horas_extras(self, funcionario, registros):
        """Calcula custo específico das horas extras"""
        
        valor_hora = self.calculadora.calcular_valor_hora_funcionario(funcionario)
        custo_extras = 0.0
        
        for r in registros:
            if r.tipo_registro == 'trabalho_normal':
                horas_diarias = float(funcionario.horario_trabalho.horas_diarias) if funcionario.horario_trabalho else 8.0
                horas_reg = float(r.horas_trabalhadas or 0)
                if horas_reg > horas_diarias:
                    horas_extras = horas_reg - horas_diarias
                    custo_extras += horas_extras * valor_hora * 0.5  # Adicional de 50%
            elif r.tipo_registro in ['sabado_trabalhado']:
                # Sábado: adicional de 50% sobre todas as horas
                horas = float(r.horas_trabalhadas or 0)
                custo_extras += horas * valor_hora * 0.5
            elif r.tipo_registro in ['domingo_trabalhado', 'feriado_trabalhado']:
                # Domingo/Feriado: adicional de 100% sobre todas as horas
                horas = float(r.horas_trabalhadas or 0)
                custo_extras += horas * valor_hora
        
        return custo_extras
    
    def _kpis_vazios(self):
        """Retorna estrutura de KPIs zerados"""
        return {
            'horas_trabalhadas': 0.0,
            'horas_extras': 0.0,
            'faltas': 0,
            'atrasos': 0.0,
            'produtividade': 0.0,
            'assiduidade': 0.0,
            'absenteismo': 0.0,
            'media_diaria': 0.0,
            'custo_mao_obra': 0.0,
            'custo_por_hora': 0.0,
            'valor_hora_base': 0.0,
            'custo_horas_extras': 0.0
        }

# Função principal para usar no sistema
def calcular_kpis_v8_1(funcionario_id, data_inicio, data_fim):
    """Função principal para cálculo de KPIs na versão 8.1"""
    engine = KPIsEngineV8_1()
    return engine.calcular_kpis_funcionario(funcionario_id, data_inicio, data_fim)

if __name__ == "__main__":
    with app.app_context():
        print("=" * 80)
        print("TESTANDO ENGINE DE KPIs v8.1")
        print("=" * 80)
        
        # Testar com funcionário existente
        funcionario_teste = Funcionario.query.filter_by(nome='Teste Completo KPIs').first()
        if funcionario_teste:
            kpis = calcular_kpis_v8_1(
                funcionario_teste.id,
                date(2025, 7, 1),
                date(2025, 7, 31)
            )
            
            print(f"FUNCIONÁRIO: {funcionario_teste.nome}")
            print(f"PERÍODO: Julho/2025")
            print("-" * 40)
            
            # KPIs Básicos
            print("KPIs BÁSICOS:")
            print(f"  • Horas Trabalhadas: {kpis['horas_trabalhadas']}h")
            print(f"  • Horas Extras: {kpis['horas_extras']}h")
            print(f"  • Faltas: {kpis['faltas']}")
            print(f"  • Atrasos: {kpis['atrasos']}h")
            
            # KPIs Analíticos
            print("\nKPIs ANALÍTICOS:")
            print(f"  • Produtividade: {kpis['produtividade']}%")
            print(f"  • Assiduidade: {kpis['assiduidade']}%")
            print(f"  • Absenteísmo: {kpis['absenteismo']}%")
            print(f"  • Média Diária: {kpis['media_diaria']}h")
            
            # KPIs Financeiros
            print("\nKPIs FINANCEIROS:")
            print(f"  • Custo Mão de Obra: R$ {kpis['custo_mao_obra']:.2f}")
            print(f"  • Custo por Hora: R$ {kpis['custo_por_hora']:.2f}")
            print(f"  • Valor Hora Base: R$ {kpis['valor_hora_base']:.2f}")
            print(f"  • Custo Horas Extras: R$ {kpis['custo_horas_extras']:.2f}")
            
        else:
            print("❌ Funcionário teste não encontrado")
        
        print("\n✅ Teste concluído!")