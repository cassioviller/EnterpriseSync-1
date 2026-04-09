# Relatório V2 — Arquivo de Mudanças

> Documento de registro histórico do ciclo de desenvolvimento V2.
> Período: janeiro–abril de 2026.

---

## Sumário por Módulo

| Módulo | Tarefas |
|---|---|
| Transporte | #1 |
| Financeiro | #2, #5, #7, #8, #9, #12, #16 |
| Ponto | #3, #11 |
| Cronograma | #4 |
| RDO | #13, #17, #18, #19 |
| Dashboard | #14 |
| Suprimentos | #6 (cancelada), #10, #15 |
| Documentação | #20 |

---

## Módulo: Transporte

### Tarefa #1 — Transporte V2 Unificado: Frota + Deslocamentos
**Data de merge:** 21/01/2026

Unificação do módulo de Frota (veículos próprios) e do módulo de Transporte (deslocamentos de funcionários) em um único dropdown "Transporte" na navbar, exclusivo para tenants V2. O menu V1 permaneceu inalterado com o link "Veículos" separado. Os custos de frota (combustível, manutenção, seguro) passaram a ser integrados automaticamente à Gestão de Custos V2 com a categoria "Despesa de Frota" (VEICULO), distinguida de "Despesa Transporte" (TRANSPORTE) para deslocamentos de funcionários.

---

## Módulo: Financeiro

### Tarefa #2 — Gestão de Custos V2 → Fluxo de Caixa Financeiro
**Data de merge:** 28/01/2026

Os custos operacionais registrados na Gestão de Custos V2 (alimentação, transporte, reembolsos, salários diaristas) passaram a ser incluídos no dashboard financeiro como saídas previstas. O fluxo de aprovação foi reestruturado em 3 etapas distintas: SOLICITADO → AUTORIZADO → PAGO, com botões e modais específicos para cada transição na tela de Gestão de Custos. Os registros de GestaoCustoPai aparecem visualmente diferenciados com a tag "Gestão V2" na listagem do financeiro.

### Tarefa #5 — CRUD Completo de Reembolsos V2
**Data de merge:** 13/02/2026

Criação do módulo completo de Reembolsos V2, incluindo blueprint, views, templates e integração automática com a Gestão de Custos. O módulo disponibiliza uma página de listagem em `/reembolsos/` com filtros por funcionário, obra e status, formulário de criação com upload opcional de comprovante, e link "Reembolsos" na navbar V2. Ao salvar um reembolso, um GestaoCustoPai com categoria REEMBOLSO é criado automaticamente via `registrar_custo_automatico()`. O acesso é restrito a tenants V2.

### Tarefa #7 — Despesas Gerais via Gestão de Custos V2
**Data de merge:** 20/02/2026

Adição da categoria `DESPESA_GERAL` na Gestão de Custos, com campos extras para data de vencimento e número do documento. Despesas avulsas (aluguel, energia, IPTU, honorários, etc.) passaram a percorrer o fluxo de aprovação V2 (PENDENTE → SOLICITADO → AUTORIZADO → PAGO). O Fluxo de Caixa foi atualizado para usar a `data_vencimento` (quando disponível) em vez da data de criação, tornando as projeções mensais mais precisas. A página de Contas a Pagar para tenants V2 passou a exibir aviso com link para a Gestão de Custos.

### Tarefa #8 — Extensão do Modelo GestaoCustos
**Data de merge:** 05/03/2026

Extensão do modelo GestaoCustoPai para absorver todos os campos necessários para registrar qualquer tipo de saída financeira: `fornecedor_id`, `forma_pagamento`, `valor_pago`, `saldo`, `conta_contabil_codigo`, `data_emissao`, `numero_parcela` e `total_parcelas`. As categorias foram reestruturadas seguindo padrões contábeis da construção civil (SINAPI/NBC TG), agrupadas em Custo Direto de Obra, Custo Indireto de Obra e Despesa Administrativa. Registros existentes foram migrados para as novas categorias, mantendo retrocompatibilidade.

### Tarefa #9 — Unificação Financeira: Extinção do ContaPagar
**Data de merge:** 12/03/2026

O módulo ContaPagar foi desligado e toda criação de despesas passou a ser centralizada na Gestão de Custos. As rotas de "Nova Conta a Pagar" foram removidas ou redirecionadas. Compras de material passaram a criar apenas um registro em GestaoCustoPai. A folha de pagamento e o RDO foram integrados para alimentar GestaoCustoPai automaticamente. O fluxo de caixa foi corrigido para não duplicar saídas. O menu lateral e o dashboard financeiro removeram "Contas a Pagar" como módulo separado. Pagamentos parciais passaram a funcionar na Gestão de Custos com os campos `valor_pago` e `saldo`.

### Tarefa #12 — Gestão de Custos: Fluxo de Aprovação em 2 Etapas
**Data de merge:** 27/03/2026

