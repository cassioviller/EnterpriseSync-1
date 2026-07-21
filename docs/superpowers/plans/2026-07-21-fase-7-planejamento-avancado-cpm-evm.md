# Fase 7 — Planejamento Avançado: CPM, Baseline e EVM

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Dar ao SIGE as três perguntas de controle de obra que ele ainda não sabe responder — *quais tarefas não podem atrasar* (caminho crítico), *quanto o plano de hoje se afastou do plano contratado* (baseline congelada) e *o que a obra conseguiu com o dinheiro que gastou* (EVM: IDP, IDC, EAC) — reaproveitando integralmente o motor, o versionamento e as curvas que os módulos M01–M10 já entregaram.

**Architecture:** Três camadas finas sobre o que já existe, nenhuma reescrita. (1) **CPM** ganha o dado que falta — a aresta tipada `TarefaPredecessora` (FS/SS/FF/SF + lag), que o parser já extrai e o snapshot já guarda em JSON — e um motor puro `utils/cpm.py` que faz passagem direta/inversa e devolve folga. O CPM da Fase 7 é camada de **análise**: não reescreve datas. (2) **Baseline** não é tabela nova: é uma `CronogramaVersao` (`models.py:5047`) marcada, porque o snapshot integral e imutável por versão já existe (`models.py:5090`) e `restaurar_versao` já sabe reconstruir a partir dele. (3) **EVM** é aritmética sobre três séries que já existem em código separado — planejado físico por tarefa (`utils/cronograma_engine.py:429`), custo previsto faseado (`services/cronograma_fisico_financeiro.py:86`) e custo realizado por mês (`services/cronograma_fisico_financeiro.py:563`); só falta multiplicar % físico por dinheiro para obter o Valor Agregado, e o campo onde isso encaixa já está declarado e vazio (`pct_fisico`, `services/cronograma_fisico_financeiro.py:254`).

**Tech Stack:** Flask 3 + Flask-Login, SQLAlchemy 2 (`models.py`), sistema de migrações próprio numerado (`migrations.py`, `migrations_to_run`), PostgreSQL, Chart.js (Gantt e curvas são JS manual + Chart.js, sem lib de Gantt), pytest (`run_tests.sh --gate`).

**Faixa de migrations reservada:** **280–289**.

---

## 1. O que os módulos M01–M10 já entregaram (NÃO refazer)

Esta seção vale mais que qualquer tarefa. Tudo abaixo foi conferido no código em 2026-07-21, commit `fb4147b`. **Se uma tarefa desta fase parecer estar construindo algo desta lista, ela está errada.**

| Já existe | Onde | Consequência para a Fase 7 |
|---|---|---|
| **Parser extrai tipo de vínculo E lag** dos dois formatos | `services/mspdi_parser.py:44` (`_TIPO_VINCULO = {0:'FF',1:'FS',2:'SF',3:'SS'}`), `:47` (`_LAG_POR_DIA = 4800.0`), `:99-114`; `services/mpp_parser_worker.py:50-63` (`_lag_dias`), `:106-117` | A Fase 7 **não** mexe em parser. O dado chega pronto |
| **Normalizador preserva tipo e lag** | `services/cronograma_normalizacao.py:355-359` (`{'chave','tipo','lag_dias'}`) | Não mexer no normalizador exceto pelo schema, se preciso |
| **Snapshot de versão guarda a lista tipada completa** | `models.py:5122` (`predecessoras_json`), montado em `services/cronograma_versao_service.py:620-626` | A fonte do backfill da Task 2 **já está em banco**, nas obras já importadas |
| **Versionamento completo de cronograma**: importação, versão sequencial por obra, snapshot integral imutável, mapeamento de reconciliação, trilha de eventos | migrations 207–212 (`migrations.py:4008-4013`); modelos `models.py:5018,5047,5090,5135,5178`; serviço `services/cronograma_versao_service.py` | **Baseline não precisa de tabela nova.** É uma versão marcada |
| **Rollback para qualquer versão** | `services/cronograma_versao_service.py:668` (`restaurar_versao`), `:691` (`_restaurar`) | Comparar baseline × vigente reusa a leitura de snapshot, não reimplementa |
| **Toda obra tem versão nº1** (backfill retroativo + obras novas) | migrations 210 e 212 (`migrations.py:4011,4013`) | Não existe obra sem ponto de baseline candidato |
| **Motor único de progresso** com tabela normativa (marco, unidade homogênea, rollup, arquivada histórica) | `utils/cronograma_engine.py:1-30` (contrato), `:510` (`calcular_progresso_geral_obra_v2`), `:632` (`rollup_realizado`) | O EV **consome** o motor; não escreve fórmula de progresso nova |
| **Planejado × realizado por tarefa, em qualquer data** | `utils/cronograma_engine.py:429` (`calcular_progresso_rdo` devolve `percentual_planejado` e `percentual_realizado`), `:143` (`_planejado_na_data`) | Já é o PV/EV **físico**. Falta só monetizar |
| **Planejado × realizado agregado da obra, em qualquer data** | `utils/cronograma_engine.py:510` devolve `progresso_geral_pct` **e** `progresso_planejado_pct` | Fallback pronto do EVM quando não há peso financeiro |
| **Série temporal de avanço físico (curva S física) já exposta e desenhada** | rota `views/obras.py:2555-2557` (`/obras/<id>/curva-avanco`); card em `templates/obras/detalhes_obra_profissional.html:1924-1948`, JS em `:2925-2946` | Não construir outra curva física |
| **Curva S financeira de custo previsto**, faseada por dias úteis com o calendário do tenant | `services/cronograma_fisico_financeiro.py:25` (`fasear_por_dias_uteis`), `:86` (`montar_curva_s`), `:346` | **É o PV monetário.** Não refazer o faseamento |
| **Custo realizado por mês, tenant-scoped, da fonte canônica** | `services/cronograma_fisico_financeiro.py:563` (`curva_realizado`, sobre `GestaoCustoFilho.data_referencia`, `models.py:5299`) | **É o AC.** Não refazer a agregação |
| **Alocação de valor por tarefa via peso de medição** | `services/cronograma_fisico_financeiro.py:62` (`alocar_por_peso`), aplicada em `:315` com `ItemMedicaoCronogramaTarefa.peso` (`models.py:5472`) | **É o "quanto vale cada tarefa".** O EV multiplica isto pelo % realizado |
| **Painel financeiro consolidado + endpoint JSON** com 4 séries acumuladas | `services/cronograma_fisico_financeiro.py:482` (`painel_financeiro`), rota `views/obras.py:2089` (`/obras/<id>/financeiro/dados`), gráfico em `static/js/financeiro_obra.js:382-390` | O painel de EVM entra **neste** endpoint, não num novo |
| **Replanejamento de curvas preservando o realizado** | `utils/cronograma_engine.py:724` (`replanejar_curvas_obra`), chamado no pós-commit de versão (`services/cronograma_versao_service.py:431`) | Rebaseline reusa isto |
| **Flag de rollout por tenant, com precedente e script** | `models.py:3620` (`cronograma_mpp_ativo`), `utils/tenant.py:113`, `scripts/flag_cronograma_mpp.py` | A flag da Fase 7 é irmã desta, não mecanismo novo |
| **Gantt interativo com arrasto de barras e edição inline** | `templates/obras/cronograma.html` (2.465 linhas), `renderGantt` em `:2129`, marcador de planejado em `:2191-2196` | A cor de crítica entra **neste** renderer |
| **Autorização real das rotas de cronograma** | `decorators.py:7` (`cronograma_import_required` — verifica de fato) | Reusar; não escrever decorator novo |
| **Suíte de cronograma**: 24 arquivos de teste, incluindo multitenancy, permissões e equivalência de migração | `tests/test_cronograma_*.py`, `tests/test_importacao_fisico_financeiro.py`, `tests/test_painel_financeiro.py` | Os testes desta fase entram no mesmo padrão |

## 2. O que NÃO existe (o delta real desta fase)

Também conferido, também em 2026-07-21.

