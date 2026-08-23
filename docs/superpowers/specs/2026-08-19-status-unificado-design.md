# Fase 4 do ciclo de compras — o status unificado — 2026-08-19

**O que é.** Uma resposta única para *"onde está esta compra?"*, em vez das seis
respostas parciais que o sistema dá hoje, cada uma numa tabela diferente.

**Por que agora.** É a quarta da ordem acordada (recebimento → dois fluxos →
alçadas → **status unificado** → relatórios) e estava bloqueada: 📖 o fecho de
17/08 registra que *"a régua de 9 etapas teria de representar dois passos que até
17/08 não existiam em tela nenhuma"* — a nota e a liberação. Eles existem desde
`9aa29a59`, e desde 19/08 o fechamento do lote também passa pelo serviço. **O
bloqueio caiu.**

---

## 🔴 O primeiro achado: as "9 etapas" nunca foram enumeradas

A régua é citada como coisa sabida em **três** documentos —
📖 `2026-08-15-alcadas-design.md:469`, `:554` e `:895`, 📖
`2026-08-17-nota-e-liberacao-design.md:8` e `:398`, `ESTADO-ATUAL.md:642` — e
🔬 **nenhum deles lista os nove**. Não há spec, não há tabela, não há enum.

Isso muda o tamanho desta fase. Ela não é "implementar a régua que está escrita":
ela é **decidir quais são as etapas**, e o número 9 é herança de conversa, não
requisito medido. Este documento trata 9 como hipótese a conferir, não como dado
— é o mesmo defeito de fabricação que abre o `ESTADO-ATUAL.md`, na forma de um
número que atravessou três specs sem procedência.

---

## O inventário: seis portadores de estado, quatro tabelas

🔬 19/08, lidos no código. É o que a régua tem de unificar.

| # | Portador | Onde | Valores | Tem máquina de estados? |
|---|---|---|---|---|
| 1 | `RequisicaoCompra.estado` | 📖 `models.py:80-99` | 6: RASCUNHO, AGUARDANDO_APROVACAO, APROVADA, REJEITADA, CONVERTIDA, CANCELADA | ✅ **sim** — `TRANSICOES_VALIDAS` + trilha auditada em `RequisicaoTransicao` (📖 `models.py:6306`) |
| 2 | `PedidoCompra.situacao_recebimento` | 📖 `models.py:5817` | 4: `nao_recebido`, `parcial`, `recebido`, `encerrado_com_saldo` | ❌ **derivado** — recalculado por `situacao_para()` a cada recebimento (📖 `services/recebimento_pedido.py:503,648`) |
| 3 | `PedidoCompra.status_aprovacao_cliente` | 📖 `models.py:5757` | texto livre: None, PENDENTE, AGUARDANDO_APROVACAO_CLIENTE, APROVADO, RECUSADO, REJEITADO | ❌ **nenhuma** — e ver o achado 2 abaixo |
| 4 | `ContaPagar.situacao_liberacao` | 📖 `models.py:2469` | 2: `bloqueada`, `liberada` | ✅ chokepoint único (`liberar()`) |
| 5 | `ContaPagar.status` | 📖 `models.py:2441` | PENDENTE, PARCIAL, PAGO, CANCELADO | ❌ nenhuma |
| 6 | `FechamentoPagamento.status` | 📖 `models.py:9416` | ABERTO, FECHADO | ✅ chokepoint desde 19/08 (`fechar_lote`) |

Mais dois estados que **não têm coluna** e mesmo assim são etapa do ciclo:

- **a nota fiscal** — existe ou não existe (`NotaFiscalPedido`); a "perna" é a
  presença, não um campo;
- **o adiantamento do Fluxo B** — `AdiantamentoFornecedor.baixado_em` nulo ou não.

🔬 **Não existe hoje NENHUMA função que agregue isto.** Varredura por
`def etapa|def situacao_geral|def status_unificado|def onde_esta` não acha nada
fora de dois scripts de cronograma, sem relação. 📖 As telas mostram badges
lado a lado (`templates/compras/index.html:104-134`) e deixam a soma para a
cabeça de quem olha. **A régua é código novo, não refatoração.**

---

## 🔴 O segundo achado: são DOIS eixos, não um

`status_aprovacao_cliente` (nº 3) **não é etapa do ciclo de compra** — é o rito do
*faturamento direto*, em que o custo só nasce depois de o cliente aprovar. Ele é
**ortogonal**: uma compra pode estar "recebida e atestada" e ao mesmo tempo
"aguardando aprovação do cliente".

