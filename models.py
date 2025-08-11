from flask_login import UserMixin
from datetime import datetime, date
from sqlalchemy import func
from enum import Enum

from flask_sqlalchemy import SQLAlchemy

# Instância única do SQLAlchemy
db = SQLAlchemy()

class TipoUsuario(Enum):
    SUPER_ADMIN = "super_admin"
    ADMIN = "admin"
    GESTOR_EQUIPES = "gestor_equipes"
    ALMOXARIFE = "almoxarife"  # MÓDULO 4: Almoxarifado
    FUNCIONARIO = "funcionario"

class Usuario(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(64), unique=True, nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password_hash = db.Column(db.String(256))
    nome = db.Column(db.String(100), nullable=False)
    ativo = db.Column(db.Boolean, default=True)
    tipo_usuario = db.Column(db.Enum(TipoUsuario), default=TipoUsuario.FUNCIONARIO, nullable=False)
    admin_id = db.Column(db.Integer, db.ForeignKey('usuario.id'), nullable=True)  # Para funcionários, referencia seu admin
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    # Relacionamentos
    funcionarios = db.relationship('Usuario', backref=db.backref('admin', remote_side=[id]), lazy='dynamic')

class Departamento(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    nome = db.Column(db.String(100), nullable=False)
    descricao = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    funcionarios = db.relationship('Funcionario', backref='departamento_ref', lazy=True)

class Funcao(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    nome = db.Column(db.String(100), nullable=False)
    descricao = db.Column(db.Text)
    salario_base = db.Column(db.Float, default=0.0)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    funcionarios = db.relationship('Funcionario', backref='funcao_ref', lazy=True)

class HorarioTrabalho(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    nome = db.Column(db.String(100), unique=True, nullable=False)
    entrada = db.Column(db.Time, nullable=False)
    saida_almoco = db.Column(db.Time, nullable=False)
    retorno_almoco = db.Column(db.Time, nullable=False)
    saida = db.Column(db.Time, nullable=False)
    dias_semana = db.Column(db.String(20), nullable=False)  # Ex: "1,2,3,4,5" (Segunda=1, Domingo=7)
    horas_diarias = db.Column(db.Float, default=8.0)  # Horas trabalhadas por dia
    valor_hora = db.Column(db.Float, default=12.0)  # Valor por hora
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    def __repr__(self):
        return f'<HorarioTrabalho {self.nome}>'

class Funcionario(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    codigo = db.Column(db.String(10), unique=True, nullable=False)  # F0001, F0002, etc.
    nome = db.Column(db.String(100), nullable=False)
    cpf = db.Column(db.String(14), unique=True, nullable=False)
    rg = db.Column(db.String(20))
    data_nascimento = db.Column(db.Date)
    endereco = db.Column(db.Text)
    telefone = db.Column(db.String(20))
    email = db.Column(db.String(120))
    data_admissao = db.Column(db.Date, nullable=False)
    salario = db.Column(db.Float, default=0.0)
    ativo = db.Column(db.Boolean, default=True)
    foto = db.Column(db.String(255))  # Caminho para o arquivo de foto
    foto_base64 = db.Column(db.Text)  # Foto em base64 para persistência completa
    departamento_id = db.Column(db.Integer, db.ForeignKey('departamento.id'))
    funcao_id = db.Column(db.Integer, db.ForeignKey('funcao.id'))
    horario_trabalho_id = db.Column(db.Integer, db.ForeignKey('horario_trabalho.id'))
    admin_id = db.Column(db.Integer, db.ForeignKey('usuario.id'), nullable=True)  # Para isolamento multi-tenant
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    # Relacionamentos
    horario_trabalho = db.relationship('HorarioTrabalho', backref=db.backref('funcionarios', overlaps="horario_trabalho"), overlaps="funcionarios")
    registros_ponto = db.relationship('RegistroPonto', backref='funcionario_ref', lazy=True, overlaps="funcionario_ref")

class Obra(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    nome = db.Column(db.String(100), nullable=False)
    codigo = db.Column(db.String(20), unique=True)  # Código único da obra
    endereco = db.Column(db.Text)
    data_inicio = db.Column(db.Date, nullable=False)
    data_previsao_fim = db.Column(db.Date)
    orcamento = db.Column(db.Float, default=0.0)
    valor_contrato = db.Column(db.Float, default=0.0)  # Valor do contrato para cálculo de margem
    area_total_m2 = db.Column(db.Float, default=0.0)  # Área total da obra
    status = db.Column(db.String(20), default='Em andamento')
    responsavel_id = db.Column(db.Integer, db.ForeignKey('funcionario.id'))
    
    # MÓDULO 2: Portal do Cliente - Campos Completos
    token_cliente = db.Column(db.String(255), unique=True)
    cliente_nome = db.Column(db.String(100))
    cliente_email = db.Column(db.String(120))
    cliente_telefone = db.Column(db.String(20))
    proposta_origem_id = db.Column(db.Integer, db.ForeignKey('proposta_comercial.id'))
    
    # Configurações do Portal
    portal_ativo = db.Column(db.Boolean, default=True)
    ultima_visualizacao_cliente = db.Column(db.DateTime)
    
    ativo = db.Column(db.Boolean, default=True)  # Campo para controle de obras ativas
    admin_id = db.Column(db.Integer, db.ForeignKey('usuario.id'), nullable=True)  # Para isolamento multi-tenant
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    registros_ponto = db.relationship('RegistroPonto', backref='obra_ref', lazy=True, overlaps="obra_ref")
    custos = db.relationship('CustoObra', backref='obra_ref', lazy=True, overlaps="obra_ref")
    
    # MÓDULO 2: Relacionamentos do Portal do Cliente
    proposta_origem = db.relationship('PropostaComercial', backref='obra_gerada')
    servicos_obra = db.relationship('ServicoObra', backref='obra', cascade='all, delete-orphan', lazy=True)

class ServicoObra(db.Model):
    """Relacionamento entre Serviços e Obras com quantidade planejada"""
    __tablename__ = 'servico_obra'
    
    id = db.Column(db.Integer, primary_key=True)
    obra_id = db.Column(db.Integer, db.ForeignKey('obra.id'), nullable=False)
    servico_id = db.Column(db.Integer, db.ForeignKey('servico.id'), nullable=False)
    quantidade_planejada = db.Column(db.Numeric(10, 4), nullable=False)  # Quantidade total planejada
    quantidade_executada = db.Column(db.Numeric(10, 4), default=0.0)  # Quantidade já executada
    observacoes = db.Column(db.Text)  # Observações específicas para este serviço na obra
    ativo = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Unique constraint para evitar duplicatas
    __table_args__ = (db.UniqueConstraint('obra_id', 'servico_id', name='_obra_servico_uc'),)

class Veiculo(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    placa = db.Column(db.String(10), unique=True, nullable=False)
    marca = db.Column(db.String(50), nullable=False)
    modelo = db.Column(db.String(50), nullable=False)
    ano = db.Column(db.Integer)
    tipo = db.Column(db.String(20), nullable=False)
    status = db.Column(db.String(20), default='Disponível')
    km_atual = db.Column(db.Integer, default=0)
    data_ultima_manutencao = db.Column(db.Date)
    data_proxima_manutencao = db.Column(db.Date)
    ativo = db.Column(db.Boolean, default=True)  # Campo para controle de veículos ativos
    admin_id = db.Column(db.Integer, db.ForeignKey('usuario.id'), nullable=True)  # Para isolamento multi-tenant
    created_at = db.Column(db.DateTime, default=datetime.utcnow)



class CategoriaServico(db.Model):
    """Categorias para classificação de serviços"""
    id = db.Column(db.Integer, primary_key=True)
    nome = db.Column(db.String(100), nullable=False)
    descricao = db.Column(db.Text)
    cor = db.Column(db.String(7), default='#6c757d')  # Cor hex para identificação visual
    icone = db.Column(db.String(50), default='fas fa-wrench')  # Ícone FontAwesome
    ordem = db.Column(db.Integer, default=0)  # Para ordenação
    ativo = db.Column(db.Boolean, default=True)
    admin_id = db.Column(db.Integer, db.ForeignKey('usuario.id'), nullable=True)  # Multi-tenant
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relacionamentos removidos - usar campo categoria string no Servico

class Servico(db.Model):
    """Serviços para coleta de dados reais via RDO - SIGE v6.3"""
    id = db.Column(db.Integer, primary_key=True)
    nome = db.Column(db.String(100), nullable=False)
    descricao = db.Column(db.Text)
    categoria = db.Column(db.String(50), nullable=False)  # Campo string principal
    unidade_medida = db.Column(db.String(10), nullable=False)  # m2, m3, kg, ton, un, m, h
    unidade_simbolo = db.Column(db.String(10))  # Símbolo da unidade para exibição
    custo_unitario = db.Column(db.Float, default=0.0)  # Custo unitário do serviço
    complexidade = db.Column(db.Integer, default=3)  # 1-5 para análise futura
    requer_especializacao = db.Column(db.Boolean, default=False)
    ativo = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relacionamentos
    subatividades = db.relationship('SubAtividade', backref='servico', cascade='all, delete-orphan', lazy=True)
    historico_produtividade = db.relationship('HistoricoProdutividadeServico', backref='servico', lazy=True)
    servicos_obra = db.relationship('ServicoObra', backref='servico', lazy=True)

class SubAtividade(db.Model):
    """Subatividades de um serviço para coleta detalhada de dados"""
    __tablename__ = 'sub_atividade'
    
    id = db.Column(db.Integer, primary_key=True)
    servico_id = db.Column(db.Integer, db.ForeignKey('servico.id'), nullable=False)
    nome = db.Column(db.String(100), nullable=False)
    descricao = db.Column(db.Text)
    ordem_execucao = db.Column(db.Integer, nullable=False)
    ferramentas_necessarias = db.Column(db.Text)
    materiais_principais = db.Column(db.Text)
    requer_aprovacao = db.Column(db.Boolean, default=False)
    pode_executar_paralelo = db.Column(db.Boolean, default=True)
    qualificacao_minima = db.Column(db.String(50))  # ajudante, meio_oficial, oficial, especialista
    ativo = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    # Relacionamentos
    historico_produtividade = db.relationship('HistoricoProdutividadeServico', backref='sub_atividade', lazy=True)

class HistoricoProdutividadeServico(db.Model):
    """Histórico de produtividade coletado via RDO"""
    __tablename__ = 'historico_produtividade_servico'
    
    id = db.Column(db.Integer, primary_key=True)
    servico_id = db.Column(db.Integer, db.ForeignKey('servico.id'), nullable=False)
    sub_atividade_id = db.Column(db.Integer, db.ForeignKey('sub_atividade.id'))
    obra_id = db.Column(db.Integer, db.ForeignKey('obra.id'), nullable=False)
    funcionario_id = db.Column(db.Integer, db.ForeignKey('funcionario.id'), nullable=False)
    data_execucao = db.Column(db.Date, nullable=False)
    quantidade_executada = db.Column(db.Numeric(10, 4), nullable=False)
    tempo_execucao_horas = db.Column(db.Numeric(8, 2), nullable=False)
    custo_mao_obra_real = db.Column(db.Numeric(10, 2), nullable=False)  # calculado automaticamente
    produtividade_hora = db.Column(db.Numeric(8, 4), nullable=False)  # quantidade/hora
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    # Relacionamentos
    obra = db.relationship('Obra', backref='historico_produtividade', lazy=True)
    funcionario = db.relationship('Funcionario', backref='historico_produtividade', lazy=True)

class RegistroPonto(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    funcionario_id = db.Column(db.Integer, db.ForeignKey('funcionario.id'), nullable=False)
    obra_id = db.Column(db.Integer, db.ForeignKey('obra.id'))  # MÓDULO 3: Campo para obras
    data = db.Column(db.Date, nullable=False)
    hora_entrada = db.Column(db.Time)
    hora_saida = db.Column(db.Time)
    hora_almoco_saida = db.Column(db.Time)
    hora_almoco_retorno = db.Column(db.Time)
    
    # MÓDULO 3: Campo tipo_local para integração com gestão de equipes
    tipo_local = db.Column(db.String(20), default='oficina')  # 'oficina', 'campo'
    
    # Cálculos automáticos conforme especificação
    horas_trabalhadas = db.Column(db.Float, default=0.0)
    horas_extras = db.Column(db.Float, default=0.0)
    minutos_atraso_entrada = db.Column(db.Integer, default=0)  # entrada após horário
    minutos_atraso_saida = db.Column(db.Integer, default=0)    # saída antes do horário
    total_atraso_minutos = db.Column(db.Integer, default=0)    # soma dos atrasos
    total_atraso_horas = db.Column(db.Float, default=0.0)      # atrasos em horas
    
    # Campos adicionais
    meio_periodo = db.Column(db.Boolean, default=False)
    saida_antecipada = db.Column(db.Boolean, default=False)
    tipo_registro = db.Column(db.String(30), default='trabalhado')  # trabalhado, falta, falta_justificada, feriado, feriado_trabalhado, sabado_horas_extras, domingo_horas_extras
    percentual_extras = db.Column(db.Float, default=0.0)  # percentual de horas extras configurável
    observacoes = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relacionamentos são definidos via backref nos modelos principais

# Novos modelos conforme especificação v3.0
class TipoOcorrencia(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    nome = db.Column(db.String(50), unique=True, nullable=False)  # Atestado Médico, Atraso Justificado, etc.
    descricao = db.Column(db.Text)
    requer_documento = db.Column(db.Boolean, default=False)
    afeta_custo = db.Column(db.Boolean, default=False)  # se deve ser incluído no custo mensal
    ativo = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

class Ocorrencia(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    funcionario_id = db.Column(db.Integer, db.ForeignKey('funcionario.id'), nullable=False)
    tipo_ocorrencia_id = db.Column(db.Integer, db.ForeignKey('tipo_ocorrencia.id'), nullable=False)
    data_inicio = db.Column(db.Date, nullable=False)
    data_fim = db.Column(db.Date)
    status = db.Column(db.String(20), default='Pendente')  # Pendente, Aprovado, Rejeitado
    descricao = db.Column(db.Text)
    documento_anexo = db.Column(db.String(500))  # caminho para arquivo anexo
    aprovado_por = db.Column(db.Integer, db.ForeignKey('usuario.id'))
    data_aprovacao = db.Column(db.DateTime)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    # Relacionamentos
    funcionario = db.relationship('Funcionario', backref='ocorrencias', lazy=True, overlaps="ocorrencias")
    tipo_ocorrencia = db.relationship('TipoOcorrencia', backref='ocorrencias', lazy=True, overlaps="ocorrencias")
    aprovador = db.relationship('Usuario', backref='ocorrencias_aprovadas', lazy=True, overlaps="ocorrencias_aprovadas")

# ===== MÓDULO 3: GESTÃO DE EQUIPES - SISTEMAS KANBAN/CALENDÁRIO =====

class CalendarioUtil(db.Model):
    data = db.Column(db.Date, primary_key=True)
    dia_semana = db.Column(db.Integer)  # 1=Segunda, 7=Domingo
    eh_util = db.Column(db.Boolean, default=True)
    eh_feriado = db.Column(db.Boolean, default=False)
    descricao_feriado = db.Column(db.String(100))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

class CustoObra(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    obra_id = db.Column(db.Integer, db.ForeignKey('obra.id'), nullable=False)
    centro_custo_id = db.Column(db.Integer, db.ForeignKey('centro_custo.id'))
    tipo = db.Column(db.String(20), nullable=False)  # 'mao_obra', 'material', 'servico', 'veiculo', 'alimentacao'
    descricao = db.Column(db.String(200), nullable=False)
    valor = db.Column(db.Float, nullable=False)
    data = db.Column(db.Date, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    # Relacionamentos
    obra = db.relationship('Obra', overlaps="custos,obra_ref")
    centro_custo_ref = db.relationship('CentroCusto', backref='custos')

# Novos modelos para Gestão Financeira Avançada

class CentroCusto(db.Model):
    """Centros de custo para classificação financeira"""
    __tablename__ = 'centro_custo'
    
    id = db.Column(db.Integer, primary_key=True)
    codigo = db.Column(db.String(20), unique=True, nullable=False)  # CC001, CC002, etc.
    nome = db.Column(db.String(100), nullable=False)
    descricao = db.Column(db.Text)
    tipo = db.Column(db.String(20), nullable=False)  # 'obra', 'departamento', 'projeto', 'atividade'
    ativo = db.Column(db.Boolean, default=True)
    obra_id = db.Column(db.Integer, db.ForeignKey('obra.id'))  # Associação opcional com obra
    departamento_id = db.Column(db.Integer, db.ForeignKey('departamento.id'))  # Associação opcional com departamento
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    # Relacionamentos
    obra = db.relationship('Obra', overlaps="centros_custo_lista")
    departamento = db.relationship('Departamento', overlaps="centros_custo_lista")

class Receita(db.Model):
    """Registro de receitas da empresa"""
    __tablename__ = 'receita'
    
    id = db.Column(db.Integer, primary_key=True)
    numero_receita = db.Column(db.String(20), unique=True, nullable=False)  # REC001, REC002, etc.
    obra_id = db.Column(db.Integer, db.ForeignKey('obra.id'))
    centro_custo_id = db.Column(db.Integer, db.ForeignKey('centro_custo.id'))
    origem = db.Column(db.String(50), nullable=False)  # 'obra', 'servico', 'venda', 'outros'
    descricao = db.Column(db.String(200), nullable=False)
    valor = db.Column(db.Float, nullable=False)
    data_receita = db.Column(db.Date, nullable=False)
    data_recebimento = db.Column(db.Date)  # Data real do recebimento
    status = db.Column(db.String(20), default='Pendente')  # 'Pendente', 'Recebido', 'Cancelado'
    forma_recebimento = db.Column(db.String(30))  # 'Dinheiro', 'Transferência', 'Cartão', 'Cheque'
    observacoes = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    # Relacionamentos
    obra = db.relationship('Obra', overlaps="receitas_lista")
    centro_custo = db.relationship('CentroCusto', overlaps="receitas_lista")

class OrcamentoObra(db.Model):
    """Orçamento planejado vs. realizado por obra"""
    __tablename__ = 'orcamento_obra'
    
    id = db.Column(db.Integer, primary_key=True)
    obra_id = db.Column(db.Integer, db.ForeignKey('obra.id'), nullable=True)
    categoria = db.Column(db.String(30), nullable=False)  # 'mao_obra', 'material', 'equipamento', 'outros'
    orcamento_planejado = db.Column(db.Float, nullable=False, default=0.0)
    custo_realizado = db.Column(db.Float, default=0.0)
    receita_planejada = db.Column(db.Float, default=0.0)
    receita_realizada = db.Column(db.Float, default=0.0)
    data_atualizacao = db.Column(db.DateTime, default=datetime.utcnow)
    observacoes = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    # Relacionamentos
    obra = db.relationship('Obra', overlaps="orcamentos_lista")
    
    @property
    def desvio_custo(self):
        """Calcula o desvio percentual do custo"""
        if self.orcamento_planejado > 0:
            return ((self.custo_realizado - self.orcamento_planejado) / self.orcamento_planejado) * 100
        return 0.0
    
    @property
    def desvio_receita(self):
        """Calcula o desvio percentual da receita"""
        if self.receita_planejada > 0:
            return ((self.receita_realizada - self.receita_planejada) / self.receita_planejada) * 100
        return 0.0

class FluxoCaixa(db.Model):
    """Movimentações de fluxo de caixa consolidadas"""
    __tablename__ = 'fluxo_caixa'
    
    id = db.Column(db.Integer, primary_key=True)
    data_movimento = db.Column(db.Date, nullable=False)
    tipo_movimento = db.Column(db.String(10), nullable=False)  # 'ENTRADA', 'SAIDA'
    categoria = db.Column(db.String(30), nullable=False)  # 'receita', 'custo_obra', 'custo_veiculo', 'alimentacao', 'salario'
    valor = db.Column(db.Float, nullable=False)
    descricao = db.Column(db.String(200), nullable=False)
    obra_id = db.Column(db.Integer, db.ForeignKey('obra.id'))
    centro_custo_id = db.Column(db.Integer, db.ForeignKey('centro_custo.id'))
    referencia_id = db.Column(db.Integer)  # ID da tabela de origem (receita, custo_obra, etc.)
    referencia_tabela = db.Column(db.String(30))  # Nome da tabela de origem
    observacoes = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    # Relacionamentos
    obra = db.relationship('Obra', overlaps="movimentos_caixa_lista")
    centro_custo = db.relationship('CentroCusto', overlaps="movimentos_caixa_lista")

class RegistroAlimentacao(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    funcionario_id = db.Column(db.Integer, db.ForeignKey('funcionario.id'), nullable=False)
    obra_id = db.Column(db.Integer, db.ForeignKey('obra.id'))
    restaurante_id = db.Column(db.Integer, db.ForeignKey('restaurante.id'))
    data = db.Column(db.Date, nullable=False)
    tipo = db.Column(db.String(20), nullable=False)  # 'cafe', 'almoco', 'jantar', 'lanche'
    valor = db.Column(db.Float, nullable=False)
    observacoes = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    # Relacionamentos
    funcionario_ref = db.relationship('Funcionario', overlaps="registros_alimentacao")
    obra_ref = db.relationship('Obra', overlaps="registros_alimentacao") 
    restaurante_ref = db.relationship('Restaurante', overlaps="registros_alimentacao")

# Modelo removido - duplicata


class RDO(db.Model):
    __tablename__ = 'rdo'
    
    id = db.Column(db.Integer, primary_key=True)
    numero_rdo = db.Column(db.String(20), unique=True, nullable=False)  # Auto-gerado
    data_relatorio = db.Column(db.Date, nullable=False)
    obra_id = db.Column(db.Integer, db.ForeignKey('obra.id'), nullable=False)
    criado_por_id = db.Column(db.Integer, db.ForeignKey('usuario.id'), nullable=False)
    
    # Condições climáticas
    tempo_manha = db.Column(db.String(50))
    tempo_tarde = db.Column(db.String(50))
    tempo_noite = db.Column(db.String(50))
    observacoes_meteorologicas = db.Column(db.Text)
    
    # Comentários gerais
    comentario_geral = db.Column(db.Text)
    
    # Status e controle
    status = db.Column(db.String(20), default='Rascunho')  # Rascunho, Finalizado
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relacionamentos
    obra = db.relationship('Obra', backref='rdos', overlaps="rdos")
    criado_por = db.relationship('Usuario', backref='rdos_criados', overlaps="rdos_criados")
    mao_obra = db.relationship('RDOMaoObra', backref='rdo_ref', cascade='all, delete-orphan', overlaps="rdo_ref")
    equipamentos = db.relationship('RDOEquipamento', backref='rdo_ref', cascade='all, delete-orphan', overlaps="rdo_ref")
    atividades = db.relationship('RDOAtividade', backref='rdo_ref', cascade='all, delete-orphan', overlaps="rdo_ref")
    ocorrencias_rdo = db.relationship('RDOOcorrencia', backref='rdo_ref', cascade='all, delete-orphan', overlaps="rdo_ref")
    fotos = db.relationship('RDOFoto', backref='rdo_ref', cascade='all, delete-orphan', overlaps="rdo_ref")
    
    def __repr__(self):
        return f'<RDO {self.numero_rdo}>'


class RDOMaoObra(db.Model):
    __tablename__ = 'rdo_mao_obra'
    
    id = db.Column(db.Integer, primary_key=True)
    rdo_id = db.Column(db.Integer, db.ForeignKey('rdo.id'), nullable=False)
    funcionario_id = db.Column(db.Integer, db.ForeignKey('funcionario.id'), nullable=False)
    funcao_exercida = db.Column(db.String(100), nullable=False)
    horas_trabalhadas = db.Column(db.Float, nullable=False)
    
    # Relacionamentos
    funcionario = db.relationship('Funcionario', backref='rdos_mao_obra', overlaps="rdos_mao_obra")


class RDOEquipamento(db.Model):
    __tablename__ = 'rdo_equipamento'
    
    id = db.Column(db.Integer, primary_key=True)
    rdo_id = db.Column(db.Integer, db.ForeignKey('rdo.id'), nullable=False)
    nome_equipamento = db.Column(db.String(100), nullable=False)
    quantidade = db.Column(db.Integer, nullable=False)
    horas_uso = db.Column(db.Float, nullable=False)
    estado_conservacao = db.Column(db.String(50), nullable=False)


class RDOAtividade(db.Model):
    __tablename__ = 'rdo_atividade'
    
    id = db.Column(db.Integer, primary_key=True)
    rdo_id = db.Column(db.Integer, db.ForeignKey('rdo.id'), nullable=False)
    descricao_atividade = db.Column(db.Text, nullable=False)
    percentual_conclusao = db.Column(db.Float, nullable=False)  # 0-100
    observacoes_tecnicas = db.Column(db.Text)


class RDOOcorrencia(db.Model):
    __tablename__ = 'rdo_ocorrencia'
    
    id = db.Column(db.Integer, primary_key=True)
    rdo_id = db.Column(db.Integer, db.ForeignKey('rdo.id'), nullable=False)
    descricao_ocorrencia = db.Column(db.Text, nullable=False)
    problemas_identificados = db.Column(db.Text)
    acoes_corretivas = db.Column(db.Text)


class RDOFoto(db.Model):
    __tablename__ = 'rdo_foto'
    
    id = db.Column(db.Integer, primary_key=True)
    rdo_id = db.Column(db.Integer, db.ForeignKey('rdo.id'), nullable=False)
    nome_arquivo = db.Column(db.String(255), nullable=False)
    caminho_arquivo = db.Column(db.String(500), nullable=False)
    legenda = db.Column(db.Text)
    uploaded_at = db.Column(db.DateTime, default=datetime.utcnow)


# Novos modelos para funcionalidades aprimoradas
class Restaurante(db.Model):
    """Modelo para restaurantes/fornecedores de alimentação"""
    __tablename__ = 'restaurante'
    
    id = db.Column(db.Integer, primary_key=True)
    nome = db.Column(db.String(100), nullable=False)
    endereco = db.Column(db.Text)
    telefone = db.Column(db.String(20))
    email = db.Column(db.String(120))
    ativo = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    responsavel = db.Column(db.String(100))  # Campo adicionado
    preco_almoco = db.Column(db.Float, default=0.0)  # Campo adicionado
    preco_jantar = db.Column(db.Float, default=0.0)  # Campo adicionado
    preco_lanche = db.Column(db.Float, default=0.0)  # Campo adicionado
    admin_id = db.Column(db.Integer, db.ForeignKey('usuario.id'), nullable=True)  # Multi-tenant
    
    # Relacionamentos
    registros_alimentacao = db.relationship('RegistroAlimentacao', lazy=True, overlaps="restaurante_ref")
    
    def __repr__(self):
        return f'<Restaurante {self.nome}>'


class UsoVeiculo(db.Model):
    """Modelo para registro de uso de veículos"""
    __tablename__ = 'uso_veiculo'
    
    id = db.Column(db.Integer, primary_key=True)
    veiculo_id = db.Column(db.Integer, db.ForeignKey('veiculo.id'), nullable=False)
    funcionario_id = db.Column(db.Integer, db.ForeignKey('funcionario.id'), nullable=False)
    obra_id = db.Column(db.Integer, db.ForeignKey('obra.id'), nullable=False)
    data_uso = db.Column(db.Date, nullable=False)
    km_inicial = db.Column(db.Integer)
    km_final = db.Column(db.Integer)
    horario_saida = db.Column(db.Time)
    horario_chegada = db.Column(db.Time)
    finalidade = db.Column(db.String(200))
    observacoes = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    # Relacionamentos
    veiculo = db.relationship('Veiculo', backref='usos', overlaps="usos")
    funcionario = db.relationship('Funcionario', backref='usos_veiculo', overlaps="usos_veiculo")
    obra = db.relationship('Obra', backref='usos_veiculo', overlaps="usos_veiculo")
    
    def __repr__(self):
        return f'<UsoVeiculo {self.veiculo_id} - {self.funcionario_id}>'


class CustoVeiculo(db.Model):
    """Modelo para custos de veículos"""
    __tablename__ = 'custo_veiculo'
    
    id = db.Column(db.Integer, primary_key=True)
    veiculo_id = db.Column(db.Integer, db.ForeignKey('veiculo.id'), nullable=False)
    obra_id = db.Column(db.Integer, db.ForeignKey('obra.id'), nullable=False)  # Obra associada ao custo
    data_custo = db.Column(db.Date, nullable=False)
    valor = db.Column(db.Float, nullable=False)
    tipo_custo = db.Column(db.String(50), nullable=False)  # 'combustivel', 'manutencao', 'seguro', 'outros'
    descricao = db.Column(db.Text)
    km_atual = db.Column(db.Integer)
    fornecedor = db.Column(db.String(100))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    # Relacionamentos
    veiculo = db.relationship('Veiculo', backref='custos_veiculo', overlaps="custos_veiculo")
    obra = db.relationship('Obra', backref='custos_veiculo', overlaps="custos_veiculo")
    
    def __repr__(self):
        return f'<CustoVeiculo {self.veiculo_id} - {self.valor}>'

class OutroCusto(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    funcionario_id = db.Column(db.Integer, db.ForeignKey('funcionario.id'), nullable=False)
    data = db.Column(db.Date, nullable=False)
    tipo = db.Column(db.String(30), nullable=False)  # 'vale_transporte', 'vale_alimentacao', 'desconto_vt', 'desconto_outras'
    categoria = db.Column(db.String(20), nullable=False)  # 'adicional' ou 'desconto'
    valor = db.Column(db.Float, nullable=False)
    descricao = db.Column(db.Text)
    obra_id = db.Column(db.Integer, db.ForeignKey('obra.id'))
    percentual = db.Column(db.Float)  # Para descontos percentuais (ex: 6% do salário)
    
    # FUNCIONALIDADE MULTI-TENANT: admin_id para isolamento de dados
    admin_id = db.Column(db.Integer, db.ForeignKey('usuario.id'), nullable=True)  # Para compatibilidade, permitir NULL inicialmente
    
    # NOVA FUNCIONALIDADE: Associação com KPIs específicos
    kpi_associado = db.Column(db.String(30), default='outros_custos')  # 'custo_alimentacao', 'custo_transporte', 'outros_custos'
    
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    funcionario = db.relationship('Funcionario', backref='outros_custos')
    obra = db.relationship('Obra', backref='outros_custos')
    admin = db.relationship('Usuario', backref='outros_custos_criados')
    
    def __repr__(self):
        return f'<OutroCusto {self.funcionario.nome} - {self.tipo} R$ {self.valor}>'

# ================================
# MÓDULO DE PROPOSTAS COMERCIAIS
# ================================

class PropostaComercial(db.Model):
    __tablename__ = 'proposta_comercial'
    
    id = db.Column(db.Integer, primary_key=True)
    numero_proposta = db.Column(db.String(20), unique=True, nullable=False)
    
    # Dados do Cliente
    cliente_nome = db.Column(db.String(100), nullable=False)
    cliente_email = db.Column(db.String(120), nullable=False)
    cliente_telefone = db.Column(db.String(20))
    cliente_cpf_cnpj = db.Column(db.String(18))
    
    # Dados da Obra
    endereco_obra = db.Column(db.Text, nullable=False)
    descricao_obra = db.Column(db.Text, nullable=False)
    area_total_m2 = db.Column(db.Float)
    
    # Valores
    valor_proposta = db.Column(db.Float, nullable=False)
    prazo_execucao = db.Column(db.Integer)  # dias
    
    # Status e Controle
    status = db.Column(db.String(20), default='Enviada')
    data_criacao = db.Column(db.DateTime, default=datetime.utcnow)
    data_envio = db.Column(db.DateTime)
    data_resposta = db.Column(db.DateTime)
    data_expiracao = db.Column(db.DateTime)
    
    # Acesso do Cliente
    token_acesso = db.Column(db.String(255), unique=True)
    
    # Resposta do Cliente
    observacoes_cliente = db.Column(db.Text)
    ip_assinatura = db.Column(db.String(45))
    user_agent_assinatura = db.Column(db.Text)
    
    # Multi-tenant
    admin_id = db.Column(db.Integer, db.ForeignKey('usuario.id'), nullable=False)
    criado_por_id = db.Column(db.Integer, db.ForeignKey('usuario.id'), nullable=False)
    
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relacionamentos
    servicos = db.relationship('ServicoPropostaComercial', backref='proposta_ref', lazy=True, cascade='all, delete-orphan')
    admin = db.relationship('Usuario', foreign_keys=[admin_id])
    criado_por = db.relationship('Usuario', foreign_keys=[criado_por_id])

class ServicoPropostaComercial(db.Model):
    __tablename__ = 'servico_proposta_comercial'
    
    id = db.Column(db.Integer, primary_key=True)
    proposta_id = db.Column(db.Integer, db.ForeignKey('proposta_comercial.id'), nullable=False)
    descricao_servico = db.Column(db.String(200), nullable=False)
    quantidade = db.Column(db.Float, nullable=False)
    unidade = db.Column(db.String(10), nullable=False)
    valor_unitario = db.Column(db.Float, nullable=False)
    valor_total = db.Column(db.Float, nullable=False)
    observacoes = db.Column(db.Text)
    ordem = db.Column(db.Integer, default=1)
    
    def __repr__(self):
        return f'<ServicoPropostaComercial {self.descricao_servico}>'


# ================================
# MÓDULO 3: GESTÃO DE EQUIPES
# ================================

class AlocacaoEquipe(db.Model):
    """Sistema completo de alocação de equipes - MÓDULO 3 v8.0"""
    __tablename__ = 'alocacao_equipe'
    
    id = db.Column(db.Integer, primary_key=True)
    
    # Relacionamentos principais
    funcionario_id = db.Column(db.Integer, db.ForeignKey('funcionario.id'), nullable=False)
    obra_id = db.Column(db.Integer, db.ForeignKey('obra.id'), nullable=False)
    
    # Dados da alocação
    data_alocacao = db.Column(db.Date, nullable=False)
    tipo_local = db.Column(db.String(20), nullable=False)  # 'oficina', 'campo'
    turno = db.Column(db.String(20), default='matutino')  # 'matutino', 'vespertino', 'noturno'
    
    # Controle e auditoria avançado (conforme reunião técnica)
    criado_por_id = db.Column(db.Integer, db.ForeignKey('usuario.id'), nullable=False)
    rdo_gerado_id = db.Column(db.Integer, db.ForeignKey('rdo.id'))  # NULL se for oficina
    rdo_gerado = db.Column(db.Boolean, default=False)  # Flag para compatibilidade
    
    # Status da alocação
    status = db.Column(db.String(20), default='Planejado')  # 'Planejado', 'Executado', 'Cancelado'
    prioridade = db.Column(db.String(20), default='Normal')  # 'Alta', 'Normal', 'Baixa'
    
    # Validações e controle de conflitos
    validacao_conflito = db.Column(db.Boolean, default=False)  # Se foi validado contra conflitos
    motivo_cancelamento = db.Column(db.Text)  # Motivo se cancelado
    
    # Observações
    observacoes = db.Column(db.Text)
    
    # Multi-tenant (OBRIGATÓRIO)
    admin_id = db.Column(db.Integer, db.ForeignKey('usuario.id'), nullable=False)
    
    # Controle de tempo
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relacionamentos
    funcionario = db.relationship('Funcionario', backref='alocacoes_equipe')
    obra = db.relationship('Obra', backref='alocacoes_equipe')
    criado_por = db.relationship('Usuario', foreign_keys=[criado_por_id], backref='alocacoes_criadas')
    admin = db.relationship('Usuario', foreign_keys=[admin_id], backref='alocacoes_administradas')
    rdo_gerado_rel = db.relationship('RDO', backref='alocacao_origem')
    
    # Índices para performance e unicidade
    __table_args__ = (
        db.UniqueConstraint('funcionario_id', 'data_alocacao', name='uk_funcionario_data_alocacao'),
        db.Index('idx_alocacao_data_admin', 'data_alocacao', 'admin_id'),
        db.Index('idx_alocacao_obra_data', 'obra_id', 'data_alocacao'),
        db.Index('idx_alocacao_funcionario_status', 'funcionario_id', 'status'),
    )
    
    def __repr__(self):
        func_nome = self.funcionario.nome if self.funcionario else f"ID:{self.funcionario_id}"
        obra_nome = self.obra.nome if self.obra else f"ID:{self.obra_id}"
        return f'<AlocacaoEquipe {func_nome} -> {obra_nome} ({self.data_alocacao})>'
    
    def to_dict(self):
        """Converter para dicionário para APIs do sistema Kanban/Calendário"""
        return {
            'id': self.id,
            'funcionario_id': self.funcionario_id,
            'funcionario_nome': self.funcionario.nome if self.funcionario else None,
            'funcionario_cargo': self.funcionario.cargo if self.funcionario else None,
            'obra_id': self.obra_id,
            'obra_nome': self.obra.nome if self.obra else None,
            'obra_codigo': self.obra.codigo if self.obra else None,
            'data_alocacao': self.data_alocacao.isoformat(),
            'tipo_local': self.tipo_local,
            'turno': self.turno,
            'status': self.status,
            'prioridade': self.prioridade,
            'rdo_gerado': self.rdo_gerado,
            'rdo_gerado_id': self.rdo_gerado_id,
            'rdo_numero': self.rdo_gerado_rel.numero_rdo if self.rdo_gerado_rel else None,
            'validacao_conflito': self.validacao_conflito,
            'observacoes': self.observacoes,
            'motivo_cancelamento': self.motivo_cancelamento,
            'created_at': self.created_at.isoformat() if self.created_at else None
        }
    
    def pode_ser_cancelada(self):
        """Verifica se a alocação pode ser cancelada"""
        from datetime import date
        return self.status == 'Planejado' and self.data_alocacao >= date.today()
    
    def gerar_numero_rdo_automatico(self):
        """Gera número de RDO conforme especificação da reunião técnica"""
        if not self.obra:
            return None
        
        data_str = self.data_alocacao.strftime('%Y%m%d')
        codigo_obra = self.obra.codigo or f'OBR{self.obra.id:03d}'
        
        # Buscar último RDO do dia para esta obra
        ultimo_rdo = RDO.query.filter(
            RDO.obra_id == self.obra_id,
            RDO.numero_rdo.like(f'RDO-{codigo_obra}-{data_str}%')
        ).order_by(RDO.numero_rdo.desc()).first()
        
        if ultimo_rdo:
            try:
                ultimo_numero = int(ultimo_rdo.numero_rdo.split('-')[-1])
                novo_numero = ultimo_numero + 1
            except:
                novo_numero = 1
        else:
            novo_numero = 1
        
        return f"RDO-{codigo_obra}-{data_str}-{novo_numero:03d}"


# ================================
# MÓDULO 4: ALMOXARIFADO INTELIGENTE
# ================================

from decimal import Decimal
import xml.etree.ElementTree as ET

class CategoriaProduto(db.Model):
    """Categorias de produtos para organização do almoxarifado"""
    __tablename__ = 'categoria_produto'
    
    id = db.Column(db.Integer, primary_key=True)
    nome = db.Column(db.String(100), nullable=False)
    descricao = db.Column(db.Text)
    codigo = db.Column(db.String(10), nullable=False)  # CIM, ELE, HID, etc.
    cor_hex = db.Column(db.String(7), default='#007bff')  # Para interface visual
    
    # Multi-tenant (OBRIGATÓRIO)
    admin_id = db.Column(db.Integer, db.ForeignKey('usuario.id'), nullable=False)
    
    # Controle de tempo
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relacionamentos
    produtos = db.relationship('Produto', backref='categoria_produto', lazy='dynamic')
    admin = db.relationship('Usuario', backref='categorias_administradas')
    
    # Índices
    __table_args__ = (
        db.UniqueConstraint('codigo', 'admin_id', name='uk_categoria_codigo_admin'),
        db.Index('idx_categoria_admin_codigo', 'admin_id', 'codigo'),
    )
    
    def __repr__(self):
        return f'<CategoriaProduto {self.nome}>'

class Fornecedor(db.Model):
    """Fornecedores para controle de compras e notas fiscais"""
    __tablename__ = 'fornecedor'
    
    id = db.Column(db.Integer, primary_key=True)
    razao_social = db.Column(db.String(200), nullable=False)
    nome_fantasia = db.Column(db.String(200))
    cnpj = db.Column(db.String(18), nullable=False)
    inscricao_estadual = db.Column(db.String(20))
    
    # Endereço
    endereco = db.Column(db.Text)
    cidade = db.Column(db.String(100))
    estado = db.Column(db.String(2))
    cep = db.Column(db.String(10))
    
    # Contato
    telefone = db.Column(db.String(20))
    email = db.Column(db.String(100))
    contato_responsavel = db.Column(db.String(100))
    
    # Status
    ativo = db.Column(db.Boolean, default=True)
    
    # Multi-tenant (OBRIGATÓRIO)
    admin_id = db.Column(db.Integer, db.ForeignKey('usuario.id'), nullable=False)
    
    # Controle de tempo
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relacionamentos
    notas_fiscais = db.relationship('NotaFiscal', backref='fornecedor', lazy='dynamic')
    admin = db.relationship('Usuario', backref='fornecedores_administrados')
    
    # Índices
    __table_args__ = (
        db.UniqueConstraint('cnpj', 'admin_id', name='uk_fornecedor_cnpj_admin'),
        db.Index('idx_fornecedor_admin_ativo', 'admin_id', 'ativo'),
    )
    
    def __repr__(self):
        return f'<Fornecedor {self.razao_social}>'
    
    @property
    def cnpj_formatado(self):
        """Retorna CNPJ formatado"""
        if len(self.cnpj) == 14:
            return f"{self.cnpj[:2]}.{self.cnpj[2:5]}.{self.cnpj[5:8]}/{self.cnpj[8:12]}-{self.cnpj[12:]}"
        return self.cnpj

class Produto(db.Model):
    """Produtos/materiais do almoxarifado com controle completo"""
    __tablename__ = 'produto'
    
    id = db.Column(db.Integer, primary_key=True)
    codigo_interno = db.Column(db.String(20), nullable=False)
    codigo_barras = db.Column(db.String(50))
    nome = db.Column(db.String(200), nullable=False)
    descricao = db.Column(db.Text)
    
    # Classificação
    categoria_id = db.Column(db.Integer, db.ForeignKey('categoria_produto.id'), nullable=False)
    
    # Unidades e medidas
    unidade_medida = db.Column(db.String(10), nullable=False)  # UN, KG, M, L, M2, M3, etc.
    peso_unitario = db.Column(db.Numeric(10,3))  # Para cálculos de frete
    dimensoes = db.Column(db.String(50))  # Ex: "10x20x30 cm"
    
    # Controle de estoque
    estoque_minimo = db.Column(db.Numeric(10,3), default=0)
    estoque_maximo = db.Column(db.Numeric(10,3))
    estoque_atual = db.Column(db.Numeric(10,3), default=0)
    estoque_reservado = db.Column(db.Numeric(10,3), default=0)  # Para futuras funcionalidades
    
    # Valores
    valor_medio = db.Column(db.Numeric(10,2), default=0)  # Calculado automaticamente
    ultimo_valor_compra = db.Column(db.Numeric(10,2))
    
    # Status e controle
    ativo = db.Column(db.Boolean, default=True)
    critico = db.Column(db.Boolean, default=False)  # Material crítico para obras
    
    # Multi-tenant (OBRIGATÓRIO)
    admin_id = db.Column(db.Integer, db.ForeignKey('usuario.id'), nullable=False)
    
    # Controle de tempo
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relacionamentos
    categoria = db.relationship('CategoriaProduto', foreign_keys=[categoria_id], overlaps="categoria_produto,produtos")
    admin = db.relationship('Usuario', foreign_keys=[admin_id], backref='produtos_administrados')
    
    # Índices
    __table_args__ = (
        db.UniqueConstraint('codigo_interno', 'admin_id', name='uk_produto_codigo_admin'),
        db.Index('idx_produto_codigo_barras', 'codigo_barras'),
        db.Index('idx_produto_admin_ativo', 'admin_id', 'ativo'),
        db.Index('idx_produto_categoria', 'categoria_id'),
        db.Index('idx_produto_estoque_baixo', 'admin_id', 'estoque_atual', 'estoque_minimo'),
    )
    
    def __repr__(self):
        return f'<Produto {self.nome}>'
    
    @property
    def estoque_disponivel(self):
        """Estoque disponível (atual - reservado)"""
        return self.estoque_atual - self.estoque_reservado
    
    @property
    def status_estoque(self):
        """Status do estoque: OK, BAIXO, CRITICO, ZERADO"""
        if self.estoque_atual <= 0:
            return 'ZERADO'
        elif self.estoque_atual <= (self.estoque_minimo * 0.5):
            return 'CRITICO'
        elif self.estoque_atual <= self.estoque_minimo:
            return 'BAIXO'
        else:
            return 'OK'
    
    @property
    def valor_estoque_atual(self):
        """Valor total do estoque atual"""
        return self.estoque_atual * self.valor_medio
    
    def to_dict(self):
        """Converter para dicionário para APIs"""
        return {
            'id': self.id,
            'codigo_interno': self.codigo_interno,
            'codigo_barras': self.codigo_barras,
            'nome': self.nome,
            'descricao': self.descricao,
            'categoria': self.categoria.nome if self.categoria else None,
            'unidade_medida': self.unidade_medida,
            'estoque_atual': float(self.estoque_atual),
            'estoque_minimo': float(self.estoque_minimo),
            'valor_medio': float(self.valor_medio),
            'status_estoque': self.status_estoque,
            'ativo': self.ativo
        }

class NotaFiscal(db.Model):
    """Notas fiscais para controle de entrada de materiais"""
    __tablename__ = 'nota_fiscal'
    
    id = db.Column(db.Integer, primary_key=True)
    numero = db.Column(db.String(20), nullable=False)
    serie = db.Column(db.String(5), nullable=False)
    chave_acesso = db.Column(db.String(44), unique=True, nullable=False)
    
    # Fornecedor
    fornecedor_id = db.Column(db.Integer, db.ForeignKey('fornecedor.id'), nullable=False)
    
    # Datas
    data_emissao = db.Column(db.Date, nullable=False)
    data_entrada = db.Column(db.Date)  # Data de entrada no estoque
    
    # Valores
    valor_produtos = db.Column(db.Numeric(10,2), nullable=False)
    valor_frete = db.Column(db.Numeric(10,2), default=0)
    valor_desconto = db.Column(db.Numeric(10,2), default=0)
    valor_total = db.Column(db.Numeric(10,2), nullable=False)
    
    # XML e processamento
    xml_content = db.Column(db.Text)  # Armazenar XML completo
    xml_hash = db.Column(db.String(64))  # Hash para detectar duplicatas
    
    # Status
    status = db.Column(db.String(20), default='Pendente')  # Pendente, Processada, Erro
    observacoes = db.Column(db.Text)
    
    # Controle
    processada_por_id = db.Column(db.Integer, db.ForeignKey('usuario.id'))
    data_processamento = db.Column(db.DateTime)
    
    # Multi-tenant (OBRIGATÓRIO)
    admin_id = db.Column(db.Integer, db.ForeignKey('usuario.id'), nullable=False)
    
    # Controle de tempo
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relacionamentos
    movimentacoes = db.relationship('MovimentacaoEstoque', backref='nota_fiscal', lazy='dynamic')
    processada_por = db.relationship('Usuario', foreign_keys=[processada_por_id])
    admin = db.relationship('Usuario', foreign_keys=[admin_id], backref='notas_fiscais_administradas')
    
    # Índices
    __table_args__ = (
        db.Index('idx_nf_admin_status', 'admin_id', 'status'),
        db.Index('idx_nf_fornecedor_data', 'fornecedor_id', 'data_emissao'),
        db.Index('idx_nf_chave_acesso', 'chave_acesso'),
    )
    
    def __repr__(self):
        return f'<NotaFiscal {self.numero}/{self.serie}>'
    
    @property
    def numero_formatado(self):
        """Número da NF formatado"""
        return f"{self.numero}/{self.serie}"

class MovimentacaoEstoque(db.Model):
    """Movimentações de estoque com rastreabilidade completa"""
    __tablename__ = 'movimentacao_estoque'
    
    id = db.Column(db.Integer, primary_key=True)
    
    # Produto
    produto_id = db.Column(db.Integer, db.ForeignKey('produto.id'), nullable=False)
    
    # Tipo de movimentação
    tipo_movimentacao = db.Column(db.String(20), nullable=False)  # ENTRADA, SAIDA, DEVOLUCAO, AJUSTE
    
    # Quantidades
    quantidade = db.Column(db.Numeric(10,3), nullable=False)
    quantidade_anterior = db.Column(db.Numeric(10,3))  # Para auditoria
    quantidade_posterior = db.Column(db.Numeric(10,3))  # Para auditoria
    
    # Valores
    valor_unitario = db.Column(db.Numeric(10,2))
    valor_total = db.Column(db.Numeric(10,2))
    
    # Data e hora
    data_movimentacao = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    
    # Origem da movimentação (relacionamentos opcionais)
    nota_fiscal_id = db.Column(db.Integer, db.ForeignKey('nota_fiscal.id'))
    rdo_id = db.Column(db.Integer, db.ForeignKey('rdo.id'))
    funcionario_id = db.Column(db.Integer, db.ForeignKey('funcionario.id'))
    obra_id = db.Column(db.Integer, db.ForeignKey('obra.id'))
    
    # Controle e auditoria
    usuario_id = db.Column(db.Integer, db.ForeignKey('usuario.id'), nullable=False)
    observacoes = db.Column(db.Text)
    ip_address = db.Column(db.String(45))
    
    # Multi-tenant (OBRIGATÓRIO)
    admin_id = db.Column(db.Integer, db.ForeignKey('usuario.id'), nullable=False)
    
    # Relacionamentos
    usuario = db.relationship('Usuario', foreign_keys=[usuario_id], backref='movimentacoes_estoque')
    funcionario = db.relationship('Funcionario', backref='movimentacoes_materiais_funcionario')
    obra = db.relationship('Obra', backref='movimentacoes_materiais_obra')
    rdo = db.relationship('RDO', backref='movimentacoes_materiais_rdo')
    
    # Índices
    __table_args__ = (
        db.Index('idx_mov_produto_data', 'produto_id', 'data_movimentacao'),
        db.Index('idx_mov_admin_tipo', 'admin_id', 'tipo_movimentacao'),
        db.Index('idx_mov_obra_data', 'obra_id', 'data_movimentacao'),
        db.Index('idx_mov_funcionario_data', 'funcionario_id', 'data_movimentacao'),
        db.Index('idx_mov_rdo', 'rdo_id'),
        db.Index('idx_mov_nf', 'nota_fiscal_id'),
    )
    
    def __repr__(self):
        return f'<MovimentacaoEstoque {self.tipo_movimentacao} - Produto:{self.produto_id}>'
    
    def to_dict(self):
        """Converter para dicionário para APIs"""
        return {
            'id': self.id,
            'produto_nome': self.produto_rel.nome if hasattr(self, 'produto_rel') and self.produto_rel else None,
            'tipo_movimentacao': self.tipo_movimentacao,
            'quantidade': float(self.quantidade),
            'valor_unitario': float(self.valor_unitario) if self.valor_unitario else None,
            'valor_total': float(self.valor_total) if self.valor_total else None,
            'data_movimentacao': self.data_movimentacao.isoformat(),
            'funcionario_nome': self.funcionario.nome if self.funcionario else None,
            'obra_nome': self.obra.nome if self.obra else None,
            'rdo_numero': self.rdo.numero_rdo if self.rdo else None,
            'usuario_nome': self.usuario.nome if self.usuario else None,
            'observacoes': self.observacoes
        }
    
    # Relacionamentos
    produto_rel = db.relationship('Produto', foreign_keys=[produto_id], overlaps="movimentacoes")


# ================================
# MÓDULO 6: FOLHA DE PAGAMENTO AUTOMÁTICA
# ================================

class ConfiguracaoSalarial(db.Model):
    """Configuração salarial por funcionário"""
    __tablename__ = 'configuracao_salarial'
    
    id = db.Column(db.Integer, primary_key=True)
    funcionario_id = db.Column(db.Integer, db.ForeignKey('funcionario.id'), nullable=False)
    salario_base = db.Column(db.Numeric(10, 2), nullable=False)  # Salário base
    tipo_salario = db.Column(db.String(20), nullable=False)  # MENSAL, HORISTA, COMISSIONADO
    valor_hora = db.Column(db.Numeric(10, 2))  # Para horistas
    percentual_comissao = db.Column(db.Numeric(5, 2))  # Para comissionados
    carga_horaria_mensal = db.Column(db.Integer, default=220)  # Horas/mês padrão
    dependentes = db.Column(db.Integer, default=0)  # Para IRRF
    data_inicio = db.Column(db.Date, nullable=False)
    data_fim = db.Column(db.Date)  # NULL = vigente
    ativo = db.Column(db.Boolean, default=True)
    admin_id = db.Column(db.Integer, db.ForeignKey('usuario.id'), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relacionamentos
    funcionario = db.relationship('Funcionario', backref='configuracoes_salariais')
    admin = db.relationship('Usuario', foreign_keys=[admin_id])
    
    # Índices para performance
    __table_args__ = (
        db.Index('idx_config_salarial_funcionario_ativo', 'funcionario_id', 'ativo'),
        db.Index('idx_config_salarial_admin_id', 'admin_id'),
        db.Index('idx_config_salarial_vigencia', 'data_inicio', 'data_fim'),
    )

class BeneficioFuncionario(db.Model):
    """Benefícios por funcionário"""
    __tablename__ = 'beneficio_funcionario'
    
    id = db.Column(db.Integer, primary_key=True)
    funcionario_id = db.Column(db.Integer, db.ForeignKey('funcionario.id'), nullable=False)
    tipo_beneficio = db.Column(db.String(50), nullable=False)  # VR, VT, PLANO_SAUDE, SEGURO_VIDA, etc.
    valor = db.Column(db.Numeric(10, 2), nullable=False)  # Valor do benefício
    percentual_desconto = db.Column(db.Numeric(5, 2), default=0)  # % descontado do funcionário
    dias_por_mes = db.Column(db.Integer, default=22)  # Para VR/VT
    ativo = db.Column(db.Boolean, default=True)
    data_inicio = db.Column(db.Date, nullable=False)
    data_fim = db.Column(db.Date)  # NULL = vigente
    observacoes = db.Column(db.Text)
    admin_id = db.Column(db.Integer, db.ForeignKey('usuario.id'), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relacionamentos
    funcionario = db.relationship('Funcionario', backref='beneficios')
    admin = db.relationship('Usuario', foreign_keys=[admin_id])
    
    # Índices
    __table_args__ = (
        db.Index('idx_beneficio_funcionario_tipo', 'funcionario_id', 'tipo_beneficio', 'ativo'),
        db.Index('idx_beneficio_admin_id', 'admin_id'),
    )

class CalculoHorasMensal(db.Model):
    """Cálculo de horas mensal baseado nos pontos"""
    __tablename__ = 'calculo_horas_mensal'
    
    id = db.Column(db.Integer, primary_key=True)
    funcionario_id = db.Column(db.Integer, db.ForeignKey('funcionario.id'), nullable=False)
    mes_referencia = db.Column(db.Date, nullable=False)  # Primeiro dia do mês
    
    # Horas trabalhadas
    horas_normais = db.Column(db.Numeric(8, 2), default=0)
    horas_extras_50 = db.Column(db.Numeric(8, 2), default=0)  # Extras 50%
    horas_extras_100 = db.Column(db.Numeric(8, 2), default=0)  # Extras 100%
    horas_noturnas = db.Column(db.Numeric(8, 2), default=0)  # Adicional noturno
    horas_dsr = db.Column(db.Numeric(8, 2), default=0)  # Descanso semanal
    
    # Faltas e atrasos
    faltas_horas = db.Column(db.Numeric(8, 2), default=0)
    atrasos_horas = db.Column(db.Numeric(8, 2), default=0)
    
    # Controle de dias
    dias_trabalhados = db.Column(db.Integer, default=0)
    dias_faltas = db.Column(db.Integer, default=0)
    dias_uteis_mes = db.Column(db.Integer, default=22)
    
    # Controle de processamento
    processado_em = db.Column(db.DateTime, default=datetime.utcnow)
    reprocessado = db.Column(db.Boolean, default=False)
    admin_id = db.Column(db.Integer, db.ForeignKey('usuario.id'), nullable=False)
    
    # Relacionamentos
    funcionario = db.relationship('Funcionario', backref='calculos_horas')
    admin = db.relationship('Usuario', foreign_keys=[admin_id])
    
    # Índices
    __table_args__ = (
        db.Index('idx_calculo_horas_funcionario_mes', 'funcionario_id', 'mes_referencia'),
        db.Index('idx_calculo_horas_admin_id', 'admin_id'),
        db.UniqueConstraint('funcionario_id', 'mes_referencia', name='uk_calculo_horas_funcionario_mes'),
    )

class FolhaPagamento(db.Model):
    """Folha de pagamento mensal por funcionário"""
    __tablename__ = 'folha_pagamento'
    
    id = db.Column(db.Integer, primary_key=True)
    funcionario_id = db.Column(db.Integer, db.ForeignKey('funcionario.id'), nullable=False)
    mes_referencia = db.Column(db.Date, nullable=False)  # Primeiro dia do mês
    
    # PROVENTOS
    salario_base = db.Column(db.Numeric(10, 2), default=0)
    horas_extras = db.Column(db.Numeric(10, 2), default=0)
    adicional_noturno = db.Column(db.Numeric(10, 2), default=0)
    dsr = db.Column(db.Numeric(10, 2), default=0)  # Descanso semanal remunerado
    comissoes = db.Column(db.Numeric(10, 2), default=0)
    bonus = db.Column(db.Numeric(10, 2), default=0)
    outros_proventos = db.Column(db.Numeric(10, 2), default=0)
    total_proventos = db.Column(db.Numeric(10, 2), default=0)
    
    # DESCONTOS OBRIGATÓRIOS
    inss = db.Column(db.Numeric(10, 2), default=0)
    irrf = db.Column(db.Numeric(10, 2), default=0)
    fgts = db.Column(db.Numeric(10, 2), default=0)  # Não é desconto, mas é calculado
    
    # DESCONTOS DE BENEFÍCIOS
    vale_refeicao = db.Column(db.Numeric(10, 2), default=0)
    vale_transporte = db.Column(db.Numeric(10, 2), default=0)
    plano_saude = db.Column(db.Numeric(10, 2), default=0)
    seguro_vida = db.Column(db.Numeric(10, 2), default=0)
    
    # DESCONTOS POR FALTAS/ATRASOS
    faltas = db.Column(db.Numeric(10, 2), default=0)
    atrasos = db.Column(db.Numeric(10, 2), default=0)
    
    # OUTROS DESCONTOS
    adiantamentos = db.Column(db.Numeric(10, 2), default=0)
    emprestimos = db.Column(db.Numeric(10, 2), default=0)
    outros_descontos = db.Column(db.Numeric(10, 2), default=0)
    total_descontos = db.Column(db.Numeric(10, 2), default=0)
    
    # LÍQUIDO
    salario_liquido = db.Column(db.Numeric(10, 2), default=0)
    
    # CONTROLE
    status = db.Column(db.String(20), default='CALCULADO')  # CALCULADO, APROVADO, PAGO
    calculado_em = db.Column(db.DateTime, default=datetime.utcnow)
    aprovado_em = db.Column(db.DateTime)
    aprovado_por = db.Column(db.Integer, db.ForeignKey('usuario.id'))
    pago_em = db.Column(db.DateTime)
    observacoes = db.Column(db.Text)
    admin_id = db.Column(db.Integer, db.ForeignKey('usuario.id'), nullable=False)
    
    # Relacionamentos
    funcionario = db.relationship('Funcionario', backref='folhas_pagamento')
    aprovador = db.relationship('Usuario', foreign_keys=[aprovado_por])
    admin = db.relationship('Usuario', foreign_keys=[admin_id])
    
    # Índices
    __table_args__ = (
        db.Index('idx_folha_funcionario_mes', 'funcionario_id', 'mes_referencia'),
        db.Index('idx_folha_admin_status', 'admin_id', 'status'),
        db.Index('idx_folha_mes_referencia', 'mes_referencia'),
        db.UniqueConstraint('funcionario_id', 'mes_referencia', name='uk_folha_funcionario_mes'),
    )

class LancamentoRecorrente(db.Model):
    """Lançamentos recorrentes mensais"""
    __tablename__ = 'lancamento_recorrente'
    
    id = db.Column(db.Integer, primary_key=True)
    funcionario_id = db.Column(db.Integer, db.ForeignKey('funcionario.id'), nullable=False)
    tipo = db.Column(db.String(20), nullable=False)  # PROVENTO, DESCONTO
    descricao = db.Column(db.String(100), nullable=False)
    valor = db.Column(db.Numeric(10, 2))  # Valor fixo
    percentual = db.Column(db.Numeric(5, 2))  # Percentual do salário
    dia_vencimento = db.Column(db.Integer, default=1)  # Dia do mês para processar
    ativo = db.Column(db.Boolean, default=True)
    data_inicio = db.Column(db.Date, nullable=False)
    data_fim = db.Column(db.Date)  # NULL = sem fim
    observacoes = db.Column(db.Text)
    admin_id = db.Column(db.Integer, db.ForeignKey('usuario.id'), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relacionamentos
    funcionario = db.relationship('Funcionario', backref='lancamentos_recorrentes')
    admin = db.relationship('Usuario', foreign_keys=[admin_id])
    
    # Índices
    __table_args__ = (
        db.Index('idx_lancamento_funcionario_ativo', 'funcionario_id', 'ativo'),
        db.Index('idx_lancamento_admin_id', 'admin_id'),
    )

class Adiantamento(db.Model):
    """Adiantamentos salariais"""
    __tablename__ = 'adiantamento'
    
    id = db.Column(db.Integer, primary_key=True)
    funcionario_id = db.Column(db.Integer, db.ForeignKey('funcionario.id'), nullable=False)
    valor_total = db.Column(db.Numeric(10, 2), nullable=False)
    data_solicitacao = db.Column(db.Date, nullable=False)
    data_aprovacao = db.Column(db.Date)
    aprovado_por = db.Column(db.Integer, db.ForeignKey('usuario.id'))
    
    # Parcelamento
    parcelas = db.Column(db.Integer, default=1)
    valor_parcela = db.Column(db.Numeric(10, 2))
    parcelas_pagas = db.Column(db.Integer, default=0)
    
    # Controle
    status = db.Column(db.String(20), default='SOLICITADO')  # SOLICITADO, APROVADO, QUITADO, CANCELADO
    motivo = db.Column(db.String(200))
    observacoes = db.Column(db.Text)
    admin_id = db.Column(db.Integer, db.ForeignKey('usuario.id'), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relacionamentos
    funcionario = db.relationship('Funcionario', backref='adiantamentos')
    aprovador = db.relationship('Usuario', foreign_keys=[aprovado_por])
    admin = db.relationship('Usuario', foreign_keys=[admin_id])
    
    # Índices
    __table_args__ = (
        db.Index('idx_adiantamento_funcionario_status', 'funcionario_id', 'status'),
        db.Index('idx_adiantamento_admin_id', 'admin_id'),
    )

class FeriasDecimo(db.Model):
    """Controle de férias e 13º salário"""
    __tablename__ = 'ferias_decimo'
    
    id = db.Column(db.Integer, primary_key=True)
    funcionario_id = db.Column(db.Integer, db.ForeignKey('funcionario.id'), nullable=False)
    tipo = db.Column(db.String(20), nullable=False)  # FERIAS, DECIMO_TERCEIRO
    ano_referencia = db.Column(db.Integer, nullable=False)
    
    # Período
    periodo_inicio = db.Column(db.Date, nullable=False)
    periodo_fim = db.Column(db.Date, nullable=False)
    
    # Cálculos
    dias_direito = db.Column(db.Integer, default=30)  # Dias de férias ou meses de 13º
    dias_gozados = db.Column(db.Integer, default=0)
    valor_calculado = db.Column(db.Numeric(10, 2), default=0)
    terco_constitucional = db.Column(db.Numeric(10, 2), default=0)  # 1/3 das férias
    
    # Controle
    status = db.Column(db.String(20), default='CALCULADO')  # CALCULADO, PAGO
    data_pagamento = db.Column(db.Date)
    observacoes = db.Column(db.Text)
    admin_id = db.Column(db.Integer, db.ForeignKey('usuario.id'), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relacionamentos
    funcionario = db.relationship('Funcionario', backref='ferias_decimos')
    admin = db.relationship('Usuario', foreign_keys=[admin_id])
    
    # Índices
    __table_args__ = (
        db.Index('idx_ferias_decimo_funcionario_tipo_ano', 'funcionario_id', 'tipo', 'ano_referencia'),
        db.Index('idx_ferias_decimo_admin_id', 'admin_id'),
    )

class ParametrosLegais(db.Model):
    """Parâmetros legais por ano (INSS, IRRF, etc.)"""
    __tablename__ = 'parametros_legais'
    
    id = db.Column(db.Integer, primary_key=True)
    admin_id = db.Column(db.Integer, db.ForeignKey('usuario.id'), nullable=False)
    ano_vigencia = db.Column(db.Integer, nullable=False)
    
    # INSS - Tabela progressiva
    inss_faixa1_limite = db.Column(db.Numeric(10, 2), default=1320.00)  # 2024
    inss_faixa1_percentual = db.Column(db.Numeric(5, 2), default=7.5)
    inss_faixa2_limite = db.Column(db.Numeric(10, 2), default=2571.29)
    inss_faixa2_percentual = db.Column(db.Numeric(5, 2), default=9.0)
    inss_faixa3_limite = db.Column(db.Numeric(10, 2), default=3856.94)
    inss_faixa3_percentual = db.Column(db.Numeric(5, 2), default=12.0)
    inss_faixa4_limite = db.Column(db.Numeric(10, 2), default=7507.49)
    inss_faixa4_percentual = db.Column(db.Numeric(5, 2), default=14.0)
    inss_teto = db.Column(db.Numeric(10, 2), default=877.24)  # Valor máximo
    
    # IRRF - Tabela progressiva
    irrf_isencao = db.Column(db.Numeric(10, 2), default=2112.00)
    irrf_faixa1_limite = db.Column(db.Numeric(10, 2), default=2826.65)
    irrf_faixa1_percentual = db.Column(db.Numeric(5, 2), default=7.5)
    irrf_faixa1_deducao = db.Column(db.Numeric(10, 2), default=158.40)
    irrf_faixa2_limite = db.Column(db.Numeric(10, 2), default=3751.05)
    irrf_faixa2_percentual = db.Column(db.Numeric(5, 2), default=15.0)
    irrf_faixa2_deducao = db.Column(db.Numeric(10, 2), default=370.40)
    irrf_faixa3_limite = db.Column(db.Numeric(10, 2), default=4664.68)
    irrf_faixa3_percentual = db.Column(db.Numeric(5, 2), default=22.5)
    irrf_faixa3_deducao = db.Column(db.Numeric(10, 2), default=651.73)
    irrf_faixa4_percentual = db.Column(db.Numeric(5, 2), default=27.5)
    irrf_faixa4_deducao = db.Column(db.Numeric(10, 2), default=884.96)
    irrf_dependente_valor = db.Column(db.Numeric(10, 2), default=189.59)
    
    # OUTROS PARÂMETROS
    fgts_percentual = db.Column(db.Numeric(5, 2), default=8.0)
    salario_minimo = db.Column(db.Numeric(10, 2), default=1412.00)  # 2024
    vale_transporte_percentual = db.Column(db.Numeric(5, 2), default=6.0)
    adicional_noturno_percentual = db.Column(db.Numeric(5, 2), default=20.0)
    hora_extra_50_percentual = db.Column(db.Numeric(5, 2), default=50.0)
    hora_extra_100_percentual = db.Column(db.Numeric(5, 2), default=100.0)
    
    # Controle
    ativo = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relacionamentos
    admin = db.relationship('Usuario', foreign_keys=[admin_id])
    
    # Índices
    __table_args__ = (
        db.Index('idx_parametros_admin_ano', 'admin_id', 'ano_vigencia'),
        db.UniqueConstraint('admin_id', 'ano_vigencia', name='uk_parametros_admin_ano'),
    )


# ================================
# NOTIFICAÇÕES CLIENTE - MÓDULO 2
# ================================

class NotificacaoCliente(db.Model):
    """Notificações automáticas para clientes via portal"""
    __tablename__ = 'notificacao_cliente'
    
    id = db.Column(db.Integer, primary_key=True)
    obra_id = db.Column(db.Integer, db.ForeignKey('obra.id'), nullable=False)
    
    # Tipo e conteúdo
    tipo = db.Column(db.String(30), nullable=False)  # 'novo_rdo', 'marco_atingido', 'atraso', 'conclusao_atividade'
    titulo = db.Column(db.String(100), nullable=False)
    mensagem = db.Column(db.Text, nullable=False)
    
    # Dados relacionados
    rdo_id = db.Column(db.Integer, db.ForeignKey('rdo.id'))
    atividade_id = db.Column(db.Integer, db.ForeignKey('rdo_atividade.id'))
    
    # Status
    visualizada = db.Column(db.Boolean, default=False)
    data_visualizacao = db.Column(db.DateTime)
    
    # Prioridade
    prioridade = db.Column(db.String(10), default='normal')  # 'baixa', 'normal', 'alta', 'urgente'
    
    # Controle
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    # Relacionamentos
    obra = db.relationship('Obra', backref='notificacoes_obra')
    rdo = db.relationship('RDO', backref='notificacoes')
    atividade = db.relationship('RDOAtividade', backref='notificacoes')
    
    def __repr__(self):
        return f'<NotificacaoCliente {self.titulo}>'

# ===============================================================
# == MÓDULO 7: SISTEMA CONTÁBIL COMPLETO
# ===============================================================

class PlanoContas(db.Model):
    """Plano de Contas brasileiro completo e hierárquico."""
    __tablename__ = 'plano_contas'
    codigo = db.Column(db.String(20), primary_key=True)  # Ex: 1.1.01.001
    nome = db.Column(db.String(200), nullable=False)
    tipo_conta = db.Column(db.String(20), nullable=False)  # ATIVO, PASSIVO, PATRIMONIO, RECEITA, DESPESA
    natureza = db.Column(db.String(10), nullable=False)  # DEVEDORA, CREDORA
    nivel = db.Column(db.Integer, nullable=False)
    conta_pai_codigo = db.Column(db.String(20), db.ForeignKey('plano_contas.codigo'))
    aceita_lancamento = db.Column(db.Boolean, default=True)  # True para contas analíticas
    ativo = db.Column(db.Boolean, default=True)
    admin_id = db.Column(db.Integer, db.ForeignKey('usuario.id'), nullable=False)

    conta_pai = db.relationship('PlanoContas', remote_side=[codigo])

class CentroCustoContabil(db.Model):
    """Centros de Custo para rateio contábil (Obras, Departamentos)."""
    __tablename__ = 'centro_custo_contabil'
    id = db.Column(db.Integer, primary_key=True)
    codigo = db.Column(db.String(20), nullable=False)
    nome = db.Column(db.String(100), nullable=False)
    tipo = db.Column(db.String(20), nullable=False)  # OBRA, DEPARTAMENTO, PROJETO
    obra_id = db.Column(db.Integer, db.ForeignKey('obra.id'))
    ativo = db.Column(db.Boolean, default=True)
    admin_id = db.Column(db.Integer, db.ForeignKey('usuario.id'), nullable=False)

    obra = db.relationship('Obra')
    __table_args__ = (db.UniqueConstraint('codigo', 'admin_id', name='uq_centro_custo_contabil_codigo_admin'),)

class LancamentoContabil(db.Model):
    """Cabeçalho dos Lançamentos Contábeis (partidas dobradas)."""
    __tablename__ = 'lancamento_contabil'
    id = db.Column(db.Integer, primary_key=True)
    numero = db.Column(db.Integer, nullable=False) # Sequencial por admin
    data_lancamento = db.Column(db.Date, nullable=False, index=True)
    historico = db.Column(db.String(500), nullable=False)
    valor_total = db.Column(db.Numeric(15, 2), nullable=False)
    origem = db.Column(db.String(50))  # MANUAL, MODULO_1, MODULO_4, MODULO_6
    origem_id = db.Column(db.Integer) # ID do registro de origem (Proposta, NotaFiscal, etc)
    usuario_id = db.Column(db.Integer, db.ForeignKey('usuario.id'))
    admin_id = db.Column(db.Integer, db.ForeignKey('usuario.id'), nullable=False, index=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    partidas = db.relationship('PartidaContabil', backref='lancamento', cascade="all, delete-orphan")
    usuario = db.relationship('Usuario', foreign_keys=[usuario_id])

class PartidaContabil(db.Model):
    """Itens do Lançamento Contábil (Débito e Crédito)."""
    __tablename__ = 'partida_contabil'
    id = db.Column(db.Integer, primary_key=True)
    lancamento_id = db.Column(db.Integer, db.ForeignKey('lancamento_contabil.id'), nullable=False)
    sequencia = db.Column(db.Integer, nullable=False)
    conta_codigo = db.Column(db.String(20), db.ForeignKey('plano_contas.codigo'), nullable=False, index=True)
    centro_custo_id = db.Column(db.Integer, db.ForeignKey('centro_custo_contabil.id'))
    tipo_partida = db.Column(db.String(10), nullable=False)  # DEBITO, CREDITO
    valor = db.Column(db.Numeric(15, 2), nullable=False)
    historico_complementar = db.Column(db.String(200))
    admin_id = db.Column(db.Integer, db.ForeignKey('usuario.id'), nullable=False)

    conta = db.relationship('PlanoContas')
    centro_custo = db.relationship('CentroCustoContabil')

class BalanceteMensal(db.Model):
    """Armazena os saldos mensais para geração rápida de relatórios."""
    __tablename__ = 'balancete_mensal'
    id = db.Column(db.Integer, primary_key=True)
    conta_codigo = db.Column(db.String(20), db.ForeignKey('plano_contas.codigo'), nullable=False)
    mes_referencia = db.Column(db.Date, nullable=False)  # Primeiro dia do mês
    saldo_anterior = db.Column(db.Numeric(15, 2), default=0)
    debitos_mes = db.Column(db.Numeric(15, 2), default=0)
    creditos_mes = db.Column(db.Numeric(15, 2), default=0)
    saldo_atual = db.Column(db.Numeric(15, 2), default=0)
    admin_id = db.Column(db.Integer, db.ForeignKey('usuario.id'), nullable=False)
    processado_em = db.Column(db.DateTime, default=datetime.utcnow)

    __table_args__ = (db.UniqueConstraint('conta_codigo', 'mes_referencia', 'admin_id', name='uq_balancete_conta_mes_admin'),)

class DREMensal(db.Model):
    """Demonstração do Resultado do Exercício (DRE) mensal."""
    __tablename__ = 'dre_mensal'
    id = db.Column(db.Integer, primary_key=True)
    mes_referencia = db.Column(db.Date, nullable=False)
    receita_bruta = db.Column(db.Numeric(15, 2), default=0)
    impostos_sobre_vendas = db.Column(db.Numeric(15, 2), default=0)
    receita_liquida = db.Column(db.Numeric(15, 2), default=0)
    custo_total = db.Column(db.Numeric(15, 2), default=0)
    lucro_bruto = db.Column(db.Numeric(15, 2), default=0)
    total_despesas = db.Column(db.Numeric(15, 2), default=0)
    lucro_operacional = db.Column(db.Numeric(15, 2), default=0)
    lucro_liquido = db.Column(db.Numeric(15, 2), default=0)
    admin_id = db.Column(db.Integer, db.ForeignKey('usuario.id'), nullable=False)
    processado_em = db.Column(db.DateTime, default=datetime.utcnow)

    __table_args__ = (db.UniqueConstraint('mes_referencia', 'admin_id', name='uq_dre_mes_admin'),)

class BalancoPatrimonial(db.Model):
    """Balanço Patrimonial em uma data específica."""
    __tablename__ = 'balanco_patrimonial'
    id = db.Column(db.Integer, primary_key=True)
    data_referencia = db.Column(db.Date, nullable=False)
    total_ativo = db.Column(db.Numeric(15, 2), default=0)
    total_passivo_patrimonio = db.Column(db.Numeric(15, 2), default=0)
    admin_id = db.Column(db.Integer, db.ForeignKey('usuario.id'), nullable=False)
    processado_em = db.Column(db.DateTime, default=datetime.utcnow)

    __table_args__ = (db.UniqueConstraint('data_referencia', 'admin_id', name='uq_balanco_data_admin'),)

class FluxoCaixaContabil(db.Model):
    """Registro de todas as entradas e saídas de caixa."""
    __tablename__ = 'fluxo_caixa_contabil'
    id = db.Column(db.Integer, primary_key=True)
    data_movimento = db.Column(db.Date, nullable=False)
    tipo_movimento = db.Column(db.String(20), nullable=False)  # ENTRADA, SAIDA
    categoria = db.Column(db.String(50), nullable=False)  # OPERACIONAL, INVESTIMENTO, FINANCIAMENTO
    descricao = db.Column(db.String(200), nullable=False)
    valor = db.Column(db.Numeric(15, 2), nullable=False)
    conta_codigo = db.Column(db.String(20), db.ForeignKey('plano_contas.codigo'))
    centro_custo_id = db.Column(db.Integer, db.ForeignKey('centro_custo_contabil.id'))
    origem = db.Column(db.String(50))
    origem_id = db.Column(db.Integer)
    admin_id = db.Column(db.Integer, db.ForeignKey('usuario.id'), nullable=False)

class ConciliacaoBancaria(db.Model):
    """Registros para conciliação bancária."""
    __tablename__ = 'conciliacao_bancaria'
    id = db.Column(db.Integer, primary_key=True)
    conta_banco = db.Column(db.String(50), nullable=False)
    data_movimento = db.Column(db.Date, nullable=False)
    historico = db.Column(db.String(200), nullable=False)
    valor = db.Column(db.Numeric(15, 2), nullable=False)
    tipo = db.Column(db.String(10), nullable=False)  # DEBITO, CREDITO
    conciliado = db.Column(db.Boolean, default=False)
    lancamento_id = db.Column(db.Integer, db.ForeignKey('lancamento_contabil.id'))
    admin_id = db.Column(db.Integer, db.ForeignKey('usuario.id'), nullable=False)

class ProvisaoMensal(db.Model):
    """Controle de provisões automáticas (Férias, 13º)."""
    __tablename__ = 'provisao_mensal'
    id = db.Column(db.Integer, primary_key=True)
    mes_referencia = db.Column(db.Date, nullable=False)
    tipo_provisao = db.Column(db.String(50), nullable=False)  # FERIAS, DECIMO_TERCEIRO, INSS_EMPRESA
    valor_provisionado = db.Column(db.Numeric(15, 2), nullable=False)
    admin_id = db.Column(db.Integer, db.ForeignKey('usuario.id'), nullable=False)

class SpedContabil(db.Model):
    """Registro dos arquivos SPED Contábil gerados."""
    __tablename__ = 'sped_contabil'
    id = db.Column(db.Integer, primary_key=True)
    periodo_inicial = db.Column(db.Date, nullable=False)
    periodo_final = db.Column(db.Date, nullable=False)
    arquivo_gerado = db.Column(db.String(200), nullable=False)
    hash_arquivo = db.Column(db.String(64), nullable=False)
    status = db.Column(db.String(20), default='GERADO') # GERADO, TRANSMITIDO, ACEITO
    data_geracao = db.Column(db.DateTime, default=datetime.utcnow)
    admin_id = db.Column(db.Integer, db.ForeignKey('usuario.id'), nullable=False)

class AuditoriaContabil(db.Model):
    """Logs da auditoria automática do sistema."""
    __tablename__ = 'auditoria_contabil'
    id = db.Column(db.Integer, primary_key=True)
    data_auditoria = db.Column(db.DateTime, default=datetime.utcnow)
    tipo_verificacao = db.Column(db.String(100), nullable=False)
    resultado = db.Column(db.String(20), nullable=False)  # CONFORME, NAO_CONFORME, ALERTA
    observacoes = db.Column(db.Text)
    valor_divergencia = db.Column(db.Numeric(15, 2))
    corrigido = db.Column(db.Boolean, default=False)
    admin_id = db.Column(db.Integer, db.ForeignKey('usuario.id'), nullable=False)

# MÓDULO 1 - SISTEMA DE PROPOSTAS
class Cliente(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    nome = db.Column(db.String(200), nullable=False)
    email = db.Column(db.String(120))
    telefone = db.Column(db.String(20))
    endereco = db.Column(db.Text)
    cnpj = db.Column(db.String(18))
    admin_id = db.Column(db.Integer, db.ForeignKey('usuario.id'), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    admin = db.relationship('Usuario', backref='clientes_administrados')

class Proposta(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    numero = db.Column(db.String(50), unique=True, nullable=False)
    cliente_id = db.Column(db.Integer, db.ForeignKey('cliente.id'), nullable=False)
    titulo = db.Column(db.String(200), nullable=False)
    descricao = db.Column(db.Text)
    valor_total = db.Column(db.Float, default=0.0)
    status = db.Column(db.String(20), default='rascunho')  # rascunho, enviada, aprovada, rejeitada
    data_vencimento = db.Column(db.Date)
    data_envio = db.Column(db.DateTime)
    data_aprovacao = db.Column(db.DateTime)
    link_visualizacao = db.Column(db.String(255))
    admin_id = db.Column(db.Integer, db.ForeignKey('usuario.id'), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    # Relacionamentos
    cliente = db.relationship('Cliente', backref='propostas')
    admin = db.relationship('Usuario', backref='propostas_administradas')

class PropostaHistorico(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    proposta_id = db.Column(db.Integer, db.ForeignKey('proposta.id'), nullable=False)
    acao = db.Column(db.String(50), nullable=False)
    descricao = db.Column(db.Text)
    usuario_id = db.Column(db.Integer, db.ForeignKey('usuario.id'), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    # Relacionamentos
    proposta = db.relationship('Proposta', backref='historico')
    usuario = db.relationship('Usuario', backref='acoes_propostas')

# Atualização de timestamp para verificar se o modelo é alterado
# Essa linha força o gunicorn a recarregar quando há mudanças
# Última modificação: 2025-08-11 21:05:00 - Módulo 1 Propostas adicionado

