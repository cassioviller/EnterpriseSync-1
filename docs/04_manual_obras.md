# Capítulo 4 — Gestão de Obras

## 4.1. Introdução à Gestão de Obras

O módulo de **Gestão de Obras** do SIGE (Sistema Integrado de Gestão Empresarial) é o núcleo operacional do sistema, concentrando todo o ciclo de vida de projetos de construção — desde o cadastro inicial até o encerramento e a análise financeira final. Este módulo é acessado pelo menu lateral **Obras** na barra de navegação principal do sistema.

Principais funcionalidades cobertas neste capítulo:

| Funcionalidade | Descrição |
|---|---|
| Cadastro de obras | Registro completo com dados do projeto, cliente, orçamento e geolocalização |
| Planejamento de serviços | Vinculação de serviços planejados com quantidades, prazos e custos unitários |
| Acompanhamento executivo | Dashboard com KPIs de custo, prazo, equipe e progresso da obra |
| Controle financeiro | Comparação entre orçado e realizado, análise de desvios e fluxo de caixa |
| Lançamento de RDO | Registro Diário de Obra vinculado diretamente ao projeto |
| Relatórios gerenciais | Geração de relatórios consolidados por obra em PDF |
| Portal do cliente | Acesso externo para o cliente acompanhar o andamento da obra |

> **Pré-requisito:** Para cadastrar e gerenciar obras, o usuário deve possuir permissão de **Administrador**. Funcionários e Gestores de Equipe podem visualizar as obras às quais estão alocados e registrar RDOs a partir da listagem.

---

## 4.2. Tela Principal de Obras

### Acessando a Tela

1. No menu de navegação superior, clique em **Obras**.
2. O sistema direcionará você para a URL `/obras`.

![Tela principal de obras](placeholder_tela_obras.png)

### Visão Geral da Interface

A tela principal de obras é dividida nas seguintes áreas:

#### KPIs Resumidos (Topo)

No topo da página, são exibidos indicadores gerais do portfólio de obras:

| KPI | Descrição |
|---|---|
| Obras Ativas | Quantidade de obras com status "Em andamento" (ex.: 8) |
| Obras Disponíveis | Total de obras cadastradas no sistema (ex.: 142) |
| Custo Total no Período | Somatório dos custos de todas as obras no período filtrado |
| Funcionários Alocados | Total de funcionários distintos com registro de ponto em obras ativas |

#### Filtros de Pesquisa

Acima dos cards de obras, o sistema oferece filtros para refinar a listagem:

1. **Nome da Obra** — Campo de texto para busca por nome (parcial ou completo).
2. **Status** — Filtre por status: *Em andamento*, *Concluída*, *Paralisada* ou *Cancelada*.
3. **Cliente** — Campo de texto para busca pelo nome do cliente responsável.
4. **Data Início** — Define o início do período para filtro por data de início da obra.
5. **Data Fim** — Define o final do período para filtro por data de início da obra.
6. Clique em **Filtrar** para atualizar a listagem e os KPIs exibidos.

![Filtros de pesquisa de obras](placeholder_filtros_obras.png)

#### Cards de Obras

Cada obra é exibida em formato de **card** (cartão visual), contendo:

- **Nome da obra** e **código** identificador (ex.: O0001).
- **Status** da obra com indicador visual colorido.
- **Cliente** associado ao projeto.
- **Endereço** da obra.
- **Data de início** e **previsão de término**.
- **Progresso** — Barra visual indicando o percentual de conclusão.
- **KPIs do card** — Custo total, dias trabalhados e funcionários alocados no período.
- **Botão +RDO** — Atalho direto para criar um novo Registro Diário de Obra, redirecionando para `/funcionario/rdo/novo?obra_id=<id>`.
- **Botão Detalhes** — Acessa a página completa da obra em `/obras/detalhes/<id>`.

![Card de obra com informações e KPIs](placeholder_card_obra.png)

#### Ordenação

A listagem de obras é ordenada automaticamente por **data de início** (mais recente primeiro). Obras com status "Em andamento" tendem a aparecer no topo por possuírem datas de início mais recentes.

