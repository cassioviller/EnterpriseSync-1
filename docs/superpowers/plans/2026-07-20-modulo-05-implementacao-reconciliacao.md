# Módulo 05 — Reconciliação e Versionamento — Implementation Plan

> Fonte: spec `2026-07-17-modulo-05-reconciliacao-versionamento.md`. Em conflito, este
> plano vence (reconcilia a spec com o modelo vivo real, mapeado em 2026-07-20).

**Goal:** comparar o cronograma ativo da obra com o `json_normalizado` (M04), classificar
diferenças (diff puro), permitir decisão manual de ambíguos, e **aplicar** a nova versão
em transação única — preservando IDs de tarefa, RDOs, medições e histórico, com rollback
por snapshot.

## Fatos do modelo vivo (medidos 2026-07-20 — NÃO re-descobrir)

- **`TarefaCronograma`** (leitura/escrita): `predecessora_id` é **ÚNICA, SET NULL, sem
  tipo/lag** (`models.py:4878`). Tem `mpp_uid` (BigInt), `wbs_codigo` (50), `fingerprint`
  (64), `is_marco`, `ativa` (NOT NULL default true), `arquivada_em`, `versao_criacao_id`
  (→cronograma_versao, SET NULL). **NÃO tem `is_resumo`** (inferido por ter filhas).
  Campos de conteúdo: `nome_tarefa`(200), `duracao_dias`(int), `data_inicio/fim`,
  `quantidade_total`(float), `unidade_medida`(20), `ordem`, `percentual_concluido`,
  `tarefa_pai_id` (SET NULL).
- **FKs que o DELETE destruiria (por isso NUNCA deletar):** `RDOApontamentoCronograma`
  (CASCADE, `models.py:4969`), `RDOSubempreitadaApontamento` (CASCADE), `ItemMedicaoCronogramaTarefa`
  (CASCADE), `RDOMaoObra` (SET NULL). Preservar IDs = preservar esses apontamentos.
- **`CronogramaVersao`**: `numero` (seq por obra, `uq_cronograma_versao_obra_numero`),
  `status` ('ativa'|'arquivada'), `importacao_id` (FK nullable), `aplicada_em/por_id`,
  `observacao`. **Índice parcial `uq_cron_versao_uma_ativa` (WHERE status='ativa')** —
  ao inserir a nova versão ativa é OBRIGATÓRIO arquivar a anterior na MESMA transação.
- **`CronogramaTarefaSnapshot`**: foto integral por versão — `versao_id` (CASCADE),
  `tarefa_id` (SET NULL, sobrevive ao arquivamento), `tarefa_pai_snapshot_id` (self-FK),
  `predecessoras_json` (lista `{uid,tipo,lag}` — ÚNICO lugar com predecessora tipada),
  `is_resumo`, `percentual_concluido_no_momento`, `payload_extra`, e cópia de
  nome/ordem/datas/duração/qtd/unidade/is_marco/mpp_uid/wbs.
- **`CronogramaTarefaMapeamento`** (`models.py:5130`): resultado da reconciliação —
  `tipo` VARCHAR(40) (exata/renomeada/movida/datas_alteradas/…/dividida/fundida/nova/
  removida/ambigua/revisao_manual), `tarefa_atual_id` (SET NULL), refs à importação,
  `origem_decisao`, `decidido_por_id`. USAR esta tabela para persistir mapeamentos.
- **UI lê por `obra_id+admin_id+is_cliente`, NÃO filtra `ativa`** (`cronograma_views.py:179,859`).
  ⇒ arquivar exige adicionar `.filter(TarefaCronograma.ativa.is_(True))` nessas queries.
- **Motor de recálculo JÁ existe** (`utils/cronograma_engine.py`): `recalcular_cronograma`,
  `sincronizar_percentuais_obra`. A aplicação os chama no fim (o "M06 antes de M5" da spec
  é sobre unificação, não sobre criar recálculo — não bloqueia o M05).
