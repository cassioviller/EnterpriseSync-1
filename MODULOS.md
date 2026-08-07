# Mapa de módulos ativos

> Documento vivo. Última atualização: **2026-07-30**.
> Fonte: `scripts/auditoria_mapa_modulos.py` + leitura de `app.py` e `main.py`.
> Linhas de registro citadas valem para o commit da data acima — podem derivar.

## Como este mapa é levantado (e sua pegadinha)

```bash
python scripts/auditoria_mapa_modulos.py
```

O script importa **só `app.py`** e enxerga 37 blueprints. Mas o entrypoint real
é o **`main.py`**, que registra **mais 21** — tudo que o script marca como
"INCERTO/sem blueprint registrado" está, na verdade, vivo e registrado lá
(portal, medição, importação, RDO, quick-create, hub de cadastros…).

**Ao atualizar este documento:** rode o script E confira os
`register_blueprint` do `main.py` (`grep -n register_blueprint main.py`).
Melhoria pendente: fazer o script importar `main` em vez de `app`, para a
auditoria parar de dar falso "morto".

A seção **"Rastreio por módulo"** (entre os marcadores `RASTREIO:INICIO/FIM`)
é gerada por outro script — **não edite à mão**:

```bash
python scripts/rastreio_modulos.py
```

Ele reescreve só o miolo entre os marcadores, preservando as marcas de
`Conferência:` já preenchidas. Blueprint novo? Adicione no dicionário
`MODULOS` do script E nas tabelas manuais acima.

**Total em 30/07/2026: 58 blueprints** (37 em `app.py` + 21 em `main.py`).

---

## Núcleo operacional (obra)

| Módulo | Blueprint | Arquivo | Registro |
|---|---|---|---|
| Obras + Dashboard + base | `main` | `views/__init__.py` (agrega `auth`, `dashboard`, `users`, `employees`, `obras`, `vehicles`, `rdo`, `api`, `admin`) | `app.py:503` |
| RDO — edição | `rdo_editar` | `rdo_editar_sistema.py` | `main.py:11` |
| RDO — CRUD completo | `rdo_crud` | `crud_rdo_completo.py` | `main.py:25` |
| Cronograma (editor, apontamentos) | `cronograma` | `cronograma_views.py` | `app.py:895` |
| Cronograma — importação `.mpp` | `cronograma_importacao` | `views/cronograma_importacao.py` | `main.py:268` |
| Portal do cliente (+ ciência de RDO) | `portal_obras` | `portal_obras_views.py` | `main.py:177` |
| Medição | `medicao` | `medicao_views.py` | `main.py:184` |
| Importação (inclui físico-financeiro) | `importacao` | `importacao_views.py` | `main.py:193` |

## Pessoas

| Módulo | Blueprint | Arquivo | Registro |
|---|---|---|---|
| Equipe | `equipe` | `equipe_views.py` | `app.py:855` |
| Funcionários (API) | `api_funcionarios` | `api_funcionarios.py` | `main.py:107` |
| Ponto | `ponto` | `ponto_views.py` | `app.py:494` |
| Folha de pagamento | `folha` (`/folha`) | `folha_pagamento_views.py` | `app.py:729` |
| Alimentação | `alimentacao` | `alimentacao_views.py` | `app.py:782` |
| Reembolso | `reembolso` | `reembolso_views.py` | `app.py:933` |
| Subempreiteiros | `subempreiteiros` | `subempreiteiros_views.py` | `app.py:923` |

## Financeiro / custos

| Módulo | Blueprint | Arquivo | Registro |
|---|---|---|---|
| Financeiro | `financeiro` | `financeiro_views.py` | `app.py:744` |
| Relatórios financeiros avançados | `financeiros` | `relatorios_financeiros_avancados.py` | `main.py:166` |
| Contabilidade | `contabilidade` (`/contabilidade`) | `contabilidade_views.py` | `app.py:736` |
| Custos de obra | `custos` | `custos_views.py` | `app.py:752` |
| Gestão de custos | `gestao_custos` | `gestao_custos_views.py` | `app.py:760` |
| Custos de escritório | `custos_escritorio` | `custos_escritorio_views.py` | `main.py:250` |
| Planejamento de custos | `planejamento_custos` | `views/planejamento_custos_views.py` | `app.py:951` |

## Comercial

| Módulo | Blueprint | Arquivo | Registro |
|---|---|---|---|
| CRM | `crm` | `crm_views.py` | `app.py:470` |
| Clientes | `clientes` | `clientes_views.py` | `app.py:462` |
| Propostas | `propostas` (`/propostas`) | `propostas_consolidated.py` | `app.py:795` |
| Orçamentos | `orcamentos` | `views/orcamentos_views.py` | `app.py:768` |
| Orçamento operacional | `orcamento_operacional` | `views/orcamento_operacional_views.py` | `app.py:772` |
| Catálogo de serviços | `catalogo`, `catalogo_api` (`/api/catalogo/*`), `catalogo_legacy` (aliases `/propostas/*`, `/medicao/obra/*`) | `views/catalogo_views.py` | `app.py:805-807` |
| Categorias de serviços | `categorias_servicos` | `categoria_servicos.py` | `app.py:823` |
| Serviço da obra (real) | `servico_obra_real` | `crud_servico_obra_real.py` | `app.py:509` |
| Serviços da obra (API) | `api_servicos_obra_limpa` | `api_servicos_obra_limpa.py` | `app.py:845` |
| Cadastrar serviço na obra | `cadastrar_servico` | `cadastrar_servico_obra.py` | `main.py:126` |

## Suprimentos / logística

| Módulo | Blueprint | Arquivo | Registro |
|---|---|---|---|
| Almoxarifado | `almoxarifado` | `views/almoxarifado.py` | `app.py:455` |
| Compras | `compras` | `compras_views.py` | `app.py:875` |
| Frota | `frota` | `frota_views.py` | `app.py:865` |
| Transporte | `transporte` | `transporte_views.py` | `app.py:885` |

## Transversais

| Módulo | Blueprint | Arquivo | Registro |
|---|---|---|---|
| Relatórios | `relatorios` (`/relatorios`) | `relatorios_funcionais.py` | `app.py:449` |
| Exportação de relatórios | `exportacao` | `exportacao_relatorios.py` | `main.py:158` |
| Analytics preditivos | `analytics` | `analytics_preditivos.py` | `main.py:138` |
| Dashboards específicos | `dashboards` | `dashboards_especificos.py` | `main.py:150` |
| Métricas | `metricas` | `views/metricas_views.py` | `app.py:959` |
| Configurações | `configuracoes` | `configuracoes_views.py` | `app.py:835` |
| Hub de cadastros | `cadastros_hub` | `cadastros_views.py` | `main.py:290` |
| Quick-create | `quick_create` | `views/quick_create_views.py` | `main.py:281` |
| Catálogos (views) | `catalogos` | `views/catalogos_views.py` | `main.py:259` |
| API organizer | `api_organizer` | `api_organizer.py` | `app.py:815` |
| Auditoria de vínculos | `vinculos_audit` | `vinculos_audit_views.py` | `app.py:905` |
| Manual do usuário | `manual` | `views/manual_views.py` | `app.py:478` |
| Landing page | `landing` | `landing_views.py` | `app.py:943` |
| Dev | `dev` | `views/dev_views.py` | `app.py:486` |
| Produção | `production` (`/prod`) | `production_routes.py` | `app.py:504` |

---

## Ativação: tudo ligado para todos, exceto flags

Não há sistema de módulos por tenant — os 58 blueprints ficam ativos para
todo mundo. O que existe de condicional são **feature flags por tenant**, em
colunas booleanas de `ConfiguracaoEmpresa` (`models.py`), ligadas por script:

| Flag | Coluna / migração | Script | O que liga |
|---|---|---|---|
| Editor de cronograma v2 | `configuracao_empresa.cronograma_editor_v2` (migração 222, default FALSE) | `scripts/flag_cronograma_editor_v2.py <admin_id> --ligar/--desligar/--status` | Motor novo: multi-predecessoras via `tarefa_vinculo`, caminho crítico, recálculo em cascata. OFF = engine antigo byte-idêntico. Atenção: motor novo usa calendário fixo seg–sex. |
| RDO percentual livre | `configuracao_empresa.rdo_percentual_livre` (migração 226, default FALSE) | `scripts/flag_rdo_percentual_livre.py` | Percentual livre no apontamento do RDO (spec `docs/superpowers/specs/2026-07-24-rdo-percentual-livre-design.md`). |

---

## Candidatos a código morto

**Nenhum no momento (30/07/2026).** Tudo que a auditoria marcou como
"INCERTO" está registrado no `main.py` ou agregado ao `main_bp` pelo
`views/__init__.py`. Se um candidato real aparecer numa rodada futura,
listar aqui com a evidência antes de remover.

---

<!-- RASTREIO:INICIO -->
## Rastreio por módulo — campos, funcionalidades e integração

> **Gerado por `python scripts/rastreio_modulos.py`** (análise estática:
> AST de `models.py` + regex de `@bp.route` + varredura de uso de modelos
> por arquivo de view). Não edite esta seção à mão — rode o script.
> Números desta geração: **184 modelos**, **755 rotas**.
> "Modelos próprios" = referenciados por até 2 módulos; o resto aparece em
> "compartilhados" — onde mora a integração, e o risco na conferência.
> A marca `Conferência:` de cada módulo é manual e **sobrevive à regeração**.

### Entidades centrais (campos completos)

FK indicada com `→tabela`.

**Obra** (`obra`, 31 colunas, usada por 36 módulos):
`id`, `nome`, `codigo`, `endereco`, `data_inicio`, `data_previsao_fim`, `orcamento`, `valor_contrato`, `fluxo_caixa_planilha`, `area_total_m2`, `status`, `estado`, `responsavel_id→funcionario`, `token_cliente`, `token_cliente_expira_em`, `cliente_id→cliente`, `proposta_origem_id→propostas_comerciais`, `portal_ativo`, `ultima_visualizacao_cliente`, `ativo`, `admin_id→usuario`, `created_at`, `data_inicio_medicao`, `valor_entrada`, `data_entrada`, `percentual_administracao`, `regime_medicao`, `cronograma_revisado_em`, `latitude`, `longitude`, `raio_geofence_metros`

**Funcionario** (`funcionario`, 25 colunas, usada por 22 módulos):
`id`, `codigo`, `nome`, `cpf`, `rg`, `data_nascimento`, `endereco`, `telefone`, `email`, `data_admissao`, `salario`, `jornada_semanal`, `ativo`, `foto`, `foto_base64`, `departamento_id→departamento`, `funcao_id→funcao`, `horario_trabalho_id→horario_trabalho`, `admin_id→usuario`, `created_at`, `tipo_remuneracao`, `valor_diaria`, `chave_pix`, `valor_va`, `valor_vt`

**Usuario** (`usuario`, 11 colunas, usada por 8 módulos):
`id`, `username`, `email`, `password_hash`, `nome`, `ativo`, `tipo_usuario`, `admin_id→usuario`, `funcionario_id→funcionario`, `created_at`, `versao_sistema`

**RDO** (`rdo`, 21 colunas, usada por 10 módulos):
`id`, `numero_rdo`, `data_relatorio`, `obra_id→obra`, `criado_por_id→usuario`, `admin_id→usuario`, `clima_geral`, `temperatura_media`, `umidade_relativa`, `vento_velocidade`, `precipitacao`, `condicoes_trabalho`, `observacoes_climaticas`, `local`, `comentario_geral`, `status`, `estado`, `rdo_retificado_id→rdo`, `motivo_retificacao`, `created_at`, `updated_at`

**CustoObra** (`custo_obra`, 18 colunas, usada por 6 módulos):
`id`, `obra_id→obra`, `centro_custo_id→centro_custo`, `tipo`, `descricao`, `valor`, `data`, `created_at`, `funcionario_id→funcionario`, `item_almoxarifado_id→almoxarifado_item`, `veiculo_id→frota_veiculo`, `admin_id→usuario`, `quantidade`, `valor_unitario`, `horas_trabalhadas`, `horas_extras`, `rdo_id→rdo`, `categoria`

**TarefaCronograma** (`tarefa_cronograma`, 30 colunas, usada por 10 módulos):
`id`, `obra_id→obra`, `tarefa_pai_id→tarefa_cronograma`, `predecessora_id→tarefa_cronograma`, `ordem`, `nome_tarefa`, `duracao_dias`, `data_inicio`, `data_fim`, `quantidade_total`, `unidade_medida`, `modo_apontamento`, `subatividade_mestre_id→subatividade_mestre`, `servico_id→servico`, `percentual_concluido`, `responsavel`, `data_entrega_real`, `admin_id→usuario`, `is_cliente`, `gerada_por_proposta_item_id→proposta_itens`, `mpp_uid`, `wbs_codigo`, `fingerprint`, `is_marco`, `ativa`, `arquivada_em`, `versao_criacao_id→cronograma_versao`, `is_critica`, `folga_dias`, `created_at`

**Servico** (`servico`, 18 colunas, usada por 10 módulos):
`id`, `nome`, `descricao`, `categoria`, `unidade_medida`, `unidade_simbolo`, `custo_unitario`, `complexidade`, `requer_especializacao`, `ativo`, `imposto_pct`, `margem_lucro_pct`, `preco_venda_unitario`, `template_padrao_id→cronograma_template`, `tipo_medicao`, `admin_id→usuario`, `created_at`, `updated_at`

**Cliente** (`cliente`, 8 colunas, usada por 8 módulos):
`id`, `nome`, `email`, `telefone`, `endereco`, `cnpj`, `admin_id→usuario`, `created_at`

**Proposta** (`propostas_comerciais`, 47 colunas, usada por 6 módulos):
`id`, `numero`, `data_proposta`, `cliente_id→cliente`, `cliente_nome`, `cliente_telefone`, `cliente_email`, `cliente_endereco`, `titulo`, `descricao`, `documentos_referencia`, `prazo_entrega_dias`, `observacoes_entrega`, `validade_dias`, `percentual_nota_fiscal`, `bdi_ac_pct`, `bdi_seguro_pct`, `bdi_risco_pct`, `bdi_garantia_pct`, `bdi_desp_financeiras_pct`, `condicoes_pagamento`, `garantias`, `consideracoes_gerais`, `itens_inclusos`, `itens_exclusos`, `status`, `token_cliente`, `data_envio`, `data_resposta_cliente`, `observacoes_cliente`, `valor_total`, `criado_por→usuario`, `admin_id→usuario`, `criado_em`, `atualizado_em`, `obra_id→obra`, `convertida_em_obra`, `orcamento_id→orcamento`, `engenheiro_id→engenheiro_responsavel`, `cronograma_default_json`, `versao`, `proposta_origem_id→propostas_comerciais`, `substituida_por_id→propostas_comerciais`, `substituida_em`, `observacao_validacao`, `proposta_template_id→proposta_templates`, `campos_pendentes_revisao`

**RegistroPonto** (`registro_ponto`, 30 colunas, usada por 4 módulos):
`id`, `funcionario_id→funcionario`, `obra_id→obra`, `data`, `hora_entrada`, `hora_saida`, `hora_almoco_saida`, `hora_almoco_retorno`, `tipo_local`, `horas_trabalhadas`, `horas_extras`, `minutos_atraso_entrada`, `minutos_atraso_saida`, `total_atraso_minutos`, `total_atraso_horas`, `meio_periodo`, `saida_antecipada`, `tipo_registro`, `percentual_extras`, `observacoes`, `created_at`, `updated_at`, `foto_registro_base64`, `reconhecimento_facial_sucesso`, `confianca_reconhecimento`, `modelo_utilizado`, `latitude`, `longitude`, `distancia_obra_metros`, `admin_id→usuario`

---

### Obras/Dashboard/base (main)

Arquivos: `views/__init__.py`, `views/auth.py`, `views/dashboard.py`, `views/users.py`, `views/employees.py`, `views/obras.py`, `views/vehicles.py`, `views/rdo.py`, `views/api.py`, `views/admin.py`
Conferência: ☐ pendente

**Funcionalidades (124 rotas):**

