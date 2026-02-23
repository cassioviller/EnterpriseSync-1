# Capítulo 2 — Módulo Dashboard

**SIGE - Estruturas do Vale (EnterpriseSync)**
Manual do Usuário — Versão 8.0

---

## 2.1. Introdução ao Dashboard

O **Dashboard** é a tela principal do SIGE e funciona como um painel de controle centralizado para a gestão da sua empresa. Ao acessar o sistema, o Dashboard apresenta uma visão consolidada e em tempo real dos principais indicadores operacionais, financeiros e de produtividade.

**Principais funcionalidades do Dashboard:**

1. **Visão Geral (KPIs)** — Exibe cartões com indicadores-chave: Funcionários Ativos, Obras Ativas, Veículos e Custos do Período.
2. **Custos Detalhados do Período** — Apresenta a composição dos custos em categorias: Alimentação, Transporte, Mão de Obra e Total, com valores em R$.
3. **Propostas Comerciais** — Mostra estatísticas de propostas enviadas, aprovadas, rejeitadas e em rascunho.
4. **Obras e RDO** — Lista as obras ativas com acesso rápido para criação de novos Relatórios Diários de Obra (RDO).
5. **Gráficos e Evolução** — Gráfico de evolução de propostas e tendências ao longo do tempo.

> **Importante:** O Dashboard exibe dados filtrados pelo **admin_id** do usuário logado, garantindo o isolamento multi-tenant. Cada empresa visualiza apenas os seus próprios dados.

[IMAGEM: Dashboard principal com visão geral dos KPIs e custos]

---

## 2.2. Acessando o Dashboard

### 2.2.1. Após o Login

Ao realizar o login no SIGE com suas credenciais de administrador, o sistema redireciona automaticamente para o Dashboard principal.

**Passo a passo:**

1. Acesse o endereço do sistema no navegador (ex.: `https://sige.cassioviller.tech`)
2. Informe seu **e-mail** e **senha** na tela de login
3. Clique em **Entrar**
4. O sistema redirecionará automaticamente para a URL `/dashboard`

> **Nota:** O comportamento de redirecionamento varia conforme o tipo de usuário:
>
> | Tipo de Usuário | Redirecionamento | Dashboard Exibido |
> |:----------------|:-----------------|:------------------|
> | ADMIN | `/dashboard` | Dashboard Administrativo completo |
> | FUNCIONÁRIO | `/funcionario/dashboard` | Dashboard do Funcionário (simplificado) |
> | SUPER_ADMIN | `/super-admin/dashboard` | Dashboard do Super Administrador |

### 2.2.2. Menu de Navegação

O Dashboard é acessível a qualquer momento por meio da barra de navegação superior (navbar). A barra apresenta o logotipo **SIGE - Estruturas do Vale** à esquerda, com fundo verde, e os seguintes itens de menu:

| Nº | Item do Menu | Descrição |
|:--:|:-------------|:----------|
| 1 | Dashboard | Painel principal com KPIs e indicadores |
| 2 | RDOs | Relatórios Diários de Obra |
| 3 | Obras | Gestão de obras e projetos |
| 4 | Funcionários | Cadastro de colaboradores |
| 5 | Equipe | Alocação de equipes de campo |
| 6 | Ponto | Controle de ponto eletrônico |
| 7 | Propostas | Propostas comerciais e orçamentos |
| 8 | Financeiro | Gestão financeira |
| 9 | Veículos | Gestão de frota |
| 10 | Alimentação | Controle de refeições |
| 11 | Almoxarifado | Estoque e materiais |
| 12 | Relatórios | Relatórios consolidados |

Para retornar ao Dashboard de qualquer tela, basta clicar no item **Dashboard** no menu superior.

[IMAGEM: Barra de navegação verde com os itens de menu do SIGE]

### 2.2.3. Filtro de Período

O Dashboard permite filtrar os dados exibidos por período. O sistema detecta automaticamente o mês mais recente com registros de ponto cadastrados e utiliza esse intervalo como padrão. Para alterar o período:

1. Localize os campos **Data Início** e **Data Fim** no topo do Dashboard
2. Selecione as datas desejadas
3. Clique em **Filtrar** para atualizar os indicadores

> **Dica:** Se não houver registros para o período selecionado, os cartões de KPI exibirão valores zerados. Verifique se existem dados lançados no período escolhido.

---

## 2.3. KPIs Principais

