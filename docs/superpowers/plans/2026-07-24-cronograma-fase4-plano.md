# Plano de Implementação — Fase 4: Linha de base (`cronograma_editor_v2`)

> **Estado em 2026-08-25 (varredura de fecho):** ✅ **FECHADO** — entregue; 🔬 todos os arquivos prometidos existem. 🔬 2/2 dos arquivos prometidos existem na árvore.
>
> Não há trabalho pendente aqui. **As caixas `- [ ]` abaixo não foram marcadas de propósito:** elas são
> rascunho de execução, não registro de estado. Quem carrega a verdade é este bloco,
> o `ESTADO-ATUAL.md`, o código e o git. O veredito acima foi dado por **existência de
> arquivo na árvore**, nunca por contagem de caixa.


Spec: `docs/superpowers/specs/2026-07-24-cronograma-editavel-design.md` (seções 1 e 5). Base: Fase 3 mergeada em `2169befa`. Tudo atrás da flag `cronograma_editor_v2` — **flag OFF = byte-idêntico**.

## Contexto verificado no código

- **Nada de linha de base existe hoje.** `CronogramaVersao` serve só ao fluxo de .mpp e continua intocada (o spec exige tabelas separadas).
- **Gantt** (`templates/obras/cronograma.html`, `renderGantt` ~2304): cada linha é um `.gantt-row` (37px, `position:relative`) contendo `.gantt-bar` (20px, centralizada por `top:50%` + `translateY(-50%)`). Posição é `left = (data_inicio − dMin) * DAY_W`, largura `= (dias + 1) * DAY_W`. A barra da baseline entra como um irmão absoluto na mesma linha, com o mesmo cálculo — nenhuma mudança na geometria existente.
- **Grade**: colunas fixas por `cellIndex` (Fase 2). A coluna "Desvio" entra **depois** de Término (índice 6), o que empurraria `COLS_NAV`/`COLS_CAMPO`/`COLS_SPAN` — ver Decisão 2.
- **Padrões reutilizáveis**: `_guard_rotas_vinculo` (404 opaco com flag off), migração idempotente (222/224), `db.Index` com nome igual nos dois lados.

## Decisão 1: "uma ativa por obra" garantida no banco

Índice único **parcial** `WHERE ativa` em `(obra_id, is_cliente)`. É o tipo de invariante que quebra em silêncio se ficar só no código; Postgres suporta índice parcial e o `db.Index(..., postgresql_where=...)` faz create_all e migração convergirem. A ativação continua desativando as irmãs em código — o índice é a rede de segurança.

`is_cliente` entra na chave porque o plano do cliente e o interno são conjuntos de tarefas distintos. A UI de baseline é **interna apenas** (spec §5: "o portal do cliente não muda"), mas escopar a tabela evita uma classe inteira de bug se a Fase 5 mexer nisso.

## Decisão 2: a coluna "Desvio" só existe quando há baseline ativa

O spec diz "coluna opcional". Renderizá-la sempre criaria uma coluna vazia para todo mundo e deslocaria os índices de célula da Fase 2 permanentemente. Renderizá-la **só quando há baseline ativa** (e com a flag on) mantém a grade atual intacta no caso comum.

Consequência: `COLS_NAV`/`COLS_CAMPO`/`COLS_SPAN` não podem ser constantes fixas — passam a ser derivadas de um `COL_OFFSET` que vale 0 sem baseline e 1 a partir da coluna 7 com baseline. Alternativa considerada e **descartada**: inserir a coluna no fim da tabela (não desloca nada, mas fica longe de Término, onde o número faz sentido).

**Mais simples e escolhido:** a coluna Desvio entra **no fim** da área de dados, logo antes de Ações, e nenhum índice de navegação muda. Fica adjacente a Planejado/Realizado — que é onde o usuário compara desempenho — e a Fase 2 não é tocada. `COLS_NAV` segue `[2,3,4,5,6,7,8]`.

## Step A — Modelo + migração 225

### A1. `models.py`