| Rota | Métodos | Função |
|---|---|---|
| `/login` | GET,POST | `login` |
| `/logout` | GET | `logout` |
| `/` | GET | `index` |
| `/health` | GET | `health_check` |
| `/health/veiculos` | GET | `health_check_veiculos` |
| `/dashboard` | GET | `dashboard` |
| `/usuarios` | GET | `usuarios` |
| `/usuarios/novo` | GET,POST | `novo_usuario` |
| `/usuarios/<int:user_id>/editar` | GET,POST | `editar_usuario` |
| `/funcionarios` | GET,POST | `funcionarios` |
| `/funcionario_perfil/<int:id>` | GET | `funcionario_perfil` |
| `/funcionarios/<int:funcionario_id>/horario-padrao` | GET | `funcionario_horario_padrao` |
| `/funcionario_perfil/<int:id>/pdf` | GET | `funcionario_perfil_pdf` |
| `/funcionario-dashboard` | GET | `funcionario_dashboard` |
| `/obras` | GET | `obras` |
| `/obras/nova` | GET,POST | `nova_obra` |
| `/obras/editar/<int:id>` | GET,POST | `editar_obra` |
| `/obras/excluir/<int:id>` | POST,GET | `excluir_obra` |
| `/obras/toggle-status/<int:id>` | POST | `toggle_status_obra` |
| `/api/obra/<int:obra_id>/toggle-ativo` | POST | `toggle_ativo_obra_api` |
| `/obras/<int:id>/trocar-cliente` | POST | `trocar_cliente_obra` |
| `/obras/<int:id>` | GET | `detalhes_obra` |
| `/obras/detalhes/<int:id>` | GET | `detalhes_obra` |
| `/obras/<int:id>/financeiro/dados` | GET | `financeiro_dados` |
| `/obras/<int:id>/financeiro/config` | POST | `financeiro_config` |
| `/obras/<int:id>/financeiro/etapa/<int:osc_id>/itens` | POST | `financeiro_etapa_itens` |
| `/obras/<int:id>/financeiro/etapa/<int:osc_id>/lancamentos` | GET | `financeiro_etapa_lancamentos` |
| `/obras/<int:id>/financeiro/etapa/<int:osc_id>/lancamentos` | POST | `financeiro_etapa_lancamento_criar` |
| `/obras/<int:id>/financeiro/etapa/<int:osc_id>/lancamentos/<int:filho_id>` | PATCH,DELETE | `financeiro_etapa_lancamento_editar` |
| `/obras/<int:id>/etapas-custo` | GET | `obra_etapas_custo` |
| `/obras/<int:id>/cronograma-revisar-inicial` | GET | `cronograma_revisar_inicial_get` |
| `/obras/<int:id>/cronograma-revisar-inicial` | POST | `cronograma_revisar_inicial_post` |
| `/obras/<int:id>/cronograma-revisar-reset` | POST | `cronograma_revisar_reset` |
| `/obras/<int:obra_id>/curva-avanco` | GET | `curva_avanco_obra` |
| `/obras/<int:obra_id>/compras/nova` | POST | `nova_compra_obra` |
| `/obras/<int:obra_id>/mapa-concorrencia/novo` | POST | `nova_mapa_concorrencia` |
| `/obras/<int:obra_id>/mapa-concorrencia/<int:mapa_id>/deletar` | POST | `deletar_mapa_concorrencia` |
| `/obras/<int:obra_id>/cronograma-cliente/gerar` | POST | `gerar_cronograma_cliente` |
| `/obras/<int:obra_id>/mapa-v2/criar` | POST | `criar_mapa_v2` |
| `/obras/<int:obra_id>/mapa-v2/<int:mapa_id>/editar` | GET,POST | `editar_mapa_v2` |
| `/obras/<int:obra_id>/mapa-v2/<int:mapa_id>/relatorio/<int:rel_id>/baixar` | GET | `baixar_relatorio_mapa_v2` |
| `/obras/<int:obra_id>/mapa-v2/<int:mapa_id>/relatorio/<int:rel_id>/excluir` | POST | `excluir_relatorio_mapa_v2` |
| `/obras/<int:obra_id>/mapa-v2/<int:mapa_id>/deletar` | POST | `deletar_mapa_v2` |
| `/obras/<int:id>/estado` | POST | `alterar_estado_obra` |
| `/obras/<int:id>/handoff` | GET | `handoff_obra_get` |
| `/obras/<int:id>/handoff` | POST | `handoff_obra_post` |
| `/obras/<int:id>/signatarios` | POST | `criar_signatario_cliente` |
| `/obras/<int:id>/signatarios/<int:sid>/senha` | POST | `gerar_senha_signatario_cliente` |
| `/obras/<int:id>/signatarios/<int:sid>/toggle` | POST | `toggle_signatario_cliente` |
| `/veiculos/<int:id>/ultima-km` | GET | `ultima_km_veiculo` |
| `/veiculos/<int:id>/kpis` | GET | `kpis_veiculo_periodo` |
| `/veiculos/<int:id>/excluir` | POST | `excluir_veiculo` |
| `/veiculos/uso` | POST | `novo_uso_veiculo_lista` |
| `/veiculos/uso/<int:uso_id>/detalhes` | GET | `detalhes_uso_veiculo` |
| `/veiculos/uso/<int:uso_id>/editar` | GET,POST | `editar_uso_veiculo` |
| `/veiculos/uso/<int:uso_id>/deletar` | POST | `deletar_uso_veiculo` |
| `/veiculos/custo/<int:custo_id>/editar` | GET,POST | `editar_custo_veiculo` |
| `/veiculos/custo/<int:custo_id>/deletar` | POST | `deletar_custo_veiculo` |
| `/veiculos/<int:id>/dashboard` | GET | `dashboard_veiculo` |
| `/veiculos/<int:id>/historico` | GET | `historico_veiculo` |
| `/veiculos/<int:id>/custos` | GET | `lista_custos_veiculo` |
| `/veiculos/<int:id>/exportar` | GET | `exportar_dados_veiculo` |
| `/veiculos/lancamentos` | GET | `lancamentos_veiculos` |
| `/veiculos/lancamentos/aprovar/<tipo>/<int:id>` | POST | `aprovar_lancamento_veiculo` |
| `/veiculos/relatorios` | GET | `relatorios_veiculos` |
| `/veiculos/relatorios/exportar` | GET | `exportar_relatorio_veiculos` |
| `/veiculos` | GET | `veiculos` |
| `/veiculos/novo` | GET,POST | `novo_veiculo` |
| `/veiculos/<int:id>` | GET | `detalhes_veiculo` |
| `/veiculos/<int:veiculo_id>/uso/novo` | GET,POST | `novo_uso_veiculo` |
| `/veiculos/<int:id>/editar` | GET,POST | `editar_veiculo` |
| `/api/veiculos/<int:id>` | GET | `api_dados_veiculo` |
| `/api/veiculos/uso/<int:uso_id>/finalizar` | POST | `api_finalizar_uso` |
| `/rdos` | GET | `rdos` |
| `/rdo` | GET | `rdos` |
| `/rdo/` | GET | `rdos` |
| `/rdo/lista` | GET | `rdos` |
| `/rdo/excluir/<int:rdo_id>` | POST,GET | `excluir_rdo` |
| `/rdo/novo` | GET | `novo_rdo` |
| `/rdo/criar` | POST | `criar_rdo` |
| `/rdo/<int:id>` | GET | `visualizar_rdo` |
| `/rdo/<int:rdo_id>/pdf` | GET | `exportar_rdo_pdf` |
| `/rdo/<int:id>/finalizar` | POST | `finalizar_rdo` |
| `/rdo/<int:id>/assinar` | POST | `assinar_rdo` |
| `/rdo/<int:id>/aprovar` | POST | `aprovar_rdo` |
| `/rdo/<int:id>/reabrir` | POST | `reabrir_rdo` |
| `/rdo/<int:id>/retificar` | POST | `retificar_rdo` |
| `/rdo/<int:id>/duplicar` | POST | `duplicar_rdo` |
| `/rdo/<int:id>/atualizar` | POST | `atualizar_rdo` |
| `/rdo/<int:id>/editar` | GET,POST | `editar_rdo` |
| `/api/obra/<int:obra_id>/percentuais-ultimo-rdo` | GET | `api_percentuais_ultimo_rdo` |
| `/funcionario/rdo/consolidado` | GET | `funcionario_rdo_consolidado` |
| `/funcionario/rdo/novo` | GET | `funcionario_rdo_novo` |
| `/rdo/salvar` | POST | `rdo_salvar_unificado` |
| `/funcionario/rdo/criar` | POST | `funcionario_criar_rdo` |
| `/funcionario/rdo/<int:id>` | GET | `funcionario_visualizar_rdo` |
| `/funcionario/rdo/<int:id>/editar` | GET,POST | `funcionario_editar_rdo` |
| `/funcionario/obras` | GET | `funcionario_obras` |
| `/api/funcionario/obras` | GET | `api_funcionario_obras` |
| `/api/funcionario/rdos/<int:obra_id>` | GET | `api_funcionario_rdos_obra` |
| `/api/funcionario/funcionarios` | GET | `api_funcionario_funcionarios_alias` |
| `/salvar-rdo-flexivel` | POST | `salvar_rdo_flexivel` |
| `/api/rdo/ultima-dados/<int:obra_id>` | GET | `api_rdo_ultima_dados` |
| `/api/obras/<int:obra_id>/funcionarios` | GET | `api_funcionarios_por_obra` |
| `/api/funcionarios` | GET | `api_funcionarios_consolidada` |
| `/api/funcao/<int:funcao_id>` | GET | `api_funcao` |
| `/api/ponto/lancamento-multiplo` | POST | `api_ponto_lancamento_multiplo` |
| `/api/funcionario/<int:id>/foto` | GET | `get_funcionario_foto` |
| `/api/funcionario/<int:funcionario_id>` | GET | `get_funcionario` |
| `/funcionarios/<int:funcionario_id>/editar` | POST | `editar_funcionario` |
| `/api/funcionario/<int:funcionario_id>/toggle-ativo` | POST | `toggle_funcionario_ativo` |
| `/api/ponto/lancamento-finais-semana` | POST | `lancamento_finais_semana` |
| `/api/obras/ativas` | GET | `api_obras_ativas` |
| `/api/obras/servicos-rdo` | POST | `api_adicionar_servico_obra` |
| `/api/obras/servicos` | DELETE | `api_remover_servico_obra` |
| `/api/servicos` | GET | `api_servicos` |
| `/api/servicos-disponiveis-obra/<int:obra_id>` | GET | `api_servicos_disponiveis_obra` |
| `/super-admin` | GET | `super_admin_dashboard` |
| `/super-admin/criar-admin` | POST | `criar_admin` |
| `/novo_ponto` | POST | `novo_ponto` |
| `/admin/database-diagnostics` | GET | `database_diagnostics` |
| `/admin/webhooks` | GET | `admin_webhooks_listar` |
| `/admin/webhooks/<int:entrega_id>/reenviar` | POST | `admin_webhooks_reenviar` |
| `/admin/database-diagnostics/check-table` | POST | `check_table_structure` |

**Modelos próprios (22):**

- **AlocacaoEquipe** (`alocacao_equipe`, 17 col) — também usado por RDO — CRUD completo: `id`, `funcionario_id→funcionario`, `obra_id→obra`, `data_alocacao`, `tipo_local`, `turno`, `criado_por_id→usuario`, `rdo_gerado_id→rdo`, `rdo_gerado`, `status`, `prioridade`, `validacao_conflito`, `motivo_cancelamento`, `observacoes`, `admin_id→usuario`, `created_at`, `updated_at`
- **CategoriaEscritorio** (`categoria_escritorio`, 6 col) — também usado por Custos de escritório: `id`, `nome`, `cor`, `ativo`, `admin_id→usuario`, `created_at`
- **CategoriaReembolso** (`categoria_reembolso`, 6 col) — também usado por Catálogos (views): `id`, `nome`, `descricao`, `ativo`, `admin_id→usuario`, `created_at`
- **HorarioDia** (`horario_dia`, 8 col) — também usado por Configurações: `id`, `horario_id→horario_trabalho`, `dia_semana`, `entrada`, `saida`, `pausa_horas`, `trabalha`, `admin_id→usuario`
- **MapaConcorrencia** (`mapa_concorrencia`, 6 col) — também usado por Portal do cliente: `id`, `obra_id→obra`, `admin_id→usuario`, `descricao_item`, `status`, `created_at`
- **MapaCotacao** (`mapa_cotacao`, 8 col): `id`, `mapa_id→mapa_concorrencia_v2`, `item_id→mapa_item_cotacao`, `fornecedor_id→mapa_fornecedor`, `admin_id→usuario`, `valor_unitario`, `prazo`, `selecionado`
- **MapaFornecedor** (`mapa_fornecedor`, 8 col) — também usado por Portal do cliente: `id`, `mapa_id→mapa_concorrencia_v2`, `admin_id→usuario`, `nome`, `ordem`, `prazo_entrega`, `observacao`, `condicoes_pagamento`
- **MapaItemCotacao** (`mapa_item_cotacao`, 8 col) — também usado por Portal do cliente: `id`, `mapa_id→mapa_concorrencia_v2`, `admin_id→usuario`, `descricao`, `unidade`, `quantidade`, `ordem`, `fornecedor_escolhido_id→mapa_fornecedor`
- **MovimentacaoEstoque** (`movimentacao_estoque`, 17 col) — também usado por RDO — CRUD completo: `id`, `produto_id→produto`, `tipo_movimentacao`, `quantidade`, `quantidade_anterior`, `quantidade_posterior`, `valor_unitario`, `valor_total`, `data_movimentacao`, `nota_fiscal_id→nota_fiscal`, `rdo_id→rdo`, `funcionario_id→funcionario`, `obra_id→obra`, `usuario_id→usuario`, `observacoes`, `ip_address`, `admin_id→usuario`
- **ObraServicoCustoItem** (`obra_servico_custo_item`, 9 col): `id`, `obra_servico_custo_id→obra_servico_custo`, `admin_id→usuario`, `descricao`, `valor`, `fonte`, `ordem`, `data_inicio`, `data_fim`
- **ObraSignatarioCliente** (`obra_signatario_cliente`, 14 col) — também usado por Portal do cliente: `id`, `obra_id→obra`, `admin_id→usuario`, `nome`, `email`, `cargo`, `password_hash`, `senha_temporaria`, `senha_expira_em`, `ativo`, `falhas_login`, `ultimo_acesso_em`, `recuperacao_pedida_em`, `criado_em`
- **ObraTransicaoEstado** (`obra_transicao_estado`, 9 col): `id`, `obra_id→obra`, `admin_id→usuario`, `estado_de`, `estado_para`, `motivo`, `detalhes`, `usuario_id→usuario`, `criado_em`
- **OpcaoConcorrencia** (`opcao_concorrencia`, 8 col) — também usado por Portal do cliente: `id`, `mapa_id→mapa_concorrencia`, `fornecedor_nome`, `valor_unitario`, `prazo_entrega`, `observacoes`, `selecionada`, `admin_id→usuario`
- **OutroCusto** (`outro_custo`, 12 col): `id`, `funcionario_id→funcionario`, `data`, `tipo`, `categoria`, `valor`, `descricao`, `obra_id→obra`, `percentual`, `admin_id→usuario`, `kpi_associado`, `created_at`
- **PedidoCompraItem** (`pedido_compra_item`, 8 col) — também usado por Compras: `id`, `pedido_id→pedido_compra`, `almoxarifado_item_id→almoxarifado_item`, `descricao`, `quantidade`, `preco_unitario`, `subtotal`, `admin_id→usuario`
- **RDOAssinatura** (`rdo_assinatura`, 17 col) — também usado por Portal do cliente: `id`, `rdo_id→rdo`, `admin_id→usuario`, `usuario_id→usuario`, `funcionario_id→funcionario`, `signatario_cliente_id→obra_signatario_cliente`, `papel`, `nome_signatario`, `cargo_signatario`, `hash_conteudo`, `algoritmo`, `provedor`, `referencia_externa`, `assinado_em`, `ip`, `user_agent`, `observacao`
- **RDOCustoDiario** (`rdo_custo_diario`, 19 col) — também usado por RDO — edição: `id`, `rdo_id→rdo`, `funcionario_id→funcionario`, `admin_id→usuario`, `data`, `tipo_remuneracao_snapshot`, `componente_folha`, `componente_va`, `componente_vt`, `componente_extra`, `custo_total_dia`, `horas_normais`, `horas_extras`, `custo_hora_normal`, `dias_uteis_mes_referencia`, `tipo_lancamento`, `retroativo`, `created_at`, `updated_at`
- **RelatorioCompraMapa** (`relatorio_compra_mapa`, 10 col) — também usado por Portal do cliente: `id`, `mapa_id→mapa_concorrencia_v2`, `obra_id→obra`, `admin_id→usuario`, `gerado_por_id→usuario`, `versao`, `arquivo_path`, `arquivo_nome`, `total_geral`, `gerado_em`
- **ServicoObra** (`servico_obra`, 10 col): `id`, `admin_id→usuario`, `obra_id→obra`, `servico_id→servico`, `quantidade_planejada`, `quantidade_executada`, `observacoes`, `ativo`, `created_at`, `updated_at`
- **UsuarioObra** (`usuario_obra`, 7 col): `id`, `usuario_id→usuario`, `obra_id→obra`, `papel`, `admin_id→usuario`, `ativo`, `created_at`
- **VehicleExpense** (`frota_despesa`, 16 col): `id`, `veiculo_id→frota_veiculo`, `obra_id→obra`, `data_custo`, `tipo_custo`, `valor`, `descricao`, `fornecedor`, `numero_nota_fiscal`, `data_vencimento`, `status_pagamento`, `forma_pagamento`, `km_veiculo`, `observacoes`, `admin_id→usuario`, `created_at`
- **WebhookEntrega** (`webhook_entrega`, 10 col): `id`, `event`, `payload`, `status`, `tentativas`, `ultimo_erro`, `proxima_tentativa_em`, `admin_id→usuario`, `created_at`, `sent_at`

**Modelos compartilhados que este módulo toca (49):** `AlimentacaoLancamento`, `AlmoxarifadoEstoque`, `AlmoxarifadoItem`, `AlmoxarifadoMovimento`, `CategoriaFluxoCaixa`, `CategoriaFornecedor`, `Cliente`, `ConfiguracaoEmpresa`, `CronogramaTemplate`, `CustoObra`, `CustoVeiculo`, `Departamento`, `FluxoCaixa`, `Fornecedor`, `Funcao`, `Funcionario`, `GestaoCustoFilho`, `GestaoCustoPai`, `HorarioTrabalho`, `LancamentoTransporte`, `Lead`, `MapaConcorrenciaV2`, `MedicaoObra`, `Obra`, `ObraOrcamentoOperacional`, `ObraServicoCusto`, `PedidoCompra`, `Proposta`, `PropostaHistorico`, `PropostaTemplate`, `RDO`, `RDOApontamentoCronograma`, `RDOEquipamento`, `RDOFoto`, `RDOMaoObra`, `RDOOcorrencia`, `RDOServicoSubatividade`, `RDOSubempreitadaApontamento`, `RegistroAlimentacao`, `RegistroPonto`, `Restaurante`, `Servico`, `ServicoObraReal`, `SubatividadeMestre`, `Subempreiteiro`, `TarefaCronograma`, `UsoVeiculo`, `Usuario`, `Veiculo`

### RDO — edição

Arquivos: `rdo_editar_sistema.py`
Conferência: ☐ pendente

**Funcionalidades (3 rotas):**

| Rota | Métodos | Função |
|---|---|---|
| `/<int:rdo_id>` | GET | `editar_rdo_form` |
| `/<int:rdo_id>` | POST | `salvar_edicao_rdo` |
| `/api/funcionarios-ativos` | GET | `api_funcionarios_ativos` |

**Modelos próprios (1):**

