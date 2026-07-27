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
| 6 | Lacuna 1 — três runbooks faltantes | ✅ | `d2946ae9` |
| 7 | Code review profundo — estrutura + varredura 1 | ✅ | `ef4bec3a` |
| 8 | Correção dos 5 achados da varredura 1 | ✅ | `1e0ed9b3` |
| 9 | Varredura 2 (commit alheio) + correção | ✅ | `a8373ffa` |
| 10 | Varredura 3 (premissa desmentida) + correção | ✅ | `c32e3380` |
| 11 | Varredura 4 (silêncio) + correção | ✅ | `fe88d78f` |
| 12 | Varreduras 5-6 + scope único do cronograma | ✅ | `61bdba6a` |
| 13 | Decisão: acesso aberto p/ todos (RBAC adiado) | ✅ | `cda59240` |
| 14 | Conferência visual do RDO percentual | ✅ | (neste commit) |

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

## 7-8 · Code review profundo — estrutura, varredura 1 e correções

Estrutura em `docs/code-review-profundo.md`: revisar **por padrão de defeito**,
não por arquivo. Seis padrões derivados de defeitos reais desta sessão; achado
só entra depois de confirmado com evidência.

### O achado 🔴 da varredura 1 — dinheiro

`portal_obras_views.py:723`, `gerar_medicao`: o percentual e o **valor** da
medição saíam de uma média que incluía a **cópia-cliente** do cronograma
(que nunca recebe sync, então entra com percentual parado) e as tarefas
**arquivadas**.

🔬 Medições que definiram a severidade: **141 obras** têm as duas visões
ativas — eu supunha que a cópia-cliente fosse rara — e há **217 tarefas
arquivadas em 187 obras**. **107 obras** teriam percentual de medição
diferente com os filtros postos; amostra: **8,75% → 11,67%**, valor medido
**25% menor**.

O teste prova o defeito: revertendo a correção, `assert 20.0 == 60.0` — a
diluição exata de (60+0+0)/3. Num contrato de R$ 100.000, R$ 20.000 medidos
em vez de R$ 60.000.

Corrigidos os cinco (A1 com autorização explícita do dono, por mudar número
financeiro): `portal_obras_views.py`, `medicao_views.py`,
`services/obra_handoff.py`, `views/orcamentos_views.py`,
`services/entregas_terceiros.py`. Novo arquivo
`tests/test_escopo_cronograma_interno.py` (5 testes). Suítes que tocam o
código alterado: **115 passed**.

### Achado secundário, ainda em aberto

Aquela média é **simples**; `calcular_progresso_geral_obra_v2` pondera por
duração. São **duas definições de "% da obra"** convivendo — e a menos
rigorosa é a que gera dinheiro. Não unifiquei: é decisão de negócio.

## 9 · Varredura 2 — o import físico-financeiro não era atômico

`sincronizar_percentuais_obra` **comita**. Chamada de dentro de
`_importar_rdos`, ela fechava a transação do import no meio — e tudo o que
vinha antes, **inclusive o `_limpar_derivados`, que é destrutivo**, ficava
gravado antes de `_registrar_versao_inicial` rodar. Uma falha ali deixava a
obra com os derivados antigos apagados, os novos gravados e **sem a
`CronogramaVersao` nº1** de que o guard do M09 depende.

Correção: a sincronização passou a rodar **depois** do commit final, como já
era em `services/atualizacao_rdos.py`.

> ⚠️ **Lição do próprio teste.** A 1ª versão comparava `count()` de tarefas e
> RDOs antes/depois — e o reimport recria a mesma quantidade, então a contagem
> batia mesmo com a transação quebrada: **o teste passava com o defeito de
> volta**. Corrigido para comparar **identidade** (conjunto de ids). Agora
> acusa "101 tarefa(s) e 26 RDO(s) sumiram".

Registrei também três candidatos **não confirmados** (`verificar_estouros_obra`,
`calcular_horas_folha`, `garantir_operacional`): nome de leitura, papel de
escrita — ou, no caso do último, implementação correta com `flush()`.

## 10 · Varredura 3 — a premissa que eu mesmo repeti horas antes

O commit da Fase 1 do editor v2, **e o runbook que escrevi hoje**, afirmavam:

> "com a flag desligada o sistema volta a usar `predecessora_id` (TI/0), que
> o dual-write manteve alimentado"

**Falso.** A sincronização existe só no sentido `predecessora_id →
tarefa_vinculo`. O CRUD novo gravava apenas a tabela nova; o campo legado —
que é o que o motor antigo lê — ficava NULL. **Toda dependência criada com o
editor v2 ligado sumia no rollback, em silêncio.** O runbook prometia uma
reversão que não acontecia.

🔬 Medido (dev): **517 de 722 vínculos (72%)** sem reflexo no campo legado;
490 seriam representáveis.

