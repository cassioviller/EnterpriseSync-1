# 📘 Manual do Usuário - SIGE v9.0
## Sistema Integrado de Gestão Empresarial para Construção Civil

---

## 📋 Índice

1. [Bem-vindo ao SIGE](#1-bem-vindo-ao-sige)
2. [Primeiros Passos](#2-primeiros-passos)
3. [Navegação e Interface](#3-navegação-e-interface)
4. [Módulo Comercial](#4-módulo-comercial)
5. [Gestão de Obras](#5-gestão-de-obras)
6. [Controle de Equipes](#6-controle-de-equipes)
7. [Gestão de Pessoas](#7-gestão-de-pessoas)
8. [Gestão Financeira](#8-gestão-financeira)
9. [Almoxarifado](#9-almoxarifado)
10. [Gestão de Frota](#10-gestão-de-frota)
11. [Relatórios e Dashboards](#11-relatórios-e-dashboards)
12. [Configurações](#12-configurações)
13. [Perguntas Frequentes](#13-perguntas-frequentes)

---

## 1. Bem-vindo ao SIGE

### O que é o SIGE?

O **SIGE (Sistema Integrado de Gestão Empresarial)** é uma plataforma completa desenvolvida especialmente para empresas de construção civil de pequeno e médio porte. O sistema integra todas as áreas da sua empresa em um único lugar:

- 💼 **Comercial**: Propostas e orçamentos
- 🏗️ **Obras**: Controle de execução e RDO (Relatório Diário de Obras)
- 👷 **Equipes**: Gestão de funcionários e ponto eletrônico
- 💰 **Financeiro**: Contas a pagar, receber e fluxo de caixa
- 📊 **Contabilidade**: Lançamentos automáticos e demonstrativos
- 📦 **Almoxarifado**: Controle de materiais, ferramentas e EPIs
- 🚗 **Frota**: Gestão de veículos e manutenções
- 🍽️ **Alimentação**: Controle de refeições de funcionários

### Principais Benefícios

✅ **Tudo Integrado**: Informações circulam automaticamente entre os módulos  
✅ **Economia de Tempo**: Menos trabalho manual, mais automação  
✅ **Segurança**: Cada empresa vê apenas seus dados (multi-tenant)  
✅ **Mobilidade**: Acesso pelo celular para ponto eletrônico e RDO  
✅ **Decisões Inteligentes**: Dashboards com indicadores em tempo real  

---

## 2. Primeiros Passos

### 2.1 Como Acessar o Sistema

1. Abra seu navegador (Chrome, Firefox, Safari ou Edge)
2. Digite o endereço do SIGE fornecido pela sua empresa
3. Insira seu **e-mail** e **senha**
4. Clique em **"Entrar"**

### 2.2 Primeiro Acesso

No primeiro acesso, você verá o **Dashboard Principal** com uma visão geral da empresa:

- 📊 **KPIs Principais**: Obras ativas, funcionários, custos do mês
- ⚠️ **Alertas**: Vencimentos, pendências e ações necessárias
- 📈 **Gráficos**: Evolução de custos, receitas e produtividade

### 2.3 Perfis de Usuário

O SIGE possui diferentes níveis de acesso:

- 👑 **Administrador**: Acesso total ao sistema
- 👨‍💼 **Gerente**: Gestão de obras, equipes e relatórios
- 👷 **Funcionário**: Acesso a ponto eletrônico e RDO
- 📋 **Operacional**: Almoxarifado, frota e alimentação

---

## 3. Navegação e Interface

### 3.1 Menu Principal

O menu superior possui todas as funcionalidades do sistema:

```
┌─────────────────────────────────────────────────────────────┐
│  SIGE - Sua Empresa    [Dashboard] [RDOs] [Obras] [Funcionários] [Equipe] [Ponto]  │
│                        [$Financeiro] [🚗Veículos] [🍽️Alimentação] [📦Almoxarifado]   │
└─────────────────────────────────────────────────────────────┘
```

### 3.2 Ícones e Significados

- 🏠 **Dashboard**: Visão geral
- 📋 **RDOs**: Relatórios Diários de Obra
- 🏗️ **Obras**: Gestão de projetos
- 👷 **Funcionários**: Cadastro de equipes
- ⏰ **Ponto**: Registro de jornada
- 💰 **Financeiro**: Contas e fluxo de caixa
- 🚗 **Veículos**: Gestão de frota
- 🍽️ **Alimentação**: Controle de refeições
- 📦 **Almoxarifado**: Materiais e ferramentas

### 3.3 Cards e Resumos

Todas as páginas principais exibem **cards informativos** na parte superior:

```
┌──────────────┐  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐
│ Total Obras  │  │ Funcionários │  │ Custos Mês   │  │ Contas a     │
│    15        │  │     42       │  │ R$ 85.500,00 │  │ Vencer       │
│    Ativas    │  │              │  │              │  │     8        │
└──────────────┘  └──────────────┘  └──────────────┘  └──────────────┘
```

---

## 4. Módulo Comercial

### 4.1 Propostas Comerciais

#### Como Criar uma Proposta

1. Acesse **Menu > Propostas > Nova Proposta**
2. Preencha as informações:
   - **Cliente**: Nome ou empresa
   - **Título**: Ex: "Reforma Escritório Centro"
   - **Prazo**: Data de início e fim estimados
3. Adicione **itens** à proposta:
   - Clique em **"+ Adicionar Item"**
   - Informe: Categoria, Descrição, Quantidade, Valor
   - Exemplo: Categoria "Mão de Obra", Descrição "Pedreiro", Qtd 30 dias, Valor R$ 200/dia
4. O sistema **calcula automaticamente** o valor total
5. Clique em **"Salvar Proposta"**

#### Gerar PDF da Proposta

1. Na lista de propostas, clique no ícone **📄 PDF**
2. O sistema gera um documento profissional com:
   - Logo da empresa
   - Dados do cliente
   - Itens detalhados por categoria
   - Valor total
3. Faça download ou envie por e-mail

#### Converter Proposta em Obra

Quando o cliente aprovar:

1. Abra a proposta aprovada
2. Clique em **"Converter em Obra"**
3. O sistema cria automaticamente:
   - ✅ Obra no sistema
   - ✅ Orçamento base
   - ✅ Estrutura para RDOs
4. Agora você pode alocar equipes e iniciar o controle!

---

## 5. Gestão de Obras

### 5.1 Cadastro de Obras

#### Criar Nova Obra

1. **Menu > Obras > Nova Obra**
2. Preencha:
   - **Nome**: Ex: "Ed. Residencial Jardim das Flores"
   - **Cliente**: Selecione da lista
   - **Endereço**: Localização completa
   - **Data Início**: Quando a obra começa
   - **Previsão de Término**: Estimativa de conclusão
   - **Valor Orçado**: Total do contrato
3. Salvar

#### Tipos de Informação

- 📍 **Localização**: Endereço completo para controle
- 💰 **Orçamento**: Valor contratado vs. custos reais
- 📅 **Cronograma**: Datas de início e fim
- 👷 **Equipe Alocada**: Funcionários vinculados

### 5.2 RDO - Relatório Diário de Obra

O RDO é o **coração do controle da obra**. Registro diário de:
- Mão de obra presente
- Equipamentos utilizados
- Serviços executados
- Ocorrências e observações
- Fotos do andamento

#### Como Criar um RDO

1. **Menu > RDOs > Novo RDO** ou **Menu > Funcionário > RDO Consolidado**
2. Selecione:
   - **Obra**: Qual projeto
   - **Data**: Dia do registro
3. **Aba Mão de Obra**:
   - Clique em **"+ Adicionar Funcionário"**
   - Selecione o funcionário
   - Informe função e horas trabalhadas
   - Repita para toda a equipe presente
4. **Aba Equipamentos** (se houver):
   - Adicione máquinas/equipamentos usados
   - Informe horas de operação
5. **Aba Serviços**:
   - Registre o que foi executado
   - Ex: "Concretagem laje 2º pavimento - 30m²"
6. **Aba Ocorrências**:
   - Registre problemas, atrasos ou observações
   - Ex: "Chuva interrompeu trabalho às 15h"
7. **Aba Fotos**:
   - Clique em **"Upload"** e selecione fotos
   - Mínimo 2-3 fotos por dia é recomendado
8. **Salvar RDO**

#### ⚠️ Importante sobre RDO

- 📅 **Diário**: Deve ser preenchido todo dia útil
- ⏰ **Pontualidade**: Preencha no mesmo dia sempre que possível
- 📸 **Fotos**: Evidências visuais são fundamentais
- ✅ **Integração Automática**: 
  - Mão de obra do RDO → Alimenta a Folha de Pagamento
  - Custos do RDO → Atualizam Custos da Obra
  - Equipamentos → Registram uso da Frota

---

## 6. Controle de Equipes

### 6.1 Cadastro de Funcionários

#### Adicionar Novo Funcionário

1. **Menu > Funcionários > Novo Funcionário**
2. **Dados Pessoais**:
   - Nome completo
   - CPF
   - Data de nascimento
   - Endereço, telefone, e-mail
3. **Dados Profissionais**:
   - **Função**: Pedreiro, Servente, Encarregado, etc.
   - **Data de Admissão**
   - **Salário Base**
   - **Horário de Trabalho**: Ex: 7h-16h (segunda a sexta)
4. Salvar

#### Funções Disponíveis

O sistema vem com funções pré-cadastradas:
- Pedreiro
- Servente
- Encarregado
- Mestre de Obras
- Eletricista
- Pintor
- Armador
- Carpinteiro

Você pode criar novas em **Menu > Configurações > Funções**.

### 6.2 Ponto Eletrônico

#### Como Funciona

O SIGE possui um **ponto eletrônico compartilhado** que pode ser acessado por celular/tablet na obra.

#### Registrar Ponto

1. Acesse **Menu > Ponto** (ou use o link direto no celular)
2. Funcionário seleciona seu nome
3. Clique em **"Registrar Ponto"**
4. Sistema registra:
   - ⏰ Horário exato
   - 📍 Localização GPS (se habilitado)
   - 📸 Foto (opcional)

#### Tipos de Registro

- 🟢 **Entrada**: Início do expediente
- 🔴 **Saída**: Fim do expediente
- 🍽️ **Saída Almoço / Retorno**: Intervalo

#### Consultar Pontos

1. **Menu > Funcionários > [Nome] > Registros de Ponto**
2. Visualize:
   - Todos os registros do mês
   - Total de horas trabalhadas
   - Horas extras (HE 50% e HE 100%)
   - Atrasos e faltas

---

## 7. Gestão de Pessoas

### 7.1 Folha de Pagamento

O SIGE calcula automaticamente a folha com base nos registros de ponto.

#### Gerar Folha de Pagamento

1. **Menu > Folha de Pagamento**
2. Selecione o **período** (competência):
   - Ex: "Outubro/2025"
3. Clique em **"Gerar Folha"**
4. O sistema calcula:
   - ✅ Dias trabalhados
   - ✅ Horas normais
   - ✅ **Horas Extras 50%** (sábados e dias úteis além da jornada)
   - ✅ **Horas Extras 100%** (domingos e feriados)
   - ✅ **Descontos de atrasos** (minutos acumulados)
   - ✅ Salário líquido

#### Entendendo a Folha

**Exemplo de Cálculo**:
```
João da Silva - Pedreiro
Salário Base: R$ 2.500,00

Horas Normais: 176h
HE 50% (Sábados): 16h × 1.5 = 24h × R$ 14,20 = R$ 340,80
HE 100% (Domingos): 8h × 2.0 = 16h × R$ 14,20 = R$ 227,20
Atrasos: 45min = 0,75h × R$ 14,20 = (R$ 10,65)

Salário Bruto: R$ 3.057,35
Descontos (INSS, etc): (R$ 305,74)
Salário Líquido: R$ 2.751,61
```

#### Integração Automática

Quando você gera a folha:
- 📊 **Contabilidade**: Lançamentos contábeis criados automaticamente
- 💰 **Contas a Pagar**: Cada salário vira uma conta a pagar
- 📈 **Custos**: Custos de mão de obra atualizados por obra

---

## 8. Gestão Financeira

### 8.1 Contas a Pagar

#### Criar Conta a Pagar

1. **Menu > $ Financeiro > Contas a Pagar**
2. Clique em **"+ Nova Conta a Pagar"**
3. Preencha:
   - **Fornecedor**: Nome (o sistema cria automaticamente se não existir)
   - **CPF/CNPJ**: Identificação do fornecedor
   - **Descrição**: Ex: "NF 1234 - Material de construção"
   - **Valor**: R$ 5.000,00
   - **Vencimento**: 30/11/2025
   - **Número do Documento**: NF-1234 (opcional)
   - **Obra** (opcional): Vincule a uma obra específica
4. Salvar

#### Pagar (Baixar) Conta

1. Na lista de contas, clique em **"$ Baixar"**
2. Informe:
   - **Valor a Pagar**: Total ou parcial
   - **Data do Pagamento**: Quando foi pago
   - **Banco**: De qual conta saiu o dinheiro
   - **Forma**: Dinheiro, PIX, Transferência, etc.
3. Confirmar

**Status Automático**:
- 🟡 **PENDENTE**: Ainda não paga
- 🟠 **PARCIAL**: Paga parcialmente
- 🟢 **PAGA**: Totalmente quitada

#### KPIs em Tempo Real

A tela de Contas a Pagar exibe:

```
┌──────────────┐  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐
│  Vencidas    │  │ A Vencer     │  │  Pendentes   │  │ Pagas no Mês │
│ R$ 500,00    │  │ R$ 4.050,00  │  │ R$ 14.430,00 │  │ R$ 5.350,00  │
└──────────────┘  └──────────────┘  └──────────────┘  └──────────────┘
```

### 8.2 Contas a Receber

Funciona de forma similar às Contas a Pagar, mas para **recebimentos de clientes**.

#### Criar Conta a Receber

1. **Menu > $ Financeiro > Contas a Receber**
2. Clique em **"+ Nova Conta a Receber"**
3. Preencha:
   - **Cliente**: Nome do cliente
   - **CPF/CNPJ**
   - **Descrição**: Ex: "Parcela 1/3 - Obra Ed. Jardim"
   - **Valor**: R$ 15.000,00
   - **Vencimento**: 15/12/2025
   - **Obra**: Vincule para rastreabilidade
4. Salvar

#### Receber

1. Clique em **"$ Receber"**
2. Informe valor recebido e data
3. Selecione banco de destino
4. Confirmar

### 8.3 Fluxo de Caixa

Visualize a saúde financeira da empresa:

1. **Menu > $ Financeiro > Fluxo de Caixa**
2. Veja:
   - 📈 **Entradas**: Tudo que entrou
   - 📉 **Saídas**: Tudo que saiu
   - 💰 **Saldo**: Diferença (entradas - saídas)
3. Filtre por período (mês, trimestre, ano)

### 8.4 Custos de Obras

#### Registrar Custo Manual

1. **Menu > Custos**
2. **"+ Novo Custo"**
3. Preencha:
   - **Obra**: Selecione a obra
   - **Categoria**: Material, Mão de Obra, Equipamento, Subempreiteiro
   - **Descrição**: Detalhe o custo
   - **Valor**: R$ 1.200,00
   - **Data**: Quando ocorreu
4. Salvar

#### Custos Automáticos

⚠️ **Importante**: Muitos custos são lançados automaticamente:
- 📋 **RDO Finalizado** → Custos de mão de obra e equipamentos
- 🚗 **Uso de Veículo** → Custo de combustível e depreciação
- 🍽️ **Refeições** → Custo de alimentação dos funcionários
- 📦 **Saída de Almoxarifado** → Custo de materiais

#### Dashboard de Custos

```
┌─────────────────────────────────────────┐
│  Total do Mês: R$ 45.800,00             │
├─────────────────────────────────────────┤
│  Por Categoria:                         │
│  🧱 Materiais:      40% - R$ 18.320,00  │
│  👷 Mão de Obra:    35% - R$ 16.030,00  │
│  🚗 Equipamentos:   15% - R$ 6.870,00   │
│  🍽️ Alimentação:    10% - R$ 4.580,00   │
└─────────────────────────────────────────┘
```

### 8.5 Contabilidade

#### Lançamentos Automáticos

O SIGE integra automaticamente com a contabilidade:

1. **Folha de Pagamento Gerada** →
   - Débito: Despesa com Pessoal
   - Crédito: Salários a Pagar

2. **Conta Paga** →
   - Débito: Fornecedores
   - Crédito: Banco

3. **Conta Recebida** →
   - Débito: Banco
   - Crédito: Receita de Serviços

#### Relatórios Contábeis

1. **Menu > Contabilidade**
2. Acesse:
   - **Plano de Contas**: Estrutura contábil
   - **Balancete**: Saldos de todas as contas
   - **DRE**: Demonstrativo de Resultado (Receitas - Despesas)
3. Selecione competência e exporte para Excel

---

## 9. Almoxarifado

### 9.1 Estrutura

O almoxarifado organiza itens em **categorias**:

- 🧱 **Materiais de Construção**: Cimento, areia, tijolos
- 🔧 **Ferramentas**: Furadeiras, serras, martelos
- 🦺 **EPIs**: Capacetes, luvas, óculos de proteção

### 9.2 Cadastrar Item

1. **Menu > 📦 Almoxarifado > Categorias**
2. Certifique-se de que a categoria existe (ou crie uma nova)
3. **Almoxarifado > Itens > + Novo Item**
4. Preencha:
   - **Nome**: Ex: "Cimento CP-II 50kg"
   - **Categoria**: Materiais de Construção
   - **Código**: CIMENT-001 (opcional)
   - **Tipo de Controle**:
     - **CONSUMÍVEL**: Controlado por quantidade (cimento, areia)
     - **SERIALIZADO**: Controlado por número de série (ferramentas)
   - **Unidade**: Saco, Kg, M³, Unidade
   - **Estoque Mínimo**: 20 (alerta quando atingir)
5. Salvar

### 9.3 Entrada de Material

Quando comprar material:

1. **Almoxarifado > Entradas > + Nova Entrada**
2. Preencha:
   - **Item**: Selecione da lista
   - **Quantidade**: 100 (sacos)
   - **Valor Unitário**: R$ 32,50
   - **Fornecedor**: (opcional)
   - **Nota Fiscal**: NF-5678 (opcional)
   - **Obra de Destino** (opcional): Se já sabe onde vai usar
3. Salvar

**O que acontece**:
- ✅ Estoque atualizado (+100)
- ✅ Valor total calculado (R$ 3.250,00)
- ✅ Movimento registrado no histórico

### 9.4 Saída de Material

Quando usar material em obra:

1. **Almoxarifado > Saídas > + Nova Saída**
2. Preencha:
   - **Item**: Cimento CP-II 50kg
   - **Quantidade**: 30
   - **Obra**: Ed. Jardim das Flores
   - **Motivo**: Concretagem laje 2º pav
   - **Funcionário Responsável**: João Silva
3. Salvar

**Integração Automática**:
- 📉 Estoque reduzido (-30)
- 💰 Custo lançado automaticamente na obra (30 × R$ 32,50 = R$ 975,00)
- 📊 Custo aparece no dashboard da obra

### 9.5 Ferramentas Serializadas

Para ferramentas com número de série:

#### Entrada
1. Marque item como **SERIALIZADO**
2. Na entrada, informe:
   - Número de série de cada unidade
   - Ex: FURAD-001, FURAD-002, FURAD-003
3. Estado: Novo, Usado, Recondicionado

#### Rastreamento
- 📍 Saiba **quem está com cada ferramenta**
- 📅 **Quando foi retirada** e por qual funcionário
- 🔄 **Histórico completo** de movimentações

---

## 10. Gestão de Frota

### 10.1 Cadastro de Veículos

1. **Menu > 🚗 Veículos > + Novo Veículo**
2. Preencha:
   - **Placa**: ABC-1234
   - **Marca/Modelo**: Ford Ranger XLT
   - **Ano**: 2020
   - **Tipo**: Caminhonete, Caminhão, Carro, Moto
   - **Status**: Ativo, Manutenção, Inativo
3. **Informações de Controle**:
   - **Hodômetro Atual**: 45.000 km
   - **Próxima Revisão**: 50.000 km
   - **Vencimento IPVA**: 31/03/2026
   - **Vencimento Seguro**: 15/07/2026
4. Salvar

### 10.2 Registrar Uso

Toda vez que um veículo for usado:

1. **Veículos > [Placa] > + Novo Uso**
2. Preencha:
   - **Data**: Quando foi usado
   - **Obra**: Qual obra (se aplicável)
   - **Motorista**: Quem dirigiu
   - **KM Inicial**: 45.000
   - **KM Final**: 45.180
   - **KM Percorridos**: 180 (calculado automaticamente)
   - **Finalidade**: Ex: "Transporte de materiais"
3. Salvar

**Integração**:
- 💰 Custo de depreciação lançado na obra
- 📊 Relatório de KM por veículo atualizado

### 10.3 Abastecimentos

1. **Veículos > [Placa] > + Abastecimento**
2. Preencha:
   - **Data/Hora**
   - **Litros**: 45,5
   - **Valor Total**: R$ 250,00
   - **Valor por Litro**: R$ 5,49 (calculado)
   - **KM Atual**: 45.180
   - **Posto**: Nome do posto
3. Salvar

**Indicadores Calculados**:
- ⛽ **Consumo Médio**: km/litro
- 💰 **Custo por KM**

### 10.4 Manutenções

#### Registrar Manutenção

1. **Veículos > [Placa] > + Manutenção**
2. **Tipo**:
   - 🔧 **Preventiva**: Revisão agendada
   - ⚠️ **Corretiva**: Quebrou/defeito
3. Preencha:
   - **Descrição**: "Troca de óleo e filtros"
   - **Valor**: R$ 350,00
   - **Oficina**: Nome da oficina
   - **Data Entrada**: Quando levou
   - **Data Saída**: Quando ficou pronta
   - **Próxima Manutenção KM**: 50.000 km
4. Salvar

### 10.5 Alertas Automáticos

O sistema alerta quando:

- 🔴 **Crítico** (até 7 dias): IPVA ou seguro vencendo
- 🟠 **Alta** (8-15 dias): Revisão próxima
- 🟡 **Média** (16-30 dias): Documentação a renovar

Acesse **Dashboard Frota** para ver todos os alertas.

---

## 11. Relatórios e Dashboards

### 11.1 Dashboard Principal

Visão consolidada da empresa:

**KPIs Principais**:
```
┌─────────────────┬─────────────────┬─────────────────┬─────────────────┐
│ Obras Ativas    │ Funcionários    │ Custos do Mês   │ Faturamento     │
│      15         │      42         │  R$ 125.400,00  │  R$ 180.000,00  │
│  ⬆️ +2 no mês   │  ⬇️ -3 no mês   │  ⬆️ +8% vs ant. │  ⬆️ +12% vs ant.│
└─────────────────┴─────────────────┴─────────────────┴─────────────────┘
```

**Gráficos**:
- 📊 Evolução de custos (últimos 6 meses)
- 📈 Obras: orçado vs. realizado
- 🎯 Produtividade por equipe

### 11.2 Relatórios Disponíveis

#### Por Módulo

1. **Obras**:
   - Obras em andamento
   - Orçado vs. Realizado
   - Cronograma vs. Execução
   
2. **Funcionários**:
   - Folha de pagamento mensal
   - Horas extras por funcionário
   - Banco de horas

3. **Financeiro**:
   - Contas a pagar/receber
   - Fluxo de caixa
   - DRE (Demonstração de Resultado)

4. **Custos**:
   - Custos por obra
   - Custos por categoria
   - TCO (Custo Total de Propriedade)

5. **Frota**:
   - Uso de veículos
   - Manutenções realizadas
   - Consumo de combustível

6. **Almoxarifado**:
   - Estoque atual
   - Movimentações
   - Materiais por obra

#### Como Gerar Relatório

1. Acesse o módulo desejado
2. Clique em **"📊 Relatórios"**
3. Selecione:
   - **Período**: Mês, trimestre, ano, personalizado
   - **Filtros**: Obra, funcionário, categoria, etc.
4. Clique em **"Gerar"**
5. **Visualize** na tela ou **Exporte** (PDF/Excel)

---

## 12. Configurações

### 12.1 Dados da Empresa

1. **Menu > ⚙️ Configurações > Empresa**
2. Mantenha atualizado:
   - Razão Social
   - CNPJ
   - Endereço
   - Telefones
   - E-mail
   - **Logo**: Upload da logo (aparece em propostas e relatórios)

### 12.2 Usuários e Permissões

#### Adicionar Usuário

1. **Configurações > Usuários > + Novo**
2. Preencha:
   - Nome
   - E-mail (usado para login)
   - Senha inicial
   - **Perfil**:
     - 👑 Administrador
     - 👨‍💼 Gerente
     - 👷 Funcionário
     - 📋 Operacional
3. Salvar

#### Permissões por Perfil

| Funcionalidade | Admin | Gerente | Funcionário | Operacional |
|----------------|-------|---------|-------------|-------------|
| Propostas      | ✅    | ✅      | ❌          | ❌          |
| Obras          | ✅    | ✅      | 👁️ Ver     | 👁️ Ver     |
| RDO            | ✅    | ✅      | ✅ Preencher| ❌          |
| Funcionários   | ✅    | ✅      | 👁️ Ver Próprio | ❌    |
| Ponto          | ✅    | 👁️ Ver | ✅ Registrar| ❌          |
| Financeiro     | ✅    | 👁️ Ver | ❌          | ❌          |
| Almoxarifado   | ✅    | ✅      | ❌          | ✅          |
| Frota          | ✅    | ✅      | ❌          | ✅          |
| Configurações  | ✅    | ❌      | ❌          | ❌          |

### 12.3 Funções e Horários

#### Cadastrar Função

1. **Configurações > Funções > + Nova**
2. Preencha:
   - Nome: "Azulejista"
   - Descrição: "Responsável por assentamento de azulejos"
   - Salário Base: R$ 2.800,00
3. Salvar

#### Horários de Trabalho

1. **Configurações > Horários > + Novo**
2. Defina:
   - Nome: "Padrão Obra"
   - Entrada: 07:00
   - Saída Almoço: 12:00
   - Retorno Almoço: 13:00
   - Saída: 16:00
   - Horas Diárias: 8h
   - Dias: Segunda a Sexta
3. Salvar

Ao cadastrar funcionário, selecione o horário. O sistema usará para calcular:
- ✅ Horas normais
- ✅ Horas extras
- ✅ Atrasos

---

## 13. Perguntas Frequentes

### ❓ Geral

**P: Posso acessar o SIGE pelo celular?**  
R: Sim! O sistema é responsivo. Algumas funções como Ponto Eletrônico e RDO são otimizadas para mobile.

**P: Meus dados estão seguros?**  
R: Sim. O SIGE é multi-tenant, ou seja, cada empresa vê apenas seus próprios dados. Há isolamento total entre empresas.

**P: Posso ter múltiplos usuários?**  
R: Sim, sem limite. Cada usuário tem seu login e permissões específicas.

### ❓ Obras e RDO

**P: Esqueci de preencher o RDO de ontem. Posso fazer hoje?**  
R: Sim. Ao criar o RDO, selecione a data de ontem. Mas mantenha a disciplina de preencher diariamente!

**P: O RDO calcula automaticamente o custo da obra?**  
R: Sim! Quando você finaliza um RDO, os custos de mão de obra e equipamentos são lançados automaticamente na obra.

**P: Como sei se a obra está no orçamento?**  
R: No Dashboard de Custos, compare "Valor Orçado" vs "Custo Realizado". O sistema calcula o desvio percentual.

### ❓ Funcionários e Ponto

**P: O funcionário pode ver o contracheque dele?**  
R: Atualmente não, mas está no roadmap. Por enquanto, exporte a folha em PDF e distribua.

**P: Como funciona o cálculo de horas extras?**  
R: 
- **HE 50%** (1,5x): Sábados e horas além da jornada em dias úteis
- **HE 100%** (2,0x): Domingos e feriados

**P: Esqueci de bater o ponto. O que fazer?**  
R: Fale com seu gerente. Ele pode ajustar manualmente o registro no sistema.

### ❓ Financeiro

**P: Posso pagar uma conta em várias parcelas?**  
R: Sim! Quando for pagar, informe o valor parcial. O sistema marca como "PARCIAL" e mantém o saldo devedor.

**P: Como cadastro um fornecedor?**  
R: Não precisa! Ao criar uma conta a pagar, se o CNPJ não existir, o sistema cria o fornecedor automaticamente.

**P: Os lançamentos contábeis são automáticos?**  
R: Sim! Folha de pagamento, contas pagas/recebidas geram lançamentos contábeis automaticamente.

### ❓ Almoxarifado

**P: Como sei quando o estoque está baixo?**  
R: Configure o "Estoque Mínimo" ao cadastrar o item. Quando atingir, aparece um alerta no dashboard.

**P: Posso devolver material ao almoxarifado?**  
R: Sim, faça uma "Entrada" com origem "Devolução de Obra" e informe qual obra devolveu.

**P: Como rastrear uma ferramenta específica?**  
R: Cadastre como "SERIALIZADO" e informe o número de série. Você verá todo o histórico: quem retirou, quando, para qual obra.

### ❓ Frota

**P: Como sei quando fazer revisão?**  
R: Configure "Próxima Revisão KM" ao cadastrar manutenção. O sistema alerta quando o hodômetro se aproximar.

**P: O sistema calcula consumo de combustível?**  
R: Sim! A cada abastecimento, ele calcula km/litro baseado no abastecimento anterior.

**P: Posso vincular despesa de veículo a uma obra?**  
R: Sim! Ao registrar uso, abastecimento ou manutenção, vincule à obra. O custo será computado automaticamente.

---

## 📞 Suporte

### Precisa de Ajuda?

- 📧 **E-mail**: suporte@sige.com.br
- 📱 **WhatsApp**: (XX) XXXXX-XXXX
- 🌐 **Portal**: suporte.sige.com.br

### Atualizações

O SIGE é atualizado regularmente com:
- 🆕 Novas funcionalidades
- 🐛 Correções de bugs
- ⚡ Melhorias de performance

Fique de olho nas notificações do sistema!

---

## ✅ Checklist Rápido de Início

Use este checklist para começar a usar o SIGE:

### Semana 1 - Configuração Inicial

- [ ] Fazer login no sistema
- [ ] Atualizar dados da empresa (nome, CNPJ, logo)
- [ ] Criar usuários da equipe
- [ ] Cadastrar funções (se necessário)
- [ ] Configurar horários de trabalho

### Semana 2 - Cadastros Base

- [ ] Cadastrar todos os funcionários
- [ ] Cadastrar obras atuais
- [ ] Cadastrar fornecedores principais
- [ ] Cadastrar veículos da frota
- [ ] Configurar categorias do almoxarifado

### Semana 3 - Operação

- [ ] Iniciar registro de ponto diário
- [ ] Preencher RDOs das obras
- [ ] Registrar entradas de material
- [ ] Lançar contas a pagar pendentes
- [ ] Registrar uso de veículos

### Semana 4 - Gestão

- [ ] Gerar primeira folha de pagamento
- [ ] Analisar custos por obra
- [ ] Verificar fluxo de caixa
- [ ] Gerar relatórios gerenciais
- [ ] Ajustar processos conforme necessário

---

## 🎯 Dicas de Boas Práticas

### 1. Disciplina nos Registros

✅ **Ponto**: Registrar todo dia, na hora correta  
✅ **RDO**: Preencher diariamente, com fotos  
✅ **Saídas de Material**: Registrar no mesmo dia do uso  

### 2. Organização

✅ Use **códigos padronizados** para obras (ex: OB-2025-001)  
✅ Preencha **observações** relevantes (histórico é importante)  
✅ Tire **fotos** sempre que possível (RDO, entregas, problemas)  

### 3. Controle Financeiro

✅ Cadastre contas assim que receber a cobrança (não deixe acumular)  
✅ Vincule despesas às obras (rastreabilidade)  
✅ Revise semanalmente o fluxo de caixa  

### 4. Aproveitamento Máximo

✅ Use os **dashboards** para decisões rápidas  
✅ Gere **relatórios mensais** para análise  
✅ Configure **alertas** (estoque, vencimentos, revisões)  
✅ Treine a equipe para usar o sistema corretamente  

---

## 📚 Glossário

**Admin**: Administrador do sistema com acesso total  
**Dashboard**: Painel com visão geral e indicadores  
**HE 50%**: Hora Extra com adicional de 50% (sábados e dias úteis)  
**HE 100%**: Hora Extra com adicional de 100% (domingos e feriados)  
**KPI**: Key Performance Indicator (Indicador de Desempenho)  
**Multi-tenant**: Arquitetura que isola dados de cada empresa  
**RDO**: Relatório Diário de Obra  
**Serializado**: Item controlado por número de série individual  
**TCO**: Total Cost of Ownership (Custo Total de Propriedade)  

---

## 📖 Histórico de Versões

### v9.0 (Outubro 2025) - Versão Atual
- ✅ Multi-tenancy completo em 100% dos módulos
- ✅ Integração automática entre todos os módulos
- ✅ Dashboard de Custos, Frota e Alimentação
- ✅ Módulo Financeiro completo (Contas a Pagar/Receber)
- ✅ Almoxarifado com controle serializado
- ✅ RDO mobile-first com fotos
- ✅ Folha de pagamento com HE diferenciada (CLT)
- ✅ Contabilidade automática

---

**© 2025 SIGE - Sistema Integrado de Gestão Empresarial**  
*Desenvolvido especialmente para empresas de construção civil*

---

## 🚀 Começe Agora!

Agora que você conhece o SIGE, é hora de começar a usar!

1. Faça login
2. Siga o **Checklist Rápido de Início**
3. Explore cada módulo
4. Use o sistema diariamente
5. Veja sua empresa crescer com organização e eficiência!

**Sucesso! 🎉**
