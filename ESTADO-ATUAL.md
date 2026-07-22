# ESTADO ATUAL — SIGE / Veks

> Snapshot de **2026-07-21** (2ª revisão, após a rodada de planejamento).
> Este é o documento a ler PRIMEIRO ao retomar. Os demais (`DEVOLUTIVA.md`,
> `DOSSIE-REPO.md`, `FECHO-FASE-0.5.md`) são o detalhe; este é o mapa.

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

Branch: `fix/fase-0-estancar` · **27 commits não pushados.**

🔬 21/07: `main` e `origin/main` estão **idênticos** em `8fe6ac9` — o merge do
M10 subiu. (A 1ª versão dizia "67 commits à frente"; era verdade quando escrita.)

## 🔴 RETOMADA IMEDIATA — banco de dev recriado vazio em 22/07

O Postgres do ambiente (`helium`) caiu em 22/07 ~00:30, não se recuperou e
foi **recriado do zero** — o banco de desenvolvimento está vazio. Nenhum
código foi perdido (26 commits, árvore limpa). Ao retomar, nesta ordem:

1. O boot do app reconstrói o schema sozinho: `create_all()` + migrations
   1-219, todas idempotentes. Basta o workflow do Replit subir. Se quiser
   forçar: `python -c "import main"`.
2. **Rodar o gate completo**, que ficou INCONCLUSIVO: a única rodada sobre
   o estado final (commit `e782f70`) morreu junto com o banco (80 falhas,
   todas `OperationalError`). O último verde íntegro foi 745 passed sobre
   o estado até a Task 7 da Fase 1; as Tasks 8-11 têm regressões dirigidas
   verdes (145 + 49 passed), não gate cheio.
   `bash run_tests.sh --gate` ou
   `python -m pytest tests/ -m "not browser" -q --timeout=240`.
3. As volumetrias ⚠️ dev deste documento (8.723 obras, 53 'Em Andamento',
   980 partidas órfãs etc.) descrevem o banco ANTIGO. Continuam válidas
   como forma do problema; o banco novo nasce limpo e as migrations
   preventivas (217-219) rodam como no-op.
4. Dois commits alheios ao plano entraram na queda: `f52a7c7` (Replit
   Agent, retry no create_all) e `e782f70` (meu: esgotado o retry, aborta
   o boot em produção — alinhado à política da Fase 0.5/1.1). O segundo
   NÃO foi testado contra banco vivo; o gate do passo 2 o cobre.

Parado em: Fase 2 (máquina de estados da Obra). A Fase 1.5 fechou em 22/07 —
14/14 tasks do plano
`docs/superpowers/plans/2026-07-21-cronograma-editavel-rdo-percentual.md`.
Pendência de rollout, não de código: ligar `escopo_obra_ativo` por tenant
(`scripts/flag_escopo_obra.py <admin_id> --ligar`) para o RBAC da Task 13
sair do modo transparente.

## 🔴 Travado do lado humano

| # | O quê | Por que trava |
|---|---|---|
| 1 | **Rotacionar `SESSION_SECRET` e a senha do Postgres** no EasyPanel | Os valores estão no **histórico do git para sempre**. Com a chave de sessão forja-se cookie de qualquer usuário de qualquer tenant |
| 2 | **`gh auth setup-git`** (ou push manual) | 🔬 21/07: o `gh` **já está autenticado** como `cassioviller` com escopo `repo`. Falta só o credential helper. Sem push, o CI nunca rodou verde |
| 3 | **Criar o volume persistente** no painel | Vale para `/var/backups/sige` (dumps) **e** para os uploads — ver a armadilha nº 2, que é pior do que parece |

Também pendem: conferir divergência entre painel e valores commitados, snapshot
do volume na Hostinger, `SIGE_ENABLE_DEMO_SEED=false`, a grafia do domínio
(`cassioviller` × `cassiovillar`, as duas no código) e o acesso ao banco de
produção — que é pré-requisito de **quase toda medição pendente abaixo**.

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

