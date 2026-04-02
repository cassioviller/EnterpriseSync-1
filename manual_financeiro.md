# Manual do Módulo Financeiro — SIGE v9.0

> Cobre todo o ciclo financeiro: lançamentos automáticos dos módulos operacionais → Gestão de Custos → aprovação → Fluxo de Caixa.

---

## Visão Geral do Fluxo

```
Módulos Operacionais          Gestão de Custos V2           Fluxo de Caixa
─────────────────────         ───────────────────           ──────────────
Transporte      ──────┐
Alimentação     ──────┤──→  PENDENTE → SOLICITADO  ──→  Saídas Previstas
Diária (Ponto)  ──────┘              → AUTORIZADO  ──→  Saídas Previstas
                                     → PAGO        ──→  Histórico (FluxoCaixa)

Material (Almox) ─────────────────────────────────→  Custo da Obra (direto)

Conta a Pagar (manual) ───────────────────────────→  Saídas Previstas
Conta a Receber (manual) ─────────────────────────→  Entradas Previstas
```

---

## PARTE A — Lançamentos Automáticos pelos Módulos

---

### A1. Transporte → Gestão de Custos

Todo lançamento de transporte cria automaticamente um custo na **Gestão de Custos V2** com categoria **TRANSPORTE**.

#### Lançamento Individual

**Caminho:** Menu superior → **Transporte** → botão **Novo Lançamento**

**Preencha:**
- Funcionário ou Veículo vinculado
- Obra (opcional, mas recomendado para rastrear o custo)
- Categoria de transporte (ex: Vale-Transporte, Táxi, Combustível)
- Data do lançamento
- Valor
- Descrição (opcional)

Clique em **Salvar**.

**O que acontece automaticamente:**
- Lançamento de transporte registrado
- Custo criado na **Gestão de Custos V2** com status **PENDENTE**, vinculado ao funcionário ou veículo

#### Lançamento em Lote (múltiplos funcionários × múltiplos dias)

**Caminho:** Menu superior → **Transporte** → **Lançamento em Lote**

**Preencha:**
- Selecione os funcionários (multi-seleção)
- Selecione o período (data início e data fim)
- Marque os dias da semana que se repetem (ex: seg, ter, qua, qui, sex)
- Obra, categoria e valor por lançamento

O sistema exibe um preview: **X funcionários × Y dias = Z lançamentos + valor total**

Clique em **Confirmar Lançamento em Lote**.

**O que acontece automaticamente:**
- Um custo na Gestão de Custos V2 é criado por funcionário com o valor total do período

---

### A2. Alimentação → Gestão de Custos

Cada lançamento de alimentação cria automaticamente um custo na **Gestão de Custos V2** com categoria **ALIMENTACAO**.

**Caminho:** Menu superior → **Alimentação** → botão **Novo Lançamento**

**Preencha:**
- Restaurante / Fornecedor
- Obra vinculada (opcional)
- Funcionários e itens consumidos
- Data e valores

Clique em **Confirmar**.

**O que acontece automaticamente:**
- Lançamento de alimentação registrado
- Custo criado na **Gestão de Custos V2** com status **PENDENTE**, vinculado ao restaurante e à obra

---

### A3. Material (Almoxarifado) → Custo da Obra

A saída de material do estoque cria o custo **diretamente na obra**, sem passar pelo fluxo de aprovação da Gestão de Custos V2.

> **Atenção:** Este é o único módulo que não passa pelo Fluxo de Caixa. O custo vai para o relatório de "Custos por Obra", não para as Saídas Previstas.

**Caminho:** Menu superior → **Almoxarifado** → **Saída de Material**

**Preencha:**
- Produto / Material
- Quantidade
- **Obra de destino** (obrigatório para que o custo seja lançado)
- Responsável / Funcionário (opcional)
- Número do lote (para rastreabilidade)

Clique em **Processar Saída**.

**O que acontece automaticamente:**
- Estoque do produto diminui
- **Custo da Obra criado** com o valor (quantidade × preço unitário)
- Esse custo aparece em: Obras → selecionar obra → aba **Custos** → categoria ALMOXARIFADO

> Se a saída não tiver obra vinculada, o custo **não é lançado** em lugar nenhum.

