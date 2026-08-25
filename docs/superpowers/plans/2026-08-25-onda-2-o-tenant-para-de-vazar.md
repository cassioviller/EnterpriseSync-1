# Onda 2 — O Tenant Para de Vazar Implementation Plan

> **Estado em 2026-08-25 (varredura de fecho):** 🟡 **ABERTO — pronto para executar** — 8 tasks. A Task 1 é **medição obrigatória antes de corrigir**: consertar o resolvedor torna invisível, de uma vez, todo dado carimbado no tenant fantasma.
>
> Escrito na varredura de 25/08. Índice de estado de todos os planos e specs em
> `docs/planos-em-aberto-2026-08-25.md`.


> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) ou superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Fazer com que nenhum papel de usuário escreva num tenant que não é o seu, e que nenhuma consulta ou FK vinda de formulário atravesse a fronteira entre empresas — fechando os 14 achados de isolamento que a varredura de 25/08 encontrou.

**Architecture:** Há **um** resolvedor de tenant correto no repositório, `utils.tenant.get_tenant_admin_id`, e **três** cópias que discordam dele. A onda começa apagando a divergência na raiz: `multitenant_helper.get_admin_id` passa a delegar, e com ela os 8 módulos que a importam se corrigem de uma vez. Depois vêm os pontos individuais, em dois grupos: FK vinda de formulário sem checagem (um helper novo, seis chamadores) e consulta que esqueceu `admin_id` (caso a caso, sem helper — cada uma erra de um jeito).

**Tech Stack:** Flask, Flask-Login, SQLAlchemy 2.0.41, PostgreSQL, pytest. Sem dependência nova.

**Spec:** `docs/superpowers/plans/2026-08-25-fecho-dos-114-achados.md` (Onda 2) — evidência por achado em `docs/auditoria/achados-code-review-2026-08-25.md` §7, §2, §5, §9.

## Global Constraints

- **Falha fechada, sempre.** Sem tenant resolvido: `abort(403)`. Nunca `admin_id IS NULL`, nunca "o primeiro admin da tabela", nunca um número fixo. 📖 `utils.tenant.require_tenant()` é o helper que já faz isso.
- **404, não 403, para recurso de outro tenant.** Responder 403 confirma que o id existe. 📖 A doutrina está escrita em `gestao_custos_views.py:547-549` e em `_get_compra_do_portal` — siga-a.
- **Um resolvedor só.** Ao fim desta onda, `get_tenant_admin_id` de `utils/tenant.py` é o único lugar onde se decide de quem é o dado. Se você precisar escrever um quarto, pare: é sinal de que a Task 2 não foi feita direito.
- **TDD sem exceção**, e o teste de isolamento usa 🔬 `tests/helpers_tenant.py` (`dois_tenants`, `cliente_de`). O arreio existe desde o p1 e a regra dele é: **nada compartilhado entre A e B**, e a busca é **pela marca**, nunca por contagem — contar dá o mesmo número quando cada tenant tem um registro.
- **Nenhuma migration**, com a única exceção da Task 1 se ela achar dado carimbado errado.
- **Gate ao fim:** `bash run_tests.sh --gate`. Régua: **2560 passed, 6 skipped, 201 deselected, 2 xfailed**.

---

## 🔴 A raiz, medida

📖 Os dois resolvedores, lado a lado:

| Papel | `utils.tenant.get_tenant_admin_id` | `multitenant_helper.get_admin_id` |
|---|---|---|
| `SUPER_ADMIN` | `current_user.id` | `current_user.id` ✅ igual |
| `ADMIN` | `current_user.id` | `current_user.id` ✅ igual |
| `FUNCIONARIO` | `current_user.admin_id` | `current_user.admin_id` ✅ igual |
| **`GESTOR_EQUIPES`** | `current_user.admin_id` | 🔴 **`current_user.id`** |
| **`ALMOXARIFE`** | `current_user.admin_id` | 🔴 **`current_user.id`** |

🔬 A divergência é **exatamente esses dois papéis**, e os dois são vivos
(`crm_views.py:83`, `views/metricas_views.py:44`). Um gestor com `id=42,
admin_id=7` recebe `admin_id=42` — **um tenant que não existe**.

🔬 **Oito módulos importam o helper errado**, e `configuracoes_views.py` o
importa **25 vezes** (import local, dentro de cada função):
`crud_servico_obra_real.py:11`, `custos_escritorio_views.py:13`,
`ponto_service.py:9`, `reembolso_views.py:12`, `ponto_views.py:28`,
`financeiro_views.py:18`, `configuracoes_views.py` (×25), `views/users.py` (×3).

🔴 **A armadilha que torna isso invisível na leitura:** 📖 `ponto_service.py:9` e
`ponto_views.py:28` fazem `from multitenant_helper import get_admin_id as
get_tenant_admin_id`. **Importam o errado com o nome do certo.** Quem lê o corpo
dessas rotas jura estar usando o resolvedor seguro.

---

## File Structure

| Arquivo | Ação | Responsabilidade |
|---|---|---|
| `scripts/medir_tenant_fantasma.py` | **Criar** | Task 1 — conta o estrago antes de consertar. Somente leitura |
| `multitenant_helper.py` | Modificar `:10-45` | Task 2 — a raiz. Delega, mantendo a forma defensiva |
| `utils/fk_do_tenant.py` | **Criar** | Task 5 — a validação de FK vinda de formulário, num lugar só |
| `views/rdo.py` | Modificar `:2820-2848` | Task 3 — mata o `return 10` |
| `portal_obras_views.py` | Modificar `:304`, `:645`, `:720` | Task 4 |
| `gestao_custos_views.py` | Modificar `:234`, `:1074`, `:262`, `:822` | Task 5 |
| `transporte_views.py` | Modificar `:204` | Task 5 |
| `views/almoxarifado/itens.py` | Modificar `:110`, `:165` | Task 5 |
| `financeiro_views.py` | Modificar `:895` | Task 5 |
| `veiculos_services.py` | Modificar `:166-175` | Task 6 |
| `rdo_editar_sistema.py` | Modificar `:218` | Task 6 |
| `ponto_views.py` | Modificar `:777` | Task 6 |
| `contabilidade_views.py` | Modificar `:1300`, `:1377` | Task 7 |
| `almoxarifado_utils.py` | Modificar `:257` | Task 7 |
| `ponto_service.py` | Modificar `:264` | Task 7 |
| `vinculos_audit_views.py` | Modificar `:38` | Task 8 |
| `services/cliente_resolver.py` | Modificar `:61` | Task 8 |
| `auth.py` | Modificar `:47-68` | Task 8 — apagar dois helpers mortos |
| `tests/test_onda2_tenant_nao_vaza.py` | **Criar** | Todos os testes desta onda |

---

### Task 1: Medir o estrago antes de consertar

> 🔴 **Esta task é pré-requisito da Task 2 e não pode ser pulada.** Se existe
> dado gravado no tenant fantasma, corrigir o resolvedor o torna **invisível de
> uma vez** — o gestor perde o acesso ao que ele mesmo criou, sem aviso. Medir
> primeiro é o que decide se a Task 2 precisa de migration de saneamento.

