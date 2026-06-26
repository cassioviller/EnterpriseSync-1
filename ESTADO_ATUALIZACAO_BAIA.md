# Estado da atualização da obra Baia — físico-financeiro

> Documento de handoff. Última atualização: **2026-06-26**.
> Resume o que foi feito nesta rodada e o que ainda falta — principalmente a
> **reconciliação dos custos pela aba `Planilha1`** do Excel novo.

---

## ⚠️ Fonte de custo que PRECISA ser lida: `Planilha de Custos REV01 (2).xlsx`

O arquivo **`Planilha de Custos REV01 (2).xlsx`** (na raiz do projeto) é a versão nova
do plano de custos. A aba que importa é a **`Planilha1`** — é dela que saem:

- o **custo por etapa** (Veks + faturamento direto) de cada nó da EAP;
- o **bloco de fluxo de caixa mensal** (medição / imposto / caixa / fat_direto por mês),
  hoje gravado verbatim em `fluxo_caixa_mensal` no JSON.

**Nesta rodada os custos NÃO foram recalculados** — só o cronograma físico foi atualizado
(ver abaixo). Os números financeiros no JSON continuam vindos da REV01 **anterior**. Para
fechar a atualização de verdade, é preciso **ler a aba `Planilha1` do
`Planilha de Custos REV01 (2).xlsx`** e reconciliar:

1. `eap[].custo` (veks / fat_direto / total / peso_pct) de cada etapa;
2. `fluxo_caixa_mensal` (meses, medicao, imposto, gasto_veks, fat_direto, caixa…).

Como ler (quando o ambiente Python voltar):

```python
from openpyxl import load_workbook
wb = load_workbook("Planilha de Custos REV01 (2).xlsx", data_only=True)
ws = wb["Planilha1"]
for row in ws.iter_rows(values_only=True):
    print(row)
```

> Observação de ambiente: o Python está temporariamente indisponível nesta máquina
> (queda do mount FUSE do `/nix/store`); só volta com **reinício do container**.

---

## O que foi feito nesta rodada

### 1. Lógica nova: competência configurável do faturamento direto

Antes, o faturamento direto sempre abatia a base de imposto/entrada **no período seguinte**
("abater no próximo pagamento"). Agora há uma opção **por obra**:

- `fat_competencia = "seguinte"` (padrão) → comportamento antigo (abate no mês seguinte);
- `fat_competencia = "mesma"` → abate **na própria medição** (mesma competência),
  reduzindo o imposto do período a que pertence, **inclusive o último** (que no modo
  antigo ficava sem abater → pagava imposto a mais).

Ganho: menos imposto, porque o fat_direto reduz a base no período certo.
Diferença de imposto entre os modos = `alíquota × fat_direto do último período`.

**Onde mora:**

| Camada | Arquivo | O quê |
|---|---|---|
| Cálculo | `services/cronograma_fisico_financeiro.py` | `calcular_fluxo_caixa(..., fat_competencia)` + helper `_fat_competencia(obra)` (lê de `fluxo_caixa_planilha`); `painel_financeiro` expõe `config.fat_competencia` |
| API | `views/obras.py` | rota `POST /obras/<id>/financeiro/config` grava a opção por obra |
| UI | `templates/obras/detalhes_obra_profissional.html` + `static/js/financeiro_obra.js` | seletor "Abatimento do faturamento direto" na aba Financeiro |
| Teste | `tests/test_cronograma_fisico_financeiro.py` | `test_caixa_fat_mesma_competencia_abate_no_proprio_periodo` (cobre os dois modos) |

Padrão preservado: obras existentes não mudam (default `"seguinte"`). A Baia foi marcada
como `"mesma"` no JSON.

### 2. Cronograma físico atualizado pelo `CRONOGRAMA OFICIAL.mpp`

Fonte: **`CRONOGRAMA OFICIAL.mpp`** (MS Project, **57 tarefas**, agora com split
**BAIA 01 / BAIA 02**, fim em **08/10**). Substituiu o cronograma antigo (43 tarefas,
fim 11/09).

Fixture atualizada: `tests/fixtures/cronograma_fisico_financeiro_baias.json`

- `cronograma_tarefas` → espelho fiel das **56 tarefas** do .mpp (ids 1..56;
  descartado o wrapper "Projeto1" id 0).
- As **12 etapas de custo** da EAP foram **mantidas** (custos/`peso_pct` intactos,
  `Σ peso_pct = 0,9999`) e tiveram só o `tarefas_mpp` **remapeado por nome**, mais
  recálculo de `inicio` / `fim` / `pct_fisico`.
- Tarefas **FAZENDA** novas (nivelamento, drenagem) entram **só no físico** (sem custo),
  alocadas a **Indiretos** para faseamento.
- `data_fim_cronograma` corrigido para **08/10**; medições **preservadas** (cronograma
  de faturamento contratual não mudou); `_meta` atualizado.

**Mapa etapa → tarefas do novo .mpp** (decidido por significado):

| Etapa | %fís | tarefas_mpp (folhas do .mpp) |
|---|---|---|
| PRELIM | 83.3 | 3, 4, 5, 9 |
| FUND | 0 | 11, 12, 14, 15, 17, 18, 20, 21, 22, 23 |
| ESTMET | 0 | 30, 31, 32 |
| ESTLSF | 0 | 26, 27, 28 |
| COBERT | 0 | 33, 35 |
| FECHA | 0 | 40, 41, 42, 43, 44, 45 |
| PINT | 0 | 37, 38, 46, 47 |
| MOLEDO | 0 | 24, 48 |
| PORTAO | 0 | 53, 54 |
| ELET | 0 | 50, 51 |
| HIDRO | 0 | 13, 16 |
| INDIRETOS | 31.9 | 2, 6, 19, 34, 36, 55, 56 (inclui FAZENDA, só físico) |

> O acoplamento: `eap[].cronograma.tarefas_mpp` (ids) → busca em `cronograma_tarefas`
> → datas que faseiam o custo da etapa (alimenta Curva S e fluxo de caixa).

---

## Commits (já no `origin/main`)

- `6d70b66b` — feat: competência configurável do fat_direto + fixture da Baia atualizada
- `49b8db0a` — chore: adiciona `CRONOGRAMA OFICIAL.mpp` (add com `-f`; `*.mpp` é ignorado)

Repositório: `github.com/cassioviller/EnterpriseSync-1`.

---

## Pendências

1. **Reconciliar custos pela `Planilha1`** do `Planilha de Custos REV01 (2).xlsx`
   (ver topo). Atualizar `eap[].custo` e `fluxo_caixa_mensal` se os números mudaram.
2. **Rodar os testes** contra o JSON novo (bloqueado enquanto o Python estiver caído):
   ```
   python -m pytest tests/test_importacao_fisico_financeiro.py tests/test_painel_financeiro.py -q
   ```
3. **Revisar o mapa etapa→tarefas** acima (foi por julgamento de nome; conferir se algum
   item — ex.: basecoat em FECHA vs PINT, içamento de pilares em FUND — deve mudar de balde).
4. Reconferir se as **datas das medições** (M4 entrega 05/10, M5 retenção 20/11) seguem
   válidas com o novo fim de cronograma (08/10) — mantidas como estavam por decisão.

---

## Como o JSON é consumido (referência rápida)

- Importação: `services/importacao_fisico_financeiro.py`
  - `cronograma_tarefas` → `mpp = {t['id']: t}` (linha ~324)
  - cada etapa → `_materializar_cronograma_fisico` usa `cronograma.tarefas_mpp` para criar
    as tarefas-folha e pesar a medição por duração.
  - `obra.fluxo_caixa_planilha = payload['fluxo_caixa_mensal']` (daí saem `imposto_pct` e
    `fat_competencia` por obra).
- Painel ao vivo: `painel_financeiro(obra)` recalcula tudo do cronograma + custos
  (o `fluxo_caixa_mensal` verbatim só alimenta o comparativo de divergência).
