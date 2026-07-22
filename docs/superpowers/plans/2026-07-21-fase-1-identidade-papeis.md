# Fase 1 — Fundação de Identidade e Papéis (RBAC + escopo por obra)

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Dar ao sistema uma identidade estável de pessoa (`Usuario` ↔ `Funcionario`) e um eixo de autorização por obra, substituindo as heurísticas de adivinhação de tenant/pessoa que hoje decidem acesso por substring de nome e por "o tenant com mais linhas".

**Architecture:** Dois níveis de papel, não um. O nível de **tenant** continua sendo o enum `TipoUsuario` existente (quem você é na empresa). O nível de **obra** passa a ser uma tabela de vínculo `UsuarioObra(usuario_id, obra_id, papel)` — o que você pode fazer *naquela* obra. As duas perguntas de autorização passam a ter uma única implementação em `utils/autorizacao.py`, em vez das quatro cópias de `admin_required` e das seis heurísticas de e-mail espalhadas hoje. O escopo por obra entra atrás de flag por tenant (desligada por padrão), como o precedente `cronograma_mpp_ativo`, para que o deploy não tire acesso de ninguém no dia em que subir.

**Tech Stack:** Flask 3 + Flask-Login, SQLAlchemy 2 (`models.py`), sistema de migrações próprio numerado (`migrations.py`, `run_migration_safe`), pytest + Playwright (`run_tests.sh --gate`), PostgreSQL.

---

## Contexto verificado no código (leia antes de começar)

Tudo abaixo foi conferido em 2026-07-21 no commit `fb4147b`. Não são suposições.

| Fato | Evidência |
|---|---|
| `Funcionario` **não** tem FK para `Usuario`. A única FK para `usuario.id` é `admin_id`, que é o **tenant**, não a pessoa | `models.py:185-220`, coluna em `models.py:207` |
| `Usuario` também não tem `funcionario_id` | `models.py:28-42` |
| A identidade da pessoa é hoje adivinhada por e-mail, por substring de nome, e por "o tenant com mais funcionários" | `views/rdo.py:88,1660,1690,2052,2585,2687`; `views/employees.py:686-706`; `crud_rdo_completo.py:29-32` |
| Existe mapeamento de e-mail **chumbado em produção** | `crud_rdo_completo.py:30` — `"funcionario@valeverde.com" if current_user.email == "123@gmail.com"` |
| Existe fallback que devolve **o primeiro funcionário do banco inteiro** | `views/employees.py:704-706` |
| Existe `except: return 10` (tenant chumbado) | `views/rdo.py:2594-2596`; idem `propostas_consolidated.py:2469` |
| **Não existe** nenhum escopo por obra. O único eixo é `admin_id` | `utils/tenant.py:15-31`, `multitenant_helper.py:10-43`, `auth.py:47-56` |
| `Obra.responsavel_id` → `funcionario.id`, mas **não governa permissão nenhuma** e **não tem `relationship`** — `obra.responsavel` resolve para `Undefined` nos templates | `models.py:258`; templates `obras.html:266`, `obra_form.html:449-456` |
| `admin_required` existe em **4 definições diferentes** | `auth.py:21` (real), `decorators.py:48` (shim), `contabilidade_views.py:39` (cópia), `folha_pagamento_views.py:22` (cópia) |
| `ALMOXARIFE` é papel **morto**: 0 rotas, 0 templates, 0 testes | `auth.py:70,90,99` — únicas ocorrências |
| `GESTOR_EQUIPES` aparece em 3 lugares, sempre como **sinônimo de ADMIN** | `views/metricas_views.py:44`, `crm_views.py:83`, `templates/base.html:894` |
| 4 rotas de obra/dashboard/perfil estão **sem decorator nenhum** | `views/obras.py:43`, `views/obras.py:1360`, `views/dashboard.py:189`, `views/employees.py:285` |
| Maior migration registrada é a **213** | `migrations.py:4014` |
| Login em teste é injeção de sessão, não POST em `/login` | `tests/test_fase0_autorizacao.py:55-60` |

### Decisões de projeto desta fase

1. **A FK mora em `Usuario.funcionario_id`**, não em `Funcionario.usuario_id`. A pergunta quente é sempre "dado o `current_user`, qual `Funcionario`?" — assim ela é leitura direta, sem join. Além disso `Funcionario` já tem uma FK para `usuario.id` (`admin_id`); uma segunda na mesma tabela seria armadilha de leitura.
2. **Nullable e `UNIQUE`.** Nem todo usuário é funcionário (admin da construtora não é), e nem todo funcionário loga. `UNIQUE` no Postgres admite múltiplos `NULL`, que é exatamente o que queremos.
3. **O backfill nunca cria registro e nunca casa por substring.** Só casa `lower(email)` exato **dentro do mesmo tenant**. O que não casar fica `NULL` e sai num relatório para decisão humana.
4. **`ADMIN` e `SUPER_ADMIN` continuam vendo todas as obras do tenant.** O escopo por obra restringe apenas os demais papéis. Fazer diferente derrubaria o acesso de todo mundo no deploy.
5. **O escopo entra atrás de flag por tenant, desligada por padrão** (`configuracao_empresa.escopo_obra_ativo`), espelhando `cronograma_mpp_ativo` (`migrations.py:4012`). Com a flag desligada o comportamento é idêntico ao de hoje. Isso torna a Fase 1 reversível sem rollback de schema.
6. **Esta fase NÃO reescreve as 177 rotas com `@admin_required` nem as 587 com `@login_required`.** Ela constrói a fundação e a aplica na fatia de obra/RDO. As demais migram nas Fases 2-5, cada uma na sua vez.

### Arquivos que esta fase cria ou altera

| Arquivo | Responsabilidade |
|---|---|
| `utils/identidade.py` | **novo** — resolve `current_user` → `Funcionario`. Único resolver do sistema |
| `utils/autorizacao.py` | **novo** — `obras_visiveis()`, `pode_ver_obra()`, decorator `obra_required` |
| `scripts/backfill_identidade_funcionario.py` | **novo** — casamento `Usuario`↔`Funcionario`, dry-run por padrão |
| `scripts/flag_escopo_obra.py` | **novo** — liga/desliga a flag por tenant |
| `models.py` | `Usuario.funcionario_id`, enum `PapelObra`, modelo `UsuarioObra`, relationship `Obra.responsavel` |
| `migrations.py` | migrations 214, 215, 216 + registro em `migrations_to_run` |
| `auth.py` | remove `almoxarife_required`, `pode_gerenciar_almoxarifado`, `pode_lancar_materiais` (código morto) |
| `decorators.py`, `contabilidade_views.py`, `folha_pagamento_views.py` | consolidam no `auth.admin_required` único |
| `crud_rdo_completo.py`, `views/employees.py`, `views/rdo.py` | trocam heurística pelo resolver |
| `views/obras.py`, `views/dashboard.py` | aplicam `obra_required` e fecham as rotas sem decorator |
| `tests/test_fase1_identidade.py` | **novo** — FK, backfill, invariante de tenant |
| `tests/test_fase1_escopo_obra.py` | **novo** — matriz papel × obra |

---

## Task 1: FK de identidade `Usuario.funcionario_id`

**Files:**
- Modify: `models.py:36` (dentro de `class Usuario`)
- Modify: `migrations.py` (nova função + registro em `migrations_to_run`, após a linha 4014)
- Test: `tests/test_fase1_identidade.py`

- [ ] **Step 1: Escreva o teste que falha**

Crie `tests/test_fase1_identidade.py`:

```python
"""Fase 1 — identidade estável Usuario ↔ Funcionario.

Antes desta fase, "qual Funcionario é o usuário logado" era decidido por
substring de nome (`views/employees.py:686`), por e-mail chumbado
(`crud_rdo_completo.py:30`) e, no último fallback, pelo primeiro
funcionário ativo do banco inteiro (`views/employees.py:704`). Estes
testes travam a FK que substitui tudo isso.
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
from models import Funcionario, TipoUsuario, Usuario

pytestmark = pytest.mark.integration


@pytest.fixture(autouse=True)
def _config():
    app.config['TESTING'] = True
    app.config['WTF_CSRF_ENABLED'] = False
    if not app.secret_key:
        app.secret_key = 'test-fase1-identidade'
    yield


def _admin(nome='Admin'):
    suf = uuid.uuid4().hex[:8]
    u = Usuario(
        username=f'f1a_{suf}', email=f'f1a_{suf}@test.local',
        nome=f'{nome} {suf}',
        password_hash=generate_password_hash('Senha@2026'),
        tipo_usuario=TipoUsuario.ADMIN, ativo=True, versao_sistema='v2',
    )
    db.session.add(u)
    db.session.commit()
    return u


def _funcionario_registro(admin_id, email=None):
    """Cria a linha de RH (Funcionario), sem login."""
    suf = uuid.uuid4().hex[:8]
    f = Funcionario(
        codigo=f'F{suf[:6].upper()}',
        nome=f'Funcionario {suf}',
        cpf=f'{suf[:11]}',
        email=email or f'f1f_{suf}@test.local',
        data_admissao=date(2026, 1, 1),
        admin_id=admin_id,
        ativo=True,
    )
    db.session.add(f)
    db.session.commit()
    return f


def test_usuario_tem_coluna_funcionario_id():
    with app.app_context():
        assert hasattr(Usuario, 'funcionario_id'), (
            'Usuario.funcionario_id não existe — a identidade continua '
            'sendo adivinhada por e-mail/substring')


def test_vinculo_usuario_funcionario_persiste():
    with app.app_context():
        admin = _admin()
        func = _funcionario_registro(admin.id)
        suf = uuid.uuid4().hex[:8]
        u = Usuario(
            username=f'f1u_{suf}', email=f'f1u_{suf}@test.local',
            nome='Operador', password_hash=generate_password_hash('x'),
            tipo_usuario=TipoUsuario.FUNCIONARIO, ativo=True,
            admin_id=admin.id, funcionario_id=func.id,
        )
        db.session.add(u)
        db.session.commit()
        uid, fid = u.id, func.id

    with app.app_context():
        recarregado = db.session.get(Usuario, uid)
        assert recarregado.funcionario_id == fid
        assert recarregado.funcionario is not None
        assert recarregado.funcionario.id == fid


def test_dois_usuarios_nao_compartilham_o_mesmo_funcionario():
    """UNIQUE: uma pessoa de RH tem no máximo um login."""
    from sqlalchemy.exc import IntegrityError

    with app.app_context():
        admin = _admin()
        func = _funcionario_registro(admin.id)
        for i in range(2):
            suf = uuid.uuid4().hex[:8]
            db.session.add(Usuario(
                username=f'f1d{i}_{suf}', email=f'f1d{i}_{suf}@test.local',
                nome=f'Dup {i}', password_hash=generate_password_hash('x'),
                tipo_usuario=TipoUsuario.FUNCIONARIO, ativo=True,
                admin_id=admin.id, funcionario_id=func.id,
            ))
            if i == 0:
                db.session.commit()
        with pytest.raises(IntegrityError):
            db.session.commit()
        db.session.rollback()


def test_funcionario_id_e_opcional():
    """Admin da construtora não é funcionário; não pode ser obrigatório."""
    with app.app_context():
        admin = _admin()
        assert admin.funcionario_id is None
```

- [ ] **Step 2: Rode o teste e confirme que falha**

```bash
python -m pytest tests/test_fase1_identidade.py -v
```

Esperado: FAIL. `test_usuario_tem_coluna_funcionario_id` falha com `AssertionError: Usuario.funcionario_id não existe`; os demais falham com `TypeError: 'funcionario_id' is an invalid keyword argument for Usuario`.

- [ ] **Step 3: Adicione a coluna ao modelo**

Em `models.py`, dentro de `class Usuario`, logo após a linha 36 (`admin_id = ...`), insira:

```python
    # Fase 1 — identidade estável da pessoa. Até 2026-07-21 não existia
    # nenhuma FK ligando o login à linha de RH: `views/employees.py:686`
    # casava por substring do username, `crud_rdo_completo.py:30` tinha um
    # e-mail chumbado, e o último fallback pegava o primeiro funcionário
    # ativo do banco INTEIRO. Nullable porque nem todo usuário é
    # funcionário (o admin da construtora não é) e nem todo funcionário
    # tem login. UNIQUE porque uma pessoa de RH tem no máximo um login —
    # no Postgres UNIQUE admite múltiplos NULL, que é o que queremos.
    # INVARIANTE DE TENANT: o Funcionario apontado tem que ser do mesmo
    # tenant do Usuario. Não dá para expressar como CHECK entre tabelas;
    # é garantido por `utils.identidade.vincular_funcionario` e travado
    # por `tests/test_fase1_identidade.py::test_vinculo_cross_tenant_e_recusado`.
    funcionario_id = db.Column(
        db.Integer,
        db.ForeignKey('funcionario.id', ondelete='SET NULL'),
        unique=True, nullable=True, index=True,
    )
```

E, logo após a linha 41 (`funcionarios = db.relationship(...)`), adicione o relationship:

