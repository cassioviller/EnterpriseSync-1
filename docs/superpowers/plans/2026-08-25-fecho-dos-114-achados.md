# Fecho dos 114 achados — o que o code review do app inteiro descobriu

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recomendado) ou superpowers:executing-plans para executar este plano task a task. Os passos usam checkbox (`- [ ]`) para acompanhamento.

> **Estado em 2026-08-25 (varredura de fecho):** 🟡 **ABERTO — escrito hoje, nada executado.**
>
> Nasceu da varredura de 25/08: dez passadas de `/code-review` por módulo sobre
> 286.517 linhas em 649 arquivos. Achados brutos, com `arquivo:linha` e cenário de
> falha, em `docs/auditoria/achados-code-review-2026-08-25.md`.

> **25/08 — este documento virou SPEC, não plano.** A varredura de escopo da
> `writing-plans` reprovou-o como plano único: ele cobre **seis subsistemas
> independentes**, e cada onda produz software funcionando e testável por conta
> própria. Foi quebrado em um plano por onda. Este arquivo continua sendo a
> evidência, o agrupamento por causa e o lugar das decisões D1/D2/D3 — os planos
> de execução o citam como `**Spec:**`.
>
> | Onda | Plano de execução | Tasks | Estado |
> |---|---|---|---|
> | 1 — o dinheiro entra errado (5 achados) | `2026-08-25-onda-1-parser-de-dinheiro.md` | 6 | ✅ escrito. 🔬 O código do plano foi **extraído e executado**: 32 passed |
> | 2 — o tenant vaza (14) | `2026-08-25-onda-2-o-tenant-para-de-vazar.md` | 8 | ✅ escrito |
> | 3 — o valor duplica ou some (16) | `2026-08-25-onda-3-o-valor-para-de-duplicar.md` | 10 | ✅ escrito. A 16ª (`financeiro_service.py:619`) **não está lá** — espera a D2 |
> | 4 — o relatório que nunca funcionou (11) | `2026-08-25-onda-4-o-relatorio-passa-a-funcionar.md` | 7 | ✅ escrito. Duas tasks bloqueadas por D3/D4 |
> | 5 — grava o que foi recusado (10) | `2026-08-25-onda-5-o-recusado-para-de-ser-gravado.md` | 8 | ✅ escrito |
> | 6 — os testes prometidos | `2026-08-25-onda-6-os-testes-prometidos.md` | 6 | ✅ escrito. Derrubou **dois** resíduos que eram falso alarme |
>
> 🔬 **Profundidade, medida — não é uniforme, e é de propósito.** Das **45 tasks**,
> **28 trazem o código de teste escrito por extenso** e **15 estão comprimidas**
> na forma *"Step 1-5: RED, correção, verde, commit"*, com o `arquivo:linha`, o
> cenário de falha e a correção descritos, mas sem o teste redigido. As
> comprimidas concentram-se nas ondas 4, 5 e 6, e são as de defeito **avulso** —
> onde não há raiz comum a extrair e o teste é mecânico. **Toda task de raiz
> comum** (o parser, o resolvedor de tenant, o saldo de estoque, o decorador de
> undo, a DRE) está por extenso. Se for executar uma comprimida e quiser o teste
> redigido antes, peça.
>
> **Ordem recomendada:** 1 → 2 → 3 → 5 → 4 → 6. A Onda 1 destrava o push; a 2 é a
> de maior superfície exposta; a 4 vem depois da 5 porque a Task 2 dela **torna
> exploitável** um furo que a Onda 2 fecha, e porque a Fase 8 pode reescrever o
> mapa de contas que ela conserta.


**Goal:** Fechar os 114 defeitos que a varredura do app inteiro encontrou, começando pelos que **hoje, com dado real, estão errando dinheiro ou cruzando tenants** — e deixar guarda de teste em cada um, para que nenhum volte.

**Architecture:** Os 114 achados **não** são 114 problemas. Agrupados por causa, viram **seis ondas**, e cinco delas têm uma raiz única que se conserta num lugar só e se aplica em muitos. A onda 1 é um parser; a onda 2 é uma função de tenant; a onda 3 é a disciplina pai×filho do `GestaoCusto`. Consertar por arquivo, na ordem em que o review os cuspiu, seria escrever a mesma correção nove vezes e errar em três.

**Tech Stack:** Flask + SQLAlchemy 2.0.41, PostgreSQL, pytest, Jinja2. Migrations pelo runner caseiro de `migrations.py` (tupla ordenada, não Alembic).

**Spec:** este plano é sua própria spec — a evidência é o documento de achados, e cada task cita `arquivo:linha`. Contexto de convenções em `CONTEXT.md`, `PLANO-NUCLEO.md` e `ESTADO-ATUAL.md`.

---

## 🔴 Bloqueios e decisões antes de começar

### D1 — o push dos 25 commits está bloqueado por um defeito de dinheiro

