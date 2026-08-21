# Linha de Base, Planejado e Revisões do Cronograma — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Tornar visível no cronograma a diferença entre **linha de base** (o plano congelado e aprovado), **planejado** (as datas que o Alan move durante a obra) e **realizado** (o que o RDO apurou) — e guardar as linhas de base como **revisões numeradas** (V1, V2…) com o motivo, para comparar "era pra entregar tal dia / com o aditivo virou tal dia".

**Architecture:** A infraestrutura já existe e funciona: `CronogramaBaseline` + `CronogramaBaselineItem` congelam datas e BAC, o índice único parcial garante uma ativa por obra e por modo, e `criar_baseline` já cria **outra** baseline a cada salvamento — ou seja, o histórico já é preservado. O que falta é (1) nomenclatura na tela, onde "Planejado" hoje é uma coluna de **percentual** e as datas vivas não têm rótulo nenhum; (2) numeração de revisão e motivo na baseline, para "V2 — aditivo" ser um dado e não uma convenção de nome digitado à mão; (3) uma comparação entre duas revisões.

**Tech Stack:** Python 3, Flask, SQLAlchemy, PostgreSQL, Jinja2, Bootstrap 5, vanilla JS, pytest.

**Spec:** Não há spec escrito. Este plano nasce da sessão de brainstorming de 2026-08-20.

## Global Constraints

- Migrations em `migrations.py`: função `_migration_NNN_slug()` + entrada na lista `migrations_to_run` (~linha 6939). **O último número usado é 311.** Os planos irmãos deste dia reservam 312 (`rdo-efetivo-terceiros`) e 313 (`cadastro-funcionario-operacional`). Este plano assume **314** — confirme com `grep -n "^            (31" migrations.py` antes de escrever.
- Migration idempotente e que **levanta** em falha.
- Toda query filtra por `admin_id`; baseline também escopa por `is_cliente`.
- O portal do cliente **não muda** — a UI de linha de base é interna (é por isso que `is_cliente` entra na chave da baseline).
- Testes em `tests/`, `pytestmark = pytest.mark.integration`. Rodar: `python -m pytest tests/<arquivo>.py -v`
- Commits em português: `feat(cronograma):`, `test(cronograma):`.

## Fora de escopo

- **Recalcular a linha de base automaticamente a partir de um aditivo.** O Paulo levantou e ele mesmo respondeu "depende do contrato". O que este plano entrega é o **registro** da revisão com motivo; decidir quando revisar continua sendo do humano.
- **Curva S comparando duas revisões.** Só a comparação de datas entra aqui.

---

## File Structure

| Arquivo | Responsabilidade |
|---|---|
| `models.py` (modificar, `CronogramaBaseline` linha 6770) | Colunas `revisao` e `motivo`. |
| `migrations.py` (modificar) | Migration 314: as duas colunas + backfill de `revisao` nas baselines existentes. |
| `cronograma_views.py` (modificar, `criar_baseline` 2184, `_baseline_to_dict` 2163, `listar_baselines` 2254) | Numerar a revisão, aceitar o motivo, expor os dois no JSON. |
| `cronograma_views.py` (rota nova, depois de `excluir_baseline` ~2320) | `GET /obra/<id>/baselines/comparar`. |
| `templates/obras/cronograma.html` (modificar, cabeçalhos ~200-213 e JS ~3348-3380) | Rótulos Planejado/Linha de base e histórico com revisão, motivo e comparação. |
| `tests/test_cronograma_baseline_revisao.py` (criar) | Numeração, motivo e comparação. |

---

### Task 1: Revisão numerada e motivo na linha de base

Hoje a baseline tem só `nome` livre. "V1", "V2" e "aditivo" viram convenção
que alguém tem de lembrar de digitar — e uma comparação confiável precisa de
ordem, não de texto.

`revisao` é sequencial por obra **e por modo** (`is_cliente`), pela mesma razão
que o índice de baseline ativa é: o plano do cliente e o interno são conjuntos
de tarefas distintos.

