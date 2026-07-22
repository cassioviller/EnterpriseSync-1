# Fase 4 — Centro de Custo Obrigatório

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Fazer com que nenhum lançamento de custo do SIGE possa existir sem um destino contábil — ou uma **obra**, ou o **centro de custo administrativo do tenant** — eliminando o furo em que uma despesa salva sem obra some do orçado×real sem erro e sem alerta.

**Architecture:** O destino do custo mora no **filho** (`gestao_custo_filho`), não no pai. Isso não é acidente: `utils/financeiro_integration.py:118-131` agrupa `GestaoCustoPai` por `(admin_id, tipo_categoria, entidade, categoria_fluxo_caixa)` **sem obra nenhuma**, de propósito — o pai é o *título a pagar* de um fornecedor, e um mesmo título legitimamente carrega linhas de mais de uma obra. Por isso a Fase 4 faz três coisas diferentes: (1) cria `gestao_custo_pai.obra_id` como coluna **derivada** — a obra do documento quando ela é única, `NULL` quando o documento é multi-obra ou administrativo — para dar escopo de obra ao pai (Fase 1) e matar a subquery de `gestao_custos_views.py:122-127`; (2) cria o **centro de custo administrativo por tenant**, que é o destino legítimo de folha, estoque e despesa de escritório; (3) só então trava a invariante no banco, como um `CHECK (obra_id IS NOT NULL OR centro_custo_id IS NOT NULL)` no **filho**, em duas etapas (`NOT VALID` → `VALIDATE`), atrás de um relatório de conformidade.

**Tech Stack:** Flask 3 + Flask-Login, SQLAlchemy 2 (`models.py`), sistema de migrações próprio numerado (`migrations.py` / `run_migration_safe` / `migrations_to_run`), pytest + Playwright (`bash run_tests.sh --gate`), PostgreSQL 15.

---

## Contexto verificado no código e no banco (leia antes de começar)

Tudo abaixo foi conferido por mim em 2026-07-21, no commit `fb4147b`, lendo o arquivo ou consultando o banco de desenvolvimento via `DATABASE_URL`. Não é suposição e não é cópia de dossiê.

### O schema

| Fato | Evidência |
|---|---|
| `GestaoCustoPai` **não tem** `obra_id` — nem no modelo nem no banco | `models.py:5210-5290` (28 colunas, nenhuma de obra); `information_schema.columns` para `gestao_custo_pai` devolve as mesmas 28, sem `obra_id` |
| `GestaoCustoFilho` **tem** `obra_id`, **nullable** | `models.py:5302`; FK `gestao_custo_filho_obra_id_fkey` no banco |
| `GestaoCustoFilho` também tem `centro_custo_id` nullable (FK para `centro_custo`) e `obra_servico_custo_id` | `models.py:5303`, `models.py:5304-5309` |
| `centro_custo.codigo` é **único GLOBAL**, não por tenant | `models.py:712` (`unique=True`); banco: `centro_custo_codigo_key UNIQUE (codigo)` |
| `gestao_custo_filho` tem no banco uma coluna `tarefa_cronograma_id` que **não existe no modelo** — drift de schema, fora do escopo desta fase | `information_schema` lista 13 colunas; `models.py:5293-5320` declara 12 |
| `ObraServicoCusto.obra_id` é **NOT NULL** — o custo por etapa já nasce amarrado à obra | `models.py:5854` |
| `Obra.percentual_administracao` é `NUMERIC(5,2) NOT NULL DEFAULT 0` e é usada **só como estimativa** de rateio administrativo | `models.py:285`; consumo único em `services/resumo_custos_obra.py:348-349` (`administracao = total_proposta_orcada * pct/100`) |
| `Obra.regime_medicao` (`'fixa'`\|`'percentual'`) governa se o vínculo custo↔etapa é obrigatório | `models.py:292-296` |
| Existem **dois** modelos de centro de custo, sem relação entre si: `CentroCusto` (financeiro, `models.py:706`) e `CentroCustoContabil` (contábil, `models.py:2541`) | ambos citados; `contabilidade_utils.py:164-173` cria um `CentroCustoContabil` por obra na aprovação da proposta, com `codigo=f"OBRA_{id}"` |

### Os números (banco de DESENVOLVIMENTO, 2026-07-21)

⚠️ **Aviso de honestidade.** Estes números vêm do banco apontado por `DATABASE_URL` neste ambiente, que é o de desenvolvimento. `ESTADO-ATUAL.md:120-122` avisa que ele está dominado por carga de suíte automatizada — e a consulta confirma: 7.984 obras e centenas de tenants sintéticos. **Nenhum número aqui mede produção.** O que eles servem para provar é a *forma* do problema, não o volume.

| Consulta | Resultado |
|---|---|
| `SELECT count(*) FROM gestao_custo_pai` | **1.246** |
| Pais com ≥1 filho apontando alguma obra | **1.169 (93,8%)** |
| Pais cujos filhos apontam **mais de uma** obra | **9** |
| Pais com filhos, todos sem obra | **70** |
| Pais sem filho nenhum | **7** |
| `SELECT count(*) FROM gestao_custo_filho` | **1.823** |
| Filhos com `obra_id IS NULL` | **80 (4,4%)** — R$ 65.399,20 de R$ 8.954.985,80 |
| Origem dos 80 filhos órfãos | `lancamento_periodo_manual` 50, `pedido_compra` 24, `almoxarifado_movimento` 6 |
| Filhos órfãos com **irmão** que tem obra | **0** |
| Filhos órfãos de `pedido_compra` cujo pedido **tem** obra | **0** |
| `centro_custo`: total / com obra / tipos | 9 / 9 / **todos `tipo='obra'`** — **não existe centro administrativo** |
| `fluxo_caixa`: total / com obra / com centro de custo | 15 / 14 / **0** |
| `reembolso_funcionario`: total / com obra | 24 / **0** |
| `obra_servico_custo` / `obra_servico_custo_item` | 41.761 / 176.872 |

### 🔴 O diagnóstico do `ESTADO-ATUAL.md` está errado — e importa

`ESTADO-ATUAL.md:126-128` diz:

> `gestao_custo_pai` não tem coluna `obra_id` — 1.118 linhas 100% órfãs.

Fui à fonte. `DOSSIE-REPO.md:512` traz a linha original da tabela: `gestao_custo_pai | 1.118 | 1.118 estruturalmente | 100%`, e `DOSSIE-REPO.md:516-518` explica o "estruturalmente": **100% das linhas estão órfãs porque a coluna não existe**, não porque a informação de obra tenha se perdido. A compressão para o `ESTADO-ATUAL.md` apagou o advérbio e virou outra afirmação — a de que a obra é irrecuperável.

**Ela não é.** O vínculo mora no filho, e ele está lá:

- **1.169 de 1.246 pais (93,8%)** têm a obra recuperável por unanimidade dos filhos.
- Apenas **9** são genuinamente ambíguos (filhos em mais de uma obra) — e esses **não são erro**: são o comportamento projetado de `registrar_custo_automatico`, que reaproveita o mesmo título a pagar do mesmo fornecedor entre obras (`utils/financeiro_integration.py:118-131`).
- **77** (70 + 7) não têm de onde derivar.
- O número **1.118** também mudou: era o total de `gestao_custo_pai` no snapshot do dossiê; hoje são **1.246**. Ele nunca foi a contagem de "linhas perdidas".

Consequência direta para o plano: **não existe reconstrução arqueológica a fazer para 94% dos casos**. Existe uma coluna a criar, uma derivação determinística a rodar, e um destino a inventar para os 6% que sobram. E, principalmente: **`NOT NULL` em `gestao_custo_pai.obra_id` seria errado**, porque quebraria os 9 pais multi-obra legítimos e todo o fluxo administrativo. A obrigatoriedade tem de cair no filho.

### Onde o furo nasce hoje (produtores estruturais de órfão)

Cinco lugares no código que roda hoje criam ou permitem custo sem destino:

| Local | O que faz |
|---|---|
| `event_manager.py:223-231` | entrada de material do almoxarifado cria `GestaoCustoFilho` **sem `obra_id`** — é a origem dos 6 órfãos do tenant `Construtora Alfa` |
| `folha_pagamento_views.py:253-261` | folha de pagamento cria `GestaoCustoFilho` **sem `obra_id`** |
| `gestao_custos_views.py:467-470` | `editar_filho` **apaga** a obra de um custo já lançado (`filho.obra_id = None`) quando o campo vem vazio |
| `gestao_custos_views.py:215,281` e `:965,990,1000` | lançamento manual e edição do pai aceitam `obra_id` ausente; o template rotula o campo literalmente como **"Obra (opcional)"** (`templates/custos/gestao.html:176-178`) |
| `compras_views.py:583` | `obra_id = request.form.get('obra_id') or None` — pedido de compra sem obra é aceito, e propaga para o filho em `compras_views.py:220` |

E um consumidor que **compensa o furo com estimativa**: `services/resumo_custos_obra.py:191-206` rateia proporcionalmente ao `valor_orcado` tudo o que não tem vínculo direto com etapa. Atenção: esse rateio é **obra → etapa**, e continua legítimo depois desta fase. O que esta fase mata é o rateio implícito **empresa → obra**, que hoje é feito por omissão (o custo simplesmente não aparece em obra nenhuma).

### Chokepoint que já existe (e que é a alavanca da fase)

`utils/financeiro_integration.py:58-219` — `registrar_custo_automatico()` é o único caminho de criação de custo para **10 módulos**: `frota_views.py:637`, `alimentacao_views.py:533`, `reembolso_views.py:204`, `transporte_views.py:292,442`, `event_manager.py:369,395,423,749,830`, `services/rdo_custos.py:427,457`, `services/importacao_excel.py:656`, `views/obras.py:2238`. Fechar a porta ali fecha dez módulos de uma vez. Os que **não** passam por ele e precisam de tratamento individual são: `gestao_custos_views.py` (253/275, 1257/1275), `compras_views.py` (193/215, 314/336), `folha_pagamento_views.py:237/253`, `event_manager.py:203/223`, `services/importacao_excel.py:1138/1154 e 2353/2368`.

---

## A regra de derivação — opções, rejeições e recomendação

Esta é a decisão de negócio da fase. Levantei o que o schema **permite**, não o que seria bonito.

### O que o schema permite

| # | Caminho | Cobertura medida (dev) | Veredito |
|---|---|---|---|
| A | **Unanimidade dos filhos** → `pai.obra_id` | 1.169/1.246 = **93,8%** | ✅ adotado |
| B | **Irmão unânime**: filho órfão herda a obra do pai quando o pai é unânime | 0 hoje; regra mais forte que existe | ✅ adotado (aplica-se ao futuro) |
| C | **Origem**: `origem_tabela`/`origem_id` → `pedido_compra.obra_id`, `conta_pagar.obra_id`, `reembolso_funcionario.obra_id`, `alimentacao_lancamento.obra_id`, `lancamento_transporte.obra_id` (todas conferidas: as 5 tabelas têm a coluna) | 0 hoje (os 24 pedidos de compra correspondentes também não têm obra) | ✅ adotado |
| D | **Natureza da origem**: `folha_pagamento` e `almoxarifado_movimento` são administrativos/estoque **por construção** | 6 filhos | ✅ adotado — não é chute, é classificação correta |
| E | **Por data** (obra ativa na data do lançamento) | — | ❌ **rejeitado**. Com mais de uma obra ativa — o caso normal — é sorteio disfarçado de regra |
| F | **Por criador** (`admin_id` / `responsavel_id`) | `admin_id` é tenant, não pessoa (`models.py:5238`); `responsavel_id` só vem preenchido por compras (`compras_views.py:210`) | ❌ **rejeitado** como regra geral |
| G | **Por centro de custo já gravado** no filho | **8 de 1.823** filhos têm `centro_custo_id` | ❌ **rejeitado** — o campo está morto |
| H | **Rateio proporcional ao orçado**, como `resumo_custos_obra.py:191` faz em memória | — | ❌ **rejeitado com veemência**. Gravar rateio é transformar estimativa em dado. É exatamente a dívida que a fase existe para pagar |

### `Recomendado:` cascata determinística com destino administrativo no fim

Ordem de aplicação, do mais forte para o mais fraco, **parando no primeiro que resolve**:

1. **R1 — unanimidade dos filhos** → grava `gestao_custo_pai.obra_id`.
2. **R2 — irmão unânime** → filho órfão herda a obra do próprio pai.
3. **R3 — origem** → filho órfão herda a obra da linha de origem (5 tabelas acima).
4. **R4 — natureza da origem** → `folha_pagamento` e `almoxarifado_movimento` vão para o **centro administrativo**.
5. **R5 — resto** → **centro administrativo**, com carimbo em `observacoes` (`[FASE4:R5]`) e nome a nome no relatório para revisão humana.

E, do outro lado, a porta: `registrar_custo_automatico` e as telas de custo passam a exigir **obra OU administrativo**, sem terceira opção. O usuário escolhe "Administrativo" de propósito; ele não escapa por omissão.

**Por que o destino administrativo é uma resposta e não uma lata de lixo:** hoje o custo administrativo real não é medido em lugar nenhum — `Obra.percentual_administracao` (`models.py:285`) inventa um percentual sobre o contrato e `resumo_custos_obra.py:349` multiplica. Com um centro administrativo de verdade, o custo administrativo passa a ter valor apurado. Fechar o loop (ratear o centro administrativo real nas obras, aposentando o percentual) **não é escopo desta fase** — é da Fase 8. Esta fase só faz o dado passar a existir.

### O que fica bloqueado se ninguém decidir? Nada.

O plano segue com a recomendação adotada em todas as tarefas. As decisões abaixo estão registradas para o Cássio confirmar ou inverter, e cada uma tem um ponto de reversão barato.

---

## Decisões que precisam do Cássio

| # | Decisão | `Recomendado:` (adotado no plano) | Onde reverter |
|---|---|---|---|
| 1 | Nome e código do centro administrativo | `codigo='ADM'`, `tipo='administrativo'`, `nome='Administração — <nome da empresa>'`. O `DEVOLUTIVA.md:236` sugere "Veks Adm", mas isso chumba o nome de **um** tenant num sistema multi-tenant | `utils/centro_custo.py`, constantes no topo |
| 2 | Destino das linhas que R1-R4 não alcançam (R5) | Centro administrativo, carimbadas `[FASE4:R5]` em `observacoes` e listadas nome a nome no relatório. **Não** deixar sem destino, **não** apagar | `services/destino_custo.py::REGRA_FALLBACK` |
| 3 | Folha de pagamento é sempre administrativa? | **Sim**, por ora. A mão de obra que é custo de obra já entra por outro caminho, com obra: os filhos de origem `rdo_mao_obra` (107), `rdo_mao_obra_va` (101), `rdo_mao_obra_vt` (101) e `rdo_custo_diario` (218) **todos** têm `obra_id`. Mandar a folha para obra também seria contagem dupla | Task 9 |
| 4 | Entrada de almoxarifado é administrativa? | **Sim**. Material que entra em estoque ainda não é custo de obra — vira custo quando sai para a obra. Hoje `event_manager.py:223` grava sem destino nenhum, o que é pior que ambas as respostas | Task 9 |
| 5 | `FATURAMENTO_DIRETO` pode ser administrativo? | **Não** — é sempre de obra (é material que o cliente paga direto ao fornecedor da obra). A validação recusa administrativo nessa categoria | Task 7, `CATEGORIAS_QUE_EXIGEM_OBRA` |
| 6 | Rollout: flag por tenant (como `cronograma_mpp_ativo`) ou constraint direto? | **Constraint direto no banco**, em duas etapas (`NOT VALID` → `VALIDATE`). Invariante contábil não é preferência de tenant. As duas etapas dão o mesmo efeito prático de uma flag: a escrita nova já é barrada enquanto o histórico ainda é revisado | Task 13 |
| 7 | `gestao_custo_pai.obra_id` vira `NOT NULL` algum dia? | **Não.** Os 9 pais multi-obra são projeto, não defeito (`utils/financeiro_integration.py:118-131`). A coluna é derivada e nullable para sempre; a obrigatoriedade mora no filho | — |
| 8 | `Obra.percentual_administracao` é aposentada nesta fase? | **Não.** Fica intacta. O centro administrativo passa a apurar o custo real; substituir a estimativa pelo rateio real é Fase 8 | — |

---

## Arquivos que esta fase cria ou altera

| Arquivo | Responsabilidade |
|---|---|
| `utils/centro_custo.py` | **novo** — resolve e cria o centro administrativo de um tenant. Único lugar que sabe o código `ADM` |
| `services/destino_custo.py` | **novo** — regras puras de derivação (R1-R5) + sincronização de `pai.obra_id` |
| `scripts/backfill_destino_custo.py` | **novo** — dry-run por padrão; `--aplicar` para gravar; relatório sempre |
| `scripts/relatorio_destino_custo.py` | **novo** — relatório de conformidade; é o gate da última tarefa |
| `models.py` | `CentroCusto.__table_args__` + `codigo` sem unique global; `GestaoCustoPai.obra_id` + relationship |
| `migrations.py` | migrations **250, 251, 252, 253, 254** + registro em `migrations_to_run` |
| `utils/financeiro_integration.py` | `registrar_custo_automatico` passa a exigir destino |
| `gestao_custos_views.py` | `novo`, `editar`, `editar_filho`, `pagar` — destino obrigatório e `FluxoCaixa` com destino |
| `templates/custos/gestao.html` | "Obra (opcional)" → "Destino do custo *"; opção explícita "Administrativo" |
| `event_manager.py`, `folha_pagamento_views.py` | passam a carimbar o centro administrativo |
| `tests/test_fase4_centro_custo.py` | **novo** — centro administrativo, unicidade por tenant, coluna do pai |
| `tests/test_fase4_destino_custo.py` | **novo** — regras de derivação, backfill, portas de escrita, constraint |

**Faixa de migrações reservada: 250-259.** A maior registrada hoje é a **213** (`migrations.py:4014`); a Fase 1 ocupa 214-216 (`docs/superpowers/plans/2026-07-21-fase-1-identidade-papeis.md`). Não há colisão.

**Pré-requisito:** a Fase 1 tem de estar aplicada. Esta fase consome `utils/autorizacao.obras_visiveis()` na Task 11.

---

## Task 1: `centro_custo` — unicidade por tenant (migration 250)

**Files:**
- Modify: `models.py:706-722` (classe `CentroCusto`)
- Modify: `migrations.py` (nova função antes da linha 3773 + registro após a linha 4014)
- Test: `tests/test_fase4_centro_custo.py`

- [ ] **Step 1: Escreva o teste que falha**

Crie `tests/test_fase4_centro_custo.py`:

```python
"""Fase 4 — centro de custo administrativo por tenant.

`centro_custo.codigo` era UNIQUE GLOBAL (`models.py:712`; constraint
`centro_custo_codigo_key` no banco, conferida em 2026-07-21). Num sistema
multi-tenant isso significa que o primeiro tenant a criar o código 'ADM'
impede todos os outros. Como a Fase 4 precisa de exatamente um centro
administrativo POR TENANT, a unicidade tem de ser (admin_id, codigo).
"""
import os
import sys
import uuid
from datetime import date

import pytest
from werkzeug.security import generate_password_hash

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import main  # noqa: F401 — registra os 54 blueprints
from app import app, db
from models import CentroCusto, Cliente, Obra, TipoUsuario, Usuario

pytestmark = pytest.mark.integration


@pytest.fixture(autouse=True)
def _config():
    app.config['TESTING'] = True
    app.config['WTF_CSRF_ENABLED'] = False
    if not app.secret_key:
        app.secret_key = 'test-fase4-centro-custo'
    yield


def _admin(prefixo='f4'):
    suf = uuid.uuid4().hex[:10]
    u = Usuario(
        username=f'{prefixo}a_{suf}', email=f'{prefixo}a_{suf}@test.local',
        nome=f'Empresa {suf}',
        password_hash=generate_password_hash('Senha@2026'),
        tipo_usuario=TipoUsuario.ADMIN, ativo=True, versao_sistema='v2',
    )
    db.session.add(u)
    db.session.commit()
    return u


def _obra(admin_id, nome='Obra F4'):
    """Obra.cliente_id é NOT NULL (models.py:265) — o cliente vem junto."""
    suf = uuid.uuid4().hex[:8]
    cli = Cliente(nome=f'Cliente {suf}', admin_id=admin_id)
    db.session.add(cli)
    db.session.flush()
    o = Obra(
        nome=f'{nome} {suf}', codigo=f'F4{suf[:6].upper()}',
        cliente_id=cli.id, admin_id=admin_id,
        data_inicio=date(2026, 1, 1), ativo=True,
    )
    db.session.add(o)
    db.session.commit()
    return o


def test_dois_tenants_podem_ter_o_mesmo_codigo_de_centro_custo():
    with app.app_context():
        a1 = _admin()
        a2 = _admin()
        db.session.add(CentroCusto(
            admin_id=a1.id, codigo='ADM', nome='Administracao 1',
            tipo='administrativo', ativo=True))
        db.session.commit()
        db.session.add(CentroCusto(
            admin_id=a2.id, codigo='ADM', nome='Administracao 2',
            tipo='administrativo', ativo=True))
        db.session.commit()

        achados = CentroCusto.query.filter(
            CentroCusto.codigo == 'ADM',
            CentroCusto.admin_id.in_([a1.id, a2.id]),
        ).count()
        assert achados == 2, (
            'centro_custo.codigo ainda é único global — um tenant bloqueia o '
            'outro')


def test_mesmo_tenant_nao_repete_codigo_de_centro_custo():
    from sqlalchemy.exc import IntegrityError

    with app.app_context():
        a = _admin()
        db.session.add(CentroCusto(
            admin_id=a.id, codigo='CC900', nome='Um', tipo='obra', ativo=True))
        db.session.commit()
        db.session.add(CentroCusto(
            admin_id=a.id, codigo='CC900', nome='Dois', tipo='obra', ativo=True))
        with pytest.raises(IntegrityError):
            db.session.commit()
        db.session.rollback()


def test_um_unico_centro_administrativo_por_tenant():
    from sqlalchemy.exc import IntegrityError

    with app.app_context():
        a = _admin()
        db.session.add(CentroCusto(
            admin_id=a.id, codigo='ADM', nome='Adm', tipo='administrativo',
            ativo=True))
        db.session.commit()
        db.session.add(CentroCusto(
            admin_id=a.id, codigo='ADM2', nome='Adm bis',
            tipo='administrativo', ativo=True))
        with pytest.raises(IntegrityError):
            db.session.commit()
        db.session.rollback()
```

- [ ] **Step 2: Rode e confirme que falha**

```bash
python -m pytest tests/test_fase4_centro_custo.py -v
```

Esperado: FAIL. `test_dois_tenants_podem_ter_o_mesmo_codigo_de_centro_custo` estoura `IntegrityError: duplicate key value violates unique constraint "centro_custo_codigo_key"`; `test_um_unico_centro_administrativo_por_tenant` falha porque o segundo insert passa (não há índice parcial).

- [ ] **Step 3: Ajuste o modelo**

Em `models.py`, na `class CentroCusto` (linha 706), troque a linha 712:

```python
    codigo = db.Column(db.String(20), unique=True, nullable=False)  # CC001, CC002, etc.
```

por:

```python
    # Fase 4 — a unicidade é POR TENANT. Até 2026-07-21 esta coluna era
    # `unique=True` global (constraint `centro_custo_codigo_key`): o primeiro
    # tenant que criasse o código 'ADM' impedia todos os demais de criar o
    # deles. Ver migration 250.
    codigo = db.Column(db.String(20), nullable=False)
```

E, logo após a linha do `departamento` relationship (`models.py:722`), acrescente as constraints:

```python
    __table_args__ = (
        db.UniqueConstraint('admin_id', 'codigo',
                            name='uq_centro_custo_admin_codigo'),
        # Um único centro administrativo por tenant — o destino obrigatório
        # dos custos que não pertencem a obra nenhuma (Fase 4). Índice PARCIAL
        # porque só vale para tipo='administrativo'; centros de obra e de
        # departamento continuam podendo ser vários.
        db.Index('uq_centro_custo_administrativo', 'admin_id',
                 unique=True,
                 postgresql_where=db.text("tipo = 'administrativo'")),
    )
```

- [ ] **Step 4: Escreva a migration 250**

Em `migrations.py`, imediatamente antes de `def executar_migracoes():` (linha 3773), insira:

```python
def migration_250_centro_custo_unicidade_por_tenant():
    """Fase 4 — `centro_custo.codigo` deixa de ser único GLOBAL.

    O banco tinha `centro_custo_codigo_key UNIQUE (codigo)` (conferido em
    2026-07-21), espelhando `models.py:712`. Num sistema multi-tenant isso é
    um defeito: o primeiro tenant a usar o código 'ADM' bloqueia todos os
    outros. A Fase 4 precisa de exatamente um centro administrativo POR
    TENANT, então a unicidade passa a ser (admin_id, codigo).

    Também cria o índice único PARCIAL que garante um único centro
    `tipo='administrativo'` por tenant.

    NÃO DESTRUTIVA: se houver duplicidade de (admin_id, codigo) a migração
    não derruba a constraint antiga; loga os pares em conflito e levanta.
    `run_migration_safe` grava status 'failed' (migrations.py:194) e a
    migração é retentada no próximo boot, porque `is_migration_executed` só
    considera aplicada a que terminou com 'success' (migrations.py:83-86).
    """
    logger.info("[Migration 250] Iniciando — unicidade de centro_custo por tenant")

    duplicados = db.session.execute(text("""
        SELECT admin_id, codigo, count(*) AS n
        FROM centro_custo
        GROUP BY admin_id, codigo
        HAVING count(*) > 1
        ORDER BY n DESC
        LIMIT 50
    """)).fetchall()
    if duplicados:
        for admin_id, codigo, n in duplicados:
            logger.error(
                "[Migration 250] CONFLITO admin_id=%s codigo=%s ocorre %s vezes",
                admin_id, codigo, n)
        raise RuntimeError(
            f"[Migration 250] {len(duplicados)} par(es) (admin_id, codigo) "
            "duplicado(s) em centro_custo. Resolva manualmente e reinicie — "
            "a constraint antiga foi preservada.")

    db.session.execute(text("""
        CREATE UNIQUE INDEX IF NOT EXISTS uq_centro_custo_admin_codigo
        ON centro_custo (admin_id, codigo)
    """))
    db.session.commit()
    logger.info("[Migration 250] Índice uq_centro_custo_admin_codigo garantido")

    db.session.execute(text("""
        ALTER TABLE centro_custo
        DROP CONSTRAINT IF EXISTS centro_custo_codigo_key
    """))
    db.session.commit()
    logger.info("[Migration 250] Constraint global centro_custo_codigo_key removida")

    duplicados_adm = db.session.execute(text("""
        SELECT admin_id, count(*) AS n
        FROM centro_custo
        WHERE tipo = 'administrativo'
        GROUP BY admin_id
        HAVING count(*) > 1
        LIMIT 50
    """)).fetchall()
    if duplicados_adm:
        for admin_id, n in duplicados_adm:
            logger.error(
                "[Migration 250] admin_id=%s tem %s centros administrativos",
                admin_id, n)
        raise RuntimeError(
            "[Migration 250] Há tenant com mais de um centro administrativo. "
            "Resolva manualmente e reinicie.")

    db.session.execute(text("""
        CREATE UNIQUE INDEX IF NOT EXISTS uq_centro_custo_administrativo
        ON centro_custo (admin_id)
        WHERE tipo = 'administrativo'
    """))
    db.session.commit()

    logger.info("[Migration 250] Concluída com sucesso")
```

- [ ] **Step 5: Registre a migration**

Em `migrations.py`, dentro de `migrations_to_run`, logo após a linha 4014 (a entrada `213`), acrescente:

```python
            (250, "Fase 4 — centro_custo: unicidade (admin_id, codigo) + índice único parcial do centro administrativo", migration_250_centro_custo_unicidade_por_tenant),
```

- [ ] **Step 6: Aplique e rode os testes**

```bash
python -c "
from app import app
from migrations import executar_migracoes
with app.app_context():
    executar_migracoes()
" 2>&1 | grep -E "250|ERRO|ERROR|CONFLITO"
python -m pytest tests/test_fase4_centro_custo.py -v
```

Esperado: `[Migration 250] Concluída com sucesso` e os 3 testes PASSAM.

- [ ] **Step 7: Commit**

```bash
git add models.py migrations.py tests/test_fase4_centro_custo.py
git commit -m "fix(fase4): centro_custo passa a ser unico por tenant

centro_custo.codigo era UNIQUE global: o primeiro tenant a criar 'ADM'
bloqueava todos os outros. Vira UNIQUE (admin_id, codigo), mais indice
unico parcial garantindo um unico centro administrativo por tenant.
Migration 250, nao destrutiva: aborta e preserva a constraint antiga se
houver duplicidade."
```

---

## Task 2: O centro administrativo do tenant (`utils/centro_custo.py` + migration 251)

**Files:**
- Create: `utils/centro_custo.py`
- Modify: `migrations.py` (nova função + registro)
- Test: `tests/test_fase4_centro_custo.py` (acrescenta)

- [ ] **Step 1: Escreva os testes que falham**

Acrescente ao final de `tests/test_fase4_centro_custo.py`:

```python
# ---------------------------------------------------------------------------
# Resolver do centro administrativo
# ---------------------------------------------------------------------------

def test_centro_administrativo_cria_uma_vez_e_reaproveita():
    from utils.centro_custo import centro_custo_administrativo

    with app.app_context():
        a = _admin()
        cc1 = centro_custo_administrativo(a.id)
        db.session.commit()
        cc2 = centro_custo_administrativo(a.id)
        db.session.commit()

        assert cc1 is not None
        assert cc1.id == cc2.id
        assert cc1.codigo == 'ADM'
        assert cc1.tipo == 'administrativo'
        assert cc1.obra_id is None
        assert cc1.admin_id == a.id
        assert CentroCusto.query.filter_by(
            admin_id=a.id, tipo='administrativo').count() == 1


def test_centro_administrativo_nao_cria_quando_criar_false():
    from utils.centro_custo import centro_custo_administrativo

    with app.app_context():
        a = _admin()
        assert centro_custo_administrativo(a.id, criar=False) is None
        assert CentroCusto.query.filter_by(admin_id=a.id).count() == 0


def test_centro_administrativo_e_por_tenant():
    from utils.centro_custo import centro_custo_administrativo

    with app.app_context():
        a1 = _admin()
        a2 = _admin()
        cc1 = centro_custo_administrativo(a1.id)
        cc2 = centro_custo_administrativo(a2.id)
        db.session.commit()
        assert cc1.id != cc2.id
        assert cc1.admin_id == a1.id
        assert cc2.admin_id == a2.id


def test_centro_administrativo_devolve_none_sem_tenant():
    """Falha fechada: sem tenant não se inventa centro de custo."""
    from utils.centro_custo import centro_custo_administrativo

    with app.app_context():
        assert centro_custo_administrativo(None) is None
```

- [ ] **Step 2: Rode e confirme que falha**

```bash
python -m pytest tests/test_fase4_centro_custo.py -v -k "administrativo"
```

Esperado: FAIL com `ModuleNotFoundError: No module named 'utils.centro_custo'`.

- [ ] **Step 3: Crie `utils/centro_custo.py`**

```python
#!/usr/bin/env python3
"""Centro de custo administrativo do tenant — SIGE Fase 4.

O sistema tem DOIS modelos de centro de custo, sem relação entre si:

  * `CentroCusto` (models.py:706) — eixo financeiro. É o usado por
    `GestaoCustoFilho.centro_custo_id` (models.py:5303), `FluxoCaixa`
    (models.py:793), `CustoObra` (models.py:669) e `Receita`.
  * `CentroCustoContabil` (models.py:2541) — eixo contábil, de partidas
    dobradas. `contabilidade_utils.py:164-173` cria um por obra na aprovação
    da proposta.

Esta fase mexe apenas no PRIMEIRO. Unificar os dois é decisão de outra fase;
misturá-los aqui esconderia o problema em vez de resolvê-lo.

O centro administrativo é o destino legítimo do custo que não pertence a
obra nenhuma: folha, estoque, escritório. Antes da Fase 4 esse custo não
tinha destino — ficava com `obra_id IS NULL` e sumia do orçado×real sem
erro e sem alerta (`DEVOLUTIVA.md` R4).

Nota sobre o nome: `DEVOLUTIVA.md:236` propõe "Veks Adm". Deliberadamente
não usamos isso — "Veks" é o nome de UM tenant, e o SIGE é multi-tenant. O
nome é derivado da empresa de cada tenant.
"""
import logging

logger = logging.getLogger('centro_custo')

CODIGO_ADMINISTRATIVO = 'ADM'
TIPO_ADMINISTRATIVO = 'administrativo'


def _nome_da_empresa(admin_id):
    """Nome legível do tenant, para rotular o centro."""
    from app import db
    from models import ConfiguracaoEmpresa, Usuario

    config = ConfiguracaoEmpresa.query.filter_by(admin_id=admin_id).first()
    if config and (config.nome_empresa or '').strip():
        return config.nome_empresa.strip()
    admin = db.session.get(Usuario, admin_id)
    return (getattr(admin, 'nome', None) or f'Empresa {admin_id}').strip()


def centro_custo_administrativo(admin_id, criar=True):
    """Devolve o `CentroCusto` administrativo do tenant.

    `criar=True` (padrão) cria na primeira chamada e faz `flush` — NÃO faz
    `commit`: quem chamou decide a transação, como o resto do módulo de
    custos (`utils/financeiro_integration.py:216`).

    `criar=False` só consulta — usado por relatório e por validação, que não
    podem ter efeito colateral.

    Falha fechada: `admin_id` vazio devolve None. Nunca "acha o mais
    provável".
    """
    if not admin_id:
        return None

    from app import db
    from models import CentroCusto

    centro = CentroCusto.query.filter_by(
        admin_id=admin_id, tipo=TIPO_ADMINISTRATIVO).first()
    if centro or not criar:
        return centro

    centro = CentroCusto(
        admin_id=admin_id,
        codigo=CODIGO_ADMINISTRATIVO,
        nome=f'Administração — {_nome_da_empresa(admin_id)}'[:100],
        descricao=('Destino dos custos que não pertencem a nenhuma obra: '
                   'folha administrativa, estoque, despesas de escritório. '
                   'Criado pela Fase 4 (centro de custo obrigatório).'),
        tipo=TIPO_ADMINISTRATIVO,
        obra_id=None,
        ativo=True,
    )
    db.session.add(centro)
    db.session.flush()
    logger.info('Centro administrativo criado para tenant %s (id=%s)',
                admin_id, centro.id)
    return centro


def id_do_centro_administrativo(admin_id, criar=True):
    """Atalho: só o id, ou None."""
    centro = centro_custo_administrativo(admin_id, criar=criar)
    return centro.id if centro else None
```

- [ ] **Step 4: Escreva a migration 251**

Em `migrations.py`, antes de `def executar_migracoes():`, insira:

```python
def migration_251_seed_centro_custo_administrativo():
    """Fase 4 — semeia um centro de custo administrativo por tenant.

    Segue o molde de `migration_182_replace_categorias_fluxo_caixa`
    (migrations.py:13351): varre os usuários ADMIN/SUPER_ADMIN e trata cada
    um como um tenant, com try/except por tenant para que um dado ruim não
    derrube a migração inteira.

    Idempotente: o índice único parcial `uq_centro_custo_administrativo`
    (migration 250) garante no máximo um por tenant, e a inserção é
    condicionada a NOT EXISTS.

    O código 'ADM' pode colidir com um centro pré-existente do mesmo tenant
    (a unicidade agora é (admin_id, codigo)). Nesse caso usamos 'ADM-<n>'
    incrementando até achar um livre — o código é rótulo, o que identifica o
    centro é `tipo='administrativo'`.
    """
    logger.info("[Migration 251] Iniciando — centro administrativo por tenant")

    rows = db.session.execute(text("""
        SELECT id FROM usuario
        WHERE tipo_usuario IN ('ADMIN', 'SUPER_ADMIN')
    """)).fetchall()
    admin_ids = [r[0] for r in rows]
    logger.info("[Migration 251] %s tenant(s) a processar", len(admin_ids))

    criados = 0
    ja_tinham = 0
    falhas = 0

    for aid in admin_ids:
        try:
            existe = db.session.execute(text("""
                SELECT id FROM centro_custo
                WHERE admin_id = :aid AND tipo = 'administrativo'
                LIMIT 1
            """), {'aid': aid}).fetchone()
            if existe:
                ja_tinham += 1
                continue

            nome_empresa = db.session.execute(text("""
                SELECT COALESCE(NULLIF(TRIM(c.nome_empresa), ''), NULLIF(TRIM(u.nome), ''),
                                'Empresa ' || u.id::text)
                FROM usuario u
                LEFT JOIN configuracao_empresa c ON c.admin_id = u.id
                WHERE u.id = :aid
                LIMIT 1
            """), {'aid': aid}).scalar() or f'Empresa {aid}'

            codigo = 'ADM'
            for tentativa in range(1, 50):
                livre = db.session.execute(text("""
                    SELECT 1 FROM centro_custo
                    WHERE admin_id = :aid AND codigo = :codigo LIMIT 1
                """), {'aid': aid, 'codigo': codigo}).fetchone()
                if not livre:
                    break
                codigo = f'ADM-{tentativa}'

            db.session.execute(text("""
                INSERT INTO centro_custo
                    (admin_id, codigo, nome, descricao, tipo, ativo, obra_id, created_at)
                VALUES
                    (:aid, :codigo, :nome, :descricao, 'administrativo', true, NULL, NOW())
            """), {
                'aid': aid,
                'codigo': codigo,
                'nome': f'Administração — {nome_empresa}'[:100],
                'descricao': ('Destino dos custos que não pertencem a nenhuma obra: '
                              'folha administrativa, estoque, despesas de escritório. '
                              'Criado pela Fase 4 (centro de custo obrigatório).'),
            })
            db.session.commit()
            criados += 1
        except Exception as e:
            db.session.rollback()
            falhas += 1
            logger.error("[Migration 251] tenant %s falhou: %s", aid, e)

    logger.info(
        "[Migration 251] Concluída — %s criados, %s já tinham, %s falhas",
        criados, ja_tinham, falhas)
```

