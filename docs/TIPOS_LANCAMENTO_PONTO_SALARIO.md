# Documentacao: Tipos de Lancamento de Ponto e Calculo de Salario
## SIGE v9.0 - Atualizado Janeiro/2026

---

## 1. PARAMETROS BASE DO CALCULO

| Parametro | Valor Padrao | Onde Configurar |
|-----------|--------------|-----------------|
| **Tolerancia de Atraso** | 10 minutos | Parametros Legais |
| **Hora de Trabalho Padrao** | Salario / 220h | Automatico |
| **DSR por Dia de Falta** | Salario / 30 | Automatico |

### Regra de Tolerancia (ATUALIZADA Jan/2026)

```
SE atraso/saida_antecipada <= 10 minutos:
    Desconto = R$ 0,00 (nao desconta nada)
    
SE atraso/saida_antecipada > 10 minutos:
    Desconto = TODO o tempo (nao apenas o excedente)
    
Exemplo:
- Atraso de 9 min  -> Desconto = 0 min
- Atraso de 10 min -> Desconto = 0 min  
- Atraso de 11 min -> Desconto = 11 min (nao 1 min!)
- Atraso de 15 min -> Desconto = 15 min (nao 5 min!)
```

---

## 2. TIPOS DE LANCAMENTO E IMPACTO NO SALARIO

### 2.1 TRABALHADO (Dia Normal)
**Codigo:** `trabalhado` ou `trabalho_normal`

| Campo | Impacto |
|-------|---------|
| Horas Trabalhadas | Contabiliza normalmente |
| Horas Extras | Se trabalhou MAIS que o contratual, gera HE 50% |
| Horas Falta | Se trabalhou MENOS que o contratual (alem tolerancia), desconta |

**Calculo:**
- Sem extras nem falta = Salario base mantido
- Extras = Valor hora x 1.5 x horas extras
- Falta parcial = Valor hora x horas faltantes

---

### 2.2 FALTA (Injustificada)
**Codigo:** `falta`

| Campo | Impacto |
|-------|---------|
| Horas Trabalhadas | 0 (zero) |
| Desconto de Horas | Valor hora x 8.8h (jornada completa) |
| Desconto DSR | Salario / 30 (perde 1 dia de DSR) |

**Calculo Exemplo (Salario R$ 3.500):**
```
Desconto horas: R$ 15,91 x 8,80h = R$ 140,00
Desconto DSR:   R$ 3.500 / 30 = R$ 116,67
TOTAL DESCONTO: R$ 256,67 por dia de falta
```

**Regra CLT:** Lei 605/49 - Falta injustificada = perde DSR proporcional

---

### 2.3 FALTA JUSTIFICADA
**Codigo:** `falta_justificada`

| Campo | Impacto |
|-------|---------|
| Horas Trabalhadas | 0 (zero) |
| Desconto de Horas | **NENHUM** |
| Desconto DSR | **NENHUM** |

**Calculo:** Nao afeta o salario. Dia e considerado como se tivesse trabalhado.

**Exemplos de Justificativas:**
- Casamento (3 dias)
- Falecimento de familiar (2-7 dias conforme grau)
- Doacao de sangue (1 dia/ano)
- Alistamento militar
- Acompanhamento medico de filho

---

### 2.4 ATESTADO MEDICO
**Codigo:** `atestado`

| Campo | Impacto |
|-------|---------|
| Horas Trabalhadas | 0 (zero) |
| Desconto de Horas | **NENHUM** |
| Desconto DSR | **NENHUM** |

**Calculo:** Identico a falta justificada. Nao afeta o salario.

**Regra:** Ate 15 dias = empresa paga. Acima 15 dias = INSS (auxilio-doenca)

---

### 2.5 FERIAS
**Codigo:** `ferias`

| Campo | Impacto |
|-------|---------|
| Horas Trabalhadas | 0 (zero) |
| Desconto | **NENHUM** |
| Adicional | 1/3 constitucional sobre dias de ferias |

**Calculo:** Tratado separadamente no modulo de ferias/decimo.

---

### 2.6 FERIADO (Nao Trabalhado)
**Codigo:** `feriado` ou `feriado_folga` ou `feriado_nao_trabalhado`

| Campo | Impacto |
|-------|---------|
| Horas Trabalhadas | 0 (zero) |
| Desconto | **NENHUM** |
| Adicional | **NENHUM** |

**Calculo:** Dia normal de repouso remunerado. Nao afeta o salario.

---

### 2.7 FERIADO TRABALHADO
**Codigo:** `feriado_trabalhado`

| Campo | Impacto |
|-------|---------|
| Horas Trabalhadas | Contabiliza como HE 100% |
| Hora Extra | Valor hora x 2.0 x horas trabalhadas |
| DSR | Proporcional sobre as horas extras |

**Calculo Exemplo (8h trabalhadas, R$ 15,91/hora):**
```
HE 100%: R$ 15,91 x 2.0 x 8h = R$ 254,56
DSR:     Proporcional sobre o valor das HE
```

---

### 2.8 SABADO FOLGA
**Codigo:** `sabado_folga`

| Campo | Impacto |
|-------|---------|
| Horas Trabalhadas | 0 (zero) |
| Desconto | **NENHUM** |

