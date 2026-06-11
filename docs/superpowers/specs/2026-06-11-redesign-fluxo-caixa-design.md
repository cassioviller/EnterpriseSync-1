# Design — Redesenho da Visualização do Fluxo de Caixa (Dashboard Híbrido)

**Data:** 2026-06-11
**Autor:** Cássio + Claude
**Status:** Aprovado (design)
**Relacionados:** `financeiro_service.py` (`calcular_fluxo_caixa`),
`financeiro_views.py` (`fluxo_caixa`), `templates/financeiro/fluxo_caixa.html`,
`docs/superpowers/specs/2026-06-10-filtro-periodo-fluxo-design.md`

## 1. Problema

Os dados de fluxo de caixa estão corretos e completos no banco (validado por
reconciliação end-to-end em 2026-06-11: 1.618 movimentos do batch `veks2026_162255`,
entradas R$ 1.166.042,55 / saídas R$ 1.504.202,39, com Contas a Receber e Contas a
Pagar batendo). **O problema é de apresentação.** A tela atual
(`templates/financeiro/fluxo_caixa.html`) é um livro-razão, não um fluxo de caixa:

1. **Sem visão no tempo.** 1.618 linhas planas numa tabela paginada por data. Não há
   saldo acumulado nem projeção — impossível responder "quando o caixa aperta?".
2. **Tabela gigante e plana.** Nenhum agrupamento por mês/categoria/obra.
3. **Realizado × previsto confuso.** Movimentos pagos e previstos na mesma tabela,
   distintos só pela cor da linha.
4. **Sem gráfico e sem subtotais.** Nenhuma agregação visível por período.

## 2. Decisões (confirmadas com o usuário)

- **Direção:** dashboard híbrido — KPIs + gráfico de evolução + tabela agrupada por
  mês com drill-down.
- **Granularidade do agrupamento (v1):** **mês**. Sub-agrupamento por categoria dentro
  do mês fica para v2.
- **Drill-down:** Bootstrap collapse, renderizado no servidor. Substitui o DataTable
  único atual por agrupamento server-side.
- **Edição inline preservada** dentro dos meses expandidos (mesmo endpoint
  `financeiro.editar_fluxo_caixa`).
- **Sem dependência nova:** Chart.js já é carregado localmente em `base_completo.html`
  (`static/js/vendor/chart.js`). Visual segue o `DESIGN.md` (Bootstrap 5, azul
  `#0d6efd`, tabelas densas `0.875rem`, badges de status existentes).

## 3. Arquitetura / fluxo de dados

`calcular_fluxo_caixa` **não muda** (é compartilhado e validado). Continua devolvendo
`detalhes` (lista plana) + `saldo_inicial`, `entradas_previstas`, `saidas_previstas`,
`saldo_final_projetado`, `alerta`.

### 3.1 Nova função pura `agregar_fluxo_mensal`

Adicionar a `FinanceiroService` (staticmethod) uma função **pura** (lista entra, dict
sai — sem I/O, sem query):

```python
@staticmethod
def agregar_fluxo_mensal(detalhes: list, saldo_inicial: float) -> dict:
    """Agrega a lista plana de movimentos em série mensal + KPIs.

    Retorna:
      {
        'meses': [
          {
            'mes': '2026-01',                 # chave ordenável
            'label': 'Jan/26',                # rótulo pt-BR
            'entradas': float,                # soma ENTRADA do mês
            'saidas': float,                  # soma |SAIDA| do mês (positivo)
            'saldo_mes': float,               # entradas - saidas
            'saldo_acumulado': float,         # saldo_inicial + soma dos saldo_mes até aqui
            'realizado_entradas': float, 'realizado_saidas': float,
            'previsto_entradas': float,  'previsto_saidas': float,
            'movimentos': [ <itens originais de detalhes daquele mês> ],
          }, ...
        ],
        'kpis': {
          'saldo_banco': float,               # = saldo_inicial
          'realizado_liquido': float,         # realizado_entradas - realizado_saidas (todos os meses)
          'previsto_liquido': float,          # previsto_entradas - previsto_saidas (todos os meses)
        },
        'serie_chart': {                      # pronto pra Chart.js (JSON no template)
          'labels': ['Jan/26', ...],
          'entradas': [float, ...],
          'saidas': [float, ...],            # positivos; exibidos como barra vermelha
          'saldo_acumulado': [float, ...],
        }
      }
    ```

- **Mês de um movimento:** derivado de `movimento['data']` (um `date`). Movimentos com
  `data` nula são agrupados num bucket `'sem-data'` ao final (rótulo "Sem data") para
  não sumirem.
- **Realizado vs previsto:** usa o campo `realizado` (bool) já presente em cada item de
  `detalhes`.
- **Fonte única do "Saldo projetado":** o card usa `fluxo['saldo_final_projetado']`
  vindo do service (não recalculo na agregação). Atenção: hoje o service projeta
  **só com o previsto** (`saldo_inicial + entradas_previstas − saidas_previstas`,
  ignorando o realizado do período) — é uma quirk existente que **não faço parte do
  escopo corrigir aqui**. O `saldo_acumulado` da série (que inclui realizado) é uma
  visão temporal própria do gráfico e pode legitimamente não coincidir com o
  `saldo_final_projetado`; os dois respondem perguntas diferentes.

