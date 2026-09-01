# As Decisões Viram Código — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Executar o trabalho de código que as 13 decisões respondidas em 01/09 destravaram e que **nenhum plano existente cobre** — os dois defeitos de produção do a09, a conta da despesa geral, o elo da rota legada do RDO, o rateio de encargos atrás de flag, o SFace nativo, as 18 rotas mortas de veículos, a falha fechada do tenant e a convergência dos resolvedores — e, ao fim, registrar por escrito o destino de tudo o que este plano deliberadamente NÃO cobre.

**Architecture:** Este plano é o complemento de execução de `2026-08-31-fecho-do-que-esta-aberto.md` — que continua sendo o sequenciador das frentes grandes (Onda 4, Resgate da Espinha, issues, índice+merge) — e obedece à mesma regra dele: **não duplicar tasks que já vivem em outro plano**. Tudo aqui é trabalho órfão: nasceu das decisões de 01/09 ou foi medido sem nunca ganhar dono. As tasks são independentes entre si, exceto onde o bloco "Interfaces" diz o contrário; a ordem escolhida põe primeiro o que corrompe dado de cliente hoje (Tasks 2 e 3).

**Tech Stack:** Flask, SQLAlchemy 2.0.41, PostgreSQL, pytest, OpenCV 4.x.

**Spec:** `docs/superpowers/plans/2026-09-01-decisoes-respondidas.md` (as 13 respostas, com a evidência de cada uma) sobre `docs/superpowers/plans/2026-08-31-fecho-do-que-esta-aberto.md` (o sequenciamento vigente). A lista completa dos 52 itens em aberto está na conversa que originou os dois; o rastro de evidência dos defeitos é `docs/auditoria/achados-code-review-2026-08-25.md`.

## Global Constraints

- **Gate:** `bash run_tests.sh --gate` (= `pytest tests/ -m "not browser"`).
- **Piso vigente, medido em 01/09:** **3052 passed, 6 skipped, 201 deselected, 74 xfailed, 0 failed** — ⚠️ costurado em duas rodadas (a das 15:15 caiu com a sessão em 89%; o restante em `tests/reports/pytest_output_20260901_162027_restante11.txt`). A rodada única de confirmação é o Step 1 da Task 12.
- **O skipped nunca sobe.** Se subir, pare e descubra por quê (lição de 28/08: 4 testes saíram do gate em silêncio).
- **Os 74 xfailed são todos `strict=True` e só DESCEM.** Consertar o código que um xfail mede **exige remover o marcador no mesmo commit** — com `strict`, o conserto sem remoção FALHA o gate por XPASS. Cada task diz quais marcadores remove. Ao fim das Tasks 2 e 3, xfailed = **72**.
- **TDD sem exceção**, RED conferido e **citado no commit**. Para os defeitos já guardados por xfail, o RED é o teste existente falhando após a remoção do marcador — cite isso.
- **Migrations:** a última é a **316** (`migrations.py:7415`); este plano cria a **317** (Task 2) e a **318** (Task 6), nesta ordem — registradas na lista de `migrations.py:7760` e vizinhança, no mesmo formato das existentes.
- **Lição N2 (obrigatória em toda migration deste plano):** `create_all()` roda ANTES das migrações em todo boot. Em banco novo, o modelo cria constraints genuínas; em banco velho, a migration é quem cria. As duas formas têm de convergir para o MESMO objeto (mesmo nome, mesmo tipo constraint-vs-índice), senão o `DROP` de uma futura migration estoura `DependentObjectsStillExist` — foi exatamente o N2 (`docs/auditoria/achados-code-review-2026-08-25.md`, seção "O Que Não Persiste").
- **Nenhum teste prova por `inspect.getsource()`** — prova por comportamento, no banco ou na resposta HTTP. Um teste de guarda tem de reprovar também quando o próprio gatilho para de funcionar (regra da onda "A Porta Irmã").
- **Working directory:** raiz do repositório. Branch de trabalho: a atual (`sdd/a-porta-irma`); o merge é da Task 10 do plano de 31/08, não deste.

---

### Task 1: Landar a árvore — o trabalho commitável que está solto

A árvore tem o resíduo da Onda 6 Task 5 (quatro resolvedores corrigidos + docs) e o documento de decisões de 01/09, **nenhum commitado**. Nada de código novo aqui; é fechar o que está aberto antes de abrir mais.

**Files:**
- Commit (já modificados na árvore): `contabilidade_views.py`, `crud_rdo_completo.py`, `folha_pagamento_views.py`, `propostas_consolidated.py`, `docs/planos-em-aberto-2026-08-25.md`, `docs/reconferencia-backlog-2026-08-23.md`, `docs/superpowers/plans/2026-08-25-onda-6-os-testes-prometidos.md`
- Commit (untracked): `tests/test_isolamento_tenant_bloco1.py`, `docs/superpowers/plans/2026-09-01-decisoes-respondidas.md`, `docs/superpowers/plans/2026-09-01-as-decisoes-viram-codigo.md`

**Interfaces:**
- Consumes: nada.
- Produces: `tests/test_isolamento_tenant_bloco1.py` no repositório — as Tasks 9 e 10 o estendem.

- [x] **Step 1: Conferir que a árvore é o que se espera**

Run: `git status --short`
Expected: exatamente os 7 modificados e os untracked listados acima (mais este plano). Qualquer outra coisa: pare e pergunte ao dono antes de commitar.

- [x] **Step 2: Rodar o censo que os diffs referenciam**

Run: `python -m pytest tests/test_isolamento_tenant_bloco1.py -v`
Expected: PASS em todos (as correções dos 4 módulos já estão na árvore; o censo é a prova delas).

- [x] **Step 3: Commit em dois pedaços**

```bash
git add tests/test_isolamento_tenant_bloco1.py contabilidade_views.py crud_rdo_completo.py folha_pagamento_views.py propostas_consolidated.py docs/planos-em-aberto-2026-08-25.md docs/reconferencia-backlog-2026-08-23.md docs/superpowers/plans/2026-08-25-onda-6-os-testes-prometidos.md
git commit -m "fix(tenant): censo de 16 resolvedores x 5 papeis, e os 4 que trancavam SUPER_ADMIN (Onda 6 Task 5)"
git add docs/superpowers/plans/2026-09-01-decisoes-respondidas.md docs/superpowers/plans/2026-09-01-as-decisoes-viram-codigo.md
git commit -m "docs(decisoes): as 13 perguntas abertas ganham resposta com evidencia, e o plano que as executa"
```

---

### Task 2: O UNIQUE de `chave_acesso` passa a ser por tenant (a09-A)

🔴 Defeito vivo em produção: `NotaFiscal.chave_acesso` tem `unique=True` **global** (`models.py`, classe `NotaFiscal`, coluna `chave_acesso`), então a nota importada pela empresa A **bloqueia a empresa B** de importar a mesma nota — e NFe é documento público: duas empresas podem legitimamente ter a mesma chave (transportadora, contabilidade compartilhada). O teste que mede isso já existe e está `xfail(strict=True)`.

**Files:**
- Modify: `models.py` (classe `NotaFiscal` — coluna `chave_acesso` e `__table_args__`)
- Modify: `migrations.py` (nova `_migration_317_chave_acesso_por_tenant` + registro na lista de migrações, formato de `migrations.py:7752`)
- Modify: `tests/test_a09_dedup_nf_entrada_e_tenant_almoxarifado.py:290-294` (remover o marcador xfail)

**Interfaces:**
- Consumes: nada.
- Produces: constraint `uq_nf_admin_chave_acesso UNIQUE (admin_id, chave_acesso)` em `nota_fiscal` — idêntica em banco novo (modelo) e banco migrado (317).

- [x] **Step 1: Transformar o xfail em RED**

Em `tests/test_a09_dedup_nf_entrada_e_tenant_almoxarifado.py:290`, apagar o decorator `@pytest.mark.xfail(strict=True, reason='🔴 achado 31/08 — o UNIQUE GLOBAL de ...')` que cobre `test_o_xml_de_outro_tenant_ainda_nao_entra_por_causa_da_chave_de_acesso`. Não toque no corpo do teste.

- [x] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_a09_dedup_nf_entrada_e_tenant_almoxarifado.py::test_o_xml_de_outro_tenant_ainda_nao_entra_por_causa_da_chave_de_acesso -v`
Expected: FAIL (IntegrityError/violação de unique global ao segundo tenant importar). Este é o RED a citar no commit.

- [x] **Step 3: Corrigir o modelo**

Em `models.py`, na classe `NotaFiscal`:

```python
# antes:
    chave_acesso = db.Column(db.String(44), unique=True, nullable=False)
