# Relatório Completo - Cássio Viller Silva de Azevedo
## Mês Completo: Junho 2025

### Dados Básicos do Funcionário
- **Nome:** Cássio Viller Silva de Azevedo
- **Código:** F0006
- **Salário:** R$ 35.000,00
- **Salário/Hora:** R$ 159,09 (baseado em 220h/mês)
- **Período Analisado:** 01/06/2025 a 30/06/2025

### Resumo Executivo
O mês de junho/2025 foi completamente populado com todos os 30 dias do mês, demonstrando todos os tipos de lançamento possíveis do sistema SIGE v6.1, incluindo os novos tipos implementados:
- **Sábado Não Trabalhado**
- **Domingo Não Trabalhado**

### Análise do Período
- **Total de Dias no Mês:** 30 dias
- **Dias com Lançamento:** 30 dias (100% do mês)
- **Horas Esperadas:** 240h (30 dias × 8h)
- **Horas Trabalhadas:** 159,25h
- **Horas Extras:** 20h
- **Produtividade:** 66,4% (159,25h ÷ 240h)

### Detalhamento dos Registros por Tipo

#### 1. Trabalho Normal (17 registros)
- Dias úteis com horário padrão: 8h às 17h
- Intervalo de almoço: 12h às 13h
- Total de horas: 136h

#### 2. Sábados (4 registros)
- **Sábados Trabalhados (2):** 7 e 14 de junho
  - Horário: 8h às 12h (4h cada)
  - Total: 8h com 50% de horas extras
- **Sábados Folga (2):** 21 e 28 de junho
  - Marcação de folga

#### 3. Domingos (5 registros)
- **Domingo Trabalhado (1):** 15 de junho
  - Horário: 8h às 12h (4h)
  - Total: 4h com 100% de horas extras
- **Domingos Folga (4):** 1, 8, 22 e 29 de junho
  - Marcação de folga

#### 4. Feriado Trabalhado (1 registro)
- **19 de junho:** Corpus Christi
- Horário: 8h às 16h (8h)
- Total: 8h com 100% de horas extras

#### 5. Faltas (2 registros)
- **Falta Não Justificada:** 10 de junho
- **Falta Justificada:** 11 de junho (consulta médica)

#### 6. Meio Período (1 registro)
- **12 de junho:** Saída antecipada
- Horário: 8h às 12h (4h)

#### 7. Atrasos (2 registros)
- **13 de junho:** Atraso de 30 minutos (entrada 8h30)
- **16 de junho:** Saída antecipada 15 minutos (saída 16h45)
- **Total de Atrasos:** 0,75h

### Cálculos de KPIs Corrigidos (Engine v3.1)

#### KPIs Básicos
1. **Horas Trabalhadas:** 159,25h
2. **Horas Extras:** 20h
3. **Faltas:** 1 (apenas não justificadas)
4. **Atrasos:** 0,75h

#### KPIs Analíticos (CORRIGIDOS)
1. **Produtividade:** 66,4%
   - Fórmula: (159,25h ÷ 240h) × 100
   - Baseado em dias_com_lancamento (30 dias)
   
2. **Absenteísmo:** 3,3%
   - Fórmula: (1 falta ÷ 30 dias) × 100
   - Considera apenas faltas não justificadas
   
3. **Média Diária:** 5,3h
   - Fórmula: 159,25h ÷ 30 dias
   - Baseado em dias efetivos com lançamento
   
4. **Faltas Justificadas:** 1

#### KPIs Financeiros
1. **Custo Mão de Obra:** R$ 30.107,95
   - Horas normais: 159,25h × R$ 159,09 = R$ 25.322,07
   - Horas extras: 20h × R$ 159,09 × 1,5 = R$ 4.772,70
   - Adicional médio de 50% para horas extras
   
2. **Custo Alimentação:** R$ 0,00
   - Não há registros de alimentação no período
   
3. **Outros Custos:** R$ 818,00
   - Vale transporte e outros benefícios

#### KPIs Resumo
1. **Custo Total:** R$ 30.925,95
2. **Eficiência:** 64,1%
   - Produtividade ajustada por absenteísmo
   - Fórmula: 66,4% × (1 - 3,3%/100) = 64,1%
3. **Horas Perdidas:** 8,8h
   - Fórmula: (1 falta × 8h) + 0,75h atrasos = 8,75h

### Impacto das Correções no Engine v3.1

#### Antes da Correção (Dados Parciais)
- **Dias com Lançamento:** 14 dias
- **Produtividade:** 74,1%
- **Absenteísmo:** 7,1%
- **Média Diária:** 5,9h

#### Após Correção (Mês Completo)
- **Dias com Lançamento:** 30 dias
- **Produtividade:** 66,4%
- **Absenteísmo:** 3,3%
- **Média Diária:** 5,3h

### Análise dos Novos Tipos de Lançamento

#### Sábado Não Trabalhado
- **Propósito:** Marcar sábados de folga
- **Registros:** 2 (dias 21 e 28)
- **Impacto nos KPIs:** Conta como dia programado mas sem horas trabalhadas
- **Visualização:** Badge cinza "SÁB. FOLGA"

#### Domingo Não Trabalhado
- **Propósito:** Marcar domingos de folga
- **Registros:** 4 (dias 1, 8, 22 e 29)
- **Impacto nos KPIs:** Conta como dia programado mas sem horas trabalhadas
- **Visualização:** Badge claro "DOM. FOLGA"

### Validação do Sistema

#### Fórmulas Implementadas Corretamente
✅ **Produtividade:** (159,25h ÷ 240h) × 100 = 66,4%
✅ **Absenteísmo:** (1 falta ÷ 30 dias) × 100 = 3,3%
✅ **Média Diária:** 159,25h ÷ 30 dias = 5,3h
✅ **Eficiência:** 66,4% × (1 - 3,3%/100) = 64,1%

#### Benefícios da Correção
1. **Mais Justo:** Usa dias efetivamente programados
2. **Mais Preciso:** Considera todos os tipos de lançamento
3. **Mais Realista:** Reflete a realidade operacional

### Conclusão
O sistema SIGE v6.1 com Engine de KPIs v3.1 agora apresenta cálculos mais precisos e justos, considerando todos os tipos de lançamento possíveis. A implementação dos novos tipos "Sábado Não Trabalhado" e "Domingo Não Trabalhado" permite um controle mais completo e realista da jornada de trabalho.

O funcionário Cássio apresentou desempenho satisfatório no mês de junho/2025, com produtividade de 66,4% e baixo absenteísmo de 3,3%, demonstrando a eficácia do sistema de controle implementado.

---
**Data do Relatório:** 13 de Julho de 2025
**Sistema:** SIGE v6.1 - Engine KPIs v3.1
**Gerado por:** Sistema Automatizado de Relatórios