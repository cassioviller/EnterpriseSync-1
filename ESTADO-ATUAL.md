# ESTADO ATUAL — SIGE / Veks

> Snapshot de **2026-08-03** (6ª revisão, após o `PLANO-NUCLEO.md` — os dez
> pacotes entregues, com três recortes explícitos).
> Este é o documento a ler PRIMEIRO ao retomar. Os demais (`PLANO-NUCLEO.md`,
> `DEVOLUTIVA.md`, `DOSSIE-REPO.md`, `FECHO-FASE-0.5.md`) são o detalhe; este é
> o mapa.

## Como ler os números deste documento

A 1ª versão deste arquivo tinha **cinco afirmações erradas**, todas descobertas
na rodada de planejamento de 21/07. Nenhuma foi mentira: cada uma foi verdade
quando escrita e envelheceu sem data, ou perdeu um qualificador na compressão
entre `DOSSIE-REPO.md` → `DEVOLUTIVA.md` → aqui. "Estruturalmente órfãs" virou
"órfãs"; "67 commits à frente" era verdade e não tinha data.

Por isso, daqui em diante **todo número carrega procedência**:

| Marca | Significado |
|---|---|
| 🔬 | **Medido** — query no banco ou execução de código, com data |
| 📖 | **Lido no código** — `caminho:linha` conferido |
| 🧮 | **Deduzido** de outro documento — não reconferido |
| ⚠️ dev | Veio do banco de **desenvolvimento**, dominado por carga de suíte. Prova a *forma* do problema, **não** o volume de produção |

Se você for corrigir algo aqui, mantenha a marca. Número sem procedência é o
defeito de fabricação que produziu os cinco erros.

## Onde estamos

Branch: `main` · 🔬 03/08: **`origin/main == main == 63cc1c13`, árvore
limpa** — conferido em `git ls-remote origin main`, não só no ref local. Os
dez pacotes do núcleo **estão no GitHub**; o aviso do commit `6942d043`
("parados atrás de um push sem credencial") **envelheceu no mesmo dia**: o
push saiu depois dele. O `gh` CLI continua deslogado *nesta máquina*
(🔬 03/08: `gh auth status` → "not logged into any GitHub hosts";
`GH_TOKEN`/`GITHUB_TOKEN` também ausentes), o que é outra coisa: ~~`git push`
funciona, o que falta é a API do GitHub (abrir PR, fetch de branch de
triagem). Refazer o login é interativo — item humano, restrito ao `gh`.~~

> 🔴 **16/08: isto envelheceu e virou falso. `git push origin` NÃO funciona.**
> 🔬 tentativa real: `remote: Invalid username or token. Password authentication
> is not supported for Git operations.` Não há `credential.helper`, não há
> `~/.git-credentials`, e `GH_TOKEN`/`GITHUB_TOKEN`/`GIT_TOKEN`/`GITHUB_PAT`
> estão todos ausentes. O item humano **não** é restrito ao `gh`: sem login,
> nada sai para o GitHub. Este parágrafo é o sexto caso do defeito de
> fabricação que abre o documento — verdade quando escrita, sem data no
> qualificador que importava.
>
> 🔬 16/08: o remote **`gitsafe-backup`** (`git://gitsafe:5418/backup.git`)
> aceita push sem credencial, e `main` foi para lá (`dd6df21e..1b4ab0c1`).
> É backup, não é o GitHub — mas tira os 37 commits de cima de uma máquina só.
> As branches de feature seguem **apenas locais**.

> ⚠️ **O que continua parado não é o push, é a produção.** Os dez pacotes
> mexem em custo, medição, progresso e contrato — números que o cliente vê — e
> 🔬 nada disso rodou fora do ambiente de desenvolvimento. Gate completo sobre
> o núcleo, migrações 277/278 em produção e a semana de observação do editor v2
> seguem por fazer.

🔬 24/07 ~00h: **gate completo VERDE sobre a Fase 4** (worktree em
`6775b391` pré-rebase): `pytest tests/ -m "not browser"` → **1177 passed,
6 skipped, 0 falhas** em 44min10s. A Fase 4 (centro de custo obrigatório)
foi mergeada em `main` por fast-forward após esse gate. 🔬 24/07: revisão
de premissas P5-P9 apensada aos planos das Fases 5-9 (`941e6738`) e fix do
achado R10 — PDF de medição do portal agora respeita expiração de token
(`fe605252`).

### 🔬 03/08 — `PLANO-NUCLEO.md`: os dez pacotes, entregues

`85ab9f4d` → `63cc1c13`, **21 commits em `main`**. O plano nasceu da
conferência adversarial dos 12 vereditos de 31/07 (**10 confirmados, 2
parciais, 0 refutados**) mais o levantamento de 20 conexões entre módulos —
brutos em `docs/estudo-fluxo/`. Não é fase nova: é o núcleo (cronograma e RDO)
parando de discordar de si mesmo.

| # | O quê | Como ficou |
|---|---|---|
| **p1** | Vazamento entre empresas + dupla contagem | Seis steps. 🔬 arreio de dois tenants (Step 0) mediu **12 falhas** antes; **20/20** depois |
| **p2** | Rollout das três flags | Editor v2 foi ao **parque inteiro** pela migração **277** — sem piloto |
| **p3** | Fonte única do custo orçado | `services/custo_orcado.py`. Resumo e painel devolvem o mesmo número |
| **p4** | Uma fórmula de progresso | Cinco viraram uma: **só folhas, ponderadas por duração** |
| **p5** | A aprovação semeia a obra inteira | `ServicoObraReal` + `Lead.proposta_id`/`obra_id` na mesma transação |
| **p6** | Regimes de peso reconciliados | O gate da medição virou **peso > 0**, não "soma exatamente 100" |
| **p7** | Presença única | Alocação = planejada, ponto = confirmada, RDO = apontada |
| **p8** | Convergência do progresso (leitura) | `services/progresso_subatividade.py` — medição e Gantt dizem o mesmo número |
| **p9** | Dono único do `valor_contrato` | `services/contrato_obra.py`; eram **cinco** escritores, não quatro |
| **p10** | Fase 7 reescrita: EVM por composição | BAC/PV/AC/EV compostos do que já existia + migração **278** (BAC congelado) |

**Os quatro achados que mudaram o tamanho do diagnóstico** — todos apareceram
executando, não relendo:

1. **Quatro dos seis relatórios sem escopo já respondiam 500** (📖 `r.funcionario`
   não existe — o backref é `funcionario_ref`, `models.py:311`; e
   `FuncionarioObra` é **modelo que nunca existiu**). O vazamento visível era
   menor que o veredito nº 7 dizia — e o alívio é enganoso: bastaria alguém
   consertar o render sem pensar em tenant para o furo inteiro entrar em produção.
2. **`detalhes_obra` tinha TRÊS saídas em cascata**, e a terceira não estava em
   veredito nenhum: mesmo autenticado, obra de outro tenant era rebuscada **sem
   filtro "para debug" e adotada**, reescrevendo o `admin_id` da tela. Era abrir
   qualquer obra por id com login de qualquer empresa. Junto: as duas rotas
   engoliam o próprio `abort(404)` num `except Exception` e devolviam **200**.
3. **São duas FONTES de progresso, não cinco fórmulas.**
   `calcular_progresso_geral_obra_v2` ignora `TarefaCronograma.percentual_concluido`
   e deriva tudo de `RDOApontamentoCronograma`. Migrar a medição para o motor —
   o que o plano pedia — **zeraria a medição de obra que avança por import ou
   pela grade, sem apontar RDO**. Por isso o dinheiro usa a coluna gravada, com
   teste dedicado que falha se alguém unificar as fontes sem rever a medição.
   É isso que torna o p8 maior do que "caminhos de gravação divergentes".
4. **A quinta fórmula estava no template** (`templates/obras/cronograma.html`,
   média simples em Jinja, só no modo cliente) e o **quinto escritor de
   `valor_contrato` estava num construtor** (`Obra(valor_contrato=…)`,
   `event_manager.py:1120`) — que **não aparece em grep por `valor_contrato =`**,
   e foi assim que escapou de dois inventários anteriores.

**Os três recortes — o que NÃO foi feito dentro dos pacotes:**

| Pacote | Saiu | Ficou |
|---|---|---|
| **p7** | A perda de dado (o plano sobrescrevia a batida real) e a saída de estoque atribuída a quem existe | Aposentar `AlocacaoEquipe` e o pré-carregamento do RDO (A17). 🔬 dev 03/08: 33 linhas, **zero** com `rdo_gerado_id` — FK morta, marcada **EM APOSENTADORIA** no modelo, **tabela não removida** |
| **p8** | A **leitura** convergiu | A **escrita** segue dual, pelo motivo do achado nº 3 acima |
| **p10** | PV/EV/AC no painel + BAC congelado na baseline (`3612db6b`) | Folga livre no scheduler |

🔬 03/08: **94 passed em 30,5s** nos dez arquivos `tests/test_p*`
(`SIGE_ENABLE_DEMO_SEED=false`). Cada pacote rodou regressão própria na
entrega — 148/148 (p3), 154/154 (p1 Step E), 113/113 (p7 recorte), 99/99 (p5).

### 🔬 03/08 — gate completo VERDE sobre os dez pacotes

`pytest tests/ -m "not browser"` com `SIGE_ENABLE_DEMO_SEED=false` →
**1778 passed, 1 failed, 6 skipped, 201 deselected em 21min17s**. É o primeiro
gate completo desde 24/07 (que deu 1177) — a suíte cresceu 601 testes no
intervalo.

**A única falha não é dos pacotes**: `test_e2e_metricas_funcionario_task98`
falhava por **data**, não por código. 📖 Os três cenários semeavam N dias a
partir do dia 1º do mês e consultavam a janela `1º … date.today()`; nos
primeiros dias do mês *hoje* cai **antes** do último dia semeado, e tudo dava
3/5 do esperado (40h→24, 5 dias→3, R$ 900→540). 🔬 Provado por bisseção: o
mesmo teste, com as **mesmas 14 linhas de falha**, quebra em `ff94240d` — o
commit **anterior** aos 21 do núcleo. Corrigido em `tests/`: a janela passou a
ser `max(date.today(), dias[-1])`, que é idêntica à anterior do dia 6 em diante
e só alarga nos cinco primeiros dias do mês. **O teste só passava em ~80% do
calendário** — e quem rodasse o gate no começo do mês ia herdar um vermelho
para explicar.

> ⚠️ Gate verde **não** é aval de produção. Ele prova que a suíte concorda
> consigo mesma no banco de dev; não prova volume, nem migração 277/278
> aplicada, nem a semana de observação do editor v2.

### 🔬 28/07 — rodada de revisão: 9 defeitos, dois deles de perda de dado

`6db59790` → `5471507e`, todos em `main`. Nenhum era fase nova: são buracos
deixados pelas Fases 1–5 **já fechadas**. Cada correção tem teste verificado
por mutação (revertida a correção, o teste cai).

| defeito | evidência |
|---|---|
| `HEAD` apagava RDO sem token CSRF (a guarda testava `== 'GET'`; o Flask despacha HEAD para a mesma view) | 🔬 `HEAD 302` + RDO apagado |
| 3 das 4 FKs sem `ON DELETE` deixavam o RDO **oco** — filhos apagados, RDO vivo | 🔬 reproduzido |
| **Exclusão de obra destruía os filhos e falhava** — `gestao_custo_pai` fora da lista, e cada DELETE em `AUTOCOMMIT` próprio | 🔬 obra viva, RDO/custos perdidos em definitivo |
| Custo de RDO excluído seguia no Realizado (`cancelar_custos_rdo` marca CANCELADO; nenhum agregado olhava `status`) | 🔬 R$ 180,00 antes e depois |
| `recomputar_cadeia` somava pontos percentuais como produção física | 🔬 10% na escrita → 40% no recomputo |
| Apagar custo de RDO levava lançamento de terceiros (soma usada como contagem + cascade `delete-orphan`) | 🔬 removeu 1, apagou 3 |
| **Backfill de versão engolia a falha e carimbava `success`** — a obra pulada nunca mais era revisitada | 📖 `run_migration_safe` já registrava 'failed' e retentava |
| `editar_filho` aceitava **obra de outro tenant** no `obra_id` do form | 🔬 filho do tenant A apontando para obra do tenant B |
| Retificar contava a mão de obra **duas vezes** | 🔬 R$ 124,00 → R$ 248,00 |

