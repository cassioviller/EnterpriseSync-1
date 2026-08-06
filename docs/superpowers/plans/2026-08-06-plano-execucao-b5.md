# Plano de execução da rodada B5 — 2026-08-06

> **For agentic workers:** REQUIRED SUB-SKILL: `superpowers:executing-plans`.
> Os passos usam checkbox (`- [ ]`).

**O que é.** O plano de **execução** da rodada B5. Os recortes — Files, Comportamento,
Steps, riscos com mitigação — vivem em
`docs/superpowers/plans/2026-08-06-rodada-b5-varredura.md` e **não são repetidos aqui**:
este documento diz a ordem, as premissas, o que roda na sessão principal e o que roda em
agentes, e o que fazer com os onze itens abertos que a varredura descobriu. Quando os dois
divergirem, **o recorte da rodada vence** — este plano é o mapa, não o território.

**Contra o quê:** branch `test/b0-arreio`, HEAD `4b53a6a1` + os dois documentos da
varredura (untracked). 63 commits locais, nada no remoto.

**Marcas:** 🔬 medido · 📖 lido · 🧮 deduzido · ⚠️ dev. Afirmações herdadas da rodada B5
citam a seção de origem em vez de repetir a marca.

---

## 1. Premissas — os defaults que este plano assume

A rodada deixou cinco decisões com default proposto (§9 dela). **Este plano executa sobre
os defaults.** Cada um está listado com o que muda se o Cássio responder o contrário —
quem retomar precisa saber que isto foi **assunção comunicada**, não decisão tomada em
silêncio.

| Decisão | Default assumido | Se a resposta for outra |
|---|---|---|
| **D-B5.3** | 404 em todas as rotas, inclusive na tela HTML | O Step 4 da B5.3 ganha um ramo: tela mantém flash+redirect, programáticas dão 404. O teste muda nos casos 1-2 |
| **D-B5.4** | (B) manter os dois `finalizar_rdo` | (A) reabre a B5.4 como **G**, serializa com a B5.3 e reescreve o arreio de custo — não fazer sem sessão dedicada |
| **D-B5.1** | (a) `GestaoCustoPai` é a única fonte da SAÍDA; o escritor de FC `'conta_pagar'` — hoje em `financeiro_views.py:434-452` (⚠️ a âncora original `:407-418` ficou EM CIMA da guarda da B5.1 depois do commit `0bc62449`; corrigida pela revisão WF-1 — executar o corte pela âncora velha apagaria a guarda) — **sai** em vez de ser completado | (b) reabre o recorte da F2 inteiro: a exclusão de gêmeos vira pré-requisito de qualquer escrita |
| **D-B5.5a/b/c** | peso vivo · só a Curva S · borda por exclusão com rótulo | Afeta só a B5.5, que está bloqueada de qualquer jeito |
| **D-B5.2** | documentar a jornada (comentário no topo), não reescrever | Se a paralelização do gate entrar na mesa, inverte — e o item nº8 (Timer) passa na frente |

**Premissa de método, herdada e não negociável:** teste visto **vermelho** antes da
correção, prova por **mutação** depois (desfazer um Step derruba só os casos dele), linha
`**Status:**` no documento da rodada com commit e desvio. É o formato das 60 Tasks
entregues.

---

## 2. A forma da execução — o que é sessão principal e o que é agente

**Implementação é SERIAL, na sessão principal.** Três razões medidas, nenhuma de gosto:

1. 🔬 O `DATABASE_URL` é único e de desenvolvimento (`app.py:110`). Todo teste roda contra
   ele. N agentes implementando em paralelo = N suítes colidindo no mesmo banco.
2. 🔬 O item novo nº8 da rodada (§4 dela): o listener de RDO sobe um `Timer` em **thread de
   fundo** sobre a scoped_session global (`models.py:8385-8423`). Paralelismo contra esse
   banco não é só lento — é **não-determinístico**.
