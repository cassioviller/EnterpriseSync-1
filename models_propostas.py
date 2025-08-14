from app import db
from datetime import datetime, date
from sqlalchemy import JSON, func
import uuid
import secrets

class PropostaComercialSIGE(db.Model):
    __tablename__ = 'propostas_comerciais'
    
    id = db.Column(db.Integer, primary_key=True)
    numero_proposta = db.Column(db.String(50), unique=True, nullable=False)
    data_proposta = db.Column(db.Date, nullable=False, default=date.today)
    
    # Dados do Cliente
    cliente_nome = db.Column(db.String(255), nullable=False)
    cliente_telefone = db.Column(db.String(20))
    cliente_email = db.Column(db.String(255))
    cliente_endereco = db.Column(db.Text)
    
    # Dados da Proposta
    assunto = db.Column(db.String(255), nullable=False)
    objeto = db.Column(db.Text, nullable=False)
    documentos_referencia = db.Column(db.Text)
    
    # Condições
    prazo_entrega_dias = db.Column(db.Integer, default=90)
    observacoes_entrega = db.Column(db.Text)
    validade_dias = db.Column(db.Integer, default=7)
    percentual_nota_fiscal = db.Column(db.Numeric(5,2), default=13.5)
    
    # Condições de Pagamento
    condicoes_pagamento = db.Column(db.Text, default="""10% de entrada na assinatura do contrato
10% após projeto aprovado
45% compra dos perfis
25% no início da montagem in loco
10% após a conclusão da montagem""")
    
    # Garantias e Considerações
    garantias = db.Column(db.Text, default="""A Estruturas do Vale garante todos os materiais empregados nos serviços contra defeitos de fabricação pelo prazo de 12 (doze) meses contados a partir da data de conclusão da obra, conforme NBR 8800.""")
    consideracoes_gerais = db.Column(db.Text, default="""Modificações nesta proposta somente serão válidas por escrito e com aceite mútuo. Em caso de cancelamento do contrato pela contratante, será cobrada multa de 30% sobre o valor total.""")
    
    # Itens Inclusos/Exclusos (JSON)
    itens_inclusos = db.Column(JSON, default=[
        "Mão de obra para execução dos serviços",
        "Todos os equipamentos de segurança necessários",
        "Transporte e alimentação da equipe",
        "Container para guarda de ferramentas",
        "Movimentação de carga (Munck)",
        "Transporte dos materiais"
    ])
    
    itens_exclusos = db.Column(JSON, default=[
        "Projeto e execução de qualquer obra civil, fundações, alvenarias, elétrica, automação, tubulações etc.",
        "Execução de ensaios destrutivos e radiográficos",
        "Fornecimento de local para armazenagem das peças",
        "Fornecimento e/ou serviços não especificados claramente nesta proposta",
        "Fornecimento de escoramento (escoras)",
        "Fornecimento de andaimes e plataformas",
        "Técnico de segurança",
        "Pintura final de acabamento",
        "Calhas, rufos, condutores e pingadeiras"
    ])
    
    # Status
    status = db.Column(db.String(50), default='rascunho')  # rascunho, enviada, aprovada, rejeitada
    token_cliente = db.Column(db.String(100), unique=True)
    data_envio = db.Column(db.DateTime)
    data_resposta_cliente = db.Column(db.DateTime)
    observacoes_cliente = db.Column(db.Text)
    
    # Valores
    valor_total = db.Column(db.Numeric(15,2), default=0)
    
    # Metadados
    criado_por = db.Column(db.Integer, db.ForeignKey('usuario.id'))
    criado_em = db.Column(db.DateTime, default=datetime.utcnow)
    atualizado_em = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Integração com Obras
    obra_id = db.Column(db.Integer, db.ForeignKey('obra.id'))
    convertida_em_obra = db.Column(db.Boolean, default=False)
    
    # Relacionamentos
    itens = db.relationship('PropostaItem', backref='proposta', lazy=True, cascade='all, delete-orphan')
    arquivos = db.relationship('PropostaArquivo', backref='proposta', lazy=True, cascade='all, delete-orphan')
    
    def __init__(self, **kwargs):
        super(PropostaComercialSIGE, self).__init__(**kwargs)
        if not self.numero_proposta:
            self.numero_proposta = self.gerar_numero_proposta()
        if not self.token_cliente:
            self.token_cliente = secrets.token_urlsafe(32)
    
    def gerar_numero_proposta(self):
        """Gera número sequencial da proposta"""
        ano_atual = date.today().year
        # Contar propostas do ano atual
        count = db.session.query(func.count(PropostaComercialSIGE.id)).filter(
            func.extract('year', PropostaComercialSIGE.data_proposta) == ano_atual
        ).scalar() or 0
        
        proximo_numero = count + 1
        return f"{proximo_numero:03d}.{str(ano_atual)[-2:]}"
    
    def calcular_valor_total(self):
        """Calcula o valor total da proposta"""
        total = sum(float(item.subtotal) for item in self.itens)
        self.valor_total = total
        return total
    
    def to_dict(self):
        return {
            'id': self.id,
            'numero_proposta': self.numero_proposta,
            'data_proposta': self.data_proposta.isoformat() if self.data_proposta else None,
            'cliente_nome': self.cliente_nome,
            'cliente_telefone': self.cliente_telefone,
            'cliente_email': self.cliente_email,
            'assunto': self.assunto,
            'status': self.status,
            'valor_total': float(self.valor_total) if self.valor_total else 0,
            'criado_em': self.criado_em.isoformat() if self.criado_em else None
        }

