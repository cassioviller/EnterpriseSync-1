# Design — Espinha Financeira da Obra: Resultado real por Atividade (SIGE)

> Data: 2026-06-14. Status: design para revisão.
> Objetivo: dar ao gestor da obra o **Resultado real por Atividade, diário** — quanto cada
> atividade do cronograma está dando de resultado de verdade enquanto a obra acontece — com
> alarme de produtividade e, adiante, previsão de fechamento.
> Termos: ver `CONTEXT.md` (Avanço realizado, Valor agregado, Custo incorrido, Resultado
> realizado/projetado, Atividade, Serviço). Contexto de domínio do orçamento: ADR 0001 (BDI).

---

## 1. Resultado esperado (a dor que isto resolve)

A mão de obra é paga por **tempo**; a receita é ganha por **quantidade produzida**. Se a
produtividade cai, a obra queima hora-homem mais rápido do que produz quantidade — e o valor que
vai entrar na medição fica menor do que o custo já incorrido. Hoje o gestor só descobre isso no
fechamento. O alvo é mostrar, **por Atividade e por dia**:

- **Valor agregado** (a receber pela produção) − **Custo incorrido** = **Resultado realizado**.
- **Alarme de produtividade**: horas que a produção "ganhou" vs horas realmente gastas.
- (Fatias adiante) **Resultado projetado** no fechamento, lente de **caixa**, aprendizado e
  consolidação de portfólio.

## 2. Princípio de arquitetura

1. **A Atividade (`TarefaCronograma`) é o centro de custo.** Serviço e Obra são níveis de
   agregação (Resultado sobe Atividade → Serviço → Obra).
2. **Read-model, não denormalização espalhada.** Um serviço único
   (`services/resultado_atividade_service.py`) **calcula** o Resultado por Atividade/dia a partir
   das fontes que já existem, em vez de gravar custo redundante em várias tabelas. Isso evita
   inflar o ledger e concentra a regra financeira num lugar testável.
3. **Reusar a espinha de venda/avanço que já existe; construir só o custo-por-atividade.** O
   levantamento de código mostrou que venda+avanço por atividade já funcionam; o buraco é o custo.

## 3. O que já existe (reuso) vs o que falta — aterrado no código

**Já existe e está correto (REUSO):**
- Cronograma → RDO → % → medição: `cronograma_engine.py:524` (`atualizar_percentual_tarefa`),
  `medicao_service.py:48` (`calcular_percentual_item`, média ponderada por peso),
  `medicao_service.py:120` (valor = % × `valor_comercial`).
- Campo de equipe V2 amarra MO à atividade: `views/rdo.py:4396` grava `RDOMaoObra` com
  `tarefa_cronograma_id`; quantidade do dia em `RDOApontamentoCronograma` (`views/rdo.py:4597`).
- **Valor agregado por atividade já é calculável**: `percentual_concluido × peso_norm ×
  valor_comercial` — só não é exposto por atividade ainda.
- Custo diário onerado por funcionário já é persistido: `RDOCustoDiario.custo_total_dia`
  (`services/custo_funcionario_dia.py`) = folha + VA + VT + extra.

**Falta / está quebrado (CONSTRUIR/CONSERTAR):**
- Nenhuma tabela de custo (`GestaoCustoFilho`, `CustoObra`, `GestaoCustoPai`) carrega
  `tarefa_cronograma_id`. `event_manager.py:645` (`lancar_custos_rdo`) agrega por funcionário/dia
  e **descarta** o elo de atividade que o `RDOMaoObra` capturou.
- Material só é reconhecido na compra (nível empresa); alimentação/transporte só chegam à obra;
  "realizado por serviço" de `resumo_custos_obra.py:190` é majoritariamente **rateio por orçado**.
- **Bug na edição do RDO**: `rdo_editar_sistema.py:374` trata `sub_func_{tarefaId}_...` como
  subatividade e **perde** o `tarefa_cronograma_id` ao editar.
- **Materialização não-automática**: `handlers/propostas_handlers.py:131` só materializa cronograma
  se há `cronograma_default_json`; por isso 26 propostas aprovadas e 0 `TarefaCronograma`.
- `RDOSubempreitadaApontamento` tem `tarefa_cronograma_id` (`models.py:5509`) mas **não gera
  custo** — gancho pronto para o telhado viga I.

## 4. Decisões de design (as recomendadas)

- **D1 — Custo incorrido de MO por atividade é COMPUTADO no read-model**, não gravado: ratear o
  `RDOCustoDiario.custo_total_dia` do funcionário pelas **horas que ele lançou em cada atividade**
  naquele dia (`RDOMaoObra.horas_trabalhadas` por `tarefa_cronograma_id`; as horas já vêm
  normalizadas por `utils/rdo_horas.py` e o `custo_total_dia` já é proporcional às horas lançadas em
  `services/custo_funcionario_dia.py:81`, então o rateio fecha sem perder nem inflar). Usa o custo
  **onerado real**, não tarifa nominal. → Fatia 1 sem migration.
  - **Ociosidade NÃO é medida.** Tempo pago e ocioso (chuva, espera) fica **embutido** no custo da
    atividade via as horas apontadas — é parte real do custo de fazê-la. O **índice de
    produtividade** (D5) é o sinal de ineficiência, sem exigir que alguém cronometre o ócio. O
    mensalista pago e não apontado a nenhuma atividade no dia cai automaticamente em `ocioso_mensal`
    (nível obra), sem entrada manual.
