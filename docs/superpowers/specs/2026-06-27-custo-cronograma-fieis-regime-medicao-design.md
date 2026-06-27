# Custo e cronograma fiéis às fontes + regime de medição por obra

> Spec de design. Data: **2026-06-27**.
> Obra-piloto: **Baia (Fazenda Santa Mônica)**. Modelo desenhado para ser geral.

---

## 1. Problema

Hoje o físico-financeiro de uma obra força **custo e cronograma a serem a mesma
coisa**: todo custo precisa "virar tarefa" do cronograma para ser faseado/medido, e
tarefa sem custo desaparece. Isso quebra a fidelidade às duas fontes de verdade e
gera três sintomas:

1. **INDIRETOS** (custo de período: escritório, estadia, refeição, encarregado…)
   não é uma etapa de obra, mas é forçado a "adotar" tarefas do cronograma para
   aparecer — então vaza para o **RDO** e para o **portal do cliente** como se fosse
   um entregável parado em 0%.
2. **Tarefas do cronograma sem custo** (FAZENDA: nivelamento/drenagem, marcação,
   limpeza, desmobilização) só aparecem se alguma etapa de custo as adota; senão
   somem do cronograma.
3. Os números do plano de custo divergem da planilha porque são mantidos à mão num
   fixture, em vez de espelharem a fonte.

As duas fontes de verdade da obra Baia são:

- **`CRONOGRAMA OFICIAL.mpp`** — o cronograma físico (56 tarefas, com hierarquia,
  datas, duração, % físico). Dirige avanço físico, RDO e portal do cliente.
- **`Planilha de Custos REV01 (2).xlsx`, aba `Planilha1`** — o plano de custo por
  etapa/item, com **distribuição mensal de Veks/Fat** (jun–out). Dirige R$ e caixa.

## 2. Objetivos e não-objetivos

**Objetivos**
- O cronograma reflete fielmente o `.mpp` (as 56 tarefas, na hierarquia do outline).
- O custo reflete fielmente a `Planilha1` (etapas, itens, distribuição mensal).
- Custo de período (indiretos e quaisquer custos sem etapa entregável) é cidadão de
  primeira classe do plano de custo: aparece no físico-financeiro, **nunca** no
  RDO/cronograma/portal.
- A ligação custo↔cronograma é **opcional** e governada pelo **regime de medição da
  obra**, de modo que o mesmo modelo sirva para obras de medição fixa (Baia) e para
  obras de medição por % físico.

**Não-objetivos**
- **Não** construir um importador automático de `.xlsx`/`.mpp` (decisão do usuário:
  reconciliação única). O fixture JSON continua sendo o intermediário; o que muda é a
  **estrutura** que ele alimenta e como o sistema a consome.
- Não mexer no cálculo de imposto/lucro já reconciliado (converge: imposto 128.903,
  lucro em caixa 24.976).

## 3. Decisões já tomadas

- **INDIRETOS = R$ 457.000** (as colunas mensais da `Planilha1`, jun–out, são a
  verdade; a coluna "Total" da planilha, 383.000, está subcontada). Total Veks da
  obra = **800.960**; Fat = **550.775**.
- **Baia = regime de medição `fixa`** (fatura por marcos contratuais M1–M5).
- Na Baia, as 11 etapas entregáveis **terão o vínculo opcional** com as tarefas do
  `.mpp` (habilita comparação custo × avanço; não fatura nada).
- Custos de período aparecem **junto** das etapas no detalhe financeiro (tudo numa
  tabela só), sem coluna de % físico.

## 4. O modelo

Dois planos independentes, mais a regra de faturamento da obra.

### 4.1 Plano físico — vem do `.mpp`
As 56 tarefas, materializadas fielmente na **hierarquia do outline** (OBRA →
MOBILIZAÇÃO / BAIAS → FUNDAÇÃO → folhas…). Tarefas `resumo` viram nós-pai; `marco`
vira marco. É o que tem **% físico, RDO e portal do cliente**. Só **etapas
entregáveis** vivem aqui. Tarefa sem custo (FAZENDA, limpeza, desmob) = físico puro,
R$ 0 — continua aparecendo no cronograma/RDO.

