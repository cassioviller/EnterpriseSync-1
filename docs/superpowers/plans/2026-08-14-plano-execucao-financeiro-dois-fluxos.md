# Plano de execução — Financeiro em dois fluxos — 2026-08-14

**O que é.** O plano de execução do spec
`docs/superpowers/specs/2026-08-14-financeiro-dois-fluxos-design.md`. As decisões e o
diagnóstico vivem lá e não são repetidos aqui; **quando divergirem, o spec vence**.

**Contexto.** Fase 2 de 5 do ciclo de compras. A Fase 1 (recebimento e atesto) é
pré-requisito **de símbolo**, não só de padrão: este plano importa `valor_atestado` e
`regime_do_tenant` de `services/recebimento_pedido.py` e lê
`pedido_compra.situacao_recebimento`. Se algum não existir, **pare — a Fase 1 não está
mesclada.**

**As fronteiras:**
1. **`main` não anda.** Tudo em `feat/financeiro-dois-fluxos`; merge e push esperam o Cássio.
2. **Âncoras por símbolo + literal**, nunca por número de linha.
3. **Red-first**: nenhum passo de implementação sem ver o teste vermelho antes.
4. **Nada de comportamento novo sem a flag.** Com `financeiro_dois_fluxos_ativo` desligada,
   o sistema tem que se comportar exatamente como hoje, movimento a movimento — e o teste
   de paridade é quem prova isso, não a leitura do diff.
5. **Dinheiro não se estorna por acidente.** Todo passo que muda `ContaPagar` existente
   começa perguntando o que acontece com a que já foi paga.

**Onde ficam os testes.** `tests/test_financeiro_dois_fluxos.py`, no molde de
`tests/test_recebimento_atesto.py`: fixtures locais, `pytestmark =
pytest.mark.integration`, tenant por `uuid4()`, sem depender de seed.

---

## Ordem e independência

```
F1 (modelos + migrations)
 └─> F2 (flag + carimbo do fluxo)
      └─> F3 (serviço: conta bloqueada, nota, liberação)
           ├─> F4 (a tríade barra o pagamento)     ← o conserto que dá nome à fase
           │    └─> F5 (o fechamento ganha efeito e segregação)
           └─> F6 (Fluxo B: adiantamento e a lista de espera)
                └─> F7 (consistência, teste-guarda e runbook)
```

F1→F4 é caminho crítico e serial. F6 só depende de F3 — pode ser feito enquanto F4/F5
andam, e é o único ramo que não mexe em `pagar_conta`. F7 fecha.

**F4 é o gate de merge.** F5 a F7 podem entrar depois, mas **não** antes de a flag ser
ligada em tenant real: F5 e F6 são becos sem saída para o usuário (conta liberada que
ninguém consegue pagar, adiantamento que não some da lista).

---

## F1 — Modelos e migrations 287/288/289

- [x] **Step 0:** conferir `migration_history` no dev **antes** de fixar número. O spec diz
  287-289 e o repositório termina em 286 — mas essa conferência já falhou duas vezes
  (B6.1 e R1), e o merge de 14/08 mostrou por quê. Se o dev estiver à frente, renumerar
  aqui e **no spec**, e não seguir com dois documentos discordando.
- [x] **Step 1 (red):** testes que provam o esqueleto:
  - `NotaFiscalPedido` e `AdiantamentoFornecedor` importáveis de `models`;
  - UNIQUE `(admin_id, fornecedor_id, numero, serie)` recusa a mesma nota duas vezes;
  - `NotaFiscalPedido.chave_acesso` **aceita NULL** — é a diferença deliberada em relação
    à `NotaFiscal` legada, e um teste que a nomeia impede que alguém "conserte" para NOT NULL;
  - `pedido_compra.fluxo_pagamento` default `'faturado'` e `conta_pagar.situacao_liberacao`
    default `'liberada'` num registro recém-criado.

  Rodar e **ver os quatro vermelhos**.
- [x] **Step 2:** os dois modelos em `models.py`, junto de `PedidoCompra` e `ContaPagar`
  respectivamente — vizinhança importa para quem lê. Docstring no padrão da casa: o que é,
  por que existe, e **por que não reusa `NotaFiscal`** (o UNIQUE global de `chave_acesso` e
  o vínculo com `MovimentacaoEstoque`), com ponteiro para o parágrafo do spec.