```python
    funcionario = db.relationship('Funcionario', foreign_keys=[funcionario_id],
                                  backref=db.backref('usuario', uselist=False))
```

- [ ] **Step 4: Escreva a migration 214**

Em `migrations.py`, imediatamente antes de `def executar_migracoes():` (linha 3773), insira:

```python
def migration_214_usuario_funcionario_id():
    """Fase 1 — FK de identidade usuario.funcionario_id.

    Aditiva e idempotente: coluna nullable + UNIQUE + índice. Nenhuma linha
    é preenchida aqui; o casamento é feito pelo
    `scripts/backfill_identidade_funcionario.py`, que roda em dry-run por
    padrão e exige revisão humana dos não-casados.

    ON DELETE SET NULL: apagar a linha de RH não pode apagar o login (nem
    estourar a FK); o usuário fica sem vínculo e aparece no relatório.
    """
    logger.info("[Migration 214] Iniciando — usuario.funcionario_id")

    db.session.execute(text("""
        ALTER TABLE usuario
        ADD COLUMN IF NOT EXISTS funcionario_id INTEGER
    """))
    db.session.commit()

    existe_fk = db.session.execute(text("""
        SELECT 1 FROM information_schema.table_constraints
        WHERE constraint_name = 'fk_usuario_funcionario_id'
          AND table_name = 'usuario'
        LIMIT 1
    """)).fetchone()
    if not existe_fk:
        db.session.execute(text("""
            ALTER TABLE usuario
            ADD CONSTRAINT fk_usuario_funcionario_id
            FOREIGN KEY (funcionario_id) REFERENCES funcionario(id)
            ON DELETE SET NULL
        """))
        db.session.commit()
        logger.info("[Migration 214] FK fk_usuario_funcionario_id criada")

    db.session.execute(text("""
        CREATE UNIQUE INDEX IF NOT EXISTS uq_usuario_funcionario_id
        ON usuario (funcionario_id)
        WHERE funcionario_id IS NOT NULL
    """))
    db.session.commit()

    logger.info("[Migration 214] Concluída com sucesso")
```

- [ ] **Step 5: Registre a migration**

Em `migrations.py`, na lista `migrations_to_run`, logo após a linha 4014 (a entrada `213`), adicione:

```python
            (214, "Fase 1 — FK de identidade usuario.funcionario_id (nullable, UNIQUE parcial)", migration_214_usuario_funcionario_id),
```

- [ ] **Step 6: Aplique a migration e rode os testes**

```bash
python -c "
from app import app
from migrations import executar_migracoes
with app.app_context():
    executar_migracoes()
" 2>&1 | grep -E "214|ERRO|ERROR"
python -m pytest tests/test_fase1_identidade.py -v
```

Esperado: log `[Migration 214] Concluída com sucesso` e os 4 testes PASSAM.

- [ ] **Step 7: Commit**

```bash
git add models.py migrations.py tests/test_fase1_identidade.py
git commit -m "feat(fase1): FK de identidade usuario.funcionario_id

A pessoa por trás do login deixa de ser adivinhada. Coluna nullable com
UNIQUE parcial + migration 214. Nenhuma linha é preenchida aqui — o
backfill é passo separado e revisável."
```

---

## Task 2: Resolver único de identidade (`utils/identidade.py`)

**Files:**
- Create: `utils/identidade.py`
- Test: `tests/test_fase1_identidade.py` (acrescenta)

- [ ] **Step 1: Escreva os testes que falham**

Acrescente ao final de `tests/test_fase1_identidade.py`:

```python
# ---------------------------------------------------------------------------
# Resolver de identidade
# ---------------------------------------------------------------------------

def _cliente_de(user_id):
    c = app.test_client()
    with c.session_transaction() as sess:
        sess['_user_id'] = str(user_id)
        sess['_fresh'] = True
    return c


def test_vincular_funcionario_recusa_cross_tenant():
    """O invariante que a FK sozinha não consegue expressar."""
    from utils.identidade import VinculoInvalido, vincular_funcionario

    with app.app_context():
        admin_a = _admin('A')
        admin_b = _admin('B')
        func_b = _funcionario_registro(admin_b.id)
        suf = uuid.uuid4().hex[:8]
        u_a = Usuario(
            username=f'f1x_{suf}', email=f'f1x_{suf}@test.local',
            nome='Do tenant A', password_hash=generate_password_hash('x'),
            tipo_usuario=TipoUsuario.FUNCIONARIO, ativo=True,
            admin_id=admin_a.id,
        )
        db.session.add(u_a)
        db.session.commit()

        with pytest.raises(VinculoInvalido):
            vincular_funcionario(u_a, func_b)

        db.session.rollback()
        assert db.session.get(Usuario, u_a.id).funcionario_id is None


def test_vincular_funcionario_aceita_mesmo_tenant():
    from utils.identidade import vincular_funcionario

    with app.app_context():
        admin = _admin()
        func = _funcionario_registro(admin.id)
        suf = uuid.uuid4().hex[:8]
        u = Usuario(
            username=f'f1y_{suf}', email=f'f1y_{suf}@test.local',
            nome='Operador', password_hash=generate_password_hash('x'),
            tipo_usuario=TipoUsuario.FUNCIONARIO, ativo=True,
            admin_id=admin.id,
        )
        db.session.add(u)
        db.session.commit()

        vincular_funcionario(u, func)
        db.session.commit()
        assert db.session.get(Usuario, u.id).funcionario_id == func.id


def test_funcionario_do_usuario_devolve_none_sem_vinculo():
    """Falha fechada: sem vínculo é None, NUNCA o primeiro do banco."""
    from utils.identidade import funcionario_do_usuario

    with app.app_context():
        admin = _admin()
        _funcionario_registro(admin.id)  # existe funcionário no banco
        suf = uuid.uuid4().hex[:8]
        u = Usuario(
            username=f'f1z_{suf}', email=f'f1z_{suf}@test.local',
            nome='Sem vinculo', password_hash=generate_password_hash('x'),
            tipo_usuario=TipoUsuario.FUNCIONARIO, ativo=True,
            admin_id=admin.id,
        )
        db.session.add(u)
        db.session.commit()
        uid = u.id

    cliente = _cliente_de(uid)
    with cliente:
        cliente.get('/dashboard')
        assert funcionario_do_usuario() is None
```

- [ ] **Step 2: Rode e confirme a falha**

```bash
python -m pytest tests/test_fase1_identidade.py -v -k "vincular or funcionario_do_usuario"
```

Esperado: FAIL com `ModuleNotFoundError: No module named 'utils.identidade'`.

- [ ] **Step 3: Implemente o resolver**

Crie `utils/identidade.py`:

```python
#!/usr/bin/env python3
"""Resolver único de identidade — SIGE Fase 1.

ANTES desta fase, responder "qual Funcionario é o usuário logado?" tinha
seis implementações diferentes, todas erradas de formas distintas:

  * `views/employees.py:686` — `Funcionario.nome ILIKE '%username%'`, sem
    admin_id: casava pessoa de outro tenant por coincidência de nome.
  * `views/employees.py:693` — fallback para o e-mail literal
    "funcionario@valeverde.com".
  * `views/employees.py:697` — "o tenant com mais funcionários ativos".
  * `views/employees.py:704` — o PRIMEIRO funcionário ativo do banco inteiro.
  * `crud_rdo_completo.py:30` — mapa de e-mail chumbado em produção.
  * `views/rdo.py:2691-2705` — se nada casasse, CRIAVA um Funcionario
    chamado "Administrador Sistema".

Todas foram substituídas por este módulo. A regra aqui é uma só: a
identidade vem da FK `Usuario.funcionario_id` e de mais nada. Sem
vínculo, a resposta é `None` — nunca um palpite.
"""
import logging

from flask_login import current_user

from models import Funcionario, TipoUsuario, Usuario, db

logger = logging.getLogger('identidade')


class VinculoInvalido(ValueError):
    """Tentativa de vincular Usuario a Funcionario de outro tenant."""


def tenant_do_usuario(usuario):
    """Tenant (admin_id) de um Usuario qualquer.

    ADMIN/SUPER_ADMIN são o próprio tenant; os demais pertencem ao
    `admin_id`. Mesma regra de `utils.tenant.get_tenant_admin_id`, mas
    aplicável a um objeto arbitrário, não só ao `current_user`.
    """
    if usuario is None:
        return None
    if usuario.tipo_usuario in (TipoUsuario.ADMIN, TipoUsuario.SUPER_ADMIN):
        return usuario.id
    return usuario.admin_id


def vincular_funcionario(usuario, funcionario):
    """Liga login ↔ linha de RH, recusando cruzamento de tenant.

    A FK sozinha não consegue expressar o invariante "o Funcionario tem
    que ser do mesmo tenant do Usuario" (é uma condição entre duas
    tabelas). Este é o único caminho que deve escrever `funcionario_id`.
    Não faz commit — quem chama decide a transação.
    """
    if funcionario is None:
        usuario.funcionario_id = None
        return usuario

    tenant_usuario = tenant_do_usuario(usuario)
    if tenant_usuario is None or funcionario.admin_id != tenant_usuario:
        raise VinculoInvalido(
            f'Usuario {usuario.id} (tenant {tenant_usuario}) não pode ser '
            f'vinculado ao Funcionario {funcionario.id} '
            f'(tenant {funcionario.admin_id})')

    usuario.funcionario_id = funcionario.id
    return usuario


def funcionario_do_usuario(usuario=None):
    """O `Funcionario` do usuário logado, ou None.

    Falha FECHADA: sem vínculo devolve None. Quem chama decide o que
    fazer — o que não pode voltar a acontecer é adivinhar.
    """
    alvo = usuario
    if alvo is None:
        try:
            if not current_user.is_authenticated:
                return None
        except Exception:
            return None
        alvo = current_user

    funcionario_id = getattr(alvo, 'funcionario_id', None)
    if not funcionario_id:
        return None

    return db.session.get(Funcionario, funcionario_id)


def usuario_do_funcionario(funcionario_id):
    """Caminho inverso: o login de uma pessoa de RH, ou None."""
    if not funcionario_id:
        return None
    return Usuario.query.filter_by(funcionario_id=funcionario_id).first()
```

- [ ] **Step 4: Rode os testes**

```bash
python -m pytest tests/test_fase1_identidade.py -v
```

Esperado: os 7 testes PASSAM.

- [ ] **Step 5: Commit**

```bash
git add utils/identidade.py tests/test_fase1_identidade.py
git commit -m "feat(fase1): resolver unico de identidade com invariante de tenant

utils/identidade.py substitui as seis heuristicas de casamento
Usuario<->Funcionario. Falha fechada: sem vinculo devolve None, nunca
um palpite. vincular_funcionario() recusa cruzamento de tenant."
```

---

## Task 3: Script de backfill do vínculo

**Files:**
- Create: `scripts/backfill_identidade_funcionario.py`
- Test: `tests/test_fase1_identidade.py` (acrescenta)

- [ ] **Step 1: Escreva os testes que falham**

Acrescente ao final de `tests/test_fase1_identidade.py`:

```python
# ---------------------------------------------------------------------------
# Backfill
# ---------------------------------------------------------------------------

def test_backfill_casa_por_email_exato_no_mesmo_tenant():
    from scripts.backfill_identidade_funcionario import executar_backfill

    with app.app_context():
        admin = _admin()
        email = f'casa_{uuid.uuid4().hex[:8]}@test.local'
        func = _funcionario_registro(admin.id, email=email)
        suf = uuid.uuid4().hex[:8]
        u = Usuario(
            username=f'f1b_{suf}', email=email.upper(),  # caixa diferente
            nome='Casa por email', password_hash=generate_password_hash('x'),
            tipo_usuario=TipoUsuario.FUNCIONARIO, ativo=True,
            admin_id=admin.id,
        )
        db.session.add(u)
        db.session.commit()
        uid, fid = u.id, func.id

        relatorio = executar_backfill(dry_run=False, admin_id=admin.id)
        assert relatorio['casados'] >= 1
        assert db.session.get(Usuario, uid).funcionario_id == fid


def test_backfill_nao_casa_entre_tenants():
    from scripts.backfill_identidade_funcionario import executar_backfill

    with app.app_context():
        admin_a = _admin('A')
        admin_b = _admin('B')
        email = f'mesmo_{uuid.uuid4().hex[:8]}@test.local'
        _funcionario_registro(admin_b.id, email=email)  # RH no tenant B
        suf = uuid.uuid4().hex[:8]
        u_a = Usuario(
            username=f'f1c_{suf}', email=email,  # mesmo e-mail, tenant A
            nome='Do tenant A', password_hash=generate_password_hash('x'),
            tipo_usuario=TipoUsuario.FUNCIONARIO, ativo=True,
            admin_id=admin_a.id,
        )
        db.session.add(u_a)
        db.session.commit()
        uid = u_a.id

        executar_backfill(dry_run=False, admin_id=admin_a.id)
        assert db.session.get(Usuario, uid).funcionario_id is None, (
            'backfill casou entre tenants — vazamento de identidade')


def test_backfill_dry_run_nao_escreve():
    from scripts.backfill_identidade_funcionario import executar_backfill

    with app.app_context():
        admin = _admin()
        email = f'dry_{uuid.uuid4().hex[:8]}@test.local'
        _funcionario_registro(admin.id, email=email)
        suf = uuid.uuid4().hex[:8]
        u = Usuario(
            username=f'f1e_{suf}', email=email,
            nome='Dry run', password_hash=generate_password_hash('x'),
            tipo_usuario=TipoUsuario.FUNCIONARIO, ativo=True,
            admin_id=admin.id,
        )
        db.session.add(u)
        db.session.commit()
        uid = u.id

        relatorio = executar_backfill(dry_run=True, admin_id=admin.id)
        assert relatorio['casados'] >= 1  # conta o que casaria
        assert db.session.get(Usuario, uid).funcionario_id is None


def test_backfill_e_idempotente():
    from scripts.backfill_identidade_funcionario import executar_backfill

    with app.app_context():
        admin = _admin()
        email = f'idem_{uuid.uuid4().hex[:8]}@test.local'
        func = _funcionario_registro(admin.id, email=email)
        suf = uuid.uuid4().hex[:8]
        u = Usuario(
            username=f'f1g_{suf}', email=email,
            nome='Idempotente', password_hash=generate_password_hash('x'),
            tipo_usuario=TipoUsuario.FUNCIONARIO, ativo=True,
            admin_id=admin.id,
        )
        db.session.add(u)
        db.session.commit()
        uid, fid = u.id, func.id

        executar_backfill(dry_run=False, admin_id=admin.id)
        segunda = executar_backfill(dry_run=False, admin_id=admin.id)
        assert segunda['casados'] == 0, 'segunda passada não deve recasar'
        assert db.session.get(Usuario, uid).funcionario_id == fid


def test_backfill_recusa_email_ambiguo():
    """Dois funcionários com o mesmo e-mail no tenant: não escolher."""
    from scripts.backfill_identidade_funcionario import executar_backfill

    with app.app_context():
        admin = _admin()
        email = f'ambig_{uuid.uuid4().hex[:8]}@test.local'
        _funcionario_registro(admin.id, email=email)
        _funcionario_registro(admin.id, email=email)
        suf = uuid.uuid4().hex[:8]
        u = Usuario(
            username=f'f1h_{suf}', email=email,
            nome='Ambiguo', password_hash=generate_password_hash('x'),
            tipo_usuario=TipoUsuario.FUNCIONARIO, ativo=True,
            admin_id=admin.id,
        )
        db.session.add(u)
        db.session.commit()
        uid = u.id

        relatorio = executar_backfill(dry_run=False, admin_id=admin.id)
        assert db.session.get(Usuario, uid).funcionario_id is None
        assert any(p['motivo'] == 'ambiguo' for p in relatorio['pendentes'])
```

- [ ] **Step 2: Rode e confirme a falha**

```bash
python -m pytest tests/test_fase1_identidade.py -v -k backfill
```

Esperado: FAIL com `ModuleNotFoundError: No module named 'scripts.backfill_identidade_funcionario'`.

- [ ] **Step 3: Implemente o script**

Crie `scripts/backfill_identidade_funcionario.py`:

```python
#!/usr/bin/env python3
"""Backfill do vínculo Usuario ↔ Funcionario — SIGE Fase 1.

Casa login com linha de RH por e-mail EXATO (case-insensitive) DENTRO do
mesmo tenant. Deliberadamente conservador:

  * não casa por nome, nem por substring, nem por CPF;
  * não cria Funcionario nenhum;
  * não casa se houver mais de um candidato (ambiguidade → humano decide);
  * não toca em quem já tem vínculo;
  * dry-run é o PADRÃO.

Uso:
    python scripts/backfill_identidade_funcionario.py            # dry-run
    python scripts/backfill_identidade_funcionario.py --aplicar
    python scripts/backfill_identidade_funcionario.py --admin-id 10 --aplicar
"""
import argparse
import logging
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy import func as sa_func

from models import Funcionario, TipoUsuario, Usuario, db
from utils.identidade import VinculoInvalido, tenant_do_usuario, vincular_funcionario

logger = logging.getLogger('backfill_identidade')


def executar_backfill(dry_run=True, admin_id=None):
    """Casa Usuario↔Funcionario. Devolve relatório; não imprime nada.

    Args:
        dry_run: se True (padrão), conta o que casaria mas não escreve.
        admin_id: restringe a um tenant. None = todos.

    Returns:
        dict com 'casados' (int), 'ja_vinculados' (int) e
        'pendentes' (lista de {usuario_id, email, motivo}).
    """
    query = Usuario.query.filter(Usuario.funcionario_id.is_(None))
    if admin_id is not None:
        query = query.filter(
            db.or_(Usuario.admin_id == admin_id, Usuario.id == admin_id))

    casados = 0
    pendentes = []

    for usuario in query.all():
        tenant = tenant_do_usuario(usuario)
        if tenant is None:
            pendentes.append({'usuario_id': usuario.id,
                              'email': usuario.email,
                              'motivo': 'sem_tenant'})
            continue

        # ADMIN/SUPER_ADMIN normalmente não são funcionários; ainda assim
        # tentamos casar — uma construtora pequena pode ter o dono
        # cadastrado no RH. Se não casar, não é pendência de verdade.
        if not usuario.email:
            pendentes.append({'usuario_id': usuario.id,
                              'email': None,
                              'motivo': 'sem_email'})
            continue

        candidatos = Funcionario.query.filter(
            sa_func.lower(Funcionario.email) == usuario.email.strip().lower(),
            Funcionario.admin_id == tenant,
        ).all()

        if len(candidatos) == 0:
            pendentes.append({'usuario_id': usuario.id,
                              'email': usuario.email,
                              'motivo': 'sem_correspondencia'})
            continue

        if len(candidatos) > 1:
            pendentes.append({'usuario_id': usuario.id,
                              'email': usuario.email,
                              'motivo': 'ambiguo'})
            continue

        candidato = candidatos[0]

        # Já tomado por outro login? UNIQUE recusaria; reporta em vez de estourar.
        ja_tomado = Usuario.query.filter(
            Usuario.funcionario_id == candidato.id,
            Usuario.id != usuario.id,
        ).first()
        if ja_tomado:
            pendentes.append({'usuario_id': usuario.id,
                              'email': usuario.email,
                              'motivo': 'funcionario_ja_vinculado'})
            continue

        casados += 1
        if not dry_run:
            try:
                vincular_funcionario(usuario, candidato)
            except VinculoInvalido:
                casados -= 1
                pendentes.append({'usuario_id': usuario.id,
                                  'email': usuario.email,
                                  'motivo': 'cross_tenant'})

    if not dry_run:
        db.session.commit()
    else:
        db.session.rollback()

    ja_vinculados = Usuario.query.filter(
        Usuario.funcionario_id.isnot(None)).count()

    return {'casados': casados,
            'ja_vinculados': ja_vinculados,
            'pendentes': pendentes}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--aplicar', action='store_true',
                        help='escreve de fato (padrão é dry-run)')
    parser.add_argument('--admin-id', type=int, default=None,
                        help='restringe a um tenant')
    args = parser.parse_args()

    from app import app
    with app.app_context():
        relatorio = executar_backfill(dry_run=not args.aplicar,
                                      admin_id=args.admin_id)

    modo = 'APLICADO' if args.aplicar else 'DRY-RUN (nada foi escrito)'
    print(f'=== Backfill de identidade — {modo} ===')
    print(f'Vínculos criados .....: {relatorio["casados"]}')
    print(f'Já vinculados no banco: {relatorio["ja_vinculados"]}')
    print(f'Pendentes ............: {len(relatorio["pendentes"])}')

    por_motivo = {}
    for p in relatorio['pendentes']:
        por_motivo.setdefault(p['motivo'], []).append(p)
    for motivo, itens in sorted(por_motivo.items()):
        print(f'  {motivo:.<28} {len(itens)}')

    ambiguos = por_motivo.get('ambiguo', [])
    if ambiguos:
        print('\nAMBÍGUOS (exigem decisão humana):')
        for p in ambiguos[:50]:
            print(f'  usuario_id={p["usuario_id"]} email={p["email"]}')

    return 0


if __name__ == '__main__':
    sys.exit(main())
```

- [ ] **Step 4: Rode os testes**

```bash
python -m pytest tests/test_fase1_identidade.py -v
```

Esperado: os 12 testes PASSAM.

- [ ] **Step 5: Rode o dry-run real e guarde o número**

```bash
python scripts/backfill_identidade_funcionario.py
```

Esperado: relatório impresso. **Não aplique ainda** — o número de `ambiguo` e `sem_correspondencia` é insumo de decisão do Cássio. Anote a saída no commit.

- [ ] **Step 6: Commit**

```bash
git add scripts/backfill_identidade_funcionario.py tests/test_fase1_identidade.py
git commit -m "feat(fase1): backfill do vinculo Usuario<->Funcionario

Casa por e-mail exato dentro do mesmo tenant. Nao casa por nome, nao
cria funcionario, nao resolve ambiguidade sozinho, dry-run por padrao."
```

---

## Task 4: Trocar as heurísticas de identidade pelo resolver

**Files:**
- Modify: `crud_rdo_completo.py:28-33`
- Modify: `views/employees.py:684-706`
- Modify: `views/rdo.py:2685-2705`
- Test: `tests/test_fase1_identidade.py` (acrescenta)

- [ ] **Step 1: Escreva o teste que falha**

Acrescente ao final de `tests/test_fase1_identidade.py`:

```python
# ---------------------------------------------------------------------------
# As heurísticas não podem voltar
# ---------------------------------------------------------------------------

@pytest.mark.parametrize('arquivo,padrao,descricao', [
    ('crud_rdo_completo.py', 'funcionario@valeverde.com',
     'e-mail chumbado no mapeamento de identidade'),
    ('crud_rdo_completo.py', '123@gmail.com',
     'e-mail chumbado no mapeamento de identidade'),
    ('views/employees.py', 'funcionario@valeverde.com',
     'fallback para e-mail literal de um tenant'),
    ('views/employees.py', 'Funcionario.nome.ilike',
     'casamento de pessoa por substring de nome'),
])
def test_heuristica_de_identidade_nao_retorna(arquivo, padrao, descricao):
    caminho = os.path.join(
        os.path.dirname(os.path.dirname(os.path.abspath(__file__))), arquivo)
    with open(caminho, encoding='utf-8') as fh:
        conteudo = fh.read()
    assert padrao not in conteudo, (
        f'{arquivo} voltou a conter "{padrao}" — {descricao}')


def test_dashboard_funcionario_sem_vinculo_nao_pega_estranho():
    """Sem vínculo, a tela não pode mostrar dados de outra pessoa."""
    with app.app_context():
        admin_a = _admin('A')
        admin_b = _admin('B')
        # Tenant B tem muitos funcionários — era o que a heurística
        # "tenant com mais funcionários" escolhia.
        for _ in range(3):
            _funcionario_registro(admin_b.id)
        suf = uuid.uuid4().hex[:8]
        u = Usuario(
            username=f'f1w_{suf}', email=f'f1w_{suf}@test.local',
            nome='Sem vinculo', password_hash=generate_password_hash('x'),
            tipo_usuario=TipoUsuario.FUNCIONARIO, ativo=True,
            admin_id=admin_a.id,
        )
        db.session.add(u)
        db.session.commit()
        uid = u.id
        nomes_b = [f.nome for f in
                   Funcionario.query.filter_by(admin_id=admin_b.id).all()]

    cliente = _cliente_de(uid)
    resposta = cliente.get('/funcionario-dashboard', follow_redirects=True)
    corpo = resposta.get_data(as_text=True)
    for nome in nomes_b:
        assert nome not in corpo, (
            f'dashboard vazou o funcionário "{nome}" do tenant B')
```

- [ ] **Step 2: Rode e confirme a falha**

```bash
python -m pytest tests/test_fase1_identidade.py -v -k "heuristica or estranho"
```

Esperado: FAIL — os 4 `test_heuristica_de_identidade_nao_retorna` falham porque os padrões ainda estão no código.

- [ ] **Step 3: Corrija `crud_rdo_completo.py`**

Substitua as linhas 28-33 (o bloco `# Para funcionários legados, buscar através do email` até o `return funcionario.admin_id`) por:

```python
    # Fase 1 — a identidade vem da FK, não de e-mail chumbado. O bloco
    # anterior mapeava "123@gmail.com" → "funcionario@valeverde.com" e
    # buscava Funcionario por e-mail SEM admin_id, casando pessoa de
    # outro tenant. Ver utils/identidade.py.
    if hasattr(current_user, 'tipo_usuario') and current_user.tipo_usuario.name == 'FUNCIONARIO':
        from utils.identidade import funcionario_do_usuario
        funcionario = funcionario_do_usuario()
        if funcionario:
            return funcionario.admin_id
```

