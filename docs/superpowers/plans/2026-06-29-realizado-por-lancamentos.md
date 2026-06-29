# Realizado por lançamentos (Pedaço 1) — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Trocar o realizado da aba/painel Financeiro: deixar de usar o número manual `valor_realizado` e passar a **somar lançamentos de custo reais** (`GestaoCustoFilho`) ligados à etapa, por período; o modal do grupo vira só Previsão; o painel da etapa ganha uma aba **Realizado — lançamentos** com **"+ Novo lançamento"** que cria um Contas a Pagar via `registrar_custo_automatico`.

**Architecture:** Backend reaproveita `GestaoCustoPai`/`GestaoCustoFilho` (sem tabela nova). O realizado já é agregado por `realizado_por_etapa`/`curva_realizado` a partir de `GestaoCustoFilho` — então o trabalho é (a) **reverter** o caminho `valor_realizado` (coluna, somas nos indicadores, parse no endpoint) e dropar a coluna (migração 203), e (b) **adicionar** endpoints REST de lançamentos (listar/criar/editar/excluir manual) + a UI de Realizado no nível da etapa. Lançamentos manuais passam pelo helper `utils/financeiro_integration.registrar_custo_automatico(...)`, virando Contas a Pagar reais que já fluem para Curva S/caixa.

**Tech Stack:** Flask + SQLAlchemy (Postgres), migrações idempotentes em `migrations.py`, front vanilla JS + Bootstrap 5 + Chart.js, testes `pytest`. Verificação visual via Playwright + chromium do Nix (`REPLIT_PLAYWRIGHT_CHROMIUM_EXECUTABLE`).

## Global Constraints

- **Obra-piloto:** Baia. **Previsto inalterado:** veks 800.960 / fat 550.775 / lucro 24.976 / imposto 128.903 / contrato 1.505.613,76 / data_fim 08/10. **Realizado começa em 0** (nenhum `GestaoCustoFilho` ligado às etapas da Baia ainda) — coerente: realizado só existe quando há lançamento.
- **Lançamento = `GestaoCustoFilho` real.** Manual usa `tipo_categoria='OUTROS'`, `origem_tabela='lancamento_periodo_manual'`, `obra_servico_custo_id=<osc da etapa>`. Aparece em Gestão de Custos/Fluxo de Caixa/Curva S — sem dupla contagem.
- **Realizado é por ETAPA × período (mês)**, não por grupo de previsão. Independente da Previsão: custo não previsto é só um lançamento (previsto fica 0).
- **Migração 203:** número livre confirmado (a 202 é `valor_realizado`). Idempotente, padrão do repo: `DROP COLUMN IF EXISTS`.
- **Helper de criação:** `registrar_custo_automatico(admin_id, tipo_categoria, entidade_nome, entidade_id, data, descricao, valor, obra_id=, obra_servico_custo_id=, origem_tabela=, origem_id=, force_v2=False)` retorna o `GestaoCustoFilho` criado (ou `None`), faz flush sem commit.
- **Recalcular pai:** `from gestao_custos_views import _recalcular_total_pai` → `_recalcular_total_pai(pai)` recalcula `valor_total`+`saldo` a partir dos filhos.
- Suíte de regressão (rodar após cada task):
  ```
  python -m pytest tests/test_cronograma_fisico_financeiro.py tests/test_painel_financeiro.py tests/test_importacao_fisico_financeiro.py -q
  ```

---

## File Structure

| Arquivo | Responsabilidade | Mudança |
|---|---|---|
| `models.py` (`ObraServicoCustoItem`, ~l.5713) | ORM da linha/período | **Modificar** — remover `valor_realizado` |
| `migrations.py` (registry ~l.4002; defs ~l.13695) | Schema | **Modificar** — `_migration_203_drop_valor_realizado` |
| `services/cronograma_fisico_financeiro.py` (l.522, 548, 565-630) | Painel/indicadores + serviço de lançamentos | **Modificar** — reverter `valor_realizado`; novo `lancamentos_da_etapa` |
| `views/obras.py` (`financeiro_etapa_itens` ~l.2136; rotas novas) | Endpoints | **Modificar** — reverter parse; **+** rotas `/lancamentos` (GET/POST/PATCH/DELETE) |
| `static/js/financeiro_obra.js` | UI viva | **Modificar** — modal só Previsão; painel da etapa com aba Realizado + lançamentos |
| `templates/obras/detalhes_obra_profissional.html` (modal) | Markup | **Modificar** — modal perde aba Realizado |
| `tests/test_painel_financeiro.py` | Testes | **Modificar** — remover testes de `valor_realizado`; novos de lançamentos |

---

## Task 1: Reverter `valor_realizado` (indicadores, coluna, endpoint) + migração 203

**Files:**
- Modify: `services/cronograma_fisico_financeiro.py:522,548,565-630`
- Modify: `models.py:5713`
- Modify: `views/obras.py` (`financeiro_etapa_itens`, parse + persistência)
- Modify: `migrations.py:4002` (registry) e ~`13695` (nova função)
- Modify: `tests/test_painel_financeiro.py` (remover testes de `valor_realizado`)

**Interfaces:**
- Produces: `realizado_por_etapa(obra)` e `curva_realizado(obra)` voltam a agregar **só** `GestaoCustoFilho`. `realizado_manual_por_osc` **deixa de existir**. Item do painel sem chave `valor_realizado`. Endpoint de itens com tupla de **6** elementos `(desc, valor, fonte, ordem, di, df)`.

- [ ] **Step 1: Write the failing test (coluna não existe mais)**

Adicionar a `tests/test_painel_financeiro.py`:

```python
@pytest.mark.integration
def test_osc_item_sem_valor_realizado():
    from models import ObraServicoCustoItem
    cols = {c.name for c in ObraServicoCustoItem.__table__.columns}
    assert 'valor_realizado' not in cols
```

- [ ] **Step 2: Run it — expect FAIL**

Run: `python -m pytest tests/test_painel_financeiro.py::test_osc_item_sem_valor_realizado -v`
Expected: FAIL (a coluna ainda existe no modelo).

- [ ] **Step 3: Remover a coluna do modelo**

Em `models.py`, apagar a linha (l.5713):

```python
    valor_realizado = db.Column(db.Numeric(15, 2), nullable=False, default=0)  # realizado manual por período (spec 2026-06-29)
```

