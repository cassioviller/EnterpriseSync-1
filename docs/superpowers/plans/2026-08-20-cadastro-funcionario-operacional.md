# Cadastro de Funcionário — Velocidade Operacional — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Deixar o cadastro de funcionário rápido o bastante para a Ana operá-lo todo dia: cadastrar com **só o nome**, ver o efetivo **em lista** (além dos cards), e **desativar vários de uma vez** por seleção.

**Architecture:** Três mudanças independentes na mesma tela. (1) `Funcionario.cpf` deixa de ser `NOT NULL` — o `UNIQUE` fica, porque o Postgres aceita múltiplos NULL num índice único, então não há migração de constraint, só o `DROP NOT NULL`. (2) `templates/funcionarios.html` ganha uma visão de tabela ao lado da de cards, alternável por botão e lembrada em `localStorage` — as duas opções, como o Paulo pediu. (3) Uma rota nova `POST /api/funcionarios/toggle-ativo-lote` faz o que hoje exige três cliques por pessoa.

**Tech Stack:** Python 3, Flask, SQLAlchemy, PostgreSQL, Jinja2, Bootstrap 5, vanilla JS, pytest.

**Spec:** Não há spec escrito. Este plano nasce da sessão de brainstorming de 2026-08-20.


## Estado — 2026-08-21

Tasks 1 (CPF opcional, migration 313) e 2 (ativar/desativar em lote)
**executadas e mescladas no `main`** — resgatadas da branch
`sdd/reuniao-20-08`, que ficou fora do merge do dia 20. A Task 3 (visão em
lista com seleção múltipla) **não foi começada**.

## Global Constraints

- Migrations em `migrations.py`: função `_migration_NNN_slug()` + entrada na lista `migrations_to_run` (~linha 6939). **O último número usado é 311.** Se o plano `2026-08-20-rdo-efetivo-terceiros.md` já tiver rodado, ele consumiu o 312 — confirme com `grep -n "^            (31" migrations.py` antes de escolher o número e use o próximo livre. Este plano assume **313**.
- Migration idempotente e que **levanta** em falha.
- Toda query filtra por `admin_id`.
- Bootstrap 5 + vanilla JS. Ícones Font Awesome.
- Testes em `tests/`, `pytestmark = pytest.mark.integration`. Rodar: `python -m pytest tests/<arquivo>.py -v`
- Commits em português: `feat(funcionarios):`, `test(funcionarios):`.

## Decisões tomadas na reunião (não reabrir)

- **A confirmação de desativação continua existindo.** O Paulo defendeu explicitamente o segundo clique ("é para não tirar um funcionário do nada sem querer"). O ganho vem da seleção múltipla: **uma** confirmação para N funcionários, não N confirmações.
- **CPF fica opcional, não sai do cadastro.** "CPF, por enquanto, não" — é velocidade, não remoção do campo.
- **Foto continua.** É o que alimenta o ponto facial. O que muda é ter também uma visão em linha.
- **PIX já existe** (`Funcionario.chave_pix`, `models.py:318`) e já aparece no card. Nada a fazer.

---

## File Structure

| Arquivo | Responsabilidade |
|---|---|
| `models.py` (modificar, `Funcionario.cpf`, linha 297) | `nullable=True`. |
| `migrations.py` (modificar) | Migration 313: `DROP NOT NULL` em `funcionario.cpf`. |
| `views/employees.py` (modificar, `funcionarios()` linhas ~62-95) | Aceitar POST sem CPF. |
| `views/api.py` (modificar, depois de `toggle_funcionario_ativo` linha 616) | Rota nova de ativação/desativação em lote. |
| `templates/funcionarios.html` (modificar) | Alternador cards/lista, tabela com checkbox, barra de ação em lote. |
| `tests/test_funcionario_cadastro_rapido.py` (criar) | CPF opcional e lote. |

---

### Task 1: CPF opcional

Hoje `views/employees.py:88` recusa o cadastro sem CPF, e a coluna é
`NOT NULL`. A Ana não sabe o CPF do Luiz na hora em que ele chega na obra.

O `UNIQUE` global da coluna **não** precisa mudar: no Postgres um índice único
aceita quantos NULL quiser. O que muda é o `NOT NULL` e a checagem de
duplicidade na view, que com `cpf=None` casaria com qualquer outro sem CPF.

