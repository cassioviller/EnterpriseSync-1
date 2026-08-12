# Plano de execução — Correções da Fase 1 (recebimento e atesto) — 2026-08-12

**O que é.** O plano de correção dos 15 defeitos que a revisão em nível `max` confirmou
no branch `feat/recebimento-atesto`, antes de a fase ser mesclada e de a flag ser ligada
em tenant real. O spec `docs/superpowers/specs/2026-08-11-recebimento-atesto-design.md`
continua sendo a fonte das decisões de desenho; **quando divergirem, o spec vence** — e
onde este plano muda o spec, a rodada correspondente diz que o spec tem de ser atualizado
junto.

**Achados de origem.** Revisão multi-agente, run `wf_46975365-805`. Cópia integral dos 15
achados com cenário de falha em
`scratchpad/code-review-notes/01-ACHADOS.md`. Cada rodada abaixo cita os
achados que fecha pelo número que eles têm lá.

**Por que agora.** Dois defeitos (C2 e C1) tornam o regime novo **pior** que o antigo para
quem ligar a flag: um cria estoque fantasma permanente, o outro descarta silenciosamente
o que o conferente digitou. Nenhum deles é de borda, e nenhum aparece como erro na tela.
Ligar a flag antes de C1–C4 é ligar um sistema que mente sobre estoque.

---

## As fronteiras

1. **Mesmo branch.** `feat/recebimento-atesto` não foi empurrado e a fase não está em
   produção: a correção pertence à entrega, não a um branch de conserto. `main` continua
   parada até o Cássio mandar.
2. **Âncoras por símbolo + literal**, nunca por número de linha.
3. **Red-first**: nenhum passo de implementação sem ver o teste vermelho antes. Todo
   achado desta lista existe porque um teste *quase* o cobria — o de C2 afirmava
   `entradas == []` e não olhou a saída pareada. Teste que não mata a mutação não conta.
4. **O contrato da flag não muda.** Com `recebimento_atesto_ativo` desligada, o sistema
   se comporta exatamente como hoje. Toda correção aqui vive dentro do regime novo ou é
   neutra para os dois.
5. **Uma rodada, um commit.** Reverter uma correção não pode arrastar as outras.

## Decisões tomadas com o Cássio antes de escrever este plano

| Questão | Decisão |
|---|---|
| A SAÍDA de consumo que sumiu (achado 1) | **Espelhar no atesto**: o par ENTRADA+SAÍDA passa a nascer do recebimento. Só muda o momento — que era o contrato da fase. Custa uma coluna e uma migration para o estorno saber o que desfazer |
| O campo de quantidade (achados 2 e 3) | **`type="number"` + parser estrito.** O navegador normaliza o que o teclado do celular produz; o servidor recusa com mensagem explícita o que não entender, em vez de virar zero e sumir |
| Pedido sem obra (achado 5) | **Autorizar por papel no tenant** quando `obra_id is None`. O eixo de obra continua valendo quando há obra |

---

## Ordem e independência

```
C1 (parser de quantidade)          ─┐
C2 (saída pareada + data do fato)  ─┼─> C3 (exclusão: rota + guard do pedido)
C4 (estado do pedido: aprovação)   ─┤
C5 (autorização: sem obra + botão) ─┤
C6 (encerrar saldo com zero itens) ─┤
C7 (sobre-entrega com justificativa)┤
C8 (verdade na tela)               ─┤
C9 (teste-guarda abrangente)       ─┘
                                    └─> Gate final
```

**Só C3 tem dependência real** (o estorno precisa saber da saída que C2 criou). As outras
oito são independentes entre si — o que limita o serial a C2→C3 e deixa o resto livre
para ser feito na ordem que der. A ordem escrita abaixo é por **risco decrescente**, para
que uma interrupção no meio deixe pronto o que mais importa.

**C1 a C4 são o gate de merge.** C5 a C9 podem entrar depois do merge sem risco de estoque
errado — mas não antes de a flag ser ligada em tenant real, porque C5 e C6 são becos sem
saída para o usuário.

