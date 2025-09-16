from flask_wtf import FlaskForm
from flask_wtf.file import FileField, FileAllowed
from wtforms import StringField, TextAreaField, FloatField, DateField, SelectField, BooleanField, TimeField, IntegerField, HiddenField
from wtforms.validators import DataRequired, Email, Length, NumberRange, Optional, ValidationError
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
    foto = FileField('Foto', validators=[Optional(), FileAllowed(['jpg', 'jpeg', 'png'], 'Apenas arquivos JPG, JPEG e PNG são permitidos!')])
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
    categoria = SelectField('Categoria', choices=[
        ('estrutura', 'Estrutura'),
        ('alvenaria', 'Alvenaria'),
        ('revestimento', 'Revestimento'),
        ('acabamento', 'Acabamento'),
        ('instalacoes', 'Instalações'),
        ('outros', 'Outros')
    ], validators=[DataRequired()])
    unidade_medida = SelectField('Unidade de Medida', choices=[
        ('m2', 'Metro Quadrado (m²)'),
        ('m3', 'Metro Cúbico (m³)'),
        ('m', 'Metro Linear (m)'),
        ('kg', 'Quilograma (kg)'),
        ('ton', 'Tonelada (ton)'),
        ('un', 'Unidade (un)'),
        ('h', 'Hora (h)')
    ], validators=[DataRequired()])
    unidade_simbolo = StringField('Símbolo da Unidade', validators=[Optional(), Length(max=10)])
    custo_unitario = FloatField('Custo Unitário', validators=[Optional(), NumberRange(min=0)])
    complexidade = SelectField('Complexidade', choices=[
        (1, 'Muito Baixa'),
        (2, 'Baixa'),
        (3, 'Média'),
        (4, 'Alta'),
        (5, 'Muito Alta')
    ], coerce=int, default=3)
    requer_especializacao = BooleanField('Requer Especialização', default=False)
    ativo = BooleanField('Ativo', default=True)

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
    """Formulário aprimorado para registro de uso de veículo"""
    veiculo_id = SelectField('Veículo', coerce=int, validators=[DataRequired()])
    funcionario_id = SelectField('Funcionário', coerce=int, validators=[DataRequired()])
    obra_id = SelectField('Obra (Opcional)', coerce=int, validators=[Optional()])
    data_uso = DateField('Data de Uso', validators=[DataRequired()], default=date.today)
    km_inicial = IntegerField('KM Inicial', validators=[Optional(), NumberRange(min=0)])
    km_final = IntegerField('KM Final', validators=[Optional(), NumberRange(min=0)])
    horario_saida = TimeField('Horário de Saída', validators=[Optional()])
    horario_chegada = TimeField('Horário de Chegada', validators=[Optional()])
    finalidade = StringField('Finalidade', validators=[Optional(), Length(max=200)])
    observacoes = TextAreaField('Observações')
    
    # Novos campos
    local_destino = StringField('Local de Destino', validators=[Optional(), Length(max=200)])
    tipo_uso = SelectField('Tipo de Uso', choices=[
        ('trabalho', 'Trabalho'),
        ('emergencia', 'Emergência'),
        ('manutencao', 'Manutenção'),
        ('transporte_materiais', 'Transporte de Materiais'),
        ('reuniao_cliente', 'Reunião Cliente'),
        ('outros', 'Outros')
    ], default='trabalho', validators=[DataRequired()])
    status_uso = SelectField('Status', choices=[
        ('ativo', 'Em Uso'),
        ('finalizado', 'Finalizado'),
        ('cancelado', 'Cancelado')
    ], default='ativo', validators=[DataRequired()])
    
    # Validações customizadas
    def validate_km_inicial(form, field):
        if field.data and hasattr(form, 'veiculo_id') and form.veiculo_id.data:
            try:
                from models import Veiculo
                veiculo = Veiculo.query.get(form.veiculo_id.data)
                if veiculo and veiculo.km_atual and field.data < veiculo.km_atual:
                    raise ValidationError(f'KM inicial ({field.data}) não pode ser menor que KM atual do veículo ({veiculo.km_atual}).')
            except Exception:
                # Se não conseguir validar, apenas prosseguir
                pass
    
    def validate_km_final(form, field):
        if field.data and form.km_inicial.data:
            if field.data <= form.km_inicial.data:
                raise ValidationError('KM final deve ser maior que KM inicial.')
            
            # Validar diferença razoável de KM (máximo 2000km por dia)
            if (field.data - form.km_inicial.data) > 2000:
                raise ValidationError('Diferença de KM muito alta para um dia (máximo 2000km).')
    
    def validate_horario_chegada(form, field):
        if field.data and form.horario_saida.data:
            from datetime import datetime, date, timedelta
            
            # Converter horários para datetime para comparação
            inicio = datetime.combine(date.today(), form.horario_saida.data)
            fim = datetime.combine(date.today(), field.data)
            
            # Se chegada é anterior à saída, assumir que é no dia seguinte
            if fim < inicio:
                fim += timedelta(days=1)
            
            # Validar duração máxima (24 horas)
            delta = fim - inicio
            if delta.total_seconds() > 86400:  # 24 horas em segundos
                raise ValidationError('Uso do veículo não pode exceder 24 horas.')
            
            # Validar duração mínima (15 minutos)
            if delta.total_seconds() < 900:  # 15 minutos em segundos
                raise ValidationError('Duração mínima de uso é 15 minutos.')


