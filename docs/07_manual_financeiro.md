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

![Tela principal do Modulo Financeiro](placeholder_financeiro_dashboard.png)

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

![KPIs do Dashboard Financeiro](placeholder_financeiro_kpis.png)

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

![Cadastro de conta no Plano de Contas](placeholder_plano_contas_cadastro.png)

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

![Cadastro de Centro de Custo](placeholder_centro_custo_cadastro.png)

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

![Formulario de nova conta a pagar](placeholder_conta_pagar_nova.png)

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

![Lista de Contas a Pagar](placeholder_contas_pagar_lista.png)

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

![Formulario de nova conta a receber](placeholder_conta_receber_nova.png)

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

![Lista de Contas a Receber](placeholder_contas_receber_lista.png)

---

## 7.6. Fluxo de Caixa

O **Fluxo de Caixa** apresenta o extrato completo de todas as movimentacoes financeiras da empresa, consolidando entradas e saidas em uma visao unificada.

### Acessando o Fluxo de Caixa

Acesse **Financeiro → Fluxo de Caixa** ou visualize a secao Fluxo de Caixa diretamente no dashboard financeiro em `/financeiro`.

![Tela de Fluxo de Caixa](placeholder_fluxo_caixa.png)

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

![Relatorio DRE](placeholder_relatorio_dre.png)

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

![Relatorio de Despesas por Centro de Custo](placeholder_despesas_centro_custo.png)

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

*Proximo capitulo: [Capitulo 8 — Modulo Consolidado](08_manual_consolidado.md)*
