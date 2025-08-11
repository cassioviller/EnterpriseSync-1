# RELATÓRIO ANÁLISE HORAS EXTRAS - SISTEMA SIGE

## Data: 11/08/2025

## Problema Identificado na Imagem
- **Funcionário**: Carlos Alberto Rigolin Junior
- **Salário**: R$ 2.106,00
- **Horas Extras**: 7.8h (julho/2025)
- **Custo Total**: R$ 2.125,38
- **Custo Adicional**: R$ 19,38

## Funcionários Carlos Encontrados no Sistema
1. **Carlos Pereira Lima** (ID 98) - R$ 4.500,00
2. **Carlos Pereira Lima** (ID 109) - R$ 3.800,00  
3. **José Carlos Ferreira** (ID 112) - R$ 2.800,00
4. **Carlos Silva Vale Verde** (ID 121) - R$ 3.500,00
5. **Carlos Silva Teste** (ID 127) - R$ 5.500,00

**Observação**: Nenhum funcionário encontrado com salário R$ 2.106,00 exato

## Lógica de Cálculo de Horas Extras no Sistema

### 1. Fontes de Cálculo Identificadas

#### A) KPIs Engine (`kpis_engine.py`)
```python
# Horário padrão fixo: 07:12 às 17:00
entrada_padrao_min = 7 * 60 + 12   # 432 min (07:12)
saida_padrao_min = 17 * 60          # 1020 min (17:00)

# Calcular extras
extras_entrada = max(0, entrada_padrao_min - entrada_real_min)  # Entrada antecipada
extras_saida = max(0, saida_real_min - saida_padrao_min)        # Saída atrasada
total_horas_extras += (extras_entrada + extras_saida) / 60
```

#### B) Calculadora de Obra (`calculadora_obra.py`)
```python
def calcular_valor_hora_funcionario(self, funcionario_id):
    # Baseado no horário específico do funcionário
    horas_mensais = horas_diarias * dias_uteis_mes
    return funcionario.salario / horas_mensais
```

#### C) Views (`views.py`)
```python
# Cálculo padrão simples
valor_hora = funcionario.salario / 220  # 220 horas/mês aprox
```

### 2. Multiplicadores de Horas Extras

**Baseado em `RELATORIO_CUSTO_MAO_OBRA_CAIO_DETALHADO.md`:**

| Tipo | Multiplicador | Aplicação |
|------|---------------|-----------|
| **Horas Extras Normais** | 1,5x | Trabalho além do horário |
| **Sábado Trabalhado** | 1,5x | 50% adicional |
| **Domingo Trabalhado** | 2,0x | 100% adicional |
| **Feriado Trabalhado** | 2,0x | 100% adicional |

### 3. Análise do Caso Carlos Alberto

#### Cálculo Reverso (baseado na imagem):
- **Diferença**: R$ 2.125,38 - R$ 2.106,00 = **R$ 19,38**
- **Horas extras**: 7.8h
- **Valor/hora extras**: R$ 19,38 ÷ 7.8h = **R$ 2,49/hora extras**

#### Possíveis Cenários:

**Cenário 1 - Valor/hora base R$ 1,66**
- Valor/hora extras = R$ 1,66 × 1,5 = R$ 2,49 ✅
- Valor/hora mensal = R$ 2.106,00 ÷ 1.270h = R$ 1,66

**Cenário 2 - Valor/hora base R$ 9,57** 
- Valor/hora normal = R$ 2.106,00 ÷ 220h = R$ 9,57
- Valor/hora extras = R$ 9,57 × 1,5 = R$ 14,36
- Custo esperado = 7.8h × R$ 14,36 = **R$ 112,01** ❌

### 4. Discrepâncias Identificadas

#### Problema 1: Valor Hora Inconsistente
- **Sistema padrão**: R$ 9,57/hora (salário ÷ 220h)
- **Cálculo reverso**: R$ 1,66/hora
- **Diferença**: 477% menor que o esperado

#### Problema 2: Base de Cálculo
- **220h/mês** (padrão CLT) vs **horário específico**
- **Horário padrão fixo** vs **horário do funcionário**

#### Problema 3: Multiplicadores
- **Tipos diferentes** de horas extras com percentuais específicos
- **Sábados**: 50% (1,5x) vs **Domingos**: 100% (2,0x)

## Possíveis Causas

### 1. Bug no Cálculo de Valor/Hora
O sistema pode estar calculando valor/hora incorretamente, usando uma base muito maior (1.270h vs 220h).

### 2. Tipo de Horas Extras Não Considerado
As 7.8h podem incluir tipos diferentes com multiplicadores variados.

### 3. Período Proporcional
Cálculo pode estar considerando apenas julho (não mês completo).

### 4. Funcionário Diferente
Carlos Alberto Rigolin Junior pode não estar no banco de dados atual.

## Recomendações de Correção

### 1. Verificação Imediata
- Localizar o funcionário exato com salário R$ 2.106,00
- Validar registros de ponto de julho/2025
- Verificar horário de trabalho configurado

### 2. Auditoria de Cálculo
- Revisar lógica de valor/hora em todas as funções
- Padronizar cálculo entre KPIs engine e views
- Verificar multiplicadores por tipo de registro

### 3. Teste com Dados Reais
- Simular cálculo manual para o período
- Comparar resultado com interface
- Documentar diferenças encontradas

## Status
🔴 **INVESTIGAÇÃO NECESSÁRIA** - Discrepância significativa identificada nos cálculos de horas extras.

---
**Próximo passo**: Localizar funcionário com salário R$ 2.106,00 e analisar registros específicos de julho/2025.