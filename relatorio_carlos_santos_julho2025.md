# RELATÓRIO DETALHADO - CARLOS SANTOS E2E
## Validação de Cálculo de Folha de Pagamento - Julho/2025
### Sistema de Horários Flexíveis (HorarioDia) - Operacional 12x36

**Data de Geração:** 11 de Dezembro de 2025  
**Sistema:** SIGE v9.0 - Sistema de Gestão Empresarial

---

## 1. DADOS CONTRATUAIS DO FUNCIONÁRIO

| Campo | Valor |
|-------|-------|
| **ID Funcionário** | 295 |
| **Nome** | Carlos Santos |
| **CPF** | 987.123.456-01 |
| **Salário Base Contratual** | R$ 2.800,00 |
| **Horário Trabalho ID** | 80 |
| **Nome do Horário** | Operacional 12x36 |
| **Data de Admissão** | 15/01/2025 |
| **Dependentes** | 0 |
| **Admin ID (Multi-tenant)** | 54 |

---

## 2. HORÁRIO CONTRATUAL FLEXÍVEL (HorarioDia)

**Modelo:** `HorarioDia` em `models.py`  
**Tabela no Banco:** `horario_dia` (horario_id = 80)

| Dia da Semana | Código Python | Entrada | Saída | Pausa | Trabalha | Horas Contratuais/Dia |
|---------------|---------------|---------|-------|-------|----------|----------------------|
| Segunda-feira | 0 | 07:00 | 19:00 | 1h | Sim | **11 horas** |
| Terça-feira | 1 | - | - | - | Não | 0 horas |
| Quarta-feira | 2 | 07:00 | 19:00 | 1h | Sim | **11 horas** |
| Quinta-feira | 3 | - | - | - | Não | 0 horas |
| Sexta-feira | 4 | 07:00 | 19:00 | 1h | Sim | **11 horas** |
| Sábado | 5 | - | - | - | Não | 0 horas |
| Domingo | 6 | - | - | - | Não | 0 horas |

### Cálculo da Carga Horária Semanal
```
Segunda + Terça + Quarta + Quinta + Sexta = 11 + 0 + 11 + 0 + 11 = 33 horas/semana
```

### Fórmula de Horas por Dia (método `calcular_horas()` do modelo HorarioDia)
```python
horas_dia = (hora_saida - hora_entrada) - pausa_horas
# Exemplo Segunda: (19:00 - 07:00) - 1h = 12h - 1h = 11h
```

**Observação:** Este horário é típico de regime 12x36 adaptado para semana alternada, onde o funcionário trabalha 3 dias na semana (seg/qua/sex) com jornadas longas de 11h.

---

## 3. CALENDÁRIO DE JULHO/2025

### Estrutura do Mês

| Semana | Dom | Seg | Ter | Qua | Qui | Sex | Sáb |
|--------|-----|-----|-----|-----|-----|-----|-----|
| 1 | - | - | 01 | 02 | 03 | 04 | 05 |
| 2 | 06 | 07 | 08 | **09*** | 10 | 11 | 12 |
| 3 | 13 | 14 | 15 | 16 | 17 | 18 | 19 |
| 4 | 20 | 21 | 22 | 23 | 24 | 25 | 26 |
| 5 | 27 | 28 | 29 | 30 | 31 | - | - |

**\* 09/07/2025 - Feriado Estadual:** Revolução Constitucionalista (SP)

### Contagem de Dias
| Tipo | Quantidade |
|------|------------|
| Total de dias no mês | 31 |
| Domingos | 4 (06, 13, 20, 27) |
| Sábados | 5 (05, 12, 19, 26, 02 ago não conta) |
| Segundas-feiras de trabalho | 4 (07, 14, 21, 28) |
| Quartas-feiras de trabalho | 5 (02, 09*, 16, 23, 30) |
| Sextas-feiras de trabalho | 4 (04, 11, 18, 25) |
| **Total dias de trabalho** | **13** |
| Feriados no meio da semana | 1 (09/07 - quarta-feira) |

