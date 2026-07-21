# Módulo 07 — RDO: modos quantitativo e percentual — Implementation Plan

> Fonte: spec `2026-07-17-modulo-07-rdo.md`. Em conflito, este plano vence
> (reconcilia a spec com o modelo vivo pós-M06, medido 2026-07-21).

**Goal:** os dois modos de apontamento (quantidade do dia / percentual acumulado)
em qualquer obra, com validações auditadas, recomputo em cadeia determinístico
para correções retroativas e semântica de colunas correta (M02) — preservando
fotos, comentários, mão de obra e o fluxo legado de subatividades.

## Fatos do modelo vivo (medidos 2026-07-21 — NÃO re-descobrir)

- **Serviço único já existe** (`services/cronograma_apontamento_service.py`, M1,
  145 linhas): `registrar_apontamento(rdo, tarefa, *, quantidade_dia|percentual_acumulado,
  admin_id)` com UPSERT por (rdo, tarefa). Modo percentual atual grava o INCREMENTO
  em `quantidade_executada_dia` (abuso herdado do import) e não escreve os campos
  semânticos do M02 (`tipo_apontamento`, `percentual_acumulado`,
  `percentual_incremento_dia`, `quantidade_total_snapshot`, `unidade_snapshot`).
- **Callers do serviço**: `views/rdo.py:4556-4592` (salvar_rdo_flexivel, só
  quantitativo, `qty <= 0` ignorado) e `cronograma_views.py:1138-1150`
  (apontar_producao). O import físico-financeiro
  (`services/importacao_fisico_financeiro.py:505-532`) grava DIRETO no modelo,
  formato antigo — fica assim até o M9 (spec §14).
- **Colunas de quantidade são NOT NULL default 0** (`models.py:4972-4973`) —
  o "campos de quantidade NULL" da spec é impossível sem migration (§8 proíbe):
  modo percentual novo grava **0.0** nelas e a verdade fica nos campos semânticos.
- **Não há tabela de eventos de RDO** — auditoria de retrocesso/sobre-execução/
  override sai como log estruturado (ressalva; evento de banco exigiria M02½).
- **Sem infra de feature-flag** (rollout é M10): o serviço faz dupla escrita
  permanente (legado + semântico) até o M9/M10 desligar.
- **tarefas_rdo** (`cronograma_views.py:843`) já devolve `unidade_medida`,
  `quantidade_total`, `quantidade_acumulada`, `percentual_realizado`; faltam
  `tipo_modo`, `is_marco`, `percentual_acumulado_anterior`, `saldo`.
- **Portal** (`portal_obras_views.py:650-698`): deriva atividades do dia EM
  MEMÓRIA (anterior por query, incremento>0). **PDF**
  (`services/rdo_pdf_service.py:631`): mostra `quantidade_executada_dia` cru —
  em modo percentual novo mostraria 0.
- **Template novo.html:1111**: `hasInput = !isPai && isEmpresa &&
  t.quantidade_total > 0` — tarefa sem quantitativo NÃO tem campo (problema 1).
  Hidden `cronograma_tarefa_<id>` montado em `apontarProducaoRDO` (~:1306).
  `editar_rdo.html` (2593 linhas) usa subatividades legadas; apontamentos de
  cronograma são editados via apontar_producao.
- **Caracterização existente** (`test_caracterizacao_apontamento_cronograma.py`):
  cobre os DOIS paths HTTP no modo quantitativo — devem seguir verdes sem edição.
  `test_apontamento_percentual_grava_incremento_diario` (import) idem.
- **Recomputo**: leitura já recalcula certo (`calcular_progresso_rdo` soma por
  data); o problema é só o PERSISTIDO (`quantidade_acumulada`/`percentual_realizado`
  dos RDOs posteriores + `percentual_concluido` da tarefa).
- Ordem estável de cadeia: (`RDO.data_relatorio`, `RDOApontamentoCronograma.id`).

## Task 1: semântica nova + validações no serviço — `tests/test_rdo_modos_apontamento.py`

`registrar_apontamento` ganha kwargs `permitir_retrocesso=False, justificativa=None,
permitir_sobreexecucao=False` e helper `modo_da_tarefa(tarefa) -> 'quantidade'|'percentual'`
(`quantidade_total>0 e unidade` ⇒ quantitativo; senão percentual; marco sempre percentual
0/100). Escrita SEMPRE dupla (legado + M02):
- quantitativo → legado igual hoje + `tipo_apontamento='quantitativo'`,
  `quantidade_total_snapshot`, `unidade_snapshot`, `percentual_acumulado=perc_real`,
  `percentual_incremento_dia = perc_real − perc_anterior`;
- percentual → `tipo_apontamento='percentual'`, `percentual_acumulado` (raw, pode
  passar de 100 só com `permitir_sobreexecucao`), `percentual_incremento_dia =
  acumulado − acumulado_anterior`, `percentual_realizado=clamp(0,100)`,
  **`quantidade_executada_dia=0.0` e `quantidade_acumulada=0.0`** (fim do abuso;
  NOT NULL impede NULL — ressalva à spec).
