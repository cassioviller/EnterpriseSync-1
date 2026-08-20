# RDO — Efetivo Interno e Terceiros — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Permitir que o encarregado registre, em qualquer atividade do RDO, **o efetivo próprio** (só pessoal operacional) **e as equipes de terceiros** (nome do terceiro + quantidade de pessoas) — que é o que o Alan já escreve à mão ("Abraão, 11 pessoas") e o Abel não registra de forma nenhuma.

**Architecture:** Quase tudo já existe. `Subempreiteiro` e `RDOSubempreitadaApontamento` (com `qtd_pessoas`, `horas_trabalhadas` e `homem_hora` calculado por listener) estão no modelo, e a rota `POST /cronograma/rdo/<rdo_id>/apontar-subempreitada` **não** valida `tarefa.responsavel` — ela aceita apontamento em qualquer tarefa. A trava é puramente de front: `templates/rdo/novo.html` só desenha o botão de subempreitada quando `responsavel === 'subempreitada'`, e nas tarefas de `terceiros` desenha apenas um checkbox "Concluído". Este plano (1) destrava o front, (2) cria a separação operacional × administrativo em `Funcao` para o seletor de efetivo parar de listar o pessoal do escritório.

**Tech Stack:** Python 3, Flask, SQLAlchemy, PostgreSQL, Jinja2, Bootstrap 5, vanilla JS, Font Awesome, pytest.

**Spec:** Não há spec escrito. Este plano nasce da sessão de brainstorming de 2026-08-20.

## Global Constraints

- Migrations vivem em `migrations.py`: função `_migration_NNN_slug()` + entrada `(NNN, "descrição", _migration_NNN_slug)` na lista `migrations_to_run` (linha ~6939). **O último número usado é 311** — o próximo livre é 312. O runner pula por NÚMERO, então número repetido = migração que nunca roda.
- Toda migration é idempotente (`IF NOT EXISTS` / `ADD COLUMN IF NOT EXISTS`) e **levanta** em falha, para não ser gravada como aplicada.
- Toda tabela carrega `admin_id` (convenção de tenancy). Toda query filtra por `admin_id`.
- Front: Bootstrap 5 + vanilla JS, sem framework. Ícones Font Awesome.
- Números em pt-BR na UI (vírgula decimal).
- Testes em `tests/`, `pytestmark = pytest.mark.integration`. Rodar: `python -m pytest tests/<arquivo>.py -v`
- Commits em português: `feat(rdo):`, `feat(cadastros):`, `test(rdo):`.

## Fora de escopo (decidido na reunião)

- **Medição / valor do subempreiteiro.** O Paulo foi explícito: "no subempreiteiro a gente vai ter que pensar numa interface pra eles, tipo, da medição deles. Eu não acho que é pra agora."
- **Funcionários coringa "Montador" e "Ajudante".** Não precisam de código: assim que o cadastro de funcionário aceitar só o nome (plano `2026-08-20-cadastro-funcionario-operacional.md`), são dois cadastros normais feitos pela Ana. Se depois virarem um conceito de sistema, entra em plano próprio.

---

## File Structure

| Arquivo | Responsabilidade |
|---|---|
| `migrations.py` (modificar, ~linha 6939 + nova função) | Migration 312: coluna `funcao.operacional`. |
| `models.py` (modificar, `class Funcao`, linha 157) | Declarar `operacional` no modelo. |
| `configuracoes_views.py` (modificar, `criar_funcao` ~462, `editar_funcao` ~500) | Ler o checkbox do formulário. |
| `templates/configuracoes/funcao_form.html` (modificar) | Checkbox "Função operacional (aparece no efetivo do RDO)". |
| `views/api.py` (modificar, `api_funcionarios_por_obra` linha 33) | Filtro `?operacional=1` no seletor de efetivo. |
| `templates/rdo/novo.html` (modificar, ~1180-1310 e ~1740-1800) | Botão de terceiros em toda folha, não só nas de `responsavel='subempreitada'`. |
| `tests/test_rdo_efetivo_terceiros.py` (criar) | Cobre o filtro operacional e o apontamento de terceiro em tarefa de empresa. |