- [ ] **Step 4: Corrija `views/employees.py`**

Substitua as linhas 684-706 (de `# Para sistema de username/senha, buscar funcionário por nome do usuário` até o fim do bloco de fallbacks, imediatamente antes de `# Usar admin_id do funcionário encontrado`) por:

```python
        # Fase 1 — identidade pela FK. A cascata anterior era: substring
        # do username → e-mail literal "funcionario@valeverde.com" → "o
        # tenant com mais funcionários ativos" → o PRIMEIRO funcionário
        # ativo do banco inteiro. Qualquer usuário sem vínculo enxergava
        # os dados de um estranho, possivelmente de outra empresa.
        from utils.identidade import funcionario_do_usuario
        funcionario_atual = funcionario_do_usuario()

        if funcionario_atual is None:
            logger.warning(
                "[EMPLOYEES] usuario_id=%s sem vínculo de Funcionario — "
                "dashboard vazio. Rode scripts/backfill_identidade_funcionario.py",
                current_user.id)
```

- [ ] **Step 5: Corrija `views/rdo.py`**

Localize o bloco em `views/rdo.py:2685-2705` que termina criando um `Funcionario("Administrador Sistema")`. Substitua todo o bloco por:

```python
        # Fase 1 — sem vínculo, devolve None. O código anterior, quando
        # nada casava, CRIAVA um Funcionario chamado "Administrador
        # Sistema" no tenant — poluindo o RH de produção a cada acesso.
        from utils.identidade import funcionario_do_usuario
        return funcionario_do_usuario()
```

- [ ] **Step 6: Rode os testes**

```bash
python -m pytest tests/test_fase1_identidade.py -v
python -m pytest tests/ -m "not browser" -k "rdo or employee" -q
```

Esperado: `test_fase1_identidade.py` todo verde. A segunda linha não deve introduzir falha nova — compare com a baseline anotada antes de começar.

- [ ] **Step 7: Commit**

```bash
git add crud_rdo_completo.py views/employees.py views/rdo.py tests/test_fase1_identidade.py
git commit -m "fix(sec,fase1): identidade da pessoa deixa de ser adivinhada

Remove o e-mail chumbado de crud_rdo_completo, a cascata de fallbacks de
views/employees (substring de nome -> tenant com mais linhas -> primeiro
funcionario do banco) e a criacao automatica de 'Administrador Sistema'
em views/rdo. Todos passam pelo resolver unico."
```

---

## Task 5: Modelo de papel por obra (`PapelObra` + `UsuarioObra`)

**Files:**
- Modify: `models.py` (enum após linha 26; modelo após `class Obra`, ~linha 340)
- Modify: `migrations.py` (migration 215 + registro)
- Test: `tests/test_fase1_escopo_obra.py`

- [ ] **Step 1: Escreva o teste que falha**

Crie `tests/test_fase1_escopo_obra.py`:

```python
"""Fase 1 — escopo por obra.

Até 2026-07-21 o único eixo de isolamento era `admin_id` (tenant): quem
entrava via qualquer papel enxergava TODAS as obras da empresa. Estes
testes travam o segundo eixo — o vínculo usuário↔obra.
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
from models import Cliente, Obra, PapelObra, TipoUsuario, Usuario, UsuarioObra

pytestmark = pytest.mark.integration


@pytest.fixture(autouse=True)
def _config():
    app.config['TESTING'] = True
    app.config['WTF_CSRF_ENABLED'] = False
    if not app.secret_key:
        app.secret_key = 'test-fase1-escopo'
    yield


def _admin(nome='Admin'):
    suf = uuid.uuid4().hex[:8]
    u = Usuario(
        username=f'f1e_{suf}', email=f'f1e_{suf}@test.local',
        nome=f'{nome} {suf}',
        password_hash=generate_password_hash('Senha@2026'),
        tipo_usuario=TipoUsuario.ADMIN, ativo=True, versao_sistema='v2',
    )
    db.session.add(u)
    db.session.commit()
    return u


def _operador(admin_id, nome='Operador'):
    suf = uuid.uuid4().hex[:8]
    u = Usuario(
        username=f'f1o_{suf}', email=f'f1o_{suf}@test.local',
        nome=f'{nome} {suf}', password_hash=generate_password_hash('Senha@2026'),
        tipo_usuario=TipoUsuario.FUNCIONARIO, ativo=True, admin_id=admin_id,
    )
    db.session.add(u)
    db.session.commit()
    return u


def _obra(admin_id, nome='Obra'):
    suf = uuid.uuid4().hex[:8]
    cliente = Cliente(nome=f'Cliente {suf}', admin_id=admin_id)
    db.session.add(cliente)
    db.session.commit()
    o = Obra(
        nome=f'{nome} {suf}', codigo=f'O{suf[:6].upper()}',
        data_inicio=date(2026, 1, 1), admin_id=admin_id,
        cliente_id=cliente.id, ativo=True,
    )
    db.session.add(o)
    db.session.commit()
    return o


def test_papel_obra_tem_os_tres_valores_da_fase_1():
    assert {p.name for p in PapelObra} == {'GESTOR', 'APONTADOR', 'LEITOR'}


def test_vinculo_usuario_obra_persiste():
    with app.app_context():
        admin = _admin()
        obra = _obra(admin.id)
        op = _operador(admin.id)
        v = UsuarioObra(usuario_id=op.id, obra_id=obra.id,
                        papel=PapelObra.GESTOR, admin_id=admin.id)
        db.session.add(v)
        db.session.commit()
        vid = v.id

    with app.app_context():
        recarregado = db.session.get(UsuarioObra, vid)
        assert recarregado.papel == PapelObra.GESTOR
        assert recarregado.ativo is True


def test_usuario_nao_se_vincula_duas_vezes_a_mesma_obra():
    from sqlalchemy.exc import IntegrityError

    with app.app_context():
        admin = _admin()
        obra = _obra(admin.id)
        op = _operador(admin.id)
        db.session.add(UsuarioObra(usuario_id=op.id, obra_id=obra.id,
                                   papel=PapelObra.GESTOR, admin_id=admin.id))
        db.session.commit()
        db.session.add(UsuarioObra(usuario_id=op.id, obra_id=obra.id,
                                   papel=PapelObra.LEITOR, admin_id=admin.id))
        with pytest.raises(IntegrityError):
            db.session.commit()
        db.session.rollback()
```

- [ ] **Step 2: Rode e confirme a falha**

```bash
python -m pytest tests/test_fase1_escopo_obra.py -v
```

Esperado: FAIL na coleção — `ImportError: cannot import name 'PapelObra' from 'models'`.

- [ ] **Step 3: Adicione o enum e o modelo**

Em `models.py`, logo após a definição de `TipoUsuario` (linha 26), insira:

```python
class PapelObra(Enum):
    """Papel de um usuário DENTRO de uma obra específica — Fase 1.

    Ortogonal a `TipoUsuario`, que é o papel no TENANT. Um usuário pode
    ser FUNCIONARIO na empresa e GESTOR de uma obra; outro pode ser
    FUNCIONARIO na empresa e APONTADOR de três obras. ADMIN e
    SUPER_ADMIN não precisam de vínculo: enxergam todas as obras do
    tenant por definição (ver utils/autorizacao.obras_visiveis).

    Deliberadamente três valores. COMPRADOR entra na Fase 3, quando a
    governança de compras existir para consumi-lo — antes disso seria
    permissão sem verbo.
    """
    GESTOR = "gestor"        # responde pela obra: edita, aprova, faz handoff
    APONTADOR = "apontador"  # lança RDO e apontamento; não edita a obra
    LEITOR = "leitor"        # só leitura
```

Em `models.py`, imediatamente após o fim da `class Obra` (antes de `class ServicoObraReal`, ~linha 340), insira:

```python
class UsuarioObra(db.Model):
    """Vínculo usuário ↔ obra — o segundo eixo de autorização (Fase 1).

    Antes desta tabela o sistema tinha um eixo só: `admin_id`. Qualquer
    usuário autenticado de um tenant alcançava todas as obras dele. As
    tabelas que pareciam vínculo não eram: `FuncionarioObrasPonto`
    (models.py:605) governa um DROPDOWN de ponto e falha ABERTA — sem
    configuração, `ponto_views.py:674` devolve todas as obras do tenant;
    `AlocacaoEquipe` (models.py:1522) é planejamento diário.

    Chaveada por `usuario_id` (não `funcionario_id`) porque autorização
    é sobre quem loga. Quem é a pessoa por trás do login é a FK
    `Usuario.funcionario_id`, resolvida em utils/identidade.py.
    """
    __tablename__ = 'usuario_obra'
    __table_args__ = (
        db.UniqueConstraint('usuario_id', 'obra_id', name='uq_usuario_obra'),
        db.Index('ix_usuario_obra_usuario_ativo', 'usuario_id', 'ativo'),
    )

    id = db.Column(db.Integer, primary_key=True)
    usuario_id = db.Column(db.Integer, db.ForeignKey('usuario.id', ondelete='CASCADE'),
                           nullable=False, index=True)
    obra_id = db.Column(db.Integer, db.ForeignKey('obra.id', ondelete='CASCADE'),
                        nullable=False, index=True)
    papel = db.Column(db.Enum(PapelObra), nullable=False,
                      default=PapelObra.LEITOR)
    # admin_id redundante com obra.admin_id, mas presente por consistência
    # com o resto do schema e para permitir filtro de tenant sem join.
    admin_id = db.Column(db.Integer, db.ForeignKey('usuario.id'), nullable=False, index=True)
    ativo = db.Column(db.Boolean, default=True, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    usuario = db.relationship('Usuario', foreign_keys=[usuario_id],
                              backref=db.backref('obras_vinculadas', lazy='dynamic'))
    obra = db.relationship('Obra', foreign_keys=[obra_id],
                           backref=db.backref('usuarios_vinculados', lazy='dynamic'))

    def __repr__(self):
        return f'<UsuarioObra u={self.usuario_id} o={self.obra_id} {self.papel.value}>'
```

- [ ] **Step 4: Escreva a migration 215**

Em `migrations.py`, antes de `def executar_migracoes():`, insira:

```python
def migration_215_usuario_obra():
    """Fase 1 — tabela usuario_obra (escopo por obra).

    Aditiva: nenhuma rota consulta esta tabela até a flag
    `configuracao_empresa.escopo_obra_ativo` (migration 216) ser ligada
    para o tenant. Criar vazia é seguro.
    """
    logger.info("[Migration 215] Iniciando — tabela usuario_obra")

    db.session.execute(text("""
        CREATE TABLE IF NOT EXISTS usuario_obra (
            id SERIAL PRIMARY KEY,
            usuario_id INTEGER NOT NULL REFERENCES usuario(id) ON DELETE CASCADE,
            obra_id INTEGER NOT NULL REFERENCES obra(id) ON DELETE CASCADE,
            papel VARCHAR(20) NOT NULL DEFAULT 'LEITOR',
            admin_id INTEGER NOT NULL REFERENCES usuario(id),
            ativo BOOLEAN NOT NULL DEFAULT TRUE,
            created_at TIMESTAMP DEFAULT NOW()
        )
    """))
    db.session.commit()

    db.session.execute(text("""
        CREATE UNIQUE INDEX IF NOT EXISTS uq_usuario_obra
        ON usuario_obra (usuario_id, obra_id)
    """))
    db.session.execute(text("""
        CREATE INDEX IF NOT EXISTS ix_usuario_obra_usuario_ativo
        ON usuario_obra (usuario_id, ativo)
    """))
    db.session.execute(text("""
        CREATE INDEX IF NOT EXISTS ix_usuario_obra_obra_id
        ON usuario_obra (obra_id)
    """))
    db.session.execute(text("""
        CREATE INDEX IF NOT EXISTS ix_usuario_obra_admin_id
        ON usuario_obra (admin_id)
    """))
    db.session.commit()

    logger.info("[Migration 215] Concluída com sucesso")
```

Registre em `migrations_to_run`, após a entrada `214`:

```python
            (215, "Fase 1 — tabela usuario_obra (escopo por obra: usuario_id, obra_id, papel)", migration_215_usuario_obra),
```

- [ ] **Step 5: Aplique e rode**

```bash
python -c "
from app import app
from migrations import executar_migracoes
with app.app_context():
    executar_migracoes()
" 2>&1 | grep -E "215|ERRO|ERROR"
python -m pytest tests/test_fase1_escopo_obra.py -v
```

Esperado: `[Migration 215] Concluída com sucesso` e os 3 testes PASSAM.

- [ ] **Step 6: Commit**

```bash
git add models.py migrations.py tests/test_fase1_escopo_obra.py
git commit -m "feat(fase1): PapelObra + tabela usuario_obra

Segundo eixo de autorizacao. Ortogonal a TipoUsuario: papel no tenant
continua sendo o enum antigo, papel NA OBRA passa a ser o vinculo.
Tabela nasce vazia e sem consumidor — a leitura entra na 216."
```

---

## Task 6: Flag de rollout por tenant (`escopo_obra_ativo`)

