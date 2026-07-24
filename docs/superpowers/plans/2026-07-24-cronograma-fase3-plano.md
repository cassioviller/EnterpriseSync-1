# Plano de Implementação — Fase 3: Desfazer/refazer (`cronograma_editor_v2`)

Spec: `docs/superpowers/specs/2026-07-24-cronograma-editavel-design.md` (seções 1, 3 e 6). Base: Fase 2 mergeada em `6c9b60d2`. Tudo atrás da flag `cronograma_editor_v2` — **flag OFF = comportamento byte-idêntico**, exceto o conserto explícito de `ativa` descrito no Step D (decisão do usuário).

## Contexto verificado no código

- **Não existe pilha de ações hoje.** `cronograma_acao` é tabela nova (migração 224; as 222/223 são da Fase 1).
- **`excluir_tarefa` (`cronograma_views.py:1047`) faz HARD delete** (`db.session.delete`), e os vínculos caem por `ondelete='CASCADE'`. Apontamentos de RDO da tarefa também são destruídos — por isso o spec exige arquivamento lógico para o desfazer.
- **`TarefaCronograma.ativa`/`arquivada_em` (models.py:5781-5782) já existem e já são usadas**: `services/cronograma_versao_service.py:610,832` arquiva tarefas na reconciliação de .mpp. Ou seja, **tarefas arquivadas já existem em produção** — o soft delete não cria uma classe nova de dado, só a torna mais comum.
- **Auditoria de vazamento de tarefa arquivada** (quem consulta `TarefaCronograma` sem filtrar `ativa`): a página do cronograma (`cronograma_views.py:349`), `tarefas_rdo` (1761), o scheduler e o `_estrutura_visual` da Fase 2 **já filtram**. Só dois pontos não filtram:
  - `services/cronograma_fisico_financeiro.py:231` — `filter_by(obra_id, admin_id).all()`;
  - `portal_obras_views.py:146` — listagem do portal do cliente.
  `medicao_service` e `rdo_pdf_service` acessam por id a partir de apontamentos existentes (não listam) — não vazam.
- **Helpers reutilizáveis**: `_guard_rotas_vinculo` (404 opaco com flag off), `_resposta_grade` (Fase 2, serializa pós-commit com `_mapas_vinculos` + `nivel`), `_editor_v2_on`, `_admin_id`, `_modo_cliente`.
- **Padrão de coluna JSON**: `db.Column(db.JSON)` (models.py:5906-5908).
- **Padrão de migração**: função `_migration_NNN_*` idempotente (`CREATE TABLE IF NOT EXISTS`, nomes de constraint iguais aos do `__table_args__`, porque `db.create_all()` roda antes) + registro na lista de `executar_migracoes()`.

## Decisão crítica 1: diff por CAMPO, não por linha

O payload guarda **somente os campos que mudaram**, não a linha inteira.

Motivo: com payload de linha inteira, este cenário destrói dado real —
usuário renomeia a tarefa (snapshot grava `percentual_concluido=40`) → um RDO
aponta progresso (`60`) → usuário dá Ctrl+Z → o desfazer restauraria `40`,
apagando progresso apurado que **não** fazia parte da ação desfeita.

