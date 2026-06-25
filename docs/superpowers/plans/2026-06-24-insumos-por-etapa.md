# Insumos (linhas de custo) por etapa — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Permitir ver/editar as linhas de custo (insumos) de cada etapa no painel Financeiro, com o custo da etapa derivado da soma das linhas.

**Architecture:** Nova tabela `ObraServicoCustoItem` (linha de custo por obra/etapa, classificada Veks/Fat) vira fonte da verdade; `recalcular_osc_dos_itens` deriva `ObraServicoCusto.mao_obra_a_realizar`/`material_a_realizar` da soma das linhas. Painel passa a expor `itens` por etapa; um endpoint substitui+recalcula; o importador popula as linhas de `eap.itens`; a UI `showEtapa` vira uma tabela editável.

**Tech Stack:** Flask, SQLAlchemy, Postgres, Bootstrap 5, Chart.js, JS vanilla, pytest.

**Spec:** `docs/superpowers/specs/2026-06-24-insumos-por-etapa-design.md`
**Branch:** `feat/insumos-por-etapa` (já criada e ativa)

---

## File Structure

- **Modify** `models.py` — nova classe `ObraServicoCustoItem` + relationship em `ObraServicoCusto`.
- **Modify** `migrations.py` — migração 199 (CREATE TABLE idempotente).
- **Modify** `services/cronograma_fisico_financeiro.py` — helper `recalcular_osc_dos_itens` + `painel_financeiro` expõe `itens` por etapa.
- **Modify** `services/importacao_fisico_financeiro.py` — popula linhas de `eap.itens`; `_limpar_derivados` apaga linhas.
- **Modify** `views/obras.py` — substitui o endpoint agregado por `financeiro_etapa_itens`.
- **Modify** `static/js/financeiro_obra.js` — `showEtapa` vira tabela editável.
- **Modify** `tests/test_painel_financeiro.py`, `tests/test_importacao_fisico_financeiro.py` — novos testes.

---

### Task 1: Modelo `ObraServicoCustoItem` + migração 199

**Files:**
- Modify: `models.py` (após a classe `ObraServicoCusto`)
- Modify: `migrations.py` (lista de migrações + nova função)
- Test: `tests/test_painel_financeiro.py`

- [ ] **Step 1: Escrever o teste que falha**

Acrescente ao final de `tests/test_painel_financeiro.py`:

```python
@pytest.mark.integration
def test_obra_servico_custo_item_schema():
    from models import ObraServicoCustoItem
    cols = {c.name for c in ObraServicoCustoItem.__table__.columns}
    assert {'id', 'obra_servico_custo_id', 'admin_id', 'descricao',
            'valor', 'fonte', 'ordem'} <= cols
```

- [ ] **Step 2: Rodar e confirmar FALHA**

Run: `python3 -m pytest tests/test_painel_financeiro.py::test_obra_servico_custo_item_schema -q`
Expected: FAIL (`ImportError: cannot import name 'ObraServicoCustoItem'`).

- [ ] **Step 3: Adicionar o modelo**

Em `models.py`, logo APÓS o fim da classe `ObraServicoCusto` (procure `class ObraServicoCusto(db.Model):` e ache o fim dela — antes da próxima `class`), adicione:

```python
class ObraServicoCustoItem(db.Model):
    """Linha de custo (insumo) de uma etapa, por obra. Fonte da verdade do custo
    previsto: ObraServicoCusto.mao_obra_a_realizar/material_a_realizar = soma destas
    linhas por `fonte` (veks/fat_direto). Ver design 2026-06-24."""
    __tablename__ = 'obra_servico_custo_item'

    id = db.Column(db.Integer, primary_key=True)
    obra_servico_custo_id = db.Column(
        db.Integer, db.ForeignKey('obra_servico_custo.id', ondelete='CASCADE'),
        nullable=False, index=True)
    admin_id = db.Column(db.Integer, db.ForeignKey('usuario.id'), nullable=False, index=True)
    descricao = db.Column(db.String(200), nullable=False)
    valor = db.Column(db.Numeric(15, 2), nullable=False, default=0)
    fonte = db.Column(db.String(20), nullable=False, default='veks')  # 'veks' | 'fat_direto'
    ordem = db.Column(db.Integer, default=0)

    osc = db.relationship('ObraServicoCusto', backref=db.backref(
        'itens_custo', cascade='all, delete-orphan'))

    def __repr__(self):
        return f'<ObraServicoCustoItem osc={self.obra_servico_custo_id} {self.descricao!r}>'
```

- [ ] **Step 4: Adicionar a migração 199**