**Files:**
- Modify: `models.py` (`class ConfiguracaoEmpresa`)
- Modify: `migrations.py` (migration 216 + registro)
- Create: `scripts/flag_escopo_obra.py`
- Test: `tests/test_fase1_escopo_obra.py` (acrescenta)

- [ ] **Step 1: Localize o precedente**

```bash
grep -n "cronograma_mpp_ativo" models.py scripts/flag_cronograma_mpp.py | head -20
```

Use a mesma forma. A flag nova é irmã dessa, não um mecanismo novo.

- [ ] **Step 2: Escreva o teste que falha**

Acrescente a `tests/test_fase1_escopo_obra.py`:

```python
# ---------------------------------------------------------------------------
# Flag de rollout
# ---------------------------------------------------------------------------

def test_flag_escopo_obra_nasce_desligada():
    from scripts.flag_escopo_obra import escopo_ativo

    with app.app_context():
        admin = _admin()
        assert escopo_ativo(admin.id) is False, (
            'flag ligada por padrão tiraria acesso de todo mundo no deploy')


def test_flag_escopo_obra_liga_e_desliga():
    from scripts.flag_escopo_obra import definir_flag, escopo_ativo

    with app.app_context():
        admin = _admin()
        definir_flag(admin.id, True)
        assert escopo_ativo(admin.id) is True
        definir_flag(admin.id, False)
        assert escopo_ativo(admin.id) is False
```

- [ ] **Step 3: Rode e confirme a falha**

```bash
python -m pytest tests/test_fase1_escopo_obra.py -v -k flag
```

Esperado: FAIL com `ModuleNotFoundError: No module named 'scripts.flag_escopo_obra'`.

- [ ] **Step 4: Adicione a coluna ao modelo**

Em `models.py`, dentro de `class ConfiguracaoEmpresa`, junto de `cronograma_mpp_ativo`, adicione:

```python
    # Fase 1 — rollout do escopo por obra, por tenant. Desligada por
    # padrão: com FALSE o comportamento é idêntico ao de antes da Fase 1
    # (não-admin enxerga todas as obras do tenant). Ligar só depois de
    # popular usuario_obra para o tenant, senão o pessoal de campo perde
    # acesso. Mesmo padrão de cronograma_mpp_ativo (migration 211).
    escopo_obra_ativo = db.Column(db.Boolean, default=False, nullable=False)
```

- [ ] **Step 5: Escreva a migration 216 e registre**

Em `migrations.py`, antes de `def executar_migracoes():`:

```python
def migration_216_escopo_obra_flag():
    """Fase 1 — flag de rollout configuracao_empresa.escopo_obra_ativo.

    DEFAULT FALSE é deliberado: enquanto estiver desligada, a Fase 1 é
    puramente aditiva e nenhum usuário perde acesso.
    """
    logger.info("[Migration 216] Iniciando — escopo_obra_ativo")
    db.session.execute(text("""
        ALTER TABLE configuracao_empresa
        ADD COLUMN IF NOT EXISTS escopo_obra_ativo BOOLEAN NOT NULL DEFAULT FALSE
    """))
    db.session.commit()
    logger.info("[Migration 216] Concluída com sucesso")
```

Registre após a entrada `215`:

```python
            (216, "Fase 1 — flag de rollout configuracao_empresa.escopo_obra_ativo (default FALSE)", migration_216_escopo_obra_flag),
```

- [ ] **Step 6: Implemente o script de flag**

Crie `scripts/flag_escopo_obra.py`:

```python
#!/usr/bin/env python3
"""Liga/desliga o escopo por obra por tenant — SIGE Fase 1.

Uso:
    python scripts/flag_escopo_obra.py <admin_id> --ligar
    python scripts/flag_escopo_obra.py <admin_id> --desligar
    python scripts/flag_escopo_obra.py <admin_id> --status

ATENÇÃO: ligar sem popular `usuario_obra` para o tenant faz todo
usuário não-ADMIN enxergar zero obras. Rode antes:
    python scripts/backfill_usuario_obra.py --admin-id <id> --aplicar
"""
import argparse
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from models import ConfiguracaoEmpresa, db


def escopo_ativo(admin_id):
    """True se o tenant já usa escopo por obra. Falha para False."""
    if not admin_id:
        return False
    config = ConfiguracaoEmpresa.query.filter_by(admin_id=admin_id).first()
    if config is None:
        return False
    return bool(getattr(config, 'escopo_obra_ativo', False))


def definir_flag(admin_id, ligado):
    """Liga/desliga, criando a ConfiguracaoEmpresa se não existir."""
    config = ConfiguracaoEmpresa.query.filter_by(admin_id=admin_id).first()
    if config is None:
        config = ConfiguracaoEmpresa(admin_id=admin_id)
        db.session.add(config)
    config.escopo_obra_ativo = bool(ligado)
    db.session.commit()
    return config.escopo_obra_ativo


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('admin_id', type=int)
    grupo = parser.add_mutually_exclusive_group(required=True)
    grupo.add_argument('--ligar', action='store_true')
    grupo.add_argument('--desligar', action='store_true')
    grupo.add_argument('--status', action='store_true')
    args = parser.parse_args()

    from app import app
    with app.app_context():
        if args.status:
            print(f'admin_id={args.admin_id} escopo_obra_ativo='
                  f'{escopo_ativo(args.admin_id)}')
            return 0

        from models import Usuario, UsuarioObra
        if args.ligar:
            vinculos = UsuarioObra.query.filter_by(
                admin_id=args.admin_id, ativo=True).count()
            nao_admins = Usuario.query.filter_by(
                admin_id=args.admin_id, ativo=True).count()
            if vinculos == 0 and nao_admins > 0:
                print(f'ABORTADO: o tenant {args.admin_id} tem {nao_admins} '
                      f'usuário(s) não-admin e ZERO vínculos em usuario_obra. '
                      f'Ligar agora tiraria o acesso de todos eles.')
                print('Rode antes: python scripts/backfill_usuario_obra.py '
                      f'--admin-id {args.admin_id} --aplicar')
                return 1

        novo = definir_flag(args.admin_id, args.ligar)
        print(f'admin_id={args.admin_id} escopo_obra_ativo={novo}')
    return 0


if __name__ == '__main__':
    sys.exit(main())
```

- [ ] **Step 7: Aplique e rode**

```bash
python -c "
from app import app
from migrations import executar_migracoes
with app.app_context():
    executar_migracoes()
" 2>&1 | grep -E "216|ERRO|ERROR"
python -m pytest tests/test_fase1_escopo_obra.py -v
```

Esperado: `[Migration 216] Concluída com sucesso` e os 5 testes PASSAM.

- [ ] **Step 8: Commit**

```bash
git add models.py migrations.py scripts/flag_escopo_obra.py tests/test_fase1_escopo_obra.py
git commit -m "feat(fase1): flag de rollout escopo_obra_ativo por tenant

Default FALSE — com a flag desligada o comportamento e identico ao de
antes da fase. O script recusa ligar num tenant sem vinculos, que
tiraria o acesso de todo o pessoal de campo."
```

---

## Task 7: Chokepoint de autorização (`utils/autorizacao.py`)

**Files:**
- Create: `utils/autorizacao.py`
- Test: `tests/test_fase1_escopo_obra.py` (acrescenta)

- [ ] **Step 1: Escreva os testes que falham**

Acrescente a `tests/test_fase1_escopo_obra.py`:

```python
# ---------------------------------------------------------------------------
# Chokepoint de autorização
# ---------------------------------------------------------------------------

def _cliente_de(user_id):
    c = app.test_client()
    with c.session_transaction() as sess:
        sess['_user_id'] = str(user_id)
        sess['_fresh'] = True
    return c


def test_admin_ve_todas_as_obras_do_tenant_mesmo_com_flag_ligada():
    """ADMIN não precisa de vínculo. Regra que evita apagão no deploy."""
    from scripts.flag_escopo_obra import definir_flag
    from utils.autorizacao import obras_visiveis

    with app.app_context():
        admin = _admin()
        o1, o2 = _obra(admin.id, 'Um'), _obra(admin.id, 'Dois')
        definir_flag(admin.id, True)
        ids_esperados = {o1.id, o2.id}
        aid = admin.id

    cliente = _cliente_de(aid)
    with cliente:
        cliente.get('/dashboard')
        visiveis = {o.id for o in obras_visiveis().all()}
    assert ids_esperados <= visiveis


def test_flag_desligada_preserva_o_comportamento_antigo():
    """Não-admin sem vínculo continua vendo o tenant inteiro."""
    from utils.autorizacao import obras_visiveis

    with app.app_context():
        admin = _admin()
        o1 = _obra(admin.id)
        op = _operador(admin.id)  # sem nenhum UsuarioObra
        oid, opid = o1.id, op.id

    cliente = _cliente_de(opid)
    with cliente:
        cliente.get('/dashboard')
        visiveis = {o.id for o in obras_visiveis().all()}
    assert oid in visiveis


def test_flag_ligada_restringe_nao_admin_as_obras_vinculadas():
    from scripts.flag_escopo_obra import definir_flag
    from utils.autorizacao import obras_visiveis

    with app.app_context():
        admin = _admin()
        minha, alheia = _obra(admin.id, 'Minha'), _obra(admin.id, 'Alheia')
        op = _operador(admin.id)
        db.session.add(UsuarioObra(usuario_id=op.id, obra_id=minha.id,
                                   papel=PapelObra.APONTADOR, admin_id=admin.id))
        db.session.commit()
        definir_flag(admin.id, True)
        minha_id, alheia_id, opid = minha.id, alheia.id, op.id

    cliente = _cliente_de(opid)
    with cliente:
        cliente.get('/dashboard')
        visiveis = {o.id for o in obras_visiveis().all()}
    assert minha_id in visiveis
    assert alheia_id not in visiveis, 'obra sem vínculo vazou com a flag ligada'


def test_vinculo_inativo_nao_da_acesso():
    from scripts.flag_escopo_obra import definir_flag
    from utils.autorizacao import pode_ver_obra

    with app.app_context():
        admin = _admin()
        obra = _obra(admin.id)
        op = _operador(admin.id)
        db.session.add(UsuarioObra(usuario_id=op.id, obra_id=obra.id,
                                   papel=PapelObra.LEITOR, admin_id=admin.id,
                                   ativo=False))
        db.session.commit()
        definir_flag(admin.id, True)
        oid, opid = obra.id, op.id

    cliente = _cliente_de(opid)
    with cliente:
        cliente.get('/dashboard')
        assert pode_ver_obra(oid) is False


def test_obra_de_outro_tenant_nunca_e_visivel():
    """O eixo antigo (tenant) continua valendo, flag ou não."""
    from utils.autorizacao import pode_ver_obra

    with app.app_context():
        admin_a, admin_b = _admin('A'), _admin('B')
        obra_b = _obra(admin_b.id)
        op_a = _operador(admin_a.id)
        oid, opid = obra_b.id, op_a.id

    cliente = _cliente_de(opid)
    with cliente:
        cliente.get('/dashboard')
        assert pode_ver_obra(oid) is False


def test_leitor_nao_edita_apontador_nao_edita_gestor_edita():
    from scripts.flag_escopo_obra import definir_flag
    from utils.autorizacao import pode_editar_obra

    with app.app_context():
        admin = _admin()
        obra = _obra(admin.id)
        definir_flag(admin.id, True)
        atores = {}
        for papel in (PapelObra.LEITOR, PapelObra.APONTADOR, PapelObra.GESTOR):
            op = _operador(admin.id, papel.value)
            db.session.add(UsuarioObra(usuario_id=op.id, obra_id=obra.id,
                                       papel=papel, admin_id=admin.id))
            atores[papel] = op.id
        db.session.commit()
        oid = obra.id

    esperado = {PapelObra.LEITOR: False, PapelObra.APONTADOR: False,
                PapelObra.GESTOR: True}
    for papel, uid in atores.items():
        cliente = _cliente_de(uid)
        with cliente:
            cliente.get('/dashboard')
            assert pode_editar_obra(oid) is esperado[papel], (
                f'{papel.name} deveria ter pode_editar_obra='
                f'{esperado[papel]}')


def test_anonimo_nao_ve_obra_nenhuma():
    from utils.autorizacao import obras_visiveis, pode_ver_obra

    with app.app_context():
        admin = _admin()
        obra = _obra(admin.id)
        oid = obra.id

    anon = app.test_client()
    with anon:
        anon.get('/dashboard')
        assert obras_visiveis().count() == 0
        assert pode_ver_obra(oid) is False
```

- [ ] **Step 2: Rode e confirme a falha**

```bash
python -m pytest tests/test_fase1_escopo_obra.py -v -k "obras_visiveis or pode_ver or pode_editar or anonimo or vinculo_inativo or flag_"
```

Esperado: FAIL com `ModuleNotFoundError: No module named 'utils.autorizacao'`.

- [ ] **Step 3: Implemente o chokepoint**

Crie `utils/autorizacao.py`:

```python
#!/usr/bin/env python3
"""Chokepoint de autorização — SIGE Fase 1.

Duas perguntas, uma implementação de cada:

  1. "Que obras este usuário enxerga?"  → obras_visiveis()
  2. "Ele pode X nesta obra?"           → pode_ver_obra / pode_editar_obra

Dois eixos, aplicados em ordem:

  * TENANT (`admin_id`) — o eixo que já existia. Vale SEMPRE, para todo
    mundo, com flag ligada ou desligada. Obra de outro tenant nunca é
    alcançável.
  * OBRA (`usuario_obra`) — o eixo novo. Só entra em vigor quando o
    tenant tem `escopo_obra_ativo = TRUE`, e só restringe quem NÃO é
    ADMIN/SUPER_ADMIN.

A ordem importa: o eixo de tenant é aplicado primeiro e não é
negociável. O escopo por obra só pode ESTREITAR o que o tenant já
permitia — nunca alargar.

Falha fechada: anônimo enxerga zero obras; tenant não resolvido idem.
"""
import logging

from flask_login import current_user

from models import Obra, PapelObra, TipoUsuario, UsuarioObra, db
from utils.tenant import get_tenant_admin_id

logger = logging.getLogger('autorizacao')

# Quem pode editar a obra, por papel na obra. LEITOR e APONTADOR não
# editam: o apontador lança RDO (Fase 5), que é outra permissão.
PAPEIS_QUE_EDITAM_OBRA = (PapelObra.GESTOR,)
PAPEIS_QUE_APONTAM = (PapelObra.GESTOR, PapelObra.APONTADOR)


def _e_admin_do_tenant():
    try:
        if not current_user.is_authenticated:
            return False
    except Exception:
        return False
    return current_user.tipo_usuario in (TipoUsuario.ADMIN,
                                         TipoUsuario.SUPER_ADMIN)


def _escopo_ativo(admin_id):
    """Flag do tenant. Import tardio: scripts/ não é importável no boot."""
    try:
        from scripts.flag_escopo_obra import escopo_ativo
        return escopo_ativo(admin_id)
    except Exception:
        logger.warning('flag escopo_obra_ativo ilegível — assumindo desligada')
        return False


def obras_visiveis(admin_id=None):
    """Query de `Obra` já filtrada pelos dois eixos.

    Devolve uma QUERY, não uma lista — quem chama acrescenta filtros,
    ordenação e paginação. Anônimo recebe uma query que não casa nada
    (e não uma exceção), para que as telas degradem em vazio.
    """
    tenant = admin_id if admin_id is not None else get_tenant_admin_id()

    if tenant is None:
        return Obra.query.filter(db.false())

    query = Obra.query.filter(Obra.admin_id == tenant)

    if _e_admin_do_tenant():
        return query

    if not _escopo_ativo(tenant):
        # Comportamento pré-Fase 1, preservado de propósito.
        return query

    return query.join(
        UsuarioObra, UsuarioObra.obra_id == Obra.id,
    ).filter(
        UsuarioObra.usuario_id == current_user.id,
        UsuarioObra.ativo.is_(True),
    )


def papel_na_obra(obra_id):
    """`PapelObra` do usuário logado nesta obra, ou None.

    ADMIN/SUPER_ADMIN devolvem GESTOR implicitamente — sem precisar de
    linha em usuario_obra.
    """
    try:
        if not current_user.is_authenticated:
            return None
    except Exception:
        return None

    obra = db.session.get(Obra, obra_id)
    tenant = get_tenant_admin_id()
    if obra is None or tenant is None or obra.admin_id != tenant:
        return None

    if _e_admin_do_tenant():
        return PapelObra.GESTOR

    vinculo = UsuarioObra.query.filter_by(
        usuario_id=current_user.id, obra_id=obra_id, ativo=True).first()
    if vinculo:
        return vinculo.papel

    if not _escopo_ativo(tenant):
        # Flag desligada: todo mundo do tenant é LEITOR por omissão.
        return PapelObra.LEITOR

    return None


def pode_ver_obra(obra_id):
    return papel_na_obra(obra_id) is not None


def pode_editar_obra(obra_id):
    return papel_na_obra(obra_id) in PAPEIS_QUE_EDITAM_OBRA


def pode_apontar_na_obra(obra_id):
    """Lançar RDO/apontamento. Consumido de verdade na Fase 5."""
    return papel_na_obra(obra_id) in PAPEIS_QUE_APONTAM
```

- [ ] **Step 4: Rode os testes**

```bash
python -m pytest tests/test_fase1_escopo_obra.py -v
```

Esperado: os 12 testes PASSAM.

- [ ] **Step 5: Commit**

```bash
git add utils/autorizacao.py tests/test_fase1_escopo_obra.py
git commit -m "feat(fase1): chokepoint de autorizacao com dois eixos

utils/autorizacao.py responde 'que obras este usuario enxerga' e 'ele
pode X nesta obra' num lugar so. Eixo de tenant vale sempre; escopo por
obra so estreita, nunca alarga, e so com a flag ligada."
```

---

## Task 8: Decorator `obra_required` e fecho das rotas sem autenticação

**Files:**
- Modify: `utils/autorizacao.py` (acrescenta o decorator)
- Modify: `views/obras.py:43`, `views/obras.py:1360`
- Modify: `views/dashboard.py:189`
- Modify: `views/employees.py:285`
- Test: `tests/test_fase1_escopo_obra.py` (acrescenta)

- [ ] **Step 1: Escreva o teste que falha**

Acrescente a `tests/test_fase1_escopo_obra.py`:

```python
# ---------------------------------------------------------------------------
# Rotas
# ---------------------------------------------------------------------------

ROTAS_QUE_EXIGEM_LOGIN = [
    '/obras',
    '/dashboard',
]


@pytest.mark.parametrize('rota', ROTAS_QUE_EXIGEM_LOGIN)
def test_rota_anonima_exige_login(rota):
    """Rotas que estavam SEM decorator nenhum até a Fase 1."""
    anon = app.test_client()
    r = anon.get(rota, follow_redirects=False)
    assert r.status_code in (302, 401), (
        f'{rota} devolveu {r.status_code} para anônimo — deveria exigir login')
    if r.status_code == 302:
        assert '/login' in r.headers.get('Location', '')


def test_detalhe_de_obra_exige_login():
    with app.app_context():
        admin = _admin()
        obra = _obra(admin.id)
        oid = obra.id

    anon = app.test_client()
    r = anon.get(f'/obras/{oid}', follow_redirects=False)
    assert r.status_code in (302, 401), (
        f'/obras/{oid} devolveu {r.status_code} para anônimo')


def test_detalhe_de_obra_de_outro_tenant_devolve_404():
    """404 e não 403: não vazar sequer a existência da obra."""
    with app.app_context():
        admin_a, admin_b = _admin('A'), _admin('B')
        obra_b = _obra(admin_b.id)
        op_a = _operador(admin_a.id)
        oid, opid = obra_b.id, op_a.id

    cliente = _cliente_de(opid)
    r = cliente.get(f'/obras/{oid}', follow_redirects=False)
    assert r.status_code == 404, (
        f'obra de outro tenant devolveu {r.status_code} — deveria ser 404')


def test_detalhe_de_obra_sem_vinculo_devolve_404_com_flag_ligada():
    from scripts.flag_escopo_obra import definir_flag

    with app.app_context():
        admin = _admin()
        obra = _obra(admin.id)
        op = _operador(admin.id)  # sem vínculo
        definir_flag(admin.id, True)
        oid, opid = obra.id, op.id

    cliente = _cliente_de(opid)
    r = cliente.get(f'/obras/{oid}', follow_redirects=False)
    assert r.status_code == 404
```

- [ ] **Step 2: Rode e confirme a falha**

```bash
python -m pytest tests/test_fase1_escopo_obra.py -v -k "rota_anonima or detalhe_de_obra"
```

Esperado: FAIL — as rotas respondem 200 para anônimo.

- [ ] **Step 3: Acrescente o decorator**

Ao final de `utils/autorizacao.py`, adicione:

```python
def obra_required(papel_minimo=None):
    """Exige login + acesso à obra do `obra_id` da URL.

    Devolve **404** (não 403) quando a obra existe mas está fora do
    alcance, para não vazar a existência de obra de outro tenant. Mesma
    escolha já travada por
    `tests/test_cronograma_permissoes.py::test_admin_de_outro_tenant_recebe_404_sem_vazar_existencia`.

    Args:
        papel_minimo: None → basta ver. `PapelObra.GESTOR` → exige edição.

    Uso:
        @app.route('/obras/<int:obra_id>')
        @obra_required()
        def detalhe(obra_id): ...
    """
    from functools import wraps

    def decorador(f):
        @wraps(f)
        def wrapper(*args, **kwargs):
            from flask import abort, jsonify, redirect, request, url_for

            quer_json = request.path.startswith('/api/') or \
                request.accept_mimetypes.best == 'application/json'

            try:
                autenticado = current_user.is_authenticated
            except Exception:
                autenticado = False
            if not autenticado:
                if quer_json:
                    return jsonify({'error': 'Autenticação necessária'}), 401
                return redirect(url_for('main.login'))

            obra_id = kwargs.get('obra_id') or kwargs.get('id')
            if obra_id is None:
                logger.error('obra_required em rota sem obra_id: %s',
                             request.endpoint)
                abort(500)

            if papel_minimo in PAPEIS_QUE_EDITAM_OBRA:
                permitido = pode_editar_obra(obra_id)
            else:
                permitido = pode_ver_obra(obra_id)

            if not permitido:
                if quer_json:
                    return jsonify({'error': 'Obra não encontrada'}), 404
                abort(404)

            return f(*args, **kwargs)
        return wrapper
    return decorador
```

- [ ] **Step 4: Aplique nas rotas desprotegidas**

Em `views/obras.py`, na rota da linha 43 (`/obras`), acrescente `@login_required` logo abaixo do `@main_bp.route(...)`:

```python
@login_required   # Fase 1 — rota estava SEM decorator nenhum (censo de 2026-07-21)
```

Na mesma rota, troque a montagem da query de obras por `obras_visiveis()`:

```python
    # Fase 1 — a listagem passa pelo chokepoint. Antes montava
    # `Obra.query.filter_by(admin_id=...)` na mão, sem eixo de obra.
    from utils.autorizacao import obras_visiveis
    query = obras_visiveis()
```

Em `views/obras.py:1360-1363`, a função é `detalhes_obra(id)` — **o kwarg é `id`, não `obra_id`**, e ela tem **duas** regras de URL. O decorator já cobre os dois nomes (`kwargs.get('obra_id') or kwargs.get('id')`). A ordem final fica:

```python
# Detalhes de uma obra específica
@main_bp.route('/obras/<int:id>')
@main_bp.route('/obras/detalhes/<int:id>')
@login_required
@obra_required()   # Fase 1 — 404 para obra fora de alcance
@capture_db_errors
def detalhes_obra(id):
```

`obra_required` vem **antes** de `capture_db_errors`: o `abort(404)` da autorização não pode ser engolido e transformado em 500 pelo handler de erro de banco.

Adicione ao topo do arquivo:

```python
from utils.autorizacao import obra_required, obras_visiveis
```

Em `views/dashboard.py:189`, a rota `/dashboard` é seguida de um `@circuit_breaker(...)` de várias linhas. O `@login_required` tem que entrar **entre** os dois, para que o anônimo seja barrado antes da query pesada e não conte como falha no circuit breaker:

```python
@main_bp.route('/dashboard')
@login_required          # Fase 1 — rota estava sem decorator nenhum
@circuit_breaker(
    name="database_heavy_query",
    ...
```

Em `views/employees.py:285` (`/funcionario_perfil/<int:id>`), acrescente `@login_required` e `@admin_required`.

- [ ] **Step 5: Rode os testes**

```bash
python -m pytest tests/test_fase1_escopo_obra.py -v
python -m pytest tests/test_fase0_autorizacao.py -v
```

Esperado: ambos verdes. `test_fase0_autorizacao.py` não pode regredir.

- [ ] **Step 6: Commit**

```bash
git add utils/autorizacao.py views/obras.py views/dashboard.py views/employees.py tests/test_fase1_escopo_obra.py
git commit -m "fix(sec,fase1): decorator obra_required + fecha 4 rotas anonimas

/obras, /obras/<id>, /dashboard e /funcionario_perfil/<id> estavam sem
decorator nenhum. Obra fora de alcance devolve 404, nao 403 — nao vaza
a existencia."
```

---

## Task 9: Backfill dos vínculos de obra

**Files:**
- Create: `scripts/backfill_usuario_obra.py`
- Modify: `models.py` (relationship `Obra.responsavel`)
- Test: `tests/test_fase1_escopo_obra.py` (acrescenta)

- [ ] **Step 1: Escreva o teste que falha**

Acrescente a `tests/test_fase1_escopo_obra.py`:

