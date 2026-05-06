# Financeiro

O módulo **Financeiro** concentra o controle de **contas a pagar**, **contas a receber**, **fluxo de caixa** e **bancos**. Ele recebe lançamentos automaticamente de vários módulos (folha de pagamento, RDO, propostas aprovadas, medições) e permite lançamentos manuais para despesas avulsas. A contabilização em partidas dobradas roda em paralelo no módulo de Contabilidade.

## Para que serve

- Controlar **vencimentos a pagar** (fornecedores, salários, despesas gerais) e marcar pagamentos.
- Controlar **vencimentos a receber** (clientes, medições) e baixar recebimentos.
- Acompanhar o **fluxo de caixa** projetado e realizado.
- Cadastrar e conciliar **contas bancárias**.
- Visualizar **DRE** e indicadores financeiros via dashboard.

## Como acessar

- **Menu superior → "Financeiro" → "Dashboard"** (`/financeiro/`).
- **Menu → Financeiro → "Fluxo de Caixa"** (`/financeiro/fluxo-caixa`).
- **Menu → Financeiro → "Gestão de Custos"** (`/gestao-custos/`) — lançamentos operacionais V2 com aprovação.
- **Menu → Financeiro → "Contas a Receber"** (`/financeiro/contas-receber`).
- **Menu → Financeiro → "Bancos"** (`/financeiro/bancos`).
- **Menu → Financeiro → "Folha de Pagamento"** (`/folha/dashboard`) — capítulo dedicado neste manual.
- **Menu → Financeiro → "Contabilidade"** (`/contabilidade/dashboard`) — partidas dobradas.

## Fluxos principais

### 1. Lançar uma conta a pagar manual
1. **Menu → Financeiro → Dashboard → "Contas a Pagar"** (ou diretamente `/financeiro/contas-pagar`).
2. Clique em **"+ Nova Conta a Pagar"** (botão verde no topo).
3. Em ambientes com banner amarelo de **"Versão V2 ativa"**, prefira o atalho **"Lançar Despesa Geral via Gestão de Custos"** para que a conta passe pelo fluxo de aprovação.
4. Preencha: **Fornecedor**, **Descrição**, **Categoria**, **Obra** (opcional), **Valor**, **Data de Vencimento**.
5. Clique em **"Salvar"** — a conta entra com status **PENDENTE**.

### 2. Marcar conta como paga
1. Em `/financeiro/contas-pagar`, localize a conta (use os filtros **Status** e **Obra** no topo).
2. Clique em **"Pagar"** na linha — abre `/financeiro/contas-pagar/<id>/pagar`.
3. Preencha **Data do Pagamento**, **Valor Pago**, **Conta Bancária** e **Forma de Pagamento**.
4. Clique em **"Confirmar Pagamento"** — status vai para **PAGO** (ou **PARCIAL**) e o lançamento aparece no fluxo de caixa.

### 3. Lançar / receber conta a receber
1. **Menu → Financeiro → "Contas a Receber"** (`/financeiro/contas-receber`).
2. **"+ Nova Conta a Receber"** abre o formulário (`/financeiro/contas-receber/nova`).
3. Preencha **Cliente**, **Obra** (opcional, mas recomendado), **Descrição**, **Valor**, **Vencimento**.
4. Para baixar o recebimento, clique em **"Receber"** na linha → preencha data/valor/banco e confirme.

> Contas a receber das **medições aprovadas** são geradas automaticamente — não precisa lançar manualmente.

### 4. Fluxo de caixa
1. **Menu → Financeiro → "Fluxo de Caixa"**.
2. Tela mostra entradas e saídas por dia/semana/mês, separando **previsto** × **realizado**.
3. Para incluir uma movimentação avulsa (transferência interna, ajuste), clique em **"+ Novo Lançamento"** (`/financeiro/fluxo-caixa/novo`).
4. Edite uma movimentação clicando no botão **"Editar"** (lápis) na linha.

### 5. Cadastrar conta bancária
1. **Menu → Financeiro → "Bancos"** (`/financeiro/bancos`).
2. Clique em **"+ Novo Banco"** (`/financeiro/bancos/novo`).
3. Preencha **Banco**, **Agência**, **Conta**, **Tipo** (corrente/poupança), **Saldo Inicial**.
4. Clique em **"Salvar"** — a conta passa a aparecer nos seletores de pagamento/recebimento.

### 6. DRE e dashboard financeiro
1. **Menu → Financeiro → Dashboard** mostra o panorama: receitas, despesas, margem.
2. Os filtros de **período** e **obra** segmentam todos os indicadores.
3. Para a contabilidade detalhada (livro razão, balancete), use **Menu → Financeiro → Contabilidade**.

## Dicas e cuidados

- **Use sempre a obra** ao lançar contas a pagar/receber — sem obra, o custo não entra no resultado da obra e distorce a margem.
- Em ambiente **V2**, despesas gerais devem ir pela **Gestão de Custos** (passa pelo aprovador). O banner amarelo no topo de Contas a Pagar lembra disso.
- **Pagamentos parciais** ajustam o saldo automaticamente — basta repetir o "Pagar" várias vezes até zerar.
- O **fluxo de caixa** combina previsões (contas em aberto) com realizado (contas baixadas). Se o número parecer estranho, confira se há contas vencidas em PENDENTE inflando o "previsto".
- **Conciliação bancária** fica em **Contabilidade** (`/contabilidade/conciliacao`), não em Bancos. Use-a periodicamente para garantir que extrato e SIGE batem.
