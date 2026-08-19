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
