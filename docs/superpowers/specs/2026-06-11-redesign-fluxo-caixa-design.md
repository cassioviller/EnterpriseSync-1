# Design — Redesenho da Visualização do Fluxo de Caixa (Dashboard Híbrido)

**Data:** 2026-06-11
**Autor:** Cássio + Claude
**Status:** Aprovado (design) — revisado após sessão de grilling (decisões Q1–Q8)
**Relacionados:** `financeiro_service.py` (`calcular_fluxo_caixa`),
`financeiro_views.py` (`fluxo_caixa`), `templates/financeiro/fluxo_caixa.html`,
`docs/adr/0003-fluxo-caixa-variacao-relativa-nao-saldo-absoluto.md`,
`docs/superpowers/specs/2026-06-10-filtro-periodo-fluxo-design.md`

## 1. Problema

Os dados de fluxo de caixa estão corretos e completos no banco (validado por
reconciliação end-to-end em 2026-06-11: 1.618 movimentos do batch `veks2026_162255`,
entradas R$ 1.166.042,55 / saídas R$ 1.504.202,39). **O problema é de apresentação.**
A tela atual (`templates/financeiro/fluxo_caixa.html`) é um livro-razão, não um fluxo
de caixa:

1. **Sem visão no tempo.** 1.618 linhas planas paginadas por data. Sem variação
   acumulada — impossível responder "como o caixa evoluiu / vai evoluir?".
2. **Tabela gigante e plana.** Nenhum agrupamento por mês.
3. **Realizado × previsto confuso.** Pago e previsto na mesma tabela, distintos só pela
   cor da linha.
4. **Sem gráfico e sem subtotais.**

## 2. Decisões (confirmadas com o usuário; refs Q# da sessão de grilling)

- **Q1 — Realizado × Previsto separados em todo lugar.** A tela nunca soma os dois num
  número único. Ver glossário (`CONTEXT.md`): **Realizado**, **Previsto**.
- **Q2 — Tabela focada no Realizado** + uma coluna "Previsto líquido do mês". O detalhe
  por lançamento (com badge de status) fica no drill-down.
- **Q3 — A linha de evolução é "Variação acumulada de caixa" (parte de 0)**, não saldo
  absoluto (o sistema não mantém saldo bancário — ADR 0003). "Saldo em banco" é um KPI
  separado, exibindo o valor real dos bancos (hoje R$ 0).
- **Q4 — Gráfico:** 2 barras realizadas (Entradas/Saídas) + 2 linhas (Variação
  acumulada **realizada**, sólida; Variação acumulada **projetada** = realizado +
  previsto, tracejada). Previsto não vira barra.
- **Q5/Q6 — Filtro de Obra funciona** (toca no `calcular_fluxo_caixa`); **Centro de
  Custo e Tipo são removidos** desta tela.
- **Granularidade:** mês (v1). Sub-grupo por categoria fica para v2.
- **Sem dependência nova:** Chart.js já carregado (`static/js/vendor/chart.js`). Visual
  segue `DESIGN.md` (Bootstrap 5, azul `#0d6efd`, tabelas densas, badges de status).

## 3. Arquitetura / fluxo de dados

### 3.1 `calcular_fluxo_caixa` ganha filtro de Obra (Q6)

Adicionar parâmetro opcional `obra_id: int = None`. Quando presente, filtrar cada fonte:
- `ContaReceber` (entradas previstas) → `.filter(ContaReceber.obra_id == obra_id)` (exato).
- `FluxoCaixa` (realizado, diretos e pagamentos) → `.filter(FluxoCaixa.obra_id == obra_id)` (exato).
- `GestaoCustoPai` (saídas previstas) → **aproximado**: incluir o pai se **algum filho**
  for da obra: `.filter(GestaoCustoPai.itens.any(GestaoCustoFilho.obra_id == obra_id))`.
  O valor contado é o do **pai inteiro** (Q8) — pai cruzando obras superestima, mas é
  raro (importação cria pai↔filho 1:1). Registrar a aproximação em comentário.

