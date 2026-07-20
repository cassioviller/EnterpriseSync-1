# Módulo 02 — Modelo de Dados e Migrations — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recomendado) ou superpowers:executing-plans, tarefa a tarefa. A spec de origem é `2026-07-17-modulo-02-modelo-dados-migrations.md` — as tabelas de colunas de lá (§4) são o dicionário de dados canônico; este plano as materializa em código.

**Goal:** Criar as 5 entidades de importação/versionamento de cronograma e as colunas de identidade estável/apontamento semântico — aditivo, idempotente, tenant-scoped, zero mudança de comportamento.

**Architecture:** Modelos passivos em `models.py` (nenhum event listener); DDL idempotente em `migrations.py` no padrão `ADD COLUMN IF NOT EXISTS`/`CREATE TABLE IF NOT EXISTS` com `db.engine.begin()` (estilo `_migration_199`+); backfill em migração separada, por lotes, re-executável.

**Tech Stack:** SQLAlchemy (declarative do projeto), PostgreSQL (índices parciais exigem PG — ok, projeto é Postgres-only).

---

## CORREÇÃO À SPEC: numeração das migrations

A spec §2/§7 diz "última migração: 199" e planeja 200-203. **Errado no repo atual**: as migrations 200-206 já existem (`_migration_200_osc_item_datas` ... `_migration_206_alimentacao_transporte_obra_servico_custo`). As migrations deste módulo são **207-210**:

- **207** — DDL das 5 tabelas novas
- **208** — colunas de identidade em `tarefa_cronograma`
- **209** — colunas semânticas em `rdo_apontamento_cronograma`
- **210** — backfill (versão nº1 + snapshots + `tipo_apontamento`)

## Fatos do repo que o executor precisa saber

- Registro: tupla `(numero, "descrição", _funcao)` na lista dentro de `executar_migracoes()` (`migrations.py:3773`; a lista atual termina perto de `migrations.py:4005`). Idempotência de execução via `migration_history` (`run_migration_safe`, `migrations.py:146`) — mas o DDL em si TAMBÉM deve ser idempotente (padrão do repo).
- Estilo de migração atual (copiar de `_migration_199_obra_servico_custo_item`, `migrations.py:13640`): `from sqlalchemy import text as sa_text` + `with db.engine.begin() as conn:` + `conn.execute(sa_text(...))` + `logger.info("[Migration NNN] ...")` + `except: logger.error(...); raise`.
- JSON: o projeto usa `db.Column(db.JSON)` (ex.: `models.py:255`), que no Postgres do projeto rende JSON — manter `db.JSON` nos modelos e `JSONB` no DDL é aceitável? **Não** — manter os dois lados iguais: usar `JSONB` no DDL e `db.JSON` no modelo é o que `fluxo_caixa_planilha` já faz? Verificado: `obra.fluxo_caixa_planilha` foi criada como JSON simples. Para as tabelas novas usar `JSONB` no DDL (spec §4 pede) e `db.Column(db.JSON)` no modelo — SQLAlchemy lê JSONB por essa coluna sem problema.
- Modelos novos entram em `models.py` logo após o bloco de cronograma existente (após `RDOApontamentoCronograma`), com comentários em português no estilo local (ver `TarefaCronograma`, `models.py:4858`).
- Testes de schema seguem o padrão de `test_medicao_contrato_schema_existe` (`tests/test_importacao_fisico_financeiro.py:27`): query em `information_schema.columns`.
- Rodar testes SEMPRE com pytest direto (`.pythonlibs/bin/python -u -m pytest ... -p no:cacheprovider`); `run_tests.sh` trava esperando servidor.

---

## Task 1: Teste de schema (vermelho)

**Files:**
- Create: `tests/test_migrations_cronograma_versionamento.py`

- [ ] **Step 1: Escrever o teste que falha**

