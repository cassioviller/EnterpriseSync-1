# Estoque / Almoxarifado

O **Almoxarifado** (`/almoxarifado/`) controla o **estoque físico** (entrada, saída, devolução, movimentações) com suporte a **dois tipos de controle**: **CONSUMÍVEL** (granel, por quantidade e lote FIFO) e **SERIALIZADO** (por número de série / patrimônio). Tem KPIs no dashboard, alertas de **estoque baixo**, **vencimento** e **manutenção**, e relatórios.

## Para que serve

- Cadastrar **itens** (com categoria, unidade, estoque mínimo, tipo de controle).
- Registrar **entrada** (com nota fiscal, valor unitário, lote, validade ou número de série).
- Registrar **saída** para funcionário/obra (com seleção de lote FIFO ou item serializado).
- Registrar **devolução** ao estoque.
- Acompanhar **movimentações**, **fornecedores** e gerar **relatórios**.

## Como acessar

- **Menu superior → "Almoxarifado"** (dropdown):
  - `/almoxarifado/` — Dashboard.
  - `/almoxarifado/itens` — Itens.
  - `/almoxarifado/categorias` — Categorias.
  - `/almoxarifado/entrada`, `/saida`, `/devolucao`.
  - `/almoxarifado/movimentacoes` — Histórico.
  - `/almoxarifado/relatorios` — Relatórios.
  - `/almoxarifado/fornecedores`.

## Fluxos principais

### 1. Cadastrar item

1. **Menu → Almoxarifado → Itens → "+ Novo Item"** (`/almoxarifado/itens/criar`).
2. Preencha **Código**, **Nome**, **Categoria**, **Unidade**, **Estoque mínimo** e o **Tipo de Controle**:
   - **CONSUMÍVEL**: contagem por quantidade e por lote (FIFO).
   - **SERIALIZADO**: cada unidade tem **número de série** próprio.
3. Salve — o item aparece em `/almoxarifado/itens` para receber entradas.

### 2. Lançar entrada de material

1. **Menu → Almoxarifado → Entrada** (`/almoxarifado/entrada`).
2. Selecione o **item** (a tela faz `GET /almoxarifado/api/item/<id>` para obter `tipo_controle`, `unidade` e estoque atual).
3. Preencha **Nota Fiscal**, **Fornecedor**, **Valor unitário**, **Data**, **Quantidade** (CONSUMÍVEL) ou **lista de números de série** (SERIALIZADO).
4. Para CONSUMÍVEL, informe **lote** e, se aplicável, **data de validade**.
5. Submeta para `POST /almoxarifado/processar-entrada` — o sistema cria registros em `AlmoxarifadoEstoque` com `status='DISPONIVEL'` e um `AlmoxarifadoMovimento` de entrada.

### 3. Lançar saída

1. **Menu → Almoxarifado → Saída** (`/almoxarifado/saida`).
2. Escolha **funcionário** e **obra** que receberão o material.
3. Selecione o **item**:
   - **CONSUMÍVEL**: a tela chama `GET /almoxarifado/api/lotes-disponiveis/<id>` para listar lotes ordenados por **FIFO** (entrada mais antiga primeiro). Escolha o lote (ou aceite a sugestão FIFO) e informe a quantidade.
   - **SERIALIZADO**: a tela chama `GET /almoxarifado/api/estoque-disponivel/<id>` e exibe os números de série em estoque. Marque os que serão entregues.
4. Submeta para `POST /almoxarifado/processar-saida` — o sistema baixa as quantidades e marca os serializados como `EM_USO`.

### 4. Lançar devolução

1. **Menu → Almoxarifado → Devolução** (`/almoxarifado/devolucao`).
2. Selecione o **funcionário** e o **item devolvido**.
3. Para CONSUMÍVEL, informe a **quantidade**; para SERIALIZADO, marque os números de série retornados.
4. O status do estoque volta para `DISPONIVEL` e um movimento de devolução é registrado.

### 5. Acompanhar movimentações

1. **Menu → Almoxarifado → Movimentações** (`/almoxarifado/movimentacoes`).
2. A tela lista as últimas movimentações com **tipo** (entrada/saída/devolução/ajuste), **item**, **quantidade**, **funcionário**, **obra** e **nota fiscal**.
3. Em `/almoxarifado/itens/<id>/movimentacoes` é possível filtrar pelo histórico de **um item** específico.

### 6. Dashboard de KPIs

1. `/almoxarifado/` exibe:
   - **Total de itens cadastrados**.
   - **Estoque baixo** (itens onde `estoque_atual < estoque_minimo`).
   - **Movimentações de hoje**.
   - **Valor total em estoque** (`Σ quantidade × valor_unitario`).
   - **Alertas**: itens vencendo nos próximos 30 dias, itens em manutenção.
   - **Últimas 10 movimentações**.

## Dicas e cuidados

- A **lógica FIFO** baseia-se em `created_at` do lote; nunca edite manualmente esse campo no banco para "pular" lotes.
- **Item SERIALIZADO** não pode ter quantidade > 1 num único registro — o sistema cria um `AlmoxarifadoEstoque` por número de série.
- Se um item tiver `estoque_minimo` em branco, o dashboard interpreta como `0` (não dispara alerta de estoque baixo). Cadastre o mínimo nos itens críticos.
- A **entrada** sempre cria um movimento (`AlmoxarifadoMovimento`) — não há "ajuste rápido" sem rastro.
- A tela `entrada` redireciona com `flash` em caso de validação tenant; sempre confirme o `admin_id` ao depurar.
- O **arquivo `almoxarifado_views.py` é grande (~140 KB)**: para entender um fluxo específico, prefira procurar pelo nome da rota com `grep -n "@almoxarifado_bp.route" almoxarifado_views.py`.
- **Relatórios** (`/almoxarifado/relatorios`) consolidam por período/fornecedor/categoria — use para análise mensal.