---

### Task 1: Coluna `operacional` em `Funcao`

Separa quem aparece no efetivo do RDO (montador, ajudante, encarregado) de
quem não deveria aparecer (administrativo). Fica em `Funcao` e não em
`Departamento` porque é a função que diz o que a pessoa faz — "Auxiliar
Administrativo" e "Montador" podem estar no mesmo departamento.

Default `TRUE`: nenhuma função existente some do RDO no deploy. A Ana desmarca
as administrativas depois, pela tela de Funções.

**Files:**
- Modify: `models.py:157-175` (`class Funcao`)
- Modify: `migrations.py` (nova função `_migration_312_funcao_operacional` + entrada na lista)
- Test: `tests/test_rdo_efetivo_terceiros.py`

**Interfaces:**
- Produces: `Funcao.operacional: bool` (NOT NULL, default/server_default TRUE). Consumido pela Task 2 (`views/api.py`) e pela Task 3 (formulário).

- [x] **Step 1: Escrever o teste que falha**

Criar `tests/test_rdo_efetivo_terceiros.py`:

```python
"""Efetivo do RDO: pessoal operacional próprio + equipes de terceiros.

Reunião de 2026-08-20: o Alan anota "Abraão, 11 pessoas" no papel porque o
RDO não tem onde registrar terceiro fora das tarefas marcadas como
`responsavel='subempreitada'`; e o seletor de efetivo lista o pessoal
administrativo junto com o de campo.
"""
import os
import sys
from datetime import date

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import main  # noqa: F401 — registra os blueprints
from app import app, db
from models import Funcao, Funcionario
from test_cronograma_versao_service import _ambiente

pytestmark = pytest.mark.integration


@pytest.fixture(autouse=True)
def _config():
    app.config['TESTING'] = True
    app.config['WTF_CSRF_ENABLED'] = False
    if not app.secret_key:
        app.secret_key = 'test-rdo-efetivo'
    yield


def test_funcao_nasce_operacional():
    """Default TRUE — nenhuma função existente some do RDO no deploy."""
    with app.app_context():
        admin, _obra = _ambiente()
        f = Funcao(nome='Montador', admin_id=admin.id, salario_base=0.0)
        db.session.add(f)
        db.session.commit()
        assert f.operacional is True


def test_funcao_pode_ser_marcada_como_administrativa():
    with app.app_context():
        admin, _obra = _ambiente()
        f = Funcao(nome='Auxiliar Administrativo', admin_id=admin.id,
                   salario_base=0.0, operacional=False)
        db.session.add(f)
        db.session.commit()
        assert f.operacional is False
```

- [x] **Step 2: Rodar para confirmar que falha**

Run: `python -m pytest tests/test_rdo_efetivo_terceiros.py -v`

Esperado: **FAIL** — `TypeError: 'operacional' is an invalid keyword argument for Funcao`.

- [x] **Step 3: Declarar a coluna no modelo**

Em `models.py`, na `class Funcao`, logo depois de `salario_base`, inserir:

```python
    # Reunião 2026-08-20 — separa o efetivo de campo do pessoal de escritório.
    # O seletor de efetivo do RDO lista SÓ funções operacionais. Fica aqui e
    # não em Departamento porque é a função que diz o que a pessoa faz:
    # "Auxiliar Administrativo" e "Montador" podem dividir departamento.
    # Default TRUE para nenhuma função existente sumir do RDO no deploy.
    operacional = db.Column(db.Boolean, nullable=False, default=True,
                            server_default='true')
```

- [x] **Step 4: Escrever a migration 312**

Em `migrations.py`, imediatamente antes de `def executar_migracoes():` (linha ~6880), inserir:

```python
def _migration_312_funcao_operacional():
    """Coluna `funcao.operacional` — separa efetivo de campo de administrativo.

    O seletor de efetivo do RDO (`/api/obras/<id>/funcionarios?operacional=1`)
    passa a listar só quem tem função operacional. Reunião 2026-08-20: o Paulo
    pediu "aqui tem que estar só o pessoal operacional".

    DEFAULT TRUE de propósito: no deploy nenhuma função existente sai do RDO.
    Marcar as administrativas é trabalho de cadastro, feito depois pela tela
    de Funções — não é decisão que uma migration possa adivinhar por nome.

    Idempotente: ADD COLUMN IF NOT EXISTS.
    """
    from sqlalchemy import text as sa_text
    logger.info("[Migration 312] Iniciando — funcao.operacional")
    with db.engine.begin() as conn:
        conn.execute(sa_text(
            "ALTER TABLE funcao ADD COLUMN IF NOT EXISTS "
            "operacional BOOLEAN NOT NULL DEFAULT TRUE"))
    logger.info("[Migration 312] Concluída com sucesso")
```

- [x] **Step 5: Registrar a migration na lista**

Em `migrations.py`, na lista `migrations_to_run`, logo depois da linha da 311, acrescentar:

```python
            (312, "Reuniao 2026-08-20 — funcao.operacional: separa o efetivo de campo do pessoal de escritorio no seletor do RDO. DEFAULT TRUE para ninguem sumir no deploy", _migration_312_funcao_operacional),
```

- [x] **Step 6: Rodar os testes**

Run: `python -m pytest tests/test_rdo_efetivo_terceiros.py -v`

Esperado: **os 2 PASSAM.**

- [x] **Step 7: Commit**

```bash
git add models.py migrations.py tests/test_rdo_efetivo_terceiros.py
git commit -m "feat(cadastros): funcao.operacional separa efetivo de campo do administrativo"
```

---

### Task 2: Seletor de efetivo do RDO lista só o operacional

**Files:**
- Modify: `views/api.py:33-60` (`api_funcionarios_por_obra`)
- Modify: `templates/rdo/novo.html:777` (a chamada `fetch`)
- Test: `tests/test_rdo_efetivo_terceiros.py`

**Interfaces:**
- Consumes: `Funcao.operacional` (Task 1).
- Produces: `GET /api/obras/<obra_id>/funcionarios?operacional=1` → `{'success': True, 'funcionarios': [{'id', 'nome', 'funcao', 'cargo'}], 'total': N}`. Sem o parâmetro o comportamento é o de hoje (todos os ativos) — outras telas consomem essa rota e não devem mudar.

- [ ] **Step 1: Escrever o teste que falha**

Acrescentar em `tests/test_rdo_efetivo_terceiros.py`:

```python
def _login(admin):
    """Client autenticado como o admin, fora de app_context aberto."""
    from test_cronograma_endpoints_m05 import _client_como
    return _client_como(admin)


def _cenario_efetivo():
    """Um funcionário operacional (Montador) e um administrativo."""
    with app.app_context():
        admin, obra = _ambiente()
        op = Funcao(nome='Montador', admin_id=admin.id, salario_base=0.0,
                    operacional=True)
        adm = Funcao(nome='Auxiliar Administrativo', admin_id=admin.id,
                     salario_base=0.0, operacional=False)
        db.session.add_all([op, adm])
        db.session.flush()
        db.session.add(Funcionario(
            codigo=f'OP{admin.id}', nome='Davi Montador', cpf=f'{admin.id:011d}',
            data_admissao=date(2026, 1, 5), admin_id=admin.id,
            funcao_id=op.id, ativo=True))
        db.session.add(Funcionario(
            codigo=f'AD{admin.id}', nome='Ana Escritorio', cpf=f'{admin.id + 1:011d}',
            data_admissao=date(2026, 1, 5), admin_id=admin.id,
            funcao_id=adm.id, ativo=True))
        db.session.commit()
        return admin, obra.id


def test_api_efetivo_filtra_administrativo():
    admin, obra_id = _cenario_efetivo()
    client = _login(admin)

    resp = client.get(f'/api/obras/{obra_id}/funcionarios?operacional=1')

    assert resp.status_code == 200
    nomes = [f['nome'] for f in resp.get_json()['funcionarios']]
    assert 'Davi Montador' in nomes
    assert 'Ana Escritorio' not in nomes


def test_api_sem_parametro_continua_devolvendo_todos():
    """Outras telas consomem esta rota — sem o parâmetro nada muda."""
    admin, obra_id = _cenario_efetivo()
    client = _login(admin)

    resp = client.get(f'/api/obras/{obra_id}/funcionarios')

    nomes = [f['nome'] for f in resp.get_json()['funcionarios']]
    assert 'Davi Montador' in nomes
    assert 'Ana Escritorio' in nomes
```

