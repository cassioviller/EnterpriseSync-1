# Fase 8 — Financeiro avançado + exportação contábil para o Domínio (layout 11758)

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Fechar o ciclo financeiro do SIGE (conciliação bancária, competência × caixa, DRE por obra) e entregar a exportação mensal dos lançamentos de caixa para o Domínio Contabilidade no layout 11758, com de/para editável pela contabilidade e relatório de pendências.

**Architecture:** Duas partes com maturidade diferente, de propósito. A **Parte A (financeiro avançado)** depende de fases anteriores que ainda não existem — está escrita como plano de arquitetura e responsabilidades, não como TDD passo a passo, e tem uma seção obrigatória de premissas a reconfirmar. A **Parte B (Domínio 11758)** é contrato externo, não depende de nada que a Fase 4 vá mudar, e está escrita com profundidade cheia: núcleo puro (`services/dominio_layout.py`, `services/dominio_mapeamento.py`, `services/dominio_validacao.py`) sem DB nem Flask, uma ponte ORM fina (`services/dominio_export.py`), e o de/para vivendo em **tabelas de dados por tenant** (`conta_dominio`, `regra_conta_dominio`) para que a contabilidade edite sem deploy — o mesmo padrão que o ADR-0002 já adotou para a classificação.

**Tech Stack:** Flask 3 + Flask-Login, SQLAlchemy 2 (`models.py`), sistema de migrações próprio numerado (`migrations.py` + `migrations_to_run`, `run_migration_safe`), PostgreSQL, `openpyxl` (relatório de pendências), pytest (`bash run_tests.sh --gate`).

**Faixa de migrações reservada: 290–299.**

---

## Contexto verificado no código (leia antes de começar)

Tudo abaixo foi conferido em 2026-07-21 no commit `fb4147b`. Não são suposições.

### O que já existe no financeiro e **não será refeito**

| Peça | Onde | Estado |
|---|---|---|
| Razão de caixa (`FluxoCaixa`), com banco, categoria, obra, fornecedor e funcionário | `models.py:781-812` | funciona; `valor` já é `Numeric(15,2)` (`models.py:790`, migration 188 em `migrations.py:13803`) |
| Fluxo de caixa com **Previsto × Realizado** separados, série mensal e KPIs | `financeiro_service.py:437` (`calcular_fluxo_caixa`), `financeiro_service.py:730` (`agregar_fluxo_mensal`), tela em `financeiro_views.py:677` | funciona; a decisão de mostrar variação relativa e não saldo está no ADR-0003 |
| 45 categorias de fluxo de caixa de construção civil + grupos financeiros | `models.py:7192-7249` (`_DEFAULTS`, 9 ENTRADA + 36 SAIDA), `models.py:7150` (`GrupoFinanceiro`), migrations 178 (`migrations.py:13269`) e 182 (`migrations.py:13351`) | funciona |
| Classificação automática por **cadastro por tenant** com prioridade, exceções, condição de obra e gatilho extra | `services/classificador_cadastro.py` (módulo puro, 419 linhas), `models.py:7268` (`PalavraChaveCategoria`), migrations 190/191/192 (`migrations.py:12224/12305/12349`), ADR-0002 | funciona |
| Aprendizado: Memória Exata + Fila por Termo + regra refinada, com loop ao vivo no preview | `models.py:7303` (`PalavraChaveSugestao`), `models.py:7324` (`CorrecaoClassificacao`), `importacao_views.py:531-710`, `tests/test_aprendizado_classificacao.py`, `tests/test_classificador_cadastro.py` | funciona |
| Importador da planilha real de fluxo de caixa, com preview assinado por HMAC e dedup de reimportação | `services/importacao_excel.py:1789` (`ImportacaoFluxoCaixa.processar`), `:2129` (`importar`), `:2183` (`_ja_existe_saida`), `:2205` (`_ja_existe_entrada`) | funciona |
| Detecção de transferência interna e casamento de banco origem/destino pela descrição | `services/importacao_excel.py:1357` (`_eh_transferencia_interna`), `:1365` (`_match_bancos_transferencia`) | funciona — mas ver o buraco B abaixo |
| Contabilidade interna de partidas dobradas: balancete, razão, DRE mensal, balanço, auditoria, PDF e Excel | `contabilidade_views.py:515/655/690/976/995`, `contabilidade_utils.py:352/266/504/406/479/805/934/1065/1251` | funciona no nível do tenant |
| Motor de lançamento contábil automático a partir das operações V2 | `contabilidade_utils.py:1555` (`gerar_lancamento_contabil_automatico`), de/para em `contabilidade_utils.py:1448` (`MAPEAMENTO_CONTABIL`), 6 chamadores (`gestao_custos_views.py:759,893`; `financeiro_service.py:188`; `folha_pagamento_views.py:277`; `alimentacao_views.py:519`; `compras_views.py:717`; `transporte_views.py:254`) | funciona — mas ver o buraco C |
| Centro de custo contábil ligado à obra | `models.py:2541` (`CentroCustoContabil`, com `obra_id` em `models.py:2549`), telas em `contabilidade_views.py:1031-1348` | funciona |
| Contas a pagar / a receber com baixa parcial, estorno, calendário e fechamento de pagamentos | `financeiro_service.py:25/73/262/297`, `financeiro_views.py:125-676`, `:1019`, `:1100` | funciona |
| Despesas de escritório recorrentes **com competência explícita** | `models.py:7097` (`DespesaEscritorio`), `models.py:7121-7143` (`DespesaEscritorioOcorrencia`, com `competencia_ano`/`competencia_mes` e `uq_despesa_ocorrencia_mes`), `custos_escritorio_views.py:281/369` | funciona |
| Índice de leitura do razão por tenant e período | `migrations.py:14306-14308` (`idx_fluxo_caixa_admin_data`, migration 213) e `migrations.py:13831` (migration 186, `idx_fluxo_caixa_banco_data`) | funciona |

### Os buracos, todos conferidos

| # | Buraco | Evidência |
|---|---|---|
| **A** | **Nada de integração com o Domínio existe.** Zero ocorrências de "dominio"/"11758" em código. A tela `/contabilidade/sped` (`contabilidade_views.py:1351`) só **lê** `SpedContabil`; nada no repositório instancia esse modelo (única definição: `models.py:2678`; únicos usos: `contabilidade_views.py:7,1361,1362`) | grep completo |
| **B** | **Transferência entre contas nunca entra no razão.** O importador detecta, joga numa lista à parte e faz `continue` (`services/importacao_excel.py:1960-1973`). A lista viaja no payload assinado (`importacao_views.py:453,473,515,550,701`) e só aparece na tela; `ImportacaoFluxoCaixa.importar` (`services/importacao_excel.py:2129`) lê apenas `dados['saidas']` e `dados['entradas']` — nenhum `FluxoCaixa` de transferência é criado |
| **C** | **O DRE não enxerga as despesas do motor V2.** `calcular_dre_mensal` soma despesas nos prefixos `5.1.01/5.1.02/5.1.04/5.1.05/5.1.06` (`contabilidade_utils.py:596-600`) e CMV em `5.1.03` (`:590`), mas `MAPEAMENTO_CONTABIL` debita despesa em `6.1.01.002`, `6.1.02.002` e `6.1.01.001` (`contabilidade_utils.py:1451-1454`), contas semeadas por `_V2_CONTAS_SEED` (`contabilidade_utils.py:1465,1479,1480`). São **dois planos de contas incompatíveis** no mesmo repositório: `financeiro_seeds.py:67` define `5 = DESPESAS`, `contabilidade_utils.py:1465` define `6 = DESPESAS` |
| **D** | **`PlanoContas` é estruturalmente single-tenant.** A PK é `codigo VARCHAR(20)` **global** (`models.py:2501`), não `(admin_id, codigo)`. `seed_plano_contas_if_needed` insere com `ON CONFLICT (codigo) DO NOTHING` (`contabilidade_utils.py:1525`) depois de checar `COUNT(*) WHERE admin_id = :aid` (`:1511-1516`): do 2º tenant em diante o `COUNT` dá 0, o `INSERT` conflita em todas as linhas e **zero contas são criadas**, mas `_v2_seeded_admins.add(admin_id)` (`:1539`) marca como feito. `PlanoContas.get_conta_cached(admin_id, codigo)` (`models.py:2529-2533`) devolve `None` para esse tenant, e `criar_lancamento_automatico` (`contabilidade_utils.py:139-150`) grava `PartidaContabil.conta_codigo` apontando para a conta **de outro tenant** |
| **E** | **O DRE tem seções permanentemente zeradas.** Ele lê `4.2.01/4.2.02` (deduções), `4.3.01`/`5.2.01` (resultado financeiro) e `5.3.01/5.3.02` (IR/CSLL) em `contabilidade_utils.py:584,609,610,617,618`, e **nenhuma dessas contas existe** em `PLANO_CONTAS_CONSTRUCAO` (`financeiro_seeds.py:10-100`) nem em `_V2_CONTAS_SEED` (`contabilidade_utils.py:1459-1500`) |
| **F** | **Não existe DRE por obra.** `calcular_dre_mensal(admin_id, ano, mes)` (`contabilidade_utils.py:504`) e a rota `/contabilidade/dre` (`contabilidade_views.py:690`) não aceitam obra. Só `contabilizar_proposta_aprovada` (`contabilidade_utils.py:164-170`) associa centro de custo à obra; `gerar_lancamento_contabil_automatico` recebe `centro_custo_id=None` por padrão (`contabilidade_utils.py:1561`) |
| **G** | **Conciliação bancária é uma tabela órfã.** `ConciliacaoBancaria` (`models.py:2656-2667`) não tem `banco_id` (tem `conta_banco VARCHAR(50)` solto), não tem rota, nem serviço, nem template. Zero ocorrências de OFX no repositório |
| **H** | **Não há campo de competência no razão.** `FluxoCaixa` só tem `data_movimento` (`models.py:787`). Competência explícita só existe para despesa de escritório (`models.py:7127-7128`) |
| **I** | **Valor entra como `float` numa coluna `NUMERIC`.** `_parse_valor` devolve `float` (`financeiro_views.py:25-44`) e alimenta `FluxoCaixa.valor` em `financeiro_views.py:751` e `:818`; `_parse_float` (`services/importacao_excel.py:35`) alimenta `financeiro_views`-equivalentes em `services/importacao_excel.py:2334,2385,2494`. Já existe `_parse_decimal` (`services/importacao_excel.py:49`) e não é usado nesses três pontos |
| **J** | **`FluxoCaixa.obra_id` é nullable e o importador não usa a obra administrativa que ele mesmo cria.** Coluna nullable em `models.py:792`; o importador cria `000 - ADMINISTRATIVO / GERAL` em `services/importacao_excel.py:2160-2178` e define `_obra_efetiva` em `:2177`, mas grava `obra_id=obra_id` cru em `:2336`, `:2387` e `:2496` — `_obra_efetiva` só é usada no relatório de tela (`:2508`) |
| **K** | **`CentroCusto` e `CentroCustoContabil` são duas tabelas sem nenhuma ligação.** `FluxoCaixa.centro_custo_id` → `centro_custo` (`models.py:793`); `PartidaContabil.centro_custo_id` → `centro_custo_contabil` (`models.py:2587`). Não há FK, relationship nem coluna de vínculo entre elas. `CentroCusto.codigo` é `unique=True` **global** (`models.py:712`) |

### Duas correções ao que os documentos afirmam

1. **`docs/integracao-dominio.md:136` aponta `calcular_fluxo_caixa` (`financeiro_service.py:437`) como "seleção do período" da exportação. Está errado para este fim.** Essa função é um **projetor**: soma `ContaReceber` em aberto (`financeiro_service.py:460-475`) e `GestaoCustoPai` com status `PENDENTE/SOLICITADO/AUTORIZADO/PARCIAL` (`:481-518`) junto com o realizado. Previsto não pode ir para a contabilidade. A exportação lê **`FluxoCaixa` direto** por `data_movimento`.

2. **`ESTADO-ATUAL.md:126-128` diz que `gestao_custo_pai` tem "1.118 linhas 100% órfãs" por não ter `obra_id`. A coluna realmente não existe (`models.py:5210-5263`), mas as linhas não são órfãs:** a obra mora no filho (`GestaoCustoFilho.obra_id`, `models.py:5302`) e todo o código já filtra por lá (`financeiro_service.py:514-517` e `:544-548`, com o comentário explícito *"GestaoCustoPai não tem obra; filtra via filhos"*). A Fase 4 precisa decidir se **move** a obra para o pai ou se **formaliza** a leitura via filho — as duas mudam a forma do DRE por obra, e é por isso que a Parte A depende dela.

### Dependências de fase declaradas

| Fase | O que a Fase 8 consome | Bloqueia o quê |
|---|---|---|
| **Fase 1** (`utils/autorizacao.py`, `UsuarioObra`, `PapelObra`) | decorator de autorização nas rotas novas de `/financeiro/dominio` e no DRE por obra | Parte B, Task B16 (usa `@admin_required` de `auth.py` já consolidado pela Fase 1) e Parte A2 |
| **Fase 3** (compras com governança) | vínculo pedido → pagamento, para a conciliação de compromisso | Parte A5 apenas |
| **Fase 4** (centro de custo obrigatório) | `FluxoCaixa.obra_id` não-nulo; decisão sobre `gestao_custo_pai.obra_id`; de/para `CentroCusto` × `CentroCustoContabil` | **toda a Parte A** (A1, A2). **Não bloqueia a Parte B** — ver Decisão D4 |
| **Fase 6** (orçamento versionado) | qual versão é a linha de base do orçado × real | Parte A6 apenas |

**A Parte B pode ser executada antes das Fases 1, 3, 4 e 6**, com uma única adaptação: usar o `admin_required` que existe hoje em `auth.py:21` em vez do consolidado da Fase 1.

---

## Decisões que precisam do Cássio

Todas já vêm com **recomendação adotada** — o plano segue com elas. Nenhuma bloqueia a execução; o que precisa de confirmação está marcado como tal.

### D1 — De onde vem o plano de contas do Domínio

**Recomendado: tabela nova `conta_dominio`, por tenant, alimentada por upload de CSV da contabilidade. Não reaproveitar `plano_contas`.**

Fundamento: `plano_contas.codigo` é PK **global** (`models.py:2501`) — dois tenants não podem ter o mesmo código, e o buraco D mostra que isso já quebra o seed hoje. Além disso o Domínio identifica conta por **código reduzido** (numérico curto), que é outro identificador, não o código hierárquico `1.1.01.002`. Misturar os dois arrastaria a contabilidade interna — que já roda em produção via `MAPEAMENTO_CONTABIL` — para dentro de uma migração de PK de alto risco.

*Precisa do contador:* o arquivo do plano de contas da Veks (código reduzido, nome, classificação). Sem ele o de/para nasce vazio e **100% das linhas caem em pendência** — o que é o comportamento correto e esperado no mês de calibração (`docs/integracao-dominio.md:31-32`).

### D2 — Regime: competência ou caixa

**Recomendado: caixa, e só caixa, para o Domínio.**

Fundamento: o princípio misto do contrato (`docs/integracao-dominio.md:62-64`) diz que a nota fiscal já chega à contabilidade por outro caminho; o que o SIGE exporta é o **movimento de caixa**, que dá baixa em Clientes/Fornecedores. Exportar competência duplicaria receita e compra — que é exatamente o que a regra 2 (`docs/integracao-dominio.md:84-86`) proíbe. A visão de competência fica **interna** (Parte A3 e o DRE por obra), nunca sai para o Domínio.

### D3 — O que exportar

**Recomendado: as linhas de `FluxoCaixa` do tenant com `data_movimento` no período, e nada mais.**

Fundamento: ver correção 1 acima. `calcular_fluxo_caixa` mistura previsto com realizado. `FluxoCaixa` é o razão de caixa e tem índice para essa consulta (`idx_fluxo_caixa_admin_data`, `migrations.py:14306`).

### D4 — Lançamento sem centro de custo

**Recomendado: não bloqueia a exportação e não vira pendência do Domínio.**

Fundamento: o contrato manda **filial e centros de custo débito/crédito em branco até confirmação de uso** (`docs/integracao-dominio.md:46-47`). Bloquear por um campo que sai vazio tornaria a Fase 8 refém da Fase 4 num ponto onde o contrato externo não pede nada. O lançamento sem obra entra no **resumo de processamento** como alerta contado, e no relatório interno de higiene — não no relatório de pendências, que é sobre conta contábil.

Quando a contabilidade confirmar o uso de centro de custo, a amarração já está prevista: `conta_dominio` tem coluna `tipo`, e o mapeamento `Obra → centro de custo do Domínio` entra como linhas `tipo='CENTRO_CUSTO'` na mesma tabela, sem migração nova. *Precisa do contador:* confirmar se usa centro de custo, e com que códigos.

### D5 — Transferências entre contas

**Recomendado: persistir o par em `FluxoCaixa` com `transferencia_par_id` (FK para si mesma), e o exportador colapsa pelo FK — não por heurística de (valor, data).**

Fundamento: hoje a transferência é **descartada** no preview e nunca vira lançamento (buraco B). Consequência: o razão de caixa está incompleto e o saldo por banco não fecha, o que também é pré-requisito da conciliação (A5). A regra 1 do contrato (`docs/integracao-dominio.md:79-83`) manda colapsar duas linhas em uma; com o par explícito isso é determinístico. Casar por `(valor, data)` — como a rotina original fazia sobre a planilha crua — produziria falso-positivo em qualquer dia com duas transferências de mesmo valor.

### D6 — Quem dispara e com que periodicidade

**Recomendado: manual, mensal, pelo ADMIN, num botão em `/financeiro/dominio`. Cada execução gravada em `exportacao_dominio`.**

Fundamento: `docs/integracao-dominio.md:150` deixa isso em aberto e `:31-32` diz que o primeiro mês é calibração com volume alto de pendências. Job agendado gera arquivo que ninguém revisa — e a validação de cobertura de 20% (`docs/integracao-dominio.md:105-106`) existe justamente para forçar revisão humana. O registro por execução dá idempotência (não reexportar o mesmo período sem querer) e trilha de auditoria.

### D7 — Fornecedor nominal vs genérico

**Recomendado: `fornecedor.conta_dominio_id` quando preenchido; senão a conta genérica de Fornecedores da regra. O matching por texto roda como *sugestão* na tela de de/para, nunca decidindo na exportação.**

Fundamento: a regra 3 do contrato (`docs/integracao-dominio.md:87-89`) pede comparação *case-insensitive* sem acentos — que é exatamente o mecanismo que o ADR-0002 tirou do código e transformou em cadastro editável. Repetir o hardcode aqui seria regressão do ADR. A função de normalização já existe e é reutilizável: `services/classificador_cadastro.py:69` (`_norm`).

### D8 — Codificação e o caractere `→`

**Recomendado: gerar em `cp1252` (Windows-1252) e usar `->` no template de transferência, não `→`.**

Fundamento: o template do contrato (`docs/integracao-dominio.md:58`) usa `→` (U+2192), que **não existe em cp1252**. Sistemas contábeis brasileiros importam CSV em ANSI por padrão. *Precisa do contador:* confirmar encoding — está listado como lacuna do contrato abaixo, e o código isola isso numa constante única.

---

## Lacunas do contrato 11758 — o que `docs/integracao-dominio.md` **não** diz

O documento especifica formato, regras de processamento, validações e templates de histórico, mas **não fixa o registro físico**. Estes pontos precisam de um arquivo-modelo real ou da confirmação da contabilidade antes da primeira entrega. Nenhum deles bloqueia a implementação: todos moram em constantes isoladas em `services/dominio_layout.py`, com um teste que trava a resposta assim que o arquivo-modelo chegar.

| # | O que falta | Onde o documento chega perto |
|---|---|---|
| 1 | **A ordem das colunas.** O doc lista os campos (data, débito, crédito, valor, código de histórico, complemento, filial, inicia lote, centros de custo) mas nunca diz em que sequência saem | `docs/integracao-dominio.md:22` diz que a ordem "é reaproveitável integralmente" da rotina original — que não está neste repositório |
| 2 | **Quantas colunas o registro tem no total** e se há colunas depois de centro de custo crédito | — |
| 3 | **Se existe linha de cabeçalho** | — |
| 4 | **Encoding do arquivo** (ANSI/cp1252, UTF-8, UTF-8 com BOM) | `:35-36` só fala do separador |
| 5 | **Terminador de linha** (CRLF ou LF) e se há `;` no fim da linha | — |
| 6 | **O que é "código reduzido"** — número inteiro, string com zeros à esquerda, largura fixa | `:124-125` cita "código reduzido" sem definir o formato |
| 7 | **O valor de `inicia lote` para as linhas seguintes de um lote composto.** O doc só define `1` para lançamento simples | `:45` |
| 8 | **Se `filial` em branco é campo vazio ou `0`** | `:46-47` |
| 9 | **Limite exato do complemento histórico.** "~60 caracteres" não diz se é truncar ou rejeitar | `:44` |
| 10 | **Como o `→` do template de transferência deve ser codificado** | `:58` |
| 11 | **Que partida usar para aporte de sócios, empréstimo recebido, venda de ativo, rendimento financeiro e devolução.** A tabela de partida/contrapartida tem 8 linhas e nenhuma cobre esses casos — que são 5 das 45 categorias de `CategoriaFluxoCaixa._DEFAULTS` (`models.py:7192-7249`) | `:66-75` |

**Ação:** pedir à contabilidade **um arquivo `.csv` de importação já aceito pelo Domínio** (qualquer mês, qualquer empresa). Ele resolve as lacunas 1–8 de uma vez. Enquanto não chegar, `tests/test_dominio_layout.py::test_ordem_bate_com_arquivo_modelo` fica `skip` com motivo explícito e o resumo de processamento sai com o aviso `LAYOUT NÃO CONFERIDO`.

---

## Arquivos que esta fase cria ou altera

| Arquivo | Responsabilidade |
|---|---|
| `services/dominio_layout.py` | **novo** — puro. Formatação de campo (data, valor, complemento), templates de histórico, ordem das colunas, montagem da linha e do arquivo. Único lugar que conhece o formato físico do 11758 |
| `services/dominio_mapeamento.py` | **novo** — puro. Value objects, situação → partida/contrapartida, fornecedor nominal, descartes automáticos, colapso do par de transferência. Único lugar que conhece a regra contábil |
| `services/dominio_validacao.py` | **novo** — puro. As 6 validações bloqueantes de `docs/integracao-dominio.md:100-106` |
| `services/dominio_export.py` | **novo** — ponte ORM → puro. Lê `FluxoCaixa` + de/para, chama o núcleo, grava auditoria, devolve os 3 artefatos |
| `dominio_views.py` | **novo** — blueprint `/financeiro/dominio`: de/para, upload do plano de contas, disparo, download |
| `models.py` | `ContaDominio`, `RegraContaDominio`, `ExportacaoDominio`, `ExportacaoDominioPendencia`; colunas `conta_dominio_id` em `BancoEmpresa` e `Fornecedor`; `transferencia_par_id` em `FluxoCaixa` |
| `migrations.py` | migrations **290–295** + registro em `migrations_to_run` (após a linha 4014) |
| `app.py` | registro do blueprint, no bloco de `try/except` depois de `financeiro_bp` (`app.py:726-731`) |
| `services/importacao_excel.py` | passa a persistir o par de transferência (`:1960-1973`, `:2129`); troca `_parse_float` por `_parse_decimal` em `:2334,2385,2494` |
| `importacao_views.py` | passa `transferencias` adiante na confirmação (`:453,473,550,701`) |
| `financeiro_views.py` | `_parse_valor` devolve `Decimal` (`:25-44`, consumidores em `:751,818`) |
| `templates/financeiro/dominio_*.html` | **novos** — de/para, plano de contas, histórico de exportações |
| `tests/test_dominio_layout.py` | **novo** — formatação e ordem das colunas |
| `tests/test_dominio_mapeamento.py` | **novo** — partida/contrapartida, fornecedor, descartes, transferência |
| `tests/test_dominio_validacao.py` | **novo** — as 6 bloqueantes |
| `tests/test_dominio_export.py` | **novo** — ciclo completo com DB |
| `tests/fixtures/dominio/modelo_11758.csv` | **novo** — arquivo-modelo da contabilidade (a receber) |

---

# PARTE A — Financeiro avançado

> **Profundidade deliberadamente reduzida.** Esta parte depende das Fases 1, 3, 4 e 6, que ainda não existem. Escrever TDD passo a passo aqui seria inventar a forma de código que a Fase 4 ainda vai decidir. O que segue são **tarefas com arquivo, responsabilidade, risco e critério de pronto** — o detalhe entra numa revisão deste plano depois que a Fase 4 fechar.

## Premissas a reconfirmar antes de executar a Parte A

Nenhuma tarefa da Parte A deve começar antes de responder estas sete. Cada uma tem a evidência do estado de HOJE ao lado; a pergunta é se a fase intermediária mudou aquilo.