```python
# ---------------------------------------------------------------------------
# Backfill de vínculos
# ---------------------------------------------------------------------------

def test_obra_tem_relationship_responsavel():
    """`obra.responsavel` resolvia para Undefined nos templates."""
    with app.app_context():
        admin = _admin()
        obra = _obra(admin.id)
        assert hasattr(obra, 'responsavel')
        assert obra.responsavel is None  # sem responsavel_id


def test_backfill_promove_responsavel_da_obra_a_gestor():
    from datetime import date as _date

    from models import Funcionario
    from scripts.backfill_usuario_obra import executar_backfill_obras
    from utils.identidade import vincular_funcionario

    with app.app_context():
        admin = _admin()
        obra = _obra(admin.id)
        suf = uuid.uuid4().hex[:8]
        func = Funcionario(
            codigo=f'R{suf[:6].upper()}', nome=f'Responsavel {suf}',
            cpf=f'{suf[:11]}', email=f'resp_{suf}@test.local',
            data_admissao=_date(2026, 1, 1), admin_id=admin.id, ativo=True)
        db.session.add(func)
        db.session.commit()

        op = _operador(admin.id)
        vincular_funcionario(op, func)
        obra.responsavel_id = func.id
        db.session.commit()
        oid, opid = obra.id, op.id

        executar_backfill_obras(dry_run=False, admin_id=admin.id)

        vinculo = UsuarioObra.query.filter_by(
            usuario_id=opid, obra_id=oid).first()
        assert vinculo is not None, 'responsável não virou GESTOR'
        assert vinculo.papel == PapelObra.GESTOR


def test_backfill_obras_e_idempotente():
    from scripts.backfill_usuario_obra import executar_backfill_obras

    with app.app_context():
        admin = _admin()
        obra = _obra(admin.id)
        op = _operador(admin.id)
        db.session.add(UsuarioObra(usuario_id=op.id, obra_id=obra.id,
                                   papel=PapelObra.GESTOR, admin_id=admin.id))
        db.session.commit()

        relatorio = executar_backfill_obras(dry_run=False, admin_id=admin.id)
        assert relatorio['criados'] == 0


def test_backfill_obras_nao_cruza_tenant():
    from scripts.backfill_usuario_obra import executar_backfill_obras

    with app.app_context():
        admin_a, admin_b = _admin('A'), _admin('B')
        obra_b = _obra(admin_b.id)
        _operador(admin_a.id)
        executar_backfill_obras(dry_run=False, admin_id=admin_a.id)

        vazou = UsuarioObra.query.filter_by(obra_id=obra_b.id).count()
        assert vazou == 0
```

- [ ] **Step 2: Rode e confirme a falha**

```bash
python -m pytest tests/test_fase1_escopo_obra.py -v -k "responsavel or backfill_obras or promove"
```

Esperado: FAIL — `hasattr(obra, 'responsavel')` é False e o módulo não existe.

- [ ] **Step 3: Adicione o relationship que faltava**

Em `models.py`, dentro de `class Obra`, junto dos demais relationships, adicione:

```python
    # Fase 1 — `responsavel_id` existe desde sempre (models.py:258) mas
    # NUNCA teve relationship: `obra.responsavel` resolvia para Undefined
    # em templates/obras.html:266 e obra_form.html:449 (sempre "Sem
    # responsável") e estourava AttributeError na f-string de
    # relatorios_funcionais.py:217.
    responsavel = db.relationship('Funcionario', foreign_keys=[responsavel_id])
```

- [ ] **Step 4: Implemente o backfill de obras**

Crie `scripts/backfill_usuario_obra.py`:

```python
#!/usr/bin/env python3
"""Backfill de `usuario_obra` — SIGE Fase 1.

Popula o escopo por obra a partir do que o sistema JÁ sabe, sem inventar
permissão. Duas fontes, nesta ordem de precedência:

  1. `Obra.responsavel_id` → GESTOR. É a declaração mais forte que
     existe hoje sobre quem responde pela obra. Exige que o Funcionario
     apontado tenha login (`Usuario.funcionario_id`), senão não há a
     quem dar permissão.
  2. `FuncionarioObrasPonto` → APONTADOR. É configuração de dropdown de
     ponto (models.py:605), mas é a única evidência registrada de que
     "esta pessoa trabalha nesta obra". Idem: só vale com login.

O que NÃO faz: não inventa LEITOR para todo mundo, não usa
`AlocacaoEquipe` (planejamento diário, muda toda semana), não cria
usuário nem funcionário.

Uso:
    python scripts/backfill_usuario_obra.py                      # dry-run
    python scripts/backfill_usuario_obra.py --aplicar
    python scripts/backfill_usuario_obra.py --admin-id 10 --aplicar
"""
import argparse
import logging
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from models import (FuncionarioObrasPonto, Obra, PapelObra, Usuario,
                    UsuarioObra, db)
from utils.identidade import tenant_do_usuario

logger = logging.getLogger('backfill_usuario_obra')


def _vincular(usuario_id, obra_id, papel, admin_id, existentes):
    """Cria o vínculo se ainda não houver. Não faz commit."""
    if (usuario_id, obra_id) in existentes:
        return False
    db.session.add(UsuarioObra(usuario_id=usuario_id, obra_id=obra_id,
                               papel=papel, admin_id=admin_id, ativo=True))
    existentes.add((usuario_id, obra_id))
    return True


def executar_backfill_obras(dry_run=True, admin_id=None):
    """Popula usuario_obra. Devolve relatório; não imprime nada.

    Returns:
        dict com 'criados' (int), 'gestores' (int), 'apontadores' (int) e
        'obras_sem_gestor' (lista de obra_id).
    """
    obras_q = Obra.query
    if admin_id is not None:
        obras_q = obras_q.filter(Obra.admin_id == admin_id)
    obras = obras_q.all()

    existentes = {
        (v.usuario_id, v.obra_id)
        for v in UsuarioObra.query.all()
    }

    criados = gestores = apontadores = 0
    obras_sem_gestor = []

    for obra in obras:
        tem_gestor = False

        # Fonte 1 — o responsável declarado da obra vira GESTOR.
        if obra.responsavel_id:
            usuario = Usuario.query.filter_by(
                funcionario_id=obra.responsavel_id).first()
            # O login tem que ser do MESMO tenant da obra. `tenant_do_usuario`
            # resolve as duas formas (ADMIN é o próprio id; os demais usam
            # admin_id), evitando a comparação torta que isso viraria aqui.
            if usuario is not None and tenant_do_usuario(usuario) == obra.admin_id:
                if _vincular(usuario.id, obra.id, PapelObra.GESTOR,
                             obra.admin_id, existentes):
                    criados += 1
                    gestores += 1
                tem_gestor = True

        # Fonte 2 — quem bate ponto na obra vira APONTADOR.
        configs = FuncionarioObrasPonto.query.filter_by(
            obra_id=obra.id, ativo=True).all()
        for config in configs:
            usuario = Usuario.query.filter_by(
                funcionario_id=config.funcionario_id).first()
            if usuario is None:
                continue
            if _vincular(usuario.id, obra.id, PapelObra.APONTADOR,
                         obra.admin_id, existentes):
                criados += 1
                apontadores += 1

        if not tem_gestor:
            obras_sem_gestor.append(obra.id)

    if dry_run:
        db.session.rollback()
    else:
        db.session.commit()

    return {'criados': criados, 'gestores': gestores,
            'apontadores': apontadores,
            'obras_sem_gestor': obras_sem_gestor}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--aplicar', action='store_true')
    parser.add_argument('--admin-id', type=int, default=None)
    args = parser.parse_args()

    from app import app
    with app.app_context():
        relatorio = executar_backfill_obras(dry_run=not args.aplicar,
                                            admin_id=args.admin_id)

    modo = 'APLICADO' if args.aplicar else 'DRY-RUN (nada foi escrito)'
    print(f'=== Backfill de usuario_obra — {modo} ===')
    print(f'Vínculos criados ...: {relatorio["criados"]}')
    print(f'  como GESTOR ......: {relatorio["gestores"]}')
    print(f'  como APONTADOR ...: {relatorio["apontadores"]}')
    print(f'Obras sem gestor ...: {len(relatorio["obras_sem_gestor"])}')
    if relatorio['obras_sem_gestor']:
        print('\nATENÇÃO: estas obras ficarão sem GESTOR. Ligar a flag do '
              'tenant sem resolvê-las deixa a obra sem ninguém que a edite '
              '(além do ADMIN):')
        print('  obra_id: ' + ', '.join(
            str(i) for i in relatorio['obras_sem_gestor'][:50]))
    return 0


if __name__ == '__main__':
    sys.exit(main())
```

- [ ] **Step 5: Rode os testes**

```bash
python -m pytest tests/test_fase1_escopo_obra.py -v
```

Esperado: todos PASSAM.

- [ ] **Step 6: Rode o dry-run real**

```bash
python scripts/backfill_usuario_obra.py
```

Esperado: relatório. O número de **obras sem gestor** é decisão do Cássio antes de ligar qualquer flag.

- [ ] **Step 7: Commit**

```bash
git add scripts/backfill_usuario_obra.py models.py tests/test_fase1_escopo_obra.py
git commit -m "feat(fase1): backfill de usuario_obra + relationship Obra.responsavel

Promove Obra.responsavel_id a GESTOR e FuncionarioObrasPonto a
APONTADOR. So vale para quem tem login. Reporta as obras que ficariam
sem gestor. Adiciona o relationship que faltava — obra.responsavel
resolvia para Undefined nos templates desde sempre."
```

---

## Task 10: Consolidar os quatro `admin_required` e retirar o papel morto

**Files:**
- Modify: `contabilidade_views.py:39-52`
- Modify: `folha_pagamento_views.py:22-35`
- Modify: `auth.py:70-99` (remove código morto)
- Test: `tests/test_fase1_identidade.py` (acrescenta)

- [ ] **Step 1: Escreva o teste que falha**

Acrescente ao final de `tests/test_fase1_identidade.py`:

```python
# ---------------------------------------------------------------------------
# Consolidação dos decorators
# ---------------------------------------------------------------------------

def test_existe_uma_unica_definicao_de_admin_required():
    """Havia 4: auth.py:21, decorators.py:48, e cópias locais em
    contabilidade_views.py:39 e folha_pagamento_views.py:22."""
    import subprocess

    raiz = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    saida = subprocess.run(
        ['grep', '-rn', '--include=*.py', '^def admin_required', '.'],
        cwd=raiz, capture_output=True, text=True).stdout
    definicoes = [linha for linha in saida.splitlines()
                  if './archive/' not in linha
                  and './entrega_baia_rev10/' not in linha]
    assert len(definicoes) == 1, (
        f'esperava 1 definição de admin_required, achei '
        f'{len(definicoes)}:\n' + '\n'.join(definicoes))
    assert definicoes[0].startswith('./auth.py:'), (
        f'a definição canônica deve morar em auth.py, está em {definicoes[0]}')


@pytest.mark.parametrize('nome', [
    'almoxarife_required',
    'pode_gerenciar_almoxarifado',
    'pode_lancar_materiais',
])
def test_codigo_morto_de_almoxarife_foi_removido(nome):
    """0 rotas, 0 templates, 0 testes usavam — mas sugeriam RBAC que não existe."""
    import auth
    assert not hasattr(auth, nome), (
        f'auth.{nome} continua existindo — 0 consumidores no censo de '
        f'2026-07-21, e sugere um controle de acesso que o almoxarifado '
        f'não tem (roda com @login_required puro)')
```

- [ ] **Step 2: Rode e confirme a falha**

```bash
python -m pytest tests/test_fase1_identidade.py -v -k "admin_required or codigo_morto"
```

Esperado: FAIL — 3 definições de `admin_required` (`auth.py`, `contabilidade_views.py`, `folha_pagamento_views.py`) e os 3 símbolos mortos presentes.

- [ ] **Step 3: Remova a cópia de `contabilidade_views.py`**

Apague a função local `admin_required` (linhas 39-52) e, no lugar do bloco de imports do topo, acrescente:

```python
# Fase 1 — usa a definição canônica. Havia uma cópia local idêntica aqui,
# uma em folha_pagamento_views.py e um shim em decorators.py.
from auth import admin_required
```

- [ ] **Step 4: Remova a cópia de `folha_pagamento_views.py`**

Apague a função local `admin_required` (linhas 22-35) e acrescente no topo:

```python
# Fase 1 — usa a definição canônica (ver contabilidade_views.py).
from auth import admin_required
```

- [ ] **Step 5: Remova o código morto de `auth.py`**

Apague as linhas 70-99 inteiras (`almoxarife_required`, `pode_gerenciar_almoxarifado`, `pode_lancar_materiais`) e deixe no lugar:

```python
# Fase 1 — `almoxarife_required`, `pode_gerenciar_almoxarifado` e
# `pode_lancar_materiais` foram removidos. Tinham ZERO consumidores no
# censo de 2026-07-21 (0 rotas, 0 templates, 0 testes): o módulo de
# almoxadofado inteiro roda com @login_required puro. Mantê-los sugeria
# um controle de acesso que não existe. Se o almoxarifado precisar de
# papel próprio, ele entra como PapelObra na Fase 3 (compras), com rota
# que o consuma.
```