---

## C1 — O que o conferente digita é o que fica gravado

**Fecha os achados 2, 3 e 4.** Três sintomas, uma função: `_quantidade_do_form` em
`compras_views.py` transforma erro de digitação em silêncio.

- [x] **Step 1 (red):** testes de unidade do parser e de rota:
  - `"3O"`, `"30 sacos"`, `"30.5.0"` → **recusa com mensagem** nomeando o item, e
    **nada é gravado** (hoje: vira `Decimal('0')`, é filtrado da lista, e o recebimento
    é gravado sem aquele item, com flash verde);
  - `"1.500"` → 1500, não 1,5 (hoje: 1,5, com `valor_atestado` 1000× menor);
  - `"30,5"` → 30,5 — o caminho que já funciona não pode regredir;
  - `POST` com `qtd_<id>=nan` e `=infinity` → mensagem de regra, **não** HTTP 500
    (hoje: `InvalidOperation` não capturada em `_validar_linhas`, sessão sem rollback);
  - campo vazio continua significando "não veio nesta entrega".
- [x] **Step 2:** parser estrito em `compras_views._quantidade_do_form`, devolvendo
  `(quantidade, erro)` em vez de engolir: entrada não vazia e não interpretável vira
  erro nomeado, nunca zero. Aceita vírgula decimal e ponto de milhar; recusa NaN/inf
  explicitamente (`Decimal.is_finite()`).
- [x] **Step 3:** o campo em `templates/compras/recebimento.html` vira
  `type="number" step="0.001" min="0"`. É o que tira a ambiguidade na origem: o
  navegador entrega valor canônico e o teclado do celular continua numérico.
- [x] **Step 4 (defesa em profundidade):** `_validar_linhas` em
  `services/recebimento_pedido.py` recusa quantidade não finita **antes** de comparar
  com zero. O serviço é o chokepoint; ele não pode depender de a rota ter limpado o dado.
- [x] **Step 5 (green + mutação):** verdes. Mutação: fazer o parser devolver `0` no
  lugar do erro e confirmar que o teste do `"3O"` **mata** a mutação.
- [x] **Step 6:** commit — `fix(compras): quantidade recebida invalida recusa em vez de sumir`

## C2 — A SAÍDA de consumo volta, no momento certo

**Fecha os achados 1 e 11.** O passo de maior risco, como a R4 foi no plano original: o
guard de emissão devolve `[]` e, com isso, os dois chamadores deixam de gerar a **saída
pareada** que derivavam de `movs_entrada`. O lote nasce `DISPONIVEL` e nunca é consumido.

A regra de espelhamento, tirada dos dois chamadores atuais:

| Situação do pedido | Regime antigo (emissão) | Regime novo (atesto) |
|---|---|---|
| Normal **com** obra | ENTRADA + SAÍDA "Consumo direto na obra" | idem, na quantidade recebida |
| Normal **sem** obra | só ENTRADA (fica em estoque) | idem |
| `aprovacao_cliente` | ENTRADA + SAÍDA "Consumo faturamento direto" | idem |

- [x] **Step 1 (red):** os testes que definem a virada:
  - pedido **com obra**, atesto de 30 de 50 → ENTRADA de 30 **e** SAÍDA de 30, lote
    `CONSUMIDO` com `quantidade_disponivel` 0 (hoje: só a ENTRADA, lote `DISPONIVEL`);
  - pedido **sem obra** → só ENTRADA, lote `DISPONIVEL` — o caso que deve continuar
    diferente;
  - `tipo_compra='aprovacao_cliente'` → o par, com a descrição de faturamento direto;
  - a SAÍDA carrega `pedido_compra_id`, `obra_id` e `admin_id` do pedido — o handler
    `material_entrada` do EventManager dedup por eles;
  - **paridade com o regime antigo**: mesmo pedido, mesma obra, mesmos itens, com e sem
    a flag → o conjunto de movimentos ao fim do ciclo é o mesmo, só muda o instante. É
    este o teste que faltava, e é ele que fecha o achado.
  - `data_movimento` da ENTRADA **e** da SAÍDA = `recebimento.data_recebimento`, não a
    data do registro (achado 11: caminhão de sábado lançado na segunda cai em agosto).
