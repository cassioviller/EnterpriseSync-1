from flask_wtf import FlaskForm
from wtforms import StringField, TextAreaField, FloatField, DateField, SelectField, BooleanField, TimeField, IntegerField
from wtforms.validators import DataRequired, Email, Length, NumberRange, Optional
from datetime import date

class DepartamentoForm(FlaskForm):
    nome = StringField('Nome', validators=[DataRequired(), Length(max=100)])
    descricao = TextAreaField('Descrição')

class FuncaoForm(FlaskForm):
    nome = StringField('Nome', validators=[DataRequired(), Length(max=100)])
    descricao = TextAreaField('Descrição')
    salario_base = FloatField('Salário Base', validators=[Optional(), NumberRange(min=0)])

class FuncionarioForm(FlaskForm):
    nome = StringField('Nome', validators=[DataRequired(), Length(max=100)])
    cpf = StringField('CPF', validators=[DataRequired(), Length(max=14)])
    rg = StringField('RG', validators=[Optional(), Length(max=20)])
    data_nascimento = DateField('Data de Nascimento', validators=[Optional()])
    endereco = TextAreaField('Endereço')
    telefone = StringField('Telefone', validators=[Optional(), Length(max=20)])
    email = StringField('Email', validators=[Optional(), Email(), Length(max=120)])
    data_admissao = DateField('Data de Admissão', validators=[DataRequired()], default=date.today)
    salario = FloatField('Salário', validators=[Optional(), NumberRange(min=0)])
    departamento_id = SelectField('Departamento', coerce=int, validators=[Optional()])
    funcao_id = SelectField('Função', coerce=int, validators=[Optional()])
    horario_trabalho_id = SelectField('Horário de Trabalho', coerce=int, validators=[Optional()])
    ativo = BooleanField('Ativo', default=True)

class ObraForm(FlaskForm):
    nome = StringField('Nome', validators=[DataRequired(), Length(max=100)])
    endereco = TextAreaField('Endereço')
    data_inicio = DateField('Data de Início', validators=[DataRequired()], default=date.today)
    data_previsao_fim = DateField('Data de Previsão de Fim', validators=[Optional()])
    orcamento = FloatField('Orçamento', validators=[Optional(), NumberRange(min=0)])
    status = SelectField('Status', choices=[
        ('Em andamento', 'Em andamento'),
        ('Concluída', 'Concluída'),
        ('Pausada', 'Pausada'),
        ('Cancelada', 'Cancelada')
    ], default='Em andamento')
    responsavel_id = SelectField('Responsável', coerce=int, validators=[Optional()])

class VeiculoForm(FlaskForm):
    placa = StringField('Placa', validators=[DataRequired(), Length(max=10)])
    marca = StringField('Marca', validators=[DataRequired(), Length(max=50)])
    modelo = StringField('Modelo', validators=[DataRequired(), Length(max=50)])
    ano = IntegerField('Ano', validators=[Optional(), NumberRange(min=1900, max=2030)])
    tipo = SelectField('Tipo', choices=[
        ('Carro', 'Carro'),
        ('Caminhão', 'Caminhão'),
        ('Moto', 'Moto'),
        ('Van', 'Van'),
        ('Outro', 'Outro')
    ], validators=[DataRequired()])
    status = SelectField('Status', choices=[
        ('Disponível', 'Disponível'),
        ('Em uso', 'Em uso'),
        ('Manutenção', 'Manutenção'),
        ('Indisponível', 'Indisponível')
    ], default='Disponível')
    km_atual = IntegerField('KM Atual', validators=[Optional(), NumberRange(min=0)])
    data_ultima_manutencao = DateField('Data da Última Manutenção', validators=[Optional()])
    data_proxima_manutencao = DateField('Data da Próxima Manutenção', validators=[Optional()])



class ServicoForm(FlaskForm):
    nome = StringField('Nome', validators=[DataRequired(), Length(max=100)])
    descricao = TextAreaField('Descrição')
    preco_unitario = FloatField('Preço Unitário', validators=[Optional(), NumberRange(min=0)])

class RegistroPontoForm(FlaskForm):
    funcionario_id = SelectField('Funcionário', coerce=int, validators=[DataRequired()])
    obra_id = SelectField('Obra', coerce=int, validators=[Optional()])
    data = DateField('Data', validators=[DataRequired()], default=date.today)
    hora_entrada = TimeField('Hora de Entrada', validators=[Optional()])
    hora_saida = TimeField('Hora de Saída', validators=[Optional()])
    hora_almoco_saida = TimeField('Hora Saída Almoço', validators=[Optional()])
    hora_almoco_retorno = TimeField('Hora Retorno Almoço', validators=[Optional()])
    observacoes = TextAreaField('Observações')

class AlimentacaoForm(FlaskForm):
    funcionario_id = SelectField('Funcionário', coerce=int, validators=[DataRequired()])
    obra_id = SelectField('Obra', coerce=int, validators=[Optional()])
    data = DateField('Data', validators=[DataRequired()], default=date.today)
    tipo = SelectField('Tipo', choices=[
        ('cafe', 'Café da Manhã'),
        ('almoco', 'Almoço'),
        ('jantar', 'Jantar'),
        ('lanche', 'Lanche')
    ], validators=[DataRequired()])
    valor = FloatField('Valor', validators=[DataRequired(), NumberRange(min=0)])
    observacoes = TextAreaField('Observações')

class HorarioTrabalhoForm(FlaskForm):
    nome = StringField('Nome do Horário', validators=[DataRequired(), Length(max=100)])
    entrada = TimeField('Hora de Entrada', validators=[DataRequired()])
    saida_almoco = TimeField('Saída para Almoço', validators=[DataRequired()])
    retorno_almoco = TimeField('Retorno do Almoço', validators=[DataRequired()])
    saida = TimeField('Hora de Saída', validators=[DataRequired()])
    dias_semana = SelectField('Dias da Semana', choices=[
        ('1,2,3,4,5', 'Segunda a Sexta'),
        ('1,2,3,4,5,6', 'Segunda a Sábado'),
        ('1,2,3,4,6', 'Segunda a Quinta e Sábado'),
        ('2,4,6', 'Terça, Quinta e Sábado'),
        ('1,3,5', 'Segunda, Quarta e Sexta'),
        ('7', 'Domingo'),
        ('6,7', 'Sábado e Domingo')
    ], validators=[DataRequired()])
