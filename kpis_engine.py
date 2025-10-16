from models import db
#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
ENGINE DE CÁLCULO DE KPIs - SIGE v3.0
Sistema Integrado de Gestão Empresarial - Estruturas do Vale

Implementa as regras de negócio específicas para cálculo correto de KPIs
conforme especificação técnica v3.0.

Regras fundamentais:
1. Faltas = dias úteis sem registro de entrada
2. Atrasos = entrada tardia + saída antecipada (em HORAS)
3. Horas Perdidas = Faltas (em horas) + Atrasos (em horas)
4. Custo = Tempo trabalhado + Faltas justificadas

Data: 04 de Julho de 2025
"""

from datetime import date, datetime, time, timedelta
    Funcionario, RegistroPonto, RegistroAlimentacao, 
    Ocorrencia, TipoOcorrencia, CalendarioUtil, HorarioTrabalho
)
from sqlalchemy import func, extract, and_, or_


class CalculadoraKPI:
    """Engine principal para cálculo de todos os KPIs"""
    
    
def calcular_valor_hora_funcionario(funcionario, data_referencia):
    """
    Calcular valor hora do funcionário baseado em dias úteis reais do mês
    
    Args:
        funcionario: Instância do modelo Funcionario
        data_referencia: datetime.date do mês de referência
    
    Returns:
        float: Valor da hora normal do funcionário
    """
    from calendar import monthrange
    
    if not funcionario.salario:
        return 0.0
    
    # Calcular dias úteis reais do mês
    ano = data_referencia.year
    mes = data_referencia.month
    
    dias_uteis = 0
    primeiro_dia, ultimo_dia = monthrange(ano, mes)
    
    for dia in range(1, ultimo_dia + 1):
        data_check = data_referencia.replace(day=dia)
        # 0=segunda, 1=terça, ..., 6=domingo
        if data_check.weekday() < 5:  # Segunda a sexta
            dias_uteis += 1
    
    # Usar horário específico do funcionário
    if funcionario.horario_trabalho and funcionario.horario_trabalho.horas_diarias:
        horas_diarias = funcionario.horario_trabalho.horas_diarias
    else:
        horas_diarias = 8.8  # Padrão baseado no horário Carlos Alberto
    
    # Horas mensais = horas/dia × dias úteis do mês
    horas_mensais = horas_diarias * dias_uteis
    
    return funcionario.salario / horas_mensais if horas_mensais > 0 else 0.0

def calcular_valor_horas_extras_funcionario(funcionario, horas_extras, tipo_registro, data_referencia):
    """
    Calcular valor das horas extras conforme legislação brasileira
    
    Args:
        funcionario: Instância do modelo Funcionario
        horas_extras: Quantidade de horas extras (float)
        tipo_registro: Tipo do registro ('domingo_trabalhado', etc.)
        data_referencia: datetime.date do mês de referência
    
    Returns:
        float: Valor monetário das horas extras
    """
    if not horas_extras or horas_extras <= 0:
        return 0.0
    
    valor_hora_normal = calcular_valor_hora_funcionario(funcionario, data_referencia)
    
    if valor_hora_normal <= 0:
        return 0.0
    
    # Multiplicador conforme legislação brasileira (CLT)
    if tipo_registro in ['domingo_trabalhado', 'domingo_horas_extras', 'feriado_trabalhado']:
        multiplicador = 2.0  # 100% adicional
    else:
        multiplicador = 1.5  # 50% adicional padrão
    
    return horas_extras * valor_hora_normal * multiplicador


class CalculadoraKPI:
    """Engine principal para cálculo de todos os KPIs"""
    
    def __init__(self):
        self.hoje = date.today()
    
    def calcular_kpis_funcionario(self, funcionario_id, data_inicio=None, data_fim=None):
        """
        Calcula todos os 16 KPIs seguindo as especificações do documento oficial
        "PROMPT DE REVISÃO – CÁLCULO DE KPIs E CUSTOS DE RH"
        
        Layout 4-4-4-4 com tipos padronizados v8.2
        """
        if not data_inicio:
            data_inicio = self.hoje.replace(day=1)  # Primeiro dia do mês
        if not data_fim:
            data_fim = self.hoje
            
        funcionario = Funcionario.query.get(funcionario_id)
        if not funcionario:
            return None
        
        # Layout 4-4-4-3: Primeira linha (4 indicadores)
        horas_trabalhadas = self._calcular_horas_trabalhadas(funcionario_id, data_inicio, data_fim)
        horas_extras = self._calcular_horas_extras(funcionario_id, data_inicio, data_fim)
        faltas = self._calcular_faltas(funcionario_id, data_inicio, data_fim)
        atrasos_horas = self._calcular_atrasos_horas(funcionario_id, data_inicio, data_fim)
        
        # Layout 4-4-4-3: Segunda linha (4 indicadores)
        produtividade = self._calcular_produtividade(funcionario_id, data_inicio, data_fim)
        absenteismo = self._calcular_absenteismo(funcionario_id, data_inicio, data_fim)
        media_diaria = self._calcular_media_horas_diarias(funcionario_id, data_inicio, data_fim)
        faltas_justificadas = self._calcular_faltas_justificadas(funcionario_id, data_inicio, data_fim)
        
        # Layout 4-4-4-3: Terceira linha (4 indicadores)
        custo_mao_obra = self._calcular_custo_mensal(funcionario_id, data_inicio, data_fim)
        custo_alimentacao = self._calcular_custo_alimentacao(funcionario_id, data_inicio, data_fim)
        custo_transporte = self._calcular_custo_transporte(funcionario_id, data_inicio, data_fim)
        outros_custos = self._calcular_outros_custos(funcionario_id, data_inicio, data_fim)
        
        # Layout 4-4-4-4: Quarta linha (4 indicadores)
        horas_perdidas = self._calcular_horas_perdidas(funcionario_id, data_inicio, data_fim)
        # Calcular valor em R$ das horas extras
        valor_horas_extras = self._calcular_valor_horas_extras(funcionario_id, data_inicio, data_fim)
        valor_falta_justificada = self._calcular_valor_falta_justificada(funcionario_id, data_inicio, data_fim)
        custo_total = self._calcular_custo_total(funcionario_id, data_inicio, data_fim)
        
        return {
            # Primeira linha (4 indicadores)
            'horas_trabalhadas': round(horas_trabalhadas, 1),
            'horas_extras': round(horas_extras, 1),
            'faltas': faltas,
            'atrasos_horas': round(atrasos_horas, 1),
            
            # Segunda linha (4 indicadores)
            'produtividade': round(produtividade, 1),
            'absenteismo': round(absenteismo, 1),
            'media_diaria': round(media_diaria, 1),
            'faltas_justificadas': faltas_justificadas,
            
            # Terceira linha (4 indicadores)
            'custo_mao_obra': round(custo_mao_obra, 2),
            'custo_alimentacao': round(custo_alimentacao, 2),
            'custo_transporte': round(custo_transporte, 2),
            'outros_custos': round(outros_custos, 2),
            
            # Quarta linha (4 indicadores)
            'horas_perdidas': round(horas_perdidas, 1),
            'eficiencia': round(valor_horas_extras, 2),  # Agora mostra valor R$ das horas extras
            'valor_falta_justificada': round(valor_falta_justificada, 2),
            'custo_total': round(custo_total, 2),
            
            # Dados auxiliares
            'periodo': {
                'inicio': data_inicio,
                'fim': data_fim,
                'dias_uteis': self._calcular_dias_uteis(data_inicio, data_fim),
                'dias_com_lancamento': self._calcular_dias_com_lancamento(funcionario_id, data_inicio, data_fim)
            },
            'funcionario': {
                'id': funcionario.id,
                'codigo': funcionario.codigo,
                'nome': funcionario.nome,
                'salario': funcionario.salario or 0
            }
        }
    
    def _calcular_horas_trabalhadas(self, funcionario_id, data_inicio, data_fim):
        """1. Horas Trabalhadas: Soma das horas efetivamente trabalhadas"""
        funcionario = Funcionario.query.get(funcionario_id)
        if not funcionario:
            return 0.0
        
        total = db.session.query(func.sum(RegistroPonto.horas_trabalhadas)).filter(
            RegistroPonto.funcionario_id == funcionario_id,
            RegistroPonto.admin_id == funcionario.admin_id,
            RegistroPonto.data >= data_inicio,
            RegistroPonto.data <= data_fim,
            RegistroPonto.horas_trabalhadas.isnot(None)
        ).scalar()
        
        return total or 0.0
    
    def _calcular_horas_extras(self, funcionario_id, data_inicio, data_fim):
        """2. Horas Extras: Baseado em horário padrão (07:12-17:00)"""
        
        funcionario = Funcionario.query.get(funcionario_id)
        if not funcionario:
            return 0.0
        
        # Buscar registros do período com horários válidos
        registros = RegistroPonto.query.filter(
            RegistroPonto.funcionario_id == funcionario_id,
            RegistroPonto.admin_id == funcionario.admin_id,
            RegistroPonto.data >= data_inicio,
            RegistroPonto.data <= data_fim,
            RegistroPonto.hora_entrada.isnot(None),
            RegistroPonto.hora_saida.isnot(None)
        ).all()
        
        total_horas_extras = 0.0
        
        # Horário padrão fixo: 07:12 às 17:00
        entrada_padrao_min = 7 * 60 + 12   # 432 min (07:12)
        saida_padrao_min = 17 * 60          # 1020 min (17:00)
        
        for registro in registros:
            # Converter horários reais para minutos
            entrada_real_min = registro.hora_entrada.hour * 60 + registro.hora_entrada.minute
            saida_real_min = registro.hora_saida.hour * 60 + registro.hora_saida.minute
            
            # Calcular extras (apenas se houver)
            extras_entrada = max(0, entrada_padrao_min - entrada_real_min)  # Entrada antecipada
            extras_saida = max(0, saida_real_min - saida_padrao_min)        # Saída atrasada
            
            # Somar ao total (converter para horas)
            total_horas_extras += (extras_entrada + extras_saida) / 60
        
        return round(total_horas_extras, 2)
    def _calcular_faltas(self, funcionario_id, data_inicio, data_fim):
        """3. Faltas: Número de faltas não justificadas registradas"""
        funcionario = Funcionario.query.get(funcionario_id)
        if not funcionario:
            return 0
        
        faltas = db.session.query(func.count(RegistroPonto.id)).filter(
            RegistroPonto.funcionario_id == funcionario_id,
            RegistroPonto.admin_id == funcionario.admin_id,
            RegistroPonto.data >= data_inicio,
            RegistroPonto.data <= data_fim,
            RegistroPonto.tipo_registro == 'falta'
        ).scalar()
        
        return faltas or 0
    
    def _calcular_atrasos_horas(self, funcionario_id, data_inicio, data_fim):
        """4. Atrasos: Total de horas de atraso (entrada + saída antecipada)
        EXCLUINDO sábados, domingos e feriados trabalhados (onde toda hora é extra)"""
        funcionario = Funcionario.query.get(funcionario_id)
        if not funcionario:
            return 0.0
        
        total = db.session.query(func.sum(RegistroPonto.total_atraso_horas)).filter(
            RegistroPonto.funcionario_id == funcionario_id,
            RegistroPonto.admin_id == funcionario.admin_id,
            RegistroPonto.data >= data_inicio,
            RegistroPonto.data <= data_fim,
            RegistroPonto.total_atraso_horas.isnot(None),
            # EXCLUIR tipos onde toda hora é extra (não há conceito de atraso)
            ~RegistroPonto.tipo_registro.in_(['sabado_trabalhado', 'sabado_trabalhado', 'domingo_trabalhado', 'domingo_horas_extras', 'feriado_trabalhado'])
        ).scalar()
        
        return total or 0.0
    
    def _calcular_custo_mensal(self, funcionario_id, data_inicio, data_fim):
        """
        9. Custo Mão de Obra: LÓGICA CORRIGIDA CONFORME LEGISLAÇÃO BRASILEIRA
        
        FÓRMULA CORRIGIDA:
        Salário Base + (Valor_Hora_Extra × Horas_Extras × Multiplicador)
        
        Multiplicadores conforme CLT:
        - Horas extras normais: 1.5x (50% adicional)
        - Sábado trabalhado: 1.5x (50% adicional) 
        - Domingo/Feriado: 2.0x (100% adicional)
        """
        funcionario = Funcionario.query.get(funcionario_id)
        if not funcionario or not funcionario.salario:
            return 0.0
        
        salario_base = float(funcionario.salario)
        
        # 1. Calcular valor/hora baseado no horário específico do funcionário
        horario = funcionario.horario_trabalho
        if horario and horario.horas_diarias:
            # Usar horário específico: horas_diarias × 22 dias úteis
            horas_mensais = horario.horas_diarias * 22
        else:
            # Fallback: jornada padrão 8h × 22 dias = 176h (não 220h!)
            horas_mensais = 176
        
        valor_hora_normal = salario_base / horas_mensais
        
        # 2. Buscar registros de ponto por tipo para calcular extras específicos
        registros = RegistroPonto.query.filter(
            RegistroPonto.funcionario_id == funcionario_id,
            RegistroPonto.admin_id == funcionario.admin_id,
            RegistroPonto.data >= data_inicio,
            RegistroPonto.data <= data_fim,
            RegistroPonto.horas_extras.isnot(None),
            RegistroPonto.horas_extras > 0
        ).all()
        
        total_custo_extras = 0.0
        
        for registro in registros:
            horas_extras = float(registro.horas_extras or 0)
            
            # Aplicar multiplicador conforme legislação brasileira
            if registro.tipo_registro in ['trabalho_normal', 'sabado_trabalhado', 'sabado_horas_extras']:
                # 50% adicional (Art. 59 CLT)
                multiplicador = 1.5
            elif registro.tipo_registro in ['domingo_trabalhado', 'domingo_horas_extras', 'feriado_trabalhado']:
                # 100% adicional (Art. 7º CF)
                multiplicador = 2.0
            else:
                # Padrão 50%
                multiplicador = 1.5
            
            custo_extras_registro = horas_extras * valor_hora_normal * multiplicador
            total_custo_extras += custo_extras_registro
        
        # 3. Calcular desconto por faltas
        faltas = self._calcular_faltas(funcionario_id, data_inicio, data_fim)
        
        # Valor por dia baseado nas horas contratuais
        valor_por_dia = (valor_hora_normal * horas_mensais) / 22  # 22 dias úteis
        desconto_faltas = valor_por_dia * faltas
        
        # 4. Custo total = salário base - descontos + extras
        custo_total = salario_base - desconto_faltas + total_custo_extras
        
        return custo_total
    
    def _calcular_dias_uteis_mes(self, ano, mes):
        """Calcula dias úteis reais do mês (seg-sex, excluindo feriados)"""
        import calendar
                from models import OutroCusto
        from datetime import timedelta
        
        primeiro_dia = date(ano, mes, 1)
        ultimo_dia = date(ano, mes, calendar.monthrange(ano, mes)[1])
        
        dias_uteis = 0
        feriados = self._get_feriados_brasil(ano)
        
        data_atual = primeiro_dia
        while data_atual <= ultimo_dia:
            # Segunda a sexta (weekday 0-4)
            if data_atual.weekday() < 5 and data_atual not in feriados:
                dias_uteis += 1
            data_atual += timedelta(days=1)
        
        return dias_uteis
    
    def _calcular_dias_uteis_periodo(self, data_inicio, data_fim):
        """Calcula dias úteis em um período específico"""
        from datetime import timedelta
        
        dias_uteis = 0
        feriados = self._get_feriados_brasil(data_inicio.year)
        
        data_atual = data_inicio
        while data_atual <= data_fim:
            if data_atual.weekday() < 5 and data_atual not in feriados:
                dias_uteis += 1
            data_atual += timedelta(days=1)
        
        return dias_uteis
    
    def _get_feriados_brasil(self, ano):
        """Feriados nacionais fixos do Brasil"""
        return [
            date(ano, 1, 1),   # Confraternização Universal
            date(ano, 4, 21),  # Tiradentes  
            date(ano, 5, 1),   # Dia do Trabalhador
            date(ano, 9, 7),   # Independência do Brasil
            date(ano, 10, 12), # Nossa Senhora Aparecida
            date(ano, 11, 2),  # Finados
            date(ano, 11, 15), # Proclamação da República
            date(ano, 12, 25), # Natal
        ]
    
    def _calcular_faltas_justificadas(self, funcionario_id, data_inicio, data_fim):
        """Calcular faltas justificadas (com ocorrências aprovadas)"""
        funcionario = Funcionario.query.get(funcionario_id)
        if not funcionario:
            return 0
        
        faltas_justificadas = db.session.query(func.count(RegistroPonto.id)).filter(
            RegistroPonto.funcionario_id == funcionario_id,
            RegistroPonto.admin_id == funcionario.admin_id,
            RegistroPonto.data >= data_inicio,
            RegistroPonto.data <= data_fim,
            RegistroPonto.tipo_registro == 'falta_justificada'
        ).scalar()
        
        return faltas_justificadas or 0
    
    def _calcular_custo_horas_extras_especifico(self, funcionario_id, data_inicio, data_fim, valor_hora):
        """Calcular custo de horas extras com percentuais específicos por tipo"""
        funcionario = Funcionario.query.get(funcionario_id)
        if not funcionario or not funcionario.horario_trabalho:
            # Fallback para cálculo simples se não tem horário específico
            horas_extras = self._calcular_horas_extras(funcionario_id, data_inicio, data_fim)
            return horas_extras * valor_hora * 1.5
        
        horas_diarias_padrao = funcionario.horario_trabalho.horas_diarias
        
        # Buscar registros de ponto no período
        registros = db.session.query(RegistroPonto).filter(
            RegistroPonto.funcionario_id == funcionario_id,
            RegistroPonto.admin_id == funcionario.admin_id,
            RegistroPonto.data >= data_inicio,
            RegistroPonto.data <= data_fim,
            RegistroPonto.horas_trabalhadas.isnot(None)
        ).all()
        
        custo_total_extras = 0.0
        
        for registro in registros:
            horas_trabalhadas = registro.horas_trabalhadas or 0
            if horas_trabalhadas > horas_diarias_padrao:
                horas_extras = horas_trabalhadas - horas_diarias_padrao
                
                # Aplicar percentual correto baseado no tipo de lançamento
                if registro.tipo_registro in ['sabado_trabalhado']:
                    percentual = 1.5  # 50% adicional
                elif registro.tipo_registro in ['domingo_trabalhado', 'domingo_horas_extras', 'feriado_trabalhado']:
                    percentual = 2.0  # 100% adicional
                else:
                    percentual = 1.5  # Padrão 50%
                
                custo_extras = horas_extras * valor_hora * percentual
                custo_total_extras += custo_extras
        
        return custo_total_extras
    
    def _calcular_custo_transporte(self, funcionario_id, data_inicio, data_fim):
        """Calcular custo de transporte (vale transporte)"""
        if not hasattr(self, 'OutroCusto'):
            try:
                self.OutroCusto = OutroCusto
            except ImportError:
                return 0.0
        
        total = db.session.query(func.sum(self.OutroCusto.valor)).filter(
            self.OutroCusto.funcionario_id == funcionario_id,
            self.OutroCusto.data >= data_inicio,
            self.OutroCusto.data <= data_fim,
            self.OutroCusto.tipo.ilike('%transporte%')
        ).scalar()
        
        return total or 0.0
    
    def _calcular_outros_custos(self, funcionario_id, data_inicio, data_fim):
        """Calcular outros custos (vale alimentação, EPIs, etc.)"""
        if not hasattr(self, 'OutroCusto'):
            try:
                self.OutroCusto = OutroCusto
            except ImportError:
                return 0.0
        
        total = db.session.query(func.sum(self.OutroCusto.valor)).filter(
            self.OutroCusto.funcionario_id == funcionario_id,
            self.OutroCusto.data >= data_inicio,
            self.OutroCusto.data <= data_fim,
            ~self.OutroCusto.tipo.ilike('%transporte%')
        ).scalar()
        
        return total or 0.0
    
    def _calcular_eficiencia(self, funcionario_id, data_inicio, data_fim):
        """14. Eficiência: Horas Trabalhadas / (Horas Trabalhadas + Horas Perdidas)"""
        horas_trabalhadas = self._calcular_horas_trabalhadas(funcionario_id, data_inicio, data_fim)
        horas_perdidas = self._calcular_horas_perdidas(funcionario_id, data_inicio, data_fim)
        
        # CORREÇÃO: Eficiência = Horas Trabalhadas / (Horas Trabalhadas + Horas Perdidas)
        # Se não há horas perdidas, eficiência = 100%
        if horas_perdidas == 0:
            return 100.0
        
        horas_totais = horas_trabalhadas + horas_perdidas
        if horas_totais == 0:
            return 0.0
        
        return (horas_trabalhadas / horas_totais) * 100
    
    def _calcular_valor_falta_justificada(self, funcionario_id, data_inicio, data_fim):
        """Calcular valor pago em faltas justificadas"""
        funcionario = Funcionario.query.get(funcionario_id)
        if not funcionario or not funcionario.salario:
            return 0.0
        
        valor_hora = funcionario.salario / 220  # 220 horas/mês
        faltas_justificadas = self._calcular_faltas_justificadas(funcionario_id, data_inicio, data_fim)
        
        # Assumir 8 horas por dia de falta justificada
        valor_total = faltas_justificadas * 8 * valor_hora
        
        return valor_total
    
    def _calcular_absenteismo(self, funcionario_id, data_inicio, data_fim):
        """6. Absenteísmo: Percentual de faltas não justificadas em relação aos dias com lançamento"""
        funcionario = Funcionario.query.get(funcionario_id)
        if not funcionario:
            return 0.0
        
        # Contar dias com lançamento (trabalho programado)
        dias_com_lancamento = db.session.query(func.count(RegistroPonto.id)).filter(
            RegistroPonto.funcionario_id == funcionario_id,
            RegistroPonto.admin_id == funcionario.admin_id,
            RegistroPonto.data >= data_inicio,
            RegistroPonto.data <= data_fim,
            RegistroPonto.tipo_registro.in_(['trabalho_normal', 'trabalhado', 'feriado_trabalhado', 'meio_periodo', 'falta', 'falta_justificada'])
        ).scalar()
        
        # Contar faltas não justificadas
        faltas = self._calcular_faltas(funcionario_id, data_inicio, data_fim)
        
        if dias_com_lancamento == 0:
            return 0.0
            
        return (faltas / dias_com_lancamento) * 100
    
    def _calcular_media_horas_diarias(self, funcionario_id, data_inicio, data_fim):
        """7. Média Diária: Média de horas trabalhadas por dia presente"""
        funcionario = Funcionario.query.get(funcionario_id)
        if not funcionario:
            return 0.0
        
        horas_total = self._calcular_horas_trabalhadas(funcionario_id, data_inicio, data_fim)
        
        dias_presenca = db.session.query(func.count(RegistroPonto.id)).filter(
            RegistroPonto.funcionario_id == funcionario_id,
            RegistroPonto.admin_id == funcionario.admin_id,
            RegistroPonto.data >= data_inicio,
            RegistroPonto.data <= data_fim,
            RegistroPonto.hora_entrada.isnot(None)
        ).scalar()
        
        if not dias_presenca:
            return 0.0
            
        return horas_total / dias_presenca
    
    def _calcular_horas_perdidas(self, funcionario_id, data_inicio, data_fim):
        """8. Horas Perdidas: Faltas + Atrasos convertidos em horas"""
        faltas = self._calcular_faltas(funcionario_id, data_inicio, data_fim)
        atrasos_horas = self._calcular_atrasos_horas(funcionario_id, data_inicio, data_fim)
        
        # Faltas em horas (assumindo 8h/dia)
        faltas_horas = faltas * 8
        
        return faltas_horas + atrasos_horas
    
    def _calcular_produtividade(self, funcionario_id, data_inicio, data_fim):
        """9. Produtividade: Percentual de eficiência baseado no horário específico do funcionário"""
        horas_trabalhadas = self._calcular_horas_trabalhadas(funcionario_id, data_inicio, data_fim)
        horas_extras = self._calcular_horas_extras(funcionario_id, data_inicio, data_fim)
        horas_perdidas = self._calcular_horas_perdidas(funcionario_id, data_inicio, data_fim)
        
        # CORREÇÃO: Produtividade = Horas Úteis / (Horas Úteis + Horas Perdidas)
        # Se não há horas perdidas, produtividade = 100%
        horas_uteis = horas_trabalhadas + horas_extras
        
        if horas_perdidas == 0:
            # Sem perdas = 100% de produtividade
            return 100.0
        
        horas_totais = horas_uteis + horas_perdidas
        if horas_totais == 0:
            return 0.0
            
        return (horas_uteis / horas_totais) * 100
    
    def _calcular_custo_alimentacao(self, funcionario_id, data_inicio, data_fim):
        """10. Custo Alimentação: Gasto total com alimentação no período"""
        total = db.session.query(func.sum(RegistroAlimentacao.valor)).filter(
            RegistroAlimentacao.funcionario_id == funcionario_id,
            RegistroAlimentacao.data >= data_inicio,
            RegistroAlimentacao.data <= data_fim
        ).scalar()
        
        return total or 0.0
    
    def _calcular_horas_faltas_justificadas(self, funcionario_id, data_inicio, data_fim):
        """Calcula horas de faltas justificadas (que afetam custo)"""
        ocorrencias = db.session.query(Ocorrencia).join(TipoOcorrencia).filter(
            Ocorrencia.funcionario_id == funcionario_id,
            Ocorrencia.status == 'Aprovado',
            TipoOcorrencia.afeta_custo == True,
            Ocorrencia.data_inicio >= data_inicio,
            Ocorrencia.data_inicio <= data_fim
        ).all()
        
        total_horas = 0
        for ocorrencia in ocorrencias:
            # Calcular dias da ocorrência
            data_fim_ocorrencia = ocorrencia.data_fim or ocorrencia.data_inicio
            dias = (data_fim_ocorrencia - ocorrencia.data_inicio).days + 1
            total_horas += dias * 8  # 8 horas por dia
            
        return total_horas
    
    def _calcular_dias_uteis(self, data_inicio, data_fim):
        """Calcula número de dias úteis no período (segunda a sexta, exceto feriados)"""
        dias_uteis = 0
        data_atual = data_inicio
        
        while data_atual <= data_fim:
            # Verificar se é dia útil (segunda=1 a sexta=5)
            if data_atual.isoweekday() <= 5:
                # Verificar se não é feriado
                feriado = CalendarioUtil.query.filter_by(
                    data=data_atual, 
                    eh_feriado=True
                ).first()
                
                if not feriado:
                    dias_uteis += 1
                    
            data_atual += timedelta(days=1)
            
        return dias_uteis
    
    def _calcular_dias_com_lancamento(self, funcionario_id, data_inicio, data_fim):
        """
        Calcula número de dias com lançamento no período
        Conta apenas dias úteis (excluindo fins de semana não trabalhados)
        """
        funcionario = Funcionario.query.get(funcionario_id)
        if not funcionario:
            return 0
        
        # Buscar registros de ponto no período
        registros = db.session.query(RegistroPonto).filter(
            RegistroPonto.funcionario_id == funcionario_id,
            RegistroPonto.admin_id == funcionario.admin_id,
            RegistroPonto.data >= data_inicio,
            RegistroPonto.data <= data_fim
        ).all()
        
        # Tipos considerados para KPIs (apenas dias úteis)
        tipos_uteis = {
            'trabalho_normal', 'trabalhado', 'feriado_trabalhado', 'meio_periodo', 
            'falta', 'falta_justificada'
        }
        
        dias_com_lancamento = 0
        for registro in registros:
            if registro.tipo_registro in tipos_uteis:
                dias_com_lancamento += 1
        
        return dias_com_lancamento
    
    def calcular_e_atualizar_ponto(self, registro_ponto_id):
        """
        Calcula automaticamente atrasos e horas para um registro de ponto
        Implementa a lógica de cálculo automático conforme triggers especificados
        """
        registro = RegistroPonto.query.get(registro_ponto_id)
        if not registro:
            return False
            
        funcionario = Funcionario.query.get(registro.funcionario_id)
        if not funcionario:
            return False
        
        # Obter horário de trabalho do funcionário
        horario = funcionario.horario_trabalho_ref if hasattr(funcionario, 'horario_trabalho_ref') else None
        if not horario:
            # Usar horário padrão se não houver específico
            horario_entrada = time(8, 0)  # 08:00
            horario_saida = time(17, 0)   # 17:00
        else:
            horario_entrada = horario.entrada
            horario_saida = horario.saida
        
        # LÓGICA CORRIGIDA: Calcular atrasos APENAS para tipos normais
        minutos_atraso_entrada = 0
        minutos_atraso_saida = 0
        
        # Em sábado, domingo e feriado trabalhado não há conceito de atraso
        # pois toda hora trabalhada é considerada extra
        if registro.tipo_registro not in ['sabado_trabalhado', 'domingo_horas_extras', 'feriado_trabalhado']:
            # ATRASO NA ENTRADA: sempre calcular se chegou após horário previsto
            if registro.hora_entrada and registro.hora_entrada > horario_entrada:
                entrada_minutos = registro.hora_entrada.hour * 60 + registro.hora_entrada.minute
                previsto_minutos = horario_entrada.hour * 60 + horario_entrada.minute
                minutos_atraso_entrada = entrada_minutos - previsto_minutos
            
            # SAÍDA ANTECIPADA: calcular se saiu antes do horário previsto
            if registro.hora_saida and registro.hora_saida < horario_saida:
                saida_minutos = registro.hora_saida.hour * 60 + registro.hora_saida.minute
                previsto_minutos = horario_saida.hour * 60 + horario_saida.minute
                minutos_atraso_saida = previsto_minutos - saida_minutos
        
        # SEMPRE atualizar campos de atraso (mesmo que zero)
        registro.minutos_atraso_entrada = minutos_atraso_entrada
        registro.minutos_atraso_saida = minutos_atraso_saida
        registro.total_atraso_minutos = minutos_atraso_entrada + minutos_atraso_saida
        registro.total_atraso_horas = registro.total_atraso_minutos / 60.0
        
        # Calcular horas trabalhadas
        if registro.hora_entrada and registro.hora_saida:
            # Calcular tempo total
            entrada_minutos = registro.hora_entrada.hour * 60 + registro.hora_entrada.minute
            saida_minutos = registro.hora_saida.hour * 60 + registro.hora_saida.minute
            
            # CORREÇÃO: Almoço opcional para tipos especiais
            tempo_almoco = 0
            if registro.hora_almoco_saida and registro.hora_almoco_retorno:
                almoco_saida = registro.hora_almoco_saida.hour * 60 + registro.hora_almoco_saida.minute
                almoco_retorno = registro.hora_almoco_retorno.hour * 60 + registro.hora_almoco_retorno.minute
                tempo_almoco = almoco_retorno - almoco_saida
            elif registro.tipo_registro == 'trabalho_normal':
                # Para trabalho normal sem horário especificado, assumir 1h
                tempo_almoco = 60
            
            total_minutos = saida_minutos - entrada_minutos - tempo_almoco
            registro.horas_trabalhadas = max(0, total_minutos / 60.0)
            
            # LÓGICA CONSOLIDADA: Usar horário padrão 07:12-17:00
            horario_entrada_padrao = time(7, 12)
            horario_saida_padrao = time(17, 0)
            
            if registro.tipo_registro in ['sabado_trabalhado', 'sabado_horas_extras', 'domingo_trabalhado', 'domingo_horas_extras', 'feriado_trabalhado']:
                # TIPOS ESPECIAIS: TODAS as horas são extras, SEM atrasos
                registro.horas_extras = registro.horas_trabalhadas or 0
                registro.total_atraso_horas = 0
                registro.total_atraso_minutos = 0
                registro.minutos_atraso_entrada = 0
                registro.minutos_atraso_saida = 0
                
                if registro.tipo_registro in ['sabado_trabalhado', 'sabado_horas_extras']:
                    registro.percentual_extras = 50.0
                else:  # domingo, feriado
                    registro.percentual_extras = 100.0
            else:
                # TIPOS NORMAIS: Calcular extras e atrasos baseado no horário padrão do funcionário
                entrada_real_min = registro.hora_entrada.hour * 60 + registro.hora_entrada.minute
                saida_real_min = registro.hora_saida.hour * 60 + registro.hora_saida.minute
                
                # USAR HORÁRIO PADRÃO DO FUNCIONÁRIO (cadastrado em horários de trabalho)
                # Se não houver horário específico, usar padrão 07:12-17:00
                if funcionario.horario_trabalho_ref:
                    entrada_padrao_funcionario = funcionario.horario_trabalho_ref.entrada
                    saida_padrao_funcionario = funcionario.horario_trabalho_ref.saida
                    print(f"📋 USANDO HORÁRIO CADASTRADO: {funcionario.nome} - {entrada_padrao_funcionario} às {saida_padrao_funcionario}")
                else:
                    entrada_padrao_funcionario = time(7, 12)  # 07:12
                    saida_padrao_funcionario = time(17, 0)    # 17:00
                    print(f"📋 USANDO HORÁRIO PADRÃO: {funcionario.nome} - 07:12 às 17:00")
                
                entrada_padrao_min = entrada_padrao_funcionario.hour * 60 + entrada_padrao_funcionario.minute
                saida_padrao_min = saida_padrao_funcionario.hour * 60 + saida_padrao_funcionario.minute
                
                # CALCULAR ATRASOS (chegou depois OU saiu antes do horário padrão)
                atraso_entrada_min = max(0, entrada_real_min - entrada_padrao_min)
                atraso_saida_min = max(0, saida_padrao_min - saida_real_min)
                total_atraso_min = atraso_entrada_min + atraso_saida_min
                
                # CALCULAR HORAS EXTRAS (chegou antes OU saiu depois do horário padrão)
                # LÓGICA CORRETA: Entrada antecipada + Saída atrasada = Horas Extras
                extra_entrada_min = max(0, entrada_padrao_min - entrada_real_min)  # Chegou antes
                extra_saida_min = max(0, saida_real_min - saida_padrao_min)       # Saiu depois
                total_extra_min = extra_entrada_min + extra_saida_min
                
                # LOG DETALHADO PARA DEBUG
                if total_extra_min > 0 or total_atraso_min > 0:
                    print(f"👤 {funcionario.nome} - {registro.data}:")
                    print(f"   Horário padrão: {entrada_padrao_funcionario}-{saida_padrao_funcionario}")
                    print(f"   Horário real: {registro.hora_entrada}-{registro.hora_saida}")
                    print(f"   Extras entrada: {extra_entrada_min}min (chegou {extra_entrada_min}min antes)")
                    print(f"   Extras saída: {extra_saida_min}min (saiu {extra_saida_min}min depois)")
                    print(f"   Total extras: {total_extra_min}min = {round(total_extra_min/60, 2)}h")
                    print(f"   Atrasos: {total_atraso_min}min = {round(total_atraso_min/60, 2)}h")
                
                # APLICAR VALORES CALCULADOS
                registro.minutos_atraso_entrada = atraso_entrada_min
                registro.minutos_atraso_saida = atraso_saida_min
                registro.total_atraso_minutos = total_atraso_min
                registro.total_atraso_horas = round(total_atraso_min / 60.0, 2)
                
                registro.horas_extras = round(total_extra_min / 60.0, 2)
                registro.percentual_extras = 50.0 if registro.horas_extras > 0 else 0.0
        
        # Salvar alterações
        db.session.commit()
        return True
    
    def _calcular_custo_total(self, funcionario_id, data_inicio, data_fim):
        """
        16. Custo Total: Soma de todos os custos do funcionário
        
        Fórmula: Custo Mão de Obra + Custo Alimentação + Custo Transporte + Outros Custos
        """
        custo_mao_obra = self._calcular_custo_mensal(funcionario_id, data_inicio, data_fim)
        custo_alimentacao = self._calcular_custo_alimentacao(funcionario_id, data_inicio, data_fim)
        custo_transporte = self._calcular_custo_transporte(funcionario_id, data_inicio, data_fim)
        outros_custos = self._calcular_outros_custos(funcionario_id, data_inicio, data_fim)
        
        custo_total = custo_mao_obra + custo_alimentacao + custo_transporte + outros_custos
        
        return custo_total
    
    def _calcular_valor_horas_extras(self, funcionario_id, data_inicio, data_fim):
        """15. Valor Horas Extras: Valor monetário baseado na coluna horas_extras e percentual_extras"""
        funcionario = Funcionario.query.get(funcionario_id)
        if not funcionario or not funcionario.salario:
            return 0.0
        
        # Valor hora base (padrão 220 horas/mês para simplicidade)
        valor_hora_base = funcionario.salario / 220
        
        # Buscar registros com horas extras e percentuais - SEM FILTRO > 0
        registros = RegistroPonto.query.filter(
            RegistroPonto.funcionario_id == funcionario_id,
            RegistroPonto.admin_id == funcionario.admin_id,
            RegistroPonto.data >= data_inicio,
            RegistroPonto.data <= data_fim,
            RegistroPonto.horas_extras.isnot(None)
        ).all()
        
        valor_total = 0.0
        
        for registro in registros:
            horas_extras = registro.horas_extras or 0
            if horas_extras <= 0:
                continue
            
            # Usar percentual_extras do registro ou definir baseado no tipo
            if registro.percentual_extras and registro.percentual_extras > 0:
                percentual = registro.percentual_extras / 100  # Converter % para decimal
                multiplicador = 1 + percentual  # 1 + 0.5 = 1.5 para sábado (50%)
            else:
                # Fallback baseado no tipo de registro - APENAS sabado_trabalhado
                if registro.tipo_registro == 'sabado_trabalhado':
                    multiplicador = 1.5  # 50% adicional
                elif registro.tipo_registro in ['domingo_trabalhado', 'feriado_trabalhado']:
                    multiplicador = 2.0  # 100% adicional  
                else:
                    multiplicador = 1.6  # 60% adicional
            
            valor_registro = horas_extras * valor_hora_base * multiplicador
            valor_total += valor_registro
        
        return valor_total


def gerar_calendario_util(ano):
    """
    Gera calendário de dias úteis para um ano específico
    Inclui feriados nacionais básicos
    """
    feriados_fixos = [
        (1, 1, "Confraternização Universal"),
        (4, 21, "Tiradentes"),
        (5, 1, "Dia do Trabalhador"),
        (9, 7, "Independência do Brasil"),
        (10, 12, "Nossa Senhora Aparecida"),
        (11, 2, "Finados"),
        (11, 15, "Proclamação da República"),
        (12, 25, "Natal")
    ]
    
    # Limpar calendário existente do ano
    CalendarioUtil.query.filter(extract('year', CalendarioUtil.data) == ano).delete()
    
    # Gerar todos os dias do ano
    data_atual = date(ano, 1, 1)
    data_fim = date(ano, 12, 31)
    
    while data_atual <= data_fim:
        eh_util = data_atual.isoweekday() <= 5  # Segunda a sexta
        eh_feriado = False
        descricao_feriado = None
        
        # Verificar feriados fixos
        for mes, dia, nome in feriados_fixos:
            if data_atual.month == mes and data_atual.day == dia:
                eh_feriado = True
                eh_util = False
                descricao_feriado = nome
                break
        
        # Criar registro no calendário
        calendario = CalendarioUtil(
            data=data_atual,
            dia_semana=data_atual.isoweekday(),
            eh_util=eh_util,
            eh_feriado=eh_feriado,
            descricao_feriado=descricao_feriado
        )
        
        db.session.add(calendario)
        data_atual += timedelta(days=1)
    
    db.session.commit()


# Instância global do engine
kpis_engine = CalculadoraKPI()

# Funções de compatibilidade para as views
def calcular_kpis_funcionario_v3(funcionario_id, data_inicio=None, data_fim=None):
    """Função de compatibilidade para calcular KPIs v3"""
    return kpis_engine.calcular_kpis_funcionario(funcionario_id, data_inicio, data_fim)

def calcular_kpis_funcionario_v4(funcionario_id, data_inicio=None, data_fim=None):
    """Função de compatibilidade para calcular KPIs v4"""
    return kpis_engine.calcular_kpis_funcionario(funcionario_id, data_inicio, data_fim)

def identificar_faltas_periodo(funcionario_id, data_inicio, data_fim):
    """Identifica faltas no período especificado"""
    return kpis_engine._calcular_faltas(funcionario_id, data_inicio, data_fim)

def processar_registros_ponto_com_faltas(funcionario_id, data_inicio, data_fim):
    """Processa registros de ponto incluindo identificação de faltas"""
    funcionario = Funcionario.query.get(funcionario_id)
    if not funcionario:
        return []
    
    registros = RegistroPonto.query.filter_by(funcionario_id=funcionario_id).filter(
        RegistroPonto.admin_id == funcionario.admin_id,
        RegistroPonto.data.between(data_inicio, data_fim)
    ).order_by(RegistroPonto.data).all()
    
    # Adicionar informações de faltas
    for registro in registros:
        if not registro.hora_entrada:
            registro.eh_falta = True
        else:
            registro.eh_falta = False
    
    return registros

def atualizar_calculos_ponto(registro_ponto_id):
    """Atualiza cálculos automáticos de um registro de ponto"""
    registro = RegistroPonto.query.get(registro_ponto_id)
    if registro:
        return kpis_engine.calcular_e_atualizar_ponto(registro_ponto_id)
    return None