- **RDOCustoDiario** (`rdo_custo_diario`, 19 col) — também usado por Obras/Dashboard/base (main): `id`, `rdo_id→rdo`, `funcionario_id→funcionario`, `admin_id→usuario`, `data`, `tipo_remuneracao_snapshot`, `componente_folha`, `componente_va`, `componente_vt`, `componente_extra`, `custo_total_dia`, `horas_normais`, `horas_extras`, `custo_hora_normal`, `dias_uteis_mes_referencia`, `tipo_lancamento`, `retroativo`, `created_at`, `updated_at`

**Modelos compartilhados que este módulo toca (11):** `Departamento`, `Funcionario`, `GestaoCustoFilho`, `Obra`, `RDO`, `RDOApontamentoCronograma`, `RDOMaoObra`, `RDOServicoSubatividade`, `ServicoObraReal`, `SubatividadeMestre`, `TarefaCronograma`

### RDO — CRUD completo

Arquivos: `crud_rdo_completo.py`
Conferência: ☐ pendente

**Funcionalidades (13 rotas):**

| Rota | Métodos | Função |
|---|---|---|
| `/` | GET | `listar_rdos` |
| `/novo` | GET | `novo_rdo` |
| `/editar/<int:rdo_id>` | GET | `editar_rdo` |
| `/visualizar/<int:rdo_id>` | GET | `visualizar_rdo` |
| `/rdo/salvar` | GET | `salvar_rdo` |
| `/rdo/salvar` | GET | `excluir_rdo` |
| `/excluir/<int:rdo_id>` | POST | `excluir_rdo` |
| `/finalizar/<int:rdo_id>` | POST | `finalizar_rdo` |
| `/<int:rdo_id>/fotos/upload` | POST | `upload_foto_rdo` |
| `/foto/<int:foto_id>/<tipo>` | GET | `servir_foto` |
| `/<int:rdo_id>/fotos` | GET | `listar_fotos_rdo` |
| `/foto/<int:foto_id>/editar` | POST | `editar_descricao_foto` |
| `/foto/<int:foto_id>/deletar` | POST | `deletar_foto` |

**Modelos próprios (2):**

- **AlocacaoEquipe** (`alocacao_equipe`, 17 col) — também usado por Obras/Dashboard/base (main): `id`, `funcionario_id→funcionario`, `obra_id→obra`, `data_alocacao`, `tipo_local`, `turno`, `criado_por_id→usuario`, `rdo_gerado_id→rdo`, `rdo_gerado`, `status`, `prioridade`, `validacao_conflito`, `motivo_cancelamento`, `observacoes`, `admin_id→usuario`, `created_at`, `updated_at`
- **MovimentacaoEstoque** (`movimentacao_estoque`, 17 col) — também usado por Obras/Dashboard/base (main): `id`, `produto_id→produto`, `tipo_movimentacao`, `quantidade`, `quantidade_anterior`, `quantidade_posterior`, `valor_unitario`, `valor_total`, `data_movimentacao`, `nota_fiscal_id→nota_fiscal`, `rdo_id→rdo`, `funcionario_id→funcionario`, `obra_id→obra`, `usuario_id→usuario`, `observacoes`, `ip_address`, `admin_id→usuario`

**Modelos compartilhados que este módulo toca (12):** `ContaPagar`, `CustoObra`, `Funcionario`, `Obra`, `RDO`, `RDOApontamentoCronograma`, `RDOEquipamento`, `RDOFoto`, `RDOMaoObra`, `RDOOcorrencia`, `RDOServicoSubatividade`, `SubatividadeMestre`

### Cronograma

Arquivos: `cronograma_views.py`
Conferência: ☐ pendente

**Funcionalidades (46 rotas):**

| Rota | Métodos | Função |
|---|---|---|
| `/` | GET | `index` |
| `/obra/<int:obra_id>` | GET | `cronograma_obra` |
| `/obra/<int:obra_id>/tarefa` | POST | `criar_tarefa` |
| `/obra/<int:obra_id>/tarefa/<int:tarefa_id>` | PUT,PATCH | `atualizar_tarefa` |
| `/obra/<int:obra_id>/tarefa/<int:tarefa_id>` | DELETE | `excluir_tarefa` |
| `/obra/<int:obra_id>/recalcular` | POST | `recalcular` |
| `/obra/<int:obra_id>/vinculo` | POST | `criar_vinculo` |
| `/obra/<int:obra_id>/vinculo/<int:vid>` | PUT,PATCH | `atualizar_vinculo` |
| `/obra/<int:obra_id>/vinculo/<int:vid>` | DELETE | `excluir_vinculo` |
| `/obra/<int:obra_id>/tarefa/<int:tarefa_id>/recuar` | POST | `recuar_tarefa` |
| `/obra/<int:obra_id>/tarefa/<int:tarefa_id>/desrecuar` | POST | `desrecuar_tarefa` |
| `/obra/<int:obra_id>/tarefa/<int:tarefa_id>/mover` | POST | `mover_tarefa` |
| `/obra/<int:obra_id>/desfazer` | POST | `desfazer_acao` |
| `/obra/<int:obra_id>/refazer` | POST | `refazer_acao` |
| `/obra/<int:obra_id>/baseline` | POST | `criar_baseline` |
| `/obra/<int:obra_id>/baselines` | GET | `listar_baselines` |
| `/obra/<int:obra_id>/baseline/<int:bid>/ativar` | POST | `ativar_baseline` |
| `/obra/<int:obra_id>/baseline/<int:bid>` | DELETE | `excluir_baseline` |
| `/obra/<int:obra_id>/reordenar` | POST | `reordenar` |
| `/calendario` | GET,POST | `calendario` |
| `/obra/<int:obra_id>/tarefas-rdo` | GET | `tarefas_rdo` |
| `/rdo/<int:rdo_id>/apontar-subempreitada` | POST | `apontar_subempreitada` |
| `/rdo/<int:rdo_id>/apontamentos-subempreitada` | GET | `listar_apontamentos_subempreitada` |
| `/rdo/apontamento-subempreitada/<int:apt_id>` | DELETE | `excluir_apontamento_subempreitada` |
| `/rdo/<int:rdo_id>/apontar` | POST | `apontar_producao` |
| `/rdo/<int:rdo_id>/apontamentos` | GET | `listar_apontamentos` |
| `/catalogo` | GET | `catalogo_subatividades` |
| `/catalogo/nova` | POST | `catalogo_nova_subatividade` |
| `/catalogo/novo-grupo` | POST | `catalogo_novo_grupo` |
| `/catalogo/<int:sub_id>/editar` | GET,POST | `catalogo_editar_subatividade` |
| `/catalogo/<int:sub_id>/excluir` | POST | `catalogo_excluir_subatividade` |
| `/api/catalogo` | GET | `api_catalogo` |
| `/templates` | GET | `listar_templates` |
| `/templates/novo` | GET,POST | `novo_template` |
| `/templates/<int:template_id>` | GET | `detalhe_template` |
| `/templates/<int:template_id>/editar` | GET,POST | `editar_template` |
| `/templates/modelo-excel` | GET | `templates_modelo_excel` |
| `/templates/importar-excel` | POST | `templates_importar_excel` |
| `/templates/<int:template_id>/excluir` | POST | `excluir_template` |
| `/obra/<int:obra_id>/aplicar-template` | POST | `aplicar_template` |
| `/api/templates/<int:template_id>` | GET | `api_template_arvore` |
| `/api/templates` | GET | `api_listar_templates` |
| `/produtividade` | GET | `produtividade_dashboard` |
| `/api/produtividade` | GET | `api_produtividade` |
| `/obra/<int:obra_id>/fisico-financeiro` | GET | `fisico_financeiro` |
| `/obra/<int:obra_id>/fisico-financeiro/export.xlsx` | GET | `fisico_financeiro_xlsx` |

**Modelos próprios (6):**

- **ComposicaoServico** (`composicao_servico`, 8 col) — também usado por Catálogo de serviços: `id`, `admin_id→usuario`, `servico_id→servico`, `insumo_id→insumo`, `coeficiente`, `unidade`, `observacao`, `created_at`
- **CronogramaBaseline** (`cronograma_baseline`, 9 col): `id`, `obra_id→obra`, `admin_id→usuario`, `nome`, `criada_em`, `criada_por→usuario`, `ativa`, `is_cliente`, `bac`
- **CronogramaBaselineItem** (`cronograma_baseline_item`, 7 col): `id`, `baseline_id→cronograma_baseline`, `tarefa_id→tarefa_cronograma`, `admin_id→usuario`, `data_inicio`, `data_fim`, `duracao_dias`
- **CronogramaTemplateItem** (`cronograma_template_item`, 11 col): `id`, `template_id→cronograma_template`, `subatividade_mestre_id→subatividade_mestre`, `parent_item_id→cronograma_template_item`, `nome_tarefa`, `ordem`, `duracao_dias`, `quantidade_prevista`, `responsavel`, `admin_id`, `created_at`
- **SubatividadeMaoObra** (`subatividade_mao_obra`, 5 col): `id`, `admin_id→usuario`, `subatividade_mestre_id→subatividade_mestre`, `composicao_servico_id→composicao_servico`, `created_at`
- **TarefaVinculo** (`tarefa_vinculo`, 8 col): `id`, `admin_id→usuario`, `obra_id→obra`, `predecessora_id→tarefa_cronograma`, `sucessora_id→tarefa_cronograma`, `tipo`, `lag_dias`, `created_at`

**Modelos compartilhados que este módulo toca (14):** `ConfiguracaoEmpresa`, `CronogramaTemplate`, `Funcionario`, `Insumo`, `Obra`, `RDO`, `RDOApontamentoCronograma`, `RDOMaoObra`, `RDOServicoSubatividade`, `RDOSubempreitadaApontamento`, `Servico`, `SubatividadeMestre`, `Subempreiteiro`, `TarefaCronograma`

### Cronograma — importação .mpp

Arquivos: `views/cronograma_importacao.py`
Conferência: ☐ pendente

**Funcionalidades (12 rotas):**

| Rota | Métodos | Função |
|---|---|---|
| `/obras/<int:obra_id>/cronograma/importacoes` | POST | `importar_cronograma` |
| `/obras/<int:obra_id>/cronograma/importacoes/<int:importacao_id>` | POST | `reconciliar_importacao` |
| `/obras/<int:obra_id>/cronograma/importacoes/<int:importacao_id>/diff` | GET | `diff_importacao` |
| `/obras/<int:obra_id>/cronograma/importacoes/<int:importacao_id>` | PATCH | `decidir_mapeamento` |
| `/obras/<int:obra_id>/cronograma/importacoes/<int:importacao_id>` | POST | `aplicar_importacao` |
| `/obras/<int:obra_id>/cronograma/versoes/<int:versao_id>/restaurar` | POST | `restaurar_versao_endpoint` |
| `/obras/<int:obra_id>/cronograma/importacoes` | GET | `listar_importacoes` |
| `/obras/<int:obra_id>/cronograma/versoes` | GET | `listar_versoes` |
| `/obras/<int:obra_id>/cronograma/importacoes/<int:importacao_id>/status` | GET | `status_importacao` |
| `/obras/<int:obra_id>/cronograma/importacoes/<int:importacao_id>` | POST | `cancelar_importacao` |
| `/obras/<int:obra_id>/cronograma/importacoes/<int:importacao_id>/previa` | GET | `previa_importacao` |
| `/obras/<int:obra_id>/cronograma/importacoes/<int:importacao_id>/resultado` | GET | `resultado_importacao` |

**Modelos próprios (5):**

- **CronogramaImportacao** (`cronograma_importacao`, 19 col): `id`, `obra_id→obra`, `admin_id→usuario`, `arquivo_nome`, `arquivo_tamanho`, `arquivo_sha256`, `arquivo_path`, `origem`, `parser_nome`, `parser_versao`, `normalizador_versao`, `status`, `json_bruto`, `json_normalizado`, `relatorio_diff`, `erro`, `criado_por_id→usuario`, `criado_em`, `aplicado_em`
- **CronogramaImportacaoEvento** (`cronograma_importacao_evento`, 7 col): `id`, `importacao_id→cronograma_importacao`, `admin_id→usuario`, `evento`, `detalhes`, `usuario_id→usuario`, `criado_em`
- **CronogramaTarefaMapeamento** (`cronograma_tarefa_mapeamento`, 10 col): `id`, `importacao_id→cronograma_importacao`, `admin_id→usuario`, `tarefa_atual_id→tarefa_cronograma`, `chave_nova`, `tipo`, `score`, `origem_decisao`, `decidido_por_id→usuario`, `detalhes`
- **CronogramaTarefaSnapshot** (`cronograma_tarefa_snapshot`, 19 col): `id`, `versao_id→cronograma_versao`, `admin_id→usuario`, `tarefa_id→tarefa_cronograma`, `mpp_uid`, `wbs_codigo`, `nome_tarefa`, `tarefa_pai_snapshot_id→cronograma_tarefa_snapshot`, `predecessoras_json`, `ordem`, `data_inicio`, `data_fim`, `duracao_dias`, `quantidade_total`, `unidade_medida`, `is_marco`, `is_resumo`, `percentual_concluido_no_momento`, `payload_extra`
- **CronogramaVersao** (`cronograma_versao`, 9 col): `id`, `obra_id→obra`, `admin_id→usuario`, `numero`, `status`, `importacao_id→cronograma_importacao`, `aplicada_em`, `aplicada_por_id→usuario`, `observacao`

**Modelos compartilhados que este módulo toca (3):** `Obra`, `TarefaCronograma`, `Usuario`

### Portal do cliente

Arquivos: `portal_obras_views.py`
Conferência: ☐ pendente

**Funcionalidades (18 rotas):**

| Rota | Métodos | Função |
|---|---|---|
| `/obra/<token>` | GET | `portal_obra` |
| `/obra/<token>/compra/<int:compra_id>/aprovar` | POST | `aprovar_compra` |
| `/obra/<token>/compra/<int:compra_id>/recusar` | POST | `recusar_compra` |
| `/obra/<token>/compra/<int:compra_id>/comprovante` | POST | `upload_comprovante` |
| `/obra/<token>/compra/<int:compra_id>/comprovante` | GET | `ver_comprovante` |
| `/obra/<token>/mapa/<int:mapa_id>/aprovar` | POST | `aprovar_mapa_concorrencia` |
| `/obra/<int:obra_id>/portal-toggle` | POST | `toggle_portal` |
| `/obra/<int:obra_id>/medicao/gerar` | POST | `gerar_medicao` |
| `/obra/<token>/mapa-v2/<int:mapa_id>/selecionar` | POST | `selecionar_mapa_v2` |
| `/obra/<token>/mapa-v2/<int:mapa_id>/relatorio/<int:rel_id>/baixar` | GET | `baixar_relatorio_mapa_v2_portal` |
| `/obra/<token>/rdo/<int:rdo_id>` | GET | `portal_rdo_detalhe` |
| `/obra/<token>/rdo/<int:rdo_id>/ciencia` | GET | `ciencia_ato` |
| `/obra/<token>/rdo/<int:rdo_id>/ciencia` | POST | `ciencia_confirmar` |
| `/obra/<token>/rdo/<int:rdo_id>/ciencia/comprovante` | GET | `ciencia_comprovante` |
| `/obra/<token>/rdo/<int:rdo_id>/ciencia/recibo.pdf` | GET | `ciencia_recibo` |
| `/obra/<token>/rdo/<int:rdo_id>/ciencia/senha` | GET | `ciencia_definir_senha` |
| `/obra/<token>/rdo/<int:rdo_id>/ciencia/senha` | POST | `ciencia_trocar_senha` |
| `/obra/<token>/rdo/<int:rdo_id>/ciencia/esqueci` | POST | `ciencia_esqueci` |

**Modelos próprios (8):**

- **MapaConcorrencia** (`mapa_concorrencia`, 6 col) — também usado por Obras/Dashboard/base (main): `id`, `obra_id→obra`, `admin_id→usuario`, `descricao_item`, `status`, `created_at`
- **MapaFornecedor** (`mapa_fornecedor`, 8 col) — também usado por Obras/Dashboard/base (main): `id`, `mapa_id→mapa_concorrencia_v2`, `admin_id→usuario`, `nome`, `ordem`, `prazo_entrega`, `observacao`, `condicoes_pagamento`
- **MapaItemCotacao** (`mapa_item_cotacao`, 8 col) — também usado por Obras/Dashboard/base (main): `id`, `mapa_id→mapa_concorrencia_v2`, `admin_id→usuario`, `descricao`, `unidade`, `quantidade`, `ordem`, `fornecedor_escolhido_id→mapa_fornecedor`
- **ObraSignatarioCliente** (`obra_signatario_cliente`, 14 col) — também usado por Obras/Dashboard/base (main): `id`, `obra_id→obra`, `admin_id→usuario`, `nome`, `email`, `cargo`, `password_hash`, `senha_temporaria`, `senha_expira_em`, `ativo`, `falhas_login`, `ultimo_acesso_em`, `recuperacao_pedida_em`, `criado_em`
- **OpcaoConcorrencia** (`opcao_concorrencia`, 8 col) — também usado por Obras/Dashboard/base (main): `id`, `mapa_id→mapa_concorrencia`, `fornecedor_nome`, `valor_unitario`, `prazo_entrega`, `observacoes`, `selecionada`, `admin_id→usuario`
- **PortalAcessoEvento** (`portal_acesso_evento`, 10 col): `id`, `obra_id→obra`, `admin_id→usuario`, `acao`, `alvo_tipo`, `alvo_id`, `ip`, `user_agent`, `detalhes`, `criado_em`
- **RDOAssinatura** (`rdo_assinatura`, 17 col) — também usado por Obras/Dashboard/base (main): `id`, `rdo_id→rdo`, `admin_id→usuario`, `usuario_id→usuario`, `funcionario_id→funcionario`, `signatario_cliente_id→obra_signatario_cliente`, `papel`, `nome_signatario`, `cargo_signatario`, `hash_conteudo`, `algoritmo`, `provedor`, `referencia_externa`, `assinado_em`, `ip`, `user_agent`, `observacao`
- **RelatorioCompraMapa** (`relatorio_compra_mapa`, 10 col) — também usado por Obras/Dashboard/base (main): `id`, `mapa_id→mapa_concorrencia_v2`, `obra_id→obra`, `admin_id→usuario`, `gerado_por_id→usuario`, `versao`, `arquivo_path`, `arquivo_nome`, `total_geral`, `gerado_em`

