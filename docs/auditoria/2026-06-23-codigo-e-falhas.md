# Código morto e padrões de falha — 2026-06-23

## Código morto: imports não usados por arquivo (ruff F401) — top 30 arquivos
     55 views/vehicles.py
     42 views/dashboard.py
     36 views/employees.py
     30 views/api.py
     29 views/obras.py
     27 views/helpers.py
     26 views/rdo.py
     18 exportacao_relatorios.py
     18 analytics_preditivos.py
     17 contabilidade_views.py
     13 views/__init__.py
     12 contabilidade_utils.py
     10 relatorios_financeiros_avancados.py
     10 propostas_consolidated.py
      8 veiculos_services.py
      8 portal_obras_views.py
      8 ponto_views.py
      8 models.py
      8 dashboards_especificos.py
      8 almoxarifado_utils.py
      7 tests/test_browser_all_modules.py
      7 financeiro_service.py
      6 event_manager.py
      5 scripts/fix_gestao_custos_seed.py
      5 pdf_generator.py
      5 decorators.py
      5 custos_views.py
      5 cronograma_views.py
      5 compras_views.py
      4 scripts/seed_v2_test.py

## Variáveis não usadas (F841) — contagem por arquivo
      6 views/rdo.py
      4 tests/test_browser_all_modules.py
      3 exportacao_relatorios.py
      2 views/vehicles.py
      2 tests/test_task_45_catalogo_eventos.py
      2 tests/test_regras_salario_completo.py
      2 tests/test_custo_diario.py
      2 propostas_consolidated.py
      2 ponto_views.py
      2 financeiro_views.py
      2 financeiro_service.py
      2 cronograma_views.py
      1 views/almoxarifado/movimentos.py
      1 utils.py
      1 utils/observability.py
      1 utils/database_diagnostics.py
      1 utils/cronograma_engine.py
      1 tests/test_orcamento_formato_br_e2e.py
      1 tests/test_cronograma_duplicado_rdo.py
      1 tests/test_cronograma_automatico_aprovacao.py