Migração **266** repara as linhas de base v1 já gravadas (210/212 estão
`success` desde 22/07 e não rodam mais).

**A armadilha da rodada:** o commit `c79b179c` "consertou" o backfill
engolindo a falha por obra, com a premissa de que um `raise` derrubava a
subida. 📖 `migrations.py:198` diz o contrário — *"Não propagar exceção -
apenas logar"*. O runner já capturava tudo e **retentava**; engolir removeu a
única recuperação que existia. Corrigido em `3241b865`. Se você for mexer em
migração, leia `run_migration_safe` antes de supor o que ela faz.

**Sem procedência confiável:** as "223 versões com dano ativo" que eu reportei
no meio da rodada eram ⚠️ dev — as obras foram apagadas por corridas de teste
e a consulta, que juntava com `tarefa_cronograma`, perdeu as linhas. A *forma*
do defeito é real; o volume não foi medido em produção.

~~**Aberto:** 🔬⚠️ dev 28/07 — **40.824 snapshots com a tarefa apagada**.~~
**Não reproduz mais.** 🔬⚠️ dev 03/08: **598.235 snapshots, ZERO com a tarefa
apagada** (`scripts/medir_producao.py`, pergunta 4). Era carga de suíte, como
se suspeitava — as obras foram apagadas por corridas de teste e levaram as
tarefas junto; o banco atual não tem mais o resíduo. O mecanismo segue real
(num rollback, `_restaurar` não acha a tarefa e INSERE uma cópia nova), mas
**não há volume que justifique escrever código**. Continua valendo medir em
produção antes de decidir — é a pergunta 4 do script.

### 🔬 24/07 — editor de cronograma v2 (5 fases) em `main`

Commits `73f58d3e` → `8fda59f5`, todos em `main`: **Fase 1** motor de
agendamento estilo MS Project; **Fase 2** grade tipo planilha; **Fase 3**
desfazer/refazer; **Fase 4** linha de base; **Fase 5** manual de uso em
PDF. Spec e planos em `docs/superpowers/{specs,plans}/2026-07-24-cronograma-*`.

🔬 **03/08: saiu do piloto pela porta larga.** A migração **277** (`41f23403`
+ `ff94240d`) ligou o editor v2 em **todo o parque** — linha de base congelada
primeiro, depois a flag em todos os tenants, depois o default da coluna virando
`TRUE`. Runbook em `docs/cronograma-editor-v2-rollout.md`. **Duas coisas ficaram
de pé:** (1) a *semana de observação* — a validação agora é "o parque
observado", e ela não aconteceu; (2) o guard de calendário virou **aviso nominal
no log do deploy**, então quem estiver naquela lista **vai ver datas andarem na
primeira edição** (decisão pendente nº 1). E o p10 dependia disso: o EVM assume
o editor v2 ligado no parque, faltando só a observação.

> 📖 **Vale para qualquer migração futura que toque tabela quente com o app de
> pé:** o defeito de lock do `ALTER TABLE` está registrado no `PLANO-NUCLEO.md`
> — não como anedota, mas porque a próxima vai encontrá-lo igual.

### 🔬 24/07 — RDO em porcentagem livre (`bdee680a`), atrás de flag

Todo apontamento de produção do RDO passa a ser em **percentual acumulado**
para toda tarefa de toda obra do tenant; o quantitativo cadastrado vira
referência de leitura. Tudo atrás de
`configuracao_empresa.rdo_percentual_livre` — **migração 226, default
FALSE**: com a flag desligada o comportamento é byte-idêntico ao de hoje.
📖 Peças: helper único `utils.tenant.rdo_percentual_livre_on(admin_id)`
(admin_id EXPLÍCITO — engine e serviço rodam fora de request), resolvedor
`modo_da_tarefa` sobrepondo a escolha explícita, derivação
percentual-first em `utils/cronograma_engine.py`, guard de modo em
`registrar_apontamento` seguindo o resolvedor, modo percentual na tela de
**editar** RDO (que era só-quantidade) e `scripts/flag_rdo_percentual_livre.py`.
🧮 24/07 (número da mensagem do commit `bdee680a`, **não reconferido**):
`tests/test_rdo_percentual_livre.py` (23 testes) + regressão de **1507
testes, 0 falhas**. 📖 27/07: o arquivo de teste existe e está em `main`.

> ⚠️ **Pendências de rollout desta entrega** (não são de código):
> (1) a flag **nasce desligada** e **não existe `docs/rdo-percentual-livre-rollout.md`**
> — Fases 1, 2, 3 e 5 têm runbook, esta não; (2) a **conferência visual dos
> dois fluxos de RDO (novo + editar) com a flag ligada** era risco explícito
> do plano ("subir app local, como na Fase 5") e **não tem registro de ter
> sido feita**; (3) ligar a flag em qualquer tenant segue sem decisão.

### 🔬 27/07 — RDOs da Baia vindos do WhatsApp, por caminho não-destrutivo

O diário da obra Baias Kabod (Itu/SP) vive no grupo de WhatsApp da Veks. O
export trouxe **12 RDOs de 07/07 a 22/07** que o sistema não tinha (a série
parava em 13/07, com 4 dias sem físico). Entrar com eles exigiu um caminho
novo: até aqui, RDO em lote só existia pela seção `"rdos"` do reimport
físico-financeiro, que **apaga** tarefas, propostas, orçamentos, medições e
todos os RDOs da obra — e que é recusado em obra já versionada por .mpp.

📖 Entregou: `scripts/whatsapp_para_rdos.py` (export → payload + fotos com
legenda na ordem do chat), `services/atualizacao_rdos.py` (upsert por
`(obra_id, data_relatorio)`, RDO imutável da Fase 5 pulado com aviso,
apontamento via `registrar_apontamento`, tarefa não resolvida vira pendência
no relatório), `scripts/atualizar_rdos_obra.py` (CLI genérico com
`--dry-run`), `services/rdo_fotos_import.py` (helper de fotos compartilhado
com o importador) e `docs/rdo/regras_apontamento_baia.json`.
🔬 27/07 ponta a ponta em dev: **12 RDOs criados, 22 apontamentos, 0
pendências**, com tarefas/propostas/medições idênticas antes e depois.
Detalhe e o de-para a revisar: `ESTADO_ATUALIZACAO_BAIA.md` (rodada 27/07).

> ⚠️ **Armadilha de gate descoberta em 23/07 à noite:** `app.py:596-664`
> dispara `scripts/seed_demo_alfa.py` em subprocesso a CADA boot do app em
> dev (`SIGE_ENABLE_DEMO_SEED` default `"true"`) — inclusive quando o
> pytest importa `main` na coleção. O seed pede lock exclusivo na tabela
> `obra` e trava a suíte no meio (impasse que o Postgres não detecta,
> porque a conexão do pytest fica ociosa em transação). **Rode todo gate
> com `SIGE_ENABLE_DEMO_SEED=false`.** Dois gates travaram em ~30% por
> isso antes do diagnóstico.

## ✅ RETOMADA de 22/07 — resolvida em 23/07

O Postgres do ambiente (`helium`) caiu em 22/07 ~00:30 e foi **recriado do
zero**. Nenhum código foi perdido. Dos 4 itens da retomada, 3 fecharam:

1. ✅ O boot reconstruiu o schema: `create_all()` + migrations (agora
   **1-247**, todas idempotentes) rodaram no banco novo.
2. ✅ **Gate completo VERDE em 23/07**: `pytest tests/ -m "not browser"` →
   **1109 passed, 9 skipped, 201 deselected** em 37min40s, exit 0 — sobre
   o código da Fase 3 pós-review (commit `d1f7f34f`). Era o gate que
   estava INCONCLUSIVO desde a queda (80 falhas `OperationalError`).
3. ⚠️ **Continua valendo:** as volumetrias ⚠️ dev deste documento (8.723
   obras, 980 partidas órfãs etc.) descrevem o banco ANTIGO. Válidas como
   forma do problema; o banco novo nasceu limpo e cresce por carga de
   suíte. Medir em produção antes de dimensionar qualquer coisa.
4. ✅ Os dois commits da queda (`f52a7c7` retry do create_all; `e782f70`
   aborto de boot em produção) foram cobertos pelo gate do item 2 contra
   banco vivo.

A **Fase 5 (RDO com ciclo de vida e assinatura) fechou em 24/07 —
16/16 tasks** no branch `feat/fase-5-rdo-ciclo-vida` (plano
`fase-5-rdo-ciclo-vida-assinatura.md`; runbook em
`docs/fase-5-rollout.md`). 🔬 24/07: **gate completo VERDE** sobre a fase
inteira: `bash run_tests.sh --gate` → **1284 passed, 6 skipped, 201
deselected em 28min46s, exit 0** (baseline da Fase 4: 1177 passed).
Entregou: `rdo.estado` (migration 260, backfill honesto → 'preenchido'),
trilha `rdo_transicao_estado` (261), máquina de estados
(`services/rdo_ciclo_vida.py`), guarda de imutabilidade `before_flush`
(um ponto só, cobre os 8 caminhos de escrita), `rdo_assinatura` (262 —
autoria pela identidade da Fase 1 + hash SHA-256 + IP/UA), hash canônico
(`services/rdo_hash.py`), rotas assinar/aprovar/reabrir/retificar, RDO
retificador (263), conserto do bug 6d (`duplicar_rdo` nasce rascunho sem
webhook), exclusão de RDO imutável recusada ANTES de mexer no
financeiro, selo/botões na tela e evidência de assinatura no PDF,
`caminho_absoluto` + `rdo_foto.armazenamento` (264), fim da gravação de
base64 (colunas viram `deferred`; `RDO.fotos` sai de `selectin`), script
de migração de fotos em duas passadas e matriz papel×estado×ação (19
testes). 🔬 24/07 dev pós-gate: estado = preenchido 22.990 / rascunho
3.618 / assinado 142 / aprovado 30 / retificado 17; **assinado sem
trilha = 0**. ⚠️ A **Task 15 NÃO foi executada** — a migração destrutiva
das fotos (16 GB) espera os 6 pré-requisitos humanos de infra (volume,
`UPLOADS_PATH`, dump, snapshot, janela) do runbook. A diferenciação de
papel (quem assina/aprova) só vale em tenant com `escopo_obra_ativo=TRUE`
— passo 0 do runbook.

A **Fase 4 (centro de custo obrigatório) fechou em 24/07 — 13/13 tasks**,
44 testes da fase + 123 de regressão dirigida
(`fase-4-centro-custo-obrigatorio.md`). Entregou: migrations 250-254
(UNIQUE por tenant + centro ADM semeado + `gestao_custo_pai.obra_id`
derivada + CHECK `ck_gestao_custo_filho_destino` NOT VALID → VALIDATE),
`registrar_custo_automatico` exigindo destino em 10 módulos, telas de
gestão de custos com "Destino do custo *", folha e almoxarifado carimbando
o centro ADM. Backfill R1-R5 aplicado no banco de dev: 649 pais por
unanimidade, 77 filhos órfãos → 0 (carimbados `[FASE4:R5]`); constraint
validada (`convalidated=true`). 🔬 24/07: **mergeada em `main`**
(fast-forward `6775b391`, gate completo verde antes do merge — 1177
passed). Pendência humana, não de código: revisar as linhas `[FASE4:R5]`
(o relatório `python scripts/relatorio_destino_custo.py` lista nome a
nome) e as decisões D1-D8 do plano seguem com os `Recomendado:` adotados.