## O plano aprovado

| Fase | Conteúdo | Estado | Plano |
|---|---|---|---|
| **0** | Estancar | ✅ | — |
| **0.5** | Backup, segredos, observabilidade, build, CI, índices | ✅ P1-2; 🟡 P3 parcial | — |
| **0.6** | Os cinco defeitos de dinheiro (D1-D5) | ✅ **21/07** | ver seção acima |
| **1** | Identidade e papéis (RBAC + escopo por obra) | ✅ **21/07** — 11/11 tasks | `fase-1-identidade-papeis.md` |
| **1.5** | Cronograma editável + RDO em % | ✅ **22/07** — 14/14 tasks | `cronograma-editavel-rdo-percentual.md` |
| **2** | Máquina de estados da Obra + handoff do GP | ⬜ | `fase-2-maquina-estados-obra.md` |
| **3** | Compras com governança | ⬜ | `fase-3-compras-governanca.md` |
| **4** | Centro de custo obrigatório | ⬜ | `fase-4-centro-custo-obrigatorio.md` |
| **5** | RDO com ciclo de vida e assinatura | ⬜ | `fase-5-rdo-ciclo-vida-assinatura.md` |
| **6** | Orçamento versionado e aditivo | ⬜ | `fase-6-orcamento-versionado-aditivo.md` |
| **7** | Planejamento avançado (CPM, baseline, EVM) | ⬜ | `fase-7-planejamento-avancado-cpm-evm.md` |
| **8** | Financeiro avançado + exportação Domínio | ⬜ | `fase-8-financeiro-avancado-dominio.md` |
| **9a/9b** | Portal, assinatura de medição, contratos, Drive | ⬜ | `fase-9-portal-assinatura-contratos.md` |

Todos em `docs/superpowers/plans/2026-07-21-*`. Faixas de migration reservadas
sem colisão: 214-216 (F1), 220-221 (F1.5), 230-232 (F2), 240-247 (F3),
250-254 (F4), 260-264 (F5), 270-276 (F6), 280-283 (F7), 290-295 (F8),
300-307 (F9). A **Fase 0.6 usou 217-219**, fora de todas as faixas.
🔬 Maior aplicada hoje: **219**. A Fase 1 aplicou 214, 215 e 216.

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
| Triagem de `fix/bloco2-segredos` e `fix/bloco1-blindagem-acesso` | ❌ órfãs, 402 commits atrás |
| `gitleaks`/`trufflehog` | ❌ indisponíveis; varredura manual não cobriu blobs binários |
| Conflito `opencv-python` × `headless` | ❌ entra por `deepface`/`retina-face`; exige decidir sobre reconhecimento facial |
| `psycopg2-binary` → `psycopg2` compilado | ⏸️ recomendado (1h); psycopg 3 **não** agora |
| 28 rotas `EXPOE DADO` sem auth | ❌ triagem caso a caso |
| Backup **agendado** | ❌ só existe o pré-migração; usar job do EasyPanel, não APScheduler |
| Skips de precondição de dado | ❌ ainda produzem verde falso em banco novo |
| ~~`duplicar_rdo` emite webhook sem lançar custos (bug 6d)~~ | ✅ **rediagnosticado — ver abaixo** |
| `scripts/medir_producao.py` | ❌ aguarda acesso ao banco |

**Bug 6d, corrigido o diagnóstico.** 🔬 21/07: `duplicar_rdo`
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

**Segunda rota morta, achada junto:** 📖 `finalizar_rdo` (`views/rdo.py:1520`)
tem guard `if rdo.status == 'Finalizado': return` — e `models.py:860` faz todo
RDO **nascer** com esse valor. É também `@admin_required`, que recusa
`FUNCIONARIO` (`auth.py:29`): **o apontador não consegue submeter o próprio
RDO**.

## Números que valem lembrar

