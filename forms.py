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
    restaurante_id = SelectField('Restaurante', coerce=int, validators=[Optional()])
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


# Formulários para RDO
class RDOForm(FlaskForm):
    # Informações gerais
    data_relatorio = DateField('Data do Relatório', validators=[DataRequired()], default=date.today)
    obra_id = SelectField('Obra', coerce=int, validators=[DataRequired()])
    
    # Condições climáticas
    tempo_manha = SelectField('Tempo da Manhã', choices=[
        ('', 'Selecione...'),
        ('Ensolarado', 'Ensolarado'),
        ('Nublado', 'Nublado'),
        ('Chuvoso', 'Chuvoso'),
        ('Parcialmente Nublado', 'Parcialmente Nublado'),
        ('Garoa', 'Garoa'),
        ('Tempestade', 'Tempestade')
    ])
    tempo_tarde = SelectField('Tempo da Tarde', choices=[
        ('', 'Selecione...'),
        ('Ensolarado', 'Ensolarado'),
        ('Nublado', 'Nublado'),
        ('Chuvoso', 'Chuvoso'),
        ('Parcialmente Nublado', 'Parcialmente Nublado'),
        ('Garoa', 'Garoa'),
        ('Tempestade', 'Tempestade')
    ])
    tempo_noite = SelectField('Tempo da Noite', choices=[
        ('', 'Selecione...'),
        ('Ensolarado', 'Ensolarado'),
        ('Nublado', 'Nublado'),
        ('Chuvoso', 'Chuvoso'),
        ('Parcialmente Nublado', 'Parcialmente Nublado'),
        ('Garoa', 'Garoa'),
        ('Tempestade', 'Tempestade')
    ])
    observacoes_meteorologicas = TextAreaField('Observações Meteorológicas')
    
    # Comentários
    comentario_geral = TextAreaField('Comentário Geral')
    
    # Status
    status = SelectField('Status', choices=[
        ('Rascunho', 'Rascunho'),
        ('Finalizado', 'Finalizado')
    ], default='Rascunho')


# Formulário para busca/filtro de RDOs
class RDOFiltroForm(FlaskForm):
    data_inicio = DateField('Data de Início', validators=[Optional()])
    data_fim = DateField('Data de Fim', validators=[Optional()])
    obra_id = SelectField('Obra', coerce=int, validators=[Optional()])
    status = SelectField('Status', choices=[
        ('', 'Todos'),
        ('Rascunho', 'Rascunho'),
        ('Finalizado', 'Finalizado')
    ], validators=[Optional()])


# Novos formulários para funcionalidades aprimoradas
class RestauranteForm(FlaskForm):
    """Formulário para cadastro de restaurantes"""
    nome = StringField('Nome', validators=[DataRequired(), Length(max=100)])
    endereco = TextAreaField('Endereço')
    telefone = StringField('Telefone', validators=[Optional(), Length(max=20)])
    email = StringField('Email', validators=[Optional(), Email(), Length(max=120)])
    contato_responsavel = StringField('Contato Responsável', validators=[Optional(), Length(max=100)])
    ativo = BooleanField('Ativo', default=True)


class AlimentacaoMultiplaForm(FlaskForm):
    """Formulário para lançamento de alimentação para múltiplos funcionários"""
    data = DateField('Data', validators=[DataRequired()], default=date.today)
    tipo = SelectField('Tipo', choices=[
        ('marmita', 'Marmita'),
        ('refeicao_local', 'Refeição no Local'),
        ('cafe', 'Café da Manhã'),
        ('jantar', 'Jantar'),
        ('lanche', 'Lanche'),
        ('outros', 'Outros')
    ], validators=[DataRequired()])
    valor = FloatField('Valor', validators=[DataRequired(), NumberRange(min=0)])
    obra_id = SelectField('Obra (Opcional)', coerce=int, validators=[Optional()])
    restaurante_id = SelectField('Restaurante (Opcional)', coerce=int, validators=[Optional()])
    funcionarios_selecionados = StringField('Funcionários Selecionados')  # JSON string
    observacoes = TextAreaField('Observações')


class UsoVeiculoForm(FlaskForm):
    """Formulário para registro de uso de veículo"""
    veiculo_id = SelectField('Veículo', coerce=int, validators=[DataRequired()])
    funcionario_id = SelectField('Funcionário', coerce=int, validators=[DataRequired()])
    obra_id = SelectField('Obra', coerce=int, validators=[DataRequired()])
    data_uso = DateField('Data de Uso', validators=[DataRequired()], default=date.today)
    km_inicial = IntegerField('KM Inicial', validators=[Optional(), NumberRange(min=0)])
    km_final = IntegerField('KM Final', validators=[Optional(), NumberRange(min=0)])
    horario_saida = TimeField('Horário de Saída', validators=[Optional()])
    horario_chegada = TimeField('Horário de Chegada', validators=[Optional()])
    finalidade = StringField('Finalidade', validators=[Optional(), Length(max=200)])
    observacoes = TextAreaField('Observações')


class CustoVeiculoForm(FlaskForm):
    """Formulário para registro de custo de veículo"""
    veiculo_id = SelectField('Veículo', coerce=int, validators=[DataRequired()])
    obra_id = SelectField('Obra', coerce=int, validators=[DataRequired()])
    data_custo = DateField('Data do Custo', validators=[DataRequired()], default=date.today)
    valor = FloatField('Valor', validators=[DataRequired(), NumberRange(min=0)])
    tipo_custo = SelectField('Tipo de Custo', choices=[
        ('combustivel', 'Combustível'),
        ('manutencao', 'Manutenção'),
        ('seguro', 'Seguro'),
        ('multa', 'Multa'),
        ('lavagem', 'Lavagem'),
        ('outros', 'Outros')
    ], validators=[DataRequired()])
    descricao = TextAreaField('Descrição')
    km_atual = IntegerField('KM Atual', validators=[Optional(), NumberRange(min=0)])
    fornecedor = StringField('Fornecedor', validators=[Optional(), Length(max=100)])


class FiltroDataForm(FlaskForm):
    """Formulário para filtros de data"""
    data_inicio = DateField('Data de Início', validators=[Optional()])
    data_fim = DateField('Data de Fim', validators=[Optional()])