Simplificação do fluxo de aprovação da Gestão de Custos V2 para apenas 2 etapas: Solicitar → Aprovar. O estado AUTORIZADO e o modal "Efetivar Pagamento" foram eliminados. A aprovação passou a executar o pagamento diretamente, com modal contendo data de pagamento e dropdown de banco (BancoEmpresa). O botão "Não" no modal volta o custo para PENDENTE. Pagamentos parciais continuam funcionando: quando há saldo restante, o status vai para PARCIAL e o ciclo reinicia.

### Tarefa #16 — Gestão de Custos: Obras Separadas por Vírgula + Resumo por Obra
**Data de merge:** 31/03/2026

Quando um lançamento pai possui filhos em mais de uma obra, a coluna "Entidade" na lista fechada passou a exibir todos os nomes de obras separados por vírgula. Ao expandir o lançamento, aparece um mini-quadro de totais por obra antes da tabela de itens, exibido apenas quando há 2 ou mais obras distintas. Lançamentos com apenas uma obra continuam sem o quadro extra.

---

## Módulo: Ponto

### Tarefa #3 — Diaristas: Custo Automático ao Bater Ponto
**Data de merge:** 04/02/2026

Implementação de integração automática para funcionários diaristas (tipo_remuneracao == 'diaria'): ao bater ponto de ENTRADA, o sistema cria automaticamente um GestaoCustoPai com categoria SALARIO e valor igual ao `valor_diaria` do funcionário, vinculado à obra onde o ponto foi batido. O sistema inclui verificação de duplicidade por `origem_tabela='registro_ponto'` e `data_referencia`, evitando lançamentos repetidos no mesmo dia. A integração cobre tanto a API `/ponto/api/bater` quanto o reconhecimento facial `/ponto/api/reconhecimento`.

### Tarefa #11 — Corrigir Lançamento de Diária no Ponto Manual
**Data de merge:** 25/03/2026

Correção de bug: quando um ponto era criado manualmente pela tela do funcionário (em `views/admin.py`), o evento `ponto_registrado` nunca era disparado após o commit, fazendo com que o lançamento de diária na Gestão de Custos V2 não ocorresse. A correção adicionou o disparo do evento `ponto_registrado` após o `db.session.commit()` na função `novo_ponto`, seguindo o mesmo padrão do fluxo de reconhecimento facial. Funcionários horistas também passaram a ter o custo calculado e lançado em `CustoObra` ao criar ponto manualmente.

---

## Módulo: Cronograma

### Tarefa #4 — Cronograma: Predecessora Inline e Recálculo em Cadeia
**Data de merge:** 07/02/2026

Dois problemas resolvidos no módulo de Cronograma: (1) a edição por duplo clique na coluna "Pred." passou a usar um `<select>` com a lista de tarefas da obra, em vez de um input numérico livre que permitia IDs inexistentes; (2) ao editar duração ou predecessora de uma tarefa via edição inline, as datas das tarefas sucessoras passaram a ser recalculadas automaticamente em cadeia, respeitando o CalendarioEmpresa (fins de semana e feriados). O frontend recebe a lista completa de tarefas atualizada no JSON de resposta e redesenha o Gantt sem recarregar a página.

---

## Módulo: RDO

### Tarefa #13 — RDO V2: Mão de Obra por Subatividade + Automação de Custo
**Data de merge:** 01/04/2026

