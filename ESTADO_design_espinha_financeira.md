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

## Próximo passo (em andamento)
**Estudar a quebra de cada atividade em passos executáveis** (placa cimentícia → instalar / tratamento
de junta / basecoat; LSF → painelização / verticalização; etc.). Saída esperada: lista de
Atividades/Subatividades por Serviço da Baia, com a sequência que faz sentido — base para montar o
cronograma (habilitação da Fatia 1) e para o catálogo `SubatividadeMestre`.
