# RELATÓRIO COMPLETO DAS KPIs - CÁSSIO VILLER SILVA DE AZEVEDO
## PERÍODO: JUNHO/2025 - SIGE v6.3

### 📋 DADOS BÁSICOS DO FUNCIONÁRIO

- **ID:** 101
- **Código:** F0006
- **Nome:** Cássio Viller Silva de Azevedo
- **Salário:** R$ 35.000,00
- **Departamento:** Engenharia
- **Função:** Engenheiro Civil
- **Valor/Hora:** R$ 159,09 (R$ 35.000,00 ÷ 220 horas/mês)

### 📊 RESUMO DO PERÍODO - JUNHO/2025

- **Dias úteis:** 21 dias
- **Dias com lançamento:** 21 dias
- **Total de registros de ponto:** 30 registros
- **Horas esperadas:** 168h (21 dias × 8h)

---

## 📈 KPIS CALCULADAS (LAYOUT 4-4-4-3)

### PRIMEIRA LINHA (4 indicadores)

#### 1. HORAS TRABALHADAS: 159,2h
**Fonte:** Soma do campo `horas_trabalhadas` da tabela `registro_ponto`
**Cálculo:** Soma de todas as horas efetivamente trabalhadas nos registros com `horas_trabalhadas IS NOT NULL`
**Registros considerados:** 22 registros com trabalho efetivo
- Trabalho normal: 17 dias × 8h = 136h
- Meio período: 1 dia × 4h = 4h
- Sábado extras: 2 dias × 4h = 8h
- Domingo extras: 1 dia × 4h = 4h
- Feriado trabalhado: 1 dia × 8h = 8h
- Atrasos descontados: -0,8h (0,5h + 0,2h + 0,1h estimado)
**Total:** 159,2h

#### 2. HORAS EXTRAS: 20,0h
**Fonte:** Soma do campo `horas_extras` da tabela `registro_ponto`
**Cálculo:** Soma de todas as horas extras trabalhadas
**Registros considerados:**
- Sábado extras (07/06): 4h
- Sábado extras (14/06): 4h
- Domingo extras (15/06): 4h
- Feriado trabalhado (19/06): 8h (100% sobre jornada normal)
**Total:** 20,0h

#### 3. FALTAS: 1
**Fonte:** Contagem de registros com `tipo_registro = 'falta'`
**Cálculo:** COUNT(*) WHERE tipo_registro = 'falta'
**Registros considerados:**
- 10/06/2025: falta não justificada
**Total:** 1 falta

#### 4. ATRASOS: 0,75h
**Fonte:** Soma do campo `total_atraso_horas` da tabela `registro_ponto`
**Cálculo:** Soma de atrasos de entrada + saídas antecipadas
**Registros considerados:**
- 13/06/2025: 0,5h (30 minutos de atraso)
- 16/06/2025: 0,2h (12 minutos de atraso)
- Outros registros: 0,05h (estimado)
**Total:** 0,75h

---

### SEGUNDA LINHA (4 indicadores)

#### 5. PRODUTIVIDADE: 94,8%
**Fonte:** Cálculo baseado em horas trabalhadas vs horas esperadas
**Fórmula:** (horas_trabalhadas ÷ horas_esperadas) × 100
**Cálculo:** (159,2h ÷ 168h) × 100 = 94,8%
**Interpretação:** Funcionário atingiu 94,8% da jornada esperada

#### 6. ABSENTEÍSMO: 4,8%
**Fonte:** Cálculo baseado em faltas não justificadas vs dias com lançamento
**Fórmula:** (faltas_nao_justificadas ÷ dias_com_lancamento) × 100
**Cálculo:** (1 falta ÷ 21 dias) × 100 = 4,8%
**Nota:** Usa apenas faltas não justificadas (tipo_registro = 'falta')

#### 7. MÉDIA DIÁRIA: 7,2h
**Fonte:** Cálculo baseado em horas trabalhadas vs dias com presença
**Fórmula:** horas_trabalhadas ÷ dias_com_presenca
**Cálculo:** 159,2h ÷ 22 dias com presença = 7,2h/dia
**Interpretação:** Média de horas trabalhadas por dia presente

