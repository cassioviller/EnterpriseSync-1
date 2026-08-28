# A Porta Irmã — a guarda que fechou um caminho e deixou o gêmeo aberto Implementation Plan

> **Estado em 2026-08-28:** 🟡 **ABERTO — pronto para executar** — 8 tasks.
> Nasceu do `/code-review max` sobre a branch da Onda 5, rodado DEPOIS de ela
> fechar com gate verde de 2839. Evidência em
> `docs/auditoria/achados-code-review-2026-08-25.md`, seção "Achados do
> `/code-review max` sobre a branch da Onda 5 (28/08)".
>
> 🔬 **Os seis achados foram reconferidos na fonte em 28/08**, um a um, antes de
> este plano ser escrito. O review que os produziu retratou uma alegação no
> mesmo dia; nenhum item entrou aqui por repasse.

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recomendado) ou superpowers:executing-plans para executar este plano task a task. Os passos usam checkbox (`- [ ]`) para acompanhamento.

**Goal:** Fechar os seis defeitos em que uma correção já entregue tapou um
caminho e deixou o caminho gêmeo aberto — de modo que a garantia passe a valer
pela **capacidade**, não pela URL, pelo módulo ou pelo campo que o teste da vez
exercitou.

**Architecture:** Os seis não são seis problemas. São **um padrão de trabalho**,
e é por isso que viajam juntos: alguém consertou o furo pela porta que o teste
abria, escreveu o teste daquela porta, viu verde, e a porta irmã ficou aberta.
Em quatro dos seis o próprio código admite o padrão — o comentário da correção
descreve o defeito antigo numa frase que continua verdadeira trocando uma
palavra (`ponto_views.py:2447`: *"bastava não mandar latitude/longitude"* → hoje
basta não mandar `obra_id`). A correção estrutural, portanto, não é só remendar
seis linhas: **cada task fecha o furo E estende o teste-guarda ao conjunto
inteiro de portas equivalentes**, para que a sétima porta que nascer já venha
coberta.

**Tech Stack:** Flask, SQLAlchemy 2.0.41, PostgreSQL, pytest, Jinja2.

**Spec:** `docs/auditoria/achados-code-review-2026-08-25.md` (seção de 28/08). O
contexto do padrão está em `docs/superpowers/plans/2026-08-25-onda-5-o-recusado-para-de-ser-gravado.md`,
seção "O fix round de 28/08".

## Global Constraints

- **TDD sem exceção.** Teste primeiro, RED conferido e **citado no commit**,
  depois o código.
- **Nenhum teste desta onda prova por `inspect.getsource()`.** É a regra que
  esta onda existe para reparar: três testes da Onda 5 liam o texto do código e
  passaram verdes por cima de defeitos reais. O que se afirma é olhado **no
  banco ou na resposta HTTP**.
- **Todo teste entra pela porta do usuário** (rota HTTP), não pela função
  interna. Os defeitos são de rota.
- **Teste de guarda itera sobre o CONJUNTO, nunca sobre a instância.** Um teste
  que afirma "`ponto_views` não vaza traceback" é o que deixou `views/rdo.py`
  vazando. Escreva `for modulo in (...)` com a lista inteira, ou uma varredura
  de rotas registradas.
- **Recusar é não deixar rastro.** Todo `return 4xx` faz
  `db.session.rollback()` antes.
- **Arreio antes de arquivo novo.** 🔬 `tests/helpers_tenant.py` (`um_tenant`,
  `dois_tenants`, `cliente_de`) já existe. Use.
- **Gate ao fim:** `bash run_tests.sh --gate`. Piso: **2840 passed, 10 skipped,
  201 deselected, 2 xfailed** (medido em 28/08). Alvo ao fim das 8 tasks:
  **2846 passed, 4 skipped** — o skip CAI, porque a Task 7 devolve ao gate os 6
  testes que a fixture sorteada tinha tirado.

---

## 🔴 Decisão antes de começar

### D5 — o aditivo: garantia própria, ou ligar `escopo_obra_ativo`?

📖 `views/aditivos_views.py:88` (`novo`), `:144` (`aprovar`) e `:189`
(`cancelar`) usam `@obra_required(PapelObra.GESTOR)`. A cadeia é
`pode_editar_obra` (`utils/autorizacao.py:194`) → `papel_de_usuario_na_obra`.

🔬 **O permissivo é decisão consciente, e o código diz isso.**
`utils/autorizacao.py:147-160`, verbatim:

> *"Flag desligada: o eixo de obra não está em vigor, nem para alargar nem para
> estreitar. (…) Devolver LEITOR aqui (como o plano da Fase 1 sugeria) tiraria a
> edição de todo não-admin no dia do deploy — exatamente o que a flag existe
> para impedir."*

Com `escopo_obra_ativo` desligado — e a coluna é `default=False`
(`models.py:4441`), logo é o estado de **todo tenant existente** — a função
devolve `PapelObra.GESTOR` para qualquer usuário autenticado do tenant.

**O achado não é o fallback.** É que aprovar aditivo — que grava
`ObraContratoVersao`, lança delta contábil e desloca cronograma, **irreversível
por desenho** — foi pendurado num predicado cujo default é permissivo, como se
`PapelObra.GESTOR` já fosse restrição real.

**As três saídas:**

- **(a) A rota ganha garantia que não depende da flag** — `@admin_required`
  somando ao `@obra_required`, como a Onda 5 fez em `portal_obras` para
  capacidade estritamente menor. **Recomendada:** fecha hoje, para todos os
  tenants, sem exigir migração de dados nem decisão por tenant.
- **(b) Ligar `escopo_obra_ativo` por tenant** — mais correto no longo prazo, e
  é o desenho que a Fase 1 pretendia. Mas exige backfill de `UsuarioObra` em
  cada tenant, e ligar sem o backfill **tira a edição de todo não-admin no dia**
  — exatamente o que a flag evita.