A seção **Visão Geral** do Dashboard apresenta 4 cartões de KPI (Key Performance Indicators) que oferecem uma fotografia instantânea da operação da empresa.

[IMAGEM: Seção Visão Geral com os 4 cartões de KPI]

### 2.3.1. Funcionários Ativos

| Atributo | Detalhe |
|:---------|:--------|
| **Indicador** | Quantidade de funcionários com status ativo |
| **Fonte dos dados** | Tabela `funcionario` filtrada por `admin_id` e `ativo = true` |
| **Exemplo** | Exibe um número como **10** (dez funcionários ativos) |
| **Atualização** | Em tempo real, a cada acesso ao Dashboard |

**Como interpretar:**

- O número reflete todos os colaboradores cadastrados e com status **Ativo** no sistema
- Funcionários desligados ou inativos não são contabilizados
- Para gerenciar funcionários, acesse o módulo **Funcionários** pelo menu superior

### 2.3.2. Obras Ativas

| Atributo | Detalhe |
|:---------|:--------|
| **Indicador** | Quantidade de obras com status ativo (em andamento, planejamento) |
| **Fonte dos dados** | Tabela `obra` filtrada por `admin_id` e status ativo |
| **Exemplo** | Exibe um número como **8** (oito obras ativas) |
| **Atualização** | Em tempo real, a cada acesso ao Dashboard |

**Como interpretar:**

- Contabiliza obras nos status: `ATIVO`, `andamento`, `Em andamento`, `ativa` e `planejamento`
- Obras finalizadas ou canceladas não aparecem neste indicador
- Clique no cartão ou acesse **Obras** no menu para ver os detalhes de cada obra

### 2.3.3. Veículos

| Atributo | Detalhe |
|:---------|:--------|
| **Indicador** | Quantidade de veículos ativos na frota |
| **Fonte dos dados** | Tabela `veiculo` filtrada por `admin_id` e `ativo = true` |
| **Exemplo** | Exibe um número como **3** (três veículos na frota) |
| **Atualização** | Em tempo real, a cada acesso ao Dashboard |

**Como interpretar:**

- Inclui todos os veículos cadastrados com status ativo
- Veículos baixados ou desativados não são contabilizados
- Para gerenciar a frota, acesse o módulo **Veículos** pelo menu superior

### 2.3.4. Custos do Período (Financeiro)

| Atributo | Detalhe |
|:---------|:--------|
| **Indicador** | Valor total dos custos no período selecionado (em R$) |
| **Fonte dos dados** | Soma dos custos de mão de obra, alimentação e transporte |
| **Exemplo** | Exibe um valor como **R$ 45.320,00** |
| **Atualização** | Conforme o filtro de período aplicado |

**Como interpretar:**

- Representa a soma consolidada de todos os custos operacionais do período
- O valor é exibido em Reais (R$) com formatação brasileira
- Para análise detalhada, consulte a seção **Custos Detalhados do Período** (abaixo dos KPIs)

---

## 2.4. Gráficos e Visualizações

O Dashboard apresenta seções gráficas e detalhadas que permitem uma análise mais aprofundada da operação.

### 2.4.1. Custos Detalhados do Período

A seção **Custos Detalhados do Período** apresenta cartões individuais com a decomposição dos custos operacionais:

| Cartão | Descrição | Exemplo |
|:-------|:----------|:--------|
| **Alimentação** | Custos com refeições, vales e cestas básicas | R$ 8.500,00 |
| **Transporte** | Custos com combustível, pedágios e deslocamentos | R$ 5.200,00 |
| **Mão de Obra** | Custos com salários, horas extras e encargos | R$ 28.600,00 |
| **Total** | Soma de todas as categorias | R$ 42.300,00 |

[IMAGEM: Cartões de Custos Detalhados do Período mostrando Alimentação, Transporte, Mão de Obra e Total]

**Como utilizar:**

1. Os valores são calculados automaticamente com base nos lançamentos do período selecionado
2. Compare os custos entre categorias para identificar onde estão os maiores gastos
3. Utilize o filtro de período para analisar a evolução mensal dos custos
4. Para detalhes de cada categoria, acesse os módulos específicos (Alimentação, Veículos, Funcionários)

### 2.4.2. Propostas Comerciais

A seção **Propostas Comerciais** exibe estatísticas consolidadas sobre as propostas da empresa:

- **Total de Propostas** — Quantidade total de propostas no período
- **Taxa de Conversão** — Percentual de propostas aprovadas em relação ao total
- **Valor Médio** — Valor médio das propostas aprovadas
- **Propostas por Mês** — Média mensal de propostas criadas nos últimos 6 meses