**Modelos compartilhados que este módulo toca (18):** `Cliente`, `ConfiguracaoEmpresa`, `ContaReceber`, `FluxoCaixa`, `Fornecedor`, `GestaoCustoPai`, `MapaConcorrenciaV2`, `MedicaoObra`, `Obra`, `PedidoCompra`, `RDO`, `RDOApontamentoCronograma`, `RDOEquipamento`, `RDOFoto`, `RDOMaoObra`, `RDOOcorrencia`, `RDOServicoSubatividade`, `TarefaCronograma`

### Medição

Arquivos: `medicao_views.py`
Conferência: ☐ pendente

**Funcionalidades (25 rotas):**

| Rota | Métodos | Função |
|---|---|---|
| `/obras/<int:obra_id>/medicao/` | GET | `gestao_itens` |
| `/obras/<int:obra_id>/medicao` | GET | `gestao_itens` |
| `/medicao/obra/<int:obra_id>` | GET | `gestao_itens` |
| `/obras/<int:obra_id>/medicao/itens` | GET | `listar_itens` |
| `/obras/<int:obra_id>/medicao/itens` | POST | `criar_item` |
| `/medicao/obra/<int:obra_id>/item` | POST | `criar_item` |
| `/obras/<int:obra_id>/medicao/itens/<int:item_id>` | POST | `editar_item` |
| `/medicao/obra/<int:obra_id>/item/<int:item_id>/editar` | POST | `editar_item` |
| `/obras/<int:obra_id>/medicao/itens/<int:item_id>` | DELETE | `excluir_item` |
| `/obras/<int:obra_id>/medicao/itens/<int:item_id>/excluir` | POST,DELETE | `excluir_item` |
| `/medicao/obra/<int:obra_id>/item/<int:item_id>/excluir` | POST,DELETE | `excluir_item` |
| `/obras/<int:obra_id>/medicao/itens/<int:item_id>/tarefas` | POST | `vincular_tarefa` |
| `/medicao/obra/<int:obra_id>/item/<int:item_id>/vincular` | POST | `vincular_tarefa` |
| `/obras/<int:obra_id>/medicao/itens/<int:item_id>/tarefas/<int:vinculo_id>/excluir` | POST,DELETE | `desvincular_tarefa` |
| `/medicao/obra/<int:obra_id>/item/<int:item_id>/desvincular/<int:vinculo_id>` | POST,DELETE | `desvincular_tarefa` |
| `/obras/<int:obra_id>/medicao/config` | POST | `config_obra_medicao` |
| `/medicao/obra/<int:obra_id>/config` | POST | `config_obra_medicao` |
| `/obras/<int:obra_id>/medicao/fechar` | POST | `gerar_medicao` |
| `/medicao/obra/<int:obra_id>/gerar` | POST | `gerar_medicao` |
| `/obras/<int:obra_id>/medicao/<int:medicao_id>/aprovar` | POST | `fechar` |
| `/medicao/obra/<int:obra_id>/fechar/<int:medicao_id>` | POST | `fechar` |
| `/obras/<int:obra_id>/medicao/<int:medicao_id>/pdf` | GET | `pdf_extrato` |
| `/medicao/obra/<int:obra_id>/pdf/<int:medicao_id>` | GET | `pdf_extrato` |
| `/medicao/<int:medicao_id>/pdf` | GET | `pdf_extrato` |
| `/medicao/portal/pdf/<int:medicao_id>` | GET | `portal_pdf_extrato` |

**Modelos próprios (1):**

- **ItemMedicaoCronogramaTarefa** (`item_medicao_cronograma_tarefa`, 5 col): `id`, `item_medicao_id→item_medicao_comercial`, `cronograma_tarefa_id→tarefa_cronograma`, `peso`, `admin_id→usuario`

**Modelos compartilhados que este módulo toca (8):** `ConfiguracaoEmpresa`, `ContaReceber`, `ItemMedicaoComercial`, `MedicaoObra`, `Obra`, `ObraServicoCusto`, `Servico`, `TarefaCronograma`

### Importação

Arquivos: `importacao_views.py`
Conferência: ☐ pendente

**Funcionalidades (23 rotas):**

| Rota | Métodos | Função |
|---|---|---|
| `/` | GET | `index` |
| `/template/<modulo>` | GET | `baixar_template` |
| `/preview/<modulo>` | POST | `preview` |
| `/confirmar/<modulo>` | POST | `confirmar` |
| `/funcionarios/preview` | POST | `funcionarios_preview` |
| `/funcionarios/confirmar` | POST | `funcionarios_confirmar` |
| `/diarias/preview` | POST | `diarias_preview` |
| `/diarias/confirmar` | POST | `diarias_confirmar` |
| `/alimentacao/preview` | POST | `alimentacao_preview` |
| `/alimentacao/confirmar` | POST | `alimentacao_confirmar` |
| `/transporte/preview` | POST | `transporte_preview` |
| `/transporte/confirmar` | POST | `transporte_confirmar` |
| `/custos/preview` | POST | `custos_preview` |
| `/custos/confirmar` | POST | `custos_confirmar` |
| `/api/entidades` | GET | `api_entidades` |
| `/fluxo-caixa/upload` | POST | `fluxo_caixa_upload` |
| `/fluxo-caixa/classificar-termo` | POST | `fluxo_caixa_classificar_termo` |
| `/fluxo-caixa/corrigir-linha` | POST | `fluxo_caixa_corrigir_linha` |
| `/fluxo-caixa/confirmar-regra-refinada` | POST | `fluxo_caixa_confirmar_regra_refinada` |
| `/fluxo-caixa/confirmar` | POST | `fluxo_caixa_confirmar` |
| `/fluxo-caixa/rollback/<batch_id>` | POST | `fluxo_caixa_rollback` |
| `/fisico-financeiro` | GET,POST | `importar_fisico_financeiro_view` |
| `/historico` | GET | `historico` |

**Modelos próprios (1):**

- **PalavraChaveCategoria** (`palavra_chave_categoria`, 15 col) — também usado por Catálogos (views): `id`, `admin_id→usuario`, `categoria_fluxo_caixa_id→categoria_fluxo_caixa`, `palavras`, `campo_alvo`, `excecoes`, `gatilho_extra`, `campo_extra`, `condicao_obra`, `prioridade`, `tipo`, `origem`, `ativo`, `created_at`, `updated_at`

**Modelos compartilhados que este módulo toca (11):** `BancoEmpresa`, `CategoriaFluxoCaixa`, `ContaPagar`, `ContaReceber`, `FluxoCaixa`, `Fornecedor`, `Funcionario`, `GestaoCustoPai`, `Obra`, `Restaurante`, `Usuario`

### Equipe

Arquivos: `equipe_views.py`
Conferência: ☐ pendente

**Funcionalidades (17 rotas):**

| Rota | Métodos | Função |
|---|---|---|
| `/` | GET | `alocacao_semanal` |
| `/alocacao` | GET | `alocacao_semanal` |
| `/alocacao-principal` | GET | `alocacao_principal` |
| `/funcionarios/<int:allocation_id>` | GET | `allocation_funcionarios` |
| `/api/allocations/<int:allocation_id>/funcionarios` | GET | `get_funcionarios_allocation_json` |
| `/api/obras-simples` | GET | `get_obras_simples` |
| `/api/allocations-simples` | GET | `get_allocations_simples` |
| `/api/funcionario/<int:funcionario_id>/horarios` | GET | `api_get_funcionario_horarios` |
| `/api/allocations` | POST | `api_alocar_obra_restful` |
| `/api/allocations/<int:obra_id>/<data_alocacao>` | DELETE | `api_remover_obra_restful` |
| `/api/allocations-week` | GET | `api_allocations_week` |
| `/api/allocation/<int:allocation_id>/funcionarios` | GET | `api_get_allocation_funcionarios` |
| `/api/allocation-employee` | POST | `api_create_allocation_employee` |
| `/api/allocation-employee/<int:allocation_employee_id>` | PUT | `api_update_allocation_employee` |
| `/api/allocation-employee/<int:allocation_employee_id>` | DELETE | `api_delete_allocation_employee` |
| `/api/sync-ponto` | POST | `api_sincronizar_ponto_manual` |
| `/api/allocation-employee/<int:allocation_employee_id>/sync-horario` | POST | `api_sincronizar_horario_funcionario` |

**Modelos próprios (2):**

- **Allocation** (`allocation`, 9 col): `id`, `admin_id→usuario`, `obra_id→obra`, `data_alocacao`, `turno_inicio`, `turno_fim`, `local_trabalho`, `nota`, `created_at`
- **AllocationEmployee** (`allocation_employee`, 15 col): `id`, `admin_id→usuario`, `allocation_id→allocation`, `funcionario_id→funcionario`, `turno_inicio`, `turno_fim`, `papel`, `observacao`, `hora_almoco_saida`, `hora_almoco_retorno`, `percentual_extras`, `tipo_lancamento`, `sincronizado_ponto`, `data_sincronizacao`, `created_at`

**Modelos compartilhados que este módulo toca (2):** `Funcionario`, `Obra`

### Funcionários (API)

Arquivos: `api_funcionarios.py`
Conferência: ☐ pendente

**Funcionalidades (3 rotas):**

| Rota | Métodos | Função |
|---|---|---|
| `/funcionarios-ativos` | GET | `funcionarios_ativos` |
| `/funcionarios/buscar` | GET | `buscar_funcionarios` |
| `/funcionarios/<int:funcionario_id>` | GET | `obter_funcionario` |

**Modelos compartilhados que este módulo toca (2):** `Funcionario`, `RDO`

### Ponto

Arquivos: `ponto_views.py`
Conferência: ☐ pendente

**Funcionalidades (32 rotas):**

| Rota | Métodos | Função |
|---|---|---|
| `/` | GET | `index` |
| `/funcionario/<int:funcionario_id>` | GET | `bater_ponto_funcionario` |
| `/obra/<int:obra_id>` | GET | `obra_dashboard` |
| `/api/bater-ponto` | POST | `api_bater_ponto` |
| `/registro/<int:registro_id>` | DELETE | `excluir_registro_ponto` |
| `/excluir-preview/<int:registro_id>` | GET | `excluir_ponto_preview` |
| `/excluir/<int:registro_id>` | POST | `excluir_registro_ponto_post` |
| `/api/status-obra/<int:obra_id>` | GET | `api_status_obra` |
| `/api/registrar-falta` | POST | `api_registrar_falta` |
| `/relatorio/obra/<int:obra_id>` | GET | `relatorio_obra` |
| `/configuracao/obra/<int:obra_id>` | GET | `configuracao_obra` |
| `/api/salvar-configuracao` | POST | `api_salvar_configuracao` |
| `/lista-obras` | GET | `lista_obras` |
| `/configuracao/funcionario/<int:funcionario_id>/obras` | GET,POST | `configurar_obras_funcionario` |
| `/configuracao/obras-funcionarios` | GET | `listar_configuracoes` |
| `/importar` | GET | `pagina_importar` |
| `/importar/download-modelo` | GET | `download_modelo` |
| `/importar/processar` | POST | `processar_importacao` |
| `/api/registrar-facial` | POST | `registrar_ponto_facial_api` |
| `/api/verificar-foto-funcionario/<int:funcionario_id>` | GET | `verificar_foto_funcionario` |
| `/facial` | GET | `ponto_facial_automatico` |
| `/api/cache/gerar` | POST | `gerar_cache_embeddings` |
| `/api/cache/status` | GET | `status_cache_embeddings` |
| `/api/cache/verificar` | GET | `verificar_cache` |
| `/api/cache/validar` | GET | `validar_cache_embeddings` |
| `/api/cache/debug` | GET | `debug_cache_embeddings` |
| `/api/identificar-e-registrar` | POST | `identificar_e_registrar` |
| `/gerenciar-fotos-faciais` | GET | `listar_funcionarios_fotos_faciais` |
| `/funcionario/<int:funcionario_id>/fotos-faciais` | GET | `gerenciar_fotos_faciais` |
| `/api/funcionario/<int:funcionario_id>/foto-facial` | POST | `adicionar_foto_facial` |
| `/api/foto-facial/<int:foto_id>` | DELETE | `excluir_foto_facial` |
| `/api/foto-facial/<int:foto_id>/ativar` | POST | `ativar_foto_facial` |

**Modelos próprios (3):**

- **ConfiguracaoHorario** (`configuracao_horario`, 13 col): `id`, `obra_id→obra`, `funcionario_id→funcionario`, `entrada_padrao`, `saida_padrao`, `almoco_inicio`, `almoco_fim`, `tolerancia_atraso`, `carga_horaria_diaria`, `admin_id→usuario`, `ativo`, `created_at`, `updated_at`
- **FotoFacialFuncionario** (`foto_facial_funcionario`, 8 col): `id`, `funcionario_id→funcionario`, `foto_base64`, `descricao`, `ordem`, `ativa`, `created_at`, `admin_id→usuario`
- **FuncionarioObrasPonto** (`funcionario_obras_ponto`, 6 col) — também usado por Relatórios: `id`, `funcionario_id→funcionario`, `obra_id→obra`, `admin_id→usuario`, `ativo`, `created_at`

**Modelos compartilhados que este módulo toca (6):** `FluxoCaixa`, `Funcionario`, `GestaoCustoFilho`, `GestaoCustoPai`, `Obra`, `RegistroPonto`

### Folha de pagamento

Arquivos: `folha_pagamento_views.py`
Conferência: ☐ pendente

**Funcionalidades (18 rotas):**

| Rota | Métodos | Função |
|---|---|---|
| `/dashboard` | GET | `dashboard` |
| `/processar/<int:ano>/<int:mes>` | POST | `processar_folha_mes` |
| `/parametros-legais` | GET | `parametros_legais` |
| `/parametros-legais/criar` | GET,POST | `criar_parametros` |
| `/parametros-legais/editar/<int:id>` | GET,POST | `editar_parametros` |
| `/parametros-legais/toggle/<int:id>` | POST | `toggle_parametros` |
| `/beneficios` | GET | `beneficios` |
| `/beneficios/criar` | GET,POST | `criar_beneficio` |
| `/beneficios/editar/<int:id>` | GET,POST | `editar_beneficio` |
| `/beneficios/deletar/<int:id>` | POST | `deletar_beneficio` |
| `/adiantamentos` | GET | `adiantamentos` |
| `/adiantamentos/criar` | GET,POST | `criar_adiantamento` |
| `/adiantamentos/aprovar/<int:id>` | POST | `aprovar_adiantamento` |
| `/adiantamentos/rejeitar/<int:id>` | POST | `rejeitar_adiantamento` |
| `/relatorios` | GET | `relatorios` |
| `/relatorios/holerite/<int:folha_id>` | GET | `holerite_pdf` |
| `/api/funcionarios/folha/<int:ano>/<int:mes>` | GET | `api_funcionarios_folha` |
| `/relatorios/analitico/<int:ano>/<int:mes>` | GET | `relatorio_excel` |

**Modelos próprios (4):**

- **Adiantamento** (`adiantamento`, 15 col): `id`, `funcionario_id→funcionario`, `valor_total`, `data_solicitacao`, `data_aprovacao`, `aprovado_por→usuario`, `parcelas`, `valor_parcela`, `parcelas_pagas`, `status`, `motivo`, `observacoes`, `admin_id→usuario`, `created_at`, `updated_at`
- **BeneficioFuncionario** (`beneficio_funcionario`, 13 col): `id`, `funcionario_id→funcionario`, `tipo_beneficio`, `valor`, `percentual_desconto`, `dias_por_mes`, `ativo`, `data_inicio`, `data_fim`, `observacoes`, `admin_id→usuario`, `created_at`, `updated_at`
- **FolhaPagamento** (`folha_pagamento`, 31 col): `id`, `funcionario_id→funcionario`, `mes_referencia`, `salario_base`, `horas_extras`, `adicional_noturno`, `dsr`, `comissoes`, `bonus`, `outros_proventos`, `total_proventos`, `inss`, `irrf`, `fgts`, `vale_refeicao`, `vale_transporte`, `plano_saude`, `seguro_vida`, `faltas`, `atrasos`, `emprestimos`, `outros_descontos`, `total_descontos`, `salario_liquido`, `status`, `calculado_em`, `aprovado_em`, `aprovado_por→usuario`, `pago_em`, `observacoes`, `admin_id→usuario`
- **ParametrosLegais** (`parametros_legais`, 35 col): `id`, `admin_id→usuario`, `ano_vigencia`, `inss_faixa1_limite`, `inss_faixa1_percentual`, `inss_faixa2_limite`, `inss_faixa2_percentual`, `inss_faixa3_limite`, `inss_faixa3_percentual`, `inss_faixa4_limite`, `inss_faixa4_percentual`, `inss_teto`, `irrf_isencao`, `irrf_faixa1_limite`, `irrf_faixa1_percentual`, `irrf_faixa1_deducao`, `irrf_faixa2_limite`, `irrf_faixa2_percentual`, `irrf_faixa2_deducao`, `irrf_faixa3_limite`, `irrf_faixa3_percentual`, `irrf_faixa3_deducao`, `irrf_faixa4_percentual`, `irrf_faixa4_deducao`, `irrf_dependente_valor`, `fgts_percentual`, `salario_minimo`, `vale_transporte_percentual`, `adicional_noturno_percentual`, `hora_extra_50_percentual`, `hora_extra_100_percentual`, `tolerancia_minutos`, `ativo`, `created_at`, `updated_at`

**Modelos compartilhados que este módulo toca (5):** `ConfiguracaoEmpresa`, `Departamento`, `Funcionario`, `GestaoCustoFilho`, `GestaoCustoPai`

### Alimentação

Arquivos: `alimentacao_views.py`
Conferência: ☐ pendente

