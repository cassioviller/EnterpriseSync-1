# Mapeamento de Módulos - EnterpriseSync

## 📋 Visão Geral do Sistema

O EnterpriseSync é um sistema completo de gestão empresarial com foco em construção civil, contendo **18 módulos integrados** e **97 modelos de dados**.

---

## 🗂️ Módulos Principais

### 1. **Dashboard** (Painel de Controle)
- **Arquivo**: `views/dashboard.py` (52K)
- **Template**: `dashboard.html`
- **Funcionalidades**:
  - Visão geral da empresa
  - KPIs gerais (funcionários, obras, veículos, custos)
  - Gráficos e estatísticas
  - Alertas e notificações
  - Dashboard executivo por obra

### 2. **Funcionários** (Gestão de Pessoal)
- **Arquivo**: `views/employees.py` (46K)
- **Templates**: `funcionarios.html`, `funcionario_form.html`, `funcionario_perfil.html`, `funcionario_dashboard.html`
- **Funcionalidades**:
  - CRUD de funcionários
  - Cadastro de dados pessoais
  - Vinculação a departamentos e funções
  - Gestão de horários de trabalho
  - Reconhecimento facial
  - Relatórios de funcionários
  - Dashboard individual do funcionário

### 3. **Obras** (Gestão de Projetos)
- **Arquivo**: `views/obras.py` (71K)
- **Templates**: `obras.html`, `obras_moderno.html`, `obra_form.html`, `dashboard_executivo_obra.html`
- **Funcionalidades**:
  - CRUD de obras
  - Cadastro de serviços da obra
  - Gestão de custos
  - Cálculo de progresso
  - Vinculação de funcionários
  - Vinculação de veículos
  - Dashboard executivo por obra
  - Relatórios de obras

### 4. **RDO** (Relatório Diário de Obra)
- **Arquivo**: `views/rdo.py` (193K)
- **Template**: `rdo_lista_unificada.html`
- **Funcionalidades**:
  - Criação de RDO diário
  - Registro de atividades e subatividades
  - Upload de fotos
  - Registro de clima e condições
  - Registro de mão de obra
  - Registro de equipamentos
  - Cálculo de progresso automático
  - Aprovação de RDOs
  - Histórico de RDOs

### 5. **Veículos** (Gestão de Frota)
- **Arquivo**: `views/vehicles.py` (87K)
- **Templates**: `veiculos_lista.html`, `veiculos_novo.html`, `veiculos_editar.html`, `veiculos_detalhes.html`, `uso_veiculo_novo.html`, `uso_veiculo_editar.html`, `custo_veiculo_novo.html`, `custo_veiculo_editar.html`
- **Funcionalidades**:
  - CRUD de veículos
  - Registro de usos (viagens)
  - Registro de custos (manutenção, combustível)
  - Vinculação a obras
  - Relatórios de uso e custos
  - Dashboard de veículos
  - Exportação de dados

### 6. **Ponto** (Controle de Ponto Eletrônico)
- **Arquivo**: `views/employees.py` (dentro do módulo de funcionários)
- **Templates**: `ponto.html`, `ponto_form.html`, `controle_ponto.html`
- **Funcionalidades**:
  - Registro de ponto (entrada/saída)
  - Reconhecimento facial para ponto
  - Controle de ponto por obra
  - Registro manual de ponto
  - Edição de registros
  - Relatórios de ponto
  - Cálculo de horas trabalhadas

### 7. **Alimentação** (Gestão de Restaurantes)
- **Arquivo**: `views/obras.py` (dentro do módulo de obras)
- **Templates**: `alimentacao.html`, `restaurantes.html`, `restaurante_form.html`, `restaurante_detalhes.html`, `controle_alimentacao.html`
- **Funcionalidades**:
  - CRUD de restaurantes
  - Registro de refeições
  - Controle de custos de alimentação
  - Vinculação a obras
  - Relatórios de alimentação

### 8. **Financeiro** (Gestão Financeira)
- **Arquivo**: `views/dashboard.py` e `views/obras.py`
- **Templates**: Integrado em vários templates
- **Funcionalidades**:
  - Fluxo de caixa
  - Controle de custos
  - Receitas e despesas
  - Relatórios financeiros
  - Dashboard financeiro

### 9. **Relatórios** (Geração de Relatórios)
- **Arquivo**: Distribuído em vários módulos
- **Template**: `relatorios.html`
- **Funcionalidades**:
  - Relatórios de funcionários
  - Relatórios de obras
  - Relatórios de veículos
  - Relatórios financeiros
  - Exportação em PDF/Excel

### 10. **Usuários** (Gestão de Usuários do Sistema)
- **Arquivo**: `views/users.py` (3.4K)
- **Templates**: Integrado em vários templates
- **Funcionalidades**:
  - CRUD de usuários
  - Controle de permissões
  - Tipos de usuário (Admin, Gerente, Funcionário)
  - Gestão de acessos

### 11. **Autenticação** (Login e Segurança)
- **Arquivo**: `views/auth.py` (2.1K)
- **Template**: `login.html`
- **Funcionalidades**:
  - Login
  - Logout
  - Recuperação de senha
  - Controle de sessão
  - Rate limiting

### 12. **API** (Endpoints para Mobile/Integrações)
- **Arquivo**: `views/api.py` (52K)
- **Templates**: Nenhum (JSON)
- **Funcionalidades**:
  - APIs RESTful
  - Endpoints para mobile
  - Autenticação via token
  - CRUD via API
  - Integração com sistemas externos

### 13. **Admin** (Funcionalidades Administrativas)
- **Arquivo**: `views/admin.py` (9.1K)
- **Templates**: `super_admin_dashboard.html`, `admin_acessos.html`
- **Funcionalidades**:
  - Super admin dashboard
  - Diagnósticos do sistema
  - Gestão de acessos
  - Configurações globais

---

## 📊 Modelos de Dados (97 modelos)

### Principais Modelos:
- **Usuario** - Usuários do sistema
- **Funcionario** - Funcionários da empresa
- **Departamento** - Departamentos da empresa
- **Funcao** - Funções/cargos
- **Obra** - Obras/projetos
- **ServicoObra** - Serviços planejados da obra
- **ServicoObraReal** - Serviços executados
- **RDO** - Relatórios diários de obra
- **RegistroPonto** - Registros de ponto
- **Veiculo** - Veículos da frota
- **UsoVeiculo** - Usos/viagens de veículos
- **CustoVeiculo** - Custos de veículos
- **Restaurante** - Restaurantes/fornecedores
- **RefeicaoFuncionario** - Refeições registradas
- **FluxoCaixa** - Movimentações financeiras

---

## 🎯 Fluxo de Uso Típico

1. **Configuração Inicial**
   - Criar primeiro usuário admin
   - Configurar empresa
   - Criar departamentos e funções

2. **Cadastros Básicos**
   - Cadastrar funcionários
   - Cadastrar obras
   - Cadastrar veículos
   - Cadastrar restaurantes

3. **Operação Diária**
   - Registro de ponto (entrada/saída)
   - Criação de RDOs
   - Registro de usos de veículos
   - Registro de refeições

4. **Gestão e Controle**
   - Acompanhamento de obras (dashboard)
   - Controle de custos
   - Relatórios gerenciais
   - Análise de KPIs

---

## 📱 Acesso

- **Web**: Interface completa via navegador
- **Mobile**: Via API (app mobile em desenvolvimento)
- **Níveis de Acesso**:
  - Super Admin
  - Admin
  - Gerente
  - Funcionário

---

Este mapeamento serve como base para a criação dos manuais de uso do sistema.
