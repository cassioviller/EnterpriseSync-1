# Documentação Completa do Sistema SIGE v6.5
*Sistema Integrado de Gestão Empresarial - Estruturas do Vale*

---

## 1. VISÃO GERAL DO APLICATIVO

### 1.1 Nome e Propósito
- **Nome:** SIGE - Sistema Integrado de Gestão Empresarial
- **Empresa:** Estruturas do Vale
- **Setor:** Construção Civil e Engenharia
- **Propósito:** Gestão completa de recursos humanos, obras, veículos, alimentação e controle financeiro para empresas de construção

### 1.2 Tecnologias Utilizadas
**Backend:**
- Python 3.11
- Flask (Framework web)
- SQLAlchemy (ORM - Object Relational Mapping)
- Flask-Login (Autenticação)
- Flask-WTF (Formulários)
- PostgreSQL (Banco de dados principal)
- Gunicorn (Servidor WSGI)

**Frontend:**
- Bootstrap 5 (Framework CSS com tema dark)
- JavaScript Vanilla + jQuery
- Chart.js (Gráficos e visualizações)
- DataTables.js (Tabelas interativas)
- Font Awesome 6 (Ícones)

**Ferramentas de Desenvolvimento:**
- Replit (Ambiente de desenvolvimento)
- Git (Controle de versão)

### 1.3 Arquitetura Geral
- **Padrão MVC:** Model-View-Controller
- **Arquitetura Multi-Tenant:** Suporte para múltiplas organizações
- **Sistema de Roles:** Super Admin, Admin, Funcionário
- **API RESTful:** Endpoints para integração
- **Responsivo:** Interface adaptável para desktop e mobile

### 1.4 Versão Atual
**v6.5 - July 22, 2025**
- Módulo de Controle de Alimentação profissional
- Sistema multi-tenant completo
- KPI Engine v3.1 com cálculos precisos
- Interface dark/light mode

---

## 2. ESTRUTURA DE PÁGINAS E NAVEGAÇÃO

### 2.1 Hierarquia de Acesso por Tipo de Usuário

#### Super Admin (axiom/cassio123)
- `/super-admin` - Dashboard exclusivo
- Gerenciamento de administradores apenas

#### Admin (admin/admin123)
- `/` - Dashboard principal
- `/funcionarios` - Gestão de funcionários
- `/obras` - Gestão de obras e projetos
- `/veiculos` - Gestão de frota
- `/alimentacao` - Controle de alimentação
- `/rdo` - Relatório Diário de Obras
- `/relatorios` - Relatórios gerenciais
- `/financeiro` - Módulo financeiro
- `/configuracoes` - Configurações do sistema

#### Funcionário (cassio/admin123)
- `/funcionario-dashboard` - Dashboard restrito
- `/rdo` - Apenas criação de RDO
- `/veiculos/uso` - Registro de uso de veículos

### 2.2 Mapa Completo de Rotas

| Rota | Método | Acesso | Descrição |
|------|--------|--------|-----------|
| `/` | GET | Admin | Dashboard principal |
| `/login` | GET/POST | Público | Página de login |
| `/logout` | GET | Autenticado | Logout do sistema |
| `/funcionarios` | GET | Admin | Lista de funcionários |
| `/funcionarios/novo` | GET/POST | Admin | Cadastro de funcionário |
| `/funcionarios/<id>` | GET | Admin | Detalhes do funcionário |
| `/funcionarios/<id>/perfil` | GET | Admin | Perfil com KPIs |
| `/obras` | GET | Admin | Lista de obras |
| `/obras/nova` | GET/POST | Admin | Nova obra |
| `/obras/<id>` | GET | Admin | Detalhes da obra |
| `/veiculos` | GET | Admin | Gestão de veículos |
| `/alimentacao` | GET | Admin | Controle de alimentação |
| `/rdo` | GET | Admin/Funcionário | Relatórios diários |
| `/relatorios` | GET | Admin | Relatórios gerenciais |
| `/financeiro` | GET | Admin | Dashboard financeiro |

---

## 3. FUNCIONALIDADES POR PÁGINA

### 3.1 Dashboard Principal (`/`)

**Objetivo:** Visão geral dos KPIs e métricas da empresa

