# COMO OS CÁLCULOS FUNCIONAM - EXEMPLO PRÁTICO DO JOÃO (F0099)

Este documento mostra **exatamente** como cada tipo de lançamento do funcionário João Silva dos Santos (F0099) é lido e usado nos cálculos dos KPIs.

---

## 1. DADOS DO FUNCIONÁRIO

**Nome:** João Silva dos Santos  
**Código:** F0099  
**Salário:** R$ 2.500,00  
**Salário/hora:** R$ 2.500,00 ÷ 220h = R$ 11,36/hora  
**Período:** Junho/2025 (20 dias úteis)  

---

## 2. ANÁLISE DETALHADA DOS REGISTROS DE PONTO

### 📊 REGISTRO POR REGISTRO - COMO CADA UM AFETA OS CÁLCULOS

#### 🔸 **03/06/2025 - TRABALHO NORMAL**
```json
{
    "tipo_registro": "trabalho_normal",
    "hora_entrada": "08:00",
    "hora_saida": "17:00",
    "hora_almoco_saida": "12:00",
    "hora_almoco_retorno": "13:00",
    "horas_trabalhadas": 8.0,
    "horas_extras": 0.0,
    "total_atraso_minutos": 0
}
```

**📈 Impacto nos KPIs:**
- ✅ **Horas trabalhadas:** +8.0h
- ✅ **Horas extras:** +0.0h
- ✅ **Faltas:** +0
- ✅ **Atrasos:** +0h
- ✅ **Custo mão de obra:** +R$ 90,91 (8h × R$ 11,36)

---

#### 🔸 **04/06/2025 - TRABALHO COM ATRASO**
```json
{
    "tipo_registro": "trabalho_normal",
    "hora_entrada": "08:30",        // 30 min atraso
    "hora_saida": "17:00",
    "horas_trabalhadas": 7.5,
    "horas_extras": 0.0,
    "total_atraso_minutos": 30
}
```

**📈 Impacto nos KPIs:**
- ✅ **Horas trabalhadas:** +7.5h
- ✅ **Horas extras:** +0.0h
- ✅ **Faltas:** +0
- ✅ **Atrasos:** +0.5h (30min ÷ 60)
- ✅ **Horas perdidas:** +0.5h
- ✅ **Custo mão de obra:** +R$ 85,23 (7.5h × R$ 11,36)

**💡 Lógica:** Sistema registra o atraso e reduz as horas trabalhadas

---

#### 🔸 **05/06/2025 - SAÍDA ANTECIPADA**
```json
{
    "tipo_registro": "trabalho_normal",
    "hora_entrada": "08:00",
    "hora_saida": "16:00",          // 1h mais cedo
    "horas_trabalhadas": 7.0,
    "horas_extras": 0.0,
    "total_atraso_minutos": 60
}
```

**📈 Impacto nos KPIs:**
- ✅ **Horas trabalhadas:** +7.0h
- ✅ **Atrasos:** +1.0h (60min ÷ 60)
- ✅ **Horas perdidas:** +1.0h
- ✅ **Custo mão de obra:** +R$ 79,55 (7h × R$ 11,36)

**💡 Lógica:** Saída antecipada conta como atraso

---

#### 🔸 **06/06/2025 - ATRASO ENTRADA + SAÍDA ANTECIPADA**
```json
{
    "tipo_registro": "trabalho_normal",
    "hora_entrada": "08:15",        // 15 min atraso
    "hora_saida": "16:30",          // 30 min mais cedo
    "horas_trabalhadas": 7.25,
    "horas_extras": 0.0,
    "total_atraso_minutos": 45      // 15 + 30
}
```

**📈 Impacto nos KPIs:**
- ✅ **Horas trabalhadas:** +7.25h
- ✅ **Atrasos:** +0.75h (45min ÷ 60)
- ✅ **Horas perdidas:** +0.75h
- ✅ **Custo mão de obra:** +R$ 82,39 (7.25h × R$ 11,36)

**💡 Lógica:** Sistema soma atrasos de entrada e saída

---

#### 🔸 **07/06/2025 - SÁBADO COM HORAS EXTRAS**
```json
{
    "tipo_registro": "sabado_horas_extras",
    "hora_entrada": "08:00",
    "hora_saida": "12:00",
    "horas_trabalhadas": 4.0,
    "horas_extras": 4.0,            // TODAS as horas são extras
    "percentual_extras": 50,
    "total_atraso_minutos": 0
}
```

**📈 Impacto nos KPIs:**
- ✅ **Horas trabalhadas:** +4.0h
- ✅ **Horas extras:** +4.0h
- ✅ **Custo mão de obra:** +R$ 45,45 (4h × R$ 11,36)
- ✅ **Custo horas extras:** +R$ 22,73 (4h × R$ 11,36 × 0.5)

**💡 Lógica:** No sábado, todas as horas são extras com 50% adicional

---

