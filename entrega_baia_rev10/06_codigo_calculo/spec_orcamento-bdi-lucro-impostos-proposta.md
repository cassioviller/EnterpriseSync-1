# Proposta de Solução — Cálculo de Preço do Orçamento: Impostos, Lucro e BDI

**Data:** 2026-05-29
**Status:** Proposta para crítica (será atacada com `grillme`)
**Autor:** Cássio Viller (via brainstorming)

> Documento deliberadamente opinativo: serve de alvo para o `grillme`. Onde há
> dúvida de produto, registro a decisão recomendada + alternativas.

## 1. Sintoma relatado

"Quando o lucro chega perto de 90, o preço vira um número astronômico."

Reprodução: serviço com custo R$ 1.000, imposto 8%, lucro 90%.
`preço = 1000 / (1 − 0,08 − 0,90) = 1000 / 0,02 = R$ 50.000`. Em 95% de lucro →
R$ 142.857. Em ≥100% (imposto+lucro) → o sistema zera o preço e mostra erro.

## 2. Diagnóstico — a fórmula atual

`services/orcamento_service.py:100`:

```
preço_venda = custo_unitário / (1 − imposto_pct/100 − margem_lucro_pct/100)
```

Isso é, na prática, um **BDI degenerado**: imposto e lucro são aplicados
"por dentro" (sobre o preço de venda). A explosão perto de 100% é
**matematicamente esperada** — não é um erro de código. O problema real é um
conjunto de falhas de produto/UX em volta dessa fórmula.

### Falhas identificadas

| # | Falha | Evidência |
|---|-------|-----------|
| **P1** | **Sem validação/limite** nos percentuais. Imposto+lucro pode chegar a 98–99% e gerar preço astronômico silenciosamente; só zera em ≥100%. | `orcamento_service.py:100-106`; forms `servico_form.html` e orçamento não limitam o input |
| **P2** | **Descasamento conceitual.** O usuário pensa "lucro = markup sobre o custo" (90% = vendo por 1,9× o custo). O sistema trata lucro como **% do preço de venda** (90% = 90% do preço é lucro → exige 50× o custo). Nada na UI explica isso. | fórmula por dentro; nenhum rótulo explicativo |
| **P3** | **"Lucro" exibido está errado.** `explodir_servico_para_quantidade` define `lucro = preço − custo`, que **inclui o imposto** (`= (imposto+margem)×preço`). Telas de Orçamento/Medição/Métricas mostram isso como "Lucro". Superestima o lucro real. | `orcamento_service.py:344`; `orcamentos/editar.html`, `metricas/*` |
| **P4** | **Não há BDI de verdade**, apesar de ser construtora. Faltam administração central (AC), despesas financeiras, risco, garantia, seguros. O markup só tem imposto + lucro. | sem campos no modelo `Servico`/`Orcamento` além de imposto/margem |
| **P5** | **`percentual_nota_fiscal` (13,5%) confunde.** É só informativo no PDF, paralelo ao `imposto_pct`, sem entrar no cálculo. Parece um segundo imposto. | `models.py:2930`; `pdf_estruturas_vale*.html` |

## 3. Respostas diretas

### 3.1 "Existe BDI para construtora? Como funciona?"

Sim — **BDI (Benefícios e Despesas Indiretas)** é o padrão da construção civil
brasileira. Fórmula consagrada (TCU, Acórdão 2622/2013):

```
BDI = [ (1 + AC + S + R + G + DF) / (1 − T − L) ] − 1
preço_venda = custo_direto × (1 + BDI)
```

- **AC** = administração central (rateio do escritório)
- **S** = seguros · **R** = riscos/imprevistos · **G** = garantias
- **DF** = despesas financeiras
- **T** = tributos sobre o preço de venda (PIS, COFINS, ISS, CPRB)
- **L** = **lucro — remuneração BRUTA do construtor**

Numerador (1 + AC + S + R + G + DF) = custos indiretos aplicados **por fora**
(multiplicam o custo). Denominador (1 − T − L) = tributos e lucro **por dentro**
(percentual do preço de venda). Faixas de referência do TCU: L ≈ 6–9%, BDI total
tipicamente **20–30%** para edificações.

**Conclusão:** o SIGE já usa a estrutura "por dentro" do BDI, mas só com T e L e
sem o numerador de custos indiretos. É um BDI incompleto.

### 3.2 "O lucro que coloco é líquido ou bruto?"

**Bruto, e sobre o faturamento.** O `margem_lucro_pct` corresponde ao **L do
BDI = remuneração bruta do construtor, como % do preço de venda** — não é líquido
(não desconta IR/CSLL, AC, despesas) e **não é markup sobre o custo**. Pior: o
valor rotulado "Lucro" nas telas (`preço − custo`) ainda embute o imposto, então
nem o L puro ele mostra.