| Não existe | Evidência |
|---|---|
| Tabela de arestas de predecessora | `grep -rn "TarefaPredecessora\|tarefa_predecessora"` → zero. A dependência é **uma** coluna auto-referente: `models.py:4883` (`predecessora_id`) |
| Tipo de vínculo e lag na tarefa viva | Só a **primeira predecessora FS** sobrevive à aplicação de versão: `services/cronograma_versao_service.py:103-110` (`_primeira_fs`) e `:583-587`. A docstring de `_primeira_fs` diz textualmente que "a lista tipada completa vive só no snapshot" |
| Qualquer cálculo de CPM: passagem direta/inversa, folga total, folga livre, flag de crítica | `utils/cronograma_engine.py` (888 linhas) não tem nenhuma. A única lógica de grafo é `verificar_ciclo` (`:108`). `recalcular_cronograma` (`:297`) faz **só** passagem direta, FS, uma predecessora, sem lag (`:347-357`) — limitação documentada no cabeçalho do módulo (`:26-28`) |
| Colunas `folga`, `is_critica`, `slack` em `TarefaCronograma` | `models.py:4863-4950` — não há |
| Folga/crítica/baseline/trabalho/custo vindos do MS Project | Nenhum parser lê `getCritical()`, `getTotalSlack()`, `getFreeSlack()`, `getBaselineStart/Finish/Cost()`, `getWork()`, `getCost()`. Contrato do parser são 13 campos: `services/mpp_parser_worker.py:123-137` |
| Baseline congelada de qualquer espécie | `grep -rn "baseline"` em `*.py`/`*.html` → zero (fora de `docs/`). O master plan já registrava: "Planejado é **volátil**… nenhuma baseline congelada" (`docs/superpowers/plans/2026-07-17-cronograma-mpp-rdo-master-plan.md:29`) |
| **Qualquer** indicador de EVM | `grep` por `EVM`, `valor_agregado`, `earned`, `BCWP`, `ACWP`, `BCWS`, `IDP`, `IDC`, `SPI`, `CPI`, `EAC`, `valor_planejado` em `*.py`/`*.html`/`*.js` → zero. O único falso positivo é a palavra portuguesa "etc." |
| Valor Agregado (EV) | Nunca se multiplica `% físico × custo`. O `realizado` das 4 séries do painel é **AC**, não EV (`services/cronograma_fisico_financeiro.py:553`) |
| `pct_fisico` por etapa | Declarado como `None` em `services/cronograma_fisico_financeiro.py:254`, repassado em `:538`, **nunca calculado**. Travado como `None` pelos testes atuais (`tests/test_importacao_fisico_financeiro.py:136,338`) |
| Custo real acumulado **até uma data** | `curva_realizado` devolve mapa mês→valor; o acumulado é feito à mão no chamador (`services/cronograma_fisico_financeiro.py:497-506`). `calcular_resumo_obra` (`services/resumo_custos_obra.py:213`) não tem parâmetro de data. `utils.py:518` (`calcular_custo_real_obra`) tem janela de datas mas é **código morto sem nenhum caller** e usa tabelas legadas, não `GestaoCustoFilho` |
| Caminho crítico na UI | `templates/obras/cronograma.html` não tem `<canvas>`, não tem Chart.js e não desenha setas de dependência. Os vermelhos existentes são de **atraso de %** (`:2193`) e do marcador de **hoje** (`:828`), não de criticidade |
| Consumo de `Obra.regime_medicao` | Coluna existe (`models.py:292`) e foi migrada (migration 201), mas **nenhuma view ou service a lê** |

---

## 3. Decisões de projeto (adotadas neste plano)

Cada uma tem uma recomendação explícita, já incorporada às tarefas. A seção 4 registra quais precisam de confirmação do Cássio — **nenhuma bloqueia a execução**.

### D1 — Quais indicadores de EVM o sistema calcula

**Recomendado: exatamente o conjunto da skill `consultor-cronograma` (Etapa 7), nem mais nem menos.** Grandezas VP, VA, CR; variações VC (`VA−CR`) e VPr (`VA−VP`); índices IDC (`VA/CR`) e IDP (`VA/VP`); previsões EAC, ETC, VAC e IDCN (TCPI).

*Por quê:* a skill do projeto já normatiza esse conjunto **e** os limiares de alarme (IDC < 0,80 por duas medições ⇒ intervenção obrigatória; IDP < 0,70 ⇒ replanejar urgente; IDCN > 1,20 ⇒ meta financeira inatingível). Adotar a lista da skill evita inventar indicador e dá farol pronto para a UI. Nomenclatura em **português** (VP/VA/CR/IDP/IDC/EAC), como no resto do sistema e como o gestor de obra brasileiro fala; o nome PMI em inglês entra só como tooltip.

**EAC padrão: `EAC = BAC / IDC`** (o desvio persistirá), com `EAC = CR + (BAC − VA)` (desvio pontual) exposta lado a lado como cenário. *Por quê:* em LSF o desvio de custo tende a ser estrutural — produtividade de montagem e preço do aço, que é commodity comprada cedo — e não um evento isolado. Mostrar as duas evita discussão sobre "qual fórmula você usou".

### D2 — Baseline é por obra ou por versão de cronograma?

**Recomendado: por VERSÃO. A baseline é uma `CronogramaVersao` marcada com `is_baseline=True`, com no máximo uma vigente por obra (índice único parcial).**

*Por quê, em três razões que se somam:*
1. O snapshot integral e imutável por versão **já existe** (`CronogramaTarefaSnapshot`, `models.py:5090`) e já contém datas, duração, hierarquia, marco e predecessoras tipadas. Uma tabela `BaselineTarefa` seria a mesma foto, duplicada e sujeita a divergir.
2. `restaurar_versao` (`services/cronograma_versao_service.py:668`) já sabe reconstruir o cronograma a partir desse snapshot — comparar baseline × vigente é leitura do mesmo lugar, com zero código de serialização novo.
3. O histórico de **rebaselines** (obrigatório em obra pública e em aditivo) sai de graça: cada rebaseline é marcar outra versão, e a anterior continua no banco com carimbo de quem e quando.

*Consequência aceita:* obra sem cronograma versionado não tem baseline — mas as migrations 210 e 212 garantiram versão nº1 para **toda** obra, então isso não acontece.

### D3 — O que é o BAC (Orçamento na Conclusão) do EVM?

**Recomendado: BAC = custo PREVISTO total das etapas** — a soma de `_previsto_por_categoria(osc)` (`services/cronograma_fisico_financeiro.py:200`, que é `realizado + a_realizar` por categoria) sobre os `ObraServicoCusto` da obra. **Não** `Obra.valor_contrato` (`models.py:254`).

*Por quê:* EVM compara valor de trabalho executado com **custo** incorrido. Usar preço de venda como BAC contra custo real infla o IDC pela margem inteira — a obra pareceria eficiente só porque foi bem vendida. `valor_contrato` continua sendo a base do faturamento comercial (`MedicaoContrato.valor`, `models.py:5585-5588`), que é outra pergunta e outro painel.

*Dependência declarada:* quando a **Fase 6** entregar orçamento versionado, o BAC deve passar a vir da versão de orçamento **congelada junto com a baseline**. Até lá o BAC é o previsto vivo — e portanto o EAC muda se alguém editar o orçado. Isso está registrado como premissa (seção 5, P3) e a Task 8 expõe `bac_origem` no payload para que a troca seja rastreável.

### D4 — O Valor Agregado é ponderado por peso físico ou por peso financeiro?

**Recomendado: peso FINANCEIRO por tarefa, com fallback físico declarado.**

- Caminho principal: `EV = Σ_tarefas (valor_alocado_da_tarefa × %realizado_da_tarefa_na_data)`, usando exatamente a alocação que já existe — `alocar_por_peso(previsto_total, pesos)` sobre `ItemMedicaoCronogramaTarefa.peso` (`services/cronograma_fisico_financeiro.py:315`, `models.py:5466-5472`).
- Fallback quando a obra não tem **nenhum** vínculo item↔tarefa: `EV = progresso_geral_pct × BAC`, usando `calcular_progresso_geral_obra_v2` (`utils/cronograma_engine.py:510`), **com aviso explícito no payload e na tela**.

*Por quê:* EVM é monetário por definição. O `progresso_geral_pct` do motor é ponderado por duração (ou quantidade homogênea), não por dinheiro — usá-lo como EV sobreponderaria tarefas longas e baratas. Em LSF isso é grave e sistemático: a montagem do frame é curta e cara, o acabamento é longo e barato; um EV por duração diria que a obra "agregou pouco valor" exatamente na etapa que consumiu metade do orçamento. O fallback existe porque hoje só as obras importadas pelo físico-financeiro têm o vínculo preenchido (ver premissa P6) — mas ele é anunciado, não silencioso.

### D5 — O CPM pode MOVER as datas das tarefas?

**Recomendado: NÃO nesta fase.** O CPM entra como camada de **análise** (folga total, folga livre, flag de crítica) calculada sobre as datas vigentes. Honrar SS/FF/SF e lag no **agendamento** — isto é, deixar o motor reescrever `data_inicio`/`data_fim` a partir da rede tipada — fica para depois, atrás da mesma flag.

*Por quê:*
1. `recalcular_cronograma` (`utils/cronograma_engine.py:297`) hoje **reescreve as datas de toda a obra** e é chamado no pós-commit de cada aplicação de versão (`services/cronograma_versao_service.py:431`). Fazê-lo passar a honrar lag e tipos mudaria datas de obras em produção como efeito colateral de uma importação.
2. O M06 fechou esse item explicitamente como fora de escopo (`docs/superpowers/plans/2026-07-17-modulo-06-motor-calculo.md:56`), preservando os dados no snapshot "para evolução futura".
3. **Ajuda o critério de pronto.** A DEVOLUTIVA pede "caminho crítico bate com o MS Project na obra piloto" (`DEVOLUTIVA.md:256`). Calculando folga sobre as datas **importadas** do Project, comparamos rede contra rede sem introduzir a variável "meu agendador reagenda diferente do agendador do Project". Se as datas divergissem, nunca saberíamos se o erro é do CPM ou do agendamento.

### D6 — Aritmética de folga em dias úteis, não corridos

