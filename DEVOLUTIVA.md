# DEVOLUTIVA — Estado atual × Especificação do app de gestão Veks

> Data: 2026-07-21. Base: varredura do repositório em quatro frentes
> paralelas, com os achados graves reverificados manualmente linha a linha.
> Regra aplicada: template sem backend ou rota morta **não** conta como
> existente. Nenhum código foi escrito — este documento é o entregável.

## Resumo em três frases

O sistema está **muito mais avançado** do que a especificação pressupõe:
7 dos 10 módulos existem, alguns em nível de produção, e o módulo de
cronograma acabou de receber dez ciclos de trabalho (importação .mpp,
versionamento, reconciliação, motor de cálculo unificado). Em compensação,
**nenhuma das 9 regras de negócio da seção 5 está codificada** — e todas
elas dependem de uma camada de papéis/permissões que não existe.
Há ainda um bug ativo de duplicação de obra e três falhas de autorização
que, na minha leitura, precedem qualquer roadmap de features.

---

## 1. Inventário do estado atual

### 1.1 Módulos com backend vivo (rota registrada + modelo + template)

| Módulo | O que faz | Maturidade |
|---|---|---|
| **CRM** (`crm_views.py`, 22 rotas) | Kanban de 8 estágios (`LeadStatus`), valor por coluna, histórico campo-a-campo (`LeadHistorico`), gate de validação por supervisor, dedupe de cliente por telefone/e-mail, import/export CSV, listas mestras configuráveis | **Produção** |
| **Orçamento / Catálogo** (`propostas_consolidated.py` 35 rotas, `views/catalogo_views.py`, `views/orcamentos_views.py`) | Insumos, composições, **preço versionado por vigência**, BDI por dentro (ADR 0001), histórico de coeficiente com autor e motivo, import/export Excel, explosão de quantitativo com fator comercial | **Produção** |
| **Proposta comercial** | Modelo rico (cláusulas, template, validade, engenheiro/ART), versionamento com cadeia v1→v2→v3, gate que impede editar proposta não-rascunho, portal do cliente com token, aprovação/rejeição | **Produção** |
| **Cronograma** (`cronograma_views.py` 34 rotas + `views/cronograma_importacao.py` 12 rotas) | **Gantt interativo real** (2.465 linhas): grade + barras, arrastar barra altera datas (`initGanttBarDrag`), reordenar por drag (SortableJS), aviso mobile. Importação .mpp/MSPDI com parse, normalização determinística, reconciliação em cascata de 6 níveis, aplicação transacional versionada, rollback por snapshot | **Produção** (recém-entregue, M01–M10) |
| **RDO** (`views/rdo.py`, `crud_rdo_completo.py`) | Clima, efetivo, equipamentos, ocorrências, fotos, subatividades, apontamento no cronograma com modos quantitativo/percentual/marco, recomputo em cadeia para correção retroativa, PDF | **Produção** — o módulo mais maduro |
| **Medição** (`medicao_views.py`, 25 rotas) | Itens medidos, vínculo item↔tarefa de cronograma, fechamento, aprovação, PDF, regime fixo/percentual por obra | **Produção** |
| **Portal do cliente** (`portal_obras_views.py`, 10 rotas) | Acesso por token, progresso, cronograma-cliente, RDOs finalizados, medições, aprovação de compras e de mapa de concorrência | **Usável** |
| **Compras** (`compras_views.py` + `views/obras.py` mapas) | Mapa de concorrência V1 e **V2 (matriz N itens × N fornecedores)**, cotação interna por serviço, PDF versionado do mapa, registro de compra com parcelas | **Usável** — falta o fluxo (ver 4.7) |
| **Financeiro** (`financeiro_views.py` 23, `contabilidade_views.py` 24, `gestao_custos_views.py` 12) | Contas a pagar/receber, fluxo de caixa com banco e categoria, importação de extrato com rollback por lote, contabilidade de partidas dobradas (balancete, DRE, razão, balanço) | **Produção** |
| **Orçado × Real** (`ObraServicoCusto`, `services/resumo_custos_obra.py`) | Orçado, realizado por natureza (material/mão de obra/outros), a realizar, saldo, recálculo automático por listener, curva S financeira mensal | **Produção** |
| **Fornecedores** (`views/almoxarifado/fornecedores.py`) | CRUD, CNPJ único por tenant, categorias, import Excel, criação inline | **Produção** |
| **Equipe / Alocação** (`equipe_views.py`) | `Allocation` + `AllocationEmployee` por obra/dia/turno, sincronização com ponto | **Usável** |

