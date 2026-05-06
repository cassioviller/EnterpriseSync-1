# Funcionários

O módulo **Funcionários** é o cadastro central de pessoas da empresa. Ele alimenta praticamente todos os outros módulos do SIGE: ponto, RDO, folha de pagamento, alocação por equipe, custos de mão de obra e indicadores de produtividade. Mantenha-o sempre atualizado.

## Para que serve

- Cadastrar colaboradores (mensalistas, diaristas, horistas) com dados pessoais, função, departamento, salário/diária, benefícios e PIX para pagamento.
- Definir o **horário padrão** de cada funcionário e as obras em que ele pode bater ponto.
- Gerar o **perfil completo** do funcionário com fotos, KPIs do mês, registros de ponto, ocorrências e histórico em PDF.
- Importar funcionários em massa por planilha (planilha modelo disponível no fluxo de importação).

## Como acessar

- **Menu superior → "Funcionários" → "Lista de funcionários"** abre a tela `/funcionarios`.
- **Menu superior → "Funcionários" → "Importar por Planilha"** abre o assistente de importação em `/importacao/`.
- **Menu superior → "Equipe"** abre a visão por equipes/alocação (`/equipe/`).
- **Menu superior → "Ponto"** dá acesso aos sub-itens: Lançar Ponto (`/ponto/`), Reconhecimento Facial (`/ponto/facial`), Gerenciar Fotos Faciais (`/ponto/gerenciar-fotos-faciais`), Importar Ponto (`/ponto/importar`).

## Fluxos principais

### 1. Cadastrar um novo funcionário
1. Menu **Funcionários → Lista de funcionários**.
2. Clique em **"Novo Funcionário"** (botão azul, canto superior direito) — abre um modal.
3. Preencha os campos obrigatórios marcados com **\***: **Nome**, **CPF**, **Função**, **Departamento**, **Data de Admissão** e **Tipo de Remuneração** (Salário fixo / Diária / Hora).
4. Conforme o tipo de remuneração, preencha **Salário** (mensalistas), **Valor da Diária** (diaristas) ou **Valor/Hora** (horistas).
5. Em **Benefícios**, informe **VA (Vale Alimentação)** e **VT (Vale Transporte)** em valor mensal.
6. Em **Dados Bancários**, preencha a **chave PIX** — ela aparece nos relatórios de folha.
7. Clique em **"Salvar"**. O sistema fecha o modal, atualiza a lista e mostra o card do novo funcionário.

> **Cuidado:** o CPF é único por empresa. Se o sistema rejeitar com "CPF já cadastrado", verifique a lista (incluindo inativos) antes de tentar criar de novo.

### 2. Ver perfil completo / KPIs
1. Na lista de funcionários, clique no **nome** ou no botão **"Ver Perfil"** do card.
2. O perfil abre em `/funcionario_perfil/<id>` com:
   - Cabeçalho com foto, função, salário, dias trabalhados.
   - **KPIs do mês**: horas trabalhadas, horas extras, faltas, atrasos, custo total.
   - Tabela de **registros de ponto** do período selecionado.
   - Filtro por intervalo de datas no topo da página.
3. Para baixar em PDF, clique em **"Exportar PDF"** (`/funcionario_perfil/<id>/pdf`).

### 3. Configurar horário e obras de ponto
1. No perfil do funcionário, clique em **"Horário Padrão"** (`/funcionarios/<id>/horario-padrao`).
2. Selecione o horário cadastrado em **Configurações → Horários de Trabalho**.
3. Para liberar o ponto em obras específicas: **Menu → Ponto → Configurar Obras por Funcionário** (`/ponto/configuracao/obras-funcionarios`).

### 4. Importar funcionários em massa
1. **Menu → Funcionários → Importar por Planilha**.
2. Baixe a **planilha modelo** com o botão indicado.
3. Preencha cada linha (nome, CPF, função, salário, etc.).
4. Faça o **upload** e revise o pré-visualizar (linhas com erro são destacadas em vermelho).
5. Confirme — o sistema cria/atualiza os funcionários e mostra o resumo do import.

### 5. Bater ponto
1. **Menu → Ponto → Lançar Ponto** (`/ponto`).
2. Escolha a obra (se for um operacional alocado em mais de uma).
3. Clique em **"Bater Ponto"** no card do funcionário — o sistema registra o horário automaticamente.
4. Para reconhecimento facial: **Menu → Ponto → Ponto Facial** (`/ponto/facial`) usa a câmera do dispositivo.
5. Para corrigir uma marcação: clique em **"Editar"** ou **"Excluir"** na linha do registro (a exclusão pede confirmação por POST).

## Dicas e cuidados

- **Antes de cadastrar funcionário**, confira se a **Função** e o **Departamento** já existem em **Configurações → Funções / Departamentos**; se não existirem, crie primeiro.
- O **tipo de remuneração** afeta o cálculo de folha. Trocá-lo depois muda a base de cálculo retroativamente — só altere com a folha do mês fechada.
- **Foto facial** é obrigatória para usar o ponto facial. Cadastre por **Ponto → Gerenciar Fotos Faciais** (`/ponto/gerenciar-fotos-faciais`).
- **Inativar em vez de excluir**: funcionários com ponto/folha históricos não podem ser apagados. Use o botão de inativar no perfil para tirá-los das telas de operação.