### 4.2 Plano de custo — vem da `Planilha1`
Etapa → item → valor, com **distribuição mensal** de Veks/Fat. Cada linha de custo é
de um de dois tipos:

- **Ligada a etapa entregável** (M.O. fundação, material cobertura…): pode/deve se
  vincular às tarefas daquela etapa no `.mpp`.
- **De período / avulsa** (indiretos, escritório, estadia, e quaisquer custos que não
  casam com um entregável): **não pertence a entregável nenhum**; faseada pelos
  próprios meses da `Planilha1`.

Custo de período é **universal** — toda obra tem. Pode haver outros custos sem etapa.

### 4.3 Faturamento — pelo regime da obra
Campo novo **`Obra.regime_medicao`**:

- **`fixa`** — fatura por marcos contratuais (datas/% fixos). ← Baia.
- **`percentual`** — fatura pelo **% físico das etapas** apurado via RDO.

### 4.4 O vínculo custo↔tarefa (condicional)

| Linha de custo | Regime `percentual` | Regime `fixa` (Baia) |
|---|---|---|
| etapa entregável | vínculo **obrigatório** (RDO mede e fatura) | vínculo **opcional** (só compara custo × avanço) |
| custo de período / avulso | **nunca** | **nunca** |

O vínculo existe por um motivo só: deixar o avanço físico (RDO) **medir/faturar** a
etapa. Logo é obrigatório quando o faturamento é por %, e opcional (decorativo, para
comparação) quando o faturamento é fixo.

## 5. Quem aparece onde (regra de ouro)

| Visão | Mostra | Custo de período? |
|---|---|---|
| **RDO / Portal do cliente / avanço físico** | só **etapas entregáveis** (tarefas do `.mpp`) | ❌ nunca |
| **Detalhe financeiro (físico-financeiro)** | **todo o custo** + avanço físico das entregáveis ao lado | ✅ **sempre** (linha de custo, sem % físico) |
| **Faturamento** | marcos (`fixa`) ou % via RDO (`percentual`) | ❌ (indireto não fatura; está embutido no preço) |

No detalhe financeiro, **tudo junto** numa tabela: etapa entregável mostra
*custo + avanço*; custo de período mostra *só custo/caixa* (coluna de % vazia/“—”).
O período jamais vaza para o mundo físico/cliente.

## 6. Mudanças de implementação

Três frentes de código + fixture + testes. Superfície **média**.

### 6.1 Materialização do cronograma — `services/importacao_fisico_financeiro.py`
Hoje `_materializar_cronograma_fisico` é chamado por etapa de custo e cria a árvore a
partir das tarefas que a etapa adota (`tarefas_mpp`). Mudar para:

- **Passo A — árvore física:** materializar **uma `TarefaCronograma` por tarefa do
  `.mpp`** a partir de `cronograma_tarefas` (as 56), com `tarefa_pai_id` reconstruído
  pelo `nivel` (pai = tarefa anterior mais próxima de `nivel−1`), datas, `duracao_dias`,
  `ordem`, `marco`, flag de `resumo`. Guardar mapa `mpp_id → TarefaCronograma.id`.
  Independente de custo. Custo de período **não** entra aqui.
- **Passo B — vínculo opcional:** para cada etapa entregável, criar
  `ItemMedicaoCronogramaTarefa(imc, tarefa, peso=dias)` apontando para as folhas **já
  materializadas** (o `tarefas_mpp` da etapa vira *referência*, não cria folha nova).
  Para custo de período: **não** cria vínculo.

### 6.2 Agrupamento do painel — `services/cronograma_fisico_financeiro.py`
`montar_fisico_financeiro` hoje agrupa etapas pela **raiz da árvore** do cronograma
(`_etapa(raiz)`). Com o outline do `.mpp` a raiz vira "OBRA" para tudo e colapsaria.
Mudar para **agrupar a etapa pelo custo (OSC/ItemMedicaoComercial)**, não pela raiz da
árvore. O faseamento do previsto continua pelas datas das tarefas vinculadas; o caixa
continua pelas datas das linhas de custo (já é assim, `fasear_custo_por_linhas`). Custo
de período aparece como sua própria linha/etapa de custo, faseado pelas linhas mensais,
sem tarefas — sem cair em "não faseado".