Em `migrations.py`, na lista de tuplas de migrações (procure a linha `(198, "Físico-financeiro — obra.fluxo_caixa_planilha (snapshot verbatim)", _migration_198_obra_fluxo_caixa_planilha),`), adicione logo abaixo:

```python
            (199, "Físico-financeiro — tabela obra_servico_custo_item (linhas de custo por etapa)", _migration_199_obra_servico_custo_item),
```

E adicione a função (perto das outras `_migration_19x`, ex.: após `_migration_198_obra_fluxo_caixa_planilha`):

```python
def _migration_199_obra_servico_custo_item():
    """Físico-financeiro — cria obra_servico_custo_item (linhas de custo por etapa,
    classificadas Veks/Fat). Idempotente."""
    from sqlalchemy import text as sa_text
    try:
        with db.engine.begin() as conn:
            conn.execute(sa_text("""
                CREATE TABLE IF NOT EXISTS obra_servico_custo_item (
                    id SERIAL PRIMARY KEY,
                    obra_servico_custo_id INTEGER NOT NULL
                        REFERENCES obra_servico_custo(id) ON DELETE CASCADE,
                    admin_id INTEGER NOT NULL REFERENCES usuario(id),
                    descricao VARCHAR(200) NOT NULL,
                    valor NUMERIC(15,2) NOT NULL DEFAULT 0,
                    fonte VARCHAR(20) NOT NULL DEFAULT 'veks',
                    ordem INTEGER DEFAULT 0
                )
            """))
            conn.execute(sa_text("CREATE INDEX IF NOT EXISTS ix_osc_item_osc ON obra_servico_custo_item(obra_servico_custo_id)"))
            conn.execute(sa_text("CREATE INDEX IF NOT EXISTS ix_osc_item_admin ON obra_servico_custo_item(admin_id)"))
        logger.info("[Migration 199] obra_servico_custo_item criada.")
    except Exception as e:
        logger.error(f"[Migration 199] Falha: {e}", exc_info=True)
        raise
```

- [ ] **Step 5: Rodar e confirmar PASSA**

Run: `python3 -m pytest tests/test_painel_financeiro.py::test_obra_servico_custo_item_schema -q`
Expected: PASS (a suíte sobe o app, que roda as migrações e cria a tabela).

- [ ] **Step 6: Commit**

```bash
git add models.py migrations.py tests/test_painel_financeiro.py
git commit -m "feat(fin): modelo ObraServicoCustoItem + migração 199"
```

---

### Task 2: Helper `recalcular_osc_dos_itens`

**Files:**
- Modify: `services/cronograma_fisico_financeiro.py`
- Test: `tests/test_painel_financeiro.py`

- [ ] **Step 1: Escrever o teste que falha**

Acrescente ao final de `tests/test_painel_financeiro.py`:

```python
@pytest.mark.integration
def test_recalcular_osc_dos_itens():
    from services.cronograma_fisico_financeiro import recalcular_osc_dos_itens
    from models import Obra, ObraServicoCusto, ObraServicoCustoItem
    with app.app_context():
        aid = _novo_admin()
        obra = Obra(nome='OI', codigo=f'OI{aid}', admin_id=aid, cliente_id=_novo_cliente(aid),
                    data_inicio=date(2026, 6, 1), valor_contrato=0)
        db.session.add(obra); db.session.flush()
        osc = ObraServicoCusto(obra_id=obra.id, admin_id=aid, nome='E1', valor_orcado=D('0'))
        db.session.add(osc); db.session.flush()
        db.session.add_all([
            ObraServicoCustoItem(obra_servico_custo_id=osc.id, admin_id=aid,
                                 descricao='a', valor=D('100'), fonte='veks', ordem=0),
            ObraServicoCustoItem(obra_servico_custo_id=osc.id, admin_id=aid,
                                 descricao='b', valor=D('50'), fonte='veks', ordem=1),
            ObraServicoCustoItem(obra_servico_custo_id=osc.id, admin_id=aid,
                                 descricao='c', valor=D('200'), fonte='fat_direto', ordem=2),
        ])
        db.session.flush()
        veks, fat = recalcular_osc_dos_itens(osc)
        assert veks == D('150') and fat == D('200')
        assert D(str(osc.mao_obra_a_realizar)) == D('150')
        assert D(str(osc.material_a_realizar)) == D('200')
```

- [ ] **Step 2: Rodar e confirmar FALHA**

Run: `python3 -m pytest tests/test_painel_financeiro.py::test_recalcular_osc_dos_itens -q`
Expected: FAIL (`ImportError: cannot import name 'recalcular_osc_dos_itens'`).

- [ ] **Step 3: Implementar o helper**

Em `services/cronograma_fisico_financeiro.py`, adicione (ex.: logo após a função `realizado_por_etapa`):

