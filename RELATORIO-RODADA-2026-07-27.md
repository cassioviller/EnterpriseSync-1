# Relatório da rodada de 2026-07-27

> **Documento vivo.** Atualizado a cada passo concluído, de propósito: se a
> sessão for interrompida, este arquivo é o que permite retomar sem perder
> nada. O que está aqui foi feito e commitado; o que está em "pendente" não.
>
> Leia junto: `ESTADO-ATUAL.md` (mapa geral) e `docs/rollout-consolidado.md`
> (o plano que saiu desta rodada).

## Índice do que aconteceu

| # | Bloco | Estado | Commit |
|---|---|---|---|
| 1 | `ESTADO-ATUAL.md` atualizado | ✅ | `280ce264` |
| 2 | RDOs da Baia via WhatsApp (caminho não-destrutivo) | ✅ | `70046475` |
| 3 | Code review do próprio trabalho — 3 defeitos | ✅ | (neste commit) |
| 4 | Revisão de prontidão + plano de rollout | ✅ | (neste commit) |
| 5 | Lacuna 2+3 — guard nas flags sem rede | ✅ | (neste commit) |
| 6 | Lacuna 1 — três runbooks faltantes | ✅ | (neste commit) |

`main` == `origin/main` até o bloco 2. Os blocos 3 e 4 estão neste commit.

---

## 1 · `ESTADO-ATUAL.md` — commit `280ce264`

O snapshot era de 23/07 e afirmava que o push estava travado e que
`origin/main` estava em `8fe6ac9`. 🔬 27/07: `origin/main == main`, árvore
limpa; o reflog registra os pushes de 35fe1a67 e bdee680a. O item humano nº 2
fechou em 24/07 — o que resta é o `gh` deslogado *nesta máquina*, que é outra
coisa (`git push` funciona; falta a API do GitHub).

Passou a registrar o **editor de cronograma v2** (5 fases, `73f58d3e` →
`8fda59f5`) e o **RDO em porcentagem livre** (`bdee680a`), este com as três
pendências de rollout que a entrega deixou.

## 2 · RDOs da Baia via WhatsApp — commit `70046475`

**O problema:** o diário da obra Baias Kabod (Itu/SP) vive no grupo de
WhatsApp. O export trouxe 12 RDOs de 07/07 a 22/07 que o sistema não tinha (a
série parava em 13/07; os dias 07, 09, 10 e 13/07 tinham texto mas
`apontamentos: []`). E não havia como entrar com eles: o único importador de
RDO em lote **apaga** tarefas, propostas, orçamentos, medições e todos os RDOs
da obra, e é **recusado** em obra já versionada por .mpp.

**O que foi entregue:**

| Arquivo | Papel |
|---|---|
| `services/atualizacao_rdos.py` | upsert por `(obra_id, data_relatorio)`; não apaga nada; pula RDO imutável da Fase 5 com aviso; apontamento via `registrar_apontamento`; tarefa não resolvida vira pendência |
| `scripts/whatsapp_para_rdos.py` | export → payload + fotos numeradas na ordem das legendas |
| `scripts/atualizar_rdos_obra.py` | CLI genérico por obra, com `--dry-run` |
| `docs/rdo/regras_apontamento_baia.json` | de-para revisável atividade→tarefa/% |
| `services/rdo_fotos_import.py` | `_materializar_fotos_rdo` extraído, usado pelos dois caminhos |
| `tests/test_atualizacao_rdos.py` | 37 testes |

**Dois achados que só o código revelou:**

1. Os ids do cronograma são contraintuitivos: **11-52 = Galpão B, 55-96 =
   Galpão A**. E o desempate por nome não pode ser o pai imediato — as duas
   "Execução de Ferragens Para Fundação" têm o mesmo pai ("Fundação") e só se
   distinguem no avô.
2. `get_calendario` cria o calendário padrão e **comita** na primeira chamada
   do tenant, dentro de `registrar_apontamento`. Esse commit alheio levava os
   RDOs pendentes junto e o `dry_run` gravava.

**Dados:** o JSON canônico foi de 19 para **26 RDOs**; 31 fotos novas em
`fotos_rdos/2026-07-14..22` (+9,5 MB). Verificação ponta a ponta em dev: 12
RDOs criados, 22 apontamentos, 0 pendências, com tarefas (101), propostas (1) e
medições (6) idênticas antes e depois.

### ⚠️ Três pontos do de-para que esperam o aval do Cássio

