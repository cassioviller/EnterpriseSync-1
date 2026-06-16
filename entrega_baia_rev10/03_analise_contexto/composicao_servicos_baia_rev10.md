# Composição de serviços — Orçamento Baia REV10

> Todos os itens 1.1–1.17 convertidos em serviço + composição de insumos, com coeficiente e **como foi calculado** em cada um.
> Modelo: **Custo + BDI**. Composição reproduz o CUSTO (colunas F/G); imposto/lucro por item vão no BDI. **Jornada 8 h/dia, 22 dias/mês.**
> M.O. com equipe → modelo hora (Forma A, uma linha por pessoa). M.O. sem equipe na planilha → taxa na unidade do serviço, marcada para conversão futura.
> 🔴 = erro/inconsistência na planilha (modelei o correto e documentei) · ⚠️ validar · 🧩 inferência.

## Tabela de preços/hora da equipe (jornada 8h × 22 dias = 176 h/mês)

| Função | R$/h | Base |
|---|---:|---|
| Encarregado | 36,36 | tabela do usuário (≈ 6.400/mês ÷ 176) |
| Montador líder | 31,82 | ≈ 5.600/mês ÷ 176 |
| Montador | 26,14 | ≈ 4.600/mês ÷ 176 |
| Ajudante | 20,46 | ≈ 3.600/mês ÷ 176 |
| Pedreiro | 25,00 | diária R$200 ÷ 8h (aba Fundação) |
| Meio oficial | 18,75 | diária R$150 ÷ 8h |
| **Equipe LSF (6 pessoas)** | **161,38** | soma enc+líder+2 montador+2 ajudante |

BDI por item (das colunas K–AE): **Material** lucro = 25% (1.1), 22% (1.17), 20% (demais), imposto 0%. **M.O.** imposto 13% + lucro 28% (15% no 1.17).

---

## 1.1 — Estrutura em Aço LSF Z275  ·  serviço em **kg** (qtd 21.900)
Custo proposta: Material R$331.345,50 · M.O. R$153.300 (R$7/kg).

| Insumo | Tipo | Un | Coef | Preço | Como calculei |
|---|---|---|---:|---:|---|
| Aço LSF galvanizado Z275 | Material | kg | 1,07 | 13,50 | `F10=(21900×13,5)×1,07`. Coef 1,07 = 1 kg + 7% de perda. |
| Fixadores/parafusos LSF | Material | vb | 0,6849 /kg | 15.000 | `+15000` na F10 ÷ 21.900 kg = R$0,685/kg (ou vb único de R$15.000). |
| Encarregado | M.O. | h | 0,022 | 36,36 | Produtividade técnica da equipe (0,022 h/kg por pessoa ≈ 60–75 dias-equipe p/ 21.900 kg, consistente com aba `Aço`). |
| Montador líder | M.O. | h | 0,022 | 31,82 | idem |
| Montador | M.O. | h | 0,022 | 26,14 | idem (linha 1 de 2) |
| Montador | M.O. | h | 0,022 | 26,14 | idem (linha 2 de 2) |
| Ajudante | M.O. | h | 0,022 | 20,46 | idem (linha 1 de 2) |
| Ajudante | M.O. | h | 0,022 | 20,46 | idem (linha 2 de 2) |

**Validação:** Material recalc = 14,445 + 0,685 = R$15,13/kg × 21.900 = **R$331.345** ✅ bate F10.
M.O. recalc = 0,022 × 161,38 = **R$3,55/kg** × 21.900 = R$77.754. Proposta = R$153.300 (R$7/kg). 🔴 **A composição técnica dá metade**: os R$7/kg da proposta embutiam margem/folga sobre o custo real. Como é Custo+BDI, a diferença aparece como margem. *(Para reproduzir os R$7/kg exatos, o coeficiente seria 0,0434 h/kg.)*

---

## 1.2 — Pintura do aço estrutural  ·  **m²** (qtd 1.173)
| Insumo | Tipo | Un | Coef | Preço | Como calculei |
|---|---|---|---:|---:|---|
| M.O. pintura aço | M.O. | m² | 1 | 35,00 | `G11=35` — taxa comercial da proposta. Sem equipe/produtividade aplicável na aba `Pintura` (escopo de 360 m²). Reutilizável como taxa; converter p/ h ao definir pintor + rendimento. |

---

## 1.3 — Pintura/Stain portão Pinus  ·  **m²** (qtd 161)
| Insumo | Tipo | Un | Coef | Preço | Como calculei |
|---|---|---|---:|---:|---|
| Stain (verba) | Material | vb | 1 | 800,00 | `H12=ROUND(F12,2)=800` — material entra **global**, não por m². |
| M.O. pintura/Stain portão | M.O. | m² | 1 | 35,00 | `G12=35`/m². |

🔴 Inconsistência da planilha: no custo o Stain é R$800 global, mas no preço de venda vira `K12×161 = R$161.000`. Modelei como global (custo); registrar no De-Para.

---

