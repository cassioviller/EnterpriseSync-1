# Auditoria — Drop das Tabelas Legadas de Propostas (Task #201)

**Data do snapshot:** 2026-04-27 18:35 UTC
**Migração:** #141 (`migration_141_drop_legacy_propostas_tables` em `migrations.py`)
**Trigger:** Task #201 — "Aposentar modelo legado de propostas"

## Estado de cada tabela legada NO MOMENTO DO BACKUP

Levantamento via `psql $DATABASE_URL` antes da execução da Migration 141.

| Tabela legada                       | Estado no schema                | Linhas    | CSV gerado                                              |
|-------------------------------------|---------------------------------|-----------|---------------------------------------------------------|
| `proposta`                          | EXISTIA                         | **10**    | `legacy_proposta_2026-04-27.csv` (10 linhas + cabeçalho)|
| `proposta_servico`                  | EXISTIA                         | 0         | `legacy_proposta_servico_2026-04-27.csv` (só cabeçalho) |
| `item_servico_proposta_dinamica`    | EXISTIA                         | 0         | `legacy_item_servico_proposta_dinamica_2026-04-27.csv`  |
| `historico_status_proposta`         | EXISTIA                         | 0         | `legacy_historico_status_proposta_2026-04-27.csv`       |
| `item_proposta`                     | EXISTIA                         | 0         | `legacy_item_proposta_2026-04-27.csv`                   |
| `proposta_log`                      | EXISTIA                         | 0         | `legacy_proposta_log_2026-04-27.csv`                    |
| `item_servico_proposta`             | **AUSENTE** (já dropada antes)  | n/a       | sem CSV — não havia o que exportar                       |
| `tabela_composicao_proposta`        | **AUSENTE** (já dropada antes)  | n/a       | sem CSV — não havia o que exportar                       |

**Total de linhas preservadas em CSV:** 10 (todas em `proposta`).
**Total de tabelas dropadas pela Migration 141:** 6 efetivas (as 6 que ainda existiam no schema). As outras 2 (`item_servico_proposta`, `tabela_composicao_proposta`) só recebem `DROP TABLE IF EXISTS` no script para tornar a migração idempotente — ninguém precisa rodar manualmente para limpar resíduos.

## Pré-condições confirmadas antes do drop

1. **Sem classe SQLAlchemy mapeando** — `grep` em `models.py` confirmou que apenas `Proposta` (→ `propostas_comerciais`, viva, 706 linhas) existe. Nenhuma das 8 tabelas legadas tinha classe `__tablename__` apontando para elas.
2. **Sem código vivo referenciando** — `rg` em `views/`, `services/`, `handlers/`, `templates/`, `utils/`, `app.py` retornou ZERO matches para qualquer dos 8 nomes legados. Único hits: `archive/`, `attached_assets/`, relatórios `.md` (todos histórico).
3. **Dependências FK confirmadas** — `pg_constraint` mostrou que as 3 dependentes (`proposta_servico`, `item_proposta`, `historico_status_proposta`, `proposta_log`) tinham FK para `proposta(id)`. Migration 141 dropa filhas antes da pai (ordem: `item_servico_proposta_dinamica`, `proposta_servico`, `item_proposta`, `historico_status_proposta`, `proposta_log`, `item_servico_proposta`, `tabela_composicao_proposta`, `proposta`) e usa `CASCADE` como cinto-e-suspensório.

## Tabelas vivas preservadas (pertencem ao novo design — NÃO dropadas)

- `propostas_comerciais` — tabela principal (706 linhas), classe `Proposta`
- `proposta_historico`
- `proposta_itens`
- `proposta_clausula`
- `proposta_template_clausula`
- `proposta_arquivos`
- `proposta_templates`

## Validação pós-migração

- `migration_history` row `migration_number=141` → `status='success'`, executada em `2026-04-27 18:36:11`.
- `tests/test_legacy_propostas_drop.py` (workflow `test-legacy-propostas-drop`) — 19/19 PASS confirmando: 8 tabelas legadas ausentes, 6 vivas presentes, `propostas_comerciais` populada, backup CSV de `proposta` com 10 linhas + cabeçalho.

## Out of scope (anotado para follow-up)

A tabela singular `proposta_comercial` (1 linha, sem classe, sem código) foi descoberta durante o levantamento mas NÃO estava no escopo da Task #201. Foi anotada como Task #204 para limpeza futura.