**Files:**
- Create: `scripts/medir_tenant_fantasma.py`

**Interfaces:**
- Consumes: nada.
- Produces: um relatório em texto. Nenhuma outra task importa este script.

- [ ] **Step 1: Write the script**

Create `scripts/medir_tenant_fantasma.py`:

```python
#!/usr/bin/env python3
"""Quantos registros foram carimbados no tenant fantasma?

`multitenant_helper.get_admin_id()` devolve `current_user.id` para
GESTOR_EQUIPES e ALMOXARIFE, quando o certo é `current_user.admin_id`. Todo
registro escrito por esses papéis pelos 8 módulos que importam o helper foi
para um `admin_id` que não é de nenhum ADMIN.

Este script SÓ LÊ. Rode antes da Task 2 da Onda 2.

    python scripts/medir_tenant_fantasma.py
"""
import sys

from app import app, db
from models import TipoUsuario, Usuario

# As tabelas escritas pelos 8 módulos que importam `multitenant_helper`.
# Nome da tabela → o módulo que a escreve, para o relatório dizer onde olhar.
TABELAS = {
    'conta_pagar': 'financeiro_views',
    'conta_receber': 'financeiro_views',
    'fluxo_caixa': 'financeiro_views',
    'registro_ponto': 'ponto_views / ponto_service',
    'reembolso': 'reembolso_views',
    'custo_escritorio': 'custos_escritorio_views',
    'configuracao_empresa': 'configuracoes_views',
    'usuario': 'views/users.py',
}


def main():
    with app.app_context():
        suspeitos = Usuario.query.filter(
            Usuario.tipo_usuario.in_([TipoUsuario.GESTOR_EQUIPES,
                                      TipoUsuario.ALMOXARIFE])).all()
        if not suspeitos:
            print('Nenhum GESTOR_EQUIPES nem ALMOXARIFE no banco.')
            print('VEREDITO: a Task 2 entra SEM migration de saneamento.')
            return 0

        print(f'{len(suspeitos)} usuário(s) com papel afetado:\n')
        total_geral = 0
        for u in suspeitos:
            print(f'  id={u.id} {u.tipo_usuario.value} admin_id={u.admin_id} '
                  f'({u.email})')
            if u.admin_id == u.id:
                print('    ↳ admin_id == id: este não distingue os dois '
                      'resolvedores, nada a corrigir')
                continue
            for tabela, modulo in sorted(TABELAS.items()):
                try:
                    n = db.session.execute(
                        db.text(f'SELECT count(*) FROM {tabela} '
                                f'WHERE admin_id = :aid'),
                        {'aid': u.id}).scalar()
                except Exception as erro:
                    print(f'    {tabela}: não consultável ({erro})')
                    continue
                if n:
                    total_geral += n
                    print(f'    🔴 {tabela}: {n} linha(s) com admin_id={u.id} '
                          f'(deveria ser {u.admin_id}) — escrito por {modulo}')

        print()
        if total_geral:
            print(f'VEREDITO: {total_geral} linha(s) no tenant fantasma.')
            print('A Task 2 PRECISA de migration de saneamento, e ela é '
                  'DECISÃO HUMANA: mover o dado para o admin_id certo pode '
                  'colidir com registro que já existe lá.')
        else:
            print('VEREDITO: nenhuma linha no tenant fantasma.')
            print('A Task 2 entra SEM migration de saneamento.')
        return 0


if __name__ == '__main__':
    sys.exit(main())
```

- [ ] **Step 2: Run it against the dev database**

Run: `python scripts/medir_tenant_fantasma.py`
Expected: um veredito, num dos dois sentidos.

⚠️ **O banco de dev é ~99% resíduo de suíte** — ele prova a *forma*, não o
volume. A medição que decide é a de **produção**, e ela depende do mesmo acesso
que `scripts/medir_producao.py` espera. Se produção não estiver acessível,
**registre isso e siga**: a Task 2 entra assim mesmo, e a migration de
saneamento fica como item humano nomeado no fecho desta onda.

- [ ] **Step 3: Commit**

```bash
git add scripts/medir_tenant_fantasma.py
git commit -m "chore(tenant): script que conta o estrago do tenant fantasma

So le. Roda antes de corrigir o resolvedor, porque corrigir torna o dado
carimbado errado invisivel de uma vez."
```

---

### Task 2: A raiz — um resolvedor só

**Files:**
- Modify: `multitenant_helper.py:10-45`
- Test: `tests/test_onda2_tenant_nao_vaza.py` (criar)

**Interfaces:**
- Consumes: `utils.tenant.get_tenant_admin_id`.
- Produces: `get_admin_id() -> int | None` — mesma assinatura, mesmo tipo de retorno, mesma tolerância a contexto sem request. **Os 8 módulos importadores não mudam nenhuma linha.**

⚠️ **A forma defensiva precisa sobreviver.** 📖 `get_admin_id` de hoje engole
exceção e devolve `None` fora de request; 📖 `get_tenant_admin_id` acessa
`current_user.is_authenticated` e `current_user.tipo_usuario` direto e **pode
levantar** em contexto de job/seed. A casca fica.

- [ ] **Step 1: Write the failing test**

Create `tests/test_onda2_tenant_nao_vaza.py`:

```python
"""Onda 2 — o tenant para de vazar.

O arreio é `tests/helpers_tenant.py` (`dois_tenants`, `cliente_de`), que existe
desde o p1. A regra dele: nada é compartilhado entre A e B, e a busca é PELA
MARCA — contar dá o mesmo número quando cada tenant tem um registro.
"""
import os
import sys
import uuid

import pytest
from werkzeug.security import generate_password_hash

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import main  # noqa: F401 — registra blueprints e handlers de evento
from app import app, db
from helpers_tenant import cliente_de, dois_tenants
from models import TipoUsuario, Usuario

pytestmark = pytest.mark.integration


@pytest.fixture(autouse=True)
def _config():
    app.config['TESTING'] = True
    app.config['WTF_CSRF_ENABLED'] = False
    if not app.secret_key:
        app.secret_key = 'test-onda2-tenant'
    yield


def _usuario_com_papel(papel, admin_id):
    """Um usuário do papel pedido, pendurado num admin que NÃO é ele."""
    suf = uuid.uuid4().hex[:8]
    u = Usuario(
        username=f'onda2_{suf}', email=f'onda2_{suf}@test.local',
        nome=f'Papel {papel.value} {suf}',
        password_hash=generate_password_hash('Senha@2026'),
        tipo_usuario=papel, ativo=True, admin_id=admin_id,
    )
    db.session.add(u)
    db.session.flush()
    return u


# ---------------------------------------------------------------------------
# Task 2 — a raiz
# ---------------------------------------------------------------------------

@pytest.mark.parametrize('papel', [TipoUsuario.GESTOR_EQUIPES,
                                   TipoUsuario.ALMOXARIFE])
def test_gestor_e_almoxarife_resolvem_o_tenant_do_dono(papel):
    """🔴 `multitenant_helper.py:25` devolvia `current_user.id` para estes dois.

    Um gestor com id=42 e admin_id=7 escrevia tudo em admin_id=42 — um tenant
    que não existe. Invisível para o admin 7, e leitura vazia de volta.
    """
    from multitenant_helper import get_admin_id
    from utils.tenant import get_tenant_admin_id

    with app.app_context():
        a, _b = dois_tenants('onda2_raiz', com_fatos=False)
        usuario = _usuario_com_papel(papel, admin_id=a.admin_id)
        db.session.commit()
        uid, esperado = usuario.id, a.admin_id

    assert uid != esperado, 'o fixture precisa distinguir id de admin_id'

    cliente = cliente_de(uid)
    with cliente.session_transaction():
        pass
    with app.test_request_context():
        from flask_login import login_user
        login_user(Usuario.query.get(uid))
        assert get_admin_id() == esperado, (
            f'{papel.value}: get_admin_id devolveu o próprio id, não o do dono')
        # e os dois resolvedores passam a concordar, que é o ponto da task
        assert get_admin_id() == get_tenant_admin_id()


@pytest.mark.parametrize('papel', [TipoUsuario.ADMIN, TipoUsuario.SUPER_ADMIN])
def test_admin_e_super_admin_nao_mudam(papel):
    """A delegação não pode mexer nos papéis que já estavam certos."""
    from multitenant_helper import get_admin_id

    with app.app_context():
        suf = uuid.uuid4().hex[:8]
        u = Usuario(username=f'onda2adm_{suf}',
                    email=f'onda2adm_{suf}@test.local', nome='Adm',
                    password_hash=generate_password_hash('Senha@2026'),
                    tipo_usuario=papel, ativo=True, versao_sistema='v2')
        db.session.add(u)
        db.session.commit()
        uid = u.id

    with app.test_request_context():
        from flask_login import login_user
        login_user(Usuario.query.get(uid))
        assert get_admin_id() == uid


def test_sem_request_context_devolve_none_em_vez_de_levantar():
    """A casca defensiva de hoje precisa sobreviver à delegação.

    `get_tenant_admin_id` acessa `current_user` direto e levanta fora de
    request; `get_admin_id` é chamado de job, seed e CLI.
    """
    from multitenant_helper import get_admin_id
    assert get_admin_id() is None
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_onda2_tenant_nao_vaza.py -v`
Expected: FAIL nos dois `test_gestor_e_almoxarife_...` — `get_admin_id` devolve o `id` do usuário, não o `admin_id` do dono.

- [ ] **Step 3: Write minimal implementation**

Trocar `multitenant_helper.py` inteiro por:

```python
"""Casca de compatibilidade sobre o resolvedor único de tenant.

Este módulo tinha a PRÓPRIA lógica de resolução, e ela discordava de
`utils.tenant.get_tenant_admin_id` em exatamente dois papéis: GESTOR_EQUIPES e
ALMOXARIFE caíam num `return current_user.id` que os mandava para um tenant
inexistente. Como oito módulos o importam — e dois deles o importam com o nome
do resolvedor certo (`get_admin_id as get_tenant_admin_id`, em
`ponto_service.py:9` e `ponto_views.py:28`) — o defeito era invisível na
leitura do chamador.

A lógica agora mora num lugar só. O que fica aqui é a casca defensiva, que o
resolvedor de `utils.tenant` não tem: ele acessa `current_user` direto e
levanta fora de request, e este helper é chamado de job, seed e CLI.
"""
import logging

from flask_login import current_user

logger = logging.getLogger(__name__)


def get_admin_id():
    """O admin_id do tenant do usuário autenticado, ou None.

    Delega para `utils.tenant.get_tenant_admin_id` — o resolvedor único.
    Nunca levanta: fora de request, sem usuário ou com erro, devolve None.
    """
    try:
        from utils.tenant import get_tenant_admin_id
        return get_tenant_admin_id()
    except Exception as erro:
        logger.debug('get_admin_id sem tenant resolvível: %s', erro)
        return None


def get_current_user_safe():
    """Retorna o current_user de forma segura."""
    return current_user
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_onda2_tenant_nao_vaza.py -v`
Expected: PASS

Depois as suítes dos oito importadores:
Run: `python -m pytest tests/test_p1_isolamento_relatorios.py tests/test_gestao_custo_filho_tenant.py tests/test_b5_baixa_conta_pagar.py -v`
Expected: PASS, mesma contagem de antes.

- [ ] **Step 5: Commit**

```bash
git add multitenant_helper.py tests/test_onda2_tenant_nao_vaza.py
git commit -m "fix(tenant): GESTOR_EQUIPES e ALMOXARIFE param de escrever em tenant fantasma

RED: get_admin_id devolvia o proprio id, nao o do dono, para os dois papeis

multitenant_helper tinha logica propria e discordava de
utils.tenant.get_tenant_admin_id em exatamente dois papeis. Oito modulos o
importam, e dois deles com o nome do resolvedor CERTO
(get_admin_id as get_tenant_admin_id) — o que tornava o defeito invisivel na
leitura do chamador.

Agora e casca: delega, e mantem a tolerancia a contexto sem request que o
resolvedor de utils.tenant nao tem."
```

---

### Task 3: Morre o `return 10`

**Files:**
- Modify: `views/rdo.py:2820-2848` (`get_admin_id_robusta`)
- Test: `tests/test_onda2_tenant_nao_vaza.py` (acrescentar)

**Interfaces:**
- Consumes: `utils.tenant.get_tenant_admin_id`.
- Produces: `get_admin_id_robusta() -> int | None`. Passa a devolver `None` onde antes devolvia `10`. 🔬 Confira os chamadores no arquivo antes: `grep -n "get_admin_id_robusta" views/rdo.py`.

⚠️ 📖 A "estratégia 3" busca `Funcionario.query.filter_by(email=current_user.email)`
**sem escopo de tenant** — e-mail repetido entre empresas devolve o funcionário
errado. A "estratégia 4" cai em `get_admin_id_dinamico()`, e o `except` final
devolve **`10` fixo**: um tenant real, de alguém.

- [ ] **Step 1: Write the failing test**

Acrescentar a `tests/test_onda2_tenant_nao_vaza.py`:

```python
# ---------------------------------------------------------------------------
# Task 3 — o `return 10`
# ---------------------------------------------------------------------------

def test_rdo_nao_tem_mais_admin_id_fixo_no_codigo():
    """🔴 `views/rdo.py:2848`: o `except` devolvia `10` — um tenant de alguém."""
    import inspect

    import views.rdo as rdo_mod
    fonte = inspect.getsource(rdo_mod)
    assert 'return 10' not in fonte, (
        'views/rdo.py ainda tem admin_id fixo no fallback')


def test_rdo_nao_resolve_tenant_por_email_sem_escopo():
    """A estratégia 3 buscava Funcionario por e-mail, sem admin_id.

    E-mail repetido entre empresas devolvia o funcionário da outra.
    """
    import inspect

    import views.rdo as rdo_mod
    fonte = inspect.getsource(rdo_mod)
    assert 'Funcionario.query.filter_by(email=current_user.email)' not in fonte
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_onda2_tenant_nao_vaza.py -k rdo -v`
Expected: FAIL — os dois padrões ainda estão no arquivo.

