"""
Modelos para Sistema de Gestão de Serviços - SIGE v8.0
Módulo para gestão de serviços, subserviços e tabelas de composição
"""

from models import db
from datetime import datetime
from enum import Enum
from sqlalchemy import Column, Integer, String, Text, DateTime, Boolean, ForeignKey, Numeric
from sqlalchemy.orm import relationship

class StatusServico(Enum):
    ATIVO = "ativo"
    INATIVO = "inativo"
    DESCONTINUADO = "descontinuado"

class TipoUnidade(Enum):
    M2 = "m2"
    M3 = "m3"
    ML = "ml"
    UN = "un"
    KG = "kg"
    H = "h"
    VERBA = "verba"

class ServicoMestre(db.Model):
    """Serviços principais que podem ser utilizados nas propostas"""
    __tablename__ = 'servico_mestre'
    
    id = Column(Integer, primary_key=True)
    admin_id = Column(Integer, ForeignKey('usuario.id'), nullable=False)
    
    # Dados básicos
    codigo = Column(String(20), nullable=False)  # Ex: SRV001
    nome = Column(String(100), nullable=False)   # Ex: "Estrutura Metálica Industrial"
    descricao = Column(Text)
    
    # Dados comerciais
    unidade = Column(String(10), nullable=False, default='m2')  # m2, m3, ml, un, kg, h, verba
    preco_base = Column(Numeric(10, 2), nullable=False, default=0.00)
    margem_lucro = Column(Numeric(5, 2), nullable=False, default=30.00)  # %
    
    # Status e controle
    status = Column(String(20), nullable=False, default='ativo')
    criado_em = Column(DateTime, default=datetime.utcnow)
    atualizado_em = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relacionamentos
    subservicos = relationship('SubServico', back_populates='servico_mestre', cascade='all, delete-orphan')
    itens_proposta = relationship('ItemServicoPropostaDinamica', back_populates='servico_mestre')
    
    # Administrador
    admin = relationship('Usuario', foreign_keys=[admin_id])
    
    def __repr__(self):
        return f'<ServicoMestre {self.codigo}: {self.nome}>'
    
    @property
    def preco_final(self):
        """Calcula preço final com margem de lucro"""
        if self.preco_base:
            return float(self.preco_base) * (1 + float(self.margem_lucro) / 100)
        return 0.0
    
    @property
    def total_subservicos(self):
        """Conta quantos subserviços este serviço possui"""
        return len(self.subservicos)

class SubServico(db.Model):
    """Subserviços que compõem um serviço mestre"""
    __tablename__ = 'sub_servico'
    
    id = Column(Integer, primary_key=True)
    servico_mestre_id = Column(Integer, ForeignKey('servico_mestre.id'), nullable=False)
    admin_id = Column(Integer, ForeignKey('usuario.id'), nullable=False)
    
    # Dados básicos
    codigo = Column(String(20), nullable=False)  # Ex: SRV001.001
    nome = Column(String(100), nullable=False)   # Ex: "Soldagem de Viga Principal"
    descricao = Column(Text)
    
    # Dados técnicos
    unidade = Column(String(10), nullable=False, default='m2')
    quantidade_base = Column(Numeric(10, 2), nullable=False, default=1.00)  # Quantidade por unidade do serviço mestre
    preco_unitario = Column(Numeric(10, 2), nullable=False, default=0.00)
    
    # Dados de execução
    tempo_execucao = Column(Numeric(5, 2), default=0.00)  # Horas
    nivel_dificuldade = Column(String(20), default='medio')  # facil, medio, dificil
    
    # Status e controle
    status = Column(String(20), nullable=False, default='ativo')
    criado_em = Column(DateTime, default=datetime.utcnow)
    atualizado_em = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relacionamentos
    servico_mestre = relationship('ServicoMestre', back_populates='subservicos')
    admin = relationship('Usuario', foreign_keys=[admin_id])
    
    def __repr__(self):
        return f'<SubServico {self.codigo}: {self.nome}>'
    
    @property
    def valor_total_base(self):
        """Calcula valor total baseado na quantidade base"""
        return float(self.quantidade_base) * float(self.preco_unitario)