## Candidatos a função/classe morta (vulture, confiança >=90%)
almoxarifado_utils.py:5: unused import 'CategoriaProduto' (90% confidence)
analytics_preditivos.py:629: unused variable 'matriz' (100% confidence)
contabilidade_utils.py:11: unused import 'FluxoCaixaContabil' (90% confidence)
contabilidade_utils.py:11: unused import 'ProvisaoMensal' (90% confidence)
contabilidade_utils.py:1084: unused import 'TA_LEFT' (90% confidence)
custos_views.py:6: unused import 'db_transaction' (90% confidence)
entrega_baia_rev10/06_codigo_calculo/orcamento_service.py:385: unused import '_math' (90% confidence)
exportacao_relatorios.py:28: unused import 'letter' (90% confidence)
financeiro_seeds.py:122: unreachable code after 'return' (100% confidence)
financeiro_service.py:10: unused import 'FluxoCaixaContabil' (90% confidence)
folha_pagamento_views.py:7: unused import 'CalculoHorasMensal' (90% confidence)
gerar_cache_facial.py:227: unreachable code after 'return' (100% confidence)
gerar_cache_facial.py:323: unreachable code after 'return' (100% confidence)
models.py:6: unused import 'SQLEnum' (90% confidence)
models.py:1413: unused variable 'mapper' (100% confidence)
models.py:5556: unused variable 'mapper' (100% confidence)
models.py:5791: unused variable 'mapper' (100% confidence)
models.py:5797: unused variable 'mapper' (100% confidence)
models.py:5805: unused variable 'mapper' (100% confidence)
models.py:5811: unused variable 'flush_context' (100% confidence)
models.py:5942: unused variable 'mapper' (100% confidence)
models.py:5948: unused variable 'mapper' (100% confidence)
models.py:5953: unused variable 'mapper' (100% confidence)
models.py:6708: unused variable 'mapper' (100% confidence)
pdf_generator.py:6: unused import 'letter' (90% confidence)
pdf_generator.py:12: unused import 'TA_LEFT' (90% confidence)
ponto_views.py:26: unused import 'DispositivoObra' (90% confidence)
ponto_views.py:30: unused import 'identificar_funcionario_multiplas_fotos' (90% confidence)
propostas_consolidated.py:30: unused import 'funcionario_key_generator' (90% confidence)
propostas_consolidated.py:30: unused import 'idempotent' (90% confidence)
propostas_consolidated.py:33: unused import 'PropostasSaga' (90% confidence)
propostas_consolidated.py:644: unreachable code after 'continue' (100% confidence)
relatorios_funcionais.py:711: unused import 'letter' (90% confidence)
relatorios_funcionais.py:770: unreachable code after 'try' (100% confidence)
scripts/gerar_manual_pdf.py:7: unused import 'TA_LEFT' (90% confidence)
services/orcamento_service.py:385: unused import '_math' (90% confidence)
tests/test_fluxo_entradas_realizadas.py:23: unused variable 'app_ctx' (100% confidence)
tests/test_fluxo_obra.py:27: unused variable 'app_ctx' (100% confidence)
tests/test_fluxo_obra.py:50: unused variable 'app_ctx' (100% confidence)
tests/test_fluxo_obra.py:84: unused variable 'app_ctx' (100% confidence)
tests/test_notificacao_proposta_enviada.py:47: unused variable 'app_ctx' (100% confidence)
tests/test_vinculo_subatividade_composicao.py:45: unused variable 'app_ctx' (100% confidence)
tests/test_vinculo_subatividade_composicao.py:137: unused variable 'app_ctx' (100% confidence)
tests/test_webhook_dispatcher.py:60: unused variable 'app_ctx' (100% confidence)
tests/test_webhook_dispatcher.py:155: unused variable 'app_ctx' (100% confidence)
tests/test_webhook_dispatcher.py:155: unused variable 'webhook_ligado' (100% confidence)
tests/test_webhook_dispatcher.py:169: unused variable 'app_ctx' (100% confidence)
tests/test_webhook_dispatcher.py:191: unused variable 'app_ctx' (100% confidence)
tests/test_webhook_dispatcher.py:191: unused variable 'webhook_ligado' (100% confidence)
tests/test_webhook_dispatcher.py:204: unused variable 'app_ctx' (100% confidence)
tests/test_webhook_dispatcher.py:204: unused variable 'webhook_ligado' (100% confidence)
tests/test_webhook_dispatcher.py:217: unused variable 'app_ctx' (100% confidence)
tests/test_webhook_dispatcher.py:217: unused variable 'webhook_ligado' (100% confidence)
tests/test_webhook_dispatcher.py:233: unused variable 'app_ctx' (100% confidence)
tests/test_webhook_dispatcher.py:233: unused variable 'webhook_ligado' (100% confidence)
tests/test_webhook_dispatcher.py:247: unused variable 'app_ctx' (100% confidence)
tests/test_webhook_dispatcher.py:247: unused variable 'webhook_ligado' (100% confidence)
tests/test_webhook_dispatcher.py:280: unused variable 'app_ctx' (100% confidence)
tests/test_webhook_dispatcher.py:280: unused variable 'webhook_ligado' (100% confidence)
tests/test_webhook_dispatcher.py:297: unused variable 'app_ctx' (100% confidence)