- [ ] **Step 5: Registre a migration**

Em `migrations.py`, em `migrations_to_run`, logo após a entrada `250`:

```python
            (251, "Fase 4 — seed do centro de custo administrativo (um por tenant)", migration_251_seed_centro_custo_administrativo),
```

- [ ] **Step 6: Aplique e rode os testes**

```bash
python -c "
from app import app
from migrations import executar_migracoes
with app.app_context():
    executar_migracoes()
" 2>&1 | grep -E "251|ERRO|ERROR"
python -m pytest tests/test_fase4_centro_custo.py -v
```

Esperado: `[Migration 251] Concluída — N criados, ...` e os 7 testes PASSAM.

- [ ] **Step 7: Commit**

```bash
git add utils/centro_custo.py migrations.py tests/test_fase4_centro_custo.py
git commit -m "feat(fase4): centro de custo administrativo por tenant

utils/centro_custo.py e a migration 251 dao ao custo que nao pertence a
obra nenhuma (folha, estoque, escritorio) um destino nomeado, em vez de
obra_id NULL. Codigo derivado do nome da empresa: 'Veks Adm' chumbaria um
tenant num sistema multi-tenant."
```

---

## Task 3: `GestaoCustoPai.obra_id` — a coluna derivada (migration 252)

**Files:**
- Modify: `models.py:5239` (dentro de `class GestaoCustoPai`) e `models.py:5267` (relationships)
- Modify: `migrations.py` (nova função + registro)
- Test: `tests/test_fase4_centro_custo.py` (acrescenta)

- [ ] **Step 1: Escreva os testes que falham**

Acrescente ao final de `tests/test_fase4_centro_custo.py`:

```python
# ---------------------------------------------------------------------------
# gestao_custo_pai.obra_id — coluna DERIVADA (nullable de propósito)
# ---------------------------------------------------------------------------

def test_gestao_custo_pai_tem_coluna_obra_id():
    from models import GestaoCustoPai

    with app.app_context():
        assert hasattr(GestaoCustoPai, 'obra_id'), (
            'gestao_custo_pai.obra_id não existe — o pai continua sem eixo '
            'de obra e a listagem depende da subquery de '
            'gestao_custos_views.py:122')


def test_gestao_custo_pai_obra_id_persiste_e_resolve_relationship():
    from models import GestaoCustoPai

    with app.app_context():
        a = _admin()
        o = _obra(a.id)
        pai = GestaoCustoPai(
            admin_id=a.id, tipo_categoria='MATERIAL', entidade_nome='Forn',
            valor_total=100, status='PENDENTE', obra_id=o.id)
        db.session.add(pai)
        db.session.commit()
        pid, oid = pai.id, o.id

    with app.app_context():
        recarregado = db.session.get(GestaoCustoPai, pid)
        assert recarregado.obra_id == oid
        assert recarregado.obra is not None
        assert recarregado.obra.id == oid


def test_gestao_custo_pai_obra_id_e_nullable_de_proposito():
    """Multi-obra e administrativo são legítimos — ver
    utils/financeiro_integration.py:118-131, que agrupa o pai por
    (admin, categoria, entidade) SEM obra."""
    from models import GestaoCustoPai

    with app.app_context():
        a = _admin()
        pai = GestaoCustoPai(
            admin_id=a.id, tipo_categoria='OUTROS', entidade_nome='Escritorio',
            valor_total=50, status='PENDENTE')
        db.session.add(pai)
        db.session.commit()
        assert pai.obra_id is None
```

- [ ] **Step 2: Rode e confirme que falha**

```bash
python -m pytest tests/test_fase4_centro_custo.py -v -k "gestao_custo_pai"
```

Esperado: FAIL. O primeiro com `AssertionError: gestao_custo_pai.obra_id não existe`; o segundo com `TypeError: 'obra_id' is an invalid keyword argument for GestaoCustoPai`.

- [ ] **Step 3: Adicione a coluna ao modelo**

Em `models.py`, dentro de `class GestaoCustoPai`, logo após a linha 5239 (`fluxo_caixa_id = ...`), insira:

```python
    # ── Fase 4 — obra do documento. COLUNA DERIVADA, e nullable PARA SEMPRE.
    #
    # O destino do custo mora no FILHO (`GestaoCustoFilho.obra_id`,
    # models.py:5302). Esta coluna é o resumo do documento, mantida em dia por
    # `services.destino_custo.sincronizar_obra_do_pai`:
    #
    #   * preenchida  → todos os filhos com obra apontam a MESMA obra;
    #   * NULL        → o documento é multi-obra ou é administrativo.
    #
    # Por que nunca vira NOT NULL: `utils/financeiro_integration.py:118-131`
    # reaproveita o mesmo pai em aberto para o mesmo (tenant, categoria,
    # entidade, categoria de fluxo de caixa), SEM olhar obra. Um título a
    # pagar de um fornecedor legitimamente carrega linhas de obras
    # diferentes — em 2026-07-21 havia 9 desses no banco de dev. A
    # obrigatoriedade do destino é travada no filho, pelo CHECK
    # `ck_gestao_custo_filho_destino` (migration 253).
    obra_id = db.Column(
        db.Integer, db.ForeignKey('obra.id'), nullable=True, index=True)
```

E, logo após a linha 5267 (`fornecedor = db.relationship('Fornecedor', ...)`), acrescente:

```python
    obra = db.relationship('Obra', foreign_keys=[obra_id])
```

- [ ] **Step 4: Escreva a migration 252**

Em `migrations.py`, antes de `def executar_migracoes():`, insira:

```python
def migration_252_gestao_custo_pai_obra_id():
    """Fase 4 — `gestao_custo_pai.obra_id` (nullable, derivada).

    Aditiva e idempotente: coluna + FK + índice. NENHUMA linha é preenchida
    aqui. O backfill é `scripts/backfill_destino_custo.py`, que roda em
    dry-run por padrão e exige revisão do relatório antes de gravar.

    Sem `ON DELETE CASCADE`: apagar uma obra não pode apagar título a pagar.
    Sem `ON DELETE SET NULL` também — se alguém tentar apagar uma obra com
    custo lançado, é melhor que o banco recuse e o humano decida. É a mesma
    postura de `gestao_custo_filho_obra_id_fkey`, que já é FK simples.
    """
    logger.info("[Migration 252] Iniciando — gestao_custo_pai.obra_id")

    db.session.execute(text("""
        ALTER TABLE gestao_custo_pai
        ADD COLUMN IF NOT EXISTS obra_id INTEGER
    """))
    db.session.commit()

    existe_fk = db.session.execute(text("""
        SELECT 1 FROM information_schema.table_constraints
        WHERE constraint_name = 'fk_gestao_custo_pai_obra_id'
          AND table_name = 'gestao_custo_pai'
        LIMIT 1
    """)).fetchone()
    if not existe_fk:
        db.session.execute(text("""
            ALTER TABLE gestao_custo_pai
            ADD CONSTRAINT fk_gestao_custo_pai_obra_id
            FOREIGN KEY (obra_id) REFERENCES obra(id)
        """))
        db.session.commit()
        logger.info("[Migration 252] FK fk_gestao_custo_pai_obra_id criada")

    db.session.execute(text("""
        CREATE INDEX IF NOT EXISTS ix_gestao_custo_pai_obra_id
        ON gestao_custo_pai (obra_id)
    """))
    db.session.commit()

    total = db.session.execute(text(
        "SELECT count(*) FROM gestao_custo_pai")).scalar()
    logger.info(
        "[Migration 252] Concluída — %s linha(s) em gestao_custo_pai, todas "
        "com obra_id NULL até o backfill", total)
```

- [ ] **Step 5: Registre a migration**

Em `migrations.py`, em `migrations_to_run`, após a entrada `251`:

```python
            (252, "Fase 4 — gestao_custo_pai.obra_id (nullable, derivada dos filhos)", migration_252_gestao_custo_pai_obra_id),
```

- [ ] **Step 6: Aplique e rode os testes**

```bash
python -c "
from app import app
from migrations import executar_migracoes
with app.app_context():
    executar_migracoes()
" 2>&1 | grep -E "252|ERRO|ERROR"
python -m pytest tests/test_fase4_centro_custo.py -v
```

Esperado: `[Migration 252] Concluída — N linha(s)...` e os 10 testes PASSAM.

- [ ] **Step 7: Commit**

```bash
git add models.py migrations.py tests/test_fase4_centro_custo.py
git commit -m "feat(fase4): gestao_custo_pai.obra_id (nullable, derivada)

A raiz da arvore de custos ganha eixo de obra. Coluna DERIVADA e nullable
para sempre: pai multi-obra e pai administrativo sao legitimos, porque
registrar_custo_automatico agrupa o pai por (tenant, categoria, entidade)
sem olhar obra. Migration 252 nao preenche nada."
```

---

## Task 4: Regras de derivação puras + relatório dry-run

**Files:**
- Create: `services/destino_custo.py`
- Create: `scripts/backfill_destino_custo.py`
- Test: `tests/test_fase4_destino_custo.py`

- [ ] **Step 1: Escreva os testes que falham**

Crie `tests/test_fase4_destino_custo.py`:

```python
"""Fase 4 — derivação do destino do custo.

O ESTADO-ATUAL.md dizia que `gestao_custo_pai` tinha "1.118 linhas 100%
órfãs". Conferido no banco em 2026-07-21: são 1.246 linhas, e 1.169 delas
(93,8%) têm a obra recuperável por UNANIMIDADE dos filhos. "100%
estruturalmente órfãs" (DOSSIE-REPO.md:512) queria dizer "a coluna não
existe", não "a informação se perdeu".

Estes testes travam a cascata R1→R5 e o comportamento dry-run do backfill.
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
from models import (Cliente, GestaoCustoFilho, GestaoCustoPai, Obra,
                    TipoUsuario, Usuario)

pytestmark = pytest.mark.integration


@pytest.fixture(autouse=True)
def _config():
    app.config['TESTING'] = True
    app.config['WTF_CSRF_ENABLED'] = False
    if not app.secret_key:
        app.secret_key = 'test-fase4-destino'
    yield


def _admin():
    suf = uuid.uuid4().hex[:10]
    u = Usuario(
        username=f'f4d_{suf}', email=f'f4d_{suf}@test.local',
        nome=f'Empresa {suf}',
        password_hash=generate_password_hash('Senha@2026'),
        tipo_usuario=TipoUsuario.ADMIN, ativo=True, versao_sistema='v2',
    )
    db.session.add(u)
    db.session.commit()
    return u


def _obra(admin_id):
    suf = uuid.uuid4().hex[:8]
    cli = Cliente(nome=f'Cliente {suf}', admin_id=admin_id)
    db.session.add(cli)
    db.session.flush()
    o = Obra(nome=f'Obra {suf}', codigo=f'F4D{suf[:6].upper()}',
             cliente_id=cli.id, admin_id=admin_id,
             data_inicio=date(2026, 1, 1), ativo=True)
    db.session.add(o)
    db.session.commit()
    return o


def _pai_com_filhos(admin_id, obras_dos_filhos, origem='manual'):
    """Cria um pai e um filho por elemento de `obras_dos_filhos` (None = sem obra)."""
    pai = GestaoCustoPai(
        admin_id=admin_id, tipo_categoria='MATERIAL', entidade_nome='Forn',
        valor_total=0, status='PENDENTE')
    db.session.add(pai)
    db.session.flush()
    for i, oid in enumerate(obras_dos_filhos):
        db.session.add(GestaoCustoFilho(
            pai_id=pai.id, admin_id=admin_id, data_referencia=date(2026, 6, 1),
            descricao=f'Linha {i}', valor=10, obra_id=oid,
            origem_tabela=origem))
    db.session.commit()
    return pai


# --- regras puras ----------------------------------------------------------

def test_obra_unanime_devolve_a_obra_quando_todas_iguais():
    from services.destino_custo import obra_unanime

    assert obra_unanime([7, 7, 7]) == 7
    assert obra_unanime([7, None, 7]) == 7
    assert obra_unanime([7]) == 7


def test_obra_unanime_devolve_none_quando_diverge_ou_vazio():
    from services.destino_custo import obra_unanime

    assert obra_unanime([7, 8]) is None
    assert obra_unanime([None, None]) is None
    assert obra_unanime([]) is None


def test_classificar_pai_nomeia_os_tres_casos():
    from services.destino_custo import classificar_pai

    assert classificar_pai([5, 5]) == ('unanime', 5)
    assert classificar_pai([5, 6]) == ('multiobra', None)
    assert classificar_pai([None]) == ('sem_obra', None)
    assert classificar_pai([]) == ('sem_filho', None)


def test_origem_administrativa_reconhece_folha_e_almoxarifado():
    from services.destino_custo import (ORIGENS_ADMINISTRATIVAS,
                                        ORIGENS_COM_OBRA)

    assert 'folha_pagamento' in ORIGENS_ADMINISTRATIVAS
    assert 'almoxarifado_movimento' in ORIGENS_ADMINISTRATIVAS
    assert 'pedido_compra' in ORIGENS_COM_OBRA
    assert 'reembolso_funcionario' in ORIGENS_COM_OBRA
    assert 'folha_pagamento' not in ORIGENS_COM_OBRA


# --- relatório dry-run -----------------------------------------------------

def test_diagnosticar_conta_unanimes_multiobra_e_orfaos():
    from scripts.backfill_destino_custo import diagnosticar

    with app.app_context():
        a = _admin()
        o1, o2 = _obra(a.id), _obra(a.id)
        _pai_com_filhos(a.id, [o1.id, o1.id])   # unânime
        _pai_com_filhos(a.id, [o1.id, o2.id])   # multi-obra
        _pai_com_filhos(a.id, [None])           # sem obra
        pai_vazio = GestaoCustoPai(
            admin_id=a.id, tipo_categoria='OUTROS', entidade_nome='X',
            valor_total=0, status='PENDENTE')
        db.session.add(pai_vazio)
        db.session.commit()

        rel = diagnosticar(admin_id=a.id)

        assert rel['pai']['total'] == 4
        assert rel['pai']['unanime'] == 1
        assert rel['pai']['multiobra'] == 1
        assert rel['pai']['sem_obra'] == 1
        assert rel['pai']['sem_filho'] == 1
        assert rel['filho']['sem_destino'] == 1


def test_diagnosticar_nao_grava_nada():
    from scripts.backfill_destino_custo import diagnosticar

    with app.app_context():
        a = _admin()
        o = _obra(a.id)
        pai = _pai_com_filhos(a.id, [o.id, o.id])
        pid = pai.id

        diagnosticar(admin_id=a.id)
        db.session.expire_all()
        assert db.session.get(GestaoCustoPai, pid).obra_id is None, (
            'diagnosticar() gravou — o dry-run tem de ser read-only')
```

- [ ] **Step 2: Rode e confirme que falha**

```bash
python -m pytest tests/test_fase4_destino_custo.py -v
```

Esperado: FAIL com `ModuleNotFoundError: No module named 'services.destino_custo'`.

- [ ] **Step 3: Crie `services/destino_custo.py`**

```python
#!/usr/bin/env python3
"""Regras de derivação do destino do custo — SIGE Fase 4.

Todo lançamento de custo tem de ter um destino: uma **obra** ou o **centro
de custo administrativo** do tenant. Este módulo concentra as regras que
decidem qual, tanto para o backfill histórico quanto para a escrita nova.

A cascata, do mais forte para o mais fraco, parando no primeiro que resolve:

  R1  unanimidade dos filhos  → grava `gestao_custo_pai.obra_id`
  R2  irmão unânime           → filho órfão herda a obra do próprio pai
  R3  origem                  → filho órfão herda a obra da linha de origem
  R4  natureza da origem      → folha e almoxarifado vão para administrativo
  R5  resto                   → administrativo, carimbado e listado

Rejeitadas de propósito, e o motivo:

  * por DATA (obra ativa na data): com mais de uma obra ativa — o caso
    normal — é sorteio disfarçado de regra.
  * por CRIADOR: `admin_id` é tenant, não pessoa (models.py:5238);
    `responsavel_id` só vem preenchido por compras (compras_views.py:210).
  * por CENTRO DE CUSTO já gravado: 8 filhos de 1.823 tinham
    `centro_custo_id` em 2026-07-21. O campo está morto.
  * por RATEIO proporcional ao orçado (o que `resumo_custos_obra.py:191`
    faz em memória): gravar rateio é transformar estimativa em dado. É
    exatamente a dívida que esta fase existe para pagar.
"""
import logging

logger = logging.getLogger('destino_custo')

# origem_tabela → (tabela, coluna de obra). Todas conferidas no banco em
# 2026-07-21: as cinco têm a coluna `obra_id`.
ORIGENS_COM_OBRA = {
    'pedido_compra': ('pedido_compra', 'obra_id'),
    'conta_pagar': ('conta_pagar', 'obra_id'),
    'reembolso_funcionario': ('reembolso_funcionario', 'obra_id'),
    'alimentacao_lancamento': ('alimentacao_lancamento', 'obra_id'),
    'lancamento_transporte': ('lancamento_transporte', 'obra_id'),
}

# Origens que são administrativas POR CONSTRUÇÃO, não por falta de dado.
#   folha_pagamento        — a mão de obra que é custo de obra entra por
#                            outro caminho e já vem com obra: os filhos de
#                            origem rdo_mao_obra / rdo_mao_obra_va /
#                            rdo_mao_obra_vt / rdo_custo_diario têm obra em
#                            100% dos casos (conferido em 2026-07-21).
#                            Mandar a folha para obra seria contagem dupla.
#   almoxarifado_movimento — material que ENTRA em estoque ainda não é custo
#                            de obra; vira quando sai. Hoje
#                            `event_manager.py:223` grava sem destino nenhum.
ORIGENS_ADMINISTRATIVAS = {
    'folha_pagamento',
    'almoxarifado_movimento',
}

# Categorias em que "administrativo" é resposta errada por definição.
# FATURAMENTO_DIRETO é material que o cliente paga direto ao fornecedor DA
# OBRA (compras_views.py:314-345) — sem obra não significa nada.
CATEGORIAS_QUE_EXIGEM_OBRA = {'FATURAMENTO_DIRETO'}

# Carimbo das linhas que só a R5 alcançou — o que o humano tem de revisar.
MARCA_FALLBACK = '[FASE4:R5]'
REGRA_FALLBACK = 'administrativo'


def obra_unanime(obra_ids):
    """R1/R2 — devolve a única obra presente, ou None.

    `None` na lista é ignorado (linha sem obra não vota). Devolve None
    quando a lista é vazia, quando só há None, ou quando há divergência.
    Nunca "escolhe a maioria": maioria é chute.
    """
    distintas = {o for o in obra_ids if o is not None}
    if len(distintas) == 1:
        return next(iter(distintas))
    return None


def classificar_pai(obra_ids):
    """Classifica um pai a partir das obras dos filhos.

    Devolve `(situacao, obra_id)` com situacao em:
      'unanime'   — resolvido, obra_id preenchido
      'multiobra' — filhos em obras diferentes; obra_id do pai fica NULL
      'sem_obra'  — tem filhos, nenhum com obra
      'sem_filho' — pai sem filho nenhum
    """
    obra_ids = list(obra_ids)
    if not obra_ids:
        return ('sem_filho', None)
    unanime = obra_unanime(obra_ids)
    if unanime is not None:
        return ('unanime', unanime)
    if any(o is not None for o in obra_ids):
        return ('multiobra', None)
    return ('sem_obra', None)


def sincronizar_obra_do_pai(pai):
    """Recalcula `pai.obra_id` a partir dos filhos atuais.

    Chamada em toda escrita que mexe nos filhos. Não faz commit — quem
    chamou controla a transação, como `_recalcular_total_pai`
    (gestao_custos_views.py:415).

    Devolve o `obra_id` gravado (ou None).
    """
    from app import db
    from models import GestaoCustoFilho

    linhas = (db.session.query(GestaoCustoFilho.obra_id)
              .filter(GestaoCustoFilho.pai_id == pai.id)
              .all())
    _situacao, obra_id = classificar_pai([r[0] for r in linhas])
    pai.obra_id = obra_id
    return obra_id


def destino_de_filho_novo(admin_id, obra_id, centro_custo_id, origem_tabela,
                          tipo_categoria=None, criar_centro=True):
    """Resolve o destino de um lançamento NOVO. Devolve `(obra_id, centro_custo_id)`.

    Regra única e sem exceção: se não veio obra, o destino é o centro
    administrativo do tenant. Nunca devolve `(None, None)` — quando não dá
    para resolver, levanta `DestinoIndefinido`, e é isso que fecha a porta.

    `criar_centro=False` só consulta (usado por validação sem efeito).
    """
    from utils.centro_custo import id_do_centro_administrativo

    if obra_id:
        return (obra_id, centro_custo_id)

    if tipo_categoria in CATEGORIAS_QUE_EXIGEM_OBRA:
        raise DestinoIndefinido(
            f'A categoria {tipo_categoria} exige obra — "administrativo" não '
            'é resposta válida para ela.')

    if centro_custo_id:
        return (None, centro_custo_id)

    adm_id = id_do_centro_administrativo(admin_id, criar=criar_centro)
    if not adm_id:
        raise DestinoIndefinido(
            f'Tenant {admin_id} não tem centro de custo administrativo e não '
            'foi possível criá-lo. Rode a migration 251.')
    logger.debug('destino administrativo aplicado (origem=%s, tenant=%s)',
                 origem_tabela, admin_id)
    return (None, adm_id)


class DestinoIndefinido(ValueError):
    """Lançamento de custo sem obra e sem centro de custo resolvível."""
```

