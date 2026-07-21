# Cronograma editável e RDO em porcentagem — Plano de Implementação

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Fazer o modo de apontamento (`quantidade` vs `percentual`) virar uma **escolha explícita da tarefa** em vez de uma dedução do serviço, e fazer o caminho automático proposta→obra parir um cronograma utilizável mesmo quando o catálogo de serviços/templates está incompleto — sem quebrar nenhuma obra que já tenha cronograma materializado.

**Architecture:** Três frentes independentes que compartilham o mesmo princípio: **o que hoje é deduzido passa a ser gravado, e o que hoje é deduzido continua sendo o default**. (1) `tarefa_cronograma` ganha a coluna `modo_apontamento`, com backfill que grava exatamente o que `modo_da_tarefa()` devolveria hoje — a migração é, por construção, um no-op de comportamento. (2) `materializar_cronograma` deixa de pular silenciosamente os itens de proposta sem template e passa a materializar uma tarefa-esqueleto por item quando o usuário marca — a obra nasce com EAP mesmo sem catálogo. (3) Uma tarefa **zero** de diagnóstico reporta, dado um `admin_id`, todas as flags que escondem cronograma daquele tenant — porque a queixa do dono pode ser flag desligada, não falta de recurso.

**Tech Stack:** Flask 3 + Flask-Login, SQLAlchemy 2 (`models.py`), sistema de migrações próprio numerado (`migrations.py`, `executar_migracoes`), Bootstrap 5 + JS vanilla nos templates, pytest (`run_tests.sh --gate`), PostgreSQL.

**Faixa de migrations reservada:** 220–229. Este plano usa **220** e **221**.

---

## O que JÁ EXISTE e NÃO será refeito

Conferido por mim em 2026-07-21 no commit `fb4147b`. Quem for executar este plano **não deve escrever CRUD de tarefa de cronograma**: ele existe, está ligado e funciona sem catálogo.

| Já existe | Evidência conferida |
|---|---|
| **Criar tarefa manual sem catálogo.** O único campo obrigatório é `nome_tarefa`; `servico_id` e `subatividade_mestre_id` são opcionais e resolvem para `None` | `cronograma_views.py:269` (rota POST), `:271` (`def criar_tarefa`), `:283-285` (única validação obrigatória: `nome`), `:365-367` (comentário Task #116), `:394` (`logger.info("[cronograma] Tarefa criada sem vínculo de serviço (servico_id=None é permitido)")`) |
| **`TarefaCronograma.servico_id` é nullable no schema**, com `ondelete='SET NULL'` | `models.py:4903-4908` |
| **O Gantt já faz o CRUD completo por AJAX**: POST criar, PUT editar, DELETE excluir, drag de barras | `templates/obras/cronograma.html:1658` (`salvarNovaTarefa`), `:1691` (fetch POST), `:1827` (`salvarEditar`), `:1864` (fetch PUT); rotas `cronograma_views.py:269`, `:450`, `:659` |
| **A UI já permite desvincular do catálogo** explicitamente | `templates/obras/cronograma.html:1640` (`limparSelecaoCatalogo()`), `:363` (`<option value="">— Sem vínculo de catálogo —</option>`) |
| **O importador `.mpp`/`.xml` cria tarefa sem serviço, sem subatividade e sem insumo** | `services/cronograma_versao_service.py:534-553` — o construtor `TarefaCronograma(...)` não menciona `servico_id` nem `subatividade_mestre_id` |
| **O motor de percentual do M07 já funciona nos dois modos**, com snapshot por linha, retrocesso justificado, sobre-execução confirmada e recomputo de cadeia | `services/cronograma_apontamento_service.py:194-340` (`registrar_apontamento`), `:92-191` (`recomputar_cadeia`) |
| **O contrato de modo já chega na UI do RDO** como `tipo_modo`, e a UI já renderiza campo único por modo | `cronograma_views.py:917` (`tipo_modo = modo_da_tarefa(t)`), `templates/rdo/novo.html:1118` e `:1425` |
| **Existe gate de revisão inicial de cronograma na obra**, com tela, POST idempotente e botão "revisar de novo" | `views/obras.py:2339` (`_precisa_revisao_cronograma_inicial`), `:2380` (GET), `:2418` (POST), `:2494` (reset); template `templates/obras/cronograma_revisar_inicial.html` |

**Portanto: nenhuma tarefa deste plano recria criação/edição/exclusão de tarefa, nem "desacopla a criação de tarefa do catálogo de insumos".** Isso já está pronto desde a Task #116.

---

## Correções ao diagnóstico do `ESTADO-ATUAL.md`

Três afirmações do snapshot são falsas ou imprecisas. Registrar isso é o resultado mais barato deste plano.

### 1. FALSO — "o cronograma nasce preso à proposta; sem catálogo cadastrado, não há cronograma"

`ESTADO-ATUAL.md:72-75`. A criação manual de tarefa nunca exigiu catálogo (tabela acima). O que é verdade é bem mais estreito: **o caminho automático** proposta→obra exige `CronogramaTemplate`, e quando não acha um, **pula o item em silêncio**.

### 2. FALSO — "`materializar_cronograma` exige serviço → composição → insumo"

`ESTADO-ATUAL.md:73-75`. A cadeia real é **`PropostaItem.servico_id` → `Servico.template_padrao_id` (ou `PropostaItem.cronograma_template_override_id`) → `CronogramaTemplate` → `CronogramaTemplateItem` → `SubatividadeMestre`**. `ComposicaoServico` e `Insumo` **não aparecem em lugar nenhum** de `services/cronograma_proposta.py` — o import do módulo (`:37-47`) não os traz, e nenhuma função os consulta. O que falta para o caminho automático funcionar é **template**, não insumo.

E o que acontece quando não há template não é erro: `montar_arvore_preview` marca o item com `sem_template=True, marcado=False` (`services/cronograma_proposta.py:280-290`) e `materializar_cronograma` faz `continue` (`:532-533`). **A obra nasce com zero tarefas, sem exceção e sem mensagem.** Pior: o handler de aprovação só chama `materializar_cronograma` quando `proposta.cronograma_default_json` é truthy (`handlers/propostas_handlers.py:134`); sem snapshot pré-configurado, o `elif` de `:158-163` apenas loga "obra criada em estado 'cronograma pendente'".

### 3. VERDADEIRO — "o RDO decide o modo sozinho"

`ESTADO-ATUAL.md:76-78`. Confirmado em `services/cronograma_apontamento_service.py:73-82`:

```python
def modo_da_tarefa(tarefa) -> str:
    if getattr(tarefa, 'is_marco', False):
        return 'percentual'
    if (tarefa.quantidade_total and float(tarefa.quantidade_total) > 0
            and (tarefa.unidade_medida or '').strip()):
        return 'quantidade'
    return 'percentual'
```

Único consumidor em código de aplicação: `cronograma_views.py:879` (import) e `:917` (uso). O usuário não escolhe nada — preencher "Quantidade" + "Unidade" no modal muda o modo do RDO como efeito colateral.

### 4. Achado NOVO — três regras diferentes para a mesma pergunta

O sistema classifica "esta tarefa é quantitativa?" em três lugares, com **três critérios distintos**:

| Local | Regra | Considera unidade? | Considera marco? |
|---|---|---|---|
| `services/cronograma_apontamento_service.py:79-81` | `quantidade_total > 0 AND unidade_medida != ''` | **sim** | sim |
| `services/cronograma_apontamento_service.py:159-161` (`recomputar_cadeia`) | `quantidade_total > 0` | não | não |
| `migrations.py:14090-14092` (backfill 210) | `t.quantidade_total > 0` | não | não |

Uma tarefa com `quantidade_total=100` e `unidade_medida=NULL` é `'percentual'` para a UI e `'quantitativo'` para o recomputo. Na prática o estrago é limitado porque `registrar_apontamento` grava `tipo_apontamento` explicitamente em toda escrita (`:324`) e a migration 210 preencheu as linhas antigas, então o fallback de `recomputar_cadeia` quase nunca dispara. Ainda assim é divergência real, e a Task 5 a fecha.

### 5. Achado NOVO — `Obra.regime_medicao` é coluna morta

`models.py:288-292` documenta: *"Governa se o vínculo custo↔tarefa é obrigatório (percentual) ou opcional (fixa)"*. **Nada lê essa coluna.** Varredura em todo `.py`/`.html`/`.js` (excluindo `migrations.py` e `.local/`) devolve apenas: a definição em `models.py:292`, a migration `_migration_201_obra_regime_medicao` (`migrations.py:13688`), um comentário em `services/importacao_fisico_financeiro.py:229` e um teste que apenas confere que a coluna existe (`tests/test_importacao_fisico_financeiro.py:41-47`). O comentário do modelo descreve uma intenção que nunca foi implementada. A Task 9 dá utilidade real à coluna e corrige o comentário.

### 6. Achado NOVO — `servico_id` de outro tenant vaza para a árvore de preview

`services/cronograma_proposta.py:282` devolve `'servico_id': it.servico_id` **cru**, sem passar pelo cache filtrado por tenant, enquanto o ramo com template (`:256`) faz `servico.id if servico else None`. Hoje isso é inofensivo porque o nó `sem_template` nunca vira tarefa. A partir da Task 11 viraria — o id iria direto para `TarefaCronograma.servico_id`. A Task 10 fecha antes.

---

## Contexto verificado no código (leia antes de começar)

| Fato | Evidência |
|---|---|
| Todo o blueprint de cronograma passa por `_check_v2()`, que faz `flash` + `redirect('main.dashboard')` (ou 403 JSON) | `cronograma_views.py:39-46`; guard chamado em 30+ rotas, ex. `:272`, `:453`, `:662`, `:848`, `:1140` |
| `is_v2_active()` depende de `Usuario.versao_sistema == 'v2'` **do admin do tenant** — e `SUPER_ADMIN` recebe `False` sempre | `utils/tenant.py:63-92`; coluna em `models.py:38`, default `'v1'` |
| O menu "Obras → Cronograma" do desktop só aparece com `is_v2_active()` | `templates/base_completo.html:738-748` |
| A flag `cronograma_mpp_ativo` nasce `FALSE` e esconde a aba de importação | `models.py:3620`, `utils/tenant.py:113-134`, `templates/obras/detalhes_obra_profissional.html:2134`, migration em `migrations.py:14105-14120` |
| Já existe script de flag por tenant com API `definir_flag` / `status_flag` — usar como molde | `scripts/flag_cronograma_mpp.py:45-73` |
| `RDOApontamentoCronograma` guarda `tipo_apontamento` ('quantitativo'\|'percentual') + 4 snapshots, criados pela migration 209 | `models.py:4990-4998`; migration registrada em `migrations.py:4010` |
| **Vocabulário divergente proposital**: `modo_da_tarefa()` devolve `'quantidade'`; `tipo_apontamento` grava `'quantitativo'`. São eixos diferentes (tarefa vs. linha de apontamento) | `services/cronograma_apontamento_service.py:81` vs `:246` |
| `registrar_apontamento` grava `tipo_apontamento` em TODA escrita, derivado do argumento recebido (XOR) | `services/cronograma_apontamento_service.py:205-209`, `:324` |
| `ApontamentoInvalido` é subclasse de `ValueError` **de propósito**: os laços legados em `views/rdo.py` protegem com `except (ValueError, TypeError)`, então uma violação num item vira warning em vez de derrubar o RDO | `services/cronograma_apontamento_service.py:52-58`; laços em `views/rdo.py:4635` e `:4652` |
| Existem **dois** caminhos de gravação de apontamento: `POST /cronograma/rdo/<id>/apontar` (JSON) e `POST salvar-rdo-flexivel` (form `cronograma_tarefa_<id>` / `cronograma_tarefa_pct_<id>`) | `cronograma_views.py:1133`; `views/rdo.py:4595-4666` |
| Fixtures de teste existentes criam `TarefaCronograma(quantidade_total=100.0)` **sem** `unidade_medida` e apontam com `quantidade_dia=` | `tests/test_cronograma_apontamento_service.py:75-88`, usos em `:101`, `:115`, `:138`, `:212`, `:234` — isso decide a Decisão D3 abaixo |
| `Obra.cliente_id` é NOT NULL — fixture cria `Cliente` antes | `models.py` classe `Obra`; padrão em `tests/test_cronograma_apontamento_service.py:57-71` |
| Login em teste é injeção de sessão | `tests/test_rdo_modos_apontamento.py:38-43` |
| Maior migration registrada é a **213** | `migrations.py:4014`; lista abre em `:3831`, dentro de `executar_migracoes()` (`:3773`) |
| Molde de migration idempotente | `migrations.py:13351` (`migration_182_replace_categorias_fluxo_caixa`) |
| **Inconsistência conhecida, deliberadamente NÃO tocada:** `modo_da_tarefa` trata marco só por `is_marco`, mas `_is_marco()` (usado nas validações) também aceita `duracao_dias == 0` | `services/cronograma_apontamento_service.py:77` vs `:85-89` |

---

## Decisões que precisam do Cássio

Nenhuma bloqueia a execução. Cada uma já tem recomendação adotada e implementada no plano.

**D1 — Vocabulário da coluna nova: `'quantidade'`/`'percentual'` ou `'quantitativo'`/`'percentual'`?**
`Recomendado: 'quantidade' | 'percentual'.` É o vocabulário que `modo_da_tarefa()` já devolve e que o JSON `tipo_modo` já entrega para `templates/rdo/novo.html:1118`. Adotar `'quantitativo'` obrigaria a traduzir na borda ou a mexer na UI do RDO sem necessidade. A coluna da **tarefa** e a coluna da **linha de apontamento** permanecem com nomes diferentes de propósito: são eixos diferentes.

**D2 — O backfill deve normalizar as tarefas hoje "quantitativas sem unidade" para `'quantidade'`?**
`Recomendado: NÃO.` O backfill grava **exatamente** o que `modo_da_tarefa()` devolveria hoje — inclusive `'percentual'` para tarefa com `quantidade_total=100` e `unidade_medida=NULL`. Qualquer outra escolha muda comportamento de obra em produção durante uma migração, que é a única coisa que este plano não pode fazer. Quem quiser corrigir essas tarefas depois faz pela UI, tarefa a tarefa, com o seletor da Task 8.

**D3 — Apontar em modo diferente do escolhido deve dar erro ou passar?**
`Recomendado: erro (422), mas SÓ quando o modo foi escolhido de fato (coluna não-NULL).` Enforcement incondicional quebraria a suíte de caracterização: `tests/test_cronograma_apontamento_service.py:101,115,138,212,234` criam tarefas com `quantidade_total=100.0` **sem unidade** (logo, `modo_da_tarefa == 'percentual'`) e apontam com `quantidade_dia=`. Restringir a validação às tarefas com modo explícito preserva 100% do legado e ainda assim honra a escolha do usuário: tarefa criada pela UI a partir da Task 7 vem com modo gravado e passa a ser validada. Nas fixtures que constroem `TarefaCronograma(...)` direto, a coluna fica `NULL` (não há default Python) e nada muda.

**D4 — Item de proposta sem template deve virar tarefa automaticamente ou só quando marcado?**
`Recomendado: só quando marcado, com o checkbox habilitado e desmarcado por padrão.` Materializar sempre quebraria `tests/test_cronograma_automatico_aprovacao.py:316` (`'item sem_template não criou tarefas extras'`) e encheria a obra de linhas que o usuário não pediu. Manter `marcado=False` como default (já é o comportamento — `services/cronograma_proposta.py:288`) e apenas **habilitar** o checkbox hoje `disabled` (`templates/obras/cronograma_revisar_inicial.html:271-273`) dá tolerância sem regressão.

**D5 — `Obra.regime_medicao` deve ganhar consumidor ou ser removida?**
`Recomendado: ganhar consumidor mínimo.` Remover uma coluna `NOT NULL` já backfillada em produção (migration 201) por 1.118+ obras é risco desnecessário. A Task 9 faz `regime_medicao == 'percentual'` significar "tarefa nova desta obra nasce em modo percentual", que é literalmente o que o nome promete, e corrige o comentário mentiroso de `models.py:288-291`. Se o Cássio decidir que a coluna deve governar o vínculo custo↔tarefa (o que o comentário atual afirma), isso é escopo da Fase 4 e não deste plano.

**D6 — Marco pode ter modo `'quantidade'`?**
`Recomendado: não, e o guard vem primeiro.` `modo_da_tarefa` continua devolvendo `'percentual'` para `is_marco=True` **antes** de olhar a coluna, e a API recusa gravar `'quantidade'` em marco. Isso preserva `tests/test_rdo_modos_apontamento.py:90` e a validação `MarcoApenasZeroOuCem`.

---

## Arquivos que este plano cria ou altera

| Arquivo | Responsabilidade |
|---|---|
| `scripts/diagnostico_cronograma_tenant.py` | **novo** — dado um `admin_id`, reporta todas as flags/estados que escondem cronograma daquele tenant |
| `models.py` | `TarefaCronograma.modo_apontamento`; comentário honesto em `Obra.regime_medicao` |
| `migrations.py` | migrations 220 (coluna + CHECK) e 221 (backfill congelando o modo atual) + registro em `migrations_to_run` |
| `services/cronograma_apontamento_service.py` | `modo_da_tarefa` lê a coluna; `_modo_deduzido` guarda a regra antiga; `recomputar_cadeia` usa o modo da tarefa; `ModoIncompativel` |
| `cronograma_views.py` | `criar_tarefa`/`atualizar_tarefa` aceitam `modo_apontamento`; `_tarefa_to_dict` devolve; rotas de tarefa e de apontamento passam pelo RBAC da Fase 1 |
| `templates/obras/cronograma.html` | seletor de modo nos modais Nova Tarefa e Editar |
| `services/cronograma_proposta.py` | `montar_arvore_preview` fecha o vazamento cross-tenant e dá corpo ao nó sem template; `materializar_cronograma` materializa esqueleto |
| `templates/obras/cronograma_revisar_inicial.html` | checkbox habilitado para item sem template |
| `views/obras.py` | gate de revisão dispara também quando a proposta tem itens mas nenhum template |
| `tests/test_cronograma_diagnostico_tenant.py` | **novo** |
| `tests/test_cronograma_modo_explicito.py` | **novo** — coluna, backfill, resolução, validação, API |
| `tests/test_cronograma_proposta_tolerante.py` | **novo** — árvore, esqueleto, gate |
| `tests/test_cronograma_rbac_fase1.py` | **novo** — matriz papel × rota de cronograma |

**Pré-requisito:** a Fase 1 (`docs/superpowers/plans/2026-07-21-fase-1-identidade-papeis.md`) precisa estar aplicada antes da Task 13 — ela fornece `utils/autorizacao.py` (`pode_editar_obra`, `pode_apontar_na_obra`, `obra_required`), `models.PapelObra`, `models.UsuarioObra` e as migrations 214–216. As Tasks 1–12 não dependem dela.

---

## Task 1: Diagnóstico das flags que escondem cronograma de um tenant

Esta é a tarefa que pode encerrar a queixa em cinco minutos. Se o tenant do Cássio estiver com `versao_sistema='v1'`, **todo** o módulo de cronograma responde `redirect` para o dashboard (`cronograma_views.py:42-44`) e nenhuma melhoria de produto muda isso.

**Files:**
- Create: `scripts/diagnostico_cronograma_tenant.py`
- Test: `tests/test_cronograma_diagnostico_tenant.py`

- [ ] **Step 1: Escreva o teste que falha**

Crie `tests/test_cronograma_diagnostico_tenant.py`:

```python
"""Diagnóstico das flags que escondem cronograma de um tenant.

Motivação: `cronograma_views.py:39` faz TODO o módulo passar por
`_check_v2()`, que redireciona para o dashboard quando
`utils.tenant.is_v2_active()` é falso — e isso depende de
`Usuario.versao_sistema == 'v2'` do ADMIN do tenant (`utils/tenant.py:63`).
Além disso `configuracao_empresa.cronograma_mpp_ativo` nasce FALSE
(`models.py:3620`) e esconde a aba de importação. Antes deste script não
havia como responder "por que o cronograma sumiu para este cliente?" sem
abrir o banco na mão.
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
from models import Cliente, ConfiguracaoEmpresa, Obra, TipoUsuario, Usuario

pytestmark = pytest.mark.integration


@pytest.fixture(autouse=True)
def _config():
    app.config['TESTING'] = True
    app.config['WTF_CSRF_ENABLED'] = False
    if not app.secret_key:
        app.secret_key = 'test-diagnostico-cronograma'
    yield


def _admin(versao='v1'):
    suf = uuid.uuid4().hex[:8]
    u = Usuario(
        username=f'diag_{suf}', email=f'diag_{suf}@test.local',
        nome=f'Diag {suf}',
        password_hash=generate_password_hash('Senha@2026'),
        tipo_usuario=TipoUsuario.ADMIN, ativo=True, versao_sistema=versao,
    )
    db.session.add(u)
    db.session.commit()
    return u


def _obra(admin_id):
    suf = uuid.uuid4().hex[:8]
    cliente = Cliente(nome=f'Cliente Diag {suf}', admin_id=admin_id)
    db.session.add(cliente)
    db.session.commit()
    o = Obra(
        nome=f'Obra Diag {suf}', codigo=f'DG-{suf[:8].upper()}',
        data_inicio=date(2026, 1, 1), admin_id=admin_id,
        cliente_id=cliente.id,
    )
    db.session.add(o)
    db.session.commit()
    return o


def test_admin_inexistente_e_reportado_sem_explodir():
    from scripts.diagnostico_cronograma_tenant import diagnosticar

    with app.app_context():
        rel = diagnosticar(999_999_999)
        assert rel['admin_existe'] is False
        assert rel['bloqueios'], 'admin inexistente tem que gerar bloqueio'


def test_tenant_v1_e_apontado_como_bloqueio_total():
    from scripts.diagnostico_cronograma_tenant import diagnosticar

    with app.app_context():
        admin = _admin(versao='v1')
        rel = diagnosticar(admin.id)
        assert rel['versao_sistema'] == 'v1'
        assert rel['v2_ativo'] is False
        codigos = [b['codigo'] for b in rel['bloqueios']]
        assert 'versao_sistema_nao_v2' in codigos
        # É o bloqueio mais grave: esconde o módulo inteiro.
        assert rel['bloqueios'][0]['codigo'] == 'versao_sistema_nao_v2'


def test_tenant_v2_sem_flag_mpp_reporta_apenas_a_aba_de_importacao():
    from scripts.diagnostico_cronograma_tenant import diagnosticar

    with app.app_context():
        admin = _admin(versao='v2')
        rel = diagnosticar(admin.id)
        assert rel['v2_ativo'] is True
        codigos = [b['codigo'] for b in rel['bloqueios']]
        assert 'versao_sistema_nao_v2' not in codigos
        assert 'cronograma_mpp_desligado' in codigos


def test_tenant_v2_com_flag_ligada_nao_tem_bloqueio_de_flag():
    from scripts.diagnostico_cronograma_tenant import diagnosticar

    with app.app_context():
        admin = _admin(versao='v2')
        cfg = ConfiguracaoEmpresa(admin_id=admin.id,
                                  nome_empresa='Diag Ltda')
        cfg.cronograma_mpp_ativo = True
        db.session.add(cfg)
        db.session.commit()

        rel = diagnosticar(admin.id)
        codigos = [b['codigo'] for b in rel['bloqueios']]
        assert 'cronograma_mpp_desligado' not in codigos
        assert rel['cronograma_mpp_ativo'] is True


def test_obra_sem_tarefa_aparece_no_relatorio():
    from scripts.diagnostico_cronograma_tenant import diagnosticar

    with app.app_context():
        admin = _admin(versao='v2')
        obra = _obra(admin.id)
        rel = diagnosticar(admin.id)
        assert rel['obras_total'] >= 1
        assert rel['obras_sem_tarefa'] >= 1
        nomes = [o['nome'] for o in rel['amostra_obras_sem_tarefa']]
        assert obra.nome in nomes


def test_relatorio_conta_servicos_sem_template():
    """Sem template não há caminho automático proposta→obra."""
    from scripts.diagnostico_cronograma_tenant import diagnosticar

    with app.app_context():
        admin = _admin(versao='v2')
        rel = diagnosticar(admin.id)
        assert 'servicos_total' in rel
        assert 'servicos_com_template' in rel
        assert rel['servicos_com_template'] <= rel['servicos_total']
```

- [ ] **Step 2: Rode e confirme a falha**

```bash
python -m pytest tests/test_cronograma_diagnostico_tenant.py -v
```

Esperado: FAIL com `ModuleNotFoundError: No module named 'scripts.diagnostico_cronograma_tenant'`.

- [ ] **Step 3: Escreva o script**

Crie `scripts/diagnostico_cronograma_tenant.py`:

```python
#!/usr/bin/env python3
"""Diagnóstico: por que o cronograma não aparece para este tenant?

Antes deste script, responder essa pergunta exigia abrir o banco. São pelo
menos cinco portas independentes, e a primeira delas esconde o módulo
INTEIRO:

  1. `Usuario.versao_sistema` do ADMIN do tenant precisa ser 'v2'
     (`utils/tenant.py:63-92`). Sem isso, `_check_v2()`
     (`cronograma_views.py:39-46`) faz flash + redirect para o dashboard em
     TODAS as rotas de cronograma, e o menu "Obras → Cronograma" some
     (`templates/base_completo.html:738-748`). Este é o bloqueio nº 1.
  2. `configuracao_empresa.cronograma_mpp_ativo` precisa ser TRUE para a
     aba de importação .mpp/.xml aparecer (`models.py:3620`,
     `templates/obras/detalhes_obra_profissional.html:2134`). Nasce FALSE.
  3. `configuracao_empresa.escopo_obra_ativo` (Fase 1): com a flag ligada,
     usuário sem linha em `usuario_obra` deixa de enxergar a obra.
  4. `obra.cronograma_revisado_em IS NULL` + proposta de origem: a obra cai
     no gate de revisão inicial (`views/obras.py:2339`).
  5. Catálogo: sem `Servico.template_padrao_id` não existe caminho
     automático proposta→obra (`services/cronograma_proposta.py:227`), e a
     obra nasce sem tarefa nenhuma.

Uso:
    python scripts/diagnostico_cronograma_tenant.py <admin_id>
    python scripts/diagnostico_cronograma_tenant.py <admin_id> --json

Como módulo (testes):
    from scripts.diagnostico_cronograma_tenant import diagnosticar
"""
from __future__ import annotations

import argparse
import json as _json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

LIMITE_AMOSTRA = 10


def diagnosticar(admin_id: int) -> dict:
    """Estado de todas as portas de cronograma do tenant. Requer app_context.

    Não escreve nada. Devolve dict com os valores brutos + a lista
    `bloqueios`, ordenada da porta mais grave (esconde o módulo inteiro)
    para a menos grave (esconde um recurso).
    """
    from app import db
    from models import (ConfiguracaoEmpresa, Obra, Servico, TarefaCronograma,
                        Usuario)

    admin = db.session.get(Usuario, admin_id)
    config = ConfiguracaoEmpresa.query.filter_by(admin_id=admin_id).first()

    versao = getattr(admin, 'versao_sistema', None)
    tipo = getattr(getattr(admin, 'tipo_usuario', None), 'name', None)
    v2_ativo = bool(admin is not None and tipo == 'ADMIN' and versao == 'v2')

    mpp_ativo = bool(config is not None
                     and getattr(config, 'cronograma_mpp_ativo', False))
    # Fase 1: a coluna pode não existir se a migration 216 ainda não rodou.
    escopo_existe = hasattr(ConfiguracaoEmpresa, 'escopo_obra_ativo')
    escopo_ativo = bool(escopo_existe and config is not None
                        and getattr(config, 'escopo_obra_ativo', False))

    obras = Obra.query.filter_by(admin_id=admin_id).all()
    obras_ids = [o.id for o in obras]

    com_tarefa = set()
    if obras_ids:
        com_tarefa = {
            row[0] for row in db.session.query(TarefaCronograma.obra_id)
            .filter(TarefaCronograma.obra_id.in_(obras_ids),
                    TarefaCronograma.admin_id == admin_id,
                    TarefaCronograma.is_cliente.is_(False),
                    TarefaCronograma.ativa.is_(True))
            .distinct().all()
        }

    sem_tarefa = [o for o in obras if o.id not in com_tarefa]
    presas_no_gate = [
        o for o in obras
        if getattr(o, 'cronograma_revisado_em', None) is None
        and getattr(o, 'proposta_origem_id', None)
    ]

    servicos = Servico.query.filter_by(admin_id=admin_id).all()
    servicos_com_template = [s for s in servicos if s.template_padrao_id]

    bloqueios = []
    if admin is None:
        bloqueios.append({
            'codigo': 'admin_inexistente',
            'gravidade': 'total',
            'mensagem': f'admin_id={admin_id} não existe na tabela usuario.',
            'como_resolver': 'Confira o id. `SELECT id, email, tipo_usuario, '
                             'versao_sistema FROM usuario WHERE tipo_usuario '
                             "IN ('ADMIN','SUPER_ADMIN');`",
        })
    else:
        if tipo != 'ADMIN':
            bloqueios.append({
                'codigo': 'nao_e_admin_de_tenant',
                'gravidade': 'total',
                'mensagem': f'usuario {admin_id} é {tipo}, não ADMIN. '
                            'is_v2_active() devolve False para SUPER_ADMIN '
                            '(utils/tenant.py:78-79).',
                'como_resolver': 'Rode o diagnóstico com o id do ADMIN do '
                                 'tenant, não com o do SUPER_ADMIN.',
            })
        if not v2_ativo:
            bloqueios.append({
                'codigo': 'versao_sistema_nao_v2',
                'gravidade': 'total',
                'mensagem': f'versao_sistema={versao!r}. Com isso _check_v2() '
                            '(cronograma_views.py:39) redireciona TODAS as '
                            'rotas de cronograma para o dashboard e o menu '
                            'some de base_completo.html:738.',
                'como_resolver': "UPDATE usuario SET versao_sistema='v2' "
                                 f'WHERE id={admin_id};',
            })

        if config is None:
            bloqueios.append({
                'codigo': 'sem_configuracao_empresa',
                'gravidade': 'parcial',
                'mensagem': 'não existe linha em configuracao_empresa para '
                            'este tenant — todas as flags por tenant leem '
                            'como desligadas.',
                'como_resolver': 'python scripts/flag_cronograma_mpp.py '
                                 f'{admin_id} --ligar  (cria a linha)',
            })
        if not mpp_ativo:
            bloqueios.append({
                'codigo': 'cronograma_mpp_desligado',
                'gravidade': 'parcial',
                'mensagem': 'cronograma_mpp_ativo=FALSE — a aba de importação '
                            '.mpp/.xml não aparece na obra '
                            '(detalhes_obra_profissional.html:2134).',
                'como_resolver': 'python scripts/flag_cronograma_mpp.py '
                                 f'{admin_id} --ligar',
            })
        if escopo_ativo:
            bloqueios.append({
                'codigo': 'escopo_obra_ativo',
                'gravidade': 'parcial',
                'mensagem': 'escopo_obra_ativo=TRUE — quem não é ADMIN só '
                            'enxerga obra com linha ativa em usuario_obra.',
                'como_resolver': 'python scripts/flag_escopo_obra.py '
                                 f'{admin_id} --desligar  (ou crie os '
                                 'vínculos em usuario_obra)',
            })
        if presas_no_gate:
            bloqueios.append({
                'codigo': 'obras_no_gate_de_revisao',
                'gravidade': 'parcial',
                'mensagem': f'{len(presas_no_gate)} obra(s) com '
                            'cronograma_revisado_em NULL e proposta de origem '
                            '— o detalhe pode redirecionar para a tela de '
                            'revisão inicial (views/obras.py:2339).',
                'como_resolver': 'Abra a obra e confirme a revisão, ou '
                                 'materialize as tarefas manualmente.',
            })
        if servicos and not servicos_com_template:
            bloqueios.append({
                'codigo': 'nenhum_servico_com_template',
                'gravidade': 'informativo',
                'mensagem': f'{len(servicos)} serviço(s) cadastrado(s), '
                            'nenhum com template_padrao_id — o caminho '
                            'automático proposta→obra não gera tarefa '
                            '(services/cronograma_proposta.py:227). Criação '
                            'MANUAL de tarefa continua funcionando.',
                'como_resolver': 'Defina Servico.template_padrao_id, ou crie '
                                 'as tarefas manualmente no Gantt.',
            })

    ordem = {'total': 0, 'parcial': 1, 'informativo': 2}
    bloqueios.sort(key=lambda b: ordem.get(b['gravidade'], 9))

    return {
        'admin_id': admin_id,
        'admin_existe': admin is not None,
        'email': getattr(admin, 'email', None),
        'tipo_usuario': tipo,
        'versao_sistema': versao,
        'v2_ativo': v2_ativo,
        'tem_configuracao_empresa': config is not None,
        'cronograma_mpp_ativo': mpp_ativo,
        'escopo_obra_coluna_existe': escopo_existe,
        'escopo_obra_ativo': escopo_ativo,
        'obras_total': len(obras),
        'obras_com_tarefa': len(com_tarefa),
        'obras_sem_tarefa': len(sem_tarefa),
        'obras_no_gate_de_revisao': len(presas_no_gate),
        'servicos_total': len(servicos),
        'servicos_com_template': len(servicos_com_template),
        'amostra_obras_sem_tarefa': [
            {'id': o.id, 'nome': o.nome} for o in sem_tarefa[:LIMITE_AMOSTRA]
        ],
        'amostra_obras_no_gate': [
            {'id': o.id, 'nome': o.nome} for o in presas_no_gate[:LIMITE_AMOSTRA]
        ],
        'bloqueios': bloqueios,
    }


