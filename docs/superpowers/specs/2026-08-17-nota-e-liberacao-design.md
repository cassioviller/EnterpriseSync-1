# A nota e a liberação — o Fluxo A ganha as duas telas que faltam

**Data:** 2026-08-17
**Origem:** conferência do fluxo de compras ponta a ponta, pedida em 17/08 depois do merge
das alçadas em `main`.
**Escopo:** fechar **pela tela** as duas ações que a Fase 2 do ciclo entregou só como
serviço — lançar a nota fiscal do pedido e liberar a conta para pagamento. Não é a Fase 4
do ciclo: é o fecho da Fase 2, e ele vem antes porque a régua de 9 etapas da Fase 4 teria
de representar dois passos que hoje não existem em tela nenhuma.

---

## ⚠️ Este spec não conserta código faltando. Conserta caminho faltando.

O código dos dois atos existe, está testado e está correto. O que não existe é rota,
template e botão. Leia isto antes de dimensionar a fase, porque o instinto ao ver
"lançar nota fiscal" é orçar um módulo de NF-e, e não é disso que se trata.

📖 17/08, conferido por varredura em todo `.py` do repositório (fora de `archive/`):

| Função | Onde | Chamadores de produção |
|---|---|---|
| `criar_obrigacao(pedido)` | `services/financeiro_compra.py:102` | 1 — `compras_views.py:403` |
| `pernas_faltantes(pedido)` | `:252` | 2 — `financeiro_views.py:512` e o sensor |
| **`lancar_nota(...)`** | `:168` | **0** — só `tests/` |
| **`liberar(pedido)`** | `:310` | **0** — só `tests/` |

📖 `NotaFiscalPedido` (`models.py:5962`) não é referenciada fora de `models.py` e do próprio
serviço: nenhuma view, nenhum template, nenhuma rota.

## Por que existe — a conta que nasce bloqueada e não tem por onde sair

📖 `situacao_liberacao_inicial` (`services/financeiro_compra.py:95-99`) faz **toda**
`ContaPagar` do Fluxo A do regime novo nascer `'bloqueada'`. 📖 `financeiro_views.py:506`
recusa a baixa dessa conta e diz, com todas as letras:

> *"Esta conta ainda não foi liberada para pagamento: sem nota fiscal lançada; sem atesto
> de recebimento. Complete a tríade (pedido, nota e atesto) e libere antes de dar baixa."*

Das três pernas, **o atesto tem tela** (`/compras/<pedido_id>/recebimento`, Fase 1) e o
pedido é o próprio fato. A nota não tem. E mesmo com as três fechadas, `liberar()` — que é
quem vira a chave — não tem botão.

**Consequência:** ligar `financeiro_dois_fluxos_ativo` em qualquer tenant produz contas a
pagar que ninguém consegue pagar pelo sistema. A Fase 2 está completa no serviço e é
**inoperável pela tela**. Não é incidente de produção: 🔬 14/08 a flag não está ligada em
tenant real nenhum. É o motivo pelo qual ela não pode ser ligada.

### Como isto passou por um gate verde e um runbook executado

Vale registrar, porque é a terceira vez que a mesma coisa acontece e as três têm a mesma
forma:

1. 📖 O plano da Fase 2 tem os steps **F3** (o serviço: `criar_obrigacao`, `lancar_nota`,
   `liberar`, `pernas_faltantes`) e **F4** (a guarda em `pagar_conta`). **Não tem step de
   tela** para nenhum dos dois atos. O Fluxo B ganhou o seu — 📖 F6 step 4, *"a tela da
   lista, na obra e no financeiro"*. O Fluxo A não, e ninguém notou porque cada step
   fechou verde no que ele mesmo prometia.
2. Os testes chamam o serviço direto (`from services.financeiro_compra import lancar_nota`),
   que é o certo para testar regra — e é exatamente por isso que eles não veem a ausência
   da rota.