## 4. Proposta de solução

### Opção A (recomendada) — BDI explícito + validação + decomposição correta

1. **Modelo de BDI** (em `ConfiguracaoEmpresa` como default e override por
   serviço/orçamento): campos `bdi_ac_pct`, `bdi_seguro_pct`, `bdi_risco_pct`,
   `bdi_garantia_pct`, `bdi_desp_financeira_pct`, `tributos_pct`, `lucro_pct`.
2. **Fórmula única** num só lugar (`orcamento_service.py`):
   `preço = custo × (1 + AC + S + R + G + DF) / (1 − T − L)`.
   Mantém o tratamento por dentro de T e L (correto p/ TCU), mas completo.
3. **Validação e guarda-corpo:** bloquear/avisar quando `T + L ≥ limite seguro`
   (ex.: 85%); exibir o **BDI% resultante** ao lado dos campos para o usuário ver
   o efeito antes de salvar; faixa sugerida (20–30%) como referência visual.
4. **Decomposição correta na UI:** mostrar Custo / Indiretos (AC+S+R+G+DF) /
   Tributos / **Lucro (L×preço)** separadamente — acaba com o "Lucro" que inclui
   imposto (P3).
5. **Reconciliar `percentual_nota_fiscal`** com o `tributos_pct` do BDI (uma
   fonte só) ou marcá-lo claramente como "apenas texto no PDF".
6. **Migração:** mapear `imposto_pct → tributos_pct`, `margem_lucro_pct →
   lucro_pct`, demais componentes default 0 (comportamento idêntico ao atual até
   a empresa preencher AC/DF/etc.).

### Opção B (mínima) — só estancar o bug

Mantém a fórmula atual; adiciona validação (P1) + corrige o rótulo do lucro (P3)
+ tooltip explicando "por dentro" (P2). Baixo esforço, não resolve P4 (sem BDI).

### Opção C — lucro "por fora" (markup sobre custo)

Trocar L para multiplicador: `preço = custo × (1 + lucro) / (1 − tributos)`.
Mais intuitivo (90% = 1,9× custo, sem explosão), mas **diverge do padrão TCU**
(onde L é por dentro). Bom para venda privada, ruim para obra pública.

### Recomendação

**Opção A.** É o que uma construtora realmente precisa, corrige todas as falhas
(P1–P5), e a migração preserva o comportamento atual como caso particular
(componentes extras = 0). A explosão deixa de acontecer na prática porque L volta
a ser um número pequeno e validado, e o usuário enxerga o BDI% resultante.

## 5. Impacto e riscos

- **Telas afetadas:** form do serviço, módulo de orçamento (`Orcamento`/
  `OrcamentoItem` já têm cascade item→global→serviço), composição, proposta/PDF,
  medição, métricas (todas leem `lucro_total`/`preço`).
- **Compatibilidade:** propostas/itens já criados têm snapshot de preço — não
  recalcular retroativamente; aplicar BDI só em novos cálculos.
- **Cascata existente** (`orcamento_view_service.py:64`: item→global→serviço→0)
  deve ser estendida para todos os componentes do BDI, não só imposto/lucro.
- **Risco de regressão** nos testes de paridade de preço (`tests/test_orcamento_*`).

## 6. Pontos abertos (para o grillme atacar)

1. Manter L "por dentro" (TCU-correto, Opção A) ou mudar para "por fora" (Opção
   C, intuitivo)? Qual é o público: obra pública (BDI obrigatório) ou venda
   privada?
2. BDI por serviço, por orçamento (global) ou por empresa? Quão granular?
3. `percentual_nota_fiscal` vira o `tributos_pct` ou continua texto separado?
4. Validar com bloqueio rígido (não deixa salvar) ou só aviso?
5. O "Lucro" das telas deve virar "Lucro líquido estimado" (descontando IR/CSLL)
   ou basta separar do imposto (lucro bruto)?
6. Vale recalcular orçamentos em rascunho ao mudar o BDI, ou só dali pra frente?

## Fontes (BDI)

- [Acórdão 2622/2013-TCU — texto oficial](https://pesquisa.apps.tcu.gov.br/doc/acordao-completo/2622/2013/Plen%C3%A1rio)
- [Sienge — Entenda o Acórdão 2622/2013](https://sienge.com.br/blog/acordao-26222013/)
- [TOTVS — BDI na construção civil: o que é, fórmula e exemplos](https://www.totvs.com/blog/gestao-para-construcao/bdi/)
- [Mais Controle ERP — BDI: o que é, fórmula e exemplos](https://maiscontroleerp.com.br/bdi-na-construcao-civil/)