3. A disciplina red-first + mutação exige **ver** o teste falhar e passar. Um agente que
   volta dizendo "verde" entrega a afirmação da evidência, não a evidência. Foi a lição
   das marcações retroativas de 05/08.

**Agentes entram onde são comprovadamente bons aqui — trabalho read-only:**

| Peça | O quê | Quando |
|---|---|---|
| **WF-1 `revisao-b5`** | Revisão adversarial dos diffs da Fase 1: um revisor por commit + um transversal, todos read-only | Depois do último commit da F1, **em paralelo com o gate** (agentes leem arquivos; o gate usa o banco — não colidem) |
| **WF-2 `varredura-b5-dinheiro`** | Levantamento + refutação dos itens novos nº1/nº2 (§4 da rodada), no mesmo formato da varredura que funcionou: cinco lentes, adversário, síntese | Pode rodar **durante** a Fase 1 — é read-only e não disputa o banco |

⚠️ Nota operacional da varredura anterior (registrada no `FECHO-VARREDURA-B5`): 🔬 4
núcleos, teto de concorrência **2**. Os workflows abaixo são dimensionados para isso —
WF-2 tem 5 agentes (~40min de relógio), WF-1 tem 5 (~30min, sobrepostos aos 21min do
gate). Nada de fan-out de onze agentes de novo nesta máquina.

**O gate:** alvo dirigido por Task (o arquivo de teste novo + os arquivos da área tocada),
e o gate **completo uma vez ao fim da Fase 1** — o precedente é a sessão de 05/08 (13
commits, um gate). Se a F1 parar no meio, gate completo antes de parar.

---

## 3. Fase 0 — destravar (nenhuma linha de código de produção)

- [x] **F0.1 — Pacote de produção consolidado.** Montar UM artefato com as **nove**
      consultas: as cinco da §7 da rodada (duas da B5.1, uma da D-B5.1, duas do Step 1 da
      B5.5) + as quatro herdadas (E02/D11 `notificacao_cliente`, B2.13 invariante da
      folha, B1.8 `q7`, E04 `rdo_gerado_id`). Cada uma com o valor ⚠️ dev de referência e
      o que cada resultado destrava. Entregar ao Cássio; **nada nesta fase espera a
      resposta** — só a B5.5 e o fecho da B2.13 esperam.
- [x] **F0.2 — Correções de registro que não pertencem a nenhuma Task.** No plano
      consolidado: a tabela de contagem do §2 (diz B3 3/10 e B4 7/9; 🔬 os Status dizem
      60/61) e o §11.3 ponto nº3 (aponta `views/obras.py:727-770`, 🔬 removida em
      `db85ba04` — item novo nº10 da rodada). **As correções do E04 ficam na B5.4 Step 3,
      onde já estão** — não duplicar.
- [x] **F0.3 — D-B5.2 pelo default:** comentário no topo de
      `tests/test_e2e_jornada_proposta_cronograma_playwright.py` — "este arquivo só roda
      inteiro; o `CTX` de módulo é escrito pelos testes 01/02/04/05 e lido por 14 dos 19;
      nunca filtrar com `-k`". Uma edição, commit próprio de docs/test.
- [x] **F0.4 — Disparar o WF-2** (§5) em background. Ele é read-only; a Fase 1 não espera
      por ele nem ele por ela.

---

## 4. Fase 1 — as quatro Tasks executáveis, na ordem da rodada

Referência de recorte: §3 da rodada. Aqui só a ordem interna de execução e as provas por
mutação que o Step de cada Task pede mas não detalha.

- [x] **F1.1 — Task B5.1** (`NameError` + guarda de re-baixa, MESMO commit).
      Red-first nos casos 1 e 3; os cinco casos verdes; mutação: desfazer o conserto do
      log derruba só 1-2, desfazer a guarda derruba só 3. **Atenção ao risco 4 do
      recorte:** o flash da guarda aponta para o estorno, e o estorno tem o defeito da
      catraca (item nº1) — o texto do flash sai como o recorte manda, sem prometer o que o
      estorno não cumpre.