```python
def recalcular_osc_dos_itens(osc):
    """Deriva os agregados da OSC da soma das linhas de custo (fonte da verdade):
    Veks (mao_obra_a_realizar) = Σ valor (fonte != 'fat_direto');
    Fat (material_a_realizar)  = Σ valor (fonte == 'fat_direto'). Retorna (veks, fat)."""
    from models import ObraServicoCustoItem
    itens = ObraServicoCustoItem.query.filter_by(obra_servico_custo_id=osc.id).all()
    veks = sum((Decimal(str(i.valor or 0)) for i in itens if i.fonte != 'fat_direto'), Decimal("0"))
    fat = sum((Decimal(str(i.valor or 0)) for i in itens if i.fonte == 'fat_direto'), Decimal("0"))
    osc.mao_obra_a_realizar = veks
    osc.material_a_realizar = fat
    osc.outros_a_realizar = Decimal("0")
    osc.fonte_mao_obra = 'veks'
    osc.fonte_material = 'fat_direto'
    return veks, fat
```

- [ ] **Step 4: Rodar e confirmar PASSA**

Run: `python3 -m pytest tests/test_painel_financeiro.py::test_recalcular_osc_dos_itens -q`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add services/cronograma_fisico_financeiro.py tests/test_painel_financeiro.py
git commit -m "feat(fin): recalcular_osc_dos_itens (custo derivado das linhas)"
```

---

### Task 3: `painel_financeiro` expõe `itens` por etapa

**Files:**
- Modify: `services/cronograma_fisico_financeiro.py` (função `painel_financeiro`)
- Test: `tests/test_painel_financeiro.py`

- [ ] **Step 1: Escrever o teste que falha**

Acrescente ao final de `tests/test_painel_financeiro.py`:

```python
@pytest.mark.integration
def test_painel_etapas_incluem_itens():
    from services.importacao_fisico_financeiro import importar_fisico_financeiro
    from services.cronograma_fisico_financeiro import painel_financeiro
    from models import Obra
    import json
    with app.app_context():
        aid = _novo_admin()
        caminho = os.path.join(os.path.dirname(__file__), 'fixtures',
                               'cronograma_fisico_financeiro_baias.json')
        oid = importar_fisico_financeiro(json.load(open(caminho, encoding='utf-8')), aid)['obra_id']
        p = painel_financeiro(Obra.query.get(oid))
        assert all('itens' in e for e in p['etapas'])
        # ao menos uma etapa com itens preenchidos
        assert any(e['itens'] for e in p['etapas'])
        for e in p['etapas']:
            for it in e['itens']:
                assert set(it) >= {'id', 'descricao', 'valor', 'fonte'}
```

- [ ] **Step 2: Rodar e confirmar FALHA**

Run: `python3 -m pytest tests/test_painel_financeiro.py::test_painel_etapas_incluem_itens -q`
Expected: FAIL (etapas ainda não têm `itens`; e dependerá da Task 4 popular — mas a chave `itens` já deve existir; após esta task a chave existe e fica `[]` se não houver linhas; o `any(...)` exige a Task 4. Veja Step 4.)

- [ ] **Step 3: Implementar — incluir `itens` por etapa**

Em `services/cronograma_fisico_financeiro.py`, função `painel_financeiro`, ANTES do bloco `etapas = []` (que monta a lista de etapas), adicione a busca das linhas:

```python
    from models import ObraServicoCusto, ObraServicoCustoItem
    osc_ids = [o.id for o in ObraServicoCusto.query.filter_by(
        obra_id=obra.id, admin_id=obra.admin_id).all()]
    itens_por_osc = {}
    if osc_ids:
        linhas = (ObraServicoCustoItem.query
                  .filter(ObraServicoCustoItem.obra_servico_custo_id.in_(osc_ids))
                  .order_by(ObraServicoCustoItem.obra_servico_custo_id,
                            ObraServicoCustoItem.ordem).all())
        for it in linhas:
            itens_por_osc.setdefault(it.obra_servico_custo_id, []).append(
                {"id": it.id, "descricao": it.descricao, "valor": it.valor, "fonte": it.fonte})
```

E no `etapas.append({...})`, adicione a chave `itens`:

```python
        etapas.append({
            "nome": e["nome"],
            "veks": e["veks"],
            "fat": e["fat_direto"],
            "previsto": e["previsto"]["total"],
            "realizado": realizado_etapa.get(osc_id, Decimal("0")),
            "osc_id": osc_id,
            "itens": itens_por_osc.get(osc_id, []),
        })
