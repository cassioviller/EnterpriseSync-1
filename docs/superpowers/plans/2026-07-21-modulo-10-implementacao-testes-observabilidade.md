# Módulo 10 — Testes, Observabilidade e Implantação — Implementation Plan

> Fonte: spec `2026-07-17-modulo-10-testes-observabilidade-rollout.md`. Em
> conflito, este plano vence (reconcilia com o modelo vivo pós-M09, medido
> 2026-07-21). Último módulo do plano mestre
> `2026-07-17-cronograma-mpp-rdo-master-plan.md`.

**Goal:** fechar a malha de verificação e operação da nova arquitetura —
flag por tenant real (hoje é proxy do V2), testes que provam os critérios
globais ainda não travados (isolamento entre obras/tenants e permissões),
métricas por importação completas e legíveis no suporte, e o mapa dos 18
critérios globais para arquivo/teste. A execução das fases 0-3 do rollout
é operacional (homolog/produção) — fora deste ambiente, como no M09.

## Fatos do modelo vivo (medidos 2026-07-21 — NÃO re-descobrir)

- **A flag já existe e já está ligada na borda**: `utils/tenant.py:117
  cronograma_mpp_ativo()` hoje é `return is_v2_active()`, com context
  processor em `app.py:287` (`inject_cronograma_mpp_flag`) e consumo em
  `templates/obras/detalhes_obra_profissional.html:2134` +
  `templates/obras/cronograma_importacoes/_secao.html`. O M10 **endurece o
  helper**, não cria a fiação. Serviços não consultam flag (controle na
  borda) — manter assim.
- **Numeração de migration: a spec diz 204, que já está tomada**
  (`_migration_204_gestao_custo_pai_categoria_fc`). A série do cronograma é
  207-210; o próximo livre é **211**. Registro na lista de
  `migrations.py:4010` (tupla `(número, descrição, função)`).
- `ConfiguracaoEmpresa` (`models.py:3588`) é por `admin_id` e **pode não
  existir** para um tenant (`configuracoes_views.py:25` usa `.first()`, sem
  criação implícita). Linha ausente ⇒ flag `False`.
- **Marcador `java` JÁ registrado** em `tests/conftest.py:64` (M03), com
  skip automático via `services.mpp_parser.java_disponivel()`. Falta só o
  atalho `--java` em `run_tests.sh` (parsing de flags em `run_tests.sh:33`).
  `--gate` é `-m "not browser"` e **inclui** a família java (que pula
  sozinha sem JVM) — não mudar isso: retirar java do gate perderia
  cobertura no ambiente que tem JVM.
- **Métricas: parcialmente prontas.** Já persistidas em
  `cronograma_importacao_evento.detalhes`: `tamanho`/`sha256` (upload),
  `tempo_parse_ms` + campos do parse (`views/cronograma_importacao.py:261`),
  contadores da normalização incl. `n_avisos`
  (`services/cronograma_normalizacao.py:379`), `resumo`+`pendencias` da
  reconciliação (`:353`), eventos de aplicação/restauração
  (`services/cronograma_versao_service.py:396/586/781`). **Faltam:**
  `matches_por_nivel`, `n_auto`, `n_manuais`, `n_conflitos`,
  `tempo_total_ms`, `rollbacks`, e logger estruturado `cronograma.importacao`.
- **Tenant/permissão: implementado, não provado.** `cronograma_import_required`
  (`decorators.py`, commit a5fc8ad) cobre as 10 rotas de
  `views/cronograma_importacao.py`; todas resolvem `get_tenant_admin_id()` e
  filtram obra/importação por `admin_id` (`:114`, `:308-314`, `:447`).
  `tests/test_cronograma_import_decorator.py` (87 linhas) cobre
  anônimo/admin/funcionário e trava os bypasses legados. **Não existem**
  `test_cronograma_multitenancy.py` nem `test_cronograma_permissoes.py` —
  são os arquivos que faltam da matriz §4.2; espera-se que passem de
  primeira (se falharem, é bug real, não teste a ajustar).
- `verificar_consistencia_progresso(obra_id, admin_id)` existe em
  `utils/cronograma_engine.py:775` (M06) mas **sem CLI**.
- **Dupla escrita legada do M07** (`services/cronograma_apontamento_service.py`)
  segue ativa por desenho (§13 do M07: reversibilidade). A remoção é da
  fase 3, pós-estabilidade — dívida registrada, não executada aqui.

## Task 1: flag por tenant real (migração 211 + helper + CLI)

- Migração `_migration_211_configuracao_empresa_cronograma_mpp` (aditiva,
  padrão do M02): `configuracao_empresa.cronograma_mpp_ativo BOOLEAN NOT
  NULL DEFAULT FALSE`; coluna em `models.py::ConfiguracaoEmpresa`.
- `utils/tenant.cronograma_mpp_ativo()` passa a ser
  `is_v2_active() and <linha de ConfiguracaoEmpresa do tenant>.cronograma_mpp_ativo`,
  com `False` seguro quando não há linha, não há admin_id ou a query falha
  (o helper nunca levanta — é lido em context processor).
- `scripts/flag_cronograma_mpp.py <admin_id> --ligar|--desligar|--status`
  (cria a linha de configuração se faltar, com os campos obrigatórios
  mínimos) — é como as fases 1-3 do rollout ligam a flag sem UI nova.