🔬 `main` está **25 commits à frente do `origin`**, e a Fase 6 inteira está só nesta
máquina. Mas 📖 `views/aditivos_views.py:102` infla contrato em **100×** e lança a
diferença no razão. **Empurrar antes de corrigir é publicar o defeito.** A Task 1.1
existe para destravar exatamente isto, e é a primeira coisa a fazer.

### 🔴 D2 (DECISÃO SUA) — o teste que afirma o defeito como intencional

📖 `financeiro_service.py:619` exclui os "gêmeos" de `saidas_previstas`, mas
`ContaPagar` **nunca** alimenta essa soma — 🔬 confirmado: aparece nas linhas 430-800
só dentro da subquery `_gemeos_reembolso`. A obrigação não muda de lado: **evapora**.
Um pedido de R$ 100k pendente projeta saída zero. O comentário do próprio código
mede a exposição: *"580 gêmeos, R$ 490.950, 24% do valor aberto"*.

🔴 **`tests/test_b5_fluxo_gemeos_e_orfaos.py:100` afirma isso como comportamento
esperado.** Corrigir exige **mudar um teste verde**, e isso não se faz em silêncio.

**As três saídas:**
- **(a) A exclusão vira consciente de estado** — o gêmeo sai da projeção só quando a
  outra perna realmente entra. Recomendada: é a única que faz o número fechar.
- **(b) `ContaPagar` passa a alimentar `saidas_previstas`** e a exclusão fica —
  maior, mexe no fluxo de caixa inteiro.
- **(c) Fica como está** e o `saldo_final_projetado` ganha, na tela, o aviso de que
  ignora 24% do valor aberto. Barato e honesto, mas não conserta.

⚠️ **A Task 3.6 está bloqueada até você escolher.** Todo o resto anda sem isso.

### D3 — `views/vehicles.py` é seis rotas mortas ou seis rotas a consertar?

🔬 Nenhum template ou JS referencia a família `main.*` de veículos —
`veiculos_editar.html` posta para `frota.editar`, `/veiculos` redireciona para
`frota.lista`. As rotas estão **registradas e alcançáveis por URL**, mas mortas pela
interface, e 📖 seis delas quebram na primeira requisição (`:192` NameError, `:716`
campos de form inexistentes, `:925` `from sqlalchemy import Funcionario`, `:1321`
colunas inexistentes, `:834` campos inexistentes, `:665` BuildError). **Recomendação:
apagar, não consertar** — consertar código que nenhuma tela chama é criar
manutenção. A Task 4.5 assume apagar; diga se prefere o contrário.

## Global Constraints

- **TDD sem exceção.** Teste primeiro, RED conferido e citado no commit, depois o
  código. Vale inclusive para o que "é só um parser".
- **Um defeito de raiz comum se conserta na raiz.** Proibido copiar a correção para
  N chamadores: se nove lugares parseiam decimal, nasce **um** helper e os nove o
  chamam. A varredura provou o custo do contrário — 📖 `gestao_custos_views.py:234`
  existe porque o commit `6af4fe93` corrigiu `editar_filho` e esqueceu os irmãos.
- **Nenhuma correção de tenant pode falhar aberta.** Sem tenant resolvido: 403, nunca
  `admin_id IS NULL`. 📖 `utils.tenant.require_tenant()` é o helper fail-closed que
  já existe.
- **Nenhum teste verde é alterado sem decisão humana registrada.** Vale para o D2 e
  para qualquer outro que apareça no caminho.
- **Nada de migration nova** salvo onde a task disser. Onde disser, confira o máximo
  do repo **no dia do commit** e numere em sequência real. Nunca reserve faixa: 📖 o
  fantasma do 270 nasceu de renumerar para "organizar".
- **Gate verde antes de cada fecho de onda:** `bash run_tests.sh --gate`. A régua de
  23/08 é 2560 passed / 6 skipped / 2 xfailed.

---

## Onda 1 — o dinheiro entra errado (5 achados, 1 causa)

> **A causa é uma só:** cinco lugares parseiam decimal brasileiro à mão, cada um de
> um jeito, e **todos os cinco erram por fator de 100 ou 1000**. Nenhum tem sanidade
> entre o formulário e o razão.

- [ ] **Task 1.1 — nasce `utils/decimal_br.py`, com um único `parse_decimal_br`.**
  RED primeiro: `tests/test_decimal_br.py` cobrindo `"150000.00"`, `"150.000,00"`,
  `"1.500"`, `"1500"`, `"1,5"`, `""`, `None`, `"-100"`, e o caso ambíguo com os dois
  separadores fora de ordem. **Regra:** entrada ambígua é **recusada**, nunca
  adivinhada. 📖 `views/orcamentos_views.py` já tem `_parse_br_decimal` — comece dele,
  e o antigo passa a delegar.