| # | Premissa | Como está hoje | Por que trava |
|---|---|---|---|
| 1 | **`FluxoCaixa.obra_id` ficou obrigatório?** | nullable (`models.py:792`); o importador cria a obra `000 - ADMINISTRATIVO / GERAL` (`services/importacao_excel.py:2160-2178`) mas grava `obra_id` cru em `:2336,2385,2496` — `_obra_efetiva` (`:2177`) só serve ao relatório de tela | sem obra em toda linha, DRE por obra e orçado × real não fecham |
| 2 | **A obra do custo mudou de lugar?** | continua no filho (`GestaoCustoFilho.obra_id`, `models.py:5302`); `gestao_custo_pai` não tem a coluna (`models.py:5210-5263`); as consultas por obra usam `.itens.any(...)` (`financeiro_service.py:516,547`) | se a Fase 4 mover a obra para o pai, o rateio do DRE por obra muda de agregação, não só de filtro |
| 3 | **O de/para `CentroCusto` × `CentroCustoContabil` foi criado?** | não existe nenhum vínculo — `FluxoCaixa.centro_custo_id` → `centro_custo` (`models.py:793`), `PartidaContabil.centro_custo_id` → `centro_custo_contabil` (`models.py:2587`), sem FK entre as tabelas | o DRE por obra lê pela partida contábil; o razão de caixa lê pelo centro operacional. Sem ponte, são dois números diferentes |
| 4 | **A PK global de `PlanoContas` foi corrigida?** | PK é `codigo` (`models.py:2501`); `seed_plano_contas_if_needed` faz `ON CONFLICT (codigo) DO NOTHING` (`contabilidade_utils.py:1525`) e do 2º tenant em diante semeia zero contas marcando como feito (`:1539`) | qualquer número contábil por tenant é suspeito enquanto isso durar |
| 5 | **`BancoEmpresa.saldo_atual` passou a ser mantido?** | o ADR-0003 registra que fica em 0 na prática; `saldo_inicial`/`saldo_atual` em `models.py:1834-1835`, `data_saldo_inicial` em `:1836` (migration 186) | conciliação sem saldo de abertura confiável não fecha, e a tela hoje mostra variação relativa justamente por isso |
| 6 | **A Fase 3 criou o vínculo pedido de compra → pagamento?** | `PedidoCompra` ganhou `obra_servico_custo_id` na migration 205 (`migrations.py:4006`), mas não há coluna ligando pagamento a pedido em `GestaoCustoPai` (`models.py:5210-5263`) nem em `FluxoCaixa` (`models.py:781-812`) | sem ele não existe "conciliação de compromisso" (A5, parte 2) |
| 7 | **Qual versão do orçamento é a linha de base?** | a Fase 6 decide; a pergunta 1 de `DEVOLUTIVA.md` ainda está aberta (Proposta versiona, `Orcamento` não) | o farol por categoria (A6) compara realizado contra orçado — precisa saber contra qual |

## A1 — Unificar o plano de contas interno e torná-lo por tenant

**Risco: alto.** Migração de PK numa tabela com dados e com duas FKs apontando para ela.

**Arquivos e responsabilidades:**
- `models.py:2498-2511` — `PlanoContas` passa a ter `id` como PK e `UniqueConstraint(admin_id, codigo)`. `conta_pai_codigo` vira `conta_pai_id`.
- `models.py:2586` — `PartidaContabil.conta_codigo` (FK para `plano_contas.codigo`) vira `conta_id`.
- `models.py:5253` — `GestaoCustoPai.conta_contabil_codigo` (String sem FK, com nota explicativa em `:5254-5256`) passa a ter FK real.
- `contabilidade_utils.py:1448-1455` (`MAPEAMENTO_CONTABIL`) e `:1459-1500` (`_V2_CONTAS_SEED`) — reconciliar com `financeiro_seeds.py:10-100` (`PLANO_CONTAS_CONSTRUCAO`). **Escolher um dos dois dialetos** (`5 = DESPESAS` do `financeiro_seeds` ou `6 = DESPESAS` do V2) e migrar o outro, incluindo as `PartidaContabil` já gravadas.
- `contabilidade_utils.py:1502-1552` (`seed_plano_contas_if_needed`) — remover o `ON CONFLICT (codigo)`, que deixa de fazer sentido.
- `contabilidade_utils.py:584,590,596-600,609,610,617,618` (`calcular_dre_mensal`) — os prefixos passam a bater com o dialeto único; criar as contas de dedução (`4.2.x`), resultado financeiro (`4.3.01`, `5.2.01`) e IR/CSLL (`5.3.x`) que hoje não existem em nenhum dos dois seeds.
- `migrations.py` — migration **296**.

**Pronto quando:** dois tenants novos recebem cada um o plano completo; o DRE de um tenant com lançamento V2 de alimentação mostra a despesa (hoje mostra zero — buraco C); as seções de dedução, resultado financeiro e IR deixam de ser estruturalmente zeradas (buraco E).

## A2 — DRE por obra

**Depende de:** A1 e das premissas 1, 2 e 3.

**Arquivos e responsabilidades:**
- `services/dre_obra.py` — **novo**, puro. Recebe as partidas já carregadas e devolve a estrutura de 11 seções por obra. A lógica de seções sai de `contabilidade_utils.py:580-624` e passa a ser reutilizada pelo DRE do tenant, para não ter duas fórmulas.
- `contabilidade_utils.py:504` — `calcular_dre_mensal` ganha `obra_id=None` e delega ao módulo puro.
- Os 6 chamadores de `gerar_lancamento_contabil_automatico` (`gestao_custos_views.py:759,893`, `financeiro_service.py:188`, `folha_pagamento_views.py:277`, `alimentacao_views.py:519`, `compras_views.py:717`, `transporte_views.py:254`) passam a resolver o `centro_custo_id` da obra em vez de deixar o default `None` (`contabilidade_utils.py:1561`).
- `contabilidade_views.py:690` e `templates/contabilidade/dre.html` — seletor de obra.
- `migrations.py` — migration **297**: backfill de `CentroCustoContabil` para toda obra ativa que ainda não tem (hoje só `contabilizar_proposta_aprovada` cria, `contabilidade_utils.py:164-170`).

**Pronto quando:** a soma dos DREs por obra do mês, mais o DRE do centro de custo administrativo, é igual ao DRE do tenant no mesmo mês, com diferença zero.

## A3 — Competência ao lado de caixa no razão

**Arquivos e responsabilidades:**
- `models.py:787` — `FluxoCaixa.data_competencia DATE`, nullable.
- `migrations.py` — migration **298**: adiciona a coluna, faz backfill `data_competencia = data_movimento` e cria `idx_fluxo_caixa_admin_competencia`.
- `financeiro_views.py:677` e `templates/financeiro/fluxo_caixa.html` — seletor **Caixa | Competência** que troca a coluna do filtro. Sem seletor, o comportamento é idêntico ao de hoje.
- `financeiro_views.py:740,801` — o formulário de lançamento e a edição inline aceitam a competência.

**Princípio:** competência só difere de caixa quando o usuário informar. Nada é inferido. O ADR-0003 já estabeleceu que não se inventa número financeiro que o dado não sustenta — a mesma regra vale aqui.

**Pronto quando:** o mesmo período consultado nos dois regimes dá o mesmo total enquanto ninguém informou competência divergente; e o relatório de escritório (`custos_escritorio_views.py:281`), que já pensa em competência (`models.py:7127-7128`), passa a bater com o fluxo em regime de competência.

## A4 — Higiene numérica: `Decimal` da entrada ao banco

**Risco: baixo. Independe das outras fases — pode ser feita já.**

**Arquivos e responsabilidades:**
- `financeiro_views.py:25-44` — `_parse_valor` devolve `Decimal`, não `float`. Consumidores: `:751` (`abs(_parse_valor(...))` → `FluxoCaixa.valor`) e `:818` (edição inline).
- `services/importacao_excel.py:2334,2385,2494` — trocar `valor` (`float`, de `_parse_float` em `:35`) por `_parse_decimal` (`:49`), que já existe e já é usado nos `ContaPagar`/`ContaReceber` vizinhos (`:2417,2472`).
- `financeiro_views.py:826` — `round(fc.valor, 2)` sobre `Decimal` devolve `Decimal`; conferir a serialização do `jsonify`.

**Pronto quando:** um lançamento de `R$ 1.234,57` importado e reeditado sai do banco com o centavo intacto, e nenhum caminho de escrita em `FluxoCaixa.valor` passa por `float`. A coluna é `NUMERIC(15,2)` desde a migration 188 (`migrations.py:13803`) — esta tarefa fecha o lado da aplicação.

## A5 — Conciliação bancária

**Depende de:** premissa 5 (saldo mantido) e, para a parte de compromisso, da premissa 6.

**Recomendado: não reaproveitar `ConciliacaoBancaria`.** O modelo (`models.py:2656-2667`) não tem `banco_id` — tem `conta_banco VARCHAR(50)` solto — e não tem rota, serviço nem template. Adaptá-lo custa mais do que criar o par certo.

**Arquivos e responsabilidades:**
- `models.py` — `ExtratoBancario` (banco_id, período, origem, hash do arquivo) e `ExtratoLinha` (data, histórico, valor `Numeric(15,2)`, tipo, `fluxo_caixa_id` nullable, status).
- `services/extrato_ofx.py` — **novo**, puro. Parser OFX. Zero ocorrências de OFX no repositório hoje; a dependência entra no `requirements`.
- `services/conciliacao.py` — **novo**, puro. Casamento por `(banco, valor exato, data ±3 dias)`, uma linha de extrato para no máximo um `FluxoCaixa`. O resto vai para fila de exceção — **nunca casamento aproximado silencioso**, pelo mesmo motivo do ADR-0002.
- `migrations.py` — migration **299**.

**Pronto quando:** um extrato OFX de um mês fechado concilia acima de 90% automaticamente, e o saldo final do extrato bate com `saldo_inicial` do banco (`models.py:1834`) somado aos movimentos conciliados. Isso é o que permite a tela de fluxo evoluir de variação relativa para saldo absoluto, como o ADR-0003 antecipa.

**Nota de sequenciamento:** a Parte B, Task B11, é pré-requisito desta tarefa — sem as transferências no razão (buraco B), a conciliação vai reprovar toda transferência entre contas próprias.

## A6 — Farol por categoria e projeção de 90 dias

**Depende de:** premissa 7 (qual versão do orçamento é a linha de base).

**Arquivos e responsabilidades:**
- `financeiro_service.py:730` (`agregar_fluxo_mensal`) — já produz série mensal e KPIs a partir dos detalhes; a projeção estende a mesma série.
- `services/farol_categoria.py` — **novo**, puro. Realizado por `CategoriaFluxoCaixa` no período contra o orçado da versão de base, com faixa de tolerância cadastrável.
- `templates/financeiro/fluxo_caixa.html` — o farol entra na tela que já existe, não numa nova.

**Pronto quando:** o farol de uma obra piloto reproduz, categoria a categoria, o que hoje é conferido na planilha.

## Riscos da Parte A

| Risco | Mitigação |
|---|---|
| A1 mexe em PK de tabela com dados e em duas FKs. Falha parcial deixa a contabilidade inconsistente | migration numa transação só (`with db.engine.begin()`, padrão de `migrations.py:13831`); dump antes; `run_migration_safe` (`migrations.py:146`) grava `failed` sem derrubar o boot (`:187-198`) — mas **não** faz rollback lógico, então o roteiro de reversão tem de ser escrito à mão |
| A2 pode produzir DRE por obra que não soma o DRE do tenant, se algum lançamento ficar sem centro de custo | o critério de pronto é justamente a soma bater; a diferença vai para uma linha "sem centro de custo" visível, nunca diluída |
| Escolher o dialeto errado do plano de contas em A1 força retrabalho em A2 e no de/para do Domínio | decidir com o contador **antes** de A1; é a mesma conversa do D1 |


---

# PARTE B — Exportação para o Domínio (layout 11758)

> **Profundidade cheia.** Contrato externo, independente das fases 1/3/4/6. TDD passo a passo.
>
> Ordem de construção: núcleo puro primeiro (B1–B7, sem DB e sem Flask, testes que rodam em milissegundos), depois schema (B8–B13), depois a ponte ORM (B14–B15), depois a interface (B16–B17).

## Convenções de teste desta parte

- Testes dos módulos puros (B1–B7): **não** importam `app`, `models` nem `main`. Rodam isolados.
- Testes com banco (B8 em diante): `import main` no topo (registra os blueprints), `pytestmark = pytest.mark.integration`, login por injeção de sessão (`sess['_user_id'] = str(user_id)`), no padrão de `tests/test_fase0_autorizacao.py:20-60` e `tests/test_endpoint_classificar_termo.py:56-61`.
- Gate: `bash run_tests.sh --gate` (`pytest tests/ -m "not browser"`).

---

## Task B1: Formatação de campo do layout 11758

**Files:**
- Create: `services/dominio_layout.py`
- Test: `tests/test_dominio_layout.py`

- [ ] **Step 1: Escreva o teste que falha**

Crie `tests/test_dominio_layout.py`:

```python
"""Layout 11758 do Domínio — formatação física do arquivo.

Contrato externo, especificado em docs/integracao-dominio.md:34-58. Este
módulo é o ÚNICO lugar do sistema que conhece separador, ordem de colunas,
formato de data e de valor. Tudo mais fala em value objects.

Módulo puro: sem DB, sem Flask.
"""
import os
import sys
from datetime import date
from decimal import Decimal

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from services.dominio_layout import (
    formatar_data,
    formatar_valor,
    truncar_complemento,
)


def test_data_sai_em_dd_mm_aaaa():
    assert formatar_data(date(2026, 3, 7)) == "07/03/2026"


def test_valor_usa_virgula_decimal_e_duas_casas():
    assert formatar_valor(Decimal("1234.5")) == "1234,50"


def test_valor_nunca_tem_separador_de_milhar():
    assert formatar_valor(Decimal("1234567.89")) == "1234567,89"


def test_valor_sai_sempre_positivo():
    assert formatar_valor(Decimal("-980.00")) == "980,00"


def test_valor_arredonda_meio_para_cima():
    # ROUND_HALF_UP: a contabilidade não aceita o banker's rounding do Python
    assert formatar_valor(Decimal("0.005")) == "0,01"


def test_valor_nao_passa_por_float():
    # 0.1 + 0.2 em float dá 0.30000000000000004; em Decimal dá 0.3
    assert formatar_valor(Decimal("0.1") + Decimal("0.2")) == "0,30"


def test_valor_zero_e_recusado():
    # docs/integracao-dominio.md:103 — nenhum valor <= 0
    with pytest.raises(ValueError):
        formatar_valor(Decimal("0.00"))


def test_complemento_trunca_em_60_caracteres():
    texto = "A" * 100
    assert len(truncar_complemento(texto)) == 60


def test_complemento_curto_passa_intacto():
    assert truncar_complemento("Tarifa bancária: TED") == "Tarifa bancária: TED"


def test_complemento_nao_deixa_separador_de_campo_vazar():
    # ';' dentro do texto quebraria o CSV inteiro
    assert ";" not in truncar_complemento("Pgto fornecedor: ACME; LTDA")
```

- [ ] **Step 2: Rode e veja falhar**

Run: `pytest tests/test_dominio_layout.py -v`
Expected: `ModuleNotFoundError: No module named 'services.dominio_layout'`

- [ ] **Step 3: Implementação mínima**

Crie `services/dominio_layout.py`:

```python
"""Layout 11758 — Domínio Contabilidade, importação "Lançamentos Contábeis
em Lote — Excel (3.1)".

Módulo PURO — sem DB, sem Flask. É o único lugar do sistema que conhece o
formato físico do arquivo. Contrato em docs/integracao-dominio.md:34-58.
"""
from decimal import Decimal, ROUND_HALF_UP

SEPARADOR = ";"
LIMITE_COMPLEMENTO = 60


def formatar_data(d) -> str:
    """DD/MM/AAAA (docs/integracao-dominio.md:40)."""
    return d.strftime("%d/%m/%Y")


def formatar_valor(v) -> str:
    """Duas casas, vírgula decimal, sem milhar, sempre positivo
    (docs/integracao-dominio.md:37-39).

    Recebe Decimal. NUNCA converter para float no caminho: FluxoCaixa.valor
    é NUMERIC(15,2) desde a migration 188 e a precisão é do contrato.
    """
    if v is None:
        raise ValueError("valor ausente")
    d = Decimal(v).copy_abs().quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    if d <= 0:
        raise ValueError(f"valor deve ser maior que zero: {v}")
    return f"{d:.2f}".replace(".", ",")


def truncar_complemento(texto) -> str:
    """Complemento histórico: ~60 caracteres (docs/integracao-dominio.md:44).

    Trunca em vez de rejeitar, e remove o separador de campo — um ';' no
    meio do texto deslocaria todas as colunas seguintes da linha.
    """
    s = str(texto or "").replace(SEPARADOR, ",").replace("\n", " ").replace("\r", " ")
    return s.strip()[:LIMITE_COMPLEMENTO]
```

- [ ] **Step 4: Rode e veja passar**

Run: `pytest tests/test_dominio_layout.py -v`
Expected: 10 passed

- [ ] **Step 5: Commit**

```bash
git add services/dominio_layout.py tests/test_dominio_layout.py
git commit -m "feat(dominio): formatacao de campo do layout 11758"
```

---

## Task B2: Templates de complemento histórico

**Files:**
- Modify: `services/dominio_layout.py`
- Test: `tests/test_dominio_layout.py`

- [ ] **Step 1: Escreva o teste que falha**

Acrescente a `tests/test_dominio_layout.py`:

```python
from services.dominio_layout import montar_complemento


def test_complemento_de_despesa():
    assert montar_complemento(
        "DESPESA", categoria="Despesas Administrativas",
        subcategoria="Energia Elétrica", descricao="CEMIG fatura 03/2026",
    ) == "Despesas Administrativas: Energia Elétrica ref. CEMIG f"


def test_complemento_de_fornecedor():
    assert montar_complemento(
        "FORNECEDOR", nome="Aço Norte Distribuidora",
    ) == "Pgto fornecedor: Aço Norte Distribuidora"


def test_complemento_de_cliente_usa_a_data_formatada():
    from datetime import date
    assert montar_complemento("CLIENTE", data=date(2026, 3, 7)) == (
        "Receb. cliente conforme fluxo de caixa 07/03/2026"
    )


def test_complemento_de_tarifa():
    assert montar_complemento(
        "TARIFA", subcategoria="TED",
    ) == "Tarifa bancária: TED"


def test_complemento_de_transferencia_usa_seta_ascii():
    # docs/integracao-dominio.md:58 escreve '→' (U+2192), que não existe em
    # cp1252. Decisão D8: usar '->'.
    assert montar_complemento(
        "TRANSFERENCIA", origem="Itaú CC", destino="Nubank",
    ) == "Transf. entre contas: Itaú CC -> Nubank"


def test_complemento_desconhecido_estoura():
    with pytest.raises(KeyError):
        montar_complemento("INEXISTENTE")
```

- [ ] **Step 2: Rode e veja falhar**

Run: `pytest tests/test_dominio_layout.py -k complemento -v`
Expected: `ImportError: cannot import name 'montar_complemento'`

- [ ] **Step 3: Implementação mínima**

Acrescente a `services/dominio_layout.py`:

```python
# Templates de complemento histórico (docs/integracao-dominio.md:52-58).
# A seta do documento é '→' (U+2192), inexistente em cp1252 — decisão D8
# do plano da Fase 8 troca por '->'.
TEMPLATES_HISTORICO = {
    "DESPESA":       "{categoria}: {subcategoria} ref. {descricao}",
    "FORNECEDOR":    "Pgto fornecedor: {nome}",
    "CLIENTE":       "Receb. cliente conforme fluxo de caixa {data}",
    "TARIFA":        "Tarifa bancária: {subcategoria}",
    "TRANSFERENCIA": "Transf. entre contas: {origem} -> {destino}",
}


def montar_complemento(tipo, **campos) -> str:
    """Aplica o template do tipo e trunca.

    Campo ausente ou None vira string vazia — o complemento nunca pode sair
    com a palavra "None" no meio. `data`, quando presente, é formatada em
    DD/MM/AAAA antes de entrar no texto.
    """
    template = TEMPLATES_HISTORICO[tipo]
    valores = {k: ("" if v is None else v) for k, v in campos.items()}
    if valores.get("data") and not isinstance(valores["data"], str):
        valores["data"] = formatar_data(valores["data"])
    return truncar_complemento(template.format(**valores))
```

- [ ] **Step 4: Rode e veja passar**

Run: `pytest tests/test_dominio_layout.py -v`
Expected: 16 passed

- [ ] **Step 5: Commit**

```bash
git add services/dominio_layout.py tests/test_dominio_layout.py
git commit -m "feat(dominio): templates de complemento historico"
```

---

## Task B3: Linha e arquivo — a ordem das colunas num lugar só

**Files:**
- Modify: `services/dominio_layout.py`
- Test: `tests/test_dominio_layout.py`

> **Atenção:** a ordem das colunas é a **lacuna 1** do contrato (ver "Lacunas do contrato 11758"). O `docs/integracao-dominio.md` lista os campos mas não a sequência. A tupla abaixo é **hipótese de trabalho**, isolada numa constante única, e o teste `test_ordem_bate_com_arquivo_modelo` trava a resposta assim que a contabilidade entregar um `.csv` já aceito pelo Domínio.

- [ ] **Step 1: Escreva o teste que falha**

Acrescente a `tests/test_dominio_layout.py`:

```python
from services.dominio_layout import (
    COLUNAS_11758,
    LinhaDominio,
    montar_arquivo,
    montar_linha,
)


def _linha_exemplo():
    return LinhaDominio(
        data=date(2026, 3, 7),
        conta_debito="1015",
        conta_credito="2030",
        valor=Decimal("1234.50"),
        complemento="Pgto fornecedor: ACME",
    )


def test_linha_tem_uma_coluna_por_campo_do_layout():
    assert montar_linha(_linha_exemplo()).count(";") == len(COLUNAS_11758) - 1


def test_linha_traz_os_campos_formatados():
    partes = montar_linha(_linha_exemplo()).split(";")
    campos = dict(zip(COLUNAS_11758, partes))
    assert campos["data"] == "07/03/2026"
    assert campos["conta_debito"] == "1015"
    assert campos["conta_credito"] == "2030"
    assert campos["valor"] == "1234,50"
    assert campos["complemento_historico"] == "Pgto fornecedor: ACME"


def test_campos_em_branco_por_contrato_saem_vazios():
    # docs/integracao-dominio.md:41 (código de histórico) e :46-47
    # (filial e centros de custo)
    partes = montar_linha(_linha_exemplo()).split(";")
    campos = dict(zip(COLUNAS_11758, partes))
    assert campos["codigo_historico"] == ""
    assert campos["filial"] == ""
    assert campos["centro_custo_debito"] == ""
    assert campos["centro_custo_credito"] == ""


def test_cada_lancamento_simples_inicia_seu_proprio_lote():
    # docs/integracao-dominio.md:45
    partes = montar_linha(_linha_exemplo()).split(";")
    assert dict(zip(COLUNAS_11758, partes))["inicia_lote"] == "1"


def test_arquivo_usa_crlf_e_nao_tem_cabecalho():
    conteudo = montar_arquivo([_linha_exemplo(), _linha_exemplo()])
    assert conteudo.count("\r\n") == 2
    assert conteudo.startswith("07/03/2026")


def test_arquivo_vazio_e_string_vazia():
    assert montar_arquivo([]) == ""


@pytest.mark.skipif(
    not os.path.exists(
        os.path.join(os.path.dirname(__file__), "fixtures", "dominio", "modelo_11758.csv")
    ),
    reason=(
        "arquivo-modelo do Domínio ainda não entregue pela contabilidade — "
        "lacuna 1 do contrato (ordem das colunas). Ver o plano da Fase 8."
    ),
)
def test_ordem_bate_com_arquivo_modelo():
    """Trava a ordem das colunas contra um arquivo REAL já aceito pelo Domínio.

    Enquanto o modelo não chega, COLUNAS_11758 é hipótese e a exportação sai
    marcada como LAYOUT NÃO CONFERIDO no resumo de processamento.
    """
    caminho = os.path.join(
        os.path.dirname(__file__), "fixtures", "dominio", "modelo_11758.csv"
    )
    with open(caminho, encoding="cp1252") as fh:
        primeira = fh.readline().rstrip("\r\n")
    assert primeira.count(";") == len(COLUNAS_11758) - 1
```

- [ ] **Step 2: Rode e veja falhar**

Run: `pytest tests/test_dominio_layout.py -k "linha or arquivo or lote or branco" -v`
Expected: `ImportError: cannot import name 'COLUNAS_11758'`

- [ ] **Step 3: Implementação mínima**

Acrescente a `services/dominio_layout.py`:

```python
from dataclasses import dataclass, field
from datetime import date as _date

EOL = "\r\n"
ENCODING = "cp1252"
INICIA_LOTE_SIMPLES = "1"

# ── Ordem das colunas do registro 11758 ────────────────────────────────────
# LACUNA DE CONTRATO: docs/integracao-dominio.md nomeia os campos (:34-48)
# mas não fixa a sequência, o total de colunas, nem se há cabeçalho. Esta
# tupla é a HIPÓTESE DE TRABALHO e é o único lugar a mudar quando a
# contabilidade entregar o arquivo-modelo. O teste
# tests/test_dominio_layout.py::test_ordem_bate_com_arquivo_modelo trava a
# resposta a partir daí.
COLUNAS_11758 = (
    "data",                   # DD/MM/AAAA           (:40)
    "conta_debito",           # código reduzido      (:124-125)
    "conta_credito",          # código reduzido
    "valor",                  # 9999,99 positivo     (:37-39)
    "codigo_historico",       # em branco            (:41)
    "complemento_historico",  # ~60 caracteres       (:44)
    "filial",                 # em branco            (:46)
    "inicia_lote",            # "1" por lançamento   (:45)
    "centro_custo_debito",    # em branco            (:46-47)
    "centro_custo_credito",   # em branco
)

LAYOUT_CONFERIDO = False   # vira True quando o arquivo-modelo for validado


@dataclass(frozen=True)
class LinhaDominio:
    """Um lançamento pronto para o arquivo. Já resolvido: contas, valor
    positivo, complemento montado."""
    data: _date
    conta_debito: str
    conta_credito: str
    valor: object            # Decimal
    complemento: str
    movimento_ids: tuple = field(default_factory=tuple)   # rastreio p/ auditoria


def montar_linha(linha: LinhaDominio) -> str:
    valores = {
        "data": formatar_data(linha.data),
        "conta_debito": str(linha.conta_debito or ""),
        "conta_credito": str(linha.conta_credito or ""),
        "valor": formatar_valor(linha.valor),
        "codigo_historico": "",
        "complemento_historico": truncar_complemento(linha.complemento),
        "filial": "",
        "inicia_lote": INICIA_LOTE_SIMPLES,
        "centro_custo_debito": "",
        "centro_custo_credito": "",
    }
    return SEPARADOR.join(valores[coluna] for coluna in COLUNAS_11758)


def montar_arquivo(linhas) -> str:
    """Concatena as linhas. Sem cabeçalho — lacuna 3 do contrato; se o
    arquivo-modelo mostrar cabeçalho, ele entra aqui e só aqui."""
    if not linhas:
        return ""
    return "".join(montar_linha(l) + EOL for l in linhas)
```

