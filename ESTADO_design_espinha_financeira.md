# ESTADO — Design da Espinha Financeira da Obra (Resultado por Atividade)

> Ponto de entrada único para retomar este trabalho. Atualizado: 2026-06-14.
> Branch: `design/espinha-financeira-obra`. Foco do usuário (Cássio): **qualidade**.

## Onde estamos
Desenhando a feature **"Resultado real por Atividade, diário"** no SIGE — quanto cada atividade do
cronograma dá de resultado de verdade enquanto a obra acontece (Valor agregado − Custo incorrido),
com alarme de produtividade e, adiante, previsão. Passamos por: brainstorming → grill-with-docs (2x)
→ análises profundas de código → spec escrito e grelhado. **Próximo passo definido pelo usuário:**
estudar como **cada atividade se quebra em passos** (ex.: placa cimentícia = instalar + tratamento de
junta + basecoat) — insumo para definir as Atividades/Subatividades do cronograma.

## Artefatos (todos no repo)
- **`docs/superpowers/specs/2026-06-14-espinha-financeira-obra-design.md`** — o spec (5 fatias, decisões D1–D6). MESTRE.
- **`docs/superpowers/specs/2026-06-14-mapa-codigo-cronograma-custo-medicao.md`** — mapa do código real (file:line). REFERÊNCIA.
- **`docs/superpowers/specs/2026-06-14-cronograma-refinado-pareto-baia-rev10.md`** — o cronograma ENXUTO (~30 atividades, Pareto+LOB). CRONOGRAMA-DE-CONTROLE DE REFERÊNCIA.
- **`docs/superpowers/specs/2026-06-14-quebra-atividades-baia-rev10.md`** — os 21 serviços em ~80 passos (dicionário de método executivo; referência, não o cronograma).
- **`CONTEXT.md`** — glossário (termos fixados nesta sessão, abaixo).
- `ESTUDO_cronograma_baia_rev10.md` — mecânica cronograma↔orçamento↔medição + mapa atividade→serviço (MPP §3).
- `CONTEXTO_orcamento_baia_rev10.md` · `HANDOFF_baia_rev10.md` — contexto do orçamento Baia.
- `ESPACO_telhado_viga_i_baia_rev10.md` · `ESPACO_custos_por_atividade_baia_rev10.md` — espaços de discussão.

## Glossário fixado (CONTEXT.md)
**Avanço realizado** (físico, RDO, âncora) · **Valor agregado** (avanço × venda) · **Custo incorrido**
(competência, no dia do fato) · **Resultado realizado/projetado** (≠ Lucro, que é BDI) ·
**Atividade** = `TarefaCronograma` (execução) · **Serviço** = linha do orçamento (precificação).
Resultado sobe Atividade → Serviço → Obra. "Realizado" sozinho é banido (existe o de caixa).

## Decisões travadas (no spec)
- **D1** Custo MO por atividade = **computado** (rateio de `RDOCustoDiario.custo_total_dia` pelas horas
  apontadas por atividade). Ociosidade **embutida, não medida**; índice de produtividade é o sinal.
- **D2** Não-MO direto = etiquetado (`tarefa_cronograma_id` em `GestaoCustoFilho`, Fatia 2);
  compartilhado = rateio por hora-homem.
- **D3** Subempreitada → custo via `RDOSubempreitadaApontamento` (telhado viga I = verba+lucro).
- **D4** Resultado (competência) ≠ Caixa (Realizado/Previsto, ADR 0003). Duas lentes.
- **D5** Alarme **primário em R$** (custo MO real vs orçado-para-o-avanço); horas só como refino onde a
  MO foi precificada em hora (1.1 LSF). A Baia precifica MO majoritariamente em R$/m² (sem hora).
- **D6** Peso Serviço→Atividade = **o da medição** (`ItemMedicaoCronogramaTarefa.peso`), editor já
  pronto (`medicao_views.py:344`). Reuso, sem campo novo.

## As 5 fatias (ordem)
1. **Resultado por Atividade (só MO) + alarme** — tracer bullet. Inclui materializar o cronograma da
   Baia, consertar o bug da edição do RDO, read-model `resultado_atividade_service`, tela. **Sem migration.**
2. **Custos não-MO por atividade** (material/alimentação/transporte + subempreitada/telhado).
3. **Motor de previsão (EVM)** — Resultado projetado, EAC, CPI/SPI.
4. **Lente de caixa** — Realizado/Previsto no tempo.
5. **Inteligência** — loop de aprendizado de produtividade + roll-up de portfólio.

## Bugs/pendências reais (do mapa de código)
- 🐛 Edição RDO V2 perde `tarefa_cronograma_id` (`rdo_editar_sistema.py:374`). Conserto na Fatia 1.
- 🟡 Materialização do cronograma não-automática (`handlers/propostas_handlers.py:131`).
- `subatividade_mestre` vazio (0); peso semeia por divisão igual — ajusta-se na tela de medição (D6).
- Gate v2: a obra Baia precisa estar em `versao_sistema='v2'`.

## Feito nesta sessão (além do spec)
**Quebra dos 21 serviços em Atividades** concluída (pesquisa do método executivo + projetos da obra) →
`docs/superpowers/specs/2026-06-14-quebra-atividades-baia-rev10.md`. Cada serviço tem seus passos em
ordem, com unidade de apontamento, dependências e peso. É o insumo para montar o cronograma da Baia
(habilitação da Fatia 1) e semear o catálogo `SubatividadeMestre`.

## Cronograma refinado — FEITO (sem supervisão, foco Pareto)
Os ~80 passos foram enxugados para **~30 atividades** (`...cronograma-refinado-pareto...`), aplicando
Pareto de custo (1.1 LSF = 40%; top 8 = 80%) + Linha de Balanço (obra repetitiva, medir por baia) +
regras de aderência (cortar passo passivo/admin; cura/secagem = folga). As 5 decisões em aberto foram
**resolvidas como gestor** (ver doc). Restam só 2 dados externos: **valor da verba+lucro do telhado
viga I** e a **contagem de pontos do 1.12** (para custo, não trava cronograma).

## Próximo passo
1. **Datas/durações + ritmos-alvo (baias/dia)** por frente — precisa exportar o `Projeto1.mpp` p/ XML.
2. **Materializar o cronograma da Baia** no sistema a partir das ~30 atividades (habilitação da Fatia 1).
3. **Plano de implementação da Fatia 1** (writing-plans).
