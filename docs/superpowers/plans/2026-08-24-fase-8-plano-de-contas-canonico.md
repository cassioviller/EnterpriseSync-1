# Fase 8 — o plano de contas passa a significar uma coisa só

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recomendado) ou superpowers:executing-plans para executar este plano task a task. Os passos usam checkbox (`- [ ]`) para acompanhamento.

**Goal:** Fazer com que um código de conta contábil signifique a mesma coisa em todo o parque, e usar isso para entregar margem de contribuição, DFC pelos três grupos, indicadores com procedência e a exportação Domínio.

**Architecture:** Um semeador só (`seed_plano_contas_if_needed`, o `_V2_CONTAS_SEED`) vira o plano canônico; os dois concorrentes ficam marcados `EM APOSENTADORIA` e param de ser chamados. Duas colunas novas em `plano_contas` (`classificacao_gasto`, `atividade_dfc`) carregam a semântica que hoje não existe em lugar nenhum, e as Tasks de leitura (margem, DFC, indicadores) são **leitura pura** — nenhuma cria caminho de escrita novo. O único ponto que toca dado histórico é o de-para das contas `5.x`, isolado numa migration própria com contagem antes e depois.

**Tech Stack:** Flask + SQLAlchemy 2.x, PostgreSQL, pytest, Jinja2. Migrations pelo runner caseiro de `migrations.py` (tupla ordenada, não Alembic).

**Spec:** `docs/superpowers/specs/2026-08-17-fase-8-financeiro-design.md` — leia antes de começar; este plano argumenta a partir dela e não a substitui. O plano velho `docs/superpowers/plans/2026-07-21-fase-8-financeiro-avancado-dominio.md` é da versão anterior do escopo: serve de referência histórica, **não** de roteiro.

---

## ⚠️ Procedência: o que mudou entre a spec (17/08) e este plano (24/08)

A spec traz números e `caminho:linha` medidos em 17/08. Sete dias depois, quatro envelheceram. Nenhum invalida a spec; todos mudam instruções deste plano. Marcas iguais às do `ESTADO-ATUAL.md`: 🔬 medido · 📖 lido no código.

| A spec diz | 🔬 24/08 | Consequência para o executor |
|---|---|---|
| migrations **310 e 311** (D4: "a maior aplicada é a 309") | a maior no repo é a **314** | Use **315** e **316**. É a própria regra da D4 aplicada de novo: numerar em sequência real, nunca renumerar para "organizar" — foi assim que nasceu o fantasma do 270 |
| `scripts/medir_producao.py` "ganha uma **sétima** pergunta" | 📖 o arquivo já tem `q1`..`q7` (a q7 é pontos duplicados no dia) | A pergunta nova é a **q8** |
| "as **28** contas do canônico" | 🔬 `_V2_CONTAS_SEED` tem **35** linhas | O seed de classificação da Task 5 cobre **35** contas. A tabela deste plano lista as 35 |
| `PlanoContas` em `models.py:3234`, `PartidaContabil` em `:3332` | 📖 **3247** e **3345** | Deriva de edições posteriores. Ancore por nome de classe, não por linha |

## Global Constraints

- **Nada de flag de comportamento.** A fase não muda comportamento: conserta significado de dado e acrescenta leitura. Não introduza `feature flag` nenhuma.
- **Nenhuma coluna nova em `partida_contabil` nem em `lancamento_contabil`.** Tudo o que DFC, margem e indicadores precisam já está lá (`conta_codigo`, `admin_id`, `tipo_partida`, `valor`).
- **Nenhuma partida é apagada ou somada.** Se um código `5.x` não tiver destino explícito, a migration **falha e nomeia o código**. Nunca chuta.
- **Conta nunca é apagada.** `5.x` sem partida vira `ativo = False` — relatório histórico aponta para ela.
- **Relatório não esconde o que não sabe.** Não classificado aparece **como não classificado, com o valor**. DFC que não fecha **mostra a diferença**. Indicador sem base sai como "sem base", nunca `0%` nem `inf`.
- **Todo indicador na tela exibe data-base e as contas que o compõem.** Número sem procedência é o defeito de fabricação que abre o `ESTADO-ATUAL.md`.
- **`classificacao_gasto`** — `VARCHAR(12)`, NOT NULL, default `'nao_classificado'`. Valores: `fixo` | `variavel` | `nao_aplicavel` | `nao_classificado`.
- **`atividade_dfc`** — `VARCHAR(14)`, NOT NULL, default `'operacional'`. Valores: `operacional` | `investimento` | `financiamento`.
- **Migrations 315 e 316**, registradas **na ordem** na tupla de `migrations.py`. O runner governa pela ordem da tupla, não pelo máximo do repo. Toda migration é provada idempotente por **dupla execução** no banco de dev antes do commit.
- **TDD sem exceção.** Teste primeiro, RED conferido e citado no commit, depois o código.

---

## 🔴 Bloqueios antes de começar

**1. Task 1 é humana e é pré-requisito de D2.** A Task 1 mede produção. Sem ela, a Task 4 (de-para) está sendo decidida com número de banco de dev — que é 99,9% resíduo de suíte. Se produção mostrar `5.x` dominante, **esta spec está errada** e o canônico volta à mesa.

**2. Há uma decisão nova, D6, que a spec não previu. Ela bloqueia a Task 4.** Ver abaixo.

### 🔴 D6 (NOVA) — o de-para não pode ser chaveado só por código

A spec manda escrever o de-para "conta a conta, à mão, **não** derivado por heurística de nome", porque "os nomes são justamente o que está inconsistente". 🔬 Ao extrair os dois seeders concorrentes para montar a tabela, o problema aparece:

| Código | `contabilidade_utils.criar_plano_contas_padrao` | `financeiro_seeds.PLANO_CONTAS_CONSTRUCAO` |
|---|---|---|
| `5` | CUSTOS | DESPESAS |
| `5.1` | CUSTO DOS SERVIÇOS PRESTADOS | DESPESAS OPERACIONAIS |
| **`5.1.01`** | **Materiais Diretos** | **MÃO DE OBRA** |
| **`5.1.02`** | **Mão de Obra Direta** | **MATERIAIS** |
| `5.2` / `5.1.03`+ | CUSTOS INDIRETOS, Materiais Indiretos | EQUIPAMENTOS, VEÍCULOS, ADMINISTRATIVAS |

**`5.1.01` e `5.1.02` estão trocados entre os dois planos.** Um de-para chaveado só em `codigo` mandaria material para pessoal em metade do parque — e o erro seria silencioso, porque a partida migraria sem falhar.

**A única evidência sobrevivente de qual seeder rodou é `plano_contas.nome`.** Ou seja: a spec proíbe usar o nome, e sem o nome a Task 4 não é executável corretamente.

*Recomendado:* chavear o de-para em **`(codigo, nome)` com igualdade exata** contra os dois conjuntos fechados que estão **no repositório** — não é heurística de nome, é reconhecer a assinatura de um dos dois seeders conhecidos. Qualquer `(codigo, nome)` fora dos dois conjuntos **faz a migration falhar e nomear o par**. Isso preserva o espírito da regra ("nunca chutar") e resolve a colisão; derivar por semelhança de string (`'MÃO DE OBRA' ≈ 'Mão de Obra Direta'`) continua **proibido**.

⚠️ **Não execute a Task 4 sem o Cássio julgar a D6.** As Tasks 1, 2, 3 e 5 a 10 não dependem dela e podem correr antes.

---

## Onde a fase pode ser cortada em duas

Se a fase inteira for grande demais para uma branch só, o corte natural é **depois da Task 6**: Tasks 1–6 são a fundação (significado do dado + margem) e produzem software testável sozinho; Tasks 7–10 são leitura nova por cima. Não corte no meio da 3–4: aposentar o semeador sem migrar as `5.x` deixa o parque em dois estados.

---

## File Structure