- [ ] **Step 4: Rode e veja passar**

Run: `pytest tests/test_dominio_layout.py -v`
Expected: 22 passed, 1 skipped (o `test_ordem_bate_com_arquivo_modelo`, com o motivo impresso)

- [ ] **Step 5: Commit**

```bash
git add services/dominio_layout.py tests/test_dominio_layout.py
git commit -m "feat(dominio): montagem de linha e arquivo do layout 11758"
```

---

## Task B4: Situação contábil → partida e contrapartida

**Files:**
- Create: `services/dominio_mapeamento.py`
- Test: `tests/test_dominio_mapeamento.py`

- [ ] **Step 1: Escreva o teste que falha**

Crie `tests/test_dominio_mapeamento.py`:

```python
"""Regra contábil da exportação para o Domínio.

A tabela de partida/contrapartida está em docs/integracao-dominio.md:66-75.
O princípio é MISTO (:62-64): a nota fiscal já chegou à contabilidade por
outro caminho, então o movimento de caixa dá BAIXA em Clientes/Fornecedores
— nunca lança a receita nem a compra de novo.

Módulo puro: sem DB, sem Flask.
"""
import os
import sys
from datetime import date
from decimal import Decimal

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from services.dominio_mapeamento import LADO_DO_BANCO, resolver_partida


def test_recebimento_de_cliente_debita_banco_credita_clientes():
    assert resolver_partida("RECEBIMENTO_CLIENTE", conta_banco="1015",
                            conta_contrapartida="1120") == ("1015", "1120")


def test_pagamento_a_fornecedor_debita_fornecedor_credita_banco():
    assert resolver_partida("PAGAMENTO_FORNECEDOR", conta_banco="1015",
                            conta_contrapartida="2030") == ("2030", "1015")


def test_despesa_direta_debita_despesa_credita_banco():
    assert resolver_partida("DESPESA_DIRETA", conta_banco="1015",
                            conta_contrapartida="4501") == ("4501", "1015")


def test_tarifa_bancaria_debita_tarifas_credita_banco():
    assert resolver_partida("TARIFA_BANCARIA", conta_banco="1015",
                            conta_contrapartida="4590") == ("4590", "1015")


def test_aplicacao_debita_aplicacao_credita_banco():
    assert resolver_partida("APLICACAO", conta_banco="1015",
                            conta_contrapartida="1210") == ("1210", "1015")


def test_resgate_inverte_a_aplicacao():
    assert resolver_partida("RESGATE", conta_banco="1015",
                            conta_contrapartida="1210") == ("1015", "1210")


def test_imposto_pago_debita_imposto_credita_banco():
    assert resolver_partida("IMPOSTO", conta_banco="1015",
                            conta_contrapartida="2140") == ("2140", "1015")


def test_toda_situacao_da_spec_esta_mapeada():
    esperadas = {
        "RECEBIMENTO_CLIENTE", "PAGAMENTO_FORNECEDOR", "DESPESA_DIRETA",
        "TARIFA_BANCARIA", "APLICACAO", "RESGATE", "IMPOSTO",
    }
    assert esperadas <= set(LADO_DO_BANCO)


def test_situacoes_genericas_existem_para_o_que_a_spec_nao_cobre():
    """docs/integracao-dominio.md:66-75 não cobre aporte de sócios, empréstimo
    recebido, venda de ativo nem rendimento financeiro. Em vez de forçar essas
    categorias num rótulo errado (o complemento histórico sairia mentindo
    "Receb. cliente"), existem duas situações genéricas que só dizem de que
    lado o banco entra. Ver "Lacunas do contrato" no plano da Fase 8."""
    assert LADO_DO_BANCO["ENTRADA_DIVERSA"] == "DEBITO"
    assert LADO_DO_BANCO["SAIDA_DIVERSA"] == "CREDITO"


def test_situacao_desconhecida_estoura():
    with pytest.raises(KeyError):
        resolver_partida("CHUTE", conta_banco="1015", conta_contrapartida="1")
```

- [ ] **Step 2: Rode e veja falhar**

Run: `pytest tests/test_dominio_mapeamento.py -v`
Expected: `ModuleNotFoundError: No module named 'services.dominio_mapeamento'`

- [ ] **Step 3: Implementação mínima**

Crie `services/dominio_mapeamento.py`:

```python
"""Regra contábil da exportação para o Domínio — módulo PURO.

Recebe value objects já carregados (Movimento, Regra) e devolve LinhaDominio
ou Pendencia. Sem DB, sem Flask. A ponte ORM vive em services/dominio_export.py.

Contrato: docs/integracao-dominio.md:60-106.
"""

# Em qual lado da partida a CONTA DO BANCO entra, por situação
# (docs/integracao-dominio.md:66-75). A contrapartida ocupa o outro lado.
# TRANSFERENCIA não está aqui: os dois lados são bancos, tratada à parte.
LADO_DO_BANCO = {
    "RECEBIMENTO_CLIENTE":  "DEBITO",
    "PAGAMENTO_FORNECEDOR": "CREDITO",
    "DESPESA_DIRETA":       "CREDITO",
    "TARIFA_BANCARIA":      "CREDITO",
    "APLICACAO":            "CREDITO",
    "RESGATE":              "DEBITO",
    "IMPOSTO":              "CREDITO",
    # Genéricas: a tabela do contrato não cobre aporte de sócios, empréstimo
    # recebido, venda de ativo, rendimento financeiro nem devolução. Dizem
    # apenas de que lado o banco entra; o complemento sai pelo template de
    # DESPESA (grupo: categoria ref. descrição), que é neutro.
    "ENTRADA_DIVERSA":      "DEBITO",
    "SAIDA_DIVERSA":        "CREDITO",
}

SITUACAO_TRANSFERENCIA = "TRANSFERENCIA"


def resolver_partida(situacao: str, conta_banco: str, conta_contrapartida: str):
    """Devolve (conta_debito, conta_credito) para a situação dada."""
    lado = LADO_DO_BANCO[situacao]
    if lado == "DEBITO":
        return (conta_banco, conta_contrapartida)
    return (conta_contrapartida, conta_banco)
```

- [ ] **Step 4: Rode e veja passar**

Run: `pytest tests/test_dominio_mapeamento.py -v`
Expected: 10 passed

- [ ] **Step 5: Commit**

```bash
git add services/dominio_mapeamento.py tests/test_dominio_mapeamento.py
git commit -m "feat(dominio): partida e contrapartida por situacao contabil"
```


---

## Task B5: Resolver um movimento em linha ou pendência

**Files:**
- Modify: `services/dominio_mapeamento.py`
- Test: `tests/test_dominio_mapeamento.py`

- [ ] **Step 1: Escreva o teste que falha**

Acrescente a `tests/test_dominio_mapeamento.py`:

```python
from services.dominio_layout import LinhaDominio
from services.dominio_mapeamento import (
    MOTIVO_SEM_CONTA_BANCO,
    MOTIVO_SEM_CONTRAPARTIDA,
    MOTIVO_SEM_REGRA,
    Movimento,
    Pendencia,
    Regra,
    resolver,
)


def _mov(**kw):
    base = dict(
        id=1, data=date(2026, 3, 7), tipo="SAIDA", valor=Decimal("980.00"),
        descricao="CEMIG fatura 03/2026", categoria_nome="Luz / Energia Elétrica",
        grupo_financeiro="Despesas Administrativas", conta_banco="1015",
        banco_nome="Itaú CC",
    )
    base.update(kw)
    return Movimento(**base)


def test_movimento_com_regra_completa_vira_linha():
    linha = resolver(_mov(), Regra(situacao="DESPESA_DIRETA", conta_contrapartida="4501"))
    assert isinstance(linha, LinhaDominio)
    assert (linha.conta_debito, linha.conta_credito) == ("4501", "1015")
    assert linha.valor == Decimal("980.00")
    assert linha.movimento_ids == (1,)


def test_linha_de_despesa_usa_grupo_e_categoria_no_complemento():
    linha = resolver(_mov(), Regra(situacao="DESPESA_DIRETA", conta_contrapartida="4501"))
    assert linha.complemento.startswith(
        "Despesas Administrativas: Luz / Energia Elétrica ref."
    )


def test_sem_regra_vira_pendencia():
    p = resolver(_mov(), None)
    assert isinstance(p, Pendencia)
    assert p.motivo == MOTIVO_SEM_REGRA
    assert p.valor == Decimal("980.00")
    assert p.descricao == "CEMIG fatura 03/2026"


def test_regra_sem_contrapartida_vira_pendencia():
    # docs/integracao-dominio.md:90-91 — nunca inventar código de conta
    p = resolver(_mov(), Regra(situacao="DESPESA_DIRETA", conta_contrapartida=None))
    assert p.motivo == MOTIVO_SEM_CONTRAPARTIDA


def test_movimento_sem_banco_mapeado_vira_pendencia():
    p = resolver(_mov(conta_banco=None),
                 Regra(situacao="DESPESA_DIRETA", conta_contrapartida="4501"))
    assert p.motivo == MOTIVO_SEM_CONTA_BANCO


def test_recebimento_de_cliente_usa_o_template_de_cliente():
    linha = resolver(
        _mov(tipo="ENTRADA", categoria_nome="Receita de Obras",
             grupo_financeiro="Receitas Operacionais"),
        Regra(situacao="RECEBIMENTO_CLIENTE", conta_contrapartida="1120"),
    )
    assert linha.complemento == "Receb. cliente conforme fluxo de caixa 07/03/2026"


def test_tarifa_usa_o_template_de_tarifa():
    linha = resolver(
        _mov(categoria_nome="Despesas Bancárias"),
        Regra(situacao="TARIFA_BANCARIA", conta_contrapartida="4590"),
    )
    assert linha.complemento == "Tarifa bancária: Despesas Bancárias"


def test_pendencia_carrega_a_conta_que_faltou():
    p = resolver(_mov(conta_banco=None),
                 Regra(situacao="DESPESA_DIRETA", conta_contrapartida="4501"))
    assert p.conta == ""          # nada a reportar: é o banco que falta
    assert p.movimento_id == 1
```

- [ ] **Step 2: Rode e veja falhar**

Run: `pytest tests/test_dominio_mapeamento.py -k "resolver or pendencia or linha or complemento or banco or cliente or tarifa" -v`
Expected: `ImportError: cannot import name 'Movimento'`

- [ ] **Step 3: Implementação mínima**

Acrescente a `services/dominio_mapeamento.py`:

```python
from dataclasses import dataclass, field
from datetime import date as _date

from services.dominio_layout import LinhaDominio, montar_complemento

MOTIVO_SEM_REGRA = "categoria sem regra de conta cadastrada"
MOTIVO_SEM_CONTRAPARTIDA = "regra sem conta de contrapartida no plano"
MOTIVO_SEM_CONTA_BANCO = "banco sem código reduzido mapeado"
MOTIVO_SEM_BANCO = "lançamento sem banco informado"
MOTIVO_PAR_INCOMPLETO = "par de transferência incompleto"

# Template de complemento histórico por situação
# (docs/integracao-dominio.md:52-58).
COMPLEMENTO_POR_SITUACAO = {
    "RECEBIMENTO_CLIENTE":  "CLIENTE",
    "PAGAMENTO_FORNECEDOR": "FORNECEDOR",
    "DESPESA_DIRETA":       "DESPESA",
    "TARIFA_BANCARIA":      "TARIFA",
    "APLICACAO":            "DESPESA",
    "RESGATE":              "DESPESA",
    "IMPOSTO":              "DESPESA",
    "ENTRADA_DIVERSA":      "DESPESA",
    "SAIDA_DIVERSA":        "DESPESA",
}


@dataclass(frozen=True)
class Movimento:
    """Uma linha de FluxoCaixa já achatada, com as contas do Domínio
    resolvidas. Espelha models.py:781-812 + os de/para desta fase."""
    id: int
    data: _date
    tipo: str                    # ENTRADA | SAIDA
    valor: object                # Decimal
    descricao: str
    categoria_nome: str = ""
    grupo_financeiro: str = ""
    conta_banco: str = None      # código reduzido de BancoEmpresa
    banco_nome: str = ""
    fornecedor_nome: str = ""
    conta_fornecedor: str = None  # código reduzido nominal do fornecedor
    transferencia_par_id: int = None


@dataclass(frozen=True)
class Regra:
    """De/para categoria → situação + conta de contrapartida
    (regra_conta_dominio)."""
    situacao: str
    conta_contrapartida: str = None


@dataclass(frozen=True)
class Pendencia:
    """Linha que não pôde virar lançamento. Vira uma linha do relatório
    .xlsx (docs/integracao-dominio.md:113)."""
    movimento_id: int
    data: _date
    descricao: str
    valor: object
    conta: str
    motivo: str


def _complemento(mov: Movimento, situacao: str) -> str:
    tipo = COMPLEMENTO_POR_SITUACAO[situacao]
    if tipo == "CLIENTE":
        return montar_complemento("CLIENTE", data=mov.data)
    if tipo == "FORNECEDOR":
        return montar_complemento("FORNECEDOR",
                                  nome=mov.fornecedor_nome or mov.descricao)
    if tipo == "TARIFA":
        return montar_complemento("TARIFA", subcategoria=mov.categoria_nome)
    return montar_complemento("DESPESA", categoria=mov.grupo_financeiro,
                              subcategoria=mov.categoria_nome,
                              descricao=mov.descricao)


def _pendencia(mov: Movimento, motivo: str, conta: str = "") -> Pendencia:
    return Pendencia(movimento_id=mov.id, data=mov.data, descricao=mov.descricao,
                     valor=mov.valor, conta=conta, motivo=motivo)


def resolver(mov: Movimento, regra):
    """Movimento + Regra → LinhaDominio, ou Pendencia com o motivo.

    Nunca inventa código de conta (docs/integracao-dominio.md:90-91): o que
    falta vira pendência com o motivo registrado.
    """
    if regra is None:
        return _pendencia(mov, MOTIVO_SEM_REGRA)
    if not mov.conta_banco:
        return _pendencia(mov, MOTIVO_SEM_CONTA_BANCO)
    contrapartida = regra.conta_contrapartida
    if not contrapartida:
        return _pendencia(mov, MOTIVO_SEM_CONTRAPARTIDA)
    debito, credito = resolver_partida(regra.situacao, mov.conta_banco, contrapartida)
    return LinhaDominio(
        data=mov.data, conta_debito=debito, conta_credito=credito,
        valor=mov.valor, complemento=_complemento(mov, regra.situacao),
        movimento_ids=(mov.id,),
    )
```

- [ ] **Step 4: Rode e veja passar**

Run: `pytest tests/test_dominio_mapeamento.py -v`
Expected: 18 passed

- [ ] **Step 5: Commit**

```bash
git add services/dominio_mapeamento.py tests/test_dominio_mapeamento.py
git commit -m "feat(dominio): resolver movimento em linha ou pendencia"
```

---

## Task B6: Fornecedor nominal antes do genérico

**Files:**
- Modify: `services/dominio_mapeamento.py`
- Test: `tests/test_dominio_mapeamento.py`

> **Decisão D7 em vigor:** a conta nominal vem do cadastro (`fornecedor.conta_dominio_id`), nunca de matching de texto na hora da exportação. O matching sem acento existe apenas como **sugestão** na tela de de/para (Task B18), e é a mesma normalização já usada pelo classificador (`services/classificador_cadastro.py:69`). Repetir aqui o hardcode que o ADR-0002 removeu seria regressão.

- [ ] **Step 1: Escreva o teste que falha**

Acrescente a `tests/test_dominio_mapeamento.py`:

```python
from services.dominio_mapeamento import sugerir_conta_fornecedor


def test_fornecedor_com_conta_nominal_vence_a_generica():
    linha = resolver(
        _mov(fornecedor_nome="Aço Norte", conta_fornecedor="2031"),
        Regra(situacao="PAGAMENTO_FORNECEDOR", conta_contrapartida="2030"),
    )
    assert linha.conta_debito == "2031"


def test_fornecedor_sem_conta_nominal_cai_na_generica():
    linha = resolver(
        _mov(fornecedor_nome="Aço Norte", conta_fornecedor=None),
        Regra(situacao="PAGAMENTO_FORNECEDOR", conta_contrapartida="2030"),
    )
    assert linha.conta_debito == "2030"


def test_conta_nominal_so_vale_para_pagamento_a_fornecedor():
    # numa despesa direta, a contrapartida é a conta da despesa
    linha = resolver(
        _mov(conta_fornecedor="2031"),
        Regra(situacao="DESPESA_DIRETA", conta_contrapartida="4501"),
    )
    assert linha.conta_debito == "4501"


def test_sugestao_de_conta_ignora_acento_e_caixa():
    # docs/integracao-dominio.md:87-89 — comparação sem acento, case-insensitive
    plano = [("2031", "AÇO NORTE DISTRIBUIDORA"), ("2032", "Cimento Sul")]
    assert sugerir_conta_fornecedor("aco norte distribuidora ltda", plano) == "2031"


def test_sugestao_sem_candidato_devolve_none():
    assert sugerir_conta_fornecedor("Fornecedor Novo", [("2032", "Cimento Sul")]) is None
```

- [ ] **Step 2: Rode e veja falhar**

Run: `pytest tests/test_dominio_mapeamento.py -k "fornecedor or sugestao" -v`
Expected: falham `test_fornecedor_com_conta_nominal_vence_a_generica` (devolve `"2030"`) e as duas de `sugerir_conta_fornecedor` (`ImportError`)

- [ ] **Step 3: Implementação mínima**

Em `services/dominio_mapeamento.py`, troque o bloco de contrapartida dentro de `resolver`:

```python
    contrapartida = regra.conta_contrapartida
    if regra.situacao == "PAGAMENTO_FORNECEDOR" and mov.conta_fornecedor:
        contrapartida = mov.conta_fornecedor
    if not contrapartida:
        return _pendencia(mov, MOTIVO_SEM_CONTRAPARTIDA)
```

E acrescente ao fim do módulo:

```python
from services.classificador_cadastro import _norm as _normalizar


def sugerir_conta_fornecedor(nome, contas_do_plano):
    """SUGESTÃO para a tela de de/para (docs/integracao-dominio.md:87-89).

    NÃO é usada na exportação — decisão D7. `contas_do_plano` é uma lista de
    (codigo_reduzido, nome_da_conta). Vence a conta cujo nome normalizado
    esteja contido no nome normalizado do fornecedor, ou vice-versa; havendo
    empate, a de nome mais longo (mais específica).
    """
    alvo = _normalizar(nome)
    if not alvo:
        return None
    candidatas = [
        (codigo, _normalizar(nome_conta))
        for codigo, nome_conta in contas_do_plano
        if _normalizar(nome_conta)
        and (_normalizar(nome_conta) in alvo or alvo in _normalizar(nome_conta))
    ]
    if not candidatas:
        return None
    return max(candidatas, key=lambda c: len(c[1]))[0]
```

- [ ] **Step 4: Rode e veja passar**

Run: `pytest tests/test_dominio_mapeamento.py -v`
Expected: 23 passed

- [ ] **Step 5: Commit**

```bash
git add services/dominio_mapeamento.py tests/test_dominio_mapeamento.py
git commit -m "feat(dominio): conta nominal de fornecedor antes da generica"
```

---

## Task B7: Descartes automáticos

**Files:**
- Modify: `services/dominio_mapeamento.py`
- Test: `tests/test_dominio_mapeamento.py`

- [ ] **Step 1: Escreva o teste que falha**

Acrescente a `tests/test_dominio_mapeamento.py`:

```python
from services.dominio_mapeamento import descartar


def test_descarta_linha_de_saldo():
    # docs/integracao-dominio.md:92-93
    assert descartar(_mov(descricao="SALDO ANTERIOR")) == "linha de saldo/total/projeção"


def test_descarta_linha_de_total():
    assert descartar(_mov(descricao="TOTAL DO MÊS")) is not None


def test_descarta_projecao():
    assert descartar(_mov(descricao="Projeção de caixa abril")) is not None


def test_descarta_data_de_1900():
    assert descartar(_mov(data=date(1900, 1, 1))) == "data inválida (ano 1900)"


def test_descarta_valor_zero():
    assert descartar(_mov(valor=Decimal("0.00"))) == "sem entrada e sem saída"


def test_nao_descarta_movimento_legitimo():
    assert descartar(_mov()) is None


def test_nao_descarta_fornecedor_com_saldo_no_nome():
    # 'saldo' só descarta quando é a linha de saldo, não quando aparece solto
    assert descartar(_mov(descricao="Pgto Saldos Materiais Ltda NF 442")) is None
```

- [ ] **Step 2: Rode e veja falhar**

Run: `pytest tests/test_dominio_mapeamento.py -k descarta -v`
Expected: `ImportError: cannot import name 'descartar'`

- [ ] **Step 3: Implementação mínima**

Acrescente a `services/dominio_mapeamento.py`:

```python
# Prefixos de linha de resumo da planilha (docs/integracao-dominio.md:92-93).
# Casamento por PREFIXO, não por substring: "Pgto Saldos Materiais" é
# despesa legítima e não pode sumir.
_PREFIXOS_DESCARTE = ("saldo", "total", "projecao", "subtotal")

DESCARTE_RESUMO = "linha de saldo/total/projeção"
DESCARTE_DATA_1900 = "data inválida (ano 1900)"
DESCARTE_SEM_VALOR = "sem entrada e sem saída"


def descartar(mov: Movimento):
    """Devolve o motivo do descarte automático, ou None se o movimento deve
    ser processado. Descarte NÃO é pendência: some do arquivo e do relatório
    de pendências, e é apenas contado no resumo de processamento."""
    if mov.data is not None and mov.data.year <= 1900:
        return DESCARTE_DATA_1900
    if mov.valor is None or mov.valor == 0:
        return DESCARTE_SEM_VALOR
    desc = _normalizar(mov.descricao)
    if any(desc.startswith(p) for p in _PREFIXOS_DESCARTE):
        return DESCARTE_RESUMO
    return None
```

- [ ] **Step 4: Rode e veja passar**

Run: `pytest tests/test_dominio_mapeamento.py -v`
Expected: 30 passed

- [ ] **Step 5: Commit**

```bash
git add services/dominio_mapeamento.py tests/test_dominio_mapeamento.py
git commit -m "feat(dominio): descartes automaticos de linha de resumo"
```


---

## Task B8: Colapsar o par de transferência em um lançamento

**Files:**
- Modify: `services/dominio_mapeamento.py`
- Test: `tests/test_dominio_mapeamento.py`

> **Decisão D5 em vigor:** o par é identificado por `FluxoCaixa.transferencia_par_id` (criado na Task B14), não por heurística de `(valor, data)`. Duas transferências de mesmo valor no mesmo dia — comum em fechamento de mês — quebrariam o casamento heurístico.

- [ ] **Step 1: Escreva o teste que falha**

Acrescente a `tests/test_dominio_mapeamento.py`:

```python
from services.dominio_mapeamento import MOTIVO_PAR_INCOMPLETO, colapsar_transferencias


def _par_transferencia():
    saida = _mov(id=10, tipo="SAIDA", conta_banco="1015", banco_nome="Itaú CC",
                 descricao="Transferência de valores", transferencia_par_id=11)
    entrada = _mov(id=11, tipo="ENTRADA", conta_banco="1016", banco_nome="Nubank",
                   descricao="Transferência de valores", transferencia_par_id=10)
    return [saida, entrada]


def test_par_vira_um_unico_lancamento():
    linhas, pendencias, restantes = colapsar_transferencias(_par_transferencia())
    assert len(linhas) == 1
    assert pendencias == []
    assert restantes == []


def test_transferencia_debita_destino_e_credita_origem():
    # docs/integracao-dominio.md:75 e :82
    linhas, _, _ = colapsar_transferencias(_par_transferencia())
    assert (linhas[0].conta_debito, linhas[0].conta_credito) == ("1016", "1015")


def test_transferencia_rastreia_os_dois_movimentos():
    linhas, _, _ = colapsar_transferencias(_par_transferencia())
    assert sorted(linhas[0].movimento_ids) == [10, 11]


def test_transferencia_usa_o_template_de_transferencia():
    linhas, _, _ = colapsar_transferencias(_par_transferencia())
    assert linhas[0].complemento == "Transf. entre contas: Itaú CC -> Nubank"


def test_par_incompleto_vira_pendencia():
    # docs/integracao-dominio.md:83 — par incompleto ⇒ pendência
    orfa = _mov(id=10, tipo="SAIDA", transferencia_par_id=99)
    linhas, pendencias, restantes = colapsar_transferencias([orfa])
    assert linhas == []
    assert len(pendencias) == 1
    assert pendencias[0].motivo == MOTIVO_PAR_INCOMPLETO


def test_transferencia_sem_banco_mapeado_vira_pendencia():
    saida, entrada = _par_transferencia()
    saida = Movimento(**{**saida.__dict__, "conta_banco": None})
    linhas, pendencias, _ = colapsar_transferencias([saida, entrada])
    assert linhas == []
    assert pendencias[0].motivo == MOTIVO_SEM_CONTA_BANCO


def test_movimentos_normais_saem_intactos_em_restantes():
    normal = _mov(id=1)
    linhas, pendencias, restantes = colapsar_transferencias([normal])
    assert (linhas, pendencias) == ([], [])
    assert restantes == [normal]
```

- [ ] **Step 2: Rode e veja falhar**

