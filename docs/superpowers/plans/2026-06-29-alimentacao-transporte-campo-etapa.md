# Alimentação e Transporte ganham o campo "Etapa" (Pedaço 4) — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Os módulos **Alimentação** e **Transporte** ganham um campo **Etapa** (opcional): cada lançamento grava `obra_servico_custo_id` na sua entidade e o repassa à `registrar_custo_automatico`, de modo que o custo entra automaticamente no **Realizado da etapa**.

**Architecture:** `AlimentacaoLancamento` e `LancamentoTransporte` recebem a coluna `obra_servico_custo_id` (migração 206). Os dois forms ganham um `<select>` Etapa em cascata com a Obra, alimentado pelo endpoint já existente `GET /obras/<id>/etapas-custo` (Pedaço 3). As views leem/validam/gravam a etapa e a passam à `registrar_custo_automatico` (que já aceita `obra_servico_custo_id` desde o Pedaço 2). Os agregadores de realizado já somam `GestaoCustoFilho` por `obra_servico_custo_id`, então os custos fluem sozinhos. `lancamentos_da_etapa` ganha rótulos amigáveis para as novas origens (e para o RDO).

**Tech Stack:** Flask + SQLAlchemy (Postgres), migrações idempotentes em `migrations.py`, front Jinja + vanilla JS + Bootstrap 5, testes `pytest`. Verificação visual via Playwright + chromium do Nix (`REPLIT_PLAYWRIGHT_CHROMIUM_EXECUTABLE`).

## Global Constraints

- **Obra-piloto:** Baia. **Previsto inalterado:** veks 800.960 / fat 550.775 / lucro 24.976 / imposto 128.903 / contrato 1.505.613,76 / data_fim 08/10. **Realizado** vem de `GestaoCustoFilho` ligados às etapas; agora alimentação e transporte com etapa também somam.
- **Etapa OPCIONAL** (mesmo com Obra). Sem etapa → comportamento atual. Etapa inválida/de outra obra → tratada como `None` (nunca derruba o lançamento).
- **Grava em dois lugares** (consistente com Compras): coluna `obra_servico_custo_id` na entidade do módulo + repassada à `registrar_custo_automatico`.
- **Migração 206:** número livre confirmado (a 205 é `pedido_compra.obra_servico_custo_id`). Idempotente, padrão do repo: `ADD COLUMN IF NOT EXISTS`.
- **RDO** já amarra a etapa (`origem_tabela='registro_ponto'`, osc via `resolver_obra_servico_custo_id`) — sem mudança de código, só regressão. **Folha** fora de escopo.
- **Reuso:** endpoint `GET /obras/<id>/etapas-custo` (Pedaço 3) já existe — não criar rota nova. `registrar_custo_automatico(..., obra_servico_custo_id=)` (Pedaço 2) já existe.
- Suíte de regressão (rodar após cada task):
  ```
  python -m pytest tests/test_cronograma_fisico_financeiro.py tests/test_painel_financeiro.py tests/test_importacao_fisico_financeiro.py -q
  ```

---

## File Structure

| Arquivo | Responsabilidade | Mudança |
|---|---|---|
| `models.py` (`AlimentacaoLancamento` ~l.1140; `LancamentoTransporte` ~l.4803) | ORM | **Modificar** — `obra_servico_custo_id` + relationship em ambos |
| `migrations.py` (registry ~l.4005; defs ~l.13760) | Schema | **Modificar** — `_migration_206_*` (duas colunas) |
| `transporte_views.py` (`novo_post` l.151) | Criação do transporte | **Modificar** — ler/validar/gravar osc + passar ao helper |
| `alimentacao_views.py` (POST em `/lancamentos/novo-v2` (`lancamento_novo_v2`) ~l.324) | Criação da alimentação | **Modificar** — idem |
| `services/cronograma_fisico_financeiro.py` (`_ORIGEM_LABELS` ~l.600) | Rótulos da aba Realizado | **Modificar** — novas origens |
| `templates/transporte/novo_lancamento.html` (obra select l.78) | UI | **Modificar** — id no obra select + select Etapa + cascata |
| `templates/alimentacao/lancamento_novo_v2.html` (obra select l.526) | UI | **Modificar** — select Etapa + cascata |
| `tests/test_painel_financeiro.py` | Testes | **Modificar** — novos testes |

---

## Task 1: Modelos + migração 206 (`obra_servico_custo_id` em alimentação e transporte)

