# Cronograma refinado (Pareto POR SERVIÇO + Linha de Balanço) — Obra Baia REV10

> Decisão de engenharia: **o que vale metrificar** no cronograma da Baia. Parte da quebra completa
> (`2026-06-14-quebra-atividades-baia-rev10.md`, ~80 passos = dicionário de método) e a enxuga.
> **Base do Pareto (corrigida): a importância de cada PASSO dentro do SEU serviço** — não o custo do
> serviço. Em cada serviço, os poucos passos vitais viram atividade; o resto funde. Serviço barato com
> 2 frentes vitais distintas → 2 atividades; serviço caro que é 1 frente só → 1 atividade.
> Data: 2026-06-14. Este é o cronograma-de-controle de referência.

## Princípio (por que e como enxugar)
1. **Pareto é POR SERVIÇO.** Dentro de cada serviço, mantém-se o passo que é **frente vital** do
   avanço daquele serviço; o passo de baixa importância **funde** na frente vizinha. O tamanho em R$
   do serviço **não** decide o detalhe — a importância do passo no serviço decide.
2. **Regra de seleção do passo:** vira atividade só se **(peso ≥ ~20% do serviço)** **E** **(frente
   distinta** — equipe, janela de tempo, ou gate diferente). Passo <20% **ou** da mesma frente contínua
   → funde. Passo **passivo** (cura, secagem) → **folga (lag)**, nunca linha de RDO. **Gate** de
   qualidade/caminho crítico → entra mesmo com peso baixo.
3. **Obra repetitiva = Linha de Balanço.** 24 baias idênticas: mede-se por **baia concluída** e pelo
   **ritmo (baias/dia)**; a curva de aprendizado (baia 8 mais rápida que a 1) é o alarme precoce.
4. **Aderência > detalhe.** Unidade natural + binário + foto, no mesmo dia. Campo a mais derruba a
   qualidade do dado. (EVM federal: pacote fino demais deve ser **agrupado**.)
5. **O peso do passo no serviço = o peso da medição** (`ItemMedicaoCronogramaTarefa.peso`, D6). A
   coluna "peso" abaixo já é o que reparte a venda do serviço entre suas atividades — soma 100%/serviço.

## Cronograma refinado — 30 atividades + 3 gates
> Unidade escolhida pela aderência (baia onde é por-baia; m²/kg/un em superfície/contagem).
> 🚩 = gate (peso 0). Peso = importância da atividade **no seu serviço** (soma 100% por serviço).

### Fase 1 — Fundação e infra embutida
| # | Atividade | Serviço | Unid. | Peso no serviço | Funde |
|---|---|---|---|---|---|
| 1 | Preparo do terreno + lastro | 1.17a | m² | 33% | locação+escavação+regularização+lastro (1 frente de terra) |
| 2 | Infra elétrica embutida | 1.17b | baias | 100% | eletrodutos/caixas antes do concreto |
| 3 | Infra hidráulica/dreno embutida | 1.17c | baias | 100% | esgoto+dreno+AF |
| 4 | 🚩 Liberação pré-concretagem | 1.17a | gate | — | checklist nível+infra tampada (trava concretagem) |
| 5 | Armação e formas | 1.17a | m² | 38% | ferragem+caixaria |
| 6 | Concretagem do radier | 1.17a | m² | 29% | ⏳ cura 7d = lag |
| 7 | Corredores — preparo e formas | 1.10 | m² | 47% | base+forma+tela |
| 8 | Corredores — concretagem | 1.10 | m² | 53% | ⏳ cura = lag |

### Fase 2 — Estrutura e cobertura
| # | Atividade | Serviço | Unid. | Peso | Funde |
|---|---|---|---|---|---|
| 9 | Painelização LSF (bancada) | 1.1 | m² painel | 50% | recebimento/marcação fundidos |
| 10 | Montagem LSF (verticalização+fixação+contravent.) | 1.1 | baias | 50% | 1 frente de montagem in loco |
| 11 | 🚩 Estrutura aprumada | 1.1 | gate | — | libera fechamento e cobertura |
| 12 | Verticalização dos pilares roliços | 1.9 | un (32) | 100% | recebimento+base+levantar+fixar |
| 13 | Telhado viga I — fabricação (oficina) | *subempr.* | % | 50% | terceiros; paralelo |
| 14 | Telhado viga I — montagem (campo) | *subempr.* | % | 50% | terceiros; depende dos apoios |
| 15 | Base OSB do telhado | 1.13 | m² | 25% | |
| 16 | Telhamento shingle (manta+telhas+cumeeira) | 1.13 | m² | 75% | starter/fileiras/cumeeira |
| 17 | 🚩 Telhado estanque | 1.13 | gate | — | fim da cumeeira |
| 18 | Pintura do aço estrutural | 1.2 | m² | 100% | preparo+primer+demãos (1 frente) |

