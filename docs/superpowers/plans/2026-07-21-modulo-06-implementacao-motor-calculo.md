# Módulo 06 — Motor de Cálculo Unificado — Implementation Plan

> Fonte: spec `2026-07-17-modulo-06-motor-calculo.md`. Em conflito, este plano vence
> (reconcilia a spec com o modelo vivo pós-M05, medido 2026-07-21).

**Goal:** `utils/cronograma_engine.py` como fonte única das fórmulas de progresso
(tabela normativa §12 da spec), convergir o KPI de detalhes da obra, mover rollup e
subempreitada para o engine, e adicionar `replanejar_curvas_obra` chamado pela
aplicação de versão (M05) — preservando os comportamentos travados por teste.

## Fatos do modelo vivo (medidos 2026-07-21 — NÃO re-descobrir)

- **Engine** (`utils/cronograma_engine.py`): `sincronizar_percentuais_obra` :140
  (pula `responsavel='terceiros'` :204; zera folha sem apontamento), `recalcular_cronograma`
  :238 (datas + sync interno; comita), `calcular_progresso_rdo` :370 (planejado linear por
  dias úteis; `None` sem plano; realizado por qtd acumulada ou último percentual),
  `calcular_progresso_geral_obra_v2` :459 (média ponderada de FOLHAS; `usar_qtd = all(...)`
  :526 SEM validação de unidade), `atualizar_percentual_tarefa` :559. **Todas já filtram
  `ativa=True` (M05)** — arquivadas hoje somem inclusive do histórico.
- **KPI B**: `views/obras.py` ~:1694-1719, dentro da view de detalhes da obra —
  "FÓRMULA SIMPLES": média de `RDOServicoSubatividade.percentual_conclusao` do último RDO.
- **D**: `calcular_progresso_real_servico` (`views/obras.py:652`) — AVG SQL por serviço
  (último registro por subatividade); consumida em :751/:803. NÃO é progresso da obra.
- **Rollup duplicado**: `cronograma_views.py` `tarefas_rdo` ~:919-943 — bottom-up por
  duração replicando a fórmula do engine.
- **Subempreitada**: `_atualizar_percentual_com_subempreitada` (`cronograma_views.py:1106`),
  chamada em :1025 e :1102 — soma qty empresa+sub, SÓ atualiza quando `quantidade_total>0`,
  comita; caminho alternativo a `atualizar_percentual_tarefa`.
- **Curva de avanço**: `views/obras.py:2561` `curva_avanco_obra` → v2 por data (:2614).
- **Testes que travam o V2** (devem ficar verdes SEM edição):
  `tests/test_importacao_fisico_financeiro.py` :749 (monotonicidade), :766 (header),
  :829 (portal); `tests/test_caracterizacao_apontamento_cronograma.py`.