**Files:**
- Modify: `models.py:6770-6820` (`class CronogramaBaseline`)
- Modify: `migrations.py` (nova função + entrada na lista)
- Modify: `cronograma_views.py:2163-2171` (`_baseline_to_dict`), `:2229-2236` (construtor em `criar_baseline`)
- Test: `tests/test_cronograma_baseline_revisao.py`

**Interfaces:**
- Produces: `CronogramaBaseline.revisao: int` (NOT NULL, ≥1) e `CronogramaBaseline.motivo: str | None` (até 200 chars). `_baseline_to_dict` passa a devolver `revisao` e `motivo` além das chaves de hoje (`id`, `nome`, `ativa`, `criada_em`, `total_itens`). `POST /obra/<id>/baseline` passa a aceitar `motivo` no body. Consumido pelas Tasks 2 e 3.

- [x] **Step 1: Escrever o teste que falha**

Criar `tests/test_cronograma_baseline_revisao.py`:

```python
"""Revisões da linha de base — reunião de 2026-08-20.

O primeiro cronograma aprovado é a V1 e não se mexe. Durante a obra o
Alan move o PLANEJADO. Quando entra um aditivo, sobe uma V2 — e as duas
ficam guardadas para responder "era pra entregar tal dia; com o aditivo
virou tal dia".
"""
import os
import sys
from datetime import date

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import main  # noqa: F401 — registra os blueprints
from app import app, db
from models import ConfiguracaoEmpresa, CronogramaBaseline
from test_cronograma_endpoints_m05 import _client_como
from test_cronograma_versao_service import _ambiente, _tarefa

pytestmark = pytest.mark.integration


@pytest.fixture(autouse=True)
def _config():
    app.config['TESTING'] = True
    app.config['WTF_CSRF_ENABLED'] = False
    if not app.secret_key:
        app.secret_key = 'test-baseline-revisao'
    yield


def _flag_editor_v2(admin_id: int, ativo: bool = True) -> None:
    config = ConfiguracaoEmpresa.query.filter_by(admin_id=admin_id).first()
    if config is None:
        config = ConfiguracaoEmpresa(admin_id=admin_id,
                                     nome_empresa=f'Empresa {admin_id}')
        db.session.add(config)
    config.cronograma_editor_v2 = bool(ativo)
    db.session.commit()


def _cenario():
    """Obra com duas folhas datadas, editor v2 ligado."""
    with app.app_context():
        admin, obra = _ambiente()
        _flag_editor_v2(admin.id, True)
        _tarefa(obra, admin, 'Fundação', ordem=0, duracao_dias=5,
                data_inicio=date(2026, 7, 1), data_fim=date(2026, 7, 7))
        _tarefa(obra, admin, 'Painelização', ordem=1, duracao_dias=3,
                data_inicio=date(2026, 7, 8), data_fim=date(2026, 7, 10))
        # `_client_como` recebe o ID; e o objeto ORM devolvido de dentro do
        # contexto já está destacado quando ele fecha.
        return admin.id, obra.id


def test_primeira_baseline_nasce_revisao_1():
    admin_id, obra_id = _cenario()
    client = _client_como(admin_id)

    resp = client.post(f'/cronograma/obra/{obra_id}/baseline',
                       json={'nome': 'Cronograma aprovado'})

    assert resp.status_code == 201, resp.get_data(as_text=True)
    assert resp.get_json()['baseline']['revisao'] == 1


def test_segunda_baseline_incrementa_a_revisao_e_grava_motivo():
    admin_id, obra_id = _cenario()
    client = _client_como(admin_id)
    client.post(f'/cronograma/obra/{obra_id}/baseline',
                json={'nome': 'Cronograma aprovado'})

    resp = client.post(f'/cronograma/obra/{obra_id}/baseline',
                       json={'nome': 'Pós-aditivo', 'motivo': 'Aditivo 01'})

    bl = resp.get_json()['baseline']
    assert bl['revisao'] == 2
    assert bl['motivo'] == 'Aditivo 01'


def test_revisao_e_sequencial_por_obra():
    """A sequência conta por obra: duas obras do mesmo tenant não se misturam."""
    admin_a_id, obra_a = _cenario()
    _admin_b_id, obra_b = _cenario()

    client_a = _client_como(admin_a_id)
    client_a.post(f'/cronograma/obra/{obra_a}/baseline', json={})
    client_a.post(f'/cronograma/obra/{obra_a}/baseline', json={})

    with app.app_context():
        rev_a = sorted(b.revisao for b in CronogramaBaseline.query
                       .filter_by(obra_id=obra_a).all())
        rev_b = [b.revisao for b in CronogramaBaseline.query
                 .filter_by(obra_id=obra_b).all()]
    assert rev_a == [1, 2]
    assert rev_b == []  # a obra B não recebeu baseline nenhuma
```

