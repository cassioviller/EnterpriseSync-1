# Financeiro em dois fluxos — a obrigação passa a nascer do que chegou

**Data:** 2026-08-14
**Origem:** pedido do Cássio — "ciclo completo de compras, da solicitação no campo até o
lançamento no fluxo de caixa, com rastreabilidade por um número único".
**Escopo:** a **segunda** das cinco fases em que o pedido foi decomposto. Cobre a tríade
PC+NF+atesto, o adiantamento a fornecedor, a segregação entre quem lança e quem libera, e
a liberação em lote.
**Depende de:** Fase 1 (recebimento e atesto) mesclada. Este spec consome
`valor_atestado()` e `situacao_recebimento`, que nasceram lá.

---

## Por que existe — e o defeito que já está em produção

`compras_views.py:305` cria a `ContaPagar` **na emissão do pedido**. Não há material,
não há nota, não há conferente: alguém preencheu um formulário e o sistema passou a dever
dinheiro. Três consequências, todas verificáveis hoje:

1. **O contas a pagar promete o que foi pedido, não o que chegou.** Entrega parcial,
   entrega que não veio, fornecedor que sumiu — a obrigação continua lá pelo valor cheio.
   A Fase 1 acabou de criar o número certo (`valor_atestado(pedido)`) e **ninguém o lê**.
2. **Não existe nota fiscal no ciclo de compra.** `NotaFiscal` (`models.py:2640`) existe,
   mas é outra coisa: nasceu para o import de XML do almoxarifado, exige
   `chave_acesso` NOT NULL **e UNIQUE global** (o mesmo campo que
   `tests/test_arreio_almoxarifado_e_tenant.py:31` registra como vazamento entre tenants),
   e se liga a `MovimentacaoEstoque` — não a `PedidoCompra`, não a `ContaPagar`.
3. **Quem lança é quem paga.** `financeiro.pagar_conta` (`financeiro_views.py:445`)
   exige `@login_required` e nada mais. A mesma pessoa cadastra o fornecedor, emite o
   pedido, cria a conta e dá a baixa. A Fase 3 tratou disso na *compra*
   (`solicitante_id != aprovador_id` como invariante); no *pagamento* não há nada.

### A peça que já existe e não faz nada

`FechamentoPagamento` (`models.py:9061`) é **a liberação em lote, sem o efeito**. A tela
(`financeiro_views.py:1429`) deixa selecionar contas, agrupa num lote, carimba
`total_selecionado` e muda o status de `ABERTO` para `FECHADO`. Só que:

- `pagar_conta` **não consulta o fechamento em ponta nenhuma** — pagar uma conta fora de
  qualquer lote funciona igual;
- `FECHADO` não bloqueia nem autoriza nada, e `reabrir` desfaz sem trilha;
- não há quem fechou, nem quando.

Ou seja: a UI do rito existe, o rito não. Esta fase **não cria uma segunda tela de lote** —
dá efeito à que está lá.

---

## Os dois fluxos, e por que são dois

O que hoje é um caminho só ("emitiu, deve") são duas realidades diferentes de canteiro:

**Fluxo A — faturado.** O material chega, depois vem a nota, depois se paga. É a compra a
prazo com fornecedor cadastrado. A obrigação só é **pagável** quando as três pontas
existem: **pedido emitido + nota lançada + atesto do que chegou**. É a tríade.

**Fluxo B — adiantamento.** Paga-se antes de receber, porque o fornecedor não entrega sem
isso. Aqui a obrigação nasce do pedido mesmo — não há o que atestar ainda. O que a fase
acrescenta é o **outro lado**: o adiantamento fica numa lista "pago, aguardando entrega"
até o atesto chegar e **baixá-lo**. Sem essa lista, dinheiro que saiu vira material que
ninguém cobra.

A diferença não é de configuração de tela: é **regime da linha**, como `exige_atesto` da
Fase 1. Carimbado na emissão, imutável depois, porque mudar o regime de um pedido em
andamento reescreveria o passado dele.

---

## Modelo de dados

### `PedidoCompra.fluxo_pagamento` — o regime

`String(16)`, NOT NULL, default `'faturado'`. Valores: `faturado` | `adiantamento`.
Carimbado na criação a partir da escolha de quem emite, **sob a flag** — com a flag
desligada todo pedido nasce `faturado` e nada muda, que é exatamente o comportamento de
hoje.

Por que coluna e não derivação: o mesmo fornecedor vende das duas formas, e a decisão é do
comprador no ato. Derivar de cadastro do fornecedor erraria no caso que mais importa.

### `nota_fiscal_pedido` — a nota que autoriza o pagamento