- [ ] **Task 1.2 — `views/aditivos_views.py:102` passa a usar o helper.** 🔴 É o que
  destrava o push (D1). Teste provando que `150000.00` num campo
  `inputmode="decimal"` **não** vira R$ 15.000.000,00 e que o razão não recebe delta
  de R$ 14,85M.
- [ ] **Task 1.3 — `compras_views.py:2853`.** 📖 `"1.500"` → `1.5`: o pedido é gravado
  a **1/1000** do preço negociado, e como o valor é *menor* que o aprovado, a guarda 3
  (`valor_total > aprovado`) **deixa passar**. GCP, ContaPagar e a entrada do
  almoxarifado herdam o número errado. É o achado nº 6 da revisão da Fase 3, ainda
  vivo. Teste cobrindo o caminho de emissão inteiro, não só o parser.
- [ ] **Task 1.4 — `services/faixa_alcada_admin.py:206`.** 📖 `"30.000"` vira R$ 30,00
  e a escada continua monotônica, então `_violacoes` não levanta nada: a primeira
  faixa do tenant passa a cobrir só compras abaixo de R$ 30.
- [ ] **Task 1.5 — `financeiro_views.py:36` (`_parse_valor`) e `:525`/`:840`.** Duas
  coisas: o parser sem ramo para entrada só com ponto (`1.500` → R$ 1,50), e a
  **ausência de validação de sinal e de ordem de grandeza** em `valor_pago`. 📖 Hoje
  `-100` **credita** o banco (`saldo_atual -= -100`), deixa `saldo = 1100`, mantém
  PENDENTE e mostra sucesso. Valide também em
  `FinanceiroService.baixar_pagamento` (:110, :127) — a view não pode ser a única
  guarda. `receber_conta` (:840) é idêntico e entra junto.

---

## Onda 2 — o tenant vaza (14 achados, 1 raiz + 13 pontos)

> 🔴 **A raiz:** 📖 `multitenant_helper.py:25`. `get_admin_id()` só mapeia
> `tipo == 'funcionario'` para `current_user.admin_id`; **todo outro papel não-admin
> cai em `return current_user.id`**. `GESTOR_EQUIPES` e `ALMOXARIFE` são papéis vivos.
> Um gestor com `id=42, admin_id=7` recebe `admin_id=42` — **um tenant que não
> existe**. Tudo escrito por `financeiro_views`, `configuracoes_views`, `ponto_views`,
> `reembolso_views` e `crud_servico_obra_real` é carimbado nesse fantasma, invisível
> para o admin 7, e as leituras voltam vazias.
> 🔬 `utils/tenant.get_tenant_admin_id` e `auth.get_tenant_filter` tratam esses papéis
> **corretamente** no ramo `else`. Esta é a **única cópia divergente** — não escreva
> uma quarta.

- [ ] **Task 2.1 — `multitenant_helper.get_admin_id()` delega para
  `utils.tenant.get_tenant_admin_id`.** RED: teste com usuário `GESTOR_EQUIPES` e
  `ALMOXARIFE` provando que o `admin_id` resolvido é o do dono, não o `id` do próprio
  usuário. ⚠️ **Antes de mudar, meça:** se já existe dado carimbado no tenant
  fantasma em produção, a correção o torna invisível de uma vez. Se houver, este item
  ganha migration de saneamento com contagem antes e depois.
- [ ] **Task 2.2 — `views/rdo.py:2838`.** `get_admin_id_robusta` resolve tenant por
  `Funcionario.query.filter_by(email=...)` **sem escopo** e cai num `return 10`
  **hardcoded**. Delegar para o helper único; o fallback numérico morre.
- [ ] **Task 2.3 — o portal do cliente para de mostrar compra interna.** 📖
  `portal_obras_views.py:304`: `compras_resolvidas` continua sem o filtro
  `tipo_compra == 'aprovacao_cliente'`. É **exatamente** o vazamento que o docstring
  de `_get_compra_do_portal` (:511) descreve como corrigido — a correção entrou nas
  duas rotas de ação e **não** na listagem que o próprio docstring aponta. Junto:
  `:645` (`upload_comprovante`) e `:720` (`ver_comprovante`), que resolvem a compra
  por `filter_by(id, obra_id)` sem `admin_id` nem `tipo_compra` — o segundo faz
  `send_file` do comprovante para visitante anônimo.
- [ ] **Task 2.4 — FKs vindas de formulário, sem checagem.** Um helper de validação e
  seis pontos: 📖 `gestao_custos_views.py:234` e `:1074` (o commit `6af4fe93`
  corrigiu só `editar_filho:550`), `transporte_views.py:204` (`obra_id`,
  `categoria_id`, `funcionario_id`, `veiculo_id`, `centro_custo_id` — só `osc_id` é
  validado), `views/almoxarifado/itens.py:110` e `:165` (`categoria_id`),
  `financeiro_views.py:895` e `gestao_custos_views.py:822`/`:262`
  (banco/fornecedor/subempreiteiro).