- [ ] **Step 4: Reverter `curva_realizado`**

Em `services/cronograma_fisico_financeiro.py`, no fim de `curva_realizado`, remover o bloco do manual (l.582-592), deixando a função terminar logo após o loop de `GestaoCustoFilho`:

```python
    out: dict = {}
    for dt, valor in rows:
        if not dt:
            continue
        chave = f"{dt.year:04d}-{dt.month:02d}"
        out[chave] = out.get(chave, Decimal("0")) + Decimal(valor or 0)
    return out
```

- [ ] **Step 5: Remover `realizado_manual_por_osc` e reverter `realizado_por_etapa`**

Apagar a função inteira `realizado_manual_por_osc` (l.596-611). Em `realizado_por_etapa`, remover o merge final (l.628-629), deixando:

```python
    out: dict = {}
    for osc_id, valor in rows:
        if osc_id is None:
            continue
        out[osc_id] = out.get(osc_id, Decimal("0")) + Decimal(valor or 0)
    return out
```

- [ ] **Step 6: Reverter o KPI e o item do painel**

Em `painel_financeiro`, remover a linha (l.548):

```python
    custo_realizado += sum(realizado_manual_por_osc(obra).values(), Decimal("0"))
```

E no dict do item (l.519-522), remover a chave `valor_realizado`, voltando a:

```python
        for it in linhas:
            itens_por_osc.setdefault(it.obra_servico_custo_id, []).append(
                {"id": it.id, "descricao": it.descricao, "valor": it.valor, "fonte": it.fonte,
                 "data_inicio": it.data_inicio, "data_fim": it.data_fim})
```

- [ ] **Step 7: Reverter o endpoint de itens (`views/obras.py`)**

Em `financeiro_etapa_itens`, no laço, remover o parse de `valor_realizado` e voltar a tupla de 6 elementos:

```python
        fonte = 'fat_direto' if it.get('fonte') == 'fat_direto' else 'veks'
        desc = (str(it.get('descricao') or '').strip() or 'Item')[:200]
        novos.append((desc, valor, fonte, i, di, df))
```

E na persistência:

```python
    for desc, valor, fonte, ordem, di, df in novos:
        db.session.add(ObraServicoCustoItem(
            obra_servico_custo_id=osc.id, admin_id=admin_id,
            descricao=desc, valor=valor, fonte=fonte, ordem=ordem,
            data_inicio=di, data_fim=df))
```

- [ ] **Step 8: Remover os testes de `valor_realizado`**

Run: `grep -n "valor_realizado" tests/test_painel_financeiro.py`
Apagar as funções de teste que dependem de `valor_realizado`: `test_osc_item_tem_valor_realizado`, `test_osc_item_valor_realizado_default_zero`, `test_painel_itens_expoem_valor_realizado`, `test_realizado_manual_entra_no_realizado_da_etapa_e_kpi`, `test_curva_realizado_inclui_valor_realizado_manual`, `test_endpoint_etapa_itens_persiste_valor_realizado`. Em `test_painel_itens_tem_campos_para_agrupar`, trocar o assert de chaves para **não** exigir `valor_realizado`:

```python
                assert {'descricao', 'fonte', 'valor'} <= set(it.keys())
```

Confirmar que nenhuma outra referência sobrou: `grep -rn "valor_realizado\|realizado_manual_por_osc" services/ views/ models.py tests/` → vazio.

- [ ] **Step 9: Adicionar a migração 203**

Em `migrations.py`, após `_migration_202_osc_item_valor_realizado`:

```python
def _migration_203_drop_valor_realizado():
    """Realizado por lançamentos — remove obra_servico_custo_item.valor_realizado
    (o realizado passa a vir de GestaoCustoFilho ligado à etapa). Idempotente.
    Ver spec 2026-06-29-realizado-por-lancamentos-design."""
    from sqlalchemy import text as sa_text
    try:
        with db.engine.begin() as conn:
            conn.execute(sa_text(
                "ALTER TABLE obra_servico_custo_item DROP COLUMN IF EXISTS valor_realizado"))
        logger.info("[Migration 203] obra_servico_custo_item.valor_realizado removida.")
    except Exception as e:
        logger.error(f"[Migration 203] Falha: {e}", exc_info=True)
        raise
```

Registrar na lista `migrations_to_run` (após a 202, l.4002):

```python
            (203, "Realizado por lançamentos — remove obra_servico_custo_item.valor_realizado", _migration_203_drop_valor_realizado),
```

- [ ] **Step 10: Rodar o novo teste + a suíte**

Run: `python -m pytest tests/test_painel_financeiro.py::test_osc_item_sem_valor_realizado -v`
Expected: PASS.
Run: `python -m pytest tests/test_cronograma_fisico_financeiro.py tests/test_painel_financeiro.py tests/test_importacao_fisico_financeiro.py -q`
Expected: verde. Os invariantes da Baia não mudam (realizado já era ~0 sem lançamentos manuais).

- [ ] **Step 11: Commit**

```bash
git add services/cronograma_fisico_financeiro.py models.py views/obras.py migrations.py tests/test_painel_financeiro.py
git commit -m "revert(baia): remove valor_realizado — realizado volta a vir só de GestaoCustoFilho (migração 203)"
```

---

## Task 2: Serviço `lancamentos_da_etapa` (listar lançamentos de uma OSC)

**Files:**
- Modify: `services/cronograma_fisico_financeiro.py` (nova função, após `realizado_por_etapa`)
- Test: `tests/test_painel_financeiro.py`

**Interfaces:**
- Produces: `lancamentos_da_etapa(obra, osc_id) -> list[dict]` — cada item
  `{"id": int, "data": date|None, "descricao": str, "valor": Decimal, "origem": str, "origem_label": str, "editavel": bool}`, ordenado por `data` (None por último). `editavel = (origem == 'lancamento_periodo_manual')`.

- [ ] **Step 1: Write the failing test**

Adicionar a `tests/test_painel_financeiro.py`:

```python
@pytest.mark.integration
def test_lancamentos_da_etapa_lista_gestao_custo_filho():
    from services.importacao_fisico_financeiro import importar_fisico_financeiro
    from services.cronograma_fisico_financeiro import lancamentos_da_etapa
    from models import Obra, ObraServicoCusto, GestaoCustoPai, GestaoCustoFilho
    from decimal import Decimal
    from datetime import date
    import json, os
    with app.app_context():
        aid = _novo_admin()
        caminho = os.path.join(os.path.dirname(__file__), 'fixtures',
                               'cronograma_fisico_financeiro_baias.json')
        oid = importar_fisico_financeiro(json.load(open(caminho, encoding='utf-8')), aid)['obra_id']
        obra = Obra.query.get(oid)
        osc = ObraServicoCusto.query.filter_by(obra_id=oid, admin_id=aid).first()
        pai = GestaoCustoPai(admin_id=aid, tipo_categoria='OUTROS',
                             entidade_nome='Fornecedor X', valor_total=Decimal('300'),
                             status='PENDENTE')
        db.session.add(pai); db.session.flush()
        db.session.add(GestaoCustoFilho(
            pai_id=pai.id, admin_id=aid, obra_id=oid, obra_servico_custo_id=osc.id,
            data_referencia=date(2026, 6, 10), descricao='Aluguel sala',
            valor=Decimal('300'), origem_tabela='lancamento_periodo_manual'))
        db.session.commit()
        out = lancamentos_da_etapa(obra, osc.id)
        assert len(out) == 1
        l = out[0]
        assert l['descricao'] == 'Aluguel sala'
        assert Decimal(str(l['valor'])) == Decimal('300')
        assert l['data'] == date(2026, 6, 10)
        assert l['editavel'] is True
        assert l['origem'] == 'lancamento_periodo_manual'
```

> Construtor de `GestaoCustoPai`/`Filho`: se algum campo NOT NULL faltar contra o Postgres real, copiar os kwargs mínimos de um teste existente que cria `GestaoCustoFilho` (ver `grep -rn "GestaoCustoFilho(" tests/`), ou usar `registrar_custo_automatico` para criar.

- [ ] **Step 2: Run it — expect FAIL**

Run: `python -m pytest tests/test_painel_financeiro.py::test_lancamentos_da_etapa_lista_gestao_custo_filho -v`
Expected: FAIL — `ImportError: cannot import name 'lancamentos_da_etapa'`.

- [ ] **Step 3: Implementar a função**

Em `services/cronograma_fisico_financeiro.py`, após `realizado_por_etapa`:

```python
def lancamentos_da_etapa(obra, osc_id) -> list:
    """Lança­mentos de custo realizado (GestaoCustoFilho) ligados a uma etapa (OSC),
    ordenados por data. `editavel` = lançamento manual criado no painel."""
    from models import db, GestaoCustoFilho, GestaoCustoPai
    rows = (db.session.query(GestaoCustoFilho)
            .join(GestaoCustoPai, GestaoCustoFilho.pai_id == GestaoCustoPai.id)
            .filter(GestaoCustoFilho.obra_id == obra.id)
            .filter(GestaoCustoFilho.obra_servico_custo_id == osc_id)
            .filter(GestaoCustoPai.admin_id == obra.admin_id)
            .filter(GestaoCustoPai.tipo_categoria != 'FATURAMENTO_DIRETO')
            .all())
    out = []
    for f in rows:
        origem = f.origem_tabela or ''
        editavel = origem == 'lancamento_periodo_manual'
        out.append({
            "id": f.id, "data": f.data_referencia, "descricao": f.descricao,
            "valor": f.valor, "origem": origem,
            "origem_label": ("Manual" if editavel else (origem or "Sistema")),
            "editavel": editavel,
        })
    out.sort(key=lambda x: (x["data"] is None, x["data"] or 0))
    return out
```

- [ ] **Step 4: Run it — expect PASS**

Run: `python -m pytest tests/test_painel_financeiro.py::test_lancamentos_da_etapa_lista_gestao_custo_filho -v`
Expected: PASS.

- [ ] **Step 5: Suíte + commit**

Run: `python -m pytest tests/test_cronograma_fisico_financeiro.py tests/test_painel_financeiro.py tests/test_importacao_fisico_financeiro.py -q`
Expected: verde.

```bash
git add services/cronograma_fisico_financeiro.py tests/test_painel_financeiro.py
git commit -m "feat(baia): serviço lancamentos_da_etapa — lista GestaoCustoFilho ligados à OSC"
```

---

## Task 3: `GET /obras/<id>/financeiro/etapa/<osc_id>/lancamentos`

**Files:**
- Modify: `views/obras.py` (nova rota, perto de `financeiro_etapa_itens`)
- Test: `tests/test_painel_financeiro.py`

**Interfaces:**
- Consumes: `lancamentos_da_etapa(obra, osc_id)` (Task 2).
- Produces: `GET .../lancamentos` → `{"lancamentos": [...]}` (JSON-safe). 404 se a OSC não for da obra/tenant.

- [ ] **Step 1: Write the failing test**

```python
@pytest.mark.integration
def test_get_lancamentos_endpoint():
    from services.importacao_fisico_financeiro import importar_fisico_financeiro
    from models import Usuario, ObraServicoCusto, GestaoCustoPai, GestaoCustoFilho
    from decimal import Decimal
    from datetime import date
    import json, os
    app.config['WTF_CSRF_ENABLED'] = False
    with app.app_context():
        aid = _novo_admin()
        u = Usuario.query.get(aid); u.versao_sistema = 'v2'; db.session.commit()
        caminho = os.path.join(os.path.dirname(__file__), 'fixtures',
                               'cronograma_fisico_financeiro_baias.json')
        oid = importar_fisico_financeiro(json.load(open(caminho, encoding='utf-8')), aid)['obra_id']
        osc = ObraServicoCusto.query.filter_by(obra_id=oid, admin_id=aid).first()
        pai = GestaoCustoPai(admin_id=aid, tipo_categoria='OUTROS', entidade_nome='F',
                             valor_total=Decimal('150'), status='PENDENTE')
        db.session.add(pai); db.session.flush()
        db.session.add(GestaoCustoFilho(
            pai_id=pai.id, admin_id=aid, obra_id=oid, obra_servico_custo_id=osc.id,
            data_referencia=date(2026, 7, 5), descricao='Conta luz', valor=Decimal('150'),
            origem_tabela='lancamento_periodo_manual'))
        db.session.commit()
        osc_id = osc.id
    with app.test_client() as c:
        with c.session_transaction() as s:
            s['_user_id'] = str(aid); s['_fresh'] = True
        r = c.get(f'/obras/{oid}/financeiro/etapa/{osc_id}/lancamentos')
        assert r.status_code == 200
        body = r.get_json()
        assert len(body['lancamentos']) == 1
        assert body['lancamentos'][0]['descricao'] == 'Conta luz'
```