- [ ] **Step 2: Rodar para confirmar que falha**

Run: `python -m pytest tests/test_rdo_efetivo_terceiros.py::test_api_efetivo_filtra_administrativo -v`

Esperado: **FAIL** — `'Ana Escritorio' in nomes` (o filtro ainda não existe).

- [ ] **Step 3: Implementar o filtro na API**

Em `views/api.py`, dentro de `api_funcionarios_por_obra`, substituir:

```python
        funcionarios = Funcionario.query.filter_by(
            admin_id=admin_id, ativo=True
        ).order_by(Funcionario.nome).all()
```

por:

```python
        q = Funcionario.query.filter_by(admin_id=admin_id, ativo=True)
        # `?operacional=1` — o seletor de efetivo do RDO. Sem o parâmetro a
        # rota continua devolvendo todos os ativos: outras telas dependem
        # disso. Funcionário SEM função entra no filtro (é o caso do cadastro
        # rápido que a Ana faz com só o nome), porque presumir escritório
        # sumiria com ele do RDO justamente no dia em que foi contratado.
        if request.args.get('operacional') in ('1', 'true', 'True'):
            from models import Funcao
            q = (q.outerjoin(Funcao, Funcionario.funcao_id == Funcao.id)
                  .filter(db.or_(Funcionario.funcao_id.is_(None),
                                 Funcao.operacional.is_(True))))
        funcionarios = q.order_by(Funcionario.nome).all()
```

Conferir que `request`, `db` e `db.or_` estão importados no topo de
`views/api.py`; se `db.or_` não existir no namespace, use
`from sqlalchemy import or_` e troque `db.or_` por `or_`.

- [ ] **Step 4: Rodar os testes**

Run: `python -m pytest tests/test_rdo_efetivo_terceiros.py -v`

Esperado: **os 4 PASSAM.**

- [ ] **Step 5: Ligar o filtro na tela do RDO**

Em `templates/rdo/novo.html`, linha ~777, trocar:

```javascript
        const resp = await fetch(`/api/obras/${obraId}/funcionarios`);
```

por:

```javascript
        // `operacional=1`: o efetivo do RDO é o pessoal de campo. Quem tem
        // função marcada como administrativa não entra (reunião 2026-08-20).
        const resp = await fetch(`/api/obras/${obraId}/funcionarios?operacional=1`);
```

- [ ] **Step 6: Commit**

```bash
git add views/api.py templates/rdo/novo.html tests/test_rdo_efetivo_terceiros.py
git commit -m "feat(rdo): seletor de efetivo lista so o pessoal operacional"
```

---

### Task 3: Marcar a função como operacional pela tela de Funções

Sem isto a coluna da Task 1 só é editável por SQL.

**Files:**
- Modify: `configuracoes_views.py:462-468` (`criar_funcao`) e `:500-503` (`editar_funcao`)
- Modify: `templates/configuracoes/funcao_form.html` (bloco novo antes de `<div class="d-flex gap-2">`)
- Test: manual (a tela é CRUD de cadastro; a regra já está coberta pelos testes da Task 1 e 2)