### 1.2 Ferramentas e rotinas

| Item | Realidade |
|---|---|
| **`veks_classificador`** | **Não existe com esse nome.** O real é `services/classificador_cadastro.py` — motor puro, sem DB/Flask, com `Regra`/`Lancamento`/`Contexto`/`Veredito`, prioridade, exceções, condição AND, condição por obra, memória exata (`CorrecaoClassificacao`) e loop de aprendizado (`PalavraChaveSugestao`). **Mais capaz do que a spec supõe.** 5 arquivos de teste |
| **`dashboard_baias.html`** | **Não existe no repositório** (zero ocorrências). O que a spec quer em 4.5 já existe melhor em `templates/obras/cronograma.html` |
| **`dashboard_executivo_obra.html`** | Existe como arquivo, **nenhuma rota o renderiza** — template morto |
| **Skill `lancamentos-contabeis-dominio`** | **Não está neste repositório** nem na lista de skills disponíveis. Ver pergunta 3 |
| **Parser MPP/MSPDI** | `services/mspdi_parser.py` (stdlib, sem JVM) + `services/mpp_parser.py` (MPXJ em subprocess isolado com timeout). Paridade validada contra export real do MS Project |
| **Motor de cronograma** | `utils/cronograma_engine.py` — progresso por tarefa, rollup hierárquico, replanejamento, marco com peso zero, verificação de consistência com CLI |
| **CLIs de suporte** | `scripts/verificar_equivalencia_obra.py`, `scripts/verificar_consistencia_progresso.py`, `scripts/flag_cronograma_mpp.py` |
| **Suíte de testes** | 858 testes; `run_tests.sh --gate` (integração contra PostgreSQL real, ~37 min), `--java`, `--suite`, Playwright |

### 1.3 O que está morto ou órfão (candidato a descarte)

- `templates/admin_acessos.html` e `editar_funcionario_acesso.html` — apontam para rotas inexistentes; renderizar levanta `BuildError`
- `templates/dashboard_executivo_obra.html`, `relatorios_financeiros_avancados.py`, `/dashboards/especificos/obras` — renderizam templates que não existem
- `/contabilidade/sped` — tela vazia por construção (nada instancia `SpedContabil`)
- `models.py::AlocacaoEquipe` — modelo legado sem nenhuma rota de CRUD, concorrente de `Allocation`
- `app.py:358` importa `handlers.folha_handlers`, que **nunca existiu no git** (engolido por `try/except`)

---

## 2. Mapa de aderência