**Funcionalidades (14 rotas):**

| Rota | Métodos | Função |
|---|---|---|
| `/restaurantes` | GET | `restaurantes_lista` |
| `/restaurantes/novo` | GET,POST | `restaurante_novo` |
| `/restaurantes/<int:restaurante_id>/editar` | GET,POST | `restaurante_editar` |
| `/restaurante/<int:restaurante_id>` | GET | `restaurante_detalhes` |
| `/restaurantes/<int:restaurante_id>/deletar` | POST | `restaurante_deletar` |
| `/` | GET | `index` |
| `/lancamentos` | GET | `lancamentos_lista` |
| `/lancamentos/novo` | GET,POST | `lancamento_novo` |
| `/lancamentos/novo-v2` | GET,POST | `lancamento_novo_v2` |
| `/api/itens` | GET | `api_itens` |
| `/itens` | GET | `itens_lista` |
| `/itens/novo` | GET,POST | `item_novo` |
| `/itens/<int:item_id>/editar` | GET,POST | `item_editar` |
| `/dashboard` | GET | `dashboard` |

**Modelos próprios (2):**

- **AlimentacaoItem** (`alimentacao_item`, 11 col): `id`, `nome`, `preco_padrao`, `descricao`, `icone`, `ordem`, `ativo`, `is_default`, `admin_id→usuario`, `created_at`, `updated_at`
- **AlimentacaoLancamentoItem** (`alimentacao_lancamento_item`, 11 col): `id`, `lancamento_id→alimentacao_lancamento`, `item_id→alimentacao_item`, `nome_item`, `preco_unitario`, `quantidade`, `subtotal`, `funcionario_id→funcionario`, `centro_custo_id→centro_custo`, `admin_id→usuario`, `created_at`

**Modelos compartilhados que este módulo toca (8):** `AlimentacaoLancamento`, `CentroCusto`, `CustoObra`, `Funcionario`, `Obra`, `ObraServicoCusto`, `RegistroAlimentacao`, `Restaurante`

### Reembolso

Arquivos: `reembolso_views.py`
Conferência: ☐ pendente

**Funcionalidades (4 rotas):**

| Rota | Métodos | Função |
|---|---|---|
| `/` | GET | `index` |
| `/novo` | GET,POST | `novo` |
| `/<int:reembolso_id>/editar` | GET,POST | `editar` |
| `/<int:reembolso_id>/excluir` | POST | `excluir` |

**Modelos próprios (1):**

- **ReembolsoFuncionario** (`reembolso_funcionario`, 14 col) — também usado por Gestão de custos: `id`, `funcionario_id→funcionario`, `valor`, `data_despesa`, `descricao`, `categoria`, `obra_id→obra`, `centro_custo_id→centro_custo`, `comprovante_url`, `gestao_custo_pai_id→gestao_custo_pai`, `origem_tabela`, `origem_id`, `admin_id→usuario`, `created_at`

**Modelos compartilhados que este módulo toca (3):** `Funcionario`, `GestaoCustoPai`, `Obra`

### Subempreiteiros

Arquivos: `subempreiteiros_views.py`
Conferência: ☐ pendente

**Funcionalidades (6 rotas):**

| Rota | Métodos | Função |
|---|---|---|
| `/` | GET | `listar` |
| `/criar` | GET,POST | `criar` |
| `/<int:sub_id>/editar` | GET,POST | `editar` |
| `/<int:sub_id>/inativar` | POST | `inativar` |
| `/<int:sub_id>` | GET | `detalhe` |
| `/api/lista` | GET | `api_lista` |

**Modelos compartilhados que este módulo toca (6):** `GestaoCustoPai`, `Obra`, `RDO`, `RDOSubempreitadaApontamento`, `Subempreiteiro`, `TarefaCronograma`

### Financeiro

Arquivos: `financeiro_views.py`
Conferência: ☐ pendente

**Funcionalidades (24 rotas):**

| Rota | Métodos | Função |
|---|---|---|
| `/` | GET | `dashboard` |
| `/contas-pagar` | GET | `listar_contas_pagar` |
| `/contas-pagar/criar` | POST | `criar_conta_pagar` |
| `/contas-pagar/nova` | GET,POST | `nova_conta_pagar` |
| `/contas-pagar/<int:conta_id>/estornar` | POST | `estornar_conta` |
| `/gestao-custo/<int:gcp_id>/estornar` | POST | `estornar_gcp` |
| `/contas-pagar/<int:conta_id>/pagar` | GET,POST | `pagar_conta` |
| `/contas-receber` | GET | `listar_contas_receber` |
| `/contas-receber/criar` | POST | `criar_conta_receber` |
| `/contas-receber/nova` | GET,POST | `nova_conta_receber` |
| `/contas-receber/<int:conta_id>/receber` | GET,POST | `receber_conta` |
| `/contas-receber/<int:conta_id>/estornar` | POST | `estornar_recebimento` |
| `/fluxo-caixa` | GET | `fluxo_caixa` |
| `/fluxo-caixa/novo` | POST | `novo_fluxo_caixa` |
| `/fluxo-caixa/<int:fc_id>/editar` | POST | `editar_fluxo_caixa` |
| `/bancos` | GET | `listar_bancos` |
| `/bancos/criar` | POST | `criar_banco` |
| `/bancos/novo` | GET,POST | `novo_banco` |
| `/plano-contas` | GET | `plano_contas` |
| `/plano-contas/inicializar` | POST | `inicializar_plano_contas` |
| `/calendario-pagamentos` | GET,POST | `calendario_pagamentos` |
| `/calendario-pagamentos/configurar` | GET,POST | `calendario_pagamentos` |
| `/fechamento-pagamentos` | GET,POST | `fechamento_pagamentos` |
| `/api/kpis` | GET | `api_kpis` |

**Modelos próprios (3):**

- **DiaPagamentoConfig** (`dia_pagamento_config`, 4 col): `id`, `dia_do_mes`, `admin_id→usuario`, `created_at`
- **FechamentoPagamento** (`fechamento_pagamento`, 7 col): `id`, `data_fechamento`, `descricao`, `status`, `total_selecionado`, `admin_id→usuario`, `created_at`
- **PlanoContas** (`plano_contas`, 9 col) — também usado por Contabilidade: `admin_id→usuario`, `codigo`, `nome`, `tipo_conta`, `natureza`, `nivel`, `conta_pai_codigo`, `aceita_lancamento`, `ativo`

**Modelos compartilhados que este módulo toca (12):** `BancoEmpresa`, `CategoriaFluxoCaixa`, `CentroCusto`, `ContaPagar`, `ContaReceber`, `FluxoCaixa`, `Fornecedor`, `GestaoCustoFilho`, `GestaoCustoPai`, `LancamentoContabil`, `Obra`, `Usuario`

### Relatórios financeiros avançados

Arquivos: `relatorios_financeiros_avancados.py`
Conferência: ☐ pendente

**Funcionalidades (3 rotas):**

| Rota | Métodos | Função |
|---|---|---|
| `/` | GET | `dashboard_financeiro` |
| `/tco/<int:veiculo_id>` | GET | `relatorio_tco_detalhado` |
| `/api/dados-financeiros` | GET | `api_dados_financeiros` |

**Modelos compartilhados que este módulo toca (4):** `CustoVeiculo`, `Obra`, `UsoVeiculo`, `Veiculo`

### Contabilidade

Arquivos: `contabilidade_views.py`
Conferência: ☐ pendente

**Funcionalidades (24 rotas):**

| Rota | Métodos | Função |
|---|---|---|
| `/dashboard` | GET | `dashboard_contabil` |
| `/plano-contas` | GET | `plano_de_contas` |
| `/lancamentos` | GET | `lancamentos_contabeis` |
| `/lancamentos/criar` | GET,POST | `criar_lancamento` |
| `/lancamentos/<int:id>` | GET | `ver_lancamento` |
| `/lancamentos/editar/<int:id>` | GET,POST | `editar_lancamento` |
| `/lancamentos/estornar/<int:id>` | POST | `estornar_lancamento` |
| `/balancete` | GET | `balancete` |
| `/razao/<conta_codigo>` | GET | `razao` |
| `/dre` | GET | `dre` |
| `/balancete/pdf` | GET | `balancete_pdf` |
| `/balancete/excel` | GET | `balancete_excel` |
| `/dre/pdf` | GET | `dre_pdf` |
| `/dre/excel` | GET | `dre_excel` |
| `/balanco` | GET | `balanco_patrimonial` |
| `/auditoria` | GET | `auditoria_contabil` |
| `/relatorios` | GET | `relatorios` |
| `/centros-custo` | GET | `centros_custo` |
| `/centros-custo/criar` | GET,POST | `criar_centro_custo` |
| `/centros-custo/editar/<int:id>` | GET,POST | `editar_centro_custo` |
| `/centros-custo/desativar/<int:id>` | POST | `desativar_centro_custo` |
| `/centros-custo/<int:id>/custos` | GET | `centro_custo_custos` |
| `/sped` | GET | `sped` |
| `/api/processar-integracao` | POST | `processar_integracao` |

**Modelos próprios (7):**

- **AuditoriaContabil** (`auditoria_contabil`, 8 col): `id`, `data_auditoria`, `tipo_verificacao`, `resultado`, `observacoes`, `valor_divergencia`, `corrigido`, `admin_id→usuario`
- **BalancoPatrimonial** (`balanco_patrimonial`, 6 col): `id`, `data_referencia`, `total_ativo`, `total_passivo_patrimonio`, `admin_id→usuario`, `processado_em`
- **CentroCustoContabil** (`centro_custo_contabil`, 9 col): `id`, `codigo`, `nome`, `tipo`, `descricao`, `obra_id→obra`, `ativo`, `admin_id→usuario`, `created_at`
- **DREMensal** (`dre_mensal`, 12 col): `id`, `mes_referencia`, `receita_bruta`, `impostos_sobre_vendas`, `receita_liquida`, `custo_total`, `lucro_bruto`, `total_despesas`, `lucro_operacional`, `lucro_liquido`, `admin_id→usuario`, `processado_em`
- **PartidaContabil** (`partida_contabil`, 9 col): `id`, `lancamento_id→lancamento_contabil`, `sequencia`, `conta_codigo`, `centro_custo_id→centro_custo_contabil`, `tipo_partida`, `valor`, `historico_complementar`, `admin_id→usuario`
- **PlanoContas** (`plano_contas`, 9 col) — também usado por Financeiro: `admin_id→usuario`, `codigo`, `nome`, `tipo_conta`, `natureza`, `nivel`, `conta_pai_codigo`, `aceita_lancamento`, `ativo`
- **SpedContabil** (`sped_contabil`, 8 col): `id`, `periodo_inicial`, `periodo_final`, `arquivo_gerado`, `hash_arquivo`, `status`, `data_geracao`, `admin_id→usuario`

**Modelos compartilhados que este módulo toca (2):** `LancamentoContabil`, `Obra`

### Custos de obra

Arquivos: `custos_views.py`
Conferência: ☐ pendente

**Funcionalidades (8 rotas):**

| Rota | Métodos | Função |
|---|---|---|
| `/` | GET | `dashboard_custos` |
| `/obra/<int:obra_id>` | GET | `custos_obra` |
| `/api/custos-categoria` | GET | `api_custos_categoria` |
| `/api/custos-mensais` | GET | `api_custos_mensais` |
| `/criar` | GET,POST | `criar_custo` |
| `/editar/<int:custo_id>` | GET,POST | `editar_custo` |
| `/deletar/<int:custo_id>` | POST | `deletar_custo` |
| `/listar` | GET | `listar_custos` |

**Modelos compartilhados que este módulo toca (2):** `CustoObra`, `Obra`

### Gestão de custos

Arquivos: `gestao_custos_views.py`
Conferência: ☐ pendente

**Funcionalidades (12 rotas):**

| Rota | Métodos | Função |
|---|---|---|
| `/` | GET | `index` |
| `/novo` | GET,POST | `novo` |
| `/obra/<int:obra_id>/servicos` | GET | `servicos_da_obra` |
| `/<int:pai_id>/filhos` | GET | `filhos` |
| `/filho/<int:filho_id>/editar` | POST | `editar_filho` |
| `/filho/<int:filho_id>/excluir` | POST | `excluir_filho` |
| `/<int:pai_id>/solicitar` | POST | `solicitar` |
| `/<int:pai_id>/autorizar` | POST | `autorizar` |
| `/<int:pai_id>/pagar` | POST | `pagar` |
| `/<int:pai_id>/editar` | GET,POST | `editar` |
| `/<int:pai_id>/excluir` | POST | `excluir` |
| `/migrar-contas-pagar` | POST | `migrar_contas_pagar` |

**Modelos próprios (1):**

- **ReembolsoFuncionario** (`reembolso_funcionario`, 14 col) — também usado por Reembolso: `id`, `funcionario_id→funcionario`, `valor`, `data_despesa`, `descricao`, `categoria`, `obra_id→obra`, `centro_custo_id→centro_custo`, `comprovante_url`, `gestao_custo_pai_id→gestao_custo_pai`, `origem_tabela`, `origem_id`, `admin_id→usuario`, `created_at`

**Modelos compartilhados que este módulo toca (14):** `AlimentacaoLancamento`, `BancoEmpresa`, `ContaPagar`, `FluxoCaixa`, `Fornecedor`, `GestaoCustoFilho`, `GestaoCustoPai`, `LancamentoTransporte`, `Obra`, `ObraServicoCusto`, `RDO`, `RDOMaoObra`, `RegistroPonto`, `Subempreiteiro`

### Custos de escritório

Arquivos: `custos_escritorio_views.py`
Conferência: ☐ pendente

**Funcionalidades (12 rotas):**

| Rota | Métodos | Função |
|---|---|---|
| `/categorias` | GET | `categorias` |
| `/categorias/nova` | GET,POST | `nova_categoria` |
| `/categorias/<int:cat_id>/editar` | GET,POST | `editar_categoria` |
| `/categorias/<int:cat_id>/toggle` | POST | `toggle_categoria` |
| `/despesas` | GET | `despesas` |
| `/despesas/nova` | GET,POST | `nova_despesa` |
| `/despesas/<int:desp_id>/editar` | GET,POST | `editar_despesa` |
| `/despesas/<int:desp_id>/toggle` | POST | `toggle_despesa` |
| `/despesas/<int:desp_id>/criar-ocorrencia` | POST | `criar_ocorrencia_avulsa` |
| `/ocorrencias/<int:oc_id>/excluir` | POST | `excluir_ocorrencia` |
| `/painel` | GET | `painel_mensal` |
| `/painel/gerar-mes` | POST | `gerar_mes` |

**Modelos próprios (3):**

- **CategoriaEscritorio** (`categoria_escritorio`, 6 col) — também usado por Obras/Dashboard/base (main): `id`, `nome`, `cor`, `ativo`, `admin_id→usuario`, `created_at`
- **DespesaEscritorio** (`despesa_escritorio`, 9 col): `id`, `nome`, `categoria_id→categoria_escritorio`, `valor`, `dia_vencimento`, `recorrente`, `ativo`, `admin_id→usuario`, `created_at`
- **DespesaEscritorioOcorrencia** (`despesa_escritorio_ocorrencia`, 9 col): `id`, `despesa_id→despesa_escritorio`, `competencia_ano`, `competencia_mes`, `data_vencimento`, `valor`, `conta_pagar_id→conta_pagar`, `admin_id→usuario`, `created_at`

**Modelos compartilhados que este módulo toca (1):** `ContaPagar`

### Planejamento de custos

Arquivos: `views/planejamento_custos_views.py`
Conferência: ☐ pendente

**Funcionalidades (8 rotas):**

| Rota | Métodos | Função |
|---|---|---|
| `/` | GET | `lista` |
| `/notificacoes/<int:notif_id>/resolver` | POST | `resolver_notificacao` |
| `/novo` | GET,POST | `novo` |
| `/<int:svc_id>/editar` | GET,POST | `editar` |
| `/<int:svc_id>/equipe` | GET,POST | `equipe` |
| `/<int:svc_id>/cotacoes` | GET,POST | `cotacoes` |
| `/<int:svc_id>/excluir` | POST | `excluir` |
| `/<int:svc_id>/vincular-item-comercial` | POST | `vincular_item_comercial` |

**Modelos próprios (3):**

- **ObraServicoCotacaoInterna** (`obra_servico_cotacao_interna`, 10 col): `id`, `admin_id→usuario`, `obra_servico_custo_id→obra_servico_custo`, `fornecedor_nome`, `fornecedor_id→fornecedor`, `prazo_entrega`, `condicao_pagamento`, `observacoes`, `selecionada`, `created_at`
- **ObraServicoCotacaoInternaLinha** (`obra_servico_cotacao_interna_linha`, 7 col): `id`, `admin_id→usuario`, `cotacao_id→obra_servico_cotacao_interna`, `descricao`, `unidade`, `quantidade`, `valor_unitario`
- **ObraServicoEquipePlanejada** (`obra_servico_equipe_planejada`, 11 col): `id`, `admin_id→usuario`, `obra_servico_custo_id→obra_servico_custo`, `funcionario_id→funcionario`, `funcionario_nome`, `quantidade_dias`, `diaria`, `almoco_e_cafe`, `transporte`, `observacoes`, `created_at`

**Modelos compartilhados que este módulo toca (5):** `Fornecedor`, `Funcionario`, `ItemMedicaoComercial`, `Obra`, `ObraServicoCusto`

### CRM

Arquivos: `crm_views.py`
Conferência: ☐ pendente

**Funcionalidades (23 rotas):**

