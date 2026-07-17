# Módulo 10 — Testes, Observabilidade e Implantação

> Parte do plano mestre `2026-07-17-cronograma-mpp-rdo-master-plan.md`. Transversal: cada módulo entrega seus testes; este módulo consolida a malha E2E, métricas, flag e rollout.

## 1. Objetivo

Garantir que a nova arquitetura entre em produção com cobertura completa (unit → integração → E2E), métricas/logs de operação, feature flag por tenant e rollout faseado começando por obra de teste — sem regressão no fluxo das baias.

## 2. Estado atual encontrado no código

- Suíte: pytest com marcadores `smoke|integration|browser` registrados em `tests/conftest.py::pytest_configure`; `run_tests.sh` (`--gate` = `pytest tests/ -m "not browser"`; `--suite`, `--bloco1..7`, `--jornada`); testes de integração contra o app real + **PostgreSQL real** (`from app import app, db`; sem sqlite); Playwright para browser (Chromium headless, exige servidor em `:5000`).
- 46 testes travam o import das baias (`tests/test_importacao_fisico_financeiro.py`); funções puras da engine físico-financeira em `tests/test_cronograma_fisico_financeiro.py`; RDO/cronograma em ~12 arquivos (`test_rdo_ciclo_completo.py`, `test_cronograma_duplicado_rdo.py`, etc.).
- Sem CI descrito no repo; execução via `run_tests.sh` manual.
- Flags: só `Usuario.versao_sistema=='v2'` (`utils/tenant.py:is_v2_active:63-90`, context processor `app.py:275`); migrations gated por env var como precedente (`migrations.py:926`).
- Deploy: EasyPanel/Docker, migrations no startup (`pre_start.py`; timeout 300s; falha pode ser ignorada se `ENABLE_ROLLBACK` desligado); múltiplos entrypoints divergentes (só `docker-entrypoint-easypanel-auto.sh` roda migrations).
- Observabilidade: logs ad-hoc; sem métricas estruturadas.

## 3. Problemas atuais

Sem flag por funcionalidade; sem métricas de importação; testes que exigirão Java não têm marcador/infra; nenhum plano de rollout formal.

## 4. Escopo

### 4.1 Feature flag

- Nova coluna não é necessária: flag por tenant via `ConfiguracaoEmpresa` (padrão existente por `admin_id`) — campo `cronograma_mpp_ativo BOOLEAN DEFAULT FALSE` (migração 204, mesma disciplina do M2). Helper `utils/tenant.py::cronograma_mpp_ativo(admin_id)` + context processor (padrão `inject_v2_flag`, `app.py:275`). Consumida por M7 (dupla escrita) e M8 (UI).

### 4.2 Matriz de testes consolidada (novos além dos módulos)

| Família | Cobre | Arquivo |
|---|---|---|
| Migrations | 200-204 idempotentes, backfill, reexecução | `tests/test_migrations_cronograma_versionamento.py` (M2) |
| Parser | campos, corrompido, timeout, paridade fixture real (marcador `java`) | `tests/test_mpp_parser.py` (M3) |
| Schema/normalização | schemas, determinismo, avisos | `tests/test_cronograma_normalizacao.py` (M4) |
| Reconciliação | cascata, split/merge, ambiguidade nunca auto | `tests/test_cronograma_reconciliacao.py` (M5) |
| Aplicação/rollback | transacional, preservação RDO/fotos, round-trip, concorrência (duas sessões → lock) | `tests/test_cronograma_versao_service.py` (M5) |
| Idempotência | hash duplicado 409; arquivo corrigido casa por uid | M3/M5 |
| Motor | tabela normativa, replanejamento, igualdade 5 fontes | `tests/test_cronograma_engine_unificado.py`, `tests/test_replanejamento.py` (M6) |
| RDO | modos, retrocesso, retroativo em cadeia, snapshots | `tests/test_rdo_modos_apontamento.py`, `tests/test_rdo_recomputo_cadeia.py` (M7) |
| Portal | percentuais consistentes pós-versão | extensão de `test_portal_*` (M6/M7) |
| Isolamento tenants/obras | duas obras, dois tenants, cronogramas independentes (critério global 1) | `tests/test_cronograma_multitenancy.py` (novo) |
| Permissões | rotas novas exigem auth real (não bypass) | `tests/test_cronograma_permissoes.py` (novo) |
| Baias | equivalência + migração + fluxo antigo intacto | `tests/test_migracao_baias_equivalencia.py` (M9) + 46 existentes |
| E2E Playwright | jornada completa importar→prévia→aplicar→RDO→portal | `tests/test_cronograma_importacao_playwright.py` (M8) |

Infra de teste: marcador novo `java` registrado no `conftest.py` (skip automático se `not java_disponivel()`); `run_tests.sh` ganha `--java` (roda a família com JVM); fixture `.mpp` sintética pequena + os `.mpp` reais como integração.

### 4.3 Observabilidade

