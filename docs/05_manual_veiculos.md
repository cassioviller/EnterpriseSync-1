# Capítulo 5 — Gestão de Frota e Veículos

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

## Resumo das URLs do Módulo

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

## Dicas e Boas Práticas

1. **Mantenha a quilometragem atualizada** — Sempre registre os usos com KM inicial e final corretos para que o sistema calcule corretamente o custo por quilômetro;
2. **Classifique os custos corretamente** — Utilize o tipo de custo adequado para cada despesa, pois isso impacta diretamente nos gráficos e relatórios analíticos;
3. **Vincule custos e usos às obras** — Sempre que possível, associe os registros a uma obra para possibilitar o rateio correto das despesas;
4. **Monitore os alertas de documentação** — Verifique regularmente os KPIs de licenciamento e seguro para evitar irregularidades;
5. **Registre todos os passageiros** — O controle de passageiros por posição (frente/traseira) é importante para conformidade com normas de segurança e seguro;
6. **Revise os gráficos mensalmente** — Utilize os gráficos de custos por mês e por categoria para identificar oportunidades de redução de despesas.

---

*Manual do Usuário — SIGE EnterpriseSync v8.0 | Capítulo 5: Gestão de Frota e Veículos*
