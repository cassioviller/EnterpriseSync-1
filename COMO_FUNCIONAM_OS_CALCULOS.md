# COMO CADA TIPO DE LANÇAMENTO É LIDO E USADO NOS CÁLCULOS

Este documento explica **exatamente** como cada tipo de lançamento é processado pelo sistema e como afeta os cálculos dos KPIs.

---

## 1. ESTRUTURA DOS TIPOS DE LANÇAMENTO

### 📋 TIPOS DE REGISTRO DE PONTO

O campo `tipo_registro` na tabela `RegistroPonto` pode ter os seguintes valores:

```python
# Tipos básicos
'trabalho_normal'        # Dia normal de trabalho
'falta'                  # Falta não justificada
'falta_justificada'      # Falta com justificativa aprovada
'meio_periodo'           # Trabalho em meio período

# Tipos especiais (fins de semana e feriados)
'sabado_horas_extras'    # Trabalho no sábado (50% extras)
'domingo_horas_extras'   # Trabalho no domingo (100% extras)
'feriado'                # Feriado não trabalhado
'feriado_trabalhado'     # Feriado trabalhado (100% extras)
```

---

## 2. LÓGICA DE LEITURA DOS DADOS

### 🔍 COMO O SISTEMA LÊ CADA TIPO

#### A. TRABALHO NORMAL (`trabalho_normal`)
```python
# Campos lidos:
- hora_entrada          # Ex: 08:00
- hora_saida            # Ex: 17:00  
- hora_almoco_saida     # Ex: 12:00
- hora_almoco_retorno   # Ex: 13:00
- horas_trabalhadas     # Ex: 8.0
- horas_extras          # Ex: 0.0
- total_atraso_minutos  # Ex: 30 (atraso entrada ou saída antecipada)

# Cálculos automáticos:
total_atraso_horas = total_atraso_minutos / 60
```

#### B. FALTAS (`falta` e `falta_justificada`)
```python
# Campos lidos:
- data                  # Data da falta
- tipo_registro         # 'falta' ou 'falta_justificada'
- observacoes          # Motivo da falta

# Cálculos:
# Falta = 8 horas perdidas
# Falta justificada = NÃO conta como horas perdidas
```

#### C. SÁBADO/DOMINGO EXTRAS
```python
# Campos lidos:
- hora_entrada          # Ex: 08:00
- hora_saida            # Ex: 12:00
- horas_trabalhadas     # Ex: 4.0
- horas_extras          # Ex: 4.0 (mesmo valor das horas trabalhadas)
- percentual_extras     # Ex: 50% (sábado) ou 100% (domingo)

# Cálculos:
# Sábado: todas as horas são extras com 50% adicional
# Domingo: todas as horas são extras com 100% adicional
```

#### D. FERIADO TRABALHADO
```python
# Campos lidos:
- hora_entrada          # Ex: 08:00
- hora_saida            # Ex: 17:00
- horas_trabalhadas     # Ex: 8.0
- horas_extras          # Ex: 8.0 (mesmo valor das horas trabalhadas)
- percentual_extras     # Ex: 100%

# Cálculos:
# Todas as horas do feriado são consideradas extras com 100% adicional
```

#### E. MEIO PERÍODO
```python
# Campos lidos:
- hora_entrada          # Ex: 08:00
- hora_saida            # Ex: 12:00
- horas_trabalhadas     # Ex: 4.0
- horas_extras          # Ex: 0.0

# Cálculos:
# Trabalho reduzido, sem horas extras
```

---

## 3. CÁLCULOS DOS KPIs

### 📊 FÓRMULAS UTILIZADAS

#### A. HORAS TRABALHADAS
```python
def calcular_horas_trabalhadas(registros_ponto):
    total = 0
    for registro in registros_ponto:
        # Soma apenas registros que têm horas trabalhadas
        if registro.horas_trabalhadas:
            total += registro.horas_trabalhadas
    return total
```

#### B. HORAS EXTRAS
```python
def calcular_horas_extras(registros_ponto):
    total = 0
    for registro in registros_ponto:
        # Soma horas extras de todos os tipos
        if registro.horas_extras:
            total += registro.horas_extras
    return total
```

#### C. FALTAS
```python
def calcular_faltas(registros_ponto):
    total = 0
    for registro in registros_ponto:
        # Conta apenas faltas não justificadas
        if registro.tipo_registro == 'falta':
            total += 1
    return total
```

#### D. ATRASOS
```python
def calcular_atrasos(registros_ponto):
    total_minutos = 0
    for registro in registros_ponto:
        # Soma todos os atrasos em minutos
        if registro.total_atraso_minutos:
            total_minutos += registro.total_atraso_minutos
    
    # Converte para horas
    return total_minutos / 60
```

#### E. HORAS PERDIDAS
```python
def calcular_horas_perdidas(registros_ponto):
    faltas = calcular_faltas(registros_ponto)
    atrasos_horas = calcular_atrasos(registros_ponto)
    
    # Fórmula: (faltas × 8) + atrasos_horas
    return (faltas * 8) + atrasos_horas
```

---

## 4. CUSTOS CALCULADOS

### 💰 CÁLCULO DE CUSTOS POR TIPO

#### A. CUSTO MÃO DE OBRA
```python
def calcular_custo_mao_obra(funcionario, registros_ponto):
    salario_hora = funcionario.salario / 220  # 220 horas/mês
    
    horas_normais = calcular_horas_trabalhadas(registros_ponto)
    custo_normal = horas_normais * salario_hora
    
    return custo_normal
```