## 1.4 — Portão em Pinus  ·  **un** (qtd 48 = 24×2)
| Insumo | Tipo | Un | Coef | Preço | Como calculei |
|---|---|---|---:|---:|---|
| Ferragens/trilho portão | Material | un | 1 | 125,00 | `F13×E13` — material por unidade. |
| M.O. montagem portão | M.O. | un | 1 | 350,00 | `G13=350`/un. Madeira fornecida pelo cliente. (Aba `Instalação Portas`: R$116,78/un técnico — proposta cobra 350/un.) |

---

## 1.5 — Fechamento interno placa cimentícia  ·  **m²** (qtd 900)
| Insumo | Tipo | Un | Coef | Preço | Como calculei |
|---|---|---|---:|---:|---|
| M.O. placa cimentícia + basecoat | M.O. | m² | 1 | 45,00 | `G14=45`/m². Material fornecido pelo cliente. (Aba `Plaqueamento Interno`: custo técnico R$12,14/m²; proposta 45 = margem.) |

---

## 1.6 — Fechamento externo régua pinus  ·  **m²** (qtd 660)
| Insumo | Tipo | Un | Coef | Preço | Como calculei |
|---|---|---|---:|---:|---|
| M.O. régua de pinus | M.O. | m² | 1 | 45,00 | `G15=45`/m². Madeira do cliente. (Aba `Plaqueamento Externo`: R$40,53/m² técnico.) |

---

## 1.7 — Pintura fechamentos internos  ·  **m²** (qtd 900)  ⚠️
| Insumo | Tipo | Un | Coef | Preço | Como calculei |
|---|---|---|---:|---:|---|
| M.O. pintura interna (cimento queimado) | M.O. | m² | 1 | 45,00 | `G16=45`/m². |

⚠️ Na planilha a unidade está como `vb` mas a quantidade é `=E14`=900 m². **Corrigi a unidade para m²** (área), conforme recomendado.

---

## 1.8 — Pintura Stain paredes externas  ·  **m²** (qtd 660)
| Insumo | Tipo | Un | Coef | Preço | Como calculei |
|---|---|---|---:|---:|---|
| Stain (verba) | Material | vb | 1 | 800,00 | `H17=ROUND(F17,2)=800` global (aqui o lado venda também é global — consistente). |
| M.O. Stain externa | M.O. | m² | 1 | 30,00 | `G17=30`/m². |

---

## 1.9 — Verticalização de pilares roliços  ·  **un** (qtd 32)  🔴
| Insumo | Tipo | Un | Coef | Preço | Como calculei |
|---|---|---|---:|---:|---|
| M.O. verticalização pilar | M.O. | un | 1 | 568,18 | `G18=(50000/2)/44` = metade de R$50.000 ÷ 44 pilares. |

🔴 Custo unitário calculado sobre **44** pilares, mas a quantidade vendida é **32** → total R$18.181,82 (= 568,18 × 32 ≈ 36% de R$50.000). Material = 0 (sapatas/concreto provavelmente no 1.17 ou cliente). Validar se a base 44 vs 32 é intencional.

---

## 1.10 — Corredores em concreto  ·  **m²** (qtd 500,4)
| Insumo | Tipo | Un | Coef | Preço | Como calculei |
|---|---|---|---:|---:|---|
| Concreto usinado | Material | m³ | 0,20 | 550,00 | `(500,4×0,2)` = 100,08 m³ ÷ 500,4 m² = 0,20 m³/m² (espessura 0,20 m). |
| Extra/ferramenta concreto | Material | m² | 1 | 3,00 | `+1500` ÷ 500,4 m² = R$3,00/m² (ou vb R$1.500). |
| M.O. concretagem | M.O. | m² | 1 | 25,00 | `(500,4×25)` = R$25/m². |
| Taxa fixa concretagem | M.O. | m² | 1 | 5,00 | `+2500` ÷ 500,4 = R$5,00/m² (ou vb R$2.500). |

**Validação:** Mat = (0,20×550 + 3,00) × 500,4 = R$56.545 ✅. M.O. = (25+5) × 500,4 = R$15.012 ✅ (≈ F19/G19).

---

## 1.11 — Revestimento pedra moledo  ·  **m²** (qtd 40)
| Insumo | Tipo | Un | Coef | Preço | Como calculei |
|---|---|---|---:|---:|---|
| M.O. revestimento pedra moledo | M.O. | m² | 1 | 230,00 | `G20=230`/m². Qtd `=80/2`=40 m². Pedra fornecida pelo cliente. (Aba `Revestimento`: R$62,98/m² técnico.) |

---

## 1.12 — Instalação de pontos de luz  ·  **vb** (qtd 1)  ⚠️
| Insumo | Tipo | Un | Coef | Preço | Como calculei |
|---|---|---|---:|---:|---|
| Ponto de luz (material) | Material | un | 12 | 400,00 | `(12×400)` — 12 pontos × R$400. |
| Adicional elétrico | Material | vb | 1 | 1.500,00 | `+1500`. |
| Quadro/diversos | Material | vb | 1 | 610,00 | `+610`. |
| M.O. instalação elétrica | M.O. | vb | 1 | 6.500,00 | `G21=6500` — verba global. |