**Files:**
- Modify: `models.py` (`AlimentacaoLancamento` ~l.1151/1156; `LancamentoTransporte` ~l.4812/4826)
- Modify: `migrations.py` (registry ~l.4005; nova função ~l.13760)
- Test: `tests/test_painel_financeiro.py`

**Interfaces:**
- Produces: `AlimentacaoLancamento.obra_servico_custo_id` e `LancamentoTransporte.obra_servico_custo_id` (Integer FK nullable → `obra_servico_custo.id`) + relationships `obra_servico_custo` em ambos.

- [ ] **Step 1: Write the failing test**

Adicionar a `tests/test_painel_financeiro.py`:

```python
@pytest.mark.integration
def test_alimentacao_transporte_tem_obra_servico_custo_id():
    from models import AlimentacaoLancamento, LancamentoTransporte
    assert 'obra_servico_custo_id' in {c.name for c in AlimentacaoLancamento.__table__.columns}
    assert 'obra_servico_custo_id' in {c.name for c in LancamentoTransporte.__table__.columns}
```

- [ ] **Step 2: Run it — expect FAIL**

Run: `python -m pytest tests/test_painel_financeiro.py::test_alimentacao_transporte_tem_obra_servico_custo_id -v`
Expected: FAIL (colunas ausentes).

- [ ] **Step 3: Coluna + relationship em `AlimentacaoLancamento`**

Em `models.py`, na classe `AlimentacaoLancamento`, logo após `obra_id = db.Column(db.Integer, db.ForeignKey('obra.id'), nullable=False)` (l.1151):

```python
    obra_servico_custo_id = db.Column(
        db.Integer, db.ForeignKey('obra_servico_custo.id'), nullable=True)
```

E logo após `obra = db.relationship('Obra', backref='lancamentos_alimentacao')` (l.1156):

```python
    obra_servico_custo = db.relationship(
        'ObraServicoCusto', foreign_keys=[obra_servico_custo_id])
```

- [ ] **Step 4: Coluna + relationship em `LancamentoTransporte`**

Em `models.py`, na classe `LancamentoTransporte`, logo após `obra_id = db.Column(db.Integer, db.ForeignKey('obra.id'), nullable=True)` (l.4812):

```python
    obra_servico_custo_id = db.Column(
        db.Integer, db.ForeignKey('obra_servico_custo.id'), nullable=True)
```

E logo após `obra = db.relationship('Obra', backref='lancamentos_transporte', foreign_keys=[obra_id])` (l.4826):

```python
    obra_servico_custo = db.relationship(
        'ObraServicoCusto', foreign_keys=[obra_servico_custo_id])
```

- [ ] **Step 5: Migração 206**

Em `migrations.py`, após `_migration_205_pedido_compra_obra_servico_custo`:

```python
def _migration_206_alimentacao_transporte_obra_servico_custo():
    """Alimentação/Transporte por etapa — adiciona obra_servico_custo_id em
    alimentacao_lancamento e lancamento_transporte (FK p/ obra_servico_custo).
    Idempotente. Ver spec 2026-06-29-alimentacao-transporte-campo-etapa-design."""
    from sqlalchemy import text as sa_text
    try:
        with db.engine.begin() as conn:
            for tabela in ('alimentacao_lancamento', 'lancamento_transporte'):
                conn.execute(sa_text(
                    f"ALTER TABLE {tabela} "
                    "ADD COLUMN IF NOT EXISTS obra_servico_custo_id INTEGER "
                    "REFERENCES obra_servico_custo(id)"))
        logger.info("[Migration 206] obra_servico_custo_id adicionada em alimentacao_lancamento e lancamento_transporte.")
    except Exception as e:
        logger.error(f"[Migration 206] Falha: {e}", exc_info=True)
        raise
```

Registrar na lista `migrations_to_run`, após a 205:

```python
            (206, "Alimentação/Transporte por etapa — obra_servico_custo_id", _migration_206_alimentacao_transporte_obra_servico_custo),
```

- [ ] **Step 6: Run it — expect PASS + suíte**

Run: `python -m pytest tests/test_painel_financeiro.py::test_alimentacao_transporte_tem_obra_servico_custo_id -v`
Expected: PASS.
Run: `python -m pytest tests/test_cronograma_fisico_financeiro.py tests/test_painel_financeiro.py tests/test_importacao_fisico_financeiro.py -q`
Expected: verde.

