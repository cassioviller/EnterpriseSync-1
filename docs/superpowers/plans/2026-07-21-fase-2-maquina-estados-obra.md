# Fase 2 — Máquina de Estados da Obra + Handoff do Gerente de Projeto

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Trocar o texto livre de `Obra.status` por uma máquina de estados com transições explícitas, histórico auditável de quem mudou o quê e por quê, e fazer da entrada em execução um ato formal — o handoff do Gerente de Projeto, que atribui o responsável e cria o vínculo `UsuarioObra` com papel `GESTOR`.

**Architecture:** Coluna nova `Obra.estado` (vocabulário fechado) convivendo com a coluna legada `Obra.status`, que passa a ser **derivada** por write-through. Quase todas as ~40 queries e templates que leem `status` seguem corretas sem mudança — mas **não todas**, e a exceção é obrigatória, não opcional (ver revisão de 22/07, achado B): a Task 9 faz a obra nascer com `status='Planejamento'`, valor que os quatro filtros do dashboard não reconhecem porque comparam contra `'planejamento'` minúsculo em `IN` case-sensitive. A Task 9 corrige esses filtros na mesma task que cria o problema. O único caminho de escrita é `services/obra_estado.transitar()`, que valida o grafo, exige motivo nas transições que precisam, grava uma linha em `obra_transicao_estado` e sincroniza `status` e `ativo`. O handoff é uma transição especializada (`PLANEJAMENTO → EM_EXECUCAO`) empacotada em `services/obra_handoff.executar_handoff()`, que só passa se houver um `Funcionario` do mesmo tenant com login (`Usuario.funcionario_id`, Fase 1) e se o gate de cronograma estiver resolvido.

**Tech Stack:** Flask 3 + Flask-Login, SQLAlchemy 2 (`models.py`), sistema de migrações próprio numerado (`migrations.py`, `run_migration_safe`), pytest (`bash run_tests.sh --gate`), PostgreSQL, Jinja2 + Bootstrap 5.

---

## Contexto verificado no código (leia antes de começar)

> ### ⚠️ Revisão de 22/07 — leia antes da tabela abaixo
>
> O plano foi escrito em 21/07 no commit `fb4147b`. A **Fase 0.6 / D5 entrou no
> mesmo dia e pisou neste terreno**, e a Fase 1.5 andou ~30 commits por cima.
> Seis pontos foram corrigidos no corpo do plano; os que mudam desenho:
>
> 1. **`utils/status_obra.py` já existe** e se declara *"a única fonte da
>    verdade do vocabulário"* de `Obra.status`. Tem `_chave()` — a mesma
>    normalização de acento/caixa que a Task 1 reimplementava como
>    `_sem_acento()` — e um `@validates('status')` em `models.py:415` que
>    intercepta **toda** escrita, inclusive o write-through de
>    `aplicar_estado()`. Reaproveitar, não duplicar.
> 2. **`'Planejamento'` não está em `STATUS_OBRA_CANONICOS`.** Precisa entrar,
>    senão o estado novo nasce fora do vocabulário canônico do próprio módulo
>    que governa o vocabulário.
> 3. **Os filtros do dashboard quebram com `'Planejamento'`** — achado B,
>    tratado na Task 9.
> 4. **A migration 217 já canonizou `obra.status`** ('Em Andamento' →
>    'Em andamento'). A Task 6 foi reescrita: o que sobra para ela é alinhar
>    `status` ao `estado` recém-derivado, não deduplicar grafia.
> 5. **Falha de migração NÃO aborta o boot** — `run_migration_safe`
>    (`migrations.py:198`) diz literalmente *"Não propagar exceção - apenas
>    logar"*. A justificativa da migration 231 foi corrigida na Task 3.
> 6. **Censo real deste banco: 2.110 `'Em andamento'`, 0 `'Em Andamento'`,
>    4 `'Concluída'`** — e não 7.958/53/13. Os números do plano vieram de
>    outra base. Reconferir em produção antes do rollout.
>
> Âncoras que derivaram: `Obra.status` `:257`→`:297` · `TipoUsuario` `:20`→`:21`
> · `create_all` `:582`→`:595` · migrações `:667`→`:703` · maior migration
> registrada `213`→`221` · `forms.py:42 default='Em Andamento'` →
> `forms.py:44 default='Em andamento'` · `views/obras.py:82-83` já não compara
> igualdade crua, passa por `normalizar_status_obra()`.

Tudo abaixo foi conferido em 2026-07-21 no commit `fb4147b`. Não são suposições.

| Fato | Evidência |
|---|---|
| `Obra.status` é `String(20)` com default `'Em andamento'` — texto livre, sem constraint | `models.py:257` |
| `Obra.responsavel_id` → `funcionario.id`, nullable, **não governa permissão nenhuma** e **não tem `relationship`** | `models.py:258`; templates que usam `obra.responsavel` e hoje renderizam sempre vazio: `templates/obras.html:266`, `templates/obras_moderno.html:760-765`, `templates/obras/detalhes_obra.html:231`, `templates/obras/detalhes_obra_profissional.html:1410`, `relatorios_funcionais.py:217` |
| `Obra.cronograma_revisado_em` é um **estado disfarçado de timestamp**: NULL = "não passou pelo gate", preenchido = "passou". Não grava quem | `models.py:300`; gate em `views/obras.py:1425-1440`; critérios em `views/obras.py:2339-2373` |
| `Obra.ativo` é o **segundo eixo de estado**, paralelo e não sincronizado com `status` | `models.py:275`; `views/obras.py:1259` e `views/obras.py:1296` flipam só `ativo`; a UI chama `ativo=False` de "Concluída / Inativa" em `templates/obras_moderno.html:803` e `:819` |
| Só existem **quatro** escritores de `Obra.status` no código vivo | `models.py:257` (default), `event_manager.py:1018` (cascata da proposta), `views/obras.py:279`+`393` (criação), `views/obras.py:863` (edição) |
| A única "transição" hoje é uma comparação de string com normalização de acento, feita **depois do commit**, só para emitir webhook | `views/obras.py:963-979` |
| O dashboard filtra por uma lista defensiva de valores que **não existem** no banco | `views/dashboard.py:428` e `:1013` → `['ATIVO', 'andamento', 'Em andamento', 'ativa', 'planejamento']`; `:1035` e `:1054` idem sem `'ATIVO'` |
| O dropdown de status é editável pelo tenant, e os defaults divergem em caixa do que o código grava | `services/dropdown_service.py:94` → `['Em Andamento', 'Concluída', 'Pausada', 'Cancelada']` (A maiúsculo) vs `'Em andamento'` gravado por `models.py:257` e `event_manager.py:1018` |
| `forms.py:42` (`ObraForm.status`) tem `default='Em Andamento'` — a terceira grafia | `forms.py:42` |
| A listagem `/obras` renderiza `obras_moderno.html`, **não** `obras.html` | `views/obras.py:262` |
| `templates/obras.html` é **template órfão** — nenhum `render_template` aponta para ele. `obras_safe.html` só é renderizado por `production_routes.py:239` | grep de `render_template` em todo o repo |
| O filtro vivo de status compara igualdade exata de string | `views/obras.py:82-83` (`Obra.status == filtros['status']`); opções em `templates/obras_moderno.html:616-619` |
| `db.create_all()` roda **antes** das migrações | `app.py:582` vs `app.py:667` |
| Consequência prática disso: `CREATE TABLE IF NOT EXISTS` numa migração de tabela nova é **no-op**, porque o `create_all` já criou a tabela a partir do modelo | prova: `migrations.py:13903-13905` declara `json_bruto JSONB`, mas `information_schema` do banco reporta `json` para essa coluna — o `CREATE TABLE` da migration 207 nunca executou |
| `create_all` **não** adiciona coluna a tabela existente — por isso `Obra.estado` precisa de migração de verdade | `app.py:582` + comportamento documentado do SQLAlchemy; é a razão de existir a migration 140 (`migrations.py:10158`) |
| Maior migration registrada: **213** | `migrations.py:4014`; confirmado no banco: `SELECT max(migration_number) FROM migration_history` → `213` |
| Falha de migração **aborta o boot** em produção | `app.py:668-680` |
| O molde de máquina de estados do repo é `CronogramaImportacao` + `CronogramaImportacaoEvento` | `models.py:5018-5044` (estados no docstring), `models.py:5178-5203` (trilha), `services/cronograma_observabilidade.py:34` (`log_transicao`) |
| Trilha de acesso em log estruturado (não em tabela) já existe para escritas | `utils/auditoria_acesso.py:49-88` |
| Catálogo de eventos `dominio.acao` com `_safe_emit` best-effort | `utils/catalogo_eventos.py:110-119`; `emit_obra_concluida` em `:289` |
| Allowlist do webhook n8n | `utils/webhook_dispatcher.py:59-71` |

### A cascata de `proposta_aprovada` — entenda antes de mexer

`EventManager` é um registry de classe: `_handlers[evento]` é uma **lista**, e `emit` percorre na ordem de registro (`event_manager.py:17,24,44`). Não há prioridade nem ordenação explícita — quem é importado primeiro roda primeiro.

Em `app.py`, a ordem é:

1. `app.py:414` — `import event_manager` registra `propagar_proposta_para_obra` (`event_manager.py:871-872`). **É quem cria a `Obra`** (`event_manager.py:1010-1026`), gera `token_cliente`, faz o back-link `proposta.obra_id` e atualiza `valor_contrato`.
2. `app.py:426` — `import handlers.propostas_handlers` registra `handle_proposta_aprovada` (`handlers/propostas_handlers.py:73-74`). Roda **depois**, e depende da `Obra` já existir: cria os `ItemMedicaoComercial` (`handlers/propostas_handlers.py:14-70`) e materializa o cronograma (`handlers/propostas_handlers.py:114-158`).

Nenhum handler commita — a rota chamadora é dona da transação e usa `raise_on_error=True` (`propostas_consolidated.py:2358`, `:2540`; contrato documentado em `event_manager.py:882-887`).

**Regra desta fase:** não registrar handler novo para `proposta_aprovada`. Um handler novo entraria no fim da lista (ou no meio, dependendo do import) e o contrato de ordem passaria a depender de mais um import. O estado inicial da obra é escrito **dentro** de `propagar_proposta_para_obra`, na mesma linha em que a `Obra` nasce.

### Censo real de `Obra.status`

Duas fontes: grep no código e consulta ao banco.

**No banco** (`SELECT status, ativo, count(*) FROM obra GROUP BY 1,2`), executado em 2026-07-21:

| `status` | `ativo` | linhas |
|---|---|---|
| `Em andamento` | `true` | 7 905 |
| `Em Andamento` | `true` | 53 |
| `Concluída` | `true` | 13 |
| `Em andamento` | `false` | 13 |
| **total** | | **7 984** |

Zero `NULL`, zero `admin_id` nulo, três grafias distintas para dois conceitos.

⚠️ **Este é o banco de DESENVOLVIMENTO** (`postgresql://postgres@helium/heliumdb`), cuja volumetria é quase toda carga de suíte automatizada — `ESTADO-ATUAL.md:119-122` avisa disso. **A distribuição de produção não foi reconferida** (o acesso ao banco de produção é uma das decisões pendentes, `ESTADO-ATUAL.md:42`). O que a tabela acima prova com segurança é **quais valores o código produz**, não em que proporção eles aparecem na Veks.

**Nas opções oferecidas ao usuário** (o que pode existir em produção mesmo sem existir aqui):

| Valor | Onde é oferecido | Vivo? |
|---|---|---|
| `Em Andamento` | `services/dropdown_service.py:94`, `forms.py:42`, `templates/obra_form.html:322` | sim |
| `Em andamento` | `templates/obras_moderno.html:616` | sim (filtro vivo) |
| `Concluída` | `dropdown_service.py:94`, `obras_moderno.html:617`, `obra_form.html:322` | sim |
| `Pausada` | `dropdown_service.py:94`, `obras_moderno.html:618`, `obra_form.html:322` | sim |
| `Cancelada` | `dropdown_service.py:94`, `obra_form.html:322` | sim (não filtrável) |
| `Planejamento` | `templates/obras_moderno.html:619` | sim (filtro), mas **nada grava esse valor** |
| `ATIVO`, `andamento`, `ativa`, `planejamento` | `views/dashboard.py:428,1013,1035,1054` | **mortos** — 0 linhas no banco |
| `Em Andamento`, `Planejamento`, `Concluída`, `Pausada`, `Cancelada` | `templates/obras.html:47-85`, `templates/obras_safe.html:38-75` | `obras.html` é órfão; `obras_safe.html` só em `production_routes.py:239` |

O grupo `obra_status` é editável pelo tenant (`services/dropdown_service.py:56`), então **valores customizados podem existir em produção**. No banco de desenvolvimento a tabela `dropdown_grupo` está vazia, então `get_opcoes_valores` cai no fallback `_SLUG_DEFAULTS` (`services/dropdown_service.py:208-221`). A migração de backfill trata qualquer valor desconhecido por regra explícita, nunca por erro.

**Bug encontrado no censo:** `templates/obra_form.html:322` oferece `Em Andamento`, o filtro vivo em `templates/obras_moderno.html:616` procura `Em andamento`, e `views/obras.py:83` compara por igualdade exata. As 53 obras salvas pelo formulário **não aparecem** ao filtrar por "Em Andamento" na listagem. A Task 6 resolve isso ao normalizar o campo legado.

### Correção ao `ESTADO-ATUAL.md`