| § | Módulo | Veredito | O que falta |
|---|---|---|---|
| 4.1 | Autenticação e usuários | **ADAPTAR** | Login existe. Falta: papéis da seção 1 (hoje só `SUPER_ADMIN/ADMIN/GESTOR_EQUIPES/ALMOXARIFE/FUNCIONARIO`), obras vinculadas ao usuário, upload de assinatura, redirecionamento por papel. A tela de admin de acessos é template órfão |
| 4.2 | Dashboard geral | **ADAPTAR** | Existe `/dashboard` operacional. **Margem e caixa já são calculados no backend e nunca renderizados** (`views/dashboard.py:1018`, `financeiro_service.py:804`). Falta: funil no dashboard, IDP/IDC, farol por obra, alertas, drill-down. O rollup de avanço usa média simples de no máximo 5 obras e **ignora o engine V2** (`views/dashboard.py:425-457`) |
| 4.3 | CRM / Comercial | **ADAPTAR** | Kanban, cadastro e histórico prontos. Falta: **agenda de próxima ação com data** (hoje só semáforo passivo `prazo_cor`/`dias_parado`; `CrmCadencia` é rótulo sem motor), motivo obrigatório na perda, criação de pastas no Drive |
| 4.4 | Orçamento | **ADAPTAR** | Editor, composições, BDI e preço vigente prontos. Falta: **versionamento no Orçamento** (hoje só a Proposta versiona; `duplicar()` cria órfão sem FK), comparador lado a lado, PDF real (a rota "PDF" devolve HTML para imprimir), SINAPI (hoje transcrição manual via Excel), sugestão de preço a partir de cotações, handoff no `vendida` |
| 4.5 | Planejamento e cronograma | **ADAPTAR** | **Gantt interativo com drag de barras já existe.** Falta: **caminho crítico/CPM** (ausente), **baseline** (ausente — o planejado é recalculado das datas correntes), **EVM IDP/IDC/EAC** (ausente), predecessoras tipadas FS/SS/FF/SF com lag **na entidade** (ver §3), import XLSX, visão mobile "minhas atividades da semana" |
| 4.6 | RDO | **ADAPTAR** | Conteúdo quase todo pronto (clima, efetivo, equipamentos, ocorrências, fotos, atividades do cronograma). Falta: **máquina de estados** (`RDO.status` default `'Finalizado'`, comentário "RDO sempre Finalizado"), **assinatura eletrônica** (inexistente — nem encarregado, nem GP, nem cliente), imutabilidade + RDO retificador, clima manhã/tarde separado, alerta de RDO em atraso, link ocorrência→requisição |
| 4.7 | Compras / Suprimentos | **CONSTRUIR (o fluxo) + ADAPTAR (as peças)** | Mapa de concorrência V2 e cotações são reaproveitáveis quase intactos. Mas **não existe requisição** (zero ocorrências de "requisic" no repo), não existe aprovação do GP, não existe alçada, não existe PO emitido (o `PedidoCompra` é registro *a posteriori* de NF/recibo), o **recebimento parcial existe** (`compras_views.py:841-948`) mas **não é o gatilho financeiro** (o financeiro nasce no registro da compra, não no recebimento), não existe avaliação de fornecedor. A compra é **efetivada no mesmo request** (`compras_views.py:708`). **[Fase 3, 23/07: requisição→aprovação→alçada→PO emitido construídos; ver `docs/fase-3-rollout.md`]** |
| 4.8 | Financeiro | **ADAPTAR** | Contas, fluxo de caixa, classificador e orçado×real prontos. Falta: **exportação Domínio** (inexistente), **importação OFX** (só Excel hoje), **comprometido** (POs aprovados como compromisso futuro — depende de 4.7), projeção 90 dias, farol de estouro por categoria, medição com assinatura do cliente |
| 4.9 | Portal do cliente | **ADAPTAR** | Portal por token com progresso, RDOs, medições e aprovação de compras existe. Falta: **login de cliente** (hoje é link com token, sem senha), assinatura eletrônica de medição e ciência de RDO, curadoria "foto visível ao cliente", canal de solicitações, extrato de contrato com aditivos |
| 4.10 | Contratos e jurídico | **CONSTRUIR** | Não existe `Contrato`, aditivo, locação nem alerta de vencimento. `Obra.valor_contrato` é um número; `MedicaoContrato` é cronograma de faturamento, não documento. `Subempreiteiro` existe como cadastro, mas sem valor contratado, escopo ou vigência |

### Transversal (seção 2 e 5) — o bloqueio real

| Item | Veredito |
|---|---|
| Máquina de estados da Obra | **✅ CONSTRUÍDA em 22/07** (Fase 2). `Obra.estado` com 5 estados, grafo validado em `services/obra_estado.transitar()`, histórico em `obra_transicao_estado`, `status`/`ativo` viraram espelhos por write-through. "Vendida" ficou de fora de propósito: venda é estado da Proposta, não da Obra |
| Handoff do GP | **✅ CONSTRUÍDO em 22/07** (Fase 2). `services/obra_handoff.executar_handoff`: responsável + `UsuarioObra(GESTOR)` + gate de cronograma na mesma transação; tela com dossiê; evento `obra.handoff` para o n8n |
| RBAC por papel | **CONSTRUIR.** CRM, Compras, Financeiro, Custos e Cronograma usam **apenas** `login_required` do flask_login — autenticação, sem papel |
| Escopo por obra | **CONSTRUIR.** `views/rdo.py:2168` filtra só por `admin_id`. Alan e Abel veriam todas as obras da Veks |
| Trilha de auditoria | **PARCIAL.** Excelente no cronograma (`CronogramaImportacaoEvento`), na proposta (`PropostaHistorico`) e no CRM (`LeadHistorico`). Ausente em compras, financeiro e obra |
| Assinatura eletrônica com hash/IP | **CONSTRUIR.** Nada existe |
| Notificações e-mail/WhatsApp | **CONSTRUIR.** Há `smtplib` em `exportacao_relatorios.py` (envio de relatório) e um link `wa.me` para compartilhar proposta. Não há sistema de notificação |
| Google Drive | **CONSTRUIR.** Zero integração. `Lead.pasta` é texto livre digitado à mão |
| Offline-first no RDO | **CONSTRUIR.** Nada existe |