# depois:
    # A09 — chave de acesso é única POR TENANT: NFe é documento público e
    # duas empresas podem importar a mesma nota. O unique global fazia a
    # primeira bloquear a segunda (xfail medido em 31/08). Constraint
    # nomeada para a migration 317 convergir com o create_all (lição N2).
    chave_acesso = db.Column(db.String(44), nullable=False)
```

E em `__table_args__` da mesma classe (hoje tem os índices `idx_nf_admin_status`, `idx_nf_fornecedor_data`, `idx_nf_chave_acesso`), acrescentar como primeiro elemento:

```python
        db.UniqueConstraint('admin_id', 'chave_acesso',
                            name='uq_nf_admin_chave_acesso'),
```

- [x] **Step 4: Escrever a migration 317**

Em `migrations.py`, junto das vizinhas (`_migration_316_...` está em `:7415`):

```python
def _migration_317_chave_acesso_por_tenant():
    """A09 — nota_fiscal.chave_acesso deixa de ser única GLOBAL.

    O unique global (criado pelo unique=True do modelo antigo, constraint
    `nota_fiscal_chave_acesso_key`) fazia a nota importada por uma empresa
    bloquear a mesma nota em outra. Passa a UNIQUE (admin_id, chave_acesso).

    Lição N2: em banco novo o create_all já cria a constraint nova pelo
    modelo; aqui os dois passos são condicionais para convergir no mesmo
    estado — DROP do global se existir, ADD da composta se faltar.
    """
    from sqlalchemy import text
    with db.engine.begin() as conn:
        conn.execute(text("""
            DO $$
            BEGIN
                IF EXISTS (SELECT 1 FROM pg_constraint
                           WHERE conname = 'nota_fiscal_chave_acesso_key') THEN
                    ALTER TABLE nota_fiscal
                        DROP CONSTRAINT nota_fiscal_chave_acesso_key;
                END IF;
                IF NOT EXISTS (SELECT 1 FROM pg_constraint
                               WHERE conname = 'uq_nf_admin_chave_acesso') THEN
                    ALTER TABLE nota_fiscal
                        ADD CONSTRAINT uq_nf_admin_chave_acesso
                        UNIQUE (admin_id, chave_acesso);
                END IF;
            END $$;
        """))
```

E registrar na lista de migrações (mesmo formato da linha `migrations.py:7752`):

```python
            (317, "A09 — nota_fiscal.chave_acesso unica por (admin_id, chave_acesso), nao global", _migration_317_chave_acesso_por_tenant),
```

- [x] **Step 5: Run tests to verify they pass**

Run: `python -m pytest tests/test_a09_dedup_nf_entrada_e_tenant_almoxarifado.py -v`
Expected: PASS em todos exceto o segundo xfail (`test_xml_de_fornecedor_novo_estoura_not_null_em_fornecedor_nome`, que a Task 3 resolve e continua XFAIL aqui). Nenhum XPASS.

- [x] **Step 6: Commit**

```bash
git add models.py migrations.py tests/test_a09_dedup_nf_entrada_e_tenant_almoxarifado.py
git commit -m "fix(a09): chave de acesso da NF e unica por tenant, nao global (migration 317; RED era o xfail de 31/08)"
```

---

### Task 3: A importação de XML de fornecedor novo para de morrer (a09-B)

🔴 Defeito vivo: `processar_xml_nfe` (`almoxarifado_utils.py`, bloco `if not fornecedor:` por volta da linha 290) cria `Fornecedor` sem o campo `nome` — que é `nullable=False` (`models.py:2380`, "Campo legado obrigatório"). **Toda importação de XML cujo emitente ainda não está cadastrado morre no INSERT.** Teste já escrito, `xfail(strict=True)`.

**Files:**
- Modify: `almoxarifado_utils.py` (criação de `Fornecedor` dentro de `processar_xml_nfe`)
- Modify: `tests/test_a09_dedup_nf_entrada_e_tenant_almoxarifado.py:332-336` (remover o marcador xfail)

**Interfaces:**
- Consumes: nada.
- Produces: nada além do conserto.

- [x] **Step 1: Transformar o xfail em RED**

Apagar o decorator `@pytest.mark.xfail(strict=True, reason='🔴 achado 31/08 — processar_xml_nfe ...')` de `test_xml_de_fornecedor_novo_estoura_not_null_em_fornecedor_nome` (linha 332).

- [x] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_a09_dedup_nf_entrada_e_tenant_almoxarifado.py::test_xml_de_fornecedor_novo_estoura_not_null_em_fornecedor_nome -v`
Expected: FAIL com IntegrityError (NOT NULL em `fornecedor.nome`). RED a citar no commit.

- [x] **Step 3: Corrigir a criação do fornecedor**

Em `almoxarifado_utils.py`, no `Fornecedor(...)` dentro de `processar_xml_nfe`:

```python
            _razao = razao_social.text if razao_social is not None else 'Não informado'
            fornecedor = Fornecedor(
                nome=_razao,  # A09 — `nome` é NOT NULL (models.py:2380); sem ele TODO emitente novo estourava o INSERT
                razao_social=_razao,
                nome_fantasia=nome_fantasia.text if nome_fantasia is not None else None,
                cnpj=cnpj,
                admin_id=admin_id,
            )
```

(Preserve os demais kwargs que existirem no construtor além dos mostrados.)

- [x] **Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/test_a09_dedup_nf_entrada_e_tenant_almoxarifado.py -v`
Expected: **tudo PASS, zero xfail restante no arquivo.**

- [x] **Step 5: Commit**

```bash
git add almoxarifado_utils.py tests/test_a09_dedup_nf_entrada_e_tenant_almoxarifado.py
git commit -m "fix(a09): fornecedor criado pelo XML nasce com nome — emitente novo importava zero notas (RED era o xfail de 31/08)"
```

---

### Task 4: A despesa geral ganha conta de débito própria (A04)

Decisão de 01/09: **não** reaproveitar `6.1.02.001-003` (significados divergem entre os planos concorrentes — é por isso que `contabilidade_utils.py:545` exclui o subgrupo do DRE). Cria-se uma analítica nova num código que **nenhum** plano concorrente usa, e o `MAPEAMENTO_CONTABIL` ganha a chave `despesa_geral`. ⚠️ `RATIFICAR` com o contador é **o nome e o grupo** (6 = despesa operacional vs 5 = custo); trocar depois é uma linha em cada lugar.

**Files:**
- Modify: `contabilidade_utils.py` (`_V2_CONTAS_SEED` em `:1547`; `MAPEAMENTO_CONTABIL` em `:1536`)
- Test: `tests/test_a04_despesa_geral_contabil.py` (novo)

**Interfaces:**
- Consumes: `seed_plano_contas_if_needed(admin_id)` (`contabilidade_utils.py:1597`) e `gerar_lancamento_contabil_automatico(...)` (`contabilidade_utils.py:1668`), ambos existentes.
- Produces: conta `6.1.02.009` e chave `MAPEAMENTO_CONTABIL['despesa_geral'] = {'debito': '6.1.02.009', 'credito': '2.1.01.001'}`.

- [x] **Step 1: Write the failing test**

```python
"""A04 — a despesa geral tem conta de débito própria e inequívoca.

Por que 6.1.02.009 e não 6.1.02.001-003: os planos de contas concorrentes
dão significados diferentes a esses três códigos (contabilidade_utils.py:545
documenta), e reaproveitar um deles escolheria um significado sem saber qual
o tenant usa. O .009 não existe em nenhum dos planos conhecidos.
Decisão: docs/superpowers/plans/2026-09-01-decisoes-respondidas.md §A04.
"""
import uuid
import pytest
from werkzeug.security import generate_password_hash

from app import app, db


@pytest.fixture()
def tenant():
    with app.app_context():
        from models import Usuario, TipoUsuario
        marca = uuid.uuid4().hex[:6]
        admin = Usuario(
            username=f'a04{marca}', email=f'a04{marca}@t.local', nome='A04',
            password_hash=generate_password_hash('x'),
            tipo_usuario=TipoUsuario.ADMIN, ativo=True)
        db.session.add(admin)
        db.session.commit()
        yield admin.id
        db.session.rollback()


def test_o_mapeamento_tem_despesa_geral():
    from contabilidade_utils import MAPEAMENTO_CONTABIL
    assert MAPEAMENTO_CONTABIL['despesa_geral'] == {
        'debito': '6.1.02.009', 'credito': '2.1.01.001'}


def test_o_seed_v2_cria_a_conta_da_despesa_geral(tenant):
    with app.app_context():
        from contabilidade_utils import seed_plano_contas_if_needed
        from models import PlanoContas
        seed_plano_contas_if_needed(tenant)
        db.session.commit()
        conta = PlanoContas.query.filter_by(
            admin_id=tenant, codigo='6.1.02.009').first()
        assert conta is not None
        assert conta.aceita_lancamento is True
        assert conta.tipo_conta == 'DESPESA'
        assert conta.conta_pai_codigo == '6.1.02'