- [x] **Step 2: Rodar para confirmar que falha**

Run: `python -m pytest tests/test_cronograma_baseline_revisao.py -v`

Esperado: **FAIL** — `KeyError: 'revisao'` (o dict da baseline não tem a chave).

`_cenario()` cria admin, cliente e obra novos a cada chamada (sufixo aleatório
em `_ambiente`), então as duas obras do teste de sequência são de tenants
distintos — o que o teste prova é que a numeração não vaza entre obras.

- [x] **Step 3: Declarar as colunas no modelo**

Em `models.py`, na `class CronogramaBaseline`, logo depois de `nome`, inserir:

```python
    # Reunião 2026-08-20 — revisão sequencial por obra E por modo, pela mesma
    # razão que o índice de "uma ativa": o plano do cliente e o interno são
    # conjuntos de tarefas distintos e não compartilham numeração.
    # O nome continua livre; a revisão é o que dá ORDEM confiável ao histórico
    # ("V1 → V2 depois do aditivo") sem depender de alguém digitar certo.
    revisao = db.Column(db.Integer, nullable=False, default=1,
                        server_default='1')
    # Por que esta revisão existe: 'Aditivo 01', 'Replanejamento pós-chuva'.
    # Livre de propósito — a taxonomia de motivo ainda não está madura.
    motivo = db.Column(db.String(200), nullable=True)
```

- [x] **Step 4: Escrever a migration 314**

Em `migrations.py`, imediatamente antes de `def executar_migracoes():`, inserir:

```python
def _migration_314_baseline_revisao_e_motivo():
    """`cronograma_baseline.revisao` e `.motivo`.

    Reunião 2026-08-20: as linhas de base já eram guardadas (salvar de novo
    sempre criou outra), mas sem numeração o histórico dependia do texto que
    alguém digitou no nome. Revisão sequencial dá ordem; motivo diz POR QUE
    a revisão existe — na prática, quase sempre um aditivo.

    Backfill: numera as baselines existentes por (obra_id, is_cliente) na
    ordem de `criada_em` (desempate por `id`, que é estável). Sem isso todas
    ficariam em 1 e a próxima colidiria.

    Idempotente: ADD COLUMN IF NOT EXISTS; o backfill só toca quem está em 1
    e tem irmã mais antiga — rodar de novo é no-op.
    """
    from sqlalchemy import text as sa_text
    logger.info("[Migration 314] Iniciando — baseline revisao/motivo")
    with db.engine.begin() as conn:
        conn.execute(sa_text(
            "ALTER TABLE cronograma_baseline ADD COLUMN IF NOT EXISTS "
            "revisao INTEGER NOT NULL DEFAULT 1"))
        conn.execute(sa_text(
            "ALTER TABLE cronograma_baseline ADD COLUMN IF NOT EXISTS "
            "motivo VARCHAR(200)"))
        conn.execute(sa_text("""
            UPDATE cronograma_baseline AS b
               SET revisao = n.rn
              FROM (
                    SELECT id,
                           ROW_NUMBER() OVER (
                               PARTITION BY obra_id, is_cliente
                               ORDER BY criada_em NULLS FIRST, id
                           ) AS rn
                      FROM cronograma_baseline
                   ) AS n
             WHERE b.id = n.id
               AND b.revisao IS DISTINCT FROM n.rn
        """))
    logger.info("[Migration 314] Concluída com sucesso")
```

