# Painel Financeiro da Obra (aba Financeiro) — Design

**Data:** 2026-06-24
**Autor:** Cássio Viller (com Claude Code)
**Status:** Aprovado para planejamento
**Referência visual:** `dashboard_baias (1).html` (raiz do projeto)
**Continuação de:** `2026-06-24-fisico-financeiro-caixa-medicoes-importacao-design.md`

## 1. Objetivo

Transformar a aba **Financeiro** de `templates/obras/detalhes_obra_profissional.html` (hoje
pares chave-valor simples, linhas 1521-1580) no **Painel Financeiro da Obra** no estilo do
`dashboard_baias`: KPIs, custo por etapa clicável/editável, Curva S com 4 séries (incluindo
**custo realizado ao longo do tempo**), doughnut Veks×Fat, caixa por mês e medições. Mais:
corrigir a semântica de **Verba Disponível = caixa (recebido − realizado)** no serviço
compartilhado, e surfaçar o **Mapa de Orçamentos** já existente.

Escopo aprovado: **Projetos 1+2+3 juntos** (painel + edição inline de itens + integração do mapa).

## 2. Decisões aprovadas

- **Onde:** dentro da aba `#tab-financeiro` da página da obra (`main.detalhes_obra`). A rota
  standalone `cronograma.fisico_financeiro` passa a **redirecionar** para `…/obras/<id>#tab-financeiro`.
- **Carregamento:** a aba carrega **sob demanda** (ao ser aberta) via endpoint JSON; gráficos
  renderizados no cliente com Chart.js (já global em `base_completo.html:27`). Mantém o load
  inicial da página leve.
- **Verba disponível = caixa:** `verba_disponivel = valor_recebido − total_realizado` no serviço
  compartilhado `resumo_custos_obra` (afeta todas as obras). Preserva a visão de margem num campo
  novo `saldo_orcamentario = contrato − custo_projetado`.
- **Custo realizado no tempo (4ª linha):** agrega `GestaoCustoFilho` por mês (fonte já existente,
  alimentada por RDO/diárias, empreitadas, compras, aluguel).
- **Edição inline** de itens de custo por etapa reaproveita a lógica de `planejamento_custos.editar`.
- **Mapa de Orçamentos:** já funcional na aba `#tab-mapa` (`MapaConcorrenciaV2`); esta entrega só
  adiciona card-resumo/link no painel + polimento leve. Reforma profunda = fora de escopo.

## 3. O que já existe (reusar, não recriar)

- **Wrappers FF** em `services/cronograma_fisico_financeiro.py`: `montar_fisico_financeiro`,
  `kpis(obra, dados)`, `fluxo_caixa(obra, dados)`, `medicoes_contrato(obra)`,
  `fluxo_caixa_divergencia(obra, dados)`.
- **`services/resumo_custos_obra.py`** — `calcular_resumo_obra(obra_id, admin_id)` (indicadores,
  grafico_barras, grafico_composicao). `verba_disponivel` hoje em `resumo_custos_obra.py:336`.
- **CRUD de custo por serviço** em `views/planejamento_custos_views.py` (`/obras/<obra_id>/
  planejamento-custos/...`: lista/novo/editar/excluir/cotacoes/equipe).
- **Mapa V2**: `MapaConcorrenciaV2`/`MapaFornecedor`/`MapaItemCotacao`/`MapaCotacao` + rotas em
  `views/obras.py` (`mapa-v2/criar|editar|deletar`) + aba `#tab-mapa` + `mapa_concorrencia_v2.html`.
- **`GestaoCustoFilho`** (`models.py`): `data_referencia` (Date), `valor`, `obra_id`,
  `obra_servico_custo_id`, `origem_tabela`; pai `GestaoCustoPai.tipo_categoria` (exclui
  `FATURAMENTO_DIRETO` para realizado).
- **Chart.js** global; `main.detalhes_obra` (`views/obras.py:1343`) já passa `obra`, `resumo`,
  `kpis`, `painel`, `mapas_v2`.

## 4. Componentes (unidades)

### 4.1 Serviço — `services/cronograma_fisico_financeiro.py`
- `curva_realizado(obra) -> {mes: Decimal}` — soma `GestaoCustoFilho.valor` por `YYYY-MM` de
  `data_referencia`, tenant-scoped, excluindo `FATURAMENTO_DIRETO`. Pura-ish (faz query; sem Flask).
- `realizado_por_etapa(obra) -> {obra_servico_custo_id: Decimal}` — soma realizada por etapa
  (via `GestaoCustoFilho.obra_servico_custo_id`).
- `painel_financeiro(obra) -> dict` — orquestrador que junta para o JSON do painel:
  `kpis`, `etapas` (com `previsto`, `veks`, `fat`, `realizado`), `curva_s` (4 séries:
  recebido_liquido, gasto_veks, lucro, realizado — acumuladas), `caixa`, `medicoes`,
  `doughnut {veks, fat}`, `divergencia`, `verba_disponivel`, `custo_realizado`.