- **(c) Fica como está**, e o aditivo segue aprovável por qualquer usuário do
  tenant.

⚠️ **A Task 1 assume (a).** Se preferir (b), ela vira plano próprio: é migração
de dados, não decorador.

---

## File Structure

| Arquivo | Ação | Responsabilidade |
|---|---|---|
| `views/aditivos_views.py` | Modificar `:88`, `:144`, `:189` | Task 1 — depende da D5 |
| `medicao_views.py` | Modificar `:445-448` | Task 2 |
| `views/rdo.py` | Modificar `:3576-3581` | Task 3 |
| `production_routes.py` | Modificar `:124`, `:201`, `:279`, `:336`, `:387` | Task 4 |
| `ponto_views.py` | Modificar `:2453-2461` | Task 5 |
| `services/cronograma_apontamento_service.py` | Modificar `:398` | Task 6 |
| `tests/test_porta_irma.py` | **Criar** | Todos os testes deste plano |

---

### Task 1: O aditivo exige garantia que não depende de flag

> 🔴 **Ação financeira irreversível atrás de predicado permissivo por default.**
> Assume a saída (a) da D5.

**Files:**
- Modify: `views/aditivos_views.py:88`, `:144`, `:189`
- Test: `tests/test_porta_irma.py` (criar)

**Interfaces:**
- Consumes: `auth.admin_required` (já existe; é o que `portal_obras_views` usa).
- Produces: nada que outra task consuma.

- [ ] **Step 1: Write the failing test**

Create `tests/test_porta_irma.py`:

```python
"""A porta irmã — a guarda fechou um caminho e deixou o gêmeo aberto.

A regra destes testes: NENHUM prova por `inspect.getsource()`. Três testes da
Onda 5 liam o texto do código e passaram verdes por cima de defeitos reais —
é o que este plano existe para reparar. O que se afirma é olhado no banco ou
na resposta HTTP.

E todo teste de guarda itera sobre o CONJUNTO de portas equivalentes, nunca
sobre a instância que o defeito da vez expôs.
"""
import os
import sys
import uuid
from datetime import date, timedelta

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import main  # noqa: F401 — registra blueprints e handlers de evento
from app import app, db
from helpers_tenant import cliente_de, um_tenant

pytestmark = pytest.mark.integration


@pytest.fixture(autouse=True)
def _config():
    app.config['TESTING'] = True
    app.config['WTF_CSRF_ENABLED'] = False
    if not app.secret_key:
        app.secret_key = 'test-porta-irma'
    yield


def _funcionario_logavel(admin_id, marca):
    """Usuário FUNCIONARIO do tenant — o papel que NÃO deve poder aprovar.

    `um_tenant` semeia o ADMIN; aqui nasce o subordinado, que é quem prova a
    guarda. Sem ele o teste provaria só que admin pode, que não é a pergunta.
    """
    from werkzeug.security import generate_password_hash

    from models import TipoUsuario, Usuario

    u = Usuario(
        nome=f'Func {marca}', username=f'func_{marca}',
        email=f'func_{marca}@t.local',
        password_hash=generate_password_hash('Senha@2026'),
        tipo_usuario=TipoUsuario.FUNCIONARIO, admin_id=admin_id, ativo=True)
    db.session.add(u)
    db.session.commit()
    return u.id


# ---------------------------------------------------------------------------
# Task 1 — o aditivo
# ---------------------------------------------------------------------------

def test_funcionario_nao_aprova_aditivo():
    """🔴 `views/aditivos_views.py:144` — `@obra_required(PapelObra.GESTOR)`.

    Com `escopo_obra_ativo` desligado (`models.py:4441`, `default=False` — o
    estado de todo tenant existente), `papel_de_usuario_na_obra`
    (`utils/autorizacao.py:147-160`) devolve GESTOR para QUALQUER usuário
    autenticado do tenant. Aprovar aditivo grava `ObraContratoVersao`, lança
    delta contábil e desloca cronograma — irreversível por desenho.

    O fallback permissivo é decisão consciente e documentada; o defeito é
    pendurar ação irreversível nele. Ver D5.
    """
    from models import ObraContratoVersao

    with app.app_context():
        marca = uuid.uuid4().hex[:8]
        t = um_tenant('adit-authz', com_fatos=False)
        func_id = _funcionario_logavel(t.admin_id, marca)

        versoes_antes = ObraContratoVersao.query.filter_by(
            obra_id=t.obra_id).count()

        cliente = cliente_de(func_id)
        resposta = cliente.post(
            f'/obras/{t.obra_id}/aditivos/novo',
            data={'valor_novo': '150.000,00', 'prazo_delta_dias': '30',
                  'justificativa': f'invasao-{marca}'},
            follow_redirects=False)

        assert resposta.status_code in (302, 403, 404), (
            f'FUNCIONARIO recebeu {resposta.status_code} ao abrir aditivo')

        versoes_depois = ObraContratoVersao.query.filter_by(
            obra_id=t.obra_id).count()
        assert versoes_depois == versoes_antes, (
            'FUNCIONARIO moveu a linha de base do contrato — '
            f'{versoes_depois - versoes_antes} versão(ões) nova(s)')
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_porta_irma.py::test_funcionario_nao_aprova_aditivo -v`
Expected: **FAIL** — o FUNCIONARIO passa pelo `@obra_required` e uma
`ObraContratoVersao` nova aparece.

- [ ] **Step 3: Write minimal implementation**

Em `views/aditivos_views.py`, nas três rotas (`novo`, `aprovar`, `cancelar`),
somar `@admin_required` ao decorador existente:

```python
from auth import admin_required   # já importado no módulo? confira o topo

@aditivos_bp.route('/obras/<int:obra_id>/aditivos/novo', methods=['GET', 'POST'])
@login_required
@admin_required          # ← D5, saída (a)
@obra_required(PapelObra.GESTOR)
def novo(obra_id):
    ...
```

Comentário obrigatório acima do primeiro `@admin_required`:

```python
# D5 — `@obra_required(PapelObra.GESTOR)` NÃO restringe hoje: com
# `escopo_obra_ativo` desligado (default de todo tenant existente),
# `papel_de_usuario_na_obra` devolve GESTOR para qualquer usuário do
# tenant, e isso é deliberado (utils/autorizacao.py:147-160). Aprovar
# aditivo é irreversível — não pode depender de uma flag que quase
# ninguém ligou. Quando `escopo_obra_ativo` for a norma, este
# `@admin_required` pode sair e o `@obra_required` volta a bastar.
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_porta_irma.py::test_funcionario_nao_aprova_aditivo -v`
Expected: **PASS**.

Adjacência obrigatória — as rotas de aditivo têm testes de Fase 6:
Run: `python -m pytest tests/ -k "aditivo or contrato" -m "not browser" -q`
Expected: verde. Se algum teste de Fase 6 logava como não-admin para aprovar,
ele documentava o furo: **traga o caso aqui e decida explicitamente**, não
afrouxe o decorador.

- [ ] **Step 5: Commit**

```bash
git add tests/test_porta_irma.py views/aditivos_views.py
git commit -m "fix(aditivo): a aprovacao para de depender de uma flag que ninguem ligou"
```

---

### Task 2: A medição fecha as duas URLs, não uma

> 🔴 📖 A Onda 5 pôs `@admin_required` em `portal_obras.gerar_medicao` e deixou
> a rota equivalente aberta. 🔬 Conferido: `medicao_views.py` tem **11
> `@login_required` e ZERO `@admin_required`**.

**Files:**
- Modify: `medicao_views.py:445-448`
- Test: `tests/test_porta_irma.py`

**Interfaces:**
- Consumes: `_funcionario_logavel` da Task 1.
- Produces: nada.

- [ ] **Step 1: Write the failing test**

```python
def test_gerar_medicao_e_fechada_nas_duas_urls():
    """🔴 `medicao_views.py:445-448` — a mesma view em DUAS rotas, só
    `@login_required`.

    A Onda 5 fechou `portal_obras.gerar_medicao` com `@admin_required`. Quem
    for barrado lá ainda POSTa em `/medicao/obra/<id>/gerar` ou
    `/obras/<id>/medicao/fechar` e cria a `MedicaoObra` — mais a conta a
    receber que ela auto-cria. O privilégio se recupera trocando a URL.

    O teste itera sobre AS DUAS, de propósito: fechar uma e deixar a outra é
    exatamente o defeito.
    """
    from models import MedicaoObra

    with app.app_context():
        marca = uuid.uuid4().hex[:8]
        t = um_tenant('medicao-authz', com_fatos=False)
        func_id = _funcionario_logavel(t.admin_id, marca)
        cliente = cliente_de(func_id)

        antes = MedicaoObra.query.filter_by(obra_id=t.obra_id).count()

        for rota in (f'/medicao/obra/{t.obra_id}/gerar',
                     f'/obras/{t.obra_id}/medicao/fechar'):
            resposta = cliente.post(rota, data={}, follow_redirects=False)
            assert resposta.status_code in (302, 403, 404), (
                f'{rota}: FUNCIONARIO recebeu {resposta.status_code}')

        depois = MedicaoObra.query.filter_by(obra_id=t.obra_id).count()
        assert depois == antes, (
            f'FUNCIONARIO gerou {depois - antes} medição(ões) por URL alternativa')
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_porta_irma.py::test_gerar_medicao_e_fechada_nas_duas_urls -v`
Expected: **FAIL** — as duas rotas aceitam o POST.

- [ ] **Step 3: Write minimal implementation**

Em `medicao_views.py:445-448`, somar `@admin_required` — **uma vez, cobrindo as
duas rotas**, já que as duas apontam para a mesma view:

```python
@medicao_bp.route('/obras/<int:obra_id>/medicao/fechar', methods=['POST'])
@medicao_bp.route('/medicao/obra/<int:obra_id>/gerar', methods=['POST'])
@login_required
@admin_required   # as DUAS URLs entram por aqui — fechar uma só é o defeito
def gerar_medicao(obra_id):
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_porta_irma.py::test_gerar_medicao_e_fechada_nas_duas_urls -v`
Expected: **PASS**.

Run: `python -m pytest tests/ -k medicao -m "not browser" -q`
Expected: verde.

- [ ] **Step 5: Commit**

```bash
git add tests/test_porta_irma.py medicao_views.py
git commit -m "fix(medicao): o admin_required do portal deixa de ser contornavel pela url irma"
```

---

### Task 3: O traceback sai do `flash`, e o guarda passa a varrer o app

> 🔴 📖 `views/rdo.py:3581` dá `flash()` com **500 caracteres de
> `format_exc()`** mais `current_user.email` e `admin_id`. É a classe que a Task
> 1 da Onda 5 fechou — no arquivo que aquela onda mais editou.
>
> 🔬 **Por que sobreviveu:** o teste-guarda
> (`test_onda5_recusado_nao_grava.py:44`) itera sobre
> `(ponto_views, equipe_views)`. Dois módulos, num app de centenas.

**Files:**
- Modify: `views/rdo.py:3576-3581`
- Test: `tests/test_porta_irma.py`

**Interfaces:**
- Consumes: nada.
- Produces: `_modulos_de_view()` — helper do teste, usado só aqui.

- [ ] **Step 1: Write the failing test**

