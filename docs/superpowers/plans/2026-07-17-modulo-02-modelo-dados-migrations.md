# Módulo 2 — Modelo de Dados e Migrations

> Parte do plano mestre `2026-07-17-cronograma-mpp-rdo-master-plan.md`.

## 1. Objetivo

Criar as entidades de importação/versionamento de cronograma e as colunas de identidade estável e de apontamento semântico, de forma aditiva, idempotente e tenant-scoped — sem alterar nenhum comportamento existente.

## 2. Estado atual encontrado no código

- `TarefaCronograma` (`models.py:4858`): sem versão, sem UID/WBS, sem marco, sem flag de arquivamento; `predecessora_id` único FS sem lag (`:4878-4882`); `quantidade_total`/`unidade_medida` (`:4888-4889`); `percentual_concluido` (`:4906`); `is_cliente` (`:4917`); `admin_id` NOT NULL (`:4911`).
- `RDOApontamentoCronograma` (`models.py:4941`): `quantidade_executada_dia`, `quantidade_acumulada`, `percentual_realizado`, `percentual_planejado` (`:4959-4966`); FK tarefa CASCADE (`:4954`). No modo percentual do import, `quantidade_executada_dia` armazena **incremento percentual** e `quantidade_acumulada=0.0` (`services/importacao_fisico_financeiro.py:521-532`) — semanticamente errado.
- Não existe hash de arquivo para cronograma (só `NotaFiscal.xml_hash` `models.py:1965` e `SpedContabil.hash_arquivo` `:2685` como precedentes). Versionamento só em Propostas (`models.py:3017,3093`).
- Padrão de migrations: `run_migration_safe(numero, nome, func)` (`migrations.py:146`) + `executar_migracoes()` (`:3773`) no startup via `pre_start.py`; idempotência por `migration_history` (`MigrationHistory`, `models.py:4619`) e SQL `IF NOT EXISTS`/checagem em `information_schema`. Última migração: **199** (`_migration_199_obra_servico_custo_item`, `migrations.py:13640`).

## 3. Problemas atuais

1. Sem identidade externa (UID/WBS) não há como reconciliar versões de `.mpp`.
2. Sem snapshot não há prévia comparável, rollback nem auditoria.
3. Campos de quantidade reutilizados para percentual (acima).
4. Reimportação muda todos os ids de tarefa (destruição via `_limpar_derivados`).

## 4. Escopo

Novas tabelas (nomes seguindo o padrão snake_case do projeto):

### `cronograma_importacao` (modelo `CronogramaImportacao`)
| Coluna | Tipo | Notas |
|---|---|---|
| id | PK | |
| obra_id | FK obra.id ondelete CASCADE, index | |
| admin_id | FK usuario.id NOT NULL, index | tenant |
| arquivo_nome | String(255) | sanitizado (`secure_filename`) |
| arquivo_tamanho | Integer | bytes |
| arquivo_sha256 | String(64), index | idempotência; unique parcial `(obra_id, arquivo_sha256)` |
| arquivo_path | String(512) nullable | caminho no storage (`UPLOADS_PATH`) |
| origem | String(20) | `'upload_mpp'` \| `'json_cli'` (contingência) |
| parser_nome | String(50) | `'mpxj'` |
| parser_versao | String(20) | versão da lib mpxj usada |
| normalizador_versao | String(20) | versão do schema/regras (Módulo 4) |
| status | String(30) | `recebido → parseado → normalizado → reconciliado → aguardando_revisao → aplicado → falhou → cancelado` |
| json_bruto | JSONB nullable | saída do parser |
| json_normalizado | JSONB nullable | validado por schema |
| relatorio_diff | JSONB nullable | saída da reconciliação |
| erro | Text nullable | |
| criado_por_id | FK usuario.id | usuário que importou |
| criado_em / aplicado_em | DateTime | |

### `cronograma_versao` (modelo `CronogramaVersao`)
| Coluna | Tipo | Notas |
|---|---|---|
| id, obra_id (CASCADE, index), admin_id (NOT NULL, index) | | |
| numero | Integer | sequencial por obra; unique `(obra_id, numero)` |
| status | String(20) | `ativa` \| `arquivada`; unique parcial: 1 ativa por obra (índice `WHERE status='ativa'`) |
| importacao_id | FK cronograma_importacao.id nullable | NULL para a versão nº1 (backfill) |
| aplicada_em, aplicada_por_id | | auditoria |
| observacao | Text | ex.: "backfill inicial", "rollback da v3" |

