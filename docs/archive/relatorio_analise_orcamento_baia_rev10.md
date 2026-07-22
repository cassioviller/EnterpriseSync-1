# Relatório de análise — Orçamento Baia REV10 × Plano de conversão

> Análise técnica do arquivo `Orçamento - Baia - REV10.xlsx` confrontada com `plano_regras_conversao_orcamento_baia_rev10.md`.
> Não foi alterado o Excel. Nada foi implementado no sistema. Convenções de confiança: ✅ confirmado na planilha · ⚠️ precisa validar · 🔴 divergência/erro na planilha · 🧩 inferência.

> **⚠️ ATUALIZAÇÃO (2026-06-12) — este relatório é a análise inicial.** Desde então:
> o item **1.17 foi decomposto** em 5 serviços reais (Fundação 92k + Elétrica 17,4k +
> Hidráulica 19k + Isolamento 6,9k + Forro 12,9k = **R$148,2k**); a **fundação foi enxugada**
> (40→20 dias, sem escavação dupla: R$121k→R$92k); elétrica/hidráulica foram **firmadas pela
> análise dos projetos** (PDFs) + SINAPI; e foi feita a **validação dupla** do orçamento
> inteiro, que confirmou o **erro de R$128k no item 1.3** (custo real coerente ≈ **R$1,073 mi**
> vs R$1,145 mi exibido). Para o contexto consolidado + como o app calcula o orçamento, ver
> **`CONTEXTO_orcamento_baia_rev10.md`**. Scripts: `scripts/decompor_117_*.py` e
> `scripts/validar_orcamento_baia_rev10.py`.

---

## 1. Resumo executivo

**Veredito: APROVADO COM AJUSTES.**

O plano acerta na arquitetura (Insumo → Preço → Serviço → Composição → Proposta → Validação) e nas regras de unidade técnica. A maior parte da interpretação dos itens 1.1–1.17 está correta. Porém a análise do Excel revelou **três fatos estruturais que o plano não considerou** e que mudam a estratégia de conversão:

1. **Existe uma camada inteira de preço de venda / BDI escondida (colunas K a AE).** As colunas F e G da proposta são **CUSTO**. O preço de venda é calculado à parte: material por `custo / (1 − lucro)` (lucro 20–25%) e mão de obra por `custo / (1 − imposto − lucro)` com imposto 13% e lucro 28% (markup de M.O. = 69,49%). O plano trata F/G como se fossem o valor final e ignora completamente impostos e lucro. **Isso precisa entrar no modelo** (o sistema já tem BDI/lucro/impostos — ver `docs/superpowers/specs/2026-05-29-orcamento-bdi-lucro-impostos-proposta.md`).

2. **O "Valor Total do Projeto" exibido (R$ 1.145.717,42) é o CUSTO, não o preço de venda.** A planilha soma as colunas de custo (H/I/J) na linha 27; as colunas de venda (M/N/O) existem mas **não são somadas nem exibidas**. Há ambiguidade real sobre qual é o número que foi proposto ao cliente. **Decisão do usuário necessária.**

3. **A planilha NÃO usa produtividade hora/unidade em lugar nenhum.** Todas as abas técnicas calculam mão de obra por *duração*: custo mensal da equipe → custo/dia (÷22) → × nº de dias da etapa → ÷ quantidade = custo unitário. Não existe nenhum coeficiente `h/kg` ou `h/m²`, nem o valor "R$ 161,37/h" nem "0,022 h/kg" citados no plano — **esses números não estão no arquivo**. Logo, converter para `h/unidade` significa *inventar* uma base de horas. O plano deve assumir isso explicitamente (decisão de jornada) ou modelar como "equipe·dia" / taxa direta R$/unidade.

Além disso, há **erros/inconsistências na própria planilha** (materiais "verba global" no custo mas multiplicados pela quantidade no preço de venda; item 1.16 com material contado uma única vez para 24 baias) que precisam ser decididos antes da importação, senão o sistema vai "herdar o erro".

---

## 2. Mapa das abas e função de cada uma