### 4.2 Serviço — `services/resumo_custos_obra.py`
- `verba_disponivel = round(valor_recebido - total_realizado, 2)` (caixa).
- `saldo_orcamentario = round(total_proposta_orcada - custo_real_da_obra, 2)` (margem, novo).
- Adiciona `saldo_orcamentario` ao dict `indicadores` e ao `_resumo_vazio()`.

### 4.3 Rotas — `views/obras.py`
- `GET /obras/<int:id>/financeiro/dados` → JSON de `painel_financeiro(obra)` (tenant-scoped,
  `@login_required`). Datas como ISO/strings, Decimais como float na fronteira JSON.
- `POST /obras/<int:id>/financeiro/etapa/<int:osc_id>` → atualiza `ObraServicoCusto`
  (veks→`mao_obra_a_realizar`, fat→`material_a_realizar`, `valor_orcado`), recalcula e devolve
  o JSON atualizado. Reusa a validação de `planejamento_custos`.
- Redirect: `cronograma.fisico_financeiro` (`cronograma_views.py:2533`) → `redirect(url_for(
  'main.detalhes_obra', id=obra_id) + '#tab-financeiro')`.

### 4.4 Template — `templates/obras/detalhes_obra_profissional.html`
Substitui o conteúdo de `#tab-financeiro` (1521-1580) por: faixa de KPIs · `<canvas>` custo por
etapa + `<div>` drill-down · `<canvas>` Curva S · `<canvas>` doughnut · `<canvas>` caixa ·
tabela de medições + alerta Indiretos · card-link para o Mapa (`#tab-mapa`).

### 4.5 Front — `static/js/financeiro_obra.js`
No `shown.bs.tab` da aba Financeiro (1ª vez): `fetch('/obras/<id>/financeiro/dados')` → renderiza
os 4 charts + KPIs + medições. Clique numa etapa → drill-down com itens editáveis (inputs) →
`POST …/financeiro/etapa/<osc_id>` → re-render. Formatação BR (R$, datas).

## 5. Fluxo de dados

```
abre aba Financeiro
   └─ JS fetch GET /obras/<id>/financeiro/dados
        └─ painel_financeiro(obra):
             montar_fisico_financeiro ─┬─ kpis, etapas(previsto/veks/fat), caixa, curva custo
             curva_realizado ──────────┼─ série realizado (GestaoCustoFilho por mês)
             realizado_por_etapa ──────┼─ realizado por etapa
             medicoes_contrato ────────┼─ medições
             resumo_custos_obra ───────┴─ recebido, verba_disponivel(caixa)
        → JSON → Chart.js (KPIs, etapas, Curva S 4 séries, doughnut, caixa) + tabelas
   editar item → POST /obras/<id>/financeiro/etapa/<osc_id> → recalc → JSON → re-render
```

## 6. Erros / bordas

- Obra sem custo/cronograma → painel com *empty state* (KPIs zerados, gráficos vazios), sem erro.
- `GestaoCustoFilho` sem lançamentos → série realizado toda zero (linha cresce a partir de 0).
- `valor_contrato = 0` → percentuais protegidos contra divisão por zero.
- Edição: `osc_id` deve pertencer à obra+tenant (`first_or_404` por `obra_id`/`admin_id`); valores
  inválidos → 400 com mensagem; recalcula só após commit.
- JSON: `Decimal`→`float` só na serialização; datas→`'YYYY-MM-DD'`.
- Multitenant: toda query escopada por `admin_id` da obra.

## 7. Invariantes / testes

- `curva_realizado`: soma por mês == soma de `GestaoCustoFilho` (excl. FAT_DIRETO) da obra;
  meses ordenados.
- `verba_disponivel == valor_recebido − total_realizado`; `saldo_orcamentario == contrato − custo_real`.
- `painel_financeiro`: chaves presentes; `curva_s` tem 4 séries de mesmo comprimento; etapas com
  `realizado` ≥ 0.
- Endpoint `financeiro/dados`: 200 autenticado, JSON com as chaves; isolamento multitenant.
- Edição: `POST` altera o OSC e o JSON de retorno reflete; tenant não edita OSC de outra obra.
- Render: aba Financeiro carrega (smoke), canvases presentes.

## 8. Fora de escopo (YAGNI)

- Reforma profunda do Mapa de Orçamentos (só surfaçar/polir).
- EVM/SPI/CPI, Curva S física, Gantt.
- Faseamento do realizado por dias úteis (realizado é por mês de lançamento).
- Edição de medições/contrato (fixas).

## 9. Ponteiros

- Design FF base: `2026-06-24-fisico-financeiro-caixa-medicoes-importacao-design.md`.
- Referência visual/comportamento: `dashboard_baias (1).html`.
- Custo realizado: `GestaoCustoFilho` + `services/resumo_custos_obra.py`.
- Edição de custo: `views/planejamento_custos_views.py`.