def _imprimir(rel: dict) -> None:
    print('=' * 72)
    print(f'DIAGNÓSTICO DE CRONOGRAMA — admin_id={rel["admin_id"]}')
    print('=' * 72)
    if not rel['admin_existe']:
        print('  admin NÃO existe.')
    else:
        print(f'  e-mail ...................: {rel["email"]}')
        print(f'  tipo_usuario .............: {rel["tipo_usuario"]}')
        print(f'  versao_sistema ...........: {rel["versao_sistema"]}')
        print(f'  V2 ativo (módulo visível) : {rel["v2_ativo"]}')
        print(f'  configuracao_empresa .....: '
              f'{"existe" if rel["tem_configuracao_empresa"] else "AUSENTE"}')
        print(f'  cronograma_mpp_ativo .....: {rel["cronograma_mpp_ativo"]}')
        print(f'  escopo_obra_ativo ........: {rel["escopo_obra_ativo"]}'
              f'{"" if rel["escopo_obra_coluna_existe"] else "  (coluna ainda não existe)"}')
        print('  ' + '-' * 68)
        print(f'  obras ....................: {rel["obras_total"]}')
        print(f'    com tarefa .............: {rel["obras_com_tarefa"]}')
        print(f'    SEM tarefa .............: {rel["obras_sem_tarefa"]}')
        print(f'    no gate de revisão .....: {rel["obras_no_gate_de_revisao"]}')
        print(f'  serviços .................: {rel["servicos_total"]}')
        print(f'    com template padrão ....: {rel["servicos_com_template"]}')

    print()
    if not rel['bloqueios']:
        print('NENHUM BLOQUEIO. O cronograma deve estar visível e utilizável.')
        return

    print(f'BLOQUEIOS ({len(rel["bloqueios"])}), do mais grave para o menos:')
    for i, b in enumerate(rel['bloqueios'], 1):
        print(f'\n  {i}. [{b["gravidade"].upper()}] {b["codigo"]}')
        print(f'     {b["mensagem"]}')
        print(f'     → {b["como_resolver"]}')

    if rel['amostra_obras_sem_tarefa']:
        print('\n  Obras sem nenhuma tarefa (amostra):')
        for o in rel['amostra_obras_sem_tarefa']:
            print(f'     id={o["id"]}  {o["nome"]}')
    if rel['amostra_obras_no_gate']:
        print('\n  Obras presas no gate de revisão (amostra):')
        for o in rel['amostra_obras_no_gate']:
            print(f'     id={o["id"]}  {o["nome"]}')


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('admin_id', type=int)
    parser.add_argument('--json', action='store_true',
                        help='imprime o relatório cru em JSON')
    args = parser.parse_args(argv)

    from app import app

    with app.app_context():
        rel = diagnosticar(args.admin_id)

    if args.json:
        print(_json.dumps(rel, indent=2, ensure_ascii=False))
    else:
        _imprimir(rel)

    return 0 if rel['admin_existe'] else 1


if __name__ == '__main__':
    raise SystemExit(main())
