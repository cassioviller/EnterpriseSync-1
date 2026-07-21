# Anexo A — Rotas sem decorator de autenticação

> Gerado por censo AST de todos os `.py` de produção (exclui `tests/`,
> `scripts/`, `archive/`). Medido em `f090b09`, ou seja **depois** das
> correções da Fase 0 — eram 64 antes.

**724 rotas no total · 48 sem nenhum decorator de autenticação.**

## Classificação

| Criticidade | Rotas | Leitura |
|---|---:|---|
| `GRAVA` | 8 | aceita POST/PUT/PATCH/DELETE sem autenticação — o pior grupo |
| `EXPOE DADO (api)` | 11 | endpoint JSON legível por anônimo |
| `EXPOE DADO (página)` | 18 | template renderizado para anônimo |
| `TOKEN (legítimo)` | 11 | portal do cliente/proposta — autenticação POR TOKEN, é o desenho correto |

## Lista completa


### GRAVA

| Arquivo:linha | Rota | Métodos | Handler | Outros decorators |
|---|---|---|---|---|
| `api_organizer.py:62` | `/templates/carregar-multiplos` | POST | `carregar_templates_multiplos` | — |
| `api_organizer.py:144` | `/propostas/salvar-organizacao` | POST | `salvar_organizacao` | — |
| `api_servicos_obra_limpa.py:82` | `/api/obra/<int:obra_id>/servicos` | POST | `adicionar_servico_obra` | — |
| `api_servicos_obra_limpa.py:158` | `/api/obra/<int:obra_id>/servico/<int:servico_obra_id>` | PUT | `atualizar_servico_obra` | — |
| `api_servicos_obra_limpa.py:216` | `/api/obra/<int:obra_id>/servico/<int:servico_obra_id>` | DELETE | `remover_servico_obra` | — |
| `cadastrar_servico_obra.py:15` | `/obra/<int:obra_id>/cadastrar-servico` | GET/POST | `cadastrar_servico_obra` | — |
| `views/api.py:655` | `/api/ponto/lancamento-finais-semana` | POST | `lancamento_finais_semana` | — |
| `views/auth.py:15` | `/login` | GET/POST | `login` | limit |

### EXPOE DADO (api)

| Arquivo:linha | Rota | Métodos | Handler | Outros decorators |
|---|---|---|---|---|
| `api_funcionarios_buscar.py:20` | `/api/funcionarios/buscar` | GET | `buscar_funcionarios` | — |
| `api_organizer.py:15` | `/` | GET | `api_status` | — |
| `api_organizer.py:29` | `/templates/listar` | GET | `listar_templates` | — |
| `api_organizer.py:181` | `/propostas/<int:proposta_id>/itens-organizados` | GET | `obter_itens_organizados` | — |
| `api_servicos_obra_limpa.py:29` | `/api/obra/<int:obra_id>/servicos` | GET | `listar_servicos_obra` | — |
| `views/api.py:25` | `/api/funcionarios/<int:obra_id>` | GET | `api_funcionarios_por_obra` | — |
| `views/api.py:54` | `/api/funcionarios` | GET | `api_funcionarios_consolidada` | — |
| `views/rdo.py:1908` | `/rdo/api/ultimo-rdo/<int:obra_id>` | GET | `api_ultimo_rdo` | — |
| `views/rdo.py:3380` | `/api/test/rdo/servicos-obra/<int:obra_id>` | GET | `api_test_rdo_servicos_obra` | — |
| `views/rdo.py:3452` | `/api/ultimo-rdo-dados/<int:obra_id>` | GET | `api_ultimo_rdo_dados_v2` | — |
| `views/rdo.py:3742` | `/api/servicos-obra-primeira-rdo/<int:obra_id>` | GET | `api_servicos_obra_primeira_rdo` | — |

### EXPOE DADO (página)

| Arquivo:linha | Rota | Métodos | Handler | Outros decorators |
|---|---|---|---|---|
| `app.py:116` | `/persistent-uploads/<path:filename>` | GET | `persistent_uploads` | — |
| `app.py:445` | `/ponto-diagnostico` | GET | `ponto_diagnostico` | — |
| `health.py:14` | `/health` | GET | `health_check` | — |
| `health.py:56` | `/health/simple` | GET | `simple_health` | — |
| `landing_views.py:6` | `/site` | GET | `landing_page` | — |
| `main.py:110` | `/servicos` | GET | `_servicos_legacy_redirect` | — |
| `medicao_views.py:513` | `/medicao/portal/pdf/<int:medicao_id>` | GET | `portal_pdf_extrato` | — |
| `ponto_views.py:577` | `/debug` | GET | `ponto_debug` | — |
| `views/auth.py:47` | `/` | GET | `index` | — |
| `views/dashboard.py:25` | `/health` | GET | `health_check` | — |
| `views/dashboard.py:35` | `/health/veiculos` | GET | `health_check_veiculos` | — |
| `views/dashboard.py:197` | `/dashboard` | GET | `dashboard` | circuit_breaker |
| `views/employees.py:286` | `/funcionario_perfil/<int:id>` | GET | `funcionario_perfil` | — |
| `views/employees.py:604` | `/funcionario_perfil/<int:id>/pdf` | GET | `funcionario_perfil_pdf` | circuit_breaker |
| `views/employees.py:746` | `/test` | GET | `test` | — |
| `views/obras.py:44` | `/obras` | GET | `obras` | — |
| `views/obras.py:1361` | `/obras/<int:id>` | GET | `detalhes_obra` | capture_db_errors |
| `views/rdo.py:924` | `/rdo/<int:id>` | GET | `visualizar_rdo` | — |