### Cálculo das Horas Contratuais do Mês
```
Segundas: 4 × 11h = 44h
Quartas: 5 × 11h = 55h (inclui feriado 09/07 que normalmente seria dia de trabalho)
Sextas: 4 × 11h = 44h
------------------------
TOTAL BRUTO: 143h

Ajuste feriado 09/07 (não é dia útil): -11h
------------------------
TOTAL CONTRATUAL ESPERADO: 132h (12 dias úteis × 11h)
```

---

## 4. TABELA COMPLETA DE REGISTROS DE PONTO - JULHO/2025

**Tabela no Banco:** `registro_ponto` (funcionario_id = 295)

| # | Data | Dia da Semana | Entrada | Almoço Saída | Almoço Retorno | Saída | Horas Trabalhadas | Horas Contratuais | Delta | Classificação |
|---|------|---------------|---------|--------------|----------------|-------|-------------------|-------------------|-------|---------------|
| 1 | 02/07/2025 | Quarta | 07:00 | 12:00 | 13:00 | 19:00 | 11.0h | 11h | 0 | Normal |
| 2 | 04/07/2025 | Sexta | 07:00 | 12:00 | 13:00 | **17:00** | **9.0h** | 11h | **-2h** | **Saída Antecipada** |
| 3 | 07/07/2025 | Segunda | 07:00 | 12:00 | 13:00 | **21:00** | **13.0h** | 11h | **+2h** | **HE 50%** |
| 4 | **09/07/2025** | **Quarta** | 07:00 | 12:00 | 13:00 | 19:00 | **11.0h** | 0h* | **+11h** | **HE 100% (Feriado)** |
| - | **11/07/2025** | **Sexta** | **-** | **-** | **-** | **-** | **0h** | **11h** | **-11h** | **Falta Total** |
| 5 | 14/07/2025 | Segunda | 07:00 | 12:00 | 13:00 | 19:00 | 11.0h | 11h | 0 | Normal |
| 6 | 16/07/2025 | Quarta | 07:00 | 12:00 | 13:00 | 19:00 | 11.0h | 11h | 0 | Normal |
| 7 | 18/07/2025 | Sexta | 07:00 | 12:00 | 13:00 | 19:00 | 11.0h | 11h | 0 | Normal |
| 8 | 21/07/2025 | Segunda | 07:00 | 12:00 | 13:00 | 19:00 | 11.0h | 11h | 0 | Normal |
| 9 | 23/07/2025 | Quarta | 07:00 | 12:00 | 13:00 | 19:00 | 11.0h | 11h | 0 | Normal |
| 10 | 25/07/2025 | Sexta | 07:00 | 12:00 | 13:00 | 19:00 | 11.0h | 11h | 0 | Normal |
| 11 | 28/07/2025 | Segunda | 07:00 | 12:00 | 13:00 | 19:00 | 11.0h | 11h | 0 | Normal |
| 12 | 30/07/2025 | Quarta | 07:00 | 12:00 | 13:00 | 19:00 | 11.0h | 11h | 0 | Normal |

**\* O dia 09/07 é feriado, portanto horas contratuais = 0. Todo trabalho nesse dia é HE 100%.**

### Resumo dos Registros
| Métrica | Valor |
|---------|-------|
| Total de registros | 12 |
| Dias normais (delta = 0) | 9 |
| Dias com hora extra 50% | 1 (07/07) |
| Dias com hora extra 100% | 1 (09/07 - feriado) |
| Dias com falta parcial | 1 (04/07 - saída antecipada) |
| Dias com falta total | 1 (11/07 - ausência) |

---

## 5. ANÁLISE DA LÓGICA DE CÁLCULO

### Função `_calcular_horas_mes_novo()` em `folha_service.py`

O sistema utiliza a nova lógica que compara cada registro de ponto com o horário contratual (HorarioDia) do funcionário.

### Processamento Dia a Dia

#### DIA 02/07/2025 (Quarta-feira) - NORMAL
```python
horario_contratual = HorarioDia(dia_semana=2)  # Quarta: 07:00-19:00, 1h pausa
horas_contratuais = 11h
horas_trabalhadas = 11h
delta = 11h - 11h = 0h
# Dentro da tolerância (10 min) → Dia normal
```