class CustoVeiculoForm(FlaskForm):
    """Formulário aprimorado para registro de custo de veículo"""
    veiculo_id = HiddenField('Veículo')
    obra_id = SelectField('Obra (Opcional)', coerce=int, validators=[Optional()])
    data_custo = DateField('Data do Custo', validators=[DataRequired()], default=date.today)
    valor = FloatField('Valor Total (R$)', validators=[DataRequired(), NumberRange(min=0)])
    tipo_custo = SelectField('Tipo de Custo', choices=[
        ('combustivel', 'Combustível'),
        ('manutencao', 'Manutenção'),
        ('seguro', 'Seguro'),
        ('multa', 'Multa'),
        ('lavagem', 'Lavagem'),
        ('ipva', 'IPVA'),
        ('licenciamento', 'Licenciamento'),
        ('pneus', 'Pneus'),
        ('outros', 'Outros')
    ], validators=[DataRequired()])
    descricao = TextAreaField('Descrição')
    km_atual = IntegerField('KM Atual', validators=[Optional(), NumberRange(min=0)])
    fornecedor = StringField('Fornecedor/Posto', validators=[Optional(), Length(max=100)])
    
    # Campos específicos para combustível
    litros_combustivel = FloatField('Litros Abastecidos', validators=[Optional(), NumberRange(min=0)])
    preco_por_litro = FloatField('Preço por Litro (R$)', validators=[Optional(), NumberRange(min=0)])
    posto_combustivel = StringField('Nome do Posto', validators=[Optional(), Length(max=100)])
    tipo_combustivel = SelectField('Tipo de Combustível', choices=[
        ('', 'Selecione...'),
        ('gasolina', 'Gasolina'),
        ('etanol', 'Etanol'),
        ('diesel', 'Diesel'),
        ('gnv', 'GNV')
    ], validators=[Optional()])
    tanque_cheio = BooleanField('Tanque Cheio?', default=False)
    
    # Campos para manutenção
    numero_nota_fiscal = StringField('Número da NF', validators=[Optional(), Length(max=50)])
    categoria_manutencao = SelectField('Categoria da Manutenção', choices=[
        ('', 'Selecione...'),
        ('preventiva', 'Preventiva'),
        ('corretiva', 'Corretiva'),
        ('emergencial', 'Emergencial'),
        ('revisao', 'Revisão')
    ], validators=[Optional()])
    proxima_manutencao_km = IntegerField('Próxima Manutenção (KM)', validators=[Optional(), NumberRange(min=0)])
    proxima_manutencao_data = DateField('Próxima Manutenção (Data)', validators=[Optional()])
    
    # Controle financeiro
    centro_custo = StringField('Centro de Custo', validators=[Optional(), Length(max=50)])
    
    # Validações customizadas
    def validate_litros_combustivel(form, field):
        if form.tipo_custo.data == 'combustivel':
            if not field.data or field.data <= 0:
                raise ValidationError('Litros de combustível é obrigatório para tipo combustível.')
    
    def validate_preco_por_litro(form, field):
        if form.tipo_custo.data == 'combustivel' and form.litros_combustivel.data:
            if not field.data or field.data <= 0:
                raise ValidationError('Preço por litro é obrigatório para abastecimentos.')
            # Validar se o total confere
            if form.valor.data and abs(form.valor.data - (field.data * form.litros_combustivel.data)) > 0.02:
                raise ValidationError('Valor total não confere com litros × preço por litro.')
    
    def validate_categoria_manutencao(form, field):
        if form.tipo_custo.data == 'manutencao' and not field.data:
            raise ValidationError('Categoria da manutenção é obrigatória para tipo manutenção.')


