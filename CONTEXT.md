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

## Estrutura do Trabalho (Orçamento ↔ Cronograma)

**Serviço**:
A linha do orçamento — unidade de **precificação**. Tem composição (custo direto) e valor de venda (via BDI). É onde o **preço mora**. Desdobra-se em uma ou mais Atividades.
_Avoid_: item, tarefa, etapa

**Atividade**:
A `TarefaCronograma` — unidade **executável e mensurável** do cronograma, onde a produção diária é apontada (RDO). Aponta para um Serviço (`servico_id`). Ex.: o Serviço "Estrutura LSF" → Atividades "painelização" e "verticalização". O preço **não** mora na Atividade; vem rateado do Serviço por hora-homem. O Resultado sobe Atividade → Serviço → Obra.
_Avoid_: tarefa (no domínio, use Atividade), subatividade, fase

## Acompanhamento Financeiro da Obra (Execução)

**Avanço realizado**:
Quanto de uma Atividade foi **fisicamente executado** (quantidade/percentual), apontado no RDO, em oposição ao _planejado_. É **avanço físico, não dinheiro** — e é a **âncora** de onde derivam tanto o _Valor agregado_ quanto o _Custo incorrido_. Termo do RDO; "Realizado" sozinho é banido de relatório (existe também o _Realizado_ de caixa, ver Fluxo de Caixa) — sempre usar com substantivo.
_Avoid_: realizado (pelado), produção, executado isolado

**Valor agregado** (a receber):
_Avanço realizado_ × valor de venda da Atividade. Mede o quanto a produção "ganhou" até a data — um avanço reconhecido, **antes** de virar obrigação ou fatura. Distinto de _Medição_ (o ato formal e periódico de medir para faturar).
_Avoid_: faturado, medido, receita, valor produzido

**Custo incorrido**:
Custo reconhecido **no dia em que o fato acontece** (competência): mão de obra pela hora trabalhada no dia, material quando consumido/requisitado, etc. É o que alimenta o _Resultado_ — distinto do _Realizado_ de caixa (quando o dinheiro de fato sai), que ocorre em outra data.
_Avoid_: custo realizado, custo pago, desembolso

**Resultado realizado**:
Valor agregado reconhecido − custo real incorrido, até a data. O que a obra/atividade deu de resultado **de verdade** até agora. Conceito _ex-post_, distinto de **Lucro** (que é planejamento do BDI, % da venda fixado antes da obra).
_Avoid_: lucro, lucro da obra, margem, markup, margem de contribuição

**Resultado projetado**:
Projeção do _Resultado realizado_ no encerramento da atividade/obra, dada a produtividade observada. É a saída do motor de previsão (EVM).
_Avoid_: lucro projetado, margem projetada, estimativa de lucro

## Fluxo de Caixa (Visualização)

**Realizado**:
Movimentação que efetivamente entrou ou saiu do caixa/banco (existe como registro de `FluxoCaixa`). É o que de fato aconteceu, não uma promessa.
_Avoid_: pago (pago é um status da obrigação; realizado é o efeito no caixa), efetivado

**Previsto**:
Obrigação em aberto ainda não liquidada (a receber ou a pagar) que projeta uma movimentação futura de caixa. Vive enquanto não vira Realizado.
_Avoid_: pendente, agendado, a vencer

**Variação acumulada de caixa**:
Quanto o caixa variou ao longo do período, partindo de **zero** e somando apenas os movimentos **Realizados**. Não é um saldo absoluto — o sistema não mantém saldo bancário (ver ADR 0003). A versão que soma também os **Previstos** é a *variação projetada*.
_Avoid_: saldo acumulado, saldo corrente, running balance (sugerem saldo absoluto, que não temos)

**Saldo em banco**:
Soma dos saldos atuais das contas bancárias cadastradas (`BancoEmpresa`). Métrica à parte da Variação acumulada; hoje fica em R$ 0 porque os saldos não são mantidos.
_Avoid_: saldo inicial, caixa

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