3. 📖 O runbook das alçadas **já admitia o buraco**, no passo 3e(ii):
   *"nota por `services.financeiro_compra.lancar_nota` — a nota ainda não tem tela
   própria"*. Estava escrito como instrução de conferência, e não como pendência: quem
   executou o runbook contornou pelo shell e seguiu.

É a mesma classe do 🔴 achado em 15/08 (`pode_ratificar` recusando a requisição que já
virara pedido): **serviço completo, tela incompleta, suíte cega para a diferença**. A
diferença é que aquele foi achado rodando o runbook, e este só apareceu quando alguém
perguntou pelo fluxo inteiro em vez de por uma fase.

---

## O que falta, exatamente

| # | O quê | Onde entra |
|---|---|---|
| 1 | Tela de notas do pedido: lista o que já foi lançado, lança mais uma | rota nova `/compras/<pedido_id>/nota` |
| 2 | Excluir nota lançada errada | rota nova, só enquanto a conta não liberou |
| 3 | Botão de liberar, com o que falta escrito ao lado | `templates/compras/detalhe.html` + rota nova |
| 4 | A porta de escape do **D6 da Fase 2**, decidida em 14/08 e **nunca construída** | `liberar(..., justificativa=...)` |
| 5 | O painel da tríade na tela do pedido | `detalhe.html`, consumindo `pernas_faltantes` |

O item 4 merece o destaque. 📖 O spec da Fase 2 decidiu, em D6:

> *"A nota fiscal é obrigatória para liberar? **Recomendado: sim no Fluxo A, com uma porta
> de escape auditável**: liberar sem nota exige justificativa escrita, fica registrado em
> `liberada_por_id`/observação e aparece num relatório de exceções."*

📖 `liberar()` hoje levanta `TriadeIncompleta` sem exceção possível — a porta de escape não
existe na assinatura (`liberar(pedido, *, usuario=None)`). A decisão foi tomada e a metade
que a torna operável ficou de fora. **Fornecedor pequeno que emite a nota semanas depois
existe**, e sem a porta ele trava o pagamento de material que já chegou e já foi conferido.

---

## Modelo de dados

### `conta_pagar.liberacao_justificativa` — a exceção que dá para consultar

`TEXT`, nullable. **Não-nulo significa liberação excepcional** — a conta foi liberada com
uma perna aberta, e o texto diz por quê, escrito por quem liberou.

Uma coluna e não duas (`liberada_sem_nota` booleana + texto) porque o booleano seria
derivável do texto e as duas poderiam divergir. Quem pergunta "quais contas foram liberadas
por exceção este mês" pergunta `WHERE liberacao_justificativa IS NOT NULL`, e a resposta não
depende de ninguém ter lembrado de marcar a caixa.

Não é `observacoes`: 📖 `liberar()` já escreve `[liberação]` e `[divergência]` ali como
texto livre (`:353` e `:357`), e um relatório de exceções que faça `LIKE '%[exceção]%'` numa
coluna de 2000 caracteres é a definição de sensor que ninguém confia.

`liberada_por_id` e `liberada_em` **já existem** e já são gravados (`:362-363`). Nada mais é
criado — nem tabela, nem enum, nem flag. A fase inteira cabe numa coluna.

### O que deliberadamente NÃO ganha coluna

**O arquivo da nota.** 📖 `NotaFiscalPedido.arquivo_path` já existe e continua nulo — ver
D4. O campo está no modelo desde a migration **287**; o que falta é onde gravar o arquivo, e
isso é infra, não schema.

---

## Fluxo, com a flag ligada

Antes e depois, no mesmo pedido do Fluxo A:

| Passo | Hoje | Com esta fase |
|---|---|---|
| Emitir pedido | `ContaPagar` nasce `bloqueada` | igual |
| Receber e atestar | tela da Fase 1 | igual |
| **Lançar a nota** | 🔴 só por `python -c` no shell | tela `/compras/<id>/nota` |
| **Ver o que falta** | só na recusa da baixa, depois de tentar | painel na tela do pedido, antes de tentar |
| **Liberar** | 🔴 não existe | botão, que só aparece quando a tríade fecha — ou com justificativa, quando não fecha |
| Pagar | recusado para sempre | passa |

O ponto do painel é esse "antes de tentar": 📖 hoje a única forma de descobrir o que falta é
ir até o financeiro, tentar pagar e ler o flash da recusa. Quem está na tela do pedido — que
é quem tem a nota na mão — não vê nada.

---

## As telas

### 1. `/compras/<int:pedido_id>/nota` — GET e POST

Uma tela só, no molde da de recebimento (`compras_views.py:1181`), e pelo mesmo motivo: quem
lança nota lança olhando o papel, e ir e voltar entre listar e criar é o que faz alguém
lançar o número errado.

**Guardas, na ordem** — a mesma sequência de `recebimento`, que já é o padrão da casa:

1. `_check_v2()`;
2. `PedidoCompra.query.filter_by(id=…, admin_id=…).first_or_404()` — tenant primeiro, e
   por filtro, não por `get()` seguido de comparação;
3. `abort(403)` se quem entrou não pode lançar (ver D1);
4. **recusa explicada** se o pedido não é do Fluxo A do regime novo: nota lançada num
   pedido que não tem tríade é linha órfã que não bloqueia nem libera nada. A recusa diz
   isso, com a razão — 📖 mesma decisão do `if not pedido.exige_atesto` em
   `compras_views.py:1214`, e pelo mesmo argumento: *"um no-op silencioso é pior que uma
   recusa"*.

**GET** mostra: as notas já lançadas (número/série, valor, emissão, quem lançou, quando), a
soma delas contra o `valor_atestado` e contra o valor do pedido, e o formulário.

