# Lançamento da etapa com Categoria de Fluxo de Caixa (Pedaço 2) — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** O "+ Novo lançamento" da etapa (Pedaço 1) ganha um campo **Categoria** vindo do catálogo `CategoriaFluxoCaixa`; o lançamento passa a gravar `GestaoCustoPai.categoria_fluxo_caixa_id` (nova coluna) e o relatório de Fluxo de Caixa exibe o nome dessa categoria.

**Architecture:** Adiciona `categoria_fluxo_caixa_id` (FK nullable) ao `GestaoCustoPai` (migração 204). `registrar_custo_automatico` passa a aceitar e gravar essa categoria — e a inclui na chave de busca do Pai em aberto, senão lançamentos de categorias diferentes (todos `tipo_categoria='OUTROS'`/entidade "Lançamento manual") se fundiriam num só Pai. As rotas `.../lancamentos` do Pedaço 1 são estendidas: o `POST` aceita `categoria_fluxo_caixa_id` (com fallback "Outras Saídas"), o `GET` devolve a lista de categorias agrupada e o rótulo por lançamento. O relatório de Fluxo de Caixa (`financeiro_service.py`) troca o rótulo `[tipo_categoria]` pelo nome da `CategoriaFluxoCaixa` quando presente. Front em `financeiro_obra.js` ganha o dropdown agrupado e um badge.

**Tech Stack:** Flask + SQLAlchemy (Postgres), migrações idempotentes em `migrations.py`, front vanilla JS + Bootstrap 5, testes `pytest`. Verificação visual via Playwright + chromium do Nix (`REPLIT_PLAYWRIGHT_CHROMIUM_EXECUTABLE`).

## Global Constraints

- **Obra-piloto:** Baia. **Previsto inalterado:** veks 800.960 / fat 550.775 / lucro 24.976 / imposto 128.903 / contrato 1.505.613,76 / data_fim 08/10. O **Realizado** continua vindo só de `GestaoCustoFilho` ligados às etapas (Pedaço 1); a coluna nova é metadado de categoria no Pai, não altera somatórios.
- **`tipo_categoria` permanece** (`NOT NULL`) e continua `'OUTROS'` no lançamento manual; a categoria real do lançamento é a `categoria_fluxo_caixa_id`. Não substituir `tipo_categoria` no resto do sistema (fora de escopo).
- **Categoria nunca derruba o POST:** ausente/inválida → cai na `CategoriaFluxoCaixa` de `nome='Outras Saídas'`/`tipo='SAIDA'` do tenant; se o catálogo não estiver semeado, grava `categoria_fluxo_caixa_id=None`.
- **Migração 204:** número livre confirmado (a 203 é `drop valor_realizado`). Idempotente, padrão do repo: `ADD COLUMN IF NOT EXISTS`.
- **Helper de criação:** `registrar_custo_automatico(admin_id, tipo_categoria, entidade_nome, entidade_id, data, descricao, valor, obra_id=, centro_custo_id=, origem_tabela=, origem_id=, obra_servico_custo_id=, categoria_fluxo_caixa_id=, force_v2=False)` retorna o `GestaoCustoFilho` criado (ou `None`); faz flush sem commit.
- **Seed do catálogo nos testes:** `CategoriaFluxoCaixa.seed_defaults(admin_id)` insere as 45 categorias padrão (inclui "Materiais de Obra", "Mão de Obra Direta", "Outras Saídas"). `_novo_admin()` NÃO semeia — chamar explicitamente no teste.
- Suíte de regressão (rodar após cada task):
  ```
  python -m pytest tests/test_cronograma_fisico_financeiro.py tests/test_painel_financeiro.py tests/test_importacao_fisico_financeiro.py -q
  ```

---

## File Structure

| Arquivo | Responsabilidade | Mudança |
|---|---|---|
| `models.py` (`GestaoCustoPai`, ~l.5004/5028) | ORM do Contas a Pagar | **Modificar** — `categoria_fluxo_caixa_id` + relationship |
| `migrations.py` (registry ~l.4003; defs ~l.13726) | Schema | **Modificar** — `_migration_204_gestao_custo_pai_categoria_fc` |
| `utils/financeiro_integration.py` (`registrar_custo_automatico`, l.59-207) | Criação do custo | **Modificar** — parâmetro `categoria_fluxo_caixa_id` (grava + chave do Pai) |
| `services/cronograma_fisico_financeiro.py` (após `lancamentos_da_etapa`, l.600-622) | Serviço da etapa | **Modificar** — `categoria_id`/`categoria_label` em `lancamentos_da_etapa`; novos `categorias_fluxo_caixa_saida`, `resolver_categoria_fluxo_caixa` |
| `views/obras.py` (`financeiro_etapa_lancamentos` l.2203; `financeiro_etapa_lancamento_criar` l.2215) | Endpoints | **Modificar** — GET expõe `categorias`; POST aceita `categoria_fluxo_caixa_id` |
| `financeiro_service.py` (`calcular_fluxo_caixa`, l.572 e l.601) | Relatório de Fluxo de Caixa | **Modificar** — rótulo usa nome da CFC |
| `static/js/financeiro_obra.js` (`carregarRealizado` l.154; `renderRealizado` l.163; `lancamentoForm` l.207) | UI viva | **Modificar** — dropdown de categoria + badge |
| `tests/test_painel_financeiro.py` | Testes | **Modificar** — novos testes |

---

## Task 1: Modelo + migração 204 (`gestao_custo_pai.categoria_fluxo_caixa_id`)

**Files:**
- Modify: `models.py` (`GestaoCustoPai`, ~l.5004 e ~l.5028)
- Modify: `migrations.py` (registry ~l.4003; nova função ~l.13726)
- Test: `tests/test_painel_financeiro.py`

**Interfaces:**
- Produces: `GestaoCustoPai.categoria_fluxo_caixa_id` (Integer FK nullable → `categoria_fluxo_caixa.id`) e o relationship `GestaoCustoPai.categoria_fluxo_caixa` (→ `CategoriaFluxoCaixa`).

- [ ] **Step 1: Write the failing test**

Adicionar a `tests/test_painel_financeiro.py`:

```python
@pytest.mark.integration
def test_gestao_custo_pai_tem_categoria_fluxo_caixa():
    from models import GestaoCustoPai
    cols = {c.name for c in GestaoCustoPai.__table__.columns}
    assert 'categoria_fluxo_caixa_id' in cols
```