- [ ] **Task 2.5 — `veiculos_services.py:167`.** `setattr` cego sobre
  `request.form.to_dict()`: um POST com `admin_id=99` transfere o veículo **e o
  histórico em cascata** para outro tenant. Lista branca de campos, nunca lista negra.
- [ ] **Task 2.6 — `rdo_editar_sistema.py:218` e `ponto_views.py:777`.** O RDO muda de
  obra (e de tenant) pelo formulário; `api_bater_ponto` cria `RegistroPonto` para
  funcionário de outro tenant **e devolve o nome dele**. `api_registrar_falta` tem o
  mesmo furo.
- [ ] **Task 2.7 — as consultas que esquecem `admin_id`.** 📖
  `contabilidade_views.py:1300` (join em `PlanoContas` só por `codigo`, quando a PK é
  composta `(admin_id, codigo)` — uma partida de R$ 840 em ~300 tenants semeados
  vira **R$ 252.000**), `contabilidade_views.py:1377` (`origem_id` do JSON lançando
  sob o `admin_id` do documento), `almoxarifado_utils.py:257` (dedup de NF por
  `xml_hash` global: o XML que outro tenant importou **nunca** pode ser importado
  aqui), `ponto_service.py:264` (`ConfiguracaoHorario` sem `admin_id`, e
  `api_salvar_configuracao` aceita qualquer `obra_id` — um tenant altera a matemática
  de atraso e hora extra de outro).
- [ ] **Task 2.8 — `vinculos_audit_views.py:38` para de falhar aberto.** `_admin_id()`
  devolve `get_tenant_admin_id()` direto e `Usuario.admin_id` é nullable
  (`models.py:122`): para funcionário sem `admin_id` todo filtro degrada para
  `admin_id IS NULL` e a página **abre sobre linhas órfãs** em vez de 403. Trocar por
  `utils.tenant.require_tenant()`.
- [ ] **Task 2.9 — `services/cliente_resolver.py:61`.** Com `cliente_id` explícito que
  não pertence ao tenant, a busca falha em silêncio, **cai** para casamento difuso por
  nome/e-mail e então **cria um Cliente novo**, sem log. O chamador
  (`event_manager.py:1244`) acredita que a regra 1 "vence sempre". FK inválida deve
  **erguer**, não inventar cliente.
- [ ] **Task 2.10 — apagar `auth.py:47` `get_tenant_filter()` e `:58`
  `can_access_data()`.** 🔬 Zero consumidores no repo — a mesma condição que
  justificou apagar `almoxarife_required` e irmãos na Fase 1, comentada no pé do
  próprio arquivo. 🔴 E são armadilha: `get_tenant_filter` devolve `None` tanto para
  "super admin vê tudo" quanto para "não autenticado", então o idiomático
  `if f: query.filter_by(admin_id=f)` **serviria as linhas de todo tenant a um
  chamador anônimo**.

---

## Onda 3 — o valor se duplica ou some (16 achados)

### 3a. Estoque que pode sair duas vezes

- [ ] **Task 3.1 — `quantidade_disponivel` passa a ser mantida em todo caminho.** 🔴 A
  raiz: 📖 `almoxarifado_utils.py:602` mantém só `estoque.quantidade`, enquanto a
  saída valida em `func.sum(quantidade_disponivel)` (`movimentos.py:597`). Quebra nos
  dois sentidos: ENTRADA manual de 100 cria lote com `quantidade_disponivel = NULL` e
  a saída recusa; **SAÍDA manual zera `quantidade` e deixa `quantidade_disponivel` em
  100 — as mesmas unidades saem de novo.** Mesma omissão em
  `movimentos.py:1066` e `:1330` (devolução: o material devolvido fica invisível e
  nunca mais pode ser emitido).
- [ ] **Task 3.2 — `movimentos.py:1045`.** `obra_id=estoque.obra_id or 1`, mas
  `estoque.obra_id = None` foi atribuído **três linhas antes** (:1031): a expressão é
  **sempre `1`**. Toda devolução serializada é carimbada com a obra de id 1 — obra
  arbitrária, possivelmente de outro tenant — e a obra real se perde.
  `relatorios.py:214` (consumo por obra) lê exatamente essa coluna.
- [ ] **Task 3.3 — `movimentos.py:411`/`:455` voltam a ser atômicas.** O `emit` roda
  **dentro** do laço, antes do commit da rota (:467), e o handler
  `criar_conta_pagar_entrada_material` commita (`event_manager.py:216`). Depois do
  item 1 a sessão já foi commitada: falha no item 3 faz `rollback()` que **não desfaz
  nada** — metade do carrinho fica no estoque e o chamador ouve que falhou. A rota de
  item único (:185, :236) emite **depois** do commit; esta divergiu. Junto:
  `movimentos.py:857`, que faz `continue` silencioso quando o lote não está mais
  DISPONIVEL e ainda responde `success: true` com a contagem cheia.

