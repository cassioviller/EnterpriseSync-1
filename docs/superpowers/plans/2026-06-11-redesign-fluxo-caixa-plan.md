# Plano de Implementação — Redesenho do Dashboard de Fluxo de Caixa

**Spec:** `docs/superpowers/specs/2026-06-11-redesign-fluxo-caixa-design.md`
**Data:** 2026-06-11
**Estratégia:** passos pequenos, cada um verificável e commitável de forma independente.
A função pura entra primeiro (com teste), depois a fiação da view, depois os 4 blocos
do template um a um. A tela continua funcionando após cada passo.

## Pré-condições / contexto confirmado
- `FinanceiroService.calcular_fluxo_caixa(admin_id, data_inicio, data_fim)` devolve
  `{saldo_inicial, entradas_previstas, saidas_previstas, saldo_final_projetado,
  detalhes, alerta}`. Cada item de `detalhes`: `data`(date|None), `tipo`('ENTRADA'|
  'SAIDA'), `descricao`, `valor`(float), `origem`, `status`, `realizado`(bool),
  `editavel`(bool, opcional), `id`(opcional). — `financeiro_service.py:430-625`
- View `financeiro_views.fluxo_caixa` — `financeiro_views.py:679-742`. Monta `filtros`,
  `obras`, `centros_custo`, `bancos`, `categorias_fc` e renderiza
  `templates/financeiro/fluxo_caixa.html`.
- **Gap pré-existente (fora de escopo):** os filtros `obra_id`/`centro_custo_id`/
  `tipo_movimento` são exibidos e repassados ao template, mas **não filtram** o
  resultado de `calcular_fluxo_caixa`. Não corrigir neste trabalho; apenas não
  introduzir regressão.
- Chart.js já carregado: `static/js/vendor/chart.js` via `base_completo.html`.
- Filtro Jinja `brl` existe (`app.py:221`).

---

## Passo 1 — Função pura `agregar_fluxo_mensal` + teste unitário (TDD)

**Arquivo:** `financeiro_service.py` (nova staticmethod em `FinanceiroService`),
`tests/test_agregar_fluxo_mensal.py` (novo).

1.1 Escrever o teste primeiro (`tests/test_agregar_fluxo_mensal.py`), sem servidor —
importa só a função pura. Casos:
   - **Lista vazia** → `meses == []`, `kpis` todos 0, `serie_chart` com listas vazias.
   - **Um mês, 1 entrada + 1 saída** → `entradas`, `saidas`, `saldo_mes` corretos;
     `saldo_acumulado == saldo_inicial + saldo_mes`.
   - **Dois meses** → `saldo_acumulado` do 2º mês = `saldo_inicial + saldo_mes[0] +
     saldo_mes[1]`; `meses` ordenados por chave `mes`.
   - **Realizado × previsto** → item `realizado=True` soma em `realizado_*`,
     `realizado=False` em `previsto_*`; `kpis.realizado_liquido` /
     `kpis.previsto_liquido` corretos.
   - **Bucket sem data** → item com `data=None` cai num mês `{'mes':'sem-data',
     'label':'Sem data'}` ao fim; não entra em `serie_chart`; entra nos KPIs.

1.2 Implementar `agregar_fluxo_mensal(detalhes, saldo_inicial)` conforme §3.1 da spec.
   Pura: sem query, sem `Decimal` (recebe floats), sem efeitos. Rótulo pt-BR do mês via
   mapa fixo de 3 letras (`Jan`..`Dez`) — não usar `locale` (não confiável no ambiente).
   `saldo_acumulado` calculado só sobre meses com data, na ordem cronológica.

1.3 `kpis` = `{saldo_banco: saldo_inicial, realizado_liquido, previsto_liquido}`
   (sem `saldo_projetado` — o card usa `fluxo.saldo_final_projetado`, ver spec §3.1).

**Verificação:** `pytest tests/test_agregar_fluxo_mensal.py -q` passa (5 casos verdes).
**Commit:** `feat(fluxo): agregação mensal pura + teste unitário`

---

## Passo 2 — Fiar a view

**Arquivo:** `financeiro_views.py:723-742`.

2.1 Após `fluxo = FinanceiroService.calcular_fluxo_caixa(...)`, chamar
   `agg = FinanceiroService.agregar_fluxo_mensal(fluxo['detalhes'], fluxo['saldo_inicial'])`.

2.2 Adicionar ao `render_template`: `meses=agg['meses']`, `kpis=agg['kpis']`,
   `serie_chart=agg['serie_chart']`. Manter tudo que já é passado (não remover `fluxo`,
   `filtros` etc. — o template ainda os usa até o Passo 5).

**Verificação:** abrir `/financeiro/fluxo-caixa` no período jan–jun/2026; a tela
renderiza igual a hoje (ainda não consumimos as novas variáveis). Sem erro 500.
**Commit:** `feat(fluxo): view passa série mensal e KPIs ao template`

---

## Passo 3 — Bloco KPIs (4 cards)

**Arquivo:** `templates/financeiro/fluxo_caixa.html` (bloco "Resumo", ~linhas 128-162).

3.1 Substituir os 4 cards atuais por:
   - **Saldo em banco** = `kpis.saldo_banco|brl`.
   - **Realizado no período** = `kpis.realizado_liquido|brl` (classe verde se ≥0,
     vermelha se <0).
   - **A realizar (previsto)** = `kpis.previsto_liquido|brl`.
   - **Saldo projetado** = `fluxo.saldo_final_projetado|brl`; card vermelho + ícone
     alerta quando `fluxo.alerta` (ou `< 0`).
   - Seguir cores/badges do `DESIGN.md`; reusar a estrutura `card`/`card-body` atual.

