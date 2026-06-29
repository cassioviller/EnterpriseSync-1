# Compras ganha o campo "Etapa" (Pedaço 3) — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** O módulo de Compras ganha um campo **Etapa** (opcional): a compra passa a gravar `obra_servico_custo_id` no `PedidoCompra` e nos `GestaoCustoFilho` que gera, de modo que o custo da compra entra automaticamente no **Realizado da etapa**.

**Architecture:** `PedidoCompra` recebe a coluna `obra_servico_custo_id` (migração 205). O form Nova Compra ganha um `<select>` Etapa em cascata com a Obra, alimentado por um endpoint novo `GET /obras/<id>/etapas-custo`. O POST `/compras/nova` valida e grava a etapa; `processar_compra_normal` (e `processar_compra_aprovada_cliente`) repassam `pedido.obra_servico_custo_id` aos `GestaoCustoFilho`. Os agregadores de realizado já somam `GestaoCustoFilho` por `obra_servico_custo_id`, então a compra flui sozinha. `lancamentos_da_etapa` rotula a origem `pedido_compra` como "Compra" (só leitura).

**Tech Stack:** Flask + SQLAlchemy (Postgres), migrações idempotentes em `migrations.py`, front Jinja + vanilla JS/jQuery + select2 + Bootstrap 5, testes `pytest`. Verificação visual via Playwright + chromium do Nix (`REPLIT_PLAYWRIGHT_CHROMIUM_EXECUTABLE`).

## Global Constraints

- **Obra-piloto:** Baia. **Previsto inalterado:** veks 800.960 / fat 550.775 / lucro 24.976 / imposto 128.903 / contrato 1.505.613,76 / data_fim 08/10. **Realizado** continua vindo de `GestaoCustoFilho` ligados às etapas; agora compras com etapa também somam.
- **Etapa é OPCIONAL** (mesmo com Obra). Sem etapa → comportamento atual preservado. Etapa nunca derruba a compra: id inválido/de outra obra → tratado como `None`.
- **Escopo: só Compras.** `tipo_categoria='MATERIAL'` (compra normal) conta no realizado; `aprovacao_cliente` cria `FATURAMENTO_DIRETO`, que os agregadores **excluem** — lá o vínculo é só rastreabilidade.
- **Migração 205:** número livre confirmado (a 204 é `gestao_custo_pai.categoria_fluxo_caixa_id`). Idempotente, padrão do repo: `ADD COLUMN IF NOT EXISTS`.
- **Helper de parcelas:** `_vencimentos(data_compra, condicao, parcelas, ...)`. `condicao='a_vista'` → 1 parcela; `condicao='parcelado'` + `parcelas=N` → N parcelas. Cada parcela vira um `GestaoCustoPai`+`GestaoCustoFilho`.
- Suíte de regressão (rodar após cada task):
  ```
  python -m pytest tests/test_cronograma_fisico_financeiro.py tests/test_painel_financeiro.py tests/test_importacao_fisico_financeiro.py -q
  ```

---

## File Structure

| Arquivo | Responsabilidade | Mudança |
|---|---|---|
| `models.py` (`PedidoCompra`, ~l.4718-4760) | ORM do pedido de compra | **Modificar** — `obra_servico_custo_id` + relationship |
| `migrations.py` (registry ~l.4004; defs ~l.13740) | Schema | **Modificar** — `_migration_205_pedido_compra_obra_servico_custo` |
| `compras_views.py` (`nova_post` l.529; `processar_compra_normal` l.162; `processar_compra_aprovada_cliente` l.274) | Criação da compra | **Modificar** — ler/validar/gravar `obra_servico_custo_id`; repassar aos `GestaoCustoFilho` |
| `views/obras.py` (perto das rotas de etapa ~l.2304) | Endpoint | **Adicionar** — `GET /obras/<id>/etapas-custo` |
| `services/cronograma_fisico_financeiro.py` (`lancamentos_da_etapa` ~l.600) | Serviço da etapa | **Modificar** — `origem_label` `pedido_compra`→`Compra` |
| `templates/compras/nova_compra.html` (bloco Obra ~l.100-115; JS ~l.388) | Markup + UI | **Modificar** — select Etapa + cascata |
| `tests/test_painel_financeiro.py` | Testes | **Modificar** — novos testes |

---

## Task 1: Modelo + migração 205 (`pedido_compra.obra_servico_custo_id`)