**Recomendado: toda folga em DIAS ÚTEIS**, pelo calendário do tenant (`CalendarioEmpresa`, via `get_calendario`, `utils/cronograma_engine.py:89`), reusando `dias_uteis_entre` (`:73`) e `calcular_data_fim` (`:59`).

*Por quê:* as durações do sistema já são em dias úteis (`calcular_data_fim` soma dias úteis). Misturar folga em dias corridos com duração em dias úteis é o erro clássico de CPM caseiro: um fim de semana no meio de um caminho vira "2 dias de folga" que não existem, e o caminho crítico sai errado. O lag do MS Project, porém, chega em dias (`_LAG_POR_DIA = 4800.0` décimos de minuto, `services/mspdi_parser.py:47`) e pode ser fracionário — a conversão para dias úteis é responsabilidade explícita da Task 3 e tem teste próprio.

### D7 — Onde os indicadores aparecem

**Recomendado: EVM entra no endpoint que já existe** (`/obras/<id>/financeiro/dados`, `views/obras.py:2089`) como uma chave `evm`, e no card do painel financeiro (`templates/obras/detalhes_obra_profissional.html`). CPM/folga entra no cronograma (`cronograma_views.py:164` e `templates/obras/cronograma.html`). Baseline entra na área de versões que já existe (`views/cronograma_importacao.py:627`, `listar_versoes`).

*Por quê:* três superfícies novas seriam três lugares para o número divergir. O sistema já pagou esse preço uma vez — o M06 existiu para convergir ≥5 caminhos que calculavam o mesmo progresso. Não repetir.

---

## 4. Decisões que precisam do Cássio

Nenhuma bloqueia. Cada uma já tem a recomendação adotada; a resposta dele muda uma linha de configuração, não a arquitetura.

| # | Pergunta | Recomendação adotada | O que muda se ele discordar |
|---|---|---|---|
| 1 | Quais indicadores de EVM você realmente usa na reunião de obra? | O conjunto completo da skill: VP, VA, CR, VC, VPr, IDP, IDC, EAC, ETC, VAC, IDCN | Só a UI — o motor calcula todos de qualquer forma; esconder é um `if` no template |
| 2 | A baseline é da obra ou da versão de cronograma? | Da **versão** (`CronogramaVersao.is_baseline`), uma vigente por obra | Se ele quiser baseline por disciplina/frente, vira um segundo campo de escopo na mesma tabela — não uma tabela nova |
| 3 | O BAC do EVM é o **custo previsto** ou o **valor de contrato**? | Custo previsto (`ObraServicoCusto`) | Uma constante em `services/evm.py`; o payload já carrega `bac_origem` |
| 4 | O EAC que ele quer ver por padrão é `BAC/IDC` ou `CR + (BAC−VA)`? | `BAC/IDC` como principal, a outra ao lado | Trocar qual é destaque na tela |
| 5 | Rebaseline pode ser feito por quem? | `PapelObra.GESTOR` da obra + `ADMIN` do tenant (Fase 1) | Um valor na lista de papéis aceitos |
| 6 | A obra piloto para validar "caminho crítico bate com o MS Project" é a Baia? | Sim — é a única com `.mpp` real no repositório (`CRONOGRAMA 16.07.mpp` / `.xml`) e com suíte de equivalência (`tests/test_migracao_baias_equivalencia.py`) | Precisaria de outro `.mpp` de referência |

---

## 5. Premissas a reconfirmar antes de executar

Esta fase é a 7ª de 9. Muita coisa terá mudado. **Reconfirme cada item abaixo antes da primeira linha de código**, com o motivo dado.

| # | Premissa | Por que reconfirmar |
|---|---|---|
| **P1** | **A faixa 280–289 continua livre.** Hoje a maior migration registrada é a **213** (`migrations.py:4014`) e as Fases 1–6 vão consumir 214 em diante | Se as fases anteriores estourarem a faixa, dois arquivos criarão o mesmo número e o registro em `migrations_to_run` (`migrations.py:3831`) vira ambíguo. Rode `grep -n "^            (2" migrations.py | tail -5` antes de escrever a 280 |
| **P2** | **`utils/autorizacao.py`, `UsuarioObra` e `PapelObra` existem com a assinatura da Fase 1** — `obras_visiveis()`, `pode_ver_obra()`, decorator `obra_required` | Todas as rotas novas desta fase devem nascer com escopo por obra. Se a Fase 1 renomeou algo, as tarefas 5, 7 e 9 usam nome inexistente e falham na importação, não em teste |
| **P3** | **De onde vem o BAC depois da Fase 6.** Enquanto o orçamento não versiona, o BAC é o previsto **vivo** de `ObraServicoCusto` — logo o EAC de uma medição passada muda se alguém editar o orçado hoje | Isso é aceitável em rodagem interna e **inaceitável** para medição contratual. Se a Fase 6 já entregou versão de orçamento, o BAC tem de ser congelado junto com a baseline (D3), o que muda a Task 8 de "somar OSC" para "ler a versão de orçamento vinculada à baseline" |
| **P4** | **O plano paralelo `docs/superpowers/plans/2026-07-21-cronograma-editavel-rdo-percentual.md` foi executado.** Conferido em 2026-07-21: **o arquivo ainda não existe** no repositório (`ls docs/superpowers/plans/` não o lista) | Esse plano torna o modo de apontamento uma **escolha explícita da tarefa**, em vez da dedução atual de `services/cronograma_apontamento_service.py:73`. O EV depende de `percentual_realizado` por tarefa vindo de `calcular_progresso_rdo` (`utils/cronograma_engine.py:429`). Se o contrato de retorno mudar (por exemplo, se `percentual_realizado` passar a ser `None` para tarefas em modo quantitativo sem quantidade), a Task 8 quebra em silêncio — produziria EV subestimado, não erro |
| **P5** | **Os nomes dos estados da Obra da Fase 2.** Congelar baseline só pode ser permitido em obra que ainda não começou a medir, ou logo no início | Sem os nomes reais, a Task 6 não consegue escrever a guarda. Não invente `EM_EXECUCAO` — leia o enum |
| **P6** | **Quantas obras reais têm `ItemMedicaoCronogramaTarefa` preenchido.** Hoje esse vínculo nasce do importador físico-financeiro (`services/importacao_fisico_financeiro.py`); obras que vieram só do `.mpp` (M03–M08) podem não ter nenhum | Se a resposta for "quase nenhuma", o EV cai no fallback físico (D4) para quase toda a base — o que muda a prioridade: antes de refinar o EVM, valeria uma tela de vínculo item↔tarefa. Medir isso depende da decisão de acesso ao banco de produção, ainda pendente (`ESTADO-ATUAL.md:103`) |
| **P7** | **Se a Fase 7 herda a flag `cronograma_mpp_ativo` ou ganha a sua.** Hoje essa flag nasce desligada e esconde a área de importação inteira (`utils/tenant.py:113`, `models.py:3620`) | Se herdar, tenant sem `.mpp` nunca vê CPM/EVM — o que pode estar certo (sem rede de predecessoras, o CPM é trivial) ou errado (o EVM não depende de `.mpp` nenhum). Este plano assume **flag própria** (Task 1) por causa disso |
| **P8** | **`tests/test_importacao_fisico_financeiro.py:136,338` continuam afirmando `pct_fisico is None`** | A Task 9 passa a calcular esse campo. Esses dois asserts vão falhar **de propósito** — precisam ser atualizados no mesmo commit, com justificativa. Se alguém tiver reescrito esse arquivo, localize os asserts equivalentes antes |
| **P9** | **`services/schemas/cronograma_normalizado.schema.json` tem `additionalProperties: false`** nas tarefas (`:30`) e nas predecessoras (`:57`) | Se qualquer tarefa desta fase precisar acrescentar campo ao normalizado, o schema **e** `NORMALIZADOR_VERSAO` (`services/cronograma_normalizacao.py:25`) têm de subir juntos. O plano evita isso, mas confirme que ninguém removeu a trava |

---

## 6. Arquivos que esta fase cria ou altera