### 3b. `GestaoCustoPai` × filhos — a disciplina quebrada

- [ ] **Task 3.4 — `reembolso_views.py:330` e `:293`.** 🔴 Excluir um reembolso apaga o
  `GestaoCustoPai` **compartilhado**, e o cascade `all, delete-orphan`
  (`models.py:7203`) leva junto os filhos de **todos os outros reembolsos do mesmo
  funcionário**. Editar sobrescreve `pai.valor_total` com o valor de um único
  reembolso e nunca atualiza o filho. 📖 `transporte_views.py:565-579` documenta e
  evita exatamente esta armadilha — a correção existe, copie a disciplina.
- [ ] **Task 3.5 — `gestao_custos_views.py:1415` e `:1433`.** O pai nasce com
  `valor_total=valor_original` e o filho com `valor=saldo_cp`; a primeira edição chama
  `_recalcular_total_pai` e **o passivo encolhe pelo valor já pago, sem trilha**. E a
  migração "idempotente" monta filho sem destino, violando
  `ck_gestao_custo_filho_destino` — o `IntegrityError` estoura **fora** do `try` por
  registro e **toda a rodada se perde**, num botão anunciado como *"ação segura e pode
  ser repetida"*.
- [ ] **Task 3.6 — `financeiro_service.py:619`.** ⚠️ **BLOQUEADA PELA DECISÃO D2.**
- [ ] **Task 3.7 — `financeiro_service.py:752`.** Pai PARCIAL: o KPI usa o saldo
  restante enquanto `detalhes` lista os filhos pelo valor cheio — os R$ 600 já pagos
  aparecem **duas vezes na mesma tela**.

### 3c. Compras, folha e ponto

- [ ] **Task 3.8 — `services/financeiro_compra.py:433`.** 🔴 Falta a guarda
  `atestado > 0`. O caminho da ressalva D6 existe justamente para liberar conta com
  atesto em aberto; quando é usado, `atestado` é 0 e **toda parcela é reescrita para
  R$ 0,00**, com `saldo = 0 - valor_pago`. É a "conta de R$ 0,00 que desaparece de
  toda projeção de caixa" que o docstring de `criar_obrigacao` diz evitar. E
  `divergencia_nota_atestado` devolve `dentro=True` quando `atestado <= 0`, então nem
  o aviso dispara.
- [ ] **Task 3.9 — `financeiro_compra.py:420` e `:566`.** `liberar()` seleciona por
  `pedido_compra_id` **sem filtrar `fechamento_id`**: fechar um lote com a parcela 1
  de 3 libera as parcelas 2 e 3, pagáveis sem nunca terem estado em lote fechado. E
  `reabrir_lote` volta o `status` mas **não** reverte `situacao_liberacao`.
- [ ] **Task 3.10 — `folha_pagamento_views.py:148` — esta é a automação A12.**
  `reprocessar` apaga só `FolhaPagamento`; o `GestaoCustoPai`/`Filho` e o lançamento
  contábil da rodada anterior sobrevivem e são recriados: **a folha dobra no contas a
  pagar e no razão.** 🔬 A reconferência de 23/08 já a listava como ABERTA — o review
  chegou nela por caminho independente. Risque da lista das 25 ao fechar.
- [ ] **Task 3.11 — a mão de obra cobrada em dobro e em triplo.** 📖
  `services/folha_service.py:761` (atraso descontado duas vezes: as horas já estão em
  `horas_falta` e `desconto_atrasos` cobra de novo), `:1336` (usa `salario_bruto`, que
  **já inclui** HE e DSR, como "Salário Base" e **soma HE 50/100 e DSR outra vez**) e
  `:1444` (`processar_e_salvar_folha_obra` lança a folha **inteira do mês** contra
  *cada* obra trabalhada — o custo por obra e todo roll-up saem inflados). Junto:
  `services/custo_funcionario_dia.py:97` (para diarista o `componente_folha` é rateado
  e `custo_hora_normal` não: a tela mostra o dobro do lançado).
- [ ] **Task 3.12 — o ponto que não vira hora.** 📖 `ponto_views.py:1487` (a importação
  Excel **nunca calcula `horas_trabalhadas`**: o mês importado marca 0h, a folha cobra
  todo dia como falta cheia, nenhum custo de obra é gerado; o ramo de atualização
  ainda descarta `obra_id`/`tipo_registro`) e `:2446` (as duas rotas de ponto facial
  commitam sem `PontoService._calcular_horas`, e `/api/identificar-e-registrar` nunca
  emite `ponto_registrado`). Junto: `views/rdo.py:2867` (a edição unificada apaga
  `RDOMaoObra` em bloco sem `remover_custos_rdo` — o trabalhador removido **segue
  sendo cobrado**) e `:1888` (`reabrir_rdo` desfaz o percentual mas deixa o custo de
  MO no razão com o RDO em rascunho).

---

## Onda 4 — o relatório que nunca funcionou (11 achados)