### `cronograma_tarefa_snapshot` (modelo `CronogramaTarefaSnapshot`)
Fotografia integral de cada tarefa em cada versão (para diff, rollback e auditoria):
`id, versao_id (FK CASCADE, index), admin_id, tarefa_id (FK tarefa_cronograma.id SET NULL — pode ter sido arquivada), mpp_uid, wbs_codigo, nome_tarefa, tarefa_pai_snapshot_id, predecessoras_json (lista {uid, tipo, lag}), ordem, data_inicio, data_fim, duracao_dias, quantidade_total, unidade_medida, is_marco, is_resumo, percentual_concluido_no_momento, payload_extra JSONB`.

### `cronograma_tarefa_mapeamento` (modelo `CronogramaTarefaMapeamento`)
Resultado da reconciliação, por importação:
`id, importacao_id (FK CASCADE, index), admin_id, tarefa_atual_id (FK tarefa_cronograma SET NULL, nullable — NULL p/ tarefa nova), chave_nova (String — uid/wbs/fingerprint no arquivo novo, nullable p/ removida), tipo (String(40): correspondencia_exata | correspondencia_provavel | nova | removida | renomeada | movida_hierarquia | datas_alteradas | duracao_alterada | predecessoras_alteradas | quantidade_alterada | unidade_alterada | ambigua | revisao_manual | dividida | fundida), score (Float 0-1), origem_decisao (String(20): auto | manual), decidido_por_id nullable, detalhes JSONB`.
Nota: um par pode ter vários registros de tipo (ex.: `correspondencia_exata` + `datas_alteradas`); modelar `tipo` como linha por classificação simplifica filtros na UI.

### `cronograma_importacao_evento` (modelo `CronogramaImportacaoEvento`)
Trilha de auditoria: `id, importacao_id (FK CASCADE, index), admin_id, evento (String(50)), detalhes JSONB, usuario_id nullable, criado_em`. Eventos mínimos: upload, parse_ok/parse_erro, normalizado, reconciliado, revisao_alterada, aplicado, rollback, cancelado.

Novas colunas em tabelas existentes (todas nullable/default, aditivas):

- `tarefa_cronograma`: `mpp_uid BIGINT` (index composto `(obra_id, mpp_uid)`), `wbs_codigo VARCHAR(50)`, `fingerprint VARCHAR(64)` (determinístico, Módulo 4), `is_marco BOOLEAN DEFAULT FALSE`, `ativa BOOLEAN DEFAULT TRUE` (index parcial `WHERE ativa`), `arquivada_em TIMESTAMP NULL`, `versao_criacao_id FK cronograma_versao NULL`.
- `rdo_apontamento_cronograma`: `tipo_apontamento VARCHAR(15)` (`'quantitativo'|'percentual'`), `percentual_acumulado FLOAT NULL`, `percentual_incremento_dia FLOAT NULL`, `quantidade_total_snapshot FLOAT NULL`, `unidade_snapshot VARCHAR(20) NULL`.
- (Predecessoras múltiplas/tipo/lag: NÃO nesta fase — permanecem em `predecessoras_json` do snapshot e no JSON normalizado; a tarefa ativa continua com `predecessora_id` FS simples. Motivo: `recalcular_cronograma` só entende FS; estender o motor de datas é evolução separada, ver M6 §5.)

## 5. Fora de escopo

- Qualquer DELETE/alteração de colunas existentes; mudanças de comportamento; UI; serviços (M3-M5); tabela de curva planejada persistida (o planejado continua derivado — decisão D7/M6).

## 6. Arquivos atuais envolvidos

`models.py` (seções cronograma ~4858-4990 e RDO ~4941-4982), `migrations.py` (append ao final + registro em `executar_migracoes` `:3773`).

## 7. Arquivos novos ou alterados previstos

- `models.py`: 5 classes novas + colunas novas (junto do bloco de cronograma existente, seguindo estilo local).
- `migrations.py`: `migration_200_cronograma_versionamento` (DDL tabelas), `migration_201_tarefa_cronograma_identidade` (colunas tarefa), `migration_202_rdo_apontamento_semantico` (colunas apontamento), `migration_203_backfill_versao_inicial` (dados — ver §13).

## 8. Alterações de banco

Como acima. Índices: todos os FKs; `(obra_id, arquivo_sha256)` unique em importação; unique parcial 1-ativa por obra em versão; `(obra_id, mpp_uid)` e parcial `ativa` em tarefa. Todas tenant-scoped via `admin_id` NOT NULL (exceto onde espelha padrão nullable já existente — aqui: sempre NOT NULL).

## 9. Serviços e responsabilidades

Nenhum serviço neste módulo; modelos são passivos. Regra: nenhuma lógica de negócio em eventos SQLAlchemy novos (o projeto tem precedente em `models.py:1422`, mas snapshots aqui são preenchidos explicitamente pelos serviços do M5).