| Arquivo | Responsabilidade | Ação |
|---|---|---|
| `scripts/medir_producao.py` | q8: retrato de `5.x` × `6.x` em produção | Modificar |
| `models.py` (`PlanoContas`, ~3247) | as duas colunas novas | Modificar |
| `migrations.py` | 315 (colunas) e 316 (de-para) | Modificar |
| `contabilidade_utils.py` | canônico; `criar_plano_contas_padrao` marcada `EM APOSENTADORIA` | Modificar |
| `financeiro_seeds.py` | `criar_plano_contas_padrao` marcada `EM APOSENTADORIA` | Modificar |
| `contabilidade_views.py:95`, `financeiro_views.py:1329` | passam a chamar o semeador único | Modificar |
| `services/plano_contas_depara.py` | **o de-para `(codigo, nome) → codigo`**, dado puro, sem lógica | Criar |
| `services/classificacao_gasto.py` | seed de `classificacao_gasto` + `atividade_dfc` das 35 canônicas | Criar |
| `services/dfc_service.py` | DFC método direto pela contrapartida | Criar |
| `services/indicadores_service.py` | liquidez, estrutura, rentabilidade, ciclos | Criar |
| `services/exportacao_dominio.py` | exportação Domínio | Criar |
| `contabilidade_views.py` | rotas de classificação, DFC, indicadores, exportação | Modificar |
| `templates/contabilidade/{classificacao_contas,dfc,indicadores}.html` | as três telas novas | Criar |
| `tests/test_fase8_*.py` | um arquivo por task | Criar |

Por que `services/plano_contas_depara.py` é arquivo próprio e só dado: o de-para é a peça que um humano precisa **revisar linha a linha** antes da migration rodar. Misturado com lógica, ninguém revisa.

---

### Task 1 — q8 em `medir_producao.py`: o retrato de produção

🔴 **Roda contra produção, exige o humano.** O código da q8 é escrito e testado aqui; a execução é do Cássio.

**Files:**
- Modify: `scripts/medir_producao.py` (acrescenta `q8_planos_de_contas`, registra em `main()`)
- Test: `tests/test_fase8_medicao_q8.py`

**Interfaces:**
- Produces: `q8_planos_de_contas(cur) -> None` — imprime; segue o molde de `q1`..`q7` (usa `_t`, `_um`, `secao`).

- [ ] **Step 1: Escrever o teste que falha**

O teste roda a query da q8 contra o banco de dev por `db.engine`, sem depender do `psycopg2` direto do script.

```python
# tests/test_fase8_medicao_q8.py
"""q8 de medir_producao: quantos tenants em 5.x, 6.x, ambos, nenhum;
quantas partidas vivem em 5.x; e se existe partida órfã."""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app import app, db  # noqa: E402


def test_q8_devolve_as_tres_respostas_e_nao_inventa_orfa():
    from scripts.medir_producao import SQL_Q8_PARTIDAS_5X, SQL_Q8_PARTIDAS_ORFAS, SQL_Q8_TENANTS
    with app.app_context():
        from sqlalchemy import text
        linhas = db.session.execute(text(SQL_Q8_TENANTS)).fetchall()
        assert linhas, 'a q8 tem de devolver ao menos uma linha de retrato'
        assert {c.lower() for c in linhas[0]._mapping.keys()} >= {
            'so_5x', 'so_6x', 'ambos', 'nenhum'}

        cinco = db.session.execute(text(SQL_Q8_PARTIDAS_5X)).scalar()
        assert cinco is not None and cinco >= 0

        orfas = db.session.execute(text(SQL_Q8_PARTIDAS_ORFAS)).scalar()
        assert orfas is not None, (
            'partida órfã tem de ser CONTADA, não presumida zero — se '
            'produção divergir do dev, a fase inteira volta à mesa')
```

- [ ] **Step 2: Rodar e ver falhar**

Run: `.pythonlibs/bin/pytest tests/test_fase8_medicao_q8.py -v`
Expected: FAIL com `ImportError: cannot import name 'SQL_Q8_TENANTS'`.

- [ ] **Step 3: Escrever a q8**

As três SQL saem como constantes de módulo justamente para o teste poder rodá-las sem `psycopg2`.

```python
# scripts/medir_producao.py — junto das outras perguntas

SQL_Q8_TENANTS = """
    WITH por_tenant AS (
        SELECT admin_id,
               bool_or(codigo LIKE '5.%%') AS tem5,
               bool_or(codigo LIKE '6.%%') AS tem6
          FROM plano_contas
         GROUP BY admin_id
    )
    SELECT count(*) FILTER (WHERE tem5 AND NOT tem6) AS so_5x,
           count(*) FILTER (WHERE tem6 AND NOT tem5) AS so_6x,
           count(*) FILTER (WHERE tem5 AND tem6)     AS ambos,
           count(*) FILTER (WHERE NOT tem5 AND NOT tem6) AS nenhum
      FROM por_tenant
"""

SQL_Q8_PARTIDAS_5X = """
    SELECT count(*) FROM partida_contabil WHERE conta_codigo LIKE '5.%%'
"""

SQL_Q8_PARTIDAS_ORFAS = """
    SELECT count(*)
      FROM partida_contabil p
     WHERE NOT EXISTS (
           SELECT 1 FROM plano_contas c
            WHERE c.codigo = p.conta_codigo AND c.admin_id = p.admin_id)
"""


def q8_planos_de_contas(cur):
    """Fase 8 / Task 1 — o retrato que decide se a Task 4 é um de-para de
    algumas centenas de linhas ou um projeto próprio.

    A pergunta que importa é UMA: quantas partidas vivem em `5.x` lá.
    ⚠️ Se produção mostrar `5.x` dominante, a spec da Fase 8 está errada e o
    canônico tem de ser reavaliado ANTES de qualquer código.
    """
    secao('q8 — planos de contas concorrentes (Fase 8)')
    for linha in _t(cur, SQL_Q8_TENANTS):
        print(f'  tenants só 5.x: {linha[0]} | só 6.x: {linha[1]} | '
              f'ambos: {linha[2]} | nenhum: {linha[3]}')
    print(f'  partidas em 5.x: {_um(cur, SQL_Q8_PARTIDAS_5X)}')
    orfas = _um(cur, SQL_Q8_PARTIDAS_ORFAS)
    print(f'  partidas ÓRFÃS (conta inexistente no plano do tenant): {orfas}')
    if orfas:
        print('  🔴 dev media ZERO órfãs. Produção divergiu — PARE e reveja '
              'a spec inteira antes de escrever a migration 316.')
```

E registre a chamada em `main()`, junto das outras: `q8_planos_de_contas(cur)`.

- [ ] **Step 4: Rodar e ver passar**

Run: `.pythonlibs/bin/pytest tests/test_fase8_medicao_q8.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add scripts/medir_producao.py tests/test_fase8_medicao_q8.py
git commit -m "feat(fase8): q8 de medir_producao — o retrato de 5.x que decide o tamanho da Task 4"
```

- [ ] **Step 6: 🔴 Entregar ao humano e PARAR nesta frente**

Peça ao Cássio: `python scripts/medir_producao.py` contra produção, e cole a saída da q8 no ledger de execução. **A Task 4 não começa sem esse número.** As Tasks 2, 3, 5–10 seguem em paralelo.

---

### Task 2 — as duas colunas (migration 315)

**Files:**
- Modify: `models.py` (classe `PlanoContas`)
- Modify: `migrations.py` (`_migration_315_plano_contas_semantica` + registro na tupla)
- Test: `tests/test_fase8_colunas_semantica.py`

**Interfaces:**
- Produces: `PlanoContas.classificacao_gasto` (str) e `PlanoContas.atividade_dfc` (str), mais as constantes `PlanoContas.CLASSIFICACAO_*` e `PlanoContas.DFC_*` usadas pelas Tasks 5–8.

- [ ] **Step 1: Escrever o teste que falha**

