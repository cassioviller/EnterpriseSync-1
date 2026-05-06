# Frota

A **Frota** (`/frota/`) gerencia **veículos** da empresa, **usos** (quilometragem, motorista, passageiros, obra) e **despesas** (combustível, manutenção, IPVA, multas). O **dashboard TCO** consolida o **custo total de propriedade** por veículo, tipo e período.

## Para que serve

- Cadastrar veículos (placa, marca, modelo, ano, tipo, combustível, KM atual).
- Registrar **utilizações** (data, motorista, passageiros, obra, KM percorrido).
- Registrar **despesas** com data, tipo, valor e descrição.
- Calcular o **TCO total** e o **custo médio por KM** com filtros por tipo, período e status.

## Como acessar

- **Menu superior → "Frota"** → `/frota/` (lista de veículos).
- **+ Novo veículo:** `/frota/novo`.
- **Detalhes do veículo:** `/frota/<id>` (abas: Uso e Custos).
- **Editar:** `/frota/<id>/editar`.
- **Dashboard TCO:** `/frota/dashboard`.
- **Novo uso:** `/frota/<veiculo_id>/uso/novo`.
- **Novo custo:** `/frota/<veiculo_id>/custo/novo`.

## Fluxos principais

### 1. Cadastrar veículo

1. **Menu → Frota → "+ Novo Veículo"** (`/frota/novo`).
2. Preencha os obrigatórios: **Placa**, **Marca**, **Modelo**, **Ano**, **Tipo** (Utilitário, Caminhão, Van, Moto…).
3. Opcionalmente: **Cor**, **Combustível** (padrão `Gasolina`), **Chassi**, **Renavam**, **KM atual**.
4. Salve — o veículo entra como **ativo** e aparece em `/frota/`.

### 2. Lançar uso

1. **Lista de veículos → clique no veículo → aba "Uso" → "+ Novo Uso"** (`/frota/<veiculo_id>/uso/novo`).
2. Preencha **Data**, **Hora saída**, **KM inicial** (obrigatórios). Inclua **Hora retorno** e **KM final** para que o sistema calcule **KM percorrido** automaticamente.
3. Selecione **Motorista** (`Funcionario`), **Obra** e **Passageiros frente / trás** (multi-select — vira CSV no banco).
4. Salve — o uso entra na aba e atualiza o **KM atual** do veículo.

### 3. Lançar despesa

1. **Detalhe do veículo → aba "Custos" → "+ Novo Custo"** (`/frota/<veiculo_id>/custo/novo`).
2. Preencha **Data**, **Tipo** (combustível, manutenção, IPVA, seguro, multa…), **Valor** e **Descrição**.
3. Para abastecimento, registre **litros** e **KM no momento** para calcular consumo médio.
4. Salve — a despesa entra no TCO do veículo.

### 4. Editar / desativar / reativar veículo

1. Em `/frota/<id>`, clique em **"Editar"** (`/frota/<id>/editar`) para atualizar dados.
2. Para **desativar**, use o botão de **excluir** (`POST /frota/<id>/deletar`) — o veículo é marcado como inativo (não some do histórico).
3. Para **reativar**, em `/frota/?status=inativo` clique em **Reativar** (`POST /frota/<id>/reativar`).

### 5. Editar / excluir uso ou custo

1. Em `/frota/<id>`, abra o uso/custo e clique em **Editar** (`/frota/uso/<uso_id>/editar` ou `/frota/custo/<custo_id>/editar`).
2. Para excluir, use o botão **Excluir** que dispara `POST /frota/uso/<id>/deletar` ou `/frota/custo/<id>/deletar`.

### 6. Dashboard TCO

1. **Menu → Frota → Dashboard** (`/frota/dashboard`).
2. KPIs:
   - **TCO total** (Σ despesas no período).
   - **KM total** percorrido.
   - **Custo médio por KM** (TCO / KM).
3. Filtros: **período**, **tipo de veículo**, **status** (`ativo`, `inativo`, vazio = todos). O padrão é **somente ativos**.
4. Ranking de veículos por TCO e por custo/KM.

## Dicas e cuidados

- **Passageiros são gravados como CSV** (`"3,7,12"`) — não use vírgula em nomes; use o select multi-select sempre que possível.
- O **KM atual** do veículo é atualizado a partir do `km_final` do último uso lançado; não edite manualmente o veículo para "corrigir" KM — lance um uso de ajuste.
- **Excluir uso ou custo** não é destrutivo no sentido financeiro, mas remove a linha do TCO; prefira **editar** quando possível.
- **Veículos inativos** continuam contando no histórico, mas saem do dashboard padrão. Use o filtro `status=inativo` para auditá-los.
- O dashboard usa `func.coalesce(..., 0)` para evitar erro com tabela vazia, mas em demos sem veículos cadastrados o dashboard exibe **zerado** — não é bug.
- O detalhe do veículo agrega **uso + custos** numa única página com abas; para visões consolidadas, use `/frota/dashboard`.