- [x] **Step 3:** as colunas: `fluxo_pagamento` em `PedidoCompra`; `situacao_liberacao`,
  `liberada_por_id`, `liberada_em` em `ContaPagar`; `fechado_por_id`, `fechado_em`,
  `reaberto_por_id` em `FechamentoPagamento`.
- [x] **Step 4:** `migration_287_nota_e_adiantamento` — as duas tabelas, com as constraints
  e os índices do spec. Sem backfill.
- [x] **Step 5:** `migration_288_regime_e_liberacao` — as sete colunas do Step 3. **Todos os
  defaults descrevem o registro histórico**: pedido antigo é `faturado`, conta antiga é
  `liberada`. Um default diferente disso trancaria o parque no dia do deploy.
- [x] **Step 6:** `migration_289_flag_e_tolerancia` — `financeiro_dois_fluxos_ativo`
  (bool, NOT NULL, default FALSE) e `tolerancia_divergencia_nf_pct` (numeric, default 2.00)
  em `configuracao_empresa`.
- [x] **Step 7 (green):** os quatro verdes. Aplicar as três migrations no dev e conferir por
  `psql`: tabelas, constraints, índices e defaults.
- [x] **Step 8:** commit — `feat(financeiro): tabelas de nota e adiantamento, regime e liberacao (migrations 287-289)`

## F2 — Flag por tenant e o carimbo do fluxo

- [x] **Step 1 (red):** testes:
  - `scripts/flag_financeiro_dois_fluxos.py --ligar` **recusa** tenant sem
    `recebimento_atesto_ativo` — é a dependência dura do spec, e a guarda mora no script
    porque quem mexe por SQL direto não tem nenhuma;
  - com a flag ligada, pedido emitido como adiantamento nasce `fluxo_pagamento='adiantamento'`;
  - com a flag **desligada**, o mesmo POST nasce `'faturado'` e a tela não oferece a escolha;
  - ligar e desligar a flag **não mexe** no regime de pedido já emitido.
- [x] **Step 2:** `scripts/flag_financeiro_dois_fluxos.py`, no formato de
  `scripts/flag_recebimento_atesto.py` — `--ligar`, `--desligar`, `--forcar`, e a listagem
  do estado atual quando chamado sem ação.
- [x] **Step 3:** `fluxo_do_tenant(admin_id)` em `services/financeiro_compra.py`, espelhando
  `regime_do_tenant`. Carimbar na criação do pedido nos **mesmos dois pontos** que a Fase 1
  carimbou `exige_atesto` — e se aparecer um terceiro, é achado, não detalhe: pare e
  registre antes de seguir.
- [x] **Step 4 (green):** os quatro verdes.
- [x] **Step 5:** commit — `feat(financeiro): flag dois-fluxos por tenant e o carimbo do fluxo no pedido`

## F3 — O serviço: conta bloqueada, nota, liberação

- [x] **Step 1 (red):** testes do serviço, um por regra do spec:
  - no regime novo + Fluxo A, a emissão cria `ContaPagar` **`bloqueada`**, com o valor do
    pedido (não zero — a projeção de caixa depende disso);
  - `lancar_nota()` recusa nota duplicada, aceita sem `chave_acesso`, e grava `lancada_por_id`;
  - `liberar()` recusa enquanto faltar qualquer perna da tríade, e a exceção **nomeia a
    perna que falta** — mensagem em português, com os dois valores quando for divergência;
  - `liberar()` **reajusta** `valor_original`/`saldo` para `valor_atestado` e registra a
    diferença na observação;
  - divergência nota × atestado **dentro** da tolerância libera; **fora** dela avisa e
    libera assim mesmo (D1), com o aviso persistido.
- [x] **Step 2:** `services/financeiro_compra.py` — chokepoint único, no molde de
  `services/recebimento_pedido.py`. `criar_obrigacao()`, `lancar_nota()`, `liberar()`,
  `pernas_faltantes(pedido)` como função **pura** (é ela que a tela e a mensagem de erro
  consomem, e função pura é a que dá para testar sem montar meio banco).
