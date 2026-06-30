# RDOs no payload de import da Baia (físico real pelo relatório semanal) — Design

> Data: 2026-06-30. Obra-piloto: **Baia** (Baias Fazenda Santa Mônica).

## Problema

Ao reimportar a obra (`importar_fisico_financeiro`), o import **apaga e recria** todas as
`TarefaCronograma` da obra (`services/importacao_fisico_financeiro.py:165`) com **ids novos** e
`percentual_concluido=0`. Os RDOs e seus `RDOApontamentoCronograma` apontavam para tarefas que
deixaram de existir → ficam **órfãos** e o avanço físico **zera**. Hoje os RDOs vêm de um script
separado (`scripts/seed_rdos_baias.py`) que gera percentuais **sintéticos** (fator de realismo
determinístico), sem relação com o que de fato aconteceu na obra.

O usuário quer que **o próprio import já traga os RDOs com os percentuais físicos corretos**,
fiéis ao relatório semanal da obra (período 22–27/06/2026).

## Decisão

Uma nova seção top-level **`"rdos"`** no JSON de import. Ao final de
`importar_fisico_financeiro` (depois de materializar o cronograma e antes do `commit`), um novo
helper **`_materializar_rdos(obra, admin_id, rdos, tid_to_db)`** cria os RDOs a partir do payload,
referenciando cada tarefa pelo **id do `.mpp`** (`tarefa_mpp`) — traduzido para o id de banco via
o `tid_to_db` que o import já monta em `_materializar_cronograma_mpp`. Em seguida o import chama
`sincronizar_percentuais_obra(obra.id, admin_id)` (`utils/cronograma_engine.py`) para gravar o
`percentual_concluido` de cada tarefa a partir do último apontamento.

**Idempotência:** o helper apaga os RDOs daquela obra antes de recriar (mesma estratégia do seed)
— reimportar nunca duplica nem orfana.

**Fonte da verdade do físico:** o avanço físico real é o **cronograma físico** (percentual por
tarefa, sincronizado do RDO; rollup nos pais por `cronograma_engine`). O `pct_fisico` do painel
financeiro ficou desacoplado (sempre `None` após o fix `13bca494`) — não é tocado aqui.

## Formato do payload (`rdos`)

```json
"rdos": [
  {
    "data": "2026-06-27",
    "clima": "Ensolarado",
    "precipitacao": "Sem chuva",
    "comentario": "Texto do dia, fiel ao relatório.",
    "mao_de_obra": 3,
    "apontamentos": [
      {"tarefa_mpp": 3, "pct": 100},
      {"tarefa_mpp": 4, "pct": 65},
      {"tarefa_mpp": 6, "pct": 20}
    ]
  }
]
```

- `data` (obrigatório): `YYYY-MM-DD`. Item sem data válida é ignorado.
- `clima`, `precipitacao`, `comentario`: opcionais (defaults vazios/"Não informado").
- `mao_de_obra` (opcional, int, default 0): nº de funcionários ativos do tenant × 8h anexados ao
  RDO. **Só realismo do documento** — RDO mão de obra **não gera custo** no Realizado (custo de
  mão de obra vem de `registro_ponto`/ponto eletrônico). Se o tenant tiver menos funcionários
  ativos que o pedido, anexa os que existirem; se não houver nenhum, não anexa mão de obra (nunca
  falha o import).
- `apontamentos[].tarefa_mpp`: id da tarefa no `cronograma_tarefas` (mesmo id usado em
  `eap[].cronograma.tarefas_mpp`). `tarefa_mpp` não encontrado → apontamento ignorado.
- `apontamentos[].pct`: **percentual acumulado** (0–100), gravado em
  `RDOApontamentoCronograma.percentual_realizado` (a sincronização usa o último por data).

## Dados da Baia (fiéis ao relatório 22–27/06/2026)

6 RDOs, um por dia (Seg→Sáb). Apontamentos só nas tarefas com avanço; as demais permanecem 0%.

| Data | Clima | Tarefa 3 (Solo SPT) | Tarefa 4 (Projetos) | Tarefa 6 (FAZENDA nivelamento) |
|---|---|---|---|---|
| 22/06 | Nublado | 100 | 50 | — |
| 23/06 | Chuvoso | 100 | 55 | — |
| 24/06 | Chuvoso | 100 | 65 | — |
| 25/06 | Parcialmente nublado | 100 | 65 | — |
| 26/06 | Nublado | 100 | 65 | — |
| 27/06 | Ensolarado | 100 | 65 | 20 |