- Métricas persistidas por importação (em `cronograma_importacao_evento.detalhes`, sem dependência nova): `tempo_parse_ms`, `n_tarefas`, `n_avisos`, `matches_por_nivel` (uid/wbs/caminho/nome/fingerprint/score), `n_auto`, `n_manuais`, `n_conflitos`, `tempo_total_ms`, `rollbacks`. (Campos de "tempo de API/tokens/custo" da spec original não se aplicam — sem API externa.)
- Logs estruturados (logger `cronograma.importacao`) em cada transição de status; erro sempre com `importacao_id`.
- Consulta de suporte: view de admin simples (rota já no M8 — lista de importações com métricas) + `scripts/verificar_equivalencia_obra.py` (M9) como ferramenta de diagnóstico.
- `verificar_consistencia_progresso` (M6) executável via CLI para suporte.

### 4.4 Rollout

- Fase 0 — schema: deploy M2 (migrations 200-204) + Docker com Java (M3). Gate: startup <300s com backfill em lotes; smoke `java -version` no entrypoint (aviso, não bloqueio).
- Fase 1 — obra de teste: flag ligada só no tenant de homologação; importar `.mpp` real; medir métricas §4.3; rodar Playwright contra homologação. Gate: jornada completa + zero drift de progresso.
- Fase 2 — baias: procedimento M9 (homolog → prod com backup). Gate: equivalência automatizada.
- Fase 3 — geral: flag default para novos tenants; documentação de usuário; agendar remoção da dupla escrita legada (M7 §13) e inventário M9 §4.3.
- Reversão por fase: desligar flag (1-3, sem perda de dados); restaurar versão (importações aplicadas); migrations aditivas não exigem down.

## 5. Fora de escopo

CI/CD novo (mantém `run_tests.sh`); APM externo; consolidação dos entrypoints Docker divergentes (recomendação registrada como dívida, não executada aqui).

## 6. Arquivos atuais envolvidos

`tests/conftest.py`, `run_tests.sh`, `utils/tenant.py`, `app.py` (context processor), `models.py`/`migrations.py` (flag 204), `docker-entrypoint-easypanel-auto.sh` (smoke java), `Dockerfile`.

## 7. Arquivos novos ou alterados previstos

Novos: testes §4.2 (`test_cronograma_multitenancy.py`, `test_cronograma_permissoes.py`, Playwright), helper de flag. Alterados: os do §6.

## 8. Alterações de banco

Migração 204 (`configuracao_empresa.cronograma_mpp_ativo`), padrão M2.

## 9. Serviços e responsabilidades

Flag lida só por views/templates; serviços não consultam flag (comportamento controlado na borda — serviços sempre funcionam quando chamados).

## 10. Rotas e contratos de API

Nenhuma nova além das já planejadas (M8 lista importações com métricas).

## 11. Fluxo de frontend

Flag esconde/mostra a seção (M8); nenhum outro efeito.

## 12. Regras de negócio

Flag desligada ⇒ sistema comporta-se exatamente como hoje (dupla escrita legada garante reversibilidade do M7).

## 13. Estratégia de migração

Fases §4.4; cada fase com gate objetivo e reversão descrita.

## 14. Compatibilidade

`--gate` continua rodando sem Java (skips); pipeline das baias verde em todas as fases.

## 15. Segurança

Testes de permissão cobrem as rotas novas com usuário anônimo/tenant errado (hoje o bypass de `decorators.py` mascara isso — as rotas novas usam o decorator real do M1).

## 16. Observabilidade

§4.3 (é o próprio escopo).

## 17. Testes

§4.2 (é o próprio escopo). Meta: nenhuma linha de fórmula/matching sem teste unitário; jornada E2E verde em homologação antes de cada fase.

## 18. Critérios de aceite

1. Matriz §4.2 completa e verde (`--gate`, `--java`, `--suite`).
2. Métricas visíveis por importação.
3. Fases 0-2 executadas com gates cumpridos.
4. Todos os 18 critérios globais do master plan verificados por teste ou checklist de fase.

## 19. Riscos

- Backfill + migrations no startup estourarem 300s → lotes (M2) + ensaio em homolog com dump de produção.
- Falha de migration silenciosamente ignorada (comportamento atual do entrypoint) → gate manual pós-deploy: conferir `migration_history` 200-204 `success`.
- Playwright em homolog instável → jornada mínima estável + retries do runner existente.

## 20. Dependências

Todos os módulos anteriores.

## 21. Ordem detalhada de implementação

1. Flag (migração 204 + helper + testes). 2. Marcador `java` + `--java` no runner. 3. Testes multitenancy/permissões. 4. Métricas nos serviços (M3-M6 emitem; aqui padroniza). 5. Playwright E2E. 6. Fase 0 → 1 → 2 → 3 com gates. Commits por passo.

## 22. Checklist de conclusão

- [ ] Flag por tenant operante
- [ ] Matriz de testes completa e verde
- [ ] Métricas por importação persistidas e visíveis
- [ ] Rollout fases 0-2 concluídas com gates
- [ ] Critérios globais 1-18 todos verificados
- [ ] Dívidas registradas (entrypoints, remoção dupla escrita, bypass decorators)