- [ ] **Step 2: Run it — expect FAIL**

Run: `python -m pytest tests/test_painel_financeiro.py::test_gestao_custo_pai_tem_categoria_fluxo_caixa -v`
Expected: FAIL (a coluna ainda não existe no modelo).

- [ ] **Step 3: Adicionar a coluna no modelo**

Em `models.py`, na classe `GestaoCustoPai`, logo após a linha `fluxo_caixa_id = db.Column(...)` (l.5004):

```python
    # Categoria de fluxo de caixa (catálogo curável) — categoriza o custo no relatório
    # de Fluxo de Caixa e no lançamento por etapa (spec 2026-06-29-lancamento-categoria-fluxo-caixa).
    categoria_fluxo_caixa_id = db.Column(
        db.Integer, db.ForeignKey('categoria_fluxo_caixa.id'), nullable=True)
```

- [ ] **Step 4: Adicionar o relationship**

Em `models.py`, na mesma classe, logo após `fornecedor = db.relationship('Fornecedor', foreign_keys=[fornecedor_id])` (l.5028):

```python
    categoria_fluxo_caixa = db.relationship(
        'CategoriaFluxoCaixa', foreign_keys=[categoria_fluxo_caixa_id])
```

- [ ] **Step 5: Adicionar a migração 204**

Em `migrations.py`, após `_migration_203_drop_valor_realizado` (~l.13726-13738):

```python
def _migration_204_gestao_custo_pai_categoria_fc():
    """Lançamento por categoria de fluxo de caixa — adiciona
    gestao_custo_pai.categoria_fluxo_caixa_id (FK p/ categoria_fluxo_caixa). Idempotente.
    Ver spec 2026-06-29-lancamento-categoria-fluxo-caixa-design."""
    from sqlalchemy import text as sa_text
    try:
        with db.engine.begin() as conn:
            conn.execute(sa_text(
                "ALTER TABLE gestao_custo_pai "
                "ADD COLUMN IF NOT EXISTS categoria_fluxo_caixa_id INTEGER "
                "REFERENCES categoria_fluxo_caixa(id)"))
        logger.info("[Migration 204] gestao_custo_pai.categoria_fluxo_caixa_id adicionada.")
    except Exception as e:
        logger.error(f"[Migration 204] Falha: {e}", exc_info=True)
        raise
```

- [ ] **Step 6: Registrar a migração**

Em `migrations.py`, na lista `migrations_to_run`, após a linha da 203 (l.4003):

```python
            (204, "Lançamento por categoria — gestao_custo_pai.categoria_fluxo_caixa_id", _migration_204_gestao_custo_pai_categoria_fc),
```

- [ ] **Step 7: Run it — expect PASS + suíte**

Run: `python -m pytest tests/test_painel_financeiro.py::test_gestao_custo_pai_tem_categoria_fluxo_caixa -v`
Expected: PASS.
Run: `python -m pytest tests/test_cronograma_fisico_financeiro.py tests/test_painel_financeiro.py tests/test_importacao_fisico_financeiro.py -q`
Expected: verde (invariantes da Baia não mudam).

- [ ] **Step 8: Commit**

```bash
git add models.py migrations.py tests/test_painel_financeiro.py
git commit -m "feat(baia): coluna gestao_custo_pai.categoria_fluxo_caixa_id (migração 204)"
```

---

## Task 2: `registrar_custo_automatico` aceita `categoria_fluxo_caixa_id`

**Files:**
- Modify: `utils/financeiro_integration.py` (`registrar_custo_automatico`, l.59-207)
- Test: `tests/test_painel_financeiro.py`

**Interfaces:**
- Consumes: `GestaoCustoPai.categoria_fluxo_caixa_id` (Task 1).
- Produces: `registrar_custo_automatico(..., categoria_fluxo_caixa_id=None)` grava a categoria no Pai e a inclui na chave de busca do Pai em aberto (categorias diferentes → Pais diferentes).

- [ ] **Step 1: Write the failing test**

Adicionar a `tests/test_painel_financeiro.py`:

```python
@pytest.mark.integration
def test_registrar_custo_separa_pai_por_categoria_fc():
    from utils.financeiro_integration import registrar_custo_automatico
    from models import CategoriaFluxoCaixa, GestaoCustoFilho
    from decimal import Decimal
    from datetime import date
    with app.app_context():
        aid = _novo_admin()
        CategoriaFluxoCaixa.seed_defaults(aid)
        db.session.commit()
        mat = CategoriaFluxoCaixa.query.filter_by(
            admin_id=aid, nome='Materiais de Obra', tipo='SAIDA').first()
        mo = CategoriaFluxoCaixa.query.filter_by(
            admin_id=aid, nome='Mão de Obra Direta', tipo='SAIDA').first()
        f1 = registrar_custo_automatico(
            admin_id=aid, tipo_categoria='OUTROS', entidade_nome='Lançamento manual',
            entidade_id=None, data=date(2026, 6, 10), descricao='Cimento',
            valor=Decimal('100'), obra_id=None,
            origem_tabela='lancamento_periodo_manual', origem_id=None,
            categoria_fluxo_caixa_id=mat.id, force_v2=True)
        f2 = registrar_custo_automatico(
            admin_id=aid, tipo_categoria='OUTROS', entidade_nome='Lançamento manual',
            entidade_id=None, data=date(2026, 6, 11), descricao='Diária',
            valor=Decimal('200'), obra_id=None,
            origem_tabela='lancamento_periodo_manual', origem_id=None,
            categoria_fluxo_caixa_id=mo.id, force_v2=True)
        db.session.commit()
        assert f1 is not None and f2 is not None
        # categorias diferentes → pais diferentes
        assert f1.pai_id != f2.pai_id
        assert f1.pai.categoria_fluxo_caixa_id == mat.id
        assert f2.pai.categoria_fluxo_caixa_id == mo.id
```

- [ ] **Step 2: Run it — expect FAIL**

Run: `python -m pytest tests/test_painel_financeiro.py::test_registrar_custo_separa_pai_por_categoria_fc -v`
Expected: FAIL — `TypeError: ... unexpected keyword argument 'categoria_fluxo_caixa_id'`.

- [ ] **Step 3: Adicionar o parâmetro à assinatura**