| Arquivo | Responsabilidade |
|---|---|
| `utils/cpm.py` | **novo** — motor CPM **puro**: recebe lista de nós e arestas, devolve datas cedo/tarde, folga total e livre, e o conjunto crítico. Sem SQLAlchemy, sem Flask, sem `datetime.today()` |
| `services/cronograma_cpm_service.py` | **novo** — adaptador: carrega a obra do banco, monta o grafo, chama `utils/cpm.py`, persiste o resultado derivado. Único lugar que traduz ORM ↔ motor |
| `services/cronograma_baseline_service.py` | **novo** — congelar baseline, ler a vigente, comparar baseline × cronograma vigente por tarefa e no total |
| `services/evm.py` | **novo** — motor EVM **puro** (as 11 grandezas a partir de VP/VA/CR/BAC) + coletor que monta VP/VA/CR/BAC das fontes existentes |
| `models.py` | modelo `TarefaPredecessora`; colunas derivadas de CPM em `TarefaCronograma`; campos de baseline em `CronogramaVersao`; flag em `ConfiguracaoEmpresa` |
| `migrations.py` | migrations **280–284** + registro em `migrations_to_run` |
| `scripts/flag_planejamento_avancado.py` | **novo** — liga/desliga a flag por tenant, espelhando `scripts/flag_cronograma_mpp.py` |
| `scripts/backfill_predecessoras_tipadas.py` | **novo** — popula `TarefaPredecessora` a partir do snapshot da versão ativa (ou do `predecessora_id` único), dry-run por padrão |
| `services/cronograma_versao_service.py` | passa a gravar **todas** as arestas tipadas ao aplicar versão, além do `predecessora_id` legado |
| `cronograma_views.py` | rota de caminho crítico; `_tarefa_to_dict` (`:53`) ganha folga/criticidade |
| `templates/obras/cronograma.html` | coluna Folga; barra crítica destacada em `renderGantt` (`:2129`) |
| `views/cronograma_importacao.py` | rotas de congelar baseline e comparar baseline × vigente; `listar_versoes` (`:627`) devolve `is_baseline` |
| `services/cronograma_fisico_financeiro.py` | `pct_fisico` por etapa deixa de ser `None`; `painel_financeiro` (`:482`) ganha a chave `evm` |
| `templates/obras/detalhes_obra_profissional.html`, `static/js/financeiro_obra.js` | card de EVM com faróis e curva de três séries |
| `tests/test_cpm_motor.py` | **novo** — motor puro, incluindo o exemplo canônico de CPM |
| `tests/test_cronograma_predecessoras_tipadas.py` | **novo** — modelo, backfill, aplicação de versão |
| `tests/test_cronograma_baseline.py` | **novo** — congelar, unicidade, comparação, rebaseline |
| `tests/test_evm.py` | **novo** — motor puro + coletor + fallback anunciado |

---

## 7. Tarefas

> **Granularidade:** cada tarefa segue o ciclo teste-falha → implementação mínima → teste-passa → commit. Como esta fase está a seis fases de distância, as tarefas descrevem **responsabilidade, arquivos e critério de aceitação** com o código completo apenas onde ele é verificável hoje (motor puro de CPM, motor puro de EVM e os testes desses motores). Onde o código dependeria de assinaturas que a Fase 1 e a Fase 6 ainda vão definir, a tarefa diz **exatamente o que fazer e contra o que verificar**, e não inventa a chamada.

### Task 1 — Flag de rollout `planejamento_avancado_ativo`

**Files:**
- Modify: `models.py` (`class ConfiguracaoEmpresa`, junto de `cronograma_mpp_ativo` em `:3620`)
- Modify: `migrations.py` (migration **280** + registro)
- Create: `scripts/flag_planejamento_avancado.py`
- Test: `tests/test_flag_planejamento_avancado.py`

**Responsabilidade:** nada desta fase aparece para nenhum tenant até alguém ligar a flag, exatamente como o M10 fez com o cronograma `.mpp`.

**Como fazer:** copie a forma do precedente — coluna `Boolean, nullable=False, default=False, server_default='false'` (`models.py:3620-3621`), helper de leitura com falha fechada em `utils/tenant.py` no molde de `cronograma_mpp_ativo` (`:113-134`, que devolve `False` em qualquer exceção porque é lido em context processor), e script CLI espelhando `scripts/flag_cronograma_mpp.py` (`--ligar` / `--desligar` / consulta por `admin_id`).

**Critério de aceitação:**
- Teste `test_flag_nasce_desligada` — tenant recém-criado devolve `False`.
- Teste `test_flag_liga_e_desliga` — ida e volta persiste.
- Teste `test_helper_nunca_levanta` — com o banco indisponível (mock que levanta), o helper devolve `False`, não propaga. *Este é o teste que importa*: a flag é lida em context processor e uma exceção aqui derruba **todas** as páginas.
- **Não** ligar a flag em lugar nenhum ainda.

**Commit:** `feat(fase7): flag planejamento_avancado_ativo por tenant (migration 280)`

---

### Task 2 — `TarefaPredecessora`: a aresta tipada com lag

**Files:**
- Modify: `models.py` (novo modelo após `TarefaCronograma`, que termina em `:4952`)
- Modify: `migrations.py` (migration **281** + registro)
- Create: `scripts/backfill_predecessoras_tipadas.py`
- Test: `tests/test_cronograma_predecessoras_tipadas.py`

**Responsabilidade:** dar ao sistema a rede de predecessoras que o parser já entrega e que hoje morre na aplicação de versão. **Aditiva:** `TarefaCronograma.predecessora_id` (`models.py:4883`) **permanece intacta** e continua sendo o que `recalcular_cronograma` lê — nada de comportamento muda nesta tarefa.

**Forma do modelo** (campos, não código completo — a `db.Column` segue o padrão do arquivo):

| Campo | Tipo | Nota |
|---|---|---|
| `id` | Integer PK | |
| `tarefa_id` | FK `tarefa_cronograma.id` ON DELETE CASCADE, NOT NULL, index | a sucessora |
| `predecessora_id` | FK `tarefa_cronograma.id` ON DELETE CASCADE, NOT NULL, index | a antecessora |
| `tipo` | String(2), NOT NULL, default `'FS'` | domínio `{FS, SS, FF, SF}` — mesma grafia do parser (`services/mspdi_parser.py:44`), **inglês**, não TI/II/TT/IT |
| `lag_dias` | Float, NOT NULL, default `0.0` | pode ser negativo (*lead*) e fracionário; o parser produz `round(..., 6)` |
| `admin_id` | FK `usuario.id`, NOT NULL, index | consistente com o resto do schema |
| `created_at` | DateTime | |

**Constraints obrigatórias:**
- `UNIQUE (tarefa_id, predecessora_id, tipo)` — o MS Project permite dois vínculos entre o mesmo par se forem de tipos diferentes; permitir duplicata do mesmo tipo é sujeira.
- `CHECK (tarefa_id <> predecessora_id)` — auto-dependência é sempre erro.
- Índice em `(tarefa_id)` e em `(predecessora_id)` — o CPM percorre a rede nos dois sentidos (passagem direta e inversa).

**Backfill (`scripts/backfill_predecessoras_tipadas.py`), dry-run por padrão:**
1. Para cada obra, localize a `CronogramaVersao` com `status='ativa'`.
2. Leia `CronogramaTarefaSnapshot.predecessoras_json` (`models.py:5122`) dos snapshots dessa versão — é **a única fonte em banco com tipo e lag** (`services/cronograma_versao_service.py:620-626`).
3. Resolva cada entrada para a `TarefaCronograma` viva. Atenção ao formato duplo documentado em `services/cronograma_versao_service.py:133-136`: snapshots de backfill/legado trazem `{'tarefa_id', 'uid', 'tipo':'FS', 'lag_dias':0}` **forjado**; snapshots de importação trazem o tipo real. Trate os dois.
4. Quando o snapshot não resolver (tarefa arquivada, `tarefa_id` nulo), caia para `TarefaCronograma.predecessora_id` como `FS`/lag 0 — e **conte esse caso separadamente no relatório**, porque ele significa "perdi o tipo real".
5. Nunca crie tarefa. Nunca escreva em `predecessora_id`. Idempotente: segunda passada cria 0 arestas.

**Testes (`tests/test_cronograma_predecessoras_tipadas.py`, `pytestmark = pytest.mark.integration`, `import main` no topo, login por `sess['_user_id']`):**
- Persistência dos quatro tipos e de lag negativo.
- `UNIQUE` recusa a duplicata do mesmo par+tipo; aceita par igual com tipos diferentes.
- `CHECK` recusa auto-dependência.
- Backfill em dry-run não escreve; com `--aplicar` escreve; segunda passada é no-op.
- Backfill preserva `SS`/`FF`/`SF` vindos do snapshot de importação — **este é o teste que prova que a fase resolveu o problema**, já que hoje só FS sobrevive (`services/cronograma_versao_service.py:103-110`).
- Isolamento de tenant: aresta de um tenant nunca aparece na consulta do outro (siga o padrão de `tests/test_cronograma_multitenancy.py`).

**Commit:** `feat(fase7): TarefaPredecessora tipada com lag + backfill do snapshot (migration 281)`

---

### Task 3 — Motor CPM puro (`utils/cpm.py`)

**Files:**
- Create: `utils/cpm.py`
- Test: `tests/test_cpm_motor.py`

**Responsabilidade:** passagem direta, passagem inversa, folga total, folga livre e conjunto crítico — **sem tocar em banco, em Flask ou no relógio**. Recebe estruturas simples, devolve estruturas simples. É o único módulo desta fase que dá para escrever hoje com certeza, porque é algoritmo puro.

**Contrato (escreva exatamente estas assinaturas — as tarefas seguintes dependem delas):**