- [x] **Step 3:** mover a criação de `compras_views.py:305` para o serviço, com o caminho
  antigo preservado sob a flag desligada. **Não** apagar o código antigo: mesma decisão da
  R4, pelo mesmo motivo — o regime velho continua sendo o de quase todo tenant.
- [x] **Step 4 (green + mutação):** todos verdes. Mutação de sanidade: fazer
  `pernas_faltantes` devolver lista vazia sempre e confirmar que o teste da tríade
  incompleta **mata** a mutação.
- [x] **Step 5:** commit — `feat(financeiro): servico da obrigacao de compra — conta bloqueada, nota e liberacao`

## F4 — A tríade barra o pagamento

- [x] **Step 1 (red):** os testes que definem a virada:
  - `POST /financeiro/pagar/<id>` de conta `bloqueada` **recusa**, e o corpo da resposta
    nomeia a perna que falta;
  - conta `liberada` paga igual a hoje — o caminho feliz não pode regredir;
  - **paridade**: no tenant com a flag desligada, emitir → pagar produz exatamente os
    mesmos registros de antes (conferido por `SELECT`, não pela ORM);
  - a guarda fica **antes** do `if POST` e **fora** do try, pela mesma razão que a B5.1
    documenta em `financeiro_views.py:445` — `abort()` dentro daquele try vira 200.
- [x] **Step 2:** a guarda em `financeiro.pagar_conta`, consultando `pernas_faltantes`.
- [x] **Step 3:** varrer atrás de outro caminho de baixa **antes de assumir que só há um**.
  Hoje há um: `FinanceiroService.baixar_pagamento` tem uma única chamada de produção
  (`financeiro_views.py:518`, dentro do próprio `pagar_conta`). Se a varredura achar um
  segundo, ele é achado — pare e decida o regime dele na mesma rodada, em vez de guardar
  só o caminho conhecido. A C9 da Fase 1 é a prova de que a varredura acha o que a leitura
  não acha.
- [x] **Step 4 (green + mutação):** verdes. Mutação: remover a guarda e confirmar que o
  teste da conta bloqueada morre.
- [x] **Step 5:** commit — `fix(financeiro): conta sem a triade nao aceita baixa, e diz o que falta`

## F5 — O fechamento ganha efeito e segregação

- [x] **Step 1 (red):**
  - no regime novo, `pagar_conta` exige conta em fechamento `FECHADO`;
  - quem **montou** o lote não consegue **fechá-lo** — invariante, não configuração,
    espelhando `solicitante_id != aprovador_id` da Fase 3;
  - `reabrir` recusa lote que já tenha conta paga;
  - `fechado_por_id`/`fechado_em` gravados; `reaberto_por_id` idem;
  - no regime **antigo**, nada disso vale — o lote continua decorativo, como sempre foi.
- [x] **Step 2:** as guardas em `financeiro_views.fechamento_pagamentos`, chamando o serviço.
  A trilha é gravada no serviço, não na rota.
- [x] **Step 3:** a tela passa a mostrar quem fechou e quando, e a esconder `reabrir` quando
  a regra o recusaria — botão que existe e sempre falha é pior que botão ausente (lição da
  C5 da Fase 1).
- [x] **Step 4 (green):** verdes.
- [x] **Step 5:** commit — `feat(financeiro): o fechamento passa a liberar de verdade, com trilha e segregacao`

## F6 — Fluxo B: adiantamento e a lista de espera

- [x] **Step 1 (red):**
  - pedido `adiantamento` nasce com `ContaPagar` **`liberada`** (não há o que atestar ainda)
    + linha em `adiantamento_fornecedor` com `baixado_em` NULL;
  - adiantamento **parcial** (D4): duas linhas no mesmo pedido, duas contas;
  - o atesto da Fase 1 baixa **todas** as pendentes daquele pedido, e só o atesto baixa;
  - pedido cancelado com adiantamento pago **não** some da lista: vira pendência de
    devolução, com o valor à vista;
  - a lista "pago, aguardando entrega" não vaza entre tenants.
- [x] **Step 2:** `registrar_adiantamento()` e `baixar_adiantamentos(pedido)` no serviço.
- [x] **Step 3:** o gancho no `registrar_recebimento` da Fase 1 — chamada ao serviço daqui,
  **não** lógica de adiantamento dentro do serviço de recebimento. Uma dependência, num
  sentido só.
