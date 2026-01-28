# Detalhamento dos 41 Testes de Calculo de Salario
## SIGE v9.0 - Janeiro/2026

---

## Parametros Base Utilizados nos Testes

| Parametro | Valor | Formula |
|-----------|-------|---------|
| Salario Base | R$ 3.500,00 | Definido |
| Horas/Mes | 220 horas | CLT padrao |
| Valor Hora | R$ 15,91 | 3.500 / 220 |
| Jornada Diaria | 8,80 horas | 8h48min |
| Tolerancia | 10 minutos | Parametro legal |

---

## ARQUIVO 1: test_calculo_tolerancia.py (12 Testes)

### Classe: TestToleranciaAtraso (7 Testes)

#### Teste 1: test_atraso_dentro_tolerancia_nao_desconta
```
Entrada: Atraso = 5 minutos
Tolerancia = 10 minutos
Calculo: 5 <= 10? SIM
Resultado Esperado: Desconto = R$ 0,00
Status: PASSOU
```

#### Teste 2: test_atraso_exatamente_tolerancia_nao_desconta
```
Entrada: Atraso = 10 minutos
Tolerancia = 10 minutos
Calculo: 10 <= 10? SIM
Resultado Esperado: Desconto = R$ 0,00
Status: PASSOU
```

#### Teste 3: test_atraso_1_minuto_alem_desconta_tudo
```
Entrada: Atraso = 11 minutos
Tolerancia = 10 minutos
Calculo: 11 > 10? SIM -> Desconta TUDO (11 min)
         11 min = 0.1833h
         Desconto = 0.1833h x R$ 15,91 = R$ 2,92
Resultado Esperado: R$ 2,92
Status: PASSOU
```

#### Teste 4: test_atraso_15_minutos_desconta_tudo
```
Entrada: Atraso = 15 minutos
Tolerancia = 10 minutos
Calculo: 15 > 10? SIM -> Desconta TUDO (15 min)
         15 min = 0.25h
         Desconto = 0.25h x R$ 15,91 = R$ 3,98
Resultado Esperado: R$ 3,98
Status: PASSOU
```

#### Teste 5: test_atraso_30_minutos_desconta_tudo
```
Entrada: Atraso = 30 minutos
Tolerancia = 10 minutos
Calculo: 30 > 10? SIM -> Desconta TUDO (30 min)
         30 min = 0.50h
         Desconto = 0.50h x R$ 15,91 = R$ 7,96
Resultado Esperado: R$ 7,96
Status: PASSOU
```

#### Teste 6: test_atraso_60_minutos_desconta_tudo
```
Entrada: Atraso = 60 minutos
Tolerancia = 10 minutos
Calculo: 60 > 10? SIM -> Desconta TUDO (60 min)
         60 min = 1.00h
         Desconto = 1.00h x R$ 15,91 = R$ 15,91
Resultado Esperado: R$ 15,91
Status: PASSOU
```

#### Teste 7: test_sem_atraso_nao_desconta
```
Entrada: Atraso = 0 minutos
Calculo: 0 <= 10? SIM
Resultado Esperado: Desconto = R$ 0,00
Status: PASSOU
```

---

### Classe: TestSaidaAntecipada (5 Testes)

#### Teste 8: test_saida_5_minutos_antes_nao_desconta
```
Entrada: Saida antecipada = 5 minutos
Tolerancia = 10 minutos
Calculo: 5 <= 10? SIM
Resultado Esperado: Desconto = R$ 0,00
Status: PASSOU
```

#### Teste 9: test_saida_10_minutos_antes_nao_desconta
```
Entrada: Saida antecipada = 10 minutos
Tolerancia = 10 minutos
Calculo: 10 <= 10? SIM
Resultado Esperado: Desconto = R$ 0,00
Status: PASSOU
```

#### Teste 10: test_saida_11_minutos_antes_desconta_tudo
```
Entrada: Saida antecipada = 11 minutos
Tolerancia = 10 minutos
Calculo: 11 > 10? SIM -> Desconta TUDO (11 min)
         11 min = 0.1833h
         Desconto = 0.1833h x R$ 15,91 = R$ 2,92
Resultado Esperado: R$ 2,92
Status: PASSOU
```

#### Teste 11: test_saida_30_minutos_antes_desconta_tudo
```
Entrada: Saida antecipada = 30 minutos
Tolerancia = 10 minutos
Calculo: 30 > 10? SIM -> Desconta TUDO (30 min)
         30 min = 0.50h
         Desconto = 0.50h x R$ 15,91 = R$ 7,96
Resultado Esperado: R$ 7,96
Status: PASSOU
```