class TabelaComposicao(db.Model):
    """Tabelas de composição de custos por tipo de estrutura"""
    __tablename__ = 'tabela_composicao'
    
    id = Column(Integer, primary_key=True)
    admin_id = Column(Integer, ForeignKey('usuario.id'), nullable=False)
    
    # Dados básicos
    nome = Column(String(100), nullable=False)  # Ex: "Galpão Industrial Padrão"
    descricao = Column(Text)
    tipo_estrutura = Column(String(50), nullable=False)  # galpao, edificio, ponte, etc.
    
    # Parâmetros técnicos
    area_minima = Column(Numeric(10, 2), default=0.00)  # m²
    area_maxima = Column(Numeric(10, 2), default=999999.99)  # m²
    altura_minima = Column(Numeric(5, 2), default=0.00)  # metros
    altura_maxima = Column(Numeric(5, 2), default=999.99)  # metros
    
    # Status e controle
    status = Column(String(20), nullable=False, default='ativa')
    criado_em = Column(DateTime, default=datetime.utcnow)
    atualizado_em = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relacionamentos
    itens_composicao = relationship('ItemTabelaComposicao', back_populates='tabela', cascade='all, delete-orphan')
    admin = relationship('Usuario', foreign_keys=[admin_id])
    
    def __repr__(self):
        return f'<TabelaComposicao {self.nome}>'
    
    @property
    def custo_total_m2(self):
        """Calcula custo total por m²"""
        return sum(item.valor_total for item in self.itens_composicao)

class ItemTabelaComposicao(db.Model):
    """Itens que compõem uma tabela de composição"""
    __tablename__ = 'item_tabela_composicao'
    
    id = Column(Integer, primary_key=True)
    tabela_composicao_id = Column(Integer, ForeignKey('tabela_composicao.id'), nullable=False)
    servico_mestre_id = Column(Integer, ForeignKey('servico_mestre.id'), nullable=False)
    admin_id = Column(Integer, ForeignKey('usuario.id'), nullable=False)
    
    # Dados de composição
    quantidade = Column(Numeric(10, 2), nullable=False, default=1.00)  # Quantidade por m²
    percentual_aplicacao = Column(Numeric(5, 2), default=100.00)  # % do serviço aplicado
    
    # Ajustes específicos
    fator_multiplicador = Column(Numeric(5, 2), default=1.00)  # Multiplicador de preço
    observacoes = Column(Text)
    
    # Relacionamentos
    tabela = relationship('TabelaComposicao', back_populates='itens_composicao')
    servico_mestre = relationship('ServicoMestre')
    admin = relationship('Usuario', foreign_keys=[admin_id])
    
    def __repr__(self):
        return f'<ItemTabelaComposicao {self.servico_mestre.nome} - {self.quantidade}>'
    
    @property
    def valor_unitario_ajustado(self):
        """Preço unitário com fator multiplicador"""
        return self.servico_mestre.preco_final * float(self.fator_multiplicador)
    
    @property
    def valor_total(self):
        """Valor total do item na composição"""
        return float(self.quantidade) * self.valor_unitario_ajustado * (float(self.percentual_aplicacao) / 100)

class ItemServicoPropostaDinamica(db.Model):
    """Itens de serviço dinamicamente adicionados à proposta"""
    __tablename__ = 'item_servico_proposta_dinamica'
    
    id = Column(Integer, primary_key=True)
    proposta_id = Column(Integer, ForeignKey('proposta.id'), nullable=False)
    servico_mestre_id = Column(Integer, ForeignKey('servico_mestre.id'), nullable=True)
    admin_id = Column(Integer, ForeignKey('usuario.id'), nullable=False)
    
    # Dados do item
    codigo_item = Column(String(20))  # Código customizado
    nome_item = Column(String(100), nullable=False)  # Nome pode ser customizado
    descricao_item = Column(Text)
    
    # Dados comerciais
    quantidade = Column(Numeric(10, 2), nullable=False, default=1.00)
    unidade = Column(String(10), nullable=False, default='m2')
    preco_unitario = Column(Numeric(10, 2), nullable=False, default=0.00)
    desconto_percentual = Column(Numeric(5, 2), default=0.00)
    
    # Flags de controle
    e_servico_mestre = Column(Boolean, default=False)  # Se foi gerado de um serviço mestre
    inclui_subservicos = Column(Boolean, default=False)  # Se incluiu subserviços automaticamente
    
    # Status e controle
    criado_em = Column(DateTime, default=datetime.utcnow)
    ordem = Column(Integer, default=1)  # Ordem na proposta
    
    # Relacionamentos
    proposta = relationship('Proposta', back_populates='itens_servicos_dinamicos', foreign_keys=[proposta_id])
    servico_mestre = relationship('ServicoMestre', back_populates='itens_proposta')
    admin = relationship('Usuario', foreign_keys=[admin_id])
    
    def __repr__(self):
        return f'<ItemServicoPropostaDinamica {self.nome_item}>'
    
    @property
    def valor_com_desconto(self):
        """Valor unitário com desconto aplicado"""
        desconto = float(self.desconto_percentual) / 100
        return float(self.preco_unitario) * (1 - desconto)
    
    @property
    def valor_total(self):
        """Valor total do item"""
        return float(self.quantidade) * self.valor_com_desconto