- [ ] **Step 7: Commit**

```bash
git add models.py migrations.py tests/test_painel_financeiro.py
git commit -m "feat(baia): obra_servico_custo_id em alimentacao_lancamento e lancamento_transporte (migração 206)"
```

---

## Task 2: Transporte — `POST /transporte/novo` grava e repassa a etapa

**Files:**
- Modify: `transporte_views.py` (`novo_post`: após a validação de `obra_id` ~l.178; construtor `LancamentoTransporte` ~l.190; chamada `registrar_custo_automatico` ~l.277)
- Test: `tests/test_painel_financeiro.py`

**Interfaces:**
- Consumes: `LancamentoTransporte.obra_servico_custo_id` (Task 1); `registrar_custo_automatico(..., obra_servico_custo_id=)`; endpoint não usado aqui (só na UI).
- Produces: `POST /transporte/novo` com `obra_servico_custo_id` no form → grava no `LancamentoTransporte` (se pertencer à obra+tenant; senão `None`) e o `GestaoCustoFilho` (`origem_tabela='lancamento_transporte'`) herda a etapa.

- [ ] **Step 1: Write the failing test**

```python
@pytest.mark.integration
def test_post_transporte_grava_etapa():
    from services.importacao_fisico_financeiro import importar_fisico_financeiro
    from services.cronograma_fisico_financeiro import realizado_por_etapa
    from models import (Usuario, Obra, ObraServicoCusto, GestaoCustoFilho,
                        CategoriaTransporte, CentroCusto)
    import json, os
    app.config['WTF_CSRF_ENABLED'] = False
    with app.app_context():
        aid = _novo_admin()
        u = Usuario.query.get(aid); u.versao_sistema = 'v2'
        caminho = os.path.join(os.path.dirname(__file__), 'fixtures',
                               'cronograma_fisico_financeiro_baias.json')
        oid = importar_fisico_financeiro(json.load(open(caminho, encoding='utf-8')), aid)['obra_id']
        osc_id = ObraServicoCusto.query.filter_by(obra_id=oid, admin_id=aid).first().id
        cat = CategoriaTransporte(nome='VT', admin_id=aid)
        cc = CentroCusto(admin_id=aid, codigo=f'CC{aid}', nome='CC', tipo='obra', obra_id=oid)
        db.session.add_all([cat, cc]); db.session.commit()
        cat_id, cc_id = cat.id, cc.id
    with app.test_client() as c:
        with c.session_transaction() as s:
            s['_user_id'] = str(aid); s['_fresh'] = True
        r = c.post('/transporte/novo', data={
            'categoria_id': str(cat_id), 'centro_custo_id': str(cc_id),
            'data_lancamento': '2026-06-10', 'valor': '300', 'descricao': 'Van obra',
            'obra_id': str(oid), 'obra_servico_custo_id': str(osc_id),
        })
        assert r.status_code in (200, 302)
    with app.app_context():
        f = GestaoCustoFilho.query.filter_by(origem_tabela='lancamento_transporte').first()
        assert f is not None and f.obra_servico_custo_id == osc_id
        assert float(realizado_por_etapa(Obra.query.get(oid)).get(osc_id, 0)) >= 300 - 1
```

- [ ] **Step 2: Run it — expect FAIL**

Run: `python -m pytest tests/test_painel_financeiro.py::test_post_transporte_grava_etapa -v`
Expected: FAIL — `f.obra_servico_custo_id` é `None` (o POST ignora a etapa) e `realizado_por_etapa` não soma.

- [ ] **Step 3: Ler e validar a etapa no `novo_post`**

Em `transporte_views.py`, em `novo_post`, logo após o bloco que converte `obra_id` para int (`if obra_id: obra_id = int(obra_id)`, ~l.177-178), adicionar:

```python
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

- [ ] **Step 4: Gravar a etapa no `LancamentoTransporte`**

Em `transporte_views.py`, no construtor `lancamento = LancamentoTransporte(...)` (~l.190-201), adicionar a linha `obra_servico_custo_id=osc_id,` (logo após `obra_id=obra_id,`):

```python
        lancamento = LancamentoTransporte(
            categoria_id=categoria_id,
            funcionario_id=funcionario_id,
            veiculo_id=veiculo_id,
            centro_custo_id=centro_custo_id,
            obra_id=obra_id,
            obra_servico_custo_id=osc_id,
            data_lancamento=data_lancamento,
            valor=valor,
            descricao=descricao,
            comprovante_url=comprovante_url,
            admin_id=admin_id,
        )