- [x] **Step 5: Registrar a migration na lista**

Em `migrations.py`, na lista `migrations_to_run`, ao final, acrescentar:

```python
            (314, "Reuniao 2026-08-20 — cronograma_baseline.revisao (sequencial por obra+modo, com backfill por criada_em) e .motivo: historico de V1/V2 deixa de depender do texto do nome", _migration_314_baseline_revisao_e_motivo),
```

- [x] **Step 6: Numerar a revisão ao criar a baseline**

Em `cronograma_views.py`, em `criar_baseline`, logo antes de
`if ativar:` (a linha `_desativar_baselines(...)`), inserir:

```python
    # Revisão = próxima da sequência desta obra NESTE modo. `max + 1` e não
    # `count + 1`: excluir a V2 não pode fazer a próxima nascer V2 de novo e
    # colidir com a comparação que alguém já guardou.
    ultima_rev = (
        db.session.query(db.func.max(CronogramaBaseline.revisao))
        .filter_by(obra_id=obra_id, admin_id=admin_id,
                   is_cliente=cliente_mode)
        .scalar()
    ) or 0
    motivo = (data.get('motivo') or '').strip() or None
```

E no construtor `CronogramaBaseline(...)`, acrescentar os dois argumentos:

```python
    baseline = CronogramaBaseline(
        obra_id=obra_id, admin_id=admin_id, nome=nome[:120],
        criada_por=current_user.id, ativa=ativar, is_cliente=cliente_mode,
        bac=bac_congelado or None,
        revisao=ultima_rev + 1, motivo=motivo[:200] if motivo else None)
```

- [x] **Step 7: Expor no JSON**

Em `cronograma_views.py`, em `_baseline_to_dict`, acrescentar as duas chaves:

```python
def _baseline_to_dict(baseline) -> dict:
    return {
        'id': baseline.id,
        'nome': baseline.nome,
        'revisao': baseline.revisao,
        'motivo': baseline.motivo,
        'ativa': baseline.ativa,
        'criada_em': baseline.criada_em.isoformat() if baseline.criada_em else None,
        'total_itens': baseline.itens.count(),
    }
```

Conferir com `sed -n '2163,2175p' cronograma_views.py` que as chaves antigas
(`id`, `nome`, `ativa`, `criada_em`, `total_itens`) continuam todas presentes —
`templates/obras/cronograma.html` e `tests/test_cronograma_baseline_api.py`
dependem delas.

- [x] **Step 8: Ordenar o histórico por revisão**

Em `cronograma_views.py`, em `listar_baselines`, trocar a ordenação da query
por `CronogramaBaseline.revisao.desc()` (a mais nova primeiro). Localizar com:

Run: `sed -n '2254,2272p' cronograma_views.py`

- [x] **Step 9: Rodar os testes**

Run: `python -m pytest tests/test_cronograma_baseline_revisao.py tests/test_cronograma_baseline_api.py -v`

Esperado: **todos PASSAM** — inclusive os antigos de `test_cronograma_baseline_api.py`, que é a rede de regressão desta task.

- [x] **Step 10: Commit**

```bash
git add models.py migrations.py cronograma_views.py tests/test_cronograma_baseline_revisao.py
git commit -m "feat(cronograma): linha de base com revisao numerada e motivo"
```

---

### Task 2: Comparar duas revisões

É a pergunta que o Paulo quer poder responder ao Guilherme e ao cliente: "era
pra entregar tal dia; com o aditivo foi pra tal dia".

**Files:**
- Modify: `cronograma_views.py` (rota nova, depois de `excluir_baseline`, que termina ~linha 2322)
- Test: `tests/test_cronograma_baseline_revisao.py`

