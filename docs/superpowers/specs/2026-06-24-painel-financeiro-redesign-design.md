# Design — Redesign do painel Financeiro da obra

**Data:** 2026-06-24
**Branch:** `feat/painel-financeiro-redesign`
**Arquivos:** `templates/obras/detalhes_obra_profissional.html` (aba `#tab-financeiro`),
`static/js/financeiro_obra.js`

## Problema

A aba **Financeiro** (página de detalhes da obra) está com a visualização "deformada":
os gráficos Chart.js usam `maintainAspectRatio:false` mas os `<canvas>` não estão
dentro de um container de altura fixa — só têm o atributo `height`. Nessa combinação
o Chart.js estica o canvas para preencher o pai sem altura definida, e ele cresce/
deforma (pior ao trocar de aba, quando o canvas renderiza com altura errada). Além
disso, os 9 KPIs ficam numa fileira solta sem hierarquia, e os blocos não têm um
agrupamento claro.

## Objetivo

Redesenho completo do painel: **consistente com o sistema** (cards Bootstrap
arredondados, fundo `#f8fafc`, verde/vermelho para sinal, ícones FontAwesome),
**visão equilibrada** (resumo enxuto no topo + blocos organizados), e **sem
deformação** (containers de altura fixa). Sem mudança de backend — os dados já
chegam prontos pelo endpoint `/obras/<id>/financeiro/dados`.

## Decisões (do usuário)

1. Escopo: **redesenho completo** (não só o bug).
2. Hierarquia: **visão equilibrada** — resumo no topo, blocos de peso parecido abaixo.
3. Estilo: **consistente com o sistema** (house style do SIGE).
4. KPIs: **manter os 9, agrupados** em Resultado / Caixa / Custo.
5. Layout: **A — Grade equilibrada** (sem navegação extra; tudo à vista).

## Estrutura visual (layout A)

### Topo — 3 cartões de grupo (row `g-3`, empilham no mobile)

Cada grupo é um card com cabeçalho (ícone + rótulo) e linhas `label … valor`
(valor alinhado à direita, `font-variant-numeric: tabular-nums`).

- **Resultado** (`fa-chart-line`): Venda, Custo total, Imposto, **Lucro projetado**
  (com margem % ao lado). Lucro recebe cor (verde ≥ 0 / vermelho < 0).
- **Caixa** (`fa-wallet`): Recebido até hoje, **Verba disponível** (verde/vermelho).
- **Custo** (`fa-coins`): Desembolso Veks, Faturamento direto, Custo realizado.

### Blocos (grade responsiva, abaixo dos grupos)

1. **Custo por etapa** — card largura cheia; barras horizontais empilhadas (Veks+Fat);
   clique numa barra abre a **edição inline** (comportamento atual preservado,
   incluindo `X-CSRFToken` no POST e o estado "edição indisponível" para etapa
   multi-OSC).
2. **Row:** Curva S (`col-lg-8`) + Doughnut Veks×Fat (`col-lg-4`).
3. **Row:** Caixa final por mês (`col-lg-6`) + Medições de contrato (tabela, `col-lg-6`).
4. **Alerta de divergência dos Indiretos** — faixa (`alert-warning`) só quando
   `|Δveks| > 1` (regra atual em `renderAlerta`).
5. **CTA Mapa de Orçamentos** — mantido como está.

## Correção da deformação (técnico)

Cada `<canvas>` passa a viver num wrapper de **altura fixa** com posição relativa:

```html
<div class="fin-chart" style="position:relative; height:340px">
  <canvas id="finEtapas"></canvas>
</div>
```

- Remover o atributo `height=...` dos `<canvas>` (a altura passa a vir do wrapper).
- Manter `maintainAspectRatio:false` no JS (agora preenche o wrapper travado).
- Alturas por bloco: **Custo por etapa ~360px**, **Curva S / Doughnut ~300px**,
  **Caixa ~280px**. A tabela de Medições ganha um container com `max-height`
  equivalente e `overflow:auto` para casar a altura do bloco vizinho.
- Os charts já são construídos quando a aba fica visível (`load()` em
  `shown.bs.tab`), então renderizam com a altura correta. Nenhuma chamada extra
  de resize é necessária; se no futuro a aba reabrir, `render()` destrói e recria
  os charts (já é o comportamento atual).

## Mudanças no JS (`financeiro_obra.js`)

- `renderKPIs(k)` reescrito: em vez de uma fileira de 8 cards, monta **3 cards de
  grupo** com listas `label/valor`. Mantém o helper `BRL`. Mantém os mesmos campos
  do payload (`venda`, `custo_total`, `imposto`, `lucro_projetado`, `lucro_pct`,
  `recebido_ate_hoje`, `verba_disponivel`, `desembolso_veks`, `fat_direto`,
  `custo_realizado`).
- `buildCharts(p)` inalterado na lógica dos datasets; só não depende mais do
  atributo `height` do canvas (o wrapper define a altura).
- `csrfToken()`, `showEtapa()`, `renderMedicoes()`, `renderAlerta()`, `load()`,
  `render()` permanecem com a mesma lógica.

## Escopo de arquivos

- `templates/obras/detalhes_obra_profissional.html` — markup da aba `#tab-financeiro`
  (containers dos grupos de KPI + wrappers `.fin-chart`).
- `static/js/financeiro_obra.js` — `renderKPIs` agrupado; render dos charts sem
  depender de `height` no canvas.
- **Sem mudança de backend, endpoint ou modelo.**

## Não-objetivos (YAGNI)

- Não mudar a fonte/paleta global do sistema.
- Não adicionar navegação interna (sub-abas) — abordagem A é grade direta.
- Não alterar cálculo de KPIs/dados (já corrigidos em PRs anteriores).
- Não mexer nas outras abas da página da obra.

## Testes

- **Preservar verdes** os smokes atuais: `test_pagina_obra_tem_aba_financeiro_e_endpoint`,
  `test_endpoint_financeiro_dados*`, `test_obras_id_serve_pagina_nao_json` e demais
  de `tests/test_painel_financeiro.py` (a aba e o endpoint não mudam de contrato).
- **Novo smoke de template:** renderizar a página da obra (autenticado, v2) e
  conferir que a aba contém os 3 grupos de KPI (rótulos "Resultado", "Caixa",
  "Custo") e ao menos um wrapper `class="fin-chart"` por canvas
  (`finEtapas`, `finCurva`, `finSplit`, `finCaixa`).
- Verificação manual: abrir a obra Baias (codigo 10, tenant Alfa), conferir que os
  gráficos não esticam e que a edição inline ainda salva.

## Riscos

- **Baixo.** Mudança só de apresentação. O principal risco é regressão visual em
  telas estreitas — mitigado mantendo a grade Bootstrap (`col-lg-*` → full no mobile)
  e alturas fixas nos wrappers.
