"""
MODELOS ATUALIZADOS PARA SISTEMA DE HORÁRIOS PADRÃO - SIGE v8.2
Adicionar ao models.py existente
"""

from sqlalchemy import Column, Integer, ForeignKey, Time, Boolean, Date, Float
from sqlalchemy.orm import relationship
from datetime import date, time

class HorarioPadrao(db.Model):
    """Horário padrão de trabalho por funcionário"""
    __tablename__ = 'horarios_padrao'
    
    id = Column(Integer, primary_key=True)
    funcionario_id = Column(Integer, ForeignKey('funcionarios.id'), nullable=False)
    
    # Horários padrão
    entrada_padrao = Column(Time, nullable=False)        # Ex: 07:12
    saida_almoco_padrao = Column(Time)                   # Ex: 12:00
    retorno_almoco_padrao = Column(Time)                 # Ex: 13:00
    saida_padrao = Column(Time, nullable=False)          # Ex: 17:00
    
    # Configurações
    ativo = Column(Boolean, default=True)
    data_inicio = Column(Date, nullable=False)
    data_fim = Column(Date)
    
    # Relacionamentos
    funcionario = relationship('Funcionario', backref='horarios_padrao')
    
    def __repr__(self):
        return f'<HorarioPadrao {self.funcionario.nome}: {self.entrada_padrao}-{self.saida_padrao}>'
    
    def calcular_carga_horaria_diaria(self):
        """Calcula carga horária diária em minutos"""
        if not self.entrada_padrao or not self.saida_padrao:
            return 0
        
        entrada_min = (self.entrada_padrao.hour * 60) + self.entrada_padrao.minute
        saida_min = (self.saida_padrao.hour * 60) + self.saida_padrao.minute
        
        # Descontar intervalo de almoço se definido
        almoco_min = 0
        if self.saida_almoco_padrao and self.retorno_almoco_padrao:
            saida_almoco = (self.saida_almoco_padrao.hour * 60) + self.saida_almoco_padrao.minute
            retorno_almoco = (self.retorno_almoco_padrao.hour * 60) + self.retorno_almoco_padrao.minute
            almoco_min = retorno_almoco - saida_almoco
        
        return saida_min - entrada_min - almoco_min

# Extensão do modelo Funcionario existente
class FuncionarioExtensao:
    """Métodos adicionais para o modelo Funcionario"""
    
    def get_horario_padrao_ativo(self, data=None):
        """Retorna horário padrão ativo para uma data específica"""
        if not data:
            data = date.today()
        
        return HorarioPadrao.query.filter(
            HorarioPadrao.funcionario_id == self.id,
            HorarioPadrao.ativo == True,
            HorarioPadrao.data_inicio <= data,
            db.or_(HorarioPadrao.data_fim.is_(None), HorarioPadrao.data_fim >= data)
        ).first()
    
    def get_carga_horaria_mensal(self, ano, mes):
        """Calcula carga horária mensal baseada no horário padrão"""
        horario = self.get_horario_padrao_ativo(date(ano, mes, 1))
        if not horario:
            return 0
        
        # Calcular dias úteis do mês (simplificado)
        import calendar
        dias_mes = calendar.monthrange(ano, mes)[1]
        dias_uteis = sum(1 for dia in range(1, dias_mes + 1) 
                        if date(ano, mes, dia).weekday() < 5)  # Segunda a sexta
        
        carga_diaria_horas = horario.calcular_carga_horaria_diaria() / 60
        return dias_uteis * carga_diaria_horas

# Extensão do modelo RegistroPonto existente  
class RegistroPontoExtensao:
    """Métodos adicionais para o modelo RegistroPonto"""
    
    def recalcular_horas_extras(self):
        """Recalcula horas extras baseado no horário padrão"""
        from utils import calcular_horas_extras_por_horario_padrao_obj
        
        entrada, saida, total = calcular_horas_extras_por_horario_padrao_obj(self)
        
        self.minutos_extras_entrada = entrada
        self.minutos_extras_saida = saida
        self.total_minutos_extras = entrada + saida
        self.horas_extras_detalhadas = total
        self.horas_extras = total  # Manter compatibilidade
        
        return total
    
    def get_detalhamento_extras(self):
        """Retorna detalhamento das horas extras"""
        return {
            'entrada_antecipada': self.minutos_extras_entrada,
            'saida_atrasada': self.minutos_extras_saida,
            'total_minutos': self.total_minutos_extras,
            'total_horas': self.horas_extras_detalhadas
        }

# Script para adicionar métodos aos modelos existentes
def estender_modelos_existentes():
    """Adiciona métodos aos modelos existentes"""
    
    # Estender Funcionario
    for metodo_nome in dir(FuncionarioExtensao):
        if not metodo_nome.startswith('_'):
            metodo = getattr(FuncionarioExtensao, metodo_nome)
            if callable(metodo):
                setattr(Funcionario, metodo_nome, metodo)
    
    # Estender RegistroPonto
    for metodo_nome in dir(RegistroPontoExtensao):
        if not metodo_nome.startswith('_'):
            metodo = getattr(RegistroPontoExtensao, metodo_nome)
            if callable(metodo):
                setattr(RegistroPonto, metodo_nome, metodo)
    
    print("✅ Modelos estendidos com novos métodos!")

if __name__ == "__main__":
    print("📋 Modelos de Horário Padrão definidos!")
    print("Adicione a classe HorarioPadrao ao seu models.py")
    print("Execute estender_modelos_existentes() para adicionar métodos")