```python
# tests/test_fase8_colunas_semantica.py
"""As duas colunas de significado: default que NÃO classifica no gasto, e
default operacional no DFC — os dois escolhidos por motivos opostos e
ambos deliberados (ver spec, 'Modelo de dados')."""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app import app, db  # noqa: E402


def test_conta_nova_nasce_nao_classificada_e_operacional():
    from models import PlanoContas
    with app.app_context():
        admin_id = _admin_de_teste()
        conta = PlanoContas(codigo='9.9.99.999', nome='Conta de teste',
                            tipo_conta='DESPESA', natureza='DEVEDORA',
                            nivel=4, aceita_lancamento=True, ativo=True,
                            admin_id=admin_id)
        db.session.add(conta)
        db.session.flush()

        assert conta.classificacao_gasto == PlanoContas.CLASSIFICACAO_NAO_CLASSIFICADO, (
            'default fixo produziria margem que parece pronta e está errada')
        assert conta.atividade_dfc == PlanoContas.DFC_OPERACIONAL, (
            'default neutro faria o DFC nascer com quase tudo fora dos três '
            'grupos — inutilizável no dia 1')
        db.session.rollback()
```

(`_admin_de_teste()` — copie o helper do arquivo de teste vizinho mais novo, `tests/test_fase6_contrato_baseline.py`, que já cria tenant próprio por teste. Não reutilize o tenant 1.)

- [ ] **Step 2: Rodar e ver falhar**

Run: `.pythonlibs/bin/pytest tests/test_fase8_colunas_semantica.py -v`
Expected: FAIL com `AttributeError: type object 'PlanoContas' has no attribute 'CLASSIFICACAO_NAO_CLASSIFICADO'`.

- [ ] **Step 3: Colunas no modelo**

```python
# models.py, dentro de class PlanoContas
    CLASSIFICACAO_FIXO = 'fixo'
    CLASSIFICACAO_VARIAVEL = 'variavel'
    CLASSIFICACAO_NAO_APLICAVEL = 'nao_aplicavel'
    CLASSIFICACAO_NAO_CLASSIFICADO = 'nao_classificado'

    DFC_OPERACIONAL = 'operacional'
    DFC_INVESTIMENTO = 'investimento'
    DFC_FINANCIAMENTO = 'financiamento'

    # Fase 8 — por TENANT e não constante de código, pelo mesmo motivo de
    # FaixaAlcada: frota é gasto fixo para quem tem frota própria e variável
    # para quem aluga por obra. Número que é regra de negócio não entra em
    # `if`. `nao_aplicavel` existe para ativo/passivo/PL/receita: sem ele,
    # "sem classificação" misturaria o que FALTA classificar com o que NUNCA
    # será, e o indicador de completude não significaria nada.
    classificacao_gasto = db.Column(db.String(12), nullable=False,
                                    default=CLASSIFICACAO_NAO_CLASSIFICADO,
                                    server_default=CLASSIFICACAO_NAO_CLASSIFICADO)
    atividade_dfc = db.Column(db.String(14), nullable=False,
                              default=DFC_OPERACIONAL,
                              server_default=DFC_OPERACIONAL)
```

- [ ] **Step 4: A migration 315**

```python
# migrations.py
def _migration_315_plano_contas_semantica():
    """Fase 8 — plano_contas ganha classificacao_gasto e atividade_dfc.

    Os defaults são escolhidos por motivos OPOSTOS e os dois de propósito:
    `nao_classificado` no gasto porque classificar por conta própria produz
    margem errada com cara de pronta; `operacional` no DFC porque na
    esmagadora maioria das contas de uma construtora é isso, e um default
    neutro faria o DFC nascer inutilizável.

    315 e não 310: a D4 da spec pediu 310 quando a maior aplicada era a 309;
    🔬 24/08 a maior do repo é a 314. A regra da própria D4 — numerar em
    sequência real, nunca renumerar para organizar — manda 315.

    Idempotente: ADD COLUMN IF NOT EXISTS.
    """
    from sqlalchemy import text as sa_text
    try:
        with db.engine.begin() as conn:
            conn.execute(sa_text("""
                ALTER TABLE plano_contas
                    ADD COLUMN IF NOT EXISTS classificacao_gasto
                        VARCHAR(12) NOT NULL DEFAULT 'nao_classificado'
            """))
            conn.execute(sa_text("""
                ALTER TABLE plano_contas
                    ADD COLUMN IF NOT EXISTS atividade_dfc
                        VARCHAR(14) NOT NULL DEFAULT 'operacional'
            """))
        logger.info('[Migration 315] plano_contas: classificacao_gasto e '
                    'atividade_dfc criadas.')
        return True
    except Exception as e:
        logger.error(f'[Migration 315] Falha: {e}', exc_info=True)
        return False
```

Registre **na ordem**, no fim da tupla:

```python
            (315, "Fase 8 — plano_contas.classificacao_gasto + atividade_dfc: a semantica que destrava margem de contribuicao e DFC", _migration_315_plano_contas_semantica),
```

- [ ] **Step 5: Rodar e ver passar, e provar idempotente**

```bash
.pythonlibs/bin/pytest tests/test_fase8_colunas_semantica.py -v
.pythonlibs/bin/python -c "from app import app; from migrations import _migration_315_plano_contas_semantica as m; app.app_context().push(); print(m(), m())"
```
Expected: PASS; e `True True` — a **dupla execução** é a prova de idempotência, não a leitura do SQL.

- [ ] **Step 6: Commit**

```bash
git add models.py migrations.py tests/test_fase8_colunas_semantica.py
git commit -m "feat(fase8): plano_contas ganha classificacao_gasto e atividade_dfc (migration 315)"
```

---

### Task 3 — um semeador só, e o guarda que impede o quarto

**Files:**
- Modify: `contabilidade_views.py:95`, `financeiro_views.py:1324-1329`
- Modify: `contabilidade_utils.py:21` e `financeiro_seeds.py:103` (marcar `EM APOSENTADORIA`)
- Test: `tests/test_fase8_semeador_unico.py`

**Interfaces:**
- Consumes: `contabilidade_utils.seed_plano_contas_if_needed(admin_id) -> None` (já existe, `:1597`).
- Produces: nenhuma assinatura nova. As duas `criar_plano_contas_padrao` continuam importáveis e **não são apagadas**.

- [ ] **Step 1: Escrever os dois testes que falham**

```python
# tests/test_fase8_semeador_unico.py
"""Dois tenants semeados por caminhos diferentes têm de receber O MESMO
plano. E um guarda por `ast` para ninguém acrescentar um quarto semeador —
mesmo molde do guarda da C9 da Fase 2, que já provou o valor dele."""
import ast
import os
import pathlib
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app import app, db  # noqa: E402

# Os DOIS lugares onde ainda é legítimo instanciar PlanoContas: o semeador
# canônico usa SQL puro, então quem sobra é a dupla em aposentadoria.
_CRIADORES_CONHECIDOS = {
    ('financeiro_seeds.py', 'criar_plano_contas_padrao'),
    ('contabilidade_utils.py', 'criar_plano_contas_padrao'),
}


def test_nenhum_criador_novo_de_plano_contas():
    raiz = pathlib.Path(__file__).resolve().parent.parent
    achados = set()
    for py in raiz.rglob('*.py'):
        partes = set(py.relative_to(raiz).parts)
        if partes & {'archive', 'tests', '__pycache__', '.pythonlibs', 'backups'}:
            continue
        try:
            arvore = ast.parse(py.read_text(encoding='utf-8'))
        except SyntaxError:
            continue
        for no in ast.walk(arvore):
            if isinstance(no, ast.FunctionDef):
                for interno in ast.walk(no):
                    if (isinstance(interno, ast.Call)
                            and isinstance(interno.func, ast.Name)
                            and interno.func.id == 'PlanoContas'):
                        achados.add((py.name, no.name))
    assert achados <= _CRIADORES_CONHECIDOS, (
        'criador NOVO de PlanoContas: '
        f'{sorted(achados - _CRIADORES_CONHECIDOS)}. Para cada código, o '
        'primeiro semeador a rodar decide o significado e os outros são '
        'descartados em silêncio — é o defeito que a Fase 8 fecha.')


def test_dois_caminhos_de_semeadura_dao_o_mesmo_plano():
    from models import PlanoContas
    with app.app_context():
        a = _admin_de_teste()
        b = _admin_de_teste()

        # caminho 1: a tela de contabilidade
        with app.test_client() as c:
            _logar(c, a)
            c.get('/contabilidade/plano-contas')
        # caminho 2: o botão do financeiro
        with app.test_client() as c:
            _logar(c, b)
            c.post('/financeiro/plano-contas/inicializar')

        plano_a = {x.codigo: x.nome for x in
                   PlanoContas.query.filter_by(admin_id=a).all()}
        plano_b = {x.codigo: x.nome for x in
                   PlanoContas.query.filter_by(admin_id=b).all()}
        assert plano_a and plano_a == plano_b, (
            'dois tenants receberam planos diferentes por terem clicado em '
            f'telas diferentes — só em A: {sorted(set(plano_a) - set(plano_b))}, '
            f'só em B: {sorted(set(plano_b) - set(plano_a))}')
```