`ESTADO-ATUAL.md:70-78` afirma que "o cronograma nasce preso à proposta… exige serviço → composição → insumo". Isso está **desatualizado**: `cronograma_views.py:365-397` (Task #116) tornou `servico_id` opcional na criação de tarefa, com fallback por nome e `logger.info("[cronograma] Tarefa criada sem vínculo de serviço (servico_id=None é permitido)")` em `cronograma_views.py:397`. Não afeta esta fase, mas confirma o aviso: trate o `ESTADO-ATUAL.md` como pista.

---

## Decisões de projeto desta fase

Cada decisão de negócio abaixo é uma **recomendação fundamentada** no vocabulário que o código já usa. O plano segue com ela adotada; a lista consolidada para o Cássio está no fim do documento.

### 1. Cinco estados, não onze

`DEVOLUTIVA.md:82` diz que a spec pede uma máquina de 11 estados e cita `vendida` e `em_execução`. Onze estados sem verbo que os consuma seriam onze rótulos.

**Recomendado:** cinco estados, cada um ancorado num valor que o código já produz ou já oferece:

| Estado | `.value` | Rótulo (= `Obra.status` legado) | Origem no código |
|---|---|---|---|
| `PLANEJAMENTO` | `planejamento` | `Planejamento` | opção viva do filtro em `templates/obras_moderno.html:619`; é o estado que hoje se expressa como `cronograma_revisado_em IS NULL` |
| `EM_EXECUCAO` | `em_execucao` | `Em andamento` | 7 958 linhas no banco; default de `models.py:257` |
| `PAUSADA` | `pausada` | `Pausada` | `dropdown_service.py:94`, `obras_moderno.html:618` |
| `CONCLUIDA` | `concluida` | `Concluída` | 13 linhas; `emit_obra_concluida` (`utils/catalogo_eventos.py:289`) |
| `CANCELADA` | `cancelada` | `Cancelada` | `dropdown_service.py:94`, `obra_form.html:322` |

`vendida` não vira estado da Obra: a venda é estado da **Proposta** (`proposta.status = 'APROVADA'`, `event_manager.py:1051`), e a Obra só existe porque a proposta foi vendida. Duplicar isso criaria duas fontes de verdade para o mesmo fato.

### 2. Coluna nova, coluna velha derivada

**Recomendado:** `Obra.estado` é a fonte de verdade; `Obra.status` vira **espelho** escrito por write-through, e `Obra.ativo` também. É a proposta do `DEVOLUTIVA.md:88` (conflito #1), e é o que torna a fase aditiva: as ~40 leituras de `status` e as ~20 de `ativo` continuam corretas sem uma linha alterada.

`ativo` deriva assim: `False` para `CONCLUIDA` e `CANCELADA`, `True` para os demais. Isso reproduz exatamente o que a UI já diz — `templates/obras_moderno.html:803` chama a lista de inativas de "Obras Concluídas / Inativas".

### 3. `VARCHAR` + `CHECK`, não `ENUM` nativo do Postgres

`UsuarioObra.papel` (Fase 1) usa `db.Enum(PapelObra)`. Aqui **não**: acrescentar valor a um tipo ENUM do Postgres exige `ALTER TYPE ... ADD VALUE`, que em versões anteriores à 12 não roda dentro de bloco transacional — e as migrações deste repo rodam dentro de uma sessão SQLAlchemy que commita ao fim (`migrations.py:170-179`). `VARCHAR(20)` + `CHECK` dá a mesma garantia e o `CHECK` é dropável e recriável numa migração comum.

### 4. Toda obra nasce em `PLANEJAMENTO`

Hoje toda obra nasce `'Em andamento'` — pela cascata (`event_manager.py:1018`) ou pelo formulário (`views/obras.py:279`). O ponto da fase é que **não existe obra em execução sem GP**.

**Recomendado:** nascer em `PLANEJAMENTO` sempre. Para não piorar a ergonomia de quem cria obra à mão, `nova_obra` executa o handoff na mesma transação **quando o formulário já traz `responsavel_id`** — o usuário não percebe diferença, mas o histórico registra a transição e o `UsuarioObra` é criado.

### 5. Quem pode fazer cada transição

Fase 1 entrega dois eixos: `TipoUsuario` (tenant) e `PapelObra` (obra). O eixo de obra só existe para quem tem linha em `usuario_obra`; `ADMIN`/`SUPER_ADMIN` são `GESTOR` implícito de tudo (`utils/autorizacao.papel_na_obra`).

**Recomendado:**

| Transição | Autoridade | Motivo obrigatório? | Por quê |
|---|---|---|---|
| `PLANEJAMENTO → EM_EXECUCAO` | `admin` | não | é o handoff: quem entrega a obra é a diretoria, não o próprio GP |
| `PLANEJAMENTO → CANCELADA` | `admin` | **sim** | distrato antes de começar precisa de rastro |
| `EM_EXECUCAO → PAUSADA` | `gestor` | **sim** | paralisação é do dia a dia da obra; o GP decide, mas registra a causa |
| `PAUSADA → EM_EXECUCAO` | `gestor` | não | retomar é desfazer, não precisa de justificativa nova |
| `EM_EXECUCAO → CONCLUIDA` | `gestor` | não | o GP entrega a obra |
| `EM_EXECUCAO → CANCELADA` | `admin` | **sim** | cancelar obra em execução é decisão comercial |
| `PAUSADA → CANCELADA` | `admin` | **sim** | idem |
| `CONCLUIDA → EM_EXECUCAO` | `admin` | **sim** | reabertura é excepcional; sem motivo vira desfazer acidental |

`CANCELADA` é terminal. Não há saída — cancelar é o fim da linha, e reviver uma obra cancelada deve ser obra nova, com proposta nova.

### 6. O handoff exige um GP **logável**

`Obra.responsavel_id` aponta para `Funcionario`, que antes da Fase 1 não tinha login. Depois da Fase 1 existe `Usuario.funcionario_id` e `utils.identidade.usuario_do_funcionario()`.

**Recomendado:** `executar_handoff` recusa `Funcionario` sem `Usuario`. Sem login não há a quem dar o `UsuarioObra` com papel `GESTOR`, e um handoff que não cria vínculo é só um campo preenchido — exatamente o que temos hoje.

### 7. O gate de cronograma é absorvido, não duplicado

`Obra.cronograma_revisado_em` continua sendo a coluna, mas deixa de ser um estado solto:

- Se há cronograma pendente de revisão (`views.obras._precisa_revisao_cronograma_inicial` retorna `True`), o handoff é **recusado** — é literalmente o critério do `DEVOLUTIVA.md:225` ("obra não entra em `em_execução` sem registro de aceite").
- Se não há nada a revisar e o carimbo está `NULL` (caso das obras criadas à mão, que nunca disparam o gate), o handoff **carimba** e registra isso em `detalhes` da transição.

Assim o gate ganha o *quem* que `DEVOLUTIVA.md:129` aponta como faltante — sem coluna nova, via a linha de histórico.

---

## Arquivos que esta fase cria ou altera

| Arquivo | Responsabilidade |
|---|---|
| `services/obra_estado.py` | **novo** — o grafo, os rótulos, `transitar()`, autorização por transição. Único escritor de `Obra.estado` |
| `services/obra_handoff.py` | **novo** — `executar_handoff()` e `dossie_handoff()` |
| `scripts/relatorio_estado_obra.py` | **novo** — censo/dry-run antes de migrar e depois de migrar |
| `models.py` | enum `EstadoObra`, coluna `Obra.estado`, modelo `ObraTransicaoEstado`, relationship `Obra.transicoes` |
| `migrations.py` | migrations 230, 231, 232 + registro em `migrations_to_run` |
| `event_manager.py` | obra nasce em `PLANEJAMENTO` com linha de histórico (dentro do handler existente) |
| `views/obras.py` | rotas `POST /obras/<id>/estado` e `/obras/<id>/handoff`; filtro por estado; `nova_obra`/`editar_obra`/`toggle_*` passam pela máquina |
| `utils/catalogo_eventos.py` | `emit_obra_estado_alterado`, `emit_obra_handoff` |
| `utils/webhook_dispatcher.py` | dois eventos novos na allowlist |
| `templates/obras/_estado_obra.html` | **novo** — badge + painel de transição + handoff |
| `templates/obras/detalhes_obra_profissional.html` | inclui o partial |
| `templates/obra_form.html` | o select de status vira badge somente-leitura |
| `tests/test_fase2_maquina_estados_obra.py` | **novo** |
| `tests/test_fase2_handoff_gp.py` | **novo** |
| `docs/fase-2-rollout.md` | **novo** — runbook e rollback |

---

## Task 1: Enum `EstadoObra` e o grafo de transições

Lógica pura, sem banco. Fixa o vocabulário antes de qualquer DDL.

**Files:**
- Modify: `models.py:20` (logo após `class TipoUsuario`)
- Create: `services/obra_estado.py`
- Test: `tests/test_fase2_maquina_estados_obra.py`

- [ ] **Step 1: Escreva o teste que falha**

Crie `tests/test_fase2_maquina_estados_obra.py`:

```python
"""Fase 2 — máquina de estados da Obra.

Antes desta fase `Obra.status` era `db.Column(db.String(20),
default='Em andamento')` (models.py:257): texto livre, alimentado por um
dropdown editável pelo tenant, sem transição validada e sem histórico.
O censo de 2026-07-21 achou três grafias para dois conceitos
('Em andamento' 7918, 'Em Andamento' 53, 'Concluída' 13) e um filtro
que nunca casava com metade delas (views/obras.py:83 compara igualdade
exata contra o valor de templates/obras_moderno.html:616).

Estes testes travam o vocabulário fechado e o grafo.
"""
import os
import sys

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import main  # noqa: F401 — registra os blueprints
from app import app, db  # noqa: F401

pytestmark = pytest.mark.integration


def test_enum_tem_exatamente_os_cinco_estados():
    from models import EstadoObra
    assert {e.value for e in EstadoObra} == {
        'planejamento', 'em_execucao', 'pausada', 'concluida', 'cancelada',
    }


def test_rotulo_de_cada_estado_e_o_texto_legado():
    """Os rótulos precisam ser exatamente o que `Obra.status` já grava —
    é o que permite manter as ~40 leituras de status funcionando."""
    from models import EstadoObra
    from services.obra_estado import ROTULOS
    assert ROTULOS[EstadoObra.EM_EXECUCAO] == 'Em andamento'
    assert ROTULOS[EstadoObra.CONCLUIDA] == 'Concluída'
    assert ROTULOS[EstadoObra.PAUSADA] == 'Pausada'
    assert ROTULOS[EstadoObra.CANCELADA] == 'Cancelada'
    assert ROTULOS[EstadoObra.PLANEJAMENTO] == 'Planejamento'
    assert set(ROTULOS) == set(EstadoObra)


def test_grafo_cobre_todos_os_estados():
    from models import EstadoObra
    from services.obra_estado import TRANSICOES
    assert set(TRANSICOES) == set(EstadoObra)


def test_cancelada_e_terminal():
    from models import EstadoObra
    from services.obra_estado import transicoes_possiveis
    assert transicoes_possiveis(EstadoObra.CANCELADA) == ()


def test_planejamento_so_vai_para_execucao_ou_cancelada():
    from models import EstadoObra
    from services.obra_estado import transicoes_possiveis
    assert set(transicoes_possiveis(EstadoObra.PLANEJAMENTO)) == {
        EstadoObra.EM_EXECUCAO, EstadoObra.CANCELADA,
    }


def test_pode_transitar_recusa_salto_invalido():
    from models import EstadoObra
    from services.obra_estado import pode_transitar
    # Pular o handoff: planejamento não conclui obra.
    assert pode_transitar(EstadoObra.PLANEJAMENTO, EstadoObra.CONCLUIDA) is False
    assert pode_transitar(EstadoObra.PLANEJAMENTO, EstadoObra.PAUSADA) is False
    assert pode_transitar(EstadoObra.CANCELADA, EstadoObra.EM_EXECUCAO) is False
    assert pode_transitar(EstadoObra.EM_EXECUCAO, EstadoObra.CONCLUIDA) is True


def test_nenhuma_transicao_aponta_para_o_proprio_estado():
    from services.obra_estado import TRANSICOES
    for origem, destinos in TRANSICOES.items():
        assert origem not in destinos, f'{origem} transita para si mesma'


def test_coagir_aceita_str_value_nome_e_enum():
    from models import EstadoObra
    from services.obra_estado import coagir
    assert coagir('em_execucao') is EstadoObra.EM_EXECUCAO
    assert coagir('EM_EXECUCAO') is EstadoObra.EM_EXECUCAO
    assert coagir(EstadoObra.EM_EXECUCAO) is EstadoObra.EM_EXECUCAO


def test_coagir_recusa_lixo():
    from services.obra_estado import EstadoDesconhecido, coagir
    with pytest.raises(EstadoDesconhecido):
        coagir('em execução')
    with pytest.raises(EstadoDesconhecido):
        coagir(None)


def test_estado_do_status_legado_mapeia_as_tres_grafias_do_censo():
    """As três grafias achadas no banco em 2026-07-21 caem no lugar certo."""
    from models import EstadoObra
    from services.obra_estado import estado_do_status_legado
    assert estado_do_status_legado('Em andamento') is EstadoObra.EM_EXECUCAO
    assert estado_do_status_legado('Em Andamento') is EstadoObra.EM_EXECUCAO
    assert estado_do_status_legado('Concluída') is EstadoObra.CONCLUIDA
    # Sem acento e em caixa alta — grafias plausíveis num tenant customizado.
    assert estado_do_status_legado('CONCLUIDA') is EstadoObra.CONCLUIDA
    assert estado_do_status_legado('pausado') is EstadoObra.PAUSADA
    assert estado_do_status_legado('Planejamento') is EstadoObra.PLANEJAMENTO
    # Valor customizado desconhecido não explode: cai em None, e quem chama decide.
    assert estado_do_status_legado('Aguardando ART') is None
    assert estado_do_status_legado(None) is None
```

- [ ] **Step 2: Rode e veja falhar**

```bash
python -m pytest tests/test_fase2_maquina_estados_obra.py -v 2>&1 | tail -20
```

Esperado: FAIL na coleção — `ImportError: cannot import name 'EstadoObra' from 'models'`.

- [ ] **Step 3: Acrescente o enum em `models.py`**

Em `models.py`, logo depois do fim de `class TipoUsuario` (que termina em `models.py:26`) e antes de `class Usuario` (`models.py:28`), insira:

```python
class EstadoObra(Enum):
    """Estados da Obra — Fase 2.

    Antes desta fase o estado da obra era `Obra.status`, um
    `db.Column(db.String(20), default='Em andamento')` de texto livre
    alimentado por um dropdown editável pelo tenant
    (`services/dropdown_service.py:94`). O censo de 2026-07-21 encontrou
    três grafias para dois conceitos ('Em andamento', 'Em Andamento',
    'Concluída') e um segundo eixo paralelo, `Obra.ativo`, que a UI
    chama de "Concluída / Inativa" (templates/obras_moderno.html:803)
    sem nunca sincronizar com `status`.

    Os cinco valores abaixo são exatamente os que o código já produz ou
    já oferece ao usuário — nenhum foi inventado. O rótulo humano de
    cada um vive em `services.obra_estado.ROTULOS` e é o texto gravado
    no campo legado `Obra.status`, que passa a ser derivado.

    Gravado como VARCHAR(20) + CHECK, não como ENUM nativo do Postgres:
    acrescentar valor a um tipo ENUM exige ALTER TYPE, que não roda
    dentro do bloco transacional em que `run_migration_safe`
    (migrations.py:146) executa as migrações deste repo.
    """
    PLANEJAMENTO = "planejamento"   # obra existe, sem GP, cronograma não aceito
    EM_EXECUCAO = "em_execucao"     # handoff feito; é o 'Em andamento' de hoje
    PAUSADA = "pausada"             # paralisada, com motivo registrado
    CONCLUIDA = "concluida"         # entregue; equivale ao ativo=False de hoje
    CANCELADA = "cancelada"         # terminal: distrato/desistência
```

- [ ] **Step 4: Crie `services/obra_estado.py`**

```python
"""Máquina de estados da Obra — Fase 2.

Este módulo é o **único** lugar autorizado a escrever `Obra.estado`.
Antes dele, quatro pontos escreviam `Obra.status` livremente:
`models.py:257` (default), `event_manager.py:1018` (cascata da
proposta), `views/obras.py:279`/`393` (criação) e `views/obras.py:863`
(edição) — nenhum validava nada, e a única "transição" existente era
uma comparação de string normalizada, feita DEPOIS do commit, só para
disparar webhook (`views/obras.py:963-979`).

O molde é `CronogramaImportacao` (`models.py:5018-5021`), o único state
machine real do sistema, com sua trilha em `CronogramaImportacaoEvento`
(`models.py:5178`) e o log estruturado de `log_transicao`
(`services/cronograma_observabilidade.py:34`). Repetimos a forma: grafo
explícito, transição que grava evento, log que nunca derruba o fluxo.

Nada aqui commita. Quem chama é dono da transação — mesmo contrato dos
handlers de evento (`event_manager.py:882-887`).
"""
from __future__ import annotations

import logging
import unicodedata

from models import EstadoObra

logger = logging.getLogger('obra.estado')


class EstadoDesconhecido(ValueError):
    """Texto que não corresponde a nenhum `EstadoObra`."""


class TransicaoInvalida(ValueError):
    """Transição recusada pelo grafo, pela autorização ou por falta de motivo."""


# ── O grafo ──────────────────────────────────────────────────────────
# Ler como "de → destinos permitidos". CANCELADA é terminal de
# propósito: reviver obra cancelada é obra nova, com proposta nova.
TRANSICOES: dict[EstadoObra, tuple[EstadoObra, ...]] = {
    EstadoObra.PLANEJAMENTO: (EstadoObra.EM_EXECUCAO, EstadoObra.CANCELADA),
    EstadoObra.EM_EXECUCAO: (EstadoObra.PAUSADA, EstadoObra.CONCLUIDA,
                             EstadoObra.CANCELADA),
    EstadoObra.PAUSADA: (EstadoObra.EM_EXECUCAO, EstadoObra.CANCELADA),
    EstadoObra.CONCLUIDA: (EstadoObra.EM_EXECUCAO,),
    EstadoObra.CANCELADA: (),
}

# Rótulo humano — é TAMBÉM o valor gravado no campo legado `Obra.status`
# por write-through. Mudar um destes textos muda o que ~40 templates e
# queries leem; ver o censo em docs/superpowers/plans/2026-07-21-fase-2.
ROTULOS: dict[EstadoObra, str] = {
    EstadoObra.PLANEJAMENTO: 'Planejamento',
    EstadoObra.EM_EXECUCAO: 'Em andamento',
    EstadoObra.PAUSADA: 'Pausada',
    EstadoObra.CONCLUIDA: 'Concluída',
    EstadoObra.CANCELADA: 'Cancelada',
}

# `Obra.ativo` deixa de ser eixo independente e passa a derivar daqui.
# A UI já trata ativo=False como "Concluída / Inativa"
# (templates/obras_moderno.html:803,819) — isto só torna explícito.
ESTADOS_INATIVOS: frozenset[EstadoObra] = frozenset(
    {EstadoObra.CONCLUIDA, EstadoObra.CANCELADA})

# Transições que exigem motivo escrito. Critério: toda transição que
# CONTRARIA a expectativa (paralisar, cancelar, reabrir) precisa de
# rastro; as que a confirmam (entregar, retomar) não.
TRANSICOES_QUE_EXIGEM_MOTIVO: frozenset[tuple[EstadoObra, EstadoObra]] = frozenset({
    (EstadoObra.PLANEJAMENTO, EstadoObra.CANCELADA),
    (EstadoObra.EM_EXECUCAO, EstadoObra.PAUSADA),
    (EstadoObra.EM_EXECUCAO, EstadoObra.CANCELADA),
    (EstadoObra.PAUSADA, EstadoObra.CANCELADA),
    (EstadoObra.CONCLUIDA, EstadoObra.EM_EXECUCAO),
})

# Autoridade mínima por transição.
#   'admin'  → apenas TipoUsuario.ADMIN / SUPER_ADMIN do tenant
#   'gestor' → o acima, OU quem tem UsuarioObra(papel=GESTOR) nesta obra
AUTORIDADE: dict[tuple[EstadoObra, EstadoObra], str] = {
    (EstadoObra.PLANEJAMENTO, EstadoObra.EM_EXECUCAO): 'admin',
    (EstadoObra.PLANEJAMENTO, EstadoObra.CANCELADA): 'admin',
    (EstadoObra.EM_EXECUCAO, EstadoObra.PAUSADA): 'gestor',
    (EstadoObra.EM_EXECUCAO, EstadoObra.CONCLUIDA): 'gestor',
    (EstadoObra.EM_EXECUCAO, EstadoObra.CANCELADA): 'admin',
    (EstadoObra.PAUSADA, EstadoObra.EM_EXECUCAO): 'gestor',
    (EstadoObra.PAUSADA, EstadoObra.CANCELADA): 'admin',
    (EstadoObra.CONCLUIDA, EstadoObra.EM_EXECUCAO): 'admin',
}


def _sem_acento(texto: str) -> str:
    """'Concluída' → 'concluida'. Mesma técnica de views/obras.py:969-973."""
    texto = (texto or '').strip().lower()
    return ''.join(c for c in unicodedata.normalize('NFKD', texto)
                   if not unicodedata.combining(c))


# Mapa do texto legado → estado. Chaves já normalizadas por `_sem_acento`.
# Cobre as três grafias achadas no banco em 2026-07-21 e as variantes
# plausíveis de um tenant que editou o dropdown obra_status.
_MAPA_LEGADO: dict[str, EstadoObra] = {
    'planejamento': EstadoObra.PLANEJAMENTO,
    'planejada': EstadoObra.PLANEJAMENTO,
    'planejado': EstadoObra.PLANEJAMENTO,
    'em andamento': EstadoObra.EM_EXECUCAO,
    'andamento': EstadoObra.EM_EXECUCAO,
    'em execucao': EstadoObra.EM_EXECUCAO,
    'em_execucao': EstadoObra.EM_EXECUCAO,
    'execucao': EstadoObra.EM_EXECUCAO,
    'ativo': EstadoObra.EM_EXECUCAO,
    'ativa': EstadoObra.EM_EXECUCAO,
    'pausada': EstadoObra.PAUSADA,
    'pausado': EstadoObra.PAUSADA,
    'paralisada': EstadoObra.PAUSADA,
    'paralisado': EstadoObra.PAUSADA,
    'concluida': EstadoObra.CONCLUIDA,
    'concluido': EstadoObra.CONCLUIDA,
    'finalizada': EstadoObra.CONCLUIDA,
    'finalizado': EstadoObra.CONCLUIDA,
    'entregue': EstadoObra.CONCLUIDA,
    'cancelada': EstadoObra.CANCELADA,
    'cancelado': EstadoObra.CANCELADA,
    'distratada': EstadoObra.CANCELADA,
}


def coagir(valor) -> EstadoObra:
    """Aceita `EstadoObra`, o `.value` ('em_execucao') ou o nome
    ('EM_EXECUCAO'). Levanta `EstadoDesconhecido` para o resto.

    Deliberadamente estrito: NÃO aceita rótulo humano ('Em andamento').
    Rótulo é saída, não entrada — quem tem texto legado usa
    `estado_do_status_legado`, que devolve None em vez de levantar.
    """
    if isinstance(valor, EstadoObra):
        return valor
    if isinstance(valor, str):
        bruto = valor.strip()
        for membro in EstadoObra:
            if bruto == membro.value or bruto.upper() == membro.name:
                return membro
    raise EstadoDesconhecido(f'estado desconhecido: {valor!r}')


def estado_do_status_legado(status: str | None) -> EstadoObra | None:
    """Traduz o texto livre de `Obra.status` em estado, ou None.

    None significa "valor customizado que o mapa não conhece" — quem
    chama decide (a migration 231 cai numa regra de derivação por
    `Obra.ativo`; o relatório de censo lista para revisão humana).
    """
    if not status:
        return None
    return _MAPA_LEGADO.get(_sem_acento(status))


def transicoes_possiveis(estado) -> tuple[EstadoObra, ...]:
    """Destinos permitidos a partir de `estado` (aceita str ou enum)."""
    return TRANSICOES.get(coagir(estado), ())


def pode_transitar(de, para) -> bool:
    """Só o grafo. Autorização e motivo são checados em `transitar`."""
    try:
        return coagir(para) in transicoes_possiveis(de)
    except EstadoDesconhecido:
        return False


def exige_motivo(de, para) -> bool:
    return (coagir(de), coagir(para)) in TRANSICOES_QUE_EXIGEM_MOTIVO


def autoridade_necessaria(de, para) -> str:
    """'admin' ou 'gestor'. Transição fora do grafo é tratada como 'admin'."""
    return AUTORIDADE.get((coagir(de), coagir(para)), 'admin')
```

- [ ] **Step 5: Rode os testes**

```bash
python -m pytest tests/test_fase2_maquina_estados_obra.py -v 2>&1 | tail -20
```

Esperado: os 10 testes PASSAM.

- [ ] **Step 6: Commit**

```bash
git add models.py services/obra_estado.py tests/test_fase2_maquina_estados_obra.py
git commit -m "feat(fase2): enum EstadoObra e o grafo de transicoes da obra

Cinco estados ancorados no vocabulario que o codigo ja produz (censo de
2026-07-21: 'Em andamento' 7918, 'Em Andamento' 53, 'Concluida' 13).
CANCELADA e terminal. services/obra_estado.py passa a ser o unico lugar
que conhece o grafo; nada aqui toca o banco ainda."
```

---

## Task 2: Tabela de histórico `ObraTransicaoEstado` + migration 230

**Files:**
- Modify: `models.py` (após o fim de `class Obra`, antes de `class ServicoObra` em `models.py:332`)
- Modify: `migrations.py` (nova função antes de `def executar_migracoes():` em `migrations.py:3773`; registro na lista após `migrations.py:4014`)
- Test: `tests/test_fase2_maquina_estados_obra.py`

- [ ] **Step 1: Escreva o teste que falha**

Acrescente ao fim de `tests/test_fase2_maquina_estados_obra.py`:

```python
# ---------------------------------------------------------------------------
# Fixtures de banco. `Obra.cliente_id` é NOT NULL (models.py:265-268), então
# todo cenário cria Cliente antes. `Funcionario.cpf` é UNIQUE global
# (models.py:189), por isso o sufixo aleatório.
# ---------------------------------------------------------------------------
import uuid
from datetime import date

from werkzeug.security import generate_password_hash


@pytest.fixture(autouse=True)
def _config():
    app.config['TESTING'] = True
    app.config['WTF_CSRF_ENABLED'] = False
    if not app.secret_key:
        app.secret_key = 'test-fase2-estados'
    yield


def _admin(prefixo='f2a'):
    from models import TipoUsuario, Usuario
    suf = uuid.uuid4().hex[:8]
    u = Usuario(
        username=f'{prefixo}_{suf}', email=f'{prefixo}_{suf}@test.local',
        nome=f'Admin {suf}',
        password_hash=generate_password_hash('Senha@2026'),
        tipo_usuario=TipoUsuario.ADMIN, ativo=True, versao_sistema='v2',
    )
    db.session.add(u)
    db.session.commit()
    return u


def _obra(admin, estado=None, status='Planejamento', ativo=True):
    """CORREÇÃO 22/07 (achado E): `estado` é opcional e só é aplicado quando
    passado explicitamente.

    A versão original tinha `estado='planejamento'` como default, o que fazia
    os testes da Task 2 dependerem de uma coluna que só nasce na Task 3 — o
    Step 6 da Task 2 admitia isso ("os testes ainda não passarão se
    `Obra.estado` não existir") e o Step 7 mandava commitar mesmo assim. Com
    o default None, a Task 2 é verificável sozinha e a Task 3 passa o estado
    quando precisa dele.
    """
    from models import Cliente, Obra
    suf = uuid.uuid4().hex[:8]
    cli = Cliente(nome=f'Cliente {suf}', admin_id=admin.id)
    db.session.add(cli)
    db.session.flush()
    kwargs = {}
    if estado is not None:
        kwargs['estado'] = estado
    o = Obra(
        nome=f'Obra {suf}', codigo=f'F2{suf[:6].upper()}',
        cliente_id=cli.id, data_inicio=date(2026, 7, 1),
        status=status, ativo=ativo, admin_id=admin.id, **kwargs,
    )
    db.session.add(o)
    db.session.commit()
    return o


def test_tabela_de_historico_existe_e_grava():
    from models import ObraTransicaoEstado
    with app.app_context():
        admin = _admin()
        obra = _obra(admin)
        reg = ObraTransicaoEstado(
            obra_id=obra.id, admin_id=admin.id,
            estado_de='planejamento', estado_para='em_execucao',
            motivo='teste', detalhes={'origem': 'pytest'},
            usuario_id=admin.id,
        )
        db.session.add(reg)
        db.session.commit()
        lido = db.session.get(ObraTransicaoEstado, reg.id)
        assert lido.estado_de == 'planejamento'
        assert lido.estado_para == 'em_execucao'
        assert lido.detalhes == {'origem': 'pytest'}
        assert lido.usuario_id == admin.id
        assert lido.criado_em is not None


def test_historico_e_acessivel_pela_obra_em_ordem_cronologica():
    from models import ObraTransicaoEstado
    with app.app_context():
        admin = _admin()
        obra = _obra(admin)
        for de, para in (('planejamento', 'em_execucao'),
                         ('em_execucao', 'pausada')):
            db.session.add(ObraTransicaoEstado(
                obra_id=obra.id, admin_id=admin.id,
                estado_de=de, estado_para=para, usuario_id=admin.id))
        db.session.commit()
        db.session.refresh(obra)
        assert [t.estado_para for t in obra.transicoes] == [
            'em_execucao', 'pausada']
```

- [ ] **Step 2: Rode e veja falhar**

```bash
python -m pytest tests/test_fase2_maquina_estados_obra.py -k "historico or tabela" -v 2>&1 | tail -20
```

Esperado: FAIL — `ImportError: cannot import name 'ObraTransicaoEstado' from 'models'`.

- [ ] **Step 3: Acrescente o modelo em `models.py`**

Em `models.py`, depois do fim de `class Obra` (a última linha é a property `cliente_telefone_efetivo`, em `models.py:330`) e antes de `class ServicoObra` (`models.py:332`), insira:

```python
class ObraTransicaoEstado(db.Model):
    """Histórico de transições de estado da Obra — Fase 2.

    Molde: `CronogramaImportacaoEvento` (models.py:5178), a única trilha
    de auditoria de máquina de estados que já existia no sistema. Mesma
    forma: FK para o agregado, tenant desnormalizado, `detalhes` em JSON
    livre, `usuario_id` nullable (transição feita por migração ou por
    automação não tem usuário).

    `estado_de` é NULL apenas na linha de backfill escrita pela
    migration 231, que registra o estado inicial derivado do texto
    legado. Essa linha carrega, no `motivo`, o valor VERBATIM de
    `Obra.status` e de `Obra.ativo` antes da migração — é o que torna a
    migration 232 (normalização do texto legado) reversível a partir do
    próprio banco.
    """
    __tablename__ = 'obra_transicao_estado'
    __table_args__ = (
        db.Index('ix_obra_transicao_obra_criado', 'obra_id', 'criado_em'),
    )

    id = db.Column(db.Integer, primary_key=True)
    obra_id = db.Column(
        db.Integer, db.ForeignKey('obra.id', ondelete='CASCADE'),
        nullable=False, index=True,
    )
    admin_id = db.Column(
        db.Integer, db.ForeignKey('usuario.id'), nullable=False, index=True,
    )
    # Guardamos o `.value` do EstadoObra, não o Enum: a coluna precisa ser
    # legível por SQL cru nas migrações e nos relatórios de censo.
    estado_de = db.Column(db.String(20), nullable=True)
    estado_para = db.Column(db.String(20), nullable=False)
    motivo = db.Column(db.Text, nullable=True)
    detalhes = db.Column(db.JSON, nullable=True)
    usuario_id = db.Column(
        db.Integer, db.ForeignKey('usuario.id'), nullable=True,
    )
    criado_em = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)

    obra = db.relationship(
        'Obra', foreign_keys=[obra_id],
        backref=db.backref('transicoes', lazy='select',
                           order_by='ObraTransicaoEstado.criado_em',
                           cascade='all, delete-orphan'),
    )

    def __repr__(self):
        return (f'<ObraTransicaoEstado obra={self.obra_id} '
                f'{self.estado_de}→{self.estado_para}>')
```

- [ ] **Step 4: Escreva a migration 230**

Em `migrations.py`, imediatamente antes de `def executar_migracoes():` (`migrations.py:3773`), insira:

```python
def migration_230_obra_transicao_estado():
    """Fase 2 — tabela `obra_transicao_estado` (histórico de transições).

    ATENÇÃO: `db.create_all()` roda ANTES das migrações (app.py:582 vs
    app.py:667), então numa base onde o modelo já foi importado a tabela
    já existe e o `CREATE TABLE IF NOT EXISTS` abaixo é no-op. Isso é
    esperado — a prova de que acontece está na migration 207, que declara
    `json_bruto JSONB` (migrations.py:13903) sobre uma coluna que o
    Postgres reporta como `json`, porque quem a criou foi o create_all.

    Por isso cada índice é criado separadamente e de forma idempotente,
    em vez de embutido no CREATE TABLE: os índices declarados só no DDL
    da migração nunca nasceriam. É a mesma lição da migration 213.

    Idempotente: seguro re-executar.
    """
    try:
        db.session.execute(text("""
            CREATE TABLE IF NOT EXISTS obra_transicao_estado (
                id SERIAL PRIMARY KEY,
                obra_id INTEGER NOT NULL REFERENCES obra(id) ON DELETE CASCADE,
                admin_id INTEGER NOT NULL REFERENCES usuario(id),
                estado_de VARCHAR(20) NULL,
                estado_para VARCHAR(20) NOT NULL,
                motivo TEXT NULL,
                detalhes JSON NULL,
                usuario_id INTEGER NULL REFERENCES usuario(id),
                criado_em TIMESTAMP NOT NULL DEFAULT NOW()
            )
        """))

        db.session.execute(text("""
            CREATE INDEX IF NOT EXISTS ix_obra_transicao_estado_obra_id
                ON obra_transicao_estado (obra_id)
        """))
        db.session.execute(text("""
            CREATE INDEX IF NOT EXISTS ix_obra_transicao_estado_admin_id
                ON obra_transicao_estado (admin_id)
        """))
        # Índice do caso de uso quente: "linha do tempo desta obra".
        db.session.execute(text("""
            CREATE INDEX IF NOT EXISTS ix_obra_transicao_obra_criado
                ON obra_transicao_estado (obra_id, criado_em)
        """))

        db.session.commit()
        logger.info(
            "MIGRACAO 230 CONCLUIDA: tabela obra_transicao_estado "
            "verificada + 3 indices garantidos"
        )
    except Exception as e:
        db.session.rollback()
        logger.error(f"[Migration 230] Erro: {e}")
        raise
```

- [ ] **Step 5: Registre a migration**

Em `migrations.py`, dentro de `executar_migracoes()`, na lista `migrations_to_run`, logo depois da linha 4014 (`(213, "Fase 0.5 — índices que nunca nasceram ...")`) e antes do `]` de fechamento, acrescente:

```python
            (230, "Fase 2 — tabela obra_transicao_estado (historico de transicoes: de/para/quem/quando/motivo)", migration_230_obra_transicao_estado),
```

> Se a Fase 1 já subiu, as linhas 214/215/216 estarão nesta lista. Insira a 230 **depois** delas — a lista é executada na ordem em que está escrita.

- [ ] **Step 6: Rode a migração e os testes**

```bash
python -c "
from app import app
with app.app_context():
    from migrations import migration_230_obra_transicao_estado as m
    m()
" 2>&1 | tail -5
python -m pytest tests/test_fase2_maquina_estados_obra.py -k "historico or tabela" -v 2>&1 | tail -20
```

Esperado: log `MIGRACAO 230 CONCLUIDA` e os 2 testes PASSAM. (Os testes ainda não passarão se `Obra.estado` não existir — a fixture `_obra` já usa `estado=`; nesse caso siga para a Task 3 e rode os dois juntos ao fim dela.)

- [ ] **Step 7: Commit**

```bash
git add models.py migrations.py tests/test_fase2_maquina_estados_obra.py
git commit -m "feat(fase2): tabela obra_transicao_estado + migration 230

Historico de quem mudou o que, quando e por que. Molde:
CronogramaImportacaoEvento (models.py:5178). Indices criados fora do
CREATE TABLE porque create_all roda antes das migracoes (app.py:582 vs
667) e o CREATE TABLE IF NOT EXISTS vira no-op."
```

---

## Task 3: Coluna `Obra.estado` + migration 231 (backfill dos dados reais)

Esta é a migração que roda sobre as obras de produção. Ela cria a coluna, deriva o estado de cada obra existente, grava a linha de histórico com o valor legado verbatim, e só então aplica `NOT NULL` e `CHECK`. Tudo numa migração só, para que não exista janela em que uma obra esteja com estado errado.

**Files:**
- Modify: `models.py` (dentro de `class Obra`, logo após `status` em `models.py:257`)
- Modify: `migrations.py` (nova função + registro)
- Test: `tests/test_fase2_maquina_estados_obra.py`

- [ ] **Step 1: Escreva o teste que falha**

Acrescente ao fim de `tests/test_fase2_maquina_estados_obra.py`:

```python
def test_coluna_estado_existe_com_default_planejamento():
    """Obra criada sem informar `estado` nasce em PLANEJAMENTO — decisão 4
    da Fase 2: não existe obra em execução sem GP."""
    from models import Cliente, Obra
    with app.app_context():
        admin = _admin()
        suf = uuid.uuid4().hex[:8]
        cli = Cliente(nome=f'Cliente {suf}', admin_id=admin.id)
        db.session.add(cli)
        db.session.flush()
        o = Obra(nome=f'Obra {suf}', codigo=f'F2D{suf[:5].upper()}',
                 cliente_id=cli.id, data_inicio=date(2026, 7, 1),
                 admin_id=admin.id)
        db.session.add(o)
        db.session.commit()
        assert o.estado == 'planejamento'


def test_check_constraint_recusa_estado_fora_do_vocabulario():
    from sqlalchemy.exc import DatabaseError
    with app.app_context():
        admin = _admin()
        obra = _obra(admin)
        with pytest.raises(DatabaseError):
            db.session.execute(
                db.text('UPDATE obra SET estado = :e WHERE id = :i'),
                {'e': 'inventado', 'i': obra.id})
            db.session.commit()
        db.session.rollback()


def test_backfill_231_deriva_estado_do_status_legado_e_do_ativo():
    """A regra de derivação, exercida sobre as quatro combinações que o
    censo de 2026-07-21 encontrou no banco, mais um valor customizado."""
    from migrations import migration_231_obra_estado
    from models import ObraTransicaoEstado
    with app.app_context():
        admin = _admin()
        casos = [
            # (status legado, ativo, estado esperado)
            ('Em andamento', True, 'em_execucao'),
            ('Em Andamento', True, 'em_execucao'),
            ('Concluída', True, 'concluida'),
            ('Em andamento', False, 'concluida'),
            ('Aguardando ART', True, 'em_execucao'),
            ('Aguardando ART', False, 'concluida'),
            ('Cancelada', False, 'cancelada'),
        ]
        obras = []
        for status, ativo, _esperado in casos:
            o = _obra(admin, estado='planejamento', status=status, ativo=ativo)
            # Zera a coluna para simular a base pré-migração.
            db.session.execute(
                db.text('UPDATE obra SET estado = NULL WHERE id = :i'),
                {'i': o.id})
            obras.append(o)
        db.session.commit()

        migration_231_obra_estado()

        for (status, ativo, esperado), o in zip(casos, obras):
            db.session.refresh(o)
            assert o.estado == esperado, (
                f'status={status!r} ativo={ativo} → {o.estado!r}, '
                f'esperado {esperado!r}')
            linha = (ObraTransicaoEstado.query
                     .filter_by(obra_id=o.id, estado_de=None)
                     .order_by(ObraTransicaoEstado.id).first())
            assert linha is not None, 'backfill não gravou linha de histórico'
            assert linha.estado_para == esperado
            assert status in (linha.motivo or ''), (
                'a linha de backfill precisa carregar o status legado '
                'verbatim — é o que torna a migration 232 reversível')


def test_backfill_231_e_idempotente():
    from migrations import migration_231_obra_estado
    from models import ObraTransicaoEstado
    with app.app_context():
        admin = _admin()
        obra = _obra(admin, estado='em_execucao', status='Em andamento')
        migration_231_obra_estado()
        n1 = ObraTransicaoEstado.query.filter_by(obra_id=obra.id).count()
        migration_231_obra_estado()
        n2 = ObraTransicaoEstado.query.filter_by(obra_id=obra.id).count()
        assert n1 == n2, 'reexecutar a 231 duplicou histórico'
        db.session.refresh(obra)
        assert obra.estado == 'em_execucao'


def test_backfill_231_nao_deixa_nenhuma_obra_sem_estado():
    from migrations import migration_231_obra_estado
    from models import Obra
    with app.app_context():
        migration_231_obra_estado()
        orfas = db.session.query(Obra.id).filter(Obra.estado.is_(None)).count()
        assert orfas == 0
```

- [ ] **Step 2: Rode e veja falhar**

```bash
python -m pytest tests/test_fase2_maquina_estados_obra.py -k "coluna_estado or check_constraint or backfill" -v 2>&1 | tail -20
```

Esperado: FAIL — `AttributeError: type object 'Obra' has no attribute 'estado'` / `ImportError: cannot import name 'migration_231_obra_estado'`.

- [ ] **Step 3: Acrescente a coluna em `models.py`**

Em `models.py`, dentro de `class Obra`, imediatamente **depois** da linha 257 (`status = db.Column(db.String(20), default='Em andamento')`), insira:

```python
    # Fase 2 — estado canônico da obra. `status` (acima) e `ativo`
    # (abaixo) passam a ser DERIVADOS deste campo por write-through em
    # services/obra_estado.transitar(). Nenhuma leitura de `status`
    # precisou mudar no deploy: ela continua recebendo exatamente os
    # mesmos textos que recebia ('Em andamento', 'Concluída', ...).
    #
    # VARCHAR + CHECK em vez de ENUM nativo: ver docstring de EstadoObra.
    # O CHECK é criado pela migration 231, não pelo declarativo — o
    # SQLAlchemy criaria uma constraint sem nome estável, impossível de
    # dropar num rollback.
    estado = db.Column(
        db.String(20), nullable=False,
        default='planejamento', server_default='planejamento',
        index=True,
    )
```

- [ ] **Step 4: Escreva a migration 231**

Em `migrations.py`, imediatamente antes de `def executar_migracoes():`, insira:

```python
def migration_231_obra_estado():
    """Fase 2 — coluna `obra.estado` + backfill das obras reais.

    Roda sobre produção. Desenho para não deixar obra em estado inválido:

      1. ADD COLUMN ... NULL           (sem server_default ainda)
      2. UPDATE derivando de status/ativo, só onde estado IS NULL
      3. INSERT do histórico de backfill, só para obras sem histórico
      4. salvaguarda: qualquer NULL remanescente vira 'em_execucao'
      5. SET DEFAULT + SET NOT NULL + CHECK

    O passo 1 NÃO usa server_default de propósito: com server_default
    TODAS as obras nasceriam 'planejamento' e ficariam assim caso o passo
    2 falhasse — um estado errado é pior que um estado ausente, porque
    ninguém desconfia dele.

    CORREÇÃO 22/07: a versão anterior deste texto dizia "sem ele a coluna
    fica NULL e o boot aborta (app.py:668)". Isso é FALSO.
    `run_migration_safe` (migrations.py:198) diz literalmente "Não
    propagar exceção - apenas logar" e devolve False; `executar_migracoes`
    conta a falha e segue. O `except` de app.py:706 nunca dispara por
    falha de migração individual — e mesmo se disparasse, o abort é
    `if IS_PRODUCTION`. Prova viva: as migrations 48 e 132 falham em todo
    boot e a aplicação sobe.

    O que de fato protege, então:
      - `is_migration_executed` só aceita status 'success', logo a 231 é
        RETENTADA no boot seguinte;
      - o passo 1 commita sozinho, então a coluna sobrevive à falha e o
        passo 2 reexecuta do zero;
      - `estado_atual()` (Task 4) nunca levanta em obra sem estado — é o
        que segura a UI durante a janela entre a falha e o boot seguinte.
    Não confie num abort que não existe.

    Regra de derivação, em ordem (a ordem importa):
      a) status mapeia para 'cancelada'  → cancelada
      b) ativo = false                   → concluida
      c) status mapeia para algo         → esse algo
      d) resto                           → em_execucao

    Por que (b) vem antes de (c): `Obra.ativo` é a flag que a UI de fato
    respeita — o dashboard filtra por ela (views/dashboard.py:426,1011) e
    a listagem chama as inativas de "Obras Concluídas / Inativas"
    (templates/obras_moderno.html:803,819). No censo de 2026-07-21 havia
    13 obras com status='Em andamento' E ativo=false: para o usuário
    elas JÁ são concluídas. Fazer o estado dizer outra coisa criaria uma
    terceira verdade.

    Reversibilidade: a linha de histórico gravada no passo 3 carrega o
    `status` e o `ativo` originais verbatim no campo `motivo`. Para
    desfazer, basta ler de volta essa linha (ver docs/fase-2-rollout.md).

    Idempotente: seguro re-executar.
    """
    ESTADOS = ('planejamento', 'em_execucao', 'pausada', 'concluida', 'cancelada')

    try:
        # 1) coluna, sem default e sem NOT NULL
        db.session.execute(text("""
            ALTER TABLE obra ADD COLUMN IF NOT EXISTS estado VARCHAR(20) NULL
        """))
        db.session.commit()

        # 2) derivação. lower() resolve caixa; a enumeração explícita das
        #    formas com e sem acento evita depender da extensão unaccent,
        #    que não é garantida no Postgres do EasyPanel.
        atualizadas = db.session.execute(text("""
            UPDATE obra SET estado = CASE
                WHEN lower(coalesce(status, '')) IN
                     ('cancelada', 'cancelado', 'distratada')
                    THEN 'cancelada'
                WHEN ativo = false
                    THEN 'concluida'
                WHEN lower(coalesce(status, '')) IN
                     ('concluída', 'concluida', 'concluído', 'concluido',
                      'finalizada', 'finalizado', 'entregue')
                    THEN 'concluida'
                WHEN lower(coalesce(status, '')) IN
                     ('pausada', 'pausado', 'paralisada', 'paralisado')
                    THEN 'pausada'
                WHEN lower(coalesce(status, '')) IN
                     ('planejamento', 'planejada', 'planejado')
                    THEN 'planejamento'
                ELSE 'em_execucao'
            END
            WHERE estado IS NULL
        """)).rowcount
        db.session.commit()
        logger.info(f"[Migration 231] {atualizadas} obra(s) com estado derivado")

        # 3) linha de histórico com o valor legado verbatim.
        #    `obra.admin_id` é nullable (models.py:276) e a coluna do
        #    histórico é NOT NULL — obras sem tenant ficam de fora e são
        #    listadas no log. No banco conferido em 2026-07-21 são zero.
        sem_tenant = db.session.execute(text("""
            SELECT count(*) FROM obra WHERE admin_id IS NULL
        """)).scalar()
        if sem_tenant:
            logger.warning(
                f"[Migration 231] {sem_tenant} obra(s) com admin_id NULL "
                "ficaram sem linha de histórico de backfill"
            )

        inseridas = db.session.execute(text("""
            INSERT INTO obra_transicao_estado
                (obra_id, admin_id, estado_de, estado_para, motivo,
                 usuario_id, criado_em)
            SELECT o.id, o.admin_id, NULL, o.estado,
                   'backfill migration 231 — status legado='
                     || coalesce(o.status, '<NULL>')
                     || ' | ativo=' || o.ativo::text,
                   NULL,
                   coalesce(o.created_at, NOW())
            FROM obra o
            WHERE o.admin_id IS NOT NULL
              AND o.estado IS NOT NULL
              AND NOT EXISTS (
                  SELECT 1 FROM obra_transicao_estado t
                  WHERE t.obra_id = o.id AND t.estado_de IS NULL
              )
        """)).rowcount
        db.session.commit()
        logger.info(f"[Migration 231] {inseridas} linha(s) de histórico de backfill")

        # 4) salvaguarda — nunca deixar obra em estado inválido
        restantes = db.session.execute(text("""
            UPDATE obra SET estado = 'em_execucao' WHERE estado IS NULL
        """)).rowcount
        if restantes:
            logger.warning(
                f"[Migration 231] {restantes} obra(s) caíram na salvaguarda "
                "'em_execucao' — investigar (o CASE do passo 2 deveria ser total)"
            )
        db.session.commit()

        # 5) trancar o contrato
        db.session.execute(text("""
            ALTER TABLE obra ALTER COLUMN estado SET DEFAULT 'planejamento'
        """))
        db.session.execute(text("""
            ALTER TABLE obra ALTER COLUMN estado SET NOT NULL
        """))
        lista = ", ".join(f"'{e}'" for e in ESTADOS)
        db.session.execute(text(f"""
            DO $$
            BEGIN
                IF NOT EXISTS (
                    SELECT 1 FROM pg_constraint WHERE conname = 'ck_obra_estado'
                ) THEN
                    ALTER TABLE obra ADD CONSTRAINT ck_obra_estado
                        CHECK (estado IN ({lista}));
                END IF;
            END $$;
        """))
        db.session.execute(text("""
            CREATE INDEX IF NOT EXISTS ix_obra_estado ON obra (estado)
        """))
        db.session.commit()

        distribuicao = db.session.execute(text("""
            SELECT estado, count(*) FROM obra GROUP BY estado ORDER BY 2 DESC
        """)).fetchall()
        logger.info(
            "MIGRACAO 231 CONCLUIDA: obra.estado NOT NULL + CHECK + indice. "
            f"Distribuicao: {[(r[0], r[1]) for r in distribuicao]}"
        )
    except Exception as e:
        db.session.rollback()
        logger.error(f"[Migration 231] Erro: {e}")
        raise
```

- [ ] **Step 5: Registre a migration**

Em `migrations.py`, na lista `migrations_to_run`, logo depois da linha da 230:

```python
            (231, "Fase 2 — obra.estado (VARCHAR+CHECK) + backfill derivado de status/ativo + historico de backfill", migration_231_obra_estado),
```

- [ ] **Step 6: Rode e verifique**

```bash
python -c "
from app import app
with app.app_context():
    from migrations import migration_231_obra_estado as m
    m()
" 2>&1 | tail -8
python -m pytest tests/test_fase2_maquina_estados_obra.py -v 2>&1 | tail -20
```

Esperado: log `MIGRACAO 231 CONCLUIDA` com a distribuição, e **todos** os testes do arquivo PASSAM (16 até aqui).

- [ ] **Step 7: Commit**

```bash
git add models.py migrations.py tests/test_fase2_maquina_estados_obra.py
git commit -m "feat(fase2): coluna obra.estado + migration 231 com backfill dos dados reais

Coluna nasce NULL, backfill deriva de status/ativo, historico grava o
valor legado verbatim, e so entao NOT NULL + CHECK. Sem server_default
no passo 1 de proposito: se o backfill falhar o boot aborta (app.py:668)
em vez de servir 7.984 obras marcadas como planejamento."
```

---

## Task 4: `transitar()` — a guarda que recusa transição inválida

**Files:**
- Modify: `services/obra_estado.py`
- Test: `tests/test_fase2_maquina_estados_obra.py`

- [ ] **Step 1: Escreva o teste que falha**

Acrescente ao fim de `tests/test_fase2_maquina_estados_obra.py`:

```python
def test_transitar_grava_historico_e_sincroniza_status_e_ativo():
    from models import EstadoObra, ObraTransicaoEstado
    from services.obra_estado import transitar
    with app.app_context():
        admin = _admin()
        obra = _obra(admin, estado='em_execucao', status='Em andamento')
        reg = transitar(obra, EstadoObra.CONCLUIDA, usuario_id=admin.id)
        db.session.commit()
        db.session.refresh(obra)
        assert obra.estado == 'concluida'
        assert obra.status == 'Concluída'      # write-through no campo legado
        assert obra.ativo is False             # ativo passa a ser derivado
        assert reg.estado_de == 'em_execucao'
        assert reg.estado_para == 'concluida'
        assert reg.usuario_id == admin.id
        assert ObraTransicaoEstado.query.filter_by(
            obra_id=obra.id, estado_para='concluida').count() == 1


def test_transitar_recusa_salto_fora_do_grafo_e_nao_grava_nada():
    from models import EstadoObra, ObraTransicaoEstado
    from services.obra_estado import TransicaoInvalida, transitar
    with app.app_context():
        admin = _admin()
        obra = _obra(admin, estado='planejamento', status='Planejamento')
        antes = ObraTransicaoEstado.query.filter_by(obra_id=obra.id).count()
        with pytest.raises(TransicaoInvalida):
            transitar(obra, EstadoObra.CONCLUIDA, usuario_id=admin.id)
        db.session.rollback()
        db.session.refresh(obra)
        assert obra.estado == 'planejamento'
        assert ObraTransicaoEstado.query.filter_by(obra_id=obra.id).count() == antes


def test_transitar_de_cancelada_nunca_passa():
    from models import EstadoObra
    from services.obra_estado import TransicaoInvalida, transitar
    with app.app_context():
        admin = _admin()
        obra = _obra(admin, estado='cancelada', status='Cancelada', ativo=False)
        for destino in EstadoObra:
            with pytest.raises(TransicaoInvalida):
                transitar(obra, destino, usuario_id=admin.id, motivo='tentativa')
        db.session.rollback()


def test_transitar_exige_motivo_onde_o_contrato_manda():
    from models import EstadoObra
    from services.obra_estado import TransicaoInvalida, transitar
    with app.app_context():
        admin = _admin()
        obra = _obra(admin, estado='em_execucao', status='Em andamento')
        with pytest.raises(TransicaoInvalida) as exc:
            transitar(obra, EstadoObra.PAUSADA, usuario_id=admin.id, motivo='   ')
        assert 'motivo' in str(exc.value).lower()
        db.session.rollback()
        db.session.refresh(obra)
        assert obra.estado == 'em_execucao'


def test_transitar_aceita_motivo_e_registra_detalhes():
    from models import EstadoObra
    from services.obra_estado import transitar
    with app.app_context():
        admin = _admin()
        obra = _obra(admin, estado='em_execucao', status='Em andamento')
        reg = transitar(obra, EstadoObra.PAUSADA, usuario_id=admin.id,
                        motivo='Chuva por 12 dias seguidos',
                        detalhes={'origem': 'pytest'})
        db.session.commit()
        assert reg.motivo == 'Chuva por 12 dias seguidos'
        assert reg.detalhes == {'origem': 'pytest'}
        db.session.refresh(obra)
        assert obra.ativo is True   # pausada continua ativa na listagem


def test_transitar_nao_commita_sozinho():
    """Contrato do repo: quem chama é dono da transação
    (event_manager.py:882-887)."""
    from models import EstadoObra, Obra
    from services.obra_estado import transitar
    with app.app_context():
        admin = _admin()
        obra = _obra(admin, estado='em_execucao', status='Em andamento')
        obra_id = obra.id
        transitar(obra, EstadoObra.CONCLUIDA, usuario_id=admin.id)
        db.session.rollback()
        recarregada = db.session.get(Obra, obra_id)
        assert recarregada.estado == 'em_execucao'
```

- [ ] **Step 2: Rode e veja falhar**

```bash
python -m pytest tests/test_fase2_maquina_estados_obra.py -k transitar -v 2>&1 | tail -20
```

Esperado: FAIL — `ImportError: cannot import name 'transitar' from 'services.obra_estado'`.

- [ ] **Step 3: Acrescente `transitar()` ao serviço**

Ao fim de `services/obra_estado.py`, adicione:

```python
def estado_atual(obra) -> EstadoObra:
    """Estado corrente da obra, tolerante a linha legada.

    Se `obra.estado` vier vazio (linha inserida por SQL cru fora da
    migração), cai no texto de `obra.status` e, em último caso, no
    eixo `obra.ativo`. Nunca levanta — quem lê estado de uma obra não
    pode ser derrubado por dado sujo.

    CORREÇÃO 22/07 (achado D): a ordem abaixo tem que ser a MESMA do CASE
    da migration 231, senão a regra de derivação existe duas vezes, em
    duas linguagens, e discorda de si mesma. O caso em que discordava:
    `status='Em andamento'` + `ativo=False` — o SQL diz 'concluida'
    (ativo vence), a versão anterior desta função dizia 'em_execucao'
    (status vencia). E este fallback só roda quando `estado` está vazio,
    que é exatamente a janela pós-falha da 231.

    Ordem canônica, idêntica à do passo 2 da migration 231:
      a) status mapeia para 'cancelada'  → cancelada
      b) ativo = false                   → concluida
      c) status mapeia para algo         → esse algo
      d) resto                           → em_execucao
    """
    try:
        return coagir(getattr(obra, 'estado', None))
    except EstadoDesconhecido:
        pass
    do_legado = estado_do_status_legado(getattr(obra, 'status', None))
    if do_legado is EstadoObra.CANCELADA:          # (a)
        return EstadoObra.CANCELADA
    if getattr(obra, 'ativo', True) is False:      # (b) — ativo vence status
        return EstadoObra.CONCLUIDA
    if do_legado is not None:                      # (c)
        return do_legado
    return EstadoObra.EM_EXECUCAO                  # (d)


def aplicar_estado(obra, estado: EstadoObra) -> None:
    """Escreve o estado e sincroniza os dois campos derivados.

    `status` e `ativo` continuam existindo porque ~40 templates e
    queries os leem (censo em docs/superpowers/plans/2026-07-21-fase-2).
    Eles deixam de ser fonte de verdade e passam a ser espelho.
    """
    obra.estado = estado.value
    obra.status = ROTULOS[estado]
    obra.ativo = estado not in ESTADOS_INATIVOS


def transitar(obra, para, usuario_id=None, motivo: str = '',
              detalhes: dict | None = None):
    """Executa uma transição validada e devolve o registro de histórico.

    Valida, nesta ordem: vocabulário → grafo → motivo obrigatório.
    NÃO valida autorização — isso é `pode_transitar_como`, chamado pela
    rota, porque o serviço também é usado por migração e por seed, onde
    não existe `current_user`.

    Não commita: a rota (ou o handler) é dona da transação, mesmo
    contrato de `propagar_proposta_para_obra` (event_manager.py:882-887).
    Faz `flush` para que o id do registro exista para o chamador.
    """
    from models import ObraTransicaoEstado, db

    de = estado_atual(obra)
    destino = coagir(para)

    if destino not in TRANSICOES.get(de, ()):
        permitidos = ', '.join(e.value for e in TRANSICOES.get(de, ())) or '(nenhum)'
        raise TransicaoInvalida(
            f'Obra {getattr(obra, "id", "?")}: transição '
            f'{de.value} → {destino.value} não é permitida. '
            f'A partir de {de.value} só é possível ir para: {permitidos}.')

    motivo_limpo = (motivo or '').strip()
    if (de, destino) in TRANSICOES_QUE_EXIGEM_MOTIVO and not motivo_limpo:
        raise TransicaoInvalida(
            f'A transição {de.value} → {destino.value} exige motivo escrito.')

    aplicar_estado(obra, destino)

    registro = ObraTransicaoEstado(
        obra_id=obra.id,
        admin_id=obra.admin_id,
        estado_de=de.value,
        estado_para=destino.value,
        motivo=motivo_limpo or None,
        detalhes=detalhes or None,
        usuario_id=usuario_id,
    )
    db.session.add(registro)
    db.session.flush()

    # Log estruturado, no molde de services/cronograma_observabilidade.py:34.
    # Nunca derruba o fluxo.
    try:
        logger.info(
            'evento=transicao obra_id=%s admin_id=%s de=%s para=%s '
            'usuario_id=%s motivo=%r',
            obra.id, obra.admin_id, de.value, destino.value,
            usuario_id, motivo_limpo[:120])
    except Exception:
        logger.debug('falha ao logar transição de obra', exc_info=True)

    return registro
```

- [ ] **Step 4: Rode os testes**

```bash
python -m pytest tests/test_fase2_maquina_estados_obra.py -v 2>&1 | tail -20
```

Esperado: 22 testes PASSAM.

- [ ] **Step 5: Commit**

```bash
git add services/obra_estado.py tests/test_fase2_maquina_estados_obra.py
git commit -m "feat(fase2): transitar() valida grafo, exige motivo e grava historico

Write-through mantem Obra.status e Obra.ativo corretos sem tocar nas ~40
leituras existentes. Nao commita: a rota e dona da transacao, mesmo
contrato dos handlers de evento (event_manager.py:882-887)."
```

---

## Task 5: Autorização por transição (`pode_transitar_como`)

Consome os dois eixos da Fase 1: `TipoUsuario` (tenant) e `PapelObra` via `utils/autorizacao.papel_na_obra`.

**Files:**
- Modify: `services/obra_estado.py`
- Test: `tests/test_fase2_maquina_estados_obra.py`

- [ ] **Step 1: Escreva o teste que falha**

Acrescente ao fim de `tests/test_fase2_maquina_estados_obra.py`:

```python
def _funcionario(admin, nome='GP Teste'):
    from models import Funcionario
    suf = uuid.uuid4().hex[:8]
    f = Funcionario(
        codigo=f'F2{suf[:6].upper()}', nome=f'{nome} {suf}',
        cpf=f'{uuid.uuid4().int % 10**11:011d}',
        data_admissao=date(2026, 1, 5), admin_id=admin.id, ativo=True,
    )
    db.session.add(f)
    db.session.commit()
    return f


def _usuario_comum(admin, funcionario=None):
    """Usuário FUNCIONARIO do tenant, opcionalmente ligado a um Funcionario."""
    from models import TipoUsuario, Usuario
    from utils.identidade import vincular_funcionario
    suf = uuid.uuid4().hex[:8]
    u = Usuario(
        username=f'f2u_{suf}', email=f'f2u_{suf}@test.local',
        nome=f'Usuario {suf}',
        password_hash=generate_password_hash('Senha@2026'),
        tipo_usuario=TipoUsuario.FUNCIONARIO, ativo=True,
        admin_id=admin.id, versao_sistema='v2',
    )
    db.session.add(u)
    db.session.flush()
    if funcionario is not None:
        vincular_funcionario(u, funcionario)
    db.session.commit()
    return u


def _vincular_gestor(usuario, obra):
    from models import PapelObra, UsuarioObra
    v = UsuarioObra(usuario_id=usuario.id, obra_id=obra.id,
                    papel=PapelObra.GESTOR, admin_id=obra.admin_id, ativo=True)
    db.session.add(v)
    db.session.commit()
    return v


def test_gestor_da_obra_pausa_mas_nao_faz_handoff():
    from models import EstadoObra
    from services.obra_estado import pode_transitar_como
    with app.app_context():
        admin = _admin()
        obra = _obra(admin, estado='em_execucao', status='Em andamento')
        func = _funcionario(admin)
        gp = _usuario_comum(admin, func)
        _vincular_gestor(gp, obra)
        assert pode_transitar_como(obra, EstadoObra.PAUSADA, gp) is True
        assert pode_transitar_como(obra, EstadoObra.CONCLUIDA, gp) is True
        # Cancelar é decisão comercial: 'admin'.
        assert pode_transitar_como(obra, EstadoObra.CANCELADA, gp) is False


def test_gestor_nao_faz_o_handoff_da_propria_obra():
    from models import EstadoObra
    from services.obra_estado import pode_transitar_como
    with app.app_context():
        admin = _admin()
        obra = _obra(admin, estado='planejamento', status='Planejamento')
        gp = _usuario_comum(admin, _funcionario(admin))
        _vincular_gestor(gp, obra)
        assert pode_transitar_como(obra, EstadoObra.EM_EXECUCAO, gp) is False


def test_admin_do_tenant_pode_todas_as_transicoes_do_grafo():
    from models import EstadoObra
    from services.obra_estado import TRANSICOES, pode_transitar_como
    with app.app_context():
        admin = _admin()
        for origem, destinos in TRANSICOES.items():
            obra = _obra(admin, estado=origem.value)
            for destino in destinos:
                assert pode_transitar_como(obra, destino, admin) is True, (
                    f'ADMIN barrado em {origem.value} → {destino.value}')
            for destino in EstadoObra:
                if destino not in destinos:
                    assert pode_transitar_como(obra, destino, admin) is False


def test_usuario_sem_vinculo_nao_transita_nada():
    from models import EstadoObra
    from services.obra_estado import pode_transitar_como
    with app.app_context():
        admin = _admin()
        obra = _obra(admin, estado='em_execucao', status='Em andamento')
        estranho = _usuario_comum(admin)
        assert pode_transitar_como(obra, EstadoObra.PAUSADA, estranho) is False


def test_admin_de_outro_tenant_nao_transita():
    from models import EstadoObra
    from services.obra_estado import pode_transitar_como
    with app.app_context():
        dono = _admin()
        intruso = _admin('f2i')
        obra = _obra(dono, estado='em_execucao', status='Em andamento')
        assert pode_transitar_como(obra, EstadoObra.PAUSADA, intruso) is False
```

- [ ] **Step 2: Rode e veja falhar**

```bash
python -m pytest tests/test_fase2_maquina_estados_obra.py -k "gestor or admin_do_tenant or sem_vinculo or outro_tenant" -v 2>&1 | tail -20
```

Esperado: FAIL — `ImportError: cannot import name 'pode_transitar_como'`.

- [ ] **Step 3: Acrescente a autorização ao serviço**

Ao fim de `services/obra_estado.py`, adicione:

```python
def pode_transitar_como(obra, para, usuario=None) -> bool:
    """`usuario` pode disparar esta transição nesta obra?

    Dois eixos, ambos obrigatórios (Fase 1):
      • tenant  — a obra tem de pertencer ao tenant do usuário;
      • obra    — 'admin' exige TipoUsuario.ADMIN/SUPER_ADMIN;
                  'gestor' aceita também quem tem UsuarioObra(GESTOR).

    Falha FECHADA: anônimo, tenant divergente, transição fora do grafo
    ou estado ilegível devolvem False, nunca exceção. A rota converte
    isso em 403/404; o serviço não decide resposta HTTP.

    `usuario=None` significa "use o current_user" — o mesmo default de
    utils/autorizacao.papel_na_obra.
    """
    from models import PapelObra, TipoUsuario
    from utils.identidade import tenant_do_usuario

    if obra is None:
        return False

    if usuario is None:
        try:
            from flask_login import current_user
            if not current_user.is_authenticated:
                return False
            usuario = current_user
        except Exception:
            return False

    tenant = tenant_do_usuario(usuario)
    if tenant is None or obra.admin_id != tenant:
        return False

    try:
        de = estado_atual(obra)
        destino = coagir(para)
    except EstadoDesconhecido:
        return False

    if destino not in TRANSICOES.get(de, ()):
        return False

    e_admin = usuario.tipo_usuario in (TipoUsuario.ADMIN, TipoUsuario.SUPER_ADMIN)
    if e_admin:
        return True

    if autoridade_necessaria(de, destino) == 'admin':
        return False

    # 'gestor': precisa de vínculo explícito com papel GESTOR nesta obra.
    # Consultamos a tabela diretamente em vez de usar
    # utils.autorizacao.papel_na_obra porque aquela função devolve LEITOR
    # por omissão quando a flag escopo_obra_ativo está desligada — o que é
    # correto para LEITURA, e seria um furo para ESCRITA de estado.
    from models import UsuarioObra
    vinculo = UsuarioObra.query.filter_by(
        usuario_id=usuario.id, obra_id=obra.id, ativo=True).first()
    return vinculo is not None and vinculo.papel == PapelObra.GESTOR
```

- [ ] **Step 4: Rode os testes**

```bash
python -m pytest tests/test_fase2_maquina_estados_obra.py -v 2>&1 | tail -20
```

Esperado: 27 testes PASSAM.

- [ ] **Step 5: Commit**

```bash
git add services/obra_estado.py tests/test_fase2_maquina_estados_obra.py
git commit -m "feat(fase2): autorizacao por transicao com os dois eixos da Fase 1

Handoff e cancelamento sao 'admin'; pausar, retomar e concluir sao do
GESTOR da obra. Consulta usuario_obra direto em vez de papel_na_obra:
aquela devolve LEITOR por omissao com a flag desligada, o que seria furo
para escrita de estado."
```

---

## Task 6: Migration 232 — alinhar o `status` legado ao `estado`

> **Reescrita na revisão de 22/07 (achado A).** A premissa original era
> deduplicar grafia — "as 53 linhas gravadas `'Em Andamento'` que o filtro vivo
> nunca encontra". Esse trabalho **já foi feito**: a migration 217
> (`_migration_217_canonizar_status_obra`, Fase 0.6 / D5) canonizou
> `obra.status` e o dropdown que o alimenta, e o `@validates('status')` de
> `models.py:415` impede que a divergência volte. Por isso este banco tem zero
> `'Em Andamento'`.
>
> O que **sobra** para a 232, e continua necessário: depois que a 231 derivou
> `estado` de `status`+`ativo`, as duas colunas podem discordar — uma obra com
> `status='Em andamento'` e `ativo=false` virou `estado='concluida'`, mas o
> texto de `status` continua dizendo "Em andamento". A 232 realinha `status`
> ao `estado`, que passou a ser a fonte de verdade. É o inverso da 231.
>
> Consequência prática: só toca linhas onde `status <> ROTULOS[estado]`. Neste
> banco isso é 1 obra (a única com `ativo=false` e status de andamento); em
> produção, reconferir.

**Files:**
- Modify: `migrations.py`
- Test: `tests/test_fase2_maquina_estados_obra.py`

- [ ] **Step 1: Escreva o teste que falha**

Acrescente ao fim de `tests/test_fase2_maquina_estados_obra.py`:

```python
def test_migration_232_alinha_status_legado_ao_estado():
    from migrations import migration_232_normalizar_status_legado
    with app.app_context():
        admin = _admin()
        divergentes = [
            _obra(admin, estado='em_execucao', status='Em Andamento'),
            _obra(admin, estado='em_execucao', status='Aguardando ART'),
            _obra(admin, estado='concluida', status='Em andamento', ativo=False),
            _obra(admin, estado='planejamento', status='Em andamento'),
        ]
        migration_232_normalizar_status_legado()
        esperados = ['Em andamento', 'Em andamento', 'Concluída', 'Planejamento']
        for obra, esperado in zip(divergentes, esperados):
            db.session.refresh(obra)
            assert obra.status == esperado


def test_migration_232_e_idempotente():
    from migrations import migration_232_normalizar_status_legado
    with app.app_context():
        admin = _admin()
        obra = _obra(admin, estado='pausada', status='Em Andamento')
        migration_232_normalizar_status_legado()
        db.session.refresh(obra)
        primeiro = obra.status
        migration_232_normalizar_status_legado()
        db.session.refresh(obra)
        assert obra.status == primeiro == 'Pausada'


def test_todo_status_do_banco_e_um_rotulo_conhecido_apos_232():
    """Depois da 232 não pode sobrar grafia fora do vocabulário."""
    from migrations import migration_232_normalizar_status_legado
    from services.obra_estado import ROTULOS
    with app.app_context():
        migration_232_normalizar_status_legado()
        valores = {r[0] for r in db.session.execute(
            db.text('SELECT DISTINCT status FROM obra')).fetchall()}
        assert valores <= set(ROTULOS.values()), (
            f'grafias fora do vocabulário: {valores - set(ROTULOS.values())}')
```

- [ ] **Step 2: Rode e veja falhar**

```bash
python -m pytest tests/test_fase2_maquina_estados_obra.py -k 232 -v 2>&1 | tail -20
```

Esperado: FAIL — `ImportError: cannot import name 'migration_232_normalizar_status_legado'`.

- [ ] **Step 3: Escreva a migration 232**

Em `migrations.py`, imediatamente antes de `def executar_migracoes():`, insira:

```python
def migration_232_normalizar_status_legado():
    """Fase 2 — alinha `obra.status` (texto legado) ao `obra.estado`.

    Depois da 231, `estado` é a fonte de verdade e `status` é espelho.
    Esta migração faz o espelho refletir de fato: as linhas antigas ainda
    carregam a grafia com que foram gravadas.

    O que isso conserta, concretamente: o formulário de obra oferecia
    'Em Andamento' (services/dropdown_service.py:94, forms.py:42,
    templates/obra_form.html:322) enquanto o filtro vivo da listagem
    procura 'Em andamento' (templates/obras_moderno.html:616) por
    igualdade exata (views/obras.py:83). As 53 obras salvas pelo
    formulário simplesmente não apareciam ao filtrar. Depois desta
    migração existe uma grafia só por estado.

    Reversível: a linha de backfill da migration 231 guarda o `status`
    original verbatim no campo `motivo` de `obra_transicao_estado`
    (ver docs/fase-2-rollout.md para o UPDATE de volta).

    Idempotente: o WHERE só toca linhas já divergentes.
    """
    try:
        rotulo_sql = """
            CASE o.estado
                WHEN 'planejamento' THEN 'Planejamento'
                WHEN 'em_execucao'  THEN 'Em andamento'
                WHEN 'pausada'      THEN 'Pausada'
                WHEN 'concluida'    THEN 'Concluída'
                WHEN 'cancelada'    THEN 'Cancelada'
                ELSE o.status
            END
        """
        alteradas = db.session.execute(text(f"""
            UPDATE obra o
               SET status = {rotulo_sql}
             WHERE o.status IS DISTINCT FROM ({rotulo_sql})
        """)).rowcount
        db.session.commit()

        restantes = db.session.execute(text("""
            SELECT status, count(*) FROM obra GROUP BY status ORDER BY 2 DESC
        """)).fetchall()
        logger.info(
            f"MIGRACAO 232 CONCLUIDA: {alteradas} obra(s) com status legado "
            f"normalizado. Distribuicao final: {[(r[0], r[1]) for r in restantes]}"
        )
    except Exception as e:
        db.session.rollback()
        logger.error(f"[Migration 232] Erro: {e}")
        raise
```

- [ ] **Step 4: Registre a migration**

Em `migrations.py`, na lista `migrations_to_run`, logo depois da linha da 231:

```python
            (232, "Fase 2 — normaliza obra.status legado para o rotulo canonico do estado (corrige 'Em Andamento' x 'Em andamento')", migration_232_normalizar_status_legado),
```

- [ ] **Step 5: Rode e verifique**

```bash
python -c "
from app import app
with app.app_context():
    from migrations import migration_232_normalizar_status_legado as m
    m()
" 2>&1 | tail -5
python -m pytest tests/test_fase2_maquina_estados_obra.py -v 2>&1 | tail -20
```

Esperado: log `MIGRACAO 232 CONCLUIDA` mostrando no máximo cinco grafias distintas; 30 testes PASSAM.

- [ ] **Step 6: Commit**

```bash
git add migrations.py tests/test_fase2_maquina_estados_obra.py
git commit -m "feat(fase2): migration 232 normaliza o status legado

Uma grafia por estado. Conserta as 53 obras gravadas como 'Em Andamento'
pelo formulario (dropdown_service.py:94) que o filtro da listagem
(obras_moderno.html:616 + views/obras.py:83) nunca encontrava."
```

---

## Task 7: Handoff do GP (`services/obra_handoff.py`)

O handoff é a transição `PLANEJAMENTO → EM_EXECUCAO` empacotada com três efeitos que hoje não existem: atribuir `Obra.responsavel_id`, criar o `UsuarioObra` com papel `GESTOR`, e resolver o gate de cronograma.

**Files:**
- Create: `services/obra_handoff.py`
- Test: `tests/test_fase2_handoff_gp.py`

- [ ] **Step 1: Escreva o teste que falha**

Crie `tests/test_fase2_handoff_gp.py`:

```python
"""Fase 2 — handoff do Gerente de Projeto.

Antes desta fase o "responsável pela obra" era `Obra.responsavel_id`
(models.py:258), uma FK para `Funcionario` que não governava permissão
nenhuma e nem sequer tinha `relationship` — `obra.responsavel` resolvia
para Undefined em todos os templates que o usam
(templates/obras.html:266, obras_moderno.html:760, detalhes_obra.html:231,
detalhes_obra_profissional.html:1410) e a Fase 1 é quem conserta isso.
No banco de 2026-07-21, 3 de 7.984 obras tinham `responsavel_id`
preenchido.

O handoff passa a ser um ato: atribui o responsável, cria o vínculo
UsuarioObra(GESTOR) — a permissão de verdade — e move a obra para
EM_EXECUCAO com registro de quem entregou.
"""
import os
import sys
import uuid
from datetime import date

import pytest
from werkzeug.security import generate_password_hash

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import main  # noqa: F401 — registra os blueprints
from app import app, db

pytestmark = pytest.mark.integration


@pytest.fixture(autouse=True)
def _config():
    app.config['TESTING'] = True
    app.config['WTF_CSRF_ENABLED'] = False
    if not app.secret_key:
        app.secret_key = 'test-fase2-handoff'
    yield


def _admin(prefixo='f2h'):
    from models import TipoUsuario, Usuario
    suf = uuid.uuid4().hex[:8]
    u = Usuario(
        username=f'{prefixo}_{suf}', email=f'{prefixo}_{suf}@test.local',
        nome=f'Admin {suf}',
        password_hash=generate_password_hash('Senha@2026'),
        tipo_usuario=TipoUsuario.ADMIN, ativo=True, versao_sistema='v2',
    )
    db.session.add(u)
    db.session.commit()
    return u


def _obra(admin, estado='planejamento', status='Planejamento',
          cronograma_revisado=True):
    from datetime import datetime as _dt

    from models import Cliente, Obra
    suf = uuid.uuid4().hex[:8]
    cli = Cliente(nome=f'Cliente {suf}', admin_id=admin.id)
    db.session.add(cli)
    db.session.flush()
    o = Obra(
        nome=f'Obra {suf}', codigo=f'H{suf[:7].upper()}',
        cliente_id=cli.id, data_inicio=date(2026, 7, 1),
        status=status, estado=estado, ativo=True, admin_id=admin.id,
        cronograma_revisado_em=(_dt.utcnow() if cronograma_revisado else None),
    )
    db.session.add(o)
    db.session.commit()
    return o


def _funcionario(admin, com_login=True):
    from models import Funcionario, TipoUsuario, Usuario
    from utils.identidade import vincular_funcionario
    suf = uuid.uuid4().hex[:8]
    f = Funcionario(
        codigo=f'H{suf[:7].upper()}', nome=f'GP {suf}',
        cpf=f'{uuid.uuid4().int % 10**11:011d}',
        data_admissao=date(2026, 1, 5), admin_id=admin.id, ativo=True,
        email=f'gp_{suf}@test.local',
    )
    db.session.add(f)
    db.session.flush()
    if com_login:
        u = Usuario(
            username=f'gp_{suf}', email=f'gp_{suf}@test.local',
            nome=f'GP {suf}',
            password_hash=generate_password_hash('Senha@2026'),
            tipo_usuario=TipoUsuario.FUNCIONARIO, ativo=True,
            admin_id=admin.id, versao_sistema='v2',
        )
        db.session.add(u)
        db.session.flush()
        vincular_funcionario(u, f)
    db.session.commit()
    return f


def test_handoff_atribui_responsavel_cria_gestor_e_move_para_execucao():
    from models import ObraTransicaoEstado, PapelObra, UsuarioObra
    from services.obra_handoff import executar_handoff
    with app.app_context():
        admin = _admin()
        obra = _obra(admin)
        func = _funcionario(admin)

        resultado = executar_handoff(obra, func, usuario_id=admin.id,
                                     motivo='Kickoff 21/07')
        db.session.commit()
        db.session.refresh(obra)

        assert obra.estado == 'em_execucao'
        assert obra.status == 'Em andamento'
        assert obra.responsavel_id == func.id

        vinculo = UsuarioObra.query.filter_by(obra_id=obra.id, ativo=True).one()
        assert vinculo.papel == PapelObra.GESTOR
        assert vinculo.usuario_id == resultado['usuario_gp_id']
        assert vinculo.admin_id == obra.admin_id

        trans = (ObraTransicaoEstado.query
                 .filter_by(obra_id=obra.id, estado_para='em_execucao')
                 .one())
        assert trans.estado_de == 'planejamento'
        assert trans.usuario_id == admin.id
        assert trans.detalhes['funcionario_id'] == func.id
        assert trans.detalhes['tipo'] == 'handoff'


def test_handoff_recusa_gp_sem_login():
    """Sem Usuario não há a quem dar o UsuarioObra — e um handoff que não
    cria vínculo é só um campo preenchido, que é o que já temos hoje."""
    from services.obra_handoff import HandoffInvalido, executar_handoff
    with app.app_context():
        admin = _admin()
        obra = _obra(admin)
        func = _funcionario(admin, com_login=False)
        with pytest.raises(HandoffInvalido) as exc:
            executar_handoff(obra, func, usuario_id=admin.id)
        assert 'login' in str(exc.value).lower()
        db.session.rollback()
        db.session.refresh(obra)
        assert obra.estado == 'planejamento'
        assert obra.responsavel_id is None


def test_handoff_recusa_funcionario_de_outro_tenant():
    from services.obra_handoff import HandoffInvalido, executar_handoff
    with app.app_context():
        dono = _admin()
        outro = _admin('f2x')
        obra = _obra(dono)
        func_alheio = _funcionario(outro)
        with pytest.raises(HandoffInvalido) as exc:
            executar_handoff(obra, func_alheio, usuario_id=dono.id)
        assert 'tenant' in str(exc.value).lower()
        db.session.rollback()


def test_handoff_recusa_obra_que_nao_esta_em_planejamento():
    from services.obra_handoff import executar_handoff
    from services.obra_estado import TransicaoInvalida
    with app.app_context():
        admin = _admin()
        obra = _obra(admin, estado='em_execucao', status='Em andamento')
        func = _funcionario(admin)
        with pytest.raises(TransicaoInvalida):
            executar_handoff(obra, func, usuario_id=admin.id)
        db.session.rollback()


def test_handoff_carimba_cronograma_quando_nao_ha_o_que_revisar():
    """Obra criada à mão nunca dispara o gate Task #200 (não tem proposta
    de origem), então `cronograma_revisado_em` ficaria NULL para sempre.
    O handoff resolve o carimbo e registra que resolveu."""
    from models import ObraTransicaoEstado
    from services.obra_handoff import executar_handoff
    with app.app_context():
        admin = _admin()
        obra = _obra(admin, cronograma_revisado=False)
        func = _funcionario(admin)
        executar_handoff(obra, func, usuario_id=admin.id)
        db.session.commit()
        db.session.refresh(obra)
        assert obra.cronograma_revisado_em is not None
        trans = ObraTransicaoEstado.query.filter_by(
            obra_id=obra.id, estado_para='em_execucao').one()
        assert trans.detalhes['cronograma_carimbado_no_handoff'] is True


def test_handoff_e_idempotente_no_vinculo():
    """Refazer o handoff para o mesmo GP não pode duplicar UsuarioObra
    (a UNIQUE (usuario_id, obra_id) da Fase 1 explodiria)."""
    from models import EstadoObra, UsuarioObra
    from services.obra_estado import transitar
    from services.obra_handoff import executar_handoff
    with app.app_context():
        admin = _admin()
        obra = _obra(admin)
        func = _funcionario(admin)
        executar_handoff(obra, func, usuario_id=admin.id)
        db.session.commit()
        # Pausa e volta para planejamento não existe no grafo; simulamos
        # a reentrada devolvendo a obra ao estado inicial por SQL cru,
        # que é o cenário de suporte ("desfizeram o handoff no banco").
        db.session.execute(
            db.text("UPDATE obra SET estado='planejamento' WHERE id=:i"),
            {'i': obra.id})
        db.session.commit()
        db.session.refresh(obra)
        executar_handoff(obra, func, usuario_id=admin.id)
        db.session.commit()
        assert UsuarioObra.query.filter_by(
            obra_id=obra.id, usuario_id=UsuarioObra.query.filter_by(
                obra_id=obra.id).first().usuario_id).count() == 1


def test_dossie_handoff_traz_proposta_cliente_e_cronograma():
    from services.obra_handoff import dossie_handoff
    with app.app_context():
        admin = _admin()
        obra = _obra(admin)
        d = dossie_handoff(obra)
        assert d['obra']['codigo'] == obra.codigo
        assert d['cliente']['nome'] == obra.cliente_ref.nome
        assert d['cronograma']['revisado'] is True
        assert d['cronograma']['total_tarefas'] == 0
        assert d['proposta'] is None            # obra sem proposta de origem
        assert d['pode_entrar_em_execucao'] is True
        assert d['bloqueios'] == []
```

- [ ] **Step 2: Rode e veja falhar**

```bash
python -m pytest tests/test_fase2_handoff_gp.py -v 2>&1 | tail -20
```

Esperado: FAIL na coleção — `ModuleNotFoundError: No module named 'services.obra_handoff'`.

- [ ] **Step 3: Crie `services/obra_handoff.py`**

```python
"""Handoff do Gerente de Projeto — Fase 2.

O que existia antes: `Obra.responsavel_id` (models.py:258), uma FK para
`Funcionario` sem `relationship`, sem efeito em permissão, preenchida em
3 das 7.984 obras do banco. `DEVOLUTIVA.md:83` classifica o handoff como
"CONSTRUIR: sem estado, sem aceite, sem GP".

O handoff é uma transição PLANEJAMENTO → EM_EXECUCAO com três efeitos
colaterais indissociáveis, todos na mesma transação:

  1. `Obra.responsavel_id` = o Funcionario indicado;
  2. `UsuarioObra(usuario_do_GP, obra, GESTOR)` — a permissão de verdade,
     o que faz `services.obra_estado.pode_transitar_como` reconhecer o GP
     e o que a Fase 1 usa em `utils.autorizacao.obras_visiveis`;
  3. resolução do gate de cronograma (`Obra.cronograma_revisado_em`).

Nada aqui commita — quem chama é dono da transação.
"""
from __future__ import annotations

import logging
from datetime import datetime

logger = logging.getLogger('obra.handoff')


class HandoffInvalido(ValueError):
    """Pré-condição do handoff não satisfeita."""


def _cronograma_pendente(obra) -> bool:
    """Há revisão inicial de cronograma pendente para esta obra?

    Reusa `views.obras._precisa_revisao_cronograma_inicial` (Task #200,
    views/obras.py:2339) em vez de reimplementar os três critérios. Uma
    segunda cópia derivaria da primeira no primeiro ajuste, e o gate é
    exatamente o tipo de regra que não pode ter duas versões.

    Import tardio e dentro de try: `views.obras` importa blueprints, e
    este serviço também é chamado de migração/seed, onde eles podem não
    estar carregados. Falha de leitura → assume "nada pendente", que é o
    comportamento pré-Fase 2 (o handoff não existia e a obra entrava em
    execução de qualquer jeito).
    """
    if obra.cronograma_revisado_em is not None:
        return False
    try:
        from views.obras import _precisa_revisao_cronograma_inicial
        return bool(_precisa_revisao_cronograma_inicial(obra, obra.admin_id))
    except Exception:
        logger.warning('não foi possível avaliar o gate de cronograma da obra %s',
                       getattr(obra, 'id', '?'), exc_info=True)
        return False


def bloqueios_do_handoff(obra, funcionario=None) -> list[str]:
    """Lista legível de tudo que impede o handoff agora. Vazia = liberado."""
    from models import EstadoObra
    from services.obra_estado import estado_atual

    problemas: list[str] = []

    if estado_atual(obra) is not EstadoObra.PLANEJAMENTO:
        problemas.append(
            f'A obra está em "{estado_atual(obra).value}" — o handoff só '
            'acontece a partir de "planejamento".')

    if _cronograma_pendente(obra):
        problemas.append(
            'O cronograma inicial ainda não foi revisado. Revise em '
            'Cronograma → Revisão inicial antes de entregar a obra ao GP.')

    if funcionario is not None:
        if funcionario.admin_id != obra.admin_id:
            problemas.append(
                'O funcionário indicado pertence a outro tenant.')
        else:
            from utils.identidade import usuario_do_funcionario
            if usuario_do_funcionario(funcionario.id) is None:
                problemas.append(
                    f'{funcionario.nome} não tem login no sistema. Crie o '
                    'usuário e vincule ao funcionário antes do handoff.')

    return problemas


def dossie_handoff(obra) -> dict:
    """Pacote de contexto que o GP recebe junto com a obra.

    Serve à tela de handoff e ao payload do evento `obra.handoff`.
    Todos os lookups são defensivos: falta de proposta ou de cronograma
    não impede o dossiê de existir.
    """
    from models import TarefaCronograma

    cliente = getattr(obra, 'cliente_ref', None)

    proposta = None
    try:
        from views.obras import _proposta_origem_obra
        p = _proposta_origem_obra(obra, obra.admin_id)
        if p is not None:
            proposta = {
                'id': p.id,
                'numero': p.numero,
                'versao': getattr(p, 'versao', 1) or 1,
                'titulo': getattr(p, 'titulo', None),
                'valor_total': float(getattr(p, 'valor_total', 0) or 0),
            }
    except Exception:
        logger.warning('dossiê: proposta de origem não resolvida (obra %s)',
                       obra.id, exc_info=True)

    try:
        total_tarefas = (db_count := TarefaCronograma.query.filter_by(
            obra_id=obra.id, admin_id=obra.admin_id).count()) and db_count or 0
    except Exception:
        total_tarefas = 0

    bloqueios = bloqueios_do_handoff(obra)

    return {
        'obra': {
            'id': obra.id,
            'codigo': obra.codigo,
            'nome': obra.nome,
            'endereco': obra.endereco,
            'data_inicio': obra.data_inicio.isoformat() if obra.data_inicio else None,
            'data_previsao_fim': (obra.data_previsao_fim.isoformat()
                                  if obra.data_previsao_fim else None),
            'valor_contrato': float(obra.valor_contrato or 0),
            'area_total_m2': float(obra.area_total_m2 or 0),
            'estado': obra.estado,
        },
        'cliente': {
            'nome': getattr(cliente, 'nome', None),
            'email': getattr(cliente, 'email', None),
            'telefone': getattr(cliente, 'telefone', None),
        },
        'proposta': proposta,
        'cronograma': {
            'revisado': obra.cronograma_revisado_em is not None,
            'revisado_em': (obra.cronograma_revisado_em.isoformat()
                            if obra.cronograma_revisado_em else None),
            'total_tarefas': total_tarefas,
        },
        'bloqueios': bloqueios,
        'pode_entrar_em_execucao': not bloqueios,
    }


def executar_handoff(obra, funcionario, usuario_id=None, motivo: str = ''):
    """Entrega a obra ao GP. Devolve um dict com o que foi feito.

    Levanta `HandoffInvalido` para pré-condições de negócio e
    `services.obra_estado.TransicaoInvalida` quando a obra não está em
    PLANEJAMENTO — dois erros distintos de propósito: o primeiro o
    usuário conserta (crie o login, revise o cronograma), o segundo é
    estado errado.

    Não commita.
    """
    from models import EstadoObra, PapelObra, UsuarioObra, db
    from services.obra_estado import transitar
    from utils.identidade import usuario_do_funcionario

    if funcionario is None:
        raise HandoffInvalido('Indique o funcionário que será o Gerente de Projeto.')

    if funcionario.admin_id != obra.admin_id:
        raise HandoffInvalido(
            f'Funcionário {funcionario.id} é do tenant {funcionario.admin_id} '
            f'e a obra é do tenant {obra.admin_id} — handoff recusado.')

    usuario_gp = usuario_do_funcionario(funcionario.id)
    if usuario_gp is None:
        raise HandoffInvalido(
            f'{funcionario.nome} não tem login no sistema. Sem Usuario não há '
            'a quem atribuir o papel GESTOR da obra — crie o usuário e '
            'vincule ao funcionário antes do handoff.')

    if _cronograma_pendente(obra):
        raise HandoffInvalido(
            'O cronograma inicial desta obra ainda não foi revisado. '
            'Conclua a revisão antes de entregar a obra ao Gerente de Projeto.')

    # 1) responsável
    obra.responsavel_id = funcionario.id

    # 2) vínculo GESTOR — upsert, porque `usuario_obra` tem UNIQUE
    #    (usuario_id, obra_id) desde a Fase 1.
    vinculo = UsuarioObra.query.filter_by(
        usuario_id=usuario_gp.id, obra_id=obra.id).first()
    if vinculo is None:
        vinculo = UsuarioObra(
            usuario_id=usuario_gp.id, obra_id=obra.id,
            papel=PapelObra.GESTOR, admin_id=obra.admin_id, ativo=True)
        db.session.add(vinculo)
        vinculo_criado = True
    else:
        vinculo.papel = PapelObra.GESTOR
        vinculo.ativo = True
        vinculo_criado = False
    db.session.flush()

    # 3) gate de cronograma: aqui só chegamos se não há nada a revisar.
    #    Obra criada à mão nunca dispara o gate da Task #200 (não tem
    #    proposta de origem) e ficaria com o carimbo NULL para sempre.
    carimbado_agora = False
    if obra.cronograma_revisado_em is None:
        obra.cronograma_revisado_em = datetime.utcnow()
        carimbado_agora = True

    registro = transitar(
        obra, EstadoObra.EM_EXECUCAO, usuario_id=usuario_id, motivo=motivo,
        detalhes={
            'tipo': 'handoff',
            'funcionario_id': funcionario.id,
            'funcionario_nome': funcionario.nome,
            'usuario_gp_id': usuario_gp.id,
            'vinculo_criado': vinculo_criado,
            'cronograma_carimbado_no_handoff': carimbado_agora,
        },
    )

    logger.info(
        'evento=handoff obra_id=%s admin_id=%s funcionario_id=%s '
        'usuario_gp_id=%s vinculo_criado=%s cronograma_carimbado=%s',
        obra.id, obra.admin_id, funcionario.id, usuario_gp.id,
        vinculo_criado, carimbado_agora)

    return {
        'obra_id': obra.id,
        'funcionario_id': funcionario.id,
        'usuario_gp_id': usuario_gp.id,
        'vinculo_id': vinculo.id,
        'vinculo_criado': vinculo_criado,
        'cronograma_carimbado_no_handoff': carimbado_agora,
        'transicao_id': registro.id,
    }
```

- [ ] **Step 4: Rode os testes**

```bash
python -m pytest tests/test_fase2_handoff_gp.py -v 2>&1 | tail -20
```

Esperado: os 7 testes PASSAM.

- [ ] **Step 5: Commit**

```bash
git add services/obra_handoff.py tests/test_fase2_handoff_gp.py
git commit -m "feat(fase2): handoff do GP cria o vinculo UsuarioObra GESTOR

Entregar a obra passa a ser um ato com tres efeitos indissociaveis:
responsavel_id, UsuarioObra(GESTOR) e resolucao do gate de cronograma.
Recusa GP sem login: sem Usuario nao ha a quem dar o papel, e handoff
sem vinculo e so um campo preenchido — que e o que existe hoje."
```

---

## Task 8: Rotas de transição e de handoff

**Files:**
- Modify: `views/obras.py` (acrescentar ao fim do arquivo)
- Test: `tests/test_fase2_handoff_gp.py`

- [ ] **Step 1: Escreva o teste que falha**

Acrescente ao fim de `tests/test_fase2_handoff_gp.py`:

```python
def _cliente_logado(user_id):
    """Login por injeção de sessão — padrão do repo
    (tests/test_fase0_autorizacao.py:55-60). O test_client é criado FORA
    de qualquer app_context aberto."""
    c = app.test_client()
    with c.session_transaction() as sess:
        sess['_user_id'] = str(user_id)
        sess['_fresh'] = True
    return c


def test_rota_estado_recusa_transicao_invalida_com_400():
    with app.app_context():
        admin = _admin()
        obra = _obra(admin, estado='planejamento')
        obra_id, admin_id = obra.id, admin.id
    c = _cliente_logado(admin_id)
    r = c.post(f'/obras/{obra_id}/estado',
               data={'estado': 'concluida'}, follow_redirects=False)
    assert r.status_code == 400, f'devolveu {r.status_code}'
    with app.app_context():
        from models import Obra
        assert db.session.get(Obra, obra_id).estado == 'planejamento'


def test_rota_estado_recusa_falta_de_motivo_com_400():
    with app.app_context():
        admin = _admin()
        obra = _obra(admin, estado='em_execucao', status='Em andamento')
        obra_id, admin_id = obra.id, admin.id
    c = _cliente_logado(admin_id)
    r = c.post(f'/obras/{obra_id}/estado', data={'estado': 'pausada'})
    assert r.status_code == 400


def test_rota_estado_aplica_transicao_valida():
    with app.app_context():
        admin = _admin()
        obra = _obra(admin, estado='em_execucao', status='Em andamento')
        obra_id, admin_id = obra.id, admin.id
    c = _cliente_logado(admin_id)
    r = c.post(f'/obras/{obra_id}/estado',
               data={'estado': 'pausada', 'motivo': 'Chuva 12 dias'},
               follow_redirects=False)
    assert r.status_code in (302, 303)
    with app.app_context():
        from models import Obra, ObraTransicaoEstado
        o = db.session.get(Obra, obra_id)
        assert o.estado == 'pausada'
        assert o.status == 'Pausada'
        t = ObraTransicaoEstado.query.filter_by(
            obra_id=obra_id, estado_para='pausada').one()
        assert t.motivo == 'Chuva 12 dias'
        assert t.usuario_id == admin_id


def test_rota_estado_de_outro_tenant_devolve_404():
    with app.app_context():
        dono = _admin()
        intruso = _admin('f2z')
        obra = _obra(dono, estado='em_execucao', status='Em andamento')
        obra_id, intruso_id = obra.id, intruso.id
    c = _cliente_logado(intruso_id)
    r = c.post(f'/obras/{obra_id}/estado',
               data={'estado': 'pausada', 'motivo': 'x'})
    assert r.status_code == 404


def test_rota_estado_exige_login():
    with app.app_context():
        admin = _admin()
        obra = _obra(admin, estado='em_execucao', status='Em andamento')
        obra_id = obra.id
    anon = app.test_client()
    r = anon.post(f'/obras/{obra_id}/estado',
                  data={'estado': 'pausada', 'motivo': 'x'},
                  follow_redirects=False)
    assert r.status_code in (302, 401, 403)


def test_rota_handoff_get_devolve_dossie_json():
    with app.app_context():
        admin = _admin()
        obra = _obra(admin)
        _funcionario(admin)
        obra_id, admin_id = obra.id, admin.id
    c = _cliente_logado(admin_id)
    r = c.get(f'/obras/{obra_id}/handoff', headers={'Accept': 'application/json'})
    assert r.status_code == 200
    dados = r.get_json()
    assert dados['obra']['id'] == obra_id
    assert dados['pode_entrar_em_execucao'] is True
    assert isinstance(dados['candidatos'], list)


def test_rota_handoff_post_entrega_a_obra():
    with app.app_context():
        admin = _admin()
        obra = _obra(admin)
        func = _funcionario(admin)
        obra_id, admin_id, func_id = obra.id, admin.id, func.id
    c = _cliente_logado(admin_id)
    r = c.post(f'/obras/{obra_id}/handoff',
               data={'responsavel_id': str(func_id), 'motivo': 'Kickoff'},
               follow_redirects=False)
    assert r.status_code in (302, 303)
    with app.app_context():
        from models import Obra, PapelObra, UsuarioObra
        o = db.session.get(Obra, obra_id)
        assert o.estado == 'em_execucao'
        assert o.responsavel_id == func_id
        assert UsuarioObra.query.filter_by(
            obra_id=obra_id, papel=PapelObra.GESTOR, ativo=True).count() == 1


def test_rota_handoff_post_com_gp_sem_login_devolve_400():
    with app.app_context():
        admin = _admin()
        obra = _obra(admin)
        func = _funcionario(admin, com_login=False)
        obra_id, admin_id, func_id = obra.id, admin.id, func.id
    c = _cliente_logado(admin_id)
    r = c.post(f'/obras/{obra_id}/handoff',
               data={'responsavel_id': str(func_id)})
    assert r.status_code == 400
    with app.app_context():
        from models import Obra
        assert db.session.get(Obra, obra_id).estado == 'planejamento'
```

- [ ] **Step 2: Rode e veja falhar**

```bash
python -m pytest tests/test_fase2_handoff_gp.py -k rota -v 2>&1 | tail -20
```

Esperado: FAIL — todas as rotas devolvem 404 (não existem).

- [ ] **Step 3: Acrescente as rotas ao fim de `views/obras.py`**

```python
# ────────────────────────────────────────────────────────────────────
# Fase 2 — máquina de estados da Obra e handoff do GP
#
# Antes daqui, mudar o estado de uma obra era escrever texto livre em
# `obra.status` pelo formulário de edição (views/obras.py:863) ou flipar
# `obra.ativo` num toggle (views/obras.py:1259). Nenhum dos dois
# validava transição nem registrava quem mudou.
#
# Estas duas rotas passam a ser o ÚNICO caminho HTTP de mudança de
# estado. Devolvem 404 (não 403) para obra fora do alcance, mesma
# escolha da Fase 1 em utils/autorizacao.obra_required — não vazar a
# existência de obra de outro tenant.
# ────────────────────────────────────────────────────────────────────

def _quer_json():
    return (request.path.startswith('/api/')
            or request.accept_mimetypes.best == 'application/json')


@main_bp.route('/obras/<int:id>/estado', methods=['POST'])
@login_required
def alterar_estado_obra(id):
    """Aplica uma transição de estado validada.

    Form: `estado` (o `.value` do EstadoObra) e `motivo` (texto).
    """
    from models import EstadoObra  # noqa: F401 — usado via coagir
    from services.obra_estado import (
        EstadoDesconhecido, TransicaoInvalida, coagir, pode_transitar_como,
        transitar,
    )

    admin_id = get_tenant_admin_id()
    obra = Obra.query.filter_by(id=id, admin_id=admin_id).first() if admin_id else None
    if obra is None:
        if _quer_json():
            return jsonify({'erro': 'Obra não encontrada'}), 404
        return 'Obra não encontrada', 404

    try:
        destino = coagir(request.form.get('estado'))
    except EstadoDesconhecido as e:
        if _quer_json():
            return jsonify({'erro': str(e)}), 400
        flash(f'Estado inválido: {request.form.get("estado")!r}', 'error')
        return redirect(url_for('main.detalhes_obra', id=obra.id)), 400

    if not pode_transitar_como(obra, destino, current_user):
        # Distinguimos "não pode" de "não existe" só no log — a resposta
        # é 403, porque o usuário JÁ provou alcançar a obra (o filtro de
        # tenant acima passou).
        logger.warning(
            'transicao negada obra_id=%s usuario_id=%s de=%s para=%s',
            obra.id, getattr(current_user, 'id', None), obra.estado,
            destino.value)
        if _quer_json():
            return jsonify({'erro': 'Sem permissão para esta transição'}), 403
        flash('Você não tem permissão para esta mudança de estado.', 'error')
        return redirect(url_for('main.detalhes_obra', id=obra.id)), 403

    motivo = (request.form.get('motivo') or '').strip()
    estado_anterior = obra.estado
    try:
        registro = transitar(obra, destino, usuario_id=current_user.id,
                             motivo=motivo, detalhes={'origem': 'ui'})
        db.session.commit()
    except TransicaoInvalida as e:
        db.session.rollback()
        if _quer_json():
            return jsonify({'erro': str(e)}), 400
        flash(str(e), 'error')
        return redirect(url_for('main.detalhes_obra', id=obra.id)), 400
    except Exception as e:
        db.session.rollback()
        logger.error('falha ao transitar obra %s: %s', obra.id, e, exc_info=True)
        if _quer_json():
            return jsonify({'erro': 'Falha ao alterar o estado da obra'}), 500
        flash(f'Erro ao alterar o estado da obra: {e}', 'error')
        return redirect(url_for('main.detalhes_obra', id=obra.id)), 500

    _notificar_transicao(obra, estado_anterior, destino, motivo, registro)

    if _quer_json():
        return jsonify({
            'ok': True, 'estado': obra.estado, 'status': obra.status,
            'ativo': obra.ativo, 'transicao_id': registro.id,
        })
    flash(f'Obra "{obra.nome}" agora está em {obra.status}.', 'success')
    return redirect(url_for('main.detalhes_obra', id=obra.id))


@main_bp.route('/obras/<int:id>/handoff', methods=['GET'])
@login_required
def handoff_obra_get(id):
    """Dossiê de handoff + lista de candidatos a GP.

    Candidato = `Funcionario` ativo do tenant QUE TEM LOGIN. Filtrar aqui
    evita oferecer no select alguém que `executar_handoff` vai recusar.
    """
    from models import Usuario
    from services.obra_handoff import dossie_handoff

    admin_id = get_tenant_admin_id()
    obra = Obra.query.filter_by(id=id, admin_id=admin_id).first() if admin_id else None
    if obra is None:
        if _quer_json():
            return jsonify({'erro': 'Obra não encontrada'}), 404
        return 'Obra não encontrada', 404

    candidatos = (
        db.session.query(Funcionario.id, Funcionario.nome, Funcionario.codigo)
        .join(Usuario, Usuario.funcionario_id == Funcionario.id)
        .filter(Funcionario.admin_id == admin_id,
                Funcionario.ativo.is_(True),
                Usuario.ativo.is_(True))
        .order_by(Funcionario.nome)
        .all()
    )
    dossie = dossie_handoff(obra)
    dossie['candidatos'] = [
        {'id': c.id, 'nome': c.nome, 'codigo': c.codigo} for c in candidatos]

    if _quer_json():
        return jsonify(dossie)
    return render_template('obras/handoff.html', obra=obra, dossie=dossie)


@main_bp.route('/obras/<int:id>/handoff', methods=['POST'])
@login_required
def handoff_obra_post(id):
    """Executa o handoff: responsável + UsuarioObra(GESTOR) + EM_EXECUCAO."""
    from models import EstadoObra
    from services.obra_estado import TransicaoInvalida, pode_transitar_como
    from services.obra_handoff import HandoffInvalido, executar_handoff

    admin_id = get_tenant_admin_id()
    obra = Obra.query.filter_by(id=id, admin_id=admin_id).first() if admin_id else None
    if obra is None:
        if _quer_json():
            return jsonify({'erro': 'Obra não encontrada'}), 404
        return 'Obra não encontrada', 404

    if not pode_transitar_como(obra, EstadoObra.EM_EXECUCAO, current_user):
        if _quer_json():
            return jsonify({'erro': 'Sem permissão para entregar esta obra'}), 403
        flash('Somente o administrador do tenant faz o handoff da obra.', 'error')
        return redirect(url_for('main.detalhes_obra', id=obra.id)), 403

    try:
        responsavel_id = int(request.form.get('responsavel_id') or 0)
    except (TypeError, ValueError):
        responsavel_id = 0
    funcionario = Funcionario.query.filter_by(
        id=responsavel_id, admin_id=admin_id).first() if responsavel_id else None
    if funcionario is None:
        if _quer_json():
            return jsonify({'erro': 'Selecione o Gerente de Projeto'}), 400
        flash('Selecione o Gerente de Projeto responsável pela obra.', 'error')
        return redirect(url_for('main.handoff_obra_get', id=obra.id)), 400

    motivo = (request.form.get('motivo') or '').strip()
    estado_anterior = obra.estado
    try:
        resultado = executar_handoff(obra, funcionario,
                                     usuario_id=current_user.id, motivo=motivo)
        db.session.commit()
    except (HandoffInvalido, TransicaoInvalida) as e:
        db.session.rollback()
        if _quer_json():
            return jsonify({'erro': str(e)}), 400
        flash(str(e), 'error')
        return redirect(url_for('main.handoff_obra_get', id=obra.id)), 400
    except Exception as e:
        db.session.rollback()
        logger.error('handoff falhou obra %s: %s', obra.id, e, exc_info=True)
        if _quer_json():
            return jsonify({'erro': 'Falha ao executar o handoff'}), 500
        flash(f'Erro no handoff: {e}', 'error')
        return redirect(url_for('main.handoff_obra_get', id=obra.id)), 500

    _notificar_handoff(obra, funcionario, resultado, estado_anterior)

    if _quer_json():
        return jsonify({'ok': True, **resultado})
    flash(f'Obra entregue a {funcionario.nome}. A obra está em execução.',
          'success')
    return redirect(url_for('main.detalhes_obra', id=obra.id))
```

> `_notificar_transicao` e `_notificar_handoff` são criadas na Task 10. Até lá as rotas quebram no `NameError` — por isso a Task 10 vem antes de rodar a suíte inteira. Para rodar os testes desta task agora, adicione **provisoriamente** os dois stubs abaixo logo acima de `alterar_estado_obra`; a Task 10 os substitui pela implementação real:
>
> ```python
> def _notificar_transicao(obra, estado_anterior, destino, motivo, registro):
>     return None  # implementado na Task 10
>
>
> def _notificar_handoff(obra, funcionario, resultado, estado_anterior):
>     return None  # implementado na Task 10
> ```

- [ ] **Step 4: Rode os testes**

```bash
python -m pytest tests/test_fase2_handoff_gp.py -v 2>&1 | tail -20
```

Esperado: os 15 testes PASSAM.

- [ ] **Step 5: Commit**

```bash
git add views/obras.py tests/test_fase2_handoff_gp.py
git commit -m "feat(fase2): rotas POST /obras/<id>/estado e /obras/<id>/handoff

Unico caminho HTTP de mudanca de estado. 404 para obra de outro tenant
(nao vazar existencia), 403 para quem alcanca mas nao pode, 400 para
transicao invalida ou motivo faltando."
```

---

## Task 9: A obra nasce em `PLANEJAMENTO` (cascata da proposta e criação manual)

> ### 🔴 Achado B da revisão de 22/07 — esta task quebra o dashboard se não for corrigida
>
> Fazer a obra nascer com `status='Planejamento'` a torna **invisível** nos
> quatro filtros do dashboard, que fazem
> `Obra.status.in_(['ATIVO', 'andamento', 'Em andamento', 'ativa', 'planejamento'])`
> — `'planejamento'` **minúsculo**, e `IN` no Postgres é case-sensitive.
> Confirmado por query: `'Planejamento' IN (...)` → `False`.
>
> Efeito sem a correção: toda obra nova vinda de proposta aprovada some dos
> contadores de obras ativas e da tabela "obras em andamento". O bug é latente
> hoje (o `<select>` de `obras_moderno.html:619` já oferece
> `value="Planejamento"`, mas nenhuma obra usa o valor); esta task o tornaria
> universal.
>
> **A correção faz parte desta task, não é opcional.** E a correção certa não é
> acrescentar `'Planejamento'` à lista de strings: é filtrar por `Obra.estado`,
> que existe desde a Task 3 e é a fonte de verdade. Isso ainda mata a lista
> defensiva `['ATIVO', 'ativa']`, cujos valores não existem em nenhuma linha do
> banco.

**Files:**
- Modify: `event_manager.py:1010-1026` (dentro de `propagar_proposta_para_obra`)
- Modify: `views/obras.py:383-403` (`nova_obra`)
- Modify: `views/dashboard.py:429`, `:1014`, `:1036`, `:1055` (filtros → `Obra.estado`)
- Test: `tests/test_fase2_handoff_gp.py`

- [ ] **Step 1: Escreva o teste que falha**

Acrescente ao fim de `tests/test_fase2_handoff_gp.py`:

```python
def test_obra_criada_pela_cascata_da_proposta_nasce_em_planejamento():
    """A ordem de import de app.py é contrato: `import event_manager`
    (app.py:414) registra `propagar_proposta_para_obra`, que CRIA a obra;
    `import handlers.propostas_handlers` (app.py:426) registra o handler
    que roda depois. Esta fase escreve o estado inicial DENTRO do handler
    existente, sem registrar handler novo — um handler novo mudaria a
    ordem da lista de `EventManager._handlers` (event_manager.py:17)."""
    from datetime import date as _date

    from event_manager import propagar_proposta_para_obra
    from models import Obra, ObraTransicaoEstado, Proposta
    with app.app_context():
        admin = _admin()
        suf = uuid.uuid4().hex[:8]
        prop = Proposta(
            numero=f'PROP-{suf}', cliente_nome=f'Cliente {suf}',
            cliente_email=f'c_{suf}@test.local', titulo=f'Casa {suf}',
            valor_total=250000.0, admin_id=admin.id, status='RASCUNHO',
            data_proposta=_date(2026, 7, 1),
        )
        db.session.add(prop)
        db.session.commit()

        propagar_proposta_para_obra({'proposta_id': prop.id}, admin.id)
        db.session.commit()

        obra = Obra.query.filter_by(proposta_origem_id=prop.id).one()
        assert obra.estado == 'planejamento'
        assert obra.status == 'Planejamento'
        assert obra.ativo is True
        linha = ObraTransicaoEstado.query.filter_by(obra_id=obra.id).one()
        assert linha.estado_de is None
        assert linha.estado_para == 'planejamento'
        assert linha.detalhes['origem'] == 'proposta_aprovada'
        assert linha.detalhes['proposta_id'] == prop.id


def test_cascata_nao_reescreve_estado_de_obra_ja_existente():
    """Aprovar a revisão v2 de uma proposta reconcilia com a obra da v1
    (Fase 0 / R1, event_manager.py:945-975). Isso NÃO pode devolver uma
    obra em execução para planejamento."""
    from datetime import date as _date

    from event_manager import propagar_proposta_para_obra
    from models import Obra, Proposta
    with app.app_context():
        admin = _admin()
        obra = _obra(admin, estado='em_execucao', status='Em andamento')
        suf = uuid.uuid4().hex[:8]
        prop = Proposta(
            numero=f'PROP-{suf}', cliente_nome=f'Cliente {suf}',
            titulo=f'Aditivo {suf}', valor_total=300000.0,
            admin_id=admin.id, status='RASCUNHO', obra_id=obra.id,
            data_proposta=_date(2026, 7, 1),
        )
        db.session.add(prop)
        db.session.commit()

        propagar_proposta_para_obra({'proposta_id': prop.id}, admin.id)
        db.session.commit()
        db.session.refresh(obra)
        assert obra.estado == 'em_execucao'


def test_nova_obra_sem_responsavel_nasce_em_planejamento():
    with app.app_context():
        admin = _admin()
        admin_id = admin.id
    c = _cliente_logado(admin_id)
    suf = uuid.uuid4().hex[:8]
    r = c.post('/obras/nova', data={
        'nome': f'Obra manual {suf}', 'codigo': f'M{suf[:7].upper()}',
        'data_inicio': '2026-07-01', 'cliente_busca': f'Cliente {suf}',
        'ativo': 'on',
    }, follow_redirects=False)
    assert r.status_code in (302, 303)
    with app.app_context():
        from models import Obra
        o = Obra.query.filter_by(admin_id=admin_id,
                                 nome=f'Obra manual {suf}').one()
        assert o.estado == 'planejamento'


def test_nova_obra_com_responsavel_ja_faz_o_handoff():
    """Preservar a ergonomia atual: quem preenche o responsável na
    criação não deve precisar de um segundo passo — mas o histórico e o
    UsuarioObra são criados igual."""
    with app.app_context():
        admin = _admin()
        func = _funcionario(admin)
        admin_id, func_id = admin.id, func.id
    c = _cliente_logado(admin_id)
    suf = uuid.uuid4().hex[:8]
    r = c.post('/obras/nova', data={
        'nome': f'Obra com GP {suf}', 'codigo': f'G{suf[:7].upper()}',
        'data_inicio': '2026-07-01', 'cliente_busca': f'Cliente {suf}',
        'responsavel_id': str(func_id), 'ativo': 'on',
    }, follow_redirects=False)
    assert r.status_code in (302, 303)
    with app.app_context():
        from models import Obra, ObraTransicaoEstado, PapelObra, UsuarioObra
        o = Obra.query.filter_by(admin_id=admin_id,
                                 nome=f'Obra com GP {suf}').one()
        assert o.estado == 'em_execucao'
        assert o.responsavel_id == func_id
        assert UsuarioObra.query.filter_by(
            obra_id=o.id, papel=PapelObra.GESTOR, ativo=True).count() == 1
        assert ObraTransicaoEstado.query.filter_by(
            obra_id=o.id, estado_para='em_execucao').count() == 1
```

- [ ] **Step 2: Rode e veja falhar**

```bash
python -m pytest tests/test_fase2_handoff_gp.py -k "cascata or nova_obra" -v 2>&1 | tail -20
```

Esperado: FAIL — `assert 'em_execucao' == 'planejamento'` (a obra ainda nasce `'Em andamento'`).

- [ ] **Step 3: Ajuste a cascata em `event_manager.py`**

Em `event_manager.py`, no bloco que constrói a `Obra` (`event_manager.py:1010-1026`), troque a linha `status='Em andamento',` por:

```python
            # Fase 2 — a obra nasce em PLANEJAMENTO, não em execução.
            # Antes: `status='Em andamento'` — a obra entrava em execução
            # no instante da aprovação, sem GP, sem aceite e sem
            # cronograma revisado. O `status` continua sendo escrito (é o
            # espelho legado lido por ~40 templates/queries), agora
            # derivado do estado por services.obra_estado.ROTULOS.
            status=_ROTULOS_ESTADO[_EstadoObra.PLANEJAMENTO],
            estado=_EstadoObra.PLANEJAMENTO.value,
```

E, logo depois do `db.session.flush()` que sucede o `db.session.add(obra)` (`event_manager.py:1028-1029`), acrescente a linha de histórico:

```python
        # Fase 2 — primeira linha do histórico de estado. `estado_de` é
        # NULL porque a obra não veio de estado nenhum: ela nasceu.
        #
        # Escrito AQUI, dentro deste handler, e não num handler novo:
        # `EventManager._handlers` é uma lista percorrida na ordem de
        # registro (event_manager.py:17,44), e a ordem de registro é a
        # ordem dos imports em app.py:414 e app.py:426. Registrar mais um
        # handler para `proposta_aprovada` acrescentaria uma terceira
        # dependência de ordem a um contrato que já não é declarado.
        from models import ObraTransicaoEstado as _OTE
        db.session.add(_OTE(
            obra_id=obra.id, admin_id=admin_id,
            estado_de=None, estado_para=_EstadoObra.PLANEJAMENTO.value,
            motivo='Obra criada pela aprovação da proposta',
            detalhes={'origem': 'proposta_aprovada',
                      'proposta_id': proposta_id,
                      'proposta_numero': proposta.numero},
            usuario_id=None,
        ))
        db.session.flush()
```

No topo de `propagar_proposta_para_obra`, junto do `from models import db, Proposta, Obra` (`event_manager.py:890`), acrescente:

```python
    from models import EstadoObra as _EstadoObra
    from services.obra_estado import ROTULOS as _ROTULOS_ESTADO
```

> O ramo `else` do mesmo handler (obra já existente, `event_manager.py:1032-1057`) **não** toca em estado — é o caminho da revisão/aditivo, e o teste `test_cascata_nao_reescreve_estado_de_obra_ja_existente` trava isso.

- [ ] **Step 4: Ajuste `nova_obra` em `views/obras.py`**

Em `views/obras.py:279`, troque:

```python
            status = request.form.get('status', 'Em andamento')
```

por:

```python
            # Fase 2 — o formulário não escolhe mais o estado. Toda obra
            # nasce em PLANEJAMENTO e sai de lá pelo handoff; o campo
            # `status` do form virou badge somente-leitura no template.
            from models import EstadoObra as _EstadoObra
            from services.obra_estado import ROTULOS as _ROTULOS_ESTADO
            status = _ROTULOS_ESTADO[_EstadoObra.PLANEJAMENTO]
```

Em `views/obras.py:393` (dentro do construtor `Obra(...)`), logo abaixo de `status=status,`, acrescente:

```python
                estado=_EstadoObra.PLANEJAMENTO.value,
```

E, entre `db.session.flush()` (`views/obras.py:406`) e o processamento de serviços (`views/obras.py:410`), insira:

```python
            # Fase 2 — primeira linha do histórico.
            from models import ObraTransicaoEstado as _OTE
            db.session.add(_OTE(
                obra_id=nova_obra.id, admin_id=admin_id,
                estado_de=None, estado_para=_EstadoObra.PLANEJAMENTO.value,
                motivo='Obra criada manualmente',
                detalhes={'origem': 'nova_obra'},
                usuario_id=current_user.id,
            ))
            db.session.flush()

            # Fase 2 — atalho de ergonomia: quem já indicou o responsável
            # no formulário não precisa de um segundo passo. O handoff
            # roda na MESMA transação, com histórico e UsuarioObra iguais
            # aos do fluxo em duas etapas. Se o funcionário não tiver
            # login, a obra é criada mesmo assim e fica em PLANEJAMENTO —
            # criar a obra não pode falhar por causa do handoff.
            if responsavel_id:
                from services.obra_handoff import (
                    HandoffInvalido, executar_handoff,
                )
                _func = Funcionario.query.filter_by(
                    id=responsavel_id, admin_id=admin_id).first()
                if _func is not None:
                    try:
                        executar_handoff(
                            nova_obra, _func, usuario_id=current_user.id,
                            motivo='Handoff automático na criação da obra')
                    except HandoffInvalido as _e_hand:
                        logger.info(
                            'Fase 2: obra %s criada sem handoff automático: %s',
                            nova_obra.id, _e_hand)
                        flash(f'Obra criada em Planejamento — {_e_hand}', 'warning')
```

> `responsavel_id` já é lido do formulário em `views/obras.py:280`. Ele chega como string; o `filter_by(id=responsavel_id)` funciona no Postgres, mas para clareza deixe a leitura como está — a query já filtra por `admin_id`, então id inválido devolve `None`.

- [ ] **Step 5: Rode os testes**

```bash
python -m pytest tests/test_fase2_handoff_gp.py -v 2>&1 | tail -20
python -m pytest tests/test_propagacao_proposta_obra.py tests/test_cronograma_revisao_obra_gate.py -v 2>&1 | tail -20
```

Esperado: 19 testes do arquivo da Fase 2 PASSAM; as duas suítes de regressão da cascata continuam verdes.

- [ ] **Step 6: Commit**

```bash
git add event_manager.py views/obras.py tests/test_fase2_handoff_gp.py
git commit -m "feat(fase2): obra nasce em PLANEJAMENTO, com linha de historico

Estado inicial escrito DENTRO de propagar_proposta_para_obra, sem
registrar handler novo: EventManager._handlers e uma lista percorrida na
ordem dos imports de app.py:414/426, e mais um handler seria mais uma
dependencia de ordem num contrato ja nao declarado. Criacao manual com
responsavel preenchido faz o handoff na mesma transacao."
```

---

## Task 10: Eventos de catálogo `obra.estado_alterado` e `obra.handoff`

**Files:**
- Modify: `utils/catalogo_eventos.py` (ao fim do arquivo, após `emit_obra_concluida` em `utils/catalogo_eventos.py:289-297`)
- Modify: `utils/webhook_dispatcher.py:59-71` (allowlist)
- Modify: `views/obras.py` (substituir os stubs `_notificar_*` da Task 8)
- Test: `tests/test_fase2_handoff_gp.py`

- [ ] **Step 1: Escreva o teste que falha**

Acrescente ao fim de `tests/test_fase2_handoff_gp.py`:

```python
def test_eventos_novos_estao_na_allowlist_do_webhook():
    from utils.webhook_dispatcher import WEBHOOK_EVENT_ALLOWLIST
    assert 'obra.estado_alterado' in WEBHOOK_EVENT_ALLOWLIST
    assert 'obra.handoff' in WEBHOOK_EVENT_ALLOWLIST


def test_emit_obra_estado_alterado_monta_payload_completo():
    from unittest.mock import patch

    from utils import catalogo_eventos
    with app.app_context():
        admin = _admin()
        obra = _obra(admin, estado='pausada', status='Pausada')
        with patch.object(catalogo_eventos, '_safe_emit') as m:
            catalogo_eventos.emit_obra_estado_alterado(
                obra, admin.id, estado_de='em_execucao',
                estado_para='pausada', motivo='Chuva', usuario_id=admin.id)
        assert m.called
        nome, payload, aid = m.call_args.args
        assert nome == 'obra.estado_alterado'
        assert aid == admin.id
        assert payload['obra_id'] == obra.id
        assert payload['estado_de'] == 'em_execucao'
        assert payload['estado_para'] == 'pausada'
        assert payload['estado_para_rotulo'] == 'Pausada'
        assert payload['motivo'] == 'Chuva'


def test_emit_obra_handoff_monta_payload_com_gp_e_dossie():
    from unittest.mock import patch

    from utils import catalogo_eventos
    with app.app_context():
        admin = _admin()
        obra = _obra(admin, estado='em_execucao', status='Em andamento')
        func = _funcionario(admin)
        with patch.object(catalogo_eventos, '_safe_emit') as m:
            catalogo_eventos.emit_obra_handoff(
                obra, admin.id, funcionario=func, usuario_gp_id=1,
                entregue_por_id=admin.id)
        nome, payload, _aid = m.call_args.args
        assert nome == 'obra.handoff'
        assert payload['gerente_projeto']['funcionario_id'] == func.id
        assert payload['gerente_projeto']['nome'] == func.nome
        assert payload['dossie']['obra']['id'] == obra.id


def test_emit_nunca_propaga_excecao():
    """Contrato do catálogo (utils/catalogo_eventos.py:110-119): webhook é
    best-effort e jamais quebra a transação de negócio."""
    from unittest.mock import patch

    from utils import catalogo_eventos
    with app.app_context():
        admin = _admin()
        obra = _obra(admin)
        with patch('event_manager.EventManager.emit',
                   side_effect=RuntimeError('n8n fora do ar')):
            catalogo_eventos.emit_obra_estado_alterado(
                obra, admin.id, estado_de='planejamento',
                estado_para='em_execucao', motivo='', usuario_id=admin.id)
```

- [ ] **Step 2: Rode e veja falhar**

```bash
python -m pytest tests/test_fase2_handoff_gp.py -k "allowlist or emit" -v 2>&1 | tail -20
```

Esperado: FAIL — `AssertionError: 'obra.estado_alterado' not in ...` e `AttributeError: module 'utils.catalogo_eventos' has no attribute 'emit_obra_estado_alterado'`.

- [ ] **Step 3: Acrescente os emissores em `utils/catalogo_eventos.py`**

Ao fim de `utils/catalogo_eventos.py` (depois de `emit_obra_concluida`, `utils/catalogo_eventos.py:297`), adicione:

```python
def emit_obra_estado_alterado(obra, admin_id: int | None, *, estado_de: str,
                              estado_para: str, motivo: str = '',
                              usuario_id: int | None = None) -> None:
    """Emite `obra.estado_alterado` a cada transição da máquina (Fase 2).

    Complementa — não substitui — `emit_obra_concluida`. A conclusão
    continua tendo evento próprio porque o consumidor n8n dela já existe
    (utils/webhook_dispatcher.py:70) e é um marco de negócio, não uma
    mudança qualquer de estado.
    """
    from services.obra_estado import ROTULOS, coagir

    payload = _payload_obra_basico(obra)

    def _rotulo(valor):
        try:
            return ROTULOS[coagir(valor)]
        except Exception:
            return valor

    payload.update({
        'estado_de': estado_de,
        'estado_de_rotulo': _rotulo(estado_de) if estado_de else None,
        'estado_para': estado_para,
        'estado_para_rotulo': _rotulo(estado_para),
        'motivo': (motivo or '')[:500],
        'usuario_id': usuario_id,
        'data_transicao': datetime.utcnow().strftime('%Y-%m-%dT%H:%M:%SZ'),
    })
    _safe_emit('obra.estado_alterado', payload, admin_id)


def emit_obra_handoff(obra, admin_id: int | None, *, funcionario,
                      usuario_gp_id: int | None,
                      entregue_por_id: int | None = None) -> None:
    """Emite `obra.handoff` — o gatilho de "avisar o GP" da Fase 2.

    Carrega o dossiê inteiro no payload para que o n8n monte a mensagem
    (e-mail/WhatsApp) sem um segundo round-trip, mesma escolha de
    `emit_obra_rdo_publicado` (utils/catalogo_eventos.py:242-259).
    """
    payload = _payload_obra_basico(obra)
    dossie = {}
    try:
        from services.obra_handoff import dossie_handoff
        dossie = dossie_handoff(obra)
    except Exception:
        logger.exception('[catalogo_eventos] dossiê de handoff falhou (obra %s)',
                         getattr(obra, 'id', None))
    payload.update({
        'gerente_projeto': {
            'funcionario_id': getattr(funcionario, 'id', None),
            'nome': getattr(funcionario, 'nome', None),
            'email': getattr(funcionario, 'email', None),
            'telefone': getattr(funcionario, 'telefone', None),
            'usuario_id': usuario_gp_id,
        },
        'entregue_por_id': entregue_por_id,
        'data_handoff': datetime.utcnow().strftime('%Y-%m-%dT%H:%M:%SZ'),
        'dossie': dossie,
    })
    _safe_emit('obra.handoff', payload, admin_id)
```

- [ ] **Step 4: Acrescente os dois eventos à allowlist**

Em `utils/webhook_dispatcher.py`, dentro de `WEBHOOK_EVENT_ALLOWLIST` (`utils/webhook_dispatcher.py:59-71`), logo depois de `"obra.concluida",`:

```python
    # — Obras / Fase 2: máquina de estados e handoff do GP —
    "obra.estado_alterado",
    "obra.handoff",
```

- [ ] **Step 5: Substitua os stubs em `views/obras.py`**

Troque os dois stubs `_notificar_transicao` / `_notificar_handoff` da Task 8 por:

```python
def _notificar_transicao(obra, estado_anterior, destino, motivo, registro):
    """Dispara os eventos de catálogo de uma transição — best-effort.

    Substitui a detecção de conclusão por comparação de string que vivia
    em `views/obras.py:963-979`, feita DEPOIS do commit e sujeita a
    grafia ('Concluída'/'Concluida'/'CONCLUÍDA'). Agora a conclusão é um
    fato da máquina, não uma inferência de texto.
    """
    from models import EstadoObra
    try:
        from utils.catalogo_eventos import (
            emit_obra_concluida, emit_obra_estado_alterado,
        )
        emit_obra_estado_alterado(
            obra, obra.admin_id, estado_de=estado_anterior,
            estado_para=destino.value, motivo=motivo,
            usuario_id=getattr(current_user, 'id', None))
        if destino is EstadoObra.CONCLUIDA:
            emit_obra_concluida(obra, obra.admin_id)
    except Exception as e:
        logger.warning('Fase 2: emissão de evento de transição falhou '
                       '(best-effort): %s', e)


def _notificar_handoff(obra, funcionario, resultado, estado_anterior):
    """Dispara `obra.handoff` e `obra.estado_alterado` — best-effort."""
    try:
        from utils.catalogo_eventos import (
            emit_obra_estado_alterado, emit_obra_handoff,
        )
        emit_obra_estado_alterado(
            obra, obra.admin_id, estado_de=estado_anterior,
            estado_para=obra.estado, motivo='handoff',
            usuario_id=getattr(current_user, 'id', None))
        emit_obra_handoff(
            obra, obra.admin_id, funcionario=funcionario,
            usuario_gp_id=resultado.get('usuario_gp_id'),
            entregue_por_id=getattr(current_user, 'id', None))
    except Exception as e:
        logger.warning('Fase 2: emissão de evento de handoff falhou '
                       '(best-effort): %s', e)
```

- [ ] **Step 6: Rode os testes**

```bash
python -m pytest tests/test_fase2_handoff_gp.py tests/test_task_45_catalogo_eventos.py -v 2>&1 | tail -20
```

Esperado: os 23 testes da Fase 2 PASSAM e `test_task_45_catalogo_eventos.py` continua verde (a allowlist cresceu, mas aquele teste só checa presença dos 8 originais — confira `tests/test_task_45_catalogo_eventos.py:95`; se ele comparar o conjunto por igualdade, acrescente os dois nomes lá).

- [ ] **Step 7: Commit**

```bash
git add utils/catalogo_eventos.py utils/webhook_dispatcher.py views/obras.py tests/test_fase2_handoff_gp.py
git commit -m "feat(fase2): eventos obra.estado_alterado e obra.handoff

O handoff passa a notificar o GP pelo canal n8n que ja existe. A
conclusao da obra deixa de ser inferida por comparacao de string
pos-commit (views/obras.py:963-979) e vira fato da maquina."
```

---

## Task 11: Fechar os caminhos antigos de escrita de estado

Enquanto `editar_obra`, `toggle_status_obra` e `toggle_ativo_obra_api` escreverem direto, a máquina é decorativa.

**Files:**
- Modify: `views/obras.py:863` (`editar_obra`), `views/obras.py:963-979`, `views/obras.py:1259`, `views/obras.py:1296`, `views/obras.py:82-83` (filtro)
- Modify: `templates/obra_form.html:315-330`
- Test: `tests/test_fase2_maquina_estados_obra.py`

- [ ] **Step 1: Escreva o teste que falha**

Acrescente ao fim de `tests/test_fase2_maquina_estados_obra.py`:

```python
def _cliente_logado(user_id):
    c = app.test_client()
    with c.session_transaction() as sess:
        sess['_user_id'] = str(user_id)
        sess['_fresh'] = True
    return c


def test_editar_obra_ignora_o_campo_status_do_formulario():
    """O form não muda mais estado. Postar 'Concluída' não pode concluir
    a obra pelas costas da máquina."""
    with app.app_context():
        admin = _admin()
        obra = _obra(admin, estado='em_execucao', status='Em andamento')
        obra_id, admin_id, cli_nome = obra.id, admin.id, obra.cliente_ref.nome
        nome = obra.nome
    c = _cliente_logado(admin_id)
    c.post(f'/obras/editar/{obra_id}', data={
        'nome': nome, 'data_inicio': '2026-07-01',
        'cliente_busca': cli_nome, 'status': 'Concluída', 'ativo': 'on',
    }, follow_redirects=False)
    with app.app_context():
        from models import Obra
        o = db.session.get(Obra, obra_id)
        assert o.estado == 'em_execucao'
        assert o.status == 'Em andamento'


def test_toggle_ativo_passa_pela_maquina_e_grava_historico():
    with app.app_context():
        admin = _admin()
        obra = _obra(admin, estado='em_execucao', status='Em andamento')
        obra_id, admin_id = obra.id, admin.id
    c = _cliente_logado(admin_id)
    r = c.post(f'/api/obra/{obra_id}/toggle-ativo')
    assert r.status_code == 200
    with app.app_context():
        from models import Obra, ObraTransicaoEstado
        o = db.session.get(Obra, obra_id)
        assert o.estado == 'concluida'
        assert o.ativo is False
        assert ObraTransicaoEstado.query.filter_by(
            obra_id=obra_id, estado_para='concluida').count() == 1


def test_toggle_ativo_reabre_obra_concluida():
    with app.app_context():
        admin = _admin()
        obra = _obra(admin, estado='concluida', status='Concluída', ativo=False)
        obra_id, admin_id = obra.id, admin.id
    c = _cliente_logado(admin_id)
    r = c.post(f'/api/obra/{obra_id}/toggle-ativo')
    assert r.status_code == 200
    with app.app_context():
        from models import Obra
        o = db.session.get(Obra, obra_id)
        assert o.estado == 'em_execucao'
        assert o.ativo is True


def test_toggle_ativo_de_obra_cancelada_devolve_400():
    """CANCELADA é terminal — o toggle não pode ressuscitar."""
    with app.app_context():
        admin = _admin()
        obra = _obra(admin, estado='cancelada', status='Cancelada', ativo=False)
        obra_id, admin_id = obra.id, admin.id
    c = _cliente_logado(admin_id)
    r = c.post(f'/api/obra/{obra_id}/toggle-ativo')
    assert r.status_code == 400
    with app.app_context():
        from models import Obra
        assert db.session.get(Obra, obra_id).estado == 'cancelada'


def test_filtro_da_listagem_aceita_estado_e_rotulo():
    """`?status=Em andamento` (link antigo) e `?estado=em_execucao` (novo)
    precisam devolver a mesma obra."""
    with app.app_context():
        admin = _admin()
        obra = _obra(admin, estado='em_execucao', status='Em andamento')
        nome, admin_id = obra.nome, admin.id
    c = _cliente_logado(admin_id)
    for query in ('status=Em+andamento', 'estado=em_execucao',
                  'status=Em+Andamento'):
        r = c.get(f'/obras?{query}')
        assert r.status_code == 200
        assert nome.encode() in r.data, f'obra sumiu com ?{query}'
```

- [ ] **Step 2: Rode e veja falhar**

```bash
python -m pytest tests/test_fase2_maquina_estados_obra.py -k "editar_obra or toggle or filtro" -v 2>&1 | tail -20
```

Esperado: FAIL — `editar_obra` ainda conclui a obra pelo form; o toggle não grava histórico; `?status=Em+Andamento` não acha nada.

- [ ] **Step 3: `editar_obra` para de escrever estado**

Em `views/obras.py`, troque a linha 863:

```python
            obra.status = request.form.get('status', 'Em andamento')
```

por:

```python
            # Fase 2 — o formulário NÃO muda mais o estado da obra. Antes
            # daqui bastava postar 'Concluída' no campo `status` para
            # concluir a obra sem validação, sem motivo e sem registro de
            # quem fez. O caminho passou a ser POST /obras/<id>/estado,
            # que valida o grafo e grava obra_transicao_estado.
            # `obra.status` continua existindo como espelho, escrito por
            # services.obra_estado.aplicar_estado.
            _status_form = request.form.get('status')
            if _status_form and _status_form != obra.status:
                logger.info(
                    'Fase 2: campo status=%r ignorado na edição da obra %s '
                    '(estado atual=%r) — use POST /obras/%s/estado',
                    _status_form, obra.id, obra.estado, obra.id)
```

E **remova** o bloco de emissão de `obra.concluida` por comparação de string (`views/obras.py:963-979`, do comentário `# Task #45 — catálogo ...` até o `except Exception as _e_cat: ...` inclusive), substituindo por:

```python
                # Fase 2 — a emissão de `obra.concluida` migrou para
                # `_notificar_transicao`, chamada pela rota de transição.
                # O bloco removido daqui comparava strings normalizadas
                # DEPOIS do commit para adivinhar se a obra tinha sido
                # concluída; agora a conclusão é um fato da máquina.
```

Também remova a linha `status_anterior = (obra.status or '').strip()` (`views/obras.py:858`) e o comentário `# Task #45 — captura status anterior ...` (`views/obras.py:856-857`), que ficaram sem uso.

- [ ] **Step 4: Os dois toggles passam pela máquina**

Em `views/obras.py`, no corpo de `toggle_status_obra` (`views/obras.py:1259`), troque:

```python
        obra.ativo = not obra.ativo
        db.session.commit()

        status_texto = "ATIVA" if obra.ativo else "CONCLUÍDA"
        flash(f'Obra "{obra.nome}" alterada para {status_texto}!', 'success')
```

por:

```python
        # Fase 2 — o toggle deixou de escrever `ativo` direto. `ativo` é
        # derivado do estado (services.obra_estado.aplicar_estado), e
        # inverter só o booleano deixava os dois eixos discordando — foi
        # assim que nasceram as 13 obras com status='Em andamento' E
        # ativo=false encontradas no censo de 2026-07-21.
        from services.obra_estado import (
            EstadoObra, TransicaoInvalida, transitar,
        )
        destino = (EstadoObra.CONCLUIDA if obra.ativo else EstadoObra.EM_EXECUCAO)
        try:
            transitar(obra, destino, usuario_id=current_user.id,
                      motivo=('Reabertura pelo botão da listagem'
                              if destino is EstadoObra.EM_EXECUCAO else ''),
                      detalhes={'origem': 'toggle_status_obra'})
            db.session.commit()
        except TransicaoInvalida as e:
            db.session.rollback()
            flash(str(e), 'error')
            return redirect(url_for('main.detalhes_obra', id=id)), 400

        flash(f'Obra "{obra.nome}" agora está em {obra.status}!', 'success')
```

No `toggle_ativo_obra_api` (`views/obras.py:1296`), troque:

```python
        obra.ativo = not obra.ativo
        db.session.commit()

        status_texto = "reativada" if obra.ativo else "concluída"
        logger.info(f"[OK] Obra {obra.nome} {status_texto} (admin_id={admin_id})")

        return jsonify({
            'success': True,
            'message': f'Obra {status_texto} com sucesso',
            'ativo': obra.ativo,
        })
```

por:

```python
        # Fase 2 — mesma razão do toggle acima: `ativo` é derivado.
        from services.obra_estado import (
            EstadoObra, TransicaoInvalida, transitar,
        )
        destino = (EstadoObra.CONCLUIDA if obra.ativo else EstadoObra.EM_EXECUCAO)
        try:
            transitar(obra, destino, usuario_id=current_user.id,
                      motivo=('Reabertura pela listagem'
                              if destino is EstadoObra.EM_EXECUCAO else ''),
                      detalhes={'origem': 'toggle_ativo_obra_api'})
            db.session.commit()
        except TransicaoInvalida as e:
            db.session.rollback()
            return jsonify({'success': False, 'message': str(e)}), 400

        logger.info(f"[OK] Obra {obra.nome} → {obra.estado} (admin_id={admin_id})")
        return jsonify({
            'success': True,
            'message': f'Obra agora está em {obra.status}',
            'ativo': obra.ativo,
            'estado': obra.estado,
            'status': obra.status,
        })
```

- [ ] **Step 5: O filtro da listagem entende estado**

Em `views/obras.py`, troque o bloco do filtro (`views/obras.py:82-83`):

```python
    if filtros['status']:
        query = query.filter(Obra.status == filtros['status'])
```

por:

```python
    # Fase 2 — o filtro passou a operar sobre `estado`. Antes comparava
    # `Obra.status` por igualdade exata contra o texto do select, o que
    # fazia `?status=Em Andamento` (grafia de dropdown_service.py:94 e
    # obra_form.html:322) não achar nenhuma das obras gravadas como
    # 'Em andamento' pela cascata da proposta (event_manager.py:1018).
    # Aceita os dois parâmetros e as duas grafias.
    from services.obra_estado import (
        EstadoDesconhecido, coagir, estado_do_status_legado,
    )
    _filtro_estado = (request.args.get('estado') or '').strip()
    _alvo = None
    if _filtro_estado:
        try:
            _alvo = coagir(_filtro_estado)
        except EstadoDesconhecido:
            _alvo = None
    if _alvo is None and filtros['status']:
        _alvo = estado_do_status_legado(filtros['status'])
    if _alvo is not None:
        query = query.filter(Obra.estado == _alvo.value)
    elif filtros['status']:
        # Valor customizado de tenant que o mapa não conhece — mantém o
        # comportamento antigo em vez de devolver lista vazia.
        query = query.filter(Obra.status == filtros['status'])
    filtros['estado'] = _filtro_estado
```

- [ ] **Step 6: O select de status vira badge**

Em `templates/obra_form.html`, troque o bloco do select (`templates/obra_form.html:315-330`, o `<select ... name="status">` com o `{% for s in (opcoes_obra_status or [...]) %}`) por:

```html
{# Fase 2 — o estado da obra deixou de ser um campo editável. Antes este
   select gravava texto livre em Obra.status, com três grafias possíveis
   ('Em Andamento' aqui, 'Em andamento' na cascata, 'Em Andamento' no
   forms.py:42). O estado agora muda só pelas rotas
   POST /obras/<id>/estado e POST /obras/<id>/handoff. #}
<div class="mb-3">
  <label class="form-label">Estado da obra</label>
  <div>
    <span class="badge bg-secondary fs-6">{{ obra.status if obra else 'Planejamento' }}</span>
    {% if obra %}
    <a class="btn btn-sm btn-outline-primary ms-2"
       href="{{ url_for('main.detalhes_obra', id=obra.id) }}#estado-obra">
      Alterar estado
    </a>
    {% endif %}
  </div>
  <div class="form-text">
    O estado muda pelo painel da obra, com registro de quem alterou e por quê.
  </div>
</div>
```

- [ ] **Step 7: Rode os testes**

```bash
python -m pytest tests/test_fase2_maquina_estados_obra.py -v 2>&1 | tail -20
python -m pytest tests/test_fase0_autorizacao.py -v 2>&1 | tail -10
```

Esperado: 35 testes da Fase 2 PASSAM; a suíte da Fase 0 continua verde.

- [ ] **Step 8: Commit**

```bash
git add views/obras.py templates/obra_form.html tests/test_fase2_maquina_estados_obra.py
git commit -m "feat(fase2): fecha os caminhos antigos de escrita de estado

editar_obra ignora o campo status do form; os dois toggles de ativo
passam por transitar(); o filtro da listagem opera sobre estado e aceita
as duas grafias. O select de status virou badge somente-leitura."
```

---

## Task 12: Painel de estado e tela de handoff

**Files:**
- Create: `templates/obras/_estado_obra.html`
- Create: `templates/obras/handoff.html`
- Modify: `views/obras.py:2050` (contexto de `detalhes_obra`)
- Modify: `templates/obras/detalhes_obra_profissional.html:1375-1380`
- Test: `tests/test_fase2_maquina_estados_obra.py`

- [ ] **Step 1: Escreva o teste que falha**

Acrescente ao fim de `tests/test_fase2_maquina_estados_obra.py`:

```python
def test_detalhe_da_obra_mostra_o_painel_de_estado_com_as_opcoes_validas():
    with app.app_context():
        admin = _admin()
        obra = _obra(admin, estado='em_execucao', status='Em andamento')
        obra_id, admin_id = obra.id, admin.id
    c = _cliente_logado(admin_id)
    r = c.get(f'/obras/{obra_id}')
    assert r.status_code == 200
    corpo = r.data.decode('utf-8', 'replace')
    assert 'id="estado-obra"' in corpo
    # A partir de EM_EXECUCAO só existem três destinos.
    assert 'value="pausada"' in corpo
    assert 'value="concluida"' in corpo
    assert 'value="cancelada"' in corpo
    assert 'value="planejamento"' not in corpo


def test_detalhe_de_obra_em_planejamento_oferece_o_handoff():
    with app.app_context():
        admin = _admin()
        obra = _obra(admin, estado='planejamento', status='Planejamento')
        obra_id, admin_id = obra.id, admin.id
    c = _cliente_logado(admin_id)
    r = c.get(f'/obras/{obra_id}')
    corpo = r.data.decode('utf-8', 'replace')
    assert f'/obras/{obra_id}/handoff' in corpo


def test_detalhe_mostra_o_historico_de_transicoes():
    from models import EstadoObra
    from services.obra_estado import transitar
    with app.app_context():
        admin = _admin()
        obra = _obra(admin, estado='em_execucao', status='Em andamento')
        transitar(obra, EstadoObra.PAUSADA, usuario_id=admin.id,
                  motivo='Falta de perfil galvanizado')
        db.session.commit()
        obra_id, admin_id = obra.id, admin.id
    c = _cliente_logado(admin_id)
    r = c.get(f'/obras/{obra_id}')
    corpo = r.data.decode('utf-8', 'replace')
    assert 'Falta de perfil galvanizado' in corpo


def test_tela_de_handoff_renderiza():
    with app.app_context():
        admin = _admin()
        obra = _obra(admin, estado='planejamento', status='Planejamento')
        obra_id, admin_id = obra.id, admin.id
    c = _cliente_logado(admin_id)
    r = c.get(f'/obras/{obra_id}/handoff')
    assert r.status_code == 200
    assert b'Gerente de Projeto' in r.data
```

- [ ] **Step 2: Rode e veja falhar**

```bash
python -m pytest tests/test_fase2_maquina_estados_obra.py -k "painel or handoff or historico" -v 2>&1 | tail -20
```

Esperado: FAIL — `id="estado-obra"` não existe; `/obras/<id>/handoff` renderiza `TemplateNotFound`.

- [ ] **Step 3: Crie `templates/obras/_estado_obra.html`**

```html
{# Fase 2 — painel de estado da obra.

   Substitui o badge estático de detalhes_obra_profissional.html:1377, que
   só imprimia `obra.status` (texto livre) sem oferecer ação nenhuma. O
   contexto vem de `views.obras.detalhes_obra`:
     estado_atual        — EstadoObra corrente
     estado_rotulo       — rótulo humano
     estado_destinos     — [(value, rotulo, exige_motivo, autoridade)]
     estado_historico    — lista de ObraTransicaoEstado, mais recente primeiro
     estado_pode_handoff — bool
#}
<div class="card mb-3" id="estado-obra">
  <div class="card-header d-flex align-items-center justify-content-between">
    <span><i class="fas fa-flag me-2"></i>Estado da obra</span>
    <span class="badge bg-primary fs-6">{{ estado_rotulo }}</span>
  </div>
  <div class="card-body">

    {% if estado_pode_handoff %}
      <div class="alert alert-warning d-flex align-items-center justify-content-between">
        <div>
          <strong>Esta obra ainda não tem Gerente de Projeto.</strong>
          Ela entra em execução pelo handoff, que atribui o responsável e
          dá a ele o papel de gestor da obra.
        </div>
        <a class="btn btn-primary"
           href="{{ url_for('main.handoff_obra_get', id=obra.id) }}">
          Entregar ao GP
        </a>
      </div>
    {% endif %}

    {% if estado_destinos %}
      <form method="POST" action="{{ url_for('main.alterar_estado_obra', id=obra.id) }}"
            class="row g-2 align-items-end">
        <div class="col-md-4">
          <label class="form-label" for="estado-destino">Mudar para</label>
          <select class="form-select" id="estado-destino" name="estado" required>
            <option value="">Selecione…</option>
            {% for valor, rotulo, exige, _autoridade in estado_destinos %}
              <option value="{{ valor }}" data-exige-motivo="{{ 1 if exige else 0 }}">
                {{ rotulo }}{% if exige %} (exige motivo){% endif %}
              </option>
            {% endfor %}
          </select>
        </div>
        <div class="col-md-6">
          <label class="form-label" for="estado-motivo">Motivo</label>
          <input class="form-control" id="estado-motivo" name="motivo"
                 maxlength="500" placeholder="Ex.: chuva por 12 dias seguidos">
        </div>
        <div class="col-md-2">
          <button type="submit" class="btn btn-outline-primary w-100">Aplicar</button>
        </div>
      </form>
    {% else %}
      <p class="text-muted mb-0">
        Esta obra está em <strong>{{ estado_rotulo }}</strong>, um estado final —
        não há transições disponíveis.
      </p>
    {% endif %}

    {% if estado_historico %}
      <hr>
      <h6 class="text-muted">Histórico</h6>
      <div class="table-responsive">
        <table class="table table-sm align-middle mb-0">
          <thead>
            <tr><th>Quando</th><th>De → Para</th><th>Quem</th><th>Motivo</th></tr>
          </thead>
          <tbody>
            {% for t in estado_historico %}
            <tr>
              <td class="text-nowrap">{{ t.criado_em.strftime('%d/%m/%Y %H:%M') }}</td>
              <td class="text-nowrap">
                {{ t.estado_de or '—' }} &rarr; <strong>{{ t.estado_para }}</strong>
              </td>
              <td>{{ t.usuario_id or 'sistema' }}</td>
              <td>{{ t.motivo or '' }}</td>
            </tr>
            {% endfor %}
          </tbody>
        </table>
      </div>
    {% endif %}
  </div>
</div>
```

- [ ] **Step 4: Crie `templates/obras/handoff.html`**

```html
{% extends "base.html" %}
{% block title %}Handoff — {{ obra.nome }}{% endblock %}
{% block content %}
{# Fase 2 — tela de handoff. O dossiê (proposta vigente, cliente,
   cronograma) é o "pacote" que DEVOLUTIVA.md:224 pede: o GP precisa
   receber contexto junto com a responsabilidade, não só um campo
   preenchido. #}
<div class="container-fluid py-3">
  <h3 class="mb-3">
    <i class="fas fa-people-arrows me-2"></i>
    Entregar a obra ao Gerente de Projeto
  </h3>
  <p class="text-muted">
    {{ obra.codigo }} — {{ obra.nome }}
  </p>

  {% if dossie.bloqueios %}
    <div class="alert alert-danger">
      <strong>O handoff está bloqueado:</strong>
      <ul class="mb-0">
        {% for b in dossie.bloqueios %}<li>{{ b }}</li>{% endfor %}
      </ul>
    </div>
  {% endif %}

  <div class="row g-3">
    <div class="col-lg-6">
      <div class="card h-100">
        <div class="card-header">Dossiê</div>
        <div class="card-body">
          <dl class="row mb-0">
            <dt class="col-5">Cliente</dt>
            <dd class="col-7">{{ dossie.cliente.nome or '—' }}</dd>
            <dt class="col-5">Contato</dt>
            <dd class="col-7">
              {{ dossie.cliente.email or '—' }}<br>{{ dossie.cliente.telefone or '' }}
            </dd>
            <dt class="col-5">Endereço</dt>
            <dd class="col-7">{{ dossie.obra.endereco or '—' }}</dd>
            <dt class="col-5">Início / previsão</dt>
            <dd class="col-7">
              {{ dossie.obra.data_inicio or '—' }} → {{ dossie.obra.data_previsao_fim or '—' }}
            </dd>
            <dt class="col-5">Valor de contrato</dt>
            <dd class="col-7">R$ {{ '%.2f'|format(dossie.obra.valor_contrato) }}</dd>
            <dt class="col-5">Área</dt>
            <dd class="col-7">{{ dossie.obra.area_total_m2 }} m²</dd>
            <dt class="col-5">Proposta vigente</dt>
            <dd class="col-7">
              {% if dossie.proposta %}
                {{ dossie.proposta.numero }} (v{{ dossie.proposta.versao }})
              {% else %}—{% endif %}
            </dd>
            <dt class="col-5">Cronograma</dt>
            <dd class="col-7">
              {{ dossie.cronograma.total_tarefas }} tarefa(s);
              {{ 'revisado' if dossie.cronograma.revisado else 'PENDENTE de revisão' }}
            </dd>
          </dl>
        </div>
      </div>
    </div>

    <div class="col-lg-6">
      <div class="card h-100">
        <div class="card-header">Gerente de Projeto</div>
        <div class="card-body">
          <form method="POST"
                action="{{ url_for('main.handoff_obra_post', id=obra.id) }}">
            <div class="mb-3">
              <label class="form-label" for="responsavel_id">Responsável</label>
              <select class="form-select" id="responsavel_id"
                      name="responsavel_id" required>
                <option value="">Selecione…</option>
                {% for cand in dossie.candidatos %}
                  <option value="{{ cand.id }}">{{ cand.nome }} ({{ cand.codigo }})</option>
                {% endfor %}
              </select>
              <div class="form-text">
                Só aparecem funcionários ativos que já têm login — o handoff
                cria o papel de gestor no usuário, não no cadastro de RH.
              </div>
            </div>
            <div class="mb-3">
              <label class="form-label" for="motivo">Observação (opcional)</label>
              <textarea class="form-control" id="motivo" name="motivo"
                        rows="3" maxlength="500"></textarea>
            </div>
            <button type="submit" class="btn btn-primary"
                    {{ 'disabled' if dossie.bloqueios else '' }}>
              Entregar a obra
            </button>
            <a class="btn btn-link"
               href="{{ url_for('main.detalhes_obra', id=obra.id) }}">Cancelar</a>
          </form>
        </div>
      </div>
    </div>
  </div>
</div>
{% endblock %}
```

- [ ] **Step 5: Alimente o contexto em `views/obras.py`**

Em `views/obras.py`, imediatamente antes do `return render_template('obras/detalhes_obra_profissional.html', ...)` (`views/obras.py:2050`), insira:

```python
        # Fase 2 — contexto do painel de estado.
        from models import EstadoObra as _EO, ObraTransicaoEstado as _OTE
        from services.obra_estado import (
            ROTULOS as _ROT, estado_atual as _estado_atual,
            exige_motivo as _exige_motivo, autoridade_necessaria as _autoridade,
            pode_transitar_como as _pode_como, transicoes_possiveis as _possiveis,
        )
        _estado = _estado_atual(obra)
        _destinos = [
            (d.value, _ROT[d], _exige_motivo(_estado, d), _autoridade(_estado, d))
            for d in _possiveis(_estado)
            if _pode_como(obra, d, current_user)
        ]
        _historico = (_OTE.query.filter_by(obra_id=obra.id)
                      .order_by(_OTE.criado_em.desc(), _OTE.id.desc())
                      .limit(30).all())
        _pode_handoff = (_estado is _EO.PLANEJAMENTO
                         and _pode_como(obra, _EO.EM_EXECUCAO, current_user))
```

E acrescente ao dicionário de contexto do `render_template` as chaves:

```python
                               estado_atual=_estado,
                               estado_rotulo=_ROT[_estado],
                               estado_destinos=_destinos,
                               estado_historico=_historico,
                               estado_pode_handoff=_pode_handoff,
```

- [ ] **Step 6: Inclua o partial no template de detalhes**

Em `templates/obras/detalhes_obra_profissional.html`, logo **depois** do bloco do badge em `templates/obras/detalhes_obra_profissional.html:1375-1380` (o `<span class="status-badge status-{{ obra.status.lower()... }}">`), acrescente:

```html
                {# Fase 2 — painel de estado com transições válidas,
                   handoff e histórico. O badge acima continua, agora
                   alimentado por um campo derivado. #}
                {% include 'obras/_estado_obra.html' %}
```

- [ ] **Step 7: Rode os testes**

```bash
python -m pytest tests/test_fase2_maquina_estados_obra.py -v 2>&1 | tail -20
```

Esperado: 39 testes PASSAM.

- [ ] **Step 8: Commit**

```bash
git add templates/obras/_estado_obra.html templates/obras/handoff.html views/obras.py templates/obras/detalhes_obra_profissional.html tests/test_fase2_maquina_estados_obra.py
git commit -m "feat(fase2): painel de estado e tela de handoff com dossie

O select so oferece transicoes que o grafo permite E que o usuario logado
pode disparar. O historico fica visivel na propria obra. A tela de
handoff entrega contexto junto com a responsabilidade."
```

---

## Task 13: Script de censo (`scripts/relatorio_estado_obra.py`) e runbook

Este script roda **antes** da migração em produção (para saber o que existe) e **depois** (para conferir o resultado).

**Files:**
- Create: `scripts/relatorio_estado_obra.py`
- Create: `docs/fase-2-rollout.md`
- Test: `tests/test_fase2_maquina_estados_obra.py`

- [ ] **Step 1: Escreva o teste que falha**

Acrescente ao fim de `tests/test_fase2_maquina_estados_obra.py`:

```python
def test_relatorio_lista_grafias_desconhecidas_e_divergencias():
    from scripts.relatorio_estado_obra import levantar
    with app.app_context():
        admin = _admin()
        _obra(admin, estado='em_execucao', status='Em andamento')
        _obra(admin, estado='em_execucao', status='Aguardando ART')
        _obra(admin, estado='em_execucao', status='Em andamento', ativo=False)

        rel = levantar(admin_id=admin.id)

        assert rel['total'] == 3
        assert rel['por_estado']['em_execucao'] == 3
        assert 'Aguardando ART' in rel['grafias_desconhecidas']
        # ativo=False com estado ativo é divergência a reportar.
        assert rel['divergencias_ativo'] == 1
        assert rel['sem_estado'] == 0


def test_relatorio_conta_obras_sem_gestor():
    from scripts.relatorio_estado_obra import levantar
    with app.app_context():
        admin = _admin()
        _obra(admin, estado='em_execucao', status='Em andamento')
        rel = levantar(admin_id=admin.id)
        assert rel['em_execucao_sem_gestor'] == 1
```

- [ ] **Step 2: Rode e veja falhar**

```bash
python -m pytest tests/test_fase2_maquina_estados_obra.py -k relatorio -v 2>&1 | tail -20
```

Esperado: FAIL — `ModuleNotFoundError: No module named 'scripts.relatorio_estado_obra'`.

- [ ] **Step 3: Crie `scripts/relatorio_estado_obra.py`**

```python
#!/usr/bin/env python3
"""Censo de estado das obras — Fase 2.

Rode ANTES da migração 231 para saber o que existe em produção, e DEPOIS
para conferir. Somente leitura: nunca escreve nada.

O censo do banco de DESENVOLVIMENTO em 2026-07-21 achou três grafias para
dois conceitos ('Em andamento' 7918, 'Em Andamento' 53, 'Concluída' 13) e
13 obras com `ativo=false` mas `status='Em andamento'`. Produção não foi
conferida — é para isso que este script existe.

Uso:
    python scripts/relatorio_estado_obra.py            # todos os tenants
    python scripts/relatorio_estado_obra.py --admin-id 10
"""
from __future__ import annotations

import argparse
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def levantar(admin_id: int | None = None) -> dict:
    """Devolve o censo como dict. Requer app_context ativo."""
    from models import Obra, UsuarioObra, PapelObra, db
    from services.obra_estado import estado_do_status_legado

    q = Obra.query
    if admin_id is not None:
        q = q.filter(Obra.admin_id == admin_id)
    obras = q.all()

    por_estado: dict[str, int] = {}
    por_status: dict[str, int] = {}
    grafias_desconhecidas: dict[str, int] = {}
    divergencias_ativo = 0
    sem_estado = 0

    for o in obras:
        estado = getattr(o, 'estado', None)
        if not estado:
            sem_estado += 1
        else:
            por_estado[estado] = por_estado.get(estado, 0) + 1
        rotulo = o.status or '<NULL>'
        por_status[rotulo] = por_status.get(rotulo, 0) + 1
        if o.status and estado_do_status_legado(o.status) is None:
            grafias_desconhecidas[o.status] = \
                grafias_desconhecidas.get(o.status, 0) + 1
        # `ativo` deve ser False exatamente em concluida/cancelada.
        esperado_ativo = estado not in ('concluida', 'cancelada')
        if estado and bool(o.ativo) != esperado_ativo:
            divergencias_ativo += 1

    ids_em_execucao = [o.id for o in obras if getattr(o, 'estado', None) == 'em_execucao']
    com_gestor = set()
    if ids_em_execucao:
        com_gestor = {
            row[0] for row in db.session.query(UsuarioObra.obra_id).filter(
                UsuarioObra.obra_id.in_(ids_em_execucao),
                UsuarioObra.papel == PapelObra.GESTOR,
                UsuarioObra.ativo.is_(True),
            ).all()
        }

    return {
        'admin_id': admin_id,
        'total': len(obras),
        'sem_estado': sem_estado,
        'por_estado': por_estado,
        'por_status_legado': por_status,
        'grafias_desconhecidas': grafias_desconhecidas,
        'divergencias_ativo': divergencias_ativo,
        'em_execucao_sem_gestor': len(
            [i for i in ids_em_execucao if i not in com_gestor]),
        'sem_responsavel': len([o for o in obras if o.responsavel_id is None]),
        'cronograma_nao_revisado': len(
            [o for o in obras if o.cronograma_revisado_em is None]),
    }


def imprimir(rel: dict) -> None:
    print('=' * 68)
    print(f'CENSO DE ESTADO DAS OBRAS — tenant={rel["admin_id"] or "TODOS"}')
    print('=' * 68)
    print(f'Total de obras ............... {rel["total"]}')
    print(f'Sem coluna `estado` .......... {rel["sem_estado"]}')
    print()
    print('Por estado:')
    for k, v in sorted(rel['por_estado'].items(), key=lambda kv: -kv[1]):
        print(f'  {k:<16} {v}')
    print()
    print('Por status legado:')
    for k, v in sorted(rel['por_status_legado'].items(), key=lambda kv: -kv[1]):
        print(f'  {k!r:<28} {v}')
    print()
    if rel['grafias_desconhecidas']:
        print('⚠️  Grafias que o mapa NÃO conhece (cairão em em_execucao ou,')
        print('    se ativo=false, em concluida — revise antes de migrar):')
        for k, v in sorted(rel['grafias_desconhecidas'].items(),
                           key=lambda kv: -kv[1]):
            print(f'  {k!r:<28} {v}')
    else:
        print('✅ Nenhuma grafia desconhecida.')
    print()
    print(f'Divergências status x ativo ....... {rel["divergencias_ativo"]}')
    print(f'Em execução SEM gestor vinculado .. {rel["em_execucao_sem_gestor"]}')
    print(f'Sem responsavel_id ................ {rel["sem_responsavel"]}')
    print(f'Cronograma não revisado ........... {rel["cronograma_nao_revisado"]}')
    print('=' * 68)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--admin-id', type=int, default=None,
                        help='limita o censo a um tenant')
    args = parser.parse_args()

    from app import app
    with app.app_context():
        imprimir(levantar(admin_id=args.admin_id))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
```

- [ ] **Step 4: Rode o script e os testes**

```bash
python scripts/relatorio_estado_obra.py 2>&1 | tail -30
python -m pytest tests/test_fase2_maquina_estados_obra.py -k relatorio -v 2>&1 | tail -10
```

Esperado: o censo imprime a distribuição e os 2 testes PASSAM.

- [ ] **Step 5: Escreva `docs/fase-2-rollout.md`**

```markdown
# Fase 2 — runbook de rollout e rollback

## Antes de subir

1. **Censo do que existe**, tenant a tenant:

       python scripts/relatorio_estado_obra.py
       python scripts/relatorio_estado_obra.py --admin-id <id>

   Olhe a seção "Grafias que o mapa NÃO conhece". Toda grafia listada ali
   vai cair na regra de derivação genérica da migration 231
   (`ativo=false → concluida`, senão `em_execucao`). Se alguma delas
   significar outra coisa na Veks, **acrescente a chave normalizada em
   `services/obra_estado._MAPA_LEGADO` e o `IN (...)` correspondente no
   CASE da migration 231 antes de subir.**

2. **Backup.** A migração escreve em `obra` (coluna nova + `status`) e
   insere ~1 linha por obra em `obra_transicao_estado`. O dump
   pré-migração do entrypoint já cobre isso; confirme que o volume
   `/var/backups/sige` existe (`ESTADO-ATUAL.md:36`).

## Ordem de execução

As três migrações rodam automaticamente no boot, na ordem em que estão em
`migrations_to_run`:

| # | O que faz | Reversível? |
|---|---|---|
| 230 | cria `obra_transicao_estado` (ou só garante os índices, se o `create_all` já criou a tabela) | sim — `DROP TABLE` |
| 231 | cria `obra.estado`, deriva de `status`/`ativo`, grava histórico, aplica NOT NULL + CHECK | sim — ver abaixo |
| 232 | normaliza `obra.status` para o rótulo canônico | sim — ver abaixo |

Falha em qualquer uma **aborta o boot** em produção (`app.py:668-680`) —
o app não sobe servindo schema meio-migrado.

## Conferência pós-migração

    python scripts/relatorio_estado_obra.py

Critérios de aceite:

- `Sem coluna estado` = 0;
- `Por status legado` tem no máximo cinco chaves, todas do vocabulário;
- `Divergências status x ativo` = 0;
- `Em execução SEM gestor vinculado` — este número é a fila de handoff
  pendente. Não é erro: é trabalho. Toda obra migrada para `em_execucao`
  herdou o estado, não o GP.

## Rollback

**Rollback de comportamento (sem tocar schema).** Reverter os commits das
Tasks 8–12 devolve as rotas antigas; `obra.estado` fica inerte e `status`
volta a ser fonte de verdade — já normalizado, o que só melhora.

**Rollback de dados da 232** (desfazer a normalização do texto legado). A
linha de backfill da 231 guardou o valor original:

```sql
UPDATE obra o
   SET status = split_part(
         split_part(t.motivo, 'status legado=', 2), ' | ativo=', 1)
  FROM obra_transicao_estado t
 WHERE t.obra_id = o.id
   AND t.estado_de IS NULL
   AND t.motivo LIKE 'backfill migration 231%';
```

**Rollback de schema da 231:**

```sql
ALTER TABLE obra DROP CONSTRAINT IF EXISTS ck_obra_estado;
DROP INDEX IF EXISTS ix_obra_estado;
ALTER TABLE obra DROP COLUMN IF EXISTS estado;
DELETE FROM migration_history WHERE migration_number IN (231, 232);
```

**Rollback de schema da 230:**

```sql
DROP TABLE IF EXISTS obra_transicao_estado;
DELETE FROM migration_history WHERE migration_number = 230;
```

Rode os DROPs **de trás para frente** (232 → 231 → 230) e lembre de
remover também as entradas de `migrations_to_run`, senão o próximo boot
reaplica tudo.

## Operação depois do rollout

- Obras migradas para `em_execucao` **não têm GESTOR**. Enquanto não
  tiverem, só `ADMIN`/`SUPER_ADMIN` conseguem pausar/concluir. Use o
  relatório para priorizar os handoffs.
- Um handoff em obra já `em_execucao` não é possível pelo grafo. Para
  atribuir GP a obra migrada, crie o `UsuarioObra(GESTOR)` pela tela de
  vínculos da Fase 1 — o handoff formal existe para obras novas.
```

- [ ] **Step 6: Commit**

```bash
git add scripts/relatorio_estado_obra.py docs/fase-2-rollout.md tests/test_fase2_maquina_estados_obra.py
git commit -m "chore(fase2): censo de estado das obras + runbook de rollout

Script somente-leitura para rodar antes e depois da migracao 231. O
runbook traz o SQL de rollback que le o status original de volta da linha
de backfill do historico."
```

---

## Task 14: Matriz de regressão e gate

**Files:**
- Modify: `tests/test_fase2_maquina_estados_obra.py`

- [ ] **Step 1: Escreva a matriz**

Acrescente ao fim de `tests/test_fase2_maquina_estados_obra.py`:

```python
# ---------------------------------------------------------------------------
# Matriz completa: 5 estados × 5 destinos × 3 atores. Uma tabela só, para
# que a regra de negócio seja legível numa tela, em vez de espalhada em
# vinte asserts.
# ---------------------------------------------------------------------------
# Legenda do valor: 'ok' = permitido; '-' = fora do grafo; 'x' = no grafo
# mas sem autoridade para este ator.
_MATRIZ = {
    #                         admin  gestor  estranho
    ('planejamento', 'em_execucao'): ('ok', 'x',  'x'),
    ('planejamento', 'cancelada'):   ('ok', 'x',  'x'),
    ('planejamento', 'pausada'):     ('-',  '-',  '-'),
    ('planejamento', 'concluida'):   ('-',  '-',  '-'),
    ('em_execucao', 'pausada'):      ('ok', 'ok', 'x'),
    ('em_execucao', 'concluida'):    ('ok', 'ok', 'x'),
    ('em_execucao', 'cancelada'):    ('ok', 'x',  'x'),
    ('em_execucao', 'planejamento'): ('-',  '-',  '-'),
    ('pausada', 'em_execucao'):      ('ok', 'ok', 'x'),
    ('pausada', 'cancelada'):        ('ok', 'x',  'x'),
    ('pausada', 'concluida'):        ('-',  '-',  '-'),
    ('concluida', 'em_execucao'):    ('ok', 'x',  'x'),
    ('concluida', 'cancelada'):      ('-',  '-',  '-'),
    ('cancelada', 'em_execucao'):    ('-',  '-',  '-'),
    ('cancelada', 'planejamento'):   ('-',  '-',  '-'),
}


@pytest.mark.parametrize('chave', sorted(_MATRIZ))
def test_matriz_de_transicoes_por_ator(chave):
    from services.obra_estado import pode_transitar, pode_transitar_como
    origem, destino = chave
    esperado_admin, esperado_gestor, esperado_estranho = _MATRIZ[chave]

    with app.app_context():
        admin = _admin()
        obra = _obra(admin, estado=origem)
        gestor = _usuario_comum(admin, _funcionario(admin))
        _vincular_gestor(gestor, obra)
        estranho = _usuario_comum(admin)

        no_grafo = pode_transitar(origem, destino)
        assert no_grafo is (esperado_admin != '-'), (
            f'{origem}→{destino}: grafo diz {no_grafo}, matriz diz '
            f'{esperado_admin!r}')

        for ator, esperado in ((admin, esperado_admin),
                               (gestor, esperado_gestor),
                               (estranho, esperado_estranho)):
            obtido = pode_transitar_como(obra, destino, ator)
            assert obtido is (esperado == 'ok'), (
                f'{origem}→{destino} para {ator.tipo_usuario}: '
                f'obtido {obtido}, matriz diz {esperado!r}')


def test_todo_par_do_grafo_esta_na_matriz():
    """Guarda contra grafo e matriz divergirem em silêncio."""
    from services.obra_estado import TRANSICOES
    pares_do_grafo = {
        (o.value, d.value) for o, destinos in TRANSICOES.items() for d in destinos
    }
    pares_da_matriz = {k for k, v in _MATRIZ.items() if v[0] == 'ok'}
    assert pares_do_grafo == pares_da_matriz


def test_toda_transicao_do_grafo_tem_autoridade_declarada():
    from services.obra_estado import AUTORIDADE, TRANSICOES
    for origem, destinos in TRANSICOES.items():
        for destino in destinos:
            assert (origem, destino) in AUTORIDADE, (
                f'{origem.value}→{destino.value} sem autoridade declarada — '
                'cairia no default "admin" sem ninguém decidir isso')


def test_nenhuma_obra_do_banco_tem_estado_fora_do_vocabulario():
    """Invariante global, roda sobre tudo o que existir na base de teste."""
    from models import EstadoObra, Obra
    with app.app_context():
        validos = {e.value for e in EstadoObra}
        fora = db.session.query(Obra.estado).filter(
            Obra.estado.notin_(list(validos))).distinct().all()
        assert fora == [], f'estados fora do vocabulário: {fora}'
```

- [ ] **Step 2: Rode a matriz**

```bash
python -m pytest tests/test_fase2_maquina_estados_obra.py -v 2>&1 | tail -25
```

Esperado: 15 casos parametrizados + 3 guardas + os 39 anteriores = 57 testes, todos PASSAM.

- [ ] **Step 3: Rode o gate inteiro**

```bash
bash run_tests.sh --gate 2>&1 | tail -40
```

Esperado: nenhuma regressão contra a baseline anotada no início da fase. Anote passados/falhados. Preste atenção especial nestas suítes, que tocam obra:

- `tests/test_propagacao_proposta_obra.py` — a cascata da proposta
- `tests/test_cronograma_revisao_obra_gate.py` — o gate Task #200
- `tests/test_task_45_catalogo_eventos.py` — a allowlist e `obra.concluida`
- `tests/test_fase0_autorizacao.py` — as rotas de obra
- `tests/test_orcamento_operacional.py`, `tests/test_formato_br_e2e_extra.py`,
  `tests/test_rdo_subgrupo_aninhado.py`, `tests/test_cronograma_apontamento_service.py`
  — fixtures que criam `Obra(status='Em andamento')` sem `estado`; devem
  continuar verdes graças ao `default='planejamento'` do modelo.

- [ ] **Step 4: Commit**

```bash
git add tests/test_fase2_maquina_estados_obra.py
git commit -m "test(fase2): matriz 5x5x3 de transicoes por ator

Uma tabela legivel em vez de vinte asserts espalhados, mais tres guardas
contra grafo, matriz e tabela de autoridade divergirem em silencio."
```

---

## Encerramento da fase

- [ ] **Atualize `ESTADO-ATUAL.md`:** marque a Fase 2 como concluída na tabela de fases (`ESTADO-ATUAL.md:53`); corrija o diagnóstico desatualizado sobre cronograma preso a insumos (`ESTADO-ATUAL.md:70-78`), já resolvido pela Task #116 em `cronograma_views.py:365-397`; acrescente à lista de documentos o `docs/fase-2-rollout.md`.
- [ ] **Atualize `DEVOLUTIVA.md`:** o conflito #1 da tabela de modelo de dados (`DEVOLUTIVA.md:88`) foi resolvido; o item "Máquina de estados da Obra" e "Handoff do GP" da tabela transversal (`DEVOLUTIVA.md:82-83`) saem de CONSTRUIR.
- [ ] **Rode o censo em produção** (`python scripts/relatorio_estado_obra.py`) e leve o número de "Em execução SEM gestor vinculado" para o Cássio — é a fila de handoff que a migração criou.
- [ ] **Verifique que a Fase 3 está destravada:** a `Requisicao` de compras vai pendurar-se numa obra com estado — é o `EM_EXECUCAO` que autoriza requisitar, e é o `UsuarioObra(GESTOR)` criado pelo handoff que vai aprovar a alçada.

---

## Decisões que precisam do Cássio

Nenhuma bloqueia o plano — todas seguem com a recomendação adotada. Se ele discordar de alguma, o ponto de mudança está indicado.

| # | Decisão | **Recomendado (adotado)** | Onde muda se ele discordar |
|---|---|---|---|
| 1 | Quais estados existem | **Cinco:** `PLANEJAMENTO`, `EM_EXECUCAO`, `PAUSADA`, `CONCLUIDA`, `CANCELADA` — cada um ancorado num valor que o código já produz ou já oferece. A spec citada em `DEVOLUTIVA.md:82` pede 11; estados sem verbo que os consuma são rótulos | `EstadoObra` (models.py), `TRANSICOES`/`ROTULOS`/`AUTORIDADE` (services/obra_estado.py), lista `ESTADOS` da migration 231 |
| 2 | Existe estado "vendida"? | **Não.** A venda é estado da *Proposta* (`proposta.status='APROVADA'`, event_manager.py:1051). Duplicar criaria duas verdades para o mesmo fato | idem #1 |
| 3 | `CANCELADA` é terminal? | **Sim.** Reviver obra cancelada deve ser obra nova, com proposta nova | `TRANSICOES[EstadoObra.CANCELADA]` |
| 4 | Quem faz o handoff | **ADMIN/SUPER_ADMIN do tenant.** O GP não se autoentrega a obra | `AUTORIDADE[(PLANEJAMENTO, EM_EXECUCAO)]` |
| 5 | Quem pausa/conclui | **O GESTOR da obra** (e o admin). Paralisação e entrega são do dia a dia da obra | `AUTORIDADE` |
| 6 | Quem cancela | **Só ADMIN.** Cancelar é decisão comercial, não de campo | `AUTORIDADE` |
| 7 | Reabrir obra concluída | **Permitido, só ADMIN, com motivo obrigatório** | `TRANSICOES[CONCLUIDA]` + `TRANSICOES_QUE_EXIGEM_MOTIVO` |
| 8 | Toda obra nasce em `PLANEJAMENTO`? | **Sim**, inclusive a criada à mão — com atalho: se o form já traz responsável, o handoff roda na mesma transação | `event_manager.py` (cascata) e `views/obras.py::nova_obra` |
| 9 | Obras `ativo=false` viram o quê? | **`CONCLUIDA`**, mesmo com `status='Em andamento'` (13 casos no censo). A UI já as chama de "Concluída / Inativa" (`templates/obras_moderno.html:803,819`) | ordem das cláusulas do `CASE` na migration 231 |
| 10 | Grafias customizadas de tenant | **Caem na regra genérica** (`ativo=false → concluida`, senão `em_execucao`) e são listadas pelo censo para revisão. Nada falha por causa de um valor desconhecido | `_MAPA_LEGADO` + `CASE` da migration 231 |
| 11 | GP sem login pode ser responsável? | **Não.** Sem `Usuario` não há a quem dar o `UsuarioObra(GESTOR)`, e handoff sem vínculo é o campo decorativo que já existe hoje | `executar_handoff` |
| 12 | Handoff bloqueia por cronograma? | **Sim quando há o que revisar; carimba quando não há.** É o critério literal de `DEVOLUTIVA.md:225` | `_cronograma_pendente` em services/obra_handoff.py |
| 13 | O que fazer com as obras já em execução migradas sem GP? | **Nada automático.** O censo reporta a fila; atribuir GP retroativo é decisão caso a caso | `docs/fase-2-rollout.md`, seção "Operação depois do rollout" |
| 14 | O grupo de dropdown `obra_status` continua editável? | **Sim, mas deixa de alimentar o campo** — vira legado inerte. Remover o grupo é assunto da limpeza de dropdowns, não desta fase | `services/dropdown_service.py:56,94` |

---

## O que a Fase 2 deliberadamente NÃO faz

- **Não remove `Obra.status` nem `Obra.ativo`.** As duas colunas continuam existindo como espelho. Remover exigiria tocar ~40 templates e queries no mesmo commit — cada fase seguinte migra a sua fatia. `views/dashboard.py:428,1013,1035,1054` continua com a lista de valores mortos: funciona, e não é desta fase.
- **Não cria `RDO.status` como máquina.** É a Fase 5 (`DEVOLUTIVA.md:249-253`), e o molde será este.
- **Não amarra o estado a nenhuma regra de negócio de outro módulo.** Obra `PAUSADA` continua aceitando RDO, compra e lançamento — travar isso é assunto das Fases 3 e 5, quando existirem os verbos.
- **Não mexe nos templates órfãos** `templates/obras.html` e `templates/obras_safe.html`, que continuam com as grafias antigas. `obras.html` não é renderizado por ninguém; `obras_safe.html` só por `production_routes.py:239`. Podar é limpeza, não máquina de estados.
- **Não implementa notificação por e-mail/WhatsApp do handoff.** Emite `obra.handoff` na allowlist do n8n com o dossiê completo no payload; quem monta a mensagem é o fluxo externo, como em todos os eventos do catálogo.
- **Não migra `Obra.responsavel_id` para apontar a `Usuario`.** `DEVOLUTIVA.md:90` sugere um `Obra.gerente_id → Usuario`; a Fase 1 resolveu a ponte com `Usuario.funcionario_id`, e o `UsuarioObra(GESTOR)` já é a permissão. Uma terceira FK para a mesma pessoa seria armadilha de leitura.

---

## Autorrevisão feita sobre este plano

**Cobertura do escopo.** Os seis itens pedidos têm tarefa:

| Pedido | Onde |
|---|---|
| Enum de status com transições explícitas | Task 1 (`EstadoObra`, `TRANSICOES`) |
| Tabela de histórico (quem, quando, de→para, motivo) | Task 2 (`ObraTransicaoEstado` + migration 230) |
| Guarda que recusa transição inválida | Task 4 (`transitar`) + Task 5 (`pode_transitar_como`) + Task 8 (400/403 nas rotas) |
| Handoff do GP (responsável + `UsuarioObra` GESTOR) | Task 7 (serviço) + Task 8 (rotas) + Task 9 (atalho na criação) + Task 12 (tela) |
| Migração dos dados existentes | Task 3 (231, backfill) + Task 6 (232, normalização) + Task 13 (censo e rollback) |
| Censo real dos valores de `Obra.status` | seção "Censo real de `Obra.status`", com consulta ao banco e ressalva explícita de que é o banco de desenvolvimento |

Investigações exigidas e onde estão respondidas: cascata `proposta_aprovada` e ordem de import — seção "A cascata de `proposta_aprovada`" e Task 9; `cronograma_revisado_em` como estado disfarçado — decisão 7 e Task 7; `responsavel_id` sem relationship — tabela de contexto e decisão 11; infra de evento/auditoria reaproveitável — Task 10 (`utils/catalogo_eventos.py`, `utils/webhook_dispatcher.py`), Task 2 (molde `CronogramaImportacaoEvento`), Task 4 (log estruturado no molde de `cronograma_observabilidade`).

**Varredura de placeholders.** Nenhum "TBD", nenhum "similar à Task N", nenhum "adicione tratamento de erro adequado". A única referência adiante é declarada e resolvida: os stubs `_notificar_transicao`/`_notificar_handoff` na Task 8, com o código do stub escrito e a substituição na Task 10.

**Consistência de tipos e nomes.** Conferidos contra todos os usos:
`EstadoObra` (models.py) · `ObraTransicaoEstado` com campos `estado_de`/`estado_para`/`motivo`/`detalhes`/`usuario_id`/`criado_em` · `services/obra_estado.py`: `TRANSICOES`, `ROTULOS`, `ESTADOS_INATIVOS`, `TRANSICOES_QUE_EXIGEM_MOTIVO`, `AUTORIDADE`, `coagir`, `estado_do_status_legado`, `transicoes_possiveis`, `pode_transitar`, `exige_motivo`, `autoridade_necessaria`, `estado_atual`, `aplicar_estado`, `transitar`, `pode_transitar_como`, `EstadoDesconhecido`, `TransicaoInvalida` · `services/obra_handoff.py`: `HandoffInvalido`, `bloqueios_do_handoff`, `dossie_handoff`, `executar_handoff` · rotas `main.alterar_estado_obra`, `main.handoff_obra_get`, `main.handoff_obra_post` · `scripts/relatorio_estado_obra.py`: `levantar`, `imprimir`.

A função do serviço chama-se `estado_atual`, e **não** `estado_de`, de propósito: `estado_de` é nome de coluna do histórico, e as duas coisas apareceriam no mesmo arquivo de teste.

**Dependências da Fase 1 usadas aqui** (assinaturas lidas em `docs/superpowers/plans/2026-07-21-fase-1-identidade-papeis.md`, não presumidas): `Usuario.funcionario_id`; `utils.identidade.tenant_do_usuario`, `vincular_funcionario`, `usuario_do_funcionario`; `models.PapelObra` (`GESTOR`/`APONTADOR`/`LEITOR`) e `models.UsuarioObra` (com `UniqueConstraint('usuario_id','obra_id')`, `admin_id` NOT NULL, `ativo`); `Obra.responsavel` relationship. **Se a Fase 1 não tiver subido, esta fase não roda** — pare e execute a Fase 1 antes.

**Riscos maiores e como estão endereçados:**

1. *A migração deixar 7 984 obras em estado errado.* Endereçado no desenho da 231 (coluna nasce NULL, sem `server_default`; boot aborta em caso de falha) e nos testes `test_backfill_231_*`.
2. *O `create_all` mascarar o DDL da migração.* Endereçado no docstring da 230 e na criação separada dos índices — a lição da migration 213, com a prova em `migrations.py:13903` vs `information_schema`.
3. *Quebrar a cascata `proposta_aprovada` mexendo em ordem de handler.* Endereçado escrevendo o estado inicial dentro do handler existente, com dois testes de regressão (`test_obra_criada_pela_cascata...`, `test_cascata_nao_reescreve_estado...`) e a execução das suítes `test_propagacao_proposta_obra.py` e `test_cronograma_revisao_obra_gate.py` na Task 14.
4. *Obras migradas para `em_execucao` sem GESTOR ficarem sem quem as opere.* Mitigado porque `ADMIN`/`SUPER_ADMIN` são GESTOR implícito; a fila é reportada pelo censo e documentada no runbook.

**Números de migration:** 230, 231, 232 — a faixa reservada é 230–239, a maior registrada hoje é 213 (`migrations.py:4014`, confirmado no banco). Se a Fase 1 já tiver subido as 214–216, insira as três **depois** delas na lista.