| Rota | Métodos | Função |
|---|---|---|
| `/` | GET | `kanban` |
| `/lista` | GET | `lista` |
| `/clientes/buscar` | GET | `buscar_clientes` |
| `/novo` | GET,POST | `novo` |
| `/<int:lead_id>/editar` | GET,POST | `editar` |
| `/<int:lead_id>/aprovar_validacao` | POST | `aprovar_validacao` |
| `/<int:lead_id>/rejeitar_validacao` | POST | `rejeitar_validacao` |
| `/<int:lead_id>/enviar_proposta` | POST | `enviar_proposta` |
| `/<int:lead_id>/excluir` | POST | `excluir` |
| `/<int:lead_id>/mudar_status` | POST | `mudar_status` |
| `/<int:lead_id>/gerar_proposta` | GET | `gerar_proposta` |
| `/<int:lead_id>/criar_obra` | GET | `criar_obra` |
| `/cadastros` | GET | `cadastros` |
| `/cadastros/<slug>/criar` | POST | `cadastros_criar` |
| `/cadastros/<slug>/<int:item_id>/editar` | POST | `cadastros_editar` |
| `/cadastros/<slug>/<int:item_id>/toggle_ativo` | POST | `cadastros_toggle` |
| `/cadastros/<slug>/<int:item_id>/excluir` | POST | `cadastros_excluir` |
| `/cadastros/<slug>/itens` | GET | `cadastros_itens` |
| `/exportar_modelo` | GET | `exportar_modelo` |
| `/exportar` | GET | `exportar` |
| `/importar` | POST | `importar` |
| `/clientes/<int:cliente_id>` | GET | `detalhe_cliente` |
| `/clientes/<int:cliente_id>/observacao` | POST | `adicionar_observacao_cliente` |

**Modelos próprios (9):**

- **ClienteObservacao** (`cliente_observacao`, 6 col): `id`, `cliente_id→cliente`, `admin_id→usuario`, `usuario_id→usuario`, `texto`, `created_at`
- **CrmCadencia** (`crm_cadencia`, 5 col): `id`, `admin_id→usuario`, `nome`, `ativo`, `created_at`
- **CrmMotivoPerda** (`crm_motivo_perda`, 5 col): `id`, `admin_id→usuario`, `nome`, `ativo`, `created_at`
- **CrmOrigem** (`crm_origem`, 5 col): `id`, `admin_id→usuario`, `nome`, `ativo`, `created_at`
- **CrmResponsavel** (`crm_responsavel`, 5 col): `id`, `admin_id→usuario`, `nome`, `ativo`, `created_at`
- **CrmSituacao** (`crm_situacao`, 5 col): `id`, `admin_id→usuario`, `nome`, `ativo`, `created_at`
- **CrmTipoMaterial** (`crm_tipo_material`, 5 col): `id`, `admin_id→usuario`, `nome`, `ativo`, `created_at`
- **CrmTipoObra** (`crm_tipo_obra`, 5 col): `id`, `admin_id→usuario`, `nome`, `ativo`, `created_at`
- **LeadHistorico** (`lead_historico`, 9 col): `id`, `lead_id→lead`, `admin_id→usuario`, `campo`, `valor_antes`, `valor_depois`, `descricao`, `usuario_id→usuario`, `created_at`

**Modelos compartilhados que este módulo toca (5):** `Cliente`, `Lead`, `Obra`, `Proposta`, `Usuario`

### Clientes

Arquivos: `clientes_views.py`
Conferência: ☐ pendente

**Funcionalidades (5 rotas):**

| Rota | Métodos | Função |
|---|---|---|
| `/` | GET | `listar` |
| `/novo` | GET,POST | `criar` |
| `/<int:id>/editar` | GET,POST | `editar` |
| `/api/buscar` | GET | `api_buscar` |
| `/<int:id>/excluir` | POST | `excluir` |

**Modelos próprios (1):**

- **Orcamento** (`orcamento`, 17 col) — também usado por Orçamentos: `id`, `admin_id→usuario`, `numero`, `titulo`, `descricao`, `cliente_id→cliente`, `cliente_nome`, `imposto_pct_global`, `margem_pct_global`, `custo_total`, `venda_total`, `lucro_total`, `status`, `ultima_proposta_id→propostas_comerciais`, `criado_por→usuario`, `criado_em`, `atualizado_em`

**Modelos compartilhados que este módulo toca (3):** `Cliente`, `Obra`, `Proposta`

### Propostas

Arquivos: `propostas_consolidated.py`
Conferência: ☐ pendente

**Funcionalidades (35 rotas):**

| Rota | Métodos | Função |
|---|---|---|
| `/` | GET | `index` |
| `/dashboard` | GET | `dashboard` |
| `/nova` | GET | `nova` |
| `/criar` | POST | `criar` |
| `/<int:id>` | GET | `visualizar` |
| `/<int:id>/observacao-validacao` | POST | `salvar_observacao_validacao` |
| `/<int:id>/status` | POST | `alterar_status` |
| `/<int:id>/pdf` | GET | `gerar_pdf` |
| `/listar` | GET | `listar` |
| `/nova-proposta` | GET | `nova_proposta` |
| `/criar-proposta` | GET,POST | `criar_proposta` |
| `/editar/<int:id>` | GET | `editar` |
| `/<int:id>/nova-versao` | POST | `criar_nova_versao` |
| `/<int:id>/enviar` | POST | `enviar` |
| `/<int:id>/whatsapp/registrar` | POST | `whatsapp_registrar` |
| `/editar/<int:id>` | POST | `atualizar` |
| `/deletar/<int:id>` | POST | `deletar` |
| `/templates` | GET | `listar_templates` |
| `/templates/novo` | GET | `novo_template` |
| `/templates/criar` | POST | `criar_template` |
| `/templates/<int:id>/editar` | GET | `editar_template` |
| `/templates/<int:id>/atualizar` | POST | `atualizar_template` |
| `/templates/<int:id>/marcar-padrao` | POST | `marcar_padrao_template` |
| `/<int:id>/cronograma-revisar` | GET | `cronograma_revisar` |
| `/<int:id>/cronograma-preview` | GET | `cronograma_preview_json` |
| `/<int:id>/cronograma-default` | POST | `salvar_cronograma_default` |
| `/aprovar/<int:id>` | POST | `aprovar` |
| `/rejeitar/<int:id>` | POST | `rejeitar` |
| `/cliente/<token>` | GET | `portal_cliente` |
| `/cliente/<token>/aprovar` | POST | `aprovar_proposta_cliente` |
| `/cliente/<token>/rejeitar` | POST | `rejeitar_proposta_cliente` |
| `/api/clientes` | GET | `api_clientes` |
| `/<int:id>/upload-arquivo` | POST | `upload_arquivo` |
| `/arquivo/<int:arquivo_id>` | GET | `download_arquivo` |
| `/arquivo/<int:arquivo_id>/delete` | POST | `deletar_arquivo` |

**Modelos próprios (4):**

- **EngenheiroResponsavel** (`engenheiro_responsavel`, 12 col) — também usado por Configurações: `id`, `admin_id→usuario`, `nome`, `crea`, `email`, `telefone`, `endereco`, `website`, `assinatura_base64`, `ativo`, `criado_em`, `atualizado_em`
- **PropostaArquivo** (`proposta_arquivos`, 15 col): `id`, `admin_id→usuario`, `proposta_id→propostas_comerciais`, `nome_arquivo`, `nome_original`, `tipo_arquivo`, `tamanho_bytes`, `caminho_arquivo`, `categoria`, `arquivo_base64`, `imagem_original_base64`, `imagem_otimizada_base64`, `thumbnail_base64`, `enviado_por→usuario`, `enviado_em`
- **PropostaClausula** (`proposta_clausula`, 9 col) — também usado por Orçamentos: `id`, `proposta_id→propostas_comerciais`, `admin_id→usuario`, `titulo`, `texto`, `ordem`, `criado_em`, `atualizado_em`, `revisado_em`
- **PropostaTemplateClausula** (`proposta_template_clausula`, 8 col) — também usado por Orçamentos: `id`, `proposta_template_id→proposta_templates`, `admin_id→usuario`, `titulo`, `texto`, `ordem`, `criado_em`, `atualizado_em`

**Modelos compartilhados que este módulo toca (14):** `Cliente`, `ConfiguracaoEmpresa`, `ContaReceber`, `ItemMedicaoComercial`, `LancamentoContabil`, `Lead`, `Obra`, `Proposta`, `PropostaHistorico`, `PropostaItem`, `PropostaTemplate`, `Servico`, `TarefaCronograma`, `Usuario`

### Orçamentos

Arquivos: `views/orcamentos_views.py`
Conferência: ☐ pendente

**Funcionalidades (13 rotas):**

| Rota | Métodos | Função |
|---|---|---|
| `/` | GET | `listar` |
| `/novo` | GET,POST | `novo` |
| `/<int:id>/editar` | GET | `editar` |
| `/<int:id>/atualizar` | POST | `atualizar` |
| `/<int:id>/itens` | POST | `adicionar_item` |
| `/itens/<int:item_id>/atualizar` | POST | `atualizar_item` |
| `/itens/<int:item_id>/reset-composicao` | POST | `reset_composicao` |
| `/itens/<int:item_id>/remover` | POST | `remover_item` |
| `/<int:id>/excluir` | POST | `excluir` |
| `/<int:id>/duplicar` | POST | `duplicar` |
| `/<int:id>/gerar-proposta` | POST | `gerar_proposta` |
| `/<int:id>/preview-cronograma` | GET | `preview_cronograma` |
| `/api/servicos/<int:servico_id>/composicao` | GET | `api_composicao_servico` |

**Modelos próprios (4):**

- **Orcamento** (`orcamento`, 17 col) — também usado por Clientes: `id`, `admin_id→usuario`, `numero`, `titulo`, `descricao`, `cliente_id→cliente`, `cliente_nome`, `imposto_pct_global`, `margem_pct_global`, `custo_total`, `venda_total`, `lucro_total`, `status`, `ultima_proposta_id→propostas_comerciais`, `criado_por→usuario`, `criado_em`, `atualizado_em`
- **OrcamentoItem** (`orcamento_item`, 27 col) — também usado por Catálogo de serviços: `id`, `admin_id→usuario`, `orcamento_id→orcamento`, `ordem`, `servico_id→servico`, `descricao`, `unidade`, `quantidade`, `imposto_pct`, `margem_pct`, `composicao_snapshot`, `cronograma_template_override_id→cronograma_template`, `custo_unitario`, `preco_venda_unitario`, `custo_total`, `venda_total`, `lucro_total`, `observacao`, `itens_inclusos`, `itens_exclusos`, `tipo_medicao_override`, `dim_largura`, `dim_comprimento`, `dim_perimetro`, `dim_pe_direito`, `dim_area_manual`, `criado_em`
- **PropostaClausula** (`proposta_clausula`, 9 col) — também usado por Propostas: `id`, `proposta_id→propostas_comerciais`, `admin_id→usuario`, `titulo`, `texto`, `ordem`, `criado_em`, `atualizado_em`, `revisado_em`
- **PropostaTemplateClausula** (`proposta_template_clausula`, 8 col) — também usado por Propostas: `id`, `proposta_template_id→proposta_templates`, `admin_id→usuario`, `titulo`, `texto`, `ordem`, `criado_em`, `atualizado_em`

**Modelos compartilhados que este módulo toca (11):** `Cliente`, `ConfiguracaoEmpresa`, `CronogramaTemplate`, `Obra`, `ObraOrcamentoOperacional`, `Proposta`, `PropostaHistorico`, `PropostaItem`, `PropostaTemplate`, `Servico`, `TarefaCronograma`

### Orçamento operacional

Arquivos: `views/orcamento_operacional_views.py`
Conferência: ☐ pendente

**Funcionalidades (3 rotas):**

| Rota | Métodos | Função |
|---|---|---|
| `/` | GET | `index` |
| `/item/<int:item_id>/salvar` | POST | `salvar_item` |
| `/atualizar-do-original` | POST | `atualizar_do_original_route` |

**Modelos próprios (2):**

- **ObraOrcamentoOperacionalItem** (`obra_orcamento_operacional_item`, 9 col): `id`, `operacional_id→obra_orcamento_operacional`, `admin_id→usuario`, `orcamento_item_origem_id→orcamento_item`, `servico_id→servico`, `descricao`, `unidade`, `quantidade`, `created_at`
- **ObraOrcamentoOperacionalItemVersao** (`obra_orcamento_operacional_item_versao`, 12 col): `id`, `item_id→obra_orcamento_operacional_item`, `admin_id→usuario`, `composicao_snapshot`, `margem_pct`, `imposto_pct`, `vigente_de`, `vigente_ate`, `modo_aplicacao`, `motivo`, `criado_por_id→usuario`, `created_at`

**Modelos compartilhados que este módulo toca (2):** `Obra`, `ObraOrcamentoOperacional`

### Catálogo de serviços

Arquivos: `views/catalogo_views.py`
Conferência: ☐ pendente

**Funcionalidades (31 rotas):**

| Rota | Métodos | Função |
|---|---|---|
| `/insumos` | GET | `insumos_list` |
| `/insumos/novo` | GET,POST | `insumo_novo` |
| `/insumos/<int:insumo_id>` | GET,POST | `insumo_editar` |
| `/insumos/<int:insumo_id>/preco` | POST | `insumo_novo_preco` |
| `/insumos/<int:insumo_id>/excluir` | POST | `insumo_excluir` |
| `/insumos/modelo-excel` | GET | `insumos_modelo_excel` |
| `/insumos/importar-excel` | POST | `insumos_importar_excel` |
| `/servicos/composicoes/modelo-excel` | GET | `composicoes_modelo_excel` |
| `/servicos/composicoes/importar-excel` | POST | `composicoes_importar_excel` |
| `/servicos` | GET | `servicos_list` |
| `/servicos/novo` | GET,POST | `servico_novo` |
| `/servicos/<int:servico_id>/composicao` | GET | `servico_composicao` |
| `/servicos/<int:servico_id>/template` | POST | `servico_vincular_template` |
| `/servicos/<int:servico_id>/composicao/add` | POST | `servico_composicao_add` |
| `/servicos/<int:servico_id>/composicao/<int:comp_id>/excluir` | POST | `servico_composicao_excluir` |
| `/servicos/<int:servico_id>/composicao/<int:comp_id>/editar` | POST | `servico_composicao_editar` |
| `/servicos/<int:servico_id>/excluir` | POST | `servico_excluir` |
| `/servicos/<int:servico_id>/preco` | POST | `servico_atualizar_preco` |
| `/servicos/<int:servico_id>/editar` | POST | `servico_editar` |
| `/servicos/<int:servico_id>/historico-obras` | GET | `servico_historico` |
| `/api/servicos/buscar` | GET | `api_buscar_servicos` |
| `/api/servicos/<int:servico_id>/explodir` | GET | `api_explodir_servico` |
| `/api/insumos/buscar` | GET | `api_buscar_insumos` |
| `/proposta-itens/<int:item_id>/vincular-servico` | POST | `vincular_proposta_item` |
| `/medicao-itens/<int:item_id>/vincular-servico` | POST | `vincular_medicao_item` |
| `/servicos/buscar` | GET | `api_alias_servicos` |
| `/insumos/buscar` | GET | `api_alias_insumos` |
| `/propostas/<int:id>/itens/<int:item_id>/vincular-servico` | POST | `alias_vincular_proposta_item_spec` |
| `/medicao/obra/<int:id>/itens/<int:item_id>/vincular-servico` | POST | `alias_vincular_medicao_item_spec` |
| `/propostas/itens/<int:item_id>/vincular-servico` | POST | `alias_vincular_proposta_item` |
| `/medicao/obra/itens/<int:item_id>/vincular-servico` | POST | `alias_vincular_medicao_item` |

**Modelos próprios (3):**

- **ComposicaoServico** (`composicao_servico`, 8 col) — também usado por Cronograma: `id`, `admin_id→usuario`, `servico_id→servico`, `insumo_id→insumo`, `coeficiente`, `unidade`, `observacao`, `created_at`
- **OrcamentoItem** (`orcamento_item`, 27 col) — também usado por Orçamentos: `id`, `admin_id→usuario`, `orcamento_id→orcamento`, `ordem`, `servico_id→servico`, `descricao`, `unidade`, `quantidade`, `imposto_pct`, `margem_pct`, `composicao_snapshot`, `cronograma_template_override_id→cronograma_template`, `custo_unitario`, `preco_venda_unitario`, `custo_total`, `venda_total`, `lucro_total`, `observacao`, `itens_inclusos`, `itens_exclusos`, `tipo_medicao_override`, `dim_largura`, `dim_comprimento`, `dim_perimetro`, `dim_pe_direito`, `dim_area_manual`, `criado_em`
- **PrecoBaseInsumo** (`preco_base_insumo`, 8 col): `id`, `admin_id→usuario`, `insumo_id→insumo`, `valor`, `vigencia_inicio`, `vigencia_fim`, `observacao`, `created_at`

**Modelos compartilhados que este módulo toca (7):** `CronogramaTemplate`, `Insumo`, `ItemMedicaoComercial`, `Obra`, `ObraServicoCusto`, `PropostaItem`, `Servico`

### Categorias de serviços

Arquivos: `categoria_servicos.py`
Conferência: ☐ pendente

**Funcionalidades (5 rotas):**

| Rota | Métodos | Função |
|---|---|---|
| `/` | GET | `index` |
| `/api/listar` | GET | `api_listar_categorias` |
| `/api/criar` | POST | `api_criar_categoria` |
| `/api/<int:categoria_id>/excluir` | DELETE | `api_excluir_categoria` |
| `/api/<int:categoria_id>/editar` | POST | `api_editar_categoria` |

**Modelos próprios (1):**

- **CategoriaServico** (`categoria_servico`, 10 col): `id`, `nome`, `descricao`, `cor`, `icone`, `ordem`, `ativo`, `admin_id→usuario`, `created_at`, `updated_at`

### Serviço da obra (real)

Arquivos: `crud_servico_obra_real.py`
Conferência: ☐ pendente

**Funcionalidades (5 rotas):**

| Rota | Métodos | Função |
|---|---|---|
| `/obra/<int:obra_id>/servicos-reais` | GET | `listar_servicos_reais` |
| `/obra/<int:obra_id>/servico-real/novo` | GET,POST | `novo_servico_real` |
| `/servico-real/<int:servico_real_id>/atualizar-progresso` | POST | `atualizar_progresso` |
| `/servico-real/<int:servico_real_id>/aprovar` | POST | `aprovar_servico` |
| `/api/obra/<int:obra_id>/servicos-reais` | GET | `api_servicos_reais` |