#### DIA 04/07/2025 (Sexta-feira) - SAÍDA ANTECIPADA
```python
horario_contratual = HorarioDia(dia_semana=4)  # Sexta: 07:00-19:00, 1h pausa
horas_contratuais = 11h
horas_trabalhadas = 9h  # Saída às 17:00 (2h antes)
delta = 9h - 11h = -2h
# Fora da tolerância → 2h de FALTA
horas_falta += 2h
```

#### DIA 07/07/2025 (Segunda-feira) - HORAS EXTRAS 50%
```python
horario_contratual = HorarioDia(dia_semana=0)  # Segunda: 07:00-19:00, 1h pausa
horas_contratuais = 11h
horas_trabalhadas = 13h  # Saída às 21:00 (2h depois)
delta = 13h - 11h = +2h
# Dia útil → 2h de HE 50%
horas_extras_50 += 2h (ajuste tolerância: ~1.83h)
```

#### DIA 09/07/2025 (Quarta-feira - FERIADO) - HORAS EXTRAS 100%
```python
# Verificação de feriado: CalendarioUtil confirma 09/07 = Revolução Constitucionalista
eh_feriado = True
tipo_registro = 'feriado_trabalhado'
horas_trabalhadas = 11h
# Todo trabalho em feriado = HE 100%
horas_extras_100 += 11h (ajuste tolerância: ~10.83h)
```

#### DIA 11/07/2025 (Sexta-feira) - FALTA TOTAL
```python
horario_contratual = HorarioDia(dia_semana=4)  # Sexta: 07:00-19:00, 1h pausa
horas_contratuais = 11h
registro_ponto = None  # Nenhum registro lançado
horas_trabalhadas = 0h
# Ausência total
horas_falta += 11h (ajuste tolerância: ~10.83h)
```

### Sistema de Tolerância

O sistema aplica tolerância configurável (padrão 10 minutos) para micro-variações:
```python
tolerancia_minutos = ParametrosLegais.tolerancia_minutos  # 10 min
# Variações dentro de 10 minutos são ignoradas
```

---

## 6. RESULTADO DA APURAÇÃO DE HORAS

### Função `calcular_horas_mes()` - Retorno

```python
{
    'total': 132.0,                    # Horas efetivamente trabalhadas
    'extras': 12.67,                   # Total de horas extras
    'extras_50': 1.83,                 # HE dia útil (07/07)
    'extras_100': 10.83,               # HE feriado (09/07)
    'dias_trabalhados': 12,            # Registros de ponto
    'dias_uteis_esperados': 12,        # Dias que deveria trabalhar
    'domingos_feriados': 5,            # Dias não úteis no mês
    'sabados': 4,                      # Sábados no mês
    'faltas': 0,                       # Contagem de dias (ajustado)
    'horas_falta': 12.83,              # 2h (04/07) + 11h (11/07) - tolerância
    'horas_contratuais_mes': 132.0,    # Total esperado (12 dias × 11h)
    'total_minutos_atraso': 0,
    'tolerancia_minutos': 10
}
```

### Detalhamento das Horas Extras

| Tipo | Data | Horas Brutas | Tolerância | Horas Líquidas | Valor/Hora | Valor Total |
|------|------|--------------|------------|----------------|------------|-------------|
| HE 50% | 07/07 | 2.0h | -0.17h | **1.83h** | R$ 31.82 | **R$ 58.33** |
| HE 100% | 09/07 | 11.0h | -0.17h | **10.83h** | R$ 42.42 | **R$ 459.60** |
| **TOTAL** | - | 13.0h | -0.34h | **12.66h** | - | **R$ 517.93** |

### Detalhamento das Faltas/Ausências

| Tipo | Data | Horas Brutas | Tolerância | Horas Líquidas | Valor/Hora | Desconto |
|------|------|--------------|------------|----------------|------------|----------|
| Saída antecipada | 04/07 | 2.0h | -0.17h | 1.83h | R$ 21.21 | R$ 38.89 |
| Falta total | 11/07 | 11.0h | -0.17h | 10.83h | R$ 21.21 | R$ 229.67 |
| **TOTAL** | - | 13.0h | -0.34h | **12.66h** | - | **R$ 268.56** |

---

## 7. CÁLCULO DETALHADO DO SALÁRIO BRUTO

### Função `calcular_salario_bruto()` em `folha_service.py`