| # | Aba | Papel real | Alimenta a proposta? | Estado |
|---|---|---|---|---|
| 1 | `Proposta Comercial ` | Planilha comercial final. Itens 1.1–1.17. **Contém custo (F–J) E venda/BDI (K–AE).** | — (é o destino) | ✅ completa |
| 2 | `Memorial de calculo` | Levantamento de áreas (R19–R26), tempo de execução por etapa em dias (R30–R39), instalações hidráulicas/louças (R42–R56), portas (R57–R62), cálculo de carga térmica de ar-condicionado (R66–R75). Contém também blocos de PISO/PAREDE porcelanato que **parecem template de outro projeto** (não aparecem na proposta). | Indiretamente (áreas e dias) | ⚠️ mistura projeto + template |
| 3 | `RESUMO CUSTOS ` | Tenta consolidar custos puxando das abas técnicas (`='Aço '!D46` etc.) + viagem/hospedagem/dias. | **Não.** Total = R$ 293.614 ≠ proposta. Área C6=0 → vários `#DIV/0!`. | 🔴 stale/parcial |
| 4 | `Fundação ` | Memória de custo da fundação: equipe, visita, materiais (escavação, concreto, bomba, aço, madeira). Custo geral R$ 49.714 / total mat. R$ 71.286. | Alimenta item 1.17 (parcial) | ⚠️ |
| 5 | `Aço ` | Memória da estrutura LSF: equipe 9 pessoas (R$ 41.640/mês), 75 dias, custo geral R$ 145.050 ÷ 26.000 kg = **R$ 5,58/kg**. | Referência do item 1.1 | ✅ chave p/ reconciliar |
| 6 | `Cobertura` | Memória da equipe de cobertura/telha. Custo geral R$ 9.277. | Referência item 1.13 | ⚠️ área=0 |
| 7 | `Plaqueamento Interno ` | Equipe + levantamento de área interna (1.502,13 m²) → R$ 12,14/m². | Referência itens 1.5/1.7 | ✅ |
| 8 | `Plaqueamento Externo` | Equipe + área externa (526,61 m²) → R$ 40,53/m². | Referência item 1.6 | ✅ |
| 9 | `Revestimento ` | Equipe + levantamento de piso/azulejo. R$ 62,98/m². | Referência item 1.11 | ⚠️ |
| 10 | `Muro` | Equipe pedreiro + materiais radier. R$ 126/m² / R$ 190/m². | (muro não está claro na proposta) | ⚠️ |
| 11 | `Instalação Portas` | Empreitada portas: 27 portas, R$ 116,78/un. | Referência item 1.4 | ⚠️ |
| 12 | `Pintura ` | Empreitada pintura R$ 35.000, R$ 108,95/m² (360 m²). | Referência itens 1.2/1.3/1.8 | ⚠️ |
| 13 | `Instalações` | Hidráulica + elétrica (louças/metais, R$/m²). Multiplicado por `RESUMO!C6`=0 → resultados zerados. | Referência itens 1.12/1.16/1.17 | 🔴 zerada |
| 14 | `PROJETO` | **Motor de precificação de serviço de engenharia da "Fundamentos" (autor Renan Ruiz, 2021).** Custo CLT = salário×1,86, custo/hora ÷220, jornada **8,75 h/dia**, imposto 12,9%, margem 25%. Template genérico, **vazio (sem horas lançadas) e desconectado** desta obra. | **Não** | 🔴 template não usado |
| 15 | `TOPOGRAFIA` | Igual ao PROJETO, com topógrafo/ajudante. Mesmo template, vazio. | **Não** | 🔴 template não usado |

**Conclusão do mapa:** a proposta (F/G) foi **digitada à mão** (são literais, não fórmulas que puxam das abas). As abas técnicas são memórias de cálculo de apoio, várias em estado meio-preenchido/quebrado, e **não há um fio de fórmula** ligando-as à proposta. Portanto, a fonte de verdade para conversão é a aba **Proposta Comercial**; as abas técnicas servem só como evidência para decompor itens (e nem sempre batem).

---

## 3. Itens 1.1 a 1.17 — fórmula, origem, interpretação, serviço/insumos sugeridos

Notação: célula da proposta entre parênteses. F=custo unit. material, G=custo unit. M.O., E=quantidade. Markup material `S` (lucro) e M.O. `Z`=imposto 13% / `AA`=lucro 28%.