**Modelos compartilhados que este módulo toca (4):** `Funcionario`, `Obra`, `Servico`, `ServicoObraReal`

### Serviços da obra (API)

Arquivos: `api_servicos_obra_limpa.py`
Conferência: ☐ pendente

**Funcionalidades (4 rotas):**

| Rota | Métodos | Função |
|---|---|---|
| `/api/obra/<int:obra_id>/servicos` | GET | `listar_servicos_obra` |
| `/api/obra/<int:obra_id>/servicos` | POST | `adicionar_servico_obra` |
| `/api/obra/<int:obra_id>/servico/<int:servico_obra_id>` | PUT | `atualizar_servico_obra` |
| `/api/obra/<int:obra_id>/servico/<int:servico_obra_id>` | DELETE | `remover_servico_obra` |

**Modelos compartilhados que este módulo toca (3):** `Servico`, `ServicoObraReal`, `Usuario`

### Cadastrar serviço na obra

Arquivos: `cadastrar_servico_obra.py`
Conferência: ☐ pendente

**Funcionalidades (1 rotas):**

| Rota | Métodos | Função |
|---|---|---|
| `/obra/<int:obra_id>/cadastrar-servico` | GET,POST | `cadastrar_servico_obra` |

**Modelos compartilhados que este módulo toca (2):** `Obra`, `Servico`

### Almoxarifado

Arquivos: `views/almoxarifado/__init__.py`, `views/almoxarifado/api.py`, `views/almoxarifado/categorias.py`, `views/almoxarifado/dashboard.py`, `views/almoxarifado/fornecedores.py`, `views/almoxarifado/itens.py`, `views/almoxarifado/movimentos.py`, `views/almoxarifado/relatorios.py`
Conferência: ☐ pendente

**Funcionalidades (37 rotas):**

| Rota | Métodos | Função |
|---|---|---|
| `/api/item/<int:id>` | GET | `api_item_info` |
| `/api/estoque-disponivel/<int:item_id>` | GET | `api_estoque_disponivel` |
| `/api/lotes-disponiveis/<int:item_id>` | GET | `api_lotes_disponiveis` |
| `/api/itens-funcionario/<int:funcionario_id>` | GET | `api_itens_funcionario` |
| `/categorias` | GET | `categorias` |
| `/categorias/criar` | GET,POST | `categorias_criar` |
| `/categorias/editar/<int:id>` | GET,POST | `categorias_editar` |
| `/categorias/deletar/<int:id>` | POST | `categorias_deletar` |
| `/` | GET | `dashboard` |
| `/fornecedores` | GET | `fornecedores` |
| `/fornecedores/criar` | GET,POST | `fornecedores_criar` |
| `/fornecedores/editar/<int:id>` | GET,POST | `fornecedores_editar` |
| `/fornecedores/modelo-excel` | GET | `fornecedores_modelo_excel` |
| `/fornecedores/importar-excel` | POST | `fornecedores_importar_excel` |
| `/fornecedores/importar-confirmar` | POST | `fornecedores_importar_confirmar` |
| `/fornecedores/deletar/<int:id>` | POST | `fornecedores_deletar` |
| `/itens` | GET | `itens` |
| `/itens/criar` | GET,POST | `itens_criar` |
| `/itens/editar/<int:id>` | GET,POST | `itens_editar` |
| `/itens/<int:id>` | GET | `itens_detalhes` |
| `/itens/<int:id>/movimentacoes` | GET | `itens_movimentacoes` |
| `/itens/deletar/<int:id>` | POST | `itens_deletar` |
| `/entrada` | GET,POST | `entrada` |
| `/processar-entrada` | POST | `processar_entrada` |
| `/processar-entrada-multipla` | POST | `processar_entrada_multipla` |
| `/saida` | GET | `saida` |
| `/processar-saida` | POST | `processar_saida` |
| `/processar-saida-multipla` | POST | `processar_saida_multipla` |
| `/devolucao` | GET | `devolucao` |
| `/processar-devolucao` | POST | `processar_devolucao` |
| `/processar-consumo` | POST | `processar_consumo` |
| `/processar-devolucao-multipla` | POST | `processar_devolucao_multipla` |
| `/movimentacoes` | GET | `movimentacoes` |
| `/movimentacoes/criar` | GET,POST | `movimentacoes_criar` |
| `/movimentacoes/editar/<int:id>` | GET,POST | `movimentacoes_editar` |
| `/movimentacoes/deletar/<int:id>` | POST | `movimentacoes_deletar` |
| `/relatorios` | GET | `relatorios` |

**Modelos próprios (2):**

- **AlmoxarifadoCategoria** (`almoxarifado_categoria`, 7 col): `id`, `nome`, `tipo_controle_padrao`, `permite_devolucao_padrao`, `admin_id→usuario`, `created_at`, `updated_at`
- **NotaFiscal** (`nota_fiscal`, 20 col): `id`, `numero`, `serie`, `chave_acesso`, `fornecedor_id→fornecedor`, `data_emissao`, `data_entrada`, `valor_produtos`, `valor_frete`, `valor_desconto`, `valor_total`, `xml_content`, `xml_hash`, `status`, `observacoes`, `processada_por_id→usuario`, `data_processamento`, `admin_id→usuario`, `created_at`, `updated_at`

**Modelos compartilhados que este módulo toca (7):** `AlmoxarifadoEstoque`, `AlmoxarifadoItem`, `AlmoxarifadoMovimento`, `CategoriaFornecedor`, `Fornecedor`, `Funcionario`, `Obra`

### Compras

Arquivos: `compras_views.py`
Conferência: ☐ pendente

**Funcionalidades (18 rotas):**

| Rota | Métodos | Função |
|---|---|---|
| `/` | GET | `index` |
| `/aprovacao` | GET | `aprovacao` |
| `/nova` | GET | `nova` |
| `/nova` | POST | `nova_post` |
| `/<int:pedido_id>` | GET | `detalhe` |
| `/<int:pedido_id>/comprovante` | GET | `comprovante` |
| `/receber/<int:pedido_id>` | POST | `receber` |
| `/lancamento/<int:gcp_id>/editar` | POST | `editar_lancamento` |
| `/excluir/<int:pedido_id>` | POST | `excluir` |
| `/requisicoes` | GET | `requisicoes` |
| `/requisicoes/nova` | GET | `requisicao_nova` |
| `/requisicoes/nova` | POST | `requisicao_nova_post` |
| `/requisicoes/<int:requisicao_id>` | GET | `requisicao_detalhe` |
| `/requisicoes/<int:requisicao_id>/enviar` | POST | `requisicao_enviar` |
| `/requisicoes/<int:requisicao_id>/cancelar` | POST | `requisicao_cancelar` |
| `/requisicoes/<int:requisicao_id>/aprovar` | POST | `requisicao_aprovar` |
| `/requisicoes/<int:requisicao_id>/rejeitar` | POST | `requisicao_rejeitar` |
| `/requisicoes/<int:requisicao_id>/emitir-pedido` | POST | `requisicao_emitir_pedido` |

**Modelos próprios (4):**

- **PedidoCompraItem** (`pedido_compra_item`, 8 col) — também usado por Obras/Dashboard/base (main): `id`, `pedido_id→pedido_compra`, `almoxarifado_item_id→almoxarifado_item`, `descricao`, `quantidade`, `preco_unitario`, `subtotal`, `admin_id→usuario`
- **RequisicaoCompra** (`requisicao_compra`, 13 col): `id`, `numero`, `admin_id→usuario`, `obra_id→obra`, `obra_servico_custo_id→obra_servico_custo`, `solicitante_id→usuario`, `estado`, `justificativa`, `data_necessidade`, `valor_estimado`, `mapa_v2_id→mapa_concorrencia_v2`, `created_at`, `updated_at`
- **RequisicaoCompraItem** (`requisicao_compra_item`, 8 col): `id`, `requisicao_id→requisicao_compra`, `admin_id→usuario`, `almoxarifado_item_id→almoxarifado_item`, `descricao`, `unidade`, `quantidade`, `preco_estimado`
- **RequisicaoTransicao** (`requisicao_transicao`, 10 col): `id`, `requisicao_id→requisicao_compra`, `admin_id→usuario`, `de_estado`, `para_estado`, `usuario_id→usuario`, `papel_aplicado`, `valor_no_momento`, `motivo`, `criado_em`

**Modelos compartilhados que este módulo toca (15):** `AlmoxarifadoEstoque`, `AlmoxarifadoItem`, `AlmoxarifadoMovimento`, `Cliente`, `ContaPagar`, `FluxoCaixa`, `Fornecedor`, `Funcionario`, `GestaoCustoFilho`, `GestaoCustoPai`, `MapaConcorrenciaV2`, `Obra`, `ObraServicoCusto`, `PedidoCompra`, `Usuario`

### Frota

Arquivos: `frota_views.py`
Conferência: ☐ pendente

**Funcionalidades (13 rotas):**

| Rota | Métodos | Função |
|---|---|---|
| `/` | GET | `lista` |
| `/novo` | GET,POST | `novo` |
| `/<int:id>` | GET | `detalhes` |
| `/<int:id>/editar` | GET,POST | `editar` |
| `/<int:id>/reativar` | POST | `reativar` |
| `/<int:veiculo_id>/uso/novo` | GET,POST | `novo_uso` |
| `/<int:veiculo_id>/custo/novo` | GET,POST | `novo_custo` |
| `/uso/<int:uso_id>/editar` | GET,POST | `editar_uso` |
| `/uso/<int:uso_id>/deletar` | POST | `deletar_uso` |
| `/custo/<int:custo_id>/editar` | GET,POST | `editar_custo` |
| `/custo/<int:custo_id>/deletar` | POST | `deletar_custo` |
| `/<int:id>/deletar` | POST | `deletar_veiculo` |
| `/dashboard` | GET | `dashboard` |

**Modelos próprios (1):**

- **Vehicle** (`frota_veiculo`, 20 col) — também usado por Transporte: `id`, `placa`, `marca`, `modelo`, `ano`, `tipo`, `km_atual`, `cor`, `chassi`, `renavam`, `combustivel`, `ativo`, `data_ultima_manutencao`, `data_proxima_manutencao`, `km_proxima_manutencao`, `data_vencimento_ipva`, `data_vencimento_seguro`, `admin_id→usuario`, `created_at`, `updated_at`

**Modelos compartilhados que este módulo toca (5):** `CustoVeiculo`, `Funcionario`, `Obra`, `UsoVeiculo`, `Veiculo`

### Transporte

Arquivos: `transporte_views.py`
Conferência: ☐ pendente

**Funcionalidades (7 rotas):**

| Rota | Métodos | Função |
|---|---|---|
| `/` | GET | `index` |
| `/novo` | GET | `novo` |
| `/novo` | POST | `novo_post` |
| `/novo-massa` | GET | `novo_massa` |
| `/novo-massa` | POST | `novo_massa_post` |
| `/categorias` | GET,POST | `categorias` |
| `/excluir/<int:lancamento_id>` | POST | `excluir` |

**Modelos próprios (2):**

- **CategoriaTransporte** (`categoria_transporte`, 5 col): `id`, `nome`, `icone`, `admin_id→usuario`, `created_at`
- **Vehicle** (`frota_veiculo`, 20 col) — também usado por Frota: `id`, `placa`, `marca`, `modelo`, `ano`, `tipo`, `km_atual`, `cor`, `chassi`, `renavam`, `combustivel`, `ativo`, `data_ultima_manutencao`, `data_proxima_manutencao`, `km_proxima_manutencao`, `data_vencimento_ipva`, `data_vencimento_seguro`, `admin_id→usuario`, `created_at`, `updated_at`

**Modelos compartilhados que este módulo toca (8):** `CentroCusto`, `CustoObra`, `Funcionario`, `GestaoCustoFilho`, `GestaoCustoPai`, `LancamentoTransporte`, `Obra`, `ObraServicoCusto`

### Relatórios

Arquivos: `relatorios_funcionais.py`
Conferência: ☐ pendente

**Funcionalidades (2 rotas):**

| Rota | Métodos | Função |
|---|---|---|
| `/gerar/<tipo>` | POST | `gerar_relatorio` |
| `/exportar/<formato>` | POST | `exportar_relatorio` |

**Modelos próprios (2):**

- **FuncionarioObrasPonto** (`funcionario_obras_ponto`, 6 col) — também usado por Ponto: `id`, `funcionario_id→funcionario`, `obra_id→obra`, `admin_id→usuario`, `ativo`, `created_at`
- **Receita** (`receita`, 14 col) — também usado por Métricas: `id`, `admin_id→usuario`, `numero_receita`, `obra_id→obra`, `centro_custo_id→centro_custo`, `origem`, `descricao`, `valor`, `data_receita`, `data_recebimento`, `status`, `forma_recebimento`, `observacoes`, `created_at`

**Modelos compartilhados que este módulo toca (8):** `CustoObra`, `Departamento`, `Funcionario`, `Obra`, `RegistroAlimentacao`, `RegistroPonto`, `Restaurante`, `Veiculo`

### Exportação de relatórios

Arquivos: `exportacao_relatorios.py`
Conferência: ☐ pendente

**Funcionalidades (6 rotas):**

| Rota | Métodos | Função |
|---|---|---|
| `/` | GET | `painel_exportacao` |
| `/gerar-pdf` | GET | `gerar_pdf` |
| `/gerar-excel` | GET | `gerar_excel` |
| `/enviar-email` | POST | `enviar_relatorio_email` |
| `/api/preview-dados` | GET | `api_preview_dados` |
| `/agendar` | POST | `agendar_relatorio` |

**Modelos próprios (1):**

- **ManutencaoVeiculo** (`manutencao_veiculo`, 16 col) — também usado por Dashboards específicos: `id`, `veiculo_id→veiculo`, `data_manutencao`, `tipo_manutencao`, `descricao`, `fornecedor`, `valor`, `km_veiculo`, `proxima_manutencao_km`, `proxima_manutencao_data`, `numero_nota_fiscal`, `status`, `observacoes`, `admin_id→usuario`, `created_at`, `updated_at`

**Modelos compartilhados que este módulo toca (3):** `CustoVeiculo`, `UsoVeiculo`, `Veiculo`

### Analytics preditivos

Arquivos: `analytics_preditivos.py`
Conferência: ☐ pendente

**Funcionalidades (3 rotas):**

| Rota | Métodos | Função |
|---|---|---|
| `/` | GET | `dashboard_analytics` |
| `/api/executar-analise` | POST | `api_executar_analise` |
| `/relatorio-preditivo` | GET | `relatorio_preditivo` |

### Dashboards específicos

Arquivos: `dashboards_especificos.py`
Conferência: ☐ pendente

**Funcionalidades (5 rotas):**

| Rota | Métodos | Função |
|---|---|---|
| `/manutencao` | GET | `dashboard_manutencao` |
| `/combustivel` | GET | `dashboard_combustivel` |
| `/obras` | GET | `dashboard_obras` |
| `/frota` | GET | `dashboard_frota` |
| `/api/dados-especificos` | GET | `api_dados_especificos` |

**Modelos próprios (1):**

- **ManutencaoVeiculo** (`manutencao_veiculo`, 16 col) — também usado por Exportação de relatórios: `id`, `veiculo_id→veiculo`, `data_manutencao`, `tipo_manutencao`, `descricao`, `fornecedor`, `valor`, `km_veiculo`, `proxima_manutencao_km`, `proxima_manutencao_data`, `numero_nota_fiscal`, `status`, `observacoes`, `admin_id→usuario`, `created_at`, `updated_at`

**Modelos compartilhados que este módulo toca (4):** `CustoVeiculo`, `Obra`, `UsoVeiculo`, `Veiculo`

### Métricas

Arquivos: `views/metricas_views.py`
Conferência: ☐ pendente

**Funcionalidades (7 rotas):**

| Rota | Métodos | Função |
|---|---|---|
| `/servico` | GET | `empresa_por_servico` |
| `/servico/aplicar-referencia/preview` | GET | `preview_referencia` |
| `/servico/aplicar-referencia` | POST | `aplicar_referencia` |
| `/funcionarios` | GET | `funcionarios` |
| `/divergencia/servico/<int:servico_id>` | GET | `divergencia_servico` |
| `/funcionarios/<int:funcionario_id>` | GET | `detalhe_funcionario` |
| `/ranking` | GET | `ranking` |

**Modelos próprios (1):**

- **Receita** (`receita`, 14 col) — também usado por Relatórios: `id`, `admin_id→usuario`, `numero_receita`, `obra_id→obra`, `centro_custo_id→centro_custo`, `origem`, `descricao`, `valor`, `data_receita`, `data_recebimento`, `status`, `forma_recebimento`, `observacoes`, `created_at`

**Modelos compartilhados que este módulo toca (5):** `Funcao`, `Funcionario`, `Obra`, `RDO`, `Servico`

### Configurações

Arquivos: `configuracoes_views.py`
Conferência: ☐ pendente

**Funcionalidades (22 rotas):**

| Rota | Métodos | Função |
|---|---|---|
| `/` | GET | `configuracoes` |
| `/empresa` | GET | `empresa` |
| `/empresa/salvar` | POST | `salvar_empresa` |
| `/empresa/tema` | POST | `salvar_tema` |
| `/api/empresa` | GET | `api_empresa` |
| `/departamentos` | GET | `departamentos` |
| `/departamentos/criar` | GET,POST | `criar_departamento` |
| `/departamentos/editar/<int:id>` | GET,POST | `editar_departamento` |
| `/departamentos/deletar/<int:id>` | POST | `deletar_departamento` |
| `/funcoes` | GET | `funcoes` |
| `/funcoes/criar` | GET,POST | `criar_funcao` |
| `/funcoes/editar/<int:id>` | GET,POST | `editar_funcao` |
| `/funcoes/deletar/<int:id>` | POST | `deletar_funcao` |
| `/horarios` | GET | `horarios` |
| `/horarios/criar` | GET,POST | `criar_horario` |
| `/horarios/editar/<int:id>` | GET,POST | `editar_horario` |
| `/horarios/deletar/<int:id>` | POST | `deletar_horario` |
| `/engenheiros` | GET | `engenheiros` |
| `/engenheiros/novo` | GET,POST | `criar_engenheiro` |
| `/engenheiros/editar/<int:id>` | GET,POST | `editar_engenheiro` |
| `/engenheiros/inativar/<int:id>` | POST | `inativar_engenheiro` |
| `/engenheiros/reativar/<int:id>` | POST | `reativar_engenheiro` |

