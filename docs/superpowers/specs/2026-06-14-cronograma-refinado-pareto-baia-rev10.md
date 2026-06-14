# Cronograma refinado (Pareto + Linha de Balanço) — Obra Baia REV10

> Decisão de engenharia: **o que realmente vale metrificar** no cronograma da Baia. Parte da quebra
> completa (`2026-06-14-quebra-atividades-baia-rev10.md`, ~80 passos = referência) e a **enxuga ao
> que tem valor de gestão**, para não poluir o RDO nem matar a aderência do preenchimento.
> Fundamentado no Pareto de custo real do orçamento + metodologia (LOB/LBMS, EVM, aderência de RDO).
> Data: 2026-06-14. Este é o **cronograma-de-controle de referência**; a quebra de ~80 passos fica
> como dicionário de método executivo.

## Princípio (por que enxugar)
1. **Pareto manda onde detalhar.** ~20% dos itens = ~80% do custo. Detalhe se paga nos itens **A**;
   nos **C** (2% cada) é só trabalho sem resultado. (Cost-significant work packages; ABC analysis.)
2. **Obra repetitiva = Linha de Balanço.** 24 baias quase idênticas ⇒ a atividade é uma **frente que
   repete a mesma operação em 24 locais**; mede-se por **baia concluída** e acompanha-se o **ritmo
   (baias/dia)**, não um checkbox de micro-passo. O ganho de **curva de aprendizado** (baia 8 sai mais
   rápida que a baia 1) vira o termômetro precoce. (LOB / LBMS Kenley-Seppänen / Takt.)
3. **Passo passivo não é atividade.** Cura do concreto, secagem de stain/tinta = **folga (lag)** entre
   atividades, nunca linha de RDO. (EIA-748 Level of Effort: "minimizar; não distorce desempenho".)
4. **Pacote curto = medição objetiva.** Atividade que cabe num período de relatório mede-se por
   **0/100 ou unidade concluída**, sem disputa de "% feito". Pacote fino demais → **agrupar** e tratar
   o antigo como marco. (Guia EVM federal CMS/HHS; regra 8/80; nada acima de ~1 mês.)
5. **Aderência > detalhe.** Encarregado abandona RDO trabalhoso; campo a mais derruba a qualidade do
   dado (lançamento "de memória"). Unidade natural + binário + foto, no mesmo dia. (Last Planner/PPC.)

## Critérios objetivos aplicados (entra no cronograma só se…)
Para cada serviço/passo: **(a)** carrega fatia relevante de custo/esforço? · **(b)** é frente com
ritmo próprio (equipe/local/janela distintos)? · **(c)** é discreto (tem produto medível) e não
passivo? · **(d)** apontável em unidade natural sem instrumentação extra? · **(e)** é gate de
qualidade/caminho crítico? · **(f)** o número muda alguma decisão? — Se um passo só passa em (a)
fraco e em mais nada, **funde**; se é passivo, vira **lag**; se é gate, **entra mesmo barato**.

## Pareto de custo (orçamento 98, custo R$ 1.017.875)
| Classe | Itens | % custo | Tratamento |
|---|---|---|---|
| **A** (80%) | 1.1 LSF (40%), 1.13 shingle, 1.17a fundação, 1.10 corredores, 1.2 pint. aço, 1.7 pint. interna, 1.5 placa, 1.6 régua | top 8 = 81% | **2–3 atividades** nas 3 maiores; 1–2 nas demais |
| **B** (15%) | 1.16, 1.4, 1.8, 1.17c, 1.9, 1.17b, 1.12 | ~12% | **1 atividade** cada (2 só onde a janela obriga) |
| **C** (5%) | 1.14, 1.17e, 1.15, 1.11, 1.17d, 1.3 | ~5% | **1 atividade** cada, unidade natural |

---

## Cronograma refinado — ~30 atividades (de ~80)

> Unidade de apontamento escolhida pela **aderência** (baia concluída onde o trabalho é por-baia;
> m²/kg em superfície contínua). 🚩 = marco/gate (custo ~0, entra por criticidade). ⏳ = folga passiva.

### Fase 1 — Fundação e infra embutida
| # | Atividade | Serviço | Unidade | Funde / nota |
|---|---|---|---|---|
| 1 | **Preparo do terreno + lastro** | 1.17a | m² | funde locação+escavação+regularização+lastro (1 frente de terra) |
| 2 | **Infra embutida na fundação (elétrica)** | 1.17b | baias (24) | eletrodutos/caixas antes do concreto |
| 3 | **Infra embutida na fundação (hidráulica/dreno)** | 1.17c | baias (24) | esgoto+dreno brita/areia+AF; funde os 3 passos |
| 4 | 🚩 **Liberação pré-concretagem** | 1.17a | gate | checklist: nível + infra tampada. Trava a concretagem |
| 5 | **Armação e formas** | 1.17a | m² | funde ferragem + caixaria |
| 6 | **Concretagem do radier + baldrames** | 1.17a | m² | ⏳ cura 7 dias vira lag até a estrutura |
| 7 | **Corredores em concreto** | 1.10 | m² | funde base+forma+armação+concretagem (1 frente de concreto) |

