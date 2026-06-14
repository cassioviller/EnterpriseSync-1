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
  naquele dia (`RDOMaoObra.horas_trabalhadas` por `tarefa_cronograma_id`). Não exige mexer
  (destrutivamente) no pipeline de geração de custo, e usa o custo **onerado real**, não uma tarifa
  nominal. → Fatia 1 sem migration.
- **D2 — Custo direto não-MO é etiquetado na origem** com `tarefa_cronograma_id` (nova FK opcional
  em `GestaoCustoFilho`); **custo compartilhado é rateado** por hora-homem/atividade/dia dentro do
  read-model. → Fatia 2.
- **D3 — Subempreitada vira custo por atividade** ligando `RDOSubempreitadaApontamento` ao ledger
  (verba+lucro), reusando seu `tarefa_cronograma_id`. → Fatia 2 (telhado viga I).
- **D4 — Resultado = competência** (Custo incorrido), separado da lente de **caixa** (Realizado/
  Previsto, ADR 0003). Duas lentes, nunca fundidas.
- **D5 — Alarme = índice de produtividade** (horas ganhas ÷ horas reais), o indicador que antecipa
  o prejuízo enquanto ainda dá para reagir.

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
- `indice_produtividade(tarefa)`:
  - `horas_ganhas` = `(quantidade_acumulada / quantidade_total) × horas_previstas_atividade`,
    onde `horas_previstas` = `SubatividadeMestre.duracao_estimada_horas` (as mesmas horas do peso).
  - `horas_reais` = Σ `RDOMaoObra.horas_trabalhadas` da atividade.
  - `indice = horas_ganhas / horas_reais` (<1 = no vermelho); **alarme** quando `< 0,9`.

**UI:** tela/aba "Resultado por Atividade" da obra (nova view `resultado_views.py` ou aba na obra),
listando por atividade: qtd prevista×produzida, Valor agregado, Custo incorrido (MO), Resultado
realizado, índice de produtividade com selo de alarme. Rollup por Serviço e Obra.

**Critérios de aceite:** com RDOs lançados por atividade, o Resultado e o índice batem com cálculo
manual; editar um RDO não quebra o vínculo; soma dos Resultados das atividades = Resultado do
serviço.

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
- **Peso/horas frágil**: se `SubatividadeMestre.duracao_estimada_horas` está vazio, o peso e as
  "horas ganhas" caem em divisão igual (`cronograma_proposta.py:677`) e distorcem o resultado.
  Popular horas previstas faz parte da montagem do cronograma da Baia.
- **Gate v2**: todo o módulo exige `versao_sistema='v2'`; a obra Baia precisa estar em v2.

## 7. Fora de escopo (YAGNI agora)

Reescrever o pipeline de custo legado (`CustoObra`); migrar dados de obras antigas (texto livre)
para o nível atividade (não dá para retroajustar — só greenfield); unificar subatividade↔tarefa.

## 8. Testes

- Unit do `resultado_atividade_service` (fórmulas: valor agregado, rateio MO, índice) com fixtures.
- Cenário de regressão do bug de edição (editar RDO mantém `tarefa_cronograma_id`).
- Cenário end-to-end na Baia: materializar cronograma → lançar RDOs por atividade → conferir
  Resultado e alarme.
