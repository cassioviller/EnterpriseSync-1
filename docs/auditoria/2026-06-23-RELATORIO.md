# Relatório de Auditoria SIGE — 2026-06-23

Consolida os achados de `2026-06-23-inventario-arquivos.md`,
`2026-06-23-mapa-modulos.md` e `2026-06-23-codigo-e-falhas.md`. Baseline em
`2026-06-23-baseline.md` (1093 erros ruff, 37 blueprints no boot).

## Resumo executivo
- Binários/artefatos a destrastrear: **5 binários** (zip×2, mpp, pkl, db) + **29
  xlsx/pdf** em attached_assets/entregáveis + **9 png** de teste.
- One-offs/disabled a remover: **6** `fix_*_admin_id.py` (mortos) + diagnósticos/relatórios
  soltos + `bypass_auth.py.disabled`. **`fix_all_admin_id_universal.py` NÃO** (vivo, ver D1).
- Módulos `*_views` MORTOS: **0** (todos vivos; Task 10 = no-op).
- Imports não usados (ruff F401): **595** → alvo do `ruff --fix` seguro (Task 8).
- Achados de falha: ALTA **1** / MÉDIA **3** / BAIXA **muitos** (51 bare except + 100
  f-strings vazias, em sua maioria cosméticos).
- Hotspots de otimização confirmados: **2** (N+1).

## A. Arquivos mortos (ação: Fase 2 — Tasks 6 e 7)
| arquivo | tipo | ação |
|---|---|---|
| `10. Kabod...zip`, `entrega_baia_rev10.zip` | binário | git rm --cached |
| `Projeto1.mpp`, `cache_facial.pkl`, `sige.db` | binário | git rm --cached |
| `APRESENTACAO_Baia_REV10.pdf`, `docs/manual_ciclo/Manual_Ciclo_SIGE.pdf` | pdf | git rm --cached |
| `attached_assets/*.xlsx`, `attached_assets/*.pdf` (29) | artefato | git rm --cached |
| `tests/reports/*.png` (9) | runtime | git rm --cached |
| 6× `fix_*_admin_id.py` (exceto universal) | one-off morto | git rm |
| `diagnostico_veiculos_*.json`, `validacao_*.json`, `relatorio_*.txt/json` | diagnóstico | git rm |
| `bypass_auth.py.disabled` | resíduo/segurança | git rm |

## B. Módulos mortos (ação: Task 10)
**Nenhum.** Todos os `*_views.py` (topo) e `views/*` são importados por `main.py` ou
`views/__init__.py`. Task 10 = NO-OP. A coexistência flat vs pacote é dívida (seção F).

## C. Código morto (ação: Fase 2 — Task 8)
- **595 imports não usados (F401)** — concentrados em `views/vehicles.py` (55),
  `views/dashboard.py` (42), `views/employees.py` (36), `views/api.py` (30),
  `views/obras.py` (29), `views/helpers.py` (27), `views/rdo.py` (26). Removíveis via
  `ruff --fix --select F401,F811` (seguro), com revisão dos imports de efeito colateral
  em `app.py` (`event_manager`, `handlers.*`).
- 52 variáveis não usadas (F841): correção manual, baixa prioridade (não no fix seguro).
- Candidatos do vulture: tratar como pistas, não remover automaticamente.

## D. Possíveis falhas (ação: Fase 3 — Tasks 9 e 11)
| id | arquivo:linha | descrição | severidade | correção |
|---|---|---|---|---|
| D1 | `app.py:601-607` | `auto_fix_all_admin_id()` roda a CADA boot dentro de try/except que só loga erro; migração pesada no startup | **ALTA** (operacional) | fora do escopo de remoção; **Task 9**: garantir `exc_info=True` no log p/ rastrear falha; consolidar como risco (F) |
| D2 | `main.py` (blocos register_blueprint) | falha de registro vira `[WARN]` sem stacktrace → rota "some" silenciosamente | MÉDIA | **Task 9**: `exc_info=True` nos logs de boot |
| D3 | `views/obras.py:750` | `except: pass`-like no rollback engole causa | MÉDIA | **Task 11**: `except Exception` + log com `exc_info` |
| D4 | `views/api.py:75,122,127,143,148` | bare `except:` em conversão `int()` | MÉDIA→BAIXA | **Task 11**: `except (ValueError, TypeError):` |
| D5 | 51× `E722` bare except (almoxarifado_utils, pdf_generator, models, utils/*, views/*) | captura ampla demais (pega KeyboardInterrupt/SystemExit) | BAIXA | narrowing pontual nos de conversão; demais ficam registrados |
| D6 | `bypass_auth.py.disabled` | bypass de auth versionado (desabilitado) | segurança (BAIXA, latente) | **Task 7**: remover do repo |

## E. Otimização (ação: Fase 4 — Task 12)
| id | arquivo:linha | hotspot | correção |
|---|---|---|---|
| E1 | `views/obras.py:127-145` | **N+1 aninhado**: `Funcionario.query.get(registro.funcionario_id)` dentro de `for registro` dentro de `for obra` | pré-carregar funcionários do período num dict antes do loop (1 query) e consultar o dict |
| E2 | `cronograma_views.py:129-134` | 2 queries por obra (`count()` + `avg()`) no loop de obras | substituir por agregação `group_by(obra_id)` (2 queries totais) |

## F. Risco de manutenção (registrar; fora de escopo desta passada)
- Arquivos gigantes: `migrations.py` (562KB), `models.py` (342KB), `views/rdo.py`
  (262KB), `propostas_consolidated.py` (127KB). Quebrar = projeto à parte.
- Dívida estrutural flat (`*_views.py`) vs pacote (`views/`) coexistindo — consolidar é
  projeto à parte (ambos vivos, sem código morto).
- `app.py` rodando auto-fix de schema a cada boot (D1) — candidato a virar migração
  versionada explícita (Alembic já está no projeto).
- `archive/` e `backups/legacy_*` (137 arquivos) — resíduo histórico isolado; remoção é
  decisão à parte.