**Modelos próprios (2):**

- **EngenheiroResponsavel** (`engenheiro_responsavel`, 12 col) — também usado por Propostas: `id`, `admin_id→usuario`, `nome`, `crea`, `email`, `telefone`, `endereco`, `website`, `assinatura_base64`, `ativo`, `criado_em`, `atualizado_em`
- **HorarioDia** (`horario_dia`, 8 col) — também usado por Obras/Dashboard/base (main): `id`, `horario_id→horario_trabalho`, `dia_semana`, `entrada`, `saida`, `pausa_horas`, `trabalha`, `admin_id→usuario`

**Modelos compartilhados que este módulo toca (6):** `ConfiguracaoEmpresa`, `Departamento`, `Funcao`, `Funcionario`, `HorarioTrabalho`, `Insumo`

### Hub de cadastros

Arquivos: `cadastros_views.py`
Conferência: ☐ pendente

**Funcionalidades (8 rotas):**

| Rota | Métodos | Função |
|---|---|---|
| `/` | GET | `index` |
| `/dropdowns/<slug>` | GET | `dropdown_opcoes` |
| `/dropdowns/<slug>/criar` | POST | `dropdown_criar_opcao` |
| `/dropdowns/<slug>/<int:opcao_id>/editar` | POST | `dropdown_editar_opcao` |
| `/dropdowns/<slug>/<int:opcao_id>/toggle` | POST | `dropdown_toggle_ativo` |
| `/dropdowns/<slug>/<int:opcao_id>/verificar-uso` | GET | `dropdown_verificar_uso` |
| `/dropdowns/<slug>/<int:opcao_id>/excluir` | POST | `dropdown_excluir_opcao` |
| `/dropdowns/<slug>/<int:opcao_id>/mover/<direcao>` | POST | `dropdown_mover_opcao` |

**Modelos próprios (2):**

- **DropdownGrupo** (`dropdown_grupo`, 8 col): `id`, `admin_id→usuario`, `slug`, `label`, `modulo`, `descricao`, `editavel`, `created_at`
- **DropdownOpcao** (`dropdown_opcao`, 10 col): `id`, `admin_id→usuario`, `grupo_id→dropdown_grupo`, `valor`, `ordem`, `cor`, `ativo`, `protegido`, `ext_id`, `created_at`

### Quick-create

Arquivos: `views/quick_create_views.py`
Conferência: ☐ pendente

**Funcionalidades (4 rotas):**

| Rota | Métodos | Função |
|---|---|---|
| `/insumo` | POST | `criar_insumo` |
| `/fornecedor` | POST | `criar_fornecedor` |
| `/cliente` | POST | `criar_cliente` |
| `/subatividade-mestre` | POST | `criar_subatividade_mestre` |

**Modelos compartilhados que este módulo toca (4):** `Cliente`, `Fornecedor`, `Insumo`, `SubatividadeMestre`

### Catálogos (views)

Arquivos: `views/catalogos_views.py`
Conferência: ☐ pendente

**Funcionalidades (31 rotas):**

| Rota | Métodos | Função |
|---|---|---|
| `/` | GET | `hub` |
| `/categorias-fluxo-caixa` | GET | `categorias_fluxo_caixa` |
| `/categorias-fluxo-caixa/criar` | GET,POST | `categorias_fluxo_caixa_criar` |
| `/categorias-fluxo-caixa/editar/<int:id>` | GET,POST | `categorias_fluxo_caixa_editar` |
| `/categorias-fluxo-caixa/toggle/<int:id>` | POST | `categorias_fluxo_caixa_toggle` |
| `/categorias-fluxo-caixa/exportar-modelo` | GET | `categorias_fluxo_caixa_exportar_modelo` |
| `/categorias-fluxo-caixa/exportar-atuais` | GET | `categorias_fluxo_caixa_exportar_atuais` |
| `/categorias-fluxo-caixa/importar` | POST | `categorias_fluxo_caixa_importar` |
| `/categorias-fluxo-caixa/deletar/<int:id>` | POST | `categorias_fluxo_caixa_deletar` |
| `/categorias-fornecedor` | GET | `categorias_fornecedor` |
| `/categorias-fornecedor/criar` | GET,POST | `categorias_fornecedor_criar` |
| `/categorias-fornecedor/editar/<int:id>` | GET,POST | `categorias_fornecedor_editar` |
| `/categorias-fornecedor/toggle/<int:id>` | POST | `categorias_fornecedor_toggle` |
| `/categorias-fornecedor/deletar/<int:id>` | POST | `categorias_fornecedor_deletar` |
| `/categorias-reembolso` | GET | `categorias_reembolso` |
| `/categorias-reembolso/criar` | GET,POST | `categorias_reembolso_criar` |
| `/categorias-reembolso/editar/<int:id>` | GET,POST | `categorias_reembolso_editar` |
| `/categorias-reembolso/toggle/<int:id>` | POST | `categorias_reembolso_toggle` |
| `/categorias-reembolso/deletar/<int:id>` | POST | `categorias_reembolso_deletar` |
| `/grupos-financeiros` | GET | `grupos_financeiros` |
| `/grupos-financeiros/api` | GET | `grupos_financeiros_api` |
| `/grupos-financeiros/criar` | GET,POST | `grupos_financeiros_criar` |
| `/grupos-financeiros/editar/<int:id>` | GET,POST | `grupos_financeiros_editar` |
| `/grupos-financeiros/toggle/<int:id>` | POST | `grupos_financeiros_toggle` |
| `/grupos-financeiros/deletar/<int:id>` | POST | `grupos_financeiros_deletar` |
| `/palavras-chave` | GET | `palavras_chave` |
| `/palavras-chave/criar` | POST | `palavras_chave_criar` |
| `/palavras-chave/<int:id>/editar` | POST | `palavras_chave_editar` |
| `/palavras-chave/<int:id>/toggle` | POST | `palavras_chave_toggle` |
| `/palavras-chave/<int:id>/excluir` | POST | `palavras_chave_excluir` |
| `/palavras-chave/sugestoes/cadastrar` | POST | `palavras_chave_sugestoes_cadastrar` |

**Modelos próprios (4):**

- **CategoriaReembolso** (`categoria_reembolso`, 6 col) — também usado por Obras/Dashboard/base (main): `id`, `nome`, `descricao`, `ativo`, `admin_id→usuario`, `created_at`
- **GrupoFinanceiro** (`grupo_financeiro`, 7 col): `id`, `nome`, `tipo`, `descricao`, `ativo`, `admin_id→usuario`, `created_at`
- **PalavraChaveCategoria** (`palavra_chave_categoria`, 15 col) — também usado por Importação: `id`, `admin_id→usuario`, `categoria_fluxo_caixa_id→categoria_fluxo_caixa`, `palavras`, `campo_alvo`, `excecoes`, `gatilho_extra`, `campo_extra`, `condicao_obra`, `prioridade`, `tipo`, `origem`, `ativo`, `created_at`, `updated_at`
- **PalavraChaveSugestao** (`palavra_chave_sugestao`, 9 col): `id`, `admin_id→usuario`, `termo`, `ocorrencias`, `soma_valor`, `exemplo`, `tipo`, `dismissed`, `created_at`

**Modelos compartilhados que este módulo toca (3):** `CategoriaFluxoCaixa`, `CategoriaFornecedor`, `FluxoCaixa`

### API organizer

Arquivos: `api_organizer.py`
Conferência: ☐ pendente

**Funcionalidades (5 rotas):**

| Rota | Métodos | Função |
|---|---|---|
| `/` | GET | `api_status` |
| `/templates/listar` | GET | `listar_templates` |
| `/templates/carregar-multiplos` | POST | `carregar_templates_multiplos` |
| `/propostas/salvar-organizacao` | POST | `salvar_organizacao` |
| `/propostas/<int:proposta_id>/itens-organizados` | GET | `obter_itens_organizados` |

**Modelos compartilhados que este módulo toca (3):** `Proposta`, `PropostaItem`, `PropostaTemplate`

### Auditoria de vínculos

Arquivos: `vinculos_audit_views.py`
Conferência: ☐ pendente

**Funcionalidades (2 rotas):**

| Rota | Métodos | Função |
|---|---|---|
| `/auditoria` | GET | `auditoria` |
| `/subatividade/<int:sub_id>/marcar-revisada` | POST | `marcar_subatividade_revisada` |

**Modelos compartilhados que este módulo toca (7):** `Funcao`, `Funcionario`, `Obra`, `RDO`, `RDOMaoObra`, `SubatividadeMestre`, `TarefaCronograma`

### Manual

Arquivos: `views/manual_views.py`
Conferência: ☐ pendente

**Funcionalidades (3 rotas):**

| Rota | Métodos | Função |
|---|---|---|
| `/` | GET | `index` |
| `/download` | GET | `download` |
| `/imagens/<path:filename>` | GET | `imagens` |

### Landing

Arquivos: `landing_views.py`
Conferência: ☐ pendente

**Funcionalidades (1 rotas):**

| Rota | Métodos | Função |
|---|---|---|
| `/site` | GET | `landing_page` |

### Dev

Arquivos: `views/dev_views.py`
Conferência: ☐ pendente

**Funcionalidades (1 rotas):**

| Rota | Métodos | Função |
|---|---|---|
| `/mobile-preview` | GET | `mobile_preview` |

### Produção

Arquivos: `production_routes.py`
Conferência: ☐ pendente

**Funcionalidades (6 rotas):**

| Rota | Métodos | Função |
|---|---|---|
| `/safe-funcionarios` | GET | `safe_funcionarios` |
| `/safe-dashboard` | GET | `safe_dashboard` |
| `/debug-info` | GET | `debug_info` |
| `/safe-obras` | GET | `safe_obras` |
| `/safe-veiculos` | GET | `safe_veiculos` |
| `/safe-alimentacao` | GET | `safe_alimentacao` |

**Modelos compartilhados que este módulo toca (7):** `Departamento`, `Funcao`, `Funcionario`, `HorarioTrabalho`, `Obra`, `RegistroAlimentacao`, `Veiculo`

---

### Matriz de integração — modelos mais compartilhados

Modelos usados por 4+ módulos: cada um é um ponto de integração a
conferir (mudança num módulo pode quebrar os outros).

| Modelo | Módulos | Quais |
|---|---|---|
| `Obra` | 36 | Obras/Dashboard/base (main), RDO — edição, RDO — CRUD completo, Cronograma, Cronograma — importação .mpp, Portal do cliente, Medição, Importação, Equipe, Ponto, Alimentação, Reembolso, Subempreiteiros, Financeiro, Relatórios financeiros avançados, Contabilidade, Custos de obra, Gestão de custos, Planejamento de custos, CRM, Clientes, Propostas, Orçamentos, Orçamento operacional, Catálogo de serviços, Serviço da obra (real), Cadastrar serviço na obra, Almoxarifado, Compras, Frota, Transporte, Relatórios, Dashboards específicos, Métricas, Auditoria de vínculos, Produção |
| `Funcionario` | 22 | Obras/Dashboard/base (main), RDO — edição, RDO — CRUD completo, Cronograma, Importação, Equipe, Funcionários (API), Ponto, Folha de pagamento, Alimentação, Reembolso, Planejamento de custos, Serviço da obra (real), Almoxarifado, Compras, Frota, Transporte, Relatórios, Métricas, Configurações, Auditoria de vínculos, Produção |
| `GestaoCustoPai` | 11 | Obras/Dashboard/base (main), Portal do cliente, Importação, Ponto, Folha de pagamento, Reembolso, Subempreiteiros, Financeiro, Gestão de custos, Compras, Transporte |
| `RDO` | 10 | Obras/Dashboard/base (main), RDO — edição, RDO — CRUD completo, Cronograma, Portal do cliente, Funcionários (API), Subempreiteiros, Gestão de custos, Métricas, Auditoria de vínculos |
| `Servico` | 10 | Obras/Dashboard/base (main), Cronograma, Medição, Propostas, Orçamentos, Catálogo de serviços, Serviço da obra (real), Serviços da obra (API), Cadastrar serviço na obra, Métricas |
| `TarefaCronograma` | 10 | Obras/Dashboard/base (main), RDO — edição, Cronograma, Cronograma — importação .mpp, Portal do cliente, Medição, Subempreiteiros, Propostas, Orçamentos, Auditoria de vínculos |
| `Fornecedor` | 9 | Obras/Dashboard/base (main), Portal do cliente, Importação, Financeiro, Gestão de custos, Planejamento de custos, Almoxarifado, Compras, Quick-create |
| `ConfiguracaoEmpresa` | 8 | Obras/Dashboard/base (main), Cronograma, Portal do cliente, Medição, Folha de pagamento, Propostas, Orçamentos, Configurações |
| `GestaoCustoFilho` | 8 | Obras/Dashboard/base (main), RDO — edição, Ponto, Folha de pagamento, Financeiro, Gestão de custos, Compras, Transporte |
| `Cliente` | 8 | Obras/Dashboard/base (main), Portal do cliente, CRM, Clientes, Propostas, Orçamentos, Compras, Quick-create |
| `Usuario` | 8 | Obras/Dashboard/base (main), Cronograma — importação .mpp, Importação, Financeiro, CRM, Propostas, Serviços da obra (API), Compras |
| `ObraServicoCusto` | 8 | Obras/Dashboard/base (main), Medição, Alimentação, Gestão de custos, Planejamento de custos, Catálogo de serviços, Compras, Transporte |
| `FluxoCaixa` | 8 | Obras/Dashboard/base (main), Portal do cliente, Importação, Ponto, Financeiro, Gestão de custos, Compras, Catálogos (views) |
| `Veiculo` | 7 | Obras/Dashboard/base (main), Relatórios financeiros avançados, Frota, Relatórios, Exportação de relatórios, Dashboards específicos, Produção |
| `RDOMaoObra` | 7 | Obras/Dashboard/base (main), RDO — edição, RDO — CRUD completo, Cronograma, Portal do cliente, Gestão de custos, Auditoria de vínculos |
| `SubatividadeMestre` | 6 | Obras/Dashboard/base (main), RDO — edição, RDO — CRUD completo, Cronograma, Quick-create, Auditoria de vínculos |
| `CustoObra` | 6 | Obras/Dashboard/base (main), RDO — CRUD completo, Alimentação, Custos de obra, Transporte, Relatórios |
| `Departamento` | 6 | Obras/Dashboard/base (main), RDO — edição, Folha de pagamento, Relatórios, Configurações, Produção |
| `Proposta` | 6 | Obras/Dashboard/base (main), CRM, Clientes, Propostas, Orçamentos, API organizer |
| `ContaPagar` | 6 | RDO — CRUD completo, Importação, Financeiro, Gestão de custos, Custos de escritório, Compras |
| `RDOServicoSubatividade` | 5 | Obras/Dashboard/base (main), RDO — edição, RDO — CRUD completo, Cronograma, Portal do cliente |
| `UsoVeiculo` | 5 | Obras/Dashboard/base (main), Relatórios financeiros avançados, Frota, Exportação de relatórios, Dashboards específicos |
| `CustoVeiculo` | 5 | Obras/Dashboard/base (main), Relatórios financeiros avançados, Frota, Exportação de relatórios, Dashboards específicos |
| `Funcao` | 5 | Obras/Dashboard/base (main), Métricas, Configurações, Auditoria de vínculos, Produção |
| `RDOApontamentoCronograma` | 5 | Obras/Dashboard/base (main), RDO — edição, RDO — CRUD completo, Cronograma, Portal do cliente |
| `ContaReceber` | 5 | Portal do cliente, Medição, Importação, Financeiro, Propostas |
| `ServicoObraReal` | 4 | Obras/Dashboard/base (main), RDO — edição, Serviço da obra (real), Serviços da obra (API) |
| `Subempreiteiro` | 4 | Obras/Dashboard/base (main), Cronograma, Subempreiteiros, Gestão de custos |
| `PropostaTemplate` | 4 | Obras/Dashboard/base (main), Propostas, Orçamentos, API organizer |
| `CategoriaFluxoCaixa` | 4 | Obras/Dashboard/base (main), Importação, Financeiro, Catálogos (views) |
| `CronogramaTemplate` | 4 | Obras/Dashboard/base (main), Cronograma, Orçamentos, Catálogo de serviços |
| `RegistroAlimentacao` | 4 | Obras/Dashboard/base (main), Alimentação, Relatórios, Produção |
| `RegistroPonto` | 4 | Obras/Dashboard/base (main), Ponto, Gestão de custos, Relatórios |
| `Restaurante` | 4 | Obras/Dashboard/base (main), Importação, Alimentação, Relatórios |
| `Insumo` | 4 | Cronograma, Catálogo de serviços, Configurações, Quick-create |
| `ItemMedicaoComercial` | 4 | Medição, Planejamento de custos, Propostas, Catálogo de serviços |
| `PropostaItem` | 4 | Propostas, Orçamentos, Catálogo de serviços, API organizer |
<!-- RASTREIO:FIM -->

---

## Histórico

- **2026-07-30** — levantamento inicial: 58 blueprints (37 `app.py` + 21
  `main.py`); constatado que `scripts/auditoria_mapa_modulos.py` não enxerga
  os do `main.py`; 2 feature flags por tenant ativas no código.
- **2026-07-30** — rastreio por módulo gerado por `scripts/rastreio_modulos.py`
  (novo): 186 modelos com colunas/FKs, 760 rotas, matriz de integração por
  modelo compartilhado. Base para a spec de conferência módulo a módulo
  (marca `Conferência:` em cada módulo).
