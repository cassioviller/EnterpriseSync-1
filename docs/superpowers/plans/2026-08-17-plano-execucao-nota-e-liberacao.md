# Plano de execução — A nota e a liberação — 2026-08-17

> **Estado em 2026-08-25 (varredura de fecho):** ✅ **FECHADO** — Fases 1–3 do ciclo de compras, entregues com runbook rodado por script. ⚠️ o code review de 25/08 achou defeitos vivos neste módulo — ver `docs/auditoria/achados-code-review-2026-08-25.md` §5. 🔬 5/5 dos arquivos prometidos existem na árvore.
>
> Não há trabalho pendente aqui. **As caixas `- [ ]` abaixo não foram marcadas de propósito:** elas são
> rascunho de execução, não registro de estado. Quem carrega a verdade é este bloco,
> o `ESTADO-ATUAL.md`, o código e o git. O veredito acima foi dado por **existência de
> arquivo na árvore**, nunca por contagem de caixa.


**O que é.** O plano de execução do spec
`docs/superpowers/specs/2026-08-17-nota-e-liberacao-design.md`. As decisões e o diagnóstico
vivem lá e não são repetidos aqui; **quando divergirem, o spec vence**.

**Contexto.** Não é fase nova do ciclo de compras: é o **fecho da Fase 2**, que entregou
`lancar_nota()` e `liberar()` sem rota, sem template e sem botão. Fura a fila da Fase 4
(régua de 9 etapas) de propósito — a régua teria de representar dois passos que hoje não
existem em tela nenhuma.

Pré-requisito **de símbolo**: este plano lê `pedido_compra.fluxo_pagamento` e
`nota_fiscal_pedido` (Fase 2, migration 287) e `valor_atestado()` (Fase 1). Se algum não
existir, **pare — a fase anterior não está mesclada.**

**As fronteiras:**

1. **`main` não anda.** Tudo em `feat/nota-e-liberacao`; merge e push esperam o Cássio.
   📖 `main` está 53 commits à frente de `origin/main` e o push para o GitHub segue
   quebrado (item humano nº 2) — o backup `gitsafe-backup` é o único lugar fora desta
   máquina.
2. **Âncoras por símbolo + literal**, nunca por número de linha.
3. **Red-first**: nenhum passo de implementação sem ver o teste vermelho antes.
4. **Esta fase NÃO tem flag própria** — e é a fronteira mais fácil de errar. Ela completa o
   caminho da `financeiro_dois_fluxos_ativo`, que já existe. A paridade a provar é: **com a
   flag da Fase 2 desligada, nada muda** — a rota da nota recusa, o painel não aparece, o
   botão não aparece, e emitir → pagar produz os mesmos registros de antes.
5. **Não afrouxar a Fase 2.** A ressalva do D3 é exceção auditável, não porta larga. O teste
   que segura isso é o de que `liberar()` **sem** `justificativa` continua byte-idêntico ao
   de hoje. Se ele precisar ser reescrito para passar, algo saiu do lugar.
6. **As cinco decisões estão fechadas** — 🔬 17/08, todas na recomendação (spec, seção
   "Decisões"). Nenhuma task espera resposta. Divergência que aparecer ao executar volta
   para o spec como 📌, não vira ajuste silencioso no código.

**Onde ficam os testes.** `tests/test_nota_e_liberacao.py`, no molde de
`tests/test_financeiro_dois_fluxos.py`: fixtures locais, `pytestmark =
pytest.mark.integration`, tenant por `uuid4()`, sem depender de seed. As fixtures ligam
`recebimento_atesto_ativo` **e** `financeiro_dois_fluxos_ativo` — sem as duas a conta nasce
`liberada`, `pernas_faltantes` volta vazia e não há tríade para testar.

---

## Ordem e independência