```

- [ ] **Step 5: Passar a etapa à `registrar_custo_automatico`**

Em `transporte_views.py`, na chamada `registrar_custo_automatico(...)` da integração de custo (~l.277-289), adicionar `obra_servico_custo_id=osc_id,` (logo após `obra_id=obra_id,`):

```python
                registrar_custo_automatico(
                    admin_id=admin_id,
                    tipo_categoria='TRANSPORTE',
                    entidade_nome=_entidade_nome,
                    entidade_id=_entidade_id,
                    data=data_lancamento,
                    descricao=descricao or f'Lançamento de transporte — {_entidade_nome}',
                    valor=_valor_liquido,
                    obra_id=obra_id,
                    obra_servico_custo_id=osc_id,
                    centro_custo_id=centro_custo_id,
                    origem_tabela='lancamento_transporte',
                    origem_id=lancamento.id,
                )
```

- [ ] **Step 6: Run it — expect PASS + suíte**

Run: `python -m pytest tests/test_painel_financeiro.py::test_post_transporte_grava_etapa -v`
Expected: PASS.
Run: `python -m pytest tests/test_cronograma_fisico_financeiro.py tests/test_painel_financeiro.py tests/test_importacao_fisico_financeiro.py -q`
Expected: verde.

- [ ] **Step 7: Commit**

```bash
git add transporte_views.py tests/test_painel_financeiro.py
git commit -m "feat(baia): transporte grava obra_servico_custo_id e amarra ao realizado da etapa"
```

---

## Task 3: Alimentação — POST grava e repassa a etapa

**Files:**
- Modify: `alimentacao_views.py` (POST em `/lancamentos/novo`: após a validação da obra ~l.337; construtor `AlimentacaoLancamento` ~l.436; chamada `registrar_custo_automatico` ~l.520)
- Test: `tests/test_painel_financeiro.py`

**Interfaces:**
- Consumes: `AlimentacaoLancamento.obra_servico_custo_id` (Task 1); `registrar_custo_automatico(..., obra_servico_custo_id=)`.
- Produces: `POST /alimentacao/lancamentos/novo-v2` (função `lancamento_novo_v2`) com `obra_servico_custo_id` → grava no `AlimentacaoLancamento` (se pertencer à obra+tenant; senão `None`) e o `GestaoCustoFilho` (`origem_tabela='alimentacao_lancamento'`) herda a etapa.

- [ ] **Step 1: Write the failing test**

```python
@pytest.mark.integration
def test_post_alimentacao_grava_etapa():
    from services.importacao_fisico_financeiro import importar_fisico_financeiro
    from services.cronograma_fisico_financeiro import realizado_por_etapa
    from models import Usuario, Obra, ObraServicoCusto, AlimentacaoLancamento, GestaoCustoFilho
    import json, os
    app.config['WTF_CSRF_ENABLED'] = False
    with app.app_context():
        aid = _novo_admin()
        u = Usuario.query.get(aid); u.versao_sistema = 'v2'
        caminho = os.path.join(os.path.dirname(__file__), 'fixtures',
                               'cronograma_fisico_financeiro_baias.json')
        oid = importar_fisico_financeiro(json.load(open(caminho, encoding='utf-8')), aid)['obra_id']
        osc_id = ObraServicoCusto.query.filter_by(obra_id=oid, admin_id=aid).first().id
        db.session.commit()
    with app.test_client() as c:
        with c.session_transaction() as s:
            s['_user_id'] = str(aid); s['_fresh'] = True
        r = c.post('/alimentacao/lancamentos/novo-v2', data={
            'obra_id': str(oid), 'data': '2026-06-10', 'descricao': 'Refeições',
            'obra_servico_custo_id': str(osc_id),
            'itens[0][preco]': '120', 'itens[0][quantidade]': '1',
            'itens[0][nome]': 'Marmita',
        })
        assert r.status_code in (200, 302)
    with app.app_context():
        al = AlimentacaoLancamento.query.filter_by(obra_id=oid).first()
        assert al is not None and al.obra_servico_custo_id == osc_id
        f = GestaoCustoFilho.query.filter_by(origem_tabela='alimentacao_lancamento', obra_id=oid).first()
        assert f is not None and f.obra_servico_custo_id == osc_id
        assert float(realizado_por_etapa(Obra.query.get(oid)).get(osc_id, 0)) >= 120 - 1