(`_logar(client, admin_id)` — copie do arquivo de teste HTTP mais novo da casa, `tests/test_fase6_aditivo.py`, que já resolve sessão e `WTF_CSRF_ENABLED=False`.)

- [ ] **Step 2: Rodar e ver falhar**

Run: `.pythonlibs/bin/pytest tests/test_fase8_semeador_unico.py -v`
Expected: `test_dois_caminhos...` FALHA com planos divergentes (`5.1.01` num, ausente no outro). O guarda por `ast` pode já passar — se passar, **está certo**: ele é rede para o futuro, não descrição de defeito atual. Registre isso no ledger em vez de forçar um RED artificial.

- [ ] **Step 3: Trocar os dois chamadores**

```python
# contabilidade_views.py, ~:95 — no lugar de criar_plano_contas_padrao(admin_id)
        # Fase 8 — semeador ÚNICO. Antes, cada tela semeava com um conteúdo
        # diferente e o primeiro a rodar decidia o que `5.1.01` significa
        # naquele tenant. Ver docs/superpowers/specs/2026-08-17-fase-8-financeiro-design.md
        from contabilidade_utils import seed_plano_contas_if_needed
        seed_plano_contas_if_needed(admin_id)
```

```python
# financeiro_views.py, ~:1324 — no lugar do import e da chamada
        # Fase 8 — semeador ÚNICO (ver contabilidade_views.py e a spec).
        from contabilidade_utils import seed_plano_contas_if_needed
        seed_plano_contas_if_needed(admin_id)
        contas_criadas = PlanoContas.query.filter_by(admin_id=admin_id).count()
```

- [ ] **Step 4: Marcar as duas em aposentadoria (sem apagar)**

No topo da docstring de **ambas** as `criar_plano_contas_padrao`:

```python
    ⚠️ EM APOSENTADORIA (Fase 8, 2026-08-24). Não tem mais chamador vivo.
    NÃO É APAGADA de propósito: remover a função e mudar o leitor no mesmo
    release são duas mudanças difíceis de bissetar juntas — mesma decisão
    da AlocacaoEquipe no p7. O semeador vivo é
    `contabilidade_utils.seed_plano_contas_if_needed`.
    Spec: docs/superpowers/specs/2026-08-17-fase-8-financeiro-design.md
```

- [ ] **Step 5: Rodar e ver passar**

Run: `.pythonlibs/bin/pytest tests/test_fase8_semeador_unico.py -v`
Expected: PASS nos dois.

- [ ] **Step 6: Commit**

```bash
git add contabilidade_views.py financeiro_views.py contabilidade_utils.py financeiro_seeds.py tests/test_fase8_semeador_unico.py
git commit -m "feat(fase8): um semeador so — os dois concorrentes ficam EM APOSENTADORIA, com guarda por ast"
```

---

### Task 4 — 🔴 o de-para das `5.x` (migration 316). **Bloqueada por D6 e pela Task 1.**

Único ponto da fase que toca dado histórico.

**Files:**
- Create: `services/plano_contas_depara.py`
- Modify: `migrations.py` (`_migration_316_depara_contas_5x` + registro)
- Test: `tests/test_fase8_depara_5x.py`

**Interfaces:**
- Produces: `DEPARA_5X: dict[tuple[str, str], str]` — chave `(codigo, nome)`, valor o código canônico de destino. E `CONTAS_5X_CONHECIDAS: set[str]`.

- [ ] **Step 1: Escrever o de-para como dado revisável**

```python
# services/plano_contas_depara.py
"""De-para das contas 5.x para o canônico (Fase 8, Task 4).

Chaveado em (codigo, NOME) e não só em codigo — decisão D6. Os dois
seeders aposentados TROCAM o significado de 5.1.01 e 5.1.02 entre si:

    5.1.01 = 'Materiais Diretos' (contabilidade_utils)
    5.1.01 = 'MÃO DE OBRA'       (financeiro_seeds)

Um de-para por código mandaria material para pessoal em metade do parque,
e o erro seria SILENCIOSO — a partida migraria sem falhar. O nome é a única
evidência sobrevivente de qual seeder rodou naquele tenant.

Isto NÃO é heurística de nome: é igualdade exata contra dois conjuntos
fechados que estão no repositório. Semelhança de string é proibida.
Par desconhecido => a migration FALHA e nomeia o par. Nunca chuta.
"""

DEPARA_5X: dict[tuple[str, str], str] = {
    # --- assinatura de contabilidade_utils.criar_plano_contas_padrao ---
    ('5.1.01', 'Materiais Diretos'):        '6.1.02.003',  # Despesa com Material
    ('5.1.02', 'Mão de Obra Direta'):       '6.1.01.001',  # Despesa com Salários
    ('5.2.01', 'Materiais Indiretos'):      '6.1.02.003',
    # --- assinatura de financeiro_seeds.PLANO_CONTAS_CONSTRUCAO ---
    ('5.1.01.001', 'Salários'):             '6.1.01.001',
    ('5.1.01.002', 'Encargos Sociais'):     '6.1.01.001',
    ('5.1.01.003', 'Vale Transporte'):      '6.1.02.002',  # Despesa com Transporte
    ('5.1.01.004', 'Vale Alimentação'):     '6.1.01.002',  # Despesa com Alimentação
    ('5.1.02.001', 'Material de Construção'): '6.1.02.003',
    ('5.1.02.002', 'Ferramentas'):          '6.1.02.003',
    ('5.1.02.003', 'EPIs'):                 '6.1.02.003',
    ('5.1.03.001', 'Aluguel de Equipamentos'): '6.1.02.003',
    ('5.1.03.002', 'Manutenção de Equipamentos'): '6.1.02.003',
    ('5.1.04.001', 'Combustível'):          '6.1.02.001',  # Despesa com Combustível
    ('5.1.04.002', 'Manutenção de Veículos'): '6.1.02.001',
    ('5.1.04.003', 'IPVA e Licenciamento'): '6.1.02.001',
    ('5.1.05.001', 'Material de Escritório'): '6.1.02.003',
    ('5.1.05.002', 'Telefone e Internet'):  '6.1.02.003',
    ('5.1.05.003', 'Energia Elétrica'):     '6.1.02.003',
    ('5.1.05.004', 'Água e Esgoto'):        '6.1.02.003',
}

# Sintéticas (aceita_lancamento=False): nunca têm partida, então não
# entram no de-para — só são desativadas.
CONTAS_5X_SINTETICAS = {
    '5', '5.1', '5.2', '5.1.01', '5.1.02', '5.1.03', '5.1.04', '5.1.05',
}
```

⚠️ **Este arquivo é para o Cássio revisar linha a linha antes de a migration rodar.** Os destinos acima são a recomendação do executor, não decisão tomada: `Ferramentas`, `EPIs` e `Aluguel de Equipamentos` caindo todos em `Despesa com Material` é a escolha mais discutível da tabela.

- [ ] **Step 2: Escrever o teste que falha**