**Funcionalidades:**
- Cartões de resumo (funcionários ativos, obras em andamento, veículos)
- Gráficos de evolução de custos
- Distribuição de funcionários por departamento
- Filtros por período (últimos 30 dias, mês atual, personalizado)
- Indicadores financeiros em tempo real

**Permissões:** Apenas Admin

**Fluxos de Trabalho:**
1. Carregamento automático dos dados do mês atual
2. Aplicação de filtros dinâmicos via JavaScript
3. Atualização de gráficos em tempo real
4. Drill-down para páginas específicas

### 3.2 Gestão de Funcionários (`/funcionarios`)

**Objetivo:** CRUD completo de funcionários e controle de RH

**Funcionalidades:**
- Lista paginada com DataTables
- Cadastro com foto (geração automática de SVG)
- Validação de CPF em tempo real
- Códigos automáticos (F0001, F0002, etc.)
- Status ativo/inativo
- Perfil detalhado com 15 KPIs

**Campos do Formulário:**
- Nome completo (obrigatório)
- CPF (validação algoritmo brasileiro)
- Email (formato válido)
- Telefone (máscara automática)
- Data de admissão
- Salário base
- Departamento (dropdown)
- Função (dropdown)
- Foto (upload ou SVG automático)

**KPIs do Perfil (Layout 4-4-4-3):**
1. **Linha 1:** Horas Trabalhadas, Horas Extras, Atrasos, Faltas
2. **Linha 2:** Faltas Justificadas, Produtividade, Absenteísmo, Média Diária
3. **Linha 3:** Horas Perdidas, Eficiência, Custo Mão de Obra, Custo Alimentação
4. **Linha 4:** Custo Transporte, Outros Custos, Custo Total

### 3.3 Gestão de Obras (`/obras`)

**Objetivo:** Controle de projetos e centros de custo

**Funcionalidades:**
- CRUD de obras/projetos
- Status (Em andamento, Concluída, Pausada, Cancelada)
- Gestão de serviços e subatividades
- Cálculo automático de percentual executado
- Controle de custos por categoria
- Geração de RDOs vinculados

**Campos:**
- Nome da obra
- Descrição
- Data de início/fim
- Orçamento total
- Cliente/contratante
- Localização
- Status atual
- Responsável técnico

### 3.4 Controle de Alimentação (`/alimentacao`)

**Objetivo:** Gestão de custos de alimentação por funcionário e obra

**Funcionalidades Principais:**
- Modal profissional com seleção múltipla de funcionários
- Busca em tempo real na lista de funcionários
- Avatares visuais dos funcionários
- Cálculo automático do valor total
- Checkbox "Selecionar Todos"
- Campos obrigatórios: Obra e Restaurante
- Validação frontend e backend

**Layout do Modal:**
1. **Card Informações Básicas:** Data, tipo de refeição, valor unitário
2. **Card Funcionários:** Lista com busca, filtros e seleção múltipla
3. **Card Obra e Restaurante:** Dropdowns obrigatórios com validação

**Validações:**
- Obra obrigatória (controle de custos e KPIs)
- Restaurante obrigatório (identificação do fornecedor)
- Pelo menos um funcionário selecionado
- Valor maior que zero

### 3.5 Relatório Diário de Obras - RDO (`/rdo`)

**Objetivo:** Registro diário de atividades e progresso das obras

**Funcionalidades:**
- Criação de RDOs por obra
- Dropdowns inteligentes com reutilização de dados
- Auto-população de serviços cadastrados na obra
- Cálculo automático de percentuais
- Campo "% Executado" readonly (calculado automaticamente)
- Histórico completo de RDOs

**Campos:**
- Obra (obrigatório)
- Data (padrão: hoje)
- Serviços executados
- Quantidades realizadas
- Funcionários envolvidos
- Equipamentos utilizados
- Observações técnicas

### 3.6 Gestão de Veículos (`/veiculos`)

**Objetivo:** Controle da frota e custos operacionais

**Funcionalidades:**
- Cadastro de veículos
- Registro de uso por funcionário
- Controle de combustível e manutenção
- Histórico de custos
- Status (Ativo, Manutenção, Inativo)

### 3.7 Módulo Financeiro (`/financeiro`)