- [x] **Step 2:** coluna `recebimento_pedido_item.almoxarifado_saida_movimento_id`
  (FK, nullable) + `migration_285_saida_do_atesto` em `migrations.py`. ⚠️ Conferir
  `migration_history` no dev **antes** de fixar o 285 — é a lição registrada na B6.1 e a
  última do repositório é a 284. Sem backfill: recebimento gravado antes desta correção
  não tem saída para apontar, e `NULL` descreve exatamente isso.
- [x] **Step 3:** `_lancar_no_estoque` passa a gerar o par conforme a tabela acima,
  gravando o id da saída na linha do recebimento e propagando `data_recebimento` para
  `data_movimento` dos dois movimentos.
- [x] **Step 4:** deixar `_gerar_saida_almoxarifado` (compras_views) e o novo caminho
  com a mesma forma de saída — mesma descrição, mesmo `lote`, mesmo `estoque_id`. Se der
  para o serviço reusar a função da view sem importar meia view, reusar; se não der,
  **um comentário em cada lado apontando para o outro**, porque são a mesma regra em dois
  lugares e a próxima pessoa precisa saber disso.
- [x] **Step 5 (green + mutação):** verdes. Mutação: gerar a saída também para pedido sem
  obra e confirmar que o segundo teste **mata** a mutação.
- [x] **Step 6:** atualizar a seção "Como fica" do spec — o regime novo passa a gerar o
  par, e o spec hoje descreve só a ENTRADA.
- [x] **Step 7:** commit — `fix(compras): o atesto gera a saida de consumo que a emissao gerava`

## C3 — A exclusão volta a ser possível, e a do pedido para de mentir

**Fecha os achados 7 e 12.** Depende de C2: com a saída pareada, o lote nasce `CONSUMIDO`
e o guard `_ja_teve_saida` passaria a bloquear **toda** exclusão de recebimento — a
correção de C2 quebra a R5 se esta rodada não vier junto.

- [x] **Step 1 (red):**
  - excluir um recebimento que gerou o par ENTRADA+SAÍDA → os **dois** movimentos somem,
    o lote some, e a situação recalcula (hoje, depois de C2: recusa dizendo que o
    material já teve saída — falso, a saída é dele mesmo);
  - excluir quando alguém **de fora** consumiu o lote → continua recusando (é o teste da
    R5 que não pode regredir);
  - `GET`/`POST` da rota nova de exclusão: quem tem papel exclui, `LEITOR` recebe 403,
    e a exclusão de um recebimento que não é o último recusa com a mensagem do serviço;
  - excluir **pedido** com recebimento gravado → **recusa explícita**, dizendo quantos
    recebimentos existem e que é preciso excluí-los primeiro (hoje: apaga a trilha de
    atesto por cascade e deixa ENTRADA, SAÍDA e lote órfãos, com `pedido_compra_id` NULL
    por `ON DELETE SET NULL`).
- [x] **Step 2:** `_ja_teve_saida` passa a ignorar a saída pareada do próprio
  recebimento (é para isso que a coluna de C2 existe), e o estorno apaga a saída e
  devolve o lote a `DISPONIVEL` **antes** de avaliar o guard. Validar tudo antes de
  apagar qualquer coisa continua valendo.
- [x] **Step 3:** rota `POST /compras/<pedido_id>/recebimento/<recebimento_id>/excluir`
  chamando `excluir_recebimento`, e o botão no detalhe do pedido, com confirmação,
  listando o rótulo (`PC-1234/2`). Sem rota, o serviço da R5 é código morto — e o
  docstring dele diz, corretamente, que errar a quantidade é o erro mais comum de quem
  recebe caminhão no portão.