#### 🔸 **08/06/2025 - DOMINGO COM HORAS EXTRAS**
```json
{
    "tipo_registro": "domingo_horas_extras",
    "hora_entrada": "08:00",
    "hora_saida": "12:00",
    "horas_trabalhadas": 4.0,
    "horas_extras": 4.0,            // TODAS as horas são extras
    "percentual_extras": 100,
    "total_atraso_minutos": 0
}
```

**📈 Impacto nos KPIs:**
- ✅ **Horas trabalhadas:** +4.0h
- ✅ **Horas extras:** +4.0h
- ✅ **Custo mão de obra:** +R$ 45,45 (4h × R$ 11,36)
- ✅ **Custo horas extras:** +R$ 45,45 (4h × R$ 11,36 × 1.0)

**💡 Lógica:** No domingo, todas as horas são extras com 100% adicional

---

#### 🔸 **10/06/2025 - FALTA NÃO JUSTIFICADA**
```json
{
    "tipo_registro": "falta",
    "data": "2025-06-10",
    "observacoes": "Falta não justificada"
}
```

**📈 Impacto nos KPIs:**
- ✅ **Horas trabalhadas:** +0h
- ✅ **Faltas:** +1
- ✅ **Horas perdidas:** +8h (1 falta × 8h)
- ✅ **Absenteísmo:** +5% (1 ÷ 20 dias úteis)
- ✅ **Produtividade:** -5% (reduz horas trabalhadas)

**💡 Lógica:** Falta não justificada conta como 8 horas perdidas

---

#### 🔸 **11/06/2025 - FALTA JUSTIFICADA**
```json
{
    "tipo_registro": "falta_justificada",
    "data": "2025-06-11",
    "observacoes": "Falta justificada - consulta médica"
}
```

**📈 Impacto nos KPIs:**
- ✅ **Horas trabalhadas:** +0h
- ✅ **Faltas:** +0 (não conta como falta para absenteísmo)
- ✅ **Horas perdidas:** +0h (não conta como tempo perdido)
- ✅ **Absenteísmo:** +0% (falta justificada não afeta)

**💡 Lógica:** Falta justificada não penaliza o funcionário

---

#### 🔸 **12/06/2025 - MEIO PERÍODO**
```json
{
    "tipo_registro": "meio_periodo",
    "hora_entrada": "08:00",
    "hora_saida": "12:00",
    "horas_trabalhadas": 4.0,
    "horas_extras": 0.0,
    "total_atraso_minutos": 0
}
```

**📈 Impacto nos KPIs:**
- ✅ **Horas trabalhadas:** +4.0h
- ✅ **Horas extras:** +0.0h
- ✅ **Custo mão de obra:** +R$ 45,45 (4h × R$ 11,36)

**💡 Lógica:** Meio período conta como trabalho normal, só com menos horas

---

#### 🔸 **13/06/2025 - TRABALHO SEM INTERVALO**
```json
{
    "tipo_registro": "trabalho_normal",
    "hora_entrada": "08:00",
    "hora_saida": "16:00",
    "hora_almoco_saida": null,      // Sem almoço
    "hora_almoco_retorno": null,
    "horas_trabalhadas": 8.0,
    "horas_extras": 0.0,
    "total_atraso_minutos": 0
}
```

**📈 Impacto nos KPIs:**
- ✅ **Horas trabalhadas:** +8.0h
- ✅ **Custo mão de obra:** +R$ 90,91 (8h × R$ 11,36)

**💡 Lógica:** Trabalho contínuo sem intervalo de almoço

---

#### 🔸 **16/06/2025 - TRABALHO COM HORAS EXTRAS**
```json
{
    "tipo_registro": "trabalho_normal",
    "hora_entrada": "08:00",
    "hora_saida": "19:00",          // 2h extras
    "horas_trabalhadas": 8.0,
    "horas_extras": 2.0,
    "percentual_extras": 50,
    "total_atraso_minutos": 0
}
```

**📈 Impacto nos KPIs:**
- ✅ **Horas trabalhadas:** +8.0h
- ✅ **Horas extras:** +2.0h
- ✅ **Custo mão de obra:** +R$ 90,91 (8h × R$ 11,36)
- ✅ **Custo horas extras:** +R$ 11,36 (2h × R$ 11,36 × 0.5)

**💡 Lógica:** Horas extras em dia normal com 50% adicional

---

#### 🔸 **19/06/2025 - FERIADO TRABALHADO**
```json
{
    "tipo_registro": "feriado_trabalhado",
    "hora_entrada": "08:00",
    "hora_saida": "17:00",
    "horas_trabalhadas": 8.0,
    "horas_extras": 8.0,            // TODAS as horas são extras
    "percentual_extras": 100,
    "total_atraso_minutos": 0
}
```

**📈 Impacto nos KPIs:**
- ✅ **Horas trabalhadas:** +8.0h
- ✅ **Horas extras:** +8.0h
- ✅ **Custo mão de obra:** +R$ 90,91 (8h × R$ 11,36)
- ✅ **Custo horas extras:** +R$ 90,91 (8h × R$ 11,36 × 1.0)

