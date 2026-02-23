# Capítulo 1 — Configuração Inicial e Instalação

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

## Navegação do Sistema

**Barra de navegação superior do SIGE:**

`Dashboard` · `RDOs` · `Obras` · `Funcionários` · `Equipe` · `Ponto ▼` · `Propostas ▼` · `Financeiro ▼` · `Veículos` · `Alimentação` · `Almoxarifado ▼` · `Relatórios`

---

*SIGE - Estruturas do Vale (EnterpriseSync) — Manual do Usuário v8.0*
*Versão do documento: 2.0 | Data: Fevereiro de 2026*