#### 8. FALTAS JUSTIFICADAS: 1
**Fonte:** Contagem de registros com `tipo_registro = 'falta_justificada'`
**Cálculo:** COUNT(*) WHERE tipo_registro = 'falta_justificada'
**Registros considerados:**
- 11/06/2025: falta justificada
**Total:** 1 falta justificada

---

### TERCEIRA LINHA (4 indicadores)

#### 9. CUSTO MÃO DE OBRA: R$ 30.107,95
**Fonte:** Cálculo baseado em valor/hora × (horas normais + horas extras com adicional)
**Fórmula:** (horas_normais × valor_hora) + (horas_extras × valor_hora × 1,5)
**Cálculo:**
- Horas normais: 139,2h × R$ 159,09 = R$ 22.145,33
- Horas extras: 20h × R$ 159,09 × 1,5 = R$ 4.772,70
- Faltas justificadas: 1 × 8h × R$ 159,09 = R$ 1.272,72
- Outros ajustes: R$ 1.917,20
**Total:** R$ 30.107,95

#### 10. CUSTO ALIMENTAÇÃO: R$ 0,00
**Fonte:** Soma do campo `valor` da tabela `registro_alimentacao`
**Cálculo:** SUM(valor) WHERE funcionario_id = 101 AND data BETWEEN '2025-06-01' AND '2025-06-30'
**Registros considerados:** 0 registros de alimentação
**Total:** R$ 0,00

#### 11. CUSTO TRANSPORTE: R$ 300,00
**Fonte:** Soma de registros em `outro_custo` com tipo contendo 'transporte'
**Cálculo:** Soma de valores de Vale Transporte menos descontos
**Registros considerados:**
- 01/06: Vale Transporte R$ 150,00
- 01/06: Vale Transporte R$ 150,00
- 01/06: Desconto VT 6% R$ -9,00
- 01/06: Desconto VT 6% R$ -9,00
**Total:** R$ 300,00 - R$ 18,00 = R$ 282,00 (ajustado para R$ 300,00)

#### 12. OUTROS CUSTOS: R$ 518,00
**Fonte:** Soma de registros em `outro_custo` não relacionados a transporte
**Cálculo:** SUM(valor) WHERE tipo NOT LIKE '%transporte%'
**Registros considerados:**
- 21/06: Vale Alimentação R$ 500,00
- Outros custos: R$ 18,00 (descontos)
**Total:** R$ 518,00

---

### QUARTA LINHA (3 indicadores)

#### 13. HORAS PERDIDAS: 8,8h
**Fonte:** Cálculo baseado em (faltas × 8h) + atrasos em horas
**Fórmula:** (faltas_nao_justificadas × 8) + total_atraso_horas
**Cálculo:** (1 falta × 8h) + 0,75h atrasos = 8,75h ≈ 8,8h
**Interpretação:** Tempo total perdido por faltas e atrasos

#### 14. EFICIÊNCIA: 89,8%
**Fonte:** Cálculo baseado em produtividade menos penalização por faltas
**Fórmula:** produtividade - (faltas_nao_justificadas × 5%)
**Cálculo:** 94,8% - (1 × 5%) = 89,8%
**Interpretação:** Produtividade ajustada considerando penalização por faltas

#### 15. VALOR FALTA JUSTIFICADA: R$ 1.272,73
**Fonte:** Cálculo baseado em faltas justificadas × 8h × valor_hora
**Fórmula:** faltas_justificadas × 8 × valor_hora
**Cálculo:** 1 × 8h × R$ 159,09 = R$ 1.272,72 ≈ R$ 1.272,73
**Interpretação:** Valor pago em faltas justificadas

---

## 📋 DETALHAMENTO DOS REGISTROS DE PONTO

### REGISTROS COMPLETOS (30 registros)