---

### A4. Diária de Funcionário → Gestão de Custos

Para funcionários com tipo de remuneração **Diária**, o simples ato de **bater o ponto** gera automaticamente um custo na Gestão de Custos V2.

**Caminho:** O lançamento acontece no **Ponto Eletrônico**, não no financeiro.

Opção 1 — Ponto pelo celular/tablet compartilhado:
- Menu → **Ponto Eletrônico** → funcionário se identifica → bate o ponto (entrada)

Opção 2 — Lançamento administrativo:
- Menu → **Funcionários** → selecionar funcionário → **Registrar Ponto**

**O que acontece automaticamente na primeira batida (entrada) do dia:**
- Ponto registrado
- Custo criado na **Gestão de Custos V2** com:
  - Categoria: **SALARIO**
  - Entidade: nome do funcionário
  - Valor: valor da diária configurada no cadastro do funcionário
  - Obra: vinculada ao ponto (se o funcionário bateu o ponto em uma obra)
- Idempotência: se o funcionário bater o ponto duas vezes no mesmo dia, o custo **não é duplicado**

> Para configurar o valor da diária: Funcionários → selecionar → editar → campo "Tipo de Remuneração" = Diária + "Valor da Diária".

---

## PARTE B — Aprovação na Gestão de Custos V2

Todos os custos criados por Transporte, Alimentação e Diária chegam aqui com status **PENDENTE**.

**Caminho:** Financeiro → **Gestão de Custos** (ou menu lateral)

A lista mostra todos os custos agrupados por entidade (funcionário, restaurante, veículo), com badges coloridos indicando o status:

| Badge | Status | Significado |
|---|---|---|
| Cinza | PENDENTE | Criado, aguardando solicitação |
| Amarelo | SOLICITADO | Solicitado ao aprovador, aparece no Fluxo de Caixa |
| Verde | AUTORIZADO | Aprovado, pronto para pagamento, aparece no Fluxo de Caixa |
| Azul | PAGO | Pago, registrado no histórico de FluxoCaixa |

---

### Passo 1 — Solicitar (PENDENTE → SOLICITADO)

**Caminho:** Gestão de Custos → localizar o registro → botão **Solicitar**

- Clique no botão **Solicitar** (ícone de seta / enviar)
- Confirme na caixa de diálogo se aparecer
- Status muda de PENDENTE para **SOLICITADO**

**Efeito no Fluxo de Caixa:** o custo aparece imediatamente em **Saídas Previstas**

---

### Passo 2 — Autorizar ou Recusar (SOLICITADO → AUTORIZADO ou PENDENTE)

**Caminho:** Gestão de Custos → localizar o registro SOLICITADO → botão **Autorizar** ou **Recusar**

- **Autorizar** → status muda para **AUTORIZADO**; continua em Saídas Previstas
- **Recusar** → status volta para **PENDENTE**; sai do Fluxo de Caixa

---

### Passo 3 — Pagar (AUTORIZADO → PAGO)

**Caminho:** Gestão de Custos → localizar o registro AUTORIZADO → botão **Pagar**

Um formulário aparece. Preencha:
- **Data do Pagamento** (preenche com hoje automaticamente)
- **Conta Bancária** (texto livre — ex: "BB Conta Corrente 1234-5", "Caixa Física")
- **Valor Pago** (preenche automaticamente com o valor solicitado)

Clique em **Confirmar Pagamento**.

**O que acontece automaticamente:**
- Status muda para **PAGO**
- Custo **sai das Saídas Previstas** do Fluxo de Caixa
- Um registro de **FluxoCaixa** histórico é criado (tipo SAIDA)
- Se a obra tiver contabilidade configurada → **lançamento contábil criado** automaticamente

---

## PARTE C — Resultado no Fluxo de Caixa

**Caminho:** Financeiro → **Fluxo de Caixa**

Use os filtros de **Data Início** e **Data Fim** para o período que deseja analisar.

### O que cada card mostra