Estado físico resultante no cronograma (após sincronização):

- **ESTUDO DE SOLO SPT** (tarefa 3): **100%** — sondagem feita e relatório encaminhado/analisado.
- **EXECUÇÃO DE PROJETOS** (tarefa 4): **65%** — cobertura e pilares metálicos enviados;
  hidráulico/elétrico ainda só solicitados.
- **FAZENDA: NIVELAMENTO DO PLATÔ** (tarefa 6): **20%** — nivelamento do galpão B iniciado em
  27/06 (galpão A pendente). Tarefa físico-pura (FAZENDA), aparece no cronograma físico; não
  pertence a nenhuma etapa de custo (INDIRETOS tem `tarefas_mpp: []`).
- **MOBILIZAÇÃO EQUIPE** (5), **MARCAÇÃO DE OBRA** (8), **GABARITO** (9), **FUNDAÇÃO** e todas as
  demais tarefas construtivas: **0%** — marcação suspensa pelo desnível ~35 cm; fundação prevista
  só para 29/06. A mobilização da equipe é narrada nos comentários, não como % (tarefa formal em
  29/06).

> Observação: os percentuais de Projetos (65%) e Nivelamento (20%) são leitura qualitativa do
> relatório e podem ser ajustados editando o `pct` no JSON — sem mudança de código.

## Onde mora

| Camada | Arquivo | Mudança |
|---|---|---|
| Import | `services/importacao_fisico_financeiro.py` | novo helper `_materializar_rdos` + chamada antes do `commit` (l.427-429) + `sincronizar_percentuais_obra` |
| Dados | `tests/fixtures/cronograma_fisico_financeiro_baias.json` | nova seção `rdos` (6 RDOs da Baia) |
| Teste | `tests/test_importacao_fisico_financeiro.py` | RDOs criados, percentuais por tarefa, idempotência, ausência de `rdos` não quebra |

`scripts/seed_rdos_baias.py` deixa de ser necessário para a Baia (o import passa a ser a fonte
única). Mantido no repo para outras obras; nenhuma mudança nele.

## Modelo (campos usados)

- `RDO`: `numero_rdo` (`String(20)`, unique — formato `RDO-{admin}-{obra}-{AAAAMMDD}`),
  `data_relatorio`, `obra_id`, `admin_id`, `criado_por_id`, `clima_geral`, `precipitacao`,
  `local`, `status='Finalizado'`, `comentario_geral`.
- `RDOMaoObra`: `funcionario_id` (FK **não-nula** → exige `Funcionario` existente),
  `funcao_exercida`, `horas_trabalhadas`.
- `RDOApontamentoCronograma`: `tarefa_cronograma_id`, `quantidade_executada_dia`,
  `quantidade_acumulada`, `percentual_realizado`, `percentual_planejado` (nullable).
- Sincronização: como as tarefas materializadas não têm `quantidade_total`,
  `sincronizar_percentuais_obra` usa `percentual_realizado` direto → `percentual_concluido`.

## Testes

- **RDOs criados:** reimport da fixture → `RDO.query.filter_by(obra_id=...).count() == 6`.
- **Percentuais por tarefa:** após import, `TarefaCronograma` "ESTUDO DE SOLO SPT" = 100,
  "EXECUÇÃO DE PROJETOS" = 65, "FAZENDA: NIVELAMENTO DO PLATÔ" = 20; "MOBILIZAÇÃO EQUIPE" = 0.
- **Idempotência:** importar duas vezes → ainda 6 RDOs (sem duplicação).
- **Sem `rdos`:** payload sem a chave → import não cria RDOs e não levanta erro (regressão p/
  outras obras).
- **Invariantes da Baia** (financeiro) preservados: veks 800.960 / fat 550.775 / lucro 24.976 /
  imposto 128.903 / contrato 1.505.613,76 / data_fim 08/10. Suíte:
  `pytest tests/test_cronograma_fisico_financeiro.py tests/test_painel_financeiro.py tests/test_importacao_fisico_financeiro.py -q`.

## Fora de escopo

- Mão de obra fiel por nome/função real (usa funcionários ativos genéricos do tenant).
- RDOs do período anterior a 22/06 (solo 11/06, projetos 08–18/06): o avanço acumulado já é
  refletido nos apontamentos da semana do relatório.
- Fotos de RDO (`seed_fotos_rdos_baias.py`) — não incluídas no import.
- Mudança no `seed_rdos_baias.py`.
</content>
</invoke>