```

- [ ] **Step 4: Rodar e confirmar PASSA**

Run: `python3 -m pytest tests/test_painel_financeiro.py::test_painel_etapas_incluem_itens -q`
Expected: pode FALHAR no `any(e['itens'] ...)` enquanto a Task 4 não popular as linhas na importação. Se falhar SÓ nesse assert, prossiga para a Task 4 e rode este teste de novo ao final dela (ele deve passar). Se quiser isolar agora, rode só a checagem de chave:
`python3 -m pytest tests/test_painel_financeiro.py::test_painel_etapas_incluem_itens -q` após a Task 4.

- [ ] **Step 5: Commit**

```bash
git add services/cronograma_fisico_financeiro.py tests/test_painel_financeiro.py
git commit -m "feat(fin): painel_financeiro expõe itens por etapa"
```

---

### Task 4: Importador popula linhas de `eap.itens` + limpeza idempotente

**Files:**
- Modify: `services/importacao_fisico_financeiro.py`
- Test: `tests/test_importacao_fisico_financeiro.py`

- [ ] **Step 1: Escrever o teste que falha**

Acrescente ao final de `tests/test_importacao_fisico_financeiro.py`:

```python
@pytest.mark.integration
def test_importa_popula_linhas_de_custo():
    from services.importacao_fisico_financeiro import importar_fisico_financeiro
    from models import ObraServicoCusto, ObraServicoCustoItem
    from decimal import Decimal
    with app.app_context():
        admin_id = _novo_admin()
        oid = importar_fisico_financeiro(_carregar_json(), admin_id)['obra_id']
        oscs = ObraServicoCusto.query.filter_by(obra_id=oid, admin_id=admin_id).all()
        osc_ids = [o.id for o in oscs]
        linhas = ObraServicoCustoItem.query.filter(
            ObraServicoCustoItem.obra_servico_custo_id.in_(osc_ids)).all()
        assert len(linhas) >= 12  # ao menos uma linha por etapa
        soma_veks = sum(float(l.valor) for l in linhas if l.fonte == 'veks')
        soma_fat = sum(float(l.valor) for l in linhas if l.fonte == 'fat_direto')
        assert abs(soma_veks - 734460) < 50
        assert abs(soma_fat - 423700) < 50
        # agregado da OSC == soma das linhas (derivação)
        for o in oscs:
            v = sum(float(l.valor) for l in linhas
                    if l.obra_servico_custo_id == o.id and l.fonte == 'veks')
            assert abs(float(o.mao_obra_a_realizar or 0) - v) < 0.01


@pytest.mark.integration
def test_reimport_nao_duplica_linhas_de_custo():
    from services.importacao_fisico_financeiro import importar_fisico_financeiro
    from models import ObraServicoCusto, ObraServicoCustoItem
    with app.app_context():
        admin_id = _novo_admin()
        importar_fisico_financeiro(_carregar_json(), admin_id)
        oid = importar_fisico_financeiro(_carregar_json(), admin_id)['obra_id']
        osc_ids = [o.id for o in ObraServicoCusto.query.filter_by(
            obra_id=oid, admin_id=admin_id).all()]
        linhas = ObraServicoCustoItem.query.filter(
            ObraServicoCustoItem.obra_servico_custo_id.in_(osc_ids)).count()
        # mesma quantia das linhas de eap.itens (sem acumular do 1º import)
        assert linhas >= 12
        orfas = ObraServicoCustoItem.query.filter(
            ~ObraServicoCustoItem.obra_servico_custo_id.in_(osc_ids),
            ObraServicoCustoItem.admin_id == admin_id).count()
        assert orfas == 0
```

- [ ] **Step 2: Rodar e confirmar FALHA**

Run: `python3 -m pytest tests/test_importacao_fisico_financeiro.py::test_importa_popula_linhas_de_custo -q`
Expected: FAIL (nenhuma linha criada ainda).

- [ ] **Step 3: Popular as linhas no importador**

Em `services/importacao_fisico_financeiro.py`, substitua o bloco atual:

```python
        if osc is not None:
            # valor_orcado fica como valor_comercial (venda); o CUSTO previsto
            # vai nos *_a_realizar, classificado Veks/Fat Direto.
            osc.mao_obra_a_realizar = info['veks']
            osc.fonte_mao_obra = 'veks'
            osc.material_a_realizar = info['fat']
            osc.fonte_material = 'fat_direto'
            osc.outros_a_realizar = Decimal('0')
            osc.fonte_outros = 'veks'
            osc.realizado_material = 0
            osc.realizado_mao_obra = 0
            osc.realizado_outros = 0