| Card | Cor | O que inclui |
|---|---|---|
| Saldo Inicial | Azul | Soma do saldo atual de todos os bancos cadastrados |
| Entradas Previstas | Verde | Contas a Receber com status PENDENTE ou PARCIAL no período |
| Saídas Previstas | Vermelho | Contas a Pagar PENDENTES + Gestão de Custos SOLICITADO/AUTORIZADO no período |
| Saldo Final Projetado | Azul/Amarelo | Saldo Inicial + Entradas − Saídas |

### Tabela de Movimentos Previstos

Cada linha da tabela representa um lançamento individual:

| Cor da linha | Tipo | Origem |
|---|---|---|
| Verde | ENTRADA | Conta a Receber pendente |
| Vermelho | SAÍDA | Conta a Pagar pendente |
| Vermelho | SAÍDA | Gestão de Custos (Transporte / Alimentação / Diária) SOLICITADO ou AUTORIZADO |

---

## PARTE D — Fluxo Manual (sem módulos operacionais)

Para despesas que não passam pelos módulos de Transporte, Alimentação etc., use o lançamento direto:

### Conta a Pagar (manual)
**Caminho:** Financeiro → Contas a Pagar → **Nova Conta a Pagar**
- Preencha: Descrição, Valor, Vencimento, Fornecedor (opcional), Obra (opcional)
- Aparece imediatamente em Saídas Previstas

### Conta a Receber (manual)
**Caminho:** Financeiro → Contas a Receber → **Nova Conta a Receber**
- Preencha: Descrição, Cliente, Valor, Vencimento, Obra (opcional)
- Aparece imediatamente em Entradas Previstas

### Dar baixa (pagar ou receber)
**Caminho:** na lista → botão **Pagar** ou **Receber** → preencher valor, data, forma e banco → confirmar

---

## PARTE E — Tabela Resumo por Módulo

| Módulo | Como lançar | Vai para | Aprovação necessária | Aparece no Fluxo de Caixa |
|---|---|---|---|---|
| **Transporte** | Menu Transporte → Novo Lançamento | Gestão de Custos PENDENTE | Sim (Solicitar → Autorizar → Pagar) | Quando SOLICITADO ou AUTORIZADO |
| **Transporte Lote** | Menu Transporte → Lançamento em Lote | Gestão de Custos PENDENTE | Sim | Quando SOLICITADO ou AUTORIZADO |
| **Alimentação** | Menu Alimentação → Novo Lançamento | Gestão de Custos PENDENTE | Sim (Solicitar → Autorizar → Pagar) | Quando SOLICITADO ou AUTORIZADO |
| **Material (Saída)** | Almoxarifado → Saída de Material | Custo da Obra (direto) | Não | Não aparece (só em Custos por Obra) |
| **Diária Funcionário** | Ponto Eletrônico → bater ponto (entrada) | Gestão de Custos PENDENTE | Sim (Solicitar → Autorizar → Pagar) | Quando SOLICITADO ou AUTORIZADO |
| **Reembolso** | Financeiro → Gestão de Custos → Reembolsos | Gestão de Custos PENDENTE | Sim | Quando SOLICITADO ou AUTORIZADO |
| **Conta a Pagar** | Financeiro → Contas a Pagar → Nova | Saídas Previstas (direto) | Não | Imediatamente (status PENDENTE) |
| **Conta a Receber** | Financeiro → Contas a Receber → Nova | Entradas Previstas (direto) | Não | Imediatamente (status PENDENTE) |

---

## PARTE F — Dicas Práticas

- **O custo de material (almoxarifado) não aparece no Fluxo de Caixa.** Ele é registrado como custo realizado da obra. Para ver: Obras → selecionar a obra → aba Custos.
- **Sem Solicitar, o custo não aparece no Fluxo de Caixa.** Um lançamento de Transporte ou Alimentação recém-criado fica invisível no Fluxo até ser Solicitado.
- **Recusar não apaga o custo.** Ele volta para PENDENTE e pode ser Solicitado novamente depois de corrigido.
- **O Saldo Inicial do Fluxo de Caixa é o saldo real dos bancos.** Mantenha os bancos atualizados dando baixa correta nas contas (selecionando o banco ao pagar).
- **Pagamento parcial:** informe só o valor pago hoje; o saldo restante continua nas Saídas Previstas.
- **Diária duplicada:** o sistema protege automaticamente — bater o ponto duas vezes no mesmo dia não gera dois custos.