class FiltroDataForm(FlaskForm):
    """Formulário para filtros de data"""
    data_inicio = DateField('Data de Início', validators=[Optional()])
    data_fim = DateField('Data de Fim', validators=[Optional()])

# Formulários para Gestão Financeira Avançada

class CentroCustoForm(FlaskForm):
    """Formulário para cadastro de centros de custo"""
    codigo = StringField('Código', validators=[DataRequired(), Length(max=20)])
    nome = StringField('Nome', validators=[DataRequired(), Length(max=100)])
    descricao = TextAreaField('Descrição')
    tipo = SelectField('Tipo', choices=[
        ('obra', 'Obra'),
        ('departamento', 'Departamento'),
        ('projeto', 'Projeto'),
        ('atividade', 'Atividade')
    ], validators=[DataRequired()])
    obra_id = SelectField('Obra (Opcional)', coerce=int, validators=[Optional()])
    departamento_id = SelectField('Departamento (Opcional)', coerce=int, validators=[Optional()])
    ativo = BooleanField('Ativo', default=True)

class ReceitaForm(FlaskForm):
    """Formulário para registro de receitas"""
    numero_receita = StringField('Número da Receita', validators=[DataRequired(), Length(max=20)])
    obra_id = SelectField('Obra (Opcional)', coerce=int, validators=[Optional()])
    centro_custo_id = SelectField('Centro de Custo (Opcional)', coerce=int, validators=[Optional()])
    origem = SelectField('Origem', choices=[
        ('obra', 'Obra'),
        ('servico', 'Serviço'),
        ('venda', 'Venda'),
        ('consultoria', 'Consultoria'),
        ('outros', 'Outros')
    ], validators=[DataRequired()])
    descricao = StringField('Descrição', validators=[DataRequired(), Length(max=200)])
    valor = FloatField('Valor', validators=[DataRequired(), NumberRange(min=0)])
    data_receita = DateField('Data da Receita', validators=[DataRequired()], default=date.today)
    data_recebimento = DateField('Data do Recebimento', validators=[Optional()])
    status = SelectField('Status', choices=[
        ('Pendente', 'Pendente'),
        ('Recebido', 'Recebido'),
        ('Cancelado', 'Cancelado')
    ], default='Pendente')
    forma_recebimento = SelectField('Forma de Recebimento', choices=[
        ('', 'Selecione...'),
        ('Dinheiro', 'Dinheiro'),
        ('Transferência', 'Transferência Bancária'),
        ('Cartão', 'Cartão'),
        ('Cheque', 'Cheque'),
        ('PIX', 'PIX'),
        ('Outros', 'Outros')
    ], validators=[Optional()])
    observacoes = TextAreaField('Observações')

class OrcamentoObraForm(FlaskForm):
    """Formulário para orçamento de obras"""
    obra_id = SelectField('Obra', coerce=int, validators=[DataRequired()])
    categoria = SelectField('Categoria', choices=[
        ('mao_obra', 'Mão de Obra'),
        ('material', 'Material'),
        ('equipamento', 'Equipamento'),
        ('servicos_terceiros', 'Serviços de Terceiros'),
        ('alimentacao', 'Alimentação'),
        ('transporte', 'Transporte'),
        ('outros', 'Outros')
    ], validators=[DataRequired()])
    orcamento_planejado = FloatField('Orçamento Planejado', validators=[DataRequired(), NumberRange(min=0)])
    receita_planejada = FloatField('Receita Planejada', validators=[Optional(), NumberRange(min=0)])
    observacoes = TextAreaField('Observações')