```

- [ ] **Step 2: Run it — expect FAIL**

Run: `python -m pytest tests/test_painel_financeiro.py::test_post_alimentacao_grava_etapa -v`
Expected: FAIL — `al.obra_servico_custo_id` é `None` (o POST ignora a etapa).

- [ ] **Step 3: Ler e validar a etapa no POST**

Em `alimentacao_views.py`, no bloco `if request.method == 'POST':`, logo após a validação da obra (o `obra = Obra.query.filter_by(...)` + `if not obra: ... return redirect(...)`, ~l.334-337), adicionar:

```python
            osc_raw = request.form.get('obra_servico_custo_id') or None
            osc_id = None
            if osc_raw:
                try:
                    _oid = int(osc_raw)
                except (TypeError, ValueError):
                    _oid = None
                if _oid:
                    from models import ObraServicoCusto as _OSC
                    if _OSC.query.filter_by(id=_oid, obra_id=obra.id, admin_id=admin_id).first():
                        osc_id = _oid
```

- [ ] **Step 4: Gravar a etapa no `AlimentacaoLancamento`**

Em `alimentacao_views.py`, no construtor `lancamento = AlimentacaoLancamento(...)` (~l.436-443), adicionar `obra_servico_custo_id=osc_id,` (logo após `obra_id=obra.id,`):

```python
            lancamento = AlimentacaoLancamento(
                data=datetime.strptime(request.form['data'], '%Y-%m-%d').date(),
                valor_total=valor_total,
                descricao=request.form.get('descricao', ''),
                restaurante_id=restaurante.id if restaurante else None,
                obra_id=obra.id,
                obra_servico_custo_id=osc_id,
                admin_id=admin_id
            )
```

- [ ] **Step 5: Passar a etapa à `registrar_custo_automatico`**

Em `alimentacao_views.py`, na chamada `registrar_custo_automatico(...)` (~l.520-531), adicionar `obra_servico_custo_id=osc_id,` (logo após `obra_id=obra.id if obra else None,`):

```python
                registrar_custo_automatico(
                    admin_id=admin_id,
                    tipo_categoria='ALIMENTACAO',
                    entidade_nome=_rest_nome,
                    entidade_id=restaurante.id if restaurante else None,
                    data=lancamento.data,
                    descricao=lancamento.descricao or f'Refeições — {_rest_nome}',
                    valor=float(valor_total),
                    obra_id=obra.id if obra else None,
                    obra_servico_custo_id=osc_id,
                    origem_tabela='alimentacao_lancamento',
                    origem_id=lancamento.id,
                )
```

- [ ] **Step 6: Run it — expect PASS + suíte**

Run: `python -m pytest tests/test_painel_financeiro.py::test_post_alimentacao_grava_etapa -v`
Expected: PASS.
Run: `python -m pytest tests/test_cronograma_fisico_financeiro.py tests/test_painel_financeiro.py tests/test_importacao_fisico_financeiro.py -q`
Expected: verde.

- [ ] **Step 7: Commit**

```bash
git add alimentacao_views.py tests/test_painel_financeiro.py
git commit -m "feat(baia): alimentação grava obra_servico_custo_id e amarra ao realizado da etapa"
```

---

## Task 4: Rótulos da aba Realizado para as novas origens

**Files:**
- Modify: `services/cronograma_fisico_financeiro.py` (`_ORIGEM_LABELS` ~l.600)
- Test: `tests/test_painel_financeiro.py`

**Interfaces:**
- Produces: `lancamentos_da_etapa` rotula `alimentacao_lancamento`→`Alimentação`, `lancamento_transporte`→`Transporte`, `registro_ponto`→`Mão de obra`, `registro_ponto_va`→`Vale alimentação`, `registro_ponto_vt`→`Vale transporte` (todos `editavel=False`).

- [ ] **Step 1: Write the failing test**

```python
@pytest.mark.integration
def test_lancamentos_da_etapa_rotula_alimentacao_transporte_rdo():
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
        casos = [('alimentacao_lancamento', 'Alimentação', 'ALIMENTACAO'),
                 ('lancamento_transporte', 'Transporte', 'TRANSPORTE'),
                 ('registro_ponto', 'Mão de obra', 'MAO_OBRA_DIRETA')]
        for origem, _label, cat in casos:
            pai = GestaoCustoPai(admin_id=aid, tipo_categoria=cat, entidade_nome='X',
                                 valor_total=Decimal('10'), status='PENDENTE')
            db.session.add(pai); db.session.flush()
            db.session.add(GestaoCustoFilho(
                pai_id=pai.id, admin_id=aid, obra_id=oid, obra_servico_custo_id=osc.id,
                data_referencia=date(2026, 6, 10), descricao=origem,
                valor=Decimal('10'), origem_tabela=origem))
        db.session.commit()
        out = {l['descricao']: l for l in lancamentos_da_etapa(obra, osc.id)}
        assert out['alimentacao_lancamento']['origem_label'] == 'Alimentação'
        assert out['lancamento_transporte']['origem_label'] == 'Transporte'
        assert out['registro_ponto']['origem_label'] == 'Mão de obra'
        assert all(out[k]['editavel'] is False for k in out)