- [ ] **Step 2: Run it — expect FAIL (404, rota inexistente)**

Run: `python -m pytest tests/test_painel_financeiro.py::test_get_lancamentos_endpoint -v`
Expected: FAIL.

- [ ] **Step 3: Implementar a rota**

Em `views/obras.py`, após `financeiro_etapa_itens`:

```python
@main_bp.route('/obras/<int:id>/financeiro/etapa/<int:osc_id>/lancamentos', methods=['GET'])
@login_required
@capture_db_errors
def financeiro_etapa_lancamentos(id, osc_id):
    from models import ObraServicoCusto
    from services.cronograma_fisico_financeiro import lancamentos_da_etapa
    admin_id = get_tenant_admin_id()
    obra = Obra.query.filter_by(id=id, admin_id=admin_id).first_or_404()
    ObraServicoCusto.query.filter_by(id=osc_id, obra_id=obra.id, admin_id=admin_id).first_or_404()
    return jsonify(_jsonable({'lancamentos': lancamentos_da_etapa(obra, osc_id)}))
```

- [ ] **Step 4: Run it — expect PASS**

Run: `python -m pytest tests/test_painel_financeiro.py::test_get_lancamentos_endpoint -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add views/obras.py tests/test_painel_financeiro.py
git commit -m "feat(baia): GET endpoint de lançamentos da etapa"
```

---

## Task 4: `POST .../lancamentos` — criar lançamento manual (Contas a Pagar)

**Files:**
- Modify: `views/obras.py` (rota POST)
- Test: `tests/test_painel_financeiro.py`

**Interfaces:**
- Consumes: `registrar_custo_automatico(...)`; `painel_financeiro(obra)`.
- Produces: `POST .../lancamentos` body `{data, descricao, valor, fornecedor?}` → cria `GestaoCustoPai`+`Filho` (`origem_tabela='lancamento_periodo_manual'`, `obra_servico_custo_id=osc_id`); responde `{"lancamento_id": int, "painel": {...}}`. Valor inválido/negativo ou data inválida → 400. OSC de outra obra/tenant → 404.

- [ ] **Step 1: Write the failing test**

```python
@pytest.mark.integration
def test_post_lancamento_manual_cria_conta_pagar():
    from services.importacao_fisico_financeiro import importar_fisico_financeiro
    from models import Usuario, ObraServicoCusto, GestaoCustoFilho
    from decimal import Decimal
    import json, os
    app.config['WTF_CSRF_ENABLED'] = False
    with app.app_context():
        aid = _novo_admin()
        u = Usuario.query.get(aid); u.versao_sistema = 'v2'; db.session.commit()
        caminho = os.path.join(os.path.dirname(__file__), 'fixtures',
                               'cronograma_fisico_financeiro_baias.json')
        oid = importar_fisico_financeiro(json.load(open(caminho, encoding='utf-8')), aid)['obra_id']
        osc_id = ObraServicoCusto.query.filter_by(obra_id=oid, admin_id=aid).first().id
    with app.test_client() as c:
        with c.session_transaction() as s:
            s['_user_id'] = str(aid); s['_fresh'] = True
        r = c.post(f'/obras/{oid}/financeiro/etapa/{osc_id}/lancamentos',
                   json={'data': '2026-06-10', 'descricao': 'Aluguel sala', 'valor': '900'})
        assert r.status_code == 200
        body = r.get_json()
        assert 'painel' in body and body.get('lancamento_id')
        # valor negativo → 400
        r2 = c.post(f'/obras/{oid}/financeiro/etapa/{osc_id}/lancamentos',
                    json={'data': '2026-06-10', 'descricao': 'x', 'valor': '-5'})
        assert r2.status_code == 400
    with app.app_context():
        f = GestaoCustoFilho.query.filter_by(
            obra_id=oid, obra_servico_custo_id=osc_id,
            origem_tabela='lancamento_periodo_manual').one()
        assert Decimal(str(f.valor)) == Decimal('900')
        assert f.descricao == 'Aluguel sala'
```

- [ ] **Step 2: Run it — expect FAIL**

Run: `python -m pytest tests/test_painel_financeiro.py::test_post_lancamento_manual_cria_conta_pagar -v`
Expected: FAIL (rota POST inexistente → 405/404).

- [ ] **Step 3: Implementar a rota POST**

Em `views/obras.py`, na mesma função de rota OU numa nova, adicionar o método POST (criar função separada):

```python
@main_bp.route('/obras/<int:id>/financeiro/etapa/<int:osc_id>/lancamentos', methods=['POST'])
@login_required
@capture_db_errors
def financeiro_etapa_lancamento_criar(id, osc_id):
    from decimal import Decimal, InvalidOperation
    from datetime import date as _date
    from models import ObraServicoCusto
    from utils.financeiro_integration import registrar_custo_automatico
    from services.cronograma_fisico_financeiro import painel_financeiro
    admin_id = get_tenant_admin_id()
    obra = Obra.query.filter_by(id=id, admin_id=admin_id).first_or_404()
    ObraServicoCusto.query.filter_by(id=osc_id, obra_id=obra.id, admin_id=admin_id).first_or_404()

    p = request.get_json(silent=True) or {}
    try:
        valor = Decimal(str(p.get('valor')).replace(',', '.'))
    except (InvalidOperation, ValueError, AttributeError, TypeError):
        return jsonify({'erro': 'valor inválido'}), 400
    if valor < 0:
        return jsonify({'erro': 'valor inválido'}), 400
    try:
        data = _date.fromisoformat(str(p.get('data'))[:10])
    except (ValueError, TypeError):
        return jsonify({'erro': 'data inválida'}), 400
    descricao = (str(p.get('descricao') or '').strip() or 'Lançamento')[:200]
    fornecedor = (str(p.get('fornecedor') or '').strip() or 'Lançamento manual')[:120]

    filho = registrar_custo_automatico(
        admin_id=admin_id, tipo_categoria='OUTROS',
        entidade_nome=fornecedor, entidade_id=None,
        data=data, descricao=descricao, valor=valor,
        obra_id=obra.id, obra_servico_custo_id=osc_id,
        origem_tabela='lancamento_periodo_manual', origem_id=None,
        force_v2=False)
    if filho is None:
        return jsonify({'erro': 'não foi possível registrar (tenant não-v2?)'}), 400
    db.session.commit()
    return jsonify(_jsonable({'lancamento_id': filho.id, 'painel': painel_financeiro(obra)}))
```