- [ ] **Step 4: Crie `scripts/backfill_destino_custo.py` (só o diagnóstico, por enquanto)**

```python
#!/usr/bin/env python3
"""Backfill do destino do custo — SIGE Fase 4.

DRY-RUN POR PADRÃO. Sem `--aplicar` este script não escreve uma linha.

Uso:
    python scripts/backfill_destino_custo.py                  # relatório global
    python scripts/backfill_destino_custo.py --tenant 832     # um tenant
    python scripts/backfill_destino_custo.py --csv /tmp/f4.csv
    python scripts/backfill_destino_custo.py --aplicar        # grava

O relatório responde três perguntas, nesta ordem:
  1. quantos `gestao_custo_pai` têm obra recuperável por unanimidade (R1);
  2. quantos são multi-obra — que NÃO são defeito, são projeto;
  3. quantos `gestao_custo_filho` continuam sem destino, e por qual regra
     cada um seria resolvido.
"""
from __future__ import annotations

import argparse
import csv
import os
import sys
from collections import Counter

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def _pais_e_obras(admin_id=None):
    """Devolve {pai_id: (admin_id, [obra_id dos filhos])} — inclui pai sem filho."""
    from app import db
    from models import GestaoCustoFilho, GestaoCustoPai

    q_pai = db.session.query(GestaoCustoPai.id, GestaoCustoPai.admin_id)
    if admin_id:
        q_pai = q_pai.filter(GestaoCustoPai.admin_id == admin_id)
    mapa = {pid: (aid, []) for pid, aid in q_pai.all()}

    q_filho = db.session.query(GestaoCustoFilho.pai_id, GestaoCustoFilho.obra_id)
    if admin_id:
        q_filho = q_filho.filter(GestaoCustoFilho.admin_id == admin_id)
    for pai_id, obra_id in q_filho.all():
        if pai_id in mapa:
            mapa[pai_id][1].append(obra_id)
    return mapa


def _regra_para_filho(filho, obra_do_pai):
    """Qual regra resolveria este filho órfão. Devolve (regra, obra_id|None)."""
    from app import db
    from sqlalchemy import text as _text

    from services.destino_custo import (ORIGENS_ADMINISTRATIVAS,
                                        ORIGENS_COM_OBRA)

    if obra_do_pai is not None:
        return ('R2_irmao_unanime', obra_do_pai)

    origem = filho.origem_tabela or ''
    if origem in ORIGENS_COM_OBRA and filho.origem_id:
        tabela, coluna = ORIGENS_COM_OBRA[origem]
        achado = db.session.execute(
            _text(f'SELECT {coluna} FROM {tabela} WHERE id = :oid'),  # noqa: S608
            {'oid': filho.origem_id},
        ).scalar()
        if achado:
            return ('R3_origem', achado)

    if origem in ORIGENS_ADMINISTRATIVAS:
        return ('R4_natureza_origem', None)

    return ('R5_fallback', None)


def diagnosticar(admin_id=None):
    """Relatório READ-ONLY. Não grava nada, nem faz flush."""
    from app import db
    from models import GestaoCustoFilho, GestaoCustoPai
    from services.destino_custo import classificar_pai

    mapa = _pais_e_obras(admin_id)

    situacoes = Counter()
    obra_por_pai = {}
    for pai_id, (_aid, obras) in mapa.items():
        situacao, obra_id = classificar_pai(obras)
        situacoes[situacao] += 1
        obra_por_pai[pai_id] = obra_id

    q_orfaos = db.session.query(GestaoCustoFilho).filter(
        GestaoCustoFilho.obra_id.is_(None),
        GestaoCustoFilho.centro_custo_id.is_(None),
    )
    if admin_id:
        q_orfaos = q_orfaos.filter(GestaoCustoFilho.admin_id == admin_id)
    orfaos = q_orfaos.all()

    regras = Counter()
    detalhe = []
    for filho in orfaos:
        regra, obra_id = _regra_para_filho(filho, obra_por_pai.get(filho.pai_id))
        regras[regra] += 1
        detalhe.append({
            'filho_id': filho.id,
            'pai_id': filho.pai_id,
            'admin_id': filho.admin_id,
            'data_referencia': str(filho.data_referencia),
            'descricao': (filho.descricao or '')[:80],
            'valor': str(filho.valor),
            'origem_tabela': filho.origem_tabela or '',
            'origem_id': filho.origem_id or '',
            'regra': regra,
            'obra_derivada': obra_id or '',
        })

    total_pai = db.session.query(GestaoCustoPai).count() if not admin_id else \
        db.session.query(GestaoCustoPai).filter(
            GestaoCustoPai.admin_id == admin_id).count()

    return {
        'pai': {
            'total': total_pai,
            'unanime': situacoes['unanime'],
            'multiobra': situacoes['multiobra'],
            'sem_obra': situacoes['sem_obra'],
            'sem_filho': situacoes['sem_filho'],
        },
        'filho': {
            'sem_destino': len(orfaos),
            'por_regra': dict(regras),
        },
        'detalhe': detalhe,
    }


def imprimir(rel):
    p, f = rel['pai'], rel['filho']
    cobertos = p['unanime']
    pct = (100.0 * cobertos / p['total']) if p['total'] else 0.0
    print('=' * 72)
    print('FASE 4 — DESTINO DO CUSTO')
    print('=' * 72)
    print(f"gestao_custo_pai .......... {p['total']:>7}")
    print(f"  R1 obra unânime ......... {p['unanime']:>7}  ({pct:.1f}%)")
    print(f"  multi-obra (fica NULL) .. {p['multiobra']:>7}  <- projeto, não defeito")
    print(f"  filhos sem obra ......... {p['sem_obra']:>7}")
    print(f"  sem filho nenhum ........ {p['sem_filho']:>7}")
    print('-' * 72)
    print(f"gestao_custo_filho sem destino: {f['sem_destino']}")
    for regra in sorted(f['por_regra']):
        print(f"  {regra:<22} {f['por_regra'][regra]:>7}")
    print('=' * 72)


def escrever_csv(rel, caminho):
    campos = ['filho_id', 'pai_id', 'admin_id', 'data_referencia', 'descricao',
              'valor', 'origem_tabela', 'origem_id', 'regra', 'obra_derivada']
    with open(caminho, 'w', newline='', encoding='utf-8') as fh:
        w = csv.DictWriter(fh, fieldnames=campos)
        w.writeheader()
        for linha in rel['detalhe']:
            w.writerow(linha)
    print(f'CSV escrito em {caminho} ({len(rel["detalhe"])} linha(s))')


def main():
    ap = argparse.ArgumentParser(description='Backfill do destino do custo (Fase 4)')
    ap.add_argument('--tenant', type=int, default=None, help='admin_id')
    ap.add_argument('--csv', default=None, help='arquivo do detalhe dos órfãos')
    ap.add_argument('--aplicar', action='store_true',
                    help='GRAVA. Sem esta flag o script é read-only.')
    args = ap.parse_args()

    from app import app

    with app.app_context():
        rel = diagnosticar(admin_id=args.tenant)
        imprimir(rel)
        if args.csv:
            escrever_csv(rel, args.csv)
        if not args.aplicar:
            print('\nDRY-RUN — nada foi gravado. Use --aplicar para gravar.')


if __name__ == '__main__':
    main()
```

- [ ] **Step 5: Rode os testes e o relatório**

```bash
python -m pytest tests/test_fase4_destino_custo.py -v
python scripts/backfill_destino_custo.py --csv /tmp/fase4-dryrun.csv
```

Esperado: os 6 testes PASSAM; o relatório imprime a tabela e termina com `DRY-RUN — nada foi gravado.`

- [ ] **Step 6: Commit**

```bash
git add services/destino_custo.py scripts/backfill_destino_custo.py tests/test_fase4_destino_custo.py
git commit -m "feat(fase4): regras de derivacao do destino + relatorio dry-run

services/destino_custo.py concentra a cascata R1-R5 e documenta as regras
rejeitadas (por data, por criador, por rateio) com o motivo. O script de
backfill nasce read-only: sem --aplicar nao grava uma linha."
```

---

## Task 5: Aplicar R1 — `pai.obra_id` por unanimidade

**Files:**
- Modify: `scripts/backfill_destino_custo.py` (acrescenta `aplicar_pais`)
- Test: `tests/test_fase4_destino_custo.py` (acrescenta)

- [ ] **Step 1: Escreva os testes que falham**

Acrescente ao final de `tests/test_fase4_destino_custo.py`:

```python
# ---------------------------------------------------------------------------
# R1 — pai.obra_id por unanimidade dos filhos
# ---------------------------------------------------------------------------

def test_aplicar_pais_preenche_unanime_e_deixa_multiobra_null():
    from scripts.backfill_destino_custo import aplicar_pais

    with app.app_context():
        a = _admin()
        o1, o2 = _obra(a.id), _obra(a.id)
        pai_u = _pai_com_filhos(a.id, [o1.id, o1.id])
        pai_m = _pai_com_filhos(a.id, [o1.id, o2.id])
        pai_s = _pai_com_filhos(a.id, [None])
        ids = (pai_u.id, pai_m.id, pai_s.id)

        resultado = aplicar_pais(admin_id=a.id)
        db.session.commit()

        assert resultado['atualizados'] == 1
        db.session.expire_all()
        assert db.session.get(GestaoCustoPai, ids[0]).obra_id == o1.id
        assert db.session.get(GestaoCustoPai, ids[1]).obra_id is None
        assert db.session.get(GestaoCustoPai, ids[2]).obra_id is None


def test_aplicar_pais_e_idempotente():
    from scripts.backfill_destino_custo import aplicar_pais

    with app.app_context():
        a = _admin()
        o = _obra(a.id)
        pai = _pai_com_filhos(a.id, [o.id, o.id])
        pid = pai.id

        primeira = aplicar_pais(admin_id=a.id)
        db.session.commit()
        segunda = aplicar_pais(admin_id=a.id)
        db.session.commit()

        assert primeira['atualizados'] == 1
        assert segunda['atualizados'] == 0
        db.session.expire_all()
        assert db.session.get(GestaoCustoPai, pid).obra_id == o.id


def test_aplicar_pais_corrige_obra_errada_gravada_antes():
    """Se um filho mudou de obra, o pai acompanha — a coluna é derivada."""
    from scripts.backfill_destino_custo import aplicar_pais

    with app.app_context():
        a = _admin()
        o1, o2 = _obra(a.id), _obra(a.id)
        pai = _pai_com_filhos(a.id, [o1.id])
        aplicar_pais(admin_id=a.id)
        db.session.commit()

        filho = GestaoCustoFilho.query.filter_by(pai_id=pai.id).one()
        filho.obra_id = o2.id
        db.session.commit()

        aplicar_pais(admin_id=a.id)
        db.session.commit()
        db.session.expire_all()
        assert db.session.get(GestaoCustoPai, pai.id).obra_id == o2.id
```

- [ ] **Step 2: Rode e confirme que falha**

```bash
python -m pytest tests/test_fase4_destino_custo.py -v -k "aplicar_pais"
```

Esperado: FAIL com `ImportError: cannot import name 'aplicar_pais' from 'scripts.backfill_destino_custo'`.

- [ ] **Step 3: Acrescente `aplicar_pais` ao script**

Em `scripts/backfill_destino_custo.py`, insira a função logo após `diagnosticar` (antes de `def imprimir`):

```python
def aplicar_pais(admin_id=None, lote=500):
    """R1 — grava `gestao_custo_pai.obra_id` por unanimidade dos filhos.

    Idempotente: recalcula sempre e só toca a linha quando o valor MUDA.
    Multi-obra e sem-obra ficam (ou voltam a ficar) NULL de propósito — a
    coluna é derivada, não é opinião gravada.

    Não faz commit: quem chama controla a transação. O `main()` comita.
    """
    from app import db
    from models import GestaoCustoPai
    from services.destino_custo import classificar_pai

    mapa = _pais_e_obras(admin_id)
    alvo = {}
    for pai_id, (_aid, obras) in mapa.items():
        _situacao, obra_id = classificar_pai(obras)
        alvo[pai_id] = obra_id

    atualizados = 0
    ids = list(alvo)
    for inicio in range(0, len(ids), lote):
        pedaco = ids[inicio:inicio + lote]
        pais = GestaoCustoPai.query.filter(GestaoCustoPai.id.in_(pedaco)).all()
        for pai in pais:
            novo = alvo.get(pai.id)
            if pai.obra_id != novo:
                pai.obra_id = novo
                atualizados += 1
        db.session.flush()

    return {'avaliados': len(ids), 'atualizados': atualizados}
```

E, em `main()`, substitua o bloco final:

```python
        if not args.aplicar:
            print('\nDRY-RUN — nada foi gravado. Use --aplicar para gravar.')
```

por:

```python
        if not args.aplicar:
            print('\nDRY-RUN — nada foi gravado. Use --aplicar para gravar.')
            return

        print('\n--aplicar: gravando…')
        r_pai = aplicar_pais(admin_id=args.tenant)
        db.session.commit()
        print(f"R1 gestao_custo_pai.obra_id: {r_pai['atualizados']} de "
              f"{r_pai['avaliados']} atualizado(s)")
```

E acrescente o import de `db` no topo de `main()`, logo abaixo de `from app import app`:

```python
    from app import app, db
```

(substituindo a linha `from app import app`).

- [ ] **Step 4: Rode os testes**

```bash
python -m pytest tests/test_fase4_destino_custo.py -v -k "aplicar_pais"
```

Esperado: os 3 testes PASSAM.

- [ ] **Step 5: Rode o backfill de verdade no banco de desenvolvimento**

```bash
python scripts/backfill_destino_custo.py --aplicar
```

Esperado: `R1 gestao_custo_pai.obra_id: ~1169 de ~1246 atualizado(s)` (o número exato depende do estado do banco no momento — o que precisa bater é a ordem de grandeza: ~94%).

- [ ] **Step 6: Commit**

```bash
git add scripts/backfill_destino_custo.py tests/test_fase4_destino_custo.py
git commit -m "feat(fase4): backfill R1 — pai.obra_id por unanimidade dos filhos

Cobre ~94% dos gestao_custo_pai. Idempotente e reversivel: a coluna e
derivada, entao rodar de novo recalcula. Multi-obra continua NULL de
proposito."
```

---

## Task 6: Aplicar R2-R5 — destino dos filhos órfãos

**Files:**
- Modify: `scripts/backfill_destino_custo.py` (acrescenta `aplicar_filhos`)
- Test: `tests/test_fase4_destino_custo.py` (acrescenta)

- [ ] **Step 1: Escreva os testes que falham**

Acrescente ao final de `tests/test_fase4_destino_custo.py`:

```python
# ---------------------------------------------------------------------------
# R2-R5 — destino dos filhos órfãos
# ---------------------------------------------------------------------------

def test_r2_filho_orfao_herda_obra_do_irmao_unanime():
    from scripts.backfill_destino_custo import aplicar_filhos, aplicar_pais

    with app.app_context():
        a = _admin()
        o = _obra(a.id)
        pai = _pai_com_filhos(a.id, [o.id, None])
        aplicar_pais(admin_id=a.id)
        db.session.commit()

        r = aplicar_filhos(admin_id=a.id)
        db.session.commit()

        assert r['por_regra'].get('R2_irmao_unanime') == 1
        orfaos = GestaoCustoFilho.query.filter_by(
            pai_id=pai.id, obra_id=None).count()
        assert orfaos == 0


def test_r3_filho_orfao_herda_obra_da_origem():
    from models import PedidoCompra
    from scripts.backfill_destino_custo import aplicar_filhos, aplicar_pais

    with app.app_context():
        a = _admin()
        o = _obra(a.id)
        pedido = PedidoCompra(
            admin_id=a.id, obra_id=o.id, numero=f'PC{uuid.uuid4().hex[:6]}',
            data_compra=date(2026, 6, 1), valor_total=100)
        db.session.add(pedido)
        db.session.flush()

        pai = GestaoCustoPai(
            admin_id=a.id, tipo_categoria='MATERIAL', entidade_nome='Forn',
            valor_total=100, status='PENDENTE')
        db.session.add(pai)
        db.session.flush()
        db.session.add(GestaoCustoFilho(
            pai_id=pai.id, admin_id=a.id, data_referencia=date(2026, 6, 1),
            descricao='Compra', valor=100, obra_id=None,
            origem_tabela='pedido_compra', origem_id=pedido.id))
        db.session.commit()

        aplicar_pais(admin_id=a.id)
        db.session.commit()
        r = aplicar_filhos(admin_id=a.id)
        db.session.commit()

        assert r['por_regra'].get('R3_origem') == 1
        filho = GestaoCustoFilho.query.filter_by(pai_id=pai.id).one()
        assert filho.obra_id == o.id


def test_r4_folha_e_almoxarifado_vao_para_o_centro_administrativo():
    from scripts.backfill_destino_custo import aplicar_filhos, aplicar_pais
    from utils.centro_custo import centro_custo_administrativo

    with app.app_context():
        a = _admin()
        pai = _pai_com_filhos(a.id, [None], origem='folha_pagamento')
        aplicar_pais(admin_id=a.id)
        db.session.commit()

        r = aplicar_filhos(admin_id=a.id)
        db.session.commit()

        assert r['por_regra'].get('R4_natureza_origem') == 1
        adm = centro_custo_administrativo(a.id, criar=False)
        assert adm is not None
        filho = GestaoCustoFilho.query.filter_by(pai_id=pai.id).one()
        assert filho.obra_id is None
        assert filho.centro_custo_id == adm.id


def test_r5_resto_vai_para_administrativo_e_fica_carimbado():
    from scripts.backfill_destino_custo import aplicar_filhos, aplicar_pais
    from services.destino_custo import MARCA_FALLBACK
    from utils.centro_custo import centro_custo_administrativo

    with app.app_context():
        a = _admin()
        pai = _pai_com_filhos(a.id, [None], origem='lancamento_periodo_manual')
        aplicar_pais(admin_id=a.id)
        db.session.commit()

        r = aplicar_filhos(admin_id=a.id)
        db.session.commit()

        assert r['por_regra'].get('R5_fallback') == 1
        adm = centro_custo_administrativo(a.id, criar=False)
        filho = GestaoCustoFilho.query.filter_by(pai_id=pai.id).one()
        assert filho.centro_custo_id == adm.id
        db.session.expire_all()
        assert MARCA_FALLBACK in (db.session.get(GestaoCustoPai, pai.id).observacoes or '')


def test_aplicar_filhos_e_idempotente():
    from scripts.backfill_destino_custo import aplicar_filhos, aplicar_pais

    with app.app_context():
        a = _admin()
        _pai_com_filhos(a.id, [None], origem='folha_pagamento')
        aplicar_pais(admin_id=a.id)
        db.session.commit()

        primeira = aplicar_filhos(admin_id=a.id)
        db.session.commit()
        segunda = aplicar_filhos(admin_id=a.id)
        db.session.commit()

        assert primeira['atualizados'] == 1
        assert segunda['atualizados'] == 0


def test_apos_backfill_nao_sobra_filho_sem_destino():
    from scripts.backfill_destino_custo import (aplicar_filhos, aplicar_pais,
                                                diagnosticar)

    with app.app_context():
        a = _admin()
        o = _obra(a.id)
        _pai_com_filhos(a.id, [o.id, None])
        _pai_com_filhos(a.id, [None], origem='folha_pagamento')
        _pai_com_filhos(a.id, [None], origem='lancamento_periodo_manual')

        aplicar_pais(admin_id=a.id)
        db.session.commit()
        aplicar_filhos(admin_id=a.id)
        db.session.commit()

        assert diagnosticar(admin_id=a.id)['filho']['sem_destino'] == 0
```

- [ ] **Step 2: Rode e confirme que falha**

```bash
python -m pytest tests/test_fase4_destino_custo.py -v -k "r2_ or r3_ or r4_ or r5_ or aplicar_filhos or apos_backfill"
```

Esperado: FAIL com `ImportError: cannot import name 'aplicar_filhos'`.

- [ ] **Step 3: Acrescente `aplicar_filhos` ao script**

Em `scripts/backfill_destino_custo.py`, logo após `aplicar_pais`, insira:

```python
def aplicar_filhos(admin_id=None):
    """R2-R5 — dá destino a todo `gestao_custo_filho` sem obra e sem centro.

    Ordem de aplicação, parando no primeiro que resolve:
      R2  irmão unânime      → herda `pai.obra_id`
      R3  origem             → herda a obra da linha de origem
      R4  natureza da origem → centro administrativo (folha, almoxarifado)
      R5  resto              → centro administrativo + carimbo [FASE4:R5]
                               nas `observacoes` do pai, para revisão humana

    Pressupõe `aplicar_pais` já rodado (R2 lê `pai.obra_id`).
    Idempotente: só olha linhas que ainda estão sem destino.
    Não faz commit.
    """
    from collections import Counter

    from app import db
    from models import GestaoCustoFilho, GestaoCustoPai
    from services.destino_custo import MARCA_FALLBACK
    from utils.centro_custo import id_do_centro_administrativo

    q = db.session.query(GestaoCustoFilho).filter(
        GestaoCustoFilho.obra_id.is_(None),
        GestaoCustoFilho.centro_custo_id.is_(None),
    )
    if admin_id:
        q = q.filter(GestaoCustoFilho.admin_id == admin_id)
    orfaos = q.all()

    if not orfaos:
        return {'avaliados': 0, 'atualizados': 0, 'por_regra': {}}

    pai_ids = {f.pai_id for f in orfaos}
    pais = {p.id: p for p in
            GestaoCustoPai.query.filter(GestaoCustoPai.id.in_(pai_ids)).all()}

    centro_por_tenant = {}
    regras = Counter()
    atualizados = 0
    pais_marcados = set()

    for filho in orfaos:
        pai = pais.get(filho.pai_id)
        obra_do_pai = pai.obra_id if pai else None
        regra, obra_id = _regra_para_filho(filho, obra_do_pai)

        if obra_id:
            filho.obra_id = obra_id
        else:
            tenant = filho.admin_id
            if tenant not in centro_por_tenant:
                centro_por_tenant[tenant] = id_do_centro_administrativo(
                    tenant, criar=True)
            centro_id = centro_por_tenant[tenant]
            if not centro_id:
                logger_aviso = (
                    f'filho {filho.id}: tenant {tenant} sem centro '
                    'administrativo — linha deixada como está')
                print(f'  AVISO {logger_aviso}')
                continue
            filho.centro_custo_id = centro_id
            if regra == 'R5_fallback' and pai is not None \
                    and pai.id not in pais_marcados:
                atual = pai.observacoes or ''
                if MARCA_FALLBACK not in atual:
                    pai.observacoes = f'{MARCA_FALLBACK} {atual}'.strip()[:2000]
                pais_marcados.add(pai.id)

        regras[regra] += 1
        atualizados += 1

    db.session.flush()
    return {'avaliados': len(orfaos), 'atualizados': atualizados,
            'por_regra': dict(regras)}
```

E, em `main()`, logo após o bloco `r_pai = ...`, acrescente:

```python
        r_filho = aplicar_filhos(admin_id=args.tenant)
        db.session.commit()
        print(f"R2-R5 gestao_custo_filho: {r_filho['atualizados']} de "
              f"{r_filho['avaliados']} resolvido(s)")
        for regra in sorted(r_filho['por_regra']):
            print(f"    {regra:<22} {r_filho['por_regra'][regra]:>7}")

        print('\nRelatório pós-aplicação:')
        imprimir(diagnosticar(admin_id=args.tenant))
```

- [ ] **Step 4: Rode os testes**

```bash
python -m pytest tests/test_fase4_destino_custo.py -v
```

Esperado: os 15 testes PASSAM.

- [ ] **Step 5: Rode o backfill completo e guarde o CSV**

```bash
python scripts/backfill_destino_custo.py --csv /tmp/fase4-antes.csv
python scripts/backfill_destino_custo.py --aplicar
python scripts/backfill_destino_custo.py --csv /tmp/fase4-depois.csv
```

Esperado: no relatório final, `gestao_custo_filho sem destino: 0`.

- [ ] **Step 6: Commit**

```bash
git add scripts/backfill_destino_custo.py tests/test_fase4_destino_custo.py
git commit -m "feat(fase4): backfill R2-R5 — destino de todo filho orfao

Cascata: irmao unanime, origem (5 tabelas conferidas), natureza da origem
(folha e almoxarifado sao administrativos por construcao) e, no fim,
centro administrativo carimbado [FASE4:R5] para revisao humana. Nenhum
chute por data, por criador ou por rateio."
```

---

## Task 7: Fechar o chokepoint — `registrar_custo_automatico` exige destino

**Files:**
- Modify: `utils/financeiro_integration.py:58-219`
- Test: `tests/test_fase4_destino_custo.py` (acrescenta)

- [ ] **Step 1: Escreva os testes que falham**

Acrescente ao final de `tests/test_fase4_destino_custo.py`:

```python
# ---------------------------------------------------------------------------
# Porta de escrita: registrar_custo_automatico
# ---------------------------------------------------------------------------

def test_registrar_custo_sem_obra_cai_no_centro_administrativo():
    from utils.centro_custo import centro_custo_administrativo
    from utils.financeiro_integration import registrar_custo_automatico

    with app.app_context():
        a = _admin()
        filho = registrar_custo_automatico(
            admin_id=a.id, tipo_categoria='OUTROS',
            entidade_nome='Papelaria', entidade_id=None,
            data=date(2026, 6, 1), descricao='Resma de papel', valor=50,
            obra_id=None, origem_tabela='teste_fase4', force_v2=True)
        db.session.commit()

        assert filho is not None
        adm = centro_custo_administrativo(a.id, criar=False)
        assert adm is not None
        assert filho.obra_id is None
        assert filho.centro_custo_id == adm.id


def test_registrar_custo_com_obra_nao_toca_no_centro():
    from utils.financeiro_integration import registrar_custo_automatico

    with app.app_context():
        a = _admin()
        o = _obra(a.id)
        filho = registrar_custo_automatico(
            admin_id=a.id, tipo_categoria='MATERIAL',
            entidade_nome='Forn', entidade_id=None,
            data=date(2026, 6, 1), descricao='Perfil', valor=100,
            obra_id=o.id, origem_tabela='teste_fase4', force_v2=True)
        db.session.commit()

        assert filho.obra_id == o.id
        assert filho.centro_custo_id is None


def test_registrar_custo_faturamento_direto_sem_obra_e_recusado():
    from services.destino_custo import DestinoIndefinido
    from utils.financeiro_integration import registrar_custo_automatico

    with app.app_context():
        a = _admin()
        with pytest.raises(DestinoIndefinido):
            registrar_custo_automatico(
                admin_id=a.id, tipo_categoria='FATURAMENTO_DIRETO',
                entidade_nome='Cliente', entidade_id=None,
                data=date(2026, 6, 1), descricao='Material do cliente',
                valor=100, obra_id=None, origem_tabela='teste_fase4',
                force_v2=True)
        db.session.rollback()


def test_registrar_custo_mantem_pai_obra_id_em_dia():
    from utils.financeiro_integration import registrar_custo_automatico

    with app.app_context():
        a = _admin()
        o1, o2 = _obra(a.id), _obra(a.id)
        f1 = registrar_custo_automatico(
            admin_id=a.id, tipo_categoria='MATERIAL', entidade_nome='Forn X',
            entidade_id=None, data=date(2026, 6, 1), descricao='L1', valor=10,
            obra_id=o1.id, origem_tabela='teste_fase4', force_v2=True)
        db.session.commit()
        pai_id = f1.pai_id
        assert db.session.get(GestaoCustoPai, pai_id).obra_id == o1.id

        registrar_custo_automatico(
            admin_id=a.id, tipo_categoria='MATERIAL', entidade_nome='Forn X',
            entidade_id=None, data=date(2026, 6, 2), descricao='L2', valor=10,
            obra_id=o2.id, origem_tabela='teste_fase4', force_v2=True)
        db.session.commit()

        db.session.expire_all()
        assert db.session.get(GestaoCustoPai, pai_id).obra_id is None, (
            'pai virou multi-obra e obra_id tem de voltar para NULL')
```

- [ ] **Step 2: Rode e confirme que falha**

```bash
python -m pytest tests/test_fase4_destino_custo.py -v -k "registrar_custo"
```

Esperado: FAIL. Os dois primeiros porque `filho.centro_custo_id` fica `None`; o terceiro porque nada levanta `DestinoIndefinido`; o quarto porque `pai.obra_id` continua `None` desde o primeiro lançamento.

- [ ] **Step 3: Aplique o destino obrigatório no chokepoint**

Em `utils/financeiro_integration.py`, dentro de `registrar_custo_automatico`, localize o bloco que hoje começa na linha 91:

```python
    try:
        if not force_v2:
            from utils.tenant import is_v2_active
            if not is_v2_active():
                return None

        from app import db
        from models import GestaoCustoPai, GestaoCustoFilho
        from sqlalchemy import func
```

e substitua por:

```python
    # ── Fase 4 — destino obrigatório. Fica FORA do try/except abaixo de
    # propósito: o `except Exception: return None` do corpo engoliria a
    # recusa e o chamador acharia que gravou. Um custo sem destino tem de
    # explodir na cara de quem tentou gravar.
    from services.destino_custo import destino_de_filho_novo

    obra_id, centro_custo_id = destino_de_filho_novo(
        admin_id=admin_id,
        obra_id=obra_id,
        centro_custo_id=centro_custo_id,
        origem_tabela=origem_tabela,
        tipo_categoria=tipo_categoria,
    )

    try:
        if not force_v2:
            from utils.tenant import is_v2_active
            if not is_v2_active():
                return None

        from app import db
        from models import GestaoCustoPai, GestaoCustoFilho
        from sqlalchemy import func
```

Depois, localize o final da função (linha 208-215 de hoje):

```python
        pai.valor_total = Decimal(str(total_existente)) + valor_dec

        db.session.flush()
        logger.info(
            f"[OK] GestaoCustoFilho adicionado: pai={pai.id} valor={valor_dec} desc={descricao[:50]}"
        )
        return filho
```

e substitua por:

```python
        pai.valor_total = Decimal(str(total_existente)) + valor_dec

        # Fase 4 — `pai.obra_id` é derivado dos filhos e tem de acompanhar.
        # Precisa vir DEPOIS do add do filho e antes do flush final para que
        # a query de irmãos já enxergue a linha nova (o autoflush do
        # SQLAlchemy resolve isso dentro de `sincronizar_obra_do_pai`).
        from services.destino_custo import sincronizar_obra_do_pai
        sincronizar_obra_do_pai(pai)

        db.session.flush()
        logger.info(
            f"[OK] GestaoCustoFilho adicionado: pai={pai.id} valor={valor_dec} "
            f"obra={filho.obra_id} centro={filho.centro_custo_id} "
            f"desc={descricao[:50]}"
        )
        return filho
```

- [ ] **Step 4: Rode os testes**

```bash
python -m pytest tests/test_fase4_destino_custo.py -v -k "registrar_custo"
```

Esperado: os 4 testes PASSAM.

- [ ] **Step 5: Rode as suítes que consomem o chokepoint**

```bash
python -m pytest tests/test_painel_financeiro.py tests/test_resumo_custos_obra.py -q
```

Esperado: PASS. Se algum teste falhar por criar custo sem obra, ele estava documentando o furo — corrija o teste para passar `obra_id` ou para esperar o centro administrativo, e registre no commit qual foi.

- [ ] **Step 6: Commit**

```bash
git add utils/financeiro_integration.py tests/test_fase4_destino_custo.py
git commit -m "feat(fase4): registrar_custo_automatico exige destino

O chokepoint de 10 modulos (frota, alimentacao, transporte, reembolso,
rdo, importacao, obras) passa a resolver obra OU centro administrativo, e
a levantar DestinoIndefinido quando nao da. A validacao fica FORA do
try/except para nao ser engolida pelo 'return None'. pai.obra_id passa a
ser sincronizado a cada lancamento."
```

---

## Task 8: Fechar as telas de gestão de custos

**Files:**
- Modify: `gestao_custos_views.py:215,275-283` (`novo`), `:462-478` (`editar_filho`), `:965,990,1000` (`editar`), `:415-420` (`_recalcular_total_pai`)
- Modify: `templates/custos/gestao.html:175-183` e `:532-537`
- Test: `tests/test_fase4_destino_custo.py` (acrescenta)

- [ ] **Step 1: Escreva os testes que falham**

Acrescente ao final de `tests/test_fase4_destino_custo.py`:

```python
# ---------------------------------------------------------------------------
# Telas de gestão de custos
# ---------------------------------------------------------------------------

def _cliente_logado(user_id):
    c = app.test_client()
    with c.session_transaction() as sess:
        sess['_user_id'] = str(user_id)
        sess['_fresh'] = True
    return c


def test_lancamento_manual_sem_obra_grava_no_centro_administrativo():
    with app.app_context():
        a = _admin()
        aid = a.id

    cli = _cliente_logado(aid)
    resp = cli.post('/custos/gestao/novo', data={
        'tipo_categoria': 'OUTROS',
        'entidade_nome': 'Papelaria Central',
        'descricao': 'Resma A4',
        'valor': '75,50',
        'data_referencia': '2026-06-01',
        'obra_id': '',
    }, follow_redirects=False)
    assert resp.status_code in (302, 200)

    with app.app_context():
        from utils.centro_custo import centro_custo_administrativo
        filho = (GestaoCustoFilho.query
                 .filter_by(admin_id=aid, descricao='Resma A4').one())
        adm = centro_custo_administrativo(aid, criar=False)
        assert adm is not None
        assert filho.obra_id is None
        assert filho.centro_custo_id == adm.id


def test_editar_filho_nao_pode_mais_deixar_a_linha_sem_destino():
    with app.app_context():
        a = _admin()
        o = _obra(a.id)
        pai = _pai_com_filhos(a.id, [o.id])
        filho = GestaoCustoFilho.query.filter_by(pai_id=pai.id).one()
        aid, fid = a.id, filho.id

    cli = _cliente_logado(aid)
    resp = cli.post(f'/custos/gestao/filho/{fid}/editar', data={'obra_id': ''})
    assert resp.status_code == 200

    with app.app_context():
        from utils.centro_custo import centro_custo_administrativo
        db.session.expire_all()
        recarregado = db.session.get(GestaoCustoFilho, fid)
        adm = centro_custo_administrativo(aid, criar=False)
        assert recarregado.obra_id is None
        assert recarregado.centro_custo_id == adm.id, (
            'esvaziar a obra deixou a linha sem destino — '
            'gestao_custos_views.py:467-470 continua aberto')


def test_editar_filho_trocando_obra_limpa_o_centro_administrativo():
    with app.app_context():
        a = _admin()
        o = _obra(a.id)
        pai = _pai_com_filhos(a.id, [None], origem='folha_pagamento')
        filho = GestaoCustoFilho.query.filter_by(pai_id=pai.id).one()
        from utils.centro_custo import centro_custo_administrativo
        filho.centro_custo_id = centro_custo_administrativo(a.id).id
        db.session.commit()
        aid, fid, oid = a.id, filho.id, o.id

    cli = _cliente_logado(aid)
    resp = cli.post(f'/custos/gestao/filho/{fid}/editar',
                    data={'obra_id': str(oid)})
    assert resp.status_code == 200

    with app.app_context():
        db.session.expire_all()
        recarregado = db.session.get(GestaoCustoFilho, fid)
        assert recarregado.obra_id == oid
        assert recarregado.centro_custo_id is None


def test_pagar_leva_obra_e_centro_para_o_fluxo_caixa():
    from models import BancoEmpresa, FluxoCaixa

    with app.app_context():
        a = _admin()
        o = _obra(a.id)
        banco = BancoEmpresa(admin_id=a.id, nome_banco='Banco F4', ativo=True)
        db.session.add(banco)
        pai = _pai_com_filhos(a.id, [o.id])
        pai.valor_total = 10
        pai.saldo = 10
        pai.status = 'AUTORIZADO'
        pai.obra_id = o.id
        db.session.commit()
        aid, pid, bid, oid = a.id, pai.id, banco.id, o.id

    cli = _cliente_logado(aid)
    resp = cli.post(f'/custos/gestao/{pid}/pagar', data={
        'valor_pago': '10',
        'data_pagamento': '2026-06-10',
        'banco_id': str(bid),
    })
    assert resp.status_code in (302, 200)

    with app.app_context():
        fc = (FluxoCaixa.query
              .filter_by(admin_id=aid, referencia_tabela='gestao_custo_pai',
                         referencia_id=pid).one())
        assert fc.obra_id == oid
        assert fc.centro_custo_id is None
```