⚠️ Fórmula usa **12 pontos**, mas a descrição diz "um ponto por baia **e** um por pilar" (24 baias + ~44 pilares ≈ 68). Modelei os 12 da fórmula; validar quantidade. Luminárias pelo cliente.

---

## 1.13 — Telha Shingle  ·  **m²** (qtd 1.173)
| Insumo | Tipo | Un | Coef | Preço | Como calculei |
|---|---|---|---:|---:|---|
| M.O. instalação telha shingle | M.O. | m² | 1 | 85,00 | `G22=85`/m². Material shingle não incluso (ver "itens não inclusos" do 1.17). |

---

## 1.14 — Cercado das baias  ·  **un** (qtd 24)
| Insumo | Tipo | Un | Coef | Preço | Como calculei |
|---|---|---|---:|---:|---|
| Fixadores cercado | Material | un | 1 | 100,00 | `F23×E23` — fixadores por baia. Réguas/pilares do cliente. |
| M.O. cercado | M.O. | un | 1 | 450,00 | `G23=450`/un. |

---

## 1.15 — Pintura Stain do cercado  ·  **un** (qtd 24)  🔴
| Insumo | Tipo | Un | Coef | Preço | Como calculei |
|---|---|---|---:|---:|---|
| Stain (verba) | Material | vb | 1 | 800,00 | `H24=ROUND(F24,2)=800` global. |
| M.O. pintura cercado | M.O. | un | 1 | 400,00 | `G24=400`/un. |

🔴 Mesma inconsistência do 1.3: custo material R$800 global, venda `K24×24 = R$24.000`. Modelei global; registrar no De-Para.

---

## 1.16 — Ponto hidráulico por baia  ·  **un** (qtd 24)  🔴
| Insumo | Tipo | Un | Coef | Preço | Como calculei |
|---|---|---|---:|---:|---|
| Material ponto hidráulico | Material | un | 1 | 867,10 | `F25=667×1,3` = R$667 +30%. |
| M.O. ponto hidráulico | M.O. | un | 1 | 100,00 | `G25=100`/un. |

🔴 Na planilha o material é contado **uma única vez** para as 24 baias (`H25=ROUND(F25,2)=867,10`, sem ×24), enquanto a M.O. é ×24. A descrição é "um ponto **por baia**". **Modelei como R$867,10/un (×24 = R$20.810)**, que é o tecnicamente correto. O original conta só 1× (R$867,10) — registrar a diferença no De-Para.

---

## 1.17 — Pacote complementar REV10  ·  **vb** (qtd 1)  🧩 pendente de decomposição
| Insumo | Tipo | Un | Coef | Preço | Como calculei |
|---|---|---|---:|---:|---|
| Material pacote complementar | Material | vb | 1 | 52.322,00 | `F26=49322+3000`. |
| M.O. pacote complementar | M.O. | vb | 1 | 40.242,00 | `G26=37742+2500`. BDI lucro 15% (não 28%). |

🧩 Engloba fundação, aço engenheirado, painelização, fechamentos, isolamento (lã de rocha), forro PVC, infra elétrica/hidráulica. Decompor depois usando `Fundação` (mat R$71.286 / geral R$49.714) e `Instalações` (atenção: está **zerada** — multiplica por área `RESUMO!C6`=0). Marcado como verba até decomposição.

---

## Catálogo consolidado de insumos

**Materiais:** Aço LSF Z275 (kg, 13,50) · Fixadores LSF (vb, 15.000) · Stain (vb, 800) · Ferragens/trilho portão (un, 125) · Fixadores cercado (un, 100) · Concreto usinado (m³, 550) · Extra concreto (vb, 1.500) · Ponto de luz material (un, 400) · Adicional elétrico (vb, 1.500) · Quadro elétrico (vb, 610) · Material ponto hidráulico (un, 867,10) · Material pacote 1.17 (vb, 52.322).

**Mão de obra (hora):** Encarregado 36,36 · Montador líder 31,82 · Montador 26,14 · Ajudante 20,46 · Pedreiro 25,00 · Meio oficial 18,75.

**Mão de obra (taxa, converter p/ h depois):** pintura aço 35/m² · pintura portão 35/m² · montagem portão 350/un · placa cimentícia 45/m² · régua pinus 45/m² · pintura interna 45/m² · Stain externa 30/m² · verticalização pilar 568,18/un · concretagem 25/m² + 2.500 · revestimento pedra 230/m² · elétrica 6.500/vb · telha shingle 85/m² · cercado 450/un · pintura cercado 400/un · ponto hidráulico 100/un · pacote 1.17 40.242/vb.

## Itens registrados para o De-Para (erros/decisões da planilha)
- **1.3 / 1.15** — Stain R$800: custo global vs venda ×qtd. Modelado global.
- **1.16** — material contado 1× na planilha; modelado ×24 (correto).
- **1.9** — base 44 pilares, qtd 32.
- **1.12** — 12 pontos na fórmula vs descrição (baias + pilares).
- **1.7** — unidade vb→m² (corrigida).
- **1.1** — custo técnico R$3,55/kg vs proposta R$7/kg (margem → BDI).
