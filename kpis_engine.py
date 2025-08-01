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
from app import db
from models import (
    Funcionario, RegistroPonto, RegistroAlimentacao, 
    Ocorrencia, TipoOcorrencia, CalendarioUtil, HorarioTrabalho
)
from sqlalchemy import func, extract, and_, or_


class KPIsEngine:
    """Engine principal para cálculo de todos os KPIs"""
    
    def __init__(self):
        self.hoje = date.today()
    
    def calcular_kpis_funcionario(self, funcionario_id, data_inicio=None, data_fim=None):
        """
        Calcula todos os KPIs de um funcionário no período especificado
        Layout 4-4-2 conforme especificação
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
        
        # Layout 4-4-4-3: Quarta linha (3 indicadores)
        horas_perdidas = self._calcular_horas_perdidas(funcionario_id, data_inicio, data_fim)
        eficiencia = self._calcular_eficiencia(funcionario_id, data_inicio, data_fim)
        valor_falta_justificada = self._calcular_valor_falta_justificada(funcionario_id, data_inicio, data_fim)
        
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
            
            # Quarta linha (3 indicadores)
            'horas_perdidas': round(horas_perdidas, 1),
            'eficiencia': round(eficiencia, 1),
            'valor_falta_justificada': round(valor_falta_justificada, 2),
            
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
        total = db.session.query(func.sum(RegistroPonto.horas_trabalhadas)).filter(
            RegistroPonto.funcionario_id == funcionario_id,
            RegistroPonto.data >= data_inicio,
            RegistroPonto.data <= data_fim,
            RegistroPonto.horas_trabalhadas.isnot(None)
        ).scalar()
        
        return total or 0.0
    
    def _calcular_horas_extras(self, funcionario_id, data_inicio, data_fim):
        """2. Horas Extras: Soma TOTAL das horas extras (campo direto + calculadas)"""
        # Usar a soma direta do campo horas_extras que já contém todos os cálculos
        total = db.session.query(func.sum(RegistroPonto.horas_extras)).filter(
            RegistroPonto.funcionario_id == funcionario_id,
            RegistroPonto.data >= data_inicio,
            RegistroPonto.data <= data_fim,
            RegistroPonto.horas_extras.isnot(None)
        ).scalar()
        
        return total or 0.0
    
    def _calcular_faltas(self, funcionario_id, data_inicio, data_fim):
        """3. Faltas: Número de faltas não justificadas registradas"""
        faltas = db.session.query(func.count(RegistroPonto.id)).filter(
            RegistroPonto.funcionario_id == funcionario_id,
            RegistroPonto.data >= data_inicio,
            RegistroPonto.data <= data_fim,
            RegistroPonto.tipo_registro == 'falta'
        ).scalar()
        
        return faltas or 0
    
    def _calcular_atrasos_horas(self, funcionario_id, data_inicio, data_fim):
        """4. Atrasos: Total de horas de atraso (entrada + saída antecipada)
        EXCLUINDO sábados, domingos e feriados trabalhados (onde toda hora é extra)"""
        total = db.session.query(func.sum(RegistroPonto.total_atraso_horas)).filter(
            RegistroPonto.funcionario_id == funcionario_id,
            RegistroPonto.data >= data_inicio,
            RegistroPonto.data <= data_fim,
            RegistroPonto.total_atraso_horas.isnot(None),
            # EXCLUIR tipos onde toda hora é extra (não há conceito de atraso)
            ~RegistroPonto.tipo_registro.in_(['sabado_horas_extras', 'domingo_horas_extras', 'feriado_trabalhado'])
        ).scalar()
        
        return total or 0.0
    
    def _calcular_custo_mensal(self, funcionario_id, data_inicio, data_fim):
        """
        5. Custo Mão de Obra: Cálculo SIMPLIFICADO e CORRETO
        
        LÓGICA CORRIGIDA: Salário proporcional apenas às horas efetivamente trabalhadas
        """
        funcionario = Funcionario.query.get(funcionario_id)
        if not funcionario or not funcionario.salario:
            return 0.0
        
        # Buscar registros de trabalho efetivo (exclui folgas e faltas não pagas)
        registros = RegistroPonto.query.filter(
            RegistroPonto.funcionario_id == funcionario_id,
            RegistroPonto.data >= data_inicio,
            RegistroPonto.data <= data_fim,
            RegistroPonto.tipo_registro.in_([
                'trabalho_normal', 'trabalhado',
                'sabado_trabalhado', 'domingo_trabalhado', 'feriado_trabalhado',
                'meio_periodo', 'falta_justificada'
            ])
        ).all()
        
        salario_mensal = float(funcionario.salario)
        # Base: 220 horas mensais (22 dias × 10h incluindo almoço)
        valor_hora_base = salario_mensal / 220.0
        
        custo_total = 0.0
        
        for registro in registros:
            tipo = registro.tipo_registro or 'trabalho_normal'
            horas_reg = float(registro.horas_trabalhadas or 0)
            
            if tipo in ['trabalho_normal', 'trabalhado']:
                # Trabalho normal: valor base por hora
                custo_total += horas_reg * valor_hora_base
                
            elif tipo == 'sabado_trabalhado':
                # Sábado: 50% adicional sobre valor base
                custo_total += horas_reg * valor_hora_base * 1.5
                
            elif tipo in ['domingo_trabalhado', 'feriado_trabalhado']:
                # Domingo/Feriado: 100% adicional sobre valor base  
                custo_total += horas_reg * valor_hora_base * 2.0
                
            elif tipo == 'meio_periodo':
                # Meio período: valor base
                custo_total += horas_reg * valor_hora_base
                
            elif tipo == 'falta_justificada':
                # Falta justificada: paga como trabalho normal (8h)
                custo_total += 8.0 * valor_hora_base
            
            # Folgas (sabado_folga, domingo_folga) não têm custo
        
        return custo_total
    
    def _calcular_faltas_justificadas(self, funcionario_id, data_inicio, data_fim):
        """Calcular faltas justificadas (com ocorrências aprovadas)"""
        faltas_justificadas = db.session.query(func.count(RegistroPonto.id)).filter(
            RegistroPonto.funcionario_id == funcionario_id,
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
                if registro.tipo_registro == 'sabado_horas_extras':
                    percentual = 1.5  # 50% adicional
                elif registro.tipo_registro in ['domingo_horas_extras', 'feriado_trabalhado']:
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
                from models import OutroCusto
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
                from models import OutroCusto
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
        """Calcular eficiência (produtividade ajustada por qualidade)"""
        produtividade = self._calcular_produtividade(funcionario_id, data_inicio, data_fim)
        faltas = self._calcular_faltas(funcionario_id, data_inicio, data_fim)
        
        # Eficiência = Produtividade - penalização por faltas
        penalizacao_faltas = min(faltas * 5, 20)  # Máximo 20% de penalização
        eficiencia = max(0, produtividade - penalizacao_faltas)
        
        return eficiencia
    
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
        # Contar dias com lançamento (trabalho programado)
        dias_com_lancamento = db.session.query(func.count(RegistroPonto.id)).filter(
            RegistroPonto.funcionario_id == funcionario_id,
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
        horas_total = self._calcular_horas_trabalhadas(funcionario_id, data_inicio, data_fim)
        
        dias_presenca = db.session.query(func.count(RegistroPonto.id)).filter(
            RegistroPonto.funcionario_id == funcionario_id,
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
        
        # Buscar funcionário e seu horário de trabalho
        funcionario = Funcionario.query.get(funcionario_id)
        if not funcionario or not funcionario.horario_trabalho:
            # Se não tem horário específico, usar padrão de 8h/dia
            dias_uteis = self._calcular_dias_uteis(data_inicio, data_fim)
            horas_esperadas = dias_uteis * 8
        else:
            # Usar horas diárias específicas do horário de trabalho
            horas_diarias_padrao = funcionario.horario_trabalho.horas_diarias
            dias_uteis = self._calcular_dias_uteis(data_inicio, data_fim)
            horas_esperadas = dias_uteis * horas_diarias_padrao
        
        if horas_esperadas == 0:
            return 0.0
            
        return (horas_trabalhadas / horas_esperadas) * 100
    
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
        # Buscar registros de ponto no período
        registros = db.session.query(RegistroPonto).filter(
            RegistroPonto.funcionario_id == funcionario_id,
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
        
        # Calcular atrasos APENAS para tipos normais (não para sábado/domingo/feriado)
        minutos_atraso_entrada = 0
        minutos_atraso_saida = 0
        
        # Em sábado, domingo e feriado trabalhado não há conceito de atraso
        # pois toda hora trabalhada é considerada extra
        if registro.tipo_registro not in ['sabado_horas_extras', 'domingo_horas_extras', 'feriado_trabalhado']:
            if registro.hora_entrada and registro.hora_entrada > horario_entrada:
                # Atraso na entrada
                entrada_minutos = registro.hora_entrada.hour * 60 + registro.hora_entrada.minute
                previsto_minutos = horario_entrada.hour * 60 + horario_entrada.minute
                minutos_atraso_entrada = entrada_minutos - previsto_minutos
            
            if registro.hora_saida and registro.hora_saida < horario_saida:
                # Saída antecipada
                saida_minutos = registro.hora_saida.hour * 60 + registro.hora_saida.minute
                previsto_minutos = horario_saida.hour * 60 + horario_saida.minute
                minutos_atraso_saida = previsto_minutos - saida_minutos
        
        # Atualizar campos de atraso
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
            
            # CORREÇÃO CRÍTICA: Calcular horas extras baseado no tipo
            if registro.tipo_registro in ['sabado_horas_extras', 'domingo_horas_extras', 'feriado_trabalhado']:
                # Para tipos especiais, TODAS as horas são extras
                registro.horas_extras = registro.horas_trabalhadas
                # Definir percentual correto automaticamente
                if registro.tipo_registro == 'sabado_horas_extras':
                    registro.percentual_extras = 50.0
                else:  # domingo_horas_extras, feriado_trabalhado
                    registro.percentual_extras = 100.0
            else:
                # Para trabalho normal, apenas horas acima da jornada padrão
                horas_jornada = funcionario.horario_trabalho.horas_diarias if funcionario.horario_trabalho else 8.0
                registro.horas_extras = max(0, registro.horas_trabalhadas - horas_jornada)
                if registro.horas_extras > 0:
                    registro.percentual_extras = 50.0  # Padrão para horas extras normais
        
        # Salvar alterações
        db.session.commit()
        return True


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
kpis_engine = KPIsEngine()

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
    registros = RegistroPonto.query.filter_by(funcionario_id=funcionario_id).filter(
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