**💡 Lógica:** Feriado trabalhado = todas as horas são extras com 100% adicional

---

## 3. CÁLCULOS DOS KPIs FINAIS

### 📊 SOMATÓRIA DOS REGISTROS

#### A. HORAS TRABALHADAS
```
03/06: 8.0h   + 04/06: 7.5h   + 05/06: 7.0h   + 06/06: 7.25h  +
07/06: 4.0h   + 08/06: 4.0h   + 09/06: 8.0h   + 10/06: 0.0h   +
11/06: 0.0h   + 12/06: 4.0h   + 13/06: 8.0h   + 16/06: 8.0h   +
19/06: 8.0h   + 20/06: 8.0h
= 88.75h
```

#### B. HORAS EXTRAS
```
Sábado (07/06): 4.0h     + Domingo (08/06): 4.0h     +
Dia normal (16/06): 2.0h + Feriado (19/06): 8.0h
= 18.0h
```

#### C. FALTAS
```
Falta não justificada (10/06): 1
Falta justificada (11/06): 0 (não conta)
= 1 falta
```

#### D. ATRASOS
```
04/06: 30min + 05/06: 60min + 06/06: 45min
= 135 minutos = 2.25h
```

#### E. HORAS PERDIDAS
```
Faltas: 1 × 8h = 8h
Atrasos: 2.25h
= 8h + 2.25h = 10.25h
```

### 💰 CÁLCULOS DE CUSTOS

#### A. CUSTO MÃO DE OBRA NORMAL
```
88.75h × R$ 11,36 = R$ 1.009,10
```

#### B. CUSTO HORAS EXTRAS
```
Sábado: 4h × R$ 11,36 × 1.5 = R$ 68,16
Domingo: 4h × R$ 11,36 × 2.0 = R$ 90,88
Dia normal: 2h × R$ 11,36 × 1.5 = R$ 34,08
Feriado: 8h × R$ 11,36 × 2.0 = R$ 181,76
= R$ 374,88
```

#### C. CUSTO ALIMENTAÇÃO
```
10 registros = R$ 171,00
```

#### D. OUTROS CUSTOS
```
6 registros = R$ 825,80
```

### 📈 INDICADORES DE PERFORMANCE

#### A. PRODUTIVIDADE
```
Horas trabalhadas: 88.75h
Horas esperadas: 20 dias × 8h = 160h
Produtividade: (88.75 ÷ 160) × 100 = 55.5%
```

#### B. ABSENTEÍSMO
```
Faltas: 1
Dias úteis: 20
Absenteísmo: (1 ÷ 20) × 100 = 5.0%
```

---

## 4. RESUMO FINAL DOS CÁLCULOS

### 📋 VALORES FINAIS DOS KPIs

| KPI | Cálculo | Valor |
|-----|---------|-------|
| **Horas trabalhadas** | Soma de todas as horas | 88.75h |
| **Horas extras** | Soma de horas extras | 18.0h |
| **Faltas** | Contagem de faltas não justificadas | 1 |
| **Atrasos** | Soma de atrasos ÷ 60 | 2.25h |
| **Horas perdidas** | (1 × 8) + 2.25 | 10.25h |
| **Custo mão de obra** | 88.75h × R$ 11,36 | R$ 1.009,10 |
| **Custo horas extras** | Cálculo por percentual | R$ 374,88 |
| **Custo alimentação** | Soma dos valores | R$ 171,00 |
| **Outros custos** | Soma dos valores | R$ 825,80 |
| **Produtividade** | (88.75 ÷ 160) × 100 | 55.5% |
| **Absenteísmo** | (1 ÷ 20) × 100 | 5.0% |

### 💵 CUSTO TOTAL DO FUNCIONÁRIO
```
Custo mão de obra: R$ 1.009,10
Custo horas extras: R$ 374,88
Custo alimentação: R$ 171,00
Outros custos: R$ 825,80
─────────────────────────────
TOTAL: R$ 2.380,78
```

---

## 5. CONCLUSÕES

### ✅ COMO O SISTEMA PROCESSA CADA TIPO

1. **Trabalho Normal:** Lê horários, calcula horas trabalhadas, detecta atrasos
2. **Sábado/Domingo:** Considera todas as horas como extras com percentual específico
3. **Feriado Trabalhado:** Aplica 100% de adicional em todas as horas
4. **Faltas:** Diferencia justificadas (não penaliza) de não justificadas (penaliza)
5. **Atrasos:** Soma entrada tardia e saída antecipada
6. **Meio Período:** Trata como trabalho normal com menos horas

### 🎯 REGRAS FUNDAMENTAIS

- **Cada tipo de registro** tem sua lógica específica de processamento
- **Percentuais de extras** são aplicados conforme o tipo (sábado 50%, domingo 100%, feriado 100%)
- **Faltas justificadas** não afetam KPIs negativamente
- **Atrasos** são convertidos de minutos para horas
- **Custos** são calculados separadamente para cada categoria

**Este exemplo mostra exatamente como o sistema SIGE v5.0 processa cada tipo de lançamento na prática!**