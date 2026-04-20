<div align="center">

# Manual do Usuário - Sistema SIGE EnterpriseSync

### Guia completo de uso do sistema

---

[LOGO DA EMPRESA]

---

**Versão 1.0 | Fevereiro de 2026**

**Sistema SIGE — EnterpriseSync**
**Estruturas do Vale**

---

</div>

> **Atualização (Task #132):** o ciclo completo do sistema —
> insumo → serviço (com composição e cronograma) → proposta →
> aprovação do cliente pelo link público → cronograma da obra
> validado pelo admin — está documentado e ilustrado em
> [`manual-ciclo-completo.md` § Apêndice B](manual-ciclo-completo.md#apêndice-b--teste-e2e-automatizado-task-132-insumo--serviço--proposta--cliente--cronograma--obra),
> com screenshots em `docs/img/manual 2/`. Use essa referência para
> entender em qual tela o cliente aprova (sem ver cronograma) e em
> qual tela o admin valida o cronograma da obra recém-criada
> (`/cronograma/obra/<id>`, badge **📋 do contrato**).

---

# Índice Geral

- [Capítulo 1 — Primeiro Acesso e Navegação](#capítulo-1--primeiro-acesso-e-navegação)
  - [1.1. Bem-vindo ao SIGE](#11-bem-vindo-ao-sige)
  - [1.2. Acessando o Sistema](#12-acessando-o-sistema)
  - [1.3. Fazendo Login](#13-fazendo-login)
  - [1.4. Conhecendo a Interface](#14-conhecendo-a-interface)
  - [1.5. Perfis de Acesso](#15-perfis-de-acesso)
  - [1.6. Alterando sua Senha](#16-alterando-sua-senha)
  - [1.7. Saindo do Sistema (Logout)](#17-saindo-do-sistema-logout)
  - [1.8. Dicas de Navegação](#18-dicas-de-navegação)
- [Capítulo 2 — Painel de Controle (Dashboard)](#capítulo-2--painel-de-controle-dashboard)
  - [2.1. O que é o Painel de Controle?](#21-o-que-é-o-painel-de-controle)
  - [2.2. Como Acessar o Painel de Controle](#22-como-acessar-o-painel-de-controle)
  - [2.3. Filtro de Período](#23-filtro-de-período--escolhendo-o-intervalo-de-datas)
  - [2.4. Cartões de KPI](#24-cartões-de-kpi--os-números-que-importam)
  - [2.5. Custos Detalhados do Período](#25-custos-detalhados-do-período)
  - [2.6. Propostas Comerciais](#26-propostas-comerciais)
  - [2.7. Gráfico de Evolução de Propostas](#27-gráfico-de-evolução-de-propostas)
  - [2.8. Obras e RDO — Acompanhamento Rápido](#28-obras-e-rdo--acompanhamento-rápido)
  - [2.9. Dashboard Executivo por Obra](#29-dashboard-executivo-por-obra)
  - [2.10. Painel do Funcionário](#210-painel-do-funcionário)
  - [2.11. Boas Práticas](#211-boas-práticas--aproveitando-o-painel-ao-máximo)
  - [2.12. Navegando do Painel para Outros Módulos](#212-navegando-do-painel-para-outros-módulos)
  - [2.13. Resumo do Capítulo](#213-resumo-do-capítulo)
- [Capítulo 3 — Gestão de Funcionários](#capítulo-3--gestão-de-funcionários)
  - [3.1. Introdução](#31-introdução)
  - [3.2. Tela Principal de Funcionários](#32-tela-principal-de-funcionários)
  - [3.3. Pesquisando e Filtrando Funcionários](#33-pesquisando-e-filtrando-funcionários)
  - [3.4. Cadastrando um Novo Funcionário](#34-cadastrando-um-novo-funcionário)
  - [3.5. Perfil do Funcionário](#35-perfil-do-funcionário)
  - [3.6. Cadastro de Fotos para Reconhecimento Facial](#36-cadastro-de-fotos-para-reconhecimento-facial)
  - [3.7. Ponto Eletrônico — Registro de Ponto](#37-ponto-eletrônico--registro-de-ponto)
  - [3.8. Consultando os Registros de Ponto](#38-consultando-os-registros-de-ponto)
  - [3.9. Relatórios de Funcionários](#39-relatórios-de-funcionários)
  - [3.10. Perguntas Frequentes](#310-perguntas-frequentes)
- [Capítulo 4 — Gestão de Obras](#capítulo-4--gestão-de-obras)
  - [4.1. Introdução](#41-introdução)
  - [4.2. Tela Principal de Obras](#42-tela-principal-de-obras)
  - [4.3. Cadastrando uma Nova Obra](#43-cadastrando-uma-nova-obra)
  - [4.4. Visualizando os Detalhes da Obra](#44-visualizando-os-detalhes-da-obra)
  - [4.5. Planejamento de Serviços](#45-planejamento-de-serviços)
  - [4.6. Lançamento de Custos Diversos](#46-lançamento-de-custos-diversos)
  - [4.7. Controle Financeiro da Obra](#47-controle-financeiro-da-obra)
  - [4.8. Criando RDOs a partir da Obra](#48-criando-rdos-a-partir-da-obra)
  - [4.9. Editando uma Obra](#49-editando-uma-obra)
  - [4.10. Alterando o Status da Obra](#410-alterando-o-status-da-obra)
  - [4.11. Equipe da Obra](#411-equipe-da-obra)
  - [4.12. Excluindo uma Obra](#412-excluindo-uma-obra)
  - [4.13. Relatórios de Obras](#413-relatórios-de-obras)
  - [4.14. Dicas e Boas Práticas](#414-dicas-e-boas-práticas)
- [Capítulo 5 — Gestão de Frota e Veículos](#capítulo-5--gestão-de-frota-e-veículos)
  - [5.1. Introdução](#51-introdução)
  - [5.2. Visualizando a Lista de Veículos](#52-visualizando-a-lista-de-veículos)
  - [5.3. Cadastrando um Novo Veículo](#53-cadastrando-um-novo-veículo)
  - [5.4. Registrando o Uso do Veículo (Viagens)](#54-registrando-o-uso-do-veículo-viagens)
  - [5.5. Controlando os Custos dos Veículos](#55-controlando-os-custos-dos-veículos)
  - [5.6. Painel de Detalhes do Veículo](#56-painel-de-detalhes-do-veículo)
  - [5.7. Controle de Documentação e Alertas](#57-controle-de-documentação-e-alertas)
  - [5.8. Relatórios de Frota](#58-relatórios-de-frota)
  - [5.9. Dicas Práticas](#59-dicas-práticas-para-uma-boa-gestão-de-frota)
  - [5.10. Perguntas Frequentes](#510-perguntas-frequentes)
- [Capítulo 6 — Relatório Diário de Obra (RDO)](#capítulo-6--relatório-diário-de-obra-rdo)
  - [6.1. O que é o RDO?](#61-o-que-é-o-rdo)
  - [6.2. Visualizando a Lista de RDOs](#62-visualizando-a-lista-de-rdos)
  - [6.3. Criando um Novo RDO — Passo a Passo](#63-criando-um-novo-rdo--passo-a-passo)
  - [6.4. Registrando Atividades e Serviços](#64-registrando-atividades-e-serviços)
  - [6.5. Tirando e Anexando Fotos](#65-tirando-e-anexando-fotos)
  - [6.6. Salvando e Enviando o RDO](#66-salvando-e-enviando-o-rdo)
  - [6.7. Aprovação de RDOs (Para Gestores)](#67-aprovação-de-rdos-para-gestores)
  - [6.8. Como o RDO Atualiza o Progresso da Obra](#68-como-o-rdo-atualiza-o-progresso-da-obra)
  - [6.9. Relatórios e Exportação](#69-relatórios-e-exportação)
  - [6.10. Dicas para Escrever Bons RDOs](#610-dicas-para-escrever-bons-rdos)
- [Capítulo 7 — Módulo Financeiro](#capítulo-7--módulo-financeiro)
  - [7.1. Introdução ao Módulo Financeiro](#71-introdução-ao-módulo-financeiro)
  - [7.2. Dashboard Financeiro](#72-dashboard-financeiro--seu-painel-de-controle)
  - [7.3. Contas a Pagar](#73-contas-a-pagar--controlando-suas-despesas)
  - [7.4. Contas a Receber](#74-contas-a-receber--controlando-suas-receitas)
  - [7.5. Fluxo de Caixa](#75-fluxo-de-caixa--o-extrato-da-sua-empresa)
  - [7.6. De onde vêm os custos automáticos?](#76-de-onde-vêm-os-custos-automáticos)
  - [7.7. Centros de Custo](#77-centros-de-custo--organizando-seus-gastos)
  - [7.8. Relatórios Financeiros](#78-relatórios-financeiros--entendendo-os-números-da-empresa)
  - [7.9. Dicas para Manter suas Finanças Organizadas](#79-dicas-para-manter-suas-finanças-organizadas)
- [Capítulo 8 — Outros Módulos](#capítulo-8--outros-módulos)
  - [8.1. Propostas Comerciais](#81-propostas-comerciais)
  - [8.2. Alimentação](#82-alimentação)
  - [8.3. Almoxarifado](#83-almoxarifado)
  - [8.4. Equipe](#84-equipe)
  - [8.5. Relatórios](#85-relatórios)
- [Capítulo 9 — Dúvidas Frequentes e Suporte](#capítulo-9--dúvidas-frequentes-e-suporte)
  - [9.1. Perguntas Frequentes](#91-perguntas-frequentes)
  - [9.2. Dicas do Dia a Dia](#92-dicas-do-dia-a-dia)
  - [9.3. Contato do Suporte](#93-contato-do-suporte)
  - [9.4. Glossário](#94-glossário)

---

# Capítulo 1 — Primeiro Acesso e Navegação

**SIGE - Estruturas do Vale (EnterpriseSync)**
Manual do Usuário — Versão 8.0

---

## 1.1. Bem-vindo ao SIGE

Bem-vindo ao **SIGE (Sistema Integrado de Gestão Empresarial)**, a plataforma completa da **Estruturas do Vale** para gerenciar todas as atividades da sua empresa de construção civil e engenharia.

Com o SIGE, você tem acesso a todas as ferramentas que precisa no dia a dia, reunidas em um único lugar:

- **Gestão de Obras** — Acompanhe o andamento de cada obra, registre atividades diárias e controle prazos.
- **Funcionários e Equipes** — Cadastre colaboradores, organize equipes de campo e gerencie escalas.
- **Controle de Ponto** — Registre entradas, saídas e pausas dos funcionários, com cálculo automático de horas trabalhadas e horas extras.
- **Relatórios Diários de Obra (RDO)** — Documente tudo o que acontece em cada obra, todos os dias.
- **Financeiro** — Gerencie contas a pagar, contas a receber e acompanhe o fluxo de caixa.
- **Propostas Comerciais** — Crie e acompanhe orçamentos e propostas para novos projetos.
- **Frota de Veículos** — Controle veículos, abastecimentos e manutenções.
- **Alimentação** — Gerencie refeições e vales alimentação dos colaboradores.
- **Almoxarifado** — Controle o estoque de materiais, requisições e movimentações.
- **Relatórios Gerenciais** — Visualize indicadores, gráficos e exporte dados para tomada de decisão.

O sistema foi projetado para ser simples e intuitivo, permitindo que todos os colaboradores — desde o escritório até o campo — possam utilizá-lo sem dificuldades.

---

## 1.2. Acessando o Sistema

### Como acessar

O SIGE é um sistema online, acessado diretamente pelo navegador de internet do seu computador, tablet ou celular. Não é necessário instalar nenhum programa.

Para acessar, basta:

1. Abra o navegador de internet de sua preferência.
2. Digite o endereço (URL) do sistema na barra de endereços. O endereço será fornecido pelo administrador da sua empresa.
3. A tela de login será exibida.

[IMAGEM: Barra de endereços do navegador com a URL do SIGE]

### Navegadores compatíveis

O SIGE funciona nos principais navegadores de internet. Recomendamos manter seu navegador sempre atualizado para a melhor experiência:

| Navegador | Versão Recomendada |
|:----------|:-------------------|
| Google Chrome | Versão 90 ou superior |
| Mozilla Firefox | Versão 88 ou superior |
| Microsoft Edge | Versão 90 ou superior |
| Safari (Mac/iPhone) | Versão 14 ou superior |

### Acesso pelo celular e tablet

O SIGE é **totalmente responsivo**, ou seja, se adapta automaticamente ao tamanho da tela do seu dispositivo. Você pode acessar todas as funcionalidades pelo celular ou tablet da mesma forma que acessa pelo computador.

**Dicas para acesso mobile:**

- Use o navegador Chrome ou Safari no seu celular.
- Para facilitar o acesso, adicione o SIGE como atalho na tela inicial do seu celular.
- Para funcionalidades como registro de ponto com foto, o navegador precisará de permissão para acessar a câmera do dispositivo.

---

## 1.3. Fazendo Login

O login é o primeiro passo para utilizar o sistema. Você precisará das suas credenciais de acesso (usuário e senha), que são fornecidas pelo administrador da empresa.

### Passo a passo para fazer login

1. Abra o navegador e acesse o endereço do SIGE.
2. Na tela de login, você verá dois campos:
   - **Username / E-mail** — Digite seu nome de usuário ou seu e-mail cadastrado.
   - **Senha** — Digite sua senha.
3. Clique no botão **"Entrar"**.

[IMAGEM: Tela de login do SIGE com os campos Username e Senha destacados]

### O que acontece após o login

Após fazer login com sucesso, você será direcionado automaticamente para a página inicial do sistema, que varia conforme o seu perfil de acesso:

| Seu Perfil | Página Inicial |
|:-----------|:---------------|
| Administrador Master | Painel do Super Administrador |
| Administrador | Dashboard (Painel de Controle) |
| Gestor de Equipes | RDO Consolidado |
| Almoxarife | RDO Consolidado |
| Funcionário | RDO Consolidado |

### Se o login não funcionar

Caso suas credenciais estejam incorretas, o sistema exibirá a mensagem:

> *"Email/Username ou senha inválidos."*

**O que fazer nesse caso:**

1. **Verifique o nome de usuário ou e-mail** — Confira se digitou corretamente, sem espaços extras.
2. **Verifique a senha** — Lembre-se de que a senha diferencia letras maiúsculas de minúsculas.
3. **Confira se o Caps Lock está desligado** — Uma causa comum de erro é digitar a senha com o Caps Lock ativado.
4. **Entre em contato com o administrador** — Se ainda não conseguir acessar, solicite ao administrador da sua empresa que verifique seu cadastro ou redefina sua senha.

[IMAGEM: Mensagem de erro de login exibida na tela]

> **Observação:** Por segurança, o sistema limita o número de tentativas de login. Se você errar muitas vezes em um curto intervalo, aguarde alguns minutos antes de tentar novamente.

---

## 1.4. Conhecendo a Interface

Após fazer login, você encontrará uma interface organizada e intuitiva. Vamos conhecer cada parte da tela:

[IMAGEM: Visão geral da interface do SIGE com as áreas numeradas]

### 1.4.1. Barra de Navegação Superior

A **barra de navegação** fica no topo da tela e é o principal meio de acessar os diferentes módulos do sistema. Ela contém os seguintes itens:

| Menu | O que você encontra |
|:-----|:--------------------|
| **Dashboard** | Painel de controle com indicadores gerais, gráficos e resumos da empresa. É a visão geral do negócio. |
| **RDOs** | Relatórios Diários de Obra — lista de todos os relatórios registrados, com opções de criar novos e visualizar os existentes. |
| **Obras** | Lista de todas as obras cadastradas, com informações de andamento, localização e equipes. |
| **Funcionários** | Cadastro completo de colaboradores, com dados pessoais, função, departamento e documentos. |
| **Equipe** | Gestão de equipes de trabalho, permitindo organizar os colaboradores por grupos e obras. |
| **Ponto** ▼ | Menu com opções para controle de ponto dos funcionários, incluindo registro de entradas e saídas, consultas e relatórios de frequência. |
| **Propostas** ▼ | Menu para criação e acompanhamento de propostas comerciais e orçamentos de obras. |
| **Financeiro** ▼ | Menu com opções financeiras, incluindo contas a pagar, contas a receber e fluxo de caixa. |
| **Veículos** | Gestão da frota de veículos, controle de abastecimentos, manutenções e quilometragem. |
| **Alimentação** | Controle de refeições fornecidas aos colaboradores e gestão de vales alimentação. |
| **Almoxarifado** ▼ | Menu para gestão de materiais, controle de estoque, requisições e movimentações de entrada e saída. |
| **Relatórios** | Relatórios consolidados e ferramentas de exportação de dados para análise gerencial. |

> **O símbolo ▼** ao lado de alguns menus indica que eles possuem submenus. Ao clicar ou passar o mouse sobre esses itens, um menu suspenso será exibido com as opções disponíveis.

[IMAGEM: Barra de navegação superior com os menus destacados]

### 1.4.2. Menu do Usuário

No canto superior direito da tela, você encontrará o **Menu do Usuário**, identificado pelo seu nome de usuário. Ao clicar sobre ele, um menu suspenso será exibido com as seguintes opções:

| Opção | O que faz |
|:------|:----------|
| **Perfil** | Acessa seus dados pessoais e permite editar informações como nome e e-mail. |
| **Configurações** | Acessa as configurações da sua conta, incluindo alteração de senha. |
| **Sair** | Encerra sua sessão e retorna à tela de login. |

[IMAGEM: Menu do usuário no canto superior direito expandido]

> **Dica:** Sempre que terminar de usar o sistema, clique em **"Sair"** para encerrar sua sessão com segurança, especialmente se estiver usando um computador compartilhado.

### 1.4.3. Área de Conteúdo Principal

A **área de conteúdo principal** ocupa a maior parte da tela e é onde as informações e formulários de cada módulo são exibidos. O conteúdo dessa área muda conforme o menu que você seleciona na barra de navegação.

Por exemplo:
- Ao clicar em **Dashboard**, a área principal exibirá gráficos e indicadores.
- Ao clicar em **Funcionários**, será exibida a lista de colaboradores cadastrados.
- Ao clicar em **RDOs**, aparecerão os relatórios diários de obra.

A maioria das telas de listagem apresenta:
- **Botão de ação** (como "Novo", "Cadastrar" ou "Adicionar") para criar novos registros.
- **Tabela de dados** com os registros existentes.
- **Ícones de ação** ao lado de cada registro (visualizar, editar, excluir).
- **Filtros e buscas** para localizar informações específicas.

[IMAGEM: Exemplo de área de conteúdo mostrando uma lista com botão de ação e filtros]

---

## 1.5. Perfis de Acesso

O SIGE possui **5 perfis de acesso** diferentes. Cada perfil determina quais menus e funcionalidades o usuário pode acessar. O perfil é definido pelo administrador da empresa no momento do cadastro do usuário.

### Resumo dos perfis

| Perfil | Quem é | O que pode fazer |
|:-------|:-------|:-----------------|
| **Administrador Master** | Responsável geral pelo sistema | Acesso total a todas as funcionalidades, incluindo gestão de múltiplas empresas |
| **Administrador** | Gestor principal da empresa | Acesso a todos os módulos da sua empresa: obras, funcionários, financeiro, relatórios, configurações |
| **Gestor de Equipes** | Líder ou encarregado de campo | Gerencia equipes, cria RDOs, controla ponto, acompanha andamento das obras |
| **Almoxarife** | Responsável pelo estoque | Acesso ao módulo de almoxarifado, controle de materiais, requisições e movimentações |
| **Funcionário** | Colaborador da empresa | Acesso restrito ao próprio registro de ponto e visualização dos RDOs consolidados |

### O que cada perfil pode ver

A tabela abaixo mostra quais módulos estão disponíveis para cada perfil de acesso:

| Módulo | Administrador Master | Administrador | Gestor de Equipes | Almoxarife | Funcionário |
|:-------|:-------------------:|:-------------:|:-----------------:|:----------:|:-----------:|
| Dashboard | ✅ | ✅ | ❌ | ❌ | ❌ |
| RDOs | ✅ | ✅ | ✅ | ❌ | ✅ (somente visualizar) |
| Obras | ✅ | ✅ | ✅ (visualizar) | ❌ | ❌ |
| Funcionários | ✅ | ✅ | ✅ (da equipe) | ❌ | ❌ |
| Equipe | ✅ | ✅ | ✅ | ❌ | ❌ |
| Ponto | ✅ | ✅ | ✅ | ❌ | ✅ (próprio) |
| Propostas | ✅ | ✅ | ❌ | ❌ | ❌ |
| Financeiro | ✅ | ✅ | ❌ | ❌ | ❌ |
| Veículos | ✅ | ✅ | ❌ | ❌ | ❌ |
| Alimentação | ✅ | ✅ | ❌ | ❌ | ❌ |
| Almoxarifado | ✅ | ✅ | ❌ | ✅ | ❌ |
| Relatórios | ✅ | ✅ | ✅ (parcial) | ❌ | ❌ |
| Configurações | ✅ | ✅ | ❌ | ❌ | ❌ |

> **Observação:** Os menus que não fazem parte do seu perfil de acesso não serão exibidos na barra de navegação. Ou seja, cada usuário vê apenas os menus que pode utilizar.

[IMAGEM: Comparação das barras de navegação para perfil Administrador e perfil Funcionário]

---

## 1.6. Alterando sua Senha

Para manter a segurança da sua conta, é recomendável alterar sua senha periodicamente, especialmente após o primeiro acesso.

### Como alterar sua senha

1. Clique no seu **nome de usuário** no canto superior direito da tela.
2. No menu suspenso, selecione **"Configurações"** ou **"Perfil"**.
3. Localize a seção de **alteração de senha**.
4. Preencha os campos:
   - **Senha atual** — Digite sua senha atual.
   - **Nova senha** — Digite a nova senha desejada.
   - **Confirmar nova senha** — Repita a nova senha para confirmação.
5. Clique em **"Salvar"** para confirmar a alteração.

[IMAGEM: Tela de alteração de senha com os campos destacados]

### Dicas para criar uma senha segura

- Use no mínimo **8 caracteres**.
- Combine **letras maiúsculas e minúsculas**.
- Inclua **números** e **caracteres especiais** (como @, #, $, !).
- Evite usar informações pessoais como nome, data de nascimento ou sequências óbvias (123456, abcdef).
- Não compartilhe sua senha com outras pessoas.

> **Esqueceu sua senha?** Entre em contato com o administrador da sua empresa. Ele poderá redefinir sua senha pelo painel de gestão de usuários.

---

## 1.7. Saindo do Sistema (Logout)

Ao terminar de usar o SIGE, é importante encerrar sua sessão corretamente para proteger seus dados.

### Como sair do sistema

1. Clique no seu **nome de usuário** no canto superior direito da tela.
2. No menu suspenso, clique em **"Sair"**.
3. Você será redirecionado para a tela de login e verá a mensagem:

> *"Você saiu do sistema."*

[IMAGEM: Menu do usuário com a opção Sair destacada]

> **Importante:** Sempre faça logout ao terminar de usar o sistema, especialmente em computadores compartilhados ou públicos. Isso evita que outras pessoas acessem seus dados.

---

## 1.8. Dicas de Navegação

Confira algumas dicas para aproveitar melhor o SIGE no seu dia a dia:

### Navegação responsiva no celular

- No celular, a barra de navegação se transforma em um **menu hambúrguer** (ícone com três linhas horizontais ☰). Toque nele para abrir o menu completo.
- As tabelas e formulários se adaptam automaticamente à tela do celular, podendo ser roladas horizontalmente quando necessário.
- Para uma melhor experiência, use o celular na posição **horizontal (paisagem)** ao visualizar tabelas com muitas colunas.

### Atalhos úteis do navegador

Embora o SIGE não possua atalhos de teclado próprios, você pode usar os atalhos padrão do seu navegador para agilizar o uso:

| Atalho | O que faz |
|:-------|:----------|
| **F5** ou **Ctrl + R** | Atualiza a página atual |
| **Ctrl + F** | Abre a busca de texto na página |
| **Ctrl + T** | Abre uma nova aba no navegador |
| **Alt + ←** | Volta para a página anterior |
| **Alt + →** | Avança para a próxima página |
| **Ctrl + +** | Aumenta o zoom da página |
| **Ctrl + -** | Diminui o zoom da página |
| **Ctrl + 0** | Restaura o zoom padrão |

### Listas e tabelas

- A maioria das telas de listagem permite **ordenar** os dados clicando no cabeçalho da coluna desejada.
- Use os **filtros** disponíveis acima das tabelas para localizar registros específicos.
- Procure pelo **campo de busca** para encontrar rapidamente um funcionário, obra ou outro registro pelo nome.

### Formulários

- Campos marcados com **asterisco (*)** são obrigatórios e devem ser preenchidos.
- Após preencher um formulário, clique no botão **"Salvar"** para registrar as informações.
- Se quiser descartar as alterações, clique em **"Cancelar"** ou simplesmente navegue para outra página.

### Conexão com a internet

- O SIGE requer uma conexão estável com a internet para funcionar corretamente.
- Se a conexão for interrompida durante o preenchimento de um formulário, suas informações poderão ser perdidas. Nesse caso, recarregue a página e preencha novamente.

> **Dica final:** Em caso de dúvidas sobre qualquer funcionalidade, consulte os capítulos específicos deste manual ou entre em contato com o administrador da sua empresa.

---

*SIGE - Estruturas do Vale (EnterpriseSync) — Manual do Usuário v8.0*
*Versão do documento: 2.0 | Data: Fevereiro de 2026*

---

# Capítulo 2 — Painel de Controle (Dashboard)

**SIGE - Estruturas do Vale**
Manual do Usuário — Versão 8.0

---

## 2.1. O que é o Painel de Controle?

O **Painel de Controle** (Dashboard) é a primeira tela que você verá ao entrar no SIGE. Pense nele como o "painel do carro" da sua empresa: em uma única tela, você acompanha os números mais importantes do seu dia a dia — quantos funcionários estão ativos, quantas obras estão em andamento, o tamanho da sua frota e quanto está custando a operação no período.

Você não precisa abrir vários módulos para ter uma visão geral. O Painel de Controle reúne tudo em um só lugar, de forma visual e prática.

**O que você encontra no Painel de Controle:**

- **Cartões de resumo (KPIs)** — Funcionários Ativos, Obras Ativas, Veículos e Custos do Período
- **Custos Detalhados** — Quanto está sendo gasto em Alimentação, Transporte e Mão de Obra
- **Propostas Comerciais** — Quantas propostas foram enviadas, aprovadas ou rejeitadas
- **Obras e RDO** — Lista das suas obras com botão rápido para criar novos relatórios
- **Gráfico de Evolução** — Tendência das suas propostas ao longo do tempo

[IMAGEM: Visão geral do Painel de Controle com os cartões de KPI e seções principais]

---

## 2.2. Como Acessar o Painel de Controle

### 2.2.1. Acesso Automático após o Login

Ao entrar no SIGE com seu e-mail e senha, você será levado automaticamente para o Painel de Controle. Não é necessário clicar em nada — o sistema já abre na tela certa para você.

**Passo a passo:**

1. Abra o SIGE no seu navegador
2. Digite seu **e-mail** e **senha**
3. Clique em **Entrar**
4. Pronto! O Painel de Controle aparecerá na tela

> **Bom saber:** Se você é um **administrador**, verá o Painel de Controle completo com todos os indicadores da empresa. Se você é um **funcionário**, verá uma versão adaptada com as informações relevantes para o seu trabalho de campo (mais detalhes na seção 2.6).

[IMAGEM: Tela de login do SIGE com campos de e-mail e senha]

### 2.2.2. Voltando ao Painel a Qualquer Momento

Você pode retornar ao Painel de Controle de qualquer tela do sistema. Basta olhar para o menu verde no topo da página e clicar em **Dashboard**.

O menu de navegação superior apresenta os seguintes itens:

| Item do Menu | Para que serve |
|:-------------|:---------------|
| **Dashboard** | Voltar ao Painel de Controle |
| **RDOs** | Relatórios Diários de Obra |
| **Obras** | Ver e gerenciar suas obras |
| **Funcionários** | Cadastro dos seus colaboradores |
| **Equipe** | Alocação de equipes nas obras |
| **Ponto** | Controle de ponto dos funcionários |
| **Propostas** | Propostas comerciais e orçamentos |
| **Financeiro** | Gestão financeira da empresa |
| **Veículos** | Gestão da sua frota |
| **Alimentação** | Controle de refeições e vales |
| **Almoxarifado** | Estoque e materiais |
| **Relatórios** | Relatórios consolidados |

> **Dica:** O item **Dashboard** é sempre o primeiro do menu. Se você se perder em qualquer tela, basta clicar nele para voltar à visão geral.

[IMAGEM: Barra de navegação verde do SIGE com os itens de menu destacados]

---

## 2.3. Filtro de Período — Escolhendo o Intervalo de Datas

No topo do Painel de Controle, você verá dois campos de data: **Data Início** e **Data Fim**. Esses campos controlam qual período os números do painel estão mostrando.

**Como usar o filtro:**

1. Clique no campo **Data Início** e selecione a data inicial desejada
2. Clique no campo **Data Fim** e selecione a data final
3. Clique no botão **Filtrar**
4. Todos os números e gráficos serão atualizados para o período escolhido

**Exemplos práticos de uso:**

- Quer ver os custos do mês passado? Selecione o primeiro e o último dia do mês
- Precisa comparar dois meses? Filtre cada mês separadamente e anote os valores
- Quer analisar o trimestre inteiro? Selecione um período de 3 meses

> **Bom saber:** Quando você acessa o Painel pela primeira vez, o sistema escolhe automaticamente o mês mais recente que possui registros. Assim, você sempre verá dados relevantes sem precisar configurar nada.

> **Atenção:** Se os cartões estiverem mostrando valores zerados, pode ser que não existam registros no período selecionado. Tente ampliar o intervalo de datas ou selecionar um mês diferente.

[IMAGEM: Campos de filtro de período com Data Início, Data Fim e botão Filtrar]

---

## 2.4. Cartões de KPI — Os Números que Importam

Logo abaixo do filtro de período, você verá **4 cartões coloridos** que mostram os indicadores mais importantes da sua empresa. Esses cartões são atualizados sempre que você acessa o Painel ou altera o filtro de período.

[IMAGEM: Os 4 cartões de KPI — Funcionários Ativos, Obras Ativas, Veículos e Custos do Período]

### 2.4.1. Funcionários Ativos

Este cartão mostra **quantos colaboradores estão ativos** na sua empresa neste momento.

**O que esse número significa na prática:**

- Se o cartão mostra **10**, você tem 10 funcionários cadastrados e ativos trabalhando
- Este número indica a capacidade atual da sua equipe
- Funcionários que foram desligados ou colocados como inativos **não aparecem** neste número

**Quando prestar atenção:**

- Se o número estiver menor do que o esperado, pode ser que algum funcionário tenha sido desativado por engano
- Se você contratou alguém recentemente e o número não mudou, verifique se o cadastro foi concluído

**Para ver mais detalhes:** Clique em **Funcionários** no menu superior para acessar a lista completa dos seus colaboradores.

### 2.4.2. Obras Ativas

Este cartão mostra **quantas obras estão em andamento ou planejamento** na sua empresa.

**O que esse número significa na prática:**

- Se o cartão mostra **8**, você tem 8 obras abertas no momento
- Este número inclui obras em andamento, em planejamento ou com status ativo
- Obras que já foram finalizadas ou canceladas **não entram** nesta contagem

**Quando prestar atenção:**

- Um número muito alto pode indicar que a equipe está sobrecarregada
- Se uma obra foi concluída mas o número não diminuiu, pode ser que o status não tenha sido atualizado no sistema

**Para ver mais detalhes:** Clique em **Obras** no menu superior para ver a lista de todas as suas obras com seus respectivos status.

### 2.4.3. Veículos

Este cartão mostra **quantos veículos ativos estão na sua frota**.

**O que esse número significa na prática:**

- Se o cartão mostra **3**, você tem 3 veículos cadastrados e disponíveis para uso
- Veículos que foram baixados ou desativados não aparecem neste número

**Quando prestar atenção:**

- Se um veículo quebrou e está fora de operação, considere desativá-lo temporariamente no sistema para manter o número atualizado
- Use este número para planejar a logística de deslocamento das equipes

**Para ver mais detalhes:** Clique em **Veículos** no menu superior para gerenciar a sua frota.

### 2.4.4. Custos do Período

Este cartão mostra o **valor total de custos operacionais** no período selecionado no filtro, exibido em Reais (R$).

**O que esse número significa na prática:**

- Se o cartão mostra **R$ 45.320,00**, este é o total que a operação custou no período filtrado
- O valor inclui custos com alimentação, transporte e mão de obra somados
- Compare este valor com meses anteriores para identificar tendências de aumento ou redução

**Quando prestar atenção:**

- Se o valor subiu significativamente em relação ao mês anterior, investigue qual categoria de custo cresceu (veja a seção de Custos Detalhados logo abaixo)
- Use este número em reuniões gerenciais para apresentar o custo operacional da empresa

**Para análise detalhada:** Role a página para baixo e veja a seção **Custos Detalhados do Período**, que decompõe esse valor total por categoria.

---

## 2.5. Custos Detalhados do Período

Logo abaixo dos cartões de KPI, você encontrará a seção **Custos Detalhados do Período**. Aqui, o custo total é dividido em categorias para que você entenda **onde o dinheiro está sendo gasto**.

[IMAGEM: Cartões de Custos Detalhados mostrando Alimentação, Transporte, Mão de Obra e Total]

Você verá 4 cartões:

| Cartão | O que mostra | Exemplo |
|:-------|:-------------|:--------|
| **Alimentação** | Custos com refeições, vales-refeição e cestas básicas | R$ 8.500,00 |
| **Transporte** | Custos com combustível, pedágios e deslocamentos da equipe | R$ 5.200,00 |
| **Mão de Obra** | Custos com salários, horas extras e encargos trabalhistas | R$ 28.600,00 |
| **Total** | Soma de todas as categorias acima | R$ 42.300,00 |

**Como usar esses números no seu dia a dia:**

1. **Identifique o maior custo** — Normalmente, a Mão de Obra representa a maior fatia. Se outro item estiver desproporcionalmente alto, vale investigar
2. **Compare com meses anteriores** — Use o filtro de período para ver mês a mês e identificar se alguma categoria está crescendo fora do normal
3. **Planeje reduções** — Se os custos com Transporte estão altos, talvez seja o momento de otimizar rotas ou revisar contratos de combustível
4. **Apresente em reuniões** — Esses cartões são perfeitos para mostrar de forma clara a composição dos custos para sócios ou gestores

> **Dica prática:** Para entender melhor cada categoria de custo, você pode acessar os módulos específicos pelo menu: **Alimentação** para ver os lançamentos de refeições, **Veículos** para ver os gastos com a frota, e **Funcionários** para ver os custos com a equipe.

---

## 2.6. Propostas Comerciais

A seção **Propostas Comerciais** no Painel de Controle oferece uma visão rápida de como está a atividade comercial da sua empresa.

[IMAGEM: Seção de Propostas Comerciais com estatísticas e indicadores]

**O que você encontra aqui:**

- **Total de Propostas** — Quantas propostas foram criadas no período
- **Taxa de Conversão** — De cada 100 propostas enviadas, quantas foram aprovadas? Esse percentual mostra a eficiência comercial
- **Valor Médio** — Qual é o valor médio das propostas aprovadas. Útil para entender o ticket médio dos seus contratos
- **Propostas por Mês** — Média de propostas criadas nos últimos 6 meses, ajuda a entender o ritmo comercial

**Os status das propostas e o que significam:**

| Status | O que significa | Como identificar |
|:-------|:----------------|:-----------------|
| **Aprovada** | O cliente aceitou a proposta — ótima notícia! | Aparece em verde |
| **Enviada** | A proposta foi enviada e aguarda a resposta do cliente | Aparece em azul |
| **Rascunho** | A proposta está sendo elaborada e ainda não foi enviada | Aparece em cinza |
| **Rejeitada** | O cliente não aceitou a proposta | Aparece em vermelho |
| **Expirada** | O prazo de validade da proposta venceu sem resposta | Aparece em laranja |

**Dicas para acompanhar suas propostas:**

- Se você tem muitas propostas com status **Enviada**, entre em contato com os clientes para obter respostas
- Propostas **Expiradas** podem ser reenviadas com valores atualizados
- Uma **Taxa de Conversão** baixa pode indicar que os valores estão acima do mercado ou que a apresentação precisa melhorar

**Para gerenciar suas propostas:** Clique em **Propostas** no menu superior para ver a lista completa, criar novas propostas ou editar as existentes.

---

## 2.7. Gráfico de Evolução de Propostas

O gráfico **Evolução de Propostas** mostra visualmente como suas propostas se comportaram ao longo do tempo. É uma forma rápida de identificar se a atividade comercial está crescendo, estável ou diminuindo.

[IMAGEM: Gráfico de Evolução de Propostas com linhas mostrando a tendência ao longo dos meses]

**Como ler o gráfico:**

- O **eixo horizontal** (embaixo) mostra os meses
- O **eixo vertical** (na lateral) mostra a quantidade de propostas
- As linhas ou barras mostram como cada status evoluiu ao longo do tempo

**O que observar:**

1. **Tendência de crescimento** — Se as linhas estão subindo, sua equipe comercial está mais ativa
2. **Queda brusca** — Se houve uma queda repentina, investigue o que aconteceu naquele mês
3. **Proporção de aprovações** — Idealmente, a linha de propostas aprovadas deve acompanhar o crescimento das propostas enviadas

> **Dica prática:** Use este gráfico em reuniões comerciais para demonstrar a evolução dos resultados e planejar metas futuras.

---

## 2.8. Obras e RDO — Acompanhamento Rápido

A seção **Obras e RDO** é uma das mais úteis do Painel de Controle. Ela lista suas obras ativas com informações resumidas e permite criar Relatórios Diários de Obra (RDOs) com apenas um clique.

[IMAGEM: Lista de Obras e RDO com nomes das obras, status e botão +RDO]

**O que você verá na lista:**

| Coluna | O que mostra |
|:-------|:-------------|
| **Nome da Obra** | O nome ou identificação do projeto |
| **Status** | Se a obra está ativa, em andamento ou em planejamento |
| **Progresso** | Quanto da obra já foi concluído (em percentual) |
| **Ação** | Botão **+RDO** para criar um relatório rapidamente |

### Como Criar um RDO Direto do Painel

Esta é uma das funcionalidades mais práticas do Painel de Controle. Em vez de navegar até o módulo de Obras e depois criar o RDO, você pode fazer tudo em poucos cliques:

1. Encontre a obra desejada na lista **Obras e RDO**
2. Clique no botão **+RDO** ao lado do nome da obra
3. O sistema abrirá o formulário de criação de RDO já vinculado àquela obra
4. Preencha as informações do dia (atividades, equipe, condições climáticas, etc.)
5. Salve o relatório

> **Dica importante:** Mantenha os RDOs atualizados diariamente. O progresso de cada obra é calculado com base nos relatórios registrados. Quanto mais atualizados os RDOs, mais precisa será a visão de andamento das obras no Painel.

**Para ver todas as obras:** Clique em **Obras** no menu superior para acessar a lista completa com todos os detalhes, incluindo obras finalizadas.

---

## 2.9. Dashboard Executivo por Obra

Além do Painel de Controle principal, o SIGE oferece um **painel detalhado individual para cada obra**. Este painel é ideal para gestores de projeto que precisam acompanhar os indicadores de uma obra específica.

**Como acessar:**

1. Clique em **Obras** no menu superior
2. Na lista de obras, clique na obra que deseja acompanhar
3. Você verá uma tela com todas as informações consolidadas daquela obra

**Informações disponíveis:**

| Seção | O que você encontra |
|:------|:--------------------|
| **Dados Gerais** | Nome da obra, cliente, endereço, data de início e previsão de término |
| **Progresso** | Percentual de conclusão geral do projeto |
| **RDOs** | Lista dos Relatórios Diários registrados para esta obra |
| **Equipe Alocada** | Quais funcionários estão trabalhando nesta obra |
| **Custos** | Detalhamento dos custos específicos da obra por categoria |
| **Serviços** | Serviços contratados e executados no projeto |

[IMAGEM: Painel Executivo de uma obra com dados gerais, progresso e custos]

> **Dica prática:** Use o Painel Executivo por Obra para preparar relatórios para clientes, mostrando o andamento do projeto com dados reais do sistema.

---

## 2.10. Painel do Funcionário

Se você acessa o SIGE como **funcionário** (e não como administrador), verá uma versão do painel adaptada para as suas necessidades de campo. O sistema reconhece automaticamente o seu perfil e mostra apenas as informações relevantes para o seu trabalho.

[IMAGEM: Painel do Funcionário com cartões de resumo e ações rápidas]

### 2.10.1. Seus Cartões de Resumo

Ao entrar no sistema, você verá 3 cartões informativos:

| Cartão | O que mostra | Exemplo |
|:-------|:-------------|:--------|
| **Obras Disponíveis** | Quantas obras estão disponíveis para você registrar relatórios | 142 |
| **RDOs Registrados** | Quantos Relatórios Diários você já criou | 10 |
| **RDOs Rascunho** | Quantos relatórios você começou mas ainda não finalizou | 5 |

**O que esses números significam para você:**

- **Obras Disponíveis** indica em quantas obras você pode trabalhar e registrar RDOs. Esse número é definido pelo seu administrador
- **RDOs Registrados** mostra o total de relatórios que você já enviou. Quanto mais RDOs registrados, mais completo estará o acompanhamento das obras
- **RDOs Rascunho** são relatórios que você começou a preencher mas não finalizou. Lembre-se de completá-los para que as informações sejam contabilizadas

> **Atenção:** Se você tem RDOs em rascunho, finalize-os o quanto antes! Rascunhos não são contabilizados nos relatórios da empresa e podem causar lacunas no acompanhamento das obras.

### 2.10.2. Ações Rápidas

Logo abaixo dos cartões, você encontra botões de **Ações Rápidas** que dão acesso direto às funcionalidades mais usadas:

| Botão | O que faz |
|:------|:----------|
| **Criar RDO** | Abre o formulário para você criar um novo Relatório Diário de Obra |
| **Ver Todos os RDOs** | Mostra a lista de todos os seus RDOs (enviados e rascunhos) |
| **Ver Obras** | Exibe as obras disponíveis para você |
| **Sair** | Encerra sua sessão no sistema |

**Fluxo típico do dia a dia:**

1. Acesse o sistema no início do dia
2. Clique em **Criar RDO** para registrar o relatório do dia
3. Selecione a obra em que está trabalhando
4. Preencha as informações: atividades realizadas, equipe presente, condições climáticas, fotos
5. Salve o relatório

### 2.10.3. RDOs Recentes e Obras Disponíveis

Na parte inferior do painel, você encontra duas listas úteis:

**RDOs Recentes:**
- Mostra os últimos relatórios que você criou
- Cada item exibe a data, a obra e o status (enviado ou rascunho)
- Clique em qualquer RDO para abri-lo e editá-lo (se ainda estiver como rascunho)

**Obras Disponíveis:**
- Lista as obras em que você pode registrar relatórios
- Cada obra mostra seu nome e status atual
- Clique em uma obra para ver mais detalhes sobre ela

[IMAGEM: Listas de RDOs Recentes e Obras Disponíveis no Painel do Funcionário]

---

## 2.11. Boas Práticas — Aproveitando o Painel ao Máximo

O Painel de Controle é mais útil quando você o consulta regularmente. Aqui estão algumas dicas práticas para tirar o máximo proveito dele:

### Para Administradores e Gestores

1. **Comece o dia pelo Painel** — Acesse o Painel de Controle logo no início do expediente para ter uma visão rápida de como está a operação
2. **Verifique os custos semanalmente** — Compare os custos do período atual com semanas anteriores para identificar tendências antes que se tornem problemas
3. **Acompanhe as propostas** — Propostas com status "Enviada" há muito tempo podem precisar de um follow-up com o cliente
4. **Monitore os RDOs** — Obras sem RDOs recentes podem indicar que a equipe de campo não está registrando as atividades
5. **Use o filtro de período** — Compare diferentes meses para entender a sazonalidade dos custos e da atividade comercial
6. **Crie RDOs direto do Painel** — Use o botão **+RDO** na seção de Obras para agilizar o registro de relatórios

### Para Funcionários

1. **Registre o RDO diariamente** — Mesmo que o dia tenha sido curto, registre o que foi feito
2. **Finalize os rascunhos** — Não deixe RDOs em rascunho por mais de um dia
3. **Verifique suas obras** — Confirme que você está registrando RDOs na obra correta
4. **Use as Ações Rápidas** — Os botões de ação rápida economizam tempo no dia a dia

### Perguntas Frequentes sobre o Painel

**Por que os valores estão zerados?**
Provavelmente o período selecionado no filtro não possui registros. Tente selecionar um período diferente ou verifique se os dados foram lançados no sistema.

**Com que frequência os números são atualizados?**
Os dados são atualizados toda vez que você acessa o Painel ou clica em Filtrar. Não é necessário atualizar a página manualmente.

**Posso ver dados de meses anteriores?**
Sim! Use o filtro de período no topo do Painel para selecionar qualquer intervalo de datas.

**O que acontece se eu não registrar RDOs?**
O progresso das obras no Painel ficará desatualizado e os gestores não terão visibilidade do andamento real dos projetos.

---

## 2.12. Navegando do Painel para Outros Módulos

O Painel de Controle funciona como um ponto de partida para acessar os outros módulos do SIGE. Aqui está um guia rápido de como ir do Painel para cada funcionalidade:

| Você quer... | Faça isso |
|:-------------|:----------|
| Ver detalhes de um funcionário | Clique em **Funcionários** no menu superior |
| Criar um RDO para uma obra | Clique no botão **+RDO** na seção Obras e RDO |
| Ver todas as suas propostas | Clique em **Propostas** no menu superior |
| Gerenciar a frota de veículos | Clique em **Veículos** no menu superior |
| Consultar os custos com alimentação | Clique em **Alimentação** no menu superior |
| Ver o estoque de materiais | Clique em **Almoxarifado** no menu superior |
| Gerar relatórios consolidados | Clique em **Relatórios** no menu superior |
| Ver o controle de ponto | Clique em **Ponto** no menu superior |
| Gerenciar a alocação da equipe | Clique em **Equipe** no menu superior |
| Acessar o financeiro da empresa | Clique em **Financeiro** no menu superior |

> **Lembre-se:** Você pode voltar ao Painel de Controle a qualquer momento clicando em **Dashboard** no menu superior.

---

## 2.13. Resumo do Capítulo

Neste capítulo, você aprendeu a:

| Seção | O que você aprendeu |
|:------|:--------------------|
| 2.1 | O que é o Painel de Controle e o que ele mostra |
| 2.2 | Como acessar o Painel e navegar pelo menu |
| 2.3 | Como usar o filtro de período para ver dados de diferentes datas |
| 2.4 | O que significam os cartões de KPI (Funcionários, Obras, Veículos, Custos) |
| 2.5 | Como interpretar os Custos Detalhados por categoria |
| 2.6 | Como acompanhar as Propostas Comerciais |
| 2.7 | Como ler o gráfico de Evolução de Propostas |
| 2.8 | Como usar a seção Obras e RDO para criar relatórios rapidamente |
| 2.9 | O que é o Painel Executivo por Obra |
| 2.10 | Como funciona o Painel do Funcionário |
| 2.11 | Boas práticas para usar o Painel no dia a dia |
| 2.12 | Como navegar do Painel para outros módulos |

---

# Capítulo 3 — Gestão de Funcionários

## 3.1. Introdução

O módulo de **Gestão de Funcionários** é onde você cadastra, acompanha e gerencia toda a equipe da sua empresa. Aqui você pode:

- Cadastrar novos funcionários com todas as informações necessárias
- Consultar e editar dados de qualquer funcionário
- Registrar fotos para o reconhecimento facial no ponto eletrônico
- Acompanhar horas trabalhadas, faltas e horas extras
- Registrar e controlar o ponto eletrônico
- Gerar relatórios e exportar informações em PDF

Este capítulo vai guiar você por cada uma dessas funcionalidades, passo a passo.

> **Quem pode usar:** Para acessar este módulo, você precisa ter permissão de **Administrador** ou **Gestor de Equipes**. Funcionários com acesso básico podem visualizar apenas o próprio painel de informações.

---

## 3.2. Tela Principal de Funcionários

### Como acessar

1. No menu lateral do sistema, clique em **Funcionários**.
2. A tela principal será exibida com todos os funcionários cadastrados.

### O que você vai encontrar nessa tela

A tela principal de funcionários é organizada em áreas que facilitam a visualização e o gerenciamento da equipe. Veja cada uma delas:

#### Indicadores no topo da página

No topo da tela, você encontra um resumo rápido com os principais números da equipe no período selecionado:

- **Total de Funcionários** — Quantos funcionários ativos estão cadastrados.
- **Horas Trabalhadas** — Soma de todas as horas trabalhadas pela equipe no período.
- **Horas Extras** — Total de horas extras acumuladas no período.
- **Faltas** — Quantidade de faltas registradas (tanto justificadas quanto não justificadas).
- **Custo Total** — Estimativa do custo com a mão de obra no período.
- **Taxa de Absenteísmo** — Percentual de ausências em relação aos dias úteis.

> **Dica:** Esses indicadores ajudam você a ter uma visão geral rápida da situação da equipe, sem precisar abrir o perfil de cada funcionário.

#### Como filtrar por período

Você pode ajustar o período dos indicadores e dados exibidos na tela:

1. Localize os campos de **Data Início** e **Data Fim** no topo da página.
2. Clique no campo **Data Início** e selecione a data desejada (por padrão, é o primeiro dia do mês atual).
3. Clique no campo **Data Fim** e selecione a data final (por padrão, é o dia de hoje).
4. Clique no botão **Filtrar** para atualizar os dados.

Os indicadores e as informações dos funcionários serão recalculados de acordo com o período escolhido.

#### Cards dos funcionários

Cada funcionário é exibido em um **card** (cartão visual) que mostra:

- **Foto do funcionário** — Se houver uma foto cadastrada, ela aparece no card. Caso contrário, será exibido um ícone com as iniciais do nome.
- **Nome completo** do funcionário.
- **Cargo ou função** que ele exerce.
- **Caixa de seleção** — Permite marcar vários funcionários para realizar ações em grupo.

---

## 3.3. Pesquisando e Filtrando Funcionários

A tela de funcionários oferece ferramentas de busca para facilitar a localização de qualquer pessoa da equipe:

### Busca por nome ou CPF

1. Localize o **campo de busca** na parte superior da lista de funcionários.
2. Digite o **nome**, o **CPF** ou o **código** do funcionário que você procura.
3. Os resultados serão filtrados automaticamente enquanto você digita.

> **Exemplo:** Se você digitar "João", todos os funcionários que tenham "João" no nome serão exibidos.

### Filtros disponíveis

Além da busca por texto, você pode usar os filtros para refinar a lista:

- **Departamento** — Selecione um departamento específico para ver apenas os funcionários daquele setor.
- **Função/Cargo** — Filtre por cargo ou função exercida.
- **Status** — Escolha entre ver funcionários **Ativos**, **Inativos** ou **Todos**.

Para usar os filtros:

1. Clique no filtro desejado (por exemplo, **Departamento**).
2. Selecione a opção na lista que aparece.
3. A lista de funcionários será atualizada automaticamente.

> **Dica:** Você pode combinar os filtros. Por exemplo, filtrar por departamento "Obras" e status "Ativo" para ver apenas quem está trabalhando atualmente no setor de obras.

### Operações em grupo

Depois de marcar vários funcionários usando as caixas de seleção nos cards, você pode realizar ações em grupo, como:

- Lançar registros de ponto para vários funcionários ao mesmo tempo.
- Alocar funcionários em uma obra.
- Exportar dados dos funcionários selecionados.

---

## 3.4. Cadastrando um Novo Funcionário

Para adicionar um novo funcionário ao sistema, siga o passo a passo abaixo:

### Passo a passo

1. Na tela de funcionários, clique no botão **+ Novo Funcionário**.
2. Um formulário será aberto na tela.
3. Preencha os campos conforme explicado nas seções a seguir.
4. Após preencher todos os dados, clique no botão **Salvar**.

### 3.4.1. Dados Pessoais

Preencha as informações pessoais do funcionário:

**Nome** *(obrigatório)*
- Digite o nome completo do funcionário.
- Exemplo: "João Carlos da Silva".

**CPF** *(obrigatório)*
- Digite os 11 números do CPF do funcionário.
- O sistema formata automaticamente (000.000.000-00).
- Cada CPF deve ser único — não é possível cadastrar dois funcionários com o mesmo CPF.

**RG**
- Digite o número do documento de identidade (RG) do funcionário.
- Este campo é opcional.

**Data de Nascimento**
- Selecione a data de nascimento do funcionário no calendário.
- Formato: dia/mês/ano (DD/MM/AAAA).

**Endereço**
- Digite o endereço completo do funcionário: rua, número, bairro, cidade, estado e CEP.
- Exemplo: "Rua das Flores, 123 - Centro - São Paulo/SP - CEP 01234-567".

**Telefone**
- Digite o número de telefone com DDD.
- Exemplo: (11) 99999-0000.

**E-mail**
- Digite o endereço de e-mail do funcionário.
- Este campo é opcional, mas útil para comunicações.

**Foto**
- Clique em **Escolher arquivo** para enviar uma foto do funcionário.
- Formatos aceitos: JPG ou PNG.
- Essa foto será exibida no card do funcionário e no perfil dele.

> **Importante sobre o CPF:** Se você digitar um CPF que já está cadastrado no sistema, uma mensagem de erro será exibida. Verifique se o funcionário já não está registrado antes de criar um novo cadastro.

### 3.4.2. Dados do Contrato de Trabalho

Preencha as informações sobre o vínculo de trabalho:

**Código do funcionário**
- Digite um código interno para identificar o funcionário (exemplo: VV001).
- Se você deixar este campo em branco, o sistema vai gerar um código automaticamente (VV001, VV002, VV003...).

**Data de Admissão** *(obrigatório)*
- Selecione a data em que o funcionário começou a trabalhar na empresa.
- Por padrão, o sistema preenche com a data de hoje.

**Salário**
- Digite o valor do salário mensal bruto do funcionário (em reais).
- Exemplo: 2.500,00.

**Departamento**
- Selecione o departamento ao qual o funcionário pertence.
- Exemplos: Administrativo, Obras, Manutenção, etc.

**Função/Cargo**
- Selecione a função ou cargo que o funcionário vai exercer.
- Exemplos: Pedreiro, Eletricista, Engenheiro, Auxiliar Administrativo, etc.

**Horário de Trabalho**
- Selecione o modelo de horário de trabalho do funcionário.
- Cada modelo define os horários de entrada, saída, pausas e dias da semana em que o funcionário trabalha.
- Se o funcionário tem uma jornada diferente, você poderá ajustar o horário individualmente depois (veja a seção 3.5.3).

> **Sobre o código automático:** Quando você não preenche o campo de código, o sistema cria automaticamente um código sequencial (VV001, VV002...). Isso é útil para manter a organização sem precisar se preocupar com a numeração.

> **Sobre os horários de trabalho:** Os modelos de horário de trabalho são configurados pelo administrador na área de **Configurações > Horários**. Eles permitem definir horários diferentes para cada dia da semana — por exemplo, sexta-feira com expediente reduzido ou sábado com meio período.

---

## 3.5. Perfil do Funcionário

### 3.5.1. Como acessar o perfil

Para ver todas as informações de um funcionário:

1. Na tela principal de funcionários, localize o funcionário desejado.
2. Clique no **card** (cartão) do funcionário ou diretamente no **nome** dele.
3. A página de perfil será aberta com todas as informações detalhadas.

### 3.5.2. O que você encontra no perfil

O perfil do funcionário está dividido em seções para facilitar a consulta:

#### Informações pessoais e contratuais

Todos os dados cadastrados do funcionário ficam visíveis nessa seção:

- Nome completo, CPF e RG
- Data de nascimento e endereço
- Telefone e e-mail
- Foto do funcionário (quando cadastrada)
- Departamento e função/cargo
- Data de admissão e salário
- Status atual (ativo ou inativo)

#### Indicadores de desempenho

O perfil exibe automaticamente os indicadores do funcionário para o período selecionado:

- **Horas Trabalhadas** — Total de horas que o funcionário trabalhou no período.
- **Horas Extras** — Total de horas extras realizadas.
- **Faltas** — Quantidade de faltas sem justificativa.
- **Faltas Justificadas** — Quantidade de faltas com atestado ou justificativa.
- **Atrasos** — Total de horas de atraso acumuladas.
- **Dias Trabalhados** — Quantidade de dias em que houve registro de ponto.
- **Taxa de Absenteísmo** — Percentual de faltas em relação aos dias úteis do período.
- **Valor da Hora** — Quanto vale cada hora de trabalho do funcionário, calculado com base no salário.
- **Valor das Horas Extras** — Custo total das horas extras realizadas.
- **DSR sobre Horas Extras** — Valor do Descanso Semanal Remunerado calculado sobre as horas extras.

> **O que é DSR?** O Descanso Semanal Remunerado (DSR) é um valor adicional pago sobre as horas extras, garantido por lei. O sistema calcula esse valor automaticamente para você.

#### Histórico de ponto

Uma tabela completa mostra todos os registros de ponto do funcionário no período, incluindo:

- Data do registro
- Horário de entrada
- Horário de saída para almoço
- Horário de retorno do almoço
- Horário de saída
- Total de horas trabalhadas no dia
- Horas extras (se houver)
- Tipo do registro (dia trabalhado, falta, feriado, etc.)
- Observações

#### Obras vinculadas

Lista todas as obras em que o funcionário está ou já esteve alocado, mostrando:

- Nome da obra
- Período em que trabalhou na obra
- Local de trabalho (campo ou escritório)

### 3.5.3. Editando as informações do funcionário

Para alterar qualquer dado cadastral do funcionário:

1. No perfil do funcionário, clique no botão **Editar**.
2. Os campos ficarão disponíveis para edição.
3. Faça as alterações necessárias.
4. Clique em **Salvar** para confirmar.

Você pode editar dados pessoais (nome, endereço, telefone) e dados contratuais (salário, departamento, função, horário de trabalho).

#### Configurando um horário personalizado

Se o funcionário tem uma jornada diferente do padrão do departamento:

1. No perfil do funcionário, localize a opção **Horário Personalizado** ou **Horário Padrão**.
2. Clique para abrir a configuração de horário individual.
3. Defina os horários de entrada, saída e intervalos para cada dia da semana.
4. Clique em **Salvar**.

> **Quando usar o horário personalizado?** Use quando um funcionário específico trabalha em um horário diferente dos demais colegas do mesmo departamento. Por exemplo, se o departamento de obras tem horário das 7h às 17h, mas um engenheiro trabalha das 8h às 18h.

---

## 3.6. Cadastro de Fotos para Reconhecimento Facial

### 3.6.1. Por que cadastrar fotos faciais?

O sistema utiliza reconhecimento facial para garantir que o ponto eletrônico seja registrado pela pessoa certa. Quando o funcionário bate o ponto, o sistema tira uma foto e compara com as fotos cadastradas para confirmar a identidade.

**Por que cadastrar mais de uma foto?**

Cadastrar várias fotos melhora muito a precisão do reconhecimento, porque o sistema consegue identificar o funcionário em diferentes situações do dia a dia:

- Uma foto com óculos e outra sem óculos
- Uma foto em ambiente claro e outra em ambiente com menos luz
- Uma foto de frente e outra levemente de lado

> **Resultado:** Quanto mais fotos cadastradas em condições variadas, mais rápido e preciso será o reconhecimento na hora de bater o ponto.

### 3.6.2. Como cadastrar fotos faciais

#### Acessando a tela de fotos

1. Acesse o perfil do funcionário (clicando no card dele na tela de funcionários).
2. No perfil, clique na opção **Fotos Faciais** ou **Gerenciar Fotos**.

#### Adicionando uma nova foto

1. Na tela de fotos faciais, clique no botão **Adicionar Foto**.
2. A câmera do seu dispositivo (computador, tablet ou celular) será ativada.
   - Se preferir, você também pode selecionar uma foto já existente no dispositivo.
3. Posicione o rosto do funcionário no centro da tela, de forma que o rosto fique bem visível.
4. Clique em **Capturar** (ou selecione o arquivo de imagem).
5. No campo **Descrição**, escreva uma identificação para a foto. Exemplos:
   - "Foto frontal sem óculos"
   - "Com óculos de grau"
   - "Com capacete de obra"
   - "Perfil lado esquerdo"
6. Clique em **Salvar** para concluir.

Repita esse processo para adicionar mais fotos do mesmo funcionário.

### 3.6.3. Dicas para fotos de qualidade

Siga estas orientações para garantir que o reconhecimento facial funcione da melhor forma:

#### Quantidade de fotos

- Cadastre **pelo menos 3 fotos** de cada funcionário.
- Quanto mais fotos, melhor a precisão.

#### Variações recomendadas

| Situação | O que cadastrar |
|---|---|
| Funcionário usa óculos | Uma foto **com** óculos e outra **sem** óculos |
| Funcionário tem barba | Atualize as fotos se houver mudança significativa (raspou a barba, deixou crescer) |
| Funcionário trabalha em obra | Uma foto **com** capacete/EPI e outra **sem** |
| Funcionário trabalha em ambientes variados | Fotos em diferentes condições de luz (escritório, ar livre) |

#### Cuidados com a iluminação

- Tire as fotos em um local **bem iluminado**, de preferência com luz natural.
- **Evite** fotos com flash direto no rosto — a luz forte pode atrapalhar o reconhecimento.
- **Evite** tirar fotos contra a luz (contraluz) — o rosto ficará escuro e o sistema pode não reconhecer.

#### Posicionamento correto

- O rosto deve estar **centralizado** na foto.
- O rosto deve ocupar a **maior parte** da imagem — não tire fotos de corpo inteiro.
- **Não cubra o rosto** com as mãos, máscara, boné ou outros objetos.

#### Expressão facial

- Prefira uma expressão **natural**, com o rosto relaxado.
- Evite caretas ou expressões muito exageradas.

> **O reconhecimento não está funcionando bem?** Se o sistema tem dificuldade em reconhecer um funcionário, tente cadastrar novas fotos em condições parecidas com o ambiente onde ele bate o ponto (mesma iluminação, com ou sem EPI, etc.).

---

## 3.7. Ponto Eletrônico — Registro de Ponto

O ponto eletrônico permite registrar os horários de entrada e saída dos funcionários. O sistema pode usar reconhecimento facial e localização para validar cada registro.

### 3.7.1. Como registrar o ponto

#### Passo a passo

1. No menu do sistema, clique em **Ponto**.
2. Selecione a opção **Registrar Ponto**.

3. **Selecione o funcionário:**
   - Se você é um gestor, selecione o nome do funcionário na lista.
   - Se o funcionário está logado no sistema, o nome dele já estará preenchido.

4. **Tire a foto para reconhecimento facial:**
   - A câmera do dispositivo será ativada automaticamente.
   - Posicione o rosto do funcionário de forma centralizada.
   - Clique em **Capturar**.

5. **Aguarde a validação:**
   - O sistema vai comparar a foto tirada com as fotos cadastradas do funcionário.
   - Se a foto corresponder, aparecerá uma mensagem de **confirmação** ✅.
   - Se a foto não corresponder, aparecerá uma mensagem de **erro** ❌. Nesse caso, tente novamente com melhor iluminação ou posicionamento.

6. **Validação de localização (quando aplicável):**
   - Se a obra possui localização cadastrada, o sistema verifica se o funcionário está próximo do local de trabalho.
   - Se estiver dentro do perímetro, a localização será validada ✅.
   - Se estiver fora do perímetro, um alerta será exibido ⚠️.

7. **Ponto registrado!**
   - Após as validações, o ponto é salvo automaticamente com o horário atual.

> **Dica:** O registro de ponto pode ser feito pelo celular, tablet ou computador. Basta acessar o sistema pelo navegador do dispositivo.

### 3.7.2. Tipos de registro de ponto

O sistema reconhece diferentes tipos de dias no registro de ponto:

| Tipo | O que significa |
|---|---|
| Dia trabalhado | Dia normal de trabalho |
| Falta | O funcionário não compareceu e não apresentou justificativa |
| Falta justificada | O funcionário não compareceu, mas apresentou justificativa (atestado médico, licença, etc.) |
| Feriado | Dia de feriado — sem trabalho |
| Feriado trabalhado | O funcionário trabalhou em um dia de feriado |
| Sábado (hora extra) | Trabalho realizado no sábado, contado como hora extra |
| Domingo (hora extra) | Trabalho realizado no domingo, contado como hora extra |

### 3.7.3. O que o sistema calcula automaticamente

Você não precisa fazer contas! O sistema calcula automaticamente:

- **Horas trabalhadas** — Com base nos horários de entrada e saída, descontando o intervalo de almoço.
- **Horas extras** — A diferença entre as horas trabalhadas e a jornada prevista no contrato.
- **Atrasos** — Se o funcionário chegou depois do horário de entrada previsto, o atraso é registrado.
- **DSR sobre horas extras** — O Descanso Semanal Remunerado sobre as horas extras é calculado conforme a legislação.

> **Sobre o almoço:** Se o funcionário trabalha mais de 6 horas, o sistema desconta automaticamente 1 hora de almoço do total de horas trabalhadas.

---

## 3.8. Consultando os Registros de Ponto

### Como acessar o controle de ponto

1. No menu do sistema, clique em **Ponto**.
2. Selecione a opção **Controle de Ponto**.

### Usando os filtros

A tela de controle de ponto permite filtrar os registros de diversas formas:

1. **Por funcionário** — Selecione um funcionário específico ou escolha "Todos" para ver a equipe toda.
2. **Por período** — Preencha os campos de **Data Início** e **Data Fim** para definir o período desejado.
3. **Por obra** — Selecione uma obra específica para ver apenas os registros daquela obra.
4. **Por tipo de registro** — Filtre por dia trabalhado, falta, feriado, etc.

Após selecionar os filtros, clique em **Filtrar** para atualizar a tabela.

### Entendendo a tabela de registros

A tabela exibe as seguintes informações para cada registro:

| Coluna | O que mostra |
|---|---|
| Data | A data do registro |
| Funcionário | O nome do funcionário |
| Entrada | Horário em que chegou ao trabalho |
| Saída Almoço | Horário em que saiu para almoçar |
| Retorno Almoço | Horário em que voltou do almoço |
| Saída | Horário em que encerrou o expediente |
| Horas Trabalhadas | Total de horas no dia (calculado automaticamente) |
| Horas Extras | Horas extras no dia (se houver) |
| Tipo | Tipo do registro (trabalhado, falta, feriado, etc.) |
| Reconhecimento | Indica se o rosto foi verificado ✅ ou não ❌ |
| Observações | Notas ou comentários sobre o registro |

### Editando um registro de ponto

Se for necessário corrigir um registro (por exemplo, o funcionário esqueceu de bater o ponto de saída):

1. Na tela de controle de ponto, localize o registro que precisa ser corrigido.
2. Clique no botão **Editar** (ícone de lápis) ao lado do registro.
3. O formulário de edição será aberto. Você pode alterar:
   - Horários de entrada, saída e almoço
   - Tipo do registro
   - Obra vinculada
   - Observações
4. Faça as correções necessárias.
5. Clique em **Salvar** para confirmar.

### Justificando uma falta

Se um funcionário faltou mas apresentou justificativa (atestado médico, por exemplo):

1. Na tela de controle de ponto, localize o registro de falta do funcionário.
2. Clique no botão **Editar** (ícone de lápis).
3. No campo **Tipo**, altere de "Falta" para **Falta Justificada**.
4. No campo **Observações**, descreva o motivo da justificativa.
   - Exemplo: "Atestado médico — consulta odontológica".
   - Exemplo: "Licença para acompanhar filho ao médico".
5. Clique em **Salvar**.

> **Por que justificar faltas?** Faltas sem justificativa podem afetar o cálculo do Descanso Semanal Remunerado (DSR) do funcionário. Quando a falta é justificada, o funcionário mantém o direito ao DSR integral.

---

## 3.9. Relatórios de Funcionários

### 3.9.1. Relatório individual em PDF

Para gerar um relatório completo de um funcionário específico:

1. Acesse o perfil do funcionário (clicando no card dele na tela de funcionários).
2. No perfil, ajuste o período desejado nos campos de **Data Início** e **Data Fim**.
3. Clique no botão **Gerar PDF** ou **Exportar PDF**.
4. O sistema vai gerar o documento e o download começará automaticamente.

#### O que o PDF inclui:

- **Dados cadastrais** — Nome, CPF, departamento, função, data de admissão, etc.
- **Indicadores do período** — Horas trabalhadas, horas extras, faltas, atrasos, custos.
- **Detalhamento financeiro** — Valor da hora, valor das horas extras, DSR, descontos.
- **Histórico de ponto** — Tabela com todos os registros de ponto do período.
- **Obras vinculadas** — Lista de obras em que o funcionário trabalhou.

> **Dica:** Esse relatório é muito útil para fechar a folha de pagamento, acompanhar produtividade individual ou apresentar informações para auditorias.

### 3.9.2. Indicadores consolidados da equipe

Na tela principal de funcionários, os indicadores no topo da página oferecem uma visão geral de toda a equipe:

| Indicador | O que mostra |
|---|---|
| Resumo de horas | Total de horas trabalhadas e horas extras por funcionário |
| Controle de faltas | Faltas, faltas justificadas e taxa de absenteísmo da equipe |
| Custo de mão de obra | Custo total com salários, horas extras e encargos |
| Produtividade | Horas trabalhadas por obra e eficiência da alocação |

### 3.9.3. Relatórios gerais

Para acessar relatórios mais detalhados:

1. No menu do sistema, clique em **Relatórios**.
2. Selecione a categoria **Funcionários** ou **Ponto**.
3. Configure os filtros:
   - **Período** — Selecione as datas de início e fim.
   - **Departamento** — Filtre por departamento específico (ou selecione "Todos").
   - **Função** — Filtre por cargo ou função (ou selecione "Todas").
   - **Obra** — Filtre por obra específica (ou selecione "Todas").
4. Clique em **Gerar Relatório**.
5. O relatório será exibido na tela e poderá ser exportado em PDF.

---

## 3.10. Perguntas Frequentes

**Posso cadastrar dois funcionários com o mesmo CPF?**
Não. O CPF é único para cada funcionário. Se você tentar cadastrar um CPF que já existe, o sistema não vai permitir e exibirá uma mensagem de erro.

**O que faço se o reconhecimento facial não está funcionando para um funcionário?**
Cadastre novas fotos faciais em condições parecidas com o ambiente onde o ponto é batido. Veja as dicas na seção 3.6.3 deste manual.

**Posso corrigir um ponto registrado com horário errado?**
Sim. Acesse o controle de ponto, localize o registro, clique em Editar e corrija os horários. Veja o passo a passo na seção 3.8.

**Como mudo o horário de trabalho de um funcionário específico?**
No perfil do funcionário, use a opção de horário personalizado para definir uma jornada diferente da padrão do departamento. Veja a seção 3.5.3.

**Preciso cadastrar fotos faciais para todos os funcionários?**
Recomendamos que sim. As fotos faciais garantem que o registro de ponto seja feito pela pessoa certa, evitando fraudes. Sem fotos cadastradas, o ponto poderá ser registrado sem verificação de identidade.

**Quantas fotos devo cadastrar por funcionário?**
Recomendamos pelo menos 3 fotos com variações (com óculos, sem óculos, diferentes iluminações). Quanto mais fotos, melhor a precisão do reconhecimento.

---

# Capítulo 4 — Gestão de Obras

## 4.1. Introdução

O módulo de **Gestão de Obras** é o coração do SIGE. É aqui que você cadastra, acompanha e controla todos os seus projetos de construção — do início ao fim. Neste capítulo, você vai aprender a:

- Visualizar todas as suas obras em um painel organizado
- Cadastrar novas obras com todas as informações importantes
- Acompanhar o andamento, os custos e a equipe de cada projeto
- Planejar e gerenciar os serviços que serão executados
- Criar Registros Diários de Obra (RDOs) diretamente pela tela de obras
- Gerar relatórios completos para tomada de decisão

> **Quem pode usar:** Administradores têm acesso total para cadastrar e gerenciar obras. Gestores de equipe e funcionários podem visualizar as obras onde estão alocados e registrar RDOs.

---

## 4.2. Tela Principal de Obras

### Como acessar

1. No menu lateral do sistema, clique em **Obras**.
2. A tela principal será exibida com todas as suas obras.

### O que você vai encontrar na tela

A tela de obras é dividida em três áreas principais: os **indicadores resumidos** no topo, os **filtros de pesquisa** e os **cards das obras**.

---

### Indicadores Resumidos (Topo da Página)

No topo da tela, você encontra um resumo rápido de todo o seu portfólio de obras:

| Indicador | O que significa |
|---|---|
| **Obras Ativas** | Quantas obras estão em andamento neste momento |
| **Obras Disponíveis** | Total de obras cadastradas no sistema |
| **Custo Total no Período** | Quanto foi gasto em todas as obras no período selecionado |
| **Funcionários Alocados** | Quantos funcionários estão trabalhando nas obras ativas |

Esses números atualizam automaticamente conforme você aplica filtros ou quando novos dados são registrados no sistema.

---

### Filtros de Pesquisa

Acima dos cards de obras, você encontra filtros para localizar rapidamente a obra que procura:

1. **Nome da Obra** — Digite o nome (ou parte dele) para buscar.
2. **Status** — Filtre por situação: *Em andamento*, *Concluída*, *Paralisada* ou *Cancelada*.
3. **Cliente** — Digite o nome do cliente para filtrar as obras dele.
4. **Data Início** — Selecione uma data para ver obras que começaram a partir dela.
5. **Data Fim** — Selecione uma data limite para o filtro.
6. Clique no botão **Filtrar** para aplicar os filtros.

Os indicadores do topo também são atualizados de acordo com os filtros aplicados, mostrando os dados apenas das obras que atendem aos critérios selecionados.

> **Dica:** Para ver todas as obras novamente, limpe os filtros e clique em **Filtrar**.

---

### Cards de Obras

Cada obra aparece na tela como um **card** (cartão visual), que funciona como um resumo rápido do projeto. Veja o que cada card mostra:

- **Nome da obra** — O nome que você deu ao projeto.
- **Código** — Código identificador único (ex.: O0001).
- **Status** — Situação atual da obra, com cor indicativa (verde para ativa, cinza para concluída, etc.).
- **Cliente** — Nome da empresa ou pessoa contratante.
- **Endereço** — Local onde a obra está sendo executada.
- **Datas** — Data de início e previsão de término.
- **Barra de progresso** — Mostra visualmente quanto da obra já foi concluído (em percentual).
- **Custos resumidos** — Custo total acumulado no período.
- **Dias trabalhados** — Quantos dias úteis foram registrados na obra.
- **Funcionários** — Quantos funcionários estão alocados.

Cada card possui dois botões importantes:

| Botão | O que faz |
|---|---|
| **+RDO** | Abre o formulário para criar um novo Registro Diário de Obra, já com essa obra selecionada |
| **Detalhes** | Abre a página completa da obra com todas as informações, gráficos e controles |

### Ordenação das Obras

As obras são organizadas automaticamente com as **mais recentes primeiro**. Obras em andamento geralmente aparecem no topo da lista.

---

## 4.3. Cadastrando uma Nova Obra

### Passo a passo

1. Na tela principal de obras, clique no botão **+ Nova Obra** (geralmente no canto superior direito).
2. O formulário de cadastro será aberto.
3. Preencha os campos conforme explicado abaixo.
4. Clique em **Salvar** para criar a obra.

Após salvar, o sistema levará você automaticamente para a página de detalhes da obra recém-criada.

---

### 4.3.1. Informações Básicas da Obra

Esses são os dados principais do seu projeto:

| Campo | O que preencher | Obrigatório? |
|---|---|---|
| **Nome** | Nome do projeto ou da obra (ex.: "Residencial Vila Nova", "Reforma Galpão Industrial") | Sim |
| **Código** | Um código único para identificar a obra (ex.: O0001). Se você deixar em branco, o sistema gera automaticamente | Não |
| **Endereço** | Endereço completo do canteiro de obras | Não |
| **Status** | Situação inicial da obra: *Em andamento*, *Concluída*, *Paralisada* ou *Cancelada*. Na maioria dos casos, selecione *Em andamento* | Sim |
| **Data de Início** | Quando a obra começou (ou vai começar) | Sim |
| **Previsão de Término** | Data estimada para entrega do projeto | Não |
| **Área Total (m²)** | Tamanho total da obra em metros quadrados | Não |
| **Responsável** | Selecione o engenheiro ou mestre de obras responsável pelo projeto (a lista mostra os funcionários cadastrados) | Não |

> **Dica:** Preencha o máximo de informações possível. Quanto mais completo o cadastro, mais preciso será o acompanhamento do projeto.

---

### 4.3.2. Dados do Cliente

Informe os dados da empresa ou pessoa que contratou a obra:

| Campo | O que preencher | Obrigatório? |
|---|---|---|
| **Nome do Cliente** | Nome da pessoa física ou empresa contratante | Não |
| **E-mail do Cliente** | E-mail de contato do cliente | Não |
| **Telefone do Cliente** | Telefone para contato | Não |
| **Portal Ativo** | Marque esta opção se deseja que o cliente possa acompanhar a obra pela internet. Ao ativar, o sistema gera automaticamente um link de acesso exclusivo para o cliente | Não |

> **Sobre o Portal do Cliente:** Quando ativado, o cliente recebe um link exclusivo para acompanhar o andamento da obra, visualizar fotos e acompanhar o progresso — sem precisar de login no sistema principal. Para isso, é necessário informar o e-mail do cliente.

---

### 4.3.3. Orçamento e Valores do Contrato

Esta é uma das seções mais importantes do cadastro. Aqui você define os valores financeiros do projeto:

| Campo | O que preencher | Obrigatório? |
|---|---|---|
| **Orçamento** | Quanto você estimou gastar para executar a obra (custos internos: mão de obra, materiais, equipamentos, etc.) | Não |
| **Valor do Contrato** | Quanto o cliente vai pagar pela obra (o valor fechado em contrato) | Não |

**Entendendo a diferença entre Orçamento e Valor do Contrato:**

- O **Orçamento** é o quanto você prevê gastar para executar a obra. É o seu custo interno.
- O **Valor do Contrato** é o quanto o cliente vai te pagar. É a sua receita.
- A diferença entre os dois é a sua **margem de lucro prevista**.

Por exemplo:
- Orçamento: R$ 800.000,00 (seus custos estimados)
- Valor do Contrato: R$ 1.000.000,00 (o que o cliente paga)
- Margem prevista: R$ 200.000,00 (20%)

O sistema acompanha os custos reais conforme a obra avança e compara com esses valores, alertando quando os gastos estão se aproximando ou ultrapassando o orçamento.

> **Importante:** Mesmo que você não tenha todos os valores definidos no momento do cadastro, preencha pelo menos o orçamento estimado. Você pode atualizar esses valores a qualquer momento editando a obra.

---

### 4.3.4. Geolocalização e Cerca Virtual

Se deseja controlar a presença dos funcionários no canteiro de obras pelo sistema de ponto, configure a localização:

| Campo | O que preencher | Obrigatório? |
|---|---|---|
| **Latitude** | Coordenada de latitude do local da obra | Não |
| **Longitude** | Coordenada de longitude do local da obra | Não |
| **Raio de Geofence (metros)** | Tamanho da "cerca virtual" ao redor da obra. O padrão é 100 metros | Não |

**Como funciona a cerca virtual (geofence):**

A cerca virtual é um recurso que verifica se o funcionário está realmente no local da obra quando registra o ponto. Funciona assim:

1. Você define as coordenadas (latitude e longitude) do centro do canteiro de obras.
2. Define um raio em metros (ex.: 100m, 200m, 500m — dependendo do tamanho da obra).
3. Quando o funcionário bate o ponto pelo celular, o sistema verifica se ele está dentro desse raio.

> **Como obter as coordenadas:** Abra o Google Maps, clique com o botão direito no local da obra e selecione "O que há aqui?". As coordenadas aparecerão na parte inferior da tela.

---

### 4.3.5. Serviços da Obra

Durante o cadastro, você já pode vincular os serviços que serão executados nesta obra:

1. Na seção **Serviços da Obra**, você verá a lista de serviços disponíveis (cadastrados previamente no módulo de Serviços).
2. Marque os serviços que fazem parte deste projeto (ex.: Concretagem, Alvenaria, Pintura, Instalação Elétrica).
3. Ao salvar a obra, os serviços selecionados serão vinculados automaticamente.

> **Nota:** Você também pode adicionar ou remover serviços depois, pela página de detalhes da obra. Não se preocupe em acertar tudo no primeiro cadastro.

---

## 4.4. Visualizando os Detalhes da Obra

### Como acessar

1. Na tela principal de obras, clique no botão **Detalhes** no card da obra desejada.
2. A página de detalhes será aberta com todas as informações do projeto.

A página de detalhes é o **painel de controle** da sua obra. Aqui você encontra tudo sobre o projeto em um só lugar.

---

### 4.4.1. Indicadores Principais (KPIs)

No topo da página de detalhes, você encontra os indicadores mais importantes da obra:

| Indicador | O que mostra |
|---|---|
| **Custo Total** | Quanto já foi gasto na obra até agora (somando tudo: mão de obra, alimentação, transporte e outros custos) |
| **Custo de Mão de Obra** | Quanto foi gasto com salários e horas extras dos funcionários nesta obra |
| **Custo de Alimentação** | Quanto foi gasto com refeições e alimentação da equipe |
| **Custos Diversos** | Outros gastos operacionais registrados (materiais, locações, etc.) |
| **Custo de Transporte** | Despesas com veículos utilizados na obra |
| **Dias Trabalhados** | Quantos dias de trabalho foram registrados na obra |
| **Funcionários Alocados** | Quantas pessoas trabalharam nesta obra |
| **Orçamento Restante** | Quanto ainda resta do orçamento (se ficar negativo, significa que os gastos ultrapassaram o previsto) |

Esses números são calculados automaticamente pelo sistema com base nos registros de ponto, alimentação, veículos e lançamentos de custos.

---

### 4.4.2. Composição de Custos

O sistema mostra como os custos da obra estão distribuídos entre as categorias:

| Categoria | De onde vem a informação |
|---|---|
| **Mão de Obra** | Calculada automaticamente com base nos registros de ponto dos funcionários (horas normais e extras) |
| **Alimentação** | Registros de refeições e marmitas fornecidas à equipe da obra |
| **Transporte** | Despesas com veículos que prestaram serviço para esta obra |
| **Diversos** | Custos avulsos que você lança manualmente (materiais, locações, etc.) |

Essa visão ajuda você a identificar onde está gastando mais e tomar decisões para otimizar os custos.

---

## 4.5. Planejamento de Serviços

### O que é o planejamento de serviços?

O planejamento de serviços define **o que** vai ser feito na obra e **quanto** de cada serviço será necessário. É como o escopo do projeto dividido em atividades mensuráveis.

### Como gerenciar os serviços de uma obra

1. Acesse a página de detalhes da obra.
2. Localize a seção **Serviços**.
3. Clique em **Gerenciar Serviços** para adicionar ou remover serviços.
4. Selecione os serviços que deseja vincular à obra.

### Informações de cada serviço

Para cada serviço vinculado à obra, você pode definir:

| Campo | O que preencher |
|---|---|
| **Serviço** | Nome da atividade (ex.: Concretagem, Alvenaria, Pintura, Instalações) |
| **Unidade de Medida** | Como o serviço é medido (metros quadrados, metros cúbicos, quilos, unidades, horas, etc.) |
| **Quantidade Planejada** | Quanto do serviço precisa ser executado no total (ex.: 500 m² de alvenaria) |
| **Valor Unitário (R$)** | Quanto custa cada unidade do serviço (ex.: R$ 45,00 por m²) |
| **Valor Total Planejado** | Calculado automaticamente: quantidade × valor unitário |
| **Data de Início Prevista** | Quando esse serviço deve começar |
| **Data de Término Prevista** | Quando esse serviço deve ser concluído |
| **Prioridade** | Nível de importância: Alta, Média ou Baixa |
| **Responsável** | Funcionário encarregado de executar esse serviço |
| **Status** | Situação: Não Iniciado, Em Andamento, Concluído ou Pausado |

### Acompanhamento automático da execução

Conforme os RDOs (Registros Diários de Obra) são preenchidos com as quantidades executadas, o sistema atualiza automaticamente:

- **Quantidade executada** — Soma de tudo que já foi feito daquele serviço.
- **Percentual concluído** — Quanto já foi feito em relação ao planejado (ex.: 350 m² de 500 m² = 70%).
- **Valor executado** — Quanto já foi gasto com aquele serviço até o momento.
- **Status automático** — O sistema muda o status conforme o progresso (0% = Não Iniciado, entre 1% e 99% = Em Andamento, 100% = Concluído).

Isso permite que você acompanhe o progresso de cada serviço sem precisar atualizar manualmente.

---

### Cronograma da Obra

O cronograma da obra é montado automaticamente a partir das datas dos serviços:

- As **datas de início e término** de cada serviço formam o cronograma geral.
- O sistema compara as datas planejadas com o que está sendo executado para identificar possíveis atrasos.
- A **data de previsão de término da obra** serve como referência para verificar se o projeto está dentro do prazo.

> **Dica:** Mantenha as datas dos serviços sempre atualizadas. Assim, o painel da obra reflete com precisão o andamento real do projeto.

---

## 4.6. Lançamento de Custos Diversos

Além dos custos automáticos (mão de obra, alimentação e transporte), você pode registrar outros gastos diretamente na obra.

### Como lançar um custo

1. Acesse a página de detalhes da obra.
2. Na seção **Custos**, clique em **Novo Lançamento**.
3. Preencha as informações:

| Campo | O que preencher |
|---|---|
| **Descrição** | O que foi o gasto (ex.: "Compra de material elétrico", "Locação de betoneira", "Aluguel de andaimes") |
| **Valor (R$)** | Quanto custou |
| **Data** | Quando o gasto aconteceu |
| **Categoria** | Tipo do custo para organização |
| **Observações** | Informações extras que julgar importantes |

4. Clique em **Salvar** para registrar o custo.

> **Bom saber:** Os custos de mão de obra são calculados automaticamente com base nos registros de ponto. Os custos de alimentação vêm do módulo de Alimentação. Você não precisa lançar esses valores manualmente — o sistema faz isso por você.

---

## 4.7. Controle Financeiro da Obra

O controle financeiro reúne todas as informações de custos e receitas do projeto para que você tenha uma visão clara da saúde financeira da obra.

### Orçado versus Realizado

O sistema compara continuamente o que foi planejado com o que está acontecendo de fato:

| Indicador | O que significa |
|---|---|
| **Valor Orçado** | O orçamento que você definiu no cadastro da obra (custo interno previsto) |
| **Valor do Contrato** | O valor que o cliente vai pagar pela obra (receita prevista) |
| **Custo Realizado** | Quanto já foi gasto de fato (soma de mão de obra + alimentação + transporte + custos diversos) |
| **Margem Bruta** | Valor do Contrato menos o Custo Realizado — é o lucro real até o momento |
| **Margem Percentual** | A margem em percentual (quanto maior, melhor para o seu negócio) |
| **Desvio Orçamentário** | Diferença entre o custo real e o orçamento — se positivo, significa que gastou mais que o previsto |
| **% do Orçamento Consumido** | Quanto do orçamento já foi utilizado |

### Alertas Automáticos

O sistema sinaliza automaticamente quando algo precisa de atenção:

| Situação | Sinal Visual | O que fazer |
|---|---|---|
| Gastos dentro do orçamento (abaixo de 80%) | 🟢 Verde | Tudo sob controle, continue acompanhando |
| Gastos se aproximando do limite (80% a 100%) | 🟡 Amarelo | Atenção! Revise as projeções de custo e avalie ajustes |
| Gastos acima do orçamento (mais de 100%) | 🔴 Vermelho | Ação urgente! Identifique onde estourou e tome medidas corretivas |
| Margem negativa (prejuízo) | 🔴 Vermelho | Situação crítica — renegocie o contrato ou reduza custos imediatamente |

### Fluxo de Caixa da Obra

O fluxo de caixa mostra o equilíbrio entre o que entra e o que sai na obra:

- **Entradas** — Parcelas do contrato recebidas do cliente (registradas no módulo Financeiro).
- **Saídas** — Todos os custos apurados (mão de obra, alimentação, transporte e outros).
- **Saldo** — A diferença entre entradas e saídas. Se negativo, significa que você está gastando mais do que recebendo.

> **Integração com o Financeiro:** Os lançamentos financeiros feitos no módulo **Financeiro** que estejam vinculados a esta obra são automaticamente considerados na análise. Acesse o módulo Financeiro pelo menu para registrar recebimentos e pagamentos.

---

## 4.8. Criando RDOs a partir da Obra

O **RDO (Registro Diário de Obra)** é o documento que registra tudo o que aconteceu na obra em cada dia de trabalho. Você pode criar um RDO diretamente pela tela de obras.

### Como criar um RDO rápido

1. Na tela principal de obras, localize a obra desejada.
2. Clique no botão **+RDO** que aparece no card da obra.
3. O formulário de RDO será aberto com a obra já selecionada automaticamente.
4. Preencha as informações do dia:

| Seção | O que registrar |
|---|---|
| **Mão de Obra** | Quais funcionários trabalharam, quantas horas cada um, qual função exerceu |
| **Equipamentos** | Quais equipamentos foram usados, por quanto tempo, se houve algum problema |
| **Serviços Executados** | Quais serviços foram realizados e as quantidades medidas (ex.: 25 m² de alvenaria) |
| **Ocorrências** | Eventos importantes: acidentes, paralisações, visitas técnicas, chuvas que impediram o trabalho |
| **Fotos** | Fotos do andamento da obra, de problemas encontrados ou de serviços concluídos |
| **Condições Climáticas** | Como estava o tempo (sol, nublado, chuva) e se isso afetou as atividades |

5. Clique em **Salvar** para registrar o RDO.

> **Para saber mais:** O preenchimento completo do RDO é explicado no **Capítulo 6 — Relatório Diário de Obra (RDO)**. Lá você encontra instruções detalhadas para cada seção do formulário.

---

## 4.9. Editando uma Obra

Precisa atualizar alguma informação da obra? É simples:

1. Na tela principal de obras, clique no botão **Detalhes** no card da obra.
2. Na página de detalhes, clique no botão **Editar**.
3. O formulário de edição será aberto com todos os dados atuais preenchidos.
4. Altere o que for necessário (nome, datas, orçamento, cliente, etc.).
5. Clique em **Salvar** para aplicar as alterações.

> **Dica:** Você pode editar o orçamento e o valor do contrato a qualquer momento. Isso é útil quando há aditivos contratuais ou revisões de escopo.

---

## 4.10. Alterando o Status da Obra

O status da obra indica a situação atual do projeto. Você pode alterá-lo rapidamente:

1. Acesse a página de detalhes da obra.
2. Clique no botão **Alterar Status**.
3. O sistema mudará o status da obra.

### Status disponíveis

| Status | Quando usar |
|---|---|
| **Em andamento** | A obra está em execução ativa, com equipe trabalhando |
| **Paralisada** | A obra foi temporariamente interrompida (aguardando aprovação, problema com fornecedor, chuvas prolongadas, etc.) |
| **Concluída** | A obra foi finalizada e entregue ao cliente |
| **Cancelada** | A obra foi cancelada definitivamente e não será retomada |

> **Bom saber:** Alterar o status de uma obra não apaga nenhum dado. Todos os registros de custos, RDOs e serviços são mantidos, independente do status. Você pode mudar o status de volta a qualquer momento.

---

## 4.11. Equipe da Obra

A equipe de cada obra pode ser definida de duas formas:

1. **Responsável técnico** — Definido diretamente no cadastro da obra (campo "Responsável"). Geralmente é o engenheiro ou mestre de obras.
2. **Equipe de campo** — Os funcionários são vinculados à obra através do módulo **Equipe** ou automaticamente quando registram ponto indicando que estão trabalhando naquela obra.

Para verificar quais funcionários estão alocados em uma obra, acesse a página de detalhes da obra e consulte a seção de equipe.

> **Dica:** Manter a equipe atualizada é importante para o cálculo correto dos custos de mão de obra e para os relatórios de produtividade.

---

## 4.12. Excluindo uma Obra

Se precisar excluir uma obra do sistema, siga estes passos:

1. Acesse a página de detalhes da obra.
2. Clique no botão **Excluir Obra**.
3. Uma mensagem de confirmação será exibida.
4. Confirme a exclusão.

> ⚠️ **Atenção — Leia antes de excluir!**
>
> A exclusão de uma obra é **permanente** e **não pode ser desfeita**. Ao excluir, serão removidos:
>
> - Todos os serviços vinculados à obra
> - Todos os custos diversos registrados
> - Todos os registros de alocação de equipe
>
> Os RDOs (Registros Diários de Obra) já criados são **mantidos** no sistema para fins de histórico e auditoria.
>
> **Recomendação:** Se a obra foi cancelada ou concluída, prefira **alterar o status** para *Cancelada* ou *Concluída* em vez de excluí-la. Assim você mantém todo o histórico para consultas futuras.

---

## 4.13. Relatórios de Obras

O sistema oferece relatórios completos para análise e documentação das suas obras.

### Tipos de relatórios disponíveis

| Relatório | O que contém |
|---|---|
| **Resumo Executivo** | Visão geral da obra: indicadores principais, progresso e situação financeira |
| **Relatório de Custos** | Detalhamento de todos os gastos por categoria e período |
| **Relatório de Serviços** | Comparação entre o que foi planejado e o que foi executado em cada serviço |
| **Relatório de Mão de Obra** | Lista de funcionários que trabalharam na obra, horas registradas e custos |
| **Relatório de RDOs** | Resumo de todos os Registros Diários de Obra do período |
| **Relatório Fotográfico** | Compilação de todas as fotos registradas nos RDOs |

### Como gerar um relatório

1. Acesse a página de detalhes da obra.
2. Clique em **Relatórios** ou **Gerar Relatório**.
3. Escolha o tipo de relatório que deseja.
4. Selecione o período de análise (data de início e data de fim).
5. Clique em **Gerar PDF**.
6. Aguarde o processamento e faça o download do arquivo.

> **Dica:** Para comparar resultados entre várias obras ao mesmo tempo, acesse o módulo **Relatórios** pelo menu lateral. Lá você encontra relatórios consolidados de todo o portfólio de projetos.

---

## 4.14. Dicas e Boas Práticas

Aqui vão algumas recomendações para aproveitar ao máximo o módulo de Gestão de Obras:

### Cadastro Completo
Preencha todos os campos possíveis no cadastro da obra, especialmente orçamento e valor do contrato. Isso permite que o sistema calcule margens e desvios automaticamente.

### RDOs Diários
Incentive sua equipe a preencher o RDO todos os dias. Quanto mais registros, mais preciso será o acompanhamento de custos e progresso.

### Acompanhamento Semanal
Reserve um momento da semana para verificar os indicadores de cada obra ativa. Os alertas de cores ajudam a identificar rapidamente quais obras precisam de atenção.

### Serviços Bem Planejados
Cadastre os serviços com quantidades e valores unitários realistas. Isso é a base para o acompanhamento do progresso e a identificação de desvios.

### Controle de Aditivos
Quando houver aditivos contratuais, atualize o valor do contrato e o orçamento na edição da obra. Assim os indicadores financeiros continuam refletindo a realidade do projeto.

### Portal do Cliente
Ative o portal do cliente para obras importantes. Isso demonstra transparência e profissionalismo, permitindo que o contratante acompanhe o andamento sem precisar ligar ou visitar a obra.

---

# Capítulo 5 — Gestão de Frota e Veículos

## 5.1. Introdução

Bem-vindo ao módulo de **Gestão de Frota** do SIGE! Este é o seu centro de controle para tudo que envolve os veículos da empresa. Aqui você pode:

- Cadastrar todos os veículos da sua frota (carros, caminhonetes, caminhões, vans, motos);
- Registrar cada viagem realizada — quem dirigiu, para onde foi, quantos quilômetros rodou e quem estava no veículo;
- Controlar todos os gastos — combustível, manutenção, pedágio, seguro, licenciamento, multas e muito mais;
- Acompanhar indicadores importantes como custo total, custo por quilômetro e quilometragem acumulada;
- Visualizar gráficos que mostram para onde está indo o dinheiro da frota;
- Ficar de olho nos vencimentos de licenciamento e seguro para não ter surpresas.

Para acessar o módulo, basta clicar em **Veículos** no menu do sistema.

> **Dica rápida:** O Dashboard principal do SIGE também mostra um resumo com a quantidade de veículos cadastrados na sua frota.

---

## 5.2. Visualizando a Lista de Veículos

Ao clicar em **Veículos** no menu, você verá a tela principal com todos os veículos cadastrados. Cada veículo aparece em formato de card, permitindo uma visão rápida do estado da sua frota.

### O que você vê em cada card de veículo

Cada card exibe as informações essenciais do veículo de forma resumida:

- **Placa** — A placa do veículo (pode ser no formato antigo ABC-1234 ou no formato Mercosul ABC1D23)
- **Modelo e Marca** — Por exemplo: "Hilux — Toyota" ou "Saveiro — Volkswagen"
- **Ano** — Ano de fabricação do veículo
- **Tipo** — Se é carro, caminhonete, caminhão, van, moto, etc.
- **Cor** — A cor do veículo
- **KM Atual** — A quilometragem mais recente registrada no odômetro
- **Status** — A situação atual do veículo

### Entendendo os status dos veículos

Os veículos são classificados com etiquetas coloridas para facilitar a identificação:

- 🟢 **Ativo** — O veículo está disponível e pronto para uso
- 🟡 **Em manutenção** — O veículo está temporariamente fora de operação (na oficina, por exemplo)
- 🔴 **Inativo** — O veículo não está sendo utilizado (vendido, baixado, parado definitivamente)

Essas etiquetas ajudam você a saber rapidamente quantos veículos estão disponíveis na sua frota.

### O que você pode fazer nesta tela

A partir da lista de veículos, você tem acesso a diversas ações:

1. **Cadastrar um novo veículo** — Clique no botão **Novo Veículo** no topo da página
2. **Ver os detalhes completos** — Clique no card de um veículo para acessar KPIs, gráficos e todo o histórico
3. **Editar os dados** — Atualize informações como placa, modelo, quilometragem ou status
4. **Registrar uma viagem** — Informe quem usou o veículo, para onde foi e quantos km rodou
5. **Lançar um custo** — Registre um abastecimento, uma manutenção, um pedágio ou qualquer outro gasto
6. **Excluir** — Remova o veículo do sistema (esta ação é restrita a administradores)

---

## 5.3. Cadastrando um Novo Veículo

Quando a empresa adquire um novo veículo ou você precisa incluir um veículo que já existia mas não estava no sistema, siga estes passos:

### Passo a passo

1. Acesse **Veículos** no menu
2. Clique no botão **Novo Veículo** (geralmente no canto superior da tela)
3. Preencha o formulário conforme orientações abaixo
4. Clique em **Salvar** para concluir o cadastro

### Seção 1: Dados do Veículo

Estes são os dados básicos de identificação:

- **Placa** *(obrigatório)* — Digite a placa do veículo. Pode ser no formato antigo (ABC-1234) ou no formato Mercosul (ABC1D23). Exemplo: *HXT-4A52*

- **Modelo** *(obrigatório)* — Informe o modelo do veículo. Exemplos: *Hilux, Saveiro, HR, Clio, Sprinter*

- **Marca** *(obrigatório)* — O fabricante do veículo. Exemplos: *Toyota, Volkswagen, Hyundai, Renault, Mercedes-Benz*

- **Ano** *(obrigatório)* — O ano de fabricação. Exemplo: *2022*

- **Tipo** *(obrigatório)* — Escolha a categoria que melhor descreve o veículo:
  - Carro
  - Caminhonete
  - Caminhão
  - Van
  - Moto
  - Outros

- **Cor** *(opcional)* — A cor predominante do veículo. Exemplo: *Branca, Prata, Preta*

- **KM Atual** *(opcional, mas recomendado)* — Informe a quilometragem atual que aparece no painel do veículo. Exemplo: *45.230*

- **Status** *(obrigatório)* — Selecione a situação inicial:
  - **Ativo** — Se o veículo está pronto para uso
  - **Em manutenção** — Se está na oficina
  - **Inativo** — Se não será utilizado no momento

> **Atenção:** Informe a quilometragem atual com a maior precisão possível! Esse número será usado como referência para validar os registros de viagens futuras. Se o veículo tiver 45.230 km no painel, informe exatamente esse valor.

### Seção 2: Documentação do Veículo

Registre os dados documentais para facilitar o controle de regularidade:

- **RENAVAM** *(opcional)* — O número do Registro Nacional de Veículos Automotores. Você encontra esse número no documento do veículo (CRV/CRLV). Exemplo: *00123456789*

- **Chassi** *(opcional)* — O número do chassi gravado na estrutura do veículo. Exemplo: *9BWHE21JX24060811*

- **Data de Licenciamento** *(opcional, mas recomendado)* — Quando vence o licenciamento anual do veículo. O sistema vai avisar quando estiver perto do vencimento para você não perder o prazo!

- **Vigência do Seguro** *(opcional, mas recomendado)* — Até quando vale a apólice de seguro do veículo. Assim como o licenciamento, o sistema vai alertar quando estiver próximo do vencimento.

> **Dica:** Mesmo que esses campos não sejam obrigatórios, preencha pelo menos as datas de licenciamento e seguro. Assim o sistema trabalha a seu favor, avisando antes que os documentos vençam!

### Seção 3: Configuração de Custo

- **Custo por KM** *(opcional)* — Se você sabe quanto custa, em média, cada quilômetro rodado por esse veículo, informe aqui. Esse valor ajuda nas comparações de eficiência entre os veículos da frota. Exemplo: *R$ 0,85/km*

### Após o cadastro

Depois de salvar, o veículo aparecerá imediatamente na lista principal e você já poderá:
- Registrar viagens
- Lançar custos
- Acompanhar os indicadores

---

## 5.4. Registrando o Uso do Veículo (Viagens)

Toda vez que um veículo sair para uma viagem ou deslocamento, é importante registrar no sistema. Esse controle permite saber quem usou cada veículo, para onde foi, quantos quilômetros rodou e quem estava junto.

### Passo a passo para registrar uma viagem

1. Na lista de veículos, localize o veículo que foi utilizado
2. Clique no botão **Registrar Uso** no card desse veículo
3. Preencha o formulário conforme as orientações abaixo
4. Clique em **Salvar** para confirmar o registro

### Campos do formulário de viagem

- **Veículo** *(preenchido automaticamente)* — Se você clicou no botão do card, o veículo já vem selecionado

- **Motorista/Condutor** *(obrigatório)* — Selecione na lista o funcionário que dirigiu o veículo. A lista mostra apenas funcionários ativos cadastrados no sistema

- **Data do Uso** *(obrigatório)* — Informe a data em que a viagem aconteceu. Exemplo: *15/01/2026*

- **Horário de Saída** *(opcional)* — Que horas o veículo saiu. Exemplo: *07:30*

- **Horário de Chegada** *(opcional)* — Que horas o veículo retornou. Exemplo: *17:45*

- **KM Inicial** *(obrigatório)* — A quilometragem que estava no painel do veículo no momento da saída. Exemplo: *45.230*

- **KM Final** *(obrigatório)* — A quilometragem que estava no painel quando o veículo voltou. Exemplo: *45.380*

- **Obra** *(opcional)* — Se o veículo foi para alguma obra específica, selecione a obra na lista. Isso é muito útil para depois saber quanto cada obra gastou com transporte

- **% Combustível** *(opcional)* — O nível do tanque de combustível no momento do registro. Útil para controlar o consumo

- **Passageiros (Frente)** *(opcional)* — Selecione os funcionários que foram no banco da frente (máximo 3 pessoas, incluindo o motorista)

- **Passageiros (Traseira)** *(opcional)* — Selecione os funcionários que foram no banco de trás (máximo 5 pessoas)

- **Observações** *(opcional)* — Qualquer informação adicional sobre a viagem. Exemplo: *"Entrega de materiais na obra do Parque Industrial"*

### Regras que o sistema verifica automaticamente

Para garantir a consistência dos dados, o sistema faz algumas verificações:

- O **KM Final** precisa ser maior que o **KM Inicial** — afinal, o veículo não anda para trás!
- O **KM Final** não pode ser menor que a última quilometragem registrada do veículo
- O mesmo funcionário não pode ser motorista e passageiro ao mesmo tempo
- O número máximo de passageiros na frente é 3 e na traseira é 5

> **Importante:** Após salvar o registro de uso, a quilometragem atual do veículo é atualizada automaticamente com o valor do KM Final. Você não precisa fazer isso manualmente!

### Consultando o histórico de viagens

Todas as viagens registradas ficam guardadas no sistema. Para consultá-las:

1. Clique no card do veículo desejado para abrir a tela de **Detalhes**
2. Role a página até a seção de **Histórico de Usos**
3. Você verá uma tabela organizada por data com todas as viagens, mostrando:
   - Data da viagem
   - Nome do motorista
   - KM de saída e chegada
   - Total de quilômetros percorridos
   - Obra de destino (quando informada)
   - Horários de saída e retorno
   - Lista de passageiros (separados por posição no veículo)

> **Dica:** Clique em qualquer viagem na tabela para ver todos os detalhes completos, incluindo a lista de passageiros organizada por posição (frente e traseira).

---

## 5.5. Controlando os Custos dos Veículos

Manter o controle financeiro da frota é essencial. O SIGE permite que você registre cada centavo gasto com os veículos, separando por categoria para facilitar a análise.

### Passo a passo para lançar um custo

1. Na lista de veículos, localize o veículo que teve a despesa
2. Clique no botão **Lançar Custo** no card desse veículo
3. Preencha o formulário conforme as orientações abaixo
4. Clique em **Salvar** para registrar o custo

### Campos do formulário de custo

- **Veículo** *(preenchido automaticamente)* — Se você clicou no botão do card, o veículo já vem selecionado

- **Tipo de Custo** *(obrigatório)* — Escolha a categoria da despesa:

  | Categoria         | Quando usar                                                    |
  |-------------------|----------------------------------------------------------------|
  | **Combustível**   | Abastecimentos (gasolina, diesel, etanol, GNV)                 |
  | **Manutenção**    | Revisões, troca de óleo, pneus, peças, reparos em geral       |
  | **Pedágio**       | Valores pagos em pedágios de rodovias                          |
  | **Seguro**        | Parcelas ou pagamento integral do seguro do veículo            |
  | **Licenciamento** | IPVA, taxas de licenciamento, emplacamento                     |
  | **Multa**         | Multas de trânsito recebidas                                   |
  | **Lavagem**       | Lavagem, higienização e limpeza do veículo                     |
  | **Outros**        | Qualquer despesa que não se encaixe nas categorias acima       |

- **Valor (R$)** *(obrigatório)* — O valor da despesa. Exemplo: *R$ 350,00*

- **Data** *(obrigatório)* — A data em que a despesa ocorreu. Exemplo: *20/01/2026*

- **Fornecedor** *(opcional)* — O nome do posto, oficina ou empresa que prestou o serviço. Exemplo: *Posto Shell BR-101* ou *Oficina do João*

- **Nota Fiscal** *(opcional)* — O número da nota fiscal, para controle contábil. Exemplo: *NF 004521*

- **Obra** *(opcional)* — Se o gasto foi relacionado a uma obra específica, selecione-a aqui. Isso permite saber depois quanto cada obra gastou com frota

- **Observações** *(opcional)* — Detalhes adicionais. Exemplo: *"Troca de 4 pneus dianteiros — desgaste por uso em estrada de terra"*

> **Dica:** Escolha sempre a categoria correta! Isso faz toda a diferença nos gráficos e relatórios. Se você colocar uma troca de óleo como "Outros" em vez de "Manutenção", o gráfico de distribuição de custos não vai refletir a realidade.

### Consultando o histórico de custos

Para ver todos os gastos de um veículo:

1. Clique no card do veículo para abrir a tela de **Detalhes**
2. Role até a seção de **Histórico de Custos**
3. Você verá uma tabela com todos os lançamentos, organizada do mais recente para o mais antigo:
   - Data do gasto
   - Tipo de custo (com indicador visual colorido por categoria)
   - Valor em reais
   - Fornecedor
   - Número da nota fiscal
   - Obra vinculada (quando informada)
   - Observações

> **Importante:** Você pode editar ou excluir um lançamento de custo caso tenha cometido algum erro. Basta clicar no registro desejado na tabela de histórico.

---

## 5.6. Painel de Detalhes do Veículo

O painel de detalhes é onde você encontra **tudo** sobre um veículo em um só lugar. Para acessá-lo, basta clicar no card do veículo na lista principal.

### 5.6.1. Indicadores de Desempenho (KPIs)

No topo da página, você encontra os números mais importantes do veículo:

**Custo Total (R$)**
Mostra a soma de **todos** os gastos registrados para esse veículo — combustível, manutenção, pedágio, seguro, tudo somado. É o valor total que esse veículo custou para a empresa.

*Exemplo: Se aparece R$ 12.450,00, significa que desde o primeiro lançamento até hoje, foram gastos doze mil quatrocentos e cinquenta reais com esse veículo.*

**Custo por KM (R$/km)**
Esse é um dos indicadores mais importantes para gestão de frota. Ele divide o custo total pela quilometragem total percorrida. Quanto menor esse número, mais econômico é o veículo.

*Exemplo: Se o custo por km é R$ 1,20, significa que cada quilômetro rodado custou, em média, um real e vinte centavos. Se outro veículo da frota tem custo de R$ 0,85/km, ele é mais econômico.*

**KM Total**
A quilometragem total acumulada pelo veículo desde que começou a ser registrado no sistema.

*Exemplo: 15.200 km significa que o veículo percorreu quinze mil e duzentos quilômetros nos registros de viagem.*

**Próximo Licenciamento**
Mostra a data prevista para o vencimento do licenciamento. Fique atento! Se essa data estiver próxima ou vencida, providencie a regularização o quanto antes.

*Exemplo: Se aparece "15/03/2026", significa que o licenciamento vence em março de 2026.*

> **Dica:** Você pode filtrar os indicadores por período! Use os campos de data inicial e data final para analisar os números de um mês específico, de um trimestre ou do período que quiser.

### 5.6.2. Entendendo os Gráficos

A tela de detalhes traz dois gráficos muito úteis para a gestão financeira da frota:

**Gráfico de Custos por Mês**

Este gráfico de barras mostra quanto foi gasto com o veículo em cada mês. Com ele você consegue:

- Ver se os gastos estão aumentando ou diminuindo ao longo dos meses
- Identificar meses com despesas fora do normal (um pico pode indicar uma manutenção grande, por exemplo)
- Comparar o padrão de gastos entre períodos diferentes
- Planejar o orçamento para os próximos meses com base no histórico

*Exemplo prático: Se você percebe que nos meses de janeiro e julho os custos sempre são maiores, pode ser porque coincidem com revisões programadas. Sabendo disso, você consegue se planejar financeiramente.*

**Gráfico de Custos por Categoria**

Este gráfico circular (pizza) mostra a distribuição percentual dos gastos por tipo. Com ele você descobre:

- Qual tipo de despesa mais pesa no bolso (combustível? manutenção?)
- Se existe alguma categoria de custo desproporcional
- Onde focar esforços para reduzir custos

*Exemplo prático: Se o gráfico mostra que 60% dos custos são com combustível e 25% com manutenção, você sabe que investir em rotas mais eficientes ou em veículos mais econômicos pode trazer uma boa economia.*

### 5.6.3. Dados Cadastrais

Nesta seção você encontra todas as informações do veículo que foram preenchidas no cadastro:

- Placa, modelo, marca, ano, tipo e cor
- RENAVAM e número do chassi
- Quilometragem atual
- Data de vencimento do licenciamento
- Data de vencimento do seguro
- Status atual (ativo, em manutenção ou inativo)
- Custo por km configurado

Para alterar qualquer uma dessas informações, clique no botão **Editar** disponível na tela.

### 5.6.4. Histórico Completo

Na parte inferior da tela de detalhes, você encontra o histórico completo de movimentação do veículo, dividido em duas seções:

- **Viagens/Usos** — Todas as viagens registradas com motorista, quilometragem, obra de destino e passageiros
- **Custos** — Todos os lançamentos financeiros com tipo, valor, data e fornecedor

Clique em qualquer registro para ver os detalhes completos ou para editar as informações.

---

## 5.7. Controle de Documentação e Alertas

Manter a documentação dos veículos em dia é fundamental para evitar problemas legais e multas. O SIGE ajuda você nessa tarefa!

### Licenciamento

Quando você cadastra a data de vencimento do licenciamento, o sistema passa a monitorar automaticamente. Na tela de detalhes do veículo, o indicador **Próximo Licenciamento** mostra claramente quando vence.

**O que fazer:**
1. Ao cadastrar o veículo, informe a data de vencimento do licenciamento
2. Verifique periodicamente o indicador na tela de detalhes
3. Quando estiver próximo do vencimento, providencie o pagamento do IPVA e das taxas de licenciamento
4. Após renovar, atualize a data no cadastro do veículo

### Seguro

Da mesma forma, o sistema acompanha a vigência do seguro do veículo.

**O que fazer:**
1. Ao cadastrar o veículo, informe a data de vencimento do seguro
2. Antes do vencimento, entre em contato com a seguradora para renovação
3. Após renovar, atualize a data no cadastro do veículo

### Alertas automáticos

O sistema gera avisos automáticos para situações que precisam de atenção:

- ⚠️ **Licenciamento próximo do vencimento** — Quando a data de licenciamento está chegando
- ⚠️ **Seguro próximo do vencimento** — Quando a apólice de seguro está perto de expirar
- ⚠️ **Veículo em manutenção prolongada** — Quando um veículo está com status "Em manutenção" há muito tempo

> **Dica:** Crie o hábito de verificar a tela de detalhes dos veículos pelo menos uma vez por semana. Assim você nunca será pego de surpresa com documentos vencidos!

---

## 5.8. Relatórios de Frota

O SIGE oferece relatórios que ajudam na tomada de decisões sobre a frota. Acesse-os pelo menu **Relatórios**.

### Relatório de Custos por Veículo

Apresenta um resumo dos gastos de cada veículo em um período que você escolhe. É ótimo para:

- Comparar qual veículo gasta mais
- Identificar veículos que estão dando muito custo de manutenção (pode ser hora de trocar!)
- Apresentar números para a diretoria

### Relatório de Utilização da Frota

Mostra com que frequência cada veículo é utilizado, quantos quilômetros rodou e quais motoristas o utilizaram. Serve para:

- Descobrir veículos que estão parados (subutilizados) — será que vale a pena mantê-los?
- Identificar veículos sobrecarregados que precisam de um substituto
- Verificar se a distribuição de uso está equilibrada

### Relatório de Custos por Obra

Quando você vincula os custos e viagens às obras, este relatório mostra quanto cada projeto gastou com frota. Muito útil para:

- Saber o custo real de transporte de cada obra
- Fazer o rateio correto das despesas entre os projetos
- Incluir os custos de frota no orçamento de futuras obras

---

## 5.9. Dicas Práticas para uma Boa Gestão de Frota

Aqui vão algumas recomendações para você tirar o máximo proveito do módulo de frota:

### 1. Registre tudo, sempre

Quanto mais informações você registrar, mais preciso será o controle. Peça aos motoristas que anotem o km de saída e chegada de cada viagem. Guarde todas as notas fiscais de abastecimento e manutenção.

### 2. Mantenha a quilometragem sempre atualizada

A quilometragem é a base para o cálculo do custo por km. Se os registros de viagem pularem números (por exemplo, de 45.000 para 48.000 sem registros intermediários), os indicadores perdem a precisão.

### 3. Classifique os custos corretamente

Na hora de lançar um custo, escolha a categoria certa. Não coloque tudo como "Outros"! Os gráficos e relatórios só serão úteis se os dados estiverem bem categorizados.

### 4. Vincule custos e viagens às obras

Sempre que possível, informe a obra relacionada. Isso permite calcular o custo real de transporte de cada projeto e fazer o rateio correto entre as obras.

### 5. Fique de olho nos vencimentos

Preencha as datas de licenciamento e seguro no cadastro de cada veículo. Verifique os alertas regularmente. Documento vencido pode gerar multas e até apreensão do veículo!

### 6. Registre todos os passageiros

O controle de quem estava no veículo (frente e traseira) é importante para:
- Conformidade com normas de segurança do trabalho
- Controle para o seguro (em caso de sinistro)
- Saber quem estava no veículo em determinada data

### 7. Analise os gráficos mensalmente

Reserve um tempo todo mês para olhar os gráficos de custos. Procure por:
- Gastos que estão crescendo sem motivo aparente
- Veículos com custo por km muito acima da média da frota
- Categorias de custo que podem ser reduzidas (será que dá para negociar o combustível?)

### 8. Compare os veículos entre si

Use o indicador de custo por km para comparar a eficiência dos veículos. Se um veículo está custando muito mais que os outros, investigue: pode ser hora de fazer uma revisão completa ou até considerar a substituição.

### 9. Planeje a manutenção preventiva

Acompanhe o histórico de manutenção de cada veículo. É mais barato fazer revisões preventivas do que esperar o veículo quebrar. Use as observações nos lançamentos para anotar quando deve ser feita a próxima revisão.

### 10. Mantenha o cadastro atualizado

Se um veículo foi vendido, mude o status para **Inativo**. Se está na oficina, mude para **Em manutenção**. Quando voltar, coloque como **Ativo** novamente. Assim a lista sempre reflete a realidade da sua frota.

---

## 5.10. Perguntas Frequentes

**Como altero a quilometragem de um veículo?**
A quilometragem é atualizada automaticamente quando você registra uma viagem. Se precisar corrigir manualmente, edite os dados cadastrais do veículo.

**Posso excluir um registro de viagem ou custo lançado errado?**
Sim! Acesse os detalhes do veículo, encontre o registro na tabela de histórico e clique para excluir ou editar.

**O que acontece se eu tentar registrar um KM Final menor que o KM Inicial?**
O sistema não permite. Vai aparecer uma mensagem de erro pedindo para você verificar os valores.

**Posso cadastrar um veículo que não tem placa ainda?**
A placa é um campo obrigatório. Se o veículo ainda não tem placa, use um identificador temporário e atualize depois.

**Como sei quanto cada obra gastou com veículos?**
Vincule os custos e viagens às obras. Depois, consulte o relatório de Custos por Obra no menu Relatórios.

**É possível ver o histórico de um veículo que já está inativo?**
Sim! Veículos inativos continuam no sistema com todo o histórico preservado. Basta acessar os detalhes normalmente.

---

# Capítulo 6 — Relatório Diário de Obra (RDO)

## 6.1. O que é o RDO?

O **Relatório Diário de Obra (RDO)** é o diário de bordo da sua obra. É nele que você, responsável pelo canteiro, registra tudo o que aconteceu no dia: quem trabalhou, que equipamentos foram usados, quais serviços avançaram, como estava o tempo e, claro, tira fotos para comprovar.

Pense no RDO como a **prestação de contas do dia**. Sem ele, fica difícil saber o que realmente aconteceu na obra — e mais difícil ainda cobrar resultados ou justificar atrasos.

### Por que preencher o RDO todo dia?

- **Memória da obra** — Daqui a seis meses, você não vai lembrar o que aconteceu num dia específico. O RDO lembra por você.
- **Progresso atualizado** — Quando o gestor aprova o RDO, o sistema atualiza automaticamente o andamento da obra. Sem RDO, o percentual de conclusão fica parado.
- **Comprovação para o cliente** — Fotos e registros do RDO servem como prova do que foi executado, facilitando medições e cobranças.
- **Registro de mão de obra** — Saber quem trabalhou e quantas horas ajuda no controle de custos e na folha de pagamento.
- **Proteção em caso de problemas** — Se houver questionamento sobre prazos, qualidade ou presença de equipe, o RDO é seu respaldo documental.
- **Controle de equipamentos** — Saber quais máquinas foram usadas e se eram próprias ou alugadas ajuda a controlar gastos operacionais.

> **Lembrete:** O RDO foi feito para ser preenchido pelo celular, direto do canteiro. Você não precisa esperar chegar no escritório para preencher!

### Como funciona o ciclo do RDO?

O caminho de um RDO é simples:

1. **Você cria** o RDO e preenche as informações do dia
2. **Você salva como rascunho** (se quiser terminar depois) ou **envia para aprovação**
3. **O gestor revisa** e aprova ou pede correções
4. **Quando aprovado**, o sistema atualiza automaticamente o progresso da obra

---

## 6.2. Visualizando a Lista de RDOs

### Como acessar

Para ver todos os RDOs registrados, vá pelo menu:

**Menu → RDO → Lista Consolidada**

Essa tela mostra todos os RDOs da sua empresa, organizados em uma tabela fácil de navegar.

### O que aparece na lista

Cada linha da tabela mostra um RDO com as seguintes informações:

- **Número do RDO** — Um código único gerado automaticamente (exemplo: RDO-10-2025-013)
- **Obra** — O nome da obra a que o RDO se refere
- **Data** — A data do relatório
- **Status** — A situação atual do RDO (veja os status abaixo)
- **Progresso** — O percentual de avanço dos serviços registrados naquele dia
- **Ações** — Botões para visualizar, editar ou excluir o RDO

### Filtrando RDOs

Se você tem muitos RDOs cadastrados, use os filtros para encontrar o que precisa:

1. **Por obra** — Escolha uma obra específica no seletor
2. **Por status** — Filtre por Rascunho, Em Elaboração, Pendente de Aprovação, Aprovado ou Reprovado
3. **Por período** — Defina uma data de início e uma data de fim para buscar RDOs de um intervalo específico
4. **Por responsável** — Filtre pelo nome de quem preencheu o RDO

### Entendendo os status

Cada RDO passa por diferentes fases. Veja o que cada status significa:

- 🔘 **Rascunho** — O RDO foi criado, mas ainda não está completo. Você pode continuar preenchendo depois.
- 🔵 **Em Elaboração** — O RDO está sendo preenchido com detalhes de serviços e mão de obra.
- 🟡 **Pendente de Aprovação** — O RDO foi finalizado e enviado para o gestor revisar.
- 🟢 **Aprovado** — O gestor revisou e aprovou. O progresso da obra já foi atualizado.
- 🔴 **Reprovado** — O gestor pediu correções. Você precisa ajustar e reenviar.

### Ações disponíveis

Na lista de RDOs, cada registro tem botões de ação:

- **Visualizar** — Abre o RDO completo, só para leitura. Bom para conferir informações.
- **Editar** — Abre o formulário para fazer alterações. Só funciona para RDOs em Rascunho ou Em Elaboração.
- **Excluir** — Remove o RDO por completo. Use com cuidado!

> **Dica rápida:** Na tela de Obras, cada obra tem um botão **"+RDO"** que já cria o RDO vinculado àquela obra. É o jeito mais rápido de começar!

---

## 6.3. Criando um Novo RDO — Passo a Passo

### Como começar

Você tem duas formas de criar um novo RDO:

**Opção 1 — Pela tela de RDOs:**
Clique no botão **"Novo RDO"** que aparece no topo da lista consolidada.

**Opção 2 — Pela tela de Obras (recomendado):**
Vá até a obra desejada e clique no botão **"+RDO"**. Assim, o formulário já vem com a obra selecionada e com as atividades do último RDO carregadas, economizando seu tempo.

### Passo 1 — Selecione a Obra

No campo **"Obra"**, escolha a obra para a qual você está fazendo o relatório do dia. Se você criou o RDO pelo botão "+RDO" da obra, esse campo já vem preenchido.

**Importante:** O sistema não permite criar dois RDOs para a mesma obra no mesmo dia. Se já existir um RDO para aquela data, você será redirecionado automaticamente para editar o RDO existente.

### Passo 2 — Defina a Data

O campo **"Data"** vem preenchido com a data de hoje, mas você pode alterar caso precise registrar um RDO de um dia anterior (por exemplo, se não conseguiu preencher ontem).

> **Dica de campo:** O ideal é preencher o RDO no final de cada dia de trabalho, enquanto as informações ainda estão frescas na memória. Deixar para o dia seguinte aumenta o risco de esquecer detalhes.

### Passo 3 — Informe as Condições Climáticas

Registrar o clima é obrigatório e muito importante. Chuva, calor excessivo ou tempo instável afetam diretamente a produtividade da equipe e podem justificar atrasos.

Preencha dois campos:

- **Condição Climática — Manhã:** Como estava o tempo de manhã? (Bom, Nublado, Chuvoso, etc.)
- **Condição Climática — Tarde:** Como estava o tempo à tarde?

Se quiser dar mais detalhes, use o campo **"Observações Meteorológicas"**. Por exemplo: *"Chuva forte entre 14h e 16h, paralisação parcial dos serviços externos."*

### Passo 4 — Registre a Mão de Obra

Aqui você informa quem trabalhou no canteiro naquele dia. Isso inclui tanto funcionários da sua empresa quanto terceirizados.

**Como adicionar um trabalhador:**

1. Clique no botão **"Adicionar Mão de Obra"**
2. **Selecione o funcionário** na lista. O sistema mostra os funcionários ativos da empresa, facilitando a busca.
3. **Informe a função** que ele exerceu no dia (pedreiro, servente, eletricista, etc.)
4. **Escolha o tipo:**
   - **Próprio** — funcionário da sua empresa
   - **Terceirizado** — funcionário de empreiteira ou subcontratado
5. **Informe as horas trabalhadas** no dia
6. Repita o processo para cada trabalhador presente

> **Dica:** Não esqueça de incluir os terceirizados! Muitas vezes, empreiteiros trazem equipe própria e é fundamental registrar essa presença para controle de custos e segurança.

**Exemplo prático:**

| Funcionário | Função | Tipo | Horas |
|------------|--------|------|-------|
| João Silva | Pedreiro | Próprio | 8h |
| Maria Santos | Servente | Próprio | 8h |
| Carlos (Empreiteira ABC) | Eletricista | Terceirizado | 6h |
| Pedro (Empreiteira ABC) | Ajudante | Terceirizado | 6h |

### Passo 5 — Registre os Equipamentos

Nesta seção, informe quais máquinas e equipamentos foram utilizados no dia.

**Como adicionar um equipamento:**

1. Clique no botão **"Adicionar Equipamento"**
2. **Descreva o equipamento** — Seja específico! Em vez de "retroescavadeira", escreva "Retroescavadeira CAT 416F"
3. **Informe a quantidade** — Quantas unidades foram utilizadas
4. **Escolha o tipo:**
   - **Próprio** — equipamento da empresa
   - **Alugado** — equipamento locado para a obra

**Exemplo prático:**

| Equipamento | Quantidade | Tipo |
|------------|:----------:|------|
| Retroescavadeira CAT 416F | 1 | Alugado |
| Betoneira 400L | 2 | Próprio |
| Vibrador de concreto | 1 | Próprio |
| Andaime metálico (conjunto) | 3 | Alugado |

> **Por que registrar equipamentos?** Equipamentos alugados representam custo diário. Registrar o uso ajuda a conferir faturas de locação e controlar gastos da obra.

---

## 6.4. Registrando Atividades e Serviços

Esta é a parte mais importante do RDO, pois é aqui que você informa o que foi efetivamente executado no dia. Esses dados alimentam diretamente o cálculo de progresso da obra.

### Como funciona a estrutura de serviços

Os serviços disponíveis no RDO são aqueles que já foram cadastrados na obra (no módulo de Serviços). Cada serviço pode ter várias **subatividades** — etapas menores que compõem o serviço completo.

**Exemplo:**
- **Serviço:** Alvenaria de Vedação
  - Subatividade 1: Marcação
  - Subatividade 2: Elevação 1º pavimento
  - Subatividade 3: Elevação 2º pavimento

### Preenchimento inteligente

O sistema facilita o seu trabalho:

- **No primeiro RDO da obra:** Todos os serviços cadastrados são carregados automaticamente, com suas subatividades
- **Nos RDOs seguintes:** O sistema traz os dados do último RDO, para que você só precise atualizar o que mudou

### Como registrar o avanço dos serviços

Para cada subatividade, informe:

1. **Quantidade executada** — Quanto foi feito no dia (em metros quadrados, metros cúbicos, unidades, etc., conforme a unidade do serviço)
2. **Percentual de conclusão** — Qual o percentual acumulado de conclusão daquela subatividade (de 0% a 100%)
3. **Observações** — Anote informações relevantes sobre a execução (opcional, mas recomendado)

**Exemplo prático:**

| Serviço | Subatividade | Executado Hoje | % Conclusão | Observações |
|---------|-------------|:--------------:|:-----------:|------------|
| Alvenaria de Vedação | Elevação 2º pav. | 45 m² | 75% | Falta parede do banheiro |
| Instalação Elétrica | Tubulação embutida | 30 m | 60% | Aguardando material para sala 3 |
| Pintura Interna | Massa corrida | 80 m² | 40% | Equipe reduzida por falta de EPIs |

> **Atenção com os percentuais!** O percentual é **acumulado**, não é só o que foi feito hoje. Se ontem a subatividade estava em 50% e hoje avançou mais 10%, o percentual deve ser informado como 60%.

### Como o progresso é calculado

O sistema calcula o progresso geral do RDO fazendo a média dos percentuais de todas as subatividades. Por exemplo:

- Subatividade A: 100%
- Subatividade B: 50%
- Subatividade C: 30%
- **Progresso do RDO: (100 + 50 + 30) ÷ 3 = 60%**

Esse valor, quando o RDO é aprovado, atualiza automaticamente o progresso geral da obra.

---

## 6.5. Tirando e Anexando Fotos

As fotos são fundamentais para comprovar o que foi executado. Clientes, gestores e auditores confiam muito mais em um RDO que tem registro fotográfico.

### Como anexar fotos

1. Na seção de fotos do RDO, clique no botão **"Adicionar Foto"**
2. **Tire a foto** diretamente pela câmera do celular ou **selecione uma foto** já salva na galeria
3. **Descreva a foto** — Escreva o que ela mostra (exemplo: "Concretagem da laje do 2º pavimento")
4. **Escolha o tipo** — Classifique a foto (serviço executado, material recebido, segurança, etc.)
5. Repita para quantas fotos forem necessárias

> O sistema otimiza automaticamente as fotos para que ocupem menos espaço, sem perder qualidade visual. Você não precisa se preocupar com o tamanho do arquivo.

### Dicas para tirar boas fotos no canteiro

Fotos bem tiradas fazem toda a diferença na hora da aprovação. Siga estas dicas:

📸 **Enquadramento** — Mostre o serviço de forma ampla, para que seja possível identificar o local e a etapa. Evite fotos muito de perto que não mostram contexto.

📸 **Iluminação** — Prefira tirar fotos com luz natural. Evite fotos contra o sol (contraluz).

📸 **Antes e depois** — Sempre que possível, tire uma foto do local antes de iniciar o serviço e outra depois. Isso mostra claramente o avanço.

📸 **Referências visuais** — Inclua elementos que ajudem a identificar o local, como pilares, marcações ou placas de eixo.

📸 **Segurança** — Registre também as condições de segurança: uso de EPIs, proteções coletivas, sinalizações.

📸 **Problemas encontrados** — Encontrou algo errado? Tubulação quebrada, material com defeito, área alagada? Fotografe e registre nas observações.

📸 **Quantidade** — Não economize nas fotos. É melhor ter fotos demais do que de menos. Registre pelo menos uma foto por serviço executado no dia.

---

## 6.6. Salvando e Enviando o RDO

Depois de preencher todas as informações, você tem duas opções:

### Opção 1 — Salvar como Rascunho

Clique no botão **"Salvar Rascunho"** quando:

- Você ainda não terminou de preencher todas as informações
- Quer revisar antes de enviar
- Precisa consultar algum dado antes de finalizar
- Vai completar o preenchimento em outro momento

O RDO ficará salvo com status **Rascunho** e você poderá voltar a editá-lo quando quiser.

### Opção 2 — Enviar para Aprovação

Quando tudo estiver preenchido e conferido, clique no botão **"Enviar para Aprovação"**.

Antes de enviar, passe por este checklist mental:

- ✅ Condições climáticas da manhã e da tarde estão preenchidas?
- ✅ Todos os trabalhadores presentes foram registrados com suas horas?
- ✅ Os equipamentos utilizados foram informados?
- ✅ Os serviços e subatividades estão com percentuais atualizados?
- ✅ As fotos dos serviços executados foram anexadas?
- ✅ As observações importantes foram registradas?

Após o envio, o RDO muda para o status **Pendente de Aprovação** e fica travado para edição até que o gestor aprove ou peça correções.

> **Atenção:** Depois de enviar para aprovação, você não consegue editar o RDO. Confira tudo antes de enviar! Se precisar fazer alguma correção, peça ao gestor para reprovar o RDO para que ele volte para edição.

---

## 6.7. Aprovação de RDOs (Para Gestores)

Se você é gestor ou administrador, esta seção explica como revisar e aprovar os RDOs enviados pela equipe de campo.

### Encontrando RDOs pendentes

1. Acesse a lista de RDOs pelo menu (**Menu → RDO → Lista Consolidada**)
2. Use o filtro de status e selecione **"Pendente de Aprovação"**
3. Os RDOs aguardando sua revisão aparecerão destacados com um indicador amarelo

### Como aprovar um RDO

1. Clique em **"Visualizar"** no RDO que deseja revisar
2. Confira todas as informações:
   - A mão de obra registrada está coerente com o que você sabe da obra?
   - Os percentuais de avanço fazem sentido com o histórico?
   - As fotos correspondem aos serviços declarados?
   - Os equipamentos informados estão corretos?
3. Se tudo estiver correto, clique no botão **"Aprovar RDO"**
4. Confirme na caixa de diálogo que aparecerá

**O que acontece quando você aprova:**
- O status do RDO muda para **Aprovado**
- O progresso da obra é atualizado automaticamente
- Os dados ficam disponíveis nos relatórios e no painel de controle
- Se a obra tem portal do cliente, o progresso atualizado aparece lá também

### Como reprovar um RDO

Se você encontrar algum problema no RDO:

1. Clique em **"Visualizar"** no RDO
2. Identifique o que precisa ser corrigido
3. Clique no botão **"Reprovar RDO"**
4. **Escreva o motivo da reprovação** no campo de observações — seja claro sobre o que precisa ser corrigido
5. O RDO volta para o responsável de campo, que poderá editar e reenviar

**Exemplos de motivos para reprovação:**

- *"Percentual de alvenaria informado como 80%, mas pela foto parece estar em torno de 60%. Favor verificar."*
- *"Faltou registrar a equipe do eletricista terceirizado que estava na obra hoje."*
- *"Não foram anexadas fotos da concretagem da laje. Favor adicionar."*

> **Boas práticas para gestores:** Revise os RDOs no mesmo dia ou no dia seguinte ao envio. Quanto mais rápido a aprovação, mais atualizado fica o acompanhamento da obra.

---

## 6.8. Como o RDO Atualiza o Progresso da Obra

Quando um RDO é aprovado pelo gestor, o sistema faz atualizações automáticas. Aqui está o que acontece, de forma simples:

### Progresso da obra

- O sistema pega os percentuais de conclusão informados nas subatividades do RDO
- Atualiza o andamento de cada serviço da obra
- Recalcula o progresso geral da obra
- Se um serviço atingiu 100%, ele é marcado como concluído

**Na prática:** Se você informou no RDO que a alvenaria do 2º pavimento está em 75%, ao aprovar o RDO, o progresso desse serviço na obra vai para 75%.

### Painel de controle (Dashboard)

- Os gráficos de evolução da obra são atualizados
- Os indicadores de desempenho refletem os novos dados
- Alertas são gerados se o progresso está abaixo do planejado

### Portal do Cliente

- Se a obra tem portal do cliente ativo, o progresso atualizado aparece automaticamente
- As fotos do RDO podem ficar disponíveis para o cliente visualizar
- O cliente acompanha a evolução sem precisar ir ao canteiro

### Controle financeiro

- As horas de mão de obra registradas alimentam o controle de custos
- Os equipamentos alugados são contabilizados nas despesas operacionais

> **Resumindo:** O simples ato de preencher e aprovar o RDO mantém toda a gestão da obra atualizada. Sem o RDO, os números ficam desatualizados e as decisões ficam prejudicadas.

---

## 6.9. Relatórios e Exportação

### Relatório Consolidado

O sistema permite gerar um relatório completo com dados de vários RDOs. É útil para reuniões com clientes, medições contratuais e análise de desempenho.

O relatório consolidado inclui:

- **Resumo de mão de obra** — Total de horas por funcionário, separado entre próprios e terceirizados
- **Resumo de equipamentos** — Quais equipamentos foram usados e com que frequência
- **Evolução do progresso** — Como os serviços avançaram ao longo do tempo
- **Histórico do clima** — Registro das condições climáticas (útil para justificar atrasos por chuva)
- **Galeria de fotos** — Todas as fotos organizadas por data

Para gerar o relatório, use os filtros de período, obra e status.

### Exportação em PDF

Cada RDO pode ser exportado individualmente como um arquivo PDF completo, contendo:

- Dados da obra e data do relatório
- Condições climáticas do dia
- Lista de trabalhadores e horas
- Lista de equipamentos
- Detalhamento dos serviços e subatividades
- Fotos com descrições
- Observações gerais

**Para exportar:**
1. Abra o RDO desejado clicando em **"Visualizar"**
2. Clique no botão **"Exportar PDF"** no topo da página
3. O arquivo será gerado e baixado automaticamente

> **Dica:** O PDF do RDO é muito útil para enviar ao cliente junto com as medições. É um documento profissional que comprova o trabalho realizado.

---

## 6.10. Dicas para Escrever Bons RDOs

Um RDO bem preenchido facilita a aprovação, evita retrabalho e serve como documento confiável. Siga estas recomendações:

### ✍️ Seja específico nas atividades

❌ *"Alvenaria"*
✅ *"Elevação de alvenaria de vedação no 2º pavimento, trecho entre eixos A e C"*

### 📊 Atualize os percentuais com cuidado

Não chute os percentuais. Avalie visualmente ou meça o que foi feito. Um percentual errado prejudica todo o planejamento da obra.

### 📝 Use as observações

O campo de observações é seu aliado. Registre:

- Motivos de paralisação (chuva, falta de material, falta de energia)
- Problemas encontrados (solo instável, tubulação danificada)
- Decisões tomadas em campo
- Visitas de fiscalização ou do cliente
- Recebimento de materiais importantes

### 📸 Capriche nas fotos

- Tire pelo menos uma foto por serviço executado
- Fotografe problemas e situações incomuns
- Registre condições de segurança
- Use a descrição para explicar o que a foto mostra

### ⏰ Preencha no mesmo dia

Preencher o RDO no mesmo dia em que o trabalho foi feito garante que as informações sejam precisas. Deixar para depois aumenta a chance de esquecer detalhes ou informar dados incorretos.

### 👷 Não esqueça ninguém

Registre todos os trabalhadores que estiveram no canteiro, incluindo terceirizados, estagiários e equipes de fornecedores. Isso é importante para controle de custos e, principalmente, para questões de segurança do trabalho.

### 🔄 Seja consistente

Mantenha um padrão de preenchimento. Use sempre os mesmos termos para descrever serviços e locais. Isso facilita a leitura e a busca nos relatórios futuramente.

---

# Capítulo 7 — Módulo Financeiro

## 7.1. Introdução ao Módulo Financeiro

O **Módulo Financeiro** do SIGE é o coração do controle de dinheiro da sua empresa. É aqui que você acompanha tudo o que entra e sai do caixa, controla as contas a pagar e a receber, e tem uma visão clara de como está a saúde financeira do seu negócio.

### O que você consegue fazer com o Módulo Financeiro?

- **Ver o resumo financeiro da empresa** — Um painel com os números mais importantes do seu caixa
- **Controlar contas a pagar** — Registrar boletos, notas fiscais e todas as despesas com fornecedores
- **Controlar contas a receber** — Registrar tudo o que seus clientes devem para você
- **Acompanhar o fluxo de caixa** — Ver o extrato completo de entradas e saídas de dinheiro
- **Gerar relatórios** — Entender o lucro ou prejuízo da empresa em cada período
- **Filtrar por obra** — Saber exatamente quanto cada obra está custando e gerando de receita

### Como acessar o Módulo Financeiro

Para acessar, clique no menu de navegação no topo da tela:

**Menu → Financeiro**

Ao clicar, você verá as seguintes opções:

- Dashboard Financeiro (visão geral)
- Contas a Pagar
- Contas a Receber
- Fluxo de Caixa
- Centros de Custo
- Relatórios

> **Dica:** O Dashboard Financeiro é a melhor tela para começar o dia. Em poucos segundos, você vê como está o caixa da empresa.

---

## 7.2. Dashboard Financeiro — Seu Painel de Controle

Ao abrir o Módulo Financeiro, a primeira coisa que você vê é o **Dashboard Financeiro**, um painel com os números mais importantes do período selecionado.

### O que cada número significa

O painel apresenta quatro indicadores principais no topo da tela:

| Indicador | O que significa | Exemplo |
|-----------|----------------|---------|
| **Total de Entradas** | Todo o dinheiro que entrou na empresa no período (pagamentos de clientes, recebimentos, etc.) | R$ 244.200,00 |
| **Total de Saídas** | Todo o dinheiro que saiu da empresa no período (pagamentos a fornecedores, custos, salários, etc.) | R$ 15.630,00 |
| **Saldo do Período** | A diferença entre o que entrou e o que saiu. Se o número for positivo, entrou mais do que saiu. Se for negativo, atenção: você gastou mais do que recebeu | R$ 228.570,00 |
| **Receitas Pendentes** | Valores que seus clientes ainda não pagaram. É o dinheiro que você tem para receber | R$ 244.200,00 |

> **Atenção:** "Receitas Pendentes" em valor alto pode significar que seus clientes estão demorando para pagar. Fique de olho!

### Gráfico de Entradas e Saídas

Logo abaixo dos indicadores, o sistema mostra um **gráfico** que compara as entradas e saídas ao longo do tempo. Esse gráfico é útil para:

1. Perceber em quais meses a empresa recebeu mais ou menos
2. Identificar meses em que os gastos foram maiores que o faturamento
3. Planejar os próximos meses com base no histórico

### Resumo de Custos por Categoria

O dashboard também mostra um resumo dos custos divididos por categoria. Isso ajuda a entender para onde o dinheiro está indo:

| Categoria | O que inclui |
|-----------|-------------|
| **Alimentação** | Custos com refeições das equipes de campo (gerados automaticamente pelo módulo de Alimentação) |
| **Transporte** | Despesas com veículos, combustível e manutenção (gerados automaticamente pelo módulo de Frota) |
| **Mão de Obra** | Salários e custos com pessoal |
| **Total** | Soma de todas as categorias |

> **Importante:** Os custos de **alimentação** e **transporte/veículos** aparecem automaticamente no financeiro. Quando você registra uma refeição no módulo de Alimentação ou um abastecimento no módulo de Frota, o valor já aparece aqui — sem precisar lançar duas vezes!

### Como filtrar os dados do Dashboard

Você pode ajustar os dados exibidos usando os filtros no topo da tela:

1. **Período** — Escolha a data inicial e a data final para ver os números de um intervalo específico (ex: o mês atual, o trimestre, o ano)
2. **Obra** — Selecione uma obra específica para ver apenas os números daquela obra
3. **Categoria** — Filtre para ver apenas um tipo de custo (ex: só alimentação, só transporte)

**Passo a passo para filtrar por período:**

1. Clique no campo **Data Inicial** e selecione a data de início
2. Clique no campo **Data Final** e selecione a data de término
3. Clique em **Filtrar** (ou o botão de busca)
4. Os indicadores e gráficos serão atualizados automaticamente

---

## 7.3. Contas a Pagar — Controlando suas Despesas

A seção de **Contas a Pagar** é onde você registra todas as contas e boletos que a empresa precisa pagar: fornecedores de material, prestadores de serviço, aluguel, energia elétrica, etc.

### 7.3.1. Como registrar uma nova despesa

**Passo a passo:**

1. No menu, clique em **Financeiro → Contas a Pagar**
2. Clique no botão **Nova Conta a Pagar**
3. Preencha as informações da conta:

| Campo | Obrigatório? | O que preencher |
|-------|:------------:|-----------------|
| **Fornecedor** | Sim | Selecione o fornecedor na lista. Se não existir, cadastre antes no módulo de Fornecedores |
| **Nº do Documento** | Não | Número do boleto, nota fiscal ou recibo |
| **Descrição** | Sim | Descreva o que está sendo pago (ex: "Cimento para Obra Solar", "Aluguel escritório Jan/2026") |
| **Valor** | Sim | Valor total da conta em reais (ex: R$ 5.000,00) |
| **Data de Emissão** | Sim | A data que aparece no boleto ou nota fiscal |
| **Data de Vencimento** | Sim | A data limite para pagar sem juros |
| **Obra** | Não | Se esse gasto é de uma obra específica, selecione a obra aqui |
| **Forma de Pagamento** | Não | Como vai pagar: boleto, transferência, PIX, dinheiro, etc. |
| **Observações** | Não | Qualquer informação extra que queira anotar |

4. Clique em **Salvar**

> **Dica:** Sempre vincule a despesa a uma **obra** quando possível. Assim, depois você consegue saber exatamente quanto cada obra está custando.

### 7.3.2. Como marcar uma conta como paga (baixar pagamento)

Quando você pagar um boleto ou conta, é importante registrar o pagamento no sistema. Assim, seus números ficam sempre atualizados.

**Passo a passo:**

1. Vá em **Financeiro → Contas a Pagar**
2. Na lista, encontre a conta que foi paga
3. Clique no botão **Baixar Pagamento** (ao lado da conta)
4. Preencha os dados do pagamento:
   - **Valor Pago** — Quanto foi pago (pode ser parcial ou total)
   - **Data do Pagamento** — A data em que o pagamento foi feito
   - **Forma de Pagamento** — Como pagou (PIX, boleto, dinheiro, etc.)
5. Clique em **Confirmar Baixa**

Pronto! O sistema atualiza tudo automaticamente:

- O valor que já foi pago
- O saldo restante (quanto falta pagar)
- O status da conta

### Entendendo os status das contas a pagar

| Status | O que significa |
|--------|----------------|
| **Pendente** | A conta ainda não foi paga |
| **Parcial** | Parte do valor foi pago, mas ainda falta um saldo |
| **Pago** | A conta foi paga integralmente — tudo certo! |
| **Vencido** | A data de vencimento já passou e a conta não foi paga (ou não foi paga totalmente) |

> **Atenção:** Contas com status **Vencido** aparecem em destaque na lista. Verifique diariamente para evitar juros e multas!

### 7.3.3. Visualizando e filtrando contas a pagar

A tela de Contas a Pagar mostra todas as suas contas em uma lista organizada com as seguintes informações:

- Nome do fornecedor
- Descrição da despesa
- Valor total da conta
- Quanto já foi pago
- Quanto falta pagar
- Data de vencimento
- Status atual (Pendente, Parcial, Pago ou Vencido)

**Filtros disponíveis para encontrar contas rapidamente:**

1. **Por status** — Veja apenas as contas pendentes, pagas, parciais ou vencidas
2. **Por fornecedor** — Busque contas de um fornecedor específico
3. **Por período de vencimento** — Veja contas que vencem em um intervalo de datas
4. **Por obra** — Veja apenas as contas de uma obra específica

> **Dica prática:** Todo início de semana, filtre as contas por "Pendente" e "Vencido" para saber exatamente o que precisa ser pago nos próximos dias.

---

## 7.4. Contas a Receber — Controlando suas Receitas

A seção de **Contas a Receber** é onde você registra tudo o que seus clientes devem pagar para a empresa: medições de obras, serviços prestados, vendas, etc.

### 7.4.1. Como registrar uma nova receita

**Passo a passo:**

1. No menu, clique em **Financeiro → Contas a Receber**
2. Clique no botão **Nova Conta a Receber**
3. Preencha as informações:

| Campo | Obrigatório? | O que preencher |
|-------|:------------:|-----------------|
| **Cliente** | Sim | Nome do cliente que vai pagar |
| **CPF/CNPJ** | Não | Documento do cliente (para controle) |
| **Nº do Documento** | Não | Número do contrato, nota fiscal ou fatura |
| **Descrição** | Sim | Descreva de onde vem essa receita (ex: "Medição 3 - Obra Residencial Solar") |
| **Valor** | Sim | Valor total a receber em reais (ex: R$ 85.000,00) |
| **Data de Emissão** | Sim | Data em que a cobrança foi emitida |
| **Data de Vencimento** | Sim | Data combinada para o cliente pagar |
| **Obra** | Não | Se é o pagamento de uma obra específica, selecione aqui |
| **Forma de Recebimento** | Não | Como vai receber: transferência, boleto, cheque, PIX, etc. |
| **Observações** | Não | Qualquer anotação extra |

4. Clique em **Salvar**

### 7.4.2. Como registrar que um cliente pagou (baixar recebimento)

Quando o cliente efetuar o pagamento, registre no sistema para manter o controle atualizado.

**Passo a passo:**

1. Vá em **Financeiro → Contas a Receber**
2. Na lista, encontre a conta que foi recebida
3. Clique no botão **Baixar Recebimento**
4. Preencha:
   - **Valor Recebido** — Quanto o cliente pagou (pode ser parcial ou total)
   - **Data do Recebimento** — A data em que o dinheiro caiu na conta
   - **Forma de Recebimento** — Como recebeu (PIX, transferência, boleto, cheque, etc.)
5. Clique em **Confirmar Baixa**

O sistema atualiza automaticamente o valor recebido, o saldo restante e o status.

### Entendendo os status das contas a receber

| Status | O que significa |
|--------|----------------|
| **Pendente** | O cliente ainda não pagou |
| **Parcial** | O cliente pagou uma parte, mas ainda deve um saldo |
| **Recebido** | O cliente pagou tudo — valor quitado! |
| **Vencido** | O prazo de pagamento já passou e o cliente não pagou (ou pagou parcialmente) |

> **Dica:** Contas com status **Vencido** precisam de atenção especial. Entre em contato com o cliente para negociar o pagamento.

### 7.4.3. Visualizando e filtrando contas a receber

A tela de Contas a Receber mostra uma lista com:

- Nome do cliente
- Descrição da receita
- Valor total a receber
- Quanto já foi recebido
- Quanto falta receber
- Data de vencimento
- Status atual

**Filtros disponíveis:**

1. **Por status** — Veja apenas os pendentes, parciais, recebidos ou vencidos
2. **Por cliente** — Busque cobranças de um cliente específico
3. **Por período de vencimento** — Veja cobranças que vencem em um intervalo de datas
4. **Por obra** — Veja apenas as cobranças de uma obra específica

---

## 7.5. Fluxo de Caixa — O Extrato da Sua Empresa

O **Fluxo de Caixa** funciona como o extrato bancário da sua empresa. Ele mostra todas as movimentações de dinheiro — tudo o que entrou e tudo o que saiu — em ordem cronológica.

### Como acessar o Fluxo de Caixa

Clique em **Financeiro → Fluxo de Caixa** no menu.

### O que você vê no Fluxo de Caixa

Cada linha do extrato mostra uma movimentação com as seguintes informações:

| Informação | O que significa |
|------------|----------------|
| **Data** | Quando a movimentação aconteceu |
| **Tipo** | Se é uma **Entrada** (dinheiro que entrou) ou **Saída** (dinheiro que saiu) |
| **Categoria** | De onde veio ou para onde foi (receita de obra, custo de veículo, alimentação, salário, etc.) |
| **Descrição** | Detalhes sobre a movimentação |
| **Valor** | Quanto foi movimentado |
| **Obra** | A qual obra essa movimentação está vinculada (quando aplicável) |

### Resumo do período

No final do extrato, o sistema mostra um resumo:

- **Total de Entradas** — Tudo o que entrou no período
- **Total de Saídas** — Tudo o que saiu no período
- **Saldo do Período** — A diferença (entradas menos saídas)

Se o saldo for positivo, sua empresa recebeu mais do que gastou. Se for negativo, os gastos superaram as receitas naquele período.

### Como filtrar o Fluxo de Caixa

Você pode refinar a visualização com os filtros:

1. **Período** — Escolha data inicial e final (ex: mês de janeiro, último trimestre)
2. **Tipo** — Veja apenas Entradas, apenas Saídas, ou Todos
3. **Categoria** — Filtre por um tipo específico (ex: só custos com veículos)
4. **Obra** — Veja apenas as movimentações de uma obra

**Exemplo prático:** Para saber quanto a Obra Residencial Solar gastou com veículos no mês de janeiro:

1. Selecione o período: 01/01/2026 a 31/01/2026
2. Selecione o tipo: Saídas
3. Selecione a categoria: Transporte/Veículos
4. Selecione a obra: Residencial Solar
5. Clique em Filtrar

> **Dica:** Use o fluxo de caixa semanalmente para conferir se não há nenhuma movimentação estranha ou lançamento esquecido.

---

## 7.6. De onde vêm os custos automáticos?

Uma das grandes vantagens do SIGE é que **vários custos aparecem automaticamente no Módulo Financeiro**, sem que você precise lançar manualmente. Isso acontece porque o sistema integra os dados de outros módulos:

### Custos de Obras

Quando materiais são comprados ou serviços são contratados para uma obra, esses custos aparecem no financeiro vinculados à obra correspondente. Assim, você sempre sabe quanto cada obra já consumiu de recursos.

### Custos de Veículos (Frota)

Sempre que um abastecimento, manutenção ou outra despesa com veículo é registrada no **módulo de Frota**, o custo aparece automaticamente no financeiro na categoria "Transporte".

### Custos de Alimentação

Quando refeições e marmitas são registradas no **módulo de Alimentação**, os custos são contabilizados automaticamente no financeiro na categoria "Alimentação".

### Custos de Mão de Obra

Os custos com salários e folha de pagamento registrados no **módulo de Folha de Pagamento** também são refletidos no financeiro.

> **Resultado:** Você tem uma visão real e completa dos custos da empresa, sem precisar lançar as mesmas informações em dois lugares diferentes. Se quiser ver o custo total de uma obra, basta filtrar o fluxo de caixa ou o dashboard pela obra — todos os custos (materiais, veículos, alimentação, mão de obra) estarão lá.

---

## 7.7. Centros de Custo — Organizando seus Gastos

Os **Centros de Custo** ajudam você a organizar as despesas da empresa por áreas. É como criar "pastas" para classificar para onde cada dinheiro foi.

### Tipos de Centro de Custo

| Tipo | Para que serve | Exemplo |
|------|---------------|---------|
| **Obra** | Agrupar todos os custos de uma obra | "Residencial Solar" |
| **Departamento** | Separar custos por setor da empresa | "Administrativo", "Operacional" |
| **Projeto** | Agrupar custos de projetos específicos | "Reforma sede" |

### Como criar um Centro de Custo

1. Acesse **Financeiro → Centros de Custo**
2. Clique em **Novo Centro de Custo**
3. Preencha:
   - **Código** — Um código curto para identificar (ex: CC001)
   - **Nome** — Nome descritivo (ex: "Obra Residencial Solar")
   - **Tipo** — Selecione: Obra, Departamento ou Projeto
   - **Descrição** — Detalhes adicionais (opcional)
   - **Obra associada** — Se for do tipo Obra, selecione a obra correspondente
4. Clique em **Salvar**

> **Dica:** Sempre que cadastrar uma nova obra no sistema, crie também um centro de custo para ela. Isso facilita muito na hora de gerar relatórios e saber quanto cada obra está custando.

---

## 7.8. Relatórios Financeiros — Entendendo os Números da Empresa

O SIGE oferece relatórios prontos para você entender a saúde financeira da empresa. Não é preciso ser contador para usá-los — eles foram feitos para serem simples e práticos.

### DRE — O Resultado da Sua Empresa (Lucro ou Prejuízo)

O **DRE** (Demonstrativo de Resultado do Exercício) é basicamente o **demonstrativo de lucro ou prejuízo da sua empresa**. Ele mostra, de forma organizada, quanto a empresa faturou, quanto gastou e qual foi o resultado final.

**Como ler o DRE em termos simples:**

| Linha do Relatório | O que significa na prática |
|--------------------|---------------------------|
| **(+) Receita Bruta** | Tudo o que a empresa faturou no período (total de serviços prestados, obras, vendas) |
| **(-) Impostos** | Os impostos que incidem sobre o faturamento |
| **(=) Receita Líquida** | O que sobra do faturamento depois de pagar os impostos |
| **(-) Custos Diretos** | Os custos diretamente ligados aos serviços/obras (materiais, mão de obra direta) |
| **(=) Lucro Bruto** | O que sobra depois de pagar os custos diretos — é a margem bruta do negócio |
| **(-) Despesas Operacionais** | Gastos para manter a empresa funcionando (aluguel, salários administrativos, energia, etc.) |
| **(=) Lucro Operacional** | O que sobra depois de pagar todas as despesas do dia a dia |
| **(=) Lucro Líquido** | O resultado final — é o lucro (ou prejuízo) real da empresa no período |

**Como gerar o DRE:**

1. Acesse **Financeiro → Relatórios → DRE**
2. Selecione o **mês e ano** que deseja analisar
3. Clique em **Gerar Relatório**

> **Dica:** Gere o DRE todo mês para acompanhar se a empresa está dando lucro ou prejuízo. Se o **Lucro Líquido** estiver negativo por vários meses seguidos, é hora de revisar custos ou aumentar o faturamento.

### Relatório de Contas a Pagar e Receber

Esse relatório mostra uma lista detalhada de todas as contas pendentes, pagas e vencidas. É muito útil para:

- Saber quanto a empresa deve pagar nos próximos dias
- Saber quanto tem para receber dos clientes
- Identificar clientes inadimplentes

**Filtros disponíveis:**

- **Por status** — Pendentes, Pagas/Recebidas ou Vencidas
- **Por período** — Escolha o intervalo de datas
- **Por fornecedor ou cliente** — Busque uma pessoa específica
- **Por obra** — Veja contas vinculadas a uma obra

### Relatório de Despesas por Centro de Custo

Esse relatório agrupa todas as despesas por centro de custo, mostrando:

- Qual centro de custo gastou mais
- Quanto cada obra ou departamento consumiu de recursos
- O percentual que cada centro de custo representa no total de despesas

É muito útil para comparar custos entre obras e identificar onde é possível economizar.

### Como exportar relatórios

Todos os relatórios podem ser:

- **Visualizados na tela** — Para consulta rápida
- **Exportados em PDF** — Para imprimir, enviar por e-mail ou guardar em arquivo

---

## 7.9. Dicas para Manter suas Finanças Organizadas

Aqui vão algumas dicas práticas para aproveitar ao máximo o Módulo Financeiro do SIGE:

### Rotina diária
- Registre **todas** as contas a pagar assim que receber o boleto ou nota fiscal. Não deixe para depois!
- Confira o **Dashboard Financeiro** todos os dias para ter uma visão rápida do caixa

### Rotina semanal
- Verifique as contas com status **Vencido** — tanto a pagar quanto a receber
- Faça a **baixa dos pagamentos** realizados durante a semana
- Confira o **Fluxo de Caixa** para garantir que todas as movimentações estão corretas

### Rotina mensal
- Gere o **DRE** para saber se a empresa teve lucro ou prejuízo no mês
- Analise o relatório de **Despesas por Centro de Custo** para identificar onde estão os maiores gastos
- Compare os custos por obra para entender quais projetos são mais rentáveis

### Boas práticas gerais

1. **Sempre vincule despesas a uma obra** — Isso permite rastrear o custo real de cada projeto
2. **Use descrições claras** — Em vez de "Material", escreva "Cimento CP-II 50kg - Obra Solar"
3. **Não acumule lançamentos** — Lance as despesas e receitas no mesmo dia em que acontecem
4. **Confira os custos automáticos** — Verifique se os custos de alimentação, veículos e mão de obra estão aparecendo corretamente
5. **Exporte relatórios mensais** — Guarde o PDF do DRE e do Fluxo de Caixa para ter um histórico organizado
6. **Crie centros de custo para cada obra** — Facilita muito a análise de rentabilidade por projeto

> **Lembre-se:** Um financeiro bem organizado não é luxo — é necessidade. Com os dados corretos no SIGE, você toma decisões melhores sobre preços, custos e investimentos.

---

# Capítulo 8 — Outros Módulos

Neste capítulo, apresentamos os demais módulos do SIGE que complementam as funcionalidades principais do sistema. Cada um deles atende a uma necessidade específica do dia a dia da sua empresa de construção.

---

## 8.1. Propostas Comerciais

O módulo de **Propostas Comerciais** permite criar, gerenciar e acompanhar orçamentos e propostas para novos projetos. Com ele, você organiza toda a parte comercial da empresa em um só lugar.

### Como acessar

No menu superior, clique em **Propostas**. Você verá a lista de todas as propostas já cadastradas.

### Criando uma nova proposta

1. Clique no botão **Nova Proposta**.
2. Preencha as informações principais:

| Campo | O que preencher |
|---|---|
| **Título** | Nome da proposta (ex.: "Proposta — Residencial Parque Sul") |
| **Cliente** | Nome da empresa ou pessoa para quem a proposta será enviada |
| **Data da Proposta** | A data de emissão da proposta |
| **Validade** | Até quando o cliente pode aceitar a proposta (ex.: 30 dias) |
| **Descrição** | Descreva o escopo do projeto, incluindo os principais serviços que serão prestados |
| **Valor Total** | O valor total da proposta em reais |
| **Observações** | Condições de pagamento, prazos, exclusões ou qualquer informação adicional |

3. Clique em **Salvar**.

### Usando modelos de proposta

O sistema pode carregar informações de propostas anteriores para você reaproveitar. Isso economiza tempo quando você precisa criar propostas semelhantes para diferentes clientes. Basta selecionar uma proposta existente como base e ajustar os valores e descrições.

### Gerando o PDF da proposta

Após criar e revisar a proposta, você pode gerar um documento profissional em PDF:

1. Abra a proposta desejada clicando nela na lista.
2. Clique no botão **Gerar PDF**.
3. O sistema vai criar um documento formatado com o logo da empresa, os dados do cliente, o escopo, os valores e as condições.
4. O PDF será baixado automaticamente para o seu computador ou celular.

> **Dica:** Revise o PDF antes de enviar ao cliente. Confira se o valor, o escopo e as condições estão corretos.

### Compartilhando a proposta com o cliente

Você pode enviar a proposta ao cliente de duas formas:

- **Por e-mail** — Envie o PDF gerado como anexo no e-mail.
- **Por link** — O sistema gera um link exclusivo que você pode compartilhar com o cliente. Ao acessar o link, o cliente visualiza a proposta diretamente no navegador, sem precisar de login.

### Acompanhando os status das propostas

| Status | O que significa |
|---|---|
| **Rascunho** | A proposta está sendo elaborada e ainda não foi enviada |
| **Enviada** | A proposta foi enviada ao cliente e aguarda resposta |
| **Aprovada** | O cliente aceitou a proposta |
| **Rejeitada** | O cliente não aceitou a proposta |
| **Expirada** | O prazo de validade da proposta venceu sem resposta |

Para alterar o status, abra a proposta e clique no botão correspondente (ex.: **Marcar como Enviada**, **Marcar como Aprovada**).

> **Dica:** Quando uma proposta for aprovada, você pode criar a obra correspondente diretamente a partir dos dados da proposta, agilizando o processo.

---

## 8.2. Alimentação

O módulo de **Alimentação** permite controlar todas as refeições fornecidas aos funcionários durante o trabalho. Os custos registrados aqui são automaticamente vinculados às obras correspondentes e aparecem no módulo Financeiro.

### Como acessar

No menu superior, clique em **Alimentação**.

### Registrando refeições

1. Clique no botão **Novo Registro** ou **Nova Refeição**.
2. Preencha as informações:

| Campo | O que preencher |
|---|---|
| **Data** | A data em que a refeição foi fornecida |
| **Obra** | Selecione a obra para a qual a refeição foi destinada |
| **Tipo de Refeição** | Café da manhã, Almoço, Jantar ou Lanche |
| **Quantidade** | Número de refeições fornecidas |
| **Valor Unitário** | Quanto custou cada refeição (ex.: R$ 18,00) |
| **Fornecedor** | Quem forneceu a refeição (restaurante, marmitaria, etc.) |
| **Observações** | Informações adicionais (ex.: "Marmita para equipe de 8 pessoas") |

3. Clique em **Salvar**.

O sistema calcula automaticamente o **valor total** (quantidade × valor unitário) e vincula o custo à obra selecionada.

### Acompanhando os custos de alimentação

Na tela principal do módulo, você encontra:

- **Resumo do período** — Total gasto com alimentação no período selecionado
- **Custo por obra** — Quanto cada obra gastou com refeições
- **Histórico de registros** — Lista de todas as refeições registradas, com filtros por data, obra e tipo de refeição

### Gerando relatórios de alimentação

1. Acesse a tela de Alimentação.
2. Use os filtros para selecionar o período e a obra desejados.
3. Clique em **Gerar Relatório** ou **Exportar PDF**.
4. O relatório mostrará o detalhamento dos custos com alimentação, incluindo totais por obra e por tipo de refeição.

> **Bom saber:** Os custos de alimentação registrados aqui aparecem automaticamente no Dashboard, nos detalhes da obra e no módulo Financeiro. Você não precisa lançar esses valores manualmente em outros módulos.

---

## 8.3. Almoxarifado

O módulo de **Almoxarifado** permite controlar todo o estoque de materiais, ferramentas e EPIs (Equipamentos de Proteção Individual) da empresa. Com ele, você sabe exatamente o que tem disponível, o que foi entregue e para quem.

### Como acessar

No menu superior, clique em **Almoxarifado**. Você verá as seguintes opções:

- **Estoque** — Visualizar todos os itens cadastrados e suas quantidades
- **Movimentações** — Registrar entradas, saídas e devoluções
- **Requisições** — Controlar pedidos de material feitos pelas equipes

### Cadastrando itens no estoque

1. Acesse **Almoxarifado → Estoque**.
2. Clique em **Novo Item**.
3. Preencha as informações:

| Campo | O que preencher |
|---|---|
| **Nome** | Nome do material, ferramenta ou EPI (ex.: "Capacete de segurança", "Furadeira Bosch", "Cimento CP-II 50kg") |
| **Categoria** | Tipo do item: Material, Ferramenta ou EPI |
| **Unidade de Medida** | Como o item é contado (unidade, kg, metro, saco, etc.) |
| **Quantidade em Estoque** | Quantidade atual disponível |
| **Estoque Mínimo** | Quantidade mínima desejada — o sistema avisa quando o estoque ficar abaixo desse valor |
| **Localização** | Onde o item está guardado (ex.: "Prateleira A3", "Galpão principal") |

4. Clique em **Salvar**.

### Registrando movimentações (entradas, saídas e devoluções)

Toda vez que um material entrar ou sair do estoque, registre a movimentação:

**Para registrar uma saída (entrega de material):**

1. Acesse **Almoxarifado → Movimentações**.
2. Clique em **Nova Movimentação**.
3. Selecione o tipo: **Saída**.
4. Selecione o **item** que está saindo do estoque.
5. Informe a **quantidade** entregue.
6. Selecione o **funcionário** que está recebendo o item.
7. Selecione a **obra** de destino (quando aplicável).
8. Clique em **Salvar**.

**Para registrar uma entrada (recebimento de material):**

Siga o mesmo processo, mas selecione o tipo **Entrada** e informe o fornecedor de origem.

**Para registrar uma devolução:**

Quando um funcionário devolver uma ferramenta ou EPI, registre como **Devolução**. O sistema atualizará o estoque automaticamente.

### Controlando quem está com o quê

O sistema mantém um registro completo de todos os itens que foram entregues a cada funcionário. Para consultar:

1. Acesse **Almoxarifado → Movimentações**.
2. Filtre por **funcionário** para ver todos os itens que estão em posse dele.
3. Você pode verificar se há ferramentas ou EPIs pendentes de devolução.

> **Dica:** Esse controle é muito importante para EPIs. Você pode comprovar que entregou os equipamentos de segurança necessários a cada funcionário, o que é fundamental para a conformidade com as normas de segurança do trabalho.

### Alertas de estoque baixo

Quando a quantidade de um item ficar abaixo do **estoque mínimo** cadastrado, o sistema exibe um alerta visual para que você providencie a reposição antes que o material acabe.

---

## 8.4. Equipe

O módulo de **Equipe** permite organizar seus funcionários em equipes de trabalho e alocá-los nas obras. Com ele, você tem controle sobre quem está trabalhando em cada projeto.

### Como acessar

No menu superior, clique em **Equipe**.

### Gerenciando equipes

Na tela principal, você visualiza as equipes cadastradas e seus membros. Para cada equipe, é possível ver:

- **Nome da equipe** — Identificação do grupo (ex.: "Equipe de Alvenaria", "Equipe Elétrica")
- **Líder da equipe** — O encarregado ou responsável pelo grupo
- **Membros** — Lista de funcionários que fazem parte da equipe
- **Obra vinculada** — Em qual obra a equipe está alocada

### Criando uma nova equipe

1. Clique em **Nova Equipe**.
2. Defina o **nome** da equipe.
3. Selecione o **líder** (encarregado) da equipe na lista de funcionários.
4. Adicione os **membros** da equipe, selecionando os funcionários desejados.
5. Vincule a equipe a uma **obra**, se aplicável.
6. Clique em **Salvar**.

### Alocando funcionários em projetos

Para mover um funcionário de uma obra para outra ou alterar a composição de uma equipe:

1. Abra a equipe desejada.
2. Adicione ou remova membros conforme necessário.
3. Altere a obra vinculada, se for o caso.
4. Clique em **Salvar**.

> **Dica:** Manter as equipes atualizadas ajuda na precisão dos relatórios de mão de obra e no cálculo dos custos por obra. Quando um funcionário é alocado a uma obra, os registros de ponto dele podem ser automaticamente vinculados a essa obra.

---

## 8.5. Relatórios

O módulo de **Relatórios** é o centro de informações consolidadas do SIGE. Aqui você acessa todos os relatórios disponíveis no sistema, reunidos em um só lugar.

### Como acessar

No menu superior, clique em **Relatórios**.

### Tipos de relatórios disponíveis

| Categoria | Relatórios disponíveis |
|---|---|
| **Obras** | Resumo executivo, custos por obra, progresso dos serviços, comparativo entre obras |
| **Funcionários** | Horas trabalhadas, horas extras, faltas e absenteísmo, custo de mão de obra |
| **Ponto** | Frequência por funcionário, resumo de ponto por período, horas extras detalhadas |
| **Financeiro** | DRE, contas a pagar/receber, fluxo de caixa, despesas por centro de custo |
| **Frota** | Custos por veículo, utilização da frota, custos por obra |
| **Alimentação** | Custos com refeições por obra e por período |
| **RDO** | Relatórios consolidados de obra, evolução de progresso, histórico climático |

### Como gerar um relatório

1. Selecione a **categoria** do relatório desejado.
2. Escolha o **tipo** de relatório dentro da categoria.
3. Aplique os **filtros** disponíveis:
   - **Período** — Data de início e data de fim
   - **Obra** — Selecione uma obra específica ou "Todas"
   - **Departamento** — Filtre por setor (quando aplicável)
   - **Funcionário** — Filtre por pessoa (quando aplicável)
4. Clique em **Gerar Relatório**.
5. O relatório será exibido na tela.

### Exportando relatórios

Todos os relatórios podem ser exportados para consulta offline ou impressão:

- **PDF** — Clique no botão **Exportar PDF** para gerar um documento formatado, pronto para imprimir ou enviar por e-mail.
- **Excel** — Quando disponível, clique em **Exportar Excel** para baixar os dados em formato de planilha, permitindo fazer cálculos e análises adicionais.

> **Dica:** Crie uma rotina mensal de geração de relatórios. Exporte o DRE, o relatório de custos por obra e o resumo de ponto todo mês e guarde em uma pasta organizada. Isso facilita muito quando você precisa consultar dados históricos ou apresentar resultados em reuniões.

---

# Capítulo 9 — Dúvidas Frequentes e Suporte

Este capítulo reúne as perguntas mais comuns sobre o uso do SIGE, dicas práticas para o dia a dia e informações sobre como obter suporte.

---

## 9.1. Perguntas Frequentes

Abaixo estão as dúvidas mais comuns dos usuários do SIGE e suas respostas:

| # | Pergunta | Resposta |
|:-:|----------|----------|
| 1 | **Não consigo fazer login. O que faço?** | Verifique se o nome de usuário (ou e-mail) e a senha estão corretos. Confira se o Caps Lock não está ativado. Se ainda não funcionar, peça ao administrador da empresa para verificar seu cadastro ou redefinir sua senha. |
| 2 | **Esqueci minha senha. Como recupero?** | Entre em contato com o administrador da sua empresa. Ele pode redefinir sua senha pelo painel de gestão de usuários. Após receber a nova senha, altere-a no primeiro acesso. |
| 3 | **O RDO não está salvando. O que pode ser?** | Verifique se todos os campos obrigatórios foram preenchidos (obra, data, condições climáticas). Confira também se sua conexão com a internet está funcionando. Se o problema persistir, tente recarregar a página e preencher novamente. |
| 4 | **A foto não está sendo enviada no RDO.** | Verifique se o navegador tem permissão para acessar a câmera do dispositivo. Tente tirar a foto novamente com boa iluminação. Se estiver usando uma foto da galeria, verifique se o arquivo não é muito grande. O sistema aceita fotos em JPG e PNG. |
| 5 | **Os números do financeiro parecem errados.** | Verifique se o filtro de período está selecionando as datas corretas. Confira se todos os pagamentos e recebimentos foram registrados no sistema. Lembre-se de que os custos de alimentação, transporte e mão de obra são calculados automaticamente — verifique se esses módulos estão com dados atualizados. |
| 6 | **Como altero o status de uma obra?** | Acesse a página de detalhes da obra e clique no botão **Alterar Status**. Você pode alternar entre "Em andamento", "Paralisada", "Concluída" e "Cancelada". |
| 7 | **Posso criar dois RDOs para a mesma obra no mesmo dia?** | Não. O sistema permite apenas um RDO por obra por dia. Se já existir um RDO para aquela data, você será redirecionado para editar o existente. |
| 8 | **O reconhecimento facial não está funcionando.** | Cadastre novas fotos do funcionário em condições de iluminação semelhantes ao local onde o ponto é registrado. Cadastre pelo menos 3 fotos com variações (com/sem óculos, com/sem capacete). Veja as dicas no Capítulo 3, seção 3.6.3. |
| 9 | **Como faço para um funcionário ver apenas suas próprias informações?** | Funcionários com perfil "Funcionário" já têm acesso restrito por padrão. Eles só conseguem ver o próprio painel, registrar ponto e visualizar os RDOs consolidados. |
| 10 | **O progresso da obra não está atualizando.** | O progresso só é atualizado quando um RDO é **aprovado** pelo gestor. Verifique se os RDOs da obra estão com status "Aprovado". RDOs em rascunho ou pendentes de aprovação não atualizam o progresso. |
| 11 | **Como exporto um relatório em PDF?** | Acesse o relatório desejado (pode ser no módulo de Obras, Funcionários, RDO ou Financeiro), configure os filtros e clique no botão **Exportar PDF** ou **Gerar PDF**. O arquivo será baixado automaticamente. |
| 12 | **Cadastrei um funcionário com dados errados. Posso corrigir?** | Sim. Acesse o perfil do funcionário, clique em **Editar** e corrija as informações necessárias. Clique em **Salvar** para confirmar. |
| 13 | **Posso usar o SIGE pelo celular?** | Sim! O sistema é totalmente responsivo e funciona em celulares e tablets. Basta acessar o endereço do SIGE pelo navegador do dispositivo (Chrome ou Safari). |
| 14 | **Como sei quanto uma obra está custando?** | Acesse a página de detalhes da obra. Os indicadores no topo mostram o custo total, dividido por categoria (mão de obra, alimentação, transporte e outros). Você também pode gerar relatórios detalhados de custos. |
| 15 | **O que acontece se eu excluir uma obra?** | A exclusão é permanente. Os serviços, custos diversos e alocações de equipe são removidos. Os RDOs já criados são mantidos para histórico. Recomendamos alterar o status para "Concluída" ou "Cancelada" em vez de excluir. |
| 16 | **Como registro uma falta justificada?** | No controle de ponto, localize o registro de falta, clique em Editar, altere o tipo para "Falta Justificada" e descreva o motivo nas observações (ex.: atestado médico). |
| 17 | **Por que meu Dashboard está mostrando tudo zerado?** | Provavelmente o filtro de período está selecionando um intervalo sem dados. Ajuste as datas de início e fim para um período que tenha registros no sistema. |

---

## 9.2. Dicas do Dia a Dia

Confira dicas práticas organizadas por perfil de usuário para aproveitar ao máximo o SIGE:

### Para Administradores

1. **Comece o dia pelo Dashboard** — Acesse o Painel de Controle logo cedo para ter uma visão geral de como está a operação da empresa.
2. **Revise as contas toda semana** — No módulo Financeiro, filtre as contas a pagar por "Vencido" e "Pendente" para não perder prazos.
3. **Acompanhe os RDOs pendentes** — Aprove os RDOs rapidamente para manter o progresso das obras atualizado.
4. **Gere o DRE todo mês** — O Demonstrativo de Resultado mostra se a empresa está lucrando ou não. É fundamental para tomada de decisão.
5. **Mantenha os cadastros atualizados** — Funcionários que saíram devem ser marcados como inativos. Obras concluídas devem ter o status alterado. Isso mantém os indicadores precisos.
6. **Exporte relatórios mensais** — Guarde PDFs do DRE, do fluxo de caixa e dos custos por obra para ter um histórico organizado.
7. **Configure os horários de trabalho** — Verifique se os modelos de horário estão corretos para evitar erros no cálculo de horas extras.

### Para Engenheiros e Gestores de Campo

1. **Preencha o RDO todo dia** — Não deixe para o dia seguinte. As informações ficam mais precisas quando registradas no mesmo dia.
2. **Capriche nas fotos** — Tire pelo menos uma foto por serviço executado. Fotos são a melhor prova do andamento da obra.
3. **Atualize os percentuais com cuidado** — Percentuais errados prejudicam todo o planejamento. Avalie visualmente antes de informar.
4. **Registre as condições climáticas** — Chuva e mau tempo justificam atrasos. Sem registro, fica difícil comprovar depois.
5. **Use o botão +RDO na tela de Obras** — É mais rápido do que criar pelo menu de RDOs, e o formulário já vem com a obra selecionada.
6. **Registre todos os terceirizados** — Mesmo que não sejam funcionários da empresa, é importante registrar a presença deles para controle de custos e segurança.
7. **Confira o progresso da obra semanalmente** — Acesse os detalhes da obra para verificar se os indicadores refletem a realidade do canteiro.

### Para Funcionários

1. **Bata o ponto pelo celular** — Acesse o SIGE pelo navegador do celular e registre seu ponto de entrada e saída diariamente.
2. **Posicione bem o rosto para o reconhecimento facial** — Centralize o rosto na tela, com boa iluminação, para que o sistema reconheça rapidamente.
3. **Finalize seus RDOs em rascunho** — Se você tem RDOs pendentes, complete-os para que as informações sejam contabilizadas.
4. **Use as Ações Rápidas** — Os botões de ação rápida no seu painel economizam tempo: Criar RDO, Ver Obras e Ver RDOs.
5. **Informe ao gestor se o ponto não for registrado** — Se houve algum problema no registro (sem internet, câmera não funcionou), avise para que o gestor possa corrigir manualmente.

---

## 9.3. Contato do Suporte

Se você encontrou algum problema que não conseguiu resolver com as orientações deste manual, entre em contato com o suporte:

| Canal | Informação |
|---|---|
| **E-mail do Suporte** | [suporte@suaempresa.com.br] |
| **Telefone / WhatsApp** | [(XX) XXXX-XXXX] |
| **Horário de Atendimento** | Segunda a sexta, das 08h às 18h |
| **Administrador do Sistema** | Procure o administrador da sua empresa para questões internas (redefinição de senha, criação de cadastro, ajuste de permissões) |

> **Antes de entrar em contato com o suporte:**
>
> 1. Consulte este manual — muitas dúvidas são respondidas aqui.
> 2. Verifique se o problema pode ser resolvido pelo administrador da empresa (ex.: redefinição de senha, alteração de perfil).
> 3. Anote as informações do problema: qual tela estava usando, o que tentou fazer, e se apareceu alguma mensagem de erro. Isso ajuda o suporte a resolver mais rápido.

---

## 9.4. Glossário

Abaixo estão os termos mais usados no SIGE e suas explicações em linguagem simples:

| Termo | O que significa |
|---|---|
| **Almoxarifado** | O local onde são guardados materiais, ferramentas e equipamentos de proteção (EPIs). No sistema, é o módulo que controla o estoque desses itens. |
| **Card** | Cartão visual que aparece na tela do sistema, mostrando um resumo das informações de um item (funcionário, obra, veículo, etc.). |
| **Centro de Custo** | Uma forma de organizar os gastos da empresa por área, obra ou departamento, facilitando a análise de onde o dinheiro está sendo gasto. |
| **Contraluz** | Quando a luz está atrás da pessoa na hora de tirar a foto, deixando o rosto escuro. Evite essa situação ao tirar fotos para o reconhecimento facial. |
| **Dashboard** | Painel de controle do sistema, que mostra indicadores, gráficos e resumos da empresa em uma única tela. |
| **DRE** | Demonstrativo de Resultado do Exercício — relatório financeiro que mostra se a empresa teve lucro ou prejuízo em um período. |
| **DSR** | Descanso Semanal Remunerado — valor adicional pago sobre as horas extras, garantido por lei. O sistema calcula automaticamente. |
| **EPI** | Equipamento de Proteção Individual — itens como capacete, luva, óculos de proteção e botas, obrigatórios para trabalho em obra. |
| **Fluxo de Caixa** | Extrato que mostra todas as entradas e saídas de dinheiro da empresa em ordem cronológica. |
| **Geofence** | Cerca virtual — um perímetro digital ao redor da obra que verifica se o funcionário está no local correto ao registrar o ponto. |
| **KPI** | Indicador-chave de desempenho (Key Performance Indicator) — são os números importantes que aparecem nos painéis do sistema (ex.: custo total, obras ativas, funcionários). |
| **Licenciamento** | Documento anual obrigatório para veículos, que inclui o pagamento do IPVA e taxas. O sistema avisa quando está próximo do vencimento. |
| **Login** | O processo de entrar no sistema usando seu nome de usuário (ou e-mail) e sua senha. |
| **Logout** | O processo de sair do sistema, encerrando sua sessão de forma segura. |
| **Margem** | A diferença entre o valor do contrato (o que o cliente paga) e o custo real da obra. Margem positiva significa lucro; negativa significa prejuízo. |
| **Obra** | Um projeto de construção cadastrado no sistema, que pode ser uma edificação, reforma, instalação ou qualquer serviço de engenharia. |
| **Orçamento** | O valor estimado que a empresa prevê gastar para executar uma obra (custo interno). |
| **PDF** | Formato de arquivo para documentos, usado para gerar relatórios que podem ser impressos ou enviados por e-mail. |
| **Ponto** | O registro de entrada e saída do funcionário no trabalho, usado para controlar a jornada de trabalho. |
| **Portal do Cliente** | Um link exclusivo gerado pelo sistema que permite ao cliente acompanhar o andamento da obra pela internet, sem precisar de login no SIGE. |
| **Proposta Comercial** | Um documento que apresenta ao cliente o escopo, o valor e as condições de um serviço que a empresa oferece. |
| **RDO** | Relatório Diário de Obra — documento que registra tudo o que aconteceu na obra em um dia de trabalho (equipe, serviços, fotos, clima, equipamentos). |
| **Reconhecimento Facial** | Funcionalidade que compara a foto tirada no momento do registro de ponto com as fotos cadastradas do funcionário, para confirmar a identidade. |
| **RENAVAM** | Registro Nacional de Veículos Automotores — número de identificação do veículo que consta no documento (CRV/CRLV). |
| **Responsivo** | Característica do sistema que faz com que a tela se adapte automaticamente ao tamanho do dispositivo (computador, tablet ou celular). |
| **Status** | A situação atual de um item no sistema (ex.: obra "Em andamento", conta "Pendente", veículo "Ativo", RDO "Aprovado"). |
| **Subatividade** | Uma etapa menor dentro de um serviço da obra. Por exemplo, o serviço "Alvenaria" pode ter as subatividades "Marcação", "Elevação 1º pavimento" e "Elevação 2º pavimento". |
| **Taxa de Absenteísmo** | Percentual que indica quantos dias os funcionários faltaram em relação ao total de dias úteis do período. |
| **Valor do Contrato** | O valor total que o cliente pagará pela obra, conforme acordado em contrato. É a receita prevista do projeto. |

---

*SIGE - Estruturas do Vale (EnterpriseSync) — Manual do Usuário*
*Versão 1.0 | Fevereiro de 2026*
