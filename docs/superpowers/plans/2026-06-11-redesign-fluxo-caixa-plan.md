# Plano de Implementação — Redesenho do Dashboard de Fluxo de Caixa

**Spec:** `docs/superpowers/specs/2026-06-11-redesign-fluxo-caixa-design.md`
**ADR:** `docs/adr/0003-fluxo-caixa-variacao-relativa-nao-saldo-absoluto.md`
**Data:** 2026-06-11 (revisado após grilling Q1–Q8)
**Estratégia:** passos pequenos, cada um verificável e commitável. Backend puro e
filtro primeiro (com testes), depois fiação da view, depois os blocos do template. A
tela continua funcionando após cada passo.

## Contexto confirmado (do código)
- `calcular_fluxo_caixa(admin_id, data_inicio, data_fim)` — `financeiro_service.py:430`.
  Itens de `detalhes`: `data`(date|None), `tipo`('ENTRADA'|'SAIDA'), `descricao`,
  `valor`(float), `origem`, `status`, `realizado`(bool), `editavel?`, `id?`.
- View `fluxo_caixa` — `financeiro_views.py:679`. Hoje passa selects de obra/centro/tipo
  mas **nenhum filtra** o resultado.
- Cobertura obra/centro: `ContaReceber.obra_id` ✓ (sem centro); `FluxoCaixa.obra_id` +
  `centro_custo_id` ✓; `GestaoCustoPai` **sem** obra/centro → só via `GestaoCustoFilho`
  (`obra_id`, `centro_custo_id`); relação `GestaoCustoPai.itens`.
- Chart.js local (`static/js/vendor/chart.js`); filtro Jinja `brl` (`app.py:221`).

---

## Passo 1 — Filtro de Obra em `calcular_fluxo_caixa` + teste (Q5/Q6/Q8)

**Arquivo:** `financeiro_service.py` (`calcular_fluxo_caixa`), `tests/test_fluxo_obra.py`.

1.1 Adicionar param `obra_id: int = None`. Quando setado, filtrar:
   - `contas_receber`: `+ .filter(ContaReceber.obra_id == obra_id)`.
   - `pagamentos_realizados` e `fluxos_diretos` (FluxoCaixa): `+ FluxoCaixa.obra_id == obra_id`.
   - `custos_v2_previstos` e `custos_v2_pagos` (GestaoCustoPai): `+ GestaoCustoPai.itens.any(
     GestaoCustoFilho.obra_id == obra_id)` — conta o **pai inteiro** (aproximação Q8;
     comentar a nota). `None`/0 = sem filtro.
1.2 Teste (`tests/test_fluxo_obra.py`, com `app_context`): criar 2 obras, lançamentos em
   cada; `calcular_fluxo_caixa(..., obra_id=A)` retorna só os da obra A em entradas e
   realizado; um GestaoCustoPai com filho na obra A entra, sem filho na A não entra.

**Verificação:** `pytest tests/test_fluxo_obra.py -q` verde; sem filtro, resultado igual
ao de hoje (não-regressão).
**Commit:** `feat(fluxo): filtro de obra em calcular_fluxo_caixa (+teste)`

---

## Passo 2 — Função pura `agregar_fluxo_mensal` + teste unitário (TDD)

**Arquivo:** `financeiro_service.py` (staticmethod), `tests/test_agregar_fluxo_mensal.py`.

2.1 Teste primeiro (sem servidor). Casos:
   - **Lista vazia** → `meses == []`, KPIs 0, `serie_chart` com listas vazias.
   - **Um mês** (1 entrada + 1 saída realizadas) → `entradas_real`/`saidas_real`/
     `saldo_mes_real` corretos; `variacao_acumulada == saldo_mes_real` (começa em 0).
   - **Dois meses** → `variacao_acumulada` do 2º = soma dos `saldo_mes_real`; meses
     ordenados por `mes`.
   - **Realizado × previsto** → item `realizado=False` entra em `previsto_liquido` (não
     em `*_real`); `var_acum_proj = var_acum_real + Σ previsto_liquido`.
   - **Bucket "sem data"** → item `data=None` vira mês `'sem-data'` ao fim;
     `variacao_acumulada None`; fora de `serie_chart`; dentro dos KPIs.
2.2 Implementar conforme spec §3.2: variação acumulada **de 0** (só realizado); rótulo
   pt-BR via mapa fixo `Jan..Dez` (sem `locale`); `serie_chart` com `entradas_real`,
   `saidas_real`, `var_acum_real`, `var_acum_proj`.

**Verificação:** `pytest tests/test_agregar_fluxo_mensal.py -q` verde.
**Commit:** `feat(fluxo): agregação mensal pura (variação acumulada) + teste`

---

## Passo 2.5 — Entradas recebidas no fluxo (achado da verificação) ✅ FEITO

Descoberto ao verificar o Passo 2 com dados reais: `calcular_fluxo_caixa` incluía as
saídas realizadas (`gestao_custo_pai`) mas **não** as entradas realizadas
(`FluxoCaixa` ENTRADA com `referencia_tabela='conta_receber'`) — R$ 1,17M recebidos
ficavam invisíveis, quebrando o propósito do redesenho. Adicionada a query simétrica
(respeita `obra_id`) + 1 teste de integração. Commit `91ead22`.

## Passo 3 — Fiar a view (Q6/Q7)

**Arquivo:** `financeiro_views.py:679-742`.