class FluxoCaixaFiltroForm(FlaskForm):
    """Formulário para filtros do fluxo de caixa"""
    data_inicio = DateField('Data de Início', validators=[Optional()])
    data_fim = DateField('Data de Fim', validators=[Optional()])
    tipo_movimento = SelectField('Tipo de Movimento', choices=[
        ('', 'Todos'),
        ('ENTRADA', 'Entrada'),
        ('SAIDA', 'Saída')
    ], validators=[Optional()])
    categoria = SelectField('Categoria', choices=[
        ('', 'Todas'),
        ('receita', 'Receita'),
        ('custo_obra', 'Custo de Obra'),
        ('custo_veiculo', 'Custo de Veículo'),
        ('alimentacao', 'Alimentação'),
        ('salario', 'Salário'),
        ('outros', 'Outros')
    ], validators=[Optional()])
    obra_id = SelectField('Obra', coerce=int, validators=[Optional()])
    centro_custo_id = SelectField('Centro de Custo', coerce=int, validators=[Optional()])
    
    def validate_data_fim(form, field):
        if field.data and form.data_inicio.data:
            if field.data < form.data_inicio.data:
                raise ValidationError('Data de fim deve ser posterior à data de início.')

# =============================================
# FORMULÁRIOS AVANÇADOS PARA GESTÃO DE VEÍCULOS
# =============================================

class ManutencaoVeiculoForm(FlaskForm):
    """Formulário especializado para registro de manutenções"""
    veiculo_id = HiddenField('Veículo')
    custo_veiculo_id = HiddenField('Custo Veículo ID')
    
    # Classificação da manutenção
    tipo_manutencao = SelectField('Tipo de Manutenção', choices=[
        ('preventiva', 'Preventiva'),
        ('corretiva', 'Corretiva'),
        ('emergencial', 'Emergencial'),
        ('recall', 'Recall/Campanha')
    ], validators=[DataRequired()])
    
    categoria = SelectField('Categoria', choices=[
        ('motor', 'Motor'),
        ('oleo', 'Óleo e Filtros'),
        ('freios', 'Sistema de Freios'),
        ('pneus', 'Pneus'),
        ('eletrica', 'Sistema Elétrico'),
        ('suspensao', 'Suspensão'),
        ('carroceria', 'Carroceria'),
        ('ar_condicionado', 'Ar Condicionado'),
        ('revisao_geral', 'Revisão Geral'),
        ('outros', 'Outros')
    ], validators=[DataRequired()])
    
    prioridade = SelectField('Prioridade', choices=[
        ('baixa', 'Baixa'),
        ('media', 'Média'),
        ('alta', 'Alta'),
        ('urgente', 'Urgente')
    ], default='media', validators=[DataRequired()])
    
    # Dados da execução
    data_manutencao = DateField('Data da Manutenção', validators=[DataRequired()], default=date.today)
    km_manutencao = IntegerField('KM na Manutenção', validators=[Optional(), NumberRange(min=0)])
    descricao = TextAreaField('Descrição dos Serviços', validators=[DataRequired()], 
                             render_kw={"rows": 4, "placeholder": "Descreva detalhadamente os serviços executados..."})
    
    pecas_utilizadas = TextAreaField('Peças Utilizadas', 
                                   render_kw={"rows": 3, "placeholder": "Liste as peças substituídas (uma por linha)"})
    servicos_executados = TextAreaField('Serviços Executados', 
                                      render_kw={"rows": 3, "placeholder": "Liste os serviços realizados (um por linha)"})
    
    # Dados financeiros
    valor_pecas = FloatField('Valor das Peças (R$)', validators=[Optional(), NumberRange(min=0)], default=0.0)
    valor_mao_obra = FloatField('Valor da Mão de Obra (R$)', validators=[Optional(), NumberRange(min=0)], default=0.0)
    valor_total = FloatField('Valor Total (R$)', validators=[DataRequired(), NumberRange(min=0)])
    
    # Fornecedor/Oficina
    oficina = StringField('Oficina/Fornecedor', validators=[Optional(), Length(max=200)])
    mecanico_responsavel = StringField('Mecânico Responsável', validators=[Optional(), Length(max=100)])
    numero_os = StringField('Número da OS', validators=[Optional(), Length(max=50)])
    
    # Garantia
    garantia_meses = IntegerField('Garantia (Meses)', validators=[Optional(), NumberRange(min=0, max=60)], default=3)
    garantia_km = IntegerField('Garantia (KM)', validators=[Optional(), NumberRange(min=0)], default=10000)
    
    # Planejamento próxima manutenção
    proxima_manutencao_km = IntegerField('Próxima Manutenção (KM)', validators=[Optional(), NumberRange(min=0)])
    proxima_manutencao_data = DateField('Próxima Manutenção (Data)', validators=[Optional()])
    intervalo_km = IntegerField('Intervalo Padrão (KM)', validators=[Optional(), NumberRange(min=0)])
    intervalo_meses = IntegerField('Intervalo Padrão (Meses)', validators=[Optional(), NumberRange(min=0)])
    
    # Status e observações
    status = SelectField('Status', choices=[
        ('agendada', 'Agendada'),
        ('em_andamento', 'Em Andamento'),
        ('concluida', 'Concluída'),
        ('cancelada', 'Cancelada')
    ], default='concluida', validators=[DataRequired()])
    
    observacoes = TextAreaField('Observações Gerais', 
                               render_kw={"rows": 2, "placeholder": "Observações adicionais sobre a manutenção..."})
    
    # Validações customizadas
    def validate_valor_total(form, field):
        if field.data:
            valor_soma = (form.valor_pecas.data or 0) + (form.valor_mao_obra.data or 0)
            if valor_soma > 0 and abs(field.data - valor_soma) > 0.01:
                raise ValidationError('Valor total deve ser igual à soma de peças + mão de obra.')
    
    def validate_proxima_manutencao_km(form, field):
        if field.data and form.km_manutencao.data:
            if field.data <= form.km_manutencao.data:
                raise ValidationError('Próxima manutenção deve ser superior ao KM atual.')
    
    def validate_proxima_manutencao_data(form, field):
        if field.data and form.data_manutencao.data:
            if field.data <= form.data_manutencao.data:
                raise ValidationError('Data da próxima manutenção deve ser posterior à data atual.')