**Objetivo:** Controle financeiro integrado

**Funcionalidades:**
- Dashboard com KPIs financeiros
- Controle de receitas e despesas
- Centros de custo
- Fluxo de caixa
- Relatórios financeiros

---

## 4. MÓDULOS E COMPONENTES

### 4.1 Módulos Principais

#### KPIs Engine v3.1 (`kpis_engine.py`)
- Cálculos precisos de produtividade
- 15 indicadores por funcionário
- Integração com horários de trabalho
- Separação de faltas justificadas/não justificadas

#### Sistema de Autenticação (`auth.py`)
- Multi-tenant com isolamento de dados
- 3 níveis hierárquicos de acesso
- Controle de sessões
- Redirecionamento baseado em papel

#### Engine de Relatórios (`relatorios_funcionais.py`)
- Exportação CSV, Excel, PDF
- 10 tipos de relatórios
- Filtros dinâmicos
- Formatação profissional

### 4.2 Bibliotecas e Dependências

```python
# Principais dependências
flask==3.0.0
flask-sqlalchemy==3.1.1
flask-login==0.6.3
flask-wtf==1.2.1
sqlalchemy==2.0.23
psycopg2-binary==2.9.9
gunicorn==21.2.0
openpyxl==3.1.2
reportlab==4.0.7
```

### 4.3 APIs Internas

| Endpoint | Método | Descrição |
|----------|--------|-----------|
| `/api/funcionarios` | GET | Lista funcionários ativos |
| `/api/obras` | GET | Lista obras em andamento |
| `/api/kpis/<funcionario_id>` | GET | KPIs de funcionário |
| `/api/custos/<obra_id>` | GET | Custos por obra |
| `/alimentacao/novo` | POST | Criar registros múltiplos |

---

## 5. CAMPOS E FORMULÁRIOS

### 5.1 Formulário de Funcionário

| Campo | Tipo | Validação | Obrigatório |
|-------|------|-----------|-------------|
| nome | Text | Max 100 chars | Sim |
| cpf | Text | Algoritmo brasileiro | Sim |
| email | Email | Formato válido | Não |
| telefone | Text | Máscara (99) 99999-9999 | Não |
| data_admissao | Date | Data válida | Sim |
| salario | Decimal | > 0 | Sim |
| departamento_id | Select | FK válida | Sim |
| funcao_id | Select | FK válida | Sim |
| foto | File | Imagem ou SVG auto | Não |

### 5.2 Formulário de Alimentação

| Campo | Tipo | Validação | Obrigatório |
|-------|------|-----------|-------------|
| data | Date | Data válida | Sim |
| tipo | Select | Lista predefinida | Sim |
| valor | Decimal | > 0 | Sim |
| obra_id | Select | FK válida | Sim |
| restaurante_id | Select | FK válida | Sim |
| funcionarios_ids | MultiSelect | Lista de FKs | Sim |
| observacoes | TextArea | Max 500 chars | Não |

### 5.3 Formulário de RDO

| Campo | Tipo | Validação | Obrigatório |
|-------|------|-----------|-------------|
| obra_id | Select | FK válida | Sim |
| data | Date | Data válida | Sim |
| servico_id | Select | FK válida | Sim |
| quantidade_executada | Decimal | > 0 | Sim |
| percentual_executado | Decimal | Readonly/Calculado | Não |
| funcionarios | MultiSelect | Lista de FKs | Não |
| observacoes | TextArea | Max 1000 chars | Não |

---

## 6. TABELAS E ESTRUTURAS DE DADOS

### 6.1 Principais Entidades

#### Funcionario
| Coluna | Tipo | Descrição |
|--------|------|-----------|
| id | Integer | Chave primária |
| codigo | String(10) | F0001, F0002, etc. |
| nome | String(100) | Nome completo |
| cpf | String(14) | CPF formatado |
| email | String(120) | Email válido |
| telefone | String(20) | Telefone formatado |
| data_admissao | Date | Data de admissão |
| salario | Decimal(10,2) | Salário base |
| departamento_id | Integer | FK para Departamento |
| funcao_id | Integer | FK para Funcao |
| ativo | Boolean | Status ativo/inativo |