```python
# tests/test_fase8_depara_5x.py
"""O de-para não pode perder nem somar partida, e tem de FALHAR ruidosamente
diante de um código que não conhece."""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app import app, db  # noqa: E402


def test_depara_preserva_a_contagem_e_a_soma():
    from sqlalchemy import text
    from migrations import _migration_316_depara_contas_5x
    with app.app_context():
        admin_id = _tenant_com_partidas_em_5x()   # helper do próprio arquivo
        antes_n = db.session.execute(text(
            'SELECT count(*) FROM partida_contabil WHERE admin_id=:a'),
            {'a': admin_id}).scalar()
        antes_soma = db.session.execute(text(
            'SELECT coalesce(sum(valor),0) FROM partida_contabil WHERE admin_id=:a'),
            {'a': admin_id}).scalar()

        assert _migration_316_depara_contas_5x() is True

        depois_n = db.session.execute(text(
            'SELECT count(*) FROM partida_contabil WHERE admin_id=:a'),
            {'a': admin_id}).scalar()
        depois_soma = db.session.execute(text(
            'SELECT coalesce(sum(valor),0) FROM partida_contabil WHERE admin_id=:a'),
            {'a': admin_id}).scalar()
        restantes = db.session.execute(text(
            "SELECT count(*) FROM partida_contabil "
            "WHERE admin_id=:a AND conta_codigo LIKE '5.%'"),
            {'a': admin_id}).scalar()

        assert depois_n == antes_n, 'partida sumiu ou foi duplicada'
        assert depois_soma == antes_soma, 'a soma mudou — valor foi somado 2x'
        assert restantes == 0, 'sobrou partida em 5.x depois do de-para'


def test_codigo_sem_destino_faz_a_migration_falhar_e_nomear():
    from sqlalchemy import text
    from migrations import _migration_316_depara_contas_5x
    with app.app_context():
        admin_id = _tenant_com_partida_em_codigo_desconhecido('5.9.99')
        assert _migration_316_depara_contas_5x() is False, (
            'código sem destino tem de FALHAR — ficar failed e retentar a '
            'cada boot é o comportamento certo (a lição da 279/309)')
        sobrou = db.session.execute(text(
            "SELECT count(*) FROM partida_contabil "
            "WHERE admin_id=:a AND conta_codigo='5.9.99'"),
            {'a': admin_id}).scalar()
        assert sobrou == 1, 'a migration falhou mas mexeu no dado assim mesmo'


def test_conta_5x_sem_partida_e_desativada_e_nao_apagada():
    from models import PlanoContas
    from migrations import _migration_316_depara_contas_5x
    with app.app_context():
        admin_id = _tenant_com_5x_sem_partida()
        _migration_316_depara_contas_5x()
        conta = PlanoContas.query.filter_by(
            admin_id=admin_id, codigo='5.1.03').first()
        assert conta is not None, (
            'conta de plano de contas NUNCA é apagada — relatório histórico '
            'aponta para ela')
        assert conta.ativo is False
```

- [ ] **Step 3: Rodar e ver falhar**

Run: `.pythonlibs/bin/pytest tests/test_fase8_depara_5x.py -v`
Expected: FAIL com `ImportError: cannot import name '_migration_316_depara_contas_5x'`.

- [ ] **Step 4: A migration 316**

```python
# migrations.py
def _migration_316_depara_contas_5x():
    """Fase 8 / Task 4 — reescreve partida_contabil.conta_codigo das 5.x
    para o canônico, e desativa as 5.x sem partida.

    TRANSAÇÃO ÚNICA com contagem antes e depois. A lição da migração 218
    (Fase 0.6) vale aqui: numa troca de significado, a ordem dos atos decide
    se o backfill é real ou no-op silencioso.

    Chaveia em (codigo, nome) — D6. Par desconhecido => FALHA e nomeia.
    Ficar 'failed' e retentar a cada boot é o comportamento certo; é o que a
    279 deveria ter feito e não fez (lição da 309).

    Nenhuma partida é apagada ou somada. Nenhuma conta é apagada.
    """
    from sqlalchemy import text as sa_text

    from services.plano_contas_depara import CONTAS_5X_SINTETICAS, DEPARA_5X
    try:
        with db.engine.begin() as conn:
            antes = conn.execute(sa_text(
                'SELECT count(*), coalesce(sum(valor),0) FROM partida_contabil'
            )).one()

            # 1. Todo par (codigo, nome) que tem partida viva precisa de destino.
            pares = conn.execute(sa_text("""
                SELECT DISTINCT p.conta_codigo, c.nome, p.admin_id
                  FROM partida_contabil p
                  JOIN plano_contas c
                    ON c.codigo = p.conta_codigo AND c.admin_id = p.admin_id
                 WHERE p.conta_codigo LIKE '5.%'
            """)).fetchall()
            sem_destino = [(cod, nome) for (cod, nome, _aid) in pares
                           if (cod, nome) not in DEPARA_5X]
            if sem_destino:
                raise RuntimeError(
                    'de-para incompleto — pares (codigo, nome) SEM destino: '
                    f'{sorted(sem_destino)}. A migração não chuta: '
                    'acrescente o destino em services/plano_contas_depara.py '
                    'e deixe esta migração retentar no próximo boot.')

            # 2. Reescreve, par a par, dentro da MESMA transação.
            for (cod, nome, aid) in pares:
                conn.execute(sa_text("""
                    UPDATE partida_contabil SET conta_codigo = :destino
                     WHERE admin_id = :aid AND conta_codigo = :cod
                       AND EXISTS (SELECT 1 FROM plano_contas c
                                    WHERE c.admin_id = :aid
                                      AND c.codigo = :cod AND c.nome = :nome)
                """), {'destino': DEPARA_5X[(cod, nome)], 'aid': aid,
                       'cod': cod, 'nome': nome})

            # 3. Contagem e soma têm de bater. Se não baterem, tudo volta.
            depois = conn.execute(sa_text(
                'SELECT count(*), coalesce(sum(valor),0) FROM partida_contabil'
            )).one()
            if (antes[0], antes[1]) != (depois[0], depois[1]):
                raise RuntimeError(
                    f'contagem/soma mudaram no de-para: {antes} -> {depois}')

            # 4. 5.x sem partida: desativa. NUNCA apaga.
            conn.execute(sa_text("""
                UPDATE plano_contas c SET ativo = false
                 WHERE c.codigo LIKE '5.%'
                   AND NOT EXISTS (SELECT 1 FROM partida_contabil p
                                    WHERE p.admin_id = c.admin_id
                                      AND p.conta_codigo = c.codigo)
            """))
            sobraram = conn.execute(sa_text(
                "SELECT count(*) FROM partida_contabil "
                "WHERE conta_codigo LIKE '5.%'")).scalar()
            if sobraram:
                raise RuntimeError(
                    f'{sobraram} partidas continuam em 5.x depois do de-para')

        logger.info(f'[Migration 316] de-para 5.x concluído; {len(pares)} '
                    f'pares migrados, contagem e soma conferidas: {antes}.')
        return True
    except Exception as e:
        logger.error(f'[Migration 316] Falha (nada foi gravado): {e}',
                     exc_info=True)
        return False
```

Registre **na ordem**, depois da 315:

```python
            (316, "Fase 8 — de-para das contas 5.x para o canonico, chaveado por (codigo, nome); 5.x sem partida desativada", _migration_316_depara_contas_5x),
```

Note que `CONTAS_5X_SINTETICAS` é importada e não usada no passo 4 — a query cobre sintéticas e analíticas pelo mesmo `NOT EXISTS`. Ou use o conjunto num `assert` de sanidade, ou remova o import; **não deixe import morto** (o `ruff` da casa reclama e o gate mede violações acrescentadas).

- [ ] **Step 5: Rodar, ver passar, provar idempotente**

```bash
.pythonlibs/bin/pytest tests/test_fase8_depara_5x.py -v
.pythonlibs/bin/python -c "from app import app; from migrations import _migration_316_depara_contas_5x as m; app.app_context().push(); print(m(), m())"
```
Expected: PASS nos três; `True True` na dupla execução (a segunda não acha par nenhum e é no-op).

