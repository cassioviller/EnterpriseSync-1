# Capítulo 5 — Gestão de Frota e Veículos

## 5.1. Introdução

Bem-vindo ao módulo de **Gestão de Frota** do SIGE! Este é o seu centro de controle para tudo que envolve os veículos da empresa. Aqui você pode:

- Cadastrar todos os veículos da sua frota (carros, caminhonetes, caminhões, vans, motos);
- Registrar cada viagem realizada — quem dirigiu, para onde foi, quantos quilômetros rodou e quem estava no veículo;
- Controlar todos os gastos — combustível, manutenção, pedágio, seguro, licenciamento, multas e muito mais;
- Acompanhar indicadores importantes como custo total, custo por quilômetro e quilometragem acumulada;
- Visualizar gráficos que mostram para onde está indo o dinheiro da frota;
- Ficar de olho nos vencimentos de licenciamento e seguro para não ter surpresas.

Para acessar o módulo, basta clicar em **Veículos** no menu lateral do sistema.

[IMAGEM: Menu lateral com destaque no item Veículos]

> **Dica rápida:** O Dashboard principal do SIGE também mostra um resumo com a quantidade de veículos cadastrados na sua frota.

---

## 5.2. Visualizando a Lista de Veículos

Ao clicar em **Veículos** no menu lateral, você verá a tela principal com todos os veículos cadastrados. Cada veículo aparece em formato de card, permitindo uma visão rápida do estado da sua frota.

[IMAGEM: Tela principal de veículos com listagem em cards]

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

[IMAGEM: Botões de ação disponíveis nos cards de veículos]

---

## 5.3. Cadastrando um Novo Veículo

Quando a empresa adquire um novo veículo ou você precisa incluir um veículo que já existia mas não estava no sistema, siga estes passos:

### Passo a passo

1. Acesse **Veículos** no menu lateral
2. Clique no botão **Novo Veículo** (geralmente no canto superior da tela)
3. Preencha o formulário conforme orientações abaixo
4. Clique em **Salvar** para concluir o cadastro

[IMAGEM: Formulário de cadastro de novo veículo]

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

[IMAGEM: Formulário de registro de uso do veículo]

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

[IMAGEM: Tabela de histórico de viagens do veículo]

> **Dica:** Clique em qualquer viagem na tabela para ver todos os detalhes completos, incluindo a lista de passageiros organizada por posição (frente e traseira).

---

## 5.5. Controlando os Custos dos Veículos

Manter o controle financeiro da frota é essencial. O SIGE permite que você registre cada centavo gasto com os veículos, separando por categoria para facilitar a análise.

### Passo a passo para lançar um custo

1. Na lista de veículos, localize o veículo que teve a despesa
2. Clique no botão **Lançar Custo** no card desse veículo
3. Preencha o formulário conforme as orientações abaixo
4. Clique em **Salvar** para registrar o custo

[IMAGEM: Formulário de lançamento de custo do veículo]

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

[IMAGEM: Tabela de histórico de custos do veículo]

> **Importante:** Você pode editar ou excluir um lançamento de custo caso tenha cometido algum erro. Basta clicar no registro desejado na tabela de histórico.

---

## 5.6. Painel de Detalhes do Veículo

O painel de detalhes é onde você encontra **tudo** sobre um veículo em um só lugar. Para acessá-lo, basta clicar no card do veículo na lista principal.

[IMAGEM: Tela de detalhes do veículo com KPIs e gráficos]

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

[IMAGEM: Gráfico de barras de custos mensais]

**Gráfico de Custos por Categoria**

Este gráfico circular (pizza) mostra a distribuição percentual dos gastos por tipo. Com ele você descobre:

- Qual tipo de despesa mais pesa no bolso (combustível? manutenção?)
- Se existe alguma categoria de custo desproporcional
- Onde focar esforços para reduzir custos

*Exemplo prático: Se o gráfico mostra que 60% dos custos são com combustível e 25% com manutenção, você sabe que investir em rotas mais eficientes ou em veículos mais econômicos pode trazer uma boa economia.*

[IMAGEM: Gráfico circular de distribuição de custos por categoria]

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

*Manual do Usuário — SIGE EnterpriseSync | Capítulo 5: Gestão de Frota e Veículos*