```
CronogramaBaseline: id, obra_id (FK CASCADE), admin_id, nome (String 120),
                    criada_em, criada_por (FK usuario), ativa (bool),
                    is_cliente (bool)
  __table_args__: Index('ix_cronograma_baseline_ativa_unica',
                        'obra_id', 'is_cliente', unique=True,
                        postgresql_where=text('ativa'))

CronogramaBaselineItem: id, baseline_id (FK CASCADE), tarefa_id (FK CASCADE),
                        data_inicio, data_fim, duracao_dias
  __table_args__: UniqueConstraint('baseline_id', 'tarefa_id')
```

### A2. Migração 225 idempotente (padrão da 224), registrada em `executar_migracoes()`.

## Step B — API (`cronograma_views.py`)

Todas com `_guard_rotas_vinculo` (404 opaco com flag off).

- `POST /obra/<id>/baseline` — body `{nome?, ativar?}`. Congela **todas as tarefas ativas do modo** que tenham `data_inicio` e `data_fim`. Nome default: `'Linha de base dd/mm/aaaa'`. `ativar` default `true`; ao ativar, desativa as irmãs na mesma transação. Obra sem tarefa datável → 400 `'Não há tarefas com datas para congelar na linha de base'`. Resposta 201 com a baseline e seus itens.
- `GET /obra/<id>/baselines` — lista (id, nome, criada_em, ativa, total_itens), mais recente primeiro.
- `POST /obra/<id>/baseline/<bid>/ativar` — ativa uma; desativa as outras. Devolve a lista de itens para o front redesenhar o Gantt.
- `DELETE /obra/<id>/baseline/<bid>` — remove (os itens caem por CASCADE). Fora do spec estrito, mas sem isso uma baseline errada é permanente.

**Não decorar com `_com_undo`**: baseline não muda tarefa, então o diff seria vazio de qualquer forma — decorar só gastaria dois snapshots por chamada.

`cronograma_obra` passa ao template `baseline_ativa` (nome + id) e `baseline_map` (`tarefa_id → {data_inicio, data_fim, duracao_dias}`), só com a flag on e fora do modo cliente.

## Step C — Frontend

- **Toolbar** `{% if editor_v2 %}`: botão "Linha de base" abrindo um modal com o nome sugerido, a lista das existentes (ativar/excluir) e o botão Salvar.
- **Gantt**: `.gantt-bar-baseline` — barra cinza de 5px logo abaixo da barra atual (`top: calc(50% + 12px)`), sem sombra, `pointer-events:none` para não atrapalhar o drag. Renderizada só quando há item de baseline para a tarefa.
- **Grade**: coluna "Desvio" antes de Ações, com `fim_atual − fim_baseline` em dias corridos; positivo (atrasado) em vermelho, negativo (adiantado) em verde, zero neutro, sem item `—`.
- `BASELINE_MAP` no JS é atualizado após salvar/ativar/excluir, seguido de `renderGantt()` e re-render da coluna.

## Step D — Testes (`tests/test_cronograma_baseline_api.py`)

1. Criar congela as datas de todas as tarefas datáveis e nasce ativa.
2. Editar a tarefa depois **não** muda o item da baseline (é congelada).
3. Criar a segunda com `ativar=false` mantém a primeira ativa.
4. Ativar a segunda desativa a primeira (uma ativa por obra).
5. O índice parcial impede duas ativas mesmo por escrita direta.
6. Tarefa criada depois da baseline não tem item (desvio nulo na UI).
7. Tarefa sem datas é ignorada; obra sem nenhuma datável → 400 verbatim.
8. Listagem escopada por obra; cross-tenant → 404 opaco.
9. Flag off → 404 nas quatro rotas.
10. Excluir baseline remove os itens (CASCADE).
11. `GET` da página com baseline ativa injeta `baseline_map`; sem baseline não injeta.
12. Modo cliente: baseline do interno não vaza para o plano do cliente.

**Regressão:** `-k cronograma` completa.

## Riscos e mitigações

| Risco | Mitigação |
|---|---|
| Coluna nova deslocar os índices da grade da Fase 2 | Desvio entra antes de Ações; `COLS_NAV` inalterado (Decisão 2) |
| Duas baselines ativas | Índice único parcial (Decisão 1) + teste 5 |
| Barra de baseline atrapalhar o drag da barra real | `pointer-events:none` |
| Baseline vazar para o portal do cliente | Escopo `is_cliente` + UI só na visão interna + teste 12 |
| Congelar obra grande | Um único `bulk_save_objects`; a operação é rara (manual) |