- [ ] **Step 6: Commit**

```bash
git add services/plano_contas_depara.py migrations.py tests/test_fase8_depara_5x.py
git commit -m "feat(fase8): de-para das 5.x chaveado por (codigo, nome) — migration 316, transacao unica, falha ruidosa"
```

---

### Task 5 — o seed de classificação e a tela de edição por tenant

**Files:**
- Create: `services/classificacao_gasto.py`
- Create: `templates/contabilidade/classificacao_contas.html`
- Modify: `contabilidade_views.py` (rotas `GET/POST /contabilidade/classificacao-contas`)
- Test: `tests/test_fase8_classificacao.py`

**Interfaces:**
- Produces:
  - `SEED_CLASSIFICACAO: dict[str, tuple[str, str]]` — `codigo -> (classificacao_gasto, atividade_dfc)`
  - `aplicar_seed_classificacao(admin_id: int) -> int` — devolve quantas contas classificou; **só toca conta em `nao_classificado`**, nunca sobrescreve escolha do tenant.

- [ ] **Step 1: O seed das 35 canônicas**

🔬 São **35**, não 28 (a spec envelheceu). Ativo, passivo, PL e receita levam `nao_aplicavel` — sem isso, "conta sem classificação" misturaria o que falta classificar com o que nunca será.

```python
# services/classificacao_gasto.py
"""Seed de classificacao_gasto × atividade_dfc para o plano canônico.

Só classifica conta que está em `nao_classificado`: escolha de tenant
nunca é sobrescrita por seed. O padrão erra para `nao_classificado` onde
não há consenso óbvio (D3) — o que não pode é o sistema decidir por conta
própria e o empresário descobrir depois que a margem dele saiu de uma
premissa que ele não viu.
"""
from models import PlanoContas as _PC

_FIXO, _VAR = _PC.CLASSIFICACAO_FIXO, _PC.CLASSIFICACAO_VARIAVEL
_NA, _NC = _PC.CLASSIFICACAO_NAO_APLICAVEL, _PC.CLASSIFICACAO_NAO_CLASSIFICADO
_OP, _INV, _FIN = _PC.DFC_OPERACIONAL, _PC.DFC_INVESTIMENTO, _PC.DFC_FINANCIAMENTO

SEED_CLASSIFICACAO: dict[str, tuple[str, str]] = {
    # Ativo, passivo, PL e receita: nao_aplicavel no gasto.
    '1': (_NA, _OP), '1.1': (_NA, _OP), '1.1.01': (_NA, _OP),
    '1.1.02': (_NA, _OP), '1.1.03': (_NA, _OP),
    '1.1.01.001': (_NA, _OP), '1.1.01.002': (_NA, _OP),
    '1.1.02.001': (_NA, _OP), '1.1.03.001': (_NA, _OP),
    '2': (_NA, _OP), '2.1': (_NA, _OP), '2.1.01': (_NA, _OP),
    '2.1.02': (_NA, _OP), '2.1.03': (_NA, _OP),
    '2.1.01.001': (_NA, _OP), '2.1.02.001': (_NA, _OP),
    '2.1.02.002': (_NA, _OP), '2.1.02.003': (_NA, _OP),
    '2.1.03.001': (_NA, _OP),
    '4': (_NA, _OP), '4.1': (_NA, _OP), '4.2': (_NA, _OP),
    '4.1.01': (_NA, _OP), '4.2.01': (_NA, _OP),
    '4.1.01.001': (_NA, _OP), '4.2.01.001': (_NA, _OP),
    # Despesas: aqui a classificação significa alguma coisa.
    '6': (_NC, _OP), '6.1': (_NC, _OP),
    '6.1.01': (_NC, _OP), '6.1.02': (_NC, _OP),
    # Salários e alimentação de equipe de obra: VARIÁVEIS numa construtora
    # que dimensiona equipe por obra. Tenant que mantém equipe fixa muda na
    # tela — é exatamente o caso que motivou a coluna ser por tenant.
    '6.1.01.001': (_VAR, _OP),
    '6.1.01.002': (_VAR, _OP),
    # Combustível e transporte acompanham a obra.
    '6.1.02.001': (_VAR, _OP),
    '6.1.02.002': (_VAR, _OP),
    '6.1.02.003': (_VAR, _OP),
}


def aplicar_seed_classificacao(admin_id: int) -> int:
    """Classifica as contas canônicas AINDA não classificadas do tenant.

    Devolve quantas mudaram. Não commita — quem chama decide a transação.
    """
    from app import db
    alteradas = 0
    contas = (_PC.query
              .filter_by(admin_id=admin_id)
              .filter(_PC.classificacao_gasto == _NC)
              .all())
    for conta in contas:
        par = SEED_CLASSIFICACAO.get(conta.codigo)
        if par is None:
            continue          # conta avulsa do tenant: fica nao_classificado
        conta.classificacao_gasto, conta.atividade_dfc = par
        alteradas += 1
    return alteradas
```

- [ ] **Step 2: O teste que falha**

```python
# tests/test_fase8_classificacao.py
def test_seed_classifica_canonicas_e_nao_toca_escolha_do_tenant():
    from models import PlanoContas
    from services.classificacao_gasto import aplicar_seed_classificacao
    with app.app_context():
        admin_id = _admin_com_plano_canonico()
        combustivel = PlanoContas.query.filter_by(
            admin_id=admin_id, codigo='6.1.02.001').first()
        combustivel.classificacao_gasto = PlanoContas.CLASSIFICACAO_FIXO
        db.session.flush()

        aplicar_seed_classificacao(admin_id)
        db.session.flush()

        salarios = PlanoContas.query.filter_by(
            admin_id=admin_id, codigo='6.1.01.001').first()
        assert salarios.classificacao_gasto == PlanoContas.CLASSIFICACAO_VARIAVEL
        assert combustivel.classificacao_gasto == PlanoContas.CLASSIFICACAO_FIXO, (
            'o seed sobrescreveu a escolha do tenant — a coluna existe '
            'justamente porque empresas classificam o mesmo gasto de formas '
            'diferentes e legítimas')


def test_conta_avulsa_do_tenant_fica_nao_classificada_e_aparece_na_tela():
    from models import PlanoContas
    from services.classificacao_gasto import aplicar_seed_classificacao
    with app.app_context():
        admin_id = _admin_com_plano_canonico()
        db.session.add(PlanoContas(
            codigo='6.1.02.900', nome='Conta avulsa do cliente',
            tipo_conta='DESPESA', natureza='DEVEDORA', nivel=4,
            aceita_lancamento=True, ativo=True, admin_id=admin_id))
        db.session.flush()
        aplicar_seed_classificacao(admin_id)
        db.session.flush()
        avulsa = PlanoContas.query.filter_by(
            admin_id=admin_id, codigo='6.1.02.900').first()
        assert avulsa.classificacao_gasto == PlanoContas.CLASSIFICACAO_NAO_CLASSIFICADO
```

- [ ] **Step 3: Rodar e ver falhar** — `ModuleNotFoundError: services.classificacao_gasto`.

- [ ] **Step 4: A tela, no molde de `/configuracoes/alcadas`**

Rota `GET` lista as contas do tenant com dois `<select>` por linha (`classificacao_gasto`, `atividade_dfc`), ordenadas por código, com as `nao_classificado` **no topo** e um contador "N de M contas classificadas". `POST` grava o que mudou e volta com flash. Autorização: o mesmo decorador que `/configuracoes/alcadas` usa — **não invente um novo**; leia `contabilidade_views.py` e copie o padrão vizinho.

- [ ] **Step 5: Rodar e ver passar** — os dois testes verdes.

- [ ] **Step 6: Commit**

```bash
git add services/classificacao_gasto.py templates/contabilidade/classificacao_contas.html contabilidade_views.py tests/test_fase8_classificacao.py
git commit -m "feat(fase8): seed de classificacao das 35 canonicas + tela de edicao por tenant"
```

