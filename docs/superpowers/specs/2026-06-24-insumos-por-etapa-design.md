# Design — Edição de insumos (linhas de custo) por etapa no painel Financeiro

**Data:** 2026-06-24
**Branch:** `feat/insumos-por-etapa`
**Arquivos:** `models.py`, `migrations.py`, `views/obras.py`,
`services/cronograma_fisico_financeiro.py`, `services/importacao_fisico_financeiro.py`,
`static/js/financeiro_obra.js`, `tests/`.

## Problema

No painel Financeiro da obra, ao clicar numa etapa abre-se um editor com **3 campos
agregados** (Veks, Fat direto, Orçado) que grava direto no `ObraServicoCusto` (OSC).
O usuário quer ver e editar **todas as linhas de custo (insumos) que compõem a
etapa** ali mesmo, e que o custo da etapa seja **derivado** dessas linhas.

## Decisões (do usuário)

1. **Custo DERIVADO dos insumos:** as linhas são a fonte da verdade; editar/
   adicionar/remover recalcula Veks/Fat/Previsto da etapa.
2. **Linhas de custo por obra** (não o catálogo compartilhado): cada linha =
   descrição + valor + classificação Veks/Fat, guardada por OBRA/etapa. Editar
   aqui NÃO afeta outras obras.
3. **Importador popula as linhas** de `eap.itens`; a obra já importada (Baias) é
   re-importada para preencher.

## Modelo de dados

Nova tabela **`ObraServicoCustoItem`** (uma linha de custo de uma etapa):

| campo | tipo | nota |
|---|---|---|
| `id` | Integer PK | |
| `obra_servico_custo_id` | FK → `obra_servico_custo(id)` ON DELETE CASCADE, NOT NULL, index | etapa dona |
| `admin_id` | FK → `usuario(id)`, NOT NULL, index | tenant |
| `descricao` | String(200), NOT NULL | nome do item |
| `valor` | Numeric(15,2), NOT NULL, default 0 | valor da linha |
| `fonte` | String(20), NOT NULL, default `'veks'` | `'veks'` ou `'fat_direto'` |
| `ordem` | Integer, default 0 | ordenação na UI |

Migração **199** em `migrations.py` (próxima livre após 198; idempotente
`CREATE TABLE IF NOT EXISTS` + índices). Relationship
`ObraServicoCusto.itens_custo` (backref, cascade delete-orphan).

### Regra de derivação (fonte da verdade)

Helper puro/serviço `recalcular_osc_dos_itens(osc)`:
- `osc.mao_obra_a_realizar` (Veks) = Σ `valor` das linhas com `fonte='veks'`
- `osc.material_a_realizar` (Fat) = Σ `valor` das linhas com `fonte='fat_direto'`
- `osc.outros_a_realizar = 0`; mantém `fonte_mao_obra='veks'`, `fonte_material='fat_direto'`.
- **Previsto da etapa = Veks + Fat** (já é como `montar_fisico_financeiro` calcula
  `previsto = realizado + a_realizar`; aqui realizado_* seguem 0).

Isso preserva o mapeamento atual do físico-financeiro (Veks→mao_obra_a_realizar,
Fat→material_a_realizar), então não há regressão nos cálculos do painel/curva.

## Endpoints (`views/obras.py`)

- **GET `/obras/<id>/financeiro/dados`** — `painel_financeiro` passa a incluir, em
  cada etapa, a lista `itens: [{id, descricao, valor, fonte}, ...]` (evita fetch
  extra no clique).
- **POST `/obras/<id>/financeiro/etapa/<osc_id>/itens`** — corpo
  `{itens: [{descricao, valor, fonte}, ...], valor_orcado}`. **Substitui** todas as
  linhas da etapa (cobre adicionar/editar/remover de uma vez): apaga as linhas
  atuais da OSC, recria a partir do payload, grava `valor_orcado`, chama
  `recalcular_osc_dos_itens(osc)`, comita e retorna o **painel inteiro**
  (`_jsonable(painel_financeiro(obra))`). Validação: `valor` numérico ≥ 0,
  `fonte ∈ {veks, fat_direto}`, `descricao` não vazia (default "Item"); payload
  inválido → 400. Tenant-scoped (`first_or_404` na obra e na OSC).