- [ ] **Step 3: Check the callers before changing the return contract**

```bash
grep -n "get_admin_id_robusta" views/rdo.py
```

Se algum chamador usar o retorno sem checar `None`, acrescente a checagem **no
chamador**, com `abort(403)`. Não devolva número para manter chamador ingênuo de
pé — foi assim que o `10` nasceu.

- [ ] **Step 4: Write minimal implementation**

Trocar o corpo de `get_admin_id_robusta` por:

```python
        def get_admin_id_robusta():
            """O tenant do usuário logado, ou None.

            Tinha quatro "estratégias" em cascata; as duas últimas eram o
            defeito. A 3 buscava `Funcionario` por e-mail SEM escopo de
            tenant — e-mail repetido entre empresas devolvia o funcionário da
            outra. E o `except` final devolvia `10` fixo: um tenant real, de
            alguém, escolhido em tempo de desenvolvimento.

            Agora delega para o resolvedor único e falha em None. Quem chama
            decide o que fazer sem tenant — e a resposta certa é 403.
            """
            from utils.tenant import get_tenant_admin_id
            try:
                return get_tenant_admin_id()
            except Exception as erro:
                logger.warning('tenant não resolvível no RDO: %s', erro)
                return None
```

- [ ] **Step 5: Run test to verify it passes**

Run: `python -m pytest tests/test_onda2_tenant_nao_vaza.py -k rdo -v`
Expected: PASS

Run: `python -m pytest tests/test_rdo_unificado_playwright.py -v -m "not browser"` e `python -m pytest tests/ -k rdo -m "not browser" -q`
Expected: PASS, mesma contagem de antes.

- [ ] **Step 6: Commit**

```bash
git add views/rdo.py tests/test_onda2_tenant_nao_vaza.py
git commit -m "fix(rdo): morre o admin_id 10 hardcoded e a busca por email sem escopo

RED: 'return 10' e Funcionario.query.filter_by(email=...) ainda no arquivo

get_admin_id_robusta tinha quatro estrategias em cascata; as duas ultimas
eram o defeito. Agora delega para o resolvedor unico e falha em None."
```

---

### Task 4: O portal do cliente para de mostrar compra interna

**Files:**
- Modify: `portal_obras_views.py:304` (`compras_resolvidas`), `:645` (`upload_comprovante`), `:720` (`ver_comprovante`)
- Test: `tests/test_onda2_tenant_nao_vaza.py` (acrescentar)

**Interfaces:**
- Consumes: `_get_compra_do_portal(obra, compra_id)`, que já existe em `portal_obras_views.py:504` e já filtra `id`, `obra_id`, `admin_id` **e** `tipo_compra='aprovacao_cliente'`.
- Produces: nada.

🔴 **O achado mais constrangedor da varredura:** 📖 o docstring de
`_get_compra_do_portal` (`:511-514`) descreve este vazamento **como corrigido** e
aponta a linha exata da listagem que o produz. A correção entrou nas duas rotas
de ação e **não** na listagem que o próprio docstring nomeia.

- [ ] **Step 1: Write the failing test**

Acrescentar a `tests/test_onda2_tenant_nao_vaza.py`:

```python
# ---------------------------------------------------------------------------
# Task 4 — o portal
# ---------------------------------------------------------------------------

def _obra_com_token(admin_id):
    from datetime import date, timedelta

    from models import Obra
    obra = Obra.query.filter_by(admin_id=admin_id).first()
    obra.token_cliente = uuid.uuid4().hex
    obra.token_cliente_expira_em = date.today() + timedelta(days=30)
    obra.portal_cliente_ativo = True
    db.session.flush()
    return obra


def test_compra_interna_aprovada_nao_aparece_no_portal():
    """🔴 `portal_obras_views.py:304` — `compras_resolvidas` não filtra tipo.

    O docstring de `_get_compra_do_portal` (`:511`) descreve ESTE vazamento
    como corrigido e aponta a linha. A correção entrou nas rotas de ação e não
    na listagem.
    """
    from models import PedidoCompra

    with app.app_context():
        a, _b = dois_tenants('onda2_portal', com_fatos=False)
        obra = _obra_com_token(a.admin_id)
        interna = PedidoCompra(
            admin_id=a.admin_id, obra_id=obra.id,
            numero=f'INTERNA-{a.marca}',
            tipo_compra='normal',
            status_aprovacao_cliente='APROVADO',
            valor_total=1234.00)
        db.session.add(interna)
        db.session.commit()
        token = obra.token_cliente

    resposta = app.test_client().get(f'/portal/obra/{token}')
    corpo = resposta.get_data(as_text=True)
    assert f'INTERNA-{a.marca}' not in corpo, (
        'compra tipo_compra=normal vazou na vitrine do cliente')


def test_comprovante_de_compra_interna_nao_e_servido_a_anonimo():
    """`upload_comprovante:645` e `ver_comprovante:720` resolviam a compra por
    `filter_by(id, obra_id)` — sem admin_id e sem tipo_compra. O segundo faz
    `send_file`.
    """
    from models import PedidoCompra

    with app.app_context():
        a, _b = dois_tenants('onda2_compr', com_fatos=False)
        obra = _obra_com_token(a.admin_id)
        interna = PedidoCompra(
            admin_id=a.admin_id, obra_id=obra.id,
            numero=f'INT2-{a.marca}', tipo_compra='normal',
            status_aprovacao_cliente='APROVADO', valor_total=99.00)
        db.session.add(interna)
        db.session.commit()
        token, cid = obra.token_cliente, interna.id

    cliente = app.test_client()
    assert cliente.get(f'/portal/obra/{token}/compra/{cid}/comprovante/ver'
                       ).status_code == 404
    assert cliente.post(f'/portal/obra/{token}/compra/{cid}/comprovante',
                        data={}).status_code == 404
```

⚠️ Confirme as duas URLs contra o arquivo antes de rodar — as rotas de
comprovante têm caminhos próprios:

```bash
grep -n "comprovante" portal_obras_views.py | grep "route"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_onda2_tenant_nao_vaza.py -k "portal or comprovante" -v`
Expected: FAIL — `INTERNA-<marca>` aparece no corpo, e as rotas de comprovante devolvem 200/302 em vez de 404.

- [ ] **Step 3: Write minimal implementation**

**3a.** Em `portal_obras_views.py:304`, acrescentar o filtro de tipo:

```python
    compras_resolvidas = (
        PedidoCompra.query
        .filter_by(obra_id=obra.id, admin_id=admin_id,
                   # A restrição que o docstring de `_get_compra_do_portal`
                   # (`:511`) já dizia existir aqui, e que faltava: o portal
                   # só mostra o que ele próprio ofereceu ao cliente. Sem
                   # ela, compra interna carimbada APROVADO virava vitrine.
                   tipo_compra='aprovacao_cliente')
        .filter(PedidoCompra.status_aprovacao_cliente.in_(['APROVADO', 'RECUSADO']))
        .order_by(PedidoCompra.created_at.desc())
        .all()
    )
```

**3b.** Em `upload_comprovante` (`:645`) e `ver_comprovante` (`:720`), trocar as
duas linhas idênticas:

```python
    compra = PedidoCompra.query.filter_by(id=compra_id, obra_id=obra.id).first_or_404()
```

por:

```python
    compra = _get_compra_do_portal(obra, compra_id)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_onda2_tenant_nao_vaza.py -k "portal or comprovante" -v`
Expected: PASS

Run: `python -m pytest tests/ -k portal -m "not browser" -q`
Expected: PASS, mesma contagem de antes.

- [ ] **Step 5: Commit**

```bash
git add portal_obras_views.py tests/test_onda2_tenant_nao_vaza.py
git commit -m "fix(portal): compra interna para de vazar na vitrine do cliente

RED: 'INTERNA-<marca>' aparecia no corpo do portal; comprovante servido a anonimo

O docstring de _get_compra_do_portal (:511) descreve ESTE vazamento como
corrigido e aponta a linha da listagem que o produz. A correcao tinha entrado
nas duas rotas de acao e nao na listagem.

As rotas de comprovante resolviam a compra por filter_by(id, obra_id): sem
admin_id e sem tipo_compra. A de ver faz send_file."
```

---

### Task 5: FK vinda de formulário, validada num lugar só

**Files:**
- Create: `utils/fk_do_tenant.py`
- Modify: `gestao_custos_views.py:234`, `:1074`, `:262`, `:822`; `transporte_views.py:204`; `views/almoxarifado/itens.py:110`, `:165`; `financeiro_views.py:895`
- Test: `tests/test_onda2_tenant_nao_vaza.py` (acrescentar)

**Interfaces:**
- Consumes: nada.
- Produces:
  - `fk_do_tenant(modelo, valor, admin_id, *, campo, obrigatorio=False) -> int | None` — devolve o id validado, `None` para vazio não-obrigatório, e `abort(400)` com mensagem genérica quando o id não pertence ao tenant.

📖 **O padrão correto já existe**, em `gestao_custos_views.py:550`, com o
comentário que explica o ataque e a doutrina da mensagem genérica. Este helper é
esse padrão extraído — não invente outro.

- [ ] **Step 1: Write the failing test**

Acrescentar a `tests/test_onda2_tenant_nao_vaza.py`:

```python
# ---------------------------------------------------------------------------
# Task 5 — FK vinda de formulário
# ---------------------------------------------------------------------------

def test_fk_do_tenant_aceita_o_que_e_do_tenant():
    from models import Obra
    from utils.fk_do_tenant import fk_do_tenant

    with app.app_context():
        a, _b = dois_tenants('onda2_fk_ok', com_fatos=False)
        with app.test_request_context():
            assert fk_do_tenant(Obra, a.obra_id, a.admin_id,
                                campo='obra') == a.obra_id
            assert fk_do_tenant(Obra, '', a.admin_id, campo='obra') is None
            assert fk_do_tenant(Obra, None, a.admin_id, campo='obra') is None


def test_fk_do_tenant_recusa_id_de_outro_tenant():
    from werkzeug.exceptions import BadRequest

    from models import Obra
    from utils.fk_do_tenant import fk_do_tenant

    with app.app_context():
        a, b = dois_tenants('onda2_fk_no', com_fatos=False)
        with app.test_request_context():
            with pytest.raises(BadRequest) as exc:
                fk_do_tenant(Obra, b.obra_id, a.admin_id, campo='obra')
            # a mensagem NÃO pode confirmar que a obra existe
            texto = str(exc.value).lower()
            assert 'outro tenant' not in texto
            assert 'não existe' not in texto


def test_fk_do_tenant_exige_quando_obrigatorio():
    from werkzeug.exceptions import BadRequest

    from models import Obra
    from utils.fk_do_tenant import fk_do_tenant

    with app.app_context():
        a, _b = dois_tenants('onda2_fk_ob', com_fatos=False)
        with app.test_request_context():
            with pytest.raises(BadRequest):
                fk_do_tenant(Obra, '', a.admin_id, campo='obra',
                             obrigatorio=True)


def test_lancamento_de_transporte_nao_prende_custo_na_obra_alheia():
    """🔴 `transporte_views.py:204` — cinco FKs entravam sem checagem.

    Só `osc_id` era validado. Um POST forjado prendia o lançamento e o
    `CustoObra` à obra de outro tenant, cujo nome passava a aparecer na
    listagem deste.
    """
    from models import LancamentoTransporte

    with app.app_context():
        a, b = dois_tenants('onda2_transp', com_fatos=False)
        admin_a, obra_b, marca_b = a.admin_id, b.obra_id, b.marca

    resposta = cliente_de(admin_a).post('/transporte/lancamentos/novo', data={
        'obra_id': str(obra_b),
        'data_lancamento': '2026-08-25',
        'valor': '100,00',
        'descricao': f'forjado contra {marca_b}',
    }, follow_redirects=False)
    assert resposta.status_code in (400, 403, 302)

    with app.app_context():
        vazou = LancamentoTransporte.query.filter_by(obra_id=obra_b).count()
        assert vazou == 0, 'lançamento gravado na obra de outro tenant'
```

⚠️ Confirme a URL do POST de transporte antes de rodar:
`grep -n "route.*lancamento" transporte_views.py | head`

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_onda2_tenant_nao_vaza.py -k "fk_do_tenant or transporte" -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'utils.fk_do_tenant'`.

- [ ] **Step 3: Write minimal implementation**

Create `utils/fk_do_tenant.py`:

```python
"""Uma FK vinda de formulário só entra se for do tenant de quem envia.

O padrão nasceu em `gestao_custos_views.py:550`, escrito para fechar um ataque
real: um POST forjado com `obra_id` de outra empresa prendia o custo lá, e
`sincronizar_obra_do_pai` propagava para o pai, disparando `recalcular_obra` no
snapshot orçado×real da vítima. A correção entrou naquela função e **não** nas
irmãs — `novo()` e `editar()` do mesmo arquivo ficaram de fora, e o mesmo
buraco existia em transporte, almoxarifado e financeiro.

Aqui o padrão vira helper, para não haver uma nona cópia com a nona variação.
"""
from flask import abort

__all__ = ['fk_do_tenant']


