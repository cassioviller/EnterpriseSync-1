# Módulo 09 — Migração do Fluxo das Baias — Implementation Plan

> Fonte: spec `2026-07-17-modulo-09-migracao-baias.md`. Em conflito, este plano
> vence (reconcilia com o modelo vivo pós-M08, medido 2026-07-21).

**Goal:** transformar a atualização de cronograma da obra-piloto num caso de uso
normal do pipeline M03-M08, com verificação de equivalência automatizada e
rollback ensaiado; o importador físico-financeiro vira formalmente "criação
inicial" (registra versão nº1) e recusa atropelar obra já versionada pelo fluxo
novo. A descontinuação física dos scripts (§4.3 da spec) fica DEPOIS do período
de estabilidade em produção — fora do que dá para executar aqui.

## Fatos do modelo vivo (medidos 2026-07-21 — NÃO re-descobrir)

- **Java disponível** (`services.mpp_parser.java_disponivel()` → True via
  JAVA_HOME/nix; `which java` vazio — usar sempre o helper). `CRONOGRAMA
  06.07.mpp` (497 KB) e a fixture canônica + symlink existem.
- `importar_fisico_financeiro` (`services/importacao_fisico_financeiro.py:754`)
  é destrutivo-idempotente: `_limpar_derivados` zera comercial+físico e recria
  (inclusive RDOs). `_materializar_cronograma_mpp` (:182) força
  `duracao_dias=max(1, dias||1)` — o pipeline novo NÃO força (marco fica com
  duração 0 e, pós-M06, peso 0 no agregado). **Divergência esperada no
  progresso geral entre antes/depois** quando o `.mpp` tem marcos; a
  equivalência compara % POR TAREFA (tolerância 0.01) e exige apenas
  consistência entre as fontes no "depois" — desvio documentado da leitura
  mais estrita do §4.1.3.
- 46 testes travam o importador (`test_importacao_fisico_financeiro.py`) —
  asserts NOVOS só em arquivo novo; os existentes não mudam.
- Reuso: `_snapshot_versao` e `restaurar_versao` (M05) já fazem foto/rollback;
  M08 fornece a UI/endpoints da jornada de reconciliação.
- Rota do hub: `/importacao/fisico-financeiro` (achar handler exato na Task 2).
- Backfill 210 (não "203" como diz a spec) criou versão nº1 para obras com
  tarefas EXISTENTES à época — obra criada pelo importador HOJE não ganha
  versão: é o gap que a Task 2 fecha.

## Task 1: verificador de equivalência — `scripts/verificar_equivalencia_obra.py`

Módulo importável + CLI (`python scripts/verificar_equivalencia_obra.py
<obra_id> <admin_id> [--salvar out.json] [--comparar out.json]`):
- `capturar_estado(obra_id, admin_id) -> dict`: n_tarefas_ativas, RDOs
  (datas), contagens de apontamentos/fotos/mão de obra, `percentual_concluido`
  por tarefa (id→pct), progresso geral (v2 hoje + KPI + curva com arquivadas +
  raiz do rollup — as fontes do M06), medições (contagem+soma), custos
  (contagem). Sem nada específico de baia (genérico por obra).
- `comparar_estados(antes, depois, tolerancia=0.01) -> dict` com
  `equivalente: bool` e lista de divergências legíveis; % por tarefa compara
  por id (tarefas vivas em ambos); fontes de progresso do "depois" devem
  concordar entre si (tolerância 0.1 de arredondamento de exibição).
Commit: `feat(cronograma): verificador de equivalência de obra para migrações (M09)`.

## Task 2: importador registra versão + recusa destrutiva

Em `importar_fisico_financeiro` (aditivo):
- Antes de `_limpar_derivados`: se a obra tem `CronogramaVersao` cuja
  `importacao_id` aponta importação de `origem` upload (fluxo novo) →
  `ValueError` com mensagem "obra já versionada pela importação de cronograma
  — use a aba Cronograma da obra"; a rota do hub devolve 422 com a mensagem.
- Após materializar tudo: `_registrar_versao_inicial(obra, admin_id)` — arquiva
  versão ativa anterior (se houver), cria `CronogramaVersao` ativa (nº max+1)
  com `observacao='importação físico-financeira (json_canonico)'`, snapshots
  via `_snapshot_versao` (M05) e `CronogramaImportacao(origem='json_canonico',
  status='aplicado', arquivo_nome do payload)` ligada à versão.
Testes (arquivo novo `tests/test_migracao_baias_equivalencia.py`): fixture
mínima cria obra → versão nº1 + snapshots + importação json_canonico existem;
reimport canônico em obra ainda-canônica segue permitido (versão nº2); recusa
422 após aplicar pelo fluxo novo. Suíte dos 46 permanece verde SEM edição.
Commit: `feat(cronograma): importador físico-financeiro versiona e protege obra migrada (M09)`.

## Task 3: cenário completo de migração da baia (banco de teste)

`test_migracao_baias_equivalencia.py`, cenário integral (marker `java`; skip
sem JVM): importar fixture canônica das baias (101 tarefas, 19 RDOs) →
`capturar_estado` (A) → upload real de `CRONOGRAMA 06.07.mpp` pelo endpoint
M03 → reconciliar (M05) → conferir matching alto (níveis 3-5, como prevê a
spec §16) → decidir programaticamente as pendências restantes (equivalente do
antigo REMAP) → aplicar → `capturar_estado` (B) → comparar A≈B (tarefas 101,
RDOs/apontamentos/fotos idênticos, % por tarefa ±0.01; uids gravados) →
`restaurar_versao` para a versão pré-migração → `capturar_estado` (C) →
comparar A≈C (rollback ensaiado). Relatório de equivalência salvo como evento
da importação (spec §16).
Commit: `test(cronograma): migração das baias com equivalência e rollback (M09)`.

## Task 4: docs + gate + fecho §22

Atualizar `ESTADO_ATUALIZACAO_BAIA.md` (novo fluxo de atualização = aba
Cronograma da obra; procedimento homolog→produção com backup e janela;
checklist de descontinuação §4.3 adiado para pós-estabilidade) e a nota em
`RDO.md`. Gate escopado + fecho com ressalvas (execução em homolog/produção e
descontinuação física são operacionais — fora deste ambiente).

## Critérios de aceite (spec §22, escopo executável)
1. Equivalência automatizada verde em banco de teste (cenário completo).
2. Rollback ensaiado no mesmo teste. 3. Importador registra versão e recusa
o caminho destrutivo em obra migrada. 4. Suíte dos 46 intacta. 5. Grep de
guarda: nenhum "baia" novo em `services/` (os comentários históricos citados
pela spec são atualizados na Task 4). 6. Fluxo antigo permanece funcional.

## Fora de escopo
Descontinuação física dos scripts/artefatos (§4.3 — pós-estabilidade);
execução em homologação/produção; família REV10; `FOTOS_RDO_BASE`.
