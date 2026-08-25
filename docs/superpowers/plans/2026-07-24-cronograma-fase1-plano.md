# Plano de Implementação — Fase 1: Motor de Agendamento (`cronograma_editor_v2`)

> **Estado em 2026-08-25 (varredura de fecho):** ✅ **FECHADO** — entregue; 🔬 todos os arquivos prometidos existem. 🔬 14/14 dos arquivos prometidos existem na árvore.
>
> Não há trabalho pendente aqui. **As caixas `- [ ]` abaixo não foram marcadas de propósito:** elas são
> rascunho de execução, não registro de estado. Quem carrega a verdade é este bloco,
> o `ESTADO-ATUAL.md`, o código e o git. O veredito acima foi dado por **existência de
> arquivo na árvore**, nunca por contagem de caixa.


Spec aprovado: `docs/superpowers/specs/2026-07-24-cronograma-editavel-design.md`

## Contexto verificado no código

- `TarefaCronograma` em `models.py:5665` — tem `predecessora_id` (única, FK self, `SET NULL`), `tarefa_pai_id`, `ordem`, `duracao_dias`, `data_inicio/fim`, `percentual_concluido`, `data_entrega_real`, `is_marco`, `ativa`, `is_cliente`, `admin_id`.
- Migrações: funções numeradas em `migrations.py`, registradas na lista `migrations_to_run` dentro de `executar_migracoes()` (linha ~5142; última é a **221**, linha 5334). Padrão: SQL cru idempotente (`IF NOT EXISTS`) via `db.engine.begin()`, log `[Migration NNN]`. Nota: o app faz `create_all` antes das migrações (comentário da migration 213), então DDL deve ser sempre `IF NOT EXISTS`.
- Flag de tenant: coluna boolean em `ConfiguracaoEmpresa` (`models.py:4141`, `cronograma_mpp_ativo`), migração espelho (211, `migrations.py:15445`), helper `utils/tenant.py:113` (`cronograma_mpp_ativo()`) e script CLI `scripts/flag_cronograma_mpp.py` (`definir_flag`/`status_flag`).
- Rotas em `cronograma_views.py`: `criar_tarefa` (340), `atualizar_tarefa` (542 — hoje chama `recalcular_cronograma` do engine antigo quando muda `duracao_dias|predecessora_id|data_inicio` e devolve `{status, tarefa, tarefas}`), `excluir_tarefa` (763 — hard delete + `predecessora_id=None` nos dependentes), `recalcular` (802), `cronograma_obra` (235 — DFS tree-flatten que define a ordem visual das linhas).
- Engine atual `utils/cronograma_engine.py`: `recalcular_cronograma` (297) só entende predecessora única FS lag 0; helpers `proximo_dia_util`, `calcular_data_fim`, `dias_uteis_entre`, `verificar_ciclo`, `get_calendario` (respeita `CalendarioEmpresa.considerar_sabado/domingo`).
- Frontend `templates/obras/cronograma.html` (2508 linhas): `salvarCampo` (1184) já faz batch-update quando a resposta traz `data.tarefas` (`updateTarefaLocal` + `renderGantt`), reverte célula + toast em erro (1216-1222); célula de predecessora é `<select>` de tarefas via `iniciarEdicao` (1000-1024) e badge `renderPredBadge` (1133); drag da barra faz PUT de `data_inicio` no `mouseup` (2129-2169) e reverte `left` em erro; `renderGantt` (2172) escolhe classe da barra por pai/%; aviso mobile nas linhas 92-97 (mobile = só lista).
- "Tarefa iniciada": apontamentos vivem em `RDOApontamentoCronograma` (`models.py:5784`, FK `tarefa_cronograma_id`), gravados por `services/cronograma_apontamento_service.registrar_apontamento`; terceiros usam `data_entrega_real`; subempreitada atualiza `percentual_concluido` por outra via (`_atualizar_percentual_com_subempreitada`, `cronograma_views.py:1263`).
- Testes: pytest (`pyproject.toml`, `--strict-markers --timeout=300`), `tests/conftest.py` importa `main` e usa o app real; padrão de fixtures em `tests/test_cronograma_versao_service.py` (`_ambiente`, `_tarefa`); flag testada em `tests/test_flag_cronograma_mpp.py`.

