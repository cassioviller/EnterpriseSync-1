# Plano de execução — Recebimento e atesto — 2026-08-11

**O que é.** O plano de execução do spec
`docs/superpowers/specs/2026-08-11-recebimento-atesto-design.md`. As decisões e o
diagnóstico vivem lá e não são repetidos aqui; **quando divergirem, o spec vence**.

**Contexto.** Fase 1 de 5 do ciclo de compras. As outras quatro (financeiro em dois
fluxos, alçadas, status unificado, relatórios) têm spec próprio e não entram aqui.

**As fronteiras:**
1. **`main` não anda.** Tudo em `feat/recebimento-atesto`; merge e push esperam o Cássio.
2. **Âncoras por símbolo + literal**, nunca por número de linha.
3. **Red-first**: nenhum passo de implementação sem ver o teste vermelho antes.
4. **Nada de comportamento novo sem a flag.** Com `recebimento_atesto_ativo` desligada, o
   sistema tem que se comportar exatamente como hoje, movimento a movimento.

**Onde ficam os testes.** `tests/test_recebimento_atesto.py`, no molde de
`tests/test_fase3_portal_seguranca.py`: fixtures locais, `pytestmark =
pytest.mark.integration`, tenant por `uuid4()`, sem depender de seed.

---

## Ordem e independência

```
R1 (modelos + migrations)
 └─> R2 (flag + carimbo do regime)
      └─> R3 (serviço: documento, validações, situação)
           ├─> R4 (o estoque passa a nascer do atesto)   ← o conserto da dupla escrita
           │    └─> R5 (exclusão do último recebimento, com estorno)
           └─> R6 (tela + recusa explícita do pedido legado)
                └─> R7 (consistência + valor_atestado)
```

R1→R4 é caminho crítico e serial. R6 só depende de R3 para o caminho feliz, mas a recusa
do legado depende de R2. R7 fecha.

---

## R1 — Modelos e migrations 283/284

- [x] **Step 1 (red):** testes que provam o esqueleto:
  - `RecebimentoPedido` e `RecebimentoPedidoItem` importáveis de `models`;
  - `UNIQUE (pedido_id, sequencia)` recusa duas sequências iguais no mesmo pedido;
  - `UNIQUE (recebimento_id, pedido_item_id)` recusa o mesmo item duas vezes no mesmo
    recebimento;
  - `pedido_compra.exige_atesto` default `False` e `situacao_recebimento` default
    `nao_recebido` num pedido recém-criado.

  Rodar e **ver os quatro vermelhos**.
- [x] **Step 2:** os dois modelos em `models.py`, junto de `PedidoCompra` (não no fim do
  arquivo — vizinhança importa para quem lê). Docstring no padrão da casa: o que é, por
  que existe, e a decisão do número derivado (`PC-1234/2`) em vez de sequência global.
- [x] **Step 3:** colunas `exige_atesto` (bool, NOT NULL, default False) e
  `situacao_recebimento` (String(24), NOT NULL, default `'nao_recebido'`) em
  `PedidoCompra`.
- [x] **Step 4:** `migration_283_recebimento_atesto` em `migrations.py` — cria as duas
  tabelas com as constraints e os índices do spec, e as duas colunas em `pedido_compra`.
  Sem backfill: pedido histórico é legado por definição, e `exige_atesto=False` descreve
  exatamente o que aconteceu com ele. Registrar na lista em `migrations.py` com o número
  **283**. ⚠️ Conferir `migration_history` no dev **antes** de fixar o número — a última
  do repositório é a 282 (conferido no dev em 11/08 — o grep ingênuo por `def migration_` mostra 266 porque as recentes usam prefixo `_`).
- [x] **Step 5:** `migration_284_flag_recebimento_atesto` — coluna
  `configuracao_empresa.recebimento_atesto_ativo` (bool, NOT NULL, default False).
- [x] **Step 6 (green):** os quatro testes verdes. Aplicar as duas migrations no dev e
  conferir por `psql`: tabelas, constraints, índices e defaults das colunas novas.
- [x] **Step 7:** commit — `feat(compras): tabelas de recebimento e atesto (migrations 283/284)`

## R2 — Flag por tenant e o carimbo do regime

- [x] **Step 1 (red):** testes:
  - pedido criado com a flag **desligada** nasce `exige_atesto=False`;
  - pedido criado com a flag **ligada** nasce `exige_atesto=True`;
  - **desligar a flag depois não muda** o `exige_atesto` de pedido já criado — é o teste
    que trava a razão de carimbar na linha em vez de comparar datas;
  - `recebimento_atesto_ativo(admin_id)` devolve `False` em qualquer erro (falha
    fechada, igual a `governanca_ativa`).
- [x] **Step 2:** `scripts/flag_recebimento_atesto.py`, no formato de
  `scripts/flag_compras_governanca.py`: `recebimento_atesto_ativo(admin_id)`,
  `definir_flag`, e `main()` com consulta / `--ligar` / `--desligar` / `--forcar`.