#### Obra
| Coluna | Tipo | Descrição |
|--------|------|-----------|
| id | Integer | Chave primária |
| nome | String(100) | Nome da obra |
| descricao | Text | Descrição detalhada |
| data_inicio | Date | Data de início |
| data_fim | Date | Data prevista de fim |
| orcamento_total | Decimal(15,2) | Orçamento aprovado |
| status | String(20) | Em andamento, Concluída, etc. |

#### RegistroAlimentacao
| Coluna | Tipo | Descrição |
|--------|------|-----------|
| id | Integer | Chave primária |
| funcionario_id | Integer | FK para Funcionario |
| obra_id | Integer | FK para Obra |
| restaurante_id | Integer | FK para Restaurante |
| data | Date | Data da refeição |
| tipo | String(20) | Almoço, Lanche, Jantar |
| valor | Decimal(8,2) | Valor unitário |
| observacoes | Text | Observações adicionais |

#### RegistroPonto
| Coluna | Tipo | Descrição |
|--------|------|-----------|
| id | Integer | Chave primária |
| funcionario_id | Integer | FK para Funcionario |
| data | Date | Data do registro |
| hora_entrada | Time | Horário de entrada |
| hora_saida | Time | Horário de saída |
| hora_almoco_inicio | Time | Início do almoço |
| hora_almoco_fim | Time | Fim do almoço |
| horas_trabalhadas | Decimal(4,2) | Horas calculadas |
| horas_extras | Decimal(4,2) | Horas extras |
| tipo_registro | String(30) | Tipo do lançamento |
| total_atraso_minutos | Integer | Atrasos em minutos |

### 6.2 Relacionamentos Principais

```
Usuario (1) ←→ (N) Funcionario
Funcionario (N) ←→ (1) Departamento
Funcionario (N) ←→ (1) Funcao
Funcionario (1) ←→ (N) RegistroPonto
Funcionario (1) ←→ (N) RegistroAlimentacao
Obra (1) ←→ (N) RegistroAlimentacao
Obra (1) ←→ (N) CustoObra
Obra (1) ←→ (N) ServicoObra
Restaurante (1) ←→ (N) RegistroAlimentacao
```

---

## 7. CÁLCULOS E KPIs

### 7.1 KPIs do Engine v3.1

#### Fórmulas Principais

**Produtividade:**
```
Produtividade = (Horas Trabalhadas ÷ Horas Esperadas) × 100
Horas Esperadas = Dias com Lançamento × Horas Diárias do Horário
```

**Absenteísmo:**
```
Absenteísmo = (Faltas Não Justificadas ÷ Dias com Lançamento) × 100
```

**Horas Perdidas:**
```
Horas Perdidas = (Faltas × 8) + (Atrasos em Horas)
```

**Eficiência:**
```
Eficiência = Produtividade × (1 - Taxa de Faltas)
```

**Custo Total:**
```
Custo Total = Custo Mão de Obra + Custo Alimentação + Custo Transporte + Outros Custos
```

### 7.2 Lógica de Dias com Lançamento

**Tipos Considerados:**
- trabalho_normal
- feriado_trabalhado
- meio_periodo
- falta
- falta_justificada

**Tipos Excluídos dos KPIs:**
- sabado_horas_extras
- domingo_horas_extras
- sabado_nao_trabalhado
- domingo_nao_trabalhado

### 7.3 Cálculo de Horas Extras

**Dias Normais:**
```python
if horas_trabalhadas > horario.horas_diarias:
    horas_extras = horas_trabalhadas - horario.horas_diarias
```

**Tipos Especiais:**
- Sábado: 50% sobre valor/hora
- Domingo: 100% sobre valor/hora
- Feriado: 100% sobre valor/hora

---

## 8. ELEMENTOS VISUAIS E INTERFACE

### 8.1 Sistema de Temas

**Dark Mode (Padrão):**
- Fundo: #1a1a1a
- Texto: #ffffff
- Cards: #2d2d2d
- Campos: #000000

**Light Mode:**
- Fundo: #ffffff
- Texto: #333333
- Cards: #f8f9fa
- Campos: #ffffff

### 8.2 Componentes Visuais

**Cartões KPI:**
```html
<div class="col-md-3 mb-3">
    <div class="card bg-primary text-white">
        <div class="card-body">
            <h5>159.2h</h5>
            <p>Horas Trabalhadas</p>
        </div>
    </div>
</div>
```

