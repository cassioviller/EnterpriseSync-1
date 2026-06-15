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

## Planos de implementação — FEITO (writing-plans, todas as fatias, 2026-06-15)
Escritos juntos para travar consistência, achar problemas cross-cutting cedo e reusar ao máximo:
- **`docs/superpowers/plans/2026-06-15-espinha-financeira-plano-mestre.md`** — contrato compartilhado
  (DC1–DC10), migration única, regra anti-dupla-contagem de MO (DC3), mapa de reúso, riscos cross-fatia.
- `...-fatia-1-resultado-por-atividade-plan.md` — MO + alarme + tela + bug RDO + habilitação Baia (sem migration).
- `...-fatia-2-custos-nao-mo-por-atividade-plan.md` — **migration ÚNICA 193**; não-MO direto+rateio; subempreitada/telhado.
- `...-fatia-3-evm-previsao-plan.md` — CPI/SPI/EAC (reúso de alarme_custo + cronograma_engine).
- `...-fatia-4-lente-caixa-plan.md` — Realizado/Previsto por obra (reúso integral do FinanceiroService, ADR 0003).
- `...-fatia-5-inteligencia-portfolio-plan.md` — learning loop (catálogo) + roll-up de portfólio.

## Execução — FEITO (2026-06-15, branch design/espinha-financeira-obra)
As 5 fatias foram implementadas e testadas (**36 testes verdes**); grill-with-docs aplicado
(ADR 0004/0005; orçado = baseline congelado da proposta; serviço→N atividades por peso).
- **Fatia 1** ✅ bug RDO + read-model + tela + **importador auto-wiring** (Baia obra 655, 28 atividades multi).
- **Fatia 2** ✅ núcleo: custo não-MO (direto+rateio, DC3 anti-dupla-contagem) + custo incorrido +
  alarme total + subempreitada→custo. Pendente: material-UI (precisão) e telhado (dado externo).
- **Fatia 3** ✅ EVM (CPI/SPI/EAC/resultado projetado). SPI espera datas do MPP.
- **Fatia 4** ✅ lente de caixa por obra (reúso do FinanceiroService, ADR 0003).
- **Fatia 5** ✅ learning loop (catálogo) + roll-up de portfólio.

## Próximo passo (pendentes pontuais)
1. **Datas/durações** por atividade — exportar `Projeto1.mpp` p/ XML → liga o **SPI** e a Linha de Balanço.
2. **Telhado viga I** (Fatia 2 §D) — falta verba+lucro+opção A/B/C (mecanismo de custo já existe).
3. **Material direto na UI** (Fatia 2) — botão espelhando equipe (custo já flui por rateio).
4. **Pushar a branch / abrir PR.**
