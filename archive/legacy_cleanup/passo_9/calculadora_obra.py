# CALCULADORA DE OBRA - SIGE v8.0
# Classe centralizada para cálculos unificados e precisos

from datetime import datetime, timedelta
from sqlalchemy import func
from models import (
    Obra, RegistroPonto, Funcionario, HorarioTrabalho, 
    CustoVeiculo, RegistroAlimentacao, CustoObra, OutroCusto
)
from utils import calcular_valor_hora_periodo

class CalculadoraObra:
    """
    Classe centralizada para todos os cálculos relacionados à obra
    Garante consistência e elimina discrepâncias nos cálculos
    """
    
    def __init__(self, obra_id, data_inicio=None, data_fim=None):
        self.obra_id = obra_id
        self.obra = Obra.query.get(obra_id)
        self.data_inicio = data_inicio or self.obra.data_inicio if self.obra else datetime.now().date().replace(day=1)
        self.data_fim = data_fim or datetime.now().date()
    
    def calcular_dias_uteis_trabalhados(self, funcionario_id):
        """
        Calcula dias úteis trabalhados baseado no horário do funcionário
        Para seg-sex 7h12-17h = 23 dias úteis em média por mês
        """
        funcionario = Funcionario.query.get(funcionario_id)
        if not funcionario or not funcionario.horario_trabalho:
            return 22  # padrão
        
        horario = funcionario.horario_trabalho
        
        # Contar dias da semana baseado no horário
        total_dias = (self.data_fim - self.data_inicio).days + 1
        
        # Se trabalha seg-sex (padrão baseado em dias_semana), calcular apenas dias úteis
        dias_semana_list = horario.dias_semana.split(',') if horario.dias_semana else []
        trabalha_seg_sex = '1' in dias_semana_list and '5' in dias_semana_list and '6' not in dias_semana_list and '7' not in dias_semana_list
        
        if trabalha_seg_sex:
            # Aproximadamente 23 dias úteis por mês (considerando feriados)
            meses = total_dias / 30.44  # média de dias por mês
            return int(23 * meses)
        
        # Para outros horários, calcular baseado nos dias específicos
        dias_trabalhados = 0
        current_date = self.data_inicio
        
        while current_date <= self.data_fim:
            weekday = current_date.weekday()  # 0=segunda, 6=domingo
            dia_semana_str = str(weekday + 1)  # Converter para 1=segunda, 7=domingo
            
            if dia_semana_str in dias_semana_list:
                dias_trabalhados += 1
            
            current_date += timedelta(days=1)
        
        return dias_trabalhados
    
    def calcular_valor_hora_funcionario(self, funcionario_id):
        """
        Calcula valor/hora baseado no horário específico do funcionário
        Exemplo: salário R$ 2.400 ÷ (8h48 × 23 dias) = R$ 11,83/hora
        """
        funcionario = Funcionario.query.get(funcionario_id)
        if not funcionario or not funcionario.salario:
            return 0
        
        horario = funcionario.horario_trabalho
        if not horario:
            # Usar cálculo baseado no período real
            return calcular_valor_hora_periodo(funcionario, self.data_inicio, self.data_fim)
        
        # Calcular baseado no horário real
        horas_diarias = horario.horas_diarias
        dias_uteis_mes = self.calcular_dias_uteis_trabalhados(funcionario_id)
        
        # Para período específico, ajustar proporcionalmente
        if self.data_inicio and self.data_fim:
            dias_periodo = (self.data_fim - self.data_inicio).days + 1
            if dias_periodo < 28:  # período menor que um mês
                dias_uteis_periodo = self.calcular_dias_uteis_trabalhados(funcionario_id)
                horas_totais_periodo = horas_diarias * dias_uteis_periodo
                return funcionario.salario * (dias_periodo / 30.44) / horas_totais_periodo if horas_totais_periodo > 0 else 0
        
        # Cálculo mensal normal
        horas_mensais = horas_diarias * dias_uteis_mes
        return funcionario.salario / horas_mensais if horas_mensais > 0 else 0
    
    def calcular_custo_mao_obra(self):
        """
        Cálculo unificado de custo de mão de obra com precisão por horário
        """
        # Buscar todos os registros de ponto no período
        registros = db.session.query(
            RegistroPonto.funcionario_id,
            func.sum(RegistroPonto.horas_trabalhadas).label('total_horas'),
            func.sum(RegistroPonto.horas_extras).label('total_extras'),
            Funcionario.nome,
            Funcionario.salario,
            HorarioTrabalho.horas_diarias
        ).select_from(
            RegistroPonto
        ).join(
            Funcionario, RegistroPonto.funcionario_id == Funcionario.id
        ).join(
            HorarioTrabalho, Funcionario.horario_trabalho_id == HorarioTrabalho.id
        ).filter(
            RegistroPonto.obra_id == self.obra_id,
            RegistroPonto.data.between(self.data_inicio, self.data_fim)
        ).group_by(
            RegistroPonto.funcionario_id,
            Funcionario.nome,
            Funcionario.salario,
            HorarioTrabalho.horas_diarias
        ).all()
        
        custo_total = 0
        detalhamento = []
        
        for registro in registros:
            # Calcular valor/hora baseado no horário específico
            valor_hora_normal = self.calcular_valor_hora_funcionario(registro.funcionario_id)
            
            # Custo horas normais
            horas_normais = (registro.total_horas or 0) - (registro.total_extras or 0)
            custo_normal = horas_normais * valor_hora_normal
            
            # Custo horas extras (percentuais diferenciados)
            custo_extras = self.calcular_custo_horas_extras(
                registro.funcionario_id,
                registro.total_extras or 0,
                valor_hora_normal
            )
            
            custo_funcionario = custo_normal + custo_extras
            custo_total += custo_funcionario
            
            detalhamento.append({
                'funcionario_id': registro.funcionario_id,
                'nome': registro.nome,
                'horas_normais': horas_normais,
                'horas_extras': registro.total_extras or 0,
                'valor_hora': valor_hora_normal,
                'custo_normal': custo_normal,
                'custo_extras': custo_extras,
                'custo_total': custo_funcionario
            })
        
        return {
            'custo_total': custo_total,
            'detalhamento': detalhamento
        }
    
    def calcular_custo_horas_extras(self, funcionario_id, total_horas_extras, valor_hora_normal):
        """
        Calcula custo de horas extras considerando tipo de registro
        """
        if total_horas_extras <= 0:
            return 0
        
        # Buscar registros de horas extras por tipo
        extras_por_tipo = db.session.query(
            RegistroPonto.tipo_registro,
            func.sum(RegistroPonto.horas_extras).label('horas')
        ).filter(
            RegistroPonto.funcionario_id == funcionario_id,
            RegistroPonto.obra_id == self.obra_id,
            RegistroPonto.data.between(self.data_inicio, self.data_fim),
            RegistroPonto.horas_extras > 0
        ).group_by(RegistroPonto.tipo_registro).all()
        
        custo_extras = 0
        
        for tipo_registro, horas in extras_por_tipo:
            if tipo_registro in ['trabalho_normal', 'meio_periodo']:
                # Horas extras em dias normais: 50% adicional
                custo_extras += horas * valor_hora_normal * 1.5
            elif tipo_registro == 'sabado_horas_extras':
                # Sábado: 50% adicional
                custo_extras += horas * valor_hora_normal * 1.5
            elif tipo_registro in ['domingo_horas_extras', 'feriado_trabalhado']:
                # Domingo/Feriado: 100% adicional
                custo_extras += horas * valor_hora_normal * 2.0
            else:
                # Outros tipos: padrão 50%
                custo_extras += horas * valor_hora_normal * 1.5
        
        # Se não encontrou tipos específicos, usar cálculo geral
        if custo_extras == 0 and total_horas_extras > 0:
            custo_extras = total_horas_extras * valor_hora_normal * 1.5
        
        return custo_extras
    
    def calcular_custo_transporte(self):
        """
        Cálculo unificado de custos de transporte
        """
        custos = db.session.query(
            func.sum(CustoVeiculo.valor).label('total')
        ).filter(
            CustoVeiculo.obra_id == self.obra_id,
            CustoVeiculo.data_custo.between(self.data_inicio, self.data_fim)
        ).scalar() or 0
        
        return custos
    
    def calcular_custo_alimentacao(self):
        """
        Cálculo unificado de custos de alimentação
        """
        custos = db.session.query(
            func.sum(RegistroAlimentacao.valor).label('total')
        ).filter(
            RegistroAlimentacao.obra_id == self.obra_id,
            RegistroAlimentacao.data.between(self.data_inicio, self.data_fim)
        ).scalar() or 0
        
        return custos
    
    def calcular_outros_custos(self):
        """
        Cálculo unificado de outros custos (materiais, equipamentos, etc.)
        """
        custos_obra = db.session.query(
            func.sum(CustoObra.valor).label('total')
        ).filter(
            CustoObra.obra_id == self.obra_id,
            CustoObra.data.between(self.data_inicio, self.data_fim)
        ).scalar() or 0
        
        custos_outros = db.session.query(
            func.sum(OutroCusto.valor).label('total')
        ).filter(
            OutroCusto.obra_id == self.obra_id,
            OutroCusto.data.between(self.data_inicio, self.data_fim)
        ).scalar() or 0
        
        return custos_obra + custos_outros
    
    def calcular_custo_total(self):
        """
        Método principal - cálculo completo e unificado
        """
        mao_obra = self.calcular_custo_mao_obra()
        transporte = self.calcular_custo_transporte()
        alimentacao = self.calcular_custo_alimentacao()
        outros = self.calcular_outros_custos()
        
        total = mao_obra['custo_total'] + transporte + alimentacao + outros
        
        return {
            'mao_obra': mao_obra['custo_total'],
            'transporte': transporte,
            'alimentacao': alimentacao,
            'outros': outros,
            'total': total,
            'detalhamento_mao_obra': mao_obra['detalhamento']
        }
    
    def obter_estatisticas_periodo(self):
        """
        Estatísticas gerais do período para contexto
        """
        total_funcionarios = db.session.query(
            func.count(func.distinct(RegistroPonto.funcionario_id))
        ).filter(
            RegistroPonto.obra_id == self.obra_id,
            RegistroPonto.data.between(self.data_inicio, self.data_fim)
        ).scalar() or 0
        
        total_registros = db.session.query(
            func.count(RegistroPonto.id)
        ).filter(
            RegistroPonto.obra_id == self.obra_id,
            RegistroPonto.data.between(self.data_inicio, self.data_fim)
        ).scalar() or 0
        
        return {
            'total_funcionarios': total_funcionarios,
            'total_registros': total_registros,
            'periodo_inicio': self.data_inicio,
            'periodo_fim': self.data_fim,
            'dias_periodo': (self.data_fim - self.data_inicio).days + 1
        }