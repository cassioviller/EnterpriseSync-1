# A lista vai a zero — design do fecho

> **O que é:** o desenho do sequenciamento que leva a **zero** a lista de
> trabalho aberto do repositório. Não é plano de implementação e não contém
> tasks de código: ele decide a ordem, o critério de pronto, e quais planos
> ainda precisam ser escritos. As tasks continuam morando nos planos de origem.
>
> **O que ele produz:** a extensão de
> `docs/superpowers/plans/2026-08-31-fecho-do-que-esta-aberto.md` de 10 para 15
> tasks, mais três planos que ainda não existem.
>
> **Medido contra:** `sdd/a-porta-irma` em `160c7282`, 02/09.
>
> Marcas: 🔬 medido · 📖 lido no código (`arquivo:linha`) · 🧮 deduzido.

## As quatro decisões que definem este desenho

Tomadas pelo dono do repositório em 02/09, e cada uma exclui alternativas que
mudariam tudo o que vem depois:

| # | Decisão | O que ela exclui |
|---|---|---|
| 1 | **Estender o sequenciador de 31/08**, não escrever um novo | Um plano-mestre paralelo, que seria a segunda fonte de verdade que a casa proíbe |
| 2 | **Zero é a lista inteira** — inclusive funcionalidade nova (Fase 9a/9b e as automações) | O recorte "só dívida e defeito", que deixaria ~13 automações e a 9a/9b num backlog sem dono |
| 3 | **Executar sob premissa declarada com falha fechada**, onde o bloqueio é humano | Parar a Fase 8 na Task 3 esperando acesso a produção que pode não depender do dono |
| 4 | **Integrar agora e a cada etapa fechada** | O merge único no fim, que adiaria por semanas o backup de 117 commits que só existem numa máquina |

E a ordem: **dinheiro errado primeiro**. A Onda 4 é a única frente errando hoje
com dado real em produção.

## O estado de partida

🔬 `sdd/a-porta-irma` está **82 commits à frente da `main`**, e a `main` **35 à
frente do `origin`** — **117 commits nunca empurrados**, incluindo a Fase 6
inteira e as seis ondas do code review de 25/08.

🔬 Piso do gate, medido em 01/09 (`tests/reports/gate_decisoes_1901.log`):
**3193 passed · 8 skipped · 201 deselected · 72 xfailed · 0 failed** (42:24).

🔬 Piso da suíte com browser, medido em 02/09 pelo runner retomável
(`scripts/suite_resumavel.py`, 30 chunks): **3435 passed · 1 failed · 8 skipped
· 72 xfailed**. O único vermelho é o achado P4, registrado no fim de
`docs/auditoria/achados-code-review-2026-08-25.md`.

📖 A última migration é a **318** (`migrations.py:7540`, registro em `:7884`).

## A arquitetura do fecho

O trabalho aberto não é uma fila — é um grafo, e as dependências duras que
sobraram são poucas, porque as decisões de 01/09 derrubaram as demais:

- **Onda 4 → Onda 2**: satisfeita. A Onda 2 fechou em `fed8f19b` (26/08).
- **Espinha Task 8 → VIGA-I**: satisfeita. Decidido em 01/09, opção B; a C foi
  declarada morta.
- **Fase 8 Task 4+ → medição de produção**: **não** satisfeita, e é a única que
  sobra. A decisão 3 a converte de bloqueio em premissa declarada.
- **Issue D → Fase 8**: a issue D (fonte única do plano de contas) é absorvida
  pela Fase 8. Sobram **sete** das oito issues.

Tudo o mais é escolha, e a escolha é a ordem das etapas abaixo.

## As oito etapas

### Etapa 0 — o que está a um passo, e a primeira integração

Fecha o que já está praticamente pronto e tira os 117 commits desta máquina.

- Task 7 do plano de 02/09 (gate consolidado + os três registros de fecho).
- Task 12, Steps 2 e 6, do plano de 01/09 — a suíte browser, absorvida pelo
  plano de 02/09.
- Task 6 do sequenciador marcada como **fechada**: 🔬 o plano de 02/09 derrubou
  a última task da Onda 6 (a jornada E2E, que rodou pela primeira vez).
- O achado P4 commitado (hoje são 39 linhas não commitadas em
  `docs/auditoria/achados-code-review-2026-08-25.md`).
- **Gate verde → merge na `main` → push.**

### Etapa 1 — Onda 4, o relatório passa a funcionar

🔬 Restam as Tasks **1, 2, 3, 6 e 7**. As Tasks 4 e 5 foram absorvidas pelo
sequenciador em 31/08 (`3d0873a4`/`41b605d0` e `0b3f932c`/`0d1a7c6d`), depois
das decisões D4 e D3 — apagar, nos dois casos.

Duas naturezas: a contabilidade que erra de **aritmética** (DRE e balancete que
não fecham entre si) e os relatórios que erram de **existência** (`km_rodado`
onde a coluna é `km_percorrido`, `AlocacaoVeiculo` que não existe no repo) — e
sobreviveram porque nenhum teste os chamava.