```python
"""Módulo 02 — schema do versionamento de cronograma (migrations 207-210).

Cobre: existência de tabelas/colunas/índices, idempotência de reexecução
e backfill (versão nº1 + tipo_apontamento). Padrão de asserts de schema:
test_medicao_contrato_schema_existe (tests/test_importacao_fisico_financeiro.py).
"""
import pytest
from sqlalchemy import text

from app import app, db

TABELAS_NOVAS = [
    'cronograma_importacao',
    'cronograma_versao',
    'cronograma_tarefa_snapshot',
    'cronograma_tarefa_mapeamento',
    'cronograma_importacao_evento',
]

COLUNAS_TAREFA = ['mpp_uid', 'wbs_codigo', 'fingerprint', 'is_marco',
                  'ativa', 'arquivada_em', 'versao_criacao_id']

COLUNAS_APONTAMENTO = ['tipo_apontamento', 'percentual_acumulado',
                       'percentual_incremento_dia',
                       'quantidade_total_snapshot', 'unidade_snapshot']


def _tem_tabela(nome):
    with db.engine.connect() as conn:
        return conn.execute(text(
            "SELECT EXISTS (SELECT FROM information_schema.tables "
            "WHERE table_name = :t)"), {'t': nome}).scalar()


def _colunas(tabela):
    with db.engine.connect() as conn:
        rows = conn.execute(text(
            "SELECT column_name FROM information_schema.columns "
            "WHERE table_name = :t"), {'t': tabela}).fetchall()
    return {r[0] for r in rows}


def test_tabelas_novas_existem():
    with app.app_context():
        faltando = [t for t in TABELAS_NOVAS if not _tem_tabela(t)]
        assert not faltando, f'tabelas ausentes: {faltando}'


def test_colunas_novas_tarefa_cronograma():
    with app.app_context():
        cols = _colunas('tarefa_cronograma')
        faltando = [c for c in COLUNAS_TAREFA if c not in cols]
        assert not faltando, f'colunas ausentes em tarefa_cronograma: {faltando}'


def test_colunas_novas_rdo_apontamento():
    with app.app_context():
        cols = _colunas('rdo_apontamento_cronograma')
        faltando = [c for c in COLUNAS_APONTAMENTO if c not in cols]
        assert not faltando, f'colunas ausentes em rdo_apontamento_cronograma: {faltando}'


def test_unique_uma_versao_ativa_por_obra():
    """Índice parcial: no máximo 1 cronograma_versao ativa por obra."""
    with app.app_context():
        with db.engine.connect() as conn:
            idx = conn.execute(text(
                "SELECT indexdef FROM pg_indexes "
                "WHERE tablename = 'cronograma_versao' "
                "AND indexdef ILIKE '%%status%%ativa%%'")).fetchall()
        assert idx, 'índice parcial WHERE status=ativa não existe'
```

- [ ] **Step 2: Rodar e verificar que falha**

Run: `.pythonlibs/bin/python -u -m pytest tests/test_migrations_cronograma_versionamento.py -p no:cacheprovider -q`
Expected: 4 FAILED (tabelas/colunas ausentes).

- [ ] **Step 3: Commit**

```bash
git add tests/test_migrations_cronograma_versionamento.py
git commit -m "test(cronograma): schema do versionamento (M02, vermelho)"
```

---

## Task 2: Modelos em `models.py`

**Files:**
- Modify: `models.py` (inserir após `RDOApontamentoCronograma`, ~linha 4990) — 5 classes novas
- Modify: `models.py` — colunas novas em `TarefaCronograma` e `RDOApontamentoCronograma`

- [ ] **Step 1: Adicionar as 5 classes**

Seguir EXATAMENTE o dicionário da spec §4 (tipos, FKs, ondelete, nullable). Esqueleto com as decisões não óbvias resolvidas:

```python
# ─────────────────────────────────────────────────────────────────────────────
# MÓDULO 02 (plano cronograma-mpp): importação e versionamento de cronograma
# Migrations 207-210. Modelos PASSIVOS (regra §9 da spec: nenhuma lógica em
# event listeners; snapshots são preenchidos explicitamente pelos serviços M5).
# ─────────────────────────────────────────────────────────────────────────────
class CronogramaImportacao(db.Model):
    """Um upload de cronograma (.xml MSPDI ou .mpp) e seu pipeline de estados:
    recebido → parseado → normalizado → reconciliado → aguardando_revisao →
    aplicado | falhou | cancelado."""
    __tablename__ = 'cronograma_importacao'

    id = db.Column(db.Integer, primary_key=True)
    obra_id = db.Column(db.Integer, db.ForeignKey('obra.id', ondelete='CASCADE'),
                        nullable=False, index=True)
    admin_id = db.Column(db.Integer, db.ForeignKey('usuario.id'),
                         nullable=False, index=True)
    arquivo_nome = db.Column(db.String(255))
    arquivo_tamanho = db.Column(db.Integer)
    arquivo_sha256 = db.Column(db.String(64), index=True)
    arquivo_path = db.Column(db.String(512), nullable=True)
    origem = db.Column(db.String(20))          # 'upload_mpp' | 'upload_mspdi' | 'json_cli'
    parser_nome = db.Column(db.String(50))     # 'mspdi_stdlib' | 'mpxj'
    parser_versao = db.Column(db.String(20))
    normalizador_versao = db.Column(db.String(20))
    status = db.Column(db.String(30), nullable=False, default='recebido')
    json_bruto = db.Column(db.JSON, nullable=True)
    json_normalizado = db.Column(db.JSON, nullable=True)
    relatorio_diff = db.Column(db.JSON, nullable=True)
    erro = db.Column(db.Text, nullable=True)
    criado_por_id = db.Column(db.Integer, db.ForeignKey('usuario.id'), nullable=True)
    criado_em = db.Column(db.DateTime, default=datetime.utcnow)
    aplicado_em = db.Column(db.DateTime, nullable=True)
```