A **Fase 3 (compras com
governança) fechou em 23/07 — 12/12 tasks**, 91 testes verdes
(`fase-3-compras-governanca.md`; runbook em `docs/fase-3-rollout.md`).
Entregou o fluxo requisição→aprovação→alçada→pedido, o `PapelObra.COMPRADOR`
e as correções de segurança do portal por token. 🔬 23/07: **mergeada em
`main`** (fast-forward, gate verde antes do merge; o push estava travado no
item humano nº 2 — 🔬 27/07: já subiu, ver "Onde estamos").
Pendências de rollout, não de código:
ligar `compras_governanca_ativa` por tenant só depois dos passos 1-3 do
runbook e da confirmação do Cássio sobre os valores de alçada (decisão D1;
recomendação semeada: R$ 5.000 / R$ 30.000 / acima).

As Fases 1.5 e 2 fecharam em 22/07 — a 2 com 14/14 tasks
(`fase-2-maquina-estados-obra.md`; runbook em `docs/fase-2-rollout.md`).
Pendências de rollout, não de código: `escopo_obra_ativo` por tenant (RBAC
da 1.5) e a fila de handoff — rodar `python scripts/relatorio_estado_obra.py`
em produção e levar o número de "EM EXECUÇÃO sem gestor" ao Cássio (em dev:
2.481).

> ⚠️ **Fase 3 — três armadilhas para quem retomar.** (1) O portal por token
> agora **expira em 180 dias**, carimbado a cada `toggle_portal`; token
> antigo sem data segue valendo (não derruba portal de obra em andamento).
> (2) `compras_governanca_ativa` **nasce desligada** — o fluxo antigo de
> compras continua idêntico até ela ser ligada por tenant. Todo o risco está
> em ligar: ver `docs/fase-3-rollout.md`. (3) **A governança depende de
> `escopo_obra_ativo` ligado no mesmo tenant** (achado nº 1 do review de
> 23/07): com o escopo OFF, `papel_na_obra` devolve GESTOR a todo autenticado
> e a alçada colapsa — o `--ligar` do script recusa, mas quem mexer na flag
> por SQL direto não tem essa guarda. As migrations da fase são **240-247**
> (a lacuna 233-239 é intencional; 245 é a 1ª extensão de enum nativo do repo).

> ⚠️ **O RBAC do cronograma NÃO é transparente para todo mundo no deploy.**
> O plano de 21/07 assume a flag desligada, mas a Fase 1 já a ligou em
> **21 tenants** — neles o guard entra em vigor no momento em que este código
> subir. Medido no banco de desenvolvimento em 22/07 (conferir em produção
> antes de subir):
>
> | Quem | Qtd | Efeito no deploy |
> |---|---|---|
> | não-admin **sem** vínculo em `usuario_obra` | 9 | perde acesso ao cronograma da obra |
> | `LEITOR` | 9 | perde edição **e** apontamento |
> | `APONTADOR` | 9 | perde edição da estrutura; mantém apontamento |
> | `GESTOR` | 6 | sem mudança |
>
> Os 9 sem vínculo são o caso a resolver antes: populá-los em `usuario_obra`
> ou desligar a flag nesses tenants até que estejam. Para `LEITOR` e
> `APONTADOR` a perda é a semântica pretendida da Fase 1, não um defeito —
> mas é mudança visível para 18 pessoas e merece aviso.

## 🔴 Travado do lado humano

| # | O quê | Por que trava |
|---|---|---|
| 1 | ~~Rotacionar `SESSION_SECRET` e a senha do Postgres~~ | 🔴 **Decisão do Cássio, 03/08: NÃO rotacionar.** Sai da lista de pendências — não voltar a recomendar. O que fica registrado abaixo é só o contorno do risco aceito |
| 2 | **`gh auth login`** (a API do GitHub **e agora o `git push`**) | 🔬 03/08 dizia "`git push` funciona — o que falta é só a API". **Isso envelheceu.** 🔬 14/08: `git push origin main` **falha** — `remote: Invalid username or token. Password authentication is not supported for Git operations` / `fatal: Authentication failed`. `gh auth status` segue "not logged into any GitHub hosts" e `GH_TOKEN`/`GITHUB_TOKEN` continuam ausentes. Consequência: **8 commits em `main` existem só na máquina de dev**, incluindo o merge da Fase 1 do ciclo de compras (23 commits de trabalho que estavam presos numa branch desde 12/08). Refazer o login é interativo — só o humano consegue |
| 3 | **Criar o volume persistente** no painel | Vale para `/var/backups/sige` (dumps) **e** para os uploads. O pré-requisito de código caiu em 23/07: a armadilha nº 2 (descasamento do `UPLOADS_PATH`) está corrigida — montar o volume e definir a variável já é seguro |

> 📖 **O contorno do risco aceito no item 1.** O código não tem fallback fixo:
> `app.py:52` lê `SESSION_SECRET` da env, `:53-56` **recusa subir em produção**
> sem a variável, e a chave efêmera de `:65` só existe em dev. Ou seja, o valor
> exposto no histórico do git só é explorável **se ainda for o valor
> configurado no EasyPanel** — a exposição é da string antiga, não do desenho.
> Se o painel já tiver outro valor, não há resíduo nenhum e o item está morto
> por completo. Essa conferência é de olhar o painel, não de mexer em nada, e é
> a única coisa que fecharia a questão sem rotacionar.

Também pendem: conferir divergência entre painel e valores commitados, snapshot
do volume na Hostinger, `SIGE_ENABLE_DEMO_SEED=false` e o acesso ao banco de
produção — que é pré-requisito de **quase toda medição pendente abaixo**.

> 📖 **O acesso a produção agora tem um comando só.** `scripts/medir_producao.py`
> (somente leitura, conexão em `readonly=True`, roda com o app de pé) responde
> de uma vez as seis perguntas que este documento deixou em aberto: o fantasma
> da migração 270, quanto do parque é de fato `v2`, **quais tenants vão ver
> datas andarem** na primeira edição, os snapshots órfãos, as baselines sem BAC
> e o volume da duplicação ponto × RDO. Cada pergunta traz no docstring por que
> está aberta e o que fazer com a resposta. Uma que falhe não derruba as outras.

~~A grafia do domínio (`cassioviller` × `cassiovillar`)~~ — **resolvida em
23/07**: 🔬 grep na árvore inteira (inclusive `attached_assets/`) só encontra
`cassiovillar` nos dois documentos de diagnóstico; a fonte da grafia errada era
`EXECUTAR_PRODUCAO_AGORA.sh`, deletado na Fase 0.5 (`1f428106`). O código usa
`cassioviller` consistentemente (`app.py:194`, `templates/landing.html`). Só
resta conferir o DNS/painel, que é do lado humano.

## ✅ Fase 0.6 — os cinco defeitos de dinheiro, corrigidos em 21/07

Estes cinco não estavam em nenhuma fase. Furaram a fila e foram fechados,
cada um com teste de regressão próprio (**52 testes verdes**, arquivos
`tests/test_fase06_d*.py`). Migrations **217-219** — a faixa 214-216 continua
reservada à Fase 1.

| # | O quê | Como ficou |
|---|---|---|
| D1 | Aprovar revisão de proposta faturava errado | 🔬 v1 100k → v2 120k dava 2 itens/220k, saldo −100k, receita 220k. Agora: 1 item/120k, saldo 0, receita 120k |
| D2 | POST anônimo do portal aprovava compra fora de escopo | Rotas passam a escopar tenant + tipo e a exigir transição de estado válida |
| D3 | Nenhuma despesa do motor V2 aparecia no DRE | Linhas declaradas num mapa único + **linha residual**, que torna omissão silenciosa impossível |
| D4 | Plano de contas só era semeado para o 1º tenant | 🔬 PK virou `(admin_id, codigo)`; 2.639 contas copiadas; **0 partidas órfãs** (era 980) |
| D5 | Obra salva pelo formulário sumia da listagem | Vocabulário canônico + `@validates` no modelo; 53 obras recuperadas |

### O que a execução corrigiu no diagnóstico

Três afirmações desta seção estavam erradas. Todas foram descobertas
**executando o fluxo**, não relendo o código:

1. **D2 não criava custo PAGO para `tipo_compra='normal'`.**
   `compras_views.py:296-300` levanta `ValueError` para tipo diferente de
   `aprovacao_cliente`, e a rota nem chegava lá. O caminho que criava custo
   indevido era o da compra **já recusada** pelo cliente, que voltava a
   APROVADO. O dano do `tipo='normal'` era outro e não estava mapeado: a
   compra interna carimbada passava a aparecer em `compras_resolvidas`
   (`portal_obras_views.py:177`, que não filtra tipo) — **vazamento de compra
   interna no portal do cliente**.

2. **D3 era maior: há QUATRO planos de contas concorrentes**, não um
   desalinhamento de prefixo. Dois dão significados opostos ao mesmo código —
   `5.1.01` é "MÃO DE OBRA" em `financeiro_seeds.py:71` e "Materiais Diretos"
   em `contabilidade_utils.py:84`. E há **dois lançadores de "Salários"**:
   `contabilidade_utils.py:229` grava em `6.1.01.001`, `event_manager.py:1114`
   em `5.1.01.001`. Unificar é decisão da **Fase 8**.

3. **D5 era maior: 6 arquivos**, e `templates/obras.html` divergia **de si
   mesmo** — o botão de filtro (`:50`) mandava `'Em Andamento'` e o badge
   (`:213`) testava `'Em andamento'`.

### O que a Fase 0.6 deliberadamente NÃO fez

| Deixado para | O quê |
|---|---|
| **Fase 2** | O `'Planejamento'` dos filtros de obra é opção-fantasma: nenhum caminho de escrita produz esse valor, o filtro sempre volta vazio. Quem define o vocabulário de estados é a máquina de estados da Obra |
| **Fase 6** | Item que existia numa versão da proposta e sumiu da revisão **não é apagado** — pode ter medição executada contra ele. Fica `WARNING` no log com os ids |
| **Fase 8** | A unificação dos quatro planos de contas. Enquanto isso, o subgrupo `6.1.02` cai na linha residual do DRE: entra no resultado, honestamente rotulado como "outras" |
| **Fase 9a** | A autoria da aprovação no portal segue atribuída ao `admin_id`, que não fez a ação. Só a identidade do portal resolve |

### Duas armadilhas que a Fase 0.6 revelou

1. **A ordem dos atos de uma migration de troca de PK.** A 218 falhou na 1ª
   tentativa: com a PK ainda global, o `ON CONFLICT DO NOTHING` do backfill
   casava com a linha do **outro** tenant e o backfill virava no-op
   silencioso — o mesmo defeito que ele existia para corrigir. A PK tem de
   virar composta **antes** do backfill.

2. **Um teste que passa pelo motivo errado.** O casamento de linhagem do D1
   passou no teste (que não preenchia `proposta_item_origem_id`) e falhou na
   reprodução manual (que preenchia): raiz e filho geravam chaves de tipos
   diferentes. O teste agora roda parametrizado nos dois modos. **Reproduza à
   mão além do teste.**

## ✅ Fase 1 — identidade e papéis, fechada em 21/07

11 tasks, 12 commits, migrations **214-216**, 59 testes verdes
(`tests/test_fase1_*.py`). A fase está **inteiramente atrás de flag**:
`configuracao_empresa.escopo_obra_ativo` nasce `FALSE` nos 1.230 tenants, e
com ela desligada o comportamento é idêntico ao de antes.