---

## 4.3. Cadastrando uma Nova Obra

### Acessando o Formulário

1. Na tela principal de obras (`/obras`), clique no botão **+ Nova Obra**.
2. O sistema direcionará você para a URL `/obras/nova`.

![Formulário de nova obra](placeholder_form_nova_obra.png)

### 4.3.1. Dados da Obra

Preencha os campos do formulário conforme a tabela abaixo:

| Campo | Tipo | Obrigatório | Descrição |
|---|---|---|---|
| Nome | Texto | Sim | Nome identificador do projeto/obra |
| Código | Texto | Não | Código único da obra (ex.: O0001). Se não informado, o sistema gera automaticamente no formato `O` + sequencial de 4 dígitos |
| Endereço | Texto | Não | Endereço completo do canteiro de obras |
| Status | Seleção | Sim | Status inicial: *Em andamento*, *Concluída*, *Paralisada* ou *Cancelada* |
| Data de Início | Data | Sim | Data de início prevista ou efetiva da obra |
| Data de Previsão de Término | Data | Não | Data estimada para conclusão do projeto |
| Área Total (m²) | Numérico | Não | Área total do projeto em metros quadrados |
| Responsável | Seleção | Não | Funcionário responsável técnico pela obra (lista de funcionários ativos) |

#### Dados do Cliente

| Campo | Tipo | Obrigatório | Descrição |
|---|---|---|---|
| Nome do Cliente | Texto | Não | Nome da pessoa ou empresa contratante |
| E-mail do Cliente | E-mail | Não | E-mail para comunicação e acesso ao portal do cliente |
| Telefone do Cliente | Texto | Não | Telefone de contato do cliente |
| Portal Ativo | Checkbox | Não | Ativa o Portal do Cliente para acompanhamento externo. Ao marcar e informar o e-mail, o sistema gera automaticamente um token de acesso seguro |

#### Geolocalização e Geofencing

| Campo | Tipo | Obrigatório | Descrição |
|---|---|---|---|
| Latitude | Numérico | Não | Coordenada de latitude do canteiro de obras |
| Longitude | Numérico | Não | Coordenada de longitude do canteiro de obras |
| Raio de Geofence (metros) | Numérico | Não | Raio da cerca virtual para validação de ponto eletrônico (padrão: 100 metros) |

> **Dica:** O geofencing permite validar se o funcionário está fisicamente dentro do perímetro da obra ao registrar o ponto. Configure latitude, longitude e raio para ativar essa funcionalidade.

![Campos de geolocalização no formulário](placeholder_geofencing_obra.png)

### 4.3.2. Orçamento e Custos

Na seção financeira do formulário, informe os valores planejados:

| Campo | Tipo | Obrigatório | Descrição |
|---|---|---|---|
| Orçamento | Monetário (R$) | Não | Valor total orçado para a execução da obra |
| Valor do Contrato | Monetário (R$) | Não | Valor firmado em contrato com o cliente. Utilizado para cálculo de margem de lucro |

> **Importante:** O valor do contrato é a referência principal para análise de rentabilidade. O sistema calcula automaticamente a margem comparando o valor do contrato com os custos reais apurados (mão de obra, alimentação, transporte e custos diversos).

### 4.3.3. Equipe da Obra

A alocação de funcionários à obra é realizada de duas formas:

1. **Responsável técnico** — Definido diretamente no formulário de cadastro da obra (campo Responsável).
2. **Equipe de campo** — Alocada através do módulo **Equipe** ou automaticamente quando funcionários registram ponto indicando a obra.

Para vincular serviços à obra durante o cadastro:

1. Na seção **Serviços da Obra**, marque os serviços desejados na lista de serviços disponíveis.
2. Os serviços listados são aqueles cadastrados previamente no módulo de Serviços do sistema.
3. Clique em **Salvar** para criar a obra com os serviços selecionados.

> **Nota:** Após o cadastro, o sistema redireciona automaticamente para a página de detalhes da obra recém-criada (`/obras/detalhes/<id>`).

---