> Todos com a mesma assinatura: **atributo ou classe que não existe**, engolido por um
> `except` que devolve forma vazia. Passam em teste de fumaça com base vazia.

- [ ] **Task 4.1 — a contabilidade passa a fechar.** 🔴 Três achados que se somam:
  `contabilidade_utils.py:621` (a DRE conta **só um lado** — estornar uma despesa de
  R$ 840 grava a partida inversa correta, mas o crédito é filtrado fora e a DRE
  reporta os R$ 840 **para sempre**, discordando permanentemente do balancete),
  `:871` e `contabilidade_views.py:619` (o `saldo_devedor` é decidido **depois** da
  normalização por natureza, então saldo credor normal cai na coluna de débito: um
  lançamento D Caixa 1.000 / C Receita 1.000 dá devedor 2.000 / credor 0), `:457` (o
  Balanço nunca acumula contas de resultado, então `balanceado` é False sempre que há
  atividade, e `abs(saldo)` soma **prejuízo acumulado ao PL**).
- [ ] **Task 4.2 — `contabilidade_utils.py:221` e o mapa de prefixos.** As três
  funções `contabilizar_*` leem atributos inexistentes (`f.salario_bruto`,
  `proposta.data_aprovacao`, `nota.fornecedor_nome`, `nota.valor_icms`): o endpoint de
  integração **500 nos três tipos**. E mesmo corrigido,
  `contabilizar_entrada_material` debita `valor_produtos + valor_icms` contra crédito
  de `valor_total`, disparando "Lançamento desbalanceado" sempre que o ICMS está
  embutido no preço — **que é a norma brasileira**. Junto: `:534`, cujo mapa de
  prefixos da DRE está **invertido** em relação a `criar_plano_contas_padrao` e
  deslocado um grupo em relação a `financeiro_seeds.py` (locação de equipamento
  reporta como CMV).
  ⚠️ **Este item conversa com a Fase 8.** O plano de 24/08 canoniza o plano de contas;
  se ele for executado antes, refaça o mapa **depois** dele, não agora.
- [ ] **Task 4.3 — `relatorios_financeiros_avancados.py`.** 🔴 O módulo é
  **inteiramente inoperante**, e responde `{"success": true, "dados": {}}` em vez de
  errar. Seis defeitos: `UsoVeiculo.km_rodado` (a coluna é `km_percorrido`, em seis
  lugares), `UsoVeiculo.horas_uso` e `CustoVeiculo.km_atual` (não existem;
  `km_veiculo` existe), `AlocacaoVeiculo` (**classe inexistente no repo**),
  `case([(cond, val)], else_=0)` (a forma de lista saiu no SQLAlchemy 2.0 e o ambiente
  roda 2.0.41 — `ArgumentError` reproduzido), `NameError` em :876, e um **produto
  cartesiano** em :512 que infla `custo_por_km` ~10×. **Decida antes de abrir:** este
  módulo tem dono e usuário? Se não, apagar é mais honesto que consertar.
- [ ] **Task 4.4 — os dois relatórios do almoxarifado que nunca rodaram.** 📖
  `views/almoxarifado/relatorios.py:39` (`filter_by(ativo=True)` numa tabela **sem
  coluna `ativo`** — `InvalidRequestError` reproduzido, 500 seco, nada captura) e
  `movimentos.py:1239` (`funcionario_id` quando a coluna é `funcionario_atual_id` — a
  rota de item único em :1019 acerta; esta devolve 500 "Erro ao processar operação"
  em **toda** devolução de carrinho). Junto: `relatorios.py:286` (`estoque_minimo` é
  nullable e aqui não tem guarda de `None`, ao contrário de `dashboard.py:52` e
  `itens.py:61`).
- [ ] **Task 4.5 — apagar as seis rotas mortas de `views/vehicles.py`.** ⚠️ Depende da
  **decisão D3**.
- [ ] **Task 4.6 — o vocabulário partido do almoxarifado.** 📖 `movimentos.py:1302`
  grava `'EM_MANUTENCAO'`/`'INUTILIZADO'`, fora do vocabulário de `models.py:5560`
  (`MANUTENCAO`, `DESCARTADO`). `funcionario_perfil.html:977` e
  `itens_detalhes.html:246` testam `'MANUTENCAO'`; `dashboard.py:93` e
  `relatorios.py:296` casam `EM_MANUTENCAO`. **O vocabulário está partido no meio** —
  item devolvido avariado não mostra selo em duas telas. Escolha um, migre o dado,
  e deixe teste guardando.
