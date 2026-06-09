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

## Importação / Classificação de Fluxo de Caixa

**Lançamento**:
Uma linha do Excel de Fluxo de Caixa (uma entrada ou uma saída), com data, descrição, fornecedor/cliente, centro de custo e valor.
_Avoid_: transação, registro, item

**Regra de Classificação**:
Associação permanente, por tenant, entre um gatilho e uma categoria de destino, com prioridade e condições. É a unidade que o usuário cadastra para ensinar o sistema a categorizar lançamentos automaticamente.
_Avoid_: palavra-chave (é parte da regra, não a regra), filtro, mapeamento

**Gatilho**:
O conjunto de palavras de uma Regra de Classificação que faz o lançamento casar (semântica "qualquer uma"). Na UI é apresentado ao usuário como "palavra-chave".
_Avoid_: keyword isolada, termo de busca

**Prioridade** (da regra):
Número que decide qual Regra de Classificação vence quando várias casam no mesmo lançamento — menor decide primeiro (mais específica). Substitui a ordem que antes era fixa no código.
_Avoid_: peso, ordem, ranking

**Pendente de Classificação**:
Lançamento que, na importação, não casou nenhuma Regra de Classificação específica e caiu no fallback genérico (Outras Saídas / Outros Recebimentos). É o que entra na fila de trabalho do usuário.
_Avoid_: revisão manual, não classificado, erro

**Termo**:
Palavra ou expressão recorrente (priorizando nome de fornecedor) usada para **agrupar** os Pendentes de Classificação na fila, de modo que classificar o termo resolva vários lançamentos de uma vez.
_Avoid_: tag, rótulo

**Correção**:
Decisão de categoria feita pelo usuário em **um lançamento individual** (no detalhe de um termo), quando o contexto contradiz a regra do termo. Vale para aquela importação e é memorizada para reuso (ver _Memória Exata_); não cria regra sozinha.
_Avoid_: override, ajuste manual, exceção

**Memória Exata**:
Reaplicação automática e silenciosa de uma Correção quando um lançamento de **texto idêntico** reaparece numa importação futura. Aprendizado sem risco de generalização indevida.
_Avoid_: cache, histórico

**Sugestão**:
Proposta que o sistema apresenta ao usuário para virar Regra de Classificação — seja a partir de Termos recorrentes na fila, seja a partir de uma Correção (regra refinada). Nunca vira regra sem confirmação do usuário.
_Avoid_: recomendação automática, regra automática