- O endpoint agregado antigo **POST `/obras/<id>/financeiro/etapa/<osc_id>`** é
  **removido** (substituído pelo de itens).

## Importador (`services/importacao_fisico_financeiro.py`)

- Ao preencher cada OSC (após a aprovação canônica), criar uma
  `ObraServicoCustoItem` por entrada de `eap.itens`: para cada item, se
  `veks>0` cria linha (`descricao=item.item`, `valor=veks`, `fonte='veks'`); se
  `fat>0` cria linha (`valor=fat`, `fonte='fat_direto'`). Depois chama
  `recalcular_osc_dos_itens(osc)` (mantém os agregados coerentes com a soma das
  linhas — idêntico ao que já gravava de `custo.veks/fat`).
- Etapa sem `itens` no JSON: cria 1 linha-fallback do agregado
  (`descricao=nome da etapa`, `valor=custo.veks`, `fonte='veks'`) e, se houver fat,
  outra linha fat — para a etapa nunca ficar sem linhas.
- `_limpar_derivados` passa a apagar as `ObraServicoCustoItem` da obra (via as OSCs
  da obra) antes de recriar — idempotência.

## UI (`static/js/financeiro_obra.js`, função `showEtapa`)

Ao clicar numa etapa, renderiza uma **tabela editável** dentro de `#fin-etapa-det`:

- Cabeçalho: nome da etapa + "Realizado: R$ X / Previsto: R$ Y" (Previsto = soma
  calculada das linhas, atualiza ao digitar).
- Uma linha por item: `descricao` (input texto), `valor` (input número),
  `fonte` (select Veks / Fat direto), botão remover (✕).
- Rodapé: "**+ Adicionar linha**" (insere linha vazia), campo "**Orçado/venda (R$)**"
  (editável) e botão "**Salvar etapa**".
- "Salvar etapa" monta o payload `{itens, valor_orcado}`, faz POST (com
  `X-CSRFToken`), e no sucesso re-renderiza o painel inteiro com `render(p)` (a
  barra da etapa e os KPIs se atualizam).
- **Veks / Fat / Previsto** são exibidos como **calculados** (read-only), atualizados
  no cliente ao editar e confirmados pelo servidor no salvar.
- Etapa multi-OSC (`osc_id == null`): mantém "edição indisponível" (como hoje).

## Não-objetivos (YAGNI)

- Não editar o catálogo `Insumo`/`ComposicaoServico` nem o Orçamento a partir daqui.
- Não há classificação por insumo no catálogo (a classificação Veks/Fat vive só na
  linha de custo da etapa).
- Não há histórico/auditoria das linhas (fora de escopo).

## Testes

- **Modelo/migração:** `test_obra_servico_custo_item_schema` — colunas e tabela
  existem.
- **Derivação:** `test_recalcular_osc_dos_itens` — OSC com 3 linhas (2 veks, 1 fat)
  → `mao_obra_a_realizar = Σveks`, `material_a_realizar = Σfat`.
- **Importador popula linhas:** após importar Baias, a OSC da etapa "Indiretos"
  tem ≥1 `ObraServicoCustoItem`; Σ linhas veks da obra ≈ 734.460 e fat ≈ 423.700
  (mantém os invariantes atuais); reimport não duplica.
- **Endpoint substitui + recalcula:** POST itens com 2 linhas → OSC recalculada,
  painel retornado com a etapa atualizada; payload inválido → 400; multitenant
  (osc de outro admin → 404).
- **Painel inclui itens por etapa:** `painel_financeiro` retorna `itens` em cada
  etapa.
- **Manter verdes** os smokes atuais de painel/cronograma/importação.

## Riscos

- **Médio-baixo.** Mudança de modelo (nova tabela + derivação). Mitigação: a
  derivação preserva exatamente o mapeamento Veks→mao_obra/Fat→material que o
  físico-financeiro já usa, então os cálculos de curva/KPIs não mudam de fórmula.
  Migração idempotente. Endpoint antigo removido — conferir que nada além do painel
  o chamava (é específico do painel, criado na mesma leva).