**Status de Propostas:**

| Status | Descrição | Cor |
|:-------|:----------|:----|
| Aprovada | Proposta aceita pelo cliente | Verde |
| Enviada | Proposta enviada aguardando resposta | Azul |
| Rascunho | Proposta em elaboração | Cinza |
| Rejeitada | Proposta não aceita pelo cliente | Vermelho |
| Expirada | Proposta enviada cuja validade expirou | Laranja |

[IMAGEM: Seção de Propostas Comerciais com estatísticas e status]

### 2.4.3. Evolução de Propostas

O gráfico **Evolução de Propostas** apresenta visualmente a tendência de criação e aprovação de propostas ao longo do tempo.

**Como interpretar o gráfico:**

1. O eixo horizontal (X) representa os meses
2. O eixo vertical (Y) representa a quantidade de propostas
3. As linhas ou barras mostram a evolução por status (aprovadas, enviadas, rejeitadas)
4. Identifique tendências de crescimento ou queda na atividade comercial

[IMAGEM: Gráfico de Evolução de Propostas ao longo do tempo]

### 2.4.4. Obras e RDO

A seção **Obras e RDO** lista as obras ativas com informações resumidas e ações rápidas:

| Coluna | Descrição |
|:-------|:----------|
| Nome da Obra | Identificação da obra |
| Status | Situação atual (ativo, em andamento, planejamento) |
| Progresso | Percentual de conclusão baseado nos RDOs |
| Ação | Botão **+RDO** para criar novo Relatório Diário de Obra |

**Como criar um RDO a partir do Dashboard:**

1. Localize a obra desejada na lista **Obras e RDO**
2. Clique no botão **+RDO** ao lado da obra
3. O sistema abrirá o formulário de criação de RDO já vinculado à obra selecionada
4. Preencha os dados do relatório e salve

[IMAGEM: Lista de Obras e RDO com botões de ação rápida]

> **Dica:** O progresso de cada obra é calculado automaticamente com base nas subatividades registradas no RDO mais recente. Mantenha os RDOs atualizados para refletir o andamento real.

---

## 2.5. Dashboard Executivo por Obra

Além do Dashboard principal, o SIGE oferece um **Dashboard Executivo** individual para cada obra. Este painel detalhado permite acompanhar os indicadores específicos de um projeto.

**Como acessar:**

1. Acesse o módulo **Obras** pelo menu superior
2. Clique na obra desejada para abrir seus detalhes
3. A URL será no formato `/obras/detalhes/<id>` (onde `<id>` é o identificador da obra)

**Informações disponíveis no Dashboard Executivo:**

| Seção | Descrição |
|:------|:----------|
| Dados Gerais | Nome, cliente, endereço, datas de início e previsão de término |
| Progresso | Percentual de conclusão geral da obra |
| RDOs | Lista de Relatórios Diários vinculados à obra |
| Equipe Alocada | Funcionários designados para a obra |
| Custos | Detalhamento dos custos operacionais por categoria |
| Serviços | Serviços contratados e executados na obra |

[IMAGEM: Dashboard Executivo de uma obra com indicadores detalhados]

> **Nota:** O Dashboard Executivo por obra é especialmente útil para gestores de projeto que precisam acompanhar o andamento de obras específicas, com dados consolidados de mão de obra, materiais e progresso físico.

---

## 2.6. Dashboard do Funcionário

Quando um usuário do tipo **FUNCIONÁRIO** acessa o sistema, ele é redirecionado automaticamente para o **Dashboard do Funcionário**, uma versão simplificada e focada nas atividades do colaborador.

**Título da página:** *Dashboard do Funcionário*

### 2.6.1. Cartões de Resumo

O Dashboard do Funcionário apresenta 4 cartões informativos:

| Cartão | Descrição |
|:-------|:----------|
| **Obras Disponíveis** | Quantidade de obras às quais o funcionário está alocado |
| **RDOs Registrados** | Total de RDOs criados pelo funcionário |
| **RDOs Rascunho** | Quantidade de RDOs salvos como rascunho (não finalizados) |
| **Acesso** | Informações sobre o nível de acesso do funcionário |

### 2.6.2. Ações Rápidas

A seção **Ações Rápidas** oferece botões de acesso direto às principais funcionalidades:

| Botão | Ação |
|:------|:-----|
| **Criar RDO** | Abre o formulário para criação de um novo Relatório Diário de Obra |
| **Ver Todos os RDOs** | Lista todos os RDOs do funcionário |
| **Ver Obras** | Exibe as obras disponíveis para o funcionário |
| **Sair** | Encerra a sessão do usuário |

### 2.6.3. RDOs Recentes e Obras Disponíveis

Abaixo dos cartões e ações rápidas, o Dashboard do Funcionário exibe:

- **RDOs Recentes** — Lista dos últimos RDOs criados pelo funcionário, com data, obra e status
- **Obras Disponíveis** — Lista das obras às quais o funcionário está alocado, com nome e status

[IMAGEM: Dashboard do Funcionário com cartões, ações rápidas e listas]

---

## 2.7. Alertas e Notificações

O Dashboard apresenta alertas e notificações visuais para situações que requerem atenção do administrador:

### 2.7.1. Tipos de Alertas

| Tipo | Descrição | Indicador Visual |
|:-----|:----------|:-----------------|
| **Propostas Expirando** | Propostas enviadas cuja validade está próxima do vencimento | Badge laranja |
| **Obras sem RDO** | Obras ativas que não tiveram RDO registrado recentemente | Destaque na lista de obras |
| **Custos Elevados** | Quando os custos do período ultrapassam a média histórica | Cartão com destaque |
| **Funcionários sem Alocação** | Colaboradores ativos não vinculados a nenhuma obra | Indicador no cartão |

### 2.7.2. Boas Práticas para Monitoramento

1. **Acesse o Dashboard diariamente** — Verifique os KPIs e alertas no início do expediente
2. **Mantenha os RDOs atualizados** — Garanta que cada obra tenha pelo menos um RDO por dia útil
3. **Monitore os custos** — Compare os custos do período atual com meses anteriores
4. **Acompanhe as propostas** — Verifique propostas enviadas que aguardam resposta do cliente
5. **Revise a alocação** — Confirme que todos os funcionários estão designados a obras ativas

---

## 2.8. Personalização do Dashboard

O Dashboard do SIGE exibe dados de forma automática com base no perfil do usuário logado. Embora o layout seja padronizado, existem formas de personalizar a experiência:

### 2.8.1. Filtros de Período

A principal forma de personalização é o **filtro de período**, que permite ajustar o intervalo de datas para todos os indicadores do Dashboard:

| Parâmetro | Descrição | Formato |
|:----------|:----------|:--------|
| `data_inicio` | Data de início do período | `AAAA-MM-DD` |
| `data_fim` | Data de fim do período | `AAAA-MM-DD` |

**Exemplo de URL com filtro:**
```
/dashboard?data_inicio=2024-07-01&data_fim=2024-07-31
```

### 2.8.2. Detecção Automática de Período

Quando nenhum filtro é aplicado manualmente, o sistema executa a seguinte lógica:

1. Busca a data do **registro de ponto mais recente** vinculado ao `admin_id` do usuário
2. Utiliza o **mês completo** dessa data como período padrão
3. Caso não existam registros, utiliza **Julho/2024** como período fallback

### 2.8.3. Isolamento Multi-Tenant

Todos os dados exibidos no Dashboard respeitam o isolamento multi-tenant:

- Cada administrador visualiza **apenas os dados da sua empresa**
- O filtro por `admin_id` é aplicado automaticamente em todas as consultas
- Não é possível visualizar dados de outras empresas, mesmo conhecendo os IDs

> **Segurança:** O sistema verifica automaticamente o `admin_id` do usuário logado e aplica o filtro em todas as queries de banco de dados. Esse comportamento é transparente para o usuário e não requer configuração.

---

## 2.9. Resumo do Capítulo

| Seção | Conteúdo |
|:------|:---------|
| 2.1 | Introdução e visão geral do Dashboard |
| 2.2 | Como acessar o Dashboard e navegar pelo menu |
| 2.3 | KPIs: Funcionários, Obras, Veículos e Custos |
| 2.4 | Gráficos: Custos detalhados, Propostas e Obras/RDO |
| 2.5 | Dashboard Executivo por Obra |
| 2.6 | Dashboard do Funcionário |
| 2.7 | Alertas e notificações |
| 2.8 | Personalização e filtros |

**Próximo capítulo:** [Capítulo 3 — Módulo Funcionários](03_manual_funcionarios.md)

---

*SIGE - Estruturas do Vale (EnterpriseSync) — Manual do Usuário v8.0*
*Documento gerado em Fevereiro/2026*