### 6.3 Regime de medição — modelo + faturamento
- Adicionar `Obra.regime_medicao` (`'fixa' | 'percentual'`, default `'fixa'` para não
  alterar obras existentes), com migração idempotente (padrão deste repo).
- Faturamento por marcos (`MedicaoContrato`) permanece para `fixa`. Para `percentual`,
  o faturamento segue a medição física (RDO → `MedicaoObra`) — já existe; o regime só
  seleciona qual dirige a receita exibida.

### 6.4 Exclusão de período do físico/portal
Como custo de período **não** é materializado como `TarefaCronograma`, ele já não
aparece no cronograma, RDO nem portal — a exclusão é estrutural (não depende de flag de
visibilidade). Garantir que nenhuma rota de RDO/portal liste linhas de custo de período.

### 6.5 Fixture — `tests/fixtures/cronograma_fisico_financeiro_baias.json`
- `cronograma_tarefas`: já espelha as 56 tarefas do `.mpp` (verificado). Garantir que
  carrega `nivel`, `resumo`, `marco`, `dias`, datas.
- Cada etapa entregável: Veks/Fat e itens fiéis à `Planilha1`; `tarefas_mpp` = suas
  folhas reais do `.mpp` (vínculo opcional da Baia).
- **INDIRETOS** vira **custo de período**: itens com distribuição mensal (`meses_veks`)
  jun–out somando 457.000; **sem** `tarefas_mpp`; marcado como período.
- Remover a adoção das tarefas FAZENDA/limpeza/desmob por INDIRETOS e o resumo `id 2`
  — elas voltam a existir só no plano físico (R$ 0).

### 6.6 Apresentação — detalhe financeiro
Na tabela de etapas do físico-financeiro, linhas de período aparecem junto das demais,
com a coluna de % físico vazia/“—”. (Sem subseção separada — decisão do usuário: tudo
junto para visualizar melhor.)

## 7. Testes e validação

- **Importação:** as 56 tarefas do `.mpp` materializadas na hierarquia do outline;
  FAZENDA/limpeza/desmob presentes no cronograma (R$ 0); INDIRETOS **ausente** do
  cronograma; tarefas-resumo presentes como nós-pai.
- **Painel:** 12 linhas de custo (11 entregáveis + INDIRETOS); agrupamento por etapa de
  custo intacto; veks 800.960 / fat 550.775; caixa mensal = `Planilha1`; INDIRETOS sem
  % físico, com custo/caixa.
- **Faturamento (Baia, `fixa`):** receita pelos marcos M1–M5; imposto 128.903; lucro em
  caixa 24.976 preservados.
- **Regressão de regime:** obra `percentual` (fixture sintético) — etapa entregável sem
  vínculo gera erro/aviso de configuração (vínculo obrigatório); custo de período nunca
  exige vínculo.
- **Portal/RDO:** nenhuma linha de período aparece nas rotas de RDO e portal.

## 8. Riscos e pontos de atenção

- **Reconstrução de hierarquia por `nivel`:** depende da ordem das tarefas em
  `cronograma_tarefas`. Validar que o outline do `.mpp` está em ordem de exibição.
- **Agrupamento por OSC:** revisar todos os consumidores de `montar_fisico_financeiro`
  que hoje assumem "raiz da árvore = etapa" (ex.: realizado_por_etapa, divergência).
- **`regime_medicao` default `fixa`:** confirma que obras existentes (medição física)
  não passam a se comportar como fixa indevidamente — se hoje já medem por %, o default
  da migração para elas deve ser `percentual` (avaliar por presença de medição física).
- **Curva S física do INDIRETOS:** período não tem % físico; o painel não deve exibir
  avanço para ele (só custo/caixa).

## 9. Trabalho futuro (fora deste spec)

- Importador automático `.xlsx` + `.mpp` (substituiria o fixture mantido à mão).
- UI para configurar `regime_medicao` e o vínculo opcional por etapa.