- [ ] **Step 4: Run it — expect PASS**

Run: `python -m pytest tests/test_painel_financeiro.py::test_post_lancamento_manual_cria_conta_pagar -v`
Expected: PASS.

- [ ] **Step 5: Suíte + commit**

Run: `python -m pytest tests/test_cronograma_fisico_financeiro.py tests/test_painel_financeiro.py tests/test_importacao_fisico_financeiro.py -q`
Expected: verde.

```bash
git add views/obras.py tests/test_painel_financeiro.py
git commit -m "feat(baia): POST lançamento manual cria Contas a Pagar ligado à etapa"
```

---

## Task 5: `PATCH`/`DELETE .../lancamentos/<filho_id>` — editar/excluir manual

**Files:**
- Modify: `views/obras.py` (rota PATCH+DELETE)
- Test: `tests/test_painel_financeiro.py`

**Interfaces:**
- Consumes: `_recalcular_total_pai(pai)` de `gestao_custos_views`.
- Produces: `PATCH .../lancamentos/<filho_id>` body `{data?, descricao?, valor?}` edita um lançamento **manual** e recalcula o pai → `{"painel": {...}}`. `DELETE` remove o manual, recalcula/remove o pai → `{"painel": {...}}`. Lançamento não-manual ou de outra obra/tenant → 403/404.

- [ ] **Step 1: Write the failing test**

```python
@pytest.mark.integration
def test_patch_e_delete_lancamento_manual():
    from services.importacao_fisico_financeiro import importar_fisico_financeiro
    from models import Usuario, ObraServicoCusto, GestaoCustoFilho, GestaoCustoPai
    from decimal import Decimal
    import json, os
    app.config['WTF_CSRF_ENABLED'] = False
    with app.app_context():
        aid = _novo_admin()
        u = Usuario.query.get(aid); u.versao_sistema = 'v2'; db.session.commit()
        caminho = os.path.join(os.path.dirname(__file__), 'fixtures',
                               'cronograma_fisico_financeiro_baias.json')
        oid = importar_fisico_financeiro(json.load(open(caminho, encoding='utf-8')), aid)['obra_id']
        osc_id = ObraServicoCusto.query.filter_by(obra_id=oid, admin_id=aid).first().id
    with app.test_client() as c:
        with c.session_transaction() as s:
            s['_user_id'] = str(aid); s['_fresh'] = True
        r = c.post(f'/obras/{oid}/financeiro/etapa/{osc_id}/lancamentos',
                   json={'data': '2026-06-10', 'descricao': 'X', 'valor': '900'})
        fid = r.get_json()['lancamento_id']
        # editar valor
        rp = c.patch(f'/obras/{oid}/financeiro/etapa/{osc_id}/lancamentos/{fid}',
                     json={'valor': '1200', 'descricao': 'Y'})
        assert rp.status_code == 200
        # excluir
        rd = c.delete(f'/obras/{oid}/financeiro/etapa/{osc_id}/lancamentos/{fid}')
        assert rd.status_code == 200
    with app.app_context():
        assert GestaoCustoFilho.query.get(fid) is None
```

- [ ] **Step 2: Run it — expect FAIL**

Run: `python -m pytest tests/test_painel_financeiro.py::test_patch_e_delete_lancamento_manual -v`
Expected: FAIL (rotas inexistentes).

- [ ] **Step 3: Implementar PATCH + DELETE**

Em `views/obras.py`:

```python
@main_bp.route('/obras/<int:id>/financeiro/etapa/<int:osc_id>/lancamentos/<int:filho_id>',
               methods=['PATCH', 'DELETE'])
@login_required
@capture_db_errors
def financeiro_etapa_lancamento_editar(id, osc_id, filho_id):
    from decimal import Decimal, InvalidOperation
    from datetime import date as _date
    from models import GestaoCustoFilho
    from gestao_custos_views import _recalcular_total_pai
    from services.cronograma_fisico_financeiro import painel_financeiro
    admin_id = get_tenant_admin_id()
    obra = Obra.query.filter_by(id=id, admin_id=admin_id).first_or_404()
    filho = GestaoCustoFilho.query.filter_by(
        id=filho_id, admin_id=admin_id, obra_id=obra.id,
        obra_servico_custo_id=osc_id).first_or_404()
    if (filho.origem_tabela or '') != 'lancamento_periodo_manual':
        return jsonify({'erro': 'lançamento não editável aqui (origem do sistema)'}), 403
    pai = filho.pai

    if request.method == 'DELETE':
        db.session.delete(filho)
        db.session.flush()
        from models import GestaoCustoFilho as _F
        if _F.query.filter_by(pai_id=pai.id).count() == 0:
            db.session.delete(pai)
        else:
            _recalcular_total_pai(pai)
        db.session.commit()
        return jsonify(_jsonable({'painel': painel_financeiro(obra)}))

    p = request.get_json(silent=True) or {}
    if 'valor' in p:
        try:
            v = Decimal(str(p.get('valor')).replace(',', '.'))
        except (InvalidOperation, ValueError, AttributeError, TypeError):
            return jsonify({'erro': 'valor inválido'}), 400
        if v < 0:
            return jsonify({'erro': 'valor inválido'}), 400
        filho.valor = v
    if 'data' in p:
        try:
            filho.data_referencia = _date.fromisoformat(str(p.get('data'))[:10])
        except (ValueError, TypeError):
            return jsonify({'erro': 'data inválida'}), 400
    if 'descricao' in p:
        filho.descricao = (str(p.get('descricao') or '').strip() or 'Lançamento')[:200]
    db.session.flush()
    _recalcular_total_pai(pai)
    db.session.commit()
    return jsonify(_jsonable({'painel': painel_financeiro(obra)}))
```

- [ ] **Step 4: Run it — expect PASS**