As outras 4 classes seguem o mesmo estilo, com o dicionário da spec §4:
- `CronogramaVersao` — incluir `db.UniqueConstraint('obra_id', 'numero', name='uq_cronograma_versao_obra_numero')` em `__table_args__`. O unique parcial 1-ativa-por-obra fica SÓ no DDL (SQLAlchemy declarativo não expressa índice parcial de forma portável — comentar isso no modelo).
- `CronogramaTarefaSnapshot` — `tarefa_id` FK `tarefa_cronograma.id` ondelete SET NULL; `predecessoras_json = db.Column(db.JSON)`; `payload_extra = db.Column(db.JSON)`.
- `CronogramaTarefaMapeamento` — `tipo` String(40); `score` Float; `detalhes` JSON.
- `CronogramaImportacaoEvento` — `evento` String(50); `detalhes` JSON; `criado_em` DateTime default utcnow.

Nota sobre a spec (origem/parser): a spec §4 previa `origem='upload_mpp'|'json_cli'` e `parser_nome='mpxj'`. O adendo do M03 (`2026-07-20-modulo-03-adendo-parser-mspdi-sem-jvm.md`) tornou o MSPDI XML o caminho primário — os comentários acima já refletem isso; os valores são livres (String), nenhuma constraint fixa os literais.

- [ ] **Step 2: Adicionar colunas aos modelos existentes**

Em `TarefaCronograma` (antes de `created_at`):

```python
    # ── Módulo 02 (cronograma-mpp), Migration 208: identidade estável ──
    # UID do MS Project (getUniqueID / <UID> do MSPDI) — chave de reconciliação
    mpp_uid = db.Column(db.BigInteger, nullable=True)
    wbs_codigo = db.Column(db.String(50), nullable=True)
    # Fingerprint determinístico do conteúdo (Módulo 4)
    fingerprint = db.Column(db.String(64), nullable=True)
    is_marco = db.Column(db.Boolean, nullable=False, default=False, server_default='false')
    # Arquivamento lógico: tarefa removida em versão nova NUNCA é deletada
    ativa = db.Column(db.Boolean, nullable=False, default=True, server_default='true')
    arquivada_em = db.Column(db.DateTime, nullable=True)
    versao_criacao_id = db.Column(db.Integer,
                                  db.ForeignKey('cronograma_versao.id', ondelete='SET NULL'),
                                  nullable=True)
```

Em `RDOApontamentoCronograma` (ao final das colunas):

```python
    # ── Módulo 02 (cronograma-mpp), Migration 209: semântica explícita ──
    # 'quantitativo' (valor do dia em unidades) | 'percentual' (acumulado %).
    # Hoje o modo é implícito por quantidade_total>0; os campos antigos NÃO
    # mudam de significado (leitura legada intacta) — ver spec §13.2.
    tipo_apontamento = db.Column(db.String(15), nullable=True)
    percentual_acumulado = db.Column(db.Float, nullable=True)
    percentual_incremento_dia = db.Column(db.Float, nullable=True)
    quantidade_total_snapshot = db.Column(db.Float, nullable=True)
    unidade_snapshot = db.Column(db.String(20), nullable=True)
```

- [ ] **Step 3: Sanidade de importação**

Run: `.pythonlibs/bin/python -c "import models; print('models OK')"`
Expected: `models OK` (nenhum conflito de mapper).

- [ ] **Step 4: Commit**

```bash
git add models.py
git commit -m "feat(cronograma): modelos de importacao/versionamento (M02)"
```

---

## Task 3: Migration 207 — DDL das 5 tabelas

**Files:**
- Modify: `migrations.py` (função ao final do arquivo + registro na lista de `executar_migracoes()`)

- [ ] **Step 1: Escrever `_migration_207_cronograma_versionamento`**