- [ ] **Task 4.7 — EVM e medição que mentem.** 📖 `services/evm.py:130` (`_pv_ate_hoje`
  soma só `etapa['meses']`, preenchido **apenas** para etapas `entregavel`, enquanto o
  BAC soma toda linha de custo: qualquer obra com custo indireto recebe **SPI
  estruturalmente inflado** e SV positivo mesmo em dia), `:100` (`cpi == 0.0` — EV=0,
  AC>0, o pior cenário possível — é tratado como "sem CPI ainda" e reporta `vac = 0`,
  exatamente no orçamento), `services/medicao_service.py:178`
  (`gerar_medicao_quinzenal` omite o fallback `percentual_do_servico_na_obra` que
  `_recalcular_imc_avanco` tem: essas obras geram **medição vazia para sempre**, com
  extrato PDF em 0%), `services/custo_orcado.py:84` (o fallback de obra é
  tudo-ou-nada enquanto o por serviço é por serviço, então o BAC subestima obra mista).

---

## Onda 5 — o estado que grava o que foi recusado (10 achados)

- [ ] **Task 5.1 — 🔴 `ponto_views.py:611` para de vazar traceback.** `/ponto/` e
  `/equipe/alocacao-principal` renderizam `traceback.format_exc()` **no HTML**,
  expondo caminhos, frames e **SQL com parâmetros vinculados** a qualquer usuário
  autenticado. É o item de maior severidade de segurança da varredura e o mais barato
  de fechar.
- [ ] **Task 5.2 — `cronograma_views.py:1017` e `:1618`.** Três `return 400` em
  `atualizar_tarefa` pulam o `db.session.rollback()`, ao contrário dos vizinhos em
  :1000/:1010/:1130. O `_com_undo` então chama `registrar_acao`, que autoflusha e
  commita: **a edição recusada é gravada e empilhada no undo**, contradizendo o
  docstring do próprio decorador. Idem `atualizar_vinculo`, que atribui `vinculo.tipo`
  e devolve 400 sem rollback — **TI vira II em silêncio**. Consertar no decorador, não
  em cada `return`.
- [ ] **Task 5.3 — `services/entregas_terceiros.py:340` e `:357`.** O toggle reverso
  zera `percentual_concluido` de toda tarefa não marcada: **subempreitada em 45% é
  apagada** no próximo salvamento de RDO que não a marque. E o `except` pelado devolve
  `(0, 0)` depois de já ter mutado a sessão, e o chamador commita: escrita parcial
  reportando que nada foi aplicado.
- [ ] **Task 5.4 — `services/cronograma_apontamento_service.py:397`.**
  `registrar_apontamento` lê `pct_ant` só de `percentual_realizado` (travado em 100)
  enquanto `recomputar_cadeia:246` prefere `percentual_acumulado`. Depois de uma
  superexecução (120/100), uma regressão real para 110% **passa por baixo** da guarda
  `RetrocessoNaoPermitido` e grava +10, que qualquer recompute vira **−10**.
- [ ] **Task 5.5 — as duas entregas da Fase 6 que não chegaram ao usuário.** 🔴
  `services/proposta_diff.py:88` lê `PropostaItem.subtotal`, **NULL** para todo item
  fora do caminho da Task #89: revisão que muda só `preco_unitario` aparece como
  "mantido" e a tela nova reporta **impacto R$ 0,00**. `PropostaItem.subtotal_calculado`
  existe exatamente para isso e não é usado em lugar nenhum. E
  `views/orcamentos_views.py:617`: **nem `orcamentos.comparar` nem
  `propostas.comparar` são linkados de template nenhum** — a Task 12 inteira foi
  entregue inalcançável.
- [ ] **Task 5.6 — `services/cronograma_proposta.py:602`.** Os ramos de reúso por
  chave natural reaproveitam a tarefa casada **sem restaurar `ativa`**: item suprimido
  e re-adicionado como novo fica **sem tarefa viva**, em silêncio.
  `natural_key_index` não filtra `ativa`.
- [ ] **Task 5.7 — o portal, o teto morto e as rotas sem papel.** 📖
  `portal_obras_views.py:663` (o fallback de 5 MB é morto: `app.py:159` põe
  `MAX_CONTENT_LENGTH = 64 MB`, sobrando rota **anônima, sem autenticação e sem rate
  limit** gravando 64 MB no volume a cada requisição), `:768` e `:798`
  (`toggle_portal` e `gerar_medicao` só com `@login_required`: qualquer FUNCIONARIO
  liga/desliga o portal — recarimbando +180 dias **sem rotacionar o token** — ou cria
  `MedicaoObra`), `:958` (`os.path.join` sem checar que o resultado fica sob
  `static/`: latente hoje, leitor de arquivo arbitrário amanhã), `:534`/`:576` (evento
  de trilha descartado nos retornos antecipados; e **dois** eventos `compra_aprovar`
  no ramo de governança).