- [ ] **Step 2: Rode e confirme que falha**

```bash
python -m pytest tests/test_fase4_destino_custo.py -v -k "lancamento_manual or editar_filho or pagar_leva"
```

Esperado: FAIL nos 4 (destino não é aplicado; `FluxoCaixa` nasce sem obra).

- [ ] **Step 3: `novo()` — destino no lançamento manual**

Em `gestao_custos_views.py`, na função `novo()`, substitua o bloco de criação do filho (linhas 275-283):

```python
            filho = GestaoCustoFilho(
                pai_id=pai.id,
                admin_id=admin_id,
                data_referencia=data_ref,
                descricao=descricao or entidade_nome,
                valor=valor,
                obra_id=obra_id,
                origem_tabela='manual',
            )
            db.session.add(filho)
            db.session.commit()
```

por:

```python
            # Fase 4 — destino obrigatório. Sem obra o custo vai para o centro
            # administrativo do tenant, nunca para lugar nenhum.
            from services.destino_custo import (DestinoIndefinido,
                                                destino_de_filho_novo,
                                                sincronizar_obra_do_pai)
            try:
                obra_id, centro_custo_id = destino_de_filho_novo(
                    admin_id=admin_id, obra_id=obra_id, centro_custo_id=None,
                    origem_tabela='manual', tipo_categoria=tipo_categoria)
            except DestinoIndefinido as e:
                db.session.rollback()
                flash(str(e), 'danger')
                return redirect(url_for('gestao_custos.novo'))

            filho = GestaoCustoFilho(
                pai_id=pai.id,
                admin_id=admin_id,
                data_referencia=data_ref,
                descricao=descricao or entidade_nome,
                valor=valor,
                obra_id=obra_id,
                centro_custo_id=centro_custo_id,
                origem_tabela='manual',
            )
            db.session.add(filho)
            db.session.flush()
            sincronizar_obra_do_pai(pai)
            db.session.commit()
```

- [ ] **Step 4: `_recalcular_total_pai()` — mantém `obra_id` derivado em dia**

Em `gestao_custos_views.py`, substitua a função inteira (linhas 415-420):

```python
def _recalcular_total_pai(pai):
    """Recalcula valor_total + saldo do pai a partir dos filhos atuais."""
    total = (db.session.query(func.coalesce(func.sum(GestaoCustoFilho.valor), 0))
             .filter_by(pai_id=pai.id).scalar()) or Decimal('0.00')
    pai.valor_total = Decimal(str(total))
    pai.saldo = pai.valor_total - Decimal(str(pai.valor_pago or 0))
```

por:

```python
def _recalcular_total_pai(pai):
    """Recalcula valor_total, saldo e obra_id do pai a partir dos filhos.

    Fase 4: `pai.obra_id` é DERIVADO (models.py, class GestaoCustoPai). Toda
    escrita que mexe nos filhos passa por aqui, então é aqui que a derivação
    se mantém honesta — inclusive voltando para NULL quando o documento vira
    multi-obra.
    """
    from services.destino_custo import sincronizar_obra_do_pai

    total = (db.session.query(func.coalesce(func.sum(GestaoCustoFilho.valor), 0))
             .filter_by(pai_id=pai.id).scalar()) or Decimal('0.00')
    pai.valor_total = Decimal(str(total))
    pai.saldo = pai.valor_total - Decimal(str(pai.valor_pago or 0))
    sincronizar_obra_do_pai(pai)
```

- [ ] **Step 5: `editar_filho()` — esvaziar a obra vira "administrativo"**

Em `gestao_custos_views.py`, na função `editar_filho`, substitua o bloco das linhas 462-478:

```python
        obra_id_raw = request.form.get('obra_id', '').strip()
        obra_alterada = False
        obras_afetadas = set()
        if filho.obra_id:
            obras_afetadas.add(filho.obra_id)
        if obra_id_raw == '':
            if filho.obra_id is not None:
                obra_alterada = True
            filho.obra_id = None
        else:
            try:
                novo_obra_id = int(obra_id_raw)
                if novo_obra_id != filho.obra_id:
                    obra_alterada = True
                filho.obra_id = novo_obra_id
            except ValueError:
                pass
```

por:

```python
        # ── Fase 4 — o campo vazio não significa mais "sem destino".
        # Até 2026-07-21 esta rota fazia `filho.obra_id = None` e pronto: o
        # custo já lançado sumia do orçado×real da obra sem erro e sem
        # alerta. Agora, obra vazia = centro de custo administrativo do
        # tenant, que é um destino nomeado e somável.
        from services.destino_custo import (DestinoIndefinido,
                                            destino_de_filho_novo)

        obra_id_raw = request.form.get('obra_id', '').strip()
        obra_alterada = False
        obras_afetadas = set()
        if filho.obra_id:
            obras_afetadas.add(filho.obra_id)

        if obra_id_raw == '':
            if filho.obra_id is not None:
                obra_alterada = True
            try:
                _obra, centro_id = destino_de_filho_novo(
                    admin_id=admin_id, obra_id=None, centro_custo_id=None,
                    origem_tabela=filho.origem_tabela,
                    tipo_categoria=pai.tipo_categoria)
            except DestinoIndefinido as e:
                db.session.rollback()
                return jsonify({'status': 'error', 'message': str(e)}), 400
            filho.obra_id = None
            filho.centro_custo_id = centro_id
        else:
            try:
                novo_obra_id = int(obra_id_raw)
                if novo_obra_id != filho.obra_id:
                    obra_alterada = True
                filho.obra_id = novo_obra_id
                # Passou a ter obra: o carimbo administrativo sai de cena.
                filho.centro_custo_id = None
            except ValueError:
                return jsonify({'status': 'error',
                                'message': 'Obra inválida.'}), 400
```

- [ ] **Step 6: `editar()` — mesma regra na edição do pai**

Em `gestao_custos_views.py`, na função `editar`, substitua o bloco das linhas 987-1002:

```python
                # Atualizar ou criar filho principal
                if filho_principal:
                    filho_principal.descricao        = descricao_filho
                    filho_principal.obra_id          = obra_id_filho
                    filho_principal.data_referencia  = data_ref
                    filho_principal.valor            = valor
                else:
                    novo_filho = GestaoCustoFilho(
                        pai_id=pai.id,
                        admin_id=admin_id,
                        data_referencia=data_ref,
                        descricao=descricao_filho,
                        valor=valor,
                        obra_id=obra_id_filho,
                        origem_tabela='manual',
                    )
                    db.session.add(novo_filho)
```

por:

```python
                # Fase 4 — destino obrigatório também na edição do pai.
                from services.destino_custo import (DestinoIndefinido,
                                                    destino_de_filho_novo)
                try:
                    obra_destino, centro_destino = destino_de_filho_novo(
                        admin_id=admin_id, obra_id=obra_id_filho,
                        centro_custo_id=None, origem_tabela='manual',
                        tipo_categoria=tipo_categoria)
                except DestinoIndefinido as e:
                    db.session.rollback()
                    flash(str(e), 'danger')
                    return redirect(url_for('gestao_custos.editar', pai_id=pai.id))

                # Atualizar ou criar filho principal
                if filho_principal:
                    filho_principal.descricao        = descricao_filho
                    filho_principal.obra_id          = obra_destino
                    filho_principal.centro_custo_id  = centro_destino
                    filho_principal.data_referencia  = data_ref
                    filho_principal.valor            = valor
                else:
                    novo_filho = GestaoCustoFilho(
                        pai_id=pai.id,
                        admin_id=admin_id,
                        data_referencia=data_ref,
                        descricao=descricao_filho,
                        valor=valor,
                        obra_id=obra_destino,
                        centro_custo_id=centro_destino,
                        origem_tabela='manual',
                    )
                    db.session.add(novo_filho)

                db.session.flush()
                _recalcular_total_pai(pai)
```

- [ ] **Step 7: `pagar()` — o `FluxoCaixa` herda o destino**

Em `gestao_custos_views.py`, na função `pagar`, substitua a criação do `FluxoCaixa` (linhas 865-877):

```python
        # Criar FluxoCaixa para o valor pago agora
        fc = FluxoCaixa(
            admin_id=admin_id,
            data_movimento=data_pgto,
            tipo_movimento='SAIDA',
            categoria=cat_fc,
            valor=valor_pago_agora,
            descricao=f'{label} — {pai.entidade_nome}',
            referencia_id=pai.id,
            referencia_tabela='gestao_custo_pai',
            observacoes=conta or None,
            banco_id=int(banco_id_str_pagar),
        )
```

por:

```python
        # Fase 4 — o movimento de caixa herda o destino do documento. Antes
        # de 2026-07-21 o `FluxoCaixa` nascia sem obra e sem centro de custo
        # (0 de 15 linhas tinham centro no banco de dev), de modo que o
        # dinheiro saía sem atribuição nenhuma.
        # `pai.obra_id` é NULL quando o documento é multi-obra — nesse caso
        # não inventamos uma: a atribuição fina fica nos filhos, e o
        # movimento de caixa aponta para o centro administrativo.
        from utils.centro_custo import id_do_centro_administrativo
        fc_obra_id = pai.obra_id
        fc_centro_id = (None if fc_obra_id
                        else id_do_centro_administrativo(admin_id, criar=True))

        # Criar FluxoCaixa para o valor pago agora
        fc = FluxoCaixa(
            admin_id=admin_id,
            data_movimento=data_pgto,
            tipo_movimento='SAIDA',
            categoria=cat_fc,
            valor=valor_pago_agora,
            descricao=f'{label} — {pai.entidade_nome}',
            obra_id=fc_obra_id,
            centro_custo_id=fc_centro_id,
            referencia_id=pai.id,
            referencia_tabela='gestao_custo_pai',
            observacoes=conta or None,
            banco_id=int(banco_id_str_pagar),
        )
```

- [ ] **Step 8: Template — o campo deixa de ser "opcional"**

Em `templates/custos/gestao.html`, substitua o bloco das linhas 175-183:

```html
    <div class="mb-4">
      <label class="form-label fw-semibold">Obra (opcional)</label>
      <select name="obra_id" class="form-select">
        <option value="">— Nenhuma —</option>
        {% for o in obras %}
        <option value="{{ o.id }}" {% if v_obra == o.id %}selected{% endif %}>{{ o.nome }}</option>
        {% endfor %}
      </select>
    </div>
```

por:

```html
    <div class="mb-4">
      <label class="form-label fw-semibold">Destino do custo *</label>
      <select name="obra_id" class="form-select" required>
        <option value="">— Administrativo (não é de obra) —</option>
        {% for o in obras %}
        <option value="{{ o.id }}" {% if v_obra == o.id %}selected{% endif %}>{{ o.nome }}</option>
        {% endfor %}
      </select>
      <small class="text-muted">
        Todo custo tem destino. Sem obra, ele entra no centro de custo
        administrativo da empresa — não desaparece do resultado.
      </small>
    </div>
```

E, no modal de edição de linha, substitua as linhas 532-537:

```html
              <label class="form-label fw-semibold small text-uppercase text-muted">Obra</label>
              <select class="form-select" name="obra_id" id="editFilhoObra">
                <option value="">— Sem obra —</option>
              </select>
```

por:

```html
              <label class="form-label fw-semibold small text-uppercase text-muted">Destino do custo</label>
              <select class="form-select" name="obra_id" id="editFilhoObra">
                <option value="">— Administrativo (não é de obra) —</option>
              </select>
```

- [ ] **Step 9: Rode os testes**

```bash
python -m pytest tests/test_fase4_destino_custo.py -v
```

Esperado: os 19 testes PASSAM.

- [ ] **Step 10: Commit**

```bash
git add gestao_custos_views.py templates/custos/gestao.html tests/test_fase4_destino_custo.py
git commit -m "feat(fase4): telas de custo com destino obrigatorio

'Obra (opcional)' vira 'Destino do custo *', e o campo vazio passa a
significar 'Administrativo' em vez de 'lugar nenhum'. editar_filho nao
consegue mais deixar a linha sem destino. _recalcular_total_pai mantem
pai.obra_id em dia, e o FluxoCaixa de pagar() herda obra ou centro."
```

---

## Task 9: Fechar os produtores estruturais (folha e almoxarifado)

**Files:**
- Modify: `event_manager.py:223-231`
- Modify: `folha_pagamento_views.py:253-261`
- Modify: `compras_views.py:215-224` e `:336-345`
- Test: `tests/test_fase4_destino_custo.py` (acrescenta)

- [ ] **Step 1: Escreva os testes que falham**

Acrescente ao final de `tests/test_fase4_destino_custo.py`:

```python
# ---------------------------------------------------------------------------
# Produtores estruturais de órfão
# ---------------------------------------------------------------------------

def test_nenhum_criador_de_filho_grava_sem_destino():
    """Varredura estática: todo `GestaoCustoFilho(` de produção passa
    `obra_id` OU `centro_custo_id` no mesmo bloco de argumentos."""
    import re
    from pathlib import Path

    raiz = Path(__file__).resolve().parent.parent
    alvos = [
        'gestao_custos_views.py', 'compras_views.py',
        'folha_pagamento_views.py', 'event_manager.py',
        'services/importacao_excel.py', 'utils/financeiro_integration.py',
    ]
    faltando = []
    for rel in alvos:
        texto = (raiz / rel).read_text(encoding='utf-8')
        for m in re.finditer(r'GestaoCustoFilho\((.*?)\)\s*\n', texto,
                             re.DOTALL):
            bloco = m.group(1)
            if 'obra_id' not in bloco and 'centro_custo_id' not in bloco:
                linha = texto[:m.start()].count('\n') + 1
                faltando.append(f'{rel}:{linha}')
    assert not faltando, (
        'GestaoCustoFilho criado sem destino em: ' + ', '.join(faltando))


def test_entrada_de_almoxarifado_vai_para_o_centro_administrativo():
    from models import AlmoxarifadoItem, AlmoxarifadoMovimentacao, Fornecedor

    with app.app_context():
        a = _admin()
        forn = Fornecedor(admin_id=a.id, nome='Forn Almox', ativo=True)
        item = AlmoxarifadoItem(admin_id=a.id, nome='Perfil U',
                                unidade_medida='un')
        db.session.add_all([forn, item])
        db.session.flush()
        mov = AlmoxarifadoMovimentacao(
            admin_id=a.id, item_id=item.id, tipo_movimentacao='ENTRADA',
            quantidade=10, valor_unitario=5, fornecedor_id=forn.id,
            data_movimento=date(2026, 6, 1))
        db.session.add(mov)
        db.session.commit()
        aid, mid = a.id, mov.id

    with app.app_context():
        from event_manager import processar_entrada_almoxarifado
        processar_entrada_almoxarifado(mid)

    with app.app_context():
        from utils.centro_custo import centro_custo_administrativo
        adm = centro_custo_administrativo(aid, criar=False)
        filhos = GestaoCustoFilho.query.filter_by(
            admin_id=aid, origem_tabela='almoxarifado_movimento',
            origem_id=mid).all()
        assert filhos, 'nenhum GestaoCustoFilho criado para a entrada'
        for f in filhos:
            assert f.obra_id is None
            assert f.centro_custo_id == adm.id
```

> **Nota para quem executa:** o segundo teste chama `processar_entrada_almoxarifado`. Confirme o nome exato da função em `event_manager.py` antes de rodar — ela é a que contém o bloco de `event_manager.py:203-232`. Se o nome divergir, ajuste o import (e só o import; o resto do teste vale).

- [ ] **Step 2: Rode e confirme que falha**

```bash
python -m pytest tests/test_fase4_destino_custo.py -v -k "nenhum_criador or almoxarifado"
```

Esperado: FAIL. A varredura estática lista `event_manager.py:223` e `folha_pagamento_views.py:253`.

- [ ] **Step 3: `event_manager.py` — entrada de almoxarifado é administrativa**

Em `event_manager.py`, substitua o bloco das linhas 223-232:

```python
        gcf = GestaoCustoFilho(
            pai_id=gcp.id,
            admin_id=admin_id,
            data_referencia=data_mov,
            descricao=f"Entrada de material - {item_nome} (Movimento #{movimento_id})",
            valor=valor_total,
            origem_tabela='almoxarifado_movimento',
            origem_id=movimento_id,
        )
        db.session.add(gcf)
```

por:

```python
        # Fase 4 — material que ENTRA em estoque ainda não é custo de obra;
        # vira quando sai. Até 2026-07-21 esta linha nascia sem obra e sem
        # centro, e o custo sumia do resultado. Destino: centro
        # administrativo do tenant.
        from utils.centro_custo import id_do_centro_administrativo
        from services.destino_custo import sincronizar_obra_do_pai

        gcf = GestaoCustoFilho(
            pai_id=gcp.id,
            admin_id=admin_id,
            data_referencia=data_mov,
            descricao=f"Entrada de material - {item_nome} (Movimento #{movimento_id})",
            valor=valor_total,
            obra_id=None,
            centro_custo_id=id_do_centro_administrativo(admin_id, criar=True),
            origem_tabela='almoxarifado_movimento',
            origem_id=movimento_id,
        )
        db.session.add(gcf)
        db.session.flush()
        sincronizar_obra_do_pai(gcp)
```

- [ ] **Step 4: `folha_pagamento_views.py` — folha é administrativa**

Em `folha_pagamento_views.py`, substitua o bloco das linhas 253-262:

```python
                            gcf = GestaoCustoFilho(
                                pai_id=gcp.id,
                                admin_id=current_user.id,
                                data_referencia=mes_referencia,
                                descricao=f"Salário {mes_ref_str} - {funcionario.nome}",
                                valor=salario_liq,
                                origem_tabela='folha_pagamento',
                                origem_id=folha.id,
                            )
                            db.session.add(gcf)
```

por:

```python
                            # Fase 4 — a folha é custo ADMINISTRATIVO. A mão
                            # de obra que é custo de obra já entra por outro
                            # caminho e já vem com obra: os filhos de origem
                            # rdo_mao_obra / rdo_mao_obra_va / rdo_mao_obra_vt
                            # / rdo_custo_diario têm obra em 100% dos casos
                            # (conferido no banco em 2026-07-21). Mandar a
                            # folha para obra seria contagem dupla.
                            from utils.centro_custo import id_do_centro_administrativo
                            from services.destino_custo import sincronizar_obra_do_pai

                            gcf = GestaoCustoFilho(
                                pai_id=gcp.id,
                                admin_id=current_user.id,
                                data_referencia=mes_referencia,
                                descricao=f"Salário {mes_ref_str} - {funcionario.nome}",
                                valor=salario_liq,
                                obra_id=None,
                                centro_custo_id=id_do_centro_administrativo(
                                    current_user.id, criar=True),
                                origem_tabela='folha_pagamento',
                                origem_id=folha.id,
                            )
                            db.session.add(gcf)
                            db.session.flush()
                            sincronizar_obra_do_pai(gcp)
```

- [ ] **Step 5: `compras_views.py` — pedido sem obra vira administrativo**

Em `compras_views.py`, substitua o bloco das linhas 215-224:

```python
        gcf = GestaoCustoFilho(
            pai_id=gcp.id,
            admin_id=admin_id,
            data_referencia=pedido.data_compra,
            descricao=desc_cp[:300],
            valor=v,
            obra_id=pedido.obra_id,
            obra_servico_custo_id=pedido.obra_servico_custo_id,
            origem_tabela='pedido_compra',
            origem_id=pedido.id,
        )
        db.session.add(gcf)
```

por:

```python
        # Fase 4 — `pedido.obra_id` é nullable (models.py:4736) e
        # `compras_views.py:583` aceita ausência com `or None`. Compra de
        # material de escritório é legítima; o que não pode é o custo ficar
        # sem destino.
        from utils.centro_custo import id_do_centro_administrativo
        gcf = GestaoCustoFilho(
            pai_id=gcp.id,
            admin_id=admin_id,
            data_referencia=pedido.data_compra,
            descricao=desc_cp[:300],
            valor=v,
            obra_id=pedido.obra_id,
            centro_custo_id=(None if pedido.obra_id
                             else id_do_centro_administrativo(admin_id, criar=True)),
            obra_servico_custo_id=pedido.obra_servico_custo_id,
            origem_tabela='pedido_compra',
            origem_id=pedido.id,
        )
        db.session.add(gcf)
        gcp.obra_id = pedido.obra_id
```

E, no faturamento direto (linhas 336-345):

```python
    gcf = GestaoCustoFilho(
        pai_id=gcp.id,
        admin_id=admin_id,
        data_referencia=pedido.data_compra,
        descricao=desc_cp[:300],
        valor=pedido.valor_total,
        obra_id=pedido.obra_id,
        obra_servico_custo_id=pedido.obra_servico_custo_id,
        origem_tabela='pedido_compra',
        origem_id=pedido.id,
    )
    db.session.add(gcf)
```

por:

```python
    # Fase 4 — FATURAMENTO_DIRETO é material que o CLIENTE paga direto ao
    # fornecedor DA OBRA. Sem obra ele não significa nada, então aqui não há
    # fallback administrativo: recusa.
    if not pedido.obra_id:
        db.session.rollback()
        flash('Faturamento direto exige uma obra: é material que o cliente '
              'paga direto ao fornecedor da obra.', 'danger')
        return redirect(url_for('compras.detalhe', pedido_id=pedido.id))

    gcf = GestaoCustoFilho(
        pai_id=gcp.id,
        admin_id=admin_id,
        data_referencia=pedido.data_compra,
        descricao=desc_cp[:300],
        valor=pedido.valor_total,
        obra_id=pedido.obra_id,
        obra_servico_custo_id=pedido.obra_servico_custo_id,
        origem_tabela='pedido_compra',
        origem_id=pedido.id,
    )
    db.session.add(gcf)
    gcp.obra_id = pedido.obra_id
```

> **Nota para quem executa:** confirme o endpoint do `redirect` acima com `grep -n "compras_bp.route" compras_views.py` — se não existir `compras.detalhe`, use `url_for('compras.index')`.

- [ ] **Step 6: Rode os testes**

```bash
python -m pytest tests/test_fase4_destino_custo.py -v -k "nenhum_criador or almoxarifado"
python -m pytest tests/test_fase4_destino_custo.py -q
```

Esperado: todos PASSAM.

- [ ] **Step 7: Commit**

```bash
git add event_manager.py folha_pagamento_views.py compras_views.py tests/test_fase4_destino_custo.py
git commit -m "feat(fase4): fecha os produtores estruturais de custo orfao

Almoxarifado (event_manager.py:223) e folha (folha_pagamento_views.py:253)
criavam GestaoCustoFilho sem destino nenhum. Passam a apontar o centro
administrativo, que e a resposta certa: estoque ainda nao e custo de obra,
e a mao de obra de obra ja entra pelo RDO com obra. Faturamento direto sem
obra passa a ser recusado. Teste de varredura estatica trava a regressao."
```

---

## Task 10: A listagem de custos passa a usar a coluna (e o escopo da Fase 1)

**Files:**
- Modify: `gestao_custos_views.py:113-127` (filtro por obra) e `:202` / `:938` (dropdowns de obra)
- Test: `tests/test_fase4_destino_custo.py` (acrescenta)

- [ ] **Step 1: Escreva os testes que falham**

Acrescente ao final de `tests/test_fase4_destino_custo.py`:

```python
# ---------------------------------------------------------------------------
# Listagem: filtro por obra e escopo da Fase 1
# ---------------------------------------------------------------------------

def test_filtro_por_obra_acha_pai_unanime_e_multiobra():
    with app.app_context():
        a = _admin()
        o1, o2 = _obra(a.id), _obra(a.id)
        pai_u = _pai_com_filhos(a.id, [o1.id])
        pai_m = _pai_com_filhos(a.id, [o1.id, o2.id])
        pai_outro = _pai_com_filhos(a.id, [o2.id])
        from scripts.backfill_destino_custo import aplicar_pais
        aplicar_pais(admin_id=a.id)
        db.session.commit()
        aid, oid = a.id, o1.id
        ids = (pai_u.id, pai_m.id, pai_outro.id)

    cli = _cliente_logado(aid)
    resp = cli.get(f'/custos/gestao/?obra_id={oid}')
    assert resp.status_code == 200
    corpo = resp.get_data(as_text=True)
    assert f'/custos/gestao/{ids[0]}/' in corpo or str(ids[0]) in corpo
    assert str(ids[1]) in corpo, 'pai multi-obra sumiu do filtro por obra'


def test_dropdown_de_obras_respeita_o_escopo_da_fase_1():
    """A lista de obras da tela de custos sai de `obras_visiveis()`."""
    import inspect

    import gestao_custos_views

    fonte = inspect.getsource(gestao_custos_views)
    assert 'obras_visiveis' in fonte, (
        'gestao_custos_views ainda monta o dropdown com '
        'Obra.query.filter_by(admin_id=...) — ignora o escopo por obra da '
        'Fase 1')
```

- [ ] **Step 2: Rode e confirme que falha**

```bash
python -m pytest tests/test_fase4_destino_custo.py -v -k "filtro_por_obra or dropdown"
```

Esperado: FAIL no segundo (`obras_visiveis` não aparece no módulo). O primeiro pode passar por acidente — o passo 3 troca a implementação sem mudar o comportamento observável, e é por isso que o teste existe.

- [ ] **Step 3: Filtro por obra usa a coluna nova, sem perder o multi-obra**

Em `gestao_custos_views.py`, substitua o bloco das linhas 122-127:

```python
    if filtro_obra_id:
        # Filtra GestaoCustoPai que têm ao menos um filho ligado à obra
        sub = db.session.query(GestaoCustoFilho.pai_id).filter_by(
            obra_id=filtro_obra_id, admin_id=admin_id
        ).subquery()
        q = q.filter(GestaoCustoPai.id.in_(sub))
```

por:

```python
    if filtro_obra_id:
        # Fase 4 — o caminho rápido é `pai.obra_id` (coluna derivada, com
        # índice `ix_gestao_custo_pai_obra_id`), que resolve ~94% dos casos
        # sem subquery. O OR com a subquery continua necessário para os pais
        # MULTI-OBRA, cujo `obra_id` é NULL de propósito: o documento tem
        # linhas na obra filtrada, mas não é "daquela obra".
        sub = db.session.query(GestaoCustoFilho.pai_id).filter_by(
            obra_id=filtro_obra_id, admin_id=admin_id
        ).subquery()
        q = q.filter(db.or_(
            GestaoCustoPai.obra_id == filtro_obra_id,
            GestaoCustoPai.id.in_(db.session.query(sub.c.pai_id)),
        ))
```

- [ ] **Step 4: Dropdowns de obra passam pelo escopo da Fase 1**

Em `gestao_custos_views.py` há três lugares que montam a lista de obras: linha 202 (`novo`), linha ~938 (`editar`) e linha ~182 (`index`). Em cada um, substitua:

```python
    obras = Obra.query.filter_by(admin_id=admin_id, ativo=True).order_by(Obra.nome).all()
```

por:

```python
    # Fase 4 + Fase 1 — a lista de obras da tela de custos respeita o escopo
    # por obra (`utils/autorizacao.obras_visiveis`, criado na Fase 1). Com a
    # flag `escopo_obra_ativo` desligada o resultado é idêntico ao anterior.
    from utils.autorizacao import obras_visiveis
    obras = (obras_visiveis(admin_id=admin_id)
             .filter(Obra.ativo.is_(True))
             .order_by(Obra.nome).all())
```

- [ ] **Step 5: Rode os testes**

```bash
python -m pytest tests/test_fase4_destino_custo.py -q
```

Esperado: todos PASSAM.

- [ ] **Step 6: Commit**

```bash
git add gestao_custos_views.py tests/test_fase4_destino_custo.py
git commit -m "perf(fase4): filtro de custo por obra usa a coluna derivada

O filtro sai de subquery pura para OR entre pai.obra_id (indexado) e a
subquery, que continua cobrindo os pais multi-obra. Os dropdowns de obra
passam por utils.autorizacao.obras_visiveis, respeitando o escopo da
Fase 1."
```

---

## Task 11: Relatório de conformidade — o gate da constraint

**Files:**
- Create: `scripts/relatorio_destino_custo.py`
- Test: `tests/test_fase4_destino_custo.py` (acrescenta)

- [ ] **Step 1: Escreva os testes que falham**

Acrescente ao final de `tests/test_fase4_destino_custo.py`:

```python
# ---------------------------------------------------------------------------
# Relatório de conformidade
# ---------------------------------------------------------------------------

def test_conformidade_reporta_zero_quando_tudo_tem_destino():
    from scripts.relatorio_destino_custo import conformidade

    with app.app_context():
        a = _admin()
        o = _obra(a.id)
        _pai_com_filhos(a.id, [o.id, o.id])

        rel = conformidade(admin_id=a.id)
        assert rel['sem_destino'] == 0
        assert rel['pronto_para_constraint'] is True


def test_conformidade_lista_os_pendentes_com_valor():
    from scripts.relatorio_destino_custo import conformidade

    with app.app_context():
        a = _admin()
        _pai_com_filhos(a.id, [None])

        rel = conformidade(admin_id=a.id)
        assert rel['sem_destino'] == 1
        assert rel['pronto_para_constraint'] is False
        assert float(rel['valor_sem_destino']) == 10.0
        assert len(rel['amostra']) == 1
        assert rel['amostra'][0]['pai_id'] is not None
```

- [ ] **Step 2: Rode e confirme que falha**

```bash
python -m pytest tests/test_fase4_destino_custo.py -v -k "conformidade"
```

Esperado: FAIL com `ModuleNotFoundError: No module named 'scripts.relatorio_destino_custo'`.

- [ ] **Step 3: Crie `scripts/relatorio_destino_custo.py`**

```python
#!/usr/bin/env python3
"""Relatório de conformidade do destino do custo — SIGE Fase 4.

Este script é o GATE da migration 253/254. Enquanto ele reportar
`sem_destino > 0`, a constraint não deve ser validada: validar com linha
pendente derruba o boot da aplicação.

READ-ONLY. Não grava nada, em nenhuma circunstância.

Uso:
    python scripts/relatorio_destino_custo.py
    python scripts/relatorio_destino_custo.py --tenant 832
    python scripts/relatorio_destino_custo.py --amostra 50
"""
from __future__ import annotations

import argparse
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def conformidade(admin_id=None, limite_amostra=20):
    """Quantas linhas de custo continuam sem destino, e quais."""
    from sqlalchemy import text

    from app import db

    filtro = 'AND f.admin_id = :aid' if admin_id else ''
    params = {'aid': admin_id} if admin_id else {}

    total = db.session.execute(text(f"""
        SELECT count(*) FROM gestao_custo_filho f
        WHERE f.obra_id IS NULL AND f.centro_custo_id IS NULL {filtro}
    """), params).scalar() or 0

    valor = db.session.execute(text(f"""
        SELECT COALESCE(sum(f.valor), 0) FROM gestao_custo_filho f
        WHERE f.obra_id IS NULL AND f.centro_custo_id IS NULL {filtro}
    """), params).scalar() or 0

    por_origem = db.session.execute(text(f"""
        SELECT COALESCE(f.origem_tabela, '(sem origem)') AS origem, count(*) AS n
        FROM gestao_custo_filho f
        WHERE f.obra_id IS NULL AND f.centro_custo_id IS NULL {filtro}
        GROUP BY 1 ORDER BY n DESC
    """), params).fetchall()

    por_tenant = db.session.execute(text(f"""
        SELECT f.admin_id, count(*) AS n
        FROM gestao_custo_filho f
        WHERE f.obra_id IS NULL AND f.centro_custo_id IS NULL {filtro}
        GROUP BY 1 ORDER BY n DESC LIMIT 20
    """), params).fetchall()

    amostra = db.session.execute(text(f"""
        SELECT f.id, f.pai_id, f.admin_id, f.data_referencia, f.valor,
               COALESCE(f.origem_tabela, ''), LEFT(COALESCE(f.descricao, ''), 60)
        FROM gestao_custo_filho f
        WHERE f.obra_id IS NULL AND f.centro_custo_id IS NULL {filtro}
        ORDER BY f.valor DESC
        LIMIT :lim
    """), {**params, 'lim': limite_amostra}).fetchall()

    pais_sem_obra = db.session.execute(text("""
        SELECT count(*) FROM gestao_custo_pai p
        WHERE p.obra_id IS NULL
    """) if not admin_id else text("""
        SELECT count(*) FROM gestao_custo_pai p
        WHERE p.obra_id IS NULL AND p.admin_id = :aid
    """), params).scalar() or 0

    tenants_sem_centro = db.session.execute(text("""
        SELECT count(*) FROM usuario u
        WHERE u.tipo_usuario IN ('ADMIN', 'SUPER_ADMIN')
          AND NOT EXISTS (
              SELECT 1 FROM centro_custo c
              WHERE c.admin_id = u.id AND c.tipo = 'administrativo')
    """)).scalar() or 0

    return {
        'sem_destino': int(total),
        'valor_sem_destino': valor,
        'por_origem': [{'origem': o, 'n': n} for o, n in por_origem],
        'por_tenant': [{'admin_id': a, 'n': n} for a, n in por_tenant],
        'amostra': [{
            'filho_id': r[0], 'pai_id': r[1], 'admin_id': r[2],
            'data': str(r[3]), 'valor': str(r[4]), 'origem': r[5],
            'descricao': r[6],
        } for r in amostra],
        'pais_sem_obra_derivada': int(pais_sem_obra),
        'tenants_sem_centro_administrativo': int(tenants_sem_centro),
        'pronto_para_constraint': int(total) == 0,
    }


def imprimir(rel):
    print('=' * 72)
    print('FASE 4 — CONFORMIDADE DO DESTINO DO CUSTO')
    print('=' * 72)
    print(f"gestao_custo_filho SEM destino ....... {rel['sem_destino']}")
    print(f"  valor envolvido .................... R$ {rel['valor_sem_destino']}")
    print(f"gestao_custo_pai com obra_id NULL .... {rel['pais_sem_obra_derivada']}"
          "   <- inclui multi-obra e administrativo, é esperado")
    print(f"tenants sem centro administrativo .... "
          f"{rel['tenants_sem_centro_administrativo']}")
    if rel['por_origem']:
        print('-' * 72)
        print('Pendentes por origem:')
        for linha in rel['por_origem']:
            print(f"  {linha['origem']:<30} {linha['n']:>7}")
    if rel['amostra']:
        print('-' * 72)
        print('Maiores pendentes:')
        for a in rel['amostra']:
            print(f"  filho={a['filho_id']:<8} pai={a['pai_id']:<8} "
                  f"tenant={a['admin_id']:<6} R$ {a['valor']:>12} "
                  f"{a['origem']:<24} {a['descricao']}")
    print('=' * 72)
    if rel['pronto_para_constraint']:
        print('✅ PRONTO — a migration 254 (VALIDATE) pode rodar.')
    else:
        print('❌ NÃO VALIDE A CONSTRAINT. Rode antes:')
        print('   python scripts/backfill_destino_custo.py --aplicar')
    print('=' * 72)


def main():
    ap = argparse.ArgumentParser(description='Conformidade do destino do custo')
    ap.add_argument('--tenant', type=int, default=None)
    ap.add_argument('--amostra', type=int, default=20)
    args = ap.parse_args()

    from app import app

    with app.app_context():
        imprimir(conformidade(admin_id=args.tenant,
                              limite_amostra=args.amostra))


if __name__ == '__main__':
    main()
```

- [ ] **Step 4: Rode os testes e o relatório**

```bash
python -m pytest tests/test_fase4_destino_custo.py -v -k "conformidade"
python scripts/relatorio_destino_custo.py
```

Esperado: os 2 testes PASSAM; o relatório termina em `✅ PRONTO` (porque a Task 6 já rodou o backfill neste banco).

- [ ] **Step 5: Commit**

```bash
git add scripts/relatorio_destino_custo.py tests/test_fase4_destino_custo.py
git commit -m "feat(fase4): relatorio de conformidade do destino do custo

Read-only. E o gate da constraint: enquanto reportar sem_destino > 0 a
migration 254 nao deve validar, porque validar com pendencia derruba o
boot. Reporta tambem tenants sem centro administrativo."
```

---

## Task 12: A trava — `CHECK ... NOT VALID` (migration 253)

**Files:**
- Modify: `migrations.py` (nova função + registro)
- Test: `tests/test_fase4_destino_custo.py` (acrescenta)

- [ ] **Step 1: Escreva os testes que falham**

Acrescente ao final de `tests/test_fase4_destino_custo.py`:

```python
# ---------------------------------------------------------------------------
# Constraint: todo lançamento novo tem destino
# ---------------------------------------------------------------------------

def test_banco_recusa_filho_novo_sem_destino():
    from sqlalchemy.exc import IntegrityError

    with app.app_context():
        a = _admin()
        pai = GestaoCustoPai(
            admin_id=a.id, tipo_categoria='OUTROS', entidade_nome='X',
            valor_total=0, status='PENDENTE')
        db.session.add(pai)
        db.session.flush()
        db.session.add(GestaoCustoFilho(
            pai_id=pai.id, admin_id=a.id, data_referencia=date(2026, 6, 1),
            descricao='Sem destino', valor=1,
            obra_id=None, centro_custo_id=None))
        with pytest.raises(IntegrityError):
            db.session.commit()
        db.session.rollback()


def test_banco_aceita_filho_com_obra_e_com_centro():
    with app.app_context():
        from utils.centro_custo import centro_custo_administrativo

        a = _admin()
        o = _obra(a.id)
        adm = centro_custo_administrativo(a.id)
        pai = GestaoCustoPai(
            admin_id=a.id, tipo_categoria='OUTROS', entidade_nome='X',
            valor_total=0, status='PENDENTE')
        db.session.add(pai)
        db.session.flush()
        db.session.add_all([
            GestaoCustoFilho(
                pai_id=pai.id, admin_id=a.id, data_referencia=date(2026, 6, 1),
                descricao='Com obra', valor=1, obra_id=o.id),
            GestaoCustoFilho(
                pai_id=pai.id, admin_id=a.id, data_referencia=date(2026, 6, 1),
                descricao='Com centro', valor=1, centro_custo_id=adm.id),
        ])
        db.session.commit()
        assert GestaoCustoFilho.query.filter_by(pai_id=pai.id).count() == 2


def test_constraint_existe_no_banco():
    from sqlalchemy import text

    with app.app_context():
        achado = db.session.execute(text("""
            SELECT conname FROM pg_constraint
            WHERE conrelid = 'gestao_custo_filho'::regclass
              AND conname = 'ck_gestao_custo_filho_destino'
        """)).fetchone()
        assert achado is not None, (
            'ck_gestao_custo_filho_destino não existe — a migration 253 não '
            'rodou')
```

- [ ] **Step 2: Rode e confirme que falha**

```bash
python -m pytest tests/test_fase4_destino_custo.py -v -k "banco_recusa or constraint_existe"
```

Esperado: FAIL. O insert sem destino é aceito; a constraint não existe.

- [ ] **Step 3: Escreva a migration 253**

Em `migrations.py`, antes de `def executar_migracoes():`, insira:

```python
def migration_253_check_destino_custo_not_valid():
    """Fase 4 — CHECK de destino em `gestao_custo_filho`, em modo NOT VALID.

    A invariante: todo lançamento de custo aponta uma obra OU um centro de
    custo. Nunca nenhum dos dois.

    Por que o CHECK vai no FILHO e não um NOT NULL no pai:
    `utils/financeiro_integration.py:118-131` reaproveita o mesmo
    `GestaoCustoPai` em aberto para o mesmo (tenant, categoria, entidade,
    categoria de fluxo de caixa), SEM olhar obra — um título a pagar
    legitimamente carrega linhas de obras diferentes (9 casos no banco de
    dev em 2026-07-21). `NOT NULL` em `gestao_custo_pai.obra_id` quebraria
    esses documentos e todo o fluxo administrativo.

    Por que NOT VALID e não a constraint pronta: `NOT VALID` faz o Postgres
    aplicar a regra a toda linha NOVA ou ATUALIZADA sem varrer a tabela e
    sem exigir que o histórico já esteja limpo. É o que permite subir a
    trava com o backfill ainda em revisão. A validação do histórico é a
    migration 254, que é a ÚLTIMA tarefa desta fase e só roda com o
    relatório de conformidade zerado.
    """
    logger.info("[Migration 253] Iniciando — CHECK de destino (NOT VALID)")

    existe = db.session.execute(text("""
        SELECT 1 FROM pg_constraint
        WHERE conrelid = 'gestao_custo_filho'::regclass
          AND conname = 'ck_gestao_custo_filho_destino'
        LIMIT 1
    """)).fetchone()

    if existe:
        logger.info("[Migration 253] Constraint já existe — nada a fazer")
        return

    db.session.execute(text("""
        ALTER TABLE gestao_custo_filho
        ADD CONSTRAINT ck_gestao_custo_filho_destino
        CHECK (obra_id IS NOT NULL OR centro_custo_id IS NOT NULL)
        NOT VALID
    """))
    db.session.commit()

    pendentes = db.session.execute(text("""
        SELECT count(*) FROM gestao_custo_filho
        WHERE obra_id IS NULL AND centro_custo_id IS NULL
    """)).scalar()
    logger.info(
        "[Migration 253] Concluída — escrita nova travada. %s linha(s) "
        "histórica(s) ainda sem destino; rode "
        "scripts/backfill_destino_custo.py --aplicar antes da migration 254",
        pendentes)
```

- [ ] **Step 4: Adicione o CHECK também ao modelo**

Em `models.py`, na `class GestaoCustoFilho`, imediatamente após a linha do relationship `obra_servico_custo` (`models.py:5316`), acrescente:

```python
    __table_args__ = (
        # Fase 4 — todo lançamento de custo tem destino: uma obra OU o
        # centro de custo administrativo do tenant. Criada pela migration
        # 253 em modo NOT VALID e validada pela 254.
        db.CheckConstraint(
            'obra_id IS NOT NULL OR centro_custo_id IS NOT NULL',
            name='ck_gestao_custo_filho_destino'),
    )
```

- [ ] **Step 5: Registre a migration**

Em `migrations.py`, em `migrations_to_run`, após a entrada `252`:

```python
            (253, "Fase 4 — CHECK ck_gestao_custo_filho_destino em modo NOT VALID (trava a escrita nova)", migration_253_check_destino_custo_not_valid),
```

- [ ] **Step 6: Aplique e rode os testes**

```bash
python -c "
from app import app
from migrations import executar_migracoes
with app.app_context():
    executar_migracoes()
" 2>&1 | grep -E "253|ERRO|ERROR"
python -m pytest tests/test_fase4_destino_custo.py -q
```

Esperado: `[Migration 253] Concluída — escrita nova travada. 0 linha(s)...` e todos os testes PASSAM.

- [ ] **Step 7: Commit**

```bash
git add models.py migrations.py tests/test_fase4_destino_custo.py
git commit -m "feat(fase4): CHECK de destino em gestao_custo_filho (NOT VALID)

Todo lancamento de custo aponta obra OU centro de custo. A trava vai no
FILHO, nao um NOT NULL no pai: pai multi-obra e projeto, nao defeito.
NOT VALID trava a escrita nova sem exigir o historico limpo — a validacao
do historico e a migration 254, atras do relatorio de conformidade."
```

---

## Task 13: A última tarefa — `VALIDATE CONSTRAINT` (migration 254)

**Files:**
- Modify: `migrations.py` (nova função + registro)
- Test: `tests/test_fase4_destino_custo.py` (acrescenta)

> ⚠️ **Ordem inegociável.** Esta é a única tarefa que varre a tabela inteira e recusa o histórico sujo. Ela só entra depois de: coluna criada (Task 3) → backfill em dry-run revisado (Task 4) → backfill aplicado (Tasks 5-6) → portas de escrita fechadas (Tasks 7-9) → relatório de conformidade zerado (Task 11) → trava da escrita nova (Task 12). Fora dessa ordem, ela derruba a escrita em produção.

- [ ] **Step 1: Escreva o teste que falha**

Acrescente ao final de `tests/test_fase4_destino_custo.py`:

```python
def test_constraint_de_destino_esta_validada():
    from sqlalchemy import text

    with app.app_context():
        convalidated = db.session.execute(text("""
            SELECT convalidated FROM pg_constraint
            WHERE conrelid = 'gestao_custo_filho'::regclass
              AND conname = 'ck_gestao_custo_filho_destino'
        """)).scalar()
        assert convalidated is True, (
            'a constraint existe mas está NOT VALID — o histórico não foi '
            'validado (migration 254)')


def test_nao_sobrou_lancamento_sem_destino_no_banco():
    from scripts.relatorio_destino_custo import conformidade

    with app.app_context():
        rel = conformidade()
        assert rel['sem_destino'] == 0, (
            f"{rel['sem_destino']} lançamento(s) ainda sem destino: "
            f"{rel['por_origem']}")
        assert rel['tenants_sem_centro_administrativo'] == 0, (
            'há tenant sem centro administrativo — a migration 251 não '
            'cobriu todo mundo')
```

- [ ] **Step 2: Rode e confirme que falha**

```bash
python -m pytest tests/test_fase4_destino_custo.py -v -k "esta_validada or nao_sobrou"
```

Esperado: FAIL no primeiro — `convalidated` é `False`, porque a 253 criou como `NOT VALID`.

- [ ] **Step 3: Rode o gate de conformidade ANTES de escrever a migration**

```bash
python scripts/relatorio_destino_custo.py
```

Esperado: `✅ PRONTO — a migration 254 (VALIDATE) pode rodar.`
**Se aparecer `❌ NÃO VALIDE`, pare aqui.** Rode `python scripts/backfill_destino_custo.py --aplicar`, confira o CSV de detalhe, e só volte quando o relatório zerar. Escrever a 254 com pendências é o erro que esta fase inteira existe para não cometer.

- [ ] **Step 4: Escreva a migration 254**

Em `migrations.py`, antes de `def executar_migracoes():`, insira:

```python
def migration_254_validate_check_destino_custo():
    """Fase 4 — valida o CHECK de destino contra o histórico. ÚLTIMO PASSO.

    `VALIDATE CONSTRAINT` varre a tabela e recusa se houver qualquer linha
    violando a regra. Por isso ela é a última migração da fase, e por isso
    ela mesma faz a contagem antes de tentar: se houver pendência, loga a
    contagem e por origem e ABORTA sem tocar na constraint.

    Abortar é seguro. `run_migration_safe` grava status 'failed'
    (migrations.py:194) sem propagar a exceção (migrations.py:199), e
    `is_migration_executed` só considera aplicada a que terminou com
    'success' (migrations.py:83-86) — então ela é retentada em todo boot,
    até que o backfill limpe o histórico. Enquanto isso o CHECK continua
    em NOT VALID, ou seja, a escrita NOVA já está travada. Nada regride.
    """
    logger.info("[Migration 254] Iniciando — VALIDATE do CHECK de destino")

    existe = db.session.execute(text("""
        SELECT convalidated FROM pg_constraint
        WHERE conrelid = 'gestao_custo_filho'::regclass
          AND conname = 'ck_gestao_custo_filho_destino'
        LIMIT 1
    """)).fetchone()

    if not existe:
        raise RuntimeError(
            "[Migration 254] ck_gestao_custo_filho_destino não existe. "
            "A migration 253 tem de rodar antes.")

    if existe[0] is True:
        logger.info("[Migration 254] Constraint já validada — nada a fazer")
        return

    pendentes = db.session.execute(text("""
        SELECT count(*) FROM gestao_custo_filho
        WHERE obra_id IS NULL AND centro_custo_id IS NULL
    """)).scalar() or 0

    if pendentes:
        por_origem = db.session.execute(text("""
            SELECT COALESCE(origem_tabela, '(sem origem)'), count(*)
            FROM gestao_custo_filho
            WHERE obra_id IS NULL AND centro_custo_id IS NULL
            GROUP BY 1 ORDER BY 2 DESC LIMIT 20
        """)).fetchall()
        for origem, n in por_origem:
            logger.error("[Migration 254] pendente origem=%s n=%s", origem, n)
        raise RuntimeError(
            f"[Migration 254] {pendentes} lançamento(s) ainda sem destino. "
            "Rode `python scripts/backfill_destino_custo.py --aplicar` e "
            "reinicie. A escrita nova já está travada pelo CHECK NOT VALID "
            "da migration 253 — nada regride enquanto isso.")

    db.session.execute(text("""
        ALTER TABLE gestao_custo_filho
        VALIDATE CONSTRAINT ck_gestao_custo_filho_destino
    """))
    db.session.commit()

    total = db.session.execute(text(
        "SELECT count(*) FROM gestao_custo_filho")).scalar()
    com_obra = db.session.execute(text(
        "SELECT count(*) FROM gestao_custo_filho WHERE obra_id IS NOT NULL"
    )).scalar()
    logger.info(
        "[Migration 254] Concluída — %s linha(s) validada(s), %s com obra, "
        "%s no centro administrativo",
        total, com_obra, total - com_obra)
```

- [ ] **Step 5: Registre a migration**

Em `migrations.py`, em `migrations_to_run`, após a entrada `253`:

```python
            (254, "Fase 4 — VALIDATE do CHECK de destino (varre o histórico; aborta e retenta se houver pendência)", migration_254_validate_check_destino_custo),
```

- [ ] **Step 6: Aplique e rode os testes**

```bash
python -c "
from app import app
from migrations import executar_migracoes
with app.app_context():
    executar_migracoes()
" 2>&1 | grep -E "254|ERRO|ERROR|pendente"
python -m pytest tests/test_fase4_destino_custo.py tests/test_fase4_centro_custo.py -q
```

Esperado: `[Migration 254] Concluída — N linha(s) validada(s), ...` e todos os testes PASSAM.

- [ ] **Step 7: Rode o gate completo**

```bash
bash run_tests.sh --gate 2>&1 | tail -20
```

Esperado: a linha final do pytest sem `failed`. **Cole essa linha no documento de fecho da fase** — `DEVOLUTIVA.md` R5 registra que módulos anteriores se declararam verdes sem o gate completo, e a dívida de processo está aberta.

- [ ] **Step 8: Commit**

```bash
git add migrations.py tests/test_fase4_destino_custo.py
git commit -m "feat(fase4): VALIDATE do CHECK de destino — a trava fecha

Ultima migracao da fase. Varre gestao_custo_filho e valida o CHECK criado
NOT VALID pela 253. Aborta e retenta a cada boot se houver pendencia, sem
regressao: a escrita nova ja estava travada. A partir daqui e impossivel
salvar lancamento de custo sem obra e sem centro de custo."
```

---

## Autorrevisão

**1. Cobertura do escopo pedido**

| Item do escopo | Onde |
|---|---|
| Confirmar ausência de `obra_id` em `GestaoCustoPai` | Contexto verificado, tabela "O schema" — modelo (`models.py:5210-5290`) e `information_schema` |
| Contagem real das linhas órfãs | Contexto, tabela "Os números" — e o aviso explícito de que o banco é o de desenvolvimento, dominado por carga de suíte |
| `gestao_custos_views.py` + modelos | Tasks 8 e 10; anchors em `:113-127`, `:215`, `:275-283`, `:415-420`, `:462-478`, `:865-877`, `:965-1002` |
| `custos_views.py`, `custos_escritorio_views.py`, `contabilidade_utils.py`, `CentroCusto`, `centro_custo_contabil`, migration 46 | Contexto ("dois modelos de centro de custo"), `utils/centro_custo.py` docstring (`contabilidade_utils.py:164-173`, migration 46 é sobre `centro_custo_contabil.descricao`, `migrations.py:1913-1945` — outro eixo, fora do escopo, com o motivo escrito) |
| `obra_servico_custo` / `obra_servico_custo_item` (migrations 199, 205, 206) | Contexto: `models.py:5854` (`obra_id` NOT NULL), volumetria 41.761/176.872, e a nota de que o rateio obra→etapa de `resumo_custos_obra.py:191` continua legítimo |
| `Obra.percentual_administracao` e `Obra.regime_medicao` | Contexto (`models.py:285`, `:292`) e Decisão 8 |
| Lançamentos financeiros e obra (`FluxoCaixa`, `CategoriaFluxoCaixa`, `GrupoFinanceiro`) | Contexto (fluxo_caixa 15/14/0) e Task 8 passo 7 |
| `obra_id` onde falta | Task 3 |
| Regra de derivação decidida e implementada | Seção "A regra de derivação", Tasks 4-6 |
| Caminho para o que a regra não alcança | R5 + Decisão 2 |
| Obrigatoriedade como última tarefa, atrás de relatório | Tasks 11 → 12 → 13 |
| Faixa 250-259 | 250, 251, 252, 253, 254 |
| Fase 1 como pré-requisito | Task 10 (`obras_visiveis`) |

**2. Placeholders** — nenhum. Todo passo que muda código traz o código completo. As duas "Notas para quem executa" (nome da função em `event_manager.py`, endpoint do redirect em `compras_views.py`) são verificações de um identificador, não conteúdo faltando: o código está escrito e roda; só o alvo do `import`/`url_for` precisa de confirmação de uma linha de `grep`.

**3. Consistência de tipos e nomes** — conferido:
`centro_custo_administrativo(admin_id, criar=True)` e `id_do_centro_administrativo(admin_id, criar=True)` (`utils/centro_custo.py`, usados nas Tasks 6, 8, 9);
`obra_unanime(obra_ids)`, `classificar_pai(obra_ids) -> (situacao, obra_id)`, `sincronizar_obra_do_pai(pai)`, `destino_de_filho_novo(admin_id, obra_id, centro_custo_id, origem_tabela, tipo_categoria=None, criar_centro=True)`, `DestinoIndefinido`, `MARCA_FALLBACK`, `ORIGENS_COM_OBRA`, `ORIGENS_ADMINISTRATIVAS`, `CATEGORIAS_QUE_EXIGEM_OBRA` (`services/destino_custo.py`);
`diagnosticar(admin_id=None)`, `aplicar_pais(admin_id=None, lote=500)`, `aplicar_filhos(admin_id=None)`, `_regra_para_filho`, `_pais_e_obras` (`scripts/backfill_destino_custo.py`);
`conformidade(admin_id=None, limite_amostra=20)` (`scripts/relatorio_destino_custo.py`).
Nomes de regra idênticos entre `_regra_para_filho` e os testes: `R2_irmao_unanime`, `R3_origem`, `R4_natureza_origem`, `R5_fallback`.
Constraints citadas com o mesmo nome em migration, modelo e teste: `uq_centro_custo_admin_codigo`, `uq_centro_custo_administrativo`, `fk_gestao_custo_pai_obra_id`, `ix_gestao_custo_pai_obra_id`, `ck_gestao_custo_filho_destino`.

**4. Risco de primeira ordem** — a sequência exigida está respeitada e é verificável na ordem das tasks: coluna nullable (3) → dry-run revisável (4) → aplicação (5, 6) → portas fechadas (7, 8, 9) → relatório (11) → trava da escrita nova (12) → validação do histórico (13). A migration 254 recusa-se a validar com pendência e é retentada a cada boot, então nem uma execução fora de ordem consegue derrubar a escrita.
