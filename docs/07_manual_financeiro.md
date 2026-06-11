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

![Tela principal do Módulo Financeiro](placeholder_financeiro_dashboard.png)

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

![Indicadores do Dashboard Financeiro](placeholder_financeiro_kpis.png)

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

![Filtros do Dashboard Financeiro](placeholder_financeiro_filtros.png)

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

![Formulário de nova conta a pagar](placeholder_conta_pagar_nova.png)

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

![Lista de Contas a Pagar](placeholder_contas_pagar_lista.png)

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

![Formulário de nova conta a receber](placeholder_conta_receber_nova.png)

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

![Lista de Contas a Receber](placeholder_contas_receber_lista.png)

---

## 7.5. Fluxo de Caixa — Mês a Mês

O **Fluxo de Caixa** mostra como o dinheiro da empresa se movimentou, separando o que **de fato aconteceu** (Realizado) do que **ainda está por vir** (Previsto), agrupado mês a mês.

### Como acessar o Fluxo de Caixa

Clique em **Financeiro → Fluxo de Caixa** no menu.

![Tela de Fluxo de Caixa](placeholder_fluxo_caixa.png)

### Os 4 indicadores do topo

| Card | O que mostra |
|------|--------------|
| **Saldo em Banco** | Soma dos saldos das contas bancárias cadastradas (mostra uma dica para configurá-los se estiver em R$ 0) |
| **Realizado no Período** | Entradas menos saídas que **de fato aconteceram** — verde quando positivo, vermelho quando negativo |
| **A Realizar (previsto)** | O que está por vir: a receber menos a pagar em aberto |
| **Saldo Projetado** | Projeção do período considerando o previsto — fica vermelho com alerta quando negativo |

### Gráfico de evolução

O gráfico mostra, mês a mês:

- **Barras verdes** — entradas realizadas
- **Barras vermelhas** — saídas realizadas
- **Linha azul sólida** — variação acumulada de caixa (parte de zero e soma só o Realizado)
- **Linha azul tracejada** — variação projetada (a mesma linha, incluindo o que ainda está previsto)

Quando as duas linhas coincidem, não há nada previsto em aberto naquele trecho.

### Tabela mensal

Cada linha é um mês, com **Entradas**, **Saídas**, **Saldo do mês**, **Variação acumulada**, **Previsto líquido** e o **número de lançamentos**. A linha fica verde quando o mês fechou positivo e vermelha quando fechou negativo.

**Clique num mês para expandir** e ver os lançamentos um a um (data, tipo, status, origem, descrição e valor). Movimentações sem data ficam num grupo **"Sem data"** ao final.

### Edição direto na tabela

Dentro de um mês expandido, as células com o ícone de lápis ✏ (data, descrição e valor de lançamentos manuais) podem ser editadas:

1. Dê **duplo clique** na célula
2. Altere o valor
3. **Enter** (ou ✓) salva; **Esc** (ou ✕) cancela

### Como filtrar o Fluxo de Caixa

1. **Período** — Escolha data inicial e final (ex: mês de janeiro, último trimestre)
2. **Obra** — Veja apenas as movimentações de uma obra

**Exemplo prático:** Para saber como ficou o caixa da Obra Residencial Solar no primeiro semestre:

1. Selecione o período: 01/01/2026 a 30/06/2026
2. Selecione a obra: Residencial Solar
3. Clique em Filtrar

Os indicadores, o gráfico e a tabela mensal passam a considerar só os movimentos daquela obra.

### Nova Movimentação

O botão verde **Nova Movimentação** abre um formulário para lançar uma entrada ou saída direta no caixa, com categoria, banco e obra opcionais.

> **Dica:** Use o fluxo de caixa semanalmente para conferir se não há nenhuma movimentação estranha ou lançamento esquecido — a linha de variação acumulada mostra rapidamente se o caixa está melhorando ou piorando.

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

![Custos automáticos no Dashboard](placeholder_custos_automaticos.png)

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

![Cadastro de Centro de Custo](placeholder_centro_custo_cadastro.png)

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

![Relatório DRE](placeholder_relatorio_dre.png)

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

![Relatório de Despesas por Centro de Custo](placeholder_despesas_centro_custo.png)

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

![Finanças organizadas](placeholder_financeiro_organizado.png)

---

*Próximo capítulo: [Capítulo 8 — Módulo Consolidado](08_manual_consolidado.md)*
