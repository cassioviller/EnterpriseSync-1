# [Refactor E] Precificação única — backend autoritativo, JS só exibe

> Bloco E do plano de remediação. Prioridade P5 — risco médio (UX do editor).

## Problem Statement

Existem duas implementações de precificação: o helper central (catálogo e
proposta, com BDI completo) e o caminho do editor de orçamento, que combina um
serviço de visão com uma **fórmula de preço duplicada em JavaScript** dentro do
template. As duas precisam concordar, mas a duplicação é frágil: o teste de
paridade já quebrou por causa de uma divergência de nome de variável no JS.

## Solution

Uma fórmula autoritativa no servidor; o JS do editor passa a apenas **exibir um
preview** consultando um endpoint de cálculo, sem reimplementar a conta. A longo
prazo, convergir o cálculo de orçamento para o helper central (ou extrair o
núcleo comum), respeitando as diferenças de regra (custo real de compra vs BDI).

## Commits

1. Endpoint leve de preview de preço que devolve o cálculo do backend para os
   inputs do editor (reusando o helper canônico).
2. Mapear as diferenças de regra entre o cálculo do editor e o helper central;
   documentar quais convergem e quais permanecem distintas.
3. JS do editor passa a consumir o endpoint (com debounce) em vez de calcular
   localmente; remover a fórmula duplicada do template.
4. Substituir o teste de paridade baseado em regex por um teste do endpoint de
   preview contra a tabela de casos canônica.
5. Verde: preview do editor == backend para os casos; nenhuma fórmula de preço
   em JS.

## Decision Document

- O servidor é a única autoridade de cálculo de preço; o cliente só exibe.
- O preview do editor é um contrato de endpoint, não uma reimplementação.
- Snapshots de orçamento/proposta já gravados **não** são recalculados.

## Testing Decisions

- Testar comportamento externo: "o endpoint de preview retorna o mesmo total que
  a persistência do backend para os mesmos inputs".
- Prior art: o teste de paridade atual (que será aposentado) e os testes de
  tabela do helper de precificação (BDI).

## Out of Scope

- Recalcular orçamentos/propostas históricos.
- Unificação total dos dois modelos de custo se as regras forem genuinamente
  diferentes (decidir no commit 2).

## Further Notes

O helper central (BDI) já é a referência de "fórmula isolada e testável"; este
refactor estende esse princípio ao editor de orçamento.