Detalhados em `ESTADO_ATUALIZACAO_BAIA.md` (rodada 27/07):

1. **Tarefas 39/84 "Instalação Infra Hidráulica" a 100% é ANTECIPAÇÃO** — a
   tarefa está planejada para agosto; o RDO de 16/07 diz que a instalação do
   esgoto das 22 baias foi concluída. Se não for a mesma tarefa, tirar.
2. **A tarefa 14 estoura o quantitativo** (64 de 48 un, o engine clampa em
   100%). Ela já vinha errada: o JSON antigo lançou 24 brocas do *Galpão A* na
   tarefa do *Galpão B*. Os dias antigos não foram reescritos.
3. **O protótipo do cocho em LSF (21 e 22/07) não tem tarefa no cronograma** —
   o sistema construtivo segue indefinido e é a causa declarada do atraso.

## 3 · Code review do próprio trabalho — 3 defeitos reais

| # | Defeito | Onde |
|---|---|---|
| 1 | `IndiceTarefas` não filtrava `is_cliente` — o apontamento podia ir para a cópia do cliente, que `sincronizar_percentuais_obra` nunca sincroniza (roda com `cliente=False`). O físico não se moveria e nada acusaria. Confirmado no banco: 315 tarefas `is_cliente=True`; a obra 20 tem 4 empresa + 4 cliente com **os 4 nomes em comum**. É a mesma omissão que a Task #147 já corrigira no endpoint `tarefas-rdo` | `services/atualizacao_rdos.py` |
| 2 | Parser silencioso com export em outro locale — `7/8/26, 8:59 AM -` não casa o cabeçalho e saía como "0 dia(s) de RDO", que se lê como "não teve RDO" e não como "não entendi o arquivo" | `scripts/whatsapp_para_rdos.py` |
| 3 | Ordenação de fotos por `(len, nome)`: com extensões misturadas, `2.jpg` vinha antes de `1.jpeg` e **as legendas grudavam nas fotos erradas** | `scripts/whatsapp_para_rdos.py` |

Os três com teste de regressão. **A obra da Baia não foi afetada pelo nº 1**
(101 tarefas, todas `is_cliente=False`), mas o CLI é genérico por obra.

**Verificado e correto:** transação e `dry_run` (o aquecimento do calendário
resolve o commit alheio); `pct=0`/`quantidade=0` (a validação usa `is None`);
unicidade de `numero_rdo`. **Integridade dos dados commitados: 26 RDOs, 57
apontamentos, 99 fotos, 0 problemas** — nenhum `tarefa_mpp` inexistente,
nenhum apontamento em tarefa-resumo, nenhuma foto referenciada sem arquivo.

**Regressão:** 225 passed, 0 falhas, 7min34s (8 suítes afetadas, sequencial).

### Duas decisões deliberadas, não bugs

- RDO existente em `rascunho` continua rascunho ao ser atualizado — o serviço
  mexe em conteúdo, não em ciclo de vida.
- O álbum de fotos é preservado inteiro se o RDO já tem qualquer foto. Um dia
  que falhou pela metade não se completa na 2ª rodada; sai aviso. Preferido a
  apagar, que violaria a promessa do módulo.

## 4 · Revisão de prontidão + plano de rollout

Documento completo: **`docs/rollout-consolidado.md`**.

**O diagnóstico:** cinco fases fecharam com gate verde e quase nada está em
uso — tudo que muda comportamento nasceu atrás de flag desligada, e nenhuma
flag foi ligada em nenhum tenant. O gargalo não é código: são duas medições em
produção que ninguém fez e três decisões de negócio.

**A dependência que ordena tudo:** `escopo_obra_ativo` é a raiz das Fases 3 e
5. Com ela em `FALSE`, `papel_na_obra` devolve GESTOR a todo autenticado —
qualquer um aprova compra e qualquer um assina RDO. E o que trava
`escopo_obra_ativo` é decisão de negócio: em dev, 4 de 8.723 obras tinham
`responsavel_id`; **ninguém mediu produção**.

**Seis lacunas de prontidão** (nenhuma é bug): 3 das 5 flags sem runbook;
`flag_rdo_percentual_livre --ligar` sem guard nenhum; `flag_cronograma_editor_v2`
avisando depois de gravar; conferência visual do RDO percentual nunca feita;
zero medições de produção; linhas `[FASE4:R5]` não revisadas.

**O plano:** 5 ondas, começando pela Onda 0 (deploy + 3 medições de leitura,
que não mudam nada e destravam a estimativa de todo o resto).