### Etapa 2 — Resgate da Espinha Financeira

10 tasks; porte de **2.542 linhas** já escritas e testadas na branch
`design/espinha-financeira-obra` (PR #6).

🔴 **Correção obrigatória antes da primeira task:** o plano escreve as
migrations **317, 318 e 319** nos títulos das Tasks 3, 4 e 8, nos corpos das
funções e nas mensagens de commit. 🔬 **A 317 e a 318 já foram gastas em 01/09**
— `_migration_317_chave_acesso_por_tenant` (`migrations.py:7505`) e
`_migration_318_flag_folha_rateio_encargos` (`:7540`). 📖 O próprio plano avisa
(`:46`) para conferir o máximo do repo no dia do commit e "nunca reservar
faixa", mas os números literais estão espalhados pelo texto. Renumerar para
**319, 320 e 321** é o primeiro passo da etapa.

🔴 Segundo achado já registrado no plano: os dois leitores de RDO da branch não
filtram estado — portados como estão, reabrem por baixo o defeito que a `main`
fechou por cima em 24/08.

### Etapa 3 — Fase 8, o plano de contas canônico

10 tasks, 🔬 3 de 21 arquivos existem. As Tasks 1–3 são executáveis hoje.

Da Task 4 em diante, o de-para é chaveado por **assinatura estrutural** — a
resposta D6 de 01/09, que corrigiu a premissa da pergunta: 📖
`contabilidade_utils.py:514` já dizia que "o sistema tem QUATRO planos de contas
concorrentes", e o enunciado original supunha dois. Discriminadores que nunca
leem `nome`: existência do grupo `6`, existência de `5.1.01.%`, os pares
mutuamente exclusivos `2.1.03.001–003` × `2.1.03.007–009`, e `aceita_lancamento`
de `5.1.01`.

**A premissa declarada (decisão 3):** os conjuntos conhecidos cobrem o parque.
**A falha fechada:** qualquer tenant cuja assinatura não seja uma das conhecidas
faz a migration parar e **nomear o tenant**. 🔬 Os 71 indeterminados do banco de
dev são a prova de que esse ramo será exercitado, não decoração. A medição de
produção deixa de ser pré-requisito e vira **ratificação posterior**.

### Etapa 4 — a família 404 (B6.4–B6.8)

Refactor de ~60 sítios em 12 arquivos, removendo os **70 `xfail(strict=True)`** à
medida que fecha. As tasks **já existem** em
`2026-08-06-rodada-b6-varredura.md`, seções B6.4–B6.8 — nenhum plano novo.

Entra aqui, e não antes, porque é o maior volume de diff e o menor risco de
dado. 📖 O padrão é `except HTTPException: raise` antes do catch-all.

### Etapa 5 — as sete issues de arquitetura

`docs/superpowers/issues/`, A–H menos a D (absorvida pela Fase 8). A, C, E e F
são independentes entre si; B é parte de D e G depende de B; H depende de C.
Nunca viraram plano nem issue no GitHub. É a Task 9 que o sequenciador já
previa — **plano novo a escrever**.

### Etapa 6 — as automações

~13 itens entre abertos e parciais: **A01, A08, A17, A20, A21, A23** abertos;
**A11, A13, A15, A16, A18, A22, A24** parciais; mais **A25** (`N8N_WEBHOOK_URL`
+ cron), que segura toda notificação.

⚠️ **A reconferência vem antes do plano.** 🔬 A última é de 23/08 e já
envelheceu: A04, A18 e A24 mudaram de estado em 01/09 (`bef17c33`, `9f169c0d`,
`9aead796`). Planejar sobre ela seria descrever um estado que não é o de hoje —
o mesmo defeito que a varredura de 25/08 diagnosticou em outro lugar
("ENTREGUE por leitura de código" não é "ENTREGUE com teste que nomeia a
regra").

Da reconferência saem **2–3 planos por família** (RDO×ponto, portal×medição,
compras, notificações), não um plano único de 13 tasks — cada família tem
superfície e risco diferentes.

### Etapa 7 — Fase 9a/9b

🔬 19 de 35 arquivos prometidos existem, e o que existe veio por outros
caminhos. Faltam `services/assinatura_documento.py`,
`services/contrato_service.py`, `services/drive_client.py`,
`scripts/portal_acessos.py`.

⚠️ **Reconferência de premissas antes de qualquer código.** O plano foi escrito
sobre o schema de **antes das Fases 1–5**, tem seção própria de "Premissas a
reconfirmar", e uma de suas decisões **já caiu**: o dono do `valor_contrato` é a
Fase 6, o que reduz a 9b a camada documental.

**Resultado válido da reconferência inclui riscar a fase**, com veredito escrito,
como as oito obsoletas do índice de 25/08. Construir sobre um schema que não
existe mais não leva a lista a zero — leva a retrabalho.

## Como o sequenciador cresce

Por **acréscimo, não renumeração**: 📖 o ledger em
`.superpowers/sdd/2026-08-31-fecho-do-que-esta-aberto/progress.md` referencia
T1–T10, e renumerar quebraria o rastro.

| Task | Estado / conteúdo |
|---|---|
| T1–T5 | ✅ fechadas |
| T6 | ✅ passa a fechada — o plano de 02/09 derrubou a última task da Onda 6 |
| T7 | Onda 4 (Etapa 1) |
| T8 | Espinha (Etapa 2) — ganha o step de renumeração das migrations |
| T9 | issues de arquitetura (Etapa 5) |
| T10 | **muda de forma:** deixa de ser o merge único do fim e vira o **ritual repetido** entre etapas |
| **T11** | o fecho do que está a um passo + primeiro merge + push (Etapa 0) — **executa antes da T7** |
| **T12** | Fase 8, o plano de contas canônico (Etapa 3) |
| **T13** | família 404 (Etapa 4) |
| **T14** | reconferência das automações → spec → planos (Etapa 6) |
| **T15** | reconferência de premissas da Fase 9a/9b → plano novo (Etapa 7) |
| **T16** | o índice volta a valer, gate consolidado final, push |

A ordem de execução — **T11 → T7 → T8 → T12 → T13 → T9 → T14 → T15 → T16** —
fica declarada no cabeçalho do plano, porque não é a ordem dos números.

## Definição de pronto — idêntica em toda etapa

1. **Gate verde:** `bash run_tests.sh --gate`, sempre destacado do terminal
   (`setsid nohup` — 🔬 três gates morreram com a sessão em 01/09), contra o
   piso **3193 passed · 8 skipped · 201 deselected · 72 xfailed · 0 failed**.
2. **O skipped nunca sobe; o xfailed só desce.** 🔬 Lição de 28/08: quatro
   testes saíram do gate em silêncio. Consertar código guardado por `xfail`
   **exige remover o marcador no mesmo commit** — com `strict`, o conserto sem
   remoção falha o gate por XPASS.
3. **Suíte browser** pelo runner retomável, piso **3435 passed · 0 failed**.
4. **O plano de origem estampado** no cabeçalho com veredito e commit.
5. **Merge na `main` e push.** Só então a etapa seguinte começa.

## Modelo de execução

SDD (`superpowers:subagent-driven-development`): um implementador por vez,
ledger próprio por plano em `.superpowers/sdd/<slug>/progress.md`, varredura de
pré-voo antes da primeira task, revisão por task com cap de 5 rodadas de fix.

**Branch a partir da `main`, não worktree** — 📖 precedente de 21/08, quando
worktrees quebraram sensores; a prática da casa é branch → gate → merge.

**TDD sem exceção**, com o RED conferido e citado no commit. **Nenhum teste
prova por `inspect.getsource()`** — prova por comportamento, no banco ou na
resposta HTTP. E um teste de guarda tem de reprovar **também quando o próprio
gatilho para de funcionar** (regra da onda "A Porta Irmã", nascida de um teste
que passava verde sobre defeito).

## Os cinco riscos

| # | Risco | Mitigação |
|---|---|---|
| 1 | **Colisão de migration.** 🔬 A última é a 318; o plano da Espinha ainda escreve 317/318/319 | O sequenciador carrega a numeração viva; cada etapa confere o máximo do repo no momento de escrever. Precedente: a Fase 6 queimou a 270 e renumerou 271→277 |
| 2 | **Premissa envelhecida.** Planos de 25/08 executando contra a árvore de setembro | Varredura de pré-voo abrindo cada etapa. Foi ela que achou o risco 1 |
| 3 | **Piso que mente.** Teste sai do gate em silêncio e o número sobe do mesmo jeito | skipped e xfailed são **pisos**, não números informativos |
| 4 | **As automações viram poço sem fundo** | A reconferência dimensiona **antes** de o plano existir; famílias separadas, não um plano único |
| 5 | **A Fase 9a/9b não sobrevive à reconferência** | É resultado válido: riscar com veredito escrito também leva a lista a zero |

## O que este design NÃO decide

- **O P4 do RDO unificado** (🔬 `tests/test_rdo_unificado_playwright.py:275-277`
  × 📖 `templates/rdo/novo.html:1262-1267`): se o botão de equipe interna deve
  aparecer em tarefa de subempreitada é decisão de produto, e não há evidência
  no repositório que decida a intenção. Fecha em uma linha, dos dois lados.
- **As três RATIFICAR** de 01/09: nome e grupo da conta `6.1.02.009` (pergunta
  do contador), congelar as históricas do A18, e ligar a flag do rateio A24.
- **O capítulo 23a do manual do RDO**: 📖 espera Alan e Abel lerem antes de virar
  cobrança. Nenhuma linha de código destrava.

Nenhum dos três bloqueia uma etapa — todos entram como premissa declarada, pela
decisão 3.