**Interfaces:**
- Consumes: `Funcao.operacional` (Task 1).
- Produces: formulário envia `operacional` como checkbox (`'on'` quando marcado, ausente quando não).

- [ ] **Step 1: Acrescentar o checkbox ao formulário**

Em `templates/configuracoes/funcao_form.html`, imediatamente antes de
`<div class="d-flex gap-2">`, inserir:

```html
          <div class="mb-4">
            <div class="form-check">
              <input class="form-check-input" type="checkbox"
                     id="operacional" name="operacional"
                     {% if funcao is none or funcao.operacional %}checked{% endif %}>
              <label class="form-check-label fw-semibold" for="operacional">
                Função operacional
              </label>
            </div>
            <div class="form-text">
              Marcada, aparece no efetivo do RDO. Desmarque para pessoal
              administrativo, que não é apontado em atividade de obra.
            </div>
          </div>
```

- [ ] **Step 2: Ler o campo na criação**

Em `configuracoes_views.py`, em `criar_funcao`, no construtor `Funcao(...)`,
acrescentar o argumento:

```python
                operacional=('operacional' in request.form),
```

O construtor fica:

```python
            funcao = Funcao(
                nome=request.form['nome'],
                descricao=request.form.get('descricao'),
                salario_base=float(request.form.get('salario_base', 0)),
                admin_id=admin_id,
                insumo_id=insumo_id,
                operacional=('operacional' in request.form),
            )
```

- [ ] **Step 3: Ler o campo na edição**

Em `configuracoes_views.py`, em `editar_funcao`, logo depois de
`funcao.descricao = request.form.get('descricao')`, inserir:

```python
            # Checkbox: ausente no POST = desmarcado. Só atualiza quando o
            # formulário de fato veio da tela de funções (marcador `origem`
            # não existe aqui, então basta o POST ter o campo `nome`, que é
            # obrigatório na tela e garante que o body é do formulário).
            funcao.operacional = ('operacional' in request.form)
```

- [ ] **Step 4: Verificar na aplicação rodando**

Subir a app e, em `/configuracoes/funcoes`:
1. Criar uma função "Auxiliar Administrativo" com o checkbox **desmarcado**.
2. Editá-la e confirmar que o checkbox continua desmarcado ao reabrir.
3. Marcar, salvar, reabrir e confirmar que ficou marcado.

Se a app não subir localmente, invocar a skill `run` para descobrir o comando
do projeto.

- [ ] **Step 5: Commit**

```bash
git add configuracoes_views.py templates/configuracoes/funcao_form.html
git commit -m "feat(cadastros): marcar funcao como operacional pela tela de funcoes"
```

---

### Task 4: Registrar equipe de terceiro em qualquer atividade do RDO

Hoje o bloco de terceiros só existe quando `responsavel === 'subempreitada'`
(`templates/rdo/novo.html:1226`). Nas tarefas de `terceiros` há só um checkbox
"Concluído", e nas de `empresa` nada — que é exatamente o caso do Abraão na
fundação, uma atividade que também tem gente nossa.

O backend já aceita: `apontar_subempreitada` (`cronograma_views.py:2585`) valida
tarefa, tenant e `is_cliente`, mas **não** olha `responsavel`. E não há risco de
dobrar percentual: `atualizar_percentual_tarefa` só converte subempreitada em
avanço via `quantidade_produzida`, então um apontamento de efetivo puro
(`quantidade_produzida = 0`) não mexe no percentual — a Task 4 pina isso em teste.

**Files:**
- Modify: `templates/rdo/novo.html:1226-1306` (bloco `acaoInner`)
- Modify: `templates/rdo/novo.html:1755` (`_subCarregarTarefas`, filtro por `responsavel`)
- Test: `tests/test_rdo_efetivo_terceiros.py`

