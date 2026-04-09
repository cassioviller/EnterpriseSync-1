# Manual do Módulo Financeiro — SIGE v9.0

> Cobre todo o ciclo financeiro: lançamentos automáticos dos módulos operacionais → Gestão de Custos → aprovação → Fluxo de Caixa.

---

## Visão Geral do Fluxo

```
Módulos Operacionais          Gestão de Custos V2           Fluxo de Caixa
─────────────────────         ───────────────────           ──────────────
Transporte      ──────┐
Alimentação     ──────┤──→  PENDENTE → SOLICITADO  ──→  Saídas Previstas
Diária (Ponto)  ──────┘              → PAGO        ──→  Histórico (FluxoCaixa)

Material (Almox) ─────────────────────────────────→  Gestão de Custos (via Compra)

Conta a Receber (manual) ─────────────────────────→  Entradas Previstas
```

---

## PARTE A — Lançamentos Automáticos pelos Módulos

---

### A1. Transporte → Gestão de Custos

Todo lançamento de transporte cria automaticamente um custo na **Gestão de Custos V2** com categoria **TRANSPORTE** (Custo Indireto de Obra).

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

Cada lançamento de alimentação cria automaticamente um custo na **Gestão de Custos V2** com categoria **ALIMENTACAO** (Custo Indireto de Obra).

**Caminho:** Menu superior → **Alimentação** → botão **Novo Lançamento**

**Preencha:**
- **Obra** (obrigatório)
- Restaurante / Fornecedor (opcional em V2 — pode ser deixado em branco)
- Itens consumidos com preços
- Data e valores

Clique em **Confirmar** / **Salvar Lançamento**.

**O que acontece automaticamente:**
- Lançamento de alimentação registrado
- Custo criado na **Gestão de Custos V2** com status **PENDENTE**, vinculado à obra

---

### A3. Material (Almoxarifado) → Custo da Obra via Compra

O custo do material é reconhecido **no momento da compra**, quando a compra é registrada no módulo **Compras/Almoxarifado → Nova Compra → Registrar Compra**. A compra cria automaticamente um lançamento na **Gestão de Custos V2** com categoria **Material de Obra**, vinculado à obra informada na compra.

> **Atenção:** A saída de material do estoque é apenas rastreamento físico — registra quem retirou e qual material foi usado. A saída **não gera novo lançamento financeiro** e não duplica o custo.

#### Fluxograma

```
COMPRA (Compras → Nova Compra → Registrar Compra)
  ├── Obra + Fornecedor informados
  ├── Lançamento "Material de Obra" criado na Gestão de Custos  ← custo reconhecido aqui
  │   ├── Se À Vista → status PAGO
  │   └── Se prazo/boleto → status PENDENTE (entra no fluxo de aprovação)
  └── Para cada item vinculado ao catálogo:
        └── Estoque (lote FIFO) atualizado automaticamente

SAÍDA DE MATERIAL (Almoxarifado → Saída de Materiais)
  ├── Estoque do item diminui
  └── Rastreamento físico: funcionário, obra e lote registrados
      (nenhum custo novo é gerado)
```

#### Registrar a Compra

**Caminho:** Menu → **Compras** → **Nova Compra**

**Preencha:**
- Fornecedor
- Nº da NF / Recibo (opcional)
- Data da Compra
- **Obra** (obrigatório — define o centro de custo)
- Condição de Pagamento (À Vista, 30/60/90 dias, parcelado)
- Itens da compra (vinculados ao catálogo do almoxarifado)

Clique em **Registrar Compra**.

#### Realizar a Saída (rastreamento físico)

**Caminho:** Menu → **Almoxarifado** → **Saída de Materiais**

**Preencha:**
- Funcionário responsável pelo recebimento
- Obra destino (opcional, recomendado para rastreabilidade)
- Item do catálogo e quantidade

Clique em **Processar Saída**.

**O que acontece:**
- Estoque do item diminui
- Rastreamento físico registrado (funcionário, obra, lote)
- **Nenhum novo lançamento financeiro é criado**

> **Para acompanhar o gasto de materiais:** use a **Gestão de Custos** (filtrando por obra e categoria "Material de Obra") ou o relatório de Custos por Obra.

---

### A4. Diária de Funcionário → Gestão de Custos

Para funcionários com tipo de remuneração **Diária**, o ato de **bater o ponto pelo dispositivo compartilhado** gera automaticamente um custo na Gestão de Custos V2.