#### Teste 12: test_saida_60_minutos_antes_desconta_tudo
```
Entrada: Saida antecipada = 60 minutos
Tolerancia = 10 minutos
Calculo: 60 > 10? SIM -> Desconta TUDO (60 min)
         60 min = 1.00h
         Desconto = 1.00h x R$ 15,91 = R$ 15,91
Resultado Esperado: R$ 15,91
Status: PASSOU
```

---

## ARQUIVO 2: test_regras_salario_completo.py (29 Testes)

### Classe: TestValorHora (1 Teste)

#### Teste 13: test_valor_hora_correto
```
Entrada: Salario = R$ 3.500,00
         Horas/Mes = 220
Calculo: 3500 / 220 = 15,909090...
         Arredondado = 15,91
Resultado Esperado: R$ 15,91
Status: PASSOU
```

---

### Classe: TestToleranciaAtraso (7 Testes)

#### Teste 14: test_atraso_5_minutos_nao_desconta
```
Entrada: Atraso = 5 minutos
Calculo: 5 <= 10? SIM
Resultado Esperado: Horas descontadas = 0
Status: PASSOU
```

#### Teste 15: test_atraso_9_minutos_nao_desconta
```
Entrada: Atraso = 9 minutos
Calculo: 9 <= 10? SIM
Resultado Esperado: Horas descontadas = 0
Status: PASSOU
```

#### Teste 16: test_atraso_10_minutos_nao_desconta
```
Entrada: Atraso = 10 minutos
Calculo: 10 <= 10? SIM
Resultado Esperado: Horas descontadas = 0
Status: PASSOU
```

#### Teste 17: test_atraso_11_minutos_desconta_tudo
```
Entrada: Atraso = 11 minutos
Calculo: 11 > 10? SIM -> Retorna 11 minutos
         11 / 60 = 0.1833h
Resultado Esperado: 0.1833 horas
Status: PASSOU
```

#### Teste 18: test_atraso_15_minutos_desconta_tudo
```
Entrada: Atraso = 15 minutos
Calculo: 15 > 10? SIM -> Retorna 15 minutos
         15 / 60 = 0.25h
Resultado Esperado: 0.25 horas
Status: PASSOU
```

#### Teste 19: test_saida_9_minutos_antes_nao_desconta
```
Entrada: Saida antecipada = 9 minutos (valor -9)
Calculo: |-9| = 9 <= 10? SIM
Resultado Esperado: Horas descontadas = 0
Status: PASSOU
```

#### Teste 20: test_saida_60_minutos_antes_desconta_tudo
```
Entrada: Saida antecipada = 60 minutos (valor -60)
Calculo: |-60| = 60 > 10? SIM -> Retorna 60 minutos
         60 / 60 = 1.00h
Resultado Esperado: 1.00 hora
Status: PASSOU
```

---

### Classe: TestFaltaInjustificada (3 Testes)

#### Teste 21: test_desconto_horas_falta_completa
```
Entrada: Falta = 1 dia completo (8.80h)
Calculo: 8.80h x R$ 15,91 = R$ 140,01
Resultado Esperado: ~R$ 140,00
Status: PASSOU
```

#### Teste 22: test_desconto_dsr_por_falta
```
Entrada: Faltas = 1 dia
Calculo: Salario / 30 = 3500 / 30 = R$ 116,67
Resultado Esperado: R$ 116,67
Status: PASSOU
```

#### Teste 23: test_total_desconto_1_falta
```
Entrada: Falta = 1 dia injustificado
Calculo: 
  Desconto Horas = 8.80h x R$ 15,91 = R$ 140,01
  Desconto DSR = R$ 3.500 / 30 = R$ 116,67
  TOTAL = R$ 140,01 + R$ 116,67 = R$ 256,68
Resultado Esperado: ~R$ 256,67
Status: PASSOU
```

---

### Classe: TestFaltaJustificadaEAtestado (4 Testes)

#### Teste 24: test_falta_justificada_sem_desconto_horas
```
Entrada: Tipo = Falta Justificada
Regra: Falta justificada NAO desconta horas
Resultado Esperado: Desconto = R$ 0,00
Status: PASSOU
```

#### Teste 25: test_falta_justificada_sem_desconto_dsr
```
Entrada: Tipo = Falta Justificada
Regra: Falta justificada NAO perde DSR
Resultado Esperado: Desconto DSR = R$ 0,00
Status: PASSOU
```