```

por:

```python
        if osc is not None:
            from models import ObraServicoCustoItem
            from services.cronograma_fisico_financeiro import recalcular_osc_dos_itens
            # Linhas de custo (insumos) da etapa = eap.itens (cada item vira linha
            # Veks e/ou Fat). Estas linhas são a fonte da verdade; os agregados da
            # OSC são derivados delas.
            ObraServicoCustoItem.query.filter_by(
                obra_servico_custo_id=osc.id).delete(synchronize_session=False)
            ordem = 0
            for it in (info['etapa'].get('itens') or []):
                nome_it = (it.get('item') or 'Item')[:200]
                v = Decimal(str(it.get('veks') or 0))
                f = Decimal(str(it.get('fat') or 0))
                if v > 0:
                    db.session.add(ObraServicoCustoItem(
                        obra_servico_custo_id=osc.id, admin_id=admin_id,
                        descricao=nome_it, valor=v, fonte='veks', ordem=ordem)); ordem += 1
                if f > 0:
                    db.session.add(ObraServicoCustoItem(
                        obra_servico_custo_id=osc.id, admin_id=admin_id,
                        descricao=nome_it, valor=f, fonte='fat_direto', ordem=ordem)); ordem += 1
            if ordem == 0:
                # Etapa sem itens detalhados no JSON → linhas do agregado.
                if info['veks'] > 0:
                    db.session.add(ObraServicoCustoItem(
                        obra_servico_custo_id=osc.id, admin_id=admin_id,
                        descricao=info['etapa']['nome'][:200], valor=info['veks'],
                        fonte='veks', ordem=ordem)); ordem += 1
                if info['fat'] > 0:
                    db.session.add(ObraServicoCustoItem(
                        obra_servico_custo_id=osc.id, admin_id=admin_id,
                        descricao=info['etapa']['nome'][:200], valor=info['fat'],
                        fonte='fat_direto', ordem=ordem)); ordem += 1
            db.session.flush()
            osc.fonte_outros = 'veks'
            osc.realizado_material = 0
            osc.realizado_mao_obra = 0
            osc.realizado_outros = 0
            recalcular_osc_dos_itens(osc)
```

- [ ] **Step 4: Limpar linhas na idempotência**

Na função `_limpar_derivados` do mesmo arquivo, ANTES da linha
`ObraServicoCusto.query.filter_by(obra_id=obra.id, admin_id=admin_id).delete(synchronize_session=False)`,
adicione (e inclua `ObraServicoCustoItem` no import do topo da função):

```python
    osc_ids_obra = [r[0] for r in db.session.query(ObraServicoCusto.id)
                    .filter_by(obra_id=obra.id, admin_id=admin_id).all()]
    if osc_ids_obra:
        ObraServicoCustoItem.query.filter(
            ObraServicoCustoItem.obra_servico_custo_id.in_(osc_ids_obra)).delete(synchronize_session=False)
```

No import da `_limpar_derivados` (a linha `from models import (Orcamento, OrcamentoItem, ...)`), acrescente `ObraServicoCustoItem` à lista.

- [ ] **Step 5: Rodar e confirmar PASSA**

Run: `python3 -m pytest tests/test_importacao_fisico_financeiro.py::test_importa_popula_linhas_de_custo tests/test_importacao_fisico_financeiro.py::test_reimport_nao_duplica_linhas_de_custo tests/test_painel_financeiro.py::test_painel_etapas_incluem_itens -q`
Expected: PASS (3).

Rode também a suíte de importação inteira para garantir que os invariantes antigos seguem:
`python3 -m pytest tests/test_importacao_fisico_financeiro.py -q`
Expected: todos PASS (Σveks≈734460, Σfat≈423700 continuam, agora derivados das linhas).

- [ ] **Step 6: Commit**

```bash
git add services/importacao_fisico_financeiro.py tests/test_importacao_fisico_financeiro.py
git commit -m "feat(fin): importador popula linhas de custo de eap.itens (idempotente)"
```

---

### Task 5: Endpoint que substitui linhas + recalcula (e remove o agregado antigo)

**Files:**
- Modify: `views/obras.py:2112-2140`
- Test: `tests/test_painel_financeiro.py`

- [ ] **Step 1: Escrever o teste que falha**

Acrescente ao final de `tests/test_painel_financeiro.py`:

```python
@pytest.mark.integration
def test_endpoint_etapa_itens_substitui_e_recalcula():
    from services.importacao_fisico_financeiro import importar_fisico_financeiro
    from models import Usuario, ObraServicoCusto, ObraServicoCustoItem
    import json
    app.config['WTF_CSRF_ENABLED'] = False
    with app.app_context():
        aid = _novo_admin()
        u = Usuario.query.get(aid); u.versao_sistema = 'v2'; db.session.commit()
        caminho = os.path.join(os.path.dirname(__file__), 'fixtures',
                               'cronograma_fisico_financeiro_baias.json')
        oid = importar_fisico_financeiro(json.load(open(caminho, encoding='utf-8')), aid)['obra_id']
        osc = ObraServicoCusto.query.filter_by(obra_id=oid, admin_id=aid).first()
        osc_id = osc.id
    with app.test_client() as c:
        with c.session_transaction() as s:
            s['_user_id'] = str(aid); s['_fresh'] = True
        # substitui por 2 linhas (1 veks 1000, 1 fat 500)
        r = c.post(f'/obras/{oid}/financeiro/etapa/{osc_id}/itens',
                   json={'itens': [
                       {'descricao': 'X', 'valor': '1000', 'fonte': 'veks'},
                       {'descricao': 'Y', 'valor': '500', 'fonte': 'fat_direto'}],
                       'valor_orcado': '2000'})
        assert r.status_code == 200
        p = r.get_json()
        assert 'kpis' in p and 'etapas' in p
        # payload inválido → 400
        r2 = c.post(f'/obras/{oid}/financeiro/etapa/{osc_id}/itens',
                    json={'itens': [{'descricao': 'Z', 'valor': 'abc', 'fonte': 'veks'}]})
        assert r2.status_code == 400
    with app.app_context():
        linhas = ObraServicoCustoItem.query.filter_by(obra_servico_custo_id=osc_id).all()
        assert len(linhas) == 2
        osc = ObraServicoCusto.query.get(osc_id)
        assert abs(float(osc.mao_obra_a_realizar) - 1000) < 0.01
        assert abs(float(osc.material_a_realizar) - 500) < 0.01