### Fase 2 — Estrutura e cobertura
| # | Atividade | Serviço | Unidade | Funde / nota |
|---|---|---|---|---|
| 8 | **Painelização LSF (bancada)** | 1.1 | m² painel | a maior frente de MO da obra (~40% do custo total) |
| 9 | **Montagem LSF (verticalização + fixação)** | 1.1 | baias (24) | funde levantar+aprumar+chumbar |
| 10 | **Contraventamento + prumo** 🚩 | 1.1 | baias (24) | trava a estrutura; conclusão = libera fechamento/cobertura |
| 11 | **Verticalização dos pilares roliços** | 1.9 | un (32) | funde recebimento+base+levantar+fixar |
| 12 | **Telhado viga I — fabricação (oficina)** | *subempreit.* | % | terceiros; verba+lucro; roda em paralelo |
| 13 | **Telhado viga I — montagem (campo)** | *subempreit.* | % | terceiros; depende dos apoios prontos |
| 14 | **Base OSB do telhado** | 1.13 | m² | |
| 15 | **Telhamento shingle (manta+telhas+cumeeira)** 🚩 | 1.13 | m² | funde manta/starter/fileiras/cumeeira; fim = telhado estanque |
| 16 | **Pintura do aço estrutural** | 1.2 | m² | funde preparo+primer+demãos |

### Fase 3 — Fechamentos e acabamento
| # | Atividade | Serviço | Unidade | Funde / nota |
|---|---|---|---|---|
| 17 | **Lã de rocha (isolamento)** | 1.17d | m² | no plano do forro; sequência antes do PVC |
| 18 | **Forro de PVC** | 1.17e | m² | funde perímetro+estrutura+réguas |
| 19 | **Fixação da placa cimentícia** | 1.5 | baias (24) | a instalação (o "instalar" do dono) |
| 20 | **Tratamento de junta + basecoat** | 1.5 | baias (24) | funde junta+basecoat (1ª/2ª demão); o acabamento da placa |
| 21 | **Fechamento em régua de pinus** | 1.6 | m² | funde barreira+ripado+régua |
| 22 | **Pintura interna dos fechamentos** | 1.7 | m² | funde selador+demãos; ⏳ depende do basecoat curado |
| 23 | **Stain das paredes externas** | 1.8 | m² | funde demãos; ⏳ secagem 12h = lag interno |
| 24 | **Revestimento pedra moledo** | 1.11 | m² | funde chapisco+assentar+rejunte+limpeza |

### Fase 4 — Esquadrias, cercado e elétrica final
| # | Atividade | Serviço | Unidade | Funde / nota |
|---|---|---|---|---|
| 25 | **Portões das baias (fabricar + instalar)** | 1.4 | un (48) | funde oficina+campo; pode pré-fabricar em paralelo |
| 26 | **Stain dos portões** | 1.3 | m² | funde demãos (na bancada) |
| 27 | **Cercado das baias** | 1.14 | baias (24) | funde corte+montagem+travamento |
| 28 | **Stain do cercado** | 1.15 | baias (24) | in loco; funde demãos |
| 29 | **Ponto hidráulico terminal por baia** | 1.16 | baias (24) | o ponto do bebedouro (1.17c já fez a rede) |
| 30 | **Elétrica final (fiação + pontos + luminárias)** | 1.12 | baias (24) | funde enfiação+quadro+pontos+energização |

🚩 **Marcos de controle (custo 0):** Liberação pré-concretagem (#4) · Estrutura aprumada (#10) ·
Telhado estanque (#15). ⏳ **Folgas passivas (não são RDO):** cura do radier (~7 d), secagem de
stain/tinta (~12 h entre demãos).

## O que foi cortado (e por quê)
- **Passos administrativos/recebimento/marcação/conferência** dos itens A → fundidos na frente
  (não são produção medível; conferência vira gate só nos 3 marcos).
- **Demãos e sub-camadas** (basecoat 1ª/2ª, stain 1ª/2ª/3ª, primer) → 1 atividade por frente de
  pintura; demão é ritmo interno, não linha de RDO.
- **Cura e secagem** → folga (lag), nunca atividade.
- **Sub-passos de verba** (elétrica/hidráulica em 3–8 micro-passos) → 1–2 atividades por janela.

## Resolução das 5 decisões em aberto (decididas como gestor)
1. **1.16 × 1.17c:** 1.17c = **rede/dreno embutido** (atividade #3, por baia); 1.16 = **ponto terminal
   do bebedouro** (atividade #29, por baia). Não há dupla contagem — escopos distintos.
2. **1.17d × 1.17e:** mantidos como **2 atividades em sequência** (#17 lã, #18 forro), cada uma medindo
   o próprio escopo/venda. Sequência evita medir o mesmo avanço 2×.
3. **1.12 pontos de luz:** atividade #30 medida por **baia (24)** — unidade natural, independe da
   contagem fina de pontos. 🔴 A quantidade de pontos para **custo** (12 da planilha vs 1/baia+1/pilar)
   continua a validar com o cliente, mas **não trava o cronograma**.
4. **Telhado viga I:** 2 atividades de subempreitada (#12 fabricação, #13 montagem), medidas por %.
   🔴 Falta o **valor da verba+lucro** e se entrega fab+montagem (se só uma, fundir #12/#13).
5. **Granularidade:** resolvida — ~30 atividades, detalhe concentrado em 1.1/1.17a/1.13 (os itens A).

## Como ler este cronograma (visão de gestor — Linha de Balanço)
Cada atividade por-baia tem um **ritmo-alvo (baias/dia)**. O valor não é só "% concluído" — é a
**inclinação** (velocidade) e se ela **acelera** com a curva de aprendizado. Uma frente que estagna
(linha horizontal) é equipe ociosa esperando a anterior; uma frente mais lenta que o ritmo-alvo é o
alarme precoce de estouro de MO (liga direto no Resultado por Atividade da Fatia 1). Definir os
ritmos-alvo por frente é o próximo passo ao montar as datas (precisa das durações do MPP/XML).