#### B. CUSTO HORAS EXTRAS
```python
def calcular_custo_horas_extras(funcionario, registros_ponto):
    salario_hora = funcionario.salario / 220
    
    total_custo_extras = 0
    for registro in registros_ponto:
        if registro.horas_extras and registro.percentual_extras:
            multiplicador = 1 + (registro.percentual_extras / 100)
            custo_extras = registro.horas_extras * salario_hora * multiplicador
            total_custo_extras += custo_extras
    
    return total_custo_extras
```

#### C. CUSTO ALIMENTAÇÃO
```python
def calcular_custo_alimentacao(funcionario_id, data_inicio, data_fim):
    registros = RegistroAlimentacao.query.filter(
        RegistroAlimentacao.funcionario_id == funcionario_id,
        RegistroAlimentacao.data >= data_inicio,
        RegistroAlimentacao.data <= data_fim
    ).all()
    
    return sum(registro.valor for registro in registros)
```

#### D. OUTROS CUSTOS
```python
def calcular_outros_custos(funcionario_id, data_inicio, data_fim):
    custos = OutroCusto.query.filter(
        OutroCusto.funcionario_id == funcionario_id,
        OutroCusto.data >= data_inicio,
        OutroCusto.data <= data_fim
    ).all()
    
    return sum(custo.valor for custo in custos)
```

---

## 5. PRODUTIVIDADE E ABSENTEÍSMO

### 📈 CÁLCULOS DE PERFORMANCE

#### A. PRODUTIVIDADE
```python
def calcular_produtividade(horas_trabalhadas, dias_uteis):
    horas_esperadas = dias_uteis * 8  # 8 horas por dia útil
    produtividade = (horas_trabalhadas / horas_esperadas) * 100
    return produtividade
```

#### B. ABSENTEÍSMO
```python
def calcular_absenteismo(faltas, dias_uteis):
    absenteismo = (faltas / dias_uteis) * 100
    return absenteismo
```

---

## 6. EXEMPLOS PRÁTICOS

### 🔧 COMO DIFERENTES TIPOS AFETAM OS CÁLCULOS

#### EXEMPLO 1: Trabalho Normal com Atraso
```python
# Registro:
{
    'tipo_registro': 'trabalho_normal',
    'hora_entrada': '08:30',      # 30 min atraso
    'hora_saida': '17:00',
    'horas_trabalhadas': 7.5,
    'horas_extras': 0.0,
    'total_atraso_minutos': 30
}

# Impacto nos KPIs:
# - Horas trabalhadas: +7.5h
# - Horas extras: +0.0h
# - Faltas: +0
# - Atrasos: +0.5h
# - Horas perdidas: +0.5h
```

#### EXEMPLO 2: Sábado com Horas Extras
```python
# Registro:
{
    'tipo_registro': 'sabado_horas_extras',
    'hora_entrada': '08:00',
    'hora_saida': '12:00',
    'horas_trabalhadas': 4.0,
    'horas_extras': 4.0,          # Todas as horas são extras
    'percentual_extras': 50
}

# Impacto nos KPIs:
# - Horas trabalhadas: +4.0h
# - Horas extras: +4.0h
# - Custo extra: 4h × salário/hora × 1.5 (50% adicional)
```

#### EXEMPLO 3: Falta Não Justificada
```python
# Registro:
{
    'tipo_registro': 'falta',
    'data': '2025-06-10',
    'observacoes': 'Falta não justificada'
}

# Impacto nos KPIs:
# - Horas trabalhadas: +0h
# - Faltas: +1
# - Horas perdidas: +8h (1 falta × 8h)
# - Absenteísmo: +5% (1 falta ÷ 20 dias úteis)
```

#### EXEMPLO 4: Feriado Trabalhado
```python
# Registro:
{
    'tipo_registro': 'feriado_trabalhado',
    'hora_entrada': '08:00',
    'hora_saida': '17:00',
    'horas_trabalhadas': 8.0,
    'horas_extras': 8.0,          # Todas as horas são extras
    'percentual_extras': 100
}

# Impacto nos KPIs:
# - Horas trabalhadas: +8.0h
# - Horas extras: +8.0h
# - Custo extra: 8h × salário/hora × 2.0 (100% adicional)
```

---

## 7. FLUXO DE PROCESSAMENTO

### 🔄 SEQUÊNCIA DE CÁLCULOS

1. **Leitura dos Dados**
   - Sistema busca todos os registros do funcionário no período
   - Filtra por tipo de registro
   - Carrega dados relacionados (horários, valores, etc.)

2. **Processamento por Tipo**
   - Cada tipo de registro é processado com sua lógica específica
   - Valores são acumulados em variáveis de controle
   - Cálculos intermediários são realizados

3. **Cálculos dos KPIs**
   - Fórmulas são aplicadas aos valores acumulados
   - Percentuais são calculados
   - Custos são computados

4. **Apresentação dos Resultados**
   - Valores são formatados para exibição
   - KPIs são organizados por categoria
   - Relatórios são gerados

---

## 8. CONSIDERAÇÕES ESPECIAIS

### ⚠️ REGRAS IMPORTANTES

1. **Prioridade dos Tipos**
   - Feriados têm prioridade sobre trabalho normal
   - Faltas justificadas não contam como horas perdidas
   - Fins de semana sempre são considerados extras

2. **Validações**
   - Horários devem ser consistentes
   - Percentuais de extras devem ser válidos
   - Datas devem estar dentro do período

3. **Defaults**
   - Tipo não especificado = 'trabalho_normal'
   - Percentual não especificado = 0%
   - Atrasos não especificados = 0 minutos

---

**Este documento mostra exatamente como cada tipo de lançamento é interpretado e usado nos cálculos do sistema SIGE v5.0.**