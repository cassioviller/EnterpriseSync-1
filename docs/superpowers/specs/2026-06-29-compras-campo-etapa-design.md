# Compras ganha o campo "Etapa" (Pedaço 3)

> Data: 2026-06-29. Obra-piloto: Baia.
> Parte 3 da iniciativa "custo realizado por lançamentos amarrados à etapa".
> Contexto: `2026-06-29-realizado-por-lancamentos-design.md` (visão completa).
> Pedaço 1 (realizado por lançamentos + lançamento manual) e Pedaço 2 (categoria de fluxo de
> caixa no lançamento manual) já implementados.

## A iniciativa e onde este pedaço entra

A visão completa: o **custo realizado** de cada etapa vem de **lançamentos reais** (Contas a
Pagar), e cada módulo de custo (Compras, Alimentação, Transporte, diárias do RDO, Folha…) nasce
ligado à obra **e** à etapa. Hoje só o **lançamento manual** (Pedaço 1) se amarra à etapa: os
módulos reais criam `GestaoCustoFilho` **sem `obra_servico_custo_id`**, então seus custos não
entram no realizado de nenhuma etapa.

Este pedaço pluga o **módulo de Compras** — o mais importante — para validar o padrão que os
demais módulos seguirão: a compra ganha um campo **Etapa**, e seu custo flui sozinho para o
Realizado da etapa.

## Problema

`processar_compra_normal` (`compras_views.py:162`) monta `GestaoCustoPai`+`GestaoCustoFilho`
diretamente (uma dupla por parcela), com `obra_id` mas **sem `obra_servico_custo_id`**. O mesmo
vale para `processar_compra_aprovada_cliente`. `PedidoCompra` (`models.py:4718`) tem `obra_id`
(opcional) mas **não tem** `obra_servico_custo_id`. Logo, nenhuma compra aparece no realizado de
uma etapa, mesmo quando é claramente o gasto de uma etapa específica.

## Objetivo

1. `PedidoCompra` ganha `obra_servico_custo_id` (opcional). O form Nova Compra ganha um select
   **Etapa** em cascata com a Obra.
2. Ao registrar a compra, os `GestaoCustoFilho` gerados recebem esse `obra_servico_custo_id` →
   a compra **entra automaticamente no Realizado da etapa** (que já soma `GestaoCustoFilho` por
   `obra_servico_custo_id`).
3. Na aba Realizado da etapa, a compra aparece como lançamento **só leitura** rotulado "Compra".

## Decisões (acordadas no brainstorming)

- **Etapa é OPCIONAL**, mesmo quando há Obra. Sem etapa, a compra se comporta como hoje (vai ao
  centro de custo da obra, só não entra no realizado de uma etapa específica). Retrocompatível.
- **Grava em dois lugares:** `PedidoCompra.obra_servico_custo_id` (rastreabilidade — a compra
  "lembra" sua etapa) **e** repassada ao(s) `GestaoCustoFilho` (o que faz o realizado somar).
- **Escopo: só Compras.** Demais módulos (Alimentação/Transporte/RDO/Folha) são os próximos
  pedaços, seguindo este mesmo padrão.

## Modelo de dados

- **`PedidoCompra.obra_servico_custo_id`** — `db.Column(db.Integer,
  db.ForeignKey('obra_servico_custo.id'), nullable=True)`. Mais o relationship:
  `obra_servico_custo = db.relationship('ObraServicoCusto', foreign_keys=[obra_servico_custo_id])`.
- `GestaoCustoFilho.obra_servico_custo_id` já existe (usado pelo Pedaço 1) — só passa a ser
  preenchido também pela compra.

`ObraServicoCusto` (a etapa) tem `id`, `obra_id`, `nome` (String 200) — é o que alimenta o select.

### Migração 205

`migrations.py`, após `_migration_204_gestao_custo_pai_categoria_fc`, idempotente, padrão do repo:

```python
def _migration_205_pedido_compra_obra_servico_custo():
    """Compras por etapa — adiciona pedido_compra.obra_servico_custo_id (FK p/
    obra_servico_custo). Idempotente. Ver spec 2026-06-29-compras-campo-etapa-design."""
    from sqlalchemy import text as sa_text
    try:
        with db.engine.begin() as conn:
            conn.execute(sa_text(
                "ALTER TABLE pedido_compra "
                "ADD COLUMN IF NOT EXISTS obra_servico_custo_id INTEGER "
                "REFERENCES obra_servico_custo(id)"))
        logger.info("[Migration 205] pedido_compra.obra_servico_custo_id adicionada.")
    except Exception as e:
        logger.error(f"[Migration 205] Falha: {e}", exc_info=True)
        raise
```

Registrar na lista `migrations_to_run`, após a 204:

```python
            (205, "Compras por etapa — pedido_compra.obra_servico_custo_id", _migration_205_pedido_compra_obra_servico_custo),
```

## Endpoint do cascata

`GET /obras/<int:id>/etapas-custo` (em `views/obras.py`) → `{"etapas": [{"id": int, "nome": str}, …]}`
das `ObraServicoCusto` da obra, tenant-scoped, ordenadas por `id` (ordem de cadastro). A obra é
validada por `admin_id` (`first_or_404`). Usado pelo select de Etapa quando a Obra muda.

## Backend de criação

### `POST /compras/nova` (`compras_views.py:529`)

- Ler `obra_servico_custo_id` do form. Resolver: se vier preenchido **e** houver `obra_id`,
  validar que a `ObraServicoCusto` pertence àquela obra e ao tenant; se válido, gravar no
  `PedidoCompra`; senão `None` (ignora silenciosamente — etapa nunca derruba a compra).
- Gravar `obra_servico_custo_id` ao construir o `PedidoCompra` (l.655-674).