**Files:**
- Modify: `models.py` (`PedidoCompra`, ~l.4727 e ~l.4757)
- Modify: `migrations.py` (registry ~l.4004; nova função ~l.13740)
- Test: `tests/test_painel_financeiro.py`

**Interfaces:**
- Produces: `PedidoCompra.obra_servico_custo_id` (Integer FK nullable → `obra_servico_custo.id`) e o relationship `PedidoCompra.obra_servico_custo`.

- [ ] **Step 1: Write the failing test**

Adicionar a `tests/test_painel_financeiro.py`:

```python
@pytest.mark.integration
def test_pedido_compra_tem_obra_servico_custo_id():
    from models import PedidoCompra
    cols = {c.name for c in PedidoCompra.__table__.columns}
    assert 'obra_servico_custo_id' in cols
```

- [ ] **Step 2: Run it — expect FAIL**

Run: `python -m pytest tests/test_painel_financeiro.py::test_pedido_compra_tem_obra_servico_custo_id -v`
Expected: FAIL (coluna ausente no modelo).

- [ ] **Step 3: Adicionar a coluna no modelo**

Em `models.py`, na classe `PedidoCompra`, logo após a linha `obra_id = db.Column(db.Integer, db.ForeignKey('obra.id'), nullable=True)`:

```python
    # Etapa (centro de custo) à qual a compra se amarra — opcional. Quando definida,
    # os GestaoCustoFilho gerados entram no Realizado dessa etapa
    # (spec 2026-06-29-compras-campo-etapa-design).
    obra_servico_custo_id = db.Column(
        db.Integer, db.ForeignKey('obra_servico_custo.id'), nullable=True)
```

- [ ] **Step 4: Adicionar o relationship**

Em `models.py`, na mesma classe, logo após a linha `obra = db.relationship('Obra', backref='pedidos_compra', foreign_keys=[obra_id])`:

```python
    obra_servico_custo = db.relationship(
        'ObraServicoCusto', foreign_keys=[obra_servico_custo_id])
```

- [ ] **Step 5: Adicionar a migração 205**

Em `migrations.py`, após a função `_migration_204_gestao_custo_pai_categoria_fc`:

```python
def _migration_205_pedido_compra_obra_servico_custo():
    """Compras por etapa — adiciona pedido_compra.obra_servico_custo_id (FK p/
    obra_servico_custo). Idempotente. Ver spec 2026-06-29-compras-campo-etapa-design."""
    from sqlalchemy import text as sa_text
    try:
        with db.engine.begin() as conn:
            conn.execute(sa_text(
                "ALTER TABLE pedido_compra "
                "ADD COLUMN IF NOT EXISTS obra_servico_custo_id INTEGER "
                "REFERENCES obra_servico_custo(id)"))
        logger.info("[Migration 205] pedido_compra.obra_servico_custo_id adicionada.")
    except Exception as e:
        logger.error(f"[Migration 205] Falha: {e}", exc_info=True)
        raise
```

- [ ] **Step 6: Registrar a migração**

Em `migrations.py`, na lista `migrations_to_run`, após a linha da 204:

```python
            (205, "Compras por etapa — pedido_compra.obra_servico_custo_id", _migration_205_pedido_compra_obra_servico_custo),
```

- [ ] **Step 7: Run it — expect PASS + suíte**

Run: `python -m pytest tests/test_painel_financeiro.py::test_pedido_compra_tem_obra_servico_custo_id -v`
Expected: PASS.
Run: `python -m pytest tests/test_cronograma_fisico_financeiro.py tests/test_painel_financeiro.py tests/test_importacao_fisico_financeiro.py -q`
Expected: verde.

- [ ] **Step 8: Commit**

```bash
git add models.py migrations.py tests/test_painel_financeiro.py
git commit -m "feat(baia): coluna pedido_compra.obra_servico_custo_id (migração 205)"
```

---

## Task 2: Compra amarra a etapa nos lançamentos de custo (`processar_compra_normal` + aprovada_cliente)

**Files:**
- Modify: `compras_views.py` (`processar_compra_normal`, gcf ~l.215-224; `processar_compra_aprovada_cliente`, seu `GestaoCustoFilho`)
- Test: `tests/test_painel_financeiro.py`

**Interfaces:**
- Consumes: `PedidoCompra.obra_servico_custo_id` (Task 1); `realizado_por_etapa(obra)` (existente).
- Produces: cada `GestaoCustoFilho` criado por uma compra leva `obra_servico_custo_id=pedido.obra_servico_custo_id` → conta no realizado da etapa (compra normal).