```

- [ ] **Step 4: Rode os testes**

```bash
python -m pytest tests/test_cronograma_diagnostico_tenant.py -v
```

Esperado: os 6 testes PASSAM.

- [ ] **Step 5: Rode o diagnóstico de verdade e anote a saída**

```bash
python -c "
from app import app
from models import Usuario, TipoUsuario
with app.app_context():
    for u in Usuario.query.filter(Usuario.tipo_usuario == TipoUsuario.ADMIN).limit(20):
        print(u.id, u.email, u.versao_sistema)
"
```

Escolha o `admin_id` do tenant do Cássio e rode:

```bash
python scripts/diagnostico_cronograma_tenant.py <admin_id>
```

Esperado: o relatório impresso. **Se o primeiro bloqueio for `versao_sistema_nao_v2`, pare e reporte** — a queixa "o cronograma não aparece" é essa flag, e o resto do plano vira melhoria, não correção.

- [ ] **Step 6: Commit**

```bash
git add scripts/diagnostico_cronograma_tenant.py tests/test_cronograma_diagnostico_tenant.py
git commit -m "feat(diag): diagnostico das flags que escondem cronograma por tenant

Responde 'por que o cronograma nao aparece para este cliente' sem abrir o
banco. Reporta versao_sistema (o bloqueio que esconde o modulo inteiro via
_check_v2), cronograma_mpp_ativo, escopo_obra_ativo, obras sem tarefa,
obras presas no gate de revisao e servicos sem template padrao."
```

---

## Task 2: Coluna `tarefa_cronograma.modo_apontamento` (migration 220)

**Files:**
- Modify: `models.py` (dentro de `class TarefaCronograma`, após a linha 4894 — `unidade_medida`)
- Modify: `migrations.py` (nova função antes de `def executar_migracoes():` na linha 3773; registro após a linha 4014)
- Test: `tests/test_cronograma_modo_explicito.py`

- [ ] **Step 1: Escreva o teste que falha**

Crie `tests/test_cronograma_modo_explicito.py`:

```python
"""Modo de apontamento como ESCOLHA da tarefa, não como dedução.

Até 2026-07-21 `services/cronograma_apontamento_service.py:73-82` decidia
sozinho: 'quantidade' quando a tarefa tinha `quantidade_total > 0` E
`unidade_medida` preenchida, 'percentual' caso contrário. O usuário não
escolhia nada — preencher "Quantidade" no modal do Gantt mudava o modo do
RDO como efeito colateral.

Estes testes travam a coluna explícita e, principalmente, travam que a
DEDUÇÃO ANTIGA continua valendo quando a coluna é NULL. Nada pode mudar de
comportamento para as tarefas que já existem.
"""
import os
import sys
import uuid
from datetime import date, timedelta

import pytest
from werkzeug.security import generate_password_hash

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import main  # noqa: F401 — registra os blueprints
from app import app, db
from models import Cliente, Obra, TarefaCronograma, TipoUsuario, Usuario

pytestmark = pytest.mark.integration

D0 = date(2026, 6, 15)


@pytest.fixture(autouse=True)
def _config():
    app.config['TESTING'] = True
    app.config['WTF_CSRF_ENABLED'] = False
    if not app.secret_key:
        app.secret_key = 'test-modo-explicito'
    yield


def _suf() -> str:
    return uuid.uuid4().hex[:10]


@pytest.fixture()
def ctx():
    """Admin V2 + cliente + obra. Obra.cliente_id é NOT NULL."""
    with app.app_context():
        suf = _suf()
        admin = Usuario(
            username=f'modo_{suf}', email=f'modo_{suf}@test.local',
            nome='Modo Explicito',
            password_hash=generate_password_hash('Senha@2026'),
            tipo_usuario=TipoUsuario.ADMIN, ativo=True, versao_sistema='v2',
        )
        db.session.add(admin)
        db.session.flush()
        cliente = Cliente(admin_id=admin.id, nome=f'Cliente Modo {suf}',
                          email=f'cli_modo_{suf}@test.local',
                          telefone='11977776666')
        db.session.add(cliente)
        db.session.flush()
        obra = Obra(
            nome=f'Obra Modo {suf}', codigo=f'MD-{suf[:8].upper()}',
            admin_id=admin.id, cliente_id=cliente.id,
            status='Em andamento', data_inicio=D0 - timedelta(days=60),
        )
        db.session.add(obra)
        db.session.commit()
        yield {'admin_id': admin.id, 'obra_id': obra.id}


def _tarefa(ctx, **kw):
    t = TarefaCronograma(
        obra_id=ctx['obra_id'], admin_id=ctx['admin_id'],
        nome_tarefa=f'Tarefa Modo {_suf()}', ordem=1, responsavel='empresa',
        duracao_dias=kw.pop('duracao_dias', 10),
        data_inicio=kw.pop('data_inicio', D0 - timedelta(days=30)),
        data_fim=kw.pop('data_fim', D0 - timedelta(days=20)),
        **kw,
    )
    db.session.add(t)
    db.session.commit()
    return t


# ---------------------------------------------------------------------------
# Task 2 — a coluna
# ---------------------------------------------------------------------------

def test_tarefa_tem_coluna_modo_apontamento():
    with app.app_context():
        assert hasattr(TarefaCronograma, 'modo_apontamento'), (
            'TarefaCronograma.modo_apontamento não existe — o modo continua '
            'sendo deduzido de quantidade_total + unidade_medida')


def test_modo_apontamento_nasce_nulo(ctx):
    """NULL = 'ninguém escolheu' = dedução antiga. É o default de propósito."""
    t = _tarefa(ctx, quantidade_total=100.0, unidade_medida='m2')
    assert t.modo_apontamento is None


def test_modo_apontamento_persiste(ctx):
    t = _tarefa(ctx, quantidade_total=100.0, unidade_medida='m2',
                modo_apontamento='percentual')
    tid = t.id
    db.session.expire_all()
    assert db.session.get(TarefaCronograma, tid).modo_apontamento == 'percentual'


def test_modo_apontamento_recusa_valor_fora_do_dominio(ctx):
    """CHECK no banco: só 'quantidade' ou 'percentual'."""
    from sqlalchemy.exc import DataError, IntegrityError

    with pytest.raises((IntegrityError, DataError)):
        _tarefa(ctx, quantidade_total=1.0, modo_apontamento='qualquer')
    db.session.rollback()
```

- [ ] **Step 2: Rode e confirme a falha**

```bash
python -m pytest tests/test_cronograma_modo_explicito.py -v
```

Esperado: FAIL. `test_tarefa_tem_coluna_modo_apontamento` falha com o `AssertionError` da mensagem; os outros falham com `TypeError: 'modo_apontamento' is an invalid keyword argument for TarefaCronograma`.

- [ ] **Step 3: Adicione a coluna ao modelo**

Em `models.py`, dentro de `class TarefaCronograma`, imediatamente após a linha 4894 (`unidade_medida = db.Column(db.String(20), nullable=True)`), insira:

```python
    # Modo de apontamento ESCOLHIDO para esta tarefa: 'quantidade' (o RDO
    # pede quantidade do dia na unidade da tarefa) ou 'percentual' (o RDO
    # pede o % acumulado). Até 2026-07-21 isso não era escolha: era
    # deduzido em `services/cronograma_apontamento_service.modo_da_tarefa`
    # a partir de `quantidade_total > 0 AND unidade_medida != ''`, ou seja,
    # preencher "Quantidade" no modal do Gantt mudava o modo do RDO como
    # efeito colateral. A queixa do dono em 21/07/2026 — "RDO em
    # porcentagem" — é exatamente isso.
    #
    # NULL significa "ninguém escolheu" e mantém a dedução antiga
    # (`_modo_deduzido`). É o default de propósito: o importador .mpp
    # (services/cronograma_versao_service.py:534) e qualquer construção
    # direta do modelo continuam se comportando como sempre.
    #
    # Vocabulário: mesmo de `modo_da_tarefa()` e do JSON `tipo_modo` que a
    # UI do RDO já consome (templates/rdo/novo.html:1118). NÃO confundir
    # com `RDOApontamentoCronograma.tipo_apontamento` (models.py:4994), que
    # usa 'quantitativo'/'percentual' e descreve a LINHA de apontamento,
    # não a tarefa.
    #
    # Marco (`is_marco`) ignora esta coluna e é sempre percentual binário —
    # o guard vem antes da leitura, em `modo_da_tarefa`.
    modo_apontamento = db.Column(db.String(12), nullable=True)
```

- [ ] **Step 4: Escreva a migration 220**

Em `migrations.py`, imediatamente antes de `def executar_migracoes():` (linha 3773), insira:

```python
def migration_220_tarefa_modo_apontamento():
    """Coluna tarefa_cronograma.modo_apontamento ('quantidade'|'percentual').

    Aditiva, idempotente e SEM backfill: a coluna nasce NULL em todas as
    linhas, e NULL significa "ninguém escolheu" — `modo_da_tarefa` continua
    deduzindo exatamente como antes. O backfill que congela o modo atual é a
    migration 221, separada de propósito: se algo der errado nela, a coluna
    já está no lugar e nada de comportamento mudou.

    O CHECK impede que qualquer caminho grave lixo na coluna. Não é
    redundante com a validação de aplicação: `cronograma_views.atualizar_tarefa`
    escreve string vinda de JSON.
    """
    logger.info("[Migration 220] Iniciando — tarefa_cronograma.modo_apontamento")

    db.session.execute(text("""
        ALTER TABLE tarefa_cronograma
        ADD COLUMN IF NOT EXISTS modo_apontamento VARCHAR(12)
    """))
    db.session.commit()

    existe_check = db.session.execute(text("""
        SELECT 1 FROM information_schema.table_constraints
        WHERE constraint_name = 'ck_tarefa_cronograma_modo_apontamento'
          AND table_name = 'tarefa_cronograma'
        LIMIT 1
    """)).fetchone()
    if not existe_check:
        db.session.execute(text("""
            ALTER TABLE tarefa_cronograma
            ADD CONSTRAINT ck_tarefa_cronograma_modo_apontamento
            CHECK (modo_apontamento IS NULL
                   OR modo_apontamento IN ('quantidade', 'percentual'))
        """))
        db.session.commit()
        logger.info("[Migration 220] CHECK ck_tarefa_cronograma_modo_apontamento criado")

    logger.info("[Migration 220] Concluída com sucesso")
```

- [ ] **Step 5: Registre a migration**

Em `migrations.py`, na lista `migrations_to_run`, imediatamente após a linha 4014 (a entrada `213`), adicione:

```python
            (220, "Cronograma editável — tarefa_cronograma.modo_apontamento (quantidade|percentual, NULL = dedução legada)", migration_220_tarefa_modo_apontamento),
```

> Se a Fase 1 já tiver registrado as entradas 214–216, mantenha a ordem numérica: a 220 entra **depois** delas.

- [ ] **Step 6: Aplique a migration e rode os testes**

```bash
python -c "
from app import app
from migrations import executar_migracoes
with app.app_context():
    executar_migracoes()
" 2>&1 | grep -E "220|ERRO|ERROR"
python -m pytest tests/test_cronograma_modo_explicito.py -v
```

Esperado: log `[Migration 220] Concluída com sucesso` e os 4 testes PASSAM.

- [ ] **Step 7: Commit**

```bash
git add models.py migrations.py tests/test_cronograma_modo_explicito.py
git commit -m "feat(cronograma): coluna modo_apontamento na tarefa (migration 220)

O modo do RDO deixa de ser deduzido de quantidade_total+unidade_medida e
passa a caber na tarefa. Coluna nullable com CHECK; NULL mantem a deducao
antiga, entao esta migration nao muda comportamento de nada."
```

---

## Task 3: Backfill que congela o modo atual (migration 221)

O objetivo é que a migração seja, por construção, um **no-op de comportamento**: cada tarefa recebe exatamente o modo que `modo_da_tarefa()` devolveria hoje.

**Files:**
- Modify: `migrations.py` (nova função antes de `def executar_migracoes():`; registro após a entrada 220)
- Test: `tests/test_cronograma_modo_explicito.py` (acrescenta)

- [ ] **Step 1: Escreva o teste que falha**

Acrescente ao final de `tests/test_cronograma_modo_explicito.py`:

```python
# ---------------------------------------------------------------------------
# Task 3 — backfill congela o modo deduzido HOJE
# ---------------------------------------------------------------------------

def _backfill():
    from migrations import migration_221_backfill_modo_apontamento
    migration_221_backfill_modo_apontamento()


@pytest.mark.parametrize('kwargs,esperado,porque', [
    ({'quantidade_total': 100.0, 'unidade_medida': 'm2'}, 'quantidade',
     'quantidade + unidade => quantitativa (regra antiga)'),
    ({'quantidade_total': 100.0, 'unidade_medida': None}, 'percentual',
     'quantidade SEM unidade => percentual (regra antiga)'),
    ({'quantidade_total': 100.0, 'unidade_medida': '   '}, 'percentual',
     'unidade só com espaços conta como vazia (regra antiga usa .strip())'),
    ({'quantidade_total': 0.0, 'unidade_medida': 'm2'}, 'percentual',
     'quantidade zero => percentual (regra antiga)'),
    ({'quantidade_total': None, 'unidade_medida': None}, 'percentual',
     'sem quantidade => percentual'),
])
def test_backfill_grava_exatamente_o_modo_deduzido_hoje(ctx, kwargs, esperado,
                                                        porque):
    from services.cronograma_apontamento_service import _modo_deduzido

    t = _tarefa(ctx, **kwargs)
    assert _modo_deduzido(t) == esperado, f'premissa quebrada: {porque}'
    tid = t.id

    _backfill()
    db.session.expire_all()
    assert db.session.get(TarefaCronograma, tid).modo_apontamento == esperado, (
        f'backfill divergiu da dedução: {porque}')


def test_backfill_marco_sempre_percentual(ctx):
    """Mesmo com quantidade + unidade, marco é percentual binário."""
    m = _tarefa(ctx, quantidade_total=100.0, unidade_medida='m2',
                is_marco=True, duracao_dias=0)
    mid = m.id
    _backfill()
    db.session.expire_all()
    assert db.session.get(TarefaCronograma, mid).modo_apontamento == 'percentual'


def test_backfill_nao_sobrescreve_escolha_existente(ctx):
    """Idempotência: quem já escolheu não é reclassificado."""
    t = _tarefa(ctx, quantidade_total=100.0, unidade_medida='m2',
                modo_apontamento='percentual')
    tid = t.id
    _backfill()
    db.session.expire_all()
    assert db.session.get(TarefaCronograma, tid).modo_apontamento == 'percentual'


def test_backfill_e_idempotente(ctx):
    t = _tarefa(ctx, quantidade_total=50.0, unidade_medida='un')
    tid = t.id
    _backfill()
    db.session.expire_all()
    primeiro = db.session.get(TarefaCronograma, tid).modo_apontamento
    _backfill()
    db.session.expire_all()
    assert db.session.get(TarefaCronograma, tid).modo_apontamento == primeiro
```

- [ ] **Step 2: Rode e confirme a falha**

```bash
python -m pytest tests/test_cronograma_modo_explicito.py -v -k backfill
```

Esperado: FAIL com `ImportError: cannot import name 'migration_221_backfill_modo_apontamento' from 'migrations'` (e, para os `parametrize`, também `cannot import name '_modo_deduzido'` — a Task 4 cria essa função; execute a Task 4 **antes** de rodar o Step 4 desta task, ou aceite a falha parcial aqui).

> **Ordem de execução:** este teste depende de `_modo_deduzido`, criado na Task 4. Escreva a migration agora (Step 3), registre (Step 4) e rode a suíte completa desta task só no Step 6 da Task 4. O Step 5 abaixo aplica a migration, que não depende de Python novo.

- [ ] **Step 3: Escreva a migration 221**

Em `migrations.py`, imediatamente após `migration_220_tarefa_modo_apontamento` (antes de `def executar_migracoes():`), insira:

```python
def migration_221_backfill_modo_apontamento():
    """Congela em tarefa_cronograma.modo_apontamento o modo que
    `services.cronograma_apontamento_service.modo_da_tarefa` devolveria HOJE.

    Esta migration é, por construção, um NO-OP DE COMPORTAMENTO: o CASE
    abaixo é a transcrição literal de `modo_da_tarefa` (linhas 77-82 daquele
    arquivo), incluindo os dois detalhes fáceis de perder:

      * marco é SEMPRE 'percentual', mesmo com quantidade e unidade
        preenchidas (guard `if getattr(tarefa, 'is_marco', False)` vem antes
        de tudo);
      * a unidade passa por `.strip()` — unidade só com espaços conta como
        vazia, logo a tarefa é percentual.

    ATENÇÃO: a regra aqui é DIFERENTE da usada no backfill da migration 210
    (migrations.py:14090), que classificou `rdo_apontamento_cronograma`
    olhando só `quantidade_total > 0`, sem unidade e sem marco. As duas
    coexistem de propósito: a 210 descreve linhas de apontamento já
    gravadas (histórico, imutável); esta descreve o modo da TAREFA daqui
    para frente.

    Só toca linhas com `modo_apontamento IS NULL` — quem já escolheu não é
    reclassificado. Idempotente.
    """
    logger.info("[Migration 221] Iniciando — backfill de modo_apontamento")

    resultado = db.session.execute(text("""
        UPDATE tarefa_cronograma
        SET modo_apontamento = CASE
            WHEN is_marco IS TRUE THEN 'percentual'
            WHEN quantidade_total IS NOT NULL
                 AND quantidade_total > 0
                 AND unidade_medida IS NOT NULL
                 AND btrim(unidade_medida) <> ''
            THEN 'quantidade'
            ELSE 'percentual'
        END
        WHERE modo_apontamento IS NULL
    """))
    db.session.commit()

    totais = db.session.execute(text("""
        SELECT modo_apontamento, COUNT(*)
        FROM tarefa_cronograma
        GROUP BY modo_apontamento
        ORDER BY modo_apontamento
    """)).fetchall()

    logger.info(f"[Migration 221] {resultado.rowcount} tarefa(s) classificada(s)")
    for modo, qtd in totais:
        logger.info(f"[Migration 221]   modo_apontamento={modo!r}: {qtd}")
    logger.info("[Migration 221] Concluída com sucesso")
```

- [ ] **Step 4: Registre a migration**

Em `migrations.py`, na lista `migrations_to_run`, logo após a entrada `220`, adicione:

```python
            (221, "Cronograma editável — backfill de modo_apontamento congelando a dedução vigente (no-op de comportamento)", migration_221_backfill_modo_apontamento),
```

- [ ] **Step 5: Aplique a migration**

```bash
python -c "
from app import app
from migrations import executar_migracoes
with app.app_context():
    executar_migracoes()