- [x] **Step 3:** guard do `--ligar`: recusa tenant sem nenhum `AlmoxarifadoItem`
  cadastrado, com a mensagem dizendo o porquê (ligar ali cria pedido que ninguém
  consegue receber). Mesma forma dos dois guards que o `flag_compras_governanca` já tem.
- [x] **Step 4:** carimbar `exige_atesto` na criação do pedido, nos **dois** pontos que
  criam `PedidoCompra` em `compras_views.py` (o POST avulso e a emissão a partir de
  requisição). Uma função só lê a flag; os dois pontos chamam ela.
- [x] **Step 5 (green):** os quatro verdes.
- [x] **Step 6:** commit — `feat(compras): flag recebimento_atesto por tenant e carimbo do regime no pedido`

## R3 — O serviço: documento, validações e situação

- [x] **Step 1 (red):** testes do `registrar_recebimento`, um por regra do spec:
  - recebimento parcial → `situacao_recebimento == 'parcial'`;
  - segundo recebimento completando → `'recebido'`;
  - `encerra_saldo=True` faltando quantidade → `'encerrado_com_saldo'`;
  - `encerra_saldo=True` com tudo entregue → `'recebido'` (a ordem de avaliação importa);
  - quantidade `0` e negativa → recusa;
  - soma acima do pedido → recusa; com `permitir_sobre_entrega=True` → aceita;
  - `encerra_saldo` sem motivo → recusa;
  - recebimento depois de encerrado → recusa, dizendo quem encerrou e quando;
  - `sequencia` incrementa 1, 2, 3 por pedido;
  - `LEITOR` da obra → recusa; `GESTOR`/`APONTADOR`/`COMPRADOR`/`ALMOXARIFE` → aceita;
  - solicitante e emissor **podem** atestar (decisão explícita do spec — o teste existe
    para que ninguém "conserte" isso sem ler a decisão).
- [x] **Step 2:** `pode_receber_na_obra(obra_id)` em `utils/autorizacao.py`, ao lado de
  `pode_requisitar_na_obra` e `pode_apontar_na_obra`.
- [x] **Step 3:** `services/recebimento_pedido.py` com `registrar_recebimento(...)` — o
  **único** caminho de escrita, no molde do chokepoint de `services/requisicao_compra.py`.
  Nesta rodada ele ainda **não** toca estoque: cria o documento, valida e atualiza a
  situação. Uma transação; `SELECT … FOR UPDATE` no pedido antes de somar quantidades.
- [x] **Step 4:** `situacao_para(pedido)` como função pura, separada de quem grava — é o
  que o script de consistência da R7 vai reusar sem duplicar regra.
- [x] **Step 5 (green + mutação):** todos verdes. Mutação de sanidade: trocar `>=` por
  `>` na derivação de `'recebido'` e confirmar que o teste do segundo recebimento
  **mata** a mutação.
- [x] **Step 6:** commit — `feat(compras): servico de recebimento — documento, validacoes e situacao derivada`

## R4 — O estoque passa a nascer do atesto

O conserto da dupla escrita. É o passo de maior risco do plano: mexe em almoxarifado.

- [x] **Step 1 (red):** os testes que definem a virada:
  - pedido com `exige_atesto=True` → a **emissão não cria nenhum**
    `AlmoxarifadoMovimento` (hoje cria: é a regressão que impede a dupla escrita de
    voltar);
  - atesto de 30 de 50 → um movimento `ENTRADA` de **30**, com lote, e
    `almoxarifado_movimento_id` preenchido na linha do recebimento;
  - item de texto livre → tem linha de recebimento, **não** tem movimento, e o
    `almoxarifado_movimento_id` fica `NULL`;
  - pedido com `exige_atesto=False` → **tudo como hoje**, movimento a movimento, na
    emissão e na rota `/receber` antiga.
- [x] **Step 2:** em `_gerar_entrada_almoxarifado` (ou nos dois chamadores — decidir na
  hora, pelo que ficar mais legível), pular a geração quando `pedido.exige_atesto`.
  **Decidido: dentro de `_gerar_entrada_almoxarifado`** — é onde a escrita acontece, e
  um terceiro chamador nascer no futuro não reabre a dupla escrita por esquecimento.
- [x] **Step 3:** gerar movimento + lote FIFO dentro de `registrar_recebimento`, para
  cada linha com `almoxarifado_item_id`, com `pedido_compra_id` preenchido (a dedup do
  handler `material_entrada` do EventManager depende disso). Gravar o id do movimento de
  volta na linha do recebimento.
