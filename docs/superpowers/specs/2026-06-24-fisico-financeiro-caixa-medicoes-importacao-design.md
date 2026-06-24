# Físico-Financeiro: Fluxo de Caixa + Medições de Contrato + Importação Completa — Design

**Data:** 2026-06-24
**Autor:** Cássio Viller (com Claude Code)
**Status:** Aprovado para planejamento
**Abordagem:** A — Derivado (estende o design aprovado em `2026-06-23-cronograma-fisico-financeiro-design.md`; **sem** segunda fonte de verdade de custo, **sem** modelos `EtapaFisicoFinanceiro`/`ItemCusto`)
**Fonte do piloto:** `cronograma_fisico_financeiro_baias.json` (de `files.zip`, 24/06 11:03) — snapshot da aba **Planilha1** de `Planilha de Custos REV01 (1).xlsx` + `CRONOGRAMA 16.06 (1).mpp`.

## 1. Objetivo

Duas entregas, na mesma obra/página, **sem refatorar o que já existe**:

1. **Importação completa numa só ação (produção):** importar um arquivo (JSON) deixa a obra **inteira planejada** — cronograma (tarefas, datas, predecessoras), financeiro (custo por etapa, split Veks/Fat), a **vinculação atividade↔custo em cada etapa**, as **medições de contrato** e o **snapshot do fluxo de caixa**. Depois do import, o painel Físico-Financeiro abre pronto.
2. **Aba "Planilha1" no painel:** acrescentar ao painel já existente as **medições de contrato**, o **fluxo de caixa mensal** (verbatim da planilha **+** recalculado pelo cronograma, lado a lado com divergência) e o **alerta da inconsistência dos Indiretos**. Mais a linha de **KPIs** no topo.

## 2. O que já existe (não recriar / não refatorar)

- **Serviço derivado** `services/cronograma_fisico_financeiro.py` — já entrega custo por etapa, faseamento mensal por dias úteis, Curva S de custo, totais, não-faseado, avisos e export XLSX. **Será estendido** com funções puras novas (caixa, medições, divergência, KPIs).
- **View/Template** `cronograma_views.py` + `templates/cronograma/fisico_financeiro.html` — ganham seções novas.
- **Modelos existentes** reutilizados pelo importador (cadeia custo→tarefa do design 23/06):
  `Obra` (`codigo`, `valor_contrato` Float, `data_inicio`, `data_previsao_fim`, `cliente_id`),
  `TarefaCronograma` (`obra_id`, `admin_id`, `nome_tarefa`, `tarefa_pai_id`, `data_inicio`, `data_fim`, `duracao_dias`, `percentual_concluido`, `servico_id`),
  `ItemMedicaoComercial` (`obra_id`, `admin_id`, `nome`, `valor_comercial`),
  `ItemMedicaoCronogramaTarefa` (`item_medicao_id`, `cronograma_tarefa_id`, `peso`, `admin_id`),
  `ObraServicoCusto` (`valor_orcado`, `{material,mao_obra,outros}_a_realizar`, `realizado_*`, `fonte_{material,mao_obra,outros}` enum `'veks'|'fat_direto'`),
  `CalendarioEmpresa` (dias úteis).
- **`MedicaoObra`/`MedicaoObraItem`** — sistema de medição **por execução** (período, % executado, conta a receber). **NÃO é tocado** nesta entrega.

A base que **não** existe ainda: `services/importacao_fisico_financeiro.py` (havia só o plano `2026-06-24-importador-...md`, escrito sobre o `files (5).zip`; este design o substitui/atualiza).

## 3. Decisões aprovadas

- **Estender a base derivada.** Os modelos novos do prompt (`EtapaFisicoFinanceiro`/`ItemCusto`) ficam descartados; o JSON é só a fonte do piloto.
- **Medições de contrato = entidade nova fixa** (`MedicaoContrato`), separada de `MedicaoObra`. Valor = `pct × valor_contrato`, fixo pelo contrato.
- **Fluxo de caixa: guardar o snapshot verbatim** da Planilha1 **E** recalcular pelo cronograma; mostrar os dois com divergência.
- **Inconsistência dos Indiretos: só alerta** em v1 — Indiretos seguem **fora** do faseamento automático (como hoje); o painel mostra a divergência e os dois lucros, sem escolher silenciosamente. Toggle 3,5×5 meses = trabalho futuro.
- **YAGNI nesta iteração:** EVM (PV/EV/AC/SPI/CPI), Curva S **física**, Gantt — adiados.

## 4. Modelo de dados

### 4.1 `MedicaoContrato` (novo)
```
MedicaoContrato:
  id, obra_id (FK obra, CASCADE), admin_id (FK usuario)
  nome            String(120)        # "Entrada", "Medição 1", ...
  data            Date
  pct             Numeric(7,5)       # fração do valor_contrato (Σ = 1.0)
  recebido_no_mes String(8) null     # "jun", "jul" ... (rótulo do mês de caixa)
  obs             Text null
  ordem           Integer            # para ordenação estável
```
Propriedade `valor` (não persistida) = `Decimal(obra.valor_contrato) × pct`. Idempotência do importador por (`obra_id`, `admin_id`, `nome`).