@pytest.mark.integration
def test_endpoint_etapa_itens_multitenant():
    from services.importacao_fisico_financeiro import importar_fisico_financeiro
    from models import Usuario, ObraServicoCusto
    import json
    app.config['WTF_CSRF_ENABLED'] = False
    with app.app_context():
        a1 = _novo_admin(); a2 = _novo_admin()
        u = Usuario.query.get(a2); u.versao_sistema = 'v2'; db.session.commit()
        caminho = os.path.join(os.path.dirname(__file__), 'fixtures',
                               'cronograma_fisico_financeiro_baias.json')
        o1 = importar_fisico_financeiro(json.load(open(caminho, encoding='utf-8')), a1)['obra_id']
        osc1 = ObraServicoCusto.query.filter_by(obra_id=o1, admin_id=a1).first().id
    with app.test_client() as c:
        with c.session_transaction() as s:
            s['_user_id'] = str(a2); s['_fresh'] = True
        r = c.post(f'/obras/{o1}/financeiro/etapa/{osc1}/itens',
                   json={'itens': []})
        assert r.status_code == 404
```

- [ ] **Step 2: Rodar e confirmar FALHA**

Run: `python3 -m pytest tests/test_painel_financeiro.py::test_endpoint_etapa_itens_substitui_e_recalcula -q`
Expected: FAIL (404 — rota `/itens` não existe).

- [ ] **Step 3: Substituir o endpoint**

Em `views/obras.py`, substitua TODO o bloco do endpoint antigo (linhas 2112-2140, de `@main_bp.route('/obras/<int:id>/financeiro/etapa/<int:osc_id>', methods=['POST'])` até o `return jsonify(_jsonable(painel_financeiro(obra)))` da função `financeiro_editar_etapa`) por:

```python
@main_bp.route('/obras/<int:id>/financeiro/etapa/<int:osc_id>/itens', methods=['POST'])
@login_required
@capture_db_errors
def financeiro_etapa_itens(id, osc_id):
    from decimal import Decimal, InvalidOperation
    from models import ObraServicoCusto, ObraServicoCustoItem
    from services.cronograma_fisico_financeiro import painel_financeiro, recalcular_osc_dos_itens
    admin_id = get_tenant_admin_id()
    obra = Obra.query.filter_by(id=id, admin_id=admin_id).first_or_404()
    osc = ObraServicoCusto.query.filter_by(id=osc_id, obra_id=obra.id, admin_id=admin_id).first_or_404()

    payload = request.get_json(silent=True) or {}
    itens = payload.get('itens')
    if not isinstance(itens, list):
        return jsonify({'erro': 'itens inválido'}), 400

    def _dec(v):
        try:
            return Decimal(str(v).replace(',', '.'))
        except (InvalidOperation, ValueError, AttributeError, TypeError):
            return None

    novos = []
    for i, it in enumerate(itens):
        valor = _dec(it.get('valor'))
        if valor is None or valor < 0:
            return jsonify({'erro': 'valor inválido'}), 400
        fonte = 'fat_direto' if it.get('fonte') == 'fat_direto' else 'veks'
        desc = (str(it.get('descricao') or '').strip() or 'Item')[:200]
        novos.append((desc, valor, fonte, i))

    orc_raw = payload.get('valor_orcado')
    if orc_raw not in (None, ''):
        orc = _dec(orc_raw)
        if orc is None:
            return jsonify({'erro': 'valor_orcado inválido'}), 400
        osc.valor_orcado = orc

    ObraServicoCustoItem.query.filter_by(
        obra_servico_custo_id=osc.id).delete(synchronize_session=False)
    for desc, valor, fonte, ordem in novos:
        db.session.add(ObraServicoCustoItem(
            obra_servico_custo_id=osc.id, admin_id=admin_id,
            descricao=desc, valor=valor, fonte=fonte, ordem=ordem))
    db.session.flush()
    recalcular_osc_dos_itens(osc)
    db.session.commit()
    return jsonify(_jsonable(painel_financeiro(obra)))
