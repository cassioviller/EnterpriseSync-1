# Alimentação

O módulo **Alimentação** (`/alimentacao/`) centraliza **lançamentos de refeições** dos funcionários em obra, com **rateio por funcionário** e **integração com o financeiro** (cada lançamento dispara um evento que cria a despesa correspondente).

## Para que serve

- Cadastrar **restaurantes** e **itens de cardápio** (almoço, marmita, café, lanche…).
- Lançar consumo do dia: **restaurante**, **obra**, **lista de funcionários** e **valor total** (V1) ou **múltiplos itens com preço, quantidade, funcionário e centro de custo** (V2).
- Emitir um **evento** (`alimentacao_lancamento_criado`) que dispara contas a pagar e gera relatório.
- Filtrar lançamentos por **período** e **restaurante**.

## Como acessar

- **Menu superior → "Alimentação"** (dropdown):
  - `/alimentacao/dashboard` — Dashboard (KPIs e gráficos).
  - `/alimentacao` — Tela inicial.
  - `/alimentacao/lancamentos/novo-v2` — Novo lançamento (V2, recomendado).
  - `/alimentacao/lancamentos/novo` — Novo lançamento (V1, legado).
  - `/alimentacao/lancamentos` — Lista de lançamentos.
  - `/alimentacao/restaurantes` — CRUD de restaurantes.
  - `/alimentacao/itens` — CRUD de itens.
- Drawer mobile: **"Alimentação"** leva direto a `/alimentacao`.

## Fluxos principais

### 1. Cadastrar restaurante

1. **Menu → Alimentação → Restaurantes → "+ Novo"** (`/alimentacao/restaurantes/novo`).
2. Preencha **Nome**, **CNPJ**, **Telefone**, **Endereço** e marque como **ativo**.
3. Salve — o restaurante aparece nos selects de lançamento.

### 2. Cadastrar itens de cardápio

1. **Menu → Alimentação → Itens → "+ Novo Item"** (`/alimentacao/itens/novo`).
2. Preencha **Nome** (ex.: "Almoço executivo"), **Preço padrão**, **Ícone** Font Awesome (ex.: `fas fa-utensils`) e **Ordem** de exibição.
3. Salve — o item passa a aparecer no formulário V2 com botão de seleção rápida.

### 3. Novo lançamento V2 (recomendado)

1. **Menu → Alimentação → "+ Novo Lançamento"** (`/alimentacao/lancamentos/novo-v2`).
2. Selecione a **Obra** e o **Restaurante**.
3. Para cada item consumido, clique no botão do item (preenche nome e preço padrão) ou em **"Item personalizado"** (digite nome e preço).
4. Em V2 (feature flag ativa), informe por **linha**: **Quantidade**, **Funcionário** (opcional) e **Centro de Custo** (opcional).
5. Em V1, selecione os funcionários no bloco superior — eles serão **rateados igualmente** entre todos os itens.
6. Submeta — o sistema valida tenant em **obra**, **restaurante**, **funcionários** e **centros de custo**, cria o lançamento e emite o evento `alimentacao_lancamento_criado`.

### 4. Novo lançamento V1 (legado)

1. **Menu → Alimentação → "Lançamento Simples"** (`/alimentacao/lancamentos/novo`).
2. Preencha **Data**, **Restaurante**, **Obra**, **Valor total** e a **lista de funcionários**.
3. O sistema rateia o valor pelos funcionários selecionados e grava na tabela `alimentacao_funcionarios_assoc`.
4. O evento `alimentacao_lancamento_criado` também é emitido para integrar com o financeiro.

### 5. Listar e filtrar lançamentos

1. **Menu → Alimentação → Lançamentos** (`/alimentacao/lancamentos`).
2. Filtros: **período**, **restaurante**, **obra**.
3. A lista exibe **data**, **restaurante**, **obra**, **valor total** e **funcionários**. Clique para ver o detalhe ou editar.

### 6. Dashboard

1. **Menu → Alimentação → Dashboard** (`/alimentacao/dashboard`) — KPIs (gasto total do mês, restaurante mais usado, top funcionários) e gráficos.
2. **Atenção:** durante o smoke test, esta rota respondeu **302** (redirect) — verifique se o redirect leva à tela esperada antes de divulgar internamente.

## Dicas e cuidados

- O **V2 é o caminho recomendado**: permite lançar várias refeições em um único registro, com responsabilização individual por funcionário e centro de custo.
- O **V1 (legado)** é mantido por compatibilidade — evite cadastrar processos em cima dele.
- Toda alteração dispara o evento de integração; **excluir um lançamento V1/V2 também precisa cancelar o lançamento financeiro associado** — verifique antes de excluir.
- Itens com `is_default=True` não devem ser apagados (são preenchidos pelo seeder em demos).
- **Validação multi-tenant é estrita** em `lancamento_novo_v2` (obra, restaurante, funcionários, centros de custo). Se a tela mostrar "Inválido ou sem permissão" o log aplica WARN com `admin_id` — útil para suporte.
- O CSV `is_default` no item é só visual (ícone + ordem); o **preço padrão** preenche o valor unitário ao clicar no item, mas pode ser editado linha a linha em V2.