Em `utils/financeiro_integration.py`, na assinatura de `registrar_custo_automatico` (l.59-73), adicionar o parâmetro antes de `force_v2`:

```python
    obra_servico_custo_id=None,
    categoria_fluxo_caixa_id=None,
    force_v2: bool = False,
):
```

- [ ] **Step 4: Incluir a categoria na chave de busca do Pai**

Em `utils/financeiro_integration.py`, no bloco `filtros` (l.123-132), após o tratamento de entidade, adicionar:

```python
        if categoria_fluxo_caixa_id is not None:
            filtros.append(GestaoCustoPai.categoria_fluxo_caixa_id == categoria_fluxo_caixa_id)
        else:
            filtros.append(GestaoCustoPai.categoria_fluxo_caixa_id.is_(None))
```

(Inserir logo antes de `pai = (GestaoCustoPai.query.filter(*filtros)...` na l.134.)

- [ ] **Step 5: Gravar a categoria ao criar o Pai**

Em `utils/financeiro_integration.py`, no construtor do Pai novo (l.142-149), adicionar a chave:

```python
            pai = GestaoCustoPai(
                admin_id=admin_id,
                tipo_categoria=categoria_normalizada,
                entidade_nome=entidade_nome,
                entidade_id=entidade_id,
                categoria_fluxo_caixa_id=categoria_fluxo_caixa_id,
                valor_total=Decimal('0.00'),
                status='PENDENTE',
            )
```

- [ ] **Step 6: Run it — expect PASS + suíte**

Run: `python -m pytest tests/test_painel_financeiro.py::test_registrar_custo_separa_pai_por_categoria_fc -v`
Expected: PASS.
Run: `python -m pytest tests/test_cronograma_fisico_financeiro.py tests/test_painel_financeiro.py tests/test_importacao_fisico_financeiro.py -q`
Expected: verde (chamadas existentes não passam o parâmetro → `None` → comportamento atual).

- [ ] **Step 7: Commit**

```bash
git add utils/financeiro_integration.py tests/test_painel_financeiro.py
git commit -m "feat(baia): registrar_custo_automatico grava categoria_fluxo_caixa_id (chave do Pai)"
```

---

## Task 3: Serviço — categorias para dropdown, resolução com fallback, e categoria nos lançamentos

**Files:**
- Modify: `services/cronograma_fisico_financeiro.py` (após `lancamentos_da_etapa`, l.600-622)
- Test: `tests/test_painel_financeiro.py`

**Interfaces:**
- Consumes: `CategoriaFluxoCaixa` (model); `GestaoCustoPai.categoria_fluxo_caixa` (Task 1).
- Produces:
  - `categorias_fluxo_caixa_saida(admin_id) -> list[dict]` — `[{"grupo": str, "opcoes": [{"id": int, "nome": str}]}]`, só SAÍDA ativas, agrupado/ordenado por `grupo_financeiro`, `nome`.
  - `resolver_categoria_fluxo_caixa(admin_id, categoria_id) -> int|None` — devolve `categoria_id` se for CFC de SAÍDA ativa do tenant; senão a "Outras Saídas" do tenant; senão `None`.
  - `lancamentos_da_etapa(obra, osc_id)` passa a incluir, por item, `categoria_id: int|None` e `categoria_label: str|None`.

- [ ] **Step 1: Write the failing tests**

Adicionar a `tests/test_painel_financeiro.py`:

```python
@pytest.mark.integration
def test_categorias_fluxo_caixa_saida_agrupa():
    from services.cronograma_fisico_financeiro import categorias_fluxo_caixa_saida
    from models import CategoriaFluxoCaixa
    with app.app_context():
        aid = _novo_admin()
        CategoriaFluxoCaixa.seed_defaults(aid)
        db.session.commit()
        grupos = categorias_fluxo_caixa_saida(aid)
        # estrutura agrupada
        assert all(set(g.keys()) == {'grupo', 'opcoes'} for g in grupos)
        nomes = {o['nome'] for g in grupos for o in g['opcoes']}
        assert 'Materiais de Obra' in nomes
        # só SAÍDA — nenhuma categoria de ENTRADA aparece
        assert 'Receita de Obras' not in nomes


@pytest.mark.integration
def test_resolver_categoria_fluxo_caixa_fallback():
    from services.cronograma_fisico_financeiro import resolver_categoria_fluxo_caixa
    from models import CategoriaFluxoCaixa
    with app.app_context():
        aid = _novo_admin()
        CategoriaFluxoCaixa.seed_defaults(aid)
        db.session.commit()
        outras = CategoriaFluxoCaixa.query.filter_by(
            admin_id=aid, nome='Outras Saídas', tipo='SAIDA').first()
        receita = CategoriaFluxoCaixa.query.filter_by(
            admin_id=aid, tipo='ENTRADA').first()
        mat = CategoriaFluxoCaixa.query.filter_by(
            admin_id=aid, nome='Materiais de Obra', tipo='SAIDA').first()
        # válida → ela mesma
        assert resolver_categoria_fluxo_caixa(aid, mat.id) == mat.id
        # None → Outras Saídas
        assert resolver_categoria_fluxo_caixa(aid, None) == outras.id
        # ENTRADA (não SAÍDA) → fallback Outras Saídas
        assert resolver_categoria_fluxo_caixa(aid, receita.id) == outras.id


@pytest.mark.integration
def test_lancamentos_da_etapa_expoe_categoria():
    from services.importacao_fisico_financeiro import importar_fisico_financeiro
    from services.cronograma_fisico_financeiro import lancamentos_da_etapa
    from utils.financeiro_integration import registrar_custo_automatico
    from models import Obra, ObraServicoCusto, CategoriaFluxoCaixa
    from decimal import Decimal
    from datetime import date
    import json, os
    with app.app_context():
        aid = _novo_admin()
        CategoriaFluxoCaixa.seed_defaults(aid)
        caminho = os.path.join(os.path.dirname(__file__), 'fixtures',
                               'cronograma_fisico_financeiro_baias.json')
        oid = importar_fisico_financeiro(json.load(open(caminho, encoding='utf-8')), aid)['obra_id']
        obra = Obra.query.get(oid)
        osc = ObraServicoCusto.query.filter_by(obra_id=oid, admin_id=aid).first()
        mat = CategoriaFluxoCaixa.query.filter_by(
            admin_id=aid, nome='Materiais de Obra', tipo='SAIDA').first()
        registrar_custo_automatico(
            admin_id=aid, tipo_categoria='OUTROS', entidade_nome='Lançamento manual',
            entidade_id=None, data=date(2026, 6, 10), descricao='Cimento',
            valor=Decimal('100'), obra_id=oid, obra_servico_custo_id=osc.id,
            origem_tabela='lancamento_periodo_manual', origem_id=None,
            categoria_fluxo_caixa_id=mat.id, force_v2=True)
        db.session.commit()
        out = lancamentos_da_etapa(obra, osc.id)
        assert len(out) == 1
        assert out[0]['categoria_id'] == mat.id
        assert out[0]['categoria_label'] == 'Materiais de Obra'
```

