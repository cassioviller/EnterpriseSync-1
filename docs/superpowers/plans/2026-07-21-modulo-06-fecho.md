# Módulo 06 — Motor de Cálculo Unificado — Fecho

> Fecha o M06 conforme o plano `2026-07-21-modulo-06-implementacao-motor-calculo.md`
> (spec `2026-07-17-modulo-06-motor-calculo.md`). Divergências deliberadas nas
> ressalvas abaixo.

## Entregue (commits nesta branch `feat/cronograma-mpp-m03-upload-parser`)

| Task | Commit | Conteúdo |
|---|---|---|
| 1 | `acaadb8` | Caracterização de D, rollup de `tarefas_rdo` e subempreitada antes de mexer |
| 2 | `845db37` | Tabela normativa §12 no engine — marcos (degrau/binário/peso 0), unidade homogênea, `com_arquivadas_historicas` |
| 3 | `335b0a6` | `rollup_realizado` + subempreitada em `atualizar_percentual_tarefa` + `progresso_geral_para_kpi` (KPI convergido, fallback C extraído) |
| 4 | `9accd9e` | `replanejar_curvas_obra` + `_motor_pos_commit` no M05 (evento `replanejado`) + `verificar_consistencia_progresso` |
| 5 | — | Teste de convergência multi-fontes + este fecho |

## Checklist §22 da spec — estado

- [x] **Tabela normativa implementada e testada caso a caso** — docstring do
      topo de `utils/cronograma_engine.py` como contrato; testes por linha:
      marco (degrau, binário, peso 0), duração-zero-como-marco, unidade
      homogênea (m2+un cai p/ duração), sem-plano `None`, arquivada
      histórica (entra só p/ `data_ref < arquivada_em` via kwarg).
- [x] **Rollup e subempreitada só no engine** — `rollup_realizado`
      (pai intermediário herda agregado das filhas) usado por `tarefas_rdo`;
      soma empresa+sub vive em `atualizar_percentual_tarefa` (acumulada do
      último RDO + produção da sub — corrige de quebra a dupla contagem da
      versão antiga da view, que somava `quantidade_executada_dia`);
      `_atualizar_percentual_com_subempreitada` é delegação fina.
- [x] **KPI de detalhes convergido** — `progresso_geral_para_kpi`: obra com
      cronograma vivo → v2 de hoje; sem cronograma → fallback C (a antiga
      FÓRMULA SIMPLES, extraída e travada por teste). `views/obras.py` usa
      `obra.admin_id` quando o super admin navega sem tenant.
- [x] **Replanejamento preserva realizado (byte a byte)** — teste compara a
      tupla completa (qtd_dia, acumulada, realizado, acumulado_pct) antes e
      depois; planejado recalculado com a data do PRÓPRIO RDO; idempotente
      (2ª execução → 0 replanejados); marco em degrau; sem-plano `None`.
- [x] **Igualdade entre as fontes provada** —
      `test_convergencia_todas_as_fontes_dao_o_mesmo_numero`: v2 direto,
      KPI, curva (com arquivadas históricas) e raiz do rollup de
      `tarefas_rdo` devolvem o MESMO número; header/portal/card já eram
      travados a v2 pelos testes existentes (`test_importacao_fisico_financeiro.py`
      :766/:829), que permanecem verdes **sem edição**.
- [x] **Gate verde sem editar os testes V2** — 17 suítes (cronograma
      completo + físico-financeiro + caracterização + M05): **230 passed,
      0 failed** (2026-07-21). Suíte completa do repo segue bloqueada por
      testes que exigem servidor vivo (pré-existente, registrado nos fechos
      M03/M05).

## Ressalvas de execução (divergências deliberadas)

1. **Evento `replanejado` próprio, não anexado ao `aplicado`** (spec §4.3
   pedia gravar o relatório no evento `aplicado`): o `aplicado` é commitado
   na transação estrutural do M05; o replanejamento roda pós-commit. Falha
   no replanejamento loga e NÃO desfaz a versão aplicada.
2. **Obra sem nenhum RDO continua fora do motor pós-commit** (política do
   M05 preservada): sem apontamentos não há curvas a replanejar, e o sync
   zeraria a carga inicial de `pct_project`.
3. **Subempreitada usa acumulada do último RDO para a parte da empresa**
   (não a soma de `quantidade_executada_dia` da view antiga) — consistente
   com o resto do engine e imune à dupla contagem; a caracterização da
   Task 1 cobre o caso de apontamento único (equivalente nos dois métodos).
4. **B caracterizado na extração, não antes** — a FÓRMULA SIMPLES era
   inline na view de detalhes (não chamável isolada); o lock ficou no teste
   do fallback extraído (`_progresso_fallback_subatividades`), mesma fórmula.
5. **D permanece** (`calcular_progresso_real_servico`, contexto por serviço)
   com teste de caracterização; não é progresso da obra.
6. **`verificar_consistencia_progresso`** entregue como função de engine
   (chamável de shell/job), sem manage-command dedicado — não há infra de
   CLI de manage no projeto.

## Fora de escopo mantido

Predecessoras tipadas/lag no motor de datas (preservadas no snapshot M05);
peso financeiro; curva persistida; mudanças de UI. Rollout/flag do novo
número do KPI é decisão do M10 (spec §13).