### 4.2 Snapshot do fluxo de caixa (verbatim)
Bloco `fluxo_caixa_mensal` do JSON guardado **como JSON** por obra, para exibição "verbatim" e cálculo da divergência. Duas opções:
- **(Escolhida)** coluna nova `fluxo_caixa_planilha JSON null` em `Obra` — migração aditiva simples, 1:1 com a obra, sem tabela nova.
- (Alternativa rejeitada) tabela `FluxoCaixaSnapshot` — overhead desnecessário para 1 blob por obra.

### 4.3 Migrações (aditivas, idempotentes, no padrão do app)
1. `CREATE TABLE medicao_contrato` (+ índices `obra_id`, `admin_id`).
2. `ALTER TABLE obra ADD COLUMN fluxo_caixa_planilha` (JSON/Text). Default NULL; não altera dados existentes.

## 5. Importador — `services/importacao_fisico_financeiro.py` (novo)

Função pública `importar_fisico_financeiro(payload: dict, admin_id: int) -> dict` (idempotente, tenant-scoped). Retorna resumo (`obra_id`, contadores, avisos) para a UI.

**Mapa JSON → modelos** (reaproveita o mapeamento já validado do plano 24/06, com os ajustes desta entrega):

| JSON | Modelo | Regra |
|---|---|---|
| `obra` + `contrato` | `Obra` (find-or-create por `codigo`+`admin_id`) | `valor_contrato`=`valor_venda`; `data_inicio`=`contrato.data_inicio`; `data_previsao_fim`=`contrato.data_fim_cronograma`; `cliente_id`=Cliente por (`nome`,`admin_id`). |
| `eap[i]` (etapa) | 1 `TarefaCronograma` **raiz** (`tarefa_pai_id=None`, datas da etapa) + N **folhas** (1 por id em `cronograma.tarefas_mpp`, datas de `cronograma_tarefas`). Transversal/sem `tarefas_mpp` → 1 folha com datas da etapa. | **a vinculação de atividade em cada etapa.** |
| `eap[i]` | 1 `ItemMedicaoComercial` (`valor_comercial`=`round(peso_pct×valor_venda,2)`) | liga custo↔tarefa via o serviço derivado. |
| folha | 1 `ItemMedicaoCronogramaTarefa` (`peso=max(1, dias da folha)`) | faseia proporcional à duração. |
| `eap[i].custo` | 1 `ObraServicoCusto` (`item_medicao_comercial_id`=IMC) | `valor_orcado`=`custo.total`; `mao_obra_a_realizar`=`custo.veks`/`fonte_mao_obra='veks'`; `material_a_realizar`=`custo.fat_direto`/`fonte_material='fat_direto'`; `outros=0/'veks'`; `realizado_*=0`. Invariante `veks+fat=custo.total`. |
| `medicoes[]` | `MedicaoContrato` (1 por item) | `nome,data,pct,recebido_no_mes,obs`, `ordem=i`. **NÃO** cria `MedicaoObra`. |
| `fluxo_caixa_mensal` | `Obra.fluxo_caixa_planilha` | guardado verbatim. |
| `cronograma_tarefas[].predecessoras` | — (informativo) | as datas já vêm **resolvidas** no JSON; não recalculamos por dependência nesta entrega. Predecessoras ficam fora de escopo. |

**Idempotência:** re-import por mesma `codigo`+`admin_id` atualiza em vez de duplicar (upsert por chaves naturais; remove órfãos da obra antes de repopular as coleções derivadas). Tudo dentro de uma transação.

**Exposição em produção:** novo módulo de import "Cronograma Físico-Financeiro (JSON)" em `importacao_views.py` (upload do arquivo → `importar_fisico_financeiro` → redireciona para o painel da obra), no padrão dos demais importadores. (CLI/seed opcional para o piloto, reutilizando a mesma função.)

## 6. Serviço — funções puras novas em `cronograma_fisico_financeiro.py`

Sem dependência de Flask; testáveis com os números do JSON.

- `medicoes_contrato(obra) -> list[{nome, data, pct, valor, mes}]` — `valor = pct × valor_contrato`. Invariantes: `Σpct≈1`, `Σvalor≈valor_contrato`.
- `fluxo_caixa(obra) -> {meses: [...], linhas:{...}}` — por mês, aplicando as regras confirmadas na Planilha1:
  - `imposto[m] = (medicao[m] − fat_direto_do_período) × 0,135`
  - `entrada[m] = medicao[m] − fat_direto_do_período − imposto[m]`
  - `caixa_inicial[m] = caixa_final[m−1] + entrada[m]` (1º mês = `entrada`)
  - `caixa_final[m] = caixa_inicial[m] − gasto_veks[m]`
  - `gasto_veks[m]` = Veks faseado vindo do faseamento derivado (mês a mês).
  - `lucro_em_caixa = caixa_final[último mês]`.