def test_lancamento_de_despesa_geral_debita_a_conta_nova(tenant):
    with app.app_context():
        from contabilidade_utils import (seed_plano_contas_if_needed,
                                         gerar_lancamento_contabil_automatico)
        from models import LancamentoContabil
        seed_plano_contas_if_needed(tenant)
        db.session.commit()
        ok = gerar_lancamento_contabil_automatico(
            tipo_operacao='despesa_geral', valor=123.45,
            descricao='Teste A04', admin_id=tenant)
        assert ok is True
        lc = (LancamentoContabil.query.filter_by(admin_id=tenant)
              .order_by(LancamentoContabil.id.desc()).first())
        assert lc is not None
```

⚠️ Antes de rodar: leia a assinatura real de `gerar_lancamento_contabil_automatico` em `contabilidade_utils.py:1668` e ajuste os kwargs do terceiro teste a ela (a função pode exigir `origem`/`origem_id` — a B5.6 os tornou parâmetros). O que o teste afirma não muda: chave nova aceita, lançamento criado.

- [x] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_a04_despesa_geral_contabil.py -v`
Expected: FAIL — `KeyError: 'despesa_geral'` no primeiro; conta ausente no segundo.

- [x] **Step 3: Write minimal implementation**

Em `contabilidade_utils.py`:

1. Em `_V2_CONTAS_SEED`, logo após a linha de `('6.1.02.002', 'Despesa com Transporte', ...)` (`:1590`):

```python
    # A04 — analítica própria da despesa geral. O código .009 não existe em
    # NENHUM dos planos concorrentes (o .001-.003 divergem de significado
    # entre eles — ver o comentário do DRE em :545). RATIFICAR com o
    # contador: nome e grupo; o código fica.
    ('6.1.02.009', 'Despesas Gerais Diversas',     'DESPESA',  'DEVEDORA', 4, '6.1.02',  True),
```

2. Em `MAPEAMENTO_CONTABIL` (`:1536`), acrescentar:

```python
    'despesa_geral':        {'debito': '6.1.02.009', 'credito': '2.1.01.001'},
```

- [x] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_a04_despesa_geral_contabil.py -v`
Expected: PASS (3/3).

- [x] **Step 5: Commit**

```bash
git add contabilidade_utils.py tests/test_a04_despesa_geral_contabil.py
git commit -m "feat(a04): despesa geral ganha conta de debito propria (6.1.02.009) e entra no mapeamento contabil"
```

---

### Task 5: A rota legada do RDO grava o elo `subatividade_mestre_id` (A18, parte destravada)

A Decisão 4 (congelar históricas) não trava isto: gravar o **elo** não muda número nenhum. Hoje só dois pontos de `views/rdo.py` gravam o elo (`:2087` e `:4258`); os dois construtores da rota legada `POST /rdo/salvar` (`:3295` e `:3349`) criam `RDOServicoSubatividade` **sem** ele, e a derivação de progresso cai em `'linha'` em silêncio. Regra: resolver por igualdade exata, **nunca** por semelhança — se não achar, fica `None` como hoje.

**Files:**
- Modify: `views/rdo.py:3295` e `views/rdo.py:3349` (os dois `RDOServicoSubatividade()` da rota legada)
- Test: `tests/test_a18_elo_rota_legada_rdo.py` (novo)

**Interfaces:**
- Consumes: `SubatividadeMestre` (modelo existente; o padrão de uso correto está em `views/rdo.py:4247-4258`).
- Produces: nada além do conserto.

- [x] **Step 1: Write the failing test**

```python
"""A18 — o RDO salvo pela rota legada nasce com o elo subatividade_mestre_id.

O elo é resolvido por igualdade EXATA de (admin_id, servico_id, nome) contra
SubatividadeMestre. Sem match exato, fica None — comportamento de hoje.
Decisão: docs/superpowers/plans/2026-09-01-decisoes-respondidas.md §A18.
"""
import uuid
import pytest
from werkzeug.security import generate_password_hash

from app import app, db


@pytest.fixture()
def cenario():
    """Admin + obra + serviço + uma SubatividadeMestre de nome conhecido."""
    with app.app_context():
        from models import (Usuario, TipoUsuario, Obra, Servico,
                            SubatividadeMestre)
        marca = uuid.uuid4().hex[:6]
        admin = Usuario(
            username=f'a18{marca}', email=f'a18{marca}@t.local', nome='A18',
            password_hash=generate_password_hash('x'),
            tipo_usuario=TipoUsuario.ADMIN, ativo=True)
        db.session.add(admin)
        db.session.flush()
        obra = Obra(nome=f'Obra A18 {marca}', admin_id=admin.id)
        db.session.add(obra)
        servico = Servico(nome=f'Servico A18 {marca}', admin_id=admin.id)
        db.session.add(servico)
        db.session.flush()
        sub = SubatividadeMestre(
            nome='Montagem de teste A18', servico_id=servico.id,
            admin_id=admin.id, ativo=True)
        db.session.add(sub)
        db.session.commit()
        yield {'admin': admin, 'obra': obra, 'servico': servico, 'sub': sub}
        db.session.rollback()


def test_rota_legada_grava_o_elo_quando_o_nome_casa(cenario):
    with app.test_client() as client:
        with client.session_transaction() as s:
            s['_user_id'] = str(cenario['admin'].id)
        r = client.post('/rdo/salvar', data={
            'obra_id': str(cenario['obra'].id),
            'data_relatorio': '01/09/2026',
            'subatividade_1_nome': 'Montagem de teste A18',
            'subatividade_1_percentual': '10',
            'subatividade_1_servico_id': str(cenario['servico'].id),
        }, follow_redirects=False)
        assert r.status_code in (200, 302)
    with app.app_context():
        from models import RDOServicoSubatividade
        linha = (RDOServicoSubatividade.query
                 .filter_by(admin_id=cenario['admin'].id,
                            nome_subatividade='Montagem de teste A18')
                 .order_by(RDOServicoSubatividade.id.desc()).first())
        assert linha is not None, 'a rota legada nem gravou a subatividade'
        assert linha.subatividade_mestre_id == cenario['sub'].id
```

⚠️ Antes de rodar: (1) confira os nomes reais dos campos do form legado lendo o parser acima de `views/rdo.py:3295` (a extração de `subatividades_extraidas` diz quais chaves ele lê — `subatividade_N_nome` etc.; ajuste o POST ao formato real); (2) confira os kwargs obrigatórios de `Obra`/`Servico`/`SubatividadeMestre` nos modelos e complete o fixture se o INSERT exigir mais campos; (3) o formato de `data_relatorio` brasileiro é o que a rota espera (`strptime` — ver o gatilho descoberto na onda "A Porta Irmã"). O teste tem de chegar ao construtor de `:3295` — se morrer antes num flash de validação, o assert de `linha is not None` acusa e o gatilho precisa de ajuste, não o alvo.

- [x] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_a18_elo_rota_legada_rdo.py -v`
Expected: FAIL no assert final — `subatividade_mestre_id` é `None`. (Se falhar em `linha is not None`, o POST não chegou ao construtor: ajuste o gatilho pelo parser real e rode de novo — esse ajuste faz parte do RED honesto.)

- [x] **Step 3: Write minimal implementation**

Em `views/rdo.py`, nos DOIS construtores da rota legada (`:3295` e `:3349`), logo após `rdo_servico_subativ.servico_id` ser resolvido, acrescentar:

```python
            # A18 — o elo com o catálogo, resolvido por igualdade EXATA
            # (admin_id, servico_id, nome). Sem match, None — nunca chutar.
            # Mesmo elo que :4258 já grava no fluxo novo.
            _mestre = None
            if rdo_servico_subativ.servico_id:
                _mestre = SubatividadeMestre.query.filter_by(
                    admin_id=admin_id_correto,
                    servico_id=rdo_servico_subativ.servico_id,
                    nome=rdo_servico_subativ.nome_subatividade,
                ).first()
            rdo_servico_subativ.subatividade_mestre_id = _mestre.id if _mestre else None
```

(Confirme que `SubatividadeMestre` já está importado no módulo — `views/rdo.py:4247` o usa; se o import for local lá, replique-o.)