---

## Step A — Modelo, migrações e flag

### A1. Modelo `TarefaVinculo` (`models.py`, logo após `TarefaCronograma`, ~linha 5778)

```python
class TarefaVinculo(db.Model):
    __tablename__ = 'tarefa_vinculo'
    __table_args__ = (
        db.UniqueConstraint('predecessora_id', 'sucessora_id', name='uq_tarefa_vinculo_par'),
        db.CheckConstraint('predecessora_id <> sucessora_id', name='ck_tarefa_vinculo_nao_reflexivo'),
        db.CheckConstraint("tipo IN ('TI','II','TT','IT')", name='ck_tarefa_vinculo_tipo'),
    )
    id = db.Column(db.Integer, primary_key=True)
    admin_id = db.Column(db.Integer, db.ForeignKey('usuario.id'), nullable=False, index=True)
    obra_id = db.Column(db.Integer, db.ForeignKey('obra.id', ondelete='CASCADE'), nullable=False, index=True)
    predecessora_id = db.Column(db.Integer, db.ForeignKey('tarefa_cronograma.id', ondelete='CASCADE'), nullable=False, index=True)
    sucessora_id = db.Column(db.Integer, db.ForeignKey('tarefa_cronograma.id', ondelete='CASCADE'), nullable=False, index=True)
    tipo = db.Column(db.String(2), nullable=False, default='TI', server_default='TI')
    lag_dias = db.Column(db.Integer, nullable=False, default=0, server_default='0')
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
```

`ondelete='CASCADE'` nas FKs de tarefa é deliberado: `excluir_tarefa` faz `db.session.delete` hard (linha 784) e os vínculos devem morrer junto (o `SET NULL` do legado `predecessora_id` continua como está).

Em `TarefaCronograma`, adicionar (aditivo, com `server_default` para não quebrar dados existentes):

```python
is_critica = db.Column(db.Boolean, nullable=False, default=False, server_default='false')
folga_dias = db.Column(db.Integer, nullable=True)   # NULL = nunca calculado pelo motor novo
```

Em `ConfiguracaoEmpresa` (~linha 4160, junto das irmãs):

```python
cronograma_editor_v2 = db.Column(db.Boolean, nullable=False, default=False, server_default='false')
```

### A2. Migrações (`migrations.py`)

Funções novas registradas em `migrations_to_run` após a linha 5334:

- **222 — `_migration_222_tarefa_vinculo_e_colunas()`**: `CREATE TABLE IF NOT EXISTS tarefa_vinculo (...)` com os constraints/índices acima (padrão da 207, `migrations.py:15223`); `ALTER TABLE tarefa_cronograma ADD COLUMN IF NOT EXISTS is_critica BOOLEAN NOT NULL DEFAULT FALSE` e `folga_dias INTEGER`; `ALTER TABLE configuracao_empresa ADD COLUMN IF NOT EXISTS cronograma_editor_v2 BOOLEAN NOT NULL DEFAULT FALSE` (padrão da 211).
- **223 — `_migration_223_backfill_vinculos_de_predecessora()`**: data migration em SQL único:

```sql
INSERT INTO tarefa_vinculo (admin_id, obra_id, predecessora_id, sucessora_id, tipo, lag_dias)
SELECT t.admin_id, t.obra_id, t.predecessora_id, t.id, 'TI', 0
FROM tarefa_cronograma t
JOIN tarefa_cronograma p ON p.id = t.predecessora_id
WHERE t.predecessora_id IS NOT NULL
  AND t.predecessora_id <> t.id
  AND p.obra_id = t.obra_id AND p.admin_id = t.admin_id
  AND NOT EXISTS (SELECT 1 FROM tarefa_vinculo v
                  WHERE v.predecessora_id = t.predecessora_id AND v.sucessora_id = t.id)
```

  Logar separadamente o COUNT das linhas **puladas** por `p.obra_id <> t.obra_id` ou `p.admin_id <> t.admin_id` (dados sujos conhecidos — ver Riscos). `predecessora_id` fica congelado (leitura), não é apagado.

### A3. Script de flag e helper

- `scripts/flag_cronograma_editor_v2.py` — cópia estrutural de `scripts/flag_cronograma_mpp.py` (mesmos `definir_flag(admin_id, ativo)`, `status_flag(admin_id)`, CLI `--ligar/--desligar/--status`), operando `config.cronograma_editor_v2`.
- `utils/tenant.py` — novo helper `cronograma_editor_v2_ativo() -> bool`, espelho exato de `cronograma_mpp_ativo()` (linha 113): exige `is_v2_active()` + flag, nunca levanta, default False.

**Verificação A:** subir o app (migrações rodam no boot), conferir no psql: tabela criada, contagem de vínculos == contagem de `predecessora_id` válidos intra-obra, flag FALSE em todos os tenants; `python scripts/flag_cronograma_editor_v2.py <id> --status`. Rodar `tests/test_flag_cronograma_mpp.py` como sanity do padrão.

---

## Step B — `services/cronograma_scheduler.py` (novo arquivo)

Motor puro + camada fina de persistência. Calendário fixo seg–sex nesta fase (ignora `CalendarioEmpresa` de propósito — decisão da spec; documentar no docstring).

### B1. Matemática de dias úteis (funções puras, sem DB)

```python
def eh_dia_util(d: date) -> bool                      # d.weekday() < 5
def proximo_dia_util(d: date) -> date                 # d se útil, senão rola p/ frente
def dia_util_anterior(d: date) -> date
def somar_dias_uteis(d: date, n: int) -> date         # n>0 anda p/ frente, n<0 p/ trás, n=0 → proximo_dia_util(d)
def fim_por_duracao(inicio: date, duracao: int) -> date   # marco/dur 0 → inicio; senão somar_dias_uteis(inicio, duracao-1)
def duracao_util_entre(inicio: date, fim: date) -> int    # nº de dias úteis inclusivo
```

### B2. Estruturas e grafo

```python
@dataclass
class NoTarefa:            # projeção pura de TarefaCronograma
    id: int; nome: str; duracao: int; inicio: date | None; fim: date | None
    pai_id: int | None; is_marco: bool; ancorada: bool

@dataclass
class VinculoSpec:
    predecessora_id: int; sucessora_id: int; tipo: str; lag: int

class ErroCiclo(ValueError):
    """mensagem em português com NOMES das tarefas do ciclo:
    'Vínculo inválido: "Alvenaria" já depende de "Reboco" (ciclo: Alvenaria → Reboco → Alvenaria).'"""

def montar_grafo(nos, vinculos) -> dict[int, list[VinculoSpec]]
def detectar_ciclo(nos, sucessores) -> list[int] | None    # DFS iterativo, devolve o ciclo p/ mensagem
def ordenar_topologicamente(nos, sucessores) -> list[int]  # Kahn; só folhas entram no grafo
```

### B3. Predicado de âncora ("tarefa iniciada")

```python
def ids_tarefas_iniciadas(obra_id: int, admin_id: int, cliente: bool = False) -> set[int]
```

Uma tarefa-folha é **ancorada** quando qualquer um vale:
1. existe `RDOApontamentoCronograma` com `tarefa_cronograma_id = t.id` (uma query `IN` para a obra inteira, não N+1);
2. `t.data_entrega_real IS NOT NULL` (terceiros/entregas);
3. `(t.percentual_concluido or 0) > 0` — cobre subempreitada e edição manual de %, sem depender da origem.