class DocumentoFiscalForm(FlaskForm):
    """Formulário para controle de documentos fiscais"""
    custo_veiculo_id = HiddenField('Custo Veículo ID')
    manutencao_id = HiddenField('Manutenção ID')
    veiculo_id = HiddenField('Veículo ID')
    
    # Dados do documento
    tipo_documento = SelectField('Tipo de Documento', choices=[
        ('nf', 'Nota Fiscal'),
        ('nfce', 'NFC-e'),
        ('nfse', 'NFS-e'),
        ('recibo', 'Recibo'),
        ('cupom', 'Cupom Fiscal'),
        ('outros', 'Outros')
    ], validators=[DataRequired()])
    
    numero_documento = StringField('Número do Documento', validators=[DataRequired(), Length(max=50)])
    serie = StringField('Série', validators=[Optional(), Length(max=10)])
    data_emissao = DateField('Data de Emissão', validators=[DataRequired()])
    valor_documento = FloatField('Valor do Documento (R$)', validators=[DataRequired(), NumberRange(min=0)])
    
    # Dados do emissor
    cnpj_emissor = StringField('CNPJ do Emissor', validators=[Optional(), Length(max=18)])
    nome_emissor = StringField('Nome do Emissor', validators=[DataRequired(), Length(max=200)])
    endereco_emissor = TextAreaField('Endereço do Emissor', 
                                   render_kw={"rows": 2, "placeholder": "Endereço completo do fornecedor"})
    
    # Dados fiscais (opcionais)
    valor_icms = FloatField('ICMS (R$)', validators=[Optional(), NumberRange(min=0)], default=0.0)
    valor_pis = FloatField('PIS (R$)', validators=[Optional(), NumberRange(min=0)], default=0.0)
    valor_cofins = FloatField('COFINS (R$)', validators=[Optional(), NumberRange(min=0)], default=0.0)
    valor_iss = FloatField('ISS (R$)', validators=[Optional(), NumberRange(min=0)], default=0.0)
    valor_desconto = FloatField('Desconto (R$)', validators=[Optional(), NumberRange(min=0)], default=0.0)
    
    # Arquivo digitalizado
    arquivo_digitalizado = FileField('Arquivo Digitalizado', 
                                   validators=[Optional(), FileAllowed(['pdf', 'jpg', 'jpeg', 'png'], 
                                   'Apenas arquivos PDF, JPG, JPEG e PNG são permitidos!')])
    
    # Observações
    observacoes_validacao = TextAreaField('Observações', 
                                        render_kw={"rows": 2, "placeholder": "Observações sobre o documento"})