### 1.1 — Estrutura em Aço Galvanizado LSF (R10) ✅
- **Fórmula:** `F=((21900*13.5)*1.07)+15000 = 331.345,50` · `G=7*21900 = 153.300` · E=1 vb · venda mat. lucro 25% → 441.794; venda M.O. → 259.830,51.
- **Origem:** material = **cálculo físico** (21.900 kg × R$13,50 × 1,07 perda + R$15.000 fixadores). M.O. = **taxa arbitrada R$7/kg** (número fixo).
- **Interpretação / ponto crítico (o do plano):** 🔴 **O R$7/kg não vem de coeficiente nenhum.** Não existe "0,022 h/kg" nem "R$161,37/h" na planilha — são números externos. A aba `Aço ` calcula o custo da equipe por *duração*: 9 pessoas × R$41.640/mês ÷ 22 = R$1.892,73/dia × 75 dias + visitas = R$145.050 ÷ **26.000 kg** = **R$5,58/kg**. A proposta usa **21.900 kg** e arredonda a M.O. para **R$7/kg** (embute folga/margem operacional sobre os 5,58). Recomendação: cadastrar M.O. como insumo **"M.O. montagem LSF (orçada)"** unidade **kg**, preço R$7/kg, coef. 1 — ou, se quiser horas, **decidir jornada e nº de pessoas** (inferência, marcar 🧩).
- **Serviço:** Montagem de estrutura LSF · unidade **kg** (qtd 21.900) *ou* vb conforme proposta.
- **Insumos:** Aço LSF Z275 (kg, R$13,50, coef 1,07 incl. perda) · Fixadores/parafusos LSF (vb, R$15.000) · M.O. montagem LSF (kg, R$7) **ou** Equipe LSF (equipe·dia).

### 1.2 — Pintura aço estrutural (R11) ✅
- `F=0` · `G=35` · E=1173 m². Origem: **taxa arbitrada R$35/m²**. Material não considerado (provável fornecimento do cliente ⚠️).
- **Serviço:** Pintura aço estrutural · m². **Insumo:** M.O. pintura aço (m², R$35) ou pintor (h) se houver jornada 🧩.

### 1.3 — Pintura + Stain em portão de Pinus (R12) 🔴
- `F=800` · `H=ROUND(F12,2)=800` (**material verba global, NÃO ×161**) · `G=35` · E=161 m².
- 🔴 **Inconsistência interna:** no custo, material = R$800 global; no preço de venda `M12 = K12*E12 = 1000 × 161 = 161.000`. Ou seja, o material entra como R$800 no custo e R$161.000 na venda. **Erro da planilha** — decidir se o Stain é R$800 global ou R$800/m².
- **Serviço:** Pintura/Stain portão Pinus · m². **Insumos:** Stain (verba R$800 ⚠️) · M.O. pintura (m², R$35).

### 1.4 — Execução de Portão em Pinus (R13) ✅
- `E=24*2=48 un` · `F=125/un` · `G=350/un`. Material e M.O. **por unidade** (×48). Origem: arbitrada/un.
- **Serviço:** Portão Pinus · un. **Insumos:** Ferragens/trilho portão (un, R$125) · M.O. montagem portão (un, R$350). Madeira = cliente.

### 1.5 — Fechamento interno placa cimentícia (R14) ✅
- `F=0` · `G=45` · E=900 m². Arbitrada R$45/m². Relaciona `Plaqueamento Interno` (lá o custo é R$12,14/m² → o R$45 embute margem). **Serviço:** m². **Insumo:** M.O. placa cimentícia (m², R$45). Material = cliente ⚠️.

### 1.6 — Fechamento externo régua pinus (R15) ✅
- `F=0` · `G=45` · E=660 m². Igual padrão. Relaciona `Plaqueamento Externo` (R$40,53/m² técnico). Madeira = cliente.

### 1.7 — Pintura fechamentos internos (R16) ⚠️
- `D='vb'` mas `E='=E14'=900` (puxa a área do 1.5) · `G=45/m²`. 🔴 **Unidade `vb` com quantidade em m²** — confirma o alerta do plano. Recomendação: cadastrar como **m²**.

### 1.8 — Pintura Stain paredes externas (R17) ⚠️
- `F=800` · `H=ROUND(F17,2)=800` global · `G=30` · E=660 m². Aqui o lado de venda **também** é global (`M17=ROUND(K17,2)=1000`) → **consistente** (diferente do 1.3/1.15). Stain = verba R$800; M.O. R$30/m².

### 1.9 — Verticalização de pilares roliços (R18) 🔴
- `E=44-12=32` · `D='vb'` · `G=(50000/2)/44=568,18` → `I=568,18×32=18.181,82`.
- 🔴 **Confirmado:** custo unitário calculado sobre **44** pilares (metade de R$50.000 ÷ 44), mas quantidade vendida = **32**. Resultado: vende-se R$18.181 (≈ 36% de R$50.000). Validar se é intencional (provável "uso metade do escopo de 44 mas só cobro 32") ⚠️. Marcar 🧩.