- [x] **Step 4:** a tela da lista, na obra e no financeiro.
- [x] **Step 5 (green + mutação):** verdes. Mutação: baixar o adiantamento na emissão em vez
  do atesto e confirmar que o teste da lista **mata** a mutação.
- [x] **Step 6:** commit — `feat(financeiro): adiantamento a fornecedor e a lista de pago aguardando entrega`

## F7 — Consistência, teste-guarda e runbook

- [ ] **Step 1 (red):** o teste-guarda da C9: varre **todo** `.py` do repositório atrás de
  `ContaPagar(` e falha em criação nova fora do serviço, carregando por escrito a lista dos
  cinco pontos legítimos que o spec tabela. A mensagem de falha tem de ser legível o
  bastante para quem nunca leu este plano.
- [ ] **Step 2:** `scripts/verificar_consistencia_financeiro.py`, no formato de
  `scripts/verificar_consistencia_recebimento.py`: acha conta `liberada` sem as três pernas,
  adiantamento baixado sem atesto, e lote `FECHADO` sem `fechado_por_id`. `--json`, exit
  0/1/2. **Varre só o regime novo** — sensor que grita sempre não é lido nunca.
- [ ] **Step 3 (green):** verdes.
- [ ] **Step 4:** runbook no fim do spec: como ligar a flag num tenant, o que conferir antes,
  e o rollback.
- [ ] **Step 5:** commit — `feat(financeiro): sensor de consistencia e o guarda da criacao de conta`

---

## Gate final

- [ ] `tests/test_financeiro_dois_fluxos.py` inteiro verde.
- [ ] Suítes vizinhas sem regressão: `-k "financeiro or compra or conta or fechamento or almoxarifado"`.
- [ ] Gate completo (`pytest tests/ -m "not browser"`) no mesmo estado em que estava antes
      da branch — **igual, não "verde"**: comparar contra a linha de base medida no dia,
      porque herdar falha alheia como se fosse sua atrasa o merge por engano.
- [ ] Num tenant de dev com a flag **desligada**: emitir pedido, conferir por SQL que a
      `ContaPagar` nasce idêntica à de antes e que a baixa funciona igual.
- [ ] No mesmo tenant com a flag **ligada**: emitir (conta bloqueada) → tentar pagar
      (recusa nomeando as pernas) → atestar → lançar nota → montar lote → fechar com outra
      pessoa → pagar. E o valor da conta reajustado para o atestado.
- [ ] Fluxo B ponta a ponta: emitir com adiantamento → pagar → conferir a lista → atestar →
      conferir que sumiu.
- [ ] Ligar e **desligar** a flag de volta não mexeu no fluxo de nenhum pedido já emitido.
- [ ] `scripts/verificar_consistencia_financeiro.py` sem drift nas obras de dev.

---

## Riscos

| Risco | Mitigação |
|---|---|
| A guarda de `pagar_conta` travar tenant que ninguém avisou | Toda ela dentro de `financeiro_dois_fluxos_ativo`, e o teste de paridade é o que prova o tenant sem flag — mais forte que ler o diff |
| Conta bloqueada sem caminho para liberar | É o que a dependência dura de `recebimento_atesto_ativo` existe para impedir. A guarda mora no `--ligar`, e o F2 Step 1 a testa |
| Reajuste do valor na liberação mexer em conta já paga | F3 Step 1: o reajuste só acontece na transição para `liberada`, e conta paga não transiciona. Teste dedicado |
| Um segundo caminho de baixa escapar da guarda | F4 Step 3 varre em vez de assumir. Foi assim que a C9 achou o quarto ponto de carimbo |
| Número da migration colidir | F1 Step 0, antes de qualquer código. Terceira vez que este risco entra num plano desta casa, e a terceira é por já ter mordido duas |
| A lista de adiantamento virar tela órfã que ninguém abre | Ela nasce **na obra**, não só no financeiro — quem cobra a entrega é o campo |
| Ligar a flag no mesmo dia do merge | Não fazer. O gate pede o ciclo completo em dev primeiro, e o runbook é o caminho de ligar em tenant real |