Run: `python -m pytest tests/test_painel_financeiro.py::test_patch_e_delete_lancamento_manual -v`
Expected: PASS.

- [ ] **Step 5: Suíte + commit**

Run: `python -m pytest tests/test_cronograma_fisico_financeiro.py tests/test_painel_financeiro.py tests/test_importacao_fisico_financeiro.py -q`
Expected: verde.

```bash
git add views/obras.py tests/test_painel_financeiro.py
git commit -m "feat(baia): PATCH/DELETE de lançamento manual (recalcula Contas a Pagar)"
```

---

## Task 6: Front — modal do grupo vira só Previsão

**Files:**
- Modify: `templates/obras/detalhes_obra_profissional.html` (modal `#fin-periodos-modal`)
- Modify: `static/js/financeiro_obra.js` (remover lógica da aba Realizado do modal)

**Interfaces:**
- Produces: modal sem aba Realizado; `abrirModuloPeriodos` renderiza só a aba Previsão.

- [ ] **Step 1: Remover a aba Realizado do markup**

No template, no `#fin-periodos-modal`, remover as `nav-tabs` (os dois `<button>` Previsão/Realizado) e o `<div class="tab-pane ... id="fin-pm-real">` inteiro, deixando só o conteúdo de previsão (a tabela `fin-pm-prev-body`, `+ Adicionar período`, `fin-pm-prev-total`). O corpo do modal fica com uma seção única (sem `tab-content`/`tab-pane`, ou mantendo só o pane de previsão sempre visível).

- [ ] **Step 2: Remover a lógica de Realizado do JS**

Em `static/js/financeiro_obra.js`, dentro de `abrirModuloPeriodos`: remover `periodoRowRealHTML`, `bindRealRow`, e as linhas que populam `#fin-pm-real-body` / `#fin-pm-real-total`. Em `renderAbas`/`totais`, remover as referências a `fin-pm-real-body` e `fin-pm-real-total` e ao `valor_realizado`. Remover `valor_realizado` de `coletarItensDaEtapa` (l.163) e o `valor_realizado: 0` no objeto de `+ Adicionar período` (l.246). Em `agruparPeriodos`/`grupoLinhaHTML`/`recalcGrupo`, remover a coluna/cálculo de `realizado` por grupo (o realizado deixa de ser por grupo).

> Mantém: `reparent ao <body>` (correção de backdrop), aba Previsão completa, total previsto.

- [ ] **Step 3: Verificar parse do JS**

Run: `node --check static/js/financeiro_obra.js`
Expected: sem saída (OK).

- [ ] **Step 4: Commit**

```bash
git add templates/obras/detalhes_obra_profissional.html static/js/financeiro_obra.js
git commit -m "refactor(baia): modal de períodos vira só Previsão (realizado sai do grupo)"
```

---

## Task 7: Front — painel da etapa com aba **Realizado — lançamentos** + Novo lançamento

**Files:**
- Modify: `static/js/financeiro_obra.js` (`showEtapa` + novas funções de Realizado)

**Interfaces:**
- Consumes: `GET/POST/PATCH/DELETE .../lancamentos` (Tasks 3-5); `rotuloMes` (já existe).
- Produces: `showEtapa` renderiza duas abas no nível da etapa (`Previsão (por grupo)` | `Realizado — lançamentos`). A aba Realizado busca os lançamentos, agrupa por mês, mostra subtotais + total, e tem `+ Novo lançamento` (data/descrição/valor/fornecedor) com editar/excluir nos manuais.

- [ ] **Step 1: Reestruturar `showEtapa` com 2 abas**

Em `static/js/financeiro_obra.js`, no HTML montado por `showEtapa`, envolver a tabela de grupos (Previsão) num pane e adicionar um pane Realizado, com um nav simples de etapa:

```javascript
    box.innerHTML =
      '<div class="border rounded p-3 bg-light">' +
      '<div class="d-flex justify-content-between mb-2"><strong>' + et.nome +
        (et.tipo === 'periodo' ? ' <span class="badge bg-secondary">período</span>' : '') +
        '</strong>' +
        '<span>Realizado: <span id="fin-et-real">' + BRL(et.realizado) + '</span>' +
        ' / Previsto: <span id="fin-it-prev">' + BRL(et.previsto) + '</span></span></div>' +
      '<ul class="nav nav-tabs mb-2"><li class="nav-item">' +
        '<button class="nav-link active" id="fin-et-tab-prev" type="button">Previsão (por grupo)</button></li>' +
        '<li class="nav-item"><button class="nav-link" id="fin-et-tab-real" type="button">Realizado — lançamentos</button></li></ul>' +
      '<div id="fin-et-pane-prev">' + previsaoTabelaHTML(box) + '</div>' +
      '<div id="fin-et-pane-real" style="display:none"></div>' +
      '</div>';
```

Onde `previsaoTabelaHTML(box)` devolve a tabela de grupos + botão "Salvar etapa" (o conteúdo que `showEtapa` montava antes). Os dois botões alternam os panes:

```javascript
    function showPane(which) {
      el('fin-et-pane-prev').style.display = which === 'prev' ? '' : 'none';
      el('fin-et-pane-real').style.display = which === 'real' ? '' : 'none';
      el('fin-et-tab-prev').classList.toggle('active', which === 'prev');
      el('fin-et-tab-real').classList.toggle('active', which === 'real');
      if (which === 'real') carregarRealizado(box, et);
    }
    el('fin-et-tab-prev').addEventListener('click', function () { showPane('prev'); });
    el('fin-et-tab-real').addEventListener('click', function () { showPane('real'); });
```

> Reconectar os binds da Previsão (`.fin-grp-open`, `#fin-it-save`) após montar o HTML, como já era feito.

- [ ] **Step 2: Implementar a aba Realizado (fetch + agrupa por mês)**