```
N1 (coluna liberacao_justificativa + migration 308)
 └─> N2 (serviço: a ressalva, e `usuario` deixa de ser opcional)
      ├─> N3 (tela da nota: lançar, listar, excluir)
      └─> N4 (painel da tríade + botão liberar)
           └─> N5 (sensor, teste-guarda e as duas correções de runbook)
```

N1→N2 é caminho crítico e serial. **N3 e N4 são irmãs** — tocam arquivos diferentes e
nenhuma depende da outra —, mas **nenhuma das duas merge sozinha**: o gate de merge é o
teste que faz o ciclo fechar pela tela (emitir → atestar → lançar nota → liberar → pagar), e
ele precisa das duas. Quem estiver sozinho faz N3 primeiro, que é a maior.

N5 pode entrar depois do merge, **com uma exceção que não é negociável**: o passo do sensor
(N5 Step 2) tem de sair **junto** com N2. Ver o risco no fim deste plano — a ressalva, se
entrar sem tocar o sensor, faz o achado 1 da Fase 2 gritar em toda conta liberada por
exceção, e sensor que grita pelo esperado deixa de ser lido.

---

## N1 — A coluna e a migration 308

- [x] **Step 0:** conferir `migration_history` no dev **antes** de fixar o número. O spec diz
  308 e o repositório termina em 299 — mas essa conferência já falhou duas vezes (B6.1 e
  R1). Se o dev estiver à frente, renumerar aqui **e no spec**, e não seguir com dois
  documentos discordando. ⚠️ 300-307 é faixa reservada da Fase 9 e 290-295 da Fase 8:
  **nenhuma das duas é vão livre**, é reserva não aplicada. Numerar dentro delas arma a
  colisão que a renumeração 270→277 existiu para evitar.
- [x] **Step 1 (red):** teste do esqueleto — `ContaPagar.liberacao_justificativa` nasce
  `None` em conta nova, e a conta histórica (criada antes da migration) também. Rodar e
  **ver vermelho**.
- [x] **Step 2:** a coluna em `models.py`, junto de `liberada_por_id`/`liberada_em`, que são
  as irmãs dela. Docstring no padrão da casa: **por que uma coluna e não duas** (o booleano
  seria derivável do texto e os dois poderiam divergir) e **por que não `observacoes`**
  (📖 `liberar()` já escreve `[liberação]` e `[divergência]` lá como texto livre, e um
  relatório de exceções que faça `LIKE` numa coluna de 2000 caracteres é a definição de
  sensor em que ninguém confia).
- [x] **Step 3:** `_migration_308_liberacao_justificativa` — uma coluna, `TEXT NULL`, **sem
  backfill**: conta antiga não tem exceção a declarar. Registrar na lista de tuplas com a
  descrição explicando o salto de 299 para 308 e por que as duas faixas do meio seguem
  reservadas.
- [x] **Step 4 (green):** rodar. Verde.
- [x] **Step 5:** commit — `feat(financeiro): coluna da liberacao excepcional e migration 308`

## N2 — O serviço: a ressalva, e `usuario` deixa de ser opcional

> Esta task fecha o **D6 da Fase 2**, decidido em 14/08 e nunca construído: 📖 `liberar()`
> levanta `TriadeIncompleta` sem exceção possível, e a porta de escape não existe na
> assinatura.

- [x] **Step 1 (red):** os testes que definem a ressalva, um por regra do spec:
  - `liberar()` com `justificativa` e uma perna aberta **libera**, grava o texto em
    `liberacao_justificativa` e mantém `liberada_por_id`/`liberada_em`;
  - `liberar()` com `justificativa` de menos de **15 caracteres** recusa com
    `RessalvaInvalida` — campo vazio e `"ok"` são a mesma coisa para quem for auditar;
  - `liberar()` com `justificativa` **recusa** quando a perna aberta é a emergência 48h não
    ratificada, e a mensagem **nomeia a emergência**;
  - `liberar()` com a tríade **fechada** e `justificativa` passada mesmo assim: libera e
    **não grava** a justificativa — não houve exceção, e gravar sugeriria uma;
  - **sem** `justificativa`, o comportamento de hoje é byte-idêntico (fronteira nº 5);
  - `lancar_nota` **sem** `usuario` recusa com erro de domínio, e não com `IntegrityError`.