**Interfaces:**
- Consumes: `CronogramaBaseline.revisao` (Task 1); `_guard_rotas_vinculo(obra_id)`, `_admin_id()`, `_modo_cliente()` (já existem em `cronograma_views.py`).
- Produces: `GET /obra/<obra_id>/baselines/comparar?de=<id>&para=<id>` → `200` com
  ```json
  {"status":"ok",
   "de":{"id":1,"revisao":1,"nome":"...","termino":"2026-07-10"},
   "para":{"id":2,"revisao":2,"nome":"...","termino":"2026-07-24"},
   "desvio_dias":14,
   "tarefas":[{"tarefa_id":9,"nome":"Painelização","de":"2026-07-10","para":"2026-07-24","desvio_dias":14}]}
  ```
  `termino` é o **maior** `data_fim` dos itens congelados (a entrega da obra naquela revisão). Só entram em `tarefas` as que mudaram de `data_fim`. `400` se `de`/`para` faltarem ou forem iguais; `404` se qualquer uma não for da obra/tenant/modo.

- [ ] **Step 1: Escrever o teste que falha**

Acrescentar em `tests/test_cronograma_baseline_revisao.py`:

```python
def test_comparar_revisoes_devolve_desvio_de_entrega():
    """V1 termina em 10/07. A obra é replanejada e a V2 termina em 24/07."""
    from models import TarefaCronograma

    admin_id, obra_id = _cenario()
    client = _client_como(admin_id)

    r1 = client.post(f'/cronograma/obra/{obra_id}/baseline',
                     json={'nome': 'Aprovado'}).get_json()['baseline']

    with app.app_context():
        t = (TarefaCronograma.query
             .filter_by(obra_id=obra_id, nome_tarefa='Painelização').one())
        t.data_fim = date(2026, 7, 24)
        db.session.commit()
        tarefa_id = t.id

    r2 = client.post(f'/cronograma/obra/{obra_id}/baseline',
                     json={'nome': 'Pós-aditivo',
                           'motivo': 'Aditivo 01'}).get_json()['baseline']

    resp = client.get(f"/cronograma/obra/{obra_id}/baselines/comparar"
                      f"?de={r1['id']}&para={r2['id']}")

    assert resp.status_code == 200, resp.get_data(as_text=True)
    body = resp.get_json()
    assert body['de']['termino'] == '2026-07-10'
    assert body['para']['termino'] == '2026-07-24'
    assert body['desvio_dias'] == 14
    mudou = {t['tarefa_id']: t for t in body['tarefas']}
    assert mudou[tarefa_id]['desvio_dias'] == 14
    assert len(body['tarefas']) == 1  # só a que mudou


def test_comparar_recusa_mesma_revisao():
    admin_id, obra_id = _cenario()
    client = _client_como(admin_id)
    r1 = client.post(f'/cronograma/obra/{obra_id}/baseline',
                     json={}).get_json()['baseline']

    resp = client.get(f"/cronograma/obra/{obra_id}/baselines/comparar"
                      f"?de={r1['id']}&para={r1['id']}")

    assert resp.status_code == 400


def test_comparar_404_para_baseline_de_outra_obra():
    admin_a_id, obra_a = _cenario()
    admin_b_id, obra_b = _cenario()
    client_a = _client_como(admin_a_id)
    client_b = _client_como(admin_b_id)
    ra = client_a.post(f'/cronograma/obra/{obra_a}/baseline',
                       json={}).get_json()['baseline']
    rb = client_b.post(f'/cronograma/obra/{obra_b}/baseline',
                       json={}).get_json()['baseline']

    resp = client_a.get(f"/cronograma/obra/{obra_a}/baselines/comparar"
                        f"?de={ra['id']}&para={rb['id']}")

    assert resp.status_code == 404
```

- [ ] **Step 2: Rodar para confirmar que falha**

Run: `python -m pytest tests/test_cronograma_baseline_revisao.py -k comparar -v`

Esperado: **FAIL** — 404, a rota não existe.

- [ ] **Step 3: Implementar a rota**

Em `cronograma_views.py`, logo depois do fim de `excluir_baseline`, inserir:

```python
@cronograma_bp.route('/obra/<int:obra_id>/baselines/comparar')
@login_required
def comparar_baselines(obra_id: int):
    """Desvio de datas entre duas revisões da linha de base.

    Reunião 2026-08-20: é a pergunta que o Paulo precisa responder ao
    cliente — "era pra entregar tal dia; com o aditivo foi pra tal dia".

    `termino` de uma revisão é o MAIOR `data_fim` dos itens congelados: a
    entrega da obra naquela revisão. Tarefa que não mudou de término fica
    fora de `tarefas` — a lista existe para mostrar o que se mexeu, e
    despejar o cronograma inteiro esconderia justamente isso.
    """
    guard = _guard_rotas_vinculo(obra_id)
    if guard:
        return guard
    admin_id = _admin_id()
    cliente_mode = _modo_cliente()

    try:
        de_id = int(request.args.get('de') or 0)
        para_id = int(request.args.get('para') or 0)
    except (TypeError, ValueError):
        return jsonify({'status': 'error', 'msg': 'Parâmetros de/para inválidos'}), 400
    if not de_id or not para_id:
        return jsonify({'status': 'error',
                        'msg': 'Informe as duas revisões (de e para)'}), 400
    if de_id == para_id:
        return jsonify({'status': 'error',
                        'msg': 'Escolha duas revisões diferentes'}), 400

    def _carregar(bid):
        return CronogramaBaseline.query.filter_by(
            id=bid, obra_id=obra_id, admin_id=admin_id,
            is_cliente=cliente_mode).first()

    de, para = _carregar(de_id), _carregar(para_id)
    if de is None or para is None:
        return jsonify({'status': 'error', 'msg': 'Linha de base não encontrada'}), 404

    def _itens(bl):
        return {i.tarefa_id: i for i in bl.itens}

    itens_de, itens_para = _itens(de), _itens(para)

    def _termino(itens):
        fins = [i.data_fim for i in itens.values() if i.data_fim]
        return max(fins) if fins else None

    fim_de, fim_para = _termino(itens_de), _termino(itens_para)
    desvio_obra = (fim_para - fim_de).days if (fim_de and fim_para) else None

    nomes = {
        t.id: t.nome_tarefa
        for t in TarefaCronograma.query.filter(
            TarefaCronograma.id.in_(set(itens_de) | set(itens_para))).all()
    }

    linhas = []
    for tarefa_id in sorted(set(itens_de) & set(itens_para)):
        a, b = itens_de[tarefa_id], itens_para[tarefa_id]
        if a.data_fim == b.data_fim:
            continue
        dias = ((b.data_fim - a.data_fim).days
                if (a.data_fim and b.data_fim) else None)
        linhas.append({
            'tarefa_id': tarefa_id,
            'nome': nomes.get(tarefa_id, ''),
            'de': a.data_fim.isoformat() if a.data_fim else None,
            'para': b.data_fim.isoformat() if b.data_fim else None,
            'desvio_dias': dias,
        })

    def _cabecalho(bl, termino):
        return {'id': bl.id, 'revisao': bl.revisao, 'nome': bl.nome,
                'motivo': bl.motivo,
                'termino': termino.isoformat() if termino else None}

    return jsonify({
        'status': 'ok',
        'de': _cabecalho(de, fim_de),
        'para': _cabecalho(para, fim_para),
        'desvio_dias': desvio_obra,
        'tarefas': linhas,
    })
```

- [ ] **Step 4: Rodar os testes**

Run: `python -m pytest tests/test_cronograma_baseline_revisao.py -v`

Esperado: **os 6 PASSAM.**

- [ ] **Step 5: Commit**

```bash
git add cronograma_views.py tests/test_cronograma_baseline_revisao.py
git commit -m "feat(cronograma): comparar duas revisoes da linha de base"
```

---

### Task 3: Nomenclatura e histórico na tela

Duas coisas: os rótulos que hoje confundem, e o histórico que já existe mas não
mostra revisão, motivo nem comparação.