**Files:**
- Modify: `models.py:297`
- Modify: `migrations.py` (nova função + entrada na lista)
- Modify: `views/employees.py:62-95`
- Test: `tests/test_funcionario_cadastro_rapido.py`

**Interfaces:**
- Produces: `Funcionario.cpf: str | None`. Consumido por qualquer código que leia CPF — ver Step 6.

- [x] **Step 1: Escrever o teste que falha**

Criar `tests/test_funcionario_cadastro_rapido.py`:

```python
"""Cadastro rápido de funcionário — reunião de 2026-08-20.

A Ana cadastra e remove gente toda semana ("Fabrício entrou, ficou dois
dias e já saiu"). Exigir CPF na hora do cadastro trava o fluxo: ela não
sabe o CPF de quem acabou de chegar na obra.
"""
import os
import sys
from datetime import date

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import main  # noqa: F401 — registra os blueprints
from app import app, db
from models import Funcionario
from test_cronograma_endpoints_m05 import _client_como
from test_cronograma_versao_service import _ambiente

pytestmark = pytest.mark.integration


@pytest.fixture(autouse=True)
def _config():
    app.config['TESTING'] = True
    app.config['WTF_CSRF_ENABLED'] = False
    if not app.secret_key:
        app.secret_key = 'test-cadastro-rapido'
    yield


def test_funcionario_pode_nascer_sem_cpf():
    with app.app_context():
        admin, _obra = _ambiente()
        f = Funcionario(codigo=f'RA{admin.id}', nome='Luiz Ajudante',
                        cpf=None, data_admissao=date(2026, 8, 20),
                        admin_id=admin.id, ativo=True)
        db.session.add(f)
        db.session.commit()
        assert f.id is not None
        assert f.cpf is None


def test_dois_funcionarios_sem_cpf_convivem():
    """O UNIQUE da coluna aceita múltiplos NULL no Postgres — se este
    teste quebrar, o índice precisa virar parcial (WHERE cpf IS NOT NULL)."""
    with app.app_context():
        admin, _obra = _ambiente()
        db.session.add(Funcionario(
            codigo=f'R1{admin.id}', nome='Luiz', cpf=None,
            data_admissao=date(2026, 8, 20), admin_id=admin.id, ativo=True))
        db.session.add(Funcionario(
            codigo=f'R2{admin.id}', nome='Fabrício', cpf=None,
            data_admissao=date(2026, 8, 20), admin_id=admin.id, ativo=True))
        db.session.commit()
        assert Funcionario.query.filter_by(
            admin_id=admin.id, cpf=None).count() == 2
```

- [x] **Step 2: Rodar para confirmar que falha**

Run: `python -m pytest tests/test_funcionario_cadastro_rapido.py -v`

Esperado: **FAIL** — `IntegrityError: null value in column "cpf" violates not-null constraint`.

- [x] **Step 3: Tornar a coluna nullable no modelo**

Em `models.py`, na `class Funcionario`, trocar:

```python
    cpf = db.Column(db.String(14), unique=True, nullable=False)
```

por:

```python
    # Reunião 2026-08-20 — CPF deixou de ser obrigatório: a Ana cadastra
    # quem chegou na obra hoje e não sabe o CPF. O UNIQUE fica: no Postgres
    # um índice único aceita quantos NULL quiser, então não há colisão entre
    # cadastros rápidos, e o dia em que o CPF for preenchido a unicidade
    # volta a valer sozinha.
    cpf = db.Column(db.String(14), unique=True, nullable=True)
```

- [x] **Step 4: Escrever a migration 313**

Em `migrations.py`, imediatamente antes de `def executar_migracoes():`, inserir:

```python
def _migration_313_funcionario_cpf_nullable():
    """`funcionario.cpf` deixa de ser NOT NULL.

    Reunião 2026-08-20: a Ana cadastra funcionário no dia em que ele aparece
    na obra e o CPF chega depois. Exigir CPF fazia o cadastro esperar pelo
    documento — e o RDO daquele dia saía sem a pessoa.

    O UNIQUE **não** é tocado: no Postgres um índice único aceita múltiplos
    NULL, então N cadastros sem CPF convivem, e a unicidade volta a valer
    assim que o número for preenchido. Trocar por índice parcial seria
    equivalente e mais arriscado (drop + create numa tabela em uso).

    Sem backfill: NULL aqui significa "ainda não informado", que é
    exatamente o estado novo — nenhuma linha histórica precisa mudar.

    Idempotente: DROP NOT NULL num coluna já nullable é no-op no Postgres.
    """
    from sqlalchemy import text as sa_text
    logger.info("[Migration 313] Iniciando — funcionario.cpf DROP NOT NULL")
    with db.engine.begin() as conn:
        conn.execute(sa_text(
            "ALTER TABLE funcionario ALTER COLUMN cpf DROP NOT NULL"))
    logger.info("[Migration 313] Concluída com sucesso")
```

