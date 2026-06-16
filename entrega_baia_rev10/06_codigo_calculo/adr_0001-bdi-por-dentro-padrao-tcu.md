---
status: accepted
---

# Precificação de orçamento via BDI completo, lucro e tributos "por dentro" (padrão TCU)

## Contexto

O cálculo atual (`services/orcamento_service.py`) usa `preço = custo / (1 − imposto% − lucro%)` — um BDI degenerado com apenas tributo (T) e lucro (L) no denominador, sem os componentes de custo indireto. Sem validação, percentuais altos de lucro (ex.: 90%) levam o divisor a ~0 e geram preços astronômicos. O SIGE atende **tanto obra pública quanto privada**.

## Decisão

Adotar o **BDI completo no padrão TCU (Acórdão 2622/2013)**: `preço = custo_direto × (1 + AC + S + R + G + DF) / (1 − T − L)`, mantendo **lucro (L) e tributos (T) "por dentro"** (percentuais do preço de venda). Lucro = remuneração **bruta** do construtor sobre o faturamento.

## Considered Options

- **A (escolhida)** — BDI completo, L e T por dentro. Serve obra pública (BDI obrigatório/TCU) e privada; migração preserva o comportamento atual quando AC/S/R/G/DF = 0.
- **B** — Apenas estancar o bug (validação + correção de rótulo) mantendo a fórmula incompleta. Rejeitada: não entrega BDI real.
- **C** — Lucro "por fora" (markup sobre custo, intuitivo, sem explosão). Rejeitada: diverge do padrão TCU exigido em obra pública.

## Consequences

- A explosão de preço perto de L+T = 100% continua **matematicamente possível** → exige validação/guarda-corpo (decisão de UX ainda aberta: bloqueio rígido vs aviso).
- O "Lucro" exibido hoje (`preço − custo`, que embute o imposto) precisa ser separado em Custo / Indiretos / Tributos / Lucro (L×preço).
- Cascata de alíquotas (item → global → serviço → empresa → 0) deve ser estendida a todos os componentes do BDI.
- Snapshots de preço já gravados em propostas/itens **não** são recalculados retroativamente.