**Verificação:** os 4 cards mostram valores coerentes com a reconciliação (realizado
líquido ≈ 1.166.042,55 − 1.504.202,39 no período total do batch).
**Commit:** `feat(fluxo): KPIs separando realizado de previsto`

---

## Passo 4 — Bloco do gráfico (Chart.js)

**Arquivo:** `templates/financeiro/fluxo_caixa.html` (novo bloco entre KPIs e tabela);
JS no `{% block scripts %}`.

4.1 Adicionar `<canvas id="graficoFluxo">` dentro de um `card`.

4.2 No script, ler `serie_chart` via `{{ serie_chart|tojson }}` e montar Chart.js misto:
   - dataset barra **Entradas** (verde `#198754`), dataset barra **Saídas**
     (vermelho `#dc3545`), ambos no eixo Y principal;
   - dataset linha **Saldo acumulado** (azul `#0d6efd`) no eixo Y secundário (`y1`);
   - tooltips formatando `pt-BR` (R$); legenda no topo.
   - Guardar contra `serie_chart.labels.length === 0` (não instanciar o chart; esconder
     o card ou mostrar "sem dados no período").

**Verificação:** gráfico aparece com 6 grupos (jan–jun), linha de saldo acumulado
crescente/decrescente coerente; um período de 1 mês degrada para 1 grupo sem quebrar.
**Commit:** `feat(fluxo): gráfico de entradas/saídas + saldo acumulado`

---

## Passo 5 — Tabela agrupada por mês + drill-down

**Arquivo:** `templates/financeiro/fluxo_caixa.html` (bloco "Tabela", ~linhas 164-302) e
o `{% block scripts %}` (init DataTables, ~linhas 547-555).

5.1 Trocar a tabela única por **uma tabela-resumo de meses**: colunas Mês ▾ · Entradas ·
   Saídas · Saldo mês · Saldo acumulado · nº · botão expandir. Iterar `meses`. Linha do
   mês com classe de cor pelo sinal de `saldo_mes`.

5.2 Cada linha-mês tem um `data-bs-toggle="collapse"` apontando para uma linha-detalhe
   (`<tr class="collapse">` com um `<td colspan>` contendo a sub-tabela dos
   `mes.movimentos`). Todos **fechados** por padrão.

5.3 A sub-tabela de movimentos reusa **exatamente** o render de célula atual (Data,
   Tipo, Status, Origem, Descrição, Valor) incluindo `cell-editable`, `data-field`,
   `data-edit-url`, `data-id` e os ícones de lápis — para a edição inline continuar
   funcionando sem mudar o JS de `saveEdit`/`enterEdit`.

5.4 **Remover o init do DataTable** (`#movimentosTable`) — o agrupamento server-side o
   substitui. Manter todo o JS de edição inline (`enterEdit`/`saveEdit`/`cancelEdit` e
   os bindings de `dblclick`/botões/teclas), que opera por `td.cell-editable` e
   independe do DataTable. Confirmar que os bindings em `DOMContentLoaded` pegam as
   células dentro dos `collapse` (estão no DOM desde o load, só escondidas → ok).

5.5 Manter o empty state atual quando `meses` vazio.

**Verificação:** meses listados com subtotais corretos; expandir um mês mostra os
lançamentos; **editar inline** data/valor/descrição de um lançamento dentro de um mês
salva e atualiza a célula (testar o fluxo `saveEdit` → 200 JSON). Modal "Nova
Movimentação" intacto.
**Commit:** `feat(fluxo): tabela agrupada por mês com drill-down e edição inline`

---

## Passo 6 — Verificação end-to-end e fechamento

6.1 Rodar a suíte de testes relevante (`pytest tests/test_agregar_fluxo_mensal.py -q`).
6.2 Render real (período jan–jun/2026, batch `veks2026_162255`): conferir
   - soma das Entradas mensais ≈ R$ 1.166.042,55, Saídas ≈ R$ 1.504.202,39;
   - `saldo_acumulado` internamente consistente (`saldo_inicial + Σ saldo_mes`);
   - KPIs, gráfico e drill-down coerentes; edição inline e modal OK.
6.3 Conferir período default (mês corrente) e período de 1 mês (gráfico degrada ok).
6.4 Revisão final do diff; nenhuma regressão nos filtros exibidos.

**Commit final (se necessário):** `fix(fluxo): ajustes pós-verificação do dashboard`

---

## Riscos / pontos de atenção
- **Edição inline dentro de `collapse`:** as células existem no DOM no load (só
  escondidas), então os listeners de `DOMContentLoaded` as alcançam. Validar no Passo 5.
- **Performance:** ~1.600 `<tr>` escondidos em `collapse`. Aceitável; se travar, paginar
  por mês fica para v2 (não fazer agora).
- **`serie_chart` vazio / 1 mês:** tratado no Passo 4.
- **Não tocar** em `calcular_fluxo_caixa`, esquema de dados, nem nos filtros não
  aplicados (gap pré-existente).

## Fora de escopo (reafirmado da spec)
Sub-grupo por categoria, toggle de granularidade, barras empilhadas realizado/previsto,
exportação, correção da quirk do `saldo_final_projetado`.
