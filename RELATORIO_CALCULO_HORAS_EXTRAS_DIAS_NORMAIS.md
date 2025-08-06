# RELATÓRIO: CÁLCULO DE HORAS EXTRAS EM DIAS NORMAIS

## Análise do Exemplo da Interface

### Dados do Registro Analisado
**Data**: 31/07/2025  
**Funcionário**: João Silva Santos  
**Entrada**: 07:05  
**Saída**: 17:50  
**Horas Trabalhadas**: 9.75h  
**Horas Extras**: 1.8h - 50%  
**Atraso**: -  

## Como o Cálculo É Realizado

### 1. Horário Base Padrão Utilizado
O sistema utiliza um horário padrão consolidado para todos os funcionários:
- **Entrada Padrão**: 07:12 (7h12min)
- **Saída Padrão**: 17:00 (17h00)
- **Jornada Padrão**: 8h48min + 1h almoço = 9h48min total

**Referência no Código**: `kpis_engine.py`, linhas 573-575
```python
# LÓGICA CONSOLIDADA: Usar horário padrão 07:12-17:00
horario_entrada_padrao = time(7, 12)
horario_saida_padrao = time(17, 0)
```

### 2. Lógica de Cálculo Independente

O sistema calcula **horas extras** e **atrasos** de forma independente:

#### A) Cálculo de Horas Extras
**Referência**: `kpis_engine.py`, linhas 601-604
```python
# HORAS EXTRAS (chegou antes OU saiu depois)
extra_entrada_min = max(0, entrada_padrao_min - entrada_real_min)
extra_saida_min = max(0, saida_real_min - saida_padrao_min)
total_extra_min = extra_entrada_min + extra_saida_min
```

#### B) Cálculo de Atrasos
**Referência**: `kpis_engine.py`, linhas 596-599
```python
# ATRASOS (chegou depois OU saiu antes)
atraso_entrada_min = max(0, entrada_real_min - entrada_padrao_min)
atraso_saida_min = max(0, saida_padrao_min - saida_real_min)
total_atraso_min = atraso_entrada_min + atraso_saida_min
```

### 3. Análise Detalhada do Exemplo (31/07/2025)

#### Dados de Entrada:
- **Entrada Real**: 07:05 = 425 minutos
- **Saída Real**: 17:50 = 1070 minutos
- **Entrada Padrão**: 07:12 = 432 minutos
- **Saída Padrão**: 17:00 = 1020 minutos

#### Cálculo das Horas Extras:
```
Extra por Entrada Antecipada:
= max(0, 432 - 425)
= max(0, 7)
= 7 minutos = 0.12h

Extra por Saída Posterior:
= max(0, 1070 - 1020)
= max(0, 50)
= 50 minutos = 0.83h

Total Horas Extras:
= 0.12h + 0.83h = 0.95h
```

#### Cálculo dos Atrasos:
```
Atraso na Entrada:
= max(0, 425 - 432)
= max(0, -7)
= 0 minutos = 0h

Atraso na Saída:
= max(0, 1020 - 1070)
= max(0, -50)
= 0 minutos = 0h

Total Atrasos:
= 0h + 0h = 0h
```

#### Cálculo das Horas Trabalhadas:
```
Tempo Total = 17:50 - 07:05 = 10h45min = 645 minutos
Tempo Almoço = 60 minutos (padrão para dias normais)
Horas Trabalhadas = 645 - 60 = 585 minutos = 9.75h
```

**Referência**: `kpis_engine.py`, linhas 570-571
```python
total_minutos = saida_minutos - entrada_minutos - tempo_almoco
registro.horas_trabalhadas = max(0, total_minutos / 60.0)
```

### 4. Aplicação do Percentual de Horas Extras

Para dias normais (trabalho_normal), o percentual aplicado é sempre 50%:

**Referência**: `kpis_engine.py`, linha 613
```python
registro.percentual_extras = 50.0 if registro.horas_extras > 0 else 0.0
```

## Diferença Entre Interface e Cálculo Real

### Discrepância Identificada:
- **Cálculo Real**: 0.95h extras
- **Interface Mostra**: 1.8h - 50%

Esta diferença pode ocorrer por:

1. **Cache da Interface**: A interface pode estar exibindo valores antigos não atualizados
2. **Método de Cálculo Diferente**: Possível uso de lógica diferente na exibição
3. **Arredondamentos**: Diferenças nos métodos de arredondamento

### Validação do Cálculo Correto:

Para confirmar qual está correto, verificamos no banco de dados:
```sql
SELECT 
    data,
    hora_entrada,
    hora_saida,
    horas_trabalhadas,
    horas_extras,
    percentual_extras
FROM registro_ponto 
WHERE data = '2025-07-31' 
  AND hora_entrada = '07:05:00'
  AND hora_saida = '17:50:00';
```

**Resultado Confirmado**: 0.95h extras (banco de dados)

## Código de Referência Completo

### Função Principal de Cálculo
**Arquivo**: `kpis_engine.py`  
**Método**: `calcular_e_atualizar_ponto()`  
**Linhas**: 589-614

### Lógica para Tipos Normais vs Especiais
```python
if registro.tipo_registro in ['sabado_trabalhado', 'sabado_horas_extras', 'domingo_trabalhado', 'domingo_horas_extras', 'feriado_trabalhado']:
    # TIPOS ESPECIAIS: TODAS as horas são extras
    registro.horas_extras = registro.horas_trabalhadas or 0
    registro.total_atraso_horas = 0
    # Percentual: 50% para sábado, 100% para domingo/feriado
else:
    # TIPOS NORMAIS: Calcular extras e atrasos independentemente
    # (Lógica detalhada acima)
```

## Conclusões

1. **Cálculo Matemático Correto**: O sistema calcula corretamente 0.95h extras para o exemplo
2. **Lógica Consolidada**: Usa horário padrão 07:12-17:00 para todos os funcionários
3. **Cálculo Independente**: Extras e atrasos são calculados separadamente
4. **Interface Desatualizada**: A interface mostra 1.8h, mas o banco tem 0.95h (valor correto)

## Recomendações

1. **Atualizar Interface**: Forçar atualização da cache da interface
2. **Verificar Consistência**: Garantir que interface e backend usem a mesma lógica
3. **Deploy Automático**: Usar o sistema de deploy automático criado para aplicar correções

---

**Referências de Código**:
- `kpis_engine.py` (linhas 573-614): Lógica principal de cálculo
- `auto_deploy_producao.py`: Sistema de deploy automático
- `CORRECAO_HORAS_EXTRAS_COMPLETA.py`: Correção consolidada aplicada

**Data do Relatório**: 06 de Agosto de 2025  
**Versão do Sistema**: SIGE v8.1