- [x] **Step 4 (green):** os quatro verdes, com atenção especial ao quarto — ele é o que
  garante que nenhum tenant sem a flag foi afetado. **Um quinto teste entrou fora do
  plano**: `registrar_recebimento` num pedido legado grava o documento e **não** lança
  estoque — é a dupla escrita com o sinal trocado, e a condição que a impede não estava
  coberta por teste nenhum. Mutação de sanidade: trocar a condição por `True` mata só
  esse teste.
- [x] **Step 5:** commit — `fix(compras): o estoque passa a nascer do atesto, nao da emissao do pedido`

## R5 — Exclusão do último recebimento, com estorno

- [x] **Step 1 (red):** excluir o último recebimento estorna os movimentos que ele gerou
  e recalcula a situação; excluir um que **não** é o último → recusa; excluir quando o
  lote gerado já teve saída → recusa, dizendo qual item já foi consumido. **Mais dois
  fora do plano**: excluir o único recebimento devolve o pedido a `nao_recebido`, e
  `LEITOR` não exclui — excluir é escrita sobre o mesmo fato que atestar, e a checagem
  de papel não estaria coberta por teste nenhum.
- [x] **Step 2:** `excluir_recebimento(recebimento, usuario)` no mesmo serviço. O
  estorno usa `almoxarifado_movimento_id` — é para isso que a coluna existe. Valida
  tudo **antes** de apagar qualquer coisa: recusa que já estornou metade dos movimentos
  deixaria o estoque pior do que encontrou.
- [x] **Step 3 (green):** verdes. Mutação de sanidade, as duas cirúrgicas: desligar o
  "só o último" mata só o teste da sequência; `_ja_teve_saida` fixo em `False` mata só o
  do lote consumido.
- [x] **Step 4:** commit — `feat(compras): excluir o ultimo recebimento estorna o estoque que ele gerou`

## R6 — Tela de recebimento

- [ ] **Step 1 (red):** testes de rota: `GET` da tela por quem tem papel; `POST` grava e
  redireciona; `POST` em pedido legado (`exige_atesto=False`) **recusa com mensagem
  explícita**, em vez de aceitar e não fazer nada — que é o defeito atual do botão;
  `LEITOR` recebe 403.
- [ ] **Step 2:** rota nova em `compras_views.py` + template no molde de
  `templates/compras/`, utilizável no celular: um campo de quantidade por item já
  preenchido com o que falta, observação, e o par encerrar-saldo + motivo.
- [ ] **Step 3:** em `templates/compras/detalhe.html`, o botão passa a apontar para a
  tela nova quando `pedido.exige_atesto`, e continua no `POST` antigo quando não. A
  situação de recebimento aparece no detalhe e na listagem.
- [ ] **Step 4 (green):** verdes.
- [ ] **Step 5:** commit — `feat(compras): tela de recebimento na obra, com parcial e encerramento de saldo`

## R7 — Consistência e o gancho da fase financeira

- [ ] **Step 1 (red):** `valor_atestado(pedido)` = Σ (quantidade recebida × preço
  unitário), incluindo item de texto livre e ignorando o saldo não entregue; o script de
  consistência acha drift quando alguém escreve `situacao_recebimento` na marra.
- [ ] **Step 2:** `valor_atestado` no serviço.
- [ ] **Step 3:** `scripts/verificar_consistencia_recebimento.py`, no formato de
  `scripts/verificar_consistencia_progresso.py`: compara o persistido com
  `situacao_para`, `--json`, exit 0 consistente / 1 drift / 2 erro de uso.
- [ ] **Step 4 (green):** verdes.
- [ ] **Step 5:** commit — `feat(compras): valor atestado e sensor de drift da situacao de recebimento`

---

## Gate final

- [ ] `tests/test_recebimento_atesto.py` inteiro verde.
- [ ] Suítes vizinhas sem regressão: `-k "compra or almoxarifado or requisicao"`.
- [ ] Num tenant de dev com a flag **desligada**: emitir pedido, conferir por `psql` que
  o estoque entrou na emissão exatamente como antes.
- [ ] No mesmo tenant com a flag **ligada**: emitir, receber parcial, receber o resto,
  encerrar saldo — conferindo os movimentos e a situação a cada passo.
- [ ] `scripts/verificar_consistencia_recebimento.py` sem drift nas obras de dev.
- [ ] Runbook curto no fim do spec: como ligar a flag num tenant e o que conferir depois.

## Riscos

| Risco | Mitigação |
|---|---|
| Mexer no almoxarifado quebra tenant em produção | Tudo atrás de `exige_atesto`, que é carimbado por pedido. Tenant sem flag não muda de comportamento, e o teste da R4 Step 1 (quarto caso) guarda isso |
| Número da migration colidir com o dev | Conferir `migration_history` antes de fixar 283/284 (lição registrada na B6.1) |
| Dupla escrita voltar num refactor futuro | A regressão explícita da R4 Step 1 é o guarda permanente |
| `situacao_recebimento` sair de sincronia | Sensor de drift da R7, no padrão do cronograma |