Demais retornos de `calcular_fluxo_caixa` permanecem: `detalhes` (cada item com `data`,
`tipo`, `descricao`, `valor`, `origem`, `status`, `realizado`, `editavel?`, `id?`),
`saldo_inicial`, `entradas_previstas`, `saidas_previstas`, `saldo_final_projetado`,
`alerta`.

### 3.2 Nova função pura `agregar_fluxo_mensal`

Staticmethod em `FinanceiroService`, **pura** (lista entra, dict sai — sem query):

```python
@staticmethod
def agregar_fluxo_mensal(detalhes: list, saldo_inicial: float) -> dict:
    """
    Retorna:
      {
        'meses': [
          { 'mes': '2026-01', 'label': 'Jan/26',
            'entradas_real': float, 'saidas_real': float,      # Realizado do mês
            'saldo_mes_real': float,                            # entradas_real - saidas_real
            'variacao_acumulada': float,                        # Σ saldo_mes_real até aqui (começa em 0)
            'previsto_liquido': float,                          # (entradas_prev - saidas_prev) do mês
            'movimentos': [ <itens de detalhes do mês> ],
          }, ...,
          # bucket final opcional:
          { 'mes': 'sem-data', 'label': 'Sem data', ... 'variacao_acumulada': None }
        ],
        'kpis': {
          'saldo_banco': float,        # = saldo_inicial (valor real dos bancos; KPI honesto)
          'realizado_liquido': float,  # Σ saldo_mes_real (todos os meses com data)
          'previsto_liquido': float,   # Σ previsto_liquido
        },
        'serie_chart': {               # pronto pro Chart.js
          'labels': ['Jan/26', ...],
          'entradas_real': [float, ...],          # barra verde
          'saidas_real': [float, ...],            # barra vermelha (positivos)
          'var_acum_real': [float, ...],          # linha sólida (de 0)
          'var_acum_proj': [float, ...],          # linha tracejada (realizado + previsto acumulado)
        }
      }
    """
```

- **Variação acumulada (Q3):** começa em **0**, soma só `saldo_mes_real`. Não usa
  `saldo_inicial` como âncora.
- **Variação projetada:** `var_acum_real[i] + Σ previsto_liquido até i`. Coincide com a
  realizada quando não há previsto.
- **Realizado vs previsto:** pelo campo `realizado` (bool) de cada item.
- **Bucket "sem data" (Q3/edge):** itens com `data` nula vão para um mês `'sem-data'` ao
  fim; **não** entram em `serie_chart` nem na variação acumulada; **entram** nos KPIs.
- **Mês "Saldo projetado" do KPI:** o card usa `fluxo['saldo_final_projetado']` do
  service (fonte única), não recalculado aqui.

### 3.3 View `fluxo_caixa`

Ler `obra_id` dos args (já lê), repassar a `calcular_fluxo_caixa(admin_id, data_inicio,
data_fim, obra_id=obra_id or None)`. Depois `agg = agregar_fluxo_mensal(fluxo['detalhes'],
fluxo['saldo_inicial'])` e passar `meses`, `kpis`, `serie_chart` ao template. **Remover**
do contexto/template os selects de Centro de Custo e Tipo (Q6/Q7).

## 4. Layout da tela (`fluxo_caixa.html`)

```
┌─ Filtros: período · OBRA ───────────────────────────────────────┐  (centro/tipo removidos)
├─ KPIs (4 cards) ────────────────────────────────────────────────┤
│ [Saldo em banco] [Realizado no período] [A realizar] [Projetado]│
├─ Gráfico (Chart.js misto) ──────────────────────────────────────┤
│  barras Entradas-real(verde) / Saídas-real(vermelho) por mês    │
│  + linha Variação acum. realizada(sólida) + projetada(tracejada)│
├─ Tabela mensal (foco no Realizado) ─────────────────────────────┤
│ Mês ▾ │ Entradas │ Saídas │ Saldo mês │ Var.acum │ Prev.líq │ nº │
│ Jan/26  120.000   -98.000   +22.000    +22.000    -7.000    312 │
│   └ drill-down: lançamentos do mês (badge Realizado/Previsto),  │
│      edição inline preservada                                    │
└─────────────────────────────────────────────────────────────────┘
```

