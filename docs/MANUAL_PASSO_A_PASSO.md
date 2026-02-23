# Manual Passo a Passo — SIGE EnterpriseSync

**Versão 1.0 | Fevereiro de 2026**

> Este manual apresenta instruções práticas e objetivas para utilizar as principais funcionalidades do sistema SIGE EnterpriseSync.

---

## Sumário

1. [Gerenciando Usuários](#1-gerenciando-usuários)
2. [Cadastro de Funcionários](#2-cadastro-de-funcionários)
3. [Criação de Obras](#3-criação-de-obras)
4. [Gestão de Equipes](#4-gestão-de-equipes)
5. [Relatório Diário de Obra (RDO)](#5-relatório-diário-de-obra-rdo)
6. [Reconhecimento Facial (Cadastro e Uso)](#6-reconhecimento-facial-cadastro-e-uso)
   - 6.1 [Cadastro de Fotos](#61-cadastro-de-fotos)
   - 6.2 [Batendo o Ponto com Reconhecimento Facial](#62-batendo-o-ponto-com-reconhecimento-facial)
7. [Propostas Comerciais](#7-propostas-comerciais)
   - 7.1 [Templates de Proposta](#71-templates-de-proposta)
   - 7.2 [Criando uma Nova Proposta](#72-criando-uma-nova-proposta)
8. [Veículos (Uso e Custo)](#8-veículos-uso-e-custo)
9. [Controle de Alimentação](#9-controle-de-alimentação)
10. [Almoxarifado](#10-almoxarifado)

---

## 1. Gerenciando Usuários

### Introdução

O módulo de Usuários permite que o administrador do sistema crie, edite e desative contas de acesso para todas as pessoas que utilizarão o SIGE EnterpriseSync. Cada usuário recebe um perfil de acesso que determina quais funcionalidades ele poderá visualizar e utilizar no sistema.

### Pré-requisitos

- Estar logado no sistema com perfil de **Administrador**.
- Ter em mãos os dados do novo usuário: nome completo, e-mail e o perfil de acesso desejado.

### Passo a Passo

1. Clique em **"Funcionários"** no menu superior do sistema.
2. Navegue até a área de gerenciamento de usuários. Você verá a tela com o título **"Usuários do Sistema"**.
3. Na tela de lista, observe a tabela com os usuários já cadastrados. As colunas mostram o nome, e-mail, tipo de acesso e status de cada usuário.
4. Para criar um novo usuário, clique no botão **"Novo Usuário"**.
5. Preencha o campo **"Nome"** com o nome completo do usuário.
6. Preencha o campo **"Email"** — este será o dado utilizado para fazer login no sistema.
7. Preencha o campo **"Username"** com um nome de usuário único.
8. Preencha o campo **"Senha"** com uma senha inicial segura.
9. No campo **"Perfil de Acesso"**, selecione o perfil adequado:
   - **Administrador** — acesso completo a todas as funcionalidades.
   - **Gestor de Equipes** — acesso ao gerenciamento de equipes e funcionalidades relacionadas.
   - **Almoxarife** — acesso ao controle de almoxarifado e materiais.
   - **Funcionário** — acesso limitado ao registro de ponto e visualização de RDOs.
10. Ative ou desative o campo **"Ativo"** conforme necessário.
11. Clique em **"Salvar"** para finalizar o cadastro.
12. Para editar um usuário existente, clique no **ícone de edição** ao lado do nome do usuário na lista.
13. Para desativar um usuário, abra o cadastro dele e desative o campo **"Ativo"**.

### Dica Prática

> Sempre crie uma senha inicial forte e oriente o novo usuário a alterá-la no primeiro acesso.

### Imagens de Referência

`[IMAGEM: Tela de lista de usuários com o botão 'Novo Usuário' destacado]`

`[IMAGEM: Formulário de criação de novo usuário com o campo 'Perfil de Acesso' em destaque]`

---

## 2. Cadastro de Funcionários

### Introdução

O módulo de Funcionários é onde você registra todos os colaboradores da empresa. As informações cadastradas aqui são utilizadas em diversos outros módulos do sistema, como controle de ponto, alocação de equipes, registro de alimentação e cálculo de custos de mão de obra.

### Pré-requisitos

- Estar logado no sistema com perfil de **Administrador** ou **Gestor de Equipes**.
- Ter em mãos os dados pessoais e contratuais do funcionário (documentos, contato, informações do contrato).

### Passo a Passo

1. Clique em **"Funcionários"** no menu superior do sistema.
2. Você verá a lista de funcionários cadastrados, exibida em formato de cards com foto (ou iniciais do nome), nome e função de cada colaborador.
3. Para cadastrar um novo funcionário, clique no botão **"+ Novo Funcionário"**.
4. Na seção **Informações Pessoais**, preencha os campos:
   - **Nome** completo do funcionário.
   - **CPF** — número do documento.
   - **RG** — número do registro geral.
   - **Data de Nascimento**.
5. Na seção **Contato**, preencha:
   - **Telefone** do funcionário.
   - **E-mail** do funcionário.
6. Na seção **Endereço**, preencha o endereço completo do funcionário.
7. Na seção **Informações do Contrato**, preencha:
   - **Cargo/Função** que o funcionário exercerá.
   - **Departamento** ao qual pertence.
   - **Salário** — valor da remuneração mensal.
   - **Data de Admissão**.
   - **Horário de Trabalho** — jornada definida para o funcionário.
8. Se desejar, faça o upload de uma **foto** do funcionário clicando na área de imagem.
9. Clique em **"Salvar"** para finalizar o cadastro.

### Dica Prática

> Preencha o campo de salário corretamente. Ele será usado para calcular automaticamente os custos de mão de obra nas obras.

### Imagens de Referência

`[IMAGEM: Tela do módulo de Funcionários com a lista de colaboradores]`

`[IMAGEM: Formulário de cadastro de funcionário]`

---

## 3. Criação de Obras

### Introdução

O módulo de Obras é o coração do sistema. Cada obra cadastrada funciona como um centro de custo e organização, conectando equipes, relatórios diários, veículos, alimentação e materiais. Manter as obras bem cadastradas e atualizadas é fundamental para o bom funcionamento de todos os outros módulos.

### Pré-requisitos

- Estar logado no sistema com perfil de **Administrador** ou **Gestor de Equipes**.
- Ter em mãos as informações da obra: nome, cliente, endereço, datas, orçamento e responsável técnico.

### Passo a Passo

1. Clique em **"Obras"** no menu superior do sistema.
2. Você verá a lista de obras cadastradas em formato de cards, exibindo o nome, status, progresso e cliente de cada obra.
3. Para criar uma nova obra, clique no botão **"+ Nova Obra"**.
4. Preencha o campo **"Nome da Obra"** com um nome claro e identificável.
5. Preencha o campo **"Código"** com o código interno da obra.
6. Selecione o **"Cliente"** associado à obra.
7. Preencha o campo **"Endereço"** com a localização completa da obra.
8. Selecione o **"Responsável Técnico"** pela obra.
9. Preencha a **"Data de Início"** e a **"Data de Término Prevista"**.
10. Preencha os campos **"Orçamento"** e **"Valor do Contrato"** com os valores financeiros.
11. No campo **"Descrição"**, adicione informações complementares sobre a obra.
12. Selecione o **"Status"** da obra:
    - **Ativa** — obra em andamento.
    - **Pausada** — obra temporariamente interrompida.
    - **Concluída** — obra finalizada.
13. Se desejar utilizar o controle de localização (cerca virtual para registro de ponto), preencha os campos de **Latitude** e **Longitude** com as coordenadas do local da obra.
14. Clique em **"Salvar"** para finalizar o cadastro.

### Dica Prática

> Mantenha o status da obra sempre atualizado. Obras "Ativas" aparecem nos filtros de RDO, Equipe e outros módulos.

### Imagens de Referência

`[IMAGEM: Lista de obras com cards]`

`[IMAGEM: Formulário de criação de nova obra]`

---

## 4. Gestão de Equipes

### Introdução

O módulo de Gestão de Equipes permite alocar funcionários nas obras de forma visual e organizada. A cada semana, você define quais colaboradores estarão trabalhando em cada obra e em qual setor (Campo ou Oficina). Essa alocação é fundamental para o controle de presença e a geração dos Relatórios Diários de Obra.

### Pré-requisitos

- Estar logado no sistema com perfil de **Administrador** ou **Gestor de Equipes**.
- Ter obras cadastradas com status **"Ativa"**.
- Ter funcionários cadastrados no sistema.

### Passo a Passo

1. Clique em **"Equipe"** no menu superior do sistema.
2. Você verá a tela **"Gestão de Equipe"** com uma barra de busca/seleção de obras no topo.
3. Abaixo, são exibidos os cards de cada obra. Cada card mostra o nome da obra e duas áreas de alocação:
   - **CAMPO** — para funcionários que trabalharão no canteiro de obras.
   - **OFICINA** — para funcionários que trabalharão na oficina/escritório da obra.
4. Use os controles de calendário semanal para navegar entre as semanas e definir a alocação no período desejado.
5. Para alocar um funcionário, arraste o nome do colaborador da lista de disponíveis e solte na área **CAMPO** ou **OFICINA** da obra desejada.
6. Você também pode clicar no nome do funcionário e selecionar a obra e o setor de destino.
7. Para remover um funcionário de uma obra, arraste-o de volta para a lista de disponíveis ou clique para desalocá-lo.
8. Repita o processo para todos os funcionários e obras necessárias.

### Dica Prática

> Manter as equipes atualizadas é crucial. A alocação de equipe é usada para controle de presença e geração de RDOs.

### Imagens de Referência

`[IMAGEM: Tela de gestão de equipes com obras e zonas CAMPO/OFICINA]`

---

## 5. Relatório Diário de Obra (RDO)

### Introdução

O Relatório Diário de Obra (RDO) é o documento que registra tudo o que aconteceu em uma obra durante o dia: condições climáticas, mão de obra presente, serviços realizados e fotos do andamento. Ele é essencial para o acompanhamento do progresso da obra e para a prestação de contas ao cliente.

### Pré-requisitos

- Estar logado no sistema com perfil de **Administrador**, **Gestor de Equipes** ou **Funcionário**.
- Ter pelo menos uma obra cadastrada com status **"Ativa"**.
- Ter funcionários alocados na obra (para a seção de mão de obra).

### Passo a Passo

1. Clique em **"RDOs"** no menu superior do sistema.
2. Você verá a lista consolidada de todos os RDOs, com colunas mostrando: Número, Obra, Data e Status (Rascunho, Em Elaboração, Pendente Aprovação, Aprovado ou Reprovado).
3. Para criar um novo RDO, clique no botão **"Novo RDO"**.
4. Selecione a **Obra** no campo de seleção (lista suspensa com as obras ativas).
5. O campo **"Data"** é preenchido automaticamente com a data de hoje. Altere se necessário.
6. Selecione as **"Condições Climáticas Manhã"** na lista suspensa (Ensolarado, Nublado, Chuvoso, etc.).
7. Selecione as **"Condições Climáticas Tarde"** na lista suspensa.
8. Na seção **"Mão de Obra"**, adicione os trabalhadores presentes na obra naquele dia:
   - Selecione o funcionário.
   - Informe a função exercida.
   - Selecione o tipo: **Próprio** ou **Terceirizado**.
9. Na seção **"Serviços/Atividades"**, descreva os serviços realizados durante o dia.
10. Na seção **"Fotos"**, anexe fotos do andamento da obra tiradas em campo.
11. Você pode clicar em **"Salvar como Rascunho"** para continuar o preenchimento mais tarde.
12. Quando o RDO estiver completo, clique em **"Enviar para Aprovação"**.
13. O gestor responsável receberá o RDO para revisão e poderá **Aprovar** ou **Reprovar** o relatório.
14. RDOs aprovados atualizam automaticamente o progresso da obra.

### Dica Prática

> Use o botão "Salvar como Rascunho" para preencher o RDO ao longo do dia e finalize apenas no final do expediente.

### Imagens de Referência

`[IMAGEM: Formulário de criação de RDO com seleção de obra e condições climáticas]`

`[IMAGEM: Seção de Mão de Obra e Serviços do RDO]`

---

## 6. Reconhecimento Facial (Cadastro e Uso)

### Introdução

O sistema SIGE EnterpriseSync utiliza reconhecimento facial para o registro de ponto dos funcionários. Este módulo é dividido em duas etapas: primeiro, o cadastro das fotos de cada colaborador; depois, o uso dessas fotos para identificar o funcionário no momento do registro de ponto. Esse recurso traz mais segurança e praticidade ao controle de presença.

### 6.1 Cadastro de Fotos

#### Introdução

O cadastro de fotos faciais é o primeiro passo para utilizar o reconhecimento facial no registro de ponto. Nesta etapa, você captura diversas fotos de cada funcionário em diferentes condições (com capacete, com óculos, de frente) para que o sistema consiga identificá-lo com precisão no dia a dia da obra.

#### Pré-requisitos

- Estar logado no sistema com perfil de **Administrador** ou **Gestor de Equipes**.
- Ter o funcionário já cadastrado no sistema.
- Ter uma câmera disponível no dispositivo (computador, tablet ou celular).
- Ambiente com boa iluminação para a captura das fotos.

#### Passo a Passo

1. Clique no menu **"Ponto"** no topo da tela para abrir o submenu.
2. Selecione **"Gerenciar Fotos Faciais"**.
3. Você verá a lista de funcionários. Clique no funcionário para o qual deseja cadastrar as fotos.
4. Na página do funcionário, você verá a seção de fotos faciais com as fotos já cadastradas (se houver).
5. Clique no botão para **adicionar nova foto**.
6. A câmera do dispositivo será ativada. Posicione o rosto do funcionário no centro da tela.
7. Certifique-se de que o rosto está bem iluminado e centralizado na câmera.
8. Clique para capturar a foto. O sistema validará automaticamente a qualidade da imagem (iluminação, tamanho do rosto e centralização).
9. Se a foto for aceita, ela será salva automaticamente.
10. Repita o processo para registrar fotos adicionais do mesmo funcionário em diferentes condições:
    - Uma foto **de frente**, sem acessórios.
    - Uma foto **com capacete de obra**.
    - Uma foto **com óculos**.
    - Fotos em **ângulos ligeiramente diferentes**.

#### Dica Prática

> Cadastre pelo menos 3 fotos por funcionário: uma de frente, uma com capacete e uma com óculos. Quanto mais fotos, melhor o reconhecimento.

#### Imagens de Referência

`[IMAGEM: Tela de cadastro de fotos no perfil do funcionário]`

`[IMAGEM: Câmera ativa para captura de foto facial]`

---

### 6.2 Batendo o Ponto com Reconhecimento Facial

#### Introdução

Com as fotos cadastradas, o funcionário pode registrar seu ponto de entrada e saída utilizando o reconhecimento facial. O sistema identifica automaticamente o colaborador pela câmera e registra o horário, trazendo mais agilidade e segurança ao processo. Se a obra tiver coordenadas configuradas, o sistema também valida a localização do funcionário.

#### Pré-requisitos

- O funcionário deve ter **pelo menos 3 fotos faciais cadastradas** no sistema.
- Ter uma câmera disponível no dispositivo utilizado para o registro.
- Se a obra utilizar cerca virtual (geofencing), o dispositivo deve ter o **GPS ativado** e o funcionário deve estar **a até 100 metros** do local da obra.

#### Passo a Passo

1. Clique no menu **"Ponto"** no topo da tela para abrir o submenu.
2. Selecione **"Ponto Eletrônico"**.
3. Você verá a tela de registro de ponto com o nome do funcionário e o horário atual.
4. Se necessário, selecione a **Obra** na qual o ponto será registrado.
5. Selecione o funcionário na lista (caso não esteja selecionado automaticamente).
6. A câmera será ativada automaticamente. Posicione o rosto de frente para a câmera.
7. O sistema irá reconhecer o rosto e confirmar a identidade do funcionário.
8. Após a confirmação, clique no botão **"Entrada"** para registrar o início do expediente ou **"Saída"** para registrar o fim.
9. Se a obra tiver coordenadas configuradas, o sistema verificará automaticamente se o funcionário está dentro do raio de 100 metros da obra.
10. Você verá a tela de confirmação indicando que o ponto foi registrado com sucesso.

#### Dica Prática

> Para um bom reconhecimento, certifique-se de que o ambiente está bem iluminado e que o rosto está centralizado na câmera.

#### Imagens de Referência

`[IMAGEM: Tela de registro de ponto com câmera ativa]`

`[IMAGEM: Confirmação de ponto registrado com sucesso]`

---

## 7. Propostas Comerciais

### Introdução

O módulo de Propostas Comerciais permite criar, gerenciar e enviar propostas de serviço para seus clientes de forma organizada e profissional. Com o uso de templates, você ganha agilidade na elaboração de novas propostas, e o portal do cliente permite que ele visualize e aprove a proposta diretamente pelo sistema.

### 7.1 Templates de Proposta

#### Introdução

Os templates de proposta são modelos pré-configurados que preenchem automaticamente as seções da proposta (como Escopo, Cronograma e Investimento) de acordo com o tipo de serviço. Utilizar templates economiza tempo e garante que todas as propostas sigam o mesmo padrão de qualidade.

#### Pré-requisitos

- Estar logado no sistema com perfil de **Administrador**.
- Ter templates já cadastrados no sistema (o sistema já vem com 4 ou mais templates padrão).

#### Passo a Passo

1. Clique no menu **"Propostas"** no topo da tela para abrir o submenu.
2. Ao criar uma nova proposta (veja a seção 7.2), você verá o campo **"Pré-carregar Template"** no formulário.
3. Clique na lista suspensa de templates para ver os modelos disponíveis.
4. Selecione o template mais adequado ao tipo de serviço que será proposto.
5. O sistema preencherá automaticamente as seções da proposta com o conteúdo do template selecionado (Escopo, Cronograma, Investimento, entre outras).
6. Você pode editar livremente o conteúdo preenchido pelo template para personalizar a proposta.

#### Dica Prática

> Crie templates para diferentes tipos de serviço. Isso economiza muito tempo na criação de novas propostas.

---

### 7.2 Criando uma Nova Proposta

#### Introdução

A criação de uma nova proposta é feita através de um formulário completo onde você define o cliente, o assunto, os serviços oferecidos e os valores. Após a criação, é possível gerar um documento em PDF e compartilhar um link exclusivo com o cliente para que ele revise e aprove a proposta.

#### Pré-requisitos

- Estar logado no sistema com perfil de **Administrador** ou **Gestor de Equipes**.
- Ter clientes cadastrados no sistema.

#### Passo a Passo

1. Clique no menu **"Propostas"** no topo da tela para abrir o submenu.
2. Selecione **"Nova Proposta"**.
3. No campo **"Nome do Cliente"**, pesquise e selecione o cliente destinatário da proposta.
4. Se desejar, selecione um template no campo **"Pré-carregar Template"** para agilizar o preenchimento.
5. Preencha o campo **"Assunto da Proposta"** com uma descrição clara do serviço oferecido.
6. Na seção **"Serviços"**, adicione os itens da proposta:
   - Preencha a descrição do serviço.
   - Informe o valor de cada item.
   - Clique para adicionar mais itens conforme necessário.
7. Observe o campo **"Total da Proposta"** que é atualizado automaticamente conforme os itens são adicionados (inicia em R$ 0,00).
8. Quando terminar, clique em **"Criar Proposta"** para salvar.
9. Após a criação, você pode gerar o **PDF** da proposta para envio ou impressão.
10. Utilize o **portal do cliente** para compartilhar um link exclusivo, permitindo que o cliente visualize e aprove a proposta diretamente pelo sistema.
11. Acompanhe o status da proposta na lista:
    - **Rascunho** — proposta em elaboração.
    - **Enviada** — proposta encaminhada ao cliente.
    - **Aprovada** — cliente aceitou a proposta.
    - **Rejeitada** — cliente recusou a proposta.

#### Dica Prática

> Após criar a proposta, gere o PDF e envie o link do portal ao cliente. Assim, ele pode aprovar diretamente pelo sistema, agilizando o processo.

#### Imagens de Referência

`[IMAGEM: Formulário de criação de proposta com seleção de template]`

`[IMAGEM: Seção de serviços e valores da proposta]`

---

## 8. Veículos (Uso e Custo)

### Introdução

O módulo de Veículos permite controlar toda a frota da empresa, registrando o uso de cada veículo (viagens), os custos associados (combustível, manutenção, pedágio, seguro) e acompanhando indicadores como custo total, custo por quilômetro e quilometragem total. Com essas informações, a gestão da frota se torna mais eficiente e transparente.

### Pré-requisitos

- Estar logado no sistema com perfil de **Administrador** ou **Gestor de Equipes**.
- Ter veículos cadastrados no sistema.
- Ter funcionários cadastrados (para registrar o motorista).
- Ter obras cadastradas (para associar o uso do veículo a uma obra).

### Passo a Passo

1. Clique em **"Veículos"** no menu superior do sistema.
2. Você verá a lista de veículos cadastrados em formato de cards, exibindo: placa, modelo, marca, ano e status de cada veículo.
3. Clique em um veículo para acessar a **página de detalhes**.
4. Na página de detalhes, você verá os indicadores principais (KPIs):
   - **Custo Total** — soma de todos os custos do veículo.
   - **Custo/Km** — custo médio por quilômetro rodado.
   - **Km Total** — quilometragem total registrada.
5. Abaixo dos indicadores, observe os **gráficos** que mostram os custos por mês e por categoria.
6. Para registrar um **uso (viagem)** do veículo:
   - Selecione o **motorista** (funcionário responsável).
   - Selecione a **obra** de destino.
   - Preencha o campo **"Km Saída"** com a quilometragem no início da viagem.
   - Preencha o campo **"Km Retorno"** com a quilometragem ao final da viagem.
   - Preencha o campo **"Destino"** com o local de destino.
   - Clique em **"Salvar"**.
7. Para registrar um **custo** do veículo:
   - Selecione o **tipo de custo**: Combustível, Manutenção, Pedágio, Seguro ou Outros.
   - Preencha o **valor** do custo.
   - Informe a **data** em que o custo ocorreu.
   - Preencha o **fornecedor** (posto, oficina, etc.).
   - Informe o número da **nota fiscal**, se houver.
   - Adicione uma **observação**, se necessário.
   - Selecione a **obra** relacionada ao custo.
   - Clique em **"Salvar"**.
8. Consulte o **histórico de usos e custos** na página de detalhes do veículo.

### Dica Prática

> Sempre atualize o hodômetro ao registrar um uso. Isso mantém o controle de custo por quilômetro preciso.

### Imagens de Referência

`[IMAGEM: Detalhes de um veículo com KPIs e gráficos]`

`[IMAGEM: Formulário de registro de custo de veículo]`

---

## 9. Controle de Alimentação

### Introdução

O módulo de Alimentação permite registrar e acompanhar os custos de refeições dos funcionários em cada obra. Você pode gerenciar restaurantes fornecedores, manter um catálogo de itens de alimentação com valores unitários e lançar as refeições diárias de forma rápida e organizada, com cálculo automático dos custos.

### Pré-requisitos

- Estar logado no sistema com perfil de **Administrador** ou **Gestor de Equipes**.
- Ter funcionários e obras cadastrados no sistema.
- Ter itens de alimentação cadastrados no catálogo (seção "Itens").

### Passo a Passo

1. Clique em **"Alimentação"** no menu superior do sistema.
2. Você verá o módulo com as seguintes seções disponíveis: **Lançamentos**, **Restaurantes**, **Itens** e **Dashboard**.
3. Para cadastrar um **restaurante/fornecedor**:
   - Acesse a seção **"Restaurantes"**.
   - Clique em **"Novo Restaurante"**.
   - Preencha o **nome**, **endereço** e **contato** do restaurante.
   - Clique em **"Salvar"**.
4. Para cadastrar **itens de alimentação**:
   - Acesse a seção **"Itens"**.
   - Clique em **"Novo Item"**.
   - Preencha o **nome** do item (ex.: Marmitex, Lanche, Água) e o **valor unitário**.
   - Clique em **"Salvar"**.
5. Para registrar um **lançamento de alimentação**:
   - Acesse a seção **"Lançamentos"**.
   - Clique em **"Novo Lançamento"**.
   - Selecione a **Obra** na lista suspensa.
   - Informe a **Data** do lançamento.
   - No campo de **Funcionários**, pesquise e selecione os funcionários que fizeram a refeição (você pode selecionar vários de uma vez).
   - Selecione os **itens de alimentação** consumidos, informando as quantidades e valores de cada um.
   - Você pode adicionar **múltiplos itens** ao mesmo lançamento.
   - O sistema calcula automaticamente o **custo total** do lançamento.
   - Clique em **"Salvar"** para registrar.
6. Para acompanhar os custos, acesse a seção **"Dashboard"** e visualize os indicadores de custos de alimentação por obra.

### Dica Prática

> Registre os custos de alimentação diariamente para que o controle financeiro da obra fique sempre atualizado.

### Imagens de Referência

`[IMAGEM: Formulário de lançamento de alimentação com seleção de funcionários e itens]`

`[IMAGEM: Dashboard de alimentação com custos por obra]`

---

## 10. Almoxarifado

### Introdução

O módulo de Almoxarifado permite o controle completo de materiais, ferramentas e Equipamentos de Proteção Individual (EPIs). Com ele, você registra entradas de materiais vindos de fornecedores, saídas de materiais para as obras e acompanha o estoque em tempo real através de indicadores e histórico de movimentações.

### Pré-requisitos

- Estar logado no sistema com perfil de **Administrador** ou **Almoxarife**.
- Ter categorias de materiais cadastradas.
- Ter itens cadastrados no catálogo de materiais.
- Ter fornecedores, funcionários e obras cadastrados no sistema.

### Passo a Passo

1. Clique no menu **"Almoxarifado"** no topo da tela para abrir o submenu.
2. Você verá o **Dashboard** com os indicadores principais (KPIs): total de itens cadastrados, valor total do estoque e movimentações recentes.
3. O módulo possui as seguintes seções: **Categorias**, **Itens**, **Entrada** e **Saída**.

#### Cadastrando Categorias e Itens

4. Acesse a seção **"Categorias"** para organizar os materiais por tipo (ex.: Material Elétrico, Ferramentas, EPIs).
5. Acesse a seção **"Itens"** para cadastrar os materiais, ferramentas e EPIs disponíveis, associando cada item a uma categoria.

#### Registrando uma Entrada de Materiais

6. Acesse a seção **"Entrada"**.
7. No formulário de entrada, selecione o **Item** desejado na lista de busca.
8. Selecione o **Fornecedor** que está entregando o material.
9. Preencha a **Quantidade** recebida.
10. Preencha o **Valor Unitário** do item.
11. Informe o número do **Lote/Nota Fiscal** para rastreamento.
12. Clique em **"Adicionar ao Carrinho"** para incluir o item na lista de entrada.
13. Repita os passos 7 a 12 para adicionar **mais itens** à mesma entrada.
14. Quando todos os itens estiverem no carrinho, clique em **"Processar"** para registrar todas as entradas de uma só vez.

#### Registrando uma Saída de Materiais

15. Acesse a seção **"Saída"**.
16. No formulário de saída, selecione o **Item** que será retirado do estoque.
17. Selecione o **Funcionário** que está recebendo o material.
18. Selecione a **Obra** de destino do material.
19. Selecione o **Lote** disponível no estoque.
20. Preencha a **Quantidade** que será retirada.
21. Clique em **"Adicionar ao Carrinho"** para incluir o item na lista de saída.
22. Repita os passos 16 a 21 para adicionar **mais itens** à mesma saída.
23. Quando todos os itens estiverem no carrinho, clique em **"Processar"** para registrar todas as saídas de uma só vez.

#### Consultando o Histórico

24. Para consultar o histórico de movimentações de um item específico, acesse a página do item e visualize todas as entradas e saídas registradas.

### Dica Prática

> Mantenha o cadastro de materiais sempre atualizado com categorias organizadas. Use o carrinho para processar várias movimentações de uma só vez.

### Imagens de Referência

`[IMAGEM: Dashboard do almoxarifado com KPIs]`

`[IMAGEM: Formulário de entrada de materiais com carrinho]`

---

*Este manual é um documento vivo e será atualizado conforme novas funcionalidades forem adicionadas ao sistema SIGE EnterpriseSync.*
