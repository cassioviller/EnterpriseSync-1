# Plano de Implementação — Fase 2: Grade tipo planilha (`cronograma_editor_v2`)

Spec: `docs/superpowers/specs/2026-07-24-cronograma-editavel-design.md` (seções 4 e 9). Base: Fase 1 mergeada em `73f58d3e`. Tudo atrás da flag `cronograma_editor_v2` — **flag OFF = comportamento byte-idêntico ao atual** (dblclick para editar, sem toolbar nova, rotas novas devolvem 404 opaco como as de vínculo).

## Contexto verificado no código

- **Tabela** (`templates/obras/cronograma.html:107-327`): colunas fixas por `cellIndex` — 0 grip, 1 `#`, 2 nome, 3 dur, 4 início, 5 término, 6 pred, 7 qtd/un, 8 resp, 9 planejado, 10 realizado, 11 ações. Cada célula editável tem um `<span>` com classe própria (`.nome-tarefa`, `.dur-val`, `.inicio-val`, `.pred-val`, `.qty-val`, `.resp-val`) e `ondblclick="iniciarEdicao(this, id, campo)"`. Linhas-filho nascem com `tarefa-filho d-none` (colapsadas); `data-pai`/`data-nivel` nos `<tr>`.
- **`iniciarEdicao` (978-1155)**: cria input/select dentro do span; commit em blur/Enter, cancela em Esc; `salvarCampo` (1243) já faz batch com `tarefas_afetadas` + revert/toast em erro. Não há listener global de teclado hoje.
- **`_mapas_vinculos` (cronograma_views.py:109)** devolve `(vinculos_por_sucessora, linha_para_tarefa, tarefa_para_linha, ids_resumo)` a partir de `ordenar_arvore_visual` — fonte única da numeração visual e dos níveis (`com_nivel=True`).
- **`criar_tarefa` (431)**: sempre anexa no fim (`nova_ordem = ultima.ordem + 1`, linha 493); aceita `tarefa_pai_id` mas **não** aceita posição. **`reordenar` (1287)**: renumera `ordem = idx` flat pela lista recebida; não mexe em `tarefa_pai_id` — indent/outdent precisa de rota própria.
- **`atualizar_tarefa` (879-902)** já aceita `tarefa_pai_id` com checagem de ciclo hierárquico (loop ascendente) — reutilizável, mas sem reposicionamento de `ordem` nem validações de resumo/vínculo.
- **Scheduler**: `montar_grafo` (163) ignora com warning vínculo cuja ponta não é folha; roll-up (424-446) sobrescreve datas/duração do pai; `_iniciadas_de` (473) só considera folhas; `recalcular_obra` (511) persiste só diffs. O motor **tolera** "pai com vínculos", mas a Fase 1 nas views **rejeita duro com 400** (`cronograma_views.py:853-859` e `criar_vinculo:1207-1210`).
- **Padrão de teste**: `tests/test_cronograma_vinculos_api.py` — `_ambiente`/`_tarefa` de `test_cronograma_versao_service`, `_client_como` de `test_cronograma_endpoints_m05`, `_flag_editor_v2` local, requests fora de `app_context`.

## Decisão crítica: indent que transforma folha-com-vínculos em resumo

Quando X é recuada sob P e P era folha, é **P** que vira resumo. **Decisão: rejeitar com 400**, não auto-remover — padrão consistente da Fase 1 (nunca mutação silenciosa de vínculos); auto-remoção seria destrutiva antes da Fase 3 (undo). Mensagem:

> `'A tarefa "{P.nome_tarefa}" tem vínculos de predecessora/sucessora e viraria uma tarefa-resumo — remova os vínculos dela antes de recuar'`

P folha **iniciada** (predicado `ids_tarefas_iniciadas`) não pode virar resumo:

> `'A tarefa "{P.nome_tarefa}" já foi iniciada e não pode virar tarefa-resumo'`

**Datas ao virar/deixar de ser pai** (só documentação + teste, o motor já resolve):
- Folha → pai: no primeiro `recalcular_obra` as datas próprias são sobrescritas pelo roll-up.
- Pai → folha (outdent do último filho): mantém as datas do último roll-up; no próximo recálculo é folha (âncora "não antes de" da própria `data_inicio`, fim recomputado da duração). Não tem vínculos (invariante garantiu).
- A tarefa recuada (X) continua folha e mantém vínculos e âncora intactos.

---

## Step A — Backend: rotas de indent/outdent (`cronograma_views.py`)

### A1. Rotas novas (padrão `_guard_rotas_vinculo` — 404 opaco com flag off)

```
POST /cronograma/obra/<int:obra_id>/tarefa/<int:tarefa_id>/recuar     → recuar_tarefa()
POST /cronograma/obra/<int:obra_id>/tarefa/<int:tarefa_id>/desrecuar  → desrecuar_tarefa()
```