| | | |
|---|---|---|
| Rotas totais / sem autenticação | 724 / 40 | 🧮 |
| Rotas de **escrita** por token eterno | **8** | 📖 21/07 — não "1", ver acima |
| Índice `rdo_apontamento_cronograma` | 881 ms → 0,034 ms | 🔬 |
| Testes | 878, gate ~39 min | 🧮 |
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

2. **⚠️ Definir `UPLOADS_PATH` hoje faz todas as fotos sumirem da tela.**
   📖 `salvar_foto_rdo` grava em `$UPLOADS_PATH/rdo/…`, mas `servir_foto`
   (`crud_rdo_completo.py:804`) procura em `os.getcwd()/static/…`. A variável
   está **vazia** hoje — e é exatamente por isso que a base64 existe: o disco
   atual é o filesystem efêmero do container. Corrigir o descasamento **antes**
   de montar o volume. Bônus: 📖 `crud_rdo_completo.py:718` monta `RDOFoto` sem
   `nome_arquivo`/`caminho_arquivo`, que são NOT NULL.

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

7. **`Obra.regime_medicao` é coluna morta com comentário mentiroso.**
   📖 `models.py:288-291` afirma governar o vínculo custo↔tarefa. **Nada no
   código a lê.**

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

## Decisões pendentes suas

Consolidadas dos 10 planos. Cada uma **já tem recomendação adotada no plano** —
nenhum plano está bloqueado esperando resposta. Revise quando puder.

| Tema | Onde | O que decidir |
|---|---|---|
| Alçada de aprovação de compra | F3 | Faixas em R$ (recomendado: 5k / 30k, absoluto e não % — `Obra.orcamento` é `Float default 0.0`) |
| Estados da Obra | F2 | Os 5 propostos, todos ancorados em valor que o código já usa |
| Regra de derivação das linhas órfãs | F4 | E o destino das ~77 irrecuperáveis |
| Folha e almoxarifado são administrativos? | F4 | Recomendado sim para ambos (evita contagem dupla com o RDO) |
| Valor jurídico da assinatura | F5, F9a | Recomendado: autoria + integridade (MP 2.200-2 art. 10 §2º), sem ICP-Brasil |
| Plano de contas e regime do Domínio | F8 | Recomendado: tabela por tenant + regime de caixa |
| **11 lacunas do layout 11758** | F8 | A 1ª é a mais básica: a spec **nunca define a ordem das colunas**. Um `.csv` já aceito pelo Domínio resolve 8 de uma vez |
| Expiração do token do portal | F9a | Recomendado: 90 dias, parametrizável |
| Miniatura do portal × migração de fotos | F5 | Único ponto sem recomendação: ou a rota por token vem antes, ou o portal fica sem miniatura no intervalo |

## Mapa dos documentos

| Arquivo | O que é |
|---|---|
| **`ESTADO-ATUAL.md`** | este — leia primeiro |
| `docs/superpowers/plans/2026-07-21-*` | **os 10 planos das fases** (ver tabela acima) |
| `DEVOLUTIVA.md` | aderência à especificação + sequência de fases. ⚠️ `:73` erra ao dizer que "não existe recebimento" — existe (`compras_views.py:841-948`) |
| `DOSSIE-REPO.md` | as 29 respostas sobre arquitetura, dados, infra e qualidade |
| `docs/anexos/A-rotas-sem-autenticacao.md` | censo AST das 724 rotas. ⚠️ `:16` classifica as rotas por token como "desenho correto" — foi o que produziu o "1 rota de escrita sem auth" |
| `FECHO-FASE-0.5.md` | o que a Fase 0.5 entregou e o que não |
| `docs/integracao-dominio.md` | layout 11758. ⚠️ 11 lacunas mapeadas na F8 |
| `docs/superpowers/plans/2026-07-17-modulo-*` | os 10 módulos do cronograma .mpp (M01–M10), fechados |
| `docs/archive/` | documentos mortos |