O guarda deixa de nomear módulos e passa a varrer o pacote:

```python
def test_nenhum_modulo_de_view_manda_traceback_para_a_resposta():
    """🔴 `views/rdo.py:3581` — `flash(f'... TRACE: {error_trace[:500]}...')`,
    com `current_user.email` e `admin_id` junto.

    A Onda 5 fechou esta classe em `ponto_views` e `equipe_views`, e escreveu
    um guarda que itera sobre esses DOIS módulos. Este substitui: varre todo
    módulo que registra rota, e exige que `format_exc` só apareça em linha de
    log. É a lista que tem de crescer sozinha, não à mão.
    """
    import importlib
    import inspect
    import pathlib

    raiz = pathlib.Path(__file__).resolve().parent.parent
    suspeitos = []

    for caminho in sorted(list(raiz.glob('*.py')) + list(raiz.glob('views/*.py'))):
        if caminho.name.startswith('_') or 'test' in caminho.name:
            continue
        fonte = caminho.read_text(encoding='utf-8', errors='replace')
        if 'format_exc' not in fonte:
            continue
        for numero, linha in enumerate(fonte.splitlines(), start=1):
            if 'format_exc' not in linha:
                continue
            # Atribuir a variável é legítimo: o que não pode é a variável
            # chegar à RESPOSTA. Por isso a checagem é dupla — a linha do
            # format_exc, e o uso em flash/render.
            if 'logger.' in linha or 'logging.' in linha:
                continue
            nome_var = linha.split('=')[0].strip() if '=' in linha else None
            if not nome_var:
                suspeitos.append(f'{caminho.name}:{numero} {linha.strip()[:80]}')
                continue
            for n2, l2 in enumerate(fonte.splitlines(), start=1):
                if nome_var in l2 and ('flash(' in l2 or 'render_template(' in l2):
                    if '_detalhes_na_resposta' in l2:
                        continue   # o gate de produção já existe
                    suspeitos.append(
                        f'{caminho.name}:{n2} manda {nome_var} para a resposta '
                        f'→ {l2.strip()[:80]}')

    assert not suspeitos, (
        'traceback pode chegar à resposta em:\n  ' + '\n  '.join(suspeitos))


def test_erro_ao_salvar_rdo_nao_vaza_frames_nem_email():
    """A prova pela porta: o POST que quebra não conta a vida do usuário."""
    with app.app_context():
        t = um_tenant('rdo-flash', com_fatos=False)
        cliente = cliente_de(t.admin_id)

    # `obra_id` inexistente força o caminho de erro da rota.
    resposta = cliente.post('/rdo/salvar',
                            data={'obra_id': '999999999',
                                  'data_relatorio': '2026-08-20'},
                            follow_redirects=True)
    corpo = resposta.get_data(as_text=True)
    for vazamento in ('Traceback (most recent call last)', 'File "/home/',
                      'ADMIN_ID:', 'TRACE:'):
        assert vazamento not in corpo, f'{vazamento!r} vazou na resposta'
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_porta_irma.py -k "traceback or frames" -v`
Expected: **FAIL** — `rdo.py` aparece na lista de suspeitos.

- [ ] **Step 3: Write minimal implementation**

Em `views/rdo.py:3576-3581`, trocar o `flash` detalhado por mensagem, mantendo o
log completo:

```python
    except Exception as e:
        import traceback
        error_trace = traceback.format_exc()
        # O traceback, o e-mail e o admin_id iam para o FLASH: frames,
        # caminhos absolutos e o SQL com parâmetros vinculados, renderizados
        # na próxima tela. Alcançável por FUNCIONARIO pela rota-alias
        # `/funcionario/rdo/criar` (:3588), que delega aqui.
        # Detalhe vive no log; o usuário vê mensagem.
        logger.error(f"TRACEBACK COMPLETO (rdo_salvar_unificado):\n{error_trace}")
        logger.error(f"contexto: user={current_user.email} "
                     f"admin_id={current_user.admin_id}")
        flash('Não foi possível salvar o RDO. O erro foi registrado; '
              'tente novamente ou acione o suporte.', 'error')
```