- [ ] **Step 2: Run them — expect FAIL**

Run: `python -m pytest tests/test_painel_financeiro.py::test_categorias_fluxo_caixa_saida_agrupa tests/test_painel_financeiro.py::test_resolver_categoria_fluxo_caixa_fallback tests/test_painel_financeiro.py::test_lancamentos_da_etapa_expoe_categoria -v`
Expected: FAIL — `ImportError` nos dois helpers; `KeyError 'categoria_id'` no terceiro.

- [ ] **Step 3: Adicionar os dois helpers**

Em `services/cronograma_fisico_financeiro.py`, logo após a função `lancamentos_da_etapa` (após l.622):

```python
def categorias_fluxo_caixa_saida(admin_id) -> list:
    """Categorias de SAÍDA ativas do tenant, agrupadas por grupo_financeiro, para o
    dropdown do lançamento: [{"grupo": str, "opcoes": [{"id", "nome"}]}]."""
    from models import db, CategoriaFluxoCaixa
    rows = (db.session.query(CategoriaFluxoCaixa)
            .filter(CategoriaFluxoCaixa.admin_id == admin_id)
            .filter(CategoriaFluxoCaixa.tipo == 'SAIDA')
            .filter(CategoriaFluxoCaixa.ativo.is_(True))
            .order_by(CategoriaFluxoCaixa.grupo_financeiro, CategoriaFluxoCaixa.nome)
            .all())
    grupos: list = []
    idx: dict = {}
    for c in rows:
        g = c.grupo_financeiro or 'Outros'
        if g not in idx:
            idx[g] = len(grupos)
            grupos.append({"grupo": g, "opcoes": []})
        grupos[idx[g]]["opcoes"].append({"id": c.id, "nome": c.nome})
    return grupos


def resolver_categoria_fluxo_caixa(admin_id, categoria_id):
    """Resolve a categoria do lançamento: devolve `categoria_id` se for uma
    CategoriaFluxoCaixa de SAÍDA ativa do tenant; senão a 'Outras Saídas' do tenant;
    senão None. Nunca levanta — categoria não derruba o POST."""
    from models import CategoriaFluxoCaixa
    if categoria_id is not None:
        c = (CategoriaFluxoCaixa.query
             .filter_by(id=categoria_id, admin_id=admin_id, tipo='SAIDA', ativo=True)
             .first())
        if c:
            return c.id
    fallback = (CategoriaFluxoCaixa.query
                .filter_by(admin_id=admin_id, nome='Outras Saídas', tipo='SAIDA')
                .first())
    return fallback.id if fallback else None
```

- [ ] **Step 4: Expor categoria em `lancamentos_da_etapa`**

Em `services/cronograma_fisico_financeiro.py`, dentro de `lancamentos_da_etapa`, no laço (l.612-620), substituir o corpo do `for f in rows:` por:

```python
    for f in rows:
        origem = f.origem_tabela or ''
        editavel = origem == 'lancamento_periodo_manual'
        pai = f.pai
        cat_id = getattr(pai, 'categoria_fluxo_caixa_id', None)
        cat_label = (pai.categoria_fluxo_caixa.nome
                     if cat_id and pai.categoria_fluxo_caixa else None)
        out.append({
            "id": f.id, "data": f.data_referencia, "descricao": f.descricao,
            "valor": f.valor, "origem": origem,
            "origem_label": ("Manual" if editavel else (origem or "Sistema")),
            "categoria_id": cat_id, "categoria_label": cat_label,
            "editavel": editavel,
        })
```

- [ ] **Step 5: Run them — expect PASS + suíte**

Run: `python -m pytest tests/test_painel_financeiro.py::test_categorias_fluxo_caixa_saida_agrupa tests/test_painel_financeiro.py::test_resolver_categoria_fluxo_caixa_fallback tests/test_painel_financeiro.py::test_lancamentos_da_etapa_expoe_categoria -v`
Expected: PASS.
Run: `python -m pytest tests/test_cronograma_fisico_financeiro.py tests/test_painel_financeiro.py tests/test_importacao_fisico_financeiro.py -q`
Expected: verde.

- [ ] **Step 6: Commit**

```bash
git add services/cronograma_fisico_financeiro.py tests/test_painel_financeiro.py
git commit -m "feat(baia): serviço de categorias (dropdown + fallback) e categoria nos lançamentos"
```

---

## Task 4: `GET .../lancamentos` expõe `categorias` (e o rótulo por lançamento)

**Files:**
- Modify: `views/obras.py` (`financeiro_etapa_lancamentos`, l.2203-2212)
- Test: `tests/test_painel_financeiro.py`

**Interfaces:**
- Consumes: `categorias_fluxo_caixa_saida(admin_id)` e `lancamentos_da_etapa` (Task 3).
- Produces: `GET .../lancamentos` → `{"lancamentos": [...], "categorias": [{"grupo", "opcoes": [{"id","nome"}]}]}`. Cada lançamento já traz `categoria_id`/`categoria_label`.

- [ ] **Step 1: Write the failing test**