> **Importante:** O custo de diária só é criado quando o ponto é registrado pelo **Ponto Eletrônico** (dispositivo compartilhado ou reconhecimento facial). O registro manual feito pelo administrador no perfil do funcionário **não gera o custo automático**.

#### Pré-requisito: configurar o funcionário como diarista

**Caminho:** Menu → **Funcionários** → clicar no nome do funcionário para abrir o perfil → botão **Editar**
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
  - Categoria: **MAO_OBRA_DIRETA** (Mão de Obra Direta)
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

### A5. Despesas Operacionais / Avulsas → Gestão de Custos

Para despesas que não têm módulo próprio no SIGE — **aluguel de escritório, energia elétrica, água, IPTU, honorários contábeis, assinaturas de software, manutenção de equipamentos** — use a **Gestão de Custos V2** com a categoria adequada. Assim a despesa passa pelo fluxo de aprovação antes de ser paga.

#### Categorias disponíveis para despesas avulsas

As categorias são organizadas em três grupos contábeis (padrão SINAPI/NBC TG):

**Custo Direto de Obra**
| Categoria | Quando usar |
|---|---|
| Material de Obra (MATERIAL) | Compra de insumos para obra sem passar pelo Almoxarifado |
| Mão de Obra Direta (MAO_OBRA_DIRETA) | Pagamento de empreiteiros, operários avulsos |
| Equipamento / Frota (EQUIPAMENTO) | Aluguel ou manutenção de máquinas de obra |
| Subempreitada (SUBEMPREITADA) | Contratos de subempreitada |

**Custo Indireto de Obra**
| Categoria | Quando usar |
|---|---|
| Alimentação (ALIMENTACAO) | Refeições em obra (quando não lançado via módulo Alimentação) |
| Transporte (TRANSPORTE) | Deslocamento para obra (quando não lançado via módulo Transporte) |
| Canteiro / Instalações (CANTEIRO) | Barracão, container, sanitário de obra |
| Taxas e Licenças (TAXAS_LICENCAS) | Anotações de responsabilidade técnica, alvarás, ISS de obra |

**Despesa Administrativa**
| Categoria | Quando usar |
|---|---|
| Salário Administrativo (SALARIO_ADMIN) | Pagamento de pessoal de escritório |
| Aluguel / Utilities (ALUGUEL_UTILITIES) | Aluguel de escritório, energia, água, internet |
| Tributos / Impostos (TRIBUTOS) | IPTU, IRPJ, CSLL, contribuições federais |
| Despesa Financeira (DESPESA_FINANCEIRA) | Juros, tarifas bancárias, IOF |
| Outros (OUTROS) | Qualquer despesa que não se enquadre acima |

#### Passo a passo

**Caminho:** Menu → **Gestão de Custos** → botão **Novo Lançamento**

1. Selecionar o **Grupo de categoria** e a **Categoria** correta (ex: Despesa Administrativa → Aluguel / Utilities)
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
- Após **Aprovar**: status muda para PAGO; sai das Saídas Previstas, vai para histórico do Fluxo de Caixa

#### Exemplos de uso

| Despesa | Fornecedor/Credor | Categoria recomendada |
|---|---|---|
| Aluguel do escritório | Imobiliária / Locador | Aluguel / Utilities (ALUGUEL_UTILITIES) |
| Conta de energia | CEMIG / Copel | Aluguel / Utilities (ALUGUEL_UTILITIES) |
| IPTU | Prefeitura | Tributos / Impostos (TRIBUTOS) |
| Honorários contábeis | Escritório Contábil X | Outros (OUTROS) |
| Assinatura de software | SaaS Provider | Outros (OUTROS) |
| Aluguel de betoneira | Empresa de Equipamentos | Equipamento / Frota (EQUIPAMENTO) |
| ISS de obra | Prefeitura | Taxas e Licenças (TAXAS_LICENCAS) |

---

## PARTE B — Aprovação na Gestão de Custos V2

Todos os custos criados por Transporte, Alimentação e Diária chegam aqui com status **PENDENTE**.

**Caminho:** Financeiro → **Gestão de Custos** (ou menu lateral)

A lista mostra todos os custos agrupados por entidade (funcionário, restaurante, veículo), com badges coloridos indicando o status:

| Badge | Status | Significado |
|---|---|---|
| Cinza | PENDENTE | Criado, aguardando solicitação |
| Amarelo | SOLICITADO | Solicitado ao aprovador, aparece no Fluxo de Caixa |
| Azul | PAGO | Pago, registrado no histórico de FluxoCaixa |

