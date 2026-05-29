# SIGE

Glossário da linguagem do domínio do SIGE (sistema de gestão para construtoras).
Mantido como referência viva — apenas termos do domínio, sem detalhes de implementação.

## Precificação / Orçamento

**Custo direto**:
Soma de `coeficiente × preço do insumo` da composição de um serviço (materiais, mão de obra, equipamentos). Base sobre a qual o preço de venda é formado.
_Avoid_: custo, custo base

**BDI** (Benefícios e Despesas Indiretas):
Índice aplicado sobre o custo direto para chegar ao preço de venda, englobando custos indiretos (administração central, seguros, risco, garantia, despesas financeiras) e o que incide sobre o faturamento (tributos e lucro). Fórmula de referência (TCU 2622/2013): `BDI = (1+AC+S+R+G+DF)/(1−T−L) − 1`.
_Avoid_: markup, taxa, sobrepreço

**Lucro** (L no BDI):
Remuneração **bruta** do construtor expressa como **percentual do preço de venda** (não do custo, não líquido de IR/CSLL). Aplicado "por dentro" (no denominador do BDI).
_Avoid_: margem, markup, lucro líquido

**Tributos** (T no BDI):
Impostos que incidem sobre o preço de venda / faturamento (PIS, COFINS, ISS, CPRB). Aplicados "por dentro" (no denominador). No código atual aparece como `imposto_pct`.
_Avoid_: imposto isolado, encargo

**Percentual de nota fiscal**:
Campo da proposta (`percentual_nota_fiscal`, default 13,5%) que hoje é **apenas informativo** no PDF ("considerar X% para nota fiscal"). NÃO entra em nenhum cálculo e é distinto de _Tributos_.
_Avoid_: imposto, tributo
