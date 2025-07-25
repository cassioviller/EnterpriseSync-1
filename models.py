from app import db
from flask_login import UserMixin
from datetime import datetime, date
from sqlalchemy import func
from enum import Enum

class TipoUsuario(Enum):
    SUPER_ADMIN = "super_admin"
    ADMIN = "admin" 
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
    departamento_id = db.Column(db.Integer, db.ForeignKey('departamento.id'))
    funcao_id = db.Column(db.Integer, db.ForeignKey('funcao.id'))
    horario_trabalho_id = db.Column(db.Integer, db.ForeignKey('horario_trabalho.id'))
    admin_id = db.Column(db.Integer, db.ForeignKey('usuario.id'), nullable=True)  # Para isolamento multi-tenant
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    # Relacionamentos
    registros_ponto = db.relationship('RegistroPonto', backref='funcionario_ref', lazy=True, overlaps="funcionario_ref")
    horario_trabalho = db.relationship('HorarioTrabalho', backref='funcionarios', lazy=True, overlaps="funcionarios")

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
    ativo = db.Column(db.Boolean, default=True)  # Campo para controle de obras ativas
    admin_id = db.Column(db.Integer, db.ForeignKey('usuario.id'), nullable=True)  # Para isolamento multi-tenant
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    registros_ponto = db.relationship('RegistroPonto', backref='obra_ref', lazy=True, overlaps="obra_ref")
    custos = db.relationship('CustoObra', backref='obra_ref', lazy=True, overlaps="obra_ref")
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
    obra_id = db.Column(db.Integer, db.ForeignKey('obra.id'))
    data = db.Column(db.Date, nullable=False)
    hora_entrada = db.Column(db.Time)
    hora_saida = db.Column(db.Time)
    hora_almoco_saida = db.Column(db.Time)
    hora_almoco_retorno = db.Column(db.Time)
    
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
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    funcionario = db.relationship('Funcionario', backref='outros_custos')
    obra = db.relationship('Obra', backref='outros_custos')
    
    def __repr__(self):
        return f'<OutroCusto {self.funcionario.nome} - {self.tipo} R$ {self.valor}>'