- **D2 — Custo direto não-MO é etiquetado na origem** com `tarefa_cronograma_id` (nova FK opcional
  em `GestaoCustoFilho`); **custo compartilhado é rateado** por hora-homem/atividade/dia dentro do
  read-model. → Fatia 2.
- **D3 — Subempreitada vira custo por atividade** ligando `RDOSubempreitadaApontamento` ao ledger
  (verba+lucro), reusando seu `tarefa_cronograma_id`. → Fatia 2 (telhado viga I).
- **D4 — Resultado = competência** (Custo incorrido), separado da lente de **caixa** (Realizado/
  Previsto, ADR 0003). Duas lentes, nunca fundidas.
- **D5 — Alarme primário em R$ (universal):** `custo MO real incorrido` vs `custo MO orçado para o
  avanço` (= `%concluído × custo MO orçado da atividade`, vindo das linhas `MAO_OBRA` do snapshot da
  composição × quantidade × peso). Alarme quando `real > orçado-para-o-avanço`. Funciona para
  qualquer modelo de precificação (R$/m², hora, verba). **Refino em horas** (horas ganhas ÷ horas
  reais) só onde a MO foi precificada **em hora** (coeficiente em `h`, ex.: item 1.1 LSF) — na Baia
  a maioria dos itens precifica MO em R$/m², sem hora-homem orçada.

## 5. As fatias

Cada fatia é end-to-end e usável sozinha; cada uma só depende das anteriores. Cada fatia terá seu
próprio plano de implementação (writing-plans) quando chegar a vez.

### Fatia 1 — Resultado por Atividade (só Mão de Obra) + alarme de produtividade  *(tracer bullet)*

**Objetivo:** para uma obra rodando no cronograma, mostrar Resultado realizado por Atividade/dia
considerando **só MO** (o maior custo variável), com o alarme.

**Habilitação (pré-requisito, parte da fatia):**
- Materializar o cronograma da obra Baia (criar template/atividades dos serviços da Baia e
  materializar) para sair do estado dormente. A obra precisa existir (proposta aprovada) e estar
  em `versao_sistema='v2'`.
- **Consertar o bug da edição do RDO** (`rdo_editar_sistema.py`): reconhecer `cron_tarefa_*` e
  gravar `tarefa_cronograma_id` na edição — senão o custo-por-atividade se corrompe ao editar.

**Dados:** nenhuma migration. (O elo já está em `RDOMaoObra.tarefa_cronograma_id` e o custo em
`RDOCustoDiario`.)

**Serviço novo:** `services/resultado_atividade_service.py`, funções puras e testáveis:
- `valor_agregado_atividade(tarefa, ate_data)` = `percentual_concluido/100 × peso_norm ×
  ItemMedicaoComercial.valor_comercial` (reusa a lógica de `medicao_service`).
- `custo_mo_atividade(tarefa, ate_data)` = Σ, por dia, do rateio:
  `RDOCustoDiario.custo_total_dia × (horas do func. na atividade / horas totais do func. no dia)`,
  usando `RDOMaoObra.tarefa_cronograma_id` + `RDOMaoObra.horas_trabalhadas`.
- `resultado_realizado_atividade(tarefa)` = valor agregado − custo MO (Fatia 1: só MO).
- `custo_mo_orcado_atividade(tarefa)` = Σ subtotais `MAO_OBRA` do `composicao_snapshot` do
  `OrcamentoItem` × quantidade × peso da atividade (em R$, disponível para qualquer precificação).
- `alarme_mo(tarefa)` **(primário, R$)**:
  - `orcado_para_avanço` = `(percentual_concluido/100) × custo_mo_orcado_atividade`.
  - `real` = `custo_mo_atividade` (acumulado).
  - **estouro** quando `real > orcado_para_avanço`; índice R$ = `orcado_para_avanço / real`
    (<1 = no vermelho).
- `indice_horas(tarefa)` **(refino, só se MO precificada em hora)**:
  - `horas_ganhas` = `(quantidade_acumulada / quantidade_total) × horas_orçadas`, onde
    `horas_orçadas` = Σ coeficientes dos insumos `MAO_OBRA` com `unidade='h'` × quantidade × peso.
  - `horas_reais` = Σ `RDOMaoObra.horas_trabalhadas` da atividade. `indice = ganhas / reais`.
  - Indisponível quando a MO do item não tem insumo horário (mostra só o alarme em R$).
