# Descrição das Páginas do Sistema SIGE v6.1

## 1. Dashboard Principal

### Visão Geral
O Dashboard é a página inicial do sistema que apresenta uma visão executiva consolidada de todos os indicadores-chave de desempenho da empresa.

### Características Principais
- **Filtros de Data Globais**: Controle temporal para análise de períodos específicos (último mês, 3 meses, ano atual)
- **KPIs Executivos**: Cards com métricas essenciais como:
  - Total de funcionários ativos
  - Centros de custo em andamento
  - Custos totais do período
  - Horas trabalhadas no mês
  - Valor total em alimentação
  - Custos operacionais de veículos

### Funcionalidades
- **Gráficos Interativos**: Visualizações em Chart.js mostrando:
  - Distribuição de funcionários por departamento
  - Evolução de custos por centro de custo
  - Tendências de produtividade ao longo do tempo
- **Navegação Rápida**: Botões de acesso direto para módulos principais
- **Alertas Visuais**: Indicadores de atenção para métricas críticas

### Layout
- Grid responsivo com cards coloridos para cada KPI
- Seção de filtros no topo para controle temporal
- Gráficos em duas colunas na parte inferior

---

## 2. Página de Funcionários

### Visão Geral
Central de gestão completa do quadro de pessoal, incluindo cadastro, controle de KPIs individuais e análise de desempenho.

### Características Principais
- **Cadastro Completo**: Formulário abrangente com dados pessoais, profissionais e documentos
- **Filtros Avançados**: Controle por período, departamento, função e status
- **KPIs Consolidados**: Métricas gerais da equipe no período selecionado:
  - Total de funcionários ativos
  - Horas trabalhadas consolidadas
  - Custos totais de mão de obra
  - Média de produtividade da equipe

### Funcionalidades
- **Visualização Dual**: Cards visuais e tabela detalhada
- **Busca Inteligente**: Filtros por nome, CPF, função ou departamento
- **Ações Rápidas**: Cadastro via modal ou formulário completo
- **Exportação**: Relatórios em CSV, Excel e PDF

### Layout
- Cabeçalho com filtros de período e botões de ação
- Grid de cards com fotos e informações básicas
- Tabela responsiva com dados detalhados e KPIs individuais

---

## 3. Perfil do Funcionário

### Visão Geral
Página detalhada individual com análise completa de desempenho, custos e histórico trabalhista.

### Características Principais
- **Dados Cadastrais**: Informações pessoais, profissionais e foto
- **15 KPIs Individuais**: Layout 4-4-4-3 com métricas específicas:

#### Linha 1 - KPIs Básicos (4 indicadores)
- Horas Trabalhadas
- Horas Extras
- Faltas
- Atrasos

#### Linha 2 - KPIs Analíticos (4 indicadores)
- Produtividade (%)
- Absenteísmo (%)
- Média Diária
- Faltas Justificadas

#### Linha 3 - KPIs Financeiros (4 indicadores)
- Custo Mão de Obra
- Custo Alimentação
- Custo Transporte
- Outros Custos

#### Linha 4 - KPIs Resumo (3 indicadores)
- Horas Perdidas
- Eficiência (%)
- Valor Falta Justificada

### Funcionalidades
- **Controle de Ponto**: Registro detalhado com tipos de lançamento:
  - Trabalho normal, faltas, faltas justificadas
  - Feriado trabalhado, sábado/domingo extras
  - Meio período, trabalho sem intervalo
- **Gestão de Alimentação**: Controle de refeições por restaurante
- **Outros Custos**: Vale transporte, benefícios, descontos
- **Filtros Temporais**: Análise por período específico

### Layout
- Seção de dados pessoais com foto
- Grid 4-4-4-3 dos KPIs com cores diferenciadas
- Abas organizadas: Ponto, Alimentação, Outros Custos

---

## 4. Página de Veículos

### Visão Geral
Gestão completa da frota empresarial com controle de status, custos operacionais e manutenção.

### Características Principais
- **Controle de Frota**: Cadastro completo de veículos com:
  - Modelo, marca, placa, ano
  - Status operacional (Disponível, Em Uso, Manutenção)
  - Tipo de veículo (Caminhão, Van, Carro)
