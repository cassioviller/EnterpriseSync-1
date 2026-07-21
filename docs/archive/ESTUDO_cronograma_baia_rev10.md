# Estudo — Cronograma vinculado ao Orçamento e Medições (Baia REV10)

> Estudo inicial (não implementação). Objetivo: criar o cronograma da obra (esboço em
> `Projeto1.mpp`, MS Project), vinculá-lo ao orçamento e às atividades/insumos, de modo que
> ele **gere as medições para o cliente**. Cobre: (1) como o sistema já faz isso, (2) o esboço
> de cronograma, (3) o mapa cronograma↔orçamento, (4) a mudança da cobertura. — 2026-06-12

---

## 1. Como o sistema (SIGE) já liga Cronograma ↔ Orçamento ↔ Insumos ↔ Medição

A boa notícia: **o mecanismo já existe e está implementado** (Tasks #102/#118). A cadeia completa:

```
Insumo + ComposicaoServico (custo)
   → Servico
      → OrcamentoItem  ──(gerar_proposta)──→  PropostaItem
            → [aprovação da proposta]
                 ├─ ItemMedicaoComercial (IMC)   = valor de venda do item (valor_comercial)
                 └─ TarefaCronograma (via template do serviço)
                       → ItemMedicaoCronogramaTarefa (peso por horas)
                              → RDO atualiza tarefa.percentual_concluido
                                    → % do IMC = média ponderada dos % das tarefas
                                          → valor_medido_periodo = Δ% × valor_comercial
                                                → MedicaoObra → ContaReceber (fatura o cliente)
```

### 1.1 Peças (models.py)
- **`CronogramaTemplate`** (models.py:5108) — conjunto reutilizável de atividades por categoria
  de serviço. Seus **`CronogramaTemplateItem`** (5139) apontam cada um para uma
  **`SubatividadeMestre`** com `duracao_dias`, `quantidade_prevista`, `ordem`, `parent_item_id`
  (hierarquia) e `responsavel`.
- **`Servico.template_padrao_id`** (432) — template default do serviço.
  **`OrcamentoItem.cronograma_template_override_id`** (6272) — override por linha do orçamento
  (precedência: override → template do serviço → nenhum). É propagado p/ `PropostaItem` no
  `gerar_proposta`.
- **`TarefaCronograma`** (4836) — a atividade materializada: `data_inicio/fim`, `duracao_dias`,
  `predecessora_id` (dependência), `percentual_concluido`, `quantidade_total`/`unidade_medida`,
  `servico_id`, `subatividade_mestre_id`, **`gerada_por_proposta_item_id`** (elo até o item),
  `is_cliente`, `responsavel` ('empresa'/'terceiros').
- **`ItemMedicaoComercial` (IMC)** — criado 1:1 por `PropostaItem` na aprovação
  (`handlers/propostas_handlers.py:55`), com `valor_comercial = PropostaItem.subtotal` (a venda).
- **`ItemMedicaoCronogramaTarefa`** — liga IMC ↔ tarefa com **peso** proporcional às horas
  estimadas (`cronograma_proposta.py:674`). Pesos de um IMC somam ~100.

### 1.2 Como "atividade X% concluída" vira "R$ a faturar" (medicao_service.py)
1. `% do IMC = Σ (tarefa.percentual_concluido × peso / Σpeso)` (medicao_service.py:48)
2. `valor_medido_periodo = (perc_atual − perc_acumulado_anterior)/100 × valor_comercial` (:123)
3. `recalcular_medicao_obra` (:275) faz upsert de **uma ContaReceber por obra**
   (`OBR-MED-{obra_id}`) = Σ executado dos IMCs → **é o que fatura o cliente**.
4. O **RDO** (`cronograma_views.py:1106` → `cronograma_engine.atualizar_percentual_tarefa:524`)
   escreve `percentual_concluido = qtd_acumulada / quantidade_total × 100`.

### 1.3 Ponto importante de entendimento (mental model)
> A medição **NÃO fatura "por insumo"**. Ela fatura **% de avanço × valor de VENDA do item**.
> Os insumos/composição definem o **custo** e (via `SubatividadeMestre → SubatividadeMaoObra →
> ComposicaoServico`) a **mão de obra** de cada atividade. O **peso** de cada atividade (por
> horas) é o que distribui o valor de venda do item entre as atividades, para medir o avanço.

Ou seja, "vincular cada atividade aos insumos" no sistema = a atividade aponta para uma
`SubatividadeMestre`/`Servico`, e o serviço tem a composição de insumos. O faturamento sai do
**valor de venda** do item (que já calibramos para bater com o original), repartido por avanço.

### 1.4 Arquivos-chave
| Papel | Arquivo |
|---|---|
| Modelos | `models.py` (4836 Tarefa, 5108 Template, 5139 TemplateItem, 6272 override) |
| Materialização proposta→cronograma | `services/cronograma_proposta.py:453` (`materializar_cronograma`) |
| Preview no orçamento | `services/cronograma_proposta.py:307` (`montar_arvore_preview_orcamento`) |
| Motor datas/dependências/progresso | `utils/cronograma_engine.py` |
| RDO → % tarefa | `cronograma_views.py:1106`, `cronograma_engine.py:524` |
| Medição (% → R$) | `services/medicao_service.py`, `medicao_views.py` |
| Aprovação → IMC + cronograma | `handlers/propostas_handlers.py:15` |

---

## 2. O esboço de cronograma — `Projeto1.mpp` (MS Project)

Autor **Guilherme Angelin**, criado 08/06/2026. Tarefas extraídas (≈30 atividades):

| # | Atividade (MPP) | Fase |
|---|---|---|
| 1 | EXECUÇÃO DE PROJETOS (LSF, TELHADO, PISO, BALDRAME, FUNDAÇÃO) | Projetos |
| 23 | EXECUÇÃO DE PROJETO DE LSF | Projetos |
| 24 | EXECUÇÃO DE PROJETO DE RADIER | Projetos |
| 25 | EXECUÇÃO DE PROJETO HIDRÁULICO E ELÉTRICO | Projetos |
| 5 | ESCAVAÇÃO DE FUNDAÇÃO PARA BALDRAMES | Fundação |
| 3 | EXECUÇÃO DE FERRAGENS PARA FUNDAÇÃO | Fundação |
| 2/6 | EXECUÇÃO DE CAIXARIA (piso de concreto e vigas baldrame) | Fundação |
| 26 | EXECUÇÃO DE PONTOS DE INSTALAÇÕES NA FUNDAÇÃO | Fundação |
| 7/27 | EXECUÇÃO DE CONCRETAGEM DAS FUNDAÇÕES | Fundação |
| 8 | EXECUÇÃO DE CONCRETAGEM DAS CALÇADAS | Concreto |
| 4 | VALIDAÇÃO DO ORÇAMENTO FUNDAÇÃO | Marco |
| **9** | **EXECUÇÃO DE ESTRUTURA METÁLICA PARA TELHADO** | **Telhado (viga I)** |
| **30** | **FABRICAÇÃO DE AÇO PARA TELHADO** | **Telhado (viga I)** |
| 10 | EXECUÇÃO DE ESTRUTURA EM LSF PARA BAIAS | Estrutura LSF |
| 11/28 | PAINELIZAÇÃO DE LSF | Estrutura LSF |
| 12/29 | VERTICALIZAÇÃO DE LSF | Estrutura LSF |
| 13 | CHAPEAMENTO EXTERNO DAS BAIAS | Fechamento |
| 14 | CHAPEAMENTO INTERNO DA BAIAS | Fechamento |
| 15 | EXECUÇÃO DE BASECOAT | Fechamento |
| 16 | PINTURA COM STAIN DAS MADEIRAS PINUS | Acabamento |
| 17 | EXECUÇÃO DE PEDRA MOLEDO | Acabamento |
| 20 | PINTURA DE ESTRUTURA DO TELHADO | Acabamento |
| 18 | EXECUÇÃO DE 1 PONTO DE ILUMINAÇÃO POR BAIA | Elétrica |
| 19 | EXECUÇÃO DE 1 PONTO DE ELÉTRICA EM CADA PILAR | Elétrica |
| 21 | EXECUÇÃO DE PORTÃO DAS BAIAS | Esquadrias |
| 22 | EXECUÇÃO DE TELHADO SINGLE (shingle) | Cobertura |

> Recurso citado: "Máquina para escavar o baldrame". O `.mpp` é binário (OLE2) — só os **nomes**
> das tarefas foram extraídos; datas/durações/predecessoras exigem parser MPP (ex.: `mpxj` via
> Java, não instalado) ou exportar do MS Project para XML/MPX.

---

## 3. Mapa: atividade do cronograma → item do orçamento (já decomposto)

| Atividade (MPP) | Item do orçamento | Obs |
|---|---|---|
| Projeto LSF/Radier/Hidráulico-Elétrico | 1.17a (proj. fundação), serviços de projeto | parte está embutida; pode virar atividade s/ custo direto |
| Escavação / Ferragens / Caixaria / Concretagem fundação | **1.17a Fundação** | já tem os insumos (aço, concreto, forma, equipe) |
| Pontos de instalação na fundação | **1.17c Infra Hidráulica** | esgoto/dreno por baia |
| Concretagem das calçadas | **1.10 Corredores em concreto** | |
| **Estrutura metálica p/ telhado + Fabricação de aço** | **⚠️ FALTA no orçamento** | cobertura viga I — ver §4 |
| Estrutura LSF / Painelização / Verticalização | **1.1 Estrutura LSF** (+1.9 verticalização) | |
| Chapeamento externo | **1.6** régua pinus | |
| Chapeamento interno + Basecoat | **1.5** placa cimentícia + basecoat | |
| Pintura stain madeiras | **1.3 / 1.8 / 1.15** | |
| Pedra moledo | **1.11** | |
| Pintura estrutura do telhado | **1.2** | |
| 1 ponto iluminação/baia + 1 elétrica/pilar | **1.12** (+ infra **1.17b**) | |
| Portão das baias | **1.4** (+ cercado **1.14**) | |
| Telhado shingle | **1.13** | material shingle = cliente |

A maior parte das atividades já tem item/insumo correspondente. **A exceção crítica é a
cobertura (telhado em viga I)** — ver abaixo.

---

## 4. ⚠️ Mudança da cobertura: steel frame → aço laminado viga I

O cronograma tem **"ESTRUTURA METÁLICA PARA TELHADO"** e **"FABRICAÇÃO DE AÇO PARA TELHADO"**
como escopo próprio (aço laminado perfil viga I), separado da **"ESTRUTURA EM LSF PARA BAIAS"**.
Isso **não está refletido no orçamento atual**:

- O item **1.1** do orçamento é "Estrutura Aço **LSF** Z275" (21.900 kg) — é o **light steel frame
  das baias**, não o telhado.
- O **telhado** antes seria em steel frame (LSF); **agora é aço laminado viga I** (perfil
  laminado a quente, mais pesado, preço/kg e fabricação diferentes).
- O projeto de cobertura `COBERTURA_ESTUDO_BAIAS_REV01.pdf` mostra só a **arquitetura** do
  telhado (telha shingle 25%, duas águas, H=1,15m, ~63 × 10 m por bloco), **não** o perfil/peso
  do aço viga I.

**Implicações:**
1. **Falta um item de orçamento** para a estrutura do telhado em viga I (fabricação + montagem),
   com: peso (kg) do aço laminado, preço/kg, perfis (ex.: W150/W200), M.O. de fabricação e
   montagem, solda, pintura/galvanização.
2. Isso muda o **custo e a venda totais** — a viga I laminada costuma custar mais por kg que LSF.
3. Precisa do **projeto estrutural do telhado** (perfis e peso) para orçar — hoje só temos a
   arquitetura. (Há o DWG `EST_PROJBAIAS_FAZMONICA_REV01` ainda não lido — pode conter.)

**Pendência:** definir o escopo do telhado em viga I (peso/perfil/preço) antes de fechar o
cronograma, senão a atividade "estrutura metálica para telhado" não terá item/insumo p/ medir.

---

## 5. O que falta para criar o cronograma e gerar medições (passos)

1. **Resolver a cobertura (§4):** criar o item de orçamento do telhado em viga I (novo serviço +
   insumos) ou decidir mantê-lo fora por ora. Sem isso, a maior atividade do telhado não mede.
2. **Definir as atividades por serviço** = criar `CronogramaTemplate` + `CronogramaTemplateItem`
   (SubatividadeMestre) para cada serviço do orçamento, espelhando as tarefas do MPP, com
   `duracao_dias` e `quantidade_prevista`.
3. **Apontar `template_padrao_id`** em cada Serviço (ou `cronograma_template_override_id` no item
   do orçamento) para o template criado.
4. **Gerar proposta a partir do orçamento** (`gerar_proposta`) → aprovar → o sistema materializa
   `TarefaCronograma` + `ItemMedicaoComercial` + pesos automaticamente.
5. **Datas/dependências:** o MPP tem a sequência (predecessoras). Definir as `predecessora_id`
   conforme o MPP (fundação → estrutura → fechamento → acabamento → cobertura).
6. **Operação:** RDO atualiza % das tarefas → medição por período fatura o cliente.

### Decisões/insumos que preciso de você
- **Telhado viga I:** tem o projeto estrutural (perfis/peso)? Ou um valor de verba para começar?
- **Datas:** quer que eu extraia datas/durações do MPP (precisa exportar o `.mpp` para XML/MPX
  do MS Project) ou definimos as durações na mão a partir dos dias por etapa do Memorial?
- **Granularidade da medição:** medir por **serviço** (17+ itens) ou por **atividade** (≈30
  tarefas do MPP)? Isso define quantos `CronogramaTemplateItem` criar.

---

## 6. Arquivos relevantes (deste estudo)
- `Projeto1.mpp` — esboço do cronograma (MS Project, binário).
- `obra_kabod/.../PROJETOS/COBERTURA_ESTUDO_BAIAS_REV01.pdf` — arquitetura do telhado.
- `obra_kabod/.../PROJETOS/EST_PROJBAIAS_FAZMONICA_REV01 (2).dwg` — estrutural (não lido; pode ter o viga I).
- `attached_assets/Pasted--34-Vincular-or-amento-ao-cronograma...txt` — spec do vínculo orçamento↔cronograma.
- Código: ver tabela §1.4.
- Orçamento já no sistema: `ORC-BAIA-REV10` (id 98), 21 itens.

> Convenções: ✅ confirmado · ⚠️ validar/falta · 🧩 inferência.