### `processar_compra_normal` (`compras_views.py:162`)

No construtor de cada `GestaoCustoFilho`, adicionar `obra_servico_custo_id=pedido.obra_servico_custo_id`:

```python
        gcf = GestaoCustoFilho(
            ...
            obra_id=pedido.obra_id,
            obra_servico_custo_id=pedido.obra_servico_custo_id,
            origem_tabela='pedido_compra',
            origem_id=pedido.id,
        )
```

Cada parcela vira um `GestaoCustoFilho` (`data_referencia = data_compra`); **todas** recebem a
mesma etapa, então o realizado da etapa soma o valor total da compra. (A etapa não afeta
`ContaPagar` nem o almoxarifado — é só o vínculo de custo→etapa.)

### `processar_compra_aprovada_cliente` (`compras_views.py:274`)

Esse caminho cria `GestaoCustoPai` com `tipo_categoria='FATURAMENTO_DIRETO'`, que os agregadores
do realizado (`realizado_por_etapa`, `curva_realizado`, `lancamentos_da_etapa`) **excluem** — é
repasse ao cliente, não custo da empresa. Adicionar `obra_servico_custo_id=pedido.obra_servico_custo_id`
ao seu `GestaoCustoFilho` por **consistência/rastreabilidade**, mas com a ciência de que **não
aparece nem soma no Realizado da etapa** (por design). Não é o foco deste pedaço.

## Exibição no Realizado da etapa

- `realizado_por_etapa` / `curva_realizado` (`services/cronograma_fisico_financeiro.py`) já
  agregam `GestaoCustoFilho` por `obra_servico_custo_id` excluindo `FATURAMENTO_DIRETO`. A compra
  tem `tipo_categoria='MATERIAL'` → **conta automaticamente**, sem mudança nesses agregadores.
- `lancamentos_da_etapa` lista o `GestaoCustoFilho` da compra como **só leitura** (`editavel`
  só é `True` para `origem_tabela='lancamento_periodo_manual'`). Melhorar o `origem_label`:
  mapear `'pedido_compra'` → **"Compra"** (hoje mostra a string crua). Mapa simples:

```python
        _LABELS = {'lancamento_periodo_manual': 'Manual', 'pedido_compra': 'Compra'}
        origem_label = _LABELS.get(origem, (origem or 'Sistema'))
```

(mantendo `"Manual"` para o caso editável.)

## UI (`templates/compras/nova_compra.html`)

- Novo bloco **Etapa** logo após o select de Obra: `<select id="oscSelect"
  name="obra_servico_custo_id">` opcional, começa desabilitado/vazio com a opção
  "— Sem etapa —". Texto de ajuda: "Amarra o custo desta compra a uma etapa da obra (entra no
  Realizado dela)."
- JS: quando `#obraSelect` muda (inclui o evento do select2), faz `fetch` a
  `/obras/<obra_id>/etapas-custo`, popula `#oscSelect` com as etapas, habilita; se a obra ficar
  vazia, limpa e desabilita o select. Em falha de fetch, mantém "— Sem etapa —".

## Testes (tests/)

- **Coluna:** `PedidoCompra.__table__` tem `obra_servico_custo_id`.
- **Endpoint `etapas-custo`:** lista as `ObraServicoCusto` da obra; obra de outro admin → 404.
- **POST grava a etapa:** `POST /compras/nova` com `obra_servico_custo_id` da obra → o
  `PedidoCompra` e o(s) `GestaoCustoFilho` ficam com aquele `obra_servico_custo_id`.
- **Compra parcelada:** condição com N parcelas → N `GestaoCustoFilho`, **todos** com a etapa.
- **Realizado soma a compra:** `realizado_por_etapa`/`painel_financeiro` da obra refletem o
  valor da compra na etapa.
- **`lancamentos_da_etapa`:** a compra aparece com `origem_label='Compra'` e `editavel=False`.
- **Etapa inválida:** `obra_servico_custo_id` de outra obra/tenant no POST → ignorado
  (`PedidoCompra.obra_servico_custo_id` fica `None`), compra criada normalmente.
- **Sem etapa:** compra com obra e sem etapa → `GestaoCustoFilho.obra_servico_custo_id=None`
  (comportamento atual preservado).
- **Invariantes da Baia** preservados; suíte financeira verde:
  `pytest tests/test_cronograma_fisico_financeiro.py tests/test_painel_financeiro.py tests/test_importacao_fisico_financeiro.py -q`.
  (Testes de compras: ver `tests/` por um `test_compras*`/fixture existente; se não houver
  harness de compras, criar o test do POST no arquivo de compras ou em `test_painel_financeiro.py`
  montando o `PedidoCompra` e chamando `processar_compra_normal` diretamente.)
- **UI** (cascata Obra→Etapa + compra aparecendo no Realizado) verificada no browser real
  (Playwright/chromium do Nix), como nos pedaços anteriores.

## Invariantes da Baia

- **Previsto inalterado:** veks 800.960 / fat 550.775 / lucro 24.976 / imposto 128.903 /
  contrato 1.505.613,76 / data_fim 08/10.
- **Realizado** continua vindo só de `GestaoCustoFilho` ligados às etapas; agora compras com
  etapa também somam (antes não somavam em etapa nenhuma).

## Fora de escopo (Pedaço 3)

- Demais módulos (Alimentação, Transporte, diárias do RDO, Folha) — próximos pedaços, mesmo padrão.
- Editar a etapa de uma compra já registrada (não há tela de edição de compra hoje).
- Menu de tipos no "+ Novo lançamento" da etapa.
- Mudança em `ContaPagar`/almoxarifado/fluxo de caixa por causa da etapa (a etapa é só vínculo
  custo→etapa).
</content>
