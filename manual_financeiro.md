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

#### Pré-requisito: cadastrar o item no Almoxarifado

Antes de dar saída, o material precisa estar cadastrado como **Item do Almoxarifado** e ter estoque registrado via entrada.

**Cadastrar item:**
**Caminho:** Menu → **Almoxarifado** → **Itens/Produtos** → botão **Novo Item**
- Nome do item (ex: "Cimento CP-II 50kg")
- Código interno
- Unidade (saca, m², kg, un, etc.)
- Tipo: Consumível ou Serializado
- Estoque mínimo

**Registrar entrada (adicionar ao estoque):**
**Caminho:** Menu → **Almoxarifado** → **Entrada de Material**
- Selecionar o item cadastrado
- Quantidade, valor unitário, fornecedor, nota fiscal
- Clicar em confirmar

#### Realizar a Saída

**Caminho:** Menu → **Almoxarifado** → **Saída de Material**

**Preencha:**
- Item (selecionar da lista — só aparecem itens com estoque disponível)
- Quantidade
- **Obra de destino** (obrigatório para que o custo seja lançado)
- Responsável / Funcionário (opcional)
- Número do lote (para rastreabilidade)

Clique em **Processar Saída**.

**O que acontece automaticamente:**
- Estoque do item diminui
- **Custo da Obra criado** com o valor (quantidade × preço unitário)
- Esse custo aparece em: Obras → selecionar obra → aba **Custos** → categoria ALMOXARIFADO

> Se a saída não tiver obra vinculada, o custo **não é lançado** em lugar nenhum.

> **Diferença importante:** o custo de material vai direto para a obra e **não aparece em Gestão de Custos nem no Fluxo de Caixa**. Para acompanhar o gasto de materiais, use o relatório de Custos por Obra.

---

### A4. Diária de Funcionário → Gestão de Custos

Para funcionários com tipo de remuneração **Diária**, o ato de **bater o ponto pelo dispositivo compartilhado** gera automaticamente um custo na Gestão de Custos V2.

> **Importante:** O custo de diária só é criado quando o ponto é registrado pelo **Ponto Eletrônico** (dispositivo compartilhado ou reconhecimento facial). O registro manual feito pelo administrador no perfil do funcionário **não gera o custo automático**.

#### Pré-requisito: configurar o funcionário como diarista

**Caminho:** Funcionários → selecionar funcionário → botão **Editar**
- Campo "Tipo de Remuneração" → selecionar **Diária**
- Campo "Valor da Diária" → informar o valor (ex: R$ 200,00)
- Salvar

#### Registrar o ponto pelo Ponto Eletrônico (cria o custo)

**Caminho:** Menu → **Ponto Eletrônico** → funcionário se identifica → bate o ponto (entrada)

O funcionário pode se identificar por:
- Reconhecimento facial (câmera)
- Seleção manual na lista (se habilitado)

**O que acontece automaticamente na primeira batida (entrada) do dia:**
- Ponto registrado
- Custo criado na **Gestão de Custos V2** com:
  - Categoria: **SALARIO**
  - Entidade: nome do funcionário
  - Valor: valor da diária configurada
  - Obra: vinculada ao ponto (se configurado)
- Status inicial: **PENDENTE** (aguarda aprovação)
- Idempotência: segunda batida no mesmo dia **não duplica** o custo

#### O que NÃO cria o custo automático

- Registro manual de ponto feito pelo administrador no perfil do funcionário (Funcionários → perfil → Novo Registro de Ponto)
- Importação de Excel de folha de ponto
- Esses métodos registram o ponto mas não disparam o fluxo financeiro automático

---

### A5. Despesas Gerais / Avulsas → Gestão de Custos

Para despesas que não têm módulo próprio no SIGE — **aluguel de escritório, energia elétrica, água, IPTU, honorários contábeis, assinaturas de software, manutenção de equipamentos** — use a categoria **Despesa Geral / Avulsa** na Gestão de Custos V2. Assim a despesa passa pelo fluxo de aprovação antes de ser paga.

> **Diferença do ContaPagar manual:** o ContaPagar tradicional registra a despesa diretamente no financeiro sem aprovação. A Gestão de Custos exige aprovação (Solicitar → Autorizar → Pagar), dando mais controle ao gestor.

#### Passo a passo

**Caminho:** Menu → **Gestão de Custos** → botão **Novo Lançamento** → ou acesse `/gestao-custos/novo?tipo=DESPESA_GERAL`

> Também há um link direto na tela de **Nova Conta a Pagar** (para tenants V2), com botão "Lançar via Gestão de Custos".

1. Selecionar categoria: **Despesa Geral / Avulsa**
2. Preencher **Fornecedor / Credor** (ex: "Imobiliária Central", "Copel Distribuição")
3. Preencher **Data de Vencimento** — aparecerá como Saída Prevista no Fluxo de Caixa no mês correto
4. Preencher **Nº Documento** (número da NF, boleto ou contrato — opcional)
5. Preencher **Descrição** (ex: "Aluguel maio/2026")
6. Preencher **Valor (R$)**
7. Preencher **Data de Referência** (mês de competência)
8. Vincular à obra (opcional)
9. Clicar em **Salvar Lançamento**

**O que acontece:**
- Custo criado com status **PENDENTE** (não aparece no Fluxo de Caixa ainda)
- Após **Solicitar**: aparece nas Saídas Previstas do Fluxo de Caixa, na data de vencimento informada
- Após **Autorizar**: permanece nas Saídas Previstas
- Após **Pagar**: sai das Saídas Previstas, vai para histórico do Fluxo de Caixa

#### Exemplos de uso

| Despesa | Fornecedor/Credor | Categoria |
|---|---|---|
| Aluguel do escritório | Imobiliária / Locador | Despesa Geral |
| Conta de energia | CEMIG / Copel | Despesa Geral |
| IPTU | Prefeitura | Despesa Geral |
| Honorários contábeis | Escritório Contábil X | Despesa Geral |
| Assinatura de software | SaaS Provider | Despesa Geral |
| Manutenção de impressora | Técnico / Empresa | Despesa Geral |

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
| **Material (Saída)** | Almoxarifado → Cadastrar Item → Entrada → Saída de Material | Custo da Obra (direto) | Não | Não aparece (só em Custos por Obra) |
| **Diária Funcionário** | **Ponto Eletrônico** (dispositivo compartilhado) → bater ponto (entrada) | Gestão de Custos PENDENTE | Sim (Solicitar → Autorizar → Pagar) | Quando SOLICITADO ou AUTORIZADO |
| **Reembolso** | Financeiro → Gestão de Custos → Reembolsos | Gestão de Custos PENDENTE | Sim | Quando SOLICITADO ou AUTORIZADO |
| **Despesa Geral (V2)** | Gestão de Custos → Novo → categoria Despesa Geral | Gestão de Custos PENDENTE | Sim | Quando SOLICITADO ou AUTORIZADO (pela data de vencimento) |
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