### 4.1 KPIs (Q1)
- **Saldo em banco** = `kpis.saldo_banco` (hoje R$ 0; dica "configure os saldos").
- **Realizado no período** = `kpis.realizado_liquido` (verde ≥0 / vermelho <0).
- **A realizar (previsto)** = `kpis.previsto_liquido`.
- **Saldo projetado** = `fluxo.saldo_final_projetado`; vermelho + alerta se `fluxo.alerta`.

### 4.2 Gráfico (Q4)
Chart.js misto: barras `entradas_real` (verde `#198754`) e `saidas_real` (vermelho
`#dc3545`) no eixo Y principal; linha `var_acum_real` (azul `#0d6efd`, sólida) e
`var_acum_proj` (azul tracejada) no eixo Y secundário. Tooltips pt-BR (R$). Se
`labels` vazio, não instanciar — mostrar "sem dados no período".

### 4.3 Tabela mensal + drill-down (Q2)
Colunas: **Mês ▾ · Entradas · Saídas · Saldo mês · Variação acumulada · Previsto líquido
· nº · [expandir]**. As 4 primeiras colunas de valor são **Realizado**; "Previsto
líquido" é o único número de previsto na grade. Linha do mês colorida pelo sinal de
`saldo_mes_real`. Drill-down (Bootstrap collapse, server-side) reusa o render de célula
atual (`cell-editable`, `data-field`, `data-edit-url`, `data-id`) para preservar a
edição inline; dentro do mês, Realizado/Previsto distinguidos pelo badge de status.
Meses começam fechados. Bucket "Sem data" no fim, sem variação acumulada.

## 5. Filtros (Q5–Q7)
- **Período** (`data_inicio`/`data_fim`): mantém comportamento atual (default mês corrente).
- **Obra:** select existente passa a filtrar de verdade (via §3.1). Exato em entradas e
  realizado; aproximado em saídas previstas (Q8).
- **Centro de Custo e Tipo:** removidos da tela (não há como honrá-los de forma
  consistente / distorcem a visão de fluxo).

## 6. Estados de borda
- **Período sem dados:** mantém o empty state atual.
- **Movimentos sem data:** bucket "Sem data" (§4.3); fora do gráfico e da variação
  acumulada; dentro dos KPIs.
- **Saldo projetado negativo:** card vermelho + alerta.
- **Performance:** ~1.600 `<tr>` em `collapse` escondido — aceitável para ferramenta
  interna desktop; paginar por mês fica para v2 se necessário.

## 7. Verificação
1. **Teste unitário** de `agregar_fluxo_mensal` (pura), em `tests/`: lista vazia; um mês;
   dois meses (variação acumulada acumula a partir de 0); separação realizado/previsto;
   bucket "sem data"; série do chart coerente.
2. **Teste do filtro de Obra** em `calcular_fluxo_caixa`: com `obra_id`, entradas e
   realizado batem com a obra; pai de saída prevista entra se tiver filho na obra.
3. **Render real** (jan–jun/2026, batch `veks2026_162255`): totais mensais somam
   entradas R$ 1.166.042,55 / saídas R$ 1.504.202,39; variação acumulada internamente
   consistente (de 0); KPIs/gráfico/drill-down coerentes; edição inline e modal OK;
   filtro de Obra reduz os números corretamente.

## 8. Fora de escopo (YAGNI)
- Centro de Custo e Tipo na tela; filtro de Obra **exato** em saídas previstas
  (exigiria denormalizar obra/centro no `GestaoCustoPai` — projeto à parte).
- Sub-grupo por categoria; toggle dia/semana; barras empilhadas realizado/previsto.
- Exportação; reconstrução de saldo bancário absoluto (ADR 0003); correção da quirk do
  `saldo_final_projetado` (projeta só com previsto).