- **Backfill (migration 210)** já criou versão nº1 'ativa' + snapshots para obras com
  tarefas. Primeira importação nova: tarefas sem `mpp_uid` ⇒ cascata cai p/ níveis 3-6.
- Pytest direto; `-m "not java"` p/ subset rápido; DB Postgres real (serverless — pode
  ter cold start).

## Contrato `RelatorioDiff` (JSON gravado em `cronograma_importacao.relatorio_diff`)

```json
{"versao": "1.0",
 "resumo": {"exatas": 90, "renomeadas": 3, "novas": 5, "removidas": 2, "ambiguas": 1,
   "revisao_manual": 1, "alteracoes": {"datas": 12, "duracao": 4, "predecessoras": 6}},
 "mapeamentos": [{"id_temp": 0, "tipo": ["exata","datas_alteradas"],
   "tarefa_atual_id": 501, "chave_nova": "uid:132", "nivel_match": "mpp_uid",
   "score": null, "decisao_requerida": false, "candidatos": [],
   "detalhes": {"nome_de":"...","nome_para":"...","datas_de":[...],"datas_para":[...]}}],
 "sugestoes_split_merge": [{"tipo":"dividida","antiga_id":77,"novas_chaves":["uid:200","uid:201"]}]}
```

`nivel_match` ∈ {mpp_uid, wbs, caminho, nome_unico, fingerprint, score, none}.
`decisao_requerida=true` para ambigua/revisao_manual/dividida/fundida.

---

## Task 1 (subagente): reconciliação PURA — `services/cronograma_reconciliacao.py`

**Files:** Create `services/cronograma_reconciliacao.py`, `tests/test_cronograma_reconciliacao.py`.

Função `reconciliar(tarefas_atuais, normalizado) -> dict` (RelatorioDiff acima). PURA:
recebe uma lista de dicts simples representando as tarefas vivas (o chamador extrai de
`TarefaCronograma` — o serviço NÃO importa models/db) e o `json_normalizado`. Cascata
determinística §4.1 (primeiro match vence; cada nível só olha não-casados):
1 mpp_uid==uid · 2 wbs_codigo==wbs · 3 caminho normalizado exato · 4 nome_normalizado
único nos dois lados · 5 fingerprint · 6 score composto (`0.5*difflib ratio + 0.2*mesmo
pai + 0.15*sobreposição datas + 0.1*duração±1d + 0.05*mesmas predecessoras`; ≥0.85 e
único ⇒ `correspondencia_provavel`; 2+ ≥0.85 ou top 0.60-0.85 ⇒ `ambigua`) · 7 resto
(novas/removidas/revisao_manual). Classificações cumulativas sobre casados: renomeada,
movida_hierarquia, datas_alteradas, duracao_alterada, predecessoras_alteradas,
quantidade_alterada, unidade_alterada. Split/merge: detecção §4.1 (nome antigo prefixo
de ≥2 novas sob mesmo pai ⇒ `dividida`; espelho ⇒ `fundida`) — SÓ sugestão.

Testes (§17): um cenário por nível da cascata; cumulativos (renomeada+datas_alteradas);
split GABARITO→A/B; determinismo (dupla execução idêntica); ambíguo marca
`decisao_requerida=true`; multitenant é responsabilidade do chamador (o serviço só vê o
que recebe — testar que não inventa matches fora da lista). Import-lint: não importa
models/db/flask.

Commit: `feat(cronograma): reconciliação determinística por cascata (M05)`.

## Task 2 (main loop + review pesada): aplicação transacional — `services/cronograma_versao_service.py`

**Files:** Create `services/cronograma_versao_service.py`, `tests/test_cronograma_versao_service.py`;
Modify `cronograma_views.py` (filtro `ativa` nas leituras).