Estilo `_migration_199` (`db.engine.begin()` + `sa_text`). DDL completo — atenção aos pontos que o `CREATE TABLE IF NOT EXISTS` sozinho não cobre:

```python
def _migration_207_cronograma_versionamento():
    """Módulo 02 (cronograma-mpp) — 5 tabelas de importação/versionamento.
    Aditivo e idempotente. Dicionário: docs/superpowers/plans/
    2026-07-17-modulo-02-modelo-dados-migrations.md §4."""
    from sqlalchemy import text as sa_text
    try:
        with db.engine.begin() as conn:
            conn.execute(sa_text("""
                CREATE TABLE IF NOT EXISTS cronograma_importacao (
                    id SERIAL PRIMARY KEY,
                    obra_id INTEGER NOT NULL REFERENCES obra(id) ON DELETE CASCADE,
                    admin_id INTEGER NOT NULL REFERENCES usuario(id),
                    arquivo_nome VARCHAR(255),
                    arquivo_tamanho INTEGER,
                    arquivo_sha256 VARCHAR(64),
                    arquivo_path VARCHAR(512),
                    origem VARCHAR(20),
                    parser_nome VARCHAR(50),
                    parser_versao VARCHAR(20),
                    normalizador_versao VARCHAR(20),
                    status VARCHAR(30) NOT NULL DEFAULT 'recebido',
                    json_bruto JSONB,
                    json_normalizado JSONB,
                    relatorio_diff JSONB,
                    erro TEXT,
                    criado_por_id INTEGER REFERENCES usuario(id),
                    criado_em TIMESTAMP DEFAULT NOW(),
                    aplicado_em TIMESTAMP
                )
            """))
            conn.execute(sa_text(
                "CREATE INDEX IF NOT EXISTS ix_cron_imp_obra ON cronograma_importacao(obra_id)"))
            conn.execute(sa_text(
                "CREATE INDEX IF NOT EXISTS ix_cron_imp_admin ON cronograma_importacao(admin_id)"))
            conn.execute(sa_text(
                "CREATE INDEX IF NOT EXISTS ix_cron_imp_sha ON cronograma_importacao(arquivo_sha256)"))
            # Dedup por conteúdo na MESMA obra, exceto tentativas falhas/canceladas
            conn.execute(sa_text("""
                CREATE UNIQUE INDEX IF NOT EXISTS uq_cron_imp_obra_sha
                ON cronograma_importacao(obra_id, arquivo_sha256)
                WHERE status NOT IN ('falhou', 'cancelado')
            """))

            conn.execute(sa_text("""
                CREATE TABLE IF NOT EXISTS cronograma_versao (
                    id SERIAL PRIMARY KEY,
                    obra_id INTEGER NOT NULL REFERENCES obra(id) ON DELETE CASCADE,
                    admin_id INTEGER NOT NULL REFERENCES usuario(id),
                    numero INTEGER NOT NULL,
                    status VARCHAR(20) NOT NULL DEFAULT 'ativa',
                    importacao_id INTEGER REFERENCES cronograma_importacao(id),
                    aplicada_em TIMESTAMP DEFAULT NOW(),
                    aplicada_por_id INTEGER REFERENCES usuario(id),
                    observacao TEXT,
                    CONSTRAINT uq_cronograma_versao_obra_numero UNIQUE (obra_id, numero)
                )
            """))
            conn.execute(sa_text(
                "CREATE INDEX IF NOT EXISTS ix_cron_versao_obra ON cronograma_versao(obra_id)"))
            conn.execute(sa_text(
                "CREATE INDEX IF NOT EXISTS ix_cron_versao_admin ON cronograma_versao(admin_id)"))
            # Uma e somente uma versão ATIVA por obra (spec §12)
            conn.execute(sa_text("""
                CREATE UNIQUE INDEX IF NOT EXISTS uq_cron_versao_uma_ativa
                ON cronograma_versao(obra_id) WHERE status = 'ativa'
            """))

            conn.execute(sa_text("""
                CREATE TABLE IF NOT EXISTS cronograma_tarefa_snapshot (
                    id SERIAL PRIMARY KEY,
                    versao_id INTEGER NOT NULL REFERENCES cronograma_versao(id) ON DELETE CASCADE,
                    admin_id INTEGER NOT NULL REFERENCES usuario(id),
                    tarefa_id INTEGER REFERENCES tarefa_cronograma(id) ON DELETE SET NULL,
                    mpp_uid BIGINT,
                    wbs_codigo VARCHAR(50),
                    nome_tarefa VARCHAR(200),
                    tarefa_pai_snapshot_id INTEGER REFERENCES cronograma_tarefa_snapshot(id),
                    predecessoras_json JSONB,
                    ordem INTEGER,
                    data_inicio DATE,
                    data_fim DATE,
                    duracao_dias INTEGER,
                    quantidade_total FLOAT,
                    unidade_medida VARCHAR(20),
                    is_marco BOOLEAN DEFAULT FALSE,
                    is_resumo BOOLEAN DEFAULT FALSE,
                    percentual_concluido_no_momento FLOAT,
                    payload_extra JSONB
                )
            """))
            conn.execute(sa_text(
                "CREATE INDEX IF NOT EXISTS ix_cron_snap_versao ON cronograma_tarefa_snapshot(versao_id)"))

            conn.execute(sa_text("""
                CREATE TABLE IF NOT EXISTS cronograma_tarefa_mapeamento (
                    id SERIAL PRIMARY KEY,
                    importacao_id INTEGER NOT NULL REFERENCES cronograma_importacao(id) ON DELETE CASCADE,
                    admin_id INTEGER NOT NULL REFERENCES usuario(id),
                    tarefa_atual_id INTEGER REFERENCES tarefa_cronograma(id) ON DELETE SET NULL,
                    chave_nova VARCHAR(120),
                    tipo VARCHAR(40) NOT NULL,
                    score FLOAT,
                    origem_decisao VARCHAR(20),
                    decidido_por_id INTEGER REFERENCES usuario(id),
                    detalhes JSONB
                )
            """))
            conn.execute(sa_text(
                "CREATE INDEX IF NOT EXISTS ix_cron_map_importacao ON cronograma_tarefa_mapeamento(importacao_id)"))

            conn.execute(sa_text("""
                CREATE TABLE IF NOT EXISTS cronograma_importacao_evento (
                    id SERIAL PRIMARY KEY,
                    importacao_id INTEGER NOT NULL REFERENCES cronograma_importacao(id) ON DELETE CASCADE,
                    admin_id INTEGER NOT NULL REFERENCES usuario(id),
                    evento VARCHAR(50) NOT NULL,
                    detalhes JSONB,
                    usuario_id INTEGER REFERENCES usuario(id),
                    criado_em TIMESTAMP DEFAULT NOW()
                )
            """))
            conn.execute(sa_text(
                "CREATE INDEX IF NOT EXISTS ix_cron_evt_importacao ON cronograma_importacao_evento(importacao_id)"))
        logger.info("[Migration 207] tabelas de versionamento de cronograma criadas.")
    except Exception as e:
        logger.error(f"[Migration 207] Falha: {e}", exc_info=True)
        raise
```