- [x] **Step 2:** `liberar(pedido, *, usuario=None, justificativa=None)`. A recusa da
  emergência **não casa por string** na lista de `pernas_faltantes`: chama
  `_emergencia_nao_ratificada(pedido)`, que já existe e já é a fonte daquela frase. Casar
  por texto quebraria no dia em que alguém melhorar a mensagem — e a mensagem é feita para
  ser melhorada.
- [x] **Step 3:** `RessalvaInvalida(ErroFinanceiroCompra)`, ao lado de `TriadeIncompleta`.
  Exceção própria e não reuso: a rota precisa distinguir "faltou perna" (que oferece o
  campo de justificativa) de "a justificativa não serve" (que devolve o campo preenchido
  com o que a pessoa escreveu).
- [x] **Step 4:** `lancar_nota` passa a exigir `usuario` — **keyword obrigatório**, sem
  default. 🔴 Hoje o default é `None` e `lancada_por_id` é NOT NULL (`models.py:6015` +
  migration 287): chamar sem usuário estoura `IntegrityError` e **aborta a transação
  inteira**, que é exatamente o que o comentário de `:173-177` existe para evitar.
  📖 Conferido: os **6** chamadores em `tests/` já passam `usuario=`, então a mudança não
  quebra ninguém — é o contrato que passa a dizer a verdade.
- [x] **Step 5 (green + mutação):** verdes. Mutação de sanidade: fazer a ressalva aceitar
  justificativa vazia e confirmar que o teste dos 15 caracteres **mata** a mutação.
- [x] **Step 6:** commit — `feat(financeiro): a liberacao ganha a ressalva do D6, e lancar_nota exige quem lancou`

## N3 — A tela da nota

- [x] **Step 1 (red):** os testes de rota:
  - `GET /compras/<id>/nota` de pedido de **outro tenant** → **404**. Por filtro
    `filter_by(id=…, admin_id=…).first_or_404()`, nunca `get()` seguido de comparação —
    📖 é o padrão de `recebimento` e é o que o achado nº 2 de 03/08 (`detalhes_obra`)
    tornou obrigatório;
  - `POST` de quem não é ADMIN do tenant → **403** (D1);
  - pedido **fora do Fluxo A do regime novo** → redirect com a razão dita, e **nenhuma**
    `NotaFiscalPedido` criada;
  - nota duplicada → flash `warning` e **200**, não 500;
  - excluir nota com a conta ainda `bloqueada` → some, e o número volta a ser aceito;
  - excluir nota com a conta já `liberada` → recusa com a razão.
- [x] **Step 2:** a rota `nota(pedido_id)` em `compras_views.py`, GET+POST na mesma view,
  no molde de `recebimento` (`compras_views.py:1181`) — inclusive na ordem das guardas:
  `_check_v2()` → tenant por filtro → permissão → recusa explicada do regime. A recusa do
  regime segue o argumento do `if not pedido.exige_atesto` de `:1214`: **um no-op silencioso
  é pior que uma recusa**, e nota lançada em pedido sem tríade é linha órfã que não bloqueia
  nem libera nada.
- [x] **Step 3:** `templates/compras/nota.html` — as notas já lançadas (número/série, valor,
  emissão, quem lançou, quando), a soma delas contra `valor_atestado(pedido)` e contra o
  valor do pedido, e o formulário. `chave_acesso` é campo **opcional, sem validação de
  dígito**: 📖 o docstring de `NotaFiscalPedido` (`models.py:5963`) já decidiu isso —
  *"metade das compras de obra chega com recibo, nota de serviço ou nota sem XML"*.
  ⚠️ **Sem input de arquivo** (D4): `arquivo_path` continua nulo até o volume persistente
  existir. Anexo gravado em `static/uploads/` some no primeiro redeploy, e nota fiscal que
  some é pior que nota fiscal que nunca foi anexada.