```python
# utils/cpm.py
"""Motor CPM puro — Fase 7.

Passagem direta/inversa sobre a rede de precedências, em UNIDADES DE DIA
ÚTIL (ver D6 do plano). Não conhece SQLAlchemy, não conhece Flask e não
lê o relógio: recebe nós e arestas, devolve números. Toda tradução
ORM <-> motor vive em services/cronograma_cpm_service.py.

Convenção de tempo: o "tempo" é um inteiro de dias úteis desde a origem
do projeto (dia 0 = primeiro dia útil). Quem chama converte data <-> índice
com utils.cronograma_engine.dias_uteis_entre / calcular_data_fim, que já
respeitam o CalendarioEmpresa do tenant.

Semântica dos quatro tipos (PMBOK / MS Project), com A = predecessora,
B = sucessora, lag L em dias úteis:
    FS  inicio_B  >= fim_A    + L      (Término-Início — o mais comum)
    SS  inicio_B  >= inicio_A + L      (Início-Início)
    FF  fim_B     >= fim_A    + L      (Término-Término)
    SF  fim_B     >= inicio_A + L      (Início-Término — raro)
"""
from __future__ import annotations

from dataclasses import dataclass, field

TIPOS_VALIDOS = ('FS', 'SS', 'FF', 'SF')


class RedeCiclica(ValueError):
    """A rede tem ciclo — não existe ordem topológica, logo não existe CPM."""

    def __init__(self, envolvidos):
        self.envolvidos = sorted(envolvidos)
        super().__init__(f'ciclo de precedência envolvendo {self.envolvidos}')


@dataclass(frozen=True)
class No:
    """Uma tarefa na rede. `duracao` em dias úteis; marco tem duração 0."""
    id: int
    duracao: int


@dataclass(frozen=True)
class Aresta:
    """Vínculo predecessora -> sucessora."""
    predecessora_id: int
    sucessora_id: int
    tipo: str = 'FS'
    lag: int = 0


@dataclass
class Resultado:
    """Saída do CPM, por nó, em índices de dia útil.

    inicio_cedo / fim_cedo  : passagem direta (o mais cedo possível)
    inicio_tarde / fim_tarde: passagem inversa (o mais tarde sem atrasar o fim)
    folga_total : quanto a tarefa pode atrasar sem atrasar o PROJETO
    folga_livre : quanto pode atrasar sem atrasar NENHUMA sucessora
    critica     : folga_total == 0
    """
    inicio_cedo: dict = field(default_factory=dict)
    fim_cedo: dict = field(default_factory=dict)
    inicio_tarde: dict = field(default_factory=dict)
    fim_tarde: dict = field(default_factory=dict)
    folga_total: dict = field(default_factory=dict)
    folga_livre: dict = field(default_factory=dict)
    critica: dict = field(default_factory=dict)
    duracao_projeto: int = 0

    def caminho_critico(self) -> list:
        """IDs críticos ordenados por início cedo (leitura de relatório)."""
        return sorted((i for i, c in self.critica.items() if c),
                      key=lambda i: (self.inicio_cedo[i], i))


def calcular(nos: list, arestas: list) -> Resultado:
    """Executa CPM sobre a rede. Levanta RedeCiclica se houver ciclo."""
    ...
```

**Notas de implementação que evitam os erros clássicos:**
- **Ordem topológica antes de tudo.** Sem ela, a passagem direta lê valores ainda não calculados e produz números plausíveis e errados. Já existe precedente de detecção de ciclo no projeto para se inspirar: `services/cronograma_normalizacao.py:210` (DFS iterativa com cores) e `utils/cronograma_engine.py:108`. Não use recursão — a Baia tem centenas de tarefas e o Python estoura em rede profunda.
- **Cada tipo restringe uma coisa diferente.** FS e SS empurram o **início** da sucessora; FF e SF empurram o **fim** dela. Depois de aplicar uma restrição de fim, o início se deriva como `fim − duracao`. Tratar os quatro como "empurra o início" é o bug mais comum de CPM caseiro.
- **Folga livre ≠ folga total.** Folga livre de A = `min(inicio_cedo das sucessoras) − fim_cedo(A) − lag`, considerando só sucessoras diretas; folga total olha o projeto inteiro. Uma tarefa com folga total 5 e folga livre 0 **não pode atrasar nem um dia** sem empurrar a vizinha, mesmo não sendo crítica — é a informação que o encarregado usa e que quase nenhum sistema mostra.
- **Marco tem duração 0** e participa da rede normalmente. O motor de progresso já trata marco como caso próprio (`utils/cronograma_engine.py:133`, `_is_marco_efetivo`); aqui basta `duracao=0`.
- **Rede desconexa é normal.** Uma obra pode ter frentes sem vínculo entre si. O motor deve tratar cada componente com a mesma data de término de projeto (o máximo global), que é o comportamento do MS Project.
- **Lag fracionário:** o parser produz `float` (`services/mspdi_parser.py:113`). O motor recebe `int`; a **conversão e o arredondamento são responsabilidade da Task 4**, e têm teste lá. Documente isso no docstring.

**Testes (`tests/test_cpm_motor.py` — puros, sem banco, sem `pytestmark`):**
1. **Exemplo canônico da skill `consultor-cronograma` (Etapa 4).** Rede: A(10) → B(20) → {C(15), D(12)} → E(8) → F(5). Assertar o quadro inteiro: `A` e `B` com folga 0 e críticas; `C` folga 2; `D` folga 5; `E` folga 2; `F` folga 2; duração do projeto = 58. *Este teste é o contrato do motor* — se ele passar, o algoritmo está certo.
2. Cadeia simples FS sem lag — a soma das durações é a duração do projeto e todo mundo é crítico.
3. FS com lag positivo empurra a sucessora e **aumenta** a duração do projeto.
4. FS com lag negativo (*lead*) sobrepõe as tarefas e **reduz** a duração.
5. Um caso para cada tipo: SS, FF e SF, com a restrição correta verificada explicitamente.
6. Duas sucessoras, uma com folga e outra sem — folga **livre** da predecessora é 0 mesmo com folga total > 0.
7. Marco (duração 0) no meio da cadeia não altera a duração do projeto.
8. Rede com ciclo levanta `RedeCiclica` e o `envolvidos` contém os nós do ciclo.
9. Rede desconexa: dois componentes independentes, o menor recebe folga igual à diferença entre os dois.
10. Rede vazia devolve `Resultado` vazio com `duracao_projeto == 0` (não estoura).

**Commit:** `feat(fase7): motor CPM puro com folga total e livre e os quatro tipos de vinculo`

---

### Task 4 — Adaptador de CPM e persistência do resultado derivado

**Files:**
- Create: `services/cronograma_cpm_service.py`
- Modify: `models.py` (colunas derivadas em `TarefaCronograma`)
- Modify: `migrations.py` (migration **282** + registro)
- Test: `tests/test_cronograma_cpm_service.py`

**Responsabilidade:** traduzir a obra do banco para `No`/`Aresta`, chamar `utils.cpm.calcular`, e gravar o resultado como **cache derivado** nas tarefas. Nada aqui muda `data_inicio`/`data_fim` (D5).

**Colunas novas em `TarefaCronograma`** — todas nullable, todas derivadas, todas recalculáveis:

| Coluna | Tipo | Nota |
|---|---|---|
| `folga_total_dias` | Integer, nullable | `NULL` = "nunca calculado" ≠ `0` = "crítica". A mesma distinção que `percentual_planejado` já faz (`models.py:4984`, nullable de propósito para separar "sem plano" de "0%") |
| `folga_livre_dias` | Integer, nullable | |
| `is_critica` | Boolean, nullable | |
| `cpm_calculado_em` | DateTime, nullable | permite mostrar "calculado há X" e detectar cache velho |

**Funções do serviço:**
- `montar_rede(obra_id, admin_id) -> (nos, arestas, indice_por_data)` — carrega tarefas **folha ativas** (mesmo critério de `calcular_progresso_geral_obra_v2`, `utils/cronograma_engine.py:510`: tarefas-pai são resumo e não entram na rede, senão duplicam caminho) e as arestas de `TarefaPredecessora`. Converte datas em índices de dia útil com `dias_uteis_entre` (`utils/cronograma_engine.py:73`) e o calendário do tenant (`get_calendario`, `:89`). Converte `lag_dias` float em dias úteis inteiros — **arredonda para cima em valor absoluto** (um lag de 0,5 dia é um dia de espera na prática; um lead de −0,5 é um dia de antecipação) e registra a conversão no relatório.
- `calcular_e_persistir(obra_id, admin_id) -> dict` — chama o motor, grava as quatro colunas, devolve relatório `{n_tarefas, n_criticas, duracao_projeto_dias, data_termino_projetada, lags_arredondados, avisos}`. Em `RedeCiclica`, **não grava nada**, loga e devolve `{'erro': 'ciclo', 'envolvidos': [...]}` — obra com ciclo não pode ter caminho crítico inventado.
- `caminho_critico(obra_id, admin_id) -> list` — leitura do cache, recalculando se `cpm_calculado_em` for `NULL`.

**Onde chamar:** ao final de `recalcular_cronograma` (`utils/cronograma_engine.py:297`), **atrás da flag da Task 1** e em bloco `try/except` que loga e segue. Precedente exato de "pós-commit que não pode derrubar a operação principal": `_motor_pos_commit` em `services/cronograma_versao_service.py:430`, e a ressalva 1 do fecho do M06 (`docs/superpowers/plans/2026-07-21-modulo-06-fecho.md:52-55`). Falha de CPM **nunca** desfaz uma aplicação de versão.