- **KPIs da Frota**: Indicadores operacionais:
  - Total de veículos
  - Veículos disponíveis
  - Veículos em manutenção
  - Veículos em operação

### Funcionalidades
- **Gestão de Custos**: Controle de gastos por veículo:
  - Combustível
  - Manutenção
  - Seguro
  - Licenciamento
- **Histórico Operacional**: Registro de uso por centro de custo
- **Alertas de Manutenção**: Notificações preventivas
- **Relatórios**: Custos por veículo, eficiência operacional

### Layout
- Cards coloridos com KPIs da frota
- Tabela detalhada com status visual
- Modais para cadastro e edição

---

## 5. Página de Alimentação

### Visão Geral
Controle completo dos gastos com alimentação, incluindo gestão de restaurantes e lançamentos por funcionário.

### Características Principais
- **Controle de Custos**: Monitoramento de gastos alimentares:
  - Total do mês
  - Registros diários
  - Média diária
  - Funcionários atendidos
- **Gestão de Restaurantes**: Cadastro de estabelecimentos parceiros
- **Lançamentos**: Registro de refeições por funcionário e centro de custo

### Funcionalidades
- **Lançamento em Lote**: Seleção múltipla de funcionários
- **Controle de Tipos**: Almoço, lanche, jantar
- **Validação de Duplicatas**: Prevenção de registros duplicados
- **Relatórios**: Gastos por funcionário, por centro de custo, por restaurante

### Layout
- Cards com resumo financeiro
- Tabela de restaurantes cadastrados
- Modal funcional para lançamentos

---

## 6. Página de Funções

### Visão Geral
Gestão de cargos e funções da empresa com controle salarial e definição de responsabilidades.

### Características Principais
- **Cadastro de Funções**: Definição completa de cargos:
  - Nome da função
  - Descrição detalhada
  - Salário base
  - Quantidade de funcionários
- **Controle Salarial**: Base para cálculos de custos de mão de obra

### Funcionalidades
- **Gestão Hierárquica**: Organização de cargos por nível
- **Análise de Custos**: Impacto salarial por função
- **Vinculação**: Associação com funcionários ativos
- **Histórico**: Registro de alterações e criação

### Layout
- Tabela organizada com informações essenciais
- Modal para cadastro e edição
- Indicadores de quantidade de funcionários por função

---

## 7. Página de Horários de Trabalho

### Visão Geral
Configuração e gestão de jornadas de trabalho com integração completa ao sistema de KPIs.

### Características Principais
- **Definição de Jornadas**: Configuração de horários:
  - Entrada, saída, intervalos
  - Dias da semana de trabalho
  - Horas diárias e semanais
  - Valor da hora trabalhada
- **Integração com KPIs**: Base para cálculos de:
  - Produtividade
  - Horas extras
  - Atrasos
  - Custos de mão de obra

### Funcionalidades
- **Flexibilidade**: Diferentes tipos de jornada:
  - Segunda a sexta
  - Segunda a sábado
  - Escalas alternadas
  - Plantões especiais
- **Cálculos Automáticos**: Integração com engine de KPIs v4.0
- **Vinculação**: Associação com funcionários específicos

### Layout
- Tabela com configurações de horário
- Badges coloridos para dias da semana
- Indicadores de funcionários por horário

---

## Integração com Centros de Custo

### Tratamento de Centros de Custo
Em todo o sistema, os **centros de custo** são tratados como unidades de controle financeiro e operacional:

- **Associação**: Todos os lançamentos (ponto, alimentação, custos) são vinculados a centros de custo específicos
- **Controle Financeiro**: Relatórios e análises agrupam custos por centro
- **Análise de Rentabilidade**: Comparação de custos vs. receitas por centro
- **Gestão Estratégica**: Tomada de decisões baseada em performance por centro

### Funcionalidades Integradas
- **Filtros Universais**: Todos os módulos permitem filtrar por centro de custo
- **Relatórios Consolidados**: Análises financeiras por centro
- **KPIs Específicos**: Indicadores individuais por centro de custo
- **Controle de Orçamento**: Acompanhamento de limite de gastos por centro

Este sistema integrado permite uma gestão empresarial completa com foco em produtividade, controle de custos e análise de desempenho por centro de custo.