**POST** chama `lancar_nota()` e trata `NotaDuplicada` como flash `warning`, não como 500 —
📖 a mensagem do serviço já é escrita para o operador (*"se for outra nota, confira o número
e a série no papel"*), então a rota só a repassa.

> 📌 **`chave_acesso` fica opcional, e isso não é economia de trabalho — é o desenho.**
> 📖 O docstring de `NotaFiscalPedido` (`models.py:5963`) já responde: *"metade das compras
> de obra chega com recibo, nota de serviço ou nota sem XML na mão do comprador: a tríade
> viraria uma trava que o campo aprende a contornar, e trava contornada é pior que trava
> ausente"*. A tela não exige a chave nem valida dígito.
>
> ⚠️ **Não confundir com o UNIQUE global.** Ele é da `NotaFiscal` **legada**
> (`models.py:2664`, `unique=True, nullable=False`), que veio do import de XML do
> almoxarifado. 📖 `nota_fiscal_pedido` **não tem UNIQUE em `chave_acesso`** — o único é
> `(admin_id, fornecedor_id, numero, serie)`, escopado por tenant como deve ser
> (migration 287). Convergir as duas tabelas segue como dívida, e não é pré-requisito
> desta tela.

> 🔴 **Uma armadilha na assinatura do serviço, achada ao escrever este spec.** 📖
> `lancar_nota` tem `usuario=None` como default e faz
> `lancada_por_id=getattr(usuario, 'id', None)` (`:197`) — mas a coluna é **NOT NULL**
> (`models.py:6015` e a migration 287). Chamar sem `usuario` não devolve erro de domínio:
> estoura `IntegrityError` e **aborta a transação inteira**, que é justamente o que o resto
> da função existe para evitar (📖 o comentário de `:173-177`). A rota sempre passa
> `current_user`, então a tela não cai nisso — mas o default mente sobre o contrato. Trocar
> por parâmetro obrigatório é uma linha e entra nesta fase, com teste.

### 2. `POST /compras/<pedido_id>/nota/<nota_id>/excluir`

Só enquanto a conta do pedido estiver `bloqueada` (ver D5). Depois de liberada, a nota é
premissa de um ato financeiro já praticado.

### 3. O painel da tríade + o botão, em `templates/compras/detalhe.html`

Entra ao lado do bloco de recebimento que já existe (`:26-50`), com a mesma forma: badge de
situação + ação. Três linhas — pedido ✅, nota, atesto — cada uma verde ou com a frase que
`pernas_faltantes` já devolve. **A tela não reimplementa a regra**: 📖 `pernas_faltantes` é
função pura e a docstring dela diz que dá para chamar de dentro do template sem medo.

O botão **Liberar para pagamento**:

- some para quem não pode liberar (D1);
- com a tríade fechada, é um POST direto;
- com perna aberta, abre o campo de justificativa e o texto muda para **"Liberar com
  ressalva"**. Nunca some — sumir é o que empurra o operador para o caminho de fora do
  sistema, que é a frase que a Fase 2 repete em três lugares.

### 4. `POST /compras/<pedido_id>/liberar`

Chama `liberar(pedido, usuario=current_user, justificativa=…)`. `TriadeIncompleta` vira
flash `warning` com a mensagem do serviço — que já nomeia a perna.

---

## Decisões — as cinco, fechadas em 17/08

🔬 **Ratificadas na sessão de 17/08, todas na recomendação.** Nenhuma task do plano de
execução espera resposta. O que **não** fecha junto é se elas descrevem a operação real —
quem for medir mede contra o campo, não contra este spec.

**D1 — Quem lança a nota e quem libera?**
*Recomendado:* **ADMIN do tenant para os dois atos**, ratificando o D2 da Fase 2 (*"fica
ADMIN; criar um `PapelObra.FINANCEIRO` aqui seria papel sem gente"*). Nada muda em
`utils/autorizacao.py`.

**D2 — Quem lança a nota pode liberar?**
*Recomendado:* **pode — as duas metades ficam registradas, e nenhuma é exigida contra a
outra nesta rodada.**

📖 O modelo já toma partido de metade da questão: `lancada_por_id` é comentado como
*"metade da segregação: quem lançou. A outra metade é quem liberou, e mora em
`ContaPagar.liberada_por_id`"* (`models.py:6013`). **Gravar as duas pontas está feito;
exigir que sejam pessoas diferentes é o que está em aberto** — e a recomendação é não
exigir, por dois motivos:

1. a segregação que já existe é geográfica e mais forte: 📖 quem atesta está na obra
   (`pode_receber_na_obra`) e quem libera está no escritório, e a tríade não fecha sem os
   dois;
2. exigir "quem lançou não libera" travaria todo tenant de um administrador só, e o efeito
   prático seria o uso **rotineiro** da ressalva do D3 — que existe para o caso raro.
   Segregação que obriga a exceção diária não é controle, é ruído.

Mesmo raciocínio já registrado na Fase 2 para o lote: exigir os dois lados só quando os dois
são conhecidos. Se depois a auditoria pedir a regra dura, ela é um `if` — e os dados para
medir quantas vezes ela morderia **já estão sendo gravados desde 14/08**.

**D3 — A porta de escape do D6 entra agora?**
*Recomendado:* **sim.** Foi decidida em 14/08 e nunca construída, e é ela que separa
"controle" de "trava". Regras: justificativa obrigatória de **no mínimo 15 caracteres**
(campo vazio e `"ok"` são a mesma coisa para quem for auditar), gravada em
`liberacao_justificativa`, e a conta sai no sensor. **A ressalva não vale para a emergência
48h não ratificada:** 📖 aquela perna não é da tríade — é a sanção da Fase 3, e liberar por
cima dela apagaria o único ponto onde o rito de emergência morde. `liberar()` recusa a
ressalva quando a perna aberta é a da emergência, e diz por quê.

**D4 — O upload do arquivo da nota entra agora?**
*Recomendado:* **não.** 📖 O padrão atual de upload em compras grava em
`static/uploads/compras` (`compras_views.py:45`) — que é exatamente o que a Fase 5 parou de
fazer, e o volume persistente é o 🔴 item humano nº 3, aberto desde julho. Anexo em
`static/` some no primeiro redeploy, e nota fiscal que some é pior que nota fiscal que nunca
foi anexada. `arquivo_path` continua nulo; o input entra quando o volume existir, e aí usa
`services/rdo_foto_service.caminho_absoluto`, que já resolve `UPLOADS_PATH`.

**D5 — Nota lançada errada: edita ou exclui?**
*Recomendado:* **exclui e lança de novo**, e só enquanto a conta estiver `bloqueada`. Nota
é documento externo — "editar" uma nota é reescrever o que o fornecedor emitiu. A exclusão
some com a linha e o `NotaDuplicada` volta a liberar o número, que é o que quem digitou
errado precisa.

---

## Casos de borda

| Situação | Comportamento |
|---|---|
| Pedido do regime antigo (`fluxo_pagamento` ≠ faturado, ou flag off) | a tela de nota **recusa com a razão dita** — não há tríade para alimentar |
| Nota lançada, atesto zero | painel mostra nota ✅ e atesto ✗; botão em "Liberar com ressalva" |
| Duas notas no mesmo pedido | somam; 📖 `valor_das_notas` já soma todas |
| Notas somam mais que o atestado, acima da tolerância | libera **e avisa**, com o aviso na observação — 📖 D1 da Fase 2, já implementado em `liberar():356` |
| Conta já paga | `liberar()` não a retoca — 📖 `:335`, já implementado |
| Liberar duas vezes | idempotente: sem conta aberta, `liberar()` devolve `[]` |
| Perna aberta é a emergência 48h | ressalva **recusada**, com a razão (D3) |
| Excluir nota de conta já liberada | recusado, com a razão |
| Tenant com a flag desligada | rota de nota recusa; painel e botão não aparecem. **Paridade: nada muda para quem não ligou** |

---

## Migrations

**308** — `conta_pagar.liberacao_justificativa TEXT NULL`.

> ⚠️ **308 e não 300.** 📖 17/08 a maior registrada em `migrations.py` é a **299** (Fase 3
> do ciclo). A faixa **300-307** é reservada da Fase 9 e **não foi aplicada** — numerar aqui
> como 300 armaria a colisão que a renumeração 270→277 existiu para evitar, e a segunda a
> rodar nunca rodaria, em silêncio. 290-295 segue reservada da Fase 8.

Uma migration, uma coluna, nullable, sem backfill: conta antiga não tem exceção a declarar.

---

## Testes

Red-first, no molde das fases anteriores. `tests/test_nota_e_liberacao.py`.

**Do serviço** (o que muda nele é só a assinatura de `liberar`):

- `liberar()` com `justificativa` e uma perna aberta **libera**, grava o texto em
  `liberacao_justificativa` e mantém `liberada_por_id`/`liberada_em`;
- `liberar()` com `justificativa` de menos de 15 caracteres **recusa**;
- `liberar()` com `justificativa` **recusa** quando a perna aberta é a emergência não
  ratificada, e a mensagem nomeia a emergência;
- sem `justificativa`, o comportamento de hoje é **byte-idêntico** — é o teste que impede
  esta fase de afrouxar a Fase 2;
- `lancar_nota` **sem `usuario`** recusa com erro de domínio, e não com `IntegrityError`
  (ver o 🔴 da seção das telas).

**Das rotas:**

- `GET /compras/<id>/nota` de outro tenant → **404** (filtro por `admin_id`, não `get()`);
- `POST` de quem não é ADMIN → **403**;
- pedido do regime antigo → redirect com a razão, e **nenhuma** `NotaFiscalPedido` criada;
- nota duplicada → flash `warning` e **200**, não 500;
- `POST /liberar` com a tríade fechada → conta vira `liberada` e a baixa passa **na mesma
  suíte** (é o teste que prova que o ciclo fecha ponta a ponta pela tela, e é o que faltou
  na Fase 2);
- excluir nota de conta liberada → recusa.

**De paridade:** tenant com a flag desligada — emitir → pagar produz os mesmos registros de
antes, conferido por `SELECT`. 📖 Mesmo teste que a F4 da Fase 2 já faz; aqui ele reroda
porque a coluna nova toca a mesma tabela.

**Mutação de sanidade:** fazer a rota de liberar ignorar `pernas_faltantes` e confirmar que
o teste da tríade incompleta morre.

**O teste-guarda que faltava.** Um teste que varre as rotas registradas e falha se
`lancar_nota` ou `liberar` voltarem a não ter chamador fora de `tests/`. É barato e teria
pego este buraco em 14/08 — a mesma ideia do guarda da C9 da Fase 2, que varre `.py` atrás
de `ContaPagar(` criado fora do serviço.

---

## Runbook — o que muda nos que já existem

Esta fase **não tem flag própria**: ela completa o caminho da
`financeiro_dois_fluxos_ativo`. Dois runbooks existentes ficam desatualizados no dia em que
ela entrar, e corrigi-los é parte da entrega:

1. 📖 `docs/superpowers/specs/2026-08-14-financeiro-dois-fluxos-design.md`, passo **2d** do
   runbook (*"lançar nota"*) — passa a ter tela e endereço.
2. 📖 `docs/superpowers/specs/2026-08-15-alcadas-design.md`, passo **3e(ii)** — a frase
   *"a nota ainda não tem tela própria"* fica **falsa**. Trocar pela tela, marcando a linha
   como as outras correções de execução daquele runbook.

E o sensor `scripts/verificar_consistencia_financeiro.py` ganha um achado:
**conta liberada com `liberacao_justificativa` preenchida** — não é defeito, é exceção, e
o sensor a lista para que ela seja lida por alguém uma vez por mês. Um sensor que só grita
erro nunca mostra o que foi decidido por fora da regra.

---

## Fora de escopo

**Os dois becos da requisição**, achados na mesma conferência de 17/08 e que **não** são
desta fase — mas ficam registrados aqui porque foram achados juntos:

1. 📖 **`REJEITADA` não tem volta pela tela.** Três camadas discordam:
   `services/requisicao_compra.py:78` permite `REJEITADA → RASCUNHO` com um comentário
   explicando o desenho (*"rejeitar não é matar"*); `models.py:89` diz que REJEITADA é
   **terminal**; e `templates/compras/requisicao_detalhe.html:385` só oferece "Cancelar".
   Quem manda hoje é a tela. A aresta é testada (`tests/test_fase3_requisicao.py:287`) e
   nenhuma rota a usa.
2. 📖 **Não há como editar item de requisição.** `RequisicaoCompraItem` só é criado em
   `compras_views.py:1846`, dentro do `nova_post`. Nem em RASCUNHO dá para acrescentar,
   corrigir ou remover — o que torna "corrige e reenvia" impossível mesmo se a aresta
   acima fosse ligada.

Os dois são a mesma fase, pequena, e ela deve vir **junta**: ligar a volta sem a edição
devolve a requisição a um estado que ninguém consegue mudar.

**Também fora:** a régua unificada de 9 etapas e os 5 relatórios (Fases 4 e 5 do ciclo);
urgência na SC; frete, validade da proposta e condição de pagamento estruturada no mapa —
📖 a condição existe como texto livre em `MapaFornecedor.condicoes_pagamento`, o que falta é
estruturá-la; convergir a `NotaFiscal` legada do import de XML com `NotaFiscalPedido`; e
consertar o **UNIQUE global de `chave_acesso`**, que é pré-requisito de exigir a chave nesta
tela e por isso está citado no 📌 acima.