- [x] **F1.2 — Task B5.2** (fixture `operacional`).
      Os dois vermelhos isolados primeiro (`:175` e `:228`); depois três passes isolados +
      7/7 no arquivo. **Não tocar em `:146`** — é o risco 2 do recorte, e é exatamente o
      tipo de "simetria" que um revisor apressado sugere.
- [x] **F1.3 — Task B5.3** (404 por tenant E por obra, M — a maior da fase).
      A ordem interna dos Steps **é a mitigação do risco 1** e não pode ser trocada:
      `except HTTPException: raise` (Step 2) vem ANTES das guardas (Steps 3-4), senão o
      404 novo é engolido e a Task fecha verde sem mudar nada — o formato exato de
      falha silenciosa que a rodada existe para impedir.
      Mutações ao fim: remover o `except HTTPException` de um handler derruba o caso 5
      daquele handler e nenhum outro; remover o `pode_ver_obra` derruba só o caso 6;
      restaurar a segunda query sem tenant derruba só o caso 7.
- [x] **F1.4 — Task B5.4** (corte das duas APIs mortas + registro do E04).
      O Step 1 é **caracterização** (teste do url_map verde antes do corte — placar
      4/9/1); o corte muda o placar e o teste junto. Mutação natural: restaurar um
      decorador cortado derruba o teste do map. O Step 3 edita três documentos
      (`models.py:2179-2183`, plano `:4732`, `ESTADO-ATUAL.md:939`) — conferir os três no
      mesmo commit, porque registro divergente entre eles foi o que fez o E04 mentir por
      dois dias.
- [x] **F1.5 — Gate completo + WF-1 em paralelo.** `bash run_tests.sh --gate` na sessão;
      WF-1 disparado junto (read-only, não disputa o banco). Findings do WF-1 que
      sobreviverem à checagem na sessão viram fix imediato + re-teste dirigido; se algum
      fix tocar código de produção, gate de novo.
- [x] **F1.6 — Status das quatro Tasks** no documento da rodada, com commit e desvio —
      no dia, não retroativo.

**WF-1 `revisao-b5`, o desenho.** Cinco agentes read-only:

| Agente | Alvo | O que ataca |
|---|---|---|
| rev:B5.1 | diff do commit 1 | Os 4 riscos do recorte viraram código? A guarda ficou FORA do try? O flash promete só o que pode? |
| rev:B5.2 | diff do commit 2 | `:146` intocado? O fixture é o intermediário, não criação no `ctx`? |
| rev:B5.3 | diff do commit 3 | O `except HTTPException` está antes do rollback em TODOS os seis? `rdo_editar_sistema.py` ficou fora? A resolução de tenant p/ SUPER_ADMIN mudou onde o recorte disse que mudaria — e só ali? |
| rev:B5.4 | diff do commit 4 | Só `:653` e `:681` cortados? `/rdo/excluir/<id>` vivo (E04)? Os três registros dizem a MESMA coisa? |
| rev:transversal | os 4 diffs juntos | `url_for` para endpoints de `rdo_crud` ainda constroem? As listas CSRF de `main.py:206-219` intactas? Algum teste por STRING de arquivo (`test_p1_dedup:207`, `test_fase1_identidade:333`, `test_arreio_custo:19`) quebrou? Desvio de recorte não registrado? |

Cada revisor devolve findings com âncora e severidade; a instrução é **refutar o commit**,
não aprová-lo. Finding sem âncora conferível não conta.

---

## 5. Fase 2 — os dois itens de dinheiro em produção, do recorte à Task

Itens novos nº1 e nº2 da rodada (§4): a **catraca de `banco.saldo_atual`** (estorno não
devolve o débito; e esse número é o `saldo_inicial` do fluxo — `financeiro_service.py:485`)
e a **discordância entre os dois caminhos de pagamento** (um debita o banco, o outro não).
São os únicos achados que valem em produção **hoje**, e não têm recorte.