### 1.10 — Corredores em concreto (R19) ✅
- `F=(500.4*0.2)*550+1500 = 56.544` · `G=(500.4*25)+2500 = 15.010` · E=1 vb.
- Origem: **físico**. Concreto = 500,4 m² × 0,20 m = 100,08 m³ × R$550 + R$1.500. M.O. = 500,4 m² × R$25 + R$2.500.
- **Serviço:** Corredor concreto · m² (500,4) ou vb. **Insumos:** Concreto usinado (m³, R$550, coef 0,20 m³/m²) · Ferramenta/extra concreto (vb R$1.500) · M.O. concretagem (m², R$25, ou h) · Taxa fixa concretagem (vb R$2.500).

### 1.11 — Revestimento pedra moledo (R20) ✅
- `E=80/2=40 m²` · `F=0` · `G=230/m²`. Arbitrada. **Serviço:** m². **Insumo:** M.O. revestimento pedra (m², R$230). Pedra = cliente ⚠️.

### 1.12 — Pontos de luz (R21) ⚠️
- `F=(12*400)+1500+610 = 6.910` · `G=6.500` global · E=1 un.
- 🔴 **Confirmado:** fórmula usa **12 pontos**, mas a descrição diz "um ponto por baia **e** um por pilar". Com 24 baias + ~44 pilares isso seria ~68 pontos, não 12. **Validar quantidade real** (provável subdimensionamento ou os "12" são só as baias de um setor) ⚠️.
- **Serviço:** Instalação pontos de luz · un/vb. **Insumos:** Ponto de luz (un, R$400, coef 12) · Adicional (vb R$1.500) · Quadro/outros (vb R$610) · M.O. elétrica (vb R$6.500). Luminárias = cliente.

### 1.13 — Telha Shingle (R22) ✅
- `F=0` · `G=85/m²` · E=1173 m². Arbitrada. **Serviço:** m². **Insumo:** M.O. telha shingle (m², R$85). Material shingle não incluso (ver "itens não inclusos" do 1.17).

### 1.14 — Cercado das baias (R23) ✅
- `E=24 un` · `F=100/un` · `G=450/un`. Material (fixadores) e M.O. por unidade. Réguas/pilares = cliente.

### 1.15 — Pintura Stain do cercado (R24) 🔴
- `F=800` · `H=ROUND(F24,2)=800` global · `G=400/un` · E=24 un.
- 🔴 **Mesma inconsistência do 1.3:** custo material = R$800 global, mas venda `M24=K24×E24 = 1000×24 = 24.000`. Decidir se Stain é global ou por unidade.

### 1.16 — Ponto hidráulico por baia (R25) 🔴
- `F=(667*1.3)=867,10` · `H=ROUND(F25,2)=867,10` (**material contado UMA vez, não ×24**) · `G=100/un` · `I=100×24=2.400` · E=24 un.
- 🔴 **Provável erro:** descrição é "um ponto hidráulico **por baia**", quantidade 24, M.O. corretamente ×24, mas o **material (R$867,10) é contado uma única vez para as 24 baias**. O plano interpretou como "R$867,10/un" — na planilha é R$867,10 **total**. Validar: material deveria ser ×24 (= R$20.810)? ⚠️🔴
- **Serviço:** Ponto hidráulico · un. **Insumos:** Material hidráulico/ponto (un, R$667 + 30%) · M.O. ponto hidráulico (un, R$100).

### 1.17 — Pacote complementar (R26) 🧩
- `F=49322+3000 = 52.322` · `G=37742+2500 = 40.242` · E=1 VB. Markup material lucro 22%, M.O. lucro **15%** (não 28%).
- **Pacote sem decomposição** englobando: fundação, aço engenheirado, painelização, fechamentos, isolamento (lã de rocha), forro PVC, infra elétrica, hidráulica, etc. + lista de "itens NÃO inclusos" (telha shingle, louças, metais, madeiras, pré-moldados, esquadrias).
- **Recomendação:** confirma o plano — **decompor antes** usando `Fundação`, `Instalações`, `Memorial`. Se não houver tempo, cadastrar como **"Pacote complementar REV10"** vb com `[pendente de decomposição]`. As abas `Fundação` (R$71.286 mat / R$49.714 geral) e `Instalações` ajudam, mas a `Instalações` está **zerada** (multiplica por área `RESUMO!C6=0`).