#### Teste 26: test_atestado_sem_desconto_horas
```
Entrada: Tipo = Atestado Medico
Regra: Atestado NAO desconta horas
Resultado Esperado: Desconto = R$ 0,00
Status: PASSOU
```

#### Teste 27: test_atestado_sem_desconto_dsr
```
Entrada: Tipo = Atestado Medico
Regra: Atestado NAO perde DSR
Resultado Esperado: Desconto DSR = R$ 0,00
Status: PASSOU
```

---

### Classe: TestHorasExtras50 (4 Testes)

#### Teste 28: test_calculo_he_50_basico
```
Entrada: Horas Extras = 1 hora (dia util ou sabado)
Calculo: R$ 15,91 x 1.5 x 1h = R$ 23,87
Resultado Esperado: R$ 23,87
Status: PASSOU
```

#### Teste 29: test_calculo_he_50_2_horas
```
Entrada: Horas Extras = 2 horas (dia 03 da simulacao)
Calculo: R$ 15,91 x 1.5 x 2h = R$ 47,73
Resultado Esperado: R$ 47,73
Status: PASSOU
```

#### Teste 30: test_calculo_he_50_4_horas_sabado
```
Entrada: Horas Extras = 4 horas (sabado dia 04)
Calculo: R$ 15,91 x 1.5 x 4h = R$ 95,46
Resultado Esperado: R$ 95,46
Status: PASSOU
```

#### Teste 31: test_total_he_50_simulacao
```
Entrada: Total HE 50% = 6 horas (2h + 4h)
Calculo: R$ 15,91 x 1.5 x 6h = R$ 143,19
Resultado Esperado: ~R$ 143,18
Status: PASSOU
```

---

### Classe: TestHorasExtras100 (4 Testes)

#### Teste 32: test_calculo_he_100_basico
```
Entrada: Horas Extras = 1 hora (domingo ou feriado)
Calculo: R$ 15,91 x 2.0 x 1h = R$ 31,82
Resultado Esperado: R$ 31,82
Status: PASSOU
```

#### Teste 33: test_calculo_he_100_feriado_trabalhado
```
Entrada: Horas Extras = 8.80 horas (feriado dia 13)
Calculo: R$ 15,91 x 2.0 x 8.80h = R$ 280,02
Resultado Esperado: ~R$ 280,00
Status: PASSOU
```

#### Teste 34: test_calculo_he_100_domingo_trabalhado
```
Entrada: Horas Extras = 6 horas (domingo dia 14)
Calculo: R$ 15,91 x 2.0 x 6h = R$ 190,92
Resultado Esperado: R$ 190,92
Status: PASSOU
```

#### Teste 35: test_total_he_100_simulacao
```
Entrada: Total HE 100% = 14.80 horas (8.80h + 6h)
Calculo: R$ 15,91 x 2.0 x 14.80h = R$ 470,94
Resultado Esperado: ~R$ 470,91
Status: PASSOU
```

---

### Classe: TestDSRSobreExtras (1 Teste)

#### Teste 36: test_dsr_formula_basica
```
Entrada: 
  Total HE = R$ 614,09 (143,18 + 470,91)
  Dias Uteis = 22
  Domingos/Feriados = 4

Calculo: 
  DSR = (Total HE / Dias Uteis) x Domingos/Feriados
  DSR = (614,09 / 22) x 4
  DSR = 27,91 x 4
  DSR = R$ 111,64

Resultado Esperado: ~R$ 111,65
Status: PASSOU
```

---

### Classe: TestSimulacaoCompleta (2 Testes)