**Por que não implementar direto:** a solução depende de uma pergunta que ninguém
respondeu — 🧮 **a `ContaPagar` persiste `banco_id`?** `baixar_pagamento` recebe
`banco_id` por parâmetro e grava `forma_pagamento` na conta (📖 `financeiro_service.py:100`),
mas se o banco debitado não fica registrado em lugar nenhum, `estornar_conta` **não tem
como saber qual banco creditar**. E cada resposta leva a uma solução diferente:

| Hipótese | Solução candidata | Custo |
|---|---|---|
| (A) persistir `banco_id` na conta | estorno credita de volta pelo campo | **coluna nova = migração 280** — primeira da faixa liberada; alocar ANTES de tocar `migrations.py` (§11.3 nº2 do plano consolidado) |
| (B) operador informa o banco no estorno | sem migração; sujeito a erro humano | P, mas o dado histórico continua irrecuperável |
| (C) `saldo_atual` deixa de ser contador mutável e vira **derivado** (cadastro + Σ movimentos por banco) | a catraca E a discordância entre caminhos morrem **por construção** — não há mais contador para os caminhos discordarem | G; toca o lado receber junto; é redesenho, não conserto |
| (D) registro em `FluxoCaixa` como fonte da reversão | 🔬 morto na largada: zero linhas `'conta_pagar'` em `fluxo_caixa` (⚠️ dev) e o escritor sai pela D-B5.1 | — |

**WF-2 `varredura-b5-dinheiro`** resolve isso com o padrão que acabou de se provar:

| Fase | Agentes | Tarefa |
|---|---|---|
| Levantar | 2 | Um por item. Cinco lentes sobre: TODOS os escritores e leitores de `saldo_atual`; as colunas reais de `ContaPagar`/`ContaReceber` (o `banco_id` existe?); o estorno do lado RECEBER (a catraca é simétrica? `baixar_recebimento` credita em `:339` — quem estorna recebimento, e devolve?); `estornar_gcp`; e a medição ⚠️ dev de quantas contas PAGO têm banco recuperável por qualquer via |
| Refutar | 2 | Os seis ataques da varredura anterior + um específico: **para cada hipótese A-D, o que ela quebra** — o par obrigatório no mesmo commit, a janela de estado incoerente, o teste que ficaria verde e oco |
| Sintetizar | 1 | Recortes B5.6 (estorno/catraca) e B5.7 (fluxo de caixa: a exclusão de gêmeos de `listar_contas_pagar` que `calcular_fluxo_caixa` não tem — item nº5 — mais o destino do escritor morto de `views/vehicles.py:922-930`, item nº3, que é gated pela D-B5.1), **apensados ao documento da rodada** com a decisão D-B5.6 formulada para o Cássio se a resposta for migração ou redesenho |

- [x] **F2.1** — WF-2 rodou (disparado na F0.4); ler a síntese, conferir na sessão as
      âncoras centrais (a regra da §6 do FECHO: 🔬 de agente não é 🔬 meu até reabrir)
- [x] **F2.2** — se a solução recomendada for (B) ou não exigir decisão: implementar B5.6
      na sessão, red-first, gate dirigido
- [x] **F2.3** — se for (A) ou (C): **parar e perguntar** — migração e redesenho são
      decisões do Cássio, com o recorte pronto na mão
- [x] **F2.4** — B5.7 implementa **depois** da resposta da D-B5.1 (default: a exclusão de
      gêmeos entra em `calcular_fluxo_caixa`; o escritor de vehicles **sai** em vez de
      ganhar `admin_id`)

---

## 6. Fase 3 — o que fica esperando, e o que destrava cada um

