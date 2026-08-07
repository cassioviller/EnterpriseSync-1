# Plano de execução da rodada B6 — 2026-08-06 (execução autônoma autorizada)

> **For agentic workers:** REQUIRED SUB-SKILL: `superpowers:executing-plans`.

**O que é.** O plano de execução da rodada B6. Os recortes vivem em
`docs/superpowers/plans/2026-08-06-rodada-b6-varredura.md` e não são repetidos; quando
divergirem, o recorte vence.

**Autorização.** O Cássio autorizou em 06/08, por escrito na sessão ("eu não vou estar
na frente da tela para aprovar, já estou dando autorização"): documentar, criar o plano
e **executar sem aprovação por etapa**. As decisões D-B6.1 a D-B6.4 executam pelos
defaults do §9 da rodada — todos decidíveis com dev + código, por exigência da decisão
anterior dele (sem consultas de produção) — e ficam registradas como decisão dele por
delegação, no padrão da B5.

**As duas fronteiras da autorização** (mantidas mesmo autorizado):
1. **`main` não anda sozinha** — o fast-forward dispara o deploy; ao final, a branch
   `test/b0-arreio` sobe para o remoto e a `main` espera o Cássio.
2. **Decisão sem default executável não é chutada** — a Task para, o resto segue, o
   motivo fica escrito (precedente B1.14).

## ⏸️ PAUSADO em 2026-08-07 — a frase que retoma é `RETOMAR ARREIO B6`

O Cássio **pausou a execução sequencial** em 07/08 para fazer ajustes específicos fora
desta rodada. O plano **não foi abandonado nem cortado**: a F1 está fechada e a F2 nunca
abriu (estado por extenso no FECHO, no fim deste arquivo).

**Quando ele escrever `RETOMAR ARREIO B6`**, a rodada volta imediatamente, sem
re-perguntar o que fazer:

1. Ler o **FECHO DA SESSÃO** (fim deste arquivo) e as Tasks **B6.4–B6.8** do recorte,
   com o **molde comum dos lotes 404** e o §5 de serialização.
2. **Re-rodar o gate completo antes de abrir a F2.** Os ajustes avulsos da pausa podem
   ter mexido na linha de base (no momento da pausa: 1981 passed / 2 failed, ambas
   provadas alheias à B6). Conferir também o `git log` da `test/b0-arreio`.
3. Retomar na **F2.1 = Task B6.4** (lote 404 de `propostas_consolidated.py`), com as
   regras da F2 abaixo intactas — um agente por lote, um de cada vez, agente não commita.

As duas fronteiras da autorização continuam valendo durante e depois da pausa, e as duas
decisões dele que ficaram escritas em vez de chutadas (ponta solta da **E02** no
`notificacao_cliente`; dependência de ordem do `test_custo_diario`) **seguem em aberto** —
a pausa não as resolve.

## Fases

- **F1 — sessão principal, serial** (as delicadas: migração, dinheiro, remoção):
  - [x] F1.1 — **B6.1** estorno de recebimento (migração **281**) — `87786a88`
  - [x] F1.2 — **B6.2** família 2 + guard do migrar — `7c188985` + `dbe1fdbc`
  - [x] F1.3 — **B6.3** vehicles, remoção provada (P) — `6c744df7`
  - [x] F1.4 — gate completo + revisão adversarial **WF-4** — findings em `55d80939`
- **F2 — os cinco lotes 404 (B6.4-B6.8), por SUBAGENTES SEQUENCIAIS**:
  - Um agente por lote, um de cada vez (o banco de dev é único — paralelismo de teste
    é não-determinismo, §2 do plano da B5). Cada agente recebe o molde da B5.3 e o
    recorte do lote; implementa red-first e roda SÓ os testes do lote.
  - A sessão principal **não terceiriza a evidência**: depois de cada agente, re-roda
    os testes do lote, roda as mutações ela mesma, revisa o diff e commita. Agente não
    commita.
  - Serialização interna: B6.5 antes de B6.7 (`views/obras.py` compartilhado).
  - [ ] F2.1 B6.4 · [ ] F2.2 B6.5 · [ ] F2.3 B6.6 · [ ] F2.4 B6.7 · [ ] F2.5 B6.8
- **F3 — fecho**: gate completo final + revisão WF dos lotes + Status/checkboxes na
  rodada + FECHO da sessão + **push da branch**.

## Registro das decisões (por delegação, 06/08)

| Decisão | Executada como |
|---|---|
| **D-B6.1** | estorno e cinto **excluem** `OBRA_MEDICAO` (recusa por origem); as 24 QUITADA legadas ficam inestornáveis e registradas |
| **D-B6.2** | `apenas_pagamento` segue editável; chore de texto nomeando o risco por extenso |
| **D-B6.3** | `novo_veiculo_OLD` sai no lote de vehicles |
| **D-B6.4** | destino do 404 = `error.html`; rotas fetch ganham JSON 404 (precedente D-B5.3) |

## FECHO DA SESSÃO — 2026-08-06 (a sessão CAIU e foi retomada)

**Onde a rodada está: a F1 fechou inteira; a F2 NÃO COMEÇOU.** Cinco lotes 404
(B6.4–B6.8) e a F3 seguem abertos. Nada foi deixado pela metade — a F2 nunca abriu.

### O que foi entregue (5 commits + 1 de docs)

| Commit | O quê |
|---|---|
| `87786a88` | B6.1 — estorno de recebimento; migração **281 gasta** |
| `7c188985` | B6.2 — família 2 sai da tela e do fluxo; migrar não clona reembolso |
| `dbe1fdbc` | chore — texto do `apenas_pagamento` |
| `6c744df7` | B6.3 — as três rotas mortas de vehicles saem |
| `55d80939` | os seis findings da revisão adversarial **WF-4** |

### A sessão caiu no meio da F1.1

A queda foi entre o Step 2 e o Step 3 da B6.1: a migração 281 e
`ContaReceber.banco_id` estavam na árvore **sem commit**, e o arreio não existia.
A retomada partiu do Step 3 (red-first), como o precedente manda — nada foi
aproveitado sem ver vermelho antes.

⚠️ **A migração 281 já estava APLICADA no banco de dev** (`migration_history`,
06/08 17:18) antes do commit existir. Quem retomar uma sessão caída depois de uma
migração precisa conferir isso: o `IF NOT EXISTS` salvou aqui, mas uma migração sem
ele teria falhado na primeira execução da árvore recuperada.

### O gate completo: 1981 passed, **2 failed — nenhuma da B6**

Diagnosticadas e provadas alheias (a B6 não tocou `views/obras.py`, nem os dois
arquivos de teste; o único FK que a 281 cria aponta para `banco_empresa`):

1. `test_custo_diario::test_4_snapshot_imutavel_mudanca_salario` — **passa isolada**
   (8 passed no arquivo inteiro). Dependência de ordem dentro do gate, pré-existente.
2. `test_excluir_obra::test_lista_cobre_toda_fk_no_action_para_obra` — aponta
   `notificacao_cliente`: a tabela **ainda existe** em dev (0 linhas) com FK NO ACTION
   para `obra`, mas `3ba7937c` já a tirou de `TABELAS_DEPENDENTES_OBRA`. A migração 279
   está registrada como `success` em 05/08 e a tabela sobreviveu mesmo assim.
   **É defeito REAL: hoje, em dev, excluir uma obra estoura nessa FK.** É ponta solta da
   **E02**, não da B6 — não foi tocada para não alargar escopo por conta própria.
   **Decisão do Cássio.**

### A revisão WF-4 (4 revisores + 1 cético por finding + síntese)

15 findings levantados, **9 sobreviveram** à refutação, consolidados em 6. Veredito
**confirmado_com_correcoes**. Só um tocava comportamento (E1, o botão Estornar inerte
com apóstrofo na descrição). As lições que valem para as próximas rodadas:

- **Âncora numérica em comentário é rot na ORIGEM, não por erosão.** Três das nove
  âncoras podres já nasceram erradas no commit que as escreveu — o autor editou o
  código e o comentário no mesmo commit e não releu o número. Política adotada:
  **citar símbolo + literal** (`` `rr_query` em `calcular_fluxo_caixa` ``), imune a
  inserção de linhas.
- **Guarda de teste sem o dado que ela guarda é guarda vazia.** O caso 4 da B6.2
  prometia guardar contra exclusão larga num tenant sem nenhuma `ContaPagar`: a mutação
  do predicado sobrevivia à suíte inteira.
- **Contador de região gerada não se edita à mão.** O gerador do `MODULOS.md` devolveu
  124/754; o hand-edit "óbvio" teria plantado 125/756 — número novo e falso.

### O que falta (F2 e F3)

- **F2 — cinco lotes 404, por subagentes sequenciais** (um por vez; o banco de dev é
  único): B6.4 propostas · B6.5 miscelânea · B6.6 frota · B6.7 obras · B6.8 cauda.
  Serialização interna: **B6.5 antes de B6.7** (`views/obras.py` compartilhado).
  A sessão principal não terceiriza a evidência: re-roda os testes, roda as mutações,
  revisa o diff e commita. Agente não commita.
- **Adiantado nesta sessão** (economia real para quem retomar): o **scanner de censo**
  do Step 0 dos cinco lotes está escrito e medido. Ele reproduz o documento
  (`propostas_consolidated.py`: 18 TRYs, todos sem o ramo, 24 ocorrências no arquivo,
  zero `except HTTPException`). ⚠️ Ele é **piso, não veredito**: em `frota_views.py`
  levanta 25 candidatos `if not ...` e o recorte nomeia **10** — os outros são validação
  de formulário e guarda de lista, que o critério (i) do molde põe fora de propósito.
  O scanner não foi versionado (o recorte manda deixá-lo no scratchpad).
- **F3 — fecho**: gate final + revisão WF dos lotes + Status/checkboxes + push.

### As duas fronteiras: respeitadas

1. **`main` não andou.** Segue em `6cd3f774`; todo o trabalho está em `test/b0-arreio`.
2. **Nenhuma decisão sem default foi chutada.** D-B6.1 a D-B6.4 executaram pelos
   defaults escritos. A única decisão nova que apareceu — o que fazer com a ponta solta
   da E02 no gate — **parou e ficou escrita**, como o precedente B1.14 manda.

## Histórico

- **2026-08-06, noite** — escrito e disparado em execução autônoma, logo após a
  varredura B6 (9 agentes, 8 Tasks, vereditos 4× confirmado_com_correcoes).
- **2026-08-06, madrugada** — a sessão caiu no meio da F1.1 e foi retomada. F1 fechada
  (5 commits), WF-4 aplicada, F2 não iniciada. Fecho acima.
- **2026-08-07** — o Cássio **pausou** a rodada para ajustes específicos fora dela e
  pediu uma frase-gatilho de retomada: **`RETOMAR ARREIO B6`** (seção no topo). O estado
  congelado é o mesmo do fecho de 06/08 — F1 fechada, F2 nunca aberta, branch com 7
  commits e **nada pushado**.
