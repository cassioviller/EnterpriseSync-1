# Lançamento da etapa com Categoria de Fluxo de Caixa (Pedaço 2)

> **Estado em 2026-08-25 (varredura de fecho):** ✅ **REALIZADA** — o plano correspondente foi executado e o código está na árvore.
>
> Veredito dado por **existência de código na árvore**, não por checkbox nem por
> mensagem de commit. Índice completo em `docs/planos-em-aberto-2026-08-25.md`.


> Data: 2026-06-29. Obra-piloto: Baia.
> Parte 2 da iniciativa "custo realizado por lançamentos amarrados à etapa".
> Contexto de partida: `2026-06-29-realizado-por-lancamentos-design.md` (Pedaço 1, já
> implementado em 8 commits — o painel da etapa tem a aba "Realizado — lançamentos" com
> "+ Novo lançamento" que cria um `GestaoCustoFilho` via `registrar_custo_automatico`).

## Contexto e revisão do escopo da iniciativa

A spec original do Pedaço 1 previa que o Pedaço 2 fosse um **menu de tipos** ("+ Novo
lançamento" → Compra/Transporte/Mão de obra/Alimentação…), abrindo o formulário de cada
módulo já amarrado a obra/etapa/período, com **Compra** implementada de ponta a ponta.

No brainstorming o usuário **simplificou e redirecionou** esse pedaço: em vez de abrir o
formulário de um módulo de origem, o "+ Novo lançamento" continua sendo **um formulário
único**, mas ganha um campo **Categoria**. A categoria escolhida é a do **fluxo de caixa**
(catálogo `CategoriaFluxoCaixa`, gerenciado pelo admin), de modo que o lançamento "já nasce
na categoria certa" e aparece categorizado no relatório de Fluxo de Caixa. O menu de tipos e a
integração com o módulo de Compras saem deste pedaço (viram trabalho futuro, se ainda desejados).

## Problema

Hoje o lançamento manual da etapa (Pedaço 1) é criado com `tipo_categoria='OUTROS'` fixo
(`views/obras.py`, `financeiro_etapa_lancamento_criar`). O usuário não consegue dizer **de que
categoria** é o gasto, então:

- No relatório de **Fluxo de Caixa** o movimento aparece como "Lançamento manual [OUTROS]".
- Não há vínculo com o catálogo curável de categorias (`CategoriaFluxoCaixa`) que o usuário
  já gerencia em `/catalogos/categorias-fluxo-caixa` e usa no modal "Nova Movimentação".

## Decisão central: qual taxonomia de categoria usar

O sistema tem **duas taxonomias de categoria paralelas e hoje desconectadas**:

| | `GestaoCustoPai.tipo_categoria` (enum) | `CategoriaFluxoCaixa` (catálogo) |
|---|---|---|
| Origem | Fixa no código (`MATERIAL`, `MAO_OBRA_DIRETA`, `ALIMENTACAO`, `OUTROS`…) | Tabela por-tenant, gerenciada pelo admin |
| Categoriza | O custo (`GestaoCustoPai`) — base da Gestão de Custos e do Realizado da etapa | Movimentos diretos de `FluxoCaixa` (modal "Nova Movimentação", importação) |
| Liga à outra | — | **Não há mapa.** `GestaoCustoPai` nem tem FK para `CategoriaFluxoCaixa` |

**Decisão (acordada no brainstorming):** usar a **`CategoriaFluxoCaixa`** (lista curável do
usuário) como a categoria do lançamento da etapa. Isso exige **adicionar uma FK
`categoria_fluxo_caixa_id` ao `GestaoCustoPai`** (migração) — um passo na direção de unificar
as duas taxonomias. O `tipo_categoria` (NOT NULL) **permanece** e continua sendo `'OUTROS'`
para o lançamento manual; a categoria real do lançamento passa a ser a `categoria_fluxo_caixa_id`.

**Escopo do relatório (acordado):** além de gravar a categoria, o **relatório de Fluxo de
Caixa** passa a **exibir** o nome da `CategoriaFluxoCaixa` (quando presente) no rótulo do
movimento, no lugar de `[tipo_categoria]`. O agrupamento do relatório continua **por mês**
(não passa a agrupar por categoria — isso seria um redesenho do template, fora de escopo).

## Modelo de dados

Sem tabela nova. Uma coluna nova:

- **`GestaoCustoPai.categoria_fluxo_caixa_id`** — `db.Column(db.Integer,
  db.ForeignKey('categoria_fluxo_caixa.id'), nullable=True)`. É onde a categorização do custo
  vive e o que o relatório de Fluxo de Caixa lê (`financeiro_service.py` consulta
  `GestaoCustoPai`). Adicionar também o `relationship`:
  `categoria_fluxo_caixa = db.relationship('CategoriaFluxoCaixa', foreign_keys=[categoria_fluxo_caixa_id])`
  — usado pelo relatório (`custo.categoria_fluxo_caixa.nome`) e por `lancamentos_da_etapa`
  (`categoria_label`).

`GestaoCustoFilho` não ganha campo de categoria: a categorização permanece no nível do Pai
(o Filho herda do Pai, como hoje). O Realizado da etapa (soma de `GestaoCustoFilho` por
`obra_servico_custo_id`, Pedaço 1) **não muda** — a categoria é só para exibição/relatório.

### Categoria-fallback

Quando o POST não traz `categoria_fluxo_caixa_id`, ou traz uma inválida (de outro tenant, não
`SAIDA`, ou inativa), o lançamento cai na categoria **"Outras Saídas"** do tenant
(`CategoriaFluxoCaixa` com `nome='Outras Saídas'`, `tipo='SAIDA'`, `grupo_financeiro='Outros'` —
linha de `_DEFAULTS`). Nunca falha por causa de categoria (preferência do usuário). Se o tenant
ainda não tiver essa linha (catálogo não semeado), grava `categoria_fluxo_caixa_id=None`
(o lançamento continua válido; cai no comportamento atual `[OUTROS]`).

## `registrar_custo_automatico` (utils/financeiro_integration.py)

A função (l.59-211) ganha um parâmetro **opcional** `categoria_fluxo_caixa_id=None`:

1. Ao **buscar o Pai em aberto** (l.118-151), incluir `categoria_fluxo_caixa_id` na chave de
   correspondência (junto de `admin_id`, `tipo_categoria`/equivalentes e `entidade`). **Sem
   isso, lançamentos de categorias diferentes — todos `tipo_categoria='OUTROS'` e
   `entidade_nome='Lançamento manual'` — se fundiriam num único Pai.** Com isso, cada categoria
   vira (no máximo) um Pai em aberto por entidade.
2. Ao **criar o Pai** (l.144-151), gravar `categoria_fluxo_caixa_id`.
3. Não muda mais nada: validação de `obra_servico_custo_id`, criação do Filho, recálculo do
   total, flush sem commit — tudo igual ao Pedaço 1.

Chamadas existentes (Compras, Alimentação, etc.) não passam o novo parâmetro → `None` →
comportamento atual preservado.

## Endpoints (views/obras.py — reusa as rotas do Pedaço 1, sem rota nova)

### `POST /obras/<id>/financeiro/etapa/<osc_id>/lancamentos`

Body passa a aceitar `categoria_fluxo_caixa_id` (além de `data`, `descricao`, `valor`,
`fornecedor?` do Pedaço 1):

- Resolve a categoria: se `categoria_fluxo_caixa_id` for de uma `CategoriaFluxoCaixa` do tenant
  com `tipo='SAIDA'` e `ativo=True`, usa-a; senão resolve para a "Outras Saídas" do tenant
  (ou `None` se inexistente). **Não retorna 400 por categoria** (fallback silencioso).
- Repassa `categoria_fluxo_caixa_id=<resolvido>` a `registrar_custo_automatico(...)` (demais
  parâmetros iguais ao Pedaço 1: `tipo_categoria='OUTROS'`,
  `origem_tabela='lancamento_periodo_manual'`, `obra_servico_custo_id=osc_id`).
- Resposta inalterada em forma: `{'lancamento_id': filho.id, 'painel': painel_financeiro(obra)}`.
- Guardas do Pedaço 1 mantidas: obra+tenant+osc via `first_or_404`; valor inválido/negativo →
  400; data inválida → 400.

### `GET /obras/<id>/financeiro/etapa/<osc_id>/lancamentos`

Passa a devolver, além de `lancamentos`:

- `categorias`: lista agrupada para montar o dropdown —
  `[{"grupo": <grupo_financeiro>, "opcoes": [{"id": int, "nome": str}, …]}, …]`, a partir das
  `CategoriaFluxoCaixa` do tenant com `tipo='SAIDA'` e `ativo=True`, ordenadas por
  `grupo_financeiro`, `nome`. (Helper `categorias_fluxo_caixa_saida(admin_id)`.)
- Em cada item de `lancamentos`, dois campos novos: `categoria_id` (int|None) e
  `categoria_label` (str|None) — vindos de `GestaoCustoPai.categoria_fluxo_caixa`.

`lancamentos_da_etapa(obra, osc_id)` (em `services/cronograma_fisico_financeiro.py`) já junta
`GestaoCustoFilho`→`GestaoCustoPai`; passa a ler também `pai.categoria_fluxo_caixa_id` e o
`nome` da categoria (via join/relationship), preenchendo `categoria_id`/`categoria_label`.

### `PATCH /obras/<id>/financeiro/etapa/<osc_id>/lancamentos/<filho_id>`

Inalterado: edita `data`/`descricao`/`valor` do lançamento manual e recalcula o Pai. **Trocar
a categoria de um lançamento existente fica fora de escopo** (exigiria re-parent de
`GestaoCustoPai`); para corrigir categoria, exclui e relança.

## Relatório de Fluxo de Caixa (financeiro_service.py)

Em `FinanceiroService.calcular_fluxo_caixa`, nos dois pontos onde a categoria aparece embutida
na descrição do movimento de `GestaoCustoPai` (l.572 e l.601):

```python
descricao = f'{custo.entidade_nome} [{custo.tipo_categoria}]'
```

passa a usar o nome da `CategoriaFluxoCaixa` quando o Pai tiver uma:

```python
cat = custo.categoria_fluxo_caixa.nome if custo.categoria_fluxo_caixa_id else custo.tipo_categoria
descricao = f'{custo.entidade_nome} [{cat}]'
```

(Implementar via um pequeno helper local para não repetir.) Nada mais muda no serviço nem no
template: o relatório continua agrupando por mês, lista plana de movimentos. Os movimentos
**realizados** já vêm de `FluxoCaixa` (que tem `categoria_fluxo_caixa_id` próprio) e não são
afetados por esta mudança.

## Migração 204

`migrations.py`: nova função após `_migration_203_drop_valor_realizado`, idempotente, padrão
do repo (`ADD COLUMN IF NOT EXISTS`):

```python
def _migration_204_gestao_custo_pai_categoria_fc():
    """Lançamento por categoria de fluxo de caixa — adiciona
    gestao_custo_pai.categoria_fluxo_caixa_id (FK p/ categoria_fluxo_caixa). Idempotente.
    Ver spec 2026-06-29-lancamento-categoria-fluxo-caixa-design."""
    from sqlalchemy import text as sa_text
    try:
        with db.engine.begin() as conn:
            conn.execute(sa_text(
                "ALTER TABLE gestao_custo_pai "
                "ADD COLUMN IF NOT EXISTS categoria_fluxo_caixa_id INTEGER "
                "REFERENCES categoria_fluxo_caixa(id)"))
        logger.info("[Migration 204] gestao_custo_pai.categoria_fluxo_caixa_id adicionada.")
    except Exception as e:
        logger.error(f"[Migration 204] Falha: {e}", exc_info=True)
        raise
```

Registrar na lista `migrations_to_run` (após a 203, ~l.4003):

```python
            (204, "Lançamento por categoria — gestao_custo_pai.categoria_fluxo_caixa_id", _migration_204_gestao_custo_pai_categoria_fc),
```

## UI (static/js/financeiro_obra.js)

- **`lancamentoForm(box, et, l)`** ganha um `<select>` de categoria com `<optgroup>` por
  `grupo`, montado a partir do `categorias` do GET `.../lancamentos` (guardado quando a aba
  Realizado carrega). O `<select>` vem antes de data/descrição/valor. No POST, inclui
  `categoria_fluxo_caixa_id` no payload.
- **Lista de lançamentos** (`renderRealizado`): cada linha mostra um badge com
  `categoria_label` (quando houver), ao lado do badge de origem.
- Resto do fluxo do Pedaço 1 inalterado (salvar → `render(painel)` + `carregarRealizado`).

## Testes (tests/test_painel_financeiro.py)

- **Migração / coluna:** `GestaoCustoPai.__table__` tem `categoria_fluxo_caixa_id`.
- **POST grava a CFC no Pai:** `POST .../lancamentos` com `categoria_fluxo_caixa_id` de uma
  `CategoriaFluxoCaixa` SAÍDA do tenant → `GestaoCustoFilho` criado, e seu `pai
  .categoria_fluxo_caixa_id` é o escolhido.
- **A chave do Pai separa categorias:** dois POSTs na mesma etapa com categorias diferentes →
  **dois** `GestaoCustoPai` distintos (não fundem num só apesar de `tipo_categoria='OUTROS'` e
  mesma entidade).
- **Fallback "Outras Saídas":** POST sem `categoria_fluxo_caixa_id` (ou com id inválido) →
  Pai com a CFC "Outras Saídas" do tenant (ou `None` se o catálogo não estiver semeado);
  nunca 400 por categoria.
- **GET expõe categorias e label:** `GET .../lancamentos` traz `categorias` agrupado por
  `grupo` (só SAÍDA ativas) e, por lançamento, `categoria_id`/`categoria_label`.
- **Relatório de Fluxo de Caixa:** com um custo de `categoria_fluxo_caixa_id` setado,
  `calcular_fluxo_caixa` produz a descrição com o **nome da CFC** (não `[OUTROS]`).
- **Multitenant:** `categoria_fluxo_caixa_id` de outro admin → tratado como inválido (cai no
  fallback), não vaza categoria de outro tenant.
- **Invariantes da Baia** preservados; suíte financeira verde:
  `pytest tests/test_cronograma_fisico_financeiro.py tests/test_painel_financeiro.py tests/test_importacao_fisico_financeiro.py -q`.
- **UI** (dropdown agrupado + badge) verificada no browser real (Playwright/chromium do Nix),
  como nos pedaços anteriores.

## Invariantes da Baia

- **Previsto inalterado:** veks 800.960 / fat 550.775 / lucro 24.976 / imposto 128.903 /
  contrato 1.505.613,76 / data_fim 08/10.
- **Realizado** continua vindo só de `GestaoCustoFilho` ligados às etapas (Pedaço 1); a coluna
  nova é metadado de categoria no Pai, não altera somatórios.

## Fora de escopo (Pedaço 2)

- Substituir `tipo_categoria` por `categoria_fluxo_caixa_id` em todo o sistema (Gestão de
  Custos, demais relatórios) — unificação completa das taxonomias é trabalho futuro.
- Agrupar o relatório de Fluxo de Caixa **por categoria** (hoje é por mês).
- Editar a categoria de um lançamento já criado (re-parent de Pai).
- Menu de tipos e abertura do formulário real do módulo de Compras (PedidoCompra/itens/
  parcelas) — descartados/adiados.
- Campo "Etapa" nos formulários dos módulos de origem.
</content>
</invoke>
