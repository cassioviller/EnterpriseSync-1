from app import db
from flask_login import UserMixin
from datetime import datetime, date
from sqlalchemy import func

class Usuario(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(64), unique=True, nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password_hash = db.Column(db.String(256))
    nome = db.Column(db.String(100), nullable=False)
    ativo = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

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
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    def __repr__(self):
        return f'<HorarioTrabalho {self.nome}>'

class Funcionario(db.Model):
    id = db.Column(db.Integer, primary_key=True)
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
    departamento_id = db.Column(db.Integer, db.ForeignKey('departamento.id'))
    funcao_id = db.Column(db.Integer, db.ForeignKey('funcao.id'))
    horario_trabalho_id = db.Column(db.Integer, db.ForeignKey('horario_trabalho.id'))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    # Relacionamentos
    registros_ponto = db.relationship('RegistroPonto', backref='funcionario_ref', lazy=True)
    horario_trabalho = db.relationship('HorarioTrabalho', backref='funcionarios', lazy=True)

class Obra(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    nome = db.Column(db.String(100), nullable=False)
    endereco = db.Column(db.Text)
    data_inicio = db.Column(db.Date, nullable=False)
    data_previsao_fim = db.Column(db.Date)
    orcamento = db.Column(db.Float, default=0.0)
    status = db.Column(db.String(20), default='Em andamento')
    responsavel_id = db.Column(db.Integer, db.ForeignKey('funcionario.id'))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    registros_ponto = db.relationship('RegistroPonto', backref='obra_ref', lazy=True)
    custos = db.relationship('CustoObra', backref='obra_ref', lazy=True)

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
    created_at = db.Column(db.DateTime, default=datetime.utcnow)



class Servico(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    nome = db.Column(db.String(100), nullable=False)
    descricao = db.Column(db.Text)
    preco_unitario = db.Column(db.Float, default=0.0)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

class RegistroPonto(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    funcionario_id = db.Column(db.Integer, db.ForeignKey('funcionario.id'), nullable=False)
    obra_id = db.Column(db.Integer, db.ForeignKey('obra.id'))
    data = db.Column(db.Date, nullable=False)
    hora_entrada = db.Column(db.Time)
    hora_saida = db.Column(db.Time)
    hora_almoco_saida = db.Column(db.Time)
    hora_almoco_retorno = db.Column(db.Time)
    horas_trabalhadas = db.Column(db.Float, default=0.0)
    horas_extras = db.Column(db.Float, default=0.0)
    observacoes = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

class CustoObra(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    obra_id = db.Column(db.Integer, db.ForeignKey('obra.id'), nullable=False)
    tipo = db.Column(db.String(20), nullable=False)  # 'mao_obra', 'material', 'servico', 'veiculo', 'alimentacao'
    descricao = db.Column(db.String(200), nullable=False)
    valor = db.Column(db.Float, nullable=False)
    data = db.Column(db.Date, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

class RegistroAlimentacao(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    funcionario_id = db.Column(db.Integer, db.ForeignKey('funcionario.id'), nullable=False)
    obra_id = db.Column(db.Integer, db.ForeignKey('obra.id'))
    data = db.Column(db.Date, nullable=False)
    tipo = db.Column(db.String(20), nullable=False)  # 'cafe', 'almoco', 'jantar', 'lanche'
    valor = db.Column(db.Float, nullable=False)
    observacoes = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

class Ocorrencia(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    funcionario_id = db.Column(db.Integer, db.ForeignKey('funcionario.id'), nullable=False)
    tipo = db.Column(db.String(50), nullable=False)
    data_inicio = db.Column(db.Date, nullable=False)
    data_fim = db.Column(db.Date)
    descricao = db.Column(db.Text)
    status = db.Column(db.String(20), default='Pendente')
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    # Relacionamento
    funcionario = db.relationship('Funcionario', backref='ocorrencias')


class RDO(db.Model):
    __tablename__ = 'rdo'
    
    id = db.Column(db.Integer, primary_key=True)
    numero_rdo = db.Column(db.String(20), unique=True, nullable=False)  # Auto-gerado
    data_relatorio = db.Column(db.Date, nullable=False)
    obra_id = db.Column(db.Integer, db.ForeignKey('obra.id'), nullable=False)
    criado_por_id = db.Column(db.Integer, db.ForeignKey('funcionario.id'), nullable=False)
    
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
    obra = db.relationship('Obra', backref='rdos')
    criado_por = db.relationship('Funcionario', backref='rdos_criados')
    mao_obra = db.relationship('RDOMaoObra', backref='rdo_ref', cascade='all, delete-orphan')
    equipamentos = db.relationship('RDOEquipamento', backref='rdo_ref', cascade='all, delete-orphan')
    atividades = db.relationship('RDOAtividade', backref='rdo_ref', cascade='all, delete-orphan')
    ocorrencias_rdo = db.relationship('RDOOcorrencia', backref='rdo_ref', cascade='all, delete-orphan')
    fotos = db.relationship('RDOFoto', backref='rdo_ref', cascade='all, delete-orphan')
    
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
    funcionario = db.relationship('Funcionario', backref='rdos_mao_obra')


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