Validações (server-side, exceções tipadas): `RetrocessoNaoPermitido` (acumulado <
anterior sem `permitir_retrocesso`+justificativa — justificativa vai no log
estruturado), `SobreexecucaoNaoConfirmada` (>100% pct ou acumulada>total sem
confirmação ⇒ erro; com confirmação grava raw e clampa `percentual_realizado`),
`MarcoApenasZeroOuCem`. O % do quantitativo passa a usar `quantidade_total_snapshot`
da linha (blinda o histórico contra mudança futura de `quantidade_total`; linhas
antigas sem snapshot continuam pelo total da tarefa).
Caracterização quantitativa existente permanece verde (dupla escrita é aditiva).
Commit: `feat(rdo): modos quantitativo e percentual com semântica M02 e validações (M07)`.

## Task 2: recomputo em cadeia — `tests/test_rdo_recomputo_cadeia.py`

`recomputar_cadeia(tarefa_id, a_partir_de, admin_id) -> int` no serviço: reprocessa
apontamentos da tarefa com `data_relatorio >= a_partir_de` em ordem (data, id):
- quantitativo: `quantidade_acumulada` = acumulado anterior + dia;
  `percentual_realizado` pelo snapshot da própria linha (senão total da tarefa);
- percentual: `percentual_incremento_dia` = acumulado − anterior;
  `percentual_realizado` = clamp do acumulado. Snapshots NUNCA mudam.
Devolve o nº de linhas alteradas. Integração (mesma transação do caller):
- `salvar_rdo_flexivel` e `apontar_producao`: após registrar, recomputar da data do
  RDO em diante (cobre retroativo e edição de apontamento — UPSERT);
- `excluir_rdo` (`views/rdo.py:460`): recomputar tarefas afetadas a partir da data
  do RDO excluído; depois `atualizar_percentual_tarefa`.
Testes: criar RDO no MEIO da série ⇒ posteriores recalculados (valores exatos);
editar apontamento antigo idem; excluir idem; mudar `quantidade_total` da tarefa ⇒
histórico imutável (snapshot) e próximo apontamento usa o novo total; desempate de
mesma data por id.
Commit: `feat(rdo): recomputo em cadeia determinístico para correções retroativas (M07)`.

## Task 3: contrato tarefas_rdo + portal/PDF pelos campos persistidos

- `tarefas_rdo`: adiciona `tipo_modo` (via `modo_da_tarefa`), `is_marco`,
  `percentual_acumulado_anterior` (último acumulado ≤ data), `saldo`
  (`quantidade_total − acumulada`, só quantitativo). Aditivo.
- Portal (`portal_rdo_detalhe`): usa `percentual_incremento_dia`/`percentual_acumulado`
  persistidos quando presentes (linhas novas); mantém a derivação em memória como
  fallback para linhas antigas (import pré-M9). Filtro incremento>0 preservado.
- PDF (`rdo_pdf_service:631`): linha percentual mostra `+X pp` (incremento
  persistido) em vez de "0 {unidade}".
Commit: `feat(rdo): contrato de modos no tarefas_rdo e leitura persistida no portal/PDF (M07)`.

## Task 4: templates novo/editar — dois modos com preview

`templates/rdo/novo.html`: `hasInput` vira `!isPai && isEmpresa` com bifurcação por
`t.tipo_modo`; quantitativo = campo "Quantidade executada HOJE ({unidade})" + linha
viva "Anterior X% → +Y hoje → Z% acumulado" (espelha backend: acumulada+qtd/total);
percentual = campo "Percentual ACUMULADO da tarefa (%)" + linha "Anterior X% →
incremento +Y pp"; marco = toggle 0/100. Nunca dois campos; nome novo
`cronograma_tarefa_pct_<id>` (quantitativo mantém `cronograma_tarefa_<id>`).
Busca client-side na árvore (input filtra por nome). Validações espelhadas:
retrocesso/sobre-execução pedem confirmação (campos `retrocesso_justificativa_<id>`,
`confirma_sobreexecucao_<id>`). `salvar_rdo_flexivel` parseia os campos novos e
delega. `editar_rdo.html`: mesma renderização da árvore (a edição de apontamento
de cronograma já roda via apontar_producao — sem novo fluxo).
Commit: `feat(rdo): UI dos dois modos com preview e validação espelhada (M07)`.

## Task 5: gate escopado + fecho §22

Suítes: modos, recomputo, caracterização (sem edição), upload/importação
físico-financeiro, engine/replanejamento, M05. Playwright
(`test_rdo_progresso_monotonico_playwright.py` + fluxo dos dois modos): estender SE
o ambiente tiver servidor vivo; senão ressalva (mesmo bloqueio M03/M05/M06).
Fecho §22 com ressalvas.

## Critérios de aceite (spec §22)
1. Dois modos em qualquer obra. 2. Quantidade nunca guarda percentual (modo novo).
3. Retrocesso/>100/marco validados e logados. 4. Recomputo atômico e testado.
5. Snapshots protegem histórico. 6. Portal/PDF consistentes. 7. Gate verde sem
editar caracterização existente.

## Fora de escopo (spec §5 + reconciliação)
Handlers legados (`rdo_salvar_unificado` :2513, bloco inline :843, `crud_rdo_completo`);
subatividades legadas; import (até M9); rascunho; fotos/mão de obra/medições;
remoção da dupla escrita (M9/M10).