Guards na ordem das rotas irmãs: `_check_v2` → `_editor_v2_on()` (senão 404 `'Não encontrado'`) → obra do tenant (404) → `_guard_editar_obra` → tarefa no obra/tenant/modo.

### A2. Semântica (calculada 100% no servidor, a partir de `ordenar_arvore_visual`)

Helper novo `_estrutura_visual(obra_id, admin_id, cliente_mode)` → `(ordenadas, nivel_map, filhas_map)`. O frontend envia **só a ação** — fonte de verdade é o servidor.

**Recuar (indent, semântica Project):** novo pai = irmão anterior (tarefa mais próxima ACIMA na ordem visual com o mesmo `tarefa_pai_id`). Validações em ordem:
1. Sem irmão anterior → 400: `'Não é possível recuar: não há tarefa acima no mesmo nível para ser o novo grupo'`.
2. Novo pai P já é resumo → permitido; X entra como última filha.
3. P é folha: rejeitar se P tem vínculo (mensagem acima); rejeitar se P iniciada (mensagem acima).
4. Aplicar: `X.tarefa_pai_id = P.id`; reposicionar X **com toda a subárvore** como última filha de P.

**Desrecuar (outdent):**
1. `X.tarefa_pai_id is None` → 400: `'A tarefa já está no nível raiz — não é possível desrecuar'`.
2. Novo pai = avô; X (com subárvore) vira próxima irmã do antigo pai, logo após a subárvore inteira dele. Irmãs seguintes permanecem no antigo pai (desvio deliberado do Project puro; registrar no docstring).
3. Antigo pai sem filhas vira folha naturalmente; devolvê-lo em `tarefas` para o front atualizar classes.

**Persistência comum** (`_aplicar_hierarquia(...)`): reconstruir a lista visual alvo (DFS com a mudança), `ordem = idx` para TODAS as tarefas do modo (estratégia flat do `/reordenar`), `flush()`, `recalcular_obra(commit=False)`, `commit()`. `ErroCiclo` → rollback + 400 (defensivo). Manter o check de ciclo hierárquico ascendente como defesa.

### A3. Resposta (mesmo shape das rotas irmãs + `nivel`)

```json
{ "status": "ok", "tarefa": {...},
  "tarefas": [ {..., "nivel": 0}, ... ],
  "tarefas_afetadas": [ {...}, ... ] }
```

Serializar com `_mapas_vinculos` **depois** do commit (numeração pode mudar). `nivel` injetado pós-serialização (`d['nivel'] = nivel_map.get(t.id, 0)`).

## Step B — Backend: inserir acima/abaixo (`criar_tarefa`)

Somente no branch flag-ON (após linha 624):

- Body ganha `ref_tarefa_id` (int) + `posicao` (`'acima'|'abaixo'`). Ausentes → comportamento atual.
- Ref inválida → 400: `'Tarefa de referência não encontrada nesta obra'`; posicao inválida → 400: `"Posição inválida: use 'acima' ou 'abaixo'"`.
- Nova tarefa herda `tarefa_pai_id` da referência (irmã). `'abaixo'` cai após a subárvore inteira da ref.
- Reusar `_aplicar_hierarquia`/renumeração flat + `recalcular_obra(commit=False)` + commit único.
- Resposta: acrescentar `tarefas` (com `nivel`) ao JSON já devolvido.

`excluir_tarefa` já cobre o botão Excluir (confirmação existente no front).

## Step C — Frontend: grade tipo planilha (`templates/obras/cronograma.html`)

Tudo dentro de `if (EDITOR_V2)` / `{% if editor_v2 %}`.

### C1. Toolbar (Jinja, linhas 23-43)

`{% if editor_v2 %}` grupo: **Recuar** (`Alt+Shift+→`), **Desrecuar** (`Alt+Shift+←`), **Inserir acima**, **Inserir abaixo**, **Excluir linha** — `disabled` sem seleção (`atualizarToolbarGrade()`), tooltips com atalhos.

### C2. Máquina de estados de seleção/edição

Estado: `gradeSel = null | { tarefaId, col }`, `gradeEditando` derivável.