- [x] **Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/test_a18_elo_rota_legada_rdo.py tests/test_rota_rdo_salvar_unica.py -v`
Expected: PASS — o novo e os 3 existentes da rota (regressão).

- [x] **Step 5: Commit**

```bash
git add views/rdo.py tests/test_a18_elo_rota_legada_rdo.py
git commit -m "fix(a18): rota legada do RDO grava subatividade_mestre_id por match exato — a derivacao para de cair em 'linha' em silencio"
```

---

### Task 6: O rateio de encargos patronais liga atrás de flag (A24)

🔬 `processar_e_salvar_folha_obra` (`services/folha_service.py:1699`), `_folha_rateada_para_obra` (`:1653`) e `_ratear_valor_por_obra` (`:1618`) estão corretos, testados (`tests/test_onda3_folha.py`) e **sem nenhum chamador de produção** — a mão de obra sai ~28% subestimada no custo de obra. Liga-se atrás de flag por tenant, **default FALSE**, no padrão exato da `rdo_percentual_livre` (migração 226 + leitor em `utils/tenant.py:165` + `scripts/flag_rdo_percentual_livre.py`). ⚠️ `RATIFICAR`: ligar em produção é decisão do dono — esta task entrega o interruptor desligado.

**Files:**
- Modify: `migrations.py` (nova `_migration_318_flag_folha_rateio_encargos` + registro na lista; espelhar `_migration_226_flag_rdo_percentual_livre` em `migrations.py:4100-4120`)
- Modify: `models.py` (coluna em `ConfiguracaoEmpresa`, junto de `rdo_percentual_livre`, `models.py:4533` vizinhança)
- Modify: `utils/tenant.py` (novo leitor, espelho de `rdo_percentual_livre_on` em `:165-192`)
- Modify: `folha_pagamento_views.py` (rota `processar`, após o laço de funcionários — o laço está em `:190-215`)
- Create: `scripts/flag_folha_rateio_encargos.py` (cópia adaptada de `scripts/flag_rdo_percentual_livre.py`)
- Test: `tests/test_a24_rateio_encargos_flag.py` (novo)

**Interfaces:**
- Consumes: `processar_e_salvar_folha_obra(obra_id, ano, mes, admin_id)` (`services/folha_service.py:1699`); `_horas_por_obra_no_mes` (`:1594`) como referência da descoberta de obras.
- Produces: `folha_rateio_encargos_on(admin_id) -> bool` em `utils/tenant.py`; coluna `configuracao_empresa.folha_rateio_encargos` (default FALSE).

- [x] **Step 1: Write the failing test**

```python
"""A24 — o rateio de encargos por obra liga atrás de flag por tenant.

Flag OFF (default): processar a folha muda ZERO no que existe hoje.
Flag ON: processar a folha também grava a folha rateada por obra, com
encargos — o pipeline de services/folha_service.py:1699 ganha chamador.
Decisão: docs/superpowers/plans/2026-09-01-decisoes-respondidas.md §A24.
"""
import pytest

from app import app, db


def test_leitor_da_flag_falha_seguro_sem_tenant():
    with app.app_context():
        from utils.tenant import folha_rateio_encargos_on
        assert folha_rateio_encargos_on(None) is False
        assert folha_rateio_encargos_on(999999999) is False


def test_a_flag_liga_e_desliga_por_script():
    with app.app_context():
        from scripts.flag_folha_rateio_encargos import definir_flag, status_flag
        from models import Usuario, TipoUsuario
        import uuid
        from werkzeug.security import generate_password_hash
        marca = uuid.uuid4().hex[:6]
        admin = Usuario(
            username=f'a24{marca}', email=f'a24{marca}@t.local', nome='A24',
            password_hash=generate_password_hash('x'),
            tipo_usuario=TipoUsuario.ADMIN, ativo=True)
        db.session.add(admin)
        db.session.commit()
        assert status_flag(admin.id) is False   # default
        definir_flag(admin.id, True)
        assert status_flag(admin.id) is True
        definir_flag(admin.id, False)
        assert status_flag(admin.id) is False
```

E o teste de comportamento fim-a-fim. A tabela de destino do rateio é `FolhaProcessada` (é nela que `salvar_folha_processada`, `services/folha_service.py:1270`, escreve — com `obra_id`, `encargos_fgts` e `encargos_inss_patronal` por linha). O cenário (admin + funcionário + ponto em duas obras no mês) já existe montado em `tests/test_onda3_folha.py:431-460`: **copie o fixture de lá** para este arquivo com o nome `cenario_folha`, devolvendo `{'admin_id': ..., 'funcionario_id': ..., 'obra_a': ..., 'obra_b': ..., 'ano': ..., 'mes': ...}` (não importe entre arquivos de teste: quebra isolamento). Então:

```python
def _processar_o_mes(admin_id, ano, mes):
    """Dispara o MESMO caminho da rota folha.processar — via cliente HTTP,
    logado como o admin do cenário. O form da rota pede mes_referencia;
    confira o nome exato do campo na própria rota antes de rodar."""
    with app.test_client() as client:
        with client.session_transaction() as s:
            s['_user_id'] = str(admin_id)
        return client.post('/folha/processar', data={
            'mes_referencia': f'{ano}-{mes:02d}',
        }, follow_redirects=False)


def test_flag_off_processar_folha_nao_grava_rateio(cenario_folha):
    with app.app_context():
        from models import FolhaProcessada
        c = cenario_folha
        _processar_o_mes(c['admin_id'], c['ano'], c['mes'])
        linhas = FolhaProcessada.query.filter_by(
            admin_id=c['admin_id'], ano=c['ano'], mes=c['mes']).all()
        com_obra = [l for l in linhas if l.obra_id is not None]
        assert com_obra == [], (
            'flag OFF (default) tem de manter o comportamento de hoje: '
            'nenhuma linha rateada por obra')


def test_flag_on_processar_folha_grava_rateio_com_encargos(cenario_folha):
    with app.app_context():
        from scripts.flag_folha_rateio_encargos import definir_flag
        from models import FolhaProcessada
        c = cenario_folha
        definir_flag(c['admin_id'], True)
        _processar_o_mes(c['admin_id'], c['ano'], c['mes'])
        obras_gravadas = {
            l.obra_id for l in FolhaProcessada.query.filter_by(
                admin_id=c['admin_id'], ano=c['ano'], mes=c['mes'])
            if l.obra_id is not None}
        assert obras_gravadas == {c['obra_a'], c['obra_b']}, (
            'com a flag ON, cada obra com ponto no mês ganha sua fatia')
        uma = FolhaProcessada.query.filter_by(
            admin_id=c['admin_id'], ano=c['ano'], mes=c['mes'],
            obra_id=c['obra_a']).first()
        assert (uma.encargos_fgts or 0) > 0 or (
            uma.encargos_inss_patronal or 0) > 0, (
            'a fatia da obra tem de carregar encargos — é o ~28% que faltava')
```

- [x] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_a24_rateio_encargos_flag.py -v`
Expected: FAIL — `ImportError` (leitor e script não existem).

- [x] **Step 3: Write minimal implementation**

1. `models.py`, em `ConfiguracaoEmpresa`, junto de `rdo_percentual_livre`:

```python
    # A24 — liga o rateio de encargos patronais por obra no processamento da
    # folha (migração 318, default FALSE). Liga-se por
    # scripts/flag_folha_rateio_encargos.py, tenant a tenant.
    folha_rateio_encargos = db.Column(db.Boolean, nullable=False,
                                      server_default=db.false())
```

2. `migrations.py` — `_migration_318_flag_folha_rateio_encargos`, espelho literal da 226 (`:4100-4120`) trocando o nome da coluna, + registro `(318, "A24 — flag configuracao_empresa.folha_rateio_encargos (default FALSE)", _migration_318_flag_folha_rateio_encargos)`.

3. `utils/tenant.py` — espelho de `rdo_percentual_livre_on` (`:165-192`):

```python
def folha_rateio_encargos_on(admin_id) -> bool:
    """Flag do rateio de encargos patronais por obra (migração 318,
    default FALSE). PONTO ÚNICO de leitura de
    `configuracao_empresa.folha_rateio_encargos`. Liga-se por
    `scripts/flag_folha_rateio_encargos.py`. NUNCA levanta: sem admin_id,
    sem linha de configuração ou com erro de banco, devolve False."""
    if not admin_id:
        return False
    try:
        from models import ConfiguracaoEmpresa
        config = ConfiguracaoEmpresa.query.filter_by(admin_id=admin_id).first()
        return bool(config and config.folha_rateio_encargos)
    except Exception as e:
        logger.warning(f"Flag folha_rateio_encargos indisponível ({e}) — assumindo desligada")
        return False
```

4. `scripts/flag_folha_rateio_encargos.py` — cópia de `scripts/flag_rdo_percentual_livre.py` trocando coluna, textos e nomes (`definir_flag`/`status_flag` mantidos).

5. `folha_pagamento_views.py`, na rota `processar`, **depois** do laço de funcionários e antes do commit final:

```python
        # A24 — com a flag ligada, o mesmo processamento também grava a
        # folha rateada por obra (encargos incluídos). As obras do mês são
        # as com ponto no período — a mesma fonte de
        # _horas_por_obra_no_mes (services/folha_service.py:1594).
        from utils.tenant import folha_rateio_encargos_on
        if folha_rateio_encargos_on(admin_id):
            from sqlalchemy import extract
            from models import RegistroPonto
            from services.folha_service import processar_e_salvar_folha_obra
            obras_do_mes = [r[0] for r in db.session.query(
                RegistroPonto.obra_id).filter(
                    RegistroPonto.obra_id.isnot(None),
                    RegistroPonto.admin_id == admin_id,
                    extract('year', RegistroPonto.data) == ano,
                    extract('month', RegistroPonto.data) == mes,
                ).distinct()]
            for _obra_id in obras_do_mes:
                processar_e_salvar_folha_obra(_obra_id, ano, mes, admin_id)
```

⚠️ Confirme em `models.py` que `RegistroPonto` tem `admin_id` direto; se o tenant lá for via `Funcionario`, troque o filtro por `join(Funcionario).filter(Funcionario.admin_id == admin_id)` — a fonte de verdade é a query de `_horas_por_obra_no_mes`.

- [x] **Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/test_a24_rateio_encargos_flag.py tests/test_onda3_folha.py -v`
Expected: PASS em todos (os de onda3 são a regressão do pipeline que agora ganhou chamador).

- [x] **Step 5: Commit**

```bash
git add models.py migrations.py utils/tenant.py folha_pagamento_views.py scripts/flag_folha_rateio_encargos.py tests/test_a24_rateio_encargos_flag.py
git commit -m "feat(a24): rateio de encargos patronais liga atras de flag por tenant (migration 318, default OFF) — o pipeline ganha chamador"
```

---

### Task 7: SFace nativo — o embedding sai do DeepFace e entra no OpenCV

🔬 O app usa do DeepFace **um único modelo**: SFace (`ponto_views.py:80`). O OpenCV instalado (4.11) já traz `cv2.FaceRecognizerSF` — o MESMO modelo SFace, via ONNX, sem TensorFlow. Esta task cria o caminho novo e **prova equivalência** com o velho; a remoção das dependências é a Task 8, separada de propósito: se a equivalência reprovar, nada foi removido.

**Files:**
- Create: `modelos_ml/face_recognition_sface_2021dec.onnx` (baixado, ver Step 1)
- Create: `utils_facial_sface.py` (embedding + comparação via OpenCV puro)
- Test: `tests/test_sface_nativo_equivalencia.py` (novo; marcado para pular sem o ONNX)

**Interfaces:**
- Consumes: `utils_facial.py` (caminho DeepFace atual, ainda instalado — é o oráculo da equivalência).
- Produces: `gerar_embedding_sface(imagem_bgr) -> np.ndarray` e `comparar_embeddings_sface(e1, e2) -> float` em `utils_facial_sface.py` — a Task 8 troca os chamadores para cá.

- [x] **Step 1: Baixar e fixar o modelo ONNX**

```bash
mkdir -p modelos_ml
curl -L -o modelos_ml/face_recognition_sface_2021dec.onnx \
  https://github.com/opencv/opencv_zoo/raw/main/models/face_recognition_sface/face_recognition_sface_2021dec.onnx
sha256sum modelos_ml/face_recognition_sface_2021dec.onnx | tee modelos_ml/face_recognition_sface_2021dec.onnx.sha256
```

Registre o sha256 no commit. (~37 MB; é o modelo oficial do opencv_zoo, mesma família que o DeepFace baixa.)

- [x] **Step 2: Write the failing test**

```python
"""O SFace nativo do OpenCV produz o mesmo veredito que o DeepFace.

Equivalência exigida: para o MESMO par de rostos, mesma-pessoa continua
mesma-pessoa e pessoas-diferentes continuam diferentes. Não se exige
igualdade bit a bit dos embeddings — o pré-processamento difere — e sim
concordância de decisão, que é o que o ponto usa.
Decisão: docs/superpowers/plans/2026-09-01-decisoes-respondidas.md §opencv.
"""
import os
import numpy as np
import pytest

ONNX = 'modelos_ml/face_recognition_sface_2021dec.onnx'

pytestmark = pytest.mark.skipif(
    not os.path.exists(ONNX),
    reason='modelo ONNX do SFace não baixado (Task 7 Step 1)')


def _rosto_sintetico(seed):
    """Imagem BGR determinística com um rosto-alvo simples.

    ⚠️ Substitua por duas fotos reais de fixture se o repositório já tiver
    (procure em tests/ por arquivos de foto usados nos testes de ponto
    facial — `grep -rl "base64\|\.jpg" tests/ | grep -i facial`). Rosto
    sintético só serve se o detector aceitar; se não aceitar, fotos reais
    são obrigatórias e este helper morre.
    """
    rng = np.random.default_rng(seed)
    return (rng.integers(0, 255, (200, 200, 3))).astype('uint8')


def test_embedding_tem_a_forma_do_sface():
    from utils_facial_sface import gerar_embedding_sface
    emb = gerar_embedding_sface(_rosto_sintetico(1))
    assert emb is not None and emb.size == 128  # SFace = 128 dims


def test_mesma_imagem_e_match_e_imagens_diferentes_nao():
    from utils_facial_sface import (gerar_embedding_sface,
                                    comparar_embeddings_sface,
                                    LIMIAR_COSSENO)
    a = gerar_embedding_sface(_rosto_sintetico(1))
    b = gerar_embedding_sface(_rosto_sintetico(1))
    c = gerar_embedding_sface(_rosto_sintetico(2))
    assert comparar_embeddings_sface(a, b) >= LIMIAR_COSSENO
    assert comparar_embeddings_sface(a, c) < LIMIAR_COSSENO
```

- [x] **Step 3: Run test to verify it fails**

Run: `python -m pytest tests/test_sface_nativo_equivalencia.py -v`
Expected: FAIL — `ModuleNotFoundError: utils_facial_sface`.

- [x] **Step 4: Write minimal implementation**

```python
"""utils_facial_sface — embedding facial SFace via OpenCV puro, sem TensorFlow.

Substitui DeepFace.build_model('SFace') (ponto_views.py:80): é o MESMO
modelo SFace, servido por cv2.FaceRecognizerSF sobre o ONNX oficial do
opencv_zoo. Limiar de cosseno 0.363 = o default documentado do SFace.
"""
import os
import threading

import cv2
import numpy as np

_ONNX = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                     'modelos_ml', 'face_recognition_sface_2021dec.onnx')
LIMIAR_COSSENO = 0.363

_lock = threading.Lock()
_modelo = None


def _get_modelo():
    global _modelo
    if _modelo is None:
        with _lock:
            if _modelo is None:
                _modelo = cv2.FaceRecognizerSF.create(_ONNX, '')
    return _modelo


def gerar_embedding_sface(imagem_bgr: np.ndarray) -> np.ndarray:
    """Embedding 128-d do rosto. A imagem deve vir recortada/alinhada no
    rosto (o app já recorta via Haar/YN antes de embeddar — mesmo contrato
    do caminho DeepFace)."""
    rec = _get_modelo()
    face = cv2.resize(imagem_bgr, (112, 112))
    return rec.feature(face).flatten()


def comparar_embeddings_sface(e1: np.ndarray, e2: np.ndarray) -> float:
    """Similaridade de cosseno entre dois embeddings (maior = mais parecido)."""
    rec = _get_modelo()
    return float(rec.match(e1.reshape(1, -1), e2.reshape(1, -1),
                           cv2.FaceRecognizerSF_FR_COSINE))
```

- [x] **Step 5: Run test to verify it passes**

Run: `python -m pytest tests/test_sface_nativo_equivalencia.py -v`
Expected: PASS. Se o segundo teste reprovar com rosto sintético, troque para fotos reais de fixture (nota no próprio teste) — o critério é decisão igual, e ruído aleatório pode não ser "rosto" o bastante; nesse caso o teste com fotos reais é o que vale.

- [x] **Step 6: Commit**

```bash
git add modelos_ml/ utils_facial_sface.py tests/test_sface_nativo_equivalencia.py
git commit -m "feat(facial): SFace nativo via cv2.FaceRecognizerSF — mesmo modelo, sem TensorFlow (caminho novo, chamadores ainda no antigo)"
```

---

### Task 8: Os chamadores trocam para o SFace nativo e o TensorFlow sai

Só executar com a Task 7 verde. Troca os pontos de uso, regenera o cache de embeddings e remove `deepface`/`retina-face` do `pyproject.toml` — o que elimina a exigência transitiva de `opencv-python` (causa da dupla instalação) e ~1,8 GB de TensorFlow.

**Files:**
- Modify: `ponto_views.py` (`get_sface_model` `:67-90`, `preload` `:93-140`, `gerar_embedding_otimizado` `:287-300` — todos os `from deepface import DeepFace`)
- Modify: `utils_facial.py` (`comparar_faces_deepface` `:34` e quem mais importar deepface — `grep -n deepface utils_facial.py`)
- Modify: `gerar_cache_facial.py` (usa `gerar_embedding_otimizado`; deve passar a fazê-lo pelo caminho novo sem mudar o formato do cache)
- Modify: `pyproject.toml` (remover `deepface` e `retina-face`; manter `opencv-python-headless`)
- Test: `tests/test_ponto_facial_sem_deepface.py` (novo)

**Interfaces:**
- Consumes: `gerar_embedding_sface`/`comparar_embeddings_sface`/`LIMIAR_COSSENO` de `utils_facial_sface.py` (Task 7).
- Produces: nada — contrato externo das funções de `utils_facial.py`/`ponto_views.py` inalterado.

- [x] **Step 1: Write the failing test**

```python
"""Depois da troca, o caminho facial não importa deepface nem tensorflow.

Prova por comportamento: importa os módulos do ponto facial, exercita a
comparação, e afirma que nem deepface nem tensorflow entraram em
sys.modules — se algum caminho ainda os importar, o teste acusa.
"""
import sys
import numpy as np