---

## 3. Conflitos de modelo de dados

| # | Conflito | Migração proposta | Risco de perda |
|---|---|---|---|
| 1 | **`Obra.status` é texto livre** (`models.py:257`, `String(20)`), alimentado por dropdown editável. A spec exige máquina de 11 estados | Coluna nova `estado` com enum + tabela `ObraTransicaoEstado` (de, para, quem, quando, motivo). Backfill mapeando os valores atuais; `status` legado mantido até a UI migrar | **Baixo** (aditivo). Atenção: valores customizados por tenant precisam de mapa manual |
| 2 | **`Obra.responsavel_id` aponta para `Funcionario`**, que **não tem FK para `Usuario`** (`models.py:258`, `189-211`). O responsável não é um usuário logável — hoje a ligação é comparação de e-mail em runtime | `Funcionario.usuario_id` (FK, nullable) + `Obra.gerente_id` → `Usuario`. Rotina de casamento por e-mail com revisão manual | **Médio** — homônimos e e-mails divergentes exigem curadoria |
| 3 | **Predecessora única sem tipo/lag.** `TarefaCronograma.predecessora_id` é FK simples (`models.py:4883`); a lista tipada `{uid, tipo, lag}` existe **só no snapshot** (`models.py:5122`). A spec §3 exige FS/SS/FF/SF + lag na atividade | Tabela `TarefaPredecessora` (tarefa, predecessora, tipo, lag). O parser MSPDI **já extrai** tipo e lag — o dado existe e é descartado hoje | **Nenhum** (aditivo); o `predecessora_id` vira derivado da primeira FS |
| 4 | **`obra_id` nullable em todo o eixo transacional.** `PedidoCompra:4736`, `ContaPagar:1746`, `ContaReceber:1793`, `FluxoCaixa:792`, `GestaoCustoFilho:5302` — e `GestaoCustoPai` **não tem campo de obra**. O código explora isso: `compras_views.py:583` faz `get('obra_id') or None`; `gestao_custos_views.py:467` permite **apagar** a obra de um custo lançado | Centro de custo "Veks Adm" como destino default; migrar órfãos para ele; então `NOT NULL` | **Alto** — precisa de classificação prévia dos registros órfãos. É a migração mais cara desta lista |
| 5 | **`Orcamento` não versiona.** Sem `versao`, `revisao` nem `origem_id`; `duplicar()` cria orçamento novo **sem FK de volta** | Self-FK `origem_id` + `versao` + `vigente`. O padrão a copiar já existe no repo: `ObraOrcamentoOperacionalItemVersao` (`models.py:6985`) faz janelas `[vigente_de, vigente_ate)` | **Baixo** (aditivo); cadeias antigas ficam sem histórico retroativo |
| 6 | **`ContaReceber` guarda cliente como texto** (`models.py:1790`), sem FK para `Cliente` | FK + backfill por CNPJ/nome | **Baixo** |
| 7 | **`RDO.status` default `'Finalizado'`** com comentário "RDO sempre Finalizado" (`models.py:860`) — não há ciclo de vida | Enum de estados + `RDOAssinatura` (papel, hash, timestamp, IP) + `rdo_retificado_id` | **Baixo** (aditivo) |
| 8 | **Duas modelagens de alocação** coexistem: `Allocation`/`AllocationEmployee` (viva) e `AlocacaoEquipe` (morta, sem rotas) | Remover a morta | **Nenhum** |

---

## 4. Reaproveitamento explícito

### Absorvido praticamente como está