- [ ] **Step 1: Write the failing test**

Adicionar a `tests/test_painel_financeiro.py`:

```python
@pytest.mark.integration
def test_processar_compra_normal_amarra_etapa():
    from services.importacao_fisico_financeiro import importar_fisico_financeiro
    from services.cronograma_fisico_financeiro import realizado_por_etapa
    from compras_views import processar_compra_normal
    from models import (Obra, ObraServicoCusto, Fornecedor, PedidoCompra,
                        PedidoCompraItem, GestaoCustoFilho)
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
        forn = Fornecedor(nome='Forn Teste', admin_id=aid, ativo=True)
        db.session.add(forn); db.session.flush()
        ped = PedidoCompra(
            numero='PC-TST', fornecedor_id=forn.id, data_compra=date(2026, 6, 10),
            obra_id=oid, obra_servico_custo_id=osc.id, condicao_pagamento='parcelado',
            parcelas=2, valor_total=Decimal('1000.00'), tipo_compra='normal',
            processada_apos_aprovacao=False, admin_id=aid)
        db.session.add(ped); db.session.flush()
        item = PedidoCompraItem(
            pedido_id=ped.id, almoxarifado_item_id=None, descricao='Cimento',
            quantidade=Decimal('1'), preco_unitario=Decimal('1000'),
            subtotal=Decimal('1000'), admin_id=aid)
        db.session.add(item); db.session.flush()
        itens = [('Cimento', 1.0, 1000.0, None, 1000.0)]
        processar_compra_normal(ped, itens, aid, aid)
        db.session.commit()
        filhos = GestaoCustoFilho.query.filter_by(
            origem_tabela='pedido_compra', origem_id=ped.id).all()
        assert len(filhos) == 2  # parcelado → 2 parcelas
        assert all(f.obra_servico_custo_id == osc.id for f in filhos)
        # realizado da etapa soma a compra inteira
        assert float(realizado_por_etapa(obra).get(osc.id, 0)) >= 1000 - 1
```

- [ ] **Step 2: Run it — expect FAIL**

Run: `python -m pytest tests/test_painel_financeiro.py::test_processar_compra_normal_amarra_etapa -v`
Expected: FAIL — os `GestaoCustoFilho` têm `obra_servico_custo_id is None`, então `realizado_por_etapa` não soma e/ou o assert de vínculo falha.

- [ ] **Step 3: Passar a etapa no `GestaoCustoFilho` de `processar_compra_normal`**

Em `compras_views.py`, dentro de `processar_compra_normal`, no construtor `gcf = GestaoCustoFilho(...)` (l.215-224), adicionar `obra_servico_custo_id=pedido.obra_servico_custo_id` (logo após `obra_id=pedido.obra_id,`):

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
```

- [ ] **Step 4: Passar a etapa também em `processar_compra_aprovada_cliente`**

Em `compras_views.py`, dentro de `processar_compra_aprovada_cliente`, localizar o único `GestaoCustoFilho(...)` (após o `gcp` FATURAMENTO_DIRETO) e adicionar a mesma linha `obra_servico_custo_id=pedido.obra_servico_custo_id,` (logo após `obra_id=pedido.obra_id,`). É só rastreabilidade — FATURAMENTO_DIRETO é excluído do realizado.

- [ ] **Step 5: Run it — expect PASS + suíte**

Run: `python -m pytest tests/test_painel_financeiro.py::test_processar_compra_normal_amarra_etapa -v`
Expected: PASS.
Run: `python -m pytest tests/test_cronograma_fisico_financeiro.py tests/test_painel_financeiro.py tests/test_importacao_fisico_financeiro.py -q`
Expected: verde.

- [ ] **Step 6: Rodar os testes de compras existentes (não-regressão)**

Run: `python -m pytest tests/test_compras_tipo.py -q`
Expected: verde (compras sem etapa passam `None`, comportamento preservado).

- [ ] **Step 7: Commit**

```bash
git add compras_views.py tests/test_painel_financeiro.py
git commit -m "feat(baia): compra amarra a etapa nos GestaoCustoFilho (entra no realizado)"
```

---

## Task 3: `lancamentos_da_etapa` rotula a origem `pedido_compra` como "Compra"

**Files:**
- Modify: `services/cronograma_fisico_financeiro.py` (`lancamentos_da_etapa`, ~l.600-622)
- Test: `tests/test_painel_financeiro.py`

**Interfaces:**
- Produces: em `lancamentos_da_etapa`, item com `origem='pedido_compra'` recebe `origem_label='Compra'` e `editavel=False` (só `lancamento_periodo_manual` é editável). `lancamento_periodo_manual` segue `origem_label='Manual'`.

- [ ] **Step 1: Write the failing test**

Adicionar a `tests/test_painel_financeiro.py`:

```python
@pytest.mark.integration
def test_lancamentos_da_etapa_rotula_compra():
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
        pai = GestaoCustoPai(admin_id=aid, tipo_categoria='MATERIAL',
                             entidade_nome='Fornecedor X', valor_total=Decimal('300'),
                             status='PENDENTE')
        db.session.add(pai); db.session.flush()
        db.session.add(GestaoCustoFilho(
            pai_id=pai.id, admin_id=aid, obra_id=oid, obra_servico_custo_id=osc.id,
            data_referencia=date(2026, 6, 10), descricao='Compra cimento',
            valor=Decimal('300'), origem_tabela='pedido_compra', origem_id=1))
        db.session.commit()
        out = lancamentos_da_etapa(obra, osc.id)
        l = next(x for x in out if x['descricao'] == 'Compra cimento')
        assert l['origem_label'] == 'Compra'
        assert l['editavel'] is False