" 2>&1 | grep -E "22[01]|ERRO|ERROR"
```

Esperado: `[Migration 221] N tarefa(s) classificada(s)` seguido das contagens por modo e `[Migration 221] Concluída com sucesso`. **Anote os dois números** — eles vão no corpo do commit e são a evidência de que o backfill fez o que se esperava.

- [ ] **Step 6: Commit**

```bash
git add migrations.py tests/test_cronograma_modo_explicito.py
git commit -m "feat(cronograma): backfill de modo_apontamento (migration 221)

Grava em cada tarefa exatamente o modo que modo_da_tarefa() devolveria
hoje — incluindo marco sempre percentual e unidade com .strip(). Por
construcao nao muda comportamento de nenhuma obra existente. Nao
sobrescreve escolha ja feita; idempotente."
```

---

## Task 4: `modo_da_tarefa` passa a ler a coluna (dedução vira fallback)

**Files:**
- Modify: `services/cronograma_apontamento_service.py:73-82`
- Test: `tests/test_cronograma_modo_explicito.py` (acrescenta)

- [ ] **Step 1: Escreva o teste que falha**

Acrescente ao final de `tests/test_cronograma_modo_explicito.py`:

```python
# ---------------------------------------------------------------------------
# Task 4 — resolução do modo
# ---------------------------------------------------------------------------

def test_coluna_vence_a_deducao(ctx):
    """O ponto do plano: a escolha do usuário manda."""
    from services.cronograma_apontamento_service import modo_da_tarefa

    # Tarefa que a dedução chamaria de 'quantidade', marcada como percentual.
    t = _tarefa(ctx, quantidade_total=250.0, unidade_medida='m2',
                modo_apontamento='percentual')
    assert modo_da_tarefa(t) == 'percentual'

    # E o inverso: sem quantidade nenhuma, mas marcada como quantidade.
    t2 = _tarefa(ctx, quantidade_total=None, unidade_medida=None,
                 modo_apontamento='quantidade')
    assert modo_da_tarefa(t2) == 'quantidade'


def test_coluna_nula_cai_na_deducao_antiga(ctx):
    from services.cronograma_apontamento_service import modo_da_tarefa

    assert modo_da_tarefa(
        _tarefa(ctx, quantidade_total=100.0, unidade_medida='m2')) == 'quantidade'
    assert modo_da_tarefa(
        _tarefa(ctx, quantidade_total=100.0, unidade_medida=None)) == 'percentual'
    assert modo_da_tarefa(
        _tarefa(ctx, quantidade_total=None)) == 'percentual'


def test_marco_ignora_a_coluna(ctx):
    """Marco é binário; nem o usuário pode torná-lo quantitativo."""
    from services.cronograma_apontamento_service import modo_da_tarefa

    m = _tarefa(ctx, quantidade_total=100.0, unidade_medida='m2',
                is_marco=True, duracao_dias=0, modo_apontamento='quantidade')
    assert modo_da_tarefa(m) == 'percentual'


def test_valor_invalido_na_coluna_cai_na_deducao(ctx):
    """Falha tolerante: lixo na coluna não pode derrubar o RDO.

    O CHECK do banco impede gravar lixo, mas o objeto em memória pode ter
    qualquer coisa antes do flush — e `modo_da_tarefa` é chamado dentro do
    laço de montagem de `tarefas_rdo` (cronograma_views.py:917), que serve
    a tela inteira.
    """
    from services.cronograma_apontamento_service import modo_da_tarefa

    t = _tarefa(ctx, quantidade_total=100.0, unidade_medida='m2')
    t.modo_apontamento = 'lixo'
    assert modo_da_tarefa(t) == 'quantidade'
    db.session.rollback()


def test_modo_da_tarefa_aceita_objeto_sem_o_atributo(ctx):
    """Robustez: o serviço é chamado com objetos leves em alguns caminhos."""
    from services.cronograma_apontamento_service import modo_da_tarefa

    class TarefaFalsa:
        is_marco = False
        quantidade_total = 10.0
        unidade_medida = 'm'

    assert modo_da_tarefa(TarefaFalsa()) == 'quantidade'


def test_modos_validos_e_o_contrato_publico():
    from services.cronograma_apontamento_service import MODOS_APONTAMENTO

    assert MODOS_APONTAMENTO == ('quantidade', 'percentual')
```

- [ ] **Step 2: Rode e confirme a falha**

```bash
python -m pytest tests/test_cronograma_modo_explicito.py -v -k "coluna or marco_ignora or invalido or objeto_sem or MODOS or modos_validos"
```

Esperado: FAIL — `test_coluna_vence_a_deducao` devolve `'quantidade'` em vez de `'percentual'`, e `test_modos_validos_e_o_contrato_publico` falha com `ImportError: cannot import name 'MODOS_APONTAMENTO'`.

- [ ] **Step 3: Reescreva `modo_da_tarefa`**

Em `services/cronograma_apontamento_service.py`, substitua o bloco das linhas 73-82 inteiro por:

```python
# Domínio do modo de apontamento da TAREFA. Vocabulário deliberadamente
# igual ao que `modo_da_tarefa` já devolvia e ao JSON `tipo_modo` que a UI
# do RDO consome (templates/rdo/novo.html:1118). NÃO confundir com
# `RDOApontamentoCronograma.tipo_apontamento` ('quantitativo'|'percentual'),
# que descreve a LINHA de apontamento — models.py:4994.
MODOS_APONTAMENTO = ('quantidade', 'percentual')


def _modo_deduzido(tarefa) -> str:
    """Regra ANTIGA, preservada literalmente como fallback.

    Era o corpo inteiro de `modo_da_tarefa` até 2026-07-21: sem coluna para
    guardar a escolha, o modo saía de `quantidade_total > 0` E
    `unidade_medida` não-vazia. Continua valendo para toda tarefa com
    `modo_apontamento IS NULL` — o importador .mpp
    (services/cronograma_versao_service.py:534) não preenche a coluna, e
    qualquer construção direta do modelo também não.
    """
    if (tarefa.quantidade_total and float(tarefa.quantidade_total) > 0
            and (tarefa.unidade_medida or '').strip()):
        return 'quantidade'
    return 'percentual'


def modo_da_tarefa(tarefa) -> str:
    """Modo de apontamento que a UI deve oferecer para a tarefa (spec §4.1).

    Ordem de resolução, do mais forte para o mais fraco:

      1. **marco** → 'percentual' sempre. Marco é binário (0 ou 100) e a
         validação `MarcoApenasZeroOuCem` depende disso. Nem a escolha
         explícita do usuário sobrepõe.
      2. **escolha explícita** em `tarefa.modo_apontamento` (coluna criada
         na migration 220). É o ponto do requisito "RDO em porcentagem":
         uma tarefa com quantitativo levantado pode, ainda assim, ser
         apontada em %.
      3. **dedução legada** (`_modo_deduzido`) quando a coluna é NULL ou
         traz valor fora do domínio.

    Falha tolerante no passo 3: valor inválido não levanta. Esta função roda
    dentro do laço que monta a tela inteira de apontamento
    (`cronograma_views.py:917`); uma linha corrompida não pode derrubar o
    RDO do dia.
    """
    if getattr(tarefa, 'is_marco', False):
        return 'percentual'

    escolhido = (getattr(tarefa, 'modo_apontamento', None) or '').strip().lower()
    if escolhido in MODOS_APONTAMENTO:
        return escolhido

    return _modo_deduzido(tarefa)
```

- [ ] **Step 4: Rode os testes desta task e da Task 3**

```bash
python -m pytest tests/test_cronograma_modo_explicito.py -v
```

Esperado: todos os testes do arquivo PASSAM (Task 2 + Task 3 + Task 4).

- [ ] **Step 5: Rode a caracterização — nada pode ter mudado**

```bash
python -m pytest tests/test_caracterizacao_apontamento_cronograma.py \
                 tests/test_cronograma_apontamento_service.py \
                 tests/test_rdo_modos_apontamento.py \
                 tests/test_rdo_recomputo_cadeia.py -v
```

Esperado: **tudo verde, sem exceção.** Esses arquivos congelam o comportamento anterior; se algum quebrar, a mudança não é neutra e o passo tem que ser revisto — não o teste.

- [ ] **Step 6: Commit**

```bash
git add services/cronograma_apontamento_service.py tests/test_cronograma_modo_explicito.py
git commit -m "feat(cronograma): modo_da_tarefa passa a respeitar a escolha da tarefa

Ordem: marco > coluna modo_apontamento > deducao legada (_modo_deduzido,
corpo antigo preservado literal). Coluna NULL mantem o comportamento de
sempre. Caracterizacao do M1/M07 permanece verde."
```

---

## Task 5: `recomputar_cadeia` usa o modo da tarefa, não `quantidade_total > 0`

Fecha a divergência documentada no achado nº 4. Na prática é quase um no-op — a migration 210 preencheu `tipo_apontamento` em todas as linhas antigas e `registrar_apontamento` o grava em toda escrita nova (`services/cronograma_apontamento_service.py:324`) — mas deixar duas regras diferentes no mesmo arquivo é dívida garantida.

**Files:**
- Modify: `services/cronograma_apontamento_service.py:158-161`
- Test: `tests/test_cronograma_modo_explicito.py` (acrescenta)

- [ ] **Step 1: Escreva o teste que falha**

Acrescente ao final de `tests/test_cronograma_modo_explicito.py`:

```python
# ---------------------------------------------------------------------------
# Task 5 — recomputo usa o mesmo classificador da UI
# ---------------------------------------------------------------------------

def _rdo(ctx, data_rdo):
    from models import RDO
    r = RDO(numero_rdo=f'MD-{_suf()[:12]}', obra_id=ctx['obra_id'],
            admin_id=ctx['admin_id'], data_relatorio=data_rdo,
            local='Campo', status='Finalizado')
    db.session.add(r)
    db.session.commit()
    return r


def test_recomputo_classifica_linha_antiga_pelo_modo_da_tarefa(ctx):
    """Linha pré-M02 (tipo_apontamento NULL) numa tarefa marcada percentual.

    Antes desta task o fallback de `recomputar_cadeia` olhava só
    `quantidade_total > 0` e chamaria a linha de 'quantitativo', divergindo
    do que a UI mostra (`modo_da_tarefa`).
    """
    from models import RDOApontamentoCronograma
    from services.cronograma_apontamento_service import recomputar_cadeia

    t = _tarefa(ctx, quantidade_total=100.0, unidade_medida='m2',
                modo_apontamento='percentual')
    r = _rdo(ctx, D0)
    ap = RDOApontamentoCronograma(
        rdo_id=r.id, tarefa_cronograma_id=t.id, admin_id=ctx['admin_id'],
        quantidade_executada_dia=0.0, quantidade_acumulada=0.0,
        percentual_realizado=42.0,
        tipo_apontamento=None,          # linha pré-M02
        percentual_acumulado=42.0,
    )
    db.session.add(ap)
    db.session.commit()

    recomputar_cadeia(t.id, D0, ctx['admin_id'])
    db.session.flush()

    assert ap.percentual_realizado == 42.0, (
        'a linha foi tratada como quantitativa: 0/100 zerou o percentual')
    assert ap.percentual_acumulado == 42.0


def test_recomputo_quantitativo_continua_igual(ctx):
    """Guarda de não-regressão do caminho quantitativo."""
    from services.cronograma_apontamento_service import (recomputar_cadeia,
                                                         registrar_apontamento)

    t = _tarefa(ctx, quantidade_total=200.0, unidade_medida='m2',
                modo_apontamento='quantidade')
    r1 = _rdo(ctx, D0 - timedelta(days=2))
    r2 = _rdo(ctx, D0)
    registrar_apontamento(r1, t, quantidade_dia=50.0, admin_id=ctx['admin_id'])
    ap2 = registrar_apontamento(r2, t, quantidade_dia=30.0,
                                admin_id=ctx['admin_id'])
    db.session.commit()

    recomputar_cadeia(t.id, D0 - timedelta(days=2), ctx['admin_id'])
    db.session.flush()
    assert ap2.quantidade_acumulada == 80.0
    assert ap2.percentual_realizado == 40.0
```

- [ ] **Step 2: Rode e confirme a falha**

```bash
python -m pytest tests/test_cronograma_modo_explicito.py -v -k recomputo
```

Esperado: FAIL em `test_recomputo_classifica_linha_antiga_pelo_modo_da_tarefa` — `percentual_realizado` vira `0.0` porque a linha foi tratada como quantitativa (`acum=0`, `total=100`).

- [ ] **Step 3: Corrija o classificador**

Em `services/cronograma_apontamento_service.py`, dentro de `recomputar_cadeia`, substitua as linhas 158-161:

```python
        # Mesma regra de classificação do backfill (migration 210).
        tipo = ap.tipo_apontamento or (
            'quantitativo' if (tarefa.quantidade_total or 0) > 0
            else 'percentual')
```

por:

```python
        # Classificação de linha SEM `tipo_apontamento` (só as anteriores à
        # migration 209 — de lá para cá `registrar_apontamento` grava sempre,
        # ver linha 324). O fallback antigo era `quantidade_total > 0`, a
        # mesma regra do backfill da migration 210, mas DIFERENTE da que a UI
        # usa: `modo_da_tarefa` também exige unidade e trata marco. Uma
        # tarefa com quantidade e sem unidade era 'percentual' na tela e
        # 'quantitativo' aqui. Agora as duas pontas usam o mesmo resolver —
        # que, desde a migration 220, respeita a escolha do usuário.
        tipo = ap.tipo_apontamento or (
            'quantitativo' if modo_da_tarefa(tarefa) == 'quantidade'
            else 'percentual')
```

- [ ] **Step 4: Rode os testes**

```bash
python -m pytest tests/test_cronograma_modo_explicito.py -v
python -m pytest tests/test_rdo_recomputo_cadeia.py tests/test_caracterizacao_apontamento_cronograma.py -v
```

Esperado: tudo PASSA.

- [ ] **Step 5: Commit**

```bash
git add services/cronograma_apontamento_service.py tests/test_cronograma_modo_explicito.py
git commit -m "fix(cronograma): recomputar_cadeia usa o mesmo classificador da UI

Havia duas regras para 'esta tarefa e quantitativa': modo_da_tarefa exigia
quantidade E unidade e tratava marco; o fallback do recomputo olhava so
quantidade_total>0. Tarefa com quantidade sem unidade era percentual na
tela e quantitativa no recomputo."
```

---

## Task 6: Apontar em modo divergente do escolhido devolve 422

Só vale quando o modo foi **escolhido de fato** (coluna não-NULL). Ver Decisão D3 — enforcement incondicional quebraria `tests/test_cronograma_apontamento_service.py:101,115,138,212,234`.

**Files:**
- Modify: `services/cronograma_apontamento_service.py` (nova exceção após a linha 70; guard dentro de `registrar_apontamento`, após a linha 209)
- Test: `tests/test_cronograma_modo_explicito.py` (acrescenta)

- [ ] **Step 1: Escreva o teste que falha**

Acrescente ao final de `tests/test_cronograma_modo_explicito.py`:

```python
# ---------------------------------------------------------------------------
# Task 6 — o modo escolhido é respeitado na escrita
# ---------------------------------------------------------------------------

def test_quantidade_em_tarefa_marcada_percentual_e_recusada(ctx):
    from services.cronograma_apontamento_service import (ModoIncompativel,
                                                         registrar_apontamento)

    t = _tarefa(ctx, quantidade_total=100.0, unidade_medida='m2',
                modo_apontamento='percentual')
    with pytest.raises(ModoIncompativel):
        registrar_apontamento(_rdo(ctx, D0), t, quantidade_dia=10.0,
                              admin_id=ctx['admin_id'])
    db.session.rollback()


def test_percentual_em_tarefa_marcada_quantidade_e_recusado(ctx):
    from services.cronograma_apontamento_service import (ModoIncompativel,
                                                         registrar_apontamento)

    t = _tarefa(ctx, quantidade_total=100.0, unidade_medida='m2',
                modo_apontamento='quantidade')
    with pytest.raises(ModoIncompativel):
        registrar_apontamento(_rdo(ctx, D0), t, percentual_acumulado=30.0,
                              admin_id=ctx['admin_id'])
    db.session.rollback()


def test_sem_escolha_explicita_nada_e_recusado(ctx):
    """Decisão D3: coluna NULL => tolerância legada, os dois modos passam.

    É o que mantém verdes as fixtures que criam tarefa com
    quantidade_total sem unidade e apontam com quantidade_dia
    (tests/test_cronograma_apontamento_service.py:101).
    """
    from services.cronograma_apontamento_service import registrar_apontamento

    t = _tarefa(ctx, quantidade_total=100.0, unidade_medida=None)
    assert t.modo_apontamento is None
    ap = registrar_apontamento(_rdo(ctx, D0), t, quantidade_dia=10.0,
                               admin_id=ctx['admin_id'])
    db.session.commit()
    assert ap.tipo_apontamento == 'quantitativo'


def test_marco_continua_aceitando_percentual(ctx):
    """Marco resolve para 'percentual' antes de olhar a coluna."""
    from services.cronograma_apontamento_service import registrar_apontamento

    m = _tarefa(ctx, quantidade_total=None, is_marco=True, duracao_dias=0,
                modo_apontamento='percentual')
    ap = registrar_apontamento(_rdo(ctx, D0), m, percentual_acumulado=100.0,
                               admin_id=ctx['admin_id'])
    db.session.commit()
    assert ap.percentual_realizado == 100.0


def test_modo_incompativel_e_valueerror(ctx):
    """Contrato do módulo: os laços legados de views/rdo.py protegem com
    `except (ValueError, TypeError)`. A exceção nova precisa cair ali, senão
    um item divergente derruba o RDO inteiro (views/rdo.py:4635)."""
    from services.cronograma_apontamento_service import ModoIncompativel

    assert issubclass(ModoIncompativel, ValueError)


def test_apontar_producao_devolve_422_no_modo_errado(ctx):
    """Caminho HTTP: cronograma_views.py:1203 mapeia ApontamentoInvalido→422."""
    t = _tarefa(ctx, quantidade_total=100.0, unidade_medida='m2',
                modo_apontamento='percentual')
    r = _rdo(ctx, D0)
    tid, rid, aid = t.id, r.id, ctx['admin_id']

    c = app.test_client()
    with c.session_transaction() as sess:
        sess['_user_id'] = str(aid)
        sess['_fresh'] = True

    resp = c.post(f'/cronograma/rdo/{rid}/apontar',
                  json={'tarefa_cronograma_id': tid,
                        'quantidade_executada_dia': 5.0})
    assert resp.status_code == 422, resp.get_data(as_text=True)[:400]