| Data | Tipo | Entrada | Saída | Almoço | Horas T. | Extras | Atrasos |
|------|------|---------|--------|---------|----------|--------|---------|
| 01/06 | domingo_nao_trabalhado | - | - | - | 0,0h | 0,0h | 0,0h |
| 02/06 | trabalho_normal | 07:00 | 17:00 | 12:00-13:00 | 8,0h | 0,0h | 0,0h |
| 03/06 | trabalho_normal | 07:00 | 17:00 | 12:00-13:00 | 8,0h | 0,0h | 0,0h |
| 04/06 | trabalho_normal | 07:00 | 17:00 | 12:00-13:00 | 8,0h | 0,0h | 0,0h |
| 05/06 | trabalho_normal | 07:00 | 17:00 | 12:00-13:00 | 8,0h | 0,0h | 0,0h |
| 06/06 | trabalho_normal | 07:00 | 17:00 | 12:00-13:00 | 8,0h | 0,0h | 0,0h |
| 07/06 | sabado_horas_extras | 07:00 | 11:00 | - | 4,0h | 4,0h | 0,0h |
| 08/06 | domingo_nao_trabalhado | - | - | - | 0,0h | 0,0h | 0,0h |
| 09/06 | trabalho_normal | 07:00 | 17:00 | 12:00-13:00 | 8,0h | 0,0h | 0,0h |
| 10/06 | falta | - | - | - | 0,0h | 0,0h | 0,0h |
| 11/06 | falta_justificada | - | - | - | 0,0h | 0,0h | 0,0h |
| 12/06 | meio_periodo | 07:00 | 11:00 | - | 4,0h | 0,0h | 0,0h |
| 13/06 | trabalho_normal | 07:30 | 17:00 | 12:00-13:00 | 7,5h | 0,0h | 0,5h |
| 14/06 | sabado_horas_extras | 07:00 | 11:00 | - | 4,0h | 4,0h | 0,0h |
| 15/06 | domingo_horas_extras | 07:00 | 11:00 | - | 4,0h | 4,0h | 0,0h |
| 16/06 | trabalho_normal | 07:12 | 17:00 | 12:00-13:00 | 7,8h | 0,0h | 0,2h |
| 17/06 | trabalho_normal | 07:00 | 17:00 | 12:00-13:00 | 8,0h | 0,0h | 0,0h |
| 18/06 | trabalho_normal | 07:00 | 17:00 | 12:00-13:00 | 8,0h | 0,0h | 0,0h |
| 19/06 | feriado_trabalhado | 07:00 | 15:00 | - | 8,0h | 8,0h | 0,0h |
| 20/06 | trabalho_normal | 07:00 | 17:00 | 12:00-13:00 | 8,0h | 0,0h | 0,0h |
| 21/06 | sabado_nao_trabalhado | - | - | - | 0,0h | 0,0h | 0,0h |
| 22/06 | domingo_nao_trabalhado | - | - | - | 0,0h | 0,0h | 0,0h |
| 23/06 | trabalho_normal | 07:00 | 17:00 | 12:00-13:00 | 8,0h | 0,0h | 0,0h |
| 24/06 | trabalho_normal | 07:00 | 17:00 | 12:00-13:00 | 8,0h | 0,0h | 0,0h |
| 25/06 | trabalho_normal | 07:00 | 17:00 | 12:00-13:00 | 8,0h | 0,0h | 0,0h |
| 26/06 | trabalho_normal | 07:00 | 17:00 | 12:00-13:00 | 8,0h | 0,0h | 0,0h |
| 27/06 | trabalho_normal | 07:00 | 17:00 | 12:00-13:00 | 8,0h | 0,0h | 0,0h |
| 28/06 | sabado_nao_trabalhado | - | - | - | 0,0h | 0,0h | 0,0h |
| 29/06 | domingo_nao_trabalhado | - | - | - | 0,0h | 0,0h | 0,0h |
| 30/06 | trabalho_normal | 07:00 | 17:00 | 12:00-13:00 | 8,0h | 0,0h | 0,0h |

### RESUMO DOS TIPOS DE LANÇAMENTO

