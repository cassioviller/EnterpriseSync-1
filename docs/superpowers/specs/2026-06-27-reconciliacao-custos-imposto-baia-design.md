# Reconciliação de custos e imposto — obra Baia (Planilha1 REV01)

> Design doc. Data: 2026-06-27.
> Objetivo: reconciliar 100% o JSON `tests/fixtures/cronograma_fisico_financeiro_baias.json`
> com a aba `Planilha1` do `Planilha de Custos REV01 (2).xlsx`, **corrigindo** as
> inconsistências internas da planilha e um bug de imposto no engine do sistema.

## Contexto

A `Planilha1` é a fonte de custo nova (custo por etapa + fluxo de caixa mensal). O JSON da
fixture ainda carregava números da REV01 anterior. Ao abrir as **fórmulas** da planilha
(não só os valores), descobrimos que o motor de cálculo é coerente, mas a planilha tem
**3 inconsistências internas** e o código do sistema tem **1 bug de imposto**.

## Como a Planilha1 calcula (modelo reverso-engenheirado)

- `P4` = `X6` = **Venda = 1.505.613,76** (denominador de tudo).
- Cada etapa: `Total = Veks + Fat Direto`. Coluna `%` = `Total ÷ Venda` (share sobre a venda).
- **Engine de caixa mensal** (jun…nov; não há custo em nov):
  - `medição = %mês × venda` (0.2 / 0.3 / 0.2 / 0.2 / 0.05 / 0.05)
  - `imposto = (medição − fat_direto) × 13,5%` (ISS 4% + DAS 9,5%)
  - `entrada = medição − fat_direto − imposto`
  - `caixa_inicial = entrada + caixa_final(mês anterior)`; `caixa_final = caixa_inicial − gasto_veks`
- A base do imposto `medição − fat_direto` equivale ao `fat_competencia = "mesma"` já no JSON.

## Decisões do usuário (2026-06-27)

1. **Indiretos = versão cara (5 meses).** A planilha conta 3,5 meses no total das etapas mas
   5 meses (Escritório) / 4 meses (Empréstimo) no fluxo mensal. Verdade adotada: **5 meses**
   → INDIRETOS veks = 457.000; custo total = 1.351.734,33.
2. **Tudo que a Veks recebe é tributado, inclusive a mobilização de junho.** Remove a exceção
   de junho da planilha.
3. **Base do imposto = medição − fat_direto.** O fat direto é pago pelo cliente direto ao
   fornecedor; a Veks não o recebe → não entra na base.

## As 3 inconsistências da planilha + 1 bug do código

| # | Onde | Problema | Correção |
|---|---|---|---|
| 1 | Planilha — Indiretos | total usa 3,5 meses, mensal usa 5/4 meses (Δ 74.000) | adotar 5 meses (decisão do usuário) |
| 2 | Planilha — `N61` imposto | junho não tributado + `+20.000` chumbado na mão | tributar junho de verdade (40.651,57) |
| 3 | Planilha — junho | célula de imposto em branco | engine do sistema já tributa junho |
| 4 | **Código** `kpis` (l.467) e `fluxo_caixa_divergencia` (l.452) | `imposto = venda × 13,5% = 203.258` supertributa o fat direto | `imposto = (venda − fat_direto_total) × 13,5% = 128.903` |

**Observação:** o engine de caixa `calcular_fluxo_caixa` (l.147) **já está correto** — tributa
`(medição − fat)` todo mês, inclusive o primeiro. Não muda.

## Estado-alvo (modelo consistente)

### `eap[].custo` (4 mudanças + peso_pct recalculado sobre Σ = 1.351.734,33)

| Etapa | veks | fat_direto | total | peso_pct |
|---|---:|---:|---:|---:|
| PRELIM | 51.159,69 | 0 | 51.159,69 | 0.0378 |
| FUND | 68.100 | **87.882,64** | 155.982,64 | 0.1154 |
| ESTMET | 0 | **332.892** | 332.892 | 0.2463 |
| ESTLSF | 15.000 | 55.000 | 70.000 | 0.0518 |
| COBERT | 75.400 | 0 | 75.400 | 0.0558 |
| FECHA | 51.000 | 75.000 | 126.000 | 0.0932 |
| PINT | 51.700 | 0 | 51.700 | 0.0382 |
| MOLEDO | 10.000 | 0 | 10.000 | 0.0074 |
| PORTAO | 10.000 | 0 | 10.000 | 0.0074 |
| ELET | 7.200 | 0 | 7.200 | 0.0053 |
| HIDRO | 4.400 | 0 | 4.400 | 0.0033 |
| INDIRETOS | **457.000** | 0 | 457.000 | 0.3381 |

Mudanças vs JSON atual: ESTMET fat 208.700→332.892; INDIRETOS veks 480.500→457.000;
FUND fat 85.000→87.882,64; PRELIM veks 51.160→51.159,69. Σpeso = 1,0000.

### `fluxo_caixa_mensal` (snapshot, regravado — junho tributado)

| | jun | jul | ago | set | out | nov |
|---|---:|---:|---:|---:|---:|---:|
| medicao | 301.123 | 451.684 | 301.123 | 301.123 | 75.281 | 75.281 |
| fat_direto | 0 | 242.180 | 154.297 | 154.297 | 0 | 0 |
| gasto_veks | 140.350 | 201.340 | 180.860 | 163.540 | 114.870 | 0 |
| imposto | 40.652 | 28.283 | 19.821 | 19.821 | 10.163 | 10.163 |
| entrada_liquida | 260.471 | 181.221 | 127.004 | 127.004 | 65.118 | 65.118 |
| caixa_inicial | 260.471 | 301.343 | 227.007 | 173.151 | 74.728 | 24.976 |
| caixa_final | 120.121 | 100.003 | 46.147 | 9.611 | −40.142 | 24.976 |

`imposto_pct = 0.135`, `fat_competencia = "mesma"`, `lucro_caixa_final = 24.976`.

> Nota: caixa_final fica negativo em out (−40.142); recupera em nov. É o faseamento da
> própria planilha (Veks desembolsa antes de receber). Informativo, não bloqueante.

### Convergência (prova do 100%)

Com o modelo corrigido, os dois lucros que antes divergiam passam a **bater**:
- `lucro_caixa_final` (caixa nov) = **24.976,15**
- `lucro_projetado` (KPI: venda − custo − imposto) = **24.976,15**
- imposto único = **128.903,28** nos três lugares (engine, KPI, divergência).

## Plano de implementação

1. **Código** `services/cronograma_fisico_financeiro.py`: em `kpis` (l.467) e
   `fluxo_caixa_divergencia` (l.452), trocar `venda × imposto_pct` por
   `(venda − fat_direto_total) × imposto_pct`. `fat_direto_total = dados["totais"]["fat_direto"]`.
2. **JSON** `tests/fixtures/cronograma_fisico_financeiro_baias.json`: atualizar `eap[].custo`
   (4 campos) + recalcular todos os `peso_pct`; regravar `fluxo_caixa_mensal`.
3. **Testes:** `test_cronograma_fisico_financeiro`, `test_painel_financeiro`,
   `test_importacao_fisico_financeiro` — ajustar asserts que dependam do imposto antigo.

## Fora de escopo

- Reorganizar o mapa etapa→tarefas do .mpp (revisão de balde — pendência separada).
- Recalibrar datas de medição contratual.