**Badges de Status:**
- Ativo: `<span class="badge bg-success">Ativo</span>`
- Inativo: `<span class="badge bg-danger">Inativo</span>`
- Falta: `<span class="badge bg-danger">FALTA</span>`
- Feriado: `<span class="badge bg-secondary">FERIADO</span>`

**Avatares de Funcionários:**
```html
<div class="employee-avatar">
    <img src="/static/fotos/F0001.svg" alt="João" class="rounded-circle" width="32" height="32">
    <span>João Silva</span>
</div>
```

### 8.3 Gráficos Chart.js

**Configuração Padrão:**
```javascript
{
    responsive: true,
    plugins: {
        legend: {
            display: true,
            labels: {
                color: '#ffffff'
            }
        }
    },
    scales: {
        y: {
            ticks: {
                color: '#ffffff'
            }
        },
        x: {
            ticks: {
                color: '#ffffff'
            }
        }
    }
}
```

---

## 9. AUTENTICAÇÃO E AUTORIZAÇÃO

### 9.1 Sistema Multi-Tenant

**Hierarquia de Acesso:**
1. **Super Admin:** Gerencia apenas administradores
2. **Admin:** Acesso completo ao sistema operacional
3. **Funcionário:** Acesso restrito (RDO + veículos)

### 9.2 Controle de Sessões

**Flask-Login Configuration:**
```python
login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'auth.login'
```

**Decorators de Segurança:**
```python
@super_admin_required
@admin_required
@funcionario_required
```

### 9.3 Isolamento de Dados

**Por Tenant:**
- Funcionários veem apenas dados do seu admin
- Super Admin isolado dos dados operacionais
- Filtros automáticos por tenant_id

---

## 10. INTEGRAÇÕES E APIs EXTERNAS

### 10.1 APIs Internas

**Endpoints Principais:**
- `/api/funcionarios` - Lista funcionários
- `/api/obras` - Lista obras
- `/api/kpis/<id>` - KPIs de funcionário
- `/alimentacao/novo` - Criar registros múltiplos

### 10.2 Formatos de Dados

**JSON Response Padrão:**
```json
{
    "success": true,
    "message": "Operação realizada com sucesso",
    "data": {
        "total_registros": 5,
        "valor_total": 125.50
    }
}
```

**Error Response:**
```json
{
    "success": false,
    "message": "Obra é obrigatória para controle de custos e KPIs",
    "error_code": 400
}
```

---

## 11. CONFIGURAÇÕES E PARÂMETROS

### 11.1 Variáveis de Ambiente

```bash
DATABASE_URL=postgresql://user:pass@host:port/dbname
SESSION_SECRET=sua_chave_secreta_aqui
FLASK_ENV=production
PGDATABASE=nome_do_banco
PGHOST=localhost
PGPORT=5432
PGUSER=usuario
PGPASSWORD=senha
```

### 11.2 Configurações Flask

```python
app.config["SQLALCHEMY_DATABASE_URI"] = os.environ.get("DATABASE_URL")
app.config["SQLALCHEMY_ENGINE_OPTIONS"] = {
    "pool_recycle": 300,
    "pool_pre_ping": True,
}
app.secret_key = os.environ.get("SESSION_SECRET")
```

---

## 12. FLUXOS DE DADOS

### 12.1 Fluxo de Controle de Alimentação

1. **Frontend:** Usuário seleciona múltiplos funcionários
2. **JavaScript:** Valida campos obrigatórios
3. **Backend:** Processa lista de funcionários
4. **Loop:** Cria registro para cada funcionário
5. **Custos:** Adiciona custo à obra correspondente
6. **Response:** Retorna total de registros e valor

### 12.2 Fluxo de Cálculo de KPIs

1. **Trigger:** Novo registro de ponto
2. **Engine:** Busca configuração do horário
3. **Cálculo:** Aplica fórmulas de produtividade
4. **Agregação:** Soma valores do período
5. **Persistência:** Atualiza campos calculados
6. **Frontend:** Exibe KPIs atualizados

### 12.3 Fluxo de RDO