- [x] **Step 4:** guard na rota `compras.excluir`: pedido com `situacao_recebimento`
  diferente de `nao_recebido` recusa. Todos os guards de `excluir_recebimento` ficam
  contornados por aquela porta hoje.
- [x] **Step 5 (green + mutação):** verdes. Mutação: remover o guard da rota `excluir` e
  confirmar que o teste do pedido com recebimento **mata** a mutação.
- [x] **Step 6:** commit — `feat(compras): excluir recebimento pela tela, e o pedido para de apagar a trilha`

## C4 — Não se atesta o que o cliente ainda não aprovou

**Fecha o achado 5** (numeração da revisão: aprovação do cliente). No regime antigo o
estoque de `tipo_compra='aprovacao_cliente'` só existia depois do aceite no portal. No
regime novo qualquer papel de obra atesta antes, e nada reverte se o cliente recusar.

- [x] **Step 1 (red):**
  - `GET` da tela de recebimento num pedido `aprovacao_cliente` ainda
    `AGUARDANDO_APROVACAO_CLIENTE` → recusa com a razão dita, sem 403 cru;
  - `registrar_recebimento` no mesmo pedido → `RecebimentoInvalido` (o serviço é o
    chokepoint: bloquear só na rota deixa o CLI e o job passando);
  - depois do aceite → atesta normalmente;
  - pedido `normal` não é afetado por nenhuma das duas checagens.
- [x] **Step 2:** a checagem de estado no serviço, junto das outras validações de
  `registrar_recebimento`, e a mensagem correspondente na rota.
- [x] **Step 3 (green + mutação):** verdes. Mutação: aceitar `RECUSADO` como estado
  válido e confirmar que o primeiro teste mata.
- [x] **Step 4:** commit — `fix(compras): atesto exige a aprovacao do cliente quando ela existe`

## C5 — Ninguém fica sem caminho: pedido sem obra, e botão que não engana

**Fecha os achados 6 e 15.** Dois lados da mesma pergunta — quem pode receber?

- [x] **Step 1 (red):**
  - pedido **sem obra** no regime novo: ADMIN do tenant atesta (hoje: 403, inclusive
    para o dono do tenant, porque `papel_de_usuario_na_obra(u, None)` devolve `None`);
  - `LEITOR` do tenant, no mesmo pedido sem obra, **continua** recusado;
  - pedido **com** obra: nada muda — o eixo de obra continua mandando;
  - o detalhe de um pedido do regime novo **não** mostra o botão "Registrar Recebimento"
    para quem a rota recusaria (hoje: mostra, e o clique dá 403 cru).
- [x] **Step 2:** `usuario_pode_receber_na_obra` com `obra_id is None` passa a decidir
  pelo papel no tenant. A regra fica em `utils/autorizacao.py`, junto das outras — não
  na rota, senão o serviço diverge dela.
- [x] **Step 3:** o detalhe passa a consultar a permissão antes de renderizar o botão,
  como os outros botões de compras já fazem.
- [x] **Step 4 (green):** verdes.
- [x] **Step 5:** commit — `fix(compras): pedido sem obra tem quem atesta, e o botao respeita o papel`

## C6 — "O resto não vem" sem inventar quantidade

**Fecha o achado 8.** Hoje encerrar o saldo exige informar ao menos um item recebido — e
a única alternativa que a tela oferece é aceitar o valor pré-preenchido, registrando
material que nunca chegou.