| Ativo | Vira | Ajuste |
|---|---|---|
| `templates/obras/cronograma.html` (2.465 linhas, Gantt com drag de barras) | **Base da tela 4.5** — não `dashboard_baias.html`, que não existe | Acrescentar CPM, baseline e EVM sobre a base pronta |
| `services/classificador_cadastro.py` + `PalavraChaveCategoria` | **Serviço da tela 4.8** (classificação assistida) | Nenhum no motor; falta só o adaptador OFX |
| `MapaConcorrenciaV2` + `MapaFornecedor` + `MapaItemCotacao` + `services/mapa_relatorio_pdf.py` | **Tela de cotação/mapa de 4.7** | Pendurar em `Requisicao` em vez de direto na obra; acrescentar avaliação de fornecedor |
| Pipeline `.mpp`/MSPDI (M03–M08) + `CronogramaVersao`/`Snapshot` | **Import/export de 4.5** e a baseline | A baseline é praticamente um snapshot rotulado — o mecanismo já existe |
| `utils/cronograma_engine.py` | **Motor de % físico** de 4.5, 4.6, 4.8 e 4.9 | Nenhum. Já converge 5 fontes |
| `services/cronograma_fisico_financeiro.py::montar_curva_s` | **Curva S de 4.5** | Hoje é financeira mensal; falta a série física com baseline |
| `CronogramaImportacaoEvento` + `services/cronograma_observabilidade.py` | **Padrão de trilha de auditoria** da seção 5.9 | Replicar a forma em compras e financeiro |
| `portal_obras_views.py` + `templates/portal/` | **Base de 4.9** | Trocar token por login; acrescentar assinatura |
| `Insumo`/`ComposicaoServico`/`PrecoBaseInsumo` | **Base de preços de 4.4** | Acrescentar `codigo_sinapi` e importador |
| `PropostaHistorico`, `LeadHistorico` | Padrão de auditoria campo-a-campo | Reaproveitar a forma |

### Padrões internos a copiar (em vez de inventar)

- **Máquina de estados**: `CronogramaImportacao` (`upload → parse_ok → normalizado → reconciliado → aplicado`, com `log_transicao` e evento auditado) é o único state machine real do sistema. É o molde para a Obra, o RDO e a Requisição.
- **Gate de uso único com carimbo**: `Obra.cronograma_revisado_em` + interceptação em `views/obras.py:1429` já tem a **forma** de um aceite. Falta gravar *quem*.
- **Versão vigente por janela**: `ObraOrcamentoOperacionalItemVersao`.
- **Decorator de autorização real**: `decorators.py:6 cronograma_import_required` — o único do arquivo que de fato valida. Modelo para o RBAC.

---

## 5. Riscos e dívidas técnicas (top 5)

### R1 — Aprovar revisão de proposta **cria obra duplicada** · Impacto: ALTO · Ativo hoje

Cadeia verificada linha a linha: editar proposta aprovada leva à criação de
versão (`propostas_consolidated.py:1224`); `criar_nova_versao` copia ~25
campos mas **não copia `obra_id`**; ao aprovar, `event_manager.py:947`
procura a obra por `proposta.obra_id` (None) e por `proposta_origem_id ==
id_da_v2` (a obra aponta para a v1) — nenhum match — e cai no ramo que
**cria uma segunda Obra** com novo código `OBR####`, replicando todos os
`ItemMedicaoComercial` e `ObraServicoCusto`.

É exatamente o fluxo do aditivo que a spec quer formalizar (regra 5.4).
**Mitigação:** propagar `obra_id` na nova versão + guarda em
`propagar_proposta_para_obra` para atualizar a obra existente. Correção de
poucas linhas; deve vir antes de qualquer trabalho em 4.4.

### R2 — Autorização é fachada · Impacto: ALTO · Ativo hoje

`decorators.py:47-60`: `admin_required` e `login_required` são
`return f(*args, **kwargs)` incondicional, com o comentário "Durante
desenvolvimento, bypass para todos". Consumidos por `configuracoes_views.py`
(21 usos) e `ponto_views.py` (10). Qualquer funcionário autenticado grava
as configurações da empresa.

**Mitigação:** sanear antes de construir o RBAC — caso contrário toda
permissão nova é contornável nessas 31 rotas.

### R3 — Rota anônima devolvendo dados de tenant escolhido por heurística · Impacto: ALTO · Ativo hoje

`views/rdo.py:2133` — `/funcionario/rdo/consolidado` tem apenas
`@capture_db_errors`, **sem `@login_required`** (confirmei que não há
`before_request` global). Chama `get_admin_id_dinamico()`
(`views/helpers.py:409`), que sem usuário autenticado escolhe o admin com
mais funcionários, depois com mais serviços, e por fim **`return 1`**.
Somam-se: edição de usuário atravessando tenant (`views/users.py:71`,
sem predicado de `admin_id`), relatório executivo sem filtro de empresa
(`relatorios_funcionais.py:289`) e ~211 das 805 rotas sem decorator de
autenticação.