**Testes:** obra montada em banco com rede conhecida bate com o resultado do motor puro; tarefa-pai não entra na rede; obra sem arestas devolve todas as folhas com folga 0 (todas críticas — correto: sem rede, cada tarefa é seu próprio caminho); ciclo devolve erro e **não** grava; recálculo é idempotente; multitenant (obra de outro tenant não entra na rede); flag desligada ⇒ `recalcular_cronograma` não chama o CPM e as colunas ficam `NULL`.

**Commit:** `feat(fase7): CPM sobre a obra — folga total, folga livre e criticidade persistidas (migration 282)`

---

### Task 5 — Caminho crítico na superfície: API e Gantt

**Files:**
- Modify: `cronograma_views.py` (`_tarefa_to_dict` em `:53`; nova rota; `cronograma_obra` em `:164`)
- Modify: `templates/obras/cronograma.html` (cabeçalho da tabela em `:116-120`; linha em `:211-214`; `renderGantt` em `:2129-2225`)
- Test: `tests/test_cronograma_cpm_rotas.py`

**Responsabilidade:** o gestor **vê** o caminho crítico. Sem isto, as tarefas 3 e 4 são um número no banco.

**O que fazer:**
- `_tarefa_to_dict` (`cronograma_views.py:53`) ganha `folga_total_dias`, `folga_livre_dias` e `is_critica`. É a única serialização de tarefa do módulo — o front inteiro passa por ela.
- Nova rota `GET /cronograma/obra/<int:obra_id>/caminho-critico`, com `@login_required` **e** o `obra_required` da Fase 1 (premissa P2), devolvendo `{tarefas_criticas: [...], duracao_projeto_dias, data_termino_projetada, calculado_em, avisos}`. Guardar atrás da flag da Task 1 no molde de `_check_v2` (`cronograma_views.py:39`).
- Nova coluna **Folga** na tabela, ao lado de `Pred.` (`templates/obras/cronograma.html:116`). Mostrar `—` quando `NULL` (nunca calculado), `0` em destaque quando crítica.
- No Gantt (`renderGantt`, `:2129`): tarefa crítica ganha **borda** distintiva, não cor de preenchimento. *Motivo:* o preenchimento já codifica progresso (`:2193` — verde ≥100%, vermelho <20%, azul no meio) e o vermelho já significa "atrasado". Sobrecarregar a mesma cor com "crítica" torna o Gantt ilegível justamente na obra em apuro. Legenda visível na tela dizendo o que a borda significa.

**Testes:** rota devolve as críticas corretas para uma rede conhecida; rota é 403 para usuário sem acesso à obra e 404 para obra de outro tenant (siga `tests/test_cronograma_permissoes.py` e `tests/test_cronograma_multitenancy.py`); com a flag desligada a rota não existe/redireciona; o dicionário de tarefa carrega as três chaves novas.

**Commit:** `feat(fase7): caminho critico visivel no Gantt e via API`

---

### Task 6 — Baseline: congelar uma versão

**Files:**
- Modify: `models.py` (`class CronogramaVersao`, `:5047`)
- Modify: `migrations.py` (migration **283** + registro)
- Create: `services/cronograma_baseline_service.py`
- Modify: `views/cronograma_importacao.py` (`listar_versoes` em `:627`; nova rota de congelar)
- Test: `tests/test_cronograma_baseline.py`

**Responsabilidade:** transformar "a versão N" em "a **linha de base** contratada", sem tabela nova (D2).

**Campos novos em `CronogramaVersao`:**

| Campo | Tipo | Nota |
|---|---|---|
| `is_baseline` | Boolean, NOT NULL, default `False`, server_default `'false'` | |
| `baseline_rotulo` | String(80), nullable | "Baseline contratual", "Rebaseline pós-aditivo 1" |
| `baseline_definida_em` | DateTime, nullable | |
| `baseline_definida_por_id` | FK `usuario.id`, nullable | quem assumiu a responsabilidade |

**Constraint que carrega a regra de negócio:** índice **único parcial** `WHERE is_baseline` sobre `(obra_id)`. Uma obra tem no máximo uma baseline vigente. **Escreva-o no DDL da migration, não no declarativo** — há precedente explícito e comentado no próprio arquivo: `models.py:5048-5051` documenta que o unique parcial de `status='ativa'` vive só no DDL da migration 207 porque o SQLAlchemy declarativo não o expressa de forma portável. Siga o precedente; não invente uma solução nova para o mesmo problema.

**Serviço:**
- `definir_baseline(versao_id, usuario_id, rotulo)` — numa transação: desmarca a baseline anterior da obra (se houver), marca a nova, grava um `CronogramaImportacaoEvento` (`models.py:5178`) de auditoria com a versão anterior e a nova. Guardas: (a) a versão tem de ter snapshots (`n_snapshots > 0` — sem foto não há baseline); (b) papel autorizado (D5/premissa P2); (c) estado da obra permite (premissa P5).
- `baseline_vigente(obra_id, admin_id)` — a versão marcada, ou `None`.
- `historico_baselines(obra_id, admin_id)` — todas as que já foram baseline, pela trilha de eventos. *Motivo:* em obra pública, "quantas vezes você rebaselinou" é pergunta de auditoria, e a resposta não pode depender do estado atual de um booleano.

**Rota:** `POST /obras/<int:obra_id>/cronograma/versoes/<int:versao_id>/baseline`, no mesmo blueprint e com o mesmo `cronograma_import_required` (`decorators.py:7`) das rotas vizinhas. `listar_versoes` (`views/cronograma_importacao.py:627`) passa a devolver `is_baseline` e `baseline_rotulo` no payload que já monta.

**Testes:** congelar marca; congelar outra desmarca a primeira **na mesma transação** (assertar que nunca existem duas — inclusive tentando o `INSERT` direto e esperando `IntegrityError`); versão sem snapshots é recusada; a trilha de eventos registra a troca; cross-tenant recusado; `listar_versoes` devolve os campos novos.

**Commit:** `feat(fase7): baseline como versao de cronograma congelada (migration 283)`

---

### Task 7 — Comparativo baseline × vigente

**Files:**
- Modify: `services/cronograma_baseline_service.py`
- Modify: `views/cronograma_importacao.py` (rota de comparação)
- Modify: `templates/obras/cronograma_importacoes/_secao.html` (ou o template da seção de versões da obra)
- Test: `tests/test_cronograma_baseline.py` (acrescenta)

**Responsabilidade:** responder "o plano de hoje se afastou quanto do plano contratado?" — por tarefa e no total.

**`comparar_com_baseline(obra_id, admin_id) -> dict`:**
- Casa snapshot da baseline ↔ tarefa viva pelo **`tarefa_id` do snapshot** (`models.py:5108`), com `mpp_uid` como segunda chave. *Motivo:* `tarefa_id` é `ON DELETE SET NULL` — tarefa apagada deixa o snapshot órfão, e o `mpp_uid` é a identidade estável que o M02 criou justamente para isso.
- Por tarefa: `delta_inicio_dias`, `delta_fim_dias`, `delta_duracao_dias`, e situação em `{'no_prazo', 'adiantada', 'atrasada', 'nova', 'removida', 'renomeada'}`. Deltas em **dias úteis** (D6).
- Agregado: `desvio_termino_dias` (fim do projeto vigente − fim da baseline), `n_tarefas_atrasadas`, `n_novas`, `n_removidas`, e `desvio_termino_no_caminho_critico` — quanto do desvio está em tarefa crítica, que é o número que realmente importa.
- Sem baseline: devolve `{'tem_baseline': False}`, não erro. A tela mostra um convite a congelar.

**Rota:** `GET /obras/<int:obra_id>/cronograma/baseline/comparacao`.

**UI:** tabela na seção de versões da obra, com filtro "só as que mudaram" (numa obra de 300 tarefas, listar as 280 iguais esconde as 20 que interessam) e com as críticas destacadas.

**Testes:** obra idêntica à baseline ⇒ todos os deltas 0 e `desvio_termino_dias == 0`; empurrar uma tarefa em N dias úteis ⇒ delta exato N (e **não** N dias corridos — inclua um caso que atravessa fim de semana, senão o teste passa por acaso); tarefa nova aparece como `nova`; tarefa arquivada aparece como `removida`; casamento por `mpp_uid` funciona quando `tarefa_id` é `NULL`; sem baseline devolve `tem_baseline: False`; cross-tenant recusado.

**Commit:** `feat(fase7): comparativo baseline x cronograma vigente por tarefa e no total`

---

### Task 8 — Motor de EVM (`services/evm.py`)

**Files:**
- Create: `services/evm.py`
- Test: `tests/test_evm.py`

**Responsabilidade:** as onze grandezas do EVM. Como no CPM, o motor é **puro** e o coletor é separado — porque as fórmulas são normativas e testáveis hoje, enquanto as fontes dependem da Fase 6 (premissa P3).

**Parte pura (escreva assim — é PMBOK, não invenção):**