Tarefas **sem predecessora e não iniciadas** são âncora do tipo "não começar antes de": mantêm a própria `data_inicio` (normalizada para `proximo_dia_util`); sem `data_inicio`, recebem `proximo_dia_util(hoje)`.

### B4. Passe para frente (função pura — coração dos testes unitários)

```python
def calcular_agendamento(nos, vinculos, hoje) -> dict[int, ResultadoTarefa]
```

Para cada folha não ancorada, em ordem topológica, `data_inicio = max` das restrições (P=predecessora, S=sucessora, L=lag em dias úteis):

| Tipo | Restrição |
|---|---|
| `TI` (FS) | `S.inicio ≥ somar_dias_uteis(P.fim, 1 + L)` |
| `II` (SS) | `S.inicio ≥ somar_dias_uteis(P.inicio, L)` |
| `TT` (FF) | `S.fim ≥ somar_dias_uteis(P.fim, L)` → `S.inicio = somar_dias_uteis(S.fim, -(dur-1))` |
| `IT` (SF) | `S.fim ≥ somar_dias_uteis(P.inicio, L)` → inicio derivado como no TT |

Combinado com a âncora "não antes de" (a própria `data_inicio` atual entra no `max`). `data_fim = fim_por_duracao(inicio, duracao)`. Tarefas ancoradas nunca têm datas alteradas, mas suas datas reais alimentam as restrições das sucessoras. Predecessora sem datas (dado legado) = restrição ignorada com aviso no log.

### B5. Roll-up e passe para trás

- Roll-up: pais (qualquer profundidade, de baixo para cima como já faz o engine antigo em 379-387): `inicio = min(filhas)`, `fim = max(filhas)`, `duracao = duracao_util_entre(...)`. Vínculos só entre folhas (validado no Step C).
- Passe para trás: `fim_projeto = max(fim das folhas)`; em ordem topológica reversa, `late_finish` = min das restrições inversas de cada vínculo de saída; `folga_dias = duracao_util_entre(inicio, late_start) - 1` (≥ 0); `is_critica = (folga_dias == 0)`. Folha ancorada participa normalmente do cálculo de folga (pode ser crítica). Pais: `folga_dias = min(filhas)`, `is_critica = any(filhas críticas)`.

### B6. Orquestração e persistência

```python
def recalcular_obra(obra_id: int, admin_id: int, *, cliente: bool = False,
                    commit: bool = True) -> ResultadoAgendamento
# ResultadoAgendamento.tarefas_afetadas: list[TarefaCronograma] (só as que mudaram
# data_inicio/data_fim/duracao_dias/folga_dias/is_critica), já persistidas.
```

Carrega tarefas ativas (`is_cliente=cliente`) + `TarefaVinculo` da obra, monta `NoTarefa`s, chama `ids_tarefas_iniciadas`, `calcular_agendamento`, grava diffs, e reaproveita o rollup de percentual do engine antigo (não duplicar — chamar como `recalcular_cronograma` faz nas linhas 391-405, ou extrair helper). Levanta `ErroCiclo` sem commitar.

Também aqui: `sincronizar_vinculos_de_predecessora_id(obra_id, admin_id) -> int` — materializa `predecessora_id` → vínculo TI/0 faltante (mesma regra da migração 223, escopo de uma obra). Usada pelo pós-importação .mpp e pela geração por proposta (Step C5).

**Verificação B:** `pytest tests/test_cronograma_scheduler.py` — o módulo puro roda sem DB.

---

## Step C — Integração de API (`cronograma_views.py`)

Todas as mudanças condicionadas a `flag_on = cronograma_editor_v2_ativo()`; com flag OFF cada rota executa **exatamente o código de hoje** (guard no topo de cada branch novo).

