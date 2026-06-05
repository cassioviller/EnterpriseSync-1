# Design — Bloco 3: BDI completo (padrão TCU) no orçamento

- **Data:** 2026-06-05
- **Status:** proposto (aguardando revisão)
- **Spec macro de origem:** `docs/superpowers/specs/2026-06-02-remediacao-auditoria-design.md` (achados D1, D2, D3)
- **ADR:** `docs/adr/0001-bdi-por-dentro-padrao-tcu.md` (status `accepted`)
- **Branch:** `fix/bloco3-bdi`. Sem push/merge/deploy até autorização explícita.

## Contexto

O cálculo atual (`services/orcamento_service.py`) usa um BDI degenerado
`preço = custo / (1 − T − L)` (só tributo e lucro no denominador), sem os
componentes de custo indireto. Três achados da auditoria:

- **D1** — BDI completo TCU (ADR 0001, `accepted`) não implementado; campos AC/S/R/G/DF inexistentes no schema.
- **D2** — `orcamento_service.py:344` exibe `lucro = preço − custo`, que embute o imposto (diverge de `L × preço`).
- **D3** — guarda-corpo só zera o preço em `T+L ≥ 100%` (silencioso); o preço dispara perto de 99% sem teto nem aviso.

A ADR 0001 já decidiu a **fórmula** e que **snapshots de propostas não são recalculados**. Este design fecha os pontos que a ADR deixou em aberto e a estratégia de implementação.

## Decisões (confirmadas no brainstorming 2026-06-05)

| Tema | Decisão |
|------|---------|
| Granularidade do BDI | **Um perfil de BDI por empresa**, com override opcional por proposta. (YAGNI na cascata item→global da ADR.) |
| Guarda-corpo (D3) | **Bloqueio em teto configurável + faixa de aviso** antes. |
| Exibição (D2) | **Split completo**: Custo direto + Indiretos (AC/S/R/G/DF) + Tributos + Lucro = Preço, nas telas internas. |
| Dados existentes | **Congelar antigos** (snapshots intactos); componentes de BDI começam em **0** → preço de catálogo não muda até preencher. |
| Estrutura de código | **Abordagem A** — helper de precificação centralizado; as 3 funções de cálculo delegam a ele. |

## Fórmula (ADR 0001)

```
indiretos = custo_direto × (AC + S + R + G + DF)/100
base      = custo_direto + indiretos            # = custo × (1 + ΣBDI)
preço     = base / (1 − (T + L)/100)
tributos  = preço × T/100
lucro     = preço × L/100                        # L "por dentro" (corrige D2)
```

Invariante verificável: `custo_direto + indiretos + tributos + lucro = preço`.
Quando `AC=S=R=G=DF=0`, a fórmula reduz a `custo / (1 − T − L)` — **idêntica
ao comportamento atual** (garantia de não-disrupção).

`T` = tributos por dentro (% do preço). `L` = lucro bruto por dentro (% do preço).

## Arquitetura

### 1. Schema (migração numerada, idempotente, aplicada no boot)

**`ConfiguracaoEmpresa`** (perfil de BDI da empresa) — colunas `Numeric(5,2)`:

| Coluna | Default | Significado |
|--------|---------|-------------|
| `bdi_ac_pct` | 0 | Administração Central |
| `bdi_seguro_pct` | 0 | Seguro |
| `bdi_risco_pct` | 0 | Risco |
| `bdi_garantia_pct` | 0 | Garantia |
| `bdi_desp_financeiras_pct` | 0 | Despesas Financeiras |
| `bdi_tl_aviso_pct` | 60 | T+L a partir do qual exibe aviso |
| `bdi_tl_bloqueio_pct` | 90 | T+L a partir do qual bloqueia |

**`Proposta`** — override opcional (mesmos 5 nomes de BDI, **nullable**;
`NULL` = herda da empresa).

`T` e `L` permanecem onde já estão: `Servico.imposto_pct` /
`Servico.margem_lucro_pct`, com fallback `ConfiguracaoEmpresa.imposto_pct_padrao`
/ `lucro_pct_padrao`.

Migração: `ADD COLUMN ... DEFAULT 0` (empresa) e `... NULL` (proposta);
linhas existentes ficam com BDI=0 → nenhum recálculo de preço.

### 2. Helper de precificação centralizado — `services/pricing.py`

Unidade isolada, sem dependência de template/HTTP, testável sozinha:

- `resolver_aliquotas(servico, proposta=None) -> Aliquotas`
  - Resolve `T, L` por `serviço → empresa → 0`.
  - Resolve `AC, S, R, G, DF` por `proposta (se não-nulo) → empresa → 0`.
  - Retorna um value-object só de leitura (dataclass) com os 7 Decimais.
- `precificar(custo_total: Decimal, aliquotas: Aliquotas) -> Precificacao`
  - Aplica a fórmula acima + guarda-corpo.
  - Retorna `custo_direto, indiretos, tributos, lucro, preco, soma_bdi_pct,
    tl_pct, status ('ok'|'aviso'|'bloqueio'), mensagem`.

As 3 funções existentes (`calcular_precos_servico`,
`calcular_precos_servico_por_quantidade`, `explodir_servico_para_quantidade`)
passam a (a) montar `custo_total` como hoje e (b) delegar a resolução de
alíquotas + fórmula ao helper. A lógica de cascata duplicada nas 3 é removida.

### 3. Guarda-corpo (D3)

Em `precificar`, com `tl = T + L`:
- `tl ≥ bdi_tl_bloqueio_pct` → `status='bloqueio'`, `preco = 0`,
  `mensagem='T+L ≥ {bloqueio}% — ajuste os percentuais'`. As camadas de
  escrita (recalcular/persistir, materializar item de proposta) **não gravam**
  preço em estado de bloqueio.
- `bdi_tl_aviso_pct ≤ tl < bdi_tl_bloqueio_pct` → `status='aviso'`, calcula
  normalmente, devolve `mensagem` de alerta para a UI.
- senão → `status='ok'`.

Substitui o atual zero-silencioso em `≥ 100%`.

### 4. Exibição (split completo — só telas internas)

Os dicts de retorno ganham `custo_direto, indiretos, indiretos_componentes
(AC/S/R/G/DF), tributos, lucro, preco, status, mensagem`. Telas internas
(detalhe de orçamento; visão interna da proposta) exibem a decomposição.
Superfícies do **cliente não mudam** — o guard test de não-vazamento
(`tests/test_proposta_no_leak.py`, Task #115) deve seguir verde.

UI:
- Config da empresa: 5 campos de BDI + 2 limiares do guarda-corpo.
- Proposta: seção opcional "BDI desta proposta" (5 campos; vazio = herda).

## Componentes e responsabilidades

| Unidade | Faz | Depende de |
|---------|-----|-----------|
| `services/pricing.py` | resolve alíquotas + aplica fórmula/guarda-corpo + breakdown | models (Servico, Proposta, ConfiguracaoEmpresa) |
| `orcamento_service.py` (3 funções) | monta custo da composição e delega ao helper | `pricing.py` |
| Migração (próximo número livre, ~#189) | adiciona colunas BDI (empresa/proposta) | engine de migração |
| Templates internos | mostram o split | dados do helper |
| Forms (empresa/proposta) | editam os percentuais | — |

## Tratamento de erros / casos de borda

- `T+L ≥ bloqueio` → `status='bloqueio'`, não persiste (ver §3).
- Alíquotas ausentes em todos os níveis → 0 (comportamento atual).
- `custo = 0` → preço 0, sem divisão inválida.
- Componentes BDI negativos: validação de form impede (≥ 0).
- Proposta sem override → herda empresa; empresa sem perfil → tudo 0.

## Testes

- **Tabela de fórmula:** casos com BDI=0 (== hoje), exemplo TCU conhecido,
  e verificação do invariante `custo+indiretos+tributos+lucro=preço`.
- **D2:** `lucro == L × preço` (não `preço − custo`).
- **D3:** as três faixas (ok / aviso / bloqueio) com os limiares default e
  customizados; bloqueio não persiste.
- **Regressão/não-disrupção:** serviço com BDI=0 → preço idêntico ao atual.
- **Cascata:** override de proposta tem precedência sobre empresa; empresa
  sobre 0.
- **Não-vazamento:** Task #115 segue verde (cliente não vê custo/indiretos).

## Rollout

- Migração aplica no boot (colunas com default 0/NULL) — sem mudança de preço.
- Snapshots de proposta **não** são recalculados (ADR 0001).
- Empresa preenche seu BDI real quando quiser; a partir daí novos cálculos
  usam o BDI completo.

## Fora de escopo

- Cascata item-a-item e nível "global" da ADR (YAGNI; empresa + override de
  proposta cobrem o caso real).
- Recálculo retroativo de propostas antigas.
- Drop das colunas-texto legadas / outros refactors não relacionados.