```python
# services/evm.py
"""Gerenciamento do Valor Agregado (EVM/GVA) — Fase 7.

Nomenclatura em português (PMBOK-BR), como o gestor de obra fala:
    VP  Valor Planejado      (PV, Planned Value  / BCWS)
    VA  Valor Agregado       (EV, Earned Value   / BCWP)
    CR  Custo Real           (AC, Actual Cost    / ACWP)
    OAC Orçamento na Conclusão (BAC, Budget at Completion)

Este módulo é PURO: recebe quatro números e devolve os indicadores.
Quem colhe VP/VA/CR/OAC do banco é `coletar_evm` mais abaixo, e a
decisão de o que é cada um está registrada em D3/D4 do plano
docs/superpowers/plans/2026-07-21-fase-7-planejamento-avancado-cpm-evm.md.
"""
from __future__ import annotations

# Limiares de farol — skill consultor-cronograma, Etapa 7 / Etapa 11.
IDC_INTERVENCAO = 0.80   # abaixo disto por 2 medições: intervenção obrigatória
IDP_REPLANEJAR = 0.70    # abaixo disto por 2 medições: replanejar urgente
IDCN_INATINGIVEL = 1.20  # acima disto: meta financeira provavelmente inatingível


def calcular_indicadores(vp: float, va: float, cr: float, oac: float) -> dict:
    """Indicadores de EVM a partir das quatro grandezas básicas.

    Divisões por zero devolvem None (não 0, não infinito): obra sem custo
    real ainda não tem IDC, e afirmar IDC=0 seria dizer que ela é
    infinitamente ineficiente. `None` é a resposta honesta e a UI mostra
    "—".
    """
    vc = va - cr           # Variação de Custo   (>0 abaixo do orçamento)
    vpr = va - vp          # Variação de Prazo   (>0 adiantado)

    idc = (va / cr) if cr else None      # Índice de Desempenho de Custo (CPI)
    idp = (va / vp) if vp else None      # Índice de Desempenho de Prazo (SPI)

    # EAC principal (D4): o desvio de custo persistirá até o fim.
    eac_persistente = (oac / idc) if idc else None
    # EAC alternativa: o desvio foi pontual, o resto sai pelo orçado.
    eac_pontual = cr + (oac - va)

    eac = eac_persistente if eac_persistente is not None else eac_pontual
    etc = eac - cr                       # Estimativa para Terminar
    vac = oac - eac                      # Variação na Conclusão (<0 estoura)

    # IDCN / TCPI: a eficiência que passa a ser NECESSÁRIA para fechar no OAC.
    denominador = oac - cr
    idcn = ((oac - va) / denominador) if denominador else None

    return {
        'vp': vp, 'va': va, 'cr': cr, 'oac': oac,
        'vc': vc, 'vpr': vpr,
        'idc': idc, 'idp': idp,
        'eac': eac, 'eac_persistente': eac_persistente,
        'eac_pontual': eac_pontual,
        'etc': etc, 'vac': vac, 'idcn': idcn,
    }


def avaliar_farois(ind: dict) -> dict:
    """Traduz os índices em situação. Limiares da skill consultor-cronograma.

    Devolve, para custo, prazo e meta: 'ok' | 'atencao' | 'critico' | None.
    """
    ...
```

**Parte de coleta — `coletar_evm(obra, data_ref) -> dict`.** Não é inventada: cada fonte já existe.

| Grandeza | Fonte já existente | Como |
|---|---|---|
| **OAC (BAC)** | `_previsto_por_categoria(osc)` — `services/cronograma_fisico_financeiro.py:200` | Soma sobre os `ObraServicoCusto` da obra (D3). Marcar `bac_origem: 'osc_previsto'` no payload |
| **VP** | `montar_fisico_financeiro(obra_id, admin_id)['curva_s']` — `services/cronograma_fisico_financeiro.py:218,346` | O `acumulado` do último mês ≤ `data_ref`. Já é o previsto faseado por dias úteis pelas datas das tarefas (`:315-327`) |
| **VA** | `alocar_por_peso(previsto_total, pesos)` (`:315`) × `calcular_progresso_rdo(tarefa_id, data_ref, admin_id)['percentual_realizado']` (`utils/cronograma_engine.py:429`) | **A única multiplicação nova de toda a fase.** Somar sobre as tarefas com valor alocado |
| **VA (fallback)** | `calcular_progresso_geral_obra_v2(obra_id, data_ref, admin_id)['progresso_geral_pct']` × OAC (`utils/cronograma_engine.py:510`) | Só quando não há **nenhum** `ItemMedicaoCronogramaTarefa`. Sempre com `va_origem: 'fallback_fisico'` e um aviso |
| **CR** | `curva_realizado(obra)` — `services/cronograma_fisico_financeiro.py:563` | Somar os meses ≤ `data_ref`. **Cuidado:** a granularidade da fonte é mensal, então `data_ref` no meio do mês inclui o mês inteiro. Documentar e expor `cr_granularidade: 'mensal'`, ou refinar a query para `data_referencia <= data_ref` — o dado tem data diária em `GestaoCustoFilho.data_referencia` (`models.py:5299`), o agrupamento por mês é escolha de `curva_realizado`, não limitação. **Recomendado: nova função com filtro por data**, deixando `curva_realizado` intocada para não quebrar `painel_financeiro` |

**Testes (`tests/test_evm.py`):**
- **Puros** (sem banco), o caso do relatório-modelo da skill: OAC 1.500.000, VP 600.000, VA 510.000, CR 540.000 ⇒ VC −30.000, VPr −90.000, IDC 0,944, IDP 0,850, EAC ≈ 1.589.000, VAC ≈ −89.000, IDCN ≈ 1,08. Tolerância explícita nos arredondamentos.
- Obra perfeita (VP=VA=CR) ⇒ IDC=IDP=1,0, VAC=0.
- `cr == 0` ⇒ `idc is None` e `eac` cai na fórmula pontual — **não** `ZeroDivisionError`, **não** `idc == 0`.
- `oac == cr` ⇒ `idcn is None`.
- Faróis: IDC 0,79 ⇒ `critico`; 0,95 ⇒ `atencao`; 1,05 ⇒ `ok`.
- **De coleta** (integração, `pytestmark = pytest.mark.integration`): obra com vínculo item↔tarefa produz `va_origem: 'peso_financeiro'`; obra sem nenhum vínculo produz `va_origem: 'fallback_fisico'` **e** aviso não vazio; obra sem custo previsto devolve OAC 0 e todos os índices `None` sem estourar; multitenant.

**Commit:** `feat(fase7): motor de EVM (VP/VA/CR, IDP/IDC, EAC/ETC/VAC/IDCN) com farois`

---

### Task 9 — EVM na tela: `pct_fisico` por etapa e painel de indicadores

**Files:**
- Modify: `services/cronograma_fisico_financeiro.py` (`:254`, `:315-327`, `:482-560`)
- Modify: `views/obras.py` (`financeiro_dados` em `:2089`)
- Modify: `templates/obras/detalhes_obra_profissional.html`, `static/js/financeiro_obra.js`
- Modify: `tests/test_importacao_fisico_financeiro.py` (asserts de `pct_fisico` — premissa P8)
- Test: `tests/test_evm_painel.py`

**Responsabilidade:** fechar o laço. Três entregas concretas:

1. **`pct_fisico` deixa de ser `None`.** Hoje o campo é inicializado como `None` em `services/cronograma_fisico_financeiro.py:254` e repassado em `:538` sem nunca ser calculado. Preencher para etapas do tipo `entregavel` (etapa `periodo` — indiretos, escritório, estadia — continua `None` **de propósito**, porque custo de período não tem avanço físico; o comentário em `:305-309` já explica). Cálculo: média dos `percentual_realizado` das tarefas vinculadas à etapa, ponderada pelo mesmo `peso` de `ItemMedicaoCronogramaTarefa` que já governa a alocação de valor em `:315`. **Consequência esperada:** `tests/test_importacao_fisico_financeiro.py:136` e `:338` afirmam hoje que `pct_fisico is None`; o de `:338` (etapas de período) continua correto, o de `:136` precisa mudar — no mesmo commit e com justificativa no corpo da mensagem.

2. **`painel_financeiro` (`:482`) ganha a chave `evm`** com os indicadores da data de hoje, a origem do VA, a origem do BAC e os avisos. Sai automaticamente por `/obras/<id>/financeiro/dados` (`views/obras.py:2089`), que já serializa o dicionário inteiro — nenhuma rota nova (D7).

3. **Card de EVM** no painel financeiro, com: os oito números, os faróis da Task 8, e a **curva de três séries** (VP, VA, CR acumulados por mês). Reusar o Chart.js que já desenha as 4 séries em `static/js/financeiro_obra.js:382-390`; o eixo de meses já é montado em `services/cronograma_fisico_financeiro.py:497-506`.

**Aviso obrigatório na tela** (não só no payload): quando `va_origem == 'fallback_fisico'`, dizer em texto que o Valor Agregado está sendo estimado pelo avanço físico porque a obra não tem vínculo item↔tarefa, e apontar onde criar o vínculo. *Motivo:* um IDC calculado por fallback é uma opinião, não uma medição — e vai para reunião de diretoria como se fosse medição.