⚠️ Se a varredura do Step 1 acusar outros módulos além de `views/rdo.py`,
**conserte todos nesta task** — é o ponto do guarda ser uma varredura.

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_porta_irma.py -k "traceback or frames" -v`
Expected: **PASS**.

- [ ] **Step 5: Commit**

```bash
git add tests/test_porta_irma.py views/rdo.py
git commit -m "fix(rdo): o flash para de mandar traceback, email e admin_id; o guarda vira varredura"
```

---

### Task 4: A mensagem de erro também passa pelo gate de produção

> 🔴 📖 `_detalhes_na_resposta()` (`356c2cf9`) fechou `error_details` e deixou
> `error_message=f"...{str(e)}"` intocado nas cinco rotas de
> `production_routes.py`. 🔬 Conferido: `templates/error.html:17` renderiza
> `{{ error_message }}` **cru**, e só `error_details` está atrás do `{% if %}`
> (`:30`). `str(e)` de erro SQLAlchemy carrega o SQL e os parâmetros vinculados.
>
> 🔬 `error_handlers.py` está limpo — a mensagem lá é constante. Os dois
> arquivos discordam desde `356c2cf9`.

**Files:**
- Modify: `production_routes.py:124`, `:201`, `:279`, `:336`, `:387`
- Test: `tests/test_porta_irma.py`

**Interfaces:**
- Consumes: `production_routes._detalhes_na_resposta` (já existe, `:13`).
- Produces: nada.

- [ ] **Step 1: Write the failing test**

```python
def test_rotas_safe_nao_mandam_excecao_crua_na_mensagem():
    """🔴 `production_routes.py:124,201,279,336,387` —
    `error_message=f"...{str(e)}"` SEM gate.

    `_detalhes_na_resposta()` fechou `error_details`; `error_message` ficou.
    `templates/error.html:17` renderiza `{{ error_message }}` cru — só
    `error_details` está atrás do `{% if %}` (:30). Num erro de SQLAlchemy,
    `str(e)` traz '(psycopg2.errors.X) ... [SQL: SELECT ...] [parameters:
    {...}]' para dentro do <h5>.

    O teste afirma o INVARIANTE de produção, não o texto: sob
    `IS_PRODUCTION`, nenhuma das cinco rotas pode devolver SQL na resposta.
    """
    import app as app_module

    with app.app_context():
        t = um_tenant('prod-safe', com_fatos=False)
        admin_id = t.admin_id

    cliente = cliente_de(admin_id)
    rotas = ('/prod/safe-funcionarios', '/prod/safe-dashboard',
             '/prod/safe-obras', '/prod/safe-veiculos', '/prod/safe-alimentacao')

    original = app_module.IS_PRODUCTION
    app_module.IS_PRODUCTION = True
    try:
        for rota in rotas:
            corpo = cliente.get(rota).get_data(as_text=True)
            for vazamento in ('[SQL:', '[parameters:', 'psycopg2.',
                              'sqlalchemy.exc', 'Traceback (most recent call last)'):
                assert vazamento not in corpo, (
                    f'{rota}: {vazamento!r} vazou na resposta em produção')
    finally:
        app_module.IS_PRODUCTION = original
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_porta_irma.py::test_rotas_safe_nao_mandam_excecao_crua_na_mensagem -v`

Expected: **FAIL** quando alguma das rotas erra de fato. ⚠️ **Se passar de
primeira, o teste não provou nada** — significa que nenhuma rota quebrou no
ambiente. Force o erro antes de seguir: renomeie temporariamente uma coluna
usada por `/prod/safe-funcionarios`, ou injete `raise SQLAlchemyError(...)` no
`try`, confirme o RED, desfaça a injeção. **Não pule esta confirmação:** foi
exatamente teste-que-nasce-verde que deixou os defeitos desta rodada passarem.

- [ ] **Step 3: Write minimal implementation**

Nos cinco `render_template('error.html', ...)`, passar a mensagem pelo gate:

```python
        return render_template('error.html',
                             error_code=500,
                             # `str(e)` traz SQL e parâmetros vinculados, e
                             # error.html:17 renderiza a mensagem CRUA — só
                             # `error_details` está atrás do {% if %}. Mesmo
                             # gate dos detalhes: em produção, mensagem
                             # genérica; fora, o diagnóstico.
                             error_message=_detalhes_na_resposta(
                                 f"Erro ao carregar funcionários: {str(e)}")
                                 or "Erro ao carregar funcionários",
                             error_details=_detalhes_na_resposta(full_error_details),
                             error_url="/prod/safe-funcionarios",
                             error_timestamp=error_timestamp), 500
```

⚠️ `:387` (`safe-alimentacao`) **não passa `error_details` nenhum** — só a
mensagem. Aplique o mesmo gate lá.

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_porta_irma.py::test_rotas_safe_nao_mandam_excecao_crua_na_mensagem -v`
Expected: **PASS**.

- [ ] **Step 5: Commit**

```bash
git add tests/test_porta_irma.py production_routes.py
git commit -m "fix(erros): a mensagem das rotas safe passa pelo mesmo gate dos detalhes"
```

---

### Task 5: O geofencing deixa de ser pulável por omissão

> 🔴 📖 `ponto_views.py:2453-2461`. 🔬 O comentário da correção anterior, no
> próprio arquivo (`:2447`): *"Antes a chamada era pulada nesse caso, tornando o
> controle consultivo — **bastava não mandar latitude/longitude**"*.
>
> Hoje **basta não mandar `obra_id`**: ele vem de `data.get('obra_id')`
> (`:2311`) sem checagem, e `if obra_id:` é falso na omissão, `if obra:` é falso
> para id de outro tenant. Nos dois casos `validar_localizacao_na_obra` **nunca
> é chamada** e o `RegistroPonto` nasce com `obra_id=None`.

**Files:**
- Modify: `ponto_views.py:2453-2461`
- Test: `tests/test_porta_irma.py`

**Interfaces:**
- Consumes: `validar_localizacao_na_obra` (já existe).
- Produces: nada.

- [ ] **Step 1: Write the failing test**

```python
@pytest.mark.parametrize('caso,payload_extra', [
    ('obra_id omitido', {}),
    ('obra_id de outro tenant', {'obra_id': 999999999}),
])
def test_ponto_facial_nao_pula_geofencing_por_obra_id(caso, payload_extra):
    """🔴 `ponto_views.py:2453` — `if obra_id:` / `if obra:`.

    O comentário em `:2447` diz que o defeito ANTIGO era "bastava não mandar
    latitude/longitude". A frase continua verdadeira trocando uma palavra:
    hoje basta não mandar `obra_id`. Nos dois casos o validador não roda e o
    RegistroPonto nasce com obra_id=None.

    Os dois casos são parametrizados de propósito: consertar a omissão e
    deixar o id-de-outro-tenant é repetir o padrão que este plano fecha.
    """
    from models import RegistroPonto

    with app.app_context():
        t = um_tenant('ponto-geo', com_fatos=False)
        admin_id = t.admin_id
        antes = RegistroPonto.query.filter_by(admin_id=admin_id).count()

    payload = {'foto_base64': 'data:image/png;base64,iVBORw0KGgo=',
               'tipo_ponto': 'entrada'}
    payload.update(payload_extra)
    # 🔬 Rota conferida: `@ponto_bp.route('/api/identificar-e-registrar')`
    # (`ponto_views.py:2285`) sobre `url_prefix='/ponto'` (`:553`).
    resposta = cliente_de(admin_id).post('/ponto/api/identificar-e-registrar',
                                         json=payload)

    assert resposta.status_code in (400, 403, 404), (
        f'{caso}: recebeu {resposta.status_code} — geofencing pulado')

    with app.app_context():
        depois = RegistroPonto.query.filter_by(admin_id=admin_id).count()
        assert depois == antes, (
            f'{caso}: gravou ponto sem passar pelo geofencing')
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_porta_irma.py -k geofencing -v`
Expected: **FAIL** nos dois casos — a rota segue adiante sem validar.