## 4.4. Planejamento da Obra

### 4.4.1. Serviços da Obra

O planejamento de serviços define **o quê** será executado na obra e em **qual quantidade**. Cada serviço vinculado possui controle individual de planejamento e execução.

#### Vinculando Serviços

1. Acesse a obra desejada em `/obras/detalhes/<id>`.
2. Na seção **Serviços**, clique em **Gerenciar Serviços**.
3. Selecione os serviços desejados na listagem de serviços disponíveis.
4. Para cada serviço selecionado, o sistema cria um registro na tabela de planejamento.

#### Campos de Planejamento por Serviço

| Campo | Descrição |
|---|---|
| Serviço | Nome do serviço (ex.: Concretagem, Alvenaria, Pintura) |
| Unidade de Medida | Unidade padrão do serviço (m², m³, kg, ton, un, m, h) |
| Quantidade Planejada | Volume total planejado para execução na obra |
| Valor Unitário | Custo por unidade do serviço (R$) |
| Valor Total Planejado | Calculado automaticamente: quantidade × valor unitário |
| Data Início Planejada | Data prevista para início da atividade |
| Data Fim Planejada | Data prevista para conclusão da atividade |
| Prioridade | Nível de prioridade: Alta (1), Média (2), Baixa (3) |
| Responsável | Funcionário responsável pela execução do serviço |
| Status | Não Iniciado, Em Andamento, Concluído ou Pausado |

![Planejamento de serviços da obra](placeholder_servicos_obra.png)

#### Acompanhamento da Execução de Serviços

À medida que os RDOs são registrados, o sistema atualiza automaticamente:

- **Quantidade Executada** — Soma das quantidades informadas nos RDOs.
- **Percentual Concluído** — Razão entre executado e planejado.
- **Valor Total Executado** — Custo real acumulado do serviço.
- **Data de Início Real** — Registrada na primeira execução.
- **Data de Fim Real** — Registrada quando o serviço atinge 100% de conclusão.

| Indicador | Fórmula |
|---|---|
| % Concluído | (Quantidade Executada ÷ Quantidade Planejada) × 100 |
| Desvio de Custo | Valor Total Executado − Valor Total Planejado |
| Status Automático | Atualizado conforme o percentual (0% = Não Iniciado, 1–99% = Em Andamento, 100% = Concluído) |

### 4.4.2. Cronograma

O cronograma da obra é montado a partir das datas planejadas dos serviços vinculados:

1. **Data de início da obra** — Definida no cadastro da obra.
2. **Data de previsão de término** — Definida no cadastro da obra.
3. **Datas dos serviços** — Cada serviço possui data de início e fim planejados.
4. O sistema compara as datas planejadas com as datas reais para identificar atrasos.

> **Dica:** Mantenha as datas dos serviços atualizadas para que o dashboard executivo reflita com precisão o andamento do projeto.

---

## 4.5. Acompanhamento da Obra

### 4.5.1. Dashboard Executivo

Ao acessar os detalhes de uma obra em `/obras/detalhes/<id>`, o sistema exibe um painel executivo com os principais indicadores:

![Dashboard executivo da obra](placeholder_dashboard_obra.png)

#### KPIs Principais

| KPI | Descrição |
|---|---|
| Custo Total | Somatório de todos os custos apurados: mão de obra + alimentação + transporte + diversos |
| Custo de Mão de Obra | Calculado com base nos registros de ponto × valor/hora do funcionário, incluindo horas extras a 150% |
| Custo de Alimentação | Soma dos registros de alimentação vinculados à obra no período |
| Custos Diversos | Lançamentos avulsos de custos operacionais da obra |
| Custo de Transporte | Despesas de veículos associadas à obra |
| Dias Trabalhados | Quantidade de dias distintos com registros de ponto na obra |
| Funcionários Alocados | Total de funcionários distintos que registraram ponto na obra |
| Orçamento Restante | Orçamento − Custo Total (com indicador visual de alerta se negativo) |

#### Composição de Custos

O sistema apresenta a composição de custos de forma visual, permitindo identificar rapidamente qual categoria representa a maior parcela do gasto:

| Categoria | Fonte de Dados |
|---|---|
| Mão de Obra | Registros de ponto × valor/hora (horas normais + horas extras × 1,5) |
| Alimentação | Módulo de Alimentação — registros vinculados à obra |
| Transporte | Módulo de Veículos — despesas com obra_id associado |
| Diversos | Lançamentos manuais de custos avulsos (OutroCusto) |

### 4.5.2. Lançamento de Custos

Para registrar custos operacionais diretamente na obra:

1. Acesse a obra em `/obras/detalhes/<id>`.
2. Na seção **Custos**, clique em **Novo Lançamento**.
3. Preencha os campos:

| Campo | Descrição |
|---|---|
| Descrição | Descrição do custo (ex.: "Material elétrico", "Locação de betoneira") |
| Valor (R$) | Valor do lançamento |
| Data | Data de referência do custo |
| Categoria | Tipo do custo para classificação |
| Observações | Informações complementares |

4. Clique em **Salvar** para registrar o custo.

> **Nota:** Custos de mão de obra e alimentação são calculados automaticamente a partir dos módulos de Ponto e Alimentação. Não é necessário lançá-los manualmente.

### 4.5.3. Registro Diário de Obra (RDO)

O RDO é o instrumento principal de registro do dia a dia da obra. Cada obra na listagem possui um botão **+RDO** que direciona para `/funcionario/rdo/novo?obra_id=<id>`.

#### Como criar um RDO a partir da obra

1. Na listagem de obras (`/obras`), localize a obra desejada.
2. Clique no botão **+RDO** no card da obra.
3. O formulário de RDO será aberto com a obra já pré-selecionada.
4. Preencha as informações do dia: condições climáticas, mão de obra presente, equipamentos utilizados, serviços executados, ocorrências e fotos.
5. Clique em **Salvar** para registrar o RDO.

> **Referência:** Para detalhes completos sobre o preenchimento do RDO, consulte o **Capítulo 6 — Registro Diário de Obra (RDO)**.

#### Informações registradas no RDO

| Seção | Dados Registrados |
|---|---|
| Mão de Obra | Funcionários presentes, horas trabalhadas, função exercida |
| Equipamentos | Equipamentos utilizados, horas de operação, status |
| Serviços/Subatividades | Serviços executados com quantidades medidas |
| Ocorrências | Eventos relevantes: acidentes, paralisações, visitas técnicas |
| Fotos | Registro fotográfico do andamento da obra |
| Condições Climáticas | Tempo (ensolarado, nublado, chuvoso) e impacto nas atividades |

---

## 4.6. Controle Financeiro da Obra

O controle financeiro da obra integra dados de múltiplos módulos para fornecer uma visão completa da saúde financeira do projeto.

### Orçado vs. Realizado

| Indicador | Cálculo |
|---|---|
| Valor Orçado | Campo `orcamento` definido no cadastro da obra |
| Valor do Contrato | Campo `valor_contrato` — receita prevista do projeto |
| Custo Realizado | Soma de: mão de obra + alimentação + transporte + custos diversos |
| Margem Bruta | Valor do Contrato − Custo Realizado |
| Margem Percentual | (Margem Bruta ÷ Valor do Contrato) × 100 |
| Desvio Orçamentário | Custo Realizado − Valor Orçado |
| % Consumido do Orçamento | (Custo Realizado ÷ Valor Orçado) × 100 |

![Gráfico orçado vs realizado](placeholder_orcado_realizado.png)

### Análise de Desvios

O sistema destaca automaticamente situações que requerem atenção:

| Situação | Indicador Visual | Ação Recomendada |
|---|---|---|
| Custo dentro do orçamento (< 80%) | Verde | Projeto sob controle |
| Custo próximo do limite (80–100%) | Amarelo | Revisar projeções de custo |
| Custo acima do orçamento (> 100%) | Vermelho | Ação corretiva urgente necessária |
| Margem negativa | Vermelho piscante | Renegociar contrato ou reduzir custos |