Reescrita do fluxo de mão de obra no RDO V2: a seção global de "Seleção de Funcionários" foi substituída por um seletor dinâmico dentro de cada card de subatividade, com campo de horas trabalhadas por funcionário naquela subatividade específica. Cada `RDOMaoObra` agora fica vinculado à sua `RDOServicoSubatividade` via novo campo `subatividade_id` (migration #90). Ao finalizar o RDO, é criado um único lançamento de custo por funcionário por data na Gestão de Custos V2 (status PENDENTE), com deduplicação para evitar lançamentos repetidos ao re-finalizar.

### Tarefa #17 — RDO V2: Catálogo de Produtividade e Templates de Cronograma
**Data de merge:** 02/04/2026

Extensão do catálogo de subatividades com campos `unidade_medida` (m², m linear, un, m³, etc.) e `meta_produtividade` (ex: 5,0 m²/h) via migration #94. Criação dos modelos `CronogramaTemplate` e `CronogramaTemplateItem` (migration #95) com suporte a multi-tenancy. Implementação de CRUD de templates com drag-and-drop de ordem via Sortable.js. Adição de botão "Aplicar Template" no cronograma de obra para popular TarefaCronograma a partir de templates reutilizáveis.

### Tarefa #18 — RDO V2: Quantidade Produzida e Índice de Produtividade
**Data de merge:** 04/04/2026

Fechamento do ciclo de produtividade: o operador informa a `quantidade_produzida` por subatividade no RDO. Ao finalizar, o sistema calcula automaticamente `produtividade_real = quantidade_produzida / horas_trabalhadas` e `indice_produtividade = produtividade_real / meta_produtividade_snapshot` para cada funcionário alocado. Novos campos adicionados via migrations #96 (RDOServicoSubatividade) e #97 (RDOMaoObra). A visualização do RDO finalizado exibe badges coloridos: verde (≥ 1.0), amarelo (0.8–1.0) e vermelho (< 0.8).

### Tarefa #19 — RDO V2: Dashboard de Produtividade por Funcionário
**Data de merge:** 07/04/2026

Criação de página de dashboard de produtividade com filtros por Obra, Subatividade, Período e Funcionário. A página exibe tabela de ranking com produtividade média e índice por funcionário, gráfico de barras (Chart.js) com produtividade real vs meta, gráfico de linha com evolução da produtividade da equipe ao longo do período, e cards de resumo com melhor performer, pior performer e média da equipe vs meta. Link "Produtividade" adicionado ao menu, acessível apenas para tenants V2.

---

## Módulo: Dashboard

### Tarefa #14 — Dashboard: Custos por Competência
**Data de merge:** 10/04/2026

Refatoração do Dashboard para mostrar Custo Realizado por competência em vez de custo pago por fluxo de caixa. O gráfico "Custos por Obra" passou a exibir barras duplas (Custo Realizado vs Orçamento), com barra excedente vermelha quando o realizado ultrapassa o orçamento. O widget "Funcionários por Departamento" foi enriquecido com headcount e custo mensal de folha por departamento. O widget "Custos Recentes" foi removido. Todas as queries garantem filtro por `admin_id` (multi-tenant).

---

## Módulo: Suprimentos

### Tarefa #6 — Gantt Interativo com Drag & Drop ⚠️ CANCELADA
**Status:** Cancelado

Tarefa cancelada durante o ciclo V2. A funcionalidade de drag & drop interativo no Gantt foi removida do escopo, ficando como item para um ciclo futuro.

### Tarefa #10 — Hotfix: Migration Colunas GestaoCustoPai
**Data de merge:** 14/03/2026

Correção emergencial para produção: criação da migration ausente que adiciona as colunas introduzidas pelo Tarefa #8 (`fornecedor_id`, `forma_pagamento`, `valor_pago`, `saldo`, `conta_contabil_codigo`, `data_emissao`, `numero_parcela`, `total_parcelas`) na tabela `gestao_custo_pai`. O entrypoint de produção foi atualizado para executar as migrations antes de o Gunicorn subir, resolvendo o erro `column gestao_custo_pai.fornecedor_id does not exist` que quebrava a aplicação em produção.

### Tarefa #15 — Reengenharia Suprimentos: Compras + Almoxarifado + Financeiro
**Data de merge:** 14/04/2026

Consolidação do fluxo de custo de material em um único caminho, eliminando a duplicação entre Compras V2 e Almoxarifado. O `PedidoCompra` passou a ser o gatilho mestre: ao salvar uma compra com `obra_id`, o sistema cria automaticamente `GestaoCustoPai(MATERIAL)`, `AlmoxarifadoMovimento(ENTRADA)` e atualiza `AlmoxarifadoEstoque`. A saída do almoxarifado passou a ser apenas controle de estoque físico, sem novo lançamento financeiro. Transferências de estoque central para obra geram `GestaoCustoPai(TRANSFERENCIA)`. O dashboard passou a ler custos de material exclusivamente de `GestaoCustoPai.tipo_categoria='MATERIAL'`.

---

## Módulo: Documentação

### Tarefa #20 — Atualizar Manuais Financeiro e Almoxarifado
**Data de merge:** 09/04/2026

Atualização dos manuais `manual_financeiro.md` e `static/manual_almoxarifado.md` para refletir as mudanças implementadas no ciclo V2: (1) fluxo de aprovação corrigido de 3 etapas para 2 etapas (Solicitar → Aprovar); (2) referências ao módulo "Conta a Pagar (manual)" removidas, pois o módulo foi extinto; (3) seção de Material/Almoxarifado reescrita para indicar que o custo é reconhecido na compra, não na saída; (4) documentação da nova funcionalidade de múltiplas obras separadas por vírgula e resumo por obra na Gestão de Custos.

---

## Tarefa Pendente

### Tarefa #21 — Catálogo de Atividades + Template Drag-and-Drop *(em andamento)*
**Status:** Em andamento

Reestruturação do catálogo de subatividades para suportar **Grupos** (sem vínculo obrigatório com Serviço) e **Subatividades** independentes. A hierarquia (raiz, sub-nó, folha) passa a ser definida pela posição no template, não no cadastro. Implementação de interface de template builder com dois painéis e drag-and-drop hierárquico em N níveis usando Sortable.js nested. Esta tarefa estava em andamento ao momento de geração deste relatório e não foi concluída no ciclo V2.

---

*Documento gerado em 14/04/2026.*