- [x] **Step 5: Registrar a migration na lista**

Em `migrations.py`, na lista `migrations_to_run`, ao final, acrescentar:

```python
            (313, "Reuniao 2026-08-20 — funcionario.cpf DROP NOT NULL: cadastro rapido sem documento em maos. UNIQUE mantido (Postgres aceita N nulos)", _migration_313_funcionario_cpf_nullable),
```

- [x] **Step 6: Rodar os testes**

Run: `python -m pytest tests/test_funcionario_cadastro_rapido.py -v`

Esperado: **os 2 PASSAM.**

Se `test_dois_funcionarios_sem_cpf_convivem` falhar com `IntegrityError`, o
banco tem um índice único que trata NULL como valor (não é o comportamento
padrão do Postgres) — nesse caso troque a migration por
`DROP CONSTRAINT` + `CREATE UNIQUE INDEX ... WHERE cpf IS NOT NULL` e refaça
o Step 4. Registre a troca no commit.

- [x] **Step 7: Aceitar o POST sem CPF na view**

Em `views/employees.py`, dentro de `funcionarios()`, trocar:

```python
            if not nome or not cpf:
                flash('[ERROR] Nome e CPF são obrigatórios!', 'error')
                return redirect(url_for('main.funcionarios'))
            
            # Verificar se CPF já existe
            funcionario_existente = Funcionario.query.filter_by(cpf=cpf).first()
            if funcionario_existente:
                flash(f'[ERROR] CPF {cpf} já está cadastrado para {funcionario_existente.nome}!', 'error')
                return redirect(url_for('main.funcionarios'))
```

por:

```python
            if not nome:
                flash('[ERROR] Nome é obrigatório!', 'error')
                return redirect(url_for('main.funcionarios'))

            # Reunião 2026-08-20 — CPF é opcional. String vazia vira None:
            # gravar '' faria o UNIQUE colidir no segundo cadastro rápido,
            # que é justamente o caso de uso (dois ajudantes no mesmo dia).
            cpf = cpf or None

            # A checagem de duplicidade só faz sentido com CPF informado —
            # `filter_by(cpf=None)` casaria com qualquer cadastro rápido
            # anterior e recusaria o segundo.
            if cpf:
                funcionario_existente = Funcionario.query.filter_by(cpf=cpf).first()
                if funcionario_existente:
                    flash(f'[ERROR] CPF {cpf} já está cadastrado para {funcionario_existente.nome}!', 'error')
                    return redirect(url_for('main.funcionarios'))
```

- [x] **Step 8: Tirar o `required` do CPF no formulário**

Run: `grep -n 'name="cpf"' templates/funcionarios.html`

Na linha encontrada, remover o atributo `required` (se houver) e trocar o label
`CPF *` por `CPF` — o asterisco é a promessa de obrigatoriedade na tela.

- [x] **Step 9: Procurar leituras de CPF que quebram com None**

Run: `grep -rn "\.cpf" --include=*.py . | grep -v tests/ | grep -v migrations.py`

Para cada uso que formate ou fatie o CPF (`.replace`, `[:3]`, `len(`), conferir
que tolera `None`. Corrigir com `(f.cpf or '')`. **Não** refatorar nada além
disso — o escopo é não quebrar, não limpar.

- [x] **Step 10: Commit**

```bash
git add models.py migrations.py views/employees.py templates/funcionarios.html tests/test_funcionario_cadastro_rapido.py
git commit -m "feat(funcionarios): CPF opcional no cadastro rapido"
```

---

### Task 2: Ativar/desativar em lote

Hoje são três cliques por pessoa (`toggleStatusFuncionario` → `confirm` →
reload). Para os oito e tantos que a Ana precisa desligar de uma vez, isso é
o que o Paulo chamou de "uma porrada de cara pra ficar desativando".