**Totais (linha 27):** Material (custo) **H27 = 458.788,60** · M.O. (custo) **I27 = 558.928,82** · **J27 = 1.145.717,42**. O "Valor Total do Projeto" (B31) repete J27 = **custo**. Soma de venda (M/N/O) não existe na planilha.

---

## 4. Lista de insumos candidatos

Marcações: preço entre parênteses; observações de confiança.

**Materiais**
| Insumo | Tipo | Un. | Preço | Origem / obs |
|---|---|---|---|---|
| Aço LSF galvanizado Z275 | Material | kg | 13,50 | 1.1 ✅ |
| Perda/sobra aço (fator) | — | % | 7% | embutido no coef. 1,07 do aço ✅ |
| Fixadores/parafusos LSF | Material | vb | 15.000 | 1.1 ✅ |
| Stain (verba) | Material | vb | 800 | 1.3/1.8/1.15 ⚠️ global vs /un a decidir |
| Ferragens/trilho portão | Material | un | 125 | 1.4 ✅ |
| Fixadores cercado | Material | un | 100 | 1.14 ✅ |
| Concreto usinado | Material | m³ | 550 | 1.10 ✅ |
| Extra/ferramenta concreto | Material/Outros | vb | 1.500 | 1.10 ✅ |
| Ponto de luz (material) | Material | un | 400 | 1.12 ⚠️ qtd |
| Adicional elétrico | Material | vb | 1.500 | 1.12 |
| Quadro/diversos elétrico | Material | vb | 610 | 1.12 |
| Material ponto hidráulico | Material | un | 667 (+30%) | 1.16 🔴 contagem |
| Pacote material complementar | Material | vb | 52.322 | 1.17 🧩 decompor |

**Mão de obra** (na planilha sempre como **taxa R$/unidade ou verba**, nunca hora)
| Insumo | Un. proposta | Preço | Origem |
|---|---|---|---|
| M.O. montagem LSF | kg | 7,00 | 1.1 (arbitrado; técnico ≈5,58/kg) |
| M.O. pintura aço | m² | 35 | 1.2 |
| M.O. pintura/Stain portão | m² | 35 | 1.3 |
| M.O. montagem portão | un | 350 | 1.4 |
| M.O. placa cimentícia | m² | 45 | 1.5 |
| M.O. régua pinus | m² | 45 | 1.6 |
| M.O. pintura interna | m² | 45 | 1.7 |
| M.O. Stain externa | m² | 30 | 1.8 |
| M.O. verticalização pilar | un/vb | 568,18 | 1.9 🔴 base 44/32 |
| M.O. concretagem | m² | 25 + 2.500 fixo | 1.10 |
| M.O. revestimento pedra | m² | 230 | 1.11 |
| M.O. elétrica (luz) | vb | 6.500 | 1.12 |
| M.O. telha shingle | m² | 85 | 1.13 |
| M.O. cercado | un | 450 | 1.14 |
| M.O. pintura cercado | un | 400 | 1.15 |
| M.O. ponto hidráulico | un | 100 | 1.16 |
| M.O. pacote complementar | vb | 40.242 | 1.17 🧩 |

**Equipe (das abas técnicas — base alternativa por equipe·dia)** 🧩
Diárias observadas: Encarregado, Montador líder (R$250/dia), Montador (R$160–180/dia), Ajudante (R$120–160/dia), Pedreiro (R$150–200/dia), Meio Oficial (R$120–150/dia), Engenheiro residente. Refeição R$30–50/dia. **Custo equipe LSF = R$41.640/mês = R$1.892,73/dia (9 pessoas).** Estas diárias só são úteis se o usuário optar por modelo equipe·dia/hora em vez das taxas R$/un da proposta.

**Custos indiretos (tipo "Outros")** — presentes nas memórias, **embutidos** nas taxas da proposta, não isolados:
Viagem/km (R$0,80/km), Pedágio, Hospedagem Airbnb (R$3.500/mês), Visita técnica "Guilherme" (R$500–1.000/diária), Frete ferramentas.

---

## 5. Lista de serviços candidatos