- [x] **Step 4:** a rota de exclusão, `POST /compras/<pedido_id>/nota/<nota_id>/excluir`,
  com a guarda da conta `bloqueada` (D5).
- [x] **Step 5 (green):** rodar. Verdes.
- [x] **Step 6:** commit — `feat(compras): a nota fiscal do pedido ganha tela`

## N4 — O painel da tríade e o botão de liberar

- [x] **Step 1 (red):**
  - `POST /compras/<id>/liberar` com a tríade fechada → conta vira `liberada` **e a baixa
    passa na mesma suíte**. Este é o teste que prova que o ciclo fecha ponta a ponta pela
    tela, e é exatamente o que faltou na Fase 2 — se só um teste desta fase sobreviver, é
    ele;
  - `POST /liberar` com perna aberta e sem justificativa → recusa nomeando a perna;
  - `POST /liberar` com perna aberta e justificativa válida → libera e grava a ressalva;
  - quem não é ADMIN → **403**;
  - **paridade**: no tenant com `financeiro_dois_fluxos_ativo` **desligada**, a tela do
    pedido não mostra painel nem botão, e emitir → pagar produz exatamente os mesmos
    registros de antes — conferido por `SELECT`, não pela ORM.
- [x] **Step 2:** a rota `liberar_pedido(pedido_id)`. `TriadeIncompleta` e `RessalvaInvalida`
  viram flash `warning` com a mensagem do serviço, que já é escrita para o operador.
- [x] **Step 3:** o painel em `templates/compras/detalhe.html`, ao lado do bloco de
  recebimento que já existe (`:26-50`) e com a mesma forma: badge + ação. Três linhas —
  pedido, nota, atesto —, cada uma verde ou com a frase que `pernas_faltantes` já devolve.
  **A tela não reimplementa a regra**: 📖 `pernas_faltantes` é função pura e a docstring
  dela diz que dá para chamar de dentro do template sem medo.
- [x] **Step 4:** o botão. Some para quem não pode liberar; com a tríade fechada é POST
  direto; com perna aberta abre o campo de justificativa e vira **"Liberar com ressalva"**.
  **Nunca some por estar bloqueado** — sumir é o que empurra o operador para o caminho de
  fora do sistema, que é a frase que a Fase 2 repete em três lugares.
- [x] **Step 5 (green + mutação):** verdes. Mutação: fazer a rota ignorar
  `pernas_faltantes` e confirmar que o teste da tríade incompleta morre.
- [x] **Step 6:** commit — `feat(compras): a triade aparece na tela do pedido e a conta ganha botao de liberar`

## N5 — Sensor, teste-guarda e os dois runbooks

- [x] **Step 1 (red):** o **teste-guarda que teria pego este buraco em 14/08**: varre as
  rotas registradas no app e falha se `lancar_nota` ou `liberar` voltarem a não ter chamador
  fora de `tests/`. Mesma ideia do guarda da C9 da Fase 2, que varre `.py` atrás de
  `ContaPagar(` criado fora do serviço. A mensagem de falha tem de ser legível para quem
  nunca leu este plano.
- [x] **Step 2:** ⚠️ **`scripts/verificar_consistencia_financeiro.py` — sai junto com N2, não
  depois.** 📖 O achado 1 (`conta_liberada_sem_triade`, `:55`) marca toda conta `liberada`
  cujo `pernas_faltantes` não está vazio. **Conta liberada por ressalva é exatamente isso** —
  sem tocar o sensor, toda exceção legítima vira inconsistência e o sensor passa a gritar
  pelo esperado. Duas mudanças: o achado 1 **pula** conta com `liberacao_justificativa`
  preenchida, e nasce o achado `liberada_com_ressalva`, que **não é defeito** — lista as
  exceções para que alguém as leia uma vez por mês. Sensor que só grita erro nunca mostra o
  que foi decidido por fora da regra.