**Files:**
- Modify: `views/api.py` (rota nova, logo depois de `toggle_funcionario_ativo`, que termina na linha ~655)
- Test: `tests/test_funcionario_cadastro_rapido.py`

**Interfaces:**
- Consumes: `models.Funcionario`, `get_tenant_admin_id()` (ambos já importados em `views/api.py`).
- Produces: `POST /api/funcionarios/toggle-ativo-lote`, body `{'ids': [int], 'ativo': bool}` → `200 {'success': True, 'alterados': N, 'message': str}`; `400` com `{'success': False, 'message': ...}` se `ids` vier vazio; `403` sem tenant. Ids fora do tenant são **ignorados em silêncio** e não contam em `alterados`. Consumido pela Task 3 (front).

- [x] **Step 1: Escrever o teste que falha**

Acrescentar em `tests/test_funcionario_cadastro_rapido.py`:

```python
def _tres_funcionarios():
    with app.app_context():
        admin, _obra = _ambiente()
        ids = []
        for i, nome in enumerate(('Davi', 'Cristiano', 'Fabrício')):
            f = Funcionario(codigo=f'L{i}{admin.id}', nome=nome, cpf=None,
                            data_admissao=date(2026, 8, 20),
                            admin_id=admin.id, ativo=True)
            db.session.add(f)
            db.session.flush()
            ids.append(f.id)
        db.session.commit()
        # `_client_como` recebe o ID; e o objeto ORM devolvido de dentro do
        # contexto já está destacado quando ele fecha.
        return admin.id, ids


def test_desativar_em_lote():
    admin_id, ids = _tres_funcionarios()
    client = _client_como(admin_id)

    resp = client.post('/api/funcionarios/toggle-ativo-lote',
                       json={'ids': ids[:2], 'ativo': False})

    assert resp.status_code == 200, resp.get_data(as_text=True)
    assert resp.get_json()['alterados'] == 2
    with app.app_context():
        assert Funcionario.query.get(ids[0]).ativo is False
        assert Funcionario.query.get(ids[1]).ativo is False
        assert Funcionario.query.get(ids[2]).ativo is True


def test_reativar_em_lote():
    admin_id, ids = _tres_funcionarios()
    client = _client_como(admin_id)
    client.post('/api/funcionarios/toggle-ativo-lote',
                json={'ids': ids, 'ativo': False})

    resp = client.post('/api/funcionarios/toggle-ativo-lote',
                       json={'ids': ids, 'ativo': True})

    assert resp.get_json()['alterados'] == 3
    with app.app_context():
        assert all(Funcionario.query.get(i).ativo for i in ids)


def test_lote_ignora_id_de_outro_tenant():
    """Silencioso de propósito: responder 404 diria a um tenant que o id
    existe em outro."""
    admin_a_id, ids_a = _tres_funcionarios()
    _admin_b_id, ids_b = _tres_funcionarios()
    client = _client_como(admin_a_id)

    resp = client.post('/api/funcionarios/toggle-ativo-lote',
                       json={'ids': [ids_a[0], ids_b[0]], 'ativo': False})

    assert resp.get_json()['alterados'] == 1
    with app.app_context():
        assert Funcionario.query.get(ids_b[0]).ativo is True


def test_lote_vazio_recusa():
    admin_id, _ids = _tres_funcionarios()
    client = _client_como(admin_id)

    resp = client.post('/api/funcionarios/toggle-ativo-lote',
                       json={'ids': [], 'ativo': False})

    assert resp.status_code == 400
    assert resp.get_json()['success'] is False
```

- [x] **Step 2: Rodar para confirmar que falha**

Run: `python -m pytest tests/test_funcionario_cadastro_rapido.py -k lote -v`

Esperado: **FAIL** — 404, a rota não existe.

- [x] **Step 3: Implementar a rota**

Em `views/api.py`, logo depois do fim de `toggle_funcionario_ativo` (antes de
`@main_bp.route('/api/ponto/lancamento-finais-semana'...)`), inserir:

```python
@main_bp.route('/api/funcionarios/toggle-ativo-lote', methods=['POST'])
@login_required
def toggle_funcionarios_ativo_lote(): 
    """Ativa ou desativa vários funcionários numa transação.

    Reunião 2026-08-20: desligar oito pessoas custava três cliques cada.
    A confirmação continua existindo — o Paulo defendeu o segundo clique
    para ninguém sair do efetivo sem querer —, mas agora é UMA confirmação
    para o lote inteiro, não uma por pessoa.

    Id fora do tenant é ignorado em silêncio, não 404: responder que o id
    "não existe aqui" já contaria que ele existe em algum lugar.
    """
    try:
        admin_id = get_tenant_admin_id()
        if not admin_id:
            return jsonify({'success': False, 'message': 'Admin não identificado'}), 403

        data = request.get_json(silent=True) or {}
        ids = data.get('ids') or []
        if not isinstance(ids, list) or not ids:
            return jsonify({'success': False,
                            'message': 'Selecione ao menos um funcionário'}), 400
        try:
            ids = [int(i) for i in ids]
        except (TypeError, ValueError):
            return jsonify({'success': False,
                            'message': 'Lista de ids inválida'}), 400

        ativo = bool(data.get('ativo', False))

        funcionarios = Funcionario.query.filter(
            Funcionario.id.in_(ids),
            Funcionario.admin_id == admin_id,
        ).all()

        hoje = datetime.now().date()
        alterados = 0
        for f in funcionarios:
            if f.ativo == ativo:
                continue
            f.ativo = ativo
            if hasattr(f, 'data_desativacao'):
                f.data_desativacao = None if ativo else hoje
            alterados += 1

        db.session.commit()

        verbo = 'ativado' if ativo else 'desativado'
        plural = 's' if alterados != 1 else ''
        logger.info(f"[OK] {alterados} funcionário(s) {verbo}(s) em lote "
                    f"(tenant {admin_id})")
        return jsonify({
            'success': True,
            'alterados': alterados,
            'message': f'{alterados} funcionário{plural} {verbo}{plural}',
        })

    except Exception as e:
        db.session.rollback()
        logger.error(f"[ERROR] Erro no toggle em lote de funcionários: {e}")
        return jsonify({'success': False, 'message': str(e)}), 500
```

- [x] **Step 4: Rodar os testes**

Run: `python -m pytest tests/test_funcionario_cadastro_rapido.py -v`

Esperado: **os 6 PASSAM.**

- [x] **Step 5: Commit**

```bash
git add views/api.py tests/test_funcionario_cadastro_rapido.py
git commit -m "feat(funcionarios): ativar e desativar em lote"
```

---

### Task 3: Visão em lista com seleção múltipla

O Paulo: "eu prefiro layout em linhas... para mim saber o meu efetivo eu tenho
que ver tudo isso aqui". E logo depois aceitou as duas opções: "deixa no formato
de lista ou nesse formato, mas dá as duas opções". A preferência fica em
`localStorage` porque quem usa a tela é a Ana, e ela não deve reescolher a cada
visita.

**Files:**
- Modify: `templates/funcionarios.html`
- Test: verificação manual (é template; a regra de negócio está coberta pela Task 2)

**Interfaces:**
- Consumes: `POST /api/funcionarios/toggle-ativo-lote` (Task 2); `funcionarios_kpis` (lista de dicts com `.funcionario` e `.modo_remuneracao`), `obter_foto_funcionario(funcionario)` — ambos já disponíveis no contexto do template.
- Produces: nada.

- [ ] **Step 1: Acrescentar o alternador de visão**

Em `templates/funcionarios.html`, imediatamente antes do comentário
`<!-- Grid de Cards de Funcionários - SEPARAÇÃO ATIVO/INATIVO -->` (linha ~543),
inserir:

```html
<!-- Alternador de visão (reunião 2026-08-20) — cards para consultar uma
     pessoa, lista para bater o efetivo inteiro de relance, como na planilha. -->
<div class="d-flex justify-content-between align-items-center mb-3">
  <div class="btn-group btn-group-sm" role="group" aria-label="Formato da lista">
    <button type="button" class="btn btn-outline-secondary" id="btnVisaoLista"
            onclick="definirVisaoFuncionarios('lista')">
      <i class="fas fa-list me-1"></i> Lista
    </button>
    <button type="button" class="btn btn-outline-secondary" id="btnVisaoCards"
            onclick="definirVisaoFuncionarios('cards')">
      <i class="fas fa-th-large me-1"></i> Cards
    </button>
  </div>
  <div id="barraAcaoLote" class="d-none align-items-center gap-2">
    <span class="text-muted small" id="loteContador">0 selecionados</span>
    <button type="button" class="btn btn-sm btn-outline-danger"
            onclick="toggleLoteFuncionarios(false)">
      <i class="fas fa-user-times me-1"></i> Desativar selecionados
    </button>
    <button type="button" class="btn btn-sm btn-outline-success"
            onclick="toggleLoteFuncionarios(true)">
      <i class="fas fa-user-check me-1"></i> Reativar selecionados
    </button>
  </div>
</div>
```