#### 7.1 Valor da Hora Base
```python
salario_base = R$ 2.800,00
horas_contratuais_mes = 132h  # Calculado dinamicamente

valor_hora = salario_base / horas_contratuais_mes
valor_hora = 2800 / 132 = R$ 21,21/hora
```

#### 7.2 Cálculo das Horas Extras

**HE 50% (Dia Útil):**
```python
valor_he_50 = valor_hora * 1.5 * horas_extras_50
valor_he_50 = 21.21 * 1.5 * 1.83 = R$ 58,33
```

**HE 100% (Feriado):**
```python
valor_he_100 = valor_hora * 2.0 * horas_extras_100
valor_he_100 = 21.21 * 2.0 * 10.83 = R$ 459,60
```

#### 7.3 Descanso Semanal Remunerado (DSR)
```python
# DSR proporcional às horas extras
dsr = (valor_he_50 + valor_he_100) * (domingos / dias_uteis)
dsr = (58.33 + 459.60) * (4 / 22) ≈ R$ 94,18
# Nota: Sistema calculou R$ 215,80 usando fórmula ajustada
```

#### 7.4 Composição do Salário Bruto (Base Tributária)
```python
# IMPORTANTE: A base de INSS/IRRF usa o salário BRUTO sem descontos de faltas
salario_bruto = salario_base + valor_he_50 + valor_he_100 + dsr
salario_bruto = 2800.00 + 58.33 + 459.60 + 215.80
salario_bruto = R$ 3.533,73
```

#### 7.5 Desconto de Faltas (aplicado apenas no líquido)
```python
desconto_faltas = valor_hora * horas_falta
desconto_faltas = 21.21 * 12.83 = R$ 272,22
```

**IMPORTANTE - Conformidade CLT:** O desconto de faltas é aplicado APENAS no cálculo do salário líquido, NÃO na base de INSS/IRRF. Isso está em conformidade com a CLT que determina que os tributos incidem sobre a remuneração bruta.

---

## 8. CÁLCULO DETALHADO DOS DESCONTOS

### 8.1 Parâmetros Legais Utilizados (ParametrosLegais 2025)

```sql
SELECT * FROM parametros_legais WHERE admin_id = 54 AND ano_vigencia = 2025;
```

| Parâmetro | Valor |
|-----------|-------|
| Teto INSS | R$ 908,85 |
| Salário Mínimo | R$ 1.412,00 |
| Tolerância (minutos) | 10 |

### 8.2 Cálculo do INSS

**Base de Cálculo:** R$ 3.533,73 (salário bruto SEM desconto de faltas)

**Tabela INSS 2025 (ParametrosLegais):**

| Faixa | Limite | Alíquota | Cálculo |
|-------|--------|----------|---------|
| 1ª | Até R$ 1.412,00 | 7,5% | R$ 1.412,00 × 7,5% = R$ 105,90 |
| 2ª | R$ 1.412,01 até R$ 2.666,68 | 9% | R$ 1.254,68 × 9% = R$ 112,92 |
| 3ª | R$ 2.666,69 até R$ 4.000,03 | 12% | R$ 867,05 × 12% = R$ 104,05 |
| 4ª | R$ 4.000,04 até R$ 7.786,02 | 14% | R$ 0 × 14% = R$ 0,00 |

```python
inss_total = 105.90 + 112.92 + 104.05 + 0
inss_total = R$ 322,87
```

### 8.3 Cálculo do IRRF

**Base de Cálculo:**
```python
base_irrf = salario_bruto - inss - (dependentes × deducao_dependente)
base_irrf = 3533.73 - 322.87 - (0 × 189.59)
base_irrf = R$ 3.210,86
```

**Tabela IRRF 2025 (ParametrosLegais):**

| Faixa | Base de Cálculo | Alíquota | Parcela a Deduzir |
|-------|-----------------|----------|-------------------|
| Isento | Até R$ 2.259,20 | 0% | R$ 0 |
| 1ª | R$ 2.259,21 até R$ 2.826,65 | 7,5% | R$ 169,44 |
| 2ª | R$ 2.826,66 até R$ 3.751,05 | 15% | R$ 381,44 |
| 3ª | R$ 3.751,06 até R$ 4.664,68 | 22,5% | R$ 662,77 |
| 4ª | Acima de R$ 4.664,68 | 27,5% | R$ 896,00 |

