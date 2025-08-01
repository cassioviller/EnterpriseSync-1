
# CORREÇÃO DO CÁLCULO DE CUSTO

## Problema Identificado:
O cálculo de custo de mão de obra está inflado.

## Salário: R$ 2.800,00
## Horas trabalhadas: 184h (23 dias * 8h)  
## Custo atual (incorreto): R$ 2.927,27
## Custo correto: R$ 2.345,45

## Fórmula correta:
valor_hora = salario_mensal / 220  # 22 dias * 10h (com almoço)
custo = valor_hora * horas_efetivamente_trabalhadas

## O problema está na engine de KPIs que adiciona custos extras incorretamente.