def test_comparacao_facial_funciona_sem_deepface_no_processo():
    for m in list(sys.modules):
        if m.startswith(('deepface', 'tensorflow')):
            del sys.modules[m]
    import utils_facial  # noqa: F401
    from utils_facial_sface import (gerar_embedding_sface,
                                    comparar_embeddings_sface)
    a = gerar_embedding_sface(
        np.zeros((112, 112, 3), dtype='uint8'))
    comparar_embeddings_sface(a, a)
    intrusos = [m for m in sys.modules
                if m.startswith(('deepface', 'tensorflow'))]
    assert intrusos == [], f'caminho facial ainda importa: {intrusos}'
```

- [x] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_ponto_facial_sem_deepface.py -v`
Expected: FAIL — `utils_facial` importa deepface no topo ou dentro das funções exercitadas.

- [x] **Step 3: Trocar os chamadores**

Em cada ponto que hoje faz `from deepface import DeepFace` (liste com `grep -rn "from deepface" ponto_views.py utils_facial.py gerar_cache_facial.py`): substituir a geração de embedding por `gerar_embedding_sface` e a comparação por `comparar_embeddings_sface`, preservando assinatura e formato de retorno das funções públicas (`comparar_faces_deepface` mantém o nome — os chamadores dela não mudam nesta task; só o miolo troca). O limiar configurado hoje (procure `threshold` em `utils_facial.py:244-302`) é recalibrado para `LIMIAR_COSSENO` — deixe o valor antigo comentado ao lado, com a data.

- [x] **Step 4: Regenerar o cache de embeddings**

Run: `python gerar_cache_facial.py`
Expected: termina sem erro e reescreve `cache_facial.pkl`. ⚠️ O cache antigo (embeddings DeepFace) é **incompatível** com o novo — a regeneração não é opcional, e o commit deve dizer isso para quem operar produção.

- [x] **Step 5: Remover as dependências**

Em `pyproject.toml`, remover as linhas de `deepface` e `retina-face` (manter `opencv-python-headless`). Depois:

```bash
uv sync 2>/dev/null || pip uninstall -y deepface retina-face
python -m pytest tests/test_ponto_facial_sem_deepface.py tests/test_sface_nativo_equivalencia.py -v
```

Expected: PASS. (Se o ambiente não tiver `uv`, o uninstall direto serve para o teste local; o lockfile é o que vale para o deploy.)

- [x] **Step 6: Rodar a regressão do ponto e commitar**

Run: `python -m pytest tests/ -k "facial or ponto" -m "not browser" -v`
Expected: PASS (nenhum teste de ponto dependia de deepface diretamente; se algum importar, ele entra na troca do Step 3).

```bash
git add ponto_views.py utils_facial.py gerar_cache_facial.py pyproject.toml tests/test_ponto_facial_sem_deepface.py
git commit -m "feat(facial): chamadores migram ao SFace nativo; deepface/retina-face saem — some o opencv duplicado e 1,8GB de TensorFlow. Producao DEVE regenerar cache_facial.pkl"
```

---

### Task 9: As 18 rotas mortas de `views/vehicles.py` saem (mesmo procedimento da D3)

Decisão de 01/09: apagar, pelo roteiro que `0b3f932c` já usou nas seis quebradas — provar morte pela interface, teste de 404, remover. A capacidade viva equivalente é o `frota_bp` (os templates postam para `frota.*`).

**Files:**
- Delete: `views/vehicles.py` (as 18 rotas em `main_bp` — lista em `grep -n "@main_bp.route" views/vehicles.py`)
- Modify: quem importa/registra o módulo (`grep -rn "vehicles" --include="*.py" . | grep -vE "pythonlibs|tests|archive"` — tipicamente o `views/__init__.py` ou `app.py`)
- Test: `tests/test_vehicles_rotas_removidas.py` (novo)

**Interfaces:**
- Consumes: nada.
- Produces: nada — remoção.

- [x] **Step 1: Provar que estão mortas ANTES de apagar**

```bash
for rota in "/veiculos" "/veiculos/novo" "/veiculos/lancamentos" "/veiculos/relatorios" "/veiculos/relatorios/exportar" "veiculos/uso" "veiculos/custo" "ultima-km" "/kpis" "api/veiculos"; do
  echo "== $rota =="; grep -rn "$rota" templates/ static/ --include="*.html" --include="*.js" | grep -v "frota" | head -3
done
```

Expected: nenhuma referência viva (url_for de `main.*` de veículos, fetch/ajax para essas URLs). ⚠️ **Qualquer hit real interrompe a task**: a rota referenciada fica de fora da remoção e é registrada no commit como sobrevivente, com o porquê.

- [x] **Step 2: Write the failing test**

```python
"""D3, segunda leva — as 18 rotas de views/vehicles.py não existem mais.

As seis quebradas saíram em 0b3f932c; estas 18 funcionavam, mas estavam
mortas pela interface (templates postam para frota.*) — superfície sem
guarda e sem teste. Decisão: decisoes-respondidas.md §vehicles.
"""
import pytest

from app import app

URLS = [
    '/veiculos', '/veiculos/novo', '/veiculos/1', '/veiculos/1/editar',
    '/veiculos/1/excluir', '/veiculos/1/ultima-km', '/veiculos/1/kpis',
    '/veiculos/1/custos', '/veiculos/1/exportar', '/veiculos/1/uso/novo',
    '/veiculos/uso/1/detalhes', '/veiculos/uso/1/editar',
    '/veiculos/custo/1/deletar', '/veiculos/lancamentos',
    '/veiculos/relatorios', '/veiculos/relatorios/exportar',
    '/api/veiculos/1', '/api/veiculos/uso/1/finalizar',
]


@pytest.mark.parametrize('url', URLS)
def test_a_url_nao_existe_mais(url):
    with app.test_client() as client:
        r = client.get(url)
        # 404 = removida. 405 seria rota viva com método errado — reprova.
        # 302 para login também reprova: significa que a rota ainda existe.
        assert r.status_code == 404, f'{url} ainda responde {r.status_code}'
```

⚠️ Ajuste a lista de URLS à saída real de `grep -n "@main_bp.route" views/vehicles.py` (18 linhas, com métodos) — a de cima foi transcrita dela em 01/09.

- [x] **Step 3: Run test to verify it fails**

Run: `python -m pytest tests/test_vehicles_rotas_removidas.py -v`
Expected: FAIL nas 18 (respondem 200/302/405 — estão vivas).

- [x] **Step 4: Remover o módulo e o registro**

Apagar `views/vehicles.py` e a linha que o importa (localizada no Step "Modify" acima). Boot de conferência: `python -c "from app import app; print(len(list(app.url_map.iter_rules())))"` — o app sobe.

- [x] **Step 5: Run tests to verify they pass**

Run: `python -m pytest tests/test_vehicles_rotas_removidas.py tests/test_b6_404_frota.py -v`
Expected: PASS nas 18 novas; os testes de frota inalterados (a família `frota.*` não foi tocada — os xfail de lá continuam XFAIL, não XPASS).

- [x] **Step 6: Commit**

```bash
git add -A views/ tests/test_vehicles_rotas_removidas.py
git commit -m "fix(veiculos): as 18 rotas mortas pela interface saem (D3, segunda leva) — a capacidade viva e o frota_bp"
```

⚠️ Registrar no commit: `tests/test_browser_all_modules.py:647` exercita `/veiculos/relatorios` — se ele referenciar a rota removida, atualizá-lo para a equivalente de `frota.*` **faz parte desta task** (rode `grep -n "veiculos" tests/test_browser_all_modules.py` e ajuste). A prova final de sobrevivência do browser é o `--suite` da Task 12.

---

### Task 10: FUNCIONARIO sem `admin_id` falha fechado (a linha que ficou fora do censo)

