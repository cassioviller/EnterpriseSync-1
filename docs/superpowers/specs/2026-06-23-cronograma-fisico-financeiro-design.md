# Cronograma Físico-Financeiro (derivado) — Design

**Data:** 2026-06-23
**Autor:** Cássio Viller (com Claude Code)
**Status:** Aprovado para planejamento
**Abordagem:** A — Derivado (sem segunda fonte de verdade de custo)

## 1. Objetivo

Dar ao cronograma do SIGE a capacidade de **cronograma físico-financeiro**, equivalente
à planilha `Previsao_Cronograma_e_Orcamentos.xlsx` (aba "Cronograma FF por etapa"):

1. **Custo planejado por etapa/tarefa** (material/M.O./outros).
2. **Faseamento mensal + Curva S de custo** (a partir das datas das tarefas).
3. **Split Veks × Faturamento Direto** (empresa desembolsa vs. cliente paga o fornecedor).
4. **Realizado vs. previsto por etapa** (desvio).
5. **Export XLSX** no layout da planilha (item firme).

Tudo **derivado** do que já existe; a única gravação nova é a classificação Veks/Fat.

## 2. O que já existe (não recriar)

- **`ObraServicoCusto`** (`models.py:5563`) — custo por serviço da obra:
  `valor_orcado` (baseline), `realizado_{material,mao_obra,outros}`,
  `{material,mao_obra,outros}_a_realizar`, propriedades `realizado_total`,
  `a_realizar_total`, `saldo`. Ligado 1:1 a `ItemMedicaoComercial` via
  `item_medicao_comercial_id`, e ao catálogo via `servico_catalogo_id`.
- **`ItemMedicaoCronogramaTarefa`** (`models.py:5217`) — `peso` (por horas) ligando
  IMC ↔ `TarefaCronograma`. Já distribui valor do item entre tarefas (usado na medição).
- **`TarefaCronograma`** (`models.py:4835`) — `obra_id`, `servico_id`, `tarefa_pai_id`
  (hierarquia; nível 0 = raiz por serviço), `data_inicio`, `data_fim`, `duracao_dias`,
  `percentual_concluido`, `gerada_por_proposta_item_id`.
- **`CalendarioEmpresa`** + helpers de dias úteis em `utils/cronograma_engine.py`
  (`_is_dia_util`, `proximo_dia_util`, `calcular_data_fim`).
- **Cotações internas multi-fornecedor** (`ObraServicoCotacaoInterna`, `models.py:5691`)
  com seleção — já cobrem a aba 2 (Mapa de Orçamentos). **Fora de escopo** desta entrega.

A cadeia de ligação custo→tarefa (já existente):
`ObraServicoCusto.item_medicao_comercial_id → ItemMedicaoComercial → (ItemMedicaoCronogramaTarefa.peso) → TarefaCronograma`.

## 3. Definições (decisões aprovadas)

- **Etapa** = nó raiz do cronograma (`TarefaCronograma` com `tarefa_pai_id IS NULL`,
  1 por serviço). Roll-up opcional por `Servico.categoria` para visão mais agregada
  (≈11 etapas da planilha).
- **Previsto** (custo esperado) por serviço = `realizado_total + a_realizar_total`, com
  split por categoria: `material = realizado_material + material_a_realizar`,
  idem `mao_obra` e `outros`. **Orçado** (`valor_orcado`) = baseline de desvio.
  **Realizado** = `realizado_total`.
- **Veks × Fat Direto** por **categoria de custo** (material/M.O./outros independentes,
  pois material pode ser Fat e M.O. Veks). Persistência: **3 colunas novas** em
  `ObraServicoCusto`: `fonte_material`, `fonte_mao_obra`, `fonte_outros` —
  enum `'veks' | 'fat_direto'`, default `'veks'`.
- **Indiretos/gestão** (escritório, empréstimo, refeição…) **não** vêm do cronograma
  (são BDI/overhead, não tarefa) → ficam **fora do faseamento** nesta versão; mostrados
  como nota. (Linha manual extra = trabalho futuro.)

## 4. Componentes (unidades isoladas)

### 4.1 Migração aditiva
3 colunas em `ObraServicoCusto` (`fonte_material`, `fonte_mao_obra`, `fonte_outros`,
default `'veks'`, NOT NULL). Segue o padrão de migração já usado pelo app (numbered
migration em `migrations.py`, idempotente, rodada no boot). Não altera dados existentes
além do default.

### 4.2 Serviço de cálculo — `services/cronograma_fisico_financeiro.py` (novo)
Função pública: `montar_fisico_financeiro(obra_id, admin_id) -> dict`.
Retorna estrutura pronta para a view e o export:
```
{
  'etapas': [
     { 'etapa_id', 'nome', 'categoria',
       'previsto': {'material','mao_obra','outros','total'},
       'veks': Decimal, 'fat_direto': Decimal,
       'orcado': Decimal, 'realizado': Decimal, 'desvio': Decimal,
       'meses': { 'YYYY-MM': Decimal, ... } },          # custo previsto faseado
     ...
  ],
  'meses_ordenados': ['YYYY-MM', ...],
  'totais': {'veks','fat_direto','total','previsto','orcado','realizado'},
  'curva_s': [ {'mes','custo_mes','acumulado','pct_acumulado'}, ... ],
  'nao_faseado': Decimal,        # custo de tarefas sem datas
  'avisos': [str, ...],          # serviços sem ObraServicoCusto, etc.
}
```
Funções internas puras (testáveis isoladamente):
- `_alocar_custo_por_tarefa(obra_servico_custo, pesos)` — distribui o custo do serviço
  às tarefas-folha proporcional ao `peso` do `ItemMedicaoCronogramaTarefa`
  (normalizado; fallback peso igual se Σpeso=0). **Conserva o total.**
- `_fasear_por_dias_uteis(valor, data_inicio, data_fim, calendario)` — distribui `valor`
  uniformemente pelos dias úteis no intervalo, agregando por mês (`YYYY-MM`). Tarefa sem
  datas → bucket `nao_faseado`.
- `_classificar_veks_fat(osc)` — soma material/M.O./outros em Veks vs Fat conforme as
  3 colunas novas.
- `_curva_s(meses)` — acumula custo por mês → `{custo_mes, acumulado, pct_acumulado}`.

### 4.3 Rota — `cronograma_views.py`
`GET /cronograma/obra/<int:obra_id>/fisico-financeiro` → chama o serviço, renderiza o
template. Guard de `admin_id`/tenant como nas demais rotas de cronograma.
`GET /cronograma/obra/<int:obra_id>/fisico-financeiro/export.xlsx` → gera o XLSX.

### 4.4 Template (novo)
Tabela espelhando a planilha: **Etapa | Veks | Fat Direto | Total | % | <mês…> |**,
linhas por etapa (e sub-linhas material/M.O./outros opcionais), rodapé com totais, e a
**Curva S** (tabela mês · custo · acumulado · % e, se viável, um gráfico simples).
Inclui *empty state* e a nota de indiretos.

### 4.5 Export XLSX (firme) — `services/cronograma_fisico_financeiro.py` ou `exportacao_relatorios`
`exportar_fisico_financeiro_xlsx(dados) -> bytes/openpyxl.Workbook` reproduzindo o layout
da planilha (aba "Cronograma FF por etapa" + aba "Curva S"). Reaproveita `openpyxl`
(já é dependência). Servido pela rota `export.xlsx`.

## 5. Fluxo de dados

```
ObraServicoCusto (custo + fonte_*)            CalendarioEmpresa (dias úteis)
        │ (item_medicao_comercial_id)                    │
        ▼                                                │
ItemMedicaoComercial ──(ItemMedicaoCronogramaTarefa.peso)─▶ TarefaCronograma (datas)
        │                                                            │
        └──────────── _alocar_custo_por_tarefa ──────────▶ custo por tarefa
                                                                     │
                                            _fasear_por_dias_uteis ──┘
                                                                     ▼
                            agregação por ETAPA (nó raiz) + buckets mensais + _curva_s
                                                                     ▼
                                         view HTML  /  export XLSX
```

## 6. Tratamento de erros / casos de borda

- Tarefa sem `data_inicio`/`data_fim` → custo no bucket `nao_faseado` (visível) + aviso.
- Serviço sem `ObraServicoCusto` correspondente → etapa com previsto 0 + aviso.
- Obra sem cronograma materializado ou sem pesos → *empty state* explicando o que falta
  (materializar via aprovação da proposta / datar tarefas).
- Σpeso = 0 num IMC → fallback peso igual entre folhas (espelha `materializar_cronograma`).
- Decimais com `Decimal`; arredondamento só na apresentação.

## 7. Invariantes / testes

- **Conservação:** `Σ(meses) + nao_faseado == Σ(previsto das etapas)` (tolerância de
  centavos).
- **Veks/Fat:** `veks + fat_direto == previsto.total` por etapa e no total.
- **Curva S:** monotônica não-decrescente; `pct_acumulado` final == 1.0 (quando há custo).
- **Faseamento:** tarefa cruzando 2 meses divide proporcional aos **dias úteis** em cada
  mês.
- Unit tests do serviço (funções puras) + 1 smoke Playwright da página
  `/cronograma/obra/<id>/fisico-financeiro` (carrega, mostra etapas/curva, baixa XLSX).

## 8. Fora de escopo (YAGNI)

- Faseamento do **realizado** no tempo (comparação realizado×previsto é por **total de
  etapa**, não mês a mês).
- **Indiretos/gestão** faseados ou como linha editável.
- **Edição** de custo por etapa direto no cronograma (seria a abordagem B).
- Cotações / Mapa de Orçamentos (já modelado em `ObraServicoCotacaoInterna`).

## 9. Ponteiros

- Arquitetura do triângulo orçamento↔proposta↔cronograma↔medição: ver mapas de
  `CONTEXTO_orcamento_baia_rev10.md` e `ESTUDO_cronograma_baia_rev10.md`.
- BDI/preço: `ADR-0001`, `services/pricing.py`.
- Origem do custo da obra: `ObraServicoCusto` + `gestao_custos_views.py`.