def fk_do_tenant(modelo, valor, admin_id, *, campo, obrigatorio=False):
    """Valida que `valor` é um id de `modelo` pertencente a `admin_id`.

    Devolve o id como `int`, ou `None` para valor vazio quando não obrigatório.
    Aborta com 400 e mensagem GENÉRICA quando o id não é do tenant: dizer
    "obra de outro tenant" confirmaria a existência dela. Mesma doutrina do
    404-em-vez-de-403 de `_rdo_do_tenant_ou_404` e de `obra_required`.
    """
    if valor in (None, '', b''):
        if obrigatorio:
            abort(400, f'{campo}: obrigatório.')
        return None

    try:
        ident = int(valor)
    except (TypeError, ValueError):
        abort(400, f'{campo} inválido.')

    if not admin_id:
        # Sem tenant resolvido não há como validar — falha fechada.
        abort(403)

    existe = modelo.query.filter_by(id=ident, admin_id=admin_id).first()
    if not existe:
        abort(400, f'{campo} inválido.')
    return ident
```

- [ ] **Step 4: Apply to the eight call sites**

Em cada arquivo, importar `from utils.fk_do_tenant import fk_do_tenant` e
trocar a leitura crua pelo helper. Os oito, com o modelo de cada um:

| Arquivo:linha | Campo | Modelo |
|---|---|---|
| `gestao_custos_views.py:234` (`novo`) | `obra_id` | `Obra` |
| `gestao_custos_views.py:1074` (`editar`) | `obra_id` | `Obra` |
| `gestao_custos_views.py:262` | `subempreiteiro_id` | `Subempreiteiro` |
| `gestao_custos_views.py:822` | `banco_id` | `Banco` |
| `transporte_views.py:204` | `obra_id`, `categoria_id`, `funcionario_id`, `veiculo_id`, `centro_custo_id` | `Obra`, `CategoriaTransporte`, `Funcionario`, `Veiculo`, `CentroCusto` |
| `views/almoxarifado/itens.py:110` | `categoria_id` | `CategoriaAlmoxarifado` |
| `views/almoxarifado/itens.py:165` | `categoria_id` | `CategoriaAlmoxarifado` |
| `financeiro_views.py:895` | `fornecedor_id` | `Fornecedor` |

Exemplo, em `transporte_views.py`:

```python
        obra_id = fk_do_tenant(Obra, request.form.get('obra_id'),
                               admin_id, campo='Obra')
        categoria_id = fk_do_tenant(CategoriaTransporte,
                                    request.form.get('categoria_id'),
                                    admin_id, campo='Categoria')
        funcionario_id = fk_do_tenant(Funcionario,
                                      request.form.get('funcionario_id'),
                                      admin_id, campo='Funcionário')
        veiculo_id = fk_do_tenant(Veiculo, request.form.get('veiculo_id'),
                                  admin_id, campo='Veículo')
        centro_custo_id = fk_do_tenant(CentroCusto,
                                       request.form.get('centro_custo_id'),
                                       admin_id, campo='Centro de custo')
```

⚠️ **Confira o nome real de cada modelo antes de escrever** — alguns diferem do
nome do campo:

```bash
grep -n "^class CategoriaTransporte\|^class CentroCusto\|^class Subempreiteiro\|^class Banco\|^class Fornecedor\|^class CategoriaAlmoxarifado" models.py
```

Se algum modelo não tiver coluna `admin_id`, **pare e reporte** — a validação
para aquele campo é outra e não cabe neste helper.

- [ ] **Step 5: Run test to verify it passes**

Run: `python -m pytest tests/test_onda2_tenant_nao_vaza.py -v`
Expected: PASS

Run: `python -m pytest tests/test_gestao_custo_filho_tenant.py tests/test_arreio_almoxarifado_e_tenant.py -v`
Expected: PASS, mesma contagem de antes.

- [ ] **Step 6: Commit**

```bash
git add utils/fk_do_tenant.py gestao_custos_views.py transporte_views.py views/almoxarifado/itens.py financeiro_views.py tests/test_onda2_tenant_nao_vaza.py
git commit -m "fix(tenant): FK vinda de formulario validada num lugar so

RED: ModuleNotFoundError utils.fk_do_tenant; lancamento gravado na obra alheia

O padrao ja existia em gestao_custos_views.py:550, escrito para fechar um
ataque real. A correcao entrou naquela funcao e nao nas irmas: novo() e
editar() do mesmo arquivo ficaram de fora, e o mesmo buraco existia em
transporte, almoxarifado e financeiro.

Oito chamadores, um helper. A mensagem e generica de proposito: dizer 'obra de
outro tenant' confirmaria a existencia dela."
```

---

### Task 6: O `setattr` cego e os dois irmãos

**Files:**
- Modify: `veiculos_services.py:166-175`, `rdo_editar_sistema.py:218`, `ponto_views.py:777`
- Test: `tests/test_onda2_tenant_nao_vaza.py` (acrescentar)

**Interfaces:**
- Consumes: `fk_do_tenant` (Task 5).
- Produces: nada.

- [ ] **Step 1: Write the failing test**

```python
# ---------------------------------------------------------------------------
# Task 6 — setattr cego e mudança de dono por formulário
# ---------------------------------------------------------------------------

def test_veiculo_nao_muda_de_tenant_por_post():
    """🔴 `veiculos_services.py:167` — `setattr` cego sobre `form.to_dict()`.

    Um POST com `admin_id=99` transferia o veículo E o histórico em cascata.
    """
    import inspect

    import veiculos_services
    fonte = inspect.getsource(veiculos_services)
    assert 'for campo, valor in dados.items():' not in fonte, (
        'ainda há setattr cego sobre o dicionário do formulário')


def test_rdo_nao_muda_de_obra_sem_checagem_de_tenant():
    """🔴 `rdo_editar_sistema.py:218` — `rdo.obra_id = obra_id` cru."""
    import inspect

    import rdo_editar_sistema
    fonte = inspect.getsource(rdo_editar_sistema)
    assert 'rdo.obra_id = obra_id' not in fonte, (
        'obra_id do formulário ainda entra sem validação de tenant')
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_onda2_tenant_nao_vaza.py -k "veiculo or rdo_nao_muda" -v`
Expected: FAIL — os dois padrões ainda estão nos arquivos.

- [ ] **Step 3: Write minimal implementation**

**3a.** Em `veiculos_services.py`, trocar o laço de `:166-175` por uma lista
branca. Acima da função, no módulo:

```python
# Lista BRANCA, nunca negra: o laço antigo era
# `for campo, valor in dados.items(): if hasattr(veiculo, campo)`, e
# `hasattr` diz sim para `admin_id`. Um POST com admin_id=99 transferia o
# veículo e, por cascade, todo o histórico dele para outro tenant.
CAMPOS_EDITAVEIS_VEICULO = frozenset({
    'placa', 'marca', 'modelo', 'ano', 'tipo', 'cor', 'chassi', 'renavam',
    'km_atual', 'km_proxima_manutencao', 'status', 'observacoes',
})
```

E o laço:

```python
            for campo, valor in dados.items():
                if campo not in CAMPOS_EDITAVEIS_VEICULO:
                    continue
                if campo == 'placa' and valor:
                    setattr(veiculo, campo, valor.upper().strip())
                elif campo in ('marca', 'modelo') and valor:
                    setattr(veiculo, campo, valor.strip())
                elif campo in ('ano', 'km_atual', 'km_proxima_manutencao') and valor:
                    setattr(veiculo, campo, int(valor))
                else:
                    setattr(veiculo, campo, valor)