Tabela nova. **Não reusar `NotaFiscal`**, e a razão é dura: `chave_acesso` é NOT NULL e
UNIQUE global lá. Metade das compras de obra chega com recibo, nota de serviço ou nota
sem XML na mão do comprador; exigir a chave de 44 dígitos para poder pagar transformaria
a tríade numa trava que o campo aprende a contornar. E o UNIQUE global é um vazamento
entre tenants já catalogado — herdar isso agora seria escolher um defeito conhecido.

| Coluna | Por quê |
|---|---|
| `pedido_id` NOT NULL | a nota é de um pedido; nota sem pedido é o mundo do import de XML, que continua onde está |
| `admin_id` NOT NULL | tenant, como todo o resto |
| `numero`, `serie` | o que o pagador confere contra o papel |
| `chave_acesso` **nullable** | quando tem, guarda; quando não tem, não trava |
| `valor_total` | é o que se compara com o atestado |
| `data_emissao`, `data_vencimento` | a segunda é o que gera o vencimento da `ContaPagar` — hoje ele é chutado da data da compra |
| `arquivo_path` nullable | PDF/XML anexado, quando houver |
| `lancada_por_id`, `created_at` | metade da segregação: quem lançou |
| UNIQUE `(admin_id, fornecedor_id, numero, serie)` | a mesma nota não entra duas vezes |

Um pedido pode ter **N notas** (entrega parcial fatura em partes). A soma das notas é
comparada com `valor_atestado(pedido)` — divergência não bloqueia, **avisa**, com o número
dos dois lados. Bloquear aqui seria travar a compra por causa de frete e arredondamento.

### `ContaPagar.situacao_liberacao` — a segregação

`String(16)`, NOT NULL, default `'liberada'`. Valores: `bloqueada` | `liberada`.
Mais `liberada_por_id` e `liberada_em`, nullable.

O default é `'liberada'` **de propósito**: toda `ContaPagar` que já existe, e toda que
nascer com a flag desligada, continua pagável como hoje. Só o regime novo cria conta
`bloqueada`. Sem isso, a migration transformaria o parque inteiro em contas travadas no
dia do deploy.

`pagar_conta` ganha uma guarda: conta `bloqueada` recusa baixa, dizendo **qual perna da
tríade falta** — "sem nota lançada", "sem atesto", "atestado R$ 0,00 de R$ 4.200,00".
Recusar sem dizer o que falta é o que faz usuário procurar o caminho de fora do sistema.

### `adiantamento_fornecedor` — o Fluxo B

Tabela nova, pequena: `pedido_id`, `admin_id`, `conta_pagar_id` (a obrigação que ele
gerou), `valor`, `data_prevista_entrega`, `baixado_em` nullable, `baixado_por_id`
nullable, `observacao`.

O adiantamento **é** uma `ContaPagar` (paga-se por ela, ela vai ao fluxo de caixa, ela
debita banco pela B5.6). O que a tabela acrescenta é a ponta que hoje não existe: a
pendência de **entrega**. Enquanto `baixado_em` for NULL, o pedido aparece na lista
"pago, aguardando entrega". O atesto da Fase 1 é quem baixa — e é o único que baixa,
porque baixa manual sem material é exatamente o buraco que a lista existe para tapar.

### `FechamentoPagamento` ganha efeito

**Quatro** colunas: `criado_por_id`, `fechado_por_id`, `fechado_em`, `reaberto_por_id`.

> 📌 **Corrigido em 14/08, durante a F5.** Este spec listava só três, esquecendo
> `criado_por_id` — e sem ela "quem monta não fecha" não é regra, é frase: dá para saber
> quem fechou e não há com quem comparar. Entrou pela **migration 296** (296 e não 290,
> porque 290-295 é faixa reservada da Fase 8 e 300-307 da Fase 9).

**Fechar o lote é o ato que libera.** Quem monta o lote e quem o fecha não podem ser a
mesma pessoa — invariante, não configuração, mesmo padrão da Fase 3.

> 📌 **Desvio deliberado, decidido na F5.** Este spec dizia que no regime novo
> `pagar_conta` exigiria a conta num fechamento `FECHADO`. **Não foi feito assim.**
> `pagar_conta` tem UMA porta: `situacao_liberacao`. Duas guardas no mesmo ponto
> recusariam o mesmo pagamento por dois motivos diferentes e dobrariam as formas de o
> usuário ficar preso, sem acrescentar controle nenhum — fechar o lote é justamente o que
> muda a situação para `liberada`. O estado mora num lugar só; o fechamento é quem o move.

Duas concessões de robustez, ambas para que a regra sobreviva ao uso real:

- **A segregação só é exigida quando os dois lados são conhecidos.** Lote anterior à 296
  não tem autor registrado; exigir com um lado ausente travaria todo lote histórico, e o
  efeito prático seria o time desligar a regra. Regra que atrapalha sem proteger é regra
  que morre — e inventar um autor seria forjar autoria, o mesmo defeito que o detector da
  Fase 5 pega em RDO assinado sem trilha.
- **Conta sem a tríade fechada é pulada no fechamento, não estoura.** Um lote de dez
  contas não pode falhar inteiro porque uma delas está sem nota. O que fica de fora
  continua bloqueado, e o sensor de consistência o nomeia.

---

## Regime de virada

Flag por tenant: `configuracao_empresa.financeiro_dois_fluxos_ativo`, default `FALSE`,
irmã de `compras_governanca_ativa` (246) e `recebimento_atesto_ativo` (284). Ligada por
`scripts/flag_financeiro_dois_fluxos.py`, com guarda dura:

> **recusa tenant sem `recebimento_atesto_ativo` ligado.** Sem atesto não existe a perna
> do atesto na tríade, e a conta nasceria `bloqueada` sem caminho para liberar. É o mesmo
> tipo de dependência que a Fase 3 tem do `escopo_obra_ativo`, e a lição de lá é que a
> guarda precisa estar no script, porque quem mexe por SQL direto não tem nenhuma.

Com a flag desligada, **movimento a movimento**: `ContaPagar` nasce na emissão, `liberada`,
sem nota, sem lote, sem regime. O teste de paridade é o que prova isso, e é o mesmo
formato do que a Fase 1 usou para o almoxarifado.

---

## Fluxo, com a flag ligada

```
Fluxo A — faturado
  emitir pedido ──> ContaPagar BLOQUEADA (valor do pedido, vencimento provisório)
       │
       ├── atestar (Fase 1) ─────> valor_atestado > 0        ┐
       │                                                      ├─> as três pernas
       └── lançar nota ──────────> nota_fiscal_pedido         ┘
                                          │
                          montar lote ────┴──> fechar lote (outra pessoa)
                                                     │
                                                     └──> ContaPagar LIBERADA ──> pagar

Fluxo B — adiantamento
  emitir pedido ──> ContaPagar LIBERADA + adiantamento_fornecedor (baixado_em NULL)
                          │                             │
                       pagar                    "pago, aguardando entrega"
                                                        │
                                          atestar (Fase 1) ──> baixado_em preenchido
```

**Caminho único de escrita.** Tudo que cria, libera ou baixa passa por
`services/financeiro_compra.py` — chokepoint, no molde de
`services/recebimento_pedido.py` e `services/requisicao_compra.py`. As rotas validam
formulário e chamam o serviço; não escrevem.

**O valor da conta.** No Fluxo A a `ContaPagar` nasce pelo valor do pedido e é
**reajustada para `valor_atestado`** no momento da liberação, com a diferença registrada
na observação. Não nasce pelo atestado porque no instante da emissão ele é zero, e uma
conta de R$ 0,00 não aparece em nenhuma projeção de caixa — o financeiro perderia a
previsão, que é metade do valor do módulo.

---

## Decisões que precisam do Cássio

Nenhuma bloqueia. Todas seguem com o `Recomendado:` implementado como **dado editável**,
não constante de código.

**D1 — Divergência entre nota e atestado bloqueia o pagamento?**
*Recomendado:* **não bloqueia, avisa**, com tolerância configurável por tenant (semeada em
**2%**). Frete, arredondamento e ICMS por dentro produzem divergência legítima toda
semana; bloquear ensina o time a lançar nota com o valor do atestado, que é pior que não
ter a conferência.

**D2 — Quem libera?**
*Recomendado:* `ADMIN` do tenant, ou um `PapelObra` novo — mas **não nesta fase**. A Fase 3
criou `COMPRADOR` com dois verbos; criar `FINANCEIRO` aqui seria papel sem gente, e o
efeito prático seria concentrar tudo no dono. Fica ADMIN, com a segregação valendo
(quem montou o lote não fecha).

**D3 — Pedido sem obra entra na tríade?**
*Recomendado:* **sim**. Material de escritório também chega ou não chega. A Fase 4 já
resolveu o destino do custo (`id_do_centro_administrativo`), e o atesto da Fase 1 já
trata pedido sem obra (correção C5).

**D4 — O adiantamento pode ser parcial?**
*Recomendado:* **sim, e é o caso comum** — 50% na assinatura, 50% na entrega. Modelado
como N linhas de `adiantamento_fornecedor` no mesmo pedido, cada uma com sua
`ContaPagar`. O atesto baixa **todas** as pendentes daquele pedido.