Espremer os dois numa régua linear produz ou etapas que se contradizem, ou uma
régua com o dobro de casas. **Recomendação: a régua é do ciclo de compra; o
faturamento direto continua sendo um selo ao lado, não uma casa da régua.**

E há o terceiro eixo, que a Fase 2 criou de propósito: **o Fluxo A (faturado) e o
Fluxo B (adiantamento) não percorrem o mesmo caminho.** No A, o dinheiro sai
depois do material; no B, antes. Uma régua única tem de ou **ramificar** ou
**nomear as casas por função** em vez de por ordem — ver a decisão D2.

---

## As decisões

### D1 — a régua é derivada ou gravada?

| | O quê | A favor | Contra |
|---|---|---|---|
| **a** ← recomendo | **Derivada** por uma função pura, `etapa_do_pedido(pedido)` | Impossível divergir do dado — ela LÊ os seis portadores, não os duplica. Sem migração, sem backfill, sem drift, e o sensor não ganha um achado novo | Não dá para filtrar por etapa em SQL, e a Fase 5 vai querer |
| **b** | **Gravada** numa coluna, mantida por listener | Consulta e índice de graça para os relatórios | Cria um SÉTIMO portador de estado — mais um lugar para divergir dos outros seis. É exatamente a doença que esta fase existe para curar |
| **c** | Derivada, e **materializada só no relatório** (Fase 5) | Fonte única + consulta rápida onde ela é necessária | Duas peças em vez de uma |

**Recomendo (a), com (c) como saída se a Fase 5 medir lentidão.** Gravar primeiro
e medir depois inverte o ônus: 🔬 o repositório tem histórico de coluna gravada
que envelhece calada (`valor_orcado` guardando venda, cinco escritores de
`valor_contrato`), e o p3/p9 do núcleo foram gastos consertando isso.

### D2 — uma régua para os dois fluxos, ou duas?

**Recomendo: UMA régua, com casas nomeadas por função**, e as casas que não se
aplicam ao fluxo aparecem **apagadas**, não ausentes. Uma régua que muda de forma
conforme o pedido obriga quem olha a saber de qual régua está falando — e a
comparação entre compras, que é o motivo de haver régua, some.

### D3 — quantas casas, afinal?

O candidato honesto, derivado do inventário (não das conversas):

| # | Casa | De onde sai |
|---|---|---|
| 1 | Requisitada | `estado` ∈ RASCUNHO, AGUARDANDO_APROVACAO |
| 2 | Aprovada | `estado` = APROVADA |
| 3 | Pedido emitido | `estado` = CONVERTIDA + `PedidoCompra` existe |
| 4 | Material recebido | `situacao_recebimento` ∈ parcial, recebido, encerrado_com_saldo |
| 5 | Nota lançada | existe `NotaFiscalPedido` |
| 6 | Liberada para pagamento | `situacao_liberacao` = liberada |
| 7 | Em lote de pagamento | `fechamento_id` não nulo |
| 8 | Paga | `ContaPagar.status` ∈ PAGO, PARCIAL |
| 9 | Encerrada | tudo pago **e** recebimento fechado |

**São nove** — e o fato de fechar em nove sem forçar é o primeiro indício de que o
número herdado não era arbitrário. Mas ele **precisa ser conferido contra as
saídas laterais**, que a régua linear não representa: REJEITADA, CANCELADA,
`encerrado_com_saldo` e a **liberação com ressalva** (D6 da Fase 2) e o
**fechamento por quem montou** (19/08) — as duas últimas são exceções declaradas
que a régua não pode esconder.

---

## Como saberemos que funciona

**Pelo runbook por script, não por gate.** É a lição de 19/08, e ela é específica:
o gate cobre a regra e não cobre o caminho — `fechar_lote()` passou semanas
testado e sem chamador de produção, e foi o runbook que achou. A régua tem o mesmo
formato de risco: uma função pura que ninguém chama passa em todo teste.

Portanto, dois requisitos de aceitação, não um:

1. `scripts/runbook_fase2.py` ganha um passo que confere, **em cada casa do
   ciclo**, que a régua diz a casa certa — a mesma medida que hoje faz 34/34;
2. a régua tem de aparecer **numa tela**, e o runbook tem de achá-la no DOM.

---

## Fora de escopo

