# Fecho do Que Está Aberto — Implementation Plan

> ## 📍 PONTO DE RETOMADA — sessão encerrada em 02/09, ~23:40
>
> **Leia estas 12 linhas antes de qualquer coisa. Nada está no meio do caminho:
> a etapa anterior fechou inteira e está no remoto.**
>
> - 🔴 **PRIMEIRO: há commits presos.** O token do Git **expirou no meio da
>   sessão de 02→03/09** (`remote: Invalid username or token`). Os pushes até
>   `331f3cfc` passaram; os seguintes **não**. Reautentique (`gh auth login`, ou
>   reconecte o GitHub no painel) e rode `git push origin main` **antes de
>   qualquer trabalho novo** — conferindo depois com `git fetch` + comparação de
>   refs, nunca pela saída do `push`.
> - **Estado do git:** `main` à frente de `origin/main` (`331f3cfc`) pelos
>   commits de pré-voo de 03/09. Árvore limpa — só
>   `tests/reports/` fora do git, por regra. A branch `sdd/a-porta-irma` foi
>   mergeada e **apagada** em 02/09 (a ponta era `bbc2c56a`, contida na `main`
>   pelo merge `83670e76` — nada se perdeu). Ela nunca existiu no `origin`.
>   🔬 Sobraram duas branches locais antigas, **de outras frentes e fora deste
>   plano**: `sdd/onda-5-o-recusado-para-de-ser-gravado` e `sdd/reuniao-20-08`.
> - **Progresso:** **7 de 16 tasks.** A Task 11 fechou os 7 Steps, incluindo o
>   ritual da Task 10 e o **primeiro push: 125 commits**, a Fase 6 entre eles.
> - **Pisos vigentes** (não use nenhum anterior): gate **3247 passed / 8
>   skipped / 201 deselected / 72 xfailed / 0 failed**; suíte com browser
>   **3435 passed / 1 failed** — o `1 failed` é o achado **P4** do RDO
>   unificado, registrado na auditoria, e é o **único vermelho conhecido**.
> - ✅ **Seis agentes de leitura rodaram em 03/09 e o resultado já está
>   integrado neste plano.** As Tasks **8, 12 e 13** ganharam pré-voo (Step 0 /
>   Step 0-b, com os defeitos que eles acharam **neste plano mestre**, não só
>   nos portados); as Tasks **9, 14 e 15** ganharam seus documentos escritos
>   (`2026-08-31-issues-de-arquitetura.md`, `reconferencia-backlog-2026-09-02.md`
>   + `specs/2026-09-02-automacoes-design.md`, `specs/2026-09-02-fase-9-premissas.md`).
>   **Nenhuma task foi executada por eles** — pré-voo e plano são insumo; a
>   execução continua em fila, porque toca banco, migrations e gate.
> - ⚠️ **Três decisões novas esperam você**, todas nomeadas nos documentos:
>   reescrever ou enterrar a Fase 9a/9b; o que fazer com `obra.progresso_conclusao`;
>   e reabrir (ou não) o corte do A20.
> - **A PRÓXIMA É A TASK 7 (Onda 4).** Ela já nasce destravada: o **Step 0**
>   (pré-voo, com a correção 🔴 do item (d) — leia-o) e o **Step 0-b** (a D7,
>   respondida "apagar" em 02/09) estão escritos com sítio e linha.
> - **Comece assim** (o ritual manda branch nova por etapa, a partir da `main`):
>
> ```bash
> git checkout main && git pull origin main
> git checkout -b sdd/onda-4-relatorio
> cat .superpowers/sdd/2026-08-31-fecho-do-que-esta-aberto/progress.md   # o ledger PRIMEIRO
> ```
>
> - ⚠️ **O ledger não está no remoto.** `.superpowers/sdd/.gitignore` ignora
>   tudo — ele existe **só nesta máquina**. Se você retomar daqui, leia-o. Se
>   retomar de outra máquina, o que estava nele desta sessão está resumido neste
>   bloco e no Step 0 da Task 7, mas o histórico das rulings de 31/08 e 02/09
>   fica para trás.
> - ⚠️ **A lição que custou caro nesta sessão:** um pré-voo foi refeito sem ler
>   o ledger, e a nota resultante mandava **não procurar um defeito vivo**
>   (`AlmoxarifadoEstoque.ativo`, `views/almoxarifado/relatorios.py:39`). Está
>   corrigida no Step 0 (d) e na auditoria. **O ledger se lê antes.**
> - **Nada espera decisão humana para a Task 7.** Seguem pendentes, mas de
>   outras tasks: **FASE8-T1** (sem acesso a produção — vira premissa declarada
>   na Task 12) e o `RATIFICAR` da **VIGA-I** (Task 8).
> - **Sessão anterior:** https://claude.ai/code/session_01FPYxL6k71Ji3b2FqeqJ3ox


> **Estado em 2026-09-02:** 🟡 **EM EXECUÇÃO — 7 de 16 tasks fechadas**, e a
> primeira integração aconteceu: a `main` recebeu a etapa por merge `--no-ff`.
>
> ⚠️ **ESTENDIDO em 02/09** pelo design
> `docs/superpowers/specs/2026-09-02-a-lista-vai-a-zero-design.md`, que decidiu
> levar a lista a **zero** — inclusive a funcionalidade nova que este plano
> antes deixava de fora (Fase 8, automações, Fase 9a/9b). As Tasks **11–16** são
> novas. A numeração cresce **por acréscimo, não por renumeração**: 📖 o ledger
> em `.superpowers/sdd/2026-08-31-fecho-do-que-esta-aberto/progress.md`
> referencia T1–T10, e renumerar quebraria o rastro.
>
> 🔴 **A ordem de execução NÃO é a ordem dos números:**
>
> **T11 → T7 → T8 → T12 → T13 → T9 → T14 → T15 → T16**
>
> | Task | Estado |
> |---|---|
> | 1 — as três decisões sobem para quem decide | ✅ `0b7abc49` `556f1bc3` — **respondidas em 01/09** (`2026-09-01-decisoes-respondidas.md`) |
> | 2 — apagar `relatorios_financeiros_avancados.py` (D4) | ✅ `3d0873a4` `41b605d0` |
> | 3 — apagar as seis rotas mortas de veículos (D3) | ✅ `0b3f932c` `0d1a7c6d` |
> | 4 — Onda 2 (o tenant para de vazar) | ✅ nada a executar: já mergeada em `fed8f19b` (26/08); doc corrigido em `b13e23c9` |
> | 5 — `o-que-nao-persiste` (os cinco achados restantes) | ✅ 6/6 tasks, gate 2872/6 skipped |
> | 6 — Onda 6 (os testes prometidos) | ✅ **fechada em 02/09** — a última task dela (a jornada E2E) foi entregue pelo plano `2026-09-02-a-suite-browser-volta-a-valer.md` |
> | **11 — o que está a um passo, e a primeira integração** | ✅ `80c3bb31` `acc486ab` `bbc2c56a`, merge `83670e76` — gate **3247/8/201/72, 0 failed** (47:43) |
> | 7 — Onda 4 (o relatório passa a funcionar) | ⬜ **próxima** — já tem o pré-voo escrito (Step 0) e a D7 respondida (Step 0-b) |
> | 8 — Resgate da Espinha Financeira (agora **10 de 10**) | ⬜ |
> | **12 — Fase 8, o plano de contas canônico** | ⬜ |
> | **13 — família 404 (B6.4–B6.8)** | ⬜ |
> | 9 — as sete issues de arquitetura viram plano | 🟡 **o plano está ESCRITO** (`2026-08-31-issues-de-arquitetura.md`, 8 tasks) — falta executá-lo |
> | **14 — reconferência das automações → spec → planos** | 🟡 **reconferência e spec FEITAS** (`docs/reconferencia-backlog-2026-09-02.md`, `specs/2026-09-02-automacoes-design.md`) — faltam os 3 planos que a spec desenha, e uma decisão do dono |
> | **15 — reconferência de premissas da Fase 9a/9b → plano novo** | 🟡 **a reconferência está FEITA** (`docs/superpowers/specs/2026-09-02-fase-9-premissas.md`) — falta só a decisão do dono e, se for reescrever, o plano novo |
> | 10 — **muda de forma:** o ritual de integração entre etapas | ⬜ repetido |
> | **16 — o índice volta a valer, gate final, push** | ⬜ |
>
> ⚠️ **Este é um plano de SEQUENCIAMENTO.** Ele não reescreve as 47 tasks que
> já existem nos seis planos abertos — elas já estão escritas com TDD e RED
> citado nos seus planos de origem, e duplicá-las criaria uma segunda fonte de
> verdade que diverge na primeira correção. O que este plano faz é: **resolver
> as decisões travadas, ordenar a execução, definir o gate entre cada etapa, e
> integrar a branch.**
>
> Duas tasks (2 e 3) são exceção e trazem código próprio: são as duas remoções
> que estavam bloqueadas por decisão e agora foram decididas — pequenas,
> independentes e já pesquisadas na fonte.

> **Complemento de 01/09:** `2026-09-01-as-decisoes-viram-codigo.md` executou
> o trabalho órfão das decisões (a09, A04, A18-elo, A24-flag, SFace nativo,
> 18 rotas de veículos, falha-fechada e censo total do tenant — 17
> resolvedores fantasmas convergidos). Continuam SEM plano próprio, por
> decisão registrada:
> - **Automações A01, A08, A17, A20, A21, A23 (abertas) e A11, A13, A15,
>   A16, A22 (parciais)** → próximo plano a escrever:
>   `2026-09-XX-onda-das-automacoes.md`. São feature-sized; entrariam aqui
>   só como placeholder, o que a casa proíbe.
> - **Família 404 (70 xfail, B6.4–B6.8)** → as tasks JÁ EXISTEM em
>   `2026-08-06-rodada-b6-varredura.md` (seções B6.4–B6.8); o refactor de
>   ~60 sítios roda por lá, removendo os marcadores xfail à medida que fecha.
>   O padrão `except HTTPException: raise` dos 5 pontos medidos é parte dele.
> - **Os 225 usos de `admin_id` em query sem guarda de `None`** (medição da
>   onda "A Porta Irmã") → o risco cai muito com as Tasks 10–11 de 01/09 (o
>   `None` deixa de virar tenant fantasma e as guardas de rota abortam 403
>   antes da query), mas a varredura guard-a-guard continua sem dono —
>   registrar na onda das automações ou na issue B (falhas silenciosas).
> - **Resolvedores ANINHADOS em função** (`rdo_editar_sistema.py:29`,
>   `views/rdo.py:2864`) → fora do alcance do censo por construção;
>   consolidá-los é refactor das funções-mãe, vai junto na onda das
>   automações (registrados em `FORA_DO_CENSO` no próprio censo).
> - **`obra.progresso_conclusao`** → funcionalidade nova, não conserto;
>   entra na onda das automações ou morre — decisão do dono.
> - **Fase 9a/9b** → segue adiada; reabrir pela seção "Premissas a
>   reconfirmar" do próprio plano.
> - **psycopg2→psycopg3** → registrado em decisoes-respondidas.md; não
>   agendar antes de existir build de produção próprio.

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recomendado) ou superpowers:executing-plans para executar este plano task a task. Os passos usam checkbox (`- [ ]`) para acompanhamento.

**Goal:** Levar a zero a lista de trabalho em aberto do repositório — seis
planos, oito issues de arquitetura, quatro decisões humanas e uma branch não
integrada — fechando cada item pela ordem que respeita suas
dependências, ou marcando explicitamente o que só uma pessoa pode destravar.

**Architecture:** O trabalho aberto não é uma fila; é um grafo com três
bloqueios reais. **(1)** A Onda 4 depende da Onda 2 — sua Task 2 *torna
exploitável* um furo que a Onda 2 fecha, então executá-la antes é abrir o furo
de propósito. **(2)** Duas tasks da Onda 4 estavam presas às decisões D3 e D4,
agora tomadas (apagar, nos dois casos) — e este plano as absorve como Tasks 2 e
3, porque são remoções pequenas e independentes que não precisam esperar o
resto da Onda 4. **(3)** Dois planos — Fase 8 e Resgate da Espinha Financeira —
tocam decisões que **nenhum executor pode tomar**: medir produção, o
significado de `5.1.01`/`5.1.02`, e a regra de verba/lucro do telhado viga I.
🔬 **Mas o bloqueio é PARCIAL, e conferir isso mudou o plano:** no Resgate da
Espinha só a **Task 8 de 10** depende da decisão — as outras nove são porte de
código já escrito e testado, e entram normalmente (Task 8 deste plano). Na
Fase 8 o bloqueio é mais fundo, porque o próprio plano avisa que **cortar entre
as Tasks 3 e 4 "deixa o parque em dois estados"** — e a Task 4 é a travada.
A Task 1 escala as três decisões; o que dá para executar sem elas, executa.

**Tech Stack:** Flask, SQLAlchemy 2.0.41, PostgreSQL, pytest, Jinja2.

**Spec:** `docs/auditoria/achados-code-review-2026-08-25.md` (achados de origem)
e os seis planos abertos listados na tabela de File Structure. O índice de
estado histórico é `docs/planos-em-aberto-2026-08-25.md` — 🔬 **conferido em
31/08: está desatualizado**, escrito contra `main` em `657326c4` e não menciona
a Onda 5, `a-porta-irma` nem `o-que-nao-persiste`. A Task 10 o substitui.

## Global Constraints

- **Gate:** `bash run_tests.sh --gate` (= `pytest tests/ -m "not browser"`).
- **Piso vigente, medido em 02/09** (`tests/reports/gate_browser_2154.log`):
  **3247 passed, 8 skipped, 201 deselected, 72 xfailed, 0 failed** (47:43).
  Toda task que fecha uma etapa roda o gate e compara contra este piso. (Pisos
  anteriores: 3193/8 em 01/09, 2872/6 em 31/08, 2854/6 em 28/08 — não use
  nenhum deles.)
  🔬 Os **54** verdes acima de 01/09 têm dono, um a um, e a conta fecha:
  `test_contrato_formularios_e2e.py` (19, a guarda de seletor da Task 11),
  `test_suite_resumavel.py` (15, o runner retomável) e
  `test_contrato_isolamento_playwright.py` (20, o contrato de isolamento). O
  plano de 02/09 previa 3212 porque só contava o primeiro — os outros dois
  nasceram depois de ele ser escrito.
- **Piso da suíte com browser, medido em 02/09** pelo runner retomável:
  **3435 passed, 8 skipped, 72 xfailed** e **1 failed** — o achado P4, que a
  Task 11 registra. Fora esse, **0 failed**.
- **O skipped nunca sobe. Piso: 8.** 🔬 Em 28/08, 4 testes saíram do gate sem
  que nada sinalizasse, e isso só foi descoberto por acaso. Skip subindo é
  cobertura saindo sem aviso — se subir, pare e descubra por quê antes de
  seguir.
- **Os xfailed são `strict=True` e só DESCEM.** Piso: 72. Consertar o código
  que um `xfail` mede **exige remover o marcador no mesmo commit** — com
  `strict`, o conserto sem remoção falha o gate por XPASS.
- **Numeração de migrations — a lista viva.** 📖 A última é a **318**
  (`migrations.py:7540`, registro em `:7884`). Nunca reserve faixa: confira o
  máximo do repo **no momento de escrever** e numere em sequência real. 🔬
  Precedente: a Fase 6 queimou a 270 e renumerou 271→277. Quem governa a ordem
  de execução é a **tupla do registry**, não o maior número.
- **TDD sem exceção.** Teste primeiro, RED conferido e **citado no commit**,
  depois o código.
- **Nenhum teste prova por `inspect.getsource()`.** O que se afirma é olhado no
  banco, na resposta HTTP ou no `url_map`.
- ⚠️ **Um teste de guarda tem de reprovar também quando o próprio gatilho para
  de funcionar.** 🔬 Regra herdada da onda "A Porta Irmã", onde **três** dos
  testes propostos pelo plano passariam verdes sem nunca chegar ao código sob
  teste. Se o teste depende de um erro injetado, ele afirma primeiro que o erro
  ocorreu.
