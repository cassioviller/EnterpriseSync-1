# Manual do Usuário — Almoxarifado SIGE v9.0

---

## Visão Geral

O módulo de Almoxarifado do SIGE controla o estoque de materiais, ferramentas e EPIs usados nas obras. O sistema reconhece o custo do material **uma única vez**, no momento da compra — a saída para obra é apenas controle físico, sem gerar nova despesa.

**Princípio central:**
> Compra (vinculada à obra) → lançamento automático na Gestão de Custos → estoque atualizado.
> Saída → controle físico para rastreamento por funcionário. Nenhum custo duplicado.

---

## Perfis de Acesso

| Perfil | O que pode fazer |
|--------|-----------------|
| ADMIN V2 | Tudo: cadastros, compras, entradas, saídas, relatórios, gestão de custos |
| Funcionário | Ver estoque próprio, solicitar materiais (se configurado) |

---

## 1. Cadastro de Itens (Catálogo)

**Caminho:** Almoxarifado → Itens → Novo Item

Cada item do catálogo representa um tipo de material ou ferramenta. Campos obrigatórios:

| Campo | Descrição |
|-------|-----------|
| Nome | Ex: "Cimento CP-II 50kg", "Capacete Obra" |
| Código | Código interno único (ex: MAT-001) |
| Tipo de Controle | **CONSUMÍVEL** (cimento, tinta) ou **SERIALIZADO** (ferramenta com nº série) |
| Unidade | kg, m², un, L, sc, m³ |
| Estoque Mínimo | Alerta quando abaixo deste valor |
| Categoria | Organiza os itens (Ferramentas, EPIs, Materiais, etc.) |

**Dica:** Use o campo "Código de Barras" (EAN-13) se quiser usar o scanner móvel.

---

## 2. Compra de Materiais (Pedido de Compra)

**Caminho:** Compras → Nova Compra

Esta é a entrada principal de custo. Ao salvar uma compra:
- O sistema cria automaticamente o **lançamento na Gestão de Custos** (categoria: Material de Obra), identificado pelo nome da obra
- O estoque é **atualizado automaticamente** para itens vinculados ao catálogo
- Nenhuma duplicação de custo ocorre em etapas posteriores

### Passo a Passo — Nova Compra

1. Selecione o **Fornecedor**
2. Informe o **Nº da NF / Recibo** (opcional)
3. Informe a **Data da Compra**
4. Selecione a **Obra** — campo obrigatório; ela define o centro de custo do material
5. Escolha a **Condição de Pagamento** (À Vista, 30/60/90 dias, parcelado)
6. Adicione os **Itens da Compra**:
   - Para cada item, use o campo "Catálogo" para ligar ao item do almoxarifado
   - Itens vinculados entram automaticamente no estoque ao salvar
7. Clique em **Registrar Compra**

> **Por que a Obra é obrigatória?**
> A obra é o centro de custo do material. Toda compra precisa estar associada a uma obra para que os custos apareçam corretamente na Gestão de Custos e nos relatórios por obra.

### O que acontece automaticamente:

```
Compra Salva (Obra X + Fornecedor Y)
├── Lançamento "Material de Obra" criado na Gestão de Custos
│   ├── Entidade principal: Obra X
│   └── Fornecedor registrado: Fornecedor Y (aparece como subtítulo)
├── Se pagamento À Vista → status PAGO
├── Se prazo/boleto → status PENDENTE (entra no fluxo de aprovação)
└── Para cada item vinculado ao catálogo:
    ├── Entrada no almoxarifado registrada
    └── Estoque (lote FIFO) atualizado
```

### Verificar Recebimento

Na tela de **Detalhe da Compra**, você vê o status de cada item:

| Status | Significado |
|--------|-------------|
| Recebido | Item já está no estoque |
| Pendente | Item vinculado ainda não deu entrada física (use "Registrar Recebimento") |
| Sem vínculo | Item não tem catálogo vinculado (controle externo ao almoxarifado) |

**Botão "Registrar Recebimento"** — aparece quando há itens vinculados com entrada pendente. Cada item é processado uma única vez.

---

## 3. Saída de Materiais

**Caminho:** Almoxarifado → Saída de Materiais

A saída registra **quem retirou** e **qual material** foi utilizado. Nenhum custo novo é gerado — o custo já foi reconhecido na compra.

### Passo a Passo — Saída

1. Selecione o **Funcionário** responsável pelo recebimento
2. Selecione a **Obra** destino (opcional, recomendado para rastreabilidade)
3. Selecione o **Item** do catálogo
4. Para **Consumíveis**: informe a quantidade; o sistema mostra os lotes disponíveis (FIFO)
   - Você pode escolher o lote manualmente ou usar o FIFO automático
5. Para **Serializados**: marque os números de série individuais para saída
6. Clique em **Processar Saída**

### Lotes (FIFO — First In, First Out)

O sistema prioriza os lotes mais antigos automaticamente. Se quiser escolher um lote específico (ex: usar o lote de uma NF específica), desmarque os outros e selecione apenas o desejado.

### Saída Múltipla (Carrinho)

Para retirar vários itens de uma vez, use o modo **Saída Múltipla**:
1. Adicione itens ao carrinho um por um
2. Revise a lista completa
3. Clique em "Processar Todos"

---

## 4. Gestão de Custos — Visualizando Materiais por Obra

**Caminho:** Gestão de Custos (menu lateral)