### TOKEN (legítimo)

| Arquivo:linha | Rota | Métodos | Handler | Outros decorators |
|---|---|---|---|---|
| `portal_obras_views.py:80` | `/obra/<token>` | GET | `portal_obra` | — |
| `portal_obras_views.py:344` | `/obra/<token>/compra/<int:compra_id>/aprovar` | POST | `aprovar_compra` | — |
| `portal_obras_views.py:378` | `/obra/<token>/compra/<int:compra_id>/recusar` | POST | `recusar_compra` | — |
| `portal_obras_views.py:389` | `/obra/<token>/compra/<int:compra_id>/comprovante` | POST | `upload_comprovante` | — |
| `portal_obras_views.py:433` | `/obra/<token>/mapa/<int:mapa_id>/aprovar` | POST | `aprovar_mapa_concorrencia` | — |
| `portal_obras_views.py:547` | `/obra/<token>/mapa-v2/<int:mapa_id>/selecionar` | POST | `selecionar_mapa_v2` | — |
| `portal_obras_views.py:619` | `/obra/<token>/mapa-v2/<int:mapa_id>/relatorio/<int:rel_id>/baixar` | GET | `baixar_relatorio_mapa_v2_portal` | — |
| `portal_obras_views.py:639` | `/obra/<token>/rdo/<int:rdo_id>` | GET | `portal_rdo_detalhe` | — |
| `propostas_consolidated.py:2454` | `/cliente/<token>` | GET | `portal_cliente` | — |
| `propostas_consolidated.py:2504` | `/cliente/<token>/aprovar` | POST | `aprovar_proposta_cliente` | — |
| `propostas_consolidated.py:2588` | `/cliente/<token>/rejeitar` | POST | `rejeitar_proposta_cliente` | — |

## Rotas por blueprint

| Blueprint | Rotas |
|---|---:|
| `main_bp` | 120 |
| `almoxarifado_bp` | 37 |
| `propostas_bp` | 35 |
| `cronograma_bp` | 34 |
| `ponto_bp` | 33 |
| `catalogos_bp` | 31 |
| `orcamentos_bp` | 26 |
| `catalogo_bp` | 25 |
| `contabilidade_bp` | 24 |
| `importacao_bp` | 23 |
| `financeiro_bp` | 22 |
| `configuracoes_bp` | 22 |
| `crm_bp` | 22 |
| `folha_bp` | 18 |
| `equipe_bp` | 16 |
| `alimentacao_bp` | 14 |
| `frota_bp` | 13 |
| `rdo_crud_bp` | 13 |
| `gestao_custos_bp` | 12 |
| `custos_escritorio_bp` | 12 |
| `medicao_bp` | 12 |
| `cronograma_importacao_bp` | 12 |
| `portal_obras_bp` | 10 |
| `cadastros_hub_bp` | 8 |
| `custos_bp` | 8 |
| `compras_bp` | 8 |
| `planejamento_custos_bp` | 8 |
| `transporte_bp` | 7 |
| `metricas_bp` | 7 |
| `subempreiteiros_bp` | 6 |
| `exportacao_bp` | 6 |
| `production_bp` | 6 |
| `api_organizer` | 5 |
| `clientes_bp` | 5 |
| `servico_obra_real_bp` | 5 |
| `dashboards_bp` | 5 |
| `categorias_bp` | 5 |
| `api_servicos_obra_bp` | 4 |
| `reembolso_bp` | 4 |
| `quick_create_bp` | 4 |
| `catalogo_legacy_bp` | 4 |
| `analytics_bp` | 3 |
| `rdo_editar_bp` | 3 |
| `financeiros_bp` | 3 |
| `app` | 3 |
| `api_funcionarios_bp` | 3 |
| `manual_bp` | 3 |
| `orcamento_operacional_bp` | 3 |
| `health_bp` | 2 |
| `vinculos_audit_bp` | 2 |
| `relatorios_bp` | 2 |
| `catalogo_api_bp` | 2 |
| `cadastrar_servico_bp` | 1 |
| `landing_bp` | 1 |
| `api_buscar_funcionarios_bp` | 1 |
| `dev_bp` | 1 |