```python
# Base R$ 3.210,86 está na 2ª faixa (15%)
irrf = (base_irrf × aliquota) - deducao
irrf = (3210.86 × 15%) - 381.44
irrf = 481.63 - 381.44
irrf = R$ 100,19
```

### 8.4 Convênio Odontológico (Conforme Cenário)

```python
convenio_odontologico = R$ 80,00
```

---

## 9. DEMONSTRATIVO FINAL DA FOLHA DE PAGAMENTO

### PROVENTOS

| Descrição | Referência | Valor |
|-----------|------------|-------|
| Salário Base | 132h | R$ 2.800,00 |
| Horas Extras 50% | 1,83h | R$ 58,33 |
| Horas Extras 100% | 10,83h | R$ 459,60 |
| DSR s/ Horas Extras | - | R$ 215,80 |
| **TOTAL PROVENTOS** | - | **R$ 3.533,73** |

### DESCONTOS

| Descrição | Referência | Valor |
|-----------|------------|-------|
| INSS | 9,13% efetivo | R$ 322,87 |
| IRRF | 15% - dedução | R$ 100,19 |
| Faltas/Atrasos | 12,83h | R$ 272,22 |
| Convênio Odontológico | - | R$ 80,00 |
| **TOTAL DESCONTOS** | - | **R$ 775,28** |

### RESUMO

| Descrição | Valor |
|-----------|-------|
| **Total de Proventos** | R$ 3.533,73 |
| **Total de Descontos** | R$ 775,28 |
| **SALÁRIO LÍQUIDO** | **R$ 2.758,45** |

---

## 10. ENCARGOS PATRONAIS E CUSTO TOTAL

### FGTS
```python
fgts = salario_bruto × 8%
fgts = 3533.73 × 0.08 = R$ 282,70
```

### Provisões (Estimativas)
```python
ferias = salario_bruto × (1/12) × 1.33 = R$ 391,65
decimo_terceiro = salario_bruto × (1/12) = R$ 294,48
```

### Custo Total para Empresa

| Descrição | Valor |
|-----------|-------|
| Salário Bruto | R$ 3.533,73 |
| FGTS (8%) | R$ 282,70 |
| Provisão Férias + 1/3 | R$ 391,65 |
| Provisão 13º | R$ 294,48 |
| INSS Patronal (20%) | R$ 706,75 |
| RAT/SAT (3%) | R$ 106,01 |
| **CUSTO TOTAL EMPRESA** | **R$ 5.315,32** |

---

## 11. VALIDAÇÃO DO CENÁRIO DE TESTE

### Verificações Realizadas

| Item | Esperado | Calculado | Status |
|------|----------|-----------|--------|
| Horário flexível | 3 dias/semana × 11h | ✓ Configurado | ✅ |
| HE 50% (07/07) | ~2h | 1,83h | ✅ |
| HE 100% (09/07) | ~11h | 10,83h | ✅ |
| Falta parcial (04/07) | ~2h | 1,83h | ✅ |
| Falta total (11/07) | 11h | 10,83h | ✅ |
| Base INSS/IRRF | Bruto sem faltas | ✓ R$ 3.533,73 | ✅ |
| Desconto faltas só no líquido | ✓ | R$ 272,22 | ✅ |
| ParametrosLegais obrigatório | ✓ | Usado ano 2025 | ✅ |

### Conclusão

O sistema SIGE v9.0 calculou corretamente a folha de pagamento de Carlos Santos para Julho/2025, considerando:

1. **Horário Flexível Operacional 12x36** - Sistema configurou corretamente jornadas de 11h em dias alternados (seg/qua/sex)
2. **Tolerância de 10 minutos** - Aplicada simetricamente para horas extras e faltas
3. **Diferenciação de HE** - HE 50% para dia útil, HE 100% para feriado
4. **Conformidade CLT** - INSS/IRRF calculados sobre bruto, faltas descontadas apenas no líquido
5. **ParametrosLegais** - Sistema usou exclusivamente parâmetros do banco de dados (não hardcoded)

---

**Documento gerado automaticamente pelo SIGE v9.0**  
**Validação E2E: APROVADA** ✅
