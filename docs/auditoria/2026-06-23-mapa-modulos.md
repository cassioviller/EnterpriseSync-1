INFO:app:[ENV] Ambiente detectado: DESENVOLVIMENTO (Replit)
INFO:app:[OK] Secret key configurada (length: 88)
INFO:app:[INFO] [DEV] Configurações de cookie padrão para desenvolvimento
INFO:app:[CONFIG] PRODUÇÃO DATABASE: postgresql://postgres:****@helium/heliumdb?sslmode=disable
INFO:root:[OK] Todos os modelos importados do arquivo consolidado
INFO:event_manager:📝 Handler lancar_custo_material_obra registrado para evento 'material_saida'
INFO:event_manager:📝 Handler criar_conta_pagar_entrada_material registrado para evento 'material_entrada'
INFO:event_manager:📝 Handler calcular_horas_folha registrado para evento 'ponto_registrado'
INFO:event_manager:📝 Handler lancar_custo_combustivel registrado para evento 'veiculo_usado'
INFO:event_manager:📝 Handler lancar_custos_rdo registrado para evento 'rdo_finalizado'
INFO:event_manager:📝 Handler propagar_proposta_para_obra registrado para evento 'proposta_aprovada'
INFO:event_manager:📝 Handler criar_lancamento_folha_pagamento registrado para evento 'folha_processada'
INFO:event_manager:📝 Handler criar_conta_pagar_alimentacao registrado para evento 'alimentacao_lancamento_criado'
INFO:event_manager:📝 Handler recalcular_medicao_apos_rdo registrado para evento 'rdo_finalizado'
INFO:event_manager:✅ Event Manager inicializado - 8 eventos registrados
INFO:root:[OK] Event Manager inicializado - 8 eventos registrados
WARNING:root:[WARN] Handler de folha não carregado: No module named 'handlers.folha_handlers'
INFO:event_manager:📝 Handler handle_proposta_aprovada registrado para evento 'proposta_aprovada'
INFO:root:[OK] Handler de propostas comerciais registrado
INFO:event_manager:📝 Handler handle_nota_fiscal_paga registrado para evento 'nota_fiscal_paga'
INFO:root:[OK] Handler de financeiro registrado
INFO:event_manager:📝 Handler webhook_emit_obra_concluida registrado para evento 'obra.concluida'
INFO:event_manager:📝 Handler webhook_emit_obra_cronograma_atualizado registrado para evento 'obra.cronograma_atualizado'
INFO:event_manager:📝 Handler webhook_emit_obra_medicao_publicada registrado para evento 'obra.medicao_publicada'
INFO:event_manager:📝 Handler webhook_emit_obra_rdo_publicado registrado para evento 'obra.rdo_publicado'
INFO:event_manager:📝 Handler webhook_emit_proposta_aprovada registrado para evento 'proposta.aprovada'
INFO:event_manager:📝 Handler webhook_emit_proposta_enviada registrado para evento 'proposta.enviada'
INFO:event_manager:📝 Handler webhook_emit_proposta_expirando registrado para evento 'proposta.expirando'
INFO:event_manager:📝 Handler webhook_emit_proposta_rejeitada registrado para evento 'proposta.rejeitada'
INFO:utils.webhook_dispatcher:[webhook] 8 listener(s) universal(is) registrados na allowlist
INFO:root:[OK] Despachante de webhook (n8n) inicializado
INFO:views.helpers:[OK] MÓDULO ENCONTRADO: utils.idempotency (Utilitários de idempotência)
INFO:views.helpers:[OK] MÓDULO ENCONTRADO: utils.circuit_breaker (Circuit breakers para resiliência)
INFO:views.helpers:[OK] MÓDULO ENCONTRADO: utils.saga (Padrão SAGA para transações)
INFO:views.helpers:[OK] MÓDULO ENCONTRADO: migrations (Sistema de migrações automáticas)
INFO:views.helpers:[OK] MÓDULO ENCONTRADO: models (Modelos do banco de dados)
INFO:views.helpers:[OK] MÓDULO ENCONTRADO: auth (Sistema de autenticação)
INFO:views.helpers:[STATS] RESUMO: 6 encontrados, 0 faltando
INFO:views.helpers:[OK] Utilitários de resiliência importados com sucesso
INFO:utils.circuit_breaker:🔌 Circuit Breaker 'database_heavy_query' inicializado - threshold=2, timeout=60s
INFO:utils.circuit_breaker:🔌 Circuit Breaker 'pdf_generation' inicializado - threshold=3, timeout=120s
INFO:utils.circuit_breaker:🔌 Circuit Breaker 'veiculo_list_query' inicializado - threshold=3, timeout=60s
INFO:views.vehicles:[OK] [VEICULOS] Services importados com sucesso
INFO:root:[OK] Blueprint almoxarifado registrado
INFO:root:[OK] Blueprint clientes (cadastros) registrado
INFO:root:[OK] Blueprint CRM de Leads registrado
INFO:root:[OK] Blueprint Manual do Usuário registrado
INFO:root:[OK] Blueprint dev_tools (mobile preview) registrado
INFO:ponto_views:🔄 Pré-carregando modelo SFace diretamente...
INFO:ponto_views:🚀 Iniciando pré-carregamento assíncrono do modelo DeepFace + cache facial
INFO:root:[OK] Blueprint ponto eletrônico registrado
INFO:root:[OK] Blueprint ServicoObraReal registrado
INFO:root:Database tables created/verified
2026-06-23 11:24:26.458150: I external/local_xla/xla/tsl/cuda/cudart_stub.cc:31] Could not find cuda drivers on your machine, GPU will not be used.
2026-06-23 11:24:26.458690: I tensorflow/core/util/port.cc:153] oneDNN custom operations are on. You may see slightly different numerical results due to floating-point round-off errors from different computation orders. To turn them off, set the environment variable `TF_ENABLE_ONEDNN_OPTS=0`.
2026-06-23 11:24:26.516385: I tensorflow/core/platform/cpu_feature_guard.cc:210] This TensorFlow binary is optimized to use available CPU instructions in performance-critical operations.
To enable the following instructions: AVX2 AVX512F AVX512_VNNI AVX512_BF16 AVX512_FP16 AVX_VNNI FMA, in other operations, rebuild TensorFlow with the appropriate compiler flags.
INFO:models:[seed-demo-alfa] auto-seed iniciado em background (log: /tmp/sige_seed_demo_alfa.log)
INFO:models:[SYNC] Executando migrações automáticas do banco de dados...
INFO:migrations:================================================================================
INFO:migrations:🚀 SISTEMA DE MIGRAÇÕES v2.0 - RASTREAMENTO ATIVO
INFO:migrations:================================================================================
INFO:migrations:🎯 DATABASE: postgresql://postgres:****@helium/heliumdb?sslmode=disable
INFO:migrations:📋 Inicializando sistema de rastreamento...
INFO:migrations:✅ Migrações aposentadas marcadas no histórico (idempotente)
INFO:migrations:⚡ Carregando cache de migrações já aplicadas...
INFO:migrations:🔄 Verificando migrações pendentes...
INFO:migrations:📋 159/159 já aplicadas — 0 pendentes
INFO:migrations:================================================================================
INFO:migrations:📊 RESUMO DAS MIGRAÇÕES
INFO:migrations:================================================================================
INFO:migrations:✅ Executadas: 0
INFO:migrations:⏭️  Puladas (já aplicadas): 159
INFO:migrations:❌ Falhas: 0
INFO:migrations:📝 Total processadas: 159
INFO:migrations:================================================================================
INFO:migrations:✅ Todas as migrações foram processadas com sucesso!
INFO:migrations:================================================================================
INFO:models:[OK] Migrações executadas com sucesso!
INFO:fix_all_admin_id_universal:====================================================================================================
INFO:fix_all_admin_id_universal:🔧 AUTO-FIX UNIVERSAL: Verificando TODAS as tabelas para admin_id...
INFO:fix_all_admin_id_universal:====================================================================================================
INFO:fix_all_admin_id_universal:====================================================================================================
INFO:fix_all_admin_id_universal:📊 RESUMO DO AUTO-FIX UNIVERSAL
INFO:fix_all_admin_id_universal:====================================================================================================
INFO:fix_all_admin_id_universal:✅ Tabelas já OK: 169
INFO:fix_all_admin_id_universal:➕ Tabelas corrigidas: 0
INFO:fix_all_admin_id_universal:❌ Tabelas com erro: 0
INFO:fix_all_admin_id_universal:📊 Total verificadas: 169
INFO:fix_all_admin_id_universal:====================================================================================================
INFO:fix_all_admin_id_universal:✅ AUTO-FIX UNIVERSAL CONCLUÍDO COM SUCESSO!
INFO:fix_all_admin_id_universal:====================================================================================================
WARNING:models:[WARN] Migration de limpeza de veículos não disponível
INFO:root:[OK] Blueprint folha de pagamento registrado
INFO:root:[OK] Blueprint contabilidade registrado
INFO:root:[OK] Blueprint financeiro v9.0 registrado
INFO:root:[OK] Blueprint custos v9.0 registrado
INFO:root:[OK] Blueprint gestao_custos V2 registrado
INFO:root:[OK] Blueprint orcamentos registrado
INFO:root:[OK] Blueprint alimentação registrado
INFO:propostas_consolidated:[OK] Propostas - Utilitários de resiliência importados
INFO:utils.circuit_breaker:🔌 Circuit Breaker 'propostas_list_query' inicializado - threshold=3, timeout=60s
INFO:propostas_consolidated:[OK] Propostas Consolidated Blueprint carregado com padrões de resiliência
INFO:root:[OK] Blueprint propostas consolidado registrado
INFO:root:[OK] Blueprint CATALOGO (insumos+composicao+orcamento) registrado
INFO:root:[OK] Blueprint API organizer registrado
INFO:root:[OK] Blueprint categorias de serviços registrado
INFO:root:[OK] Blueprint configurações registrado
INFO:root:[OK] Blueprint API serviços obra LIMPA registrado
INFO:root:[OK] Blueprint EQUIPE (gestão lean) registrado
INFO:frota_views:[OK] [FROTA] Services importados com sucesso
INFO:root:[OK] Blueprint FROTA registrado
INFO:root:[OK] Blueprint COMPRAS registrado
INFO:root:[OK] Blueprint TRANSPORTE registrado
INFO:root:[OK] Blueprint CRONOGRAMA registrado
INFO:root:[OK] Blueprint VINCULOS_AUDIT (Task #62) registrado
INFO:root:[OK] Auto-link listener (Task #62) instalado
INFO:root:[OK] Blueprint SUBEMPREITEIROS registrado
INFO:root:[OK] Blueprint REEMBOLSOS V2 registrado
INFO:root:[OK] Blueprint landing page registrado
INFO:root:[OK] Blueprint planejamento_custos registrado
INFO:root:[OK] Blueprint METRICAS (Task #3) registrado
INFO:root:[LOCK] Sistema de bypass PERMANENTEMENTE desabilitado - admin_id consistente
INFO:root:[OK] Comando CLI diagnosticar-fotos-faciais registrado
INFO:root:[OK] Comando CLI init-planejamento-custos registrado
INFO:root:[OK] Comando CLI emitir-propostas-expirando registrado
INFO:root:[OK] Comando CLI cobertura-ociosa registrado
WARNING:root:[WARN] APScheduler não iniciado: No module named 'apscheduler'
INFO:root:[OK] CSRF exempt: main
INFO:root:[OK] CSRF exempt: api_organizer
INFO:root:[OK] CSRF exempt: api_servicos_obra_limpa
INFO:root:[OK] CSRF exempt: ponto
INFO:root:[OK] CSRF exempt: landing
INFO:root:[OK] CSRF exempt: servico_obra_real
INFO:root:[OK] CSRF exempt: production
INFO:root:[OK] CSRF exempt: relatorios
INFO:root:[OK] CSRF exempt: almoxarifado
INFO:root:[OK] CSRF exempt: alimentacao
INFO:root:[OK] CSRF exempt: folha
INFO:root:[OK] CSRF exempt: contabilidade
INFO:root:[OK] CSRF exempt: financeiro
INFO:root:[OK] CSRF exempt: custos
INFO:root:[OK] CSRF exempt: propostas
INFO:root:[OK] CSRF exempt: configuracoes
INFO:root:[OK] CSRF exempt: categorias_servicos
INFO:root:[OK] CSRF exempt: equipe
INFO:root:[OK] CSRF exempt: frota
INFO:root:[OK] CSRF exempt: orcamentos
# Blueprints registrados ( 37 )
- alimentacao  <-  alimentacao_views
- almoxarifado  <-  views.almoxarifado
- api_organizer  <-  api_organizer
- api_servicos_obra_limpa  <-  api_servicos_obra_limpa
- catalogo  <-  views.catalogo_views
- catalogo_api  <-  views.catalogo_views
- catalogo_legacy  <-  views.catalogo_views
- categorias_servicos  <-  categoria_servicos
- clientes  <-  clientes_views
- compras  <-  compras_views
- configuracoes  <-  configuracoes_views
- contabilidade  <-  contabilidade_views
- crm  <-  crm_views
- cronograma  <-  cronograma_views
- custos  <-  custos_views
- dev  <-  views.dev_views
- equipe  <-  equipe_views
- financeiro  <-  financeiro_views
- folha  <-  folha_pagamento_views
- frota  <-  frota_views
- gestao_custos  <-  gestao_custos_views
- landing  <-  landing_views
- main  <-  views
- manual  <-  views.manual_views
- metricas  <-  views.metricas_views
- orcamento_operacional  <-  views.orcamento_operacional_views
- orcamentos  <-  views.orcamentos_views
- planejamento_custos  <-  views.planejamento_custos_views
- ponto  <-  ponto_views
- production  <-  production_routes
- propostas  <-  propostas_consolidated
- reembolso  <-  reembolso_views
- relatorios  <-  relatorios_funcionais
- servico_obra_real  <-  crud_servico_obra_real
- subempreiteiros  <-  subempreiteiros_views
- transporte  <-  transporte_views
- vinculos_audit  <-  vinculos_audit_views

# Módulos *_views candidatos vs vivos
- alimentacao_views: VIVO
- cadastros_views: INCERTO/sem blueprint registrado
- clientes_views: VIVO
- compras_views: VIVO
- configuracoes_views: VIVO
- contabilidade_views: VIVO
- crm_views: VIVO
- cronograma_views: VIVO
- custos_escritorio_views: INCERTO/sem blueprint registrado
- custos_views: VIVO
- equipe_views: VIVO
- financeiro_views: VIVO
- folha_pagamento_views: VIVO
- frota_views: VIVO
- gestao_custos_views: VIVO
- importacao_views: INCERTO/sem blueprint registrado
- landing_views: VIVO
- medicao_views: INCERTO/sem blueprint registrado
- ponto_views: VIVO
- portal_obras_views: INCERTO/sem blueprint registrado
- reembolso_views: VIVO
- subempreiteiros_views: VIVO
- transporte_views: VIVO
- views.admin: INCERTO/sem blueprint registrado
- views.api: INCERTO/sem blueprint registrado
- views.auth: INCERTO/sem blueprint registrado
- views.catalogo_views: VIVO
- views.catalogos_views: INCERTO/sem blueprint registrado
- views.dashboard: INCERTO/sem blueprint registrado
- views.dev_views: VIVO
- views.employees: INCERTO/sem blueprint registrado
- views.helpers: INCERTO/sem blueprint registrado
- views.manual_views: VIVO
- views.metricas_views: VIVO
- views.obras: INCERTO/sem blueprint registrado
- views.orcamento_operacional_views: VIVO
- views.orcamentos_views: VIVO
- views.planejamento_custos_views: VIVO
- views.quick_create_views: INCERTO/sem blueprint registrado
- views.rdo: INCERTO/sem blueprint registrado
- views.users: INCERTO/sem blueprint registrado
- views.vehicles: INCERTO/sem blueprint registrado
- vinculos_audit_views: VIVO

## Veredito final (por análise de import-graph + template)
- cadastros_views: VIVO — importado em: main.py 
- custos_escritorio_views: VIVO — importado em: main.py 
- importacao_views: VIVO — importado em: main.py tests/conftest.py tests/test_endpoint_classificar_termo.py views/almoxarifado/fornecedores.py 
- medicao_views: VIVO — importado em: main.py 
- portal_obras_views: VIVO — importado em: main.py 
- views.admin: VIVO — importado em: views/__init__.py 
- views.api: VIVO — importado em: views/__init__.py 
- views.auth: VIVO — importado em: views/__init__.py 
- views.catalogos_views: VIVO — importado em: main.py tests/conftest.py tests/test_catalogos_palavras_chave.py 
- views.dashboard: VIVO — importado em: views/__init__.py 
- views.employees: VIVO — importado em: views/__init__.py 
- views.helpers: VIVO — importado em: importacao_views.py views/dashboard.py views/__init__.py views/vehicles.py views/rdo.py views/employees.py views/obras.py views/api.py 
- views.obras: VIVO — importado em: views/__init__.py 
- views.quick_create_views: VIVO — importado em: main.py 
- views.rdo: VIVO — importado em: views/__init__.py 
- views.users: VIVO — importado em: views/__init__.py 
- views.vehicles: VIVO — importado em: views/__init__.py 

## CONCLUSÃO
Nenhum módulo `*_views.py` (topo) nem do pacote `views/` está morto — todos são
importados por `main.py` ou `views/__init__.py`. A coexistência flat vs pacote é dívida
arquitetural (migração pela metade), mas **não há código de view morto a remover**.
→ Task 10 do plano = NO-OP. A consolidação flat→pacote fica registrada como risco de
manutenção (fora do escopo desta passada, ver RELATORIO seção F).