Run: `pytest tests/test_dominio_mapeamento.py -k "transferencia or par" -v`
Expected: `ImportError: cannot import name 'colapsar_transferencias'`

- [ ] **Step 3: Implementação mínima**

Acrescente a `services/dominio_mapeamento.py`:

```python
def colapsar_transferencias(movimentos):
    """Colapsa cada par de transferência em UM lançamento
    (docs/integracao-dominio.md:79-83).

    Devolve (linhas, pendencias, restantes). `restantes` são os movimentos
    que não são transferência e seguem para `resolver`.

    O par vem do FK `transferencia_par_id` (models.py, migration 293) — não
    de heurística de valor e data.
    """
    por_id = {m.id: m for m in movimentos}
    linhas, pendencias, restantes, vistos = [], [], [], set()

    for mov in movimentos:
        if mov.transferencia_par_id is None:
            restantes.append(mov)
            continue
        if mov.id in vistos:
            continue

        par = por_id.get(mov.transferencia_par_id)
        if par is None:
            pendencias.append(_pendencia(mov, MOTIVO_PAR_INCOMPLETO))
            vistos.add(mov.id)
            continue

        vistos.update({mov.id, par.id})
        origem = mov if mov.tipo == "SAIDA" else par
        destino = par if mov.tipo == "SAIDA" else mov

        if not origem.conta_banco or not destino.conta_banco:
            sem_conta = origem if not origem.conta_banco else destino
            pendencias.append(_pendencia(sem_conta, MOTIVO_SEM_CONTA_BANCO))
            continue

        linhas.append(LinhaDominio(
            data=origem.data,
            conta_debito=destino.conta_banco,
            conta_credito=origem.conta_banco,
            valor=origem.valor,
            complemento=montar_complemento(
                "TRANSFERENCIA", origem=origem.banco_nome, destino=destino.banco_nome),
            movimento_ids=(origem.id, destino.id),
        ))

    return linhas, pendencias, restantes
```

- [ ] **Step 4: Rode e veja passar**

Run: `pytest tests/test_dominio_mapeamento.py -v`
Expected: 37 passed

- [ ] **Step 5: Commit**

```bash
git add services/dominio_mapeamento.py tests/test_dominio_mapeamento.py
git commit -m "feat(dominio): colapso do par de transferencia entre contas"
```

---

## Task B9: Remover duplicatas exatas

**Files:**
- Modify: `services/dominio_mapeamento.py`
- Test: `tests/test_dominio_mapeamento.py`

- [ ] **Step 1: Escreva o teste que falha**

Acrescente a `tests/test_dominio_mapeamento.py`:

```python
from services.dominio_mapeamento import remover_duplicatas_exatas


def test_duplicata_exata_e_removida():
    # docs/integracao-dominio.md:93
    a = _mov(id=1)
    b = _mov(id=2)   # mesma data, valor, descrição, banco e categoria
    unicos, removidos = remover_duplicatas_exatas([a, b])
    assert [m.id for m in unicos] == [1]
    assert [m.id for m in removidos] == [2]


def test_mesmo_valor_em_datas_diferentes_nao_e_duplicata():
    a = _mov(id=1, data=date(2026, 3, 7))
    b = _mov(id=2, data=date(2026, 3, 8))
    unicos, removidos = remover_duplicatas_exatas([a, b])
    assert len(unicos) == 2
    assert removidos == []


def test_mesmo_dia_e_valor_com_fornecedor_diferente_nao_e_duplicata():
    # duas diárias iguais no mesmo dia são legítimas — mesma lógica de
    # services/importacao_excel.py:2186-2189
    a = _mov(id=1, descricao="Diária João")
    b = _mov(id=2, descricao="Diária Maria")
    unicos, _ = remover_duplicatas_exatas([a, b])
    assert len(unicos) == 2


def test_a_primeira_ocorrencia_e_a_que_fica():
    a, b, c = _mov(id=5), _mov(id=6), _mov(id=7)
    unicos, removidos = remover_duplicatas_exatas([a, b, c])
    assert [m.id for m in unicos] == [5]
    assert [m.id for m in removidos] == [6, 7]
```

- [ ] **Step 2: Rode e veja falhar**

Run: `pytest tests/test_dominio_mapeamento.py -k duplicata -v`
Expected: `ImportError: cannot import name 'remover_duplicatas_exatas'`

- [ ] **Step 3: Implementação mínima**

Acrescente a `services/dominio_mapeamento.py`:

```python
DESCARTE_DUPLICATA = "duplicata exata"


def _chave_duplicata(mov: Movimento):
    return (mov.data, mov.tipo, mov.valor, _normalizar(mov.descricao),
            mov.conta_banco, _normalizar(mov.categoria_nome))


def remover_duplicatas_exatas(movimentos):
    """Descarte de duplicata exata (docs/integracao-dominio.md:93).

    "Exata" = mesma data, tipo, valor, descrição normalizada, banco e
    categoria. Fica a PRIMEIRA ocorrência. Devolve (unicos, removidos).
    """
    vistos, unicos, removidos = set(), [], []
    for mov in movimentos:
        chave = _chave_duplicata(mov)
        if chave in vistos:
            removidos.append(mov)
        else:
            vistos.add(chave)
            unicos.append(mov)
    return unicos, removidos
```

- [ ] **Step 4: Rode e veja passar**

Run: `pytest tests/test_dominio_mapeamento.py -v`
Expected: 41 passed

- [ ] **Step 5: Commit**

```bash
git add services/dominio_mapeamento.py tests/test_dominio_mapeamento.py
git commit -m "feat(dominio): descarte de duplicata exata"
```

---

## Task B10: As seis validações bloqueantes

**Files:**
- Create: `services/dominio_validacao.py`
- Test: `tests/test_dominio_validacao.py`

- [ ] **Step 1: Escreva o teste que falha**

Crie `tests/test_dominio_validacao.py`:

```python
"""Validações bloqueantes da exportação para o Domínio.

docs/integracao-dominio.md:96-106 — as seis rodam ANTES de entregar o
arquivo; qualquer uma que falhe impede a geração.

Módulo puro: sem DB, sem Flask.
"""
import os
import sys
from datetime import date
from decimal import Decimal

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from services.dominio_layout import LinhaDominio
from services.dominio_validacao import LIMITE_PENDENCIA, validar


def _linha(**kw):
    base = dict(data=date(2026, 3, 7), conta_debito="4501", conta_credito="1015",
                valor=Decimal("100.00"), complemento="x")
    base.update(kw)
    return LinhaDominio(**base)


CONTAS = {"4501", "1015", "2030"}
INICIO, FIM = date(2026, 3, 1), date(2026, 3, 31)


def test_lote_valido_nao_produz_erro():
    assert validar([_linha()], pendencias=[], contas_validas=CONTAS,
                   data_inicio=INICIO, data_fim=FIM) == []


def test_partidas_dobradas_por_lote():
    # cada linha é seu próprio lote (docs:45): débito e crédito da MESMA
    # linha já são iguais por construção; a checagem pega linha corrompida
    erros = validar([_linha(conta_debito="4501", conta_credito="4501")],
                    [], CONTAS, INICIO, FIM)
    assert any("mesma conta" in e for e in erros)


def test_conta_de_debito_fora_do_plano_bloqueia():
    erros = validar([_linha(conta_debito="9999")], [], CONTAS, INICIO, FIM)
    assert any("9999" in e for e in erros)


def test_conta_de_credito_fora_do_plano_bloqueia():
    erros = validar([_linha(conta_credito="8888")], [], CONTAS, INICIO, FIM)
    assert any("8888" in e for e in erros)


def test_data_fora_do_periodo_bloqueia():
    erros = validar([_linha(data=date(2026, 4, 2))], [], CONTAS, INICIO, FIM)
    assert any("fora do período" in e for e in erros)


def test_valor_zero_bloqueia():
    erros = validar([_linha(valor=Decimal("0.00"))], [], CONTAS, INICIO, FIM)
    assert any("valor" in e for e in erros)


def test_valor_negativo_bloqueia():
    erros = validar([_linha(valor=Decimal("-1.00"))], [], CONTAS, INICIO, FIM)
    assert any("valor" in e for e in erros)


def test_conta_vazia_bloqueia():
    erros = validar([_linha(conta_debito="")], [], CONTAS, INICIO, FIM)
    assert any("vazia" in e for e in erros)


def test_cobertura_abaixo_de_80_por_cento_bloqueia():
    # docs/integracao-dominio.md:105-106 — mais de 20% em pendência: parar
    linhas = [_linha() for _ in range(7)]
    pendencias = list(range(3))          # 3 de 10 = 30%
    erros = validar(linhas, pendencias, CONTAS, INICIO, FIM)
    assert any("cobertura" in e for e in erros)


def test_cobertura_exatamente_no_limite_passa():
    linhas = [_linha() for _ in range(8)]
    pendencias = list(range(2))          # 2 de 10 = 20%, no limite
    assert LIMITE_PENDENCIA == Decimal("0.20")
    assert validar(linhas, pendencias, CONTAS, INICIO, FIM) == []


def test_lote_totalmente_vazio_bloqueia():
    erros = validar([], [], CONTAS, INICIO, FIM)
    assert any("nenhum lançamento" in e for e in erros)
```

- [ ] **Step 2: Rode e veja falhar**

Run: `pytest tests/test_dominio_validacao.py -v`
Expected: `ModuleNotFoundError: No module named 'services.dominio_validacao'`

- [ ] **Step 3: Implementação mínima**

Crie `services/dominio_validacao.py`:

```python
"""Validações bloqueantes da exportação para o Domínio — módulo PURO.

docs/integracao-dominio.md:96-106. Rodam ANTES de entregar o arquivo.
Devolve a lista de erros; lista vazia significa "pode gerar".
"""
from decimal import Decimal

LIMITE_PENDENCIA = Decimal("0.20")


def validar(linhas, pendencias, contas_validas, data_inicio, data_fim):
    erros = []

    if not linhas:
        erros.append("nenhum lançamento gerado no período")

    for l in linhas:
        # 1. partidas dobradas por lote — cada linha é um lote (docs:45),
        #    logo débito e crédito têm de existir e ser contas distintas
        if l.conta_debito and l.conta_debito == l.conta_credito:
            erros.append(
                f"lançamento de {l.data} debita e credita a mesma conta "
                f"{l.conta_debito}")

        # 5. nenhuma linha com débito E crédito vazios
        if not l.conta_debito or not l.conta_credito:
            erros.append(f"lançamento de {l.data} com conta vazia")
            continue

        # 2. todo código existe no plano de contas
        for conta in (l.conta_debito, l.conta_credito):
            if conta not in contas_validas:
                erros.append(
                    f"conta {conta} não existe no plano de contas do Domínio")

        # 3. datas dentro do período exportado
        if not (data_inicio <= l.data <= data_fim):
            erros.append(
                f"lançamento com data {l.data} fora do período "
                f"{data_inicio} a {data_fim}")

        # 4. nenhum valor <= 0
        if l.valor is None or Decimal(l.valor) <= 0:
            erros.append(f"lançamento de {l.data} com valor inválido: {l.valor}")

    # 6. cobertura: mais de 20% em pendência ⇒ parar e reportar
    total = len(linhas) + len(pendencias)
    if total and (Decimal(len(pendencias)) / Decimal(total)) > LIMITE_PENDENCIA:
        pct = (Decimal(len(pendencias)) / Decimal(total) * 100).quantize(Decimal("0.1"))
        erros.append(
            f"cobertura insuficiente: {len(pendencias)} de {total} linhas "
            f"({pct}%) em pendência, acima do limite de 20%")

    return erros
```

- [ ] **Step 4: Rode e veja passar**

Run: `pytest tests/test_dominio_validacao.py -v`
Expected: 11 passed

- [ ] **Step 5: Commit**

```bash
git add services/dominio_validacao.py tests/test_dominio_validacao.py
git commit -m "feat(dominio): seis validacoes bloqueantes do layout 11758"
```


---

## Task B11: Plano de contas do Domínio por tenant (`conta_dominio`, migration 290)

**Files:**
- Modify: `models.py` (fim do arquivo, depois de `CategoriaReembolso`, hoje a linha 7610)
- Modify: `migrations.py` (nova função + registro em `migrations_to_run`, após a linha 4014)
- Test: `tests/test_dominio_schema.py`

> **Decisão D1 em vigor:** tabela nova, não reaproveita `plano_contas` — cuja PK é `codigo` **global** (`models.py:2501`) e por isso não comporta dois tenants (buraco D).

- [ ] **Step 1: Escreva o teste que falha**

Crie `tests/test_dominio_schema.py`:

```python
"""Fase 8 — schema da exportação para o Domínio.

O plano de contas do Domínio (código reduzido) é DADO por tenant, editável
pela contabilidade sem deploy — mesmo princípio do ADR-0002 para as Regras
de Classificação. Não reaproveita `plano_contas`, cuja PK `codigo` é global
(models.py:2501) e já quebra o seed do 2º tenant (contabilidade_utils.py:1525).
"""
import os
import sys
import uuid

import pytest
from sqlalchemy.exc import IntegrityError
from werkzeug.security import generate_password_hash

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import main  # noqa: F401 — registra os blueprints
from app import app, db
from models import TipoUsuario, Usuario

pytestmark = pytest.mark.integration


@pytest.fixture(autouse=True)
def _config():
    app.config['TESTING'] = True
    app.config['WTF_CSRF_ENABLED'] = False
    if not app.secret_key:
        app.secret_key = 'test-fase8-dominio'
    yield


def _admin():
    suf = uuid.uuid4().hex[:8]
    u = Usuario(
        username=f'f8_{suf}', email=f'f8_{suf}@test.local', nome=f'Admin {suf}',
        password_hash=generate_password_hash('Senha@2026'),
        tipo_usuario=TipoUsuario.ADMIN, ativo=True, versao_sistema='v2',
    )
    db.session.add(u)
    db.session.commit()
    return u.id


def test_conta_dominio_aceita_o_mesmo_codigo_em_dois_tenants():
    """O que `plano_contas` NÃO consegue fazer (models.py:2501)."""
    from models import ContaDominio
    with app.app_context():
        a, b = _admin(), _admin()
        db.session.add_all([
            ContaDominio(admin_id=a, codigo_reduzido='1015', nome='Itaú CC'),
            ContaDominio(admin_id=b, codigo_reduzido='1015', nome='Banco do Brasil'),
        ])
        db.session.commit()
        assert ContaDominio.query.filter_by(codigo_reduzido='1015').count() == 2


def test_conta_dominio_recusa_codigo_repetido_no_mesmo_tenant():
    from models import ContaDominio
    with app.app_context():
        a = _admin()
        db.session.add(ContaDominio(admin_id=a, codigo_reduzido='1015', nome='Itaú'))
        db.session.commit()
        db.session.add(ContaDominio(admin_id=a, codigo_reduzido='1015', nome='Outro'))
        with pytest.raises(IntegrityError):
            db.session.commit()
        db.session.rollback()


def test_conta_dominio_tem_tipo_para_conta_e_centro_de_custo():
    """Decisão D4: quando a contabilidade confirmar o uso de centro de custo,
    ele entra como linha tipo='CENTRO_CUSTO' na mesma tabela, sem migração."""
    from models import ContaDominio
    with app.app_context():
        a = _admin()
        cc = ContaDominio(admin_id=a, codigo_reduzido='CC01', nome='Obra Alfa',
                          tipo='CENTRO_CUSTO')
        db.session.add(cc)
        db.session.commit()
        assert cc.tipo == 'CENTRO_CUSTO'


def test_conta_dominio_nasce_ativa():
    from models import ContaDominio
    with app.app_context():
        c = ContaDominio(admin_id=_admin(), codigo_reduzido='2030', nome='Fornecedores')
        db.session.add(c)
        db.session.commit()
        assert c.ativo is True
        assert c.tipo == 'CONTA'
```

- [ ] **Step 2: Rode e veja falhar**

Run: `pytest tests/test_dominio_schema.py -v`
Expected: `ImportError: cannot import name 'ContaDominio' from 'models'`

- [ ] **Step 3: Modelo**

Acrescente ao fim de `models.py`:

```python
class ContaDominio(db.Model):
    """Plano de contas do Domínio Contabilidade, por tenant.

    Fase 8 / decisão D1. NÃO é `PlanoContas` (models.py:2498): aquele é a
    contabilidade interna, tem PK global em `codigo` e usa código
    hierárquico; este usa o CÓDIGO REDUZIDO do Domínio e é dado editável
    pela contabilidade, no espírito do ADR-0002.
    """
    __tablename__ = 'conta_dominio'

    id = db.Column(db.Integer, primary_key=True)
    admin_id = db.Column(db.Integer, db.ForeignKey('usuario.id'), nullable=False)
    codigo_reduzido = db.Column(db.String(20), nullable=False)
    nome = db.Column(db.String(200), nullable=False)
    classificacao = db.Column(db.String(40))   # código hierárquico do Domínio, opcional
    tipo = db.Column(db.String(20), nullable=False, default='CONTA')  # CONTA | CENTRO_CUSTO
    ativo = db.Column(db.Boolean, nullable=False, default=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    __table_args__ = (
        db.UniqueConstraint('admin_id', 'codigo_reduzido',
                            name='uq_conta_dominio_admin_codigo'),
        db.Index('idx_conta_dominio_admin_tipo', 'admin_id', 'tipo', 'ativo'),
    )
```

- [ ] **Step 4: Migration**

Acrescente a `migrations.py`, junto das demais funções de módulo (depois da linha 14264):

```python
def _migration_290_conta_dominio():
    """Fase 8 — plano de contas do Domínio por tenant (código reduzido).

    Decisão D1 do plano: não reaproveita `plano_contas`, cuja PK `codigo` é
    global (models.py:2501).
    """
    from sqlalchemy import text as sa_text
    try:
        with db.engine.begin() as conn:
            conn.execute(sa_text("""
                CREATE TABLE IF NOT EXISTS conta_dominio (
                    id               SERIAL PRIMARY KEY,
                    admin_id         INTEGER      NOT NULL REFERENCES usuario(id),
                    codigo_reduzido  VARCHAR(20)  NOT NULL,
                    nome             VARCHAR(200) NOT NULL,
                    classificacao    VARCHAR(40),
                    tipo             VARCHAR(20)  NOT NULL DEFAULT 'CONTA',
                    ativo            BOOLEAN      NOT NULL DEFAULT TRUE,
                    created_at       TIMESTAMP    DEFAULT NOW(),
                    CONSTRAINT uq_conta_dominio_admin_codigo
                        UNIQUE (admin_id, codigo_reduzido)
                )
            """))
            conn.execute(sa_text("""
                CREATE INDEX IF NOT EXISTS idx_conta_dominio_admin_tipo
                  ON conta_dominio (admin_id, tipo, ativo)
            """))
        logger.info("[Migration 290] conta_dominio criada.")
    except Exception as e:
        logger.error(f"[Migration 290] Falha: {e}", exc_info=True)
        raise
```

E registre em `migrations_to_run`, logo depois da linha 4014:

```python
            (290, "Fase 8 — plano de contas do Domínio por tenant (código reduzido)", _migration_290_conta_dominio),
```

- [ ] **Step 5: Rode e veja passar**

Run: `pytest tests/test_dominio_schema.py -v`
Expected: 4 passed

- [ ] **Step 6: Commit**

```bash
git add models.py migrations.py tests/test_dominio_schema.py
git commit -m "feat(dominio): tabela conta_dominio (migration 290)"
```

---

## Task B12: De/para categoria → situação e contrapartida (`regra_conta_dominio`, migration 291)

**Files:**
- Modify: `models.py` (depois de `ContaDominio`)
- Modify: `migrations.py`
- Test: `tests/test_dominio_schema.py`

- [ ] **Step 1: Escreva o teste que falha**

Acrescente a `tests/test_dominio_schema.py`:

```python
def _categoria(admin_id, nome='Luz / Energia Elétrica'):
    from models import CategoriaFluxoCaixa
    CategoriaFluxoCaixa.seed_defaults(admin_id)
    db.session.commit()
    return CategoriaFluxoCaixa.query.filter_by(admin_id=admin_id, nome=nome).first()


def test_regra_liga_categoria_a_situacao_e_contrapartida():
    from models import ContaDominio, RegraContaDominio
    with app.app_context():
        a = _admin()
        cat = _categoria(a)
        conta = ContaDominio(admin_id=a, codigo_reduzido='4501', nome='Energia')
        db.session.add(conta)
        db.session.flush()
        r = RegraContaDominio(admin_id=a, categoria_fluxo_caixa_id=cat.id,
                              situacao='DESPESA_DIRETA', conta_contrapartida_id=conta.id)
        db.session.add(r)
        db.session.commit()
        assert r.conta_contrapartida.codigo_reduzido == '4501'


def test_regra_admite_contrapartida_nula_no_mes_de_calibracao():
    """docs/integracao-dominio.md:29-32 — o plano de contas da Veks ainda não
    foi entregue. A regra nasce com a situação preenchida e a conta NULA; a
    linha vira pendência com motivo, em vez de conta inventada (:90-91)."""
    from models import RegraContaDominio
    with app.app_context():
        a = _admin()
        cat = _categoria(a)
        r = RegraContaDominio(admin_id=a, categoria_fluxo_caixa_id=cat.id,
                              situacao='DESPESA_DIRETA')
        db.session.add(r)
        db.session.commit()
        assert r.conta_contrapartida_id is None


def test_uma_regra_por_categoria_por_tenant():
    from models import RegraContaDominio
    with app.app_context():
        a = _admin()
        cat = _categoria(a)
        db.session.add(RegraContaDominio(admin_id=a, categoria_fluxo_caixa_id=cat.id,
                                         situacao='DESPESA_DIRETA'))
        db.session.commit()
        db.session.add(RegraContaDominio(admin_id=a, categoria_fluxo_caixa_id=cat.id,
                                         situacao='IMPOSTO'))
        with pytest.raises(IntegrityError):
            db.session.commit()
        db.session.rollback()
```

- [ ] **Step 2: Rode e veja falhar**

Run: `pytest tests/test_dominio_schema.py -k regra -v`
Expected: `ImportError: cannot import name 'RegraContaDominio' from 'models'`

- [ ] **Step 3: Modelo**

Acrescente a `models.py`, depois de `ContaDominio`:

```python
class RegraContaDominio(db.Model):
    """De/para `categoria de fluxo de caixa → situação contábil + conta de
    contrapartida` (docs/integracao-dominio.md:118-123).

    A situação decide de que lado o banco entra
    (services/dominio_mapeamento.py:LADO_DO_BANCO); a contrapartida ocupa o
    outro lado. Contrapartida NULA é estado legítimo no mês de calibração:
    a linha vira pendência em vez de conta inventada.
    """
    __tablename__ = 'regra_conta_dominio'

    id = db.Column(db.Integer, primary_key=True)
    admin_id = db.Column(db.Integer, db.ForeignKey('usuario.id'), nullable=False)
    categoria_fluxo_caixa_id = db.Column(
        db.Integer, db.ForeignKey('categoria_fluxo_caixa.id'), nullable=False)
    situacao = db.Column(db.String(30), nullable=False)
    conta_contrapartida_id = db.Column(
        db.Integer, db.ForeignKey('conta_dominio.id', ondelete='SET NULL'))
    ativo = db.Column(db.Boolean, nullable=False, default=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    categoria = db.relationship('CategoriaFluxoCaixa')
    conta_contrapartida = db.relationship('ContaDominio')

    __table_args__ = (
        db.UniqueConstraint('admin_id', 'categoria_fluxo_caixa_id',
                            name='uq_regra_conta_dominio_admin_categoria'),
        db.Index('idx_regra_conta_dominio_admin', 'admin_id', 'ativo'),
    )
```

- [ ] **Step 4: Migration**

```python
def _migration_291_regra_conta_dominio():
    """Fase 8 — de/para categoria → situação contábil + contrapartida.

    Estruturado como DADO, não como código (docs/integracao-dominio.md:118-120),
    para a contabilidade manter sem deploy.
    """
    from sqlalchemy import text as sa_text
    try:
        with db.engine.begin() as conn:
            conn.execute(sa_text("""
                CREATE TABLE IF NOT EXISTS regra_conta_dominio (
                    id                       SERIAL PRIMARY KEY,
                    admin_id                 INTEGER     NOT NULL REFERENCES usuario(id),
                    categoria_fluxo_caixa_id INTEGER     NOT NULL
                        REFERENCES categoria_fluxo_caixa(id),
                    situacao                 VARCHAR(30) NOT NULL,
                    conta_contrapartida_id   INTEGER
                        REFERENCES conta_dominio(id) ON DELETE SET NULL,
                    ativo                    BOOLEAN     NOT NULL DEFAULT TRUE,
                    created_at               TIMESTAMP   DEFAULT NOW(),
                    updated_at               TIMESTAMP   DEFAULT NOW(),
                    CONSTRAINT uq_regra_conta_dominio_admin_categoria
                        UNIQUE (admin_id, categoria_fluxo_caixa_id)
                )
            """))
            conn.execute(sa_text("""
                CREATE INDEX IF NOT EXISTS idx_regra_conta_dominio_admin
                  ON regra_conta_dominio (admin_id, ativo)
            """))
        logger.info("[Migration 291] regra_conta_dominio criada.")
    except Exception as e:
        logger.error(f"[Migration 291] Falha: {e}", exc_info=True)
        raise
```

Registro:

```python
            (291, "Fase 8 — de/para categoria → situação contábil e contrapartida", _migration_291_regra_conta_dominio),
```

- [ ] **Step 5: Rode e veja passar**

Run: `pytest tests/test_dominio_schema.py -v`
Expected: 7 passed

- [ ] **Step 6: Commit**

```bash
git add models.py migrations.py tests/test_dominio_schema.py
git commit -m "feat(dominio): tabela regra_conta_dominio (migration 291)"
```

---

## Task B13: Amarrar banco e fornecedor à conta do Domínio (migration 292)