**Mitigação:** auditoria de rotas com `before_request` de negação por
padrão; eliminar os fallbacks de auto-detecção.

### R4 — Orçado × Real tem furo estrutural · Impacto: MÉDIO-ALTO · Ativo hoje

Como `obra_id` é nullable em todo o eixo transacional (§3.4), lançamento
salvo sem obra **some do custo da obra sem erro e sem alerta**.
`services/resumo_custos_obra.py:190` implementa um rateio proporcional ao
orçado como paliativo — ou seja, o furo é conhecido e hoje é compensado
por **estimativa, não por dado**. A regra 5.3 da spec é a correção certa.

**Mitigação:** migração §3.4, que é a mais cara — exige classificar os
registros órfãos antes de tornar o campo obrigatório.

### R5 — Fechos de módulo sem gate completo · Impacto: MÉDIO · Recém-corrigido

Descoberto hoje: o `--gate` completo (~37 min, quase tudo integração
contra PostgreSQL real) não era rodado até o fim. Duas famílias ficaram
vermelhas do M06 ao M09 atravessando quatro fechos que se declararam
verdes — uma delas era bug real (raiz do cronograma exibindo 0% em árvore
de 3 níveis). Corrigido, e a dívida de processo ficou registrada.

**Mitigação:** nenhuma fase desta especificação deve ser aceita sem a
linha final do `--gate` colada no documento de fecho.

---

## 6. Proposta de sequência

Princípio: **primeiro parar de perder dado, depois destravar as regras,
só então as features novas.** As fases 0–2 não entregam tela nova — e são
as que mais mudam o sistema.

### Fase 0 — Estancar (P)
- R1: propagar `obra_id` na revisão de proposta + guarda contra obra duplicada
- R2: sanear os no-op de `decorators.py`
- R3: `@login_required` na rota anônima, remover fallback `return 1`, filtro de tenant em `views/users.py` e `relatorios_funcionais.py`
- **Pronto quando:** teste provando que aprovar v2 atualiza a obra existente; teste de rota anônima devolvendo 401; `--gate` verde

### Fase 1 — Fundação de identidade e papéis (M)
- `Funcionario.usuario_id`; `Obra.gerente_id` → `Usuario`
- Papéis da seção 1 em `TipoUsuario`; tabela `UsuarioObra` (escopo)
- Decorator `papel_required` + `escopo_obra_required` no molde do `cronograma_import_required`
- Tela 4.1 de admin de usuários (substitui os templates órfãos)
- **Pronto quando:** encarregado logado vê só as obras dele em RDO, cronograma e custos, provado por teste; menu renderiza por papel

### Fase 2 — Máquina de estados da Obra e handoff (M)
- Enum de estados + `ObraTransicaoEstado` auditada
- Aceite formal do GP (regra 5.1), reusando a forma do gate `cronograma_revisado_em`
- Dossiê de handoff (proposta vigente, quantitativos, projetos, contatos) + notificação ao GP
- **Pronto quando:** obra não entra em `em_execução` sem registro de aceite; transição inválida rejeitada por teste

### Fase 3 — Compras com governança (G)
- `Requisicao` + estados; pendurar o mapa V2 existente na requisição
- Aprovação do GP com alçada configurável (regra 5.2); tela mobile de aprovação
- `PedidoCompra` vira PO de verdade (numeração, PDF, estados) — o registro atual vira `Recebimento`
- Recebimento gera contas a pagar automaticamente (regra 5.7)
- Avaliação de fornecedor
- **Pronto quando:** nenhum PO emitido sem aprovação registrada, provado por teste; ciclo completo requisição→pagar num teste de integração

### Fase 4 — Centro de custo obrigatório (M, risco alto)
- Centro "Veks Adm"; classificação dos órfãos; `obra_id` NOT NULL (regra 5.3)
- "Comprometido" no orçado×real (POs aprovados) — depende da fase 3
- **Pronto quando:** impossível salvar lançamento operacional sem obra; orçado×real sem rateio paliativo

### Fase 5 — RDO com ciclo de vida e assinatura (M)
- Estados, imutabilidade, RDO retificador (regra 5.5)
- `RDOAssinatura` com hash + timestamp + IP (regra 5.9)
- Clima manhã/tarde, alerta de atraso, link ocorrência→requisição
- **Pronto quando:** RDO validado não aceita edição; retificador vinculado; assinatura auditável