- **D6 — O peso Serviço→Atividade é o da medição (REUSO).** Tanto a venda quanto o custo orçado da
  atividade são divididos pelo `ItemMedicaoCronogramaTarefa.peso` que **já existe** para a medição —
  uma única fonte de verdade. Editor manual já pronto: `medicao_views.py:344` (`vincular_tarefa`),
  tela `templates/medicao/gestao_itens.html`, validação soma=100% (`medicao_service.py:68`). **Sem
  campo nem regra nova.**

**UI:** tela/aba "Resultado por Atividade" da obra (nova view `resultado_views.py` ou aba na obra),
listando por atividade: qtd prevista×produzida, Valor agregado, Custo incorrido (MO), Resultado
realizado, índice de produtividade com selo de alarme. Rollup por Serviço e Obra.

**Critérios de aceite:** com RDOs lançados por atividade, o Resultado e o índice batem com cálculo
manual; editar um RDO não quebra o vínculo; a soma do Custo incorrido das atividades = custo de MO
**apontado** da obra (o pago não apontado a nenhuma atividade fica em `ocioso_mensal`, nível obra,
automático — sem medição manual).

**Fora de escopo (Fatia 1):** material/alimentação/transporte, subempreitada, previsão, caixa.

### Fatia 2 — Custos não-MO por atividade (+ subempreitada / telhado viga I)

**Dados:** add FK nullable `tarefa_cronograma_id` em `GestaoCustoFilho` (migration). Opcional: idem
em `CustoObra` se necessário para combustível.

**Lógica:**
- **Direto** (material consumido na atividade, equipamento dedicado): handlers/lançamento passam
  `tarefa_cronograma_id` ao `registrar_custo_automatico` (`utils/financeiro_integration.py`).
  Botões na Atividade (como o de equipe) para lançar compra/material direto.
- **Compartilhado** (alimentação, transporte, VA/VT): fica no nível obra/dia e o read-model
  **rateia** por hora-homem/atividade/dia. Sem digitação extra no campo.
- **Subempreitada → custo:** ligar `RDOSubempreitadaApontamento` (que já tem
  `tarefa_cronograma_id`) ao ledger. **Telhado viga I**: entra como **verba única + lucro** por
  atividade (subempreitada), sem decompor insumos; ver `ESPACO_telhado_viga_i_baia_rev10.md` (manter
  a venda total da obra travada via recálculo de margem).

`custo_incorrido_atividade` passa a somar MO (Fatia 1) + direto + rateio compartilhado +
subempreitada.

### Fatia 3 — Motor de previsão (EVM)

`Resultado projetado` no fechamento por atividade e obra: CPI = índice de produtividade,
SPI = avanço real ÷ planejado, **EAC** (estimativa no término) e margem projetada. Alerta com a
alavanca ("faltam +N un/HH ou realocar equipe"). Puro cálculo sobre o read-model da Fatia 1–2.

### Fatia 4 — Lente de caixa

Curva de **Realizado/Previsto** no tempo (ADR 0003: variação, não saldo): Valor agregado → medição
→ ContaReceber vs Custo → ContaPagar, para mostrar quando a obra fica no vermelho de **caixa**.
Lente distinta do Resultado (competência).

### Fatia 5 — Inteligência

- **Loop de aprendizado:** produtividade real observada realimenta `SubatividadeMestre.
  meta_produtividade`/`duracao_estimada_horas` → o próximo orçamento fica mais preciso.
- **Roll-up de portfólio:** Resultado/EVM/caixa consolidados por todas as obras → visão da empresa.

## 6. Riscos e bugs conhecidos (a tratar)

- **Bug edição RDO** (`rdo_editar_sistema.py:374`) — corrigido na Fatia 1.
- **Materialização não-automática** — para a Baia, materializamos explicitamente; rever se vira
  automático é decisão à parte (possível ADR).
- **Peso semeado por divisão igual**: quando `SubatividadeMestre.duracao_estimada_horas` está vazio,
  a materialização semeia o peso por divisão igual (`cronograma_proposta.py:677`). Mitigação: ajustar
  na **tela de medição que já existe** (D6) — não é campo novo. Para o refino em horas (1.1), as
  horas vêm da composição (D5), não do catálogo.
- **Gate v2**: todo o módulo exige `versao_sistema='v2'`; a obra Baia precisa estar em v2.

## 7. Fora de escopo (YAGNI agora)

Reescrever o pipeline de custo legado (`CustoObra`); migrar dados de obras antigas (texto livre)
para o nível atividade (não dá para retroajustar — só greenfield); unificar subatividade↔tarefa.

## 8. Testes

- Unit do `resultado_atividade_service` (fórmulas: valor agregado, rateio MO, índice) com fixtures.
- Cenário de regressão do bug de edição (editar RDO mantém `tarefa_cronograma_id`).
- Cenário end-to-end na Baia: materializar cronograma → lançar RDOs por atividade → conferir
  Resultado e alarme.