**Files:**
- Modify: `models.py:1825-1845` (`BancoEmpresa`), `models.py:1676-1730` (`Fornecedor`)
- Modify: `migrations.py`
- Test: `tests/test_dominio_schema.py`

- [ ] **Step 1: Escreva o teste que falha**

Acrescente a `tests/test_dominio_schema.py`:

```python
def test_banco_aponta_para_a_conta_do_dominio():
    from models import BancoEmpresa, ContaDominio
    with app.app_context():
        a = _admin()
        conta = ContaDominio(admin_id=a, codigo_reduzido='1015', nome='Itaú CC')
        db.session.add(conta)
        db.session.flush()
        banco = BancoEmpresa(admin_id=a, nome_banco='Itaú', agencia='0001',
                             conta='12345-6', conta_dominio_id=conta.id)
        db.session.add(banco)
        db.session.commit()
        assert banco.conta_dominio.codigo_reduzido == '1015'


def test_fornecedor_aponta_para_a_conta_nominal_do_dominio():
    """Decisão D7 — a conta nominal vem do cadastro, não de matching de texto."""
    from models import ContaDominio, Fornecedor
    with app.app_context():
        a = _admin()
        conta = ContaDominio(admin_id=a, codigo_reduzido='2031', nome='Aço Norte')
        db.session.add(conta)
        db.session.flush()
        f = Fornecedor(admin_id=a, nome='Aço Norte', cnpj=f'{uuid.uuid4().int % 10**14:014d}',
                       conta_dominio_id=conta.id)
        db.session.add(f)
        db.session.commit()
        assert f.conta_dominio.codigo_reduzido == '2031'


def test_amarracao_e_opcional():
    from models import BancoEmpresa
    with app.app_context():
        b = BancoEmpresa(admin_id=_admin(), nome_banco='Caixa', agencia='0002',
                         conta='99999-9')
        db.session.add(b)
        db.session.commit()
        assert b.conta_dominio_id is None
```

- [ ] **Step 2: Rode e veja falhar**

Run: `pytest tests/test_dominio_schema.py -k "banco or fornecedor or amarracao" -v`
Expected: `TypeError: 'conta_dominio_id' is an invalid keyword argument for BancoEmpresa`

- [ ] **Step 3: Colunas**

Em `models.py`, dentro de `BancoEmpresa` (depois de `data_saldo_inicial`, hoje `models.py:1836`):

```python
    # Fase 8 — código reduzido desta conta no plano do Domínio
    conta_dominio_id = db.Column(
        db.Integer, db.ForeignKey('conta_dominio.id', ondelete='SET NULL'))
```

E o relationship, junto dos demais:

```python
    conta_dominio = db.relationship('ContaDominio')
```

Em `models.py`, dentro de `Fornecedor` (depois de `chave_pix`, hoje `models.py:1702`):

```python
    # Fase 8 — conta nominal deste fornecedor no plano do Domínio (decisão D7)
    conta_dominio_id = db.Column(
        db.Integer, db.ForeignKey('conta_dominio.id', ondelete='SET NULL'))
```

E o relationship, junto de `categorias` (`models.py:1715-1723`):

```python
    conta_dominio = db.relationship('ContaDominio')
```

- [ ] **Step 4: Migration**

```python
def _migration_292_amarracao_conta_dominio():
    """Fase 8 — banco_empresa e fornecedor apontam para conta_dominio.

    Decisão D7: a conta nominal do fornecedor é CADASTRO, não matching de
    texto na hora da exportação (o que o ADR-0002 já removeu da classificação).
    """
    from sqlalchemy import text as sa_text
    try:
        with db.engine.begin() as conn:
            for tabela in ('banco_empresa', 'fornecedor'):
                conn.execute(sa_text(f"""
                    ALTER TABLE {tabela}
                      ADD COLUMN IF NOT EXISTS conta_dominio_id INTEGER
                      REFERENCES conta_dominio(id) ON DELETE SET NULL
                """))
                conn.execute(sa_text(f"""
                    CREATE INDEX IF NOT EXISTS idx_{tabela}_conta_dominio
                      ON {tabela} (conta_dominio_id)
                      WHERE conta_dominio_id IS NOT NULL
                """))
        logger.info("[Migration 292] conta_dominio_id em banco_empresa e fornecedor.")
    except Exception as e:
        logger.error(f"[Migration 292] Falha: {e}", exc_info=True)
        raise
```

Registro:

```python
            (292, "Fase 8 — banco_empresa.conta_dominio_id e fornecedor.conta_dominio_id", _migration_292_amarracao_conta_dominio),
```

- [ ] **Step 5: Rode e veja passar**

Run: `pytest tests/test_dominio_schema.py -v`
Expected: 10 passed

- [ ] **Step 6: Commit**

```bash
git add models.py migrations.py tests/test_dominio_schema.py
git commit -m "feat(dominio): amarracao de banco e fornecedor a conta_dominio (migration 292)"
```


---

## Task B14: Transferência vira par no razão (migration 293)

**Files:**
- Modify: `models.py:781-812` (`FluxoCaixa`)
- Modify: `migrations.py`
- Modify: `services/importacao_excel.py:2129` (`ImportacaoFluxoCaixa.importar`)
- Modify: `importacao_views.py:942-946`
- Test: `tests/test_dominio_transferencia.py`

> **Fecha o buraco B.** Hoje a transferência é detectada (`services/importacao_excel.py:1961`), colocada numa lista (`:1964-1972`), viaja no payload assinado (`importacao_views.py:473`) — e é **descartada**: `importar` só lê `dados['saidas']` e `dados['entradas']`, e o confirmar nem repassa a lista (`importacao_views.py:942-946`). O razão fica incompleto e o saldo por banco não fecha. Decisão D5.

- [ ] **Step 1: Escreva o teste que falha**

Crie `tests/test_dominio_transferencia.py`:

```python
"""Fase 8 — transferência entre contas passa a existir no razão de caixa.

Antes desta tarefa: o importador detectava a transferência
(services/importacao_excel.py:1357,1961), guardava numa lista à parte
(:1964-1972) e fazia `continue` (:1973). A lista chegava até o template
(importacao_views.py:515) mas NUNCA virava FluxoCaixa — `importar`
(services/importacao_excel.py:2129) só lê 'saidas' e 'entradas', e o
confirmar nem repassava a chave (importacao_views.py:942-946).
"""
import os
import sys
import uuid
from datetime import date
from decimal import Decimal

import pytest
from werkzeug.security import generate_password_hash

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import main  # noqa: F401
from app import app, db
from models import TipoUsuario, Usuario

pytestmark = pytest.mark.integration


@pytest.fixture(autouse=True)
def _config():
    app.config['TESTING'] = True
    if not app.secret_key:
        app.secret_key = 'test-fase8-transf'
    yield


def _cenario():
    from models import BancoEmpresa
    suf = uuid.uuid4().hex[:8]
    u = Usuario(username=f'tr_{suf}', email=f'tr_{suf}@test.local', nome='T',
                password_hash=generate_password_hash('x'),
                tipo_usuario=TipoUsuario.ADMIN, ativo=True, versao_sistema='v2')
    db.session.add(u)
    db.session.flush()
    origem = BancoEmpresa(admin_id=u.id, nome_banco='Itaú', agencia='1', conta='1')
    destino = BancoEmpresa(admin_id=u.id, nome_banco='Nubank', agencia='2', conta='2')
    db.session.add_all([origem, destino])
    db.session.commit()
    return u.id, origem.id, destino.id


def test_transferencia_cria_duas_linhas_ligadas():
    from models import FluxoCaixa
    from services.importacao_excel import ImportacaoFluxoCaixa
    with app.app_context():
        admin_id, origem_id, destino_id = _cenario()
        batch = f'tst_{uuid.uuid4().hex[:6]}'
        ImportacaoFluxoCaixa().importar({
            'entradas': [], 'saidas': [], 'batch_id': batch,
            'transferencias': [{
                'data': '2026-03-07', 'valor': 5000.0,
                'descricao': 'Transferência de valores ITAU - NUBANK',
                'banco_origem_id': origem_id, 'banco_destino_id': destino_id,
            }],
        }, admin_id)

        linhas = FluxoCaixa.query.filter_by(admin_id=admin_id, import_batch_id=batch).all()
        assert len(linhas) == 2
        saida = next(l for l in linhas if l.tipo_movimento == 'SAIDA')
        entrada = next(l for l in linhas if l.tipo_movimento == 'ENTRADA')
        assert saida.transferencia_par_id == entrada.id
        assert entrada.transferencia_par_id == saida.id
        assert saida.banco_id == origem_id
        assert entrada.banco_id == destino_id


def test_transferencia_grava_valor_em_decimal():
    """A coluna é NUMERIC(15,2) desde a migration 188 (migrations.py:13803).
    O par não pode reintroduzir float."""
    from models import FluxoCaixa
    from services.importacao_excel import ImportacaoFluxoCaixa
    with app.app_context():
        admin_id, origem_id, destino_id = _cenario()
        batch = f'tst_{uuid.uuid4().hex[:6]}'
        ImportacaoFluxoCaixa().importar({
            'entradas': [], 'saidas': [], 'batch_id': batch,
            'transferencias': [{
                'data': '2026-03-07', 'valor': '1234,57',
                'descricao': 'Transferência de valores',
                'banco_origem_id': origem_id, 'banco_destino_id': destino_id,
            }],
        }, admin_id)
        linha = FluxoCaixa.query.filter_by(admin_id=admin_id, import_batch_id=batch).first()
        assert linha.valor == Decimal('1234.57')


def test_transferencia_sem_banco_de_destino_e_ignorada():
    """Sem os dois bancos não há par determinístico — não inventar."""
    from models import FluxoCaixa
    from services.importacao_excel import ImportacaoFluxoCaixa
    with app.app_context():
        admin_id, origem_id, _ = _cenario()
        batch = f'tst_{uuid.uuid4().hex[:6]}'
        r = ImportacaoFluxoCaixa().importar({
            'entradas': [], 'saidas': [], 'batch_id': batch,
            'transferencias': [{
                'data': '2026-03-07', 'valor': 100.0, 'descricao': 'Transf',
                'banco_origem_id': origem_id, 'banco_destino_id': None,
            }],
        }, admin_id)
        assert FluxoCaixa.query.filter_by(import_batch_id=batch).count() == 0
        assert r['n_transferencias_ignoradas'] == 1
```

- [ ] **Step 2: Rode e veja falhar**

Run: `pytest tests/test_dominio_transferencia.py -v`
Expected: `AttributeError: 'FluxoCaixa' object has no attribute 'transferencia_par_id'`

- [ ] **Step 3: Coluna e migration**

Em `models.py`, dentro de `FluxoCaixa` (depois de `funcionario_id`, hoje `models.py:804`):

```python
    # Fase 8 / decisão D5 — as duas pernas de uma transferência entre contas
    # apontam uma para a outra. O exportador do Domínio colapsa o par em UM
    # lançamento (docs/integracao-dominio.md:79-83) sem heurística de valor/data.
    transferencia_par_id = db.Column(
        db.Integer, db.ForeignKey('fluxo_caixa.id', ondelete='SET NULL'))
```

Em `migrations.py`:

```python
def _migration_293_fluxo_caixa_transferencia_par():
    """Fase 8 — par explícito de transferência entre contas.

    Fecha o buraco em que a transferência era detectada
    (services/importacao_excel.py:1961) e descartada (:1973), deixando o
    razão de caixa incompleto.
    """
    from sqlalchemy import text as sa_text
    try:
        with db.engine.begin() as conn:
            conn.execute(sa_text("""
                ALTER TABLE fluxo_caixa
                  ADD COLUMN IF NOT EXISTS transferencia_par_id INTEGER
                  REFERENCES fluxo_caixa(id) ON DELETE SET NULL
            """))
            conn.execute(sa_text("""
                CREATE INDEX IF NOT EXISTS idx_fluxo_caixa_transferencia_par
                  ON fluxo_caixa (transferencia_par_id)
                  WHERE transferencia_par_id IS NOT NULL
            """))
        logger.info("[Migration 293] fluxo_caixa.transferencia_par_id criada.")
    except Exception as e:
        logger.error(f"[Migration 293] Falha: {e}", exc_info=True)
        raise
```

Registro:

```python
            (293, "Fase 8 — fluxo_caixa.transferencia_par_id (par de transferência entre contas)", _migration_293_fluxo_caixa_transferencia_par),
```

- [ ] **Step 4: O importador passa a persistir o par**

Em `services/importacao_excel.py`, dentro de `importar` (a função começa em `:2129`), **antes** do `db.session.commit()` de `:2521`, acrescente:

```python
            # ── Transferências entre contas: duas pernas ligadas ────────────
            # Detectadas no preview (:1961) e até aqui descartadas. Sem os
            # dois bancos não há par determinístico: a linha é ignorada e
            # contada, nunca adivinhada.
            for t in dados.get('transferencias', []):
                origem_id = t.get('banco_origem_id')
                destino_id = t.get('banco_destino_id')
                if not origem_id or not destino_id or origem_id == destino_id:
                    n_transferencias_ignoradas += 1
                    continue
                data_t = _parse_data(t.get('data'))
                valor_t = _parse_decimal(t.get('valor'))
                if not data_t or not valor_t or valor_t <= 0:
                    n_transferencias_ignoradas += 1
                    continue
                desc_t = (t.get('descricao') or 'Transferência entre contas')[:200]

                saida_t = FluxoCaixa(
                    admin_id=admin_id, data_movimento=data_t,
                    tipo_movimento='SAIDA', categoria='transferencia',
                    valor=valor_t, descricao=desc_t, banco_id=origem_id,
                    import_batch_id=batch_id,
                )
                entrada_t = FluxoCaixa(
                    admin_id=admin_id, data_movimento=data_t,
                    tipo_movimento='ENTRADA', categoria='transferencia',
                    valor=valor_t, descricao=desc_t, banco_id=destino_id,
                    import_batch_id=batch_id,
                )
                db.session.add_all([saida_t, entrada_t])
                db.session.flush()
                saida_t.transferencia_par_id = entrada_t.id
                entrada_t.transferencia_par_id = saida_t.id
                n_transferencias += 1
```

Inicialize os dois contadores junto dos demais (`services/importacao_excel.py:2150-2158`):

```python
        n_transferencias = 0
        n_transferencias_ignoradas = 0
```

E acrescente ao dicionário de retorno (`services/importacao_excel.py:2528-2541`):

```python
            'n_transferencias': n_transferencias,
            'n_transferencias_ignoradas': n_transferencias_ignoradas,
```

- [ ] **Step 5: A tela de confirmação repassa a lista**

Em `importacao_views.py:942-946`, acrescente a chave que hoje falta:

```python
        resultado = svc.importar({
            'entradas': entradas,
            'saidas': todas_saidas,
            'transferencias': payload.get('transferencias', []),
            'batch_id': batch_id,
        }, admin_id)
```

- [ ] **Step 6: Rode e veja passar**

Run: `pytest tests/test_dominio_transferencia.py -v`
Expected: 3 passed

- [ ] **Step 7: Commit**

```bash
git add models.py migrations.py services/importacao_excel.py importacao_views.py tests/test_dominio_transferencia.py
git commit -m "feat(dominio): transferencia entre contas vira par no razao (migration 293)"
```

---

## Task B15: Trilha de auditoria da exportação (migration 294)

**Files:**
- Modify: `models.py`
- Modify: `migrations.py`
- Test: `tests/test_dominio_schema.py`

- [ ] **Step 1: Escreva o teste que falha**

Acrescente a `tests/test_dominio_schema.py`:

```python
def test_exportacao_registra_periodo_hash_e_contadores():
    from datetime import date
    from models import ExportacaoDominio
    with app.app_context():
        a = _admin()
        e = ExportacaoDominio(
            admin_id=a, data_inicio=date(2026, 3, 1), data_fim=date(2026, 3, 31),
            nome_arquivo='importacao_dominio_veks_2026-03.csv',
            hash_arquivo='deadbeef' * 8, status='GERADO',
            total_movimentos=120, total_linhas=110, total_pendencias=8,
            total_descartes=2, layout_conferido=False,
        )
        db.session.add(e)
        db.session.commit()
        assert e.id is not None
        assert e.layout_conferido is False


def test_pendencia_pertence_a_uma_exportacao_e_guarda_o_motivo():
    from datetime import date
    from decimal import Decimal
    from models import ExportacaoDominio, ExportacaoDominioPendencia
    with app.app_context():
        a = _admin()
        e = ExportacaoDominio(admin_id=a, data_inicio=date(2026, 3, 1),
                              data_fim=date(2026, 3, 31),
                              nome_arquivo='x.csv', hash_arquivo='y', status='BLOQUEADO')
        db.session.add(e)
        db.session.flush()
        p = ExportacaoDominioPendencia(
            exportacao_id=e.id, admin_id=a, fluxo_caixa_id=None,
            data_movimento=date(2026, 3, 7), descricao='CEMIG fatura',
            valor=Decimal('980.00'), conta='', motivo='categoria sem regra de conta cadastrada')
        db.session.add(p)
        db.session.commit()
        assert e.pendencias[0].motivo.startswith('categoria sem regra')


def test_apagar_a_exportacao_leva_as_pendencias_junto():
    from datetime import date
    from models import ExportacaoDominio, ExportacaoDominioPendencia
    with app.app_context():
        a = _admin()
        e = ExportacaoDominio(admin_id=a, data_inicio=date(2026, 3, 1),
                              data_fim=date(2026, 3, 31),
                              nome_arquivo='x.csv', hash_arquivo='y', status='GERADO')
        db.session.add(e)
        db.session.flush()
        db.session.add(ExportacaoDominioPendencia(
            exportacao_id=e.id, admin_id=a, data_movimento=date(2026, 3, 7),
            descricao='x', valor=0, conta='', motivo='m'))
        db.session.commit()
        eid = e.id
        db.session.delete(e)
        db.session.commit()
        assert ExportacaoDominioPendencia.query.filter_by(exportacao_id=eid).count() == 0
```

- [ ] **Step 2: Rode e veja falhar**

Run: `pytest tests/test_dominio_schema.py -k exportacao -v`
Expected: `ImportError: cannot import name 'ExportacaoDominio' from 'models'`

- [ ] **Step 3: Modelos**

Acrescente a `models.py`, depois de `RegraContaDominio`:

```python
class ExportacaoDominio(db.Model):
    """Uma execução da exportação para o Domínio (decisão D6: manual, mensal).

    Dá idempotência (não reexportar o mesmo período sem querer) e trilha —
    o mês de calibração vai ter várias tentativas bloqueadas antes da boa
    (docs/integracao-dominio.md:31-32).
    """
    __tablename__ = 'exportacao_dominio'

    id = db.Column(db.Integer, primary_key=True)
    admin_id = db.Column(db.Integer, db.ForeignKey('usuario.id'), nullable=False)
    data_inicio = db.Column(db.Date, nullable=False)
    data_fim = db.Column(db.Date, nullable=False)
    nome_arquivo = db.Column(db.String(200), nullable=False)
    hash_arquivo = db.Column(db.String(64), nullable=False)
    status = db.Column(db.String(20), nullable=False, default='GERADO')  # GERADO | BLOQUEADO
    erros = db.Column(db.Text)              # validações bloqueantes, uma por linha
    total_movimentos = db.Column(db.Integer, nullable=False, default=0)
    total_linhas = db.Column(db.Integer, nullable=False, default=0)
    total_pendencias = db.Column(db.Integer, nullable=False, default=0)
    total_descartes = db.Column(db.Integer, nullable=False, default=0)
    total_sem_obra = db.Column(db.Integer, nullable=False, default=0)  # alerta, não pendência (D4)
    layout_conferido = db.Column(db.Boolean, nullable=False, default=False)
    usuario_id = db.Column(db.Integer, db.ForeignKey('usuario.id'))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    pendencias = db.relationship('ExportacaoDominioPendencia', backref='exportacao',
                                 cascade='all, delete-orphan', lazy=True)

    __table_args__ = (
        db.Index('idx_exportacao_dominio_admin_periodo',
                 'admin_id', 'data_inicio', 'data_fim'),
    )


class ExportacaoDominioPendencia(db.Model):
    """Linha que não virou lançamento. Alimenta o relatório .xlsx
    (docs/integracao-dominio.md:113)."""
    __tablename__ = 'exportacao_dominio_pendencia'

    id = db.Column(db.Integer, primary_key=True)
    exportacao_id = db.Column(
        db.Integer, db.ForeignKey('exportacao_dominio.id', ondelete='CASCADE'),
        nullable=False)
    admin_id = db.Column(db.Integer, db.ForeignKey('usuario.id'), nullable=False)
    fluxo_caixa_id = db.Column(
        db.Integer, db.ForeignKey('fluxo_caixa.id', ondelete='SET NULL'))
    data_movimento = db.Column(db.Date, nullable=False)
    descricao = db.Column(db.String(300), nullable=False)
    valor = db.Column(db.Numeric(15, 2), nullable=False)
    conta = db.Column(db.String(20))
    motivo = db.Column(db.String(200), nullable=False)

    __table_args__ = (
        db.Index('idx_exportacao_dominio_pendencia_exp', 'exportacao_id'),
    )
```

- [ ] **Step 4: Migration**

```python
def _migration_294_exportacao_dominio():
    """Fase 8 — trilha das execuções de exportação e suas pendências."""
    from sqlalchemy import text as sa_text
    try:
        with db.engine.begin() as conn:
            conn.execute(sa_text("""
                CREATE TABLE IF NOT EXISTS exportacao_dominio (
                    id               SERIAL PRIMARY KEY,
                    admin_id         INTEGER      NOT NULL REFERENCES usuario(id),
                    data_inicio      DATE         NOT NULL,
                    data_fim         DATE         NOT NULL,
                    nome_arquivo     VARCHAR(200) NOT NULL,
                    hash_arquivo     VARCHAR(64)  NOT NULL,
                    status           VARCHAR(20)  NOT NULL DEFAULT 'GERADO',
                    erros            TEXT,
                    total_movimentos INTEGER      NOT NULL DEFAULT 0,
                    total_linhas     INTEGER      NOT NULL DEFAULT 0,
                    total_pendencias INTEGER      NOT NULL DEFAULT 0,
                    total_descartes  INTEGER      NOT NULL DEFAULT 0,
                    total_sem_obra   INTEGER      NOT NULL DEFAULT 0,
                    layout_conferido BOOLEAN      NOT NULL DEFAULT FALSE,
                    usuario_id       INTEGER      REFERENCES usuario(id),
                    created_at       TIMESTAMP    DEFAULT NOW()
                )
            """))
            conn.execute(sa_text("""
                CREATE INDEX IF NOT EXISTS idx_exportacao_dominio_admin_periodo
                  ON exportacao_dominio (admin_id, data_inicio, data_fim)
            """))
            conn.execute(sa_text("""
                CREATE TABLE IF NOT EXISTS exportacao_dominio_pendencia (
                    id             SERIAL PRIMARY KEY,
                    exportacao_id  INTEGER       NOT NULL
                        REFERENCES exportacao_dominio(id) ON DELETE CASCADE,
                    admin_id       INTEGER       NOT NULL REFERENCES usuario(id),
                    fluxo_caixa_id INTEGER       REFERENCES fluxo_caixa(id) ON DELETE SET NULL,
                    data_movimento DATE          NOT NULL,
                    descricao      VARCHAR(300)  NOT NULL,
                    valor          NUMERIC(15,2) NOT NULL,
                    conta          VARCHAR(20),
                    motivo         VARCHAR(200)  NOT NULL
                )
            """))
            conn.execute(sa_text("""
                CREATE INDEX IF NOT EXISTS idx_exportacao_dominio_pendencia_exp
                  ON exportacao_dominio_pendencia (exportacao_id)
            """))
        logger.info("[Migration 294] exportacao_dominio e pendências criadas.")
    except Exception as e:
        logger.error(f"[Migration 294] Falha: {e}", exc_info=True)
        raise
```

Registro:

```python
            (294, "Fase 8 — trilha de exportação para o Domínio e pendências", _migration_294_exportacao_dominio),
```

- [ ] **Step 5: Rode e veja passar**

Run: `pytest tests/test_dominio_schema.py -v`
Expected: 13 passed

- [ ] **Step 6: Commit**

```bash
git add models.py migrations.py tests/test_dominio_schema.py
git commit -m "feat(dominio): trilha de exportacao e pendencias (migration 294)"
```


---

## Task B16: Semear a situação contábil das 45 categorias (migration 295)

**Files:**
- Create: `services/seed_regras_dominio.py`
- Modify: `migrations.py`
- Test: `tests/test_dominio_seed.py`

> **Por que semear a situação e não a conta:** o plano de contas da Veks ainda não foi entregue (`docs/integracao-dominio.md:144-146`). A situação é regra contábil geral e não depende do plano; a conta depende. Semeando só a situação, o primeiro relatório de pendências diz *"conta não mapeada para a categoria X"* em vez de *"categoria desconhecida"* — que é a informação de que a contabilidade precisa para preencher o de/para.
>
> Segue o padrão da migration 191 (`migrations.py:12305`), que semeia as Regras de Classificação por tenant chamando um módulo de serviço.

- [ ] **Step 1: Escreva o teste que falha**

Crie `tests/test_dominio_seed.py`:

```python
"""Fase 8 — seed da situação contábil por categoria de fluxo de caixa.

Semeia SÓ a situação (regra contábil geral, docs/integracao-dominio.md:66-75),
nunca a conta: o plano de contas da Veks não foi entregue (:144-146) e
inventar código de conta é proibido (:90-91).
"""
import os
import sys
import uuid

import pytest
from werkzeug.security import generate_password_hash

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import main  # noqa: F401
from app import app, db
from models import TipoUsuario, Usuario

pytestmark = pytest.mark.integration


@pytest.fixture(autouse=True)
def _config():
    app.config['TESTING'] = True
    if not app.secret_key:
        app.secret_key = 'test-fase8-seed'
    yield


def _tenant_com_categorias():
    from models import CategoriaFluxoCaixa
    suf = uuid.uuid4().hex[:8]
    u = Usuario(username=f'sd_{suf}', email=f'sd_{suf}@test.local', nome='S',
                password_hash=generate_password_hash('x'),
                tipo_usuario=TipoUsuario.ADMIN, ativo=True, versao_sistema='v2')
    db.session.add(u)
    db.session.flush()
    CategoriaFluxoCaixa.seed_defaults(u.id)
    db.session.commit()
    return u.id


def test_seed_cria_uma_regra_por_categoria_do_tenant():
    from models import CategoriaFluxoCaixa, RegraContaDominio
    from services.seed_regras_dominio import seed_para_admin
    with app.app_context():
        aid = _tenant_com_categorias()
        seed_para_admin(aid, commit=True)
        n_cat = CategoriaFluxoCaixa.query.filter_by(admin_id=aid, ativo=True).count()
        assert RegraContaDominio.query.filter_by(admin_id=aid).count() == n_cat


def test_seed_nao_preenche_conta():
    from models import RegraContaDominio
    from services.seed_regras_dominio import seed_para_admin
    with app.app_context():
        aid = _tenant_com_categorias()
        seed_para_admin(aid, commit=True)
        regras = RegraContaDominio.query.filter_by(admin_id=aid).all()
        assert all(r.conta_contrapartida_id is None for r in regras)


def test_material_de_obra_e_pagamento_a_fornecedor():
    from models import CategoriaFluxoCaixa, RegraContaDominio
    from services.seed_regras_dominio import seed_para_admin
    with app.app_context():
        aid = _tenant_com_categorias()
        seed_para_admin(aid, commit=True)
        cat = CategoriaFluxoCaixa.query.filter_by(
            admin_id=aid, nome='Materiais de Obra').first()
        r = RegraContaDominio.query.filter_by(
            admin_id=aid, categoria_fluxo_caixa_id=cat.id).first()
        assert r.situacao == 'PAGAMENTO_FORNECEDOR'


def test_despesas_bancarias_e_tarifa():
    from models import CategoriaFluxoCaixa, RegraContaDominio
    from services.seed_regras_dominio import seed_para_admin
    with app.app_context():
        aid = _tenant_com_categorias()
        seed_para_admin(aid, commit=True)
        cat = CategoriaFluxoCaixa.query.filter_by(
            admin_id=aid, nome='Despesas Bancárias').first()
        r = RegraContaDominio.query.filter_by(
            admin_id=aid, categoria_fluxo_caixa_id=cat.id).first()
        assert r.situacao == 'TARIFA_BANCARIA'


def test_receita_de_obras_e_recebimento_de_cliente():
    from models import CategoriaFluxoCaixa, RegraContaDominio
    from services.seed_regras_dominio import seed_para_admin
    with app.app_context():
        aid = _tenant_com_categorias()
        seed_para_admin(aid, commit=True)
        cat = CategoriaFluxoCaixa.query.filter_by(
            admin_id=aid, nome='Receita de Obras').first()
        r = RegraContaDominio.query.filter_by(
            admin_id=aid, categoria_fluxo_caixa_id=cat.id).first()
        assert r.situacao == 'RECEBIMENTO_CLIENTE'


def test_categoria_fora_do_de_para_cai_na_generica_do_seu_tipo():
    """Aporte de Sócios não existe na tabela do contrato (:66-75) — vira
    ENTRADA_DIVERSA em vez de mentir 'Receb. cliente'."""
    from models import CategoriaFluxoCaixa, RegraContaDominio
    from services.seed_regras_dominio import seed_para_admin
    with app.app_context():
        aid = _tenant_com_categorias()
        seed_para_admin(aid, commit=True)
        cat = CategoriaFluxoCaixa.query.filter_by(
            admin_id=aid, nome='Aporte de Sócios').first()
        r = RegraContaDominio.query.filter_by(
            admin_id=aid, categoria_fluxo_caixa_id=cat.id).first()
        assert r.situacao == 'ENTRADA_DIVERSA'


def test_seed_e_idempotente():
    from models import RegraContaDominio
    from services.seed_regras_dominio import seed_para_admin
    with app.app_context():
        aid = _tenant_com_categorias()
        seed_para_admin(aid, commit=True)
        n = RegraContaDominio.query.filter_by(admin_id=aid).count()
        seed_para_admin(aid, commit=True)
        assert RegraContaDominio.query.filter_by(admin_id=aid).count() == n


def test_seed_nao_sobrescreve_ajuste_do_usuario():
    from models import CategoriaFluxoCaixa, RegraContaDominio
    from services.seed_regras_dominio import seed_para_admin
    with app.app_context():
        aid = _tenant_com_categorias()
        seed_para_admin(aid, commit=True)
        cat = CategoriaFluxoCaixa.query.filter_by(
            admin_id=aid, nome='Materiais de Obra').first()
        r = RegraContaDominio.query.filter_by(
            admin_id=aid, categoria_fluxo_caixa_id=cat.id).first()
        r.situacao = 'DESPESA_DIRETA'
        db.session.commit()
        seed_para_admin(aid, commit=True)
        db.session.refresh(r)
        assert r.situacao == 'DESPESA_DIRETA'
```

- [ ] **Step 2: Rode e veja falhar**

Run: `pytest tests/test_dominio_seed.py -v`
Expected: `ModuleNotFoundError: No module named 'services.seed_regras_dominio'`

- [ ] **Step 3: Implementação mínima**

Crie `services/seed_regras_dominio.py`:

```python
"""Seed da situação contábil por categoria de fluxo de caixa (Fase 8).

Semeia SÓ a situação — regra contábil geral da tabela
docs/integracao-dominio.md:66-75. A conta de contrapartida fica NULA até a
contabilidade entregar o plano de contas da Veks (:144-146); inventar
código de conta é proibido (:90-91).

Idempotente por (admin_id, categoria): nunca sobrescreve o que o usuário
ajustou. Mesmo contrato do seed de Regras de Classificação
(services/seed_palavras_chave.py, migration 191).
"""
from models import CategoriaFluxoCaixa, RegraContaDominio, db
from services.classificador_cadastro import _norm

# Nome da categoria (CategoriaFluxoCaixa._DEFAULTS, models.py:7192-7249)
# → situação contábil (services/dominio_mapeamento.py:LADO_DO_BANCO).
SITUACAO_POR_CATEGORIA = {
    # ── Custo direto de obra: compra de terceiro, dá baixa em Fornecedores
    "Mão de Obra Direta":                  "PAGAMENTO_FORNECEDOR",
    "Subempreitada":                       "PAGAMENTO_FORNECEDOR",
    "Serviços Terceirizados de Obra":      "PAGAMENTO_FORNECEDOR",
    "Materiais de Obra":                   "PAGAMENTO_FORNECEDOR",
    "Ferramentas e Consumíveis":           "PAGAMENTO_FORNECEDOR",
    "EPIs e Segurança do Trabalho":        "PAGAMENTO_FORNECEDOR",
    "Locação de Equipamentos":             "PAGAMENTO_FORNECEDOR",
    "Fretes e Entregas":                   "PAGAMENTO_FORNECEDOR",
    # ── Despesa operacional direta: sem NF prévia, debita a conta da despesa
    "Combustível e Frota":                 "DESPESA_DIRETA",
    "Manutenção de Frota e Equipamentos":  "DESPESA_DIRETA",
    "Transporte de Obra":                  "DESPESA_DIRETA",
    "Alimentação de Obra":                 "DESPESA_DIRETA",
    "Hospedagem de Obra":                  "DESPESA_DIRETA",
    "Benefício Alimentação":               "DESPESA_DIRETA",
    "Benefício Transporte":                "DESPESA_DIRETA",
    "Salários e Encargos":                 "DESPESA_DIRETA",
    "Pró-labore e Retirada de Sócios":     "DESPESA_DIRETA",
    "Reembolsos a Funcionários":           "DESPESA_DIRETA",
    "Despesa Financeira":                  "DESPESA_DIRETA",
    "Água":                                "DESPESA_DIRETA",
    "Luz / Energia Elétrica":              "DESPESA_DIRETA",
    "Internet":                            "DESPESA_DIRETA",
    "Telefone":                            "DESPESA_DIRETA",
    "Sistemas e Assinaturas":              "DESPESA_DIRETA",
    "Aluguel e Locação Administrativa":    "DESPESA_DIRETA",
    "Contabilidade e Jurídico":            "DESPESA_DIRETA",
    "Marketing e Vendas":                  "DESPESA_DIRETA",
    "Material de Escritório":              "DESPESA_DIRETA",
    "Treinamentos e Capacitações":         "DESPESA_DIRETA",
    "Manutenção Predial e Escritório":     "DESPESA_DIRETA",
    # ── Tributos: provisão já feita, debita a conta do imposto
    "Impostos e Taxas":                    "IMPOSTO",
    "Taxas de Obra / ART / Licenças":      "IMPOSTO",
    # ── Tarifa bancária
    "Despesas Bancárias":                  "TARIFA_BANCARIA",
    # ── Entradas de cliente: dão baixa em Clientes, nunca lançam receita
    "Receita de Obras":                    "RECEBIMENTO_CLIENTE",
    "Receita de Serviços":                 "RECEBIMENTO_CLIENTE",
    "Adiantamento de Clientes":            "RECEBIMENTO_CLIENTE",
    "Reembolso de Cliente":                "RECEBIMENTO_CLIENTE",
}

# Categorias fora da tabela do contrato caem na genérica do seu tipo.
# São: Empréstimos e Financiamentos, Outras Saídas (SAIDA); Aporte de Sócios,
# Empréstimos Recebidos, Rendimentos Financeiros, Venda de Ativos,
# Outros Recebimentos (ENTRADA). Ver lacuna 11 do plano da Fase 8.
GENERICA_POR_TIPO = {"ENTRADA": "ENTRADA_DIVERSA", "SAIDA": "SAIDA_DIVERSA"}

_SITUACAO_NORM = {_norm(k): v for k, v in SITUACAO_POR_CATEGORIA.items()}


def situacao_para(nome_categoria, tipo) -> str:
    return _SITUACAO_NORM.get(_norm(nome_categoria),
                              GENERICA_POR_TIPO.get(tipo, "SAIDA_DIVERSA"))


def seed_para_admin(admin_id: int, commit: bool = False) -> int:
    """Cria a regra que falta para cada categoria ativa do tenant.
    Não toca em regra existente. Devolve quantas criou."""
    existentes = {
        r.categoria_fluxo_caixa_id
        for r in RegraContaDominio.query.filter_by(admin_id=admin_id).all()
    }
    criadas = 0
    for cat in CategoriaFluxoCaixa.query.filter_by(admin_id=admin_id, ativo=True).all():
        if cat.id in existentes:
            continue
        db.session.add(RegraContaDominio(
            admin_id=admin_id,
            categoria_fluxo_caixa_id=cat.id,
            situacao=situacao_para(cat.nome, cat.tipo),
        ))
        criadas += 1
    db.session.flush()
    if commit:
        db.session.commit()
    return criadas
```

- [ ] **Step 4: Migration**

Em `migrations.py`, no estilo da migration 191 (`migrations.py:12305`):

```python
def _migration_295_seed_regras_dominio():
    """Fase 8 — semeia a situação contábil por categoria em cada tenant.

    Só a situação; a conta de contrapartida fica NULA até o plano de contas
    da Veks chegar (docs/integracao-dominio.md:144-146).
    """
    from models import TipoUsuario, Usuario
    from services.seed_regras_dominio import seed_para_admin
    total = 0
    try:
        admins = Usuario.query.filter(
            Usuario.tipo_usuario.in_([TipoUsuario.ADMIN, TipoUsuario.SUPER_ADMIN])
        ).all()
        for u in admins:
            try:
                total += seed_para_admin(u.id, commit=False)
                db.session.commit()
            except Exception as e_tenant:
                db.session.rollback()
                logger.warning(f"[Migration 295] tenant {u.id} falhou: {e_tenant}")
        logger.info(f"[Migration 295] {total} regras de conta do Domínio semeadas.")
    except Exception as e:
        db.session.rollback()
        logger.error(f"[Migration 295] Falha: {e}", exc_info=True)
        raise
```

Registro:

```python
            (295, "Fase 8 — seed da situação contábil por categoria de fluxo de caixa", _migration_295_seed_regras_dominio),
```

- [ ] **Step 5: Rode e veja passar**

Run: `pytest tests/test_dominio_seed.py -v`
Expected: 8 passed

- [ ] **Step 6: Commit**

```bash
git add services/seed_regras_dominio.py migrations.py tests/test_dominio_seed.py
git commit -m "feat(dominio): seed da situacao contabil por categoria (migration 295)"
```


---

## Task B17: Orquestrador — do razão de caixa ao arquivo

**Files:**
- Create: `services/dominio_export.py`
- Test: `tests/test_dominio_export.py`

> **Decisão D3 em vigor:** lê `FluxoCaixa` direto por `data_movimento`, **não** `FinanceiroService.calcular_fluxo_caixa` (`financeiro_service.py:437`), que mistura previsto com realizado. O índice `idx_fluxo_caixa_admin_data` (`migrations.py:14306`) cobre exatamente essa consulta.

- [ ] **Step 1: Escreva o teste que falha**

Crie `tests/test_dominio_export.py`:

```python
"""Fase 8 — ciclo completo da exportação para o Domínio.

Lê FluxoCaixa direto (decisão D3): calcular_fluxo_caixa
(financeiro_service.py:437) mistura previsto (ContaReceber em aberto,
GestaoCustoPai PENDENTE) com realizado, e previsto não vai para a
contabilidade.
"""
import os
import sys
import uuid
from datetime import date
from decimal import Decimal

import pytest
from werkzeug.security import generate_password_hash

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import main  # noqa: F401
from app import app, db
from models import TipoUsuario, Usuario

pytestmark = pytest.mark.integration

INICIO, FIM = date(2026, 3, 1), date(2026, 3, 31)


@pytest.fixture(autouse=True)
def _config():
    app.config['TESTING'] = True
    if not app.secret_key:
        app.secret_key = 'test-fase8-export'
    yield


def _tenant_completo():
    """Tenant com categorias, regras semeadas, plano de contas do Domínio
    preenchido e um banco amarrado. Devolve (admin_id, banco_id)."""
    from models import BancoEmpresa, CategoriaFluxoCaixa, ContaDominio, RegraContaDominio
    from services.seed_regras_dominio import seed_para_admin

    suf = uuid.uuid4().hex[:8]
    u = Usuario(username=f'ex_{suf}', email=f'ex_{suf}@test.local', nome='Veks Teste',
                password_hash=generate_password_hash('x'),
                tipo_usuario=TipoUsuario.ADMIN, ativo=True, versao_sistema='v2')
    db.session.add(u)
    db.session.flush()
    CategoriaFluxoCaixa.seed_defaults(u.id)
    db.session.flush()
    seed_para_admin(u.id, commit=False)

    contas = {
        '1015': 'Banco Itaú CC', '1120': 'Clientes', '2030': 'Fornecedores',
        '4501': 'Energia Elétrica', '4590': 'Tarifas Bancárias',
        '2140': 'Impostos a Recolher', '4900': 'Despesas Diversas',
        '1900': 'Entradas Diversas', '2900': 'Saídas Diversas',
    }
    por_codigo = {}
    for codigo, nome in contas.items():
        c = ContaDominio(admin_id=u.id, codigo_reduzido=codigo, nome=nome)
        db.session.add(c)
        por_codigo[codigo] = c
    db.session.flush()

    padrao = {
        'PAGAMENTO_FORNECEDOR': '2030', 'RECEBIMENTO_CLIENTE': '1120',
        'DESPESA_DIRETA': '4501', 'TARIFA_BANCARIA': '4590', 'IMPOSTO': '2140',
        'APLICACAO': '4900', 'RESGATE': '4900',
        'ENTRADA_DIVERSA': '1900', 'SAIDA_DIVERSA': '2900',
    }
    for r in RegraContaDominio.query.filter_by(admin_id=u.id).all():
        r.conta_contrapartida_id = por_codigo[padrao[r.situacao]].id

    banco = BancoEmpresa(admin_id=u.id, nome_banco='Itaú CC', agencia='1',
                         conta='1', conta_dominio_id=por_codigo['1015'].id)
    db.session.add(banco)
    db.session.commit()
    return u.id, banco.id


def _lancamento(admin_id, banco_id, nome_categoria, tipo, valor, dia=7, descricao='X'):
    from models import CategoriaFluxoCaixa, FluxoCaixa
    cat = CategoriaFluxoCaixa.query.filter_by(admin_id=admin_id, nome=nome_categoria).first()
    fc = FluxoCaixa(admin_id=admin_id, data_movimento=date(2026, 3, dia),
                    tipo_movimento=tipo, categoria='custo_obra', valor=Decimal(valor),
                    descricao=descricao, banco_id=banco_id,
                    categoria_fluxo_caixa_id=cat.id)
    db.session.add(fc)
    db.session.commit()
    return fc.id


def test_exportacao_gera_uma_linha_por_lancamento():
    from services.dominio_export import exportar
    with app.app_context():
        aid, bid = _tenant_completo()
        _lancamento(aid, bid, 'Luz / Energia Elétrica', 'SAIDA', '980.00',
                    descricao='CEMIG 03/2026')
        r = exportar(aid, INICIO, FIM)
        assert r.erros == []
        assert len(r.linhas) == 1
        assert r.conteudo.count('\r\n') == 1


def test_despesa_debita_a_conta_da_despesa_e_credita_o_banco():
    from services.dominio_export import exportar
    with app.app_context():
        aid, bid = _tenant_completo()
        _lancamento(aid, bid, 'Luz / Energia Elétrica', 'SAIDA', '980.00')
        r = exportar(aid, INICIO, FIM)
        assert (r.linhas[0].conta_debito, r.linhas[0].conta_credito) == ('4501', '1015')


def test_recebimento_debita_o_banco_e_credita_clientes():
    from services.dominio_export import exportar
    with app.app_context():
        aid, bid = _tenant_completo()
        _lancamento(aid, bid, 'Receita de Obras', 'ENTRADA', '50000.00')
        r = exportar(aid, INICIO, FIM)
        assert (r.linhas[0].conta_debito, r.linhas[0].conta_credito) == ('1015', '1120')


def test_lancamento_fora_do_periodo_nao_entra():
    from models import CategoriaFluxoCaixa, FluxoCaixa
    from services.dominio_export import exportar
    with app.app_context():
        aid, bid = _tenant_completo()
        cat = CategoriaFluxoCaixa.query.filter_by(admin_id=aid, nome='Impostos e Taxas').first()
        db.session.add(FluxoCaixa(
            admin_id=aid, data_movimento=date(2026, 4, 2), tipo_movimento='SAIDA',
            categoria='custo_obra', valor=Decimal('10.00'), descricao='Fora',
            banco_id=bid, categoria_fluxo_caixa_id=cat.id))
        _lancamento(aid, bid, 'Impostos e Taxas', 'SAIDA', '10.00')
        db.session.commit()
        r = exportar(aid, INICIO, FIM)
        assert len(r.linhas) == 1


def test_lancamento_de_outro_tenant_nao_vaza():
    from services.dominio_export import exportar
    with app.app_context():
        aid_a, bid_a = _tenant_completo()
        aid_b, bid_b = _tenant_completo()
        _lancamento(aid_a, bid_a, 'Impostos e Taxas', 'SAIDA', '10.00')
        _lancamento(aid_b, bid_b, 'Impostos e Taxas', 'SAIDA', '99.00')
        r = exportar(aid_a, INICIO, FIM)
        assert len(r.linhas) == 1
        assert r.linhas[0].valor == Decimal('10.00')


def test_categoria_sem_conta_vira_pendencia_e_nao_arquivo():
    from models import CategoriaFluxoCaixa, RegraContaDominio
    from services.dominio_export import exportar
    with app.app_context():
        aid, bid = _tenant_completo()
        cat = CategoriaFluxoCaixa.query.filter_by(admin_id=aid, nome='Internet').first()
        regra = RegraContaDominio.query.filter_by(
            admin_id=aid, categoria_fluxo_caixa_id=cat.id).first()
        regra.conta_contrapartida_id = None
        db.session.commit()
        for i in range(9):
            _lancamento(aid, bid, 'Impostos e Taxas', 'SAIDA', '10.00', dia=i + 1)
        _lancamento(aid, bid, 'Internet', 'SAIDA', '300.00', dia=15)

        r = exportar(aid, INICIO, FIM)
        assert len(r.linhas) == 9
        assert len(r.pendencias) == 1
        assert 'contrapartida' in r.pendencias[0].motivo
        assert r.erros == []          # 1 de 10 = 10%, dentro do limite


def test_pendencia_acima_de_20_por_cento_bloqueia_o_arquivo():
    from models import CategoriaFluxoCaixa, RegraContaDominio
    from services.dominio_export import exportar
    with app.app_context():
        aid, bid = _tenant_completo()
        cat = CategoriaFluxoCaixa.query.filter_by(admin_id=aid, nome='Internet').first()
        RegraContaDominio.query.filter_by(
            admin_id=aid, categoria_fluxo_caixa_id=cat.id
        ).first().conta_contrapartida_id = None
        db.session.commit()
        _lancamento(aid, bid, 'Impostos e Taxas', 'SAIDA', '10.00', dia=1)
        _lancamento(aid, bid, 'Internet', 'SAIDA', '300.00', dia=2)

        r = exportar(aid, INICIO, FIM)
        assert any('cobertura' in e for e in r.erros)
        assert r.conteudo == ''


def test_transferencia_sai_como_um_unico_lancamento():
    from models import BancoEmpresa, ContaDominio, FluxoCaixa
    from services.dominio_export import exportar
    with app.app_context():
        aid, bid = _tenant_completo()
        conta2 = ContaDominio(admin_id=aid, codigo_reduzido='1016', nome='Nubank')
        db.session.add(conta2)
        db.session.flush()
        banco2 = BancoEmpresa(admin_id=aid, nome_banco='Nubank', agencia='2',
                              conta='2', conta_dominio_id=conta2.id)
        db.session.add(banco2)
        db.session.flush()
        saida = FluxoCaixa(admin_id=aid, data_movimento=date(2026, 3, 7),
                           tipo_movimento='SAIDA', categoria='transferencia',
                           valor=Decimal('5000.00'), descricao='Transf', banco_id=bid)
        entrada = FluxoCaixa(admin_id=aid, data_movimento=date(2026, 3, 7),
                             tipo_movimento='ENTRADA', categoria='transferencia',
                             valor=Decimal('5000.00'), descricao='Transf', banco_id=banco2.id)
        db.session.add_all([saida, entrada])
        db.session.flush()
        saida.transferencia_par_id = entrada.id
        entrada.transferencia_par_id = saida.id
        db.session.commit()

        r = exportar(aid, INICIO, FIM)
        assert len(r.linhas) == 1
        assert (r.linhas[0].conta_debito, r.linhas[0].conta_credito) == ('1016', '1015')


def test_execucao_fica_registrada_com_hash():
    from models import ExportacaoDominio
    from services.dominio_export import exportar
    with app.app_context():
        aid, bid = _tenant_completo()
        _lancamento(aid, bid, 'Impostos e Taxas', 'SAIDA', '10.00')
        exportar(aid, INICIO, FIM)
        e = ExportacaoDominio.query.filter_by(admin_id=aid).one()
        assert e.status == 'GERADO'
        assert len(e.hash_arquivo) == 64
        assert e.total_linhas == 1


def test_execucao_bloqueada_tambem_fica_registrada_com_as_pendencias():
    from models import CategoriaFluxoCaixa, ExportacaoDominio, RegraContaDominio
    from services.dominio_export import exportar
    with app.app_context():
        aid, bid = _tenant_completo()
        cat = CategoriaFluxoCaixa.query.filter_by(admin_id=aid, nome='Internet').first()
        RegraContaDominio.query.filter_by(
            admin_id=aid, categoria_fluxo_caixa_id=cat.id
        ).first().conta_contrapartida_id = None
        db.session.commit()
        _lancamento(aid, bid, 'Internet', 'SAIDA', '300.00')
        exportar(aid, INICIO, FIM)
        e = ExportacaoDominio.query.filter_by(admin_id=aid).one()
        assert e.status == 'BLOQUEADO'
        assert len(e.pendencias) == 1


def test_lancamento_sem_obra_e_alerta_e_nao_pendencia():
    """Decisão D4: o contrato manda centro de custo em branco
    (docs/integracao-dominio.md:46-47); obra ausente não bloqueia."""
    from models import ExportacaoDominio
    from services.dominio_export import exportar
    with app.app_context():
        aid, bid = _tenant_completo()
        _lancamento(aid, bid, 'Impostos e Taxas', 'SAIDA', '10.00')  # obra_id NULL
        r = exportar(aid, INICIO, FIM)
        assert r.pendencias == []
        assert ExportacaoDominio.query.filter_by(admin_id=aid).one().total_sem_obra == 1


def test_nome_do_arquivo_segue_o_contrato():
    from services.dominio_export import exportar
    with app.app_context():
        aid, bid = _tenant_completo()
        _lancamento(aid, bid, 'Impostos e Taxas', 'SAIDA', '10.00')
        r = exportar(aid, INICIO, FIM)
        # docs/integracao-dominio.md:48
        assert r.nome_arquivo == 'importacao_dominio_veks-teste_2026-03.csv'
```

- [ ] **Step 2: Rode e veja falhar**

Run: `pytest tests/test_dominio_export.py -v`
Expected: `ModuleNotFoundError: No module named 'services.dominio_export'`

- [ ] **Step 3: Implementação mínima**

Crie `services/dominio_export.py`:

```python
"""Ponte ORM → núcleo puro da exportação para o Domínio (Fase 8).

Lê FluxoCaixa direto por data_movimento (decisão D3): calcular_fluxo_caixa
(financeiro_service.py:437) mistura previsto com realizado. O índice
idx_fluxo_caixa_admin_data (migrations.py:14306) cobre esta consulta.
"""
import hashlib
import re
from dataclasses import dataclass, field

from sqlalchemy.orm import joinedload

from models import (BancoEmpresa, ExportacaoDominio, ExportacaoDominioPendencia,
                    FluxoCaixa, RegraContaDominio, Usuario, db)
from services.classificador_cadastro import _norm
from services.dominio_layout import LAYOUT_CONFERIDO, montar_arquivo
from services.dominio_mapeamento import (Movimento, Regra, colapsar_transferencias,
                                         descartar, remover_duplicatas_exatas, resolver)
from services.dominio_validacao import validar


@dataclass
class ResultadoExportacao:
    nome_arquivo: str
    conteudo: str
    linhas: list = field(default_factory=list)
    pendencias: list = field(default_factory=list)
    descartes: list = field(default_factory=list)   # (movimento, motivo)
    erros: list = field(default_factory=list)
    total_movimentos: int = 0
    total_sem_obra: int = 0
    layout_conferido: bool = LAYOUT_CONFERIDO
    exportacao_id: int = None


def _slug(texto) -> str:
    s = _norm(texto)
    s = re.sub(r"[^a-z0-9]+", "-", s).strip("-")
    return s or "empresa"


def _nome_arquivo(admin_id, data_inicio) -> str:
    """importacao_dominio_<empresa>_<periodo>.csv
    (docs/integracao-dominio.md:48)."""
    admin = db.session.get(Usuario, admin_id)
    empresa = _slug(getattr(admin, "nome", None) or getattr(admin, "username", ""))
    return f"importacao_dominio_{empresa}_{data_inicio:%Y-%m}.csv"


def _carregar_regras(admin_id):
    """categoria_fluxo_caixa_id → Regra (value object puro)."""
    regras = {}
    q = RegraContaDominio.query.options(
        joinedload(RegraContaDominio.conta_contrapartida)
    ).filter_by(admin_id=admin_id, ativo=True).all()
    for r in q:
        conta = r.conta_contrapartida
        regras[r.categoria_fluxo_caixa_id] = Regra(
            situacao=r.situacao,
            conta_contrapartida=(conta.codigo_reduzido
                                 if conta is not None and conta.ativo else None),
        )
    return regras


def _carregar_movimentos(admin_id, data_inicio, data_fim):
    linhas = FluxoCaixa.query.options(
        joinedload(FluxoCaixa.banco),
        joinedload(FluxoCaixa.categoria_fluxo_caixa),
        joinedload(FluxoCaixa.fornecedor_ref),
    ).filter(
        FluxoCaixa.admin_id == admin_id,
        FluxoCaixa.data_movimento >= data_inicio,
        FluxoCaixa.data_movimento <= data_fim,
    ).order_by(FluxoCaixa.data_movimento, FluxoCaixa.id).all()

    # conta do Domínio do banco: sai do relationship, evitando uma query por linha
    movimentos, por_fc = [], {}
    for fc in linhas:
        banco = fc.banco
        conta_banco = None
        banco_nome = ""
        if banco is not None:
            banco_nome = banco.nome_banco or ""
            cd = banco.conta_dominio
            conta_banco = cd.codigo_reduzido if cd is not None and cd.ativo else None
        cat = fc.categoria_fluxo_caixa
        forn = fc.fornecedor_ref
        conta_forn = None
        if forn is not None and forn.conta_dominio is not None and forn.conta_dominio.ativo:
            conta_forn = forn.conta_dominio.codigo_reduzido
        mov = Movimento(
            id=fc.id, data=fc.data_movimento, tipo=fc.tipo_movimento,
            valor=fc.valor, descricao=fc.descricao or "",
            categoria_nome=(cat.nome if cat is not None else ""),
            grupo_financeiro=(cat.grupo_financeiro if cat is not None else "") or "",
            conta_banco=conta_banco, banco_nome=banco_nome,
            fornecedor_nome=(forn.nome if forn is not None else ""),
            conta_fornecedor=conta_forn,
            transferencia_par_id=fc.transferencia_par_id,
        )
        movimentos.append(mov)
        por_fc[fc.id] = fc
    return movimentos, por_fc


def _contas_validas(admin_id):
    from models import ContaDominio
    return {c.codigo_reduzido for c in
            ContaDominio.query.filter_by(admin_id=admin_id, ativo=True).all()}


def exportar(admin_id, data_inicio, data_fim, usuario_id=None) -> ResultadoExportacao:
    movimentos, por_fc = _carregar_movimentos(admin_id, data_inicio, data_fim)
    total_movimentos = len(movimentos)
    total_sem_obra = sum(1 for fc in por_fc.values() if fc.obra_id is None)

    # 1. descartes automáticos (docs/integracao-dominio.md:92-93)
    descartes, restantes = [], []
    for mov in movimentos:
        motivo = descartar(mov)
        (descartes.append((mov, motivo)) if motivo else restantes.append(mov))
    unicos, duplicatas = remover_duplicatas_exatas(restantes)
    descartes.extend((m, "duplicata exata") for m in duplicatas)

    # 2. transferências viram UM lançamento (docs:79-83)
    linhas, pendencias, simples = colapsar_transferencias(unicos)

    # 3. o resto passa pelo de/para
    regras = _carregar_regras(admin_id)
    for mov in simples:
        fc = por_fc[mov.id]
        saida = resolver(mov, regras.get(fc.categoria_fluxo_caixa_id))
        (pendencias if hasattr(saida, "motivo") else linhas).append(saida)

    linhas.sort(key=lambda l: (l.data, l.movimento_ids))

    # 4. validações bloqueantes (docs:96-106)
    erros = validar(linhas, pendencias, _contas_validas(admin_id), data_inicio, data_fim)
    conteudo = "" if erros else montar_arquivo(linhas)
    nome = _nome_arquivo(admin_id, data_inicio)

    resultado = ResultadoExportacao(
        nome_arquivo=nome, conteudo=conteudo, linhas=linhas, pendencias=pendencias,
        descartes=descartes, erros=erros, total_movimentos=total_movimentos,
        total_sem_obra=total_sem_obra,
    )
    resultado.exportacao_id = _registrar(resultado, admin_id, data_inicio,
                                         data_fim, usuario_id)
    return resultado


def _registrar(r: ResultadoExportacao, admin_id, data_inicio, data_fim, usuario_id):
    """Trilha da execução (decisão D6). Tentativa bloqueada também é gravada:
    o mês de calibração vive delas (docs/integracao-dominio.md:31-32)."""
    registro = ExportacaoDominio(
        admin_id=admin_id, data_inicio=data_inicio, data_fim=data_fim,
        nome_arquivo=r.nome_arquivo,
        hash_arquivo=hashlib.sha256(r.conteudo.encode("utf-8")).hexdigest(),
        status="BLOQUEADO" if r.erros else "GERADO",
        erros="\n".join(r.erros) or None,
        total_movimentos=r.total_movimentos, total_linhas=len(r.linhas),
        total_pendencias=len(r.pendencias), total_descartes=len(r.descartes),
        total_sem_obra=r.total_sem_obra, layout_conferido=r.layout_conferido,
        usuario_id=usuario_id,
    )
    db.session.add(registro)
    db.session.flush()
    for p in r.pendencias:
        db.session.add(ExportacaoDominioPendencia(
            exportacao_id=registro.id, admin_id=admin_id, fluxo_caixa_id=p.movimento_id,
            data_movimento=p.data, descricao=(p.descricao or "")[:300],
            valor=p.valor, conta=p.conta or None, motivo=p.motivo[:200]))
    db.session.commit()
    return registro.id
```

- [ ] **Step 4: Rode e veja passar**

Run: `pytest tests/test_dominio_export.py -v`
Expected: 12 passed

- [ ] **Step 5: Commit**

```bash
git add services/dominio_export.py tests/test_dominio_export.py
git commit -m "feat(dominio): orquestrador da exportacao a partir do razao de caixa"
```


---

## Task B18: Relatório de pendências (.xlsx) e resumo do processamento (.md)

**Files:**
- Modify: `services/dominio_export.py`
- Test: `tests/test_dominio_relatorios.py`

> Os três artefatos do contrato (`docs/integracao-dominio.md:108-114`): o `.csv`, o relatório de pendências `.xlsx` e o resumo `.md`. `openpyxl` já é usado no repositório (`contabilidade_utils.py:946`, `exportacao_relatorios.py:241`).

- [ ] **Step 1: Escreva o teste que falha**

Crie `tests/test_dominio_relatorios.py`:

```python
"""Fase 8 — os dois artefatos que acompanham o .csv
(docs/integracao-dominio.md:108-114)."""
import io
import os
import sys
from datetime import date
from decimal import Decimal

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from services.dominio_export import ResultadoExportacao, resumo_markdown, xlsx_pendencias
from services.dominio_layout import LinhaDominio
from services.dominio_mapeamento import Pendencia


def _resultado():
    return ResultadoExportacao(
        nome_arquivo='importacao_dominio_veks_2026-03.csv',
        conteudo='linha\r\n',
        linhas=[LinhaDominio(data=date(2026, 3, 7), conta_debito='4501',
                             conta_credito='1015', valor=Decimal('980.00'),
                             complemento='Energia', movimento_ids=(1,))],
        pendencias=[Pendencia(movimento_id=2, data=date(2026, 3, 9),
                              descricao='Internet Vivo', valor=Decimal('300.00'),
                              conta='', motivo='regra sem conta de contrapartida no plano')],
        descartes=[],
        erros=[],
        total_movimentos=2,
        total_sem_obra=1,
    )


def test_xlsx_tem_as_cinco_colunas_do_contrato():
    import openpyxl
    wb = openpyxl.load_workbook(io.BytesIO(xlsx_pendencias(_resultado())))
    ws = wb.active
    # docs/integracao-dominio.md:113 — data, descrição, valor, conta, motivo
    assert [c.value for c in ws[1]] == ['Data', 'Descrição', 'Valor', 'Conta', 'Motivo']


def test_xlsx_traz_uma_linha_por_pendencia():
    import openpyxl
    ws = openpyxl.load_workbook(io.BytesIO(xlsx_pendencias(_resultado()))).active
    assert ws.max_row == 2
    assert ws.cell(row=2, column=2).value == 'Internet Vivo'


def test_xlsx_sem_pendencia_tem_so_o_cabecalho():
    import openpyxl
    r = _resultado()
    r.pendencias = []
    ws = openpyxl.load_workbook(io.BytesIO(xlsx_pendencias(r))).active
    assert ws.max_row == 1


def test_resumo_traz_totais_por_tipo():
    md = resumo_markdown(_resultado())
    assert 'Movimentos lidos | 2' in md
    assert 'Lançamentos gerados | 1' in md
    assert 'Pendências | 1' in md


def test_resumo_traz_debito_e_credito_por_conta():
    # docs/integracao-dominio.md:114
    md = resumo_markdown(_resultado())
    assert '4501' in md and '1015' in md


def test_resumo_avisa_quando_o_layout_nao_foi_conferido():
    """Lacuna 1 do contrato: a ordem das colunas é hipótese até a
    contabilidade entregar o arquivo-modelo."""
    r = _resultado()
    r.layout_conferido = False
    assert 'LAYOUT NÃO CONFERIDO' in resumo_markdown(r)


def test_resumo_conta_lancamentos_sem_obra_como_alerta():
    # decisão D4 — alerta, não pendência
    assert 'sem obra | 1' in resumo_markdown(_resultado())


def test_resumo_de_execucao_bloqueada_lista_os_erros():
    r = _resultado()
    r.erros = ['cobertura insuficiente: 3 de 10 linhas (30.0%)']
    md = resumo_markdown(r)
    assert 'BLOQUEADO' in md
    assert 'cobertura insuficiente' in md
```

- [ ] **Step 2: Rode e veja falhar**

Run: `pytest tests/test_dominio_relatorios.py -v`
Expected: `ImportError: cannot import name 'xlsx_pendencias'`

- [ ] **Step 3: Implementação mínima**

Acrescente a `services/dominio_export.py`:

```python
def xlsx_pendencias(resultado: ResultadoExportacao) -> bytes:
    """Relatório de pendências (docs/integracao-dominio.md:113):
    data, descrição, valor, conta, motivo."""
    import io as _io

    from openpyxl import Workbook
    from openpyxl.styles import Font

    wb = Workbook()
    ws = wb.active
    ws.title = "Pendências"
    ws.append(["Data", "Descrição", "Valor", "Conta", "Motivo"])
    for celula in ws[1]:
        celula.font = Font(bold=True)
    for p in resultado.pendencias:
        ws.append([p.data, p.descricao, float(p.valor or 0), p.conta or "", p.motivo])
    for coluna, largura in zip("ABCDE", (12, 46, 14, 12, 46)):
        ws.column_dimensions[coluna].width = largura
    buffer = _io.BytesIO()
    wb.save(buffer)
    return buffer.getvalue()


def resumo_markdown(resultado: ResultadoExportacao) -> str:
    """Resumo do processamento (docs/integracao-dominio.md:114):
    totais por tipo e débito/crédito por conta."""
    from collections import defaultdict
    from decimal import Decimal as _D

    status = "BLOQUEADO" if resultado.erros else "GERADO"
    partes = [
        f"# Exportação para o Domínio — {resultado.nome_arquivo}",
        "",
        f"**Status:** {status}",
    ]
    if not resultado.layout_conferido:
        partes += [
            "",
            "> ⚠️ **LAYOUT NÃO CONFERIDO.** A ordem das colunas do registro 11758 "
            "ainda não foi validada contra um arquivo aceito pelo Domínio "
            "(lacuna 1 do contrato). Conferir antes de enviar à contabilidade.",
        ]
    if resultado.erros:
        partes += ["", "## Validações que bloquearam a geração", ""]
        partes += [f"- {e}" for e in resultado.erros]

    partes += [
        "", "## Totais", "", "| Indicador | Quantidade |", "|---|---|",
        f"| Movimentos lidos | {resultado.total_movimentos} |",
        f"| Lançamentos gerados | {len(resultado.linhas)} |",
        f"| Pendências | {len(resultado.pendencias)} |",
        f"| Descartes automáticos | {len(resultado.descartes)} |",
        f"| Lançamentos sem obra | {resultado.total_sem_obra} |",
    ]

    debito, credito = defaultdict(lambda: _D("0")), defaultdict(lambda: _D("0"))
    for l in resultado.linhas:
        debito[l.conta_debito] += _D(l.valor)
        credito[l.conta_credito] += _D(l.valor)
    partes += ["", "## Débito e crédito por conta", "",
               "| Conta | Débito | Crédito |", "|---|---:|---:|"]
    for conta in sorted(set(debito) | set(credito)):
        partes.append(f"| {conta} | {debito[conta]:.2f} | {credito[conta]:.2f} |")

    if resultado.pendencias:
        por_motivo = defaultdict(int)
        for p in resultado.pendencias:
            por_motivo[p.motivo] += 1
        partes += ["", "## Pendências por motivo", "", "| Motivo | Linhas |", "|---|---:|"]
        for motivo, n in sorted(por_motivo.items(), key=lambda kv: -kv[1]):
            partes.append(f"| {motivo} | {n} |")

    return "\n".join(partes) + "\n"
```

- [ ] **Step 4: Rode e veja passar**

Run: `pytest tests/test_dominio_relatorios.py -v`
Expected: 8 passed

- [ ] **Step 5: Commit**

```bash
git add services/dominio_export.py tests/test_dominio_relatorios.py
git commit -m "feat(dominio): relatorio de pendencias xlsx e resumo do processamento"
```

---

## Task B19: Blueprint, telas e download

**Files:**
- Create: `dominio_views.py`
- Create: `templates/financeiro/dominio_painel.html`, `templates/financeiro/dominio_depara.html`, `templates/financeiro/dominio_contas.html`
- Modify: `app.py:726-731` (bloco de registro do `financeiro_bp`)
- Test: `tests/test_dominio_views.py`

- [ ] **Step 1: Escreva o teste que falha**

Crie `tests/test_dominio_views.py`:

```python
"""Fase 8 — rotas da exportação para o Domínio.

Login por injeção de sessão, no padrão de tests/test_fase0_autorizacao.py.
"""
import io
import os
import sys
import uuid
from datetime import date
from decimal import Decimal

import pytest
from werkzeug.security import generate_password_hash

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import main  # noqa: F401
from app import app, db
from models import TipoUsuario, Usuario

pytestmark = pytest.mark.integration


@pytest.fixture(autouse=True)
def _config():
    app.config['TESTING'] = True
    app.config['WTF_CSRF_ENABLED'] = False
    if not app.secret_key:
        app.secret_key = 'test-fase8-views'
    yield


def _usuario(tipo=TipoUsuario.ADMIN):
    suf = uuid.uuid4().hex[:8]
    u = Usuario(username=f'vw_{suf}', email=f'vw_{suf}@test.local', nome='Veks',
                password_hash=generate_password_hash('x'),
                tipo_usuario=tipo, ativo=True, versao_sistema='v2')
    db.session.add(u)
    db.session.commit()
    return u.id


def _cliente(user_id):
    c = app.test_client()
    with c.session_transaction() as sess:
        sess['_user_id'] = str(user_id)
        sess['_fresh'] = True
    return c


def test_painel_exige_autenticacao():
    resp = app.test_client().get('/financeiro/dominio/')
    assert resp.status_code in (302, 401)


def test_painel_abre_para_admin():
    with app.app_context():
        c = _cliente(_usuario())
        assert c.get('/financeiro/dominio/').status_code == 200


def test_funcionario_nao_acessa_o_painel():
    with app.app_context():
        c = _cliente(_usuario(TipoUsuario.FUNCIONARIO))
        assert c.get('/financeiro/dominio/').status_code in (302, 403)


def test_upload_do_plano_de_contas_cria_as_contas():
    from models import ContaDominio
    with app.app_context():
        aid = _usuario()
        csv = 'codigo_reduzido;nome;classificacao\n1015;Banco Itaú CC;1.1.01\n2030;Fornecedores;2.1.01\n'
        resp = _cliente(aid).post(
            '/financeiro/dominio/contas/importar',
            data={'arquivo': (io.BytesIO(csv.encode('utf-8')), 'plano.csv')},
            content_type='multipart/form-data', follow_redirects=True)
        assert resp.status_code == 200
        assert ContaDominio.query.filter_by(admin_id=aid).count() == 2


def test_upload_e_idempotente_e_atualiza_o_nome():
    from models import ContaDominio
    with app.app_context():
        aid = _usuario()
        c = _cliente(aid)
        for nome in ('Banco Itaú CC', 'Itaú Conta Movimento'):
            c.post('/financeiro/dominio/contas/importar',
                   data={'arquivo': (io.BytesIO(f'codigo_reduzido;nome\n1015;{nome}\n'.encode()),
                                     'plano.csv')},
                   content_type='multipart/form-data', follow_redirects=True)
        contas = ContaDominio.query.filter_by(admin_id=aid).all()
        assert len(contas) == 1
        assert contas[0].nome == 'Itaú Conta Movimento'


def test_contas_de_outro_tenant_nao_aparecem_no_depara():
    from models import ContaDominio
    with app.app_context():
        a, b = _usuario(), _usuario()
        db.session.add(ContaDominio(admin_id=b, codigo_reduzido='9999',
                                    nome='CONTA-DO-OUTRO-TENANT'))
        db.session.commit()
        html = _cliente(a).get('/financeiro/dominio/de-para').get_data(as_text=True)
        assert 'CONTA-DO-OUTRO-TENANT' not in html


def test_exportar_sem_lancamento_devolve_bloqueio_e_nao_arquivo():
    with app.app_context():
        c = _cliente(_usuario())
        resp = c.post('/financeiro/dominio/exportar',
                      data={'data_inicio': '2026-03-01', 'data_fim': '2026-03-31'},
                      follow_redirects=True)
        assert resp.status_code == 200
        assert 'nenhum lançamento' in resp.get_data(as_text=True)


def test_download_do_csv_de_uma_execucao_gerada():
    from models import ExportacaoDominio
    with app.app_context():
        aid = _usuario()
        e = ExportacaoDominio(admin_id=aid, data_inicio=date(2026, 3, 1),
                              data_fim=date(2026, 3, 31), status='GERADO',
                              nome_arquivo='importacao_dominio_veks_2026-03.csv',
                              hash_arquivo='h', total_linhas=1)
        db.session.add(e)
        db.session.commit()
        resp = _cliente(aid).get(f'/financeiro/dominio/exportacao/{e.id}/csv')
        assert resp.status_code == 200
        assert 'importacao_dominio_veks_2026-03.csv' in resp.headers['Content-Disposition']


def test_download_de_execucao_de_outro_tenant_da_404():
    from models import ExportacaoDominio
    with app.app_context():
        a, b = _usuario(), _usuario()
        e = ExportacaoDominio(admin_id=b, data_inicio=date(2026, 3, 1),
                              data_fim=date(2026, 3, 31), status='GERADO',
                              nome_arquivo='x.csv', hash_arquivo='h')
        db.session.add(e)
        db.session.commit()
        assert _cliente(a).get(f'/financeiro/dominio/exportacao/{e.id}/csv').status_code == 404
```

- [ ] **Step 2: Rode e veja falhar**

Run: `pytest tests/test_dominio_views.py -v`
Expected: 404 em todas as rotas — o blueprint não existe

- [ ] **Step 3: Regenerar o arquivo no download**

O `.csv` **não é guardado em disco nem no banco** — é regerado a partir da execução registrada. Isso mantém o razão como fonte única e evita um segundo lugar onde o arquivo pode divergir.

Em `services/dominio_export.py`, renomeie o corpo atual de `exportar` (tudo entre o `_carregar_movimentos` e o `return resultado`, **exceto** a linha que chama `_registrar`) para `_processar`, e deixe as duas entradas assim:

```python
def _processar(admin_id, data_inicio, data_fim) -> ResultadoExportacao:
    """Pipeline puro-com-ORM: lê, descarta, colapsa, resolve, valida, monta.
    NÃO grava nada."""
    movimentos, por_fc = _carregar_movimentos(admin_id, data_inicio, data_fim)
    total_movimentos = len(movimentos)
    total_sem_obra = sum(1 for fc in por_fc.values() if fc.obra_id is None)

    descartes, restantes = [], []
    for mov in movimentos:
        motivo = descartar(mov)
        (descartes.append((mov, motivo)) if motivo else restantes.append(mov))
    unicos, duplicatas = remover_duplicatas_exatas(restantes)
    descartes.extend((m, "duplicata exata") for m in duplicatas)

    linhas, pendencias, simples = colapsar_transferencias(unicos)

    regras = _carregar_regras(admin_id)
    for mov in simples:
        fc = por_fc[mov.id]
        saida = resolver(mov, regras.get(fc.categoria_fluxo_caixa_id))
        (pendencias if hasattr(saida, "motivo") else linhas).append(saida)

    linhas.sort(key=lambda l: (l.data, l.movimento_ids))

    erros = validar(linhas, pendencias, _contas_validas(admin_id), data_inicio, data_fim)
    return ResultadoExportacao(
        nome_arquivo=_nome_arquivo(admin_id, data_inicio),
        conteudo=("" if erros else montar_arquivo(linhas)),
        linhas=linhas, pendencias=pendencias, descartes=descartes, erros=erros,
        total_movimentos=total_movimentos, total_sem_obra=total_sem_obra,
    )


def exportar(admin_id, data_inicio, data_fim, usuario_id=None) -> ResultadoExportacao:
    """Executa e REGISTRA (decisão D6)."""
    resultado = _processar(admin_id, data_inicio, data_fim)
    resultado.exportacao_id = _registrar(resultado, admin_id, data_inicio,
                                         data_fim, usuario_id)
    return resultado


def reexportar(exportacao_id, admin_id) -> ResultadoExportacao:
    """Regenera os artefatos de uma execução já registrada, sem criar um novo
    registro. O arquivo nunca é persistido: a fonte é o razão de caixa."""
    registro = ExportacaoDominio.query.filter_by(
        id=exportacao_id, admin_id=admin_id).first_or_404()
    resultado = _processar(admin_id, registro.data_inicio, registro.data_fim)
    resultado.exportacao_id = registro.id
    return resultado
```

- [ ] **Step 4: Blueprint**

Crie `dominio_views.py`:

```python
"""Exportação contábil para o Domínio — layout 11758 (Fase 8).

Decisão D6: disparo manual e mensal pelo ADMIN. Cada execução fica
registrada em exportacao_dominio.
"""
import csv
import io
import logging
from datetime import datetime

from flask import (Blueprint, Response, flash, redirect, render_template,
                   request, url_for)
from flask_login import login_required

from auth import admin_required
from models import ContaDominio, ExportacaoDominio, RegraContaDominio, db
from multitenant_helper import get_admin_id
from services.dominio_export import (exportar, reexportar, resumo_markdown,
                                     xlsx_pendencias)
from services.dominio_layout import ENCODING
from services.dominio_mapeamento import LADO_DO_BANCO

logger = logging.getLogger(__name__)

dominio_bp = Blueprint('dominio', __name__, url_prefix='/financeiro/dominio')


def _data(nome, padrao=None):
    bruto = (request.form.get(nome) or request.args.get(nome) or '').strip()
    if not bruto:
        return padrao
    try:
        return datetime.strptime(bruto, '%Y-%m-%d').date()
    except ValueError:
        return padrao


@dominio_bp.route('/')
@login_required
@admin_required
def painel():
    """Histórico de execuções e disparo de uma nova."""
    admin_id = get_admin_id()
    execucoes = ExportacaoDominio.query.filter_by(admin_id=admin_id)\
        .order_by(ExportacaoDominio.created_at.desc()).limit(24).all()
    n_contas = ContaDominio.query.filter_by(admin_id=admin_id, ativo=True).count()
    n_sem_conta = RegraContaDominio.query.filter_by(
        admin_id=admin_id, ativo=True, conta_contrapartida_id=None).count()
    return render_template('financeiro/dominio_painel.html',
                           execucoes=execucoes, n_contas=n_contas,
                           n_sem_conta=n_sem_conta)


@dominio_bp.route('/contas')
@login_required
@admin_required
def contas():
    admin_id = get_admin_id()
    return render_template(
        'financeiro/dominio_contas.html',
        contas=ContaDominio.query.filter_by(admin_id=admin_id)
                                 .order_by(ContaDominio.codigo_reduzido).all())


@dominio_bp.route('/contas/importar', methods=['POST'])
@login_required
@admin_required
def importar_contas():
    """Upload do plano de contas do Domínio (CSV `;`).

    Colunas: codigo_reduzido;nome[;classificacao][;tipo]. Idempotente por
    (admin_id, codigo_reduzido): reimportar atualiza nome e classificação.
    """
    admin_id = get_admin_id()
    arquivo = request.files.get('arquivo')
    if not arquivo:
        flash('Selecione o arquivo do plano de contas.', 'warning')
        return redirect(url_for('dominio.contas'))
    try:
        texto = arquivo.read().decode('utf-8-sig', errors='replace')
        leitor = csv.DictReader(io.StringIO(texto), delimiter=';')
        existentes = {c.codigo_reduzido: c for c in
                      ContaDominio.query.filter_by(admin_id=admin_id).all()}
        criadas = atualizadas = 0
        for linha in leitor:
            codigo = (linha.get('codigo_reduzido') or '').strip()
            nome = (linha.get('nome') or '').strip()
            if not codigo or not nome:
                continue
            conta = existentes.get(codigo)
            if conta is None:
                conta = ContaDominio(admin_id=admin_id, codigo_reduzido=codigo[:20])
                db.session.add(conta)
                existentes[codigo] = conta
                criadas += 1
            else:
                atualizadas += 1
            conta.nome = nome[:200]
            conta.classificacao = (linha.get('classificacao') or '').strip()[:40] or None
            conta.tipo = (linha.get('tipo') or 'CONTA').strip().upper()[:20]
            conta.ativo = True
        db.session.commit()
        flash(f'{criadas} contas criadas, {atualizadas} atualizadas.', 'success')
    except Exception as e:
        db.session.rollback()
        logger.error(f'[DOMINIO] Falha ao importar plano de contas: {e}', exc_info=True)
        flash('Não foi possível ler o arquivo. Confira o separador (;) e o cabeçalho.',
              'danger')
    return redirect(url_for('dominio.contas'))


@dominio_bp.route('/de-para', methods=['GET', 'POST'])
@login_required
@admin_required
def de_para():
    """Edita situação e conta de contrapartida por categoria."""
    admin_id = get_admin_id()
    if request.method == 'POST':
        contas_validas = {c.id for c in
                          ContaDominio.query.filter_by(admin_id=admin_id).all()}
        for regra in RegraContaDominio.query.filter_by(admin_id=admin_id).all():
            situacao = request.form.get(f'situacao_{regra.id}')
            if situacao in LADO_DO_BANCO:
                regra.situacao = situacao
            conta_id = request.form.get(f'conta_{regra.id}', type=int)
            regra.conta_contrapartida_id = conta_id if conta_id in contas_validas else None
        db.session.commit()
        flash('De/para atualizado.', 'success')
        return redirect(url_for('dominio.de_para'))

    regras = RegraContaDominio.query.filter_by(admin_id=admin_id)\
        .order_by(RegraContaDominio.situacao).all()
    return render_template(
        'financeiro/dominio_depara.html', regras=regras,
        situacoes=sorted(LADO_DO_BANCO),
        contas=ContaDominio.query.filter_by(admin_id=admin_id, ativo=True)
                                 .order_by(ContaDominio.codigo_reduzido).all())


@dominio_bp.route('/exportar', methods=['POST'])
@login_required
@admin_required
def executar():
    admin_id = get_admin_id()
    hoje = datetime.utcnow().date()
    inicio = _data('data_inicio', hoje.replace(day=1))
    fim = _data('data_fim', hoje)
    resultado = exportar(admin_id, inicio, fim, usuario_id=admin_id)
    if resultado.erros:
        for erro in resultado.erros[:10]:
            flash(erro, 'danger')
        flash('Exportação bloqueada — corrija o de/para e rode de novo.', 'warning')
    else:
        flash(f'{len(resultado.linhas)} lançamentos gerados, '
              f'{len(resultado.pendencias)} pendências.', 'success')
    return redirect(url_for('dominio.painel'))


def _artefatos(exportacao_id):
    admin_id = get_admin_id()
    return reexportar(exportacao_id, admin_id)


@dominio_bp.route('/exportacao/<int:exportacao_id>/csv')
@login_required
@admin_required
def baixar_csv(exportacao_id):
    resultado = _artefatos(exportacao_id)
    return Response(
        resultado.conteudo.encode(ENCODING, errors='replace'),
        mimetype='text/csv',
        headers={'Content-Disposition':
                 f'attachment; filename="{resultado.nome_arquivo}"'})


@dominio_bp.route('/exportacao/<int:exportacao_id>/pendencias.xlsx')
@login_required
@admin_required
def baixar_pendencias(exportacao_id):
    resultado = _artefatos(exportacao_id)
    nome = resultado.nome_arquivo.replace('.csv', '_pendencias.xlsx')
    return Response(
        xlsx_pendencias(resultado),
        mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
        headers={'Content-Disposition': f'attachment; filename="{nome}"'})


@dominio_bp.route('/exportacao/<int:exportacao_id>/resumo.md')
@login_required
@admin_required
def baixar_resumo(exportacao_id):
    resultado = _artefatos(exportacao_id)
    nome = resultado.nome_arquivo.replace('.csv', '_resumo.md')
    return Response(
        resumo_markdown(resultado), mimetype='text/markdown',
        headers={'Content-Disposition': f'attachment; filename="{nome}"'})
```

- [ ] **Step 5: Registro no `app.py`**

Logo depois do bloco do `financeiro_bp` (`app.py:726-731`), no mesmo padrão de `try/except`:

```python
    # Blueprint exportação Domínio (Fase 8)
    try:
        from dominio_views import dominio_bp
        app.register_blueprint(dominio_bp)
        logging.info("[OK] Blueprint exportacao Dominio registrado")
    except Exception as e:
        logging.error(f"[ERROR] Erro ao registrar blueprint Dominio: {e}", exc_info=True)
```

> **Não mova o bloco para cima da linha 386.** A ordem de import do `app.py` é contrato não declarado (`ESTADO-ATUAL.md:132-135`).

- [ ] **Step 6: Templates**

`templates/financeiro/dominio_painel.html`, `dominio_contas.html` e `dominio_depara.html` estendem `base.html` e seguem o Bootstrap das telas vizinhas (`templates/financeiro/fluxo_caixa.html`, `templates/financeiro/plano_contas.html`). Conteúdo mínimo de cada um:

- **`dominio_painel.html`** — formulário `POST /financeiro/dominio/exportar` com `data_inicio`/`data_fim`; dois avisos (`n_contas == 0` → "importe o plano de contas"; `n_sem_conta > 0` → "N categorias sem conta de contrapartida"); tabela de execuções com período, status, contadores e os três links de download.
- **`dominio_contas.html`** — formulário `multipart/form-data` para `POST /financeiro/dominio/contas/importar` com o cabeçalho esperado documentado na própria tela (`codigo_reduzido;nome;classificacao;tipo`), e tabela das contas do tenant.
- **`dominio_depara.html`** — um `<form method="post">` com uma linha por regra: nome da categoria, `<select name="situacao_{{ regra.id }}">` com as situações, `<select name="conta_{{ regra.id }}">` com as contas do tenant (opção vazia = sem conta). Linhas sem conta destacadas.

- [ ] **Step 7: Rode e veja passar**

Run: `pytest tests/test_dominio_views.py -v`
Expected: 9 passed

- [ ] **Step 8: Commit**

```bash
git add dominio_views.py app.py templates/financeiro/dominio_*.html services/dominio_export.py tests/test_dominio_views.py
git commit -m "feat(dominio): painel, de/para e download dos artefatos"
```

---

## Task B20: Jornada completa e gate

**Files:**
- Create: `tests/test_dominio_jornada.py`
- Test: a suíte inteira

- [ ] **Step 1: Escreva o teste de jornada**

Crie `tests/test_dominio_jornada.py`:

```python
"""Fase 8 — jornada do mês de calibração, ponta a ponta.

Reproduz o que o contrato prevê (docs/integracao-dominio.md:29-32): o
primeiro mês tem volume alto de pendências, a exportação é BLOQUEADA, a
contabilidade preenche o de/para, e a segunda tentativa gera o arquivo.
"""
import os
import sys
import uuid
from datetime import date
from decimal import Decimal

import pytest
from werkzeug.security import generate_password_hash

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import main  # noqa: F401
from app import app, db
from models import TipoUsuario, Usuario

pytestmark = pytest.mark.integration

INICIO, FIM = date(2026, 3, 1), date(2026, 3, 31)


@pytest.fixture(autouse=True)
def _config():
    app.config['TESTING'] = True
    app.config['WTF_CSRF_ENABLED'] = False
    if not app.secret_key:
        app.secret_key = 'test-fase8-jornada'
    yield


def test_calibracao_bloqueia_e_depois_libera():
    from models import (BancoEmpresa, CategoriaFluxoCaixa, ContaDominio,
                        ExportacaoDominio, FluxoCaixa, RegraContaDominio)
    from services.dominio_export import exportar
    from services.seed_regras_dominio import seed_para_admin

    with app.app_context():
        # ── 1. Tenant novo, com categorias e situações semeadas, sem plano ──
        suf = uuid.uuid4().hex[:8]
        u = Usuario(username=f'jn_{suf}', email=f'jn_{suf}@test.local', nome='Veks',
                    password_hash=generate_password_hash('x'),
                    tipo_usuario=TipoUsuario.ADMIN, ativo=True, versao_sistema='v2')
        db.session.add(u)
        db.session.flush()
        CategoriaFluxoCaixa.seed_defaults(u.id)
        db.session.flush()
        seed_para_admin(u.id, commit=False)
        banco = BancoEmpresa(admin_id=u.id, nome_banco='Itaú CC', agencia='1', conta='1')
        db.session.add(banco)
        db.session.flush()

        cat = CategoriaFluxoCaixa.query.filter_by(
            admin_id=u.id, nome='Luz / Energia Elétrica').first()
        for dia in range(1, 6):
            db.session.add(FluxoCaixa(
                admin_id=u.id, data_movimento=date(2026, 3, dia),
                tipo_movimento='SAIDA', categoria='custo_obra',
                valor=Decimal('100.00'), descricao=f'CEMIG {dia}',
                banco_id=banco.id, categoria_fluxo_caixa_id=cat.id))
        db.session.commit()

        # ── 2. Primeira tentativa: sem plano de contas, tudo pendência ──────
        primeira = exportar(u.id, INICIO, FIM)
        assert primeira.conteudo == ''
        assert any('cobertura' in e for e in primeira.erros)
        assert len(primeira.pendencias) == 5
        assert ExportacaoDominio.query.get(primeira.exportacao_id).status == 'BLOQUEADO'

        # ── 3. A contabilidade entrega o plano e o de/para é preenchido ─────
        conta_banco = ContaDominio(admin_id=u.id, codigo_reduzido='1015', nome='Itaú CC')
        conta_desp = ContaDominio(admin_id=u.id, codigo_reduzido='4501', nome='Energia')
        db.session.add_all([conta_banco, conta_desp])
        db.session.flush()
        banco.conta_dominio_id = conta_banco.id
        RegraContaDominio.query.filter_by(
            admin_id=u.id, categoria_fluxo_caixa_id=cat.id
        ).first().conta_contrapartida_id = conta_desp.id
        db.session.commit()

        # ── 4. Segunda tentativa: arquivo sai ───────────────────────────────
        segunda = exportar(u.id, INICIO, FIM)
        assert segunda.erros == []
        assert segunda.pendencias == []
        assert segunda.conteudo.count('\r\n') == 5
        assert all(l.conta_debito == '4501' and l.conta_credito == '1015'
                   for l in segunda.linhas)
        assert ExportacaoDominio.query.get(segunda.exportacao_id).status == 'GERADO'

        # ── 5. As duas tentativas ficam na trilha ───────────────────────────
        assert ExportacaoDominio.query.filter_by(admin_id=u.id).count() == 2


def test_o_arquivo_fecha_em_partidas_dobradas():
    """Σ débitos = Σ créditos no lote inteiro (docs/integracao-dominio.md:100)."""
    from collections import defaultdict
    from models import (BancoEmpresa, CategoriaFluxoCaixa, ContaDominio,
                        FluxoCaixa, RegraContaDominio)
    from services.dominio_export import exportar
    from services.seed_regras_dominio import seed_para_admin

    with app.app_context():
        suf = uuid.uuid4().hex[:8]
        u = Usuario(username=f'pd_{suf}', email=f'pd_{suf}@test.local', nome='Veks',
                    password_hash=generate_password_hash('x'),
                    tipo_usuario=TipoUsuario.ADMIN, ativo=True, versao_sistema='v2')
        db.session.add(u)
        db.session.flush()
        CategoriaFluxoCaixa.seed_defaults(u.id)
        db.session.flush()
        seed_para_admin(u.id, commit=False)

        conta_banco = ContaDominio(admin_id=u.id, codigo_reduzido='1015', nome='Itaú')
        db.session.add(conta_banco)
        db.session.flush()
        banco = BancoEmpresa(admin_id=u.id, nome_banco='Itaú', agencia='1', conta='1',
                             conta_dominio_id=conta_banco.id)
        db.session.add(banco)
        db.session.flush()

        contas = {}
        for i, situacao in enumerate(sorted({r.situacao for r in
                                             RegraContaDominio.query.filter_by(
                                                 admin_id=u.id).all()})):
            c = ContaDominio(admin_id=u.id, codigo_reduzido=f'900{i}', nome=situacao)
            db.session.add(c)
            db.session.flush()
            contas[situacao] = c.id
        for r in RegraContaDominio.query.filter_by(admin_id=u.id).all():
            r.conta_contrapartida_id = contas[r.situacao]

        for i, cat in enumerate(CategoriaFluxoCaixa.query.filter_by(
                admin_id=u.id, ativo=True).limit(20).all()):
            db.session.add(FluxoCaixa(
                admin_id=u.id, data_movimento=date(2026, 3, (i % 28) + 1),
                tipo_movimento=cat.tipo, categoria='custo_obra',
                valor=Decimal('137.31'), descricao=f'Lanc {i}',
                banco_id=banco.id, categoria_fluxo_caixa_id=cat.id))
        db.session.commit()

        r = exportar(u.id, INICIO, FIM)
        assert r.erros == []
        debitos, creditos = defaultdict(Decimal), defaultdict(Decimal)
        for l in r.linhas:
            debitos[l.conta_debito] += Decimal(l.valor)
            creditos[l.conta_credito] += Decimal(l.valor)
        assert sum(debitos.values()) == sum(creditos.values())
```

- [ ] **Step 2: Rode a jornada**

Run: `pytest tests/test_dominio_jornada.py -v`
Expected: 2 passed

- [ ] **Step 3: Rode o gate inteiro**

Run: `bash run_tests.sh --gate`
Expected: nenhuma regressão nos testes que já passavam. Atenção especial a
`tests/test_aprendizado_classificacao.py`, `tests/test_classificador_cadastro.py`,
`tests/test_regressao_classificacao.py`, `tests/test_fluxo_entradas_realizadas.py`,
`tests/test_agregar_fluxo_mensal.py` e `tests/test_painel_financeiro.py` — são os
vizinhos diretos do que esta fase tocou.

- [ ] **Step 4: Confira o lint das migrações**

Run: `python -c "import migrations; nums=[m[0] for m in []]"` — não basta. Rode:

```bash
grep -n "(29[0-9]," migrations.py
```

Expected: exatamente 6 linhas (290 a 295), cada uma dentro de `migrations_to_run`, sem número repetido.

- [ ] **Step 5: Commit**

```bash
git add tests/test_dominio_jornada.py
git commit -m "test(dominio): jornada do mes de calibracao e partidas dobradas"
```


---

# Fecho da fase

## Riscos da Parte B

| Risco | Probabilidade | Mitigação |
|---|---|---|
| **A ordem das colunas está errada** e o Domínio recusa o arquivo | alta enquanto o arquivo-modelo não chegar | tudo isolado em `COLUNAS_11758` (`services/dominio_layout.py`); o resumo `.md` sai com `LAYOUT NÃO CONFERIDO`; o teste `test_ordem_bate_com_arquivo_modelo` trava a resposta assim que o modelo existir. **Trocar a ordem é editar uma tupla e rodar os testes** |
| **Encoding** — a contabilidade abre em UTF-8 e vê acento quebrado | média | `ENCODING` é constante única, usada só em `dominio_views.baixar_csv`; a decisão D8 documenta a escolha e o motivo |
| **O de/para nasce vazio** e 100% vira pendência no primeiro mês | certa, e é o comportamento correto | o contrato prevê (`docs/integracao-dominio.md:31-32`); a validação de cobertura bloqueia o arquivo em vez de entregar lixo; o painel mostra "N categorias sem conta" antes de o usuário tentar |
| **Transferência já importada antes desta fase** continua fora do razão | certa para o histórico | a Task B14 só corrige daqui para a frente. O histórico exige reimportação do período, ou um script de backfill que a Fase 8 **não** escreve — porque casar par no histórico é exatamente a heurística que a decisão D5 recusa |
| **Fornecedor sem conta nominal** cai no genérico e a contabilidade perde o detalhe | média | é o comportamento do contrato (`docs/integracao-dominio.md:69`); a tela de de/para oferece `sugerir_conta_fornecedor` para o preenchimento em lote |
| **`FluxoCaixa` sem banco** (`banco_id` é nullable, `models.py:798`) vira pendência em massa | média — depende de quanto do histórico foi importado sem a coluna BANCO | o motivo da pendência é explícito (`banco sem código reduzido mapeado`); o `.xlsx` deixa claro quantas linhas e de que categoria |
| **A execução grava mesmo quando bloqueia** e polui a tabela | baixa | é intencional: o mês de calibração vive das tentativas bloqueadas, e o painel mostra as 24 mais recentes |

## Critérios de pronto da fase

**Parte B (Domínio) — pronta quando:**

1. `bash run_tests.sh --gate` passa sem regressão, com os 7 arquivos de teste novos verdes (`test_dominio_layout`, `test_dominio_mapeamento`, `test_dominio_validacao`, `test_dominio_schema`, `test_dominio_transferencia`, `test_dominio_seed`, `test_dominio_export`, `test_dominio_relatorios`, `test_dominio_views`, `test_dominio_jornada`).
2. Um mês real de `FluxoCaixa` da Veks é exportado, e o arquivo é **aceito pelo Domínio na importação** — este é o único critério que não roda sozinho e depende da contabilidade.
3. Σ débitos = Σ créditos no arquivo inteiro.
4. As pendências do primeiro mês estão **todas explicadas por motivo** no `.xlsx`, sem nenhuma linha com motivo genérico.
5. Nenhum código de conta aparece no arquivo sem existir em `conta_dominio` do tenant.
6. `ContaDominio` e `RegraContaDominio` de um tenant nunca aparecem para outro (coberto por `test_contas_de_outro_tenant_nao_aparecem_no_depara` e `test_lancamento_de_outro_tenant_nao_vaza`).
7. `COLUNAS_11758` foi conferida contra `tests/fixtures/dominio/modelo_11758.csv` e `LAYOUT_CONFERIDO = True`.

**Parte A — pronta quando:** cada tarefa cumpre o seu próprio critério, listado junto dela. A fase só fecha quando A1 e A2 estiverem verdes, porque são as que sustentam qualquer número contábil por obra.

## O que esta fase deliberadamente NÃO faz

| Item | Por quê |
|---|---|
| **Importação de retorno do Domínio** (conciliar o que a contabilidade aceitou) | `docs/integracao-dominio.md:147-148` diz explicitamente que o escopo é exportação apenas. Não há spec |
| **Backfill do par de transferência no histórico** | casar par histórico por `(valor, data)` é a heurística que a decisão D5 recusa. O caminho correto é reimportar o período |
| **Medição com assinatura do cliente (regra 5.6)** | `DEVOLUTIVA.md:259` lista isso na Fase 8, mas é assinatura no portal — pertence à Fase 9a, com o mesmo mecanismo da ciência de RDO |
| **SPED contábil** | `SpedContabil` (`models.py:2678`) continua uma tela vazia. É outro layout, outro contrato, e ninguém pediu |
| **Reescrever `MAPEAMENTO_CONTABIL`** (`contabilidade_utils.py:1448`) | a contabilidade interna e a exportação para o Domínio são coisas diferentes (D1). Unificar planos internos é a tarefa A1, não a Parte B |
| **Job agendado de exportação** | decisão D6 — o mês de calibração exige revisão humana |

## Rollback

**Parte B é reversível sem perda.** Nada do que ela cria altera dado existente, com uma exceção declarada.

| Migration | Reversão |
|---|---|
| 290, 291, 294 | `DROP TABLE` — tabelas novas, sem dado de negócio anterior |
| 292 | `ALTER TABLE ... DROP COLUMN conta_dominio_id` em `banco_empresa` e `fornecedor` — colunas novas, nullable |
| 293 | `ALTER TABLE fluxo_caixa DROP COLUMN transferencia_par_id`. **Atenção:** as linhas de `FluxoCaixa` de transferência criadas pela Task B14 continuam no razão. Removê-las é `DELETE FROM fluxo_caixa WHERE categoria = 'transferencia' AND import_batch_id = ...`, por lote |
| 295 | `DELETE FROM regra_conta_dominio WHERE admin_id = ...` — mas isso apaga também o de/para que a contabilidade preencheu. Preferir desativar (`ativo = FALSE`) |

Desregistrar o blueprint (`app.py`) tira as rotas sem tocar em schema. `run_migration_safe` (`migrations.py:146`) grava `failed` e **não** propaga a exceção (`:198`) — uma migration que falha não derruba o boot, mas também não desfaz o que já rodou dentro dela; por isso cada uma está numa transação só (`with db.engine.begin()`).

## Autorrevisão feita sobre este plano

Conferido com o spec (`docs/integracao-dominio.md`) na mão, seção por seção:

| Seção do contrato | Onde está coberta |
|---|---|
| Formato do arquivo (`:34-48`) | Tasks B1, B3 — separador, decimal, data, código de histórico, complemento, inicia lote, filial, centros de custo, nome do arquivo |
| Templates de histórico (`:50-58`) | Task B2, com a decisão D8 para o `→` |
| Partida e contrapartida (`:60-75`) | Tasks B4 (as 7 situações), B8 (transferência), mais 2 genéricas para o que a tabela não cobre (lacuna 11) |
| Regra 1 — dedup de transferência (`:79-83`) | Tasks B8 e B14 |
| Regra 2 — não duplicar receita/compra (`:84-86`) | decisão D2 + as situações `RECEBIMENTO_CLIENTE`/`PAGAMENTO_FORNECEDOR`, que dão baixa em vez de lançar |
| Regra 3 — fornecedor específico (`:87-89`) | Task B6, com a decisão D7 movendo o matching para sugestão |
| Regra 4 — nunca inventar conta (`:90-91`) | Task B5 (`MOTIVO_SEM_CONTRAPARTIDA`), Task B10 (validação 2) |
| Regra 5 — descartes (`:92-93`) | Tasks B7 e B9 |
| Validações bloqueantes (`:96-106`) | Task B10, as 6 |
| Saídas (`:108-114`) | Tasks B17 (csv) e B18 (xlsx e md) |
| Específico da Veks — 2 tabelas de de/para como dados (`:116-124`) | Tasks B11 (`conta_dominio`) e B12 (`regra_conta_dominio`), editáveis em B19 |
| Pontos de encaixe (`:126-141`) | todos usados, **menos** `calcular_fluxo_caixa` — ver correção 1 no contexto |
| Lacunas conhecidas (`:143-150`) | plano de contas → D1; retorno do Domínio → fora de escopo, declarado; quem dispara → D6 |

**Varredura de placeholder:** o único `...` do plano estava no esboço de `reexportar` na Task B19 e foi substituído pelo código completo de `_processar`/`exportar`/`reexportar`. Não há "TBD", "similar à Task N" nem passo de código sem bloco de código.

**Consistência de tipos entre tarefas:** `LinhaDominio` (B3) é a mesma que B5, B8, B10, B17 e B18 consomem, com os campos `data`, `conta_debito`, `conta_credito`, `valor`, `complemento`, `movimento_ids`. `Pendencia` (B5) tem `movimento_id`, `data`, `descricao`, `valor`, `conta`, `motivo` — os mesmos cinco campos do `.xlsx` (B18) mais o id de rastreio, e os mesmos que `ExportacaoDominioPendencia` grava (B15). `Movimento` (B5) tem exatamente os campos que `_carregar_movimentos` (B17) preenche. `LADO_DO_BANCO` (B4) é a mesma fonte que o seed (B16) e o `<select>` da tela (B19) consultam.

**Cobertura de escopo da Parte A:** conciliação → A5; competência × caixa → A3; DRE por obra → A2; farol e projeção → A6. O que a investigação achou de quebrado e que o escopo original não previa (buracos C, D, E) virou A1, declarado como pré-requisito de A2.

---

## Encerramento

Ao terminar as Tasks B1–B20:

```bash
bash run_tests.sh --gate
git log --oneline -20
```

E anote em `ESTADO-ATUAL.md` que a Fase 8 **Parte B** está concluída, que a Parte A depende das Fases 1/3/4/6, e que o item aberto do lado humano é **o arquivo-modelo do Domínio e o plano de contas da Veks** — sem eles, `LAYOUT_CONFERIDO` continua `False` e o de/para continua vazio.