- [x] **Step 3 (green):** verdes. Rodar o sensor no tenant de dev: exit 0 antes da ressalva,
  e depois de uma liberação excepcional ele lista **uma** linha, sem virar exit 1 por causa
  dela.
- [x] **Step 4:** as **duas correções de runbook**. Nenhuma é cosmética: as duas descrevem
  hoje um contorno que deixa de existir.
  - 📖 `2026-08-14-financeiro-dois-fluxos-design.md`, passo **2d** (*"lançar nota"*) —
    ganha o endereço da tela;
  - 📖 `2026-08-15-alcadas-design.md`, passo **3e(ii)** — a frase *"a nota ainda não tem
    tela própria"* fica **falsa**. Trocar pela tela, marcando a linha como as outras
    correções de execução daquele runbook.
- [x] **Step 5:** commit — `feat(financeiro): sensor enxerga a liberacao excepcional, e o guarda das duas rotas`

---

## Desvios da execução — 17/08

Três, e nenhum silencioso. Ficam aqui porque o plano é o documento contra o qual a
próxima rodada vai se comparar.

1. 🔴 **O red-first do N3 foi furado.** Os testes de rota da tela da nota foram escritos
   **depois** da rota, não antes: a regressão dirigida do N2 ocupava o banco por 5 minutos
   e eu segui codando em vez de esperar. Eles nasceram **verdes**, que é exatamente o
   sintoma contra o qual o red-first protege — teste que passa pelo motivo errado é a
   lição do D1 da Fase 0.6 e da Task 7 da Fase 1. Recuperação: provei por **mutação** que
   são load-bearing (removida a guarda de ADMIN morre o teste do 403; desligada a recusa
   do regime morre o teste do Fluxo A). **Mutação não substitui red-first** — ela prova
   que o teste vê o código, não que ele foi escrito antes dele.
2. **N2 e N3 saíram num commit só** (`0a343ed0`), não em dois como o plano previa. Sem
   consequência técnica; a mensagem cobre os dois.
3. **A ordem N3/N4 foi serial**, não paralela. O plano as chamava de irmãs e estava certo
   — nada nelas conflitou.

**O que a execução acrescentou ao desenho** (e está registrado no spec como 📌):
`_quantidade_do_form` em vez de `Decimal()` direto na tela da nota. É o parser que
**recusa** `"1.500"` em vez de chutar entre mil e quinhentos e um e meio — o achado nº 6
da revisão da Fase 3, que ficou aberto lá porque consertar num lugar só criaria
divergência. A tela é nova: nasce certa, e não herda a convenção defeituosa.

---

## Gate final — 🟡 executado em 17/08, com UM item não cumprido

- [x] Suíte da fase verde: **25 passed** (`tests/test_nota_e_liberacao.py`)
- [x] **Regressão dirigida** verde: **296 passed, exit 0** em 5min20s — a mudança de
  assinatura de `lancar_nota` não quebrou nenhum dos 6 chamadores, como a conferência
  prévia previa
- [x] Gate completo: **2425 passed, 2 failed, 6 skipped, 2 xfailed** em 32min58s. Log
  redirecionado para arquivo, não pipado — a lição de 16/08 foi seguida. **As duas falhas
  são as duas conhecidas e anteriores**, as mesmas que reproduzem em `main`:
  `test_excluir_obra::test_lista_cobre_toda_fk_no_action_para_obra` e
  `test_fase5_rdo_ciclo_vida::test_backfill_marcou_os_rdos_historicos_como_preenchido`.
  **Zero falhas novas.** A aritmética fecha: 2400 (baseline de 16/08) + 25 desta fase = 2425
- [x] Ciclo com a flag **desligada**: paridade conferida por `SELECT` — conta nasce
  `liberada`, `liberacao_justificativa` NULL, e o botão não aparece na tela do pedido