**Calculo:** Dia de descanso. Nao afeta o salario.

---

### 2.9 SABADO TRABALHADO (Horas Extras)
**Codigo:** `sabado_horas_extras` ou `sabado_trabalhado`

| Campo | Impacto |
|-------|---------|
| Horas Trabalhadas | Contabiliza como HE 50% |
| Hora Extra | Valor hora x 1.5 x horas trabalhadas |
| DSR | Proporcional sobre as horas extras |

**Calculo Exemplo (4h trabalhadas, R$ 15,91/hora):**
```
HE 50%: R$ 15,91 x 1.5 x 4h = R$ 95,46
DSR:    Proporcional sobre o valor das HE
```

**Regra:** Sabado pode ser 50% ou 100% dependendo do acordo coletivo.

---

### 2.10 DOMINGO FOLGA
**Codigo:** `domingo_folga`

| Campo | Impacto |
|-------|---------|
| Horas Trabalhadas | 0 (zero) |
| Desconto | **NENHUM** |

**Calculo:** Dia de DSR (Descanso Semanal Remunerado). Nao afeta o salario.

---

### 2.11 DOMINGO TRABALHADO (Horas Extras)
**Codigo:** `domingo_horas_extras` ou `domingo_trabalhado`

| Campo | Impacto |
|-------|---------|
| Horas Trabalhadas | Contabiliza como HE 100% |
| Hora Extra | Valor hora x 2.0 x horas trabalhadas |
| DSR | Proporcional sobre as horas extras |

**Calculo Exemplo (6h trabalhadas, R$ 15,91/hora):**
```
HE 100%: R$ 15,91 x 2.0 x 6h = R$ 190,92
DSR:     Proporcional sobre o valor das HE
```

---

## 3. FORMULAS DE CALCULO

### 3.1 Valor da Hora
```
Valor Hora = Salario Base / 220 horas
```

### 3.2 Horas Extras 50% (Dias Uteis e Sabados)
```
Valor HE 50% = Valor Hora x 1.5 x Quantidade de Horas
```

### 3.3 Horas Extras 100% (Domingos e Feriados)
```
Valor HE 100% = Valor Hora x 2.0 x Quantidade de Horas
```

### 3.4 DSR sobre Horas Extras
```
DSR = (Total Valor HE) / Dias Uteis x Domingos/Feriados do Mes
```

### 3.5 Desconto de Faltas (Horas)
```
Desconto = Valor Hora x Horas Faltadas
```

### 3.6 Desconto de DSR por Falta Injustificada
```
Desconto DSR = (Salario Base / 30) x Quantidade de Dias de Falta
```

---

## 4. SIMULACAO COMPLETA (Janeiro/2026)

### Dados do Funcionario
- Salario: R$ 3.500,00
- Jornada: 07:12 - 17:00 (8h48min = 8.80h/dia)
- Valor Hora: R$ 3.500 / 220 = R$ 15,91

### Eventos do Mes
| Dia | Tipo | Horas | HE 50% | HE 100% | Desconto |
|-----|------|-------|--------|---------|----------|
| 01 | Feriado | 0 | 0 | 0 | R$ 0 |
| 03 | Trabalhado (+2h) | 10.80h | 2.00h | 0 | R$ 0 |
| 04 | Sabado Trabalhado | 4.00h | 4.00h | 0 | R$ 0 |
| 06 | **FALTA** | 0 | 0 | 0 | **R$ 256,67** |
| 07 | Falta Justificada | 0 | 0 | 0 | R$ 0 |
| 08 | Atestado | 0 | 0 | 0 | R$ 0 |
| 09 | Atraso 15min | 8.55h | 0 | 0 | **R$ 3,98** |
| 10 | Saida 1h antes | 7.80h | 0 | 0 | **R$ 15,91** |
| 13 | Feriado Trabalhado | 8.80h | 0 | 8.80h | R$ 0 |
| 14 | Domingo Trabalhado | 6.00h | 0 | 6.00h | R$ 0 |

### Calculo Final

| Descricao | Valor |
|-----------|-------|
| Salario Base | R$ 3.500,00 |
| (+) HE 50% (6h x R$15,91 x 1.5) | R$ 143,18 |
| (+) HE 100% (14.8h x R$15,91 x 2.0) | R$ 470,91 |
| (+) DSR sobre Extras | R$ 111,65 |
| (-) Desconto DSR Falta | R$ 116,67 |
| (-) Desconto Horas (falta+atrasos) | R$ 159,89 |
| **SALARIO LIQUIDO (antes INSS/IRRF)** | **R$ 3.949,18** |

---

## 5. RESUMO DAS REGRAS ATUALIZADAS

1. **Tolerancia:** Se ultrapassar 10 min, desconta TUDO (nao so o excedente)
2. **Falta Injustificada:** Desconta horas + DSR (salario/30)
3. **Falta Justificada/Atestado:** NAO desconta nada
4. **HE 50%:** Dias uteis + Sabados
5. **HE 100%:** Domingos + Feriados
6. **DSR sobre Extras:** Calculado proporcionalmente aos dias trabalhados

---

*Documento gerado automaticamente pelo SIGE v9.0*
*Atualizado em: Janeiro/2026*