class PropostaItem(db.Model):
    __tablename__ = 'proposta_itens'
    
    id = db.Column(db.Integer, primary_key=True)
    proposta_id = db.Column(db.Integer, db.ForeignKey('propostas_comerciais.id'), nullable=False)
    item_numero = db.Column(db.Integer, nullable=False)
    descricao = db.Column(db.String(500), nullable=False)
    quantidade = db.Column(db.Numeric(10,3), nullable=False)
    unidade = db.Column(db.String(10), nullable=False)
    preco_unitario = db.Column(db.Numeric(10,2), nullable=False)
    ordem = db.Column(db.Integer, nullable=False)
    
    criado_em = db.Column(db.DateTime, default=datetime.utcnow)
    
    @property
    def subtotal(self):
        return self.quantidade * self.preco_unitario
    
    def to_dict(self):
        return {
            'id': self.id,
            'item_numero': self.item_numero,
            'descricao': self.descricao,
            'quantidade': float(self.quantidade),
            'unidade': self.unidade,
            'preco_unitario': float(self.preco_unitario),
            'subtotal': float(self.subtotal),
            'ordem': self.ordem
        }

class PropostaArquivo(db.Model):
    __tablename__ = 'proposta_arquivos'
    
    id = db.Column(db.Integer, primary_key=True)
    proposta_id = db.Column(db.Integer, db.ForeignKey('propostas_comerciais.id'), nullable=False)
    nome_arquivo = db.Column(db.String(255), nullable=False)
    nome_original = db.Column(db.String(255), nullable=False)
    tipo_arquivo = db.Column(db.String(100))
    tamanho_bytes = db.Column(db.BigInteger)
    caminho_arquivo = db.Column(db.String(500), nullable=False)
    categoria = db.Column(db.String(50))  # 'dwg', 'pdf', 'foto', 'documento', 'outros'
    
    enviado_por = db.Column(db.Integer, db.ForeignKey('usuario.id'))
    enviado_em = db.Column(db.DateTime, default=datetime.utcnow)
    
    def to_dict(self):
        return {
            'id': self.id,
            'nome_original': self.nome_original,
            'tipo_arquivo': self.tipo_arquivo,
            'tamanho_bytes': self.tamanho_bytes,
            'categoria': self.categoria,
            'enviado_em': self.enviado_em.isoformat() if self.enviado_em else None
        }

class PropostaTemplate(db.Model):
    __tablename__ = 'proposta_templates'
    
    id = db.Column(db.Integer, primary_key=True)
    nome = db.Column(db.String(100), nullable=False)
    descricao = db.Column(db.Text)
    itens_padrao = db.Column(JSON)  # Array de itens padrão para este template
    ativo = db.Column(db.Boolean, default=True)
    
    criado_em = db.Column(db.DateTime, default=datetime.utcnow)
    
    def to_dict(self):
        return {
            'id': self.id,
            'nome': self.nome,
            'descricao': self.descricao,
            'itens_padrao': self.itens_padrao,
            'ativo': self.ativo
        }