| Cód. | Serviço | Un. sugerida | Qtd | Origem |
|---|---|---|---|---|
| S1.1 | Estrutura LSF Z275 | kg (ou vb) | 21.900 | 1.1 |
| S1.2 | Pintura aço estrutural | m² | 1.173 | 1.2 |
| S1.3 | Pintura/Stain portão pinus | m² | 161 | 1.3 |
| S1.4 | Portão em pinus | un | 48 | 1.4 |
| S1.5 | Fechamento interno placa cimentícia | m² | 900 | 1.5 |
| S1.6 | Fechamento externo régua pinus | m² | 660 | 1.6 |
| S1.7 | Pintura fechamentos internos | **m²** (não vb) | 900 | 1.7 ⚠️ |
| S1.8 | Pintura Stain paredes externas | m² | 660 | 1.8 |
| S1.9 | Verticalização pilares roliços | un (ou vb) | 32 | 1.9 ⚠️ |
| S1.10 | Corredores em concreto | m² (ou vb) | 500,4 | 1.10 |
| S1.11 | Revestimento pedra moledo | m² | 40 | 1.11 |
| S1.12 | Instalação pontos de luz | un/vb | 12? | 1.12 ⚠️ |
| S1.13 | Instalação telha shingle | m² | 1.173 | 1.13 |
| S1.14 | Cercado das baias | un | 24 | 1.14 |
| S1.15 | Pintura Stain cercado | un | 24 | 1.15 |
| S1.16 | Ponto hidráulico por baia | un | 24 | 1.16 |
| S1.17 | Pacote complementar REV10 | vb | 1 | 1.17 🧩 decompor |

---

## 6. Regras de coeficiente — confirmadas e corrigidas

**Confirmadas pelo plano:**
- ✅ Material: `coef = qtd material / qtd serviço`. Ex.: concreto 0,20 m³/m² (1.10) ✅.
- ✅ Verba fechada: unidade vb, qtd 1, coef 1, preço = valor da verba (1.17, e materiais "global").
- ✅ Repetição de insumo (Forma A) é aceita pelo sistema — confirmado pela própria proposta, que repete `ROUND` por linha. Operacionalmente, repetir linhas é melhor para auditar equipe.

**Correções / acréscimos (importantes):**

1. 🔴 **Mão de obra NÃO tem coeficiente em horas na planilha.** Toda M.O. é taxa `R$/unidade` (R$/kg, R$/m², R$/un) ou verba. A regra `coef h/un = (R$/un) / (R$/h da equipe)` do plano (seção 5.1) usa um "R$/h" que **não existe no arquivo**. Duas saídas honestas:
   - **(Recomendada p/ fidelidade)** insumo de M.O. com **unidade igual à da proposta** (kg, m², un) e preço = a taxa, coef 1. Sem inventar horas.
   - **(Técnica, se quiser produtividade)** modelar **equipe·dia**: coef = `dias da etapa / quantidade` (dias vêm do `Memorial!TEMPO DE EXECUÇÃO`, ex. aço = 5600/700 = 8 dias). Converter para horas só após **decidir jornada** (as abas PROJETO/TOPOGRAFIA usam **8,75 h/dia e 220 h/mês**, único lugar com base horária).

2. 🔴 **Falta a regra de markup/BDI.** Coeficiente reproduz o **custo**; o preço de venda precisa de regra separada:
   - Material: `venda = custo / (1 − lucro)`, lucro 20–25% (1.1=25%, maioria 20%, 1.17=22%).
   - M.O.: `venda = custo / (1 − imposto − lucro)`, imposto 13%, lucro 28% (1.17=15%). → markup 69,49%.
   Mapear esses % para os campos de imposto/lucro do orçamento do sistema (que já existem).

3. ⚠️ **"Perda" como fator, não como insumo.** O 7% do aço está como fator 1,07 multiplicando o material — melhor cadastrar como coeficiente 1,07 no insumo aço (ou campo de perda), não como insumo separado.

---

## 7. Pontos de decisão para o usuário