- [x] Ciclo com a flag **ligada**, por rota, do começo ao fim: emitir → atestar → lançar
  nota → liberar → **pagar**, com a baixa gravada. É o teste que dá nome ao gate de merge
- [x] **A ressalva, pela rota:** pedido com atesto e sem nota → liberação com
  justificativa → `liberacao_justificativa` gravada → a conta paga
- [x] **A recusa da ressalva:** emergência 48h não ratificada não é destravada por
  justificativa nenhuma, e a recusa nomeia a ratificação
- [x] Sensor rodado pela **CLI** num tenant de dev com ressalva: lista a exceção com o
  motivo, imprime "sem drift" e sai **exit 0** — a exceção não é contada como defeito
- [x] As divergências entre spec e código registradas no próprio spec como 📌
  (`_quantidade_do_form`) e os desvios de execução registrados acima
- [ ] 🔴 **O runbook da Fase 2 rodado de ponta a ponta num tenant de dev, PELA TELA, por
  um humano.** **NÃO foi feito.** Todo o ciclo acima foi exercitado pelo `test_client`,
  que percorre as rotas e renderiza os templates de verdade — mas ninguém abriu o
  navegador, clicou no botão e leu a tela.

  Este item não é formalidade, e a própria história deste repositório é a prova: 🔬 em
  15/08 foi exatamente ele que achou o 🔴 que a suíte inteira não pegava (`pode_ratificar`
  recusando a requisição já convertida). Os testes da A6 não viam porque criavam o
  `PedidoCompra` direto no banco; aqui os meus não veem o que quer que só apareça com um
  humano na frente da tela.

  **Fica em aberto e é o primeiro item de quem retomar.** O que reduz o risco — e não o
  elimina — são os dois testes de render acrescentados no fim da execução, que provam que
  as duas telas devolvem 200 nos três estados do painel (bloqueada, pronta, liberada com
  ressalva) e que o texto da exceção aparece para quem lê.

---

## Riscos

| Risco | Mitigação |
|---|---|
| 🔴 **A ressalva quebra o sensor da Fase 2** — conta liberada por exceção é literalmente o que o achado 1 procura, e ele passaria a gritar pelo esperado | N5 Step 2 sai **junto com N2**, não depois. É a única dependência fora de ordem deste plano, e está marcada como tal na seção "Ordem" |
| **A ressalva vira a porta larga** — o operador descobre que "Liberar com ressalva" é mais rápido que cobrar a nota do fornecedor | Justificativa escrita de 15+ caracteres, autoria gravada, e o sensor listando as exceções para leitura mensal. ⚠️ **Se depois da primeira volta a ressalva for a maioria das liberações, o defeito não é o campo — é o processo**, e aí a decisão volta ao Cássio |
| **Mudar a assinatura de `lancar_nota` e `liberar` quebra as três fases que já as chamam** | 📖 Conferido antes de escrever este plano: os 6 chamadores de `lancar_nota` estão todos em `tests/` e todos já passam `usuario=`; `liberar` ganha parâmetro **opcional**, então nenhum chamador muda. Regressão dirigida no gate, antes do gate completo |
| **A tela da nota vira cadastro de NF-e** — validação de chave, XML, importação | O spec fecha isso em duas linhas e o D4 tira o upload da rodada. Se aparecer pedido de XML durante a execução, é fase nova com spec próprio: 📖 a `NotaFiscal` legada já existe para isso e **convergir as duas é dívida registrada** |
| **Painel na tela do pedido consultando o serviço a cada render** — `pernas_faltantes` faz duas queries por pedido | Só renderiza no Fluxo A do regime novo, que hoje é **zero** tenant; e a tela é de um pedido, não de lista. Se um dia entrar numa listagem, aí é que precisa de cuidado — anotar no template, não otimizar agora |
| **Pedido sem obra** (material de escritório) | 📖 Já resolvido: D3 da Fase 2 decidiu que entra na tríade, e o atesto da Fase 1 já trata pedido sem obra (correção C5). O teste da fase inclui um |