`aplicar_versao(importacao_id, decisoes, usuario_id) -> CronogramaVersao`, transação única:
1. Validar: importação `aguardando_revisao`; zero pendências sem decisão; `SELECT FOR
   UPDATE` na obra (lock anti-concorrência).
2. Snapshot integral da versão ativa atual (se ainda não snapshotada).
3. Aplicar mapeamentos: **casadas → UPDATE in-place** (nome, datas, duração,
   `tarefa_pai_id`, **`predecessora_id`=primeira predecessora FS; lista tipada completa
   só no snapshot**, quantidade, unidade, wbs_codigo, mpp_uid, is_marco, ordem — NUNCA
   sobrescreve `percentual_concluido`); **novas → INSERT** (`versao_criacao_id`=nova);
   **removidas/divididas/fundidas → `ativa=False, arquivada_em=now()`** (assert anti-DELETE
   em código). Fusão quantitativa só soma acumulados se todas as antigas têm mesma unidade.
4. Carga inicial de `pct_project` → realizado SOMENTE se a obra não tem NENHUM RDO.
5. Nova `CronogramaVersao` ativa; anterior → 'arquivada' (respeita `uq_cron_versao_uma_ativa`);
   snapshot da nova; `importacao.status='aplicado'`, `aplicado_em`, `CronogramaVersao.importacao_id`.
6. Recalcular: `recalcular_cronograma` + `sincronizar_percentuais_obra`; evento `aplicado`
   com antes/depois + contadores de matching por nível.
7. Commit único; qualquer exceção ⇒ rollback total.
+ **Filtro `ativa` na UI**: `cronograma_views.py` queries de leitura ganham
  `.filter(TarefaCronograma.ativa.is_(True))` (as 2 mapeadas + varrer o arquivo).

Testes (§17, os que mais importam): obra com RDOs criados via UI → aplicar versão com
datas novas → **todos** `RDOApontamentoCronograma`/medições intactos (contagem+valores),
IDs de casadas inalterados; **assert-no-DELETE**; transacionalidade (exceção injetada no
meio ⇒ obra byte-idêntica por snapshot compare); concorrência (2 aplicações ⇒ 1 falha
limpa); tarefa arquivada NÃO aparece na query da UI.

Commit: `feat(cronograma): aplicação transacional versionada preservando RDOs (M05)`.

## Task 3 (subagente): rollback — `restaurar_versao` + round-trip

`restaurar_versao(versao_id, usuario_id)`: reconstrói tarefas do snapshot da versão alvo
(UPDATE vivas, reativa arquivadas, arquiva as criadas depois), nova versão
`observacao='rollback da vN'`, mesmo recálculo. Teste de propriedade: aplicar vN+1 →
restaurar vN ⇒ tarefas idênticas ao snapshot de vN (reflexão sobre colunas).
Commit: `feat(cronograma): restauração de versão por snapshot com round-trip (M05)`.

## Task 4 (subagente): endpoints — `cronograma_views.py`/view do M03

`POST .../importacoes/<iid>/reconciliar` (grava relatorio_diff + mapeamentos auto,
status `aguardando_revisao`); `GET .../<iid>/diff`; `PATCH .../<iid>/mapeamentos/<mid>`
(decisão manual); `POST .../<iid>/aplicar` (422 se pendências); `POST .../versoes/<vid>/restaurar`.
Todas com `cronograma_import_required` + tenant-scope. Testes de integração.
Commit: `feat(cronograma): endpoints de reconciliação, decisão e aplicação (M05)`.

## Task 5: gate escopado + fecho §22.

## Critérios de aceite (spec §18/§22)
1. Cascata coberta nível a nível. 2. Ambíguo nunca auto-aplicado (teste negativo).
3. Aplicação preserva 100% dos RDOs/medições (contagem+valores). 4. Rollback round-trip
verde. 5. Transacionalidade (rollback total em exceção). 6. Nenhum DELETE de
tarefa_cronograma no serviço (assert+teste). 7. Concorrência: 2ª aplicação falha limpa.