- `fluxo_caixa_divergencia(obra) -> {por_mes:[...], resumo:{...}}` — compara `fluxo_caixa` recalculado × `Obra.fluxo_caixa_planilha` (verbatim), mês a mês; `resumo` traz a inconsistência dos Indiretos: `veks_etapas` (≈734.460) × `veks_mensal_planilha` (≈824.460), `delta` (≈90.000), e os **dois lucros** (em caixa ≈152.047 × por totais de etapa).
- `kpis(obra) -> {venda, custo_total, lucro_projetado, lucro_pct, desembolso_veks, fat_direto, recebido_ate_hoje}`.

## 7. UI — `templates/cronograma/fisico_financeiro.html` (estender)

Na mesma página, novas seções (Bootstrap 5 + Chart.js local já em uso):
- **KPIs** no topo (cartões): venda, custo total, lucro projetado (% venda), desembolso Veks, fat direto, recebido até hoje.
- **Curva S de custo** — já existe (mantida).
- **Medições de contrato** — tabela `nome · data · % · valor · mês`.
- **Fluxo de caixa mensal** — tabela mês a mês (medição, fat direto, imposto, entrada líquida, caixa inicial/final) do **recalculado**, com coluna/realce de **divergência** vs. planilha verbatim.
- **Alerta dos Indiretos** — banner com a divergência (Δ ≈90k) e os dois lucros; texto explicando a decisão pendente (3,5 vs 5 meses), sem alterar números.

Tudo em pt-BR, formato monetário BR.

## 8. Fluxo de dados

```
IMPORT (1 ação)                                  PAINEL (derivado, sempre consistente)
 JSON ──▶ importar_fisico_financeiro             ObraServicoCusto + TarefaCronograma + IMCT
   ├─ Obra/Cliente                                        │ (faseamento por dias úteis)
   ├─ TarefaCronograma raiz+folhas  ─────────────▶  montar_fisico_financeiro → etapas, Curva S custo
   ├─ IMC + ItemMedicaoCronogramaTarefa(peso)             │
   ├─ ObraServicoCusto (veks/fat + fonte_*)        gasto_veks mensal ─┐
   ├─ MedicaoContrato (pct×venda)  ─────────────▶  medicoes_contrato ─┤
   └─ Obra.fluxo_caixa_planilha (verbatim) ──┐                        ▼
                                             │                  fluxo_caixa (regra fat direto)
                                             └──▶ fluxo_caixa_divergencia (recalc × verbatim, Indiretos)
                                                                       ▼
                                                        KPIs + tabelas + alerta no template
```

## 9. Erros / casos de borda

- Obra sem cronograma/custo materializado → *empty state* (já existe) + KPIs zerados.
- `valor_contrato = 0` → medições com valor 0 + aviso (evita divisão por zero em %).
- Medição sem `recebido_no_mes` → derivar o mês da `data`.
- `fluxo_caixa_planilha` ausente (obra não importada por JSON) → esconder a coluna de divergência; mostrar só o recalculado.
- Re-import → upsert idempotente, sem duplicar tarefas/itens/medições; transação única (rollback em erro).
- Decimais em `Decimal`; arredondamento só na apresentação.

## 10. Invariantes / testes

- **Importador (integração):** após import do JSON, a obra tem 12 etapas-raiz, 43 folhas, 6 `MedicaoContrato` (Σpct=1, Σvalor=valor_contrato), `fluxo_caixa_planilha` preenchido; re-import não duplica; isolamento multitenant (obra A não enxerga B).
- **`fluxo_caixa` (unit, números do JSON):** regra do fat direto e caixa rolante → **lucro em caixa ≈ 152.047**; `caixa_final[jun] ≈ 132.523`.
- **`medicoes_contrato`:** Σpct = 1.0; Σvalor = `valor_contrato` (tolerância de centavos).
- **`fluxo_caixa_divergencia`:** `delta` Veks ≈ 90.000; expõe os dois lucros.
- **Conservação (já no design 23/06):** `Σ(meses) + nao_faseado == Σ(previsto)`; `veks + fat == previsto.total`.
- **Smoke (browser):** página `/cronograma/obra/<id>/fisico-financeiro` carrega com KPIs, medições, fluxo de caixa e alerta.

## 11. Fora de escopo (YAGNI)

- Refator de `MedicaoObra`/`MedicaoObraItem`.
- Toggle 3,5×5 meses dos Indiretos (faseamento de transversais).
- EVM (PV/EV/AC/SPI/CPI), Curva S **física**, Gantt/timeline.
- Faseamento do **realizado** no tempo.
- Modelos `EtapaFisicoFinanceiro`/`ItemCusto` (descartados).
- Cotações / Mapa de Orçamentos (já em `ObraServicoCotacaoInterna`).

## 12. Ponteiros

- Design base: `docs/superpowers/specs/2026-06-23-cronograma-fisico-financeiro-design.md`.
- Plano anterior (a substituir/atualizar): `docs/superpowers/plans/2026-06-24-importador-e-dashboard-fisico-financeiro.md`.
- Serviço derivado: `services/cronograma_fisico_financeiro.py`.
- Fonte do piloto: `Planilha de Custos REV01 (1).xlsx` (aba Planilha1) + `CRONOGRAMA 16.06 (1).mpp` → `cronograma_fisico_financeiro_baias.json`.