- [ ] **Step 2: Registrar na lista** de `executar_migracoes()` após a entrada 206:

```python
            (207, "Cronograma-mpp M02 — tabelas de importação/versionamento (importacao, versao, snapshot, mapeamento, evento)", _migration_207_cronograma_versionamento),
```

- [ ] **Step 3: Aplicar e testar**

Run: `.pythonlibs/bin/python -c "from app import app; from migrations import executar_migracoes; app.app_context().push(); executar_migracoes()"`
Depois: `.pythonlibs/bin/python -u -m pytest tests/test_migrations_cronograma_versionamento.py::test_tabelas_novas_existem tests/test_migrations_cronograma_versionamento.py::test_unique_uma_versao_ativa_por_obra -p no:cacheprovider -q`
Expected: `2 passed`.

- [ ] **Step 4: Commit**

```bash
git add migrations.py
git commit -m "feat(cronograma): migration 207 — tabelas de versionamento"
```

---

## Task 4: Migrations 208 e 209 — colunas aditivas

**Files:**
- Modify: `migrations.py`

- [ ] **Step 1: Escrever as duas funções**

```python
def _migration_208_tarefa_cronograma_identidade():
    """Módulo 02 — identidade estável em tarefa_cronograma (uid/wbs/fingerprint,
    marco, arquivamento lógico, versão de criação). Aditivo e idempotente."""
    from sqlalchemy import text as sa_text
    try:
        with db.engine.begin() as conn:
            conn.execute(sa_text("ALTER TABLE tarefa_cronograma ADD COLUMN IF NOT EXISTS mpp_uid BIGINT"))
            conn.execute(sa_text("ALTER TABLE tarefa_cronograma ADD COLUMN IF NOT EXISTS wbs_codigo VARCHAR(50)"))
            conn.execute(sa_text("ALTER TABLE tarefa_cronograma ADD COLUMN IF NOT EXISTS fingerprint VARCHAR(64)"))
            conn.execute(sa_text("ALTER TABLE tarefa_cronograma ADD COLUMN IF NOT EXISTS is_marco BOOLEAN NOT NULL DEFAULT FALSE"))
            conn.execute(sa_text("ALTER TABLE tarefa_cronograma ADD COLUMN IF NOT EXISTS ativa BOOLEAN NOT NULL DEFAULT TRUE"))
            conn.execute(sa_text("ALTER TABLE tarefa_cronograma ADD COLUMN IF NOT EXISTS arquivada_em TIMESTAMP"))
            conn.execute(sa_text(
                "ALTER TABLE tarefa_cronograma ADD COLUMN IF NOT EXISTS versao_criacao_id "
                "INTEGER REFERENCES cronograma_versao(id) ON DELETE SET NULL"))
            conn.execute(sa_text(
                "CREATE INDEX IF NOT EXISTS ix_tarefa_cron_obra_uid ON tarefa_cronograma(obra_id, mpp_uid)"))
            conn.execute(sa_text(
                "CREATE INDEX IF NOT EXISTS ix_tarefa_cron_ativa ON tarefa_cronograma(obra_id) WHERE ativa"))
        logger.info("[Migration 208] identidade estável em tarefa_cronograma.")
    except Exception as e:
        logger.error(f"[Migration 208] Falha: {e}", exc_info=True)
        raise


def _migration_209_rdo_apontamento_semantico():
    """Módulo 02 — semântica explícita do apontamento (tipo, percentuais
    próprios, snapshot de quantidade/unidade). Campos antigos INTACTOS."""
    from sqlalchemy import text as sa_text
    try:
        with db.engine.begin() as conn:
            conn.execute(sa_text("ALTER TABLE rdo_apontamento_cronograma ADD COLUMN IF NOT EXISTS tipo_apontamento VARCHAR(15)"))
            conn.execute(sa_text("ALTER TABLE rdo_apontamento_cronograma ADD COLUMN IF NOT EXISTS percentual_acumulado FLOAT"))
            conn.execute(sa_text("ALTER TABLE rdo_apontamento_cronograma ADD COLUMN IF NOT EXISTS percentual_incremento_dia FLOAT"))
            conn.execute(sa_text("ALTER TABLE rdo_apontamento_cronograma ADD COLUMN IF NOT EXISTS quantidade_total_snapshot FLOAT"))
            conn.execute(sa_text("ALTER TABLE rdo_apontamento_cronograma ADD COLUMN IF NOT EXISTS unidade_snapshot VARCHAR(20)"))
        logger.info("[Migration 209] colunas semânticas em rdo_apontamento_cronograma.")
    except Exception as e:
        logger.error(f"[Migration 209] Falha: {e}", exc_info=True)
        raise
```

