# MODELS CONSOLIDADOS - SIGE v8.0
# Arquivo único para eliminar dependências circulares

from flask_login import UserMixin
from datetime import datetime, date, time
from sqlalchemy import func, JSON, Column, Integer, String, Text, Float, Boolean, DateTime, Date, Time, Numeric, ForeignKey, Enum as SQLEnum
from enum import Enum
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy.orm import DeclarativeBase, relationship, backref
from functools import lru_cache
import logging
import uuid
import secrets

logger = logging.getLogger(__name__)

class Base(DeclarativeBase):
    pass

db = SQLAlchemy(model_class=Base)

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
    admin_id = db.Column(db.Integer, db.ForeignKey('usuario.id'), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    funcionarios = db.relationship('Funcionario', backref='departamento_ref', lazy=True)

class Funcao(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    nome = db.Column(db.String(100), nullable=False)
    descricao = db.Column(db.Text)
    salario_base = db.Column(db.Float, default=0.0)
    admin_id = db.Column(db.Integer, db.ForeignKey('usuario.id'), nullable=False)
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
    admin_id = db.Column(db.Integer, db.ForeignKey('usuario.id'), nullable=False)
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
    jornada_semanal = db.Column(db.Integer, default=44)
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
    cliente = db.Column(db.String(200), nullable=True)  # Campo cliente para filtros
    proposta_origem_id = db.Column(db.Integer, db.ForeignKey('propostas_comerciais.id'))
    
    # Configurações do Portal
    portal_ativo = db.Column(db.Boolean, default=True)
    ultima_visualizacao_cliente = db.Column(db.DateTime)
    
    ativo = db.Column(db.Boolean, default=True)  # Campo para controle de obras ativas
    admin_id = db.Column(db.Integer, db.ForeignKey('usuario.id'), nullable=True)  # Para isolamento multi-tenant
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    registros_ponto = db.relationship('RegistroPonto', backref='obra_ref', lazy=True, overlaps="obra_ref")
    custos = db.relationship('CustoObra', backref='obra_ref', lazy=True, overlaps="obra_ref")
    servicos_obra = db.relationship('ServicoObra', backref='obra', cascade='all, delete-orphan', lazy=True)
    servicos_reais = db.relationship('ServicoObraReal', backref='obra_real', cascade='all, delete-orphan', lazy=True)

class ServicoObra(db.Model):
    """Relacionamento ORIGINAL - Serviços das Propostas vinculados às Obras (MANTIDO PARA COMPATIBILIDADE)"""
    __tablename__ = 'servico_obra'
    
    id = db.Column(db.Integer, primary_key=True)
    admin_id = db.Column(db.Integer, db.ForeignKey('usuario.id'), nullable=False)
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

class ServicoObraReal(db.Model):
    """NOVA TABELA - Gestão completa dos serviços reais executados na obra com controle avançado"""
    __tablename__ = 'servico_obra_real'
    
    id = db.Column(db.Integer, primary_key=True)
    obra_id = db.Column(db.Integer, db.ForeignKey('obra.id'), nullable=False)
    servico_id = db.Column(db.Integer, db.ForeignKey('servico.id'), nullable=False)
    
    # Planejamento detalhado
    quantidade_planejada = db.Column(db.Numeric(12, 4), nullable=False, default=0.0)
    quantidade_executada = db.Column(db.Numeric(12, 4), default=0.0)
    percentual_concluido = db.Column(db.Numeric(5, 2), default=0.0)  # 0.00 a 100.00%
    
    # Controle de prazo
    data_inicio_planejada = db.Column(db.Date)
    data_fim_planejada = db.Column(db.Date)
    data_inicio_real = db.Column(db.Date)
    data_fim_real = db.Column(db.Date)
    
    # Controle de custos
    valor_unitario = db.Column(db.Numeric(10, 2), default=0.0)
    valor_total_planejado = db.Column(db.Numeric(12, 2), default=0.0)
    valor_total_executado = db.Column(db.Numeric(12, 2), default=0.0)
    
    # Status e controle
    status = db.Column(db.String(30), default='Não Iniciado')  # Não Iniciado, Em Andamento, Concluído, Pausado
    prioridade = db.Column(db.Integer, default=3)  # 1=Alta, 2=Média, 3=Baixa
    responsavel_id = db.Column(db.Integer, db.ForeignKey('funcionario.id'))  # Funcionário responsável
    
    # Observações e notas
    observacoes = db.Column(db.Text)
    notas_tecnicas = db.Column(db.Text)  # Para detalhes técnicos específicos
    
    # Controle de qualidade
    aprovado = db.Column(db.Boolean, default=False)
    data_aprovacao = db.Column(db.DateTime)
    aprovado_por_id = db.Column(db.Integer, db.ForeignKey('funcionario.id'))
    
    # Multi-tenant e controle
    admin_id = db.Column(db.Integer, db.ForeignKey('usuario.id'), nullable=False)
    ativo = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relacionamentos
    servico = db.relationship('Servico', foreign_keys=[servico_id], backref='servicos_obra_real', lazy=True)
    responsavel = db.relationship('Funcionario', foreign_keys=[responsavel_id], backref='servicos_responsavel_real', lazy=True)
    aprovado_por = db.relationship('Funcionario', foreign_keys=[aprovado_por_id], backref='servicos_aprovados_real', lazy=True)
    admin = db.relationship('Usuario', backref='servicos_obra_real_criados', lazy=True)
    
    # Unique constraint para evitar duplicatas
    __table_args__ = (db.UniqueConstraint('obra_id', 'servico_id', name='_servico_obra_real_uc'),)




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
    # Multi-tenant obrigatório
    admin_id = db.Column(db.Integer, db.ForeignKey('usuario.id'), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relacionamentos
    # Removido: subatividades obsoletas - agora usamos SubatividadeMestre
    historico_produtividade = db.relationship('HistoricoProdutividadeServico', backref='servico', lazy=True)
    servicos_obra = db.relationship('ServicoObra', backref='servico', lazy=True)
    servicos_reais = db.relationship('ServicoObraReal', backref='servico_real', lazy=True)
    admin = db.relationship('Usuario', backref='servicos_criados')

# Removido: SubAtividade - substituído por SubatividadeMestre

class HistoricoProdutividadeServico(db.Model):
    """Histórico de produtividade coletado via RDO"""
    __tablename__ = 'historico_produtividade_servico'
    
    id = db.Column(db.Integer, primary_key=True)
    admin_id = db.Column(db.Integer, db.ForeignKey('usuario.id'), nullable=False)
    servico_id = db.Column(db.Integer, db.ForeignKey('servico.id'), nullable=False)
    # Removido: referência à tabela obsoleta sub_atividade
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
    admin_id = db.Column(db.Integer, db.ForeignKey('usuario.id'), nullable=False)
    
    # Índices para performance
    __table_args__ = (
        db.Index('idx_registro_ponto_funcionario_data', 'funcionario_id', 'data'),
        db.Index('idx_registro_ponto_obra_data', 'obra_id', 'data'),
        db.Index('idx_registro_ponto_admin_data', 'admin_id', 'data'),
    )

class ConfiguracaoHorario(db.Model):
    """Configuração de horários padrão por obra"""
    __tablename__ = 'configuracao_horario'
    
    id = db.Column(db.Integer, primary_key=True)
    obra_id = db.Column(db.Integer, db.ForeignKey('obra.id'), nullable=False)
    funcionario_id = db.Column(db.Integer, db.ForeignKey('funcionario.id'))  # Opcional: configuração específica por funcionário
    
    # Horários padrão
    entrada_padrao = db.Column(db.Time, default=time(8, 0))      # 08:00
    saida_padrao = db.Column(db.Time, default=time(17, 0))       # 17:00
    almoco_inicio = db.Column(db.Time, default=time(12, 0))      # 12:00
    almoco_fim = db.Column(db.Time, default=time(13, 0))         # 13:00
    
    # Configurações
    tolerancia_atraso = db.Column(db.Integer, default=15)        # 15 minutos
    carga_horaria_diaria = db.Column(db.Integer, default=480)    # 8 horas em minutos
    
    # Controle multi-tenant
    admin_id = db.Column(db.Integer, db.ForeignKey('usuario.id'), nullable=False)
    ativo = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relacionamentos
    obra = db.relationship('Obra', backref='configuracoes_horario')
    funcionario = db.relationship('Funcionario', backref='configuracao_horario_individual')

class DispositivoObra(db.Model):
    """Registro de dispositivos autorizados por obra para ponto eletrônico compartilhado"""
    __tablename__ = 'dispositivo_obra'
    
    id = db.Column(db.Integer, primary_key=True)
    obra_id = db.Column(db.Integer, db.ForeignKey('obra.id'), nullable=False)
    nome_dispositivo = db.Column(db.String(100), nullable=False)  # "Tablet Obra A"
    identificador = db.Column(db.String(200))  # User-agent ou fingerprint
    ultimo_acesso = db.Column(db.DateTime)
    ativo = db.Column(db.Boolean, default=True)
    
    # Localização GPS do dispositivo
    latitude = db.Column(db.Float)
    longitude = db.Column(db.Float)
    
    # Controle multi-tenant
    admin_id = db.Column(db.Integer, db.ForeignKey('usuario.id'), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relacionamento
    obra = db.relationship('Obra', backref='dispositivos_autorizados')

class FuncionarioObrasPonto(db.Model):
    """Configuração de quais obras aparecem no dropdown para cada funcionário bater ponto"""
    __tablename__ = 'funcionario_obras_ponto'
    
    id = db.Column(db.Integer, primary_key=True)
    funcionario_id = db.Column(db.Integer, db.ForeignKey('funcionario.id'), nullable=False)
    obra_id = db.Column(db.Integer, db.ForeignKey('obra.id'), nullable=False)
    admin_id = db.Column(db.Integer, db.ForeignKey('usuario.id'), nullable=False)
    ativo = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    # Relacionamentos
    funcionario = db.relationship('Funcionario', backref='obras_ponto_disponiveis')
    obra = db.relationship('Obra', backref='funcionarios_autorizados')
    
    # Constraint única para evitar duplicatas
    __table_args__ = (
        db.UniqueConstraint('funcionario_id', 'obra_id', 'admin_id', name='uq_funcionario_obra_admin'),
    )

# Novos modelos conforme especificação v3.0
class TipoOcorrencia(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    admin_id = db.Column(db.Integer, db.ForeignKey('usuario.id'), nullable=False)
    nome = db.Column(db.String(50), unique=True, nullable=False)  # Atestado Médico, Atraso Justificado, etc.
    descricao = db.Column(db.Text)
    requer_documento = db.Column(db.Boolean, default=False)
    afeta_custo = db.Column(db.Boolean, default=False)  # se deve ser incluído no custo mensal
    ativo = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

class Ocorrencia(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    admin_id = db.Column(db.Integer, db.ForeignKey('usuario.id'), nullable=False)
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
    aprovador = db.relationship('Usuario', foreign_keys=[aprovado_por], backref='ocorrencias_aprovadas', lazy=True, overlaps="ocorrencias_aprovadas")

# ===== MÓDULO 3: GESTÃO DE EQUIPES - SISTEMAS KANBAN/CALENDÁRIO =====

class CalendarioUtil(db.Model):
    data = db.Column(db.Date, primary_key=True)
    admin_id = db.Column(db.Integer, db.ForeignKey('usuario.id'), nullable=False)
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
    
    # Campos adicionados pela Migração 43 para integração completa
    funcionario_id = db.Column(db.Integer, db.ForeignKey('funcionario.id'))
    item_almoxarifado_id = db.Column(db.Integer, db.ForeignKey('almoxarifado_item.id'))
    veiculo_id = db.Column(db.Integer, db.ForeignKey('frota_veiculo.id'))
    admin_id = db.Column(db.Integer, db.ForeignKey('usuario.id'))
    quantidade = db.Column(db.Numeric(10, 2), default=1)
    valor_unitario = db.Column(db.Numeric(10, 2), default=0)
    horas_trabalhadas = db.Column(db.Numeric(5, 2))
    horas_extras = db.Column(db.Numeric(5, 2))
    rdo_id = db.Column(db.Integer, db.ForeignKey('rdo.id'))
    categoria = db.Column(db.String(50))
    
    # Relacionamentos
    obra = db.relationship('Obra', overlaps="custos,obra_ref")
    centro_custo_ref = db.relationship('CentroCusto', backref='custos')
    funcionario = db.relationship('Funcionario', foreign_keys=[funcionario_id])
    veiculo = db.relationship('Vehicle', foreign_keys=[veiculo_id])
    admin = db.relationship('Usuario', foreign_keys=[admin_id])
    
    # ✅ OTIMIZAÇÃO: Índices compostos para queries frequentes
    __table_args__ = (
        db.Index('idx_custo_admin_data', 'admin_id', 'data'),  # Filtros por período
        db.Index('idx_custo_obra_tipo', 'obra_id', 'tipo'),     # Filtros por obra e tipo
    )

# Novos modelos para Gestão Financeira Avançada

class CentroCusto(db.Model):
    """Centros de custo para classificação financeira"""
    __tablename__ = 'centro_custo'
    
    id = db.Column(db.Integer, primary_key=True)
    admin_id = db.Column(db.Integer, db.ForeignKey('usuario.id'), nullable=False)
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
    admin_id = db.Column(db.Integer, db.ForeignKey('usuario.id'), nullable=False)
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
    admin_id = db.Column(db.Integer, db.ForeignKey('usuario.id'), nullable=False)
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
    admin_id = db.Column(db.Integer, db.ForeignKey('usuario.id'), nullable=False)
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
    admin_id = db.Column(db.Integer, db.ForeignKey('usuario.id'), nullable=False)
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
    admin_id = db.Column(db.Integer, db.ForeignKey('usuario.id'), nullable=True)  # Para isolamento multi-tenant
    
    # Condições climáticas padronizadas
    clima_geral = db.Column(db.String(50))  # Ensolarado, Nublado, Chuvoso, etc.
    temperatura_media = db.Column(db.String(10))  # "25°C"
    umidade_relativa = db.Column(db.Integer)  # 0-100%
    vento_velocidade = db.Column(db.String(20))  # "Fraco", "Moderado", "Forte"
    precipitacao = db.Column(db.String(20))  # "Sem chuva", "Garoa", "Chuva forte"
    condicoes_trabalho = db.Column(db.String(50))  # "Ideais", "Adequadas", "Limitadas", "Inadequadas"
    observacoes_climaticas = db.Column(db.Text)
    
    # Local de trabalho
    local = db.Column(db.String(20), default='Campo')  # "Campo" ou "Oficina"
    
    # Comentários gerais
    comentario_geral = db.Column(db.Text)
    
    # Status e controle
    status = db.Column(db.String(20), default='Rascunho')  # Rascunho, Finalizado
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relacionamentos
    obra = db.relationship('Obra', backref='rdos', overlaps="rdos")
    criado_por = db.relationship('Usuario', foreign_keys=[criado_por_id], backref='rdos_criados', overlaps="rdos_criados")
    admin = db.relationship('Usuario', foreign_keys=[admin_id], backref='rdos_admin', overlaps="rdos_admin")
    mao_obra = db.relationship('RDOMaoObra', backref='rdo_ref', cascade='all, delete-orphan', overlaps="rdo_ref")
    equipamentos = db.relationship('RDOEquipamento', backref='rdo_ref', cascade='all, delete-orphan', overlaps="rdo_ref")
    # Removido: atividades obsoletas - agora usamos servico_subatividades
    ocorrencias_rdo = db.relationship('RDOOcorrencia', backref='rdo_ref', cascade='all, delete-orphan', overlaps="rdo_ref")
    # fotos - definido em RDOFoto com backref (linha ~743)
    
    def __repr__(self):
        return f'<RDO {self.numero_rdo}>'
    
    @property
    def progresso_geral(self):
        """Calcula progresso geral baseado nas atividades"""
        if not self.atividades:
            return 0
        return round(sum(a.percentual_conclusao for a in self.atividades) / len(self.atividades), 2)
    
    @property
    def total_horas_trabalhadas(self):
        """Calcula total de horas trabalhadas no RDO"""
        return sum(m.horas_trabalhadas for m in self.mao_obra)
    
    @property
    def total_funcionarios(self):
        """Conta funcionários únicos no RDO"""
        return len(set(m.funcionario_id for m in self.mao_obra))
    
    def validar_rdo_unico_por_dia(self):
        """Valida se já existe outro RDO para a mesma obra/data"""
        rdo_existente = RDO.query.filter(
            RDO.obra_id == self.obra_id,
            RDO.data_relatorio == self.data_relatorio,
            RDO.id != self.id if self.id else True
        ).first()
        return rdo_existente is None, rdo_existente
    
    def gerar_numero_rdo(self):
        """Gera número único para RDO"""
        if not self.numero_rdo:
            ano = self.data_relatorio.year
            count = db.session.query(func.count(RDO.id)).filter(
                func.extract('year', RDO.data_relatorio) == ano,
                RDO.obra_id == self.obra_id
            ).scalar() or 0
            self.numero_rdo = f"RDO-{ano}-{count + 1:03d}"
    
    def __repr__(self):
        return f'<RDO {self.numero_rdo}>'


class RDOMaoObra(db.Model):
    __tablename__ = 'rdo_mao_obra'
    
    id = db.Column(db.Integer, primary_key=True)
    admin_id = db.Column(db.Integer, db.ForeignKey('usuario.id'), nullable=False)
    rdo_id = db.Column(db.Integer, db.ForeignKey('rdo.id'), nullable=False)
    funcionario_id = db.Column(db.Integer, db.ForeignKey('funcionario.id'), nullable=False)
    funcao_exercida = db.Column(db.String(100), nullable=False)  # Nome correto do database
    horas_trabalhadas = db.Column(db.Float, nullable=False)
    
    # Relacionamentos
    funcionario = db.relationship('Funcionario', backref='rdos_mao_obra', overlaps="rdos_mao_obra")
    
    # Compatibilidade com código legado
    @property
    def funcao(self):
        return self.funcao_exercida
    
    @funcao.setter
    def funcao(self, value):
        self.funcao_exercida = value


class RDOEquipamento(db.Model):
    __tablename__ = 'rdo_equipamento'
    
    id = db.Column(db.Integer, primary_key=True)
    admin_id = db.Column(db.Integer, db.ForeignKey('usuario.id'), nullable=False)
    rdo_id = db.Column(db.Integer, db.ForeignKey('rdo.id'), nullable=False)
    nome_equipamento = db.Column(db.String(100), nullable=False)
    quantidade = db.Column(db.Integer, nullable=False)
    horas_uso = db.Column(db.Float, nullable=False)
    estado_conservacao = db.Column(db.String(50), nullable=False)


# Removido: RDOAtividade - substituído por RDOServicoSubatividade


class RDOOcorrencia(db.Model):
    __tablename__ = 'rdo_ocorrencia'
    
    id = db.Column(db.Integer, primary_key=True)
    admin_id = db.Column(db.Integer, db.ForeignKey('usuario.id'), nullable=False)
    rdo_id = db.Column(db.Integer, db.ForeignKey('rdo.id'), nullable=False)
    tipo_ocorrencia = db.Column(db.String(50), nullable=False)  # "Problema", "Observação", "Melhoria", "Segurança"
    severidade = db.Column(db.String(20), default='Baixa')  # "Baixa", "Média", "Alta", "Crítica"
    descricao_ocorrencia = db.Column(db.Text, nullable=False)
    problemas_identificados = db.Column(db.Text)
    acoes_corretivas = db.Column(db.Text)
    responsavel_acao = db.Column(db.String(100))  # Quem deve resolver
    prazo_resolucao = db.Column(db.Date)  # Prazo para resolver
    status_resolucao = db.Column(db.String(20), default='Pendente')  # "Pendente", "Em Andamento", "Resolvido"
    observacoes_resolucao = db.Column(db.Text)
    criado_em = db.Column(db.DateTime, default=datetime.utcnow)


class RDOFoto(db.Model):
    __tablename__ = 'rdo_foto'
    
    id = db.Column(db.Integer, primary_key=True)
    admin_id = db.Column(db.Integer, db.ForeignKey('usuario.id'), nullable=False, index=True)
    rdo_id = db.Column(db.Integer, db.ForeignKey('rdo.id'), nullable=False, index=True)
    
    # ✅ CORREÇÃO CRÍTICA: Campos legados são NOT NULL no banco de dados
    nome_arquivo = db.Column(db.String(255), nullable=False)
    caminho_arquivo = db.Column(db.String(500), nullable=False)
    legenda = db.Column(db.Text)
    
    # Novos campos (v9.0)
    descricao = db.Column(db.Text)
    arquivo_original = db.Column(db.String(500))
    arquivo_otimizado = db.Column(db.String(500))
    thumbnail = db.Column(db.String(500))
    nome_original = db.Column(db.String(255))
    tamanho_bytes = db.Column(db.BigInteger)
    ordem = db.Column(db.Integer, default=0)
    
    # 🔥 ARMAZENAMENTO PERSISTENTE (v9.0.4) - Fotos em Base64 no banco de dados
    # Solução: Igual aos funcionários - fotos NUNCA são perdidas em deploy/restart
    imagem_original_base64 = db.Column(db.Text)  # Backup completo da imagem original
    imagem_otimizada_base64 = db.Column(db.Text)  # Versão otimizada (1200px) para visualização
    thumbnail_base64 = db.Column(db.Text)  # Miniatura (300px) para listagem rápida
    
    uploaded_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    # Relacionamento com RDO
    rdo = db.relationship('RDO', backref=db.backref('fotos', lazy='selectin', order_by='RDOFoto.ordem'))


# ===== MÓDULO ALIMENTAÇÃO - Gestão de Refeições =====

class Restaurante(db.Model):
    """Modelo para restaurantes/fornecedores de alimentação"""
    __tablename__ = 'restaurante'
    
    id = db.Column(db.Integer, primary_key=True)
    nome = db.Column(db.String(100), nullable=False)
    endereco = db.Column(db.Text)
    telefone = db.Column(db.String(20))
    razao_social = db.Column(db.String(200))
    cnpj = db.Column(db.String(18))
    pix = db.Column(db.String(100))
    nome_conta = db.Column(db.String(100))
    admin_id = db.Column(db.Integer, db.ForeignKey('usuario.id'), nullable=False)
    
    # Relacionamentos
    lancamentos = db.relationship('AlimentacaoLancamento', back_populates='restaurante', lazy='dynamic')
    registros_alimentacao = db.relationship('RegistroAlimentacao', lazy=True, overlaps="restaurante_ref")
    
    def __repr__(self):
        return f'<Restaurante {self.nome}>'


# Tabela de associação para relacionamento Many-to-Many entre AlimentacaoLancamento e Funcionario
alimentacao_funcionarios_assoc = db.Table('alimentacao_funcionarios_assoc',
    db.Column('lancamento_id', db.Integer, db.ForeignKey('alimentacao_lancamento.id'), primary_key=True),
    db.Column('funcionario_id', db.Integer, db.ForeignKey('funcionario.id'), primary_key=True)
)


class AlimentacaoLancamento(db.Model):
    """Lançamentos de alimentação para controle de custos com refeições"""
    __tablename__ = 'alimentacao_lancamento'
    
    id = db.Column(db.Integer, primary_key=True)
    data = db.Column(db.Date, nullable=False, index=True)
    valor_total = db.Column(db.Numeric(10, 2), nullable=False)
    descricao = db.Column(db.Text)
    
    # Chaves Estrangeiras - padrão multi-tenant com admin_id NOT NULL
    restaurante_id = db.Column(db.Integer, db.ForeignKey('restaurante.id'), nullable=False)
    obra_id = db.Column(db.Integer, db.ForeignKey('obra.id'), nullable=False)
    admin_id = db.Column(db.Integer, db.ForeignKey('usuario.id'), nullable=False)
    
    # Relacionamentos
    restaurante = db.relationship('Restaurante', back_populates='lancamentos')
    obra = db.relationship('Obra', backref='lancamentos_alimentacao')
    
    # Many-to-Many com Funcionários
    funcionarios = db.relationship('Funcionario',
                                 secondary=alimentacao_funcionarios_assoc,
                                 backref=db.backref('lancamentos_alimentacao', lazy='dynamic'),
                                 lazy='selectin')
    
    @property
    def valor_por_funcionario(self):
        """Calcula o valor rateado por funcionário"""
        num_funcionarios = len(self.funcionarios)
        if not num_funcionarios or self.valor_total is None:
            return 0
        return self.valor_total / num_funcionarios


class DocumentoFiscal(db.Model):
    """Controle de documentos fiscais relacionados a veículos"""
    __tablename__ = 'documento_fiscal'
    
    id = db.Column(db.Integer, primary_key=True)
    custo_veiculo_id = db.Column(db.Integer, db.ForeignKey('custo_veiculo.id'), nullable=True)
    manutencao_id = db.Column(db.Integer, db.ForeignKey('manutencao_veiculo.id'), nullable=True)
    veiculo_id = db.Column(db.Integer, db.ForeignKey('veiculo.id'), nullable=False)
    
    # Dados do documento
    tipo_documento = db.Column(db.String(20), nullable=False)  # nf, nfce, recibo, cupom, outros
    numero_documento = db.Column(db.String(50), nullable=False)
    serie = db.Column(db.String(10))
    data_emissao = db.Column(db.Date, nullable=False)
    valor_documento = db.Column(db.Float, nullable=False)
    
    # Dados do emissor
    cnpj_emissor = db.Column(db.String(18))
    nome_emissor = db.Column(db.String(200), nullable=False)
    endereco_emissor = db.Column(db.Text)
    
    # Dados fiscais
    valor_icms = db.Column(db.Float, default=0.0)
    valor_pis = db.Column(db.Float, default=0.0)
    valor_cofins = db.Column(db.Float, default=0.0)
    valor_iss = db.Column(db.Float, default=0.0)
    valor_desconto = db.Column(db.Float, default=0.0)
    
    # Arquivo digitalizado
    arquivo_digitalizado = db.Column(db.String(500))  # Caminho para o arquivo
    arquivo_nome_original = db.Column(db.String(200))  # Nome original do arquivo
    arquivo_tamanho = db.Column(db.Integer)  # Tamanho em bytes
    
    # Controle e validação
    validado = db.Column(db.Boolean, default=False)
    validado_por_id = db.Column(db.Integer, db.ForeignKey('usuario.id'))
    data_validacao = db.Column(db.DateTime)
    observacoes_validacao = db.Column(db.Text)
    
    # Status contábil
    lancado_contabilidade = db.Column(db.Boolean, default=False)
    data_lancamento = db.Column(db.DateTime)
    numero_lancamento = db.Column(db.String(50))
    
    # Multi-tenant
    admin_id = db.Column(db.Integer, db.ForeignKey('usuario.id'), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relacionamentos
    custo_veiculo = db.relationship('CustoVeiculo', backref='documentos_fiscais', overlaps="documentos_fiscais")
    veiculo = db.relationship('Veiculo', backref='documentos_fiscais', overlaps="documentos_fiscais")
    validado_por = db.relationship('Usuario', foreign_keys=[validado_por_id], backref='documentos_validados')
    admin = db.relationship('Usuario', foreign_keys=[admin_id], backref='documentos_criados')
    
    @property
    def valor_impostos_total(self):
        """Calcula total de impostos"""
        return (self.valor_icms or 0) + (self.valor_pis or 0) + (self.valor_cofins or 0) + (self.valor_iss or 0)
    
    @property
    def valor_liquido(self):
        """Calcula valor líquido (valor total - descontos)"""
        return self.valor_documento - (self.valor_desconto or 0)
    
    @property
    def percentual_impostos(self):
        """Calcula percentual de impostos sobre o valor total"""
        if self.valor_documento > 0:
            return round((self.valor_impostos_total / self.valor_documento) * 100, 2)
        return 0
    
    def __repr__(self):
        return f'<DocumentoFiscal {self.tipo_documento} - {self.numero_documento} - R${self.valor_documento}>'


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
# MÓDULO DE PROPOSTAS COMERCIAIS (MOVIDO PARA models_propostas.py)
# ================================
# As definições das classes Proposta e ServicoPropostaComercialSIGE
# foram movidas para models_propostas.py para evitar conflitos de importação

# ================================
# ENHANCED RDO SYSTEM - SUBATIVIDADES
# ================================

class RDOServicoSubatividade(db.Model):
    """
    Modelo compatível com a estrutura real do database
    """
    __tablename__ = 'rdo_servico_subatividade'
    
    id = db.Column(db.Integer, primary_key=True)
    rdo_id = db.Column(db.Integer, db.ForeignKey('rdo.id'), nullable=False)
    servico_id = db.Column(db.Integer, db.ForeignKey('servico.id'), nullable=False)
    
    # Campos conforme estrutura real do database
    nome_subatividade = db.Column(db.String(255), nullable=False)
    descricao_subatividade = db.Column(db.Text)
    percentual_conclusao = db.Column(db.Float, default=0.0)
    percentual_anterior = db.Column(db.Float, default=0.0)
    incremento_dia = db.Column(db.Float, default=0.0)
    observacoes_tecnicas = db.Column(db.Text)
    ordem_execucao = db.Column(db.Integer)
    ativo = db.Column(db.Boolean, default=True)
    admin_id = db.Column(db.Integer, nullable=False)
    
    # Controle de tempo
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relacionamentos
    rdo = db.relationship('RDO', backref='servico_subatividades')
    servico = db.relationship('Servico', backref='rdo_subatividades')
    
    # Propriedades de compatibilidade
    @property
    def percentual(self):
        return self.percentual_conclusao
    
    @percentual.setter
    def percentual(self, value):
        self.percentual_conclusao = value
    
    @property
    def observacoes(self):
        return self.observacoes_tecnicas
    
    @observacoes.setter
    def observacoes(self, value):
        self.observacoes_tecnicas = value
    
    def __repr__(self):
        return f'<RDOServicoSubatividade RDO:{self.rdo_id} Servico:{self.servico_id} - {self.percentual_conclusao}%>'


class SubatividadeMestre(db.Model):
    """
    Modelo mestre de subatividades para cada serviço
    Define as subatividades padrão que podem ser aplicadas aos serviços
    """
    __tablename__ = 'subatividade_mestre'
    
    id = db.Column(db.Integer, primary_key=True)
    servico_id = db.Column(db.Integer, db.ForeignKey('servico.id'), nullable=False)
    
    # Dados da subatividade
    nome = db.Column(db.String(200), nullable=False)
    descricao = db.Column(db.Text)
    ordem_padrao = db.Column(db.Integer, default=0)
    
    # Configurações
    obrigatoria = db.Column(db.Boolean, default=True)  # Sempre aparece nos RDOs
    duracao_estimada_horas = db.Column(db.Float)  # Para planejamento
    complexidade = db.Column(db.Integer, default=1)  # 1-5
    
    # Multi-tenant
    admin_id = db.Column(db.Integer, db.ForeignKey('usuario.id'), nullable=False)
    
    # Controle
    ativo = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relacionamentos
    servico = db.relationship('Servico', backref='subatividades_mestre')
    admin = db.relationship('Usuario', backref='subatividades_mestre_administradas')
    
    # Índices
    __table_args__ = (
        db.Index('idx_subativ_mestre_servico', 'servico_id'),
        db.Index('idx_subativ_mestre_admin', 'admin_id'),
    )
    
    def __repr__(self):
        return f'<SubatividadeMestre {self.nome}>'
    
    def to_dict(self):
        return {
            'id': self.id,
            'nome': self.nome,
            'descricao': self.descricao,
            'ordem_padrao': self.ordem_padrao,
            'obrigatoria': self.obrigatoria,
            'duracao_estimada_horas': self.duracao_estimada_horas,
            'complexidade': self.complexidade,
            'servico_id': self.servico_id,
            'servico_nome': self.servico.nome if self.servico else None
        }


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

class ContaPagar(db.Model):
    """Contas a Pagar - Gestão de pagamentos a fornecedores"""
    __tablename__ = 'conta_pagar'
    
    id = db.Column(db.Integer, primary_key=True)
    fornecedor_id = db.Column(db.Integer, db.ForeignKey('fornecedor.id'), nullable=False)
    obra_id = db.Column(db.Integer, db.ForeignKey('obra.id'))
    numero_documento = db.Column(db.String(50))
    descricao = db.Column(db.Text, nullable=False)
    valor_original = db.Column(db.Numeric(15, 2), nullable=False)
    valor_pago = db.Column(db.Numeric(15, 2), default=0)
    saldo = db.Column(db.Numeric(15, 2))
    data_emissao = db.Column(db.Date, nullable=False)
    data_vencimento = db.Column(db.Date, nullable=False)
    data_pagamento = db.Column(db.Date)
    status = db.Column(db.String(20), default='PENDENTE')
    conta_contabil_codigo = db.Column(db.String(20), db.ForeignKey('plano_contas.codigo'))
    forma_pagamento = db.Column(db.String(50))
    observacoes = db.Column(db.Text)
    origem_tipo = db.Column(db.String(50))
    origem_id = db.Column(db.Integer)
    admin_id = db.Column(db.Integer, db.ForeignKey('usuario.id'), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    fornecedor = db.relationship('Fornecedor', backref='contas_pagar')
    obra = db.relationship('Obra', backref='contas_pagar')
    conta_contabil = db.relationship('PlanoContas', backref='contas_pagar_rel')
    admin = db.relationship('Usuario', backref='contas_pagar_admin')
    
    __table_args__ = (
        db.Index('idx_conta_pagar_vencimento', 'data_vencimento'),
        db.Index('idx_conta_pagar_status', 'status'),
        db.Index('idx_conta_pagar_fornecedor', 'fornecedor_id'),
        db.Index('idx_conta_pagar_obra', 'obra_id'),
        db.Index('idx_conta_pagar_admin', 'admin_id'),
    )

class ContaReceber(db.Model):
    """Contas a Receber - Gestão de recebimentos de clientes"""
    __tablename__ = 'conta_receber'
    
    id = db.Column(db.Integer, primary_key=True)
    cliente_nome = db.Column(db.String(200), nullable=False)
    cliente_cpf_cnpj = db.Column(db.String(18))
    obra_id = db.Column(db.Integer, db.ForeignKey('obra.id'))
    numero_documento = db.Column(db.String(50))
    descricao = db.Column(db.Text, nullable=False)
    valor_original = db.Column(db.Numeric(15, 2), nullable=False)
    valor_recebido = db.Column(db.Numeric(15, 2), default=0)
    saldo = db.Column(db.Numeric(15, 2))
    data_emissao = db.Column(db.Date, nullable=False)
    data_vencimento = db.Column(db.Date, nullable=False)
    data_recebimento = db.Column(db.Date)
    status = db.Column(db.String(20), default='PENDENTE')
    conta_contabil_codigo = db.Column(db.String(20), db.ForeignKey('plano_contas.codigo'))
    forma_recebimento = db.Column(db.String(50))
    observacoes = db.Column(db.Text)
    origem_tipo = db.Column(db.String(50))
    origem_id = db.Column(db.Integer)
    admin_id = db.Column(db.Integer, db.ForeignKey('usuario.id'), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    obra = db.relationship('Obra', backref='contas_receber')
    conta_contabil = db.relationship('PlanoContas', backref='contas_receber_rel')
    admin = db.relationship('Usuario', backref='contas_receber_admin')
    
    __table_args__ = (
        db.Index('idx_conta_receber_vencimento', 'data_vencimento'),
        db.Index('idx_conta_receber_status', 'status'),
        db.Index('idx_conta_receber_cliente', 'cliente_cpf_cnpj'),
        db.Index('idx_conta_receber_obra', 'obra_id'),
        db.Index('idx_conta_receber_admin', 'admin_id'),
    )

class BancoEmpresa(db.Model):
    """Contas Bancárias da Empresa"""
    __tablename__ = 'banco_empresa'
    
    id = db.Column(db.Integer, primary_key=True)
    nome_banco = db.Column(db.String(100), nullable=False)
    agencia = db.Column(db.String(10), nullable=False)
    conta = db.Column(db.String(20), nullable=False)
    tipo_conta = db.Column(db.String(20))
    saldo_inicial = db.Column(db.Numeric(15, 2), default=0)
    saldo_atual = db.Column(db.Numeric(15, 2), default=0)
    ativo = db.Column(db.Boolean, default=True)
    admin_id = db.Column(db.Integer, db.ForeignKey('usuario.id'), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    admin = db.relationship('Usuario', backref='bancos_empresa')
    
    __table_args__ = (
        db.Index('idx_banco_admin', 'admin_id'),
    )

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
        db.Index('idx_folha_admin_mes_status', 'admin_id', 'mes_referencia', 'status'),  # ✅ OTIMIZAÇÃO: Índice composto para filtros combinados
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
    
    @staticmethod
    @lru_cache(maxsize=128)
    def get_parametros_cached(admin_id: int, ano: int):
        """
        Busca parâmetros legais com cache em memória
        
        Cache de 128 entradas (admin_id + ano)
        Parâmetros legais mudam raramente (uma vez por ano no máximo)
        
        Args:
            admin_id: ID do administrador/tenant
            ano: Ano de vigência dos parâmetros
            
        Returns:
            ParametrosLegais ou None
        """
        return ParametrosLegais.query.filter_by(
            admin_id=admin_id,
            ano_vigencia=ano
        ).first()
    
    @staticmethod
    def invalidar_cache():
        """Limpa cache de parâmetros legais (usar ao criar/editar)"""
        ParametrosLegais.get_parametros_cached.cache_clear()
        logger.info("🔄 Cache de ParametrosLegais invalidado")


# ================================
# NOTIFICAÇÕES CLIENTE - MÓDULO 2
# ================================

class NotificacaoCliente(db.Model):
    """Notificações automáticas para clientes via portal"""
    __tablename__ = 'notificacao_cliente'
    
    id = db.Column(db.Integer, primary_key=True)
    admin_id = db.Column(db.Integer, db.ForeignKey('usuario.id'), nullable=False)
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
    # Removido: relacionamento com RDOAtividade obsoleto
    
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
    
    @staticmethod
    @lru_cache(maxsize=256)
    def get_conta_cached(admin_id: int, codigo: str):
        """
        Busca conta contábil com cache em memória
        
        Cache de 256 entradas (admin_id + codigo)
        Plano de contas muda raramente (setup inicial + ajustes ocasionais)
        
        Args:
            admin_id: ID do administrador/tenant
            codigo: Código da conta (ex: '1.1.01.001')
            
        Returns:
            PlanoContas ou None
        """
        return PlanoContas.query.filter_by(
            admin_id=admin_id,
            codigo=codigo,
            ativo=True
        ).first()
    
    @staticmethod
    def invalidar_cache():
        """Limpa cache do plano de contas (usar ao criar/editar)"""
        PlanoContas.get_conta_cached.cache_clear()
        logger.info("🔄 Cache de PlanoContas invalidado")

class CentroCustoContabil(db.Model):
    """Centros de Custo para rateio contábil (Obras, Departamentos)."""
    __tablename__ = 'centro_custo_contabil'
    id = db.Column(db.Integer, primary_key=True)
    codigo = db.Column(db.String(20), nullable=False)
    nome = db.Column(db.String(100), nullable=False)
    tipo = db.Column(db.String(20), nullable=False)  # OBRA, DEPARTAMENTO, PROJETO
    descricao = db.Column(db.Text)
    obra_id = db.Column(db.Integer, db.ForeignKey('obra.id'))
    ativo = db.Column(db.Boolean, default=True)
    admin_id = db.Column(db.Integer, db.ForeignKey('usuario.id'), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    obra = db.relationship('Obra')
    partidas = db.relationship('PartidaContabil', foreign_keys='PartidaContabil.centro_custo_id', back_populates='centro_custo')
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
    
    # ✅ OTIMIZAÇÃO: Índices compostos para queries frequentes
    __table_args__ = (
        db.Index('idx_lancamento_admin_data_origem', 'admin_id', 'data_lancamento', 'origem'),  # Relatórios contábeis
    )

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
    centro_custo = db.relationship('CentroCustoContabil', back_populates='partidas')

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


# Atualização de timestamp para verificar se o modelo é alterado
# Essa linha força o gunicorn a recarregar quando há mudanças
# Última modificação: 2025-08-11 21:05:00 - Módulo 1 Propostas adicionado



# MODELS DE SERVIÇOS
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

# MODELS DE PROPOSTAS
class Proposta(db.Model):
    __tablename__ = 'propostas_comerciais'
    
    id = db.Column(db.Integer, primary_key=True)
    numero = db.Column('numero_proposta', db.String(50), unique=True, nullable=False)  # Mapeado para coluna numero_proposta no banco
    data_proposta = db.Column(db.Date, nullable=False, default=date.today)
    
    # Dados do Cliente
    cliente_id = db.Column(db.Integer, db.ForeignKey('cliente.id'), nullable=True)  # FK adicionada pela Migração 43
    cliente_nome = db.Column(db.String(255), nullable=False)
    cliente_telefone = db.Column(db.String(20))
    cliente_email = db.Column(db.String(255))
    cliente_endereco = db.Column(db.Text)
    
    # Dados da Proposta
    titulo = db.Column('assunto', db.String(255), nullable=True)  # Mapeado para coluna assunto no banco
    descricao = db.Column('objeto', db.Text, nullable=True)  # Mapeado para coluna objeto no banco
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
    admin_id = db.Column(db.Integer, db.ForeignKey('usuario.id'), nullable=True)
    criado_em = db.Column(db.DateTime, default=datetime.utcnow)
    atualizado_em = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Integração com Obras
    obra_id = db.Column(db.Integer, db.ForeignKey('obra.id'))
    convertida_em_obra = db.Column(db.Boolean, default=False)
    
    # Relacionamentos
    cliente = db.relationship('Cliente', backref='propostas')
    itens = db.relationship('PropostaItem', backref='proposta', lazy=True, cascade='all, delete-orphan')
    arquivos = db.relationship('PropostaArquivo', backref='proposta', lazy=True, cascade='all, delete-orphan')
    
    def __init__(self, **kwargs):
        super(Proposta, self).__init__(**kwargs)
        if not self.numero:
            self.numero = self.gerar_numero_proposta()
        if not self.token_cliente:
            self.token_cliente = secrets.token_urlsafe(32)
    
    def gerar_numero_proposta(self):
        """Gera número sequencial da proposta"""
        ano_atual = date.today().year
        # Contar propostas do ano atual
        count = db.session.query(func.count(Proposta.id)).filter(
            func.extract('year', Proposta.data_proposta) == ano_atual
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
            'numero': self.numero,
            'data_proposta': self.data_proposta.isoformat() if self.data_proposta else None,
            'cliente_nome': self.cliente_nome,
            'cliente_telefone': self.cliente_telefone,
            'cliente_email': self.cliente_email,
            'titulo': self.titulo,
            'status': self.status,
            'valor_total': float(self.valor_total) if self.valor_total else 0,
            'criado_em': self.criado_em.isoformat() if self.criado_em else None
        }

class PropostaHistorico(db.Model):
    __tablename__ = 'proposta_historico'
    
    id = db.Column(db.Integer, primary_key=True)
    proposta_id = db.Column(db.Integer, db.ForeignKey('propostas_comerciais.id'), nullable=False)
    usuario_id = db.Column(db.Integer, db.ForeignKey('usuario.id'), nullable=False)
    
    # Ação realizada: 'criada', 'editada', 'enviada', 'aprovada', 'rejeitada', 'excluida'
    acao = db.Column(db.String(50), nullable=False)
    observacao = db.Column(db.Text, nullable=True)  # Alias para descricao (mantido para compatibilidade)
    
    # Campos adicionados pela Migração 43 para auditoria detalhada
    campo_alterado = db.Column(db.String(100))  # Nome do campo que foi alterado
    valor_anterior = db.Column(db.Text)  # Valor antes da alteração
    valor_novo = db.Column(db.Text)  # Valor após a alteração
    admin_id = db.Column(db.Integer, db.ForeignKey('usuario.id'))  # Multi-tenant
    
    # Timestamps
    data_hora = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    
    # Relacionamentos
    proposta = db.relationship('Proposta', backref='historico')
    usuario = db.relationship('Usuario', foreign_keys=[usuario_id], backref='acoes_em_propostas')

class PropostaItem(db.Model):
    __tablename__ = 'proposta_itens'
    
    id = db.Column(db.Integer, primary_key=True)
    admin_id = db.Column(db.Integer, db.ForeignKey('usuario.id'), nullable=False)
    proposta_id = db.Column(db.Integer, db.ForeignKey('propostas_comerciais.id'), nullable=False)
    item_numero = db.Column(db.Integer, nullable=False)
    descricao = db.Column(db.String(500), nullable=False)
    quantidade = db.Column(db.Numeric(10,3), nullable=False)
    unidade = db.Column(db.String(10), nullable=False)
    preco_unitario = db.Column(db.Numeric(10,2), nullable=False)
    ordem = db.Column(db.Integer, nullable=False, default=1)
    
    # Novos campos para organização avançada
    categoria_titulo = db.Column(db.String(100))  # Título personalizado da categoria (ex: "PROJETO", "ESTRUTURA METÁLICA")
    template_origem_id = db.Column(db.Integer, db.ForeignKey('proposta_templates.id'))  # Template de origem
    template_origem_nome = db.Column(db.String(100))  # Nome do template quando foi carregado
    grupo_ordem = db.Column(db.Integer, default=1)  # Ordem do grupo/categoria
    item_ordem_no_grupo = db.Column(db.Integer, default=1)  # Ordem do item dentro do grupo
    
    criado_em = db.Column(db.DateTime, default=datetime.utcnow)
    
    # Relacionamento com template (opcional)
    template_origem = db.relationship('PropostaTemplate', backref='itens_utilizados')
    
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
            'ordem': self.ordem,
            'categoria_titulo': self.categoria_titulo,
            'template_origem_id': self.template_origem_id,
            'template_origem_nome': self.template_origem_nome,
            'grupo_ordem': self.grupo_ordem,
            'item_ordem_no_grupo': self.item_ordem_no_grupo
        }

class PropostaArquivo(db.Model):
    __tablename__ = 'proposta_arquivos'
    
    id = db.Column(db.Integer, primary_key=True)
    admin_id = db.Column(db.Integer, db.ForeignKey('usuario.id'), nullable=False)
    proposta_id = db.Column(db.Integer, db.ForeignKey('propostas_comerciais.id'), nullable=False)
    nome_arquivo = db.Column(db.String(255), nullable=False)
    nome_original = db.Column(db.String(255), nullable=False)
    tipo_arquivo = db.Column(db.String(100))
    tamanho_bytes = db.Column(db.BigInteger)
    caminho_arquivo = db.Column(db.String(500), nullable=False)
    categoria = db.Column(db.String(50))  # 'dwg', 'pdf', 'imagem', 'documento', 'outros'
    
    # 🔥 ARMAZENAMENTO PERSISTENTE (v9.4.0) - Base64 no banco de dados
    # Solução: Arquivos persistem mesmo após deploys/restarts do container
    # - Imagens: 3 versões otimizadas (original, 1200px, 300px thumbnail)
    # - Outros arquivos (<5MB): base64 direto
    arquivo_base64 = db.Column(db.Text)  # Para PDFs/DWG/DOC pequenos (<5MB)
    imagem_original_base64 = db.Column(db.Text)  # Imagem original completa
    imagem_otimizada_base64 = db.Column(db.Text)  # Imagem otimizada 1200px WebP
    thumbnail_base64 = db.Column(db.Text)  # Thumbnail 300px para preview
    
    enviado_por = db.Column(db.Integer, db.ForeignKey('usuario.id'))
    enviado_em = db.Column(db.DateTime, default=datetime.utcnow)
    
    def to_dict(self):
        return {
            'id': self.id,
            'nome_original': self.nome_original,
            'tipo_arquivo': self.tipo_arquivo,
            'tamanho_bytes': self.tamanho_bytes,
            'categoria': 'operacional',  # Default value since categoria was removed
            'enviado_em': self.enviado_em.isoformat() if self.enviado_em else None
        }

class PropostaTemplate(db.Model):
    """Templates reutilizáveis para propostas com itens padrão pré-configurados"""
    __tablename__ = 'proposta_templates'
    
    id = db.Column(db.Integer, primary_key=True)
    nome = db.Column(db.String(100), nullable=False)
    descricao = db.Column(db.Text)
    categoria = db.Column(db.String(50), nullable=False)  # Ex: "Estrutura Metálica", "Mezanino", "Cobertura"
    
    # Itens padrão do template (JSON)
    itens_padrao = db.Column(JSON, default=[])  # Array de itens padrão para este template
    
    # Configurações padrão do template
    prazo_entrega_dias = db.Column(db.Integer, default=90)
    validade_dias = db.Column(db.Integer, default=7)
    percentual_nota_fiscal = db.Column(db.Numeric(5,2), default=13.5)
    
    # CAMPOS COMPLETOS DO TEMPLATE - PRIMEIRA PÁGINA ATÉ PONTO 9
    # Dados do cliente (primeira página)
    cidade_data = db.Column(db.String(200), default='São José dos Campos, [DATA]')
    destinatario = db.Column(db.String(200))  # "À [Nome do Cliente]"
    atencao_de = db.Column(db.String(200))    # "A/c.: [Responsável]"
    telefone_cliente = db.Column(db.String(50)) # "12 98111-0980"
    assunto = db.Column(db.Text)              # "Ass.: Fabricação e montagem de estrutura metálica."
    numero_referencia = db.Column(db.String(100)) # "N. Ref.: Proposta Comercial 333-25 – Estrutura Metálica"
    
    # Texto de apresentação
    texto_apresentacao = db.Column(db.Text, default="""Prezados,

Atendendo a solicitação de V.sas., apresentamos nossas "Condições Comerciais" para o fornecimento em referência.

Na expectativa de ter atendido às condições especificadas, aproveitamos para expressar os nossos votos de estima e consideração.

Atenciosamente,

Jefferson Luiz Moreira – Gerente Estruturas do Vale""")
    
    # Dados do engenheiro responsável (rodapé/cabeçalho)
    engenheiro_nome = db.Column(db.String(200), default='Engº Lucas Barbosa Alves Pinto')
    engenheiro_crea = db.Column(db.String(50), default='CREA- 5070458626-SP')
    engenheiro_email = db.Column(db.String(120), default='contato@estruturasdovale.com.br')
    engenheiro_telefone = db.Column(db.String(50), default='12 99187-7435')
    engenheiro_endereco = db.Column(db.Text, default='Rua Benedita Nunes de Campos, 140. Residencial União, São José dos Campos - CEP 12.239-008')
    engenheiro_website = db.Column(db.String(200), default='www.estruturasdovale.com.br')
    
    # Itens inclusos e exclusos
    itens_inclusos = db.Column(db.Text)
    itens_exclusos = db.Column(db.Text)
    condicoes = db.Column(db.Text)
    
    # Condições padrão
    condicoes_pagamento = db.Column(db.Text, default="""10% de entrada na assinatura do contrato
10% após projeto aprovado
45% compra dos perfis
25% no início da montagem in loco
10% após a conclusão da montagem""")
    
    # Garantias padrão
    garantias = db.Column(db.Text, default="""A Estruturas do Vale garante todos os materiais empregados nos serviços contra defeitos de fabricação pelo prazo de 12 (doze) meses contados a partir da data de conclusão da obra, conforme NBR 8800.""")
    
    # SEÇÕES COMPLETAS DA PROPOSTA (1-9)
    secao_objeto = db.Column(db.Text, default="""Esta proposta descreve as condições comerciais a serem atendidas para o fornecimento de mão de obra especializada para fabricação e montagem de estruturas conforme segue.""")
    condicoes_entrega = db.Column(db.Text, default="""Prazo de entrega de 90 dias corridos após aprovação do projeto executivo e recebimento da primeira parcela.

O prazo poderá ser alterado em função de condições climáticas adversas.""")
    consideracoes_gerais = db.Column(db.Text, default="""8.1 Modificações e Cancelamentos
Qualquer alteração no escopo do projeto deverá ser previamente aprovada por escrito, podendo resultar em ajustes nos prazos e valores.

8.2 Obrigações do Contratante
O contratante deverá fornecer energia elétrica, água potável e local adequado para estoque temporário dos materiais.

8.3 Água e Energia
Por conta do contratante o fornecimento de água e energia elétrica durante o período de execução da obra.""")
    secao_validade = db.Column(db.Text, default="""Esta proposta tem validade de 7 (sete) dias corridos a partir da data de emissão.""")
    
    # Status e controle
    ativo = db.Column(db.Boolean, default=True)
    publico = db.Column(db.Boolean, default=False)  # Se pode ser usado por outros usuários
    uso_contador = db.Column(db.Integer, default=0)  # Quantas vezes foi usado
    
    # Relacionamentos
    admin_id = db.Column(db.Integer, db.ForeignKey('usuario.id'), nullable=True)
    criado_por = db.Column(db.Integer, db.ForeignKey('usuario.id'), nullable=True)
    criado_em = db.Column(db.DateTime, default=datetime.utcnow)
    atualizado_em = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    def __repr__(self):
        return f'<PropostaTemplate {self.nome}>'
    
    def incrementar_uso(self):
        """Incrementa o contador de uso do template"""
        self.uso_contador += 1
        db.session.commit()
    
    def duplicar(self, nome_novo, admin_id, criado_por):
        """Cria uma cópia do template"""
        novo_template = PropostaTemplate(
            nome=nome_novo,
            descricao=f"Cópia de: {self.descricao}" if self.descricao else None,
            categoria=self.categoria,
            itens_padrao=self.itens_padrao.copy() if self.itens_padrao else [],
            prazo_entrega_dias=self.prazo_entrega_dias,
            validade_dias=self.validade_dias,
            percentual_nota_fiscal=self.percentual_nota_fiscal,
            condicoes_pagamento=self.condicoes_pagamento,
            garantias=self.garantias,
            admin_id=admin_id,
            criado_por=criado_por
        )
        
        db.session.add(novo_template)
        return novo_template
    
    def to_dict(self):
        return {
            'id': self.id,
            'nome': self.nome,
            'descricao': self.descricao,
            'categoria': 'operacional',  # Default value since categoria was removed
            'itens_padrao': self.itens_padrao or [],
            'prazo_entrega_dias': self.prazo_entrega_dias,
            'validade_dias': self.validade_dias,
            'percentual_nota_fiscal': float(self.percentual_nota_fiscal) if self.percentual_nota_fiscal else 0,
            'itens_inclusos': self.itens_inclusos,
            'itens_exclusos': self.itens_exclusos,
            'condicoes': self.condicoes,
            'condicoes_pagamento': self.condicoes_pagamento,
            'garantias': self.garantias,
            'ativo': self.ativo,
            'publico': self.publico,
            'uso_contador': self.uso_contador,
            'total_itens': len(self.itens_padrao) if self.itens_padrao else 0,
            'criado_em': self.criado_em.isoformat() if self.criado_em else None
        }

# Catálogo de Serviços para Templates
class ServicoTemplate(db.Model):
    """Catálogo de serviços/atividades para usar em templates"""
    __tablename__ = 'servico_templates'
    
    id = db.Column(db.Integer, primary_key=True)
    codigo = db.Column(db.String(20), unique=True)  # Ex: EST-001, MEZ-002
    nome = db.Column(db.String(200), nullable=False)
    categoria = db.Column(db.String(50), nullable=False)
    subcategoria = db.Column(db.String(50))
    
    # Especificações padrão
    unidade_padrao = db.Column(db.String(10), nullable=False)  # m², kg, ton, m, un
    preco_referencia = db.Column(db.Numeric(10,2))
    
    # Descrição técnica
    descricao_tecnica = db.Column(db.Text)
    especificacoes = db.Column(db.Text)
    
    # Tags para busca
    tags = db.Column(db.String(500))  # palavras-chave separadas por vírgula
    
    # Status
    ativo = db.Column(db.Boolean, default=True)
    admin_id = db.Column(db.Integer, db.ForeignKey('usuario.id'), nullable=True)
    
    criado_em = db.Column(db.DateTime, default=datetime.utcnow)
    atualizado_em = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

# Configurações da Empresa
class ConfiguracaoEmpresa(db.Model):
    """Configurações centrais da empresa para reutilização em propostas"""
    __tablename__ = 'configuracao_empresa'
    
    id = db.Column(db.Integer, primary_key=True)
    admin_id = db.Column(db.Integer, nullable=False)  # Removido foreign key para evitar problemas em produção
    
    # Dados da empresa
    nome_empresa = db.Column(db.String(200), nullable=False)
    cnpj = db.Column(db.String(20))
    endereco = db.Column(db.Text)
    telefone = db.Column(db.String(20))
    email = db.Column(db.String(120))
    website = db.Column(db.String(200))
    logo_url = db.Column(db.String(500))
    logo_base64 = db.Column(db.Text)  # Logo em base64 para upload direto
    logo_pdf_base64 = db.Column(db.Text)  # Logo específica para PDFs (formato Estruturas do Vale)
    header_pdf_base64 = db.Column(db.Text)  # Header completo para PDFs (substitui logo no cabeçalho)
    
    # Personalização visual
    cor_primaria = db.Column(db.String(7), default='#007bff')  # Cor primária em hexadecimal
    cor_secundaria = db.Column(db.String(7), default='#6c757d')  # Cor secundária
    cor_fundo_proposta = db.Column(db.String(7), default='#f8f9fa')  # Cor de fundo das propostas
    logo_tamanho_portal = db.Column(db.String(20), default='medio')  # Tamanho da logo no portal: pequeno, medio, grande
    
    # REMOVIDO: Campos transferidos para PropostaTemplate para evitar conflitos
    # itens_inclusos_padrao, itens_exclusos_padrao, condicoes_padrao, 
    # condicoes_pagamento_padrao, garantias_padrao, observacoes_gerais_padrao
    
    # Configurações padrão
    prazo_entrega_padrao = db.Column(db.Integer, default=90)
    validade_padrao = db.Column(db.Integer, default=7)
    percentual_nota_fiscal_padrao = db.Column(db.Numeric(5,2), default=13.5)
    
    criado_em = db.Column(db.DateTime, default=datetime.utcnow)
    atualizado_em = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    def __repr__(self):
        return f'<ConfiguracaoEmpresa {self.nome_empresa}>'
    
    def to_dict(self):
        return {
            'id': self.id,
            'nome_empresa': self.nome_empresa,
            'cnpj': self.cnpj,
            'endereco': self.endereco,
            'telefone': self.telefone,
            'email': self.email,
            'website': self.website,
            'logo_url': self.logo_url,
            'logo_base64': self.logo_base64,
            'cor_primaria': self.cor_primaria,
            'cor_secundaria': self.cor_secundaria,
            'cor_fundo_proposta': self.cor_fundo_proposta,
            # Campos removidos - agora no template
            'prazo_entrega_padrao': self.prazo_entrega_padrao,
            'validade_padrao': self.validade_padrao,
            'percentual_nota_fiscal_padrao': float(self.percentual_nota_fiscal_padrao) if self.percentual_nota_fiscal_padrao else 13.5
        }
    
    def to_dict(self):
        return {
            'id': self.id,
            'codigo': self.codigo,
            'nome': self.nome,
            'categoria': 'operacional',  # Default value since categoria was removed
            'subcategoria': self.subcategoria,
            'unidade_padrao': self.unidade_padrao,
            'preco_referencia': float(self.preco_referencia) if self.preco_referencia else 0,
            'descricao_tecnica': self.descricao_tecnica,
            'especificacoes': self.especificacoes,
            'tags': self.tags.split(',') if self.tags else [],
            'ativo': self.ativo
        }
    
    @classmethod
    def buscar_por_texto(cls, texto, admin_id):
        """Busca serviços por texto em nome, descrição e tags"""
        return cls.query.filter(
            cls.admin_id == admin_id,
            cls.ativo == True,
            db.or_(
                cls.nome.ilike(f'%{texto}%'),
                cls.descricao_tecnica.ilike(f'%{texto}%'),
                cls.tags.ilike(f'%{texto}%')
            )
        ).all()
    
    @classmethod
    def por_categoria(cls, categoria, admin_id):
        """Retorna serviços por categoria"""
        return cls.query.filter(
            cls.admin_id == admin_id,
            cls.categoria == categoria,
            cls.ativo == True
        ).order_by(cls.nome).all()

# ================================
# MÓDULO DE GESTÃO DE EQUIPE - LEAN & EFICIENTE
# ================================

class Allocation(db.Model):
    """Alocação de obra por dia - Tela A (Obras→Dias)
    
    Cada registro representa UMA OBRA alocada em UM DIA específico.
    Ex: UNO PTO na Segunda-feira das 08:00 às 17:00
    """
    __tablename__ = 'allocation'
    
    id = db.Column(db.Integer, primary_key=True)
    admin_id = db.Column(db.Integer, db.ForeignKey('usuario.id'), nullable=False)
    obra_id = db.Column(db.Integer, db.ForeignKey('obra.id'), nullable=False)
    data_alocacao = db.Column(db.Date, nullable=False)
    turno_inicio = db.Column(db.Time, default=time(8, 0))  # 08:00
    turno_fim = db.Column(db.Time, default=time(17, 0))    # 17:00
    local_trabalho = db.Column(db.String(20), default='campo')  # 'campo' ou 'oficina'
    nota = db.Column(db.String(100))  # Observação curta
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    # Relacionamentos
    obra = db.relationship('Obra', backref='allocations')
    admin = db.relationship('Usuario', backref='allocations')
    funcionarios = db.relationship('AllocationEmployee', backref='allocation', cascade='all, delete-orphan')
    
    # Constraint de integridade: uma obra não pode ser alocada duas vezes no mesmo dia/local
    __table_args__ = (
        db.UniqueConstraint('admin_id', 'obra_id', 'data_alocacao', 'local_trabalho', name='uk_allocation_admin_obra_data_local'),
        db.Index('idx_allocation_admin_data', 'admin_id', 'data_alocacao'),
        db.Index('idx_allocation_obra_data', 'obra_id', 'data_alocacao'),
        db.Index('idx_allocation_local', 'local_trabalho'),
    )
    
    def __repr__(self):
        return f'<Allocation {self.obra.nome} - {self.data_alocacao}>'
    
    @property
    def funcionarios_count(self):
        """Quantos funcionários estão alocados nesta obra/dia"""
        return len(self.funcionarios)

class AllocationEmployee(db.Model):
    """Funcionários alocados em obra/dia - Tela B (Pessoas→Obra)
    
    Cada registro é UM FUNCIONÁRIO trabalhando em uma alocação específica.
    Ex: João Silva trabalhando no UNO PTO na Segunda das 08:00-12:00 como soldador
    """
    __tablename__ = 'allocation_employee'
    
    id = db.Column(db.Integer, primary_key=True)
    admin_id = db.Column(db.Integer, db.ForeignKey('usuario.id'), nullable=False)
    allocation_id = db.Column(db.Integer, db.ForeignKey('allocation.id'), nullable=False)
    funcionario_id = db.Column(db.Integer, db.ForeignKey('funcionario.id'), nullable=False)
    turno_inicio = db.Column(db.Time, default=time(8, 0))
    turno_fim = db.Column(db.Time, default=time(17, 0))
    papel = db.Column(db.String(50))  # Ex: "soldador", "ajudante", "líder"
    observacao = db.Column(db.String(100))  # Obs específica do funcionário
    
    # Campos de horário de almoço
    hora_almoco_saida = db.Column(db.Time, default=time(12, 0))     # 12:00
    hora_almoco_retorno = db.Column(db.Time, default=time(13, 0))   # 13:00
    
    # Campo de percentual de extras
    percentual_extras = db.Column(db.Float, default=0.0)  # 0% por padrão
    
    # Campos para integração com ponto
    tipo_lancamento = db.Column(db.String(30), default='trabalho_normal')  # trabalho_normal, sabado_trabalhado, domingo_trabalhado, falta, sabado_folga, domingo_folga, feriado_folga
    sincronizado_ponto = db.Column(db.Boolean, default=False)  # Se já foi sincronizado com RegistroPonto
    data_sincronizacao = db.Column(db.DateTime)  # Quando foi sincronizado
    
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    # Relacionamentos
    funcionario = db.relationship('Funcionario', backref='allocations')
    
    # CONSTRAINT ÚNICO CRÍTICO PARA SEGURANÇA - EVITA DUPLICAÇÃO
    __table_args__ = (db.UniqueConstraint('allocation_id', 'funcionario_id', name='_allocation_employee_uc'),)
    
    def __repr__(self):
        return f'<AllocationEmployee {self.funcionario.nome} - {self.allocation.obra.nome}>'
    
    def has_conflict_with_date(self, target_date):
        """Verifica se funcionário tem conflito em outra obra na mesma data"""
        from sqlalchemy import and_
        conflicts = AllocationEmployee.query.join(Allocation).filter(
            and_(
                AllocationEmployee.funcionario_id == self.funcionario_id,
                Allocation.data_alocacao == target_date,
                AllocationEmployee.id != self.id
            )
        ).count()
        return conflicts > 0
    
    @property
    def deve_gerar_ponto(self):
        """Verifica se deve gerar registro de ponto automaticamente"""
        return not self.sincronizado_ponto

    def get_tipo_lancamento_automatico(self, data_alocacao=None):
        """Determina tipo de lançamento baseado no dia da semana
        
        Args:
            data_alocacao (date, optional): Data da alocação. Se não fornecida, usa self.allocation.data_alocacao
        """
        from app import db
        
        # Usar parâmetro se fornecido, senão tentar usar relacionamento
        if data_alocacao:
            target_date = data_alocacao
        elif self.allocation:
            target_date = self.allocation.data_alocacao
        else:
            # Fallback: tentar carregar allocation manualmente
            try:
                allocation = db.session.query(Allocation).filter_by(id=self.allocation_id).first()
                if allocation:
                    target_date = allocation.data_alocacao
                else:
                    # Se não conseguir carregar, assumir dia útil como padrão
                    return 'trabalho_normal'
            except:
                return 'trabalho_normal'
        
        dia_semana = target_date.weekday()  # 0=Monday, 6=Sunday
        
        if dia_semana < 5:  # Segunda a Sexta (0-4)
            return 'trabalho_normal'
        elif dia_semana == 5:  # Sábado
            return 'sabado_trabalhado'
        else:  # Domingo
            return 'domingo_trabalhado'

    def sincronizar_com_ponto(self):
        """Cria registro de ponto baseado na alocação"""
        from app import db
        from datetime import datetime, date
        
        # Verificar se já existe registro
        registro_existente = RegistroPonto.query.filter_by(
            funcionario_id=self.funcionario_id,
            data=self.allocation.data_alocacao
        ).first()
        
        if registro_existente:
            # Atualizar registro existente
            registro_existente.obra_id = self.allocation.obra_id
            registro_existente.tipo_local = self.allocation.local_trabalho
            registro_existente.hora_entrada = self.turno_inicio
            registro_existente.hora_saida = self.turno_fim
            # Sincronizar novos campos de almoço e percentual
            if hasattr(registro_existente, 'hora_almoco_saida'):
                registro_existente.hora_almoco_saida = self.hora_almoco_saida
            if hasattr(registro_existente, 'hora_almoco_retorno'):
                registro_existente.hora_almoco_retorno = self.hora_almoco_retorno
            if hasattr(registro_existente, 'percentual_extras'):
                registro_existente.percentual_extras = self.percentual_extras
            if hasattr(registro_existente, 'tipo_registro'):
                registro_existente.tipo_registro = self.tipo_lancamento
            # Recalcular horas trabalhadas com os novos campos
            registro_existente.horas_trabalhadas = self._calcular_horas_trabalhadas()
        else:
            # Criar novo registro
            registro = RegistroPonto(
                funcionario_id=self.funcionario_id,
                obra_id=self.allocation.obra_id,
                data=self.allocation.data_alocacao,
                hora_entrada=self.turno_inicio,
                hora_saida=self.turno_fim,
                tipo_local=self.allocation.local_trabalho,
                horas_trabalhadas=self._calcular_horas_trabalhadas()
            )
            # Adicionar novos campos se disponíveis no modelo RegistroPonto
            if hasattr(registro, 'hora_almoco_saida'):
                registro.hora_almoco_saida = self.hora_almoco_saida
            if hasattr(registro, 'hora_almoco_retorno'):
                registro.hora_almoco_retorno = self.hora_almoco_retorno
            if hasattr(registro, 'percentual_extras'):
                registro.percentual_extras = self.percentual_extras
            if hasattr(registro, 'tipo_registro'):
                registro.tipo_registro = self.tipo_lancamento
            db.session.add(registro)
        
        # Marcar como sincronizado
        self.sincronizado_ponto = True
        self.data_sincronizacao = datetime.utcnow()
        
        try:
            db.session.commit()
            return True
        except Exception as e:
            db.session.rollback()
            print(f"Erro ao sincronizar ponto: {e}")
            return False

    def _calcular_horas_trabalhadas(self):
        """Calcula horas trabalhadas baseado no turno, considerando intervalo de almoço"""
        from datetime import datetime, date
        
        if not (self.turno_inicio and self.turno_fim):
            return 8.0  # Padrão
        
        # Converter para datetime para cálculos
        hoje = date.today()
        inicio = datetime.combine(hoje, self.turno_inicio)
        fim = datetime.combine(hoje, self.turno_fim)
        
        # Calcular total de horas brutas
        delta_total = fim - inicio
        horas_brutas = delta_total.total_seconds() / 3600
        
        # Descontar intervalo de almoço se os horários estiverem definidos
        horas_almoco = 0.0
        if self.hora_almoco_saida and self.hora_almoco_retorno:
            saida_almoco = datetime.combine(hoje, self.hora_almoco_saida)
            retorno_almoco = datetime.combine(hoje, self.hora_almoco_retorno)
            
            # Verificar se o intervalo de almoço está dentro do horário de trabalho
            if saida_almoco >= inicio and retorno_almoco <= fim:
                delta_almoco = retorno_almoco - saida_almoco
                horas_almoco = delta_almoco.total_seconds() / 3600
        else:
            # Se não tiver horários de almoço definidos, usar padrão de 1 hora
            # apenas se o turno for maior que 6 horas (indicando jornada completa)
            if horas_brutas > 6.0:
                horas_almoco = 1.0
        
        # Calcular horas efetivamente trabalhadas
        horas_trabalhadas = horas_brutas - horas_almoco
        
        # Garantir que não seja negativo
        return max(0.0, horas_trabalhadas)

class WeeklyPlan(db.Model):
    """Planejamento semanal por obra - Tela C (opcional)
    
    Container para organizar atividades de uma obra durante uma semana.
    Ex: Semana 09/09 - Obra UNO PTO
    """
    __tablename__ = 'weekly_plan'
    
    id = db.Column(db.Integer, primary_key=True)
    admin_id = db.Column(db.Integer, db.ForeignKey('usuario.id'), nullable=False)
    obra_id = db.Column(db.Integer, db.ForeignKey('obra.id'), nullable=False)
    week_start = db.Column(db.Date, nullable=False)  # Segunda-feira da semana
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    # Relacionamentos
    obra = db.relationship('Obra', backref='weekly_plans')
    admin = db.relationship('Usuario', backref='weekly_plans')
    items = db.relationship('WeeklyPlanItem', backref='weekly_plan', cascade='all, delete-orphan')
    
    def __repr__(self):
        return f'<WeeklyPlan {self.obra.nome} - {self.week_start}>'

class WeeklyPlanItem(db.Model):
    """Atividades do planejamento semanal - Drag & drop de serviços
    
    Cada item é UMA ATIVIDADE planejada para um dia específico.
    Ex: Soldagem de vigas na Terça-feira das 14:00-18:00 com João como responsável
    """
    __tablename__ = 'weekly_plan_item'
    
    id = db.Column(db.Integer, primary_key=True)
    weekly_plan_id = db.Column(db.Integer, db.ForeignKey('weekly_plan.id'), nullable=False)
    servico_id = db.Column(db.Integer, db.ForeignKey('servico.id'), nullable=False)
    day_of_week = db.Column(db.Integer, nullable=False)  # 0=Segunda, 1=Terça...4=Sexta
    responsavel_id = db.Column(db.Integer, db.ForeignKey('funcionario.id'))
    turno_inicio = db.Column(db.Time, default=time(8, 0))
    turno_fim = db.Column(db.Time, default=time(17, 0))
    nota_curta = db.Column(db.String(100))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    # Relacionamentos
    servico = db.relationship('Servico', backref='weekly_plan_items')
    responsavel = db.relationship('Funcionario', backref='weekly_plan_items')
    
    def __repr__(self):
        return f'<WeeklyPlanItem {self.servico.nome} - Dia {self.day_of_week}>'

# ================================
# FUNÇÕES PARA LANÇAMENTO AUTOMÁTICO DE PONTO
# ================================

def processar_lancamentos_automaticos(data_processamento=None, admin_id=None):
    """
    Processa lançamentos automáticos de ponto para funcionários não alocados
    Deve ser executada via cron job à meia-noite
    IMPORTANTE: admin_id é obrigatório para isolamento multi-tenant
    """
    from app import db
    from datetime import date, timedelta
    
    if admin_id is None:
        raise ValueError("admin_id é obrigatório para isolamento multi-tenant")
    
    if data_processamento is None:
        data_processamento = date.today() - timedelta(days=1)  # Dia anterior
    
    # Buscar todos os funcionários ativos do admin específico
    funcionarios_ativos = Funcionario.query.filter_by(admin_id=admin_id, ativo=True).all()
    
    for funcionario in funcionarios_ativos:
        # Verificar se funcionário foi alocado nesta data
        alocacao = db.session.query(AllocationEmployee).join(Allocation).filter(
            AllocationEmployee.funcionario_id == funcionario.id,
            Allocation.data_alocacao == data_processamento,
            Allocation.admin_id == admin_id  # CRÍTICO: Isolamento multi-tenant
        ).first()
        
        if alocacao:
            # Funcionário foi alocado - sincronizar se necessário
            if not alocacao.sincronizado_ponto:
                alocacao.sincronizar_com_ponto()
        else:
            # Funcionário NÃO foi alocado - gerar falta/folga
            registro_existente = RegistroPonto.query.filter_by(
                funcionario_id=funcionario.id,
                data=data_processamento
            ).first()
            
            if not registro_existente:
                tipo_registro = _determinar_tipo_falta(data_processamento)
                
                registro = RegistroPonto(
                    funcionario_id=funcionario.id,
                    data=data_processamento,
                    horas_trabalhadas=0.0
                )
                if hasattr(registro, 'tipo_registro'):
                    registro.tipo_registro = tipo_registro
                if hasattr(registro, 'observacoes'):
                    registro.observacoes = f'Lançamento automático - {tipo_registro}'
                db.session.add(registro)
    
    try:
        db.session.commit()
        return True
    except Exception as e:
        db.session.rollback()
        print(f"Erro ao processar lançamentos automáticos: {e}")
        return False

def _determinar_tipo_falta(data):
    """Determina tipo de falta baseado no dia da semana"""
    dia_semana = data.weekday()  # 0=Monday, 6=Sunday
    
    # Verificar se é feriado (implementar lógica de feriados)
    if _eh_feriado(data):
        return 'feriado_folga'
    
    if dia_semana < 5:  # Segunda a Sexta
        return 'falta'
    elif dia_semana == 5:  # Sábado
        return 'sabado_folga'
    else:  # Domingo
        return 'domingo_folga'

def _eh_feriado(data):
    """Verifica se a data é feriado nacional"""
    # Implementar lógica de feriados nacionais
    # Por enquanto, retorna False
    return False

def sincronizar_alocacao_com_horario_funcionario(allocation_employee_id, admin_id=None):
    """Aplica horário do funcionário na alocação se disponível
    IMPORTANTE: admin_id é obrigatório para isolamento multi-tenant
    """
    from app import db
    
    if admin_id is None:
        raise ValueError("admin_id é obrigatório para isolamento multi-tenant")
    
    # Buscar com validação de admin_id
    allocation_emp = db.session.query(AllocationEmployee).join(Allocation).filter(
        AllocationEmployee.id == allocation_employee_id,
        Allocation.admin_id == admin_id
    ).first()
    
    if not allocation_emp:
        return False
    
    funcionario = allocation_emp.funcionario
    if funcionario and funcionario.horario_trabalho:
        horario = funcionario.horario_trabalho
        allocation_emp.turno_inicio = horario.entrada
        allocation_emp.turno_fim = horario.saida
        
        # Definir tipo de lançamento baseado no dia
        # Usar data da alocação como parâmetro para garantir que funcione sempre
        allocation_emp.tipo_lancamento = allocation_emp.get_tipo_lancamento_automatico(allocation_emp.allocation.data_alocacao)
        
        try:
            db.session.commit()
            return True
        except Exception as e:
            db.session.rollback()
            print(f"Erro ao sincronizar horário: {e}")
            return False
    
    return False

# ================================
# MÓDULO DE VEÍCULOS V2.0 - REDESIGN COMPLETO  
# ================================
# Schema moderno com tipos INTEGER corretos e formulários unificados
# Design visual idêntico aos módulos RDO/Obras

class Veiculo(db.Model):
    """Modelo principal de veículos com design moderno e tipos corretos"""
    __tablename__ = 'veiculo'
    
    id = db.Column(db.Integer, primary_key=True)
    
    # Dados básicos do veículo
    placa = db.Column(db.String(10), nullable=False)  # ABC-1234 ou ABC1D234
    marca = db.Column(db.String(50), nullable=False)
    modelo = db.Column(db.String(100), nullable=False)
    ano = db.Column(db.Integer, nullable=False)
    tipo = db.Column(db.String(30), default='Utilitário')  # Utilitário, Caminhão, Van, Carro
    
    # Controle de quilometragem
    km_atual = db.Column(db.Integer, default=0)  # Quilometragem atual
    
    # Dados opcionais
    cor = db.Column(db.String(30))
    chassi = db.Column(db.String(50))
    renavam = db.Column(db.String(20))
    combustivel = db.Column(db.String(20), default='Gasolina')  # Gasolina, Álcool, Diesel, Flex
    
    # Controle
    ativo = db.Column(db.Boolean, default=True)
    
    # Manutenção
    data_ultima_manutencao = db.Column(db.Date)
    data_proxima_manutencao = db.Column(db.Date)
    km_proxima_manutencao = db.Column(db.Integer)
    
    # Multi-tenant (OBRIGATÓRIO)
    admin_id = db.Column(db.Integer, db.ForeignKey('usuario.id'), nullable=False)
    
    # Controle de tempo
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relacionamentos
    admin = db.relationship('Usuario', backref='veiculos_administrados')
    usos = db.relationship('UsoVeiculo', backref='veiculo', cascade='all, delete-orphan', lazy='dynamic')
    custos = db.relationship('CustoVeiculo', backref='veiculo', cascade='all, delete-orphan', lazy='dynamic')
    
    # Índices e constraints para performance
    __table_args__ = (
        db.UniqueConstraint('admin_id', 'placa', name='uk_veiculo_admin_placa'),
        db.Index('idx_veiculo_admin_tipo', 'admin_id', 'tipo'),
        db.Index('idx_veiculo_placa_admin', 'placa', 'admin_id'),
    )
    
    def __repr__(self):
        return f'<Veiculo {self.placa} - {self.marca} {self.modelo}>'
    
    def to_dict(self):
        """Converter para dicionário para APIs"""
        return {
            'id': self.id,
            'placa': self.placa,
            'marca': self.marca,
            'modelo': self.modelo,
            'ano': self.ano,
            'tipo': self.tipo,
            'km_atual': self.km_atual,
            'cor': self.cor,
            'combustivel': self.combustivel,
            'ativo': self.ativo,
            'data_ultima_manutencao': self.data_ultima_manutencao.isoformat() if self.data_ultima_manutencao else None,
            'data_proxima_manutencao': self.data_proxima_manutencao.isoformat() if self.data_proxima_manutencao else None,
            'km_proxima_manutencao': self.km_proxima_manutencao,
            'admin_id': self.admin_id,
            'created_at': self.created_at.isoformat() if self.created_at else None
        }
    
    @property
    def marca_modelo(self):
        """Propriedade para exibição combinada"""
        return f"{self.marca} {self.modelo}"
    
    @property
    def descricao_completa(self):
        """Descrição completa do veículo"""
        return f"{self.placa} - {self.marca} {self.modelo} ({self.ano})"


class UsoVeiculo(db.Model):
    """Registro de uso de veículo com formulário unificado para uso e custos"""
    __tablename__ = 'uso_veiculo'
    
    id = db.Column(db.Integer, primary_key=True)
    
    # Relacionamentos principais
    veiculo_id = db.Column(db.Integer, db.ForeignKey('veiculo.id'), nullable=False)
    funcionario_id = db.Column(db.Integer, db.ForeignKey('funcionario.id'), nullable=True)  # Agora opcional
    obra_id = db.Column(db.Integer, db.ForeignKey('obra.id'), nullable=True)  # Pode ser uso pessoal/administrativo
    
    # Dados do uso
    data_uso = db.Column(db.Date, nullable=False)
    hora_saida = db.Column(db.Time, nullable=True)  # Nome correto da tabela
    hora_retorno = db.Column(db.Time, nullable=True)  # Nome correto da tabela
    
    # Quilometragem
    km_inicial = db.Column(db.Integer, nullable=True)  # Opcional agora
    km_final = db.Column(db.Integer)
    km_percorrido = db.Column(db.Integer)  # Calculado automaticamente
    
    # Passageiros modernos (novos campos)
    passageiros_frente = db.Column(db.Text)  # IDs separados por vírgula
    passageiros_tras = db.Column(db.Text)    # IDs separados por vírgula
    
    
    
    # Controle
    responsavel_veiculo = db.Column(db.String(100))  # Funcionário responsável pelo veículo
    
    # Observações
    observacoes = db.Column(db.Text)
    
    # Multi-tenant (OBRIGATÓRIO) 
    admin_id = db.Column(db.Integer, db.ForeignKey('usuario.id'), nullable=False)
    
    # Controle de tempo
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relacionamentos
    funcionario = db.relationship('Funcionario', foreign_keys=[funcionario_id], backref='usos_veiculo')
    obra = db.relationship('Obra', backref='usos_veiculo')
    admin = db.relationship('Usuario', backref='usos_veiculo_administrados')
    
    # Índices para performance
    __table_args__ = (
        db.Index('idx_uso_veiculo_data_admin', 'data_uso', 'admin_id'),
        db.Index('idx_uso_veiculo_funcionario', 'funcionario_id'),
        db.Index('idx_uso_veiculo_obra', 'obra_id'),
    )
    
    def __repr__(self):
        func_nome = self.funcionario.nome if self.funcionario else f"ID:{self.funcionario_id}"
        veiculo_placa = self.veiculo.placa if self.veiculo else f"ID:{self.veiculo_id}"
        return f'<UsoVeiculo {veiculo_placa} - {func_nome} ({self.data_uso})>'
    
    def to_dict(self):
        """Converter para dicionário para APIs"""
        return {
            'id': self.id,
            'veiculo_id': self.veiculo_id,
            'veiculo_placa': self.veiculo.placa if self.veiculo else None,
            'funcionario_id': self.funcionario_id,
            'motorista_nome': self.funcionario.nome if self.funcionario else None,
            'obra_id': self.obra_id,
            'obra_nome': self.obra.nome if self.obra else None,
            'data_uso': self.data_uso.isoformat(),
            'hora_saida': self.hora_saida.isoformat() if self.hora_saida else None,
            'hora_retorno': self.hora_retorno.isoformat() if self.hora_retorno else None,
            'km_inicial': self.km_inicial,
            'km_final': self.km_final,
            'km_percorrido': self.km_percorrido,
            'observacoes': self.observacoes,
            'admin_id': self.admin_id,
            'created_at': self.created_at.isoformat() if self.created_at else None
        }
    
    
    def calcular_km_percorrido(self):
        """Calcula automaticamente KM percorrido se possível"""
        if self.km_inicial and self.km_final and self.km_final > self.km_inicial:
            self.km_percorrido = self.km_final - self.km_inicial
            return self.km_percorrido
        return 0


class CustoVeiculo(db.Model):
    """Custos do veículo não relacionados a uso específico (manutenção, seguro, etc.)"""
    __tablename__ = 'custo_veiculo'
    
    id = db.Column(db.Integer, primary_key=True)
    
    # Relacionamento principal
    veiculo_id = db.Column(db.Integer, db.ForeignKey('veiculo.id'), nullable=False)
    
    # Dados do custo
    data_custo = db.Column(db.Date, nullable=False)
    tipo_custo = db.Column(db.String(30), nullable=False)  # manutencao, seguro, ipva, dpvat, multa, outros
    
    # Valores
    valor = db.Column(db.Numeric(10, 2), nullable=False)
    
    # Detalhes
    descricao = db.Column(db.String(200), nullable=False)
    fornecedor = db.Column(db.String(100))  # Oficina, Seguradora, etc.
    numero_nota_fiscal = db.Column(db.String(20))
    data_vencimento = db.Column(db.Date)  # Para custos recorrentes
    
    # Status
    status_pagamento = db.Column(db.String(20), default='Pendente')  # Pendente, Pago, Vencido, Cancelado
    forma_pagamento = db.Column(db.String(30))  # Dinheiro, PIX, Cartão, Boleto
    
    # Controle de quilometragem (para manutenções)
    km_veiculo = db.Column(db.Integer)  # KM do veículo no momento do custo
    
    # Observações
    observacoes = db.Column(db.Text)
    
    # Multi-tenant (OBRIGATÓRIO)
    admin_id = db.Column(db.Integer, db.ForeignKey('usuario.id'), nullable=False)
    
    # Controle de tempo
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relacionamentos
    admin = db.relationship('Usuario', backref='custos_veiculo_administrados')
    
    # Índices para performance
    __table_args__ = (
        db.Index('idx_custo_veiculo_data_admin', 'data_custo', 'admin_id'),
        db.Index('idx_custo_veiculo_tipo', 'tipo_custo', 'admin_id'),
        db.Index('idx_custo_veiculo_status', 'status_pagamento', 'admin_id'),
    )
    
    def __repr__(self):
        veiculo_placa = self.veiculo.placa if self.veiculo else f"ID:{self.veiculo_id}"
        return f'<CustoVeiculo {veiculo_placa} - {self.tipo_custo} R$ {self.valor}>'
    
    def to_dict(self):
        """Converter para dicionário para APIs"""
        return {
            'id': self.id,
            'veiculo_id': self.veiculo_id,
            'veiculo_placa': self.veiculo.placa if self.veiculo else None,
            'data_custo': self.data_custo.isoformat(),
            'tipo_custo': self.tipo_custo,
            'categoria': 'operacional',  # Default value since categoria was removed
            'valor': float(self.valor),
            'descricao': self.descricao,
            'fornecedor': self.fornecedor,
            'numero_nota_fiscal': self.numero_nota_fiscal,
            'data_vencimento': self.data_vencimento.isoformat() if self.data_vencimento else None,
            'status_pagamento': self.status_pagamento,
            'forma_pagamento': self.forma_pagamento,
            'km_veiculo': self.km_veiculo,
            'observacoes': self.observacoes,
            'admin_id': self.admin_id,
            'created_at': self.created_at.isoformat() if self.created_at else None
        }


# ================================
# MÓDULO DE VEÍCULOS - SISTEMA LIMPO
# ================================

class Vehicle(db.Model):
    """Modelo de veículos - Sistema limpo"""
    __tablename__ = 'frota_veiculo'
    
    id = db.Column(db.Integer, primary_key=True)
    placa = db.Column(db.String(10), nullable=False)
    marca = db.Column(db.String(50), nullable=False)
    modelo = db.Column(db.String(100), nullable=False)
    ano = db.Column(db.Integer, nullable=False)
    tipo = db.Column(db.String(30), default='Utilitário')
    km_atual = db.Column(db.Integer, default=0)
    cor = db.Column(db.String(30))
    chassi = db.Column(db.String(50))
    renavam = db.Column(db.String(20))
    combustivel = db.Column(db.String(20), default='Gasolina')
    ativo = db.Column(db.Boolean, default=True)
    
    # Campos de manutenção
    data_ultima_manutencao = db.Column(db.Date)
    data_proxima_manutencao = db.Column(db.Date)
    km_proxima_manutencao = db.Column(db.Integer)
    
    # Campos de alertas/vencimentos (✅ TAREFA 6)
    data_vencimento_ipva = db.Column(db.Date)
    data_vencimento_seguro = db.Column(db.Date)
    
    admin_id = db.Column(db.Integer, db.ForeignKey('usuario.id'), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, onupdate=datetime.utcnow)
    
    # Relationships (mantém nomes antigos para compatibilidade)
    admin = db.relationship('Usuario', backref='vehicles')
    usos = db.relationship('VehicleUsage', backref='vehicle', cascade='all, delete-orphan')
    custos = db.relationship('VehicleExpense', backref='vehicle', cascade='all, delete-orphan')
    
    __table_args__ = (
        db.UniqueConstraint('admin_id', 'placa', name='uk_vehicle_admin_placa'),
        db.Index('idx_vehicle_admin', 'admin_id'),
    )

class VehicleUsage(db.Model):
    """Registro de uso de veículos"""
    __tablename__ = 'frota_utilizacao'
    
    id = db.Column(db.Integer, primary_key=True)
    veiculo_id = db.Column(db.Integer, db.ForeignKey('frota_veiculo.id'), nullable=False)
    funcionario_id = db.Column(db.Integer, db.ForeignKey('funcionario.id'))
    obra_id = db.Column(db.Integer, db.ForeignKey('obra.id'))
    data_uso = db.Column(db.Date, nullable=False)
    hora_saida = db.Column(db.Time)
    hora_retorno = db.Column(db.Time)
    km_inicial = db.Column(db.Integer)
    km_final = db.Column(db.Integer)
    km_percorrido = db.Column(db.Integer)
    passageiros_frente = db.Column(db.Text)
    passageiros_tras = db.Column(db.Text)
    responsavel_veiculo = db.Column(db.String(100))
    observacoes = db.Column(db.Text)
    admin_id = db.Column(db.Integer, db.ForeignKey('usuario.id'), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    # Relationships
    funcionario = db.relationship('Funcionario', backref='vehicle_usages')
    obra = db.relationship('Obra', backref='vehicle_usages')
    admin = db.relationship('Usuario', backref='vehicle_usages')
    
    __table_args__ = (
        db.Index('idx_vehicle_usage_data_admin', 'data_uso', 'admin_id'),
    )

class VehicleExpense(db.Model):
    """Despesas de veículos"""
    __tablename__ = 'frota_despesa'
    
    id = db.Column(db.Integer, primary_key=True)
    veiculo_id = db.Column(db.Integer, db.ForeignKey('frota_veiculo.id'), nullable=False)
    obra_id = db.Column(db.Integer, db.ForeignKey('obra.id'))
    data_custo = db.Column(db.Date, nullable=False)
    tipo_custo = db.Column(db.String(30), nullable=False)
    valor = db.Column(db.Numeric(10, 2), nullable=False)
    descricao = db.Column(db.String(200), nullable=False)
    fornecedor = db.Column(db.String(100))
    numero_nota_fiscal = db.Column(db.String(20))
    data_vencimento = db.Column(db.Date)
    status_pagamento = db.Column(db.String(20), default='Pendente')
    forma_pagamento = db.Column(db.String(30))
    km_veiculo = db.Column(db.Integer)
    observacoes = db.Column(db.Text)
    admin_id = db.Column(db.Integer, db.ForeignKey('usuario.id'), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    # Relationships
    obra = db.relationship('Obra', backref='vehicle_expenses')
    admin = db.relationship('Usuario', backref='vehicle_expenses')
    
    __table_args__ = (
        db.Index('idx_vehicle_expense_data_admin', 'data_custo', 'admin_id'),
    )

# ================================
# ALMOXARIFADO V3.0 - GESTÃO DE MATERIAIS, FERRAMENTAS E EPIs
# ================================

class AlmoxarifadoCategoria(db.Model):
    """Categorias de materiais do almoxarifado"""
    __tablename__ = 'almoxarifado_categoria'
    
    id = db.Column(db.Integer, primary_key=True)
    nome = db.Column(db.String(100), nullable=False)
    tipo_controle_padrao = db.Column(db.String(20), nullable=False)  # SERIALIZADO ou CONSUMIVEL
    permite_devolucao_padrao = db.Column(db.Boolean, default=True)
    admin_id = db.Column(db.Integer, db.ForeignKey('usuario.id'), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    admin = db.relationship('Usuario', backref='almoxarifado_categorias')
    
    __table_args__ = (
        db.Index('idx_almox_categoria_admin', 'admin_id'),
    )

class AlmoxarifadoItem(db.Model):
    """Catálogo de itens do almoxarifado"""
    __tablename__ = 'almoxarifado_item'
    
    id = db.Column(db.Integer, primary_key=True)
    codigo = db.Column(db.String(50), nullable=False)
    nome = db.Column(db.String(200), nullable=False)
    categoria_id = db.Column(db.Integer, db.ForeignKey('almoxarifado_categoria.id'), nullable=False)
    tipo_controle = db.Column(db.String(20), nullable=False)  # SERIALIZADO ou CONSUMIVEL
    permite_devolucao = db.Column(db.Boolean, default=True)
    estoque_minimo = db.Column(db.Integer, default=0)
    unidade = db.Column(db.String(20))  # un, kg, m, litros, etc
    admin_id = db.Column(db.Integer, db.ForeignKey('usuario.id'), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    categoria = db.relationship('AlmoxarifadoCategoria', backref='itens')
    admin = db.relationship('Usuario', backref='almoxarifado_itens')
    
    __table_args__ = (
        db.Index('idx_almox_item_codigo_admin', 'codigo', 'admin_id'),
        db.Index('idx_almox_item_categoria', 'categoria_id'),
        db.Index('idx_almox_item_nome', 'nome'),
    )

class AlmoxarifadoEstoque(db.Model):
    """Controle de estoque (serializado e consumível) com rastreamento de lotes FIFO"""
    __tablename__ = 'almoxarifado_estoque'
    
    id = db.Column(db.Integer, primary_key=True)
    item_id = db.Column(db.Integer, db.ForeignKey('almoxarifado_item.id'), nullable=False)
    numero_serie = db.Column(db.String(100))  # Para SERIALIZADO
    quantidade = db.Column(db.Numeric(10, 2), default=0)  # Para CONSUMIVEL (quantidade atual)
    
    # NOVOS CAMPOS PARA RASTREAMENTO DE LOTES FIFO
    quantidade_inicial = db.Column(db.Numeric(10, 2))  # Quantidade original da entrada deste lote
    quantidade_disponivel = db.Column(db.Numeric(10, 2))  # Quantidade ainda disponível para saída
    entrada_movimento_id = db.Column(db.Integer, db.ForeignKey('almoxarifado_movimento.id'))  # Vincula ao movimento de entrada
    
    status = db.Column(db.String(20), default='DISPONIVEL')  # DISPONIVEL, EM_USO, MANUTENCAO, DESCARTADO, CONSUMIDO
    funcionario_atual_id = db.Column(db.Integer, db.ForeignKey('funcionario.id'))
    obra_id = db.Column(db.Integer, db.ForeignKey('obra.id'))
    valor_unitario = db.Column(db.Numeric(10, 2))
    lote = db.Column(db.String(50))
    data_validade = db.Column(db.Date)
    admin_id = db.Column(db.Integer, db.ForeignKey('usuario.id'), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    item = db.relationship('AlmoxarifadoItem', backref='estoque')
    funcionario_atual = db.relationship('Funcionario', backref='itens_almoxarifado_posse')
    obra = db.relationship('Obra', backref='itens_almoxarifado_obra')
    admin = db.relationship('Usuario', backref='almoxarifado_estoque')
    entrada_movimento = db.relationship('AlmoxarifadoMovimento', foreign_keys=[entrada_movimento_id], backref='lotes_criados')
    
    __table_args__ = (
        db.Index('idx_almox_estoque_item_status', 'item_id', 'status'),
        db.Index('idx_almox_estoque_funcionario', 'funcionario_atual_id'),
        db.Index('idx_almox_estoque_admin', 'admin_id'),
        db.Index('idx_almox_estoque_numero_serie', 'numero_serie'),
        db.Index('idx_almox_estoque_entrada_mov', 'entrada_movimento_id'),
        db.Index('idx_almox_estoque_fifo', 'item_id', 'status', 'created_at'),  # Índice composto para queries FIFO
    )

class AlmoxarifadoMovimento(db.Model):
    """Histórico de movimentações (ENTRADA, SAIDA, DEVOLUCAO)"""
    __tablename__ = 'almoxarifado_movimento'
    
    id = db.Column(db.Integer, primary_key=True)
    tipo_movimento = db.Column(db.String(20), nullable=False)  # ENTRADA, SAIDA, DEVOLUCAO
    item_id = db.Column(db.Integer, db.ForeignKey('almoxarifado_item.id'), nullable=False)
    estoque_id = db.Column(db.Integer, db.ForeignKey('almoxarifado_estoque.id'))
    funcionario_id = db.Column(db.Integer, db.ForeignKey('funcionario.id'))
    obra_id = db.Column(db.Integer, db.ForeignKey('obra.id'), nullable=True)  # NULL permitido para ENTRADAs
    fornecedor_id = db.Column(db.Integer, db.ForeignKey('fornecedor.id'))  # Integração com Financeiro
    quantidade = db.Column(db.Numeric(10, 2))
    valor_unitario = db.Column(db.Numeric(10, 2))
    nota_fiscal = db.Column(db.String(50))
    lote = db.Column(db.String(50))
    numero_serie = db.Column(db.String(100))  # Para movimentos de serializados
    condicao_item = db.Column(db.String(20))  # Para devoluções: BOM, DANIFICADO, PERDIDO
    observacao = db.Column(db.Text)
    data_movimento = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    usuario_id = db.Column(db.Integer, db.ForeignKey('usuario.id'), nullable=False)
    admin_id = db.Column(db.Integer, db.ForeignKey('usuario.id'), nullable=False)
    origem_manual = db.Column(db.Boolean, default=False)
    impacta_estoque = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    # Relationships
    item = db.relationship('AlmoxarifadoItem', backref='movimentos')
    estoque = db.relationship('AlmoxarifadoEstoque', backref='movimentos')
    funcionario = db.relationship('Funcionario', backref='movimentos_almoxarifado')
    obra = db.relationship('Obra', backref='movimentos_almoxarifado')
    fornecedor = db.relationship('Fornecedor', backref='movimentos_almoxarifado')
    usuario = db.relationship('Usuario', foreign_keys=[usuario_id], backref='movimentos_almoxarifado_criados')
    admin = db.relationship('Usuario', foreign_keys=[admin_id], backref='movimentos_almoxarifado_admin')
    
    __table_args__ = (
        db.Index('idx_almox_movimento_data', 'data_movimento'),
        db.Index('idx_almox_movimento_tipo', 'tipo_movimento'),
        db.Index('idx_almox_movimento_funcionario', 'funcionario_id'),
        db.Index('idx_almox_movimento_obra', 'obra_id'),
        db.Index('idx_almox_movimento_fornecedor', 'fornecedor_id'),
        db.Index('idx_almox_movimento_admin', 'admin_id'),
    )

# ================================
# RASTREAMENTO DE MIGRAÇÕES
# ================================
class MigrationHistory(db.Model):
    """Rastreamento de migrações executadas para garantir idempotência"""
    __tablename__ = 'migration_history'
    
    id = db.Column(db.Integer, primary_key=True)
    migration_number = db.Column(db.Integer, unique=True, nullable=False)
    migration_name = db.Column(db.String(200), nullable=False)
    executed_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    execution_time_ms = db.Column(db.Integer)
    status = db.Column(db.String(20), default='success')  # success, failed, skipped
    error_message = db.Column(db.Text)
    
    __table_args__ = (
        db.Index('idx_migration_number', 'migration_number'),
        db.Index('idx_migration_executed', 'executed_at'),
    )
    
    def __repr__(self):
        return f'<Migration #{self.migration_number}: {self.migration_name}>'

# ================================
# ALIASES PARA COMPATIBILIDADE
# ================================
# Manter compatibilidade com código legado que importa Frota*
FrotaVeiculo = Vehicle
FrotaUtilizacao = VehicleUsage
FrotaDespesa = VehicleExpense