- **Integração a cada etapa fechada** (decisão do dono, 02/09 — substitui a
  regra de 31/08 de "merge só ao fim"). Gate verde → merge na `main` → push.
  🔬 O motivo era: **117 commits nunca empurrados** (a `main` 35 à frente do
  `origin`, a branch 82 à frente da `main`), incluindo a Fase 6 inteira, e eles
  só existiam nesta máquina. ✅ **Resolvido em 02/09 pela Task 11:** foram
  **125** (a rodada de 02/09 somou mais oito), e `origin/main` está em
  `31da1447`. A partir daqui a cadência vale para o que vier — cada etapa que
  fecha passa pelo ritual antes de a seguinte começar. A branch de trabalho segue sendo `sdd/a-porta-irma`
  até o primeiro merge; depois, branch nova por etapa a partir da `main`. Não
  use worktree — 📖 precedente de 21/08, worktrees quebraram sensores.
- ⚠️ **Todo `git push` é confirmado com o dono antes de acontecer.** O plano
  autoriza a cadência, não o gesto.
- **Recusar é não deixar rastro.** Todo `return 4xx` faz
  `db.session.rollback()` antes.
- **Arreio antes de arquivo novo.** 🔬 `tests/helpers_tenant.py` (`um_tenant`,
  `dois_tenants`, `cliente_de`) já existe. Use.
- **Varredura de pré-voo abre cada etapa.** Antes da primeira task de um plano
  portado, confira pares de tasks que compartilham arquivo, e cada task contra
  a árvore de hoje. 🔬 Foi ela que achou a colisão de migration da Task 8 — e
  vários destes planos foram escritos em 25/08, contra uma árvore que já não
  existe.
- **`2026-09-XX` em nome de arquivo** significa *a data do dia em que a task
  roda*. Substitua ao criar; não crie arquivo com `XX` no nome.

---

## 🔴 Decisões — o estado de cada uma

| # | Decisão | Estado | Consequência |
|---|---|---|---|
| **D3** | `views/vehicles.py`: apagar ou consertar as rotas mortas? | ✅ **APAGAR** (31/08) | Task 3 deste plano. Absorve a Task 5 da Onda 4 |
| **D4** | `relatorios_financeiros_avancados.py` tem dono? | ✅ **APAGAR** (31/08) | Task 2 deste plano. Absorve a Task 4 da Onda 4 |
| **D5** | O aditivo: garantia própria ou ligar `escopo_obra_ativo`? | ✅ **GARANTIA PRÓPRIA** (28/08) | Já executada na onda "A Porta Irmã" (`da778eba`) |
| **D6** | O de-para do plano de contas pode ser chaveado só por código? | ✅ **RESPONDIDA (01/09)** — chavear por **assinatura estrutural**, não por `(código, nome)`. 🔴 E a premissa da pergunta estava errada: 📖 `contabilidade_utils.py:514` diz que são **quatro** planos concorrentes, não dois | Destrava a **Task 12** deste plano |
| **VIGA-I** | A regra de verba/lucro do telhado viga I | ✅ **RESPONDIDA (01/09)** — **opção B** (markup uniforme, move `orcamento.margem_pct_global` até a venda total voltar a R$ 1.720.796,75). A opção **C está morta**: citada em quatro documentos e definida em nenhum. `RATIFICAR` — é escolha comercial | A Task 8 do Resgate deixa de ser resíduo. A **Task 8 deste plano vira 10/10** |
| **FASE8-T1** | Medir o plano de contas em **produção** (não em dev) | 🟡 **SEM ACESSO — vira premissa declarada** (decisão do dono, 02/09) | A Task 12 executa com **falha fechada e nomeada**; a medição vira ratificação posterior |
| **D7** | `exportacao_relatorios.py`: apagar ou consertar? | ✅ **APAGAR (02/09)** — achada pelo pré-voo da Task 7 e respondida no mesmo dia. É a **D4 outra vez**: módulo registrado e vivo (`main.py:157`), inoperante por três defeitos, devolvendo `{'success': True, 'resumo': {}}` | Vira o **Step 0-b da Task 7**, no padrão das Tasks 2 e 3: remoção + extinção congelada no `url_map` |

⚠️ **O bloqueio dos dois é PARCIAL — e a primeira versão deste plano errou
isso.** A conferência na fonte, em 31/08, mostrou:

- **Resgate da Espinha Financeira:** 🔬 o cabeçalho do plano diz "**uma única
  task** presa a decisão de negócio", e a Task 8 confirma: *"Se o Cássio não
  decidir, entregue as Tasks 1–7 e 9–10 e deixe esta nomeada como resíduo."*
  **Nove das dez tasks entram na fila** — são porte de 2.542 linhas já escritas
  e testadas no PR #6. Isso virou a **Task 8** deste plano.
- **Fase 8:** 🔬 a D6 diz que *"as Tasks 1, 2, 3 e 5 a 10 não dependem dela"*,
  mas a seção "Onde a fase pode ser cortada em duas" diz o contrário sobre a 3:
  *"Não corte no meio da 3–4: aposentar o semeador sem migrar as `5.x` deixa o
  parque em dois estados."* **O plano se contradiz**, e a metade insegura é a
  que age sobre dados de todos os tenants.

> **Atualização de 02/09 — a contradição deixou de importar.** Com a D6
> respondida, a fase **não é mais cortada**: as dez tasks entram juntas na
> **Task 12** deste plano, e o parque nunca fica em dois estados. O que
> substitui o bloqueio é a **premissa declarada com falha fechada** — a
> migration para e **nomeia o tenant** cuja assinatura não for uma das
> conhecidas. 🔬 Os 71 tenants indeterminados do banco de dev são a prova de
> que esse ramo será exercitado, não decoração.

---

## File Structure

| Arquivo | Ação | Responsabilidade |
|---|---|---|
| `docs/superpowers/plans/2026-08-31-decisoes-pendentes.md` | **Criar** | Task 1 — o pedido de decisão, com evidência |
| `relatorios_financeiros_avancados.py` | **Apagar** (942 linhas) | Task 2 |
| `main.py:163-169` | Modificar | Task 2 — tirar o registro do blueprint |
| `scripts/rastreio_modulos.py:50` | Modificar | Task 2 — tirar da tabela de rastreio |
| `views/vehicles.py` | Modificar (6 blocos) | Task 3 |
| `tests/test_fecho_rotas_extintas.py` | **Criar** | Tasks 2 e 3 — congela as extinções |
| `docs/superpowers/plans/2026-08-25-onda-2-*.md` | Executar + marcar | Task 4 |
| `docs/superpowers/plans/2026-08-28-o-que-nao-persiste.md` | Executar + marcar | Task 5 |
| `docs/superpowers/plans/2026-08-25-onda-6-*.md` | Executar + marcar | Task 6 |
| `docs/superpowers/plans/2026-08-25-onda-4-*.md` | Executar + marcar | Task 7 |
| `docs/superpowers/plans/2026-08-24-resgate-espinha-financeira.md` | Executar 9/10 + marcar | Task 8 |
| `docs/superpowers/plans/2026-08-31-issues-de-arquitetura.md` | **Criar** | Task 9 |
| `docs/superpowers/plans/2026-09-02-a-suite-browser-volta-a-valer.md` | Executar T7 + marcar | Task 11 |
| `docs/superpowers/plans/2026-09-01-as-decisoes-viram-codigo.md` | Fechar T12 Steps 2 e 6 | Task 11 |
| `docs/auditoria/achados-code-review-2026-08-25.md` | Commitar (39 linhas soltas) | Task 11 — o achado P4 |
| `docs/superpowers/plans/2026-08-24-fase-8-plano-de-contas-canonico.md` | Executar 10/10 + marcar | Task 12 |
| `docs/superpowers/plans/2026-08-06-rodada-b6-varredura.md` | Executar B6.4–B6.8 + marcar | Task 13 |
| `docs/reconferencia-backlog-2026-09-XX.md` | **Criar** | Task 14 — a reconferência das automações |
| `docs/superpowers/specs/2026-09-XX-automacoes-design.md` | **Criar** | Task 14 — a spec que sai da reconferência |
| `docs/superpowers/specs/2026-09-XX-fase-9-premissas.md` | **Criar** | Task 15 — o veredito das premissas da 9a/9b |
| `docs/planos-em-aberto-2026-09-XX.md` | **Criar** | Task 16 — o índice que volta a valer |

---

### Task 1: As três decisões que só uma pessoa toma sobem para quem decide

> 🔴 Esta task **não escreve código** e **não pode ser fechada por um agente**.
> Ela produz o pedido de decisão e para. As Tasks 2-9 seguem sem depender dela.

**Files:**
- Create: `docs/superpowers/plans/2026-08-31-decisoes-pendentes.md`

**Interfaces:**
- Consumes: nada.
- Produces: nada que outra task deste plano consuma. Destrava, no futuro, a
  Fase 8 e o Resgate da Espinha Financeira.

- [ ] **Step 1: Reunir a evidência de cada decisão, da fonte**

```bash
# D6 — os dois seeders que trocam o significado de 5.1.01 e 5.1.02
grep -rn "5\.1\.01\|5\.1\.02" --include=*.py . | grep -v archive | grep -v test

# FASE8-T1 — o que dev diz hoje (para contrastar com produção)
grep -n "Task 1" docs/superpowers/plans/2026-08-24-fase-8-plano-de-contas-canonico.md

# VIGA-I — onde a regra de verba/lucro é citada
grep -rn "viga I\|viga-i\|telhado" docs/superpowers/plans/2026-08-24-resgate-espinha-financeira.md
```

- [ ] **Step 2: Escrever o pedido de decisão**

Crie `docs/superpowers/plans/2026-08-31-decisoes-pendentes.md` com esta
estrutura — **uma seção por decisão**, e cada uma respondendo três perguntas:
o que está travado, quais são as saídas, e o que muda em cada saída.

```markdown
# Decisões pendentes — o que trava a Fase 8 e o Resgate da Espinha

> **Para quem decide.** Três perguntas. Cada uma trava um plano inteiro que já
> está escrito e pronto para executar. Nenhuma delas é técnica: são o
> significado de uma conta contábil, uma medição de produção, e uma regra de
> rateio de lucro.

## D6 — o de-para do plano de contas não pode ser chaveado só por código

**O que trava:** `docs/superpowers/plans/2026-08-24-fase-8-plano-de-contas-canonico.md`,
Task 4 em diante (10 tasks, 3 de 21 arquivos existem).

**O problema:** os dois seeders aposentados trocam entre si o significado de
`5.1.01` e `5.1.02`. Um de-para chaveado só pelo código da conta aplicaria o
significado errado à metade do parque, silenciosamente — e um lançamento
contábil mal classificado não se anuncia.

**A tabela que expõe a colisão**, extraída dos dois seeders concorrentes:

| Código | `contabilidade_utils.criar_plano_contas_padrao` | `financeiro_seeds.PLANO_CONTAS_CONSTRUCAO` |
|---|---|---|
| `5` | CUSTOS | DESPESAS |
| `5.1` | CUSTO DOS SERVIÇOS PRESTADOS | DESPESAS OPERACIONAIS |
| **`5.1.01`** | **Materiais Diretos** | **MÃO DE OBRA** |
| **`5.1.02`** | **Mão de Obra Direta** | **MATERIAIS** |

**O aperto:** a spec manda escrever o de-para conta a conta, **não** derivado
por heurística de nome, "porque os nomes são justamente o que está
inconsistente". Mas 🔬 **a única evidência sobrevivente de qual seeder rodou é
`plano_contas.nome`.** A spec proíbe usar o nome, e sem o nome a Task 4 não é
executável corretamente.

**As saídas:**

- **(a) Chavear em `(codigo, nome)` com igualdade exata** contra os dois
  conjuntos fechados que estão no repositório — *recomendada pelo plano*. Não é
  heurística: é reconhecer a assinatura de um dos dois seeders conhecidos.
  Qualquer par fora dos dois conjuntos **faz a migration falhar e nomear o
  par**. Preserva o "nunca chutar"; derivar por semelhança de string
  (`'MÃO DE OBRA' ≈ 'Mão de Obra Direta'`) segue proibido.
- **(b) Manter a regra literal da spec** (só `codigo`) — mandaria material para
  pessoal em metade do parque, **em silêncio**, porque a partida migra sem
  falhar.
- **(c) Adiar a Fase 8** até haver outra evidência de proveniência além do nome.

**O que muda em cada uma:** (a) destrava as 10 tasks e assume que os dois
conjuntos do repositório cobrem todo o parque — se algum tenant tiver um plano
de contas de terceira origem, a migration para e mostra qual. (b) é a única que
corrompe dado. (c) mantém o status quo: dois significados para o mesmo código,
e relatórios que não se comparam entre tenants.

## FASE8-T1 — medir o plano de contas em produção

**O que trava:** a mesma Fase 8, na raiz. A Task 4 estaria sendo decidida com
número de banco de **dev**, que é majoritariamente resíduo de suíte de teste.

**A pergunta:** se produção mostrar `5.x` dominante, a spec da Fase 8 está
errada e o canônico volta à mesa. Ninguém mediu.

## VIGA-I — a regra de verba/lucro do telhado viga I

**O que trava:** `docs/superpowers/plans/2026-08-24-resgate-espinha-financeira.md`
(10 tasks, 7 de 20 arquivos existem, porte de 2.542 linhas do PR #6).

**O que trava exatamente:** apenas a **Task 8 de 10** (migration 319: `verba`,
`lucro` e `pai` em `rdo_subempreitada_apontamento`). 🔬 As outras nove são porte
de código já escrito e testado, e estão sendo entregues pela Task 8 do plano de
fecho de 31/08 — **esta decisão não segura o resto.**

**A pergunta:** o "telhado viga I" precisa de **verba**, **lucro %** e a escolha
entre as **opções A/B/C**, mantendo a **venda total travada**.

**O que muda:** com a resposta, a migration 319 entra, o ramo de subempreitada
volta a `custo_nao_mo_atividade`, e os testes da Fatia 2
(`tests/test_resultado_fatia2_custo_nao_mo.py`) saem de `xfail`. Sem ela, o
resultado por atividade fica **sem o custo de subempreitada** — não erra, mas
mede menos do que promete, e o `xfail` é o registro disso.
```

⚠️ **O conteúdo acima foi extraído da fonte em 31/08** — a tabela de colisão
vem da seção D6 de `2026-08-24-fase-8-plano-de-contas-canonico.md`, e o escopo
do viga I vem da Task 8 de `2026-08-24-resgate-espinha-financeira.md`. Confira
que continuam valendo antes de enviar; não reescreva as saídas de memória.

- [ ] **Step 3: Commit**

```bash
git add docs/superpowers/plans/2026-08-31-decisoes-pendentes.md
git commit -m "docs(decisoes): as tres perguntas que travam a fase 8 e a espinha sobem para quem decide"
```

- [ ] **Step 4: PARAR e escalar**

Diga ao usuário, explicitamente, que a Fase 8 e o Resgate da Espinha Financeira
**permanecem abertos** e que este plano não os fecha. Não siga adiante
assumindo uma resposta.

---

### Task 2: Apagar `relatorios_financeiros_avancados.py` (D4)

> ✅ **Decisão D4 tomada em 31/08: apagar.** Absorve a Task 4 da Onda 4.
>
> 🔬 **Conferido na fonte em 31/08, antes desta task ser escrita:**
> - O módulo tem **942 linhas** e **3 rotas** (`/`, `/tco/<int:veiculo_id>`,
>   `/api/dados-financeiros`) sob o blueprint `relatorios_financeiros`
>   (`url_prefix='/relatorios/financeiros'`).
> - Suas duas chamadas de `render_template` apontam para
>   `relatorios/financeiros/dashboard.html` e `.../tco_detalhado.html` — e
>   📖 **o diretório `templates/relatorios/` NÃO EXISTE.** As rotas que
>   renderizam não têm o que renderizar.
> - 🔬 **Zero** testes referenciam o módulo. 🔬 **Zero** templates ou JS usam
>   `url_for('relatorios_financeiros.*')`.
> - Só dois arquivos o mencionam: `main.py:165` (registro) e
>   `scripts/rastreio_modulos.py:50` (tabela de rastreio).

**Files:**
- Delete: `relatorios_financeiros_avancados.py`
- Modify: `main.py:163-169`
- Modify: `scripts/rastreio_modulos.py:50`
- Test: `tests/test_fecho_rotas_extintas.py` (criar)

**Interfaces:**
- Consumes: nada.
- Produces: `tests/test_fecho_rotas_extintas.py`, que a Task 3 estende.

- [ ] **Step 1: Write the failing test**

Crie `tests/test_fecho_rotas_extintas.py`:

```python
"""As rotas que este repositório extinguiu, e a prova de que não voltaram.

Segue o padrão de `tests/test_b5_fluxo_gemeos_e_orfaos.py:210`, que congela a
extinção da família `main.*` de custo de veículo: a morte é PROVADA pelo
`url_map`, não afirmada por comentário. Um `grep` diz que ninguém chama; só o
`url_map` diz que ninguém PODE chamar.
"""
import os
import sys

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import main  # noqa: F401 — registra blueprints
from app import app

pytestmark = pytest.mark.integration


def _endpoints():
    return {r.endpoint for r in app.url_map.iter_rules()}


def test_relatorios_financeiros_avancados_esta_extinto():
    """🔴 D4 — o módulo respondia `{"success": true, "dados": {}}` em vez de
    errar, por seis defeitos independentes.

    🔬 As duas rotas que renderizavam apontavam para
    `templates/relatorios/financeiros/*.html`, e o diretório
    `templates/relatorios/` não existe — nunca existiu na árvore. Um relatório
    que não tem template não é um relatório quebrado, é um relatório que nunca
    funcionou.

    Apagar foi mais honesto que consertar: ninguém reclamou em meses porque
    ninguém conseguia usar.
    """
    vivos = {e for e in _endpoints() if e.startswith('relatorios_financeiros.')}
    assert not vivos, (
        f'o blueprint relatorios_financeiros voltou a registrar rotas: {vivos}')
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_fecho_rotas_extintas.py -v`
Expected: **FAIL** — três endpoints vivos
(`relatorios_financeiros.dashboard_financeiro` e as outras duas). Se passar de
primeira, **pare**: o blueprint já não registra, e o achado mudou.

- [ ] **Step 3: Write minimal implementation**

Apague o arquivo e as duas referências:

```bash
git rm relatorios_financeiros_avancados.py
```

Em `main.py`, remova o bloco de registro inteiro (linhas 163-169), que hoje é:

```python
# Registrar Relatórios Financeiros Avançados
try:
    from relatorios_financeiros_avancados import financeiros_bp
    app.register_blueprint(financeiros_bp)
    logger.info("[OK] Relatórios Financeiros Avançados registrado")
except Exception as e:
    logger.error(f"[ERROR] Erro ao registrar Relatórios Financeiros: {e}", exc_info=True)
```

Substitua por uma linha de lápide, no mesmo estilo do
`# Relatórios de uso detalhado removido (código obsoleto limpo)` que já existe
logo abaixo:

```python
# Relatórios Financeiros Avançados removido em 31/08 (decisão D4): módulo
# inoperante por seis defeitos, renderizando templates que nunca existiram
# (`templates/relatorios/`). Extinção congelada em
# tests/test_fecho_rotas_extintas.py.
```

Em `scripts/rastreio_modulos.py:50`, remova a entrada:

```python
    'Relatórios financeiros avançados': ['relatorios_financeiros_avancados.py'],
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_fecho_rotas_extintas.py -v`
Expected: **PASS**.

Run: `python -c "import main; print('app sobe')"`
Expected: `app sobe` — sem o registro, o app ainda tem de subir.

Run: `python -m pytest tests/ -k "relatorio or financeiro" -m "not browser" -q`
Expected: verde. ⚠️ Se algum teste cair, ele dependia do módulo morto — traga o
caso, não o conserte por reflexo.

- [ ] **Step 5: Commit**

```bash
git add -A tests/test_fecho_rotas_extintas.py main.py scripts/rastreio_modulos.py
git commit -m "fix(relatorios): o modulo financeiro avancado sai — 942 linhas que nunca renderizaram"
```

---

### Task 3: Apagar as seis rotas quebradas de veículos (D3)

> ✅ **Decisão D3 tomada em 31/08: apagar.** Absorve a Task 5 da Onda 4.
>
> 🔬 **As seis causas foram reconferidas na fonte em 31/08, uma a uma** — e
> **duas alegações do achado original não bateram** e precisaram ser
> reescritas. Não repasse a lista antiga; use esta:

| Linha | Função | Causa, verificada em 31/08 |
|---|---|---|
| `:192` | `processar_passageiro_veiculo` (helper de `novo_uso_veiculo_lista`) | `PassageiroVeiculo` **não está importado** — `views/vehicles.py:3` importa só `db, TipoUsuario, Funcionario, Obra`. NameError → `-1` → rollback com a mensagem **falsa** "já estavam registrados como passageiros" |
| `:665` | `deletar_uso_veiculo` | `url_for('main.detalhes_veiculo', veiculo_id=...)`, mas a assinatura é `detalhes_veiculo(id)` (`:1598`). BuildError **depois** do commit: a exclusão funciona e a tela diz "Erro ao excluir uso" |
| `:716` | `editar_custo_veiculo` | `form.km_custo` / `form.litros` não existem em `CustoVeiculoForm` (`forms.py:224`), que tem `km_atual` e `litros_combustivel`. **A edição de custo nunca gravou** |
| `:834` | `dashboard_veiculo` | `uso.horas_uso` sobre instâncias de `UsoVeiculo` — 🔬 **`horas_uso` é coluna de `RDOEquipamento` (`models.py:1451`), não de `UsoVeiculo`.** O achado original dizia "campos inexistentes"; o campo existe, no modelo errado |
| `:925` | `historico_veiculo` | `from sqlalchemy import Funcionario, Obra` → ImportError em toda requisição |
| `:1321` | `aprovar_lancamento_veiculo` | `item.aprovado = True` sobre `UsoVeiculo`/`CustoVeiculo` — 🔬 **nenhum dos dois tem a coluna** (`aprovado` é de `ServicoObraReal`, `models.py:663`). SQLAlchemy aceita o atributo em Python e não persiste: **commit vazio com flash de sucesso** |

> 🔬 **Prova de que estão mortas pela interface:** as **24** funções de rota de
> `views/vehicles.py` têm **zero** referências em `templates/` e `static/`
> (medido em 31/08, `url_for('main.<func>')` para cada uma). Nenhum link direto
> a `/veiculos` em template ou JS. A capacidade viva equivalente é o
> `frota_bp` (`frota_views.py`, 13 rotas).
>
> ⚠️ **O escopo é AS SEIS, não o módulo inteiro.** As outras 18 rotas estão
> mortas pela interface mas **funcionam**, e uma delas —
> `relatorios_veiculos` (`/veiculos/relatorios`) — é exercitada por
> `tests/test_browser_all_modules.py:647`. Apagá-las é outra decisão, e a
> Task 9 a registra como pendência, não como feito.

**Files:**
- Modify: `views/vehicles.py` (6 blocos + 1 helper órfão)
- Test: `tests/test_fecho_rotas_extintas.py` (criado na Task 2)

**Interfaces:**
- Consumes: `_endpoints()` de `tests/test_fecho_rotas_extintas.py` (Task 2).
- Produces: nada.

- [ ] **Step 1: Write the failing test**

Acrescente a `tests/test_fecho_rotas_extintas.py`:

```python
# ---------------------------------------------------------------------------
# D3 — as seis rotas de veículo que quebravam na primeira requisição
# ---------------------------------------------------------------------------

# 🔬 As seis, por endpoint. Cada uma quebrava por uma causa DIFERENTE, e três
# delas mentiam para o usuário: rollback com mensagem de sucesso (:192), erro
# numa exclusão que funcionou (:665), e commit vazio com flash de aprovação
# (:1321). A capacidade viva equivalente é o `frota_bp`.
SEIS_EXTINTAS = (
    'main.novo_uso_veiculo_lista',      # :192 NameError PassageiroVeiculo
    'main.deletar_uso_veiculo',         # :665 BuildError depois do commit
    'main.editar_custo_veiculo',        # :716 form.km_custo não existe
    'main.dashboard_veiculo',           # :834 horas_uso é de RDOEquipamento
    'main.historico_veiculo',           # :925 ImportError na linha de import
    'main.aprovar_lancamento_veiculo',  # :1321 aprovado não é coluna
)


@pytest.mark.parametrize('endpoint', SEIS_EXTINTAS)
def test_rota_de_veiculo_quebrada_esta_extinta(endpoint):
    """🔴 D3 — seis rotas registradas, alcançáveis por URL, e quebradas na
    primeira requisição.

    Consertar código que nenhuma tela chama é criar manutenção para uma
    funcionalidade que ninguém pediu — e três delas MENTIAM para o usuário,
    que é pior que quebrar em silêncio.

    O teste itera sobre AS SEIS, não sobre uma: apagar cinco e deixar a sexta
    é o padrão que a onda "A Porta Irmã" existiu para fechar.
    """
    assert endpoint not in _endpoints(), (
        f'{endpoint} voltou ao url_map — a capacidade viva é o frota_bp')


def test_a_familia_viva_de_frota_continua_registrada():
    """A contraprova: apagar as seis não pode ter levado a frota junto.

    Sem esta afirmação, o teste acima passaria também se alguém apagasse o
    app inteiro — um guarda que só sabe dizer "não existe" não distingue
    remoção cirúrgica de estrago.
    """
    vivos = {e for e in _endpoints() if e.startswith('frota.')}
    assert len(vivos) >= 13, (
        f'a família frota.* encolheu para {len(vivos)} — esperado >= 13')
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_fecho_rotas_extintas.py -v`
Expected: **FAIL nos seis casos** (`main.* voltou ao url_map`), e **PASS** em
`test_a_familia_viva_de_frota_continua_registrada`. Se algum dos seis passar
antes da remoção, **pare** — essa rota já não está registrada e a tabela acima
está velha.

- [ ] **Step 3: Write minimal implementation**

Em `views/vehicles.py`, apague **do decorador até o fim do corpo** de cada uma
das seis funções. Faixas medidas em 31/08 — **confira o nome da função antes de
cortar**, porque qualquer edição anterior desloca as linhas:

| Bloco a apagar | Faixa em 31/08 |
|---|---|
| `processar_passageiro_veiculo` (helper) + `novo_uso_veiculo_lista` | `:171-378` |
| `deletar_uso_veiculo` | `:636-676` |
| `editar_custo_veiculo` | `:677-731` |
| `dashboard_veiculo` | `:812-917` |
| `historico_veiculo` | `:918-1014` |
| `aprovar_lancamento_veiculo` | `:1305-1335` |

⚠️ **O helper `processar_passageiro_veiculo` (`:171`) sai junto** — 🔬 seus
únicos chamadores são `:324` e `:335`, ambos dentro de
`novo_uso_veiculo_lista`. Fica órfão no instante em que a rota sai.

⚠️ **O helper `organizar_passageiros_por_posicao` (`:379`) FICA** — 🔬 é usado
em `:556`, dentro de `detalhes_uso_veiculo`, que **não** está entre as seis.

No lugar do primeiro bloco removido, deixe a lápide:

```python
# Seis rotas de veículo removidas em 31/08 (decisão D3): registradas e
# alcançáveis por URL, mortas pela interface (zero referências em templates e
# JS) e quebradas na primeira requisição — três delas mentindo para o usuário
# (rollback com mensagem de sucesso, erro numa exclusão que funcionou, commit
# vazio com flash de aprovação). A capacidade viva é o `frota_bp`.
# Extinção congelada em tests/test_fecho_rotas_extintas.py.
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_fecho_rotas_extintas.py -v`
Expected: **PASS** — os seis e a contraprova da frota.

Run: `python -m pytest tests/ -k "veiculo or frota or uso" -m "not browser" -q`
Expected: verde. ⚠️ 🔬 `tests/test_b5_fluxo_gemeos_e_orfaos.py:210` já congela
uma extinção anterior da mesma família — ele tem de **continuar passando**.

Run: `bash run_tests.sh --gate`
Expected: **2854 passed** ou mais (o piso mais os testes novos), **6 skipped**,
**201 deselected**, **0 failed**. 🔬 O deselected não muda: nenhuma das seis é
exercitada por teste de browser — `/veiculos/relatorios` é `relatorios_veiculos`,
que **não** está entre as seis.

- [ ] **Step 5: Commit**

```bash
git add tests/test_fecho_rotas_extintas.py views/vehicles.py
git commit -m "fix(veiculos): as seis rotas que quebravam na primeira requisicao saem (D3)"
```

---

### Task 4: Onda 2 — o tenant para de vazar

> ⚠️ **Esta task vem ANTES da Onda 4, sempre.** 🔬 A Task 2 da Onda 4 *torna
> exploitável* um furo que esta onda fecha. Executar a Onda 4 primeiro é abrir
> o furo de propósito.

**Files:**
- Execute: `docs/superpowers/plans/2026-08-25-onda-2-o-tenant-para-de-vazar.md` (8 tasks)

**Interfaces:**
- Consumes: nada deste plano.
- Produces: o resolvedor de tenant corrigido, de que a Onda 4 (Task 7) depende.

- [ ] **Step 1: Ler o plano inteiro antes de tocar em código**

Run: `sed -n '1,80p' docs/superpowers/plans/2026-08-25-onda-2-o-tenant-para-de-vazar.md`

⚠️ **A Task 1 daquele plano é MEDIÇÃO OBRIGATÓRIA, não código.** Consertar o
resolvedor torna invisível, de uma vez, todo dado carimbado no tenant fantasma
— medir antes é a única chance de saber o tamanho do estrago. **Não pule para
a Task 2.**

- [ ] **Step 2: Executar as 8 tasks, uma a uma, pela sub-skill**

Use `superpowers:subagent-driven-development` (recomendado) ou
`superpowers:executing-plans`, task a task, com o ciclo TDD de cada uma.

⚠️ Ao escrever cada teste, aplique a constraint global: **o teste tem de
reprovar quando o próprio gatilho para de funcionar.** Antes de aceitar um
verde, pergunte se o teste chegaria ao código sob teste caso o defeito não
existisse.

- [ ] **Step 3: Gate**

Run: `bash run_tests.sh --gate`
Expected: **0 failed**, **skipped ≤ 6**, passed ≥ 2854 + os testes que a onda
acrescentou.

- [ ] **Step 4: Marcar o plano como fechado**

No cabeçalho de `2026-08-25-onda-2-o-tenant-para-de-vazar.md`, troque
`🟡 **ABERTO — pronto para executar**` por `✅ **FECHADO — 8/8 tasks**` com os
números reais do gate e os commits, no formato que
`2026-08-28-a-porta-irma.md` usa hoje.

- [ ] **Step 5: Commit**

```bash
git add docs/superpowers/plans/2026-08-25-onda-2-o-tenant-para-de-vazar.md
git commit -m "docs(onda-2): a onda fecha, com o gate e as 8 tasks marcadas"
```

---

### Task 5: `o-que-nao-persiste` — os cinco achados restantes do review

> Os cinco que sobraram do `/code-review max` sobre a branch da Onda 5, depois
> que a onda "A Porta Irmã" fechou os outros seis. Causa comum: **escrita que
> não chega ao banco, ou chega pela metade.**

**Files:**
- Execute: `docs/superpowers/plans/2026-08-28-o-que-nao-persiste.md` (6 tasks)

**Interfaces:**
- Consumes: nada.
- Produces: nada que outra task deste plano consuma.

- [x] **Step 1: Conferir que os cinco achados ainda existem na fonte**

Os cinco, e onde estão listados como abertos em
`docs/auditoria/achados-code-review-2026-08-25.md`, seção
"🔴 Abertos — os cinco que sobraram":

```bash
grep -n "portal_obras_views.py:647\|models.py:7616\|cronograma_proposta.py:609\|proposta_diff.py:92\|portal_obras_views.py:774" docs/auditoria/achados-code-review-2026-08-25.md
```

⚠️ O plano é de 28/08 e a árvore mudou desde então. **Reconfira cada um na
fonte antes de corrigir** — a própria onda "A Porta Irmã" encontrou duas
alegações do review que não batiam.

- [x] **Step 2: Executar as 6 tasks pela sub-skill**

Use `superpowers:subagent-driven-development` ou
`superpowers:executing-plans`, task a task.

- [x] **Step 3: Gate**

Run: `bash run_tests.sh --gate`
Expected: **0 failed**, **skipped ≤ 6**.
✅ **Medido em 31/08:** 2872 passed, 6 skipped, 201 deselected, 2 xfailed, 0
failed (46min44s). +18 verdes sobre o piso de 2854; skipped ficou em 6.

- [x] **Step 4: Marcar o plano e o documento de auditoria**

Feche o cabeçalho do plano, e em
`docs/auditoria/achados-code-review-2026-08-25.md` mova os cinco de
"🔴 Abertos — os cinco que sobraram" para uma tabela de corrigidos com o
commit de cada um — exatamente como a seção
"✅ Corrigidos pela onda 'A Porta Irmã' (31/08)" faz.

- [x] **Step 5: Commit**

```bash
git add docs/superpowers/plans/2026-08-28-o-que-nao-persiste.md docs/auditoria/achados-code-review-2026-08-25.md
git commit -m "docs(nao-persiste): a onda fecha, e os cinco achados restantes saem de abertos"
```

---

### Task 6: Onda 6 — os testes que os planos prometeram

> ✅ **FECHADA em 02/09.** As Tasks 1–5 entraram nas ondas de 31/08 e 01/09; a
> Task 6 (a jornada E2E, que nunca havia rodado) foi entregue pelo plano
> `2026-09-02-a-suite-browser-volta-a-valer.md`, que a nomeia explicitamente
> como sua Task 6. 🔬 A jornada rodou pela primeira vez em 02/09 e ficou verde
> depois do `160c7282` (o cliente nascia depois do GET). **Nada a executar
> aqui** — os Steps abaixo ficam como registro do que foi pedido.

> A menor das ondas abertas (377 linhas, 6 tasks). 🔬 Ela já derrubou dois
> resíduos que a medição mecânica apontara e eram falso alarme, e confirmou um
> real: zero testes citam `entrada_ja_lancada`.

**Files:**
- Execute: `docs/superpowers/plans/2026-08-25-onda-6-os-testes-prometidos.md` (6 tasks)

**Interfaces:**
- Consumes: nada.
- Produces: cobertura nova; o `passed` do gate sobe.

- [ ] **Step 1: Executar as 6 tasks pela sub-skill**

Use `superpowers:subagent-driven-development` ou
`superpowers:executing-plans`, task a task.

⚠️ Esta onda **só escreve testes**. O risco dela não é regressão, é o oposto:
**teste que nasce verde.** Todo teste desta onda tem de ter um RED medido e
citado no commit — se um teste passa na primeira execução, ele não provou nada
e não deve ser commitado como prova.

- [ ] **Step 2: Gate**

Run: `bash run_tests.sh --gate`
Expected: **0 failed**, **skipped ≤ 6**, e o **passed sobe** pelo número de
testes que a onda acrescentou. Se o passed não subir, a onda não entregou.

- [ ] **Step 3: Marcar o plano como fechado**

- [ ] **Step 4: Commit**

```bash
git add docs/superpowers/plans/2026-08-25-onda-6-os-testes-prometidos.md
git commit -m "docs(onda-6): a onda fecha, com os testes prometidos entregues"
```

---

### Task 7: Onda 4 — o relatório passa a funcionar

> ⚠️ **DEPENDE DA TASK 4** (Onda 2). Não comece antes de ela fechar.
>
> 🔬 As Tasks 4 e 5 daquele plano foram **absorvidas** pelas Tasks 2 e 3 deste
> — as duas eram as bloqueadas por D4 e D3, e as duas já estarão feitas.
> Restam **5 das 7**.

**Files:**
- Execute: `docs/superpowers/plans/2026-08-25-onda-4-o-relatorio-passa-a-funcionar.md` (Tasks 1, 2, 3, 6, 7)

**Interfaces:**
- Consumes: o resolvedor de tenant corrigido pela Task 4 deste plano.
- Produces: nada.

- [ ] **Step 0: O pré-voo desta etapa — a árvore de hoje já mudou o plano**

🔬 **Varredura feita em 02/09** (com o gate da Task 11 rodando; só leitura e
execução de checagem). A Onda 4 foi escrita em 25/08 e o adendo dela é de 28/08;
desde então as Tasks 2 e 3 deste plano e a onda de 01/09 passaram por cima dos
mesmos arquivos. O que mudou, e o que isso obriga:

**(a) Duas tasks ficaram vazias — e o Step 1 abaixo descreve a segunda errado.**
`relatorios_financeiros_avancados.py` não existe mais (`3d0873a4`). E
`views/vehicles.py` **também não existe**: as 18 rotas saíram inteiras em
`12703381` (01/09, "segunda leva"), não só as seis. ⚠️ O texto do Step 1 ainda
diz que as outras 18 "estão mortas pela interface mas funcionam, e a remoção
delas é decisão que ninguém tomou" — **está desatualizado**; corrija ao marcar.

**(b) 🔴 O defeito que motivou a D4 tem um gêmeo VIVO, e a Onda 4 não o lista.**
📖 `exportacao_relatorios.py` é blueprint registrado (`main.py:157`,
`url_prefix='/relatorios/exportacao'`) e consta da lista de módulos de
`app.py:1108` — o mesmo argumento que pôs `dashboards_especificos.py` no adendo
de 28/08. Em `_obter_dados_resumo_executivo` (`:373-418`):

- `:380` — `UsoVeiculo.km_rodado`. 🔬 Provado por execução, não por leitura:
  `AttributeError: type object 'UsoVeiculo' has no attribute 'km_rodado'`. A
  coluna real é `km_percorrido` (`models.py:5265`).
- `:396` — `ManutencaoVeiculo` e `:404`, `:480-483` — `AlertaVeiculo`: **nenhum
  dos dois está importado**. 📖 O import de `models` (`:36-38`) traz apenas
  `db, Veiculo, CustoVeiculo, UsoVeiculo` → `NameError`. E `AlertaVeiculo`
  **não existe em parte alguma do repo**: só o `AlertaVeiculoForm`
  (`forms.py:475`) — é o mesmo caso do `AlocacaoVeiculo` que o cabeçalho da
  Onda 4 cita para o módulo apagado.
- `:416-418` — `except Exception: logger.error(...); return {}`, e a rota
  `/api/preview-dados` (`:731-757`) devolve `{'success': True, 'resumo': {}}`.
  **É literalmente a mentira que a D4 mandou apagar**, viva noutro arquivo.
- Alcançável por três rotas: `/gerar-pdf` (via `:97`), `/gerar-excel` (via
  `:245`) e `/api/preview-dados` (`:746`).

⚠️ **Não conserte no meio.** Isto é achado, não task: registrado em
`docs/auditoria/achados-code-review-2026-08-25.md` e escalado como **D7** em
`2026-08-31-decisoes-pendentes.md` — apagar ou consertar é a mesma pergunta da
D4, e quem a respondeu foi o dono, não o executor.

**(c) Linhas que andaram.** O adendo de 28/08 aponta `dashboards_especificos.py`
`:394, :446, :461`; hoje são **`:396, :448, :463`**. Na Task 1, `:621` (DRE),
`:871` (balancete) e `:457` (Balanço) de `contabilidade_utils.py` **não são mais
o que o plano diz** — o arquivo foi tocado em 01/09 (`bef17c33`), e
`contabilidade_views.py` também (`a6afcb8e`). Ancore por **nome de função**, não
por linha: `calcular_dre_mensal:557`, `obter_dados_balancete:789`,
`gerar_balancete_mensal:352`, `gerar_balanco_patrimonial:406`.

**(d) 🔴 CORREÇÃO — a primeira versão deste Step 0 errou aqui, e o erro mandava
não procurar um defeito vivo.** Ela dizia que o `ativo=True` "numa tabela sem
`ativo`" do cabeçalho da Onda 4 era falso alarme, porque `Veiculo.ativo`
**existe** (`models.py:5186`). 🔬 `Veiculo.ativo` existe mesmo — mas **não é
dele que o plano fala**. A afirmação aponta para `AlmoxarifadoEstoque`, e o
defeito está **VIVO**: `views/almoxarifado/relatorios.py:39` faz
`AlmoxarifadoEstoque.query.filter_by(admin_id=admin_id, ativo=True)` e a classe
(`models.py:5562`) **não tem a coluna** — conferido por duas vias independentes,
`grep` na classe (zero ocorrências) e `hasattr(models.AlmoxarifadoEstoque,
'ativo') == False`. O relatório quebra na primeira linha da rota. 📖 O pré-voo
anterior, no ledger da casa
(`.superpowers/sdd/2026-08-31-fecho-do-que-esta-aberto/progress.md`), já tinha
medido isto e marcado como o **mais grave** da Onda 4 — quem escreveu o Step 0
não o leu antes. **Leia o ledger antes do pré-voo da próxima etapa.**
`AlocacaoVeiculo`, esse sim, não tem mais nenhuma referência no repo.

**(e) Alvos íntegros — as linhas do plano valem.** Intocados desde antes de a
Onda 4 ser escrita: `views/almoxarifado/relatorios.py` (22/07, `b30923b5`),
`services/evm.py` (03/08, `3612db6b`), `services/custo_orcado.py` (05/08),
`services/medicao_service.py` (24/08) e `views/almoxarifado/movimentos.py`
(27/08).

**(f) Pares que compartilham arquivo** (a regra de pré-voo da casa): Tasks 1 e 2
em `contabilidade_utils.py`; Tasks 3 e 6 em `views/almoxarifado/movimentos.py`.
Ordem numérica resolve as duas.

**(g) A régua da Onda 4 está morta.** Ela manda comparar contra **2560 passed,
6 skipped, 2 xfailed** — três pisos atrás. Vale o piso deste plano (Global
Constraints), não o dela.

**(h) Nada foi começado:** `tests/test_onda4_relatorio_funciona.py` não existe.

- [ ] **Step 0-b: Apagar `exportacao_relatorios.py` (D7), no padrão das Tasks 2 e 3**

✅ **A D7 foi respondida em 02/09: APAGAR** — mesma resposta e mesmo argumento da
D4. 🔬 O pré-voo confirmou o pressuposto do argumento: **zero referências em
`templates/` e `static/`** — o módulo está morto pela interface, exatamente como
os dois que já saíram.

**RED primeiro.** Em `tests/test_fecho_rotas_extintas.py`, acrescente a família
parametrizada (o arquivo já tem `SEIS_EXTINTAS` e a âncora
`test_o_url_map_esta_populado`, que impede afirmação vácua):

```python
EXPORTACAO_EXTINTA = (
    'exportacao_relatorios.painel_exportacao',
    'exportacao_relatorios.gerar_pdf',
    'exportacao_relatorios.gerar_excel',
    'exportacao_relatorios.enviar_relatorio_email',
    'exportacao_relatorios.api_preview_dados',
    'exportacao_relatorios.agendar_relatorio',
)
```

Rode antes de apagar: as seis têm de **FALHAR** (hoje estão registradas). RED
citado no commit.

**Depois, a remoção — cinco sítios, e o quinto é o que morde:**

| Onde | O quê |
|---|---|
| `exportacao_relatorios.py` | apagar o arquivo (≈800 linhas) |
| `main.py:157` | tirar `from exportacao_relatorios import exportacao_bp` e o registro |
| `main.py:209` e `app.py:1108` | tirar `'exportacao_relatorios'` das listas de módulos |
| `scripts/rastreio_modulos.py:77` | tirar `'Exportação de relatórios'` da tabela de rastreio |
| ⚠️ `tests/test_isolamento_tenant_bloco1.py:103` | **tirar `'exportacao_relatorios'` do censo de resolvedores.** 🔬 O censo é o teste da Onda 6/Task 5 (16 resolvedores × 5 papéis); apagar o módulo sem tirá-lo daqui **quebra o gate** — e é a única referência ao módulo fora dele mesmo e das listas |

E o comentário de extinção no `main.py`, no formato que as Tasks 2 e 3 usaram:
módulo inoperante por três defeitos independentes, blueprint registrado,
devolvendo `{'success': True, 'resumo': {}}`; evidência em
`docs/auditoria/achados-code-review-2026-08-25.md` (02/09).

⚠️ **O `km_rodado` NÃO morre com este arquivo.** Sobram `dashboards_especificos.py`
`:396`, `:448`, `:463` — vivos, registrados, e alvo do adendo de 28/08 da Onda 4.

- [ ] **Step 1: Marcar as duas tasks absorvidas, antes de executar**

Em `2026-08-25-onda-4-o-relatorio-passa-a-funcionar.md`, marque as Tasks 4 e 5
como executadas por este plano, com o commit, para que o executor não as refaça:

```markdown
### Task 4: [título original]

> ✅ **ABSORVIDA pelo plano de fecho (31/08), Task 2** — decisão D4 resolvida
> como "apagar". Commit: [hash do commit da Task 2].

### Task 5: Apagar as seis rotas mortas de veículos

> ✅ **ABSORVIDA pelo plano de fecho (31/08), Task 3** — decisão D3 resolvida
> como "apagar". Commit: [hash do commit da Task 3]. ⚠️ O escopo executado foi
> **as seis rotas quebradas**, não o módulo inteiro: as outras 18 rotas de
> `views/vehicles.py` estão mortas pela interface mas funcionam, e a remoção
> delas é decisão que ninguém tomou.
```

- [ ] **Step 2: Executar as cinco tasks restantes pela sub-skill**

⚠️ **A Task 2 daquele plano é a que dependia da Onda 2.** Confirme que a Task 4
deste plano fechou antes de tocá-la.

- [ ] **Step 3: Gate**

Run: `bash run_tests.sh --gate`
Expected: **0 failed**, **skipped = 8**, **xfailed ≤ 72**.

- [ ] **Step 4: Marcar o plano como fechado**

- [ ] **Step 5: Commit**

```bash
git add docs/superpowers/plans/2026-08-25-onda-4-o-relatorio-passa-a-funcionar.md
git commit -m "docs(onda-4): a onda fecha, com as duas tasks absorvidas pelo plano de fecho"
```

---

### Task 8: Resgate da Espinha Financeira — as dez tasks

> 🔬 **O bloqueio deste plano é de UMA task, não do plano.** O cabeçalho diz
> "uma única task presa a decisão de negócio", e a própria Task 8 dele instrui:
> *"Se o Cássio não decidir, entregue as Tasks 1–7 e 9–10 e deixe esta nomeada
> como resíduo."* Nove das dez entram.
>
> Não é feature nova: é **porte de 2.542 linhas já escritas e testadas** no
> PR #6 (`design/espinha-financeira-obra`), contra uma árvore que evoluiu 476
> commits em paralelo, do outro lado da fratura de linhagem de 22/07.
> 🔬 7 de 20 arquivos prometidos já existem na árvore.

> **Atualização de 02/09:** a VIGA-I foi respondida (**opção B**, markup
> uniforme) e a Task 8 daquele plano **deixa de ser resíduo**. São **10 de 10**.
> O Step 2 abaixo mudou de "marcar como resíduo" para "renumerar as migrations".

**Files:**
- Execute: `docs/superpowers/plans/2026-08-24-resgate-espinha-financeira.md`,
  Tasks **1–10**
- Modify: o mesmo arquivo — a renumeração das migrations (Step 2)

**Interfaces:**
- Consumes: nada deste plano.
- Produces: o *Resultado por Atividade* (valor agregado − custo incorrido, por
  atividade do cronograma), com alarme, EVM, lente de caixa, roll-up de
  portfólio e o importador de obra por planilha.

- [ ] **Step 0: O pré-voo desta etapa (feito em 03/09) — o que ele mudou**

🔬 Varredura sítio a sítio contra a árvore de hoje. **As 10 tasks continuam
válidas e nada do porte evaporou** — mas quatro precisam de emenda, e **as duas
correções mais graves eram deste plano mestre, não do plano portado**: o `sed`
do Step 2 (corrigido acima) e o Step 2b pela metade (idem).

**O que mais mudou, task a task do plano da Espinha:**

- **Task 3 → migration 319, Task 4 → 320, Task 8 → 321**, depois do `sed`
  corrigido. Máximo real hoje: **318**.
- 🔴 **Task 9 — `Files: Create` está errado.** 🔬
  `scripts/criar_orcamento_baia_rev10.py` **já existe e diverge** da branch (103
  linhas): a `main` tem o `main()` velho, que pega o primeiro ADMIN; a branch
  tem `criar_orcamento_baia(admin_id, xlsx_path)`, a forma reusável que o E2E
  chama. **É sobrescrita, não criação** — trate como merge consciente, não como
  arquivo novo. E 🔬 `tests/test_rdo_edicao_preserva_tarefa.py` **já está
  portado, byte a byte idêntico** (`b30923b5`): nada a fazer nele.
- ⚠️ **O hash do xlsx da Baia diverge** entre `main` e branch (14609 vs 14608
  bytes). O Step 1 da Task 9 manda "conferir o hash" e essa conferência
  **falha**. Confira por conteúdo, não por hash.
- ⚠️ **Task 1:** o `git fetch` que ela manda já não é preciso (o ref é local),
  mas **a tag ainda falta** — não pule essa parte. 🔬 O inventário do Step 2
  **bate exatamente** (537/291/27/63/174 + 4 templates) contra a branch
  congelada `a18f86e7` (15/06): o porte está inteiro e acessível.
- ⚠️ **Task 7:** a instrução "registrar em `app.py`, junto dos vizinhos de obra"
  está **certa** hoje — não a troque por `main.py`, que é RDO/portal.
- ⚠️ **Task 6:** o aviso do escritor único de contrato segue vivo
  (`services/contrato_obra.py:262`).
- **Tasks 2 e 5: sem emenda.** As assinaturas e chaves de retorno da 2 foram
  confirmadas; o Step 1 da 5 (reconfirmar o baseline) segue obrigatório e **não
  foi verificado** pelo pré-voo — é medição que exige rodar.

**Réguas podres, nos dois planos:** onde se lê **476 commits**, o número real
medido em 03/09 é **706** — 🔬 conferido com o próprio comando que o plano cita,
`git rev-list --count origin/fix/fase-0-estancar..main`. Os três sítios: este
plano em `:1048`, e o da Espinha em `:19` e `:495`. E o inventário "7 de 20
arquivos existem" é, medido, **4 de 21**. ⚠️ O que **não** muda com o número: as
linhagens continuam disjuntas e o PR #6 continua não sendo mesclável — é porte,
não merge.

📖 O relatório completo do pré-voo, com o método de cada medição, ficou em
`.superpowers/sdd/2026-08-31-fecho-do-que-esta-aberto/preflight-t8.md` —
⚠️ **gitignored**, existe só nesta máquina.

- [ ] **Step 1: Ler o plano e as specs que ele cita, antes de portar**

```bash
sed -n '1,60p' docs/superpowers/plans/2026-08-24-resgate-espinha-financeira.md
```

🔬 As specs que o porte argumenta contra:
`docs/superpowers/specs/2026-06-14-espinha-financeira-obra-design.md` (D1–D6),
o contrato cross-cutting em
`docs/superpowers/plans/2026-06-15-espinha-financeira-plano-mestre.md`
(DC1–DC11), `docs/adr/0004-*` (granularidade serviço→N atividades) e
`docs/adr/0005-*` (orçado = baseline congelado da Proposta).

- [ ] **Step 2: Renumerar as migrations do plano portado, ANTES de executar**

🔴 **O plano da Espinha escreve as migrations 317, 318 e 319 — e a 317 e a 318
já foram gastas.** 📖 `migrations.py:7505` (`_migration_317_chave_acesso_por_tenant`,
A09) e `:7540` (`_migration_318_flag_folha_rateio_encargos`, A24), ambas de
01/09. 📖 O plano avisa genericamente (`:46`) para conferir o máximo no dia,
mas os números literais estão nos **títulos das Tasks 3, 4 e 8**, nos **corpos
das funções**, nas **tuplas do registry** e nas **mensagens de commit**.

Confirme o máximo primeiro:

```bash
grep -n "_migration_3[0-9][0-9]_" migrations.py | tail -3
```

Expected: a última é a `318`. Se for maior, use o número real — a lista viva
das Global Constraints manda sobre este texto.

Agora renumere no plano da Espinha, **por conteúdo, nunca por número de linha**:

🔴 **CORRIGIDO em 03/09 — o `sed` que estava aqui produzia exatamente a colisão
que ele existe para evitar.** 🔬 Provado por execução, em cópia: com o texto
antigo (duas invocações, a 317→319 primeiro e a 319→321 depois), **as Tasks 3 e
8 saíam ambas na `321`** — porque a segunda invocação também casa a `319` que a
primeira acabou de criar. E o ⚠️ que acompanhava o bloco afirmava o **oposto**
do que acontece: dizia que rodar depois evitava a re-renumeração, quando é
rodar depois que a causa.

O correto é **ordem decrescente, num comando só** (a `319` sai da frente antes
de a `317` chegar nela):

```bash
F=docs/superpowers/plans/2026-08-24-resgate-espinha-financeira.md
sed -i 's/migration 319/migration 321/g; s/[Mm]igration 319/migration 321/g; s/migration 318/migration 320/g; s/migration 317/migration 319/g; s/_migration_317_template_item_peso_medicao/_migration_319_template_item_peso_medicao/g; s/\[Migration 317\]/[Migration 319]/g' "$F"
grep -n "31[7-9]\|32[01]" "$F"
```

⚠️ **`Migration` com M maiúsculo existe e o `sed` antigo não casava:** 📖
`2026-08-24-resgate-espinha-financeira.md:444` escreve `**Step 3: Migration
319**`. Confira **sítio a sítio**, não pela ausência de dígito: o esperado é
`peso_medicao` na **319**, `origem` na **320**, `verba/lucro/pai` na **321**, e
a tupla `(317, "Resgate Espinha — ...` do registry virando `(319, ...`.
🔬 Máximo real medido em 03/09: **318** (`migrations.py:7505` e `:7540`,
registry `:7883`-`:7884`) — os números 319/320/321 seguem livres.

- [ ] **Step 2b: A Task 8 daquele plano ENTRA — a VIGA-I foi respondida**

Substitua o aviso de bloqueio no cabeçalho da Task 8 dele por:

```markdown
> ✅ **DESTRAVADA em 01/09 — opção B (markup uniforme).** O ajuste move um
> único parâmetro declarado (`orcamento.margem_pct_global`) até a venda total
> voltar a R$ 1.720.796,75. Não reduza margens item a item (opção A): isso
> muda a margem de itens que ninguém tocou e contamina a própria medida que
> esta fase entrega. A **opção C está morta** — citada em quatro documentos,
> definida em nenhum. `RATIFICAR` com o dono: é escolha comercial.
```

🔴 **E troque TAMBÉM o Step 1 da Task 8 dele — o pré-voo de 03/09 achou que este
Step 2b desarmava só metade do bloqueio.** 📖
`2026-08-24-resgate-espinha-financeira.md:442` ainda diz `**Step 1: 🔴 Confirmar
a decisão com o Cássio** (verba, lucro %, opção A/B/C). Sem isso, **pare
aqui**.` Quem executar lê o cabeçalho destravado, chega ao Step 1 e **para**.
Substitua por:

```markdown
- [x] **Step 1: A decisão já existe** — opção B (markup uniforme), respondida em
      01/09 (`2026-09-01-decisoes-respondidas.md`). ⚠️ O `RATIFICAR` com o dono
      segue pendente e é escolha comercial, mas **não bloqueia o porte**.
```

🔴 **A Task 8 dele precisa de um step que não existe: portar
`_registrar_custo_subempreitada`.** 🔬 Medido em 03/09: a função vive **só na
branch congelada** (`a18f86e7:cronograma_views.py:917`) e a `main` tem **zero**
ocorrências — mas `tests/test_resultado_fatia2_custo_nao_mo.py:184` a importa. E
📖 `cronograma_views.py` **não é citado em lugar nenhum** do plano da Espinha.
Sem esse porte, o Step 5 ("rodar e ver passar") não passa, o `xfail` da Fatia 2
nunca sai, e como ele é `strict=True` o `xfailed` **não volta ao piso de 72** —
o gate fecha vermelho por XPASS ou por falha, dos dois lados.

- [ ] **Step 3: Executar as nove tasks pela sub-skill**

Use `superpowers:subagent-driven-development` ou
`superpowers:executing-plans`, task a task.

⚠️ **Porte não dispensa RED.** O plano é explícito: *"Cada módulo portado ganha
teste antes de entrar — os testes da branch vêm junto, mas **não substituem o
RED**."* Um teste que veio pronto do PR #6 e passa na primeira execução contra
a árvore de hoje não provou que o porte funcionou; provou que o teste existe.
Rode-o contra a árvore **antes** do módulo entrar e veja o RED.

⚠️ **A Task 5 remove um ramo que a Task 8 devolve.** Agora que a Task 8 roda, o
ramo volta — e os testes da Fatia 2
(`tests/test_resultado_fatia2_custo_nao_mo.py`) **saem do `xfail` na Task 8, no
mesmo commit que os faz passar**. Com `strict=True`, deixar o marcador depois
do conserto falha o gate por XPASS. Entre a Task 5 e a Task 8 eles ficam
`xfail` e o `xfailed` do gate sobe; ao fim da Task 8 ele volta ao piso.

- [ ] **Step 4: Gate**

Run: `bash run_tests.sh --gate`
Expected: **0 failed**, **skipped = 8**, e os `xfailed` sobem (os da Fatia 2
entram como esperados-a-falhar). Passed sobe pelo porte.

- [ ] **Step 5: Marcar o plano como fechado**

```markdown
> **Estado em [data]:** ✅ **FECHADO — 10/10 tasks**, entregues pelo plano de
> fecho de 31/08, Task 8. A Task 8 destravou com a VIGA-I respondida em 01/09
> (opção B). Migrations **319, 320 e 321** (renumeradas: as 317 e 318 do texto
> original já haviam sido gastas em 01/09). Gate: [números reais].
```

- [ ] **Step 6: Commit**

```bash
git add docs/superpowers/plans/2026-08-24-resgate-espinha-financeira.md
git commit -m "docs(espinha): as 10 tasks entregues, migrations renumeradas para 319-321"
```

- [ ] **Step 7: Integrar (o ritual da Task 10)**

Execute a Task 10 deste plano. Ela é o ritual repetido: gate → suíte → merge →
push.

---

### Task 9: As sete issues de arquitetura viram plano, ou ficam adiadas por escrito

> **Atualização de 02/09:** são **sete**, não oito. A issue **D (fonte única do
> plano de contas)** é absorvida pela **Task 12** deste plano — a Fase 8 entrega
> exatamente a fonte única que ela pede. Por isso esta task **executa depois da
> T12**, e o Step 1 abaixo confirma a absorção em vez de "resolver a
> sobreposição".
>
> 🔬 `docs/superpowers/issues/` tem **8 issues** derivadas do plano de
> remediação de saúde de 08/06 (A a H), e **nenhum plano aberto as endereça**.
> Elas não são achados de review — são dívida de arquitetura: cache de
> instância ORM, `create_app()` único, fonte única do plano de contas,
> precificação única, N+1 de config por request, infra de testes e migrações.
>
> Adiar é uma resposta legítima. Adiar **sem registrar** é como elas chegaram
> a 31/08 sem ninguém notar.

**Files:**
- Create: `docs/superpowers/plans/2026-08-31-issues-de-arquitetura.md`
- Modify: `docs/superpowers/issues/README.md`

**Interfaces:**
- Consumes: nada.
- Produces: nada.

> ## ✅ O plano está ESCRITO (03/09) — `2026-08-31-issues-de-arquitetura.md`
>
> 1.289 linhas, **8 tasks** (7 de código + 1 de fecho). 🔬 Nenhuma cria
> migration — o máximo real é **318**, a Task 8 leva 319–321 e a Task 12 leva
> 322–323, então esta etapa não entra na disputa.
>
> **Cinco issues viraram task**, e duas trouxeram achado novo que ninguém tinha:
> - 🔴 **Issue E — o teste de paridade compara duas transcrições, e erra.** Ele
>   não confronta a implementação com a fonte: confronta duas cópias do mesmo
>   texto — e ainda assim **erra R$ 0,05** num caso da própria tabela, **10× a
>   tolerância que ele mesmo declara**.
> - 🔴 **Issue H — 316 linhas de teste que não testam nada.** 🔬 Conferido por
>   execução: `pytest tests/test_propostas_block_scripts_213.py --collect-only`
>   devolve **"no tests collected"**. O arquivo existe, é grande, e prova zero.
>   ⚠️ E ele não está sozinho: outros **20** arquivos embrulham um `main()` num
>   único `test_` — recorte adiado e nomeado no plano.
> - 🔴 **Issue B — o usuário é informado de sucesso quando o lançamento falhou.**
>   📖 `folha_pagamento_views.py:314-336`: o retorno de
>   `gerar_lancamento_contabil_automatico` é **descartado**, o `except` só loga
>   `warning`, e `:340` dispara `flash('Folha processada com sucesso!')` de
>   qualquer modo. 🔬 Conferido na fonte.
> - **Issue A:** os dois `@lru_cache` de `models.py:3187`/`:3285` devolvendo
>   entidade ORM — 🔬 **zero chamadores** hoje: é bug latente, e o plano decide
>   **converter em vez de apagar**, com o custo de errar escrito.
> - **Issue C:** 🔬 `app.py` registra 38 blueprints e `main.py` mais 15, mas a
>   guarda de layout só roda em `main.py:303`. ⚠️ O teste **tem de rodar em
>   subprocesso**: `conftest.py:65` já importa `main`, e sem isso a guarda passa
>   por **verdade vácua**.
>
> **Metade da issue D já estava fechada, por evidência:** o seeder idempotente
> (`contabilidade_utils.py:1641`, `ON CONFLICT (admin_id, codigo)`) e a PK
> composta (migration **218**, `migrations.py:7813`). ⚠️ O commit **não é
> citável** — `git log -S` cai em `b30923b5`, a reimportação do repo inteiro
> (1.437 arquivos): a prova é o código, e o plano diz isso em vez de fingir
> procedência. A outra metade da D é a **Task 12**.
>
> **Duas adiadas, com motivo escrito:** **F** — 🔬 a evidência não sobreviveu
> (zero `ConfiguracaoEmpresa.query` dentro de laço, e o cache por request já
> existe em `services/pricing.py:73`); volta se uma contagem de queries mostrar
> outra coisa. **G** — depende do registro persistido que a issue B deixa de
> fora.
>
> ✅ **Nenhuma issue depende de decisão humana.** O plano registra as **três
> decisões de projeto que ele mesmo toma**, cada uma com o custo de errar.
>
> ⚠️ **Resíduo:** o Step 3 abaixo (a coluna de estado em
> `docs/superpowers/issues/README.md`) ficou **dentro do plano novo, como Task
> 8 dele** — não foi aplicado ao README aqui.

- [ ] **Step 1: Reconferir cada issue contra a árvore de hoje**

As oito, com prioridade e dependência declaradas no próprio README:

```bash
cat docs/superpowers/issues/README.md
```

| # | Issue | Prio | Depende de |
|---|---|---|---|
| A | Cache de instância ORM | P1 | — |
| B | Falhas silenciosas → sinais acionáveis | P2 | parte de D |
| C | `create_app()` único | P3 | — |
| D | Fonte única do plano de contas (+ADR) | P4 | — |
| E | Precificação única | P5 | — |
| F | N+1 de config por request | P6 | A (padrão) |
| G | Onboarding / prontidão do tenant | P7 | B |
| H | Infra de testes + migrações | P8 | C |

⚠️ **As issues são de 08/06 — quase três meses.** Antes de planejar qualquer
uma, confirme que o defeito ainda existe.

🔬 **A issue D sai da lista: a Task 12 a entregou.** Confirme, não presuma —
abra `D-fonte-unica-plano-contas.md`, leia o que ela pede, e compare com o que a
Fase 8 entregou. Se sobrar recorte, ele entra no plano desta task **nomeando o
que a Fase 8 não cobriu**; se não sobrar, marque D como fechada pela Task 12,
com o commit. Sobram **sete** de qualquer modo — ou seis mais um recorte.

⚠️ A issue **B** depende de "parte de D" e a **G** depende de B: se D fechou,
confira se o pré-requisito de B foi junto antes de planejá-la.

- [ ] **Step 2: Escrever o plano das que sobreviverem à reconferência**

Crie `docs/superpowers/plans/2026-08-31-issues-de-arquitetura.md` cobrindo
**apenas** as issues cujo defeito você confirmou na árvore, começando por **A**
(o README já a recomenda: bug latente real, risco baixo, RED claro). Para cada
uma: o RED, a correção mínima, o gate.

Para as que **não** sobreviverem, ou que você decidir adiar, registre no mesmo
documento uma seção "Adiadas, e por quê" — com o motivo e o que precisaria
mudar para elas voltarem à fila. Uma issue adiada com motivo escrito é
gerenciável; uma issue esquecida não é.

- [ ] **Step 3: Atualizar o README das issues**

Em `docs/superpowers/issues/README.md`, acrescente à tabela uma coluna de
estado apontando para o plano novo ou para a seção de adiadas.

- [ ] **Step 4: Commit**

```bash
git add docs/superpowers/plans/2026-08-31-issues-de-arquitetura.md docs/superpowers/issues/README.md
git commit -m "docs(issues): as sete issues de arquitetura ganham plano ou adiamento por escrito"
```

---

### Task 10: O ritual de integração — repetido ao fim de CADA etapa

> **Mudou de forma em 02/09.** Antes era "a última task: merge ao fim de tudo".
> Agora é o **ritual repetido**: toda etapa que fecha passa por aqui antes de a
> seguinte começar. 🔬 O motivo era: **117 commits nunca empurrados**, e a Fase 6
> inteira só existia nesta máquina. ✅ **A primeira execução foi em 02/09**
> (Task 11): 125 commits empurrados, gate verde na branch e na `main` com os
> mesmos números.
>
> Esta task **não tem checkbox próprio** — ela é executada uma vez por etapa,
> pelas Tasks 11, 7, 8, 12, 13, 9, 14, 15 e 16.

**Files:**
- Modify: o plano da etapa que fechou (o carimbo de estado)

**Interfaces:**
- Consumes: uma etapa com o gate verde.
- Produces: `main` atualizada e empurrada.

**Step A: Gate, destacado do terminal**

```bash
setsid nohup bash run_tests.sh --gate > tests/reports/gate_$(date +%m%d_%H%M).log 2>&1 &
```

⚠️ **Nunca rode o gate preso ao terminal.** 🔬 Três gates morreram com a sessão
em 01/09, e o registro escrito a partir de um log truncado disse "18% com 2
FAILED" quando o log real dizia 62% e 7 FAILED — um placar parcial virou placar
e uma decisão foi tomada em cima dele.

Expected: **0 failed**, **skipped = 8**, **xfailed ≤ 72**, passed ≥ **3247** mais
os testes da etapa. (🔬 O `3193` que estava aqui era o piso de 01/09 — resíduo
achado pelo pré-voo da Task 13 em 03/09.)

**Step B: Suíte com browser, pelo runner retomável**

```bash
setsid nohup python3 scripts/suite_resumavel.py > tests/reports/runner_$(date +%H%M).log 2>&1 &
```

Morreu? Rode o **mesmo comando**: retoma de onde parou. Expected: **3435 passed
ou mais, 0 failed** (o P4 já corrigido ou registrado pela Task 11).

📖 O runner isola processo por arquivo de browser e por isso **esconde bugs de
ordem**. A rodada monolítica (`bash run_tests.sh --suite`) é a checagem de
ordem — rode-a nas etapas que mexem em fixture ou em conftest, não em todas.

**Step C: Carimbar o plano da etapa**

O plano de origem recebe, no cabeçalho, o veredito com **commit e números
reais** do gate. Veredito provado por **existência de arquivo na árvore e por
git, nunca por contagem de checkbox** — 📖 a regra do índice de 25/08, que
mostrou que somar checkbox fazia o repositório parecer ter ~2.900 itens abertos
quando o número real era três.

**Step D: Merge na `main`**

```bash
git checkout main
git merge --no-ff <branch-da-etapa>
setsid nohup bash run_tests.sh --gate > tests/reports/gate_pos_merge_$(date +%H%M).log 2>&1 &
```

Expected: gate verde **em `main`**, com os mesmos números do Step A.

⚠️ **Merge só com o Step A verde e o Step B verde.** Se qualquer um falhou, o
merge não acontece — a branch continua sendo o lugar do trabalho.

**Step E: Push — confirmando com o dono**

```bash
git log --oneline origin/main..main | wc -l   # quantos commits vão subir
git push origin main
```

⚠️ **Pergunte antes.** O plano autoriza a cadência, não o gesto. Diga quantos
commits sobem e o que eles contêm.

---

### Task 11: O que está a um passo, e a primeira integração

> **Executa ANTES da Task 7.** Três frentes estão a um ou dois passos do fim, e
> os commits saem da máquina aqui. Nada nesta task é trabalho novo — é
> fechar o que já está feito.

**Files:**
- Execute: `docs/superpowers/plans/2026-09-02-a-suite-browser-volta-a-valer.md`, **Task 7**
- Modify: `docs/superpowers/plans/2026-09-01-as-decisoes-viram-codigo.md` (Task 12, Steps 2 e 6)
- Modify: `docs/auditoria/achados-code-review-2026-08-25.md` (39 linhas já escritas, **não commitadas**)
- Modify: este plano (o carimbo da Task 6)

**Interfaces:**
- Consumes: nada.
- Produces: `main` com os commits empurrados (foram **125**); o piso do gate
  confirmado numa rodada única.

- [x] **Step 1: Conferir o que está solto na árvore**

Run: `git status --short`
Expected: exatamente `M docs/auditoria/achados-code-review-2026-08-25.md` e
`?? tests/reports/`. Qualquer outra coisa: pare e pergunte ao dono antes de
commitar — 📖 é a lição da Ruling P5 de 01/09, quando um `git add tests/` teria
varrido trabalho em curso de outra sessão para dentro de um commit alheio.

- [x] **Step 2: Commitar o achado P4** — `80c3bb31`.

🔬 As 39 linhas descrevem o único vermelho da suíte de 02/09: o teste
(`tests/test_rdo_unificado_playwright.py:275-277`) exige `#btn-equipe-<id>` numa
tarefa de **subempreitada**, e 📖 `templates/rdo/novo.html:1262-1267` só emite
esse botão no ramo `else` (tarefa interna). Decisão de produto — não conserte
aqui.

```bash
git add docs/auditoria/achados-code-review-2026-08-25.md
git commit -m "docs(achados): a suite browser rodou inteira e sobrou um achado — P4 do RDO unificado"
```

- [x] **Step 3: Executar a Task 7 do plano de 02/09** — gate **3247/8/201/72, 0 failed**; o plano de 02/09 fecha 7/7.

Use `superpowers:subagent-driven-development`. Ela é a última daquele plano:
gate consolidado e os três registros de fecho. `tests/reports/` fica **fora** do
commit (📖 `*.log` já é ignorado; o diretório inteiro é artefato de rodada).

- [x] **Step 4: Fechar a Task 12 do plano de 01/09**

Os Steps 2 e 6 dela ficaram abertos quando a sessão caiu. O Step 2 (suíte com
browser) foi **cumprido pelo plano de 02/09** — a suíte rodou inteira pela
primeira vez. Marque os dois `[x]` e substitua a nota de estado da task por:

```markdown
> **Estado em 02/09:** ✅ **FECHADA.** Step 1 (gate único) verde em 01/09:
> 3193 passed / 8 skipped / 201 deselected / 72 xfailed / 0 failed. Step 2
> (suíte com browser) cumprido pelo plano `2026-09-02-a-suite-browser-volta-a-valer.md`:
> 3435 passed / 1 failed / 8 skipped / 72 xfailed, o único vermelho sendo o
> achado P4, registrado na auditoria. As 2 FAILED que interromperam a rodada de
> 01/09 eram podridão de teste, não regressão — deriva de seletor e teste não
> idempotente, ambas diagnosticadas e corrigidas.
```

- [x] **Step 5: Carimbar a Task 6 deste plano como fechada** — conferido: cabeçalho e corpo batem, e o plano da Onda 6 também foi fechado (estava aberto).

Já está escrito no cabeçalho e no corpo da Task 6. Confira que os dois batem.

- [x] **Step 6: Commit dos registros**

```bash
git add docs/superpowers/plans/2026-09-01-as-decisoes-viram-codigo.md docs/superpowers/plans/2026-09-02-a-suite-browser-volta-a-valer.md docs/superpowers/plans/2026-08-31-fecho-do-que-esta-aberto.md
git commit -m "docs(fecho): a suite browser e as decisoes de 01/09 fecham; a onda 6 cai junto"
```

- [x] **Step 7: O ritual da Task 10 — e o primeiro push** ✅ **FEITO em 02/09.**

Execute os Steps A a E da Task 10. ⚠️ Este é o **primeiro push**: 🔬 117
commits, incluindo a Fase 6 inteira e as seis ondas do code review. Diga o
número ao dono antes de empurrar.

> **Como foi, com os números reais:**
> - **Step A** — gate na branch: **3247 passed, 8 skipped, 201 deselected, 72
>   xfailed, 0 failed** (47:43, `gate_browser_2154.log`).
> - **Step B** — suíte com browser pelo runner retomável: **3435 passed, 1
>   failed, 8 skipped, 72 xfailed**; o único vermelho é o achado P4, registrado.
>   🔬 Conferido que o ledger (18:07) é **posterior** ao último commit de código
>   (`160c7282`, 18:04) — o placar vale para a árvore que subiu, não para uma
>   anterior.
> - **Step C** — carimbos: este plano, `2026-09-02-a-suite-browser-volta-a-valer`
>   (7/7), `2026-09-01-as-decisoes-viram-codigo` (Task 12) e
>   `2026-08-25-onda-6-os-testes-prometidos` (6/6, estava aberto).
> - **Step D** — merge `--no-ff` (`83670e76`), 88 commits. Conferido antes que
>   `main` era ancestral da branch: merge trivial, sem conflito. Gate **na
>   `main`**: **3247 / 8 / 201 / 72, 0 failed** (44:55,
>   `gate_pos_merge_2249.log`) — os mesmos números do Step A.
> - **Step E** — o dono autorizou e o push saiu: **125 commits**, não 117 — a
>   rodada de 02/09 somou oito. `origin/main` = `main` = `31da1447`, confirmado
>   por `git fetch` e comparação de refs, não pela saída do `push`.

---

### Task 12: Fase 8 — o plano de contas canônico, as dez tasks

> 🔬 10 tasks, 3 de 21 arquivos existem. A D6 foi respondida em 01/09 e a fase
> **deixa de ser cortada em duas**: as dez entram juntas, e o parque nunca fica
> em dois estados.

**Files:**
- Execute: `docs/superpowers/plans/2026-08-24-fase-8-plano-de-contas-canonico.md` (10 tasks)
- Modify: o mesmo arquivo — a renumeração das migrations (Step 0) e o método da
  Task 4 (Step 1)

**Interfaces:**
- Consumes: nada deste plano.
- Produces: `classificar_assinatura(admin_id)` e a exceção
  `AssinaturaDesconhecida` em `contabilidade_utils.py`, mais o plano de contas
  canônico — que a **issue D** consome (ver Task 9, que por isso planeja
  **sete** issues, não oito).

- [ ] **Step 0: Renumerar as migrations da Fase 8, ANTES de tudo**

🔴 **Mesmo defeito da Task 8, e o pre-flight de 02/09 o achou aqui também.** 🔬 O
plano da Fase 8 escreve `_migration_315_plano_contas_semantica` (Task 2) e
`_migration_316_depara_contas_5x` (Task 4) — 📖 e **as duas já existem**:
`migrations.py:7381` (Onda 5, índice de vigência) e `:7415` (fix round do code
review, versão de contrato por tenant). O número aparece no **título da task**,
no **nome da função**, na **tupla do registry**, na **mensagem de commit** e num
**teste que importa a função pelo nome**.

Confira o máximo do dia — a Task 8 rodou antes e levou 319/320/321:

```bash
grep -n "_migration_3[0-9][0-9]_" migrations.py | tail -3
```

Renumere no plano da Fase 8, **de trás para frente** (a 316 antes da 315, senão
a 315→322 recém-criada seria renumerada de novo):

```bash
F=docs/superpowers/plans/2026-08-24-fase-8-plano-de-contas-canonico.md
sed -i 's/_migration_316_depara_contas_5x/_migration_323_depara_contas_5x/g; s/migration 316/migration 323/g; s/(316, "Fase 8/(323, "Fase 8/g' "$F"
sed -i 's/_migration_315_plano_contas_semantica/_migration_322_plano_contas_semantica/g; s/migration 315/migration 322/g; s/(315, "Fase 8/(322, "Fase 8/g' "$F"
grep -n "31[5-9]\|32[0-3]" "$F"
```

⚠️ Se o `grep` do primeiro comando mostrar um máximo diferente de 321, **use os
dois números seguintes ao máximo real** — a lista viva das Global Constraints
manda sobre este texto. E confira que a linha 214 do plano da Fase 8 ("a spec
inteira antes de escrever a migration 316") também foi renumerada: ela é prosa,
não código, e um `sed` que só olhasse `_migration_` a deixaria mentindo.

> ## 📥 O que a Onda 4 (Task 7) deixou explicitamente para esta task — 03/09
>
> 🔴 **Duas das três integrações contábeis não conseguem lançar hoje**, e o
> motivo é exatamente o que esta task existe para resolver: elas postam contra
> códigos de conta de **outro seeder**. 🔬 Medido em 03/09, num tenant semeado
> pelo plano canônico:
>
> | Integração | Conta que falta |
> |---|---|
> | `contabilizar_proposta_aprovada` (`MODULO_1`) | `4.1.02.002` |
> | `contabilizar_folha_pagamento` (`MODULO_6`) | `2.1.02.004`, `2.1.03.007`, `2.1.03.008` |
>
> A Onda 4 **não remapeou** — o plano dela proíbe consertar o mapa antes desta
> fase, porque seria consertá-lo contra um vocabulário que vai mudar. O que ela
> fez foi pôr **falha fechada e nomeada** no ponto único
> (`contabilidade_utils.criar_lancamento_automatico`): em vez de
> `ForeignKeyViolation` com dump de SQL, o usuário recebe o código da conta que
> falta, e nada é gravado.
>
> ⚠️ **Quando esta task canonizar o plano de contas, os alvos são estes quatro
> códigos** — e o teste `test_conta_ausente_e_recusada_com_nome_e_sem_rastro`
> (`tests/test_onda4_relatorio_funciona.py`) é o registro vivo da divergência:
> ele **passa a falhar** quando a Fase 8 fizer a conta existir, e nesse momento
> deve ser reescrito para outro código ausente, não apagado.
>
> 📖 Também fica para cá o **mapa de prefixos da DRE** (`contabilidade_utils.py`,
> a função `calcular_dre_mensal`): a Onda 4 o mediu invertido em relação a
> `criar_plano_contas_padrao` e deslocado um grupo em relação a
> `financeiro_seeds.py` — locação de equipamento reportando como CMV — e o
> deixou intacto pela mesma razão.

- [ ] **Step 0-b: Desarmar os SEIS sítios que mandam parar (pré-voo de 03/09)**

🔴 **A Task 12 não executa como está escrita, e o Step 0 acima não resolve isso.**
📖 `2026-08-24-fase-8-plano-de-contas-canonico.md:79` diz, em caixa: *"⚠️ **Não
execute a Task 4 sem o Cássio julgar a D6.**"* — e mais cinco sítios repetem que
a D6 está aberta ou que a Task 4 está bloqueada. A D6 **foi respondida em
01/09** (assinatura estrutural). Substitua os seis antes de despachar qualquer
task, senão o executor lê o cabeçalho destravado e para no meio. 🔬 É o mesmo
defeito que o pré-voo achou na Task 8 (Step 2b): destravar o cabeçalho e
esquecer o corpo.

🔴 **E o `sed` do Step 0 deixa 11 sobras** — 4 delas `[Migration 315]` /
`[Migration 316]` **dentro de `logger.info`/`logger.error`**, com `M` maiúsculo
que a regex não casa. Essas quatro viram **código de produção logando o número
errado**: log que mente é o defeito que esta casa persegue. Confira sítio a
sítio depois do `sed`, com `grep -n "31[5-9]\|32[0-3]"`, e trate `[Mm]igration`.

⚠️ **Os números 322/323 do Step 0 são hipótese, não medição.** 🔬 O máximo real
hoje é **318**; 319/320/321 só ficam gastos **se** a Task 8 rodar antes. Calcule
no dia, do máximo real, como as Global Constraints mandam.

🔴 **Dois dos cinco sinais da "assinatura estrutural" não discriminam** — e este
é o achado que mais muda a Task 4:
- **"grupo 6"** é compartilhado com o seeder **canônico** `_V2_CONTAS_SEED`: os
  tenants que só têm grupo 6 seriam rotulados de legado por engano.
- **`4.1.01.%` / `2.1.03.001`** idem.
- 🔴 E existe um **quarto plano** que o método não previu:
  `scripts/seed_demo_alfa.py:3501-3512`, com as **raízes invertidas**
  (3 = receita, 4 = despesa) — 📖 e ele roda no **auto-seed do boot**
  (`app.py:618`), não é código morto. Ele casa com **dois** sinais ao mesmo
  tempo.
- **Sinais limpos:** `5.1.01.%` e o `aceita_lancamento` de `5.1.01`. Outros três
  limpos ficaram de fora do plano e deviam entrar: `5.2.01`, `2.1.03.007-009` e
  `4.1.02.%`.

🔴 **O teste do Step 3 falha por dois motivos errados** (é a 10ª e a 11ª
ocorrência do padrão que o ledger já registra: teste que não chega ao código sob
teste): (1) ele usa uma fixture `app` que **não existe** — 🔬 zero `def app(` em
`tests/`, e o projeto não tem `pytest-flask`; (2) o `PlanoContas(...)` que ele
monta omite `natureza` e `nivel`, ambos `NOT NULL` (📖 `models.py:3276-3277`) →
`IntegrityError` antes da asserção. As demais citações do plano estão exatas.

🔴 **O guarda por `ast` da Task 3 reprova hoje por acusação falsa:** o scan
devolve **4** pares criadores e `_CRIADORES_CONHECIDOS` lista **2** — faltam
`scripts/seed_demo_alfa.py::_seed:464` e `::_upsert_conta:3480`, porque
`scripts/` não está na lista de ignorados.

⚠️ **O Step 1 troca o método e deixa 8 sítios do plano ainda dizendo
`(codigo, nome)`** (dict, docstring, a query `pares`, o `UPDATE`, o registry, a
mensagem de commit e a Interface) — instruções opostas no mesmo arquivo.
E 🔬 `_V2_CONTAS_SEED` tem **36** contas, não 35: falta `6.1.02.009` no
`SEED_CLASSIFICACAO`, e ela é alvo vivo de `MAPEAMENTO_CONTABIL['despesa_geral']`.

🔬 **"3 de 21 arquivos existem" não reproduz.** São **25** caminhos; dos **18 a
criar, zero existem**; dos a modificar, 7 de 7. O número honesto é: **nada da
Fase 8 foi executado**.

🔬 **Linhas que andaram** (ancore por nome): `PlanoContas` 3247→**3253**,
`seed_plano_contas_if_needed` 1597→**1605**, `contabilidade_views.py:95`→**93**,
`financeiro_views.py:1329`→**1320**. ✅ **Sem colisão com a Task 13:** os lotes
B6.4–B6.8 não tocam `contabilidade_views.py`.

**Veredito do pré-voo:** 7 das 10 tasks seguem válidas com correção pontual; a
**Task 3 precisa de correção obrigatória** (o guarda acusa falso); a **Task 4
precisa ser REESCRITA**, não só destravada (os sinais não discriminam); a Task 9
(Domínio) continua sem leiaute. ⚠️ **Não verificado:** a distribuição real no
banco — o Step 2 exige `from app import app`, que dispara `create_all()` e as
migrations (`app.py:554`, `:592`, `:720`) e **escreve no banco compartilhado**.
📖 Relatório completo em `.superpowers/.../preflight-t12.md` (gitignored).

- [ ] **Step 1: Trocar o método da Task 4, ANTES de executar**

O plano manda chavear o de-para por `codigo`. 🔬 Isso mandaria material para
pessoal em metade do parque, **em silêncio**. Substitua o método da Task 4 por
**assinatura estrutural** — a resposta D6 de 01/09, cuja evidência é:

| Sinal | Prova |
|---|---|
| existe grupo `6` | seeder `contabilidade_utils` (o `financeiro_seeds` não tem grupo 6) |
| existe `5.1.01.%` | seeder `financeiro_seeds` (o `contabilidade_utils` não tem filhos nível 4 sob `5.1.01`) |
| `2.1.03.001–003` × `2.1.03.007–009` | mutuamente exclusivos entre os dois |
| `4.1.01.%` × `4.1.02.%` | mutuamente exclusivos entre os dois |
| `aceita_lancamento` de `5.1.01` | **True** num, **False** no outro (lá é sintética) |

Nenhum deles lê `nome` — a proibição da spec é preservada. 🔬 E a premissa da
pergunta original estava errada: 📖 `contabilidade_utils.py:514` diz que o
sistema tem **QUATRO** planos concorrentes, não dois.

- [ ] **Step 2: Medir a distribuição no banco de dev antes de escrever a migration**

```bash
python3 -c "
from app import app
from models import db
with app.app_context():
    for sql, rot in [
      (\"SELECT count(DISTINCT admin_id) FROM plano_contas WHERE codigo LIKE '6%'\", 'tem grupo 6'),
      (\"SELECT count(DISTINCT admin_id) FROM plano_contas WHERE codigo LIKE '5.1.01.%'\", 'tem 5.1.01.%'),
      (\"SELECT count(DISTINCT admin_id) FROM plano_contas\", 'total com plano'),
    ]:
        print(rot, db.session.execute(db.text(sql)).scalar())
"
```

🔬 A medição de 01/09 deu: 6.941 tenants só com grupo 6, 95 com `5.1.01.%` (e
esses 95 têm **as duas** assinaturas — dois seeders rodaram no mesmo tenant), 86
com `5.2.01.001`, e **71 que não casam com nenhuma**. Se os seus números
divergirem muito disso, **pare e reconfira** antes de escrever a migration: o
banco de dev mudou desde a medição, e o de-para depende dela.

- [ ] **Step 3: Escrever a falha fechada no teste, antes da migration (RED)**

O ramo que importa é o do tenant **indeterminado**. Ele tem de **parar a
migration e nomear o tenant** — não escolher um default:

```python
import pytest
from models import db, PlanoContas
from tests.helpers_tenant import um_tenant


@pytest.mark.integration
def test_tenant_de_assinatura_desconhecida_para_a_migracao_e_nomeia_o_tenant(app):
    """Um plano de contas de terceira origem NAO pode ser migrado por chute.

    RED antes da migration: classificar_assinatura nao existe ainda.
    """
    from contabilidade_utils import AssinaturaDesconhecida, classificar_assinatura

    with app.app_context():
        # `um_tenant` devolve um Tenant com .admin_id (tests/helpers_tenant.py:148)
        admin_id = um_tenant('fase8-assinatura').admin_id
        # Terceira origem: nem grupo 6 (contabilidade_utils) nem 5.1.01.%
        # (financeiro_seeds) — as duas assinaturas conhecidas ficam de fora.
        db.session.add(PlanoContas(
            admin_id=admin_id, codigo='7.9.99', nome='Conta de origem desconhecida',
            tipo_conta='DESPESA', aceita_lancamento=True,
        ))
        db.session.commit()

        with pytest.raises(AssinaturaDesconhecida) as exc:
            classificar_assinatura(admin_id)
        assert str(admin_id) in str(exc.value), 'a excecao tem de NOMEAR o tenant'
```

⚠️ 📖 A PK de `plano_contas` é **`(admin_id, codigo)`** (`models.py:3271-3273`,
migration 218) e o campo do tipo chama-se **`tipo_conta`**, não `tipo`
(`:3275`). Confira os demais `NOT NULL` antes de colar
(`grep -n "class PlanoContas" -A 25 models.py`) — um campo faltando faz o teste
falhar por `IntegrityError`, e não pelo motivo certo.
`AssinaturaDesconhecida` e `classificar_assinatura` nascem na Task 4 da Fase 8;
o import dentro da função é o que produz o RED como `ImportError`.

⚠️ **Este teste é a guarda principal da task.** 🔬 Os 71 tenants indeterminados
de dev garantem que o ramo será exercitado — ele não é defensivo, é o caminho
de metade do trabalho.

- [ ] **Step 4: Rodar o teste e ver o RED**

Run: `python -m pytest tests/test_fase8_plano_contas_canonico.py -k assinatura_desconhecida -v`
Expected: FAIL — `NameError`/`ImportError` em `classificar_assinatura`.

- [ ] **Step 5: Executar as dez tasks pela sub-skill**

Use `superpowers:subagent-driven-development`, task a task.

⚠️ **A migration desta fase age sobre dados de TODOS os tenants.** Ela tem de
ser provada **idempotente por dupla execução** no banco de dev, como as 271–275
da Fase 6. E 📖 a lição N2: `create_all()` roda ANTES das migrações em todo
boot — o objeto que o modelo cria e o que a migration cria têm de convergir
(mesmo nome, mesmo tipo constraint-vs-índice), senão um `DROP` futuro estoura
`DependentObjectsStillExist`.

- [ ] **Step 6: Registrar a premissa e o que a ratifica**

No cabeçalho do plano da Fase 8:

```markdown
> ⚠️ **PREMISSA DECLARADA (decisão do dono, 02/09):** os conjuntos de códigos
> conhecidos cobrem o parque de produção. Não foi medido — não há acesso ao
> banco de produção. **O que a ratifica:** rodar `scripts/medir_producao.py`
> quando houver acesso. **O que acontece se a premissa for falsa:** a migration
> PARA e nomeia o tenant; nenhuma partida é migrada para conta errada. O custo
> é uma rodada manual por tenant de terceira origem, não dado corrompido.
```

- [ ] **Step 7: Gate, carimbo e ritual**

Execute os Steps A a E da Task 10.

```bash
git add docs/superpowers/plans/2026-08-24-fase-8-plano-de-contas-canonico.md
git commit -m "docs(fase-8): a fase fecha 10/10 com de-para por assinatura estrutural e falha nomeada"
```

---

### Task 13: A família 404 — B6.4 a B6.8

> 🔬 **70 `xfail(strict=True)`** esperando o refactor de ~60 sítios em 12
> arquivos. As tasks **já existem** — `docs/superpowers/plans/2026-08-06-rodada-b6-varredura.md`,
> seções **B6.4 a B6.8**. Nenhum plano novo.

**Files:**
- Execute: `docs/superpowers/plans/2026-08-06-rodada-b6-varredura.md`, seções B6.4–B6.8

**Interfaces:**
- Consumes: nada.
- Produces: o `xfailed` do gate **desce** de 72 para perto de 2.

- [ ] **Step 0: O pré-voo desta etapa (03/09) — e o corte em cinco lotes**

🔴 **O Step 1 abaixo mede errado.** `grep "xfail" | wc -l` devolve **44**, mas
isso conta prosa. 🔬 Os marcadores reais são **13 decoradores**, que produzem os
**70 testes** por parametrização: propostas 3→**40**, obras 2→**22**, frota
4→**4**, miscelânea 3→**3**, cauda 1→**1**.

🔴 **O Step 2 é inexequível como está escrito.** "Um commit por sítio, removendo
o `xfail` correspondente" **não existe**: o marcador é por *função de teste*, e
os 18 handlers de propostas pendem de **um único** decorador. Ou o commit é o
**lote inteiro**, ou os testes são re-parametrizados antes. Escolha e escreva
qual.

⚠️ **Armadilha silenciosa, e é a que mais custa:** 🔬 11 dos 13 arquivos não
importam `HTTPException` e **5 não importam `abort`** — `views/admin.py` é um
deles (`abort`: 0 ocorrências). Sem o import, o `abort(404)` novo vira
`NameError`, **engolido pelo próprio `except Exception` do handler**: o teste
continua `xfailed` e parece que "o fix não pegou". Todo lote começa conferindo
os imports.

🔬 **Tamanho real: 61 sítios** (32 de "404 escrito e engolido" + 29 de "404 não
escrito"), ~90 edições contando os ramos-guarda — o "~60" do plano sobreviveu a
28 dias. **Todos** os sítios estão vivos, e **todas** as linhas de 06/08
andaram (de 8 a 95 linhas): ancore por nome de função, nunca por número.

🔴 **O B6.8 encolheu:** seu item-manchete (`views/admin.py:441`, o único oráculo
de enumeração) já foi corrigido em `0c6590a4` (01/09) e tem teste verde. E a
premissa "`grep -c 'except HTTPException'` = 0" **caducou**: hoje
`views/obras.py:2238` e `views/admin.py:460` têm o ramo.

**O corte, e o porquê de cada peça** — 🔬 o achado que decide: *xfail e trabalho
não são proporcionais*. B6.4+B6.7 são **62 dos 70 xfail** em 29 sítios; os
outros três lotes são **32 sítios por 8 xfail** — e neles zero xfail cobre
`configuracoes_views.py` (5 sítios), `views/dashboard.py` (2) e
`obras.excluir_obra` (1).

**Ordem recomendada: B6.4 → B6.6 → B6.5 → B6.7 → B6.8**, um arquivo de teste por
commit, com `views/dashboard.py` **recortado do B6.5 para commit próprio** (0
xfail, e é o único ponto que mexe em 401/403 do login). O B6.6 sobe para segundo
— contra a ordem de 06/08 — para ensaiar a mecânica do `abort` novo num arquivo
parado desde 27/08 **antes** de aplicá-la a `views/obras.py`. A única
serialização dura do plano original (B6.5 antes de B6.7) fica preservada.

**Xfail esperado ao fim de cada etapa: 72 → 32 → 28 → 25 → 3 → 2.** ⚠️ O alvo
final é **2 xfailed exatos** (`test_p1_dedup_cross_origem.py` e
`test_arreio_presenca_rotas.py`, que não são desta task), não "perto de 2" — com
`strict=True`, sobrar ou faltar um é gate vermelho.

**Algum dos 70 já passaria hoje?** ⚠️ **Hipótese, não medição** (o pré-voo não
roda teste): **nenhum**. O `strict` já filtrou os falsos positivos no
nascimento — dois sítios entraram verdes por XPASS — e nenhum commit tocou os
alvos depois dos testes. Confirme na primeira rodada do lote.

📖 Relatório completo em `.superpowers/.../preflight-t13.md` (gitignored).

- [ ] **Step 1: Medir o tamanho real antes de começar**

```bash
grep -rn "xfail" tests/test_b6_404_*.py | wc -l
grep -rlc "except HTTPException" --include=*.py . | head
```

Expected: ~70 marcadores. 🔬 `grep -c 'except HTTPException'` deu **0** em todos
os arquivos do lote quando a Onda 6 mediu — o refactor nunca foi feito, e os
testes entraram com `xfail` de propósito, para que o dia em que ele rodar o
teste **falhe por passar**.

- [ ] **Step 2: Executar seção a seção, removendo os marcadores no mesmo commit**

Use `superpowers:subagent-driven-development`.

⚠️ 🔴 **Com `strict=True`, corrigir sem remover o marcador FALHA o gate por
XPASS.** Cada commit que conserta um sítio remove o `xfail` correspondente. Não
acumule remoções para o fim.

- [ ] **Step 3: Gate após cada seção**

Run: `bash run_tests.sh --gate`
Expected: **0 failed**, **skipped = 8**, e o **xfailed desce** pelo número de
marcadores removidos. Se o xfailed não desceu, ou nada foi corrigido, ou os
marcadores ficaram — as duas coisas são defeito.

- [ ] **Step 4: Carimbar o plano e integrar**

```bash
git add docs/superpowers/plans/2026-08-06-rodada-b6-varredura.md
git commit -m "docs(b6): as secoes B6.4-B6.8 fecham e os xfail da familia 404 saem"
```

Execute os Steps A a E da Task 10.

---

### Task 14: As automações — a reconferência vem antes do plano

> ~13 itens: **A01, A08, A17, A20, A21, A23** abertos; **A11, A13, A15, A16,
> A18, A22, A24** parciais; e **A25** (`N8N_WEBHOOK_URL` + cron), que segura
> toda notificação.
>
> ⚠️ **Não escreva plano a partir do documento de 23/08.** 🔬 Ele já envelheceu:
> A04, A18 e A24 mudaram de estado em 01/09 (`bef17c33`, `9f169c0d`,
> `9aead796`). Planejar sobre ele seria descrever um estado que não é o de hoje
> — o mesmo defeito que a varredura de 25/08 diagnosticou noutro lugar
> ("ENTREGUE por leitura de código" não é "ENTREGUE com teste que nomeia a
> regra").

**Files:**
- Create: `docs/reconferencia-backlog-2026-09-XX.md` (a data do dia)
- Create: `docs/superpowers/specs/2026-09-XX-automacoes-design.md`
- Modify: `docs/reconferencia-backlog-2026-08-23.md` (marcar como substituído)

**Interfaces:**
- Consumes: nada.
- Produces: 2–3 planos por família, que as etapas seguintes executam.

> ## ✅ A reconferência e a spec estão FEITAS (03/09)
>
> 📖 `docs/reconferencia-backlog-2026-09-02.md` (711 linhas) e
> `docs/superpowers/specs/2026-09-02-automacoes-design.md` (438 linhas). Os 11
> itens foram remedidos um a um contra a árvore, com a pergunta que a casa
> aprendeu a fazer depois da A09: **existe teste guardando?** — só **A16** tem
> (dois `xfail(strict=True)`).
>
> 🔴 **Cinco divergências entre o registro e a árvore. Duas destravam trabalho:**
> - **A15 e A23 NÃO estão mais travadas.** As decisões 4 e 7 foram respondidas
>   em **01/09** e ninguém levou a resposta de volta ao backlog. Pior: o corte
>   do A23 dizia *"não existe canal"* — 🔬 e `utils/webhook_dispatcher.py`
>   **existe desde 22/07** (`0ea9402d`), com allowlist, retry e teste.
> - 🔴 **A21 — a mensagem de commit afirma o que o commit não fez.** `ce331094`
>   diz ter consertado "kwargs de colunas inexistentes"; consertou os do
>   construtor de `RDO`. 🔬 Os três de `crud_rdo_completo.py:427,428,448`
>   continuam vivos, e provei por execução que as colunas não existem:
>   `RDOEquipamento.horas_utilizacao`, `RDOEquipamento.observacoes` e
>   `RDOOcorrencia.descricao_completa` — as três **NÃO EXISTEM**. 📖 Log que
>   afirma fechado o que está aberto é o defeito que esta casa persegue.
> - **A16 encolheu:** `ed17ab7f` (27/08) fechou o sítio do totem sem citar o
>   item.
> - **A13 tem três escritores de venda em `valor_orcado`, não dois** — o
>   terceiro (`models.py:8424`) é um listener `after_insert` que dispara sozinho
>   a cada aprovação.
>
> **A spec decide:** 3 planos (RDO×ponto → Portal×medição → cauda barata), 8
> tasks. **Fora, com destino escrito:** A08 (regra de rateio), A13-origem
> (backfill + decisão), A20 (reabrir o corte com o dono), A21a (segue cortado).
> **Escalado como decisão, não como task:** `obra.progresso_conclusao` — a barra
> some em silêncio em 5 templates e há **dois números candidatos com semânticas
> diferentes**; a pergunta está escrita em §5.1 da spec.
>
> ⚠️ **Um número não foi remedido:** os 3,2% do A13 são o valor de 23/08 —
> remedir exige o banco compartilhado, proibido enquanto os agentes rodavam em
> paralelo.
>
> ✅ O banner de substituição no topo do documento de 23/08 (Step 2 desta task)
> foi escrito em 03/09.

- [ ] **Step 1: Reconferir item a item, contra a árvore de hoje**

Para cada um dos ~13, três perguntas — e a resposta de cada uma **medida**, não
lembrada:

1. O defeito/lacuna ainda existe? (📖 `arquivo:linha`)
2. Existe teste que o nomeia? (`grep -rln "<símbolo>" tests/`)
3. O que mudou desde 23/08? (`git log --oneline --since=2026-08-23 -- <arquivo>`)

⚠️ **"ENTREGUE por leitura de código" não conta.** 🔬 O A09 foi dado como
entregue assim em 23/08, e a varredura de 25/08 achou um furo de tenant no
mesmo dedup (`almoxarifado_utils.py:257`). Item sem teste que o nomeie volta
como **PARCIAL**, não ENTREGUE.

- [ ] **Step 2: Escrever a reconferência**

`docs/reconferencia-backlog-2026-09-XX.md`, no formato do de 23/08: uma seção
por item, com veredito anterior → veredito de hoje, a evidência, e o recorte do
que sobra. No topo do de 23/08, o banner de substituição.

- [ ] **Step 3: Agrupar em famílias e escrever a spec**

`docs/superpowers/specs/2026-09-XX-automacoes-design.md`, agrupando o que
sobreviveu por **família**, não por número:

| Família | Itens candidatos |
|---|---|
| RDO × ponto | A11 (guarda cruzada no ramo horista), A16 (evento no sync alocação→ponto), A17 (pré-carregar mão de obra) |
| Portal × medição | A15 (`MedicaoObra` paralela sem itens nem recálculo), A23 (aviso de comprovante) |
| Compras | A20 (pré-preencher pedido com o vencedor), A21 (FK de frota + TypeError de kwargs), A22b (persistir CPF/CNPJ) |
| Notificações e operação | A25 (`N8N_WEBHOOK_URL` + cron — 📖 o runbook já existe em `docs/operacao-agendamentos.md`) |
| Resíduos de origem | A13 (a origem, decisão adiada), A18 (unificação da vigência em diante), A08, A01 |

⚠️ **Um plano por família, não um de 13 tasks.** Cada família tem superfície,
risco e teste diferentes; um plano único obrigaria o executor a trocar de
domínio a cada task.

- [ ] **Step 4: Escrever os planos e executá-los**

Use `superpowers:writing-plans` para cada família, depois
`superpowers:subagent-driven-development` para executar.

- [ ] **Step 5: Commit e ritual**

```bash
git add docs/reconferencia-backlog-2026-09-XX.md docs/reconferencia-backlog-2026-08-23.md docs/superpowers/specs/2026-09-XX-automacoes-design.md
git commit -m "docs(automacoes): a reconferencia mede o estado de hoje e agrupa em familias"
```

Execute os Steps A a E da Task 10 ao fim de cada família.

---

### Task 15: Fase 9a/9b — as premissas antes do código

> 🔬 19 de 35 arquivos prometidos existem, e o que existe veio por **outros
> caminhos** (portal do cliente, medição, ciência do RDO). Faltam
> `services/assinatura_documento.py`, `services/contrato_service.py`,
> `services/drive_client.py`, `scripts/portal_acessos.py`.
>
> ⚠️ O plano foi escrito sobre o schema de **antes das Fases 1–5**, tem seção
> própria de *"Premissas a reconfirmar antes de executar"*, e uma de suas
> decisões **já caiu**: o dono do `valor_contrato` é a Fase 6, o que reduz a 9b
> a camada documental.

**Files:**
- Create: `docs/superpowers/specs/2026-09-XX-fase-9-premissas.md`
- Modify: `docs/superpowers/plans/2026-07-21-fase-9-portal-assinatura-contratos.md` (o veredito no cabeçalho)

**Interfaces:**
- Consumes: nada.
- Produces: ou um plano novo, ou um veredito de morte por escrito. **Os dois
  levam a lista a zero.**

> ## ✅ A reconferência está FEITA (03/09) — falta a decisão
>
> 📖 `docs/superpowers/specs/2026-09-02-fase-9-premissas.md` (607 linhas). O
> plano-alvo **existe**: `2026-07-21-fase-9-portal-assinatura-contratos.md`, e
> este é o **terceiro** veredito de premissas dele — já havia dois apensados
> (`941e6738` em 23/07, `a723babe` em 03/08).
>
> 🔴 **O achado que domina, e já foi corrigido na fonte:** o cabeçalho dizia
> **"nunca começada"** e era falso. 🔬 Três migrations levam o nome da fase no
> registro permanente (`migrations.py:7845-7847`: as tuplas 267, 268 e 269, todas
> "Fase 9a — …") e dois commits executaram sob o rótulo (`851fd70b`,
> `1fbc97c0`). A fase estava **parcialmente consumida e era dita virgem**. 📖 É a
> **terceira** ocorrência desse apodrecimento — o ledger já registrou o mesmo
> para as Ondas 1 e 2. O cabeçalho do plano de 21/07 foi corrigido em 03/09.
>
> **Placar das premissas numeradas (P1–P10):** 3 valem, 0 caíram, 2 mudaram, 5
> **não verificáveis aqui** (console Google, env de produção, e duas perguntas
> ao dono abertas há 43 dias). ⚠️ Mas elas **não decidem a fase** — são externas
> por construção. Quem decide são as premissas não numeradas: **5 valem** (os
> cinco furos de segurança da 9a, todos vivos e medidos: token em claro
> `models.py:397`, zero escopo, CSRF exempt `main.py:220-226`, `_PATHS_SENSIVEIS`
> inalterado `utils/auditoria_acesso.py:29`, zero `Referrer-Policy` no repo),
> **3 caíram** e **3 mudaram**.
>
> **Recomendação da reconferência — a escolha é do dono:** **reescrever, partida
> em duas.** A **9a** mantém o tamanho (11 de 14 tasks pendentes, sem
> substituto) mas fica mais barata, porque `ObraSignatarioCliente` +
> `portal_signatario_auth` já são precedente em produção. A **9b encolhe ~60%**:
> as Tasks 15, 16 e 18 somem (a Fase 6 as entregou), sobra a 17 (executável
> hoje) e as 19 e 20 (bloqueadas pelas premissas não verificáveis).
> 🔴 **Não enterrar:** os cinco furos de segurança seguem vivos, e riscar o plano
> não fecha nenhum deles.

- [ ] **Step 1: Abrir o plano pela seção de premissas, não pelo começo**

```bash
grep -n "Premissas a reconfirmar" -A 60 docs/superpowers/plans/2026-07-21-fase-9-portal-assinatura-contratos.md
```

- [ ] **Step 2: Medir cada premissa contra a árvore de hoje**

Para cada uma: 📖 o `arquivo:linha` que a confirma **hoje**, ou a prova de que
ela caiu. A decisão nº 2 já se sabe caída (o `valor_contrato` é da Fase 6) —
trate-a como o exemplo do formato, não como a única.

- [ ] **Step 3: Escrever o veredito**

`docs/superpowers/specs/2026-09-XX-fase-9-premissas.md`, com uma das duas
conclusões, **explicitamente**:

- **(a) As premissas sobrevivem** (ou sobrevivem em recorte menor): escreva o
  que resta e siga para o Step 4.
- **(b) Não sobrevivem:** risque a fase, no formato dos oito planos obsoletos
  do índice de 25/08 — **por que não executar**, e o que precisaria mudar para
  ela voltar. 🔴 Isto é resultado **válido e final**, não fracasso: construir
  sobre um schema que não existe mais não leva a lista a zero, leva a
  retrabalho.

No cabeçalho do plano de 21/07, o carimbo correspondente.

- [ ] **Step 4: Se (a) — escrever o plano novo e executá-lo**

Use `superpowers:writing-plans` sobre a spec do Step 3. O plano de 21/07 vira
**histórico**; não o execute ao pé da letra.

- [ ] **Step 5: Commit e ritual**

```bash
git add docs/superpowers/specs/2026-09-XX-fase-9-premissas.md docs/superpowers/plans/2026-07-21-fase-9-portal-assinatura-contratos.md
git commit -m "docs(fase-9): as premissas medidas contra a arvore de hoje, e o veredito"
```

Execute os Steps A a E da Task 10.

---

### Task 16: O índice volta a valer, o gate final, o push

> A última de verdade. Aqui a lista chega a zero — ou o que sobrar está
> nomeado, com motivo escrito e o que precisaria mudar.

**Files:**
- Create: `docs/planos-em-aberto-2026-09-XX.md`
- Modify: `docs/planos-em-aberto-2026-08-25.md` (banner de substituição)

**Interfaces:**
- Consumes: o estado final de todas as tasks.
- Produces: o índice de estado que passa a valer.

- [ ] **Step 1: Gate consolidado e suíte, os dois destacados**

```bash
setsid nohup bash run_tests.sh --gate > tests/reports/gate_final_$(date +%m%d).log 2>&1 &
setsid nohup python3 scripts/suite_resumavel.py > tests/reports/runner_final_$(date +%H%M).log 2>&1 &
```

Expected: **0 failed** nos dois. **skipped = 8** (nunca 9). **xfailed próximo de
2** — os 70 da família 404 saíram na Task 13.

⚠️ Rode também a monolítica uma vez: `bash run_tests.sh --suite`. 📖 O runner
isola processo e por isso esconde bugs de ordem; as duas dizem coisas
diferentes de propósito.

- [ ] **Step 2: Escrever o índice novo**

`docs/planos-em-aberto-2026-09-XX.md`, no formato do de 25/08 (que ele
substitui), com o veredito de cada plano **provado por existência de arquivo na
árvore e por git, nunca por contagem de checkbox**.

Tem de registrar, no mínimo:
- cada plano fechado por esta rodada, com **commit e números de gate**;
- o que sobrou aberto e **por quê** — com o que precisaria mudar para fechar;
- as três `RATIFICAR` pendentes (conta `6.1.02.009` com o contador, congelar as
  históricas do A18, a flag do rateio A24) e a premissa declarada da Fase 8;
- o **P4** do RDO unificado, se ainda não tiver decisão de produto;
- as 18 rotas de `views/vehicles.py` que a Task 9 de 01/09 removeu (`12703381`),
  para o índice não repetir a pendência antiga;
- o capítulo 23a do manual do RDO, esperando Alan e Abel.

No topo do de 25/08:

```markdown
> ⛔ **SUBSTITUÍDO por `docs/planos-em-aberto-2026-09-XX.md`.** Escrito contra
> `main` em `657326c4`, não conhece a Onda 5, "A Porta Irmã", "O Que Não
> Persiste", as decisões de 01/09 nem a rodada de fecho. Vale como registro
> histórico.
```

- [ ] **Step 3: Commit**

```bash
git add docs/planos-em-aberto-2026-09-XX.md docs/planos-em-aberto-2026-08-25.md
git commit -m "docs(indice): a lista chega a zero, e o que sobra esta nomeado com motivo"
```

- [ ] **Step 4: O ritual final**

Execute os Steps A a E da Task 10. Este é o push que fecha a rodada.

---

## Notas de execução

**Ordem obrigatória (atualizada em 02/09):**

**T11 → T7 → T8 → T12 → T13 → T9 → T14 → T15 → T16**, com a **Task 10** (o
ritual de integração) executada ao fim de cada uma.

🔴 **A ordem não é a dos números.** As Tasks 1–6 já fecharam; a T11 é nova e vem
primeiro porque tira os commits da máquina antes de qualquer trabalho novo (foram
125, empurrados em 02/09).

**O critério da ordem é dinheiro errado primeiro.** A Onda 4 (T7) é a única
frente que está errando **hoje**, com dado real em produção: DRE e balancete que
não fecham entre si, e quatro relatórios que nunca funcionaram. Tudo o mais é
dívida que espera bem.

**As dependências duras que sobraram são duas:**
- **T7 → Task 4** (Onda 2): satisfeita, `fed8f19b` (26/08).
- **T9 → T12**: a issue **D** (fonte única do plano de contas) é absorvida pela
  Fase 8. Por isso a Task 9 planeja **sete** issues, não oito — e por isso vem
  depois da T12.

**Nada roda em paralelo.** 📖 A skill proíbe paralelizar implementadores, e a
razão é conflito de índice do git — 🔬 arriscado em 31/08 com duas tasks de
arquivos disjuntos, e a nota do ledger registra que o risco era real mesmo não
tendo se materializado.

**A Task 8 (Espinha) é a maior desta rodada** — porte de 2.542 linhas, agora
10/10 com a VIGA-I respondida.

**O que este plano NÃO fecha, e por quê** (revisto em 02/09 — quatro linhas da
tabela original saíram porque deixaram de valer):

| Item | Motivo |
|---|---|
| **O P4 do RDO unificado** | 🔬 `tests/test_rdo_unificado_playwright.py:275-277` exige `#btn-equipe-<id>` numa tarefa de subempreitada; 📖 `templates/rdo/novo.html:1262-1267` só o emite no ramo interno. **Decisão de produto** — não há evidência no repositório que decida a intenção. Fecha em uma linha, dos dois lados. A Task 11 o registra; a Task 16 o lista se ainda estiver aberto |
| **As três `RATIFICAR` de 01/09** | Nome e grupo da conta `6.1.02.009` (pergunta do contador), congelar as históricas do A18, e ligar a flag do rateio A24. Nenhuma bloqueia uma etapa — o código está escrito e atrás de interruptor |
| **A medição de produção da Fase 8** | Sem acesso ao banco. Vira **premissa declarada com falha fechada** (Task 12, Step 6), e a medição fica como ratificação posterior |
| **O capítulo 23a do manual do RDO** | 📖 Espera Alan e Abel lerem antes de virar cobrança. Nenhuma linha de código destrava |
| `templates/medicao/gestao_itens.html:510` | O form aponta para a rota que a onda "A Porta Irmã" fechou com `@admin_required`. Se GESTOR alcança a página, o botão virou beco. Decisão de produto |

🔬 **Saíram da tabela, e por quê:** a **Fase 8** entrou (Task 12, D6
respondida); a **Task 8 da Espinha** entrou (VIGA-I respondida); as **18 rotas
de `views/vehicles.py`** foram removidas em 01/09 (`12703381`); e o **`git
push`** deixou de estar fora de escopo — passou a ser o Step E do ritual, uma
vez por etapa, sempre confirmado com o dono.

**A regra que esta rodada herda, e que vale mais que qualquer task:** 🔬 na onda
"A Porta Irmã", **três** dos testes propostos pelo plano teriam passado verdes
sem nunca alcançar o código sob teste — e teriam sido commitados como prova de
correção. Aquela onda nasceu porque testes anteriores provavam por
`inspect.getsource()`; proibir a técnica não bastou, porque o vício reapareceu
noutra forma. **Antes de aceitar qualquer verde nesta rodada, pergunte se o
teste chegaria ao código sob teste caso o defeito não existisse.** Se a
resposta for sim, o teste é andaime.