Aqui ficam todos os lançamentos financeiros, incluindo as compras de material. Cada compra aparece com a **obra como identificador principal** e o fornecedor como informação secundária.

### Como cada linha aparece na lista

```
Categoria          Entidade
─────────────────────────────────────────────
Material de Obra   Obra Comercial Bloco A        ← nome da obra (principal)
                   🚚 Fornecedor Silva Materiais  ← fornecedor (subtítulo)
```

### Filtros disponíveis

| Filtro | Como usar |
|--------|-----------|
| **Busca** | Digite o nome da obra ou qualquer texto |
| **Status** | Pendente, Solicitado, Pago, Parcial |
| **Categoria** | Selecione "Material de Obra" para ver só compras |
| **Obra** | Dropdown para filtrar por uma obra específica |

### Como ver todos os materiais de uma obra

1. Acesse **Gestão de Custos**
2. No dropdown **"Todas as obras"**, selecione a obra desejada
3. Opcionalmente, no dropdown **"Todas as categorias"**, selecione **"Material de Obra"**
4. Clique em **Filtrar**

Você verá todas as compras de material associadas àquela obra, com o valor, status e fornecedor de cada uma.

### Fluxo de Aprovação de Pagamento

Para compras com prazo (boleto, parcelado):

```
PENDENTE → [Solicitar] → SOLICITADO → [Aprovar] → PAGO
```

1. **Solicitar**: clique no ícone de avião e informe o valor a solicitar
2. **Aprovar**: clique no ícone de confirmação, informe a data e banco
3. O sistema atualiza o saldo automaticamente

---

## 5. Estoque e Inventário

**Caminho:** Almoxarifado → Itens

### Indicadores por Item

| Cor/Ícone | Significado |
|-----------|-------------|
| Verde | Estoque acima do mínimo |
| Amarelo | Estoque abaixo do mínimo (alerta) |
| Vermelho | Estoque zerado |

Clique em um item para ver:
- Posição atual do estoque por lote
- Histórico de entradas e saídas
- Qual funcionário/obra recebeu o material

---

## 6. Relatórios

**Caminho:** Almoxarifado → Relatórios

| Relatório | O que mostra |
|-----------|-------------|
| Posição de Estoque | Quantidade disponível de cada item |
| Movimentações | Todas as entradas e saídas num período |
| Itens por Funcionário | Materiais retirados por pessoa |
| Consumo por Obra | Quanto cada obra consumiu de cada material |
| Alertas de Estoque | Itens abaixo do mínimo |

Para gerar: selecione o relatório, ajuste os filtros e clique em **Gerar Relatório**.

---

## 7. Importação de XML (NF-e)

**Caminho:** Almoxarifado → Importar XML

Permite importar a NF-e eletrônica do fornecedor:
1. Faça upload do arquivo `.xml` da NF-e
2. O sistema lê os itens automaticamente
3. Vincule cada produto ao catálogo interno
4. Confirme para dar entrada no estoque

---

## 8. Scanner de Código de Barras

**Caminho:** Almoxarifado → Scanner (acesso móvel)

Ideal para o celular na obra. Permita a câmera e aponte para o código de barras do item para:
- Consultar estoque rápido
- Registrar saída diretamente

---

## Fluxo Resumido (Visão Gestor)

```
1. CADASTRAR itens no catálogo (uma vez por item)
      ↓
2. COMPRAR materiais — informar obra e fornecedor
   (gera custo na Gestão de Custos + entrada no estoque)
      ↓
3. EMITIR materiais para funcionário/obra (saída física)
      ↓
4. ACOMPANHAR custos em Gestão de Custos
   (filtre por obra para ver todos os materiais dela)
      ↓
5. APROVAR pagamentos (para compras com prazo)
      ↓
6. GERAR relatórios de consumo por obra
```

---

## Perguntas Frequentes

**P: A obra é obrigatória na compra?**
R: Sim. A obra define o centro de custo do material e faz o lançamento aparecer corretamente na Gestão de Custos. Sem ela não é possível rastrear quanto cada obra gastou em material.

**P: Preciso registrar a entrada manualmente quando faço uma compra?**
R: Não. Ao salvar a compra com itens vinculados ao catálogo, a entrada no estoque é automática.

**P: O custo aparece duplicado se eu fizer a saída depois?**
R: Não. O custo é reconhecido apenas na compra. A saída é só rastreamento físico de quem usou o material.

**P: Posso comprar sem vincular itens ao catálogo?**
R: Sim. Itens sem vínculo ficam como "Sem vínculo" na tela de detalhe da compra. O custo é registrado normalmente na Gestão de Custos, mas o estoque não é controlado automaticamente.

**P: Como encontro todas as compras de uma obra específica?**
R: Acesse Gestão de Custos, use o filtro "Todas as obras" e selecione a obra desejada. Você verá todos os lançamentos de Material de Obra com o nome da obra em destaque em cada linha.

**P: O que é FIFO?**
R: Primeiro que entra, primeiro que sai. O sistema sempre usa o lote mais antigo primeiro nas saídas. Garante que materiais mais velhos sejam usados antes de vencer.

**P: Como saber quais materiais estão em falta?**
R: Acesse Almoxarifado → Relatórios → Alertas de Estoque. Também aparecem alertas no dashboard principal.

---

*SIGE v9.0 — Sistema de Gestão Empresarial*
*Módulo Almoxarifado — Versão 2.0 — Multi-tenant*