Os 5 relatórios (Fase 5) — esta fase entrega a régua que eles vão consumir, e
nada mais. Também fora: mexer em `EstadoRequisicao`, que 📖 a spec das alçadas
já decidiu deixar quieta (`:469`), e a convergência da `NotaFiscal` legada.

**A pergunta herdada da Fase 3 que volta a esta mesa:** 📖
`2026-08-15-alcadas-design.md:554` deixou para a Fase 4 o beco do reenvio quando
as compras irmãs são de etapas diferentes. Ele é de alçada, não de régua — mas é
aqui que "o quadro inteiro está à vista", que foi a razão de adiá-lo. Entra como
pergunta a responder, não como entrega assumida.

---

## 🔬 Conferência de 23/08 — a régua lida no código, e o que sobra para decidir

> A spec pedia, em D3, que as nove casas fossem "conferidas contra as saídas
> laterais". Isto é essa conferência: cada casa foi lida no `models.py` de hoje,
> campo por campo. **Nada aqui é decisão tomada** — é o candidato da D3 com os
> defeitos que a leitura achou, para virar aprovação ou correção.

### As nove casas existem no dado — com duas correções

🔬 23/08, por introspeção dos modelos (`__table__.columns`):

| # | Casa | Campo que ela lê | Existe hoje |
|---|---|---|---|
| 1 | Requisitada | `RequisicaoCompra.estado` | ✅ |
| 2 | Aprovada | `RequisicaoCompra.estado` | ✅ |
| 3 | Pedido emitido | ~~`RequisicaoCompra.pedido_id`~~ → **`PedidoCompra.requisicao_id`** | ⚠️ **corrigido** — o vínculo existe ao contrário do que a D3 supôs; a derivação vai do pedido para a requisição |
| 4 | Material recebido | `PedidoCompra.situacao_recebimento` | ✅ |
| 5 | Nota lançada | presença de `NotaFiscalPedido` (`pedido_id`) | ✅ |
| 6 | Liberada para pagamento | `ContaPagar.situacao_liberacao` | ✅ |
| 7 | Em lote de pagamento | `ContaPagar.fechamento_id` | ✅ |
| 8 | Paga | `ContaPagar.status`, `valor_pago` | ✅ |
| 9 | Encerrada | `situacao_recebimento` + `ContaPagar.status` | ✅ |

⚠️ **Segunda correção: o atesto não é coluna.** `PedidoCompra.valor_atestado`
**não existe**; 📖 `valor_atestado(pedido)` é **função** em
`services/recebimento_pedido.py`, consumida por `services/financeiro_compra.py:306,315`.
Quem escrever a régua tem de chamá-la, não ler campo.

### 🔴 O problema que a régua linear ainda não resolve: o Fluxo B inverte a ordem

A D2 resolveu a *forma* (uma régua, casas nomeadas por função, inaplicáveis
apagadas) mas não a *ordem*. 📖 `models.py:5845` — no fluxo `'adiantamento'`
**paga-se antes de receber**. Numa régua linear, isso acende a casa 8 antes da 4,
e uma barra de progresso que acende fora de ordem lê como defeito.

**Proposta (a decidir): a régua é uma LISTA DE CONFERÊNCIA com um ponteiro, não
uma barra de progresso.**

- cada casa acende quando **a condição dela é verdadeira**, independente da ordem;
- o "onde está" é derivado: **a primeira casa aplicável ainda não satisfeita**;
- no Fluxo B a casa 8 acende cedo e o ponteiro continua dizendo *"aguardando
  material"* — que é exatamente a verdade que hoje ninguém consegue ler.

Isso preserva o motivo de haver régua (as mesmas nove colunas em toda compra,
comparáveis) sem mentir sobre o caminho de cada fluxo.

**Condição da casa 8, então, é união e não campo único:**
`ContaPagar.status ∈ (PAGO, PARCIAL)` **ou** (`fluxo_pagamento = 'adiantamento'`
**e** `AdiantamentoFornecedor.baixado_em` não nulo). 🔬 os quatro campos existem.

### As saídas laterais — e uma que não é saída