```

- [ ] **Step 2: Run it — expect FAIL**

Run: `python -m pytest tests/test_painel_financeiro.py::test_lancamentos_da_etapa_rotula_alimentacao_transporte_rdo -v`
Expected: FAIL — rótulos vêm crus (`'alimentacao_lancamento'` etc.).

- [ ] **Step 3: Estender `_ORIGEM_LABELS`**

Em `services/cronograma_fisico_financeiro.py`, substituir a definição de `_ORIGEM_LABELS` (l.600) por:

```python
_ORIGEM_LABELS = {
    'lancamento_periodo_manual': 'Manual',
    'pedido_compra': 'Compra',
    'alimentacao_lancamento': 'Alimentação',
    'lancamento_transporte': 'Transporte',
    'registro_ponto': 'Mão de obra',
    'registro_ponto_va': 'Vale alimentação',
    'registro_ponto_vt': 'Vale transporte',
}
```

- [ ] **Step 4: Run it — expect PASS**

Run: `python -m pytest tests/test_painel_financeiro.py::test_lancamentos_da_etapa_rotula_alimentacao_transporte_rdo -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add services/cronograma_fisico_financeiro.py tests/test_painel_financeiro.py
git commit -m "feat(baia): rótulos da aba Realizado para alimentação/transporte/mão de obra"
```

---

## Task 5: UI — select Etapa em cascata nos forms de Alimentação e Transporte

**Files:**
- Modify: `templates/transporte/novo_lancamento.html` (obra select l.78)
- Modify: `templates/alimentacao/lancamento_novo_v2.html` (obra select l.526)

**Interfaces:**
- Consumes: `GET /obras/<id>/etapas-custo` (Pedaço 3).
- Produces: `<select name="obra_servico_custo_id" id="oscSelect">` em ambos os forms, populado em cascata e enviado no POST.

- [ ] **Step 1: Transporte — id no obra select + select Etapa**

Em `templates/transporte/novo_lancamento.html`, trocar a linha do obra select (l.78) para incluir um `id`:

```html
              <select name="obra_id" id="obraSelect" class="form-select" required>
```

E imediatamente após o `</select>` desse campo de Obra (e antes de fechar a coluna/`</div>` do campo), inserir o bloco da Etapa:

```html
              <div class="mt-2">
                <label class="form-label">Etapa <small class="text-muted">(opcional)</small></label>
                <select name="obra_servico_custo_id" id="oscSelect" class="form-select" disabled>
                  <option value="">— Sem etapa —</option>
                </select>
                <small class="text-muted">Amarra o custo a uma etapa da obra (entra no Realizado dela).</small>
              </div>