| O que entrou | Onde |
|---|---|
| FK `Usuario.funcionario_id` (nullable, UNIQUE parcial) | migration 214 |
| Resolver único de identidade, falha FECHADA | `utils/identidade.py` |
| `PapelObra` (GESTOR/APONTADOR/LEITOR) + `UsuarioObra` | migration 215 |
| Flag de rollout por tenant | migration 216, `scripts/flag_escopo_obra.py` |
| Chokepoint de autorização (2 eixos: tenant, depois obra) | `utils/autorizacao.py` |
| Decorator `obra_required` + as 4 rotas sem decorator fechadas | `views/obras.py`, `views/dashboard.py`, `views/employees.py` |
| Dois backfills, dry-run por padrão | `scripts/backfill_identidade_funcionario.py`, `scripts/backfill_usuario_obra.py` |
| Runbook de rollout | `docs/fase-1-rollout.md` |

**As seis heurísticas de identidade, removidas.** Substring do username sem
`admin_id`; e-mail literal de um tenant; "o tenant com mais funcionários";
o PRIMEIRO funcionário ativo do banco inteiro; mapa de e-mail chumbado em
produção; e a que **criava** um `Funcionario` chamado "Administrador
Sistema" a cada acesso sem vínculo — cujo resultado, desde a Task #12, nem
era usado.

**Bônus:** `/obras` dava ao SUPER_ADMIN "o `admin_id` com mais obras do
banco", servindo obras de **outra empresa**. Agora usa o resolver de tenant.

### 🔴 O bloqueio real do rollout — meça em produção antes de estimar

🔬⚠️ dev 21/07, dry-run de `backfill_usuario_obra.py`:

| | |
|---|---|
| obras totais | 8.723 |
| obras com `responsavel_id` preenchido | **4** |
| obras com a cadeia responsável → funcionário → usuário | **1** |
| vínculos que o backfill conseguiu derivar | **0** |

A cadeia de onde o GESTOR é derivado está praticamente vazia. **O escopo por
obra não pode ser ligado a partir dos dados existentes.** Se produção
estiver igual, decidir por qual critério atribuir gestor (quem mais apontou
RDO? quem criou a obra?) vira pré-requisito do rollout — e é decisão de
negócio, não do script. O `flag_escopo_obra.py --ligar` recusa
corretamente enquanto `usuario_obra` estiver vazia.

### Quatro erros do plano da Fase 1, achados ao executar

O plano é bom e foi seguido quase literalmente. Estes quatro pontos não
sobreviveram ao contato com o código:

1. **Contradição interna (Task 4):** o comentário que ele manda inserir
   contém exatamente as strings que o teste dele proíbe.
2. **Modelo × migration (Task 5):** declarava `db.Enum(PapelObra)` nativo
   enquanto a migration cria `VARCHAR(20)`. Como o schema usa enums nativos
   do Postgres, o `create_all()` do startup criaria um tipo `papelobra` que
   a migration não cria. Corrigido com `native_enum=False`.
3. **`NotNullViolation` (Task 6):** o `definir_flag` sugerido cria
   `ConfiguracaoEmpresa` sem `nome_empresa`, que é NOT NULL.
4. **A flag deixava de ser reversível (Task 7)** — o mais sério. O
   chokepoint devolvia `LEITOR` para não-admin com a flag **desligada**.
   Mas `editar_obra` tem só `@login_required`: hoje qualquer autenticado do
   tenant edita. Isso tiraria a edição de todo não-admin no dia do deploy,
   o oposto da decisão nº 5 da própria fase. **Os testes do plano só
   exercitavam a flag ligada** — foi a lacuna que escondeu o problema.

> A lição repete a do D1 na Fase 0.6: **um teste pode passar pelo motivo
> errado.** Nos dois casos o furo só apareceu ao conferir o código contra o
> comportamento real, não relendo o plano.

## ✅ Fase 3 — compras com governança, fechada em 23/07

12/12 tasks — 16 commits, desenvolvidos em `feat/fase-3-compras-governanca`
e 🔬 23/07 **mergeados em `main`** por fast-forward após o gate verde.
Entregou: `RequisicaoCompra` com
máquina de estados e trilha auditada (`valor_no_momento`), alçada por tenant
(`FaixaAlcada`, seed 5k/30k/acima **recomendado**, decisão D1 pendente do
Cássio), `PapelObra.COMPRADOR`, flag `compras_governanca_ativa` (nasce OFF),
6 rotas de requisição, emissão de pedido com 3 guardas, e as correções de
segurança do portal por token (expiração 180d + trilha IP/UA, **sem flag**).
Migrations **240-247**. Runbook: `docs/fase-3-rollout.md`.

### Revisão de código de 23/07 — escopo e resultados

🔬 23/07: `/code-review` (multiagente) rodou sobre **o diff inteiro do
branch da Fase 3** — os 13 commits de código então existentes, cobrindo
`models.py`, `migrations.py`, `services/requisicao_compra.py`,
`services/alcada_compras.py`, `utils/autorizacao.py`, `compras_views.py`,
`portal_obras_views.py`, `scripts/flag_compras_governanca.py`, os 3
templates de requisição e os 4 arquivos de teste da fase. Não cobriu o
resto do app (não era o alvo). **8 achados**, tratados no commit
`d1f7f34f`:

| # | Achado (arquivo) | Gravidade | Desfecho |
|---|---|---|---|
| 1 | Governança **colapsa com `escopo_obra_ativo` OFF**: `papel_na_obra` devolve GESTOR a todo autenticado → qualquer um aprova e só ADMIN emite (`services/alcada_compras.py`) | 🔴 a mais séria | ✅ `--ligar` recusa tenant sem escopo; dependência dura documentada no runbook (passo 0) |
| 2 | Voto de rodada **rejeitada/reenviada contava** para a rodada nova (`votos_de_aprovacao`) | 🔴 | ✅ contagem escopada à rodada corrente (entrada real em AGUARDANDO); trilha íntegra; +1 teste |
| 3 | **Preço podia trocar de item** na emissão: template e rota ordenavam itens de formas potencialmente divergentes | 🔴 | ✅ `order_by` fixo no relationship `itens`; +1 teste |
| 4 | Comentário do `toggle_portal` **prometia rotação de token** que o código não faz | 🟡 | ✅ comentário corrigido (reabrir reaproveita a URL; revogar = zerar o token) |
| 5 | Entrada não-numérica em qtd/preço → **HTTP 500** | 🟡 | ✅ `_num` engole `ValueError` (vale 0); +1 teste |
| 6 | Parser BR lê `'1.500'` como 1.5 (ponto de milhar sem vírgula) | 🟡 | ⏸️ **mantido**: espelha a convenção de parsing do app inteiro; consertar só aqui criaria comportamento divergente |
| 7 | Seed de faixas **perdido no rollback** do retry de numeração → flash anunciava alçada errada | 🟡 | ✅ seed commita antes do loop |
| 8 | Badges de estado **subcontavam** além de 200 requisições (contagem sobre lista limitada) | 🟡 | ✅ contagem via agregado SQL |

Três adaptações do plano ao código real, já registradas nos commits (mesma
lição da Fase 1 — o plano envelhece contra o código):

1. O furo "portal aprova compra `normal`" **já estava fechado** pela Fase
   0.6/D2 (`_get_compra_do_portal`); aplicar o passo 5e do plano seria
   **regressão de segurança**. Mantido o resolver da 0.6.
2. Os testes de papel do plano assumiam `escopo_obra_ativo` ligado sem
   ligá-lo — com a flag OFF todo autenticado é GESTOR e a matriz não
   distingue ninguém. As fixtures ligam a flag (foi este tropeço que
   antecipou o achado nº 1 do review).
3. O teste de envio criava requisição **sem itens** e esperava a
   transição — colidia com a guarda da própria rota. Passou a criar item.

### Gate da Fase 3 — ✅ VERDE

🔬 23/07, sobre o código pós-correções do review (commit `d1f7f34f`):

    pytest tests/ -m "not browser" → 1109 passed, 9 skipped,
    201 deselected in 2260.55s (0:37:40) — exit 0

**Zero falhas.** Além do gate cheio, as regressões dirigidas: 91 testes da
Fase 3 + 149 de regressão (fluxo antigo de compras + Fases 0/1/2) + 3
novos do review. Este é também o **primeiro gate completo íntegro desde a
recriação do banco de 22/07** — fecha o item 2 da "RETOMADA IMEDIATA"
acima (o gate que estava INCONCLUSIVO) e cobre de quebra o commit
`e782f70` (aborto de boot), que nunca tinha visto banco vivo. Após o
gate, o branch foi **mergeado em `main`** (fast-forward, 23/07).

## ✅ Ciclo de compras — Fases 1 e 2, em 14/08