**Interfaces:**
- Consumes: `POST /cronograma/rdo/<rdo_id>/apontar-subempreitada` com body `{tarefa_cronograma_id, subempreiteiro_id, qtd_pessoas, horas_trabalhadas, quantidade_produzida, observacoes}` → `{'status':'ok','apontamento':{...}}`; `GET /subempreiteiros/api/lista` → `{'status':'ok','subempreiteiros':[...]}`.
- Produces: nada consumido por tasks posteriores.

- [ ] **Step 1: Escrever o teste que falha**

Acrescentar em `tests/test_rdo_efetivo_terceiros.py`:

```python
def test_apontar_terceiro_em_tarefa_de_empresa_nao_mexe_no_percentual():
    """Efetivo de terceiro (11 pessoas, 0 produzido) numa tarefa da empresa.

    É o caso do Abraão na fundação: a atividade é nossa, mas tem equipe
    terceira junto. Registrar o efetivo NÃO pode alterar o avanço — quem
    move percentual é produção, não gente presente.
    """
    from models import (RDO, Subempreiteiro, TarefaCronograma,
                        RDOSubempreitadaApontamento)
    from test_cronograma_versao_service import _tarefa

    with app.app_context():
        admin, obra = _ambiente()
        tarefa = _tarefa(obra, admin, 'Fundação', ordem=0,
                         duracao_dias=10,
                         data_inicio=date(2026, 7, 1),
                         data_fim=date(2026, 7, 10),
                         quantidade_total=100.0,
                         unidade_medida='m3',
                         responsavel='empresa',
                         percentual_concluido=40.0)
        sub = Subempreiteiro(nome='Abraão', admin_id=admin.id, ativo=True)
        db.session.add(sub)
        rdo = RDO(numero_rdo=f'RDO-EF-{admin.id}',
                  data_relatorio=date(2026, 7, 5),
                  obra_id=obra.id, admin_id=admin.id)
        db.session.add(rdo)
        db.session.commit()
        ctx = dict(admin=admin, rdo_id=rdo.id, tarefa_id=tarefa.id,
                   sub_id=sub.id)

    client = _login(ctx['admin'])
    resp = client.post(
        f"/cronograma/rdo/{ctx['rdo_id']}/apontar-subempreitada",
        json={'tarefa_cronograma_id': ctx['tarefa_id'],
              'subempreiteiro_id': ctx['sub_id'],
              'qtd_pessoas': 11,
              'horas_trabalhadas': 8.8,
              'quantidade_produzida': 0},
    )

    assert resp.status_code == 200, resp.get_data(as_text=True)
    assert resp.get_json()['apontamento']['qtd_pessoas'] == 11

    with app.app_context():
        apt = RDOSubempreitadaApontamento.query.filter_by(
            rdo_id=ctx['rdo_id']).one()
        assert apt.qtd_pessoas == 11
        # homem_hora = 0 produzido / (11 * 8.8) = 0.0 (listener before_insert)
        assert apt.homem_hora == pytest.approx(0.0)
        # O avanço da tarefa NÃO se mexeu.
        t = TarefaCronograma.query.get(ctx['tarefa_id'])
        assert t.percentual_concluido == pytest.approx(40.0, abs=0.01)
```

- [ ] **Step 2: Rodar para ver o resultado**

Run: `python -m pytest tests/test_rdo_efetivo_terceiros.py::test_apontar_terceiro_em_tarefa_de_empresa_nao_mexe_no_percentual -v`

Esperado: **PASSA** — o backend já suporta. Se falhar no `status_code`, leia a
mensagem: a rota exige a flag V2 do tenant (`_check_v2`), que `_ambiente()` já
liga. Se falhar no assert do percentual, `atualizar_percentual_tarefa` está
zerando a tarefa e a mudança de front **não pode** ser feita antes de corrigir
isso — pare e reporte.

- [ ] **Step 3: Commit do teste**