```javascript
  function carregarRealizado(box, et) {
    var pane = el('fin-et-pane-real');
    pane.innerHTML = '<div class="text-muted small">Carregando…</div>';
    fetch('/obras/' + OBRA_ID + '/financeiro/etapa/' + et.osc_id + '/lancamentos',
          { headers: { 'X-Requested-With': 'XMLHttpRequest' } })
      .then(function (r) { if (!r.ok) throw new Error(r.status); return r.json(); })
      .then(function (d) { renderRealizado(box, et, d.lancamentos || []); })
      .catch(function () { pane.innerHTML = '<div class="text-danger small">Falha ao carregar lançamentos.</div>'; });
  }
  function renderRealizado(box, et, lancs) {
    var porMes = {}, ordem = [];
    lancs.forEach(function (l) {
      var chave = l.data ? String(l.data).slice(0, 7) : 'sem-data';
      if (!porMes[chave]) { porMes[chave] = []; ordem.push(chave); }
      porMes[chave].push(l);
    });
    ordem.sort();
    var total = 0, html = '';
    ordem.forEach(function (chave) {
      var linhas = porMes[chave], sub = 0;
      var rotulo = chave === 'sem-data' ? 'sem data' : rotuloMes(chave + '-01');
      html += '<div class="fw-bold mt-2">' + rotulo + '</div><table class="table table-sm mb-1"><tbody>';
      linhas.forEach(function (l) {
        sub += Number(l.valor || 0); total += Number(l.valor || 0);
        var acoes = l.editavel
          ? '<button type="button" class="btn btn-sm btn-link p-0 fin-lc-edit" data-id="' + l.id + '">✎</button> ' +
            '<button type="button" class="btn btn-sm btn-link text-danger p-0 fin-lc-del" data-id="' + l.id + '">×</button>'
          : '<span class="badge bg-light text-dark border">' + (l.origem_label || 'Sistema') + '</span>';
        html += '<tr><td style="width:90px">' + (l.data ? String(l.data).slice(8, 10) + '/' + String(l.data).slice(5, 7) : '—') + '</td>' +
          '<td>' + String(l.descricao || '').replace(/</g, '&lt;') + '</td>' +
          '<td class="text-end" style="width:120px">' + BRL(l.valor) + '</td>' +
          '<td class="text-end" style="width:90px">' + acoes + '</td></tr>';
      });
      html += '</tbody></table><div class="small text-muted">Subtotal ' + rotulo + ': ' + BRL(sub) + '</div>';
    });
    if (!ordem.length) html = '<div class="text-muted small">Sem lançamentos. Use "+ Novo lançamento".</div>';
    el('fin-et-pane-real').innerHTML =
      html +
      '<div class="d-flex justify-content-between align-items-center mt-2">' +
        '<button type="button" id="fin-lc-novo" class="btn btn-outline-primary btn-sm">+ Novo lançamento</button>' +
        '<span class="small">Total realizado: <strong>' + BRL(total) + '</strong></span></div>' +
      '<div id="fin-lc-form"></div>';
    el('fin-lc-novo').addEventListener('click', function () { lancamentoForm(box, et, null); });
    el('fin-et-pane-real').querySelectorAll('.fin-lc-edit').forEach(function (b) {
      b.addEventListener('click', function () {
        var l = lancs.filter(function (x) { return String(x.id) === b.getAttribute('data-id'); })[0];
        lancamentoForm(box, et, l);
      });
    });
    el('fin-et-pane-real').querySelectorAll('.fin-lc-del').forEach(function (b) {
      b.addEventListener('click', function () { excluirLancamento(box, et, b.getAttribute('data-id')); });
    });
  }
```

- [ ] **Step 3: Formulário de novo/editar lançamento + persistência**

```javascript
  function lancamentoForm(box, et, l) {
    var hoje = (l && l.data) ? String(l.data).slice(0, 10) : '';
    el('fin-lc-form').innerHTML =
      '<div class="border rounded p-2 mt-2"><div class="row g-2">' +
        '<div class="col-3"><input type="date" id="fin-lc-data" class="form-control form-control-sm" value="' + hoje + '"></div>' +
        '<div class="col-5"><input type="text" id="fin-lc-desc" class="form-control form-control-sm" placeholder="Descrição" value="' + (l ? String(l.descricao || '').replace(/"/g, '&quot;') : '') + '"></div>' +
        '<div class="col-2"><input type="number" step="0.01" id="fin-lc-valor" class="form-control form-control-sm text-end" placeholder="Valor" value="' + (l ? Number(l.valor || 0) : '') + '"></div>' +
        '<div class="col-2"><button type="button" id="fin-lc-salvar" class="btn btn-primary btn-sm w-100">Salvar</button></div>' +
      '</div></div>';
    el('fin-lc-salvar').addEventListener('click', function () {
      var payload = {
        data: el('fin-lc-data').value || '',
        descricao: el('fin-lc-desc').value || '',
        valor: el('fin-lc-valor').value || '0'
      };
      var url = '/obras/' + OBRA_ID + '/financeiro/etapa/' + et.osc_id + '/lancamentos' + (l ? '/' + l.id : '');
      fetch(url, {
        method: l ? 'PATCH' : 'POST',
        headers: { 'Content-Type': 'application/json', 'X-CSRFToken': csrfToken() },
        body: JSON.stringify(payload)
      })
        .then(function (r) { if (!r.ok) throw new Error(r.status); return r.json(); })
        .then(function (d) { if (d.painel) render(d.painel); carregarRealizado(box, et); })
        .catch(function () { el('fin-lc-form').innerHTML = '<div class="text-danger small">Falha ao salvar.</div>'; });
    });
  }
  function excluirLancamento(box, et, id) {
    fetch('/obras/' + OBRA_ID + '/financeiro/etapa/' + et.osc_id + '/lancamentos/' + id, {
      method: 'DELETE', headers: { 'X-CSRFToken': csrfToken() }
    })
      .then(function (r) { if (!r.ok) throw new Error(r.status); return r.json(); })
      .then(function (d) { if (d.painel) render(d.painel); carregarRealizado(box, et); })
      .catch(function () {});
  }
```

- [ ] **Step 4: Verificar parse do JS**

Run: `node --check static/js/financeiro_obra.js`
Expected: sem saída.

- [ ] **Step 5: Verificação visual (browser real)**

Subir a app (`gunicorn --bind 0.0.0.0:5000 --reuse-port --reload main:app`) e, com o chromium do Nix
(`$REPLIT_PLAYWRIGHT_CHROMIUM_EXECUTABLE`) via Playwright, logar (`admin@construtoraalfa.com.br` /
`Alfa@2026`), abrir uma obra com financeiro importado → aba **Financeiro** → clicar numa etapa →
aba **Realizado — lançamentos** → **+ Novo lançamento** (data/descrição/valor) → Salvar. Conferir:
1. O lançamento aparece sob o mês certo, com subtotal e total atualizados.
2. O ✎ edita e o × exclui (somente em manuais).
3. O cabeçalho "Realizado / Previsto" e a Curva S refletem o novo lançamento.
4. O modal do grupo (`▸`) mostra **só Previsão**.