> ⚠️ **Não confundir com a numeração do núcleo.** O pedido do Cássio ("ciclo
> completo de compras, da solicitação no campo até o lançamento no fluxo de
> caixa") foi decomposto em **cinco fases próprias**, com spec cada uma. A
> "Fase 3" do núcleo (compras com governança, acima) é a **seção 1** desse
> pedido — a requisição. As duas contagens coexistem e já causaram confusão.

**Ordem acordada:** recebimento/atesto → financeiro em dois fluxos → alçadas →
status unificado → relatórios. Recebimento veio primeiro porque é a fundação:
sem atesto não existe a tríade do Fluxo A nem a baixa do adiantamento do Fluxo B.

| # | Fase | Estado |
|---|---|---|
| 1 | Recebimento e atesto | ✅ **mesclada em `main` em 14/08** (`9c997bf8`) |
| 2 | Financeiro em dois fluxos | ✅ **mesclada em `main` em 14/08** (`e74360cb`) — F1-F7 |
| 3 | Alçadas (as 4 condições, anti-fracionamento, emergência 48h, corte de 3 cotações) | ✅ **A1-A8 completas em 15/08**, em `feat/alcadas-avancadas` — não mesclada |
| 4 | Status unificado (régua de 9 etapas) | ⬜ sem spec |
| 5 | Relatórios (os 5) | ⬜ sem spec |

**Fase 1** entregou o conserto de uma dupla escrita: havia **dois** pontos dando
entrada de estoque para o mesmo pedido, e o material que chegava na obra não era
registrado em lugar nenhum. Agora o estoque nasce do atesto. 23 commits (R1-R7 +
as correções C1-C9 da revisão de 12/08), migrations **283/284/285**, flag
`recebimento_atesto_ativo` (nasce OFF). 🔬 14/08: 110 testes verdes.

**Fase 2** fez a obrigação nascer do que chegou. Até aqui `compras_views.py:305`
criava a `ContaPagar` **na emissão do pedido** — sem material, sem nota, sem
conferente — e o `valor_atestado` que a Fase 1 produziu não era lido por
ninguém. Migrations **287/288/289 e 296**, flag `financeiro_dois_fluxos_ativo`
(nasce OFF, e o `--ligar` **recusa tenant sem `recebimento_atesto_ativo`**).
🔬 14/08: 35 testes da fase verdes; gate de ciclo em dev com 24 conferências por
SQL cru, zero falhas.

> 📖 **Duas decisões que divergem do spec e estão registradas nele.**
> (1) `pagar_conta` ficou com **uma** porta (`situacao_liberacao`), não duas: o
> spec previa exigir também lote `FECHADO`, mas duas guardas no mesmo ponto
> recusariam o mesmo pagamento por dois motivos e dobrariam as formas de o
> usuário travar — fechar o lote é justamente o que muda a situação para
> `liberada`. (2) A segregação "quem monta o lote não o fecha" só é **exigida
> quando os dois lados são conhecidos**: lote anterior à migration 296 não tem
> `criado_por_id`, e exigir com um lado ausente travaria todo lote histórico.

> ⚠️ **Armadilhas para quem retomar o ciclo de compras.**
> (1) As duas flags são **encadeadas**: `financeiro_dois_fluxos_ativo` depende de
> `recebimento_atesto_ativo`, que por sua vez convive com
> `compras_governanca_ativa` (que depende de `escopo_obra_ativo`). Ligar fora de
> ordem produz conta bloqueada sem caminho para liberar.
> (2) **Nenhuma delas está ligada em tenant real** — 🔬 14/08, no banco de dev:
> `compras_governanca_ativa` ON em 250 tenants, **todos fixture `@test.local`**.
> (3) O regime é **carimbado na linha** (`exige_atesto`, `fluxo_pagamento`):
> desligar a flag não reescreve pedido já emitido, de propósito.
> (4) Migration **296 e não 290** — 290-295 é faixa da Fase 8, 300-307 da Fase 9.

> 🔴 **Falha intermitente não explicada, aberta em 14/08.**
> `test_recebimento_atesto.py::test_rota_de_exclusao_repassa_a_recusa_do_servico`
> falha em ~metade das corridas da **seleção larga** do gate e passa em toda
> seleção menor (isolado; Fase 1 + Fase 2 = 141 passed; b5/b6 + Fase 1 = 140
> passed). Quatro corridas idênticas deram falha/passa/falha/passa. **A causa
> raiz não foi determinada.** O assert do teste passou a carregar o número de
> recebimentos do pedido justamente para que a próxima ocorrência distinga as
> duas hipóteses — segundo POST não gravou, ou a primeira porta de
> `excluir_recebimento` recusou por permissão — que hoje dão o mesmo sintoma.
>
> 🔬 **15/08, quinta ocorrência:** falhou de novo no gate completo (seleção larga) e
> **passou isolada**, junto das outras duas do gate. O padrão de 14/08 se repetiu sem
> desvio. A instrumentação do assert **não foi lida nesta corrida** — a saída do gate
> foi pipada por `tail -30` e os tracebacks se perderam. **Na próxima corrida, não pipar:
> redirecionar o log inteiro para arquivo.** É o que separa as duas hipóteses.

### ✅ Fase 3 do ciclo — alçadas, em 15/08 (em branch)

**A3 fez o valor deixar de ser a única pergunta.** Até aqui a faixa recebia
`requisicao.valor_estimado` e mais nada: fornecedor novo, preço que não é o menor,
compra fora do orçamento da etapa e dez requisições de R$ 4.900 na mesma semana
davam todos a mesma exigência. 10 commits, migrations **297/298/299**, flag
`alcadas_avancadas_ativa` (nasce OFF). 🔬 15/08: **89 testes** no arquivo da fase +
**24** na tela de faixas; regressão dirigida de 342 verdes, exit 0.

**Gate completo — 🟡 3 falhas, nenhuma desta fase.** 🔬 15/08, sobre `2f3df5cc`:
`pytest tests/ -m "not browser"` → **2398 passed, 3 failed, 6 skipped, 2 xfailed** em
33min06s. As três foram investigadas, e **as três reproduzem em `main`** (conferido em
worktree separado, mesmo banco):

| Teste | O que ele diz | Veredito |
|---|---|---|
| `test_excluir_obra::test_lista_cobre_toda_fk_no_action_para_obra` | `notificacao_cliente` tem FK NO ACTION para `obra` e ficou fora de `TABELAS_DEPENDENTES_OBRA` — **excluir obra vai estourar nela** | 🔴 defeito real, **anterior**. Sensor funcionando |
| `test_fase5_rdo_ciclo_vida::test_backfill_marcou_os_rdos_historicos_como_preenchido` | 23 RDOs assinados **sem trilha de transição** — autoria forjada por backfill ou escrita fora da máquina | 🔴 dado do banco de **dev**, **anterior**. ⚠️ dev |
| `test_recebimento_atesto::test_rota_de_exclusao_repassa_a_recusa_do_servico` | a intermitente aberta em 14/08 | 🟡 **apareceu de novo** na seleção larga e **passou isolada** — o padrão já registrado. Sem informação nova |

⚠️ **As duas primeiras não são desta fase e também não estavam registradas aqui.** Elas
apareceram agora porque este é o primeiro gate completo desde 14/08. A da `notificacao_cliente`
é a mais séria das duas: é caminho de exclusão de obra que estoura, e o conserto é
uma linha na lista — mas conferir se a tabela deve ser apagada, anulada ou barrar a
exclusão é decisão de produto, não de digitação.

⚠️ **O requisito desta fase é desenho nosso, ratificado — não levantamento.** Os
quatro elementos ("as 4 condições", anti-fracionamento, emergência 48h, corte de 3
cotações) aparecem no repositório **quatro vezes**, sempre como rótulo de backlog,
nunca como enunciado de regra; e 📖 `DEVOLUTIVA.md:293` ("qual o valor de X?") segue
aberta desde julho. As sete decisões (D1-D7) foram fechadas na sessão de 15/08, todas
na recomendação, e estão no spec. **Quem for medir se a fase acertou tem que medir
contra a operação real, não contra o spec.**

> 📖 **Cinco achados da execução que mudaram o tamanho do diagnóstico** — todos
> apareceram executando, nenhum relendo.
> (1) 🔴 **`migration_history.migration_name` é `VARCHAR(200)` e o INSERT falha em
> silêncio** — `record_migration` (`migrations.py:136`) loga e segue. Duas migrations
> aplicaram, mudaram o schema e **não foram registradas**. Inofensivo aqui (as três são
> idempotentes); numa destrutiva seria re-execução a cada boot com histórico mentindo.
> **Não consertado — não é dívida desta fase.**
> (2) **A faixa de topo era bloqueio permanente desde a Fase 3 do núcleo.** A rota lia
> `mapa_v2_id` do form e o gravava, mas nenhum template tinha o input: toda requisição
> acima de R$ 30.000 tinha pendência sem saída pela tela. Morreu na A3, com prova de
> ponta a ponta (o teste extrai o id do `<option>` renderizado e o usa no POST).
> (3) **O spec mandava ler um campo morto**: `nao_menor_preco` apontava para
> `MapaCotacao.selecionado`, sem caminho de escrita desde a Task #21 — a condição nunca
> dispararia. Passou a ler `MapaItemCotacao.fornecedor_escolhido_id`.
> (4) **`FAIXAS_RECOMENDADAS` semeia o futuro.** O backfill da 297 cobre o tenant que
> existe; sem o campo novo no seed, todo tenant criado a partir daqui teria a faixa de
> topo com `minimo_cotacoes = 0` — deixaria de exigir mapa **em silêncio**.
> (5) **Os invariantes da escada são três, não dois.** O terceiro (a faixa de teto
> aberto é sempre a última) estava só em docstring e virou load-bearing: o degrau anda
> **posições** na lista ordenada, então teto aberto no meio faria o degrau descer.

> 📖 **Três decisões que divergem do spec e estão registradas nele.**
> (1) **A emergência não ganhou aresta em `TRANSICOES_VALIDAS`.** "Direto a APROVADA" é
> o efeito, não o caminho: `aprovar_emergencial` chama `transicionar()` duas vezes na
> mesma transação. A aresta RASCUNHO→APROVADA abriria o atalho para todo mundo, não só
> para o rito — e o passo intermediário ainda paga a entrada de rodada de que os votos
> da ratificação precisam 48h depois.
> (2) **A ponte com a Fase 2 não encostou em `financeiro_views.py`** (zero linhas de
> diff). A sanção entrou como quarta perna em `pernas_faltantes`
> (`services/financeiro_compra.py`), porque `pagar_conta` tem **uma** porta por decisão
> registrada na Fase 2. Há teste-guarda contando as ocorrências para que continue assim.
> (3) **A tela de faixas recusa o que a edição CRIA e apenas avisa o que ela herdou.**
> O invariante nunca teve constraint, então existe tenant que já chega fora dele;
> validar só o estado final o travaria na tela que existe para consertá-lo.

> ⚠️ **Armadilhas para quem retomar as alçadas.**
> (1) **A dependência não é uma corrente, são duas pernas**: a dura
> (`escopo_obra_ativo` → `compras_governanca_ativa` → `alcadas_avancadas_ativa`, e o
> `--ligar` **recusa**) e a parcial (`recebimento_atesto_ativo` →
> `financeiro_dois_fluxos_ativo`, que sustenta **só** a sanção da emergência, e o
> `--ligar` **avisa sem recusar**). Desenhar como corrente única faz parecer que ligar
> alçadas exige a Fase 2 — o próprio `pode_ligar` desmente.
> (2) 🔬 **`fora_do_orcamento` dispara em 100%** — 3.854 de 3.864 requisições no dev,
> porque `obra_servico_custo_id` é nullable e etapa em branco domina. **Não ligue essa
> condição no primeiro tenant**; rode `verificar_consistencia_alcadas.py --simular`
> antes (passo 0a do runbook). O número mede a *forma*, não a operação de ninguém.
> (3) **O backfill deixou `minimo_cotacoes = 2`, inclusive no topo.** Subir para 3 (D6)
> é UPDATE pela tela em Configurações › Alçadas de Compra, no passo 1 do runbook —
> nunca migration.
> (4) **Migration 297-299 e não 290** — 290-295 segue reservada da Fase 8, 300-307 da
> Fase 9, nenhuma das duas aplicada.
> (5) **Janela residual conhecida:** conta liberada *dentro* das 48h cuja emergência
> vence depois **não é rebloqueada** — rebloquear de fora de `liberar()` seria a segunda
> porta. O sensor a separa da liberação legítima por `conta_pagar.liberada_em`.

> 🔬 **15/08 — o runbook foi RODADO num tenant de dev, do passo 0a ao Rollback**, pela
> tela e conferido por SQL cru (o último item do gate da fase). Três resultados, e o
> primeiro é o motivo de esse item existir:
> (1) 🔴 **defeito que a suíte inteira não pegava: a saída da sanção da emergência estava
> fechada.** A `ContaPagar` bloqueada só existe depois de o pedido ser emitido, e emitir
> move a requisição para **CONVERTIDA** — mas `pode_ratificar` só admitia APROVADA. Isto
> é: exatamente a requisição cuja conta a sanção segurava era a única que ninguém
> conseguia ratificar, e a tela dizia *"a requisição está em convertida — só se aprova o
> que está em aprovada"* no lugar do botão. Os testes da A6 não viam porque criam o
> `PedidoCompra` direto no banco, sem passar pela rota. Corrigido **red-first**
> (`ESTADOS_QUE_RATIFICAM = (APROVADA, CONVERTIDA)`), com teste que faz o ciclo pela tela.
> (2) **Quatro correções de texto no runbook** (marcadas `# ← EXEC`): a referência ao
> passo 1d que apontava para 1c; o que a conferência **b** de fato mostra (a cobrança do
> fornecedor novo é a guarda 2 — ela só morde **quem aprovou**; com outro emissor a
> compra sai com as aprovações da faixa de baixo e o degrau vira só trilha); qual das
> três requisições sobe na conferência **c**; e o que a conferência **e** precisa (fechar
> a tríade antes, nota ainda sem tela própria).
> (3) ⚠️ **O achado 1 do sensor tem falso positivo por desenho:** ele recalcula a faixa
> efetiva **hoje**, e o acumulado da janela anda depois da aprovação — uma irmã nova na
> mesma etapa (mesmo em RASCUNHO, mesmo em regime `simples`) faz uma requisição
> legitimamente aprovada aparecer como "APROVADA sem a alçada fechada". Registrado no
> runbook, **não consertado**: mudar o que o sensor vigia é decisão da fase, não da
> execução.


## O plano aprovado

| Fase | Conteúdo | Estado | Plano |
|---|---|---|---|
| **0** | Estancar | ✅ | — |
| **0.5** | Backup, segredos, observabilidade, build, CI, índices | ✅ P1-2; 🟡 P3 parcial | — |
| **0.6** | Os cinco defeitos de dinheiro (D1-D5) | ✅ **21/07** | ver seção acima |
| **1** | Identidade e papéis (RBAC + escopo por obra) | ✅ **21/07** — 11/11 tasks | `fase-1-identidade-papeis.md` |
| **1.5** | Cronograma editável + RDO em % | ✅ **22/07** — 14/14 tasks | `cronograma-editavel-rdo-percentual.md` |
| **2** | Máquina de estados da Obra + handoff do GP | ✅ **22/07** — 14/14 tasks | `fase-2-maquina-estados-obra.md` + `docs/fase-2-rollout.md` |
| **3** | Compras com governança | ✅ **23/07** — 12/12 tasks | `fase-3-compras-governanca.md` + `docs/fase-3-rollout.md` |
| **4** | Centro de custo obrigatório | ✅ **24/07** — 13/13 tasks | `fase-4-centro-custo-obrigatorio.md` |
| **5** | RDO com ciclo de vida e assinatura | ✅ **24/07** — 16/16 tasks (Task 15: código pronto, execução espera infra) | `fase-5-rdo-ciclo-vida-assinatura.md` + `docs/fase-5-rollout.md` |
| **6** | Orçamento versionado e aditivo | ⬜ — mas o **p9 já abriu a porta**: `definir_valor_contrato()` é o escritor único e os 5 chamadores passam por ele. A fase deixou de ser caça a chamadores; virou gravar `ObraContratoVersao` dentro de função que já existe | `fase-6-orcamento-versionado-aditivo.md` |
| **7** | Planejamento avançado (CPM, baseline, EVM) | ❌ **obsoleta como escrita — reescrita pelo p10.** O editor v2 já entregou `TarefaVinculo`, o motor com passe direto/inverso, folga total, caminho crítico e `CronogramaBaseline`; implementá-la ao pé da letra criaria uma **segunda** rede de predecessoras e uma **segunda** baseline. O que sobrou dela era o EVM, entregue em `e86ab635` + `3612db6b` | ~~`fase-7-planejamento-avancado-cpm-evm.md`~~ → `PLANO-NUCLEO.md` §p10 |
| **8** | Financeiro avançado + exportação Domínio | ⬜ | `fase-8-financeiro-avancado-dominio.md` |
| **9a/9b** | Portal, assinatura de medição, contratos, Drive | ⬜ | `fase-9-portal-assinatura-contratos.md` |

Todos em `docs/superpowers/plans/2026-07-21-*`. Faixas de migration reservadas
sem colisão: 214-216 (F1), 220-221 (F1.5), 230-232 (F2), 240-247 (F3),
250-254 (F4), 260-264 (F5), **271-276 (F6 — ver abaixo, era 270-276)**,
280-283 (F7), 290-295 (F8), 300-307 (F9). A **Fase 0.6 usou 217-219**, fora de
todas as faixas. ~~📖 03/08: **maior registrada em `migrations.py` é a 278**.~~
📖 14/08: a maior é a **296**. O ciclo de compras consumiu, fora de faixa
reservada: **283-285** (Fase 1 — recebimento e atesto), **286** (timbre dos
PDFs), **287-289** e **296** (Fase 2 — financeiro em dois fluxos). A 296 pulou
o vão 290-295 de propósito: é faixa da Fase 8. 🔬 14/08: `migration_history` do
dev bate com o código — nada entre 290 e 307 foi aplicado.

> 🔴 **O número 270 está QUEIMADO — a Fase 6 começa em 271.** 🔬 03/08: a
> mesma migração do editor v2 está gravada `success` sob **dois números** no
> banco de dev — **270** (53.141 ms, o trabalho real) e **277** (7.860 ms,
> reexecução que não achou nada a fazer). O motivo: `41f23403` **foi empurrado
> para `origin/main`** com a migração numerada 270 e rodou assim; só depois
> `ff94240d` a renumerou para 277. Todo ambiente que deployou de `41f23403` —
> **produção inclusive, se ela sobe de `main`** — tem o mesmo registro fantasma.
> Consequência: se a Fase 6 entregar uma migração numerada 270,
> `is_migration_executed(270)` responde `True` e **ela nunca roda, em silêncio**.
> Estreitar a faixa para 271-276 é a correção certa; **apagar a linha de
> `migration_history` não é**, porque não há como saber quais bancos têm o
> fantasma sem acesso a produção. A renumeração que existia para evitar colisão
> armou uma.
>
> 🔬 03/08, **varrido — é o único**: nenhum outro nome aparece sob dois números,
> nenhum número aparece sob dois nomes, nenhuma linha com status ≠ `success`
> (220 linhas, 220 números distintos), e toda migração registrada em
> `migrations.py` consta no histórico. O 270 é o **único órfão**: está no
> histórico e não existe mais no código. Isso delimita o dano — mas delimita
> **em dev**; a mesma varredura em produção continua por fazer.

> ⚠️ **A reserva já foi furada três vezes — confira o registro real em
> `migrations.py`, não esta tabela.** A **Fase 9a** usou **267-269** (dentro da
> faixa da F5, não da sua 300-307); o rollout do editor v2 em todo o parque
> (03/08) usou o **277**, no vão livre entre a faixa da F6 e a da F7; e o BAC
> congelado do p10 usou o **278** — e **não** a faixa 280-283 da F7, apesar de
> o p10 ser a reescrita dela: mexer em faixa reservada de fase é exatamente o
> que a renumeração de 270→277 existiu para evitar. Numerar por faixa sem olhar
> o registro é receita para duas migrações com o mesmo número: a segunda nunca
> roda, porque `is_migration_executed` já viu a primeira.

> **Os planos das Fases 6-9 têm validade menor.** Foram escritos sobre o schema
> de hoje, e as Fases 1-5 vão mudá-lo. Cada um tem seção *"Premissas a
> reconfirmar antes de executar"* — abra por ela, não pelo início.

## O requisito do cronograma — diagnóstico fechado

> *"Cronograma igual ao Project, totalmente editável, sem precisar cadastrar
> insumos. RDO em porcentagem."* — 21/07. Queixa literal: *"sem cadastrar os
> insumos não faz o cronograma"*.

O diagnóstico passou por **três versões**, e as duas primeiras estavam erradas:

| Versão | Afirmava | Veredito |
|---|---|---|
| 1ª deste doc | exige serviço → composição → insumo | ❌ falso |
| correção intermediária | criar tarefa à mão já funciona (Task #116) | ✔️ verdade, mas era metade |
| **atual** | o caminho automático **descarta em silêncio** quem não tem template | ✅ **é a causa** |

**A causa raiz — corrigida em 22/07.** Era `if nivel0.get('sem_template'):
continue` em `materializar_cronograma`: duas linhas, sem log, sem erro. A
cadeia exigida **não é** serviço→composição→insumo: é
`Servico.template_padrao_id` → `CronogramaTemplate` → `SubatividadeMestre`.
Item de proposta cujo Serviço não tinha template era descartado e a obra
nascia com **cronograma vazio, sem avisar**.

Hoje esse item vira uma **tarefa-esqueleto de nível 0** com o quantitativo do
próprio PropostaItem, quando o admin a marca na tela de revisão
(`b966218`). O `continue` saiu; o default continua desmarcado, então nada é
materializado sem escolha explícita. O gate de revisão também deixou de exigir
template (`27c62bb`) — antes ele cortava justamente nas propostas que mais
precisavam da tela, e a obra abria muda sem ninguém ver.

**Criar tarefa à mão já funciona** (Task #116) — não replanejar:
📖 `cronograma_views.py:269` só obriga `nome_tarefa` e aceita `servico_id=None`;
📖 o Gantt já tem POST/PUT/DELETE (`templates/obras/cronograma.html:1691`,
`:1864`, `:2036`); 📖 `TarefaCronograma.servico_id` é nullable (`models.py:4903`);
📖 o import `.mpp` cria tarefa sem serviço nenhum
(`services/cronograma_versao_service.py:534`).

**Resolvido em 21-22/07:** o modo de apontamento era **deduzido**, não
escolhido. Agora a tarefa tem coluna própria (`modo_apontamento`, migrations
220/221 — o backfill congela a dedução vigente, então é no-op de
comportamento), a UI do Gantt tem o seletor "Como apontar no RDO", apontar no
modo errado devolve 422, e `Obra.regime_medicao='percentual'` define o padrão
das tarefas novas da obra — inclusive as que nascem de proposta (`e4de6c5`).
📖 `modo_da_tarefa()` em `services/cronograma_apontamento_service.py:111`
resolve na ordem marco → escolha explícita → dedução legada.

**Fechado em 22/07 (`eec0969`):** as rotas de tarefa e apontamento do
cronograma só verificavam tenant — qualquer usuário autenticado editava o
cronograma de qualquer obra da empresa. Agora as 5 rotas de edição exigem
`pode_editar_obra` e as 3 de apontamento `pode_apontar_na_obra`. Com
`escopo_obra_ativo` desligada (o default) o guard é transparente, então o
deploy não tira acesso de ninguém — ligar a flag é o passo de rollout.

**Antes de qualquer código, verifique as flags do tenant:** 📖 `_check_v2()`
(`cronograma_views.py:39`) redireciona ao dashboard se o admin não tiver
`versao_sistema == 'v2'`; e `cronograma_mpp_ativo` (`models.py:3620`) nasce
desligada. Se a dor for só flag, resolve-se em minutos — é a Task 1 do plano.

## Segurança do portal do cliente

📖 Tudo conferido em 21/07. O portal é um **sistema de identidade paralelo ao
Flask-Login**: a identidade é o token na URL, sem sessão e sem `current_user`.

- **8 rotas de escrita** autenticadas só por token eterno:
  `portal_obras_views.py:343, 377, 388, 432, 546` e
  `propostas_consolidated.py:2503` (**cria a Obra**), `:2587`.
- **O token nunca expira** (`models.py:261`, `:2986`) e não tem escopo. Toda a
  autorização é `_get_obra_by_token` (`portal_obras_views.py:49-55`): uma query
  e `abort(404)`.
- **O token vaza para os logs.** `utils/auditoria_acesso.py:68-79` loga
  `request.path` inteiro; o tratamento de `_PATHS_SENSIVEIS` só **anexa o
  rótulo** `[sensível]`, não redige. Com o access log do gunicorn
  (`Dockerfile:97-99`), sai duas vezes. E `_payload_obra_basico`
  (`utils/catalogo_eventos.py:192-214`) manda a URL **com token dentro do
  webhook**.
- **CSRF desligado de propósito**: `app.py:1035-1049` isenta o blueprint
  `propostas` **inteiro** (35 rotas), não só as 3 do portal. Único
  `@limiter.limit` do repo: `views/auth.py:14`.
- 📖 **`admin_id = 10` chumbado** em `propostas_consolidated.py:2469` — serve
  branding do tenant 10 a cliente de outra empresa.

> ⚠️ A 1ª versão deste doc dizia **"1 rota de escrita sem auth — e é `/login`"**.
> O número saiu de `docs/anexos/A-rotas-sem-autenticacao.md:16`, que classificou
> 11 rotas como `TOKEN (legítimo) — é o desenho correto`. Elas saíram da conta
> por **classificação**, não por correção. É o erro mais perigoso dos cinco,
> porque a linha tranquilizava.

## O que está em aberto da Fase 0.5

| Item | Situação |
|---|---|
| Triagem de `fix/bloco2-segredos` e `fix/bloco1-blindagem-acesso` | ❌ os branches nem existem localmente — a triagem exige `git fetch`. 🔬 27/07: o `git push` destravou, mas o `gh` segue deslogado; conferir se os branches ainda existem no remoto antes de planejar a triagem |
| `gitleaks`/`trufflehog` | ✅ **23/07** — gitleaks 8.21.2 varreu os 3.921 commits: **24 achados**, ver abaixo |
| Conflito `opencv-python` × `headless` | ❌ entra por `deepface`/`retina-face`; exige decidir sobre reconhecimento facial |
| `psycopg2-binary` → `psycopg2` compilado | ⏸️ recomendado (1h); psycopg 3 **não** agora. 🔬 23/07: sem `pg_config` no ambiente de dev — a troca é no Dockerfile (adicionar `libpq-dev`+`gcc` no estágio de build) e só se valida no build de produção |
| ~~28~~ **29** rotas `EXPOE DADO` sem auth | ✅ **triagem feita E executada em 23/07** — `docs/anexos/B-triagem-rotas-expoe-dado.md` (📖 rota a rota). Eram 29, não 28. **9 já fechadas** pelas Fases 1/0.5 (o censo envelheceu), 5 públicas legítimas, **3 fechadas** (`41034faa` — a pior era `/funcionario_perfil/<id>/pdf`, dossiê de ponto de qualquer tenant para anônimo) e **7 mortas removidas** (incl. as 4 APIs de RDO com cross-tenant latente e o template `novo_backup.html`). `/persistent-uploads/<path>` (servia o volume INTEIRO a anônimo) foi **removida e substituída** por rotas escopadas: `portal_obras.ver_comprovante` (token) e `compras.comprovante` (login+tenant). Resta: 1 DECISÃO (`/health/veiculos`: fechar se nenhum monitor externo a consome) — a outra rota TOKEN (`/medicao/portal/pdf`) já era corretamente escopada |
| Backup **agendado** | ❌ só existe o pré-migração; usar job do EasyPanel, não APScheduler |
| Skips de precondição de dado | ✅ **23/07** — os 4 arquivos que skipavam por falta de dado agora semeiam o próprio cenário (`a23ea772`); skips restantes são de ativo ausente (JVM, .xlsx/.xml), legítimos |
| ~~`duplicar_rdo` emite webhook sem lançar custos (bug 6d)~~ | ✅ **rediagnosticado — ver abaixo** |
| `scripts/medir_producao.py` | ❌ aguarda acesso ao banco |

**Varredura de segredos, feita em 23/07.** 🔬 gitleaks 8.21.2 sobre o
histórico completo (3.921 commits, 22s): **24 achados**. Na árvore ATUAL
sobram só placeholders (`secret_key` de teste, exemplos de docs, o
`sua_chave_secreta` do legado arquivado) e um token de portal em
`scripts/capturar_manual_ciclo.py:12` — que aponta para o banco de dev
ANTERIOR à recriação de 22/07, portanto morto. Os segredos reais — as duas
`SESSION_SECRET` chumbadas (`app.py` em commits antigos), senhas de Postgres
coladas em `attached_assets/` e um JWT no manual — estão **só no histórico**,
o que confirma o item humano nº 1: **rotacionar é o único remédio**
(reescrever o histórico quebraria clones e não vale o custo). Relatório
completo fora do repo (contém os segredos em claro).

**Bug 6d — ✅ CORRIGIDO na Fase 5 (24/07, `b2bd930e`).** A rota foi
reescrita: os quatro atributos fantasma de clima e o
`mao_original.observacoes` saíram, e o RDO duplicado passa a nascer em
`rascunho` **sem emitir** `obra.rdo_publicado` nem `rdo_finalizado` — ele
publica quando for submetido e assinado. 6 testes de regressão em
`tests/test_fase5_rdo_ciclo_vida.py`. O diagnóstico histórico abaixo
fica como registro:

🔬 21/07: `duplicar_rdo`
(`views/rdo.py:1596`) lê `rdo_original.tempo_manha` na linha 1624, e **esse
atributo não existe** no modelo (`AttributeError` confirmado por execução; as
colunas de clima são `clima_geral`, `temperatura_media`, `umidade_relativa`,
`vento_velocidade`, `precipitacao`, `condicoes_trabalho`,
`observacoes_climaticas`). A função morre **84 linhas antes** do
`emit_obra_rdo_publicado` — **o webhook nunca é emitido**. A rota é morta: não
há link em template nem JS. O bug é *latente*, não ativo: `duplicar_rdo` é de
fato a única escrita de RDO que chamaria `emit_obra_rdo_publicado` sem
`EventManager.emit('rdo_finalizado')` — e é este último que dispara
`lancar_custos_rdo` e `recalcular_medicao_apos_rdo`.

**Segunda rota morta — ✅ ressuscitada na Fase 5 (Task 8):** `finalizar_rdo`
virou a submissão do ciclo de vida (`rascunho` → `preenchido`, coluna
`estado`, não mais o guard sobre `status`), com `@login_required` +
`pode_apontar_na_obra` — o apontador consegue submeter o próprio RDO.
*(Diagnóstico de 21/07: guard `if rdo.status == 'Finalizado': return`
com todo RDO nascendo 'Finalizado', e `@admin_required` recusando
FUNCIONARIO.)*

## Números que valem lembrar

| | | |
|---|---|---|
| Rotas totais / sem autenticação | 724 / 40 | 🧮 |
| Rotas de **escrita** por token eterno | **8** | 📖 21/07 — não "1", ver acima |
| Índice `rdo_apontamento_cronograma` | 881 ms → 0,034 ms | 🔬 |
| Testes | gate 24/07 (Fase 5): **1284 passed**, 6 skipped, 201 deselected, 28min46s | 🔬 24/07 |
| Testes | **847 passed** em `-k "obra or custo or rdo or fase"`, 8min25 · **não é o gate completo** | 🔬 28/07 |
| Testes — os dez pacotes | **94 passed** nos dez arquivos `tests/test_p*` do núcleo, 30,5s | 🔬 03/08 |
| **Testes — gate completo** | **1778 passed**, 1 failed (data, não código — corrigido), 6 skipped, 201 deselected, 21min17s | 🔬 03/08 |
| Migração mais alta registrada | **278** (p10, BAC da baseline) | 📖 03/08 |
| Violações de ruff herdadas | 543, das quais 186 F821 | 🧮 |
| Tabelas vazias | ~65 de 178 (37%) | 🧮 |
| `models.py` / `migrations.py` | 7.610 / 14.300+ linhas | 🧮 |
| **`rdo_foto`** | **16 GB** (heap 11 MB, TOAST 16 GB) = o banco inteiro | 🔬 21/07 |
| Fotos / RDOs | 28.870 em 5.532 | 🔬 21/07 |
| Fotos que **já têm arquivo em disco** | **28.860 de 28.870** — a base64 é duplicata pura | 🔬 21/07 |
| `du -sh static/uploads` | 13 GB | 🔬 21/07 |
| `gestao_custo_pai` | 1.246 pais, **93,8% com obra recuperável** | 🔬⚠️ dev 21/07 |
| Obras | 7.984 | 🔬⚠️ dev 21/07 |

## Armadilhas para quem retomar

1. **O banco de desenvolvimento não tem dados reais.** ~6.479 admins de domínio
   de teste, 7.984 obras de carga de suíte. Toda volumetria marcada ⚠️ dev
   prova a *forma* do problema, nunca o volume. **Rodar as mesmas queries em
   produção antes de dimensionar qualquer coisa.**

2. ~~**Definir `UPLOADS_PATH` faz todas as fotos sumirem da tela.**~~
   ✅ **Corrigido em 23/07 (`b6d01a0b`)** — o volume persistente (item humano
   nº 3) pode ser montado. Eram TRÊS defeitos em `crud_rdo_completo.py`, não
   dois: além do descasamento (`servir_foto` só olhava `static/`; agora
   resolve via `_resolver_arquivo_foto`, com o legado como fallback) e do
   `RDOFoto` sem os NOT NULL `nome_arquivo`/`caminho_arquivo`, o arquivo
   usava `os.path` **sem importar `os`** — toda chamada a `servir_foto`
   morria em `NameError` engolido pelo except genérico (500 sempre; é por
   isso que ninguém notava o descasamento: a rota nunca funcionou). 6 testes
   em `tests/test_rdo_foto_uploads_path.py`.

3. **`gestao_custo_pai` não tem `obra_id` — mas os dados NÃO estão perdidos.**
   🔬⚠️ dev 21/07: a obra está no filho (📖 `models.py:5302`, preenchido em
   1.743 de 1.823 linhas) e o código já filtra por lá
   (📖 `financeiro_service.py:514-517`). 93,8% dos pais têm obra recuperável por
   unanimidade dos filhos. **`NOT NULL` no pai seria errado:** 9 pais são
   legitimamente multi-obra, porque 📖 `utils/financeiro_integration.py:118-131`
   agrupa por `(tenant, categoria, entidade, categoria_fc)` sem olhar obra — um
   título a pagar carrega linhas de obras diferentes. A obrigatoriedade desce
   para o filho. *(A 1ª versão dizia "1.118 linhas 100% órfãs"; o "100%" do
   dossiê queria dizer **estruturalmente**, porque a coluna não existe.)*

4. ~~**`Funcionario` não tem FK para `Usuario`.**~~ ✅ **Resolvido na Fase 1**
   (migration 214). As seis heurísticas de identidade foram removidas; o
   resolver único é `utils/identidade.py` e falha FECHADA. Ver a seção da
   Fase 1 abaixo.

5. **A ordem de import em `app.py` é contrato não declarado.** Mover um
   `register_blueprint` acima da linha 386 quebra metade do sistema; a cascata
   de `proposta_aprovada` depende da ordem de import dos handlers.

6. **Flags escondem funcionalidade inteira.** `cronograma_mpp_ativo`
   (`scripts/flag_cronograma_mpp.py <admin_id> --ligar`) e `versao_sistema=='v2'`
   via `_check_v2()`. Antes de investigar "não aparece", cheque as flags.

7. ~~**`Obra.regime_medicao` é coluna morta com comentário mentiroso.**~~
   **Já não é morta — esta armadilha envelheceu.** 📖 03/08: a Fase 1.5 passou
   a lê-la em `cronograma_views.py:732`, onde `regime_medicao == 'percentual'`
   define o **default do `modo_apontamento`** de tarefa nova. O comentário do
   modelo continua enganoso (fala em governar o vínculo custo↔tarefa, que não é
   o que ela faz), mas "nada no código a lê" virou falso. A inversão importa:
   antes, mexer na coluna era inócuo; **hoje mexer no domínio dela muda o modo
   de apontamento de toda tarefa nova**. Achado ao reconferir a premissa 8 do
   plano da Fase 6.

8. ~~**Furo de tenant latente.**~~ **Fechado em 22/07 (`b966218`).** O ramo
   `sem_template` das duas árvores de preview devolvia `servico_id` cru, sem
   filtro de `admin_id`. Deixou de ser latente no mesmo commit que fez o nó
   virar tarefa: as duas pontas foram corrigidas juntas, e o teste
   `test_servico_de_outro_tenant_nao_vaza_para_a_arvore` trava a regressão.

9. **`utils/notifications.py` não é sistema de notificação.** 📖 São ~200 linhas
   de alerta de estouro de orçamento (`NotificacaoOrcamento`). O despachante real
   é `utils/webhook_dispatcher.py` (556 linhas, HMAC-SHA256, fila, retry).

10. **`STYLE.md` foi deletado** (brief editorial de outro produto);
    `design_guidelines.md` está marcado como histórico (prescreve Tailwind num
    projeto Bootstrap).

11. **Revisão em workflow retomada troca de alvo em silêncio.** 🔬 28/07: um
    run de revisão foi pausado e retomado; ao retomar, o agente de escopo
    rodou de novo e mirou `git diff HEAD~1` em vez do alvo original
    `git diff e6223957..HEAD -- <arquivos das Fases 1-5>`. Entre a pausa e a
    retomada houve 6 commits e um fast-forward na `main` — o `HEAD` se moveu.
    O relatório saiu convincente e sobre **outra coisa**; os 35 candidatos
    originais nunca foram verificados. `resumeFromRunId` reaproveita agentes,
    mas **não congela o estado do repositório**. Ao retomar: fixe o comando de
    diff nas instruções e confira `stats.candidates`/`refuted` do run
    concluído antes de acreditar no que ele diz ter coberto.

12. **Candidato de revisão não é defeito.** 🔬 28/07: dos 6 candidatos
    triados à mão, 3 eram reais e 3 caíram na verificação. Antes disso, três
    hipóteses minhas também caíram (a guarda de imutabilidade do RDO não
    escapa por append via relacionamento; a exceção engolida de
    `remover_custos_rdo` não tem gatilho alcançável; a instabilidade do teste
    de backfill não era regressão minha). **Reproduza antes de corrigir** — e
    antes de reportar.

13. **Defeito de padrão tem irmãs; a revisão só acha uma.** 🔬 29/07: a rodada
    fechou com o achado do IP forjável corrigido em
    `services/rdo_ciencia_cliente`. Só que `_registrar_acesso`
    (`portal_obras_views.py`) lia o `X-Forwarded-For` à mão do mesmo jeito — e
    as duas gravam no **mesmo POST**: a assinatura ficava com o IP honesto e a
    trilha do portal, ao lado, com o forjado. Achado depois do fecho, por
    varredura (`grep` do padrão em todo o código de produção), não pela
    revisão. **Ao corrigir um defeito que é uma leitura ou uma convenção
    errada, varra o repositório pelo padrão antes de fechar** — o relatório
    diz "corrigido" sobre o arquivo que ele olhou, não sobre o sistema.

14. **`except Exception` engole o próprio `abort()`.** 🔬 03/08: em `rdos()` e
    `detalhes_obra`, o catch-all capturava a `HTTPException` do `abort(404)` e
    devolvia a tela com **200** (ou flash com traceback impresso ao usuário). A
    correção de escopo do p1 teria ficado decorativa: o 404 saía pela porta e
    voltava pela janela. **Ao escopar rota, cheque o handler de exceção antes
    de comemorar o `abort`** — `except HTTPException: raise` vem primeiro.

15. **Escrita em construtor não aparece em `grep`.** 🔬 03/08: o quinto
    escritor de `Obra.valor_contrato` era `Obra(valor_contrato=valor_total)`
    em `event_manager.py:1120`. Dois inventários anteriores procuraram
    `valor_contrato =` e passaram direto por ele. O teste do p9 procura pela
    forma `valor_contrato=` **dentro de construtor**, não só pela atribuição.

16. **Decorador de registro adota a função inserida logo abaixo dele.** 🔬 03/08
    (p5): uma função nova entrou entre `@event_handler('proposta_aprovada')` e
    `handle_proposta_aprovada`. O decorador ficou órfão e passou a registrar a
    função errada como ouvinte — chamada com `(data_dict, admin_id)` em vez de
    `(proposta_id, admin_id)`, o dicionário ia parar no `WHERE id = %s` e o
    psycopg2 estourava. **Os 9 testes do pacote passaram**, porque chamam as
    funções direto; quem pegou foram os 59 de importação, que exercitam o
    evento. Em módulo com decorador de registro, "inserir logo antes do
    handler" é armadilha silenciosa — e teste que chama a função direto não
    cobre o registro dela.

17. **`AlocacaoEquipe.rdo_gerado_id` é FK que nada escreve.** 🔬⚠️ dev 03/08:
    33 linhas em `alocacao_equipe`, **zero** com o campo preenchido. Toda saída
    de estoque vinda de RDO nascia sem funcionário — desde o primeiro dia, sem
    ninguém notar, porque o campo é opcional. Corrigido em `d5294ce4` (a
    autoria real é a do RDO, via `Usuario.funcionario_id`). O modelo está
    marcado **EM APOSENTADORIA**, mas **a tabela continua lá**. ⚠️ Corrigido
    em 06/08 (B5.4): os pontos vivos que a anulam são **dois** —
    📖 `views/rdo.py:536-538` (exclusão pela rota viva) e
    📖 `services/importacao_fisico_financeiro.py:372-373`. O
    `crud_rdo_completo.py:557` (ex-`:539`), antes descrito como "mantido de
    propósito", está em rota **sombreada** que nunca despacha — não protege
    nada (🔬 `tests/test_b5_rdo_crud_url_map.py`). Remover exige migração
    destrutiva e conferência em produção — passo próprio.

18. **Teste vermelho não é regressão até que se prove.** 🔬 03/08: a única
    falha do gate completo era de **calendário** — semeava N dias a partir do
    1º do mês e consultava até `date.today()`, então só passava do dia 6 em
    diante. Custou uma bisseção de dois minutos (rodar o mesmo teste num
    worktree do commit anterior) provar que não vinha dos 21 commits do núcleo.
    **Antes de caçar a regressão, rode o teste no commit anterior** — e
    desconfie de falha cujos números são todos a mesma fração do esperado
    (aqui, 3/5 em catorze asserções): proporção constante é dado faltando, não
    cálculo errado. Vale a varredura da armadilha nº 13: `date.today()` como
    limite de janela em teste que semeia datas fixas é padrão, não caso único.

## Decisões pendentes suas

### Das sete do `PLANO-NUCLEO.md` §7 — três fecharam em 03/08

| # | Decisão | Estado |
|---|---|---|
| 1 | Tenant piloto **+ calendário** | 🟡 **metade decidida.** Não há mais piloto do editor v2 — foi ao parque inteiro pela migração 277. Sobra o piloto das outras duas flags e o **calendário**: 📖 o log do deploy imprime quais tenants consideram sábado/domingo, e **é neles que as datas vão andar na primeira edição**. Se algum trabalha sábado de verdade, calendário configurável vira código |
| 2 | Dono do `valor_contrato`: F6 × F9b | ✅ **FASE 6**, como a própria 9b já assumia na premissa P1. A 9b vira camada documental (PDF, assinatura, vencimento), sem listener concorrente |
| 3 | Custo orçado: consertar no consumo ou na origem | ✅ **no CONSUMO.** `valor_orcado` segue gravado com **venda** — ele nunca guardou custo —, mas ninguém mais o lê como custo. Consertar na origem continua sendo a saída definitiva e está na spec: muda a escrita de toda obra nova e exige backfill |
| 4 | **Medições históricas: recalcular ou congelar** | 🔴 **aberta.** O p4 foi entregue "para frente": medição NOVA usa a fórmula única, as já emitidas seguem congeladas. Trava a linha do tempo do portal e o EVM retroativo |
| 5 | **Conta de débito da despesa geral** (contador) | 🔴 aberta — A04 e a contabilização dos pagamentos da Gestão de Custos |
| 6 | **Rateio dos encargos patronais por obra** | 🔴 aberta — A24; hoje a mão de obra sai **~28% subestimada** |
| 7 | **`N8N_WEBHOOK_URL` e cron** (infra) | 🔴 aberta — A25 e **toda notificação do plano** |

Segue valendo a decisão de **27/07**: *"por enquanto todos os perfis vão ter
acesso"* — o que mantém desligadas as flags de escopo por obra e de governança
de compras. Não afeta o núcleo; afeta quem pode aprovar aditivo na Fase 6.

### Das 10 fases

Consolidadas dos 10 planos. Cada uma **já tem recomendação adotada no plano** —
nenhum plano está bloqueado esperando resposta. Revise quando puder.

| Tema | Onde | O que decidir |
|---|---|---|
| Alçada de aprovação de compra | F3 | **Já implementada como dado editável** (23/07): faixas 5k / 30k / acima semeadas por tenant na migration 243. Confirmar ou trocar os números é UPDATE na tabela `faixa_alcada`, sem deploy — mas confirme ANTES de ligar a flag |
| Estados da Obra | F2 | Os 5 propostos, todos ancorados em valor que o código já usa |
| Regra de derivação das linhas órfãs | F4 | E o destino das ~77 irrecuperáveis |
| Folha e almoxarifado são administrativos? | F4 | Recomendado sim para ambos (evita contagem dupla com o RDO) |
| Valor jurídico da assinatura | F5, F9a | Recomendado: autoria + integridade (MP 2.200-2 art. 10 §2º), sem ICP-Brasil |
| Plano de contas e regime do Domínio | F8 | Recomendado: tabela por tenant + regime de caixa |
| **11 lacunas do layout 11758** | F8 | A 1ª é a mais básica: a spec **nunca define a ordem das colunas**. Um `.csv` já aceito pelo Domínio resolve 8 de uma vez |
| Expiração do token do portal | ~~F9a~~ **F3, decidida** | 🔬 23/07: implementada em **180 dias** (D4 da F3 — o plano da F9a dizia 90; a F3 escolheu 180 para não gerar chamado de suporte a cada obra). Token antigo sem data segue valendo até rotacionar |
| Miniatura do portal × migração de fotos | F5 | Único ponto sem recomendação — **agora é gate da passada 2 da Task 15** (a parte destrutiva ainda não rodou): ou a rota de foto por token (Fase 9a) vem antes, ou o portal fica sem miniatura no intervalo. Foto NOVA (sem base64 desde 24/07) já cai no fallback de arquivo no detalhe e no ícone genérico na listagem |

## Mapa dos documentos

| Arquivo | O que é |
|---|---|
| **`ESTADO-ATUAL.md`** | este — leia primeiro |
| **`PLANO-NUCLEO.md`** (31/07, fechado 03/08) | **leia em segundo.** Os 10 pacotes do núcleo, os 12 vereditos, a matriz de 20 conexões, o backlog de 25 automações, as estruturas mortas e as 7 decisões. Onde ele diverge do `FLUXO-IDEAL.md`, **vale ele** |
| `FLUXO-IDEAL.md` (30/07) | O diagnóstico que originou o plano. Suas ondas 0-3 foram **reordenadas** nos pacotes p1-p10 — traz o aviso no topo |
| `docs/estudo-fluxo/*.json` (31/07) | Os brutos: conferência adversarial dos 12 vereditos e o levantamento de conexões |
| `docs/superpowers/{specs,plans}/2026-08-03-p1-*` | Spec e plano do p1 — o único pacote que teve os dois documentos antes do código, porque dois vereditos mudaram de tamanho ao serem reconferidos |
| `docs/superpowers/plans/2026-07-21-*` | **os 10 planos das fases** (ver tabela acima). ⚠️ o da **Fase 7 está obsoleto** — substituído pelo p10 |
| `DEVOLUTIVA.md` | aderência à especificação + sequência de fases. (O erro do `:73` sobre "não existe recebimento" foi corrigido em 23/07 — o recebimento existe, só não é o gatilho financeiro) |
| `docs/fase-1-rollout.md` / `fase-2-rollout.md` / `fase-3-rollout.md` | **runbooks de rollout por fase** — pré-checagens, ordem de ligar flags e rollback. ⚠️ são do **núcleo**; no ciclo de compras o runbook mora no fim do próprio spec |
| `docs/superpowers/specs/2026-08-{11,14,15}-*-design.md` | **os specs das três fases entregues do ciclo de compras** (recebimento e atesto, financeiro em dois fluxos, alçadas). Cada um traz o runbook no fim e as divergências como 📌 no ponto exato do texto — leia os 📌, são o que a execução descobriu contra o plano |
| `DOSSIE-REPO.md` | as 29 respostas sobre arquitetura, dados, infra e qualidade |
| `docs/anexos/A-rotas-sem-autenticacao.md` | censo AST das 724 rotas. ⚠️ `:16` classifica as rotas por token como "desenho correto" — foi o que produziu o "1 rota de escrita sem auth" |
| `FECHO-FASE-0.5.md` | o que a Fase 0.5 entregou e o que não |
| `docs/integracao-dominio.md` | layout 11758. ⚠️ 11 lacunas mapeadas na F8 |
| `docs/superpowers/plans/2026-07-17-modulo-*` | os 10 módulos do cronograma .mpp (M01–M10), fechados |
| `docs/revisao-fases-1-5-PARCIAL.md` | 29 candidatos de revisão **não verificados** — pistas, não defeitos. Leia o topo: o workflow trocou de alvo ao ser retomado |
| `docs/archive/` | documentos mortos |