### C1. Parser de predecessoras — `services/cronograma_predecessor_parser.py` (novo)

```python
def parsear_predecessoras(texto: str, linha_para_tarefa: dict[int, int]) -> list[VinculoSpec]
def formatar_predecessoras(vinculos, tarefa_para_linha: dict[int, int]) -> str
class ErroParsePredecessora(ValueError)  # mensagem em português
```

- Gramática: entradas separadas por `;` (tolerar `,`), cada uma `^(\d+)(TI|II|TT|IT)?([+-]\d+)?$` após `strip()`/uppercase; sem tipo = `TI`; sem lag = 0. String vazia = remover todos os vínculos.
- O número é a **linha visual da grade** (1-based). O mapa linha→tarefa é construído no backend replicando o DFS de `cronograma_obra` (linhas 260-278) — **extrair esse flatten para um helper compartilhado** `ordenar_arvore_visual(tarefas) -> list` (em `utils/cronograma_engine.py`) usado pela view e pelo parser, para que os números nunca divirjam.
- Erros (400, pt-BR): `"Linha 99 não existe na grade"`, `"Tipo de vínculo inválido: 'XX' (use TI, II, TT ou IT)"`, `"Uma tarefa não pode ser predecessora dela mesma"`, `"Linha 12 é uma tarefa-resumo — vincule apenas tarefas-folha"`, `"Formato inválido: '12T+'. Exemplos: 12, 12TI+3, 12II-2"`.

### C2. `_tarefa_to_dict` (linha 86) — campos aditivos (sempre presentes, inofensivos com flag off)

```python
'is_critica': bool(getattr(t, 'is_critica', False)),
'folga_dias': getattr(t, 'folga_dias', None),
'predecessoras_texto': ...,  # via formatar_predecessoras; '' quando sem vínculos
```

Para evitar N+1, as rotas montam um mapa `vinculos_por_sucessora` da obra e passam ao serializador (novo parâmetro opcional).

### C3. Rotas alteradas (mesmos nomes/paths)

- **`atualizar_tarefa` (542):** com flag on —
  - aceita novo campo `predecessoras_texto`; parseia, valida folhas/obra/tenant, aplica diff em `TarefaVinculo` (delete/insert), **não** grava mais `predecessora_id` (congelado);
  - rejeita `data_inicio` em tarefa ancorada: 400 `"Tarefa já iniciada por apontamento de RDO — o início não pode ser alterado"`;
  - substitui o bloco `_SCHEDULING_FIELDS` (737-742) por `recalcular_obra(...)`; `ErroCiclo` → rollback + 400 com a mensagem;
  - resposta: mantém `status/tarefa/tarefas` (compatibilidade) e **adiciona `tarefas_afetadas`** (só os diffs do motor, serializados).
  - Com flag OFF: código atual intocado, **mais** dual-write silencioso do vínculo TI/0 quando `predecessora_id` muda (mantém `tarefa_vinculo` fresca para quando a flag ligar).
- **`criar_tarefa` (340):** flag on — aceita `predecessoras_texto` (além do `predecessora_id` legado do modal), cria vínculos, chama `recalcular_obra`, devolve `201 {status, tarefa, tarefas_afetadas}`. Flag off — intocada + dual-write.
- **`excluir_tarefa` (763):** vínculos caem por CASCADE; com flag on chama `recalcular_obra` depois e adiciona `tarefas_afetadas` à resposta (mantendo `tarefas`).
- **`recalcular` (802):** `if flag_on: recalcular_obra(...)` else engine antigo; resposta inalterada (`tarefas` completa) + `tarefas_afetadas`.

### C4. Rotas novas de vínculo (CRUD explícito)

```
POST   /cronograma/obra/<int:obra_id>/vinculo            → criar_vinculo()
PUT    /cronograma/obra/<int:obra_id>/vinculo/<int:vid>  → atualizar_vinculo()   # tipo/lag
DELETE /cronograma/obra/<int:obra_id>/vinculo/<int:vid>  → excluir_vinculo()
```