- [ ] **Step 2: Registrar** (após a 207):

```python
            (208, "Cronograma-mpp M02 — identidade estável em tarefa_cronograma (mpp_uid/wbs/fingerprint/is_marco/ativa)", _migration_208_tarefa_cronograma_identidade),
            (209, "Cronograma-mpp M02 — semântica de apontamento em rdo_apontamento_cronograma (tipo/percentuais/snapshot)", _migration_209_rdo_apontamento_semantico),
```

- [ ] **Step 3: Aplicar e testar**

Run: mesma linha de `executar_migracoes()` da Task 3, depois
`.pythonlibs/bin/python -u -m pytest tests/test_migrations_cronograma_versionamento.py -p no:cacheprovider -q`
Expected: `4 passed`.

- [ ] **Step 4: Commit**

```bash
git add migrations.py
git commit -m "feat(cronograma): migrations 208-209 — colunas de identidade e semantica"
```

---

## Task 5: Teste de idempotência

**Files:**
- Modify: `tests/test_migrations_cronograma_versionamento.py`

- [ ] **Step 1: Acrescentar**

```python
def test_reexecucao_das_migracoes_e_noop():
    """run_migration_safe pula por migration_history; e o DDL em si é
    idempotente (IF NOT EXISTS) — as funções podem rodar de novo sem erro."""
    from migrations import (_migration_207_cronograma_versionamento,
                            _migration_208_tarefa_cronograma_identidade,
                            _migration_209_rdo_apontamento_semantico)
    with app.app_context():
        _migration_207_cronograma_versionamento()
        _migration_208_tarefa_cronograma_identidade()
        _migration_209_rdo_apontamento_semantico()
```

- [ ] **Step 2: Rodar** — Expected: `5 passed`.

- [ ] **Step 3: Commit**

