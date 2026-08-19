# Serviço tem uma ou mais Atividades repartidas pelo Peso da medição; 1:1 é só fallback; granularidade congela no apontamento

**Status:** accepted

O modelo do domínio é **1 Serviço → uma ou mais Atividades**, e o **Peso da medição**
(`ItemMedicaoCronogramaTarefa.peso`, soma 100% por Serviço) é a fonte **única** que reparte venda,
custo orçado e medição do Serviço entre suas Atividades (D6/D8). Ex. (cronograma refinado da Baia):
Serviço 1.1 "Estrutura LSF" → Painelização (50%) + Montagem (50%); Serviço 1.17a "Radier" → Preparo
(33%) + Armação/formas (38%) + Concretagem (29%). É **esse** o alvo — não Serviço = Atividade.

**Serviço = Atividade (1:1, peso 100%) é apenas o _fallback_** para quando o detalhamento das
Atividades de um Serviço **não está carregado** no sistema (sem `CronogramaTemplate` → 
`materializar_cronograma` cria 0 Atividades). Garante que a obra funciona ponta a ponta com zero
config, mas **não é o modelo desejado**: quando há detalhamento (o cronograma refinado tem 30
Atividades com pesos explícitos), a importação deve criar a estrutura **multi-atividade** com os
pesos do detalhamento.

A granularidade de um Serviço **congela quando ele começa a receber RDO**: a materialização é
idempotente por `gerada_por_proposta_item_id` e **não existe operação de split** de Atividade — os
apontamentos ficam presos ao `tarefa_cronograma_id`. Portanto o detalhamento (1:1 → N atividades) é
uma decisão de **pré-execução**; depois de apontado, re-particionar exigiria reatribuir histórico de
produção/custo, o que rejeitamos por ser frágil. Consideramos bloquear o apontamento até detalhar
(rejeitado: contradiz "importou e funciona") e permitir split a qualquer momento (rejeitado: risco
de reatribuição). Decisão prática: carregar o detalhamento **antes** de apontar; onde ele faltar,
o 1:1 segura a obra sem travá-la.