### Fluxo de Caixa da Obra

O fluxo de caixa por obra considera:

1. **Entradas** — Parcelas do contrato recebidas (registradas no módulo Financeiro).
2. **Saídas** — Todos os custos apurados (mão de obra, alimentação, transporte, diversos).
3. **Saldo** — Diferença entre entradas e saídas acumuladas.

> **Integração:** O controle financeiro da obra está diretamente integrado ao módulo **Financeiro** (acessível em **Financeiro** no menu de navegação). Lançamentos financeiros com centro de custo vinculado à obra são automaticamente considerados na análise.

---

## 4.7. Relatórios de Obras

O módulo de relatórios permite gerar documentos consolidados sobre o andamento e os custos das obras. Acesse pelo menu **Relatórios** ou diretamente na página de detalhes da obra.

### Tipos de Relatórios Disponíveis

| Relatório | Descrição | Formato |
|---|---|---|
| Resumo Executivo da Obra | Visão geral com KPIs, progresso e status financeiro | PDF |
| Relatório de Custos | Detalhamento de todos os custos por categoria e período | PDF |
| Relatório de Serviços | Comparação entre planejado e executado por serviço | PDF |
| Relatório de Mão de Obra | Funcionários alocados, horas trabalhadas e custos | PDF |
| Relatório de RDOs | Consolidado dos Registros Diários de Obra do período | PDF |
| Relatório Fotográfico | Compilação das fotos registradas nos RDOs | PDF |

### Gerando um Relatório

1. Acesse a obra desejada em `/obras/detalhes/<id>`.
2. Clique em **Relatórios** ou **Gerar Relatório**.
3. Selecione o tipo de relatório desejado.
4. Defina o período de análise (data início e data fim).
5. Clique em **Gerar PDF**.
6. O sistema processará os dados e disponibilizará o arquivo para download.

![Geração de relatórios de obras](placeholder_relatorios_obra.png)

> **Dica:** Para uma análise comparativa entre múltiplas obras, utilize o módulo **Relatórios** no menu principal, que oferece visões consolidadas de todo o portfólio.

---

## Operações Administrativas

### Editando uma Obra

1. Acesse a listagem de obras em `/obras`.
2. Clique no card da obra desejada para acessar os detalhes.
3. Clique em **Editar** para abrir o formulário de edição em `/obras/editar/<id>`.
4. Altere os campos necessários e clique em **Salvar**.

### Alterando o Status da Obra

O status de uma obra pode ser alternado rapidamente:

1. Na página de detalhes da obra, clique no botão de **Alterar Status**.
2. O sistema alterna o status via requisição POST para `/obras/toggle-status/<id>`.
3. Os status disponíveis são:

| Status | Descrição |
|---|---|
| Em andamento | Obra em execução ativa |
| Concluída | Obra finalizada e entregue |
| Paralisada | Obra temporariamente interrompida |
| Cancelada | Obra cancelada definitivamente |

### Excluindo uma Obra

1. Acesse a página de detalhes da obra.
2. Clique em **Excluir Obra**.
3. Confirme a exclusão na caixa de diálogo.
4. O sistema envia uma requisição POST para `/obras/excluir/<id>`.

> **Atenção:** A exclusão de uma obra remove permanentemente todos os dados associados, incluindo serviços vinculados, custos e registros de alocação. RDOs já registrados são mantidos no sistema para fins de histórico.

---

## Resumo de URLs do Módulo

| Ação | URL | Método |
|---|---|---|
| Listagem de obras | `/obras` | GET |
| Nova obra | `/obras/nova` | GET / POST |
| Detalhes da obra | `/obras/detalhes/<id>` | GET |
| Editar obra | `/obras/editar/<id>` | GET / POST |
| Excluir obra | `/obras/excluir/<id>` | POST |
| Alternar status | `/obras/toggle-status/<id>` | POST |
| Novo RDO vinculado | `/funcionario/rdo/novo?obra_id=<id>` | GET |

---

*Próximo capítulo: [Capítulo 5 — Gestão de Veículos e Frota](05_manual_veiculos.md)*