| Item | Espera | Destrava |
|---|---|---|
| **B5.5** (curva de baseline) | Step 1 em produção (duas consultas do pacote F0.1) + D-B5.5a/b/c | Se produção ≈ dev (82 obras, 1 relevante, Δ 1,1 p.p. na direção **contrária** ao risco 6), a recomendação é **não implementar** e fechar a dívida como "medida e descartada" — resultado tão válido quanto entregar |
| **B2.13** (fecho) | a consulta do invariante no pacote | zero ⇒ marca a última Task do plano consolidado; ≠0 ⇒ item novo com migração própria |
| **E02/D11** | deploy (migração 279 no boot) | `success` ⇒ nada; `failed` ⇒ `git revert ab626765` — o roteiro está no `FECHO-SESSAO-2026-08-05.md` |
| **Família flash+redirect (35 rotas) + 45 candidatas de 404 engolido** | Task própria com arreio próprio — o recorte da B5.3 mediu e deixou fora de propósito | Rodada B6, com a B5.3 como molde |
| **Itens nº7/nº8/nº9** (CTX da jornada, `Timer` do listener, gate sem randomização) | decisão de paralelizar o gate | Se entrar na mesa: nº8 **primeiro** (é quem torna paralelismo não-determinístico), depois nº7, depois `pytest-randomly` |
| **Push dos 63+ commits** | decisão do Cássio | ⚠️ com a B5.1 dentro, o argumento "não empurrar com defeito conhecido" **cai** — depois da F1, o que segura o push é só o gate do E02 |

---

## 7. Sequenciamento

```
F0.1-F0.3 (sessão, ~30min)
F0.4: WF-2 dispara ───────────────────────────┐  (read-only, ~40min, fundo)
F1.1 B5.1 → F1.2 B5.2 → F1.3 B5.3 → F1.4 B5.4 │  (sessão, serial)
F1.5: gate 21min ─┬─ WF-1 revisão (fundo)  ←──┘
                  └→ fixes → Status (F1.6)
F2: ler síntese WF-2 → B5.6 (ou pergunta) → B5.7 (pós D-B5.1)
F3: conforme produção/decisões chegarem
```

A única serialização dura da F1 é a herdada da rodada: **B5.3 antes da B5.4** (e só
importaria de verdade na hipótese (A) da D-B5.4, que o default descarta). WF-2 não
serializa com nada; WF-1 só precisa dos quatro commits prontos.

**Fila de perguntas ao Cássio ao fim da F1** (nenhuma trava a F1): D-B5.1 (reconciliação,
não escolha nova), D-B5.3 (só se quiser reverter o default já aplicado), resultado do
pacote de produção, push. A D-B5.6 entra se o WF-2 devolver migração ou redesenho.

---

## 8. O que este plano NÃO cobre

Os adiados da §8.2 do plano consolidado seguem onde estão — esta rodada não os reabre. A
rodada B6 (família dos 404, suite health se a paralelização vier) só nasce depois de a B5
fechar e com varredura própria. E nada aqui substitui as decisões 4-7 do `PLANO-NUCLEO.md`,
que continuam travando A15/A18/A24/A25.

## Histórico

- **2026-08-06** — Plano de execução escrito sobre a rodada B5 recém-varrida. Defaults
  das cinco decisões assumidos e comunicados (§1). Duas peças de orquestração definidas:
  WF-1 (revisão adversarial pós-F1) e WF-2 (recorte dos dois itens de dinheiro), ambas
  read-only por construção — implementação permanece serial na sessão principal, pelas
  três razões da §2.
- **2026-08-06, noite — EXECUTADO INTEIRO, com um desvio de premissa.** F0, F1
  (B5.1-B5.4 + gate 1952 + WF-1), F2 (B5.6 `08f2ee88` com a migração 280, B5.7
  `3288ba84`+`b5472260`, apertos WF-3 em `f69cb359`). O desvio: o Cássio decidiu NÃO
  rodar as consultas de produção — os defaults viraram decisão (registrada na rodada,
  §9/§10), a B5.5 caiu pelo mecanismo do próprio Step 1 e a F3 encolheu para o roteiro
  de deploy do E02 + as filas futuras (contador: mapear DESPESA_GERAL; estorno de
  recebimento; rodada B6). A nota da D-B5.1 na §1 foi re-ancorada pela revisão WF-1 e o
  escritor que ela manda apagar saiu em `f69cb359`.