```

- [ ] **Step 2: Transporte — JS da cascata**

Em `templates/transporte/novo_lancamento.html`, antes do `{% endblock %}` final (ou ao fim do bloco de scripts existente), adicionar:

```html
<script>
(function () {
  var obraSel = document.getElementById('obraSelect');
  var oscSel = document.getElementById('oscSelect');
  if (!obraSel || !oscSel) return;
  function carregarEtapas(obraId) {
    oscSel.innerHTML = '<option value="">— Sem etapa —</option>';
    if (!obraId) { oscSel.disabled = true; return; }
    fetch('/obras/' + obraId + '/etapas-custo', { headers: { 'X-Requested-With': 'XMLHttpRequest' } })
      .then(function (r) { if (!r.ok) throw new Error(r.status); return r.json(); })
      .then(function (d) {
        (d.etapas || []).forEach(function (e) {
          var o = document.createElement('option');
          o.value = e.id; o.textContent = e.nome; oscSel.appendChild(o);
        });
        oscSel.disabled = false;
      })
      .catch(function () { oscSel.disabled = true; });
  }
  obraSel.addEventListener('change', function () { carregarEtapas(obraSel.value); });
  carregarEtapas(obraSel.value);
})();
</script>
```

- [ ] **Step 3: Alimentação — select Etapa após o obra select**

Em `templates/alimentacao/lancamento_novo_v2.html`, imediatamente após o `</select>` do campo `<select ... name="obra_id" id="obra_id" required>` (l.526), inserir:

```html
                        <div class="mt-2">
                          <label class="form-label">Etapa <small class="text-muted">(opcional)</small></label>
                          <select name="obra_servico_custo_id" id="oscSelect" class="form-select" disabled>
                            <option value="">— Sem etapa —</option>
                          </select>
                          <small class="text-muted">Amarra o custo a uma etapa da obra (entra no Realizado dela).</small>
                        </div>
```

- [ ] **Step 4: Alimentação — JS da cascata**

Em `templates/alimentacao/lancamento_novo_v2.html`, antes do `{% endblock %}` final (ou ao fim do bloco de scripts), adicionar:

```html
<script>
(function () {
  var obraSel = document.getElementById('obra_id');
  var oscSel = document.getElementById('oscSelect');
  if (!obraSel || !oscSel) return;
  function carregarEtapas(obraId) {
    oscSel.innerHTML = '<option value="">— Sem etapa —</option>';
    if (!obraId) { oscSel.disabled = true; return; }
    fetch('/obras/' + obraId + '/etapas-custo', { headers: { 'X-Requested-With': 'XMLHttpRequest' } })
      .then(function (r) { if (!r.ok) throw new Error(r.status); return r.json(); })
      .then(function (d) {
        (d.etapas || []).forEach(function (e) {
          var o = document.createElement('option');
          o.value = e.id; o.textContent = e.nome; oscSel.appendChild(o);
        });
        oscSel.disabled = false;
      })
      .catch(function () { oscSel.disabled = true; });
  }
  obraSel.addEventListener('change', function () { carregarEtapas(obraSel.value); });
  carregarEtapas(obraSel.value);
})();
</script>
```

- [ ] **Step 5: Verificar que a app importa (templates compilam sob demanda)**

Run: `python -c "from app import app; print('app import ok')"`
Expected: `app import ok` (sem erro fatal). A verificação real é visual no Step 6.

- [ ] **Step 6: Verificação visual (browser real)**

Subir a app (`gunicorn --bind 0.0.0.0:5000 --reuse-port --reload main:app`) e, com o chromium do Nix
(`$REPLIT_PLAYWRIGHT_CHROMIUM_EXECUTABLE`) via Playwright, logar (`admin@construtoraalfa.com.br` /
`Alfa@2026`). Conferir, em **Transporte → Novo** e **Alimentação → Novo lançamento**:
1. Ao escolher uma **Obra** com etapas, o select **Etapa** habilita e lista as etapas daquela obra.
2. Registrar um lançamento com Obra + Etapa.
3. Abrir a obra → Financeiro → a etapa → aba **Realizado — lançamentos**: o custo aparece com badge **"Transporte"** / **"Alimentação"** (só leitura) e soma no Realizado.

- [ ] **Step 7: Commit**

```bash
git add templates/transporte/novo_lancamento.html templates/alimentacao/lancamento_novo_v2.html
git commit -m "feat(baia): select Etapa em cascata nos forms de Transporte e Alimentação"
```

---

## Task 6: Fechamento — RDO (regressão) + ponta-a-ponta + suíte

**Files:**
- Test: `tests/test_painel_financeiro.py`

- [ ] **Step 1: Teste de regressão do RDO (mão de obra já amarra a etapa)**

```python
@pytest.mark.integration
def test_rdo_mao_de_obra_no_realizado_da_etapa():
    from services.importacao_fisico_financeiro import importar_fisico_financeiro
    from services.cronograma_fisico_financeiro import realizado_por_etapa, lancamentos_da_etapa
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
        pai = GestaoCustoPai(admin_id=aid, tipo_categoria='MAO_OBRA_DIRETA',
                             entidade_nome='Equipe', valor_total=Decimal('800'),
                             status='PENDENTE')
        db.session.add(pai); db.session.flush()
        db.session.add(GestaoCustoFilho(
            pai_id=pai.id, admin_id=aid, obra_id=oid, obra_servico_custo_id=osc.id,
            data_referencia=date(2026, 6, 10), descricao='Diária pedreiro',
            valor=Decimal('800'), origem_tabela='registro_ponto'))
        db.session.commit()
        assert float(realizado_por_etapa(obra).get(osc.id, 0)) >= 800 - 1
        lanc = next(l for l in lancamentos_da_etapa(obra, osc.id) if l['descricao'] == 'Diária pedreiro')
        assert lanc['origem_label'] == 'Mão de obra' and lanc['editavel'] is False