3.1 Passar `obra_id or None` a `calcular_fluxo_caixa`.
3.2 `agg = FinanceiroService.agregar_fluxo_mensal(fluxo['detalhes'], fluxo['saldo_inicial'])`;
   adicionar `meses=agg['meses']`, `kpis=agg['kpis']`, `serie_chart=agg['serie_chart']`.
3.3 **Remover** do contexto os dados de Centro de Custo e Tipo (e parar de buscar
   `centros_custo`). Manter `obras`, `bancos`, `categorias_fc`, `filtros` (sem
   centro/tipo), `fluxo`.

**Verificação:** `/financeiro/fluxo-caixa` renderiza sem erro; filtrar por obra muda os
números; novas variáveis disponíveis (ainda não consumidas pelo template).
**Commit:** `feat(fluxo): view filtra por obra e fornece série mensal/KPIs`

---

## Passo 4 — Template: filtros + KPIs (Q1/Q6/Q7)

**Arquivo:** `templates/financeiro/fluxo_caixa.html` (blocos Filtros ~72-126 e Resumo ~128-162).

4.1 Filtros: manter Período + Obra; **remover** selects de Centro de Custo e Tipo.
4.2 KPIs (4 cards): Saldo em banco (`kpis.saldo_banco`, com dica se 0) · Realizado no
   período (`kpis.realizado_liquido`, verde/vermelho) · A realizar
   (`kpis.previsto_liquido`) · Saldo projetado (`fluxo.saldo_final_projetado`, vermelho +
   alerta se `fluxo.alerta`).

**Verificação:** filtros enxutos; KPIs coerentes com a reconciliação.
**Commit:** `feat(fluxo): filtros enxutos + KPIs realizado/previsto`

---

## Passo 5 — Template: gráfico (Q3/Q4)

**Arquivo:** `fluxo_caixa.html` (novo bloco + `{% block scripts %}`).

5.1 `<canvas id="graficoFluxo">` num card.
5.2 Chart.js misto a partir de `{{ serie_chart|tojson }}`: barras `entradas_real`
   (verde) + `saidas_real` (vermelho) no eixo `y`; linha `var_acum_real` (azul sólida) +
   `var_acum_proj` (azul tracejada) no eixo `y1`. Tooltips R$ pt-BR. Guarda para
   `labels` vazio (não instanciar / mensagem).

**Verificação:** 6 grupos (jan–jun); duas linhas coincidem onde não há previsto; período
de 1 mês degrada sem quebrar.
**Commit:** `feat(fluxo): gráfico de variação acumulada (realizada + projetada)`

---

## Passo 6 — Template: tabela mensal + drill-down (Q2)

**Arquivo:** `fluxo_caixa.html` (bloco Tabela ~164-302) e init DataTables (~547-555).

6.1 Tabela-resumo de meses: **Mês ▾ · Entradas · Saídas · Saldo mês · Variação acumulada
   · Previsto líquido · nº · [expandir]** (4 primeiras = realizado). Linha colorida pelo
   sinal de `saldo_mes_real`.
6.2 Cada mês → `collapse` com sub-tabela de `mes.movimentos`, reusando o render de célula
   atual (`cell-editable`, `data-field`, `data-edit-url`, `data-id`, ícone lápis). Badge
   de status distingue Realizado/Previsto. Fechados por padrão. Bucket "Sem data" ao fim.
6.3 **Remover** o init do DataTable único; **manter** todo o JS de edição inline
   (`enterEdit`/`saveEdit`/`cancelEdit` + bindings em `DOMContentLoaded`, que pegam
   células dentro dos `collapse` por já estarem no DOM).
6.4 Manter empty state quando `meses` vazio.

**Verificação:** meses com subtotais corretos; expandir mostra lançamentos; **editar
inline** dentro de um mês salva (200 JSON) e atualiza a célula; modal "Nova
Movimentação" intacto.
**Commit:** `feat(fluxo): tabela mensal com drill-down e edição inline`

---

## Passo 7 — Verificação end-to-end e fechamento
7.1 `pytest tests/test_fluxo_obra.py tests/test_agregar_fluxo_mensal.py -q` verde.
7.2 Render real (jan–jun/2026, batch `veks2026_162255`): somatórios mensais batem com
   entradas R$ 1.166.042,55 / saídas R$ 1.504.202,39; variação acumulada consistente
   (de 0); filtro de Obra reduz os números corretamente; KPIs/gráfico/drill-down OK;
   edição inline e modal OK.
7.3 Revisão do diff; nenhuma regressão.

**Commit final (se necessário):** `fix(fluxo): ajustes pós-verificação`

---

## Riscos / atenção
- **Edição inline dentro de `collapse`:** células no DOM no load (só escondidas) → os
  listeners as alcançam. Validar no Passo 6.
- **Filtro de Obra aproximado em saídas previstas** (pai multi-obra superestima) — raro;
  comentar no código.
- **Performance:** ~1.600 `<tr>` escondidos — aceitável; paginar por mês = v2.
- **`serie_chart` vazio / 1 mês:** tratado no Passo 5.

## Fora de escopo (reafirmado)
Centro de Custo/Tipo na tela; obra exato em saídas previstas; sub-grupo por categoria;
toggle de granularidade; barras empilhadas; exportação; saldo bancário absoluto;
correção da quirk do `saldo_final_projetado`.