```python
@pytest.mark.integration
def test_get_lancamentos_inclui_categorias():
    from services.importacao_fisico_financeiro import importar_fisico_financeiro
    from models import Usuario, ObraServicoCusto, CategoriaFluxoCaixa
    import json, os
    app.config['WTF_CSRF_ENABLED'] = False
    with app.app_context():
        aid = _novo_admin()
        u = Usuario.query.get(aid); u.versao_sistema = 'v2'
        CategoriaFluxoCaixa.seed_defaults(aid); db.session.commit()
        caminho = os.path.join(os.path.dirname(__file__), 'fixtures',
                               'cronograma_fisico_financeiro_baias.json')
        oid = importar_fisico_financeiro(json.load(open(caminho, encoding='utf-8')), aid)['obra_id']
        osc_id = ObraServicoCusto.query.filter_by(obra_id=oid, admin_id=aid).first().id
    with app.test_client() as c:
        with c.session_transaction() as s:
            s['_user_id'] = str(aid); s['_fresh'] = True
        r = c.get(f'/obras/{oid}/financeiro/etapa/{osc_id}/lancamentos')
        assert r.status_code == 200
        body = r.get_json()
        assert 'categorias' in body and isinstance(body['categorias'], list)
        nomes = {o['nome'] for g in body['categorias'] for o in g['opcoes']}
        assert 'Materiais de Obra' in nomes
```

- [ ] **Step 2: Run it — expect FAIL**

Run: `python -m pytest tests/test_painel_financeiro.py::test_get_lancamentos_inclui_categorias -v`
Expected: FAIL — sem a chave `categorias`.

- [ ] **Step 3: Estender o GET**

Em `views/obras.py`, substituir a função `financeiro_etapa_lancamentos` (l.2203-2212) por:

```python
@main_bp.route('/obras/<int:id>/financeiro/etapa/<int:osc_id>/lancamentos', methods=['GET'])
@login_required
@capture_db_errors
def financeiro_etapa_lancamentos(id, osc_id):
    from models import ObraServicoCusto
    from services.cronograma_fisico_financeiro import (
        lancamentos_da_etapa, categorias_fluxo_caixa_saida)
    admin_id = get_tenant_admin_id()
    obra = Obra.query.filter_by(id=id, admin_id=admin_id).first_or_404()
    ObraServicoCusto.query.filter_by(id=osc_id, obra_id=obra.id, admin_id=admin_id).first_or_404()
    return jsonify(_jsonable({
        'lancamentos': lancamentos_da_etapa(obra, osc_id),
        'categorias': categorias_fluxo_caixa_saida(admin_id),
    }))
```

- [ ] **Step 4: Run it — expect PASS**

Run: `python -m pytest tests/test_painel_financeiro.py::test_get_lancamentos_inclui_categorias -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add views/obras.py tests/test_painel_financeiro.py
git commit -m "feat(baia): GET lançamentos expõe categorias de fluxo de caixa"
```

---

## Task 5: `POST .../lancamentos` aceita `categoria_fluxo_caixa_id`

**Files:**
- Modify: `views/obras.py` (`financeiro_etapa_lancamento_criar`, l.2215-2252)
- Test: `tests/test_painel_financeiro.py`

**Interfaces:**
- Consumes: `resolver_categoria_fluxo_caixa(admin_id, categoria_id)` (Task 3); `registrar_custo_automatico(..., categoria_fluxo_caixa_id=)` (Task 2).
- Produces: `POST .../lancamentos` body `{data, descricao, valor, fornecedor?, categoria_fluxo_caixa_id?}` → grava o custo com a categoria resolvida no Pai; resposta inalterada `{lancamento_id, painel}`.

- [ ] **Step 1: Write the failing test**

```python
@pytest.mark.integration
def test_post_lancamento_grava_categoria_fc_e_fallback():
    from services.importacao_fisico_financeiro import importar_fisico_financeiro
    from models import Usuario, ObraServicoCusto, GestaoCustoFilho, CategoriaFluxoCaixa
    import json, os
    app.config['WTF_CSRF_ENABLED'] = False
    with app.app_context():
        aid = _novo_admin()
        u = Usuario.query.get(aid); u.versao_sistema = 'v2'
        CategoriaFluxoCaixa.seed_defaults(aid); db.session.commit()
        caminho = os.path.join(os.path.dirname(__file__), 'fixtures',
                               'cronograma_fisico_financeiro_baias.json')
        oid = importar_fisico_financeiro(json.load(open(caminho, encoding='utf-8')), aid)['obra_id']
        osc_id = ObraServicoCusto.query.filter_by(obra_id=oid, admin_id=aid).first().id
        mat_id = CategoriaFluxoCaixa.query.filter_by(
            admin_id=aid, nome='Materiais de Obra', tipo='SAIDA').first().id
        outras_id = CategoriaFluxoCaixa.query.filter_by(
            admin_id=aid, nome='Outras Saídas', tipo='SAIDA').first().id
    with app.test_client() as c:
        with c.session_transaction() as s:
            s['_user_id'] = str(aid); s['_fresh'] = True
        # com categoria válida
        r = c.post(f'/obras/{oid}/financeiro/etapa/{osc_id}/lancamentos',
                   json={'data': '2026-06-10', 'descricao': 'Cimento', 'valor': '900',
                         'categoria_fluxo_caixa_id': mat_id})
        assert r.status_code == 200
        # sem categoria → fallback Outras Saídas
        r2 = c.post(f'/obras/{oid}/financeiro/etapa/{osc_id}/lancamentos',
                    json={'data': '2026-06-11', 'descricao': 'Sem categoria', 'valor': '50'})
        assert r2.status_code == 200
    with app.app_context():
        fmat = GestaoCustoFilho.query.filter_by(
            obra_id=oid, obra_servico_custo_id=osc_id, descricao='Cimento').one()
        ffall = GestaoCustoFilho.query.filter_by(
            obra_id=oid, obra_servico_custo_id=osc_id, descricao='Sem categoria').one()
        assert fmat.pai.categoria_fluxo_caixa_id == mat_id
        assert ffall.pai.categoria_fluxo_caixa_id == outras_id
```

- [ ] **Step 2: Run it — expect FAIL**

Run: `python -m pytest tests/test_painel_financeiro.py::test_post_lancamento_grava_categoria_fc_e_fallback -v`
Expected: FAIL — o POST ainda ignora a categoria (ambos os pais ficam sem `categoria_fluxo_caixa_id`).

- [ ] **Step 3: Estender o POST**

Em `views/obras.py`, em `financeiro_etapa_lancamento_criar`:

(a) trocar o import do serviço (l.2223) para incluir o resolvedor:

```python
    from services.cronograma_fisico_financeiro import painel_financeiro, resolver_categoria_fluxo_caixa
```

(b) após a linha `fornecedor = (...)[:120]` (l.2240), adicionar o parse + resolução da categoria:

```python
    cat_raw = p.get('categoria_fluxo_caixa_id')
    try:
        cat_in = int(cat_raw) if cat_raw not in (None, '', 'null') else None
    except (ValueError, TypeError):
        cat_in = None
    categoria_fc_id = resolver_categoria_fluxo_caixa(admin_id, cat_in)
```

(c) na chamada `registrar_custo_automatico(...)` (l.2242-2248), adicionar o argumento:

```python
    filho = registrar_custo_automatico(
        admin_id=admin_id, tipo_categoria='OUTROS',
        entidade_nome=fornecedor, entidade_id=None,
        data=data, descricao=descricao, valor=valor,
        obra_id=obra.id, obra_servico_custo_id=osc_id,
        origem_tabela='lancamento_periodo_manual', origem_id=None,
        categoria_fluxo_caixa_id=categoria_fc_id,
        force_v2=False)
```

- [ ] **Step 4: Run it — expect PASS + suíte**

Run: `python -m pytest tests/test_painel_financeiro.py::test_post_lancamento_grava_categoria_fc_e_fallback -v`
Expected: PASS.
Run: `python -m pytest tests/test_cronograma_fisico_financeiro.py tests/test_painel_financeiro.py tests/test_importacao_fisico_financeiro.py -q`
Expected: verde.

- [ ] **Step 5: Commit**

```bash
git add views/obras.py tests/test_painel_financeiro.py
git commit -m "feat(baia): POST lançamento grava categoria de fluxo de caixa (fallback Outras Saídas)"
```

---

## Task 6: Relatório de Fluxo de Caixa usa o nome da `CategoriaFluxoCaixa`

**Files:**
- Modify: `financeiro_service.py` (`calcular_fluxo_caixa`, l.572 e l.601; novo helper)
- Test: `tests/test_painel_financeiro.py`

**Interfaces:**
- Consumes: `GestaoCustoPai.categoria_fluxo_caixa` (Task 1).
- Produces: nos `detalhes` de SAÍDA vindos de `GestaoCustoPai`, a `descricao` usa o nome da CFC (`"{entidade_nome} [{nome_cfc}]"`) quando `categoria_fluxo_caixa_id` está setado; senão mantém `[tipo_categoria]`.

- [ ] **Step 1: Write the failing test**

```python
@pytest.mark.integration
def test_fluxo_caixa_usa_nome_categoria_fc():
    from financeiro_service import FinanceiroService
    from utils.financeiro_integration import registrar_custo_automatico
    from models import CategoriaFluxoCaixa
    from decimal import Decimal
    from datetime import date
    with app.app_context():
        aid = _novo_admin()
        CategoriaFluxoCaixa.seed_defaults(aid)
        db.session.commit()
        mat = CategoriaFluxoCaixa.query.filter_by(
            admin_id=aid, nome='Materiais de Obra', tipo='SAIDA').first()
        registrar_custo_automatico(
            admin_id=aid, tipo_categoria='OUTROS', entidade_nome='Fornecedor X',
            entidade_id=None, data=date(2026, 6, 10), descricao='Cimento',
            valor=Decimal('100'), obra_id=None,
            origem_tabela='lancamento_periodo_manual', origem_id=None,
            categoria_fluxo_caixa_id=mat.id, force_v2=True)
        db.session.commit()
        out = FinanceiroService.calcular_fluxo_caixa(
            aid, date(2026, 1, 1), date(2030, 1, 1))
        saidas = [d for d in out['detalhes'] if d.get('tipo') == 'SAIDA']
        assert any('Materiais de Obra' in (d.get('descricao') or '') for d in saidas)
        assert not any('[OUTROS]' in (d.get('descricao') or '') for d in saidas)
```

- [ ] **Step 2: Run it — expect FAIL**

Run: `python -m pytest tests/test_painel_financeiro.py::test_fluxo_caixa_usa_nome_categoria_fc -v`
Expected: FAIL — a descrição ainda sai como `Fornecedor X [OUTROS]`.

- [ ] **Step 3: Adicionar o helper de rótulo**

Em `financeiro_service.py`, na classe `FinanceiroService`, imediatamente antes do método `calcular_fluxo_caixa` (l.428), adicionar:

```python
    @staticmethod
    def _rotulo_categoria(custo):
        """Rótulo de categoria do custo para o fluxo de caixa: nome da
        CategoriaFluxoCaixa quando vinculada, senão o tipo_categoria (enum)."""
        if getattr(custo, 'categoria_fluxo_caixa_id', None) and custo.categoria_fluxo_caixa:
            return custo.categoria_fluxo_caixa.nome
        return custo.tipo_categoria
```

> Se `calcular_fluxo_caixa` não tiver `@staticmethod` logo acima dela, manter o decorator do helper mesmo assim (ambos são estáticos no arquivo).

- [ ] **Step 4: Usar o helper nos dois pontos**

Em `financeiro_service.py`, substituir a l.572:

```python
                    'descricao': f'{custo.entidade_nome} [{FinanceiroService._rotulo_categoria(custo)}]',
```

E a l.601:

```python
                        'descricao': f'{custo.entidade_nome} [{FinanceiroService._rotulo_categoria(custo)}]',
```

- [ ] **Step 5: Run it — expect PASS + suíte**

Run: `python -m pytest tests/test_painel_financeiro.py::test_fluxo_caixa_usa_nome_categoria_fc -v`
Expected: PASS.
Run: `python -m pytest tests/test_cronograma_fisico_financeiro.py tests/test_painel_financeiro.py tests/test_importacao_fisico_financeiro.py -q`
Expected: verde.

- [ ] **Step 6: Commit**

```bash
git add financeiro_service.py tests/test_painel_financeiro.py
git commit -m "feat(baia): relatório de fluxo de caixa usa nome da categoria curável"
```

---

## Task 7: Front — dropdown de categoria + badge na aba Realizado

**Files:**
- Modify: `static/js/financeiro_obra.js` (`carregarRealizado` l.154; `renderRealizado` l.163; `lancamentoForm` l.207)

**Interfaces:**
- Consumes: `GET .../lancamentos` (Task 4) com `categorias` + `categoria_label`; `POST .../lancamentos` (Task 5) com `categoria_fluxo_caixa_id`.
- Produces: a aba Realizado mostra um badge de categoria por lançamento; o "+ Novo lançamento" tem um `<select>` agrupado de categoria e o envia no POST.

- [ ] **Step 1: Guardar as categorias do GET**