```

- [ ] **Step 2: Rode e confirme a falha**

```bash
python -m pytest tests/test_cronograma_modo_explicito.py -v -k "incompativel or marcada or sem_escolha or 422"
```

Esperado: FAIL com `ImportError: cannot import name 'ModoIncompativel'`.

- [ ] **Step 3: Adicione a exceção**

Em `services/cronograma_apontamento_service.py`, imediatamente após a classe `MarcoApenasZeroOuCem` (linha 70), insira:

```python
class ModoIncompativel(ApontamentoInvalido):
    """Apontamento enviado num modo diferente do ESCOLHIDO para a tarefa.

    Só dispara quando alguém escolheu de fato — `tarefa.modo_apontamento`
    não-NULL (coluna da migration 220). Tarefa com a coluna NULL mantém a
    tolerância de sempre: os dois modos são aceitos e o `tipo_apontamento`
    da linha sai do argumento recebido. Ver Decisão D3 do plano
    `2026-07-21-cronograma-editavel-rdo-percentual.md`: enforcement
    incondicional quebraria as fixtures de caracterização, que criam tarefa
    com `quantidade_total` sem `unidade_medida` e apontam com
    `quantidade_dia` (tests/test_cronograma_apontamento_service.py:101).
    """
```

- [ ] **Step 4: Adicione o guard em `registrar_apontamento`**

Em `services/cronograma_apontamento_service.py`, dentro de `registrar_apontamento`, imediatamente após o bloco do XOR (que termina na linha 209 com `)`) e **antes** de `from sqlalchemy import func as sqlfunc`, insira:

```python
    # Guard de modo: honra a ESCOLHA do usuário. Marco não entra aqui —
    # `modo_da_tarefa` já resolve marco para 'percentual' antes de olhar a
    # coluna, e a validação binária é a MarcoApenasZeroOuCem mais abaixo.
    modo_escolhido = (getattr(tarefa, 'modo_apontamento', None) or '').strip().lower()
    if modo_escolhido in MODOS_APONTAMENTO and not getattr(tarefa, 'is_marco', False):
        if quantidade_dia is not None and modo_escolhido != 'quantidade':
            raise ModoIncompativel(
                f'A tarefa "{tarefa.nome_tarefa}" está configurada para '
                f'apontamento em PERCENTUAL — envie o % acumulado, não '
                f'quantidade.')
        if percentual_acumulado is not None and modo_escolhido != 'percentual':
            raise ModoIncompativel(
                f'A tarefa "{tarefa.nome_tarefa}" está configurada para '
                f'apontamento por QUANTIDADE ({tarefa.unidade_medida or "un"}) '
                f'— envie a quantidade do dia, não percentual.')
```

- [ ] **Step 5: Rode os testes**

```bash
python -m pytest tests/test_cronograma_modo_explicito.py -v
python -m pytest tests/test_caracterizacao_apontamento_cronograma.py \
                 tests/test_cronograma_apontamento_service.py \
                 tests/test_rdo_modos_apontamento.py -v
```

Esperado: tudo PASSA. Se algum teste de caracterização quebrar, o guard escapou do escopo "só quando a coluna está preenchida" — reveja o `if`.

- [ ] **Step 6: Commit**

```bash
git add services/cronograma_apontamento_service.py tests/test_cronograma_modo_explicito.py
git commit -m "feat(cronograma): apontar no modo errado devolve 422 (ModoIncompativel)

So vale quando o modo foi escolhido de fato (coluna nao-NULL); tarefa sem
escolha mantem a tolerancia legada, que e o que sustenta as fixtures de
caracterizacao. ModoIncompativel e ValueError, entao o laco legado de
views/rdo.py degrada para warning em vez de derrubar o RDO."
```

---

## Task 7: A API do cronograma aceita e devolve `modo_apontamento`

**Files:**
- Modify: `cronograma_views.py:53-79` (`_tarefa_to_dict`, linha 68)
- Modify: `cronograma_views.py:271-436` (`criar_tarefa`)
- Modify: `cronograma_views.py:452-...` (`atualizar_tarefa`)
- Modify: `cronograma_views.py:917-946` (bloco de montagem do item em `tarefas_rdo`)
- Test: `tests/test_cronograma_modo_explicito.py` (acrescenta)

- [ ] **Step 1: Escreva o teste que falha**

Acrescente ao final de `tests/test_cronograma_modo_explicito.py`:

```python
# ---------------------------------------------------------------------------
# Task 7 — contrato HTTP
# ---------------------------------------------------------------------------

def _cliente(admin_id):
    c = app.test_client()
    with c.session_transaction() as sess:
        sess['_user_id'] = str(admin_id)
        sess['_fresh'] = True
    return c


def test_criar_tarefa_aceita_modo_apontamento(ctx):
    oid, aid = ctx['obra_id'], ctx['admin_id']
    c = _cliente(aid)
    resp = c.post(f'/cronograma/obra/{oid}/tarefa',
                  json={'nome_tarefa': 'Montagem de painéis',
                        'modo_apontamento': 'percentual'})
    assert resp.status_code == 201, resp.get_data(as_text=True)[:400]
    corpo = resp.get_json()['tarefa']
    assert corpo['modo_apontamento'] == 'percentual'

    with app.app_context():
        t = db.session.get(TarefaCronograma, corpo['id'])
        assert t.modo_apontamento == 'percentual'


def test_criar_tarefa_sem_modo_deixa_nulo(ctx):
    """Sem escolha explícita, a dedução legada continua no comando."""
    oid, aid = ctx['obra_id'], ctx['admin_id']
    c = _cliente(aid)
    resp = c.post(f'/cronograma/obra/{oid}/tarefa',
                  json={'nome_tarefa': 'Tarefa sem modo',
                        'quantidade_total': 80, 'unidade_medida': 'm2'})
    assert resp.status_code == 201
    corpo = resp.get_json()['tarefa']
    with app.app_context():
        t = db.session.get(TarefaCronograma, corpo['id'])
        assert t.modo_apontamento is None


def test_criar_tarefa_recusa_modo_invalido(ctx):
    oid, aid = ctx['obra_id'], ctx['admin_id']
    c = _cliente(aid)
    resp = c.post(f'/cronograma/obra/{oid}/tarefa',
                  json={'nome_tarefa': 'Tarefa ruim',
                        'modo_apontamento': 'banana'})
    assert resp.status_code == 400
    assert 'modo_apontamento' in resp.get_json()['msg']


def test_atualizar_tarefa_muda_o_modo(ctx):
    t = _tarefa(ctx, quantidade_total=100.0, unidade_medida='m2')
    oid, tid, aid = ctx['obra_id'], t.id, ctx['admin_id']
    c = _cliente(aid)
    resp = c.put(f'/cronograma/obra/{oid}/tarefa/{tid}',
                 json={'modo_apontamento': 'percentual'})
    assert resp.status_code == 200, resp.get_data(as_text=True)[:400]

    with app.app_context():
        assert db.session.get(
            TarefaCronograma, tid).modo_apontamento == 'percentual'


def test_atualizar_tarefa_limpa_o_modo_com_string_vazia(ctx):
    """Voltar para "automático" precisa ser possível pela UI."""
    t = _tarefa(ctx, quantidade_total=100.0, unidade_medida='m2',
                modo_apontamento='percentual')
    oid, tid, aid = ctx['obra_id'], t.id, ctx['admin_id']
    c = _cliente(aid)
    resp = c.put(f'/cronograma/obra/{oid}/tarefa/{tid}',
                 json={'modo_apontamento': ''})
    assert resp.status_code == 200

    with app.app_context():
        assert db.session.get(TarefaCronograma, tid).modo_apontamento is None


def test_atualizar_tarefa_recusa_modo_quantidade_em_marco(ctx):
    """Decisão D6: marco é sempre percentual."""
    m = _tarefa(ctx, is_marco=True, duracao_dias=0)
    oid, mid, aid = ctx['obra_id'], m.id, ctx['admin_id']
    c = _cliente(aid)
    resp = c.put(f'/cronograma/obra/{oid}/tarefa/{mid}',
                 json={'modo_apontamento': 'quantidade'})
    assert resp.status_code == 400
    assert 'marco' in resp.get_json()['msg'].lower()


def test_tarefas_rdo_reflete_a_escolha(ctx):
    """`tipo_modo` é o contrato que templates/rdo/novo.html:1118 consome."""
    t = _tarefa(ctx, quantidade_total=100.0, unidade_medida='m2',
                modo_apontamento='percentual')
    oid, tid, aid = ctx['obra_id'], t.id, ctx['admin_id']
    c = _cliente(aid)
    resp = c.get(f'/cronograma/obra/{oid}/tarefas-rdo?data={D0.isoformat()}')
    assert resp.status_code == 200
    itens = {i['id']: i for i in resp.get_json()['tarefas']}
    assert itens[tid]['tipo_modo'] == 'percentual'
    assert itens[tid]['modo_apontamento'] == 'percentual'
    assert itens[tid]['saldo'] is None, (
        'saldo só faz sentido no modo quantidade')
```

- [ ] **Step 2: Rode e confirme a falha**

```bash
python -m pytest tests/test_cronograma_modo_explicito.py -v -k "criar_tarefa or atualizar_tarefa or tarefas_rdo_reflete"
```

Esperado: FAIL — `KeyError: 'modo_apontamento'` no dict devolvido e `200` onde se esperava `400`.

- [ ] **Step 3: `_tarefa_to_dict` devolve o campo**

Em `cronograma_views.py`, dentro de `_tarefa_to_dict`, imediatamente após a linha 68 (`'unidade_medida': t.unidade_medida,`), insira:

```python
        # Escolha explícita de modo (migration 220). None = automático:
        # `modo_da_tarefa` deduz de quantidade_total + unidade_medida como
        # sempre fez. A UI do Gantt usa este campo para posicionar o seletor.
        'modo_apontamento': getattr(t, 'modo_apontamento', None),
```

- [ ] **Step 4: Adicione o helper de parse e use em `criar_tarefa`**

Em `cronograma_views.py`, imediatamente após `_parse_date` (que termina na linha 87), insira:

```python
def _parse_modo_apontamento(data, tarefa_is_marco=False):
    """Lê `modo_apontamento` do corpo. Devolve (valor, erro).

    Contrato:
      * chave ausente  → (None, None)  — não mexer no que já está gravado;
      * '' / None      → ('', None)    — LIMPAR (voltar ao automático);
      * valor válido   → (valor, None);
      * qualquer outra → (None, mensagem de erro).

    O sentinel '' distingue "não mandou" de "mandou vazio para limpar" —
    sem ele não haveria como voltar uma tarefa ao modo automático pela UI.
    """
    from services.cronograma_apontamento_service import MODOS_APONTAMENTO

    if 'modo_apontamento' not in data:
        return None, None

    bruto = data.get('modo_apontamento')
    if bruto in (None, ''):
        return '', None

    valor = str(bruto).strip().lower()
    if valor not in MODOS_APONTAMENTO:
        return None, (
            f'modo_apontamento inválido: {bruto!r}. '
            f'Use um de {", ".join(MODOS_APONTAMENTO)}, ou vazio para automático.')
    if tarefa_is_marco and valor == 'quantidade':
        return None, ('Um marco só admite apontamento percentual (0% ou 100%) '
                      '— modo_apontamento="quantidade" é inválido para marco.')
    return valor, None