Correção: `_espelhar_no_campo_legado()` mantém `predecessora_id` em dia na
criação e exclusão de vínculo. **Mas o espelho é parcial por natureza da
coluna** — ela guarda UMA predecessora, sempre TI, sem lag. Vínculo II/TT/IT,
lag ≠ 0 ou segunda predecessora ficam NULL **de propósito**: perder a
dependência no rollback é melhor do que reintroduzi-la com o tipo errado. O
runbook foi corrigido com a tabela do que sobrevive e do que não.

4 testes novos; sem a correção falham com `assert None == <id>`.
Regressão da área: **80 passed**.

## 11 · Varredura 4 — silêncio onde deveria haver erro

205 `except`/`continue` mudos no repositório, mas **97 são em `migrations.py`**
(idempotência por construção) e boa parte do resto é parsing defensivo de
formulário. O critério que separou ruído de defeito: **o silêncio descarta
dado que o usuário mandou, num caminho que grava?**

🟡 **D1** — o import descartava apontamento de tarefa inexistente com um
`continue` mudo. Um `tarefa_mpp` errado no JSON (typo, ou cronograma que mudou
entre a geração e o import) sumia sem rastro e o físico do dia não entrava. O
caso irmão (`_vincular_etapa_tarefas`) já avisava; este não. Agora acrescenta
à lista `avisos`, que o import devolve e a rota/CLI imprime.

Registrei como **ruído avaliado e descartado** os 14 de `views/rdo.py`
(parsing de formulário, o primeiro deles já loga) e os 97 de `migrations.py`.

## 12 · Fecho da revisão — P3, P6 e a correção estrutural

**P3 (guard tardio)** — universo fechado: existem 5 flags de tenant, todas
examinadas. As duas antigas já guardavam antes de gravar; as duas novas foram
corrigidas em `15cac501`; a quinta governa borda visual e não tem efeito a
guardar. **Nenhuma instância restante.**

**P6 (convenção duplicada)** — as duas ordenações de foto foram unificadas, e
o filtro do cronograma repetido em 6 lugares virou um scope único. Sobra uma,
**e ela é decisão sua**: existem duas definições de "% da obra" — média
simples (`gerar_medicao`) × ponderada por duração
(`calcular_progresso_geral_obra_v2`). A média simples é a que gera
`valor_medido`. Unificar muda dinheiro em obras com tarefas de durações muito
diferentes.

**A correção estrutural.** `TarefaCronograma.do_cronograma_interno(obra_id,
admin_id)` passa a ser o ponto único que carrega a convenção
`is_cliente=False + ativa=True`, adotado nos 6 consumidores. Esquecer o
escopo passa a exigir sair do caminho padrão, em vez de ser o caminho padrão.

### O que a revisão sugere sobre o repositório

Os oito defeitos não estavam espalhados ao acaso. **Quatro nasceram de uma
convenção que o código não conseguia lembrar sozinho** — filtrar
`is_cliente`, guardar antes de gravar, avisar em vez de descartar,
sincronizar depois do commit. A correção pontual resolve a instância; o que
impede a volta é mover a convenção para onde esquecê-la exija esforço.

**Os outros quatro nasceram de afirmar sem medir.** A defesa aqui não é
código: é tratar toda frase de continuidade ("é preservado", "é
byte-idêntico", "o dual-write mantém") como hipótese até uma query dizer o
contrário. **Duas dessas frases eram minhas.**

## 13-14 · Decisão de acesso e a conferência visual do RDO percentual

**Decisão do Cássio (27/07):** acesso aberto para todos por enquanto — não há
níveis de acesso definidos. `escopo_obra_ativo` e `compras_governanca_ativa`
ficam desligadas **por decisão de negócio**; detalhe e consequências em
`docs/rollout-consolidado.md`.

**Conferência visual (passo 5 do runbook) — feita e aprovada.** App real em
dev, tenant `visual_rdo`, obra da Baia importada, flag ligada pelo CLI
(o guard deixou passar, como devia). Playwright + Chromium headless — que
**não subia neste ambiente** (libnspr4/libnss3/libgbm ausentes) e passou a
subir com `LD_LIBRARY_PATH` apontando para as libs do nix store
(nss, nspr, mesa, xkbcommon, alsa-lib).

| Verificação | Resultado |
|---|---|
| Novo RDO: cards pedem % acumulado | ✅ todos, inclusive sem quantitativo |
| "Total: 48 un" como referência de leitura | ✅ só na tarefa com quantitativo; nunca "Total: 0" |
| Editar RDO (era só-quantidade) | ✅ modo % presente; Ant: 60% → 80% = histórico real de 21-22/07 |
| Seletor "Como apontar no RDO" no cronograma | ✅ invisível na tarefa-folha (2 no DOM, 0 visíveis) |

Evidências versionadas em `docs/img/rdo-pct-*.png` (3 capturas, ~540 KB).
Com isso, **a flag `rdo_percentual_livre` está pronta para ser ligada na
Baia real** — era a última pendência técnica do pedido original.

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