- [ ] **Step 6: Commit**

```bash
git add static/js/financeiro_obra.js
git commit -m "feat(baia): aba Realizado por lançamentos no painel da etapa (+ Novo lançamento manual)"
```

---

## Task 8: Fechamento — custo não previsto + suíte completa

**Files:**
- Test: `tests/test_painel_financeiro.py`

- [ ] **Step 1: Teste do custo não previsto**

```python
@pytest.mark.integration
def test_custo_nao_previsto_conta_no_realizado_da_etapa():
    from services.importacao_fisico_financeiro import importar_fisico_financeiro
    from services.cronograma_fisico_financeiro import painel_financeiro
    from models import Usuario, Obra, ObraServicoCusto
    from decimal import Decimal
    import json, os
    app.config['WTF_CSRF_ENABLED'] = False
    with app.app_context():
        aid = _novo_admin()
        u = Usuario.query.get(aid); u.versao_sistema = 'v2'; db.session.commit()
        caminho = os.path.join(os.path.dirname(__file__), 'fixtures',
                               'cronograma_fisico_financeiro_baias.json')
        oid = importar_fisico_financeiro(json.load(open(caminho, encoding='utf-8')), aid)['obra_id']
        osc_id = ObraServicoCusto.query.filter_by(obra_id=oid, admin_id=aid).first().id
    with app.test_client() as c:
        with c.session_transaction() as s:
            s['_user_id'] = str(aid); s['_fresh'] = True
        c.post(f'/obras/{oid}/financeiro/etapa/{osc_id}/lancamentos',
               json={'data': '2026-06-10', 'descricao': 'Multa imprevista', 'valor': '1000'})
    with app.app_context():
        p = painel_financeiro(Obra.query.get(oid))
        et = next(e for e in p['etapas'] if e['osc_id'] == osc_id)
        assert float(et['realizado']) >= 1000 - 1   # conta mesmo sem previsão correspondente
```

- [ ] **Step 2: Rodar + invariantes**

Run: `python -m pytest tests/test_painel_financeiro.py::test_custo_nao_previsto_conta_no_realizado_da_etapa -v`
Expected: PASS.
Run: `python -m pytest tests/test_cronograma_fisico_financeiro.py tests/test_painel_financeiro.py tests/test_importacao_fisico_financeiro.py -q`
Expected: verde; invariantes da Baia (veks 800.960 / fat 550.775 / lucro 24.976 / imposto 128.903) preservados.

- [ ] **Step 3: Suíte inteira (não-browser)**

Run: `python -m pytest -q --ignore=scripts --ignore=archive -k "not playwright and not browser"`
Expected: sem regressões fora do escopo (as falhas pré-existentes são Playwright/ambiente e os 2 erros de coleta em `scripts/`/`archive/`).

- [ ] **Step 4: Commit**

```bash
git add tests/test_painel_financeiro.py
git commit -m "test(baia): custo não previsto conta no realizado da etapa"
```

---

## Sequência de dependências

```
T1 (revert + migração 203) → T2 (serviço) → T3 (GET) → T4 (POST) → T5 (PATCH/DELETE)
T1 → T6 (modal só Previsão)
T2..T5, T6 → T7 (UI Realizado) → T8 (fechamento)
```

## Rollback
Cada task é um commit isolado. Reverter T7 mantém o backend (T1-T5) estável; reverter T1 restauraria `valor_realizado` (mas T2+ assumem o realizado por lançamentos). A migração 203 é idempotente (`DROP COLUMN IF EXISTS`).

---

## Self-Review

**1. Spec coverage**

| Requisito da spec | Task |
|---|---|
| Realizado = soma de `GestaoCustoFilho` ligados à etapa, por mês | T1 (revert p/ pipeline existente) + T2/T7 (exibição) |
| Lançamento = `GestaoCustoFilho` real (sem tabela nova) | T2, T4 |
| Manual cria Contas a Pagar via `registrar_custo_automatico` | T4 |
| Editar/excluir manual recalcula o pai | T5 |
| Não-manual é só leitura (403 em PATCH/DELETE) | T5 |
| Realizado por ETAPA × período (não por grupo) | T6 (tira do grupo) + T7 (nível etapa) |
| Custo não previsto conta sem previsão | T8 |
| Modal do grupo vira só Previsão | T6 |
| Painel da etapa com aba Realizado + Novo lançamento | T7 |
| Remover `valor_realizado` (coluna, somas, endpoint) | T1 |
| Migração 203 idempotente | T1 |
| GET/POST/PATCH/DELETE `/lancamentos` | T3, T4, T5 |
| Indicadores sem dupla contagem | T1 (revert) |
| Multitenant (404) | T3/T4/T5 (guarda `first_or_404` por admin) |
| Invariantes da Baia; suíte verde | T1, T8 |

**2. Placeholder scan** — sem TBD/TODO; cada step de código mostra o código; comandos com expected output. `previsaoTabelaHTML(box)` em T7 é descrito como "o conteúdo que `showEtapa` montava antes" — o implementador extrai o HTML/binds atuais de `showEtapa` para essa função (refactor mecânico, sem lógica nova).

**3. Type consistency** — `lancamentos_da_etapa(obra, osc_id)` retorna dicts com `{id, data, descricao, valor, origem, origem_label, editavel}`, consumidos igualmente no GET (T3), na UI (T7) e nos testes. `origem_tabela='lancamento_periodo_manual'` é o mesmo marcador em T4 (criação), T5 (guarda 403) e T2 (`editavel`). Endpoints `/lancamentos` (coleção: GET/POST) e `/lancamentos/<filho_id>` (item: PATCH/DELETE) consistentes entre T3-T5 e o front T7.

Observação de cobertura: a interação de UI (abas da etapa, formulário, editar/excluir) é verificada manualmente no browser real (T7 step 5) — não há harness JS/DOM no repo; mesmo padrão das fases de UI viva dos planos anteriores.