class AlertaVeiculoForm(FlaskForm):
    """Formulário para criação de alertas personalizados"""
    veiculo_id = SelectField('Veículo', coerce=int, validators=[DataRequired()])
    
    # Tipo de alerta
    tipo_alerta = SelectField('Tipo de Alerta', choices=[
        ('manutencao_vencida', 'Manutenção Vencida'),
        ('documento_vencendo', 'Documento Vencendo'),
        ('gasto_excessivo', 'Gasto Excessivo'),
        ('km_excessivo', 'Quilometragem Excessiva'),
        ('seguro_vencendo', 'Seguro Vencendo'),
        ('licenciamento_vencendo', 'Licenciamento Vencendo'),
        ('personalizado', 'Personalizado')
    ], validators=[DataRequired()])
    
    categoria = SelectField('Categoria', choices=[
        ('urgente', 'Urgente'),
        ('importante', 'Importante'),
        ('informativo', 'Informativo')
    ], default='importante', validators=[DataRequired()])
    
    # Dados do alerta
    titulo = StringField('Título do Alerta', validators=[DataRequired(), Length(max=200)])
    descricao = TextAreaField('Descrição', 
                            render_kw={"rows": 3, "placeholder": "Descreva detalhadamente o alerta..."})
    data_alerta = DateField('Data do Alerta', validators=[DataRequired()], default=date.today)
    data_vencimento = DateField('Data de Vencimento', validators=[Optional()])
    
    # Valores de referência
    valor_limite = FloatField('Valor Limite (R$)', validators=[Optional(), NumberRange(min=0)])
    km_limite = IntegerField('KM Limite', validators=[Optional(), NumberRange(min=0)])
    dias_antecedencia = IntegerField('Dias de Antecedência', validators=[Optional(), NumberRange(min=1, max=365)], default=30)

class FiltroVeiculosForm(FlaskForm):
    """Formulário para filtros avançados de veículos"""
    veiculo_id = SelectField('Veículo Específico', coerce=int, validators=[Optional()])
    tipo_custo = SelectField('Tipo de Custo', choices=[
        ('', 'Todos os tipos'),
        ('combustivel', 'Combustível'),
        ('manutencao', 'Manutenção'),
        ('seguro', 'Seguro'),
        ('multa', 'Multa'),
        ('lavagem', 'Lavagem'),
        ('ipva', 'IPVA'),
        ('licenciamento', 'Licenciamento'),
        ('pneus', 'Pneus'),
        ('outros', 'Outros')
    ], validators=[Optional()])
    
    data_inicio = DateField('Data de Início', validators=[Optional()])
    data_fim = DateField('Data de Fim', validators=[Optional()])
    valor_min = FloatField('Valor Mínimo (R$)', validators=[Optional(), NumberRange(min=0)])
    valor_max = FloatField('Valor Máximo (R$)', validators=[Optional(), NumberRange(min=0)])
    obra_id = SelectField('Obra', coerce=int, validators=[Optional()])
    fornecedor = StringField('Fornecedor', validators=[Optional(), Length(max=100)])

class RelatorioTCOForm(FlaskForm):
    """Formulário para relatório de TCO (Total Cost of Ownership)"""
    veiculo_id = SelectField('Veículo', coerce=int, validators=[DataRequired()])
    periodo_analise = SelectField('Período de Análise', choices=[
        ('3_meses', 'Últimos 3 Meses'),
        ('6_meses', 'Últimos 6 Meses'),
        ('1_ano', 'Último Ano'),
        ('2_anos', 'Últimos 2 Anos'),
        ('personalizado', 'Período Personalizado')
    ], default='1_ano', validators=[DataRequired()])
    
    data_inicio = DateField('Data de Início', validators=[Optional()])
    data_fim = DateField('Data de Fim', validators=[Optional()])
    
    incluir_depreciacao = BooleanField('Incluir Depreciação', default=True)
    valor_depreciacao_anual = FloatField('Depreciação Anual (R$)', validators=[Optional(), NumberRange(min=0)])
    
    incluir_seguro = BooleanField('Incluir Seguro', default=True)
    valor_seguro_anual = FloatField('Seguro Anual (R$)', validators=[Optional(), NumberRange(min=0)])
    
    incluir_ipva = BooleanField('Incluir IPVA', default=True)
    valor_ipva_anual = FloatField('IPVA Anual (R$)', validators=[Optional(), NumberRange(min=0)])
    
    formato_relatorio = SelectField('Formato do Relatório', choices=[
        ('pdf', 'PDF'),
        ('excel', 'Excel'),
        ('web', 'Visualizar na Tela')
    ], default='web', validators=[DataRequired()])