Em `static/js/financeiro_obra.js`, em `carregarRealizado` (l.159-160), trocar o `.then` que processa a resposta por:

```javascript
      .then(function (r) { if (!r.ok) throw new Error(r.status); return r.json(); })
      .then(function (d) { box._categorias = d.categorias || []; renderRealizado(box, et, d.lancamentos || []); })
```

- [ ] **Step 2: Helper de `<select>` agrupado**

Em `static/js/financeiro_obra.js`, logo antes de `function lancamentoForm(box, et, l) {` (l.207), adicionar:

```javascript
  function categoriaSelectHTML(cats, sel) {
    var h = '<select id="fin-lc-cat" class="form-select form-select-sm"><option value="">— Categoria —</option>';
    (cats || []).forEach(function (g) {
      h += '<optgroup label="' + String(g.grupo || '').replace(/</g, '&lt;') + '">';
      (g.opcoes || []).forEach(function (o) {
        h += '<option value="' + o.id + '"' + (String(o.id) === String(sel) ? ' selected' : '') +
             '>' + String(o.nome || '').replace(/</g, '&lt;') + '</option>';
      });
      h += '</optgroup>';
    });
    return h + '</select>';
  }
```

- [ ] **Step 3: Badge de categoria na lista**

Em `static/js/financeiro_obra.js`, em `renderRealizado`, na montagem da linha (l.182-185), trocar a célula da descrição para incluir o badge de categoria:

```javascript
        html += '<tr><td style="width:90px">' + (l.data ? String(l.data).slice(8, 10) + '/' + String(l.data).slice(5, 7) : '—') + '</td>' +
          '<td>' + String(l.descricao || '').replace(/</g, '&lt;') +
            (l.categoria_label ? ' <span class="badge bg-light text-dark border">' + String(l.categoria_label).replace(/</g, '&lt;') + '</span>' : '') + '</td>' +
          '<td class="text-end" style="width:120px">' + BRL(l.valor) + '</td>' +
          '<td class="text-end" style="width:90px">' + acoes + '</td></tr>';
```

- [ ] **Step 4: Select de categoria no formulário (só ao criar)**

Em `static/js/financeiro_obra.js`, substituir o corpo de `lancamentoForm` (l.207-232) por:

```javascript
  function lancamentoForm(box, et, l) {
    var hoje = (l && l.data) ? String(l.data).slice(0, 10) : '';
    var catRow = l ? '' :
      '<div class="col-12 mb-1">' + categoriaSelectHTML(box._categorias, '') + '</div>';
    el('fin-lc-form').innerHTML =
      '<div class="border rounded p-2 mt-2"><div class="row g-2">' +
        catRow +
        '<div class="col-3"><input type="date" id="fin-lc-data" class="form-control form-control-sm" value="' + hoje + '"></div>' +
        '<div class="col-5"><input type="text" id="fin-lc-desc" class="form-control form-control-sm" placeholder="Descrição" value="' + (l ? String(l.descricao || '').replace(/"/g, '&quot;') : '') + '"></div>' +
        '<div class="col-2"><input type="number" step="0.01" id="fin-lc-valor" class="form-control form-control-sm text-end" placeholder="Valor" value="' + (l ? Number(l.valor || 0) : '') + '"></div>' +
        '<div class="col-2"><button type="button" id="fin-lc-salvar" class="btn btn-primary btn-sm w-100">Salvar</button></div>' +
      '</div></div>';
    el('fin-lc-salvar').addEventListener('click', function () {
      var catEl = el('fin-lc-cat');
      var payload = {
        data: el('fin-lc-data').value || '',
        descricao: el('fin-lc-desc').value || '',
        valor: el('fin-lc-valor').value || '0'
      };
      if (catEl) payload.categoria_fluxo_caixa_id = catEl.value || '';
      var url = '/obras/' + OBRA_ID + '/financeiro/etapa/' + et.osc_id + '/lancamentos' + (l ? '/' + l.id : '');
      fetch(url, {
        method: l ? 'PATCH' : 'POST',
        headers: { 'Content-Type': 'application/json', 'X-CSRFToken': csrfToken() },
        body: JSON.stringify(payload)
      })
        .then(function (r) { if (!r.ok) throw new Error(r.status); return r.json(); })
        .then(function (d) { if (d.painel) { render(d.painel); atualizarCabecalhoEtapa(et, d.painel); } carregarRealizado(box, et); })
        .catch(function () { el('fin-lc-form').innerHTML = '<div class="text-danger small">Falha ao salvar.</div>'; });
    });
  }
```

- [ ] **Step 5: Verificar parse do JS**

Run: `node --check static/js/financeiro_obra.js`
Expected: sem saída (OK).

- [ ] **Step 6: Verificação visual (browser real)**

Subir a app (`gunicorn --bind 0.0.0.0:5000 --reuse-port --reload main:app`) e, com o chromium do Nix
(`$REPLIT_PLAYWRIGHT_CHROMIUM_EXECUTABLE`) via Playwright, logar (`admin@construtoraalfa.com.br` /
`Alfa@2026`), abrir uma obra com financeiro importado → aba **Financeiro** → clicar numa etapa →
aba **Realizado — lançamentos** → **+ Novo lançamento**. Conferir:
1. O `<select>` de categoria aparece agrupado (Custo Direto de Obra, Despesas…), com "Materiais de Obra" etc.
2. Salvar com categoria "Materiais de Obra" → o lançamento aparece com o badge "Materiais de Obra".
3. O relatório de **Fluxo de Caixa** mostra o movimento como "… [Materiais de Obra]" (não "[OUTROS]").
4. Salvar sem escolher categoria → entra como "Outras Saídas".

- [ ] **Step 7: Commit**

```bash
git add static/js/financeiro_obra.js
git commit -m "feat(baia): dropdown de categoria de fluxo de caixa no + Novo lançamento"
```

---

## Task 8: Fechamento — fluxo ponta-a-ponta + suíte completa

**Files:**
- Test: `tests/test_painel_financeiro.py`

- [ ] **Step 1: Teste ponta-a-ponta (POST → realizado → categoria visível)**