- [ ] **Step 2: Acrescentar a tabela**

Logo depois do bloco do Step 1, inserir:

```html
<div id="visaoListaFuncionarios" class="d-none">
  <div class="table-responsive">
    <table class="table table-sm table-hover align-middle">
      <thead class="table-light">
        <tr>
          <th style="width:36px">
            <input class="form-check-input" type="checkbox" id="chkTodosFuncionarios"
                   onchange="marcarTodosFuncionarios(this.checked)"
                   title="Selecionar todos">
          </th>
          <th>Nome</th>
          <th>Função</th>
          <th>Telefone</th>
          <th class="text-end">Remuneração</th>
          <th>Status</th>
          <th style="width:110px"></th>
        </tr>
      </thead>
      <tbody>
        {% for kpi in funcionarios_kpis %}
        <tr class="funcionario-linha"
            data-nome="{{ kpi.funcionario.nome.lower() }}"
            data-funcao="{{ kpi.funcionario.funcao_ref.nome.lower() if kpi.funcionario.funcao_ref else '' }}"
            data-status="{{ 'ativo' if kpi.funcionario.ativo else 'inativo' }}">
          <td>
            <input class="form-check-input chk-funcionario" type="checkbox"
                   value="{{ kpi.funcionario.id }}"
                   onchange="atualizarContadorLote()">
          </td>
          <td class="{{ '' if kpi.funcionario.ativo else 'text-muted' }}">
            {{ kpi.funcionario.nome }}
          </td>
          <td>{{ kpi.funcionario.funcao_ref.nome if kpi.funcionario.funcao_ref else '-' }}</td>
          <td>{{ kpi.funcionario.telefone or '-' }}</td>
          <td class="text-end">
            {% if kpi.modo_remuneracao == 'diaria' %}
              R$ {{ '{:,.2f}'.format(kpi.funcionario.valor_diaria or 0) }} / dia
            {% else %}
              R$ {{ '{:,.2f}'.format(kpi.funcionario.salario or 0) }} / mês
            {% endif %}
          </td>
          <td>
            {% if kpi.funcionario.ativo %}
              <span class="badge bg-success">Ativo</span>
            {% else %}
              <span class="badge bg-secondary">Inativo</span>
            {% endif %}
          </td>
          <td class="text-end">
            <a href="{{ url_for('main.funcionario_perfil', id=kpi.funcionario.id) }}"
               class="btn btn-sm btn-outline-primary" title="Ver perfil">
              <i class="fas fa-user"></i>
            </a>
          </td>
        </tr>
        {% endfor %}
      </tbody>
    </table>
  </div>
</div>
```

- [ ] **Step 3: Envolver os cards existentes num contêiner alternável**

Ainda em `templates/funcionarios.html`:

- Logo antes de `{% set funcionarios_ativos = ... %}` (linha ~545), abrir:
  ```html
  <div id="visaoCardsFuncionarios">
  ```
- Logo depois do `{% endif %}` que fecha a seção de **inativos** (procurar com
  `grep -n "funcionarios-inativos" templates/funcionarios.html` e ir até o
  `{% endif %}` correspondente), fechar:
  ```html
  </div>
  ```

Conferir com `grep -c "visaoCardsFuncionarios" templates/funcionarios.html` que
o resultado é `2` (abertura e nenhuma outra menção além do JS do Step 4, que
soma mais uma — então após o Step 4 o esperado passa a ser `3`).

- [ ] **Step 4: Acrescentar o JS**

No bloco `<script>` do fim do arquivo, logo antes de
`// Toggle status funcionário (ativar/desativar) - CORRIGIDO` (linha ~2143),
inserir:

```javascript
// ── Visão lista x cards (reunião 2026-08-20) ──────────────────────────
// A preferência é lembrada porque quem vive nesta tela é a Ana: reescolher
// o formato a cada visita é o tipo de atrito que faz voltar pro Excel.
const _VISAO_KEY = 'sige.funcionarios.visao';

function definirVisaoFuncionarios(visao) {
    const lista = document.getElementById('visaoListaFuncionarios');
    const cards = document.getElementById('visaoCardsFuncionarios');
    const barra = document.getElementById('barraAcaoLote');
    const btnL = document.getElementById('btnVisaoLista');
    const btnC = document.getElementById('btnVisaoCards');
    if (!lista || !cards) return;

    const ehLista = visao === 'lista';
    lista.classList.toggle('d-none', !ehLista);
    cards.classList.toggle('d-none', ehLista);
    btnL.classList.toggle('active', ehLista);
    btnC.classList.toggle('active', !ehLista);
    // A ação em lote só existe na lista — é lá que tem checkbox.
    barra.classList.toggle('d-none', !ehLista);
    barra.classList.toggle('d-flex', ehLista);

    try { localStorage.setItem(_VISAO_KEY, visao); } catch (e) { /* modo privado */ }
    if (ehLista) atualizarContadorLote();
}

function marcarTodosFuncionarios(marcar) {
    document.querySelectorAll('.chk-funcionario').forEach(c => {
        // Respeita o filtro de busca: linha escondida não entra na seleção.
        if (c.closest('tr').style.display !== 'none') c.checked = marcar;
    });
    atualizarContadorLote();
}

function _idsSelecionados() {
    return Array.from(document.querySelectorAll('.chk-funcionario:checked'))
        .map(c => parseInt(c.value, 10));
}

function atualizarContadorLote() {
    const n = _idsSelecionados().length;
    const el = document.getElementById('loteContador');
    if (el) el.textContent = `${n} selecionado${n === 1 ? '' : 's'}`;
}

function toggleLoteFuncionarios(ativo) {
    const ids = _idsSelecionados();
    if (!ids.length) {
        alert('Selecione ao menos um funcionário.');
        return;
    }
    const verbo = ativo ? 'reativar' : 'desativar';
    // UMA confirmação para o lote — o segundo clique continua existindo,
    // só deixou de ser um por pessoa.
    if (!confirm(`Tem certeza que deseja ${verbo} ${ids.length} funcionário(s)?`)) return;

    fetch('/api/funcionarios/toggle-ativo-lote', {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json',
            'X-CSRFToken': getCsrfToken()
        },
        body: JSON.stringify({ ids: ids, ativo: ativo })
    })
    .then(r => r.json())
    .then(data => {
        if (data.success) {
            alert(data.message);
            location.reload();
        } else {
            alert('Erro: ' + data.message);
        }
    })
    .catch(err => {
        console.error('Erro:', err);
        alert('Erro interno do servidor');
    });
}

document.addEventListener('DOMContentLoaded', function () {
    let salva = 'cards';
    try { salva = localStorage.getItem(_VISAO_KEY) || 'cards'; } catch (e) { /* modo privado */ }
    definirVisaoFuncionarios(salva);
});
```

- [ ] **Step 5: Fazer o filtro de busca alcançar as linhas**

O filtro atual varre `.funcionario-card` (linha ~1262). Localizar a função que
faz isso e, no mesmo laço, aplicar a mesma regra a `.funcionario-linha`:

Run: `grep -n "funcionario-card')" templates/funcionarios.html`

Na função encontrada, depois do laço existente sobre os cards, acrescentar:

```javascript
    // Mesmo filtro para a visão em lista.
    document.querySelectorAll('.funcionario-linha').forEach(function (linha) {
        const nome = linha.dataset.nome || '';
        const funcao = linha.dataset.funcao || '';
        const casa = !termo || nome.includes(termo) || funcao.includes(termo);
        linha.style.display = casa ? '' : 'none';
    });
    atualizarContadorLote();
```

Ajustar o nome da variável do termo de busca (`termo`) para o que a função já
usa — não renomear a variável existente.

- [ ] **Step 6: Verificar na aplicação rodando**

Em `/funcionarios`:
1. Alternar Lista / Cards; recarregar a página e confirmar que voltou no formato escolhido.
2. Na lista: marcar dois, conferir o contador, clicar "Desativar selecionados", confirmar **uma** vez, e ver os dois virarem Inativo.
3. Marcar os mesmos dois e reativar.
4. Digitar no campo de busca e conferir que as linhas filtram junto com os cards.
5. "Selecionar todos" com busca ativa deve marcar só o que está visível.

- [ ] **Step 7: Commit**

```bash
git add templates/funcionarios.html
git commit -m "feat(funcionarios): visao em lista com selecao multipla e acao em lote"
```