## Bare except / raise-without-from (ruff E722, B904)
almoxarifado_utils.py:55:5: E722 Do not use bare `except`
almoxarifado_utils.py:72:5: E722 Do not use bare `except`
almoxarifado_utils.py:91:9: E722 Do not use bare `except`
categoria_servicos.py:28:5: E722 Do not use bare `except`
contabilidade_views.py:1161:9: E722 Do not use bare `except`
crud_rdo_completo.py:688:13: E722 Do not use bare `except`
dashboards_especificos.py:53:9: E722 Do not use bare `except`
fix_all_admin_id_universal.py:186:9: E722 Do not use bare `except`
models.py:1615:13: E722 Do not use bare `except`
models.py:3832:13: E722 Do not use bare `except`
pdf_generator.py:20:1: E722 Do not use bare `except`
pdf_generator.py:23:5: E722 Do not use bare `except`
production_routes.py:276:9: E722 Do not use bare `except`
propostas_consolidated.py:431:9: E722 Do not use bare `except`
relatorios_financeiros_avancados.py:58:9: E722 Do not use bare `except`
services/rdo_foto_service.py:297:9: B904 Within an `except` clause, raise exceptions with `raise ... from err` or `raise ... from None` to distinguish them from errors in exception handling
services/rdo_foto_service.py:357:9: E722 Do not use bare `except`
services/rdo_foto_service.py:367:9: E722 Do not use bare `except`
utils/database_diagnostics.py:319:13: E722 Do not use bare `except`
utils/idempotency.py:202:25: E722 Do not use bare `except`
utils/idempotency.py:239:17: E722 Do not use bare `except`
utils/production_error_handler.py:49:5: E722 Do not use bare `except`
utils/production_error_handler.py:130:5: E722 Do not use bare `except`
utils/saga.py:263:17: E722 Do not use bare `except`
views/api.py:75:21: E722 Do not use bare `except`
views/api.py:122:21: E722 Do not use bare `except`
views/api.py:127:21: E722 Do not use bare `except`
views/api.py:143:21: E722 Do not use bare `except`
views/api.py:148:21: E722 Do not use bare `except`
views/api.py:1078:9: E722 Do not use bare `except`
views/dashboard.py:174:9: E722 Do not use bare `except`
views/employees.py:167:17: E722 Do not use bare `except`
views/employees.py:184:9: E722 Do not use bare `except`
views/employees.py:539:13: E722 Do not use bare `except`
views/helpers.py:479:9: E722 Do not use bare `except`
views/obras.py:750:9: E722 Do not use bare `except`
views/obras.py:979:9: E722 Do not use bare `except`
views/obras.py:1001:13: E722 Do not use bare `except`
views/obras.py:1014:9: E722 Do not use bare `except`
views/obras.py:1601:17: E722 Do not use bare `except`
(total E722/B904: 54)

## 'except ...: pass' que engole erro (top arquivos)
    140 migrations.py:
     10 views/rdo.py:
     10 views/obras.py:
      9 propostas_consolidated.py:
      8 scripts/smoke_test_modulos_apoio.py:
      7 medicao_views.py:
      6 utils/webhook_dispatcher.py:
      4 views/almoxarifado/relatorios.py:
      4 models.py:
      4 cronograma_views.py:
      3 importacao_views.py:
      2 views/almoxarifado/itens.py:
      2 utils/rdo_equip_ocorr.py:
      2 utils/production_error_handler.py:
      2 utils/catalogo_eventos.py:
      2 tests/test_rdo_unificado_playwright.py:
      2 tests/test_browser_all_modules.py:
      2 services/rdo_foto_service.py:
      2 services/custo_funcionario_dia.py:
      2 services/cronograma_proposta.py:

## Registro de blueprint silencioso no boot (main.py)
13:    logger.error(f"[WARN] Erro ao importar sistema de edição RDO: {e}")
14:except Exception as e:
27:    logger.warning(f"[WARN] Sistema CRUD RDO não encontrado: {e}")
90:    logger.warning(f"[WARN] Health check não encontrado: {e}")
102:except Exception as e:
118:except Exception as e:
130:except Exception as e:
142:except Exception as e:
150:except Exception as e:
158:except Exception as e:
169:except Exception as e:
176:except Exception as e:
185:except Exception as e:
221:except Exception as e:
222:    logger.error(f"[WARN] CSRF exempt portal_obras routes: {e}")
228:except Exception as e:
229:    logger.error(f"[WARN] CSRF exempt medicao portal: {e}")
237:    logger.warning(f"[WARN] custos_escritorio não encontrado: {e}")
238:except Exception as e:
246:    logger.warning(f"[WARN] catalogos não encontrado: {e}")
247:except Exception as e:
255:    logger.warning(f"[WARN] quick_create não encontrado: {e}")
256:except Exception as e:
264:    logger.warning(f"[WARN] cadastros_hub não encontrado: {e}")
265:except Exception as e:
