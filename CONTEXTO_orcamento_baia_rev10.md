# Contexto — Orçamento "Baia REV10" (Kabod Cabana) para handoff a outro LLM

> Documento autossuficiente. Reúne (1) como o aplicativo SIGE calcula um orçamento,
> (2) o orçamento real que estou trabalhando, (3) os arquivos relevantes, (4) o que já
> foi feito e (5) as decisões em aberto. Cole isto inteiro num LLM para continuar o trabalho.
> Última atualização: 2026-06-12.

---

## 0. Resumo de uma linha

Estou convertendo um orçamento de obra feito à mão no Excel (`Orçamento - Baia - REV10.xlsx`,
24 baias de bovinos na Fazenda Santa Mônica, Itu/SP) para o modelo estruturado do meu
sistema (SIGE, app Flask), decompondo a "verba" genérica do item 1.17 em insumos/serviços
reais, ancorando preços no SINAPI e validando o total contra a planilha.

---

## 1. Como o aplicativo (SIGE) calcula um orçamento

App Flask + SQLAlchemy. O orçamento segue a cadeia:
**Insumo → Preço → Composição → Serviço → Item de Orçamento → (BDI) → Venda → Proposta.**

### 1.1 Modelos de dados (arquivo `models.py`)

- **`Insumo`** (models.py:5995) — `nome`, `tipo` (`MATERIAL` | `MAO_OBRA` | `EQUIPAMENTO`),
  `unidade`, `fator_comercial` (múltiplo de fornecimento, ex.: 100 parafusos = 1 pacote),
  `fracionavel` (True=kg/m/h; False=peça → arredonda pra cima na compra).
  Método `preco_vigente(data_ref)`.
- **`PrecoBaseInsumo`** (models.py:6060) — `insumo_id`, `valor`, `vigencia_inicio`,
  `vigencia_fim` (nullable = sem expiração). O preço vigente é o 1º registro (ordenado por
  `vigencia_inicio` desc) cuja janela contém `data_ref`; senão 0.
- **`ComposicaoServico`** (models.py:6082) — liga `servico_id` ↔ `insumo_id` com
  `coeficiente` (consumo de insumo por unidade de serviço) e `unidade`.
- **`Servico`** (models.py:415) — `nome`, `categoria`, `unidade_medida`, e defaults de
  markup: `imposto_pct`, `margem_lucro_pct`.
- **`Orcamento`** (models.py:6201) e **`OrcamentoItem`** (models.py:6249) — o item tem
  `quantidade`, `composicao_snapshot` (JSON editável), `custo_unitario`,
  `preco_venda_unitario`, `custo_total`, `venda_total`, `lucro_total`, e overrides
  `imposto_pct` / `margem_pct`.
- **`ConfiguracaoEmpresa`** (models.py:3577) — defaults de BDI da empresa:
  `imposto_pct_padrao` (8%), `lucro_pct_padrao` (10%), e componentes BDI
  `bdi_ac_pct` (Adm. Central), `bdi_seguro_pct`, `bdi_risco_pct`, `bdi_garantia_pct`,
  `bdi_desp_financeiras_pct` (todos default 0). Guarda-corpo: avisa quando T+L ≥ 60%,
  bloqueia quando T+L ≥ 90%.
- **`Proposta`** (models.py:2907) / **`PropostaItem`** (models.py:3153) — herdam **só o
  preço de venda** do orçamento; custos ficam ocultos do cliente.

### 1.2 Cadeia de cálculo (custo)

1. **Custo unitário do Serviço** (`services/orcamento_service.py:34-133`,
   `calcular_precos_servico`):
   `custo_unitario = Σ( coeficiente_i × preco_vigente_i / fator_comercial_i )`,
   separado por tipo (material / mão de obra / outros).
2. **Custo real do OrcamentoItem com quantidade comercial**
   (`services/orcamento_view_service.py:79-204`, `recalcular_item`):
   para cada linha do snapshot, `qtd_tec = coef × quantidade`; se o insumo não é fracionável
   (ou `fator>1`), arredonda pra cima ao múltiplo do `fator` → `custo_compra = Σ(qtd_compra × preço)`.
3. **Totais do Orçamento** (`recalcular_orcamento`, mesmo arquivo:325):
   `custo_total = Σ(item.custo_total)`, idem venda e lucro.

### 1.3 Custo → Venda (BDI / imposto / lucro)

Fórmula TCU "por dentro" (spec em `docs/superpowers/specs/2026-05-29-orcamento-bdi-lucro-impostos-proposta.md`):

- **BDI completo** (`services/pricing.py:143-205`, `precificar`):
  ```
  indiretos = custo_direto × (AC + S + R + G + DF)/100
  preco     = (custo_direto + indiretos) / (1 − (T + L)/100)
  tributos  = preco × T/100   ;   lucro = preco × L/100
  ```
  onde **T** = imposto, **L** = lucro/margem. Cascata de alíquotas:
  Serviço → ConfiguracaoEmpresa → 0 (e BDI: Proposta → Empresa → 0).
- **Caminho do OrcamentoItem** (`orcamento_view_service.py:167`) usa o **divisor simples**
  (só imposto + margem, sem AC/S/R/G/DF):
  ```
  preco_unit  = custo_medio / (1 − (T + L)/100)
  venda_total = custo_compra / (1 − (T + L)/100)
  ```

> ⚠️ Detalhe importante: a planilha original NÃO usa essa fórmula. Nela o material é
> `venda = custo/(1−lucro)` (lucro 20–25%) e a mão de obra `venda = custo/(1−imposto−lucro)`
> (imposto 13%, lucro 28% → markup 69,49%). Ao importar, mapear esses % para `imposto_pct`
> e `margem_pct` do sistema.

### 1.4 Geração da Proposta

`views/orcamentos_views.py:595-818` (`gerar_proposta`): recalcula o orçamento, cria a
`Proposta` com `valor_total = Orcamento.venda_total`, e um `PropostaItem` por item
(copiando só `preco_unitario`/`subtotal` de venda + snapshot; sem custos).

### 1.5 Arquivos-chave do cálculo (código)

| Arquivo | Papel |
|---|---|
| `models.py` | Modelos + `Insumo.preco_vigente` (6044) |
| `services/orcamento_service.py` | Custo do serviço a partir dos insumos |
| `services/orcamento_view_service.py` | Custo real do item (qtd comercial) + totais |
| `services/pricing.py` | Fórmula BDI/TCU + guarda-corpo |
| `views/orcamentos_views.py` | Orçamento → Proposta |
| `docs/superpowers/specs/2026-05-29-orcamento-bdi-lucro-impostos-proposta.md` | Spec do BDI |

---

## 2. O orçamento que tenho (entrada)

- **Arquivo:** `Orçamento - Baia - REV10.xlsx` (15 abas). A **fonte de verdade é a aba
  `Proposta Comercial`**, colunas **F/G = CUSTO** unitário (material/M.O.), E=quantidade,
  H/I = custo total, J = total. As colunas K–AE são a camada de venda/BDI (lucro/imposto).
- **As abas técnicas** (`Fundação`, `Aço `, `Instalações`, `Memorial de calculo`, etc.) são
  memórias de cálculo de apoio — várias em estado meio-preenchido/quebrado. **Não há fórmula
  ligando-as à proposta**; os valores F/G foram digitados à mão.
- **A obra:** 24 baias de 30 m² em 2 blocos de 12 (planta `BLOCO 1 E 2`), separados por uma
  "cabana existente". Estrutura em LSF (aço galvanizado), cobertura shingle, fechamentos em
  placa cimentícia/régua pinus, fundação em radier + vigas baldrame.
- **Item 1.17 ("Pacote complementar"):** uma verba única de **R$92.564** (mat 52.322 + M.O.
  40.242) que engloba 9 escopos descritos em texto, sem decomposição. Foi o foco do trabalho.

### 2.1 Os 17 itens da proposta (custo, da planilha)

| Item | Descrição curta | Un | Qtd | J (custo total) |
|---|---|---|---|--:|
| 1.1 | Estrutura LSF Z275 | vb | 1 | 484.645,50 |
| 1.2 | Pintura aço estrutural | m² | 1.173 | 41.055,00 |
| 1.3 | Pintura/Stain portão pinus | m² | 161 | 134.435,00 🔴 |
| 1.4 | Portão pinus | un | 48 | 22.800,00 |
| 1.5 | Fechamento interno placa cimentícia | m² | 900 | 40.500,00 |
| 1.6 | Fechamento externo régua pinus | m² | 660 | 29.700,00 |
| 1.7 | Pintura fechamentos internos | vb* | 900 | 40.500,00 |
| 1.8 | Pintura Stain paredes externas | m² | 660 | 20.600,00 |
| 1.9 | Verticalização pilares roliços | vb | 32 | 18.181,82 |
| 1.10 | Corredores em concreto | vb | 1 | 71.554,00 |
| 1.11 | Revestimento pedra moledo | m² | 40 | 9.200,00 |
| 1.12 | Pontos de luz | un | 1 | 13.410,00 |
| 1.13 | Telha shingle | m² | 1.173 | 99.705,00 |
| 1.14 | Cercado das baias | un | 24 | 13.200,00 |
| 1.15 | Pintura Stain cercado | un | 24 | 10.400,00 |
| 1.16 | Ponto hidráulico por baia | un | 24 | 3.267,10 |
| 1.17 | Pacote complementar (verba) | VB | 1 | 92.564,00 |
| | **TOTAL (J27 da planilha)** | | | **1.145.717,42** |

---

## 3. O que já foi feito

Tudo versionado em git (branch `main`). Scripts idempotentes que escrevem no catálogo do
sistema (rodam com `PYTHONPATH=/home/runner/workspace python3 scripts/<nome>.py`).

### 3.1 Decomposição do item 1.17 em 5 serviços reais (catálogo `Obra Baia REV10`)

| Serviço (1.17) | Custo | Base | Confiança |
|---|--:|---|---|
| Fundação – sapatas, radier e aço | **92.001** | aba `Fundação`, **enxugada** (ver 3.3) | ✅ |
| Infra Elétrica | 17.400 | contagem dos projetos + SINAPI-SP 104473/104480 | ⚠️ |
| Infra Hidráulica | 19.000 | projetos + Memorial + SINAPI 104678 | ⚠️ |
| Isolamento lã de rocha | 6.865 | área Memorial; preço de mercado (~R$25/m²) | 🧩 |
| Forro PVC preto | 12.945 | área Memorial; SINAPI 96111 (R$66/m²) | 🧩 |
| **1.17 REAL** | **148.211** | (vs verba R$92.564 → gap R$55,6k / 60%) | |

Escopos do 1.17 **não recadastrados** (já estão em outros itens — evitar dupla contagem):
aço/painelização → **1.1**; fechamentos → **1.5/1.6**; pintura stain → **1.8/1.15**.
**Não inclusos** (cliente fornece o material): telha shingle, louças/metais (R$40.939,92),
madeiras, pré-moldados, esquadrias.

### 3.2 Firmação de elétrica/hidráulica pela análise dos projetos (PDFs)

- **DETALHE_ESTUDO_BAIAS**: cada baia tem **1 ponto de luz no teto + 1 ponto de água fria +
  1 ponto de esgoto** (bebedouro). Legenda elétrica: ponto luz, arandela, refletor LED,
  interruptor paralelo, tomada baixa/média.
- **IMPLANTAÇÃO**: 2 blocos de 12 baias + cabana existente. O banheiro/apoio (8 bacias, 6
  cubas, 2 mictórios, etc. do Memorial) **é do projeto** → a infra hidráulica e a M.O. de
  instalação das louças (R$3.436) entram; só o **material das louças** fica "não incluso".
- Substituiu a "verba Vereda" (R$28k cada) por contagem SINAPI: Elétrica R$17,4k,
  Hidráulica R$19,0k.

### 3.3 Enxugamento da fundação (correção de gordura)

A aba `Fundação` bilava **40 dias de equipe (R$46.800)** + escavação à parte (R$5.600), mas o
`Memorial` diz RADIER = 15 dias e a equipe já faz a escavação. Ajustado para **20 dias** e
escavação removida (dupla contagem) → fundação de **R$121k caiu para R$92.001**. Cruzamento
SINAPI: R$2.078/m³, dentro da faixa de concreto armado de fundação. Surpresa: a fundação
enxuta ficou a **R$563 da verba 1.17** → a verba do autor foi dimensionada para a fundação a
~20 dias.

### 3.4 Validação dupla do orçamento inteiro

Script `scripts/validar_orcamento_baia_rev10.py` recalcula item a item e revelou:

- 🔴 **Erro na planilha — item 1.3 (R$128.000 fantasma):** no total `J` o Stain entra como
  R$800 × 161 m² (=128.800), mas na coluna de material `H` entra como R$800 global. **Só o
  1.3** é internamente inconsistente (`J ≠ H+I`).
- **Três totais:**
  | Total | Valor |
  |---|--:|
  | Planilha (J27) — com fantasma do 1.3 | 1.145.717,42 |
  | Consistente (ΣH+ΣI, corrige 1.3) | **1.017.717,42** |
  | Validado (consistente + 1.17 decomposto) | **1.073.364,66** |
- Líquido: o 1.3 inflava R$128k; o 1.17 subprecificava R$55,6k → o custo real (~R$1,073 mi)
  é ~R$72k **menor** que o exibido (R$1,145 mi).

---

## 4. Arquivos relevantes (todos em `/home/runner/workspace`)

### Entrada (dados da obra)
- `Orçamento - Baia - REV10.xlsx` — **a planilha original** (fonte de verdade = aba `Proposta Comercial`).
- `obra_kabod/10. Kabod Cabana - Baias de bovinos/PROJETOS/`:
  - `DETALHE_ESTUDO_BAIAS_REV00.pdf` — detalhe de 1 baia + **legenda elétrica/hidráulica**.
  - `BLOCO 1 E 2_ESTUDO_BAIAS_REV01.pdf` — planta baixa das 24 baias.
  - `IMPLANTACAO_ESTUDO_BAIAS_REV00.pdf` — implantação (2 blocos + cabana existente).
  - `CROQUIS_KABODCABANAS_22 BAIAS...pdf` — renders 3D.
  - `EST_PROJBAIAS_FAZMONICA_REV01 (2).dwg` — **projeto estrutural (DWG, ainda não lido)** —
    fonte para confirmar área/volume real do radier.
- `obra_kabod/.../PROPOSTA/REVISÕES BAIAS/REV. 10/` — proposta comercial REV10 (docx/pdf).

### Análise e planos (markdown)
- `relatorio_analise_orcamento_baia_rev10.md` — análise técnica item a item (1.1–1.17),
  com os erros da planilha e as 9 decisões.
- `plano_regras_conversao_orcamento_baia_rev10.md` — plano/regras de conversão.
- `composicao_servicos_baia_rev10.md` — composições de serviço.
- **`CONTEXTO_orcamento_baia_rev10.md`** — este documento.

### Scripts (em `scripts/`, idempotentes)
- `gerar_importacao_baia_rev10.py` — gera a planilha de importação.
- `criar_orcamento_baia_rev10.py` — importa catálogo + monta o orçamento no sistema.
- `gerar_proposta_baia_rev10.py` — gera a proposta a partir do orçamento.
- `decompor_117_fundacao.py` — serviço Fundação do 1.17 (enxugado a 20 dias).
- `decompor_117_resto.py` — serviços Elétrica/Hidráulica/Isolamento/Forro do 1.17.
- `validar_orcamento_baia_rev10.py` — **validação dupla** (recalcula tudo, acha o erro do 1.3).

### Planilhas de importação geradas
- `IMPORTACAO_Baia_REV10.xlsx`, `IMPORTACAO_Baia_REV10_completa.xlsx`.

### Código do sistema (cálculo) — ver tabela na seção 1.5.

---

## 5. Decisões em aberto (não corrigidas em silêncio)

1. **Item 1.3 (R$128k):** o Stain é R$800 **global** (então J está errado em R$128k) ou
   R$800/**m²** (então H está errado)? Muda o total do projeto em R$128k.
2. **Item 1.16:** material hidráulico R$867,10 contado **1× para 24 baias**. Se for ×24,
   +R$19.943.
3. **Material das louças (R$40.939,92):** manter "não incluso" (como na proposta REV10) ou a
   VEKS passa a fornecer?
4. **Custo × Venda:** reproduzir o **custo** (F/G) e aplicar imposto/lucro do sistema por cima
   (recomendado), ou gravar o preço de venda direto? E qual o "Valor do Projeto" exibido —
   custo (~R$1,07 mi) ou venda (~R$1,7 mi)?
5. **Modelo de M.O.:** taxa R$/unidade fiel à proposta (rápido) ou equipe·dia/hora (técnico,
   exige decidir jornada)?
6. **Itens 1.9 (base 44 vende 32), 1.12 (12 pts vs 24 baias + pilares):** validar quantidades.
7. **Premissas 🧩 do 1.17 ainda por confirmar:** nº de luminárias nos pilares (~20), metragem
   da rede de água fria (~130m), área de isolamento/forro (usei 196 m² de forro).

---

## 6. Próximos passos sugeridos

1. Fechar as decisões 1–3 (impactam o número final direto).
2. Montar o **lado de venda** (a outra metade da validação dupla): aplicar imposto/lucro e
   bater com as colunas M/N/O da planilha.
3. Abrir o **projeto estrutural (DWG)** para confirmar área/volume do radier (valida os 58 m³).
4. Importar o 1.17 decomposto no orçamento do sistema (hoje os serviços existem no catálogo;
   falta montar/atualizar o `OrcamentoItem` correspondente).

### Convenções de confiança usadas neste material
✅ confirmado na planilha/projeto · ⚠️ precisa validar · 🔴 divergência/erro · 🧩 inferência/estimativa.