- [ ] **Task 5.8 — os RDOs que quebram ou duplicam.** 📖 `views/rdo.py:2127`
  (`atualizar_rdo` lê `rdo.tempo_manha`, que não é atributo: **todo POST levanta
  `AttributeError`** — verificado em runtime), `:3070` (`obra_id` não vinculada;
  `NameError` escapa do `except` local), `:4002` (`salvar_rdo_flexivel` ignora
  `rdo_id` e não tem guarda de obra+data: **é o produtor dos RDOs duplicados** que os
  serviços de exportação contornam), `:3969` (colisão de `numero_rdo` checada por
  `admin_id` numa coluna `UNIQUE` global: linha com `admin_id` NULL gera
  `IntegrityError` em laço permanente), `:2969` e `crud_rdo_completo.py:602` (campos
  gravados em atributos não mapeados, perdidos em silêncio — inclusive a **autoria da
  finalização**).
- [ ] **Task 5.9 — frota e transporte.** 📖 `frota_views.py:499` (`km_atual = km_final`
  sem comparação: uso retroativo faz o **odômetro andar para trás** e cala o alerta de
  manutenção — as três rotas irmãs têm a guarda), `:741` (edição lê passageiros de
  `to_dict()`, só o primeiro do multi-select, e apaga `responsavel_veiculo` quando o
  campo não vem), `:1063` (`.join(FrotaVeiculo)` duplicado — confirmado no SA 2.0.41
  que não é deduplicado: o filtro por tipo do dashboard TCO **sempre erra**),
  `transporte_views.py:442` (lote grava sem `origem_id` e
  `_limpar_gestao_custo_filho` filtra por ele: excluir deixa o valor vivo em Contas a
  Pagar dizendo *"Gestão de Custos atualizada"*), `reembolso_views.py:34`
  (`url_for('main_bp.dashboard')` quando o blueprint chama-se `main`).
- [ ] **Task 5.10 — os índices que discordam das queries.** 📖 `models.py:7608`:
  `uq_contrato_versao_vigente` é `UNIQUE (obra_id) WHERE vigente_ate IS NULL`, mas
  todo leitor filtra por `(obra_id, admin_id)`. Uma linha com `admin_id` divergente —
  e a migration 273 **cita precedente real, a migration 266** — trava a obra
  **permanentemente**: `abrir_versao` não vê a linha, não a fecha, e seu INSERT viola
  o índice. Junto: `models.py:8648` (`versao` sem `server_default`, então schema novo
  e produção **discordam em silêncio**), `:7698` (cascade ausente no backref de
  `AditivoContrato`), `services/contrato_obra.py:407`, `views/aditivos_views.py:143`,
  `:147`, `:74`, `templates/aditivos/listar.html:50`,
  `templates/obras/detalhes_obra_profissional.html:1316` (o `url_for` sem guarda que
  transforma a falha tolerada do blueprint em **500 em toda obra**),
  `services/orcamento_versao.py:117` (toda revisão atribuída ao autor da v1).

---

## Onda 6 — os testes que os planos prometeram e ninguém escreveu

> Fecha os resíduos nomeados no índice de 25/08. Não é higiene: 🔬 **A05, A09 e A10
> foram dadas como ENTREGUES por leitura de código, sem nenhum teste guardando.**

- [ ] **Task 6.1** — `tests/test_a05_custo_mensalista_por_rota.py`,
  `tests/test_a09_dedup_nf_entrada_e_tenant_almoxarifado.py`,
  `tests/test_a10_ponto_manual_nao_perde_custo.py`. ⚠️ O de A09 vai **falhar de
  cara** — é o mesmo defeito da Task 2.7 (`almoxarifado_utils.py:257`). Escreva-o
  como RED da Task 2.7, não como teste novo.
- [ ] **Task 6.2** — `tests/test_b5_curva_baseline.py` e os quatro
  `tests/test_b6_404_{obras,frota,cauda,miscelanea}.py`.
- [ ] **Task 6.3** — `tests/test_isolamento_tenant_bloco1.py`, agora com o que a
  Onda 2 corrigiu. O isolamento é coberto hoje por `test_p1_isolamento_relatorios.py`,
  `test_gestao_custo_filho_tenant.py` e `test_arreio_almoxarifado_e_tenant.py` —
  nenhum cobre `multitenant_helper.get_admin_id`.
- [ ] **Task 6.4** — rodar `bash run_tests.sh --jornada`, que **nunca rodou**. Os 7
  blocos (59 passed) e a varredura (48/48) rodaram; a jornada, não.

---

## Verificação de fecho

- [ ] `bash run_tests.sh --gate` verde (régua: 2560 passed / 6 skipped / 2 xfailed) —
      e **se o número de verdes subiu, diga em quanto e por quê**.
- [ ] Todo teste alterado de verde para outra coisa tem decisão humana registrada
      neste arquivo.
- [ ] `docs/auditoria/achados-code-review-2026-08-25.md` atualizado com o veredito de
      cada achado: corrigido, riscado por decisão, ou adiado com motivo.
- [ ] `ESTADO-ATUAL.md` ganha a seção de 25/08.
- [ ] A12 riscada de `docs/reconferencia-backlog-2026-08-23.md`.
- [ ] Os 25 commits empurrados — **depois** da Task 1.2, nunca antes.