Guards idênticos aos existentes (filtro `admin_id`/`obra_id` na query) + 404 se flag off. Corpo: `{predecessora_id, sucessora_id, tipo, lag_dias}` (IDs de tarefa, não linhas). Validações: mesma obra/tenant/modo, ambas folhas, par único, sem auto-vínculo, sem ciclo antes do commit. Resposta: `{status:'ok', vinculo:{...}, tarefas_afetadas:[...]}`.

### C5. Integrações que criam tarefas fora da tela

- `services/cronograma_proposta.materializar_cronograma` (483) e `services/cronograma_versao_service` (aplicação de versão .mpp, ~529-587; restauração ~792-805) continuam gravando `predecessora_id`; adicionar **uma chamada** a `sincronizar_vinculos_de_predecessora_id(obra_id, admin_id)` ao final de cada fluxo. Materialização das predecessoras tipadas de `predecessoras_json` é fase futura — fora de escopo; isto apenas impede vínculos obsoletos.

**Verificação C:** `pytest tests/test_cronograma_vinculos_api.py tests/test_cronograma_permissoes.py tests/test_cronograma_multitenancy.py tests/test_cronograma_interface_obra.py` — os dois últimos com flag off garantem regressão zero.

---

## Step D — Frontend (`templates/obras/cronograma.html`)

`cronograma_obra` (view, 316-331) passa `editor_v2=cronograma_editor_v2_ativo()`; o template define `const EDITOR_V2 = {{ 'true' if editor_v2 else 'false' }};`. **Todo comportamento novo fica atrás de `if (EDITOR_V2)`; com flag off nenhum caminho JS muda.**

1. **Batch-update sem reload:** em `salvarCampo` (1196-1206), `salvarNovaTarefa` (~1683), `salvarEditar` (~1868), handler do `mouseup` do drag (2152-2158) e no handler de exclusão: se `data.tarefas_afetadas`, aplicar `data.tarefas_afetadas.forEach(updateTarefaLocal)` + `renderGantt()` e **não** chamar `recalcularTudo(false)`. `updateTarefaLocal` (1226) já atualiza início/fim/duração/pred por linha — acrescentar folga/crítica.
2. **Barras críticas vermelhas:** em `renderGantt` (2236), com `EDITOR_V2 && t.is_critica && !isPai && perc < 100`, classe `gantt-bar-critica`; CSS novo (fundo `#dc3545`, progresso interno mais escuro). Precedência: `done` > `critica` > `low/leaf`. Tooltip: `" • Caminho crítico (folga 0d)"`.
3. **Célula de predecessoras em formato Project:** com flag on, `iniciarEdicao(..., 'predecessora_id')` (1000-1024) abre `<input type="text">` pré-preenchido com `t.predecessoras_texto` em vez do `<select>`; ao confirmar, `salvarCampo` envia `{predecessoras_texto: valor}`. `renderPredBadge` (1133) e `restaurarCelulaPred` (1144) ganham variante flag-on exibindo o texto formatado (ou `—`). Com flag off, `<select>` e `predecessora_id` intocados.
4. **Erro → toast + revert:** já é o comportamento de `salvarCampo` (1216-1222) e do drag (2161-2167); mensagens de ciclo/tarefa iniciada chegam prontas em `data.msg`. Garantir que a variante texto de `restaurarCelulaPred` restaura o `predecessoras_texto` anterior.
5. **Folga:** exibir `folga_dias` no tooltip da barra (sem coluna nova nesta fase).
6. **Mobile:** intocado.

**Verificação D:** manual em obra piloto com flag ligada — editar duração e ver cascata sem reload; criar ciclo pela célula e ver toast + revert; barra vermelha; desligar a flag e conferir comportamento idêntico ao atual.

---

## Step E — Testes