| Situação | O que a conferência achou | Proposta |
|---|---|---|
| **REJEITADA** | 📖 `models.py:80-99`: **não é terminal** — dela se volta para RASCUNHO ("rejeitar não é matar"). O docstring já registra que até 17/08 ele mesmo dizia o contrário | **Não é saída lateral**: é a casa 1 com um selo. Tratá-la como fim seria repetir o erro que a Fase 3 já corrigiu |
| **CANCELADA** | Terminal, junto com CONVERTIDA | Encerra a régua: badge no lugar do ponteiro, dizendo **em qual casa parou** |
| **`encerrado_com_saldo`** | Valor de `situacao_recebimento` | Satisfaz a casa 4 **e** a 9, com selo "com saldo" — não é pendência |
| **Liberação com ressalva** (D6 da Fase 2) | 📖 `ContaPagar.liberacao_justificativa`, gravada em `services/financeiro_compra.py:450` | Casa 6 acesa **com selo**; a régua não pode esconder que houve ressalva |
| **Fechamento por quem montou** (19/08) | Exceção declarada quando falta `criado_por_id` | Casa 7 acesa **com selo**, mesma regra |
| **Faturamento direto** (`status_aprovacao_cliente`) | Eixo ortogonal, como a spec já dizia | Fora da régua, selo ao lado |

### O que continua sendo decisão humana

1. **A régua é lista de conferência com ponteiro** (proposta acima) ou barra de
   progresso que ramifica no Fluxo B?
2. As nove casas, com as duas correções, **são estas nove**?
3. Os cinco selos (ressalva, fechamento por quem montou, com saldo, adiantamento,
   aprovação do cliente) aparecem na régua ou só no detalhe?

Respondidas as três, a fase vira plano: 🔬 não existe hoje função nenhuma que
agregue isto, então é código novo — `etapa_do_pedido(pedido)` derivada (D1a), a
tela, e o runbook por script que a acha no DOM.

---

## ✅ 23/08 — as três decisões, tomadas por delegação e ancoradas fora de casa

> "Para três perguntas pode fazer o que achar melhor, pesquise na internet o que o
> mercado atual trabalha em outros app, ou em estudos acadêmicos atuais."
> — Cássio, 23/08. Isto é a resposta, com a evidência externa que a sustenta.
> A régua nunca tinha sido comparada com como o resto do mundo modela P2P; foi.

### O que o mercado faz — quatro fontes, mesma conclusão