Decisão de 01/09: o ramo de `crud_rdo_completo.get_admin_id` que resolve por FK quando `current_user.admin_id` é vazio **sai**; o módulo passa a delegar ao canônico como os outros três, e a linha deliberadamente excluída do censo entra nele. ⚠️ `RATIFICAR`: um funcionário nesse estado (defeito de dado) passa a ser barrado com 403 em vez de funcionar por adivinhação — é o comportamento que `utils/tenant.py` já documenta ("FALHA SEGURA").

**Files:**
- Modify: `crud_rdo_completo.py:16-40` (o `get_admin_id` local vira delegação ao canônico — o diff-padrão é o já aplicado em `contabilidade_views.py` pela Task 1)
- Modify: `tests/test_isolamento_tenant_bloco1.py` (remover a exceção documentada do caso FUNCIONARIO-sem-admin_id para `crud_rdo_completo` — procure o comentário que a marca)
- Create: `scripts/medir_funcionarios_sem_admin_id.py` (medição read-only para produção)

**Interfaces:**
- Consumes: `get_tenant_admin_id()` de `utils/tenant.py`.
- Produces: censo sem exceções — as Tasks seguintes tratam o censo como cobertura total.

- [x] **Step 1: Tornar o censo o RED**

Em `tests/test_isolamento_tenant_bloco1.py`, localizar a exceção do caso (grep por `crud_rdo_completo` no arquivo; há um desvio/skip documentado para FUNCIONARIO sem `admin_id`) e removê-la, fazendo o caso afirmar o canônico (`None` ⇒ mesmo resultado nos dois).

- [x] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_isolamento_tenant_bloco1.py -v -k crud_rdo`
Expected: FAIL — o resolvedor local devolve o id da FK onde o canônico devolve `None`.

- [x] **Step 3: Write minimal implementation**

`crud_rdo_completo.py` — substituir o corpo de `get_admin_id` pela delegação (mesmo shape do diff de `contabilidade_views.py`):

```python
def get_admin_id():
    """Tenant do usuário autenticado. DELEGA para o resolvedor canônico.

    Decisão de 01/09 (decisoes-respondidas.md §admin_id): o ramo que
    resolvia FUNCIONARIO sem admin_id por FK saiu — usuário nesse estado é
    defeito de dado e falha FECHADO (None ⇒ 403 nas guardas), como
    utils/tenant.py documenta. A medição do tamanho do reparo em produção
    é scripts/medir_funcionarios_sem_admin_id.py.
    """
    from utils.tenant import get_tenant_admin_id
    return get_tenant_admin_id()