```

- [ ] **Step 2: Rodar + invariantes**

Run: `python -m pytest tests/test_painel_financeiro.py::test_rdo_mao_de_obra_no_realizado_da_etapa -v`
Expected: PASS.
Run: `python -m pytest tests/test_cronograma_fisico_financeiro.py tests/test_painel_financeiro.py tests/test_importacao_fisico_financeiro.py -q`
Expected: verde; invariantes da Baia (veks 800.960 / fat 550.775 / lucro 24.976 / imposto 128.903) preservados.

- [ ] **Step 3: Suíte inteira (não-browser)**

Run: `python -m pytest -q --ignore=scripts --ignore=archive -k "not playwright and not browser"`
Expected: sem regressões fora do escopo (falhas pré-existentes são Playwright/ambiente e os 2 erros de coleta em `scripts/`/`archive/`).

- [ ] **Step 4: Commit**

```bash
git add tests/test_painel_financeiro.py
git commit -m "test(baia): RDO mão de obra no realizado da etapa (regressão)"
```

---

## Sequência de dependências

```
T1 (colunas + migração) → T2 (transporte) , T3 (alimentação)
T1 → T4 (rótulos) [monta filhos direto]
T1 → T5 (UI) [endpoint já existe]
T2, T3, T4 → T6 (fechamento)
```

## Rollback
Cada task é um commit isolado. Reverter T5 mantém o backend (T1-T4) estável. A migração 206 é idempotente (`ADD COLUMN IF NOT EXISTS`) e as colunas são nullable — reverter o modelo deixa as colunas órfãs sem quebrar.

---

## Self-Review

**1. Spec coverage**

| Requisito da spec | Task |
|---|---|
| `AlimentacaoLancamento.obra_servico_custo_id` + relationship | T1 |
| `LancamentoTransporte.obra_servico_custo_id` + relationship | T1 |
| Migração 206 (duas colunas), idempotente | T1 |
| Transporte: ler/validar/gravar + passar ao helper | T2 |
| Alimentação: ler/validar/gravar + passar ao helper | T3 |
| Etapa opcional / inválida → None | T2/T3 (validação por obra+admin) |
| Custos entram no realizado da etapa | T2/T3 (`realizado_por_etapa` assert) |
| `origem_label` Alimentação/Transporte/Mão de obra (+VA/VT) | T4 |
| RDO já amarra (regressão) | T6 |
| UI: select Etapa em cascata nos 2 forms | T5 |
| Folha fora de escopo | — (não há task; documentado na spec) |
| Invariantes da Baia; suíte verde | T6 |

**2. Placeholder scan** — sem TBD/TODO; cada step de código mostra o código completo; comandos com expected output. A verificação de UI (cascata + custos no realizado) é manual no browser real (T5 Step 6), mesmo padrão dos pedaços anteriores.

**3. Type consistency** —
- Coluna `obra_servico_custo_id` (T1) lida/gravada por T2 (`LancamentoTransporte`) e T3 (`AlimentacaoLancamento`), e passada a `registrar_custo_automatico(..., obra_servico_custo_id=)` (assinatura do Pedaço 2).
- `origem_tabela` consistente entre criação e rótulo: `'lancamento_transporte'` (T2/código existente), `'alimentacao_lancamento'` (T3/código existente), `'registro_ponto'` (RDO/event_manager) — todos mapeados em `_ORIGEM_LABELS` (T4) e exercitados em T4/T6.
- Endpoint `GET /obras/<id>/etapas-custo` retorna `{etapas:[{id,nome}]}` (Pedaço 3), consumido pelo JS de T5 (`d.etapas`, `e.id`, `e.nome`).
- `realizado_por_etapa(obra) -> {osc_id: Decimal}` usado em T2/T3/T6.
</content>