```

⚠️ **Confira a lista contra o modelo antes de escrever** — um campo editável de
verdade que ficar de fora vira bug silencioso de "não salva":

```bash
grep -n "^class Veiculo" -A 40 models.py
```

**3b.** Em `rdo_editar_sistema.py:218`, trocar `rdo.obra_id = obra_id` por:

```python
        # O RDO não pode mudar de dono pelo formulário: `obra_id` vinha cru.
        rdo.obra_id = fk_do_tenant(Obra, obra_id, rdo.admin_id,
                                   campo='Obra', obrigatorio=True)
```

com `from utils.fk_do_tenant import fk_do_tenant` no topo.

**3c.** Em `ponto_views.py:777` (`api_bater_ponto`) e na irmã
`api_registrar_falta`, validar `funcionario_id` e `obra_id` com `fk_do_tenant`
contra `get_admin_id()` antes de passá-los ao serviço. 📖 Hoje o serviço cria o
`RegistroPonto` para funcionário de outro tenant **e devolve o nome dele** na
resposta — o vazamento é de dado, não só de escrita.

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_onda2_tenant_nao_vaza.py -v`
Expected: PASS

Run: `python -m pytest tests/ -k "veiculo or frota or ponto" -m "not browser" -q`
Expected: PASS, mesma contagem de antes.

- [ ] **Step 5: Commit**

```bash
git add veiculos_services.py rdo_editar_sistema.py ponto_views.py tests/test_onda2_tenant_nao_vaza.py
git commit -m "fix(tenant): lista branca no setattr, e RDO/ponto param de mudar de dono

RED: 'for campo, valor in dados.items()' e 'rdo.obra_id = obra_id' no fonte

hasattr(veiculo, 'admin_id') diz sim. Um POST com admin_id=99 transferia o
veiculo e o historico em cascata. Lista BRANCA, nunca negra.

api_bater_ponto criava RegistroPonto para funcionario de outro tenant e
devolvia o NOME dele — vazamento de dado, nao so de escrita."
```

---

### Task 7: As consultas que esqueceram `admin_id`

**Files:**
- Modify: `contabilidade_views.py:1300`, `:1377`; `almoxarifado_utils.py:257`; `ponto_service.py:264`
- Test: `tests/test_onda2_tenant_nao_vaza.py` (acrescentar)

**Interfaces:**
- Consumes: nada.
- Produces: nada. Cada correção é local.

⚠️ **Sem helper aqui de propósito:** as quatro erram de jeitos diferentes — um
join incompleto, um `origem_id` de request, um dedup global e uma configuração
sem escopo. Um helper único as achataria e esconderia o que cada uma quer dizer.

- [ ] **Step 1: Write the failing test**

```python
# ---------------------------------------------------------------------------
# Task 7 — consultas sem admin_id
# ---------------------------------------------------------------------------

def test_dedup_de_nf_e_por_tenant_nao_global():
    """🔴 `almoxarifado_utils.py:257` — `filter_by(xml_hash=...)` sem admin_id.

    Se outro tenant já importou aquele XML, este ouve "já foi importada" e
    NUNCA consegue importar. É o mesmo defeito que `entrada_ja_lancada`
    (`views/almoxarifado/movimentos.py:16`) documenta e evita uma camada
    abaixo.
    """
    import inspect

    import almoxarifado_utils
    fonte = inspect.getsource(almoxarifado_utils)
    assert 'NotaFiscal.query.filter_by(xml_hash=xml_hash)' not in fonte, (
        'dedup de NF ainda é global entre tenants')


def test_join_do_plano_de_contas_leva_admin_id():
    """🔴 `contabilidade_views.py:1300` — join só por `codigo`.

    A PK de `PlanoContas` é composta `(admin_id, codigo)` (`models.py:3266`).
    Cada tenant que possui aquele código soma uma linha duplicada: uma partida
    de R$ 840 em ~300 tenants semeados vira R$ 252.000, com `conta.nome` de um
    plano alheio.
    """
    import inspect

    import contabilidade_views
    fonte = inspect.getsource(contabilidade_views)
    assert 'PartidaContabil.conta_codigo == PlanoContas.codigo)' not in fonte, (
        'o join de PlanoContas ainda ignora admin_id')
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_onda2_tenant_nao_vaza.py -k "dedup or join_do_plano" -v`
Expected: FAIL — os dois padrões ainda estão nos arquivos.

- [ ] **Step 3: Write minimal implementation**

**3a.** `contabilidade_views.py:1300` — acrescentar `admin_id` ao `join`:

```python
        .join(PlanoContas,
              db.and_(PartidaContabil.conta_codigo == PlanoContas.codigo,
                      PartidaContabil.admin_id == PlanoContas.admin_id))
```

**3b.** `contabilidade_views.py:1377` — `origem_id` vem do JSON do request e
`contabilizar_*` carrega por PK pelada, lançando sob o `admin_id` **do
documento**. Validar o documento contra o tenant do usuário antes de contabilizar:

```python
    admin_id = get_tenant_admin_id()
    documento = Modelo.query.filter_by(id=origem_id, admin_id=admin_id).first()
    if not documento:
        return jsonify({'success': False, 'message': 'Documento inválido.'}), 400
```

trocando `Modelo` pelo modelo de cada `tipo`. 📖 Hoje só o achado de
`contabilidade_utils.py:221` (atributos inexistentes, Onda 4) impede a escrita de
aterrissar — **quando a Onda 4 consertar aquilo, este vira exploitável.** Não
adie.

**3c.** `almoxarifado_utils.py:257` — acrescentar o tenant ao dedup:

```python
    ja_existe = NotaFiscal.query.filter_by(
        xml_hash=xml_hash, admin_id=admin_id).first()
```

⚠️ Confirme que `admin_id` está em escopo naquela função; se não estiver, passe-o
como parâmetro em vez de resolvê-lo lá dentro.

**3d.** `ponto_service.py:264` — `ConfiguracaoHorario` lida sem `admin_id`, e
`api_salvar_configuracao` aceita qualquer `obra_id`. Escopar a leitura e validar
o `obra_id` com `fk_do_tenant`.

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_onda2_tenant_nao_vaza.py -v`
Expected: PASS

Run: `python -m pytest tests/test_fase06_d4_plano_contas_por_tenant.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add contabilidade_views.py almoxarifado_utils.py ponto_service.py tests/test_onda2_tenant_nao_vaza.py
git commit -m "fix(tenant): quatro consultas que esqueciam admin_id

RED: o join de PlanoContas e o dedup de NF ainda ignoravam o tenant

PlanoContas tem PK composta (admin_id, codigo): o join so por codigo fazia
uma partida de R\$ 840 virar R\$ 252.000 em ~300 tenants semeados.