---

### Passo 1 — Solicitar (PENDENTE → SOLICITADO)

**Caminho:** Gestão de Custos → localizar o registro → botão **Solicitar**

- Clique no botão **Solicitar** (ícone de seta / enviar)
- Confirme na caixa de diálogo se aparecer
- Status muda de PENDENTE para **SOLICITADO**

**Efeito no Fluxo de Caixa:** o custo aparece imediatamente em **Saídas Previstas**

---

### Passo 2 — Aprovar ou Recusar (SOLICITADO → PAGO ou PENDENTE)

**Caminho:** Gestão de Custos → localizar o registro SOLICITADO → botão **Aprovar** ou **Recusar**

- **Aprovar** → um formulário aparece; preencha:
  - **Data do Pagamento** (preenche com hoje automaticamente)
  - **Conta Bancária** (texto livre — ex: "BB Conta Corrente 1234-5", "Caixa Física")
  - **Valor Pago** (preenche automaticamente com o valor solicitado)
  - Clique em **Confirmar Pagamento**
  - Status muda para **PAGO**; custo sai das Saídas Previstas e vai para o histórico de FluxoCaixa
- **Recusar** → status volta para **PENDENTE**; sai do Fluxo de Caixa

**O que acontece automaticamente ao Aprovar:**
- Status muda para **PAGO**
- Custo **sai da tabela de Movimentos Previstos** do Fluxo de Caixa
- Um registro de **FluxoCaixa** histórico é criado (tipo SAIDA)
- Se a obra tiver contabilidade configurada → **lançamento contábil criado** automaticamente

> **Confirmado em teste:** após APROVAR, a linha some imediatamente de "Movimentos Previstos" no Fluxo de Caixa.

---

## PARTE C — Resultado no Fluxo de Caixa

**Caminho:** Financeiro → **Fluxo de Caixa**

Use os filtros de **Data Início** e **Data Fim** para o período que deseja analisar.

### O que cada card mostra

| Card | Cor | O que inclui |
|---|---|---|
| Saldo Inicial | Azul | Soma do saldo atual de todos os bancos cadastrados |
| Entradas Previstas | Verde | Contas a Receber com status PENDENTE ou PARCIAL no período |
| Saídas Previstas | Vermelho | Gestão de Custos SOLICITADO no período |
| Saldo Final Projetado | Azul/Amarelo | Saldo Inicial + Entradas − Saídas |

### Tabela de Movimentos Previstos

Cada linha da tabela representa um lançamento individual:

| Cor da linha | Tipo | Origem |
|---|---|---|
| Verde | ENTRADA | Conta a Receber pendente |
| Vermelho | SAÍDA | Gestão de Custos (qualquer categoria) SOLICITADO |

> **Gestão de Custos com Data de Vencimento:** quando o lançamento tem data de vencimento preenchida (ex: Aluguel, Energia), ele aparece no período que inclui essa data — não a data de criação. Isso garante que a projeção de caixa esteja no mês correto.

---

## PARTE D — Fluxo Manual (sem módulos operacionais)

Para entradas financeiras que não passam pelos módulos operacionais, use o lançamento direto:

### Conta a Receber (manual)
**Caminho:** Financeiro → Contas a Receber → **Nova Conta a Receber**
- Preencha: Descrição, Cliente, Valor, Vencimento, Obra (opcional)
- Aparece imediatamente em Entradas Previstas

### Dar baixa (receber)
**Caminho:** na lista → botão **Receber** → preencher valor, data, forma e banco → confirmar

---

## PARTE E — Tabela Resumo por Módulo