```bash
git add tests/test_migrations_cronograma_versionamento.py
git commit -m "test(cronograma): idempotencia do DDL do M02"
```

---

## Task 6: Migration 210 — backfill

**Files:**
- Modify: `migrations.py`
- Modify: `tests/test_migrations_cronograma_versionamento.py`

- [ ] **Step 1: Teste do backfill primeiro (vermelho)**

Fixture: importar as baias no banco de teste (padrão dos testes de importação — `importar_fisico_financeiro(payload, admin_id)` com a fixture `tests/fixtures/cronograma_fisico_financeiro_baias.json`), limpar `tipo_apontamento` e versões (simular estado pré-210), rodar `_migration_210_backfill_versao_inicial()`, conferir:

```python
def test_backfill_cria_versao_1_e_snapshots(ambiente_baias):
    """Obra com tarefas ganha versão nº1 ativa e 1 snapshot por tarefa."""
    from migrations import _migration_210_backfill_versao_inicial
    from models import CronogramaVersao, CronogramaTarefaSnapshot, TarefaCronograma
    with app.app_context():
        _migration_210_backfill_versao_inicial()
        obra_id = ambiente_baias['obra_id']
        admin_id = ambiente_baias['admin_id']
        v = CronogramaVersao.query.filter_by(obra_id=obra_id, status='ativa').one()
        assert v.numero == 1
        assert v.observacao == 'backfill inicial'
        n_tarefas = TarefaCronograma.query.filter_by(obra_id=obra_id, admin_id=admin_id).count()
        n_snaps = CronogramaTarefaSnapshot.query.filter_by(versao_id=v.id).count()
        assert n_snaps == n_tarefas


def test_backfill_tipo_apontamento(ambiente_baias):
    """quantidade_total>0 → 'quantitativo'; senão 'percentual' com
    percentual_acumulado=percentual_realizado e incremento=quantidade_executada_dia
    (que no modo percentual guarda o incremento % — importacao_fisico_financeiro:521-532)."""
    from models import RDOApontamentoCronograma, TarefaCronograma
    with app.app_context():
        aps = (RDOApontamentoCronograma.query
               .join(TarefaCronograma,
                     TarefaCronograma.id == RDOApontamentoCronograma.tarefa_cronograma_id)
               .filter(RDOApontamentoCronograma.admin_id == ambiente_baias['admin_id'])
               .all())
        assert aps, 'fixture sem apontamentos'
        for ap in aps:
            t = ap.tarefa  # ou query pela FK, conforme relationship disponível
            if t.quantidade_total and t.quantidade_total > 0:
                assert ap.tipo_apontamento == 'quantitativo'
                assert ap.quantidade_total_snapshot == t.quantidade_total
            else:
                assert ap.tipo_apontamento == 'percentual'
                assert ap.percentual_acumulado == ap.percentual_realizado
                assert ap.percentual_incremento_dia == ap.quantidade_executada_dia


def test_backfill_reexecucao_noop(ambiente_baias):
    """Rodar de novo não duplica versão nem snapshots."""
    from migrations import _migration_210_backfill_versao_inicial
    from models import CronogramaVersao
    with app.app_context():
        _migration_210_backfill_versao_inicial()
        _migration_210_backfill_versao_inicial()
        n = CronogramaVersao.query.filter_by(obra_id=ambiente_baias['obra_id']).count()
        assert n == 1
```

(O executor escreve a fixture `ambiente_baias` no padrão dos módulos de teste existentes: admin novo + `importar_fisico_financeiro` + retorno de ids. Multitenant: criar um segundo admin sem tarefas e assertar que nada foi criado para ele.)

- [ ] **Step 2: Implementar `_migration_210_backfill_versao_inicial`**

Regras (spec §13): loop por obra com tarefas; pular obra que já tem versão nº1; commit por obra (lotes); `tipo_apontamento` só onde `IS NULL`. Backfill dos apontamentos por UPDATE SQL direto (mais rápido e sem carregar ORM):