## 5 · Lacunas 2 e 3 — guard nas duas flags que não tinham rede

### 🔎 O achado que mudou o rollout do RDO percentual

A entrega de 24/07 afirmava, no commit e no aviso do próprio script, que a
continuidade estava garantida: *"a linha quantitativa antiga já grava
`percentual_realizado`, então a tarefa em 62% continua em 62% ao ligar a
flag"*. **Isso vale para o que a dupla escrita do M07 escreve hoje, não para
toda linha legada.**

🔬 27/07, banco de dev (⚠️ dominado por carga de suíte — prova a FORMA, não o
volume de produção): **148 apontamentos** com `quantidade_acumulada > 0` e
`percentual_realizado = 0`, em **133 tarefas de 84 tenants**. Nessas tarefas o
`percentual_concluido` hoje sai da quantidade; com a flag ligada passaria a
sair do percentual — que é 0. **A obra perderia avanço físico na tela sem
ninguém apontar nada.**

Daí o guard: `tarefas_que_regridem(admin_id)` compara, tarefa a tarefa, o %
de hoje com o % de depois, usando a mesma fórmula dos dois lados. O `--ligar`
**recusa antes de gravar** e lista as tarefas; `--forcar` passa por cima;
desligar reverte de qualquer forma.

### O mesmo defeito de forma nas duas flags

Ambas chamavam `definir_flag` **primeiro** e imprimiam o aviso **depois** —
quem lesse o aviso já estava com a flag ligada. Agora o guard vem antes:

| Script | O que passou a recusar |
|---|---|
| `flag_rdo_percentual_livre.py` | tarefas que perderiam físico (com `--forcar`) |
| `flag_cronograma_editor_v2.py` | calendário do tenant que considera sábado/domingo, incompatível com o motor seg–sex desta fase (com `--forcar`) |

Também corrigi o texto do aviso do RDO percentual, que afirmava a premissa
derrubada acima.

**Testes:** +7 em `tests/test_rdo_percentual_livre.py` (30, eram 23) e o
arquivo novo `tests/test_flag_cronograma_editor_v2.py` (6) — **essa flag não
tinha teste nenhum desde 24/07**. Suítes: 76 passed.

## 6 · Lacuna 1 — os três runbooks que faltavam

Das cinco flags que seguram as entregas, **três não tinham runbook**. Agora
todas têm, no padrão dos das Fases 1-5 (o que a flag muda → pré-requisitos →
ordem → rollback → o que a entrega deliberadamente NÃO fez).

| Runbook | O ponto que ele existe para não deixar passar |
|---|---|
| `docs/rdo-percentual-livre-rollout.md` | As tarefas que perdem físico, e o passo 5 — a **conferência visual dos dois fluxos de RDO**, que continua sem ter sido feita |
| `docs/cronograma-editor-v2-rollout.md` | **Desligar a flag reverte o MOTOR, não o DADO**: datas já recalculadas continuam gravadas. Daí o snapshot antes de ligar |
| `docs/cronograma-mpp-rollout.md` | O bloqueio nº 1 é `versao_sistema='v2'`, que **mascara as outras quatro portas** — por isso o diagnóstico vem antes de tudo. E a flag governa a borda visual, **não é controle de acesso** |

`docs/rollout-consolidado.md` foi atualizado: a tabela das cinco flags agora
aponta cada runbook, e a tabela de lacunas marca 1, 2 e 3 como fechadas.

---

## Regressão final da rodada

🔬 27/07, sequencial, `SIGE_ENABLE_DEMO_SEED=false`:
**225 passed, 0 falhas, 3min19s** sobre `test_atualizacao_rdos`,
`test_rdo_percentual_livre`, `test_flag_cronograma_editor_v2`,
`test_importacao_fisico_financeiro`, `test_fase5_rdo_ciclo_vida`,
`test_fase5_rdo_fotos` e `test_painel_financeiro`.

## Pendente nesta rodada

Nada. Os dois itens que estavam abertos (lacunas 1 e 2+3) foram fechados.

## Fora do escopo desta rodada, e continua em aberto

- A **Onda 0** do rollout (medições em produção) — é ação humana.
- Os **três pontos do de-para da Baia** que esperam aval.
- A **Task 15 da Fase 5** (migração de 16 GB de fotos), com seis
  pré-requisitos de infraestrutura, nenhum feito.
- As **Fases 6 a 9** — planos escritos em 21-23/07, nenhuma linha de código.