```

Ainda em `criar_tarefa`, imediatamente **antes** do bloco `tarefa = TarefaCronograma(` (linha 421), insira:

```python
    # Modo de apontamento escolhido (migration 220). Ausente ⇒ None, e a
    # dedução legada (`_modo_deduzido`) continua no comando — exatamente o
    # comportamento anterior à coluna.
    modo_apontamento, erro_modo = _parse_modo_apontamento(data)
    if erro_modo:
        return jsonify({'status': 'error', 'msg': erro_modo}), 400
    modo_apontamento = modo_apontamento or None
```

E, dentro do construtor `TarefaCronograma(...)` de `criar_tarefa`, imediatamente após a linha `unidade_medida=(data.get('unidade_medida') or '').strip() or None,`, acrescente:

```python
        modo_apontamento=modo_apontamento,
```

- [ ] **Step 5: Trate o campo em `atualizar_tarefa`**

Em `cronograma_views.py`, dentro de `atualizar_tarefa`, imediatamente após o bloco `if 'unidade_medida' in data:` (que termina com `tarefa.unidade_medida = str(data['unidade_medida']).strip() or None`), insira:

```python
    if 'modo_apontamento' in data:
        # '' significa "voltar ao automático" (grava NULL); valor válido
        # significa "o usuário escolheu". Ver _parse_modo_apontamento.
        novo_modo, erro_modo = _parse_modo_apontamento(
            data, tarefa_is_marco=bool(getattr(tarefa, 'is_marco', False)))
        if erro_modo:
            return jsonify({'status': 'error', 'msg': erro_modo}), 400
        tarefa.modo_apontamento = novo_modo or None
```

- [ ] **Step 6: Exponha o campo em `tarefas_rdo`**

Em `cronograma_views.py`, dentro de `tarefas_rdo`, no dict `item` (linha 924 em diante), imediatamente após a linha `'tipo_modo': tipo_modo,`, insira:

```python
            # Escolha explícita (None = automático). `tipo_modo` acima é o
            # modo EFETIVO já resolvido; este campo diz se veio de escolha
            # ou de dedução — a UI do Gantt precisa dos dois.
            'modo_apontamento': getattr(t, 'modo_apontamento', None),
```

- [ ] **Step 7: Rode os testes**

```bash
python -m pytest tests/test_cronograma_modo_explicito.py -v
python -m pytest tests/test_cronograma_interface_obra.py tests/test_rdo_modos_apontamento.py -v
```

Esperado: tudo PASSA.

- [ ] **Step 8: Commit**

```bash
git add cronograma_views.py tests/test_cronograma_modo_explicito.py
git commit -m "feat(cronograma): API aceita e devolve modo_apontamento

criar_tarefa/atualizar_tarefa aceitam o campo (string vazia limpa e volta
ao automatico), _tarefa_to_dict e tarefas_rdo devolvem. Marco recusa
'quantidade' com 400. Sem o campo, comportamento identico ao anterior."
```

---

## Task 8: Seletor de modo no Gantt (Nova Tarefa e Editar)

**Files:**
- Modify: `templates/obras/cronograma.html:425-431` (modal Nova Tarefa, após o campo Unidade)
- Modify: `templates/obras/cronograma.html:1337-1355` (`abrirModalNovaTarefa`)
- Modify: `templates/obras/cronograma.html:1658-1689` (`salvarNovaTarefa`)
- Modify: `templates/obras/cronograma.html:525-534` (offcanvas Editar, após `ed_unidade_row`)
- Modify: `templates/obras/cronograma.html:1747-1798` (`abrirEditar`)
- Modify: `templates/obras/cronograma.html:1848-1860` (`salvarEditar`)

Esta task é de template puro; a cobertura automatizada dela é a Task 7 (o contrato HTTP já está travado).

- [ ] **Step 1: Adicione o campo ao modal Nova Tarefa**

Em `templates/obras/cronograma.html`, imediatamente após o bloco do campo Unidade (o `<div class="col-md-3">` que contém `id="nt_unidade"`, terminando na linha 431), insira:

```html
          <div class="col-md-6">
            <label class="form-label fw-semibold small text-uppercase text-muted ls-1">
              <i class="fas fa-ruler-combined me-1 text-primary"></i>Como apontar no RDO
            </label>
            <select id="nt_modo" class="form-select">
              <option value="">Automático (quantidade se houver unidade)</option>
              <option value="percentual">Percentual — informar % acumulado</option>
              <option value="quantidade">Quantidade — informar produção do dia</option>
            </select>
            <div class="form-text small">
              Escolha "Percentual" para acompanhar a tarefa sem levantar quantitativo.
            </div>
          </div>
```

- [ ] **Step 2: Limpe o campo ao abrir o modal**

Em `templates/obras/cronograma.html`, dentro de `abrirModalNovaTarefa()`, imediatamente após a linha `document.getElementById('nt_unidade').value = '';` (linha 1342), insira:

```javascript
  document.getElementById('nt_modo').value = '';
```

- [ ] **Step 3: Envie o campo no POST**

Em `templates/obras/cronograma.html`, dentro de `salvarNovaTarefa()`, no objeto `body`, imediatamente após a linha `servico_id:              servicoId,`, acrescente:

```javascript
    // '' = automático (o backend grava NULL e a deducao legada continua
    // valendo). Ver _parse_modo_apontamento em cronograma_views.py.
    modo_apontamento:        document.getElementById('nt_modo').value || '',
```

- [ ] **Step 4: Adicione o campo ao offcanvas Editar**

Em `templates/obras/cronograma.html`, imediatamente após o bloco `<div class="col-6 d-none" id="ed_unidade_row">` (que termina na linha 534, logo antes do comentário `{# Preview progresso #}`), insira:

```html
      <div class="col-12" id="ed_modo_row">
        <label class="form-label fw-semibold small text-uppercase text-muted">
          <i class="fas fa-ruler-combined me-1 text-primary"></i>Como apontar no RDO
        </label>
        <select id="ed_modo" class="form-select">
          <option value="">Automático (quantidade se houver unidade)</option>
          <option value="percentual">Percentual — informar % acumulado</option>
          <option value="quantidade">Quantidade — informar produção do dia</option>
        </select>
        <div class="form-text small" id="ed_modo_hint"></div>
      </div>
```

- [ ] **Step 5: Popule e esconda o campo em `abrirEditar`**

Em `templates/obras/cronograma.html`, dentro de `abrirEditar(tarefaId)`, imediatamente após a linha `document.getElementById('ed_unidade').value  = t.unidade_medida || '';` (linha 1754), insira:

```javascript
  document.getElementById('ed_modo').value = t.modo_apontamento || '';
  // Dica explicando o efetivo quando o usuário deixa em "Automático".
  const modoEfetivo = (t.quantidade_total > 0 && (t.unidade_medida || '').trim())
        ? 'quantidade' : 'percentual';
  document.getElementById('ed_modo_hint').textContent = t.modo_apontamento
        ? ''
        : `Automático hoje resolve para "${modoEfetivo}".`;
```

Ainda em `abrirEditar`, no bloco que trata tarefa pai, declare a linha nova junto das outras. Substitua as linhas 1775-1779:

```javascript
  const paiAlert   = document.getElementById('ed_pai_alert');
  const qtdRow     = document.getElementById('ed_qtd_row');
  const unidRow    = document.getElementById('ed_unidade_row');
  const inicioRow  = document.getElementById('ed_inicio_row');
  const fimRow     = document.getElementById('ed_fim_row');
```

por:

```javascript
  const paiAlert   = document.getElementById('ed_pai_alert');
  const qtdRow     = document.getElementById('ed_qtd_row');
  const unidRow    = document.getElementById('ed_unidade_row');
  const inicioRow  = document.getElementById('ed_inicio_row');
  const fimRow     = document.getElementById('ed_fim_row');
  // Tarefa pai não é apontada (o % dela é rollup das filhas, ver
  // utils/cronograma_engine.rollup_realizado) — esconder o seletor evita
  // sugerir uma escolha que não tem efeito nenhum.
  const modoRow    = document.getElementById('ed_modo_row');
```

E, dentro do mesmo `if (temFilhos) { ... } else { ... }`, acrescente uma linha em cada ramo — no ramo `if`, após `fimRow?.classList.add('d-none');`:

```javascript
    modoRow?.classList.add('d-none');
```

e no ramo `else`, após `fimRow?.classList.remove('d-none');`:

```javascript
    modoRow?.classList.remove('d-none');
```

- [ ] **Step 6: Envie o campo no PUT**

Em `templates/obras/cronograma.html`, dentro de `salvarEditar()`, no objeto `body`, imediatamente após a linha `servico_id:             edSvcId,`, acrescente:

```javascript
    // '' limpa a escolha e devolve a tarefa ao modo automático.
    modo_apontamento:       document.getElementById('ed_modo').value || '',
```

- [ ] **Step 7: Verifique a renderização de ponta a ponta**

```bash
python -m pytest tests/test_cronograma_interface_obra.py -v
python -m pytest tests/test_cronograma_modo_explicito.py -v
```

Esperado: tudo PASSA. Depois, confira na mão que os três ids novos existem exatamente uma vez cada:

```bash
grep -c "id=\"nt_modo\"" templates/obras/cronograma.html
grep -c "id=\"ed_modo\"" templates/obras/cronograma.html
grep -c "id=\"ed_modo_row\"" templates/obras/cronograma.html
```

Esperado: `1`, `1`, `1`.

- [ ] **Step 8: Commit**

```bash
git add templates/obras/cronograma.html
git commit -m "feat(cronograma): seletor 'Como apontar no RDO' nos modais do Gantt

Nova Tarefa e Editar ganham o campo, com 'Automatico' como default (grava
NULL e mantem a deducao legada). Tarefa pai esconde o seletor: o percentual
dela e rollup das filhas, nao apontamento."
```

---

## Task 9: `Obra.regime_medicao` deixa de ser coluna morta

Achado nº 5: a coluna existe, foi backfillada pela migration 201, e **nada a lê**. O comentário de `models.py:288-291` descreve um comportamento que nunca foi implementado. Esta task dá à coluna o significado que o nome promete e torna o comentário verdadeiro. Ver Decisão D5.

**Files:**
- Modify: `models.py:288-292`
- Modify: `cronograma_views.py` (dentro de `criar_tarefa`, no bloco de `modo_apontamento` da Task 7)
- Test: `tests/test_cronograma_modo_explicito.py` (acrescenta)

- [ ] **Step 1: Escreva o teste que falha**

Acrescente ao final de `tests/test_cronograma_modo_explicito.py`:

```python
# ---------------------------------------------------------------------------
# Task 9 — regime_medicao da obra é o default do modo
# ---------------------------------------------------------------------------

def test_obra_percentual_cria_tarefa_percentual_por_padrao(ctx):
    """Obra que fatura pelo % físico não deveria exigir quantitativo."""
    from models import Obra

    with app.app_context():
        obra = db.session.get(Obra, ctx['obra_id'])
        obra.regime_medicao = 'percentual'
        db.session.commit()

    c = _cliente(ctx['admin_id'])
    resp = c.post(f"/cronograma/obra/{ctx['obra_id']}/tarefa",
                  json={'nome_tarefa': 'Estrutura metálica',
                        'quantidade_total': 300, 'unidade_medida': 'm2'})
    assert resp.status_code == 201
    corpo = resp.get_json()['tarefa']
    assert corpo['modo_apontamento'] == 'percentual'


def test_obra_fixa_nao_forca_modo(ctx):
    """'fixa' é o default do schema; não pode mudar o comportamento antigo."""
    from models import Obra

    with app.app_context():
        assert db.session.get(Obra, ctx['obra_id']).regime_medicao == 'fixa'

    c = _cliente(ctx['admin_id'])
    resp = c.post(f"/cronograma/obra/{ctx['obra_id']}/tarefa",
                  json={'nome_tarefa': 'Fundação',
                        'quantidade_total': 40, 'unidade_medida': 'm3'})
    assert resp.status_code == 201
    corpo = resp.get_json()['tarefa']
    assert corpo['modo_apontamento'] is None


def test_escolha_explicita_vence_o_regime_da_obra(ctx):
    from models import Obra

    with app.app_context():
        obra = db.session.get(Obra, ctx['obra_id'])
        obra.regime_medicao = 'percentual'
        db.session.commit()

    c = _cliente(ctx['admin_id'])
    resp = c.post(f"/cronograma/obra/{ctx['obra_id']}/tarefa",
                  json={'nome_tarefa': 'Contrapiso',
                        'quantidade_total': 120, 'unidade_medida': 'm2',
                        'modo_apontamento': 'quantidade'})
    assert resp.status_code == 201
    assert resp.get_json()['tarefa']['modo_apontamento'] == 'quantidade'
```

- [ ] **Step 2: Rode e confirme a falha**

```bash
python -m pytest tests/test_cronograma_modo_explicito.py -v -k "regime or obra_percentual or obra_fixa or vence_o_regime"
```

Esperado: FAIL em `test_obra_percentual_cria_tarefa_percentual_por_padrao` — `modo_apontamento` volta `None`.

- [ ] **Step 3: Aplique o default em `criar_tarefa`**

Em `cronograma_views.py`, dentro de `criar_tarefa`, substitua o bloco inserido na Task 7:

```python
    modo_apontamento, erro_modo = _parse_modo_apontamento(data)
    if erro_modo:
        return jsonify({'status': 'error', 'msg': erro_modo}), 400
    modo_apontamento = modo_apontamento or None
```

por:

```python
    modo_apontamento, erro_modo = _parse_modo_apontamento(data)
    if erro_modo:
        return jsonify({'status': 'error', 'msg': erro_modo}), 400
    modo_apontamento = modo_apontamento or None

    # Default por obra: `regime_medicao == 'percentual'` significa que a obra
    # fatura pelo % físico apurado via RDO (models.py:288-292) — exigir
    # quantitativo por tarefa nessa obra é contraditório. Só vale quando o
    # usuário NÃO escolheu: escolha explícita sempre vence.
    # 'fixa' (o default do schema) deixa NULL e mantém a dedução legada, para
    # que nada mude nas obras existentes.
    if modo_apontamento is None and (obra.regime_medicao or '').lower() == 'percentual':
        modo_apontamento = 'percentual'
```

- [ ] **Step 4: Torne o comentário do modelo verdadeiro**

Em `models.py`, substitua o bloco das linhas 287-292:

```python
    # Regime de medição/faturamento da obra:
    #   'fixa'       → fatura por marcos contratuais (MedicaoContrato, datas/% fixos).
    #   'percentual' → fatura pelo % físico das etapas apurado via RDO (MedicaoObra).
    # Governa se o vínculo custo↔tarefa é obrigatório (percentual) ou opcional (fixa).
    # Ver spec 2026-06-27-custo-cronograma-fieis-regime-medicao.
    regime_medicao = db.Column(db.String(20), default='fixa', nullable=False)
```

por:

```python
    # Regime de medição/faturamento da obra:
    #   'fixa'       → fatura por marcos contratuais (MedicaoContrato, datas/% fixos).
    #   'percentual' → fatura pelo % físico das etapas apurado via RDO (MedicaoObra).
    #
    # O que esta coluna governa DE FATO (conferido em 2026-07-21): o modo de
    # apontamento padrão das tarefas criadas na obra. Com 'percentual',
    # `cronograma_views.criar_tarefa` grava `modo_apontamento='percentual'`
    # na tarefa nova quando o usuário não escolheu — faz sentido: se a obra
    # fatura pelo % físico, exigir quantitativo por tarefa é contraditório.
    # Escolha explícita do usuário sempre vence.
    #
    # O que esta coluna NÃO governa (o comentário anterior afirmava que sim,
    # e era falso): o vínculo custo↔tarefa. Nenhum código lia esta coluna
    # antes do plano `2026-07-21-cronograma-editavel-rdo-percentual.md`;
    # a única leitura era o teste de existência em
    # tests/test_importacao_fisico_financeiro.py:41. Tornar o vínculo
    # custo↔tarefa obrigatório em regime percentual é escopo da Fase 4
    # (centro de custo obrigatório).
    #
    # Ver spec 2026-06-27-custo-cronograma-fieis-regime-medicao e a
    # migration 201 (migrations.py:13688), que backfilla 'percentual' para
    # obras com medição física preexistente.
    regime_medicao = db.Column(db.String(20), default='fixa', nullable=False)
```

- [ ] **Step 5: Rode os testes**

```bash
python -m pytest tests/test_cronograma_modo_explicito.py -v
python -m pytest tests/test_importacao_fisico_financeiro.py -v
```

Esperado: tudo PASSA.

- [ ] **Step 6: Commit**

```bash
git add models.py cronograma_views.py tests/test_cronograma_modo_explicito.py
git commit -m "feat(cronograma): regime_medicao='percentual' vira default de modo da tarefa

A coluna existia desde a migration 201 e NINGUEM a lia — o comentario do
modelo afirmava governar o vinculo custo<->tarefa, o que era falso. Agora
ela decide o modo padrao das tarefas novas da obra, e o comentario diz a
verdade. 'fixa' (default do schema) nao muda nada."
```

---

## Task 10: Fechar o vazamento de `servico_id` e dar corpo ao nó sem template

Pré-requisito da Task 11: hoje o nó `sem_template` carrega `it.servico_id` **cru**, sem passar pelo filtro de tenant (achado nº 6). Enquanto o nó era descartado isso era inofensivo; quando ele virar tarefa, o id iria direto para `TarefaCronograma.servico_id`.

**Files:**
- Modify: `services/cronograma_proposta.py:279-290`
- Test: `tests/test_cronograma_proposta_tolerante.py`

- [ ] **Step 1: Escreva o teste que falha**

Crie `tests/test_cronograma_proposta_tolerante.py`:

```python
"""Caminho automático proposta→obra tolerante a catálogo incompleto.

Até 2026-07-21 um PropostaItem cujo serviço não tinha
`template_padrao_id` era marcado `sem_template=True` em
`montar_arvore_preview` (services/cronograma_proposta.py:280-290) e
descartado com um `continue` em `materializar_cronograma`
(:532-533). Resultado: obra aprovada nascia com ZERO tarefa, sem erro e
sem mensagem.

O que estes testes travam:
  * o `servico_id` do nó sem template passa pelo filtro de tenant
    (era cru — vazamento cross-tenant latente, :282);
  * o nó sem template ganha corpo (duracao_dias/unidade) para poder virar
    tarefa;
  * marcado=False continua o default (não regride
    tests/test_cronograma_automatico_aprovacao.py:303);
  * quando MARCADO, vira uma tarefa-esqueleto de nível 0.
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
from models import (Cliente, Obra, Proposta, PropostaItem, Servico,
                    TarefaCronograma, TipoUsuario, Usuario)

pytestmark = pytest.mark.integration


@pytest.fixture(autouse=True)
def _config():
    app.config['TESTING'] = True
    app.config['WTF_CSRF_ENABLED'] = False
    if not app.secret_key:
        app.secret_key = 'test-proposta-tolerante'
    yield


def _suf() -> str:
    return uuid.uuid4().hex[:10]


def _admin():
    suf = _suf()
    u = Usuario(
        username=f'prop_{suf}', email=f'prop_{suf}@test.local',
        nome=f'Prop {suf}',
        password_hash=generate_password_hash('Senha@2026'),
        tipo_usuario=TipoUsuario.ADMIN, ativo=True, versao_sistema='v2',
    )
    db.session.add(u)
    db.session.commit()
    return u


def _cenario(admin_id, servico_admin_id=None):
    """Proposta com 1 item apontando para um Servico SEM template.

    `servico_admin_id` permite criar o serviço em OUTRO tenant, para o teste
    de vazamento.
    """
    suf = _suf()
    cliente = Cliente(nome=f'Cliente Prop {suf}', admin_id=admin_id)
    db.session.add(cliente)
    db.session.flush()

    servico = Servico(nome=f'Servico Sem Template {suf}',
                      admin_id=servico_admin_id or admin_id, ativo=True)
    db.session.add(servico)
    db.session.flush()

    obra = Obra(nome=f'Obra Prop {suf}', codigo=f'PR-{suf[:8].upper()}',
                admin_id=admin_id, cliente_id=cliente.id,
                data_inicio=date(2026, 1, 1))
    db.session.add(obra)
    db.session.flush()

    proposta = Proposta(numero=f'P-{suf[:10]}', admin_id=admin_id,
                        cliente_id=cliente.id, obra_id=obra.id,
                        cliente_nome=cliente.nome)
    db.session.add(proposta)
    db.session.flush()

    item = PropostaItem(proposta_id=proposta.id, servico_id=servico.id,
                        descricao='Estrutura em Light Steel Frame',
                        quantidade=1, preco_unitario=1000, ordem=1)
    db.session.add(item)
    db.session.commit()
    return {'admin_id': admin_id, 'obra': obra, 'proposta': proposta,
            'item': item, 'servico': servico}


def test_no_sem_template_nasce_desmarcado():
    """Não regride tests/test_cronograma_automatico_aprovacao.py:303."""
    from services.cronograma_proposta import montar_arvore_preview

    with app.app_context():
        admin = _admin()
        c = _cenario(admin.id)
        arvore = montar_arvore_preview(c['proposta'], admin.id)
        assert len(arvore) == 1
        assert arvore[0]['sem_template'] is True
        assert arvore[0]['marcado'] is False


def test_servico_de_outro_tenant_nao_vaza_para_a_arvore():
    """services/cronograma_proposta.py:282 devolvia it.servico_id cru."""
    from services.cronograma_proposta import montar_arvore_preview

    with app.app_context():
        admin_a = _admin()
        admin_b = _admin()
        c = _cenario(admin_a.id, servico_admin_id=admin_b.id)
        arvore = montar_arvore_preview(c['proposta'], admin_a.id)
        assert arvore[0]['sem_template'] is True
        assert arvore[0]['servico_id'] is None, (
            'servico_id de outro tenant vazou para a árvore de preview')


def test_no_sem_template_tem_corpo_para_virar_tarefa():
    from services.cronograma_proposta import montar_arvore_preview

    with app.app_context():
        admin = _admin()
        c = _cenario(admin.id)
        no = montar_arvore_preview(c['proposta'], admin.id)[0]
        assert no['duracao_dias'] >= 1
        assert no['responsavel'] == 'empresa'
        assert no['filhos'] == []
```

- [ ] **Step 2: Rode e confirme a falha**

```bash
python -m pytest tests/test_cronograma_proposta_tolerante.py -v
```

Esperado: FAIL. `test_servico_de_outro_tenant_nao_vaza_para_a_arvore` traz o id do serviço alheio; `test_no_sem_template_tem_corpo_para_virar_tarefa` falha com `KeyError: 'duracao_dias'`.

- [ ] **Step 3: Corrija o ramo `sem_template`**

Em `services/cronograma_proposta.py`, substitua o bloco `else:` das linhas 279-290:

```python
        else:
            arvore.append({
                'proposta_item_id': it.id,
                'servico_id': it.servico_id,
                'servico_nome': nome_serv,
                'template_id': None,
                'template_nome': None,
                'sem_template': True,
                'horas_totais_estimadas': 0.0,
                'marcado': bool(pre.get('marcado')) if pre else False,
                'filhos': [],
            })
```

por:

```python
        else:
            # `servico.id if servico else None`, e NÃO `it.servico_id`: o
            # ramo com template (acima) já fazia assim, este não. `servicos`
            # é o cache FILTRADO por admin_id (linha 185), então um
            # PropostaItem apontando para serviço de outro tenant não entra
            # nele — e o id cru vazava para a árvore. Enquanto o nó era
            # descartado em materializar_cronograma isso era inofensivo; a
            # partir do momento em que ele vira TarefaCronograma, o id iria
            # direto para `tarefa.servico_id`.
            arvore.append({
                'proposta_item_id': it.id,
                'servico_id': servico.id if servico else None,
                'servico_nome': nome_serv,
                'template_id': None,
                'template_nome': None,
                'sem_template': True,
                'horas_totais_estimadas': 0.0,
                # Corpo mínimo para o nó poder virar uma tarefa-esqueleto
                # quando o usuário o marca (ver materializar_cronograma). Sem
                # estas chaves o nó era só um rótulo de tela.
                'duracao_dias': 1,
                'unidade_medida': None,
                'quantidade_prevista': None,
                'responsavel': 'empresa',
                # Default DESMARCADO, de propósito: materializar tudo encheria
                # a obra de linhas que ninguém pediu e quebraria
                # tests/test_cronograma_automatico_aprovacao.py:316.
                'marcado': bool(pre.get('marcado')) if pre else False,
                'filhos': [],
            })
```

- [ ] **Step 4: Rode os testes**

```bash
python -m pytest tests/test_cronograma_proposta_tolerante.py -v
python -m pytest tests/test_cronograma_automatico_aprovacao.py -v
```

Esperado: tudo PASSA.

- [ ] **Step 5: Commit**

```bash
git add services/cronograma_proposta.py tests/test_cronograma_proposta_tolerante.py
git commit -m "fix(sec,cronograma): no sem_template para de vazar servico_id de outro tenant

O ramo com template usava o cache filtrado por admin_id; o ramo
sem_template devolvia it.servico_id cru. Inofensivo enquanto o no era
descartado, perigoso a partir da materializacao do esqueleto. O no tambem
ganha corpo (duracao/responsavel) para poder virar tarefa."
```

---

## Task 11: Item de proposta sem template vira tarefa-esqueleto quando marcado

Esta é a frente 2 do plano: **a obra deixa de poder nascer muda**. Ver Decisão D4.

**Files:**
- Modify: `services/cronograma_proposta.py:528-537` (`materializar_cronograma`)
- Modify: `templates/obras/cronograma_revisar_inicial.html:264-283`
- Test: `tests/test_cronograma_proposta_tolerante.py` (acrescenta)

- [ ] **Step 1: Escreva o teste que falha**

Acrescente ao final de `tests/test_cronograma_proposta_tolerante.py`:

```python
# ---------------------------------------------------------------------------
# Task 11 — esqueleto para item sem template
# ---------------------------------------------------------------------------

def test_item_sem_template_desmarcado_nao_gera_tarefa():
    """Não regride tests/test_cronograma_automatico_aprovacao.py:316."""
    from services.cronograma_proposta import (materializar_cronograma,
                                              montar_arvore_preview)

    with app.app_context():
        admin = _admin()
        c = _cenario(admin.id)
        arvore = montar_arvore_preview(c['proposta'], admin.id)
        criadas = materializar_cronograma(c['proposta'], admin.id,
                                          c['obra'].id, arvore_marcada=arvore)
        db.session.commit()
        assert criadas == 0
        assert TarefaCronograma.query.filter_by(obra_id=c['obra'].id).count() == 0


def test_item_sem_template_marcado_gera_tarefa_esqueleto():
    """O ponto da frente 2: obra utilizável mesmo sem catálogo."""
    from services.cronograma_proposta import (materializar_cronograma,
                                              montar_arvore_preview)

    with app.app_context():
        admin = _admin()
        c = _cenario(admin.id)
        arvore = montar_arvore_preview(c['proposta'], admin.id)
        arvore[0]['marcado'] = True

        criadas = materializar_cronograma(c['proposta'], admin.id,
                                          c['obra'].id, arvore_marcada=arvore)
        db.session.commit()

        assert criadas == 1
        tarefas = TarefaCronograma.query.filter_by(obra_id=c['obra'].id).all()
        assert len(tarefas) == 1
        t = tarefas[0]
        assert t.nome_tarefa == c['servico'].nome
        assert t.tarefa_pai_id is None
        assert t.gerada_por_proposta_item_id == c['item'].id
        assert t.servico_id == c['servico'].id
        assert t.data_inicio is not None, (
            'tarefa-esqueleto sem data não aparece no Gantt')


def test_esqueleto_e_idempotente():
    """Rematerializar não duplica (chave gerada_por_proposta_item_id)."""
    from services.cronograma_proposta import (materializar_cronograma,
                                              montar_arvore_preview)

    with app.app_context():
        admin = _admin()
        c = _cenario(admin.id)
        arvore = montar_arvore_preview(c['proposta'], admin.id)
        arvore[0]['marcado'] = True

        materializar_cronograma(c['proposta'], admin.id, c['obra'].id,
                                arvore_marcada=arvore)
        db.session.commit()
        segunda = materializar_cronograma(c['proposta'], admin.id,
                                          c['obra'].id, arvore_marcada=arvore)
        db.session.commit()

        assert segunda == 0
        assert TarefaCronograma.query.filter_by(obra_id=c['obra'].id).count() == 1


def test_esqueleto_de_servico_de_outro_tenant_nao_grava_servico_id():
    """Efeito prático da Task 10 na materialização."""
    from services.cronograma_proposta import (materializar_cronograma,
                                              montar_arvore_preview)

    with app.app_context():
        admin_a = _admin()
        admin_b = _admin()
        c = _cenario(admin_a.id, servico_admin_id=admin_b.id)
        arvore = montar_arvore_preview(c['proposta'], admin_a.id)
        arvore[0]['marcado'] = True

        materializar_cronograma(c['proposta'], admin_a.id, c['obra'].id,
                                arvore_marcada=arvore)
        db.session.commit()

        t = TarefaCronograma.query.filter_by(obra_id=c['obra'].id).one()
        assert t.servico_id is None
```

- [ ] **Step 2: Rode e confirme a falha**

```bash
python -m pytest tests/test_cronograma_proposta_tolerante.py -v -k esqueleto
```

Esperado: FAIL — `criadas == 0` onde se esperava `1`, porque `materializar_cronograma` faz `continue` no `sem_template`.

- [ ] **Step 3: Remova o descarte incondicional**

Em `services/cronograma_proposta.py`, dentro do laço `for nivel0 in arvore_marcada:`, substitua as linhas 530-536:

```python
        if not nivel0.get('marcado'):
            continue
        if nivel0.get('sem_template'):
            continue
        if pi_id in ja_existem:
            logger.info(f"#102: proposta_item_id={pi_id} já materializado em obra={obra_id} — skip")
            continue
```

por:

```python
        if not nivel0.get('marcado'):
            continue
        if pi_id in ja_existem:
            logger.info(f"#102: proposta_item_id={pi_id} já materializado em obra={obra_id} — skip")
            continue

        # Item SEM template (`Servico.template_padrao_id` vazio e sem override
        # por linha) não é mais descartado. Até 2026-07-21 havia aqui um
        # `if nivel0.get('sem_template'): continue` — a obra nascia com ZERO
        # tarefa, sem erro e sem mensagem, e a queixa do dono ("sem cadastrar
        # os insumos não faz o cronograma") vinha daqui.
        #
        # Como o nó não tem filhos, o fluxo normal abaixo já produz
        # exatamente o que queremos: UMA tarefa de nível 0 com o nome do
        # serviço/descrição do item, marcada com `gerada_por_proposta_item_id`
        # (idempotência) e com `data_inicio` semeada pela obra. É o esqueleto
        # de EAP que o usuário arrasta e detalha no Gantt.
        #
        # `folhas_marcadas` fica vazio, então NÃO se cria vínculo
        # `ItemMedicaoCronogramaTarefa`: sem folha não há peso a distribuir, e
        # inventar peso 100% numa tarefa que ninguém detalhou distorceria a
        # medição comercial.
        #
        # O default continua DESMARCADO (montar_arvore_preview grava
        # `marcado=False` para sem_template) — chegar aqui exige o usuário ter
        # marcado o item na tela de revisão.
        if nivel0.get('sem_template'):
            logger.info(
                f"#102: proposta_item_id={pi_id} sem template — materializando "
                f"tarefa-esqueleto de nível 0 em obra={obra_id}"
            )
```

- [ ] **Step 4: Habilite o checkbox na tela de revisão**

Em `templates/obras/cronograma_revisar_inicial.html`, substitua o bloco das linhas 265-273:

```html
                {% if not item.sem_template %}
                <input type="checkbox" class="form-check-input chk-raiz"
                       data-pi-id="{{ item.proposta_item_id }}"
                       {% if item.marcado %}checked{% endif %}>
                {% else %}
                <input type="checkbox" class="form-check-input" disabled
                       title="Sem template padrão definido — não gera tarefas">
                {% endif %}
```

por:

```html
                {# O checkbox de item sem template era `disabled`: o usuário
                   via a linha e não podia fazer nada com ela, e a obra
                   nascia sem tarefa nenhuma. Agora ele marca e recebe uma
                   tarefa-esqueleto de nível 0 para detalhar no Gantt.
                   Continua DESMARCADO por padrão. #}
                <input type="checkbox" class="form-check-input chk-raiz"
                       data-pi-id="{{ item.proposta_item_id }}"
                       {% if item.marcado %}checked{% endif %}
                       {% if item.sem_template %}
                       title="Sem template padrão — marcar cria uma tarefa única com o nome do serviço, para você detalhar no cronograma"
                       {% endif %}>
```

E substitua o bloco das linhas 280-284:

```html
                {% if item.sem_template %}
                <span class="badge bg-secondary">
                    <i class="fas fa-ban me-1"></i> Sem template padrão — não gera tarefas
                </span>
                {% endif %}
```

por:

```html
                {% if item.sem_template %}
                <span class="badge bg-warning text-dark">
                    <i class="fas fa-diagram-project me-1"></i>
                    Sem template — gera 1 tarefa para detalhar
                </span>
                {% endif %}
```

- [ ] **Step 5: Rode os testes**

```bash
python -m pytest tests/test_cronograma_proposta_tolerante.py -v
python -m pytest tests/test_cronograma_automatico_aprovacao.py \
                 tests/test_cronograma_revisao_obra_gate.py -v
```

Esperado: tudo PASSA. `test_cronograma_automatico_aprovacao.py` continua verde porque o item `sem_template` segue com `marcado=False` naquele cenário.

- [ ] **Step 6: Commit**

```bash
git add services/cronograma_proposta.py templates/obras/cronograma_revisar_inicial.html tests/test_cronograma_proposta_tolerante.py
git commit -m "feat(cronograma): item de proposta sem template vira tarefa-esqueleto

Havia um 'if sem_template: continue' em materializar_cronograma que fazia a
obra nascer com ZERO tarefa, sem erro e sem mensagem, quando o servico nao
tinha template_padrao_id. Agora o usuario marca o item na revisao e recebe
uma tarefa de nivel 0 com o nome do servico para detalhar no Gantt. Default
continua desmarcado, sem peso de medicao, idempotente por
gerada_por_proposta_item_id."
```

---

## Task 12: A obra com proposta nunca abre sem oferecer cronograma

Falta ainda o caso mais silencioso: quando **nenhum** item da proposta tem template, `tem_conteudo_para_revisar` devolve `False` (`services/cronograma_proposta.py:402-444`), `_precisa_revisao_cronograma_inicial` corta em `views/obras.py:2360-2362`, o gate nunca dispara e o usuário nunca chega à tela onde a Task 11 funciona.

**Files:**
- Modify: `services/cronograma_proposta.py` (nova função após `tem_conteudo_para_revisar`, linha 444)
- Modify: `views/obras.py:2358-2362`
- Test: `tests/test_cronograma_proposta_tolerante.py` (acrescenta)

- [ ] **Step 1: Escreva o teste que falha**

Acrescente ao final de `tests/test_cronograma_proposta_tolerante.py`:

```python
# ---------------------------------------------------------------------------
# Task 12 — o gate dispara mesmo sem template
# ---------------------------------------------------------------------------

def test_proposta_sem_template_tem_itens_materializaveis():
    from services.cronograma_proposta import (tem_conteudo_para_revisar,
                                              tem_itens_materializaveis)

    with app.app_context():
        admin = _admin()
        c = _cenario(admin.id)
        # A função antiga continua dizendo "não há template" — é verdade.
        assert tem_conteudo_para_revisar(c['proposta'], admin.id) is False
        # A nova diz "mas há item para virar tarefa".
        assert tem_itens_materializaveis(c['proposta'], admin.id) is True


def test_proposta_vazia_nao_dispara_o_gate():
    from services.cronograma_proposta import tem_itens_materializaveis

    with app.app_context():
        admin = _admin()
        suf = _suf()
        cliente = Cliente(nome=f'Cliente Vazio {suf}', admin_id=admin.id)
        db.session.add(cliente)
        db.session.flush()
        proposta = Proposta(numero=f'PV-{suf[:10]}', admin_id=admin.id,
                            cliente_id=cliente.id, cliente_nome=cliente.nome)
        db.session.add(proposta)
        db.session.commit()
        assert tem_itens_materializaveis(proposta, admin.id) is False


def test_gate_dispara_para_obra_com_proposta_sem_template():
    from views.obras import _precisa_revisao_cronograma_inicial

    with app.app_context():
        admin = _admin()
        c = _cenario(admin.id)
        obra = c['obra']
        obra.proposta_origem_id = c['proposta'].id
        obra.cronograma_revisado_em = None
        db.session.commit()

        assert _precisa_revisao_cronograma_inicial(obra, admin.id) is True, (
            'obra nasceria muda: sem template o gate não disparava e o '
            'usuário nunca via a tela de revisão')


def test_gate_nao_dispara_para_obra_ja_revisada():
    from datetime import datetime

    from views.obras import _precisa_revisao_cronograma_inicial

    with app.app_context():
        admin = _admin()
        c = _cenario(admin.id)
        obra = c['obra']
        obra.proposta_origem_id = c['proposta'].id
        obra.cronograma_revisado_em = datetime.utcnow()
        db.session.commit()
        assert _precisa_revisao_cronograma_inicial(obra, admin.id) is False


def test_gate_nao_dispara_para_obra_que_ja_tem_tarefa():
    """Obra legada com tarefas não pode cair no gate (critério (c) do #200)."""
    from views.obras import _precisa_revisao_cronograma_inicial

    with app.app_context():
        admin = _admin()
        c = _cenario(admin.id)
        obra = c['obra']
        obra.proposta_origem_id = c['proposta'].id
        obra.cronograma_revisado_em = None
        db.session.add(TarefaCronograma(
            obra_id=obra.id, admin_id=admin.id, nome_tarefa='Já existe',
            ordem=0, duracao_dias=1, is_cliente=False,
        ))
        db.session.commit()
        assert _precisa_revisao_cronograma_inicial(obra, admin.id) is False
```

- [ ] **Step 2: Rode e confirme a falha**

```bash
python -m pytest tests/test_cronograma_proposta_tolerante.py -v -k "materializaveis or gate"
```

Esperado: FAIL com `ImportError: cannot import name 'tem_itens_materializaveis'`.

- [ ] **Step 3: Adicione a função ao serviço**

Em `services/cronograma_proposta.py`, imediatamente após `tem_conteudo_para_revisar` (que termina na linha 444) e antes do separador `# ─── Materialização`, insira:

```python
def tem_itens_materializaveis(proposta, admin_id: int) -> bool:
    """True se a proposta tem ao menos um item que PODE virar tarefa.

    Complementar a `tem_conteudo_para_revisar`, que só responde "há template
    configurado?". Desde a tolerância a catálogo incompleto, um item **sem**
    template também vira tarefa (uma tarefa-esqueleto de nível 0) quando o
    usuário o marca na tela de revisão — logo, a existência de PropostaItem
    já é motivo suficiente para oferecer a tela.

    As duas funções coexistem de propósito: `tem_conteudo_para_revisar`
    continua sendo a resposta correta para "há árvore de template a revisar?"
    e não muda de semântica (é consumida pelo gate junto com esta).

    Filtro de tenant: a proposta já é carregada por `admin_id` pelo caller
    (`views/obras._proposta_origem_obra`), e PropostaItem não tem `admin_id`
    próprio — a proposta é o escopo.
    """
    return (
        db.session.query(PropostaItem.id)
        .filter(PropostaItem.proposta_id == proposta.id)
        .limit(1)
        .first()
    ) is not None
```

- [ ] **Step 4: Use no gate**

Em `views/obras.py`, dentro de `_precisa_revisao_cronograma_inicial`, substitua as linhas 2358-2362:

```python
    proposta = _proposta_origem_obra(obra, admin_id)
    if proposta is None:
        return False
    from services.cronograma_proposta import tem_conteudo_para_revisar
    if not tem_conteudo_para_revisar(proposta, admin_id):
        return False
```

por:

```python
    proposta = _proposta_origem_obra(obra, admin_id)
    if proposta is None:
        return False
    # Antes: o gate exigia `tem_conteudo_para_revisar`, isto é, ao menos um
    # item com CronogramaTemplate. Quando nenhum serviço tinha
    # `template_padrao_id`, o gate não disparava, o usuário nunca via a tela
    # de revisão e a obra abria com cronograma vazio, em silêncio. Como um
    # item SEM template agora também vira tarefa (tarefa-esqueleto), basta
    # existir item para valer a pena oferecer a tela.
    from services.cronograma_proposta import (tem_conteudo_para_revisar,
                                              tem_itens_materializaveis)
    if not (tem_conteudo_para_revisar(proposta, admin_id)
            or tem_itens_materializaveis(proposta, admin_id)):
        return False
```

- [ ] **Step 5: Rode os testes**

```bash
python -m pytest tests/test_cronograma_proposta_tolerante.py -v
python -m pytest tests/test_cronograma_revisao_obra_gate.py \
                 tests/test_cronograma_automatico_aprovacao.py -v
```

Esperado: tudo PASSA.

- [ ] **Step 6: Commit**

```bash
git add services/cronograma_proposta.py views/obras.py tests/test_cronograma_proposta_tolerante.py
git commit -m "fix(cronograma): gate de revisao dispara mesmo sem template padrao

Quando nenhum servico da proposta tinha template_padrao_id o gate cortava
em tem_conteudo_para_revisar, o usuario nunca via a tela e a obra abria com
cronograma vazio em silencio. Agora basta existir PropostaItem — o item sem
template vira tarefa-esqueleto na propria tela."
```

---

## Task 13: RBAC da Fase 1 nas rotas de tarefa e apontamento do cronograma

**Pré-requisito:** a Fase 1 precisa estar aplicada (`utils/autorizacao.py` com `pode_editar_obra`/`pode_apontar_na_obra`, `models.PapelObra`, `models.UsuarioObra`, `scripts/flag_escopo_obra.py`).

Hoje as rotas de tarefa só verificam tenant (`Obra.query.filter_by(id=obra_id, admin_id=admin_id)`) — qualquer usuário autenticado do tenant edita o cronograma de qualquer obra.

**Files:**
- Modify: `cronograma_views.py` (`criar_tarefa`, `atualizar_tarefa`, `excluir_tarefa`, `apontar_producao`)
- Test: `tests/test_cronograma_rbac_fase1.py`

- [ ] **Step 1: Escreva o teste que falha**

Crie `tests/test_cronograma_rbac_fase1.py`:

```python
"""RBAC da Fase 1 aplicado às rotas de tarefa/apontamento do cronograma.

Até a Fase 1 o único eixo era o tenant: `cronograma_views.criar_tarefa`
filtra `Obra.query.filter_by(id=obra_id, admin_id=admin_id)` e pronto —
qualquer usuário autenticado do tenant edita o cronograma de qualquer obra
da empresa.

Estes testes travam o segundo eixo. Com `escopo_obra_ativo` DESLIGADA o
comportamento tem que ser idêntico ao de antes (a flag existe justamente
para que o deploy não tire acesso de ninguém).

NOTA de harness: requests do test client ficam FORA de app_context aberto —
Flask-Login cacheia `g._login_user` e congela o primeiro usuário resolvido.
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
from models import (Cliente, Obra, PapelObra, TarefaCronograma, TipoUsuario,
                    Usuario, UsuarioObra)

pytestmark = pytest.mark.integration


@pytest.fixture(autouse=True)
def _config():
    app.config['TESTING'] = True
    app.config['WTF_CSRF_ENABLED'] = False
    if not app.secret_key:
        app.secret_key = 'test-cronograma-rbac'
    yield


def _suf() -> str:
    return uuid.uuid4().hex[:10]


def _admin():
    suf = _suf()
    u = Usuario(
        username=f'cra_{suf}', email=f'cra_{suf}@test.local', nome=f'Adm {suf}',
        password_hash=generate_password_hash('Senha@2026'),
        tipo_usuario=TipoUsuario.ADMIN, ativo=True, versao_sistema='v2',
    )
    db.session.add(u)
    db.session.commit()
    return u


def _funcionario(admin_id):
    suf = _suf()
    u = Usuario(
        username=f'crf_{suf}', email=f'crf_{suf}@test.local', nome=f'Fun {suf}',
        password_hash=generate_password_hash('Senha@2026'),
        tipo_usuario=TipoUsuario.FUNCIONARIO, ativo=True, admin_id=admin_id,
    )
    db.session.add(u)
    db.session.commit()
    return u


def _obra(admin_id):
    suf = _suf()
    cliente = Cliente(nome=f'Cliente RBAC {suf}', admin_id=admin_id)
    db.session.add(cliente)
    db.session.flush()
    o = Obra(nome=f'Obra RBAC {suf}', codigo=f'RB-{suf[:8].upper()}',
             admin_id=admin_id, cliente_id=cliente.id,
             data_inicio=date(2026, 1, 1))
    db.session.add(o)
    db.session.commit()
    return o


def _cliente_http(user_id):
    c = app.test_client()
    with c.session_transaction() as sess:
        sess['_user_id'] = str(user_id)
        sess['_fresh'] = True
    return c


def test_flag_desligada_preserva_o_comportamento_antigo():
    """Sem a flag, funcionário do tenant continua criando tarefa."""
    with app.app_context():
        admin = _admin()
        obra = _obra(admin.id)
        func = _funcionario(admin.id)
        oid, fid = obra.id, func.id

    c = _cliente_http(fid)
    r = c.post(f'/cronograma/obra/{oid}/tarefa',
               json={'nome_tarefa': 'Tarefa livre'})
    assert r.status_code == 201, r.get_data(as_text=True)[:300]


def test_flag_ligada_sem_vinculo_recusa_criacao():
    from scripts.flag_escopo_obra import definir_flag

    with app.app_context():
        admin = _admin()
        obra = _obra(admin.id)
        func = _funcionario(admin.id)
        definir_flag(admin.id, True)
        oid, fid = obra.id, func.id

    c = _cliente_http(fid)
    r = c.post(f'/cronograma/obra/{oid}/tarefa',
               json={'nome_tarefa': 'Tarefa proibida'})
    assert r.status_code == 404, r.get_data(as_text=True)[:300]

    with app.app_context():
        definir_flag(admin.id, False)


def test_flag_ligada_gestor_da_obra_cria():
    from scripts.flag_escopo_obra import definir_flag

    with app.app_context():
        admin = _admin()
        obra = _obra(admin.id)
        func = _funcionario(admin.id)
        db.session.add(UsuarioObra(usuario_id=func.id, obra_id=obra.id,
                                   papel=PapelObra.GESTOR, admin_id=admin.id))
        db.session.commit()
        definir_flag(admin.id, True)
        oid, fid = obra.id, func.id

    c = _cliente_http(fid)
    r = c.post(f'/cronograma/obra/{oid}/tarefa',
               json={'nome_tarefa': 'Tarefa do gestor'})
    assert r.status_code == 201, r.get_data(as_text=True)[:300]

    with app.app_context():
        definir_flag(admin.id, False)


def test_flag_ligada_apontador_nao_edita_a_estrutura():
    """APONTADOR lança RDO; não mexe no cronograma."""
    from scripts.flag_escopo_obra import definir_flag

    with app.app_context():
        admin = _admin()
        obra = _obra(admin.id)
        func = _funcionario(admin.id)
        db.session.add(UsuarioObra(usuario_id=func.id, obra_id=obra.id,
                                   papel=PapelObra.APONTADOR,
                                   admin_id=admin.id))
        db.session.commit()
        definir_flag(admin.id, True)
        oid, fid = obra.id, func.id

    c = _cliente_http(fid)
    r = c.post(f'/cronograma/obra/{oid}/tarefa',
               json={'nome_tarefa': 'Tarefa do apontador'})
    assert r.status_code == 404, r.get_data(as_text=True)[:300]

    with app.app_context():
        definir_flag(admin.id, False)


def test_admin_do_tenant_sempre_edita_mesmo_com_flag_ligada():
    """ADMIN não precisa de linha em usuario_obra (decisão 4 da Fase 1)."""
    from scripts.flag_escopo_obra import definir_flag

    with app.app_context():
        admin = _admin()
        obra = _obra(admin.id)
        definir_flag(admin.id, True)
        oid, aid = obra.id, admin.id

    c = _cliente_http(aid)
    r = c.post(f'/cronograma/obra/{oid}/tarefa',
               json={'nome_tarefa': 'Tarefa do admin'})
    assert r.status_code == 201, r.get_data(as_text=True)[:300]

    with app.app_context():
        definir_flag(admin.id, False)


def test_excluir_tarefa_de_obra_fora_do_escopo_recusa():
    from scripts.flag_escopo_obra import definir_flag

    with app.app_context():
        admin = _admin()
        obra = _obra(admin.id)
        func = _funcionario(admin.id)
        t = TarefaCronograma(obra_id=obra.id, admin_id=admin.id,
                             nome_tarefa='Alvo', ordem=0, duracao_dias=1,
                             is_cliente=False)
        db.session.add(t)
        db.session.commit()
        definir_flag(admin.id, True)
        oid, tid, fid = obra.id, t.id, func.id

    c = _cliente_http(fid)
    r = c.delete(f'/cronograma/obra/{oid}/tarefa/{tid}')
    assert r.status_code == 404

    with app.app_context():
        definir_flag(admin.id, False)
        assert db.session.get(TarefaCronograma, tid) is not None
```

- [ ] **Step 2: Rode e confirme a falha**

```bash
python -m pytest tests/test_cronograma_rbac_fase1.py -v
```

Esperado: FAIL — as rotas devolvem `201`/`200` onde os testes esperam `404`, porque hoje só existe o eixo de tenant.

- [ ] **Step 3: Adicione o guard de escopo em `cronograma_views.py`**

Em `cronograma_views.py`, imediatamente após `_admin_id()` (linha 48-51), insira:

```python
def _guard_editar_obra(obra_id: int):
    """Fase 1 — segundo eixo de autorização nas rotas que MEXEM na obra.

    Devolve uma resposta JSON 404 quando o usuário não pode editar aquela
    obra, ou None quando pode. 404 e não 403 é deliberado: a mesma escolha
    já travada por `tests/test_cronograma_permissoes.py` — a existência de
    uma obra fora do alcance não vaza.

    Com `configuracao_empresa.escopo_obra_ativo` DESLIGADA (o default),
    `pode_editar_obra` devolve True para todo usuário do tenant e este guard
    é transparente. É o que torna esta task reversível sem rollback.
    """
    from utils.autorizacao import pode_editar_obra
    if not pode_editar_obra(obra_id):
        return jsonify({'status': 'error', 'msg': 'Obra não encontrada'}), 404
    return None


def _guard_apontar_obra(obra_id: int):
    """Fase 1 — mesmo guard, para as rotas de APONTAMENTO.

    GESTOR e APONTADOR passam; LEITOR não. Separado de `_guard_editar_obra`
    porque lançar produção e reestruturar o cronograma são permissões
    diferentes (PAPEIS_QUE_APONTAM vs PAPEIS_QUE_EDITAM_OBRA em
    utils/autorizacao.py).
    """
    from utils.autorizacao import pode_apontar_na_obra
    if not pode_apontar_na_obra(obra_id):
        return jsonify({'status': 'error', 'msg': 'Obra não encontrada'}), 404
    return None
```

- [ ] **Step 4: Aplique nas quatro rotas**

Em `cronograma_views.py`, em **`criar_tarefa`**, imediatamente após a linha `obra = Obra.query.filter_by(id=obra_id, admin_id=admin_id).first_or_404()`, insira:

```python
    escopo = _guard_editar_obra(obra_id)
    if escopo:
        return escopo
```

Em **`atualizar_tarefa`**, imediatamente após `admin_id = _admin_id()` e antes de `cliente_mode = _modo_cliente()`, insira:

```python
    escopo = _guard_editar_obra(obra_id)
    if escopo:
        return escopo
```

Em **`excluir_tarefa`**, imediatamente após a linha `admin_id = _admin_id()`, insira:

```python
    escopo = _guard_editar_obra(obra_id)
    if escopo:
        return escopo
```

Em **`apontar_producao`**, imediatamente após o bloco que resolve o RDO (`if not rdo: return jsonify(...), 404`), insira:

```python
    # O escopo é da OBRA do RDO — a rota recebe rdo_id, não obra_id.
    escopo = _guard_apontar_obra(rdo.obra_id)
    if escopo:
        return escopo
```

- [ ] **Step 5: Rode os testes**

```bash
python -m pytest tests/test_cronograma_rbac_fase1.py -v
python -m pytest tests/test_cronograma_permissoes.py \
                 tests/test_cronograma_multitenancy.py \
                 tests/test_cronograma_modo_explicito.py -v
```

Esperado: tudo PASSA. `test_cronograma_modo_explicito.py` continua verde porque usa o próprio ADMIN do tenant.

- [ ] **Step 6: Commit**

```bash
git add cronograma_views.py tests/test_cronograma_rbac_fase1.py
git commit -m "feat(sec,cronograma): escopo por obra nas rotas de tarefa e apontamento

criar/atualizar/excluir tarefa exigem pode_editar_obra; apontar_producao
exige pode_apontar_na_obra (GESTOR+APONTADOR). 404 e nao 403, para nao
vazar existencia. Com escopo_obra_ativo desligada — o default — o guard e
transparente e o comportamento e identico ao anterior."
```

---

## Task 14: Gate completo e nota de rollout

**Files:**
- Modify: `ESTADO-ATUAL.md:70-89` (corrige o diagnóstico falso)

- [ ] **Step 1: Rode o gate inteiro**

```bash
bash run_tests.sh --gate 2>&1 | tail -40
```

Esperado: mesma contagem de falhas da baseline anotada antes de começar, **sem falha nova**. Se houver falha nova, ela é responsabilidade deste plano — não anote como pré-existente sem conferir com `git stash`.

- [ ] **Step 2: Confirme que as migrations aplicam do zero**

```bash
python -c "
from app import app
from migrations import executar_migracoes
with app.app_context():
    executar_migracoes()
" 2>&1 | grep -E "\[Migration 22[01]\]|ERRO|ERROR"
```

Esperado: as duas migrations reportam "Concluída com sucesso" e, na segunda execução, a 221 reporta `0 tarefa(s) classificada(s)` — prova de idempotência.

- [ ] **Step 3: Corrija o diagnóstico do `ESTADO-ATUAL.md`**

Em `ESTADO-ATUAL.md`, substitua o bloco das linhas 70-89 (de `Diagnóstico confirmado no código` até `**O que falta:** ... não uma dedução.`) por:

```markdown
Diagnóstico **revisado em 21/07/2026** — duas das três afirmações originais
eram falsas (ver `docs/superpowers/plans/2026-07-21-cronograma-editavel-rdo-percentual.md`):

1. ~~O cronograma nasce preso à proposta.~~ **FALSO.** Criar tarefa manual
   nunca exigiu catálogo: `cronograma_views.py:271` (`criar_tarefa`) só
   obriga `nome_tarefa`, e `TarefaCronograma.servico_id` é nullable
   (`models.py:4903`). O importador `.mpp` também cria tarefa sem serviço
   (`services/cronograma_versao_service.py:534`).
2. ~~`materializar_cronograma` exige serviço → composição → insumo.~~
   **FALSO.** A cadeia real é `Servico.template_padrao_id` →
   `CronogramaTemplate` → `SubatividadeMestre`. `ComposicaoServico` e
   `Insumo` não aparecem em `services/cronograma_proposta.py`. O que
   acontecia sem template não era erro: o item era descartado em
   `:532` e a obra nascia com **zero tarefa, em silêncio**.
3. **O RDO decidia o modo sozinho.** VERDADEIRO —
   `services/cronograma_apontamento_service.py:73-82`.

**Entregue pelo plano de 21/07:** coluna `tarefa_cronograma.modo_apontamento`
(migrations 220/221, backfill que congela a dedução vigente — no-op de
comportamento), seletor "Como apontar no RDO" no Gantt, tarefa-esqueleto
para item de proposta sem template, gate de revisão que dispara mesmo sem
template, e `scripts/diagnostico_cronograma_tenant.py` para responder "por
que o cronograma não aparece para este tenant?" sem abrir o banco.
```

- [ ] **Step 4: Commit**

```bash
git add ESTADO-ATUAL.md
git commit -m "docs: corrige o diagnostico de cronograma do ESTADO-ATUAL

Duas das tres afirmacoes eram falsas: criar tarefa manual nunca exigiu
catalogo, e materializar_cronograma depende de CronogramaTemplate, nao de
composicao/insumo. O problema real era outro — obra nascia muda quando o
servico nao tinha template padrao."
```

- [ ] **Step 5: Rollout — o que ligar e em que ordem**

Não é passo de código; é o roteiro de produção. Execute na ordem e anote as saídas.

```bash
# 1. Diagnóstico ANTES de qualquer coisa — pode encerrar o assunto.
python scripts/diagnostico_cronograma_tenant.py <admin_id>

# 2. Se o bloqueio for versao_sistema_nao_v2, resolva isso primeiro:
#    UPDATE usuario SET versao_sistema='v2' WHERE id=<admin_id>;
#    e rode o diagnóstico de novo.

# 3. Área de importação .mpp, se o tenant for usar:
python scripts/flag_cronograma_mpp.py <admin_id> --ligar

# 4. Escopo por obra (Fase 1) — só depois de popular usuario_obra,
#    senão os não-admin perdem acesso às obras:
python scripts/flag_escopo_obra.py <admin_id> --status
```

O modo explícito de apontamento **não tem flag**: a migration 221 congela o comportamento atual em cada tarefa, então ligar não é uma decisão — já está ligado e nada mudou. O que muda é que, a partir do deploy, o usuário passa a **poder** escolher.

---

## Autorrevisão

Feita contra o escopo original, com olhos frescos.

**1. Cobertura do escopo.**

| Requisito do escopo | Onde é atendido |
|---|---|
| Seção "O que já existe e NÃO será refeito", com evidência | Seção homônima, 7 linhas de tabela com `caminho:linha` conferidos |
| Reconferir as linhas citadas no briefing | Todas conferidas; três divergiram e estão corrigidas no texto (`criar_tarefa` é `:269`/`:271`, não `:269` da função; o comentário Task #116 está em `:365`, não `:269`) |
| Frente 1 — modo vira escolha explícita, com backfill neutro | Tasks 2, 3, 4, 6, 7, 8 |
| Frente 1 — cuidar dos consumidores (`tipo_apontamento`, snapshots 209, `recomputar_cadeia`) | Task 5 (classificador), Task 6 (guard de escrita), contexto verificado documenta a distinção de vocabulário |
| Frente 2 — tolerância do caminho automático proposta→obra | Tasks 10, 11, 12; a investigação está na Correção nº 2 (o que ele exige de fato: template; o que acontece: obra vazia em silêncio) |
| Frente 3 — tarefa **primeira** de diagnóstico por `admin_id` | Task 1, com todas as flags: `versao_sistema`, `cronograma_mpp_ativo`, `escopo_obra_ativo`, gate de revisão, catálogo sem template |
| Convivência: obras com cronograma já materializado não quebram | Backfill neutro (Task 3, testes `parametrize` que comparam com `_modo_deduzido`); esqueleto só com `marcado=True` (Task 11); guard de modo só com coluna não-NULL (Task 6); flag desligada no RBAC (Task 13) |
| `Obra.regime_medicao` — entender a interação e tratar | Achado nº 5 (coluna morta), Decisão D5, Task 9 |
| Migrations na faixa 220–229, sistema próprio, modelo da 182 | 220 e 221, registradas em `migrations_to_run` após a 213, idempotentes, `IF NOT EXISTS`, `logger`, `db.session.execute(text(...))` |
| Usar as peças da Fase 1 | Task 13 usa `pode_editar_obra`, `pode_apontar_na_obra`, `PapelObra`, `UsuarioObra`, `scripts/flag_escopo_obra` |
| Testes: pytest, injeção de sessão, `import main`, `pytestmark`, `Cliente` antes de `Obra`, requests fora de `app_context` | Os quatro arquivos novos seguem o padrão; a nota de harness está em `tests/test_cronograma_rbac_fase1.py` |
| Recomendação explícita para cada decisão de negócio | D1–D6, todas marcadas `Recomendado:` e todas adotadas no corpo do plano |

**2. Varredura de placeholders.** Nenhuma ocorrência de "TODO", "TBD", "similar à Task N", "tratamento apropriado" ou "escreva testes para o acima". Todo passo que altera código traz o código completo. Os dois passos sem código (Task 14 steps 1-2 e 5) são execução de comando e roteiro de rollout, com comandos exatos.

**3. Consistência de tipos e nomes.** Verificado cruzando as tasks:
- `modo_apontamento` (coluna, str `'quantidade'`/`'percentual'`/`NULL`) — Tasks 2, 3, 4, 6, 7, 8, 9, consistente.
- `MODOS_APONTAMENTO` (tupla) — definida na Task 4, consumida nas Tasks 6 e 7.
- `_modo_deduzido(tarefa) -> str` — definida na Task 4, consumida no teste da Task 3.
- `ModoIncompativel` — definida na Task 6, testada na Task 6.
- `_parse_modo_apontamento(data, tarefa_is_marco=False) -> (valor, erro)` — definida na Task 7, reusada na Task 9.
- `_guard_editar_obra` / `_guard_apontar_obra` — definidas e usadas na Task 13.
- `tem_itens_materializaveis(proposta, admin_id) -> bool` — definida na Task 12, usada em `views/obras.py` na mesma task.
- `diagnosticar(admin_id) -> dict` — chaves do dict batem entre o script e os seis testes da Task 1.
- Migrations: `migration_220_tarefa_modo_apontamento` e `migration_221_backfill_modo_apontamento`, nomes idênticos na definição, no registro e no teste que importa a 221.

**4. Dependência de ordem sinalizada.** A Task 3 escreve um teste que importa `_modo_deduzido`, criado na Task 4. Isso está declarado em caixa no Step 2 da Task 3, com a instrução de rodar a suíte completa só no Step 4 da Task 4. É a única inversão do plano e é deliberada: a migration de backfill tem que existir antes de mexer no resolver, para que a coluna esteja preenchida quando `modo_da_tarefa` começar a lê-la.