```

- [ ] **Step 2: Run it — expect FAIL**

Run: `python -m pytest tests/test_painel_financeiro.py::test_lancamentos_da_etapa_rotula_compra -v`
Expected: FAIL — `origem_label` vem como `'pedido_compra'` (string crua), não `'Compra'`.

- [ ] **Step 3: Mapear o rótulo de origem**

Em `services/cronograma_fisico_financeiro.py`, imediatamente antes de `def lancamentos_da_etapa(`, adicionar a constante:

```python
_ORIGEM_LABELS = {'lancamento_periodo_manual': 'Manual', 'pedido_compra': 'Compra'}
```

E dentro do laço de `lancamentos_da_etapa`, trocar a linha do `origem_label`:

```python
            "origem_label": _ORIGEM_LABELS.get(origem, (origem or "Sistema")),
```

(O `editavel` continua `origem == 'lancamento_periodo_manual'`, então a compra fica só leitura.)

- [ ] **Step 4: Run it — expect PASS**

Run: `python -m pytest tests/test_painel_financeiro.py::test_lancamentos_da_etapa_rotula_compra -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add services/cronograma_fisico_financeiro.py tests/test_painel_financeiro.py
git commit -m "feat(baia): aba Realizado rotula lançamento de compra como 'Compra'"
```

---

## Task 4: Endpoint `GET /obras/<id>/etapas-custo`

**Files:**
- Modify: `views/obras.py` (nova rota, após as rotas `.../lancamentos`, ~l.2304)
- Test: `tests/test_painel_financeiro.py`

**Interfaces:**
- Produces: `GET /obras/<id>/etapas-custo` → `{"etapas": [{"id": int, "nome": str}, …]}` das `ObraServicoCusto` da obra (tenant-scoped, ordenadas por `id`). 404 se a obra não for do tenant.

- [ ] **Step 1: Write the failing test**

```python
@pytest.mark.integration
def test_endpoint_etapas_custo():
    from services.importacao_fisico_financeiro import importar_fisico_financeiro
    from models import Usuario, ObraServicoCusto
    import json, os
    app.config['WTF_CSRF_ENABLED'] = False
    with app.app_context():
        aid = _novo_admin()
        u = Usuario.query.get(aid); u.versao_sistema = 'v2'; db.session.commit()
        caminho = os.path.join(os.path.dirname(__file__), 'fixtures',
                               'cronograma_fisico_financeiro_baias.json')
        oid = importar_fisico_financeiro(json.load(open(caminho, encoding='utf-8')), aid)['obra_id']
        n = ObraServicoCusto.query.filter_by(obra_id=oid, admin_id=aid).count()
        outro = _novo_admin()
    with app.test_client() as c:
        with c.session_transaction() as s:
            s['_user_id'] = str(aid); s['_fresh'] = True
        r = c.get(f'/obras/{oid}/etapas-custo')
        assert r.status_code == 200
        body = r.get_json()
        assert len(body['etapas']) == n and n > 0
        assert {'id', 'nome'} <= set(body['etapas'][0].keys())
    # obra de outro admin → 404
    with app.test_client() as c:
        with c.session_transaction() as s:
            s['_user_id'] = str(outro); s['_fresh'] = True
        assert c.get(f'/obras/{oid}/etapas-custo').status_code == 404
```

- [ ] **Step 2: Run it — expect FAIL**

Run: `python -m pytest tests/test_painel_financeiro.py::test_endpoint_etapas_custo -v`
Expected: FAIL — rota inexistente (404 nos dois casos).

- [ ] **Step 3: Implementar a rota**

Em `views/obras.py`, após a função `financeiro_etapa_lancamento_editar` (~l.2304):

```python
@main_bp.route('/obras/<int:id>/etapas-custo', methods=['GET'])
@login_required
@capture_db_errors
def obra_etapas_custo(id):
    from models import ObraServicoCusto
    admin_id = get_tenant_admin_id()
    obra = Obra.query.filter_by(id=id, admin_id=admin_id).first_or_404()
    rows = (ObraServicoCusto.query
            .filter_by(obra_id=obra.id, admin_id=admin_id)
            .order_by(ObraServicoCusto.id).all())
    return jsonify({'etapas': [{'id': o.id, 'nome': o.nome} for o in rows]})
```

- [ ] **Step 4: Run it — expect PASS**

Run: `python -m pytest tests/test_painel_financeiro.py::test_endpoint_etapas_custo -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add views/obras.py tests/test_painel_financeiro.py
git commit -m "feat(baia): GET /obras/<id>/etapas-custo (etapas para o select de compra)"
```

---

## Task 5: `POST /compras/nova` lê, valida e grava `obra_servico_custo_id`

**Files:**
- Modify: `compras_views.py` (`nova_post`, após o bloco de validação da obra ~l.593; construtor do `PedidoCompra` ~l.655-672)
- Test: `tests/test_painel_financeiro.py`

**Interfaces:**
- Consumes: `PedidoCompra.obra_servico_custo_id` (Task 1); `processar_compra_normal` que repassa a etapa (Task 2).
- Produces: `POST /compras/nova` com `obra_servico_custo_id` no form → grava no `PedidoCompra` (se pertencer à obra+tenant; senão `None`). Os `GestaoCustoFilho` herdam a etapa.

- [ ] **Step 1: Write the failing test**

```python
@pytest.mark.integration
def test_post_nova_compra_grava_etapa():
    from services.importacao_fisico_financeiro import importar_fisico_financeiro
    from models import Usuario, ObraServicoCusto, Fornecedor, PedidoCompra, GestaoCustoFilho
    import json, os
    app.config['WTF_CSRF_ENABLED'] = False
    with app.app_context():
        aid = _novo_admin()
        u = Usuario.query.get(aid); u.versao_sistema = 'v2'
        caminho = os.path.join(os.path.dirname(__file__), 'fixtures',
                               'cronograma_fisico_financeiro_baias.json')
        oid = importar_fisico_financeiro(json.load(open(caminho, encoding='utf-8')), aid)['obra_id']
        osc_id = ObraServicoCusto.query.filter_by(obra_id=oid, admin_id=aid).first().id
        forn = Fornecedor(nome='Forn POST', admin_id=aid, ativo=True)
        db.session.add(forn); db.session.commit()
        forn_id = forn.id
    with app.test_client() as c:
        with c.session_transaction() as s:
            s['_user_id'] = str(aid); s['_fresh'] = True
        data = {
            'fornecedor_id': str(forn_id), 'data_compra': '2026-06-10',
            'condicao_pagamento': 'a_vista', 'parcelas': '1',
            'obra_id': str(oid), 'obra_servico_custo_id': str(osc_id),
            'tipo_compra': 'normal',
            'item_descricao[]': 'Cimento', 'item_quantidade[]': '1',
            'item_preco[]': '100', 'item_almoxarifado_id[]': '',
        }
        r = c.post('/compras/nova', data=data)
        assert r.status_code in (200, 302)
        # etapa inválida (não pertence à obra) → gravada como None
        data2 = dict(data); data2['obra_servico_custo_id'] = '999999'
        data2['item_descricao[]'] = 'Areia'
        r2 = c.post('/compras/nova', data=data2)
        assert r2.status_code in (200, 302)
    with app.app_context():
        ped = PedidoCompra.query.filter_by(admin_id=aid, numero=None,
                                           obra_id=oid).order_by(PedidoCompra.id).all()
        # primeiro pedido: etapa válida; segundo: None
        p_ok = next(p for p in ped if p.obra_servico_custo_id == osc_id)
        assert p_ok is not None
        f = GestaoCustoFilho.query.filter_by(
            origem_tabela='pedido_compra', origem_id=p_ok.id).first()
        assert f.obra_servico_custo_id == osc_id
        p_invalida = next(p for p in ped if p.id != p_ok.id)
        assert p_invalida.obra_servico_custo_id is None
```

- [ ] **Step 2: Run it — expect FAIL**

Run: `python -m pytest tests/test_painel_financeiro.py::test_post_nova_compra_grava_etapa -v`
Expected: FAIL — o POST ignora `obra_servico_custo_id`; ambos os pedidos ficam com `None`, então `next(p for p in ped if p.obra_servico_custo_id == osc_id)` levanta `StopIteration`.

- [ ] **Step 3: Ler e validar a etapa no POST**

Em `compras_views.py`, em `nova_post`, logo após o bloco de validação da obra (que termina com o `if not obra_owner: ... return redirect(...)`, ~l.593), adicionar:

```python
        # Etapa (ObraServicoCusto) opcional — só vale com obra; valida obra+tenant.
        osc_id = request.form.get('obra_servico_custo_id') or None
        if osc_id and obra_id:
            try:
                osc_id = int(osc_id)
            except (TypeError, ValueError):
                osc_id = None
            if osc_id:
                from models import ObraServicoCusto as _OSC
                if not _OSC.query.filter_by(
                        id=osc_id, obra_id=obra_id, admin_id=admin_id).first():
                    osc_id = None
        else:
            osc_id = None
```

- [ ] **Step 4: Gravar a etapa no `PedidoCompra`**

Em `compras_views.py`, no construtor `pedido = PedidoCompra(...)` (l.655-672), adicionar a linha `obra_servico_custo_id=osc_id,` (logo após `obra_id=obra_id,`):

```python
        pedido = PedidoCompra(
            numero=numero,
            fornecedor_id=fornecedor_id,
            data_compra=data_compra,
            obra_id=obra_id,
            obra_servico_custo_id=osc_id,
            condicao_pagamento=condicao,
            parcelas=parcelas,
            valor_total=valor_total,
            observacoes=observacoes,
            anexo_url=anexo_url,
            tipo_compra=tipo_compra,
            processada_apos_aprovacao=False,
            status_aprovacao_cliente='AGUARDANDO_APROVACAO_CLIENTE' if tipo_compra == 'aprovacao_cliente' else None,
            admin_id=admin_id,
            responsavel_id=responsavel_id,
            data_vencimento_primeira_parcela=data_primeira_parcela,
            intervalo_parcelas_dias=intervalo_parcelas_dias,
        )
```

- [ ] **Step 5: Run it — expect PASS + suíte**

Run: `python -m pytest tests/test_painel_financeiro.py::test_post_nova_compra_grava_etapa -v`
Expected: PASS.
Run: `python -m pytest tests/test_cronograma_fisico_financeiro.py tests/test_painel_financeiro.py tests/test_importacao_fisico_financeiro.py tests/test_compras_tipo.py -q`
Expected: verde.

- [ ] **Step 6: Commit**

```bash
git add compras_views.py tests/test_painel_financeiro.py
git commit -m "feat(baia): POST /compras/nova grava obra_servico_custo_id (valida obra/tenant)"
```

---

## Task 6: UI — select Etapa em cascata no Nova Compra

**Files:**
- Modify: `templates/compras/nova_compra.html` (bloco da Obra ~l.100-115; bloco de scripts ~l.388)

**Interfaces:**
- Consumes: `GET /obras/<id>/etapas-custo` (Task 4); o `<select name="obra_id" id="obraSelect">` existente.
- Produces: `<select name="obra_servico_custo_id" id="oscSelect">` populado em cascata; enviado no POST.

- [ ] **Step 1: Adicionar o select de Etapa no markup**

Em `templates/compras/nova_compra.html`, imediatamente após o `</div>` que fecha o bloco da Obra (o `<div class="col-md-12">` que contém `#obraSelect`, ~l.115), inserir:

```html
              <div class="col-md-12">
                <label class="form-label fw-semibold">
                  Etapa <small class="text-muted ms-1">(opcional)</small>
                </label>
                <select name="obra_servico_custo_id" id="oscSelect" class="form-select" disabled>
                  <option value="">— Sem etapa —</option>
                </select>
                <div class="form-text"><i class="fas fa-info-circle me-1"></i>Amarra o custo desta compra a uma etapa da obra (entra no Realizado dela). Selecione a Obra primeiro.</div>
              </div>
```

- [ ] **Step 2: Adicionar o JS da cascata**

Em `templates/compras/nova_compra.html`, dentro do bloco `<script>` principal (perto do final, logo após `atualizarTipoCompra();` ~l.388 — antes do fechamento do bloco/`</script>` em que ele está), inserir:

```javascript
// ── ETAPA (cascata com a Obra) ────────────────────────────────
(function () {
  var oscSel = document.getElementById('oscSelect');
  var obraSel = document.getElementById('obraSelect');
  if (!oscSel || !obraSel) return;
  function carregarEtapas(obraId) {
    oscSel.innerHTML = '<option value="">— Sem etapa —</option>';
    if (!obraId) { oscSel.disabled = true; return; }
    fetch('/obras/' + obraId + '/etapas-custo', { headers: { 'X-Requested-With': 'XMLHttpRequest' } })
      .then(function (r) { if (!r.ok) throw new Error(r.status); return r.json(); })
      .then(function (d) {
        (d.etapas || []).forEach(function (e) {
          var o = document.createElement('option');
          o.value = e.id; o.textContent = e.nome;
          oscSel.appendChild(o);
        });
        oscSel.disabled = false;
      })
      .catch(function () { oscSel.disabled = true; });
  }
  // select2 dispara o evento via jQuery; ouvir os dois p/ robustez
  obraSel.addEventListener('change', function () { carregarEtapas(obraSel.value); });
  if (window.jQuery) {
    window.jQuery(obraSel).on('change', function () { carregarEtapas(obraSel.value); });
  }
  // estado inicial (caso a obra já venha selecionada)
  carregarEtapas(obraSel.value);
})();
```

- [ ] **Step 3: Verificar que o template renderiza (sem erro de sintaxe Jinja)**

Run: `python -c "from app import app; c=app.test_client(); import flask; print('template import ok')"`
Expected: `template import ok` (importar a app não levanta erro; o template é compilado sob demanda — a verificação real é visual no Step 4).

- [ ] **Step 4: Verificação visual (browser real)**

Subir a app (`gunicorn --bind 0.0.0.0:5000 --reuse-port --reload main:app`) e, com o chromium do Nix
(`$REPLIT_PLAYWRIGHT_CHROMIUM_EXECUTABLE`) via Playwright, logar (`admin@construtoraalfa.com.br` /
`Alfa@2026`), abrir **Compras → Nova Compra**. Conferir:
1. Ao escolher uma **Obra** que tenha etapas, o select **Etapa** habilita e lista as etapas daquela obra.
2. Trocar/limpar a Obra atualiza/limpa o select Etapa.
3. Registrar uma compra **normal** com Obra + Etapa + 1 item.
4. Abrir a obra → Financeiro → a etapa escolhida → aba **Realizado — lançamentos**: a compra aparece com badge **"Compra"** (só leitura) e soma no Realizado da etapa.

- [ ] **Step 5: Commit**

```bash
git add templates/compras/nova_compra.html
git commit -m "feat(baia): select Etapa em cascata no formulário de Nova Compra"
```

---

## Task 7: Fechamento — compra no realizado ponta-a-ponta + suíte

**Files:**
- Test: `tests/test_painel_financeiro.py`

- [ ] **Step 1: Teste ponta-a-ponta (POST compra → realizado da etapa no painel)**

```python
@pytest.mark.integration
def test_compra_com_etapa_entra_no_painel_realizado():
    from services.importacao_fisico_financeiro import importar_fisico_financeiro
    from services.cronograma_fisico_financeiro import painel_financeiro
    from models import Usuario, Obra, ObraServicoCusto, Fornecedor
    import json, os
    app.config['WTF_CSRF_ENABLED'] = False
    with app.app_context():
        aid = _novo_admin()
        u = Usuario.query.get(aid); u.versao_sistema = 'v2'
        caminho = os.path.join(os.path.dirname(__file__), 'fixtures',
                               'cronograma_fisico_financeiro_baias.json')
        oid = importar_fisico_financeiro(json.load(open(caminho, encoding='utf-8')), aid)['obra_id']
        osc_id = ObraServicoCusto.query.filter_by(obra_id=oid, admin_id=aid).first().id
        forn = Fornecedor(nome='Forn E2E', admin_id=aid, ativo=True)
        db.session.add(forn); db.session.commit()
        forn_id = forn.id
    with app.test_client() as c:
        with c.session_transaction() as s:
            s['_user_id'] = str(aid); s['_fresh'] = True
        c.post('/compras/nova', data={
            'fornecedor_id': str(forn_id), 'data_compra': '2026-06-10',
            'condicao_pagamento': 'a_vista', 'parcelas': '1',
            'obra_id': str(oid), 'obra_servico_custo_id': str(osc_id),
            'tipo_compra': 'normal',
            'item_descricao[]': 'Cimento', 'item_quantidade[]': '1',
            'item_preco[]': '750', 'item_almoxarifado_id[]': '',
        })
    with app.app_context():
        p = painel_financeiro(Obra.query.get(oid))
        et = next(e for e in p['etapas'] if e['osc_id'] == osc_id)
        assert float(et['realizado']) >= 750 - 1
```

- [ ] **Step 2: Rodar + invariantes**

Run: `python -m pytest tests/test_painel_financeiro.py::test_compra_com_etapa_entra_no_painel_realizado -v`
Expected: PASS.
Run: `python -m pytest tests/test_cronograma_fisico_financeiro.py tests/test_painel_financeiro.py tests/test_importacao_fisico_financeiro.py tests/test_compras_tipo.py -q`
Expected: verde; invariantes da Baia (veks 800.960 / fat 550.775 / lucro 24.976 / imposto 128.903) preservados.

- [ ] **Step 3: Suíte inteira (não-browser)**

Run: `python -m pytest -q --ignore=scripts --ignore=archive -k "not playwright and not browser"`
Expected: sem regressões fora do escopo (falhas pré-existentes são Playwright/ambiente e os 2 erros de coleta em `scripts/`/`archive/`).

- [ ] **Step 4: Commit**

```bash
git add tests/test_painel_financeiro.py
git commit -m "test(baia): compra com etapa entra no realizado da etapa (ponta-a-ponta)"
```

---

## Sequência de dependências

```
T1 (coluna + migração) → T2 (processar passa etapa) → T5 (POST grava) → T7 (fechamento)
T1 → T4 (endpoint)
T2 → T3 (rótulo) [T3 também pode rodar após T1, monta o filho direto]
T4 → T6 (UI cascata)
T2, T5 → T7
```

## Rollback
Cada task é um commit isolado. Reverter T6 mantém o backend (T1-T5) estável. A migração 205 é idempotente (`ADD COLUMN IF NOT EXISTS`) e a coluna é nullable — reverter o modelo deixa a coluna órfã sem quebrar.

---

## Self-Review

**1. Spec coverage**

| Requisito da spec | Task |
|---|---|
| `PedidoCompra.obra_servico_custo_id` + relationship | T1 |
| Migração 205 idempotente | T1 |
| `processar_compra_normal` repassa a etapa ao(s) `GestaoCustoFilho` | T2 |
| Compra parcelada → todas as parcelas com a etapa | T2 (assert `len==2` + `all(...)`) |
| `processar_compra_aprovada_cliente` (rastreabilidade; excluído do realizado) | T2 (Step 4) |
| Realizado da etapa soma a compra | T2 (`realizado_por_etapa`), T7 (`painel_financeiro`) |
| `origem_label` `pedido_compra`→`Compra`, só leitura | T3 |
| Endpoint `GET /obras/<id>/etapas-custo` (multitenant 404) | T4 |
| `POST /compras/nova` grava a etapa; etapa inválida → `None` | T5 |
| Etapa opcional / sem etapa preserva comportamento | T5 (caso None), T2/test_compras_tipo (não-regressão) |
| UI: select Etapa em cascata | T6 |
| Invariantes da Baia; suíte verde | T2, T5, T7 |

**2. Placeholder scan** — sem TBD/TODO; cada step de código mostra o código completo; comandos com expected output. A verificação de UI (cascata + compra no realizado) é manual no browser real (T6 Step 4), mesmo padrão das fases de UI viva dos planos anteriores.

**3. Type consistency** —
- `PedidoCompra.obra_servico_custo_id` (T1) é lido em T2 (`pedido.obra_servico_custo_id`) e gravado em T5 (`obra_servico_custo_id=osc_id`).
- Endpoint retorna `{"etapas": [{"id","nome"}]}` (T4), consumido pelo JS de T6 (`d.etapas`, `e.id`, `e.nome`).
- `_ORIGEM_LABELS` (T3) mapeia as mesmas strings de origem usadas por T2 (`'pedido_compra'`) e pelo Pedaço 1 (`'lancamento_periodo_manual'`).
- `realizado_por_etapa(obra) -> {osc_id: Decimal}` e `painel_financeiro` (etapa com `osc_id`/`realizado`) usados consistentemente em T2/T7.
</content>