- `COLS_NAV = [2,3,4,5,6,7,8]`; editáveis `{2:'nome_tarefa', 3:'duracao_dias', 4:'data_inicio', 6:'predecessoras_texto', 7:'quantidade_total', 8:'responsavel'}` com spans `{2:'.nome-tarefa', 3:'.dur-val', 4:'.inicio-val', 6:'.pred-val', 7:'.qty-val', 8:'.resp-val'}`. Col 5 selecionável somente-leitura.
- **Clique** (delegado no `#tarefasBody`, só flag on): 1º clique → `selecionarCelula(row, col)` (classe `.grade-cel-sel`, outline azul, `scrollIntoView`); clique em célula já selecionada → `entrarEdicao()`. `ondblclick` server-rendered permanece (inofensivo flag on).
- **`entrarEdicao(charInicial?)`**: bloqueios client-side com toast (backend autoritativo): pai não edita dur/início/qtd/pred (`'Tarefa-resumo: datas e duração vêm das subtarefas'`); iniciada → `'Tarefa já iniciada — o início não pode ser alterado'`. Senão chama `iniciarEdicao` existente; `charInicial` → `inp.value = charInicial`.
- **Teclado global** — um `document.addEventListener('keydown')` só com flag on. Guards: (1) `e.target.closest('input, select, textarea, [contenteditable]')` → return; (2) `.modal.show, .offcanvas.show` → return; (3) sem `gradeSel` → return. Teclas: `Alt+Shift+→/←` indent/outdent (antes das setas); setas movem (vertical pula `.d-none`); `Tab`/`Shift+Tab` horizontal com wrap; `Enter` desce; `F2` edita; `Esc` limpa; caractere imprimível → `entrarEdicao(e.key)`.
- **Dentro do editor** (gated em `iniciarEdicao`): `Tab` → commit + `moverSelecao(±1, 0)`; `Enter` commit + desce. Seleção sobrevive re-render (spans, não `<td>`).
- `Ctrl+Z`/`Ctrl+Y`: Fase 3 — não registrar.

### C3. Indent/outdent/insert — wiring e DOM

- Extrair bloco de hierarquia de `excluirTarefa` (2105-2143) para `sincronizarHierarquiaDOM(listaTarefas)` — usada por excluir, recuar, desrecuar, inserir. Acrescentar `row.dataset.nivel` e `padding-left = nivel*20px` (multi-nível).
- `recuarSelecionada()`/`desrecuarSelecionada()`: POST; sucesso → `tarefas = data.tarefas`, reordenar `<tr>`, `sincronizarHierarquiaDOM`, expandir novo pai / remover `d-none` da subárvore movida, `tarefas_afetadas.forEach(updateTarefaLocal)`, `renumerarTudo()`, `renderGantt()`, manter `gradeSel`. Erro → toast verbatim.
- `inserirLinha('acima'|'abaixo')`: `criar_tarefa` com `{nome_tarefa:'Nova tarefa', duracao_dias:1, ref_tarefa_id, posicao}`; sucesso → sync + selecionar nome da nova linha + abrir edição. Modal "Nova Tarefa" continua para o fluxo completo.
- Excluir da toolbar → `excluirTarefa` existente.

### C4. Mobile

Intocado.

## Step D — Testes

**Novo `tests/test_cronograma_grade_api.py`** (padrão do `test_cronograma_vinculos_api.py`):

1. Recuar B sob A → 200, `B.tarefa_pai_id == A.id`, `tarefas` com `nivel`, A em `tarefas_afetadas` com roll-up.
2. Recuar primeira linha → 400 mensagem exata.
3. Recuar primeira filha de grupo → 400 mesma mensagem.
4. Recuar sob folha com vínculo → 400 mensagem de vínculos; nada persistido.
5. Recuar sob folha iniciada → 400 "já foi iniciada".
6. Recuar sob resumo → última filha; `ordem` renumerada flat.
7. Desrecuar raiz → 400.
8. Desrecuar filha → irmã do ex-pai, após a subárvore; ex-pai vira folha (asserção do comportamento pai→folha).
9. Flag off → 404 nas rotas novas.
10. Cross-tenant → 404 opaco; nada persistido.
11. Inserir acima/abaixo: posição correta; "abaixo" de resumo cai após a subárvore; ref inexistente → 400; flag off ignora os campos.
12. Recuar reordena numeração → `predecessoras_texto` reflete linhas novas.

**Regressão:** `test_cronograma_vinculos_api.py`, `test_cronograma_permissoes.py`, `test_cronograma_multitenancy.py`, `test_cronograma_interface_obra.py`, `test_cronograma_versao_service.py`.

## Riscos e mitigações

| Risco | Mitigação |
|---|---|
| Keydown global sequestrando inputs/modais | Guards `closest(...)` + `.modal.show/.offcanvas.show`; listener só com flag on |
| Flag off mudar UX | Toolbar em `{% if editor_v2 %}`; listeners atrás de `if (EDITOR_V2)`; `ondblclick` intocado |
| Numeração de predecessoras defasada após indent | Serialização pós-commit com `_mapas_vinculos`; front substitui `tarefas` inteiro + `renumerarTudo()` |
| DOM de hierarquia divergir (multi-nível, toggles) | Helper único `sincronizarHierarquiaDOM` com `nivel` explícito do servidor |
| Renumeração de `ordem` colidir com drag SortableJS | Mesma estratégia flat `ordem = idx`; operações sequenciais |
| Linha movida invisível (pai colapsado) | Front força expansão do novo pai |
| Pré-checagens client-side divergirem | São cortesia; backend sempre valida |

## Sequência de entrega (subagentes)

1. **Backend** — Steps A+B em `cronograma_views.py`.
2. **Testes de API** — Step D (+ regressão) — depende de 1.
3. **Frontend** — Steps C1-C3 — depende de 1.
4. **Verificação final** — regressão completa, flag off idêntico.