```python
@pytest.mark.integration
def test_lancamento_categoria_ponta_a_ponta():
    from services.importacao_fisico_financeiro import importar_fisico_financeiro
    from services.cronograma_fisico_financeiro import lancamentos_da_etapa, painel_financeiro
    from models import Usuario, Obra, ObraServicoCusto, CategoriaFluxoCaixa
    import json, os
    app.config['WTF_CSRF_ENABLED'] = False
    with app.app_context():
        aid = _novo_admin()
        u = Usuario.query.get(aid); u.versao_sistema = 'v2'
        CategoriaFluxoCaixa.seed_defaults(aid); db.session.commit()
        caminho = os.path.join(os.path.dirname(__file__), 'fixtures',
                               'cronograma_fisico_financeiro_baias.json')
        oid = importar_fisico_financeiro(json.load(open(caminho, encoding='utf-8')), aid)['obra_id']
        osc_id = ObraServicoCusto.query.filter_by(obra_id=oid, admin_id=aid).first().id
        mat_id = CategoriaFluxoCaixa.query.filter_by(
            admin_id=aid, nome='Materiais de Obra', tipo='SAIDA').first().id
    with app.test_client() as c:
        with c.session_transaction() as s:
            s['_user_id'] = str(aid); s['_fresh'] = True
        c.post(f'/obras/{oid}/financeiro/etapa/{osc_id}/lancamentos',
               json={'data': '2026-06-10', 'descricao': 'Cimento', 'valor': '1000',
                     'categoria_fluxo_caixa_id': mat_id})
    with app.app_context():
        obra = Obra.query.get(oid)
        out = lancamentos_da_etapa(obra, osc_id)
        assert any(l['categoria_label'] == 'Materiais de Obra' for l in out)
        # conta no realizado da etapa
        p = painel_financeiro(obra)
        et = next(e for e in p['etapas'] if e['osc_id'] == osc_id)
        assert float(et['realizado']) >= 1000 - 1
```

- [ ] **Step 2: Rodar + invariantes**

Run: `python -m pytest tests/test_painel_financeiro.py::test_lancamento_categoria_ponta_a_ponta -v`
Expected: PASS.
Run: `python -m pytest tests/test_cronograma_fisico_financeiro.py tests/test_painel_financeiro.py tests/test_importacao_fisico_financeiro.py -q`
Expected: verde; invariantes da Baia (veks 800.960 / fat 550.775 / lucro 24.976 / imposto 128.903) preservados.

- [ ] **Step 3: Suíte inteira (não-browser)**

Run: `python -m pytest -q --ignore=scripts --ignore=archive -k "not playwright and not browser"`
Expected: sem regressões fora do escopo (falhas pré-existentes são Playwright/ambiente e os 2 erros de coleta em `scripts/`/`archive/`).

- [ ] **Step 4: Commit**

```bash
git add tests/test_painel_financeiro.py
git commit -m "test(baia): lançamento por categoria de fluxo de caixa ponta-a-ponta"
```

---

## Sequência de dependências

```
T1 (coluna + migração) → T2 (registrar) → T5 (POST)
T1 → T3 (serviço: helpers + lancamentos) → T4 (GET)
T1 → T6 (relatório de fluxo de caixa)
T3 → T5, T4
T2..T6 → T7 (front) → T8 (fechamento)
```

## Rollback
Cada task é um commit isolado. Reverter T7 mantém o backend (T1-T6) estável. A migração 204 é idempotente (`ADD COLUMN IF NOT EXISTS`) e a coluna é nullable — reverter o modelo deixa a coluna órfã no banco sem quebrar (o ORM só para de mapeá-la); para remover de fato, criar migração simétrica `DROP COLUMN IF EXISTS` no futuro.

---

## Self-Review

**1. Spec coverage**

| Requisito da spec | Task |
|---|---|
| `categoria_fluxo_caixa_id` em `GestaoCustoPai` + relationship | T1 |
| Migração 204 idempotente | T1 |
| `registrar_custo_automatico` grava a categoria | T2 |
| Categoria entra na chave do Pai (não funde categorias) | T2 |
| `tipo_categoria` permanece 'OUTROS' no manual | T2/T5 (chamada usa 'OUTROS') |
| Dropdown só SAÍDA ativas, agrupado por grupo | T3 (`categorias_fluxo_caixa_saida`), T4 (GET), T7 (UI) |
| Fallback "Outras Saídas" / nunca falha por categoria | T3 (`resolver_categoria_fluxo_caixa`), T5 |
| GET expõe `categorias` + `categoria_id`/`categoria_label` | T3 (lancamentos), T4 (GET) |
| POST aceita `categoria_fluxo_caixa_id` | T5 |
| PATCH não troca categoria (fora de escopo) | — (PATCH inalterado; UI só mostra select ao criar — T7 step 4) |
| Relatório de Fluxo de Caixa usa nome da CFC | T6 |
| UI: dropdown + badge | T7 |
| Realizado/somatórios inalterados | T8 (assert realizado), suíte em todas |
| Multitenant (categoria de outro admin → fallback) | T3 (`resolver` filtra por admin_id); coberto por `test_resolver_categoria_fluxo_caixa_fallback` (categoria não-SAÍDA → fallback; mesma lógica para id de outro tenant que não casa `admin_id`) |
| Invariantes da Baia; suíte verde | T1-T8 |

**2. Placeholder scan** — sem TBD/TODO; cada step de código mostra o código completo; comandos com expected output. A verificação de UI (select/badge/relatório) é manual no browser real (T7 step 6) — não há harness JS/DOM no repo, mesmo padrão das fases de UI viva dos planos anteriores.

**3. Type consistency** —
- `registrar_custo_automatico(..., categoria_fluxo_caixa_id=)` definido em T2 e consumido em T5 com o mesmo nome.
- `categorias_fluxo_caixa_saida(admin_id) -> [{"grupo", "opcoes":[{"id","nome"}]}]` produzido em T3, consumido em T4 (GET) e T7 (`categoriaSelectHTML(cats, sel)` lê `g.grupo`, `g.opcoes`, `o.id`, `o.nome`).
- `resolver_categoria_fluxo_caixa(admin_id, categoria_id) -> int|None` produzido em T3, consumido em T5.
- `lancamentos_da_etapa` acrescenta `categoria_id`/`categoria_label` em T3, lidos em T7 (badge) e nos testes T3/T8.
- `FinanceiroService._rotulo_categoria(custo)` definido e usado dentro do mesmo arquivo em T6.
- Front: `box._categorias` setado em T7 step 1 e lido em T7 step 4; `payload.categoria_fluxo_caixa_id` casa com o body esperado pelo POST (T5).
</content>