## 10. Rotas e contratos de API

Nenhuma.

## 11. Fluxo de frontend

Nenhum.

## 12. Regras de negócio

- Uma e somente uma `cronograma_versao.status='ativa'` por obra (constraint parcial + verificação no serviço M5).
- `tarefa_cronograma.ativa=False` nunca aparece em listagens novas, mas continua legível por joins de histórico (RDOs antigos).
- Snapshots são imutáveis após criados.

## 13. Estratégia de migração

- 200-202: DDL puro idempotente (`IF NOT EXISTS` via checagem `information_schema`, padrão de `_migration_75_cronograma_v2` `migrations.py:5405`).
- 203 (backfill, em lotes por obra para caber no timeout de 300s do startup):
  1. Para cada obra com tarefas: criar `cronograma_versao` nº1 `ativa` (observacao='backfill inicial') e snapshot de todas as tarefas.
  2. `rdo_apontamento_cronograma`: `tipo_apontamento = 'quantitativo'` se a tarefa tem `quantidade_total > 0`, senão `'percentual'`; `quantidade_total_snapshot`/`unidade_snapshot` copiados da tarefa; no modo percentual, `percentual_acumulado = percentual_realizado` e `percentual_incremento_dia = quantidade_executada_dia` (que hoje guarda o incremento percentual — ver `services/importacao_fisico_financeiro.py:526-528`). **Os campos antigos não são alterados** (leitura legada continua funcionando).
  3. Idempotente: pula obra que já tem versão nº1; pula apontamento com `tipo_apontamento` preenchido.

## 14. Compatibilidade

Nenhuma query existente é afetada (colunas novas nullable com default neutro; `ativa=TRUE` no backfill). O importador físico-financeiro atual continua funcionando sem conhecer as tabelas novas — na fase M9 ele passa a registrar versão.

## 15. Segurança

`admin_id` NOT NULL em tudo; nenhum dado sensível em JSONB além do conteúdo do próprio cronograma; `json_bruto` pode conter notas do Project — tratado como dado do tenant.

## 16. Observabilidade

Migração 203 loga contagem por obra (padrão de log do `run_migration_safe`).

## 17. Testes

- `tests/test_migrations_cronograma_versionamento.py`: (a) rodar `executar_migracoes()` duas vezes → sem erro (idempotência); (b) schema: colunas/índices existem (padrão de `test_medicao_contrato_schema_existe`, `tests/test_importacao_fisico_financeiro.py:27`); (c) backfill: obra com tarefas ganha versão 1 ativa + snapshots com contagem igual; apontamento percentual ganha `tipo_apontamento='percentual'` e `percentual_acumulado` correto; (d) unique 1-ativa por obra; (e) multitenant: backfill não cruza `admin_id`.
- Suíte `--gate` inteira verde (nenhuma regressão).

## 18. Critérios de aceite

1. Migrations 200-203 aplicam em banco com dados das baias sem erro e em <60s.
2. Reexecução = no-op.
3. Zero mudança de comportamento nas telas.
4. Critério global 15 (auditoria) tem onde morar (`cronograma_importacao_evento`).

## 19. Riscos

- Backfill lento em produção → lotes por obra + commit por lote.
- JSONB grande (json_bruto de cronogramas enormes) → limite de tamanho no M3 (validação de upload) protege.
- Constraint parcial `WHERE status='ativa'` exige Postgres (ok — projeto é Postgres-only, `app.py:58`).

## 20. Dependências

M1 concluído (nenhuma técnica, mas evita conflito de merge).

## 21. Ordem detalhada de implementação

1. Escrever teste de schema (falha). 2. Modelos em `models.py`. 3. Migração 200; teste passa parcial. 4. Migrações 201-202. 5. Teste de idempotência. 6. Migração 203 com testes de backfill (fixture: importar baias no banco de teste, rodar backfill, conferir). 7. Suíte completa. 8. Commit por migração.

## 22. Checklist de conclusão

- [x] 5 modelos novos + colunas novas em `models.py` (`e9ad566`)
- [x] Migrations **207-210** registradas em `executar_migracoes()` — a spec previa 200-203, mas 200-206 já existiam no repo; ver plano de implementação `2026-07-20-modulo-02-implementacao-modelo-dados.md`
- [x] Idempotência provada por teste (`test_reexecucao_das_migracoes_e_noop` + `test_backfill_reexecucao_noop`)
- [x] Backfill testado com dados das baias (`f65b56f` — inclui campos antigos byte a byte intactos e multitenant)
- [x] Suíte gate verde (2026-07-20: `pytest tests/ -m "not browser"` → 446 passed, 4 skipped)