```bash
git add tests/test_rdo_efetivo_terceiros.py
git commit -m "test(rdo): apontar efetivo de terceiro em tarefa da empresa nao move percentual"
```

- [ ] **Step 4: Desenhar o botão de terceiros em toda folha**

Em `templates/rdo/novo.html`, no bloco `acaoInner` (~linha 1200), o `if/else`
por responsável hoje é mutuamente exclusivo. Trocar a estrutura para que o
bloco de terceiros seja **acrescentado** a todos os ramos de folha.

4a. Extrair o HTML do botão para uma função. Logo antes de
`function _rdoBadgeResponsavel(` (ou, se não existir ali, logo antes da função
que monta `acaoInner`), inserir:

```javascript
// Reunião 2026-08-20 — efetivo de terceiro em QUALQUER atividade, não só nas
// marcadas como subempreitada. É o caso do Abraão na fundação: atividade
// nossa, com equipe terceira junto. O backend (`apontar-subempreitada`) nunca
// olhou `responsavel` — a trava era só esta função de desenho.
function _rdoBotaoTerceiros(t, nomeTarefaEsc) {
    const apontados = (_subPendingApontamentos || [])
        .filter(a => a.tarefa_cronograma_id === t.id).length;
    return `
        <button type="button"
                class="btn btn-sm ${apontados > 0 ? 'btn-primary' : 'btn-outline-secondary'} d-flex align-items-center gap-1 px-2"
                id="btn-terceiro-${t.id}"
                onclick="event.stopPropagation(); abrirModalEquipeTarefa(${t.id}, '${nomeTarefaEsc}')"
                title="Registrar equipe de terceiro nesta atividade">
          <i class="fas fa-hammer"></i>
          <span class="badge rounded-pill bg-light text-dark ms-1" id="badge-terceiro-${t.id}"
                onclick="event.stopPropagation(); abrirListaSubempreitadaNovo(${t.id}, '${nomeTarefaEsc}')"
                title="Ver/editar apontamentos de terceiro desta tarefa"
                style="${apontados > 0 ? '' : 'display:none'};font-size:.7rem;cursor:pointer">${apontados}</span>
        </button>`;
}
```

4b. No ramo `isTerceiros`, trocar o fechamento do template para incluir o botão.
O `acaoInner` desse ramo passa a terminar assim (acrescentar a linha do botão
logo antes do `</div>` final):

```javascript
                    <label class="form-check-label small fw-semibold ms-1" for="chk_terc_${t.id}">
                      Concluído
                    </label>
                  </div>
                  ${_rdoBotaoTerceiros(t, nomeTarefaEsc)}
                </div>`;
```

4c. No ramo `isSub`, substituir o `<button>` inline inteiro pela chamada da
função — o HTML é idêntico, muda só o id (`btn-terceiro-` em vez de
`btn-equipe-`), para não colidir com o botão de efetivo interno:

```javascript
            acaoInner = `
                <div class="d-flex align-items-center gap-1" onclick="event.stopPropagation()">
                  ${t.quantidade_total ? `<small class="text-muted">Total: ${qty_total}</small>` : ''}
                  ${_rdoBotaoTerceiros(t, nomeTarefaEsc)}
                </div>`;
```

4d. No ramo `else` (empresa), acrescentar o botão de terceiros **depois** do
botão de efetivo interno. O fim do `acaoInner` fica:

```javascript
                <button type="button"
                        class="btn btn-sm btn-outline-secondary d-flex align-items-center gap-1 px-2"
                        id="btn-equipe-${t.id}"
                        onclick="event.stopPropagation(); abrirModalEquipeTarefa(${t.id}, '${nomeTarefaEsc}')"
                        title="Alocar equipe nesta atividade">
                    <i class="fas fa-users"></i>
                    <span class="badge rounded-pill bg-primary ms-1" id="badge-equipe-${t.id}" style="display:none;font-size:.7rem">0</span>
                </button>
                ${_rdoBotaoTerceiros(t, nomeTarefaEsc)}`;
```