Com diff por campo, desfazer um rename escreve só `nome_tarefa`. A cascata de
datas do motor entra no payload porque ela realmente mudou naquela ação — que
é exatamente o que o spec pede ("payloads guardam o estado de todas as tarefas
e vínculos afetados, incluindo as datas alteradas pela cascata").

## Decisão crítica 2: identidade estável — ids nunca ressuscitam

- **Tarefas**: identificadas por `id`. Com o soft delete (Step D) a linha nunca sai da tabela, então criar/excluir viram mutação de campo (`ativa`). Desfazer uma criação = `ativa=False`; desfazer uma exclusão = `ativa=True`. Nenhum id precisa ser recriado, e apontamentos de RDO/medição continuam apontando para a linha certa.
- **Vínculos**: identificados pelo par natural `(predecessora_id, sucessora_id)` — que já tem `UNIQUE (uq_tarefa_vinculo_par)`. Vínculo é hard delete mesmo; recriar com id novo é seguro porque **nada referencia `tarefa_vinculo.id`** a não ser a API. Assim o desfazer nunca precisa forçar PK nem mexer em sequence do Postgres.

## Step A — Modelo + migração 224

### A1. `models.py` — `CronogramaAcao`

```
id, obra_id (FK CASCADE), admin_id (FK usuario), usuario_id (FK usuario),
is_cliente (bool, default False), tipo_acao (VARCHAR 32),
payload_antes (JSON), payload_depois (JSON),
desfeita (bool, default False), criada_em (DateTime)
```

Índice composto `(obra_id, usuario_id, is_cliente, id)` — a consulta da pilha é sempre por essa chave.

`is_cliente` é coluna e não campo do payload: a pilha do plano do cliente (`?cliente=1`) e a do plano interno são **pilhas distintas**; misturá-las aplicaria payload no conjunto errado de tarefas.

### A2. Migração 224 (idempotente, padrão da 222)

`CREATE TABLE IF NOT EXISTS cronograma_acao (...)` + índice. Registrar em `executar_migracoes()` como `(224, "Cronograma editável Fase 3 — tabela cronograma_acao (pilha de desfazer/refazer por obra+usuário)", _migration_224_cronograma_acao)`.

## Step B — Serviço `services/cronograma_undo.py`

```python
CAMPOS_TAREFA = ('tarefa_pai_id','predecessora_id','ordem','nome_tarefa',
                 'duracao_dias','data_inicio','data_fim','quantidade_total',
                 'unidade_medida','responsavel','percentual_concluido',
                 'modo_apontamento','subatividade_mestre_id','servico_id',
                 'is_critica','folga_dias','ativa','arquivada_em')
LIMITE_PILHA = 50
```

- `snapshot_obra(obra_id, admin_id, cliente) -> dict` — **duas** queries (tarefas SEM filtro de `ativa`, para enxergar o arquivamento; vínculos da obra). Serializa datas em ISO. Vínculos por chave `"pred-suc"`.
- `diff_snapshots(antes, depois) -> (payload_antes, payload_depois) | (None, None)` — diff por campo; id só em `depois` ⇒ `antes={'ativa': False}`, `depois={'ativa': True}` (criação); id só em `antes` ⇒ **ignorado com log** (hard delete de tarefa não é desfazível; não deve ocorrer com a flag on). Devolve `(None, None)` quando não houve mudança — é isso que faz rota que retornou 400/404 não registrar ação nenhuma.
- `aplicar_payload(obra_id, admin_id, cliente, payload) -> list[TarefaCronograma]` — escreve os campos, faz upsert/delete de vínculos por par, commita e devolve as tarefas tocadas. **Não chama `recalcular_obra`**: o payload já contém as datas pós-cascata, e re-agendar poderia divergir do estado gravado.
- `registrar_acao(obra_id, admin_id, usuario_id, cliente, tipo_acao, antes)` — tira o snapshot `depois`, diffa, e se houve mudança: apaga as ações `desfeita=True` da pilha (nova ação descarta o refazer pendente), insere, e poda para `LIMITE_PILHA`.
- `desfazer(...)` / `refazer(...)` — `desfeita=False` mais recente / `desfeita=True` mais antiga. Devolvem `(acao, afetadas)` ou `(None, [])`.
- `estado_pilha(...) -> (pode_desfazer, pode_refazer)`.

Invariante da pilha: como toda ação nova apaga as `desfeita=True`, a pilha é sempre "um bloco de `desfeita=False` embaixo, um bloco de `desfeita=True` em cima" — por isso desfazer/refazer são um simples `ORDER BY id` nas pontas.

## Step C — Decorator e rotas (`cronograma_views.py`)

### C1. `_com_undo(tipo_acao)`

Decorator aplicado **por fora** da view (abaixo de `@login_required`). Com a flag off chama a view direto e não faz nada. Com a flag on: snapshot antes → executa a view → `registrar_acao`. Como o registro só grava se houve diff, **erro 400/404 e rollback não sujam a pilha** — sem nenhum tratamento especial por rota.

Falha ao gravar o histórico é logada e engolida: o histórico nunca pode derrubar uma edição que já foi commitada.

Aplicar em: `criar_tarefa`, `atualizar_tarefa`, `excluir_tarefa`, `criar_vinculo`, `atualizar_vinculo`, `excluir_vinculo`, `recuar_tarefa`, `desrecuar_tarefa`, `reordenar`. **Não** em `recalcular` (idempotente, não é ação do usuário) nem nas próprias rotas de desfazer/refazer.

### C2. Rotas novas

```
POST /cronograma/obra/<int:obra_id>/desfazer
POST /cronograma/obra/<int:obra_id>/refazer
```

Guards: `_guard_rotas_vinculo` (404 opaco com flag off). Pilha vazia → 400 `'Não há nada para desfazer'` / `'Não há nada para refazer'`.

Resposta: shape das rotas irmãs + estado da pilha —
`{status, tarefa: null, tarefas (com nivel), tarefas_afetadas, tipo_acao, pode_desfazer, pode_refazer}`.

### C3. `excluir_tarefa` — soft delete com a flag ON

Com a flag ON: `ativa=False`, `arquivada_em=utcnow()` em vez de `db.session.delete`, e **hard delete dos vínculos** da tarefa (o par natural fica no payload, então o desfazer os recria). Re-parentagem de filhas e limpeza de `predecessora_id` continuam iguais — são mutações de campo capturadas pelo snapshot. Com a flag OFF, o hard delete de hoje permanece intocado.

## Step D — Conserto do vazamento de tarefa arquivada (fora da flag)

Decisão do usuário: adicionar `.filter(TarefaCronograma.ativa.is_(True))` em
`services/cronograma_fisico_financeiro.py:231` e `portal_obras_views.py:146`.
Vale para todo tenant, inclusive os de flag off — conserta o vazamento que já
existe hoje para tarefas arquivadas pela reconciliação de .mpp. Registrar em
teste que a tarefa arquivada não aparece em nenhum dos dois.

## Step E — Frontend (`templates/obras/cronograma.html`)

- Toolbar `{% if editor_v2 %}`: **Desfazer** (`Ctrl+Z`) e **Refazer** (`Ctrl+Y`), `disabled` conforme `pode_desfazer`/`pode_refazer`.
- `cronograma_obra` passa o estado inicial da pilha para o template.
- No keydown global (que hoje faz `if (e.ctrlKey || e.metaKey || e.altKey) return`), tratar `Ctrl+Z`/`Ctrl+Y` **antes** desse return — e sem exigir `gradeSel` (desfazer não depende de célula selecionada).
- `desfazer()`/`refazer()` reusam `_aplicarListaServidor` da Fase 2 e atualizam os botões pelo `pode_*` da resposta.
- Após qualquer mutação bem-sucedida: `pode_desfazer=true`, `pode_refazer=false` (é exatamente a invariante "ação nova descarta o refazer") — evita tocar no shape de resposta das outras rotas.

## Step F — Testes (`tests/test_cronograma_undo_api.py`)

1. Editar nome → desfazer restaura o nome; refazer reaplica.
2. Desfazer de edição de duração restaura **a cascata inteira** (datas da sucessora).
3. Desfazer NÃO mexe em campo que a ação não tocou (regressão da Decisão 1: apontamento de RDO altera `percentual_concluido` entre a ação e o Ctrl+Z; o desfazer preserva o valor novo).
4. Criar tarefa → desfazer arquiva (`ativa=False`, some da lista); refazer traz de volta.
5. Excluir tarefa → desfazer restaura tarefa **e vínculos**; apontamento de RDO sobrevive.
6. Recuar → desfazer restaura `tarefa_pai_id` e `ordem`.
7. Vínculo criado → desfazer remove; editado (tipo/lag) → desfazer restaura o par.
8. Ação nova após desfazer descarta o refazer pendente (400 no refazer).
9. Pilha vazia → 400 nas duas rotas, mensagens verbatim.
10. Flag off → 404 nas duas rotas; e nenhuma ação é gravada com flag off.
11. Rota que falha (400) não grava ação na pilha.
12. Pilha por usuário e por obra: ação de outro usuário/obra não é desfeita; cross-tenant → 404.
13. Poda em 50: a 51ª ação descarta a mais antiga.
14. Tarefa arquivada não aparece em físico-financeiro nem no portal do cliente (Step D).

**Regressão:** suíte `-k cronograma` completa + `test_replanejamento`, `test_cronograma_restaurar_versao` (mexem em `ativa`).

## Riscos e mitigações

| Risco | Mitigação |
|---|---|
| Desfazer destruir progresso de RDO | Diff por campo (Decisão 1) + teste 3 |
| Soft delete deixar tarefa "fantasma" em relatório | Auditoria feita; Step D fecha os 2 pontos; teste 14 |
| Pilha crescer sem limite | Poda em 50 por (obra, usuário, modo) + teste 13 |
| Payload aplicar no plano errado (cliente × interno) | `is_cliente` é coluna e filtra a pilha |
| Falha ao gravar histórico derrubar a edição | `registrar_acao` engole e loga; a edição já commitou |
| Rota com erro sujar a pilha | Registro condicionado a diff não-vazio + teste 11 |
| Ctrl+Z sequestrar undo nativo de um input | Guard `closest('input, select, textarea')` já existente no keydown global |

## Sequência de entrega

1. Step A (modelo + migração) → 2. Step B (serviço) → 3. Step C (decorator + rotas + soft delete) → 4. Step D (filtros `ativa`) → 5. Step E (frontend) → 6. Step F (testes + regressão).