### Fase 3 — Fechamentos e acabamento
| # | Atividade | Serviço | Unid. | Peso | Funde |
|---|---|---|---|---|---|
| 19 | Lã de rocha (isolamento) | 1.17d | m² | 100% | |
| 20 | Forro de PVC | 1.17e | m² | 100% | perímetro+estrutura+réguas (1 frente) |
| 21 | Fixação da placa cimentícia | 1.5 | baias | 55% | o "instalar" do dono |
| 22 | Tratamento de junta + basecoat | 1.5 | baias | 45% | junta+basecoat (frente de acabamento) |
| 23 | Fechamento em régua de pinus | 1.6 | m² | 100% | barreira+ripado+régua (1 frente) |
| 24 | Pintura interna dos fechamentos | 1.7 | m² | 100% | selador+demãos; ⏳ basecoat curado |
| 25 | Stain das paredes externas | 1.8 | m² | 100% | demãos; ⏳ secagem 12h = lag |
| 26 | Revestimento pedra moledo | 1.11 | m² | 100% | chapisco+assentar+rejunte (1 frente) |

### Fase 4 — Esquadrias, cercado e elétrica final
| # | Atividade | Serviço | Unid. | Peso | Funde |
|---|---|---|---|---|---|
| 27 | Portões — fabricação (oficina) | 1.4 | un (48) | 60% | corte+quadro+contravent.+lixa+roldana |
| 28 | Portões — instalação (campo) | 1.4 | un (48) | 40% | trilho+pendurar+regulagem |
| 29 | Stain dos portões | 1.3 | m² | 100% | demãos (bancada) |
| 30 | Cercado das baias | 1.14 | baias | 100% | corte+montagem+travamento (1 frente) |
| 31 | Stain do cercado | 1.15 | baias | 100% | demãos (in loco) |
| 32 | Ponto hidráulico terminal por baia | 1.16 | baias | 100% | bebedouro (rede já no #3) |
| 33 | Elétrica final (fiação+pontos+luminárias) | 1.12 | baias | 100% | enfiação+quadro+pontos+energização |

⏳ **Folgas passivas (não são RDO):** cura do radier (~7d), cura dos corredores, secagem de stain/tinta (~12h entre demãos).

## O que mudou ao corrigir a base (custo → importância no serviço)
- **Corredores (1.10):** 1 → **2** atividades — preparo e concretagem são **2 frentes vitais distintas**
  do serviço (antes eu dava 1 só porque o serviço era "só 7% do custo" — base errada).
- **Portões (1.4):** 1 → **2** — fabricação (oficina) e instalação (campo) são frentes distintas e
  vitais (60%/40%), podem correr em paralelo.
- **LSF (1.1):** 3 → **2** — verticalização+fixação+contraventamento são **uma frente contínua** de
  montagem; não eram 3 frentes só porque o serviço é caro.
- **Pintura do aço, forro, pedra, régua:** 1 atividade — são **uma frente contínua** cada, mesmo tendo
  vários passos (os passos têm peso, mas não são frentes distintas).

## Decisões em aberto — resolvidas como gestor
1. **1.16 × 1.17c:** 1.17c = rede/dreno embutido (#3); 1.16 = ponto terminal do bebedouro (#32). Sem dupla contagem.
2. **1.17d × 1.17e:** 2 atividades em sequência (#19 lã, #20 forro), cada uma seu escopo/venda.
3. **1.12:** medido por baia (#33); a contagem fina de pontos é questão de **custo** (validar com cliente), não trava o cronograma.
4. **Telhado viga I:** #13/#14 por %; 🔴 falta valor da verba+lucro e se entrega fab+montagem (se só uma, fundir).
5. **Granularidade:** resolvida pela regra peso≥20% + frente distinta.

## Como ler (Linha de Balanço)
Cada atividade por-baia tem um **ritmo-alvo (baias/dia)**; o sinal de gestão é a **inclinação** (velocidade)
e se ela **acelera**. Frente estagnada = equipe ociosa esperando a anterior; frente mais lenta que o alvo
= alarme precoce de estouro de MO (liga no Resultado por Atividade da Fatia 1). Definir os ritmos-alvo
precisa das durações (exportar `Projeto1.mpp` → XML).