| Fonte | O que ela mostra |
|---|---|
| **SAP MM** ([SAP Help — PO Status](https://help.sap.com/docs/SAP_SUPPLY_CHAIN_MANAGEMENT/3ca3c124fc81486585fde980106996a8/480dce82909d3c8be10000000a42189c.html)) | O item de pedido **não tem status linear**. Tem indicadores independentes: `ELIKZ` (entrega concluída) e `EREKZ` (fatura final) na `EKPO`, mais status de confirmação, de alteração e de aprovação, cada um por sua conta. O relatório ME2N cruza-os; não os funde |
| **Odoo** ([3-way matching](https://www.odoo.com/documentation/13.0/applications/inventory_and_mrp/purchase/purchases/rfq/3_way_matching.html), [receipt status](https://apps.odoo.com/apps/modules/18.0/eq_purchase_receipt_status)) | `state` do pedido **ao lado** de `receipt_status` e `invoice_status` derivados. O veredito do 3-way match é o campo **computado** "Should be paid" — com um "Force Status" para o humano sobrepor, visível no mesmo lugar |
| **NetSuite** ([status do PO](https://docs.oracle.com/en/cloud/saas/netsuite/ns-online-help/section_N2408514.html)) | Força **um** enum linear — e o resultado é o produto cartesiano vazando para dentro dele: existe o status **"Pending Billing/Partially Received"**. É a prova pelo contra-exemplo do que acontece quando dois eixos são espremidos num |
| **BPI Challenge 2019** ([ICPM](https://icpmconference.org/2019/icpm-2019/contests-challenges/bpi-challenge-2019/)), 1,5 milhão de eventos de P2P real | O log **exige ao menos quatro modelos de processo**, um por categoria de fluxo — e "fatura antes do recebimento" é uma delas, **legítima**, não desvio. Nosso Fluxo B é um caso conhecido da literatura, não uma esquisitice nossa |

E a orientação de UX bate: passo a passo (*stepper*) só serve para processo
**genuinamente sequencial**; quando os passos são independentes, cada um tem de
exibir o próprio estado, senão o componente vira "um menu confuso"
([Progress tracker design](https://www.uxpin.com/studio/blog/design-progress-trackers/),
[PatternFly](https://www.patternfly.org/components/progress-stepper/design-guidelines/)).

### ✅ D3.1 — a régua é LISTA DE CONFERÊNCIA com ponteiro, não barra de progresso

Cada casa acende quando **a condição dela é verdadeira**, na ordem que for; o
"onde está" é derivado — **a primeira casa aplicável ainda não satisfeita**.

**Por quê:** é o que SAP e Odoo fazem (indicadores independentes + derivação), e o
que a NetSuite mostra custar quando não se faz (o status combinado). Com 9 casas ×
2 fluxos, um enum linear precisaria enumerar as combinações — e a primeira delas
já seria "pago aguardando material", que é exatamente o Fluxo B normal.

### ✅ D3.2 — são estas NOVE casas, com as duas correções da conferência

Sem casa nova. Duas anotações que passam a valer:

- **As casas 3, 4 e 5 são o *three-way match*** (pedido ↔ recebimento ↔ nota) — o
  mesmo trio que SAP, Odoo e NetSuite conferem. Vale marcá-las como um grupo: é o
  que dá sentido a elas para além da ordem.
- **O atesto NÃO vira uma décima casa.** Ele é a **condição da casa 6**
  (liberada para pagamento), do mesmo jeito que na SAP a verificação de fatura é o
  que solta o bloqueio de pagamento em vez de ser uma etapa à parte. Uma casa
  própria contaria o mesmo evento duas vezes. 📖 lembrar que `valor_atestado()` é
  função em `services/recebimento_pedido.py`, não coluna.

### ✅ D3.3 — quatro selos na régua, um ao lado

Selo **na casa** que ele qualifica — é o padrão do "Force Status" da Odoo, que
mostra a exceção no mesmo lugar do estado, e não numa tela de detalhe:

| Selo | Casa | Por que na régua |
|---|---|---|
| Liberação **com ressalva** (📖 `ContaPagar.liberacao_justificativa`) | 6 | Esconder a ressalva é esconder que alguém assumiu um risco |
| **Fechamento por quem montou** (exceção declarada de 19/08) | 7 | Idem — é segregação de função dispensada |
| **`encerrado_com_saldo`** | 4 e 9 | Distingue "chegou tudo" de "encerramos com falta" |
| **Adiantamento** (Fluxo B, `AdiantamentoFornecedor.baixado_em`) | 8 | É *por que* a casa acendeu fora de ordem |

**Fora da régua, ao lado:** o **faturamento direto** (`status_aprovacao_cliente`),
como a spec já tinha decidido — eixo ortogonal, selo próprio.

### A condição de cada casa, fechada

| # | Casa | Acende quando |
|---|---|---|
| 1 | Requisitada | `RequisicaoCompra.estado` ∈ RASCUNHO, AGUARDANDO_APROVACAO, REJEITADA *(REJEITADA é selo, não saída — dela volta-se a RASCUNHO)* |
| 2 | Aprovada | `estado` = APROVADA |
| 3 | Pedido emitido | existe `PedidoCompra` com `requisicao_id` = esta *(o vínculo é este; não há `RequisicaoCompra.pedido_id`)* |
| 4 | Material recebido | `situacao_recebimento` ∈ parcial, recebido, encerrado_com_saldo |
| 5 | Nota lançada | existe `NotaFiscalPedido` do pedido |
| 6 | Liberada para pagamento | `ContaPagar.situacao_liberacao` = liberada *(o atesto é a condição disto)* |
| 7 | Em lote de pagamento | `ContaPagar.fechamento_id` não nulo |
| 8 | Paga | `ContaPagar.status` ∈ PAGO, PARCIAL **ou** (`fluxo_pagamento` = adiantamento **e** `AdiantamentoFornecedor.baixado_em` não nulo) |
| 9 | Encerrada | todas as contas do pedido pagas **e** `situacao_recebimento` ∈ recebido, encerrado_com_saldo |

**Saídas que encerram a régua:** CANCELADA (e CONVERTIDA, que é sucesso da
requisição). O ponteiro dá lugar a um selo que diz **em qual casa parou**.

🔬 23/08: todos os campos acima foram lidos por introspeção dos modelos e existem.

**A fase está pronta para virar plano.** O que falta é escrever
`etapa_do_pedido(pedido)` derivada (D1a), a tela, e o runbook por script que a
ache no DOM — o critério que a própria spec fixou para não repetir o
`fechar_lote()`, testado e inalcançável por semanas.

---

**23/08 — entregue.** `etapa_do_pedido` derivada, a régua no detalhe e na
listagem, e o runbook por script achando-a no DOM: branch
`feat/regua-status-unificado`. Números e detalhe em `### ✅ 23/08 — Fase 4 do
ciclo` em `ESTADO-ATUAL.md`.