**D5 — O que acontece com as contas a pagar já abertas no dia em que a flag liga?**
*Recomendado:* **nada** — continuam `liberada`. A virada vale para pedido **novo**, pelo
mesmo argumento da Fase 1: reescrever obrigação histórica é reescrever o passado
financeiro, e ninguém pediu isso.

**D6 — A nota fiscal é obrigatória para liberar?**
*Recomendado:* **sim no Fluxo A**, com uma porta de escape auditável: liberar sem nota
exige justificativa escrita, fica registrado em `liberada_por_id`/observação e aparece num
relatório de exceções. Fornecedor pequeno que emite nota semanas depois existe; o que não
pode é a exceção ser silenciosa.

---

## Casos de borda

| Situação | Comportamento |
|---|---|
| Nota lançada, atesto zero | Conta segue `bloqueada`; a tela nomeia a perna que falta |
| Atesto completo, sem nota | Idem, com D6 valendo para a exceção |
| Nota de valor maior que o atestado | Avisa acima da tolerância (D1); não bloqueia |
| Entrega parcial encerrada com saldo (C6 da Fase 1) | O atestado é o que chegou; a conta é reajustada para baixo na liberação |
| Excluir recebimento (R5 da Fase 1) de pedido com conta já liberada | **Recusa** — o estorno teria de desfazer liberação e pagamento, e isso é estorno financeiro, não de estoque |
| Pedido `aprovacao_cliente` | A ciência do cliente continua sendo pré-requisito do atesto (C4); a tríade se aplica igual |
| Adiantamento pago, pedido cancelado | O adiantamento **não some**: vira pendência de devolução, com o valor à vista na lista |
| Fechamento reaberto com conta já paga | Recusa reabrir; o lote fechado com pagamento é documento |
| Mesma pessoa montou e fechou o lote | Recusa, dizendo por quê — invariante, não configuração |
| Duas notas com mesmo número e série do mesmo fornecedor | Recusa pelo UNIQUE, com mensagem em português |

---

## Migrations

Números **287, 288, 289** — livres e fora de faixa reservada. `main` e o banco de dev
terminam em **286** (conferido em `migration_history` em 14/08, depois do merge da Fase 1,
que trouxe 283/284/285). As faixas 290-295 (Fase 8) e 300-307 (Fase 9) **não** são tocadas,
e o 270 segue queimado — nada aqui chega perto dele.

⚠️ Conferir `migration_history` **de novo** antes de fixar. Foi a lição da B6.1, repetida
na R1 da Fase 1, e ela apareceu mais uma vez no merge de 14/08.

| Nº | O que faz |
|---|---|
| 287 | `nota_fiscal_pedido` + `adiantamento_fornecedor` |
| 288 | `pedido_compra.fluxo_pagamento`; `conta_pagar.situacao_liberacao`, `liberada_por_id`, `liberada_em`; `fechamento_pagamento.fechado_por_id`, `fechado_em`, `reaberto_por_id` |
| 289 | `configuracao_empresa.financeiro_dois_fluxos_ativo` (default FALSE) + `tolerancia_divergencia_nf_pct` (default 2.00) |

Sem backfill em nenhuma. Todo default descreve exatamente o que o registro histórico é.

---

## Testes

`tests/test_financeiro_dois_fluxos.py`, no molde de `tests/test_recebimento_atesto.py`:
fixtures locais, `pytestmark = pytest.mark.integration`, tenant por `uuid4()`, sem depender
de seed. Os que não podem faltar:

- **paridade com a flag desligada** — emitir pedido, conferir por SQL que a `ContaPagar`
  nasce igual à de hoje, `liberada`, e que `pagar_conta` não mudou de comportamento;
- a tríade incompleta **recusa** a baixa, e a mensagem nomeia a perna que falta;
- a liberação **reajusta** o valor para o atestado, e registra a diferença;
- quem montou o lote **não** consegue fechá-lo;
- adiantamento pago aparece na lista "aguardando entrega" e **some dela** no atesto;
- adiantamento parcial (D4): duas linhas, o atesto baixa as duas;
- nota duplicada recusa; nota sem `chave_acesso` **passa**;
- divergência dentro e fora da tolerância;
- excluir recebimento de pedido com conta liberada recusa.

E o **teste-guarda** no formato da C9 da Fase 1: varre o repositório inteiro atrás de
`ContaPagar(` fora do serviço. São **cinco** os pontos de criação hoje, e só um é compra:

| Ponto | É compra? |
|---|---|
| `compras_views.py:305` | **sim** — é este que a fase move para o serviço |
| `custos_escritorio_views.py:25` | não — custo de escritório |
| `event_manager.py:1719` | não — handler de evento |
| `financeiro_service.py:46` | não — lançamento avulso pela tela |
| `services/importacao_excel.py:2414` | não — import de planilha, e nasce já `PAGO` |

O teste tem de carregar essa lista **por escrito**, para que a próxima criação em caminho
de compra apareça como falha em vez de passar despercebida. É o que a C9 provou valer: ela
revelou um quarto ponto de carimbo de regime que ninguém sabia que existia.

---

## Runbook — ligar a flag num tenant

```bash
# 0. Onde o tenant está hoje. O regime de recebimento é PRÉ-REQUISITO DURO —
#    sem ele a conta do Fluxo A nasce bloqueada sem caminho para liberar.
python scripts/flag_recebimento_atesto.py <ID>
python scripts/flag_financeiro_dois_fluxos.py <ID>

# 1. Ligar. Recusa tenant sem recebimento_atesto_ativo; --forcar existe, mas
#    leia o motivo antes de usá-lo.
python scripts/flag_financeiro_dois_fluxos.py <ID> --ligar

# 2. O ciclo completo numa obra piloto, com TRÊS pessoas diferentes:
#    quem emite o pedido, quem monta o lote, quem fecha o lote.
#    Conferir, em ordem:
#      a) emitir  -> ContaPagar nasce situacao_liberacao='bloqueada'
#      b) pagar   -> RECUSA, nomeando a perna que falta
#      c) atestar -> valor_atestado > 0
#      d) lançar nota
#         ← 17/08: TEM TELA. /compras/<pedido_id>/nota, ou o botão "Notas
#           fiscais" no painel de liberação da tela do pedido. Até o fecho
#           desta data o passo só era executável por
#           `services.financeiro_compra.lancar_nota` no shell, e quem rodou
#           este runbook em 15/08 o contornou assim.
#      d2) liberar -> botão na tela do pedido, quando a tríade fecha.
#           ← 17/08: o passo que FALTAVA nesta lista. `liberar()` existia,
#           estava testado e não tinha chamador de produção nenhum: a conta
#           ficava bloqueada para sempre e o runbook não notava, porque
#           pulava direto de "lançar nota" para "montar o lote".
#           Com perna aberta o botão vira "Liberar com ressalva" e exige
#           justificativa de 15+ caracteres (D6) — a conta sai no sensor,
#           marcada, e NÃO conta como drift.
#      e) montar o lote e pedir a OUTRA pessoa que feche
#      f) o valor da conta caiu para o atestado, com a diferença na observação
#      g) pagar   -> passa

# 3. O sensor, depois do piloto e depois em cada rodada:
python scripts/verificar_consistencia_financeiro.py <ID>
```

| O que conferir | Onde | O que significa se estiver errado |
|---|---|---|
| `situacao_liberacao` da conta nova | `conta_pagar` | `liberada` no Fluxo A = o carimbo do fluxo não pegou |
| `fluxo_pagamento` do pedido novo | `pedido_compra` | `faturado` num pedido de adiantamento = a tela não mandou a escolha |
| `fechado_por_id` do lote | `fechamento_pagamento` | NULL = alguém fechou por SQL, e a segregação não valeu |
| Saída do sensor | script acima | qualquer linha = escrita por fora do serviço |

### Rollback

```bash
python scripts/flag_financeiro_dois_fluxos.py <ID> --desligar
```

Pedido novo volta a nascer `faturado` e a conta nova volta a nascer `liberada`,
no mesmo minuto. **Mas as contas que já nasceram bloqueadas continuam
bloqueadas** — o regime é carimbado na linha, e desligar a flag não reescreve o
passado. Libere-as pela tela (fechando o lote) antes de considerar o rollback
completo; o sensor lista quais são.

O adiantamento já registrado também não some: ele é a prova de que houve
dinheiro adiantado, e some só quando o atesto chegar.

---

## Fora de escopo

As regras novas de alçada (as 4 condições que sobem um degrau, anti-fracionamento,
emergência 48h, corte de 3 cotações); urgência na SC; condição de pagamento estruturada no
mapa; o status unificado de 9 etapas; os 5 relatórios. São as Fases 3, 4 e 5 do ciclo.

Também fora: **convergir a `NotaFiscal` legada** do import de XML com a
`nota_fiscal_pedido` desta fase, e **consertar o UNIQUE global de `chave_acesso`**. As duas
são dívida conhecida e nenhuma é pré-requisito daqui — mas quem fizer a convergência
depois deve começar por este parágrafo.