1. **Custo × venda:** o sistema deve reproduzir o **custo** (F/G) e aplicar imposto/lucro por cima (recomendado, casa com o BDI já existente), ou gravar direto o **preço de venda** (K/L)? E o "Valor do Projeto" exibido deve ser custo (R$1,15 mi) ou venda (≈R$1,7 mi somando M/N/O)?
2. **Modelo de M.O.:** taxa R$/unidade fiel à proposta (rápido, fiel) **ou** equipe·dia/hora (técnico, exige jornada 8 vs 8,75 h e composição de equipe)?
3. **Item 1.1:** manter R$7/kg como taxa, ou recompor pela equipe da aba `Aço ` (R$5,58/kg com 26.000 kg)? E qual quantidade vale: 21.900 kg (proposta) ou 26.000 kg (memória)?
4. **Materiais "verba global" (1.3, 1.15):** R$800 de Stain é global ou por m²/unidade? (Hoje custo=global, venda=×qtd → inconsistente.)
5. **Item 1.16:** material hidráulico é R$867,10 **total** (como está) ou R$867,10 **por baia** (×24)?
6. **Item 1.9:** vender 32 com custo calculado sobre 44 é intencional?
7. **Item 1.12:** são 12 pontos de luz mesmo, ou faltou contar baias+pilares?
8. **Item 1.17:** decompor agora (usando abas técnicas) ou importar como verba com `[pendente]`?
9. **Insumos repetidos:** confirmar Forma A (linhas repetidas) no importador — ou cair na Forma B (coef consolidado) se houver limite.

---

## 8. Melhor plano de execução (ajustado)

1. **Fonte de verdade = aba `Proposta Comercial`, colunas F/G (custo).** Abas técnicas só como evidência de decomposição; não confiar nos totais delas (estão stale/zerados).
2. **Resolver as 6 decisões críticas** (seção 7) **antes** de gerar qualquer cadastro — especialmente custo×venda e modelo de M.O.
3. **Congelar os erros conhecidos** num "De-Para" com flag (não corrigir silenciosamente; registrar valor original + valor sugerido).
4. **Gerar as 7 abas de importação** (seção 9) com rastreabilidade célula-a-célula.
5. **Camada de markup explícita**: gravar imposto% e lucro% por item conforme colunas R/S/Z/AA, para o BDI do sistema reproduzir o preço de venda.
6. **Validação dupla:** recalcular custo (deve bater H/I/J com diferença ≈ 0) **e** recalcular venda (deve bater M/N/O). Status OK/Revisar/Divergente por item.
7. **Item 1.17 por último**, decomposto ou marcado como pendente.
8. Só então propor a importação no sistema (com aprovação).

---

## 9. Estrutura sugerida para importação

**`01_INSUMOS`** — `id_insumo | nome | tipo (Material/MaoObra/Equip/Outros) | unidade_tecnica | descricao | fracionavel | origem_celula`

**`02_PRECOS_INSUMOS`** — `id_insumo | preco_vigente | unidade_comercial | fator_comercial | data | fonte (proposta/aba técnica) | obs`

**`03_SERVICOS`** — `id_servico | codigo_proposta (1.x) | nome | unidade_venda | quantidade | imposto_pct | lucro_pct | origem_item`

**`04_COMPOSICAO_SERVICOS`** — `id_servico | id_insumo | coeficiente | unidade_coef | tipo_origem (físico/arbitrado/verba/memorial/pacote) | obs` *(uma linha por pessoa quando equipe — Forma A)*

**`05_ORCAMENTO_PROPOSTA`** — `codigo | descricao | unidade | quantidade | custo_unit_mat | custo_unit_mo | total_mat_custo | total_mo_custo | total_mat_venda | total_mo_venda`

**`06_VALIDACAO`** — `codigo | custo_mat_orig (H) | custo_mat_recalc | dif_R$ | dif_% | custo_mo_orig (I) | custo_mo_recalc | venda_orig (O) | venda_recalc | status`

**`07_DE_PARA_ORIGINAL`** — `codigo | celula_qtd (Exx) | celula_mat (Fxx) | celula_mo (Gxx) | formula_original | aba_tecnica | flag_erro_planilha | decisao_usuario`

---

## 10. Veredito final

**APROVADO COM AJUSTES.** O plano é uma base sólida e as regras de unidade/rastreabilidade estão corretas. Para ser executável com fidelidade ao orçamento, precisa incorporar: **(a)** a camada de imposto/lucro (BDI) das colunas K–AE; **(b)** o fato de que o "valor do projeto" exibido é custo, não venda; **(c)** o reconhecimento de que a planilha não usa produtividade em horas — logo o modelo `h/unidade` do plano é uma escolha, não um dado; e **(d)** o tratamento explícito dos erros internos da planilha (1.3, 1.15, 1.16, e a base 44/32 do 1.9, e os 12 pontos do 1.12) via De-Para com decisão do usuário, sem corrigir em silêncio.