O rótulo "Planejado" na tabela é hoje um **percentual** ("progresso planejado
para hoje"), enquanto as colunas de data — que é o que o Alan move e o que o
Paulo chama de planejado — não têm rótulo nenhum. Essa é a colisão a desfazer.

**Files:**
- Modify: `templates/obras/cronograma.html:200-213` (cabeçalhos)
- Modify: `templates/obras/cronograma.html:3348-3380` (`carregarBaselines`, `abrirModalBaseline`)
- Test: verificação manual + `tests/test_cronograma_interface_obra.py` como rede de regressão

**Interfaces:**
- Consumes: `GET /obra/<id>/baselines` (agora com `revisao` e `motivo`) e `GET /obra/<id>/baselines/comparar` (Task 2).
- Produces: nada.

- [ ] **Step 1: Renomear os cabeçalhos**

Em `templates/obras/cronograma.html`, no `<thead>`, aplicar:

```html
              <th class="th-date" title="Data de início PLANEJADA — é esta que se move durante a obra">Início (plan.)</th>
              <th class="th-date" title="Data de término PLANEJADA — é esta que se move durante a obra">Término (plan.)</th>
```

e

```html
              <th class="th-perc" title="Progresso planejado para hoje (cálculo linear de datas)">% Planejado</th>
              <th class="th-perc" title="Progresso realizado, calculado automaticamente pelos apontamentos do RDO">% Realizado</th>
```

**Não** mexer na ordem nem na quantidade de colunas: a navegação por célula da
grade usa índice de coluna (`COLS_NAV`, `td.cellIndex`) e a coluna Desvio já
depende de `baseline_ativa`. Só o texto e o `title` mudam.

- [ ] **Step 2: Rodar a regressão de interface**

Run: `python -m pytest tests/test_cronograma_interface_obra.py tests/test_cronograma_grade_api.py -v`

Esperado: **todos PASSAM.** Se algum teste casar por texto de cabeçalho
(`"Planejado"`), atualizar o teste — é mudança de rótulo intencional.

- [ ] **Step 3: Mostrar revisão e motivo no histórico**

Em `templates/obras/cronograma.html`, em `carregarBaselines`, substituir o
`box.innerHTML = data.baselines.map(...)` por:

```javascript
  box.innerHTML = data.baselines.map(b => `
    <div class="d-flex align-items-center justify-content-between border rounded px-2 py-1 mb-1">
      <div class="small">
        <span class="badge bg-dark me-1" title="Revisão da linha de base">V${b.revisao}</span>
        ${b.ativa ? '<span class="badge bg-success me-1">ativa</span>' : ''}
        <strong>${b.nome}</strong>
        ${b.motivo ? `<span class="badge bg-warning text-dark ms-1" title="Motivo da revisão">${b.motivo}</span>` : ''}
        <span class="text-muted">— ${b.total_itens} tarefa(s)</span>
      </div>
      <div class="btn-group btn-group-sm">
        ${b.ativa ? '' : `<button class="btn btn-outline-primary" onclick="ativarBaseline(${b.id})" title="Usar esta na comparação"><i class="fas fa-check"></i></button>`}
        <button class="btn btn-outline-secondary" onclick="marcarParaComparar(${b.id}, ${b.revisao})" title="Comparar com outra revisão"><i class="fas fa-code-compare"></i></button>
        <button class="btn btn-outline-danger" onclick="excluirBaseline(${b.id}, '${b.nome.replace(/'/g, '')}')" title="Excluir"><i class="fas fa-trash-can"></i></button>
      </div>
    </div>`).join('');
```

- [ ] **Step 4: Implementar a comparação no front**

Logo depois de `carregarBaselines`, inserir:

```javascript
// ── Comparar duas revisões (reunião 2026-08-20) ──
// Dois cliques no ícone de comparação: o 1º marca a origem, o 2º dispara.
let _blComparar = null;

function marcarParaComparar(id, revisao) {
  if (_blComparar === null) {
    _blComparar = { id, revisao };
    toast(`V${revisao} marcada. Clique em outra revisão para comparar.`);
    return;
  }
  if (_blComparar.id === id) {
    _blComparar = null;
    toast('Comparação cancelada.');
    return;
  }
  const de = _blComparar;
  _blComparar = null;
  _executarComparacao(de.id, id);
}

async function _executarComparacao(deId, paraId) {
  const data = await _baselineFetch(
    apiUrl(`/baselines/comparar?de=${deId}&para=${paraId}`), {});
  if (!data) return;
  const box = document.getElementById('bl_lista');
  if (!box) return;
  const sinal = (n) => (n > 0 ? `+${n}` : `${n}`);
  const linhas = data.tarefas.length
    ? data.tarefas.map(t => `
        <tr><td class="small">${t.nome}</td>
            <td class="small text-muted">${formatDate(t.de)}</td>
            <td class="small">${formatDate(t.para)}</td>
            <td class="small text-end ${t.desvio_dias > 0 ? 'text-danger' : 'text-success'}">${sinal(t.desvio_dias)} d</td></tr>`).join('')
    : '<tr><td colspan="4" class="small text-muted">Nenhuma tarefa mudou de término entre as duas revisões.</td></tr>';
  box.innerHTML = `
    <div class="border rounded p-2 mb-2">
      <div class="d-flex justify-content-between align-items-center mb-2">
        <strong class="small">V${data.de.revisao} → V${data.para.revisao}</strong>
        <button class="btn btn-sm btn-outline-secondary" onclick="carregarBaselines()">
          <i class="fas fa-arrow-left"></i> Voltar
        </button>
      </div>
      <div class="small mb-2">
        Entrega: <span class="text-muted">${formatDate(data.de.termino)}</span>
        → <strong>${formatDate(data.para.termino)}</strong>
        <span class="badge ${data.desvio_dias > 0 ? 'bg-danger' : 'bg-success'} ms-1">${sinal(data.desvio_dias)} dia(s)</span>
      </div>
      <table class="table table-sm mb-0">
        <thead><tr><th class="small">Tarefa</th><th class="small">De</th><th class="small">Para</th><th class="small text-end">Desvio</th></tr></thead>
        <tbody>${linhas}</tbody>
      </table>
    </div>`;
}
```

- [ ] **Step 5: Acrescentar o campo motivo ao modal**

Localizar o modal com `grep -n 'id="bl_nome"' templates/obras/cronograma.html`
e, logo depois do input de nome, inserir:

```html
          <div class="mb-2">
            <label for="bl_motivo" class="form-label small mb-1">Motivo da revisão</label>
            <input type="text" class="form-control form-control-sm" id="bl_motivo"
                   maxlength="200" placeholder="Ex.: Aditivo 01">
            <div class="form-text">Opcional. Deixe em branco na primeira linha de base (o cronograma aprovado).</div>
          </div>
```

E na função que faz o POST (`salvarBaseline`, ~linha 3319), incluir o campo no
body. Localizar com `grep -n "apiUrl('/baseline')" templates/obras/cronograma.html`
e acrescentar `motivo` ao objeto enviado:

```javascript
    body: JSON.stringify({ nome: nome, ativar: ativar,
                           motivo: (document.getElementById('bl_motivo')?.value || '').trim() }),
```

Conferir o nome real das variáveis `nome` e `ativar` na função antes de editar
— não renomear o que já existe.

- [ ] **Step 6: Verificar na aplicação rodando**

Numa obra com cronograma e editor v2 ligado:
1. Cabeçalhos mostram "Início (plan.)", "Término (plan.)", "% Planejado", "% Realizado".
2. Salvar uma linha de base sem motivo → aparece "V1" no histórico.
3. Mover o término de uma tarefa, salvar outra linha de base com motivo "Aditivo 01" → aparece "V2" com o badge do motivo.
4. Clicar no ícone de comparar na V1, depois na V2 → aparece a tabela com o desvio de entrega e só as tarefas que mudaram.
5. "Voltar" recarrega a lista.

- [ ] **Step 7: Commit**

```bash
git add templates/obras/cronograma.html
git commit -m "feat(cronograma): rotulos planejado/linha de base e historico de revisoes com comparacao"
```
