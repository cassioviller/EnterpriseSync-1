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

![Tela principal de obras](placeholder_tela_obras.png)

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

![Filtros de pesquisa de obras](placeholder_filtros_obras.png)

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

![Card de obra com informações e KPIs](placeholder_card_obra.png)

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

![Formulário de nova obra](placeholder_form_nova_obra.png)

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

![Campos de geolocalização no formulário](placeholder_geofencing_obra.png)

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

![Dashboard executivo da obra](placeholder_dashboard_obra.png)

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

![Planejamento de serviços da obra](placeholder_servicos_obra.png)

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

![Gráfico orçado vs realizado](placeholder_orcado_realizado.png)

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

> **Integração com o Financeiro:** Os lançamentos financeiros feitos no módulo **Financeiro** que estejam vinculados a esta obra são automaticamente considerados na análise. Acesse o módulo Financeiro pelo menu lateral para registrar recebimentos e pagamentos.

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

> **Para saber mais:** O preenchimento completo do RDO é explicado no **Capítulo 6 — Registro Diário de Obra (RDO)**. Lá você encontra instruções detalhadas para cada seção do formulário.

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

![Geração de relatórios de obras](placeholder_relatorios_obra.png)

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

*Próximo capítulo: [Capítulo 5 — Gestão de Veículos e Frota](05_manual_veiculos.md)*