---

### Task 6 — DRE Gerencial com margem de contribuição

**Files:**
- Modify: `contabilidade_utils.py` (nova `calcular_dre_gerencial`, ao lado de `calcular_dre_mensal`)
- Modify: `templates/contabilidade/` (a tela do DRE ganha o bloco gerencial)
- Test: `tests/test_fase8_margem_contribuicao.py`

**Interfaces:**
- Produces: `calcular_dre_gerencial(admin_id, data_inicio, data_fim) -> dict` com as chaves `receita_liquida`, `custos_variaveis`, `margem_contribuicao`, `margem_percentual`, `custos_fixos`, `resultado`, `nao_classificado`, `tem_base`.

- [ ] **Step 1: O teste que falha, com um caso conferido na calculadora**

```python
# tests/test_fase8_margem_contribuicao.py
def test_margem_de_contribuicao_de_um_caso_montado_a_mao():
    """Receita 100.000, variáveis 60.000, fixos 25.000.
    Margem = 40.000 (40%); resultado = 15.000."""
    from contabilidade_utils import calcular_dre_gerencial
    with app.app_context():
        admin_id = _tenant_com_lancamentos(receita=100000, variavel=60000,
                                           fixo=25000)
        dre = calcular_dre_gerencial(admin_id, date(2026, 8, 1), date(2026, 8, 31))
        assert float(dre['margem_contribuicao']) == pytest.approx(40000.0)
        assert float(dre['margem_percentual']) == pytest.approx(40.0)
        assert float(dre['resultado']) == pytest.approx(15000.0)


def test_nao_classificado_aparece_em_linha_propria_com_o_valor():
    from contabilidade_utils import calcular_dre_gerencial
    with app.app_context():
        admin_id = _tenant_com_lancamentos(receita=100000, variavel=60000,
                                           fixo=25000, nao_classificado=5000)
        dre = calcular_dre_gerencial(admin_id, date(2026, 8, 1), date(2026, 8, 31))
        assert float(dre['nao_classificado']) == pytest.approx(5000.0), (
            'relatório que esconde o que não sabe classificar é relatório '
            'que mente devagar')


def test_sem_receita_no_periodo_a_margem_e_sem_base_e_nao_zero_por_cento():
    from contabilidade_utils import calcular_dre_gerencial
    with app.app_context():
        admin_id = _tenant_com_lancamentos(receita=0, variavel=1000, fixo=0)
        dre = calcular_dre_gerencial(admin_id, date(2026, 8, 1), date(2026, 8, 31))
        assert dre['tem_base'] is False
        assert dre['margem_percentual'] is None, (
            '0% diria "a empresa não tem margem"; a verdade é "não há base '
            'para calcular"')


def test_mutacao_classificar_tudo_como_fixo_mata_o_teste_da_margem():
    """Guarda de mutação: se a margem ignorasse classificacao_gasto, este
    teste passaria junto com o primeiro. Ele tem de DIVERGIR."""
    from contabilidade_utils import calcular_dre_gerencial
    from models import PlanoContas
    with app.app_context():
        admin_id = _tenant_com_lancamentos(receita=100000, variavel=60000,
                                           fixo=25000)
        PlanoContas.query.filter_by(admin_id=admin_id).update(
            {'classificacao_gasto': PlanoContas.CLASSIFICACAO_FIXO})
        db.session.flush()
        dre = calcular_dre_gerencial(admin_id, date(2026, 8, 1), date(2026, 8, 31))
        assert float(dre['margem_contribuicao']) == pytest.approx(100000.0), (
            'com tudo fixo não há custo variável: a margem tem de ser a '
            'receita inteira. Se este número continuar 40.000, a margem não '
            'está lendo classificacao_gasto')
```

- [ ] **Step 2: Rodar e ver falhar** — `ImportError: cannot import name 'calcular_dre_gerencial'`.

- [ ] **Step 3: Implementar** — agregue `PartidaContabil` por `classificacao_gasto` no período, via `JOIN plano_contas ON (codigo, admin_id)`. `margem_percentual` só existe se `receita_liquida > 0`; senão `None` e `tem_base = False`.

- [ ] **Step 4: Rodar e ver passar** — os quatro verdes, **incluindo o de mutação**.

- [ ] **Step 5: Commit**

```bash
git add contabilidade_utils.py templates/contabilidade tests/test_fase8_margem_contribuicao.py
git commit -m "feat(fase8): DRE gerencial — margem de contribuicao, com linha propria para o nao classificado"
```

---

### Task 7 — DFC pelos três grupos, método direto

**Files:**
- Create: `services/dfc_service.py`
- Create: `templates/contabilidade/dfc.html`
- Modify: `contabilidade_views.py` (rota `/contabilidade/dfc`)
- Test: `tests/test_fase8_dfc.py`

**Interfaces:**
- Produces: `montar_dfc(admin_id, data_inicio, data_fim) -> dict` com `operacional`, `investimento`, `financiamento`, `variacao_caixa`, `diferenca`, `fecha` (bool).

- [ ] **Step 1: O teste que falha — e ele soma os três e compara**

```python
# tests/test_fase8_dfc.py
def test_os_tres_grupos_somam_a_variacao_de_caixa():
    from services.dfc_service import montar_dfc
    with app.app_context():
        admin_id = _tenant_com_movimento_de_caixa()
        dfc = montar_dfc(admin_id, date(2026, 8, 1), date(2026, 8, 31))
        soma = (dfc['operacional'] + dfc['investimento'] + dfc['financiamento'])
        assert soma == pytest.approx(dfc['variacao_caixa'])
        assert dfc['fecha'] is True


def test_quando_nao_fecha_a_diferenca_e_mostrada_e_nao_escondida():
    from services.dfc_service import montar_dfc
    with app.app_context():
        admin_id = _tenant_com_partida_de_caixa_sem_contrapartida()
        dfc = montar_dfc(admin_id, date(2026, 8, 1), date(2026, 8, 31))
        assert dfc['fecha'] is False
        assert dfc['diferenca'] != 0, (
            'DFC que não fecha tem de MOSTRAR a diferença; esconder é o '
            'defeito que o residual "outras" do DRE já evitou uma vez')
```

- [ ] **Step 2: Rodar e ver falhar** — `ModuleNotFoundError: services.dfc_service`.

- [ ] **Step 3: Implementar pelo método direto**

Para cada lançamento que toca `1.1.01.x` ou `1.1.02.x`, a natureza do movimento vem da **outra perna** da partida — `plano_contas.atividade_dfc` da contrapartida. 🔬 `1.1.02.001` é a conta com mais partidas do sistema (3.061 em dev), então o dado existe e é o mais denso que temos. Lançamento de caixa **sem** contrapartida entra em `diferenca`, nunca é distribuído por rateio.

- [ ] **Step 4: Rodar e ver passar.**

- [ ] **Step 5: Commit**

```bash
git add services/dfc_service.py templates/contabilidade/dfc.html contabilidade_views.py tests/test_fase8_dfc.py
git commit -m "feat(fase8): DFC pelos tres grupos, metodo direto pela contrapartida; diferenca aparece na tela"
```

---

### Task 8 — indicadores e ciclos, cada um com procedência

**Files:**
- Create: `services/indicadores_service.py`
- Create: `templates/contabilidade/indicadores.html`
- Modify: `contabilidade_views.py` (rota `/contabilidade/indicadores`)
- Test: `tests/test_fase8_indicadores.py`

**Interfaces:**
- Produces: `calcular_indicadores(admin_id, data_base) -> list[dict]`, cada item com `nome`, `valor`, `data_base`, `contas` (lista dos códigos que o compõem), `tem_base` (bool).

| Grupo | Indicadores |
|---|---|
| Liquidez | corrente, seca |
| Estrutura | endividamento, imobilização do PL |
| Rentabilidade | margem líquida, ROE, giro do ativo |
| Ciclos | prazo médio de recebimento, de pagamento, ciclo financeiro |