- `is_marco` existe (M02) e é preenchido pelo M05; nenhum consumidor no engine hoje.
- `RDOApontamentoCronograma.percentual_planejado` é snapshot do momento do RDO (nullable,
  Task #142: `None` = "sem plano").
- M05 `aplicar_versao` (`services/cronograma_versao_service.py`): pós-commit roda
  recalcular+sincronizar SÓ se a obra tem RDO; evento `aplicado` já commitado na transação.

## Task 1: caracterização antes de mexer — `tests/test_cronograma_engine_unificado.py`

Travar comportamento atual de: **B** (média simples de subatividades do último RDO —
caracterizar a FÓRMULA, não a view: fixture com RDOServicoSubatividade), **D**
(`calcular_progresso_real_servico` — último registro por subatividade, AVG), rollup de
`tarefas_rdo` (endpoint JSON: pai = média ponderada por duração das filhas),
subempreitada (qty empresa+sub / total). Commit: `test(cronograma): caracterização dos
caminhos de progresso antes da unificação (M06)`.

## Task 2: regras §4.2 no engine (TDD por linha da tabela §12)

Tabela normativa na docstring do topo do engine. Regras novas:
- **Marco** (`is_marco` OU `duracao_dias==0` não-marco): peso **0** no agregado;
  planejado = degrau (0 antes de `data_inicio`, 100 a partir dela; sem data → None);
  realizado = 0/100 (≥100 → 100, senão 0). Marcos ficam FORA do cálculo de `usar_qtd`.
- **Unidade homogênea**: `usar_qtd=True` exige adicionalmente
  `len({unidade_medida das folhas não-marco}) == 1` (nunca soma m+un+dias).
- **Arquivadas históricas**: `calcular_progresso_geral_obra_v2` ganha kwarg
  `com_arquivadas_historicas=False` (assinatura pública compatível): quando True, folhas
  arquivadas com `arquivada_em > data_ref` (ou seja, vivas NA data consultada) entram no
  agregado — a curva de avanço histórica não "perde" trabalho feito. `curva_avanco_obra`
  passa True. Default False preserva o comportamento pós-M05 (risco §19 da spec).
- Extrair helper puro `_planejado_linear(data_inicio, data_fim, duracao, data_ref, sab, dom)`
  usado por `calcular_progresso_rdo` e pelo replanejamento (Task 4).
Commit: `feat(cronograma): tabela normativa §12 no engine — marcos, unidades, arquivadas (M06)`.

## Task 3: rollup e subempreitada só no engine; KPI B convergido

- `rollup_realizado(itens) -> dict` no engine (itens: dicts com id/tarefa_pai_id/ordem/
  duracao_dias/percentual_realizado; devolve {pai_id: pct}) — `tarefas_rdo` passa a usá-la
  (mesma fórmula, um só lugar).
- Subempreitada: `atualizar_percentual_tarefa(tarefa_id, admin_id)` passa a somar
  `RDOSubempreitadaApontamento.quantidade_produzida` quando existir;
  `_atualizar_percentual_com_subempreitada` vira delegação fina (mantida por
  compatibilidade de chamadas :1025/:1102).
- **KPI B**: nova `progresso_geral_para_kpi(obra_id, admin_id)` no engine — bifurcação:
  obra com `TarefaCronograma` interna viva → `calcular_progresso_geral_obra_v2(hoje)`;
  senão fallback C (média simples de subatividades do último RDO, movida para o engine
  como `_progresso_fallback_subatividades`). `views/obras.py` ~:1694 usa a função;
  **D fica** (contexto por serviço) com comentário de escopo + teste da Task 1.
Commit: `feat(cronograma): rollup, subempreitada e KPI de obra unificados no engine (M06)`.

## Task 4: `replanejar_curvas_obra` + integração M05 — `tests/test_replanejamento.py`

`replanejar_curvas_obra(obra_id, admin_id) -> dict` no engine:
1. UMA query de apontamentos (join RDO, ordem cronológica); para cada um, recalcular
   `percentual_planejado` com as datas vigentes via `_planejado_linear` (marco = degrau).
   **Intocados**: `quantidade_executada_dia`, `quantidade_acumulada`,
   `percentual_realizado`, `percentual_acumulado`.
2. `sincronizar_percentuais_obra` (pais + persistidos).
3. Relatório `{apontamentos_replanejados, tarefas_sem_historico_reconciliado (ids
   arquivados com apontamentos), progresso_antes, progresso_depois}`.
Integração M05: `aplicar_versao`/`restaurar_versao` chamam no pós-commit quando
`tem_rdo` (substituindo o par recalcular+sincronizar avulso… NÃO: recalcular continua —
replanejar entra DEPOIS dele) e gravam o relatório num evento **`replanejado`** próprio
(o evento `aplicado` já foi commitado na transação estrutural — desvio documentado da
spec §4.3, que pedia anexar ao `aplicado`).
Observabilidade (§16): `verificar_consistencia_progresso(obra_id, admin_id) -> dict`
compara `percentual_concluido` persistido × recalculado e devolve/loga drift.
Testes: obra com 3 RDOs em datas distintas → mudar datas → planejado recalculado por
data de RDO, realizado **byte-idêntico** (tupla completa antes/depois); relatório;
monotonicidade pós-replanejamento; aplicar_versao gera evento `replanejado`.
Commit: `feat(cronograma): replanejamento determinístico de curvas pós-aplicação (M06)`.

## Task 5: convergência + gate + fecho §22

Teste de igualdade entre as fontes para a mesma fixture: v2 direto, KPI
(`progresso_geral_para_kpi`), último ponto da curva (mesma chamada v2 da view), e
raiz do rollup de `tarefas_rdo` — todas o MESMO número (header/portal/card já travados
pelos testes existentes :766/:829). Gate escopado (suítes cronograma + fisico_financeiro
+ caracterização) SEM editar os testes V2. Fecho §22 com ressalvas.
Commit: `docs(cronograma): fecho do M06 (Task 5)`.

## Critérios de aceite (spec §22)
1. Tabela §12 caso a caso. 2. Rollup/subempreitada só no engine. 3. KPI convergido.
4. Replanejamento preserva realizado (byte a byte). 5. Igualdade entre fontes provada.
6. Gate verde sem editar testes V2 existentes.

## Fora de escopo (mantido da spec §5)
Predecessoras tipadas/lag no motor de datas (dados preservados no snapshot — M05);
peso financeiro; curva persistida; UI.
