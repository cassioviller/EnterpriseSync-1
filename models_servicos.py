"""
Modelos para o sistema de Gestão de Serviços
Sistema SIGE - Estruturas do Vale
"""

from datetime import datetime
from app import db

class CategoriaServico(db.Model):
    """Categorias de serviços para organização"""
    __tablename__ = 'categoria_servico'
    __table_args__ = {'extend_existing': True}
    
    id = db.Column(db.Integer, primary_key=True)
    nome = db.Column(db.String(100), nullable=False)
    descricao = db.Column(db.Text)
    cor_hexadecimal = db.Column(db.String(7), default='#007bff')  # Cor para identificação visual
    ativo = db.Column(db.Boolean, default=True)
    admin_id = db.Column(db.Integer, nullable=False, default=10)
    criado_em = db.Column(db.DateTime, default=datetime.utcnow)
    
    # Relacionamentos
    servicos_gestao = db.relationship('ServicoGestao', backref='categoria', lazy=True, cascade='all, delete-orphan')
    
    def __repr__(self):
        return f'<CategoriaServico {self.nome}>'

class ServicoGestao(db.Model):
    """Serviços para gestão e orçamentos"""
    __tablename__ = 'servico_gestao'
    
    id = db.Column(db.Integer, primary_key=True)
    nome = db.Column(db.String(200), nullable=False)
    descricao = db.Column(db.Text)
    categoria_id = db.Column(db.Integer, db.ForeignKey('categoria_servico.id'), nullable=False)
    unidade = db.Column(db.String(50), nullable=False, default='m²')  # m², m³, kg, unidade, etc.
    unidade_simbolo = db.Column(db.String(10), nullable=False, default='m²')
    preco_base = db.Column(db.Numeric(10, 2), default=0.00)
    tempo_estimado = db.Column(db.Integer, default=1)  # em dias
    ativo = db.Column(db.Boolean, default=True)
    admin_id = db.Column(db.Integer, nullable=False, default=10)
    criado_em = db.Column(db.DateTime, default=datetime.utcnow)
    atualizado_em = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relacionamentos
    subatividades = db.relationship('SubatividadeServico', backref='servico_gestao', lazy=True, cascade='all, delete-orphan')
    servicos_obra = db.relationship('ServicoObraGestao', backref='servico_gestao', lazy=True)
    
    def __repr__(self):
        return f'<ServicoGestao {self.nome}>'
    
    @property
    def total_subatividades(self):
        """Retorna o número total de subatividades"""
        return SubatividadeServico.query.filter_by(servico_id=self.id, ativo=True).count()
    
    @property
    def percentual_padrao(self):
        """Calcula o percentual padrão de cada subatividade"""
        if self.total_subatividades > 0:
            return round(100 / self.total_subatividades, 2)
        return 0

class SubatividadeServico(db.Model):
    """Subatividades que compõem um serviço"""
    __tablename__ = 'subatividade_servico'
    __table_args__ = {'extend_existing': True}
    
    id = db.Column(db.Integer, primary_key=True)
    servico_id = db.Column(db.Integer, db.ForeignKey('servico_gestao.id'), nullable=False)
    nome = db.Column(db.String(200), nullable=False)
    descricao = db.Column(db.Text)
    percentual_padrao = db.Column(db.Numeric(5, 2), default=0.00)  # % que representa do serviço total
    ordem = db.Column(db.Integer, default=1)  # Ordem de execução
    ativo = db.Column(db.Boolean, default=True)
    admin_id = db.Column(db.Integer, nullable=False, default=10)
    criado_em = db.Column(db.DateTime, default=datetime.utcnow)
    
    def __repr__(self):
        return f'<SubatividadeServico {self.nome}>'

class ServicoObraGestao(db.Model):
    """Relacionamento entre serviços e obras com quantidades"""
    __tablename__ = 'servico_obra_gestao'
    
    id = db.Column(db.Integer, primary_key=True)
    obra_id = db.Column(db.Integer, db.ForeignKey('obra.id'), nullable=False)
    servico_id = db.Column(db.Integer, db.ForeignKey('servico_gestao.id'), nullable=False)
    quantidade_planejada = db.Column(db.Numeric(10, 3), default=0.000)
    quantidade_executada = db.Column(db.Numeric(10, 3), default=0.000)
    preco_unitario = db.Column(db.Numeric(10, 2), default=0.00)
    observacoes = db.Column(db.Text)
    ativo = db.Column(db.Boolean, default=True)
    admin_id = db.Column(db.Integer, nullable=False, default=10)
    criado_em = db.Column(db.DateTime, default=datetime.utcnow)
    atualizado_em = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    def __repr__(self):
        return f'<ServicoObraGestao Obra:{self.obra_id} Serviço:{self.servico_id}>'
    
    @property
    def percentual_conclusao(self):
        """Calcula o percentual de conclusão do serviço na obra"""
        if self.quantidade_planejada and self.quantidade_planejada > 0:
            return min(round((self.quantidade_executada / self.quantidade_planejada) * 100, 2), 100)
        return 0
    
    @property
    def valor_total_planejado(self):
        """Valor total planejado para este serviço"""
        return self.quantidade_planejada * self.preco_unitario
    
    @property
    def valor_total_executado(self):
        """Valor total executado para este serviço"""
        return self.quantidade_executada * self.preco_unitario

class TabelaPreco(db.Model):
    """Tabelas de preços para diferentes contextos"""
    __tablename__ = 'tabela_preco'
    __table_args__ = {'extend_existing': True}
    
    id = db.Column(db.Integer, primary_key=True)
    nome = db.Column(db.String(100), nullable=False)
    descricao = db.Column(db.Text)
    vigencia_inicio = db.Column(db.Date, nullable=False)
    vigencia_fim = db.Column(db.Date)
    ativo = db.Column(db.Boolean, default=True)
    padrao = db.Column(db.Boolean, default=False)  # Tabela padrão do sistema
    admin_id = db.Column(db.Integer, nullable=False, default=10)
    criado_em = db.Column(db.DateTime, default=datetime.utcnow)
    
    # Relacionamentos
    itens = db.relationship('ItemTabelaPreco', backref='tabela', lazy=True, cascade='all, delete-orphan')
    
    def __repr__(self):
        return f'<TabelaPreco {self.nome}>'

class ItemTabelaPreco(db.Model):
    """Itens de uma tabela de preços"""
    __tablename__ = 'item_tabela_preco'
    __table_args__ = {'extend_existing': True}
    
    id = db.Column(db.Integer, primary_key=True)
    tabela_id = db.Column(db.Integer, db.ForeignKey('tabela_preco.id'), nullable=False)
    servico_id = db.Column(db.Integer, db.ForeignKey('servico_gestao.id'), nullable=False)
    preco_unitario = db.Column(db.Numeric(10, 2), nullable=False)
    observacoes = db.Column(db.Text)
    admin_id = db.Column(db.Integer, nullable=False, default=10)
    criado_em = db.Column(db.DateTime, default=datetime.utcnow)
    atualizado_em = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relacionamento com serviço
    servico = db.relationship('ServicoGestao', backref='itens_tabela')
    
    def __repr__(self):
        return f'<ItemTabelaPreco Tabela:{self.tabela_id} Serviço:{self.servico_id}>'