- **Consequência a tratar no mesmo commit:** default FALSE esconde a área
  do M08 de quem hoje a vê. Os testes que dependem da seção
  (`tests/test_cronograma_interface_obra.py`,
  `tests/test_cronograma_importacao_obra_playwright.py`) ligam a flag no
  setup. Endpoints **não** passam a exigir flag (a spec restringe a flag à
  borda visual; a jornada por API segue viva para os testes e para o
  suporte).
- Testes (novo `tests/test_flag_cronograma_mpp.py`): sem linha ⇒ False;
  linha com FALSE ⇒ False; TRUE + V2 ⇒ True; TRUE sem V2 ⇒ False;
  idempotência da 211; CLI liga/desliga.
Commit: `feat(cronograma): flag cronograma_mpp_ativo por tenant com migração 211 (M10)`.

## Task 2: infra de teste — `--java` no runner

`run_tests.sh` ganha `--java` (`TARGET_FILE="tests/"; MARKER_ARGS=(-m java)`),
documentado no cabeçalho junto de `--gate`/`--suite`. `--gate` fica como
está (java pula sozinha sem JVM — spec §14). Conferir a matriz §4.2 contra
os arquivos reais e registrar o mapa no fecho (Task 5).
Commit: `test(cronograma): atalho --java no runner e matriz de testes conferida (M10)`.

## Task 3: isolamento entre obras/tenants e permissões

- `tests/test_cronograma_multitenancy.py` (critério global 1): dois tenants
  × duas obras, cada uma com sua importação/versão; provar que reconciliar,
  aplicar e restaurar em A não altera contagens/percentuais de B; que a
  lista de importações/versões de cada obra só enxerga as suas; e que
  `GET/POST` com `obra_id` do outro tenant devolve 404 (não 200 nem 500).
- `tests/test_cronograma_permissoes.py` (§15): tabela das 10 rotas de
  `views/cronograma_importacao.py` × {anônimo, funcionário, admin de outro
  tenant} ⇒ {401, 403, 404}, incluindo `mapeamento_id` de outra importação.
- Se alguma rota escapar da tabela, corrigir a rota (não o teste) no mesmo
  commit e registrar no fecho.
Commit: `test(cronograma): isolamento multitenant e permissões das rotas de importação (M10)`.

## Task 4: métricas completas + logs estruturados + CLI de consistência

- Fechar o conjunto de `detalhes` da spec §4.3 nos eventos já existentes:
  reconciliação passa a gravar `matches_por_nivel` (uid/wbs/caminho/nome/
  fingerprint/score), `n_auto`, `n_manuais`, `n_conflitos`; aplicação grava
  `tempo_total_ms` (do upload ao aplicado) e `rollbacks` (restaurações
  ligadas à importação). Aditivo: nenhuma chave existente muda de nome —
  os testes de `test_upload_cronograma.py` e `test_cronograma_normalizacao.py`
  seguem verdes sem edição.
- Logger `cronograma.importacao` em cada transição de status, sempre com
  `importacao_id` e `obra_id`; erro com `exc_info`.
- Exibir as métricas na seção de importações do M08 (a lista já existe;
  acrescentar tempo, contagens e níveis de matching na linha expandida).
- `scripts/verificar_consistencia_progresso.py <obra_id> <admin_id>`
  envolvendo o helper do M06 (ferramenta de suporte da spec §4.3), no mesmo
  formato de saída do `verificar_equivalencia_obra.py` (M09).
- Testes: novo `tests/test_cronograma_metricas.py` — jornada mínima
  (upload → reconciliar → aplicar) e assert das chaves nos eventos; CLI
  devolve exit code 0/1 conforme consistência.
Commit: `feat(cronograma): métricas por importação, logs estruturados e CLI de consistência (M10)`.

## Task 5: mapa dos 18 critérios, dívidas e fecho §22

- Documento de fecho `2026-07-21-modulo-10-fecho.md` com a **tabela dos 18
  critérios globais → arquivo/teste que os prova** (ou "checklist de fase",
  para os que só a operação fecha: 16 e 17 dependem da janela de
  estabilidade do M09).
- Dívidas registradas explicitamente (spec §22): remoção da dupla escrita
  legada do M07, inventário de descontinuação do M09 §4.3, consolidação dos
  entrypoints Docker divergentes, bypasses legados de `decorators.py`.
- Procedimento de rollout (fases 0-3, com gate e reversão por fase) escrito
  como runbook operacional — incluindo o gate manual pós-deploy de conferir
  `migration_history` 207-211 em `success` (o entrypoint pode engolir falha
  de migration).
- Gate: `./run_tests.sh --gate` e `--java` verdes.
Commit: `docs(cronograma): fecho do M10 — critérios globais mapeados e runbook de rollout`.

## Critérios de aceite (spec §18, escopo executável)

1. Flag por tenant operante (migração 211 + helper + CLI), default FALSE,
   sem quebrar a área do M08 nos testes.
2. Matriz §4.2 completa: os dois arquivos que faltavam existem e passam;
   `--gate` e `--java` verdes.
3. Métricas da §4.3 persistidas por importação e visíveis na seção do M08.
4. Os 18 critérios globais mapeados para teste ou checklist de fase.
5. Suíte existente intacta (nenhum teste de módulo anterior editado, exceto
   o setup de flag da Task 1).

## Fora de escopo

Execução das fases 0-3 em homologação/produção (operacional, como no M09);
remoção da dupla escrita do M07 e a descontinuação física do M09 §4.3
(pós-estabilidade); CI/CD novo; APM externo; consolidação dos entrypoints
Docker (dívida registrada, não executada).