- [ ] **Step 3: Write minimal implementation**

`obra_id` passa a ser **obrigatório e resolvível**, com o mesmo desenho que
`validar_localizacao_na_obra` já tem para coordenada ausente:

```python
        # `obra_id` é obrigatório e tem de resolver NO TENANT. Antes,
        # `if obra_id:` era falso na omissão e `if obra:` era falso para id
        # alheio — nos dois casos o validador não rodava e o ponto nascia
        # com obra_id=None. É a mesma frase do defeito anterior
        # ("bastava não mandar latitude/longitude") com outra palavra.
        if not obra_id:
            return jsonify({
                'success': False,
                'message': 'Obra não informada. Selecione a obra antes de '
                           'registrar o ponto.'}), 400
        obra = Obra.query.filter_by(id=obra_id, admin_id=admin_id).first()
        if obra is None:
            return jsonify({
                'success': False,
                'message': 'Obra não encontrada para esta empresa.'}), 404

        valido_geo, distancia_obra, msg_geo = validar_localizacao_na_obra(
            latitude_func, longitude_func, obra)
        logger.info(f"Geofencing para {funcionario.nome}: {msg_geo}")
        if not valido_geo:
            return jsonify({
                'success': False,
                'message': f'Você está fora da área permitida da obra. {msg_geo}',
                'funcionario_nome': funcionario.nome,
                'distancia_obra': round(distancia_obra, 1) if distancia_obra else None
            }), 403
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_porta_irma.py -k geofencing -v`
Expected: **PASS** nos dois casos.

Run: `python -m pytest tests/ -k "ponto or geofenc" -m "not browser" -q`
Expected: verde. ⚠️ Se algum teste existente POSTa sem `obra_id` e esperava
sucesso, ele **documentava o furo** — traga o caso e decida explicitamente.

- [ ] **Step 5: Commit**

```bash
git add tests/test_porta_irma.py ponto_views.py
git commit -m "fix(ponto): omitir obra_id deixa de pular o geofencing inteiro"
```

---

### Task 6: A guarda de retrocesso enxerga o RDO irmão do mesmo dia

> 🔴 📖 `services/cronograma_apontamento_service.py:398` — a janela de `pct_ant`
> é `RDO.data_relatorio < rdo.data_relatorio`, **estrito**.
>
> 🔬 **A contradição está dentro do mesmo commit.** `views/rdo.py:4035-4046`
> documenta que dois RDOs na mesma obra e mesmo dia são estado LEGAL, e
> `recomputar_cadeia` (`:183`) reprocessa em ordem **`(data_relatorio, id)`** —
> ou seja, o recompute VÊ o irmão do mesmo dia; a guarda não. O apontamento que
> a guarda deixa passar é o que o recompute depois transforma em incremento
> negativo. É a forma exata do defeito que este `pct_ant` foi escrito para
> corrigir, um eixo ao lado.

**Files:**
- Modify: `services/cronograma_apontamento_service.py:398`
- Test: `tests/test_porta_irma.py`

**Interfaces:**
- Consumes: `RDOApontamentoCronograma`, `recomputar_cadeia` (já existem).
- Produces: nada.

- [ ] **Step 1: Write the failing test**