- [ ] **Step 1: O teste que falha, um caso de valor conhecido por indicador**

```python
# tests/test_fase8_indicadores.py
def test_liquidez_corrente_de_um_caso_conhecido():
    """AC 200.000 / PC 80.000 = 2,5."""
    from services.indicadores_service import calcular_indicadores
    with app.app_context():
        admin_id = _tenant_com_balanco(ativo_circulante=200000,
                                       passivo_circulante=80000)
        por_nome = {i['nome']: i for i in
                    calcular_indicadores(admin_id, date(2026, 8, 31))}
        assert por_nome['liquidez_corrente']['valor'] == pytest.approx(2.5)


def test_divisao_por_zero_vira_sem_base_e_nunca_inf():
    from services.indicadores_service import calcular_indicadores
    with app.app_context():
        admin_id = _tenant_com_balanco(ativo_circulante=200000,
                                       passivo_circulante=0)
        por_nome = {i['nome']: i for i in
                    calcular_indicadores(admin_id, date(2026, 8, 31))}
        ind = por_nome['liquidez_corrente']
        assert ind['tem_base'] is False and ind['valor'] is None


def test_todo_indicador_carrega_data_base_e_as_contas_que_o_compoem():
    from services.indicadores_service import calcular_indicadores
    with app.app_context():
        admin_id = _tenant_com_balanco(ativo_circulante=200000,
                                       passivo_circulante=80000)
        for ind in calcular_indicadores(admin_id, date(2026, 8, 31)):
            assert ind['data_base'] == date(2026, 8, 31)
            assert ind['contas'], (
                f"{ind['nome']} sem procedência — indicador sem as contas que "
                'o compõem é o defeito de fabricação do ESTADO-ATUAL, agora '
                'em forma de número na tela')
```

- [ ] **Step 2: Rodar e ver falhar.**
- [ ] **Step 3: Implementar** — derivados do balanço e do DRE que já existem.
- [ ] **Step 4: Rodar e ver passar.**
- [ ] **Step 5: Commit**

```bash
git add services/indicadores_service.py templates/contabilidade/indicadores.html contabilidade_views.py tests/test_fase8_indicadores.py
git commit -m "feat(fase8): indicadores e ciclos, cada um com data-base e as contas que o compoem"
```

---

### Task 9 — exportação Domínio

**Depende da Task 4.** Exportar para a contabilidade externa um plano que significa duas coisas é exportar o defeito para fora de casa.

**Files:**
- Create: `services/exportacao_dominio.py`
- Modify: `contabilidade_views.py` (rota de download)
- Test: `tests/test_fase8_exportacao_dominio.py`

**Interfaces:**
- Produces: `exportar_dominio(admin_id, data_inicio, data_fim) -> str` — o conteúdo do arquivo no layout Domínio.

- [ ] **Step 1: 🔴 Confirmar o layout ANTES de escrever o teste.** O escopo é "inalterado" em relação ao plano original, mas o plano original é de julho e **não** traz o leiaute campo a campo. Antes de qualquer código: leia `docs/superpowers/plans/2026-07-21-fase-8-financeiro-avancado-dominio.md`, e se ele não fixar o leiaute, **pergunte ao Cássio qual versão do Domínio** o escritório contábil recebe. Escrever um exportador para um leiaute suposto é trabalho jogado fora.
- [ ] **Step 2: Teste que falha, com um lançamento de valor conhecido e o registro esperado byte a byte.**
- [ ] **Step 3: Rodar e ver falhar.**
- [ ] **Step 4: Implementar.**
- [ ] **Step 5: Rodar e ver passar.**
- [ ] **Step 6: Commit**

```bash
git add services/exportacao_dominio.py contabilidade_views.py tests/test_fase8_exportacao_dominio.py
git commit -m "feat(fase8): exportacao Dominio sobre o plano ja unificado"
```

---

### Task 10 — paridade, gate e fecho

**Este é o teste que impede a fase de reescrever o passado enquanto conserta o vocabulário.**

**Files:**
- Test: `tests/test_fase8_paridade.py`
- Modify: `ESTADO-ATUAL.md`

- [ ] **Step 1: O teste de paridade**

```python
# tests/test_fase8_paridade.py
def test_dre_e_balanco_nao_mudam_depois_da_fase_inteira():
    """Os números que JÁ existem não podem mudar. A fase conserta o
    vocabulário; o passado fica igual."""
    from contabilidade_utils import calcular_dre_mensal
    from migrations import (_migration_315_plano_contas_semantica,
                            _migration_316_depara_contas_5x)
    with app.app_context():
        admin_id = _tenant_com_historico_em_5x_e_6x()
        antes = calcular_dre_mensal(admin_id, 2026, 8)
        _migration_315_plano_contas_semantica()
        _migration_316_depara_contas_5x()
        depois = calcular_dre_mensal(admin_id, 2026, 8)
        assert antes['receita_bruta'] == depois['receita_bruta']
        assert antes['resultado_liquido'] == depois['resultado_liquido'], (
            'a fase mudou o resultado do passado — o de-para não é para '
            'corrigir números, é para corrigir significado')
```

⚠️ Se este teste falhar, **não conserte o teste**. Uma diferença aqui significa que o de-para mudou a que linha do DRE uma despesa pertence — o que pode ser legítimo (era esse o defeito) ou um erro de destino. Leve o caso ao Cássio com os dois DREs lado a lado antes de mexer em qualquer coisa.

- [ ] **Step 2: Gate completo sobre a árvore que vai ser integrada**

```bash
bash run_tests.sh --gate
```
Referência a bater: o gate do `main` do mesmo dia. Registre **passed / skipped / deselected / xfailed** e o tempo. Um gate verde só vale para a árvore em que rodou — se você mesclar o `main` depois, **rode de novo**.

- [ ] **Step 3: `ruff` medido contra a base da branch, com a MESMA config**

```bash
.pythonlibs/bin/ruff check <arquivos tocados>
```
A pergunta certa não é quantas violações existem, é **quantas você acrescentou**. Comparar configs diferentes dá número errado — já deu, na Fase 6.

- [ ] **Step 4: Dupla execução das duas migrations no banco de dev** — prova de idempotência por execução, não por leitura.

- [ ] **Step 5: `ESTADO-ATUAL.md`** — registre o fecho **e nomeie os resíduos**, em vez de dizer que ficou tudo redondo. Comece por estes, que já se sabe que vão sobrar: o leiaute Domínio se a Task 9 tiver sido cortada; as contas avulsas de tenant que continuam `nao_classificado` por desenho; e a D6, com o que foi decidido.

- [ ] **Step 6: Commit de fecho**

```bash
git add ESTADO-ATUAL.md tests/test_fase8_paridade.py
git commit -m "chore(fase8): fecho — plano de contas canonico, margem, DFC e indicadores"
```

---

## Self-review deste plano

**Cobertura da spec:** Task 1→T1 · Task 2→"Modelo de dados"+migration 310 (aqui 315) · Task 3→T2 · Task 4→T3+migration 311 (aqui 316) · Task 5→T4 (coluna, seed, tela) · Task 6→T4 (margem no DRE) · Task 7→T5 · Task 8→T6 · Task 9→T7 · Task 10→"Testes/Paridade". Todos os seis casos de borda da spec têm teste nomeado. D1, D2, D3, D4 e D5 estão respeitadas; **D6 é nova e está aberta**.

**Fora de escopo, e continua fora:** passos 4 e 5 do RFA, consolidação entre tenants, conversão de moeda, competência × caixa como opção de relatório, e a `NotaFiscal` legada × `nota_fiscal_pedido`.

**O que este plano NÃO resolve, e você deve saber antes de começar:**
1. A **D6** bloqueia a Task 4. Sem julgamento, o de-para é inexecutável sem chutar.
2. A **Task 1** é humana. Sem o número de produção, a D2 está sendo decidida com banco de dev — 99,9% resíduo de suíte.
3. O **leiaute Domínio** da Task 9 não está fixado em lugar nenhum que eu tenha encontrado.