Novos arquivos em `tests/` (padrão dos existentes; marker `integration` onde houver DB):

1. **`tests/test_cronograma_scheduler.py`** (unitário, sem DB): dias úteis (atravessar fim de semana, n negativo, n=0 normalizando sábado→segunda, duração 1, marco); cada tipo TI/II/TT/IT com lag 0/+3/−2; múltiplas predecessoras → vence a restrição máxima; ciclo direto e indireto → `ErroCiclo` com nomes; âncoras (iniciada e "não antes de"); folga/crítico (cadeia linear toda crítica; ramo paralelo com folga > 0; pai = any); roll-up em dois níveis.
2. **`tests/test_cronograma_predecessor_parser.py`**: válidos (`12`, `12TI`, `12TI+3`, `12II-2`, `12;15TT+1`, espaços, vírgula) e inválidos (linha inexistente, tipo `XX`, auto-referência, resumo, lixo) com mensagens exatas; `formatar_predecessoras` como inverso do parse.
3. **`tests/test_cronograma_vinculos_api.py`** (integração): CRUD de vínculo (tenant → 404, par duplicado → 400, ciclo → 400); PUT de `duracao_dias` com flag on devolve `tarefas_afetadas` com a cascata; PUT `data_inicio` de tarefa com apontamento → 400; DELETE dispara recálculo; `/recalcular` usa motor novo com flag on e antigo com flag off; dual-write com flag off.
4. **`tests/test_migrations_tarefa_vinculo.py`**: idempotência da 222/223 (rodar duas vezes), backfill ignora cross-obra e auto-referência.
5. **Regressão (rodar):** `test_cronograma_versao_service.py`, `test_upload_cronograma.py`, `test_cronograma_reconciliacao.py`, `test_cronograma_automatico_aprovacao.py`, `test_cronograma_proposta_tolerante.py`, `test_cronograma_engine_unificado.py`, `test_cronograma_permissoes.py`, `test_cronograma_multitenancy.py`, `test_flag_cronograma_mpp.py`.

---

## Riscos e mitigação

| Risco | Mitigação / verificação |
|---|---|
| `models.py` gigante — conflitos e create_all implícito | Mudança 100% aditiva num único bloco após `TarefaCronograma`; `server_default` em tudo. |
| Ordem de migração — `create_all` roda antes de `executar_migracoes` | Todo DDL da 222 é `IF NOT EXISTS`; constraints nomeados também no `__table_args__`, então create_all e migração convergem. |
| `predecessora_id` cruzando obras/tenants (dado sujo real) | Backfill 223 filtra intra-obra/tenant e loga as puladas; motor ignora vínculo cuja predecessora não está na obra (warning). |
| `data_inicio` em fim de semana pós-migração | Motor normaliza para `proximo_dia_util` só em não ancoradas e só com flag on; documentar que o 1º recálculo pode deslocar datas. |
| Divergência de numeração de linhas (drag renumera) | Helper único `ordenar_arvore_visual` compartilhado view/parser; após reordenar, frontend refaz `predecessoras_texto` a partir da resposta do servidor. |
| `tarefa_vinculo` obsoleta com flag off | Dual-write TI/0 no PUT/POST legado + `sincronizar_vinculos_de_predecessora_id` em import/proposta/restauração. |
| Dois motores coexistindo | Nenhuma linha do engine antigo alterada; rota decide pela flag em um ponto por rota. |
| Calendário divergente (engine antigo respeita `CalendarioEmpresa`) | Docstring no scheduler; warning no script de flag se `considerar_sabado/domingo` = TRUE. |
| Performance do recálculo total | O(V+E), 3 queries + commit único; medir na maior obra real antes do rollout. |

## Sequência de entrega

A (modelo+migrações+flag) → B (scheduler + unit tests) ∥ C1 (parser + tests) → C (API + testes de API) → D (frontend) → E (regressão completa) → ligar flag no tenant de homologação via script.
