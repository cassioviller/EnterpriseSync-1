<div align="center">

# 📘 Manual de Uso do Sistema EnterpriseSync

### Guia completo para usuarios e administradores

---

[LOGO DA EMPRESA]

---

**Sistema:** SIGE v9.0 — EnterpriseSync
**Versao:** 1.0
**Data:** Fevereiro de 2026
**Empresa:** Estruturas do Vale
**Classificacao:** Documento Interno — Uso Restrito

---

</div>

---

# Indice Geral

- [Capitulo 1 — Configuracao Inicial e Instalacao](#capitulo-1--configuração-inicial-e-instalação)
  - [1.1. Introducao](#11-introdução)
  - [1.2. Requisitos do Sistema](#12-requisitos-do-sistema)
  - [1.3. Instalacao do Sistema](#13-instalação-do-sistema)
  - [1.4. Primeiro Acesso e Configuracao da Empresa](#14-primeiro-acesso-e-configuração-da-empresa)
  - [1.5. Configuracoes Globais](#15-configurações-globais)
  - [1.6. Gestao de Usuarios](#16-gestão-de-usuários)
  - [1.7. Checklist de Configuracao Inicial](#17-checklist-de-configuração-inicial)
- [Capitulo 2 — Modulo Dashboard](#capitulo-2--módulo-dashboard)
  - [2.1. Introducao ao Dashboard](#21-introdução-ao-dashboard)
  - [2.2. Acessando o Dashboard](#22-acessando-o-dashboard)
  - [2.3. KPIs Principais](#23-kpis-principais)
  - [2.4. Graficos e Visualizacoes](#24-gráficos-e-visualizações)
  - [2.5. Dashboard Executivo por Obra](#25-dashboard-executivo-por-obra)
  - [2.6. Dashboard do Funcionario](#26-dashboard-do-funcionário)
  - [2.7. Alertas e Notificacoes](#27-alertas-e-notificações)
  - [2.8. Personalizacao do Dashboard](#28-personalização-do-dashboard)
- [Capitulo 3 — Gestao de Funcionarios](#capitulo-3--gestão-de-funcionários)
  - [3.1. Introducao a Gestao de Funcionarios](#31-introdução-à-gestão-de-funcionários)
  - [3.2. Tela Principal de Funcionarios](#32-tela-principal-de-funcionários)
  - [3.3. Cadastrando um Novo Funcionario](#33-cadastrando-um-novo-funcionário)
  - [3.4. Perfil do Funcionario](#34-perfil-do-funcionário)
  - [3.5. Reconhecimento Facial](#35-reconhecimento-facial)
  - [3.6. Controle de Ponto Eletronico](#36-controle-de-ponto-eletrônico)
  - [3.7. Relatorios de Funcionarios](#37-relatórios-de-funcionários)
- [Capitulo 4 — Gestao de Obras](#capitulo-4--gestão-de-obras)
  - [4.1. Introducao a Gestao de Obras](#41-introdução-à-gestão-de-obras)
  - [4.2. Tela Principal de Obras](#42-tela-principal-de-obras)
  - [4.3. Cadastrando uma Nova Obra](#43-cadastrando-uma-nova-obra)
  - [4.4. Planejamento da Obra](#44-planejamento-da-obra)
  - [4.5. Acompanhamento da Obra](#45-acompanhamento-da-obra)
  - [4.6. Controle Financeiro da Obra](#46-controle-financeiro-da-obra)
  - [4.7. Relatorios de Obras](#47-relatórios-de-obras)
- [Capitulo 5 — Gestao de Frota e Veiculos](#capitulo-5--gestão-de-frota-e-veículos)
  - [5.1. Introducao a Gestao de Frota](#51-introdução-à-gestão-de-frota)
  - [5.2. Tela Principal de Veiculos](#52-tela-principal-de-veículos)
  - [5.3. Cadastrando um Novo Veiculo](#53-cadastrando-um-novo-veículo)
  - [5.4. Registrando o Uso de Veiculos](#54-registrando-o-uso-de-veículos)
  - [5.5. Controle de Custos de Veiculos](#55-controle-de-custos-de-veículos)
  - [5.6. Detalhes do Veiculo](#56-detalhes-do-veículo)
  - [5.7. Relatorios de Frota](#57-relatórios-de-frota)
- [Capitulo 6 — Relatorio Diario de Obra (RDO)](#capitulo-6--relatorio-diario-de-obra-rdo)
  - [6.1. Introducao ao RDO](#61-introducao-ao-rdo)
  - [6.2. Tela Principal de RDOs](#62-tela-principal-de-rdos)
  - [6.3. Criando um Novo RDO](#63-criando-um-novo-rdo)
  - [6.4. Registrando Atividades no RDO](#64-registrando-atividades-no-rdo)
  - [6.5. Finalizando e Enviando para Aprovacao](#65-finalizando-e-enviando-para-aprovacao)
  - [6.6. Aprovacao de RDOs](#66-aprovacao-de-rdos)
  - [6.7. Impacto do RDO no Sistema](#67-impacto-do-rdo-no-sistema)
  - [6.8. Relatorios de RDO](#68-relatorios-de-rdo)
- [Capitulo 7 — Modulo Financeiro](#capitulo-7--modulo-financeiro)
  - [7.1. Introducao ao Modulo Financeiro](#71-introducao-ao-modulo-financeiro)
  - [7.2. Dashboard Financeiro](#72-dashboard-financeiro)
  - [7.3. Plano de Contas e Centros de Custo](#73-plano-de-contas-e-centros-de-custo)
  - [7.4. Contas a Pagar](#74-contas-a-pagar)
  - [7.5. Contas a Receber](#75-contas-a-receber)
  - [7.6. Fluxo de Caixa](#76-fluxo-de-caixa)
  - [7.7. Relatorios Financeiros](#77-relatorios-financeiros)
- [Capitulo 8 — Modulos Avancados](#capitulo-8--módulos-avançados)
  - [8.1. Modulo de Propostas Comerciais](#81-módulo-de-propostas-comerciais)
  - [8.2. Modulo de Alimentacao](#82-módulo-de-alimentação)
  - [8.3. Modulo de Almoxarifado](#83-módulo-de-almoxarifado)
  - [8.4. Modulo de API](#84-módulo-de-api)
  - [8.5. Modulo de Relatorios](#85-módulo-de-relatórios)
  - [8.6. Modulo de Administracao](#86-módulo-de-administração)
- [Capitulo 9 — Suporte e Consideracoes Finais](#capitulo-9--suporte-e-considerações-finais)
  - [9.1. Troubleshooting](#91-troubleshooting)
  - [9.2. Boas Praticas](#92-boas-práticas)
  - [9.3. Contato do Suporte](#93-contato-do-suporte)
  - [9.4. Glossario](#94-glossário)

---

# Capitulo 1 — Configuração Inicial e Instalação

**SIGE - Estruturas do Vale (EnterpriseSync)**
Manual do Usuário — Versão 8.0

---

## 1.1. Introdução

Bem-vindo ao **SIGE (Sistema Integrado de Gestão Empresarial)**, comercializado sob a marca **EnterpriseSync** e operado pela **Estruturas do Vale**. O SIGE é uma plataforma completa desenvolvida especificamente para empresas do setor de construção civil e engenharia, reunindo **97 modelos de dados** e **18 módulos integrados** em uma única solução web multi-tenant.

**Objetivos do EnterpriseSync:**

1. **Centralizar informações** — Reunir todos os dados operacionais, administrativos e financeiros em um único ambiente acessível de qualquer dispositivo.
2. **Automatizar processos** — Reduzir trabalho manual por meio de cálculos automáticos de horas trabalhadas, horas extras, custos e produtividade.
3. **Garantir rastreabilidade** — Manter histórico completo e auditável de todas as operações realizadas no sistema.
4. **Isolamento multi-tenant** — Permitir que múltiplas empresas operem de forma isolada na mesma instalação, com segregação total de dados via coluna `admin_id`.
5. **Apoiar a tomada de decisão** — Fornecer dashboards, KPIs e relatórios gerenciais em tempo real.

### Módulos Disponíveis

O menu de navegação do SIGE exibe os seguintes módulos na barra superior:

| Nº | Módulo | Tipo de Menu | Descrição |
|:--:|:-------|:------------|:----------|
| 1 | Dashboard | Link direto | Painel gerencial com KPIs e indicadores |
| 2 | RDOs | Link direto | Relatórios Diários de Obra |
| 3 | Obras | Link direto | Gestão completa de obras e projetos |
| 4 | Funcionários | Link direto | Cadastro e gestão de colaboradores |
| 5 | Equipe | Link direto | Alocação e gestão de equipes de campo |
| 6 | Ponto | Dropdown ▼ | Controle de ponto eletrônico com reconhecimento facial |
| 7 | Propostas | Dropdown ▼ | Propostas comerciais e orçamentos |
| 8 | Financeiro | Dropdown ▼ | Contas a pagar, receber e fluxo de caixa |
| 9 | Veículos | Link direto | Gestão de frota e controle de veículos |
| 10 | Alimentação | Link direto | Controle de refeições e vales alimentação |
| 11 | Almoxarifado | Dropdown ▼ | Estoque, requisições e movimentações de materiais |
| 12 | Relatórios | Link direto | Relatórios consolidados e exportações |

> **URL de acesso em produção:** [https://sige.cassioviller.tech](https://sige.cassioviller.tech)

### O que será coberto neste capítulo

Neste capítulo, você aprenderá a:

1. Verificar os requisitos de hardware e software necessários para o funcionamento do sistema
2. Instalar e configurar o SIGE em ambiente de produção via Docker e EasyPanel
3. Realizar o primeiro acesso e configurar os dados da empresa
4. Cadastrar departamentos, funções e horários de trabalho
5. Gerenciar usuários e suas permissões de acesso

---

## 1.2. Requisitos do Sistema

### 1.2.1. Requisitos de Hardware (Servidor)

| Componente | Requisito Mínimo | Requisito Recomendado |
|:-----------|:-----------------|:---------------------|
| Processador | 2 vCPUs | 4 vCPUs |
| Memória RAM | 2 GB | 4 GB ou superior |
| Armazenamento | 20 GB SSD | 50 GB SSD ou superior |
| Rede | 10 Mbps | 100 Mbps |

### 1.2.2. Requisitos de Software (Servidor)

| Software | Versão Mínima | Observação |
|:---------|:-------------|:-----------|
| Sistema Operacional | Ubuntu 20.04 LTS ou similar | Qualquer distribuição Linux com suporte a Docker |
| Docker | 20.10+ | Motor de contêineres para deploy da aplicação |
| Docker Compose | 2.0+ | Orquestração de serviços (app + banco de dados) |
| PostgreSQL | 14+ | Banco de dados relacional (Neon-backed em produção) |
| Python | 3.11+ | Runtime da aplicação (incluso no contêiner Docker) |

### 1.2.3. Requisitos do Navegador (Cliente)

| Navegador | Versão Mínima |
|:----------|:-------------|
| Google Chrome | 90+ |
| Mozilla Firefox | 88+ |
| Microsoft Edge | 90+ |
| Safari | 14+ |

> **Nota:** O sistema é totalmente responsivo e pode ser acessado via dispositivos móveis (smartphones e tablets). Para funcionalidades de reconhecimento facial e geolocalização no módulo de Ponto, é necessário que o navegador tenha acesso à câmera e ao GPS do dispositivo.

### 1.2.4. Requisitos de Rede

- Conexão com a internet estável (mínimo 10 Mbps)
- Porta 443 (HTTPS) liberada para acesso externo
- Certificado SSL válido (obrigatório para ambiente de produção)

---

## 1.3. Instalação do Sistema

O SIGE é distribuído como uma aplicação containerizada via **Docker**, com suporte nativo ao **EasyPanel** para gerenciamento simplificado do deploy.

### 1.3.1. Pré-requisitos de Instalação

Certifique-se de que o Docker e o Docker Compose estão instalados no servidor:

```bash
# Verificar instalação do Docker
docker --version

# Verificar instalação do Docker Compose
docker compose version
```

### 1.3.2. Clonando o Repositório

```bash
# Clonar o repositório do projeto
git clone https://github.com/sua-organizacao/enterprisesync.git

# Acessar o diretório do projeto
cd enterprisesync
```

### 1.3.3. Configuração das Variáveis de Ambiente

Crie o arquivo `.env` na raiz do projeto com as seguintes variáveis obrigatórias:

```env
# === Banco de Dados ===
DATABASE_URL=postgresql://usuario:senha@host:5432/nome_do_banco
PGHOST=host_do_banco
PGPORT=5432
PGUSER=usuario_do_banco
PGPASSWORD=senha_do_banco
PGDATABASE=nome_do_banco

# === Segurança ===
SESSION_SECRET=sua_chave_secreta_aqui
```

**Detalhamento das variáveis:**

| Variável | Descrição | Exemplo |
|:---------|:----------|:--------|
| `DATABASE_URL` | URL de conexão completa com o PostgreSQL | `postgresql://sige:s3nh4@db:5432/sige_db` |
| `SESSION_SECRET` | Chave secreta para criptografia de sessões Flask | Gere com: `python -c "import secrets; print(secrets.token_hex(32))"` |
| `PGHOST` | Endereço do servidor PostgreSQL | `db` ou `localhost` |
| `PGPORT` | Porta do PostgreSQL | `5432` |
| `PGUSER` | Usuário do banco de dados | `sige` |
| `PGPASSWORD` | Senha do banco de dados | `s3nh4_segura_123` |
| `PGDATABASE` | Nome do banco de dados | `sige_db` |

> **Segurança:** Nunca compartilhe ou exponha o arquivo `.env` em repositórios públicos. Adicione-o ao `.gitignore`. Utilize senhas fortes com no mínimo 16 caracteres, combinando letras, números e caracteres especiais.

### 1.3.4. Instalação via Docker Compose

```bash
# Construir e iniciar os containers
docker compose up -d --build

# Verificar se os containers estão rodando
docker compose ps
```

### 1.3.5. Instalação via EasyPanel

Para instalação via **EasyPanel**, siga os passos abaixo:

1. Acesse o painel de controle do EasyPanel no endereço do seu servidor.
2. Clique em **"Create Service"** → **"App"**.
3. Selecione a opção **"Docker Image"** ou **"GitHub Repository"** e vincule ao repositório do SIGE.
4. Configure todas as variáveis de ambiente listadas na seção 1.3.3.
5. Defina a porta de exposição como **5000**.
6. Configure o domínio personalizado (ex: `sige.cassioviller.tech`).
7. Ative o certificado SSL automático (Let's Encrypt).
8. Clique em **"Deploy"**.

[IMAGEM: Tela de configuração do EasyPanel com variáveis de ambiente]

### 1.3.6. Migrações do Banco de Dados

O sistema executa automaticamente `db.create_all()` na inicialização, criando todas as **97 tabelas** que ainda não existem no banco de dados. Não é necessário executar migrações manuais na maioria dos casos.

Caso necessário, as migrações podem ser executadas manualmente:

```bash
# Acessar o container da aplicação
docker exec -it enterprisesync-app bash

# Executar as migrações
flask db upgrade
```

### 1.3.7. Iniciando o Servidor

O servidor é iniciado automaticamente pelo Gunicorn com o seguinte comando:

```bash
gunicorn --bind 0.0.0.0:5000 --reuse-port --reload main:app
```

Após a inicialização bem-sucedida, o sistema estará acessível em:

- **Produção:** `https://sige.cassioviller.tech`
- **Desenvolvimento local:** `http://localhost:5000`

### 1.3.8. Verificando a Instalação

Acesse a URL do sistema no navegador. Se a **tela de login** for exibida corretamente com os campos **Username** e **Senha** e o botão **"Entrar"**, a instalação foi concluída com sucesso.

[IMAGEM: Tela de login do SIGE com campos Username e Senha]

---

## 1.4. Primeiro Acesso e Configuração da Empresa

### 1.4.1. Criando o Primeiro Usuário Super Admin

O primeiro usuário do sistema deve ser do tipo **SUPER_ADMIN**, que possui acesso irrestrito a todas as funcionalidades e configurações. Este usuário é criado via linha de comando durante a implantação inicial:

```bash
# Acessar o shell Python dentro do container
docker exec -it enterprisesync-app flask shell
```

```python
from models import db, Usuario, TipoUsuario
from werkzeug.security import generate_password_hash

admin = Usuario(
    nome="Administrador Principal",
    username="admin",
    email="admin@suaempresa.com.br",
    password_hash=generate_password_hash("SenhaSegura123!"),
    tipo_usuario=TipoUsuario.SUPER_ADMIN,
    ativo=True
)

db.session.add(admin)
db.session.commit()
print(f"Super Admin criado com ID: {admin.id}")
```

> **Importante:** Após o primeiro acesso, altere a senha padrão imediatamente por motivos de segurança.

### 1.4.2. Realizando o Primeiro Login

1. Acesse o sistema pela URL configurada: `https://sige.cassioviller.tech`
2. Na tela de login, preencha os campos:
   - **Username:** Informe o nome de usuário **ou** o e-mail cadastrado
   - **Senha:** Informe a senha definida na criação do SUPER_ADMIN
3. Clique no botão **"Entrar"**

[IMAGEM: Tela de login preenchida com credenciais de acesso]

> **Informações sobre o login:**
> - O campo Username aceita tanto o **nome de usuário** quanto o **e-mail** cadastrado.
> - Em caso de credenciais inválidas, será exibida a mensagem: *"Email/Username ou senha inválidos."*
> - O sistema possui **rate limiting de 30 tentativas por minuto** no endpoint de login para proteção contra ataques de força bruta.

### 1.4.3. Redirecionamento Após Login

Após o login bem-sucedido, o sistema redireciona automaticamente o usuário conforme seu tipo:

| Tipo de Usuário | Página de Destino | URL |
|:----------------|:------------------|:----|
| SUPER_ADMIN | Dashboard Super Admin | `/super_admin_dashboard` |
| ADMIN | Dashboard Administrativo | `/dashboard` |
| GESTOR_EQUIPES | RDO Consolidado | `/funcionario/rdo/consolidado` |
| ALMOXARIFE | RDO Consolidado | `/funcionario/rdo/consolidado` |
| FUNCIONARIO | RDO Consolidado | `/funcionario/rdo/consolidado` |

[IMAGEM: Dashboard do Super Admin após primeiro login]

### 1.4.4. Configurando os Dados da Empresa

Após o primeiro login como Super Admin, configure os dados da sua empresa:

1. Acesse o **Painel Administrativo** (Dashboard do Super Admin).
2. Navegue até **Configurações** → **Dados da Empresa**.
3. Preencha os seguintes campos:

| Campo | Descrição | Obrigatório |
|:------|:----------|:-----------:|
| Nome da Empresa | Razão social ou nome fantasia | Sim |
| CNPJ | Cadastro Nacional de Pessoa Jurídica | Sim |
| Endereço | Endereço completo da sede | Sim |
| Telefone | Telefone principal de contato | Não |
| E-mail | E-mail corporativo | Não |

4. Clique em **"Salvar"**.

[IMAGEM: Formulário de configuração dos dados da empresa]

### 1.4.5. Configurando o Logo da Empresa

1. Na tela de configurações da empresa, localize a seção **"Logo"**.
2. Clique em **"Escolher Arquivo"**.
3. Selecione uma imagem nos formatos **PNG**, **JPG** ou **SVG** (tamanho recomendado: 200×200 pixels).
4. Clique em **"Salvar"**.

O logo será exibido no cabeçalho do sistema e nos relatórios gerados.

[IMAGEM: Upload do logo da empresa]

> **Multi-tenant:** O SIGE opera com isolamento de dados por empresa. Cada ADMIN gerencia seus próprios funcionários, obras, registros e configurações, sem acesso aos dados de outras empresas. Este isolamento é garantido pelo campo `admin_id` presente em todas as tabelas do sistema.

---

## 1.5. Configurações Globais

As configurações globais definem a estrutura organizacional da empresa dentro do sistema. É **fundamental** configurá-las antes de iniciar o cadastro de funcionários e a operação dos demais módulos.

### 1.5.1. Departamentos

Os **departamentos** representam as divisões organizacionais da empresa. Cada funcionário deve estar vinculado a um departamento para fins de organização e geração de relatórios setoriais.

**Campos do cadastro de Departamento:**

| Campo | Tipo | Obrigatório | Descrição |
|:------|:-----|:-----------:|:----------|
| Nome | Texto (até 100 caracteres) | Sim | Nome do departamento |
| Descrição | Texto livre | Não | Detalhamento das atividades do departamento |

#### Criando um Departamento

1. Acesse **Configurações** → **Departamentos**.
2. Clique no botão **"Novo Departamento"**.
3. Preencha o **Nome** (ex: "Engenharia", "Produção", "Administrativo").
4. Opcionalmente, adicione uma **Descrição** detalhada.
5. Clique em **"Salvar"**.

[IMAGEM: Formulário de cadastro de departamento]

#### Exemplos de Departamentos

| Departamento | Descrição |
|:-------------|:----------|
| Engenharia | Equipe de engenheiros e projetistas |
| Produção | Equipe de operários e mestres de obra |
| Administrativo | Equipe de escritório e gestão |
| Almoxarifado | Equipe de controle de materiais e estoque |
| Segurança do Trabalho | Equipe de segurança e prevenção de acidentes |

#### Editando e Excluindo Departamentos

- Para **editar**, clique no ícone de edição ao lado do departamento desejado.
- Para **excluir**, clique no ícone de exclusão (somente departamentos sem funcionários vinculados podem ser excluídos).

> **Atenção:** A exclusão de um departamento é irreversível. Certifique-se de que não há funcionários vinculados antes de excluir.

### 1.5.2. Funções (Cargos)

As **funções** definem os cargos e posições dos funcionários dentro da empresa. Cada função pode ter um salário base associado, que serve como referência para o cadastro individual dos colaboradores.

**Campos do cadastro de Função:**

| Campo | Tipo | Obrigatório | Descrição |
|:------|:-----|:-----------:|:----------|
| Nome | Texto (até 100 caracteres) | Sim | Nome da função/cargo |
| Descrição | Texto livre | Não | Detalhamento das atribuições do cargo |
| Salário Base | Numérico (R$) | Não | Valor base mensal de remuneração |

#### Criando uma Função

1. Acesse **Configurações** → **Funções**.
2. Clique no botão **"Nova Função"**.
3. Preencha o **Nome** (ex: "Pedreiro", "Engenheiro Civil", "Auxiliar Administrativo").
4. Adicione a **Descrição** das atribuições do cargo (opcional).
5. Informe o **Salário Base** em reais (opcional).
6. Clique em **"Salvar"**.

[IMAGEM: Formulário de cadastro de função]

#### Exemplos de Funções

| Função | Descrição | Salário Base (R$) |
|:-------|:----------|------------------:|
| Engenheiro Civil | Responsável técnico por projetos e obras | 12.000,00 |
| Mestre de Obras | Coordenação de equipes em campo | 6.500,00 |
| Pedreiro | Execução de alvenaria e acabamentos | 3.200,00 |
| Eletricista | Instalações elétricas e manutenção | 3.800,00 |
| Encarregado de Obra | Supervisão direta de equipes operacionais | 5.000,00 |
| Operador de Máquinas | Operação de equipamentos pesados | 4.200,00 |
| Auxiliar de Almoxarifado | Apoio no controle de materiais e estoque | 2.500,00 |
| Ajudante Geral | Apoio geral às atividades de obra | 2.100,00 |

> **Dica:** O salário base definido na função serve como referência. O salário individual de cada funcionário pode ser ajustado diretamente no cadastro do funcionário.

### 1.5.3. Horários de Trabalho

Os **horários de trabalho** definem os padrões de jornada que serão associados aos funcionários para controle de ponto e cálculo automático de horas trabalhadas, horas extras e atrasos.

O SIGE permite configurar horários diferentes para **cada dia da semana**, incluindo intervalos de pausa e identificação de dias não trabalhados.

**Campos do cadastro de Horário de Trabalho:**

| Campo | Tipo | Obrigatório | Descrição |
|:------|:-----|:-----------:|:----------|
| Nome | Texto (até 100 caracteres) | Sim | Nome identificador do horário (deve ser único) |
| Ativo | Booleano | Sim | Se o horário está ativo para uso |
| Horas Diárias | Numérico | Não | Carga horária padrão por dia (ex: 8.0) |
| Valor Hora | Numérico (R$) | Não | Valor da hora de trabalho |

**Configuração por dia da semana (HorarioDia):**

Para cada dia (Segunda a Domingo), é possível configurar individualmente:

| Campo | Tipo | Descrição |
|:------|:-----|:----------|
| Dia da Semana | Inteiro (0-6) | 0=Segunda, 1=Terça, 2=Quarta, 3=Quinta, 4=Sexta, 5=Sábado, 6=Domingo |
| Entrada | Hora (HH:MM) | Horário de entrada (ex: 07:00) |
| Saída | Hora (HH:MM) | Horário de saída (ex: 17:00) |
| Pausa (horas) | Numérico | Duração do intervalo de almoço em horas (ex: 1.0) |
| Trabalha | Booleano | Define se é dia útil de trabalho |

#### Criando um Horário de Trabalho

1. Acesse **Configurações** → **Horários de Trabalho**.
2. Clique no botão **"Novo Horário"**.
3. Informe o **Nome** do horário (ex: "Comercial Padrão", "Obra - Campo").
4. Configure os horários para **cada dia da semana**:
   - Marque os dias em que há trabalho (normalmente segunda a sexta).
   - Defina entrada, saída e tempo de pausa para cada dia.
   - Para sábados com meia jornada, configure entrada e saída diferenciadas.
5. Clique em **"Salvar"**.

[IMAGEM: Formulário de configuração de horário de trabalho com dias da semana]

#### Exemplo: Horário Comercial Padrão (44h semanais)

| Dia | Trabalha | Entrada | Saída | Pausa (h) | Horas Líquidas |
|:----|:--------:|:-------:|:-----:|:---------:|:--------------:|
| Segunda-feira | Sim | 07:30 | 17:30 | 1,0 | 9,0 |
| Terça-feira | Sim | 07:30 | 17:30 | 1,0 | 9,0 |
| Quarta-feira | Sim | 07:30 | 17:30 | 1,0 | 9,0 |
| Quinta-feira | Sim | 07:30 | 17:30 | 1,0 | 9,0 |
| Sexta-feira | Sim | 07:30 | 17:30 | 1,0 | 9,0 |
| Sábado | Sim | 07:30 | 11:30 | 0,0 | 4,0 |
| Domingo | Não | — | — | — | 0,0 |

#### Outros Exemplos de Horários

| Nome do Horário | Seg–Sex | Sábado | Carga Semanal |
|:----------------|:-------:|:------:|:-------------:|
| Comercial Padrão | 07:30–17:30 | 07:30–11:30 | 44h |
| Administrativo | 08:00–17:00 | Não trabalha | 40h |
| Obra Turno Manhã | 06:00–14:00 | 06:00–10:00 | 44h |
| Obra Turno Tarde | 14:00–22:00 | Não trabalha | 40h |

#### Configuração de Tolerâncias

O sistema suporta configuração de tolerâncias de atraso por obra/local de trabalho:

| Configuração | Valor Padrão | Descrição |
|:-------------|:------------:|:----------|
| Tolerância de Atraso | 15 minutos | Registros dentro da tolerância não são contabilizados como atraso |
| Carga Horária Diária | 8 horas (480 min) | Horas de trabalho esperadas por dia |
| Pausa para Almoço | 1 hora | Tempo de intervalo para refeição |

> **Importante:** O horário de trabalho é uma peça fundamental do sistema. Ele é utilizado no cálculo automático de horas trabalhadas, horas extras, atrasos e na geração da folha de pagamento.

---

## 1.6. Gestão de Usuários

A gestão de usuários é uma das configurações mais importantes do SIGE. Cada pessoa que acessa o sistema precisa ter um usuário cadastrado com o tipo de permissão adequado. O sistema opera no modelo **multi-tenant**, onde cada administrador (ADMIN) gerencia seus próprios dados de forma isolada.

### 1.6.1. Tipos de Usuário

O SIGE possui **5 tipos de usuário**, cada um com diferentes níveis de permissão:

| Tipo | Identificador | Nível | Descrição | Destino Após Login |
|:-----|:--------------|:-----:|:----------|:-------------------|
| **Super Administrador** | `SUPER_ADMIN` | Total | Acesso irrestrito a todo o sistema, incluindo gestão de múltiplas empresas/tenants e diagnósticos | `/super_admin_dashboard` |
| **Administrador** | `ADMIN` | Alto | Gerencia todos os dados da sua empresa (tenant). Cria usuários, departamentos, obras e configurações | `/dashboard` |
| **Gestor de Equipes** | `GESTOR_EQUIPES` | Médio | Gerencia equipes de campo, cria RDOs, controla ponto e acompanha o andamento das obras | `/funcionario/rdo/consolidado` |
| **Almoxarife** | `ALMOXARIFE` | Específico | Acesso ao módulo de almoxarifado para controle de materiais, estoque e movimentações | `/funcionario/rdo/consolidado` |
| **Funcionário** | `FUNCIONARIO` | Básico | Acesso restrito ao próprio perfil, registro de ponto e visualização de RDOs consolidados | `/funcionario/rdo/consolidado` |

**Hierarquia de permissões:** `SUPER_ADMIN` > `ADMIN` > `GESTOR_EQUIPES` / `ALMOXARIFE` > `FUNCIONARIO`

[IMAGEM: Diagrama de hierarquia dos tipos de usuário]

### 1.6.2. Criando Usuários

Somente usuários do tipo **ADMIN** ou **SUPER_ADMIN** podem criar novos usuários.

**Para criar um novo usuário:**

1. Faça login como ADMIN ou SUPER_ADMIN.
2. Acesse a lista de usuários pela URL `/usuarios`.
3. Clique no botão **"Novo Usuário"** (URL: `/usuarios/novo`).
4. Preencha os campos do formulário:

| Campo | Obrigatório | Descrição |
|:------|:-----------:|:----------|
| Nome | Sim | Nome completo do usuário |
| E-mail | Sim | Endereço de e-mail (deve ser único no sistema) |
| Username | Sim | Nome de usuário para login (deve ser único) |
| Senha | Sim | Senha de acesso (será armazenada com hash criptográfico) |
| Tipo de Usuário | Sim | Selecione entre: ADMIN, GESTOR_EQUIPES, ALMOXARIFE ou FUNCIONARIO |

5. Clique em **"Salvar"** para criar o usuário.

[IMAGEM: Formulário de criação de novo usuário]

> **Segurança:** As senhas são armazenadas utilizando hash criptográfico via Werkzeug. O sistema nunca armazena senhas em texto puro. Recomenda-se senhas com no mínimo 8 caracteres, combinando letras maiúsculas, minúsculas, números e caracteres especiais.

> **Multi-tenant:** Quando um ADMIN cria um novo usuário, o campo `admin_id` é preenchido automaticamente, vinculando o novo usuário à empresa do administrador. Isso garante o isolamento dos dados entre empresas.

### 1.6.3. Editando e Desativando Usuários

#### Editando um Usuário

1. Acesse a lista de usuários em `/usuarios`.
2. Localize o usuário desejado na listagem.
3. Clique no ícone de **edição** ao lado do nome (URL: `/usuarios/<id>/editar`).
4. Altere os campos necessários:
   - **Nome**, **E-mail**, **Username** e **Tipo de Usuário** podem ser atualizados.
   - A **Senha** só será alterada se um novo valor for informado no campo correspondente. Se o campo for deixado em branco, a senha atual será mantida.
   - O campo **Ativo** permite ativar ou desativar o acesso do usuário.
5. Clique em **"Salvar"** para confirmar as alterações.

[IMAGEM: Formulário de edição de usuário com campo Ativo destacado]

#### Desativando um Usuário

1. Acesse a edição do usuário conforme descrito acima.
2. Desmarque a opção **"Ativo"**.
3. Clique em **"Salvar"**.

#### Reativando um Usuário

1. Acesse a edição do usuário.
2. Marque novamente a opção **"Ativo"**.
3. Clique em **"Salvar"**.

> **Importante:** Desativar um usuário **não exclui** seus dados do sistema. O usuário desativado simplesmente não conseguirá realizar login. Todos os registros históricos (ponto, RDOs, movimentações) são preservados integralmente. Esta abordagem garante a integridade e rastreabilidade dos dados.

---

## 1.7. Checklist de Configuração Inicial

Utilize a tabela abaixo como guia para garantir que todas as etapas de configuração inicial foram concluídas antes de iniciar a operação do sistema:

| Nº | Etapa | Descrição | Status |
|:--:|:------|:----------|:------:|
| 1 | Instalação do servidor | Docker e EasyPanel configurados, deploy realizado com sucesso | ☐ |
| 2 | Variáveis de ambiente | `DATABASE_URL`, `SESSION_SECRET`, `PGHOST`, `PGPORT`, `PGUSER`, `PGPASSWORD` e `PGDATABASE` configuradas | ☐ |
| 3 | Banco de dados | PostgreSQL acessível e tabelas criadas automaticamente | ☐ |
| 4 | Certificado SSL | HTTPS configurado e funcionando no domínio de produção | ☐ |
| 5 | Primeiro login | Usuário SUPER_ADMIN criado e login realizado com sucesso | ☐ |
| 6 | Dados da empresa | Razão social, CNPJ, endereço e logotipo configurados | ☐ |
| 7 | Departamentos | Ao menos um departamento cadastrado (ex: Engenharia, Produção) | ☐ |
| 8 | Funções | Ao menos uma função/cargo cadastrada com salário base | ☐ |
| 9 | Horários de trabalho | Ao menos um horário de trabalho configurado com dias da semana | ☐ |
| 10 | Usuário ADMIN | Administrador da empresa criado e testado | ☐ |
| 11 | Usuários operacionais | Gestores, almoxarifes e funcionários cadastrados conforme necessidade | ☐ |
| 12 | Teste de acesso | Login testado com cada tipo de usuário, confirmando redirecionamento correto | ☐ |
| 13 | Backup | Rotina de backup do banco de dados PostgreSQL configurada | ☐ |

> **Próximos passos:** Após concluir todas as etapas deste checklist, o sistema estará pronto para uso operacional. Prossiga para o **Capítulo 2 — Dashboard e Painel de Controle** para aprender a utilizar as funcionalidades do dia a dia.

---

# Capitulo 2 — Módulo Dashboard

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

# Capitulo 3 — Gestão de Funcionários

## 3.1. Introdução à Gestão de Funcionários

O módulo de **Gestão de Funcionários** do SIGE (Sistema Integrado de Gestão Empresarial) centraliza todas as operações relacionadas ao cadastro, acompanhamento e controle da força de trabalho da empresa. Este módulo é acessado pelo menu lateral **Funcionários** na barra de navegação principal do sistema.

Principais funcionalidades cobertas neste capítulo:

| Funcionalidade | Descrição |
|---|---|
| Cadastro de funcionários | Registro completo com dados pessoais, contratuais e de acesso |
| Perfil individual | Visualização detalhada de cada funcionário com KPIs e histórico |
| Reconhecimento facial | Cadastro de múltiplas fotos para verificação de identidade no ponto |
| Controle de ponto eletrônico | Registro, visualização e gestão de frequência com validação biométrica |
| Relatórios | Geração de relatórios individuais e consolidados em PDF |

> **Pré-requisito:** Para utilizar este módulo, o usuário deve possuir permissão de **Administrador** ou **Gestor de Equipes**. Funcionários com perfil básico terão acesso apenas ao seu próprio dashboard em `/funcionario-dashboard`.

---

## 3.2. Tela Principal de Funcionários

### Acessando a Tela

1. No menu de navegação superior, clique em **Funcionários**.
2. O sistema direcionará você para a URL `/funcionarios`.

### Visão Geral da Interface

A tela principal de funcionários é dividida nas seguintes áreas:

#### KPIs Resumidos (Topo)

No topo da página, são exibidos indicadores-chave de desempenho (KPIs) gerais do período selecionado:

| KPI | Descrição |
|---|---|
| Total de Funcionários | Quantidade de funcionários ativos cadastrados |
| Horas Trabalhadas | Soma total de horas trabalhadas no período |
| Horas Extras | Total de horas extras acumuladas |
| Faltas | Quantidade de faltas registradas (justificadas e não justificadas) |
| Custo Total | Custo estimado com mão de obra no período |
| Taxa de Absenteísmo | Percentual de ausências em relação aos dias úteis possíveis |

#### Filtros de Período

Acima dos cards de funcionários, há campos para filtrar os dados por período:

1. **Data Início** — Define o início do período de análise (padrão: primeiro dia do mês atual).
2. **Data Fim** — Define o final do período de análise (padrão: data atual).
3. Clique em **Filtrar** para atualizar os KPIs e dados exibidos.

#### Cards de Funcionários

Os funcionários são exibidos em formato de **cards** (cartões visuais), cada um contendo:

- **Foto ou avatar com iniciais** — Se o funcionário possui foto cadastrada, ela será exibida. Caso contrário, um avatar com as iniciais do nome é gerado automaticamente.
- **Nome completo** do funcionário.
- **Função/Cargo** atribuído ao funcionário.
- **Checkbox de seleção** — Permite selecionar múltiplos funcionários para operações em lote.

#### Busca e Filtros

A tela oferece recursos de busca e filtragem:

1. **Campo de busca** — Digite o nome, CPF ou código do funcionário para localizar rapidamente.
2. **Filtro por departamento** — Filtre os funcionários por departamento.
3. **Filtro por função** — Filtre por cargo/função.
4. **Filtro por status** — Visualize funcionários ativos, inativos ou todos.

#### Operações em Lote

Após selecionar funcionários via checkbox, é possível realizar operações em lote como:

- Lançamento de ponto para múltiplos funcionários simultaneamente.
- Alocação em obras.
- Exportação de dados selecionados.

---

## 3.3. Cadastrando um Novo Funcionário

O cadastro de novos funcionários é realizado diretamente na tela principal `/funcionarios`, por meio de um formulário modal. Não existe uma página separada para criação.

### Passo a Passo

1. Na tela de funcionários (`/funcionarios`), clique no botão **+ Novo Funcionário**.
2. Um formulário modal será aberto com os campos organizados em seções.
3. Preencha os dados conforme descrito nas subseções abaixo.
4. Clique em **Salvar** para confirmar o cadastro.

### 3.3.1. Dados Pessoais

Preencha as informações pessoais do funcionário:

| Campo | Tipo | Obrigatório | Descrição |
|---|---|---|---|
| Nome | Texto | Sim | Nome completo do funcionário |
| CPF | Texto (14 caracteres) | Sim | CPF com formatação (000.000.000-00). Deve ser único no sistema |
| RG | Texto | Não | Número do documento de identidade |
| Data de Nascimento | Data | Não | Data de nascimento no formato DD/MM/AAAA |
| Endereço | Texto longo | Não | Endereço completo (rua, número, bairro, cidade, estado, CEP) |
| Telefone | Texto | Não | Telefone com DDD. Ex.: (11) 99999-0000 |
| E-mail | Texto | Não | Endereço de e-mail do funcionário |
| Foto | Arquivo (imagem) | Não | Foto do funcionário (JPG, PNG). Será exibida no card e no perfil |

> **Importante:** O CPF é validado como campo único. Caso um CPF já esteja cadastrado para outro funcionário, o sistema exibirá uma mensagem de erro e impedirá a duplicação.

### 3.3.2. Dados Contratuais

Preencha as informações referentes ao vínculo empregatício:

| Campo | Tipo | Obrigatório | Descrição |
|---|---|---|---|
| Código | Texto (10 caracteres) | Não | Código interno do funcionário (ex.: VV001). Se deixado em branco, será gerado automaticamente pelo sistema |
| Data de Admissão | Data | Sim | Data de início do vínculo empregatício. Padrão: data atual |
| Salário | Numérico (R$) | Não | Salário mensal bruto do funcionário |
| Departamento | Seleção | Não | Departamento ao qual o funcionário pertence |
| Função/Cargo | Seleção | Não | Função ou cargo exercido pelo funcionário |
| Horário de Trabalho | Seleção | Não | Modelo de horário de trabalho associado (define entrada, saída, pausas e dias da semana) |

> **Código automático:** Quando o campo Código é deixado em branco, o sistema gera automaticamente um código sequencial no formato `VV001`, `VV002`, etc., baseando-se no último código cadastrado.

> **Horário de trabalho:** Os modelos de horário de trabalho podem ser configurados em **Configurações > Horários** e definem horários diferenciados para cada dia da semana (ex.: sexta-feira com expediente reduzido, sábado meio período, etc.).

### 3.3.3. Dados de Acesso

Após o cadastro, o funcionário poderá ter seu horário padrão configurado individualmente através da rota:

```
/funcionarios/<id>/horario-padrao
```

Esta configuração permite personalizar os horários de trabalho do funcionário caso ele possua uma jornada diferente do modelo padrão atribuído ao seu departamento.

---

## 3.4. Perfil do Funcionário

### Acessando o Perfil

Para acessar o perfil detalhado de um funcionário:

1. Na tela principal de funcionários, clique no **card** ou no **nome** do funcionário desejado.
2. O sistema direcionará para a URL `/funcionario_perfil/<id>`.

### Seções do Perfil

O perfil do funcionário está organizado nas seguintes seções:

#### Informações Pessoais

Exibe todos os dados cadastrais do funcionário:

- Nome completo, CPF, RG
- Data de nascimento e endereço
- Telefone e e-mail
- Foto (quando cadastrada)
- Departamento e função
- Data de admissão e salário
- Status (ativo/inativo)

#### KPIs Individuais

Indicadores calculados automaticamente para o período filtrado:

| Indicador | Descrição |
|---|---|
| Horas Trabalhadas | Total de horas registradas no período |
| Horas Extras | Total de horas extras acumuladas (calculadas com fator 1,5x) |
| Faltas | Quantidade de faltas não justificadas |
| Faltas Justificadas | Quantidade de faltas com justificativa/atestado |
| Atrasos | Total de horas de atraso acumuladas |
| Dias Trabalhados | Quantidade de dias com registro de ponto efetivo |
| Taxa de Absenteísmo | Percentual de faltas em relação aos dias úteis do período |
| Valor Hora | Valor da hora calculado com base no salário e jornada contratual |
| Valor Horas Extras | Custo total das horas extras (com fator 1,5x) |
| DSR sobre HE | Descanso Semanal Remunerado calculado sobre horas extras (Lei 605/49) |

#### Histórico de Ponto

Tabela detalhada com todos os registros de ponto do período, exibindo:

- Data do registro
- Hora de entrada e saída
- Hora de saída e retorno do almoço
- Horas trabalhadas e horas extras
- Tipo de registro (trabalhado, falta, feriado, etc.)
- Observações

#### Obras Vinculadas

Lista de obras nas quais o funcionário está ou esteve alocado, com informações de:

- Nome da obra
- Período de alocação
- Tipo de local (campo ou escritório)

#### Dashboard Individual

O funcionário possui um dashboard personalizado acessível em `/funcionario-dashboard`, que apresenta um resumo visual de seus indicadores de desempenho.

### Exportando o Perfil em PDF

Para gerar um relatório PDF do perfil do funcionário:

1. No perfil do funcionário, clique no botão **Exportar PDF** ou **Gerar PDF**.
2. O sistema gerará o documento e iniciará o download automaticamente.
3. A URL direta para geração do PDF é `/funcionario_perfil/<id>/pdf`.

O PDF inclui dados pessoais, KPIs do período e o histórico detalhado de registros de ponto.

---

## 3.5. Reconhecimento Facial

### 3.5.1. Importância do Reconhecimento Facial

O SIGE utiliza reconhecimento facial como camada de segurança para validar a identidade do funcionário no momento do registro de ponto. Este recurso previne fraudes como o chamado "ponto amigo" (quando um colega registra o ponto no lugar de outro).

**Parâmetros técnicos do reconhecimento:**

| Parâmetro | Valor | Descrição |
|---|---|---|
| Limiar de distância | 0.40 | Distância máxima entre a foto capturada e a foto cadastrada para considerar uma correspondência |
| Confiança mínima | 60% | Percentual mínimo de confiança exigido para validar o reconhecimento |
| Modelo utilizado | VGG-Face | Rede neural utilizada para extração de características faciais |
| Brilho aceito | 30 a 230 | Faixa de luminosidade aceita na foto (evita fotos muito escuras ou com flash excessivo) |
| Tamanho mínimo | 150×150 px | Resolução mínima da foto capturada para garantir qualidade do reconhecimento |

> **Nota:** Quanto menor a distância facial, maior a confiança de que a pessoa na foto é realmente o funcionário cadastrado.

### 3.5.2. Cadastrando Fotos Faciais

O sistema permite cadastrar **múltiplas fotos faciais** por funcionário, o que melhora significativamente a precisão do reconhecimento em diferentes condições.

#### Acessando a Gestão de Fotos Faciais

1. Acesse o perfil do funcionário em `/funcionario_perfil/<id>`.
2. Clique na opção **Fotos Faciais** ou acesse diretamente a URL:
   ```
   /ponto/funcionario/<id>/fotos-faciais
   ```

#### Cadastrando uma Nova Foto

1. Na tela de fotos faciais, clique em **Adicionar Foto**.
2. A câmera do dispositivo será ativada (ou selecione um arquivo de imagem).
3. Posicione o rosto centralizado no enquadramento.
4. Capture ou selecione a foto.
5. Adicione uma **descrição** para a foto (ex.: "Frontal sem óculos", "Com óculos", "Perfil esquerdo").
6. Clique em **Salvar**.

#### Recomendações para Fotos de Qualidade

Para garantir o melhor desempenho do reconhecimento facial, siga estas orientações:

1. **Cadastre pelo menos 3 fotos** com variações:
   - Uma foto frontal sem acessórios
   - Uma foto com óculos (se o funcionário usa)
   - Uma foto em perfil lateral

2. **Iluminação adequada:**
   - Evite fotos com flash direto ou contraluz
   - Prefira ambientes com iluminação natural ou difusa
   - O sistema rejeita fotos com brilho fora da faixa 30-230

3. **Enquadramento correto:**
   - Rosto centralizado e ocupando a maior parte da imagem
   - Resolução mínima de 150×150 pixels
   - Sem obstruções no rosto (mãos, máscaras, bonés)

4. **Expressão neutra:**
   - Prefira expressões neutras ou levemente sorridente
   - Evite caretas ou expressões exageradas

| Situação | Recomendação |
|---|---|
| Funcionário usa óculos | Cadastrar fotos com e sem óculos |
| Funcionário usa barba | Atualizar fotos após mudanças significativas no visual |
| Funcionário trabalha em campo | Cadastrar foto com EPI (capacete) quando aplicável |
| Baixa taxa de reconhecimento | Adicionar mais fotos em condições variadas de iluminação |

> **Dica:** Fotos faciais podem ser gerenciadas a qualquer momento. Se o sistema apresentar dificuldade em reconhecer um funcionário, adicione novas fotos com condições de iluminação similares às do ambiente de trabalho.

---

## 3.6. Controle de Ponto Eletrônico

O módulo de ponto eletrônico do SIGE permite o registro da jornada de trabalho dos funcionários com validação por reconhecimento facial e geolocalização (geofencing).

### 3.6.1. Registrando Ponto

#### Acesso à Tela de Ponto

1. No menu de navegação, clique no dropdown **Ponto**.
2. Selecione **Registrar Ponto** para acessar a URL `/ponto`.

#### Fluxo de Registro com Reconhecimento Facial

O processo de registro de ponto segue as seguintes etapas:

1. **Seleção do funcionário** — O funcionário é identificado automaticamente (se logado) ou selecionado manualmente pelo gestor.

2. **Captura da foto** — A câmera do dispositivo é ativada para capturar a foto do funcionário no momento do registro.

3. **Validação facial** — O sistema compara a foto capturada com as fotos faciais cadastradas:
   - Se a distância facial for **≤ 0.40** e a confiança **≥ 60%**: registro aprovado
   - Caso contrário: registro rejeitado com mensagem de erro

4. **Validação de geolocalização (Geofencing)** — Se a obra possui coordenadas cadastradas:
   - O GPS do dispositivo é consultado
   - A distância entre o funcionário e a obra é calculada
   - Se a distância for **≤ 100 metros** (raio padrão): localização validada
   - Caso contrário: alerta de localização fora do perímetro

5. **Registro efetivado** — Após as validações, o ponto é registrado com:
   - Hora de entrada ou saída
   - Foto capturada (armazenada em base64)
   - Resultado do reconhecimento facial (sucesso/falha, confiança, modelo)
   - Coordenadas GPS e distância da obra

#### Tipos de Registro

O sistema suporta os seguintes tipos de registro de ponto:

| Tipo | Descrição |
|---|---|
| `trabalhado` | Dia normal de trabalho |
| `falta` | Falta não justificada |
| `falta_justificada` | Falta com justificativa ou atestado médico |
| `feriado` | Dia de feriado (sem trabalho) |
| `feriado_trabalhado` | Trabalho em dia de feriado |
| `sabado_horas_extras` | Trabalho em sábado (computado como hora extra) |
| `domingo_horas_extras` | Trabalho em domingo (computado como hora extra) |

### 3.6.2. Visualizando Registros de Ponto

#### Controle de Ponto (Gestão)

1. No menu **Ponto**, selecione **Controle de Ponto** para acessar `/controle_ponto`.
2. Utilize os filtros disponíveis:
   - **Funcionário** — Selecione um funcionário específico ou visualize todos.
   - **Período** — Defina as datas de início e fim.
   - **Obra** — Filtre por obra específica.
   - **Tipo de registro** — Filtre por tipo (trabalhado, falta, etc.).

A tabela de registros exibe:

| Coluna | Descrição |
|---|---|
| Data | Data do registro |
| Funcionário | Nome do funcionário |
| Entrada | Hora de entrada registrada |
| Saída Almoço | Hora de saída para almoço |
| Retorno Almoço | Hora de retorno do almoço |
| Saída | Hora de saída registrada |
| Horas Trabalhadas | Total de horas calculado automaticamente |
| Horas Extras | Horas extras calculadas (excedente da jornada contratual) |
| Tipo | Tipo do registro (trabalhado, falta, feriado, etc.) |
| Reconhecimento | Indica se houve validação facial |
| Observações | Anotações adicionais |

#### Cálculos Automáticos

O sistema realiza os seguintes cálculos automaticamente:

1. **Horas trabalhadas** — Diferença entre entrada e saída, descontando o período de almoço. Se a jornada ultrapassa 6 horas, 1 hora de almoço é descontada automaticamente.
2. **Horas extras** — Diferença entre as horas trabalhadas e a jornada contratual definida no horário de trabalho do funcionário.
3. **Atrasos** — Diferença entre o horário contratual de entrada e o horário efetivo de entrada.
4. **DSR sobre horas extras** — Descanso semanal remunerado calculado proporcionalmente sobre as horas extras, conforme a Lei 605/49.

### 3.6.3. Editando e Justificando Registros

#### Editando um Registro

1. Na tela de controle de ponto (`/controle_ponto`), localize o registro desejado.
2. Clique no botão **Editar** (ícone de lápis) na linha correspondente.
3. Um formulário será exibido permitindo alterar:
   - Horários de entrada, saída, almoço
   - Tipo de registro
   - Obra vinculada
   - Observações
4. Clique em **Salvar** para confirmar as alterações.

#### Justificando Faltas

Para registrar uma justificativa de falta:

1. Localize o registro de falta na tela de controle de ponto.
2. Clique em **Editar**.
3. Altere o tipo de registro para **Falta Justificada**.
4. No campo **Observações**, registre o motivo da justificativa (ex.: "Atestado médico", "Licença", etc.).
5. Salve o registro.

> **Importante:** Faltas justificadas são tratadas de forma diferente no cálculo de DSR. Enquanto faltas não justificadas podem gerar perda proporcional do DSR, faltas justificadas preservam o direito ao descanso semanal remunerado.

---

## 3.7. Relatórios de Funcionários

O SIGE oferece diversas opções de relatórios relacionados aos funcionários:

### Relatório Individual (PDF)

Gere um relatório completo de um funcionário específico:

1. Acesse o perfil do funcionário em `/funcionario_perfil/<id>`.
2. Selecione o período desejado nos filtros de data.
3. Clique em **Gerar PDF** ou acesse diretamente:
   ```
   /funcionario_perfil/<id>/pdf
   ```

O relatório PDF inclui:

- Dados cadastrais completos
- KPIs do período selecionado (horas, extras, faltas, custos)
- Detalhamento financeiro (valor hora, DSR, descontos)
- Histórico completo de registros de ponto
- Informações de obras vinculadas

### Relatórios Consolidados

Na tela principal de funcionários (`/funcionarios`), os KPIs consolidados oferecem uma visão gerencial de toda a equipe:

| Relatório | Dados Incluídos |
|---|---|
| Resumo de horas | Total de horas trabalhadas e extras por funcionário |
| Controle de faltas | Faltas, faltas justificadas e taxa de absenteísmo |
| Custo de mão de obra | Custo total com salários, horas extras e encargos |
| Produtividade | Horas por obra, eficiência e alocação |

### Acessando Relatórios Gerais

1. No menu de navegação, clique em **Relatórios**.
2. Selecione a categoria **Funcionários** ou **Ponto**.
3. Configure os filtros (período, departamento, obra).
4. Clique em **Gerar Relatório**.

---

## Resumo de URLs do Módulo de Funcionários

| Funcionalidade | URL | Método |
|---|---|---|
| Lista de funcionários | `/funcionarios` | GET |
| Criar funcionário | `/funcionarios` | POST |
| Perfil do funcionário | `/funcionario_perfil/<id>` | GET |
| PDF do perfil | `/funcionario_perfil/<id>/pdf` | GET |
| Dashboard do funcionário | `/funcionario-dashboard` | GET |
| Horário padrão | `/funcionarios/<id>/horario-padrao` | GET |
| Fotos faciais | `/ponto/funcionario/<id>/fotos-faciais` | GET/POST |
| Registro de ponto | `/ponto` | GET/POST |
| Controle de ponto | `/controle_ponto` | GET |

---

# Capitulo 4 — Gestão de Obras

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

#### Ordenação

A listagem de obras é ordenada automaticamente por **data de início** (mais recente primeiro). Obras com status "Em andamento" tendem a aparecer no topo por possuírem datas de início mais recentes.

---

## 4.3. Cadastrando uma Nova Obra

### Acessando o Formulário

1. Na tela principal de obras (`/obras`), clique no botão **+ Nova Obra**.
2. O sistema direcionará você para a URL `/obras/nova`.

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

#### Acompanhamento da Execução de Serviços

À medida que os RDOs são registrados, o sistema atualiza automaticamente:

- **Quantidade Executada** — Soma das quantidades informadas nos RDOs.
- **Percentual Concluído** — Razão entre executado e planejado.
- **Valor Total Executado** — Custo real acumulado do serviço.
- **Data de Início Real** — Registrada na primeira execução.
- **Data de Fim Real** — Registrada quando o serviço atinge 100% de conclusão.

| Indicador | Fórmula |
|---|---|
| % Concluído | (Quantidade Executada / Quantidade Planejada) x 100 |
| Desvio de Custo | Valor Total Executado - Valor Total Planejado |
| Status Automático | Atualizado conforme o percentual (0% = Não Iniciado, 1-99% = Em Andamento, 100% = Concluído) |

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

#### KPIs Principais

| KPI | Descrição |
|---|---|
| Custo Total | Somatório de todos os custos apurados: mão de obra + alimentação + transporte + diversos |
| Custo de Mão de Obra | Calculado com base nos registros de ponto x valor/hora do funcionário, incluindo horas extras a 150% |
| Custo de Alimentação | Soma dos registros de alimentação vinculados à obra no período |
| Custos Diversos | Lançamentos avulsos de custos operacionais da obra |
| Custo de Transporte | Despesas de veículos associadas à obra |
| Dias Trabalhados | Quantidade de dias distintos com registros de ponto na obra |
| Funcionários Alocados | Total de funcionários distintos que registraram ponto na obra |
| Orçamento Restante | Orçamento - Custo Total (com indicador visual de alerta se negativo) |

#### Composição de Custos

O sistema apresenta a composição de custos de forma visual, permitindo identificar rapidamente qual categoria representa a maior parcela do gasto:

| Categoria | Fonte de Dados |
|---|---|
| Mão de Obra | Registros de ponto x valor/hora (horas normais + horas extras x 1,5) |
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

> **Referência:** Para detalhes completos sobre o preenchimento do RDO, consulte o **Capítulo 6 — Relatório Diário de Obra (RDO)**.

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
| Margem Bruta | Valor do Contrato - Custo Realizado |
| Margem Percentual | (Margem Bruta / Valor do Contrato) x 100 |
| Desvio Orçamentário | Custo Realizado - Valor Orçado |
| % Consumido do Orçamento | (Custo Realizado / Valor Orçado) x 100 |

### Análise de Desvios

O sistema destaca automaticamente situações que requerem atenção:

| Situação | Indicador Visual | Ação Recomendada |
|---|---|---|
| Custo dentro do orçamento (< 80%) | Verde | Projeto sob controle |
| Custo próximo do limite (80-100%) | Amarelo | Revisar projeções de custo |
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

> **Dica:** Para uma análise comparativa entre múltiplas obras, utilize o módulo **Relatórios** no menu principal, que oferece visões consolidadas de todo o portfólio.

---

## Operações Administrativas de Obras

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

## Resumo de URLs do Módulo de Obras

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

# Capitulo 5 — Gestão de Frota e Veículos

## 5.1. Introdução à Gestão de Frota

O módulo de **Gestão de Frota** do SIGE (EnterpriseSync) permite o controle completo dos veículos utilizados pela empresa em suas operações. Com ele, é possível:

- Cadastrar e manter atualizados os dados de cada veículo da frota;
- Registrar o uso dos veículos, incluindo motorista, obra de destino, quilometragem e passageiros;
- Controlar todos os custos associados (combustível, manutenção, pedágio, seguro, entre outros);
- Acompanhar indicadores-chave de desempenho (KPIs) como custo total, custo por quilômetro e quilometragem acumulada;
- Visualizar gráficos de custos por mês e por categoria;
- Monitorar documentação veicular, como data de licenciamento e vigência do seguro.

O acesso ao módulo é feito pelo menu lateral, clicando em **Veículos**. O Dashboard principal do sistema também exibe o KPI de quantidade de veículos cadastrados.

[IMAGEM: Menu lateral com destaque no item Veículos]

---

## 5.2. Tela Principal de Veículos

Ao acessar o menu **Veículos** (URL: `/veiculos`), o sistema exibe a listagem completa dos veículos cadastrados. A tela apresenta os veículos em formato de cards ou lista, permitindo uma visão rápida do estado da frota.

[IMAGEM: Tela principal de veículos com listagem]

### 5.2.1. Informações Exibidas

Cada veículo na listagem apresenta as seguintes informações:

| Informação         | Descrição                                                  |
|---------------------|------------------------------------------------------------|
| **Placa**           | Placa do veículo no formato Mercosul ou antigo             |
| **Modelo / Marca**  | Modelo e fabricante do veículo                             |
| **Ano**             | Ano de fabricação                                          |
| **Tipo**            | Categoria do veículo (caminhonete, carro, caminhão, etc.)  |
| **Cor**             | Cor do veículo                                             |
| **KM Atual**        | Quilometragem atual registrada no odômetro                 |
| **Status**          | Situação atual: Ativo, Em manutenção, Inativo, etc.        |

### 5.2.2. Status dos Veículos

O sistema utiliza indicadores visuais (badges coloridos) para representar o status de cada veículo:

| Status              | Cor        | Descrição                                      |
|---------------------|------------|-------------------------------------------------|
| **Ativo**           | Verde      | Veículo disponível para uso                     |
| **Em manutenção**   | Amarelo    | Veículo temporariamente indisponível            |
| **Inativo**         | Vermelho   | Veículo fora de operação                        |

### 5.2.3. Ações Disponíveis

Na tela de listagem, o usuário pode executar as seguintes ações:

1. **Novo Veículo** — Botão para cadastrar um novo veículo na frota;
2. **Visualizar Detalhes** — Acessa o painel completo com KPIs, gráficos e histórico do veículo;
3. **Editar** — Altera os dados cadastrais do veículo;
4. **Registrar Uso** — Abre o formulário para lançar uma nova viagem/uso;
5. **Lançar Custo** — Registra um novo custo associado ao veículo;
6. **Excluir** — Remove o veículo do sistema (ação restrita a administradores).

[IMAGEM: Botões de ação na listagem de veículos]

---

## 5.3. Cadastrando um Novo Veículo

Para cadastrar um novo veículo, clique no botão **Novo Veículo** na tela principal ou acesse diretamente a URL `/veiculos/novo`. O formulário de cadastro está dividido em três seções.

[IMAGEM: Formulário de cadastro de novo veículo]

### 5.3.1. Dados do Veículo

Preencha os campos de identificação básica do veículo:

| Campo       | Obrigatório | Descrição                                              |
|-------------|-------------|--------------------------------------------------------|
| **Placa**   | Sim         | Placa do veículo (formato antigo ABC-1234 ou Mercosul ABC1D23) |
| **Modelo**  | Sim         | Modelo do veículo (ex.: Hilux, Saveiro, HR)            |
| **Marca**   | Sim         | Fabricante (ex.: Toyota, Volkswagen, Hyundai)          |
| **Ano**     | Sim         | Ano de fabricação do veículo                           |
| **Tipo**    | Sim         | Categoria: Carro, Caminhonete, Caminhão, Van, Moto, etc. |
| **Cor**     | Não         | Cor predominante do veículo                            |
| **KM Atual**| Não         | Quilometragem atual do odômetro                        |
| **Status**  | Sim         | Situação inicial do veículo (Ativo, Em manutenção, Inativo) |

**Dica:** Informe a quilometragem atual com precisão, pois ela será utilizada como referência para validação dos lançamentos de uso subsequentes.

### 5.3.2. Dados de Documentação

Registre as informações documentais do veículo para controle de regularidade:

| Campo                    | Obrigatório | Descrição                                        |
|--------------------------|-------------|--------------------------------------------------|
| **RENAVAM**              | Não         | Número do Registro Nacional de Veículos          |
| **Chassi**               | Não         | Número do chassi do veículo                      |
| **Data de Licenciamento**| Não         | Data de vencimento do licenciamento anual         |
| **Vigência do Seguro**   | Não         | Data de vencimento da apólice de seguro           |

**Importante:** O sistema utiliza a data de licenciamento para exibir alertas de proximidade de vencimento na tela de detalhes do veículo.

### 5.3.3. Configurações de Custo

Configure os parâmetros financeiros do veículo:

| Campo         | Obrigatório | Descrição                                          |
|---------------|-------------|-----------------------------------------------------|
| **Custo/KM**  | Não         | Custo estimado por quilômetro rodado (R$/km)        |

Este valor é utilizado para cálculos de custo operacional e comparações de eficiência entre veículos da frota.

**Passo a passo para cadastrar:**

1. Acesse **Veículos** no menu lateral;
2. Clique no botão **Novo Veículo**;
3. Preencha os campos obrigatórios (Placa, Modelo, Marca, Ano, Tipo);
4. Informe os dados de documentação e configurações de custo conforme necessário;
5. Clique em **Salvar** para concluir o cadastro.

Após o cadastro, o veículo aparecerá na listagem principal e estará disponível para registro de uso e custos.

---

## 5.4. Registrando o Uso de Veículos

O registro de uso documenta cada viagem ou deslocamento realizado com os veículos da frota, vinculando o motorista, a obra de destino, a quilometragem percorrida e os passageiros transportados.

### 5.4.1. Lançando Nova Viagem/Uso

Para registrar um novo uso, utilize o botão **Registrar Uso** na listagem de veículos ou acesse o formulário diretamente. O sistema abrirá um modal ou formulário com os seguintes campos:

[IMAGEM: Formulário de registro de uso do veículo]

| Campo                     | Obrigatório | Descrição                                              |
|---------------------------|-------------|--------------------------------------------------------|
| **Veículo**               | Sim         | Veículo utilizado (selecionado automaticamente se acessado via card) |
| **Motorista/Condutor**    | Sim         | Funcionário responsável pela condução                  |
| **Data do Uso**           | Sim         | Data em que o deslocamento ocorreu                     |
| **Horário de Saída**      | Não         | Hora de partida do veículo                             |
| **Horário de Chegada**    | Não         | Hora de retorno do veículo                             |
| **KM Inicial**            | Sim         | Quilometragem do odômetro na saída                     |
| **KM Final**              | Sim         | Quilometragem do odômetro no retorno                   |
| **Obra**                  | Não         | Obra de destino (vincula o deslocamento a uma obra)    |
| **Observações**           | Não         | Informações complementares sobre o deslocamento        |
| **% Combustível**         | Não         | Nível do tanque de combustível no momento do registro  |
| **Passageiros (Frente)**  | Não         | Funcionários transportados no banco da frente (máx. 3) |
| **Passageiros (Traseira)**| Não         | Funcionários transportados no banco traseiro (máx. 5)  |

**Validações automáticas:**

- O **KM Final** deve ser maior que o **KM Inicial**;
- O **KM Final** não pode ser menor que a quilometragem atual registrada do veículo;
- O mesmo funcionário não pode ser registrado como motorista e passageiro simultaneamente;
- Há limite máximo de 3 passageiros na frente e 5 na traseira.

**Passo a passo:**

1. Na listagem de veículos, clique em **Registrar Uso** no card do veículo desejado;
2. O campo **Veículo** será preenchido automaticamente;
3. Selecione o **Motorista** na lista de funcionários ativos;
4. Informe a **Data**, os **horários** e a **quilometragem** de saída e retorno;
5. Opcionalmente, vincule a uma **Obra** e adicione **passageiros**;
6. Clique em **Salvar** para registrar o uso.

Após o registro, a quilometragem atual do veículo é atualizada automaticamente com o valor do KM Final informado.

### 5.4.2. Histórico de Usos

O histórico de usos pode ser consultado na tela de **Detalhes do Veículo** (seção 5.6). Ele apresenta uma tabela cronológica com todos os deslocamentos registrados, incluindo:

- Data do uso;
- Nome do motorista/condutor;
- KM inicial e final;
- Quilometragem percorrida;
- Obra de destino;
- Horários de saída e retorno;
- Passageiros transportados (com indicação de posição: frente/traseira).

[IMAGEM: Tabela de histórico de usos do veículo]

É possível visualizar os detalhes completos de cada uso clicando sobre o registro, que abrirá um modal com informações detalhadas incluindo dados técnicos, horários e lista de passageiros organizados por posição no veículo.

---

## 5.5. Controle de Custos de Veículos

O módulo de custos permite registrar e acompanhar todas as despesas associadas a cada veículo, categorizadas por tipo para análise financeira detalhada.

### 5.5.1. Lançando Novo Custo

Para registrar um novo custo, utilize o botão **Lançar Custo** na listagem de veículos ou acesse o formulário de novo custo. Preencha os seguintes campos:

[IMAGEM: Formulário de lançamento de custo do veículo]

| Campo            | Obrigatório | Descrição                                              |
|------------------|-------------|--------------------------------------------------------|
| **Veículo**      | Sim         | Veículo ao qual o custo será atribuído                 |
| **Tipo de Custo**| Sim         | Categoria da despesa (ver tabela abaixo)               |
| **Valor (R$)**   | Sim         | Valor monetário da despesa                             |
| **Data**         | Sim         | Data em que a despesa ocorreu                          |
| **Fornecedor**   | Não         | Nome do fornecedor ou prestador de serviço             |
| **Nota Fiscal**  | Não         | Número da nota fiscal para controle contábil           |
| **Obra**         | Não         | Obra vinculada ao custo (para rateio por obra)         |
| **Observações**  | Não         | Detalhes adicionais sobre a despesa                    |

**Tipos de custo disponíveis:**

| Tipo de Custo    | Descrição                                           |
|------------------|-----------------------------------------------------|
| **Combustível**  | Abastecimentos de combustível                       |
| **Manutenção**   | Revisões, reparos, troca de peças                   |
| **Pedágio**      | Custos com pedágios em rodovias                     |
| **Seguro**       | Pagamento de apólice de seguro                      |
| **Licenciamento**| Taxas de licenciamento e IPVA                       |
| **Multa**        | Multas de trânsito                                  |
| **Lavagem**      | Lavagem e higienização do veículo                   |
| **Outros**       | Despesas diversas não classificadas acima            |

**Passo a passo:**

1. Na listagem de veículos, clique em **Lançar Custo** no card do veículo;
2. Selecione o **Tipo de Custo** adequado;
3. Informe o **Valor**, a **Data** e, opcionalmente, o **Fornecedor** e a **Nota Fiscal**;
4. Vincule a uma **Obra** se o custo for específico de um projeto;
5. Clique em **Salvar** para registrar o custo.

### 5.5.2. Histórico de Custos

O histórico completo de custos de cada veículo está disponível na tela de **Detalhes do Veículo** (seção 5.6). A tabela apresenta:

- Data do custo;
- Tipo de custo (com indicador visual por categoria);
- Valor;
- Fornecedor;
- Nota fiscal;
- Obra vinculada;
- Observações.

[IMAGEM: Tabela de histórico de custos do veículo]

Os custos são exibidos em ordem cronológica decrescente (mais recentes primeiro) e podem ser editados ou excluídos conforme a permissão do usuário.

---

## 5.6. Detalhes do Veículo

A tela de detalhes (URL: `/veiculos/<id>/detalhes`) é o painel central de acompanhamento de cada veículo. Ela reúne todas as informações cadastrais, indicadores de desempenho, gráficos analíticos e histórico de movimentação.

[IMAGEM: Tela de detalhes do veículo com KPIs e gráficos]

### 5.6.1. Indicadores-Chave (KPIs)

No topo da página de detalhes são exibidos os principais KPIs do veículo:

| KPI                        | Descrição                                                     |
|-----------------------------|---------------------------------------------------------------|
| **Custo Total**             | Soma de todos os custos registrados para o veículo (R$)       |
| **Custo por KM**            | Custo total dividido pela quilometragem total percorrida      |
| **KM Total**                | Quilometragem total acumulada pelo veículo                    |
| **Próximo Licenciamento**   | Data prevista para o próximo licenciamento veicular           |

Esses indicadores são calculados automaticamente com base nos registros de uso e custos lançados no sistema. Os KPIs podem ser filtrados por período (data inicial e data final) para análise de intervalos específicos.

### 5.6.2. Gráficos Analíticos

A tela de detalhes inclui gráficos interativos para análise visual dos dados:

1. **Custos por Mês** — Gráfico de barras mostrando a evolução mensal dos custos totais do veículo, permitindo identificar tendências de aumento ou redução de despesas;

2. **Custos por Categoria** — Gráfico de pizza (ou rosca) com a distribuição percentual dos custos por tipo (combustível, manutenção, pedágio, seguro, etc.), facilitando a identificação das principais fontes de despesa.

[IMAGEM: Gráficos de custos por mês e por categoria]

### 5.6.3. Dados Cadastrais

A seção de dados cadastrais exibe todas as informações registradas do veículo, incluindo:

- Placa, modelo, marca, ano, tipo e cor;
- RENAVAM e número do chassi;
- Quilometragem atual;
- Data de licenciamento e vigência do seguro;
- Status atual do veículo;
- Custo por KM configurado.

### 5.6.4. Histórico Completo

Na parte inferior da tela de detalhes, o sistema apresenta o histórico completo de:

- **Usos/Viagens** — Todos os deslocamentos registrados com informações de motorista, quilometragem, obra e passageiros;
- **Custos** — Todos os lançamentos financeiros com tipo, valor, data e fornecedor.

Cada registro pode ser expandido para visualização detalhada ou editado diretamente a partir desta tela.

---

## 5.7. Relatórios de Frota

O módulo de Veículos integra-se ao sistema de relatórios do SIGE, disponível no menu **Relatórios**. Os principais relatórios disponíveis para a gestão de frota incluem:

### 5.7.1. Relatório de Custos por Veículo

Apresenta um resumo consolidado dos custos de cada veículo em um período selecionado, com detalhamento por categoria de custo. Útil para comparar a eficiência financeira entre veículos da frota.

### 5.7.2. Relatório de Utilização da Frota

Mostra a frequência de uso de cada veículo, quilometragem percorrida e motoristas associados. Permite identificar veículos subutilizados ou sobrecarregados.

### 5.7.3. Relatório de Custos por Obra

Quando os custos de veículos são vinculados a obras específicas, este relatório consolida os gastos de frota por projeto, auxiliando no controle orçamentário e no rateio de despesas.

### 5.7.4. Alertas de Documentação

O sistema gera alertas automáticos para:

- Licenciamento próximo do vencimento (exibido no KPI "Próximo Licenciamento");
- Seguro próximo do vencimento;
- Veículos com status "Em manutenção" por período prolongado.

[IMAGEM: Tela de relatórios de frota]

---

## Resumo das URLs do Módulo de Veículos

| Funcionalidade          | URL                                |
|-------------------------|------------------------------------|
| Listagem de Veículos    | `/veiculos`                        |
| Novo Veículo            | `/veiculos/novo`                   |
| Editar Veículo          | `/veiculos/<id>/editar`            |
| Detalhes do Veículo     | `/veiculos/<id>/detalhes`          |
| Registrar Uso           | `/veiculos/uso` (POST)             |
| Novo Custo              | `/custo_veiculo/novo`              |
| Editar Custo            | `/custo_veiculo/<id>/editar`       |

---

## Dicas e Boas Práticas para Veículos

1. **Mantenha a quilometragem atualizada** — Sempre registre os usos com KM inicial e final corretos para que o sistema calcule corretamente o custo por quilômetro;
2. **Classifique os custos corretamente** — Utilize o tipo de custo adequado para cada despesa, pois isso impacta diretamente nos gráficos e relatórios analíticos;
3. **Vincule custos e usos às obras** — Sempre que possível, associe os registros a uma obra para possibilitar o rateio correto das despesas;
4. **Monitore os alertas de documentação** — Verifique regularmente os KPIs de licenciamento e seguro para evitar irregularidades;
5. **Registre todos os passageiros** — O controle de passageiros por posição (frente/traseira) é importante para conformidade com normas de segurança e seguro;
6. **Revise os gráficos mensalmente** — Utilize os gráficos de custos por mês e por categoria para identificar oportunidades de redução de despesas.

---

# Capitulo 6 — Relatorio Diario de Obra (RDO)

## 6.1. Introducao ao RDO

O **Relatorio Diario de Obra (RDO)** e o principal instrumento de registro e controle da execucao fisica de uma obra no SIGE. Funciona como um verdadeiro **diario de bordo** da construcao, documentando tudo o que acontece no canteiro de obras a cada dia: mao de obra presente, equipamentos utilizados, servicos executados, condicoes climaticas e registros fotograficos.

### Por que o RDO e essencial?

| Beneficio | Descricao |
|-----------|-----------|
| **Registro historico** | Documenta diariamente todas as atividades executadas no canteiro |
| **Controle de progresso automatico** | Ao aprovar um RDO, o sistema atualiza automaticamente o percentual de conclusao da obra |
| **Rastreabilidade** | Permite verificar quem trabalhou, quais servicos foram realizados e em que condicoes |
| **Evidencia fotografica** | Fotos otimizadas em WebP comprovam a execucao dos servicos |
| **Integracao financeira** | Dados de mao de obra e equipamentos alimentam o modulo financeiro |
| **Base para medicoes** | Serve como base documental para medicoes contratuais com o cliente |

> **Importante:** O RDO foi projetado com **design mobile-first**, permitindo que o responsavel pela obra preencha o relatorio diretamente do canteiro, usando smartphone ou tablet.

### Fluxo Geral do RDO

```
Criacao (Rascunho) → Elaboracao → Envio para Aprovacao → Aprovacao/Rejeicao → Atualizacao Automatica da Obra
```

O sistema utiliza um **EventManager** para integracoes automaticas: ao aprovar um RDO, o progresso da obra, os indicadores financeiros e o dashboard sao atualizados de forma automatica e transparente.

---

## 6.2. Tela Principal de RDOs

### Acessando a Lista Consolidada

Para acessar a tela principal de RDOs, navegue pelo menu lateral ate:

**Menu → RDO → Lista Consolidada**

A URL de acesso direto e: `/funcionario/rdo/consolidado`

### Colunas da Lista

A tabela consolidada de RDOs apresenta as seguintes informacoes:

| Coluna | Descricao | Exemplo |
|--------|-----------|---------|
| **Numero RDO** | Identificador unico gerado automaticamente | RDO-10-2025-013 |
| **Obra** | Nome da obra associada ao RDO | Obra E2E Test yBSJZA |
| **Data** | Data do relatorio diario | 27/10/2025 |
| **Status** | Situacao atual do RDO | Rascunho |
| **Progresso** | Percentual de conclusao dos servicos registrados | 45,2% |
| **Acoes** | Botoes para visualizar, editar ou excluir | Visualizar / Editar |

### Filtros Disponiveis

A tela principal oferece filtros para localizar RDOs rapidamente:

1. **Filtro por Obra** — Selecione uma obra especifica no dropdown
2. **Filtro por Status** — Filtre por Rascunho, Em Elaboracao, Pendente de Aprovacao, Aprovado ou Reprovado
3. **Filtro por Data Inicio** — Defina a data inicial do periodo de busca
4. **Filtro por Data Fim** — Defina a data final do periodo de busca
5. **Filtro por Funcionario** — Filtre por responsavel pelo preenchimento

### Status dos RDOs

O sistema utiliza os seguintes status para controle do ciclo de vida do RDO:

| Status | Descricao | Cor |
|--------|-----------|-----|
| **Rascunho** | RDO criado, ainda em preenchimento inicial | Cinza |
| **Em Elaboracao** | RDO sendo preenchido com detalhes de servicos e mao de obra | Azul |
| **Pendente de Aprovacao** | RDO finalizado e enviado para aprovacao do gestor | Amarelo |
| **Aprovado** | RDO revisado e aprovado pelo gestor — atualiza progresso da obra | Verde |
| **Reprovado** | RDO rejeitado com observacoes — necessita correcao e reenvio | Vermelho |

### Acoes Rapidas

Na lista de RDOs, cada registro apresenta botoes de acao:

- **Visualizar** — Abre o RDO em modo somente leitura com todos os detalhes
- **Editar** — Abre o formulario de edicao (disponivel apenas para RDOs em Rascunho ou Em Elaboracao)
- **Excluir** — Remove o RDO e todas as suas dependencias (mao de obra, equipamentos, fotos, subatividades)

> **Dica:** Na tela de Obras (`/funcionario/obras`), cada obra possui um botao **"+RDO"** que permite criar um novo RDO ja vinculado aquela obra, agilizando o preenchimento.

---

## 6.3. Criando um Novo RDO

### Acesso ao Formulario de Criacao

Existem duas formas de criar um novo RDO:

1. **Pela tela de RDOs:** Clique no botao **"Novo RDO"** na lista consolidada
   - URL: `/rdo/novo`
2. **Pela tela de Obras:** Clique no botao **"+RDO"** na obra desejada
   - URL: `/funcionario/rdo/novo?obra_id=<id_da_obra>`

Ao acessar via obra, o formulario ja vem com a obra pre-selecionada e com as atividades do ultimo RDO pre-carregadas.

### 6.3.1. Informacoes Gerais

O primeiro bloco do formulario solicita as informacoes basicas do RDO:

| Campo | Tipo | Obrigatorio | Descricao |
|-------|------|:-----------:|-----------|
| **Obra** | Dropdown de selecao | Sim | Selecione a obra para a qual o RDO sera registrado |
| **Data** | Campo de data | Sim | Data do relatorio (padrao: data atual) |
| **Condicao Climatica — Manha** | Dropdown | Sim | Condicao do tempo no periodo da manha (Bom, Nublado, Chuvoso, etc.) |
| **Condicao Climatica — Tarde** | Dropdown | Sim | Condicao do tempo no periodo da tarde |
| **Observacoes Meteorologicas** | Texto livre | Nao | Detalhes adicionais sobre as condicoes climaticas |
| **Comentario Geral** | Texto livre | Nao | Observacoes gerais sobre o dia de trabalho |

**Regras de Negocio:**

- O sistema **nao permite** criar dois RDOs para a mesma obra na mesma data. Se ja existir um RDO para a combinacao obra + data selecionada, o usuario sera redirecionado automaticamente para a edicao do RDO existente.
- O **numero do RDO** e gerado automaticamente pelo sistema no formato: `RDO-<obra_id>-<ano>-<sequencial>` (exemplo: RDO-10-2025-013).
- O **responsavel** e identificado automaticamente pelo usuario logado no sistema.

> **Importante:** O campo de data vem preenchido com a data atual, mas pode ser alterado para registrar RDOs retroativos, caso necessario.

### 6.3.2. Mao de Obra

A secao de Mao de Obra permite registrar todos os trabalhadores presentes no canteiro durante o dia:

| Campo | Descricao |
|-------|-----------|
| **Funcionario** | Selecao do funcionario presente (lista filtrada pela obra) |
| **Funcao** | Funcao exercida pelo trabalhador no dia |
| **Tipo** | Classificacao: **Proprio** (equipe interna) ou **Terceirizado** |
| **Horas Trabalhadas** | Quantidade de horas trabalhadas no dia |

**Como adicionar mao de obra:**

1. Clique no botao **"Adicionar Mao de Obra"**
2. Selecione o funcionario no dropdown
3. Informe a funcao exercida
4. Selecione o tipo (proprio ou terceirizado)
5. Informe as horas trabalhadas
6. Repita para cada trabalhador presente

> **Dica:** O sistema pre-carrega a lista de funcionarios ativos vinculados a empresa, facilitando a selecao rapida.

### 6.3.3. Equipamentos

A secao de Equipamentos registra as maquinas e equipamentos utilizados no dia:

| Campo | Descricao |
|-------|-----------|
| **Descricao** | Nome ou descricao do equipamento utilizado |
| **Quantidade** | Quantidade de unidades do equipamento |
| **Tipo** | Classificacao: **Proprio** ou **Alugado** |

**Como adicionar equipamentos:**

1. Clique no botao **"Adicionar Equipamento"**
2. Informe a descricao do equipamento (ex: "Retroescavadeira CAT 416F")
3. Informe a quantidade
4. Selecione o tipo (proprio ou alugado)
5. Repita para cada equipamento utilizado

---

## 6.4. Registrando Atividades no RDO

A secao de Atividades e a parte mais importante do RDO, pois alimenta diretamente o calculo de progresso da obra. O sistema utiliza uma estrutura hierarquica: **Servicos → Subatividades**.

### 6.4.1. Selecionando Servicos

Os servicos disponiveis para registro no RDO sao aqueles previamente cadastrados na obra atraves do modulo de **Servicos da Obra** (`servico_obra_real`).

**Pre-carregamento inteligente:**

- Ao criar o **primeiro RDO** de uma obra, o sistema carrega automaticamente todos os servicos cadastrados naquela obra, com suas respectivas subatividades
- Ao criar **RDOs subsequentes**, o sistema pre-carrega os dados do ultimo RDO da obra, permitindo atualizar os percentuais de conclusao

| Informacao Exibida | Descricao |
|--------------------|-----------|
| **Nome do Servico** | Nome do servico cadastrado (ex: "Alvenaria de Vedacao") |
| **Categoria** | Categoria do servico (ex: "Estrutura", "Acabamento") |
| **Quantidade Planejada** | Quantidade total planejada para o servico na obra |
| **Unidade de Medida** | Unidade utilizada (m2, m3, kg, un, m, h, etc.) |

### 6.4.2. Registrando Subatividades

Cada servico pode conter multiplas **subatividades** cadastradas na tabela mestre (`SubatividadeMestre`). No RDO, o usuario registra:

| Campo | Descricao |
|-------|-----------|
| **Subatividade** | Nome da subatividade (pre-carregado da tabela mestre) |
| **Quantidade Executada** | Quantidade efetivamente executada no dia |
| **Percentual de Conclusao** | Percentual acumulado de conclusao da subatividade |
| **Observacoes Tecnicas** | Notas tecnicas sobre a execucao |

**Calculo de Progresso:**

O progresso total do RDO e calculado como a **media simples** dos percentuais de conclusao de todas as subatividades registradas:

```
Progresso Total = Soma dos Percentuais / Numero de Subatividades
```

Exemplo: Se um RDO possui 3 subatividades com 100%, 50% e 30%, o progresso total sera:
```
(100 + 50 + 30) / 3 = 60%
```

### 6.4.3. Anexando Fotos

O sistema permite anexar fotografias para documentar a execucao dos servicos:

| Campo | Descricao |
|-------|-----------|
| **Foto** | Upload de imagem (JPG, PNG ou WebP) |
| **Descricao** | Descricao da foto (o que ela documenta) |
| **Tipo** | Classificacao da foto (servico, material, seguranca, etc.) |

**Caracteristicas do upload de fotos:**

- As fotos sao automaticamente **otimizadas para formato WebP**, reduzindo o tamanho do arquivo sem perda significativa de qualidade
- As fotos sao armazenadas na pasta `static/uploads/rdo/<obra_id>/<rdo_id>/`
- E possivel anexar multiplas fotos por RDO
- As fotos ficam disponiveis para visualizacao na tela de detalhes do RDO e no portal do cliente

> **Dica Mobile:** O upload de fotos foi otimizado para dispositivos moveis, permitindo capturar fotos diretamente da camera do smartphone e anexar ao RDO em tempo real.

---

## 6.5. Finalizando e Enviando para Aprovacao

Apos preencher todas as secoes do RDO, o usuario pode:

### Salvar como Rascunho

- Clique no botao **"Salvar Rascunho"**
- O RDO sera salvo com status **Rascunho** e podera ser editado posteriormente
- Ideal para quando o preenchimento sera concluido em outro momento

### Enviar para Aprovacao

1. Revise todas as informacoes preenchidas (mao de obra, equipamentos, servicos, fotos)
2. Clique no botao **"Enviar para Aprovacao"**
3. O status do RDO sera alterado para **Pendente de Aprovacao**
4. O gestor/administrador recebera uma notificacao sobre o novo RDO pendente

**Checklist antes de enviar:**

- [ ] Condicoes climaticas informadas para manha e tarde
- [ ] Mao de obra presente registrada com horas trabalhadas
- [ ] Equipamentos utilizados registrados (se houver)
- [ ] Servicos e subatividades com percentuais atualizados
- [ ] Fotos anexadas documentando os servicos executados
- [ ] Comentarios e observacoes preenchidos quando necessario

> **Atencao:** Apos o envio para aprovacao, o RDO **nao podera ser editado** pelo responsavel ate que o gestor aprove ou rejeite o documento.

---

## 6.6. Aprovacao de RDOs

O fluxo de aprovacao e responsabilidade do **gestor** ou **administrador** da empresa.

### Acessando RDOs Pendentes

1. Acesse a lista de RDOs pelo menu lateral
2. Utilize o filtro de status **"Pendente de Aprovacao"**
3. Os RDOs pendentes serao exibidos com destaque visual (badge amarelo)

### Fluxo de Aprovacao

O gestor pode realizar as seguintes acoes em um RDO pendente:

| Acao | Descricao | Resultado |
|------|-----------|-----------|
| **Aprovar** | Confirma que os dados do RDO estao corretos | Status muda para **Aprovado**; progresso da obra e atualizado automaticamente |
| **Reprovar** | Indica que o RDO necessita de correcoes | Status muda para **Reprovado**; RDO retorna para edicao do responsavel |

### Aprovando um RDO

1. Abra o RDO pendente clicando em **"Visualizar"**
2. Revise todos os dados: mao de obra, servicos executados, fotos e observacoes
3. Clique no botao **"Aprovar RDO"**
4. Confirme a aprovacao na caixa de dialogo
5. O sistema registra o aprovador e a data/hora da aprovacao

**Dados registrados na aprovacao:**

- `aprovado_por` — Identificacao do gestor que aprovou
- `data_aprovacao` — Data e hora exata da aprovacao

### Reprovando um RDO

1. Abra o RDO pendente clicando em **"Visualizar"**
2. Identifique os pontos que necessitam correcao
3. Clique no botao **"Reprovar RDO"**
4. Informe o motivo da reprovacao no campo de observacoes
5. O RDO retorna para o status de edicao e o responsavel pode corrigir e reenviar

> **Boas praticas para aprovacao:** Sempre verifique se as fotos anexadas correspondem aos servicos declarados e se os percentuais de conclusao sao coerentes com o historico da obra.

---

## 6.7. Impacto do RDO no Sistema

O RDO nao e apenas um documento de registro — ele e o **motor de atualizacao** de diversos modulos do SIGE. Quando um RDO e aprovado, uma cadeia de atualizacoes automaticas e disparada pelo **EventManager**.

### 6.7.1. Atualizacao Automatica do Progresso da Obra

Ao aprovar um RDO, o sistema:

1. Recalcula o percentual de conclusao de cada servico da obra baseado nas subatividades registradas
2. Atualiza o campo `quantidade_executada` dos servicos reais (`servico_obra_real`)
3. Recalcula o percentual de conclusao global da obra
4. Atualiza o status do servico (Nao Iniciado → Em Andamento → Concluido)

### 6.7.2. Atualizacao Financeira

Os dados de mao de obra e equipamentos alimentam o modulo financeiro:

- **Horas trabalhadas** sao contabilizadas para calculo de custo de mao de obra
- **Equipamentos alugados** sao considerados no custo operacional
- A **produtividade** (quantidade/hora) e registrada no historico de produtividade por servico

### 6.7.3. Atualizacao do Dashboard

O dashboard principal reflete os dados dos RDOs aprovados:

- **KPIs de progresso** sao recalculados com base nos servicos atualizados
- **Graficos de evolucao** apresentam a curva de progresso real vs. planejado
- **Alertas** sao gerados automaticamente quando o progresso esta abaixo do esperado

### 6.7.4. Portal do Cliente

Quando o portal do cliente esta ativo para a obra:

- O progresso atualizado e refletido automaticamente no portal
- As fotos do RDO podem ser disponibilizadas para visualizacao do cliente
- Notificacoes sao enviadas ao cliente sobre atualizacoes relevantes

---

## 6.8. Relatorios de RDO

O SIGE oferece opcoes de geracao de relatorios a partir dos dados coletados nos RDOs.

### 6.8.1. Relatorio Consolidado

O relatorio consolidado apresenta uma visao geral de todos os RDOs de uma obra ou periodo:

| Informacao | Descricao |
|------------|-----------|
| **Resumo de Mao de Obra** | Total de horas trabalhadas por funcionario e por tipo (proprio/terceirizado) |
| **Resumo de Equipamentos** | Equipamentos utilizados com classificacao proprio/alugado |
| **Progresso Acumulado** | Evolucao do percentual de conclusao dos servicos ao longo do tempo |
| **Condicoes Climaticas** | Historico de condicoes climaticas que podem justificar atrasos |
| **Registro Fotografico** | Galeria cronologica de fotos organizadas por data |

**Filtros do relatorio consolidado:**

1. **Periodo** — Selecione data inicio e data fim
2. **Obra** — Filtre por obra especifica
3. **Status** — Inclua apenas RDOs aprovados, todos, ou filtre por status especifico

### 6.8.2. Exportacao Individual em PDF

Cada RDO pode ser exportado individualmente em formato PDF contendo:

- Cabecalho com dados da obra e data do relatorio
- Condicoes climaticas do dia
- Tabela de mao de obra com horas trabalhadas
- Tabela de equipamentos utilizados
- Detalhamento de servicos e subatividades executadas
- Fotos anexadas com descricoes
- Observacoes gerais e assinatura do responsavel

**Para exportar um RDO em PDF:**

1. Acesse o RDO desejado clicando em **"Visualizar"**
2. Clique no botao **"Exportar PDF"** localizado no topo da pagina
3. O arquivo PDF sera gerado e disponibilizado para download

### 6.8.3. Relatorio de Produtividade

O sistema gera relatorios de produtividade baseados nos dados dos RDOs:

| Metrica | Calculo |
|---------|---------|
| **Produtividade por Servico** | Quantidade executada / Horas de mao de obra |
| **Eficiencia da Equipe** | Comparacao entre planejado e realizado |
| **Custo Real vs. Orcado** | Custo de mao de obra real vs. custo orcado por servico |

---

## Resumo do Capitulo 6

O RDO e a peca central do controle de execucao de obras no SIGE. Atraves dele, o responsavel em campo documenta diariamente o que foi realizado, permitindo que gestores acompanhem o progresso em tempo real e tomem decisoes baseadas em dados concretos.

**Pontos-chave:**

1. O RDO registra mao de obra, equipamentos, servicos executados e fotos
2. O preenchimento e otimizado para dispositivos moveis (mobile-first)
3. O fluxo de aprovacao garante a qualidade dos dados registrados
4. A aprovacao do RDO dispara atualizacoes automaticas de progresso, financeiro e dashboard
5. Fotos sao otimizadas automaticamente para WebP, economizando armazenamento
6. Relatorios consolidados e PDFs individuais podem ser gerados a qualquer momento

---

# Capitulo 7 — Modulo Financeiro

## 7.1. Introducao ao Modulo Financeiro

O **Modulo Financeiro** do SIGE e o centro de controle economico da empresa. Ele reune todas as funcionalidades necessarias para gerenciar receitas, despesas, fluxo de caixa, contas a pagar e a receber, alem de oferecer relatorios contabeis completos como DRE (Demonstrativo de Resultado do Exercicio) e balancetes.

### Por que utilizar o Modulo Financeiro?

| Beneficio | Descricao |
|-----------|-----------|
| **Visao consolidada** | Dashboard com KPIs em tempo real: entradas, saidas, saldo e receitas pendentes |
| **Controle de contas** | Gestao completa de contas a pagar (fornecedores) e contas a receber (clientes) |
| **Fluxo de caixa** | Extrato detalhado de todas as movimentacoes financeiras com filtros avancados |
| **Plano de contas** | Estrutura hierarquica de contas contabeis com suporte a partidas dobradas |
| **Centros de custo** | Classificacao de despesas por obra, departamento ou projeto |
| **Integracao com obras** | Custos automaticamente vinculados a obras para controle por projeto |
| **Relatorios contabeis** | DRE, balancete, fluxo de caixa e analise por centro de custo |
| **Lancamentos automaticos** | Lancamentos contabeis gerados automaticamente a partir de movimentacoes |

### Acesso ao Modulo

Para acessar o Modulo Financeiro, utilize o menu de navegacao superior:

**Menu → Financeiro**

O menu Financeiro e um dropdown que apresenta as seguintes opcoes de acesso rapido:

- Dashboard Financeiro
- Contas a Pagar
- Contas a Receber
- Fluxo de Caixa
- Plano de Contas
- Centros de Custo
- Relatorios

A URL de acesso direto ao dashboard financeiro e: `/financeiro`

> **Importante:** O Modulo Financeiro utiliza **partidas dobradas** (debito e credito) para garantir a integridade contabil de todos os lancamentos. Cada movimentacao gera automaticamente os lancamentos contabeis correspondentes.

---

## 7.2. Dashboard Financeiro

### Visao Geral dos KPIs

Ao acessar `/financeiro`, o sistema apresenta um painel com os principais indicadores financeiros do periodo selecionado:

| KPI | Descricao | Exemplo |
|-----|-----------|---------|
| **Total Entradas** | Soma de todas as receitas e recebimentos no periodo | R$ 244.200,00 |
| **Total Saidas** | Soma de todas as despesas e pagamentos no periodo | R$ 15.630,00 |
| **Saldo Periodo** | Diferenca entre entradas e saidas (Entradas - Saidas) | R$ 228.570,00 |
| **Receitas Pendentes** | Total de receitas com status pendente de recebimento | R$ 244.200,00 |

### Grafico de Fluxo de Caixa

Abaixo dos KPIs, o dashboard exibe a secao **Fluxo de Caixa** com um grafico que apresenta a evolucao das entradas e saidas ao longo do periodo. O grafico permite:

1. Visualizar a tendencia de receitas e despesas
2. Identificar periodos de maior ou menor liquidez
3. Comparar entradas vs. saidas de forma visual

### Detalhamento de Custos

O dashboard tambem apresenta um resumo dos custos por categoria:

| Categoria | Descricao |
|-----------|-----------|
| **Alimentacao** | Custos com refeicoes e alimentacao de equipes |
| **Transporte** | Despesas com veiculos, combustivel e deslocamentos |
| **Mao de Obra** | Salarios, encargos e custos com pessoal |
| **Total** | Soma consolidada de todas as categorias |

### Filtros do Dashboard

O dashboard permite filtrar os dados por:

1. **Periodo** — Selecione data inicial e data final para analise
2. **Obra** — Filtre os dados financeiros por obra especifica
3. **Categoria** — Visualize apenas uma categoria de movimentacao

---

## 7.3. Plano de Contas e Centros de Custo

### 7.3.1. Configurando o Plano de Contas

O **Plano de Contas** e a estrutura hierarquica que organiza todas as contas contabeis da empresa. O SIGE utiliza o padrao brasileiro de plano de contas com os seguintes grupos principais:

| Codigo | Grupo | Natureza | Descricao |
|--------|-------|----------|-----------|
| 1.x.xx.xxx | **Ativo** | Devedora | Bens e direitos da empresa |
| 2.x.xx.xxx | **Passivo** | Credora | Obrigacoes e dividas |
| 3.x.xx.xxx | **Patrimonio Liquido** | Credora | Capital e reservas |
| 4.x.xx.xxx | **Receitas** | Credora | Faturamento e ganhos |
| 5.x.xx.xxx | **Despesas** | Devedora | Custos e gastos operacionais |

#### Estrutura Hierarquica

O plano de contas possui **4 niveis** de hierarquia:

```
1           → Grupo (Ativo)
 1.1        → Subgrupo (Ativo Circulante)
  1.1.01    → Conta Sintetica (Caixa e Equivalentes)
   1.1.01.001 → Conta Analitica (Caixa Geral)
```

> **Regra:** Somente contas **analiticas** (ultimo nivel) aceitam lancamentos. Contas sinteticas servem apenas para agrupamento nos relatorios.

#### Cadastrando uma Nova Conta

Para adicionar uma conta ao plano de contas:

1. Acesse **Financeiro → Plano de Contas**
2. Clique no botao **Nova Conta**
3. Preencha os campos obrigatorios:

| Campo | Descricao | Exemplo |
|-------|-----------|---------|
| **Codigo** | Codigo hierarquico unico | 1.1.01.003 |
| **Nome** | Nome descritivo da conta | Banco Bradesco - CC |
| **Tipo** | ATIVO, PASSIVO, PATRIMONIO, RECEITA ou DESPESA | ATIVO |
| **Natureza** | DEVEDORA ou CREDORA | DEVEDORA |
| **Nivel** | Nivel na hierarquia (1 a 4) | 4 |
| **Conta Pai** | Codigo da conta pai na hierarquia | 1.1.01 |
| **Aceita Lancamento** | Se a conta e analitica (aceita lancamentos) | Sim |

4. Clique em **Salvar**

### 7.3.2. Centros de Custo

Os **Centros de Custo** permitem classificar as despesas por area de responsabilidade, facilitando a analise de custos por obra, departamento ou projeto.

#### Tipos de Centro de Custo

| Tipo | Descricao | Exemplo |
|------|-----------|---------|
| **Obra** | Vinculado a uma obra especifica | CC-OBRA-001 - Residencial Solar |
| **Departamento** | Vinculado a um departamento | CC-DEPT-ADM - Administrativo |
| **Projeto** | Para projetos transversais | CC-PROJ-TI - Implantacao ERP |
| **Atividade** | Para atividades especificas | CC-ATIV-TREIN - Treinamentos |

#### Cadastrando um Centro de Custo

1. Acesse **Financeiro → Centros de Custo**
2. Clique em **Novo Centro de Custo**
3. Preencha os campos:

| Campo | Obrigatorio | Descricao |
|-------|:-----------:|-----------|
| **Codigo** | Sim | Codigo unico (ex: CC001) |
| **Nome** | Sim | Nome descritivo do centro de custo |
| **Tipo** | Sim | Obra, Departamento, Projeto ou Atividade |
| **Descricao** | Nao | Detalhamento do centro de custo |
| **Obra** | Nao | Obra associada (quando tipo = Obra) |
| **Departamento** | Nao | Departamento associado (quando tipo = Departamento) |

4. Clique em **Salvar**

> **Dica:** Ao cadastrar uma nova obra no sistema, crie um centro de custo vinculado a ela para facilitar o rastreamento de todas as despesas do projeto.

---

## 7.4. Contas a Pagar

O modulo de **Contas a Pagar** gerencia todas as obrigacoes financeiras com fornecedores, prestadores de servico e demais credores.

### 7.4.1. Lancando Nova Despesa

Para registrar uma nova conta a pagar:

1. Acesse **Financeiro → Contas a Pagar**
2. Clique no botao **Nova Conta a Pagar**
3. Preencha o formulario:

| Campo | Obrigatorio | Descricao |
|-------|:-----------:|-----------|
| **Fornecedor** | Sim | Selecione o fornecedor cadastrado |
| **Numero do Documento** | Nao | Numero da NF, boleto ou recibo |
| **Descricao** | Sim | Descricao detalhada da despesa |
| **Valor Original** | Sim | Valor total do documento (R$) |
| **Data de Emissao** | Sim | Data de emissao do documento |
| **Data de Vencimento** | Sim | Data limite para pagamento |
| **Obra** | Nao | Obra associada a despesa |
| **Conta Contabil** | Nao | Conta do plano de contas para classificacao |
| **Forma de Pagamento** | Nao | Boleto, transferencia, dinheiro, etc. |
| **Observacoes** | Nao | Informacoes complementares |

4. Clique em **Salvar**

> **Importante:** O sistema calcula automaticamente o **saldo** da conta (Valor Original - Valor Pago) e atualiza o status conforme os pagamentos sao registrados.

### 7.4.2. Baixando Pagamento

Para registrar o pagamento (total ou parcial) de uma conta:

1. Na lista de Contas a Pagar, localize a conta desejada
2. Clique no botao **Baixar Pagamento**
3. Informe:
   - **Valor Pago** — Valor efetivamente pago nesta baixa
   - **Data do Pagamento** — Data em que o pagamento foi realizado
   - **Forma de Pagamento** — Meio utilizado para o pagamento
4. Clique em **Confirmar Baixa**

O sistema atualiza automaticamente:

- O **valor pago acumulado** da conta
- O **saldo restante** (Valor Original - Valor Pago)
- O **status** da conta:

| Status | Condicao |
|--------|----------|
| **PENDENTE** | Nenhum pagamento realizado |
| **PARCIAL** | Pagamento parcial efetuado (saldo > 0) |
| **PAGO** | Pagamento integral realizado (saldo = 0) |
| **VENCIDO** | Data de vencimento ultrapassada sem pagamento total |

### 7.4.3. Visualizando Contas a Pagar

A tela de listagem apresenta todas as contas a pagar com as seguintes colunas:

| Coluna | Descricao |
|--------|-----------|
| **Fornecedor** | Nome do fornecedor |
| **Descricao** | Descricao resumida da despesa |
| **Valor Original** | Valor total do documento |
| **Valor Pago** | Total ja pago |
| **Saldo** | Valor restante a pagar |
| **Vencimento** | Data de vencimento |
| **Status** | Situacao atual (Pendente, Parcial, Pago, Vencido) |
| **Acoes** | Visualizar, Editar, Baixar Pagamento |

**Filtros disponiveis:**

1. **Status** — Filtre por Pendente, Parcial, Pago ou Vencido
2. **Fornecedor** — Busque por fornecedor especifico
3. **Periodo de Vencimento** — Filtre por intervalo de datas
4. **Obra** — Exiba contas vinculadas a uma obra especifica

---

## 7.5. Contas a Receber

O modulo de **Contas a Receber** controla todos os valores a receber de clientes, medicoes de obras e demais fontes de receita.

### 7.5.1. Lancando Nova Receita

Para registrar uma nova conta a receber:

1. Acesse **Financeiro → Contas a Receber**
2. Clique no botao **Nova Conta a Receber**
3. Preencha o formulario:

| Campo | Obrigatorio | Descricao |
|-------|:-----------:|-----------|
| **Cliente** | Sim | Nome do cliente |
| **CPF/CNPJ** | Nao | Documento do cliente |
| **Numero do Documento** | Nao | Numero do contrato, NF ou fatura |
| **Descricao** | Sim | Descricao da receita |
| **Valor Original** | Sim | Valor total a receber (R$) |
| **Data de Emissao** | Sim | Data de emissao do documento |
| **Data de Vencimento** | Sim | Data prevista para recebimento |
| **Obra** | Nao | Obra associada a esta receita |
| **Conta Contabil** | Nao | Conta do plano de contas |
| **Forma de Recebimento** | Nao | Transferencia, boleto, cheque, etc. |
| **Observacoes** | Nao | Informacoes complementares |

4. Clique em **Salvar**

### 7.5.2. Baixando Recebimento

Para registrar o recebimento (total ou parcial) de uma conta:

1. Na lista de Contas a Receber, localize a conta desejada
2. Clique no botao **Baixar Recebimento**
3. Informe:
   - **Valor Recebido** — Valor efetivamente recebido
   - **Data do Recebimento** — Data em que o valor foi recebido
   - **Forma de Recebimento** — Meio pelo qual foi recebido
4. Clique em **Confirmar Baixa**

O sistema atualiza automaticamente o valor recebido acumulado, o saldo restante e o status da conta (PENDENTE, PARCIAL ou RECEBIDO).

### 7.5.3. Visualizando Contas a Receber

A tela de listagem exibe todas as contas a receber com colunas analogas as de Contas a Pagar:

| Coluna | Descricao |
|--------|-----------|
| **Cliente** | Nome do cliente |
| **Descricao** | Descricao resumida da receita |
| **Valor Original** | Valor total a receber |
| **Valor Recebido** | Total ja recebido |
| **Saldo** | Valor restante a receber |
| **Vencimento** | Data de vencimento |
| **Status** | Situacao atual (Pendente, Parcial, Recebido, Vencido) |
| **Acoes** | Visualizar, Editar, Baixar Recebimento |

**Filtros disponiveis:**

1. **Status** — Filtre por Pendente, Parcial, Recebido ou Vencido
2. **Cliente** — Busque por cliente especifico
3. **Periodo de Vencimento** — Filtre por intervalo de datas
4. **Obra** — Exiba contas vinculadas a uma obra especifica

---

## 7.6. Fluxo de Caixa

O **Fluxo de Caixa** apresenta o extrato completo de todas as movimentacoes financeiras da empresa, consolidando entradas e saidas em uma visao unificada.

### Acessando o Fluxo de Caixa

Acesse **Financeiro → Fluxo de Caixa** ou visualize a secao Fluxo de Caixa diretamente no dashboard financeiro em `/financeiro`.

### Estrutura do Extrato

Cada movimentacao no fluxo de caixa registra:

| Campo | Descricao |
|-------|-----------|
| **Data** | Data da movimentacao |
| **Tipo** | ENTRADA ou SAIDA |
| **Categoria** | Classificacao: receita, custo_obra, custo_veiculo, alimentacao, salario |
| **Descricao** | Detalhamento da movimentacao |
| **Valor** | Valor da movimentacao (R$) |
| **Obra** | Obra vinculada (quando aplicavel) |
| **Centro de Custo** | Centro de custo associado |

### Filtros e Analise

O fluxo de caixa oferece filtros avancados para analise:

1. **Periodo** — Selecione intervalo de datas (data inicial e final)
2. **Tipo de Movimento** — Filtre por Entradas, Saidas ou Todos
3. **Categoria** — Selecione uma categoria especifica
4. **Obra** — Filtre movimentacoes por obra

### Analise de Entradas vs. Saidas

O sistema apresenta um resumo comparativo ao final do extrato:

| Indicador | Descricao |
|-----------|-----------|
| **Total de Entradas** | Soma de todas as movimentacoes do tipo ENTRADA no periodo |
| **Total de Saidas** | Soma de todas as movimentacoes do tipo SAIDA no periodo |
| **Saldo do Periodo** | Diferenca entre total de entradas e total de saidas |
| **Saldo Acumulado** | Saldo progressivo considerando movimentacoes anteriores |

> **Dica:** Utilize o grafico de fluxo de caixa no dashboard para identificar rapidamente periodos com saldo negativo e antecipar necessidades de capital de giro.

### Contas Bancarias

O modulo tambem permite o cadastro de contas bancarias da empresa para controle de saldos:

| Campo | Descricao |
|-------|-----------|
| **Nome do Banco** | Instituicao financeira |
| **Agencia** | Numero da agencia |
| **Conta** | Numero da conta corrente |
| **Tipo de Conta** | Corrente, Poupanca, etc. |
| **Saldo Inicial** | Saldo na data de implantacao |
| **Saldo Atual** | Saldo atualizado automaticamente |

---

## 7.7. Relatorios Financeiros

O SIGE oferece um conjunto completo de relatorios financeiros para suporte a tomada de decisao.

### DRE — Demonstrativo de Resultado do Exercicio

O **DRE** apresenta o resultado economico da empresa em um periodo determinado, detalhando receitas, custos e despesas:

| Linha do DRE | Descricao |
|--------------|-----------|
| **(+) Receita Bruta** | Total de receitas no periodo |
| **(-) Impostos sobre Vendas** | Tributos incidentes sobre o faturamento |
| **(=) Receita Liquida** | Receita Bruta - Impostos |
| **(-) Custo Total** | Custos diretos de producao/servicos |
| **(=) Lucro Bruto** | Receita Liquida - Custo Total |
| **(-) Despesas Operacionais** | Despesas administrativas, comerciais, etc. |
| **(=) Lucro Operacional** | Lucro Bruto - Despesas Operacionais |
| **(=) Lucro Liquido** | Resultado final do periodo |

Para gerar o DRE:

1. Acesse **Financeiro → Relatorios → DRE**
2. Selecione o **mes/ano de referencia**
3. Clique em **Gerar Relatorio**

### Relatorio de Fluxo de Caixa Contabil

O relatorio de fluxo de caixa contabil classifica as movimentacoes em tres categorias conforme normas contabeis:

| Categoria | Descricao | Exemplos |
|-----------|-----------|----------|
| **Operacional** | Atividades do dia a dia da empresa | Receitas de obras, pagamento de salarios |
| **Investimento** | Aquisicao e venda de ativos | Compra de equipamentos, venda de veiculos |
| **Financiamento** | Captacao e pagamento de recursos | Emprestimos, aportes de capital |

### Relatorio de Contas a Pagar/Receber

Relatorios detalhados de contas a pagar e a receber com opcoes de filtro por:

- **Status** — Pendentes, Pagas/Recebidas, Vencidas
- **Periodo de Vencimento** — Intervalo de datas
- **Fornecedor/Cliente** — Filtro por entidade
- **Obra** — Filtro por projeto

### Despesas por Centro de Custo

Este relatorio agrupa todas as despesas por centro de custo, permitindo:

1. Identificar centros de custo com maior consumo de recursos
2. Comparar orcado vs. realizado por obra
3. Analisar a distribuicao percentual de despesas
4. Acompanhar a evolucao mensal dos custos

| Coluna | Descricao |
|--------|-----------|
| **Centro de Custo** | Codigo e nome do centro de custo |
| **Tipo** | Obra, Departamento, Projeto ou Atividade |
| **Total Despesas** | Soma das despesas no periodo |
| **% do Total** | Participacao percentual no total geral |
| **Variacao** | Comparativo com periodo anterior |

### Balancete de Verificacao

O **Balancete** apresenta os saldos de todas as contas contabeis em um periodo:

| Coluna | Descricao |
|--------|-----------|
| **Codigo** | Codigo da conta no plano de contas |
| **Nome da Conta** | Descricao da conta contabil |
| **Saldo Anterior** | Saldo no inicio do periodo |
| **Debitos** | Total de debitos no periodo |
| **Creditos** | Total de creditos no periodo |
| **Saldo Atual** | Saldo ao final do periodo |

> **Nota:** O balancete e gerado automaticamente a partir dos lancamentos contabeis registrados pelo sistema de partidas dobradas.

### Exportacao de Relatorios

Todos os relatorios financeiros podem ser exportados nos seguintes formatos:

1. **PDF** — Para impressao e arquivo fisico
2. **Tela** — Visualizacao direta no navegador com opcao de impressao

> **Integracao SPED:** O SIGE suporta a geracao de arquivos no formato SPED Contabil para transmissao a Receita Federal, contemplando todos os lancamentos contabeis do periodo.

---

# Capitulo 8 — Módulos Avançados

**SIGE - Estruturas do Vale (EnterpriseSync)**
Manual do Usuário — Versão 9.0

---

## 8.1. Módulo de Propostas Comerciais

O módulo de **Propostas Comerciais** do SIGE permite criar, gerenciar e acompanhar propostas de orçamento enviadas a clientes e prospects. Ele integra-se diretamente com o módulo de Obras, facilitando a conversão de propostas aprovadas em novos projetos.

### 8.1.1. Visão Geral

| Funcionalidade | Descrição |
|---|---|
| Criação de propostas | Formulário completo com dados do cliente, serviços, valores e condições |
| Templates reutilizáveis | Modelos pré-configurados para agilizar a elaboração de novas propostas |
| Geração de PDF | Exportação automática da proposta em formato PDF profissional |
| Portal do cliente | Acesso externo via token seguro para o cliente visualizar e aprovar propostas |
| Controle de validade | Gestão de prazos de validade com alertas automáticos de expiração |
| Histórico de versões | Registro de todas as alterações realizadas em cada proposta |

### 8.1.2. Criando uma Nova Proposta

Para criar uma nova proposta comercial:

1. Acesse **Propostas** no menu de navegação superior.
2. Clique no botão **"Nova Proposta"**.
3. Preencha os campos do formulário:

| Campo | Obrigatório | Descrição |
|---|:---:|---|
| **Título** | Sim | Título descritivo da proposta (ex.: "Construção Residencial - Lote 15") |
| **Cliente** | Sim | Nome do cliente ou empresa destinatária |
| **E-mail do Cliente** | Não | E-mail para envio da proposta e acesso ao portal |
| **Telefone do Cliente** | Não | Telefone de contato |
| **Descrição** | Não | Descrição detalhada do escopo da proposta |
| **Valor Total** | Sim | Valor total da proposta em R$ |
| **Data de Validade** | Sim | Data limite para aceitação da proposta |
| **Condições de Pagamento** | Não | Termos e condições de pagamento |
| **Observações** | Não | Informações adicionais ou ressalvas |

4. Na seção **Itens da Proposta**, adicione os serviços e materiais inclusos:
   - Descrição do item
   - Quantidade
   - Unidade de medida
   - Valor unitário
   - Valor total (calculado automaticamente)

5. Clique em **"Salvar"** para criar a proposta como rascunho.

### 8.1.3. Templates de Propostas

O sistema permite criar e utilizar templates para padronizar e agilizar a criação de propostas:

1. Acesse **Propostas → Templates**.
2. Crie um novo template com itens pré-definidos, textos padrão e condições comerciais.
3. Ao criar uma nova proposta, selecione o template desejado para pré-preencher os campos automaticamente.

### 8.1.4. Geração de PDF

Cada proposta pode ser exportada em formato PDF profissional:

1. Acesse a proposta desejada.
2. Clique no botão **"Gerar PDF"**.
3. O sistema gerará um documento formatado contendo:
   - Cabeçalho com logo da empresa e dados de contato
   - Dados do cliente
   - Escopo detalhado dos serviços
   - Tabela de itens com valores
   - Condições de pagamento
   - Prazo de validade
   - Espaço para assinatura

### 8.1.5. Portal do Cliente com Token de Acesso

O Portal do Cliente permite que o destinatário da proposta visualize e interaja com o documento sem necessidade de login no sistema:

1. Ao criar ou editar uma proposta, marque a opção **"Ativar Portal do Cliente"**.
2. Informe o e-mail do cliente.
3. O sistema gera automaticamente um **token de acesso seguro** (URL única).
4. O link é enviado ao cliente por e-mail.
5. O cliente pode:
   - Visualizar todos os detalhes da proposta
   - Aprovar ou solicitar alterações
   - Baixar o PDF da proposta
   - Acompanhar o andamento (quando vinculada a uma obra)

> **Segurança:** O token de acesso é único e criptografado. Ele pode ser revogado ou regenerado a qualquer momento pelo administrador.

### 8.1.6. Ciclo de Vida da Proposta

| Status | Descrição | Ação Disponível |
|---|---|---|
| **Rascunho** | Proposta em elaboração | Editar, Enviar |
| **Enviada** | Proposta enviada ao cliente | Aguardar resposta |
| **Aprovada** | Proposta aceita pelo cliente | Converter em Obra |
| **Rejeitada** | Proposta recusada pelo cliente | Criar nova versão |
| **Expirada** | Prazo de validade vencido | Renovar ou arquivar |

---

## 8.2. Módulo de Alimentação

O módulo de **Alimentação** do SIGE gerencia o controle de refeições fornecidas aos funcionários nas obras, permitindo o acompanhamento de custos e a gestão de fornecedores de alimentação.

### 8.2.1. Visão Geral

| Funcionalidade | Descrição |
|---|---|
| Registro de refeições | Controle diário de refeições servidas por obra e por funcionário |
| Tipos de refeição | Café da manhã, almoço, jantar, lanche e marmita |
| Custo por obra | Rateio automático dos custos de alimentação por obra |
| Fornecedores | Cadastro e gestão de fornecedores de alimentação |
| Relatórios | Relatórios de consumo e custos por período, obra e funcionário |

### 8.2.2. Registrando Refeições

Para registrar refeições fornecidas:

1. Acesse **Alimentação** no menu de navegação.
2. Clique em **"Novo Registro"**.
3. Preencha os campos:

| Campo | Obrigatório | Descrição |
|---|:---:|---|
| **Data** | Sim | Data da refeição |
| **Obra** | Sim | Obra onde a refeição foi servida |
| **Tipo de Refeição** | Sim | Café da manhã, Almoço, Jantar, Lanche ou Marmita |
| **Quantidade** | Sim | Número de refeições servidas |
| **Valor Unitário** | Sim | Custo por refeição (R$) |
| **Fornecedor** | Não | Fornecedor responsável pela refeição |
| **Funcionários** | Não | Funcionários que receberam a refeição |
| **Observações** | Não | Informações adicionais |

4. Clique em **"Salvar"**.

### 8.2.3. Custo por Obra

O sistema calcula automaticamente o custo total de alimentação por obra:

- **Custo diário** — Soma das refeições registradas no dia para a obra
- **Custo mensal** — Acumulado do mês para a obra
- **Custo por funcionário** — Média de custo de alimentação por colaborador alocado

Esses valores são automaticamente integrados ao **Dashboard da Obra** e ao **Módulo Financeiro**, aparecendo na categoria "Alimentação" dos custos operacionais.

### 8.2.4. Relatórios de Alimentação

| Relatório | Descrição |
|---|---|
| Consumo por Obra | Total de refeições e custos por obra no período |
| Consumo por Funcionário | Detalhamento individual de refeições recebidas |
| Custos por Tipo de Refeição | Distribuição de custos entre café, almoço, jantar, etc. |
| Evolução Mensal | Gráfico de evolução dos custos de alimentação ao longo dos meses |

---

## 8.3. Módulo de Almoxarifado

O módulo de **Almoxarifado** gerencia todo o controle de materiais, ferramentas, EPIs (Equipamentos de Proteção Individual) e insumos utilizados nas obras e operações da empresa.

### 8.3.1. Visão Geral

| Funcionalidade | Descrição |
|---|---|
| Cadastro de materiais | Registro completo de materiais com código, descrição, unidade e estoque mínimo |
| Controle de ferramentas | Gestão de ferramentas com controle de empréstimo e devolução |
| Gestão de EPIs | Controle de equipamentos de proteção individual por funcionário |
| Fornecedores | Cadastro de fornecedores com histórico de compras |
| Movimentações | Registro de entradas, saídas e devoluções de materiais |
| Inventário | Controle de estoque com alertas de estoque mínimo |

### 8.3.2. Cadastrando Materiais

Para cadastrar um novo material no almoxarifado:

1. Acesse **Almoxarifado → Materiais** no menu de navegação.
2. Clique em **"Novo Material"**.
3. Preencha os campos:

| Campo | Obrigatório | Descrição |
|---|:---:|---|
| **Código** | Sim | Código interno do material (ex.: MAT-001) |
| **Descrição** | Sim | Nome/descrição do material |
| **Categoria** | Sim | Categoria: Material de Construção, Ferramenta, EPI, Consumível, etc. |
| **Unidade de Medida** | Sim | Unidade: un, kg, m, m², m³, litro, caixa, pacote |
| **Estoque Mínimo** | Não | Quantidade mínima para alerta de reposição |
| **Estoque Atual** | Não | Quantidade atual em estoque |
| **Valor Unitário** | Não | Custo médio por unidade (R$) |
| **Localização** | Não | Local de armazenamento no almoxarifado |
| **Fornecedor Padrão** | Não | Fornecedor preferencial para reposição |

4. Clique em **"Salvar"**.

### 8.3.3. Ferramentas e EPIs

O sistema possui categorias específicas para controle de ferramentas e EPIs:

**Ferramentas:**
- Registro de patrimônio com número de série
- Controle de empréstimo por funcionário
- Histórico de manutenção e vida útil
- Alerta de devolução pendente

**EPIs:**
- Controle de entrega por funcionário com assinatura digital
- Registro de CA (Certificado de Aprovação) e validade
- Controle de periodicidade de troca
- Relatório de conformidade com NR-6

### 8.3.4. Fornecedores

O cadastro de fornecedores do almoxarifado inclui:

| Campo | Descrição |
|---|---|
| **Razão Social** | Nome oficial do fornecedor |
| **CNPJ** | Cadastro Nacional de Pessoa Jurídica |
| **Contato** | Nome da pessoa de contato |
| **Telefone** | Telefone comercial |
| **E-mail** | E-mail para pedidos e comunicação |
| **Endereço** | Endereço completo |
| **Materiais Fornecidos** | Lista de materiais que o fornecedor oferece |
| **Condições Comerciais** | Prazos de pagamento, descontos, frete |

### 8.3.5. Movimentação de Materiais

O fluxo de materiais no almoxarifado é controlado por três tipos de movimentação:

| Tipo | Descrição | Impacto no Estoque |
|---|---|---|
| **Entrada** | Recebimento de materiais de fornecedores ou transferências | Aumenta o estoque |
| **Saída** | Retirada de materiais para uso em obras ou setores | Diminui o estoque |
| **Devolução** | Retorno de materiais não utilizados ou ferramentas emprestadas | Aumenta o estoque |

**Registrando uma movimentação:**

1. Acesse **Almoxarifado → Movimentações**.
2. Clique em **"Nova Movimentação"**.
3. Selecione o tipo (Entrada, Saída ou Devolução).
4. Informe:
   - Material ou ferramenta
   - Quantidade
   - Obra de destino (para saídas)
   - Funcionário responsável
   - Nota fiscal (para entradas)
   - Observações
5. Clique em **"Confirmar"**.

O sistema atualiza automaticamente o saldo de estoque e registra o histórico completo da movimentação para rastreabilidade.

### 8.3.6. Alertas do Almoxarifado

O sistema gera alertas automáticos para:

- Materiais com estoque abaixo do mínimo configurado
- Ferramentas com devolução pendente há mais de X dias
- EPIs com validade próxima do vencimento
- Pedidos de compra pendentes de aprovação

---

## 8.4. Módulo de API

O SIGE disponibiliza uma **API RESTful** que permite a integração com aplicativos móveis, sistemas externos e automações personalizadas.

### 8.4.1. Visão Geral da API

| Característica | Descrição |
|---|---|
| **Protocolo** | RESTful sobre HTTPS |
| **Formato** | JSON (entrada e saída) |
| **Autenticação** | Token Bearer (JWT) |
| **Versionamento** | Prefixo `/api/v1/` |
| **Rate Limiting** | 100 requisições por minuto por token |
| **Documentação** | Disponível em `/api/docs` |

### 8.4.2. Autenticação por Token

Para utilizar a API, é necessário obter um token de autenticação:

**Endpoint de autenticação:**
```
POST /api/v1/auth/login
```

**Corpo da requisição (JSON):**
```json
{
  "username": "seu_usuario",
  "password": "sua_senha"
}
```

**Resposta de sucesso:**
```json
{
  "token": "eyJhbGciOiJIUzI1NiIs...",
  "expires_in": 86400,
  "user": {
    "id": 1,
    "nome": "Administrador",
    "tipo": "ADMIN"
  }
}
```

**Utilizando o token:**

Inclua o token no cabeçalho `Authorization` de todas as requisições subsequentes:
```
Authorization: Bearer eyJhbGciOiJIUzI1NiIs...
```

### 8.4.3. Endpoints Principais

| Recurso | Método | Endpoint | Descrição |
|---|---|---|---|
| **Funcionários** | GET | `/api/v1/funcionarios` | Lista todos os funcionários |
| **Funcionários** | GET | `/api/v1/funcionarios/<id>` | Detalhes de um funcionário |
| **Funcionários** | POST | `/api/v1/funcionarios` | Cria novo funcionário |
| **Obras** | GET | `/api/v1/obras` | Lista todas as obras |
| **Obras** | GET | `/api/v1/obras/<id>` | Detalhes de uma obra |
| **Ponto** | POST | `/api/v1/ponto/registrar` | Registra ponto de funcionário |
| **RDOs** | GET | `/api/v1/rdos` | Lista todos os RDOs |
| **RDOs** | POST | `/api/v1/rdos` | Cria novo RDO |
| **Veículos** | GET | `/api/v1/veiculos` | Lista veículos da frota |
| **Financeiro** | GET | `/api/v1/financeiro/resumo` | Resumo financeiro do período |
| **Serviços** | GET | `/api/v1/servicos` | Lista serviços cadastrados |

### 8.4.4. Integração Mobile

A API foi projetada para suportar aplicativos móveis nativos e PWA (Progressive Web Apps), oferecendo:

- Endpoints otimizados para conexões de baixa largura de banda
- Suporte a upload de fotos comprimidas para registro de ponto e RDO
- Notificações push via webhooks configuráveis
- Modo offline com sincronização posterior

### 8.4.5. Integração com Sistemas Externos

O SIGE permite integração com sistemas de terceiros através da API:

| Sistema | Tipo de Integração | Descrição |
|---|---|---|
| **ERP** | Bidirecional | Sincronização de dados financeiros e de funcionários |
| **Contabilidade** | Exportação | Envio de lançamentos contábeis no formato SPED |
| **eSocial** | Exportação | Geração de eventos de admissão, ponto e folha |
| **Folha de Pagamento** | Exportação | Exportação de dados de horas e cálculos trabalhistas |
| **BI (Business Intelligence)** | Leitura | Acesso a dados consolidados para dashboards externos |

---

## 8.5. Módulo de Relatórios

O módulo de **Relatórios** centraliza todas as opções de geração de relatórios do SIGE, oferecendo uma interface unificada com filtros globais e múltiplos formatos de exportação.

### 8.5.1. Central de Relatórios

Acesse **Relatórios** no menu de navegação para visualizar a central de relatórios. A tela principal organiza os relatórios por categoria:

| Categoria | Relatórios Disponíveis |
|---|---|
| **Funcionários** | Folha de ponto, horas extras, absenteísmo, custo de mão de obra |
| **Obras** | Resumo executivo, custos por obra, progresso, cronograma |
| **Financeiro** | DRE, fluxo de caixa, contas a pagar/receber, balancete |
| **Veículos** | Custos por veículo, utilização da frota, quilometragem |
| **Alimentação** | Consumo por obra, custo por funcionário, evolução mensal |
| **Almoxarifado** | Posição de estoque, movimentações, materiais críticos |
| **RDO** | Consolidado por obra, produtividade, condições climáticas |
| **Propostas** | Pipeline comercial, taxa de conversão, valor médio |

### 8.5.2. Filtros Globais

Todos os relatórios compartilham um conjunto de filtros globais que podem ser combinados:

| Filtro | Descrição |
|---|---|
| **Período** | Data de início e data de fim para delimitação temporal |
| **Obra** | Filtra dados por uma obra específica ou todas as obras |
| **Departamento** | Filtra por departamento da empresa |
| **Funcionário** | Filtra por um funcionário específico |
| **Status** | Filtra por status do registro (ativo, concluído, pendente, etc.) |

### 8.5.3. Exportação em PDF e Excel

Todos os relatórios podem ser exportados nos seguintes formatos:

| Formato | Descrição | Uso Recomendado |
|---|---|---|
| **PDF** | Documento formatado para impressão e arquivo | Relatórios gerenciais, apresentações, arquivo físico |
| **Excel (XLSX)** | Planilha com dados estruturados em colunas | Análises detalhadas, gráficos personalizados, manipulação de dados |
| **Tela** | Visualização direta no navegador | Consultas rápidas, impressão via navegador |

**Para exportar um relatório:**

1. Selecione o relatório desejado na central de relatórios.
2. Configure os filtros (período, obra, departamento, etc.).
3. Clique em **"Gerar Relatório"** para visualizar na tela.
4. Utilize os botões **"Exportar PDF"** ou **"Exportar Excel"** para download do arquivo.

---

## 8.6. Módulo de Administração

O módulo de **Administração** é acessível exclusivamente por usuários do tipo **SUPER_ADMIN** e oferece ferramentas avançadas para gestão, diagnóstico e monitoramento do sistema como um todo.

### 8.6.1. Painel Super Admin

O painel do Super Admin (URL: `/super_admin_dashboard`) é o centro de controle global do sistema, oferecendo visão sobre todos os tenants (empresas) cadastrados.

| Funcionalidade | Descrição |
|---|---|
| **Gestão de Tenants** | Visualizar, criar e gerenciar empresas (administradores) cadastrados no sistema |
| **Monitoramento Global** | KPIs consolidados de todos os tenants: total de usuários, obras, RDOs, etc. |
| **Auditoria** | Logs de ações críticas realizadas por todos os usuários do sistema |
| **Configurações Globais** | Parâmetros que afetam todo o sistema (rate limiting, tamanhos de upload, etc.) |

### 8.6.2. Diagnósticos do Sistema

O módulo de diagnósticos permite verificar a saúde e o desempenho do sistema:

| Diagnóstico | Descrição |
|---|---|
| **Status do Banco de Dados** | Verifica conexão, latência e integridade do PostgreSQL |
| **Uso de Armazenamento** | Espaço utilizado por uploads (fotos de ponto, RDO, propostas) |
| **Performance** | Tempo de resposta das principais rotas e endpoints |
| **Integridade de Dados** | Verificação de consistência entre tabelas relacionadas |
| **Sessões Ativas** | Número de usuários conectados simultaneamente |
| **Logs de Erro** | Registro de erros e exceções ocorridos no sistema |

### 8.6.3. Saúde do Sistema (Health Check)

O endpoint de health check permite monitorar a disponibilidade do sistema:

```
GET /api/health
```

**Resposta:**
```json
{
  "status": "healthy",
  "database": "connected",
  "uptime": "72h 15m",
  "version": "9.0",
  "timestamp": "2026-02-23T10:30:00Z"
}
```

### 8.6.4. Gestão de Backups

O módulo de administração oferece ferramentas para gestão de backups:

| Funcionalidade | Descrição |
|---|---|
| **Backup Manual** | Gerar backup completo do banco de dados sob demanda |
| **Backup Agendado** | Configurar rotina automática de backup (diário, semanal) |
| **Restauração** | Restaurar banco de dados a partir de um backup anterior |
| **Histórico** | Visualizar lista de backups realizados com data e tamanho |

> **Importante:** Recomenda-se configurar backups automáticos diários e manter pelo menos 30 dias de histórico. Armazene os backups em local separado do servidor de produção para proteção contra perda de dados.

---

# Capitulo 9 — Suporte e Considerações Finais

**SIGE - Estruturas do Vale (EnterpriseSync)**
Manual do Usuário — Versão 9.0

---

## 9.1. Troubleshooting

Esta seção apresenta os problemas mais comuns encontrados pelos usuários do SIGE e suas respectivas soluções. Consulte a tabela abaixo antes de entrar em contato com o suporte técnico.

### Problemas Comuns e Soluções

| Problema | Causa Provável | Solução |
|---|---|---|
| **Não consigo fazer login** | Credenciais incorretas ou usuário desativado | Verifique se o username/e-mail e senha estão corretos. Confirme com o administrador se o usuário está ativo. Tente recuperar a senha ou solicite uma redefinição ao ADMIN. |
| **Mensagem "Email/Username ou senha inválidos"** | Username ou senha digitados incorretamente | Verifique maiúsculas/minúsculas na senha. Tente usar o e-mail em vez do username (ou vice-versa). Limpe o cache do navegador. |
| **Sistema muito lento** | Alto volume de dados ou conexão de rede instável | Verifique a conexão de internet. Tente acessar em outro navegador. Reduza o período do filtro de datas. Contate o administrador para verificar o desempenho do servidor. |
| **Reconhecimento facial falha constantemente** | Fotos cadastradas em condições diferentes da captura | Cadastre novas fotos faciais com iluminação semelhante ao ambiente de registro de ponto. Certifique-se de que a câmera está limpa. Evite contraluz. Cadastre pelo menos 3 fotos diferentes. |
| **Reconhecimento facial rejeita funcionário válido** | Distância facial acima do limiar (0.40) | Adicione mais fotos ao cadastro facial do funcionário. Tente em condições de melhor iluminação. Verifique se o funcionário mudou de aparência (barba, óculos, etc.) e atualize as fotos. |
| **RDO não salva / erro ao salvar** | Campos obrigatórios não preenchidos ou RDO duplicado | Verifique se todos os campos obrigatórios estão preenchidos (Obra e Data são obrigatórios). Confirme que não existe outro RDO para a mesma obra na mesma data. |
| **RDO não pode ser editado** | RDO com status "Pendente de Aprovação" ou "Aprovado" | Apenas RDOs com status "Rascunho" ou "Em Elaboração" podem ser editados. Solicite ao gestor que reprove o RDO para permitir a edição. |
| **Progresso da obra não atualiza** | RDO não foi aprovado pelo gestor | O progresso da obra só é atualizado quando o RDO é aprovado. Solicite ao gestor que aprove os RDOs pendentes. |
| **Discrepância nos valores financeiros** | Lançamentos duplicados ou período de filtro incorreto | Verifique o período selecionado nos filtros. Confira se não há lançamentos duplicados. Revise os centros de custo associados. Compare com o extrato de fluxo de caixa. |
| **Contas a pagar/receber com status incorreto** | Baixas não registradas ou valores incorretos | Verifique se todos os pagamentos/recebimentos foram baixados corretamente. Confira os valores de cada baixa. O status é calculado automaticamente pelo sistema. |
| **Fotos do RDO não carregam** | Erro no upload ou formato não suportado | Verifique se a foto está em formato JPG, PNG ou WebP. O tamanho máximo é de 10 MB por imagem. Tente capturar a foto novamente. |
| **Geolocalização não funciona** | GPS desativado ou permissão negada no navegador | Ative o GPS/localização do dispositivo. Conceda permissão de localização ao navegador. Verifique se a obra possui coordenadas cadastradas (latitude e longitude). |
| **Relatório PDF em branco** | Sem dados no período selecionado | Verifique se existem dados para o período e filtros selecionados. Tente ampliar o intervalo de datas. |
| **Erro "500 Internal Server Error"** | Erro interno do servidor | Tente novamente em alguns minutos. Se persistir, contate o suporte técnico informando a URL, o horário e a ação que estava realizando. |
| **Usuário não aparece na lista** | Filtro de status ativo ou busca restritiva | Verifique se o filtro de status não está ocultando usuários inativos. Limpe o campo de busca e tente novamente. |
| **Dados de outro tenant aparecendo** | Erro de configuração do admin_id | Contate o suporte técnico imediatamente. Este é um problema crítico de isolamento de dados que deve ser resolvido com urgência. |

### Passos Gerais para Resolução

1. **Atualize a página** — Pressione `Ctrl+F5` (ou `Cmd+Shift+R` no Mac) para forçar a atualização completa.
2. **Limpe o cache** — Acesse as configurações do navegador e limpe o cache e cookies.
3. **Tente outro navegador** — Teste em Chrome, Firefox ou Edge para descartar problemas de compatibilidade.
4. **Verifique a conexão** — Confirme que a internet está funcionando e estável.
5. **Consulte o administrador** — Se o problema persistir, informe ao administrador do sistema com detalhes do erro.

---

## 9.2. Boas Práticas

Adotar boas práticas no uso diário do SIGE garante a qualidade dos dados, a eficiência operacional e a confiabilidade das informações gerenciais.

### 9.2.1. Rotinas Diárias

| Prática | Descrição | Responsável |
|---|---|---|
| **Registrar ponto diariamente** | Todos os funcionários devem registrar entrada e saída todos os dias | Funcionários / Gestores |
| **Preencher RDOs no mesmo dia** | Registre o RDO no próprio dia da obra para maior precisão dos dados | Gestores de Equipe |
| **Aprovar RDOs pendentes** | Revise e aprove os RDOs no final de cada dia ou início do dia seguinte | Administradores |
| **Verificar o Dashboard** | Acesse o Dashboard no início do expediente para acompanhar os KPIs | Administradores |
| **Registrar refeições** | Lance as refeições fornecidas diariamente no módulo de Alimentação | Responsáveis pela alimentação |

### 9.2.2. Rotinas Semanais

| Prática | Descrição | Responsável |
|---|---|---|
| **Revisar custos das obras** | Compare orçado vs. realizado e identifique desvios | Administradores |
| **Atualizar alocação de equipes** | Verifique se as equipes estão corretamente alocadas às obras | Gestores |
| **Conferir movimentações de almoxarifado** | Valide entradas e saídas de materiais registradas na semana | Almoxarifes |
| **Verificar contas a pagar** | Confira vencimentos da semana seguinte e programe pagamentos | Financeiro |
| **Atualizar quilometragem dos veículos** | Confirme que os registros de uso estão atualizados | Motoristas / Gestores |

### 9.2.3. Rotinas Mensais

| Prática | Descrição | Responsável |
|---|---|---|
| **Gerar relatórios consolidados** | Emita relatórios de funcionários, obras e financeiro do mês | Administradores |
| **Conferir folha de pagamento** | Valide horas trabalhadas, extras, faltas e DSR calculados pelo sistema | RH / Administradores |
| **Realizar backup manual** | Gere um backup completo do banco de dados e armazene em local seguro | Super Admin / TI |
| **Revisar propostas comerciais** | Acompanhe propostas pendentes, expiradas e oportunidades de follow-up | Comercial |
| **Atualizar dados cadastrais** | Revise e atualize dados de funcionários, veículos e fornecedores | Administradores |
| **Inventário de almoxarifado** | Realize contagem física e compare com o saldo do sistema | Almoxarifes |

### 9.2.4. Dicas Gerais

1. **Mantenha os cadastros atualizados** — Dados desatualizados comprometem a qualidade dos relatórios e KPIs.
2. **Utilize senhas fortes** — Combine letras, números e caracteres especiais. Troque as senhas periodicamente.
3. **Treine os usuários** — Garanta que todos os colaboradores conheçam as funcionalidades que precisam utilizar.
4. **Documente processos** — Registre os procedimentos operacionais padrão da empresa no uso do sistema.
5. **Utilize filtros e relatórios** — Explore os filtros avançados e relatórios para tomar decisões baseadas em dados.
6. **Faça backups regulares** — Nunca dependa de um único ponto de armazenamento para dados críticos.
7. **Monitore alertas** — Preste atenção aos alertas do Dashboard e do almoxarifado para agir preventivamente.
8. **Atualize fotos faciais** — Quando funcionários mudam de aparência, atualize as fotos de reconhecimento.
9. **Registre observações nos RDOs** — Comentários detalhados facilitam a análise futura e a resolução de disputas.
10. **Vincule custos às obras** — Sempre associe despesas a obras específicas para um controle financeiro preciso.

---

## 9.3. Contato do Suporte

Para suporte técnico ou dúvidas sobre o sistema SIGE EnterpriseSync, utilize os canais abaixo:

### Canais de Atendimento

| Canal | Informação | Horário |
|---|---|---|
| **E-mail** | [suporte@enterprisesync.com.br] | Segunda a Sexta, 08:00 - 18:00 |
| **Telefone** | [+55 (XX) XXXX-XXXX] | Segunda a Sexta, 08:00 - 18:00 |
| **WhatsApp** | [+55 (XX) XXXXX-XXXX] | Segunda a Sexta, 08:00 - 18:00 |
| **Portal de Suporte** | [https://suporte.enterprisesync.com.br] | 24 horas (registro de chamados) |

### Níveis de Suporte

| Nível | Descrição | SLA |
|---|---|---|
| **Crítico** | Sistema indisponível ou perda de dados | Resposta em até 1 hora |
| **Alto** | Funcionalidade principal inoperante | Resposta em até 4 horas |
| **Médio** | Problema parcial que não impede o uso | Resposta em até 8 horas |
| **Baixo** | Dúvida, sugestão ou melhoria | Resposta em até 24 horas |

### Informações para o Chamado

Ao entrar em contato com o suporte, tenha em mãos:

1. **Nome do usuário** e **tipo de perfil** (ADMIN, GESTOR, etc.)
2. **URL da página** onde o problema ocorreu
3. **Descrição detalhada** do problema ou dúvida
4. **Passos para reprodução** (o que foi feito antes do erro)
5. **Mensagem de erro** exibida (se houver)
6. **Print da tela** com o erro visível
7. **Navegador e dispositivo** utilizados (ex.: Chrome 120, Windows 11)

> **Nota:** Os dados de contato acima são placeholders. Substitua pelas informações reais da equipe de suporte da sua organização.

---

## 9.4. Glossário

Relação dos principais termos e siglas utilizados no SIGE EnterpriseSync:

| Termo | Definição |
|---|---|
| **Admin (ADMIN)** | Administrador do sistema — tipo de usuário com permissões completas para gerenciar dados da sua empresa (tenant) |
| **admin_id** | Campo presente em todas as tabelas do banco de dados que garante o isolamento multi-tenant dos dados por empresa |
| **Almoxarifado** | Módulo do sistema responsável pelo controle de estoque de materiais, ferramentas e EPIs |
| **API** | Application Programming Interface — interface de programação para integração com sistemas externos |
| **Balancete** | Relatório contábil que apresenta os saldos de todas as contas em um determinado período |
| **CA** | Certificado de Aprovação — documento obrigatório para EPIs conforme NR-6 |
| **Centro de Custo** | Unidade de classificação de despesas por área de responsabilidade (obra, departamento, projeto) |
| **DRE** | Demonstrativo de Resultado do Exercício — relatório contábil que apresenta receitas, custos e resultado do período |
| **DSR** | Descanso Semanal Remunerado — direito trabalhista calculado sobre horas extras conforme Lei 605/49 |
| **EPI** | Equipamento de Proteção Individual — equipamento de segurança obrigatório conforme NR-6 |
| **EventManager** | Componente interno do sistema que gerencia eventos e dispara atualizações automáticas entre módulos |
| **Geofencing** | Cerca virtual baseada em coordenadas GPS utilizada para validar a localização do funcionário no registro de ponto |
| **KPI** | Key Performance Indicator — Indicador-Chave de Desempenho exibido nos dashboards e relatórios |
| **Multi-tenant** | Arquitetura que permite múltiplas empresas operarem de forma isolada na mesma instalação do sistema |
| **NR-6** | Norma Regulamentadora nº 6 do Ministério do Trabalho — regulamenta o uso de EPIs |
| **Obra** | Projeto de construção civil cadastrado no sistema, com orçamento, equipe, serviços e controle financeiro |
| **Ponto** | Registro de frequência do funcionário — entrada, saída, almoço — com suporte a reconhecimento facial |
| **Portal do Cliente** | Interface web de acesso externo que permite ao cliente acompanhar o andamento da obra ou proposta |
| **RDO** | Relatório Diário de Obra — documento que registra diariamente as atividades executadas no canteiro |
| **Reconhecimento Facial** | Tecnologia biométrica utilizada para validar a identidade do funcionário no registro de ponto |
| **SIGE** | Sistema Integrado de Gestão Empresarial — nome interno do sistema EnterpriseSync |
| **SPED** | Sistema Público de Escrituração Digital — formato da Receita Federal para transmissão de dados contábeis |
| **Subatividade** | Divisão detalhada de um serviço cadastrado na obra, utilizada para controle granular de progresso no RDO |
| **Super Admin (SUPER_ADMIN)** | Tipo de usuário com acesso irrestrito a todas as funcionalidades e dados de todos os tenants do sistema |
| **Tenant** | Inquilino — cada empresa que opera dentro da mesma instalação do sistema com dados isolados |
| **Token** | Chave de autenticação temporária utilizada para acesso à API ou ao portal do cliente |
| **WebP** | Formato de imagem otimizado utilizado pelo sistema para armazenar fotos com qualidade e menor tamanho |

---

<div align="center">

---

**SIGE - Estruturas do Vale (EnterpriseSync)**
**Manual do Usuário — Versão 9.0**

Documento gerado em Fevereiro de 2026
Todos os direitos reservados.

---

</div>