1. **Seleção:** Usuário escolhe obra
2. **Auto-população:** Sistema carrega serviços da obra
3. **Entrada:** Usuário informa quantidade executada
4. **Cálculo:** Sistema calcula percentual automaticamente
5. **Validação:** Verifica consistência dos dados
6. **Persistência:** Salva RDO e atualiza progresso da obra

---

## 13. PERFORMANCE E OTIMIZAÇÕES

### 13.1 Otimizações Implementadas

**Database:**
- Índices em chaves estrangeiras
- Connection pooling configurado
- Queries com joinedload() para evitar N+1

**Frontend:**
- DataTables com paginação server-side
- Lazy loading de componentes
- Minificação de assets estáticos

**Cache:**
- Session storage para preferências
- LocalStorage para tema dark/light

### 13.2 Limitações Conhecidas

- Máximo 1000 funcionários por tenant
- Relatórios limitados a 50.000 registros
- Upload de fotos limitado a 5MB
- Sessão expira em 24 horas

---

## 14. ESTRUTURA DE ARQUIVOS

```
/
├── app.py                    # Configuração principal Flask
├── main.py                   # Entry point da aplicação
├── models.py                 # Modelos SQLAlchemy
├── views.py                  # Rotas e controllers
├── forms.py                  # Formulários WTF
├── auth.py                   # Sistema de autenticação
├── kpis_engine.py           # Engine de cálculo de KPIs
├── utils.py                 # Funções utilitárias
├── relatorios_funcionais.py # Sistema de relatórios
├── static/
│   ├── css/                 # Estilos customizados
│   ├── js/                  # JavaScript customizado
│   └── fotos/               # Fotos dos funcionários
├── templates/
│   ├── base.html            # Template base
│   ├── dashboard.html       # Dashboard principal
│   ├── funcionarios.html    # Lista de funcionários
│   ├── alimentacao.html     # Controle de alimentação
│   └── ...                  # Outros templates
└── replit.md               # Documentação do projeto
```

---

## 15. CASOS DE USO PRINCIPAIS

### 15.1 Lançamento de Alimentação em Massa

**Cenário:** Necessidade de lançar alimentação para 15 funcionários simultaneamente

**Fluxo:**
1. Admin acessa `/alimentacao`
2. Clica em "Controle de Alimentação"
3. Preenche data, tipo e valor
4. Seleciona obra e restaurante (obrigatórios)
5. Busca e seleciona funcionários
6. Sistema calcula valor total automaticamente
7. Confirma e registra 15 entradas individuais
8. Custos são automaticamente adicionados à obra

### 15.2 Análise de Produtividade de Funcionário

**Cenário:** Verificar performance de funcionário específico

**Fluxo:**
1. Admin acessa `/funcionarios`
2. Clica no funcionário desejado
3. Sistema exibe 15 KPIs em layout 4-4-4-3
4. Analisa produtividade, absenteísmo, custos
5. Pode filtrar por período específico
6. Exporta relatório se necessário

### 15.3 Criação de RDO com Auto-População

**Cenário:** Registro diário de progresso da obra

**Fluxo:**
1. Funcionário/Admin acessa `/rdo`
2. Seleciona obra do dropdown
3. Sistema auto-popula serviços cadastrados
4. Informa quantidade executada
5. Sistema calcula percentual automaticamente
6. Adiciona observações e salva
7. Progresso da obra é atualizado

---

## 16. CONCLUSÃO

O SIGE v6.5 representa um sistema maduro e completo para gestão empresarial no setor de construção civil. Com arquitetura multi-tenant, interface responsiva e cálculos precisos de KPIs, oferece todas as ferramentas necessárias para:

- **Gestão de RH:** Controle completo de funcionários com KPIs detalhados
- **Controle de Custos:** Rastreabilidade por obra e categoria
- **Gestão de Projetos:** RDOs inteligentes com auto-população
- **Análise Gerencial:** Dashboard e relatórios em múltiplos formatos
- **Controle Operacional:** Gestão de frota e alimentação

O sistema está preparado para produção com todas as validações, otimizações e funcionalidades essenciais implementadas.

---

*Documentação gerada em: July 22, 2025*
*Versão do Sistema: SIGE v6.5*
*Autor: Sistema SIGE - Estruturas do Vale*