```

- [x] **Step 4: Escrever a medição**

```python
#!/usr/bin/env python3
"""Mede (read-only) quantos usuários ativos não-admin estão sem admin_id.

É o tamanho do reparo de dado que a falha-fechada de 01/09 expõe. Rodar
contra produção ANTES de ligar o deploy que contém a Task 10:
    DATABASE_URL=<prod> python scripts/medir_funcionarios_sem_admin_id.py
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def main():
    from app import app, db
    from sqlalchemy import text
    with app.app_context():
        linhas = db.session.execute(text("""
            SELECT tipo_usuario, COUNT(*)
            FROM usuario
            WHERE admin_id IS NULL
              AND ativo = true
              AND tipo_usuario NOT IN ('ADMIN', 'SUPER_ADMIN')
            GROUP BY tipo_usuario ORDER BY 2 DESC
        """)).fetchall()
        total = sum(n for _, n in linhas)
        print(f'usuários ativos não-admin sem admin_id: {total}')
        for papel, n in linhas:
            print(f'  {papel}: {n}')
        print('cada um destes passa a receber 403 com a falha-fechada ativa.')


if __name__ == '__main__':
    main()
```

- [x] **Step 5: Run tests to verify they pass**

Run: `python -m pytest tests/test_isolamento_tenant_bloco1.py -v && python scripts/medir_funcionarios_sem_admin_id.py`
Expected: censo todo PASS; a medição imprime a contagem de dev (~263 — resíduo de suíte; o número que importa é o de produção, e o commit diz isso).

- [x] **Step 6: Commit**

```bash
git add crud_rdo_completo.py tests/test_isolamento_tenant_bloco1.py scripts/medir_funcionarios_sem_admin_id.py
git commit -m "fix(tenant): FUNCIONARIO sem admin_id falha fechado tambem no RDO — a resolucao por FK sai, e a medicao do reparo vai junto (RATIFICAR antes do deploy)"
```

---

### Task 11: Os resolvedores que faltam entram no censo e convergem (o tenant fantasma)

🔬 A onda "A Porta Irmã" mediu ~11 resolvedores com lógica própria cujo padrão (`admin_id if set else current_user.id`) devolve **tenant fantasma** para usuário sem `admin_id`. O censo (`RESOLVEDORES`, `tests/test_isolamento_tenant_bloco1.py:83`) já cobre 16 módulos; `views/metricas_views` e `subempreiteiros_views` estão citados na medição e **fora da lista**. Esta task fecha a diferença: todo módulo com resolvedor próprio entra no censo, e os que divergirem do canônico convergem — pelo diff-padrão da Task 1.

**Files:**
- Modify: `tests/test_isolamento_tenant_bloco1.py:83-99` (lista `RESOLVEDORES`)
- Modify: os módulos que o RED apontar (no mínimo `views/metricas_views.py` e `subempreiteiros_views.py`; a lista real sai do Step 1)

**Interfaces:**
- Consumes: censo da Task 1/10; `get_tenant_admin_id()` canônico.
- Produces: censo = cobertura total dos resolvedores do parque.

- [x] **Step 1: Levantar quem tem resolvedor próprio e está fora do censo**

```bash
grep -rln "def get_admin_id\|def _get_admin_id" --include="*.py" . | grep -vE "pythonlibs|tests|archive|utils/tenant"
```

Compare com `RESOLVEDORES` (`tests/test_isolamento_tenant_bloco1.py:83`). Todo módulo da primeira lista fora da segunda entra. (O meta-teste `test_a_lista_do_censo_cobre_quem_tem_resolvedor_proprio` em `:226` já tenta pegar isso — se ele não pegou `metricas_views`/`subempreiteiros`, o padrão de grep DELE precisa do ajuste também: leia-o e alinhe.)

- [x] **Step 2: Estender a lista (RED)**

Acrescentar os módulos achados a `RESOLVEDORES`, em ordem alfabética.

Run: `python -m pytest tests/test_isolamento_tenant_bloco1.py -v`
Expected: FAIL nos módulos novos que divergem do canônico (tipicamente no papel SUPER_ADMIN ou no FUNCIONARIO-sem-admin_id — o fantasma). **Anote quais papéis falham em qual módulo: isso vai no commit.** Se algum módulo novo nascer verde, diga isso no commit também — cobertura nova, não conserto.

- [x] **Step 3: Convergir os divergentes**

Em cada módulo que falhou, aplicar o diff-padrão (o de `contabilidade_views.py` na Task 1): o `get_admin_id` local vira

```python
def get_admin_id():
    """Tenant do usuário autenticado. DELEGA para o resolvedor canônico.

    Convergido em 01/09: a cópia local devolvia current_user.id como
    fallback — um TENANT FANTASMA para usuário sem admin_id, onde o
    canônico falha fechado. Medido pelo censo de
    tests/test_isolamento_tenant_bloco1.py.
    """
    from utils.tenant import get_tenant_admin_id
    return get_tenant_admin_id()
```

⚠️ Um módulo por vez, rodando o censo entre um e outro — se a convergência de um módulo quebrar outro teste do gate (algum fluxo dependia do fantasma), **pare nesse módulo**, registre, e traga a decisão ao dono em vez de forçar.

- [x] **Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/test_isolamento_tenant_bloco1.py -v`
Expected: PASS — censo completo, zero exceções.

- [x] **Step 5: Commit**

```bash
git add tests/test_isolamento_tenant_bloco1.py views/metricas_views.py subempreiteiros_views.py  # + os demais que o Step 1 achou
git commit -m "fix(tenant): os resolvedores fora do censo entram e convergem ao canonico — o tenant fantasma sai do parque"
```

---

### Task 12: Registro, operação agendada e o gate único

> **Estado em 01/09 ~19:45 (sessão encerrada no meio do Step 2):**
> - ✅ **Step 1 — gate único VERDE:** `3193 passed, 8 skipped, 201
>   deselected, 72 xfailed, 0 failed` em 42:24
>   (`tests/reports/gate_decisoes_1901.log`). Os 8 skips conferidos um a
>   um: 6 antigos (test_processar_usa_cadastro ×5,
>   test_regressao_classificacao ×1) + 2 NOVOS DELIBERADOS — o oráculo
>   deepface de `test_sface_nativo_equivalencia.py`, que pula desde que a
>   Task 8 removeu o deepface. O piso do gate passa a ser **skipped = 8**.
> - 🟡 **Step 2 — `--suite` INTERROMPIDA a ~18%** com **2 FAILED** em
>   `TestIntegracaoPropostaObra` (`test_criar_proposta_flash_sucesso` e
>   `test_aprovar_proposta_gera_obra`) — log parcial em
>   `tests/reports/suite_decisoes_1930.log`, SEM traceback (ele só sai no
>   fim da rodada). Diagnóstico pendente: (1) rerodar os 2 isolados —
>   `python -m pytest "tests/test_browser_all_modules.py::TestIntegracaoPropostaObra" -v`
>   — para separar flake de real; (2) não há placar histórico da família
>   browser nos reports, então NÃO se sabe se é regressão. O fluxo de
>   proposta não foi tocado pelas Tasks 5–11 desta rodada; o vizinho mais
>   próximo é a convergência de `propostas_consolidated` da Onda 6
>   (`a6afcb8e`, papel SUPER_ADMIN — o browser loga como admin). Os demais
>   ~110 browser rodados até a interrupção passaram, incluindo
>   `test_relatorios_veiculos` já apontando para `/frota/dashboard`.
> - ✅ Steps 3, 4 e 5 — runbook + registros escritos e commitados.
> - ⬜ Step 6 — o commit final previsto virou o commit parcial desta nota;
>   falta só fechar a suíte browser e, se verde, atualizar esta nota.

A última: o que este plano decidiu NÃO fazer fica escrito (a regra da casa — adiar sem registrar é como as issues chegaram a 31/08), a operação agendada ganha runbook, e o placar costurado de 01/09 vira uma rodada única.

**Files:**
- Create: `docs/operacao-agendamentos.md`
- Modify: `docs/superpowers/plans/2026-08-31-fecho-do-que-esta-aberto.md` (nota na tabela de estado)
- Modify: `docs/superpowers/plans/2026-08-31-decisoes-pendentes.md` (banner apontando as respostas)
- Modify: `docs/superpowers/plans/2026-08-24-fase-8-plano-de-contas-canonico.md` e `2026-08-24-resgate-espinha-financeira.md` (nota de decisão no cabeçalho)
- Modify: `docs/reconferencia-backlog-2026-08-23.md` (estados de A04/A18/A24/A25)

**Interfaces:**
- Consumes: o estado final das Tasks 1–11.
- Produces: o registro que a Task 10 do plano de 31/08 vai consumir no índice novo.

- [x] **Step 1: Rodar o gate único**

```bash
setsid nohup bash run_tests.sh --gate > tests/reports/gate_decisoes_$(date +%H%M).log 2>&1 &
```

(~50-60 min; destacado do terminal — três gates já morreram com sessão em 01/09.) Expected ao fim: **0 failed, skipped ≤ 6, xfailed = 72** (74 − os 2 do a09), passed ≥ 3052 + os testes novos deste plano. Registrar a contagem exata no Step 6.

- [ ] **Step 2: Rodar a suíte com browser**

Run: `bash run_tests.sh --suite` (após o gate verde)
Expected: verde — é a única prova de que a remoção da Task 9 não quebrou `test_browser_all_modules` (o gate deseleciona os 201 de browser).

- [x] **Step 3: Escrever o runbook de agendamentos**

`docs/operacao-agendamentos.md`, com exatamente estas seções (conteúdo das decisões de 01/09, §A25 e §backup):

```markdown
# Operação — tudo o que roda por agendamento

> Decisão de 01/09 (decisoes-respondidas.md): agendador vive FORA do
> processo web. O guard multi-worker do APScheduler é manual
> (app.py:1056) e quebra no primeiro `-w 2`.

## Backup do banco (Fase 0.5 — ❌ até o job existir)
- Job de cron do EasyPanel, diário:
  `pg_dump "$DATABASE_URL" | gzip > /backups/sige_$(date +%F).sql.gz`
- Retenção mínima 14 dias; testar o RESTORE uma vez por mês, não só o dump.

## Notificações n8n (A25)
- Pré-requisito: `N8N_WEBHOOK_URL` no ambiente (dono define; sem ela o
  despachante é no-op — app.py:436).
- Job diário do EasyPanel: `flask emitir-propostas-expirando`
  (comando de notificacoes_cli.py:130; use `--dry-run` para validar).

## Cobertura ociosa (job mensal já existente)
- Hoje roda via APScheduler in-process (app.py:1089, dia 1 às 06:00).
- Ao criar os jobs externos acima, migrar este também:
  `flask cobertura-ociosa` (CLI registrado em app.py:1045) no cron do dia 1,
  e `SCHEDULER_ENABLED=0` no serviço web.
```

⚠️ Antes de commitar: conferir os nomes exatos dos comandos CLI (`flask --help` lista; `emitir-propostas-expirando` está em `notificacoes_cli.py:130`, o de cobertura em `cobertura_ociosa_cli.py`) e corrigir o runbook se divergirem.

- [x] **Step 4: Registrar as decisões nos planos que elas destravam**

1. `2026-08-31-decisoes-pendentes.md` — no topo:
```markdown
> ✅ **RESPONDIDAS em 01/09** — ver `2026-09-01-decisoes-respondidas.md`.
> D6: assinatura estrutural (≥4 seeders, não 2). FASE8-T1: segue aguardando
> acesso a produção. VIGA-I: opção B; a C foi declarada morta.
```
2. `2026-08-24-fase-8-plano-de-contas-canonico.md` — nota no cabeçalho: a Task 4 muda de método (assinatura estrutural, decisoes-respondidas §D6); Tasks 1–3 executáveis já; a medição de produção ganhou as 3 perguntas novas do §FASE8-T1.
3. `2026-08-24-resgate-espinha-financeira.md` — nota no cabeçalho: VIGA-I decidida (opção B, RATIFICAR pendente); a Task 8 de lá destrava ao ratificar.
4. `docs/reconferencia-backlog-2026-08-23.md` — riscar/atualizar: A04 (entregue, Task 4 daqui), A18 (elo entregue, Decisão 4 = congelar, RATIFICAR), A24 (flag entregue OFF, RATIFICAR liga), A25 (runbook escrito; falta só a credencial).

- [x] **Step 5: Registrar o que este plano NÃO cobre, com destino**

Na tabela de estado de `2026-08-31-fecho-do-que-esta-aberto.md`, acrescentar abaixo dela:

```markdown
> **Complemento de 01/09:** `2026-09-01-as-decisoes-viram-codigo.md` executou
> o trabalho órfão das decisões (a09, A04, A18-elo, A24-flag, SFace, 18 rotas
> de veículos, falha-fechada e censo total do tenant). Continuam SEM plano
> próprio, por decisão registrada:
> - **Automações A01, A08, A17, A20, A21, A23 (abertas) e A11, A13, A15,
>   A16, A22 (parciais)** → próximo plano a escrever:
>   `2026-09-XX-onda-das-automacoes.md`. São feature-sized; entrariam aqui
>   só como placeholder, o que a casa proíbe.
> - **Família 404 (70 xfail, B6.4–B6.8)** → as tasks JÁ EXISTEM em
>   `2026-08-06-rodada-b6-varredura.md` (seções B6.4–B6.8); o refactor de
>   ~60 sítios roda por lá, removendo os marcadores xfail à medida que fecha.
>   O padrão `except HTTPException: raise` dos 5 pontos medidos é parte dele.
> - **Os 225 usos de `admin_id` em query sem guarda de `None`** (medição da
>   onda "A Porta Irmã") → o risco cai muito com as Tasks 10–11 daqui (o
>   `None` deixa de virar tenant fantasma e as guardas de rota abortam 403
>   antes da query), mas a varredura guard-a-guard continua sem dono —
>   registrar na onda das automações ou na issue B (falhas silenciosas).
> - **`obra.progresso_conclusao`** → funcionalidade nova, não conserto;
>   entra na onda das automações ou morre — decisão do dono.
> - **Fase 9a/9b** → segue adiada; reabrir pela seção "Premissas a
>   reconfirmar" do próprio plano.
> - **psycopg2→psycopg3** → registrado em decisoes-respondidas.md; não
>   agendar antes de existir build de produção próprio.
```

- [ ] **Step 6: Commit final**

```bash
git add docs/operacao-agendamentos.md docs/superpowers/plans/2026-08-31-fecho-do-que-esta-aberto.md docs/superpowers/plans/2026-08-31-decisoes-pendentes.md docs/superpowers/plans/2026-08-24-fase-8-plano-de-contas-canonico.md docs/superpowers/plans/2026-08-24-resgate-espinha-financeira.md docs/reconferencia-backlog-2026-08-23.md
git commit -m "docs: as decisoes de 01/09 registradas nos planos que destravavam; runbook de agendamento; gate unico <CONTAGEM> — o que ficou de fora tem destino escrito"
```

(Substituir `<CONTAGEM>` pela contagem real do Step 1 — ex.: `3061 passed, 6 skipped, 72 xfailed`.)