Corrija a grafia ao colar: `almoxarifado`, não `almoxadofado`.

- [ ] **Step 6: Verifique que nada quebrou e rode o gate**

```bash
grep -rn "almoxarife_required\|pode_gerenciar_almoxarifado\|pode_lancar_materiais" --include=*.py --include=*.html . | grep -v archive | grep -v entrega_baia
python -m pytest tests/test_fase1_identidade.py -v
bash run_tests.sh --gate 2>&1 | tail -30
```

Esperado: o `grep` não devolve nada fora de `tests/`. Os testes da Fase 1 passam. O gate não regride em relação à baseline anotada no início.

- [ ] **Step 7: Commit**

```bash
git add auth.py contabilidade_views.py folha_pagamento_views.py tests/test_fase1_identidade.py
git commit -m "refactor(fase1): uma unica definicao de admin_required

Remove as copias locais de contabilidade_views e folha_pagamento_views
(42 rotas passam a usar auth.admin_required) e o codigo morto de
almoxarife em auth.py — 0 consumidores, sugeria RBAC inexistente."
```

---

## Task 11: Matriz de regressão e runbook de rollout

**Files:**
- Create: `tests/test_fase1_matriz_autorizacao.py`
- Create: `docs/fase-1-rollout.md`

- [ ] **Step 1: Escreva a matriz**

Crie `tests/test_fase1_matriz_autorizacao.py`:

```python
"""Fase 1 — matriz papel × obra × ação.

Uma tabela só, para que a regressão apareça como célula errada e não
como teste solto. Mesmo espírito de
`tests/test_cronograma_permissoes.py::_rotas`.
"""
import os
import sys
import uuid
from datetime import date

import pytest
from werkzeug.security import generate_password_hash

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import main  # noqa: F401
from app import app, db
from models import (Cliente, Obra, PapelObra, TipoUsuario, Usuario,
                    UsuarioObra)

pytestmark = pytest.mark.integration


@pytest.fixture(autouse=True)
def _config():
    app.config['TESTING'] = True
    app.config['WTF_CSRF_ENABLED'] = False
    if not app.secret_key:
        app.secret_key = 'test-fase1-matriz'
    yield


def _usuario(tipo, admin_id=None, nome='U'):
    suf = uuid.uuid4().hex[:8]
    u = Usuario(
        username=f'm1_{suf}', email=f'm1_{suf}@test.local', nome=f'{nome} {suf}',
        password_hash=generate_password_hash('Senha@2026'),
        tipo_usuario=tipo, ativo=True, admin_id=admin_id, versao_sistema='v2')
    db.session.add(u)
    db.session.commit()
    return u


def _obra_de(admin_id):
    suf = uuid.uuid4().hex[:8]
    cliente = Cliente(nome=f'Cli {suf}', admin_id=admin_id)
    db.session.add(cliente)
    db.session.commit()
    o = Obra(nome=f'Obra {suf}', codigo=f'M{suf[:6].upper()}',
             data_inicio=date(2026, 1, 1), admin_id=admin_id,
             cliente_id=cliente.id, ativo=True)
    db.session.add(o)
    db.session.commit()
    return o


def _cliente_de(user_id):
    c = app.test_client()
    with c.session_transaction() as sess:
        sess['_user_id'] = str(user_id)
        sess['_fresh'] = True
    return c


# ator → (ver, editar, apontar) na obra do PRÓPRIO tenant, flag LIGADA
MATRIZ = {
    'admin':            (True,  True,  True),
    'gestor':           (True,  True,  True),
    'apontador':        (True,  False, True),
    'leitor':           (True,  False, False),
    'sem_vinculo':      (False, False, False),
    'admin_outro':      (False, False, False),
    'anonimo':          (False, False, False),
}


@pytest.fixture(scope='module')
def cenario():
    """Um tenant, uma obra, um ator de cada tipo. Devolve só ids."""
    with app.app_context():
        from scripts.flag_escopo_obra import definir_flag

        admin = _usuario(TipoUsuario.ADMIN, nome='Dono')
        outro = _usuario(TipoUsuario.ADMIN, nome='Concorrente')
        obra = _obra_de(admin.id)

        atores = {'admin': admin.id, 'admin_outro': outro.id, 'anonimo': None}
        for chave, papel in (('gestor', PapelObra.GESTOR),
                             ('apontador', PapelObra.APONTADOR),
                             ('leitor', PapelObra.LEITOR)):
            u = _usuario(TipoUsuario.FUNCIONARIO, admin_id=admin.id, nome=chave)
            db.session.add(UsuarioObra(usuario_id=u.id, obra_id=obra.id,
                                       papel=papel, admin_id=admin.id))
            atores[chave] = u.id
        atores['sem_vinculo'] = _usuario(
            TipoUsuario.FUNCIONARIO, admin_id=admin.id, nome='orfao').id
        db.session.commit()
        definir_flag(admin.id, True)

        return {'obra_id': obra.id, 'atores': atores}


@pytest.mark.parametrize('ator', sorted(MATRIZ))
def test_matriz_de_autorizacao(cenario, ator):
    from utils.autorizacao import (pode_apontar_na_obra, pode_editar_obra,
                                   pode_ver_obra)

    esperado_ver, esperado_editar, esperado_apontar = MATRIZ[ator]
    user_id = cenario['atores'][ator]
    obra_id = cenario['obra_id']

    cliente = app.test_client() if user_id is None else _cliente_de(user_id)
    with cliente:
        cliente.get('/dashboard')
        assert pode_ver_obra(obra_id) is esperado_ver, (
            f'{ator}: pode_ver_obra deveria ser {esperado_ver}')
        assert pode_editar_obra(obra_id) is esperado_editar, (
            f'{ator}: pode_editar_obra deveria ser {esperado_editar}')
        assert pode_apontar_na_obra(obra_id) is esperado_apontar, (
            f'{ator}: pode_apontar_na_obra deveria ser {esperado_apontar}')


@pytest.mark.parametrize('ator', sorted(MATRIZ))
def test_detalhe_da_obra_respeita_a_matriz(cenario, ator):
    esperado_ver = MATRIZ[ator][0]
    user_id = cenario['atores'][ator]
    obra_id = cenario['obra_id']

    cliente = app.test_client() if user_id is None else _cliente_de(user_id)
    r = cliente.get(f'/obras/{obra_id}', follow_redirects=False)

    if esperado_ver:
        assert r.status_code == 200, f'{ator}: esperava 200, veio {r.status_code}'
    elif user_id is None:
        assert r.status_code in (302, 401), f'{ator}: anônimo veio {r.status_code}'
    else:
        assert r.status_code == 404, (
            f'{ator}: esperava 404 (sem vazar existência), veio {r.status_code}')
```

- [ ] **Step 2: Rode a matriz**

```bash
python -m pytest tests/test_fase1_matriz_autorizacao.py -v
```

Esperado: 14 testes PASSAM (7 atores × 2 famílias).

- [ ] **Step 3: Escreva o runbook**

Crie `docs/fase-1-rollout.md`:

```markdown
# Fase 1 — runbook de rollout

A Fase 1 é aditiva enquanto `escopo_obra_ativo` estiver `FALSE`. Todo o
risco está em **ligar a flag**. A ordem abaixo não é sugestão.

## Por tenant, nesta ordem

1. **Backfill de identidade em dry-run**

       python scripts/backfill_identidade_funcionario.py --admin-id <id>

   Leia `ambiguo` e `sem_correspondencia`. Ambíguo é e-mail repetido no
   RH — resolver no cadastro antes de seguir.

2. **Aplicar a identidade**

       python scripts/backfill_identidade_funcionario.py --admin-id <id> --aplicar

3. **Backfill de vínculos de obra em dry-run**

       python scripts/backfill_usuario_obra.py --admin-id <id>

   O número que importa é **obras sem gestor**. Cada uma dessas obras,
   com a flag ligada, fica sem ninguém que a edite além do ADMIN.

4. **Resolver as obras sem gestor.** Preencher `Obra.responsavel_id`
   com um funcionário que tenha login, ou criar o vínculo à mão.

5. **Aplicar os vínculos**

       python scripts/backfill_usuario_obra.py --admin-id <id> --aplicar

6. **Ligar a flag**

       python scripts/flag_escopo_obra.py <id> --ligar

   O script recusa se `usuario_obra` estiver vazia para o tenant.

## Rollback

Um comando, sem tocar em schema:

    python scripts/flag_escopo_obra.py <id> --desligar

Volta ao comportamento pré-Fase 1 imediatamente. As tabelas e as FKs
continuam lá, inertes.

## O que a Fase 1 deliberadamente NÃO fez

- Não migrou as 177 rotas `@admin_required` nem as 587 `@login_required`
  para o novo eixo. Elas continuam com autorização só de tenant. Cada
  fase seguinte migra a sua fatia.
- Não tocou nos dois portais por token (`portal_obras_views.py`,
  `propostas_consolidated.py`), que continuam sendo um sistema de
  identidade paralelo, sem expiração e sem escopo de ação. Cinco rotas
  POST que mutam estado seguem alcançáveis só com a URL. Isso é dívida
  conhecida — candidata natural à Fase 9a, junto da assinatura de
  medição.
- Não resolveu `GESTOR_EQUIPES`, que segue sendo sinônimo de ADMIN em
  `views/metricas_views.py:44` e `crm_views.py:83`.
- Não criou `PapelObra.COMPRADOR`. Entra na Fase 3, com rota que o use.
```

- [ ] **Step 4: Rode a suíte inteira do gate**

```bash
bash run_tests.sh --gate 2>&1 | tail -40
```

Esperado: nenhuma regressão contra a baseline anotada no início da fase. Anote o número final de passados/falhados.

- [ ] **Step 5: Commit**

```bash
git add tests/test_fase1_matriz_autorizacao.py docs/fase-1-rollout.md
git commit -m "test(fase1): matriz papel x obra x acao + runbook de rollout

7 atores x 3 acoes numa tabela so, mais o teste de que /obras/<id>
devolve 404 (nao 403) para quem nao alcanca. Runbook documenta a ordem
obrigatoria do backfill e o rollback de um comando."
```

---

## Encerramento da fase

- [ ] **Atualize `ESTADO-ATUAL.md`:** marque a Fase 1 como concluída na tabela de fases; remova a armadilha nº 4 ("`Funcionario` não tem FK para `Usuario`") e substitua por um apontamento para `docs/fase-1-rollout.md`; atualize a contagem de rotas sem autenticação (40 → 36).
- [ ] **Verifique que a Fase 2 está destravada:** `Obra.responsavel_id` agora tem relationship e um GESTOR correspondente em `usuario_obra` — é o que o handoff do GP da Fase 2 vai consumir.
- [ ] **Não ligue nenhuma flag em produção** sem os dry-runs dos passos 1 e 3 do runbook revisados pelo Cássio.

## Autorrevisão feita sobre este plano

- **Cobertura:** os quatro pilares do escopo original ("FK Funcionario→Usuario, modelo de papéis, escopo por obra, decorators reais, migração dos admins existentes, suíte de isolamento") têm tarefa: 1-4 (identidade), 5 (papéis), 6-8 (escopo + decorator), 3 e 9 (migração dos existentes), 11 (suíte). O item "decorators reais substituindo os no-op" foi ajustado: os no-op **já foram corrigidos na Fase 0** (`decorators.py:48-76` hoje delega para a implementação real) — o que sobrou de verdade era a **duplicação** em quatro lugares, tratada na Task 10.
- **Risco maior identificado:** ligar o escopo derrubaria acesso de campo. Endereçado com a flag por tenant (Task 6), o guard no script que recusa ligar sem vínculos, e o `test_flag_desligada_preserva_o_comportamento_antigo`.
- **Consistência de nomes:** `funcionario_do_usuario`, `vincular_funcionario`, `tenant_do_usuario` (utils/identidade.py); `obras_visiveis`, `papel_na_obra`, `pode_ver_obra`, `pode_editar_obra`, `pode_apontar_na_obra`, `obra_required` (utils/autorizacao.py); `executar_backfill` (identidade) vs `executar_backfill_obras` (vínculos) — nomes distintos de propósito, os dois scripts são importados no mesmo teste; `escopo_ativo`/`definir_flag` (scripts/flag_escopo_obra.py). Conferidos contra todos os usos nos testes.
- **Números de migration:** 214, 215, 216 — a maior registrada hoje é 213 (`migrations.py:4014`). Confira antes de aplicar, caso outra branch tenha avançado.
- **Assinaturas conferidas no código, não presumidas:** `detalhes_obra` recebe `id` (não `obra_id`) e tem duas regras de URL — o decorator aceita os dois nomes de kwarg de propósito; `/dashboard` tem um `@circuit_breaker` que exige posição específica do `@login_required`; `Cliente` só precisa de `nome` + `admin_id` (`models.py:2703-2711`), como as fixtures assumem; `cronograma_mpp_ativo` mora em `models.py:3620` e é o molde da flag nova.