```python
def _migration_210_backfill_versao_inicial():
    """Módulo 02 — backfill: versão nº1 ativa + snapshots por obra com tarefas;
    tipo_apontamento nos apontamentos existentes. Idempotente (pula o que já
    tem); commit por obra para caber no timeout de startup."""
    from sqlalchemy import text as sa_text
    try:
        with db.engine.connect() as conn:
            obras = conn.execute(sa_text("""
                SELECT DISTINCT t.obra_id, t.admin_id FROM tarefa_cronograma t
                WHERE NOT EXISTS (
                    SELECT 1 FROM cronograma_versao v WHERE v.obra_id = t.obra_id
                )
            """)).fetchall()
        for obra_id, admin_id in obras:
            with db.engine.begin() as conn:
                versao_id = conn.execute(sa_text("""
                    INSERT INTO cronograma_versao (obra_id, admin_id, numero, status, observacao)
                    VALUES (:o, :a, 1, 'ativa', 'backfill inicial') RETURNING id
                """), {'o': obra_id, 'a': admin_id}).scalar()
                conn.execute(sa_text("""
                    INSERT INTO cronograma_tarefa_snapshot
                        (versao_id, admin_id, tarefa_id, nome_tarefa, ordem,
                         data_inicio, data_fim, duracao_dias, quantidade_total,
                         unidade_medida, percentual_concluido_no_momento)
                    SELECT :v, t.admin_id, t.id, t.nome_tarefa, t.ordem,
                           t.data_inicio, t.data_fim, t.duracao_dias, t.quantidade_total,
                           t.unidade_medida, t.percentual_concluido
                    FROM tarefa_cronograma t WHERE t.obra_id = :o
                """), {'v': versao_id, 'o': obra_id})
            logger.info(f"[Migration 210] obra {obra_id}: versão 1 + snapshots.")
        with db.engine.begin() as conn:
            conn.execute(sa_text("""
                UPDATE rdo_apontamento_cronograma ap SET
                    tipo_apontamento = CASE
                        WHEN t.quantidade_total > 0 THEN 'quantitativo' ELSE 'percentual' END,
                    quantidade_total_snapshot = t.quantidade_total,
                    unidade_snapshot = t.unidade_medida,
                    percentual_acumulado = CASE
                        WHEN t.quantidade_total > 0 THEN NULL ELSE ap.percentual_realizado END,
                    percentual_incremento_dia = CASE
                        WHEN t.quantidade_total > 0 THEN NULL ELSE ap.quantidade_executada_dia END
                FROM tarefa_cronograma t
                WHERE t.id = ap.tarefa_cronograma_id
                  AND ap.tipo_apontamento IS NULL
            """))
        logger.info("[Migration 210] backfill concluído.")
    except Exception as e:
        logger.error(f"[Migration 210] Falha: {e}", exc_info=True)
        raise
```

- [ ] **Step 3: Registrar** `(210, "Cronograma-mpp M02 — backfill versão nº1 + snapshots + tipo_apontamento", _migration_210_backfill_versao_inicial)`.

- [ ] **Step 4: Rodar o arquivo inteiro** — Expected: todos os testes do arquivo verdes.

- [ ] **Step 5: Commit**

```bash
git add migrations.py tests/test_migrations_cronograma_versionamento.py
git commit -m "feat(cronograma): migration 210 — backfill de versao inicial"
```

---

## Task 7: Verificação de regressão

- [ ] **Step 1: Conjunto que toca cronograma/RDO/importação**

Run: `.pythonlibs/bin/python -u -m pytest tests/test_importacao_fisico_financeiro.py tests/test_caracterizacao_apontamento_cronograma.py tests/test_cronograma_apontamento_service.py tests/test_migrations_cronograma_versionamento.py -p no:cacheprovider --tb=short -q`
Expected: tudo verde.

- [ ] **Step 2: Gate completo** (longo, ~38min — rodar em background)

Run: `.pythonlibs/bin/python -u -m pytest tests/ -m "not browser" -p no:cacheprovider --tb=short -q`
Expected: mesmo resultado do fecho do M01 (437 passed + os novos), 0 falhas.

- [ ] **Step 3: Fechar o checklist §22 da spec do M02** (com as ressalvas de numeração 207-210) e commit.

---

## Critérios de aceite

1. Migrations 207-210 aplicam no banco de teste com dados das baias sem erro.
2. Reexecução = no-op (provado por teste, não por leitura).
3. Zero mudança de comportamento (gate igual ao fecho do M01).
4. Campos antigos de `rdo_apontamento_cronograma` byte a byte intactos após o backfill.

## Riscos

| Risco | Mitigação |
|---|---|
| Spec desatualizada em outros pontos além da numeração | Task 1 valida contra o banco real, não contra a spec |
| `db.JSON` do SQLAlchemy vs JSONB do DDL divergirem em roundtrip | Testes do backfill leem o que o SQL gravou |
| Backfill lento em produção | Commit por obra; a migração roda no startup com timeout 300s |
| Conflito de mapper pelas FKs novas (`versao_criacao_id`) | Task 2 Step 3 importa `models` antes de qualquer migração |