- [x] **Step 1 (red):**
  - recebimento com zero itens e `encerra_saldo=True` + motivo → **grava**, situação
    `encerrado_com_saldo`, **zero** movimentos de estoque;
  - recebimento com zero itens e `encerra_saldo=False` → continua recusando ("recebimento
    vazio não é atesto de nada" segue valendo para o caso comum);
  - pedido em que **nada** chegou e o fornecedor cancelou → `encerrado_com_saldo`, não
    `nao_recebido`;
  - `valor_atestado` de um pedido encerrado sem nenhum item recebido = 0.
- [x] **Step 2:** `_validar_linhas` aceita lista vazia quando `encerra_saldo` (o motivo
  já é obrigatório, e é ele que explica o fato seis meses depois).
- [x] **Step 3:** reordenar `situacao_para`: encerramento passa a ser perguntado **antes**
  de "nada recebido" e **depois** de "tudo completo". A ordem das perguntas é a regra, e o
  docstring dela tem de ser atualizado junto.
- [x] **Step 4:** conferir `scripts/verificar_consistencia_recebimento.py` contra a ordem
  nova — o sensor reusa `situacao_para` de propósito, mas o teste dele fixa cenários.
- [x] **Step 5 (green + mutação):** verdes. Mutação: voltar a ordem antiga em
  `situacao_para` e confirmar que o teste do pedido cancelado mata.
- [x] **Step 6:** commit — `feat(compras): encerrar o saldo sem inventar quantidade recebida`

## C7 — Sobre-entrega com justificativa, como o spec prometeu

**Fecha o achado 10.** `permitir_sobre_entrega` desliga o teto de **todas** as linhas e não
pede justificativa nenhuma — contra a própria mensagem de erro que manda "marcar a
sobre-entrega e justificar", e contra o spec. Compare com `encerra_saldo`, que recusa sem
motivo.

- [x] **Step 1 (red):**
  - sobre-entrega marcada **sem** justificativa → recusa, no molde da recusa do
    encerramento sem motivo;
  - sobre-entrega marcada **com** justificativa → grava, e a justificativa fica na
    `observacao` do recebimento;
  - a mensagem de sucesso (ou o próprio erro, quando houver) **nomeia os itens** que
    passaram do pedido — é o que faz o 500 digitado por engano aparecer para quem digitou.
- [x] **Step 2:** a validação no serviço e o campo de justificativa na tela, aparecendo
  junto da caixa, como o par motivo/encerramento já faz.
- [x] **Step 3 (green):** verdes.
- [x] **Step 4:** commit — `fix(compras): sobre-entrega exige justificativa e nomeia o que estourou`

## C8 — A tela para de mentir

**Fecha os achados 9 e 14.** Dois textos errados, nenhum deles inofensivo.

- [x] **Step 1 (red):**
  - `templates/compras/recebimento.html` mostra "Pedido: 50", não "Pedido: 5E+1"
    (`Decimal('50.000').normalize()` sai em notação científica para todo número redondo —
    100 vira `1E+2`, 1200 vira `1.2E+3`);
  - emissão de pedido com `exige_atesto` **não** afirma que a entrada no almoxarifado foi
    gerada; emissão de pedido legado continua afirmando, palavra por palavra.
- [x] **Step 2:** o template passa a usar o helper `_num_enxuto` que a própria rota já
  criou para isso (expor como filtro ou passar o dicionário pronto — decidir na hora, pelo
  que ficar mais legível).
- [x] **Step 3:** o flash da emissão passa a descrever o que de fato aconteceu, e a dizer
  o próximo passo ("o estoque entra quando o recebimento for atestado").
- [x] **Step 4 (green):** verdes.
- [x] **Step 5:** commit — `fix(compras): a tela para de mentir sobre quantidade e sobre estoque`

## C9 — O teste-guarda passa a guardar o repositório inteiro

**Fecha o achado 13.** `test_todo_ponto_que_cria_pedido_carimba_o_regime` abre exatamente
`compras_views.py` e diz proteger contra "um terceiro ponto de criação nascer sem decidir
sobre o regime". O terceiro ponto **já existe**: `views/obras.py` (`nova_compra_obra`)
constrói `PedidoCompra` sem carimbar, e o teste passa verde.

- [ ] **Step 1 (red):** o teste passa a varrer **todo** `.py` do repositório (excluindo
  `tests/`, `.pythonlibs/`, `archive/`) e falha nomeando arquivo e linha de cada
  construção sem carimbo. Rodar e **ver vermelho em `views/obras.py`** — se ficar verde,
  a varredura está errada, não o código.
- [ ] **Step 2:** carimbar o regime em `views/obras.py`, via `regime_do_tenant(admin_id)`,
  como os outros dois pontos fazem. ⚠️ Esse caminho **nunca** gerou movimento de estoque
  (os itens que ele cria não têm `almoxarifado_item_id`): carimbar `exige_atesto=True` ali
  dá ao pedido um documento de recebimento e um `valor_atestado` utilizável pela fase
  financeira, sem mudar nada no almoxarifado. Confirmar isso por teste antes de assumir.
- [ ] **Step 3 (green):** verde, e a mensagem de falha do teste tem de ser legível o
  bastante para quem criar o quarto ponto entender o que fazer.
- [ ] **Step 4:** commit — `test(compras): o guarda do carimbo de regime varre o repositorio inteiro`

---

## Gate final

- [ ] `tests/test_recebimento_atesto.py` inteiro verde, com a contagem nova de testes
      registrada aqui (eram 51).
- [ ] Suítes vizinhas sem regressão: `-k "compra or almoxarifado or requisicao"` — eram
      90 verdes. (Playwright continua dando erro de ambiente por falta de navegador neste
      host, antes e depois.)
- [ ] **A paridade, conferida por SQL cru num tenant de dev**: mesmo pedido, mesma obra,
      mesmos itens, emitido e recebido com a flag **desligada** e depois com a flag
      **ligada** → o conjunto final de movimentos (ENTRADA, SAÍDA, lote, status) é o
      mesmo, só muda o instante. É o gate que faltava na fase original.
- [ ] Ciclo completo com a flag ligada: emitir (zero movimentos) → receber parcial → o
      par ENTRADA+SAÍDA com `data_movimento` = data do recebimento → **excluir o
      recebimento pela tela** e ver os dois movimentos e o lote sumirem → receber de novo
      → encerrar saldo sem informar quantidade.
- [ ] Pedido **sem obra** com a flag ligada: ADMIN atesta, o lote fica `DISPONIVEL`,
      `LEITOR` é recusado.
- [ ] Pedido `aprovacao_cliente`: atesto recusado antes do aceite, aceito depois.
- [ ] Tentativa de excluir um pedido com recebimento gravado → recusa; nenhum movimento
      órfão no banco.
- [ ] `scripts/verificar_consistencia_recebimento.py` sem drift nas obras de dev
      (admins 1, 6793, 3510 — exit 0), incluindo um pedido encerrado sem item recebido.
- [ ] Spec atualizado onde este plano o mudou: a seção "Como fica" (C2) e a ordem das
      perguntas de `situacao_para` (C6).
- [ ] Uma releitura do runbook do spec: ele manda conferir "um `ENTRADA` de 30" depois do
      recebimento parcial, e a partir de C2 a resposta certa passa a ser o par.

## Riscos

| Risco | Mitigação |
|---|---|
| C2 mexe no almoxarifado de novo, e é a segunda vez nesta fase | Tudo dentro de `exige_atesto`. O teste de paridade do gate é o que prova que o tenant sem flag não mudou — é mais forte que o `entradas == []` que deixou o defeito passar |
| C2 quebrar a R5 (todo lote nasce `CONSUMIDO`) | É exatamente o que C3 existe para resolver, e por isso C3 é a única dependência serial do plano. Não mesclar C2 sem C3 |
| Número da migration 285 colidir com o dev | Conferir `migration_history` antes de fixar (lição da B6.1, repetida na R1) |
| A saída pareada virar uma terceira cópia da mesma regra | C2 Step 4: reusar, ou comentar dos dois lados apontando um para o outro |
| C9 revelar um quarto ponto de criação que ninguém conhecia | Melhor descobrir na varredura do que num tenant com a flag ligada. Se aparecer, decidir o regime dele na mesma rodada |
| Corrigir tudo e ligar a flag no mesmo dia | Não fazer. O gate pede o ciclo completo em dev primeiro, e o runbook do spec continua sendo o caminho de ligar em tenant real |