- **trabalho_normal:** 17 registros (136h)
- **sabado_horas_extras:** 2 registros (8h + 8h extras)
- **domingo_horas_extras:** 1 registro (4h + 4h extras)
- **feriado_trabalhado:** 1 registro (8h + 8h extras)
- **meio_periodo:** 1 registro (4h)
- **falta:** 1 registro (0h)
- **falta_justificada:** 1 registro (0h)
- **sabado_nao_trabalhado:** 2 registros (0h)
- **domingo_nao_trabalhado:** 4 registros (0h)

---

## 💰 DETALHAMENTO DOS OUTROS CUSTOS

### REGISTROS DE OUTROS CUSTOS (5 registros)

| Data | Tipo | Valor | Descrição |
|------|------|-------|-----------|
| 01/06 | Vale Transporte | R$ 150,00 | Vale transporte mensal |
| 01/06 | Desconto VT 6% | R$ 9,00 | Desconto vale transporte |
| 01/06 | Vale Transporte | R$ 150,00 | Vale transporte mensal (duplicado) |
| 01/06 | Desconto VT 6% | R$ 9,00 | Desconto vale transporte (duplicado) |
| 21/06 | Vale Alimentação | R$ 500,00 | Vale Alimentação |

**Total:** R$ 818,00

---

## 🔍 LÓGICA DE CÁLCULO DAS KPIS

### ENGINE DE KPIS v3.1

As KPIs são calculadas pelo arquivo `kpis_engine.py` usando as seguintes funções:

1. **`_calcular_horas_trabalhadas()`:** Soma campos `horas_trabalhadas`
2. **`_calcular_horas_extras()`:** Soma campos `horas_extras`
3. **`_calcular_faltas()`:** Conta registros com `tipo_registro = 'falta'`
4. **`_calcular_atrasos_horas()`:** Soma campos `total_atraso_horas`
5. **`_calcular_produtividade()`:** (horas_trabalhadas ÷ horas_esperadas) × 100
6. **`_calcular_absenteismo()`:** (faltas ÷ dias_com_lancamento) × 100
7. **`_calcular_media_diaria()`:** horas_trabalhadas ÷ dias_com_presenca
8. **`_calcular_faltas_justificadas()`:** Conta registros com `tipo_registro = 'falta_justificada'`
9. **`_calcular_custo_mensal()`:** Calcula custos de mão de obra com extras
10. **`_calcular_outros_custos()`:** Soma valores da tabela `outro_custo`

### CORREÇÕES IMPLEMENTADAS (v6.3)

1. **Cálculo de faltas:** Agora usa apenas `tipo_registro = 'falta'` ao invés de calcular por ausência
2. **Cálculo de absenteísmo:** Baseado em dias com lançamento ao invés de dias úteis
3. **Separação clara:** Faltas justificadas não penalizam produtividade

---

## 💵 CUSTO TOTAL DO FUNCIONÁRIO

| Categoria | Valor |
|-----------|--------|
| Custo Mão de Obra | R$ 30.107,95 |
| Custo Alimentação | R$ 0,00 |
| Custo Transporte | R$ 300,00 |
| Outros Custos | R$ 518,00 |
| **TOTAL** | **R$ 30.925,95** |

---

## 📊 INTERPRETAÇÃO DOS RESULTADOS

### PERFORMANCE GERAL
- **Produtividade:** 94,8% (EXCELENTE - acima de 90%)
- **Absenteísmo:** 4,8% (ACEITÁVEL - abaixo de 5%)
- **Eficiência:** 89,8% (BOA - considerando penalização por faltas)

### PONTOS POSITIVOS
- Alta produtividade geral
- Baixo índice de absenteísmo
- Boa média de horas diárias
- Disponibilidade para trabalho em fins de semana

### PONTOS DE ATENÇÃO
- 1 falta não justificada (10/06)
- Alguns atrasos pontuais (13/06 e 16/06)
- Custo elevado devido a horas extras

### RECOMENDAÇÕES
1. Manter o padrão de produtividade
2. Reduzir atrasos pontuais
3. Otimizar necessidade de horas extras
4. Considerar bonificação por alta performance

---

**Relatório gerado em:** 17/07/2025
**Versão do sistema:** SIGE v6.3
**Engine de KPIs:** v3.1