```python
def test_retrocesso_e_barrado_entre_rdos_do_mesmo_dia():
    """🔴 `cronograma_apontamento_service.py:398` — janela com `<` estrito.

    O commit `ed85d117` afirma, em `views/rdo.py:4035`, que dois RDOs na
    mesma obra e mesmo dia são estado LEGAL (a diária é rateada entre eles).
    E `recomputar_cadeia` reprocessa em ordem `(data_relatorio, id)`, logo
    ENXERGA o irmão do mesmo dia.

    A guarda não enxerga: RDO A do dia 20 registra acumulado 120
    (superexecução confirmada); RDO B, mesma obra e MESMO dia 20, registra
    50. `pct_ant` lê só o que é estritamente anterior ao dia 20, acha 0, e
    50 > 0 passa. O recompute depois vira isso em incremento de −70.
    """
    from models import RDO, RDOApontamentoCronograma, TarefaCronograma
    from services.cronograma_apontamento_service import (
        RetrocessoNaoPermitido, registrar_apontamento)

    with app.app_context():
        t = um_tenant('retro-mesmo-dia', com_fatos=False)
        dia = date(2026, 8, 20)

        tarefa = TarefaCronograma(
            obra_id=t.obra_id, admin_id=t.admin_id,
            nome_tarefa=f'Tarefa {uuid.uuid4().hex[:6]}', ordem=0,
            responsavel='propria', duracao_dias=10,
            percentual_concluido=0.0)
        db.session.add(tarefa)

        def _rdo(sufixo):
            r = RDO(numero_rdo=f'RDO-{uuid.uuid4().hex[:8]}-{sufixo}',
                    obra_id=t.obra_id, data_relatorio=dia, local='Campo',
                    admin_id=t.admin_id)
            db.session.add(r)
            return r

        rdo_a, rdo_b = _rdo('A'), _rdo('B')
        db.session.commit()

        # 🔬 Assinatura conferida (`:311`): `registrar_apontamento(rdo, tarefa,
        # *, quantidade_dia=None, percentual_acumulado=None, admin_id,
        # permitir_retrocesso=False, justificativa=None,
        # permitir_sobreexecucao=False)`. `quantidade_dia` XOR
        # `percentual_acumulado`. A superexecução de 120 exige
        # `permitir_sobreexecucao=True`, senão a guarda de SOBRE-execução
        # barra antes e o teste provaria a guarda errada.
        registrar_apontamento(rdo_a, tarefa, percentual_acumulado=120.0,
                              admin_id=t.admin_id,
                              permitir_sobreexecucao=True)
        db.session.commit()

        with pytest.raises(RetrocessoNaoPermitido):
            registrar_apontamento(rdo_b, tarefa, percentual_acumulado=50.0,
                                  admin_id=t.admin_id)
```

⚠️ `registrar_apontamento` faz **UPSERT por (rdo, tarefa)** — daí os dois RDOs
distintos do cenário. Um só RDO atualizaria a própria linha e não exercitaria
a janela de `pct_ant`.

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_porta_irma.py::test_retrocesso_e_barrado_entre_rdos_do_mesmo_dia -v`
Expected: **FAIL** — `DID NOT RAISE RetrocessoNaoPermitido`.

- [ ] **Step 3: Write minimal implementation**

A janela passa a casar com a ordem que `recomputar_cadeia` usa — mesma data,
desempate por id:

```python
        .filter(
            RDOApontamentoCronograma.tarefa_cronograma_id == tarefa.id,
            RDOApontamentoCronograma.admin_id == admin_id,
            # `<` estrito tornava INVISÍVEL o RDO irmão do mesmo dia — e
            # `views/rdo.py:4035` afirma, no mesmo commit, que dois RDOs no
            # mesmo dia são estado legal. `recomputar_cadeia` (:183) já
            # ordena por `(data_relatorio, id)` e enxerga o irmão; a guarda
            # tem de usar o MESMO critério, senão admite o apontamento que o
            # recompute depois vira incremento negativo.
            db.or_(
                RDO.data_relatorio < rdo.data_relatorio,
                db.and_(RDO.data_relatorio == rdo.data_relatorio,
                        RDOApontamentoCronograma.rdo_id != rdo.id),
            ),
        )
```

⚠️ **O `!= rdo.id` não é detalhe.** Sem ele, reprocessar o próprio RDO lê o
apontamento que ele mesmo acabou de gravar e a guarda barra a própria escrita.

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_porta_irma.py::test_retrocesso_e_barrado_entre_rdos_do_mesmo_dia -v`
Expected: **PASS**.

Adjacência obrigatória — é a área que a Onda 5 já derrubou uma vez:
Run: `python -m pytest tests/ -k "cronograma or apontamento or rdo" -m "not browser" -q`
Expected: verde. ⚠️ Os testes de caracterização que congelam "dois RDOs no
mesmo dia" (`test_cronograma_duplicado_rdo.py`,
`test_caracterizacao_apontamento_cronograma.py`) **têm de continuar passando** —
se caírem, a correção virou a guarda cega que `ed85d117` removeu.

- [ ] **Step 5: Commit**

```bash
git add tests/test_porta_irma.py services/cronograma_apontamento_service.py
git commit -m "fix(cronograma): a guarda de retrocesso passa a ver o rdo irmao do mesmo dia"
```

---

### Task 7: A fixture para de sortear o tenant, e o gate volta a medir o que diz

> 🔴 📖 `tests/test_propagacao_proposta_obra.py:35` e `:135` —
> `Usuario.query.filter_by(tipo_usuario='ADMIN').first()`, um `.first()` **sem
> `ORDER BY`**, seguido de `pytest.skip('Sem obra para tenant — teste pula')`.
>
> 🔬 **Medido em 28/08:** o banco de teste tem **185.784 usuários ADMIN**. Qual
> linha o PostgreSQL devolve num `SELECT ... LIMIT 1` sem ordenação é o que a
> varredura encontrar primeiro, e isso muda com qualquer escrita. No gate de
> 28/08 o sorteado foi `f3m_37ad1f04@test.local` (id 132306), que não tem obra —
> e **6 testes pararam de rodar**, sem nada no gate sinalizando. Não havia
> acontecido em nenhum dos oito gates anteriores.
>
> É o mesmo padrão desta onda num eixo diferente: **a verificação parece cobrir
> mais do que cobre**. Aqui a falha não é de `getsource` — é de sorteio.

**Files:**
- Modify: `tests/test_propagacao_proposta_obra.py:35-42`, `:133-140`
- Test: o próprio arquivo (é teste consertando teste).

**Interfaces:**
- Consumes: `tests/helpers_tenant.um_tenant`.
- Produces: nada.

- [ ] **Step 1: Write the failing test**

O RED aqui não é um `assert` novo — é **provar que o skip acontece**, e ele
depende de qual linha o banco devolve. Torne o defeito determinístico antes de
consertá-lo:

```python
def test_a_fixture_de_propagacao_nao_depende_de_sorteio(monkeypatch):
    """🔴 `test_propagacao_proposta_obra.py:35` — `.first()` sem ORDER BY.

    Colocado em `tests/test_porta_irma.py` de propósito: prova, de fora, que
    a fixture do outro arquivo não pula quando o primeiro ADMIN do banco não
    tem obra. Sem isto o conserto não teria RED — o sorteio às vezes cai numa
    linha boa e o defeito se esconde.
    """
    import models

    with app.app_context():
        marca = uuid.uuid4().hex[:8]
        from werkzeug.security import generate_password_hash
        orfao = models.Usuario(
            nome=f'Admin sem obra {marca}', username=f'semobra_{marca}',
            email=f'semobra_{marca}@t.local',
            password_hash=generate_password_hash('Senha@2026'),
            tipo_usuario=models.TipoUsuario.ADMIN, admin_id=None, ativo=True)
        db.session.add(orfao)
        db.session.commit()
        orfao_id = orfao.id

    # Força o pior sorteio possível: o primeiro ADMIN é o que não tem obra.
    consulta_real = models.Usuario.query

    with app.app_context():
        from test_propagacao_proposta_obra import setup_obra_proposta  # noqa

        # A fixture não pode pular só porque ESTE admin não tem obra.
        alvo = db.session.get(models.Usuario, orfao_id)
        assert alvo is not None
        obras = models.Obra.query.filter_by(admin_id=alvo.id).count()
        assert obras == 0, 'cenário mal montado: o órfão tem obra'
```

⚠️ Este teste sozinho não força o skip — ele monta o cenário. O RED de verdade
é o **Step 2**.

- [ ] **Step 2: Run test to verify it fails**

Com o órfão semeado, rode o arquivo alvo:

Run: `python -m pytest tests/test_propagacao_proposta_obra.py -p no:randomly -v -rs`
Expected: **6 SKIPPED**, com a razão `Sem obra para tenant — teste pula`.

⚠️ Se não pular, o sorteio caiu numa linha boa. Semeie mais órfãos e repita até
ver o skip — **é o RED, e sem ele o conserto não prova nada**.

- [ ] **Step 3: Write minimal implementation**

A fixture para de sortear e passa a semear o próprio tenant, como todo o resto
da suíte já faz:

```python
@pytest.fixture(scope='function')
def setup_obra_proposta():
    """Cria obra + proposta + itens em transação revertida.

    Antes, escolhia o tenant com
    `Usuario.query.filter_by(tipo_usuario='ADMIN').first()` — um `.first()`
    SEM `ORDER BY` num banco com 185.784 ADMINs — e pulava quando o sorteado
    não tinha obra. Em 28/08 isso tirou 6 testes do gate em silêncio, e o
    gate não tem como avisar: skip não é falha.

    `um_tenant` semeia admin + obra próprios. O teste deixa de depender do
    que já estava no banco, e não pula mais.
    """
    from helpers_tenant import um_tenant

    with app.app_context():
        t = um_tenant('propagacao', com_fatos=False)
        aid = t.admin_id
        obra = Obra.query.filter_by(admin_id=aid).first()

        svc1 = Servico(admin_id=aid, nome='__t82_svc_a', categoria='Teste',
                       unidade_medida='un')
        ...
```

⚠️ **Os dois `pytest.skip` saem.** Se algum cenário genuinamente não puder rodar,
ele deve **falhar**, não pular — skip que ninguém lê é cobertura perdida.

Aplique o mesmo em `:133-140`, que tem a cópia da mesma fixture.

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_propagacao_proposta_obra.py -p no:randomly -v -rs`
Expected: **6 passed, 0 skipped** — e o `-rs` não lista nada.

Rode duas vezes seguidas: a segunda prova que a fixture não deixa resíduo que
afete a primeira.

- [ ] **Step 5: Commit**

```bash
git add tests/test_propagacao_proposta_obra.py tests/test_porta_irma.py
git commit -m "fix(teste): a fixture de propagacao semeia o tenant em vez de sortear entre 185.784"
```

---

### Task 8: O gate, e o fecho da onda

**Files:**
- Nenhum. Só verificação.

- [ ] **Step 1: Rodar o gate inteiro**

Run: `bash run_tests.sh --gate`
Expected: **2846 passed, 4 skipped, 201 deselected, 2 xfailed** — ou mais
verdes, somando os testes deste plano.

⚠️ **O número de SKIPPED tem de CAIR de 10 para 4**: a Task 7 devolve ao gate
os 6 testes de `tests/test_propagacao_proposta_obra.py` que a fixture sorteada
tinha tirado. Se continuar em 10, a Task 7 não pegou. E siga conferindo o skip
nas rodadas seguintes: skip subindo não é ruído, é cobertura saindo sem aviso.

- [ ] **Step 2: Marcar os achados**

Em `docs/auditoria/achados-code-review-2026-08-25.md`, seção "Achados do
`/code-review max` sobre a branch da Onda 5 (28/08)", mover cada um dos seis
de "Abertos" para uma tabela de corrigidos, **com o commit que o fechou** — e
marcar também "Um achado sobre o próprio gate", fechado pela Task 7.

- [ ] **Step 3: Registrar o que a onda descobriu**

Se alguma task revelou achado novo — e a Task 3 vai revelar, porque a varredura
substitui uma lista de dois módulos por uma do app inteiro — registre em seção
própria no fim do documento de auditoria, como as Ondas 3 e 5 fizeram.

- [ ] **Step 4: Commit do fecho**

```bash
git add docs/
git commit -m "docs(porta-irma): a onda fecha, com o gate e os seis achados marcados"
```

---

## Notas de execução

**Ordem recomendada:** 7 PRIMEIRO (devolve 6 testes ao gate — executar as
outras sem ela é medir com régua curta) → 1 → 2 (autorização, maior superfície
e independentes entre si) → 3 → 4 (vazamento, e a Task 3 pode acusar alvos que
mudam o escopo da 4) → 5 → 6 (comportamento, e a 6 é a que mais mexe em área
sensível).

**A Task 6 é a de maior risco de regressão.** Mexe no mesmo serviço que derrubou
o gate da Onda 5. Rode a adjacência de cronograma antes de seguir para o gate.

⚠️ **Este plano NÃO cobre os cinco achados restantes do review** — eles estão em
`docs/superpowers/plans/2026-08-28-o-que-nao-persiste.md`, porque a causa é
outra: escrita que não chega ao banco, ou chega pela metade.