### Fase 6 — Orçamento versionado e aditivo (M)
- Versão no `Orcamento` (ou decisão explícita de que a Proposta é a dona — ver pergunta 1)
- Aditivo que ajusta `valor_contrato` de forma auditável e reajusta medições (regra 5.4)
- Comparador de versões; PDF real
- **Pronto quando:** aditivo cria versão e move o contrato com trilha; edição livre de `valor_contrato` bloqueada

### Fase 7 — Planejamento avançado (G)
- CPM/caminho crítico, baseline (via snapshot rotulado), EVM (IDP/IDC/EAC)
- `TarefaPredecessora` tipada — o parser já extrai tipo e lag
- Visão mobile do encarregado; import XLSX
- **Pronto quando:** caminho crítico bate com o MS Project na obra piloto

### Fase 8 — Financeiro avançado (M)
- Exportação Domínio; importação OFX; projeção 90 dias; farol por categoria
- Medição com assinatura do cliente (regra 5.6)

### Fase 9 — Portal, contratos e integrações (G)
- Login de cliente; assinatura de medição e ciência de RDO; curadoria de fotos; canal de solicitações
- Módulo 4.10 (contratos, aditivos, locações, alertas)
- Google Drive; notificações e-mail/WhatsApp
- Offline-first do RDO — **avaliar separadamente**, é o item de maior custo da spec

### Sobre a stack (requisito 6.1)

**Mantém Flask.** Não vejo justificativa de custo/benefício para migrar:
o que a spec pede é modelagem e regra de negócio, não capacidade de
framework. O Gantt interativo, o motor de cronograma, o classificador e a
suíte de 858 testes são investimento que uma migração jogaria fora. O
único ponto que mereceria stack diferente é o **offline-first do RDO** —
e isso se resolve com PWA sobre o Flask atual, não com reescrita.

---

## 7. Perguntas abertas (priorizadas)

1. **Quem é o dono da versão vigente: Orçamento ou Proposta?** Hoje o
   código versiona a **Proposta** (com cadeia e gate funcionando) e o
   `Orcamento` não versiona. A spec §3 diz o contrário. Inverter é caro e
   descarta um mecanismo que funciona. Proposta minha: manter a Proposta
   como dona da versão vigente e dar ao Orçamento apenas cadeia de
   revisões internas. Você concorda ou o Orçamento tem de ser a fonte?

2. **Onde está a skill/rotina `lancamentos-contabeis-dominio`?** Ela não
   está neste repositório nem nas skills disponíveis, e não há nenhuma
   integração com o Domínio no código. Preciso do artefato (ou do layout
   11758 documentado) para a fase 8.

3. **Alçada de aprovação: qual o valor de X?** E a dupla aprovação
   (GP + Guilherme) é por valor absoluto, por % do orçamento da obra, ou
   por categoria?

4. **Migração do `obra_id` obrigatório (fase 4):** os lançamentos
   históricos sem obra vão todos para "Veks Adm", ou você quer uma
   curadoria manual antes? Isso decide se a fase 4 é M ou G.

5. **Portal do cliente: token ou login?** Hoje é link com token, sem
   senha — funciona e é simples. A spec pede login. Migrar exige cadastro
   e recuperação de senha para o cliente. Confirma que quer login?

6. **Assinatura eletrônica: qual o valor jurídico pretendido?** Desenho na
   tela + hash + IP tem valor probatório limitado. Se a intenção é
   oponibilidade contratual real, o caminho é ICP-Brasil ou um provedor
   (Clicksign/D4Sign) — muda muito o custo.

7. **Offline-first do RDO é requisito ou desejável?** É o item mais caro
   da especificação (sincronização, conflito, fila de fotos). Vale saber
   se os canteiros realmente ficam sem sinal.

8. **Estados da obra: `oportunidade` e `orçamento` são estados da Obra ou
   do Lead?** Hoje o Lead tem o funil e a Obra nasce só na aprovação.
   Fazer a Obra nascer na oportunidade muda o CRM inteiro.

9. **Google Drive: conta de serviço ou OAuth por usuário?** E a estrutura
   de pastas padrão por obra — você tem o template definido?

10. **A flag `cronograma_mpp_ativo` nasce desligada** (entregue hoje).
    Antes de qualquer deploy: ligo para os tenants atuais, ou o rollout
    começa mesmo por uma obra de homologação?