### 3.2 View `fluxo_caixa`

Depois de obter `fluxo = FinanceiroService.calcular_fluxo_caixa(...)`, chamar
`agg = FinanceiroService.agregar_fluxo_mensal(fluxo['detalhes'], fluxo['saldo_inicial'])`
e passar `meses=agg['meses']`, `kpis=agg['kpis']`, `serie_chart=agg['serie_chart']|tojson`
ao template. Filtros, modal "Nova Movimentação" e contexto atual permanecem.

## 4. Layout da tela (`fluxo_caixa.html`)

Quatro blocos, de cima para baixo:

```
┌─ Filtros: período · obra · centro de custo · tipo ──────────────┐  (igual hoje)
├─ KPIs (4 cards) ────────────────────────────────────────────────┤
│ [Saldo em banco] [Realizado no período] [A realizar] [Projetado]│
│                                          (previsto)   ⚠ se <0    │
├─ Gráfico (Chart.js, tipo 'bar' + linha) ────────────────────────┤
│  barras Entradas(verde #198754) / Saídas(vermelho #dc3545) /mês │
│  + linha Saldo acumulado(azul #0d6efd) no eixo Y secundário     │
├─ Tabela agrupada por mês ───────────────────────────────────────┤
│ Mês ▾   Entradas   Saídas   Saldo mês   Saldo acum.  nº   [ver]  │
│ Jan/26  120.000   -98.000    +22.000     +22.000     312   ▸     │
│   └ (collapse) lançamentos do mês: Data·Tipo·Status·Origem·      │
│      Descrição·Valor — edição inline; linha do mês colorida pelo │
│      sinal do saldo_mes (verde/vermelho)                         │
└─────────────────────────────────────────────────────────────────┘
```

### 4.1 KPIs (separam realizado de previsto — dor #3)
- **Saldo em banco** = `kpis.saldo_banco`.
- **Realizado no período** = `kpis.realizado_liquido` (verde se ≥0, vermelho se <0).
- **A realizar (previsto)** = `kpis.previsto_liquido`.
- **Saldo projetado** = `fluxo.saldo_final_projetado` (fonte única, do service); card
  vira vermelho + ícone de alerta quando `< 0` (mantém a semântica de `fluxo.alerta`).

### 4.2 Gráfico (dores #1 e #4)
Chart.js misto: dois datasets de barra (entradas, saídas) + um dataset de linha
(saldo acumulado) em eixo secundário. Dados vêm de `serie_chart` (JSON). Se houver só
um mês no período, degrada para um grupo de barras — limitação conhecida e aceita no v1.

### 4.3 Tabela mensal + drill-down (dores #2 e #1)
- Uma linha por mês com os subtotais. Linha colorida pelo sinal de `saldo_mes`.
- Botão expande um `collapse` com os `movimentos` daquele mês, reaproveitando o render
  de célula atual (incluindo `cell-editable` e o JS de edição inline já existente).
- Dentro do mês, ordenação por data; Realizado e Previsto distinguidos pelo badge de
  status que já existe (sem seção separada no v1).
- Todos os meses começam **fechados**.

## 5. Estados de borda
- **Período sem dados:** mantém o empty state atual ("Nenhum movimento encontrado" +
  botão criar).
- **Movimentos sem data:** bucket "Sem data" no fim da tabela; não entram no saldo
  acumulado do gráfico (mas entram nos KPIs).
- **Saldo negativo:** card projetado vermelho + alerta; linha de mês com saldo negativo
  em vermelho.
- **Performance:** ~1.600 linhas renderizadas dentro de `collapse` escondido é aceitável
  para ferramenta interna desktop. Se virar problema, pagina-se por mês depois (v2).

## 6. Verificação
1. **Teste unitário** de `agregar_fluxo_mensal` (função pura) em `tests/` — casos:
   meses múltiplos, saldo acumulado correto, separação realizado/previsto, bucket
   sem-data, lista vazia. (Primeiro teste unitário do módulo financeiro.)
2. **Render real** com o batch já no banco (jan–jun/2026): abrir a tela no período e
   conferir que os totais mensais somados batem com entradas R$ 1.166.042,55 / saídas
   R$ 1.504.202,39 (realizados do batch) e que o `saldo_acumulado` é internamente
   consistente (`saldo_inicial + Σ saldo_mes`). Não exigir que ele coincida com
   `saldo_final_projetado` — são métricas diferentes (ver §3.1).
3. Conferir que a edição inline e o modal "Nova Movimentação" continuam funcionando.

## 7. Fora de escopo (YAGNI)
- Sub-agrupamento por categoria dentro do mês.
- Toggle de granularidade (dia/semana/mês).
- Barras empilhadas realizado/previsto no gráfico.
- Exportação (PDF/Excel) da visão de fluxo.
- Mudanças em `calcular_fluxo_caixa` ou no esquema de dados.