**Testes:** `pct_fisico` de etapa entregável reflete o avanço ponderado; etapa de período continua `None`; `painel_financeiro` traz `evm` com as chaves esperadas; o endpoint serializa `Decimal` corretamente (o `_jsonable` de `views/obras.py:2096` já trata — assertar que nada vira string quebrada); obra sem cronograma não quebra o painel; multitenant.

**Commit:** `feat(fase7): EVM no painel financeiro da obra + pct_fisico por etapa`

---

### Task 10 — Fecho: gate, obra piloto e documentação

**Files:**
- Modify: `docs/superpowers/plans/2026-07-21-fase-7-fecho.md` (criar)
- Test: suíte completa

**Responsabilidade:** provar que funciona contra o dado real, não contra fixture.

**Passos:**
1. Rodar `bash run_tests.sh --gate` e anotar o resultado **contra a baseline de falhas pré-existentes** (há testes que exigem servidor vivo e já falhavam antes — registrado nos fechos M03/M05).
2. Rodar `bash run_tests.sh --java` — a família com JVM/MPXJ. Se o backfill da Task 2 tocar o caminho do parser, é aqui que aparece.
3. **Validação da obra piloto (critério de pronto da DEVOLUTIVA, `DEVOLUTIVA.md:256`):** importar `CRONOGRAMA 16.07.xml` na obra Baia, ligar a flag, calcular o CPM e **comparar o conjunto de tarefas críticas com o que o MS Project reporta** para o mesmo arquivo. Divergência aceitável: nenhuma na composição do caminho; até 1 dia útil na duração total, atribuível a arredondamento de lag (Task 4). Divergência maior ⇒ investigar antes de fechar, não depois.
4. Congelar a versão ativa da Baia como baseline, aplicar uma segunda importação, e conferir que o comparativo aponta os deltas certos.
5. Escrever o fecho no molde dos existentes (`docs/superpowers/plans/2026-07-21-modulo-06-fecho.md`): entregue, checklist, **ressalvas de execução (divergências deliberadas)**, fora de escopo mantido.

**Fora de escopo a registrar explicitamente no fecho:** agendamento honrando SS/FF/SF e lag (D5); nivelamento de recursos e histograma de mão de obra; linha de balanço; PERT de três pontos; simulação de cenários; relatórios por público (Word/PPT/HTML da skill); EVM por etapa individual (esta fase entrega EVM da obra e `pct_fisico` por etapa, não a matriz completa).

**Commit:** `docs(fase7): fecho — CPM validado contra o MS Project na obra piloto`

---

## 8. Riscos

| Risco | Probabilidade | Impacto | Mitigação já embutida no plano |
|---|---|---|---|
| **Caminho crítico não bate com o MS Project** — o Project usa restrições (`ConstraintType`), deadlines e calendários por tarefa que o parser **não lê** (`services/mpp_parser_worker.py:123-137`) | Alta | Alto — é o critério de pronto | D5 (CPM sobre datas importadas, não reagendadas) elimina a maior fonte de divergência. Task 10 mede a divergência antes de declarar pronto. Se restou divergência, a causa provável é restrição de tarefa: acrescentar `getConstraintType/Date` ao parser é uma tarefa nova pequena, não um redesenho |
| **Lag fracionário arredondado muda o caminho crítico** | Média | Médio | Task 4 arredonda explicitamente, registra `lags_arredondados` no relatório e tem teste. A Task 10 lista a divergência de 1 dia útil como aceitável e atribuível a isto |
| **`ItemMedicaoCronogramaTarefa` vazio na maioria das obras** ⇒ EV por fallback em quase toda a base | Média-alta | Alto — o IDC vira opinião | Premissa P6 manda medir **antes**. D4 exige aviso visível na tela, não só no payload. Se a medição confirmar o pior caso, a resposta certa é uma tela de vínculo item↔tarefa — que é escopo novo, não conserto desta fase |
| **BAC vivo faz o EAC de medição passada mudar** quando alguém edita o orçado | Alta enquanto a Fase 6 não fechar | Alto para uso contratual | Premissa P3. `bac_origem` no payload torna a troca rastreável. Até a Fase 6, o EVM é ferramenta de gestão interna, não peça de medição — dizer isso na tela |
| **CPM cai e derruba a aplicação de versão** | Baixa | Alto | Task 4 chama o CPM em pós-commit com `try/except`, no precedente exato de `_motor_pos_commit` (`services/cronograma_versao_service.py:430`) e da ressalva 1 do fecho do M06 |
| **Colunas derivadas ficam obsoletas** (alguém muda datas e a folga não recalcula) | Média | Médio | `cpm_calculado_em` permite detectar cache velho; `NULL` ≠ `0` impede confundir "não calculado" com "crítica". A UI mostra `—` |
| **Obra com ciclo de predecessoras** (o normalizador detecta na importação, `services/cronograma_normalizacao.py:229`, mas o backfill pode criar rede cíclica a partir de dados legados) | Baixa | Médio | Motor levanta `RedeCiclica`; adaptador não grava nada e devolve os nós envolvidos. Nunca inventa caminho crítico |
| **Rede grande estoura recursão** | Baixa | Médio | Task 3 exige DFS/ordenação **iterativa**, com o precedente de `services/cronograma_normalizacao.py:210` |
| **A Fase 7 chega e a Fase 1 renomeou `obra_required`** | Média | Baixo | Premissa P2 manda reconfirmar antes da primeira linha. Falha de import é ruidosa, não silenciosa |
| **Dois planos escrevem a migration 280** | Média | Alto — colisão silenciosa no registro | Premissa P1 manda conferir `migrations_to_run` antes de escrever |

## 9. Critérios de pronto

A Fase 7 está pronta quando **todos** os itens abaixo forem verificáveis por comando, não por leitura:

- [ ] `bash run_tests.sh --gate` verde, comparado à baseline de falhas pré-existentes anotada no início.
- [ ] `bash run_tests.sh --java` verde (ou pulando limpo, sem JDK).
- [ ] O motor puro de CPM passa no exemplo canônico da skill `consultor-cronograma` (Task 3, teste 1) — quadro completo de IC/TC/IT/TT/FT.
- [ ] **O conjunto de tarefas críticas calculado para `CRONOGRAMA 16.07.xml` é idêntico ao que o MS Project reporta para o mesmo arquivo**, e a duração total diverge em no máximo 1 dia útil (`DEVOLUTIVA.md:256`).
- [ ] Uma obra tem no máximo uma baseline vigente, provado por `IntegrityError` no `INSERT` direto — não só por caminho feliz.
- [ ] Comparativo baseline × vigente devolve delta correto em dias **úteis** para uma alteração que atravessa fim de semana.
- [ ] O motor de EVM reproduz o relatório-modelo da skill (IDC 0,944 / IDP 0,850 / EAC ≈ 1.589.000 / IDCN ≈ 1,08).
- [ ] Obra sem vínculo item↔tarefa produz `va_origem: 'fallback_fisico'`, aviso não vazio no payload **e** texto visível na tela.
- [ ] Com a flag desligada, o sistema se comporta **exatamente** como antes desta fase: nenhuma coluna nova é lida, nenhuma rota nova responde, `recalcular_cronograma` não chama o CPM.
- [ ] Nenhuma tarefa desta fase reimplementou algo da seção 1 — conferido lendo os diffs contra aquela tabela.

---

## 10. Autorrevisão

**Cobertura do escopo pedido.** Caminho crítico calculado: tarefas 2, 3, 4, 5. Baseline congelada e comparável: tarefas 6 e 7. EVM (IDP/IDC/EAC): tarefas 8 e 9. Rollout seguro: tarefas 1 e 10. Nenhum item do escopo ficou sem tarefa.

**Consistência de nomes entre tarefas.** `utils.cpm.calcular(nos, arestas) -> Resultado` (Task 3) é chamado por `services.cronograma_cpm_service.calcular_e_persistir` (Task 4), cujo cache é lido por `cronograma_views._tarefa_to_dict` (Task 5). `services.evm.calcular_indicadores(vp, va, cr, oac)` e `avaliar_farois(ind)` (Task 8) são consumidos por `painel_financeiro` (Task 9). `definir_baseline` / `baseline_vigente` (Task 6) são usados por `comparar_com_baseline` (Task 7). Colunas `folga_total_dias`, `folga_livre_dias`, `is_critica`, `cpm_calculado_em` aparecem com a mesma grafia nas tarefas 4, 5 e nos critérios de pronto.

**Numeração de migrations.** 280 (flag, Task 1), 281 (`tarefa_predecessora`, Task 2), 282 (colunas de CPM, Task 4), 283 (campos de baseline, Task 6). 284–289 ficam livres para desdobramentos. Nenhuma tarefa usa número fora da faixa reservada.

**O que este plano deliberadamente NÃO faz:** não reescreve `recalcular_cronograma`; não cria tabela de baseline; não cria endpoint novo para o EVM; não toca no parser, no normalizador nem no reconciliador; não implementa nivelamento de recursos, histograma, linha de balanço, PERT nem simulação de cenários — que a skill `consultor-cronograma` cobre e que são fases futuras, não esta.