- [ ] **Step 5: Liberar a lista de tarefas do modal de terceiros**

Em `templates/rdo/novo.html`, em `_subCarregarTarefas` (~linha 1755), trocar:

```javascript
    const tarefas = (window.__tarefasRDOAll || []).filter(t => (t.responsavel || '') === 'subempreitada');
```

por:

```javascript
    // Toda folha pode receber equipe de terceiro (reunião 2026-08-20).
    // Pais/resumo continuam fora: apontamento é sempre em folha.
    const tarefas = (window.__tarefasRDOAll || []).filter(t => !t.is_pai);
```

Se o payload de `/cronograma/obra/<id>/tarefas-rdo` não expuser `is_pai`,
conferir o nome real da chave em `cronograma_views.py:2447-2580` e usar a que
existir (a rota monta o dict lá); em último caso, filtrar por
`!(window.__tarefasRDOAll || []).some(x => x.tarefa_pai_id === t.id)`.

- [ ] **Step 6: Liberar o pré-carregamento da lista de subempreiteiros**

Em `templates/rdo/novo.html`, ~linha 1127, trocar:

```javascript
        if (json.tarefas.some(t => (t.responsavel || '') === 'subempreitada')) {
```

por:

```javascript
        if (json.tarefas && json.tarefas.length) {
```

- [ ] **Step 7: Verificar na aplicação rodando**

Abrir um RDO novo numa obra com cronograma e conferir:
1. Numa atividade de `empresa`, existem **dois** botões: 👥 (efetivo interno) e 🔨 (terceiro).
2. O botão de terceiro abre o modal, lista os subempreiteiros cadastrados e a tarefa correta.
3. Salvar "Abraão / 11 pessoas / 8,8h / 0 produzido" e conferir que o badge do botão vira `1`.
4. Recarregar a tela e conferir que o percentual da atividade **não** mudou.
5. Numa atividade de `terceiros`, o checkbox "Concluído" continua funcionando e o botão 🔨 aparece ao lado.

- [ ] **Step 8: Commit**

```bash
git add templates/rdo/novo.html
git commit -m "feat(rdo): registrar equipe de terceiro em qualquer atividade"
```

---

### Task 5: Repetir a liberação na tela de edição de RDO

`templates/rdo/editar_rdo.html` também referencia subempreitada e precisa do
mesmo tratamento, senão o RDO fica editável só pela criação.

**Files:**
- Modify: `templates/rdo/editar_rdo.html`
- Test: verificação manual (o backend já está coberto pela Task 4)

**Interfaces:**
- Consumes: as mesmas rotas da Task 4.
- Produces: nada.

- [ ] **Step 1: Mapear as ocorrências**

Run: `grep -n "subempreitada\|responsavel" templates/rdo/editar_rdo.html`

Anotar cada linha que condiciona UI a `responsavel === 'subempreitada'`.

- [ ] **Step 2: Aplicar as mesmas trocas da Task 4**

Para cada ocorrência mapeada, aplicar a transformação equivalente aos Steps 4,
5 e 6 da Task 4: o bloco de terceiros deixa de ser exclusivo do responsável
`subempreitada` e passa a ser acrescentado a toda folha.

Se `editar_rdo.html` **não** tiver o bloco de apontamento de subempreitada (só
menções em outro contexto, como um resumo de leitura), registrar isso no commit
e não inventar tela nova — a criação é o fluxo de campo.

- [ ] **Step 3: Verificar na aplicação rodando**

Editar o RDO criado na Task 4 Step 7 e conferir que o apontamento "Abraão / 11
pessoas" aparece e pode ser alterado e excluído.

- [ ] **Step 4: Commit**

```bash
git add templates/rdo/editar_rdo.html
git commit -m "feat(rdo): equipe de terceiro tambem na edicao do RDO"
```