| Módulo | Como lançar | Vai para | Aprovação necessária | Aparece no Fluxo de Caixa |
|---|---|---|---|---|
| **Transporte** | Menu Transporte → Novo Lançamento | Gestão de Custos PENDENTE (cat: TRANSPORTE) | Sim (Solicitar → Aprovar) | Quando SOLICITADO |
| **Transporte Lote** | Menu Transporte → Lançamento em Lote | Gestão de Custos PENDENTE (cat: TRANSPORTE) | Sim | Quando SOLICITADO |
| **Alimentação** | Menu Alimentação → Novo Lançamento | Gestão de Custos PENDENTE (cat: ALIMENTACAO) | Sim (Solicitar → Aprovar) | Quando SOLICITADO |
| **Material (Compra)** | Compras → Nova Compra → Registrar Compra | Gestão de Custos (cat: Material de Obra) | Sim (para compras a prazo) | Quando SOLICITADO |
| **Diária Funcionário** | **Ponto Eletrônico** (dispositivo compartilhado) → bater ponto (entrada) | Gestão de Custos PENDENTE (cat: MAO_OBRA_DIRETA) | Sim (Solicitar → Aprovar) | Quando SOLICITADO |
| **Reembolso** | Financeiro → Gestão de Custos → Reembolsos | Gestão de Custos PENDENTE (cat: OUTROS) | Sim | Quando SOLICITADO |
| **Despesa Avulsa (V2)** | Gestão de Custos → Novo → categoria adequada | Gestão de Custos PENDENTE | Sim | Quando SOLICITADO (pela data de vencimento) |
| **Conta a Receber** | Financeiro → Contas a Receber → Nova | Entradas Previstas (direto) | Não | Imediatamente (status PENDENTE) |

---

## PARTE F — Hierarquia de Categorias (Gestão de Custos V2)

As categorias seguem o padrão contábil da construção civil (SINAPI / NBC TG 47):

### Custo Direto de Obra
| Categoria | Código | Descrição |
|---|---|---|
| Material de Obra | MATERIAL | Insumos físicos incorporados à obra |
| Mão de Obra Direta | MAO_OBRA_DIRETA | Operários, pedreiros, eletricistas, diaristas |
| Equipamento / Frota | EQUIPAMENTO | Máquinas, veículos de obra, ferramentas caras |
| Subempreitada | SUBEMPREITADA | Contratos de terceiros para serviços de obra |

### Custo Indireto de Obra
| Categoria | Código | Descrição |
|---|---|---|
| Alimentação | ALIMENTACAO | Refeições, marmitas, restaurante |
| Transporte | TRANSPORTE | Vale-transporte, táxi, combustível de obra |
| Canteiro / Instalações | CANTEIRO | Barracão, container, aluguel de sanitário |
| Taxas e Licenças | TAXAS_LICENCAS | Alvarás, ART/RRT, ISS de obra |

### Despesa Administrativa
| Categoria | Código | Descrição |
|---|---|---|
| Salário Administrativo | SALARIO_ADMIN | Pessoal de escritório, gestores |
| Aluguel / Utilities | ALUGUEL_UTILITIES | Aluguel de imóvel, energia, água, internet |
| Tributos / Impostos | TRIBUTOS | IPTU, IRPJ, CSLL, contribuições |
| Despesa Financeira | DESPESA_FINANCEIRA | Juros, tarifas bancárias, IOF |
| Outros | OUTROS | Demais despesas administrativas |

> **Retrocompatibilidade:** registros criados antes da Task #8 com categorias legadas (COMPRA, VEICULO, SALARIO, REEMBOLSO, DESPESA_GERAL) foram migrados automaticamente. Caso algum registro legado apareça, ele será exibido normalmente com um badge "(legado)".

---

## PARTE G — Dicas Práticas

- **O custo de material (almoxarifado) é reconhecido na compra.** Ele é registrado na Gestão de Custos quando a compra é salva, vinculado à obra. Para ver: Gestão de Custos → filtrar por obra e categoria "Material de Obra".
- **A saída de material não gera custo.** É apenas rastreamento físico de quem retirou o material.
- **Sem Solicitar, o custo não aparece no Fluxo de Caixa.** Um lançamento de Transporte ou Alimentação recém-criado fica invisível no Fluxo até ser Solicitado.
- **Recusar não apaga o custo.** Ele volta para PENDENTE e pode ser Solicitado novamente depois de corrigido.
- **O Saldo Inicial do Fluxo de Caixa é o saldo real dos bancos.** Mantenha os bancos atualizados dando baixa correta nas contas (selecionando o banco ao pagar).
- **Pagamento parcial:** informe só o valor pago hoje; o saldo restante continua nas Saídas Previstas.
- **Diária duplicada:** o sistema protege automaticamente — bater o ponto duas vezes no mesmo dia não gera dois custos.
- **Data de vencimento importa:** ao lançar despesas com data de vencimento (aluguel, energia, IPTU), preencha o campo para que o Fluxo de Caixa projete a saída no mês correto.
- **Escolha a categoria correta:** use a hierarquia contábil para classificar corretamente. Isso impacta relatórios de Custo da Obra vs. Despesa Administrativa.
