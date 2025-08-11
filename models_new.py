"""
SIGE v8.0 - Modelos de dados corrigidos
Versão sem imports circulares usando aplicação factory pattern
"""

from flask_sqlalchemy import SQLAlchemy
from flask_login import UserMixin
from datetime import datetime, date
from sqlalchemy import func
from enum import Enum

# Instância global do SQLAlchemy que será configurada pelo app
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
    admin_id = db.Column(db.Integer, db.ForeignKey('usuario.id'), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    # Relacionamentos
    admin = db.relationship('Usuario', backref='funcionarios_administrados')
    horario_trabalho = db.relationship('HorarioTrabalho', backref='funcionarios')

# Adicionar as outras classes conforme necessário...
# (Obra, RDO, RegistroPonto, etc.)

class Obra(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    nome = db.Column(db.String(200), nullable=False)
    cliente = db.Column(db.String(100), nullable=False)
    endereco = db.Column(db.Text)
    valor_total = db.Column(db.Float, default=0.0)
    data_inicio = db.Column(db.Date)
    data_fim_prevista = db.Column(db.Date)
    status = db.Column(db.String(20), default='ativa')
    admin_id = db.Column(db.Integer, db.ForeignKey('usuario.id'), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    # Relacionamentos
    admin = db.relationship('Usuario', backref='obras_administradas')

# Registros de ponto para todos os módulos
class RegistroPonto(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    funcionario_id = db.Column(db.Integer, db.ForeignKey('funcionario.id'), nullable=False)
    data = db.Column(db.Date, nullable=False)
    hora_entrada = db.Column(db.Time)
    hora_saida_almoco = db.Column(db.Time)
    hora_retorno_almoco = db.Column(db.Time)
    hora_saida = db.Column(db.Time)
    horas_trabalhadas = db.Column(db.Float, default=0.0)
    horas_extras = db.Column(db.Float, default=0.0)
    admin_id = db.Column(db.Integer, db.ForeignKey('usuario.id'), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    # Relacionamentos
    funcionario = db.relationship('Funcionario', backref='registros_ponto')
    admin = db.relationship('Usuario', backref='registros_ponto_administrados')