#### Teste 37: test_simulacao_janeiro_2026
```
SIMULACAO COMPLETA DO MES

Dados Base:
  Salario: R$ 3.500,00
  Valor Hora: R$ 15,91

PROVENTOS:
+---------------------------+------------+---------------------------+
| Item                      | Valor      | Calculo                   |
+---------------------------+------------+---------------------------+
| Salario Base              | R$ 3.500,00| Fixo                      |
| HE 50% (6h)               | R$   143,18| 15,91 x 1.5 x 6h          |
| HE 100% (14.80h)          | R$   470,91| 15,91 x 2.0 x 14.80h      |
| DSR sobre Extras          | R$   111,65| 614,09 / 22 x 4           |
+---------------------------+------------+---------------------------+
| TOTAL PROVENTOS           | R$ 4.225,74|                           |
+---------------------------+------------+---------------------------+

DESCONTOS:
+---------------------------+------------+---------------------------+
| Item                      | Valor      | Calculo                   |
+---------------------------+------------+---------------------------+
| Desconto DSR Falta (1 dia)| R$   116,67| 3.500 / 30                |
| Desconto Horas            | R$   159,89| Detalhado abaixo          |
+---------------------------+------------+---------------------------+
| TOTAL DESCONTOS           | R$   276,56|                           |
+---------------------------+------------+---------------------------+

Detalhamento Desconto Horas:
  - Dia 06 (falta): 8.80h x R$ 15,91 = R$ 140,00
  - Dia 09 (atraso 15min): 0.25h x R$ 15,91 = R$ 3,98
  - Dia 10 (saida 1h antes): 1.00h x R$ 15,91 = R$ 15,91
  - TOTAL: R$ 159,89

CALCULO FINAL:
  Proventos:  R$ 4.225,74
  Descontos:  R$   276,56
  ----------------------
  LIQUIDO:    R$ 3.949,18

Resultado Esperado: R$ 3.949,18
Status: PASSOU
```

#### Teste 38: test_valores_intermediarios_simulacao
```
Validacao dos valores intermediarios:
  - HE 50% (6h) = R$ 143,18 ... OK
  - HE 100% (14.80h) = R$ 470,91 ... OK
  - Desconto DSR (1 falta) = R$ 116,67 ... OK

Status: PASSOU
```

---

### Classe: TestCasosEspeciais (3 Testes)

#### Teste 39: test_mes_sem_horas_extras
```
Entrada: Mes sem nenhuma hora extra
Calculo: 
  Salario = R$ 3.500,00
  HE 50% = R$ 0,00
  HE 100% = R$ 0,00
  Total = R$ 3.500,00

Resultado Esperado: R$ 3.500,00
Status: PASSOU
```

#### Teste 40: test_mes_sem_faltas
```
Entrada: Mes sem nenhuma falta
Calculo:
  Desconto Horas = R$ 0,00
  Desconto DSR = R$ 0,00
  Total Descontos = R$ 0,00

Resultado Esperado: R$ 0,00 em descontos
Status: PASSOU
```

#### Teste 41: test_multiplas_faltas
```
Entrada: 3 faltas injustificadas
Calculo:
  Desconto DSR = (R$ 3.500 / 30) x 3
  Desconto DSR = R$ 116,67 x 3
  Desconto DSR = R$ 350,01

Resultado Esperado: ~R$ 350,00
Status: PASSOU
```

---

## RESUMO GERAL DOS 41 TESTES

| Categoria | Qtd Testes | Cobertura |
|-----------|------------|-----------|
| Valor Hora | 1 | Formula basica |
| Tolerancia Atraso | 14 | 0-60 min, entrada e saida |
| Falta Injustificada | 3 | Horas + DSR + Total |
| Falta Justificada | 2 | Sem desconto horas/DSR |
| Atestado Medico | 2 | Sem desconto horas/DSR |
| Horas Extras 50% | 4 | 1h, 2h, 4h, 6h total |
| Horas Extras 100% | 4 | 1h, 8.8h, 6h, 14.8h total |
| DSR sobre Extras | 1 | Formula completa |
| Simulacao Completa | 2 | Mes inteiro + intermediarios |
| Casos Especiais | 3 | Sem HE, sem faltas, multiplas faltas |
| **TOTAL** | **41** | **100% Aprovados** |

---

## FORMULAS UTILIZADAS

### 1. Valor da Hora
```
Valor_Hora = Salario_Base / 220
Exemplo: 3500 / 220 = R$ 15,91
```

### 2. Tolerancia
```
SE diferenca <= 10 minutos:
    Desconto = 0
SENAO:
    Desconto = diferenca (em horas) x Valor_Hora
```

### 3. Horas Extras 50%
```
HE_50 = Valor_Hora x 1.5 x Quantidade_Horas
```

### 4. Horas Extras 100%
```
HE_100 = Valor_Hora x 2.0 x Quantidade_Horas
```

### 5. DSR sobre Extras
```
DSR = (Total_HE / Dias_Uteis) x Domingos_Feriados
```

### 6. Desconto por Falta (Horas)
```
Desconto_Horas = Valor_Hora x Horas_Faltadas
```

### 7. Desconto por Falta (DSR)
```
Desconto_DSR = (Salario_Base / 30) x Dias_Falta
```

---

*Documento gerado automaticamente pelo SIGE v9.0*
*Atualizado em: Janeiro/2026*