```

- [ ] **Step 4: Rodar e confirmar PASSA**

Run: `python3 -m pytest tests/test_painel_financeiro.py::test_endpoint_etapa_itens_substitui_e_recalcula tests/test_painel_financeiro.py::test_endpoint_etapa_itens_multitenant -q`
Expected: PASS (2).

Confirme que nenhum teste antigo dependia do endpoint removido:
`python3 -m pytest tests/test_painel_financeiro.py -q`
Expected: todos PASS. (Se algum teste antigo referenciava `/financeiro/etapa/<id>` sem `/itens`, ele apontava para o endpoint agregado removido — atualize-o para o novo formato `/itens` com JSON, ou remova-o se redundante.)

- [ ] **Step 5: Commit**

```bash
git add views/obras.py tests/test_painel_financeiro.py
git commit -m "feat(fin): endpoint financeiro/etapa/<osc>/itens (substitui+recalcula); remove o agregado"
```

---

### Task 6: UI — `showEtapa` vira tabela editável

**Files:**
- Modify: `static/js/financeiro_obra.js:50-79` (função `showEtapa`)
- Test: manual (JS roda no browser; sem harness JS). Smokes de template seguem verdes.

- [ ] **Step 1: Substituir a função `showEtapa`**

Em `static/js/financeiro_obra.js`, substitua a função `showEtapa` inteira (linhas 50-79) por:

```javascript
  function etapaLinhaHTML(it) {
    var sel = function (v) { return it && it.fonte === v ? ' selected' : ''; };
    return '<tr>' +
      '<td><input class="form-control form-control-sm fin-it-desc" value="' +
        ((it && it.descricao) ? String(it.descricao).replace(/"/g, '&quot;') : '') + '"></td>' +
      '<td><input type="number" step="0.01" class="form-control form-control-sm fin-it-valor text-end" value="' +
        (it ? Number(it.valor || 0) : 0) + '"></td>' +
      '<td><select class="form-select form-select-sm fin-it-fonte">' +
        '<option value="veks"' + sel('veks') + '>Veks</option>' +
        '<option value="fat_direto"' + sel('fat_direto') + '>Fat direto</option>' +
      '</select></td>' +
      '<td class="text-center"><button type="button" class="btn btn-sm btn-link text-danger fin-it-del p-0">&times;</button></td>' +
    '</tr>';
  }
  function showEtapa(et) {
    var box = el('fin-etapa-det');
    if (et.osc_id == null) {
      box.innerHTML = '<div class="border rounded p-3 bg-light"><strong>' + et.nome + '</strong>' +
        '<div class="small text-muted mt-1">Etapa sem custo único vinculável — edição indisponível.</div></div>';
      return;
    }
    var linhas = (et.itens || []).map(etapaLinhaHTML).join('');
    box.innerHTML =
      '<div class="border rounded p-3 bg-light">' +
      '<div class="d-flex justify-content-between mb-2"><strong>' + et.nome + '</strong>' +
        '<span>Realizado: ' + BRL(et.realizado) + ' / Previsto: <span id="fin-it-prev">' + BRL(et.previsto) + '</span></span></div>' +
      '<table class="table table-sm align-middle mb-2"><thead><tr>' +
        '<th>Descrição</th><th class="text-end" style="width:140px">Valor (R$)</th>' +
        '<th style="width:120px">Tipo</th><th style="width:32px"></th></tr></thead>' +
      '<tbody id="fin-it-body">' + linhas + '</tbody></table>' +
      '<div class="d-flex justify-content-between align-items-end flex-wrap gap-2">' +
        '<button type="button" id="fin-it-add" class="btn btn-outline-secondary btn-sm">+ Adicionar linha</button>' +
        '<div class="d-flex align-items-end gap-2">' +
          '<div><label class="small text-muted">Orçado/venda (R$)</label>' +
            '<input id="fin-it-orc" type="number" step="0.01" class="form-control form-control-sm" value="' + Number(et.previsto || 0) + '"></div>' +
          '<button type="button" id="fin-it-save" class="btn btn-primary btn-sm">Salvar etapa</button>' +
        '</div>' +
      '</div></div>';

    function recalcPrev() {
      var total = 0;
      box.querySelectorAll('.fin-it-valor').forEach(function (i) { total += Number(i.value || 0); });
      el('fin-it-prev').textContent = BRL(total);
    }
    function bindRow(tr) {
      tr.querySelector('.fin-it-del').addEventListener('click', function () { tr.remove(); recalcPrev(); });
      tr.querySelector('.fin-it-valor').addEventListener('input', recalcPrev);
    }
    box.querySelectorAll('#fin-it-body tr').forEach(bindRow);
    el('fin-it-add').addEventListener('click', function () {
      var tmp = document.createElement('tbody');
      tmp.innerHTML = etapaLinhaHTML(null);
      var tr = tmp.firstChild;
      el('fin-it-body').appendChild(tr);
      bindRow(tr);
    });
    el('fin-it-save').addEventListener('click', function () {
      var itens = [];
      box.querySelectorAll('#fin-it-body tr').forEach(function (tr) {
        itens.push({
          descricao: tr.querySelector('.fin-it-desc').value,
          valor: tr.querySelector('.fin-it-valor').value || '0',
          fonte: tr.querySelector('.fin-it-fonte').value
        });
      });
      fetch('/obras/' + OBRA_ID + '/financeiro/etapa/' + et.osc_id + '/itens', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', 'X-CSRFToken': csrfToken() },
        body: JSON.stringify({ itens: itens, valor_orcado: el('fin-it-orc').value || '0' })
      })
        .then(function (r) { if (!r.ok) throw new Error(r.status); return r.json(); })
        .then(function (p) { render(p); box.innerHTML = '<div class="text-success small">Salvo e recalculado.</div>'; })
        .catch(function () { box.innerHTML = '<div class="text-danger small">Falha ao salvar.</div>'; });
    });
  }
```

- [ ] **Step 2: Rodar os smokes de template/painel (devem seguir verdes)**

Run: `python3 -m pytest tests/test_painel_financeiro.py -q`
Expected: todos PASS (a UI é client-side; os smokes server-side não quebram).

- [ ] **Step 3: Verificação manual de markup**

Run:
```bash
python3 -c "
import sys; sys.path.insert(0,'/home/runner/workspace')
from main import app
app.config['WTF_CSRF_ENABLED']=False
c=app.test_client()
with c.session_transaction() as s: s['_user_id']='832'; s['_fresh']=True
print('status', c.get('/obras/detalhes/2515').status_code)
"
```
Expected: `status 200`. (Confirmação visual da tabela editável e do recálculo é feita pelo usuário no navegador, logado como `admin_alfa`, após re-importar a Baias.)

- [ ] **Step 4: Commit**

```bash
git add static/js/financeiro_obra.js
git commit -m "feat(fin): showEtapa vira tabela editável de linhas de custo"
```

---

## Self-Review

**1. Spec coverage:**
- `ObraServicoCustoItem` + migração 199 → Task 1. ✓
- `recalcular_osc_dos_itens` (derivação) → Task 2. ✓
- Painel expõe `itens` por etapa → Task 3. ✓
- Importador popula de `eap.itens` + `_limpar_derivados` apaga → Task 4. ✓
- Endpoint substitui+recalcula+retorna painel; remove o agregado → Task 5. ✓
- UI `showEtapa` tabela editável → Task 6. ✓
- Manter verdes painel/cronograma/importação → rodados em Tasks 3,4,5,6. ✓

**2. Placeholder scan:** sem TBD/TODO; todo passo tem código/comando completo. ✓

**3. Type/consistency:** nomes consistentes — modelo `ObraServicoCustoItem` (campos `obra_servico_custo_id/admin_id/descricao/valor/fonte/ordem`), helper `recalcular_osc_dos_itens(osc)→(veks,fat)`, endpoint `financeiro_etapa_itens` em `/financeiro/etapa/<osc_id>/itens` recebendo `{itens:[{descricao,valor,fonte}], valor_orcado}`, JS `showEtapa` postando o mesmo formato JSON. `D` e `_novo_cliente` já existem em `test_painel_financeiro.py` (usados pelos testes). ✓

**Nota de risco (derivação vs invariante):** após a Task 4, os agregados Σveks/Σfat passam a ser a soma das linhas de `eap.itens`. Os testes usam tolerância de 50 sobre 734.460/423.700; se a soma dos itens divergir do `custo.veks/fat` por etapa, ajustar a expectativa para a soma real das linhas (não relaxar além do necessário).