O dedup de NF por xml_hash global impedia um tenant de importar um XML que
outro ja tinha importado."
```

---

### Task 8: Falhar fechado, e apagar as armadilhas

**Files:**
- Modify: `vinculos_audit_views.py:38`, `services/cliente_resolver.py:61`, `auth.py:47-68`
- Test: `tests/test_onda2_tenant_nao_vaza.py` (acrescentar)

**Interfaces:**
- Consumes: `utils.tenant.require_tenant`.
- Produces: `auth.get_tenant_filter` e `auth.can_access_data` **deixam de existir**. 🔬 Zero consumidores — conferido em 25/08.

- [ ] **Step 1: Write the failing test**

```python
# ---------------------------------------------------------------------------
# Task 8 — falhar fechado, e apagar as armadilhas
# ---------------------------------------------------------------------------

def test_auditoria_de_vinculos_falha_fechada_sem_tenant():
    """🔴 `vinculos_audit_views.py:38` — `Usuario.admin_id` é nullable.

    Para funcionário sem `admin_id`, todo filtro degradava para
    `admin_id IS NULL` e a página abria sobre linhas órfãs em vez de 403.
    """
    import inspect

    import vinculos_audit_views
    fonte = inspect.getsource(vinculos_audit_views._admin_id)
    assert 'require_tenant' in fonte, (
        '_admin_id ainda devolve get_tenant_admin_id() direto, que pode ser '
        'None e vira admin_id IS NULL')


def test_helpers_mortos_de_auth_foram_apagados():
    """`get_tenant_filter` devolvia None para 'super admin vê tudo' E para
    'não autenticado'. O idiomático `if f: query.filter_by(admin_id=f)`
    serviria as linhas de todo tenant a um chamador anônimo.

    Zero consumidores — a mesma condição que justificou apagar
    `almoxarife_required` e irmãos na Fase 1.
    """
    import auth
    assert not hasattr(auth, 'get_tenant_filter')
    assert not hasattr(auth, 'can_access_data')
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_onda2_tenant_nao_vaza.py -k "falha_fechada or helpers_mortos" -v`
Expected: FAIL — `_admin_id` não usa `require_tenant`, e os dois helpers ainda existem.

- [ ] **Step 3: Confirm the two helpers really have no consumers**

```bash
grep -rn "get_tenant_filter\|can_access_data" --include=*.py --include=*.html . | grep -v __pycache__ | grep -v archive/
```
Expected: só as definições em `auth.py` e o teste novo. **Se aparecer chamador, pare** — apagar deixa de ser a resposta.

- [ ] **Step 4: Write minimal implementation**

**4a.** `vinculos_audit_views.py:38`:

```python
def _admin_id() -> int:
    """O tenant do usuário, ou 403.

    Devolvia `get_tenant_admin_id()` direto, e `Usuario.admin_id` é nullable
    (`models.py:122`): funcionário sem admin_id fazia todo filtro do módulo
    degradar para `admin_id IS NULL`. A página FALHAVA ABERTA sobre linhas
    órfãs, e `marcar_subatividade_revisada` (`:116`) mutava
    `SubatividadeMestre` de tenant NULL. O docstring do módulo promete
    "filtra TUDO por admin_id do usuário corrente".
    """
    from utils.tenant import require_tenant
    return require_tenant()
```

**4b.** `services/cliente_resolver.py:61` — FK explícita inválida passa a
**erguer**, em vez de cair no casamento difuso e criar cliente novo:

```python
    if cliente_id:
        cliente = Cliente.query.filter_by(id=cliente_id,
                                          admin_id=admin_id).first()
        if not cliente:
            # A regra 1 "vence sempre": o chamador (`event_manager.py:1244`)
            # passa `proposta.cliente_id` acreditando nisso. Cair para o
            # casamento difuso aqui criava um Cliente DUPLICADO, sem log, com
            # a obra presa a ele — o que `propostas_consolidated.py:595`
            # documenta querer evitar.
            raise ValueError(
                f'cliente_id={cliente_id} não pertence ao tenant {admin_id}')
        return cliente
```

**4c.** Apagar `get_tenant_filter` e `can_access_data` de `auth.py:47-68`,
deixando no lugar o comentário no mesmo estilo do que já existe no pé do arquivo:

```python
# Onda 2 (25/08) — `get_tenant_filter` e `can_access_data` foram removidos.
# Tinham ZERO consumidores (censo de 25/08), a mesma condição que justificou
# remover `almoxarife_required` e irmãos na Fase 1. E eram armadilha:
# `get_tenant_filter` devolvia None tanto para "super admin vê tudo" quanto
# para "não autenticado", então o idiomático
# `if f: query.filter_by(admin_id=f)` serviria as linhas de TODO tenant a um
# chamador anônimo. Quem precisa de tenant usa `utils.tenant.require_tenant`.
```

⚠️ Se `TipoUsuario` ficar sem uso no import de `auth.py` depois da remoção,
remova-o também — mas confira antes: `grep -n "TipoUsuario" auth.py`.

- [ ] **Step 5: Run test to verify it passes**

Run: `python -m pytest tests/test_onda2_tenant_nao_vaza.py -v`
Expected: PASS

- [ ] **Step 6: Run the full gate**

Run: `bash run_tests.sh --gate`
Expected: **2560 passed, 6 skipped, 201 deselected, 2 xfailed** — ou mais verdes.

⚠️ Se algum teste antes verde falhar, **pare e reporte**. Esta onda muda o
resolvedor de tenant: um teste que dependia do comportamento fantasma é achado
novo, não ruído.

- [ ] **Step 7: Commit**

```bash
git add vinculos_audit_views.py services/cliente_resolver.py auth.py tests/test_onda2_tenant_nao_vaza.py
git commit -m "fix(tenant): falhar fechado, e apagar os dois helpers-armadilha

RED: _admin_id sem require_tenant; auth.get_tenant_filter ainda existia

vinculos_audit._admin_id devolvia get_tenant_admin_id() direto e admin_id e
nullable: a pagina falhava ABERTA sobre linhas orfas em vez de 403.

cliente_resolver caia para casamento difuso quando o cliente_id explicito nao
era do tenant, e criava cliente duplicado sem log.

get_tenant_filter devolvia None para 'super admin ve tudo' E para 'nao
autenticado'. Zero consumidores; apagados."
```

---

## Fecho da onda

- [ ] `bash run_tests.sh --gate` verde, com a contagem registrada.
- [ ] `scripts/medir_tenant_fantasma.py` rodado **em produção**, e o veredito
      registrado aqui. Se houver dado no tenant fantasma, a migration de
      saneamento é **decisão humana** — mover pode colidir com registro que já
      existe no destino.
- [ ] `docs/auditoria/achados-code-review-2026-08-25.md` — marcar os 14 achados
      desta onda.
- [ ] 🔬 Conferir que sobrou **um** resolvedor: `grep -rn "def get_admin_id\|def get_tenant_admin_id\|def get_safe_admin_id" --include=*.py . | grep -v __pycache__`
      deve mostrar `utils/tenant.py` como única fonte de lógica; os demais são cascas.
